document.addEventListener('DOMContentLoaded', function () {
  const autoSolveToggle = document.getElementById('autoSolveToggle');
  const autoRunToggle = document.getElementById('autoRunToggle');
  const toggleBadge = document.getElementById('toggleBadge');
  const autoRunBadge = document.getElementById('autoRunBadge');
  const solveNowBtn = document.getElementById('solveNowBtn');
  const copySolutionsBtn = document.getElementById('copySolutionsBtn');
  const status = document.getElementById('status');

  function setSolveToggle(enabled) {
    if (enabled) {
      autoSolveToggle.classList.add('active');
      autoSolveToggle.querySelector('.toggle-label').textContent = 'Disable Sandbox Solver';
      toggleBadge.textContent = 'On';
    } else {
      autoSolveToggle.classList.remove('active');
      autoSolveToggle.querySelector('.toggle-label').textContent = 'Enable Sandbox Solver';
      toggleBadge.textContent = 'Off';
    }
  }

  function setRunToggle(enabled) {
    if (enabled) {
      autoRunToggle.classList.add('active');
      autoRunBadge.textContent = 'On';
    } else {
      autoRunToggle.classList.remove('active');
      autoRunBadge.textContent = 'Off';
    }
  }

  function flashStatus(text, ok) {
    status.textContent = text;
    status.className = 'status ' + (ok === false ? 'err' : ok ? 'ok' : '');
  }

  // ── Resilient messaging ──────────────────────────────────────────────────
  // Tabs that were already open before this extension was installed/reloaded
  // never got content.js injected by the manifest's declarative content
  // script (Chrome only injects into NEW navigations). If a message fails to
  // reach the tab, force a fresh injection (clearing any stale marker first)
  // and retry once before giving up.

  function isCourseraUrl(url) {
    try {
      const host = new URL(url).hostname;
      return /(^|\.)coursera\.org$/i.test(host);
    } catch (_e) {
      return false;
    }
  }

  function injectAndRetry(tabId, message, callback) {
    chrome.scripting.executeScript(
      {
        target: { tabId: tabId },
        func: function () {
          try {
            delete window.__COURSERA_SANDBOX_SOLVER__;
            delete window.__COURSERA_SANDBOX_INJECTED__;
          } catch (_e) {
            /* ignore */
          }
        }
      },
      function () {
        if (chrome.runtime.lastError) {
          callback(null, chrome.runtime.lastError.message);
          return;
        }
        chrome.scripting.insertCSS(
          { target: { tabId: tabId }, files: ['styles.css'] },
          function () {
            void chrome.runtime.lastError; // CSS failure is non-fatal
            chrome.scripting.executeScript(
              { target: { tabId: tabId }, files: ['content.js'] },
              function () {
                if (chrome.runtime.lastError) {
                  callback(null, chrome.runtime.lastError.message);
                  return;
                }
                chrome.tabs.sendMessage(tabId, message, function (response) {
                  if (chrome.runtime.lastError) {
                    callback(null, chrome.runtime.lastError.message);
                    return;
                  }
                  callback(response, null);
                });
              }
            );
          }
        );
      }
    );
  }

  function sendWithHeal(tabId, tabUrl, message, callback) {
    chrome.tabs.sendMessage(tabId, message, function (response) {
      if (!chrome.runtime.lastError) {
        callback(response, null);
        return;
      }
      if (!isCourseraUrl(tabUrl)) {
        callback(null, 'Open a Coursera page first');
        return;
      }
      // Content script missing/orphaned on an already-open tab — heal it.
      injectAndRetry(tabId, message, callback);
    });
  }

  function withActiveCourseraTab(message, callback) {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      const tab = tabs[0];
      if (!tab || !tab.id) {
        callback(null, 'No active tab');
        return;
      }
      if (!isCourseraUrl(tab.url || '')) {
        callback(null, 'Open a Coursera page first');
        return;
      }
      sendWithHeal(tab.id, tab.url || '', message, callback);
    });
  }

  chrome.storage.sync.get(
    ['sandboxAutoSolveEnabled', 'sandboxAutoRun'],
    function (result) {
      setSolveToggle(!!result.sandboxAutoSolveEnabled);
      setRunToggle(result.sandboxAutoRun !== false);
    }
  );

  autoSolveToggle.addEventListener('click', function () {
    chrome.storage.sync.get(['sandboxAutoSolveEnabled'], function (result) {
      const next = !result.sandboxAutoSolveEnabled;
      chrome.storage.sync.set({ sandboxAutoSolveEnabled: next }, function () {
        setSolveToggle(next);
        withActiveCourseraTab(
          { action: 'toggleSandboxSolve', enabled: next },
          function (_response, err) {
            if (err) {
              flashStatus(err, false);
            } else {
              flashStatus(next ? 'Sandbox solver enabled' : 'Sandbox solver disabled', true);
            }
          }
        );
      });
    });
  });

  autoRunToggle.addEventListener('click', function () {
    chrome.storage.sync.get(['sandboxAutoRun'], function (result) {
      const next = result.sandboxAutoRun === false;
      chrome.storage.sync.set({ sandboxAutoRun: next }, function () {
        setRunToggle(next);
        withActiveCourseraTab(
          { action: 'setSandboxAutoRun', enabled: next },
          function (_response, err) {
            if (err) {
              flashStatus(err, false);
            } else {
              flashStatus(next ? 'Will click Run after fill' : 'Will not click Run', true);
            }
          }
        );
      });
    });
  });

  solveNowBtn.addEventListener('click', function () {
    flashStatus('Scanning page…', true);
    withActiveCourseraTab({ action: 'solveSandboxesNow' }, function (response, err) {
      if (err) {
        flashStatus(err, false);
        return;
      }
      if (response && response.ok) {
        const reasons = response.reasons || {};
        const reasonKeys = Object.keys(reasons);
        let text = 'Found ' + response.found + ' sandbox(es), solved ' + response.solved;
        if (reasonKeys.length) {
          text +=
            ' — ' +
            reasonKeys
              .map(function (k) {
                return reasons[k] + ' ' + k.replace(/-/g, ' ');
              })
              .join(', ');
        }
        flashStatus(text, response.solved > 0);
      } else {
        flashStatus((response && response.error) || 'No sandboxes found', false);
      }
    });
  });

  copySolutionsBtn.addEventListener('click', function () {
    flashStatus('Generating solutions…', true);
    withActiveCourseraTab({ action: 'generateCopySolutions' }, function (response, err) {
      if (err) {
        flashStatus(err, false);
        return;
      }
      if (response && response.ok) {
        flashStatus(
          'Generated ' + response.count + '/' + response.total + ' solution(s) — see panel on the page',
          response.count > 0
        );
      } else {
        flashStatus((response && response.error) || 'No coding questions detected', false);
      }
    });
  });
});
