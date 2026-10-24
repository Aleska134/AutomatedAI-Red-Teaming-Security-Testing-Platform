"""Run a batch of security scenarios resiliently.

Kept free of any Streamlit/UI imports so it is easy to unit test. The dashboard
passes a ``runner`` callable that actually executes one scenario (queue + poll);
this module just guarantees that one failing scenario never aborts the rest.
"""

from typing import Any, Callable


def collect_scenario_results(
    scenarios: list[Any],
    runner: Callable[[Any], dict],
) -> list[dict[str, Any]]:
    """Run every scenario independently and collect a per-test result.

    ``runner(scenario)`` runs one scenario and returns its result dict (or
    raises). A failing scenario is recorded as an ERROR and does NOT stop the
    remaining scenarios — so one asleep or timed-out target can no longer abort
    a whole batch. Returns a list of ``{name, outcome, error}`` dicts, one per
    scenario, in order.
    """
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        try:
            result = runner(scenario)
            outcome = "BREACHED" if result.get("is_breached") else "SECURED"
            results.append({"name": scenario.name, "outcome": outcome, "error": None})
        except Exception as error:  # noqa: BLE001 - record per test, keep going
            results.append(
                {"name": scenario.name, "outcome": "ERROR", "error": str(error)}
            )
    return results
