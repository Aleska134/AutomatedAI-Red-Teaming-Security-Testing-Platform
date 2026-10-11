"""Per-company onboarded chatbot targets.

A target promotes a transient webhook URL into a saved, reusable record scoped
to one company. Every read is filtered by ``company_id`` so one company can
never see or test another company's targets.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from tinydb import Query

from app.database import targets_collection


class TargetError(Exception):
    """Raised when a target operation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(target: dict[str, Any]) -> dict[str, Any]:
    """Public view: never expose the stored auth token."""
    return {
        "target_id": target["target_id"],
        "company_id": target["company_id"],
        "name": target["name"],
        "webhook_url": target["webhook_url"],
        "has_auth_token": bool(target.get("auth_token")),
        "created_at": target["created_at"],
    }


def create_target(
    *,
    company_id: str,
    name: str,
    webhook_url: str,
    auth_token: Optional[str] = None,
) -> dict[str, Any]:
    target = {
        "target_id": f"target-{uuid.uuid4().hex[:12]}",
        "company_id": company_id,
        "name": name.strip(),
        "webhook_url": webhook_url.strip(),
        "auth_token": auth_token,
        "created_at": _utc_now(),
    }
    targets_collection.insert(target)
    return _public(target)


def list_targets(company_id: str) -> list[dict[str, Any]]:
    records = targets_collection.search(Query().company_id == company_id)
    return sorted(
        (_public(t) for t in records),
        key=lambda item: item["created_at"],
        reverse=True,
    )


def get_target(company_id: str, target_id: str) -> Optional[dict[str, Any]]:
    """Return the raw target record only if it belongs to the company."""
    result = targets_collection.search(
        (Query().target_id == target_id) & (Query().company_id == company_id)
    )
    return dict(result[0]) if result else None


def delete_target(company_id: str, target_id: str) -> bool:
    if get_target(company_id, target_id) is None:
        return False
    targets_collection.remove(
        (Query().target_id == target_id) & (Query().company_id == company_id)
    )
    return True
