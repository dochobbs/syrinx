"""
Script generation using Claude API.
Generates realistic pediatric encounter dialogue.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
import anthropic

from .input_parser import EncounterSpec, ParticipantConfig
from .error_injector import ErrorInjector


SYSTEM_PROMPT = """You are an expert medical education script writer creating realistic pediatric doctor-patient encounter scripts.

Your scripts are used to:
1. Train AI medical scribes
2. Teach medical learners to identify errors
3. Simulate realistic clinical conversations

OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
{
  "script": [
    {"speaker": "doctor", "text": "dialogue text", "direction": "tone/action"},
    {"speaker": "parent", "text": "dialogue text", "direction": "tone/action"}
  ]
}

SPEAKER ROLES:
- "doctor" - The physician (always present)
- "parent" - Single parent/caregiver
- "mom" - Mother (when both parents present)
- "dad" - Father (when both parents present)
- "child" - Speaking child (4+ years)
- "teen" - Adolescent patient

DIRECTION ANNOTATIONS (for TTS prosody):
- Tones: "warm", "concerned", "reassuring", "rushed", "dismissive", "anxious", "frustrated", "calm"
- Actions: "[examining]", "[typing]", "[thinking]", "[explaining]"
- Ambient: "[baby fussing]", "[child coughing]", "[pause]"

SCRIPT GUIDELINES:
1. Natural conversational flow with realistic pauses and interruptions
2. Age-appropriate language for children
3. Include examination findings verbalized by doctor
4. Realistic parent responses based on their style (anxious, calm, experienced, etc.)
5. Medical accuracy in terminology, doses, and clinical reasoning
6. Standard history-taking flow: Chief complaint → HPI → PMH → Allergies → Meds → Social → ROS → Exam → Assessment → Plan

DURATION TARGETS:
- short: 15-20 dialogue lines
- medium: 25-35 dialogue lines
- long: 40-50 dialogue lines

CRITICAL: Return ONLY the JSON object. No markdown, no explanation, no code blocks."""


def get_participant_prompt(config: ParticipantConfig) -> str:
    """Get prompt fragment for participant configuration."""
    prompts = {
        ParticipantConfig.PARENT_INFANT: """
PARTICIPANTS: One parent with non-speaking infant/toddler (<2 years)
- Only "doctor" and "parent" speak
- Include baby sounds in directions: [baby fussing], [baby crying], [baby cooing]
- Parent may narrate baby's behavior: "She's been so fussy..."
""",
        ParticipantConfig.PARENT_CHILD: """
PARTICIPANTS: One parent with speaking child (4+ years)
- "doctor", "parent", and "child" speak
- Child speaks in age-appropriate language
- Child may be cooperative, shy, or complaining
- Include child naturally: Doctor may ask child directly
""",
        ParticipantConfig.TWO_PARENTS_CHILD: """
PARTICIPANTS: Two parents (mom and dad) with child
- Use "mom" and "dad" instead of "parent"
- Parents may have different perspectives or interrupt each other
- Doctor should address both parents
- Child may or may not speak depending on age
""",
        ParticipantConfig.PARENT_FUSSY_TODDLER: """
PARTICIPANTS: Parent with fussy/crying toddler (1-3 years)
- "doctor" and "parent" speak
- Include frequent: [child crying], [child whining], [parent soothing child]
- Parent may be distracted trying to calm child
- Doctor may need to repeat questions or pause
""",
    }
    return prompts.get(config, prompts[ParticipantConfig.PARENT_INFANT])


def get_duration_lines(tier: str) -> tuple:
    """Get line count target for duration tier."""
    targets = {
        "short": (15, 20),
        "medium": (25, 35),
        "long": (40, 50),
    }
    return targets.get(tier, (25, 35))


class ScriptGenerator:
    """Generates doctor-patient conversation scripts using Claude."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model
        self.error_injector = ErrorInjector()

    def generate_script(self, encounter_spec: EncounterSpec) -> Dict[str, Any]:
        """
        Generate complete encounter script.

        Args:
            encounter_spec: Specification for the encounter

        Returns:
            Dictionary with script array
        """
        # Build the generation prompt
        user_prompt = self._build_generation_prompt(encounter_spec)

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Extract text content
        content = response.content[0].text

        # Parse JSON response
        try:
            # Try to extract JSON from response
            result = self._parse_json_response(content)
            return result
        except Exception as e:
            raise ValueError(f"Failed to parse script response: {e}\nResponse: {content[:500]}")

    def _build_generation_prompt(self, spec: EncounterSpec) -> str:
        """Build the complete generation prompt."""
        lines = []

        # Encounter type
        lines.append(f"Generate a {spec.encounter_type.value} pediatric encounter script.\n")

        # Patient info
        if spec.patient_profile:
            lines.append(spec.patient_profile.to_context_string())
        else:
            lines.append(f"PATIENT: {spec.get_patient_name()}")
            lines.append(f"Age: {spec.get_patient_age()}")
            if spec.patient_sex:
                lines.append(f"Sex: {spec.patient_sex}")

        lines.append(f"\nCHIEF COMPLAINT: {spec.chief_complaint}")

        # Styles
        lines.append(f"\nPARENT STYLE: {spec.get_parent_style()}")
        lines.append(f"DOCTOR STYLE: {spec.doctor_style}")
        lines.append(f"DOCTOR GENDER: {spec.doctor_gender}")

        # Participants
        lines.append(get_participant_prompt(spec.participants))

        # Duration
        min_lines, max_lines = get_duration_lines(spec.duration_tier)
        lines.append(f"TARGET LENGTH: {min_lines}-{max_lines} dialogue lines ({spec.duration_tier})")

        # Error injection
        if spec.errors:
            error_prompt = self.error_injector.get_injection_prompt(spec.errors)
            lines.append(f"\nINTENTIONAL ERRORS TO INJECT:\n{error_prompt}")
            lines.append("\nIMPORTANT: Make errors subtle but detectable by careful review.")
        else:
            lines.append("\nNo intentional errors - generate a clean, well-conducted encounter.")

        # Learning targets if specified
        if spec.targets:
            lines.append(f"\nLEARNING OBJECTIVES: {', '.join(spec.targets)}")

        lines.append("\nGenerate the complete script now as JSON.")

        return "\n".join(lines)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from Claude's response, handling various formats."""
        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            # Find the actual JSON content
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            content = "\n".join(json_lines)

        # Try to find JSON object
        if not content.startswith("{"):
            # Look for JSON object in the response
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                content = match.group(0)

        return json.loads(content)

    def parse_natural_language(self, nl_input: str) -> EncounterSpec:
        """
        Parse natural language input into EncounterSpec using Claude.

        Args:
            nl_input: Natural language description

        Returns:
            EncounterSpec with extracted parameters
        """
        parse_prompt = f"""Parse this natural language description into structured encounter parameters.

INPUT: "{nl_input}"

Return JSON with these fields (use null for unspecified):
{{
  "encounter_type": "acute" | "well-child" | "mental-health" | "follow-up",
  "patient_age": "age string like '6 months' or '4 years'",
  "patient_name": "name or null",
  "patient_sex": "male" | "female" | null,
  "chief_complaint": "main reason for visit",
  "parent_style": "description like 'anxious', 'calm', 'experienced'",
  "doctor_style": "description like 'warm', 'rushed', 'thorough'",
  "participants": "parent+infant" | "parent+child" | "two-parents+child" | "parent+fussy-toddler",
  "duration": "short" | "medium" | "long",
  "errors": [
    {{"category": "clinical|communication|documentation", "type": "error-type"}}
  ]
}}

Return ONLY the JSON object."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": parse_prompt}]
        )

        content = response.content[0].text
        parsed = self._parse_json_response(content)

        # Convert to EncounterSpec
        from .input_parser import (
            parse_encounter_type, parse_participants, ErrorSpec, ParticipantConfig
        )

        errors = []
        for err in parsed.get("errors", []):
            if err and err.get("category") and err.get("type"):
                errors.append(ErrorSpec(
                    category=err["category"],
                    error_type=err["type"]
                ))

        try:
            participants = parse_participants(parsed.get("participants", "parent+infant"))
        except ValueError:
            participants = ParticipantConfig.PARENT_INFANT

        try:
            encounter_type = parse_encounter_type(parsed.get("encounter_type", "acute"))
        except ValueError:
            from .input_parser import EncounterType
            encounter_type = EncounterType.ACUTE

        return EncounterSpec(
            encounter_type=encounter_type,
            chief_complaint=parsed.get("chief_complaint", ""),
            patient_name=parsed.get("patient_name", ""),
            patient_age=parsed.get("patient_age", "12 months"),
            patient_sex=parsed.get("patient_sex", ""),
            parent_style=parsed.get("parent_style", "concerned"),
            doctor_style=parsed.get("doctor_style", "warm, thorough"),
            participants=participants,
            duration_tier=parsed.get("duration", "medium"),
            errors=errors
        )
