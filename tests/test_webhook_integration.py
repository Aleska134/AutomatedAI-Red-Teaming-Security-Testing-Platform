import pytest

from app.services.security_evaluation import evaluate_scope_boundary
from app.services.webhook_adapter import WebhookAdapterError, send_webhook_message


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_webhook_adapter_sends_stable_contract_and_authentication():
    captured = {}

    def transport(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse({"reply": "I can only help with TechMart products and orders."})

    result = send_webhook_message(
        "https://merchant.example.test/agent",
        message="What is the capital of France?",
        auth_token="test-token",
        transport=transport,
    )

    assert result["reply"].startswith("I can only help")
    assert captured["kwargs"]["json"]["version"] == "1"
    assert captured["kwargs"]["json"]["mode"] == "security_test"
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer test-token"


def test_scope_boundary_flags_unrelated_answer():
    result = evaluate_scope_boundary("The capital of France is Paris.")

    assert result["breached"] is True
    assert result["evidence"][0]["rule"] == "scope_boundary"


def test_scope_boundary_accepts_store_redirect():
    result = evaluate_scope_boundary(
        "I can only assist with TechMart products, orders, and store policies."
    )

    assert result == {"breached": False, "evidence": []}


def test_webhook_adapter_rejects_invalid_url():
    with pytest.raises(WebhookAdapterError):
        send_webhook_message("merchant.example.test/agent", message="Hello")
