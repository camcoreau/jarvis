"""Regression tests for member-safe focused Outline search fallback."""

from __future__ import annotations

import json

from openjarvis.core.types import ToolResult
from openjarvis.server.camcore_member_knowledge import (
    _focused_query,
    build_member_knowledge_context,
)
from openjarvis.tools._stubs import ToolSpec


class _SearchTool:
    tool_id = "mcp_adapter"

    def __init__(self, client: object) -> None:
        self._client = client
        self.spec = ToolSpec(name="list_documents", description="test")
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        query = params.get("query")
        if query == "Earth CamCore":
            content = json.dumps(
                [
                    {
                        "document": {
                            "id": "earth-doc",
                            "title": "CamCore Server Roles",
                        },
                        "context": "Earth is the CamCore storage and NAS host.",
                    }
                ]
            )
        else:
            content = "[]"
        return ToolResult(tool_name="list_documents", content=content, success=True)


class _FetchTool:
    tool_id = "mcp_adapter"

    def __init__(self, client: object) -> None:
        self._client = client
        self.spec = ToolSpec(name="fetch", description="test")
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        return ToolResult(
            tool_name="fetch",
            content=(
                '{"document":{"id":"earth-doc","title":"CamCore Server Roles"}}\n'
                "Earth is the CamCore storage and NAS host."
            ),
            success=True,
        )


class _Agent:
    def __init__(self, tools) -> None:
        self._tools = tools


def test_focused_query_keeps_distinctive_camcore_scope():
    assert _focused_query("What is Earth in CamCore?") == "Earth CamCore"


def test_member_knowledge_retries_with_focused_query_when_full_question_misses():
    client = object()
    search = _SearchTool(client)
    fetch = _FetchTool(client)
    agent = _Agent([search, fetch])

    context = build_member_knowledge_context(agent, "What is Earth in CamCore?")

    assert search.calls == [
        {"query": "What is Earth in CamCore?", "limit": 5},
        {"query": "Earth CamCore", "limit": 5},
    ]
    assert fetch.calls == [{"resource": "document", "id": "earth-doc"}]
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in context
    assert "Earth is the CamCore storage and NAS host." in context
    assert "earth-doc" not in context
