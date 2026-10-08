"""Injectable clock. Everything is stored in UTC; the business day is Asia/Dhaka."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DHAKA = ZoneInfo("Asia/Dhaka")

_now_fn: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731


def now() -> datetime:
    """Current time, timezone-aware UTC."""
    return _now_fn()


def set_now(fn: Callable[[], datetime]) -> None:
    global _now_fn
    _now_fn = fn


def reset() -> None:
    set_now(lambda: datetime.now(UTC))


@contextmanager
def frozen(at: datetime) -> Iterator[list[datetime]]:
    """Freeze time in tests. Yields a 1-element list; assign [0] to move time."""
    holder = [at.astimezone(UTC)]
    previous = _now_fn
    set_now(lambda: holder[0])
    try:
        yield holder
    finally:
        set_now(previous)


def local_now() -> datetime:
    return now().astimezone(DHAKA)


def today() -> date:
    """Business date in Dhaka."""
    return local_now().date()


def local_dt(d: date, t: time) -> datetime:
    """A Dhaka wall-clock date+time as an aware datetime."""
    return datetime.combine(d, t, tzinfo=DHAKA)


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start = local_dt(d, time(0, 0)).astimezone(UTC)
    return start, start + timedelta(days=1)


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(DHAKA)
