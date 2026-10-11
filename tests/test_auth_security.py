"""Unit tests for password hashing and JWT helpers (no DB, no network)."""

import pytest

from app.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_token_roundtrip_carries_claims():
    token = create_access_token(subject="a@test.local", company_id="company-1", role="company")
    claims = decode_access_token(token)
    assert claims["sub"] == "a@test.local"
    assert claims["company_id"] == "company-1"
    assert claims["role"] == "company"


def test_expired_token_is_rejected():
    token = create_access_token(
        subject="a@test.local", company_id="company-1", role="company", expires_minutes=-1
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token(subject="a@test.local", company_id="company-1", role="company")
    with pytest.raises(TokenError):
        decode_access_token(token + "tampered")
