"""Regression coverage for MCP-backed CamCore capability detection."""

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


def test_outline_capability_uses_mcp_spec_names(monkeypatch):
    """MCP adapters share one tool_id; their concrete spec names must survive."""

    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")

    agent = SimpleNamespace(
        agent_id="camcore_assistant",
        _tools=[
            SimpleNamespace(
                tool_id="mcp_adapter",
                spec=SimpleNamespace(name="camcore-outline:list_documents"),
            ),
            SimpleNamespace(
                tool_id="mcp_adapter",
                spec=SimpleNamespace(name="camcore-outline:fetch"),
            ),
            SimpleNamespace(tool_id="camcore_portainer_overview"),
        ],
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
    assert capabilities["knowledge.outline.read"]["evidence"] == "documented"
    assert capabilities["docker.containers.read"]["available"] is True
