"""CamCore portal-specific API routes.

The public CamCore member portal must never inherit the operations agent's
server-side tools or memory context.  This module exposes a deliberately
narrow chat endpoint for authenticated portal members.  Authentication remains
handled by the normal OpenJarvis API-key middleware; the CamCore portal gateway
keeps that key server-side.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from openjarvis.server.models import ChatCompletionRequest, ChatMessage
from openjarvis.server.routes import _handle_direct, _handle_stream

router = APIRouter(prefix="/v1/camcore/portal", tags=["camcore-portal"])

_MEMBER_SYSTEM_PROMPT = """
You are Jarvis | CamCore AI in member chat mode for an authenticated CamCore user.

You are a private, chat-only assistant. You have no operational tools in this
mode and cannot make changes to CamCore systems. Do not claim to have checked
live infrastructure, performed an action, changed a setting, or contacted a
service unless that information is explicitly present in the conversation.

Help with approved CamCore services, Microsoft 365 and managed-device guidance,
Cameron-Media usage, general questions, explanations, writing, planning and safe
troubleshooting. Protect credentials, personal information and private
infrastructure details. Do not reveal internal hostnames, IP addresses, secrets,
admin-only procedures, private monitoring data or operational memory. If a
request requires administrative access, a system change, security-sensitive
information or current operational state, explain that a CamCore administrator
must handle it.

Keep answers clear, practical and appropriately concise. Use Australian English.
""".strip()

_MAX_HISTORY_MESSAGES = 24
_MAX_MESSAGE_CHARS = 12_000
_MAX_TOKENS = 2_048


def _member_request(
    request_body: ChatCompletionRequest,
    model: str,
) -> ChatCompletionRequest:
    history: list[ChatMessage] = []
    for message in request_body.messages:
        if message.role not in {"user", "assistant"}:
            continue
        content = (message.content or "").strip()
        if not content:
            continue
        history.append(
            ChatMessage(
                role=message.role,
                content=content[:_MAX_MESSAGE_CHARS],
            )
        )

    history = history[-_MAX_HISTORY_MESSAGES:]
    if not any(message.role == "user" for message in history):
        raise HTTPException(status_code=400, detail="A user message is required")

    return ChatCompletionRequest(
        model=model,
        messages=[
            ChatMessage(role="system", content=_MEMBER_SYSTEM_PROMPT),
            *history,
        ],
        temperature=0.2,
        max_tokens=min(max(1, request_body.max_tokens), _MAX_TOKENS),
        stream=request_body.stream,
        tools=None,
    )


@router.post("/chat/completions")
async def camcore_member_chat(request_body: ChatCompletionRequest, request: Request):
    """Serve member-safe CamCore chat without agent tools or memory.

    The model is forced to the server's configured model, caller-supplied system
    messages and tools are discarded, and neither memory context nor completed
    exchanges are loaded/stored.  Administrators use the normal
    ``/v1/chat/completions`` route through the portal gateway when they need the
    full CamCore operations agent.
    """

    engine = request.app.state.engine
    model = str(getattr(request.app.state, "model", "") or request_body.model).strip()
    if not model:
        raise HTTPException(
            status_code=503,
            detail="CamCore portal model is unavailable",
        )

    safe_request = _member_request(request_body, model)

    if safe_request.stream:
        return await _handle_stream(
            engine,
            model,
            safe_request,
            trace_store=None,
            app_config=None,
            bus=None,
            memory_service=None,
        )

    return await asyncio.to_thread(
        _handle_direct,
        engine,
        model,
        safe_request,
        bus=None,
        complexity_info=None,
        app_config=None,
    )


__all__ = ["router"]
