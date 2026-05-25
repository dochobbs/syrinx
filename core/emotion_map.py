"""
Emotion taxonomy for Syrinx TTS voice modulation.

Maps emotion keywords (from script direction fields) to:
1. ElevenLabs voice parameters (stability, similarity_boost, style)
2. Benchmark labels (coarse sentiment + specific emotion)
"""

import os
import sys
from typing import Dict, Any, Optional


EMOTION_MAP: Dict[str, Dict[str, Any]] = {
  "anxious": {
    "coarse": "negative",
    "emotion": "anxiety",
    "voice": {"stability": 0.20, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True},
  },
  "frustrated": {
    "coarse": "negative",
    "emotion": "frustration",
    "voice": {"stability": 0.25, "similarity_boost": 0.70, "style": 0.40, "use_speaker_boost": True},
  },
  "reassuring": {
    "coarse": "positive",
    "emotion": "warmth",
    "voice": {"stability": 0.50, "similarity_boost": 0.85, "style": 0.20, "use_speaker_boost": True},
  },
  "calm": {
    "coarse": "neutral",
    "emotion": "calm",
    "voice": {"stability": 0.55, "similarity_boost": 0.85, "style": 0.10, "use_speaker_boost": True},
  },
  "concerned": {
    "coarse": "negative",
    "emotion": "concern",
    "voice": {"stability": 0.30, "similarity_boost": 0.80, "style": 0.25, "use_speaker_boost": True},
  },
  "dismissive": {
    "coarse": "negative",
    "emotion": "contempt",
    "voice": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.30, "use_speaker_boost": True},
  },
  "rushed": {
    "coarse": "negative",
    "emotion": "urgency",
    "voice": {"stability": 0.40, "similarity_boost": 0.70, "style": 0.35, "use_speaker_boost": True},
  },
  "warm": {
    "coarse": "positive",
    "emotion": "warmth",
    "voice": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.25, "use_speaker_boost": True},
  },
  "relieved": {
    "coarse": "positive",
    "emotion": "relief",
    "voice": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.20, "use_speaker_boost": True},
  },
  "urgent": {
    "coarse": "negative",
    "emotion": "urgency",
    "voice": {"stability": 0.25, "similarity_boost": 0.75, "style": 0.40, "use_speaker_boost": True},
  },
}

DEFAULT_EMOTION: Dict[str, Any] = {
  "coarse": "neutral",
  "emotion": "neutral",
  "voice": {"stability": 0.35, "similarity_boost": 0.80, "style": 0.15, "use_speaker_boost": True},
}

EMOTION_KEYWORDS = list(EMOTION_MAP.keys())


def lookup_emotion(direction: Optional[str]) -> Dict[str, Any]:
  """Look up emotion data from a script line's direction field.

  Extracts the first word from the direction string and matches it
  against EMOTION_MAP. Falls back to DEFAULT_EMOTION for unrecognized
  or missing directions.

  When a non-empty ``direction`` is supplied but the first word is not a
  recognized emotion keyword, a warning is printed to stderr so operators
  notice that sentiment-label fidelity for that line has degraded to the
  neutral default. Set ``SYRINX_EMOTION_WARN=0`` to silence (e.g. in tests).

  Args:
    direction: The direction field from a script line, e.g. "anxious, examining child"

  Returns:
    Dict with keys: coarse, emotion, voice
  """
  if not direction:
    return DEFAULT_EMOTION

  first_word = direction.strip().split(",")[0].strip().lower()
  if first_word in EMOTION_MAP:
    return EMOTION_MAP[first_word]

  # Unrecognized keyword — surface the degradation so it isn't silent.
  if os.environ.get("SYRINX_EMOTION_WARN", "1") != "0":
    print(
      f"WARN: emotion direction {first_word!r} not in EMOTION_MAP "
      f"(from direction={direction!r}); falling back to DEFAULT_EMOTION. "
      f"Known keywords: {', '.join(EMOTION_KEYWORDS)}",
      file=sys.stderr,
    )
  return DEFAULT_EMOTION
