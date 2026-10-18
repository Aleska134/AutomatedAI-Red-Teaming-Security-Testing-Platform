"""Authentication configuration.

Secrets come from the environment. Only APP_ENV=development may fall back to a
built-in secret; any other environment refuses to start without a strong
JWT_SECRET_KEY, so a misconfigured deployment cannot accept forged tokens.
"""

import os

from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
IS_DEVELOPMENT = APP_ENV == "development"

_DEV_SECRET = "local-development-secret-change-me"
_MIN_SECRET_LENGTH = 32


def _load_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if IS_DEVELOPMENT:
        return secret or _DEV_SECRET
    if not secret or len(secret) < _MIN_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to at least 32 characters outside "
            "APP_ENV=development."
        )
    return secret


# HS256 signing secret for JWTs.
JWT_SECRET_KEY = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
# Access-token lifetime in minutes.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

# Optional first-admin bootstrap. If both are set, an admin account is created
# (or updated) at startup. Never hardcode real credentials.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
