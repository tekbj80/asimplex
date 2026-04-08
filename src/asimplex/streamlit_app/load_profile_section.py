"""Sidebar and load-profile UI section."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from asimplex.tools.csv_tool import csv_reader_format


def init_session_state() -> None:
    st.session_state.setdefault("load_profile_series", None)
    st.session_state.setdefault("load_profile_description", None)
    st.session_state.setdefault("load_profile_filename", None)


def _render_description_table(description: object) -> None:
    st.markdown("**Description**")
    if isinstance(description, dict):
        table_df = pd.DataFrame(
            {"metric": list(description.keys()), "value": list(description.values())}
        )
        st.table(table_df)
        return

    st.table(pd.DataFrame({"metric": ["description"], "value": [description]}))


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
