"""Simulation run and results UI section."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from asimplex.streamlit_app.simulation_plan_section import run_simulation_plan_with_params


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
                benchmark_df = pd.DataFrame(
                    {"benchmark": list(benchmarks.keys()), "value": list(benchmarks.values())}
                )
                st.dataframe(benchmark_df, width="stretch", hide_index=True)

        simulation_plot_html = st.session_state.get("simulation_plan_plot_html")
        
        if isinstance(simulation_plot_html, str) and simulation_plot_html.strip():
            with st.expander("Simulation Interactive Plot", expanded=False):
                components.html(simulation_plot_html, height=850, scrolling=True)
