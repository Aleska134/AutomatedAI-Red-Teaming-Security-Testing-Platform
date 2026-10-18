"""Company and user account management (registration, login, access control).

Multi-tenancy model (Option A): a single database with every record scoped by
``company_id``. A company registers in ``pending`` status and cannot operate
until an admin activates it, which gives the platform owner explicit control
over who gets access (useful for an approval-gated or subscription service).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.auth.config import ADMIN_EMAIL, ADMIN_PASSWORD
from app.auth.security import hash_password, verify_password
from app.database import companies_collection, users_collection

# Company lifecycle states.
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
VALID_STATUSES = {STATUS_PENDING, STATUS_ACTIVE, STATUS_SUSPENDED}

# User roles.
ROLE_ADMIN = "admin"
ROLE_COMPANY = "company"


class AccountError(Exception):
    """Base error for account operations."""


class DuplicateAccountError(AccountError):
    """Raised when an email is already registered."""


class AuthenticationError(AccountError):
    """Raised when credentials are invalid."""


class InactiveAccountError(AccountError):
    """Raised when a valid user belongs to a non-active company."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_reset_token(token: str) -> str:
    """Reset tokens are stored hashed so a database leak cannot be replayed."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bump_token_version(user: dict[str, Any]) -> int:
    return int(user.get("token_version", 0)) + 1


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    result = users_collection.find(email=_normalize_email(email))
    return dict(result[0]) if result else None


def get_company(company_id: str) -> Optional[dict[str, Any]]:
    result = companies_collection.find(company_id=company_id)
    return dict(result[0]) if result else None


def _public_company(company: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": company["company_id"],
        "name": company["name"],
        "status": company["status"],
        "created_at": company["created_at"],
    }


def register_company(
    *,
    company_name: str,
    email: str,
    password: str,
    role: str = ROLE_COMPANY,
    status: str = STATUS_PENDING,
) -> dict[str, Any]:
    """Register a new company and its first user.

    New companies start as ``pending`` so an admin must approve them before
    they can run tests.
    """
    normalized = _normalize_email(email)
    if get_user_by_email(normalized) is not None:
        raise DuplicateAccountError("An account with this email already exists.")

    company_id = f"company-{uuid.uuid4().hex[:12]}"
    user_id = f"user-{uuid.uuid4().hex[:12]}"
    timestamp = _utc_now()

    company = {
        "company_id": company_id,
        "name": company_name.strip() or company_id,
        "status": status,
        "created_at": timestamp,
    }
    user = {
        "user_id": user_id,
        "company_id": company_id,
        "email": normalized,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": timestamp,
    }
    companies_collection.insert(company)
    users_collection.insert(user)
    return {"company": _public_company(company), "user_id": user_id, "role": role}


def authenticate(email: str, password: str) -> dict[str, Any]:
    """Verify credentials and return the user plus its company.

    Admins may authenticate regardless of company status; non-admin users must
    belong to an active company.
    """
    user = get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise AuthenticationError("Invalid email or password.")

    company = get_company(user["company_id"])
    if company is None:
        raise AuthenticationError("Invalid email or password.")

    if user["role"] != ROLE_ADMIN and company["status"] != STATUS_ACTIVE:
        raise InactiveAccountError(
            "This company account is not active yet. Please contact the administrator."
        )
    return {"user": user, "company": company}


def list_companies() -> list[dict[str, Any]]:
    """Return all registered companies (admin view), newest first."""
    companies = companies_collection.all()
    return sorted(
        (_public_company(c) for c in companies),
        key=lambda item: item["created_at"],
        reverse=True,
    )


def set_company_status(company_id: str, status: str) -> dict[str, Any]:
    """Activate or suspend a company (admin action)."""
    if status not in VALID_STATUSES:
        raise AccountError(f"Invalid status '{status}'.")
    if get_company(company_id) is None:
        raise AccountError(f"Company '{company_id}' was not found.")
    companies_collection.update({"status": status}, company_id=company_id)
    return _public_company(get_company(company_id))


def change_password(email: str, current_password: str, new_password: str) -> None:
    """Change a user's password after verifying the current one."""
    user = get_user_by_email(email)
    if user is None or not verify_password(current_password, user["password_hash"]):
        raise AuthenticationError("The current password is incorrect.")
    users_collection.update(
        {
            "password_hash": hash_password(new_password),
            "token_version": _bump_token_version(user),
        },
        email=_normalize_email(email),
    )


def create_password_reset_token(email: str) -> Optional[str]:
    """Create a single-use reset token for an existing account.

    Returns the token so a caller can deliver it (e.g. by email). Returns None
    when the email is unknown; callers should still respond generically so the
    endpoint does not reveal whether an account exists.
    """
    user = get_user_by_email(email)
    if user is None:
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    users_collection.update(
        {"reset_token": _hash_reset_token(token), "reset_token_expires": expires},
        email=_normalize_email(email),
    )
    return token


def reset_password_with_token(token: str, new_password: str) -> None:
    """Consume a valid, unexpired reset token and set a new password."""
    if not token:
        raise AuthenticationError("Invalid or expired reset token.")
    result = users_collection.find(reset_token=_hash_reset_token(token))
    if not result:
        raise AuthenticationError("Invalid or expired reset token.")
    user = result[0]
    expires = user.get("reset_token_expires")
    if not expires or datetime.fromisoformat(expires) < datetime.now(timezone.utc):
        raise AuthenticationError("Invalid or expired reset token.")
    users_collection.update(
        {
            "password_hash": hash_password(new_password),
            "token_version": _bump_token_version(user),
            "reset_token": None,
            "reset_token_expires": None,
        },
        user_id=user["user_id"],
    )


def ensure_admin_user() -> None:
    """Create or refresh the bootstrap admin from environment variables.

    No-op unless both ADMIN_EMAIL and ADMIN_PASSWORD are set. The admin's
    company is always active.
    """
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return

    existing = get_user_by_email(ADMIN_EMAIL)
    if existing is not None:
        # Keep the admin password in sync with the environment and ensure role.
        users_collection.update(
            {"password_hash": hash_password(ADMIN_PASSWORD), "role": ROLE_ADMIN},
            email=_normalize_email(ADMIN_EMAIL),
        )
        companies_collection.update(
            {"status": STATUS_ACTIVE}, company_id=existing["company_id"]
        )
        return

    register_company(
        company_name="Platform Administration",
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        role=ROLE_ADMIN,
        status=STATUS_ACTIVE,
    )
