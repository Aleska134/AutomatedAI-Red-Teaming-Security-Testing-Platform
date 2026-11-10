"""Adversarial inputs: incomplete, null or oddly typed records must never crash
the dashboard data layer or the reports, and must not corrupt statistics."""

import pytest

from app.services.merchant_reporting import (
    build_findings,
    build_merchant_report,
    group_findings,
)
from app.services.run_report import render_combined_report, render_run_report
from app.services.target_analytics import (
    compare_targets,
    summarize_all_targets,
    summarize_target,
)
from tests.conftest import register_active_company


def _run(**overrides):
    record = {
        "run_id": "r1", "session_id": "r1", "status": "completed",
        "simulation_number": 1, "strategy": "scope", "breached": False,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    return {**record, **overrides}


# --- merchant report ------------------------------------------------------ #

@pytest.mark.parametrize("score", [None, "", "n/a", "7.5", 7, True])
def test_report_survives_odd_defense_scores(score):
    report = build_merchant_report([_run(defense_efficiency_score=score)])
    assert report["total_runs"] == 1
    assert 0 <= report["average_defense_efficiency"] <= 10


@pytest.mark.parametrize("number", [None, "3", "3.0", 3.0, "abc", -1])
def test_report_survives_odd_simulation_numbers(number):
    report = build_merchant_report([_run(simulation_number=number)])
    assert report["latest_simulation"] is not None


@pytest.mark.parametrize("field", ["tool_events", "evidence"])
def test_null_list_fields_do_not_crash(field):
    run = _run(breached=True, **{field: None})
    assert build_merchant_report([run])["breached_runs"] == 1
    assert isinstance(build_findings([run]), list)


def test_finding_with_null_severity_or_description_still_sorts_and_groups():
    findings = build_findings([
        _run(evidence=[
            {"rule": "scope_boundary", "severity": None, "description": None},
            {"rule": "canary_leak", "severity": "HIGH"},
            {"severity": "low"},
        ])
    ])
    grouped = group_findings(findings)
    assert len(grouped) == 3
    assert all(isinstance(row["severity"], str) for row in grouped)
    assert grouped[0]["severity"].lower() == "high"  # unknown severity sorts last


def test_non_dict_evidence_entries_are_ignored():
    findings = build_findings([_run(evidence=["oops", None, {"rule": "canary_leak"}])])
    assert [f["rule"] for f in findings] == ["canary_leak"]


def test_group_findings_with_mixed_simulation_numbers():
    findings = build_findings([
        _run(simulation_number=2, evidence=[{"rule": "canary_leak"}]),
        _run(simulation_number=None, evidence=[{"rule": "canary_leak"}]),
        _run(simulation_number="unknown", evidence=[{"rule": "canary_leak"}]),
    ])
    assert group_findings(findings)[0]["count"] == 3


def test_empty_inputs_everywhere():
    assert build_merchant_report([])["risk_status"] == "no_data"
    assert build_findings([]) == []
    assert group_findings([]) == []
    assert summarize_all_targets([], {}) == []


# --- target analytics ----------------------------------------------------- #

def test_analytics_survive_null_and_odd_fields():
    runs = [
        _run(target_id="t", defense_efficiency_score=None, evidence=None, breached=True),
        _run(target_id="t", defense_efficiency_score="bad", created_at=None),
        _run(target_id="t", strategy=None),
    ]
    summary = summarize_target(runs, "t", {})
    assert summary["tests"] == 3
    assert summary["verdict"] == "fell"
    compare_targets(runs, "t", "t", {})  # same chatbot on both sides


def test_breached_flag_wins_over_conclusive_false():
    run = _run(target_id="t", breached=True, conclusive=False)
    assert summarize_target([run], "t", {})["breached"] == 1


def test_target_name_is_not_trusted_as_markup_in_stats():
    summary = summarize_target([_run(target_id="x")], "x", {"x": "<script>alert(1)</script>"})
    assert summary["name"] == "<script>alert(1)</script>"  # data layer keeps it raw


# --- reports -------------------------------------------------------------- #

NASTY = '<script>alert("x")</script><img src=x onerror=alert(1)>'


@pytest.mark.parametrize("lang", ["en", "es", "fr", "", None])
def test_run_report_escapes_everything_and_handles_unknown_language(lang):
    run = _run(
        breached=True, analysis=NASTY, strategy=NASTY, target_id=NASTY,
        history=[{"role": "user", "content": NASTY}, {"role": "assistant", "content": NASTY}],
        evidence=[{"rule": NASTY, "severity": NASTY, "description": NASTY}],
        inconclusive_reason=NASTY,
    )
    html = render_run_report(run, lang)
    assert "<script>alert" not in html
    assert "<img src=x" not in html


def test_run_report_with_missing_and_null_parts():
    run = _run(history=None, evidence=None, analysis=None, tool_events=None,
               defense_efficiency_score=None)
    assert "<html" in render_run_report(run, "en").lower()
    history_oddities = [{"role": "user"}, {"content": "no role"}, {}, {"role": "x", "content": None}]
    assert "<html" in render_run_report(_run(history=history_oddities), "es").lower()


def test_combined_report_with_empty_and_mixed_runs():
    assert "<html" in render_combined_report([], "en").lower()
    runs = [_run(), _run(run_id="r2", conclusive=False), _run(run_id="r3", status="failed")]
    html = render_combined_report(runs, "es")
    assert "<html" in html.lower()


def test_combined_report_escapes_across_runs():
    runs = [_run(analysis=NASTY, evidence=[{"rule": "x", "description": NASTY}]) for _ in range(2)]
    assert "<script>alert" not in render_combined_report(runs, "en")


# --- API: tenant isolation and bad input ---------------------------------- #

def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_company_cannot_run_against_another_companys_target(api_client, monkeypatch):
    _, a_token = register_active_company(api_client, "Shop A", "a@edge.test")
    _, b_token = register_active_company(api_client, "Shop B", "b@edge.test")
    monkeypatch.setattr("app.services.targets.assert_public_url", lambda *a, **k: None,
                        raising=False)
    created = api_client.post(
        "/api/v1/targets",
        json={"authorization_confirmed": True, "name": "A bot", "webhook_url": "https://example.com/chat"},
        headers=_headers(a_token),
    )
    if created.status_code not in (200, 201):
        pytest.skip(f"cannot create target in this environment: {created.text}")
    target_id = created.json().get("target_id") or created.json()["data"]["target_id"]

    stolen = api_client.post(
        "/api/v1/simulation/loop",
        json={"turns": 1, "target_id": target_id}, headers=_headers(b_token),
    )
    assert stolen.status_code in (400, 403, 404, 422)
    assert api_client.delete(f"/api/v1/targets/{target_id}", headers=_headers(b_token)
                             ).status_code in (403, 404)


@pytest.mark.parametrize(
    "payload",
    [
        {"turns": 0}, {"turns": -5}, {"turns": 10**9}, {"turns": "many"},
        {"turns": None}, {"turns": 1.5}, {"turns": 1, "strategy": "x" * 100_000},
        {"turns": 1, "strategy": 123}, {"turns": 1, "history": "not a list"},
        {"turns": 1, "history": [{"role": "user"}] * 10_000},
        {"turns": 1, "target_id": {"$ne": None}}, {"turns": 1, "target_id": "../../etc"},
        [], "text", None,
    ],
)
def test_simulation_loop_rejects_bad_input_without_server_error(api_client, admin_token, payload):
    response = api_client.post("/api/v1/simulation/loop", json=payload,
                               headers=_headers(admin_token))
    assert response.status_code < 500, response.text


def test_endpoints_require_authentication(api_client):
    for method, path in [("get", "/api/v1/simulations"), ("get", "/api/v1/targets"),
                         ("post", "/api/v1/simulation/loop"),
                         ("get", "/api/v1/test-runs/anything")]:
        response = getattr(api_client, method)(path)
        assert response.status_code in (401, 403), (path, response.status_code)


def test_garbage_and_expired_tokens_are_rejected(api_client):
    for token in ["", "abc", "Bearer", "a.b.c", "null", "x" * 10_000]:
        response = api_client.get("/api/v1/simulations", headers=_headers(token))
        assert response.status_code in (401, 403), token[:20]


def test_unknown_run_id_is_404_not_500(api_client, admin_token):
    for run_id in ["nope", "../etc/passwd", "%00", "a" * 5000]:
        response = api_client.get(f"/api/v1/test-runs/{run_id}", headers=_headers(admin_token))
        assert response.status_code in (404, 422), (run_id[:20], response.status_code)
