// Content script - runs in the context of Coursera pages
(function courseraAutomationContentScript() {
    'use strict';

    if (globalThis.__COURSERA_AUTOMATION_EXT__) {
        console.log('[Coursera Auto] Already loaded, skipping duplicate injection');
        return;
    }

    const state = {
        autoAnswerEnabled: false,
        questionObserver: null,
        questionScanInterval: null,
        questionScanDebounce: null,
        questionScanInFlight: false,
        videoObserver: null
    };
    globalThis.__COURSERA_AUTOMATION_EXT__ = state;
    globalThis.__COURSERA_AUTOMATION_LOADED__ = true;

    console.log('Coursera Automation Extension loaded');

    initialize().catch(function(err) {
        console.error('[Coursera Auto] Initialize failed:', err);
    });

    async function initialize() {
    // Load settings
        const result = await chrome.storage.sync.get(['autoAnswerEnabled']);
        state.autoAnswerEnabled = result.autoAnswerEnabled || false;

        injectScript();

        if (state.autoAnswerEnabled) {
            startQuestionMonitoring();
        }

        startVideoMonitoring();
        chrome.runtime.onMessage.addListener(handleMessage);
    }

    function injectScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('injected.js');
    script.onload = function() {
        this.remove();
    };
        (document.head || document.documentElement).appendChild(script);
    }

    function handleMessage(request, sender, sendResponse) {
        switch (request.action) {
            case 'setVideoSpeed':
                setVideoSpeed(request.speed);
                break;
            case 'toggleAutoAnswer':
                state.autoAnswerEnabled = request.enabled;
                if (state.autoAnswerEnabled) {
                    startQuestionMonitoring();
                } else {
                    stopQuestionMonitoring();
                }
                break;
        }
        sendResponse({ success: true });
    }

    function setVideoSpeed(speed) {
    // Send message to injected script
    window.postMessage({
        type: 'COURSERA_AUTOMATION',
        action: 'setVideoSpeed',
        speed: speed
    }, '*');
    
    // Also try direct manipulation as fallback
    const videos = document.querySelectorAll('video');
    videos.forEach(video => {
        try {
            video.playbackRate = speed;
            console.log(`Set video speed to ${speed}x`);
        } catch (error) {
            console.error('Error setting video speed:', error);
        }
        });
    }

    function scheduleQuestionScan() {
        if (state.questionScanDebounce) {
            clearTimeout(state.questionScanDebounce);
        }
        state.questionScanDebounce = setTimeout(function() {
            runQuestionScan().catch(function(err) {
                console.error('[Coursera Auto] Scan failed:', err);
            });
        }, 400);
    }

    async function runQuestionScan() {
        if (!state.autoAnswerEnabled || state.questionScanInFlight) {
            return;
        }
        state.questionScanInFlight = true;
        try {
            await scanAllQuestions();
        } finally {
            state.questionScanInFlight = false;
        }
    }

    function startQuestionMonitoring() {
        console.log('[Coursera Auto] Starting question monitoring...');
        stopQuestionMonitoring();

        state.questionObserver = new MutationObserver(function() {
            scheduleQuestionScan();
        });
        state.questionObserver.observe(document.body, {
            childList: true,
            subtree: true
        });

        runQuestionScan().catch(function(err) {
            console.error('[Coursera Auto] Initial scan failed:', err);
        });
        state.questionScanInterval = setInterval(function() {
            runQuestionScan().catch(function(err) {
                console.error('[Coursera Auto] Interval scan failed:', err);
            });
        }, 2000);
    }

    function stopQuestionMonitoring() {
        if (state.questionObserver) {
            state.questionObserver.disconnect();
            state.questionObserver = null;
        }
        if (state.questionScanInterval) {
            clearInterval(state.questionScanInterval);
            state.questionScanInterval = null;
        }
        if (state.questionScanDebounce) {
            clearTimeout(state.questionScanDebounce);
            state.questionScanDebounce = null;
        }
        state.questionScanInFlight = false;
    }

    function findQuestionBlocks() {
    const seen = new Set();
    const results = [];

    const selectors = [
        '[data-testid="part-Submission_MultipleChoiceQuestion"]',
        '[data-testid="part-Submission_CheckboxQuestion"]',
        '[data-testid="part-Submission_TextInputQuestion"]',
        '[data-testid^="part-Submission_"]',
        '.rc-FormPartsQuestion',
        'fieldset'
    ];

    for (const selector of selectors) {
        document.querySelectorAll(selector).forEach(function(node) {
            if (seen.has(node)) return;
            const hasChoices = node.querySelector('input[type="radio"], input[type="checkbox"]');
            const hasTextAnswer = node.querySelector(
                'input[aria-label="Enter answer here"], textarea[aria-label="Enter answer here"], input[type="text"], textarea'
            );
            if (!hasChoices && !hasTextAnswer) return;
            seen.add(node);
            results.push(node);
        });
    }

    if (results.length === 0) {
        document.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach(function(input) {
            let parent = input.parentElement;
            for (let i = 0; i < 12 && parent; i++) {
                const count = parent.querySelectorAll('input[type="radio"], input[type="checkbox"]').length;
                if (count >= 2 && !seen.has(parent)) {
                    seen.add(parent);
                    results.push(parent);
                    break;
                }
                parent = parent.parentElement;
            }
        });
    }

    const leafBlocks = results.filter(function(block) {
        return !results.some(function(other) {
            return other !== block && block.contains(other);
        });
    });

    leafBlocks.sort(function(a, b) {
        const ra = a.getBoundingClientRect();
        const rb = b.getBoundingClientRect();
        return (ra.top + window.scrollY) - (rb.top + window.scrollY);
    });

    return leafBlocks;
}

    async function scanAllQuestions() {
        if (!state.autoAnswerEnabled) return;
    const blocks = findQuestionBlocks();
    if (blocks.length > 0) {
        console.log('[Coursera Auto] Scanning ' + blocks.length + ' question block(s)');
    }
        for (let i = 0; i < blocks.length; i++) {
            await processQuestion(blocks[i]);
        }
    }

    function startVideoMonitoring() {
        state.videoObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    const videos = node.querySelectorAll ? node.querySelectorAll('video') : [];
                    if (node.tagName === 'VIDEO') {
                        setupVideoControls(node);
                    }
                    videos.forEach(setupVideoControls);
                }
            });
        });
        });

        state.videoObserver.observe(document.body, {
            childList: true,
            subtree: true
        });

        document.querySelectorAll('video').forEach(setupVideoControls);
    }

    function setupVideoControls(video) {
    // Add event listeners for better speed control
    video.addEventListener('loadeddata', function() {
        // Restore speed setting
        chrome.storage.sync.get(['currentSpeed'], function(result) {
            if (result.currentSpeed) {
                video.playbackRate = result.currentSpeed;
            }
        });
    });
}

async function processQuestion(questionElement) {
    if (questionElement.dataset.courseraAutomationDone === 'true') return;

    const questionData = extractQuestionData(questionElement);
    if (!questionData) return;

    questionElement.dataset.courseraAutomationDone = 'true';

    try {
        console.log('[Coursera Auto] Question:', questionData.prompt.slice(0, 80) + '...');
        console.log('[Coursera Auto] Options:', questionData.options.map(function(o) { return o.text; }));

        const answerResult = await getAIAnswer(questionData);
        if (!answerResult || !answerResult.answers || !answerResult.answers.length) {
            questionElement.dataset.courseraAutomationDone = 'false';
            return;
        }

        const selected = selectAnswer(questionElement, questionData, answerResult.answers);
        if (selected) {
            console.log('[Coursera Auto] Answered question');
        } else {
            console.warn('[Coursera Auto] Could not click answer:', answerResult.answers);
            questionElement.dataset.courseraAutomationDone = 'false';
        }
    } catch (error) {
        console.error('[Coursera Auto] Error processing question:', error);
        questionElement.dataset.courseraAutomationDone = 'false';
    }
}

function normalizeText(text) {
    return (text || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function extractQuestionData(questionElement) {
    let prompt = '';

    const legend = questionElement.querySelector('[data-testid="legend"]');
    const cml = legend && legend.querySelector('.rc-CML');
    const fromLegend = ((cml || legend || null).innerText || '')
        .replace(/^\d+\.\s*/, '')
        .replace(/\d+\s*points?\s*/gi, '')
        .replace(/\s+/g, ' ')
        .trim();
    if (fromLegend) {
        prompt = fromLegend.slice(0, 1200);
    }

    if (!prompt) {
        const promptSelectors = [
            '[data-testid="question-prompt"]',
            '[data-testid="prompt"]',
            '.rc-FormPartsQuestion__contentCell',
            '.question-prompt',
            'h1', 'h2', 'h3', 'h4'
        ];
        for (const selector of promptSelectors) {
            const el = questionElement.querySelector(selector);
            if (el && el.textContent.trim().length > 5) {
                prompt = el.textContent.trim().slice(0, 1200);
                break;
            }
        }
    }

    const options = [];
    const newLabels = questionElement.querySelectorAll('label.cds-checkboxAndRadio-label');
    if (newLabels.length >= 2) {
        newLabels.forEach(function(label, index) {
            const text = (label.innerText || '').replace(/\s+/g, ' ').trim().replace(/^[○◉□■✓✗]\s*/, '');
            if (text) options.push({ text: text, index: index, element: label });
        });
    }

    if (options.length === 0) {
        const legacyOpts = questionElement.querySelectorAll('.rc-Option');
        if (legacyOpts.length >= 2) {
            legacyOpts.forEach(function(opt, index) {
                const text = (opt.innerText || '').replace(/\s+/g, ' ').trim();
                if (text) options.push({ text: text, index: index, element: opt });
            });
        }
    }

    if (options.length === 0) {
        const labels = [...questionElement.querySelectorAll('label')].filter(function(label) {
            return label.querySelector('input[type="radio"], input[type="checkbox"]');
        });
        labels.forEach(function(label, index) {
            const text = (label.innerText || '').replace(/\s+/g, ' ').trim();
            if (text && text.length < 800) {
                options.push({ text: text, index: index, element: label });
            }
        });
    }

    const textInput = questionElement.querySelector(
        'input[aria-label="Enter answer here"], textarea[aria-label="Enter answer here"], input[type="text"], textarea'
    );
    if (textInput && prompt) {
        return {
            prompt: prompt,
            options: [{ text: '', index: 0, element: textInput }],
            type: 'text'
        };
    }

    if (prompt && options.length >= 2) {
        const checkboxCount = questionElement.querySelectorAll(
            'input[type="checkbox"], [role="checkbox"]'
        ).length;
        const radioCount = questionElement.querySelectorAll('input[type="radio"]').length;
        const multiSelectPrompt =
            /select all|choose all|tick all|check all|choose\s+(?:two|three|four|five|\d+)|\(choose\s+(?:two|three|four|five|\d+)\)/i.test(
                prompt
            );
        const isCheckboxQuestion =
            questionElement.matches('[data-testid="part-Submission_CheckboxQuestion"]') ||
            questionElement.querySelector('[data-testid*="CheckboxQuestion"]') ||
            checkboxCount > 0 ||
            (multiSelectPrompt && checkboxCount >= radioCount) ||
            multiSelectPrompt;

        return {
            prompt: prompt,
            options: options,
            type: isCheckboxQuestion ? 'multiple-select' : 'multiple-choice',
            checkboxCount: checkboxCount
        };
    }

    return null;
}

async function getAIAnswer(questionData) {
    try {
        const response = await fetch('http://localhost:8000/answer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: questionData.prompt,
                options: questionData.options.map(opt => opt.text),
                type: questionData.type
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            const answers = normalizeAnswerList(result, questionData);
            const confidence = result.confidence || 0;
            console.log(
                '[Coursera Auto] AI answer' +
                (answers.length > 1 ? 's' : '') + ':',
                answers,
                '(' + Math.round(confidence * 100) + '%)'
            );
            return { answers: answers, answer: answers[0] || result.answer };
        }
        console.warn('[Coursera Auto] Backend error, using local fallback:', response.status);
    } catch (error) {
        console.warn('[Coursera Auto] Backend offline, using local fallback:', error.message);
    }

    return getHeuristicAnswer(questionData);
}

function normalizeAnswerList(result, questionData) {
    let list = [];
    if (Array.isArray(result.answers) && result.answers.length > 0) {
        list = result.answers.map(function(a) { return String(a).trim(); }).filter(Boolean);
    }

    const combined = (result.answer || '').trim();
    if (list.length <= 1 && combined) {
        if (combined.includes(';')) {
            list = combined.split(';').map(function(s) { return s.trim(); }).filter(Boolean);
        } else if (combined.includes('|')) {
            list = combined.split('|').map(function(s) { return s.trim(); }).filter(Boolean);
        } else if (list.length === 0) {
            list = [combined];
        }
    }

    return list;
}

function resolveOptionIndicesForAnswers(options, answerTexts) {
    const indices = new Set();
    const normAnswers = answerTexts.map(normalizeText).filter(Boolean);

    options.forEach(function(opt, index) {
        const optNorm = normalizeText(opt.text);
        if (!optNorm) return;

        for (let i = 0; i < normAnswers.length; i++) {
            const ans = normAnswers[i];
            if (optNorm === ans) {
                indices.add(index);
                return;
            }
            if (optNorm.length >= 12 && ans.includes(optNorm)) {
                indices.add(index);
                return;
            }
            if (ans.length >= 12 && optNorm.includes(ans)) {
                indices.add(index);
                return;
            }
            const optPrefix = optNorm.slice(0, Math.min(50, optNorm.length));
            const ansPrefix = ans.slice(0, Math.min(50, ans.length));
            if (optPrefix.length >= 15 && (ans.includes(optPrefix) || optNorm.includes(ansPrefix))) {
                indices.add(index);
                return;
            }
        }
    });

    return Array.from(indices).sort(function(a, b) { return a - b; });
}

function getHeuristicAnswer(questionData) {
    const options = questionData.options;
    const positiveKeywords = ['correct', 'true', 'yes', 'always'];

    const matched = [];
    options.forEach(function(option) {
        const text = option.text.toLowerCase();
        if (positiveKeywords.some(function(keyword) { return text.includes(keyword); })) {
            matched.push(option.text);
        }
    });

    if (matched.length > 0) {
        return { answers: matched, answer: matched[0] };
    }

    const longestOption = options.reduce(function(prev, current) {
        return (current.text.length > prev.text.length) ? current : prev;
    });
    return { answers: [longestOption.text], answer: longestOption.text };
}

function findOptionIndex(options, answerText) {
    const normAnswer = normalizeText(answerText);
    if (!normAnswer) return -1;

    let idx = options.findIndex(function(o) {
        return normalizeText(o.text) === normAnswer;
    });
    if (idx >= 0) return idx;

    idx = options.findIndex(function(o) {
        const t = normalizeText(o.text);
        return t.includes(normAnswer) || normAnswer.includes(t);
    });
    if (idx >= 0) return idx;

    const answerWords = normAnswer.split(' ').filter(function(w) { return w.length > 3; });
    if (answerWords.length > 0) {
        let bestIdx = -1;
        let bestScore = 0;
        options.forEach(function(o, i) {
            const t = normalizeText(o.text);
            const score = answerWords.filter(function(w) { return t.includes(w); }).length;
            if (score > bestScore) {
                bestScore = score;
                bestIdx = i;
            }
        });
        if (bestIdx >= 0) return bestIdx;
    }

    return -1;
}

function clickCourseraInput(input) {
    const label = input.closest('label') || input.parentElement && input.parentElement.closest('label');
    const target = label || input;
    ['mousedown', 'mouseup', 'click'].forEach(function(type) {
        target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    });
    if (input.type === 'checkbox' && !input.checked) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked');
        if (setter && setter.set) {
            setter.set.call(input, true);
        } else {
            input.checked = true;
        }
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }
}

function fillTextAnswer(input, answerText) {
    input.focus();
    input.dispatchEvent(new Event('focus', { bubbles: true }));

    if (input.getAttribute('contenteditable') === 'true') {
        input.textContent = answerText;
        input.dispatchEvent(new InputEvent('input', { bubbles: true, data: answerText }));
        return true;
    }

    const inserted = document.execCommand && document.execCommand('insertText', false, answerText);
    if (!inserted || !input.value) {
        const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (nativeSetter && nativeSetter.set) {
            nativeSetter.set.call(input, answerText);
        } else {
            input.value = answerText;
        }
    }
    input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: answerText }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
}

function selectAnswer(questionElement, questionData, answerTexts) {
    const texts = Array.isArray(answerTexts) ? answerTexts : [answerTexts];

    if (questionData.type === 'text') {
        const input = questionData.options[0].element;
        console.log('[Coursera Auto] Filled text answer');
        return fillTextAnswer(input, texts[0] || '');
    }

    const isMulti =
        questionData.type === 'multiple-select' ||
        (questionData.checkboxCount > 0 && texts.length > 1);

    if (isMulti) {
        const indices = resolveOptionIndicesForAnswers(questionData.options, texts);
        if (indices.length === 0) {
            console.warn('[Coursera Auto] No options matched for multi-select:', texts);
            return false;
        }

        const checkboxes = [...questionElement.querySelectorAll(
            'input[type="checkbox"], [role="checkbox"] input, label.cds-checkboxAndRadio-label input[type="checkbox"]'
        )];

        let clicked = 0;
        indices.forEach(function(optionIndex) {
            const opt = questionData.options[optionIndex];
            let input = checkboxes[optionIndex];
            if (!input && opt.element) {
                input = opt.element.querySelector('input[type="checkbox"]');
            }
            if (input) {
                if (!input.checked) {
                    clickCourseraInput(input);
                }
                clicked++;
                console.log('[Coursera Auto] Checked (' + (clicked) + '/' + indices.length + '):',
                    opt.text.slice(0, 60) + (opt.text.length > 60 ? '...' : ''));
            } else if (opt.element) {
                opt.element.click();
                clicked++;
            }
        });
        return clicked > 0;
    }

    const answerText = texts[0];
    const optionIndex = findOptionIndex(questionData.options, answerText);
    if (optionIndex < 0) return false;

    const inputs = [...questionElement.querySelectorAll('input[type="radio"]')];
    const input = inputs[optionIndex];
    if (!input) {
        const fallback = questionData.options[optionIndex].element;
        if (fallback) {
            fallback.click();
            console.log('[Coursera Auto] Clicked option:', questionData.options[optionIndex].text);
            return true;
        }
        return false;
    }

    clickCourseraInput(input);
    console.log('[Coursera Auto] Selected:', questionData.options[optionIndex].text);
    return true;
}

})();
