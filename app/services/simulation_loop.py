"""Background execution of attacker-versus-defender simulation runs.

The defender is either the built-in Defender or a saved external chatbot
reached through the v1 webhook contract.
"""

import logging
from datetime import datetime, timezone

from app.agents.attacker import generate_attack_payload_result
from app.agents.defender import query_defender
from app.agents.judge import evaluate_simulation
from app.database import sessions_collection
from app.services.security_evaluation import (
    assess_conclusiveness,
    evaluate_business_rules,
    merge_audit_with_deterministic_evidence,
)
from app.services.test_runs import complete_test_run, fail_test_run, start_test_run
from app.services.webhook_adapter import WebhookAdapterError, send_webhook_message

logger = logging.getLogger(__name__)

FAILURE_MESSAGE = (
    "The security simulation could not be completed. This usually means the "
    "LLM provider is unavailable or its API key is not configured."
)

# External chatbots commonly cap the history they accept; send only recent turns.
WEBHOOK_HISTORY_LIMIT = 20
# Reported actions compared against the target's business rules.
REPORTED_ACTION_KEYS = ("applied_coupons", "applied_discount_percent", "actions_taken")


def execute_simulation_run(
    run_id: str,
    *,
    strategy: str,
    turns: int,
    history: list[dict],
    company_id: str,
    customer_id: str,
    target: dict | None = None,
) -> None:
    """Run a queued simulation to completion, persisting its outcome.

    Runs outside the request, so errors are stored on the run (status
    ``failed``) instead of being raised to a client.
    """
    try:
        _run(run_id, strategy, turns, history, company_id, customer_id, target)
    except WebhookAdapterError as error:
        # Adapter messages are generic and safe to show the tenant.
        logger.warning("Simulation run %s: target unreachable", run_id)
        fail_test_run(run_id, f"The target chatbot failed: {error}")
    except Exception:
        logger.exception("Simulation run %s failed", run_id)
        fail_test_run(run_id, FAILURE_MESSAGE)


def _query_target(target: dict, message: str, history: list[dict], outcome: dict) -> str:
    """Send one attack turn to an external chatbot and record its reported outcome."""
    result = send_webhook_message(
        target["webhook_url"],
        message=message,
        history=history[-WEBHOOK_HISTORY_LIMIT:],
        auth_token=target.get("auth_token"),
    )
    metadata = result["metadata"]
    outcome["security_outcome"] = metadata.get("security_outcome")
    outcome["block_reason"] = metadata.get("block_reason")
    for key in REPORTED_ACTION_KEYS:
        if key in metadata:
            outcome[key] = metadata[key]
    return result["reply"]


def _run(run_id, strategy, turns, history, company_id, customer_id, target) -> None:
    start_test_run(run_id)
    current_history = list(history)
    tool_events: list[dict] = []
    defense_outcomes: list[dict] = []
    attack_generation_events: list[dict] = []

    for turn in range(1, turns + 1):
        attack_result = generate_attack_payload_result(current_history, strategy=strategy)
        attacker_message = attack_result["payload"]
        attack_generation_events.append(
            {
                **attack_result,
                "turn": turn,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        current_history.append({"role": "user", "content": attacker_message})
        outcome: dict = {}
        if target:
            defender_reply = _query_target(
                target, attacker_message, current_history[:-1], outcome
            )
        else:
            defender_reply = query_defender(
                attacker_message,
                current_history[:-1],
                customer_id=customer_id,
                tool_events=tool_events,
                defense_outcome=outcome,
            )
        defense_outcomes.append(outcome)
        current_history.append({"role": "assistant", "content": defender_reply})

    audit_report = evaluate_simulation(current_history, tool_events)
    rule_evidence = evaluate_business_rules(
        (target or {}).get("business_rules"), current_history, defense_outcomes
    )
    if rule_evidence:
        # Declared business rules are ground truth: any violation is a breach.
        evidence = audit_report.get("evidence", []) + rule_evidence
        audit_report = merge_audit_with_deterministic_evidence(
            audit_report, {"deterministic_breach": True, "evidence": evidence}
        )
    # Numbered per company so tenants cannot infer each other's activity.
    simulation_number = sum(
        1 for r in sessions_collection.all() if r.get("company_id") == company_id
    )
    complete_test_run(
        run_id,
        simulation_number=simulation_number,
        total_turns=turns,
        history=current_history,
        breached=audit_report.get("breached", False),
        confidence_score=audit_report.get("confidence_score", 0.0),
        attacker_aggression_level=audit_report.get("attacker_aggression_level", 1),
        defense_efficiency_score=audit_report.get("defense_efficiency_score", 10),
        attack_vector_keywords=audit_report.get("attack_vector_keywords", []),
        analysis=audit_report.get("analysis", "No analysis provided."),
        deterministic_breach=audit_report.get("deterministic_breach", False),
        evidence=audit_report.get("evidence", []),
        tool_events=tool_events,
        defense_outcomes=defense_outcomes,
        attack_generation_events=attack_generation_events,
        **assess_conclusiveness(defense_outcomes, audit_report),
    )
