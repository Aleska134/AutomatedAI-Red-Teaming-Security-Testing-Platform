"""FastAPI dependencies that enforce authentication and tenancy."""

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import TokenError, decode_access_token
from app.services.accounts import (
    ROLE_ADMIN,
    STATUS_ACTIVE,
    get_company,
    get_user_by_email,
)

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    """Resolve the authenticated user + company from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    try:
        claims = decode_access_token(credentials.credentials)
    except TokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    user = get_user_by_email(claims.get("sub", ""))
    if user is None:
        raise _UNAUTHORIZED
    company = get_company(user["company_id"])
    if company is None:
        raise _UNAUTHORIZED
    return {"user": user, "company": company, "claims": claims}


def require_admin(
    principal: dict[str, Any] = Depends(get_current_principal),
) -> dict[str, Any]:
    """Allow only platform administrators."""
    if principal["user"]["role"] != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges are required.",
        )
    return principal


def require_active_company(
    principal: dict[str, Any] = Depends(get_current_principal),
) -> dict[str, Any]:
    """Allow operations only for users of an active company (admins exempt)."""
    user = principal["user"]
    company = principal["company"]
    if user["role"] != ROLE_ADMIN and company["status"] != STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This company account is not active yet.",
        )
    return principal
