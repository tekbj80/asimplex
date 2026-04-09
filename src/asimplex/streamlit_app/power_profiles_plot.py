"""Plotly chart for power profiles in session state."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simuplex.application_support_functions.peak_shaving import determine_battery_discharge

HOUR_FRAC = 0.25
TARIFF_THRESHOLD = 2700.0


def render_power_profiles_plot() -> None:
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        st.info("Upload a load profile or PV profile to visualize time series.")
        return

    with st.expander("Power Profiles Plot", expanded=True):
        fig = go.Figure()
        if "load" in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles["load"],
                    mode="lines",
                    name="Load",
                    line={"color": "blue", "width": 1.5},
                )
            )
        if "pv" in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles["pv"],
                    mode="lines",
                    name="PV",
                    line={"color": "gold", "width": 1.5},
                )
            )
        if "excess_pv" in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles["excess_pv"],
                    mode="lines",
                    name="Excess PV",
                    line={"color": "green", "width": 1.5},
                )
            )
        if "grid_power_draw" in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles["grid_power_draw"],
                    mode="lines",
                    name="Grid Power Draw",
                    line={"color": "red", "width": 1.5},
                )
            )

        if "grid_power_draw" in profiles.columns:
            grid_draw_max = float(profiles["grid_power_draw"].max())
            fig.add_hline(
                y=grid_draw_max,
                line_color="red",
                line_dash="dot",
                line_width=1.5,
                annotation_text=f"grid_power_draw_max={grid_draw_max:.2f}",
                annotation_position="top right",
            )

        usage_hour_equivalent = st.session_state.get("usage_hour_equivalent")
        if usage_hour_equivalent is not None:
            fig.add_hline(
                y=float(usage_hour_equivalent),
                line_color="black",
                line_dash="dot",
                line_width=1.5,
                annotation_text=f"usage_hour_equivalent={float(usage_hour_equivalent):.2f}",
                annotation_position="top left",
            )

        fig.update_layout(
            margin={"l": 10, "r": 10, "t": 30, "b": 10},
            xaxis_title="Time",
            yaxis_title="Power (kW)",
            legend_title="Profiles",
            template="plotly_white",
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("Battery Discharge Results", expanded=True):
        required_cols = {"load", "pv", "grid_power_draw"}
        if not required_cols.issubset(set(profiles.columns)):
            st.info("Load and PV profiles are both required to compute battery discharge results.")
            return

        load_peak = float(profiles["load"].max())
        if load_peak <= 0:
            st.warning("Load peak is zero. Unable to compute a valid power limit.")
            return

        power_limit = profiles["grid_power_draw"].mul(HOUR_FRAC).sum() / TARIFF_THRESHOLD
        st.caption(f"Tariff threshold: {TARIFF_THRESHOLD:.0f} | Computed power limit: {power_limit:.4f}")

        try:
            battery_input = pd.DataFrame({"grid_power_draw": profiles["grid_power_draw"]}, index=profiles.index)
            discharge_df = determine_battery_discharge(
                load_profile=battery_input,
                power_limit=float(power_limit),
                col="grid_power_draw",
            )
            st.session_state["battery_discharge_results"] = discharge_df
            if isinstance(discharge_df, pd.DataFrame) and not discharge_df.empty:
                st.dataframe(discharge_df, width="stretch")
            else:
                st.info("No discharge events found for the current power limit.")
        except Exception as exc:
            st.error(f"Battery discharge calculation failed: {exc}")
