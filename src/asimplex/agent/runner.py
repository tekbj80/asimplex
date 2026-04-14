"""LangChain agent runner for scoped simulation tuning."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain.tools import tool

from asimplex.agent.tools import get_llm_context_payloads, search_price_list

SYSTEM_PROMPT = """
You are an optimization copilot for a peak-shaving simulation.

You may propose updates ONLY for:
- application.grid_limit
- application.evo_threshold
- battery_selection.product_id (chosen from price list)

You must NOT propose changes to:
- clock
- any profile data
- tariff or tariff_non_functional
- any other simulation key

Always include concise reasoning and mention EVO logic:
- evo_threshold is SOC p.u. above which EVO is activated.
- lsk_charge_from_grid influences charging toward evo_threshold.
""".strip()


@dataclass
class AgentResponse:
    reasoning: str
    proposed_params: dict[str, Any]
    next_step: str


def _extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def run_tuning_agent(*, user_message: str, session_state: dict[str, Any]) -> dict[str, Any]:
    context_payloads = get_llm_context_payloads(session_state)

    @tool
    def get_context_payloads() -> str:
        """Return profile summary, peak-shaving JSON, and current simulation params."""
        return json.dumps(context_payloads, indent=2)

    @tool
    def lookup_price_list(query: str) -> str:
        """Search non_code_resources/price_list.csv by product name, inverter, or product ID."""
        return json.dumps(search_price_list(query, limit=12), indent=2)

    model_name = os.getenv("ASIMPLEX_AGENT_MODEL", "gpt-4.1-mini")
    llm = init_chat_model(model_name, temperature=0)
    tools = [get_context_payloads, lookup_price_list]
    agent = create_agent(
        model=llm,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        response_format=ToolStrategy(AgentResponse),
    )
    result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})

    structured = result.get("structured_response")
    if isinstance(structured, AgentResponse):
        parsed = {
            "reasoning": structured.reasoning,
            "proposed_params": structured.proposed_params or {},
            "next_step": structured.next_step,
        }
    elif isinstance(structured, dict):
        parsed = dict(structured)
    else:
        output_text = ""
        messages = result.get("messages", [])
        if isinstance(messages, list) and messages:
            last = messages[-1]
            output_text = str(getattr(last, "content", ""))
        parsed = _extract_json_object(output_text)
        if not parsed:
            parsed = {
                "reasoning": output_text or "Agent did not return structured output.",
                "proposed_params": {},
                "next_step": "insufficient_data",
            }
    if not isinstance(parsed, dict):
        parsed = {
            "reasoning": "Agent did not return structured output.",
            "proposed_params": {},
            "next_step": "insufficient_data",
        }
    parsed.setdefault("reasoning", "")
    parsed.setdefault("proposed_params", {})
    parsed.setdefault("next_step", "insufficient_data")
    return parsed

