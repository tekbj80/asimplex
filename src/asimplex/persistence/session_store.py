"""SQLite-backed project/version registry keyed by project name."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DB_PATH = Path(__file__).resolve().parents[3] / ".asimplex_sessions.db"


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _sqlite_utc_to_berlin(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt_utc = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return raw


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
                reason_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                model TEXT NOT NULL,
                ingest_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost_eur REAL NOT NULL,
                meta_json TEXT,
                FOREIGN KEY(project_name) REFERENCES projects(session_id)
            )
            """
        )
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(profile_snapshots)").fetchall()}
        if "metadata_json" not in existing_cols:
            conn.execute("ALTER TABLE profile_snapshots ADD COLUMN metadata_json TEXT")
        if "reason_text" not in existing_cols:
            conn.execute("ALTER TABLE profile_snapshots ADD COLUMN reason_text TEXT")
        if "created_at" not in existing_cols:
            # SQLite ALTER TABLE does not allow non-constant defaults on some versions.
            conn.execute("ALTER TABLE profile_snapshots ADD COLUMN created_at TEXT")
            conn.execute(
                "UPDATE profile_snapshots SET created_at = CURRENT_TIMESTAMP "
                "WHERE created_at IS NULL OR created_at = ''"
            )
        conn.commit()


def normalize_project_name(project_name: str) -> str:
    return str(project_name or "").strip()


def list_project_names() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT project_name FROM projects ORDER BY project_name").fetchall()
    return [str(row[0]) for row in rows]


def project_exists(project_name: str) -> bool:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM projects WHERE project_name = ? LIMIT 1", (normalized_name,)).fetchone()
    return row is not None


def create_project(project_name: str) -> None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO projects(session_id, project_name) VALUES(?, ?)",
            (normalized_name, normalized_name),
        )
        conn.commit()


def upsert_project(project_name: str) -> None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects(session_id, project_name)
            VALUES(?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                project_name = excluded.project_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (normalized_name, normalized_name),
        )
        conn.commit()


def get_next_version_no(project_name: str) -> int:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(version_no) FROM simulation_versions WHERE session_id = ?",
            (normalized_name,),
        ).fetchone()
    max_version = row[0] if row is not None else None
    return int(max_version) + 1 if max_version is not None else 0


def create_version(
    *,
    project_name: str,
    source: str,
    note: str | None,
    params: dict[str, Any],
    patch: dict[str, Any] | None = None,
) -> int:
    normalized_name = normalize_project_name(project_name)
    version_no = get_next_version_no(normalized_name)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO simulation_versions(session_id, version_no, source, note, params_json, patch_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_name,
                version_no,
                source.strip(),
                (note or "").strip(),
                json.dumps(params if isinstance(params, dict) else {}),
                json.dumps(patch if isinstance(patch, dict) else {}),
            ),
        )
        conn.commit()
    return version_no


def list_versions(project_name: str, limit: int = 100) -> list[dict[str, Any]]:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT version_no, created_at, source, note
            FROM simulation_versions
            WHERE session_id = ?
            ORDER BY version_no DESC, created_at DESC
            LIMIT ?
            """,
            (normalized_name, int(limit)),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for version_no, created_at, source, note in rows:
        out.append(
            {
                "version_no": int(version_no),
                "created_at": _sqlite_utc_to_berlin(created_at),
                "source": str(source or ""),
                "note": str(note or ""),
            }
        )
    return out


def get_latest_params(project_name: str) -> dict[str, Any] | None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT params_json, version_no, created_at, source, note
            FROM simulation_versions
            WHERE session_id = ?
            ORDER BY version_no DESC, created_at DESC
            LIMIT 1
            """,
            (normalized_name,),
        ).fetchone()
    if row is None:
        return None
    params_json, version_no, created_at, source, note = row
    return {
        "params": json.loads(params_json) if params_json else {},
        "version_no": int(version_no),
        "created_at": _sqlite_utc_to_berlin(created_at),
        "source": str(source or ""),
        "note": str(note or ""),
    }


def get_version_by_no(project_name: str, version_no: int) -> dict[str, Any] | None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT params_json, patch_json, created_at, source, note
            FROM simulation_versions
            WHERE session_id = ? AND version_no = ?
            LIMIT 1
            """,
            (normalized_name, int(version_no)),
        ).fetchone()
    if row is None:
        return None
    params_json, patch_json, created_at, source, note = row
    return {
        "params": json.loads(params_json) if params_json else {},
        "patch": json.loads(patch_json) if patch_json else {},
        "version_no": int(version_no),
        "created_at": _sqlite_utc_to_berlin(created_at),
        "source": str(source or ""),
        "note": str(note or ""),
    }


def get_project_name(project_name: str) -> str | None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            "SELECT project_name FROM projects WHERE session_id = ? LIMIT 1",
            (normalized_name,),
        ).fetchone()
    if row is None:
        return None
    return str(row[0]) if row[0] is not None else None


def profile_snapshot_exists(project_name: str, profile_type: str) -> bool:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM profile_snapshots WHERE session_id = ? AND profile_type = ? LIMIT 1",
            (normalized_name, profile_type),
        ).fetchone()
    return row is not None


def save_profile_snapshot(
    *,
    project_name: str,
    profile_type: str,
    filename: str | None,
    series: list[Any] | None,
    description: Any,
    parse_attempts: list[str] | None,
    metadata: dict[str, Any] | None = None,
    reason_text: str | None = None,
) -> bool:
    """Insert/update one profile snapshot per (project_name, profile_type).

    Returns True if an existing snapshot was overwritten.
    """
    normalized_name = normalize_project_name(project_name)
    overwritten = profile_snapshot_exists(normalized_name, profile_type)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO profile_snapshots(
                session_id, profile_type, filename, series_json, description_json, parse_attempts_json, metadata_json, reason_text
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, profile_type) DO UPDATE SET
                filename = excluded.filename,
                series_json = excluded.series_json,
                description_json = excluded.description_json,
                parse_attempts_json = excluded.parse_attempts_json,
                metadata_json = excluded.metadata_json,
                reason_text = excluded.reason_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                normalized_name,
                profile_type,
                filename or "",
                json.dumps(series if isinstance(series, list) else []),
                json.dumps(description),
                json.dumps(parse_attempts if isinstance(parse_attempts, list) else []),
                json.dumps(metadata if isinstance(metadata, dict) else {}),
                (reason_text or "").strip(),
            ),
        )
        conn.commit()
    return overwritten


def get_profile_snapshot(project_name: str, profile_type: str) -> dict[str, Any] | None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT filename, series_json, description_json, parse_attempts_json, metadata_json, reason_text, created_at, updated_at
            FROM profile_snapshots
            WHERE session_id = ? AND profile_type = ?
            LIMIT 1
            """,
            (normalized_name, profile_type),
        ).fetchone()
    if row is None:
        return None
    return {
        "filename": str(row[0] or ""),
        "series": json.loads(row[1]) if row[1] else [],
        "description": json.loads(row[2]) if row[2] else None,
        "parse_attempts": json.loads(row[3]) if row[3] else [],
        "metadata": json.loads(row[4]) if row[4] else {},
        "reason_text": str(row[5] or ""),
        "created_at": _sqlite_utc_to_berlin(row[6]),
        "updated_at": _sqlite_utc_to_berlin(row[7]),
    }


def save_tariff_snapshot(
    *,
    project_name: str,
    filename: str | None,
    selected_voltage_level: str | None,
    extracted_tariff: dict[str, Any] | None,
) -> None:
    normalized_name = normalize_project_name(project_name)
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
                normalized_name,
                filename or "",
                selected_voltage_level or "",
                json.dumps(extracted_tariff if isinstance(extracted_tariff, dict) else {}),
            ),
        )
        conn.commit()


def get_tariff_snapshot(project_name: str) -> dict[str, Any] | None:
    normalized_name = normalize_project_name(project_name)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT filename, selected_voltage_level, extracted_tariff_json, updated_at
            FROM tariff_snapshots
            WHERE session_id = ?
            LIMIT 1
            """,
            (normalized_name,),
        ).fetchone()
    if row is None:
        return None
    return {
        "filename": str(row[0] or ""),
        "selected_voltage_level": str(row[1] or ""),
        "extracted_tariff": json.loads(row[2]) if row[2] else {},
        "updated_at": _sqlite_utc_to_berlin(row[3]),
    }


def append_llm_usage_event(project_name: str, row: dict[str, Any]) -> None:
    normalized_name = normalize_project_name(project_name)
    if not normalized_name:
        return
    action = str(row.get("action", "") or "")
    model = str(row.get("model", "") or "")
    if not action or not model:
        return
    ingest_tokens = int(row.get("ingest_tokens", 0) or 0)
    output_tokens = int(row.get("output_tokens", 0) or 0)
    total_tokens = int(row.get("total_tokens", ingest_tokens + output_tokens) or 0)
    cost_eur = float(row.get("cost_eur", 0.0) or 0.0)
    event_time = str(row.get("time", "") or "").strip()
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_usage_events(
                project_name, created_at, action, model, ingest_tokens, output_tokens, total_tokens, cost_eur, meta_json
            ) VALUES (?, COALESCE(NULLIF(?, ''), CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_name,
                event_time,
                action,
                model,
                ingest_tokens,
                output_tokens,
                total_tokens,
                cost_eur,
                json.dumps(meta),
            ),
        )
        conn.commit()


def list_llm_usage_events(project_name: str, limit: int = 1000) -> list[dict[str, Any]]:
    normalized_name = normalize_project_name(project_name)
    if not normalized_name:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT created_at, action, model, ingest_tokens, output_tokens, total_tokens, cost_eur, meta_json
            FROM llm_usage_events
            WHERE project_name = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (normalized_name, int(limit)),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for created_at, action, model, ingest_tokens, output_tokens, total_tokens, cost_eur, meta_json in rows:
        out.append(
            {
                "time": _sqlite_utc_to_berlin(created_at),
                "action": str(action or ""),
                "model": str(model or ""),
                "ingest_tokens": int(ingest_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "total_tokens": int(total_tokens or 0),
                "cost_eur": float(cost_eur or 0.0),
                "meta": json.loads(meta_json) if meta_json else {},
            }
        )
    return out


def clear_llm_usage_events(project_name: str) -> None:
    normalized_name = normalize_project_name(project_name)
    if not normalized_name:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM llm_usage_events WHERE project_name = ?", (normalized_name,))
        conn.commit()


# Backward-compatible aliases while the rest of the app migrates terminology.
normalize_project_name_to_session_id = normalize_project_name
list_project_session_ids = list_project_names

