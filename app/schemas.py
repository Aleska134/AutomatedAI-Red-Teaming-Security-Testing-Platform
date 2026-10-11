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
    full_chat_history: list[ChatMessage]


class AddToCartRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    coupon_code: str | None = Field(default=None, max_length=50)


class CustomerChatRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=8_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class CustomerChatResponse(BaseModel):
    customer_id: str
    reply: str
    history: list[ChatMessage]
    tool_events: list[dict] = Field(default_factory=list)
