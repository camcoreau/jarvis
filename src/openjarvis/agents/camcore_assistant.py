"""CamCore Jarvis agent built on the OpenJarvis orchestrator."""

from __future__ import annotations

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
- For documented CamCore architecture, server roles, services, policies, standards,
  procedures, or configuration, consult the CamCore Outline knowledge source before
  answering when the relevant MCP tools are available.
- Use ``list_documents`` to find relevant documentation and ``fetch`` to read the
  selected document before relying on it.
- Treat Outline as authoritative for documented state, but not as proof of current
  runtime health, reachability, or live service status.
- If no relevant documentation is found, say so and do not invent undocumented
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


def _guardrail_redact_operations_context(text: str) -> str:
    """Pre-redact retrieval with the same scanners used by GuardrailsEngine.

    Operations Outline context is server-generated, but it still passes through the
    inference engine's BLOCK-mode input scanner. Applying the canonical redactors
    here prevents already-retrieved documentation from blocking the whole request,
    without weakening scanning of user input or model output.
    """

    try:
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        safe = text
        for scanner in (SecretScanner(), PIIScanner()):
            safe = scanner.redact(safe)
        return safe
    except Exception:
        logger.warning(
            "CamCore operations Outline guardrail redaction failed",
            exc_info=True,
        )
        return ""


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
        return super().run(input, context=context, **kwargs)
