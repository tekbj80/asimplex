"""Simulation plan UI for editable simuplex defaults and run control."""

from __future__ import annotations

import copy
import json

from bokeh.embed import file_html
from bokeh.resources import CDN
import pandas as pd
import streamlit as st
from simuplex import DEFAULT_BATTERY_PARAMS, DEFAULT_CLOCK_PARAMS, DEFAULT_COMMERCIAL_PARAMS, DEFAULT_GRID_PARAMS
from simuplex.applications.peak_shaving import DEFAULT_APPLICATION_PARAMS

from asimplex.observability.app_log_store import log_event
from asimplex.persistence.session_store import create_version, get_version_by_no, list_versions
from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.tools.simuplex_simulation import build_peak_shaving_simulator, build_simulation_plot_layout


def default_simulation_plan_params() -> dict:
    return {
        "clock": {
            "start_year": int(DEFAULT_CLOCK_PARAMS["start_time"].year),
            "timestep_minutes": int(DEFAULT_CLOCK_PARAMS["time_step_size"].total_seconds() // 60),
        },
        "application": {
            "grid_limit": float(DEFAULT_APPLICATION_PARAMS["grid_limit"]),
            "evo_threshold": float(DEFAULT_APPLICATION_PARAMS["evo_threshold"]),
            "lsk_charge_from_grid": bool(DEFAULT_APPLICATION_PARAMS["lsk_charge_from_grid"]),
            "grid_sale_allowed": bool(DEFAULT_APPLICATION_PARAMS["grid_sale_allowed"]),
            "backup_power_soc": float(DEFAULT_APPLICATION_PARAMS["backup_power_soc"]),
        },
        "battery": {
            "nominal_capacity": float(DEFAULT_BATTERY_PARAMS["nominal_capacity"]),
            "nominal_power": float(DEFAULT_BATTERY_PARAMS["nominal_power"]),
            "inverter_power": float(DEFAULT_BATTERY_PARAMS["inverter_power"]),
            "initial_soc": float(DEFAULT_BATTERY_PARAMS["initial_soc"]),
            "capex": float(DEFAULT_BATTERY_PARAMS["capex"]),
            "annual_opex": float(DEFAULT_BATTERY_PARAMS["annual_opex"]),
        },
        "grid": {
            "max_power": float(DEFAULT_GRID_PARAMS["max_power"]) if DEFAULT_GRID_PARAMS["max_power"] != float("inf") else 1e9,
        },
        "tariff": {
            "below_2500": {
                "grid_draw_cost": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["grid_draw_cost"]),
                "feed_in_tariff": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["feed_in_tariff"]),
                "demand_charge": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["demand_charge"]),
            },
            "above_2500": {
                "grid_draw_cost": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["grid_draw_cost"]),
                "feed_in_tariff": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["feed_in_tariff"]),
                "demand_charge": float(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["demand_charge"]),
            },
        },
        "tariff_non_functional": {
            "base_charge_eur_annual": 0.0,
            "taxes_duties_percent_of_total": 0.0,
        },
    }


SIM_PLAN_WIDGET_BINDINGS: tuple[tuple[str, tuple[str, ...], object], ...] = (
    ("sim_plan_start_year", ("clock", "start_year"), int),
    ("sim_plan_timestep_minutes", ("clock", "timestep_minutes"), int),
    ("sim_plan_grid_limit", ("application", "grid_limit"), float),
    ("sim_plan_evo_threshold", ("application", "evo_threshold"), float),
    ("sim_plan_backup_power_soc", ("application", "backup_power_soc"), float),
    ("sim_plan_lsk_charge_from_grid", ("application", "lsk_charge_from_grid"), bool),
    ("sim_plan_grid_sale_allowed", ("application", "grid_sale_allowed"), bool),
    ("sim_plan_nominal_capacity", ("battery", "nominal_capacity"), float),
    ("sim_plan_nominal_power", ("battery", "nominal_power"), float),
    ("sim_plan_inverter_power", ("battery", "inverter_power"), float),
    ("sim_plan_initial_soc", ("battery", "initial_soc"), float),
    ("sim_plan_capex", ("battery", "capex"), float),
    ("sim_plan_annual_opex", ("battery", "annual_opex"), float),
    ("sim_plan_grid_max_power", ("grid", "max_power"), float),
    ("sim_plan_tariff_below_grid_draw", ("tariff", "below_2500", "grid_draw_cost"), float),
    ("sim_plan_tariff_below_feed_in", ("tariff", "below_2500", "feed_in_tariff"), float),
    ("sim_plan_tariff_below_demand", ("tariff", "below_2500", "demand_charge"), float),
    ("sim_plan_tariff_above_grid_draw", ("tariff", "above_2500", "grid_draw_cost"), float),
    ("sim_plan_tariff_above_feed_in", ("tariff", "above_2500", "feed_in_tariff"), float),
    ("sim_plan_tariff_above_demand", ("tariff", "above_2500", "demand_charge"), float),
    ("sim_plan_base_charge_eur_annual", ("tariff_non_functional", "base_charge_eur_annual"), float),
    (
        "sim_plan_taxes_duties_percent_of_total",
        ("tariff_non_functional", "taxes_duties_percent_of_total"),
        float,
    ),
)


def _serializable_defaults_snapshot() -> dict:
    snapshot = {
        "DEFAULT_CLOCK_PARAMS": copy.deepcopy(DEFAULT_CLOCK_PARAMS),
        "DEFAULT_APPLICATION_PARAMS": copy.deepcopy(DEFAULT_APPLICATION_PARAMS),
        "DEFAULT_BATTERY_PARAMS": copy.deepcopy(DEFAULT_BATTERY_PARAMS),
        "DEFAULT_GRID_PARAMS": copy.deepcopy(DEFAULT_GRID_PARAMS),
        "DEFAULT_COMMERCIAL_PARAMS": {
            "below_2500": copy.deepcopy(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500),
            "above_2500": copy.deepcopy(DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500),
        },
    }
    serializable = {}
    for key, value in snapshot.items():
        serializable[key] = json.loads(json.dumps(value, default=str))
    return serializable


def _get_value_from_param_path(params: dict, path: tuple[str, ...]):
    cursor = params
    for part in path:
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def update_simulation_plan_params() -> dict:
    params = st.session_state.get("simulation_plan_params")
    if not isinstance(params, dict):
        params = default_simulation_plan_params()

    for widget_key, path, caster in SIM_PLAN_WIDGET_BINDINGS:
        value = _get_value_from_param_path(params, path)
        if value is None:
            continue
        st.session_state[widget_key] = caster(value)

    st.session_state["simulation_plan_params"] = params
    return params


def apply_extracted_tariff_to_simulation_plan_params(
    *,
    extracted_tariff: dict[str, object] | None,
) -> dict:
    params = st.session_state.get("simulation_plan_params")
    if not isinstance(params, dict):
        params = default_simulation_plan_params()

    if not isinstance(extracted_tariff, dict):
        st.session_state["simulation_plan_params"] = params
        return params

    try:
        below_2500 = extracted_tariff.get("below_2500_flh", {})
        above_2500 = extracted_tariff.get("above_2500_flh", {})
        if isinstance(below_2500, dict):
            params["tariff"]["below_2500"]["grid_draw_cost"] = float(below_2500["energy_charge_eur_per_kwh"])
            params["tariff"]["below_2500"]["demand_charge"] = float(below_2500["power_charge_eur_per_kw"])
        if isinstance(above_2500, dict):
            params["tariff"]["above_2500"]["grid_draw_cost"] = float(above_2500["energy_charge_eur_per_kwh"])
            params["tariff"]["above_2500"]["demand_charge"] = float(above_2500["power_charge_eur_per_kw"])
        params.setdefault("tariff_non_functional", {})
        params["tariff_non_functional"]["base_charge_eur_annual"] = float(extracted_tariff["base_charge_eur_annual"])
        params["tariff_non_functional"]["taxes_duties_percent_of_total"] = float(
            extracted_tariff["taxes_duties_percent_of_total"]
        )
    except (KeyError, TypeError, ValueError):
        st.session_state["simulation_plan_params"] = params
        return params

    st.session_state["simulation_plan_params"] = params
    return params


def _set_simulation_param_from_widget(path: tuple[str, ...], widget_key: str, caster) -> None:
    params = st.session_state.get("simulation_plan_params")
    if not isinstance(params, dict):
        params = default_simulation_plan_params()

    value = st.session_state.get(widget_key)
    if value is None:
        return
    value = caster(value)

    cursor = params
    for part in path[:-1]:
        cursor.setdefault(part, {})
        if not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[path[-1]] = value
    st.session_state["simulation_plan_params"] = params


def run_simulation_plan_with_params(params: dict) -> tuple[bool, str]:
    profiles = st.session_state.get("power_profiles")
    required_columns = {
        ProfileColumn.SITE_LOAD.column_name,
        ProfileColumn.PV_PRODUCTION.column_name,
    }
    if not isinstance(profiles, pd.DataFrame) or not required_columns.issubset(set(profiles.columns)):
        return False, "Load and PV profiles are required before running simulation."

    try:
        simulator = build_peak_shaving_simulator(
            load_profile=profiles[ProfileColumn.SITE_LOAD.column_name].astype(float).tolist(),
            pv_power_profile=profiles[ProfileColumn.PV_PRODUCTION.column_name].astype(float).tolist(),
            simulation_plan_params=params,
        )
        simulator.run_simulation(in_jupyter=False, disable_tqdm=False, calculate_benchmarks=True)
        benchmarks = simulator.benchmarks or {}
        simulation_plot_layout = build_simulation_plot_layout(
            simulator,
            title="Simulation Plan Output",
            additional_description="Interactive output from the proposed simulation settings.",
        )
        simulation_plot_html = file_html(simulation_plot_layout, CDN, "Simulation Plan Output")
        st.session_state["simulation_plan_benchmarks"] = benchmarks
        st.session_state["simulation_plan_simulator"] = simulator
        st.session_state["simulation_plan_plot_layout"] = simulation_plot_layout
        st.session_state["simulation_plan_plot_html"] = simulation_plot_html
        st.session_state["simulation_plan_params"] = params
        return True, "Simulation completed."
    except Exception as exc:  # pragma: no cover - runtime dependent path
        return False, f"Simulation failed: {exc}"


def render_simulation_plan_section() -> None:
    params = update_simulation_plan_params()
    st.session_state.setdefault("simulation_plan_benchmarks", None)
    st.session_state.setdefault("simulation_plan_simulator", None)
    st.session_state.setdefault("simulation_plan_plot_layout", None)
    st.session_state.setdefault("simulation_plan_plot_html", None)

    def _k(base: str) -> str:
        return base

    with st.expander("Simulation Plan", expanded=False):
        st.markdown("**Clock**")
        params["clock"]["start_year"] = int(
            st.number_input(
                "Start year",
                min_value=2000,
                max_value=2100,
                value=int(params["clock"]["start_year"]),
                key=_k("sim_plan_start_year"),
                on_change=_set_simulation_param_from_widget,
                args=(("clock", "start_year"), _k("sim_plan_start_year"), int),
            )
        )
        params["clock"]["timestep_minutes"] = int(
            st.number_input(
                "Timestep (minutes)",
                min_value=1,
                max_value=60,
                value=int(params["clock"]["timestep_minutes"]),
                key=_k("sim_plan_timestep_minutes"),
                on_change=_set_simulation_param_from_widget,
                args=(("clock", "timestep_minutes"), _k("sim_plan_timestep_minutes"), int),
            )
        )

        st.markdown("**Application**")
        params["application"]["grid_limit"] = float(
            st.number_input(
                "Grid limit (kW)",
                min_value=0.0,
                value=float(params["application"]["grid_limit"]),
                key=_k("sim_plan_grid_limit"),
                on_change=_set_simulation_param_from_widget,
                args=(("application", "grid_limit"), _k("sim_plan_grid_limit"), float),
            )
        )
        params["application"]["evo_threshold"] = float(
            st.number_input(
                "EVO threshold",
                min_value=0.0,
                max_value=1.0,
                value=float(params["application"]["evo_threshold"]),
                step=0.01,
                key=_k("sim_plan_evo_threshold"),
                on_change=_set_simulation_param_from_widget,
                args=(("application", "evo_threshold"), _k("sim_plan_evo_threshold"), float),
            )
        )
        params["application"]["backup_power_soc"] = float(
            st.number_input(
                "Backup power SOC",
                min_value=0.0,
                max_value=1.0,
                value=float(params["application"]["backup_power_soc"]),
                step=0.01,
                key=_k("sim_plan_backup_power_soc"),
                on_change=_set_simulation_param_from_widget,
                args=(("application", "backup_power_soc"), _k("sim_plan_backup_power_soc"), float),
            )
        )
        params["application"]["lsk_charge_from_grid"] = bool(
            st.checkbox(
                "LSK charge from grid",
                value=bool(params["application"]["lsk_charge_from_grid"]),
                key=_k("sim_plan_lsk_charge_from_grid"),
                on_change=_set_simulation_param_from_widget,
                args=(("application", "lsk_charge_from_grid"), _k("sim_plan_lsk_charge_from_grid"), bool),
            )
        )
        params["application"]["grid_sale_allowed"] = bool(
            st.checkbox(
                "Grid sale allowed",
                value=bool(params["application"]["grid_sale_allowed"]),
                key=_k("sim_plan_grid_sale_allowed"),
                on_change=_set_simulation_param_from_widget,
                args=(("application", "grid_sale_allowed"), _k("sim_plan_grid_sale_allowed"), bool),
            )
        )

        st.markdown("**Battery**")
        c1, c2 = st.columns(2)
        with c1:
            params["battery"]["nominal_capacity"] = float(
                st.number_input(
                    "Nominal capacity (kWh)",
                    min_value=0.0,
                    value=float(params["battery"]["nominal_capacity"]),
                    key=_k("sim_plan_nominal_capacity"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "nominal_capacity"), _k("sim_plan_nominal_capacity"), float),
                )
            )
            params["battery"]["nominal_power"] = float(
                st.number_input(
                    "Nominal power (kW)",
                    min_value=0.0,
                    value=float(params["battery"]["nominal_power"]),
                    key=_k("sim_plan_nominal_power"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "nominal_power"), _k("sim_plan_nominal_power"), float),
                )
            )
            params["battery"]["inverter_power"] = float(
                st.number_input(
                    "Inverter power (kW)",
                    min_value=0.0,
                    value=float(params["battery"]["inverter_power"]),
                    key=_k("sim_plan_inverter_power"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "inverter_power"), _k("sim_plan_inverter_power"), float),
                )
            )
        with c2:
            params["battery"]["initial_soc"] = float(
                st.number_input(
                    "Initial SOC",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(params["battery"]["initial_soc"]),
                    step=0.01,
                    key=_k("sim_plan_initial_soc"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "initial_soc"), _k("sim_plan_initial_soc"), float),
                )
            )
            params["battery"]["capex"] = float(
                st.number_input(
                    "CAPEX",
                    min_value=0.0,
                    value=float(params["battery"]["capex"]),
                    key=_k("sim_plan_capex"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "capex"), _k("sim_plan_capex"), float),
                )
            )
            params["battery"]["annual_opex"] = float(
                st.number_input(
                    "Annual OPEX",
                    min_value=0.0,
                    value=float(params["battery"]["annual_opex"]),
                    key=_k("sim_plan_annual_opex"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("battery", "annual_opex"), _k("sim_plan_annual_opex"), float),
                )
            )

        st.markdown("**Grid and Tariff**")
        params["grid"]["max_power"] = float(
            st.number_input(
                "Grid max power (kW)",
                min_value=0.0,
                value=float(params["grid"]["max_power"]),
                key=_k("sim_plan_grid_max_power"),
                on_change=_set_simulation_param_from_widget,
                args=(("grid", "max_power"), _k("sim_plan_grid_max_power"), float),
            )
        )
        electrical_tariff = st.session_state.get("electrical_tariff", {})
        extracted_tariff = electrical_tariff.get("llm_extracted_tariff")
        if isinstance(extracted_tariff, dict):
            st.caption("Tariff inputs were updated from the uploaded tariff PDF. You can still edit them manually.")
            with st.expander("Extracted tariff JSON", expanded=False):
                st.json(extracted_tariff)

        t1, t2 = st.columns(2)
        with t1:
            st.markdown("`<2500`")
            params["tariff"]["below_2500"]["grid_draw_cost"] = float(
                st.number_input(
                    "Grid draw cost (EUR/kWh)",
                    min_value=0.0,
                    value=float(params["tariff"]["below_2500"]["grid_draw_cost"]),
                    key=_k("sim_plan_tariff_below_grid_draw"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "below_2500", "grid_draw_cost"), _k("sim_plan_tariff_below_grid_draw"), float),
                )
            )
            params["tariff"]["below_2500"]["feed_in_tariff"] = float(
                st.number_input(
                    "Feed-in tariff (EUR/kWh)",
                    min_value=0.0,
                    value=float(params["tariff"]["below_2500"]["feed_in_tariff"]),
                    key=_k("sim_plan_tariff_below_feed_in"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "below_2500", "feed_in_tariff"), _k("sim_plan_tariff_below_feed_in"), float),
                )
            )
            params["tariff"]["below_2500"]["demand_charge"] = float(
                st.number_input(
                    "Demand charge (EUR/kW)",
                    min_value=0.0,
                    value=float(params["tariff"]["below_2500"]["demand_charge"]),
                    key=_k("sim_plan_tariff_below_demand"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "below_2500", "demand_charge"), _k("sim_plan_tariff_below_demand"), float),
                )
            )
        with t2:
            st.markdown("`>2500`")
            params["tariff"]["above_2500"]["grid_draw_cost"] = float(
                st.number_input(
                    "Grid draw cost (EUR/kWh) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["grid_draw_cost"]),
                    key=_k("sim_plan_tariff_above_grid_draw"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "above_2500", "grid_draw_cost"), _k("sim_plan_tariff_above_grid_draw"), float),
                )
            )
            params["tariff"]["above_2500"]["feed_in_tariff"] = float(
                st.number_input(
                    "Feed-in tariff (EUR/kWh) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["feed_in_tariff"]),
                    key=_k("sim_plan_tariff_above_feed_in"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "above_2500", "feed_in_tariff"), _k("sim_plan_tariff_above_feed_in"), float),
                )
            )
            params["tariff"]["above_2500"]["demand_charge"] = float(
                st.number_input(
                    "Demand charge (EUR/kW) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["demand_charge"]),
                    key=_k("sim_plan_tariff_above_demand"),
                    on_change=_set_simulation_param_from_widget,
                    args=(("tariff", "above_2500", "demand_charge"), _k("sim_plan_tariff_above_demand"), float),
                )
            )

        params.setdefault("tariff_non_functional", {})
        params["tariff_non_functional"]["base_charge_eur_annual"] = float(
            st.number_input(
                "Base charge (EUR/year) - not functional yet",
                min_value=0.0,
                value=float(params["tariff_non_functional"].get("base_charge_eur_annual", 0.0)),
                key=_k("sim_plan_base_charge_eur_annual"),
                on_change=_set_simulation_param_from_widget,
                args=(
                    ("tariff_non_functional", "base_charge_eur_annual"),
                    _k("sim_plan_base_charge_eur_annual"),
                    float,
                ),
            )
        )
        params["tariff_non_functional"]["taxes_duties_percent_of_total"] = float(
            st.number_input(
                "Taxes/duties (% of total) - not functional yet",
                min_value=0.0,
                max_value=100.0,
                value=float(params["tariff_non_functional"].get("taxes_duties_percent_of_total", 0.0)),
                step=0.1,
                key=_k("sim_plan_taxes_duties_percent_of_total"),
                on_change=_set_simulation_param_from_widget,
                args=(
                    ("tariff_non_functional", "taxes_duties_percent_of_total"),
                    _k("sim_plan_taxes_duties_percent_of_total"),
                    float,
                ),
            )
        )
        st.caption("Note: Base charge and taxes/duties are displayed for planning only and are not used in simulation yet.")

        st.session_state["simulation_plan_params"] = params

        if st.checkbox("Show default dictionaries", value=False, key="sim_plan_show_defaults"):
            st.code(json.dumps(_serializable_defaults_snapshot(), indent=2), language="json")

        st.markdown("---")
        st.markdown("**Simulation Parameter Versions**")
        project_name = str(st.session_state.get("project_name", "") or "")
        version_note = st.text_input(
            "Version note",
            value=str(st.session_state.get("sim_version_note", "") or ""),
            key="sim_version_note",
            placeholder="e.g. Manually adjusted grid limit after review",
        )
        versions = list_versions(project_name, limit=100) if project_name else []
        st.session_state["sim_versions_cache"] = versions

        selected_version_no = None
        if versions:
            selected_version_no = st.selectbox(
                "Saved versions",
                options=[int(v.get("version_no", -1)) for v in versions],
                format_func=lambda vn: next(
                    (
                        f"v{item['version_no']} - {item['created_at']} - {item['source']}"
                        + (f" ({item['note']})" if item.get("note") else "")
                        for item in versions
                        if int(item.get("version_no", -1)) == int(vn)
                    ),
                    f"v{vn}",
                ),
                index=0,
                key="sim_version_selected",
            )
        else:
            st.caption("No saved versions yet.")

        c_save, c_load = st.columns(2)
        if c_save.button("Save version", key="sim_version_save_btn", type="secondary", width="stretch"):
            if not project_name:
                st.warning("Load or create a project first to save versions.")
            else:
                version_no = create_version(
                    project_name=project_name,
                    source="manual_save",
                    note=version_note,
                    params=st.session_state.get("simulation_plan_params", {}),
                    patch={},
                )
                log_event(
                    project_name=project_name,
                    source="simulation_plan",
                    event_type="create_version",
                    status="success",
                    message=f"Manual simulation version saved as v{version_no}.",
                    payload={"version_no": version_no},
                )
                st.success(f"Saved version v{version_no}.")
                st.rerun()

        if c_load.button("Load selected version", key="sim_version_load_btn", width="stretch"):
            if not project_name:
                st.warning("Load or create a project first.")
            elif selected_version_no is None:
                st.warning("No saved version selected.")
            else:
                selected_payload = get_version_by_no(project_name, int(selected_version_no))
                if isinstance(selected_payload, dict):
                    selected_params = selected_payload.get("params", {})
                    if isinstance(selected_params, dict):
                        st.session_state["simulation_plan_params"] = selected_params
                        log_event(
                            project_name=project_name,
                            source="simulation_plan",
                            event_type="load_version",
                            status="success",
                            message=f"Loaded simulation version v{selected_version_no}.",
                            payload={"version_no": int(selected_version_no)},
                        )
                        st.success(f"Loaded version v{selected_version_no}.")
                        st.rerun()
                else:
                    st.error("Could not load selected version.")
                    log_event(
                        project_name=project_name,
                        source="simulation_plan",
                        event_type="load_version",
                        status="error",
                        message="Failed to load selected simulation version.",
                        payload={"version_no": int(selected_version_no)},
                    )
