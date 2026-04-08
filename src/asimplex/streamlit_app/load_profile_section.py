"""Sidebar and load-profile UI section."""

from __future__ import annotations

from io import BytesIO
from numbers import Real

import pandas as pd
import streamlit as st

from asimplex.tools.csv_tool import csv_reader_format


def init_session_state() -> None:
    st.session_state.setdefault("load_profile_series", None)
    st.session_state.setdefault("load_profile_description", None)
    st.session_state.setdefault("load_profile_filename", None)


def _format_metric_name(metric_key: str) -> str:
    parts = metric_key.split("_")
    if not parts:
        return metric_key

    unit_candidates = {"kW", "kWh", "Mw", "Mwh", "W", "Wh", "N"}
    unit = None
    last_part = parts[-1]
    if last_part in unit_candidates:
        unit = last_part
        parts = parts[:-1]

    readable_metric = " ".join(parts)
    if unit:
        return f"{readable_metric} ({unit})"
    return readable_metric


def _format_metric_value(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        precision = 2 if abs(float(value)) > 1 else 5
        return round(float(value), precision)
    return value


def _render_description_table(description: object) -> None:
    st.markdown("**Description**")
    if isinstance(description, dict):
        metrics = [_format_metric_name(str(k)) for k in description.keys()]
        values = [_format_metric_value(v) for v in description.values()]
        table_df = pd.DataFrame({"metric": metrics, "value": values})
        st.dataframe(
            table_df,
            hide_index=True,
            use_container_width=True,
        )
        return

    fallback_df = pd.DataFrame({"metric": ["description"], "value": [description]})
    st.dataframe(
        fallback_df,
        hide_index=True,
        use_container_width=True,
    )


def render_sidebar() -> None:
    st.sidebar.title("asimplex")
    st.sidebar.caption("Navigation")
    st.sidebar.button("New chat", use_container_width=True, disabled=True)
    st.sidebar.divider()

    with st.sidebar.expander("Load profile", expanded=True):
        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            accept_multiple_files=False,
        )

        if uploaded_file is not None:
            try:
                csv_bytes = BytesIO(uploaded_file.getvalue())
                result = csv_reader_format(csv_bytes=csv_bytes)
                st.session_state["load_profile_series"] = result.get("time_series_list")
                st.session_state["load_profile_description"] = result.get("description")
                st.session_state["load_profile_filename"] = uploaded_file.name
            except Exception as exc:  # pragma: no cover - UI defensive branch
                st.session_state["load_profile_series"] = [0]
                st.session_state["load_profile_description"] = f"Failed to parse file: {exc}"
                st.session_state["load_profile_filename"] = uploaded_file.name

        description = st.session_state.get("load_profile_description")
        if description is not None:
            _render_description_table(description)
