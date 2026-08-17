"""Regressions for CamCore Operations read-only Outline answer routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from openjarvis.agents.camcore_assistant import CamCoreAssistantAgent
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


class _RuntimeTool(BaseTool):
    tool_id = "runtime_test"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="check_runtime",
            description="Check live runtime state.",
            parameters={"type": "object", "properties": {}},
        )

    def execute(self, **params) -> ToolResult:
        return ToolResult(
            tool_name="check_runtime",
            content="runtime-ok",
            success=True,
        )


def _agent():
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.generate.return_value = {
        "content": "SILVER-KOALA-4821",
        "usage": {},
        "finish_reason": "stop",
    }
    return CamCoreAssistantAgent(engine, "test-model", tools=[_RuntimeTool()]), engine


def _fresh_context(*_args, **_kwargs):
    return (
        "CAMCORE OPERATIONS DOCUMENTATION PRIORITY\n\n"
        "FRESH CAMCORE OUTLINE DOCUMENTATION\n"
        "CamCore documentation marker: SILVER-KOALA-4821"
    )


def test_read_only_documentation_lookup_runs_one_turn_without_tools(monkeypatch):
    agent, engine = _agent()
    monkeypatch.setattr(
        "openjarvis.agents.camcore_assistant._fresh_operations_outline_context",
        _fresh_context,
    )

    result = agent.run(
        "According to the current CamCore documentation, "
        "what is the CamCore documentation marker?"
    )

    assert result.content == "SILVER-KOALA-4821"
    assert result.turns == 1
    assert "tools" not in engine.generate.call_args.kwargs


def test_simple_documented_fact_lookup_runs_without_tools(monkeypatch):
    agent, engine = _agent()
    monkeypatch.setattr(
        "openjarvis.agents.camcore_assistant._fresh_operations_outline_context",
        _fresh_context,
    )

    result = agent.run("What is Earth in CamCore?")

    assert result.content == "SILVER-KOALA-4821"
    assert result.turns == 1
    assert "tools" not in engine.generate.call_args.kwargs


def test_explicit_operational_action_keeps_tools(monkeypatch):
    agent, engine = _agent()
    monkeypatch.setattr(
        "openjarvis.agents.camcore_assistant._fresh_operations_outline_context",
        _fresh_context,
    )

    agent.run("Restart Earth")

    tools = engine.generate.call_args.kwargs["tools"]
    assert tools[0]["function"]["name"] == "check_runtime"


def test_live_state_question_keeps_tools(monkeypatch):
    agent, engine = _agent()
    monkeypatch.setattr(
        "openjarvis.agents.camcore_assistant._fresh_operations_outline_context",
        _fresh_context,
    )

    agent.run("What is Earth's current CPU usage?")

    tools = engine.generate.call_args.kwargs["tools"]
    assert tools[0]["function"]["name"] == "check_runtime"
