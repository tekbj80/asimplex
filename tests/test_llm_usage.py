"""Tests for LLM token usage helpers."""

from __future__ import annotations

from asimplex.llm_usage import (
    default_llm_usage,
    record_llm_usage,
    sum_usage_from_langchain_messages,
)


def test_record_llm_usage_accumulates_and_updates_last() -> None:
    state: dict = {"llm_usage": default_llm_usage()}
    record_llm_usage(state, label="Chat agent", input_tokens=10, output_tokens=20)
    u = state["llm_usage"]
    assert u["total_input"] == 10
    assert u["total_output"] == 20
    assert u["last_label"] == "Chat agent"
    assert u["last_input"] == 10
    assert u["last_output"] == 20
    assert u["total_cost_eur"] > 0
    assert len(u["rows"]) == 1
    assert u["rows"][0]["action"] == "Chat agent"
    assert u["rows"][0]["model"] == "gpt-4.1-mini"
    assert u["rows"][0]["ingest_tokens"] == 10
    assert u["rows"][0]["output_tokens"] == 20
    assert u["rows"][0]["cost_eur"] > 0

    record_llm_usage(state, label="Tariff extraction", input_tokens=5, output_tokens=3)
    u = state["llm_usage"]
    assert u["total_input"] == 15
    assert u["total_output"] == 23
    assert u["last_label"] == "Tariff extraction"
    assert u["last_input"] == 5
    assert u["last_output"] == 3
    assert len(u["rows"]) == 2
    assert u["rows"][1]["total_tokens"] == 8


def test_record_llm_usage_coerces_none_and_invalid() -> None:
    state: dict = {}
    record_llm_usage(state, label="x", input_tokens=None, output_tokens="bad")  # type: ignore[arg-type]
    u = state["llm_usage"]
    assert u["total_input"] == 0
    assert u["total_output"] == 0
    assert len(u["rows"]) == 1
    assert u["rows"][0]["total_tokens"] == 0
    assert u["rows"][0]["cost_eur"] == 0.0


def test_sum_usage_from_langchain_messages() -> None:
    class _Msg:
        def __init__(self, um: dict) -> None:
            self.usage_metadata = um

    messages = [
        _Msg({"input_tokens": 3, "output_tokens": 1}),
        _Msg({"input_tokens": 100, "output_tokens": 40}),
    ]
    assert sum_usage_from_langchain_messages(messages) == (103, 41)


def test_sum_usage_from_langchain_messages_empty() -> None:
    assert sum_usage_from_langchain_messages([]) == (0, 0)
    assert sum_usage_from_langchain_messages(None) == (0, 0)
