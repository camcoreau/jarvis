"""Static contracts for the CamCore Portal deployment and repository CI."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_jarvis_waits_for_model_install_and_probes_readiness():
    compose = _read("deploy/camcore/compose.yaml")

    assert "ollama-model:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "condition: service_healthy" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "urlopen('http://127.0.0.1:8000/'," not in compose


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
