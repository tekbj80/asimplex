"""Tests for extracting tool invocation traces from runner messages."""

from __future__ import annotations

from asimplex.agent.runner import _extract_tool_invocations


class _Msg:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


def test_extract_tool_invocations_from_messages() -> None:
    messages = [
        _Msg(
            [
                {"name": "get_context_payloads", "id": "call_1", "args": {}},
                {"name": "draft_parameter_patch", "id": "call_2", "args": {"x": 1}},
            ]
        ),
        _Msg(None),
    ]
    invocations = _extract_tool_invocations(messages)
    assert [x["tool_name"] for x in invocations] == ["get_context_payloads", "draft_parameter_patch"]
    assert invocations[0]["order"] == 1
    assert invocations[1]["order"] == 2
