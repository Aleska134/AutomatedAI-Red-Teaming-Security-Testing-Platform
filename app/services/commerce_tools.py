"""Tool definitions and dispatch for the commerce support agent."""

import json
from typing import Any, Callable

from app.services.commerce import (
    CommerceError,
    add_to_cart,
    checkout_cart,
    get_or_create_cart,
    search_products,
)

COMMERCE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the TechMart product catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "A product name or category to search for.",
                    }
                },
                "required": ["search_term"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "Retrieve the customer's current shopping cart.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add an in-stock product to the customer's cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["product_id", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "checkout",
            "description": (
                "Complete the customer's open cart and create a paid demo order. "
                "Only call this after the customer clearly confirms the purchase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coupon_code": {"type": ["string", "null"]},
                },
                "required": ["coupon_code"],
                "additionalProperties": False,
            },
        },
    },
]


def _error_result(error: Exception) -> dict[str, str]:
    return {"error": str(error)}


def execute_commerce_tool(
    name: str,
    arguments: dict[str, Any],
    customer_id: str,
    checkout_allowed: bool = False,
) -> dict[str, Any]:
    """Execute one allowlisted tool with the authenticated customer context."""
    if name == "checkout" and not checkout_allowed:
        return {
            "error": (
                "Checkout requires an explicit purchase confirmation in the "
                "customer's latest message."
            )
        }

    handlers: dict[str, Callable[..., Any]] = {
        "search_products": lambda: search_products(arguments.get("search_term", "")),
        "get_cart": lambda: get_or_create_cart(customer_id),
        "add_to_cart": lambda: add_to_cart(
            customer_id,
            arguments["product_id"],
            arguments["quantity"],
        ),
        "checkout": lambda: checkout_cart(
            customer_id,
            arguments.get("coupon_code"),
        ),
    }
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"Unsupported commerce tool '{name}'."}

    try:
        return {"result": handler()}
    except (CommerceError, KeyError, TypeError, ValueError) as error:
        return _error_result(error)


def serialize_tool_result(result: dict[str, Any]) -> str:
    """Serialize tool output into a bounded JSON message for the model."""
    return json.dumps(result, ensure_ascii=True, default=str)[:8_000]
