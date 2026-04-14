"""Shared calculation utilities."""

from __future__ import annotations

import datetime as dt

import pandas as pd


def _hour_frac_from_series(load_series: pd.Series) -> float:
    return float((load_series.index[1] - load_series.index[0]) / dt.timedelta(hours=1))


def calculate_full_hour_equivalent(load_series: pd.Series) -> float:
    """
    Calculate full-hour-equivalent (FHE) from a power time series.

    FHE = (sum(power) * hour_frac) / max(power)
    where hour_frac is derived from the time-step in the index.
    """
    hour_frac = _hour_frac_from_series(load_series)
    return float((load_series.sum() * hour_frac) / load_series.max())


def summarize_load_profile(load_series: pd.Series) -> dict[str, float]:
    """Return power and daily-energy summary metrics for a profile series."""
    hour_frac = _hour_frac_from_series(load_series)
    daily_energy_series = load_series.resample("D").sum() * hour_frac

    return {
        "annual_energy_consumption_kWh": float(load_series.sum() * hour_frac),
        "peak_power_kW": float(load_series.max()),
        "minimum_power_kW": float(load_series.min()),
        "average_power_kW": float(load_series.mean()),
        "power_p50_kW": float(load_series.quantile(0.5)),
        "power_p25_kW": float(load_series.quantile(0.25)),
        "full_hour_equivalent_H": float(calculate_full_hour_equivalent(load_series)),
        "daily_energy_p25_kWh": float(daily_energy_series.quantile(0.25)),
        "daily_energy_p50_kWh": float(daily_energy_series.quantile(0.5)),
        "average_daily_energy_kWh": float(daily_energy_series.mean()),
    }

