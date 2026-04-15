"""Sidebar container for app sections."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.persistence.session_store import (
    create_project,
    get_project_name,
    get_profile_snapshot,
    get_tariff_snapshot,
    init_db,
    list_project_session_ids,
    normalize_project_name_to_session_id,
    project_exists,
)
from asimplex.streamlit_app.electrical_tariff_section import (
    VOLTAGE_LEVEL_OPTIONS,
    render_electrical_tariff_section,
)
from asimplex.streamlit_app.load_profile_section import apply_profile_to_power_profiles, render_load_profile_section
from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.streamlit_app.pv_profile_section import render_pv_profile_section
from asimplex.streamlit_app.simulation_plan_section import update_simulation_plan_params
from asimplex.tools.csv_tool import BASE_INDEX_15MIN


def _hydrate_profiles_for_session(session_id: str) -> None:
    st.session_state["power_profiles"] = pd.DataFrame(index=BASE_INDEX_15MIN.copy())

    load_snapshot = get_profile_snapshot(session_id, "load")
    pv_snapshot = get_profile_snapshot(session_id, "pv")

    st.session_state["load_profile_series"] = None
    st.session_state["load_profile_description"] = None
    st.session_state["load_profile_filename"] = None
    st.session_state["load_profile_parse_attempts"] = None
    st.session_state["pv_profile_series"] = None
    st.session_state["pv_profile_description"] = None
    st.session_state["pv_profile_filename"] = None
    st.session_state["pv_profile_parse_attempts"] = None

    if isinstance(load_snapshot, dict):
        series = load_snapshot.get("series", [])
        st.session_state["load_profile_series"] = series
        st.session_state["load_profile_description"] = load_snapshot.get("description")
        st.session_state["load_profile_filename"] = load_snapshot.get("filename")
        st.session_state["load_profile_parse_attempts"] = load_snapshot.get("parse_attempts")
        if isinstance(series, list) and series:
            apply_profile_to_power_profiles(ProfileColumn.SITE_LOAD.column_name, series)

    if isinstance(pv_snapshot, dict):
        series = pv_snapshot.get("series", [])
        st.session_state["pv_profile_series"] = series
        st.session_state["pv_profile_description"] = pv_snapshot.get("description")
        st.session_state["pv_profile_filename"] = pv_snapshot.get("filename")
        st.session_state["pv_profile_parse_attempts"] = pv_snapshot.get("parse_attempts")
        metadata = pv_snapshot.get("metadata", {})
        if isinstance(metadata, dict) and str(metadata.get("source", "")) == "pvgis":
            if "project_lat" in metadata:
                st.session_state["project_lat"] = float(metadata["project_lat"])
            if "project_lon" in metadata:
                st.session_state["project_lon"] = float(metadata["project_lon"])
            if "peak_power_kwp" in metadata:
                st.session_state["pvgis_peak_kw"] = float(metadata["peak_power_kwp"])
            if "tilt_deg" in metadata:
                st.session_state["pvgis_tilt"] = float(metadata["tilt_deg"])
            if "azimuth_deg" in metadata:
                st.session_state["pvgis_azimuth"] = float(metadata["azimuth_deg"])
            if "loss_percent" in metadata:
                st.session_state["pvgis_loss"] = float(metadata["loss_percent"])
        if isinstance(series, list) and series:
            apply_profile_to_power_profiles(ProfileColumn.PV_PRODUCTION.column_name, series)

    tariff_snapshot = get_tariff_snapshot(session_id)
    if isinstance(tariff_snapshot, dict):
        selected_voltage_level = tariff_snapshot.get("selected_voltage_level", "")
        if selected_voltage_level not in VOLTAGE_LEVEL_OPTIONS:
            selected_voltage_level = VOLTAGE_LEVEL_OPTIONS[0]
        st.session_state["electrical_tariff"] = {
            "selected_voltage_level": selected_voltage_level,
            "llm_extracted_tariff": tariff_snapshot.get("extracted_tariff"),
            "llm_response_debug_text": "",
            "source_filename": tariff_snapshot.get("filename", ""),
            "loaded_from_session": True,
        }
        extracted = tariff_snapshot.get("extracted_tariff")
        if isinstance(extracted, dict):
            from asimplex.streamlit_app.simulation_plan_section import apply_extracted_tariff_to_simulation_plan_params

            apply_extracted_tariff_to_simulation_plan_params(extracted_tariff=extracted)
    update_simulation_plan_params()

def render_project_session_selector() -> None:
    """Render project/session selector under sidebar title."""
    init_db()
    session_ids = list_project_session_ids()
    options = [""] + session_ids
    default_session_id = str(st.session_state.get("project_session_id", "") or "")
    select_index = options.index(default_session_id) if default_session_id in options else 0

    selected_existing = st.sidebar.selectbox(
        "Project sessions",
        options=options,
        index=select_index,
        format_func=lambda x: "Select existing project..." if x == "" else x,
        key="project_session_selectbox",
    )
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Load project", key="load_project_session_btn", width="stretch"):
        if not selected_existing:
            st.sidebar.warning("Please select an existing project ID.")
        else:
            st.session_state["project_session_id"] = selected_existing
            st.session_state["project_name"] = get_project_name(selected_existing) or selected_existing
            st.session_state["session_ready"] = True
            _hydrate_profiles_for_session(selected_existing)
            st.sidebar.success(f"Loaded project: {selected_existing}")
            st.rerun()

    if c2.button("New project", key="new_project_toggle_btn", width="stretch"):
        st.session_state["show_new_project_input"] = True

    if st.session_state.get("show_new_project_input", False):
        project_name = st.sidebar.text_input(
            "New project name",
            value="",
            key="new_project_name_input",
            placeholder="e.g. Berlin_Pilot_A",
        )
        if st.sidebar.button("Create project", key="create_project_btn", type="primary", width="stretch"):
            session_id = normalize_project_name_to_session_id(project_name)
            if not session_id:
                st.sidebar.error("Project name is empty after normalization. Use letters/numbers.")
            elif project_exists(session_id):
                st.sidebar.error(f"Project ID already exists: {session_id}")
            else:
                create_project(session_id, project_name)
                st.session_state["project_name"] = project_name.strip()
                st.session_state["project_session_id"] = session_id
                st.session_state["session_ready"] = True
                st.session_state["show_new_project_input"] = False
                st.sidebar.success(f"Created project: {session_id}")
                st.rerun()

    active_project_name = str(st.session_state.get("project_name", "") or "").strip()
    if active_project_name:
        st.sidebar.caption(f"Active project: `{active_project_name}`")


def render_token_usage_table() -> None:
    """Render a fixed-height, scrollable token/cost usage table in sidebar."""
    raw = st.session_state.get("llm_usage")
    u = raw if isinstance(raw, dict) else {}
    total_in = int(u.get("total_input", 0) or 0)
    total_out = int(u.get("total_output", 0) or 0)
    total_cost = float(u.get("total_cost_eur", 0.0) or 0.0)
    rows = u.get("rows", [])
    rows_df = pd.DataFrame(rows if isinstance(rows, list) else [])
    if rows_df.empty:
        rows_df = pd.DataFrame(
            columns=["time", "action", "model", "ingest_tokens", "output_tokens", "total_tokens", "cost_eur"]
        )
    sum_row = {
        "time": "",
        "action": "SUM",
        "model": "",
        "ingest_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cost_eur": total_cost,
    }
    rows_df = pd.concat([rows_df, pd.DataFrame([sum_row])], ignore_index=True)
    if "cost_eur" in rows_df.columns:
        rows_df["cost_eur"] = pd.to_numeric(rows_df["cost_eur"], errors="coerce").fillna(0.0).map(
            lambda x: f"EUR {x:.6f}"
        )
    with st.sidebar.expander("LLM usage", expanded=False):
        st.dataframe(
            rows_df,
            width="stretch",
            height=220,
            hide_index=True,
        )


def render_sidebar() -> None:
    render_project_session_selector()
    st.sidebar.divider()
    render_load_profile_section()
    render_pv_profile_section()
    render_electrical_tariff_section()
    render_token_usage_table()
