#!/usr/bin/env python3
"""
Coursera Automation AI Backend
Provides intelligent question answering for Coursera quizzes
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


def _load_dotenv() -> None:
    """Load .env from project root into os.environ (does not override existing vars)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

# Optional AI libraries - install as needed
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    AsyncOpenAI = None  # type: ignore

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2-chat-latest")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")


def _gemini_min_interval_for_model(model: str) -> float:
    """Spacing between Gemini calls — tighter limits on newer flash models."""
    if os.environ.get("GEMINI_MIN_INTERVAL_SEC"):
        return float(os.environ["GEMINI_MIN_INTERVAL_SEC"])
    m = (model or "").lower()
    if "2.0" in m or m.startswith("gemini-2-flash"):
        return 6.0
    if "lite" in m:
        return 8.0
    if "2.5" in m or "3." in m or "3-" in m:
        return 15.0
    return 10.0
CURSOR_AGENT_BIN = os.environ.get("CURSOR_AGENT_BIN", "").strip()
CURSOR_AGENT_MODEL = os.environ.get("CURSOR_AGENT_MODEL", "").strip()
CURSOR_AGENT_TIMEOUT_SEC = float(os.environ.get("CURSOR_AGENT_TIMEOUT_SEC", "180"))
VALID_AI_PROVIDERS = ("openai", "gemini", "claude", "cursor", "agent")
_raw_provider = os.environ.get("AI_PROVIDER", "openai").strip().lower()
AI_PROVIDER = "cursor" if _raw_provider == "agent" else _raw_provider

try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    google_genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    from anthropic import AsyncAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    AsyncAnthropic = None  # type: ignore

try:
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Coursera Automation AI", version="1.0.0")

# Enable CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    options: List[str]
    type: str = "multiple-choice"
    context: Optional[str] = None

class AnswerResponse(BaseModel):
    answer: str
    answers: Optional[List[str]] = None
    confidence: float
    reasoning: Optional[str] = None
    source: str

@dataclass
class AIProvider:
    name: str
    enabled: bool
    priority: int

def _is_multi_select(question_type: str) -> bool:
    t = (question_type or "").lower()
    return t in ("multiple-select", "checkbox", "multiple_select", "multi-select")


_MULTI_HINT_RE = re.compile(
    r"choose\s+(?:two|three|four|five|\d+)|select\s+all|choose\s+all|"
    r"\(choose\s+(?:two|three|four|five|\d+)\)",
    re.IGNORECASE,
)


def _effective_question_type(question: str, question_type: str) -> str:
    """Infer checkbox / choose-N from question text when the extension sends radio type."""
    if _is_multi_select(question_type):
        return question_type
    if question and _MULTI_HINT_RE.search(question):
        return "multiple-select"
    return question_type or "multiple-choice"


def _expected_answer_count(question: str) -> Optional[int]:
    if not question:
        return None
    q = question.lower()
    m = re.search(r"choose\s+(two|three|four|five|(\d+))", q)
    if not m:
        return None
    token = m.group(1)
    words = {"two": 2, "three": 3, "four": 4, "five": 5}
    if token in words:
        return words[token]
    if token.isdigit():
        return int(token)
    return None


def _strip_markdown_fences(content: str) -> str:
    text = (content or "").strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json_object(content: str) -> dict:
    text = _strip_markdown_fences(content)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise json.JSONDecodeError("No JSON object in LLM response", text, 0)


def _split_answer_blob(blob: str) -> List[str]:
    blob = (blob or "").strip()
    if not blob:
        return []
    if ";" in blob:
        return [p.strip() for p in blob.split(";") if p.strip()]
    if "|" in blob:
        return [p.strip() for p in blob.split("|") if p.strip()]
    if re.search(r",\s*[A-E][).]\s", blob, re.IGNORECASE):
        parts = re.split(r",\s*(?=[A-E][).]\s)", blob, flags=re.IGNORECASE)
        return [p.strip() for p in parts if p.strip()]
    return [blob]


def _expand_letter_answers(answers: List[str], options: List[str]) -> List[str]:
    expanded: List[str] = []
    for raw in answers:
        token = raw.strip()
        if re.fullmatch(r"[A-Ea-e]", token) and options:
            idx = ord(token.upper()) - ord("A")
            if 0 <= idx < len(options):
                expanded.append(options[idx])
                continue
        expanded.append(raw)
    return expanded


def _parse_llm_json(
    content: str,
    question_type: str,
    options: Optional[List[str]] = None,
) -> Tuple[List[str], float, str]:
    """Parse OpenAI / Gemini JSON (or fenced JSON) into a list of answer strings."""
    try:
        parsed = _extract_json_object(content)
        confidence = float(parsed.get("confidence", 0.85))
        reasoning = str(parsed.get("reasoning", "") or "")

        answers: List[str] = []
        raw_answers = parsed.get("answers")
        if isinstance(raw_answers, list) and raw_answers:
            answers = [str(a).strip() for a in raw_answers if str(a).strip()]
        elif isinstance(raw_answers, str) and raw_answers.strip():
            answers = _split_answer_blob(raw_answers)

        if not answers:
            single = str(parsed.get("answer", "")).strip()
            if single:
                answers = (
                    _split_answer_blob(single)
                    if _is_multi_select(question_type)
                    and (";" in single or "|" in single)
                    else [single]
                )

        if _is_multi_select(question_type) and len(answers) <= 1:
            combined = str(parsed.get("answer", "")).strip()
            if combined and (";" in combined or "|" in combined):
                answers = _split_answer_blob(combined)

        if options and answers:
            answers = _expand_letter_answers(answers, options)

        return answers, confidence, reasoning
    except (json.JSONDecodeError, TypeError, ValueError):
        text = _strip_markdown_fences(content)
        if _is_multi_select(question_type):
            if ";" in text or "|" in text:
                return _split_answer_blob(text), 0.7, "Split plain-text multi-select response"
        return ([text] if text else []), 0.75, "Parsed from plain-text model response"


def _resolve_cursor_agent_bin() -> Optional[str]:
    """Find Cursor Agent CLI binary (`agent` / `cursor-agent`)."""
    if CURSOR_AGENT_BIN:
        path = shutil.which(CURSOR_AGENT_BIN) or (
            CURSOR_AGENT_BIN if os.path.isfile(CURSOR_AGENT_BIN) else None
        )
        if path:
            return path
    for candidate in ("agent", "cursor-agent", "cursor"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def _extract_cursor_cli_text(stdout: str) -> str:
    """Parse Cursor Agent CLI --output-format json (or plain text) stdout."""
    text = (stdout or "").strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            break
        else:
            return text

    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return text

    for key in ("result", "text", "output", "answer"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            joined = "".join(parts).strip()
            if joined:
                return joined

    return text


def _llm_system_prompt(question_type: str) -> str:
    if _is_multi_select(question_type):
        return (
            "You are an expert quiz assistant for university courses. "
            "The user will give you a question and a labeled list of options (A, B, C…). "
            "Pick every correct option. "
            "Reply with ONLY a JSON object — no markdown, no explanation outside JSON:\n"
            '{"answers": ["full text of option 1", "full text of option 2"], '
            '"answer": "full text of option 1", '
            '"confidence": 0.95, "reasoning": "one sentence"}\n'
            "The strings in answers[] must be copied EXACTLY as they appear in the options list."
        )
    return (
        "You are an expert quiz assistant for university courses. "
        "The user will give you a question and a labeled list of options (A, B, C…). "
        "Pick the single best correct answer. "
        "Reply with ONLY a JSON object — no markdown, no explanation outside JSON:\n"
        '{"answer": "full text of the correct option", '
        '"confidence": 0.95, "reasoning": "one sentence"}\n'
        "The answer string must be copied EXACTLY as it appears in the options list."
    )


class CourseraAI:
    def __init__(self):
        self.qa_pipeline = None
        self.openai_client = None
        self.gemini_client = None
        self.anthropic_client = None
        self.openai_model = OPENAI_MODEL
        self.gemini_model = GEMINI_MODEL
        self.claude_model = CLAUDE_MODEL
        self.cursor_agent_bin = _resolve_cursor_agent_bin()
        self.cursor_agent_model = CURSOR_AGENT_MODEL
        self.ai_provider = AI_PROVIDER if AI_PROVIDER in VALID_AI_PROVIDERS else "openai"
        if AI_PROVIDER not in VALID_AI_PROVIDERS:
            logger.warning(f"Unknown AI_PROVIDER={AI_PROVIDER!r}, using openai")

        openai_ready = False
        gemini_ready = False
        claude_ready = False
        cursor_ready = False

        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if HAS_OPENAI and openai_key:
            self.openai_client = AsyncOpenAI(api_key=openai_key)
            openai_ready = True
        elif HAS_OPENAI and self.ai_provider == "openai":
            logger.warning("OPENAI_API_KEY not set — OpenAI unavailable")

        gemini_key = (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )
        if HAS_GEMINI and gemini_key:
            self.gemini_client = google_genai.Client(api_key=gemini_key)
            gemini_ready = True
        elif HAS_GEMINI and self.ai_provider == "gemini":
            logger.warning("GEMINI_API_KEY / GOOGLE_API_KEY not set — Gemini unavailable")

        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if HAS_ANTHROPIC and anthropic_key:
            self.anthropic_client = AsyncAnthropic(api_key=anthropic_key)
            claude_ready = True
        elif HAS_ANTHROPIC and self.ai_provider == "claude":
            logger.warning("ANTHROPIC_API_KEY not set — Claude unavailable")

        if self.cursor_agent_bin:
            cursor_ready = True
        elif self.ai_provider == "cursor":
            logger.warning(
                "Cursor Agent CLI not found — install: curl https://cursor.com/install -fsS | bash "
                "or set CURSOR_AGENT_BIN in .env"
            )

        llm_active = (
            (self.ai_provider == "openai" and openai_ready)
            or (self.ai_provider == "gemini" and gemini_ready)
            or (self.ai_provider == "claude" and claude_ready)
            or (self.ai_provider == "cursor" and cursor_ready)
        )

        if llm_active:
            if self.ai_provider == "openai":
                logger.info(f"Active LLM: OpenAI ({self.openai_model})")
            elif self.ai_provider == "gemini":
                logger.info(f"Active LLM: Gemini ({self.gemini_model})")
            elif self.ai_provider == "claude":
                logger.info(f"Active LLM: Claude ({self.claude_model})")
            else:
                model_label = self.cursor_agent_model or "default"
                logger.info(
                    f"Active LLM: Cursor Agent CLI ({self.cursor_agent_bin}, model={model_label})"
                )
        else:
            logger.warning(
                f"AI_PROVIDER={self.ai_provider} but provider not configured — using heuristics"
            )

        if HAS_TRANSFORMERS and not llm_active:
            try:
                self.qa_pipeline = pipeline(
                    "question-answering",
                    model="distilbert-base-cased-distilled-squad",
                )
                logger.info("Loaded Transformers QA model")
            except Exception as e:
                logger.warning(f"Failed to load Transformers model: {e}")

        self.providers = []
        if self.ai_provider == "openai" and openai_ready:
            self.providers.append(AIProvider("openai", True, 1))
        elif self.ai_provider == "gemini" and gemini_ready:
            self.providers.append(AIProvider("gemini", True, 1))
        elif self.ai_provider == "claude" and claude_ready:
            self.providers.append(AIProvider("claude", True, 1))
        elif self.ai_provider == "cursor" and cursor_ready:
            self.providers.append(AIProvider("cursor", True, 1))
        if self.qa_pipeline is not None:
            self.providers.append(AIProvider("transformers", True, 2))
        self.providers.append(AIProvider("heuristic", True, 3))

        self._llm_lock = asyncio.Lock()
        self._gemini_last_call = 0.0
        self._gemini_min_interval = _gemini_min_interval_for_model(self.gemini_model)
        if self.ai_provider == "gemini":
            logger.info(
                f"Gemini pacing: {self._gemini_min_interval:.0f}s between requests "
                f"(set GEMINI_MIN_INTERVAL_SEC to override)"
            )
        self._cursor_auth_ok: Optional[bool] = None
        self._cursor_auth_warned = False
        if self.ai_provider == "cursor" and cursor_ready:
            self._probe_cursor_auth()
    
    async def answer_question(self, question: str, options: List[str], 
                            question_type: str = "multiple-choice", 
                            context: str = None) -> Dict[str, Any]:
        """
        Answer a question using the best available AI provider
        """
        question_type = _effective_question_type(question, question_type)

        for provider in sorted(self.providers, key=lambda x: x.priority):
            if not provider.enabled:
                continue
            
            try:
                if provider.name == "openai" and self.openai_client:
                    return await self._answer_with_openai(question, options, question_type, context)
                elif provider.name == "gemini" and self.gemini_client:
                    return await self._answer_with_gemini(question, options, question_type, context)
                elif provider.name == "claude" and self.anthropic_client:
                    return await self._answer_with_claude(question, options, question_type, context)
                elif provider.name == "cursor" and self.cursor_agent_bin:
                    if not self._cursor_is_authenticated():
                        result = await self._fallback_after_cursor(
                            question, options, question_type, context
                        )
                        if result is not None:
                            return result
                        continue
                    return await self._answer_with_cursor(
                        question, options, question_type, context
                    )
                elif provider.name == "transformers" and self.qa_pipeline:
                    return await self._answer_with_transformers(question, options, question_type, context)
                elif provider.name == "heuristic":
                    return await self._answer_with_heuristics(question, options, question_type, context)
            except Exception as e:
                logger.error(f"Error with {provider.name}: {e}")
                if provider.name == "gemini" and self.openai_client:
                    try:
                        logger.info("Falling back to OpenAI after Gemini error")
                        return await self._answer_with_openai(
                            question, options, question_type, context
                        )
                    except Exception as fallback_err:
                        logger.error(f"OpenAI fallback failed: {fallback_err}")
                if provider.name == "cursor":
                    result = await self._fallback_after_cursor(
                        question, options, question_type, context
                    )
                    if result is not None:
                        return result
                continue
        
        # Fallback
        return {
            "answer": options[0] if options else "",
            "confidence": 0.1,
            "reasoning": "Fallback answer - no AI providers available",
            "source": "fallback"
        }
    
    def _match_answer_to_option(self, raw_answer: str, options: List[str]) -> Optional[str]:
        """Map model output to one of the provided option strings."""
        if not raw_answer or not options:
            return None

        raw = raw_answer.strip()
        raw_lower = raw.lower()

        for option in options:
            if raw == option or raw_lower == option.lower():
                return option

        for option in options:
            if option.lower() in raw_lower or raw_lower in option.lower():
                return option

        if re.fullmatch(r"[A-Ea-e]", raw):
            idx = ord(raw.upper()) - ord("A")
            if 0 <= idx < len(options):
                return options[idx]

        letter_match = re.match(r"^([A-Ea-e])[).\s:]", raw)
        if letter_match:
            idx = ord(letter_match.group(1).upper()) - ord("A")
            if 0 <= idx < len(options):
                return options[idx]

        number_match = re.match(r"^(\d+)", raw)
        if number_match:
            idx = int(number_match.group(1)) - 1
            if 0 <= idx < len(options):
                return options[idx]

        return None

    def _match_answers_to_options(
        self, raw_answers: List[str], options: List[str]
    ) -> List[str]:
        matched: List[str] = []
        used_indices: set[int] = set()

        for raw in raw_answers:
            option = self._match_answer_to_option(raw, options)
            if option and option not in matched:
                matched.append(option)
                used_indices.add(options.index(option))

        if len(matched) < len(raw_answers) and len(raw_answers) > 1:
            for i, opt in enumerate(options):
                if i in used_indices:
                    continue
                opt_lower = opt.lower()
                for raw in raw_answers:
                    raw_lower = raw.lower()
                    if len(opt_lower) >= 12 and (
                        opt_lower in raw_lower or raw_lower in opt_lower
                        or opt_lower[:40] in raw_lower
                    ):
                        if opt not in matched:
                            matched.append(opt)
                            used_indices.add(i)
                        break

        return matched

    async def _finalize_llm_answer_async(
        self,
        raw_answers: List[str],
        confidence: float,
        reasoning: str,
        options: List[str],
        source: str,
        question: str,
        question_type: str,
        context: str,
    ) -> Dict[str, Any]:
        matched = self._match_answers_to_options(raw_answers, options)

        if _is_multi_select(question_type) and len(matched) <= 1 and raw_answers:
            blob = " ".join(raw_answers).lower()
            for opt in options:
                opt_lower = opt.lower()
                if len(opt_lower) >= 8 and opt_lower in blob and opt not in matched:
                    matched.append(opt)

        if not matched:
            logger.warning(f"{source} answer(s) did not match options: {raw_answers!r}")
            return await self._answer_with_heuristics(question, options, question_type, context)

        return {
            "answer": matched[0] if len(matched) == 1 else "; ".join(matched),
            "answers": matched,
            "confidence": min(max(confidence, 0.0), 1.0),
            "reasoning": reasoning,
            "source": source,
        }

    async def _answer_with_openai(self, question: str, options: List[str], 
                                question_type: str, context: str) -> Dict[str, Any]:
        """Answer using OpenAI GPT-5.2 (gpt-5.2-chat-latest by default)."""
        prompt = self._create_prompt(question, options, question_type, context)

        request_kwargs = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": _llm_system_prompt(question_type)},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if not self.openai_model.startswith("gpt-5"):
            request_kwargs["temperature"] = 0.1

        response = await self.openai_client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content or ""
        raw_answers, confidence, reasoning = _parse_llm_json(
            content, question_type, options
        )
        return await self._finalize_llm_answer_async(
            raw_answers, confidence, reasoning, options,
            f"openai:{self.openai_model}", question, question_type, context,
        )

    async def _gemini_generate(self, full_prompt: str):
        """Rate-limited Gemini call with 429 retries (free tier ~5 RPM)."""
        async with self._llm_lock:
            elapsed = time.monotonic() - self._gemini_last_call
            wait = self._gemini_min_interval - elapsed
            if wait > 0:
                logger.info(f"Gemini rate limit: waiting {wait:.1f}s")
                await asyncio.sleep(wait)

            last_error: Optional[Exception] = None
            for attempt in range(4):
                try:
                    def _generate():
                        config_kwargs: Dict[str, Any] = {
                            "response_mime_type": "application/json",
                            "temperature": 0.2,
                        }
                        if genai_types is not None:
                            config_kwargs["automatic_function_calling"] = (
                                genai_types.AutomaticFunctionCallingConfig(disable=True)
                            )
                        return self.gemini_client.models.generate_content(
                            model=self.gemini_model,
                            contents=full_prompt,
                            config=genai_types.GenerateContentConfig(**config_kwargs),
                        )

                    response = await asyncio.to_thread(_generate)
                    self._gemini_last_call = time.monotonic()
                    return response
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "429" not in err_str and "RESOURCE_EXHAUSTED" not in err_str:
                        raise
                    delay = 10.0
                    retry_match = re.search(
                        r"retry in (\d+(?:\.\d+)?)\s*s", err_str, re.IGNORECASE
                    )
                    if retry_match:
                        delay = float(retry_match.group(1)) + 0.5
                    else:
                        delay = min(30.0, 10.0 * (attempt + 1))
                    logger.warning(
                        f"Gemini 429, retry {attempt + 1}/3 in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
            if last_error:
                raise last_error
            raise RuntimeError("Gemini generate failed with no error")

    async def _answer_with_gemini(self, question: str, options: List[str],
                                  question_type: str, context: str) -> Dict[str, Any]:
        """Answer using Google Gemini."""
        prompt = self._create_prompt(question, options, question_type, context)
        full_prompt = f"{_llm_system_prompt(question_type)}\n\n{prompt}"

        response = await self._gemini_generate(full_prompt)
        content = (response.text or "").strip()
        raw_answers, confidence, reasoning = _parse_llm_json(
            content, question_type, options
        )
        return await self._finalize_llm_answer_async(
            raw_answers, confidence, reasoning, options,
            f"gemini:{self.gemini_model}", question, question_type, context,
        )

    async def _answer_with_claude(self, question: str, options: List[str],
                                  question_type: str, context: str) -> Dict[str, Any]:
        """Answer using Anthropic Claude."""
        prompt = self._create_prompt(question, options, question_type, context)
        response = await self.anthropic_client.messages.create(
            model=self.claude_model,
            max_tokens=1024,
            temperature=0,
            system=_llm_system_prompt(question_type),
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text if response.content else ""
        raw_answers, confidence, reasoning = _parse_llm_json(
            content, question_type, options
        )
        return await self._finalize_llm_answer_async(
            raw_answers, confidence, reasoning, options,
            f"claude:{self.claude_model}", question, question_type, context,
        )

    @staticmethod
    def _is_cursor_auth_error(message: str) -> bool:
        msg = (message or "").lower()
        return (
            "authentication required" in msg
            or "agent login" in msg
            or "cursor_api_key" in msg
            or "not logged in" in msg
        )

    def _warn_cursor_auth_once(self) -> None:
        if self._cursor_auth_warned:
            return
        self._cursor_auth_warned = True
        logger.error(
            "Cursor Agent CLI is not authenticated. Fix one of:\n"
            "  1) Run in terminal: agent login\n"
            "  2) Add to .env: CURSOR_API_KEY=<key from "
            "https://cursor.com/dashboard → Integrations>\n"
            "Then restart: ./start_backend.sh cursor"
        )

    def _probe_cursor_auth(self) -> bool:
        if os.environ.get("CURSOR_API_KEY", "").strip():
            self._cursor_auth_ok = True
            return True
        if not self.cursor_agent_bin:
            self._cursor_auth_ok = False
            return False
        try:
            proc = subprocess.run(
                [self.cursor_agent_bin, "status"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            combined = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
            if "not logged in" in combined or "authentication required" in combined:
                self._cursor_auth_ok = False
                self._warn_cursor_auth_once()
                return False
            if proc.returncode == 0 and (
                "logged in" in combined or "authenticated" in combined
            ):
                self._cursor_auth_ok = True
                return True
        except Exception as e:
            logger.warning(f"Could not probe Cursor CLI auth: {e}")
        self._cursor_auth_ok = False
        self._warn_cursor_auth_once()
        return False

    def _cursor_is_authenticated(self) -> bool:
        if self._cursor_auth_ok is None:
            return self._probe_cursor_auth()
        return self._cursor_auth_ok

    async def _fallback_after_cursor(
        self,
        question: str,
        options: List[str],
        question_type: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Prefer Gemini when Cursor fails (OpenAI often quota-limited)."""
        for fallback_name, fallback_fn in (
            ("gemini", self._answer_with_gemini if self.gemini_client else None),
            ("openai", self._answer_with_openai if self.openai_client else None),
        ):
            if fallback_fn is None:
                continue
            try:
                logger.info(f"Falling back to {fallback_name} after Cursor error")
                return await fallback_fn(question, options, question_type, context)
            except Exception as fallback_err:
                err_str = str(fallback_err)
                if "insufficient_quota" in err_str or "429" in err_str:
                    logger.warning(
                        f"{fallback_name} unavailable (quota/rate limit), trying next"
                    )
                else:
                    logger.error(f"{fallback_name} fallback failed: {fallback_err}")
        return None

    async def _run_cursor_agent_cli(self, full_prompt: str) -> str:
        """Invoke Cursor Agent CLI in headless print mode (uses your Cursor subscription)."""
        if not self.cursor_agent_bin:
            raise RuntimeError("Cursor Agent CLI not installed")

        async with self._llm_lock:
            cmd: List[str] = [
                self.cursor_agent_bin,
                "-p",
                "--output-format",
                "json",
                "--mode",
                "ask",
                "--trust",
                "--sandbox",
                "disabled",
            ]
            api_key = os.environ.get("CURSOR_API_KEY", "").strip()
            if api_key:
                cmd.extend(["--api-key", api_key])
            if self.cursor_agent_model:
                cmd.extend(["--model", self.cursor_agent_model])
            cmd.append(full_prompt)

            logger.info("Calling Cursor Agent CLI...")

            def _run() -> str:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=CURSOR_AGENT_TIMEOUT_SEC,
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                )
                if proc.returncode != 0:
                    err = (proc.stderr or proc.stdout or "").strip()
                    if self._is_cursor_auth_error(err):
                        self._cursor_auth_ok = False
                        self._warn_cursor_auth_once()
                    raise RuntimeError(
                        f"Cursor Agent CLI exited {proc.returncode}: {err[:500]}"
                    )
                return _extract_cursor_cli_text(proc.stdout)

            return await asyncio.to_thread(_run)

    async def _answer_with_cursor(
        self,
        question: str,
        options: List[str],
        question_type: str,
        context: str,
    ) -> Dict[str, Any]:
        """Answer using Cursor Agent CLI (`agent -p`), same JSON parsing as OpenAI/Gemini."""
        prompt = self._create_prompt(question, options, question_type, context)
        full_prompt = f"{_llm_system_prompt(question_type)}\n\n{prompt}"

        content = await self._run_cursor_agent_cli(full_prompt)
        raw_answers, confidence, reasoning = _parse_llm_json(
            content, question_type, options
        )
        source = "cursor-agent"
        if self.cursor_agent_model:
            source = f"cursor-agent:{self.cursor_agent_model}"
        return await self._finalize_llm_answer_async(
            raw_answers,
            confidence,
            reasoning,
            options,
            source,
            question,
            question_type,
            context,
        )
    
    async def _answer_with_transformers(self, question: str, options: List[str], 
                                      question_type: str, context: str) -> Dict[str, Any]:
        """Answer using Hugging Face Transformers"""
        if not self.qa_pipeline:
            raise Exception("Transformers pipeline not available")
        
        best_answer = None
        best_score = 0
        reasoning = []
        
        # Create context from question and options
        full_context = f"Question: {question}\n"
        if context:
            full_context += f"Context: {context}\n"
        full_context += "Options:\n" + "\n".join([f"- {opt}" for opt in options])
        
        # Try each option as a potential answer
        for option in options:
            try:
                # Ask "Which option is correct?" with the context
                result = self.qa_pipeline(
                    question=f"Which option is the correct answer: {option}?",
                    context=full_context
                )
                
                score = result['score']
                reasoning.append(f"{option}: {score:.3f}")
                
                if score > best_score:
                    best_score = score
                    best_answer = option
                    
            except Exception as e:
                logger.warning(f"Error processing option '{option}': {e}")
        
        if not best_answer:
            best_answer = options[0]
            best_score = 0.1
        
        return {
            "answer": best_answer,
            "confidence": min(best_score * 2, 1.0),  # Scale score
            "reasoning": "; ".join(reasoning),
            "source": "transformers"
        }
    
    async def _answer_with_heuristics(self, question: str, options: List[str], 
                                    question_type: str, context: str) -> Dict[str, Any]:
        """Answer using enhanced rule-based heuristics"""
        question_lower = question.lower()
        reasoning = []
        
        # Enhanced knowledge base for common questions
        knowledge_patterns = {
            # Geography and capitals
            'capital.*france': 'paris',
            'capital.*uk|united kingdom': 'london',
            'capital.*germany': 'berlin',
            'capital.*italy': 'rome',
            'capital.*spain': 'madrid',
            'capital.*japan': 'tokyo',
            'capital.*china': 'beijing',
            'capital.*russia': 'moscow',
            
            # Programming and technology
            'machine learning.*language|language.*machine.*learning|programming.*language.*known.*machine': 'python',
            'python.*machine.*learning|python.*known.*for': 'python',
            'html.*stand': 'hypertext markup language',
            'css.*stand': 'cascading style sheets',
            'object.*oriented.*programming': 'classes and objects',
            'javascript.*browser|javascript.*used.*for': 'javascript',
            'sql.*database|sql.*stands': 'structured query language',
            'api.*stands.*for': 'application programming interface',
            'json.*stands.*for': 'javascript object notation',
            'xml.*stands.*for': 'extensible markup language',
            'http.*retrieve|http.*protocol': 'get',
            'version control.*git': 'track changes',
            'tcp.*ip|transmission.*control': 'transmission control protocol',
            'dns.*stands|domain.*name.*system': 'domain name system',
            'url.*stands|uniform.*resource': 'uniform resource locator',
            
            # Computer Science concepts
            'algorithm.*complexity|big.*o.*notation': 'big o',
            'binary.*search.*complexity|time.*complexity.*binary': 'o(log n)',
            'database.*acid': 'atomicity',
            'inheritance.*programming|inherit.*properties.*methods': 'inherit',
            'polymorphism.*programming': 'polymorphism',
            'encapsulation.*programming': 'encapsulation',
            'overfitting.*machine.*learning|model.*performs.*too.*well': 'training data',
            'overfitting.*means|overfitting.*definition': 'performs too well on training',
            'dns.*server|dns.*purpose': 'translate domain names',
            'http.*retrieve|http.*get': 'get',
            
            # Mathematics and formulas
            'area.*circle|circle.*area': 'πr²',
            'circumference.*circle': '2πr',
            'pythagorean.*theorem': 'a² + b² = c²',
            'pi.*value|value.*pi': '3.14159',
            'fibonacci.*sequence': '0, 1, 1, 2, 3, 5, 8',
            
            # Python specific
            'python.*data.*type|valid.*python.*type': 'list|tuple|dict',
            'not.*valid.*python|invalid.*python': 'array',
            
            # Science and math
            'speed.*light': '299,792,458',
            'gravity.*earth': '9.8',
            'photosynthesis.*produces': 'oxygen',
            'mitochondria.*powerhouse': 'cell',
            'dna.*stands.*for': 'deoxyribonucleic acid',
            'rna.*stands.*for': 'ribonucleic acid',
            
            # Business and economics
            'gdp.*stands.*for': 'gross domestic product',
            'ceo.*stands.*for': 'chief executive officer',
            'roi.*stands.*for': 'return on investment'
        }
        
        # Rule 1: Knowledge-based matching with negative question handling
        knowledge_scores = {}
        is_negative_question = any(neg in question_lower for neg in ['not', 'incorrect', 'false', 'except', 'excluding'])
        
        for i, option in enumerate(options):
            option_lower = option.lower()
            score = 0
            
            for pattern, expected in knowledge_patterns.items():
                if re.search(pattern, question_lower):
                    if expected.lower() in option_lower:
                        if is_negative_question:
                            # For negative questions, penalize matches (we want the opposite)
                            score -= 2
                            reasoning.append(f"Negative question: penalizing '{option}' for pattern '{pattern}'")
                        else:
                            score += 3
                            reasoning.append(f"Knowledge match: '{option}' matches pattern for '{pattern}'")
                        break
            
            # Special handling for negative questions about Python data types
            if 'not.*valid.*python' in question_lower or 'invalid.*python' in question_lower:
                if option_lower in ['array', 'pointer', 'char', 'int', 'float']:
                    score += 3  # Increased score for likely invalid types
                    reasoning.append(f"Negative Python type question: '{option}' is likely not a valid Python type")
                elif option_lower in ['list', 'tuple', 'dict', 'dictionary', 'set', 'str', 'string']:
                    score -= 1  # Penalize valid Python types in negative questions
                    reasoning.append(f"Negative Python type question: '{option}' is a valid Python type")
            
            knowledge_scores[i] = score
        
        # Rule 2: Keyword analysis
        keyword_scores = {}
        positive_keywords = [
            'correct', 'true', 'yes', 'always', 'all', 'both', 'every',
            'most', 'best', 'should', 'must', 'important', 'necessary',
            'primarily', 'main', 'key', 'essential', 'fundamental'
        ]
        
        negative_keywords = [
            'incorrect', 'false', 'no', 'never', 'none', 'neither', 'wrong',
            'not', 'least', 'worst', 'avoid', 'don\'t', 'cannot', 'impossible'
        ]
        
        for i, option in enumerate(options):
            option_lower = option.lower()
            score = 0
            
            # Check for positive indicators
            for keyword in positive_keywords:
                if keyword in option_lower:
                    score += 0.5
                    reasoning.append(f"Positive keyword '{keyword}' in option {i+1}")
            
            # Check for negative patterns
            question_negative = any(neg in question_lower for neg in negative_keywords)
            option_negative = any(neg in option_lower for neg in negative_keywords)
            
            if question_negative and option_negative:
                score += 0.3  # Double negative often correct
            elif not question_negative and not option_negative:
                score += 0.2  # Both positive
            
            keyword_scores[i] = score
        
        # Rule 3: Length and complexity heuristic
        length_scores = {}
        max_length = max(len(opt) for opt in options) if options else 1
        for i, option in enumerate(options):
            # Moderate length often better than too short or too long
            length_ratio = len(option) / max_length
            if 0.3 <= length_ratio <= 0.8:
                length_scores[i] = 0.5
            elif length_ratio > 0.8:
                length_scores[i] = 0.3  # Longest option bonus
            else:
                length_scores[i] = 0.1
        
        # Rule 4: Academic and technical patterns
        academic_scores = {}
        academic_patterns = [
            'according to', 'research shows', 'studies indicate',
            'analysis reveals', 'theory suggests', 'methodology',
            'framework', 'paradigm', 'concept', 'principle'
        ]
        
        technical_patterns = [
            'algorithm', 'protocol', 'specification', 'standard',
            'implementation', 'architecture', 'structure', 'design'
        ]
        
        for i, option in enumerate(options):
            option_lower = option.lower()
            score = 0
            
            for pattern in academic_patterns:
                if pattern in option_lower:
                    score += 0.3
            
            for pattern in technical_patterns:
                if pattern in option_lower:
                    score += 0.2
            
            # Look for explanatory words
            explanatory_words = ['because', 'therefore', 'however', 'although', 'since', 'while']
            for word in explanatory_words:
                if word in option_lower:
                    score += 0.1
            
            academic_scores[i] = score
        
        # Rule 5: Specific question type analysis
        question_type_scores = {}
        for i, option in enumerate(options):
            option_lower = option.lower()
            score = 0
            
            # True/False questions
            if any(word in question_lower for word in ['true', 'false', 'correct', 'incorrect']):
                if 'true' in option_lower or 'correct' in option_lower:
                    score += 0.4
            
            # Definition questions
            if any(word in question_lower for word in ['define', 'definition', 'means', 'refers to']):
                if len(option) > 30:  # Definitions tend to be longer
                    score += 0.3
            
            # Best practice questions
            if any(word in question_lower for word in ['best', 'recommended', 'should', 'practice']):
                if any(word in option_lower for word in ['best', 'recommended', 'should', 'proper']):
                    score += 0.5
            
            question_type_scores[i] = score
        
        # Combine all scores with weights
        final_scores = {}
        for i in range(len(options)):
            final_scores[i] = (
                knowledge_scores.get(i, 0) * 0.4 +      # Highest weight for knowledge
                keyword_scores.get(i, 0) * 0.25 +       # Keyword analysis
                length_scores.get(i, 0) * 0.15 +        # Length heuristic
                academic_scores.get(i, 0) * 0.1 +       # Academic patterns
                question_type_scores.get(i, 0) * 0.1    # Question type specific
            )
        
        # Find best option
        if final_scores:
            best_idx = max(final_scores.keys(), key=lambda k: final_scores[k])
            best_answer = options[best_idx]
            max_score = final_scores[best_idx]
            confidence = min(max_score / 2, 0.95)  # Scale confidence
            
            # Boost confidence if we had a knowledge match
            if knowledge_scores.get(best_idx, 0) > 0:
                confidence = min(confidence + 0.3, 0.95)
                
        else:
            best_answer = options[0] if options else ""
            confidence = 0.1
        
        # Add scoring breakdown to reasoning
        reasoning.append(f"Scores: {[f'{i+1}:{final_scores.get(i, 0):.2f}' for i in range(len(options))]}")
        
        result = {
            "answer": best_answer,
            "confidence": confidence,
            "reasoning": "; ".join(reasoning),
            "source": "enhanced_heuristic",
        }
        if _is_multi_select(question_type):
            n = _expected_answer_count(question) or 3
            ranked = sorted(
                final_scores.keys(), key=lambda k: final_scores[k], reverse=True
            )
            picked = []
            for idx in ranked:
                if final_scores[idx] > 0.02:
                    picked.append(options[idx])
                if len(picked) >= n:
                    break
            if not picked:
                picked = [best_answer]
            result["answers"] = picked
            result["answer"] = "; ".join(picked)
        return result
    
    def _create_prompt(self, question: str, options: List[str],
                      question_type: str, context: str) -> str:
        """Create a prompt for AI models"""
        prompt = f"Question: {question}\n\n"
        if context:
            prompt += f"Context: {context}\n\n"
        prompt += "Options:\n"
        for i, option in enumerate(options):
            prompt += f"{chr(65 + i)}. {option}\n"

        if _is_multi_select(question_type):
            n = _expected_answer_count(question)
            prompt += (
                f"\nSelect exactly {n} correct options." if n
                else "\nSelect all correct options (may be more than one)."
            )
        else:
            prompt += "\nSelect the single correct option."

        return prompt

# Global AI instance
coursera_ai = CourseraAI()

@app.get("/")
async def root():
    return {"message": "Coursera Automation AI Backend", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai_provider": coursera_ai.ai_provider,
        "openai_model": coursera_ai.openai_model if coursera_ai.openai_client else None,
        "openai_configured": coursera_ai.openai_client is not None,
        "gemini_model": coursera_ai.gemini_model if coursera_ai.gemini_client else None,
        "gemini_configured": coursera_ai.gemini_client is not None,
        "claude_model": coursera_ai.claude_model if coursera_ai.anthropic_client else None,
        "claude_configured": coursera_ai.anthropic_client is not None,
        "cursor_agent_bin": coursera_ai.cursor_agent_bin,
        "cursor_agent_model": coursera_ai.cursor_agent_model or None,
        "cursor_configured": coursera_ai.cursor_agent_bin is not None,
        "cursor_authenticated": coursera_ai._cursor_is_authenticated()
        if coursera_ai.cursor_agent_bin
        else False,
        "providers": [
            {"name": p.name, "enabled": p.enabled, "priority": p.priority} 
            for p in coursera_ai.providers
        ]
    }

@app.post("/answer", response_model=AnswerResponse)
async def answer_question(request: QuestionRequest):
    """Answer a Coursera question"""
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        if not request.options:
            raise HTTPException(status_code=400, detail="Options cannot be empty")
        
        logger.info(f"Answering question: {request.question[:100]}...")
        
        result = await coursera_ai.answer_question(
            question=request.question,
            options=request.options,
            question_type=request.type,
            context=request.context
        )
        
        answers = result.get("answers") or []
        logger.info(
            f"Answer: {result['answer'][:120]}{'...' if len(result['answer']) > 120 else ''} "
            f"(n={len(answers)}, confidence: {result['confidence']:.3f}, source: {result['source']})"
        )
        
        return AnswerResponse(
            answer=result["answer"],
            answers=result.get("answers"),
            confidence=result["confidence"],
            reasoning=result.get("reasoning"),
            source=result["source"],
        )
        
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch-answer")
async def batch_answer_questions(requests: List[QuestionRequest]):
    """Answer multiple questions in batch"""
    results = []
    
    for request in requests:
        try:
            result = await coursera_ai.answer_question(
                question=request.question,
                options=request.options,
                question_type=request.type,
                context=request.context
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error in batch question: {e}")
            results.append({
                "answer": request.options[0] if request.options else "",
                "confidence": 0.1,
                "reasoning": f"Error: {str(e)}",
                "source": "error"
            })
    
    return {"results": results}

if __name__ == "__main__":
    logger.info("Starting Coursera Automation AI Backend...")
    logger.info(f"AI_PROVIDER: {coursera_ai.ai_provider}")
    logger.info(f"OpenAI library: {HAS_OPENAI}, configured: {coursera_ai.openai_client is not None}")
    logger.info(f"Gemini library: {HAS_GEMINI}, configured: {coursera_ai.gemini_client is not None}")
    logger.info(f"Anthropic library: {HAS_ANTHROPIC}, configured: {coursera_ai.anthropic_client is not None}")
    if coursera_ai.openai_client:
        logger.info(f"OpenAI model: {coursera_ai.openai_model}")
    if coursera_ai.gemini_client:
        logger.info(f"Gemini model: {coursera_ai.gemini_model}")
    if coursera_ai.anthropic_client:
        logger.info(f"Claude model: {coursera_ai.claude_model}")
    if coursera_ai.cursor_agent_bin:
        logger.info(f"Cursor Agent CLI: {coursera_ai.cursor_agent_bin}")
        if coursera_ai.cursor_agent_model:
            logger.info(f"Cursor Agent model: {coursera_ai.cursor_agent_model}")
    logger.info(f"Transformers available: {HAS_TRANSFORMERS}")
    logger.info(f"Requests available: {HAS_REQUESTS}")
    
    uvicorn.run(
        "ai_backend:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
