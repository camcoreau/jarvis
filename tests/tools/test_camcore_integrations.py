"""Tests for CamCore's bounded read-only service integrations."""

from __future__ import annotations

import json

import httpx

from openjarvis.tools.camcore_integrations import (
    CamCoreBetterStackOverviewTool,
    CamCoreGitHubOverviewTool,
    CamCoreHomeAssistantStateTool,
    CamCoreM365ServiceHealthTool,
    CamCoreSynologyApiInventoryTool,
    CamCoreYouTrackOverviewTool,
)


def _response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, json=data, request=httpx.Request("GET", "https://example.test")
    )


def test_betterstack_returns_bounded_monitor_and_incident_fields(monkeypatch):
    monkeypatch.setenv("CAMCORE_BETTERSTACK_API_TOKEN", "secret-token")

    def request(method, url, **kwargs):
        del method, kwargs
        if url.endswith("/api/v2/monitors"):
            return _response(
                {
                    "data": [
                        {
                            "id": "1",
                            "attributes": {
                                "pronounceable_name": "Jarvis",
                                "status": "up",
                                "monitor_type": "status",
                                "last_checked_at": "2026-08-19T10:00:00Z",
                                "url": "https://private.example",
                                "request_headers": [
                                    {"name": "X-Secret", "value": "nope"}
                                ],
                            },
                        }
                    ],
                    "pagination": {"next": None},
                }
            )
        return _response(
            {
                "data": [
                    {
                        "id": "10",
                        "attributes": {
                            "name": "Example incident",
                            "cause": "Status 500",
                            "status": "Started",
                            "started_at": "2026-08-19T10:01:00Z",
                            "acknowledged_at": None,
                            "response_content": "secret body",
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "request", request)
    result = CamCoreBetterStackOverviewTool().execute()
    assert result.success is True
    payload = json.loads(result.content)
    assert payload["monitor_count"] == 1
    assert payload["active_incident_count"] == 1
    assert "private.example" not in result.content
    assert "request_headers" not in result.content
    assert "secret body" not in result.content
    assert "secret-token" not in result.content


def test_youtrack_returns_only_selected_operational_fields(monkeypatch):
    monkeypatch.setenv("CAMCORE_YOUTRACK_URL", "https://tasks.example")
    monkeypatch.setenv("CAMCORE_YOUTRACK_TOKEN", "yt-secret")
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _response(
            [
                {
                    "idReadable": "OPS-1",
                    "summary": "Investigate service",
                    "resolved": None,
                    "updated": 123,
                    "project": {"shortName": "OPS", "name": "Operations"},
                    "customFields": [
                        {"name": "Priority", "value": {"name": "Major"}},
                        {
                            "name": "SensitiveInternalField",
                            "value": {"text": "not returned"},
                        },
                    ],
                }
            ]
        ),
    )
    result = CamCoreYouTrackOverviewTool().execute()
    assert result.success is True
    payload = json.loads(result.content)
    assert payload["issues"][0]["id"] == "OPS-1"
    assert payload["issues"][0]["fields"]["Priority"] == "Major"
    assert "SensitiveInternalField" not in result.content
    assert "yt-secret" not in result.content


def test_homeassistant_requires_server_side_entity_allowlist(monkeypatch):
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_URL", "http://homeassistant:8123")
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_TOKEN", "ha-secret")
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_ENTITIES", "sensor.safe")

    called = False

    def request(*args, **kwargs):
        nonlocal called
        called = True
        return _response({})

    monkeypatch.setattr(httpx, "request", request)
    result = CamCoreHomeAssistantStateTool().execute(entity_id="device_tracker.private")
    assert result.success is False
    assert "not in the server-side allow-list" in result.content
    assert called is False


def test_homeassistant_drops_location_and_arbitrary_attributes(monkeypatch):
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_URL", "http://homeassistant:8123")
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_TOKEN", "ha-secret")
    monkeypatch.setenv("CAMCORE_HOMEASSISTANT_ENTITIES", "sensor.safe")
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _response(
            {
                "entity_id": "sensor.safe",
                "state": "23.4",
                "last_changed": "2026-08-19T10:00:00Z",
                "last_updated": "2026-08-19T10:00:01Z",
                "attributes": {
                    "friendly_name": "Safe sensor",
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "latitude": -38.0,
                    "longitude": 144.0,
                    "access_token": "never-return",
                },
            }
        ),
    )
    result = CamCoreHomeAssistantStateTool().execute(entity_id="sensor.safe")
    assert result.success is True
    assert "Safe sensor" in result.content
    assert "latitude" not in result.content
    assert "longitude" not in result.content
    assert "never-return" not in result.content
    assert "ha-secret" not in result.content


def test_m365_uses_client_credentials_but_never_returns_token(monkeypatch):
    monkeypatch.setenv("CAMCORE_M365_TENANT_ID", "tenant")
    monkeypatch.setenv("CAMCORE_M365_CLIENT_ID", "client")
    monkeypatch.setenv("CAMCORE_M365_CLIENT_SECRET", "client-secret")

    def request(method, url, **kwargs):
        del method, kwargs
        if "oauth2/v2.0/token" in url:
            return _response({"access_token": "graph-access-token"})
        if url.endswith("/healthOverviews"):
            return _response(
                {
                    "value": [
                        {
                            "id": "Exchange",
                            "service": "Exchange Online",
                            "status": "serviceOperational",
                        }
                    ]
                }
            )
        return _response(
            {
                "value": [
                    {
                        "id": "EX1",
                        "title": "Current service issue",
                        "service": "Exchange Online",
                        "status": "investigating",
                        "classification": "incident",
                        "startDateTime": "2026-08-19T10:00:00Z",
                        "lastModifiedDateTime": "2026-08-19T10:05:00Z",
                        "impactDescription": "Some users affected",
                        "isResolved": False,
                    },
                    {"id": "EX0", "title": "Old issue", "isResolved": True},
                ]
            }
        )

    monkeypatch.setattr(httpx, "request", request)
    result = CamCoreM365ServiceHealthTool().execute()
    assert result.success is True
    payload = json.loads(result.content)
    assert payload["service_count"] == 1
    assert payload["active_issue_count"] == 1
    assert payload["active_issues"][0]["id"] == "EX1"
    assert "graph-access-token" not in result.content
    assert "client-secret" not in result.content


def test_github_is_server_allowlisted_and_filters_pull_requests(monkeypatch):
    monkeypatch.setenv("CAMCORE_GITHUB_REPOSITORIES", "camcoreau/jarvis")
    monkeypatch.setenv("CAMCORE_GITHUB_TOKEN", "github-secret")

    def request(method, url, **kwargs):
        del method, kwargs
        if url.endswith("/issues"):
            return _response(
                [
                    {
                        "number": 1,
                        "title": "Issue",
                        "updated_at": "2026-08-19T10:00:00Z",
                    },
                    {
                        "number": 2,
                        "title": "PR",
                        "pull_request": {},
                        "updated_at": "2026-08-19T10:00:00Z",
                    },
                ]
            )
        if url.endswith("/actions/runs"):
            return _response(
                {
                    "workflow_runs": [
                        {
                            "name": "CI",
                            "event": "push",
                            "status": "completed",
                            "conclusion": "success",
                            "head_branch": "main",
                            "updated_at": "2026-08-19T10:00:00Z",
                        }
                    ]
                }
            )
        return _response(
            {
                "full_name": "camcoreau/jarvis",
                "default_branch": "main",
                "updated_at": "2026-08-19T10:00:00Z",
            }
        )

    monkeypatch.setattr(httpx, "request", request)
    result = CamCoreGitHubOverviewTool().execute()
    assert result.success is True
    payload = json.loads(result.content)
    repo = payload["repositories"][0]
    assert repo["open_issue_count"] == 1
    assert repo["recent_workflow_runs"][0]["conclusion"] == "success"
    assert "github-secret" not in result.content


def test_synology_inventory_never_claims_storage_health(monkeypatch):
    monkeypatch.setenv("CAMCORE_SYNOLOGY_URL", "https://nas.example")
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _response(
            {
                "success": True,
                "data": {
                    "SYNO.API.Auth": {
                        "minVersion": 1,
                        "maxVersion": 7,
                        "path": "entry.cgi",
                    },
                    "SYNO.Storage.CGI.Storage": {
                        "minVersion": 1,
                        "maxVersion": 1,
                        "path": "entry.cgi",
                    },
                    "SYNO.FileStation.List": {
                        "minVersion": 1,
                        "maxVersion": 2,
                        "path": "entry.cgi",
                    },
                },
            }
        ),
    )
    result = CamCoreSynologyApiInventoryTool().execute()
    assert result.success is True
    payload = json.loads(result.content)
    assert payload["kind"] == "capability-discovery"
    assert "SYNO.Storage.CGI.Storage" in payload["apis"]
    assert "does not prove physical disk" in payload["warning"]
    assert "SYNO.FileStation.List" not in payload["apis"]
