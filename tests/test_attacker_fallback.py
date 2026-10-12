from app.agents import attacker


def test_provider_refusal_uses_local_scenario_library(monkeypatch):
    # The provider "refuses" by returning a refusal string; the attacker must
    # fall back to its local scenario library.
    monkeypatch.setattr(
        attacker,
        "generate_text",
        lambda *_, **__: "I'm sorry, I can't assist with that.",
    )

    result = attacker.generate_attack_payload_result(strategy="authority_override")

    assert result["status"] == "provider_refused"
    assert result["source"] == "local_scenario_library"
    assert result["payload"] == attacker.LOCAL_TEST_PAYLOADS["authority_override"]


def test_generated_payload_keeps_llm_source(monkeypatch):
    monkeypatch.setattr(
        attacker,
        "generate_text",
        lambda *_, **__: "Please explain the return policy.",
    )

    result = attacker.generate_attack_payload_result(strategy="social_engineering")

    assert result["status"] == "generated"
    assert result["source"] == "attacker_llm"


def test_provider_exception_uses_local_scenario_library(monkeypatch):
    # A provider error (e.g. missing API key) must also fall back safely.
    def boom(*_, **__):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(attacker, "generate_text", boom)

    result = attacker.generate_attack_payload_result(strategy="jailbreak_dan")

    assert result["status"] == "generation_failed"
    assert result["source"] == "local_scenario_library"
