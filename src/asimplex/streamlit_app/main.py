"""Barebone Streamlit UI shell for future chat agent work."""

from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st

from asimplex.agent.tools import apply_parameter_patch, propose_parameter_patch
from asimplex.llm_usage import record_llm_usage
from asimplex.persistence.session_store import create_version
from asimplex.streamlit_app.peak_shaving_table import render_peak_shaving_table
from asimplex.streamlit_app.power_profiles_plot import render_power_profiles_plot
from asimplex.streamlit_app.session_state import init_session_state
from asimplex.streamlit_app.sidebar import render_sidebar
from asimplex.streamlit_app.simulation_plan_section import (
    render_simulation_plan_section,
    run_simulation_plan_with_params,
)


def render_chat_shell() -> None:
    st.title("Chat")
    st.caption("Agent can propose scoped simulation tuning with reasoning.")
    st.session_state.setdefault("agent_chat_history", [])
    st.session_state.setdefault("agent_pending_proposal", None)

    history = st.session_state["agent_chat_history"]
    for msg in history:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("content", ""))

    user_message = st.chat_input("Ask the agent to tune grid_limit / evo_threshold / battery selection...")
    if user_message:
        history.append({"role": "user", "content": user_message})
        with st.chat_message("assistant"):
            with st.spinner("Agent is reasoning..."):
                try:
                    from asimplex.agent.runner import run_tuning_agent

                    agent_result = run_tuning_agent(user_message=user_message, session_state=st.session_state)
                    usage = agent_result.get("usage")
                    if isinstance(usage, dict):
                        record_llm_usage(
                            st.session_state,
                            label="Chat agent",
                            model_name=os.getenv("ASIMPLEX_AGENT_MODEL", "gpt-4.1-mini"),
                            input_tokens=usage.get("input_tokens"),
                            output_tokens=usage.get("output_tokens"),
                        )
                    reasoning = str(agent_result.get("reasoning", "")).strip()
                    proposed_params = agent_result.get("proposed_params", {})
                    next_step = str(agent_result.get("next_step", "insufficient_data"))
                    patch = agent_result.get("patch", {})
                    issues = agent_result.get("issues", [])
                    selected_battery = agent_result.get("selected_battery")

                    response_parts = []
                    if reasoning:
                        response_parts.append(reasoning)
                    if isinstance(proposed_params, dict) and proposed_params:
                        response_parts.append("Proposed changes:")
                        response_parts.append(f"```json\n{json.dumps(proposed_params, indent=2)}\n```")

                    assistant_text = "\n\n".join(response_parts) if response_parts else "No actionable proposal returned."
                    st.markdown(assistant_text)
                    history.append({"role": "assistant", "content": assistant_text})

                    if isinstance(proposed_params, dict) and proposed_params and next_step == "confirm":
                        st.session_state["agent_pending_proposal"] = {
                            "proposed_params": proposed_params,
                            "reasoning": reasoning,
                            "patch": patch if isinstance(patch, dict) else {},
                            "issues": issues if isinstance(issues, list) else [],
                            "selected_battery": selected_battery if isinstance(selected_battery, dict) else None,
                        }
                    else:
                        st.session_state["agent_pending_proposal"] = None
                except Exception as exc:  # pragma: no cover - depends on runtime/model config
                    err = f"Agent request failed: {exc}"
                    st.error(err)
                    history.append({"role": "assistant", "content": err})

    pending = st.session_state.get("agent_pending_proposal")
    if isinstance(pending, dict):
        proposed_params = pending.get("proposed_params", {})
        current_params = st.session_state.get("simulation_plan_params", {})
        patch = pending.get("patch", {})
        issues = pending.get("issues", [])
        selected_battery = pending.get("selected_battery")
        if not isinstance(patch, dict) or not isinstance(issues, list):
            patch_result = propose_parameter_patch(current_params, proposed_params if isinstance(proposed_params, dict) else {})
            patch = patch_result.get("patch", {})
            issues = patch_result.get("issues", [])
            selected_battery = patch_result.get("selected_battery")

        with st.container(border=True):
            st.markdown("**Pending parameter proposal**")
            reasoning = str(pending.get("reasoning", "")).strip()
            if reasoning:
                st.markdown(reasoning)
            if selected_battery:
                st.markdown("Selected battery from price list:")
                st.code(json.dumps(selected_battery, indent=2), language="json")

            if issues:
                st.error("Proposal contains disallowed or invalid updates.")
                st.caption(
                    "Expected nested payload under `application` and/or "
                    "`battery_selection`; dotted keys are invalid."
                )
                st.code(json.dumps({"issues": issues}, indent=2), language="json")
            else:
                st.markdown("Patch to apply:")
                st.code(json.dumps(patch, indent=2), language="json")

            c1, c2 = st.columns(2)
            if c1.button("Confirm apply + run", key="agent_confirm_apply_run", type="primary", disabled=bool(issues)):
                updated_params = apply_parameter_patch(current_params, patch)
                st.session_state["simulation_plan_params"] = updated_params
                project_name = str(st.session_state.get("project_name", "") or "")
                if project_name:
                    patch_keys = sorted(list((patch or {}).keys())) if isinstance(patch, dict) else []
                    create_version(
                        project_name=project_name,
                        source="agent_setting",
                        note=f"Agent confirmed update ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}): {', '.join(patch_keys)}",
                        params=updated_params if isinstance(updated_params, dict) else {},
                        patch=patch if isinstance(patch, dict) else {},
                    )
                with st.spinner("Applying changes and running simulation..."):
                    ok, msg = run_simulation_plan_with_params(updated_params)
                history.append({"role": "assistant", "content": msg})
                st.session_state["agent_pending_proposal"] = None
                st.rerun()

            if c2.button("Reject proposal", key="agent_reject_proposal"):
                history.append({"role": "assistant", "content": "Proposal rejected. No parameters were changed."})
                st.session_state["agent_pending_proposal"] = None
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="asimplex", page_icon=":speech_balloon:", layout="wide")
    init_session_state()
    st.sidebar.title("asimplex")
    st.sidebar.caption("Navigation")
    render_sidebar()
    render_power_profiles_plot()
    render_peak_shaving_table()
    render_simulation_plan_section()
    render_chat_shell()


if __name__ == "__main__":
    main()
