# Error Injection Reference

**Module:** `core/error_injector.py`

## Overview

Syrinx can inject deliberate errors into encounter scripts for AI scribe training. Errors are specified via the `--error` flag and follow the format `category:type`.

## Error Categories

### Clinical Errors

Errors in medical decision-making.

| Error | Key | Description | Example |
|-------|-----|-------------|---------|
| Missed Allergy | `clinical:missed-allergy` | Doctor prescribes medication the patient is allergic to | Prescribing amoxicillin to a penicillin-allergic patient |
| Missed Diagnosis | `clinical:missed-diagnosis` | Doctor fails to recognize the correct condition | Missing signs of pneumonia, diagnosing as "viral URI" |
| Ignored Red Flag | `clinical:ignored-red-flag` | Doctor dismisses a concerning symptom | Ignoring nuchal rigidity in a febrile infant |
| Wrong Medication | `clinical:wrong-medication` | Incorrect medication or dose for age/weight | Adult dose of acetaminophen for a 6-month-old |

### Communication Errors

Problems in the doctor-patient interaction.

| Error | Key | Description | Example |
|-------|-----|-------------|---------|
| Interrupted | `communication:interrupted` | Doctor repeatedly cuts off the parent | "Yes, but--" before parent finishes |
| Jargon | `communication:jargon` | Uses medical terms without explanation | "We need to rule out AOM" without defining it |
| Dismissive | `communication:dismissive` | Minimizes parent concerns | "That's nothing to worry about" to a worried parent |
| Rushed | `communication:rushed` | Hurries through the visit | Skips social history, brief exam |

### Documentation Errors

Information that a scribe would miss or get wrong.

| Error | Key | Description | Example |
|-------|-----|-------------|---------|
| Incomplete History | `documentation:incomplete-history` | Skips allergies, medications, or PMH | No medication reconciliation performed |
| No Follow-up | `documentation:no-follow-up` | No return precautions given | Doesn't mention when to come back |
| Missing Med Rec | `documentation:missing-med-rec` | Doesn't review current medications | Skips "What medications is she on?" |

## Usage

### Single Error

```bash
python syrinx.py generate \
    --patient patients/olivia_chen.json \
    --chief-complaint "ear infection" \
    --error clinical:missed-allergy
```

### Multiple Errors

```bash
python syrinx.py generate \
    --patient patients/olivia_chen.json \
    --chief-complaint "fever" \
    --error clinical:missed-diagnosis \
    --error communication:rushed
```

### List Available Errors

```bash
# All errors
python syrinx.py errors list

# Filter by category
python syrinx.py errors list --category clinical
python syrinx.py errors list --category communication
python syrinx.py errors list --category documentation
```

## How Injection Works

1. The error type is looked up in the error catalog (`core/error_injector.py`)
2. Each error has an `injection_prompt` that instructs Claude how to introduce the error naturally
3. The injection prompt is appended to the script generation prompt
4. The error metadata is recorded in `_generated.errors_injected` for ground truth validation

## Error Combinations

Some error combinations produce more realistic scripts than others:

| Combination | Realism |
|-------------|---------|
| `clinical:missed-allergy` alone | High -- very common in practice |
| `clinical:missed-diagnosis` + `communication:rushed` | High -- rushed visits lead to missed diagnoses |
| `clinical:wrong-medication` + `documentation:missing-med-rec` | High -- no med rec leads to wrong meds |
| Multiple clinical errors | Lower -- multiple clinical errors in one visit is unusual |

## Detection Markers

Each error type includes `detection_markers` -- keys that ground truth extraction should look for when validating whether an AI scribe detected the error.

For example, `clinical:missed-allergy` markers include:
- Medication prescribed matches a known allergen
- Allergy not mentioned in assessment
- No allergy check documented
