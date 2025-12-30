# Syrinx Project Worklist

## Priority 1 - Current Sprint

### Echo Integration
- [ ] Start Echo server on port 8001
- [ ] Test Echo widget chat functionality end-to-end
- [ ] Add encounter transcript to Echo context for tutoring
- [ ] Implement Deepgram voice input in Echo widget
- [ ] Connect ElevenLabs for Echo voice responses

### Web App Polish
- [ ] Add health check endpoint to server.py
- [ ] Test all Library scenarios load correctly
- [ ] Verify Practice mode WebSocket connection
- [ ] Test session recording and localStorage persistence

## Priority 2 - Enhancements

### Generation Features
- [ ] Test natural language encounter generation
- [ ] Verify error injection works (clinical errors)
- [ ] Test Oread patient import functionality
- [ ] Add audio generation with ElevenLabs

### Practice Mode
- [ ] Test doctor role (AI plays parent)
- [ ] Test parent role (AI plays doctor)
- [ ] Verify Deepgram STT for voice input
- [ ] Test session save/export functionality

### Export Features
- [ ] Test JSON export
- [ ] Test Markdown export
- [ ] Test FHIR R4 export
- [ ] Test audio WAV export

## Priority 3 - Future

### Learning Features
- [ ] Add learning objectives display
- [ ] Implement post-session feedback
- [ ] Add ground truth comparison mode
- [ ] Performance metrics tracking

### Advanced
- [ ] Scenario library with categories
- [ ] Difficulty filtering
- [ ] Session history analysis
- [ ] Mobile responsive testing

## Completed (2025-12-30)
- [x] Dynamic scenario loading from API (29 scenarios)
- [x] Echo widget integration (HTML, CSS, JS)
- [x] /api/scenarios endpoint
- [x] Echo context passing (source, encounter, view, role)
