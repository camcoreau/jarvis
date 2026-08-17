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
        engine = _make_engine("Current Outline answer")
        agent = CamCoreAssistantAgent(
            engine,
            "test-model",
            tools=[search, fetch],
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
