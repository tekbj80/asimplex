"""Log viewer section for structured app events."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from asimplex.observability.app_log_store import list_events


def render_log_viewer_section() -> None:
    st.subheader("Application Logs")
    st.caption("Structured app events captured in the local SQLite log store.")

    project_name = str(st.session_state.get("project_name", "") or "").strip()
    c1, c2 = st.columns([1, 1])
    with c1:
        scope = st.selectbox(
            "Scope",
            options=["Active project only", "All projects"],
            index=0 if project_name else 1,
            key="log_view_scope",
        )
    with c2:
        limit = st.selectbox("Max rows", options=[50, 100, 250, 500], index=1, key="log_view_limit")

    selected_project = project_name if scope == "Active project only" and project_name else None
    events = list_events(project_name=selected_project, limit=int(limit))
    if not events:
        st.info("No log events found for the selected scope.")
        return

    statuses = sorted({str(e.get("status", "") or "") for e in events if str(e.get("status", "") or "").strip()})
    selected_statuses = st.multiselect(
        "Filter status",
        options=statuses,
        default=statuses,
        key="log_view_status_filter",
    )
    filtered_events = [
        e for e in events if not selected_statuses or str(e.get("status", "") or "") in set(selected_statuses)
    ]

    st.caption(f"Showing {len(filtered_events)} of {len(events)} events.")
    if not filtered_events:
        st.info("No events match the selected status filter.")
        return

    rows: list[dict[str, object]] = []
    for event in filtered_events:
        tools = event.get("tool_invocations")
        payload = event.get("payload")
        rows.append(
            {
                "created_at": event.get("created_at", ""),
                "project_name": event.get("project_name", ""),
                "source": event.get("source", ""),
                "event_type": event.get("event_type", ""),
                "status": event.get("status", ""),
                "message": event.get("message", ""),
                "tool_count": len(tools) if isinstance(tools, list) else 0,
                "error": event.get("error", ""),
                "payload": json.dumps(payload, ensure_ascii=True) if isinstance(payload, dict) else "",
            }
        )

    st.dataframe(pd.DataFrame(rows), width="stretch", height=360, hide_index=True)
    with st.expander("Raw events JSON", expanded=False):
        st.code(json.dumps(filtered_events, indent=2), language="json")
