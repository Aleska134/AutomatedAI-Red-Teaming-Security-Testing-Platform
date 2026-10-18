"""Stable, minimal webhook contract for testing external merchant agents."""

import ipaddress
import os
import socket
from typing import Any, Callable
from urllib.parse import urlparse

import requests


class WebhookAdapterError(RuntimeError):
    """Raised when an external agent cannot be reached or parsed safely."""


def _private_webhooks_allowed() -> bool:
    """Local development may target a chatbot on localhost; nothing else may."""
    return os.getenv("ALLOW_PRIVATE_WEBHOOKS", "").strip().lower() == "true"


def _resolve_host(host: str) -> list[str]:
    try:
        return [info[4][0] for info in socket.getaddrinfo(host, None)]
    except (socket.gaierror, UnicodeError) as error:
        raise WebhookAdapterError("webhook_url host could not be resolved.") from error


def validate_webhook_url(webhook_url: str) -> None:
    """Allow only explicit HTTP(S) endpoints on public addresses.

    Blocks SSRF: every resolved address must be globally routable, so a
    tenant cannot make the platform call loopback, private networks, or the
    cloud metadata service (169.254.169.254).
    """
    parsed = urlparse(webhook_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebhookAdapterError("webhook_url must be an absolute HTTP(S) URL.")
    if _private_webhooks_allowed():
        return
    for address in _resolve_host(parsed.hostname):
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise WebhookAdapterError(
                "webhook_url must resolve to a public address."
            )


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
            # A redirect could bounce the request to an internal address.
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WebhookAdapterError("The merchant webhook did not return a valid response.") from error

    reply = payload.get("reply") or payload.get("message")
    if not isinstance(reply, str) or not reply.strip():
        raise WebhookAdapterError("The merchant webhook response must include a non-empty reply.")

    # Optional structured metadata. Targets that implement the enriched contract
    # expose a security outcome; older targets simply omit it.
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return {"reply": reply.strip(), "metadata": metadata, "raw_response": payload}
