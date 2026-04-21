"""Simulation run and results UI section."""

from __future__ import annotations

from bokeh.embed import file_html
from bokeh.resources import CDN
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from numbers import Real
from simuplex.common import BenchmarkNames, get_benchmark_name_attribute

from asimplex.streamlit_app.simulation_plan_section import run_simulation_plan_with_params
from asimplex.streamlit_app.profile_columns import ProfileColumn
from asimplex.tools.simuplex_simulation import build_base_case_simulator
from asimplex.tools.formatting import format_metric_value
from asimplex.tools.simuplex_simulation import build_simulation_plot_layout

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


def _benchmark_display_formatter(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        precision = 2 if abs(float(value)) > 1 else 5
        return f"{float(value):,.{precision}f}"
    return value


def _numeric_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _has_meaningful_benchmarks(benchmarks: object) -> bool:
    if not isinstance(benchmarks, dict) or not benchmarks:
        return False
    numeric_values = [_numeric_or_none(value) for value in benchmarks.values()]
    numeric_values = [value for value in numeric_values if value is not None]
    if numeric_values:
        return any(value != 0.0 for value in numeric_values)
    return any(bool(value) for value in benchmarks.values())


def _build_benchmark_context_payload(
    base_case_benchmarks: object,
    proposal_benchmarks: object,
) -> dict[str, object]:
    if not isinstance(base_case_benchmarks, dict) or not base_case_benchmarks:
        return {}
    if not isinstance(proposal_benchmarks, dict) or not proposal_benchmarks:
        return {
            "base_case_benchmarks": {
                benchmark_id: base_case_benchmarks[benchmark_id]
                for benchmark_id in BENCHMARKS_TO_DISPLAY
                if benchmark_id in base_case_benchmarks
            }
        }

    comparison_rows: list[dict[str, object]] = []
    for benchmark_id in BENCHMARKS_TO_DISPLAY:
        if benchmark_id not in base_case_benchmarks and benchmark_id not in proposal_benchmarks:
            continue
        attrs = get_benchmark_name_attribute(benchmark_id) or {}
        base_value = base_case_benchmarks.get(benchmark_id)
        proposal_value = proposal_benchmarks.get(benchmark_id)
        base_numeric = _numeric_or_none(base_value)
        proposal_numeric = _numeric_or_none(proposal_value)
        comparison_rows.append(
            {
                "benchmark_id": benchmark_id,
                "description": str(attrs.get("description", "") or benchmark_id),
                "unit": str(attrs.get("unit", "") or ""),
                "base_case": base_value,
                "proposed_case": proposal_value,
                "improvement_proposed_minus_base_case": (
                    proposal_numeric - base_numeric
                    if proposal_numeric is not None and base_numeric is not None
                    else None
                ),
                "diff_base_case_minus_proposed_case": (
                    base_numeric - proposal_numeric
                    if proposal_numeric is not None and base_numeric is not None
                    else None
                ),
            }
        )
    return {
        "base_case_benchmarks": {
            benchmark_id: base_case_benchmarks[benchmark_id]
            for benchmark_id in BENCHMARKS_TO_DISPLAY
            if benchmark_id in base_case_benchmarks
        },
        "proposal_benchmarks": {
            benchmark_id: proposal_benchmarks[benchmark_id]
            for benchmark_id in BENCHMARKS_TO_DISPLAY
            if benchmark_id in proposal_benchmarks
        },
        "comparison_rows": comparison_rows,
    }


def _ensure_agent_generated_save_description(
    *,
    benchmark_context_payload: object,
) -> str:
    if not isinstance(benchmark_context_payload, dict) or not benchmark_context_payload:
        return ""
    try:
        from asimplex.agent.runner import run_benchmark_summary_agent

        description = run_benchmark_summary_agent(session_state=st.session_state)
        return description.strip() if isinstance(description, str) else ""
    except Exception:
        return ""


def _format_export_description(text: str) -> str:
    """Keep description readable by splitting inline bullets onto new lines."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    parts = [part.strip() for part in raw.split("- ") if part.strip()]
    if len(parts) <= 1:
        return raw
    return "\n".join(f"- {part}" for part in parts)


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


def render_base_case_section() -> None:
    params = st.session_state.get("simulation_plan_params", {})
    base_case_enabled = _base_case_ready()
    if st.button("Run base case", key="sim_base_case_run_button", disabled=not base_case_enabled):
        st.info("Running base case simulator... tqdm progress is shown in terminal output.")
        with st.spinner("Base case running..."):
            ok, msg = _run_base_case_simulation(params if isinstance(params, dict) else {})
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    if not base_case_enabled:
        st.caption("Base case requires loaded load/PV profiles and extracted tariff values.")


def render_simulation_results_section() -> None:
    params = st.session_state.get("simulation_plan_params", {})
    base_case_benchmarks = st.session_state.get("base_case_benchmarks")
    proposal_benchmarks = st.session_state.get("simulation_plan_benchmarks")
    simulation_plot_html = st.session_state.get("simulation_plan_plot_html")
    simulation_plot_layout = st.session_state.get("simulation_plan_plot_layout")
    simulation_simulator = st.session_state.get("simulation_plan_simulator")
    proposal_enabled = _has_meaningful_benchmarks(base_case_benchmarks)
    st.session_state["simulation_benchmark_context_json"] = _build_benchmark_context_payload(
        base_case_benchmarks,
        proposal_benchmarks,
    )

    if st.button("Run simulation", type="primary", key="sim_plan_run_button", disabled=not proposal_enabled):
        st.info("Running proposal simulator... tqdm progress is shown in terminal output.")
        with st.spinner("Simulation running..."):
            ok, msg = run_simulation_plan_with_params(params if isinstance(params, dict) else {})
        if ok:
            st.success(msg)
        else:
            st.error(msg)
    if not proposal_enabled:
        st.caption("Please run the base case simulation first, then the proposal simulation can be done.")

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
                    "Improvement (Base Case - Proposal)": _format_benchmark_value(
                        benchmark_id,
                        (
                            _numeric_or_none(base_case_benchmarks.get(benchmark_id))
                            - _numeric_or_none(proposal_benchmarks.get(benchmark_id))
                        )
                        if (
                            isinstance(base_case_benchmarks, dict)
                            and isinstance(proposal_benchmarks, dict)
                            and benchmark_id in base_case_benchmarks
                            and benchmark_id in proposal_benchmarks
                            and _numeric_or_none(base_case_benchmarks.get(benchmark_id)) is not None
                            and _numeric_or_none(proposal_benchmarks.get(benchmark_id)) is not None
                        )
                        else None,
                    ),
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
            numeric_columns = ["Base Case", "Proposal", "Improvement (Base Case - Proposal)"]
            benchmark_styler = benchmark_df.style.format(
                {col: _benchmark_display_formatter for col in numeric_columns if col in benchmark_df.columns}
            )
            st.dataframe(benchmark_styler, width="stretch", hide_index=True)

    if isinstance(simulation_plot_html, str) and simulation_plot_html.strip():
        project_name = str(st.session_state.get("project_name", "") or "").strip()
        default_title = project_name if project_name else "Simulation Plan Output"
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in default_title).strip() or "simulation_output"
        st.session_state.setdefault("simulation_plot_save_title", default_title)
        st.session_state.setdefault("simulation_plot_save_description", "Please add notes for the HTML description.")
        pending_description = st.session_state.pop("simulation_plot_save_description_pending", None)
        if isinstance(pending_description, str) and pending_description.strip():
            st.session_state["simulation_plot_save_description"] = pending_description

        with st.expander("Simulation Interactive Plot", expanded=False):
            components.html(simulation_plot_html, height=850, scrolling=True)

        with st.expander("Result Export", expanded=False):
            st.text_input(
                "Title",
                key="simulation_plot_save_title",
                help="Used as the exported HTML document title. Defaults to project name.",
            )
            st.text_area(
                "Description",
                key="simulation_plot_save_description",
                height=120,
                help="Summary of improvements vs base case (editable).",
            )
            if st.button("Ask AI to generate description", key="simulation_plot_generate_description_button"):
                benchmark_context_payload = st.session_state.get("simulation_benchmark_context_json")
                generated_description = _ensure_agent_generated_save_description(
                    benchmark_context_payload=benchmark_context_payload,
                )
                if generated_description:
                    st.session_state["simulation_plot_save_description_pending"] = generated_description
                    st.success("Description generated.")
                    st.rerun()
                else:
                    st.warning("Could not generate description. Please run base/proposal simulations first.")
            st.caption("Generate the export file first, then download it.")
            html_title = str(st.session_state.get("simulation_plot_save_title", "") or default_title).strip() or default_title
            description = _format_export_description(
                str(st.session_state.get("simulation_plot_save_description", "") or "")
            )
            if st.button("Generate file to download", key="simulation_plot_generate_file_button", type="secondary"):
                if simulation_simulator is None and simulation_plot_layout is None:
                    st.error("No simulation plot context found. Run simulation again, then generate.")
                else:
                    try:
                        layout_to_save = (
                            build_simulation_plot_layout(
                                simulation_simulator,
                                title=html_title,
                                additional_description=description,
                            )
                            if simulation_simulator is not None
                            else simulation_plot_layout
                        )
                        generated_html = (
                            file_html(layout_to_save, CDN, html_title)
                            if layout_to_save is not None
                            else simulation_plot_html
                        )
                        st.session_state["simulation_plot_generated_html"] = generated_html
                        st.success("File generated. Click Download HTML.")
                    except Exception as exc:
                        st.error(f"Failed to generate export file: {exc}")
            generated_html = st.session_state.get("simulation_plot_generated_html")
            import pickle
            with open('test.bin', 'wb') as f:
                pickle.dump(st.session_state.get('simulation_plan_simulator'), f)
                
            if isinstance(generated_html, str) and generated_html.strip():
                st.download_button(
                    "Download HTML",
                    data=generated_html.encode("utf-8"),
                    file_name=f"{safe_title.replace(' ', '_')}.html",
                    mime="text/html",
                    key="simulation_plot_download_button",
                )
