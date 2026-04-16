"""Shared Streamlit session-state initialization."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.constants import (
    ASIMPLEX_AGENT_HISTORY_MAX_MESSAGES,
    ASIMPLEX_AGENT_HISTORY_MAX_TOKENS,
    ASIMPLEX_AGENT_HISTORY_MAX_TURNS,
    ASIMPLEX_AGENT_HISTORY_STRATEGY,
)
from asimplex.llm_usage import default_llm_usage
from asimplex.streamlit_app.simulation_plan_section import default_simulation_plan_params
from asimplex.tools.csv_tool import BASE_INDEX_15MIN


def init_session_state() -> None:
    st.session_state.setdefault("project_name", "")
    st.session_state.setdefault("session_ready", False)
    st.session_state.setdefault("show_new_project_input", False)
    st.session_state.setdefault("load_profile_series", None)
    st.session_state.setdefault("load_profile_description", None)
    st.session_state.setdefault("load_profile_filename", None)
    st.session_state.setdefault("load_profile_parse_attempts", None)
    st.session_state.setdefault("load_profile_reason_text", "")
    st.session_state.setdefault("load_profile_created_at", "")
    st.session_state.setdefault("load_profile_updated_at", "")
    st.session_state.setdefault("pv_profile_series", None)
    st.session_state.setdefault("pv_profile_description", None)
    st.session_state.setdefault("pv_profile_filename", None)
    st.session_state.setdefault("pv_profile_parse_attempts", None)
    st.session_state.setdefault("pv_profile_reason_text", "")
    st.session_state.setdefault("pv_profile_created_at", "")
    st.session_state.setdefault("pv_profile_updated_at", "")
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
            "source_filename": "",
            "loaded_from_session": False,
        },
    )
    st.session_state.setdefault("llm_usage", default_llm_usage())
    st.session_state.setdefault("agent_history_strategy", ASIMPLEX_AGENT_HISTORY_STRATEGY)
    st.session_state.setdefault("agent_history_max_messages", ASIMPLEX_AGENT_HISTORY_MAX_MESSAGES)
    st.session_state.setdefault("agent_history_max_turns", ASIMPLEX_AGENT_HISTORY_MAX_TURNS)
    st.session_state.setdefault("agent_history_max_tokens", ASIMPLEX_AGENT_HISTORY_MAX_TOKENS)
    st.session_state.setdefault("simulation_plan_params", default_simulation_plan_params())
    st.session_state.setdefault("base_case_benchmarks", None)
    st.session_state.setdefault("simulation_benchmark_context_json", {})
    st.session_state.setdefault("sim_version_note", "")
    st.session_state.setdefault("sim_version_selected", None)
    st.session_state.setdefault("sim_versions_cache", [])
    if "power_profiles" not in st.session_state:
        st.session_state["power_profiles"] = pd.DataFrame(index=BASE_INDEX_15MIN.copy())

