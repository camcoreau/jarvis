"""Tests for the CamCoreAssistantAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

from openjarvis.agents.camcore_assistant import (
    CAMCORE_SYSTEM_PROMPT,
    CamCoreAssistantAgent,
)
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Role


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


class TestCamCoreAssistantAgent:
    def test_registered(self):
        assert AgentRegistry.contains("camcore_assistant")
        assert AgentRegistry.get("camcore_assistant") is CamCoreAssistantAgent

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
