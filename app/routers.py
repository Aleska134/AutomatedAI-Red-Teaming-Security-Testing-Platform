import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.agents.defender import query_defender
from app.auth.dependencies import require_active_company
from app.database import sessions_collection
from app.schemas import (
    AddToCartRequest,
    CheckoutRequest,
    CustomerChatRequest,
    CustomerChatResponse,
    SimulationLoopRequest,
    SimulationQueuedResponse,
    WebhookTestRequest,
    WebhookTestResponse,
)
from app.services.accounts import list_companies
from app.services.commerce import (
    CommerceError,
    add_to_cart,
    checkout_cart,
    ensure_sandbox_customer,
    get_or_create_cart,
    search_products,
)
from app.services.security_evaluation import evaluate_webhook_metadata
from app.services.simulation_loop import execute_simulation_run
from app.services.targets import get_target
from app.services.test_runs import create_test_run, get_test_run, list_test_runs
from app.services.webhook_adapter import WebhookAdapterError, send_webhook_message

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation & Data Endpoints"]
)


def _sandbox_customer(principal: dict) -> str:
    """The caller's customer ID always comes from its token, never the body."""
    return ensure_sandbox_customer(principal["company"]["company_id"])


@router.post(
    "/commerce/chat",
    response_model=CustomerChatResponse,
    summary="Send a message to the commerce support agent",
)
def commerce_chat(
    payload: CustomerChatRequest,
    principal: dict = Depends(require_active_company),
):
    customer_id = _sandbox_customer(principal)
    get_or_create_cart(customer_id)

    history = [message.model_dump() for message in payload.history]
    tool_events: list[dict] = []
    defense_outcome: dict = {}
    reply = query_defender(
        payload.message,
        chat_history=history,
        customer_id=customer_id,
        tool_events=tool_events,
        defense_outcome=defense_outcome,
    )
    return {
        "customer_id": customer_id,
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


@router.get("/commerce/cart", summary="Get the company's sandbox cart")
def get_cart(principal: dict = Depends(require_active_company)):
    return get_or_create_cart(_sandbox_customer(principal))


@router.post("/commerce/carts/items", summary="Add an item to the sandbox cart")
def add_cart_item(
    payload: AddToCartRequest,
    principal: dict = Depends(require_active_company),
):
    try:
        return add_to_cart(
            _sandbox_customer(principal),
            payload.product_id,
            payload.quantity,
        )
    except CommerceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/commerce/checkout", summary="Check out the sandbox cart")
def checkout(
    payload: CheckoutRequest,
    principal: dict = Depends(require_active_company),
):
    try:
        return checkout_cart(_sandbox_customer(principal), payload.coupon_code)
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

@router.post(
    "/simulation/loop",
    response_model=SimulationQueuedResponse,
    status_code=202,
    summary="Queue an attacker-versus-defender simulation",
)
def run_automated_simulation_loop(
    payload: SimulationLoopRequest,
    background_tasks: BackgroundTasks,
    principal: dict = Depends(require_active_company),
):
    """
    Queues a multi-turn adversarial simulation bound to the selected strategy.
    It runs in the background; poll ``GET /test-runs/{run_id}`` for its status.
    """
    company_id = principal["company"]["company_id"]
    target = None
    if payload.target_id:
        target = get_target(company_id, payload.target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target not found.")
    run_id = f"loop-{uuid.uuid4().hex[:8]}"
    record = create_test_run(
        run_id=run_id,
        strategy=payload.strategy,
        turns_requested=payload.turns,
        company_id=company_id,
        target_id=payload.target_id,
    )
    background_tasks.add_task(
        execute_simulation_run,
        run_id,
        strategy=payload.strategy,
        turns=payload.turns,
        history=[message.model_dump() for message in payload.history],
        company_id=company_id,
        customer_id=_sandbox_customer(principal),
        target=target,
    )
    return {
        "run_id": run_id,
        "session_id": run_id,
        "status": record["status"],
        "created_at": record["created_at"],
    }

# --- History and Analytics Queries (Data Layer) ---

@router.get("/simulations", summary="Retrieve all simulation logs")
def get_all_simulations(principal: dict = Depends(require_active_company)):
    """
    Fetches the red teaming sessions visible to the caller (admins see all).
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
        # Numbers restart per company, so label each run with its owner.
        names = {c["company_id"]: c["name"] for c in list_companies()}
        return [{**r, "company_name": names.get(r.get("company_id"))} for r in records]
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
    Returns a single simulation record by its session ID.
    """
    for record in _scoped_sessions(principal):
        if record.get("session_id") == session_id:
            return record
    raise HTTPException(status_code=404, detail=f"Simulation session {session_id} not found.")

@router.get("/simulations/number/{sim_num}", summary="Get specific log by its sequence number")
def get_simulation_by_sequence_number(
    sim_num: int,
    company_id: str | None = None,
    principal: dict = Depends(require_active_company),
):
    """
    Returns a company's simulation by its sequence number. Numbers restart per
    company, so admins pass ``company_id`` to pick one (default: their own).
    """
    own_company = principal["company"]["company_id"]
    scope = company_id if company_id and _is_admin(principal) else own_company
    for record in _scoped_sessions(principal):
        if record.get("company_id") == scope and record.get("simulation_number") == sim_num:
            return record
    raise HTTPException(status_code=404, detail=f"Simulation #{sim_num} does not exist.")