"""Sidebar LLM dashboard (history strategy, rate limits, usage table)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.constants import (
    AGENT_HISTORY_STRATEGIES,
    AGENT_HISTORY_STRATEGY_LAST_MESSAGES,
    AGENT_HISTORY_STRATEGY_LAST_TURNS,
    AGENT_HISTORY_STRATEGY_SUMMARY,
    AGENT_HISTORY_STRATEGY_TOKEN_BUDGET,
)


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
        st.markdown("**Chat history context**")
        strategy_labels = {
            AGENT_HISTORY_STRATEGY_LAST_MESSAGES: "Last messages",
            AGENT_HISTORY_STRATEGY_LAST_TURNS: "Last turns",
            AGENT_HISTORY_STRATEGY_TOKEN_BUDGET: "Token budget",
            AGENT_HISTORY_STRATEGY_SUMMARY: "Summary + recent turns",
        }
        current_strategy = str(st.session_state.get("agent_history_strategy", AGENT_HISTORY_STRATEGY_LAST_MESSAGES))
        st.selectbox(
            "History strategy",
            options=AGENT_HISTORY_STRATEGIES,
            index=AGENT_HISTORY_STRATEGIES.index(current_strategy) if current_strategy in AGENT_HISTORY_STRATEGIES else 0,
            format_func=lambda x: strategy_labels.get(x, x),
            key="agent_history_strategy",
            help="Controls how much stored chat history is sent to the agent on each turn.",
        )
        st.slider(
            "Max messages",
            min_value=2,
            max_value=40,
            value=int(st.session_state.get("agent_history_max_messages", 12) or 12),
            step=1,
            key="agent_history_max_messages",
            disabled=st.session_state.get("agent_history_strategy") != AGENT_HISTORY_STRATEGY_LAST_MESSAGES,
        )
        st.slider(
            "Max turns",
            min_value=1,
            max_value=12,
            value=int(st.session_state.get("agent_history_max_turns", 4) or 4),
            step=1,
            key="agent_history_max_turns",
            disabled=st.session_state.get("agent_history_strategy")
            not in {AGENT_HISTORY_STRATEGY_LAST_TURNS, AGENT_HISTORY_STRATEGY_SUMMARY},
        )
        st.slider(
            "Max tokens",
            min_value=250,
            max_value=8000,
            value=int(st.session_state.get("agent_history_max_tokens", 2000) or 2000),
            step=250,
            key="agent_history_max_tokens",
            disabled=st.session_state.get("agent_history_strategy") != AGENT_HISTORY_STRATEGY_TOKEN_BUDGET,
        )
        if st.session_state.get("agent_history_strategy") == AGENT_HISTORY_STRATEGY_SUMMARY:
            st.caption("Older messages are compressed into a short system summary while recent turns stay verbatim.")

        st.divider()
        st.markdown("**Rate limits**")
        st.number_input(
            "Tariff cooldown (seconds)",
            min_value=0,
            max_value=600,
            step=5,
            key="tariff_cooldown_seconds",
            help="Minimum wait time between tariff extraction attempts in this session.",
        )
        st.number_input(
            "Chat requests per minute",
            min_value=0,
            max_value=240,
            step=1,
            key="chat_requests_per_minute",
            help="Maximum chat-agent requests allowed per minute in this session.",
        )
        st.caption(
            "Setting either value to 0 disables that limiter for the current session."
        )

        st.divider()
        st.markdown("**LLM usage**")
        st.dataframe(
            rows_df,
            width="stretch",
            height=220,
            hide_index=True,
        )
