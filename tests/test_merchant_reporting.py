from app.services.merchant_reporting import (
    build_findings,
    build_merchant_report,
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
