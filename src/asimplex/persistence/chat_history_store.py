"""LangChain-backed chat history persistence for project-scoped conversations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, trim_messages

from asimplex.persistence.session_store import DB_PATH

DEFAULT_THREAD_ID = "tuning_chat"


def _connection_string() -> str:
    db_path = Path(DB_PATH).resolve()
    return f"sqlite:///{db_path.as_posix()}"


def _session_id(project_name: str, thread_id: str = DEFAULT_THREAD_ID) -> str:
    return f"{project_name.strip()}:{thread_id.strip() or DEFAULT_THREAD_ID}"


def _new_history(project_name: str, thread_id: str = DEFAULT_THREAD_ID):
    from langchain_community.chat_message_histories import SQLChatMessageHistory

    return SQLChatMessageHistory(
        session_id=_session_id(project_name, thread_id),
        connection=_connection_string(),
        table_name="message_store",
    )


def list_messages(project_name: str, thread_id: str = DEFAULT_THREAD_ID) -> list[BaseMessage]:
    project = str(project_name or "").strip()
    if not project:
        return []
    return list(_new_history(project, thread_id).messages)


def append_exchange(project_name: str, user_message: str, assistant_message: str, thread_id: str = DEFAULT_THREAD_ID) -> None:
    project = str(project_name or "").strip()
    if not project:
        return
    history = _new_history(project, thread_id)
    history.add_message(HumanMessage(content=str(user_message or "")))
    history.add_message(AIMessage(content=str(assistant_message or "")))


def clear_messages(project_name: str, thread_id: str = DEFAULT_THREAD_ID) -> None:
    project = str(project_name or "").strip()
    if not project:
        return
    _new_history(project, thread_id).clear()


def trim_for_context(messages: list[BaseMessage], max_messages: int = 12) -> list[BaseMessage]:
    if max_messages <= 0:
        return []
    return trim_messages(
        messages,
        max_tokens=int(max_messages),
        token_counter=len,
        strategy="last",
        include_system=True,
    )


def list_messages_for_ui(project_name: str, thread_id: str = DEFAULT_THREAD_ID) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in list_messages(project_name, thread_id):
        role = "assistant"
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        out.append({"role": role, "content": content})
    return out
