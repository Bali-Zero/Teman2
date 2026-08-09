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
    * Backwards-compatible passthrough when `agent_role=None` for ordinary
      tools; all seven PII-bearing internal tools are denied before it
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
from backend.services.pii.violation_store import hash_subject

logger = logging.getLogger(__name__)

# Tools that touch client/staff PII and must NEVER pass through the
# legacy agent_role=None path or any WhatsApp caller profile (TOURNIQUET,
# Zero GO 2026-07-21 — see
# memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`).
# The module docstring's "zero CRM tools" claim stopped being true once
# `create_agentic_rag` (agentic/__init__.py) registered CRMTool (name
# "crm_query"), TimeSheetTool (name "timesheet"), and TeamKnowledgeTool
# (name "team_knowledge") into the shared tool list — all three then rode
# the blanket no-principal passthrough below. Exact `.name` values verified
# against tools.py (CRMTool ~1009, TimeSheetTool ~919, TeamKnowledgeTool
# ~530); exact match only, never substring (cicatrix-superscar #3).
# `team_knowledge` added round-2 (Codex red-team on the round-1 diff): its
# search branch does `search_term in json.dumps(record).lower()` — an empty
# search_term (the schema default) matches every record, dumping all staff
# PII (email/pin/religion/notes/...) for 19 team members to any no-principal
# caller (blog/ask, WA-unknown).
SENSITIVE_TOOLS = frozenset(
    {
        "crm_query",
        "timesheet",
        "team_knowledge",
        "team_my_clients",
        "team_my_practices",
        "team_my_deadlines",
        "team_practice_detail",
    }
)

# WhatsApp capability ceiling (L0). This is an allowlist, not a denylist:
# any future tool added to the shared agentic registry stays unavailable on
# WhatsApp until it is explicitly reviewed and added here. The trusted
# ``is_whatsapp`` marker is derived by the server from the dedicated WA bot
# credential; it never comes from the request body/channel field.
WA_L0_ALLOWED_TOOLS = frozenset({"vector_search", "get_pricing", "calculator"})

# ``vector_search`` is safe on WhatsApp only across public/low-PII corpora.
# Pricing must use ``get_pricing`` (the canonical PricingTool), never the
# legacy pricing vector collection. Training conversations are excluded
# because the PDP plan classifies them high risk for residual PII.
WA_L0_VECTOR_COLLECTIONS = frozenset(
    {
        "visa_oracle",
        "legal_unified",
        "kbli_2025_final",
        "tax_genius",
        "immigration_circulars",
        "balizero_news",
    }
)


def _truncate(value: Any, max_len: int = 40) -> str:
    """Render a tool argument value short enough for a confirmation modal."""
    s = str(value)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _principal_token(user_email: str | None) -> str:
    """
    Render the calling principal for the `tool_authz` audit log — NEVER the
    raw identifier (PII leak, UU PDP Art. 67-68 / SYMBIOSIS Law 2).

    `user_email` is a misnomer inherited from the JWT-only Phase 2 design:
    `wa_inbox_bot.generate_bot_reply` passes `f"whatsapp_{phone}"` through
    this exact same parameter for the WhatsApp channel, so a client's phone
    number reaches `authorize()`/`_audit()` looking like any other
    principal. Every other current/future channel id (Telegram, web
    session, ...) will do the same.

    Applied UNIFORMLY — no `.startswith`/substring branch on the shape of
    `user_email` decides whether it gets redacted (cicatrix-superscar
    family #3, guard-over/under-match: a shape check here is exactly the
    disease — the next channel id that doesn't happen to match a pattern
    would leak in the clear). Every non-empty principal is pseudonymised,
    full stop; only the true absence of a principal (`None`/empty) renders
    as the literal "anonymous", so a legacy no-principal passthrough stays
    visually distinct from a redacted one.

    Reproducible by an operator: given the original identifier `x` (an
    email or a `whatsapp_<phone>` string), the log token is
    `hash_subject(x)` — see `backend.services.pii.violation_store` — i.e.
    `sha256(x.encode()).hexdigest()[:32]`, prefixed with `h:` so a reader
    can tell at a glance this is a redacted token, never a raw value. Same
    identifier always yields the same token (stable — greppable/correlatable
    across log lines for one principal); different identifiers yield
    different tokens.
    """
    if not user_email:
        return "anonymous"
    return f"h:{hash_subject(user_email)}"


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
        reason: Internal authorization explanation. Callers must render a
            fixed generic observation and never echo this value to the LLM,
            logs, spans, or streaming events.
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
        caller_profile: dict[str, Any] | None = None,
        is_whatsapp: bool = False,
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
            caller_profile: Server-derived audience profile. A non-None value
                is not surface authority, but it does identify a client-like
                caller that must never execute internal tools, even if an
                inconsistent privileged ``agent_role`` is also present.
            is_whatsapp: The sole trusted server-derived WhatsApp surface
                marker. Never derive this from an HTTP body field.

        Returns:
            AuthResult describing the decision. Caller MUST inspect
            `result.is_allowed` and use `result.args` (possibly mutated)
            instead of the original `args` dict.
        """
        # ── WhatsApp L0 allowlist ─────────────────────────────────────────
        # Only the trusted server-side surface marker applies the exact WA
        # capability ceiling. ``caller_profile`` is audience context, not a
        # substitute for channel authority.
        if is_whatsapp and tool_name not in WA_L0_ALLOWED_TOOLS:
            reason = "This capability is not available in this conversation."
            self._audit(
                "deny",
                user_email,
                agent_role,
                tool_name,
                "tool unavailable on WhatsApp L0",
            )
            return AuthResult.deny(reason, args)

        # ── Sensitive-tool deny (TOURNIQUET, 2026-07-21) ──────────────────
        # PII-bearing tools are denied for every profiled client-like caller
        # and for no-principal callers BEFORE the legacy passthrough below.
        # The profile takes precedence over contradictory privileged roles.
        if tool_name in SENSITIVE_TOOLS and (caller_profile is not None or agent_role is None):
            reason = "This capability is not available in this conversation."
            self._audit(
                "deny",
                user_email,
                agent_role,
                tool_name,
                "internal tool unavailable on this surface",
            )
            return AuthResult.deny(reason, args)

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

        # ── 3. Confirmation requirement (VASSAL Phase 3) ──────────────────
        # When Phase 3 landed, `AgentRole` grew a `requires_confirmation:
        # list[str]` field. If the requested tool is in that list, this
        # branch returns AuthResult.confirm() with a preview reason that
        # tool_executor forwards to ConfirmationService.request_and_wait.
        # For tools NOT in the list, `_check_requires_confirmation` still
        # returns None and the ALLOWED path below fires.
        confirm_result = self._check_requires_confirmation(
            user_email,
            agent_role,
            tool_name,
            args,
        )
        if confirm_result is not None:
            self._audit(
                "needs_confirmation",
                user_email,
                agent_role,
                tool_name,
                confirm_result.reason,
            )
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

        VASSAL Phase 3: no longer a no-op. If the role's
        `requires_confirmation` list contains this tool, return
        AuthResult.confirm() with a human-readable preview reason. The
        tool_executor then awaits ConfirmationService.request_and_wait
        with that reason as the SSE `preview` field, and either proceeds
        or denies based on the user's decision.

        Returns None for tools that are not gated — callers keep their
        normal ALLOWED-path behavior. This preserves the Phase 2 contract
        for every tool not explicitly listed.
        """
        _ = user_email  # reserved for future per-user overrides
        required = getattr(agent_role, "requires_confirmation", None) or []
        if tool_name not in required:
            return None
        reason = self._build_confirmation_preview(agent_role, tool_name, args)
        return AuthResult.confirm(reason=reason, args=args)

    @staticmethod
    def _build_confirmation_preview(
        agent_role: AgentRole,
        tool_name: str,
        args: dict[str, Any],
    ) -> str:
        """
        Build the preview reason surfaced to the user in the SSE
        `confirmation_required` event and used as the LLM observation
        when the user rejects.

        The text must be informative enough that a reasonable user can
        decide approve/reject without additional context, and short
        enough to render in a small modal (see Phase 3B frontend).
        """
        # Keep args short — modal UI will truncate anyway.
        arg_preview = ", ".join(f"{k}={_truncate(v)}" for k, v in list(args.items())[:4])
        if len(args) > 4:
            arg_preview += f", … (+{len(args) - 4} more)"
        return (
            f"Tool '{tool_name}' requires user confirmation for role "
            f"'{agent_role.role_id}'. Arguments: {{{arg_preview}}}"
        )

    @staticmethod
    def _audit(
        action: str,
        user_email: str | None,
        agent_role: AgentRole | None,
        tool_name: str,
        _reason: str,
    ) -> None:
        """
        Structured audit log line for every decision.

        We use a single logger format that downstream log shippers can
        grep/parse. The "tool_authz" prefix is unique to this module.

        Phase 3 adds `needs_confirmation` as a third decision value
        alongside `allow` and `deny`. ``_reason`` is deliberately excluded:
        confirmation previews can be derived from model-supplied arguments
        and therefore must not enter logs.

        `user=` is a pseudonymised token (`_principal_token`), never the raw
        `user_email` — see that function's docstring. This fires on EVERY
        tool call (allow included, not just deny), so it is the highest
        volume of the two PII surfaces this module has had (the other being
        the SENSITIVE_TOOLS deny path added 2026-07-21).
        """
        role_id = agent_role.role_id if agent_role else "none"
        scope = agent_role.client_scope if agent_role else "none"
        # `allow` is INFO; everything else (`deny`, `needs_confirmation`)
        # is WARNING because both are exceptional outcomes worth surfacing.
        log_fn = logger.info if action == "allow" else logger.warning
        log_fn(
            "tool_authz decision=%s user=%s role=%s scope=%s tool=%s",
            action,
            _principal_token(user_email),
            role_id,
            scope,
            tool_name,
        )


__all__ = [
    "AuthDecision",
    "AuthResult",
    "ToolAuthorizer",
]
