"""Plotly chart for power profiles in session state."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


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
