from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.defender import query_defender
from app.agents.attacker import generate_attack_payload # <-- Imported the attacker logic

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation Endpoints"]
)

class MessageRequest(BaseModel):
    message: str
    history: list = []

class SimulationTurnResponse(BaseModel):
    attacker_message: str
    defender_reply: str
    updated_history: list

@router.post("/defender/chat")
def chat_with_defender(payload: MessageRequest):
    """
    Endpoint to manually test a single payload against the Defender Bot.
    """
    if not payload.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
        
    defender_response = query_defender(payload.message, payload.history)
    return {"defender_reply": defender_response}


@router.post("/simulation/step", response_model=SimulationTurnResponse)
def trigger_simulation_step(payload: MessageRequest):
    """
    Triggers an automated single turn where the Attacker Bot inspects the history,
    generates a payload, and the Defender Bot responds to it.
    """
    # 1. Let the Attacker Bot generate the next attack vector based on history
    attacker_message = generate_attack_payload(payload.history)
    
    # 2. Append the attacker's message to the temporary simulation history
    updated_history = list(payload.history)
    updated_history.append({"role": "user", "content": attacker_message})
    
    # 3. Pass the newly generated attack to the Defender Bot
    defender_reply = query_defender(attacker_message, payload.history)
    
    # 4. Append the defender's response to close the current conversational turn
    updated_history.append({"role": "assistant", "content": defender_reply})
    
    return {
        "attacker_message": attacker_message,
        "defender_reply": defender_reply,
        "updated_history": updated_history
    }