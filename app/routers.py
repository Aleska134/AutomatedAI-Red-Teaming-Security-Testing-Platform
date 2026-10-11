import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_active_company
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
    WebhookTestRequest,
    WebhookTestResponse,
)
from app.services.commerce import (
    CommerceError,
    add_to_cart,
    checkout_cart,
    get_or_create_cart,
    search_products,
)
from app.services.test_runs import (
    complete_test_run,
    create_test_run,
    fail_test_run,
    get_test_run,
    list_test_runs,
    start_test_run,
)
from app.services.security_evaluation import evaluate_webhook_metadata
from app.services.webhook_adapter import WebhookAdapterError, send_webhook_message

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


@router.post(
    "/integrations/webhook/test",
    response_model=WebhookTestResponse,
    summary="Test a merchant chatbot through the v1 webhook contract",
)
def test_webhook_integration(
    payload: WebhookTestRequest,
    _: dict = Depends(require_active_company),
):
    try:
        result = send_webhook_message(
            payload.webhook_url,
            message=payload.message,
            history=[message.model_dump() for message in payload.history],
            auth_token=payload.auth_token,
        )
    except WebhookAdapterError as error:
        return {
            "status": "failed",
            "scenario": "scope-boundary",
            "breached": False,
            "evidence": [],
            "error": str(error),
        }

    evaluation = evaluate_webhook_metadata(result["reply"], result.get("metadata"))
    return {
        "status": "completed",
        "scenario": "scope-boundary",
        "breached": evaluation["breached"],
        "evidence": evaluation["evidence"],
        "response": result["reply"],
        "security_outcome": evaluation.get("security_outcome"),
        "block_reason": evaluation.get("block_reason"),
        "metadata_available": evaluation.get("metadata_available", False),
    }

@router.post("/simulation/loop", response_model=LoopSimulationResponse)
def run_automated_simulation_loop(
    payload: SimulationLoopRequest,
    principal: dict = Depends(require_active_company),
):
    """
    Executes a multi-turn adversarial simulation loop where the attacker
    is bound to a user-selected offensive red-teaming strategy.
    """
    company_id = principal["company"]["company_id"]
    session_id = f"loop-{uuid.uuid4().hex[:8]}"
    run_record = create_test_run(
        run_id=session_id,
        strategy=payload.strategy,
        turns_requested=payload.turns,
        company_id=company_id,
    )
    run_record = start_test_run(session_id)
    current_history = [message.model_dump() for message in payload.history]
    tool_events: list[dict] = []
    defense_outcomes: list[dict] = []
    attack_generation_events: list[dict] = []
    turns_executed = 0
    
    try:
        for turn in range(payload.turns):
            turns_executed += 1
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
        next_simulation_number = existing_records_count
        session_record = {
            **run_record,
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
        # The identifiers are passed positionally; drop them from the payload so
        # they do not collide with the ``run_id`` parameter during binding.
        session_record.pop("run_id", None)
        session_record.pop("session_id", None)
        session_record = complete_test_run(session_id, **session_record)
        return {
            "session_id": session_id,
            "run_id": session_id,
            "status": session_record["status"],
            "run_type": session_record["run_type"],
            "strategy": session_record["strategy"],
            "created_at": session_record["created_at"],
            "started_at": session_record["started_at"],
            "completed_at": session_record["completed_at"],
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
            "full_chat_history": current_history,
        }
    except Exception as error:
        # Mark the run failed and return a clear, non-leaking message instead of
        # an opaque 500 so the dashboard can explain what happened.
        fail_test_run(session_id, str(error))
        raise HTTPException(
            status_code=502,
            detail=(
                "The security simulation could not be completed. This usually "
                "means the LLM provider is unavailable or the OPENAI_API_KEY is "
                "not configured. Deterministic checks still ran where possible."
            ),
        ) from error

# --- History and Analytics Queries (Data Layer) ---

@router.get("/simulations", summary="Retrieve all simulation logs")
def get_all_simulations(principal: dict = Depends(require_active_company)):
    """
    Fetches every red teaming session recorded in the local JSON database.
    Essential for parsing summary charts in the frontend dashboard.
    """
    records = _scoped_sessions(principal)
    return {"count": len(records), "data": records}


def _is_admin(principal: dict) -> bool:
    return principal["user"]["role"] == "admin"


def _scoped_sessions(principal: dict) -> list[dict]:
    """Return simulation records visible to the principal (admins see all)."""
    records = sessions_collection.all()
    if _is_admin(principal):
        return records
    company_id = principal["company"]["company_id"]
    return [r for r in records if r.get("company_id") == company_id]


@router.get("/test-runs", response_model=list[dict], summary="Retrieve persisted test runs")
def get_test_runs(principal: dict = Depends(require_active_company)):
    if _is_admin(principal):
        return list_test_runs()
    return list_test_runs(company_id=principal["company"]["company_id"])


@router.get("/test-runs/{run_id}", response_model=dict, summary="Retrieve one persisted test run")
def get_test_run_by_id(run_id: str, principal: dict = Depends(require_active_company)):
    scope = None if _is_admin(principal) else principal["company"]["company_id"]
    result = get_test_run(run_id, company_id=scope)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Test run {run_id} not found.")
    return result

@router.get("/simulations/{session_id}", summary="Get specific log by ID")
def get_simulation_by_id(
    session_id: str,
    principal: dict = Depends(require_active_company),
):
    """
    Queries TinyDB for a single evaluation profile matching the specified tracking token.
    """
    for record in _scoped_sessions(principal):
        if record.get("session_id") == session_id:
            return record
    raise HTTPException(status_code=404, detail=f"Simulation session {session_id} not found.")

@router.get("/simulations/number/{sim_num}", summary="Get specific log by its sequence number")
def get_simulation_by_sequence_number(
    sim_num: int,
    principal: dict = Depends(require_active_company),
):
    """
    Queries TinyDB for an evaluation profile matching the chronological sequence integer.
    """
    for record in _scoped_sessions(principal):
        if record.get("simulation_number") == sim_num:
            return record
    raise HTTPException(status_code=404, detail=f"Simulation #{sim_num} does not exist.")