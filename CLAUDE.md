# CLAUDE.md - Syrinx Development Context

**Last Updated:** December 2025

This file provides context for AI assistants working on Syrinx.

## Project Overview

**Syrinx** is a synthetic pediatric encounter generator that creates realistic doctor-patient dialogue scripts with optional error injection. It's designed for AI scribe training and medical education.

Named after the nymph who became pan pipes (voice/sound), Syrinx focuses on the audio and conversational aspects of medical encounters.

## Quick Start

```bash
cd /Users/dochobbs/Downloads/Consult/MedEd/synvoice
source venv/bin/activate

# Natural language generation
python syrinx.py generate --nl "acute visit, anxious mom, 6mo fever"

# With patient profile
python syrinx.py generate --patient patients/olivia_chen.json --chief-complaint "fever x2 days"

# With error injection and audio
python syrinx.py generate --patient patients/olivia_chen.json \
    --chief-complaint "ear infection" \
    --error clinical:missed-allergy \
    --audio
```

## Project Structure

```
synvoice/
├── syrinx.py              # Main CLI entry point
├── generate_audio.py      # ElevenLabs TTS audio synthesis
├── core/
│   ├── __init__.py
│   ├── input_parser.py    # Parse NL and structured inputs
│   ├── script_generator.py # Claude API script generation
│   ├── error_injector.py  # Error catalog and injection prompts
│   ├── encounter_builder.py # Build encounter JSON
│   ├── ground_truth.py    # Extract ground truth for evaluation
│   └── validator.py       # Encounter validation
├── patients/              # Patient profile JSONs
│   └── olivia_chen.json   # Example patient
├── encounters/            # Generated encounter JSONs
│   └── testbench/         # Test bench encounters
├── audio_output/          # Generated WAV files
├── venv/                  # Python virtual environment
├── requirements.txt
├── README.md
└── CLAUDE.md              # This file
```

## CLI Commands

### Generate Encounters

```bash
# Natural language (quickest)
python syrinx.py generate --nl "well-child, 12 month, vaccine hesitant mom"

# Structured CLI options
python syrinx.py generate \
    --encounter-type acute \
    --patient-age "6 months" \
    --chief-complaint "fever x2 days" \
    --parent-style "anxious first-time mom" \
    --duration medium \
    --error clinical:missed-allergy

# From patient profile
python syrinx.py generate \
    --patient patients/olivia_chen.json \
    --chief-complaint "ear infection" \
    --audio
```

### Other Commands

```bash
# List available error types
python syrinx.py errors list
python syrinx.py errors list --category clinical

# List parent personas
python syrinx.py personas

# List patient profiles
python syrinx.py patients list

# Extract ground truth from encounter
python syrinx.py extract encounters/syrinx_001.json --validate
```

## Error Injection System

Syrinx can inject three categories of errors for AI scribe training:

### Clinical Errors
| Error | Key | Description |
|-------|-----|-------------|
| Missed Allergy | `clinical:missed-allergy` | Doctor prescribes med patient is allergic to |
| Missed Diagnosis | `clinical:missed-diagnosis` | Doctor fails to recognize condition |
| Ignored Red Flag | `clinical:ignored-red-flag` | Doctor dismisses concerning symptom |
| Wrong Medication | `clinical:wrong-medication` | Incorrect med/dose for age/weight |

### Communication Errors
| Error | Key | Description |
|-------|-----|-------------|
| Interrupted | `communication:interrupted` | Doctor cuts off parent repeatedly |
| Used Jargon | `communication:jargon` | Medical terms without explanation |
| Dismissive | `communication:dismissive` | Minimizes parent concerns |
| Rushed | `communication:rushed` | Hurries through visit |

### Documentation Errors
| Error | Key | Description |
|-------|-----|-------------|
| Incomplete History | `documentation:incomplete-history` | Skips allergies/meds/PMH |
| No Follow-up | `documentation:no-follow-up` | No return precautions |
| Missing Med Rec | `documentation:missing-med-rec` | Doesn't review current meds |

## Encounter Types

| Type | Description |
|------|-------------|
| `acute` | Sick visit (fever, ear infection, respiratory) |
| `well-child` | Routine visit (screening, vaccines) |
| `mental-health` | Anxiety, ADHD, depression visits |
| `follow-up` | Med adjustments, treatment checks |

## Participant Configurations

| Config | Description |
|--------|-------------|
| `parent+infant` | Single parent, non-speaking baby (<2 years) |
| `parent+child` | Single parent, speaking child (4+ years) |
| `two-parents+child` | Mom and dad present |
| `parent+fussy-toddler` | With [baby crying] annotations |

## Duration Tiers

| Tier | Script Lines | Audio |
|------|--------------|-------|
| `short` | ~15-20 lines | ~2-3 min |
| `medium` | ~25-35 lines | ~4-5 min |
| `long` | ~40-50 lines | ~7-10 min |

## Output Format

Generated encounters are JSON:

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

### ElevenLabs TTS

```bash
# Generate audio from existing encounter
python generate_audio.py --single syrinx_001

# Batch process directory
python generate_audio.py --encounters-dir encounters/testbench --output-dir audio_output/testbench
```

### Voice Assignments

| Key | Voice | Character Use |
|-----|-------|---------------|
| `male-1` | Eric | Doctors, dads |
| `male-2` | Will | Teen boys |
| `female-1` | Matilda | Female doctors |
| `female-2` | Jessica | Moms, teen girls |
| `child-boy` | Liam | Young boys |
| `child-girl` | Laura | Young girls |
| `elderly-male` | Bill | Grandparents |
| `elderly-female` | Alice | Grandparents |

## Patient Profiles

Patient profiles in `patients/` contain reusable medical history:

```json
{
  "patient": {
    "name": "Olivia Chen",
    "dob": "2024-06-15",
    "age": "6 months",
    "sex": "female"
  },
  "family": {
    "mother": {
      "name": "Sarah Chen",
      "style": "anxious first-time mom"
    }
  },
  "medical_history": {
    "allergies": ["penicillin - rash after amoxicillin at 4 months"],
    "medications": [],
    "past_medical": ["born at 38 weeks", "jaundice treated with phototherapy"]
  }
}
```

## Ground Truth Extraction

Extract clinical ground truth from generated encounters for evaluation:

```bash
# Full extraction
python syrinx.py extract encounters/syrinx_001.json

# Minimal (faster)
python syrinx.py extract encounters/syrinx_001.json --minimal

# With validation report
python syrinx.py extract encounters/syrinx_001.json --validate
```

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Required for audio
ELEVEN_API_KEY=...
```

These are configured in `venv/bin/activate`.

## Dependencies

- Python 3.9+
- anthropic (Claude API for script generation)
- requests (HTTP client)
- numpy, scipy (Audio processing)

## Code Locations

| Component | File | Purpose |
|-----------|------|---------|
| CLI Entry | `syrinx.py` | All commands |
| Script Gen | `core/script_generator.py` | Claude API + prompts |
| Error Catalog | `core/error_injector.py` | Error definitions |
| Ground Truth | `core/ground_truth.py` | Extraction + validation |
| Audio | `generate_audio.py` | ElevenLabs synthesis |

## Metis Integration

Syrinx is part of the **MedEd Platform**, orchestrated by Metis.

### Platform Overview

| Project | Greek Name | Port | Purpose |
|---------|------------|------|---------|
| synpat | Oread | 8004 | Patient generation |
| synvoice | **Syrinx** | 8003 | Encounter scripts |
| synchart | Mneme | 8002 | EMR interface |
| echo | Echo | 8001 | AI tutor |
| metis | Metis | 3000 | Portal (planned) |

### Shared Models

Syrinx uses shared models generated by Metis:

```bash
# Regenerate shared models after schema changes
cd /Users/dochobbs/Downloads/Consult/MedEd/metis/shared
python sync.py --project syrinx
```

Generated models location: `models/_generated/context.py`

### Starting with Metis

```bash
# Start all MedEd services at once
cd /Users/dochobbs/Downloads/Consult/MedEd/metis/scripts
./start-all.sh

# Check status
./status.sh

# Stop all
./stop-all.sh
```

### Standalone Mode

Syrinx can run independently without Metis:

```bash
cd /Users/dochobbs/Downloads/Consult/MedEd/synvoice
source venv/bin/activate
python server.py
# API at http://localhost:8003
```

### Data Flow

```
Oread → [Patient JSON] → Syrinx → [Encounter Script] → Echo
                                                     → Mneme
```

**Shared Context:**
Syrinx encounters can be sent to Echo as `EncounterContext`:

```python
class EncounterContext(BaseModel):
    encounter_id: str
    patient: PatientContext  # Shared from Oread
    chief_complaint: str
    script: list[dict]       # Dialogue lines
    errors_injected: list[dict]
    source: Literal["syrinx"]
```

## Development Tasks

### Adding a New Error Type

1. Add to `core/error_injector.py` in appropriate category
2. Create `ErrorTemplate` with:
   - `injection_prompt` - Instructions for Claude
   - `detection_markers` - Keys for ground truth extraction
3. Test: `python syrinx.py generate --error category:new-error`

### Adding a New Encounter Type

1. Add to `EncounterType` enum in `core/input_parser.py`
2. Update `parse_encounter_type()` mapping
3. Update prompts in `core/script_generator.py`

### Creating Patient Profiles

1. Create JSON in `patients/` directory
2. Follow schema: patient, family, medical_history, social_history
3. Test: `python syrinx.py patients list`

## Known Issues

- Audio generation requires ElevenLabs API (paid)
- Long scripts may exceed API context limits
- Some error combinations don't produce realistic scripts

## Related Projects

| Project | Path | Integration |
|---------|------|-------------|
| **Metis** | `metis/` | Platform orchestration |
| **Oread** | `synpat/` | Patient data source |
| **Mneme** | `synchart/` | EMR for chart review |
| **Echo** | `echo/` | AI tutor for feedback |

## Code Style

- Python 3.9+
- Type hints required
- 2-space indentation
- Google-style docstrings
