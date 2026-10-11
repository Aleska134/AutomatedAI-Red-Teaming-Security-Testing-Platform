from types import SimpleNamespace

from app.agents import attacker


def test_provider_refusal_uses_local_scenario_library(monkeypatch):
    refusal = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="I'm sorry, I can't assist with that.")
            )
        ]
    )
    monkeypatch.setattr(
        attacker.client.chat.completions,
        "create",
        lambda **_: refusal,
    )

    result = attacker.generate_attack_payload_result(
        strategy="authority_override",
    )

    assert result["status"] == "provider_refused"
    assert result["source"] == "local_scenario_library"
    assert result["payload"] == attacker.LOCAL_TEST_PAYLOADS["authority_override"]


def test_generated_payload_keeps_llm_source(monkeypatch):
    generated = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Please explain the return policy.")
            )
        ]
    )
    monkeypatch.setattr(
        attacker.client.chat.completions,
        "create",
        lambda **_: generated,
    )

    result = attacker.generate_attack_payload_result(strategy="social_engineering")

    assert result["status"] == "generated"
    assert result["source"] == "attacker_llm"
