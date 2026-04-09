"""Peak shaving result table section."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from asimplex.constants import HOUR_FRAC, TARIFF_THRESHOLD
from simuplex.application_support_functions.peak_shaving import determine_battery_discharge


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
                plot_df = discharge_df.copy()
                plot_df["energy"] = pd.to_numeric(plot_df.get("energy"), errors="coerce")
                plot_df["peak_power"] = pd.to_numeric(plot_df.get("peak_power"), errors="coerce")

                duration_series = plot_df.get("duration")
                if duration_series is not None:
                    if pd.api.types.is_timedelta64_dtype(duration_series):
                        duration_hours = duration_series.dt.total_seconds() / 3600.0
                    else:
                        duration_hours = pd.to_timedelta(duration_series, errors="coerce").dt.total_seconds() / 3600.0
                    plot_df["duration_hours"] = duration_hours
                else:
                    plot_df["duration_hours"] = pd.Series(index=plot_df.index, dtype=float)

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(
                    go.Scatter(
                        x=plot_df.index,
                        y=plot_df["energy"],
                        mode="markers",
                        name="energy (kWh)",
                        marker={"color": "green", "size": 8, "symbol": "circle"},
                        hovertemplate="time=%{x}<br>energy=%{y:.2f} kWh<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=plot_df.index,
                        y=plot_df["peak_power"],
                        mode="markers",
                        name="peak_power (kW)",
                        marker={"color": "blue", "size": 8, "symbol": "square"},
                        hovertemplate="time=%{x}<br>peak_power=%{y:.2f} kW<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=plot_df.index,
                        y=plot_df["duration_hours"],
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
                st.dataframe(discharge_df, width="stretch", height=160)
            else:
                st.info("No discharge events found for the current power limit.")
        except Exception as exc:
            st.error(f"Battery discharge calculation failed: {exc}")
