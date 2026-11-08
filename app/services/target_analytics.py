"""Per-chatbot (target) analytics, kept free of Streamlit so it is easy to test.

Statistics are computed only from conclusive runs: an unjudged run (provider
outage, failure) says nothing about how well a chatbot resists attacks.
"""

from typing import Any

from app.services.merchant_reporting import conclusive_runs, finished_runs

BUILTIN_LABEL = "Built-in Defender (simulator)"


def runs_for_target(
    runs: list[dict[str, Any]], target_id: str | None
) -> list[dict[str, Any]]:
    """Runs that attacked one chatbot; ``None`` is the built-in Defender."""
    return [run for run in runs if run.get("target_id") == target_id]


def target_label(target_id: str | None, names_by_id: dict[str, str]) -> str:
    """Display name for a target id, falling back to the raw id if deleted."""
    if not target_id:
        return BUILTIN_LABEL
    return names_by_id.get(target_id, target_id)


def summarize_target(
    runs: list[dict[str, Any]], target_id: str | None, names_by_id: dict[str, str]
) -> dict[str, Any]:
    """Resistance summary for one chatbot from all visible runs."""
    mine = runs_for_target(runs, target_id)
    judged = conclusive_runs(mine)
    breached = sum(bool(run.get("breached")) for run in judged)
    scores = [
        float(run["defense_efficiency_score"])
        for run in judged
        if run.get("defense_efficiency_score") is not None
    ]
    violated_rules = {
        evidence.get("rule")
        for run in judged
        if run.get("breached")
        for evidence in run.get("evidence", [])
    }
    if not judged:
        verdict = "no_data"
    elif breached:
        verdict = "fell"
    else:
        verdict = "resisted"
    return {
        "target_id": target_id,
        "name": target_label(target_id, names_by_id),
        "tests": len(judged),
        "breached": breached,
        "held": len(judged) - breached,
        "inconclusive": len(finished_runs(mine)) - len(judged),
        "breach_rate": round(breached / len(judged), 4) if judged else None,
        "avg_defense": round(sum(scores) / len(scores), 2) if scores else None,
        "violated_rules": len(violated_rules),
        "last_run_at": max((run.get("created_at") or "" for run in mine), default=""),
        "verdict": verdict,
    }


def summarize_all_targets(
    runs: list[dict[str, Any]], names_by_id: dict[str, str]
) -> list[dict[str, Any]]:
    """One summary per chatbot that has runs, most vulnerable first."""
    target_ids = {run.get("target_id") for run in runs}
    summaries = [summarize_target(runs, tid, names_by_id) for tid in target_ids]
    # None rates (no data) sort last; higher breach rate first.
    return sorted(
        summaries,
        key=lambda s: (s["breach_rate"] is None, -(s["breach_rate"] or 0), s["name"]),
    )


def _outcome(run: dict[str, Any]) -> str:
    if run.get("breached"):
        return "breached"
    if run.get("conclusive") is False:
        return "inconclusive"
    return "held"


def latest_outcome_by_strategy(
    runs: list[dict[str, Any]], target_id: str | None
) -> dict[str, str]:
    """Most recent verdict for each attack strategy tried against a chatbot."""
    latest: dict[str, dict[str, Any]] = {}
    for run in finished_runs(runs_for_target(runs, target_id)):
        strategy = run.get("strategy")
        if not strategy:
            continue
        current = latest.get(strategy)
        if current is None or (run.get("created_at") or "") >= (
            current.get("created_at") or ""
        ):
            latest[strategy] = run
    return {strategy: _outcome(run) for strategy, run in latest.items()}


def compare_targets(
    runs: list[dict[str, Any]],
    target_a: str | None,
    target_b: str | None,
    names_by_id: dict[str, str],
) -> dict[str, Any]:
    """Side-by-side comparison of two chatbots.

    The fair comparison only counts the tests both chatbots were given
    (``shared``); tests only one of them ran are listed but not scored, so a
    chatbot is not judged harder or easier just because it got different tests.
    """
    outcomes_a = latest_outcome_by_strategy(runs, target_a)
    outcomes_b = latest_outcome_by_strategy(runs, target_b)
    rows = [
        {
            "strategy": strategy,
            "a": outcomes_a.get(strategy),
            "b": outcomes_b.get(strategy),
        }
        for strategy in sorted(set(outcomes_a) | set(outcomes_b))
    ]
    judged = ("breached", "held")
    shared = [row for row in rows if row["a"] in judged and row["b"] in judged]
    return {
        "a": summarize_target(runs, target_a, names_by_id),
        "b": summarize_target(runs, target_b, names_by_id),
        "rows": rows,
        "shared_tests": len(shared),
        "a_shared_breached": sum(row["a"] == "breached" for row in shared),
        "b_shared_breached": sum(row["b"] == "breached" for row in shared),
    }
