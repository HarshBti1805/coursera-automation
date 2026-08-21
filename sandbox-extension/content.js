// Coursera Sandbox Solver — content script (sandbox / lab code only)
(function sandboxSolverContentScript() {
  'use strict';

  if (globalThis.__COURSERA_SANDBOX_SOLVER__) {
    console.log('[Sandbox Solver] Already loaded, skipping');
    return;
  }

  const state = {
    enabled: false,
    autoRun: true,
    observer: null,
    scanInterval: null,
    scanDebounce: null,
    scanInFlight: false
  };
  globalThis.__COURSERA_SANDBOX_SOLVER__ = state;

  console.log('[Sandbox Solver] Loaded');

  // Register the listener synchronously so the popup can always reach this
  // tab immediately, even before storage/settings have finished loading.
  chrome.runtime.onMessage.addListener(handleMessage);

  initialize().catch(function (err) {
    console.error('[Sandbox Solver] Init failed:', err);
  });

  async function initialize() {
    const result = await chrome.storage.sync.get([
      'sandboxAutoSolveEnabled',
      'sandboxAutoRun'
    ]);
    state.enabled = !!result.sandboxAutoSolveEnabled;
    state.autoRun = result.sandboxAutoRun !== false;

    injectPageScript();

    if (state.enabled) {
      startMonitoring();
    }
  }

  function injectPageScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('injected.js');
    script.onload = function () {
      this.remove();
    };
    (document.head || document.documentElement).appendChild(script);
  }

  function handleMessage(request, _sender, sendResponse) {
    if (request.action === 'ping') {
      sendResponse({ ok: true, enabled: state.enabled });
      return true;
    }
    if (request.action === 'toggleSandboxSolve') {
      state.enabled = !!request.enabled;
      if (state.enabled) startMonitoring();
      else stopMonitoring();
      sendResponse({ success: true });
      return true;
    }
    if (request.action === 'setSandboxAutoRun') {
      state.autoRun = !!request.enabled;
      sendResponse({ success: true });
      return true;
    }
    if (request.action === 'solveSandboxesNow') {
      solveAllSandboxes()
        .then(function (stats) {
          sendResponse({ ok: true, found: stats.found, solved: stats.solved, reasons: stats.reasons });
        })
        .catch(function (err) {
          sendResponse({ ok: false, error: String(err && err.message ? err.message : err) });
        });
      return true;
    }
    if (request.action === 'generateCopySolutions') {
      generateCopySolutions()
        .then(function (result) {
          sendResponse(result);
        })
        .catch(function (err) {
          sendResponse({ ok: false, error: String(err && err.message ? err.message : err) });
        });
      return true;
    }
    return false;
  }

  function startMonitoring() {
    stopMonitoring();
    console.log('[Sandbox Solver] Monitoring started');

    state.observer = new MutationObserver(function () {
      scheduleScan();
    });
    state.observer.observe(document.body, { childList: true, subtree: true });

    runScan();
    state.scanInterval = setInterval(runScan, 2500);
  }

  function stopMonitoring() {
    if (state.observer) {
      state.observer.disconnect();
      state.observer = null;
    }
    if (state.scanInterval) {
      clearInterval(state.scanInterval);
      state.scanInterval = null;
    }
    if (state.scanDebounce) {
      clearTimeout(state.scanDebounce);
      state.scanDebounce = null;
    }
    state.scanInFlight = false;
  }

  function scheduleScan() {
    if (state.scanDebounce) clearTimeout(state.scanDebounce);
    state.scanDebounce = setTimeout(runScan, 450);
  }

  function runScan() {
    if (!state.enabled || state.scanInFlight) return;
    solveAllSandboxes().catch(function (err) {
      console.error('[Sandbox Solver] Scan error:', err);
    });
  }

  async function solveAllSandboxes() {
    if (state.scanInFlight) {
      return { found: 0, solved: 0, reasons: {} };
    }
    state.scanInFlight = true;
    try {
      const blocks = findSandboxBlocks();
      if (blocks.length) {
        console.log('[Sandbox Solver] Found ' + blocks.length + ' sandbox block(s)');
      }
      let solved = 0;
      const reasons = {};
      function tally(reason) {
        reasons[reason] = (reasons[reason] || 0) + 1;
      }

      const results = await Promise.allSettled(
        blocks.map(function (block) {
          return processSandbox(block).then(function (result) {
            if (result.solved) solved += 1;
            else tally(result.reason);
          });
        })
      );
      results.forEach(function (r) {
        if (r.status === 'rejected') {
          console.error('[Sandbox Solver] Block error:', r.reason);
          tally('exception');
        }
      });
      if (blocks.length) {
        console.log('[Sandbox Solver] Solved ' + solved + '/' + blocks.length, reasons);
      }
      return { found: blocks.length, solved: solved, reasons: reasons };
    } finally {
      state.scanInFlight = false;
    }
  }

  // ── Detection ────────────────────────────────────────────────────────────

  const EDITOR_SEL =
    '.monaco-editor, .CodeMirror, .ace_editor, .cm-editor, [class*="ace_editor"]';

  function findSandboxBlocks() {
    const seen = new Set();
    const results = [];

    function addBlock(node) {
      if (!node || seen.has(node)) return;
      if (node.closest && node.closest('[data-sandbox-solver-done="true"]')) return;
      // Skip MCQ blocks that only embed code as scenario display
      if (hasChoiceInputs(node)) return;
      seen.add(node);
      results.push(node);
    }

    // Explicit Coursera code / lab parts. These attribute-substring selectors
    // are speculative (Coursera doesn't document their internal testids), so
    // require an ACTUAL editor/textarea/contenteditable match — never just a
    // nearby button — or a "Lab"/"sandbox" substring match on an unrelated
    // element (e.g. "FormPartsQuestion-Label") would falsely flag every
    // question on the page as a sandbox.
    const knownSelectors = [
      '[data-testid="part-Submission_CodeQuestion"]',
      '[data-testid*="CodeQuestion"]',
      '[data-testid*="CodeBlock"]',
      '[data-testid*="sandbox"]',
      '[class*="Sandbox"]',
      '[class*="code-editor"]',
      '[class*="CodeEditor"]'
    ];
    knownSelectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (
          el.querySelector(EDITOR_SEL) ||
          el.querySelector('textarea') ||
          el.querySelector('[contenteditable="true"]')
        ) {
          addBlock(el);
        }
      });
    });

    // Any editor with a nearby Run / Submit / Evaluate control
    document.querySelectorAll(EDITOR_SEL).forEach(function (editor) {
      if (hasChoiceInputs(editor.parentElement || editor)) return;
      const block = narrowIfTooBroad(climbToSandboxRoot(editor));
      if (block) addBlock(block);
    });

    // Run buttons that sit next to a code area (matches the assessment UI screenshot)
    document.querySelectorAll('button, a, [role="button"]').forEach(function (btn) {
      const label = (btn.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
      if (!/^(run|submit|evaluate|check|execute|test)$/i.test(label) && label !== 'run') {
        return;
      }
      const root = narrowIfTooBroad(climbToSandboxRoot(btn));
      if (!root) return;
      if (
        root.querySelector(EDITOR_SEL) ||
        root.querySelector('textarea') ||
        root.querySelector('[contenteditable="true"]')
      ) {
        addBlock(root);
      }
    });

    // Prefer leaf blocks (don't process a parent and its child twice)
    const leaves = results.filter(function (block) {
      return !results.some(function (other) {
        return other !== block && block.contains(other);
      });
    });

    leaves.sort(function (a, b) {
      return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
    });

    return leaves;
  }

  function hasChoiceInputs(node) {
    if (!node || !node.querySelector) return false;
    return !!node.querySelector(
      'input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"]'
    );
  }

  // Climbs from `el` toward the document root and returns the FIRST ancestor
  // that already has enough context (an editor plus a run control or prompt
  // text). Critically, this STOPS as soon as that ancestor is found — it
  // must not keep climbing and overwriting the match with broader and
  // broader ancestors, or a page with many separate exercises ends up
  // merging several of them into one oversized, unusable block.
  function climbToSandboxRoot(el) {
    let node = el && el.nodeType === 1 ? el : el && el.parentElement;
    for (let i = 0; i < 12 && node; i++) {
      if (hasChoiceInputs(node) && !node.querySelector(EDITOR_SEL)) {
        break;
      }
      const hasEditor =
        node.matches(EDITOR_SEL) ||
        !!node.querySelector(EDITOR_SEL) ||
        !!node.querySelector('textarea') ||
        !!node.querySelector('[contenteditable="true"]');

      if (hasEditor) {
        const isNamedContainer =
          node.matches(
            'fieldset, [role="group"], [data-testid^="part-"], .rc-FormPartsQuestion, form'
          ) ||
          /sandbox|code|lab|editor/i.test(node.className || '') ||
          /sandbox|code|lab|editor/i.test(node.getAttribute('data-testid') || '');
        const hasRun = !!findRunButton(node);
        const hasPrompt =
          !!node.querySelector(
            '[data-testid="legend"], [data-testid*="prompt"], .rc-CML, h1, h2, h3, h4'
          ) || (node.innerText || '').trim().length > 40;

        if (isNamedContainer || hasRun || hasPrompt) {
          return node;
        }
      }
      node = node.parentElement;
    }
    return null;
  }

  // If the resolved block accidentally spans multiple exercises (more than
  // one editor or more than one run control), try each direct child for a
  // tighter, self-contained match instead of solving the wrong code with
  // the wrong prompt.
  function narrowIfTooBroad(node) {
    if (!node) return node;
    const editorCount = node.querySelectorAll(EDITOR_SEL).length || (node.matches(EDITOR_SEL) ? 1 : 0);
    const runCount = countRunButtons(node);
    if (editorCount <= 1 && runCount <= 1) return node;

    const children = Array.prototype.slice.call(node.children || []);
    for (let i = 0; i < children.length; i++) {
      const child = children[i];
      if (!child.querySelectorAll) continue;
      const childHasEditor = child.matches(EDITOR_SEL) || !!child.querySelector(EDITOR_SEL);
      if (!childHasEditor) continue;
      const ed = child.querySelectorAll(EDITOR_SEL).length || (child.matches(EDITOR_SEL) ? 1 : 0);
      const rb = countRunButtons(child);
      if (ed <= 1 && rb <= 1) return child;
    }
    console.warn(
      '[Sandbox Solver] Block spans ' + editorCount + ' editor(s)/' + runCount +
        ' run control(s) and could not be narrowed — using it as-is'
    );
    return node;
  }

  function countRunButtons(root) {
    if (!root || !root.querySelectorAll) return 0;
    const candidates = root.querySelectorAll('button, a, [role="button"], input[type="button"]');
    let count = 0;
    for (let i = 0; i < candidates.length; i++) {
      if (isRunLikeLabel(candidates[i].textContent || candidates[i].value)) count++;
    }
    return count;
  }

  function isRunLikeLabel(text) {
    const t = (text || '').replace(/\s+/g, ' ').trim().toLowerCase();
    return (
      t === 'run' ||
      t === 'submit' ||
      t === 'evaluate' ||
      t === 'check' ||
      t === 'execute' ||
      t === 'test code' ||
      t === 'run code'
    );
  }

  function findRunButton(root) {
    if (!root || !root.querySelectorAll) return null;
    const candidates = root.querySelectorAll('button, a, [role="button"], input[type="button"]');
    for (let i = 0; i < candidates.length; i++) {
      if (isRunLikeLabel(candidates[i].textContent || candidates[i].value)) {
        return candidates[i];
      }
    }
    return null;
  }

  // ── Extract + solve ──────────────────────────────────────────────────────

  async function processSandbox(block) {
    if (block.dataset.sandboxSolverDone === 'true') return { solved: false, reason: 'already-done' };
    if (block.dataset.sandboxSolverPending === 'true') return { solved: false, reason: 'already-pending' };

    const editorInfo = detectEditor(block);
    if (!editorInfo) {
      console.log('[Sandbox Solver] Skipping block — no code editor found inside it', block);
      return { solved: false, reason: 'no-editor-detected' };
    }

    const data = extractSandboxData(block, editorInfo);
    if (!data || !data.prompt) {
      console.log('[Sandbox Solver] Skipping block — could not extract a question prompt', block);
      return { solved: false, reason: 'no-prompt-text' };
    }

    block.dataset.sandboxSolverPending = 'true';
    try {
      console.log(
        '[Sandbox Solver] Solving (' +
          data.editorType +
          '): ' +
          data.prompt.slice(0, 90) +
          (data.prompt.length > 90 ? '…' : '')
      );

      const answer = await getAICode(data);
      if (!answer) {
        delete block.dataset.sandboxSolverPending;
        return { solved: false, reason: 'ai-backend-failed' };
      }

      const filled = await fillEditor(data, answer);
      if (!filled) {
        console.warn('[Sandbox Solver] Failed to fill editor', data.editorType, block);
        delete block.dataset.sandboxSolverPending;
        return { solved: false, reason: 'fill-editor-failed' };
      }

      block.dataset.sandboxSolverDone = 'true';
      delete block.dataset.sandboxSolverPending;

      if (state.autoRun) {
        const runBtn = findRunButton(block);
        if (runBtn) {
          setTimeout(function () {
            runBtn.click();
            console.log('[Sandbox Solver] Clicked Run');
          }, 400);
        }
      }

      console.log('[Sandbox Solver] Filled solution (' + answer.split('\n').length + ' lines)');
      return { solved: true, reason: null };
    } catch (err) {
      console.error('[Sandbox Solver] Error:', err);
      delete block.dataset.sandboxSolverPending;
      return { solved: false, reason: 'exception' };
    }
  }

  function cleanCloneText(el, extraRemoveSel) {
    if (!el) return '';
    const clone = el.cloneNode(true);
    const removeSel =
      EDITOR_SEL +
      ', script, style, button, [role="button"], ' +
      (extraRemoveSel || '');
    clone.querySelectorAll(removeSel).forEach(function (n) {
      n.remove();
    });
    return (clone.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function readVisibleEditorText(editorEl, editorType) {
    if (!editorEl) return '';

    if (editorType === 'monaco' || editorEl.classList.contains('monaco-editor')) {
      const lines = editorEl.querySelectorAll('.view-lines .view-line');
      if (lines.length) {
        return Array.from(lines)
          .map(function (l) {
            return l.textContent;
          })
          .join('\n')
          .replace(/\u00a0/g, ' ');
      }
    }

    if (editorType === 'codemirror' || editorEl.classList.contains('CodeMirror')) {
      const code = editorEl.querySelector('.CodeMirror-code, .cm-content');
      if (code) return (code.innerText || code.textContent || '').replace(/\u00a0/g, ' ');
    }

    if (editorType === 'ace' || editorEl.classList.contains('ace_editor')) {
      const lines = editorEl.querySelectorAll('.ace_line');
      if (lines.length) {
        return Array.from(lines)
          .map(function (l) {
            return l.textContent;
          })
          .join('\n');
      }
    }

    const ta = editorEl.matches('textarea')
      ? editorEl
      : editorEl.querySelector('textarea');
    if (ta && ta.value) return ta.value;

    return (editorEl.innerText || '').trim();
  }

  function detectEditor(block) {
    const monaco = block.querySelector('.monaco-editor');
    if (monaco) return { el: monaco, type: 'monaco' };

    const cm = block.querySelector('.CodeMirror, .cm-editor');
    if (cm) return { el: cm, type: 'codemirror' };

    const ace = block.querySelector('.ace_editor, [class*="ace_editor"]');
    if (ace) return { el: ace, type: 'ace' };

    const ta =
      block.querySelector('textarea.inputarea') ||
      block.querySelector('textarea[class*="code"]') ||
      block.querySelector('textarea');
    if (ta) return { el: ta, type: 'textarea' };

    const editable = block.querySelector('[contenteditable="true"]');
    if (editable) return { el: editable, type: 'contenteditable' };

    return null;
  }

  function extractSandboxData(block, editorInfo) {
    editorInfo = editorInfo || detectEditor(block);
    if (!editorInfo) return null;

    // Mark editor for page-context fill
    if (!editorInfo.el.dataset.sandboxEditorId) {
      editorInfo.el.dataset.sandboxEditorId =
        'sb-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    }

    let prompt = '';
    const legend = block.querySelector('[data-testid="legend"]');
    if (legend) {
      prompt = cleanCloneText(legend);
    }
    if (!prompt || prompt.length < 12) {
      const promptEls = block.querySelectorAll(
        '[data-testid*="prompt"], .rc-CML, .rc-FormPartsQuestion__contentCell, h1, h2, h3, h4, ol, ul, p'
      );
      for (let i = 0; i < promptEls.length; i++) {
        const t = cleanCloneText(promptEls[i]);
        if (t.length > 15 && !/^(run|reset)$/i.test(t)) {
          prompt = t;
          break;
        }
      }
    }
    if (!prompt || prompt.length < 12) {
      prompt = cleanCloneText(block, 'textarea, [contenteditable="true"]');
    }

    // Strip trailing Run/Reset noise and point counts
    prompt = prompt
      .replace(/\b\d+\s*points?\b/gi, '')
      .replace(/\b(Run|Reset|Submit|Evaluate)\b/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 2500);

    if (!prompt || prompt.length < 8) return null;

    const codeTemplate = readVisibleEditorText(editorInfo.el, editorInfo.type);

    return {
      prompt: prompt,
      codeTemplate: (codeTemplate || '').trim(),
      editorId: editorInfo.el.dataset.sandboxEditorId,
      editorType: editorInfo.type,
      block: block
    };
  }

  async function getAICode(data) {
    try {
      const response = await fetch('http://localhost:8000/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: data.prompt,
          options: [],
          type: 'sandbox',
          context: data.codeTemplate || null
        })
      });

      if (!response.ok) {
        let detail = '';
        try {
          const errBody = await response.json();
          detail = errBody && (errBody.detail || errBody.message) || '';
        } catch (_e) {
          /* body wasn't JSON */
        }
        console.warn('[Sandbox Solver] Backend HTTP', response.status, detail || '(no detail)');
        return null;
      }

      const result = await response.json();
      let code = (result.answer || '').trim();
      if (!code && Array.isArray(result.answers) && result.answers[0]) {
        code = String(result.answers[0]).trim();
      }
      code = stripCodeFences(code);
      if (!code) return null;

      console.log(
        '[Sandbox Solver] AI code ready (' +
          Math.round((result.confidence || 0) * 100) +
          '% from ' +
          (result.source || 'ai') +
          ')'
      );
      return code;
    } catch (err) {
      console.warn('[Sandbox Solver] Backend offline:', err.message);
      return null;
    }
  }

  function stripCodeFences(text) {
    let t = (text || '').trim();
    if (!t.startsWith('```')) return t;
    t = t.replace(/^```[a-zA-Z0-9_+-]*\s*\n?/, '');
    t = t.replace(/\n?```\s*$/, '');
    return t.trim();
  }

  function fillEditor(data, code) {
    return new Promise(function (resolve) {
      const requestId = 'fill-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);

      function onResult(event) {
        if (!event.data || event.data.type !== 'COURSERA_SANDBOX_RESULT') return;
        if (event.data.requestId !== requestId) return;
        window.removeEventListener('message', onResult);
        resolve(!!event.data.ok);
      }

      window.addEventListener('message', onResult);
      window.postMessage(
        {
          type: 'COURSERA_SANDBOX',
          action: 'fillCodeEditor',
          requestId: requestId,
          code: code,
          editorId: data.editorId,
          editorType: data.editorType
        },
        '*'
      );

      // Fallback timeout — assume success if injected script doesn't reply
      // (older path) but prefer explicit ack.
      setTimeout(function () {
        window.removeEventListener('message', onResult);
        resolve(true);
      }, 2500);
    });
  }

  // ── Copy-paste fallback ──────────────────────────────────────────────────
  // When the on-page editor can't be identified/filled automatically (custom
  // widgets, iframes, unknown DOM), this generates a solution per detected
  // coding question and shows it in an on-page panel with a Copy button, so
  // the user can paste it in manually. Detection here is deliberately more
  // lenient than the autofill path — it does NOT require recognizing the
  // editor technology, only a "Run" control (this widget's own fingerprint,
  // per the assignment UI) attached to a reasonably long block of text.

  let panelSolutions = [];

  async function generateCopySolutions() {
    const blocks = findLenientCodeBlocks();
    if (!blocks.length) {
      return { ok: false, count: 0, total: 0, error: 'No coding questions detected on this page' };
    }

    panelSolutions = blocks.map(function () {
      return null;
    });
    renderPanelSkeleton(blocks.length);

    let count = 0;
    await Promise.allSettled(
      blocks.map(function (block, idx) {
        return (async function () {
          const prompt = extractPromptLenient(block);
          if (!prompt || prompt.length < 8) {
            updatePanelEntry(idx, { error: 'Could not read the question text for this block' });
            return;
          }
          try {
            const code = await getAICode({ prompt: prompt, codeTemplate: '' });
            if (!code) {
              updatePanelEntry(idx, { prompt: prompt, error: 'AI backend did not return a solution (is it running?)' });
              return;
            }
            panelSolutions[idx] = { prompt: prompt, code: code };
            updatePanelEntry(idx, { prompt: prompt, code: code });
            count += 1;
          } catch (err) {
            updatePanelEntry(idx, {
              prompt: prompt,
              error: String(err && err.message ? err.message : err)
            });
          }
        })();
      })
    );

    return { ok: true, count: count, total: blocks.length };
  }

  function findLenientCodeBlocks() {
    const seen = new Set();
    const results = [];

    document.querySelectorAll('button, a, [role="button"], input[type="button"]').forEach(function (btn) {
      if (!isRunLikeLabel(btn.textContent || btn.value)) return;
      const root = climbToLenientRoot(btn);
      if (!root || seen.has(root)) return;
      seen.add(root);
      results.push(root);
    });

    const leaves = results.filter(function (block) {
      return !results.some(function (other) {
        return other !== block && block.contains(other);
      });
    });

    leaves.sort(function (a, b) {
      return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
    });

    return leaves;
  }

  function climbToLenientRoot(el) {
    let node = el && el.nodeType === 1 ? el : el && el.parentElement;
    let fallback = null;
    for (let i = 0; i < 12 && node; i++) {
      if (hasChoiceInputs(node) && !node.querySelector(EDITOR_SEL) && !node.querySelector('textarea')) {
        break; // this scope looks like an MCQ, not a standalone code exercise
      }
      const text = (node.innerText || '').trim();
      const hasReset = !!findButtonByLabel(node, 'reset');
      // "Run" + "Reset" together is this widget's specific fingerprint
      // (visible in the assignment screenshot) — trust it immediately.
      if (hasReset && text.length > 20) {
        return node;
      }
      if (!fallback && text.length > 40) {
        fallback = node;
      }
      node = node.parentElement;
    }
    return fallback;
  }

  function findButtonByLabel(root, label) {
    if (!root || !root.querySelectorAll) return null;
    const candidates = root.querySelectorAll('button, a, [role="button"], input[type="button"]');
    for (let i = 0; i < candidates.length; i++) {
      const t = (candidates[i].textContent || candidates[i].value || '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
      if (t === label) return candidates[i];
    }
    return null;
  }

  function extractPromptLenient(block) {
    const clone = block.cloneNode(true);
    clone.querySelectorAll('script, style, button, [role="button"], a, input[type="button"]').forEach(function (n) {
      n.remove();
    });
    let text = (clone.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim();
    text = text.replace(/\b\d+\s*points?\b/gi, '').replace(/\s+/g, ' ').trim();
    return text.slice(0, 3000);
  }

  // ── Solutions panel ──────────────────────────────────────────────────────

  const PANEL_ID = 'coursera-sandbox-solutions-panel';

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) {
      panel.style.display = 'flex';
      return panel;
    }

    panel = document.createElement('div');
    panel.id = PANEL_ID;
    panel.innerHTML =
      '<div class="sbxsol-header">' +
      '<span class="sbxsol-title">Sandbox Solutions</span>' +
      '<div class="sbxsol-actions">' +
      '<button type="button" class="sbxsol-btn" data-action="copy-all">Copy All</button>' +
      '<button type="button" class="sbxsol-btn sbxsol-btn-icon" data-action="close">&times;</button>' +
      '</div>' +
      '</div>' +
      '<div class="sbxsol-body"></div>';
    (document.body || document.documentElement).appendChild(panel);

    panel.querySelector('[data-action="close"]').addEventListener('click', function () {
      panel.style.display = 'none';
    });
    panel.querySelector('[data-action="copy-all"]').addEventListener('click', function (evt) {
      const text = panelSolutions
        .filter(Boolean)
        .map(function (sol, i) {
          return 'Question ' + (i + 1) + ':\n' + sol.prompt + '\n\nSolution:\n' + sol.code;
        })
        .join('\n\n' + '─'.repeat(40) + '\n\n');
      copyText(text || '');
      flashLabel(evt.currentTarget, 'Copied!');
    });

    return panel;
  }

  function renderPanelSkeleton(count) {
    const panel = ensurePanel();
    const body = panel.querySelector('.sbxsol-body');
    body.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const item = document.createElement('div');
      item.className = 'sbxsol-item';
      item.dataset.index = String(i);
      item.innerHTML =
        '<div class="sbxsol-item-header">Question ' + (i + 1) + '</div>' +
        '<div class="sbxsol-prompt">Reading question…</div>' +
        '<div class="sbxsol-status">Generating solution…</div>';
      body.appendChild(item);
    }
  }

  function updatePanelEntry(index, data) {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    const item = panel.querySelector('.sbxsol-item[data-index="' + index + '"]');
    if (!item) return;

    const promptEl = item.querySelector('.sbxsol-prompt');
    if (data.prompt && promptEl) {
      promptEl.textContent = data.prompt.slice(0, 220) + (data.prompt.length > 220 ? '…' : '');
    }

    const statusEl = item.querySelector('.sbxsol-status');

    if (data.error) {
      if (statusEl) {
        statusEl.textContent = data.error;
        statusEl.classList.add('sbxsol-error');
      }
      return;
    }

    if (statusEl) statusEl.remove();

    const codeWrap = document.createElement('div');
    codeWrap.className = 'sbxsol-code-wrap';

    const pre = document.createElement('pre');
    pre.className = 'sbxsol-code';
    pre.textContent = data.code;

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'sbxsol-btn sbxsol-copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', function (evt) {
      copyText(data.code);
      flashLabel(evt.currentTarget, 'Copied!');
    });

    codeWrap.appendChild(pre);
    codeWrap.appendChild(copyBtn);
    item.appendChild(codeWrap);
  }

  function flashLabel(btn, text) {
    const original = btn.textContent;
    btn.textContent = text;
    btn.classList.add('sbxsol-flash');
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('sbxsol-flash');
    }, 1400);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () {
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.style.top = '0';
    ta.style.left = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
    } catch (_e) {
      /* ignore */
    }
    ta.remove();
  }
})();
