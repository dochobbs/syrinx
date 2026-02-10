# Ground Truth Extraction Guide

**Module:** `core/ground_truth.py`

## Overview

Syrinx can extract structured clinical ground truth from generated encounter scripts. This is used for AI scribe training -- comparing scribe output against the known-correct clinical data.

## How It Works

1. Takes a generated encounter JSON (from `encounters/`)
2. Sends the script transcript to Claude with a structured extraction prompt
3. Returns a JSON object with all clinical data points
4. Optionally validates the extraction against the original encounter metadata

## Usage

### CLI

```bash
# Full extraction
python syrinx.py extract encounters/syrinx_001.json

# Minimal (faster, less detail)
python syrinx.py extract encounters/syrinx_001.json --minimal

# With validation report
python syrinx.py extract encounters/syrinx_001.json --validate
```

### Programmatic

```python
from core.ground_truth import extract_ground_truth, validate_extraction

# Extract
result = extract_ground_truth("encounters/syrinx_001.json")

# Validate against metadata
report = validate_extraction(result, encounter_metadata)
```

## Extracted Fields

The extraction returns a JSON structure with:

| Section | Fields |
|---------|--------|
| **Chief Complaint** | Brief reason for visit |
| **HPI** | Onset, duration, symptoms, severity, timing, modifying factors |
| **Review of Systems** | Constitutional, HEENT, respiratory, GI, skin, neuro |
| **Past Medical History** | Conditions, surgeries, hospitalizations |
| **Medications** | Current medications with doses |
| **Allergies** | Allergens and reactions |
| **Physical Exam** | Vitals, system-by-system findings |
| **Assessment** | Diagnoses with ICD-10 if mentioned |
| **Plan** | Treatment, medications ordered, follow-up |
| **Injected Errors** | Errors present in the script (from metadata) |

## Validation

When using `--validate`, the extraction is compared against:

- Patient profile (allergies, medications, medical history)
- Encounter metadata (encounter type, chief complaint)
- Error injection metadata (expected errors should be detectable)

The validation report highlights:
- Missing data points
- Inconsistencies between script and profile
- Whether injected errors are correctly identifiable

## Use Cases

1. **Scribe Training** -- Generate encounters with known ground truth, have AI scribes produce notes, compare against ground truth
2. **Error Detection** -- Validate that injected errors are detectable in the transcript
3. **Quality Assurance** -- Ensure generated scripts contain medically coherent content
