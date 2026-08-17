"""Tests for the CamCore Portainer operations connector."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import openjarvis.tools.camcore_portainer as portainer


_ENDPOINT = {
    "Id": 2,
    "Name": "ganymede",
    "Status": 1,
    "URL": "tcp://secret:9001",
}
_CONTAINER = {
    "Id": "abcdef1234567890",
    "Names": ["/camcore-status"],
    "Image": "ghcr.io/camcoreau/camcore-status:test",
    "State": "running",
    "Status": "Up 30 minutes (healthy)",
    "Labels": {"secret": "must-not-return"},
}


def _inspect_payload() -> dict:
    return {
        "Id": _CONTAINER["Id"],
        "Name": "/camcore-status",
        "RestartCount": 1,
        "Config": {
            "Image": _CONTAINER["Image"],
            "Env": [
                "API_KEY=must-not-return",
                "PASSWORD=must-not-return",
            ],
            "Labels": {"secret": "must-not-return"},
        },
        "State": {
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "ExitCode": 0,
            "StartedAt": "2026-08-17T12:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "Health": {
                "Status": "healthy",
                "Log": [{"Output": "secret"}],
            },
        },
        "NetworkSettings": {
            "Networks": {
                "proxy": {"IPAddress": "192.168.5.200"},
                "backend": {"IPAddress": "172.30.0.20"},
            }
        },
        "Mounts": [
            {
                "Source": "/volume2/private/source",
                "Destination": "/data",
            },
        ],
    }


def _stats_payload() -> dict:
    return {
        "cpu_stats": {
            "cpu_usage": {
                "total_usage": 300,
                "percpu_usage": [1, 1],
            },
            "system_cpu_usage": 2_000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 1_000,
        },
        "memory_stats": {
            "usage": 104_857_600,
            "limit": 536_870_912,
        },
        "networks": {
            "eth0": {
                "rx_bytes": 1_048_576,
                "tx_bytes": 2_097_152,
            },
        },
    }


class TestCamCorePortainerSpecs:
    def test_read_tools_are_not_confirmation_gated(self):
        overview = portainer.CamCorePortainerOverviewTool()
        status = portainer.CamCorePortainerContainerStatusTool()
        logs = portainer.CamCorePortainerContainerLogsTool()
        assert overview.spec.requires_confirmation is False
        assert status.spec.requires_confirmation is False
        assert logs.spec.requires_confirmation is False

    def test_mutation_tool_requires_confirmation_and_system_admin(self):
        spec = portainer.CamCorePortainerContainerActionTool().spec
        assert spec.requires_confirmation is True
        assert "system:admin" in spec.required_capabilities
        assert spec.parameters["properties"]["action"]["enum"] == [
            "start",
            "stop",
            "restart",
        ]

    def test_tools_do_not_accept_arbitrary_urls_or_headers(self):
        tools = (
            portainer.CamCorePortainerOverviewTool(),
            portainer.CamCorePortainerContainerStatusTool(),
            portainer.CamCorePortainerContainerLogsTool(),
            portainer.CamCorePortainerContainerActionTool(),
        )
        for tool in tools:
            properties = tool.spec.parameters.get("properties", {})
            assert "url" not in properties
            assert "headers" not in properties
            assert "api_key" not in properties


class TestCamCorePortainerRedaction:
    def test_redaction_failure_fails_closed(self):
        with patch(
            "openjarvis.security.scanner.SecretScanner",
            side_effect=RuntimeError("scanner unavailable"),
        ):
            result = portainer._redact_sensitive("API_KEY=must-not-return")
        assert result == portainer._REDACTION_FAILURE
        assert "must-not-return" not in result


class TestCamCorePortainerOverview:
    def test_missing_server_side_configuration_is_explicit(self):
        with patch.dict(
            os.environ,
            {
                "CAMCORE_PORTAINER_URL": "",
                "CAMCORE_PORTAINER_API_KEY": "",
            },
            clear=False,
        ):
            result = portainer.CamCorePortainerOverviewTool().execute()
        assert result.success is False
        assert "CAMCORE_PORTAINER_URL" in result.content
        assert "CAMCORE_PORTAINER_API_KEY" in result.content

    def test_overview_returns_allow_listed_live_container_state(self):
        with patch.object(
            portainer._PortainerClient,
            "json",
            side_effect=[[_ENDPOINT], [_CONTAINER]],
        ):
            result = portainer.CamCorePortainerOverviewTool().execute()
        assert result.success is True
        payload = json.loads(result.content)
        environment = payload["environments"][0]
        assert environment["name"] == "ganymede"
        assert environment["container_count"] == 1
        assert environment["unhealthy"] == 0
        assert environment["containers"][0]["health"] == "healthy"
        assert "secret:9001" not in result.content
        assert "must-not-return" not in result.content


class TestCamCorePortainerContainerStatus:
    def test_status_returns_resource_usage_without_sensitive_fields(self):
        responses = [
            [_ENDPOINT],
            [_CONTAINER],
            _inspect_payload(),
            _stats_payload(),
        ]
        with patch.object(
            portainer._PortainerClient,
            "json",
            side_effect=responses,
        ):
            result = portainer.CamCorePortainerContainerStatusTool().execute(
                container="camcore-status"
            )
        assert result.success is True
        payload = json.loads(result.content)
        assert payload["environment"] == "ganymede"
        assert payload["state"]["health"] == "healthy"
        assert payload["cpu_percent"] == 40.0
        assert payload["memory"]["usage_mib"] == 100.0
        assert payload["network"]["rx_mib"] == 1.0
        assert payload["mount_destinations"] == ["/data"]
        assert payload["networks"] == ["backend", "proxy"]
        assert "must-not-return" not in result.content
        assert "/volume2/private/source" not in result.content
        assert "192.168.5.200" not in result.content


class TestCamCorePortainerLogs:
    def test_logs_are_redacted_before_return_to_model(self):
        response = MagicMock()
        response.content = (
            b"user=person@example.com API_KEY=THIS-IS-SECRET\n"
        )
        with (
            patch.object(
                portainer._PortainerClient,
                "json",
                side_effect=[[_ENDPOINT], [_CONTAINER]],
            ),
            patch.object(
                portainer._PortainerClient,
                "request",
                return_value=response,
            ),
            patch(
                "openjarvis.tools.camcore_portainer._redact_sensitive",
                return_value=(
                    "user=[REDACTED] API_KEY=[REDACTED]\n"
                ),
            ),
        ):
            result = portainer.CamCorePortainerContainerLogsTool().execute(
                container="camcore-status",
                tail=50,
            )
        assert result.success is True
        assert "person@example.com" not in result.content
        assert "THIS-IS-SECRET" not in result.content
        assert "[REDACTED]" in result.content
        assert result.metadata["redacted"] is True

    def test_docker_multiplexed_log_stream_is_decoded(self):
        first = b"hello\n"
        second = b"error\n"
        data = (
            b"\x01\x00\x00\x00"
            + len(first).to_bytes(4, "big")
            + first
            + b"\x02\x00\x00\x00"
            + len(second).to_bytes(4, "big")
            + second
        )
        assert portainer._decode_docker_log_stream(data) == (
            "hello\nerror\n"
        )


class TestCamCorePortainerAction:
    def test_unsupported_action_is_rejected_without_api_call(self):
        with patch.object(
            portainer._PortainerClient,
            "request",
        ) as request:
            result = portainer.CamCorePortainerContainerActionTool().execute(
                container="camcore-status",
                action="delete",
            )
        assert result.success is False
        assert "Unsupported action" in result.content
        request.assert_not_called()

    def test_restart_uses_portainer_docker_gateway(self):
        with (
            patch.object(
                portainer._PortainerClient,
                "json",
                side_effect=[[_ENDPOINT], [_CONTAINER]],
            ),
            patch.object(
                portainer._PortainerClient,
                "request",
            ) as request,
        ):
            result = portainer.CamCorePortainerContainerActionTool().execute(
                container="camcore-status",
                action="restart",
                timeout=15,
            )
        assert result.success is True
        request.assert_called_once_with(
            "POST",
            "endpoints/2/docker/containers/abcdef1234567890/restart",
            params={"t": "15"},
        )
