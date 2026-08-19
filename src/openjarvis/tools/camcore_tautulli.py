"""Privacy-preserving CamCore media activity from Tautulli.

Tautulli's ``get_activity`` response contains rich session metadata including
usernames, media titles, file paths, IP addresses and player information. Jarvis
only needs an operational summary, so this tool aggregates the response and
never returns individual session identity or media-title data to the model.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_TIMEOUT = 15.0


class _TautulliConfigError(RuntimeError):
    """Raised when Tautulli is not configured server-side."""


class _TautulliRequestError(RuntimeError):
    """Raised when Tautulli returns an unusable response."""


def _origin() -> str:
    value = os.environ.get("CAMCORE_TAUTULLI_URL", "").strip().rstrip("/")
    if not value:
        raise _TautulliConfigError(
            "CamCore Tautulli integration is not configured; set "
            "CAMCORE_TAUTULLI_URL server-side."
        )
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _TautulliConfigError(
            "CAMCORE_TAUTULLI_URL must be a fixed http/https origin."
        )
    if parsed.query or parsed.fragment:
        raise _TautulliConfigError(
            "CAMCORE_TAUTULLI_URL must not contain a query or fragment."
        )
    return value


def _api_key() -> str:
    value = os.environ.get("CAMCORE_TAUTULLI_API_KEY", "").strip()
    if not value:
        raise _TautulliConfigError(
            "CamCore Tautulli integration is not configured; set "
            "CAMCORE_TAUTULLI_API_KEY server-side."
        )
    return value


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, _TautulliConfigError):
        return str(exc)[:2_000]
    try:
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        return PIIScanner().redact(SecretScanner().redact(str(exc)))[:2_000]
    except Exception:
        return "Tautulli live activity check failed."


def _counter(sessions: list[dict[str, Any]], field: str) -> dict[str, int]:
    values = Counter(
        str(item.get(field) or "unknown").strip().lower()
        for item in sessions
        if isinstance(item, dict)
    )
    return dict(sorted(values.items()))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


@ToolRegistry.register("camcore_tautulli_activity")
class CamCoreTautulliActivityTool(BaseTool):
    """Read aggregate, identity-free Plex activity through Tautulli."""

    tool_id = "camcore_tautulli_activity"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.tool_id,
            description=(
                "Read aggregate current CamCore Media activity from Tautulli. "
                "Returns counts, stream decisions, media-type totals and aggregate "
                "bandwidth only; never usernames, IP addresses, media titles, file "
                "paths or individual viewing details."
            ),
            parameters={"type": "object", "properties": {}},
            category="camcore",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        del params
        try:
            origin = _origin()
            key = _api_key()
            try:
                response = httpx.get(
                    f"{origin}/api/v2",
                    params={"apikey": key, "cmd": "get_activity"},
                    headers={"Accept": "application/json"},
                    timeout=_TIMEOUT,
                    follow_redirects=False,
                )
            except httpx.RequestError as exc:
                raise _TautulliRequestError("Tautulli request failed.") from exc

            if response.is_redirect:
                raise _TautulliRequestError(
                    (
                        "Tautulli returned an unexpected redirect; configure "
                        "the final internal origin."
                    )
                )
            if response.status_code >= 400:
                raise _TautulliRequestError(
                    f"Tautulli returned HTTP {response.status_code}."
                )
            try:
                envelope = response.json()
            except ValueError as exc:
                raise _TautulliRequestError("Tautulli returned invalid JSON.") from exc

            api_response = (
                envelope.get("response") if isinstance(envelope, dict) else None
            )
            if (
                not isinstance(api_response, dict)
                or api_response.get("result") != "success"
            ):
                raise _TautulliRequestError("Tautulli get_activity did not succeed.")
            data = api_response.get("data") or {}
            if not isinstance(data, dict):
                raise _TautulliRequestError(
                    "Tautulli activity response had an invalid shape."
                )
            raw_sessions = data.get("sessions") or []
            sessions = [item for item in raw_sessions if isinstance(item, dict)]

            payload = {
                "source": "Tautulli get_activity",
                "stream_count": _int(data.get("stream_count")) or len(sessions),
                "transcode_count": _int(data.get("stream_count_transcode")),
                "direct_play_count": _int(data.get("stream_count_direct_play")),
                "direct_stream_count": _int(data.get("stream_count_direct_stream")),
                "lan_stream_count": _int(data.get("stream_count_lan")),
                "wan_stream_count": _int(data.get("stream_count_wan")),
                "total_bandwidth_kbps": _int(data.get("total_bandwidth")),
                "lan_bandwidth_kbps": _int(data.get("lan_bandwidth")),
                "wan_bandwidth_kbps": _int(data.get("wan_bandwidth")),
                "media_types": _counter(sessions, "media_type"),
                "transcode_decisions": _counter(sessions, "transcode_decision"),
                "session_states": _counter(sessions, "state"),
                "privacy": "aggregate-only",
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


__all__ = ["CamCoreTautulliActivityTool"]
