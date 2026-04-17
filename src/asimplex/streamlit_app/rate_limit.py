"""Session-scoped rate limiting helpers for Streamlit flows."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any


def _get_now(now_ts: float | None = None) -> float:
    return float(now_ts) if now_ts is not None else time.time()


def _parse_llm_usage_time(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None


def check_llm_usage_window_limit(
    session_state: dict[str, Any],
    *,
    action_label: str,
    max_requests: int,
    window_seconds: int,
    now_ts: float | None = None,
) -> tuple[bool, int]:
    """Check request window limit using `session_state['llm_usage']['rows']`."""
    if max_requests <= 0 or window_seconds <= 0:
        return True, 0

    now = _get_now(now_ts)
    cutoff = now - float(window_seconds)
    usage = session_state.get("llm_usage", {})
    rows = usage.get("rows", []) if isinstance(usage, dict) else []
    recent_timestamps: list[float] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("action", "")) != action_label:
            continue
        ts = _parse_llm_usage_time(row.get("time"))
        if ts is not None and ts >= cutoff:
            recent_timestamps.append(ts)

    if len(recent_timestamps) >= max_requests:
        oldest_recent_ts = min(recent_timestamps)
        retry_after = max(1, int(oldest_recent_ts + float(window_seconds) - now))
        return False, retry_after

    return True, 0


def check_tariff_cooldown_remaining(
    session_state: dict[str, Any],
    *,
    cooldown_seconds: int,
    now_ts: float | None = None,
) -> int:
    """Return remaining cooldown seconds for tariff extraction."""
    if cooldown_seconds <= 0:
        return 0
    now = _get_now(now_ts)
    last_ts = float(session_state.get("tariff_last_extract_attempt_ts", 0.0) or 0.0)
    elapsed = now - last_ts
    remaining = int(float(cooldown_seconds) - elapsed)
    return max(0, remaining)


def mark_tariff_extraction_attempt(session_state: dict[str, Any], *, now_ts: float | None = None) -> None:
    """Mark tariff extraction attempt timestamp for cooldown tracking."""
    session_state["tariff_last_extract_attempt_ts"] = _get_now(now_ts)
