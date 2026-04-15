"""Load-profile UI section and shared profile helpers."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from asimplex.observability.app_log_store import log_event
from asimplex.persistence.session_store import get_profile_snapshot, save_profile_snapshot
from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.tools.calculations import calculate_full_hour_equivalent
from asimplex.tools.formatting import format_metric_name, format_metric_value
from asimplex.tools.csv_tool import csv_reader_format, normalize_series_to_15min_2023


def _calculate_excess_and_deficit_of_pv_power(profiles_df: pd.DataFrame) -> pd.DataFrame:
    """Compute the excess and deficit of PV power."""
    has_load = ProfileColumn.SITE_LOAD.column_name in profiles_df.columns
    has_pv = ProfileColumn.PV_PRODUCTION.column_name in profiles_df.columns
    if has_load and has_pv:
        profiles_df[ProfileColumn.PV_SURPLUS.column_name] = (
            profiles_df[ProfileColumn.PV_PRODUCTION.column_name] - profiles_df[ProfileColumn.SITE_LOAD.column_name]
        ).clip(lower=0)
        profiles_df[ProfileColumn.GRID_IMPORT.column_name] = (
            profiles_df[ProfileColumn.SITE_LOAD.column_name] - profiles_df[ProfileColumn.PV_PRODUCTION.column_name]
        ).clip(lower=0)
    else:
        profiles_df = profiles_df.drop(
            columns=[ProfileColumn.PV_SURPLUS.column_name, ProfileColumn.GRID_IMPORT.column_name], errors="ignore"
        )
    return profiles_df


def _calculate_full_hour_equivalent(profiles_df: pd.DataFrame) -> None:
    """
    Update session-state full-hour-equivalent (FHE) using selected basis.

    - "load only" when no existing PV system
    - "residual load with PV" when existing PV system
    """
    use_residual_load = bool(st.session_state.get("pv_system_already_exists", False))
    if use_residual_load:
        col_for_fhe_calc = ProfileColumn.GRID_IMPORT.column_name
        calc_description = "residual load with PV"
    else:
        col_for_fhe_calc = ProfileColumn.SITE_LOAD.column_name
        calc_description = "load only"

    usage_state = st.session_state.get("usage_hour_equivalent")
    if not isinstance(usage_state, dict):
        usage_state = {"value": None, "description": calc_description}
    usage_state["description"] = calc_description

    if col_for_fhe_calc in profiles_df.columns:
        col_peak = float(profiles_df[col_for_fhe_calc].max())
    else:
        col_peak = 0.0

    if col_peak > 0 and col_for_fhe_calc in profiles_df.columns:
        usage_hour_equivalent = calculate_full_hour_equivalent(profiles_df[col_for_fhe_calc])
        usage_state["value"] = float(usage_hour_equivalent)
    elif col_for_fhe_calc in profiles_df.columns:
        usage_state["value"] = 0.0
    else:
        usage_state["value"] = None
    st.session_state["usage_hour_equivalent"] = usage_state


def refresh_power_profiles_metrics() -> None:
    profiles_df = st.session_state.get("power_profiles")
    if isinstance(profiles_df, pd.DataFrame):
        updated_profiles_df = _calculate_excess_and_deficit_of_pv_power(profiles_df.copy())
        _calculate_full_hour_equivalent(updated_profiles_df)
        st.session_state["power_profiles"] = updated_profiles_df


def apply_profile_to_power_profiles(column_name: str, values: list[object]) -> bool:
    series_15 = normalize_series_to_15min_2023(values)
    if series_15 is None:
        return False
    profiles_df = st.session_state["power_profiles"].copy()
    profiles_df[column_name] = series_15.values
    profiles_df = _calculate_excess_and_deficit_of_pv_power(profiles_df)
    _calculate_full_hour_equivalent(profiles_df)
    st.session_state["power_profiles"] = profiles_df
    return True


def render_description_table(description: object, parse_attempts: list[str] | None = None) -> None:
    st.markdown("**Description**")
    if isinstance(description, str) and isinstance(parse_attempts, list) and len(parse_attempts) > 0:
        st.markdown(description)
        st.markdown("**Parse attempts**")
        st.markdown(f"```text\n{chr(10).join(parse_attempts[-5:])}\n```")
        return

    if isinstance(description, dict):
        metrics = [format_metric_name(str(k)) for k in description.keys()]
        values = [format_metric_value(v) for v in description.values()]
        table_df = pd.DataFrame({"metric": metrics, "value": values})
        st.dataframe(
            table_df,
            hide_index=True,
            width="stretch",
        )
        return

    fallback_df = pd.DataFrame({"metric": ["description"], "value": [description]})
    st.dataframe(fallback_df, hide_index=True, width="stretch")


def render_load_profile_section() -> None:
    with st.sidebar.expander("Load profile", expanded=True):
        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            accept_multiple_files=False,
            key="load_profile_upload",
        )
        update_reason = st.text_input(
            "Reason for updating load profile",
            key="load_profile_update_reason",
            placeholder="e.g. Updated from latest metering export",
        )

        if uploaded_file is not None:
            try:
                csv_bytes = BytesIO(uploaded_file.getvalue())
                result = csv_reader_format(csv_bytes=csv_bytes)
                st.session_state["load_profile_series"] = result.get("time_series_list")
                st.session_state["load_profile_description"] = result.get("description")
                st.session_state["load_profile_filename"] = uploaded_file.name
                st.session_state["load_profile_parse_attempts"] = result.get("parse_attempts")
                if isinstance(result.get("description"), dict):
                    apply_profile_to_power_profiles(
                        ProfileColumn.SITE_LOAD.column_name, result.get("time_series_list", [])
                    )
                    project_name = str(st.session_state.get("project_name", "") or "")
                    if project_name:
                        overwritten = save_profile_snapshot(
                            project_name=project_name,
                            profile_type="load",
                            filename=uploaded_file.name,
                            series=result.get("time_series_list"),
                            description=result.get("description"),
                            parse_attempts=result.get("parse_attempts"),
                            metadata={"source": "csv_upload"},
                            reason_text=update_reason,
                        )
                        snapshot = get_profile_snapshot(project_name, "load")
                        if isinstance(snapshot, dict):
                            st.session_state["load_profile_reason_text"] = snapshot.get("reason_text", "")
                            st.session_state["load_profile_created_at"] = snapshot.get("created_at", "")
                            st.session_state["load_profile_updated_at"] = snapshot.get("updated_at", "")
                        if overwritten:
                            st.info("Load profile already existed for this project and has been overwritten.")
                        else:
                            st.success("Load profile saved to project storage.")
                        log_event(
                            project_name=project_name,
                            source="load_profile",
                            event_type="save_profile_snapshot",
                            status="success",
                            message="Load profile snapshot saved.",
                            payload={"filename": uploaded_file.name, "overwritten": overwritten},
                        )
            except Exception as exc:  # pragma: no cover - UI defensive branch
                st.session_state["load_profile_series"] = [0]
                st.session_state["load_profile_description"] = f"Failed to parse file: {exc}"
                st.session_state["load_profile_filename"] = uploaded_file.name
                st.session_state["load_profile_parse_attempts"] = None
                log_event(
                    project_name=str(st.session_state.get("project_name", "") or ""),
                    source="load_profile",
                    event_type="save_profile_snapshot",
                    status="error",
                    error=str(exc),
                    message="Load profile parsing/saving failed.",
                    payload={"filename": uploaded_file.name},
                )

        description = st.session_state.get("load_profile_description")
        parse_attempts = st.session_state.get("load_profile_parse_attempts")
        loaded_filename = st.session_state.get("load_profile_filename")
        if isinstance(loaded_filename, str) and loaded_filename.strip():
            st.caption(f"Loaded file: `{loaded_filename}`")
        load_created_at = str(st.session_state.get("load_profile_created_at", "") or "")
        load_updated_at = str(st.session_state.get("load_profile_updated_at", "") or "")
        load_reason_text = str(st.session_state.get("load_profile_reason_text", "") or "")
        if load_created_at or load_updated_at or load_reason_text:
            meta_parts: list[str] = []
            if load_created_at:
                meta_parts.append(f"Created: {load_created_at}")
            if load_updated_at:
                meta_parts.append(f"Updated: {load_updated_at}")
            if load_reason_text:
                meta_parts.append(f"Reason: {load_reason_text}")
            st.caption(" | ".join(meta_parts))
        if description is not None:
            render_description_table(description, parse_attempts=parse_attempts)
