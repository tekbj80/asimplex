"""Barebone Streamlit UI shell for future chat agent work."""

from __future__ import annotations

import streamlit as st


def render_sidebar() -> None:
    st.sidebar.title("asimplex")
    st.sidebar.caption("Navigation")
    st.sidebar.button("New chat", use_container_width=True, disabled=True)
    st.sidebar.divider()
    st.sidebar.markdown("### Chats")
    st.sidebar.markdown("- Chat 1")
    st.sidebar.markdown("- Chat 2")
    st.sidebar.markdown("- Chat 3")


def render_chat_shell() -> None:
    st.title("Chat")
    st.caption("Barebone layout only - no logic wired yet.")
    st.container(border=True).markdown("Assistant responses will appear here.")
    st.chat_input("Type a message...", disabled=True)


def main() -> None:
    st.set_page_config(page_title="asimplex", page_icon=":speech_balloon:", layout="wide")
    render_sidebar()
    render_chat_shell()


if __name__ == "__main__":
    main()
