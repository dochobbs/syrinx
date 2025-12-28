# Syrinx Core Modules
from .input_parser import EncounterSpec, PatientProfile, parse_age_string
from .script_generator import ScriptGenerator
from .error_injector import ErrorInjector, ERROR_CATALOG
from .encounter_builder import EncounterBuilder
from .validator import (
    validate_error_injection,
    validation_summary,
    infer_targets,
    categorize_targets,
    ValidationResult
)
from .ground_truth import (
    GroundTruthExtractor,
    clean_ground_truth,
    validate_ground_truth
)
