"""Tests for agent tool parameter-shape handling."""

from __future__ import annotations

from asimplex.agent.tools import get_proposal_json_format, propose_parameter_patch


def test_propose_parameter_patch_accepts_dotted_application_keys() -> None:
    result = propose_parameter_patch(
        current_params={},
        proposed_params={
            "application.grid_limit": 220.87,
            "application.evo_threshold": 0.95,
        },
    )
    assert result["issues"] == []
    assert result["patch"]["application"]["grid_limit"] == 220.87
    assert result["patch"]["application"]["evo_threshold"] == 0.95


def test_propose_parameter_patch_merges_nested_and_dotted_application_keys() -> None:
    result = propose_parameter_patch(
        current_params={},
        proposed_params={
            "application": {"grid_limit": 180.0},
            "application.evo_threshold": 0.4,
        },
    )
    assert result["issues"] == []
    assert result["patch"]["application"]["grid_limit"] == 180.0
    assert result["patch"]["application"]["evo_threshold"] == 0.4


def test_get_proposal_json_format_contains_expected_contract_keys() -> None:
    payload = get_proposal_json_format()
    assert payload["allowed_top_level_keys"] == ["application", "battery_selection"]
    assert payload["allowed_application_keys"] == ["grid_limit", "evo_threshold"]
    assert payload["constraints"]["application"]["grid_limit"]["type"] == "number"
    assert payload["constraints"]["application"]["evo_threshold"]["maximum"] == 1.0
    assert payload["constraints"]["battery_selection"]["product_id"]["type"] == "integer"
    assert "path_constraints" in payload
    assert "canonical_examples" in payload
    assert "anti_patterns" in payload


def test_canonical_examples_from_contract_validate_without_issues() -> None:
    payload = get_proposal_json_format()
    examples = payload["canonical_examples"]
    for key in ("application_only",):
        result = propose_parameter_patch(current_params={}, proposed_params=examples[key])
        assert result["issues"] == []


def test_battery_example_from_contract_is_shape_valid() -> None:
    payload = get_proposal_json_format()
    result = propose_parameter_patch(current_params={}, proposed_params=payload["canonical_examples"]["battery_only"])
    # Battery ID existence depends on repo-local price list; verify no shape/allow-list issues.
    assert all("Top-level key" not in issue for issue in result["issues"])
    assert all("must be an object" not in issue for issue in result["issues"])
