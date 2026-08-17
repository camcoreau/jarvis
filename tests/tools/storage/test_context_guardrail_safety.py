"""Regression tests for Guardrails-safe automatic memory injection."""

from __future__ import annotations

from types import SimpleNamespace

from openjarvis.core.types import Message, Role
from openjarvis.security.guardrails import GuardrailsEngine
from openjarvis.security.types import RedactionMode
from openjarvis.tools.storage._stubs import RetrievalResult
from openjarvis.tools.storage.context import inject_context


class _Backend:
    def retrieve(self, query: str, *, top_k: int = 5):
        return [
            RetrievalResult(
                content=(
                    "Remembered CamCore contact admin@example.com and test host "
                    "192.0.2.44."
                ),
                score=1.0,
                source="memory",
            )
        ]


def _block_config():
    return SimpleNamespace(
        security=SimpleNamespace(
            enabled=True,
            scan_input=True,
            mode="block",
            secret_scanner=True,
            pii_scanner=True,
        )
    )


def test_block_mode_pre_redacts_memory_before_system_prompt_merge(monkeypatch):
    monkeypatch.setattr("openjarvis.core.config.load_config", _block_config)

    messages = [
        Message(role=Role.SYSTEM, content="Base system prompt"),
        Message(role=Role.USER, content="What is the CamCore documentation marker?"),
    ]
    enriched = inject_context(
        "What is the CamCore documentation marker?",
        messages,
        _Backend(),
    )

    assert enriched[0].role == Role.SYSTEM
    assert "Base system prompt" in enriched[0].content
    assert "admin@example.com" not in enriched[0].content
    assert "192.0.2.44" not in enriched[0].content
    assert "[REDACTED:email]" in enriched[0].content
    assert "[REDACTED:ipv4_address]" in enriched[0].content

    class _Engine:
        engine_id = "test"

        def generate(self, messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
            return {
                "content": "Memory-safe answer",
                "usage": {},
                "finish_reason": "stop",
            }

        def list_models(self):
            return ["test-model"]

        def health(self):
            return True

    guarded = GuardrailsEngine(_Engine(), mode=RedactionMode.BLOCK)
    result = guarded.generate(enriched, model="test-model")
    assert result["content"] == "Memory-safe answer"


def test_non_block_mode_preserves_existing_memory_behaviour(monkeypatch):
    config = _block_config()
    config.security.mode = "redact"
    monkeypatch.setattr("openjarvis.core.config.load_config", lambda: config)

    messages = [Message(role=Role.USER, content="Recall my CamCore contact")]
    enriched = inject_context("Recall my CamCore contact", messages, _Backend())

    assert "admin@example.com" in enriched[0].content
    assert "192.0.2.44" in enriched[0].content
