"""Shared formatting helpers for display tables."""

from __future__ import annotations

from numbers import Real


def format_metric_name(metric_key: str) -> str:
    parts = metric_key.split("_")
    if not parts:
        return metric_key

    unit_candidates = {"kW", "kWh", "MW", "MWh", "W", "Wh", "N", "H"}
    unit = None
    last_part = parts[-1]
    if last_part in unit_candidates:
        unit = last_part
        parts = parts[:-1]

    readable_metric = " ".join(parts)
    if unit:
        return f"{readable_metric} ({unit})"
    return readable_metric


def format_metric_value(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        precision = 2 if abs(float(value)) > 1 else 5
        return round(float(value), precision)
    return value
