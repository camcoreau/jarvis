"""CamCore Local/OpenAI provider policy for the signed-in portal.

Provider selection is deliberately server-side. The browser may request a mode,
but this module decides whether that mode is permitted for the authenticated role
and whether the configured cloud provider is actually available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from openjarvis.engine.cloud import PRICING

VALID_PROVIDERS = frozenset({"auto", "local", "openai"})

# OpenAI's gpt-5.6 alias routes to GPT-5.6 Sol. Defining the exact alias here
# prevents CloudEngine's generic prefix pricing lookup from matching the older
# gpt-5 entry first. Cached-input pricing is not represented by the upstream
# two-value PRICING structure, so this records the standard input/output rates.
PRICING["gpt-5.6"] = (5.00, 30.00)


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
    # CamCore is local-first for every role. Cloud inference remains an explicit
    # option when enabled and configured.
    default = "local"
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


def _engine_has_openai(engine: object, model: str) -> bool:
    try:
        if not engine.health() or not engine.can_serve(model):
            return False
        models = set(engine.list_models())
    except Exception:
        return False
    if model in models:
        return True
    # MultiEngine advertises CloudEngine's curated model list. A newly released
    # gpt-* alias can still be routable before that curated list is updated, so
    # any advertised gpt-* model proves the OpenAI client is active and
    # MultiEngine can route the requested alias by prefix.
    return model.startswith("gpt-") and any(item.startswith("gpt-") for item in models)


def _local_available(engine: object, model: str) -> bool:
    """Return whether the configured local model is currently serviceable."""

    try:
        if not engine.health() or not engine.can_serve(model):
            return False
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
    return _engine_has_openai(engine, openai_model(env))


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
    local_available = _local_available(engine, local_model)

    selected = request_name
    if request_name == "auto":
        selected = _auto_preference(env, role)

    if selected == "openai" and not cloud_available:
        if not fallback or not local_available:
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

    if selected == "local" and not local_available:
        raise RuntimeError("Local inference is not available for this CamCore session")

    return ProviderDecision(
        requested=request_name,
        selected=selected,
        model=cloud_model if selected == "openai" else local_model,
        local_model=local_model,
        openai_model=cloud_model,
        fallback_allowed=fallback and local_available,
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
    cloud_available = openai_available(engine, normalized_role, env)
    local_available = _local_available(engine, local_model)
    cloud_model = openai_model(env)
    auto_resolved = _auto_preference(env, normalized_role)
    auto_available = local_available
    if auto_resolved == "openai":
        if cloud_available:
            auto_available = True
        elif _env_bool(env, "CAMCORE_OPENAI_FALLBACK_LOCAL", True):
            auto_resolved = "local"
            auto_available = local_available
        else:
            auto_available = False
    return {
        "ready": auto_available,
        "default": "auto",
        "autoResolved": auto_resolved,
        "fallbackLocal": _env_bool(env, "CAMCORE_OPENAI_FALLBACK_LOCAL", True),
        "providers": [
            {
                "id": "auto",
                "label": "Auto",
                "available": auto_available,
                "model": (cloud_model if auto_resolved == "openai" else local_model),
                "privacy": (
                    "cloud-possible" if auto_resolved == "openai" else "camcore-only"
                ),
            },
            {
                "id": "local",
                "label": "Local",
                "available": local_available,
                "model": local_model,
                "privacy": "camcore-only",
            },
            {
                "id": "openai",
                "label": "OpenAI",
                "available": cloud_available,
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
