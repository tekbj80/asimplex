"""Peak shaving result table section."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from asimplex.constants import HOUR_FRAC, TARIFF_THRESHOLD
from simuplex.application_support_functions.peak_shaving import determine_battery_discharge


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


def render_peak_shaving_table() -> None:
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        return

    with st.expander("Peak Shaving to Achieve 2500 Full Usage Hours", expanded=True):
        required_cols = {"load", "pv", "grid_power_draw"}
        if not required_cols.issubset(set(profiles.columns)):
            st.info("Load and PV profiles are both required to compute battery discharge results.")
            return

        load_peak = float(profiles["load"].max())
        if load_peak <= 0:
            st.warning("Load peak is zero. Unable to compute a valid power limit.")
            return

        power_limit = profiles["grid_power_draw"].mul(HOUR_FRAC).sum() / TARIFF_THRESHOLD
        st.caption(f"Tariff threshold: {TARIFF_THRESHOLD:.0f} | Computed power limit: {power_limit:.2f} kW")

        try:
            battery_input = pd.DataFrame({"grid_power_draw": profiles["grid_power_draw"]}, index=profiles.index)
            discharge_df = determine_battery_discharge(
                load_profile=battery_input,
                power_limit=float(power_limit),
                col="grid_power_draw",
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
                        marker={"color": "green", "size": 8, "symbol": "circle"},
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
                        marker={"color": "blue", "size": 8, "symbol": "square"},
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
                        marker={"color": "red", "size": 8, "symbol": "diamond"},
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
                    current_fhe_h=st.session_state.get("usage_hour_equivalent"),
                )
                st.session_state["peak_shaving_json"] = summary_json
                with st.expander("Peak shaving JSON (Summarized Data to LLM)", expanded=False):
                    st.markdown("**Peak shaving JSON output**")
                    st.code(json.dumps(summary_json, indent=2), language="json")
            else:
                st.info("No discharge events found for the current power limit.")
        except Exception as exc:
            st.error(f"Battery discharge calculation failed: {exc}")
