"""OpenAI-compatible API server for OpenJarvis."""

from __future__ import annotations

# CamCore fork extension: register the member-safe portal router onto the
# existing OpenAI-compatible router without modifying upstream route plumbing.
from openjarvis.server.routes import router as _router
from openjarvis.server.camcore_portal_routes import router as _camcore_portal_router

_router.include_router(_camcore_portal_router)
