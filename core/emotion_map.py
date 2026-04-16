"""
Emotion taxonomy for Syrinx TTS voice modulation.

Maps emotion keywords (from script direction fields) to:
1. ElevenLabs voice parameters (stability, similarity_boost, style)
2. Benchmark labels (coarse sentiment + specific emotion)
"""

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

  Args:
    direction: The direction field from a script line, e.g. "anxious, examining child"

  Returns:
    Dict with keys: coarse, emotion, voice
  """
  if not direction:
    return DEFAULT_EMOTION

  first_word = direction.strip().split(",")[0].strip().lower()
  return EMOTION_MAP.get(first_word, DEFAULT_EMOTION)
