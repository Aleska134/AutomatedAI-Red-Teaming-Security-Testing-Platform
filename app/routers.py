from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.defender import query_defender

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation Endpoint"]
)

# Definimos qué datos esperamos recibir en la petición utilizando Pydantic
class MessageRequest(BaseModel):
    message: str
    history: list = [] # Opcional: lista de mensajes previos [{"role": "user", "content": "..."}]

@router.post("/defender/chat")
def chat_with_defender(payload: MessageRequest):
    """
    Endpoint to send a payload directly to the Defender Bot.
    Useful for testing if the defender can resist manual attacks before automating.
    """
    if not payload.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
        
    # Llamamos a la lógica de nuestra IA
    defender_response = query_defender(payload.message, payload.history)
    
    return {
        "defender_reply": defender_response
    }