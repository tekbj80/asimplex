"""Sidebar container for app sections."""

from __future__ import annotations

import streamlit as st

from asimplex.streamlit_app.electrical_tariff_section import render_electrical_tariff_section
from asimplex.streamlit_app.load_profile_section import render_load_profile_section
from asimplex.streamlit_app.pv_profile_section import render_pv_profile_section


def render_sidebar() -> None:
    st.sidebar.title("asimplex")
    st.sidebar.caption("Navigation")
    st.sidebar.button("New chat", width="stretch", disabled=True)
    st.sidebar.divider()
    render_load_profile_section()
    render_pv_profile_section()
    render_electrical_tariff_section()
