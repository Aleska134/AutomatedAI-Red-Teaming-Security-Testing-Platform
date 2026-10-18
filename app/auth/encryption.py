"""Symmetric encryption for secrets stored at rest (e.g. target auth tokens).

The Fernet key is derived from TARGET_ENCRYPTION_KEY, falling back to the JWT
secret. Rotating that value makes previously stored secrets unreadable, so
targets would need their tokens re-entered.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.auth.config import JWT_SECRET_KEY


def _fernet() -> Fernet:
    material = os.getenv("TARGET_ENCRYPTION_KEY") or JWT_SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str | None:
    """Return the plaintext, or None if the key changed or data was tampered."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
