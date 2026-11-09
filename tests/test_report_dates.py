from app.services.merchant_reporting import build_findings, group_findings
from app.services.run_report import render_combined_report, render_run_report


def _run(run_id="r1", started="2026-01-28T15:00:00+00:00", done="2026-01-28T15:02:05+00:00", **extra):
    return {
        "run_id": run_id, "session_id": run_id, "simulation_number": 1, "strategy": "scope",
        "breached": False, "created_at": "2026-01-28T14:59:00+00:00", "started_at": started,
        "completed_at": done, "history": [], "evidence": [], **extra,
    }


def test_single_report_shows_readable_date_and_duration():
    html = render_run_report(_run())
    assert "28 Jan 2026, 15:00 UTC" in html
    assert "Duration: 2 min 05 s" in html
    assert "2026-01-28T15:00:00" not in html  # no raw ISO string


def test_report_uses_the_viewers_time_zone_and_language():
    html = render_run_report(_run(), "es", "America/New_York")
    assert "28 ene 2026, 10:00 EST" in html
    assert "Duración: 2 min 05 s" in html


def test_report_records_when_it_was_generated():
    assert "Report generated: " in render_run_report(_run())
    assert "Reporte generado: " in render_run_report(_run(), "es")


def test_run_that_never_started_falls_back_to_queue_time_without_duration():
    html = render_run_report(_run(started=None, done=None))
    assert "28 Jan 2026, 14:59 UTC" in html
    assert "Duration" not in html


def test_unreadable_dates_never_break_or_inject():
    html = render_run_report(_run(started="<script>x</script>", done="nope"))
    assert "<script>x" not in html
    assert "&lt;script&gt;" in html


def test_combined_report_shows_the_period_covered():
    runs = [
        _run("a", started="2026-01-28T15:00:00+00:00"),
        _run("b", started="2026-02-02T09:30:00+00:00"),
    ]
    html = render_combined_report(runs, "en")
    assert "Tests run between" in html
    assert "28 Jan 2026, 15:00 UTC" in html and "2 Feb 2026, 09:30 UTC" in html


def test_combined_report_without_runs_still_renders():
    assert "Tests run between" not in render_combined_report([], "en")


def test_findings_remember_when_they_were_last_seen():
    evidence = [{"rule": "canary_leak", "description": "Leaked."}]
    findings = build_findings([
        _run("a", evidence=evidence, completed_at="2026-01-01T10:00:00+00:00"),
        _run("b", evidence=evidence, completed_at="2026-03-01T10:00:00+00:00"),
        _run("c", evidence=evidence, completed_at=None, created_at="2026-02-01T10:00:00+00:00"),
    ])
    (row,) = group_findings(findings)
    assert row["count"] == 3
    assert row["last_seen"] == "2026-03-01T10:00:00+00:00"
