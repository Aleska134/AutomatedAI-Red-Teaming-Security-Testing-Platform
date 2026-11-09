import pytest

from app.services.timefmt import (
    format_duration,
    format_timestamp,
    parse_timestamp,
    resolve_timezone,
    run_time,
)

STAMP = "2026-01-28T15:05:09+00:00"


def test_default_is_utc_and_labelled():
    assert format_timestamp(STAMP) == "28 Jan 2026, 15:05 UTC"


def test_converts_to_the_viewers_zone():
    assert format_timestamp(STAMP, "America/New_York") == "28 Jan 2026, 10:05 EST"


def test_conversion_can_change_the_day():
    assert format_timestamp("2026-01-28T23:30:00Z", "Asia/Tokyo") == "29 Jan 2026, 08:30 JST"


def test_spanish_month_names():
    assert format_timestamp("2026-10-03T08:00:00+00:00", lang="es") == "3 oct 2026, 08:00 UTC"


def test_without_year():
    assert format_timestamp(STAMP, with_year=False) == "28 Jan, 15:05 UTC"


def test_naive_timestamps_are_treated_as_utc():
    assert format_timestamp("2026-01-28T15:05:09") == "28 Jan 2026, 15:05 UTC"


@pytest.mark.parametrize("zone", ["Mars/Olympus", "", None, "../../etc/passwd", "x" * 500])
def test_unknown_zone_falls_back_to_utc(zone):
    assert format_timestamp(STAMP, zone) == "28 Jan 2026, 15:05 UTC"
    assert resolve_timezone(zone).utcoffset(None).total_seconds() == 0


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_value_shows_a_dash(value):
    assert format_timestamp(value) == "—"


@pytest.mark.parametrize("value", ["yesterday", "2026-99-99", 12345, ["x"]])
def test_unreadable_value_is_shown_as_text_not_a_crash(value):
    assert format_timestamp(value) == str(value)
    assert parse_timestamp(value) is None


def test_unknown_language_falls_back_to_english():
    assert format_timestamp(STAMP, lang="fr").startswith("28 Jan")


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-01-01T10:00:00+00:00", "2026-01-01T10:00:42+00:00", "42 s"),
        ("2026-01-01T10:00:00+00:00", "2026-01-01T10:02:05+00:00", "2 min 05 s"),
        ("2026-01-01T10:00:00+00:00", "2026-01-01T11:03:00+00:00", "1 h 03 min"),
        ("2026-01-01T10:00:00+00:00", "2026-01-01T09:00:00+00:00", ""),  # clock went back
        (None, "2026-01-01T10:00:00+00:00", ""),
        ("2026-01-01T10:00:00+00:00", "garbage", ""),
    ],
)
def test_duration(start, end, expected):
    assert format_duration(start, end) == expected


def test_run_time_prefers_start_over_queue_time():
    assert run_time({"started_at": "S", "created_at": "C"}) == "S"
    assert run_time({"started_at": None, "created_at": "C"}) == "C"
    assert run_time({}) is None
