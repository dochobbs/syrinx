#!/usr/bin/env python3
"""
Syrinx - Synthetic Pediatric Encounter Generator

Generate realistic doctor-patient encounter scripts with optional
error injection for AI scribe training and medical education.

Usage:
    python syrinx.py generate --nl "acute visit, anxious mom, 6mo fever, doctor misses allergy"
    python syrinx.py generate --patient patients/olivia.json --chief-complaint "fever x2 days"
    python syrinx.py errors list
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.input_parser import (
    EncounterSpec, PatientProfile, EncounterType, ParticipantConfig,
    ErrorSpec, parse_encounter_type, parse_participants, parse_error_string
)
from core.script_generator import ScriptGenerator
from core.error_injector import ErrorInjector, ERROR_CATALOG
from core.encounter_builder import EncounterBuilder


def cmd_generate(args):
    """Handle generate command."""
    print("Syrinx - Generating Encounter")
    print("=" * 40)

    # Initialize generator
    try:
        generator = ScriptGenerator()
    except ValueError as e:
        print(f"Error: {e}")
        print("Set ANTHROPIC_API_KEY environment variable")
        return 1

    builder = EncounterBuilder(output_dir=args.output_dir)

    # Build encounter spec
    if args.nl:
        # Natural language mode
        print(f"Parsing: {args.nl[:60]}...")
        spec = generator.parse_natural_language(args.nl)
        print(f"  Type: {spec.encounter_type.value}")
        print(f"  Patient: {spec.patient_age}")
        print(f"  Complaint: {spec.chief_complaint}")
        if spec.errors:
            print(f"  Errors: {[e.error_type for e in spec.errors]}")
    else:
        # Structured mode
        spec = _build_spec_from_args(args)

    # Load patient profile if specified
    if args.patient:
        print(f"Loading patient: {args.patient}")
        spec.patient_profile = PatientProfile.from_json(args.patient)
        print(f"  Name: {spec.patient_profile.name}")
        print(f"  Age: {spec.patient_profile.age}")
        if spec.patient_profile.allergies:
            print(f"  Allergies: {spec.patient_profile.allergies}")

    # Generate script
    print("\nGenerating script with Claude...")
    try:
        result = generator.generate_script(spec)
        script = result.get("script", [])
        print(f"  Generated {len(script)} dialogue lines")
    except Exception as e:
        print(f"Error generating script: {e}")
        return 1

    # Build encounter JSON
    encounter = builder.build_encounter(spec, script)

    # Save encounter
    filepath = builder.save_encounter(encounter, args.output_dir)
    print(f"\nSaved: {filepath}")

    # Generate audio if requested
    if args.audio:
        print("\nGenerating audio...")
        audio_path = _generate_audio(filepath, args.audio_dir)
        if audio_path:
            print(f"Audio: {audio_path}")

    print("\nDone!")
    return 0


def cmd_errors(args):
    """Handle errors command."""
    injector = ErrorInjector()

    if args.errors_action == "list":
        category = args.category if hasattr(args, 'category') else None

        print("Available Error Types")
        print("=" * 50)

        for cat in ["clinical", "communication", "documentation"]:
            if category and cat != category:
                continue

            print(f"\n{cat.upper()}")
            print("-" * 30)

            for template in injector.list_errors(cat):
                print(f"  {template.error_type}")
                print(f"    {template.description}")

    return 0


def cmd_personas(args):
    """Handle personas command."""
    print("Parent Personas")
    print("=" * 40)
    print("\nCommon styles to use with --parent-style:")
    print()
    personas = [
        ("anxious", "Worried, asks many questions, needs reassurance"),
        ("calm", "Relaxed, trusts doctor, provides clear information"),
        ("experienced", "Has older children, knows what to expect"),
        ("first-time", "New parent, uncertain, asks basic questions"),
        ("dismissive", "Downplays symptoms, reluctant to seek care"),
        ("demanding", "Expects specific treatment, may push back"),
        ("overwhelmed", "Stressed, may have trouble focusing"),
        ("detailed", "Provides thorough history, organized"),
    ]
    for style, desc in personas:
        print(f"  {style:15} - {desc}")

    return 0


def cmd_patients(args):
    """Handle patients command."""
    patients_dir = Path("patients")

    if args.patients_action == "list":
        print("Patient Profiles")
        print("=" * 40)

        if not patients_dir.exists():
            print("No patients directory found")
            return 0

        for f in sorted(patients_dir.glob("*.json")):
            try:
                profile = PatientProfile.from_json(str(f))
                print(f"\n  {f.name}")
                print(f"    {profile.name}, {profile.age}, {profile.sex}")
                if profile.allergies:
                    print(f"    Allergies: {', '.join(profile.allergies)}")
            except Exception as e:
                print(f"\n  {f.name} - Error: {e}")

    return 0


def _build_spec_from_args(args) -> EncounterSpec:
    """Build EncounterSpec from CLI arguments."""
    # Parse encounter type
    enc_type = EncounterType.ACUTE
    if args.encounter_type:
        enc_type = parse_encounter_type(args.encounter_type)

    # Parse participants
    participants = ParticipantConfig.PARENT_INFANT
    if args.participants:
        participants = parse_participants(args.participants)

    # Parse errors
    errors = []
    if args.error:
        for err_str in args.error:
            errors.append(parse_error_string(err_str))

    return EncounterSpec(
        encounter_type=enc_type,
        chief_complaint=args.chief_complaint or "routine visit",
        patient_name=args.patient_name or "",
        patient_age=args.patient_age or "12 months",
        patient_sex=args.patient_sex or "",
        parent_style=args.parent_style or "concerned",
        doctor_style=args.doctor_style or "warm, thorough",
        doctor_gender=args.doctor_gender or "female",
        participants=participants,
        duration_tier=args.duration or "medium",
        errors=errors
    )


def _generate_audio(encounter_path: str, audio_dir: str) -> str:
    """Generate audio from encounter JSON using existing generate_audio.py"""
    try:
        # Import the audio generator
        from generate_audio import process_encounter

        os.makedirs(audio_dir, exist_ok=True)
        return process_encounter(encounter_path, audio_dir, verbose=True)
    except ImportError:
        print("  Warning: generate_audio.py not found")
        return None
    except Exception as e:
        print(f"  Audio generation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Syrinx - Synthetic Pediatric Encounter Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Natural language generation
  python syrinx.py generate --nl "acute visit with anxious mom, 6mo with fever"

  # With patient profile
  python syrinx.py generate --patient patients/olivia.json --chief-complaint "fever"

  # Structured with errors
  python syrinx.py generate --encounter-type acute --patient-age "6 months" \\
      --chief-complaint "fever x2 days" --error clinical:missed-allergy

  # List available errors
  python syrinx.py errors list
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate an encounter")
    gen_parser.add_argument("--nl", help="Natural language description")
    gen_parser.add_argument("--patient", help="Path to patient profile JSON")
    gen_parser.add_argument("--encounter-type", "-t", help="acute, well-child, mental-health, follow-up")
    gen_parser.add_argument("--patient-age", help="Patient age (e.g., '6 months', '4 years')")
    gen_parser.add_argument("--patient-name", help="Patient name")
    gen_parser.add_argument("--patient-sex", help="Patient sex (male/female)")
    gen_parser.add_argument("--chief-complaint", "-c", help="Chief complaint / reason for visit")
    gen_parser.add_argument("--parent-style", help="Parent communication style")
    gen_parser.add_argument("--doctor-style", help="Doctor communication style")
    gen_parser.add_argument("--doctor-gender", help="Doctor gender for voice (male/female)")
    gen_parser.add_argument("--participants", "-p", help="Participant config")
    gen_parser.add_argument("--error", "-e", action="append", help="Error to inject (category:type)")
    gen_parser.add_argument("--duration", "-d", help="Duration tier: short, medium, long")
    gen_parser.add_argument("--output-dir", "-o", default="encounters", help="Output directory")
    gen_parser.add_argument("--audio", "-a", action="store_true", help="Also generate audio")
    gen_parser.add_argument("--audio-dir", default="audio_output", help="Audio output directory")

    # Errors command
    err_parser = subparsers.add_parser("errors", help="List available errors")
    err_sub = err_parser.add_subparsers(dest="errors_action")
    err_list = err_sub.add_parser("list", help="List all error types")
    err_list.add_argument("--category", help="Filter by category")

    # Personas command
    pers_parser = subparsers.add_parser("personas", help="List parent personas")

    # Patients command
    pat_parser = subparsers.add_parser("patients", help="Manage patient profiles")
    pat_sub = pat_parser.add_subparsers(dest="patients_action")
    pat_sub.add_parser("list", help="List patient profiles")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "errors":
        return cmd_errors(args)
    elif args.command == "personas":
        return cmd_personas(args)
    elif args.command == "patients":
        return cmd_patients(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
