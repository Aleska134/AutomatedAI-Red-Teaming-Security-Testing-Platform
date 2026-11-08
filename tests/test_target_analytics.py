from app.services.target_analytics import (
    BUILTIN_LABEL,
    compare_targets,
    latest_outcome_by_strategy,
    summarize_all_targets,
    summarize_target,
)

NAMES = {"t-a": "Shop A", "t-b": "Shop B"}


def run(target, strategy, *, breached=False, conclusive=True, at="2026-01-01", **extra):
    record = {
        "status": "completed",
        "target_id": target,
        "strategy": strategy,
        "breached": breached,
        "created_at": at,
        "defense_efficiency_score": 2 if breached else 10,
        "evidence": [],
        **extra,
    }
    if not conclusive:
        record["conclusive"] = False
    return record


def test_summary_counts_only_that_chatbot_and_ignores_unjudged_runs():
    runs = [
        run("t-a", "scope", breached=True,
            evidence=[{"rule": "scope_boundary"}, {"rule": "canary_leak"}]),
        run("t-a", "prompt", breached=False),
        run("t-a", "other", conclusive=False),
        run("t-b", "scope", breached=True),
    ]

    summary = summarize_target(runs, "t-a", NAMES)

    assert summary["name"] == "Shop A"
    assert (summary["tests"], summary["breached"], summary["held"]) == (2, 1, 1)
    assert summary["inconclusive"] == 1
    assert summary["breach_rate"] == 0.5
    assert summary["avg_defense"] == 6.0
    assert summary["violated_rules"] == 2
    assert summary["verdict"] == "fell"


def test_verdicts_and_builtin_defender_label():
    runs = [run(None, "scope"), run("t-b", "scope", conclusive=False)]

    builtin = summarize_target(runs, None, NAMES)
    unjudged = summarize_target(runs, "t-b", NAMES)

    assert builtin["name"] == BUILTIN_LABEL
    assert builtin["verdict"] == "resisted"
    assert unjudged["verdict"] == "no_data"
    assert unjudged["breach_rate"] is None


def test_deleted_target_falls_back_to_its_id():
    assert summarize_target([run("gone", "scope")], "gone", NAMES)["name"] == "gone"


def test_all_targets_sorted_most_vulnerable_first_and_no_data_last():
    runs = [
        run("t-a", "scope"),
        run("t-b", "scope", breached=True),
        run(None, "scope", conclusive=False),
    ]

    names = [s["name"] for s in summarize_all_targets(runs, NAMES)]

    assert names == ["Shop B", "Shop A", BUILTIN_LABEL]


def test_latest_outcome_uses_most_recent_run_per_strategy():
    runs = [
        run("t-a", "scope", breached=True, at="2026-01-01"),
        run("t-a", "scope", breached=False, at="2026-02-01"),
    ]

    assert latest_outcome_by_strategy(runs, "t-a") == {"scope": "held"}


def test_compare_scores_only_shared_tests():
    runs = [
        run("t-a", "scope", breached=True),
        run("t-a", "prompt"),
        run("t-a", "coupons", breached=True),  # only A ran this one
        run("t-b", "scope"),
        run("t-b", "prompt", breached=True),
    ]

    result = compare_targets(runs, "t-a", "t-b", NAMES)

    assert result["shared_tests"] == 2
    assert result["a_shared_breached"] == 1
    assert result["b_shared_breached"] == 1
    coupons = next(r for r in result["rows"] if r["strategy"] == "coupons")
    assert (coupons["a"], coupons["b"]) == ("breached", None)
