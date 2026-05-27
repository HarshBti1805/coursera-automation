document.addEventListener('DOMContentLoaded', () => {
  const speedBtns       = document.querySelectorAll('.speed-btn');
  const customSpeedInput = document.getElementById('customSpeed');
  const setCustomSpeedBtn = document.getElementById('setCustomSpeed');
  const autoAnswerCheck  = document.getElementById('autoAnswerCheck');
  const statusEl         = document.getElementById('status');
  const currentSpeedLabel = document.getElementById('currentSpeedLabel');
  const backendDot       = document.getElementById('backendDot');
  const backendLabel     = document.getElementById('backendLabel');

  // ── Backend health ping ──
  fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(2500) })
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(data => {
      backendDot.className = 'dot online';
      backendLabel.textContent = data.ai_provider ?? 'online';
    })
    .catch(() => {
      backendDot.className = 'dot offline';
      backendLabel.textContent = 'offline';
    });

  // ── Load saved state ──
  chrome.storage.sync.get(['autoAnswerEnabled', 'currentSpeed'], result => {
    autoAnswerCheck.checked = !!result.autoAnswerEnabled;
    if (result.autoAnswerEnabled) setStatus('active', 'auto answer on');

    if (result.currentSpeed) {
      updateSpeedUI(result.currentSpeed);
    }
  });

  // ── Speed buttons ──
  speedBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      setVideoSpeed(parseFloat(btn.dataset.speed));
      speedBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // ── Custom speed ──
  setCustomSpeedBtn.addEventListener('click', applyCustomSpeed);
  customSpeedInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') applyCustomSpeed();
  });

  function applyCustomSpeed() {
    const val = parseFloat(customSpeedInput.value);
    if (val > 0 && val <= 10) {
      setVideoSpeed(val);
      speedBtns.forEach(b => b.classList.remove('active'));
      customSpeedInput.value = '';
    }
  }

  // ── Toggle auto answer ──
  autoAnswerCheck.addEventListener('change', () => {
    const enabled = autoAnswerCheck.checked;
    chrome.storage.sync.set({ autoAnswerEnabled: enabled });

    if (enabled) {
      setStatus('active', 'auto answer on');
    } else {
      setStatus('', 'auto answer off');
    }

    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'toggleAutoAnswer', enabled });
      }
    });
  });

  // ── Helpers ──
  function setVideoSpeed(speed) {
    chrome.storage.sync.set({ currentSpeed: speed });
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'setVideoSpeed', speed });
      }
    });
    updateSpeedUI(speed);
    setStatus('ok', `speed → ${speed}×`);
  }

  function updateSpeedUI(speed) {
    currentSpeedLabel.textContent = `${speed}×`;
    speedBtns.forEach(b => {
      b.classList.toggle('active', parseFloat(b.dataset.speed) === speed);
    });
  }

  function setStatus(cls, text) {
    statusEl.className = 'status-line' + (cls ? ` ${cls}` : '');
    statusEl.textContent = text;
  }
});
