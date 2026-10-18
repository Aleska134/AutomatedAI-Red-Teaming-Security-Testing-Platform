"""Simulation numbers restart per company and runs stay tenant-isolated."""

from tests.conftest import register_active_company

MODULE = "app.services.simulation_loop"


def _fake_agents(monkeypatch):
    monkeypatch.setattr(
        f"{MODULE}.generate_attack_payload_result",
        lambda history, strategy: {"payload": "hi", "source": "test"},
    )
    monkeypatch.setattr(f"{MODULE}.query_defender", lambda *args, **kwargs: "No.")
    monkeypatch.setattr(
        f"{MODULE}.evaluate_simulation",
        lambda history, tool_events: {"breached": False},
    )


def _run(api_client, headers):
    response = api_client.post("/api/v1/simulation/loop", json={"turns": 1}, headers=headers)
    return response.json()["run_id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_numbers_are_per_company_and_runs_are_isolated(api_client, admin_token, monkeypatch):
    _fake_agents(monkeypatch)
    a_id, a_token = register_active_company(api_client, "Shop A", "a@scope.test")
    _, b_token = register_active_company(api_client, "Shop B", "b@scope.test")
    a, b, admin = _headers(a_token), _headers(b_token), _headers(admin_token)

    _run(api_client, admin)
    _run(api_client, admin)
    a_run = _run(api_client, a)
    b_run = _run(api_client, b)

    # Admin activity does not advance a client's counter.
    a_data = api_client.get("/api/v1/simulations", headers=a).json()["data"]
    assert [r["simulation_number"] for r in a_data] == [1]
    assert [r["run_id"] for r in a_data] == [a_run]

    # Clients cannot see or fetch another company's run.
    assert b_run not in {r["run_id"] for r in api_client.get("/api/v1/test-runs", headers=a).json()}
    assert api_client.get(f"/api/v1/test-runs/{b_run}", headers=a).status_code == 404
    assert api_client.get(f"/api/v1/simulations/{b_run}", headers=a).status_code == 404

    # Admin sees every run, each labelled with its company.
    admin_data = api_client.get("/api/v1/simulations", headers=admin).json()["data"]
    assert len(admin_data) == 4
    names = {r["run_id"]: r["company_name"] for r in admin_data}
    assert names[a_run] == "Shop A" and names[b_run] == "Shop B"

    # "#1" is ambiguous for admins, so the number lookup is scoped to a company.
    by_number = api_client.get(
        "/api/v1/simulations/number/1", params={"company_id": a_id}, headers=admin
    ).json()
    assert by_number["run_id"] == a_run
    own = api_client.get("/api/v1/simulations/number/1", headers=admin).json()
    assert own["company_name"] == "Admin Co"


def test_client_cannot_use_company_id_to_read_other_tenants(api_client, monkeypatch):
    _fake_agents(monkeypatch)
    _, a_token = register_active_company(api_client, "Shop A", "a2@scope.test")
    b_id, b_token = register_active_company(api_client, "Shop B", "b2@scope.test")
    _run(api_client, _headers(b_token))

    response = api_client.get(
        "/api/v1/simulations/number/1", params={"company_id": b_id}, headers=_headers(a_token)
    )
    assert response.status_code == 404
