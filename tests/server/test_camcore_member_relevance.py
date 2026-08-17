"""Regression coverage for CamCore Outline retrieval relevance."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openjarvis.core.types import ToolResult
from openjarvis.server.camcore_member_knowledge import build_member_knowledge_context
from openjarvis.tools._stubs import ToolSpec


class _SearchTool:
    tool_id = "mcp_adapter"

    def __init__(self, client: object) -> None:
        self._client = client
        self.spec = ToolSpec(name="list_documents", description="test", parameters={})
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        query = params.get("query", "")
        if query == "CamCore documentation marker":
            content = "\n".join(
                [
                    json.dumps(
                        {
                            "document": {
                                "id": "doc-support-marker",
                                "title": "CamCore Support Email Replies",
                            },
                            "context": (
                                "CamCore notification emails ask users to reply "
                                "above the marker."
                            ),
                        }
                    ),
                    json.dumps(
                        {
                            "document": {
                                "id": "doc-validation",
                                "title": "Jarvis Member Knowledge Validation",
                            },
                            "context": (
                                "CamCore documentation marker: GREEN-WOMBAT-9642"
                            ),
                        }
                    ),
                    json.dumps(
                        {
                            "document": {
                                "id": "doc-runbook",
                                "title": "Operational Runbooks",
                            },
                            "context": "CamCore documentation lifecycle guidance.",
                        }
                    ),
                ]
            )
        else:
            content = "\n".join(
                json.dumps(
                    {
                        "document": {
                            "id": f"doc-runbook-{index}",
                            "title": f"Operations Runbook {index}",
                        },
                        "context": "General CamCore documentation and troubleshooting.",
                    }
                )
                for index in range(1, 6)
            )
        return ToolResult(tool_name="list_documents", content=content, success=True)


class _FetchTool:
    tool_id = "mcp_adapter"

    def __init__(self, client: object) -> None:
        self._client = client
        self.spec = ToolSpec(name="fetch", description="test", parameters={})
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        document_id = params.get("id")
        if document_id == "doc-validation":
            title = "Jarvis Member Knowledge Validation"
            content = "CamCore documentation marker: GREEN-WOMBAT-9642"
        elif document_id == "doc-support-marker":
            title = "CamCore Support Email Replies"
            content = "Reply above the marker in CamCore notification emails."
        else:
            title = "Operations Runbook"
            content = "General CamCore documentation and troubleshooting steps."

        body = "\n".join(
            [
                json.dumps(
                    {
                        "document": {
                            "id": document_id,
                            "title": title,
                        }
                    }
                ),
                content,
            ]
        )
        return ToolResult(tool_name="fetch", content=body, success=True)


def test_phrase_ranking_beats_unrelated_support_marker_before_fetching():
    client = object()
    search = _SearchTool(client)
    fetch = _FetchTool(client)
    agent = MagicMock()
    agent._tools = [search, fetch]

    query = (
        "According to the current CamCore documentation, what is the CamCore "
        "documentation marker?"
    )
    context = build_member_knowledge_context(agent, query)

    assert search.calls == [
        {"query": query, "limit": 5},
        {"query": "CamCore documentation marker", "limit": 5},
    ]
    assert fetch.calls[0] == {"resource": "document", "id": "doc-validation"}
    assert len(fetch.calls) <= 2
    assert "GREEN-WOMBAT-9642" in context
    assert "Jarvis Member Knowledge Validation" in context
    assert "Reply above the marker" not in context
    assert "CamCore Support Email Replies" not in context
    assert "General CamCore documentation and troubleshooting steps." not in context
