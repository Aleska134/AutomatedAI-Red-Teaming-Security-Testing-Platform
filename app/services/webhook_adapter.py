"""Stable, minimal webhook contract for testing external merchant agents."""

from typing import Any, Callable
from urllib.parse import urlparse

import requests


class WebhookAdapterError(RuntimeError):
    """Raised when an external agent cannot be reached or parsed safely."""


def validate_webhook_url(webhook_url: str) -> None:
    """Allow only explicit HTTP(S) endpoints for the integration boundary."""
    parsed = urlparse(webhook_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebhookAdapterError("webhook_url must be an absolute HTTP(S) URL.")


def send_webhook_message(
    webhook_url: str,
    *,
    message: str,
    history: list[dict[str, str]] | None = None,
    auth_token: str | None = None,
    transport: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Send the versioned test contract and return a normalized agent response."""
    validate_webhook_url(webhook_url)
    headers = {"Content-Type": "application/json", "X-AI-Security-Test": "v1"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    body = {
        "version": "1",
        "message": message,
        "history": history or [],
        "mode": "security_test",
    }
    try:
        response = transport(
            webhook_url,
            json=body,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WebhookAdapterError("The merchant webhook did not return a valid response.") from error

    reply = payload.get("reply") or payload.get("message")
    if not isinstance(reply, str) or not reply.strip():
        raise WebhookAdapterError("The merchant webhook response must include a non-empty reply.")
    return {"reply": reply.strip(), "raw_response": payload}
