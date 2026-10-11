"""Persistence helpers for merchant security test runs."""

from datetime import datetime, timezone
from typing import Any

from tinydb import Query

from app.database import sessions_collection


def utc_now() -> str:
    """Return a consistently formatted UTC timestamp for stored runs."""
    return datetime.now(timezone.utc).isoformat()


def create_test_run(
    *,
    run_id: str,
    strategy: str,
    turns_requested: int,
    run_type: str = "manual",
    company_id: str | None = None,
) -> dict[str, Any]:
    """Create a queued test record before execution begins."""
    timestamp = utc_now()
    record = {
        "run_id": run_id,
        "session_id": run_id,
        "company_id": company_id,
        "run_type": run_type,
        "strategy": strategy,
        "turns_requested": turns_requested,
        "status": "queued",
        "created_at": timestamp,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None,
    }
    sessions_collection.insert(record)
    return record


def start_test_run(run_id: str) -> dict[str, Any]:
    """Mark a queued run as actively executing."""
    return update_test_run(
        run_id,
        status="running",
        started_at=utc_now(),
    )


def update_test_run(run_id: str, **fields: Any) -> dict[str, Any]:
    """Update a stored run and return its current record.

    ``run_id``/``session_id`` are the record's stable identifiers, so if they
    arrive in ``fields`` (for example when a full record is splatted back in)
    they are dropped rather than overwritten, keeping the identity consistent.
    """
    fields.pop("run_id", None)
    fields.pop("session_id", None)
    sessions_collection.update(fields, Query().run_id == run_id)
    result = get_test_run(run_id)
    if result is None:
        raise KeyError(f"Test run {run_id} was not found.")
    return result


def complete_test_run(run_id: str, **fields: Any) -> dict[str, Any]:
    """Mark a run completed while preserving its audit data."""
    fields.pop("status", None)
    fields.pop("completed_at", None)
    return update_test_run(
        run_id,
        **fields,
        status="completed",
        completed_at=utc_now(),
    )


def fail_test_run(run_id: str, error: str) -> dict[str, Any]:
    """Mark a run failed with an explicit error message."""
    return update_test_run(
        run_id,
        status="failed",
        failed_at=utc_now(),
        error=error,
    )


def get_test_run(run_id: str, company_id: str | None = None) -> dict[str, Any] | None:
    """Return one test run by its stable identifier.

    When ``company_id`` is provided, the run is only returned if it belongs to
    that company, enforcing tenant isolation.
    """
    result = sessions_collection.search(Query().run_id == run_id)
    if not result:
        return None
    record = result[0]
    if company_id is not None and record.get("company_id") != company_id:
        return None
    return record


def list_test_runs(company_id: str | None = None) -> list[dict[str, Any]]:
    """Return test runs newest first, optionally scoped to one company."""
    records = sessions_collection.search(Query().run_id.exists())
    if company_id is not None:
        records = [r for r in records if r.get("company_id") == company_id]
    return sorted(
        records,
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )
