"""CamCore Jarvis agent built on the OpenJarvis orchestrator."""

from __future__ import annotations

import copy
import logging
from typing import Any, List, Optional

from openjarvis.agents._stubs import AgentContext, AgentResult
from openjarvis.agents.orchestrator import OrchestratorAgent
from openjarvis.core.events import EventBus
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Message, Role
from openjarvis.engine._stubs import InferenceEngine
from openjarvis.tools._stubs import BaseTool

logger = logging.getLogger(__name__)

CAMCORE_SYSTEM_PROMPT = """You are Jarvis, the private AI operations assistant for
CamCore.

CamCore is the Cameron Family Secure Network. Your job is to help operate, understand,
secure, document, and improve CamCore systems while protecting family privacy and
service reliability.

Operating principles:
- Prefer local processing and local data. Use external services only when they are
  required for the task or explicitly configured.
- Treat infrastructure details, credentials, access tokens, personal information,
  logs, private domains, and internal service data as sensitive.
- Prefer inspection and explanation before modification. For destructive,
  irreversible, security-sensitive, or externally visible actions, require explicit
  user intent before proceeding.
- Use tools to verify current state rather than inventing configuration, hostnames,
  service status, or credentials.
- Follow least privilege. Never expose secrets in responses, logs, URLs, commits, or
  generated configuration.
- Distinguish public CamCore services under camcore.au from private/internal services
  under camcore.network.
- Preserve working services and favour reversible, documented changes.
- When evidence is incomplete, say what is known, what is unknown, and what should be
  checked next.

CamCore knowledge source:
- Documented CamCore architecture, server roles, services, policies, standards,
  procedures, or configuration may be preloaded server-side from the read-only
  CamCore Outline knowledge source before you answer.
- Treat freshly preloaded Outline content as authoritative for documented state, but
  not as proof of current runtime health, reachability, or live service status.
- If no relevant documentation is supplied, say so and do not invent undocumented
  CamCore-specific facts.

Be concise, practical, and operationally focused. Explain risks before recommending
changes that could affect availability, security, data integrity, or user access.
"""

_OPERATIONS_OUTLINE_PRIORITY = """CAMCORE OPERATIONS DOCUMENTATION PRIORITY
The following context was freshly fetched server-side from CamCore's read-only
Outline knowledge source for this request. For documented CamCore facts, treat this
fresh fetched content as authoritative over public web search, stale search snippets,
prior conversation, or model memory. Do not use a public search result to contradict a
fact present in this fresh Outline context. Outline documents describe documented
state and do not by themselves prove current runtime health.

This prefetch is deliberately bounded and sanitised before model exposure. If an
authorised operational task genuinely needs additional restricted detail, use the
approved Operations tools rather than inferring it or substituting public search.
"""

_OUTLINE_MODEL_TOOL_NAMES = {"list_documents", "fetch"}


def _block_mode_redact(text: str) -> str | None:
    """Redact server-generated text only when input Guardrails run in BLOCK mode.

    The redactors mirror the scanners enabled by the active security configuration.
    ``None`` means BLOCK mode is active but the redaction pass failed, so callers can
    fail closed to a known-safe static prompt rather than forwarding unchecked text.
    """

    try:
        from openjarvis.core.config import load_config

        security = load_config().security
    except Exception:
        logger.debug(
            "Unable to resolve CamCore security config for server context",
            exc_info=True,
        )
        return text

    if (
        not getattr(security, "enabled", False)
        or not getattr(security, "scan_input", False)
        or str(getattr(security, "mode", "")).lower() != "block"
    ):
        return text

    try:
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        safe = text
        if getattr(security, "secret_scanner", False):
            safe = SecretScanner().redact(safe)
        if getattr(security, "pii_scanner", False):
            safe = PIIScanner().redact(safe)
        return safe
    except Exception:
        logger.warning(
            "CamCore BLOCK-mode server context redaction failed",
            exc_info=True,
        )
        return None


def _guardrail_redact_operations_context(text: str) -> str:
    """Pre-redact fetched Outline context before Operations model exposure."""

    safe = _block_mode_redact(text)
    return safe or ""


def _fresh_operations_outline_context(agent: Any, query: str) -> str:
    """Return fresh, bounded Outline context for CamCore Operations questions."""

    try:
        from openjarvis.server.camcore_member_knowledge import (
            build_member_knowledge_context,
        )

        context = build_member_knowledge_context(agent, query)
    except Exception:
        logger.warning("CamCore operations Outline prefetch failed", exc_info=True)
        return ""

    if not context:
        return ""

    context = _guardrail_redact_operations_context(context)
    if not context:
        return ""

    context = context.replace(
        "APPROVED CAMCORE MEMBER KNOWLEDGE",
        "FRESH CAMCORE OUTLINE DOCUMENTATION",
        1,
    )
    return f"{_OPERATIONS_OUTLINE_PRIORITY}\n\n{context}"


def _with_operations_outline_context(
    context: Optional[AgentContext],
    knowledge_context: str,
) -> AgentContext:
    """Clone request context and merge fresh Outline text into the system prompt."""

    enriched = AgentContext()
    if context is not None:
        enriched.conversation.messages = list(context.conversation.messages)
        enriched.conversation.max_messages = context.conversation.max_messages
        enriched.tools = list(context.tools)
        enriched.memory_results = list(context.memory_results)
        enriched.metadata = dict(context.metadata)

    enriched.conversation.add(
        Message(
            role=Role.SYSTEM,
            content=knowledge_context,
            metadata={"memory_context": True, "camcore_outline": True},
        )
    )
    return enriched


def _is_server_side_outline_tool(tool: Any) -> bool:
    """Identify the two read-only Outline MCP tools reserved for server retrieval."""

    if getattr(tool, "tool_id", None) != "mcp_adapter":
        return False
    try:
        name = str(tool.spec.name or "").strip().rsplit(":", 1)[-1]
    except Exception:
        return False
    return name in _OUTLINE_MODEL_TOOL_NAMES


def _operations_model_view(agent: Any) -> Any:
    """Return a request-local agent view that cannot call raw Outline MCP tools.

    The full agent keeps ``list_documents`` and ``fetch`` attached so trusted
    server-side retrieval can run before inference. The model-facing clone removes
    those tools from both the advertised tool schema and executor, preventing a
    redundant model-selected Outline call from feeding an unsanitised MCP result into
    a later Guardrails-scanned inference turn. Other Operations tools are unchanged.
    """

    cloned = copy.copy(agent)
    filtered_tools = [
        tool
        for tool in (getattr(agent, "_tools", None) or [])
        if not _is_server_side_outline_tool(tool)
    ]
    cloned._tools = filtered_tools

    executor = getattr(agent, "_executor", None)
    if executor is not None:
        cloned._executor = copy.copy(executor)
        cloned._executor._tools = {tool.spec.name: tool for tool in filtered_tools}

    # Loop guards carry per-run mutable state; a request-local view starts clean.
    cloned._loop_guard = None
    return cloned


@AgentRegistry.register("camcore_assistant")
class CamCoreAssistantAgent(OrchestratorAgent):
    """CamCore-specific orchestrator with a safety-focused default persona."""

    agent_id = "camcore_assistant"

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        tools: Optional[List[BaseTool]] = None,
        bus: Optional[EventBus] = None,
        max_turns: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        mode: str = "function_calling",
        system_prompt: Optional[str] = None,
        prompt_builder: Optional[Any] = None,
        parallel_tools: bool = True,
        interactive: bool = False,
        confirm_callback=None,
    ) -> None:
        super().__init__(
            engine,
            model,
            tools=tools,
            bus=bus,
            max_turns=max_turns,
            temperature=temperature,
            max_tokens=max_tokens,
            mode=mode,
            system_prompt=system_prompt or CAMCORE_SYSTEM_PROMPT,
            prompt_builder=prompt_builder,
            parallel_tools=parallel_tools,
            interactive=interactive,
            confirm_callback=confirm_callback,
        )

    def _build_messages(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        *,
        system_prompt: Optional[str] = None,
    ) -> list[Message]:
        """Build messages and sanitise only Jarvis's server-built system prompt.

        ``BaseAgent`` always places its generated system prompt first. That prompt can
        include CamCore persona files plus server-generated memory/Outline context. In
        BLOCK mode we canonical-redact that first server-built message so trusted
        context cannot block inference. Any later caller-supplied system message and
        every user message remain untouched and are still fully scanned by Guardrails.
        """

        messages = super()._build_messages(
            input,
            context,
            system_prompt=system_prompt,
        )
        if not messages or messages[0].role != Role.SYSTEM:
            return messages

        original = messages[0]
        safe = _block_mode_redact(original.content)
        if safe is None:
            safe = CAMCORE_SYSTEM_PROMPT
        if safe != original.content:
            messages[0] = Message(
                role=original.role,
                content=safe,
                name=original.name,
                tool_calls=original.tool_calls,
                tool_call_id=original.tool_call_id,
                metadata=original.metadata,
                images=original.images,
            )
        return messages

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Run Operations with fresh Outline facts preloaded when relevant."""

        knowledge_context = _fresh_operations_outline_context(self, input)
        if knowledge_context:
            context = _with_operations_outline_context(context, knowledge_context)

        run_agent = _operations_model_view(self)
        return OrchestratorAgent.run(run_agent, input, context=context, **kwargs)
