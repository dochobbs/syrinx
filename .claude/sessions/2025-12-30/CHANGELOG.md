# Changelog - 2025-12-30

## Features

### Dynamic Scenario Loading
- Replaced hardcoded 6 scenarios with API-driven loading
- Added `/api/scenarios` endpoint to server.py
- Loads all 29 encounters from encounters/ directory
- Extracts metadata: title, description, type, difficulty, duration

### Echo Widget Integration
- Added floating chat widget for Echo clinical tutor
- Purple gradient FAB button (bottom-right)
- Chat panel with header, messages, input area
- Voice toggle and mic button for voice input
- Context passing to Echo API (source, encounter, view, role)

## Files Changed

| File | Changes |
|------|---------|
| `server.py` | Added /api/scenarios endpoint (~50 lines) |
| `web/app.js` | Dynamic loading + Echo widget JS (~200 lines) |
| `web/styles.css` | Echo widget styles (~300 lines) |
| `web/index.html` | Echo widget HTML structure |

## Previous Commits (Reference)
- `4db575c`: Add violet Mic icon favicon and CLAUDE.md
- `9881e2e`: Add Syrinx Web Application
- `1c11b21`: Add error validation, target inference, ground truth
- `17f0f95`: Initial Syrinx implementation
