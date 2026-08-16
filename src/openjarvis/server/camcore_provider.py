"""CamCore Local/OpenAI provider policy for the signed-in portal.

Provider selection is deliberately server-side.  The browser may request a mode,
but this module decides whether that mode is permitted for the authenticated role
and whether the configured cloud provider is actually available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

VALID_PROVIDERS = frozenset({"auto", "local", "openai"})


def _env_bool(environment: Mapping[str, str], name: str, default: bool) -> bool:
    value = str(environment.get(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _role(role: str) -> str:
    return "admin" if str(role).strip().lower() == "admin" else "member"


def _auto_preference(environment: Mapping[str, str], role: str) -> str:
    key = (
        "CAMCORE_ADMIN_AUTO_PROVIDER"
        if _role(role) == "admin"
        else "CAMCORE_MEMBER_AUTO_PROVIDER"
    )
    default = "local" if _role(role) == "admin" else "openai"
    value = str(environment.get(key, default)).strip().lower()
    return value if value in {"local", "openai"} else default


def _openai_enabled(environment: Mapping[str, str], role: str) -> bool:
    key = (
        "CAMCORE_ADMIN_OPENAI_ENABLED"
        if _role(role) == "admin"
        else "CAMCORE_MEMBER_OPENAI_ENABLED"
    )
    return _env_bool(environment, key, True)


def openai_model(environment: Mapping[str, str] | None = None) -> str:
    env = environment or os.environ
    return str(env.get("CAMCORE_OPENAI_MODEL", "gpt-5.6")).strip() or "gpt-5.6"


def _engine_has_model(engine: object, model: str) -> bool:
    try:
        return model in set(engine.list_models())
    except Exception:
        return False


def openai_available(
    engine: object,
    role: str,
    environment: Mapping[str, str] | None = None,
) -> bool:
    env = environment or os.environ
    if not _openai_enabled(env, role):
        return False
    if not str(env.get("OPENAI_API_KEY", "")).strip():
        return False
    return _engine_has_model(engine, openai_model(env))


@dataclass(frozen=True, slots=True)
class ProviderDecision:
    requested: str
    selected: str
    model: str
    local_model: str
    openai_model: str
    fallback_allowed: bool
    fallback_from: str | None = None

    @property
    def is_cloud(self) -> bool:
        return self.selected == "openai"


def resolve_provider(
    requested: str,
    *,
    role: str,
    engine: object,
    local_model: str,
    environment: Mapping[str, str] | None = None,
) -> ProviderDecision:
    """Resolve a requested provider using CamCore role and availability policy."""

    env = environment or os.environ
    request_name = str(requested or "auto").strip().lower()
    if request_name not in VALID_PROVIDERS:
        raise ValueError("Provider must be auto, local or openai")

    cloud_model = openai_model(env)
    fallback = _env_bool(env, "CAMCORE_OPENAI_FALLBACK_LOCAL", True)
    cloud_available = openai_available(engine, role, env)

    selected = request_name
    if request_name == "auto":
        selected = _auto_preference(env, role)

    if selected == "openai" and not cloud_available:
        if not fallback:
            raise RuntimeError("OpenAI is not available for this CamCore session")
        return ProviderDecision(
            requested=request_name,
            selected="local",
            model=local_model,
            local_model=local_model,
            openai_model=cloud_model,
            fallback_allowed=fallback,
            fallback_from="openai",
        )

    return ProviderDecision(
        requested=request_name,
        selected=selected,
        model=cloud_model if selected == "openai" else local_model,
        local_model=local_model,
        openai_model=cloud_model,
        fallback_allowed=fallback,
    )


def provider_status(
    *,
    role: str,
    engine: object,
    local_model: str,
    environment: Mapping[str, str] | None = None,
) -> dict:
    """Return safe provider metadata for the CamCore portal UI."""

    env = environment or os.environ
    normalized_role = _role(role)
    available = openai_available(engine, normalized_role, env)
    cloud_model = openai_model(env)
    default_decision = resolve_provider(
        "auto",
        role=normalized_role,
        engine=engine,
        local_model=local_model,
        environment=env,
    )
    return {
        "default": "auto",
        "autoResolved": default_decision.selected,
        "fallbackLocal": _env_bool(env, "CAMCORE_OPENAI_FALLBACK_LOCAL", True),
        "providers": [
            {
                "id": "auto",
                "label": "Auto",
                "available": True,
                "model": (
                    cloud_model
                    if default_decision.selected == "openai"
                    else local_model
                ),
                "privacy": (
                    "cloud-possible"
                    if normalized_role == "member"
                    else "local-first"
                ),
            },
            {
                "id": "local",
                "label": "Local",
                "available": True,
                "model": local_model,
                "privacy": "camcore-only",
            },
            {
                "id": "openai",
                "label": "OpenAI",
                "available": available,
                "model": cloud_model,
                "privacy": "cloud",
            },
        ],
    }


__all__ = [
    "ProviderDecision",
    "VALID_PROVIDERS",
    "openai_available",
    "openai_model",
    "provider_status",
    "resolve_provider",
]
