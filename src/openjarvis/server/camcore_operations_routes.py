"""CamCore administrator operations overview routes.

These endpoints expose only deliberately safe operational summaries. They do not
return credentials, connector URLs, raw tool schemas, environment variables or
arbitrary Docker inspect payloads.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from openjarvis.server.camcore_access import require_admin

router = APIRouter(prefix="/v1/camcore/operations", tags=["camcore-operations"])


def _tool_ids(request: Request) -> set[str]:
    agent = getattr(request.app.state, "agent", None)
    tools = getattr(agent, "_tools", []) if agent is not None else []
    result: set[str] = set()
    for tool in tools or []:
        tool_id = str(getattr(tool, "tool_id", "") or "").strip()
        if not tool_id:
            try:
                tool_id = str(tool.spec.name or "").strip()
            except Exception:
                tool_id = ""
        if tool_id:
            result.add(tool_id)
    return result


def _capability(
    capability_id: str,
    label: str,
    *,
    available: bool,
    source: str,
    scope: str,
    mode: str = "read",
    evidence: str = "available",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "label": label,
        "available": available,
        "source": source,
        "scope": scope,
        "mode": mode,
        "evidence": evidence if available else "unavailable",
        "requires_confirmation": requires_confirmation,
    }


def build_capability_inventory(request: Request) -> list[dict[str, Any]]:
    """Build a safe inventory from tools actually attached to this session."""

    tools = _tool_ids(request)
    outline_read = {"list_documents", "fetch"}.issubset(tools)
    portainer_read = "camcore_portainer_overview" in tools
    portainer_logs = "camcore_portainer_container_logs" in tools
    portainer_control = "camcore_portainer_container_action" in tools

    return [
        _capability(
            "knowledge.outline.read",
            "CamCore documentation",
            available=outline_read,
            source="Outline",
            scope="Read-only documented architecture, procedures and configuration",
            evidence="documented",
        ),
        _capability(
            "docker.containers.read",
            "Docker container state",
            available=portainer_read,
            source="Portainer",
            scope="Environments, container state and Docker health only",
            evidence="live-capable",
        ),
        _capability(
            "docker.logs.read",
            "Container logs",
            available=portainer_logs,
            source="Portainer",
            scope="Recent redacted container stdout/stderr",
            evidence="live-capable",
        ),
        _capability(
            "docker.containers.control",
            "Container control",
            available=portainer_control,
            source="Portainer",
            scope="Start, stop and restart only",
            mode="write",
            evidence="live-capable",
            requires_confirmation=True,
        ),
        _capability(
            "synology.storage.read",
            "Synology storage health",
            available=False,
            source="Synology DSM",
            scope="Storage pools, volumes, SMART, hardware and UPS",
        ),
        _capability(
            "monitoring.health.read",
            "Infrastructure monitoring",
            available=False,
            source="Monitoring",
            scope="Host and service health outside Docker",
        ),
        _capability(
            "m365.operations.read",
            "Microsoft 365 operations",
            available=False,
            source="Microsoft 365",
            scope="Service health, licensing, devices and security summaries",
        ),
        _capability(
            "youtrack.operations.read",
            "YouTrack operations",
            available=False,
            source="YouTrack",
            scope="Tasks, support and operational work",
        ),
        _capability(
            "homeassistant.state.read",
            "Home Assistant state",
            available=False,
            source="Home Assistant",
            scope="Approved entity state only",
        ),
        _capability(
            "media.status.read",
            "Media services",
            available=False,
            source="CamCore Media",
            scope="Service status and activity",
        ),
    ]


@router.get("/capabilities")
async def camcore_operations_capabilities(request: Request):
    """Return the administrator session's safe operational capability inventory."""

    require_admin(request)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": build_capability_inventory(request),
    }


@router.get("/overview")
async def camcore_operations_overview(request: Request):
    """Return live Docker overview when the approved Portainer tool is attached."""

    require_admin(request)
    capabilities = build_capability_inventory(request)
    portainer_capability = next(
        item for item in capabilities if item["id"] == "docker.containers.read"
    )
    source: dict[str, Any]
    if not portainer_capability["available"]:
        source = {
            "state": "unavailable",
            "evidence": "unavailable",
            "source": "Portainer",
            "detail": "No current-session Portainer container read capability is attached.",
        }
    else:
        from openjarvis.tools.camcore_portainer import CamCorePortainerOverviewTool

        result = CamCorePortainerOverviewTool().execute(include_stopped=True)
        if result.success:
            try:
                data = json.loads(result.content)
            except (TypeError, ValueError):
                data = {"detail": "Portainer returned an unreadable safe summary."}
            source = {
                "state": "live",
                "evidence": "live",
                "source": "Portainer",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
        else:
            source = {
                "state": "error",
                "evidence": "unavailable",
                "source": "Portainer",
                "detail": str(result.content or "Portainer live check failed")[:2000],
            }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {"portainer": source},
        "capabilities": capabilities,
    }


__all__ = ["build_capability_inventory", "router"]
