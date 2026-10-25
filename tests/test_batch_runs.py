"""Running a batch of selected tests must be resilient.

One failing test (e.g. the target was asleep and the run timed out) must not
abort the remaining tests in the batch — every scenario runs independently and
reports its own outcome.
"""

from app.services.batch_runner import can_combine_runs, collect_scenario_results


class FakeScenario:
    def __init__(self, name):
        self.name = name


def test_all_scenarios_run_and_report_outcomes():
    scenarios = [FakeScenario("A"), FakeScenario("B"), FakeScenario("C")]

    def runner(scenario):
        # A breaches, B and C do not.
        return {"is_breached": scenario.name == "A"}

    results = collect_scenario_results(scenarios, runner)

    assert [r["name"] for r in results] == ["A", "B", "C"]
    assert [r["outcome"] for r in results] == ["BREACHED", "SECURED", "SECURED"]


def test_a_failing_scenario_does_not_abort_the_rest():
    scenarios = [FakeScenario("first"), FakeScenario("second"), FakeScenario("third")]

    def runner(scenario):
        # The FIRST scenario fails (as if the target timed out).
        if scenario.name == "first":
            raise RuntimeError("target asleep; timed out")
        return {"is_breached": False}

    results = collect_scenario_results(scenarios, runner)

    # All three are reported — the failure did not stop the batch.
    assert len(results) == 3
    assert results[0]["outcome"] == "ERROR"
    assert "timed out" in results[0]["error"]
    # The two tests after the failure still ran.
    assert results[1]["outcome"] == "SECURED"
    assert results[2]["outcome"] == "SECURED"


def test_every_scenario_can_fail_independently():
    scenarios = [FakeScenario("x"), FakeScenario("y")]

    def runner(scenario):
        raise RuntimeError(f"{scenario.name} failed")

    results = collect_scenario_results(scenarios, runner)

    assert all(r["outcome"] == "ERROR" for r in results)
    assert [r["name"] for r in results] == ["x", "y"]


def test_empty_batch_returns_empty():
    assert collect_scenario_results([], lambda s: {}) == []


# --- can_combine_runs: combined report must cover a single chatbot --------- #


def test_can_combine_same_target_runs():
    runs = [{"target_id": "t-weak"}, {"target_id": "t-weak"}]
    ok, reason = can_combine_runs(runs)
    assert ok is True
    assert reason == ""


def test_cannot_combine_fewer_than_two():
    ok, reason = can_combine_runs([{"target_id": "t-weak"}])
    assert ok is False
    assert "at least two" in reason


def test_cannot_combine_different_targets():
    runs = [{"target_id": "t-weak"}, {"target_id": "t-hardened"}]
    ok, reason = can_combine_runs(runs)
    assert ok is False
    assert "different chatbots" in reason


def test_builtin_simulator_runs_combine_together():
    # Two runs against the built-in simulator (no target_id) share target None.
    runs = [{"target_id": None}, {"target_id": None}]
    ok, _ = can_combine_runs(runs)
    assert ok is True
