"""
Encounter builder for Syrinx.
Assembles final encounter JSON from generated script and metadata.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .input_parser import EncounterSpec, ParticipantConfig, parse_age_string


# Voice assignments based on role and context
VOICE_ASSIGNMENTS = {
    # Doctor voices
    "doctor_male": "male-1",      # Eric - Smooth, Trustworthy
    "doctor_female": "female-1",  # Matilda - Professional

    # Parent voices
    "parent_female": "female-2",  # Jessica - Warm
    "parent_male": "male-1",      # Eric
    "mom": "female-2",            # Jessica
    "dad": "male-1",              # Eric

    # Child voices
    "child_male": "child-boy",    # Liam
    "child_female": "child-girl", # Laura
    "teen_male": "male-2",        # Will - Relaxed
    "teen_female": "female-2",    # Jessica

    # Elderly
    "elderly_male": "elderly-male",     # Bill
    "elderly_female": "elderly-female", # Alice
}


class EncounterBuilder:
    """Builds complete encounter JSON from components."""

    def __init__(self, output_dir: str = "encounters"):
        self.output_dir = output_dir
        self.encounter_counter = self._get_next_id()

    def _get_next_id(self) -> int:
        """Get next encounter ID based on existing files."""
        path = Path(self.output_dir)
        if not path.exists():
            return 1

        existing = list(path.glob("*.json"))
        if not existing:
            return 1

        # Find highest ID
        max_id = 0
        for f in existing:
            try:
                # Extract ID from filename like "01_acute_..." or "syrinx_001_..."
                name = f.stem
                if name.startswith("syrinx_"):
                    id_part = name.split("_")[1]
                else:
                    id_part = name.split("_")[0]
                max_id = max(max_id, int(id_part))
            except (ValueError, IndexError):
                continue

        return max_id + 1

    def build_encounter(
        self,
        spec: EncounterSpec,
        script: List[Dict[str, str]],
        encounter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete encounter JSON.

        Args:
            spec: Encounter specification
            script: Generated script lines
            encounter_id: Optional custom ID

        Returns:
            Complete encounter dictionary
        """
        if not encounter_id:
            encounter_id = f"syrinx_{self.encounter_counter:03d}"
            self.encounter_counter += 1

        encounter = {
            "metadata": self._build_metadata(spec, encounter_id),
            "speakers": self._build_speakers(spec, script),
            "script": script,
        }

        # Add generation info
        encounter["_generated"] = {
            "tool": "syrinx",
            "timestamp": datetime.now().isoformat(),
            "errors_injected": [
                {"category": e.category, "type": e.error_type, "severity": e.severity}
                for e in spec.errors
            ] if spec.errors else []
        }

        return encounter

    def _build_metadata(self, spec: EncounterSpec, encounter_id: str) -> Dict[str, Any]:
        """Build metadata section."""
        # Calculate duration tier based on line count expectation
        duration_tier = spec.duration_tier

        # Build targets list
        targets = spec.targets.copy() if spec.targets else []

        # Add error-related targets
        for error in spec.errors:
            if error.category == "clinical":
                targets.append(f"detect_{error.error_type}")
            elif error.category == "communication":
                targets.append("communication_quality")
            elif error.category == "documentation":
                targets.append("documentation_completeness")

        metadata = {
            "id": encounter_id,
            "encounter_type": spec.encounter_type.value,
            "patient_age": spec.get_patient_age(),
            "patient_name": spec.get_patient_name(),
            "chief_complaint": spec.chief_complaint,
            "targets": list(set(targets)),  # Remove duplicates
            "duration_tier": duration_tier,
        }

        # Add patient sex if known
        if spec.patient_sex:
            metadata["patient_sex"] = spec.patient_sex
        elif spec.patient_profile and spec.patient_profile.sex:
            metadata["patient_sex"] = spec.patient_profile.sex

        return metadata

    def _build_speakers(
        self,
        spec: EncounterSpec,
        script: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, str]]:
        """Build speakers section with voice assignments."""
        speakers = {}

        # Find all unique speakers in script
        speaker_roles = set()
        for line in script:
            speaker_roles.add(line.get("speaker", ""))

        # Assign voices based on role
        for role in speaker_roles:
            if not role:
                continue

            voice, style = self._assign_voice_and_style(role, spec)
            speakers[role] = {
                "voice": voice,
                "style": style
            }

        return speakers

    def _assign_voice_and_style(
        self,
        role: str,
        spec: EncounterSpec
    ) -> tuple:
        """
        Assign voice and style for a speaker role.

        Returns:
            Tuple of (voice_key, style_description)
        """
        role_lower = role.lower()

        # Doctor
        if role_lower == "doctor":
            if spec.doctor_gender.lower() in ["male", "m"]:
                voice = VOICE_ASSIGNMENTS["doctor_male"]
            else:
                voice = VOICE_ASSIGNMENTS["doctor_female"]
            return (voice, spec.doctor_style)

        # Parent (single)
        if role_lower == "parent":
            style = spec.get_parent_style() or "concerned"
            # Guess gender from style keywords
            if any(w in style.lower() for w in ["dad", "father", "his"]):
                voice = VOICE_ASSIGNMENTS["parent_male"]
            else:
                voice = VOICE_ASSIGNMENTS["parent_female"]
            return (voice, style)

        # Mom
        if role_lower == "mom":
            style = spec.get_parent_style() or "concerned"
            if spec.patient_profile and spec.patient_profile.mother:
                style = spec.patient_profile.mother.style or style
            return (VOICE_ASSIGNMENTS["mom"], style or "concerned")

        # Dad
        if role_lower == "dad":
            if spec.patient_profile and spec.patient_profile.father:
                style = spec.patient_profile.father.style
            else:
                style = "supportive"
            return (VOICE_ASSIGNMENTS["dad"], style)

        # Child
        if role_lower == "child":
            age_months, _ = parse_age_string(spec.get_patient_age())
            if spec.patient_sex and spec.patient_sex.lower() in ["male", "m", "boy"]:
                voice = VOICE_ASSIGNMENTS["child_male"]
            elif spec.patient_sex and spec.patient_sex.lower() in ["female", "f", "girl"]:
                voice = VOICE_ASSIGNMENTS["child_female"]
            else:
                # Default based on common names or random
                voice = VOICE_ASSIGNMENTS["child_female"]

            # Style based on age
            if age_months < 48:  # Under 4 years
                style = "toddler, simple speech"
            elif age_months < 84:  # 4-7 years
                style = "young child, cooperative"
            else:
                style = "older child, articulate"

            return (voice, style)

        # Teen
        if role_lower == "teen":
            if spec.patient_sex and spec.patient_sex.lower() in ["male", "m", "boy"]:
                voice = VOICE_ASSIGNMENTS["teen_male"]
            else:
                voice = VOICE_ASSIGNMENTS["teen_female"]
            return (voice, "teenager, initially guarded")

        # Default fallback
        return ("female-2", "neutral")

    def save_encounter(
        self,
        encounter: Dict[str, Any],
        output_dir: Optional[str] = None
    ) -> str:
        """
        Save encounter to JSON file.

        Returns:
            Path to saved file
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename
        metadata = encounter["metadata"]
        enc_id = metadata["id"]
        enc_type = metadata["encounter_type"]
        patient_name = metadata["patient_name"].lower().replace(" ", "_")

        filename = f"{enc_id}_{enc_type}_{patient_name}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(encounter, f, indent=2)

        return filepath
