"""Tests for LLM usage event persistence in session_store."""

from __future__ import annotations

from pathlib import Path

from asimplex.persistence import session_store


def test_append_and_list_llm_usage_events(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_llm_usage.db"
    monkeypatch.setattr(session_store, "DB_PATH", test_db)

    session_store.init_db()
    session_store.create_project("proj-usage")

    session_store.append_llm_usage_event(
        "proj-usage",
        {
            "time": "2026-01-01 12:00:00",
            "action": "Chat agent",
            "model": "gpt-4.1-mini",
            "ingest_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost_eur": 0.0001,
        },
    )
    session_store.append_llm_usage_event(
        "proj-usage",
        {
            "time": "2026-01-01 12:01:00",
            "action": "Tariff extraction",
            "model": "gpt-4.1-mini",
            "ingest_tokens": 20,
            "output_tokens": 4,
            "total_tokens": 24,
            "cost_eur": 0.0002,
        },
    )

    rows = session_store.list_llm_usage_events("proj-usage")
    assert len(rows) == 2
    assert rows[0]["action"] == "Chat agent"
    assert rows[1]["action"] == "Tariff extraction"
    assert sum(int(r["ingest_tokens"]) for r in rows) == 30
    assert sum(int(r["output_tokens"]) for r in rows) == 9
