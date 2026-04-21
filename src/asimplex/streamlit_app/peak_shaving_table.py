"""Peak shaving result table section."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from asimplex.constants import HOUR_FRAC, TARIFF_THRESHOLD
from asimplex.streamlit_app.profile_columns import ProfileColumn
from simuplex.application_support_functions.peak_shaving import (
    determine_battery_discharge,
    determine_capacity_needed_for_peak_shaving,
)

ENERGY_COLOR = "#D4A017"  # soft gold
PEAK_POWER_COLOR = "#5B8FD9"  # muted blue
DURATION_COLOR = "#4C9085"  # muted teal


def _to_float(value: float) -> float:
    return float(round(float(value), 2))


def _series_quantiles_summary(series: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "p50": _to_float(clean.quantile(0.50)),
        "p95": _to_float(clean.quantile(0.95)),
        "max": _to_float(clean.max()),
    }


def _normalized_bucket_counts(series: pd.Series, unit: str) -> dict[str, int]:
    fraction_edges = [0.0, 0.1, 0.3, 0.6, 0.9, 1.0]
    bins = [0.0, 0.1, 0.3, 0.6, 0.9, 1.0]

    def _format_range_labels(max_value: float) -> list[str]:
        return [
            f"{fraction_edges[i] * max_value:.0f}-{fraction_edges[i + 1] * max_value:.0f} {unit}"
            for i in range(len(fraction_edges) - 1)
        ]

    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        labels = _format_range_labels(0.0)
        return {label: 0 for label in labels}

    max_value = float(clean.max())
    labels = _format_range_labels(max_value)
    if max_value <= 0:
        return {label: (int(len(clean)) if idx == 0 else 0) for idx, label in enumerate(labels)}

    normalized = (clean / max_value).clip(lower=0.0, upper=1.0)
    bucketed = pd.cut(
        normalized,
        bins=bins,
        labels=labels,
        include_lowest=True,
        right=False,
        ordered=False,
    )
    counts = bucketed.value_counts(sort=False)
    return {label: int(counts.get(label, 0)) for label in labels}


def _build_peak_shaving_json(
    *,
    discharge_df: pd.DataFrame,
    power_limit_kw: float,
    current_fhe_h: float | None,
) -> dict:
    energy = discharge_df["energy"]
    peak_power = discharge_df["peak_power"]
    duration_h = discharge_df["duration_hours"]

    return {
        "application_type": "peak_shaving",
        "analysis_period": "2023-01-01 to 2023-12-31",
        "timestep_minutes": int(HOUR_FRAC * 60),
        "current_full_hour_equivalent_h": _to_float(current_fhe_h or 0.0),
        "target_full_hour_equivalent_h": int(TARIFF_THRESHOLD),
        "required_grid_limit_kw": _to_float(power_limit_kw),
        "event_summary": {
            "number_of_events": int(len(discharge_df)),
            "annual_discharge_energy_kwh": _to_float(pd.to_numeric(energy, errors="coerce").sum()),
            "event_energy_kwh": _series_quantiles_summary(energy),
            "peak_power_kw": _series_quantiles_summary(peak_power),
            "duration_h": _series_quantiles_summary(duration_h),
        },
        "event_distribution": {
            "energy_kwh_buckets": _normalized_bucket_counts(energy, "kWh"),
            "peak_power_kw_buckets": _normalized_bucket_counts(peak_power, "kW"),
            "duration_h_buckets": _normalized_bucket_counts(duration_h, "h"),
        },
    }


def recompute_peak_shaving_capacity_table() -> pd.DataFrame:
    profiles = st.session_state.get("power_profiles")
    if not isinstance(profiles, pd.DataFrame) or profiles.empty:
        df = pd.DataFrame()
        st.session_state["peak_shaving_capacity_table"] = df
        return df
    if ProfileColumn.SITE_LOAD.column_name not in profiles.columns:
        df = pd.DataFrame()
        st.session_state["peak_shaving_capacity_table"] = df
        return df

    load_series = pd.to_numeric(profiles[ProfileColumn.SITE_LOAD.column_name], errors="coerce").dropna()
    if load_series.empty:
        df = pd.DataFrame()
        st.session_state["peak_shaving_capacity_table"] = df
        return df

    load_median = float(load_series.median())
    load_max = float(load_series.max())
    start_limit = int(np.floor(load_median))
    end_limit = int(np.ceil(load_max))
    if end_limit < start_limit:
        end_limit = start_limit

    load_profile_df = pd.DataFrame({"load": load_series}, index=load_series.index)
    rows: list[dict[str, float]] = []
    for grid_limit in range(start_limit, end_limit + 1):
        capacity_kwh, power_kw = determine_capacity_needed_for_peak_shaving(
            grid_limit=float(grid_limit),
            load_profile=load_profile_df,
            load_col="load",
        )
        rows.append(
            {
                "grid_limit_kw": float(grid_limit),
                "capacity_kwh": float(capacity_kwh),
                "power_kw": float(power_kw),
            }
        )

    capacity_df = pd.DataFrame(rows)
    biggest_cap = st.session_state.get("battery_with_biggest_capacity", {})
    biggest_power = st.session_state.get("battery_with_biggest_power", {})
    if isinstance(biggest_cap, dict) and isinstance(biggest_power, dict):
        cap_a = biggest_cap.get("capacity")
        cap_b = biggest_power.get("capacity")
        try:
            smaller_cap = min(float(cap_a), float(cap_b))
            capacity_df = capacity_df.loc[capacity_df["capacity_kwh"] <= smaller_cap].copy()
        except (TypeError, ValueError):
            pass
    st.session_state["peak_shaving_capacity_table"] = capacity_df
    return capacity_df


def _build_peak_shaving_capacity_summary(capacity_df: pd.DataFrame) -> dict[str, object]:
    if not isinstance(capacity_df, pd.DataFrame) or capacity_df.empty:
        return {
            "limits": {
                "grid_limit_min_kw": None,
                "grid_limit_max_kw": None,
                "rows_total": 0,
            },
            "battery_caps": {
                "largest_capacity_kwh": None,
                "largest_power_battery_capacity_kwh": None,
                "smaller_cap_kwh": None,
            },
            "feasibility": {
                "feasible_rows_count": 0,
                "first_feasible_grid_limit_kw": None,
            },
            "anchor_candidates": [],
        }

    largest_capacity = None
    largest_power_battery_capacity = None
    smaller_cap = None
    biggest_cap = st.session_state.get("battery_with_biggest_capacity", {})
    biggest_power = st.session_state.get("battery_with_biggest_power", {})
    try:
        largest_capacity = float((biggest_cap or {}).get("capacity"))
    except (TypeError, ValueError):
        largest_capacity = None
    try:
        largest_power_battery_capacity = float((biggest_power or {}).get("capacity"))
    except (TypeError, ValueError):
        largest_power_battery_capacity = None
    if largest_capacity is not None and largest_power_battery_capacity is not None:
        smaller_cap = min(largest_capacity, largest_power_battery_capacity)

    df = capacity_df.copy()
    if smaller_cap is not None:
        df["capacity_feasible"] = pd.to_numeric(df["capacity_kwh"], errors="coerce") <= float(smaller_cap)
    else:
        df["capacity_feasible"] = True
    feasible_df = df.loc[df["capacity_feasible"]].copy()

    anchor_df = feasible_df if not feasible_df.empty else df
    anchor_candidates: list[dict[str, object]] = []
    if not anchor_df.empty:
        index_candidates = {0, len(anchor_df) // 2, len(anchor_df) - 1}
        target_grid_limit = float(anchor_df["grid_limit_kw"].median())
        nearest_idx = (anchor_df["grid_limit_kw"] - target_grid_limit).abs().idxmin()
        index_candidates.add(int(anchor_df.index.get_loc(nearest_idx)))

        for idx in sorted(index_candidates):
            if idx < 0 or idx >= len(anchor_df):
                continue
            row = anchor_df.iloc[idx]
            anchor_candidates.append(
                {
                    "grid_limit_kw": float(row["grid_limit_kw"]),
                    "required_capacity_kwh": float(row["capacity_kwh"]),
                    "required_power_kw": float(row["power_kw"]),
                    "capacity_feasible": bool(row["capacity_feasible"]),
                }
            )

        deduped: list[dict[str, object]] = []
        seen_keys: set[tuple[float, float, float, bool]] = set()
        for item in anchor_candidates:
            key = (
                float(item["grid_limit_kw"]),
                float(item["required_capacity_kwh"]),
                float(item["required_power_kw"]),
                bool(item["capacity_feasible"]),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)
        anchor_candidates = deduped[:5]

    first_feasible = None
    if not feasible_df.empty:
        first_feasible = float(feasible_df["grid_limit_kw"].iloc[0])

    return {
        "limits": {
            "grid_limit_min_kw": float(df["grid_limit_kw"].min()),
            "grid_limit_max_kw": float(df["grid_limit_kw"].max()),
            "rows_total": int(len(df)),
        },
        "battery_caps": {
            "largest_capacity_kwh": largest_capacity,
            "largest_power_battery_capacity_kwh": largest_power_battery_capacity,
            "smaller_cap_kwh": smaller_cap,
        },
        "feasibility": {
            "feasible_rows_count": int(len(feasible_df)),
            "first_feasible_grid_limit_kw": first_feasible,
        },
        "anchor_candidates": anchor_candidates,
    }


def render_peak_shaving_table() -> None:
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        return

    with st.expander("Peak Shaving to Achieve 2500 Full Usage Hours", expanded=True):
        required_cols = {
            ProfileColumn.SITE_LOAD.column_name,
            ProfileColumn.PV_PRODUCTION.column_name,
            ProfileColumn.GRID_IMPORT.column_name,
        }
        if not required_cols.issubset(set(profiles.columns)):
            st.info("Load and PV profiles are both required to compute battery discharge results.")
            return

        capacity_df = st.session_state.get("peak_shaving_capacity_table")
        if not isinstance(capacity_df, pd.DataFrame):
            capacity_df = recompute_peak_shaving_capacity_table()
        if isinstance(capacity_df, pd.DataFrame) and not capacity_df.empty:
            st.markdown("**Capacity needed for peak shaving (filtered by largest available batteries)**")
            st.dataframe(capacity_df.round(3), width="stretch", hide_index=True)
        st.session_state["peak_shaving_capacity_summary_json"] = _build_peak_shaving_capacity_summary(capacity_df)
        with st.expander("Peak shaving capacity summary JSON (for LLM)", expanded=False):
            st.code(
                json.dumps(st.session_state.get("peak_shaving_capacity_summary_json", {}), indent=2),
                language="json",
            )

        load_peak = float(profiles[ProfileColumn.SITE_LOAD.column_name].max())
        if load_peak <= 0:
            st.warning("Load peak is zero. Unable to compute a valid power limit.")
            return

        power_limit = profiles[ProfileColumn.GRID_IMPORT.column_name].mul(HOUR_FRAC).sum() / TARIFF_THRESHOLD
        st.caption(f"Tariff threshold: {TARIFF_THRESHOLD:.0f} | Computed power limit: {power_limit:.2f} kW")

        try:
            battery_input = pd.DataFrame(
                {ProfileColumn.GRID_IMPORT.column_name: profiles[ProfileColumn.GRID_IMPORT.column_name]},
                index=profiles.index,
            )
            discharge_df = determine_battery_discharge(
                load_profile=battery_input,
                power_limit=float(power_limit),
                col=ProfileColumn.GRID_IMPORT.column_name,
            )
            st.session_state["battery_discharge_results"] = discharge_df
            if isinstance(discharge_df, pd.DataFrame) and not discharge_df.empty:
                discharge_df = discharge_df.copy()
                discharge_df["energy"] = pd.to_numeric(discharge_df.get("energy"), errors="coerce")
                discharge_df["peak_power"] = pd.to_numeric(discharge_df.get("peak_power"), errors="coerce")

                duration_series = discharge_df.get("duration")
                if duration_series is not None:
                    if pd.api.types.is_timedelta64_dtype(duration_series):
                        duration_hours = duration_series.dt.total_seconds() / 3600.0
                    else:
                        duration_hours = pd.to_timedelta(duration_series, errors="coerce").dt.total_seconds() / 3600.0
                    discharge_df["duration_hours"] = duration_hours
                else:
                    discharge_df["duration_hours"] = pd.Series(index=discharge_df.index, dtype=float)

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(
                    go.Scatter(
                        x=discharge_df.index,
                        y=discharge_df["energy"],
                        mode="markers",
                        name="energy (kWh)",
                        marker={"color": ENERGY_COLOR, "size": 8, "symbol": "circle"},
                        hovertemplate="time=%{x}<br>energy=%{y:.2f} kWh<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=discharge_df.index,
                        y=discharge_df["peak_power"],
                        mode="markers",
                        name="peak_power (kW)",
                        marker={"color": PEAK_POWER_COLOR, "size": 8, "symbol": "circle"},
                        hovertemplate="time=%{x}<br>peak_power=%{y:.2f} kW<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=discharge_df.index,
                        y=discharge_df["duration_hours"],
                        mode="markers",
                        name="duration (h)",
                        marker={"color": DURATION_COLOR, "size": 8, "symbol": "circle"},
                        hovertemplate="time=%{x}<br>duration=%{y:.2f} h<extra></extra>",
                    ),
                    secondary_y=True,
                )

                fig.update_layout(
                    margin={"l": 10, "r": 10, "t": 30, "b": 10},
                    template="plotly_white",
                    legend_title="Discharge metrics",
                )
                fig.update_yaxes(title_text="Energy / Peak Power", secondary_y=False)
                fig.update_yaxes(title_text="Duration (hours)", secondary_y=True, showgrid=False)
                st.plotly_chart(fig, width="stretch")

                # Keep a compact table view under the chart.
                st.dataframe(discharge_df.describe(), width="stretch", height=160)

                summary_json = _build_peak_shaving_json(
                    discharge_df=discharge_df,
                    power_limit_kw=float(power_limit),
                    current_fhe_h=(
                        st.session_state.get("usage_hour_equivalent", {}).get("value")
                        if isinstance(st.session_state.get("usage_hour_equivalent"), dict)
                        else st.session_state.get("usage_hour_equivalent")
                    ),
                )
                st.session_state["peak_shaving_json"] = summary_json
                with st.expander("Peak shaving JSON (Summarized Data to LLM)", expanded=False):
                    st.markdown("**Peak shaving JSON output**")
                    st.code(json.dumps(summary_json, indent=2), language="json")
            else:
                st.info("No discharge events found for the current power limit.")
        except Exception as exc:
            st.error(f"Battery discharge calculation failed: {exc}")
