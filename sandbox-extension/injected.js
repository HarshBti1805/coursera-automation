// Page-context script: fill sandbox code editors (Monaco / CodeMirror / Ace / textarea)
(function () {
  'use strict';

  if (window.__COURSERA_SANDBOX_INJECTED__) return;
  window.__COURSERA_SANDBOX_INJECTED__ = true;

  console.log('[Sandbox Solver] Injected script ready');

  window.addEventListener('message', function (event) {
    if (!event.data || event.data.type !== 'COURSERA_SANDBOX') return;
    handleAction(event.data);
  });

  function handleAction(data) {
    if (data.action === 'fillCodeEditor') {
      var ok = fillCodeEditor(data.editorId, data.editorType, data.code);
      window.postMessage(
        {
          type: 'COURSERA_SANDBOX_RESULT',
          requestId: data.requestId,
          ok: ok
        },
        '*'
      );
    }
  }

  function fillCodeEditor(editorId, editorType, code) {
    if (!code) return false;

    if ((editorType === 'monaco' || !editorType) && tryFillMonaco(editorId, code)) {
      return true;
    }
    if ((editorType === 'codemirror' || !editorType) && tryFillCodeMirror(editorId, code)) {
      return true;
    }
    if ((editorType === 'ace' || !editorType) && tryFillAce(editorId, code)) {
      return true;
    }
    if (tryFillTextarea(editorId, code)) return true;
    if (tryFillContentEditable(editorId, code)) return true;

    console.warn('[Sandbox Solver] No editor fill method worked for', editorId, editorType);
    return false;
  }

  function findMarkedNode(editorId) {
    if (!editorId) return null;
    return document.querySelector('[data-sandbox-editor-id="' + editorId + '"]');
  }

  function tryFillMonaco(editorId, code) {
    var monaco = window.monaco;
    if (!monaco && window.require) {
      try {
        monaco = window.require('vs/editor/editor.main');
      } catch (_e) {
        /* ignore */
      }
    }
    if (!monaco || !monaco.editor || !monaco.editor.getEditors) return false;

    var editors = monaco.editor.getEditors();
    if (!editors || !editors.length) return false;

    var target = null;
    for (var i = 0; i < editors.length; i++) {
      var node = editors[i].getDomNode && editors[i].getDomNode();
      if (node && node.dataset && node.dataset.sandboxEditorId === editorId) {
        target = editors[i];
        break;
      }
    }
    if (!target) {
      // If only one editor on the page, use it
      if (editors.length === 1) target = editors[0];
      else {
        // Prefer visible editor near our marked node
        var marked = findMarkedNode(editorId);
        if (marked) {
          for (var j = 0; j < editors.length; j++) {
            var n = editors[j].getDomNode && editors[j].getDomNode();
            if (n && (n === marked || marked.contains(n) || n.contains(marked))) {
              target = editors[j];
              break;
            }
          }
        }
      }
    }
    if (!target) return false;

    try {
      target.focus();
      var model = target.getModel && target.getModel();
      if (model && model.getFullModelRange) {
        target.executeEdits('sandbox-solver', [
          { range: model.getFullModelRange(), text: code, forceMoveMarkers: true }
        ]);
      } else if (target.setValue) {
        target.setValue(code);
      } else {
        return false;
      }
      console.log('[Sandbox Solver] Monaco filled');
      return true;
    } catch (e) {
      console.warn('[Sandbox Solver] Monaco error:', e);
      return false;
    }
  }

  function tryFillCodeMirror(editorId, code) {
    var el = findMarkedNode(editorId);
    if (!el) return false;

    // CodeMirror 5
    var cm = el.CodeMirror || (el.closest && el.closest('.CodeMirror') && el.closest('.CodeMirror').CodeMirror);
    if (!cm && el.parentElement) cm = el.parentElement.CodeMirror;
    if (cm && typeof cm.setValue === 'function') {
      try {
        cm.setValue(code);
        console.log('[Sandbox Solver] CodeMirror 5 filled');
        return true;
      } catch (e) {
        console.warn('[Sandbox Solver] CodeMirror 5 error:', e);
      }
    }

    // CodeMirror 6 — look for view on DOM
    var cm6Root = el.classList && el.classList.contains('cm-editor') ? el : el.querySelector && el.querySelector('.cm-editor');
    if (cm6Root && cm6Root.cmView && cm6Root.cmView.view) {
      try {
        var view = cm6Root.cmView.view;
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: code }
        });
        console.log('[Sandbox Solver] CodeMirror 6 filled');
        return true;
      } catch (e) {
        console.warn('[Sandbox Solver] CodeMirror 6 error:', e);
      }
    }

    return false;
  }

  function tryFillAce(editorId, code) {
    var el = findMarkedNode(editorId);
    if (!el) return false;

    var aceEl = el.classList && el.classList.contains('ace_editor') ? el : el.closest && el.closest('.ace_editor');
    if (!aceEl) aceEl = el.querySelector && el.querySelector('.ace_editor');
    if (!aceEl) aceEl = el;

    try {
      if (window.ace && typeof window.ace.edit === 'function') {
        var editor = window.ace.edit(aceEl);
        if (editor && typeof editor.setValue === 'function') {
          editor.setValue(code, -1);
          editor.clearSelection();
          console.log('[Sandbox Solver] Ace filled');
          return true;
        }
      }
      // Some pages stash the editor instance on the element
      if (aceEl.env && aceEl.env.editor && typeof aceEl.env.editor.setValue === 'function') {
        aceEl.env.editor.setValue(code, -1);
        console.log('[Sandbox Solver] Ace (env) filled');
        return true;
      }
    } catch (e) {
      console.warn('[Sandbox Solver] Ace error:', e);
    }
    return false;
  }

  function tryFillTextarea(editorId, code) {
    var container = findMarkedNode(editorId);
    if (!container) return false;

    var textarea = container.matches('textarea')
      ? container
      : container.querySelector('textarea.inputarea') || container.querySelector('textarea');

    if (!textarea) {
      // Monaco often puts textarea as sibling inside overflow guard
      var parent = container.parentElement;
      if (parent) {
        textarea =
          parent.querySelector('textarea.inputarea') || parent.querySelector('textarea');
      }
    }
    if (!textarea) return false;

    try {
      textarea.focus();
      var proto = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
      if (proto && proto.set) {
        proto.set.call(textarea, code);
      } else {
        textarea.value = code;
      }
      textarea.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: code }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
      // Also try execCommand path for frameworks listening to it
      try {
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, code);
      } catch (_e) {
        /* ignore */
      }
      console.log('[Sandbox Solver] Textarea filled');
      return true;
    } catch (e) {
      console.warn('[Sandbox Solver] Textarea error:', e);
      return false;
    }
  }

  function tryFillContentEditable(editorId, code) {
    var container = findMarkedNode(editorId);
    if (!container) return false;
    var el = container.getAttribute && container.getAttribute('contenteditable') === 'true'
      ? container
      : container.querySelector('[contenteditable="true"]');
    if (!el) return false;
    try {
      el.focus();
      el.textContent = code;
      el.dispatchEvent(new InputEvent('input', { bubbles: true, data: code }));
      console.log('[Sandbox Solver] Contenteditable filled');
      return true;
    } catch (e) {
      console.warn('[Sandbox Solver] Contenteditable error:', e);
      return false;
    }
  }
})();
