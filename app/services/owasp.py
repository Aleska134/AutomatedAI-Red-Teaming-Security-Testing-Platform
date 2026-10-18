"""Map deterministic findings to the OWASP Top 10 for LLM Applications (2025)."""

from typing import Any

OWASP_LLM_TOP10 = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM03": "Supply Chain",
    "LLM04": "Data and Model Poisoning",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM07": "System Prompt Leakage",
    "LLM08": "Vector and Embedding Weaknesses",
    "LLM09": "Misinformation",
    "LLM10": "Unbounded Consumption",
}

# Claims in replies (invented coupons, discounts, return terms) are
# misinformation; actions the target reports performing are excessive agency.
RULE_TO_OWASP = {
    "scope_boundary": "LLM01",
    "business_rule_bypass": "LLM01",
    "customer_data_access": "LLM02",
    "prompt_disclosure": "LLM07",
    "discount_limit": "LLM09",
    "business_discount_limit": "LLM09",
    "invented_coupon": "LLM09",
    "return_window": "LLM09",
    "unauthorized_checkout": "LLM06",
    "unauthorized_coupon_applied": "LLM06",
    "unauthorized_discount_applied": "LLM06",
    "forbidden_action": "LLM06",
}


def owasp_for(rule: str) -> dict[str, str] | None:
    """Return ``{"id", "name"}`` for a rule, or None when it is not mapped."""
    code = RULE_TO_OWASP.get(rule)
    if code is None:
        return None
    return {"id": code, "name": OWASP_LLM_TOP10[code]}


def owasp_label(rule: str) -> str:
    """Human-readable label such as ``LLM07: System Prompt Leakage``."""
    category = owasp_for(rule)
    return f"{category['id']}: {category['name']}" if category else "Unmapped"


def tag_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return evidence items with an ``owasp`` field added from their rule."""
    return [
        {**item, "owasp": owasp_for(str(item.get("rule", "")))}
        for item in evidence
    ]
