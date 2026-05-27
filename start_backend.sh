#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Allow: ./start_backend.sh openai | gemini | cursor
if [ -n "$1" ]; then
  export AI_PROVIDER="$1"
fi

cursor_cli_hint() {
  if command -v agent >/dev/null 2>&1; then
    echo "agent (found)"
  elif command -v cursor-agent >/dev/null 2>&1; then
    echo "cursor-agent (found)"
  else
    echo "not installed — curl https://cursor.com/install -fsS | bash"
  fi
}

select_provider() {
  echo ""
  echo "Select AI provider:"
  echo "  1) OpenAI       (${OPENAI_MODEL:-gpt-5.2-chat-latest})"
  echo "  2) Gemini       (${GEMINI_MODEL:-gemini-2.0-flash})"
  echo "  3) Claude       (${CLAUDE_MODEL:-claude-haiku-4-5})"
  echo "  4) Cursor Agent ($(cursor_cli_hint))"
  echo ""
  read -r -p "Choice [1]: " choice
  case "$choice" in
    2|gemini|Gemini|GEMINI) export AI_PROVIDER=gemini ;;
    3|claude|Claude|CLAUDE|anthropic|Anthropic) export AI_PROVIDER=claude ;;
    4|cursor|Cursor|CURSOR|agent|Agent|AGENT) export AI_PROVIDER=cursor ;;
    *) export AI_PROVIDER=openai ;;
  esac
}

if [ -z "$AI_PROVIDER" ]; then
  select_provider
fi

AI_PROVIDER=$(echo "$AI_PROVIDER" | tr '[:upper:]' '[:lower:]')
export AI_PROVIDER

echo ""
echo "🤖 Starting Coursera AI Backend on http://localhost:8000"
echo "   Provider: $AI_PROVIDER"

if [ "$AI_PROVIDER" = "openai" ]; then
  if [ -n "$OPENAI_API_KEY" ]; then
    echo "   Model: ${OPENAI_MODEL:-gpt-5.2-chat-latest}"
  else
    echo "   ⚠️  OPENAI_API_KEY not set — add it to .env"
  fi
elif [ "$AI_PROVIDER" = "gemini" ]; then
  if [ -n "$GEMINI_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
    echo "   Model: ${GEMINI_MODEL:-gemini-2.0-flash}"
  else
    echo "   ⚠️  GEMINI_API_KEY or GOOGLE_API_KEY not set — add it to .env"
  fi
elif [ "$AI_PROVIDER" = "claude" ]; then
  if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "   Model: ${CLAUDE_MODEL:-claude-haiku-4-5}"
  else
    echo "   ⚠️  ANTHROPIC_API_KEY not set — add it to .env"
  fi
elif [ "$AI_PROVIDER" = "cursor" ]; then
  AGENT_BIN="${CURSOR_AGENT_BIN:-$(command -v agent 2>/dev/null || command -v cursor-agent 2>/dev/null)}"
  if [ -n "$AGENT_BIN" ]; then
    echo "   CLI: $AGENT_BIN"
    if [ -n "$CURSOR_AGENT_MODEL" ]; then
      echo "   Model: $CURSOR_AGENT_MODEL"
    fi
    if [ -n "$CURSOR_API_KEY" ]; then
      echo "   Auth: CURSOR_API_KEY set in .env"
    elif "$AGENT_BIN" status 2>&1 | grep -qi "logged in"; then
      echo "   Auth: logged in (agent login)"
    else
      echo ""
      echo "   ⚠️  Cursor Agent CLI is NOT authenticated."
      echo "      Option A:  agent login"
      echo "      Option B:  add CURSOR_API_KEY to .env"
      echo "               (Cursor Dashboard → Integrations → User API keys)"
      echo ""
      echo "   Until then, quiz answers will fall back to Gemini (if configured)."
      echo ""
    fi
  else
    echo "   ⚠️  Cursor Agent CLI not found — install from https://cursor.com/docs/cli/overview"
  fi
else
  echo "   ⚠️  Unknown AI_PROVIDER=$AI_PROVIDER — use openai, gemini, or cursor"
  export AI_PROVIDER=openai
fi

# Persist choice for next run (merge into .env)
if [ -f .env ]; then
  if grep -q '^AI_PROVIDER=' .env 2>/dev/null; then
    if [ "$(uname)" = "Darwin" ]; then
      sed -i '' "s/^AI_PROVIDER=.*/AI_PROVIDER=$AI_PROVIDER/" .env
    else
      sed -i "s/^AI_PROVIDER=.*/AI_PROVIDER=$AI_PROVIDER/" .env
    fi
  else
    echo "AI_PROVIDER=$AI_PROVIDER" >> .env
  fi
elif [ ! -f .env ]; then
  echo "AI_PROVIDER=$AI_PROVIDER" > .env
fi

echo ""
python ai_backend.py
