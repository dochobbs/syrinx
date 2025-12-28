"""
Validation module for Syrinx.
Validates error injection, infers learning targets, and extracts ground truth.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .input_parser import EncounterSpec, EncounterType, ParticipantConfig, parse_age_string
from .error_injector import ERROR_CATALOG, ErrorSpec


@dataclass
class ValidationResult:
    """Result of validating an error injection."""
    error_type: str
    markers_found: List[str]
    markers_expected: List[str]
    confidence: str  # "high", "medium", "low"
    evidence: List[str]  # Specific text snippets that support detection
    likely_present: bool


# Keyword patterns for detecting error markers
DETECTION_PATTERNS = {
    # Allergy-related
    "allergy_mentioned": [
        r"\b(allerg|allergic|reaction|rash|hives|anaphyla|swelling)\b",
    ],
    "penicillin_class": [
        r"\b(amoxicillin|augmentin|penicillin|ampicillin|amox[-\s]?clav)\b",
    ],
    "prescription_given": [
        r"\b(prescri|pharmacy|i'll send|pick up|take .* times|twice daily|once daily|mg)\b",
    ],

    # Red flag symptoms
    "red_flag_symptom": [
        r"\b(letharg|floppy|won't eat|not feeding|bulging fontanel|stiff neck|petechial|purple spots)\b",
        r"\b(difficulty breathing|turning blue|unresponsive|seizure|convulsion)\b",
        r"\b(projectile vomit|blood in stool|bloody diarrhea)\b",
    ],
    "inadequate_response": [
        r"\b(nothing to worry|probably fine|just a|don't worry|it's normal|all kids get)\b",
    ],

    # Communication patterns
    "interruption_pattern": [
        r"(—|\.\.\.)\s*(doctor|Dr\.)",  # Parent cut off mid-sentence
        r"parent:.*\.\.\.",  # Trailing off
    ],
    "jargon_used": [
        r"\b(bilateral|prn|prophylaxis|empiric|febrile|otitis media|URI|BID|TID|QID)\b",
        r"\b(erythematous|tympanic|pharyngeal|rhinorrhea|effusion|afebrile)\b",
    ],
    "parent_confusion": [
        r"\b(what does that mean|i don't understand|sorry\?|could you explain|in english)\b",
    ],

    # Rushed encounter
    "rushed_encounter": [
        r"\b(next patient|wrap this up|got to go|running behind|quickly)\b",
        r"\b(anything else\? no\?|okay you're all set)\b",
    ],

    # Dismissive
    "concern_dismissed": [
        r"\b(overreact|you're worried about nothing|it's fine|not a big deal)\b",
        r"\b(all (kids|babies|children) get|very common|see this all the time)\b",
    ],

    # Documentation gaps
    "allergies_not_asked": [],  # Detected by absence
    "meds_not_reviewed": [],  # Detected by absence
    "missing_follow_up": [],  # Detected by absence
}

# Words that indicate proper documentation
DOCUMENTATION_MARKERS = {
    "allergies_asked": [r"\b(any allergies|allergic to anything|allergy)\b"],
    "meds_reviewed": [r"\b(current medication|taking any|on any medication|medication list)\b"],
    "follow_up_given": [r"\b(come back|follow up|call if|return if|watch for|bring .* back)\b"],
}


def get_full_text(script: List[Dict]) -> str:
    """Combine all script text into searchable string."""
    return " ".join([line.get("text", "").lower() for line in script])


def get_speaker_text(script: List[Dict], speaker: str) -> str:
    """Get text from specific speaker."""
    return " ".join([
        line.get("text", "").lower()
        for line in script
        if line.get("speaker", "").lower() == speaker.lower()
    ])


def find_pattern_matches(text: str, patterns: List[str]) -> List[str]:
    """Find all matches for a list of regex patterns."""
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        matches.extend(found)
    return matches


def validate_missed_allergy(script: List[Dict]) -> ValidationResult:
    """Validate missed-allergy error injection."""
    full_text = get_full_text(script)
    parent_text = get_speaker_text(script, "parent")
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check if allergy was mentioned (by parent)
    allergy_matches = find_pattern_matches(parent_text, DETECTION_PATTERNS["allergy_mentioned"])
    if allergy_matches:
        markers_found.append("allergy_mentioned")
        evidence.append(f"Allergy mentioned: {allergy_matches[:3]}")

    # Check for penicillin-class drug prescription (by doctor)
    drug_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["penicillin_class"])
    if drug_matches:
        markers_found.append("conflicting_prescription")
        evidence.append(f"Penicillin-class prescribed: {drug_matches[:3]}")

    # Check for prescription language
    rx_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["prescription_given"])
    if rx_matches:
        markers_found.append("prescription_given")

    # Determine confidence
    likely_present = "allergy_mentioned" in markers_found and "conflicting_prescription" in markers_found

    if likely_present and len(drug_matches) >= 1:
        confidence = "high"
    elif "allergy_mentioned" in markers_found:
        confidence = "medium"
    else:
        confidence = "low"

    return ValidationResult(
        error_type="missed-allergy",
        markers_found=markers_found,
        markers_expected=["allergy_mentioned", "conflicting_prescription", "no_allergy_documentation"],
        confidence=confidence,
        evidence=evidence,
        likely_present=likely_present
    )


def validate_ignored_red_flag(script: List[Dict]) -> ValidationResult:
    """Validate ignored-red-flag error injection."""
    full_text = get_full_text(script)
    parent_text = get_speaker_text(script, "parent")
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check for red flag symptoms mentioned
    rf_matches = find_pattern_matches(parent_text, DETECTION_PATTERNS["red_flag_symptom"])
    if rf_matches:
        markers_found.append("red_flag_symptom")
        evidence.append(f"Red flag symptoms: {rf_matches[:3]}")

    # Check for inadequate response
    inad_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["inadequate_response"])
    if inad_matches:
        markers_found.append("inadequate_response")
        evidence.append(f"Dismissive response: {inad_matches[:3]}")

    likely_present = "red_flag_symptom" in markers_found and "inadequate_response" in markers_found

    return ValidationResult(
        error_type="ignored-red-flag",
        markers_found=markers_found,
        markers_expected=["red_flag_symptom", "inadequate_response", "no_escalation"],
        confidence="high" if likely_present else "medium" if markers_found else "low",
        evidence=evidence,
        likely_present=likely_present
    )


def validate_rushed(script: List[Dict]) -> ValidationResult:
    """Validate rushed encounter error injection."""
    full_text = get_full_text(script)
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check for rushed language
    rushed_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["rushed_encounter"])
    if rushed_matches:
        markers_found.append("rushed_encounter")
        evidence.append(f"Rushed language: {rushed_matches[:3]}")

    # Check line count (rushed encounters tend to be short)
    if len(script) < 20:
        markers_found.append("short_encounter")
        evidence.append(f"Only {len(script)} dialogue lines")

    likely_present = "rushed_encounter" in markers_found

    return ValidationResult(
        error_type="rushed",
        markers_found=markers_found,
        markers_expected=["rushed_encounter", "questions_unanswered", "incomplete_assessment"],
        confidence="high" if len(markers_found) >= 2 else "medium" if markers_found else "low",
        evidence=evidence,
        likely_present=likely_present
    )


def validate_dismissive(script: List[Dict]) -> ValidationResult:
    """Validate dismissive communication error."""
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check for dismissive language
    dismiss_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["concern_dismissed"])
    if dismiss_matches:
        markers_found.append("concern_dismissed")
        evidence.append(f"Dismissive language: {dismiss_matches[:3]}")

    likely_present = "concern_dismissed" in markers_found

    return ValidationResult(
        error_type="dismissive",
        markers_found=markers_found,
        markers_expected=["concern_dismissed", "empathy_lacking", "condescending_tone"],
        confidence="high" if likely_present else "low",
        evidence=evidence,
        likely_present=likely_present
    )


def validate_jargon(script: List[Dict]) -> ValidationResult:
    """Validate medical jargon error."""
    doctor_text = get_speaker_text(script, "doctor")
    parent_text = get_speaker_text(script, "parent")

    markers_found = []
    evidence = []

    # Check for jargon
    jargon_matches = find_pattern_matches(doctor_text, DETECTION_PATTERNS["jargon_used"])
    if jargon_matches:
        markers_found.append("jargon_used")
        evidence.append(f"Jargon terms: {list(set(jargon_matches))[:5]}")

    # Check for parent confusion
    confusion_matches = find_pattern_matches(parent_text, DETECTION_PATTERNS["parent_confusion"])
    if confusion_matches:
        markers_found.append("parent_confusion")
        evidence.append(f"Parent confused: {confusion_matches[:3]}")

    likely_present = "jargon_used" in markers_found

    return ValidationResult(
        error_type="used-jargon",
        markers_found=markers_found,
        markers_expected=["jargon_used", "parent_confusion", "no_clarification"],
        confidence="high" if len(markers_found) >= 2 else "medium" if markers_found else "low",
        evidence=evidence,
        likely_present=likely_present
    )


def validate_incomplete_history(script: List[Dict]) -> ValidationResult:
    """Validate incomplete history documentation error."""
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check what's MISSING
    allergies_asked = find_pattern_matches(doctor_text, DOCUMENTATION_MARKERS["allergies_asked"])
    meds_asked = find_pattern_matches(doctor_text, DOCUMENTATION_MARKERS["meds_reviewed"])

    if not allergies_asked:
        markers_found.append("allergies_not_asked")
        evidence.append("No allergy question found")

    if not meds_asked:
        markers_found.append("meds_not_reviewed")
        evidence.append("No medication review found")

    likely_present = len(markers_found) >= 1

    return ValidationResult(
        error_type="incomplete-history",
        markers_found=markers_found,
        markers_expected=["missing_history_elements", "allergies_not_asked", "meds_not_reviewed"],
        confidence="high" if len(markers_found) >= 2 else "medium" if markers_found else "low",
        evidence=evidence,
        likely_present=likely_present
    )


def validate_no_follow_up(script: List[Dict]) -> ValidationResult:
    """Validate missing follow-up plan error."""
    doctor_text = get_speaker_text(script, "doctor")

    markers_found = []
    evidence = []

    # Check for follow-up language
    follow_up = find_pattern_matches(doctor_text, DOCUMENTATION_MARKERS["follow_up_given"])

    if not follow_up:
        markers_found.append("missing_follow_up")
        evidence.append("No follow-up instructions found")

    likely_present = "missing_follow_up" in markers_found

    return ValidationResult(
        error_type="no-follow-up-plan",
        markers_found=markers_found,
        markers_expected=["missing_follow_up", "no_return_precautions", "vague_instructions"],
        confidence="high" if likely_present else "low",
        evidence=evidence,
        likely_present=likely_present
    )


# Validator dispatch table
VALIDATORS = {
    "missed-allergy": validate_missed_allergy,
    "missed-diagnosis": validate_ignored_red_flag,  # Similar detection
    "ignored-red-flag": validate_ignored_red_flag,
    "wrong-medication": validate_missed_allergy,  # Similar patterns
    "interrupted-patient": lambda s: ValidationResult("interrupted-patient", [], [], "medium", [], False),
    "used-jargon": validate_jargon,
    "dismissive": validate_dismissive,
    "rushed": validate_rushed,
    "incomplete-history": validate_incomplete_history,
    "no-follow-up-plan": validate_no_follow_up,
    "missing-med-reconciliation": validate_incomplete_history,
}


def validate_error_injection(
    script: List[Dict],
    error_specs: List[ErrorSpec]
) -> Dict[str, ValidationResult]:
    """
    Validate that all requested errors were properly injected.

    Args:
        script: The generated script
        error_specs: List of errors that should have been injected

    Returns:
        Dictionary mapping error_type to ValidationResult
    """
    results = {}

    for spec in error_specs:
        validator = VALIDATORS.get(spec.error_type)
        if validator:
            results[spec.error_type] = validator(script)
        else:
            # Unknown error type - can't validate
            results[spec.error_type] = ValidationResult(
                error_type=spec.error_type,
                markers_found=[],
                markers_expected=[],
                confidence="unknown",
                evidence=["No validator available for this error type"],
                likely_present=False
            )

    return results


def validation_summary(results: Dict[str, ValidationResult]) -> Dict[str, Any]:
    """Generate summary of validation results."""
    total = len(results)
    high_confidence = sum(1 for r in results.values() if r.confidence == "high")
    likely_present = sum(1 for r in results.values() if r.likely_present)

    return {
        "total_errors_requested": total,
        "high_confidence_detected": high_confidence,
        "likely_present": likely_present,
        "success_rate": likely_present / total if total > 0 else 0,
        "details": {
            error_type: {
                "likely_present": r.likely_present,
                "confidence": r.confidence,
                "evidence": r.evidence
            }
            for error_type, r in results.items()
        }
    }


# =============================================================================
# TARGET INFERENCE
# =============================================================================

# Content patterns for target inference
TARGET_PATTERNS = {
    # Clinical skills
    "vaccine_counseling": [
        r"\b(vaccine|immunization|shot|mmr|dtap|hep|polio|varicella)\b"
    ],
    "antibiotic_stewardship": [
        r"\b(antibiotic|amoxicillin|azithromycin|cephalosporin|penicillin)\b"
    ],
    "pain_management": [
        r"\b(tylenol|motrin|ibuprofen|acetaminophen|pain medication)\b"
    ],
    "disposition_decision": [
        r"\b(admit|hospital|emergency|er|urgent care|iv fluids|observation)\b"
    ],
    "diagnostic_workup": [
        r"\b(x-ray|ct scan|mri|ultrasound|blood test|urine|lumbar puncture|culture)\b"
    ],
    "referral_coordination": [
        r"\b(refer|specialist|see a|appointment with|pediatric \w+ologist)\b"
    ],

    # Social/behavioral
    "social_determinants": [
        r"\b(divorced|custody|daycare|school|housing|food insecurity|homeless)\b"
    ],
    "mental_health_screening": [
        r"\b(anxiety|depression|stress|worried|sad|suicide|self-harm|cutting)\b"
    ],
    "substance_screening": [
        r"\b(alcohol|drugs|vaping|smoking|marijuana|substance)\b"
    ],
    "safety_screening": [
        r"\b(abuse|neglect|hurt|hit|safe at home|gun|firearm|pool|car seat)\b"
    ],

    # Communication
    "vaccine_hesitancy": [
        r"\b(concerned about vaccine|not sure about|worried about shot|anti-vax|research)\b"
    ],
    "parent_education": [
        r"\b(let me explain|what this means|here's what|i want you to understand)\b"
    ],
    "shared_decision_making": [
        r"\b(what do you think|your preference|option|choice|decide together)\b"
    ],

    # Clinical content
    "feeding_assessment": [
        r"\b(nursing|breastfeed|formula|bottle|eating|feeding|appetite)\b"
    ],
    "growth_monitoring": [
        r"\b(weight|height|percentile|growth chart|gaining|growing)\b"
    ],
    "developmental_milestone": [
        r"\b(walking|talking|words|crawling|sitting|milestone|development)\b"
    ],
    "sleep_assessment": [
        r"\b(sleep|sleeping|nap|bedtime|waking|night)\b"
    ],
}


def infer_targets(
    spec: EncounterSpec,
    script: List[Dict]
) -> List[str]:
    """
    Infer learning targets based on encounter specification and content.

    Args:
        spec: Encounter specification
        script: Generated script

    Returns:
        List of inferred learning target strings
    """
    targets = []
    full_text = get_full_text(script)
    age_months, _ = parse_age_string(spec.get_patient_age())

    # ENCOUNTER TYPE TARGETS
    if spec.encounter_type == EncounterType.ACUTE:
        targets.extend([
            "history_of_present_illness",
            "differential_diagnosis",
            "treatment_plan"
        ])
    elif spec.encounter_type == EncounterType.WELL_CHILD:
        targets.extend([
            "growth_assessment",
            "developmental_screening",
            "anticipatory_guidance",
            "immunization_review"
        ])
    elif spec.encounter_type == EncounterType.MENTAL_HEALTH:
        targets.extend([
            "psychosocial_assessment",
            "safety_screening",
            "therapeutic_rapport"
        ])
    elif spec.encounter_type == EncounterType.FOLLOW_UP:
        targets.extend([
            "interval_history",
            "treatment_response",
            "care_plan_adjustment"
        ])

    # AGE-BASED TARGETS
    if age_months < 1:
        targets.extend([
            "neonatal_red_flags",
            "feeding_assessment",
            "jaundice_screening"
        ])
    elif age_months < 3:
        targets.append("young_infant_fever_protocol")
    elif age_months < 12:
        targets.append("infant_developmental_screening")
    elif age_months < 24:
        targets.append("toddler_safety_counseling")
    elif age_months < 60:
        targets.append("preschool_readiness")
    elif age_months < 144:
        targets.append("school_age_wellness")
    else:  # 12+ years
        targets.extend([
            "adolescent_confidentiality",
            "risk_behavior_screening"
        ])

    # PARTICIPANT-BASED TARGETS
    if spec.participants == ParticipantConfig.TWO_PARENTS_CHILD:
        targets.append("multi_caregiver_communication")
    elif spec.participants == ParticipantConfig.PARENT_FUSSY_TODDLER:
        targets.append("challenging_exam_environment")

    # CONTENT-BASED TARGETS (from script analysis)
    for target, patterns in TARGET_PATTERNS.items():
        if find_pattern_matches(full_text, patterns):
            targets.append(target)

    # ERROR-BASED TARGETS (from spec)
    for error in spec.errors:
        if error.category == "clinical":
            targets.append(f"detect_{error.error_type}")
        elif error.category == "communication":
            targets.append("communication_quality")
        elif error.category == "documentation":
            targets.append("documentation_completeness")

    # Remove duplicates while preserving order
    seen = set()
    unique_targets = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique_targets.append(t)

    return unique_targets


def categorize_targets(targets: List[str]) -> Dict[str, List[str]]:
    """Categorize targets into domains for reporting."""
    categories = {
        "clinical_skills": [],
        "communication": [],
        "documentation": [],
        "age_specific": [],
        "content_specific": [],
        "error_detection": []
    }

    clinical = ["history_of_present_illness", "differential_diagnosis", "treatment_plan",
                "antibiotic_stewardship", "pain_management", "disposition_decision",
                "diagnostic_workup", "referral_coordination", "growth_assessment",
                "developmental_screening", "feeding_assessment", "immunization_review"]

    communication = ["anticipatory_guidance", "parent_education", "shared_decision_making",
                     "therapeutic_rapport", "multi_caregiver_communication", "vaccine_hesitancy",
                     "adolescent_confidentiality"]

    documentation = ["documentation_completeness", "interval_history", "care_plan_adjustment"]

    age_specific = ["neonatal_red_flags", "young_infant_fever_protocol", "infant_developmental_screening",
                    "toddler_safety_counseling", "preschool_readiness", "school_age_wellness",
                    "risk_behavior_screening"]

    for target in targets:
        if target.startswith("detect_"):
            categories["error_detection"].append(target)
        elif target in clinical:
            categories["clinical_skills"].append(target)
        elif target in communication:
            categories["communication"].append(target)
        elif target in documentation:
            categories["documentation"].append(target)
        elif target in age_specific:
            categories["age_specific"].append(target)
        else:
            categories["content_specific"].append(target)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}
