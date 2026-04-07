"""
Tool Authorizer — Server-side RBAC for the agentic ReAct loop.

This module is the canonical authorization point for any tool the agentic
orchestrator (`backend.services.rag.agentic.AgenticRAGOrchestrator`) attempts
to execute on behalf of an authenticated team agent. It is invoked from the
chokepoint `backend.services.rag.agentic.tool_executor.execute_tool` and
returns an `AuthResult` describing whether the call is allowed, denied, or
needs interactive confirmation (the latter is scaffolding for Phase 3).

Phase 2 scope (VASSAL_PLAN_V7 §7 Week 2 — "Strada B"):
    * Default-deny via `team_agent_config.is_tool_allowed`
    * Blocked-tools enforcement
    * Audit logging on every decision (allow + deny)
    * Backwards-compatible passthrough when `agent_role=None`
      (legacy /stream endpoint and any caller without an authenticated
      team agent — the orchestrator must remain functional for blog and
      marketing flows)
    * Scaffolding (NOT enforced) for `client_scope` and `requires_confirmation`
      — see "Scaffolding rationale" below

Out of Phase 2 scope (planned for later phases):
    * `verify_client_access` injection for tools accepting `client_id`
      (deferred to Strada A: requires CRM tools to be registered as
      `BaseTool` instances inside the agentic loop, which they are NOT
      today — see VASSAL_PHASE2_HANDOFF.md)
    * `_force_assigned_to` filter injection for list_clients-style tools
    * Real interactive confirmation gates — Phase 3 will implement
      `confirmation_service` and flip NEEDS_CONFIRMATION from scaffold
      to active

Source of truth for roles & allowlists:
    `backend.services.agents.team_agent_config.TEAM_AGENTS`. The authorizer
    intentionally does NOT consult `backend.app.utils.crm_utils` (which has
    its own divergent admin lists used by the REST CRM routers). This is a
    documented two-source-of-truth situation, tracked for resolution in
    Phase 7 of VASSAL_PLAN_V8 ("Policy Source Unification via shared YAML").
    Until then, the authorizer's lane is the agentic ReAct loop and only
    that lane.

Scaffolding rationale (client_scope + requires_confirmation):
    The current ReAct tool registry has 9 tools (vector_search, pricing,
    team_knowledge, knowledge_graph, calculator, vision, image_generation,
    web_search, timesheet). NONE of them accept `client_id` and NONE of
    them are write actions that need confirmation today. So the
    `client_scope` and `requires_confirmation` checks are present in the
    code path but are no-ops for the current tool set.

    This is INFRASTRUCTURE, not a corner cut: when Phase 3 wires real
    confirmation gates and when (eventually) CRM tools are registered into
    the agentic loop, the AuthResult shape and the ToolAuthorizer entry
    point do NOT change. Callers (`tool_executor.execute_tool`) and
    consumers (Phase 3 confirmation service) can be built against the
    stable interface today.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.services.agents.team_agent_config import AgentRole, is_tool_allowed

logger = logging.getLogger(__name__)


class AuthDecision(str, Enum):
    """Outcome of an authorization check."""

    ALLOWED = "allowed"
    DENIED = "denied"
    NEEDS_CONFIRMATION = "needs_confirmation"  # Scaffolding for Phase 3


@dataclass(frozen=True)
class AuthResult:
    """
    Result of `ToolAuthorizer.authorize`.

    Attributes:
        decision: One of ALLOWED / DENIED / NEEDS_CONFIRMATION.
        reason: Human-readable explanation. Echoed back to the LLM as the
            tool observation when DENIED, so it should be informative
            enough for the model to decide what to do next ("you don't
            have permission to call X, try Y instead").
        args: Possibly mutated tool arguments. Phase 2 returns args
            unchanged. Phase 3+ may inject server-controlled fields
            (e.g. `_force_assigned_to=user_email`) when scope filters
            are applied to list-style tools.
    """

    decision: AuthDecision
    reason: str = ""
    args: dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.decision == AuthDecision.ALLOWED

    @property
    def is_denied(self) -> bool:
        return self.decision == AuthDecision.DENIED

    @property
    def needs_confirmation(self) -> bool:
        return self.decision == AuthDecision.NEEDS_CONFIRMATION

    @classmethod
    def allow(cls, args: dict[str, Any] | None = None) -> AuthResult:
        return cls(decision=AuthDecision.ALLOWED, reason="", args=args or {})

    @classmethod
    def deny(cls, reason: str, args: dict[str, Any] | None = None) -> AuthResult:
        return cls(decision=AuthDecision.DENIED, reason=reason, args=args or {})

    @classmethod
    def confirm(cls, reason: str, args: dict[str, Any] | None = None) -> AuthResult:
        """Phase 3 scaffold — never returned by Phase 2 implementation."""
        return cls(decision=AuthDecision.NEEDS_CONFIRMATION, reason=reason, args=args or {})


class ToolAuthorizer:
    """
    Stateless authorizer. Safe to instantiate once at process start and
    share across requests (no instance state, no I/O).

    Phase 3 will give it a `confirmation_service` dependency for real
    NEEDS_CONFIRMATION handling. The Phase 2 constructor accepts no
    arguments to keep the migration trivial.
    """

    def __init__(self) -> None:
        # Intentionally empty. Phase 3 will add `confirmation_service` here.
        pass

    async def authorize(
        self,
        user_email: str | None,
        agent_role: AgentRole | None,
        tool_name: str,
        args: dict[str, Any],
    ) -> AuthResult:
        """
        Authorize a tool call.

        The function is async because Phase 3 confirmation gates will need
        to await Redis state and the SSE confirmation future. Keeping the
        signature awaitable from day one means `tool_executor.execute_tool`
        does not need a second refactor when Phase 3 lands.

        Args:
            user_email: Authenticated user email (from JWT). May be None
                for legacy/anonymous callers, in which case `agent_role`
                must also be None.
            agent_role: The user's AgentRole from `team_agent_config`, or
                None if the caller is not a registered team agent (this
                is the legacy /stream path; we passthrough as ALLOWED for
                backward compatibility — see module docstring).
            tool_name: Name of the tool the LLM wants to call.
            args: Tool arguments parsed from the LLM's function call.

        Returns:
            AuthResult describing the decision. Caller MUST inspect
            `result.is_allowed` and use `result.args` (possibly mutated)
            instead of the original `args` dict.
        """
        # ── Backward compatibility ────────────────────────────────────────
        # Legacy /stream endpoint and any non-authenticated path passes
        # `agent_role=None`. We do NOT enforce in that case — the legacy
        # endpoint serves blog/marketing flows that are intentionally
        # auth-optional. Phase 1 endpoint splitting already established
        # this contract.
        if agent_role is None:
            self._audit("allow", user_email, agent_role, tool_name, "no agent_role (legacy path)")
            return AuthResult.allow(args)

        # ── 1. Default-deny via team_agent_config allowlist ──────────────
        # Single source of truth: `is_tool_allowed` already implements
        # the (blocked > allowed > admin-empty-allowlist) precedence we
        # want. Reusing it avoids drift between authorizer and config.
        if not is_tool_allowed(agent_role, tool_name):
            reason = self._build_deny_reason(agent_role, tool_name)
            self._audit("deny", user_email, agent_role, tool_name, reason)
            return AuthResult.deny(reason, args)

        # ── 2. Client-scope enforcement (SCAFFOLDING) ────────────────────
        # No-op for the current 9-tool registry: none of them accept
        # `client_id`. When CRM tools land (Strada A, future), this is
        # where verify_client_access injection plugs in. The hook is
        # left explicit so Phase 3+ does not need to refactor authorize().
        scope_result = self._check_client_scope(user_email, agent_role, tool_name, args)
        if scope_result is not None:
            return scope_result

        # ── 3. Confirmation requirement (SCAFFOLDING) ────────────────────
        # No-op for Phase 2: AgentRole has no `requires_confirmation`
        # field yet. Phase 3 will add it and this branch will start
        # returning NEEDS_CONFIRMATION for write tools like
        # `delete_client`, `delete_practice`, etc.
        confirm_result = self._check_requires_confirmation(
            user_email, agent_role, tool_name, args,
        )
        if confirm_result is not None:
            return confirm_result

        # ── ALLOWED ──────────────────────────────────────────────────────
        self._audit("allow", user_email, agent_role, tool_name, "in allowlist")
        return AuthResult.allow(args)

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_deny_reason(role: AgentRole, tool_name: str) -> str:
        """Build a structured deny reason that the LLM can read back."""
        if role.blocked_tools and tool_name in role.blocked_tools:
            return (
                f"Tool '{tool_name}' is explicitly blocked for role "
                f"'{role.role_id}'. Choose a different tool."
            )
        return (
            f"Tool '{tool_name}' is not in the allowlist for role "
            f"'{role.role_id}'. Choose a different tool."
        )

    def _check_client_scope(
        self,
        user_email: str | None,
        agent_role: AgentRole,
        tool_name: str,
        args: dict[str, Any],
    ) -> AuthResult | None:
        """
        Check client_scope constraint.

        Returns an AuthResult ONLY if a scope check fires (deny or
        scope-injected allow). Returns None if no scope rule applies,
        in which case the caller continues with subsequent checks.

        Phase 2 scope: scaffold only. The agentic loop has zero CRM
        tools and zero tools that accept `client_id`, so this method
        currently always returns None. The hook stays so Phase 3+ /
        Strada A can fill it in without modifying `authorize()`.
        """
        # Phase 2: no-op. Method body intentionally empty until tools
        # that accept `client_id` are registered into the loop.
        _ = (user_email, agent_role, tool_name, args)  # silence unused
        return None

    def _check_requires_confirmation(
        self,
        user_email: str | None,
        agent_role: AgentRole,
        tool_name: str,
        args: dict[str, Any],
    ) -> AuthResult | None:
        """
        Check whether the tool requires interactive user confirmation.

        Phase 2 scope: scaffold only. `AgentRole` does not yet have a
        `requires_confirmation: list[str]` field. When Phase 3 adds it,
        this method becomes `if tool_name in agent_role.requires_confirmation: return AuthResult.confirm(...)`.

        Returns None today.
        """
        _ = (user_email, agent_role, tool_name, args)
        return None

    @staticmethod
    def _audit(
        action: str,
        user_email: str | None,
        agent_role: AgentRole | None,
        tool_name: str,
        reason: str,
    ) -> None:
        """
        Structured audit log line for every decision.

        We use a single logger format that downstream log shippers can
        grep/parse. The "tool_authz" prefix is unique to this module.
        """
        role_id = agent_role.role_id if agent_role else "none"
        scope = agent_role.client_scope if agent_role else "none"
        log_fn = logger.info if action == "allow" else logger.warning
        log_fn(
            "tool_authz decision=%s user=%s role=%s scope=%s tool=%s reason=%s",
            action,
            user_email or "anonymous",
            role_id,
            scope,
            tool_name,
            reason,
        )


__all__ = [
    "AuthDecision",
    "AuthResult",
    "ToolAuthorizer",
]
