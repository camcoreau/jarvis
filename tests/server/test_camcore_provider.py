"""Tests for CamCore Local/OpenAI provider policy."""

from __future__ import annotations

import pytest

from openjarvis.server.camcore_provider import provider_status, resolve_provider


class _Engine:
    def __init__(
        self,
        models: list[str],
        *,
        unhealthy_models: set[str] | None = None,
    ):
        self._models = models
        self._unhealthy_models = unhealthy_models or set()

    def list_models(self) -> list[str]:
        return list(self._models)

    def health(self) -> bool:
        return True

    def can_serve(self, model: str) -> bool:
        if model in self._unhealthy_models:
            return False
        if model in self._models:
            return True
        return model.startswith("gpt-") and any(
            item.startswith("gpt-") for item in self._models
        )


def _env(**overrides: str) -> dict[str, str]:
    values = {
        "OPENAI_API_KEY": "test-token",
        "CAMCORE_OPENAI_MODEL": "gpt-5.6",
        "CAMCORE_OPENAI_FALLBACK_LOCAL": "true",
        "CAMCORE_MEMBER_OPENAI_ENABLED": "true",
        "CAMCORE_ADMIN_OPENAI_ENABLED": "true",
        "CAMCORE_MEMBER_AUTO_PROVIDER": "local",
        "CAMCORE_ADMIN_AUTO_PROVIDER": "local",
    }
    values.update(overrides)
    return values


def test_member_auto_is_local_first_by_default():
    decision = resolve_provider(
        "auto",
        role="member",
        engine=_Engine(["qwen3.5:4b", "gpt-5.4"]),
        local_model="qwen3.5:4b",
        environment=_env(),
    )
    assert decision.selected == "local"
    assert decision.model == "qwen3.5:4b"


def test_member_can_explicitly_choose_openai_when_configured():
    decision = resolve_provider(
        "openai",
        role="member",
        engine=_Engine(["qwen3.5:4b", "gpt-5.4"]),
        local_model="qwen3.5:4b",
        environment=_env(),
    )
    assert decision.selected == "openai"
    assert decision.model == "gpt-5.6"


def test_admin_auto_is_local_first_by_default():
    decision = resolve_provider(
        "auto",
        role="admin",
        engine=_Engine(["qwen3.5:4b", "gpt-5.4"]),
        local_model="qwen3.5:4b",
        environment=_env(),
    )
    assert decision.selected == "local"
    assert decision.model == "qwen3.5:4b"


def test_openai_falls_back_local_when_key_missing():
    decision = resolve_provider(
        "openai",
        role="member",
        engine=_Engine(["qwen3.5:4b", "gpt-5.4"]),
        local_model="qwen3.5:4b",
        environment=_env(OPENAI_API_KEY=""),
    )
    assert decision.selected == "local"
    assert decision.fallback_from == "openai"


def test_role_policy_can_disable_openai():
    status = provider_status(
        role="member",
        engine=_Engine(["qwen3.5:4b", "gpt-5.4"]),
        local_model="qwen3.5:4b",
        environment=_env(CAMCORE_MEMBER_OPENAI_ENABLED="false"),
    )
    cloud = next(item for item in status["providers"] if item["id"] == "openai")
    assert cloud["available"] is False
    assert status["autoResolved"] == "local"


def test_cloud_can_fail_closed_when_fallback_disabled():
    with pytest.raises(RuntimeError, match="OpenAI is not available"):
        resolve_provider(
            "openai",
            role="admin",
            engine=_Engine(["qwen3.5:4b"]),
            local_model="qwen3.5:4b",
            environment=_env(
                OPENAI_API_KEY="",
                CAMCORE_OPENAI_FALLBACK_LOCAL="false",
            ),
        )


def test_status_is_not_ready_when_local_model_is_unavailable():
    status = provider_status(
        role="member",
        engine=_Engine(
            ["qwen3.5:4b", "gpt-5.4"],
            unhealthy_models={"qwen3.5:4b"},
        ),
        local_model="qwen3.5:4b",
        environment=_env(),
    )
    providers = {item["id"]: item for item in status["providers"]}

    assert status["ready"] is False
    assert providers["auto"]["available"] is False
    assert providers["local"]["available"] is False
    assert providers["openai"]["available"] is True


def test_auto_does_not_silently_export_when_local_model_is_unavailable():
    with pytest.raises(RuntimeError, match="Local inference is not available"):
        resolve_provider(
            "auto",
            role="member",
            engine=_Engine(
                ["qwen3.5:4b", "gpt-5.4"],
                unhealthy_models={"qwen3.5:4b"},
            ),
            local_model="qwen3.5:4b",
            environment=_env(),
        )


def test_explicit_openai_remains_available_when_local_model_is_unhealthy():
    decision = resolve_provider(
        "openai",
        role="member",
        engine=_Engine(
            ["qwen3.5:4b", "gpt-5.4"],
            unhealthy_models={"qwen3.5:4b"},
        ),
        local_model="qwen3.5:4b",
        environment=_env(),
    )

    assert decision.selected == "openai"
    assert decision.model == "gpt-5.6"
    assert decision.fallback_allowed is False


def test_invalid_provider_is_rejected():
    with pytest.raises(ValueError, match="auto, local or openai"):
        resolve_provider(
            "other",
            role="member",
            engine=_Engine(["qwen3.5:4b"]),
            local_model="qwen3.5:4b",
            environment=_env(),
        )
