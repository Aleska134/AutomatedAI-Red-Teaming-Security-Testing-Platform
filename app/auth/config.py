"""Authentication configuration.

Secrets come from the environment. In local development a stable default secret
is used so tokens survive a reload, but production MUST set JWT_SECRET_KEY.
"""

import os

# HS256 signing secret for JWTs. Override in any real deployment.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "local-development-secret-change-me")
JWT_ALGORITHM = "HS256"
# Access-token lifetime in minutes.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

# Optional first-admin bootstrap. If both are set, an admin account is created
# (or updated) at startup. Never hardcode real credentials.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
