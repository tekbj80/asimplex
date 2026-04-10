"""Shared calculation utilities."""

from __future__ import annotations

import datetime as dt

import pandas as pd


def calculate_full_hour_equivalent(load_series: pd.Series) -> float:
    """
    Calculate full-hour-equivalent (FHE) from a power time series.

    FHE = (sum(power) * hour_frac) / max(power)
    where hour_frac is derived from the time-step in the index.
    """
    numeric_series = pd.to_numeric(load_series, errors="coerce").dropna()
    if numeric_series.empty:
        return 0.0

    max_value = float(numeric_series.max())
    if max_value <= 0:
        return 0.0

    if len(numeric_series.index) >= 2:
        hour_frac = (numeric_series.index[1] - numeric_series.index[0]) / dt.timedelta(hours=1)
    else:
        hour_frac = 1.0

    return float((numeric_series.sum() * hour_frac) / max_value)


def summarize_load_profile(load_series: pd.Series) -> dict[str, float]:
    """Return summary metrics for a power profile series."""
    numeric_series = pd.to_numeric(load_series, errors="coerce").dropna()
    if numeric_series.empty:
        return {
            "annual_energy_consumption_kWh": 0.0,
            "peak_power_kW": 0.0,
            "base_power_kW": 0.0,
            "average_power_kW": 0.0,
            "50th_quantile_power_kW": 0.0,
            "25th_quantile_power_kW": 0.0,
            "full_hour_equivalent_H": 0.0,
        }

    if len(numeric_series.index) >= 2:
        hour_frac = (numeric_series.index[1] - numeric_series.index[0]) / dt.timedelta(hours=1)
    else:
        hour_frac = 1.0

    return {
        "annual_energy_consumption_kWh": float(numeric_series.sum() * hour_frac),
        "peak_power_kW": float(numeric_series.max()),
        "base_power_kW": float(numeric_series.min()),
        "average_power_kW": float(numeric_series.mean()),
        "50th_quantile_power_kW": float(numeric_series.quantile(0.5)),
        "25th_quantile_power_kW": float(numeric_series.quantile(0.25)),
        "full_hour_equivalent_H": float(calculate_full_hour_equivalent(numeric_series)),
    }
