"""Plotly chart for power profiles in session state."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from asimplex.constants import HOUR_FRAC
from asimplex.streamlit_app.profile_columns import (
    description,
    profile_color,
    profile_label,
    ProfileColumn,
)
from asimplex.tools.calculations import summarize_load_profile
from asimplex.tools.formatting import format_metric_name, format_metric_value

LINE_PLOT_HEIGHT_PX = 500
RADIAL_PLOT_HEIGHT_PX = 400

DAILY_ENERGY_USAGE_DESCRIPTION = "<br>".join(
    f"**{profile_label[col]}**: {description[col]}"
    for col in (
        ProfileColumn.SITE_LOAD,
        ProfileColumn.PV_PRODUCTION,
        ProfileColumn.PV_SURPLUS,
        ProfileColumn.GRID_IMPORT,
    )
)

def _summary_display_formatter(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        precision = 2 if abs(float(value)) > 1 else 5
        return f"{float(value):,.{precision}f}"
    return value


def radial_season_plot(df: pd.DataFrame, title: str = "Radial Time Series") -> go.Figure:
    plot_columns = [
        col.column_name
        for col in (
            ProfileColumn.SITE_LOAD,
            ProfileColumn.PV_PRODUCTION,
            ProfileColumn.PV_SURPLUS,
            ProfileColumn.GRID_IMPORT,
        )
        if col.column_name in df.columns
    ]
    fig = go.Figure()
    if not plot_columns:
        fig.update_layout(title=title)
        return fig

    s = df[plot_columns].dropna().copy()
    if s.empty:
        fig.update_layout(title=title)
        return fig

    max_day = int(s.index.dayofyear.max())
    theta_deg = (s.index.dayofyear - 1) / max_day * 360.0
    date_labels = s.index.strftime("%b-%d")
    month_starts = pd.date_range("2023-01-01", "2023-12-01", freq="MS")
    month_tickvals = ((month_starts.dayofyear - 1) / 365.0 * 360.0).tolist()
    month_ticktext = [d.strftime("%b") for d in month_starts]

    for col in plot_columns:
        col_enum = ProfileColumn(col)
        fig.add_trace(
            go.Scatterpolar(
                r=s[col].values,
                theta=theta_deg,
                customdata=date_labels,
                mode="lines+markers",
                name=profile_label.get(col_enum, col),
                line={"color": profile_color.get(col_enum), "width": 1.2},
                hovertemplate="Date: %{customdata}<br>%{fullData.name}: %{r:,.2f} kWh<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        height=RADIAL_PLOT_HEIGHT_PX,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        polar=dict(
            angularaxis=dict(
                direction="clockwise",
                rotation=90,
                tickmode="array",
                tickvals=month_tickvals,
                ticktext=month_ticktext,
            )
        ),
        showlegend=True,
    )
    return fig


def render_power_profiles_plot() -> None:
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        st.info("Upload a load profile or PV profile to visualize time series.")
        return

    with st.expander("Power Profiles Plot", expanded=True):
        col_line_plot, col_radial_plot = st.columns([2, 1], gap="medium")
        fig = go.Figure()
        if ProfileColumn.SITE_LOAD.column_name in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles[ProfileColumn.SITE_LOAD.column_name],
                    mode="lines",
                    name=profile_label[ProfileColumn.SITE_LOAD],
                    line={"color": profile_color[ProfileColumn.SITE_LOAD], "width": 1.5},
                )
            )
        if ProfileColumn.PV_PRODUCTION.column_name in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles[ProfileColumn.PV_PRODUCTION.column_name],
                    mode="lines",
                    name=profile_label[ProfileColumn.PV_PRODUCTION],
                    line={"color": profile_color[ProfileColumn.PV_PRODUCTION], "width": 1.5},
                )
            )
        if ProfileColumn.PV_SURPLUS.column_name in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles[ProfileColumn.PV_SURPLUS.column_name],
                    mode="lines",
                    name=profile_label[ProfileColumn.PV_SURPLUS],
                    line={"color": profile_color[ProfileColumn.PV_SURPLUS], "width": 1.5},
                )
            )
        if ProfileColumn.GRID_IMPORT.column_name in profiles.columns:
            fig.add_trace(
                go.Scatter(
                    x=profiles.index,
                    y=profiles[ProfileColumn.GRID_IMPORT.column_name],
                    mode="lines",
                    name=profile_label[ProfileColumn.GRID_IMPORT],
                    line={"color": profile_color[ProfileColumn.GRID_IMPORT], "width": 1.5},
                )
            )

        if ProfileColumn.GRID_IMPORT.column_name in profiles.columns:
            grid_draw_max = float(profiles[ProfileColumn.GRID_IMPORT.column_name].max())
            fig.add_hline(
                y=grid_draw_max,
                line_color=profile_color[ProfileColumn.GRID_IMPORT],
                line_dash="dot",
                line_width=1.5,
                annotation_text=f"{ProfileColumn.GRID_IMPORT.column_name}_max={grid_draw_max:.2f}",
                annotation_position="top right",
            )

        usage_hour_equivalent = st.session_state.get("usage_hour_equivalent")
        usage_value = None
        usage_description = "load only"
        if isinstance(usage_hour_equivalent, dict):
            usage_value = usage_hour_equivalent.get("value")
            usage_description = str(usage_hour_equivalent.get("description", usage_description))
        else:
            usage_value = usage_hour_equivalent

        if usage_value is not None:
            fig.add_hline(
                y=float(usage_value),
                line_color="black",
                line_dash="dot",
                line_width=1.5,
                annotation_text=f"usage_hour_equivalent ({usage_description})={float(usage_value):.2f}",
                annotation_position="top left",
            )

        fig.update_layout(
            margin={"l": 10, "r": 10, "t": 30, "b": 10},
            xaxis_title="Time",
            yaxis_title="Power (kW)",
            legend_title="Profiles",
            template="plotly_white",
            height=LINE_PLOT_HEIGHT_PX,
        )
        with col_line_plot:
            st.plotly_chart(fig, width="stretch")
        with col_radial_plot:
            st.plotly_chart(radial_season_plot(profiles.resample("D").sum().mul(HOUR_FRAC), title="Daily Energy Usage"), width="stretch")
            st.markdown(
                f"<div style='font-size: 0.8em;'>{DAILY_ENERGY_USAGE_DESCRIPTION}</div>",
                unsafe_allow_html=True,
            )
            

        st.markdown("**Profile summary**")
        summary_columns = [
            ProfileColumn.SITE_LOAD.column_name,
            ProfileColumn.GRID_IMPORT.column_name,
            ProfileColumn.PV_SURPLUS.column_name,
        ]
        available_summary_columns = [col for col in summary_columns if col in profiles.columns]
        metric_map: dict[str, dict[str, float]] = {}
        llm_payload: dict[str, dict[str, object]] = {}
        if not available_summary_columns:
            st.dataframe(pd.DataFrame(columns=["metric"]), width="stretch", height=320)
        else:
            metric_map = {col: summarize_load_profile(profiles[col]) for col in available_summary_columns}
            llm_payload = {
                col: {
                    "description": description[ProfileColumn(col)],
                    "metrics": metric_map[col],
                }
                for col in available_summary_columns
            }
            raw_metrics = list(next(iter(metric_map.values())).keys())
            summary_df = pd.DataFrame({"metric": [format_metric_name(m) for m in raw_metrics]})
            for col in available_summary_columns:
                summary_df[col] = [format_metric_value(metric_map[col][metric]) for metric in raw_metrics]
            summary_styler = summary_df.style.format(
                {col: _summary_display_formatter for col in available_summary_columns}
            )
            st.dataframe(summary_styler, width="stretch", height=320, hide_index=True)

        with st.expander("Profile summary JSON to be sent to LLM", expanded=False):
            st.code(json.dumps(llm_payload, indent=2), language="json")



