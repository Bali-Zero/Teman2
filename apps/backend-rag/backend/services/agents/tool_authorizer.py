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
    * A DB-backed ownership check for tools accepting a bare `client_id` /
      `practice_id` (e.g. `get_client(client_id=...)`) is still deferred —
      this class is documented as stateless/no-I/O, and per F5/F7 the
      CRM endpoint independently enforces `assigned_to` for those anyway
      (endpoint authorization is the boundary; this authorizer is
      early-deny only). `_check_client_scope` (below) is no longer a pure
      no-op: it DOES enforce the `assigned_to` staff-scope filter argument
      (F5's `list_practices`/`create_reminder`/`open_practice` shape),
      which is verifiable in-process without touching Postgres.
    * `_force_assigned_to`-style filter INJECTION for list_clients-style
      tools is still not implemented — a `deny`, not a silent
      server-side override of an LLM-chosen argument, is what this class
      offers instead (an override risks the model believing its own
      argument was honored when it was not; a deny is auditable and
      round-trips back to the model as an observation it can act on).
    * Real interactive confirmation gates — Phase 3 will implement
      `confirmation_service` and flip NEEDS_CONFIRMATION from scaffold
      to active

Source of truth for roles & allowlists:
    `backend.services.agents.team_agent_config.TEAM_AGENTS` remains the
    source of truth for role → tool allowlist (step 1 above) and for the
    admin bypass on `_check_client_scope` (`agent_role.client_scope ==
    "all"`, checked FIRST and with no I/O — see that method's docstring
    for why it must be checked before, not instead of, `crm_access.py`'s
    own admin notion).

    F5 (docs/plans/2026-08-25-due-bot-live/MANDATE.md) explicitly asks this
    module to "reuse ... `crm_access.py` filters", so `_check_client_scope`
    now DOES call `backend.app.deps.crm_access.get_crm_user_filter` (which
    itself defers to `backend.app.utils.crm_utils.is_crm_admin`) for the
    "assigned"-scope case — a deliberate, narrow crossing of the boundary
    below, not its removal: `verify_client_access` (crm_utils.py's
    per-record, DB-backed check used by the REST CRM routers) is still not
    consulted, and the broader two-source-of-truth question this section
    used to describe is NOT resolved by this change, only narrowed to the
    one check that needed it. This is a documented two-source-of-truth
    situation, tracked for resolution in Phase 7 of VASSAL_PLAN_V8 ("Policy
    Source Unification via shared YAML"). Until then, the authorizer's lane
    is the agentic ReAct loop and only that lane.

Scaffolding rationale (client_scope + requires_confirmation):
    The current ReAct tool registry has 9 tools (vector_search, pricing,
    team_knowledge, knowledge_graph, calculator, vision, image_generation,
    web_search, timesheet). NONE of them accept `client_id`/`practice_id`/
    `assigned_to` and NONE of them are write actions that need confirmation
    today. So `_check_client_scope` and `_check_requires_confirmation` are
    both REAL checks (not stubs) whose bodies simply never fire for the
    current tool set — every one of them returns None on the very first
    line, `_extract_scope_filter_value(args)` finding nothing to inspect.

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

from backend.app.deps.crm_access import get_crm_user_filter
from backend.services.agents.team_agent_config import AgentRole, get_agent_role, is_tool_allowed
from backend.services.pii.violation_store import hash_subject

logger = logging.getLogger(__name__)

# F5 (docs/plans/2026-08-25-due-bot-live/MANDATE.md): "complete or bypass the
# no-op `_check_client_scope`... before any mutation arms". Argument keys
# `_check_client_scope` inspects to decide whether a call needs scope
# verification at all — deliberately narrow, and deliberately NOT `client_id`
# / `practice_id` (see that method's docstring for why a bare record
# reference is excluded on purpose, not by oversight).
CLIENT_SCOPE_FILTER_KEYS = frozenset({"assigned_to"})

# Tools that touch client/staff PII and must NEVER pass through the
# legacy agent_role=None path (TOURNIQUET, Zero GO 2026-07-21 — see
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
SENSITIVE_TOOLS = frozenset({"crm_query", "timesheet", "team_knowledge"})


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
        # ── Sensitive-tool deny (TOURNIQUET, 2026-07-21) ──────────────────
        # PII-bearing tools are denied for no-principal callers BEFORE the
        # legacy passthrough below, regardless of agent_role. This closes
        # the public blog/ask + WA-unknown ReAct vector without touching
        # the passthrough's behavior for every other tool.
        if tool_name in SENSITIVE_TOOLS and agent_role is None:
            reason = "This action needs an authenticated Bali Zero staff account."
            self._audit(
                "deny",
                user_email,
                agent_role,
                tool_name,
                "sensitive tool requires authenticated staff principal",
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

        # ── 2. Client-scope enforcement (F5) ──────────────────────────────
        # Still a no-op for the current 9-tool registry — none of them
        # carry an `assigned_to` argument — but the check itself is now
        # real (see `_check_client_scope`'s docstring): a call carrying
        # `args["assigned_to"]` that names a staff member other than the
        # caller, from a non-admin caller, is denied here BEFORE step 3.
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
        Early-deny a client-scope violation this authorizer can verify
        without a database round-trip (F5: "complete or bypass the no-op
        `_check_client_scope`... before any mutation arms").

        Returns `AuthResult.deny(...)` ONLY when it can be CERTAIN, from
        `args` + `agent_role` alone, that the call is out of scope. Every
        other path returns `None` — including "no restriction applies"
        AND "cannot verify, so don't guess". `None` never means "allowed
        unconditionally": per F7, "CRM routes independently enforce
        `assigned_to` (endpoint authorization is the boundary; the local
        authorizer is early-deny only)" — this method is that early,
        optional, no-I/O layer, not the boundary itself. A `None` here
        just means the (still-authoritative) endpoint decides on its own.

        Structural extraction (never string-sniffing a value): the ONLY
        argument key inspected is `assigned_to` (`CLIENT_SCOPE_FILTER_KEYS`
        — see its module-level comment for why bare `client_id` /
        `practice_id` record references are deliberately excluded: whether
        a SPECIFIC record belongs to this caller lives in Postgres
        (`clients.assigned_to` / `practices.assigned_to`), and this class
        is documented as stateless/no-I/O — verifying that would mean
        adding a DB round-trip here, which is exactly what F7 assigns to
        the endpoint instead). `assigned_to` is different: it is a
        staff-scoping filter/target ARGUMENT the tool itself declares
        (F5's `list_practices`, `create_reminder`, `open_practice` in
        `apps/team-bot/team_bot/registry/tools.py`), expressed in the same
        identity currency as `user_email` — comparable in-process, with
        zero I/O, exactly like `crm_access.get_crm_user_filter`'s own
        documented "WHERE assigned_to = $N" usage.

        Admin bypass (checked in this order; each is sufficient on its
        own — the deny path below only runs if BOTH say "not an admin"):
          1. `agent_role.client_scope == "all"` — this authorizer's own
             role model (`team_agent_config.py`), checked FIRST and with
             NO further I/O. Needed because `crm_access.py`'s narrower
             CRM-admin allowlist does not recognise every role this field
             already marks unrestricted (verified empirically: the tax
             team — `client_scope="all"` — is absent from
             `crm_utils.is_crm_admin`'s allowlists).
          2. `get_crm_user_filter` (`backend.app.deps.crm_access` — F5:
             "reuse ... `crm_access.py` filters") returns `None` — a
             genuine CRM admin per THAT source even though this role's
             own `client_scope` says "assigned" (e.g. `ruslana@balizero.com`,
             role `crm_full`, recognised via
             `crm_utils.PRACTICES_EXTRA_VIEW_EMAILS`). Reused, not
             re-derived, per F5's explicit instruction not to compute
             assigned_to filtering a third time (the same computation
             already exists in `crm_access.get_crm_user_filter` and
             `team_crm_tools.resolve_team_crm_scope`).

        For everyone else, `args["assigned_to"]` (if present) must equal
        the caller's own scope filter — case/whitespace-insensitive —
        or the call is denied.

        One more guard before that comparison ever fires: `get_agent_role
        (user_email) == agent_role` must hold. `user_email` is a misnomer
        (see `_principal_token`'s docstring) — on the WhatsApp channel it
        is `whatsapp_<phone>`, not a real email, even when `agent_role`
        was correctly resolved via a DIFFERENT, separately-trusted email
        upstream (`agentic_rag.py::_derive_wa_agent_role`). Comparing a
        phone-shaped principal against a real `assigned_to` email would
        NEVER match, which would silently deny a WhatsApp-channel caller
        referencing their OWN book. Skipping the comparison in that case
        (deferring to the endpoint, per F7) is the safe direction: a
        missed early-deny costs nothing (the endpoint still enforces the
        real boundary); a wrongful deny would be a usability regression
        with no compensating safety benefit.
        """
        identifier_value: Any = None
        for key in CLIENT_SCOPE_FILTER_KEYS:
            if key in args:
                identifier_value = args[key]
                break
        if identifier_value is None:
            return None  # no scope-carrying argument present — untouched

        if agent_role.client_scope == "all":
            return None

        if get_agent_role(user_email or "") != agent_role:
            # Cannot confirm `user_email` is a real, comparable identity
            # for this `agent_role` (e.g. the WA channel's phone-shaped
            # pseudo-id) — defer to the endpoint rather than risk a false
            # deny for a legitimate self-reference.
            return None

        scope_filter = get_crm_user_filter(current_user={"email": user_email or ""})
        if scope_filter is None:
            # crm_access.py also considers this caller an admin, even
            # though this role's own `client_scope` says "assigned".
            return None

        claimed = str(identifier_value).strip().lower()
        if claimed != scope_filter:
            reason = (
                f"Tool '{tool_name}' argument 'assigned_to' names a staff "
                f"member outside your assigned client scope."
            )
            self._audit("deny", user_email, agent_role, tool_name, reason)
            return AuthResult.deny(reason, args)

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
        reason: str,
    ) -> None:
        """
        Structured audit log line for every decision.

        We use a single logger format that downstream log shippers can
        grep/parse. The "tool_authz" prefix is unique to this module.

        Phase 3 adds `needs_confirmation` as a third decision value
        alongside `allow` and `deny`. The format string is unchanged so
        existing log shipper grep patterns keep working.

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
            "tool_authz decision=%s user=%s role=%s scope=%s tool=%s reason=%s",
            action,
            _principal_token(user_email),
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
