/**
 * Syrinx Web Application
 * Medical Encounter Simulator
 */

// ============================================
// STATE
// ============================================

const state = {
    currentView: 'generate',
    theme: localStorage.getItem('syrinx-theme') || 'light',

    // Generation state
    currentEncounter: null,
    importedPatient: null,
    audioContext: null,
    audioBuffer: null,
    audioSource: null,
    isPlaying: false,

    // Practice state
    selectedRole: null,
    activeSession: null,
    sessionStartTime: null,
    sessionMessages: [],
    isRecording: false,
    mediaRecorder: null,
    deepgramSocket: null,

    // Sessions
    savedSessions: JSON.parse(localStorage.getItem('syrinx-sessions') || '[]'),
};

// ============================================
// PRESETS
// ============================================

const PRESETS = {
    'acute-fever': '6-month-old infant with fever for 2 days, temp up to 102.5, decreased appetite, fussy. Anxious first-time mom.',
    'well-child': '4-year-old girl for routine well-child check. Mom has questions about vaccines and preschool readiness.',
    'ear-infection': '2-year-old boy pulling at ear, had cold last week, now has fever and irritable. Parents both present.',
    'asthma': '8-year-old with known asthma, here for follow-up. Using rescue inhaler 3x/week. Coughing at night.',
    'mental-health': '15-year-old teen, parents concerned about mood changes, isolation, declining grades. Teen initially guarded.'
};

const SCENARIOS = [
    {
        id: 'acute-fever',
        title: 'Infant with Fever',
        description: '6-month-old with 2-day fever, first-time anxious parents',
        difficulty: 'beginner',
        type: 'acute',
        duration: '5 min'
    },
    {
        id: 'ear-infection',
        title: 'Ear Infection',
        description: 'Toddler with ear pain, recent URI, both parents present',
        difficulty: 'beginner',
        type: 'acute',
        duration: '4 min'
    },
    {
        id: 'well-child-4yo',
        title: 'Well Child (4 years)',
        description: 'Routine check, vaccine questions, developmental screening',
        difficulty: 'intermediate',
        type: 'well-child',
        duration: '6 min'
    },
    {
        id: 'asthma-followup',
        title: 'Asthma Follow-up',
        description: '8-year-old with poor asthma control, needs plan adjustment',
        difficulty: 'intermediate',
        type: 'acute',
        duration: '5 min'
    },
    {
        id: 'teen-depression',
        title: 'Teen Mental Health',
        description: 'Adolescent with mood changes, requires sensitive approach',
        difficulty: 'advanced',
        type: 'mental-health',
        duration: '8 min'
    },
    {
        id: 'missed-allergy',
        title: 'Hidden Allergy Mention',
        description: 'Parent casually mentions allergy that could affect treatment',
        difficulty: 'advanced',
        type: 'error',
        duration: '5 min'
    }
];

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initGenerateView();
    initPracticeView();
    initLibraryView();
    initSessionsView();
    initModals();

    // Initialize Lucide icons
    lucide.createIcons();
});

function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeToggle();

    document.getElementById('themeToggle').addEventListener('click', () => {
        state.theme = state.theme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', state.theme);
        localStorage.setItem('syrinx-theme', state.theme);
        updateThemeToggle();
    });
}

function updateThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    const icon = toggle.querySelector('i');
    const label = toggle.querySelector('.theme-toggle-label');

    if (state.theme === 'dark') {
        icon.setAttribute('data-lucide', 'sun');
        label.textContent = 'Light';
    } else {
        icon.setAttribute('data-lucide', 'moon');
        label.textContent = 'Dark';
    }
    lucide.createIcons();
}

// ============================================
// NAVIGATION
// ============================================

function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = link.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewId) {
    // Update nav
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.view === viewId);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === `view-${viewId}`);
    });

    state.currentView = viewId;
}

// ============================================
// GENERATE VIEW
// ============================================

function initGenerateView() {
    // Preset chips
    document.querySelectorAll('[data-preset]').forEach(chip => {
        chip.addEventListener('click', () => {
            const preset = chip.dataset.preset;
            document.getElementById('nlInput').value = PRESETS[preset] || '';
        });
    });

    // Import patient from Oread
    document.getElementById('importOread').addEventListener('click', () => {
        document.getElementById('oreadFileInput').click();
    });

    document.getElementById('oreadFileInput').addEventListener('change', handleOreadImport);

    document.getElementById('clearPatient').addEventListener('click', () => {
        state.importedPatient = null;
        document.getElementById('patientBadge').style.display = 'none';
    });

    // Generate form
    document.getElementById('generateForm').addEventListener('submit', handleGenerate);

    // Download and copy buttons
    document.getElementById('downloadBtn').addEventListener('click', () => {
        if (state.currentEncounter) {
            openModal('downloadModal');
        }
    });

    document.getElementById('copyTranscriptBtn').addEventListener('click', copyTranscript);
}

async function handleOreadImport(e) {
    const file = e.target.files[0];
    if (!file) return;

    try {
        const text = await file.text();
        const patient = JSON.parse(text);

        state.importedPatient = patient;

        // Update UI
        const name = patient.demographics?.given_names?.[0] || patient.patient?.name || 'Patient';
        document.getElementById('patientName').textContent = name;
        document.getElementById('patientBadge').style.display = 'inline-flex';

    } catch (err) {
        console.error('Failed to import patient:', err);
        alert('Failed to import patient file. Please ensure it\'s valid Oread JSON.');
    }

    // Reset file input
    e.target.value = '';
}

async function handleGenerate(e) {
    e.preventDefault();

    const nlInput = document.getElementById('nlInput').value.trim();
    if (!nlInput) {
        alert('Please describe the encounter');
        return;
    }

    const duration = document.getElementById('duration').value;
    const errorType = document.getElementById('errorType').value;

    // Show loading state
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('audioPlayer').style.display = 'none';
    document.getElementById('transcriptContainer').style.display = 'none';
    document.getElementById('objectivesContainer').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('loadingText').textContent = 'Generating script...';

    try {
        // Generate encounter
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: nlInput,
                duration: duration,
                error_type: errorType !== 'none' ? errorType : null,
                patient: state.importedPatient
            })
        });

        if (!response.ok) {
            throw new Error('Generation failed');
        }

        const encounter = await response.json();
        state.currentEncounter = encounter;

        // Generate audio
        document.getElementById('loadingText').textContent = 'Generating audio...';

        const audioResponse = await fetch('/api/generate/audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ encounter_id: encounter.metadata.id })
        });

        if (audioResponse.ok) {
            const audioData = await audioResponse.json();
            encounter.audio_url = audioData.audio_url;
        }

        // Show results
        document.getElementById('loadingState').style.display = 'none';
        displayEncounter(encounter);

    } catch (err) {
        console.error('Generation error:', err);
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('emptyState').style.display = 'block';
        alert('Failed to generate encounter. Please try again.');
    }
}

function displayEncounter(encounter) {
    // Show audio player
    document.getElementById('audioPlayer').style.display = 'block';

    // Initialize audio if URL available
    if (encounter.audio_url) {
        initAudioPlayer(encounter.audio_url);
    }

    // Show transcript
    document.getElementById('transcriptContainer').style.display = 'block';
    const transcriptContent = document.getElementById('transcriptContent');
    transcriptContent.innerHTML = '';

    encounter.script.forEach((line, index) => {
        const lineEl = document.createElement('div');
        lineEl.className = `transcript-line ${line.speaker}`;
        lineEl.dataset.index = index;

        lineEl.innerHTML = `
            <span class="transcript-speaker">${line.speaker}</span>
            <span class="transcript-text">${line.text}</span>
            ${line.direction ? `<span class="transcript-direction">[${line.direction}]</span>` : ''}
        `;

        transcriptContent.appendChild(lineEl);
    });

    // Show learning objectives
    if (encounter.metadata?.targets && encounter.metadata.targets.length > 0) {
        document.getElementById('objectivesContainer').style.display = 'block';
        const objectivesList = document.getElementById('objectivesList');
        objectivesList.innerHTML = '';

        encounter.metadata.targets.forEach(target => {
            const tag = document.createElement('span');
            tag.className = 'objective-tag';
            tag.textContent = target.replace(/_/g, ' ');
            objectivesList.appendChild(tag);
        });
    }
}

function initAudioPlayer(audioUrl) {
    // TODO: Implement full audio player with waveform
    // For now, use HTML5 audio
    const audioEl = document.createElement('audio');
    audioEl.src = audioUrl;
    audioEl.preload = 'metadata';

    const playPauseBtn = document.getElementById('playPauseBtn');
    const progressSlider = document.getElementById('progressSlider');
    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');
    const volumeSlider = document.getElementById('volumeSlider');

    audioEl.addEventListener('loadedmetadata', () => {
        totalTimeEl.textContent = formatTime(audioEl.duration);
    });

    audioEl.addEventListener('timeupdate', () => {
        currentTimeEl.textContent = formatTime(audioEl.currentTime);
        progressSlider.value = (audioEl.currentTime / audioEl.duration) * 100;
    });

    audioEl.addEventListener('ended', () => {
        state.isPlaying = false;
        playPauseBtn.querySelector('i').setAttribute('data-lucide', 'play');
        lucide.createIcons();
    });

    playPauseBtn.addEventListener('click', () => {
        if (state.isPlaying) {
            audioEl.pause();
            playPauseBtn.querySelector('i').setAttribute('data-lucide', 'play');
        } else {
            audioEl.play();
            playPauseBtn.querySelector('i').setAttribute('data-lucide', 'pause');
        }
        state.isPlaying = !state.isPlaying;
        lucide.createIcons();
    });

    progressSlider.addEventListener('input', () => {
        audioEl.currentTime = (progressSlider.value / 100) * audioEl.duration;
    });

    volumeSlider.addEventListener('input', () => {
        audioEl.volume = volumeSlider.value / 100;
    });

    // Store reference
    state.audioElement = audioEl;
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function copyTranscript() {
    if (!state.currentEncounter) return;

    const text = state.currentEncounter.script
        .map(line => `${line.speaker.toUpperCase()}: ${line.text}`)
        .join('\n');

    navigator.clipboard.writeText(text).then(() => {
        alert('Transcript copied to clipboard');
    });
}

// ============================================
// PRACTICE VIEW
// ============================================

function initPracticeView() {
    // Role selection
    document.querySelectorAll('.role-card').forEach(card => {
        card.addEventListener('click', () => {
            state.selectedRole = card.dataset.role;
            document.getElementById('roleSelection').style.display = 'none';
            document.getElementById('scenarioSelection').style.display = 'block';
            renderScenarios();
        });
    });

    // Back button
    document.getElementById('backToRoles').addEventListener('click', () => {
        document.getElementById('scenarioSelection').style.display = 'none';
        document.getElementById('roleSelection').style.display = 'block';
    });

    // Custom scenario
    document.getElementById('startCustomSession').addEventListener('click', () => {
        const description = document.getElementById('customScenario').value.trim();
        if (description) {
            startSession({ description, custom: true });
        }
    });

    // End session
    document.getElementById('endSession').addEventListener('click', endSession);

    // Voice input
    document.getElementById('voiceInputBtn').addEventListener('click', toggleVoiceInput);

    // Text input fallback
    document.getElementById('sendTextBtn').addEventListener('click', sendTextMessage);
    document.getElementById('textInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendTextMessage();
    });
}

function renderScenarios() {
    const grid = document.getElementById('scenarioGrid');
    grid.innerHTML = '';

    SCENARIOS.forEach(scenario => {
        const card = document.createElement('div');
        card.className = 'scenario-card';
        card.innerHTML = `
            <h4>${scenario.title}</h4>
            <p>${scenario.description}</p>
            <div class="scenario-badges">
                <span class="scenario-badge difficulty-${scenario.difficulty}">${scenario.difficulty}</span>
                <span class="scenario-badge">${scenario.type}</span>
                <span class="scenario-badge">${scenario.duration}</span>
            </div>
        `;
        card.addEventListener('click', () => startSession(scenario));
        grid.appendChild(card);
    });
}

async function startSession(scenario) {
    document.getElementById('scenarioSelection').style.display = 'none';
    document.getElementById('activeSession').style.display = 'block';

    // Set context
    const contextText = scenario.custom
        ? scenario.description
        : `${scenario.title}: ${scenario.description}`;
    document.getElementById('contextText').textContent = contextText;

    // Initialize session
    state.activeSession = {
        id: `session_${Date.now()}`,
        role: state.selectedRole,
        scenario: scenario,
        startTime: new Date(),
        messages: []
    };
    state.sessionStartTime = Date.now();
    state.sessionMessages = [];

    // Start timer
    updateSessionTimer();
    state.timerInterval = setInterval(updateSessionTimer, 1000);

    // Clear conversation
    document.getElementById('conversation').innerHTML = '';

    // Connect to WebSocket for interactive session
    await connectSession();
}

async function connectSession() {
    try {
        // Connect to WebSocket
        const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/session`;
        state.sessionSocket = new WebSocket(wsUrl);

        state.sessionSocket.onopen = () => {
            // Send session init
            state.sessionSocket.send(JSON.stringify({
                type: 'init',
                role: state.selectedRole,
                scenario: state.activeSession.scenario
            }));
        };

        state.sessionSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleSessionMessage(data);
        };

        state.sessionSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            addMessage('ai', 'Connection error. Using text-only mode.');
        };

        state.sessionSocket.onclose = () => {
            console.log('WebSocket closed');
        };

    } catch (err) {
        console.error('Failed to connect session:', err);
        // Fall back to REST API
        addMessage('ai', getInitialMessage());
    }
}

function getInitialMessage() {
    if (state.selectedRole === 'doctor') {
        return "Hello, I'm the parent. My child has been sick and I'm worried. What would you like to know?";
    } else {
        return "Hello, I'm Dr. Martinez. What brings you in today?";
    }
}

function handleSessionMessage(data) {
    switch (data.type) {
        case 'message':
            addMessage('ai', data.text);
            break;
        case 'audio':
            // Play AI audio response
            playAudioResponse(data.audio_url);
            break;
        case 'end':
            endSession();
            break;
    }
}

function addMessage(sender, text) {
    const conversation = document.getElementById('conversation');

    const messageEl = document.createElement('div');
    messageEl.className = `message ${sender}`;

    const icon = sender === 'ai'
        ? (state.selectedRole === 'doctor' ? 'user' : 'stethoscope')
        : (state.selectedRole === 'doctor' ? 'stethoscope' : 'user');

    const label = sender === 'ai'
        ? (state.selectedRole === 'doctor' ? 'Parent' : 'Doctor')
        : 'You';

    messageEl.innerHTML = `
        <div class="message-avatar">
            <i data-lucide="${icon}"></i>
        </div>
        <div class="message-content">
            <span class="message-sender">${label}</span>
            <div class="message-text">${text}</div>
        </div>
    `;

    conversation.appendChild(messageEl);
    conversation.scrollTop = conversation.scrollHeight;
    lucide.createIcons();

    // Store message
    state.sessionMessages.push({ sender, text, timestamp: Date.now() });
}

function showTypingIndicator() {
    const conversation = document.getElementById('conversation');
    const indicator = document.createElement('div');
    indicator.className = 'message ai';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = `
        <div class="message-avatar">
            <i data-lucide="${state.selectedRole === 'doctor' ? 'user' : 'stethoscope'}"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    conversation.appendChild(indicator);
    conversation.scrollTop = conversation.scrollHeight;
    lucide.createIcons();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

async function toggleVoiceInput() {
    const btn = document.getElementById('voiceInputBtn');

    if (state.isRecording) {
        stopVoiceInput();
        btn.classList.remove('recording');
        btn.querySelector('i').setAttribute('data-lucide', 'mic');
    } else {
        await startVoiceInput();
        btn.classList.add('recording');
        btn.querySelector('i').setAttribute('data-lucide', 'mic-off');
    }

    lucide.createIcons();
}

async function startVoiceInput() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Connect to Deepgram for real-time transcription
        const dgUrl = `wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true`;
        state.deepgramSocket = new WebSocket(dgUrl, ['token', window.DEEPGRAM_API_KEY || '']);

        state.deepgramSocket.onopen = () => {
            state.isRecording = true;

            // Create MediaRecorder to send audio chunks
            state.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            state.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && state.deepgramSocket?.readyState === WebSocket.OPEN) {
                    state.deepgramSocket.send(event.data);
                }
            };

            state.mediaRecorder.start(250); // Send chunks every 250ms
        };

        state.deepgramSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const transcript = data.channel?.alternatives?.[0]?.transcript;

            if (transcript && data.is_final) {
                // Send transcribed text as message
                sendMessage(transcript);
            }
        };

        state.deepgramSocket.onerror = (error) => {
            console.error('Deepgram error:', error);
            stopVoiceInput();
        };

    } catch (err) {
        console.error('Failed to start voice input:', err);
        alert('Microphone access required for voice input');
    }
}

function stopVoiceInput() {
    state.isRecording = false;

    if (state.mediaRecorder) {
        state.mediaRecorder.stop();
        state.mediaRecorder = null;
    }

    if (state.deepgramSocket) {
        state.deepgramSocket.close();
        state.deepgramSocket = null;
    }
}

function sendTextMessage() {
    const input = document.getElementById('textInput');
    const text = input.value.trim();

    if (text) {
        sendMessage(text);
        input.value = '';
    }
}

async function sendMessage(text) {
    addMessage('user', text);
    showTypingIndicator();

    if (state.sessionSocket?.readyState === WebSocket.OPEN) {
        state.sessionSocket.send(JSON.stringify({
            type: 'message',
            text: text
        }));
    } else {
        // Fall back to REST API
        try {
            const response = await fetch('/api/session/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.activeSession.id,
                    role: state.selectedRole,
                    message: text,
                    history: state.sessionMessages
                })
            });

            hideTypingIndicator();

            if (response.ok) {
                const data = await response.json();
                addMessage('ai', data.response);

                if (data.audio_url) {
                    playAudioResponse(data.audio_url);
                }
            }
        } catch (err) {
            hideTypingIndicator();
            console.error('Failed to send message:', err);
        }
    }
}

function playAudioResponse(audioUrl) {
    const audio = new Audio(audioUrl);
    audio.play();
}

function updateSessionTimer() {
    if (!state.sessionStartTime) return;

    const elapsed = Math.floor((Date.now() - state.sessionStartTime) / 1000);
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;

    document.getElementById('sessionTimer').textContent =
        `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function endSession() {
    // Stop timer
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }

    // Stop voice input
    if (state.isRecording) {
        stopVoiceInput();
    }

    // Close WebSocket
    if (state.sessionSocket) {
        state.sessionSocket.close();
        state.sessionSocket = null;
    }

    // Calculate duration
    const duration = Math.floor((Date.now() - state.sessionStartTime) / 1000);

    // Populate summary modal
    document.getElementById('summaryDuration').textContent = formatTime(duration);
    document.getElementById('summaryTurns').textContent = state.sessionMessages.length;

    const summaryTranscript = document.getElementById('summaryTranscript');
    summaryTranscript.innerHTML = state.sessionMessages.map(m => `
        <div class="message ${m.sender}">
            <strong>${m.sender === 'user' ? 'You' : 'AI'}:</strong> ${m.text}
        </div>
    `).join('');

    // Show summary modal
    openModal('sessionSummaryModal');

    // Set up save/discard handlers
    document.getElementById('saveSession').onclick = () => {
        saveSession(duration);
        closeModal('sessionSummaryModal');
        resetPracticeView();
    };

    document.getElementById('discardSession').onclick = () => {
        closeModal('sessionSummaryModal');
        resetPracticeView();
    };
}

function saveSession(duration) {
    const session = {
        ...state.activeSession,
        endTime: new Date(),
        duration: duration,
        messages: state.sessionMessages
    };

    state.savedSessions.unshift(session);
    localStorage.setItem('syrinx-sessions', JSON.stringify(state.savedSessions));

    updateSessionsList();
}

function resetPracticeView() {
    document.getElementById('activeSession').style.display = 'none';
    document.getElementById('roleSelection').style.display = 'block';
    document.getElementById('scenarioSelection').style.display = 'none';

    state.activeSession = null;
    state.sessionStartTime = null;
    state.sessionMessages = [];
}

// ============================================
// LIBRARY VIEW
// ============================================

function initLibraryView() {
    renderLibrary();

    // Search
    document.getElementById('librarySearch').addEventListener('input', (e) => {
        renderLibrary(e.target.value);
    });

    // Filters
    document.querySelectorAll('.filter-chips .chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            renderLibrary(null, chip.dataset.filter);
        });
    });
}

function renderLibrary(search = '', filter = 'all') {
    const grid = document.getElementById('libraryGrid');
    grid.innerHTML = '';

    let scenarios = SCENARIOS;

    // Apply filter
    if (filter !== 'all') {
        scenarios = scenarios.filter(s => s.type === filter);
    }

    // Apply search
    if (search) {
        const searchLower = search.toLowerCase();
        scenarios = scenarios.filter(s =>
            s.title.toLowerCase().includes(searchLower) ||
            s.description.toLowerCase().includes(searchLower)
        );
    }

    scenarios.forEach(scenario => {
        const card = document.createElement('div');
        card.className = 'scenario-card';
        card.innerHTML = `
            <h4>${scenario.title}</h4>
            <p>${scenario.description}</p>
            <div class="scenario-badges">
                <span class="scenario-badge difficulty-${scenario.difficulty}">${scenario.difficulty}</span>
                <span class="scenario-badge">${scenario.type}</span>
                <span class="scenario-badge">${scenario.duration}</span>
            </div>
        `;
        card.addEventListener('click', () => {
            switchView('practice');
            // Auto-select scenario
            state.selectedRole = 'doctor';
            document.getElementById('roleSelection').style.display = 'none';
            document.getElementById('scenarioSelection').style.display = 'block';
            renderScenarios();
        });
        grid.appendChild(card);
    });

    lucide.createIcons();
}

// ============================================
// SESSIONS VIEW
// ============================================

function initSessionsView() {
    updateSessionsList();

    document.getElementById('exportAllBtn').addEventListener('click', exportAllSessions);
}

function updateSessionsList() {
    const list = document.getElementById('sessionsList');
    const empty = document.getElementById('emptySessions');

    // Update stats
    document.getElementById('totalSessions').textContent = state.savedSessions.length;

    const totalSeconds = state.savedSessions.reduce((sum, s) => sum + (s.duration || 0), 0);
    document.getElementById('totalTime').textContent = formatTime(totalSeconds);

    if (state.savedSessions.length === 0) {
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';

    // Clear and rebuild list (keep empty state element)
    Array.from(list.children).forEach(child => {
        if (child !== empty) child.remove();
    });

    state.savedSessions.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item';

        const date = new Date(session.startTime);
        const dateStr = date.toLocaleDateString();
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        item.innerHTML = `
            <div>
                <h4>${session.scenario?.title || 'Custom Scenario'}</h4>
                <div class="session-meta">
                    <span><i data-lucide="calendar"></i>${dateStr} ${timeStr}</span>
                    <span><i data-lucide="clock"></i>${formatTime(session.duration)}</span>
                    <span><i data-lucide="message-square"></i>${session.messages?.length || 0} turns</span>
                </div>
            </div>
            <div>
                <button class="btn btn-secondary" data-id="${session.id}">
                    <i data-lucide="download"></i> Export
                </button>
            </div>
        `;

        item.querySelector('button').addEventListener('click', () => exportSession(session));
        list.insertBefore(item, empty);
    });

    lucide.createIcons();
}

function exportSession(session) {
    const data = JSON.stringify(session, null, 2);
    downloadFile(data, `syrinx_session_${session.id}.json`, 'application/json');
}

function exportAllSessions() {
    const data = JSON.stringify(state.savedSessions, null, 2);
    downloadFile(data, `syrinx_all_sessions_${Date.now()}.json`, 'application/json');
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ============================================
// MODALS
// ============================================

function initModals() {
    // Close on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    });

    // Close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.modal-overlay').classList.remove('active');
        });
    });

    // Export options
    document.querySelectorAll('.export-option').forEach(option => {
        option.addEventListener('click', () => {
            const format = option.dataset.format;
            exportEncounter(format);
            closeModal('downloadModal');
        });
    });
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

async function exportEncounter(format) {
    if (!state.currentEncounter) return;

    const encounterId = state.currentEncounter.metadata.id;

    switch (format) {
        case 'json':
            const jsonData = JSON.stringify(state.currentEncounter, null, 2);
            downloadFile(jsonData, `${encounterId}.json`, 'application/json');
            break;

        case 'markdown':
            const md = encounterToMarkdown(state.currentEncounter);
            downloadFile(md, `${encounterId}.md`, 'text/markdown');
            break;

        case 'audio':
            if (state.currentEncounter.audio_url) {
                window.open(state.currentEncounter.audio_url, '_blank');
            } else {
                alert('Audio not available for this encounter');
            }
            break;

        case 'fhir':
            try {
                const response = await fetch(`/api/export/${encounterId}?format=fhir`);
                if (response.ok) {
                    const fhir = await response.json();
                    downloadFile(JSON.stringify(fhir, null, 2), `${encounterId}_fhir.json`, 'application/json');
                }
            } catch (err) {
                alert('Failed to export FHIR format');
            }
            break;
    }
}

function encounterToMarkdown(encounter) {
    const m = encounter.metadata;
    let md = `# ${m.id}\n\n`;
    md += `**Type:** ${m.encounter_type}\n`;
    md += `**Patient:** ${m.patient_name}, ${m.patient_age}\n`;
    md += `**Chief Complaint:** ${m.chief_complaint}\n\n`;
    md += `## Transcript\n\n`;

    encounter.script.forEach(line => {
        md += `**${line.speaker.toUpperCase()}:** ${line.text}`;
        if (line.direction) md += ` _[${line.direction}]_`;
        md += '\n\n';
    });

    return md;
}
