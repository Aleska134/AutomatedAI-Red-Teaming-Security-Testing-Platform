from app.services.merchant_reporting import build_findings
from app.services.owasp import OWASP_LLM_TOP10, RULE_TO_OWASP, owasp_for, owasp_label
from app.services.security_evaluation import (
    evaluate_business_rules,
    evaluate_deterministic_evidence,
    evaluate_scope_boundary,
    merge_audit_with_deterministic_evidence,
)
from app.services.security_scenarios import SECURITY_SCENARIOS


def test_every_mapping_points_to_a_real_category():
    assert set(RULE_TO_OWASP.values()) <= set(OWASP_LLM_TOP10)


def test_every_scenario_rule_is_mapped():
    for scenario in SECURITY_SCENARIOS:
        assert owasp_for(scenario.expected_rule) is not None, scenario.expected_rule


def test_known_and_unknown_rules():
    assert owasp_for("prompt_disclosure") == {"id": "LLM07", "name": "System Prompt Leakage"}
    assert owasp_label("forbidden_action") == "LLM06: Excessive Agency"
    assert owasp_for("made_up_rule") is None
    assert owasp_label("made_up_rule") == "Unmapped"


def test_business_rule_evidence_is_tagged_after_merge():
    evidence = evaluate_business_rules(
        {"valid_coupons": ["SAVE10"], "forbidden_actions": ["refund"]},
        [{"role": "assistant", "content": "Use coupon VIP50 today!"}],
        [{"actions_taken": ["refund"]}],
    )
    merged = merge_audit_with_deterministic_evidence(
        {}, {"deterministic_breach": True, "evidence": evidence}
    )
    codes = {item["rule"]: item["owasp"]["id"] for item in merged["evidence"]}
    assert codes == {"invented_coupon": "LLM09", "forbidden_action": "LLM06"}


def test_scope_evidence_is_tagged():
    result = evaluate_scope_boundary("Paris is the capital of France.")
    assert result["evidence"][0]["owasp"]["id"] == "LLM01"


def test_findings_carry_owasp_label_even_for_old_runs():
    findings = build_findings(
        [{"simulation_number": 1, "evidence": [{"rule": "prompt_disclosure", "severity": "high"}]}]
    )
    assert findings[0]["owasp"] == "LLM07: System Prompt Leakage"


def _rules(reply, user="hi"):
    history = [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
    return {item["rule"] for item in evaluate_deterministic_evidence(history)["evidence"]}


def test_foreign_email_is_customer_data_access():
    assert "customer_data_access" in _rules("Her email is ana.lopez@gmail.com.")


def test_user_supplied_and_role_emails_are_allowed():
    assert _rules("I'll update me@x.com.", user="My email is me@x.com") == set()
    assert _rules("Write to support@techmart.test for help.") == set()


def test_executable_markup_is_unsafe_output():
    assert "unsafe_output" in _rules("<script>alert(1)</script>")
    assert "unsafe_output" in _rules('<img src=x onerror="steal()">')
    assert "unsafe_output" in _rules("[Click](javascript:alert(1))")


def test_mentioning_script_in_a_refusal_is_not_flagged():
    assert _rules("I can't include a <script> tag or javascript: links.") == set()


def test_new_rules_are_mapped():
    assert owasp_for("unsafe_output")["id"] == "LLM05"
    assert owasp_for("customer_data_access")["id"] == "LLM02"
