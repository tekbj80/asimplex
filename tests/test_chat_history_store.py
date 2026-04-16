"""Tests for LangChain-backed chat history persistence."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from asimplex.constants import (
    AGENT_HISTORY_STRATEGY_LAST_MESSAGES,
    AGENT_HISTORY_STRATEGY_LAST_TURNS,
    AGENT_HISTORY_STRATEGY_SUMMARY,
    AGENT_HISTORY_STRATEGY_TOKEN_BUDGET,
)
from asimplex.persistence import chat_history_store


def test_append_and_list_messages_for_ui(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_chat_history.db"
    monkeypatch.setattr(chat_history_store, "DB_PATH", test_db)

    chat_history_store.append_exchange(
        project_name="proj-chat",
        user_message="hello",
        assistant_message="hi there",
    )

    rows = chat_history_store.list_messages_for_ui("proj-chat")
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "hello"
    assert rows[1]["role"] == "assistant"
    assert rows[1]["content"] == "hi there"


def test_thread_isolation_and_clear(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_chat_history_threads.db"
    monkeypatch.setattr(chat_history_store, "DB_PATH", test_db)

    chat_history_store.append_exchange(
        project_name="proj-chat",
        thread_id="tuning_chat",
        user_message="u1",
        assistant_message="a1",
    )
    chat_history_store.append_exchange(
        project_name="proj-chat",
        thread_id="other_thread",
        user_message="u2",
        assistant_message="a2",
    )

    default_rows = chat_history_store.list_messages_for_ui("proj-chat", thread_id="tuning_chat")
    other_rows = chat_history_store.list_messages_for_ui("proj-chat", thread_id="other_thread")
    assert [x["content"] for x in default_rows] == ["u1", "a1"]
    assert [x["content"] for x in other_rows] == ["u2", "a2"]

    chat_history_store.clear_messages("proj-chat", thread_id="other_thread")
    assert chat_history_store.list_messages_for_ui("proj-chat", thread_id="other_thread") == []
    assert [x["content"] for x in chat_history_store.list_messages_for_ui("proj-chat", thread_id="tuning_chat")] == [
        "u1",
        "a1",
    ]


def test_trim_for_context_last_messages() -> None:
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="a1"),
        HumanMessage(content="u2"),
        AIMessage(content="a2"),
    ]
    trimmed = chat_history_store.trim_for_context(
        messages,
        strategy=AGENT_HISTORY_STRATEGY_LAST_MESSAGES,
        max_messages=2,
    )
    assert [str(msg.content) for msg in trimmed] == ["u2", "a2"]


def test_trim_for_context_last_turns() -> None:
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="a1"),
        HumanMessage(content="u2"),
        AIMessage(content="a2"),
        HumanMessage(content="u3"),
        AIMessage(content="a3"),
    ]
    trimmed = chat_history_store.trim_for_context(
        messages,
        strategy=AGENT_HISTORY_STRATEGY_LAST_TURNS,
        max_turns=2,
    )
    assert [str(msg.content) for msg in trimmed] == ["u2", "a2", "u3", "a3"]


def test_trim_for_context_token_budget() -> None:
    messages = [
        HumanMessage(content="tiny"),
        AIMessage(content="small reply"),
        HumanMessage(content="x" * 800),
    ]
    trimmed = chat_history_store.trim_for_context(
        messages,
        strategy=AGENT_HISTORY_STRATEGY_TOKEN_BUDGET,
        max_tokens=50,
    )
    assert [str(msg.content) for msg in trimmed] == ["tiny", "small reply"]


def test_trim_for_context_summary() -> None:
    messages = [
        HumanMessage(content="first question"),
        AIMessage(content="first answer"),
        HumanMessage(content="second question"),
        AIMessage(content="second answer"),
    ]
    trimmed = chat_history_store.trim_for_context(
        messages,
        strategy=AGENT_HISTORY_STRATEGY_SUMMARY,
        max_turns=1,
    )
    assert isinstance(trimmed[0], SystemMessage)
    assert "Summary of earlier chat context" in str(trimmed[0].content)
    assert [str(msg.content) for msg in trimmed[1:]] == ["second question", "second answer"]
