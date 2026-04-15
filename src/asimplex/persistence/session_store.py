"""SQLite-backed project/session registry for Streamlit sessions."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[3] / ".asimplex_sessions.db"


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                session_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                version_no INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                note TEXT,
                params_json TEXT NOT NULL,
                patch_json TEXT,
                FOREIGN KEY(session_id) REFERENCES projects(session_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_snapshots (
                session_id TEXT NOT NULL,
                profile_type TEXT NOT NULL,
                filename TEXT,
                series_json TEXT NOT NULL,
                description_json TEXT,
                parse_attempts_json TEXT,
                metadata_json TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(session_id, profile_type),
                FOREIGN KEY(session_id) REFERENCES projects(session_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tariff_snapshots (
                session_id TEXT PRIMARY KEY,
                filename TEXT,
                selected_voltage_level TEXT,
                extracted_tariff_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES projects(session_id)
            )
            """
        )
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(profile_snapshots)").fetchall()}
        if "metadata_json" not in existing_cols:
            conn.execute("ALTER TABLE profile_snapshots ADD COLUMN metadata_json TEXT")
        conn.commit()


def normalize_project_name_to_session_id(project_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", project_name.strip().lower())
    return normalized.strip("-")


def list_project_session_ids() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT session_id FROM projects ORDER BY session_id").fetchall()
    return [str(row[0]) for row in rows]


def project_exists(session_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM projects WHERE session_id = ? LIMIT 1", (session_id,)).fetchone()
    return row is not None


def create_project(session_id: str, project_name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO projects(session_id, project_name) VALUES(?, ?)",
            (session_id, project_name.strip()),
        )
        conn.commit()


def get_project_name(session_id: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT project_name FROM projects WHERE session_id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row[0]) if row[0] is not None else None


def profile_snapshot_exists(session_id: str, profile_type: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM profile_snapshots WHERE session_id = ? AND profile_type = ? LIMIT 1",
            (session_id, profile_type),
        ).fetchone()
    return row is not None


def save_profile_snapshot(
    *,
    session_id: str,
    profile_type: str,
    filename: str | None,
    series: list[Any] | None,
    description: Any,
    parse_attempts: list[str] | None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Insert/update one profile snapshot per (session_id, profile_type).

    Returns True if an existing snapshot was overwritten.
    """
    overwritten = profile_snapshot_exists(session_id, profile_type)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO profile_snapshots(
                session_id, profile_type, filename, series_json, description_json, parse_attempts_json, metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, profile_type) DO UPDATE SET
                filename = excluded.filename,
                series_json = excluded.series_json,
                description_json = excluded.description_json,
                parse_attempts_json = excluded.parse_attempts_json,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                profile_type,
                filename or "",
                json.dumps(series if isinstance(series, list) else []),
                json.dumps(description),
                json.dumps(parse_attempts if isinstance(parse_attempts, list) else []),
                json.dumps(metadata if isinstance(metadata, dict) else {}),
            ),
        )
        conn.commit()
    return overwritten


def get_profile_snapshot(session_id: str, profile_type: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT filename, series_json, description_json, parse_attempts_json, updated_at
            , metadata_json
            FROM profile_snapshots
            WHERE session_id = ? AND profile_type = ?
            LIMIT 1
            """,
            (session_id, profile_type),
        ).fetchone()
    if row is None:
        return None
    return {
        "filename": str(row[0] or ""),
        "series": json.loads(row[1]) if row[1] else [],
        "description": json.loads(row[2]) if row[2] else None,
        "parse_attempts": json.loads(row[3]) if row[3] else [],
        "updated_at": str(row[4] or ""),
        "metadata": json.loads(row[5]) if row[5] else {},
    }


def save_tariff_snapshot(
    *,
    session_id: str,
    filename: str | None,
    selected_voltage_level: str | None,
    extracted_tariff: dict[str, Any] | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tariff_snapshots(session_id, filename, selected_voltage_level, extracted_tariff_json)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                filename = excluded.filename,
                selected_voltage_level = excluded.selected_voltage_level,
                extracted_tariff_json = excluded.extracted_tariff_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                filename or "",
                selected_voltage_level or "",
                json.dumps(extracted_tariff if isinstance(extracted_tariff, dict) else {}),
            ),
        )
        conn.commit()


def get_tariff_snapshot(session_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT filename, selected_voltage_level, extracted_tariff_json, updated_at
            FROM tariff_snapshots
            WHERE session_id = ?
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "filename": str(row[0] or ""),
        "selected_voltage_level": str(row[1] or ""),
        "extracted_tariff": json.loads(row[2]) if row[2] else {},
        "updated_at": str(row[3] or ""),
    }

