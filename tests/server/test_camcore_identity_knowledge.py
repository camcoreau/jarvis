"""Regression tests for CamCore/Jarvis identity knowledge retrieval."""

from __future__ import annotations

import json

from openjarvis.core.types import ToolResult
from openjarvis.server.camcore_member_knowledge import (
    _query_terms,
    _relevant_excerpt,
    build_member_knowledge_context,
)
from openjarvis.tools._stubs import ToolSpec


class _IdentityListTool:
    tool_id = "mcp_adapter"

    def __init__(self, client) -> None:
        self._client = client
        self.spec = ToolSpec(
            name="camcore-outline:list_documents",
            description="test",
            parameters={},
        )
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        query = params.get("query")
        if query == "CamCore":
            content = json.dumps(
                [
                    {
                        "document": {
                            "id": "doc-definition",
                            "title": "CamCore",
                        },
                        "context": (
                            "CamCore is a privately owned and operated family "
                            "technology network."
                        ),
                    }
                ]
            )
        else:
            # Reproduce the edge case that previously suppressed the focused retry:
            # the broad conversational search returns exactly one result.
            content = json.dumps(
                [
                    {
                        "document": {
                            "id": "doc-generic",
                            "title": "Operations Notes",
                        },
                        "context": "CamCore operational notes.",
                    }
                ]
            )
        return ToolResult(tool_name=self.spec.name, content=content, success=True)


class _IdentityFetchTool:
    tool_id = "mcp_adapter"

    def __init__(self, client) -> None:
        self._client = client
        self.spec = ToolSpec(
            name="camcore-outline:fetch",
            description="test",
            parameters={},
        )
        self.calls: list[dict] = []

    def execute(self, **params):
        self.calls.append(params)
        document_id = params["id"]
        if document_id == "doc-definition":
            body = (
                "CamCore is a privately owned and operated family technology "
                "network that delivers secure, reliable and professionally "
                "managed digital services for the Cameron household, "
                "Cameron-Media and associated family operations."
            )
            title = "CamCore"
        else:
            body = "CamCore operational notes for administrators."
            title = "Operations Notes"
        content = "\n".join(
            [
                json.dumps({"document": {"id": document_id, "title": title}}),
                body,
            ]
        )
        return ToolResult(tool_name=self.spec.name, content=content, success=True)


def _identity_agent():
    client = object()
    list_tool = _IdentityListTool(client)
    fetch_tool = _IdentityFetchTool(client)

    class _Agent:
        _tools = [list_tool, fetch_tool]

    return _Agent(), list_tool, fetch_tool


def test_camcore_identity_query_keeps_identity_noun_as_excerpt_anchor():
    assert _query_terms("What is CamCore?") == {"camcore"}


def test_specific_camcore_query_still_prefers_distinctive_subject():
    assert _query_terms("What is Earth in CamCore?") == {"earth"}


def test_identity_excerpt_can_use_fresh_canonical_definition():
    raw = "\n".join(
        [
            json.dumps({"document": {"id": "doc-definition", "title": "CamCore"}}),
            "# CamCore",
            (
                "CamCore is a privately owned and operated family technology "
                "network."
            ),
        ]
    )
    excerpt = _relevant_excerpt(raw, "What is CamCore?")
    assert "privately owned and operated family technology network" in excerpt


def test_identity_query_forces_focused_search_even_after_one_broad_match():
    agent, list_tool, fetch_tool = _identity_agent()

    context = build_member_knowledge_context(agent, "What is CamCore?")

    assert list_tool.calls == [
        {"query": "What is CamCore?", "limit": 5},
        {"query": "CamCore", "limit": 5},
    ]
    assert fetch_tool.calls[0] == {"resource": "document", "id": "doc-definition"}
    assert "APPROVED CAMCORE MEMBER KNOWLEDGE" in context
    assert "privately owned and operated family technology network" in context
