"""Helpers for agent context, pricing lookup, and safe parameter patching."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
PRICE_LIST_PATH = REPO_ROOT / "non_code_resources" / "price_list.csv"

ALLOWED_APPLICATION_KEYS = {"grid_limit", "evo_threshold"}
ALLOWED_TOP_LEVEL_KEYS = {"application", "battery_selection"}


def load_price_list_df() -> pd.DataFrame:
    df = pd.read_csv(PRICE_LIST_PATH)
    for col in ["productId", "capacity", "power", "price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["productId", "capacity", "power", "price"]).copy()


def load_price_list_records(limit: int = 200) -> list[dict[str, Any]]:
    df = load_price_list_df().head(limit)
    return df.to_dict(orient="records")


def search_price_list(query: str, *, limit: int = 100) -> list[dict[str, Any]]:
    df = load_price_list_df()
    q = (query or "").strip()
    if not q:
        return df.head(limit).to_dict(orient="records")

    mask = (
        df["productName"].astype(str).str.contains(q, case=False, na=False)
        | df["inverter"].astype(str).str.contains(q, case=False, na=False)
        | df["productId"].astype(str).str.contains(q, case=False, na=False)
    )
    if mask.any():
        return df.loc[mask].head(limit).to_dict(orient="records")
    return df.head(limit).to_dict(orient="records")


def search_price_list_near_target(
    *,
    target_capacity_kwh: float,
    target_power_kw: float,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return nearest battery candidates to target capacity/power."""
    df = load_price_list_df().copy()
    if df.empty:
        return []

    try:
        target_capacity = max(float(target_capacity_kwh), 1e-6)
        target_power = max(float(target_power_kw), 1e-6)
    except (TypeError, ValueError):
        return df.head(limit).to_dict(orient="records")

    cap_rel = (df["capacity"] - target_capacity).abs() / target_capacity
    power_rel = (df["power"] - target_power).abs() / target_power
    # Slightly favor capacity matching because storage sizing is primary.
    df["distance_score"] = (0.6 * cap_rel) + (0.4 * power_rel)

    nearest = df.sort_values(by=["distance_score", "price", "productId"], ascending=[True, True, True]).head(limit)
    return nearest.to_dict(orient="records")


def get_llm_simulation_context_payload(session_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_summary_json": session_state.get("profile_summary_json") or {},
        "peak_shaving_json": session_state.get("peak_shaving_json") or {},
        "peak_shaving_capacity_summary_json": session_state.get("peak_shaving_capacity_summary_json") or {},
        "simulation_plan_params": session_state.get("simulation_plan_params") or {},
        "simulation_benchmark_context_json": session_state.get("simulation_benchmark_context_json") or {},
    }


def get_proposal_json_format() -> dict[str, Any]:
    """Return canonical proposal JSON contract for agent parameter updates."""
    return {
        "allowed_top_level_keys": ["application", "battery_selection"],
        "allowed_application_keys": ["grid_limit", "evo_threshold"],
        "constraints": {
            "application": {
                "grid_limit": {"type": "number", "exclusive_minimum": 0},
                "evo_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "battery_selection": {
                "product_id": {"type": "integer"},
            },
        },
        "path_constraints": {
            "application.grid_limit": {"type": "number", "exclusive_minimum": 0},
            "application.evo_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "battery_selection.product_id": {"type": "integer"},
        },
        "canonical_examples": {
            "application_only": {"application": {"grid_limit": 220.87, "evo_threshold": 0.95}},
            "battery_only": {"battery_selection": {"product_id": 123456}},
            "application_and_battery": {
                "application": {"grid_limit": 180.0, "evo_threshold": 0.4},
                "battery_selection": {"product_id": 123456},
            },
        },
        "anti_patterns": {
            "dotted_keys_not_allowed": [
                "application.grid_limit",
                "application.evo_threshold",
                "battery_selection.product_id",
            ]
        },
    }


def _normalize_product_id(selection: dict[str, Any]) -> int | None:
    raw = selection.get("product_id", selection.get("productId"))
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def validate_scope(proposed_params: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in proposed_params:
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            issues.append(f"Top-level key '{key}' is not allowed.")

    app = proposed_params.get("application")
    if app is not None:
        if not isinstance(app, dict):
            issues.append("Key 'application' must be an object.")
        else:
            for key in app:
                if key not in ALLOWED_APPLICATION_KEYS:
                    issues.append(f"Application key '{key}' is not allowed.")
            if "evo_threshold" in app:
                try:
                    evo = float(app["evo_threshold"])
                    if not 0.0 <= evo <= 1.0:
                        issues.append("application.evo_threshold must be between 0.0 and 1.0.")
                except (TypeError, ValueError):
                    issues.append("application.evo_threshold must be numeric.")
            if "grid_limit" in app:
                try:
                    grid = float(app["grid_limit"])
                    if grid <= 0:
                        issues.append("application.grid_limit must be greater than 0.")
                except (TypeError, ValueError):
                    issues.append("application.grid_limit must be numeric.")

    battery_selection = proposed_params.get("battery_selection")
    if battery_selection is not None and not isinstance(battery_selection, dict):
        issues.append("Key 'battery_selection' must be an object.")
    return issues


def _normalize_proposed_params_shape(proposed_params: dict[str, Any]) -> dict[str, Any]:
    """Normalize flattened dotted keys into nested proposal objects.

    Example:
    {"application.grid_limit": 120} -> {"application": {"grid_limit": 120}}
    """
    normalized: dict[str, Any] = dict(proposed_params)

    application = normalized.get("application")
    if not isinstance(application, dict):
        application = {}
    for dotted_key in ("application.grid_limit", "application.evo_threshold"):
        if dotted_key in normalized:
            leaf_key = dotted_key.split(".", 1)[1]
            application[leaf_key] = normalized.pop(dotted_key)
    if application:
        normalized["application"] = application

    battery_selection = normalized.get("battery_selection")
    if not isinstance(battery_selection, dict):
        battery_selection = {}
    for dotted_key in ("battery_selection.product_id", "battery_selection.productId"):
        if dotted_key in normalized:
            leaf_key = dotted_key.split(".", 1)[1]
            battery_selection[leaf_key] = normalized.pop(dotted_key)
    if battery_selection:
        normalized["battery_selection"] = battery_selection

    return normalized


def propose_parameter_patch(
    current_params: dict[str, Any],
    proposed_params: dict[str, Any],
) -> dict[str, Any]:
    proposed_params = _normalize_proposed_params_shape(proposed_params)
    issues = validate_scope(proposed_params)
    if issues:
        return {"patch": {}, "selected_battery": None, "issues": issues}

    patch: dict[str, Any] = {}
    selected_battery: dict[str, Any] | None = None

    application = proposed_params.get("application", {})
    if isinstance(application, dict):
        app_patch: dict[str, Any] = {}
        if "grid_limit" in application:
            app_patch["grid_limit"] = float(application["grid_limit"])
        if "evo_threshold" in application:
            app_patch["evo_threshold"] = float(application["evo_threshold"])
        if app_patch:
            patch["application"] = app_patch

    battery_selection = proposed_params.get("battery_selection", {})
    if isinstance(battery_selection, dict):
        product_id = _normalize_product_id(battery_selection)
        if product_id is None:
            if battery_selection:
                issues.append("battery_selection must include numeric product_id.")
        else:
            price_df = load_price_list_df()
            row_df = price_df.loc[price_df["productId"].astype(int) == product_id]
            if row_df.empty:
                issues.append(f"battery_selection.product_id={product_id} not found in price list.")
            else:
                row = row_df.iloc[0]
                patch["battery"] = {
                    "nominal_capacity": float(row["capacity"]),
                    "nominal_power": float(row["power"]),
                    "inverter_power": float(row["power"]),
                    "capex": float(row["price"]),
                }
                selected_battery = {
                    "productId": int(row["productId"]),
                    "productName": str(row["productName"]),
                    "capacity": float(row["capacity"]),
                    "power": float(row["power"]),
                    "inverter": str(row["inverter"]),
                    "price": float(row["price"]),
                }

    return {"patch": patch, "selected_battery": selected_battery, "issues": issues}


def apply_parameter_patch(base_params: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(base_params)
    for top_key, values in patch.items():
        if not isinstance(values, dict):
            continue
        updated.setdefault(top_key, {})
        if isinstance(updated[top_key], dict):
            updated[top_key].update(values)
    return updated

