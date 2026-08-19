"""CamCore trusted-proxy identity and role enforcement.

The generic OpenJarvis API key authenticates the reverse proxy to Jarvis, but it
cannot identify the human using the proxy. CamCore production can therefore add
a second, explicit trust boundary: an authenticated reverse proxy supplies a
short identity envelope plus a shared proxy secret. Jarvis validates that secret
before trusting any asserted member/admin role.

Local and upstream OpenJarvis deployments remain compatible because the default
mode is ``legacy``. CamCore production enables ``trusted-proxy`` explicitly.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Mapping

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

ACCESS_MODE_LEGACY = "legacy"
ACCESS_MODE_TRUSTED_PROXY = "trusted-proxy"
_VALID_ACCESS_MODES = {ACCESS_MODE_LEGACY, ACCESS_MODE_TRUSTED_PROXY}
_VALID_ROLES = {"member", "admin"}

_PROXY_SECRET_HEADER = "X-CamCore-Proxy-Secret"
_SUBJECT_HEADER = "X-CamCore-Subject"
_EMAIL_HEADER = "X-CamCore-Email"
_DISPLAY_NAME_HEADER = "X-CamCore-Display-Name"
_ROLE_HEADER = "X-CamCore-Role"

_MEMBER_ALLOWED_PATHS = {
    "/v1/camcore/portal/chat/completions",
    "/v1/camcore/portal/providers",
    "/v1/camcore/portal/identity",
}


@dataclass(frozen=True, slots=True)
class CamCoreIdentity:
    """Identity asserted by CamCore's trusted authentication proxy."""

    subject: str
    role: str
    email: str = ""
    display_name: str = ""
    auth_source: str = "trusted-proxy"

    def to_safe_dict(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "role": self.role,
            "email": self.email,
            "display_name": self.display_name,
            "auth_source": self.auth_source,
        }


def access_mode(environment: Mapping[str, str] | None = None) -> str:
    """Return the configured CamCore access mode, defaulting to compatibility."""

    env = environment or os.environ
    value = str(env.get("CAMCORE_ACCESS_MODE", ACCESS_MODE_LEGACY)).strip().lower()
    return value if value in _VALID_ACCESS_MODES else ACCESS_MODE_LEGACY


def _requires_identity(path: str) -> bool:
    return (
        path.startswith("/v1/")
        or path.startswith("/api/")
        or path == "/metrics"
        or path.startswith("/metrics/")
    )


def _member_path_allowed(path: str) -> bool:
    return path in _MEMBER_ALLOWED_PATHS


def _safe_header(value: str | None, *, limit: int = 512) -> str:
    return str(value or "").strip()[:limit]


def _secrets_match(presented: str, expected: str) -> bool:
    try:
        presented_bytes = presented.encode("utf-8")
        expected_bytes = expected.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return secrets.compare_digest(presented_bytes, expected_bytes)


def _identity_from_headers(request: Request, expected_secret: str) -> CamCoreIdentity | None:
    presented = _safe_header(request.headers.get(_PROXY_SECRET_HEADER), limit=4096)
    if not presented or not _secrets_match(presented, expected_secret):
        return None

    subject = _safe_header(request.headers.get(_SUBJECT_HEADER))
    role = _safe_header(request.headers.get(_ROLE_HEADER), limit=32).lower()
    if not subject or role not in _VALID_ROLES:
        return None

    return CamCoreIdentity(
        subject=subject,
        role=role,
        email=_safe_header(request.headers.get(_EMAIL_HEADER)),
        display_name=_safe_header(request.headers.get(_DISPLAY_NAME_HEADER)),
    )


def request_identity(request: Request) -> CamCoreIdentity | None:
    """Return the trusted CamCore identity attached to this request, if any."""

    identity = getattr(request.state, "camcore_identity", None)
    return identity if isinstance(identity, CamCoreIdentity) else None


def request_role(request: Request, requested_role: str = "member") -> str:
    """Resolve role from trusted identity, retaining legacy compatibility."""

    identity = request_identity(request)
    if identity is not None:
        return identity.role
    role = str(requested_role or "member").strip().lower()
    return role if role in _VALID_ROLES else "member"


def require_admin(request: Request) -> None:
    """Require an administrator identity when trusted-proxy mode is active."""

    if access_mode() != ACCESS_MODE_TRUSTED_PROXY:
        return
    identity = request_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="CamCore identity is required")
    if identity.role != "admin":
        raise HTTPException(status_code=403, detail="CamCore administrator access required")


class CamCoreAccessMiddleware(BaseHTTPMiddleware):
    """Validate trusted proxy identity and enforce member route isolation."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if access_mode() != ACCESS_MODE_TRUSTED_PROXY:
            return await call_next(request)
        if request.method == "OPTIONS" or not _requires_identity(request.url.path):
            return await call_next(request)

        expected_secret = os.environ.get("CAMCORE_PROXY_IDENTITY_SECRET", "").strip()
        if not expected_secret:
            return JSONResponse(
                {"detail": "CamCore trusted proxy identity is not configured"},
                status_code=503,
            )

        identity = _identity_from_headers(request, expected_secret)
        if identity is None:
            return JSONResponse(
                {"detail": "Invalid or incomplete CamCore proxy identity"},
                status_code=401,
            )

        request.state.camcore_identity = identity
        if identity.role == "member" and not _member_path_allowed(request.url.path):
            return JSONResponse(
                {"detail": "This API surface requires CamCore administrator access"},
                status_code=403,
            )
        return await call_next(request)


__all__ = [
    "ACCESS_MODE_LEGACY",
    "ACCESS_MODE_TRUSTED_PROXY",
    "CamCoreAccessMiddleware",
    "CamCoreIdentity",
    "access_mode",
    "request_identity",
    "request_role",
    "require_admin",
]
