"""CamCore administrator operations overview routes.

These endpoints expose only deliberately safe operational summaries. They do not
return credentials, connector URLs, raw tool schemas, environment variables or
arbitrary provider payloads.
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
    betterstack_read = "camcore_betterstack_overview" in tools
    youtrack_read = "camcore_youtrack_overview" in tools
    homeassistant_read = "camcore_homeassistant_state" in tools
    m365_read = "camcore_m365_service_health" in tools
    github_read = "camcore_github_overview" in tools
    synology_discovery = "camcore_synology_api_inventory" in tools

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
            "monitoring.health.read",
            "Infrastructure monitoring",
            available=betterstack_read,
            source="Better Stack",
            scope="Configured uptime monitor state and unresolved incidents",
            evidence="live-capable",
        ),
        _capability(
            "m365.servicehealth.read",
            "Microsoft 365 service health",
            available=m365_read,
            source="Microsoft Graph",
            scope="Subscribed service health and current service issues only",
            evidence="live-capable",
        ),
        _capability(
            "youtrack.operations.read",
            "YouTrack operations",
            available=youtrack_read,
            source="YouTrack",
            scope="Bounded read-only issue/work context using the configured query",
            evidence="live-capable",
        ),
        _capability(
            "homeassistant.state.read",
            "Home Assistant state",
            available=homeassistant_read,
            source="Home Assistant",
            scope="Current state for server allow-listed entity IDs only",
            evidence="live-capable",
        ),
        _capability(
            "github.operations.read",
            "GitHub operations",
            available=github_read,
            source="GitHub",
            scope="Bounded issues and Actions state for server allow-listed repositories",
            evidence="live-capable",
        ),
        _capability(
            "synology.api.discovery",
            "Synology API discovery",
            available=synology_discovery,
            source="Synology DSM",
            scope="Advertised DSM API names and versions only",
            evidence="live-capable",
        ),
        _capability(
            "synology.storage.read",
            "Synology storage health",
            available=False,
            source="Synology DSM",
            scope="Storage pools, volumes, SMART, hardware and UPS require a documented dedicated source",
        ),
        _capability(
            "media.status.read",
            "Media services",
            available=False,
            source="CamCore Media",
            scope="Dedicated media service status and activity integration",
        ),
    ]


def _source_unavailable(source_name: str, detail: str) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "evidence": "unavailable",
        "source": source_name,
        "detail": detail[:2_000],
    }


def _source_from_result(source_name: str, result: Any) -> dict[str, Any]:
    if not getattr(result, "success", False):
        return {
            "state": "error",
            "evidence": "unavailable",
            "source": source_name,
            "detail": str(getattr(result, "content", "Live check failed"))[:2_000],
        }
    try:
        data = json.loads(result.content)
    except (TypeError, ValueError):
        data = {"detail": f"{source_name} returned an unreadable safe summary."}
    return {
        "state": "live",
        "evidence": "live",
        "source": source_name,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


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
    """Return live evidence from configured read-only CamCore integrations."""

    require_admin(request)
    capabilities = build_capability_inventory(request)
    available = {item["id"]: bool(item["available"]) for item in capabilities}
    sources: dict[str, dict[str, Any]] = {}

    if available.get("docker.containers.read"):
        from openjarvis.tools.camcore_portainer import CamCorePortainerOverviewTool

        sources["portainer"] = _source_from_result(
            "Portainer",
            CamCorePortainerOverviewTool().execute(include_stopped=True),
        )
    else:
        sources["portainer"] = _source_unavailable(
            "Portainer",
            "No current-session Portainer container read capability is attached.",
        )

    from openjarvis.tools.camcore_integrations import (
        CamCoreBetterStackOverviewTool,
        CamCoreGitHubOverviewTool,
        CamCoreM365ServiceHealthTool,
        CamCoreSynologyApiInventoryTool,
        CamCoreYouTrackOverviewTool,
    )

    read_sources = (
        (
            "betterstack",
            "monitoring.health.read",
            "Better Stack",
            CamCoreBetterStackOverviewTool,
        ),
        (
            "youtrack",
            "youtrack.operations.read",
            "YouTrack",
            CamCoreYouTrackOverviewTool,
        ),
        (
            "m365",
            "m365.servicehealth.read",
            "Microsoft 365",
            CamCoreM365ServiceHealthTool,
        ),
        (
            "github",
            "github.operations.read",
            "GitHub",
            CamCoreGitHubOverviewTool,
        ),
        (
            "synology",
            "synology.api.discovery",
            "Synology DSM",
            CamCoreSynologyApiInventoryTool,
        ),
    )
    for source_id, capability_id, source_name, tool_class in read_sources:
        if available.get(capability_id):
            sources[source_id] = _source_from_result(source_name, tool_class().execute())
        else:
            sources[source_id] = _source_unavailable(
                source_name,
                f"No current-session {source_name} read capability is attached.",
            )

    # Home Assistant is deliberately entity-scoped: the overview does not bulk
    # enumerate states because that could expose unrelated household context.
    sources["homeassistant"] = (
        {
            "state": "available",
            "evidence": "available",
            "source": "Home Assistant",
            "detail": "Entity-scoped read capability is attached; no bulk state query is performed.",
        }
        if available.get("homeassistant.state.read")
        else _source_unavailable(
            "Home Assistant",
            "No current-session allow-listed Home Assistant state capability is attached.",
        )
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "capabilities": capabilities,
    }


__all__ = ["build_capability_inventory", "router"]
