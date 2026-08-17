"""CamCore Portainer tools for live Docker inspection and control.

Credentials and arbitrary request targets never enter the model tool schema.
Read tools return an allow-listed view of Docker state instead of raw inspect
payloads, which can contain environment variables and other secrets.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_DEFAULT_TIMEOUT = 15.0
_MAX_LOG_CHARS = 50_000
_MAX_TAIL = 500
_REDACTION_FAILURE = "[sensitive operational content omitted: redaction unavailable]"


class _PortainerConfigError(RuntimeError):
    """Raised when the CamCore Portainer connector is not configured."""


class _PortainerRequestError(RuntimeError):
    """Raised when Portainer returns an unusable response."""


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _redact_sensitive(text: str) -> str:
    """Redact secrets and PII before text reaches model context."""
    try:
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        text = SecretScanner().redact(text)
        return PIIScanner().redact(text)
    except Exception:
        return _REDACTION_FAILURE


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, _PortainerConfigError):
        return str(exc)[:2_000]
    return _redact_sensitive(str(exc))[:2_000]


class _PortainerClient:
    """Small fixed-target client for the configured Portainer API origin."""

    def __init__(self) -> None:
        self.base_url = (
            os.environ.get("CAMCORE_PORTAINER_URL", "").strip().rstrip("/")
        )
        self.api_key = os.environ.get("CAMCORE_PORTAINER_API_KEY", "").strip()
        self.verify_tls = _env_bool("CAMCORE_PORTAINER_VERIFY_TLS", True)

    def _check_config(self) -> None:
        missing: list[str] = []
        if not self.base_url:
            missing.append("CAMCORE_PORTAINER_URL")
        if not self.api_key:
            missing.append("CAMCORE_PORTAINER_API_KEY")
        if missing:
            names = ", ".join(missing)
            raise _PortainerConfigError(
                f"CamCore Portainer connector is not configured; set {names} "
                "server-side in the Jarvis stack."
            )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        self._check_config()
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        try:
            response = httpx.request(
                method,
                url,
                headers={
                    "Accept": "application/json",
                    "X-API-Key": self.api_key,
                },
                params=params,
                timeout=_DEFAULT_TIMEOUT,
                verify=self.verify_tls,
                follow_redirects=False,
            )
        except httpx.RequestError as exc:
            raise _PortainerRequestError(
                f"Portainer request failed: {_redact_sensitive(str(exc))}"
            ) from exc

        if response.is_redirect:
            raise _PortainerRequestError(
                "Portainer returned a redirect. Configure CAMCORE_PORTAINER_URL "
                "to the final internal Portainer API origin."
            )
        if response.status_code >= 400:
            detail = _redact_sensitive(response.text)[:1_000].strip()
            suffix = f": {detail}" if detail else ""
            raise _PortainerRequestError(
                f"Portainer returned HTTP {response.status_code}{suffix}"
            )
        return response

    def json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self.request(method, path, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise _PortainerRequestError(
                "Portainer returned a non-JSON response for a JSON API request."
            ) from exc


def _endpoint_name(endpoint: dict[str, Any]) -> str:
    return str(endpoint.get("Name") or f"environment-{endpoint.get('Id', '?')}")


def _list_endpoints(client: _PortainerClient) -> list[dict[str, Any]]:
    data = client.json("GET", "endpoints")
    if not isinstance(data, list):
        raise _PortainerRequestError(
            "Portainer environment list had an invalid shape."
        )
    return [
        item
        for item in data
        if isinstance(item, dict) and item.get("Id") is not None
    ]


def _resolve_endpoint(
    client: _PortainerClient,
    environment: str | int,
) -> dict[str, Any]:
    endpoints = _list_endpoints(client)
    wanted = str(environment).strip()
    if not wanted:
        raise _PortainerRequestError("No Portainer environment was provided.")

    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for endpoint in endpoints:
        endpoint_id = str(endpoint.get("Id"))
        name = _endpoint_name(endpoint)
        if wanted == endpoint_id or wanted.casefold() == name.casefold():
            exact.append(endpoint)
        elif wanted.casefold() in name.casefold():
            partial.append(endpoint)

    matches = exact or partial
    if len(matches) == 1:
        return matches[0]
    if not matches:
        available = ", ".join(sorted(_endpoint_name(item) for item in endpoints))
        raise _PortainerRequestError(
            f"Unknown Portainer environment '{wanted}'. "
            f"Available: {available or 'none'}."
        )
    names = ", ".join(sorted(_endpoint_name(item) for item in matches))
    raise _PortainerRequestError(
        f"Environment '{wanted}' is ambiguous. Matching environments: {names}."
    )


def _list_containers(
    client: _PortainerClient,
    endpoint_id: int,
    *,
    include_stopped: bool = True,
) -> list[dict[str, Any]]:
    data = client.json(
        "GET",
        f"endpoints/{endpoint_id}/docker/containers/json",
        params={"all": "true" if include_stopped else "false"},
    )
    if not isinstance(data, list):
        raise _PortainerRequestError("Docker container list had an invalid shape.")
    return [item for item in data if isinstance(item, dict) and item.get("Id")]


def _container_names(container: dict[str, Any]) -> list[str]:
    values = container.get("Names") or []
    if not isinstance(values, list):
        return []
    return [str(value).lstrip("/") for value in values if value]


def _primary_container_name(container: dict[str, Any]) -> str:
    names = _container_names(container)
    if names:
        return names[0]
    return str(container.get("Id", "unknown"))[:12]


def _container_health(container: dict[str, Any]) -> str | None:
    status = str(container.get("Status") or "").lower()
    if "(healthy)" in status:
        return "healthy"
    if "(unhealthy)" in status:
        return "unhealthy"
    if "health: starting" in status or "(health: starting)" in status:
        return "starting"
    return None


def _container_summary(container: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "name": _primary_container_name(container),
        "id": str(container.get("Id", ""))[:12],
        "image": str(container.get("Image") or ""),
        "state": str(container.get("State") or "unknown"),
        "status": str(container.get("Status") or "unknown"),
    }
    health = _container_health(container)
    if health:
        summary["health"] = health
    return summary


def _find_container(
    client: _PortainerClient,
    container_name_or_id: str,
    environment: str | int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    wanted = str(container_name_or_id).strip()
    if not wanted:
        raise _PortainerRequestError("No container name or ID was provided.")

    endpoints = (
        [_resolve_endpoint(client, environment)]
        if environment is not None and str(environment).strip()
        else _list_endpoints(client)
    )
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    wanted_folded = wanted.casefold()

    for endpoint in endpoints:
        endpoint_id = int(endpoint["Id"])
        containers = _list_containers(
            client,
            endpoint_id,
            include_stopped=True,
        )
        for container in containers:
            container_id = str(container.get("Id") or "")
            names = _container_names(container)
            name_match = wanted_folded in {
                name.casefold() for name in names
            }
            id_match = container_id.casefold() == wanted_folded
            prefix_match = container_id.casefold().startswith(wanted_folded)
            if name_match or id_match or prefix_match:
                matches.append((endpoint, container))

    if len(matches) == 1:
        return matches[0]
    if not matches:
        scope = (
            f" in environment '{environment}'"
            if environment is not None and str(environment).strip()
            else ""
        )
        raise _PortainerRequestError(
            f"Container '{wanted}' was not found{scope}."
        )

    labels = ", ".join(
        f"{_endpoint_name(endpoint)}/{_primary_container_name(container)}"
        for endpoint, container in matches
    )
    raise _PortainerRequestError(
        f"Container '{wanted}' is ambiguous. Matching containers: {labels}."
    )


def _cpu_percent(stats: dict[str, Any]) -> float | None:
    cpu_stats = stats.get("cpu_stats") or {}
    pre_cpu = stats.get("precpu_stats") or {}
    cpu_usage = cpu_stats.get("cpu_usage") or {}
    pre_usage = pre_cpu.get("cpu_usage") or {}
    cpu_delta = int(cpu_usage.get("total_usage") or 0) - int(
        pre_usage.get("total_usage") or 0
    )
    system_delta = int(cpu_stats.get("system_cpu_usage") or 0) - int(
        pre_cpu.get("system_cpu_usage") or 0
    )
    online_cpus = int(cpu_stats.get("online_cpus") or 0)
    if not online_cpus:
        per_cpu = cpu_usage.get("percpu_usage") or []
        online_cpus = len(per_cpu) or 1
    if cpu_delta < 0 or system_delta <= 0:
        return None
    return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)


def _memory_stats(stats: dict[str, Any]) -> dict[str, Any]:
    memory = stats.get("memory_stats") or {}
    usage = int(memory.get("usage") or 0)
    limit = int(memory.get("limit") or 0)
    result: dict[str, Any] = {
        "usage_mib": round(usage / 1024 / 1024, 2),
        "limit_mib": round(limit / 1024 / 1024, 2),
    }
    if limit > 0:
        result["percent"] = round((usage / limit) * 100.0, 2)
    return result


def _network_stats(stats: dict[str, Any]) -> dict[str, Any]:
    networks = stats.get("networks") or {}
    if not isinstance(networks, dict):
        return {"rx_mib": 0.0, "tx_mib": 0.0}
    rx = 0
    tx = 0
    for counters in networks.values():
        if isinstance(counters, dict):
            rx += int(counters.get("rx_bytes") or 0)
            tx += int(counters.get("tx_bytes") or 0)
    return {
        "rx_mib": round(rx / 1024 / 1024, 2),
        "tx_mib": round(tx / 1024 / 1024, 2),
    }


def _decode_docker_log_stream(content: bytes) -> str:
    """Decode Docker multiplexed log frames, falling back to plain UTF-8."""
    if not content:
        return ""
    multiplexed = (
        len(content) >= 8
        and content[0] in (0, 1, 2)
        and content[1:4] == b"\x00\x00\x00"
    )
    if not multiplexed:
        return content.decode("utf-8", errors="replace")

    chunks: list[bytes] = []
    offset = 0
    while offset + 8 <= len(content):
        if content[offset + 1 : offset + 4] != b"\x00\x00\x00":
            return content.decode("utf-8", errors="replace")
        size = int.from_bytes(content[offset + 4 : offset + 8], "big")
        start = offset + 8
        end = start + size
        if end > len(content):
            return content.decode("utf-8", errors="replace")
        chunks.append(content[start:end])
        offset = end
    return b"".join(chunks).decode("utf-8", errors="replace")


@ToolRegistry.register("camcore_portainer_overview")
class CamCorePortainerOverviewTool(BaseTool):
    """Return a safe live overview of environments and containers."""

    tool_id = "camcore_portainer_overview"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read live CamCore Docker state through Portainer. List "
                "environments and safe container summaries without container "
                "environment variables or labels."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "include_stopped": {
                        "type": "boolean",
                        "description": (
                            "Include stopped containers. Defaults to true."
                        ),
                    }
                },
            },
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        include_stopped = bool(params.get("include_stopped", True))
        client = _PortainerClient()
        try:
            endpoints = _list_endpoints(client)
            environments: list[dict[str, Any]] = []
            for endpoint in endpoints:
                item: dict[str, Any] = {
                    "id": endpoint.get("Id"),
                    "name": _endpoint_name(endpoint),
                    "portainer_status": endpoint.get("Status"),
                }
                try:
                    containers = _list_containers(
                        client,
                        int(endpoint["Id"]),
                        include_stopped=include_stopped,
                    )
                    summaries = [
                        _container_summary(container)
                        for container in containers
                    ]
                    item["container_count"] = len(summaries)
                    item["running"] = sum(
                        1
                        for value in summaries
                        if value["state"] == "running"
                    )
                    item["unhealthy"] = sum(
                        1
                        for value in summaries
                        if value.get("health") == "unhealthy"
                    )
                    item["containers"] = sorted(
                        summaries,
                        key=lambda value: value["name"].casefold(),
                    )
                except Exception as exc:
                    item["error"] = _safe_error(exc)
                environments.append(item)

            payload = {
                "source": "Portainer live API",
                "environment_count": len(environments),
                "environments": environments,
            }
            return ToolResult(
                tool_name=self.tool_id,
                content=json.dumps(payload, indent=2, sort_keys=True),
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.tool_id,
                content=_safe_error(exc),
                success=False,
            )


@ToolRegistry.register("camcore_portainer_container_status")
class CamCorePortainerContainerStatusTool(BaseTool):
    """Read allow-listed state and resource use for one container."""

    tool_id = "camcore_portainer_container_status"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read live status, health, restart count, safe network and "
                "mount metadata, CPU, memory, and network usage for a CamCore "
                "container through Portainer."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name or container ID/prefix.",
                    },
                    "environment": {
                        "type": "string",
                        "description": (
                            "Optional Portainer environment name or ID. Omit "
                            "when the container name is unique across CamCore."
                        ),
                    },
                },
                "required": ["container"],
            },
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        client = _PortainerClient()
        try:
            endpoint, container = _find_container(
                client,
                str(params.get("container") or ""),
                params.get("environment"),
            )
            endpoint_id = int(endpoint["Id"])
            container_id = str(container["Id"])
            inspect = client.json(
                "GET",
                f"endpoints/{endpoint_id}/docker/containers/{container_id}/json",
            )
            stats = client.json(
                "GET",
                f"endpoints/{endpoint_id}/docker/containers/{container_id}/stats",
                params={"stream": "false"},
            )
            if not isinstance(inspect, dict) or not isinstance(stats, dict):
                raise _PortainerRequestError(
                    "Docker inspect/stats response was invalid."
                )

            state = inspect.get("State") or {}
            health = state.get("Health") or {}
            config = inspect.get("Config") or {}
            network_settings = inspect.get("NetworkSettings") or {}
            networks = network_settings.get("Networks") or {}
            mounts = inspect.get("Mounts") or []
            network_names = (
                sorted(networks.keys())
                if isinstance(networks, dict)
                else []
            )
            payload: dict[str, Any] = {
                "source": "Portainer live API",
                "environment": _endpoint_name(endpoint),
                "container": _primary_container_name(container),
                "id": container_id[:12],
                "image": config.get("Image") or container.get("Image"),
                "state": {
                    "status": state.get("Status"),
                    "running": state.get("Running"),
                    "paused": state.get("Paused"),
                    "restarting": state.get("Restarting"),
                    "oom_killed": state.get("OOMKilled"),
                    "dead": state.get("Dead"),
                    "exit_code": state.get("ExitCode"),
                    "started_at": state.get("StartedAt"),
                    "finished_at": state.get("FinishedAt"),
                    "health": health.get("Status"),
                },
                "restart_count": inspect.get("RestartCount"),
                "networks": network_names,
                "mount_destinations": sorted(
                    str(item.get("Destination"))
                    for item in mounts
                    if isinstance(item, dict) and item.get("Destination")
                ),
                "cpu_percent": _cpu_percent(stats),
                "memory": _memory_stats(stats),
                "network": _network_stats(stats),
            }
            return ToolResult(
                tool_name=self.tool_id,
                content=json.dumps(payload, indent=2, sort_keys=True),
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.tool_id,
                content=_safe_error(exc),
                success=False,
            )


@ToolRegistry.register("camcore_portainer_container_logs")
class CamCorePortainerContainerLogsTool(BaseTool):
    """Read recent container logs with security redaction."""

    tool_id = "camcore_portainer_container_logs"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read recent stdout/stderr from a CamCore container through "
                "Portainer. Secrets and PII are redacted before logs are "
                "returned to the model."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name or container ID/prefix.",
                    },
                    "environment": {
                        "type": "string",
                        "description": (
                            "Optional Portainer environment name or ID."
                        ),
                    },
                    "tail": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _MAX_TAIL,
                        "description": (
                            "Number of recent log lines to request (max 500)."
                        ),
                    },
                },
                "required": ["container"],
            },
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            tail = int(params.get("tail", 100))
        except (TypeError, ValueError):
            tail = 100
        tail = max(1, min(tail, _MAX_TAIL))

        client = _PortainerClient()
        try:
            endpoint, container = _find_container(
                client,
                str(params.get("container") or ""),
                params.get("environment"),
            )
            endpoint_id = int(endpoint["Id"])
            container_id = str(container["Id"])
            response = client.request(
                "GET",
                f"endpoints/{endpoint_id}/docker/containers/{container_id}/logs",
                params={
                    "stdout": "true",
                    "stderr": "true",
                    "timestamps": "true",
                    "tail": str(tail),
                },
            )
            decoded = _decode_docker_log_stream(response.content)
            text = _redact_sensitive(decoded)
            truncated = len(text) > _MAX_LOG_CHARS
            if truncated:
                text = text[:_MAX_LOG_CHARS] + "\n[logs truncated]"
            header = (
                f"Live Portainer logs: {_endpoint_name(endpoint)}/"
                f"{_primary_container_name(container)} (tail={tail})\n"
            )
            return ToolResult(
                tool_name=self.tool_id,
                content=header + (text or "(no log output)"),
                success=True,
                metadata={
                    "tail": tail,
                    "truncated": truncated,
                    "redacted": True,
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.tool_id,
                content=_safe_error(exc),
                success=False,
            )


@ToolRegistry.register("camcore_portainer_container_action")
class CamCorePortainerContainerActionTool(BaseTool):
    """Start, stop, or restart a container after explicit confirmation."""

    tool_id = "camcore_portainer_container_action"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Start, stop, or restart a CamCore container through "
                "Portainer. This modifies live state and always requires "
                "explicit confirmation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name or container ID/prefix.",
                    },
                    "environment": {
                        "type": "string",
                        "description": (
                            "Optional Portainer environment name or ID."
                        ),
                    },
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "restart"],
                        "description": "Container action to perform.",
                    },
                    "timeout": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "description": (
                            "Stop/restart grace period in seconds. "
                            "Defaults to 10."
                        ),
                    },
                },
                "required": ["container", "action"],
            },
            category="camcore",
            requires_confirmation=True,
            required_capabilities=["system:admin"],
        )

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action") or "").strip().lower()
        if action not in {"start", "stop", "restart"}:
            return ToolResult(
                tool_name=self.tool_id,
                content=(
                    "Unsupported action. Allowed actions: "
                    "start, stop, restart."
                ),
                success=False,
            )
        try:
            timeout = int(params.get("timeout", 10))
        except (TypeError, ValueError):
            timeout = 10
        timeout = max(1, min(timeout, 60))

        client = _PortainerClient()
        try:
            endpoint, container = _find_container(
                client,
                str(params.get("container") or ""),
                params.get("environment"),
            )
            endpoint_id = int(endpoint["Id"])
            container_id = str(container["Id"])
            request_params = (
                {"t": str(timeout)}
                if action in {"stop", "restart"}
                else None
            )
            client.request(
                "POST",
                (
                    f"endpoints/{endpoint_id}/docker/containers/"
                    f"{container_id}/{action}"
                ),
                params=request_params,
            )
            return ToolResult(
                tool_name=self.tool_id,
                content=(
                    f"Portainer accepted '{action}' for "
                    f"{_endpoint_name(endpoint)}/"
                    f"{_primary_container_name(container)}."
                ),
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.tool_id,
                content=_safe_error(exc),
                success=False,
            )


__all__ = [
    "CamCorePortainerContainerActionTool",
    "CamCorePortainerContainerLogsTool",
    "CamCorePortainerContainerStatusTool",
    "CamCorePortainerOverviewTool",
]
