"""The multi-turn attacker can target a saved external chatbot by webhook."""

from app.services.webhook_adapter import WebhookAdapterError
from tests.test_background_runs import MODULE, _auth, _fake_agents


def _create_target(api_client, headers, monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_WEBHOOKS", "true")
    response = api_client.post(
        "/api/v1/targets",
        json={"name": "Shop bot", "webhook_url": "http://localhost:8001/api/v1/chat",
              "auth_token": "bot-secret"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["target_id"]


def test_simulation_attacks_external_target(api_client, monkeypatch):
    _fake_agents(monkeypatch)
    calls = []

    def fake_webhook(url, *, message, history, auth_token):
        calls.append({"url": url, "history": history, "auth_token": auth_token})
        return {"reply": "Sorry, I can't.",
                "metadata": {"security_outcome": "blocked", "block_reason": "discount"}}

    monkeypatch.setattr(f"{MODULE}.send_webhook_message", fake_webhook)
    monkeypatch.setattr(
        f"{MODULE}.query_defender",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Defender used")),
    )
    headers = _auth(api_client, "hook@runs.test")
    target_id = _create_target(api_client, headers, monkeypatch)

    run_id = api_client.post(
        "/api/v1/simulation/loop", json={"turns": 2, "target_id": target_id},
        headers=headers,
    ).json()["run_id"]

    run = api_client.get(f"/api/v1/test-runs/{run_id}", headers=headers).json()
    assert run["status"] == "completed"
    assert run["target_id"] == target_id
    assert len(calls) == 2
    assert calls[0]["auth_token"] == "bot-secret"
    assert len(calls[1]["history"]) == 2  # previous turn is sent as context
    assert run["defense_outcomes"][0]["security_outcome"] == "blocked"


def test_unreachable_target_fails_run(api_client, monkeypatch):
    _fake_agents(monkeypatch)

    def down(*args, **kwargs):
        raise WebhookAdapterError("The merchant webhook did not return a valid response.")

    monkeypatch.setattr(f"{MODULE}.send_webhook_message", down)
    headers = _auth(api_client, "down@runs.test")
    target_id = _create_target(api_client, headers, monkeypatch)

    run_id = api_client.post(
        "/api/v1/simulation/loop", json={"turns": 1, "target_id": target_id},
        headers=headers,
    ).json()["run_id"]

    run = api_client.get(f"/api/v1/test-runs/{run_id}", headers=headers).json()
    assert run["status"] == "failed"
    assert "target chatbot failed" in run["error"]


def test_other_company_target_is_not_found(api_client, monkeypatch):
    owner = _auth(api_client, "owner@runs.test")
    target_id = _create_target(api_client, owner, monkeypatch)
    intruder = _auth(api_client, "intruder@runs.test")

    response = api_client.post(
        "/api/v1/simulation/loop", json={"turns": 1, "target_id": target_id},
        headers=intruder,
    )
    assert response.status_code == 404
