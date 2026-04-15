"""Tests for structured app event logging."""

from __future__ import annotations

from pathlib import Path

from asimplex.observability import app_log_store


def test_log_event_and_list_events(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_app_logs.db"
    monkeypatch.setattr(app_log_store, "DB_PATH", test_db)

    app_log_store.init_db()
    app_log_store.log_event(
        project_name="proj-a",
        source="chat_agent",
        event_type="agent_turn",
        status="success",
        tool_invocations=[{"tool_name": "lookup_price_list"}],
        message="ok",
        payload={"next_step": "confirm"},
    )
    app_log_store.log_event(
        project_name="proj-a",
        source="tariff_extraction",
        event_type="extract_tariff",
        status="error",
        error="bad file",
        payload={"filename": "nonsense.pdf"},
    )

    events = app_log_store.list_events("proj-a", limit=10)
    assert len(events) == 2
    assert events[0]["status"] == "error"
    assert events[1]["status"] == "success"
    assert events[1]["tool_invocations"][0]["tool_name"] == "lookup_price_list"
