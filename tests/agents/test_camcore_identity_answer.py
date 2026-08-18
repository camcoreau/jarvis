"""Regression tests for deterministic CamCore identity answers."""

from __future__ import annotations

from unittest.mock import MagicMock

from openjarvis.agents.camcore_assistant import (
    CAMCORE_CANONICAL_DEFINITION,
    CamCoreAssistantAgent,
    _is_camcore_identity_question,
)


def _engine() -> MagicMock:
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.generate.return_value = {
        "content": "model should not be called",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "finish_reason": "stop",
    }
    return engine


def test_direct_camcore_identity_question_returns_canonical_definition_without_model():
    engine = _engine()
    agent = CamCoreAssistantAgent(engine, "test-model")

    result = agent.run("What is CamCore?")

    assert result.content == CAMCORE_CANONICAL_DEFINITION
    assert result.turns == 0
    assert result.metadata["camcore_canonical_identity"] is True
    engine.generate.assert_not_called()


def test_identity_variants_are_narrowly_recognised():
    assert _is_camcore_identity_question("What is CamCore?")
    assert _is_camcore_identity_question("Explain CamCore")
    assert _is_camcore_identity_question("Tell me about CamCore.")
    assert not _is_camcore_identity_question("What is Earth in CamCore?")
    assert not _is_camcore_identity_question("What is CamCore's current status?")
