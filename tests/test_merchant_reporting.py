from app.services.merchant_reporting import (
    build_findings,
    build_merchant_report,
    group_findings,
)


def test_merchant_report_aggregates_security_status():
    report = build_merchant_report(
        [
            {
                "simulation_number": 1,
                "breached": False,
                "deterministic_breach": False,
                "defense_efficiency_score": 10,
                "tool_events": [{"tool_name": "search_products"}],
            },
            {
                "simulation_number": 2,
                "breached": True,
                "deterministic_breach": True,
                "defense_efficiency_score": 2,
                "tool_events": [],
            },
        ]
    )

    assert report["risk_status"] == "at_risk"
    assert report["total_runs"] == 2
    assert report["breached_runs"] == 1
    assert report["tool_event_count"] == 1
    assert report["average_defense_efficiency"] == 6.0


def test_findings_include_recommendations():
    findings = build_findings(
        [
            {
                "simulation_number": 4,
                "session_id": "loop-test",
                "evidence": [
                    {
                        "rule": "unauthorized_checkout",
                        "severity": "critical",
                        "description": "Checkout succeeded without confirmation.",
                    }
                ],
            }
        ]
    )

    assert findings[0]["severity"] == "critical"
    assert "confirmation" in findings[0]["recommendation"].lower()


def test_inconclusive_and_unfinished_runs_are_not_defenses_held():
    report = build_merchant_report(
        [
            {"simulation_number": 1, "status": "completed", "breached": False,
             "defense_efficiency_score": 10},
            {"simulation_number": 2, "status": "completed", "breached": False,
             "conclusive": False, "defense_efficiency_score": 10},
            {"simulation_number": 3, "status": "failed"},
            {"simulation_number": 4, "status": "queued"},
        ]
    )

    assert report["total_runs"] == 1
    assert report["defenses_held"] == 1
    assert report["inconclusive_runs"] == 1
    assert report["risk_status"] == "secure"


def test_only_inconclusive_runs_gives_no_data():
    report = build_merchant_report(
        [{"simulation_number": 1, "status": "completed", "breached": False,
          "conclusive": False}]
    )

    assert report["risk_status"] == "no_data"
    assert report["defenses_held"] == 0


def test_group_findings_collapses_repeats_across_runs():
    evidence = {"rule": "canary_leak", "severity": "high", "description": "Leaked."}
    findings = build_findings(
        [
            {"simulation_number": 2, "session_id": "a", "evidence": [evidence]},
            {"simulation_number": 1, "session_id": "b", "evidence": [evidence]},
            {"simulation_number": 3, "session_id": "c", "evidence": [
                {**evidence, "rule": "scope_boundary", "description": "Off topic."}]},
        ]
    )

    grouped = group_findings(findings)

    assert len(grouped) == 2
    leak = next(row for row in grouped if row["rule"] == "canary_leak")
    assert leak["count"] == 2
    assert leak["simulations"] == [1, 2]
