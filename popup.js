document.addEventListener('DOMContentLoaded', function () {
  const speedButtons = document.querySelectorAll('.speed-btn');
  const customSpeedInput = document.getElementById('customSpeed');
  const setCustomSpeedBtn = document.getElementById('setCustomSpeed');
  const autoAnswerToggle = document.getElementById('autoAnswerToggle');
  const toggleLabel = autoAnswerToggle.querySelector('.toggle-label');
  const toggleBadge = document.getElementById('toggleBadge');
  const status = document.getElementById('status');

  function setToggleState(enabled) {
    if (enabled) {
      autoAnswerToggle.classList.add('active');
      toggleLabel.textContent = 'Disable Auto Answer';
      toggleBadge.textContent = 'On';
    } else {
      autoAnswerToggle.classList.remove('active');
      toggleLabel.textContent = 'Enable Auto Answer';
      toggleBadge.textContent = 'Off';
    }
  }

  // Load saved settings
  chrome.storage.sync.get(['autoAnswerEnabled', 'currentSpeed'], function (result) {
    setToggleState(!!result.autoAnswerEnabled);

    if (result.currentSpeed) {
      speedButtons.forEach(btn => {
        if (parseFloat(btn.dataset.speed) === result.currentSpeed) {
          btn.classList.add('active');
        }
      });
    }
  });

  // Speed button handlers
  speedButtons.forEach(button => {
    button.addEventListener('click', function () {
      const speed = parseFloat(this.dataset.speed);
      setVideoSpeed(speed);
      speedButtons.forEach(btn => btn.classList.remove('active'));
      this.classList.add('active');
    });
  });

  // Custom speed handler
  setCustomSpeedBtn.addEventListener('click', function () {
    const speed = parseFloat(customSpeedInput.value);
    if (speed && speed > 0 && speed <= 10) {
      setVideoSpeed(speed);
      speedButtons.forEach(btn => btn.classList.remove('active'));
      customSpeedInput.value = '';
    }
  });

  // Auto answer toggle
  autoAnswerToggle.addEventListener('click', function () {
    chrome.storage.sync.get(['autoAnswerEnabled'], function (result) {
      const newState = !result.autoAnswerEnabled;

      chrome.storage.sync.set({ autoAnswerEnabled: newState }, function () {
        setToggleState(newState);
        status.textContent = newState ? 'Auto answer enabled' : 'Auto answer disabled';

        chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
          chrome.tabs.sendMessage(tabs[0].id, {
            action: 'toggleAutoAnswer',
            enabled: newState
          });
        });
      });
    });
  });

  function setVideoSpeed(speed) {
    chrome.storage.sync.set({ currentSpeed: speed });

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      chrome.tabs.sendMessage(tabs[0].id, {
        action: 'setVideoSpeed',
        speed: speed
      });
    });

    status.textContent = `Speed set to ${speed}x`;
  }
});
