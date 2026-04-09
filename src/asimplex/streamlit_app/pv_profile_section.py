"""PV profile UI section."""

from __future__ import annotations

from io import BytesIO

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

from asimplex.streamlit_app.load_profile_section import (
    apply_profile_to_power_profiles,
    render_description_table,
)
from asimplex.tools.csv_tool import csv_reader_format, normalize_series_to_15min_2023


def _fetch_pv_power_profile_15min(
    lat: float,
    lon: float,
    *,
    peak_power_kwp: float,
    tilt_deg: float,
    azimuth_deg: float,
    loss_percent: float,
    timeout: float = 120.0,
) -> pd.Series:
    params = {
        "lat": lat,
        "lon": lon,
        "pvcalculation": 1,
        "peakpower": peak_power_kwp,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "loss": loss_percent,
        "startyear": 2019,
        "endyear": 2019,
        "outputformat": "json",
        "trackingtype": 0,
    }
    response = requests.get(
        "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    records = payload.get("outputs", {}).get("hourly")
    if not records:
        raise ValueError("PVGIS response has no outputs.hourly.")

    hourly_df = pd.DataFrame(records)
    if "P" not in hourly_df.columns:
        raise ValueError("PVGIS response has no P column.")

    # Keep it simple: use PVGIS P column directly (W -> kW),
    # then normalize with the existing app helper.
    p_values_kw = (pd.to_numeric(hourly_df["P"], errors="coerce") / 1000.0).dropna().tolist()
    normalized = normalize_series_to_15min_2023(p_values_kw)
    if normalized is None:
        raise ValueError("PVGIS profile could not be normalized to the app timeline.")
    return normalized


def _build_description_from_series(series: pd.Series) -> dict[str, float]:
    return {
        "highest_energy_per_day_kWh": float(series.resample("D").sum().max() * 0.25),
        "lowest_energy_per_day_kWh": float(series.resample("D").sum().min() * 0.25),
        "average_energy_per_day_kWh": float(series.resample("D").sum().mean() * 0.25),
        "peak_power_kW": float(series.max()),
        "lowest_power_kW": float(series.min()),
        "rows_of_data_N": float(len(series)),
    }


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
                st.session_state["pv_profile_parse_attempts"] = result.get("parse_attempts")
                if isinstance(result.get("description"), dict):
                    apply_profile_to_power_profiles("pv", result.get("time_series_list", []))
            except Exception as exc:  # pragma: no cover - UI defensive branch
                st.session_state["pv_profile_series"] = [0]
                st.session_state["pv_profile_description"] = f"Failed to parse PV file: {exc}"
                st.session_state["pv_profile_filename"] = uploaded_file.name
                st.session_state["pv_profile_parse_attempts"] = None

        st.markdown("**Map**")
        m = folium.Map(
            location=[st.session_state["project_lat"], st.session_state["project_lon"]],
            zoom_start=6,
            control_scale=True,
        )
        folium.LatLngPopup().add_to(m)
        folium.Marker(
            [st.session_state["project_lat"], st.session_state["project_lon"]],
            tooltip="Selected location",
            icon=folium.Icon(color="green", icon="info-sign"),
        ).add_to(m)
        output = st_folium(m, width=None, height=320, use_container_width=True, key="pv_profile_map")
        if output and output.get("last_clicked"):
            st.session_state["project_lat"] = float(output["last_clicked"]["lat"])
            st.session_state["project_lon"] = float(output["last_clicked"]["lng"])
            st.success(
                f"Location set: {st.session_state['project_lat']:.6f}, {st.session_state['project_lon']:.6f}"
            )

        c1, c2 = st.columns(2)
        with c1:
            lat = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=float(st.session_state["project_lat"]),
                format="%.6f",
                key="pv_manual_lat",
            )
            peak_kw = st.number_input(
                "Peak power (kWp)",
                min_value=0.1,
                value=1.0,
                step=0.1,
                format="%.3f",
                key="pvgis_peak_kw",
            )
            tilt = st.number_input(
                "Tilt angle (deg)",
                min_value=0.0,
                max_value=90.0,
                value=10.0,
                step=1.0,
                key="pvgis_tilt",
            )
        with c2:
            lon = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=float(st.session_state["project_lon"]),
                format="%.6f",
                key="pv_manual_lon",
            )
            azimuth = st.number_input(
                "Azimuth (deg)",
                min_value=-180.0,
                max_value=180.0,
                value=0.0,
                step=1.0,
                help="PVGIS: 0 = South, +90 = West, -90 = East.",
                key="pvgis_azimuth",
            )
            loss = st.number_input(
                "Losses (%)",
                min_value=0.0,
                max_value=100.0,
                value=22.85,
                step=0.5,
                key="pvgis_loss",
            )

        st.session_state["project_lat"] = float(lat)
        st.session_state["project_lon"] = float(lon)

        if st.button("Fetch PV profile (15 min)", type="primary", key="pvgis_fetch"):
            try:
                with st.spinner("Calling PVGIS (may take a minute)..."):
                    pv_series_15 = _fetch_pv_power_profile_15min(
                        st.session_state["project_lat"],
                        st.session_state["project_lon"],
                        peak_power_kwp=float(peak_kw),
                        tilt_deg=float(tilt),
                        azimuth_deg=float(azimuth),
                        loss_percent=float(loss),
                    )
                applied = apply_profile_to_power_profiles("pv", pv_series_15.tolist())
                if not applied:
                    raise ValueError("Fetched PV profile could not be aligned to the app timeline.")
                st.session_state["pv_profile_series"] = pv_series_15.tolist()
                st.session_state["pv_profile_description"] = _build_description_from_series(pv_series_15)
                st.session_state["pv_profile_filename"] = "PVGIS seriescalc"
                st.session_state["pv_profile_parse_attempts"] = None
                st.success(f"Fetched and stored {len(pv_series_15)} PV rows.")
            except Exception as exc:
                st.error(f"Request failed: {exc}")

        description = st.session_state.get("pv_profile_description")
        parse_attempts = st.session_state.get("pv_profile_parse_attempts")
        if description is not None:
            render_description_table(description, parse_attempts=parse_attempts)
