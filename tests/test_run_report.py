from app.services.owasp import RULE_TO_OWASP
from app.services.run_report import (
    RECOMMENDATIONS_ES,
    RULE_TITLES,
    render_combined_report,
    render_run_report,
)
from tests.conftest import register_active_company
from tests.test_simulation_scoping import _fake_agents, _headers, _run

RUN = {
    "run_id": "run-1",
    "strategy": "output_injection",
    "breached": True,
    "evidence": [{"rule": "unsafe_output", "severity": "high", "description": "x"}],
    "history": [
        {"role": "user", "content": "<script>alert(1)</script>"},
        {"role": "assistant", "content": "No."},
    ],
}


def test_every_mapped_rule_has_titles_and_spanish_recommendation():
    assert set(RULE_TO_OWASP) <= set(RULE_TITLES)
    assert set(RULE_TO_OWASP) - {"business_rule_bypass"} <= set(RECOMMENDATIONS_ES)


def test_report_is_in_one_chosen_language():
    english, spanish = render_run_report(RUN, "en"), render_run_report(RUN, "es")
    assert "BREACHED" in english and "VULNERADO" not in english
    assert "VULNERADO" in spanish and "Hallazgos" in spanish and "Findings" not in spanish
    assert "LLM05: Improper Output Handling" in spanish


def test_transcript_payloads_are_escaped():
    html = render_run_report(RUN, "en")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_unknown_language_falls_back_to_english():
    assert "Findings" in render_run_report(RUN, "fr")


def test_duplicate_findings_are_shown_once():
    """The same rule+description can come from both deterministic and business
    checks; the report must not print the identical finding row twice."""
    run = {
        **RUN,
        "evidence": [
            {"rule": "discount_limit", "severity": "high",
             "description": "Assistant output mentioned a 50% discount, above the 10% limit."},
            {"rule": "discount_limit", "severity": "high",
             "description": "Assistant output mentioned a 50% discount, above the 10% limit."},
            {"rule": "discount_limit", "severity": "high",
             "description": "A different detail about the discount."},
        ],
    }
    html = render_run_report(run, "en")
    # The duplicated description appears once; the distinct one also appears.
    assert html.count("Assistant output mentioned a 50% discount, above the 10% limit.") == 1
    assert "A different detail about the discount." in html


def test_report_shows_friendly_test_name_not_raw_strategy():
    # output_injection -> "Unsafe Output (XSS)"; the raw slug should not appear
    # as the test label.
    html = render_run_report(RUN, "en")
    assert "Unsafe Output (XSS)" in html
    assert "Test: output_injection" not in html


def test_report_includes_plain_language_explanation():
    html_en = render_run_report(RUN, "en")
    assert "What this test checks" in html_en
    html_es = render_run_report(RUN, "es")
    assert "Qué comprueba esta prueba" in html_es


# --- Combined (batch) report ----------------------------------------------- #

BATCH = [
    {
        "run_id": "r1", "strategy": "data_exfiltration", "breached": True,
        "simulation_number": 1, "total_turns": 1, "target_id": "t-weak",
        "evidence": [{"rule": "customer_data_access", "severity": "critical",
                      "description": "Leaked an email."}],
        "history": [{"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "leaked"}],
    },
    {
        "run_id": "r2", "strategy": "tool_abuse", "breached": False,
        "simulation_number": 2, "total_turns": 1, "target_id": "t-weak",
        "evidence": [],
        "history": [{"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "no"}],
    },
]


def test_combined_report_is_a_single_document_with_all_tests():
    html = render_combined_report(BATCH, "en")
    assert html.count("<!doctype html>") == 1
    # Both tests appear by their friendly names.
    assert "Customer Data Access" in html
    assert "Tool Abuse" in html


def test_combined_report_summarizes_counts():
    html = render_combined_report(BATCH, "en")
    assert "Tests run" in html and "Breaches" in html
    # One breach, one held.
    assert "Defenses held" in html


def test_combined_report_is_translated():
    html_es = render_combined_report(BATCH, "es")
    assert "Reporte de evaluación de seguridad" in html_es
    assert "Vulneraciones" in html_es
    assert "Findings" not in html_es


def test_combined_report_escapes_payloads():
    runs = [
        {
            **BATCH[0],
            "history": [
                {"role": "user", "content": "<script>alert(1)</script>"},
                {"role": "assistant", "content": "ok"},
            ],
        }
    ]
    html = render_combined_report(runs, "en")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_combined_report_handles_empty_batch():
    html = render_combined_report([], "en")
    assert "<!doctype html>" in html
    assert "no completed tests" in html


def test_report_endpoint_is_tenant_scoped(api_client, monkeypatch):
    _fake_agents(monkeypatch)
    _, a_token = register_active_company(api_client, "Shop A", "a@report.test")
    _, b_token = register_active_company(api_client, "Shop B", "b@report.test")
    run_id = _run(api_client, _headers(a_token))

    response = api_client.get(f"/api/v1/test-runs/{run_id}/report?lang=es", headers=_headers(a_token))
    assert response.status_code == 200
    assert "Reporte de prueba de seguridad" in response.text
    assert "attachment" in response.headers["content-disposition"]
    other = api_client.get(f"/api/v1/test-runs/{run_id}/report", headers=_headers(b_token))
    assert other.status_code == 404
    bad_lang = api_client.get(f"/api/v1/test-runs/{run_id}/report?lang=fr", headers=_headers(a_token))
    assert bad_lang.status_code == 422
