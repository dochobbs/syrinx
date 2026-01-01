# Changelog - 2026-01-01

## Commits
- `bc105f3`: chore: Archive session 2025-12-30

## Uncommitted Features (Ready to Commit)

### Echo Widget Integration
- Floating chat widget for Echo clinical tutor
- Purple gradient FAB button
- Chat panel with header, messages, input
- Voice toggle and mic button
- Context passing to Echo API

### Dynamic Scenario Loading
- `/api/scenarios` endpoint
- Loads 29 encounters from JSON files
- Replaced hardcoded 6-scenario array

## Files with Uncommitted Changes
| File | Changes |
|------|---------|
| server.py | +59 lines (API endpoint) |
| web/app.js | +225 lines (Echo + dynamic loading) |
| web/styles.css | +303 lines (Echo styles) |
| web/index.html | +46 lines (Echo HTML) |
