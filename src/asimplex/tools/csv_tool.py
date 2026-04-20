"""CSV parsing helpers for robust time-series extraction."""

from __future__ import annotations

from io import BytesIO
from itertools import product
from typing import BinaryIO

import pandas as pd

BASE_INDEX_15MIN = pd.date_range("2023-01-01", freq="15 min", periods=35040)
BAD_DATA_MESSAGE = """
No valid full-year series found for supplied parsing options. 

CSV file should be in columns, having a whole year of data. 
Valid number of rows (exclude header) 8760, 35040, 8784, 35136.

"""

def normalize_series_to_15min_2023(values: list[object]) -> pd.Series | None:
    """Normalize hourly or 15-min yearly series to a 2023 15-minute index."""
    numeric_series = pd.to_numeric(pd.Series(values), errors="coerce")
    n_rows = len(numeric_series)

    if n_rows == 35040:
        normalized = numeric_series.reset_index(drop=True)
    elif n_rows == 8760:
        normalized = numeric_series.repeat(4).reset_index(drop=True)
    elif n_rows == 35136:
        leap_index_15 = pd.date_range("2024-01-01", freq="15 min", periods=35136)
        leap_series_15 = pd.Series(numeric_series.values, index=leap_index_15)
        normalized = leap_series_15[~((leap_series_15.index.month == 2) & (leap_series_15.index.day == 29))]
        normalized = normalized.reset_index(drop=True)
    elif n_rows == 8784:
        leap_index_h = pd.date_range("2024-01-01", freq="h", periods=8784)
        leap_series_h = pd.Series(numeric_series.values, index=leap_index_h)
        no_leap_h = leap_series_h[~((leap_series_h.index.month == 2) & (leap_series_h.index.day == 29))]
        normalized = no_leap_h.repeat(4).reset_index(drop=True)
    else:
        return None

    if len(normalized) != len(BASE_INDEX_15MIN):
        return None
    return pd.Series(normalized.values, index=BASE_INDEX_15MIN)


def csv_reader_format(
    csv_bytes: BinaryIO | BytesIO,
) -> dict:
    """
    Read and return a validated yearly time series with statistics.

    This function loops through a fixed set of parsing options and returns the
    first valid parse that produces a full-year profile.
    """
    # The parser intentionally stays constrained to a known-good option set.
    sep_options = [",", ";", "\t"]
    decimal_options = [",", "."]
    thousands_options = [None, ",", ".", "_"]
    header_options = [0, None]
    col_options = [-1]
    skiprows_options = [0, 1, 2]

    parse_errors: list[str] = []

    for sep_opt, decimal_opt, thousands_opt, header_opt, col_opt, skiprows_opt in product(
        sep_options,
        decimal_options,
        thousands_options,
        header_options,
        col_options,
        skiprows_options,
    ):
        try:
            csv_bytes.seek(0)
            df = pd.read_csv(
                csv_bytes,
                sep=sep_opt,
                decimal=decimal_opt,
                thousands=thousands_opt,
                header=header_opt,
                skiprows=skiprows_opt
            )   
            series = df.iloc[:, col_opt]
        except Exception as exc:  # pragma: no cover - defensive parse fallback
            parse_errors.append(
                f"Failed for sep={sep_opt}, decimal={decimal_opt}, "
                f"thousands={thousands_opt}, header={header_opt}, col={col_opt}: {exc}"
            )
            continue

        if len(series) not in [8760, 8760 * 4, 8784, 8784 * 4]:
            parse_errors.append(
                f"Incomplete data for sep={sep_opt}, decimal={decimal_opt}, "
                f"thousands={thousands_opt}, header={header_opt}, col={col_opt}"
            )
            continue

        series_numeric = pd.to_numeric(series, errors="coerce")
        if series_numeric.isna().all():
            parse_errors.append(
                f"Non-numeric series for sep={sep_opt}, decimal={decimal_opt}, "
                f"thousands={thousands_opt}, header={header_opt}, col={col_opt}"
            )
            continue

        diff_values = series_numeric.diff().dropna().unique()
        if len(diff_values) > 0 and float(diff_values[0]) == 1:
            parse_errors.append(
                f"Detected index-like column for sep={sep_opt}, decimal={decimal_opt}, "
                f"thousands={thousands_opt}, header={header_opt}, col={col_opt}"
            )
            continue

        if len(series_numeric) in [8760, 8784]:
            freq = "h"
            hour_frac = 1
        else:
            freq = "15 min"
            hour_frac = 0.25

        series_numeric.index = pd.date_range("2023-01-01", freq=freq, periods=len(series_numeric))
        daily = series_numeric.resample("D").sum() * hour_frac

        stats_dict = {
            "highest_energy_per_day_kWh": float(daily.max()),
            "lowest_energy_per_day_kWh": float(daily.min()),
            "average_energy_per_day_kWh": float(daily.mean()),
            "peak_power_kW": float(series_numeric.max()),
            "lowest_power_kW": float(series_numeric.min()),
            "rows_of_data_N": len(series_numeric),
        }
        format_params = {
            "sep": sep_opt,
            "decimal": decimal_opt,
            "thousands_sep": thousands_opt,
            "header": header_opt,
            "col_number": col_opt,
        }

        return {
            "time_series_list": series_numeric.tolist(), 
            "description": stats_dict,
            'format_params': format_params
            }

    return {
        "time_series_list": [0],
        "description": BAD_DATA_MESSAGE,
        "parse_attempts": parse_errors,
    }
