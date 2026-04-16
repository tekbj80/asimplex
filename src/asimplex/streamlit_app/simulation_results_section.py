"""Simulation run and results UI section."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from simuplex.common import BenchmarkNames, get_benchmark_name_attribute

from asimplex.streamlit_app.simulation_plan_section import run_simulation_plan_with_params
from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.tools.simuplex_simulation import build_base_case_simulator
from asimplex.tools.formatting import format_metric_value

BENCHMARKS_TO_DISPLAY = [
    "annual_electricity_cost",
    "grid_energy_cost",
    "feed_in_revenue",
    "power_charge",
    "grid_energy_drawn",
    "grid_energy_feed_in",
    "grid_peak_power_drawn",
    "grid_volllaststunde",
    "annual_operating_cost_no_discount",
    "amortization_period",
    "amortization_period_simple",
    "levelized_cost_of_energy",
    "internal_rate_of_return",
    "return_on_investment",
    "load_unmet",
    "load_total",
    "load_peak",
    "eigenverbrauchsquoten",
    "autarkiegrad",
    "pv_utilized_energy",
    "pv_potential_energy",
    "pv_curtailed_energy",
    "pv_self_consumption",
    "ess_cycles",
    "soh_degradation",
    "ess_life_time",
    "savings_due_to_battery",
]


def _benchmark_label(benchmark_id: str) -> str:
    attrs = get_benchmark_name_attribute(benchmark_id) or {}
    description = str(attrs.get("description", "") or benchmark_id)
    unit = str(attrs.get("unit", "") or "")
    return f"{description} ({unit})" if unit and unit != "_" else description


def _format_benchmark_value(benchmark_id: str, value: object) -> object:
    return format_metric_value(value)


def _base_case_ready() -> bool:
    profiles = st.session_state.get("power_profiles")
    required_columns = {
        ProfileColumn.SITE_LOAD.column_name,
        ProfileColumn.PV_PRODUCTION.column_name,
    }
    if not isinstance(profiles, pd.DataFrame) or not required_columns.issubset(set(profiles.columns)):
        return False
    tariff_state = st.session_state.get("electrical_tariff", {})
    extracted_tariff = tariff_state.get("llm_extracted_tariff") if isinstance(tariff_state, dict) else None
    return isinstance(extracted_tariff, dict) and bool(extracted_tariff)


def _run_base_case_simulation(params: dict) -> tuple[bool, str]:
    profiles = st.session_state.get("power_profiles")
    required_columns = {
        ProfileColumn.SITE_LOAD.column_name,
        ProfileColumn.PV_PRODUCTION.column_name,
    }
    if not isinstance(profiles, pd.DataFrame) or not required_columns.issubset(set(profiles.columns)):
        return False, "Load and PV profiles are required before running the base case."
    try:
        simulator = build_base_case_simulator(
            load_profile=profiles[ProfileColumn.SITE_LOAD.column_name].astype(float).tolist(),
            pv_power_profile=profiles[ProfileColumn.PV_PRODUCTION.column_name].astype(float).tolist(),
            simulation_plan_params=params if isinstance(params, dict) else {},
            has_existing_pv_system=bool(st.session_state.get("pv_system_already_exists", False)),
        )
        simulator.run_simulation(in_jupyter=False, disable_tqdm=False, calculate_benchmarks=True)
        st.session_state["base_case_benchmarks"] = simulator.benchmarks or {}
        return True, "Base case completed."
    except Exception as exc:  # pragma: no cover - runtime dependent path
        return False, f"Base case failed: {exc}"


def render_simulation_results_section() -> None:
    with st.expander("Simulation Run & Results", expanded=False):
        params = st.session_state.get("simulation_plan_params", {})
        base_case_enabled = _base_case_ready()
        c1, c2 = st.columns(2)
        if c1.button("Run base case", key="sim_base_case_run_button", disabled=not base_case_enabled):
            st.info("Running base case simulator... tqdm progress is shown in terminal output.")
            with st.spinner("Base case running..."):
                ok, msg = _run_base_case_simulation(params if isinstance(params, dict) else {})
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        if c2.button("Run simulation", type="primary", key="sim_plan_run_button"):
            st.info("Running proposal simulator... tqdm progress is shown in terminal output.")
            with st.spinner("Simulation running..."):
                ok, msg = run_simulation_plan_with_params(params if isinstance(params, dict) else {})
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        if not base_case_enabled:
            st.caption("Base case requires loaded load/PV profiles and extracted tariff values.")

        base_case_benchmarks = st.session_state.get("base_case_benchmarks")
        proposal_benchmarks = st.session_state.get("simulation_plan_benchmarks")
        if (
            isinstance(base_case_benchmarks, dict)
            and base_case_benchmarks
        ) or (
            isinstance(proposal_benchmarks, dict)
            and proposal_benchmarks
        ):
            with st.expander("Simulation Benchmarks", expanded=False):
                benchmark_rows = [
                    {
                        "benchmark": _benchmark_label(benchmark_id),
                        "Base Case": _format_benchmark_value(benchmark_id, base_case_benchmarks.get(benchmark_id))
                        if isinstance(base_case_benchmarks, dict) and benchmark_id in base_case_benchmarks
                        else None,
                        "Proposal": _format_benchmark_value(benchmark_id, proposal_benchmarks.get(benchmark_id))
                        if isinstance(proposal_benchmarks, dict) and benchmark_id in proposal_benchmarks
                        else None,
                    }
                    for benchmark_id in BENCHMARKS_TO_DISPLAY
                    if (
                        isinstance(base_case_benchmarks, dict)
                        and benchmark_id in base_case_benchmarks
                    ) or (
                        isinstance(proposal_benchmarks, dict)
                        and benchmark_id in proposal_benchmarks
                    )
                ]
                benchmark_df = pd.DataFrame(benchmark_rows)
                st.dataframe(benchmark_df, width="stretch", hide_index=True)

        simulation_plot_html = st.session_state.get("simulation_plan_plot_html")
        
        if isinstance(simulation_plot_html, str) and simulation_plot_html.strip():
            with st.expander("Simulation Interactive Plot", expanded=False):
                components.html(simulation_plot_html, height=850, scrolling=True)
