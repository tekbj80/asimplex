"""Sidebar container for app sections."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.streamlit_app.electrical_tariff_section import render_electrical_tariff_section
from asimplex.streamlit_app.load_profile_section import render_load_profile_section
from asimplex.streamlit_app.pv_profile_section import render_pv_profile_section


def render_token_usage_table() -> None:
    """Render a fixed-height, scrollable token/cost usage table in sidebar."""
    raw = st.session_state.get("llm_usage")
    u = raw if isinstance(raw, dict) else {}
    total_in = int(u.get("total_input", 0) or 0)
    total_out = int(u.get("total_output", 0) or 0)
    total_cost = float(u.get("total_cost_eur", 0.0) or 0.0)
    rows = u.get("rows", [])
    rows_df = pd.DataFrame(rows if isinstance(rows, list) else [])
    if rows_df.empty:
        rows_df = pd.DataFrame(
            columns=["time", "action", "model", "ingest_tokens", "output_tokens", "total_tokens", "cost_eur"]
        )
    sum_row = {
        "time": "",
        "action": "SUM",
        "model": "",
        "ingest_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cost_eur": total_cost,
    }
    rows_df = pd.concat([rows_df, pd.DataFrame([sum_row])], ignore_index=True)
    if "cost_eur" in rows_df.columns:
        rows_df["cost_eur"] = pd.to_numeric(rows_df["cost_eur"], errors="coerce").fillna(0.0).map(
            lambda x: f"EUR {x:.6f}"
        )
    with st.sidebar.expander("LLM usage", expanded=False):
        st.dataframe(
            rows_df,
            width="stretch",
            height=220,
            hide_index=True,
        )


def render_sidebar() -> None:
    render_load_profile_section()
    render_pv_profile_section()
    render_electrical_tariff_section()
    render_token_usage_table()
