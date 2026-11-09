"""Readable dates for runs and reports, free of Streamlit so it is unit-tested.

Runs store UTC ISO timestamps. People read them in their own time zone, so the
dashboard passes the viewer's IANA zone name; without one (or with an unknown
zone) the time is shown in UTC and labelled as such, never silently shifted.
"""

from datetime import datetime, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
}
MISSING = "—"


def parse_timestamp(value: Any) -> datetime | None:
    """An aware datetime from an ISO string; naive values are taken as UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def resolve_timezone(name: str | None) -> tzinfo:
    """The named IANA zone, or UTC when it is missing or unknown."""
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return timezone.utc


def format_timestamp(
    value: Any, tz_name: str | None = None, lang: str = "en", *, with_year: bool = True
) -> str:
    """e.g. ``28 Oct 2026, 10:00 UTC``; unreadable values are returned as text."""
    parsed = parse_timestamp(value)
    if parsed is None:
        blank = value is None or (isinstance(value, str) and not value.strip())
        return MISSING if blank else str(value)
    local = parsed.astimezone(resolve_timezone(tz_name))
    month = MONTHS.get(lang, MONTHS["en"])[local.month - 1]
    year = f" {local.year}" if with_year else ""
    return f"{local.day} {month}{year}, {local:%H:%M} {local.tzname() or 'UTC'}"


def format_duration(started: Any, finished: Any) -> str:
    """e.g. ``42 s`` or ``2 min 05 s``; empty when either time is unknown."""
    start, end = parse_timestamp(started), parse_timestamp(finished)
    if start is None or end is None:
        return ""
    seconds = int((end - start).total_seconds())
    if seconds < 0:
        return ""
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60:02d} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


def run_time(run: dict[str, Any]) -> Any:
    """When a test ran: when it started, else when it was queued."""
    return run.get("started_at") or run.get("created_at")
