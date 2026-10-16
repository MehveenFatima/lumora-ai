"""
Calendar-date helpers for target completion dates.

"Today" should be the learner's local date, not the server's: the web app sends it in the
X-Client-Date header (YYYY-MM-DD). It is accepted only if it is within one day of the UTC date
(every real time zone is), otherwise the UTC date is used.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Request

CLIENT_DATE_HEADER = "x-client-date"
DEFAULT_TARGET_DAYS = 30


def parse_date(value: Any) -> Optional[date]:
    """Accepts a date, a datetime or an ISO 'YYYY-MM-DD' string; returns None if it isn't one."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def client_today(request: Optional[Request] = None) -> date:
    utc_today = datetime.now(timezone.utc).date()
    if request is not None:
        sent = parse_date(request.headers.get(CLIENT_DATE_HEADER))
        if sent and abs((sent - utc_today).days) <= 1:
            return sent
    return utc_today


def default_target(today: date) -> date:
    return today + timedelta(days=DEFAULT_TARGET_DAYS)


def format_long(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"
