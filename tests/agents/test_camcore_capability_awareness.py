"""Regression tests for CamCore Operations capability awareness."""

from __future__ import annotations

from unittest.mock import MagicMock

import openjarvis.agents.camcore_assistant as camcore_assistant_module
from openjarvis.agents.camcore_assistant import (
    CamCoreAssistantAgent,
    _is_read_only_documentation_lookup,
    _operations_capability_context,
)
from openjarvis.core.types import Role
from openjarvis.tools.camcore_portainer import (
    CamCorePortainerContainerActionTool,
    CamCorePortainerContainerStatusTool,
    CamCorePortainerOverviewTool,
)


def _make_engine(content: str = "Documented Earth answer") -> MagicMock:
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.generate.return_value = {
        "content": content,
        "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        "model": "test-model",
        "finish_reason": "stop",
    }
    return engine


def test_capability_inventory_describes_attached_portainer_scope():
    agent = MagicMock()
    agent._engine = None
    agent._tools = [
        CamCorePortainerOverviewTool(),
        CamCorePortainerContainerStatusTool(),
        CamCorePortainerContainerActionTool(),
    ]

    context = _operations_capability_context(agent)

    assert "CAMCORE OPERATIONS CAPABILITY INVENTORY" in context
    assert "camcore_portainer_overview [read/live]" in context
    assert "camcore_portainer_container_status [read/live]" in context
    assert "camcore_portainer_container_action" in context
    assert "confirmation required for changes" in context
    assert "Only a successful tool result is a live observation" in context


def test_documentation_fastpath_keeps_capability_awareness(monkeypatch):
    engine = _make_engine()
    agent = CamCoreAssistantAgent(
        engine,
        "test-model",
        tools=[CamCorePortainerOverviewTool(), CamCorePortainerContainerStatusTool()],
    )
    monkeypatch.setattr(
        camcore_assistant_module,
        "_fresh_operations_outline_context",
        lambda _agent, _query: (
            "CAMCORE OPERATIONS DOCUMENTATION PRIORITY\n\n"
            "FRESH CAMCORE OUTLINE DOCUMENTATION\nEarth is the storage host."
        ),
    )

    result = agent.run("What is Earth in CamCore?")

    assert result.content == "Documented Earth answer"
    messages = engine.generate.call_args[0][0]
    assert messages[0].role == Role.SYSTEM
    assert "CAMCORE OPERATIONS CAPABILITY INVENTORY" in messages[0].content
    assert "camcore_portainer_overview" in messages[0].content
    assert "FRESH CAMCORE OUTLINE DOCUMENTATION" in messages[0].content
    assert "tools" not in engine.generate.call_args.kwargs


def test_live_state_question_keeps_portainer_callable(monkeypatch):
    engine = _make_engine("Live-check answer")
    agent = CamCoreAssistantAgent(
        engine,
        "test-model",
        tools=[CamCorePortainerOverviewTool(), CamCorePortainerContainerStatusTool()],
    )
    monkeypatch.setattr(
        camcore_assistant_module,
        "_fresh_operations_outline_context",
        lambda _agent, _query: (
            "CAMCORE OPERATIONS DOCUMENTATION PRIORITY\n\n"
            "FRESH CAMCORE OUTLINE DOCUMENTATION\nEarth is a documented server."
        ),
    )

    result = agent.run("What containers are currently running on Earth?")

    assert result.content == "Live-check answer"
    advertised = engine.generate.call_args.kwargs["tools"]
    names = {item["function"]["name"] for item in advertised}
    assert names == {
        "camcore_portainer_overview",
        "camcore_portainer_container_status",
    }


def test_live_state_language_is_not_documentation_only():
    assert _is_read_only_documentation_lookup("What is Earth in CamCore?") is True
    assert (
        _is_read_only_documentation_lookup(
            "What containers are currently running on Earth?"
        )
        is False
    )
    assert (
        _is_read_only_documentation_lookup("What is the disk usage on Earth?")
        is False
    )
    assert _is_read_only_documentation_lookup("Is Plex healthy on Earth?") is False
