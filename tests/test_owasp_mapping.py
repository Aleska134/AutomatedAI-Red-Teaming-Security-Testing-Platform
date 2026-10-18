from app.services.merchant_reporting import build_findings
from app.services.owasp import OWASP_LLM_TOP10, RULE_TO_OWASP, owasp_for, owasp_label
from app.services.security_evaluation import (
    evaluate_business_rules,
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
