import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.agents.defender import query_defender
from app.agents.attacker import generate_attack_payload_result
from app.agents.judge import evaluate_simulation
from app.database import sessions_collection
from app.schemas import (
    AddToCartRequest,
    CheckoutRequest,
    CustomerChatRequest,
    CustomerChatResponse,
    LoopSimulationResponse,
    SimulationLoopRequest,
)
from app.services.commerce import (
    CommerceError,
    add_to_cart,
    checkout_cart,
    get_or_create_cart,
    search_products,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation & Data Endpoints"]
)


@router.post(
    "/commerce/chat",
    response_model=CustomerChatResponse,
    summary="Send a message to the commerce support agent",
)
def commerce_chat(payload: CustomerChatRequest):
    try:
        get_or_create_cart(payload.customer_id)
    except CommerceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    history = [message.model_dump() for message in payload.history]
    tool_events: list[dict] = []
    defense_outcome: dict = {}
    reply = query_defender(
        payload.message,
        chat_history=history,
        customer_id=payload.customer_id,
        tool_events=tool_events,
        defense_outcome=defense_outcome,
    )
    return {
        "customer_id": payload.customer_id,
        "reply": reply,
        "history": [
            *history,
            {"role": "user", "content": payload.message},
            {"role": "assistant", "content": reply},
        ],
        "tool_events": tool_events,
        "defense_outcome": defense_outcome,
    }


@router.get("/commerce/products", summary="Search the demo product catalog")
def list_products(search: str = ""):
    return {"data": search_products(search)}


@router.get("/commerce/carts/{customer_id}", summary="Get a customer's open cart")
def get_cart(customer_id: str):
    try:
        return get_or_create_cart(customer_id)
    except CommerceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/commerce/carts/items", summary="Add an item to a customer's cart")
def add_cart_item(payload: AddToCartRequest):
    try:
        return add_to_cart(
            payload.customer_id,
            payload.product_id,
            payload.quantity,
        )
    except CommerceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/commerce/checkout", summary="Check out a demo cart")
def checkout(payload: CheckoutRequest):
    try:
        return checkout_cart(payload.customer_id, payload.coupon_code)
    except CommerceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.post("/simulation/loop", response_model=LoopSimulationResponse)
def run_automated_simulation_loop(payload: SimulationLoopRequest):
    """
    Executes a multi-turn adversarial simulation loop where the attacker
    is bound to a user-selected offensive red-teaming strategy.
    """
    current_history = [message.model_dump() for message in payload.history]
    tool_events: list[dict] = []
    defense_outcomes: list[dict] = []
    attack_generation_events: list[dict] = []
    turns_executed = 0
    
    for turn in range(payload.turns):
        turns_executed += 1
        
        # Pass the requested strategy directly into our updated attacker model
        attack_result = generate_attack_payload_result(
            current_history,
            strategy=payload.strategy,
        )
        attacker_message = attack_result["payload"]
        attack_generation_events.append(
            {
                **attack_result,
                "turn": turns_executed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        current_history.append({"role": "user", "content": attacker_message})
        outcome: dict = {}
        defender_reply = query_defender(
            attacker_message,
            current_history[:-1],
            tool_events=tool_events,
            defense_outcome=outcome,
        )
        defense_outcomes.append(outcome)
        current_history.append({"role": "assistant", "content": defender_reply})
        
    audit_report = evaluate_simulation(current_history, tool_events)
    
    existing_records_count = len(sessions_collection.all())
    next_simulation_number = existing_records_count + 1
    
    session_id = f"loop-{uuid.uuid4().hex[:8]}"
    
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
        "analysis": audit_report.get("analysis", "No analysis provided."),
        "deterministic_breach": audit_report.get("deterministic_breach", False),
        "evidence": audit_report.get("evidence", []),
        "tool_events": tool_events,
        "defense_outcomes": defense_outcomes,
        "attack_generation_events": attack_generation_events,
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
        "deterministic_breach": session_record["deterministic_breach"],
        "evidence": session_record["evidence"],
        "tool_events": session_record["tool_events"],
        "defense_outcomes": session_record["defense_outcomes"],
        "attack_generation_events": session_record["attack_generation_events"],
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