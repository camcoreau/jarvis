"""Read-only CamCore integrations for approved operational context.

Every integration has a fixed server-side target and credential source. The
model never supplies URLs, tokens, tenant IDs or repository API origins. Tools
return deliberately bounded summaries rather than raw provider payloads.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_TIMEOUT = 20.0
_MAX_TEXT = 2_000


class _IntegrationConfigError(RuntimeError):
    """Raised when an optional CamCore integration is not configured."""


class _IntegrationRequestError(RuntimeError):
    """Raised when an upstream integration returns unusable data."""


def _redact_sensitive(text: str) -> str:
    try:
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        return PIIScanner().redact(SecretScanner().redact(text))
    except Exception:
        return "[sensitive operational content omitted]"


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, _IntegrationConfigError):
        return str(exc)[:_MAX_TEXT]
    return _redact_sensitive(str(exc))[:_MAX_TEXT]


def _required_env(*names: str) -> list[str]:
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise _IntegrationConfigError(
            "CamCore integration is not configured; set "
            + ", ".join(missing)
            + " server-side."
        )
    return [os.environ[name].strip() for name in names]


def _configured_origin(name: str, *, allow_http: bool = False) -> str:
    value = _required_env(name)[0].rstrip("/")
    parsed = urlparse(value)
    valid_schemes = {"https"} | ({"http"} if allow_http else set())
    if (
        parsed.scheme not in valid_schemes
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        schemes = "http/https" if allow_http else "https"
        raise _IntegrationConfigError(
            f"{name} must be a fixed {schemes} origin without query or fragment."
        )
    return value


def _json_response(response: httpx.Response, provider: str) -> Any:
    if response.is_redirect:
        raise _IntegrationRequestError(f"{provider} returned an unexpected redirect.")
    if response.status_code >= 400:
        raise _IntegrationRequestError(
            f"{provider} returned HTTP {response.status_code}."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise _IntegrationRequestError(f"{provider} returned invalid JSON.") from exc


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    provider: str,
) -> Any:
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            timeout=_TIMEOUT,
            follow_redirects=False,
        )
    except httpx.RequestError as exc:
        raise _IntegrationRequestError(
            f"{provider} request failed: {_redact_sensitive(str(exc))}"
        ) from exc
    return _json_response(response, provider)


def _tool_result(tool_id: str, payload: Any) -> ToolResult:
    return ToolResult(
        tool_name=tool_id,
        content=json.dumps(payload, indent=2, sort_keys=True),
        success=True,
    )


def _tool_error(tool_id: str, exc: Exception) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=_safe_error(exc), success=False)


@ToolRegistry.register("camcore_betterstack_overview")
class CamCoreBetterStackOverviewTool(BaseTool):
    """Read CamCore monitor state and unresolved incidents from Better Stack."""

    tool_id = "camcore_betterstack_overview"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read the current CamCore Better Stack uptime monitor "
                "summary and unresolved incidents. Returns monitor "
                "names/statuses and bounded incident metadata only."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            token = _required_env("CAMCORE_BETTERSTACK_API_TOKEN")[0]
            team = os.environ.get("CAMCORE_BETTERSTACK_TEAM", "").strip()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            monitor_params: dict[str, Any] = {"per_page": 250, "page": 1}
            incident_params: dict[str, Any] = {
                "resolved": "false",
                "per_page": 50,
                "page": 1,
            }
            if team:
                monitor_params["team_name"] = team
                incident_params["team_name"] = team

            monitors_json = _request_json(
                "GET",
                "https://uptime.betterstack.com/api/v2/monitors",
                headers=headers,
                params=monitor_params,
                provider="Better Stack",
            )
            incidents_json = _request_json(
                "GET",
                "https://uptime.betterstack.com/api/v3/incidents",
                headers=headers,
                params=incident_params,
                provider="Better Stack",
            )

            monitors = []
            for item in (
                monitors_json.get("data", []) if isinstance(monitors_json, dict) else []
            ):
                if not isinstance(item, dict):
                    continue
                attributes = item.get("attributes") or {}
                if not isinstance(attributes, dict):
                    continue
                monitors.append(
                    {
                        "id": str(item.get("id") or ""),
                        "name": str(attributes.get("pronounceable_name") or "unnamed"),
                        "status": str(attributes.get("status") or "unknown"),
                        "monitor_type": str(
                            attributes.get("monitor_type") or "unknown"
                        ),
                        "last_checked_at": attributes.get("last_checked_at"),
                    }
                )

            incidents = []
            for item in (
                incidents_json.get("data", [])
                if isinstance(incidents_json, dict)
                else []
            ):
                if not isinstance(item, dict):
                    continue
                attributes = item.get("attributes") or {}
                if not isinstance(attributes, dict):
                    continue
                incidents.append(
                    {
                        "id": str(item.get("id") or ""),
                        "name": str(attributes.get("name") or "incident")[:300],
                        "cause": _redact_sensitive(str(attributes.get("cause") or ""))[
                            :500
                        ],
                        "status": str(attributes.get("status") or "unknown"),
                        "started_at": attributes.get("started_at"),
                        "acknowledged_at": attributes.get("acknowledged_at"),
                    }
                )

            status_counts: dict[str, int] = {}
            for monitor in monitors:
                state = monitor["status"]
                status_counts[state] = status_counts.get(state, 0) + 1
            return _tool_result(
                self.tool_id,
                {
                    "source": "Better Stack Uptime API",
                    "monitor_count": len(monitors),
                    "status_counts": status_counts,
                    "active_incident_count": len(incidents),
                    "monitors": monitors,
                    "active_incidents": incidents,
                    "truncated": bool(
                        isinstance(monitors_json, dict)
                        and (monitors_json.get("pagination") or {}).get("next")
                    ),
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


def _youtrack_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_youtrack_value(item) for item in value[:10]]
    if isinstance(value, dict):
        for key in ("name", "fullName", "login", "text"):
            if value.get(key) not in (None, ""):
                return value[key]
    return None


@ToolRegistry.register("camcore_youtrack_overview")
class CamCoreYouTrackOverviewTool(BaseTool):
    """Read bounded unresolved operational work from CamCore YouTrack."""

    tool_id = "camcore_youtrack_overview"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read a bounded list of CamCore YouTrack issues using "
                "the server-configured read query. Returns issue IDs, "
                "summaries, project, resolution state and selected fields."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            origin = _configured_origin("CAMCORE_YOUTRACK_URL", allow_http=True)
            token = _required_env("CAMCORE_YOUTRACK_TOKEN")[0]
            query = (
                os.environ.get("CAMCORE_YOUTRACK_QUERY", "#Unresolved").strip()
                or "#Unresolved"
            )
            fields = (
                "id,idReadable,summary,resolved,updated,project(shortName,name),"
                "customFields(name,value(name,login,fullName,text))"
            )
            data = _request_json(
                "GET",
                f"{origin}/api/issues",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params={"query": query, "fields": fields, "$top": 50},
                provider="YouTrack",
            )
            if not isinstance(data, list):
                raise _IntegrationRequestError(
                    "YouTrack issue list had an invalid shape."
                )

            selected_fields = {
                "State",
                "Priority",
                "Assignee",
                "Service",
                "Impact",
                "Category",
            }
            issues = []
            for issue in data[:50]:
                if not isinstance(issue, dict):
                    continue
                project = issue.get("project") or {}
                custom: dict[str, Any] = {}
                for field in issue.get("customFields") or []:
                    if not isinstance(field, dict):
                        continue
                    name = str(field.get("name") or "")
                    if name in selected_fields:
                        custom[name] = _youtrack_value(field.get("value"))
                issues.append(
                    {
                        "id": str(issue.get("idReadable") or issue.get("id") or ""),
                        "summary": str(issue.get("summary") or "")[:1_000],
                        "project": str(
                            project.get("shortName") or project.get("name") or ""
                        ),
                        "resolved": issue.get("resolved") is not None,
                        "updated": issue.get("updated"),
                        "fields": custom,
                    }
                )
            return _tool_result(
                self.tool_id,
                {
                    "source": "YouTrack REST API",
                    "query": query,
                    "issue_count": len(issues),
                    "issues": issues,
                    "truncated": len(data) >= 50,
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


def _allowed_home_assistant_entities() -> set[str]:
    raw = os.environ.get("CAMCORE_HOMEASSISTANT_ENTITIES", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


@ToolRegistry.register("camcore_homeassistant_state")
class CamCoreHomeAssistantStateTool(BaseTool):
    """Read state for an explicitly allow-listed Home Assistant entity."""

    tool_id = "camcore_homeassistant_state"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read current state for one CamCore Home Assistant entity. "
                "Only entity IDs allow-listed server-side are accepted; "
                "location and arbitrary attributes are not returned."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": (
                            "Allow-listed Home Assistant entity ID, "
                            "for example sensor.example."
                        ),
                    }
                },
                "required": ["entity_id"],
            },
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            origin = _configured_origin("CAMCORE_HOMEASSISTANT_URL", allow_http=True)
            token = _required_env("CAMCORE_HOMEASSISTANT_TOKEN")[0]
            entity_id = str(params.get("entity_id") or "").strip().lower()
            allowed = _allowed_home_assistant_entities()
            if not allowed:
                raise _IntegrationConfigError(
                    "CAMCORE_HOMEASSISTANT_ENTITIES has no approved entity IDs."
                )
            if entity_id not in allowed:
                raise _IntegrationRequestError(
                    (
                        f"Home Assistant entity '{entity_id}' is not in "
                        "the server-side allow-list."
                    )
                )
            data = _request_json(
                "GET",
                f"{origin}/api/states/{entity_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                provider="Home Assistant",
            )
            if not isinstance(data, dict):
                raise _IntegrationRequestError(
                    "Home Assistant state response had an invalid shape."
                )
            attributes = data.get("attributes") or {}
            safe_attributes = {
                key: attributes.get(key)
                for key in ("friendly_name", "unit_of_measurement", "device_class")
                if isinstance(attributes, dict) and attributes.get(key) is not None
            }
            return _tool_result(
                self.tool_id,
                {
                    "source": "Home Assistant REST API",
                    "entity_id": data.get("entity_id") or entity_id,
                    "state": data.get("state"),
                    "last_changed": data.get("last_changed"),
                    "last_updated": data.get("last_updated"),
                    "attributes": safe_attributes,
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


def _graph_access_token() -> str:
    tenant, client_id, client_secret = _required_env(
        "CAMCORE_M365_TENANT_ID",
        "CAMCORE_M365_CLIENT_ID",
        "CAMCORE_M365_CLIENT_SECRET",
    )
    token_data = _request_json(
        "POST",
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        provider="Microsoft identity platform",
    )
    if not isinstance(token_data, dict) or not token_data.get("access_token"):
        raise _IntegrationRequestError(
            "Microsoft identity platform did not return an access token."
        )
    return str(token_data["access_token"])


@ToolRegistry.register("camcore_m365_service_health")
class CamCoreM365ServiceHealthTool(BaseTool):
    """Read Microsoft 365 tenant service health using Microsoft Graph."""

    tool_id = "camcore_m365_service_health"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read CamCore Microsoft 365 subscribed service health "
                "and current service issues via Microsoft Graph. "
                "Requires server-side ServiceHealth.Read.All application access."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            token = _graph_access_token()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            health = _request_json(
                "GET",
                "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/healthOverviews",
                headers=headers,
                params={"$select": "id,service,status"},
                provider="Microsoft Graph",
            )
            issues_data = _request_json(
                "GET",
                "https://graph.microsoft.com/v1.0/admin/serviceAnnouncement/issues",
                headers=headers,
                params={
                    "$select": (
                        "id,title,service,status,classification,startDateTime,"
                        "lastModifiedDateTime,impactDescription,isResolved"
                    )
                },
                provider="Microsoft Graph",
            )
            services = []
            for item in health.get("value", []) if isinstance(health, dict) else []:
                if isinstance(item, dict):
                    services.append(
                        {
                            "id": str(item.get("id") or ""),
                            "service": str(item.get("service") or ""),
                            "status": str(item.get("status") or "unknown"),
                        }
                    )
            active_issues = []
            for item in (
                issues_data.get("value", []) if isinstance(issues_data, dict) else []
            ):
                if not isinstance(item, dict) or item.get("isResolved") is True:
                    continue
                active_issues.append(
                    {
                        "id": str(item.get("id") or ""),
                        "title": str(item.get("title") or "")[:500],
                        "service": str(item.get("service") or ""),
                        "status": str(item.get("status") or "unknown"),
                        "classification": str(item.get("classification") or ""),
                        "startDateTime": item.get("startDateTime"),
                        "lastModifiedDateTime": item.get("lastModifiedDateTime"),
                        "impactDescription": _redact_sensitive(
                            str(item.get("impactDescription") or "")
                        )[:1_000],
                    }
                )
            return _tool_result(
                self.tool_id,
                {
                    "source": "Microsoft Graph serviceAnnouncement",
                    "service_count": len(services),
                    "services": services,
                    "active_issue_count": len(active_issues),
                    "active_issues": active_issues[:50],
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


@ToolRegistry.register("camcore_github_overview")
class CamCoreGitHubOverviewTool(BaseTool):
    """Read bounded issue and Actions state for approved CamCore repositories."""

    tool_id = "camcore_github_overview"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read bounded GitHub issue and Actions status for "
                "repositories allow-listed server-side in "
                "CAMCORE_GITHUB_REPOSITORIES. No repository can be "
                "supplied by the model."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            repositories = [
                item.strip()
                for item in os.environ.get("CAMCORE_GITHUB_REPOSITORIES", "").split(",")
                if item.strip()
            ]
            if not repositories:
                raise _IntegrationConfigError(
                    (
                        "CAMCORE_GITHUB_REPOSITORIES has no approved "
                        "owner/repository entries."
                    )
                )
            token = os.environ.get("CAMCORE_GITHUB_TOKEN", "").strip()
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"

            summaries = []
            for repository in repositories[:25]:
                owner, separator, name = repository.partition("/")
                if not separator or not owner or not name or "/" in name:
                    raise _IntegrationConfigError(
                        f"Invalid CAMCORE_GITHUB_REPOSITORIES entry: {repository!r}."
                    )
                encoded_repo = f"{owner}/{name}"
                repo_data = _request_json(
                    "GET",
                    f"https://api.github.com/repos/{encoded_repo}",
                    headers=headers,
                    provider="GitHub",
                )
                issues_data = _request_json(
                    "GET",
                    f"https://api.github.com/repos/{encoded_repo}/issues",
                    headers=headers,
                    params={
                        "state": "open",
                        "per_page": 20,
                        "sort": "updated",
                        "direction": "desc",
                    },
                    provider="GitHub",
                )
                runs_data = _request_json(
                    "GET",
                    f"https://api.github.com/repos/{encoded_repo}/actions/runs",
                    headers=headers,
                    params={"per_page": 10},
                    provider="GitHub",
                )
                issues = []
                for issue in issues_data if isinstance(issues_data, list) else []:
                    if not isinstance(issue, dict) or "pull_request" in issue:
                        continue
                    issues.append(
                        {
                            "number": issue.get("number"),
                            "title": str(issue.get("title") or "")[:500],
                            "updated_at": issue.get("updated_at"),
                        }
                    )
                runs = []
                for run in (
                    runs_data.get("workflow_runs", [])
                    if isinstance(runs_data, dict)
                    else []
                ):
                    if isinstance(run, dict):
                        runs.append(
                            {
                                "name": str(run.get("name") or ""),
                                "event": str(run.get("event") or ""),
                                "status": str(run.get("status") or ""),
                                "conclusion": run.get("conclusion"),
                                "head_branch": run.get("head_branch"),
                                "updated_at": run.get("updated_at"),
                            }
                        )
                summaries.append(
                    {
                        "repository": str(repo_data.get("full_name") or encoded_repo),
                        "default_branch": repo_data.get("default_branch"),
                        "updated_at": repo_data.get("updated_at"),
                        "open_issue_count": len(issues),
                        "recent_issues": issues,
                        "recent_workflow_runs": runs,
                    }
                )
            return _tool_result(
                self.tool_id,
                {
                    "source": "GitHub REST API",
                    "repository_count": len(summaries),
                    "repositories": summaries,
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


@ToolRegistry.register("camcore_synology_api_inventory")
class CamCoreSynologyApiInventoryTool(BaseTool):
    """Discover advertised DSM APIs without claiming undocumented storage health."""

    tool_id = "camcore_synology_api_inventory"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Discover which Synology DSM WebAPI names and versions "
                "are advertised by the configured NAS. This is "
                "capability discovery only and is not disk, SMART, "
                "RAID/SHR, volume or UPS health."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            origin = _configured_origin("CAMCORE_SYNOLOGY_URL", allow_http=True)
            data = _request_json(
                "GET",
                f"{origin}/webapi/entry.cgi",
                params={
                    "api": "SYNO.API.Info",
                    "version": 1,
                    "method": "query",
                    "query": "all",
                },
                provider="Synology DSM",
            )
            if not isinstance(data, dict) or data.get("success") is not True:
                raise _IntegrationRequestError(
                    "Synology DSM API discovery did not succeed."
                )
            raw = data.get("data") or {}
            if not isinstance(raw, dict):
                raise _IntegrationRequestError(
                    "Synology DSM API inventory had an invalid shape."
                )
            interesting = {}
            prefixes = ("SYNO.API.", "SYNO.Core.", "SYNO.Storage.")
            for name, details in raw.items():
                if not str(name).startswith(prefixes) or not isinstance(details, dict):
                    continue
                interesting[str(name)] = {
                    "minVersion": details.get("minVersion"),
                    "maxVersion": details.get("maxVersion"),
                }
            return _tool_result(
                self.tool_id,
                {
                    "source": "Synology DSM SYNO.API.Info",
                    "kind": "capability-discovery",
                    "api_count": len(interesting),
                    "apis": dict(sorted(interesting.items())),
                    "warning": (
                        "This inventory does not prove physical disk, SMART, "
                        "storage-pool, RAID/SHR, filesystem, hardware or UPS "
                        "health."
                    ),
                },
            )
        except Exception as exc:
            return _tool_error(self.tool_id, exc)


__all__ = [
    "CamCoreBetterStackOverviewTool",
    "CamCoreGitHubOverviewTool",
    "CamCoreHomeAssistantStateTool",
    "CamCoreM365ServiceHealthTool",
    "CamCoreSynologyApiInventoryTool",
    "CamCoreYouTrackOverviewTool",
]
