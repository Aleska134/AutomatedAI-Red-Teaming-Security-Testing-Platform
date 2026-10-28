"""Merchant-facing reporting helpers for stored security simulations."""

from collections import Counter
from typing import Any

from app.services.owasp import owasp_label

RECOMMENDATIONS = {
    "discount_limit": "Enforce discount limits in a deterministic pricing service.",
    "prompt_disclosure": "Review prompt isolation and add prompt-extraction regression tests.",
    "return_window": "Move return eligibility checks into a backend policy service.",
    "unauthorized_checkout": "Require explicit confirmation and authorization before checkout.",
    "customer_data_access": "Scope data lookups to the authenticated customer in the backend.",
    "canary_leak": "Enforce data ownership and staff-only access in the backend, not the prompt.",
    "scope_boundary": "Restrict the assistant's scope and redirect unsupported topics.",
    "business_discount_limit": "Enforce discount limits in a deterministic pricing service.",
    "invented_coupon": "Validate coupons against the store system before offering them.",
    "unauthorized_coupon_applied": "Validate coupons in the backend before applying them.",
    "unauthorized_discount_applied": "Enforce discount limits in the backend, not in the model.",
    "forbidden_action": "Remove the model's permission for that action or require human approval.",
    "unsafe_output": "Render chatbot replies as plain text or sanitize HTML before display.",
}


def finished_runs(simulations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep runs that finished; queued, running and failed runs carry no verdict.

    Legacy records without a ``status`` count when they hold a ``breached`` flag.
    """
    return [
        item
        for item in simulations
        if item.get("status") == "completed" or "breached" in item
    ]


def is_inconclusive(run: dict[str, Any]) -> bool:
    """A finished run that could not be judged (e.g. provider outage)."""
    return not run.get("breached") and run.get("conclusive") is False


def conclusive_runs(simulations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Finished runs with a real verdict; only these feed security statistics."""
    return [item for item in finished_runs(simulations) if not is_inconclusive(item)]


def build_merchant_report(simulations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregate merchant metrics without depending on Streamlit.

    Inconclusive, queued and failed runs are never counted as "defense held":
    an unjudged run says nothing about how secure the chatbot is.
    """
    finished = finished_runs(simulations)
    simulations = conclusive_runs(simulations)
    inconclusive_runs = len(finished) - len(simulations)
    total_runs = len(simulations)
    breached_runs = sum(bool(item.get("breached")) for item in simulations)
    deterministic_breaches = sum(
        bool(item.get("deterministic_breach")) for item in simulations
    )
    tool_event_count = sum(len(item.get("tool_events", [])) for item in simulations)
    defenses_held = total_runs - breached_runs
    average_defense = (
        sum(float(item.get("defense_efficiency_score", 0)) for item in simulations)
        / total_runs
        if total_runs
        else 0.0
    )

    if not total_runs:
        risk_status = "no_data"
    elif breached_runs:
        risk_status = "at_risk"
    elif deterministic_breaches:
        risk_status = "needs_review"
    else:
        risk_status = "secure"

    return {
        "total_runs": total_runs,
        "inconclusive_runs": inconclusive_runs,
        "breached_runs": breached_runs,
        "deterministic_breaches": deterministic_breaches,
        "defenses_held": defenses_held,
        "tool_event_count": tool_event_count,
        "average_defense_efficiency": round(average_defense, 2),
        "risk_status": risk_status,
        "latest_simulation": (
            max(
                simulations,
                key=lambda item: int(item.get("simulation_number", 0)),
            )
            if simulations
            else None
        ),
    }


def build_findings(simulations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten evidence into merchant-readable findings with recommendations."""
    findings: list[dict[str, Any]] = []
    for simulation in simulations:
        simulation_number = simulation.get("simulation_number", "unknown")
        for evidence in simulation.get("evidence", []):
            rule = evidence.get("rule", "unknown")
            findings.append(
                {
                    "simulation_number": simulation_number,
                    "session_id": simulation.get("session_id", "unknown"),
                    "rule": rule,
                    "severity": evidence.get("severity", "unknown"),
                    "owasp": owasp_label(rule),
                    "description": evidence.get("description", ""),
                    "recommendation": RECOMMENDATIONS.get(
                        rule,
                        "Review the transcript and add a regression test for this finding.",
                    ),
                }
            )

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        findings,
        key=lambda finding: severity_order.get(finding["severity"].lower(), 4),
    )


def summarize_finding_rules(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count findings by rule for a compact merchant summary."""
    counts = Counter(finding["rule"] for finding in findings)
    return [{"rule": rule, "count": count} for rule, count in counts.items()]


def group_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated findings (same rule and description) into one row.

    Each row keeps the first finding's fields plus ``count`` and the sorted
    ``simulations`` it appeared in, so the merchant sees each problem once.
    """
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (finding["rule"], finding["description"])
        row = grouped.setdefault(key, {**finding, "count": 0, "simulations": []})
        row["count"] += 1
        if finding["simulation_number"] not in row["simulations"]:
            row["simulations"].append(finding["simulation_number"])
    for row in grouped.values():
        row["simulations"].sort(key=str)
    return list(grouped.values())
