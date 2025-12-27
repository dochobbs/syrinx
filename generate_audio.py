#!/usr/bin/env python3
"""
SynVoice - Pediatric Encounter Audio Generator
Uses ElevenLabs TTS API with direct PCM output (no MP3 decoding required).

Designed for Python 3.14+ compatibility by avoiding audioop/pydub dependencies.
"""

import os
import json
import numpy as np
from pathlib import Path
import argparse
from scipy.io.wavfile import write as wav_write
import time
import requests

# Configuration
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
SAMPLE_RATE = 24000
API_BASE = "https://api.elevenlabs.io/v1"

# Voice settings for natural sound
VOICE_SETTINGS = {
    "stability": 0.35,
    "similarity_boost": 0.80,
    "style": 0.15,
    "use_speaker_boost": True,
}

# Voice ID mapping (encounter voice type -> ElevenLabs voice ID)
VOICE_ID_MAP = {
    "male-1": "cjVigY5qzO86Huf0OWal",      # Eric - Smooth, Trustworthy (doctors/dads)
    "male-2": "bIHbv24MWmeRgasZH58o",      # Will - Relaxed Optimist (teen boys)
    "female-1": "XrExE9yKIg1WjnnlVkGX",    # Matilda - Knowledgeable, Professional (doctors/moms)
    "female-2": "cgSgspJ2msm6clMCkdW9",    # Jessica - Playful, Bright, Warm (moms/teen girls)
    "child-boy": "TX3LPaxmHKxFdv7VOQHJ",   # Liam - Energetic, young male
    "child-girl": "FGY2WhTYpPnrIDTdsKH5",  # Laura - Enthusiast, young female
    "elderly-male": "pqHfZKP75CvOlQylNhV4",    # Bill - Wise, Mature
    "elderly-female": "Xb7hH8MSUJpSbSDYk0k2",  # Alice - Clear, Engaging
}

# Default voice ID (Jessica)
DEFAULT_VOICE_ID = "cgSgspJ2msm6clMCkdW9"


def check_api_key():
    """Verify API key is set."""
    if not ELEVEN_API_KEY:
        print("Error: ELEVEN_API_KEY environment variable not set")
        print("Run: export ELEVEN_API_KEY='your-key-here'")
        return False
    return True


def get_voice_id(voice_key: str) -> str:
    """Get ElevenLabs voice ID from voice key."""
    return VOICE_ID_MAP.get(voice_key, DEFAULT_VOICE_ID)


def generate_speech_pcm(text: str, voice_id: str) -> bytes:
    """
    Generate speech using ElevenLabs API with PCM output.
    Returns raw 16-bit signed little-endian PCM data at 24kHz.
    """
    url = f"{API_BASE}/text-to-speech/{voice_id}?output_format=pcm_24000"

    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_API_KEY,
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": VOICE_SETTINGS,
    }

    response = requests.post(url, json=data, headers=headers, timeout=30)

    if response.status_code == 401:
        raise Exception("Invalid API key")
    elif response.status_code == 422:
        raise Exception(f"Validation error: {response.text}")
    elif response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text}")

    return response.content


def pcm_to_numpy(pcm_data: bytes) -> np.ndarray:
    """Convert raw PCM bytes to numpy float32 array."""
    if len(pcm_data) % 2 != 0:
        pcm_data = pcm_data + b'\x00'
    audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32) / 32768.0
    return audio_float


def generate_silence(duration_ms: int) -> np.ndarray:
    """Generate silence of specified duration in milliseconds."""
    num_samples = int(SAMPLE_RATE * duration_ms / 1000)
    return np.zeros(num_samples, dtype=np.float32)


def process_encounter(encounter_path: str, output_dir: str, verbose: bool = True) -> str:
    """
    Process a single encounter JSON and generate audio.
    Returns path to generated audio file.
    """
    with open(encounter_path, 'r') as f:
        encounter = json.load(f)

    metadata = encounter['metadata']
    speakers = encounter['speakers']
    script = encounter['script']

    encounter_id = metadata['id']
    patient_name = metadata['patient_name']
    chief_complaint = metadata['chief_complaint']

    if verbose:
        print(f"\n{'='*60}")
        print(f"Encounter {encounter_id}: {patient_name}")
        print(f"Chief Complaint: {chief_complaint}")
        print(f"Lines: {len(script)}")
        print('='*60)

    audio_segments = []

    for i, line in enumerate(script):
        speaker_key = line['speaker']
        text = line['text']

        speaker_info = speakers.get(speaker_key, {})
        voice_key = speaker_info.get('voice', 'female-1')
        voice_id = get_voice_id(voice_key)

        if verbose:
            truncated = text[:50] + "..." if len(text) > 50 else text
            print(f"  [{i+1}/{len(script)}] {speaker_key}: {truncated}")

        try:
            pcm_data = generate_speech_pcm(text, voice_id)
            audio = pcm_to_numpy(pcm_data)
            audio_segments.append(audio)

            pause_ms = 500 if "?" in text else 350
            audio_segments.append(generate_silence(pause_ms))

        except Exception as e:
            print(f"    Warning: Failed line {i+1}: {e}")
            audio_segments.append(generate_silence(2000))

    full_audio = np.concatenate(audio_segments)

    max_val = np.max(np.abs(full_audio))
    if max_val > 0:
        full_audio = full_audio / max_val * 0.95

    audio_int16 = (full_audio * 32767).astype(np.int16)

    encounter_type = metadata.get('encounter_type', 'visit')
    safe_name = patient_name.lower().replace(' ', '_')
    output_filename = f"{encounter_id}_{encounter_type}_{safe_name}.wav"
    output_path = os.path.join(output_dir, output_filename)

    wav_write(output_path, SAMPLE_RATE, audio_int16)

    duration_sec = len(full_audio) / SAMPLE_RATE

    if verbose:
        print(f"\n  Output: {output_filename}")
        print(f"  Duration: {duration_sec:.1f}s ({duration_sec/60:.1f} min)")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Generate pediatric encounter audio using ElevenLabs TTS'
    )
    parser.add_argument(
        '--encounters-dir', '-e',
        default='encounters',
        help='Directory containing encounter JSON files (default: encounters)'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='audio_output',
        help='Directory to save generated audio (default: audio_output)'
    )
    parser.add_argument(
        '--single', '-s',
        help='Process only a single encounter (by filename or ID)'
    )
    parser.add_argument(
        '--start-from', '-f',
        type=int,
        help='Start from encounter number (e.g., 5 to start from encounter 05)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress verbose output'
    )

    args = parser.parse_args()

    if not check_api_key():
        return 1

    os.makedirs(args.output_dir, exist_ok=True)

    encounters_path = Path(args.encounters_dir)
    if not encounters_path.exists():
        print(f"Error: Encounters directory not found: {args.encounters_dir}")
        return 1

    encounter_files = sorted(encounters_path.glob('*.json'))

    if not encounter_files:
        print(f"Error: No JSON files found in {args.encounters_dir}")
        return 1

    if args.single:
        encounter_files = [f for f in encounter_files
                         if args.single in f.name or args.single in f.stem]
        if not encounter_files:
            print(f"Error: No encounter matching '{args.single}' found")
            return 1

    if args.start_from:
        start_id = f"{args.start_from:02d}"
        encounter_files = [f for f in encounter_files if f.name >= f"{start_id}_"]

    print(f"\nSynVoice - ElevenLabs TTS Audio Generator")
    print(f"=========================================")
    print(f"Encounters: {len(encounter_files)}")
    print(f"Output: {args.output_dir}")

    start_time = time.time()
    generated = []

    for i, encounter_file in enumerate(encounter_files):
        print(f"\n[{i+1}/{len(encounter_files)}] {encounter_file.name}")
        try:
            output_path = process_encounter(
                str(encounter_file),
                args.output_dir,
                verbose=not args.quiet
            )
            generated.append(output_path)
        except Exception as e:
            print(f"Error: {e}")
            continue

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"{'='*60}")
    print(f"Generated: {len(generated)}/{len(encounter_files)}")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")

    if generated:
        print(f"\nFiles:")
        for path in generated:
            print(f"  - {os.path.basename(path)}")

    return 0


if __name__ == '__main__':
    exit(main())
