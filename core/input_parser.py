"""
Input parsing for Syrinx CLI.
Handles natural language and structured inputs, plus patient profile loading.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path


class EncounterType(Enum):
    ACUTE = "acute"
    WELL_CHILD = "well-child"
    MENTAL_HEALTH = "mental-health"
    FOLLOW_UP = "follow-up"


class ParticipantConfig(Enum):
    PARENT_INFANT = "parent+infant"
    PARENT_CHILD = "parent+child"
    TWO_PARENTS_CHILD = "two-parents+child"
    PARENT_FUSSY_TODDLER = "parent+fussy-toddler"


@dataclass
class ErrorSpec:
    """Specification for an error to inject."""
    category: str  # clinical, communication, documentation
    error_type: str  # missed-allergy, rushed, etc.
    severity: str = "moderate"  # mild, moderate, severe


@dataclass
class FamilyMember:
    """Family member info from patient profile."""
    name: str
    style: str = ""
    relationship: str = ""


@dataclass
class PatientProfile:
    """Patient profile loaded from JSON file."""
    # Patient info
    name: str
    age: str
    sex: str
    dob: str = ""
    preferred_name: str = ""

    # Family
    mother: Optional[FamilyMember] = None
    father: Optional[FamilyMember] = None

    # Medical history
    allergies: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    chronic_conditions: List[str] = field(default_factory=list)
    past_medical: List[str] = field(default_factory=list)
    immunizations: str = ""
    last_well_check: str = ""

    # Social history
    lives_with: str = ""
    daycare: bool = False
    siblings: List[str] = field(default_factory=list)
    pets: List[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str) -> "PatientProfile":
        """Load patient profile from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        patient = data.get("patient", {})
        family = data.get("family", {})
        medical = data.get("medical_history", {})
        social = data.get("social_history", {})

        mother = None
        if "mother" in family:
            mother = FamilyMember(
                name=family["mother"].get("name", ""),
                style=family["mother"].get("style", ""),
                relationship="mother"
            )

        father = None
        if "father" in family:
            father = FamilyMember(
                name=family["father"].get("name", ""),
                style=family["father"].get("style", ""),
                relationship="father"
            )

        return cls(
            name=patient.get("name", ""),
            age=patient.get("age", ""),
            sex=patient.get("sex", ""),
            dob=patient.get("dob", ""),
            preferred_name=patient.get("preferred_name", ""),
            mother=mother,
            father=father,
            allergies=medical.get("allergies", []),
            medications=medical.get("medications", []),
            chronic_conditions=medical.get("chronic_conditions", []),
            past_medical=medical.get("past_medical", []),
            immunizations=medical.get("immunizations", ""),
            last_well_check=medical.get("last_well_check", ""),
            lives_with=social.get("lives_with", ""),
            daycare=social.get("daycare", False),
            siblings=social.get("siblings", []),
            pets=social.get("pets", [])
        )

    def to_context_string(self) -> str:
        """Convert patient profile to context string for prompt."""
        lines = [
            f"PATIENT: {self.name}",
            f"Age: {self.age}",
            f"Sex: {self.sex}",
        ]

        if self.preferred_name:
            lines.append(f"Goes by: {self.preferred_name}")

        if self.mother:
            lines.append(f"Mother: {self.mother.name} ({self.mother.style})")
        if self.father:
            lines.append(f"Father: {self.father.name} ({self.father.style})")

        lines.append("\nMEDICAL HISTORY:")
        if self.allergies:
            lines.append(f"Allergies: {', '.join(self.allergies)}")
        else:
            lines.append("Allergies: NKDA")

        if self.medications:
            lines.append(f"Medications: {', '.join(self.medications)}")

        if self.chronic_conditions:
            lines.append(f"Chronic conditions: {', '.join(self.chronic_conditions)}")

        if self.past_medical:
            lines.append(f"Past medical: {', '.join(self.past_medical)}")

        if self.immunizations:
            lines.append(f"Immunizations: {self.immunizations}")

        if self.last_well_check:
            lines.append(f"Last well check: {self.last_well_check}")

        lines.append("\nSOCIAL HISTORY:")
        if self.lives_with:
            lines.append(f"Lives with: {self.lives_with}")
        lines.append(f"Daycare: {'Yes' if self.daycare else 'No'}")
        if self.siblings:
            lines.append(f"Siblings: {', '.join(self.siblings)}")
        if self.pets:
            lines.append(f"Pets: {', '.join(self.pets)}")

        return "\n".join(lines)


@dataclass
class EncounterSpec:
    """Complete specification for generating an encounter."""
    # Required
    encounter_type: EncounterType
    chief_complaint: str

    # Patient (from profile or specified)
    patient_name: str = ""
    patient_age: str = ""
    patient_sex: str = ""
    patient_profile: Optional[PatientProfile] = None

    # Participants and style
    participants: ParticipantConfig = ParticipantConfig.PARENT_INFANT
    parent_style: str = "concerned"
    doctor_style: str = "warm, thorough"
    doctor_gender: str = "female"  # for voice selection

    # Errors to inject
    errors: List[ErrorSpec] = field(default_factory=list)

    # Output control
    duration_tier: str = "medium"  # short, medium, long
    targets: List[str] = field(default_factory=list)  # learning objectives

    def get_patient_name(self) -> str:
        """Get patient name from profile or direct specification."""
        if self.patient_profile:
            return self.patient_profile.name
        return self.patient_name or "Child"

    def get_patient_age(self) -> str:
        """Get patient age from profile or direct specification."""
        if self.patient_profile:
            return self.patient_profile.age
        return self.patient_age or "12 months"

    def get_parent_style(self) -> str:
        """Get parent style, preferring profile if available."""
        if self.patient_profile and self.patient_profile.mother:
            return self.patient_profile.mother.style or self.parent_style or "concerned"
        return self.parent_style or "concerned"


def parse_age_string(age_str: str) -> tuple:
    """
    Parse age string into (months, display_string).

    Examples:
        "6 months" -> (6, "6 months")
        "2 years" -> (24, "2 years")
        "18mo" -> (18, "18 months")
        "4yo" -> (48, "4 years")
    """
    age_str = age_str.lower().strip()

    # Match patterns like "6 months", "6mo", "6m"
    month_match = re.match(r"(\d+)\s*(months?|mo|m)\b", age_str)
    if month_match:
        months = int(month_match.group(1))
        return (months, f"{months} months" if months != 1 else "1 month")

    # Match patterns like "2 years", "2yo", "2y"
    year_match = re.match(r"(\d+)\s*(years?|yo|y)\b", age_str)
    if year_match:
        years = int(year_match.group(1))
        months = years * 12
        return (months, f"{years} years" if years != 1 else "1 year")

    # Match patterns like "3 weeks", "3wk", "3w"
    week_match = re.match(r"(\d+)\s*(weeks?|wk|w)\b", age_str)
    if week_match:
        weeks = int(week_match.group(1))
        return (0, f"{weeks} weeks" if weeks != 1 else "1 week")

    # Match patterns like "5 days", "5d"
    day_match = re.match(r"(\d+)\s*(days?|d)\b", age_str)
    if day_match:
        days = int(day_match.group(1))
        return (0, f"{days} days" if days != 1 else "1 day")

    # Default: try to parse as just a number (assume months)
    try:
        months = int(age_str)
        return (months, f"{months} months")
    except ValueError:
        return (12, age_str)  # Default to 12 months if unparseable


def parse_error_string(error_str: str) -> ErrorSpec:
    """
    Parse error specification string.

    Format: category:type[:severity]
    Examples:
        "clinical:missed-allergy"
        "communication:rushed:severe"
    """
    parts = error_str.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid error format: {error_str}. Use category:type")

    category = parts[0]
    error_type = parts[1]
    severity = parts[2] if len(parts) > 2 else "moderate"

    valid_categories = ["clinical", "communication", "documentation"]
    if category not in valid_categories:
        raise ValueError(f"Invalid error category: {category}. Use: {valid_categories}")

    return ErrorSpec(category=category, error_type=error_type, severity=severity)


def parse_participants(part_str: str) -> ParticipantConfig:
    """Parse participant configuration string."""
    mapping = {
        "parent+infant": ParticipantConfig.PARENT_INFANT,
        "parent+child": ParticipantConfig.PARENT_CHILD,
        "two-parents+child": ParticipantConfig.TWO_PARENTS_CHILD,
        "two-parents": ParticipantConfig.TWO_PARENTS_CHILD,
        "parent+fussy-toddler": ParticipantConfig.PARENT_FUSSY_TODDLER,
        "parent+toddler": ParticipantConfig.PARENT_FUSSY_TODDLER,
    }

    normalized = part_str.lower().strip()
    if normalized in mapping:
        return mapping[normalized]

    raise ValueError(f"Unknown participant config: {part_str}. Use: {list(mapping.keys())}")


def parse_encounter_type(type_str: str) -> EncounterType:
    """Parse encounter type string."""
    mapping = {
        "acute": EncounterType.ACUTE,
        "well-child": EncounterType.WELL_CHILD,
        "wellchild": EncounterType.WELL_CHILD,
        "wcc": EncounterType.WELL_CHILD,
        "mental-health": EncounterType.MENTAL_HEALTH,
        "mentalhealth": EncounterType.MENTAL_HEALTH,
        "mh": EncounterType.MENTAL_HEALTH,
        "follow-up": EncounterType.FOLLOW_UP,
        "followup": EncounterType.FOLLOW_UP,
        "fu": EncounterType.FOLLOW_UP,
    }

    normalized = type_str.lower().strip()
    if normalized in mapping:
        return mapping[normalized]

    raise ValueError(f"Unknown encounter type: {type_str}. Use: acute, well-child, mental-health, follow-up")
