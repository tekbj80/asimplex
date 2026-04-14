"""Simulation plan UI for editable simuplex defaults and run control."""

from __future__ import annotations

import copy
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from simuplex import DEFAULT_BATTERY_PARAMS, DEFAULT_CLOCK_PARAMS, DEFAULT_COMMERCIAL_PARAMS, DEFAULT_GRID_PARAMS
from simuplex.applications.peak_shaving import DEFAULT_APPLICATION_PARAMS

from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.tools.simuplex_simulation import build_peak_shaving_simulator, build_simulation_plot_html


def _default_simulation_plan_params() -> dict:
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


def _apply_extracted_tariff_to_params(params: dict) -> tuple[dict, bool]:
    electrical_tariff = st.session_state.get("electrical_tariff", {})
    extracted = electrical_tariff.get("llm_extracted_tariff", {})
    if not isinstance(extracted, dict):
        return params, False

    above_2500 = extracted.get("above_2500_flh", {})
    below_2500 = extracted.get("below_2500_flh", {})
    if not isinstance(above_2500, dict) or not isinstance(below_2500, dict):
        return params, False

    extracted_signature = json.dumps(extracted, sort_keys=True)
    already_applied_signature = params.get("_last_extracted_tariff_signature")
    if already_applied_signature == extracted_signature:
        return params, True

    try:
        params["tariff"]["below_2500"]["grid_draw_cost"] = float(below_2500["energy_charge_eur_per_kwh"])
        params["tariff"]["below_2500"]["demand_charge"] = float(below_2500["power_charge_eur_per_kw"])
        params["tariff"]["above_2500"]["grid_draw_cost"] = float(above_2500["energy_charge_eur_per_kwh"])
        params["tariff"]["above_2500"]["demand_charge"] = float(above_2500["power_charge_eur_per_kw"])
        params.setdefault("tariff_non_functional", {})
        params["tariff_non_functional"]["base_charge_eur_annual"] = float(extracted["base_charge_eur_annual"])
        params["tariff_non_functional"]["taxes_duties_percent_of_total"] = float(
            extracted["taxes_duties_percent_of_total"]
        )
        params["_last_extracted_tariff_signature"] = extracted_signature
    except (KeyError, TypeError, ValueError):
        return params, False
    return params, True


def render_simulation_plan_section() -> None:
    params = st.session_state.get("simulation_plan_params")
    if not isinstance(params, dict):
        params = _default_simulation_plan_params()
        st.session_state["simulation_plan_params"] = params
    st.session_state.setdefault("simulation_plan_benchmarks", None)
    st.session_state.setdefault("simulation_plan_plot_html", None)

    with st.expander("Simulation Plan", expanded=False):
        st.markdown("**Clock**")
        params["clock"]["start_year"] = int(
            st.number_input(
                "Start year",
                min_value=2000,
                max_value=2100,
                value=int(params["clock"]["start_year"]),
                key="sim_plan_start_year",
            )
        )
        params["clock"]["timestep_minutes"] = int(
            st.number_input(
                "Timestep (minutes)",
                min_value=1,
                max_value=60,
                value=int(params["clock"]["timestep_minutes"]),
                key="sim_plan_timestep_minutes",
            )
        )

        st.markdown("**Application**")
        params["application"]["grid_limit"] = float(
            st.number_input(
                "Grid limit (kW)",
                min_value=0.0,
                value=float(params["application"]["grid_limit"]),
                key="sim_plan_grid_limit",
            )
        )
        params["application"]["evo_threshold"] = float(
            st.number_input(
                "EVO threshold",
                min_value=0.0,
                max_value=2.0,
                value=float(params["application"]["evo_threshold"]),
                step=0.01,
                key="sim_plan_evo_threshold",
            )
        )
        params["application"]["backup_power_soc"] = float(
            st.number_input(
                "Backup power SOC",
                min_value=0.0,
                max_value=1.0,
                value=float(params["application"]["backup_power_soc"]),
                step=0.01,
                key="sim_plan_backup_power_soc",
            )
        )
        params["application"]["lsk_charge_from_grid"] = bool(
            st.checkbox(
                "LSK charge from grid",
                value=bool(params["application"]["lsk_charge_from_grid"]),
                key="sim_plan_lsk_charge_from_grid",
            )
        )
        params["application"]["grid_sale_allowed"] = bool(
            st.checkbox(
                "Grid sale allowed",
                value=bool(params["application"]["grid_sale_allowed"]),
                key="sim_plan_grid_sale_allowed",
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
                    key="sim_plan_nominal_capacity",
                )
            )
            params["battery"]["nominal_power"] = float(
                st.number_input(
                    "Nominal power (kW)",
                    min_value=0.0,
                    value=float(params["battery"]["nominal_power"]),
                    key="sim_plan_nominal_power",
                )
            )
            params["battery"]["inverter_power"] = float(
                st.number_input(
                    "Inverter power (kW)",
                    min_value=0.0,
                    value=float(params["battery"]["inverter_power"]),
                    key="sim_plan_inverter_power",
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
                    key="sim_plan_initial_soc",
                )
            )
            params["battery"]["capex"] = float(
                st.number_input(
                    "CAPEX",
                    min_value=0.0,
                    value=float(params["battery"]["capex"]),
                    key="sim_plan_capex",
                )
            )
            params["battery"]["annual_opex"] = float(
                st.number_input(
                    "Annual OPEX",
                    min_value=0.0,
                    value=float(params["battery"]["annual_opex"]),
                    key="sim_plan_annual_opex",
                )
            )

        st.markdown("**Grid and Tariff**")
        params["grid"]["max_power"] = float(
            st.number_input(
                "Grid max power (kW)",
                min_value=0.0,
                value=float(params["grid"]["max_power"]),
                key="sim_plan_grid_max_power",
            )
        )
        params, has_extracted_tariff = _apply_extracted_tariff_to_params(params)
        electrical_tariff = st.session_state.get("electrical_tariff", {})
        extracted_tariff = electrical_tariff.get("llm_extracted_tariff")
        if has_extracted_tariff and isinstance(extracted_tariff, dict):
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
                    key="sim_plan_tariff_below_grid_draw",
                )
            )
            params["tariff"]["below_2500"]["feed_in_tariff"] = float(
                st.number_input(
                    "Feed-in tariff (EUR/kWh)",
                    min_value=0.0,
                    value=float(params["tariff"]["below_2500"]["feed_in_tariff"]),
                    key="sim_plan_tariff_below_feed_in",
                )
            )
            params["tariff"]["below_2500"]["demand_charge"] = float(
                st.number_input(
                    "Demand charge (EUR/kW)",
                    min_value=0.0,
                    value=float(params["tariff"]["below_2500"]["demand_charge"]),
                    key="sim_plan_tariff_below_demand",
                )
            )
        with t2:
            st.markdown("`>2500`")
            params["tariff"]["above_2500"]["grid_draw_cost"] = float(
                st.number_input(
                    "Grid draw cost (EUR/kWh) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["grid_draw_cost"]),
                    key="sim_plan_tariff_above_grid_draw",
                )
            )
            params["tariff"]["above_2500"]["feed_in_tariff"] = float(
                st.number_input(
                    "Feed-in tariff (EUR/kWh) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["feed_in_tariff"]),
                    key="sim_plan_tariff_above_feed_in",
                )
            )
            params["tariff"]["above_2500"]["demand_charge"] = float(
                st.number_input(
                    "Demand charge (EUR/kW) ",
                    min_value=0.0,
                    value=float(params["tariff"]["above_2500"]["demand_charge"]),
                    key="sim_plan_tariff_above_demand",
                )
            )

        params.setdefault("tariff_non_functional", {})
        params["tariff_non_functional"]["base_charge_eur_annual"] = float(
            st.number_input(
                "Base charge (EUR/year) - not functional yet",
                min_value=0.0,
                value=float(params["tariff_non_functional"].get("base_charge_eur_annual", 0.0)),
                key="sim_plan_base_charge_eur_annual",
            )
        )
        params["tariff_non_functional"]["taxes_duties_percent_of_total"] = float(
            st.number_input(
                "Taxes/duties (% of total) - not functional yet",
                min_value=0.0,
                max_value=100.0,
                value=float(params["tariff_non_functional"].get("taxes_duties_percent_of_total", 0.0)),
                step=0.1,
                key="sim_plan_taxes_duties_percent_of_total",
            )
        )
        st.caption("Note: Base charge and taxes/duties are displayed for planning only and are not used in simulation yet.")

        st.session_state["simulation_plan_params"] = params

        if st.checkbox("Show default dictionaries", value=False, key="sim_plan_show_defaults"):
            st.code(json.dumps(_serializable_defaults_snapshot(), indent=2), language="json")

        if st.button("Run simulation", type="primary", key="sim_plan_run_button"):
            profiles = st.session_state.get("power_profiles")
            required_columns = {
                ProfileColumn.SITE_LOAD.column_name,
                ProfileColumn.PV_PRODUCTION.column_name,
            }
            if not isinstance(profiles, pd.DataFrame) or not required_columns.issubset(set(profiles.columns)):
                st.error("Load and PV profiles are required before running simulation.")
            else:
                try:
                    st.info("Running simulator... tqdm progress is shown in terminal output.")
                    simulator = build_peak_shaving_simulator(
                        load_profile=profiles[ProfileColumn.SITE_LOAD.column_name].astype(float).tolist(),
                        pv_power_profile=profiles[ProfileColumn.PV_PRODUCTION.column_name].astype(float).tolist(),
                        simulation_plan_params=params,
                    )
                    with st.spinner("Simulation running..."):
                        simulator.run_simulation(in_jupyter=False, disable_tqdm=False, calculate_benchmarks=True)
                    benchmarks = simulator.benchmarks or {}
                    simulation_plot_html = build_simulation_plot_html(simulator, title="Simulation Plan Output")
                    st.session_state["simulation_plan_benchmarks"] = benchmarks
                    st.session_state["simulation_plan_plot_html"] = simulation_plot_html
                    st.success("Simulation completed.")
                except Exception as exc:
                    st.error(f"Simulation failed: {exc}")

        benchmarks = st.session_state.get("simulation_plan_benchmarks")
        if isinstance(benchmarks, dict) and benchmarks:
            with st.expander("Simulation Benchmarks", expanded=True):
                benchmark_df = pd.DataFrame(
                    {"benchmark": list(benchmarks.keys()), "value": list(benchmarks.values())}
                )
                st.dataframe(benchmark_df, width="stretch", hide_index=True)

        simulation_plot_html = st.session_state.get("simulation_plan_plot_html")
        if isinstance(simulation_plot_html, str) and simulation_plot_html.strip():
            with st.expander("Simulation Interactive Plot", expanded=True):
                st.markdown("**Simulation Interactive Plot**")
                components.html(simulation_plot_html, height=850, scrolling=True)
