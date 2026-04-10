"""Load-profile UI section and shared profile helpers."""

from __future__ import annotations

from io import BytesIO
from numbers import Real

import pandas as pd
import streamlit as st

from asimplex.constants import HOUR_FRAC
from asimplex.tools.csv_tool import BASE_INDEX_15MIN, csv_reader_format, normalize_series_to_15min_2023


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
    if "power_profiles" not in st.session_state:
        st.session_state["power_profiles"] = pd.DataFrame(index=BASE_INDEX_15MIN.copy())


def _calculate_excess_and_deficit_of_pv_power(profiles_df: pd.DataFrame) -> pd.DataFrame:
    """Compute the excess and deficit of PV power."""
    has_load = "load" in profiles_df.columns
    has_pv = "pv" in profiles_df.columns
    if has_load and has_pv:
        profiles_df["excess_pv"] = (profiles_df["pv"] - profiles_df["load"]).clip(lower=0)
        profiles_df["grid_power_draw"] = (profiles_df["load"] - profiles_df["pv"]).clip(lower=0)
    else:
        profiles_df = profiles_df.drop(columns=["excess_pv", "grid_power_draw"], errors="ignore")
    return profiles_df


def _calculate_full_hour_equivalent(profiles_df: pd.DataFrame) -> None:
    """
    Update session-state full-hour-equivalent (FHE) using selected basis.

    - "load only" when no existing PV system
    - "residual load with PV" when existing PV system
    """
    use_residual_load = bool(st.session_state.get("pv_system_already_exists", False))
    if use_residual_load:
        col_for_fhe_calc = "grid_power_draw"
        calc_description = "residual load with PV"
    else:
        col_for_fhe_calc = "load"
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
        usage_hour_equivalent = profiles_df[col_for_fhe_calc].mul(HOUR_FRAC).sum() / col_peak
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


def _format_metric_name(metric_key: str) -> str:
    parts = metric_key.split("_")
    if not parts:
        return metric_key

    unit_candidates = {"kW", "kWh", "MW", "MWh", "W", "Wh", "N"}
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


def render_description_table(description: object, parse_attempts: list[str] | None = None) -> None:
    st.markdown("**Description**")
    if isinstance(description, str) and isinstance(parse_attempts, list) and len(parse_attempts) > 0:
        st.markdown(description)
        st.markdown("**Parse attempts**")
        st.markdown(f"```text\n{chr(10).join(parse_attempts[-5:])}\n```")
        return

    if isinstance(description, dict):
        metrics = [_format_metric_name(str(k)) for k in description.keys()]
        values = [_format_metric_value(v) for v in description.values()]
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

        if uploaded_file is not None:
            try:
                csv_bytes = BytesIO(uploaded_file.getvalue())
                result = csv_reader_format(csv_bytes=csv_bytes)
                st.session_state["load_profile_series"] = result.get("time_series_list")
                st.session_state["load_profile_description"] = result.get("description")
                st.session_state["load_profile_filename"] = uploaded_file.name
                st.session_state["load_profile_parse_attempts"] = result.get("parse_attempts")
                if isinstance(result.get("description"), dict):
                    apply_profile_to_power_profiles("load", result.get("time_series_list", []))
            except Exception as exc:  # pragma: no cover - UI defensive branch
                st.session_state["load_profile_series"] = [0]
                st.session_state["load_profile_description"] = f"Failed to parse file: {exc}"
                st.session_state["load_profile_filename"] = uploaded_file.name
                st.session_state["load_profile_parse_attempts"] = None

        description = st.session_state.get("load_profile_description")
        parse_attempts = st.session_state.get("load_profile_parse_attempts")
        if description is not None:
            render_description_table(description, parse_attempts=parse_attempts)
