"""Offline tests for the configurable LLM provider layer (no real API calls)."""

import pytest

from app.agents import llm_provider


def test_defaults_to_openai(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm_provider.get_provider() == "openai"


def test_unknown_provider_falls_back_to_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "totally-unknown")
    assert llm_provider.get_provider() == "openai"


@pytest.mark.parametrize("value,expected", [("gemini", "gemini"), ("OpenAI", "openai")])
def test_provider_selection(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_PROVIDER", value)
    assert llm_provider.get_provider() == expected


def test_generate_text_routes_to_selected_backend(monkeypatch):
    calls = {}

    def fake_gemini_text(system_prompt, messages, temperature):
        calls["gemini"] = (system_prompt, messages, temperature)
        return "gemini-out"

    monkeypatch.setattr(llm_provider, "get_provider", lambda: "gemini")
    monkeypatch.setattr(llm_provider, "_gemini_text", fake_gemini_text)

    out = llm_provider.generate_text("sys", [{"role": "user", "content": "hi"}], temperature=0.5)
    assert out == "gemini-out"
    assert calls["gemini"][0] == "sys"


def test_gemini_contents_maps_roles():
    # Mapping relies on the SDK's types; skip gracefully if it is unavailable.
    pytest.importorskip("google.genai")
    contents = llm_provider._gemini_contents(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
    )
    assert contents[0].role == "user"
    # OpenAI's "assistant" role maps to Gemini's "model" role.
    assert contents[1].role == "model"
    # The request must end on a user turn, so a continuation prompt is appended.
    assert contents[-1].role == "user"


def test_gemini_contents_empty_history_gets_user_turn():
    pytest.importorskip("google.genai")
    contents = llm_provider._gemini_contents([])
    # Gemini rejects empty requests; we must send at least one user turn.
    assert len(contents) == 1
    assert contents[0].role == "user"


def test_gemini_contents_ending_in_user_is_unchanged():
    pytest.importorskip("google.genai")
    contents = llm_provider._gemini_contents(
        [{"role": "user", "content": "attack please"}]
    )
    assert len(contents) == 1
    assert contents[0].role == "user"


def test_gemini_contents_skips_empty_messages():
    pytest.importorskip("google.genai")
    contents = llm_provider._gemini_contents(
        [{"role": "user", "content": ""}]
    )
    # The empty message is skipped, then a continuation user turn is added.
    assert len(contents) == 1
    assert contents[0].role == "user"
