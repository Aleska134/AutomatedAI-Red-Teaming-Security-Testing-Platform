import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.defender import query_defender
from app.agents.attacker import generate_attack_payload
from app.agents.judge import evaluate_simulation # <-- Imported the Judge logic
from app.database import sessions_collection      # <-- Imported our TinyDB table

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation Endpoints"]
)

class MessageRequest(BaseModel):
    message: str = ""
    history: list = []

class FullSimulationResponse(BaseModel):
    session_id: str
    attacker_message: str
    defender_reply: str
    is_breached: bool
    audit_analysis: str
    confidence: float

@router.post("/simulation/run-step", response_model=FullSimulationResponse)
def run_full_automated_step(payload: MessageRequest):
    """
    Executes a fully automated pipeline turn: 
    1. Attacker attacks. 
    2. Defender protects. 
    3. Judge evaluates the compliance breach.
    4. TinyDB logs the session results locally.
    """
    # 1. Generate attack vector based on past turns
    attacker_message = generate_attack_payload(payload.history)
    
    # 2. Build updated history array
    updated_history = list(payload.history)
    updated_history.append({"role": "user", "content": attacker_message})
    
    # 3. Query the security shield (Defender Bot)
    defender_reply = query_defender(attacker_message, payload.history)
    updated_history.append({"role": "assistant", "content": defender_reply})
    
    # 4. Trigger the Judge Bot audit process
    audit_report = evaluate_simulation(updated_history)
    
    # 5. Generate a unique session tracking token
    session_id = str(uuid.uuid4())[:8]
    
    # 6. Prepare the session payload structure for local persistence
    session_record = {
        "session_id": session_id,
        "history": updated_history,
        "breached": audit_report.get("breached", False),
        "confidence_score": audit_report.get("confidence_score", 0.0),
        "analysis": audit_report.get("analysis", "No analysis provided.")
    }
    
    # 7. Write directly to our local local_db.json file via TinyDB
    sessions_collection.insert(session_record)
    
    return {
        "session_id": session_id,
        "attacker_message": attacker_message,
        "defender_reply": defender_reply,
        "is_breached": session_record["breached"],
        "audit_analysis": session_record["analysis"],
        "confidence": session_record["confidence_score"]
    }