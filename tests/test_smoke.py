"""Smoke tests for the Syrinx FastAPI server (W5.7).

Covers the endpoints that beta cares about most:
  * /health — liveness + config flags
  * /api/patients/import + GET round-trip + list
  * LRU eviction in _store_patient
  * /api/audio + /api/audio/cleanup lifecycle

Mocks ElevenLabs / Anthropic so nothing hits the network.
"""

import json
import time
from pathlib import Path
from typing import Dict

import pytest
from fastapi.testclient import TestClient

import server


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def client() -> TestClient:
  """A TestClient bound to the live FastAPI app."""
  return TestClient(server.app)


@pytest.fixture(autouse=True)
def _reset_state():
  """Clear in-memory stores between tests so order doesn't matter."""
  server.imported_patients.clear()
  server.active_sessions.clear()
  server.encounters_cache.clear()
  yield
  server.imported_patients.clear()
  server.active_sessions.clear()
  server.encounters_cache.clear()


@pytest.fixture
def audio_dir(tmp_path, monkeypatch) -> Path:
  """Redirect AUDIO_DIR to a temp dir so cleanup tests don't nuke real files."""
  tmp_audio = tmp_path / "audio_output"
  tmp_audio.mkdir()
  monkeypatch.setattr(server, "AUDIO_DIR", tmp_audio)
  return tmp_audio


def _oread_patient() -> Dict:
  """Minimal Oread-shaped patient payload for import tests."""
  return {
    "id": "test_patient_001",
    "demographics": {
      "given_names": ["Olivia"],
      "family_name": "Chen",
      "date_of_birth": "2024-06-15",
      "sex_at_birth": "female",
    },
    "allergy_list": [
      {
        "display_name": "penicillin",
        "reactions": [{"manifestation": "rash"}],
      }
    ],
    "medication_list": [
      {"display_name": "vitamin D drops"}
    ],
    "problem_list": [
      {"code": {"display": "Eczema"}}
    ],
  }


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #

def test_health_returns_healthy(client):
  resp = client.get("/health")
  assert resp.status_code == 200
  body = resp.json()
  assert body["status"] == "healthy"
  assert body["service"] == "syrinx"
  # Config flags must be present (booleans) and patient count exposed.
  assert "anthropic_configured" in body
  assert "eleven_configured" in body
  assert body["imported_patients"] == 0


# --------------------------------------------------------------------------- #
# /api/patients/import + GET + list
# --------------------------------------------------------------------------- #

def test_import_patient_returns_success(client):
  resp = client.post("/api/patients/import", json=_oread_patient())
  assert resp.status_code == 200, resp.text
  body = resp.json()
  assert body["success"] is True
  assert body["patient_id"] == "test_patient_001"
  assert body["name"] == "Olivia"
  # Sanity: age string is non-empty (computed from DOB).
  assert isinstance(body["age"], str) and body["age"]


def test_import_then_get_round_trip(client):
  payload = _oread_patient()
  client.post("/api/patients/import", json=payload).raise_for_status()

  resp = client.get("/api/patients/test_patient_001")
  assert resp.status_code == 200
  body = resp.json()
  assert body["id"] == "test_patient_001"
  assert body["profile"]["name"] == "Olivia"
  assert "penicillin - rash" in body["profile"]["allergies"][0]
  assert body["profile"]["medications"] == ["vitamin D drops"]
  assert body["profile"]["chronic_conditions"] == ["Eczema"]
  # Raw payload preserved verbatim.
  assert body["raw"] == payload


def test_get_unknown_patient_404(client):
  resp = client.get("/api/patients/no_such_id")
  assert resp.status_code == 404


def test_list_patients(client):
  client.post("/api/patients/import", json=_oread_patient()).raise_for_status()
  resp = client.get("/api/patients")
  assert resp.status_code == 200
  body = resp.json()
  assert body["count"] == 1
  assert body["patients"][0]["id"] == "test_patient_001"


# --------------------------------------------------------------------------- #
# LRU eviction
# --------------------------------------------------------------------------- #

def test_lru_evicts_oldest_when_over_capacity(monkeypatch):
  """SYRINX_MAX_PATIENTS=3 (set in conftest); insert 4 and oldest must drop."""
  # MAX_IMPORTED_PATIENTS is read at import time, so override directly for the
  # test — re-importing server.py would re-run the startup hook side effects.
  monkeypatch.setattr(server, "MAX_IMPORTED_PATIENTS", 3)

  for i in range(4):
    server._store_patient(f"p{i}", {"id": f"p{i}", "profile": {"name": f"P{i}", "age": "5"}, "raw": {}, "imported_at": "now"})

  assert len(server.imported_patients) == 3
  # p0 was inserted first → should have been evicted
  assert "p0" not in server.imported_patients
  assert list(server.imported_patients.keys()) == ["p1", "p2", "p3"]


def test_lru_refresh_moves_to_end(monkeypatch):
  """Re-storing an existing patient must refresh it (move to MRU position)."""
  monkeypatch.setattr(server, "MAX_IMPORTED_PATIENTS", 3)

  for i in range(3):
    server._store_patient(f"p{i}", {"id": f"p{i}", "profile": {"name": f"P{i}", "age": "5"}, "raw": {}, "imported_at": "now"})

  # Touch p0 — now p1 is the oldest.
  server._store_patient("p0", {"id": "p0", "profile": {"name": "P0-updated", "age": "5"}, "raw": {}, "imported_at": "later"})
  # Add a new one to force an eviction.
  server._store_patient("p3", {"id": "p3", "profile": {"name": "P3", "age": "5"}, "raw": {}, "imported_at": "now"})

  assert "p1" not in server.imported_patients
  assert server.imported_patients["p0"]["profile"]["name"] == "P0-updated"


# --------------------------------------------------------------------------- #
# /api/audio + /api/audio/cleanup
# --------------------------------------------------------------------------- #

def test_audio_list_empty(client, audio_dir):
  resp = client.get("/api/audio")
  assert resp.status_code == 200
  body = resp.json()
  assert body["count"] == 0
  assert body["total_bytes"] == 0
  assert body["files"] == []


def test_audio_list_reports_files(client, audio_dir):
  (audio_dir / "enc_001.wav").write_bytes(b"RIFFfake-wav-data")
  (audio_dir / "enc_002.wav").write_bytes(b"RIFFfake-wav-data-longer-too")

  resp = client.get("/api/audio")
  body = resp.json()
  assert body["count"] == 2
  assert body["total_bytes"] == sum(p.stat().st_size for p in audio_dir.glob("*.wav"))
  names = {f["filename"] for f in body["files"]}
  assert names == {"enc_001.wav", "enc_002.wav"}


def test_audio_cleanup_days_zero_deletes_everything(client, audio_dir):
  (audio_dir / "old.wav").write_bytes(b"old")
  (audio_dir / "new.wav").write_bytes(b"new")
  assert len(list(audio_dir.glob("*.wav"))) == 2

  resp = client.post("/api/audio/cleanup?days=0")
  assert resp.status_code == 200
  body = resp.json()
  assert body["deleted_count"] == 2
  assert set(body["files"]) == {"old.wav", "new.wav"}
  assert list(audio_dir.glob("*.wav")) == []


def test_audio_cleanup_preserves_recent(client, audio_dir):
  """days=30 should NOT delete a file just written."""
  (audio_dir / "fresh.wav").write_bytes(b"fresh")
  resp = client.post("/api/audio/cleanup?days=30")
  assert resp.status_code == 200
  body = resp.json()
  assert body["deleted_count"] == 0
  assert (audio_dir / "fresh.wav").exists()


# --------------------------------------------------------------------------- #
# JSON parser regression (W5.8)
# --------------------------------------------------------------------------- #

def test_json_parser_ignores_trailing_prose():
  """Synthetic regression test for the greedy-regex bug fixed in W5.8."""
  from core.script_generator import ScriptGenerator
  sg = ScriptGenerator.__new__(ScriptGenerator)  # bypass __init__/API key
  out = sg._parse_json_response('{"script": [{"speaker": "doctor", "text": "hi"}]} and some trailing}')
  assert out == {"script": [{"speaker": "doctor", "text": "hi"}]}


def test_json_parser_handles_markdown_fence():
  from core.script_generator import ScriptGenerator
  sg = ScriptGenerator.__new__(ScriptGenerator)
  raw = '```json\n{"a": 1, "b": [1,2,3]}\n```'
  assert sg._parse_json_response(raw) == {"a": 1, "b": [1, 2, 3]}


# --------------------------------------------------------------------------- #
# Emotion fallback warning (W5.10)
# --------------------------------------------------------------------------- #

def test_emotion_warn_emits_stderr(monkeypatch, capsys):
  """Unrecognized direction keyword should warn (unless silenced)."""
  monkeypatch.setenv("SYRINX_EMOTION_WARN", "1")
  from core.emotion_map import lookup_emotion, DEFAULT_EMOTION
  result = lookup_emotion("flabbergasted, waving arms")
  assert result == DEFAULT_EMOTION
  err = capsys.readouterr().err
  assert "flabbergasted" in err
  assert "DEFAULT_EMOTION" in err


def test_emotion_warn_silenced_by_env(monkeypatch, capsys):
  monkeypatch.setenv("SYRINX_EMOTION_WARN", "0")
  from core.emotion_map import lookup_emotion
  lookup_emotion("flabbergasted")
  assert capsys.readouterr().err == ""
