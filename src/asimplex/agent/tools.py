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


def search_price_list(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
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


def get_llm_context_payloads(session_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_summary_json": session_state.get("profile_summary_json") or {},
        "peak_shaving_json": session_state.get("peak_shaving_json") or {},
        "simulation_plan_params": session_state.get("simulation_plan_params") or {},
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


def propose_parameter_patch(
    current_params: dict[str, Any],
    proposed_params: dict[str, Any],
) -> dict[str, Any]:
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

