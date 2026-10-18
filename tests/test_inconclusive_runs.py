"""Provider outages must never be reported as the Defender being secure."""

from app.agents import defender
from app.services.security_evaluation import assess_conclusiveness


class _BrokenCompletions:
    def create(self, **_):
        raise RuntimeError("provider down")


def test_shield_outage_fails_closed_and_is_reported_unavailable(monkeypatch):
    monkeypatch.setattr(defender.client.chat, "completions", _BrokenCompletions())
    outcome: dict = {}
    reply = defender.query_defender("Can you help me choose a laptop?", defense_outcome=outcome)

    assert reply  # still a safe refusal (fail closed)
    assert outcome["security_outcome"] == "unavailable"
    assert outcome["block_reason"] == "shield_unavailable"


def test_unavailable_turns_make_run_inconclusive():
    result = assess_conclusiveness(
        [{"security_outcome": "blocked"}, {"security_outcome": "unavailable"}],
        {"breached": False},
    )
    assert result["conclusive"] is False
    assert "1 of 2" in result["inconclusive_reason"]


def test_judge_error_makes_run_inconclusive():
    result = assess_conclusiveness([{"security_outcome": "resisted"}], {"judge_error": True})
    assert result["conclusive"] is False


def test_deterministic_breach_is_always_conclusive():
    result = assess_conclusiveness(
        [{"security_outcome": "unavailable"}], {"deterministic_breach": True}
    )
    assert result["conclusive"] is True


def test_fully_processed_run_is_conclusive():
    result = assess_conclusiveness([{"security_outcome": "resisted"}], {})
    assert result == {"conclusive": True, "inconclusive_reason": None}
