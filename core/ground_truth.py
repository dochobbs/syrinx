"""
Ground truth extraction for scribe training.
Uses Claude to extract structured clinical data from encounter scripts.
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
import anthropic


EXTRACTION_PROMPT = """You are a medical documentation expert. Extract structured clinical data from this pediatric encounter transcript.

TRANSCRIPT:
{transcript}

Extract the following information. Use null for fields not mentioned. Be precise and use exact quotes where appropriate.

Return ONLY valid JSON with this structure:
{{
  "chief_complaint": "brief statement of why patient came in",

  "history_of_present_illness": {{
    "onset": "when symptoms started",
    "duration": "how long symptoms have lasted",
    "symptoms": ["list", "of", "symptoms"],
    "severity": "mild/moderate/severe",
    "quality": "description of symptom character",
    "timing": "constant/intermittent/specific times",
    "modifying_factors": {{
      "alleviating": ["what makes it better"],
      "aggravating": ["what makes it worse"]
    }},
    "associated_symptoms": ["other symptoms mentioned"]
  }},

  "review_of_systems": {{
    "constitutional": "fever, weight changes, fatigue",
    "heent": "ear, nose, throat findings",
    "respiratory": "cough, breathing",
    "cardiovascular": "heart-related",
    "gastrointestinal": "appetite, vomiting, diarrhea, constipation",
    "genitourinary": "urination, diapers",
    "skin": "rashes, lesions",
    "neurological": "headache, alertness, behavior",
    "psychiatric": "mood, anxiety, behavior"
  }},

  "past_medical_history": {{
    "conditions": ["chronic conditions"],
    "surgeries": ["past surgeries"],
    "hospitalizations": ["past hospital stays"],
    "birth_history": "if mentioned (gestational age, delivery, complications)"
  }},

  "allergies": [
    {{
      "allergen": "medication or substance",
      "reaction": "type of reaction (rash, anaphylaxis, etc.)"
    }}
  ],

  "medications": [
    {{
      "name": "medication name",
      "dose": "dose if mentioned",
      "frequency": "how often taken"
    }}
  ],

  "family_history": ["relevant family medical history"],

  "social_history": {{
    "living_situation": "who child lives with",
    "daycare_school": "daycare or school attendance",
    "exposures": "sick contacts, travel, pets",
    "development": "developmental concerns if mentioned"
  }},

  "physical_exam": {{
    "vitals": {{
      "temperature": {{"value": null, "unit": "F or C"}},
      "heart_rate": null,
      "respiratory_rate": null,
      "blood_pressure": null,
      "oxygen_saturation": null,
      "weight": null
    }},
    "general": "overall appearance",
    "heent": "head, eyes, ears, nose, throat findings",
    "neck": "lymph nodes, stiffness",
    "lungs": "breath sounds",
    "heart": "heart sounds",
    "abdomen": "abdominal exam",
    "skin": "skin findings",
    "extremities": "extremity findings",
    "neurological": "neuro findings"
  }},

  "assessment": [
    {{
      "diagnosis": "diagnosis name",
      "icd10": "ICD-10 code if you can infer it",
      "certainty": "confirmed/suspected/ruled_out"
    }}
  ],

  "plan": {{
    "medications_prescribed": [
      {{
        "name": "medication name",
        "dose": "dose",
        "route": "PO/IM/IV/topical/etc",
        "frequency": "how often",
        "duration": "how long to take",
        "instructions": "special instructions"
      }}
    ],
    "orders": ["labs, imaging, procedures ordered"],
    "referrals": ["specialist referrals"],
    "patient_education": ["education topics discussed"],
    "follow_up": {{
      "timing": "when to return",
      "with_whom": "with PCP/specialist/etc"
    }},
    "return_precautions": ["warning signs to return for"]
  }}
}}

Return ONLY the JSON object. No explanation or markdown."""


class GroundTruthExtractor:
    """Extracts structured ground truth from encounter scripts."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model

    def format_transcript(self, script: List[Dict]) -> str:
        """Format script as readable transcript."""
        lines = []
        for line in script:
            speaker = line.get("speaker", "unknown").upper()
            text = line.get("text", "")
            direction = line.get("direction", "")

            if direction:
                lines.append(f"{speaker}: {text} [{direction}]")
            else:
                lines.append(f"{speaker}: {text}")

        return "\n".join(lines)

    def extract(self, script: List[Dict]) -> Dict[str, Any]:
        """
        Extract structured ground truth from script.

        Args:
            script: List of dialogue lines

        Returns:
            Structured clinical data dictionary
        """
        transcript = self.format_transcript(script)
        prompt = EXTRACTION_PROMPT.format(transcript=transcript)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text.strip()

        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if content.startswith("```"):
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

            # Find JSON object
            if not content.startswith("{"):
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    content = match.group(0)

            return json.loads(content)

        except Exception as e:
            raise ValueError(f"Failed to parse ground truth: {e}\nResponse: {content[:500]}")

    def extract_minimal(self, script: List[Dict]) -> Dict[str, Any]:
        """
        Extract minimal ground truth (faster, less detailed).
        Good for quick validation or when full extraction isn't needed.

        Args:
            script: List of dialogue lines

        Returns:
            Minimal structured data
        """
        transcript = self.format_transcript(script)

        minimal_prompt = f"""Extract key clinical data from this transcript. Return JSON only.

TRANSCRIPT:
{transcript}

Return:
{{
  "chief_complaint": "...",
  "diagnoses": ["..."],
  "medications_prescribed": [{{"name": "...", "dose": "...", "frequency": "...", "duration": "..."}}],
  "allergies": [{{"allergen": "...", "reaction": "..."}}],
  "follow_up": "...",
  "return_precautions": ["..."]
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": minimal_prompt}]
        )

        content = response.content[0].text.strip()

        try:
            if content.startswith("```"):
                content = re.search(r'\{[\s\S]*\}', content).group(0)
            elif not content.startswith("{"):
                content = re.search(r'\{[\s\S]*\}', content).group(0)
            return json.loads(content)
        except Exception as e:
            raise ValueError(f"Failed to parse minimal ground truth: {e}")


def clean_ground_truth(ground_truth: Dict) -> Dict:
    """
    Clean ground truth by removing null/empty fields.
    Makes the output more readable.
    """
    def clean_value(v):
        if v is None:
            return None
        if isinstance(v, dict):
            cleaned = {k: clean_value(val) for k, val in v.items()}
            cleaned = {k: val for k, val in cleaned.items() if val is not None}
            return cleaned if cleaned else None
        if isinstance(v, list):
            cleaned = [clean_value(item) for item in v if item is not None]
            cleaned = [item for item in cleaned if item]
            return cleaned if cleaned else None
        if isinstance(v, str):
            v = v.strip()
            return v if v and v.lower() not in ["null", "none", "n/a", "not mentioned"] else None
        return v

    return clean_value(ground_truth) or {}


def validate_ground_truth(ground_truth: Dict) -> Dict[str, Any]:
    """
    Validate ground truth for completeness.

    Returns:
        Dictionary with validation results
    """
    issues = []
    completeness = {}

    # Check required fields
    required = ["chief_complaint", "assessment", "plan"]
    for field in required:
        if not ground_truth.get(field):
            issues.append(f"Missing required field: {field}")
        else:
            completeness[field] = True

    # Check plan has medications or explanation
    plan = ground_truth.get("plan", {})
    if isinstance(plan, dict):
        has_meds = bool(plan.get("medications_prescribed"))
        has_orders = bool(plan.get("orders"))
        has_followup = bool(plan.get("follow_up"))

        if not (has_meds or has_orders):
            issues.append("Plan has no medications or orders")

        if not has_followup:
            issues.append("No follow-up plan specified")

    # Check allergies documented
    if not ground_truth.get("allergies"):
        issues.append("Allergies not documented (should be NKDA if none)")

    # Calculate completeness score
    all_sections = [
        "chief_complaint", "history_of_present_illness", "review_of_systems",
        "past_medical_history", "allergies", "medications", "physical_exam",
        "assessment", "plan"
    ]
    filled = sum(1 for s in all_sections if ground_truth.get(s))
    completeness_score = filled / len(all_sections)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "completeness_score": completeness_score,
        "sections_present": filled,
        "sections_total": len(all_sections)
    }
