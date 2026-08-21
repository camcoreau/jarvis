"""Static contracts for the CamCore deployment and repository CI."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OLLAMA_IMAGE = (
    "ollama/ollama:0.32.15@"
    "sha256:57d60e686821ea81a7748a3ec8141308c8b8f95b27105713954abf7a6529e700"
)


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_jarvis_waits_for_model_install_and_probes_readiness():
    compose = _read("deploy/camcore/compose.yaml")

    assert "ollama-model:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "condition: service_healthy" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "urlopen('http://127.0.0.1:8000/'," not in compose


def test_only_ollama_joins_the_external_ai_frontend_network():
    compose = yaml.safe_load(_read("deploy/camcore/compose.yaml"))
    services = compose["services"]

    assert "open-webui" not in services
    assert set(compose["volumes"]) == {"jarvis-data", "ollama-models"}
    assert compose["networks"]["ai"] == {
        "external": True,
        "name": "${CAMCORE_AI_NETWORK:-camcore-ai-backend}",
    }
    assert compose["networks"]["jarvis-ai"] == {
        "name": "camcore-jarvis-ai",
        "driver": "bridge",
    }
    assert services["ollama"]["networks"] == {
        "ai": {"aliases": ["camcore-ollama"]},
        "jarvis-ai": None,
    }
    assert services["ollama-model"]["networks"] == ["jarvis-ai"]
    assert services["jarvis"]["networks"] == ["jarvis-ai", "proxy"]
    assert [
        service_name
        for service_name, service in services.items()
        if "ai" in service.get("networks", [])
    ] == ["ollama"]


def test_ollama_release_and_cpu_limits_are_explicit():
    compose = yaml.safe_load(_read("deploy/camcore/compose.yaml"))
    services = compose["services"]

    assert services["ollama"]["image"] == OLLAMA_IMAGE
    assert services["ollama-model"]["image"] == OLLAMA_IMAGE
    assert services["ollama"]["environment"] == {
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_CONTEXT_LENGTH": "${CAMCORE_OLLAMA_CONTEXT_LENGTH:-8192}",
        "OLLAMA_MAX_LOADED_MODELS": "${CAMCORE_OLLAMA_MAX_LOADED_MODELS:-1}",
        "OLLAMA_NUM_PARALLEL": "${CAMCORE_OLLAMA_NUM_PARALLEL:-1}",
        "OLLAMA_MAX_QUEUE": "${CAMCORE_OLLAMA_MAX_QUEUE:-32}",
        "OLLAMA_KEEP_ALIVE": "${CAMCORE_OLLAMA_KEEP_ALIVE:-10m}",
        "TZ": "${CAMCORE_TZ:-Australia/Melbourne}",
    }
    assert "ports" not in services["ollama"]


def test_frontend_configuration_is_owned_outside_the_jarvis_repository():
    compose = _read("deploy/camcore/compose.yaml")
    env_example = _read("deploy/camcore/.env.example")

    assert not (REPO_ROOT / "deploy/camcore/OPEN-WEBUI.md").exists()
    assert "open-webui" not in compose.lower()
    assert "CAMCORE_AI_NETWORK=camcore-ai-backend" in env_example
    assert "CAMCORE_AI_MICROSOFT_" not in env_example
    assert "CAMCORE_AI_WEBUI_" not in env_example
    assert "CAMCORE_AI_OAUTH_" not in env_example


def test_tag_free_fork_skips_rolling_release_without_masking_pipefail():
    workflow = _read(".github/workflows/autotag.yml")

    assert "tail -1 || true" in workflow
    assert 'echo "enabled=false" >> "$GITHUB_OUTPUT"' in workflow
    assert "if: steps.version.outputs.enabled == 'true'" in workflow


def test_docs_always_build_but_pages_publish_requires_opt_in():
    workflow = _read(".github/workflows/docs.yml")

    assert "uv run mkdocs build" in workflow
    assert workflow.count('".github/workflows/docs.yml"') == 2
    assert workflow.count('"pyproject.toml"') == 2
    assert workflow.count('"uv.lock"') == 2
    assert workflow.count("vars.CAMCORE_DOCS_PAGES_ENABLED == 'true'") == 2
    assert workflow.index("uv run mkdocs build") < workflow.index(
        "vars.CAMCORE_DOCS_PAGES_ENABLED == 'true'"
    )


def test_desktop_validation_has_read_only_repository_permissions():
    workflow = yaml.safe_load(_read(".github/workflows/desktop.yml"))

    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["validate"]
    for job in ("clean-release", "build-and-release", "refresh-stable-channel"):
        assert workflow["jobs"][job]["permissions"] == {"contents": "write"}
