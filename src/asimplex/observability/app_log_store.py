"""Structured application event logging to a separate SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[3] / ".asimplex_app_logs.db"


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                tool_invocations_json TEXT,
                message TEXT,
                error TEXT,
                payload_json TEXT
            )
            """
        )
        conn.commit()


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {})
    except Exception:
        return json.dumps({"_serialization_error": True, "repr": repr(value)})


def log_event(
    *,
    project_name: str | None,
    source: str,
    event_type: str,
    status: str,
    tool_invocations: list[dict[str, Any]] | None = None,
    message: str | None = None,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO app_events(
                project_name, source, event_type, status, tool_invocations_json, message, error, payload_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (project_name or "").strip() or None,
                (source or "").strip() or "unknown",
                (event_type or "").strip() or "unknown",
                (status or "").strip() or "unknown",
                _safe_json_dumps(tool_invocations if isinstance(tool_invocations, list) else []),
                (message or "").strip(),
                (error or "").strip(),
                _safe_json_dumps(payload if isinstance(payload, dict) else {}),
            ),
        )
        conn.commit()


def list_events(project_name: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        if project_name:
            rows = conn.execute(
                """
                SELECT project_name, created_at, source, event_type, status, tool_invocations_json, message, error, payload_json
                FROM app_events
                WHERE project_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_name.strip(), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT project_name, created_at, source, event_type, status, tool_invocations_json, message, error, payload_json
                FROM app_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    out: list[dict[str, Any]] = []
    for project, created_at, source, event_type, status, tool_json, message, error, payload_json in rows:
        out.append(
            {
                "project_name": str(project or ""),
                "created_at": str(created_at or ""),
                "source": str(source or ""),
                "event_type": str(event_type or ""),
                "status": str(status or ""),
                "tool_invocations": json.loads(tool_json) if tool_json else [],
                "message": str(message or ""),
                "error": str(error or ""),
                "payload": json.loads(payload_json) if payload_json else {},
            }
        )
    return out
