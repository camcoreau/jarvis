"""Regression tests for Outline MCP multi-block member knowledge output."""

from __future__ import annotations

import json

from openjarvis.core.types import ToolResult
from openjarvis.server.camcore_member_knowledge import build_member_knowledge_context
from openjarvis.tools._stubs import ToolSpec


class _FakeMcpTool:
    tool_id = "mcp_adapter"

    def __init__(self, name: str, client: object, responses: list[str]) -> None:
        self.spec = ToolSpec(name=name, description="test", parameters={})
        self._client = client
        self._responses = list(responses)
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        content = self._responses.pop(0) if self._responses else ""
        return ToolResult(tool_name=self.spec.name, content=content, success=True)


def test_member_knowledge_parses_outline_multi_text_block_search_results():
    outline_client = object()

    # Outline's success([...]) emits one text block per result. OpenJarvis's MCP
    # adapter joins those text blocks with newlines, producing NDJSON here.
    search_content = "\n".join(
        [
            json.dumps(
                {
                    "document": {
                        "id": "doc-earth",
                        "title": "CamCore Server Roles",
                        "url": "https://docs.camcore.network/doc/server-roles",
                    },
                    "context": "Earth is the CamCore storage and NAS host.",
                }
            ),
            json.dumps(
                {
                    "document": {
                        "id": "doc-jupiter",
                        "title": "Compute Platform",
                        "url": "https://docs.camcore.network/doc/compute",
                    },
                    "context": "Jupiter provides CamCore compute capacity.",
                }
            ),
        ]
    )
    fetch_content = "\n".join(
        [
            json.dumps(
                {
                    "document": {
                        "id": "doc-earth",
                        "title": "CamCore Server Roles",
                    }
                }
            ),
            "## Server roles",
            "Earth is the CamCore storage and NAS host.",
        ]
    )

    list_tool = _FakeMcpTool("list_documents", outline_client, [search_content])
    fetch_tool = _FakeMcpTool("fetch", outline_client, [fetch_content, ""])

    class _Agent:
        _tools = [list_tool, fetch_tool]

    context = build_member_knowledge_context(_Agent(), "What is Earth in CamCore?")

    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in context
    assert "Earth is the CamCore storage and NAS host." in context
    assert "CamCore Server Roles" in context
    assert "doc-earth" not in context
    assert "doc-jupiter" not in context
    assert "docs.camcore.network" not in context
    assert list_tool.calls == [{"query": "What is Earth in CamCore?", "limit": 5}]
    assert fetch_tool.calls[0] == {"resource": "document", "id": "doc-earth"}


def test_member_knowledge_handles_outline_zero_result_array():
    outline_client = object()
    list_tool = _FakeMcpTool("list_documents", outline_client, ["[]", "[]"])
    fetch_tool = _FakeMcpTool("fetch", outline_client, [])

    class _Agent:
        _tools = [list_tool, fetch_tool]

    context = build_member_knowledge_context(_Agent(), "What is Earth in CamCore?")

    assert context == ""
    assert list_tool.calls == [
        {"query": "What is Earth in CamCore?", "limit": 5},
        {"query": "Earth", "limit": 5},
    ]
    assert fetch_tool.calls == []
