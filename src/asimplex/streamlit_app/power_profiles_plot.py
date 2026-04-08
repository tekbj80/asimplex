"""Plotly chart for power profiles in session state."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def render_power_profiles_plot() -> None:
    st.subheader("Power Profiles")
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        st.info("Upload a load profile or PV profile to visualize time series.")
        return

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
                line={"color": "orange", "width": 1.5},
            )
        )

    fig.update_layout(
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        legend_title="Profiles",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
