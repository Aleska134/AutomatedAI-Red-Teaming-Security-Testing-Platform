"""Shared domain rules and values for the commerce security simulation."""

from enum import StrEnum

STORE_NAME = "TechMart"
MAX_DISCOUNT_PERCENT = 10
RETURN_WINDOW_DAYS = 30
STANDARD_COUPON_CODE = "TECH10"


class AttackStrategy(StrEnum):
    """Supported attacker behaviors exposed by the API."""

    SOCIAL_ENGINEERING = "social_engineering"
    AUTHORITY_OVERRIDE = "authority_override"
    JAILBREAK_DAN = "jailbreak_dan"
    ROLEPLAY_HYPOTHETICAL = "roleplay_hypothetical"
    SCOPE_BOUNDARY = "scope_boundary"
    INDIRECT_INJECTION = "indirect_injection"
    OBFUSCATION = "obfuscation"
    DATA_EXFILTRATION = "data_exfiltration"
    OUTPUT_INJECTION = "output_injection"
    TOOL_ABUSE = "tool_abuse"


SUPPORTED_ATTACK_STRATEGIES = tuple(strategy.value for strategy in AttackStrategy)
