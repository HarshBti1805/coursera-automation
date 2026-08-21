// Injected script - runs in the page context for enhanced video control
(function() {
    'use strict';
    
    console.log('Coursera Automation injected script loaded');
    
    // Listen for messages from content script
    window.addEventListener('message', function(event) {
        if (event.data.type === 'COURSERA_AUTOMATION') {
            handleAction(event.data);
        }
    });
    
    function handleAction(data) {
        switch (data.action) {
            case 'setVideoSpeed':
                setAllVideoSpeeds(data.speed);
                break;
            case 'fillCodeEditor':
                fillCodeEditor(data.editorId, data.editorType, data.code);
                break;
        }
    }

    // ── Code editor filling ────────────────────────────────────────────────

    function fillCodeEditor(editorId, editorType, code) {
        if (!code) return;

        // 1. Try Monaco API (window.monaco available in page context)
        if (editorType === 'monaco' || !editorType) {
            if (tryFillMonaco(editorId, code)) return;
        }

        // 2. Try CodeMirror API
        if (editorType === 'codemirror' || !editorType) {
            if (tryFillCodeMirror(editorId, code)) return;
        }

        // 3. Generic textarea fallback (Monaco's hidden inputarea)
        tryFillTextarea(editorId, code);
    }

    function tryFillMonaco(editorId, code) {
        var m = window.monaco || window.require && window.require('vs/editor/editor.main');
        if (!m || !m.editor) return false;

        var editors = m.editor.getEditors();
        if (!editors || editors.length === 0) return false;

        // Prefer the editor whose DOM node carries our marker attribute.
        var target = null;
        for (var i = 0; i < editors.length; i++) {
            var node = editors[i].getDomNode && editors[i].getDomNode();
            if (node && node.dataset.courseraEditorId === editorId) {
                target = editors[i];
                break;
            }
        }
        // Fall back to the first editor if we couldn't match by ID.
        if (!target) target = editors[0];

        if (!target) return false;

        try {
            target.focus();
            var model = target.getModel();
            if (model) {
                // Use edit operations so undo history is preserved.
                var fullRange = model.getFullModelRange();
                target.executeEdits('coursera-auto', [{
                    range: fullRange,
                    text: code,
                    forceMoveMarkers: true
                }]);
            } else {
                target.setValue(code);
            }
            console.log('[Coursera Auto] Monaco editor filled');
            return true;
        } catch (e) {
            console.warn('[Coursera Auto] Monaco fill error:', e);
            return false;
        }
    }

    function tryFillCodeMirror(editorId, code) {
        var el = document.querySelector('[data-coursera-editor-id="' + editorId + '"]');
        if (!el) return false;
        var cm = el.CodeMirror;
        if (!cm || typeof cm.setValue !== 'function') return false;
        try {
            cm.setValue(code);
            console.log('[Coursera Auto] CodeMirror editor filled');
            return true;
        } catch (e) {
            console.warn('[Coursera Auto] CodeMirror fill error:', e);
            return false;
        }
    }

    function tryFillTextarea(editorId, code) {
        var container = document.querySelector('[data-coursera-editor-id="' + editorId + '"]');
        if (!container) return false;
        // Monaco creates a hidden <textarea class="inputarea"> for keyboard access.
        var textarea = container.querySelector('textarea.inputarea') || container.querySelector('textarea');
        if (!textarea) return false;
        try {
            textarea.focus();
            // Select all existing content.
            textarea.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'a', code: 'KeyA', ctrlKey: true, bubbles: true, cancelable: true
            }));
            // Insert replacement text.
            var inserted = document.execCommand('insertText', false, code);
            if (!inserted) {
                var proto = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
                if (proto && proto.set) proto.set.call(textarea, code);
                textarea.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: code }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
            }
            console.log('[Coursera Auto] Textarea fallback filled');
            return true;
        } catch (e) {
            console.warn('[Coursera Auto] Textarea fallback error:', e);
            return false;
        }
    }
    
    function setAllVideoSpeeds(speed) {
        // Find all video elements
        const videos = document.querySelectorAll('video');
        
        videos.forEach(video => {
            try {
                // Override playbackRate property
                Object.defineProperty(video, 'playbackRate', {
                    set: function(value) {
                        this._playbackRate = speed;
                        this.defaultPlaybackRate = speed;
                        
                        // Trigger speed change event
                        const event = new Event('ratechange');
                        this.dispatchEvent(event);
                    },
                    get: function() {
                        return this._playbackRate || speed;
                    },
                    configurable: true
                });
                
                video.playbackRate = speed;
                video.defaultPlaybackRate = speed;
                
                console.log(`Video speed set to ${speed}x`);
            } catch (error) {
                console.error('Error setting video speed:', error);
            }
        });
        
        // Also override any rate limiting
        overrideRateLimiting();
    }
    
    function overrideRateLimiting() {
        // Override common rate limiting methods
        const originalCreateElement = document.createElement;
        document.createElement = function(tagName) {
            const element = originalCreateElement.call(this, tagName);
            
            if (tagName.toLowerCase() === 'video') {
                // Remove rate limitations on new video elements
                const originalSetAttribute = element.setAttribute;
                element.setAttribute = function(name, value) {
                    if (name === 'playbackrate' || name === 'data-max-rate') {
                        return; // Ignore rate limiting attributes
                    }
                    return originalSetAttribute.call(this, name, value);
                };
            }
            
            return element;
        };
        
        // Override HTMLVideoElement prototype
        if (window.HTMLVideoElement) {
            const originalPlaybackRateDescriptor = Object.getOwnPropertyDescriptor(
                HTMLVideoElement.prototype, 'playbackRate'
            );
            
            if (originalPlaybackRateDescriptor) {
                Object.defineProperty(HTMLVideoElement.prototype, 'playbackRate', {
                    set: function(value) {
                        // Allow any playback rate
                        originalPlaybackRateDescriptor.set.call(this, value);
                    },
                    get: originalPlaybackRateDescriptor.get,
                    configurable: true
                });
            }
        }
    }
    
    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        overrideRateLimiting();
    });
    
    // Also run immediately in case DOM is already loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', overrideRateLimiting);
    } else {
        overrideRateLimiting();
    }
    
})();
