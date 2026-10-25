from app.services.security_scenarios import (
    SECURITY_SCENARIOS,
    STRATEGY_EXPLANATIONS,
    friendly_test_name,
    get_categories,
    get_scenarios,
    scenarios_for_target,
    select_scenarios,
    strategy_explanation,
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


# --- Assessment mode selection (full / focused / pick) --------------------- #


def test_scenarios_for_target_filters_webhook_only_for_simulator():
    # With a saved target, every scenario is runnable.
    with_target = scenarios_for_target(get_scenarios(), has_target=True)
    assert len(with_target) == len(SECURITY_SCENARIOS)

    # Without a target (built-in simulator), webhook-only scenarios drop out.
    simulator_only = scenarios_for_target(get_scenarios(), has_target=False)
    assert all(
        getattr(s, "execution_mode", "simulator") == "simulator" for s in simulator_only
    )
    assert len(simulator_only) < len(SECURITY_SCENARIOS)


def test_full_mode_returns_all_runnable_scenarios():
    result = select_scenarios("full", has_target=True)
    assert len(result) == len(SECURITY_SCENARIOS)


def test_focused_mode_returns_only_the_category():
    result = select_scenarios("focused", has_target=True, category="Commerce Abuse")
    assert result
    assert all(s.category == "Commerce Abuse" for s in result)


def test_pick_mode_returns_exactly_the_chosen_tests():
    all_scenarios = get_scenarios()
    chosen = [all_scenarios[0].name, all_scenarios[2].name]
    result = select_scenarios("pick", has_target=True, chosen_names=chosen)
    assert sorted(s.name for s in result) == sorted(chosen)


def test_pick_mode_with_no_selection_returns_nothing():
    result = select_scenarios("pick", has_target=True, chosen_names=[])
    assert result == []


def test_pick_mode_ignores_unknown_names():
    result = select_scenarios(
        "pick", has_target=True, chosen_names=["Not a real scenario"]
    )
    assert result == []


# --- Friendly names & plain-language explanations -------------------------- #


def test_friendly_test_name_maps_strategy_to_scenario_name():
    assert friendly_test_name("data_exfiltration") == "Customer Data Access"
    assert friendly_test_name("indirect_injection") == "Indirect Prompt Injection"


def test_friendly_test_name_falls_back_for_unknown_strategy():
    # Unknown slug -> readable title-case, never a crash.
    assert friendly_test_name("some_new_strategy") == "Some New Strategy"


def test_every_scenario_strategy_has_a_plain_language_explanation():
    # Every strategy actually used by a scenario must have an explanation, so no
    # report or log ever shows a blank "what this checks".
    for scenario in SECURITY_SCENARIOS:
        assert scenario.strategy in STRATEGY_EXPLANATIONS, scenario.strategy
        assert strategy_explanation(scenario.strategy, "en")
        assert strategy_explanation(scenario.strategy, "es")


def test_strategy_explanation_is_bilingual_and_differs():
    en = strategy_explanation("data_exfiltration", "en")
    es = strategy_explanation("data_exfiltration", "es")
    assert en and es and en != es


def test_strategy_explanation_unknown_returns_empty():
    assert strategy_explanation("nope") == ""
