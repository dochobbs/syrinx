"""Shared pytest fixtures + sys.path / env setup for Syrinx tests.

We import server.py from the repo root, so tests run with:
    venv/bin/python -m pytest tests/ -v

ANTHROPIC_API_KEY is forced to a dummy value before any import so the
startup validator can't sys.exit(1) on a missing key, and so individual
tests that monkeypatch anthropic.Anthropic don't blow up at construction
time.
"""

import os
import sys
from pathlib import Path

# Force test-safe env BEFORE importing server, which has an on_event
# startup hook that exits the process if ANTHROPIC_API_KEY is missing.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("SYRINX_EMOTION_WARN", "0")

# Cap the LRU small so eviction tests don't have to import 500 patients.
os.environ.setdefault("SYRINX_MAX_PATIENTS", "3")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
