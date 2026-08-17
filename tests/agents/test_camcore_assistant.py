"""Tests for the CamCoreAssistantAgent."""

from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock

import openjarvis.agents.camcore_assistant as camcore_assistant_module
from openjarvis.agents.camcore_assistant import (
    CAMCORE_SYSTEM_PROMPT,
    CamCoreAssistantAgent,
)
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Role, ToolResult
from openjarvis.security.guardrails import GuardrailsEngine
from openjarvis.security.types import RedactionMode
from openjarvis.tools._stubs import ToolSpec


def _make_engine(content: str = "CamCore is healthy.") -> MagicMock:
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.generate.return_value = {
        "content": content,
        "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        "model": "test-model",
        "finish_reason": "stop",
    }
    return engine


class _FakeMcpTool:
    tool_id = "mcp_adapter"

    def __init__(self, name: str, client: object, content: str) -> None:
        self.spec = ToolSpec(name=name, description="test", parameters={})
        self._client = client
        self._content = content
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        return ToolResult(
            tool_name=self.spec.name,
            content=self._content,
            success=True,
        )

    def to_openai_function(self):
        return {
            "type": "function",
            "function": {
                "name": self.spec.name,
                "description": self.spec.description,
                "parameters": self.spec.parameters,
            },
        }


class TestCamCoreAssistantAgent:
    def test_registered(self):
        # tests/conftest.py clears registries before every test. Reload the module
        # to exercise the same decorator-based registration used at app startup.
        module = importlib.reload(camcore_assistant_module)

        assert AgentRegistry.contains("camcore_assistant")
        assert AgentRegistry.get("camcore_assistant") is module.CamCoreAssistantAgent

    def test_agent_id(self):
        agent = CamCoreAssistantAgent(_make_engine(), "test-model")
        assert agent.agent_id == "camcore_assistant"

    def test_default_system_prompt_is_injected(self):
        engine = _make_engine()
        agent = CamCoreAssistantAgent(engine, "test-model")

        result = agent.run("Check CamCore")

        assert result.content == "CamCore is healthy."
        messages = engine.generate.call_args[0][0]
        assert messages[0].role == Role.SYSTEM
        assert messages[0].content == CAMCORE_SYSTEM_PROMPT
        assert "camcore.network" in messages[0].content
        assert "camcore.au" in messages[0].content

    def test_explicit_system_prompt_can_override_default(self):
        engine = _make_engine()
        agent = CamCoreAssistantAgent(
            engine,
            "test-model",
            system_prompt="Custom CamCore prompt",
        )

        agent.run("Check CamCore")

        messages = engine.generate.call_args[0][0]
        assert messages[0].content == "Custom CamCore prompt"

    def test_operations_prefetch_prefers_fresh_outline_fetch(self):
        client = object()
        search = _FakeMcpTool(
            "list_documents",
            client,
            json.dumps(
                {
                    "document": {
                        "id": "validation-doc",
                        "title": "Jarvis Member Knowledge Validation",
                    },
                    "context": "CamCore validation phrase: BLUE-ORCHID-7319",
                }
            ),
        )
        fetch = _FakeMcpTool(
            "fetch",
            client,
            "\n".join(
                [
                    json.dumps(
                        {
                            "document": {
                                "id": "validation-doc",
                                "title": "Jarvis Member Knowledge Validation",
                            }
                        }
                    ),
                    "CamCore validation phrase: SILVER-KOALA-4821",
                ]
            ),
        )
        calculator = _FakeMcpTool("calculator", client, "42")
        engine = _make_engine("Current Outline answer")
        agent = CamCoreAssistantAgent(
            engine,
            "test-model",
            tools=[search, fetch, calculator],
        )

        result = agent.run(
            "According to the current CamCore documentation, what is the CamCore "
            "validation phrase?"
        )

        assert result.content == "Current Outline answer"
        messages = engine.generate.call_args[0][0]
        assert messages[0].role == Role.SYSTEM
        assert "CAMCORE OPERATIONS DOCUMENTATION PRIORITY" in messages[0].content
        assert "FRESH CAMCORE OUTLINE DOCUMENTATION" in messages[0].content
        assert "SILVER-KOALA-4821" in messages[0].content
        assert "BLUE-ORCHID-7319" not in messages[0].content
        assert "authoritative over public web search" in messages[0].content
        assert search.calls == [
            {
                "query": (
                    "According to the current CamCore documentation, what is the "
                    "CamCore validation phrase?"
                ),
                "limit": 5,
            }
        ]
        assert fetch.calls == [{"resource": "document", "id": "validation-doc"}]

        advertised = engine.generate.call_args.kwargs["tools"]
        advertised_names = {tool["function"]["name"] for tool in advertised}
        assert advertised_names == {"calculator"}

    def test_operations_prefetch_does_not_trip_block_mode_guardrails(self):
        client = object()
        search = _FakeMcpTool(
            "list_documents",
            client,
            json.dumps(
                {
                    "document": {
                        "id": "marker-doc",
                        "title": "Jarvis Knowledge Marker",
                    },
                    "context": "CamCore documentation marker: OLD-MARKER",
                }
            ),
        )
        fetch = _FakeMcpTool(
            "fetch",
            client,
            "\n".join(
                [
                    json.dumps(
                        {
                            "document": {
                                "id": "marker-doc",
                                "title": "Jarvis Knowledge Marker",
                            }
                        }
                    ),
                    "CamCore documentation marker: GREEN-WOMBAT-9642",
                    "Test support number: 202-555-0187",
                    "Test payment reference: 4111111111111111",
                ]
            ),
        )
        underlying = _make_engine("Current Outline marker")
        guarded = GuardrailsEngine(underlying, mode=RedactionMode.BLOCK)
        agent = CamCoreAssistantAgent(
            guarded,
            "test-model",
            tools=[search, fetch],
        )

        result = agent.run(
            "According to the current CamCore documentation, what is the CamCore "
            "documentation marker?"
        )

        assert result.content == "Current Outline marker"
        messages = underlying.generate.call_args[0][0]
        system_prompt = messages[0].content
        assert "GREEN-WOMBAT-9642" in system_prompt
        assert "OLD-MARKER" not in system_prompt
        assert "202-555-0187" not in system_prompt
        assert "4111111111111111" not in system_prompt
        assert "[REDACTED:" in system_prompt
        assert "tools" not in underlying.generate.call_args.kwargs

    def test_operations_model_cannot_reinvoke_raw_outline_tools(self):
        client = object()
        search = _FakeMcpTool(
            "list_documents",
            client,
            json.dumps(
                {
                    "document": {"id": "marker-doc", "title": "Marker"},
                    "context": "CamCore documentation marker: OLD-MARKER",
                }
            ),
        )
        fetch = _FakeMcpTool(
            "fetch",
            client,
            '{"document":{"id":"marker-doc","title":"Marker"}}\n'
            "CamCore documentation marker: GREEN-WOMBAT-9642\n"
            "Contact raw-tool@example.com",
        )
        engine = MagicMock()
        engine.engine_id = "mock"
        engine.generate.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-outline",
                        "name": "list_documents",
                        "arguments": json.dumps({"query": "marker", "limit": 5}),
                    }
                ],
                "usage": {},
                "finish_reason": "tool_calls",
            },
            {
                "content": "Safe final answer",
                "tool_calls": [],
                "usage": {},
                "finish_reason": "stop",
            },
        ]
        agent = CamCoreAssistantAgent(
            engine,
            "test-model",
            tools=[search, fetch],
        )

        result = agent.run("What is the CamCore documentation marker?")

        assert result.content == "Safe final answer"
        assert search.calls == [
            {"query": "What is the CamCore documentation marker?", "limit": 5}
        ]
        assert fetch.calls == [{"resource": "document", "id": "marker-doc"}]
        assert result.tool_results[0].success is False
        assert result.tool_results[0].content == "Unknown tool: list_documents"
        second_messages = engine.generate.call_args_list[1].args[0]
        tool_messages = [
            message for message in second_messages if message.role == Role.TOOL
        ]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "Unknown tool: list_documents"
        assert "raw-tool@example.com" not in tool_messages[0].content
