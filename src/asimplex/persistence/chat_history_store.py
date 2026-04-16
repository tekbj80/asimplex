"""LangChain-backed chat history persistence for project-scoped conversations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, trim_messages

from asimplex.constants import (
    AGENT_HISTORY_STRATEGY_LAST_MESSAGES,
    AGENT_HISTORY_STRATEGY_LAST_TURNS,
    AGENT_HISTORY_STRATEGY_SUMMARY,
    AGENT_HISTORY_STRATEGY_TOKEN_BUDGET,
    ASIMPLEX_AGENT_HISTORY_MAX_MESSAGES,
    ASIMPLEX_AGENT_HISTORY_MAX_TOKENS,
    ASIMPLEX_AGENT_HISTORY_MAX_TURNS,
    ASIMPLEX_AGENT_HISTORY_STRATEGY,
)
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


def _approximate_token_count(messages: list[BaseMessage] | BaseMessage) -> int:
    if isinstance(messages, BaseMessage):
        content = messages.content if isinstance(messages.content, str) else str(messages.content)
        return max(1, len(content) // 4)
    return sum(_approximate_token_count(msg) for msg in messages)


def _trim_last_turns(messages: list[BaseMessage], max_turns: int) -> list[BaseMessage]:
    if max_turns <= 0:
        return []
    selected: list[BaseMessage] = []
    turns_seen = 0
    waiting_for_user_boundary = False
    for msg in reversed(messages):
        selected.append(msg)
        if isinstance(msg, AIMessage):
            waiting_for_user_boundary = True
            continue
        if isinstance(msg, HumanMessage):
            if waiting_for_user_boundary:
                turns_seen += 1
                waiting_for_user_boundary = False
            else:
                turns_seen += 1
            if turns_seen >= max_turns:
                break
    return list(reversed(selected))


def _summarize_messages(messages: list[BaseMessage], kept_messages: list[BaseMessage]) -> list[BaseMessage]:
    kept_count = len(kept_messages)
    dropped_messages = messages[:-kept_count] if kept_count < len(messages) else []
    if not dropped_messages:
        return kept_messages
    summary_lines: list[str] = []
    for msg in dropped_messages:
        role = "assistant"
        if isinstance(msg, HumanMessage):
            role = "user"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        compact = " ".join(content.split())
        if compact:
            summary_lines.append(f"- {role}: {compact[:160]}")
    if not summary_lines:
        return kept_messages
    summary_message = SystemMessage(
        content="Summary of earlier chat context:\n" + "\n".join(summary_lines[-8:])
    )
    return [summary_message, *kept_messages]


def _trim_token_budget(messages: list[BaseMessage], max_tokens: int) -> list[BaseMessage]:
    if max_tokens <= 0:
        return []
    kept: list[BaseMessage] = []
    used_tokens = 0
    for msg in reversed(messages):
        msg_tokens = _approximate_token_count(msg)
        if msg_tokens > max_tokens:
            continue
        if used_tokens + msg_tokens > max_tokens:
            break
        kept.append(msg)
        used_tokens += msg_tokens
    return list(reversed(kept))


def trim_for_context(
    messages: list[BaseMessage],
    *,
    strategy: str = ASIMPLEX_AGENT_HISTORY_STRATEGY,
    max_messages: int = ASIMPLEX_AGENT_HISTORY_MAX_MESSAGES,
    max_turns: int = ASIMPLEX_AGENT_HISTORY_MAX_TURNS,
    max_tokens: int = ASIMPLEX_AGENT_HISTORY_MAX_TOKENS,
) -> list[BaseMessage]:
    if not messages:
        return []
    if strategy == AGENT_HISTORY_STRATEGY_LAST_TURNS:
        return _trim_last_turns(messages, max_turns=max_turns)
    if strategy == AGENT_HISTORY_STRATEGY_TOKEN_BUDGET:
        return _trim_token_budget(messages, max_tokens=max_tokens)
    if strategy == AGENT_HISTORY_STRATEGY_SUMMARY:
        kept_messages = _trim_last_turns(messages, max_turns=max_turns)
        return _summarize_messages(messages, kept_messages)
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
