"""Simulation run and results UI section."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from simuplex.common import BenchmarkNames, get_benchmark_name_attribute

from asimplex.streamlit_app.simulation_plan_section import run_simulation_plan_with_params
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


def render_simulation_results_section() -> None:
    with st.expander("Simulation Run & Results", expanded=False):
        params = st.session_state.get("simulation_plan_params", {})
        if st.button("Run simulation", type="primary", key="sim_plan_run_button"):
            st.info("Running simulator... tqdm progress is shown in terminal output.")
            with st.spinner("Simulation running..."):
                ok, msg = run_simulation_plan_with_params(params if isinstance(params, dict) else {})
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        benchmarks = st.session_state.get("simulation_plan_benchmarks")
        if isinstance(benchmarks, dict) and benchmarks:
            with st.expander("Simulation Benchmarks", expanded=False):
                benchmark_rows = [
                    {
                        "benchmark": _benchmark_label(benchmark_id),
                        "value": _format_benchmark_value(benchmark_id, benchmarks[benchmark_id]),
                    }
                    for benchmark_id in BENCHMARKS_TO_DISPLAY
                    if benchmark_id in benchmarks
                ]
                benchmark_df = pd.DataFrame(benchmark_rows)
                st.dataframe(benchmark_df, width="stretch", hide_index=True)

        simulation_plot_html = st.session_state.get("simulation_plan_plot_html")
        
        if isinstance(simulation_plot_html, str) and simulation_plot_html.strip():
            with st.expander("Simulation Interactive Plot", expanded=False):
                components.html(simulation_plot_html, height=850, scrolling=True)
