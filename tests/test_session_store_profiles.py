"""Persistence tests for profile snapshot metadata behavior."""

from __future__ import annotations

import time
from pathlib import Path

from asimplex.persistence import session_store


def test_profile_snapshot_persists_reason_and_timestamps(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_sessions.db"
    monkeypatch.setattr(session_store, "DB_PATH", test_db)

    session_store.init_db()
    session_store.create_project("proj-a", "Project A")

    overwritten = session_store.save_profile_snapshot(
        session_id="proj-a",
        profile_type="load",
        filename="load_v1.csv",
        series=[1.0, 2.0, 3.0],
        description={"rows_of_data_N": 3},
        parse_attempts=[],
        metadata={"source": "csv_upload"},
        reason_text="initial upload",
    )
    assert overwritten is False

    first = session_store.get_profile_snapshot("proj-a", "load")
    assert isinstance(first, dict)
    assert first["reason_text"] == "initial upload"
    assert first["filename"] == "load_v1.csv"
    assert first["created_at"]
    assert first["updated_at"]

    # SQLite CURRENT_TIMESTAMP is second-level; pause to force timestamp change.
    time.sleep(1.1)

    overwritten = session_store.save_profile_snapshot(
        session_id="proj-a",
        profile_type="load",
        filename="load_v2.csv",
        series=[9.0, 8.0, 7.0],
        description={"rows_of_data_N": 3},
        parse_attempts=[],
        metadata={"source": "csv_upload"},
        reason_text="updated with revised profile",
    )
    assert overwritten is True

    second = session_store.get_profile_snapshot("proj-a", "load")
    assert isinstance(second, dict)
    assert second["reason_text"] == "updated with revised profile"
    assert second["filename"] == "load_v2.csv"
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] != first["updated_at"]
