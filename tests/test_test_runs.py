import uuid

from tinydb import Query

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
        )
        assert created["status"] == "queued"
        assert created["started_at"] is None

        started = start_test_run(run_id)
        assert started["status"] == "running"
        assert started["started_at"]

        completed = complete_test_run(
            run_id,
            simulation_number=1,
            total_turns=3,
            breached=False,
        )
        assert completed["status"] == "completed"
        assert completed["completed_at"]
        assert completed["total_turns"] == 3
        assert get_test_run(run_id)["run_id"] == run_id
        assert any(item["run_id"] == run_id for item in list_test_runs())
    finally:
        sessions_collection.remove(Query().run_id == run_id)


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
        sessions_collection.remove(Query().run_id == run_id)
