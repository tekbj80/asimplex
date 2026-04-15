"""Shared Streamlit session-state initialization."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.llm_usage import default_llm_usage
from asimplex.streamlit_app.simulation_plan_section import default_simulation_plan_params
from asimplex.tools.csv_tool import BASE_INDEX_15MIN


def init_session_state() -> None:
    st.session_state.setdefault("load_profile_series", None)
    st.session_state.setdefault("load_profile_description", None)
    st.session_state.setdefault("load_profile_filename", None)
    st.session_state.setdefault("load_profile_parse_attempts", None)
    st.session_state.setdefault("pv_profile_series", None)
    st.session_state.setdefault("pv_profile_description", None)
    st.session_state.setdefault("pv_profile_filename", None)
    st.session_state.setdefault("pv_profile_parse_attempts", None)
    st.session_state.setdefault("project_lat", 52.520000)
    st.session_state.setdefault("project_lon", 13.405000)
    st.session_state.setdefault("pv_system_already_exists", False)
    st.session_state.setdefault(
        "usage_hour_equivalent",
        {"value": None, "description": "load only"},
    )
    st.session_state.setdefault(
        "electrical_tariff",
        {
            "selected_voltage_level": None,
            "llm_extracted_tariff": None,
            "llm_response_debug_text": "",
        },
    )
    st.session_state.setdefault("llm_usage", default_llm_usage())
    st.session_state.setdefault("simulation_plan_params", default_simulation_plan_params())
    if "power_profiles" not in st.session_state:
        st.session_state["power_profiles"] = pd.DataFrame(index=BASE_INDEX_15MIN.copy())

