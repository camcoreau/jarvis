"""CamCore portal-specific API routes.

The public CamCore member portal must never inherit the operations agent's
server-side tools or memory context. Administrators may use the operations
agent, but cloud use is explicit and policy-controlled so operational memory is
not silently exported to an external model provider.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from openjarvis.server.camcore_provider import provider_status, resolve_provider
from openjarvis.server.models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatMessage,
    DeltaMessage,
    StreamChoice,
)
from openjarvis.server.routes import (
    _handle_agent,
    _handle_direct,
    _to_messages,
    chat_completions,
)

router = APIRouter(prefix="/v1/camcore/portal", tags=["camcore-portal"])
logger = logging.getLogger(__name__)

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


def _requested_provider(request: Request) -> str:
    return str(request.headers.get("X-CamCore-Provider", "auto") or "auto")


def _local_model(
    request: Request,
    request_body: ChatCompletionRequest | None = None,
) -> str:
    model = str(getattr(request.app.state, "model", "") or "").strip()
    if not model and request_body is not None:
        model = str(request_body.model or "").strip()
    if not model:
        raise HTTPException(
            status_code=503,
            detail="CamCore portal model is unavailable",
        )
    return model


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


def _provider_event(
    provider: str,
    model: str,
    fallback_from: str | None = None,
) -> str:
    payload = {"provider": provider, "model": model}
    if fallback_from:
        payload["fallbackFrom"] = fallback_from
    return f"event: camcore.provider\ndata: {json.dumps(payload)}\n\n"


def _stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-store, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def _member_stream(engine, request_body: ChatCompletionRequest, decision):
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    async def generate():
        selected = decision.selected
        model = decision.model
        fallback_from = decision.fallback_from
        yield _provider_event(selected, model, fallback_from)
        first_chunk = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[StreamChoice(delta=DeltaMessage(role="assistant"))],
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        async def run_model(run_model: str):
            messages = _to_messages(_member_request(request_body, run_model).messages)
            async for token in engine.stream(
                messages,
                model=run_model,
                temperature=0.2,
                max_tokens=min(max(1, request_body.max_tokens), _MAX_TOKENS),
            ):
                if token:
                    yield token

        emitted = False
        try:
            async for token in run_model(model):
                emitted = True
                content_chunk = ChatCompletionChunk(
                    id=chunk_id,
                    model=model,
                    choices=[StreamChoice(delta=DeltaMessage(content=token))],
                )
                yield f"data: {content_chunk.model_dump_json()}\n\n"
        except Exception as exc:
            if (
                decision.selected == "openai"
                and decision.fallback_allowed
                and not emitted
            ):
                logger.warning(
                    "OpenAI member chat failed; falling back local: %s",
                    exc,
                )
                model = decision.local_model
                yield _provider_event("local", model, "openai")
                async for token in run_model(model):
                    content_chunk = ChatCompletionChunk(
                        id=chunk_id,
                        model=model,
                        choices=[StreamChoice(delta=DeltaMessage(content=token))],
                    )
                    yield f"data: {content_chunk.model_dump_json()}\n\n"
            else:
                raise

        finish_chunk = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[StreamChoice(delta=DeltaMessage(), finish_reason="stop")],
        )
        yield f"data: {finish_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=_stream_headers(),
    )


def _agent_for_model(agent, model: str):
    """Create a request-local agent view without mutating the shared agent."""

    cloned = copy.copy(agent)
    cloned._model = model
    # Loop guards may hold per-run state. The cloud clone starts clean while
    # reusing the immutable tool list/executor and the process-owned MCP clients.
    cloned._loop_guard = None
    return cloned


async def _operations_stream(
    request_body: ChatCompletionRequest,
    request: Request,
    decision,
):
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="CamCore operations agent unavailable",
        )

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    bus = getattr(request.app.state, "bus", None)
    trace_store = getattr(request.app.state, "trace_store", None)

    async def generate():
        model = decision.model
        provider = decision.selected
        fallback_from = decision.fallback_from
        yield _provider_event(provider, model, fallback_from)
        first_chunk = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[StreamChoice(delta=DeltaMessage(role="assistant"))],
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        run_agent = _agent_for_model(agent, model)
        try:
            response = await asyncio.to_thread(
                _handle_agent,
                run_agent,
                model,
                request_body,
                None,
                trace_store=trace_store,
                bus=bus,
            )
        except Exception as exc:
            if decision.selected == "openai" and decision.fallback_allowed:
                logger.warning(
                    "OpenAI operations chat failed; falling back local: %s",
                    exc,
                )
                provider = "local"
                model = decision.local_model
                yield _provider_event(provider, model, "openai")
                response = await asyncio.to_thread(
                    _handle_agent,
                    _agent_for_model(agent, model),
                    model,
                    request_body,
                    None,
                    trace_store=trace_store,
                    bus=bus,
                )
            else:
                raise

        content = response.choices[0].message.content or ""
        if content:
            content_chunk = ChatCompletionChunk(
                id=chunk_id,
                model=model,
                choices=[StreamChoice(delta=DeltaMessage(content=content))],
            )
            yield f"data: {content_chunk.model_dump_json()}\n\n"
        finish_chunk = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[StreamChoice(delta=DeltaMessage(), finish_reason="stop")],
        )
        yield f"data: {finish_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=_stream_headers(),
    )


@router.get("/providers")
async def camcore_portal_providers(request: Request):
    """Expose provider availability without exposing provider credentials."""

    role = str(request.query_params.get("role", "member")).strip().lower()
    if role not in {"member", "admin"}:
        raise HTTPException(status_code=400, detail="Role must be member or admin")
    return provider_status(
        role=role,
        engine=request.app.state.engine,
        local_model=_local_model(request),
    )


@router.post("/chat/completions")
async def camcore_member_chat(request_body: ChatCompletionRequest, request: Request):
    """Serve member-safe CamCore chat without agent tools or memory."""

    engine = request.app.state.engine
    local_model = _local_model(request, request_body)
    try:
        decision = resolve_provider(
            _requested_provider(request),
            role="member",
            engine=engine,
            local_model=local_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    safe_request = _member_request(request_body, decision.model)
    if safe_request.stream:
        return await _member_stream(engine, safe_request, decision)

    try:
        return await asyncio.to_thread(
            _handle_direct,
            engine,
            decision.model,
            safe_request,
            bus=None,
            complexity_info=None,
            app_config=None,
        )
    except Exception:
        if decision.selected != "openai" or not decision.fallback_allowed:
            raise
        fallback_request = _member_request(request_body, decision.local_model)
        return await asyncio.to_thread(
            _handle_direct,
            engine,
            decision.local_model,
            fallback_request,
            bus=None,
            complexity_info=None,
            app_config=None,
        )


@router.post("/operations/chat/completions")
async def camcore_operations_chat(
    request_body: ChatCompletionRequest,
    request: Request,
):
    """Serve policy-controlled administrator operations chat.

    Local mode delegates to the normal server route, retaining operational
    memory behaviour. OpenAI mode uses a request-local copy of the operations
    agent and deliberately does not preload Jarvis memory. Approved tool calls
    may still send the minimum required prompt/tool results to OpenAI.
    """

    local_model = _local_model(request, request_body)
    try:
        decision = resolve_provider(
            _requested_provider(request),
            role="admin",
            engine=request.app.state.engine,
            local_model=local_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if decision.selected == "local":
        request_body.model = decision.local_model
        return await chat_completions(request_body, request)

    request_body.model = decision.model
    if request_body.stream:
        return await _operations_stream(request_body, request, decision)

    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="CamCore operations agent unavailable",
        )
    try:
        return await asyncio.to_thread(
            _handle_agent,
            _agent_for_model(agent, decision.model),
            decision.model,
            request_body,
            None,
            trace_store=getattr(request.app.state, "trace_store", None),
            bus=getattr(request.app.state, "bus", None),
        )
    except Exception:
        if not decision.fallback_allowed:
            raise
        return await asyncio.to_thread(
            _handle_agent,
            _agent_for_model(agent, decision.local_model),
            decision.local_model,
            request_body,
            None,
            trace_store=getattr(request.app.state, "trace_store", None),
            bus=getattr(request.app.state, "bus", None),
        )


__all__ = ["router"]
