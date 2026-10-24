import uuid

from app.database import sessions_collection
from app.services.test_runs import (
    complete_test_run,
    create_test_run,
    fail_test_run,
    get_test_run,
    list_test_runs,
    start_test_run,
)


def test_test_run_lifecycle_persists_status_and_timestamps():
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    try:
        created = create_test_run(
            run_id=run_id,
            strategy="social_engineering",
            turns_requested=3,
            company_id="company-lifecycle",
        )
        assert created["status"] == "queued"
        assert created["started_at"] is None

        started = start_test_run(run_id)
        assert started["status"] == "running"
        assert started["started_at"]

        completed = complete_test_run(
            run_id,
            company_id="company-lifecycle",
            total_turns=3,
            breached=False,
        )
        assert completed["status"] == "completed"
        assert completed["completed_at"]
        assert completed["total_turns"] == 3
        # The number is assigned automatically (first completed run -> 1).
        assert completed["simulation_number"] == 1
        assert get_test_run(run_id)["run_id"] == run_id
        assert any(item["run_id"] == run_id for item in list_test_runs())
    finally:
        sessions_collection.remove(run_id=run_id)


def test_failed_test_run_records_explicit_error():
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    try:
        create_test_run(
            run_id=run_id,
            strategy="authority_override",
            turns_requested=1,
        )
        failed = fail_test_run(run_id, "provider unavailable")

        assert failed["status"] == "failed"
        assert failed["failed_at"]
        assert failed["error"] == "provider unavailable"
    finally:
        sessions_collection.remove(run_id=run_id)


def test_complete_run_tolerates_splatted_record_with_identifiers():
    """Regression: completing a run by splatting a full record (which already
    contains run_id/session_id) must not raise a duplicate-argument error."""
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    try:
        created = create_test_run(
            run_id=run_id,
            strategy="social_engineering",
            turns_requested=1,
            company_id="company-xyz",
        )
        start_test_run(run_id)

        # Mirror the router: build a record from the created one and splat it.
        record = {**created, "breached": False, "analysis": "ok"}
        record.pop("run_id", None)
        record.pop("session_id", None)
        record.pop("company_id", None)
        completed = complete_test_run(run_id, company_id="company-xyz", **record)

        assert completed["status"] == "completed"
        assert completed["run_id"] == run_id
        assert completed["company_id"] == "company-xyz"
    finally:
        sessions_collection.remove(run_id=run_id)
