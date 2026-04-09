"""Barebone Streamlit UI shell for future chat agent work."""

from __future__ import annotations

import streamlit as st

from asimplex.streamlit_app.load_profile_section import init_session_state
from asimplex.streamlit_app.peak_shaving_table import render_peak_shaving_table
from asimplex.streamlit_app.power_profiles_plot import render_power_profiles_plot
from asimplex.streamlit_app.sidebar import render_sidebar


def render_chat_shell() -> None:
    st.title("Chat")
    st.caption("Barebone layout only - no logic wired yet.")
    st.container(border=True).markdown("Assistant responses will appear here.")
    st.chat_input("Type a message...", disabled=True)


def main() -> None:
    st.set_page_config(page_title="asimplex", page_icon=":speech_balloon:", layout="wide")
    init_session_state()
    render_sidebar()
    render_power_profiles_plot()
    render_peak_shaving_table()
    render_chat_shell()


if __name__ == "__main__":
    main()
