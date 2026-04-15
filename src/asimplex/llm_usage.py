"""LLM token usage helpers (session accumulation + LangChain message parsing)."""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any


def _coerce_int(value: int | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def default_llm_usage() -> dict[str, Any]:
    return {
        "total_input": 0,
        "total_output": 0,
        "last_label": "",
        "last_input": 0,
        "last_output": 0,
        "total_cost_eur": 0.0,
        "rows": [],
    }


def _price_table_eur_per_million_tokens() -> dict[str, tuple[float, float]]:
    usd_to_eur = float(os.getenv("ASIMPLEX_USD_TO_EUR", "0.92"))
    return {
        "gpt-4.1-mini": (
            float(os.getenv("ASIMPLEX_GPT41_MINI_INPUT_USD_PER_1M", "0.40")) * usd_to_eur,
            float(os.getenv("ASIMPLEX_GPT41_MINI_OUTPUT_USD_PER_1M", "1.60")) * usd_to_eur,
        ),
        "gpt-4o-mini": (
            float(os.getenv("ASIMPLEX_GPT4O_MINI_INPUT_USD_PER_1M", "0.15")) * usd_to_eur,
            float(os.getenv("ASIMPLEX_GPT4O_MINI_OUTPUT_USD_PER_1M", "0.60")) * usd_to_eur,
        ),
    }


def _estimate_cost_eur(model_name: str, input_tokens: int, output_tokens: int) -> float:
    table = _price_table_eur_per_million_tokens()
    in_per_m, out_per_m = table.get(model_name, (0.0, 0.0))
    return (input_tokens / 1_000_000.0) * in_per_m + (output_tokens / 1_000_000.0) * out_per_m


def record_llm_usage(
    session_state: dict[str, Any],
    *,
    label: str,
    model_name: str = "gpt-4.1-mini",
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    inp = _coerce_int(input_tokens)
    out = _coerce_int(output_tokens)
    usage = session_state.setdefault("llm_usage", default_llm_usage())
    usage["total_input"] = int(usage.get("total_input", 0)) + inp
    usage["total_output"] = int(usage.get("total_output", 0)) + out
    usage["last_label"] = str(label)
    usage["last_input"] = inp
    usage["last_output"] = out
    cost_eur = _estimate_cost_eur(model_name, inp, out)
    usage["total_cost_eur"] = float(usage.get("total_cost_eur", 0.0) or 0.0) + cost_eur
    rows = usage.setdefault("rows", [])
    if not isinstance(rows, list):
        rows = []
        usage["rows"] = rows
    rows.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": str(label),
            "model": str(model_name),
            "ingest_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "cost_eur": cost_eur,
        }
    )


def sum_usage_from_langchain_messages(messages: list[Any] | None) -> tuple[int, int]:
    """Sum input/output tokens from LangChain AIMessage.usage_metadata across a turn."""
    if not messages:
        return 0, 0
    total_in = 0
    total_out = 0
    for msg in messages:
        um = getattr(msg, "usage_metadata", None)
        if not isinstance(um, dict):
            continue
        total_in += _coerce_int(um.get("input_tokens"))
        total_out += _coerce_int(um.get("output_tokens"))
    return total_in, total_out
