"""Tests for the dashboard's user-facing error message helper.

``humanize_error`` turns FastAPI error responses — both plain-string
``detail`` (HTTPException) and the list-of-objects ``detail`` that 422
validation errors produce — into plain language a non-technical user can act
on, never exposing words like "string" or raw JSON.
"""

from app.frontend_auth import humanize_error


class FakeResponse:
    """Minimal stand-in for a requests.Response with a .json() method."""

    def __init__(self, payload, raise_json=False):
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("No JSON body")
        return self._payload


def _validation(detail):
    return FakeResponse({"detail": detail})


def test_empty_required_field_reads_as_required():
    # The exact error a user hit: signing in with an empty password.
    response = _validation(
        [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 1 character",
                "ctx": {"min_length": 1},
            }
        ]
    )
    message = humanize_error(response, "Sign in failed.")
    assert message == "Password is required."
    # Never leak the technical vocabulary.
    assert "string" not in message.lower()
    assert "character" not in message.lower()


def test_missing_field_reads_as_required():
    response = _validation(
        [{"type": "missing", "loc": ["body", "email"], "msg": "Field required"}]
    )
    assert humanize_error(response, "x") == "Email is required."


def test_too_short_with_real_minimum():
    response = _validation(
        [
            {
                "type": "string_too_short",
                "loc": ["body", "new_password"],
                "msg": "String should have at least 8 characters",
                "ctx": {"min_length": 8},
            }
        ]
    )
    assert humanize_error(response, "x") == "New password must be at least 8 characters long."


def test_invalid_email_message():
    response = _validation(
        [{"type": "value_error", "loc": ["body", "email"], "msg": "not valid"}]
    )
    assert humanize_error(response, "x") == "Please enter a valid email address."


def test_invalid_webhook_url_message():
    response = _validation(
        [{"type": "value_error", "loc": ["body", "webhook_url"], "msg": "bad"}]
    )
    message = humanize_error(response, "x")
    assert "valid URL" in message
    assert "http" in message


def test_multiple_errors_are_joined_and_deduped():
    response = _validation(
        [
            {"type": "value_error", "loc": ["body", "email"], "msg": "x"},
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "y",
                "ctx": {"min_length": 1},
            },
        ]
    )
    message = humanize_error(response, "x")
    assert "Please enter a valid email address." in message
    assert "Password is required." in message


def test_plain_string_detail_passes_through():
    # Normal HTTPException detail (e.g. wrong credentials) is already readable.
    response = FakeResponse({"detail": "Invalid email or password."})
    assert humanize_error(response, "Sign in failed.") == "Invalid email or password."


def test_no_json_body_uses_fallback():
    # A 500 returning HTML, or any non-JSON body, falls back cleanly.
    response = FakeResponse(None, raise_json=True)
    assert humanize_error(response, "Could not save target.") == "Could not save target."


def test_empty_detail_uses_fallback():
    assert humanize_error(FakeResponse({}), "fallback here") == "fallback here"


def test_unknown_field_is_humanized_not_raw():
    # A field without a friendly label should still read cleanly, not as a raw key.
    response = _validation(
        [{"type": "missing", "loc": ["body", "some_new_field"], "msg": "Field required"}]
    )
    assert humanize_error(response, "x") == "Some new field is required."
