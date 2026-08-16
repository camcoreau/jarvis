"""OpenAI-compatible API server for OpenJarvis."""

from __future__ import annotations

from openjarvis.server.camcore_portal_routes import router as _camcore_portal_router
from openjarvis.server.routes import router as _router

# CamCore fork extension: register the member-safe portal router onto the
# existing OpenAI-compatible router without modifying upstream route plumbing.
_router.include_router(_camcore_portal_router)
