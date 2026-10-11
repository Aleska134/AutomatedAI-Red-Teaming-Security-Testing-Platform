from app.services.security_scenarios import (
    SECURITY_SCENARIOS,
    get_categories,
    get_scenarios,
)


def test_full_assessment_contains_all_scenarios():
    assert len(get_scenarios()) == len(SECURITY_SCENARIOS)
    assert len(get_scenarios()) >= 6


def test_focused_category_returns_only_matching_scenarios():
    scenarios = get_scenarios("Commerce Abuse")

    assert scenarios
    assert all(scenario.category == "Commerce Abuse" for scenario in scenarios)
    assert "Commerce Abuse" in get_categories()


def test_scope_boundary_uses_connected_webhook_mode():
    scenario = next(item for item in SECURITY_SCENARIOS if item.scenario_id == "scope-boundary")

    assert scenario.category == "Agent Safety"
    assert scenario.execution_mode == "webhook"


def test_legacy_scenarios_default_to_simulator_mode():
    scenario = SECURITY_SCENARIOS[0]

    assert getattr(scenario, "execution_mode", "simulator") == "simulator"
