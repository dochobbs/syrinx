#!/usr/bin/env python3
"""
Syrinx Web Server
FastAPI server for the Syrinx medical encounter simulator.
"""

import os
import json
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import anthropic

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from core.input_parser import EncounterSpec, PatientProfile, parse_error_string
from core.script_generator import ScriptGenerator
from core.encounter_builder import EncounterBuilder
from core.ground_truth import GroundTruthExtractor

# ============================================
# CONFIG
# ============================================

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"
ENCOUNTERS_DIR = BASE_DIR / "encounters"
AUDIO_DIR = BASE_DIR / "audio_output"

# Ensure directories exist
ENCOUNTERS_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

# ============================================
# APP
# ============================================

app = FastAPI(
    title="Syrinx",
    description="Medical Encounter Simulator",
    version="1.0.0"
)

# Serve static files
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

# ============================================
# MODELS
# ============================================

class GenerateRequest(BaseModel):
    description: str
    duration: str = "medium"
    error_type: Optional[str] = None
    patient: Optional[Dict[str, Any]] = None

class AudioRequest(BaseModel):
    encounter_id: str

class MessageRequest(BaseModel):
    session_id: str
    role: str
    message: str
    history: List[Dict[str, Any]] = []

class SessionConfig(BaseModel):
    role: str
    scenario: Dict[str, Any]

# ============================================
# STATE
# ============================================

# Active WebSocket sessions
active_sessions: Dict[str, Dict] = {}

# Cached encounters
encounters_cache: Dict[str, Dict] = {}

# ============================================
# ROUTES - STATIC
# ============================================

@app.get("/")
async def root():
    """Serve the main web app."""
    return FileResponse(WEB_DIR / "index.html")

@app.get("/styles.css")
async def styles():
    """Serve CSS."""
    return FileResponse(WEB_DIR / "styles.css", media_type="text/css")

@app.get("/app.js")
async def app_js():
    """Serve JavaScript."""
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")

# ============================================
# ROUTES - GENERATION
# ============================================

@app.post("/api/generate")
async def generate_encounter(request: GenerateRequest):
    """Generate a new encounter from natural language description."""
    try:
        generator = ScriptGenerator()
        builder = EncounterBuilder(output_dir=str(ENCOUNTERS_DIR))

        # Parse natural language to spec
        spec = generator.parse_natural_language(request.description)

        # Override duration if specified
        spec.duration_tier = request.duration

        # Add error injection if specified
        if request.error_type:
            error = parse_error_string(f"clinical:{request.error_type}")
            spec.errors = [error]

        # Add patient context if provided
        if request.patient:
            try:
                spec.patient_profile = PatientProfile.from_dict(request.patient)
            except Exception:
                # Try Oread format
                spec.patient_profile = parse_oread_patient(request.patient)

        # Generate script
        result = generator.generate_script(spec)
        script = result.get("script", [])

        # Build encounter
        encounter = builder.build_encounter(spec, script)

        # Save encounter
        filepath = builder.save_encounter(encounter)

        # Cache it
        encounter_id = encounter["metadata"]["id"]
        encounters_cache[encounter_id] = encounter

        return encounter

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/audio")
async def generate_audio(request: AudioRequest):
    """Generate TTS audio for an encounter."""
    encounter_id = request.encounter_id

    # Find the encounter file
    encounter_files = list(ENCOUNTERS_DIR.glob(f"{encounter_id}*.json"))
    if not encounter_files:
        raise HTTPException(status_code=404, detail="Encounter not found")

    encounter_file = encounter_files[0]

    try:
        # Import audio generator
        from generate_audio import process_encounter

        # Generate audio
        audio_path = process_encounter(str(encounter_file), str(AUDIO_DIR), verbose=False)

        if audio_path:
            # Return relative URL
            audio_filename = Path(audio_path).name
            return {"audio_url": f"/audio/{audio_filename}"}
        else:
            raise HTTPException(status_code=500, detail="Audio generation failed")

    except ImportError:
        raise HTTPException(status_code=500, detail="Audio generation not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serve generated audio files."""
    audio_path = AUDIO_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(audio_path, media_type="audio/wav")

# ============================================
# ROUTES - INTERACTIVE SESSION
# ============================================

@app.websocket("/api/session")
async def session_websocket(websocket: WebSocket):
    """WebSocket endpoint for interactive sessions."""
    await websocket.accept()

    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "role": None,
        "scenario": None,
        "history": [],
        "client": None
    }

    try:
        # Initialize Anthropic client
        session["client"] = anthropic.Anthropic()

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "init":
                # Initialize session
                session["role"] = data.get("role")
                session["scenario"] = data.get("scenario")

                # Send initial message
                initial = get_ai_initial_message(session)
                await websocket.send_json({
                    "type": "message",
                    "text": initial
                })
                session["history"].append({
                    "role": "assistant",
                    "content": initial
                })

            elif msg_type == "message":
                # User sent a message
                user_text = data.get("text", "")
                session["history"].append({
                    "role": "user",
                    "content": user_text
                })

                # Generate AI response
                response = await generate_ai_response(session)

                await websocket.send_json({
                    "type": "message",
                    "text": response
                })
                session["history"].append({
                    "role": "assistant",
                    "content": response
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if session_id in active_sessions:
            del active_sessions[session_id]

@app.post("/api/session/message")
async def session_message(request: MessageRequest):
    """REST fallback for interactive messages."""
    try:
        client = anthropic.Anthropic()

        # Build conversation history
        messages = []
        for msg in request.history:
            role = "assistant" if msg.get("sender") == "ai" else "user"
            messages.append({
                "role": role,
                "content": msg.get("text", "")
            })

        # Add new message
        messages.append({
            "role": "user",
            "content": request.message
        })

        # Get system prompt based on role
        system = get_session_system_prompt(request.role, None)

        # Generate response
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system,
            messages=messages
        )

        response_text = response.content[0].text

        return {
            "response": response_text,
            "audio_url": None  # TODO: Generate TTS
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ROUTES - EXPORT
# ============================================

@app.get("/api/export/{encounter_id}")
async def export_encounter(encounter_id: str, format: str = "json"):
    """Export encounter in various formats."""
    # Find encounter
    encounter_files = list(ENCOUNTERS_DIR.glob(f"{encounter_id}*.json"))
    if not encounter_files:
        raise HTTPException(status_code=404, detail="Encounter not found")

    with open(encounter_files[0]) as f:
        encounter = json.load(f)

    if format == "json":
        return encounter

    elif format == "markdown":
        md = encounter_to_markdown(encounter)
        return JSONResponse(content={"markdown": md})

    elif format == "fhir":
        fhir = encounter_to_fhir(encounter)
        return fhir

    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")

# ============================================
# HELPERS
# ============================================

def parse_oread_patient(data: Dict) -> PatientProfile:
    """Parse Oread patient format to Syrinx PatientProfile."""
    demographics = data.get("demographics", {})

    given_names = demographics.get("given_names", [])
    name = given_names[0] if given_names else "Patient"

    # Calculate age from DOB
    dob = demographics.get("date_of_birth")
    if dob:
        from datetime import date
        birth = date.fromisoformat(dob)
        today = date.today()
        age_years = today.year - birth.year
        age_months = (today.year - birth.year) * 12 + today.month - birth.month
        if age_years < 2:
            age = f"{age_months} months"
        else:
            age = f"{age_years} years"
    else:
        age = "unknown"

    sex = demographics.get("sex_at_birth", "unknown")

    # Get medical history
    allergies = []
    for allergy in data.get("allergy_list", []):
        name_str = allergy.get("display_name", "")
        reaction = allergy.get("reactions", [{}])[0].get("manifestation", "")
        allergies.append(f"{name_str} - {reaction}" if reaction else name_str)

    medications = []
    for med in data.get("medication_list", []):
        medications.append(med.get("display_name", ""))

    conditions = []
    for condition in data.get("problem_list", []):
        conditions.append(condition.get("code", {}).get("display", ""))

    return PatientProfile(
        name=name,
        age=age,
        sex=sex,
        allergies=allergies,
        medications=medications,
        chronic_conditions=conditions
    )

def get_session_system_prompt(role: str, scenario: Optional[Dict]) -> str:
    """Get system prompt for interactive session based on role."""
    scenario_desc = ""
    if scenario:
        scenario_desc = scenario.get("description", scenario.get("title", ""))

    if role == "doctor":
        # User is doctor, AI plays parent/patient
        return f"""You are roleplaying as a worried parent bringing your child to see a pediatrician.

Scenario: {scenario_desc}

Guidelines:
- Stay in character as a concerned parent
- Describe symptoms naturally, don't over-explain
- React emotionally but appropriately to what the doctor says
- Include realistic details like the child's behavior
- If asked medical history, provide realistic answers
- Don't be overly compliant - have some realistic concerns and questions
- Keep responses conversational, 1-3 sentences typically
- Occasionally mention the child's reactions (fussy, crying, calm, etc.)

Do NOT break character or explain what you're doing. Just respond as the parent would."""

    else:
        # User is parent, AI plays doctor
        return f"""You are roleplaying as a pediatrician seeing a patient.

Scenario: {scenario_desc}

Guidelines:
- Stay in character as a competent, caring pediatrician
- Ask appropriate history questions
- Explain things clearly without too much jargon
- Show empathy for parent concerns
- Make clinical observations based on the conversation
- Provide appropriate reassurance or concern based on symptoms
- Keep responses professional but warm, 1-3 sentences typically
- Occasionally describe what you're observing or doing (examining, listening, etc.)

Do NOT break character or explain what you're doing. Just respond as the doctor would."""

def get_ai_initial_message(session: Dict) -> str:
    """Get the AI's initial message to start the conversation."""
    role = session.get("role")
    scenario = session.get("scenario", {})

    if role == "doctor":
        # AI is parent, user is doctor
        scenario_type = scenario.get("type", "acute")
        if scenario_type == "acute":
            return "Hi doctor, thank you for seeing us. My child has been sick and I'm really worried."
        elif scenario_type == "well-child":
            return "Hi! We're here for the checkup. Everything seems fine but I do have a few questions."
        else:
            return "Hello, thank you for seeing us today. I've been concerned about some things."
    else:
        # AI is doctor, user is parent
        return "Hello, I'm Dr. Martinez. What brings you in today?"

async def generate_ai_response(session: Dict) -> str:
    """Generate AI response using Claude."""
    client = session.get("client")
    if not client:
        return "Sorry, I'm having trouble responding right now."

    system = get_session_system_prompt(session.get("role"), session.get("scenario"))
    history = session.get("history", [])

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system,
            messages=history
        )
        return response.content[0].text
    except Exception as e:
        print(f"AI response error: {e}")
        return "I'm sorry, could you repeat that?"

def encounter_to_markdown(encounter: Dict) -> str:
    """Convert encounter to Markdown format."""
    m = encounter.get("metadata", {})
    md = f"# {m.get('id', 'Encounter')}\n\n"
    md += f"**Type:** {m.get('encounter_type', 'unknown')}\n"
    md += f"**Patient:** {m.get('patient_name', 'unknown')}, {m.get('patient_age', 'unknown')}\n"
    md += f"**Chief Complaint:** {m.get('chief_complaint', 'unknown')}\n\n"
    md += "## Transcript\n\n"

    for line in encounter.get("script", []):
        speaker = line.get("speaker", "unknown").upper()
        text = line.get("text", "")
        direction = line.get("direction", "")
        md += f"**{speaker}:** {text}"
        if direction:
            md += f" _[{direction}]_"
        md += "\n\n"

    return md

def encounter_to_fhir(encounter: Dict) -> Dict:
    """Convert encounter to FHIR R4 Encounter resource."""
    m = encounter.get("metadata", {})

    # Basic FHIR Encounter structure
    fhir = {
        "resourceType": "Encounter",
        "id": m.get("id", str(uuid.uuid4())),
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "type": [{
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "185349003",
                "display": "Encounter for check up"
            }],
            "text": m.get("encounter_type", "clinical encounter")
        }],
        "subject": {
            "display": m.get("patient_name", "Patient")
        },
        "reasonCode": [{
            "text": m.get("chief_complaint", "")
        }],
        "period": {
            "start": encounter.get("_generated", {}).get("timestamp", datetime.now().isoformat())
        }
    }

    return fhir

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
