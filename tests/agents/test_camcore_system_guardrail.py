"""Guardrails regressions for CamCore server-built Operations context."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openjarvis.agents._stubs import AgentContext
from openjarvis.agents.camcore_assistant import CamCoreAssistantAgent
from openjarvis.core.types import Message, Role
from openjarvis.security.guardrails import GuardrailsEngine, SecurityBlockError
from openjarvis.security.types import RedactionMode


def _block_security_config():
    return SimpleNamespace(
        security=SimpleNamespace(
            enabled=True,
            scan_input=True,
            mode="block",
            secret_scanner=True,
            pii_scanner=True,
        )
    )


class _PromptBuilder:
    def build(self):
        return "admin@example.com 192.0.2.44"


def _guarded_agent(prompt_builder=None):
    underlying = MagicMock()
    underlying.engine_id = "mock"
    underlying.generate.return_value = {
        "content": "Safe answer",
        "usage": {},
        "finish_reason": "stop",
    }
    guarded = GuardrailsEngine(underlying, mode=RedactionMode.BLOCK)
    agent = CamCoreAssistantAgent(guarded, "test-model", prompt_builder=prompt_builder)
    return agent, underlying


def test_server_built_system_prompt_is_redacted_in_block_mode(monkeypatch):
    agent, underlying = _guarded_agent(_PromptBuilder())
    monkeypatch.setattr("openjarvis.core.config.load_config", _block_security_config)

    result = agent.run("Check CamCore")

    assert result.content == "Safe answer"
    messages = underlying.generate.call_args.args[0]
    assert messages[0].role == Role.SYSTEM
    assert "admin@example.com" not in messages[0].content
    assert "192.0.2.44" not in messages[0].content
    assert "[REDACTED:email]" in messages[0].content
    assert "[REDACTED:ipv4_address]" in messages[0].content


def test_caller_system_message_remains_guardrails_scanned(monkeypatch):
    agent, _ = _guarded_agent()
    monkeypatch.setattr("openjarvis.core.config.load_config", _block_security_config)
    context = AgentContext()
    context.conversation.add(
        Message(role=Role.SYSTEM, content="Caller contact admin@example.com")
    )

    with pytest.raises(SecurityBlockError):
        agent.run("Check CamCore", context=context)
