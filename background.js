// Background service worker
chrome.runtime.onInstalled.addListener(function() {
    console.log('Coursera Automation Extension installed');
    
    // Set default settings
    chrome.storage.sync.set({
        autoAnswerEnabled: false,
        currentSpeed: 1
    });
});

// content.js is injected via manifest content_scripts — do not inject again here
// (duplicate injection causes "Identifier already been declared" errors)
