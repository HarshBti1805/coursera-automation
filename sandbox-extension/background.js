chrome.runtime.onInstalled.addListener(function () {
  console.log('Coursera Sandbox Solver installed');
  chrome.storage.sync.set({
    sandboxAutoSolveEnabled: false,
    sandboxAutoRun: true
  });
});
