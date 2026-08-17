"""Regression tests for fresh fetched Outline content in member chat."""

from __future__ import annotations

import json

from openjarvis.core.types import ToolResult
from openjarvis.server.camcore_member_knowledge import build_member_knowledge_context
from openjarvis.tools._stubs import ToolSpec


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


def test_fresh_fetch_wins_over_stale_outline_search_context():
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
                "The validation device is called Test Moon.",
            ]
        ),
    )

    class _Agent:
        _tools = [search, fetch]

    query = (
        "According to the current CamCore documentation, what is the CamCore "
        "validation phrase?"
    )
    context = build_member_knowledge_context(_Agent(), query)

    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in context
    assert "SILVER-KOALA-4821" in context
    assert "BLUE-ORCHID-7319" not in context
    assert "Search context" not in context
    assert search.calls == [{"query": query, "limit": 5}]
    assert fetch.calls == [{"resource": "document", "id": "validation-doc"}]


def test_stale_search_snippet_is_not_used_when_fetch_has_no_relevant_excerpt():
    client = object()
    search = _FakeMcpTool(
        "list_documents",
        client,
        json.dumps(
            {
                "document": {"id": "validation-doc", "title": "Validation"},
                "context": "CamCore validation phrase: BLUE-ORCHID-7319",
            }
        ),
    )
    fetch = _FakeMcpTool(
        "fetch",
        client,
        (
            '{"document":{"id":"validation-doc","title":"Validation"}}\n'
            "Unrelated text."
        ),
    )

    class _Agent:
        _tools = [search, fetch]

    context = build_member_knowledge_context(
        _Agent(),
        "What is the CamCore validation phrase?",
    )

    assert context == ""
    assert "BLUE-ORCHID-7319" not in context
