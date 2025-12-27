"""
Error injection system for Syrinx.
Defines error types and provides injection prompts for Claude.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from .input_parser import ErrorSpec


@dataclass
class ErrorTemplate:
    """Template for injecting a specific error type."""
    category: str
    error_type: str
    name: str
    description: str
    injection_prompt: str
    detection_markers: List[str]


# Clinical Errors - mistakes in medical decision-making
CLINICAL_ERRORS = {
    "missed-allergy": ErrorTemplate(
        category="clinical",
        error_type="missed-allergy",
        name="Missed Medication Allergy",
        description="Doctor prescribes medication without noting allergy mentioned by parent",
        injection_prompt="""
INJECT ERROR: Missed Medication Allergy
- The parent should clearly mention a medication allergy early in the conversation
  (e.g., "She had a reaction to amoxicillin last year - got a rash all over")
- The doctor acknowledges but doesn't document or remember it
- Later, the doctor prescribes a related medication without checking
  (e.g., prescribes Augmentin or another penicillin-class antibiotic)
- The parent may or may not catch the error
""",
        detection_markers=["allergy_mentioned", "conflicting_prescription", "no_allergy_documentation"]
    ),

    "missed-diagnosis": ErrorTemplate(
        category="clinical",
        error_type="missed-diagnosis",
        name="Missed Diagnosis",
        description="Doctor fails to recognize condition from presented symptoms",
        injection_prompt="""
INJECT ERROR: Missed Diagnosis
- Parent describes symptoms that should raise concern for a specific diagnosis
- Doctor attributes symptoms to something benign or common
- Red flags are mentioned but not recognized as significant
- Example: Attributing persistent headache with morning vomiting to stress,
  missing signs of increased intracranial pressure
""",
        detection_markers=["diagnosis_omitted", "symptoms_dismissed", "red_flag_missed"]
    ),

    "ignored-red-flag": ErrorTemplate(
        category="clinical",
        error_type="ignored-red-flag",
        name="Ignored Red Flag Symptom",
        description="Doctor dismisses or overlooks a concerning symptom",
        injection_prompt="""
INJECT ERROR: Ignored Red Flag
- Parent mentions a symptom that should trigger urgent action
  (e.g., high fever in newborn, petechial rash, severe headache with neck stiffness)
- Doctor acknowledges hearing it but doesn't act appropriately
- No escalation, no urgent workup ordered
- Doctor may rationalize: "That's probably nothing to worry about"
""",
        detection_markers=["red_flag_symptom", "inadequate_response", "no_escalation"]
    ),

    "wrong-medication": ErrorTemplate(
        category="clinical",
        error_type="wrong-medication",
        name="Wrong Medication or Dose",
        description="Doctor prescribes incorrect medication or inappropriate dose",
        injection_prompt="""
INJECT ERROR: Wrong Medication/Dose
- Doctor prescribes medication that is:
  - Wrong for the condition (antibiotic for viral illness)
  - Age-inappropriate (adult formulation for infant)
  - Wrong dose (too high or too low for weight/age)
  - Contraindicated combination with current medications
- Error should be subtle but detectable by careful review
""",
        detection_markers=["prescription_error", "dose_error", "contraindication"]
    ),
}

# Communication Errors - problems in doctor-patient interaction
COMMUNICATION_ERRORS = {
    "interrupted-patient": ErrorTemplate(
        category="communication",
        error_type="interrupted-patient",
        name="Interrupted Patient/Parent",
        description="Doctor repeatedly cuts off parent before they finish speaking",
        injection_prompt="""
INJECT ERROR: Interrupted Patient
- Doctor should interrupt the parent at least 3-4 times
- Parent starts explaining something, doctor cuts in with next question
- Show parent frustration: "Well, I was trying to say..." or losing train of thought
- Information may be lost because parent couldn't finish
- Example:
  Parent: "So she started having this fever on Tuesday and then—"
  Doctor: "Is she eating normally?"
""",
        detection_markers=["interruption_pattern", "incomplete_history", "parent_frustration"]
    ),

    "used-jargon": ErrorTemplate(
        category="communication",
        error_type="used-jargon",
        name="Used Medical Jargon",
        description="Doctor uses medical terminology without explanation",
        injection_prompt="""
INJECT ERROR: Medical Jargon
- Doctor uses medical terms without explaining them:
  - "febrile illness" instead of "fever"
  - "otitis media" instead of "ear infection"
  - "bilateral" "prn" "prophylaxis" "empiric therapy"
- Parent shows confusion: "I'm sorry, what does that mean?"
- Doctor may not clarify or uses more jargon in explanation
""",
        detection_markers=["jargon_used", "parent_confusion", "no_clarification"]
    ),

    "dismissive": ErrorTemplate(
        category="communication",
        error_type="dismissive",
        name="Dismissive of Concerns",
        description="Doctor minimizes or dismisses parent's legitimate concerns",
        injection_prompt="""
INJECT ERROR: Dismissive
- When parent expresses worry, doctor minimizes:
  - "You're overreacting, all kids get this"
  - "There's nothing to worry about"
  - "I see this all the time, it's fine"
- Doctor doesn't validate parent's feelings or explain reasoning
- May come across as condescending or impatient
""",
        detection_markers=["concern_dismissed", "empathy_lacking", "condescending_tone"]
    ),

    "rushed": ErrorTemplate(
        category="communication",
        error_type="rushed",
        name="Rushed Encounter",
        description="Doctor hurries through visit without thorough assessment",
        injection_prompt="""
INJECT ERROR: Rushed Encounter
- Doctor speaks quickly, moves fast through questions
- May say things like:
  - "I have to get to my next patient"
  - "Let's wrap this up"
  - "Anything else? No? Great."
- Doesn't pause for parent questions
- Skips parts of history or exam
""",
        detection_markers=["rushed_encounter", "questions_unanswered", "incomplete_assessment"]
    ),
}

# Documentation-Relevant Errors - issues that affect medical record quality
DOCUMENTATION_ERRORS = {
    "incomplete-history": ErrorTemplate(
        category="documentation",
        error_type="incomplete-history",
        name="Incomplete History",
        description="Doctor fails to gather complete medical history",
        injection_prompt="""
INJECT ERROR: Incomplete History
- Doctor skips important history elements:
  - Never asks about allergies
  - Doesn't review current medications
  - Skips past medical history
  - Doesn't ask about family history when relevant
- Jumps straight to current complaint without context
- Missing standard review of systems
""",
        detection_markers=["missing_history_elements", "allergies_not_asked", "meds_not_reviewed"]
    ),

    "no-follow-up-plan": ErrorTemplate(
        category="documentation",
        error_type="no-follow-up-plan",
        name="No Follow-up Plan",
        description="Doctor doesn't provide clear follow-up instructions",
        injection_prompt="""
INJECT ERROR: No Follow-up Plan
- Doctor gives vague or no return precautions:
  - Doesn't say when to come back
  - Doesn't explain what symptoms to watch for
  - Doesn't say how to reach someone if problems arise
  - No clear "call if" or "return if" instructions
- May end abruptly: "Okay, you're all set"
""",
        detection_markers=["missing_follow_up", "no_return_precautions", "vague_instructions"]
    ),

    "missing-med-reconciliation": ErrorTemplate(
        category="documentation",
        error_type="missing-med-reconciliation",
        name="Missing Medication Reconciliation",
        description="Doctor doesn't review current medications before prescribing",
        injection_prompt="""
INJECT ERROR: Missing Med Reconciliation
- Parent mentions child is on multiple medications
- Doctor doesn't ask what they are or review them
- Prescribes new medication without checking for interactions
- No discussion of how new med fits with current regimen
""",
        detection_markers=["medications_not_reviewed", "interactions_not_checked"]
    ),
}

# Combined catalog
ERROR_CATALOG = {
    **CLINICAL_ERRORS,
    **COMMUNICATION_ERRORS,
    **DOCUMENTATION_ERRORS,
}


class ErrorInjector:
    """Manages error injection into encounter scripts."""

    def __init__(self):
        self.catalog = ERROR_CATALOG

    def get_error_template(self, error_type: str) -> Optional[ErrorTemplate]:
        """Get template for a specific error type."""
        return self.catalog.get(error_type)

    def get_injection_prompt(self, error_specs: List[ErrorSpec]) -> str:
        """
        Build combined injection prompt for all requested errors.

        Args:
            error_specs: List of errors to inject

        Returns:
            Combined prompt string for script generation
        """
        if not error_specs:
            return ""

        prompts = []
        for spec in error_specs:
            template = self.get_error_template(spec.error_type)
            if template:
                severity_note = ""
                if spec.severity == "mild":
                    severity_note = "\n(Make this error subtle - barely noticeable)"
                elif spec.severity == "severe":
                    severity_note = "\n(Make this error obvious - clearly problematic)"

                prompts.append(f"{template.injection_prompt}{severity_note}")
            else:
                # Generic fallback for unknown error types
                prompts.append(f"""
INJECT ERROR: {spec.category} - {spec.error_type}
The doctor should make a {spec.severity} {spec.category} error of type "{spec.error_type}".
This should be detectable by a careful reviewer.
""")

        return "\n".join(prompts)

    def list_errors(self, category: Optional[str] = None) -> List[ErrorTemplate]:
        """List available error templates, optionally filtered by category."""
        templates = list(self.catalog.values())

        if category:
            templates = [t for t in templates if t.category == category]

        return templates

    def list_categories(self) -> List[str]:
        """List available error categories."""
        return ["clinical", "communication", "documentation"]

    def describe_error(self, error_type: str) -> str:
        """Get human-readable description of an error type."""
        template = self.get_error_template(error_type)
        if template:
            return f"{template.name}: {template.description}"
        return f"Unknown error type: {error_type}"
