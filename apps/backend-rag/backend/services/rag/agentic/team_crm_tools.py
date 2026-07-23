"""WA team-assistant Phase 2 — CRM-scoped read-only tools per team member.

Zero's GO (2026-07-20, ruling captured in memory
`decision_wa_team_assistant_phase2_crm_go_2026_07_20.md`): a Bali Zero team
member messaging the Zantara WA bot can ask about THEIR OWN clients,
practices, and upcoming deadlines — never anyone else's. V1
(`whatsapp_identity.py` + `wa_inbox_bot.py`, PR #2872) already resolves the
inbound sender's identity and forwards it as `profile` (`role`
"creator"/"team", optional `name`/`email`) all the way into
`user_context["profile"]` inside the agentic orchestrator
(`orchestrator_core.py::process_query_core`).

Design (V2a, per the ruling — read this before changing scope):

* **4 deterministic intents**, not free SQL: my-clients, my-practices,
  my-deadlines, practice-detail-by-name. Every query is a parameterized
  SQL statement with a fixed shape — the LLM chooses WHICH tool/params,
  never the WHERE clause.
* **RBAC chain** identical to the REST CRM routers (CLAUDE.md §13 /
  `backend/services/crm_shared_memory.py`): `LOWER(c.assigned_to) =
  LOWER(<team member email>)` unless the caller is an admin (reuses
  `backend.app.utils.crm_utils.is_crm_admin` — the SAME allowlist the REST
  CRM endpoints use, not a second copy).
* **Read-only.** No INSERT/UPDATE/DELETE anywhere in this module.
* **Scope comes from the server, never the LLM.** Every `execute()` reads
  the caller's identity from a `_caller_profile` kwarg injected by
  `tool_executor.execute_tool()` (mirrors the existing `_user_id`
  injection there) — `parameters_schema` never exposes an
  email/assigned_to/scope field an LLM could set. This closes the same
  class of bug the 2026-07-20 adversarial-review fix on V1 closed
  (`agentic_rag.py` — caller-supplied identity must never be trusted).
* **Hard-absence when the flag is off.** `create_agentic_rag()`
  (`backend/services/rag/agentic/__init__.py`) only appends these tools to
  the orchestrator's fixed tool list when `WA_TEAM_CRM_TOOLS_ENABLED` is
  truthy — the flag is read ONCE at orchestrator-construction time, so
  when it's off (the shipped default) these tools do not exist anywhere
  in the Gemini function-declaration schema, for ANY caller. When the flag
  is on, `execute()` still self-gates on `profile.role` before touching
  the database — a client/unknown sender's `_caller_profile` is `None`
  (V1's innocence contract), so the tool returns a static "not available"
  string with zero DB access.
* **No PII in logs.** Every log line here uses `client_id` / row counts,
  never `full_name`/email — UU PDP boundary (CLAUDE.md §14).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.logging_utils import get_logger
from backend.services.tools.definitions import BaseTool

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Feature flag — default OFF (rollout plan: flag OFF -> deploy -> prove-live
# with Zero + 1 pilot member -> flag ON via Fly secret, operator step).
# Mirrors the exact pattern of WA_INBOX_BOT_AUTOREPLY in wa_inbox_bot.py.
# ---------------------------------------------------------------------------


def is_team_crm_tools_enabled() -> bool:
    """True only when the Fly secret WA_TEAM_CRM_TOOLS_ENABLED is truthy.

    Read once at orchestrator-construction time (see `create_agentic_rag`
    in `__init__.py`) — NOT re-read per request. Arm with:
    ``fly secrets set WA_TEAM_CRM_TOOLS_ENABLED=true -a nuzantara-rag``.
    """
    return os.getenv("WA_TEAM_CRM_TOOLS_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ---------------------------------------------------------------------------
# Scope resolution — pure function, no I/O. Reuses the SAME admin allowlist
# the REST CRM routers use (backend.app.utils.crm_utils.is_crm_admin), per
# the ruling: "read the authoritative admin list from wherever CRM RBAC
# already defines it — do NOT hardcode a new copy".
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamCrmScope:
    """Resolved authorization scope for a single tool call.

    `is_admin=True` -> no assigned_to filter (sees the whole book).
    `is_admin=False, email=<addr>` -> filter WHERE LOWER(assigned_to)=email.
    `is_admin=False, email=None` -> identity resolved to "team" but no
        usable email (env-override `WHATSAPP_TEAM_NUMBERS` path, which
        carries no email) -- tools must refuse with a clear message, NEVER
        fall back to showing everything or nothing-filtered.
    """

    is_admin: bool
    email: str | None


def resolve_team_crm_scope(profile: dict[str, Any] | None) -> TeamCrmScope | None:
    """Resolve the caller's CRM scope from the (already-trusted) profile dict.

    Returns ``None`` for anyone who is not team/creator (client, unknown,
    or profile absent entirely) — the tool-level "hard innocence" gate.
    `profile` here is whatever V1 threaded into
    ``user_context["profile"]``; by the time it reaches this module it has
    already passed the router-level trust gate (2026-07-20 adversarial-review
    fix: only forwarded for `current_user.role in ("internal", "admin")`).
    This function does not re-derive trust — it only maps role -> scope.
    """
    if not profile:
        return None

    role = str(profile.get("role", "")).strip().lower()

    if role == "creator":
        # The WA "owner" number (Zero) — always admin scope, matching the
        # ruling's admin list. No email is carried in the creator profile
        # (see whatsapp_identity.py `_owner_numbers()`), so we do not try
        # to look one up here — creator == full access, full stop.
        return TeamCrmScope(is_admin=True, email=None)

    if role == "team":
        email = str(profile.get("email") or "").strip().lower()
        if email and is_crm_admin({"email": email}):
            # A team-resolved sender whose email is ALSO in the admin
            # allowlist (e.g. asya@balizero.com resolving via the
            # team_members DB path rather than the owner-number path).
            return TeamCrmScope(is_admin=True, email=email)
        return TeamCrmScope(is_admin=False, email=email or None)

    return None


def is_team_or_creator_profile(profile: dict[str, Any] | None) -> bool:
    """True when `profile.role` is "team" or "creator".

    Used by `orchestrator_core.py`'s FAQ/semantic-cache gate: team-mode
    answers must NEVER be read from or written to a shared cache (ruling
    2026-07-20: "team-answer MAI in cache/log in chiaro"). Deliberately
    independent of `is_team_crm_tools_enabled()` — the cache-PII concern
    holds even when the CRM-tools flag is off, since V1's persona framing
    (TEAM_PERSONA/CREATOR_PERSONA) is already live and could itself leak
    into a shared cache entry.
    """
    if not profile:
        return False
    return str(profile.get("role", "")).strip().lower() in ("team", "creator")


def _scope_from_kwargs(kwargs: dict[str, Any]) -> TeamCrmScope | None:
    """Pop `_caller_profile` (server-injected, see tool_executor.execute_tool)
    and resolve it. Never present in `parameters_schema` — an LLM cannot
    set or forge it."""
    profile = kwargs.get("_caller_profile")
    if not is_team_crm_tools_enabled():
        # Defense-in-depth: even if a future refactor registers these tools
        # unconditionally, execute() still refuses when the flag is off.
        return None
    return resolve_team_crm_scope(profile)


_NOT_AVAILABLE = json.dumps(
    {
        "available": False,
        "message": "This tool is only available to authenticated Bali Zero team members.",
    }
)

_IDENTITY_UNRESOLVED = json.dumps(
    {
        "available": False,
        "message": (
            "Your team identity could not be matched to a CRM email — "
            "ask an admin to add your WhatsApp number to team_members."
        ),
    }
)


# ---------------------------------------------------------------------------
# Limits — mirrors backend/app/routers/crm_shared_memory.py constants.
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 10
MAX_LIMIT = 30
DEFAULT_DAYS_AHEAD = 60
MAX_DAYS_AHEAD = 365


def _clamp_limit(limit: Any) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


def _clamp_days(days: Any) -> int:
    try:
        n = int(days)
    except (TypeError, ValueError):
        return DEFAULT_DAYS_AHEAD
    return max(1, min(n, MAX_DAYS_AHEAD))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class TeamMyClientsTool(BaseTool):
    """V2a intent (a): the caller's own clients, with a practice count."""

    def __init__(self, db_pool: asyncpg.Pool | None) -> None:
        self.db_pool = db_pool

    @property
    def name(self) -> str:
        return "team_my_clients"

    @property
    def description(self) -> str:
        return (
            "List the CALLER'S OWN CRM clients (name + active practice count). "
            "Only usable by an authenticated Bali Zero team member — returns "
            "nothing for anyone else. Use for 'my clients', 'i miei clienti', "
            "'klien saya'."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": f"Max clients to return (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
                },
            },
            "required": [],
        }

    async def execute(self, limit: int = DEFAULT_LIMIT, **kwargs: Any) -> str:
        scope = _scope_from_kwargs(kwargs)
        if scope is None:
            return _NOT_AVAILABLE
        if not scope.is_admin and not scope.email:
            return _IDENTITY_UNRESOLVED
        if self.db_pool is None:
            return json.dumps({"available": True, "clients": [], "error": "db_unavailable"})

        limit = _clamp_limit(limit)
        sql = """
            SELECT c.id, c.full_name,
                   COUNT(p.id) FILTER (WHERE p.status <> 'cancelled') AS practice_count
            FROM clients c
            LEFT JOIN practices p ON p.client_id = c.id
        """
        params: list[Any] = []
        if not scope.is_admin:
            sql += " WHERE LOWER(c.assigned_to) = $1"
            params.append(scope.email)
        sql += f" GROUP BY c.id, c.full_name ORDER BY c.full_name LIMIT ${len(params) + 1}"
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        logger.info(
            "team_crm_tools.my_clients",
            extra={"admin_scope": scope.is_admin, "result_count": len(rows)},
        )
        return json.dumps(
            {
                "available": True,
                "clients": [
                    {
                        "client_id": r["id"],
                        "full_name": r["full_name"],
                        "practice_count": r["practice_count"],
                    }
                    for r in rows
                ],
            }
        )


class TeamMyPracticesTool(BaseTool):
    """V2a intent (b): the caller's own practices + status."""

    def __init__(self, db_pool: asyncpg.Pool | None) -> None:
        self.db_pool = db_pool

    @property
    def name(self) -> str:
        return "team_my_practices"

    @property
    def description(self) -> str:
        return (
            "List the CALLER'S OWN CRM practices (client name, practice type, "
            "status). Only usable by an authenticated Bali Zero team member. "
            "Use for 'my practices', 'le mie pratiche', 'praktik saya'."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": (
                        "Optional practice status filter (e.g. 'on_process', "
                        "'waiting_documents', 'completed'). Omit for all statuses."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": f"Max practices to return (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        status: str | None = None,
        limit: int = DEFAULT_LIMIT,
        **kwargs: Any,
    ) -> str:
        scope = _scope_from_kwargs(kwargs)
        if scope is None:
            return _NOT_AVAILABLE
        if not scope.is_admin and not scope.email:
            return _IDENTITY_UNRESOLVED
        if self.db_pool is None:
            return json.dumps({"available": True, "practices": [], "error": "db_unavailable"})

        limit = _clamp_limit(limit)
        sql = """
            SELECT p.id, p.status, p.expiry_date, p.created_at,
                   pt.name AS practice_type, c.full_name AS client_name
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE 1=1
        """
        params: list[Any] = []
        if not scope.is_admin:
            params.append(scope.email)
            sql += f" AND LOWER(c.assigned_to) = ${len(params)}"
        if status:
            params.append(status)
            sql += f" AND p.status = ${len(params)}"
        params.append(limit)
        sql += f" ORDER BY p.created_at DESC LIMIT ${len(params)}"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        logger.info(
            "team_crm_tools.my_practices",
            extra={"admin_scope": scope.is_admin, "result_count": len(rows)},
        )
        return json.dumps(
            {
                "available": True,
                "practices": [
                    {
                        "practice_id": r["id"],
                        "client_name": r["client_name"],
                        "practice_type": r["practice_type"],
                        "status": r["status"],
                        "expiry_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
                    }
                    for r in rows
                ],
            }
        )


class TeamMyDeadlinesTool(BaseTool):
    """V2a intent (c): expiring deadlines for the caller's own clients.

    Reuses the two existing compliance/expiry surfaces rather than
    reinventing a query:
    - `client_expiry_alerts_view` (passport/visa/kitas/e_visa/document —
      same view `backend/app/routers/crm_enhanced_alerts.py` reads).
    - `compliance_alerts` (visa_expiry/document_expiry/license_renewal/
      lkpm/tax categories — same table `backend/app/routers/
      compliance_alerts.py` reads), joined to `clients` for assigned_to.
    """

    def __init__(self, db_pool: asyncpg.Pool | None) -> None:
        self.db_pool = db_pool

    @property
    def name(self) -> str:
        return "team_my_deadlines"

    @property
    def description(self) -> str:
        return (
            "List upcoming compliance deadlines (KITAS/visa/passport expiry, "
            "LKPM, SPT/tax filings, license renewals) for the CALLER'S OWN "
            "clients. Only usable by an authenticated Bali Zero team member. "
            "Use for 'my deadlines', 'le mie scadenze', 'jatuh tempo saya'."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": (
                        f"Look-ahead window in days (default {DEFAULT_DAYS_AHEAD}, "
                        f"max {MAX_DAYS_AHEAD})."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": f"Max deadlines to return (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        days_ahead: int = DEFAULT_DAYS_AHEAD,
        limit: int = DEFAULT_LIMIT,
        **kwargs: Any,
    ) -> str:
        scope = _scope_from_kwargs(kwargs)
        if scope is None:
            return _NOT_AVAILABLE
        if not scope.is_admin and not scope.email:
            return _IDENTITY_UNRESOLVED
        if self.db_pool is None:
            return json.dumps({"available": True, "deadlines": [], "error": "db_unavailable"})

        days_ahead = _clamp_days(days_ahead)
        limit = _clamp_limit(limit)

        expiry_sql = """
            SELECT client_name, document_type AS category, expiry_date AS deadline,
                   days_until_expiry AS days_until
            FROM client_expiry_alerts_view
            WHERE expiry_date IS NOT NULL
              AND expiry_date > CURRENT_DATE
              AND expiry_date <= CURRENT_DATE + ($1 || ' days')::interval
        """
        alerts_sql = """
            SELECT c.full_name AS client_name, ca.category, ca.deadline,
                   ca.days_until
            FROM compliance_alerts ca
            JOIN clients c ON c.id = ca.client_id
            WHERE ca.deadline IS NOT NULL
              AND ca.deadline > CURRENT_DATE
              AND ca.deadline <= CURRENT_DATE + ($1 || ' days')::interval
              AND ca.status <> 'resolved'
        """
        expiry_params: list[Any] = [days_ahead]
        alerts_params: list[Any] = [days_ahead]
        if not scope.is_admin:
            expiry_sql += f" AND LOWER(assigned_to) = ${len(expiry_params) + 1}"
            expiry_params.append(scope.email)
            alerts_sql += f" AND LOWER(c.assigned_to) = ${len(alerts_params) + 1}"
            alerts_params.append(scope.email)
        expiry_sql += f" ORDER BY expiry_date ASC LIMIT ${len(expiry_params) + 1}"
        expiry_params.append(limit)
        alerts_sql += f" ORDER BY ca.deadline ASC LIMIT ${len(alerts_params) + 1}"
        alerts_params.append(limit)

        async with self.db_pool.acquire() as conn:
            expiry_rows = await conn.fetch(expiry_sql, *expiry_params)
            alert_rows = await conn.fetch(alerts_sql, *alerts_params)

        deadlines = [
            {
                "client_name": r["client_name"],
                "category": r["category"],
                "deadline": r["deadline"].isoformat() if r["deadline"] else None,
                "days_until": r["days_until"],
            }
            for r in expiry_rows
        ] + [
            {
                "client_name": r["client_name"],
                "category": r["category"],
                "deadline": r["deadline"].isoformat() if r["deadline"] else None,
                "days_until": r["days_until"],
            }
            for r in alert_rows
        ]
        deadlines.sort(key=lambda d: d["days_until"] if d["days_until"] is not None else 10**9)
        deadlines = deadlines[:limit]

        logger.info(
            "team_crm_tools.my_deadlines",
            extra={"admin_scope": scope.is_admin, "result_count": len(deadlines)},
        )
        return json.dumps({"available": True, "deadlines": deadlines})


class TeamPracticeDetailTool(BaseTool):
    """V2a intent (d): practice detail by client name, fuzzy WITHIN scope only.

    Guilt/innocence invariant: the fuzzy ILIKE match is applied INSIDE the
    same query as the assigned_to filter — a team member can never widen
    their match by fuzzy-searching a colleague's client name; the row is
    simply absent from the result set (same shape as "not found").
    """

    def __init__(self, db_pool: asyncpg.Pool | None) -> None:
        self.db_pool = db_pool

    @property
    def name(self) -> str:
        return "team_practice_detail"

    @property
    def description(self) -> str:
        return (
            "Look up practice detail (status, type, dates, notes) for a "
            "client by (fuzzy) name — but ONLY within the caller's OWN "
            "assigned clients. Returns no results for a client not assigned "
            "to the caller, even if the name matches. Use for 'status of "
            "[client]', 'a che punto è [client]'."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "client_name": {
                    "type": "string",
                    "description": "Client name (or partial name) to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Max practices to return (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
                },
            },
            "required": ["client_name"],
        }

    async def execute(
        self,
        client_name: str,
        limit: int = DEFAULT_LIMIT,
        **kwargs: Any,
    ) -> str:
        scope = _scope_from_kwargs(kwargs)
        if scope is None:
            return _NOT_AVAILABLE
        if not scope.is_admin and not scope.email:
            return _IDENTITY_UNRESOLVED
        if not client_name or not client_name.strip():
            return json.dumps({"available": True, "practices": [], "error": "client_name_required"})
        if self.db_pool is None:
            return json.dumps({"available": True, "practices": [], "error": "db_unavailable"})

        limit = _clamp_limit(limit)
        pattern = f"%{client_name.strip()}%"
        sql = """
            SELECT p.id, p.status, p.expiry_date, p.notes, p.created_at, p.updated_at,
                   pt.name AS practice_type, c.full_name AS client_name
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE c.full_name ILIKE $1
        """
        params: list[Any] = [pattern]
        if not scope.is_admin:
            params.append(scope.email)
            sql += f" AND LOWER(c.assigned_to) = ${len(params)}"
        params.append(limit)
        sql += f" ORDER BY p.created_at DESC LIMIT ${len(params)}"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        logger.info(
            "team_crm_tools.practice_detail",
            extra={"admin_scope": scope.is_admin, "result_count": len(rows)},
        )
        return json.dumps(
            {
                "available": True,
                "practices": [
                    {
                        "practice_id": r["id"],
                        "client_name": r["client_name"],
                        "practice_type": r["practice_type"],
                        "status": r["status"],
                        "expiry_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
                        "notes": r["notes"],
                        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    }
                    for r in rows
                ],
            }
        )


def create_team_crm_tools(db_pool: asyncpg.Pool | None) -> list[BaseTool]:
    """Factory — the 4 V2a tools, bound to `db_pool`.

    Called from `create_agentic_rag()` ONLY when
    `is_team_crm_tools_enabled()` is true (flag read once, at
    orchestrator-construction time — see module docstring).
    """
    return [
        TeamMyClientsTool(db_pool),
        TeamMyPracticesTool(db_pool),
        TeamMyDeadlinesTool(db_pool),
        TeamPracticeDetailTool(db_pool),
    ]


TEAM_CRM_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "team_my_clients",
        "team_my_practices",
        "team_my_deadlines",
        "team_practice_detail",
    }
)
