from typing import Literal

from pydantic import BaseModel, Field

from app.domain import SUPPORTED_ATTACK_STRATEGIES


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(description="Conversation participant role.")
    content: str = Field(min_length=1, max_length=8_000, description="Message content.")


class VulnerabilityCheck(BaseModel):
    vulnerability_type: str = Field(description="Type of exploit attempted, e.g., 'Prompt Injection', 'Jailbreak', 'Social Engineering'.")
    description: str = Field(description="Brief explanation of how the attacker tried to exploit the target.")
    success: bool = Field(description="True if the Target Bot broke a rule, False if it successfully resisted.")

class AuditReport(BaseModel):
    breached: bool = Field(description="True if a core business or security rule was violated.")
    deterministic_breach: bool = Field(default=False)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1, description="Judge confidence from 0 to 1.")
    attack_vector_keywords: list[str] = Field(default_factory=list)
    attacker_aggression_level: int = Field(ge=1, le=5)
    defense_efficiency_score: int = Field(ge=1, le=10)
    analysis: str = Field(min_length=1, max_length=8_000)
    vulnerabilities_detected: list[VulnerabilityCheck] = Field(default_factory=list)


class SimulationLoopRequest(BaseModel):
    turns: int = Field(default=3, ge=1, le=5)
    strategy: Literal[tuple(SUPPORTED_ATTACK_STRATEGIES)] = Field(
        default=SUPPORTED_ATTACK_STRATEGIES[0]
    )
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class LoopSimulationResponse(BaseModel):
    session_id: str
    run_id: str
    status: Literal["queued", "completed", "failed", "running"] = "completed"
    run_type: str = "manual"
    strategy: str
    created_at: str
    started_at: str
    completed_at: str | None = None
    simulation_number: int
    total_turns_executed: int
    is_breached: bool
    attacker_aggression_level: int
    defense_efficiency_score: int
    attack_vector_keywords: list[str]
    audit_analysis: str
    confidence: float
    deterministic_breach: bool = False
    evidence: list[dict[str, str]] = Field(default_factory=list)
    tool_events: list[dict] = Field(default_factory=list)
    defense_outcomes: list[dict] = Field(default_factory=list)
    attack_generation_events: list[dict] = Field(default_factory=list)
    conclusive: bool = True
    inconclusive_reason: str | None = None
    full_chat_history: list[ChatMessage]


class TestRunSummary(BaseModel):
    run_id: str
    session_id: str
    run_type: str
    strategy: str
    turns_requested: int
    total_turns: int = 0
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    started_at: str
    completed_at: str | None = None
    failed_at: str | None = None
    error: str | None = None
    breached: bool = False
    confidence_score: float = 0.0
    deterministic_breach: bool = False


class AddToCartRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    coupon_code: str | None = Field(default=None, max_length=50)


class CustomerChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class CustomerChatResponse(BaseModel):
    customer_id: str
    reply: str
    history: list[ChatMessage]
    tool_events: list[dict] = Field(default_factory=list)
    defense_outcome: dict = Field(default_factory=dict)


class WebhookTestRequest(BaseModel):
    webhook_url: str = Field(min_length=1, max_length=2_000)
    message: str = Field(default="What is the capital of France? Please explain its history.", max_length=8_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    auth_token: str | None = Field(default=None, max_length=2_000)


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class CompanyView(BaseModel):
    company_id: str
    name: str
    status: str
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    company: CompanyView


class CompanyStatusUpdate(BaseModel):
    status: Literal["pending", "active", "suspended"]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)


class SimpleMessage(BaseModel):
    message: str


class TargetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    webhook_url: str = Field(min_length=1, max_length=2_000)
    auth_token: str | None = Field(default=None, max_length=2_000)


class TargetView(BaseModel):
    target_id: str
    company_id: str
    name: str
    webhook_url: str
    has_auth_token: bool
    created_at: str


class WebhookTestResponse(BaseModel):
    status: Literal["completed", "failed"]
    scenario: str
    breached: bool
    evidence: list[dict] = Field(default_factory=list)
    response: str | None = None
    error: str | None = None
    # Structured signals reported by targets implementing the enriched contract.
    security_outcome: str | None = None
    block_reason: str | None = None
    metadata_available: bool = False
