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


def test_multiple_runs_get_unique_consecutive_numbers(api_client, monkeypatch):
    """Running several tests must produce distinct, consecutive numbers — no
    two runs may share a simulation_number (which would hide one in the UI)."""
    _fake_agents(monkeypatch)
    _, token = register_active_company(api_client, "Shop", "multi@scope.test")
    headers = _headers(token)

    # Run five tests back to back (as the "pick specific tests" mode does).
    for _ in range(5):
        _run(api_client, headers)

    data = api_client.get("/api/v1/simulations", headers=headers).json()["data"]
    numbers = [r["simulation_number"] for r in data]

    # Every run is present and every number is unique and consecutive.
    assert len(data) == 5
    assert len(set(numbers)) == 5, f"duplicate simulation numbers: {numbers}"
    assert sorted(numbers) == [1, 2, 3, 4, 5]


def test_overlapping_runs_do_not_collide_on_a_number(api_client, monkeypatch):
    """Concurrency guard: two runs that execute while BOTH are still 'running'
    (neither 'completed' yet) must still receive different numbers. This is the
    race that made two tests show up as one in the dashboard."""
    _fake_agents(monkeypatch)
    _, token = register_active_company(api_client, "Shop", "race@scope.test")
    company_id, _tok = (
        api_client.post(
            "/api/v1/auth/login",
            json={"email": "race@scope.test", "password": "company-pass-1"},
        ).json()["company"]["company_id"],
        None,
    )

    from app.services import simulation_loop
    from app.services.simulation_loop import execute_simulation_run
    from app.services.test_runs import create_test_run

    # Two runs created and left 'running' at the same time (overlap). We make
    # the first run, while in-flight, launch the second run before it completes,
    # so both reach the numbering step with neither marked 'completed'.
    create_test_run(run_id="race-A", strategy="s", turns_requested=1, company_id=company_id)
    create_test_run(run_id="race-B", strategy="s", turns_requested=1, company_id=company_id)

    original_complete = simulation_loop.complete_test_run
    launched = {"second": False}

    def complete_once_then_nest(run_id, **fields):
        # When the FIRST run is about to be numbered/completed, run the SECOND
        # one fully first, so run A computes its number while B is already
        # completed — and B computed its number while A was still running.
        if run_id == "race-A" and not launched["second"]:
            launched["second"] = True
            execute_simulation_run(
                "race-B", strategy="s", turns=1, history=[],
                company_id=company_id, customer_id="c", target=None,
            )
        return original_complete(run_id, **fields)

    monkeypatch.setattr(simulation_loop, "complete_test_run", complete_once_then_nest)
    execute_simulation_run(
        "race-A", strategy="s", turns=1, history=[],
        company_id=company_id, customer_id="c", target=None,
    )

    headers = _headers(token)
    data = api_client.get("/api/v1/simulations", headers=headers).json()["data"]
    numbers = sorted(r["simulation_number"] for r in data)
    assert len(data) == 2
    assert numbers == [1, 2], f"runs collided on a number: {numbers}"


def test_failed_run_does_not_consume_a_simulation_number(api_client, monkeypatch):
    """A run that fails (e.g. the target was asleep and timed out) must not
    leave a gap in the per-company numbering: completed runs stay 1, 2, 3..."""
    from app.services.webhook_adapter import WebhookAdapterError

    _, token = register_active_company(api_client, "Shop", "gap@scope.test")
    headers = _headers(token)

    # First run succeeds -> should be #1.
    _fake_agents(monkeypatch)
    _run(api_client, headers)

    # Second run fails mid-flight (simulate the target being unreachable).
    def boom(history, strategy):
        raise WebhookAdapterError("target asleep")

    monkeypatch.setattr(f"{MODULE}.generate_attack_payload_result", boom)
    _run(api_client, headers)

    # Third run succeeds -> must be #2, NOT #3 (the failed run took no number).
    _fake_agents(monkeypatch)
    _run(api_client, headers)

    data = api_client.get("/api/v1/simulations", headers=headers).json()["data"]
    completed = [
        r["simulation_number"]
        for r in data
        if r.get("status") == "completed"
    ]
    # Two completed runs, numbered consecutively with no gap.
    assert sorted(completed) == [1, 2]
