from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def wall_duration_ms(start: datetime, end: datetime) -> float:
    return (ensure_utc(end) - ensure_utc(start)).total_seconds() * 1000.0


def format_duration_ms(ms: float | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f} ms"
    if ms < 60_000:
        return f"{ms / 1000:.2f} s"
    minutes = int(ms // 60_000)
    seconds = (ms % 60_000) / 1000.0
    return f"{minutes}m {seconds:.1f}s"
