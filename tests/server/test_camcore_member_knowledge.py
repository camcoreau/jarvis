"""Tests for the CamCore member-safe read-only knowledge boundary."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.core.types import Role, ToolResult  # noqa: E402
from openjarvis.server.app import create_app  # noqa: E402
from openjarvis.tools._stubs import ToolSpec  # noqa: E402


def _config() -> JarvisConfig:
    config = JarvisConfig()
    config.analytics.enabled = False
    config.traces.enabled = False
    config.agent.context_from_memory = True
    return config


def _engine():
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.health.return_value = True
    engine.list_models.return_value = ["server-model"]
    engine.generate.return_value = {
        "content": "Knowledge-backed reply",
        "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24},
        "finish_reason": "stop",
    }

    async def stream(messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
        engine.stream_messages = messages
        engine.stream_model = model
        for token in ["Knowledge", " reply"]:
            yield token

    engine.stream = stream
    return engine


class _FakeTool:
    def __init__(
        self,
        name: str,
        *,
        content: str = "",
        success: bool = True,
        mcp_client=None,
    ) -> None:
        self.spec = ToolSpec(name=name, description="test", parameters={})
        self.content = content
        self.success = success
        self.calls: list[dict] = []
        if mcp_client is not None:
            self.tool_id = "mcp_adapter"
            self._client = mcp_client

    def execute(self, **params):
        self.calls.append(params)
        return ToolResult(
            tool_name=self.spec.name,
            content=self.content,
            success=self.success,
        )


def _knowledge_agent():
    search_content = json.dumps(
        [
            {
                "document": {
                    "id": "doc-earth",
                    "title": "CamCore Server Roles",
                    "url": "https://docs.camcore.network/doc/server-roles",
                },
                "context": "Earth is the CamCore storage and NAS host.",
            }
        ]
    )
    fetch_content = "\n".join(
        [
            json.dumps(
                {
                    "document": {
                        "id": "doc-earth",
                        "title": "CamCore Server Roles",
                        "url": "https://docs.camcore.network/doc/server-roles",
                    }
                }
            ),
            "## Server roles",
            "Earth is the CamCore storage and NAS host.",
            "OPENAI_API_KEY=must-not-reach-member-model",
            "Earth management address: 192.168.5.25",
            "Earth private portal: docs.camcore.network",
        ]
    )

    outline_client = object()
    list_tool = _FakeTool(
        "camcore-outline:list_documents",
        content=search_content,
        mcp_client=outline_client,
    )
    fetch_tool = _FakeTool(
        "camcore-outline:fetch",
        content=fetch_content,
        mcp_client=outline_client,
    )
    destructive_tool = _FakeTool("delete_document", content="should never be called")

    agent = MagicMock()
    agent.agent_id = "camcore_assistant"
    agent._model = "server-model"
    agent._tools = [list_tool, fetch_tool, destructive_tool]
    return agent, list_tool, fetch_tool, destructive_tool


def test_member_camcore_query_gets_sanitized_outline_context_without_agent_tools():
    engine = _engine()
    agent, list_tool, fetch_tool, destructive_tool = _knowledge_agent()
    app = create_app(engine, "server-model", agent=agent, config=_config())
    client = TestClient(app)

    response = client.post(
        "/v1/camcore/portal/chat/completions",
        json={
            "model": "ignored-model",
            "messages": [{"role": "user", "content": "What is Earth in CamCore?"}],
        },
    )

    assert response.status_code == 200
    agent.run.assert_not_called()
    assert destructive_tool.calls == []
    assert list_tool.calls == [{"query": "What is Earth in CamCore?", "limit": 5}]
    assert fetch_tool.calls == [{"resource": "document", "id": "doc-earth"}]

    args, kwargs = engine.generate.call_args
    messages = args[0]
    assert messages[0].role == Role.SYSTEM
    system_prompt = messages[0].content
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in system_prompt
    assert "Earth is the CamCore storage and NAS host." in system_prompt
    assert "doc-earth" not in system_prompt
    assert "docs.camcore.network" not in system_prompt
    assert "192.168.5.25" not in system_prompt
    assert "must-not-reach-member-model" not in system_prompt
    assert "[restricted line redacted]" in system_prompt
    assert "[network address redacted]" in system_prompt
    assert "[private hostname redacted]" in system_prompt
    assert "tools" not in kwargs


def test_member_stream_keeps_sanitized_knowledge_context():
    engine = _engine()
    agent, _, _, _ = _knowledge_agent()
    app = create_app(engine, "server-model", agent=agent, config=_config())
    client = TestClient(app)

    response = client.post(
        "/v1/camcore/portal/chat/completions",
        json={
            "model": "ignored-model",
            "messages": [{"role": "user", "content": "What is Earth in CamCore?"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert "Knowledge" in response.text
    assert engine.stream_messages[0].role == Role.SYSTEM
    system_prompt = engine.stream_messages[0].content
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in system_prompt
    assert "Earth is the CamCore storage and NAS host." in system_prompt
    assert "192.168.5.25" not in system_prompt
    assert "docs.camcore.network" not in system_prompt
    agent.run.assert_not_called()


def test_generic_member_chat_does_not_touch_outline():
    engine = _engine()
    agent, list_tool, fetch_tool, destructive_tool = _knowledge_agent()
    app = create_app(engine, "server-model", agent=agent, config=_config())
    client = TestClient(app)

    response = client.post(
        "/v1/camcore/portal/chat/completions",
        json={
            "model": "ignored-model",
            "messages": [{"role": "user", "content": "Help me rewrite this sentence."}],
        },
    )

    assert response.status_code == 200
    assert list_tool.calls == []
    assert fetch_tool.calls == []
    assert destructive_tool.calls == []
    agent.run.assert_not_called()


def test_outline_failure_degrades_to_normal_member_chat():
    engine = _engine()
    outline_client = object()
    failed_list = _FakeTool(
        "list_documents",
        content="error",
        success=False,
        mcp_client=outline_client,
    )
    fetch_tool = _FakeTool("fetch", content="unused", mcp_client=outline_client)
    agent = MagicMock()
    agent._model = "server-model"
    agent._tools = [failed_list, fetch_tool]
    app = create_app(engine, "server-model", agent=agent, config=_config())
    client = TestClient(app)

    response = client.post(
        "/v1/camcore/portal/chat/completions",
        json={
            "model": "ignored-model",
            "messages": [{"role": "user", "content": "What is Earth in CamCore?"}],
        },
    )

    assert response.status_code == 200
    args, _ = engine.generate.call_args
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" not in args[0][0].content
    assert failed_list.calls == [{"query": "What is Earth in CamCore?", "limit": 5}]
    assert fetch_tool.calls == []
    agent.run.assert_not_called()


def test_same_named_non_mcp_tools_are_not_trusted_for_member_knowledge():
    engine = _engine()
    list_tool = _FakeTool("list_documents", content="not trusted")
    fetch_tool = _FakeTool("fetch", content="not trusted")
    agent = MagicMock()
    agent._model = "server-model"
    agent._tools = [list_tool, fetch_tool]
    app = create_app(engine, "server-model", agent=agent, config=_config())
    client = TestClient(app)

    response = client.post(
        "/v1/camcore/portal/chat/completions",
        json={
            "model": "ignored-model",
            "messages": [{"role": "user", "content": "What is Earth in CamCore?"}],
        },
    )

    assert response.status_code == 200
    assert list_tool.calls == []
    assert fetch_tool.calls == []
    args, _ = engine.generate.call_args
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" not in args[0][0].content
