"""PV profile UI section."""

from __future__ import annotations

from io import BytesIO

import streamlit as st

from asimplex.streamlit_app.load_profile_section import (
    apply_profile_to_power_profiles,
    render_description_table,
)
from asimplex.tools.csv_tool import csv_reader_format


def render_pv_profile_section() -> None:
    with st.sidebar.expander("PV Power Profile", expanded=False):
        uploaded_file = st.file_uploader(
            "Upload PV CSV file",
            type=["csv"],
            accept_multiple_files=False,
            key="pv_profile_upload",
        )

        if uploaded_file is not None:
            try:
                csv_bytes = BytesIO(uploaded_file.getvalue())
                result = csv_reader_format(csv_bytes=csv_bytes)
                st.session_state["pv_profile_series"] = result.get("time_series_list")
                st.session_state["pv_profile_description"] = result.get("description")
                st.session_state["pv_profile_filename"] = uploaded_file.name
                if isinstance(result.get("description"), dict):
                    apply_profile_to_power_profiles("pv", result.get("time_series_list", []))
            except Exception as exc:  # pragma: no cover - UI defensive branch
                st.session_state["pv_profile_series"] = [0]
                st.session_state["pv_profile_description"] = f"Failed to parse PV file: {exc}"
                st.session_state["pv_profile_filename"] = uploaded_file.name

        st.markdown("**Map**")
        st.info("Map section placeholder. We will wire interactive coordinates next.")

        description = st.session_state.get("pv_profile_description")
        if description is not None:
            render_description_table(description)
