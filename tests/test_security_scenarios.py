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
