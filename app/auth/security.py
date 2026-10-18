"""Password hashing and JWT helpers.

Uses bcrypt directly for password hashing and PyJWT for signed access tokens.
These functions are pure and deterministic enough to test offline.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.auth.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)

# bcrypt rejects passwords longer than 72 bytes; we enforce a safe cap earlier
# at the schema level, and truncate defensively here.
_BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a token cannot be decoded or is invalid/expired."""


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given plaintext password."""
    password_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        password_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    subject: str,
    company_id: str,
    role: str,
    token_version: int = 0,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Create a signed JWT carrying the principal's identity and tenancy."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "company_id": company_id,
        "role": role,
        # Bumped on every password change/reset to revoke older sessions.
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT, raising TokenError on any problem."""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as error:
        raise TokenError(str(error)) from error
