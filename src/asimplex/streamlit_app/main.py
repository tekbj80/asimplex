"""Barebone Streamlit UI shell for future chat agent work."""

from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st

from asimplex.agent.tools import apply_parameter_patch, propose_parameter_patch
from asimplex.constants import CHAT_AGENT_STR_FOR_DISPLAY, CHAT_AGENT_STR_FOR_LOGGING
from asimplex.llm_usage import record_llm_usage
from asimplex.observability.app_log_store import log_event
from asimplex.persistence.chat_history_store import append_exchange, list_messages_for_ui
from asimplex.persistence.session_store import append_llm_usage_event, create_version
from asimplex.streamlit_app.log_viewer_section import render_log_viewer_section
from asimplex.streamlit_app.load_profile_section import render_load_profile_section
from asimplex.streamlit_app.peak_shaving_table import render_peak_shaving_table
from asimplex.streamlit_app.power_profiles_plot import render_power_profiles_plot
from asimplex.streamlit_app.pv_profile_section import render_pv_profile_section
from asimplex.streamlit_app.rate_limit import check_llm_usage_window_limit
from asimplex.streamlit_app.session_state import init_session_state
from asimplex.streamlit_app.sidebar import render_sidebar
from asimplex.streamlit_app.simulation_plan_section import (
    render_simulation_plan_section,
    run_simulation_plan_with_params,
)
from asimplex.streamlit_app.simulation_results_section import (
    render_base_case_section,
    render_simulation_results_section,
)


def _format_rag_sources_markdown(rag_hits: list[dict[str, object]]) -> str:
    if not rag_hits:
        return ""
    lines = ["Sources:"]
    for hit in rag_hits:
        source_name = str(hit.get("source_name", "") or "unknown")
        collection_name = str(hit.get("collection_name", "") or "unknown_collection")
        chunk_id = int(hit.get("chunk_id", -1) or -1)
        content = " ".join(str(hit.get("content", "") or "").split())
        snippet = content[:280] + ("..." if len(content) > 280 else "")
        lines.append(f"- {source_name} ({collection_name}, chunk {chunk_id})")
        if snippet:
            lines.append(f"  - \"{snippet}\"")
    return "\n".join(lines)


def _render_rag_sources(rag_hits: list[dict[str, object]]) -> None:
    # Sources are kept inline inside assistant text to avoid duplicated UI sections.
    return


def render_chat_shell() -> None:
    st.title("Chat")
    st.caption("Agent can propose scoped simulation tuning with reasoning.")
    st.session_state.setdefault("agent_chat_history", [])
    st.session_state.setdefault("agent_chat_history_project", "")
    st.session_state.setdefault("agent_pending_proposal", None)
    active_project_name = str(st.session_state.get("project_name", "") or "").strip()
    loaded_project_name = str(st.session_state.get("agent_chat_history_project", "") or "").strip()
    if active_project_name != loaded_project_name:
        st.session_state["agent_chat_history"] = list_messages_for_ui(active_project_name) if active_project_name else []
        st.session_state["agent_chat_history_project"] = active_project_name

    history = st.session_state["agent_chat_history"]
    for msg in history:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("content", ""))

    pending = st.session_state.get("agent_pending_proposal")
    if isinstance(pending, dict):
        proposed_params = pending.get("proposed_params", {})
        current_params = st.session_state.get("simulation_plan_params", {})
        patch = pending.get("patch", {})
        issues = pending.get("issues", [])
        selected_battery = pending.get("selected_battery")
        pending_rag_hits_raw = pending.get("rag_context_hits")
        pending_rag_hits = pending_rag_hits_raw if isinstance(pending_rag_hits_raw, list) else []
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
            _render_rag_sources([hit for hit in pending_rag_hits if isinstance(hit, dict)])

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
                log_event(
                    project_name=project_name,
                    source=CHAT_AGENT_STR_FOR_LOGGING,
                    event_type="agent_apply_patch",
                    status="success",
                    message="Confirmed agent proposal and applied parameter patch.",
                    payload={"patch_keys": sorted(list(patch.keys())) if isinstance(patch, dict) else []},
                )
                with st.spinner("Applying changes and running simulation..."):
                    ok, msg = run_simulation_plan_with_params(updated_params)
                sources_markdown = _format_rag_sources_markdown(
                    [hit for hit in pending_rag_hits if isinstance(hit, dict)][:3]
                )
                confirm_response_parts = [msg]
                if sources_markdown:
                    confirm_response_parts.append(sources_markdown)
                history.append({"role": "assistant", "content": "\n\n".join(confirm_response_parts)})
                st.session_state["agent_pending_proposal"] = None
                st.rerun()

            if c2.button("Reject proposal", key="agent_reject_proposal"):
                history.append({"role": "assistant", "content": "Proposal rejected. No parameters were changed."})
                st.session_state["agent_pending_proposal"] = None
                st.rerun()

    user_message = st.chat_input("Ask the agent to tune grid_limit / evo_threshold / battery selection...")
    if user_message:
        history.append({"role": "user", "content": user_message})
        chat_limit = int(st.session_state.get("chat_requests_per_minute", 12) or 0)
        allowed, retry_after = check_llm_usage_window_limit(
            st.session_state,
            action_label=CHAT_AGENT_STR_FOR_DISPLAY,
            max_requests=chat_limit,
            window_seconds=60,
        )
        if not allowed:
            blocked_msg = (
                "Rate limit reached for chat requests. "
                f"Please wait {retry_after}s and try again."
            )
            history.append({"role": "assistant", "content": blocked_msg})
            if active_project_name:
                append_exchange(
                    project_name=active_project_name,
                    user_message=user_message,
                    assistant_message=blocked_msg,
                )
            log_event(
                project_name=str(st.session_state.get("project_name", "") or ""),
                source=CHAT_AGENT_STR_FOR_LOGGING,
                event_type="rate_limit",
                status="blocked",
                message="Chat request blocked by rate limit.",
                payload={"retry_after_seconds": retry_after, "chat_requests_per_minute": chat_limit},
            )
            st.rerun()

        with st.spinner("Agent is reasoning..."):
            try:
                from asimplex.agent.runner import run_tuning_agent

                agent_result = run_tuning_agent(user_message=user_message, session_state=st.session_state)
                usage = agent_result.get("usage")
                tool_invocations = (
                    agent_result.get("tool_invocations")
                    if isinstance(agent_result.get("tool_invocations"), list)
                    else []
                )
                if isinstance(usage, dict):
                    row = record_llm_usage(
                        st.session_state,
                        label=CHAT_AGENT_STR_FOR_DISPLAY,
                        model_name=os.getenv("ASIMPLEX_AGENT_MODEL", "gpt-4.1-mini"),
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                    )
                    project_name = str(st.session_state.get("project_name", "") or "")
                    if project_name:
                        append_llm_usage_event(project_name, row)
                reasoning = str(agent_result.get("reasoning", "")).strip()
                proposed_params = agent_result.get("proposed_params", {})
                next_step = str(agent_result.get("next_step", "insufficient_data"))
                patch = agent_result.get("patch", {})
                issues = agent_result.get("issues", [])
                selected_battery = agent_result.get("selected_battery")
                rag_hits_raw = agent_result.get("rag_context_hits")
                rag_hits = rag_hits_raw if isinstance(rag_hits_raw, list) else []
                log_event(
                    project_name=str(st.session_state.get("project_name", "") or ""),
                    source=CHAT_AGENT_STR_FOR_LOGGING,
                    event_type="agent_turn",
                    status="success",
                    tool_invocations=tool_invocations,
                    message="Agent response generated.",
                    payload={"next_step": next_step},
                )

                response_parts = []
                if reasoning:
                    response_parts.append(reasoning)
                if isinstance(proposed_params, dict) and proposed_params:
                    response_parts.append("Proposed changes:")
                    response_parts.append(f"```json\n{json.dumps(proposed_params, indent=2)}\n```")
                sources_markdown = _format_rag_sources_markdown(
                    [hit for hit in rag_hits if isinstance(hit, dict)][:3]
                )
                if sources_markdown:
                    response_parts.append(sources_markdown)

                assistant_text = "\n\n".join(response_parts) if response_parts else "No actionable proposal returned."
                history.append({"role": "assistant", "content": assistant_text})
                if active_project_name:
                    append_exchange(
                        project_name=active_project_name,
                        user_message=user_message,
                        assistant_message=assistant_text,
                    )

                if isinstance(proposed_params, dict) and proposed_params and next_step == "confirm":
                    st.session_state["agent_pending_proposal"] = {
                        "proposed_params": proposed_params,
                        "reasoning": reasoning,
                        "patch": patch if isinstance(patch, dict) else {},
                        "issues": issues if isinstance(issues, list) else [],
                        "selected_battery": selected_battery if isinstance(selected_battery, dict) else None,
                        "rag_context_hits": [hit for hit in rag_hits if isinstance(hit, dict)][:5],
                    }
                else:
                    st.session_state["agent_pending_proposal"] = None
                st.rerun()
            except Exception as exc:  # pragma: no cover - depends on runtime/model config
                err = f"Agent request failed: {exc}"
                history.append({"role": "assistant", "content": err})
                if active_project_name:
                    append_exchange(
                        project_name=active_project_name,
                        user_message=user_message,
                        assistant_message=err,
                    )
                log_event(
                    project_name=str(st.session_state.get("project_name", "") or ""),
                    source=CHAT_AGENT_STR_FOR_LOGGING,
                    event_type="agent_turn",
                    status="error",
                    error=str(exc),
                    message="Agent request failed.",
                )
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="asimplex", page_icon=":speech_balloon:", layout="wide")
    st.sidebar.image("c:/Users/el_Boon/reference/Portfolio/logo.png", width=100)
    init_session_state()
    st.sidebar.title("asimplex")
    st.sidebar.markdown(
        "AI-Assisted Simulation for Simplifying Complexity<br>"
        "Part of the IDEAS project:<br>"
        "<b>I</b>ntegrated <b>D</b>ata-Driven <b>E</b>nergy <b>A</b>nalytics and <b>S</b>izing",
    unsafe_allow_html=True,
)
    render_sidebar()
    profiles_tab, simulations_tab, chat_tab, logs_tab = st.tabs(["Profiles", "Simulations", "Chat", "Logs"])
    with profiles_tab:
        render_load_profile_section()
        render_pv_profile_section()
        render_base_case_section()
        render_power_profiles_plot()
        render_peak_shaving_table()
    with simulations_tab:
        render_simulation_plan_section()
        render_simulation_results_section()
    with chat_tab:
        render_chat_shell()
    with logs_tab:
        render_log_viewer_section()


if __name__ == "__main__":
    main()
