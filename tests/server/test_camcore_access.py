"""Security tests for CamCore trusted-proxy identity and route isolation."""

from __future__ import annotations

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


def _headers(role: str = "member") -> dict[str, str]:
    return {
        "X-CamCore-Proxy-Secret": "proxy-test-secret",
        "X-CamCore-Subject": f"test-{role}",
        "X-CamCore-Role": role,
        "X-CamCore-Email": f"{role}@camcore.au",
        "X-CamCore-Display-Name": f"Test {role.title()}",
    }


def test_member_identity_is_accepted_but_generic_api_is_denied(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    identity = client.get("/v1/camcore/portal/identity", headers=_headers("member"))
    assert identity.status_code == 200
    assert identity.json()["role"] == "member"
    assert identity.json()["display_name"] == "Test Member"

    generic = client.get("/v1/models", headers=_headers("member"))
    assert generic.status_code == 403
    assert "administrator" in generic.json()["detail"]


def test_member_cannot_escalate_provider_role_with_query_parameter(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    response = client.get(
        "/v1/camcore/portal/providers?role=admin",
        headers=_headers("member"),
    )
    assert response.status_code == 200
    assert response.json()["autoResolved"] == "local"


def test_member_cannot_call_operations_api(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    response = client.get(
        "/v1/camcore/operations/capabilities",
        headers=_headers("member"),
    )
    assert response.status_code == 403


def test_admin_can_use_generic_and_operations_apis(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    models = client.get("/v1/models", headers=_headers("admin"))
    assert models.status_code == 200

    capabilities = client.get(
        "/v1/camcore/operations/capabilities",
        headers=_headers("admin"),
    )
    assert capabilities.status_code == 200
    ids = {item["id"] for item in capabilities.json()["capabilities"]}
    assert "docker.containers.read" in ids
    assert "synology.storage.read" in ids


def test_invalid_proxy_secret_fails_closed(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.setenv("CAMCORE_PROXY_IDENTITY_SECRET", "proxy-test-secret")
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    headers = _headers("admin")
    headers["X-CamCore-Proxy-Secret"] = "wrong"
    response = client.get("/v1/models", headers=headers)
    assert response.status_code == 401


def test_missing_server_proxy_secret_is_service_unavailable(monkeypatch):
    monkeypatch.setenv("CAMCORE_ACCESS_MODE", "trusted-proxy")
    monkeypatch.delenv("CAMCORE_PROXY_IDENTITY_SECRET", raising=False)
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    response = client.get("/v1/models", headers=_headers("admin"))
    assert response.status_code == 503


def test_legacy_mode_preserves_upstream_api_compatibility(monkeypatch):
    monkeypatch.delenv("CAMCORE_ACCESS_MODE", raising=False)
    monkeypatch.delenv("CAMCORE_PROXY_IDENTITY_SECRET", raising=False)
    client = TestClient(create_app(_engine(), "server-model", config=_config()))

    response = client.get("/v1/models")
    assert response.status_code == 200
