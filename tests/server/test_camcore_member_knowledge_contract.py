"""Static security contract for CamCore member knowledge retrieval."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / "src/openjarvis/server/camcore_portal_routes.py"
KNOWLEDGE = ROOT / "src/openjarvis/server/camcore_member_knowledge.py"


def test_member_knowledge_route_stays_direct_model_only():
    routes = ROUTES.read_text(encoding="utf-8")
    member_block = routes.split('@router.post("/chat/completions")', 1)[1].split(
        '@router.post("/operations/chat/completions")', 1
    )[0]

    assert "build_member_knowledge_context" in member_block
    assert "_handle_direct" in member_block
    assert "_handle_agent" not in member_block
    assert "chat_completions(" not in member_block


def test_member_knowledge_tool_allowlist_and_redaction_contract():
    source = KNOWLEDGE.read_text(encoding="utf-8")

    assert '_ALLOWED_TOOL_NAMES = {"list_documents", "fetch"}' in source
    assert 'tool_id", None) != "mcp_adapter"' in source
    assert 'resource="document"' in source
    assert "_PRIVATE_HOST_RE" in source
    assert "_IPV4_RE" in source
    assert "_SECRET_LINE_RE" in source
    assert "_EMAIL_RE" in source
    assert "_MAX_CONTEXT_CHARS" in source
