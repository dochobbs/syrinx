# Syrinx

Synthetic Pediatric Encounter Generator for AI scribe training and medical education.

Part of the **MedEd Platform** - see `metis/` for platform orchestration.

## Overview

Syrinx generates realistic doctor-patient encounter scripts with optional error injection. It uses Claude API for script generation and ElevenLabs for text-to-speech audio synthesis.

**Port:** 8003

## Features

- **Natural Language Input**: Describe encounters in plain English
- **Structured CLI**: Fine-grained control over encounter parameters
- **Patient Profiles**: Import reusable patient JSON files with medical history
- **Error Injection**: Inject clinical, communication, or documentation errors
- **Multiple Encounter Types**: Acute, well-child, mental-health, follow-up
- **Duration Control**: Short (~15-20 lines), medium (~25-35), long (~40-50)
- **Audio Generation**: ElevenLabs TTS with 8 distinct voices

## Installation

```bash
cd synvoice
python3 -m venv venv
source venv/bin/activate
pip install anthropic requests numpy scipy
```

API keys are configured in `venv/bin/activate`:
- `ANTHROPIC_API_KEY` - Claude API
- `ELEVEN_API_KEY` - ElevenLabs TTS

## Quick Start

```bash
source venv/bin/activate

# Natural language generation
python syrinx.py generate --nl "acute visit, anxious mom, 6mo fever"

# With patient profile
python syrinx.py generate --patient patients/olivia_chen.json --chief-complaint "fever x2 days"

# With error injection and audio
python syrinx.py generate --patient patients/olivia_chen.json \
    --chief-complaint "ear infection" \
    --error clinical:missed-allergy \
    --duration short \
    --audio
```

## CLI Reference

### Generate Command

```bash
python syrinx.py generate [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--nl` | Natural language description |
| `--patient` | Path to patient profile JSON |
| `--encounter-type`, `-t` | acute, well-child, mental-health, follow-up |
| `--patient-age` | e.g., "6 months", "4 years" |
| `--patient-name` | Patient name |
| `--patient-sex` | male/female |
| `--chief-complaint`, `-c` | Reason for visit |
| `--parent-style` | Parent communication style |
| `--doctor-style` | Doctor communication style |
| `--doctor-gender` | male/female (for voice selection) |
| `--participants`, `-p` | Participant configuration |
| `--error`, `-e` | Error to inject (repeatable) |
| `--duration`, `-d` | short, medium, long |
| `--output-dir`, `-o` | Output directory (default: encounters) |
| `--audio`, `-a` | Also generate audio |
| `--audio-dir` | Audio output directory |

### Other Commands

```bash
# List available error types
python syrinx.py errors list

# List parent personas
python syrinx.py personas

# List patient profiles
python syrinx.py patients list
```

## Error Types

### Clinical Errors
| Error | Description |
|-------|-------------|
| `clinical:missed-allergy` | Doctor prescribes medication patient is allergic to |
| `clinical:missed-diagnosis` | Doctor misses the correct diagnosis |
| `clinical:ignored-red-flag` | Doctor dismisses concerning symptoms |
| `clinical:wrong-medication` | Incorrect medication or dose for age |

### Communication Errors
| Error | Description |
|-------|-------------|
| `communication:interrupted` | Doctor cuts off parent repeatedly |
| `communication:jargon` | Uses medical terms without explanation |
| `communication:dismissive` | Minimizes parent concerns |
| `communication:rushed` | Hurries through visit |

### Documentation Errors
| Error | Description |
|-------|-------------|
| `documentation:incomplete-history` | Skips allergies/meds/PMH |
| `documentation:no-follow-up` | No return precautions given |
| `documentation:missing-med-rec` | Doesn't review current medications |

## Participant Configurations

| Config | Description |
|--------|-------------|
| `parent+infant` | Single parent, non-speaking baby (<2 years) |
| `parent+child` | Single parent, speaking child (4+ years) |
| `two-parents+child` | Mom and dad present |
| `parent+fussy-toddler` | With [baby crying] annotations |

## Patient Profiles

Patient profiles are JSON files containing medical history:

```json
{
  "patient": {
    "name": "Olivia Chen",
    "dob": "2024-06-15",
    "age": "6 months",
    "sex": "female",
    "preferred_name": "Livvy"
  },
  "family": {
    "mother": {
      "name": "Sarah Chen",
      "style": "anxious first-time mom, asks many questions"
    },
    "father": {
      "name": "Mike Chen",
      "style": "calm, supportive, lets mom take lead"
    }
  },
  "medical_history": {
    "allergies": ["penicillin - developed rash after amoxicillin at 4 months"],
    "medications": [],
    "chronic_conditions": [],
    "past_medical": [
      "born at 38 weeks via uncomplicated vaginal delivery",
      "jaundice treated with phototherapy for 2 days"
    ],
    "immunizations": "up to date for age",
    "last_well_check": "4 month visit - growing well"
  },
  "social_history": {
    "lives_with": "both parents in apartment",
    "daycare": false,
    "siblings": [],
    "pets": ["dog named Max"]
  }
}
```

## Output Format

Generated encounters are saved as JSON:

```json
{
  "metadata": {
    "id": "syrinx_001",
    "encounter_type": "acute",
    "patient_age": "6 months",
    "patient_name": "Olivia Chen",
    "chief_complaint": "fever x2 days",
    "targets": ["detect_missed-allergy"],
    "duration_tier": "short"
  },
  "speakers": {
    "parent": {"voice": "female-2", "style": "anxious first-time mom"},
    "doctor": {"voice": "female-1", "style": "warm, thorough"}
  },
  "script": [
    {"speaker": "doctor", "text": "Good morning...", "direction": "warm"},
    {"speaker": "parent", "text": "Hi, she's had...", "direction": "anxious"}
  ],
  "_generated": {
    "tool": "syrinx",
    "timestamp": "2025-12-27T09:52:21.765591",
    "errors_injected": [{"category": "clinical", "type": "missed-allergy"}]
  }
}
```

## Audio Generation

Generate audio from existing encounter JSON:

```bash
# Single encounter
python generate_audio.py --single syrinx_001

# All encounters in a directory
python generate_audio.py --encounters-dir encounters/testbench --output-dir audio_output/testbench
```

### Voice Assignments

| Voice Key | Character | Use Case |
|-----------|-----------|----------|
| male-1 | Eric | Doctors, dads |
| male-2 | Will | Teen boys |
| female-1 | Matilda | Doctors |
| female-2 | Jessica | Moms, teen girls |
| child-boy | Liam | Young boys |
| child-girl | Laura | Young girls |
| elderly-male | Bill | Grandparents |
| elderly-female | Alice | Grandparents |

## Project Structure

```
synvoice/
├── syrinx.py              # Main CLI entry point
├── generate_audio.py      # ElevenLabs TTS generator
├── core/
│   ├── __init__.py
│   ├── input_parser.py    # Parse NL and structured inputs
│   ├── script_generator.py # Claude API script generation
│   ├── error_injector.py  # Error catalog and injection
│   └── encounter_builder.py # Build encounter JSON
├── patients/              # Patient profile JSONs
├── encounters/            # Generated encounter JSONs
│   └── testbench/         # Test bench encounters
├── audio_output/          # Generated WAV files
│   └── testbench/         # Test bench audio
└── venv/                  # Python virtual environment
```

## Examples

### Acute Visit with Missed Allergy

```bash
python syrinx.py generate \
    --patient patients/olivia_chen.json \
    --chief-complaint "ear infection" \
    --error clinical:missed-allergy \
    --audio
```

The doctor initially prescribes a penicillin-based antibiotic, and the parent catches the error based on the allergy in the patient profile.

### Well-Child with Vaccine Hesitant Parent

```bash
python syrinx.py generate \
    --nl "well-child visit, 12 month old, vaccine hesitant mom" \
    --duration medium
```

### Mental Health with Family Conflict

```bash
python syrinx.py generate \
    --nl "mental health visit, 14yo with anxiety, parents disagree on treatment" \
    --duration long
```

## Dependencies

- Python 3.9+
- anthropic (Claude API)
- requests (HTTP client)
- numpy, scipy (Audio processing)

## License

Internal use only - Medical education and AI scribe training.
