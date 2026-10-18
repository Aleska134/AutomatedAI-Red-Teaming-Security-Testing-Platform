from app.services.owasp import RULE_TO_OWASP
from app.services.run_report import RECOMMENDATIONS_ES, RULE_TITLES, render_run_report
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
