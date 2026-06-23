import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.defender import query_defender
from app.agents.attacker import generate_attack_payload
from app.agents.judge import evaluate_simulation 
from app.database import sessions_collection      

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation & Data Endpoints"]
)

# --- Updated Schema to accept Attack Strategy ---
class SimulationLoopRequest(BaseModel):
    turns: int = 3  
    strategy: str = "social_engineering" # <-- Added payload field with a default value
    history: list = []  

class LoopSimulationResponse(BaseModel):
    session_id: str
    simulation_number: int 
    total_turns_executed: int
    is_breached: bool
    attacker_aggression_level: int
    defense_efficiency_score: int
    attack_vector_keywords: list
    audit_analysis: str
    confidence: float
    full_chat_history: list

@router.post("/simulation/loop", response_model=LoopSimulationResponse)
def run_automated_simulation_loop(payload: SimulationLoopRequest):
    """
    Executes a multi-turn adversarial simulation loop where the attacker
    is bound to a user-selected offensive red-teaming strategy.
    """
    if payload.turns < 1 or payload.turns > 5:
        raise HTTPException(status_code=400, detail="Turns must be between 1 and 5 to optimize API execution.")
        
    # Validate that the requested strategy is supported
    valid_strategies = ["social_engineering", "authority_override", "jailbreak_dan", "roleplay_hypothetical"]
    if payload.strategy not in valid_strategies:
        raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid_strategies}")
        
    current_history = list(payload.history)
    turns_executed = 0
    
    for turn in range(payload.turns):
        turns_executed += 1
        
        # Pass the requested strategy directly into our updated attacker model
        attacker_message = generate_attack_payload(current_history, strategy=payload.strategy)
        current_history.append({"role": "user", "content": attacker_message})
        
        defender_reply = query_defender(attacker_message, current_history[:-1])
        current_history.append({"role": "assistant", "content": defender_reply})
        
    audit_report = evaluate_simulation(current_history)
    
    existing_records_count = len(sessions_collection.all())
    next_simulation_number = existing_records_count + 1
    
    session_id = f"loop-{str(uuid.uuid4())[:8]}"
    
    session_record = {
        "session_id": session_id,
        "simulation_number": next_simulation_number, 
        "total_turns": turns_executed,
        "history": current_history,
        "breached": audit_report.get("breached", False),
        "confidence_score": audit_report.get("confidence_score", 0.0),
        "attacker_aggression_level": audit_report.get("attacker_aggression_level", 1),
        "defense_efficiency_score": audit_report.get("defense_efficiency_score", 10),
        "attack_vector_keywords": audit_report.get("attack_vector_keywords", []),
        "analysis": audit_report.get("analysis", "No analysis provided.")
    }
    
    sessions_collection.insert(session_record)
    
    return {
        "session_id": session_id,
        "simulation_number": session_record["simulation_number"],
        "total_turns_executed": turns_executed,
        "is_breached": session_record["breached"],
        "attacker_aggression_level": session_record["attacker_aggression_level"],
        "defense_efficiency_score": session_record["defense_efficiency_score"],
        "attack_vector_keywords": session_record["attack_vector_keywords"],
        "audit_analysis": session_record["analysis"],
        "confidence": session_record["confidence_score"],
        "full_chat_history": current_history
    }

# --- History and Analytics Queries (Data Layer) ---

@router.get("/simulations", summary="Retrieve all simulation logs")
def get_all_simulations():
    """
    Fetches every red teaming session recorded in the local JSON database.
    Essential for parsing summary charts in the frontend dashboard.
    """
    records = sessions_collection.all()
    return {"count": len(records), "data": records}

@router.get("/simulations/{session_id}", summary="Get specific log by ID")
def get_simulation_by_id(session_id: str):
    """
    Queries TinyDB for a single evaluation profile matching the specified tracking token.
    """
    from tinydb import Query
    Session = Query()
    result = sessions_collection.search(Session.session_id == session_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Simulation session {session_id} not found.")
    return result[0]

@router.get("/simulations/number/{sim_num}", summary="Get specific log by its sequence number")
def get_simulation_by_sequence_number(sim_num: int):
    """
    Queries TinyDB for an evaluation profile matching the chronological sequence integer.
    """
    from tinydb import Query
    Session = Query()
    result = sessions_collection.search(Session.simulation_number == sim_num)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Simulation #{sim_num} does not exist.")
    return result[0]