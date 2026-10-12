"""Configurable LLM provider layer.

Lets the attacker and judge agents run against OpenAI (default) or Google
Gemini, selected with the ``LLM_PROVIDER`` environment variable. This keeps the
platform provider-agnostic without changing agent logic, and lets you test
simulations with Gemini's free tier instead of spending OpenAI credit.

Scope (option B): this layer covers plain text generation (attacker) and JSON
generation (judge). The defender's tool-calling path still uses OpenAI directly
and falls back to deterministic refusals; unifying tool calling across
providers is deferred.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"


def get_provider() -> str:
    """Return the configured LLM provider name (defaults to OpenAI)."""
    provider = (os.getenv("LLM_PROVIDER") or PROVIDER_OPENAI).strip().lower()
    return provider if provider in {PROVIDER_OPENAI, PROVIDER_GEMINI} else PROVIDER_OPENAI


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _gemini_model() -> str:
    # A floating alias that tracks the current Gemini Flash model.
    return os.getenv("GEMINI_MODEL", "gemini-flash-latest")


@lru_cache
def _request_timeout() -> float:
    """Per-request LLM timeout in seconds (keeps simulations bounded)."""
    return float(os.getenv("LLM_REQUEST_TIMEOUT", "30"))


def _openai_client():
    from openai import OpenAI

    # Fail fast: a short timeout and no retries so an unavailable provider falls
    # back to deterministic behavior quickly instead of hanging a simulation.
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY") or "not-configured",
        timeout=_request_timeout(),
        max_retries=0,
    )


@lru_cache
def _gemini_client():
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "not-configured"
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(_request_timeout() * 1000)),
    )


def generate_text(
    system_prompt: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
) -> str:
    """Generate a plain-text completion from the configured provider.

    ``messages`` is a list of ``{"role": "user"|"assistant", "content": str}``.
    Raises on provider errors so callers can apply their own fallback.
    """
    if get_provider() == PROVIDER_GEMINI:
        return _gemini_text(system_prompt, messages, temperature)
    return _openai_text(system_prompt, messages, temperature)


def generate_json(
    system_prompt: str,
    user_content: str,
    *,
    temperature: float = 0.1,
) -> str:
    """Generate a JSON-formatted completion (returned as a raw JSON string)."""
    if get_provider() == PROVIDER_GEMINI:
        return _gemini_json(system_prompt, user_content, temperature)
    return _openai_json(system_prompt, user_content, temperature)


# --- OpenAI backend ------------------------------------------------------- #


def _openai_text(system_prompt: str, messages: list[dict], temperature: float) -> str:
    response = _openai_client().chat.completions.create(
        model=_openai_model(),
        messages=[{"role": "system", "content": system_prompt}, *messages],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


def _openai_json(system_prompt: str, user_content: str, temperature: float) -> str:
    response = _openai_client().chat.completions.create(
        model=_openai_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return response.choices[0].message.content or "{}"


# --- Gemini backend ------------------------------------------------------- #


def _gemini_contents(messages: list[dict]) -> list:
    """Map OpenAI-style messages to Gemini contents (assistant -> model)."""
    from google.genai import types

    contents = []
    for message in messages:
        role = "model" if message.get("role") == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=str(message.get("content", "")))],
            )
        )
    return contents


def _gemini_text(system_prompt: str, messages: list[dict], temperature: float) -> str:
    from google.genai import types

    response = _gemini_client().models.generate_content(
        model=_gemini_model(),
        contents=_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        ),
    )
    return (response.text or "").strip()


def _gemini_json(system_prompt: str, user_content: str, temperature: float) -> str:
    from google.genai import types

    response = _gemini_client().models.generate_content(
        model=_gemini_model(),
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return response.text or "{}"
