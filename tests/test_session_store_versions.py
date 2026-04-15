"""Persistence tests for simulation parameter versioning."""

from __future__ import annotations

from pathlib import Path

from asimplex.persistence import session_store


def test_create_version_increments_and_latest_and_roundtrip(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test_versions.db"
    monkeypatch.setattr(session_store, "DB_PATH", test_db)

    session_store.init_db()
    session_store.create_project("proj-versions")

    v0 = session_store.create_version(
        project_name="proj-versions",
        source="manual_save",
        note="initial",
        params={"application": {"grid_limit": 110.0, "evo_threshold": 0.8}},
        patch={"application": {"grid_limit": 110.0}},
    )
    v1 = session_store.create_version(
        project_name="proj-versions",
        source="tariff_upload",
        note="tariff updated",
        params={"application": {"grid_limit": 120.0, "evo_threshold": 0.85}},
        patch={"tariff": {"below_2500": {"grid_draw_cost": 0.11}}},
    )
    v2 = session_store.create_version(
        project_name="proj-versions",
        source="agent_setting",
        note="agent changed threshold",
        params={"application": {"grid_limit": 120.0, "evo_threshold": 0.9}},
        patch={"application": {"evo_threshold": 0.9}},
    )

    assert v0 == 0
    assert v1 == 1
    assert v2 == 2

    latest = session_store.get_latest_params("proj-versions")
    assert isinstance(latest, dict)
    assert latest["version_no"] == 2
    assert latest["source"] == "agent_setting"
    assert latest["params"]["application"]["evo_threshold"] == 0.9

    versions = session_store.list_versions("proj-versions")
    assert [item["version_no"] for item in versions] == [2, 1, 0]

    v1_payload = session_store.get_version_by_no("proj-versions", 1)
    assert isinstance(v1_payload, dict)
    assert v1_payload["version_no"] == 1
    assert v1_payload["source"] == "tariff_upload"
    assert v1_payload["params"]["application"]["grid_limit"] == 120.0
    assert v1_payload["patch"]["tariff"]["below_2500"]["grid_draw_cost"] == 0.11
