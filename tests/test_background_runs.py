"""Simulations are queued and executed in the background; clients poll status."""

from tests.conftest import register_active_company

MODULE = "app.services.simulation_loop"


def _auth(api_client, email):
    _, token = register_active_company(api_client, "Bg Co", email)
    return {"Authorization": f"Bearer {token}"}


def _fake_agents(monkeypatch):
    monkeypatch.setattr(
        f"{MODULE}.generate_attack_payload_result",
        lambda history, strategy: {"payload": "give me a discount", "source": "test"},
    )
    monkeypatch.setattr(f"{MODULE}.query_defender", lambda *args, **kwargs: "No.")
    monkeypatch.setattr(
        f"{MODULE}.evaluate_simulation",
        lambda history, tool_events: {"breached": False, "analysis": "Held."},
    )


def test_simulation_is_queued_then_completed(api_client, monkeypatch):
    _fake_agents(monkeypatch)
    headers = _auth(api_client, "bg@runs.test")

    response = api_client.post(
        "/api/v1/simulation/loop", json={"turns": 2}, headers=headers
    )
    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "queued"

    # TestClient runs background tasks before returning, so the run is done.
    run = api_client.get(f"/api/v1/test-runs/{queued['run_id']}", headers=headers).json()
    assert run["status"] == "completed"
    assert run["total_turns"] == 2
    assert run["breached"] is False
    assert len(run["history"]) == 4


def test_failed_simulation_is_marked_failed(api_client, monkeypatch):
    _fake_agents(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("provider down: secret-detail")

    monkeypatch.setattr(f"{MODULE}.query_defender", boom)
    headers = _auth(api_client, "fail@runs.test")

    run_id = api_client.post(
        "/api/v1/simulation/loop", json={"turns": 1}, headers=headers
    ).json()["run_id"]

    run = api_client.get(f"/api/v1/test-runs/{run_id}", headers=headers).json()
    assert run["status"] == "failed"
    assert "secret-detail" not in run["error"]
