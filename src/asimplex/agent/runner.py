"""LangChain agent runner for scoped simulation tuning."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain.tools import tool

from asimplex.agent.tools import (
    get_llm_simulation_context_payload,
    get_proposal_json_format as get_proposal_json_format_contract,
    propose_parameter_patch,
    search_price_list,
)
from asimplex.llm_usage import sum_usage_from_langchain_messages
from asimplex.persistence.chat_history_store import list_messages, trim_for_context

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

Before drafting proposed_params, you MUST call tool `get_proposal_json_format`.
Use that returned contract as the source of truth for shape and constraints.
Then call tool `draft_parameter_patch` with your candidate params so validation
and battery lookup are checked.
If draft_parameter_patch returns issues, revise proposed_params and retry.
Only set next_step="confirm" when issues is empty and patch is non-empty.
""".strip()


@dataclass
class AgentResponse:
    reasoning: str
    proposed_params: dict[str, Any]
    next_step: str
    patch: dict[str, Any] | None = None
    issues: list[str] | None = None
    selected_battery: dict[str, Any] | None = None


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


def _extract_tool_invocations(messages: list[Any] | None) -> list[dict[str, Any]]:
    if not messages:
        return []
    invocations: list[dict[str, Any]] = []
    order = 0
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                order += 1
                args = call.get("args")
                invocations.append(
                    {
                        "order": order,
                        "tool_name": str(call.get("name", "") or ""),
                        "tool_call_id": str(call.get("id", "") or ""),
                        "args_preview": json.dumps(args, default=str)[:500] if args is not None else "",
                    }
                )
    return invocations


def run_tuning_agent(*, user_message: str, session_state: dict[str, Any]) -> dict[str, Any]:
    context_payloads = get_llm_simulation_context_payload(session_state)
    current_params = context_payloads.get("simulation_plan_params", {})
    project_name = str(session_state.get("project_name", "") or "").strip()
    max_history_messages = int(os.getenv("ASIMPLEX_AGENT_HISTORY_MAX_MESSAGES", "12"))
    history_messages = list_messages(project_name) if project_name else []
    context_messages = trim_for_context(history_messages, max_messages=max_history_messages)

    @tool
    def get_context_payloads() -> str:
        """Return profile summary, peak-shaving JSON, and current simulation params."""
        return json.dumps(context_payloads, indent=2)

    @tool
    def lookup_price_list(query: str) -> str:
        """Search non_code_resources/price_list.csv by product name, inverter, or product ID."""
        return json.dumps(search_price_list(query, limit=12), indent=2)

    @tool
    def get_proposal_json_format() -> str:
        """Return canonical nested JSON contract for proposed_params."""
        return json.dumps(get_proposal_json_format_contract(), indent=2)

    @tool
    def draft_parameter_patch(proposed_params_json: str) -> str:
        """Validate a proposed parameter object and return patch, selected_battery, and issues."""
        proposed_obj = _extract_json_object(proposed_params_json)
        if not isinstance(proposed_obj, dict):
            proposed_obj = {}
        result_obj = propose_parameter_patch(current_params if isinstance(current_params, dict) else {}, proposed_obj)
        return json.dumps(result_obj, indent=2)

    model_name = os.getenv("ASIMPLEX_AGENT_MODEL", "gpt-4.1-mini")
    llm = init_chat_model(model_name, temperature=0)
    tools = [get_context_payloads, lookup_price_list, get_proposal_json_format, draft_parameter_patch]
    agent = create_agent(
        model=llm,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        response_format=ToolStrategy(AgentResponse),
    )
    result = agent.invoke({"messages": [*context_messages, HumanMessage(content=user_message)]})
    messages = result.get("messages")
    usage_in, usage_out = sum_usage_from_langchain_messages(messages)
    tool_invocations = _extract_tool_invocations(messages if isinstance(messages, list) else None)

    structured = result.get("structured_response")
    if isinstance(structured, AgentResponse):
        parsed = {
            "reasoning": structured.reasoning,
            "proposed_params": structured.proposed_params or {},
            "next_step": structured.next_step,
            "patch": structured.patch or {},
            "issues": structured.issues or [],
            "selected_battery": structured.selected_battery,
        }
    elif isinstance(structured, dict):
        parsed = dict(structured)
    else:
        output_text = ""
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
    parsed.setdefault("patch", {})
    parsed.setdefault("issues", [])
    parsed.setdefault("selected_battery", None)

    # Ensure a validated patch result is always present.
    proposed_params = parsed.get("proposed_params", {})
    if isinstance(proposed_params, dict):
        patch_result = propose_parameter_patch(
            current_params if isinstance(current_params, dict) else {},
            proposed_params,
        )
        if not isinstance(parsed.get("patch"), dict) or not parsed.get("patch"):
            parsed["patch"] = patch_result.get("patch", {})
        if not isinstance(parsed.get("issues"), list) or not parsed.get("issues"):
            parsed["issues"] = patch_result.get("issues", [])
        if parsed.get("selected_battery") is None:
            parsed["selected_battery"] = patch_result.get("selected_battery")

    patch_nonempty = isinstance(parsed.get("patch"), dict) and bool(parsed.get("patch"))
    issues_empty = isinstance(parsed.get("issues"), list) and not parsed.get("issues")
    if patch_nonempty and issues_empty:
        parsed["next_step"] = "confirm"

    parsed["usage"] = {"input_tokens": usage_in, "output_tokens": usage_out}
    parsed["tool_invocations"] = tool_invocations
    return parsed

