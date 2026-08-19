"""Tests for CamCore Operations capability truthfulness."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.app import create_app  # noqa: E402


def _config() -> JarvisConfig:
    config = JarvisConfig()
    config.analytics.enabled = False
    config.traces.enabled = False
    return config


def _engine():
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.health.return_value = True
    engine.list_models.return_value = ["server-model"]
    return engine


def _admin_headers() -> dict[str, str]:
    return {
        "X-CamCore-Proxy-Secret": "proxy-test-secret",
        "X-CamCore-Subject": "admin-subject",
        "X-CamCore-Role": "admin",
    }


def _agent(tool_ids: list[str]):
    return SimpleNamespace(
        agent_id="camcore_assistant",
        _tools=[SimpleNamespace(tool_id=tool_id) for tool_id in tool_ids],
    )


def test_inventory_reports_attached_tools_without_inventing_missing_integrations(
    monkeypatch,
):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    agent = _agent(
        [
            "list_documents",
            "fetch",
            "camcore_portainer_overview",
            "camcore_portainer_container_logs",
            "camcore_portainer_container_action",
        ]
    )
    client = TestClient(
        create_app(_engine(), "server-model", agent=agent, config=_config())
    )

    response = client.get(
        "/v1/camcore/operations/capabilities",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    capabilities = {item["id"]: item for item in response.json()["capabilities"]}

    assert capabilities["knowledge.outline.read"]["available"] is True
    assert capabilities["docker.containers.read"]["available"] is True
    assert capabilities["docker.containers.control"]["requires_confirmation"] is True
    assert capabilities["synology.storage.read"]["available"] is False
    assert capabilities["m365.servicehealth.read"]["available"] is False
    assert capabilities["youtrack.operations.read"]["available"] is False
    assert capabilities["media.status.read"]["available"] is False


def test_inventory_does_not_treat_documentation_as_live_health(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    agent = _agent(["list_documents", "fetch"])
    client = TestClient(
        create_app(_engine(), "server-model", agent=agent, config=_config())
    )

    response = client.get(
        "/v1/camcore/operations/capabilities",
        headers=_admin_headers(),
    )
    capabilities = {item["id"]: item for item in response.json()["capabilities"]}

    assert capabilities["knowledge.outline.read"]["evidence"] == "documented"
    assert capabilities["docker.containers.read"]["available"] is False
    assert capabilities["monitoring.health.read"]["available"] is False
    assert capabilities["synology.storage.read"]["available"] is False


def test_inventory_surfaces_read_only_operations_integrations(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    agent = _agent(
        [
            "camcore_betterstack_overview",
            "camcore_youtrack_overview",
            "camcore_homeassistant_state",
            "camcore_m365_service_health",
            "camcore_github_overview",
            "camcore_tautulli_activity",
            "camcore_synology_api_inventory",
        ]
    )
    client = TestClient(
        create_app(_engine(), "server-model", agent=agent, config=_config())
    )

    response = client.get(
        "/v1/camcore/operations/capabilities",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    capabilities = {item["id"]: item for item in response.json()["capabilities"]}

    assert capabilities["monitoring.health.read"]["available"] is True
    assert capabilities["youtrack.operations.read"]["available"] is True
    assert capabilities["homeassistant.state.read"]["available"] is True
    assert capabilities["m365.servicehealth.read"]["available"] is True
    assert capabilities["github.operations.read"]["available"] is True
    assert capabilities["media.status.read"]["available"] is True
    assert capabilities["synology.api.discovery"]["available"] is True
    # Discovery never promotes DSM storage health into a live capability.
    assert capabilities["synology.storage.read"]["available"] is False
