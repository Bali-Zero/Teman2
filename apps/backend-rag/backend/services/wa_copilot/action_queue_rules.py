"""WA Copilot action_queue rules engine (S1.9 v1).

Builds operator-facing action items by scanning derived signals from S1.3
(identity), S1.4 (conversations), S1.5 (extractions), S1.7 (practice
candidates), S1.8 (team promises) and the practices/whatsapp tables.

Nine deterministic triggers, each producing rows in ``action_queue`` with a
sha256 ``dedup_key`` so re-runs are idempotent against the partial unique
index ``uix_action_queue_open_dedup`` (alive while status IN open/snoozed).

CLI:
    python -m backend.services.wa_copilot.action_queue_rules \\
      (--apply | --dry-run) \\
      [--rule R1,R2,...]   (default: all 9) \\
      [--limit N]          (per-rule cap on candidate rows)\\
      [--batch-size 200]   (DB executemany chunk size)\\
      [--metrics-json /tmp/action-queue.json]

Anti-pattern guards:
  - PgBouncer-safe asyncpg (statement_cache_size=0).
  - Idempotent: ON CONFLICT (dedup_key) DO NOTHING leverages the partial
    UNIQUE index already in mig 200.
  - Owner falls back to 'unassigned' when conversations.owner_team_member
    is NULL (rules can target rows without conversation join too — R3,
    R5, R6, R9 dispatch by client/practice).
  - sha256(dedup_key) generated in Python via stdlib hashlib — no DB-side
    digest dependency.

References:
  - Migration 200: action_queue table
  - S1.8 team_promises module (apps/backend-rag/backend/services/wa_copilot/team_promises.py)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

ENGINE_VERSION = "v1-2026-05-25"
BATCH_SIZE_DEFAULT = 200
DEFAULT_OWNER_FALLBACK = "unassigned"

ALL_RULES = [
    "R1",  # silence_72h_after_team_commitment
    "R2",  # client_question_unanswered_24h
    "R3",  # missing_doc_blocker_repeated
    "R4",  # payment_unresolved
    "R5",  # reentry_permit_repeated
    "R6",  # stale_practice_active_chat
    "R7",  # practice_link_review_pending
    "R8",  # identity_resolution_needs_review
    "R9",  # compliance_deadline_30d
]


# ---------------------------------------------------------------------------
# Data class for one candidate action row
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ActionCandidate:
    """One candidate action_queue row, pre-insert.

    ``evidence`` MUST be JSON-serialisable (dict[str, Any]); we serialise
    via ``json.dumps(default=str)`` so datetimes/decimals fall back to
    string representation.
    """

    action_type: str
    reason: str
    recommended_action: str
    dedup_key: str
    evidence: dict[str, Any]
    priority: int = 5
    owner: str | None = None
    due_at: _dt.datetime | None = None
    client_id: int | None = None
    practice_id: int | None = None
    conversation_id: int | None = None
    suggested_message_draft: str | None = None


@dataclass
class RuleMetrics:
    """Per-rule run metrics."""

    rule_id: str
    candidates_found: int = 0
    actions_created: int = 0
    actions_skipped_conflict: int = 0
    errors: int = 0
    wall_ms: int = 0


@dataclass
class EngineMetrics:
    """Aggregate engine metrics across all rules."""

    rules_executed: list[str] = field(default_factory=list)
    total_candidates: int = 0
    total_created: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    by_rule: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_action_type: dict[str, int] = field(default_factory=dict)
    wall_ms: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _owner_for(conv_owner: str | None) -> str:
    return conv_owner if conv_owner else DEFAULT_OWNER_FALLBACK


async def _insert_actions(
    pool: asyncpg.Pool,
    candidates: list[ActionCandidate],
    *,
    apply: bool,
    metrics: RuleMetrics,
    batch_size: int,
) -> None:
    """Persist (or count in dry-run) candidate actions in batches.

    Uses ``INSERT ... ON CONFLICT (dedup_key) DO NOTHING`` keyed on the
    partial unique index ``uix_action_queue_open_dedup``. The conflict
    target is the index, not a single column — Postgres lets us elide
    the predicate as long as it matches.
    """
    if not candidates:
        return
    if not apply:
        metrics.actions_created += len(candidates)
        return

    async with pool.acquire() as conn:
        for i in range(0, len(candidates), batch_size):
            chunk = candidates[i : i + batch_size]
            async with conn.transaction():
                for cand in chunk:
                    evidence_json = json.dumps(cand.evidence, default=str)
                    result = await conn.execute(
                        """
                        INSERT INTO action_queue (
                            client_id, practice_id, conversation_id,
                            action_type, reason, recommended_action,
                            suggested_message_draft, due_at, evidence,
                            owner, priority, dedup_key
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12)
                        ON CONFLICT (dedup_key)
                          WHERE status IN ('open', 'snoozed')
                          DO NOTHING
                        """,
                        cand.client_id,
                        cand.practice_id,
                        cand.conversation_id,
                        cand.action_type,
                        cand.reason,
                        cand.recommended_action,
                        cand.suggested_message_draft,
                        cand.due_at,
                        evidence_json,
                        cand.owner,
                        cand.priority,
                        cand.dedup_key,
                    )
                    if result.endswith(" 1"):
                        metrics.actions_created += 1
                    else:
                        metrics.actions_skipped_conflict += 1


# ---------------------------------------------------------------------------
# Rule R1 — silence 72h after team commitment
# ---------------------------------------------------------------------------


async def rule_R1(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """Unresolved team_promises past due_at by >=72h, made within 30d."""
    sql = """
        SELECT p.promise_id, p.message_id, p.conversation_id, p.client_id,
               p.promise_text, p.due_at, p.created_at,
               c.owner_team_member
        FROM team_promises p
        LEFT JOIN whatsapp_conversations c ON c.conversation_id = p.conversation_id
        WHERE p.resolved = false
          AND p.due_at IS NOT NULL
          AND p.due_at < NOW() - INTERVAL '72 hours'
          AND p.created_at > NOW() - INTERVAL '30 days'
        ORDER BY p.due_at
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"followup_team_commitment:{r['promise_id']}")
        snippet = (r["promise_text"] or "").strip()[:120]
        out.append(
            ActionCandidate(
                action_type="followup_team_commitment",
                reason=(
                    f"team promise made on {r['created_at'].date().isoformat()}, "
                    f"due {r['due_at'].date().isoformat()}, still unresolved"
                ),
                recommended_action=(
                    f"Send follow-up to client about: {snippet}"
                ),
                dedup_key=dedup,
                evidence={
                    "promise_id": int(r["promise_id"]),
                    "message_id": int(r["message_id"]),
                    "promise_text": snippet,
                    "due_at": r["due_at"].isoformat() if r["due_at"] else None,
                },
                priority=7,
                owner=_owner_for(r["owner_team_member"]),
                due_at=_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24),
                client_id=int(r["client_id"]) if r["client_id"] else None,
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R2 — client question unanswered 24h
# ---------------------------------------------------------------------------


async def rule_R2(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """Client questions (fact_type='client_question') with no team reply
    in 24h window on the same conversation."""
    sql = """
        SELECT e.extraction_id, e.message_id, e.conversation_id, e.client_id,
               e.fact_value, m.message_date,
               c.owner_team_member
        FROM whatsapp_extractions e
        JOIN whatsapp_message_context m ON m.id = e.message_id
        LEFT JOIN whatsapp_conversations c ON c.conversation_id = e.conversation_id
        WHERE e.fact_type = 'client_question'
          AND e.created_at > NOW() - INTERVAL '30 days'
          AND e.conversation_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM whatsapp_message_context m2
              WHERE m2.conversation_id = m.conversation_id
                AND m2.sender_role = 'team'
                AND m2.message_date > m.message_date
                AND m2.message_date <= m.message_date + INTERVAL '24 hours'
          )
        ORDER BY m.message_date DESC
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"answer_question:{r['extraction_id']}")
        question_value = ""
        if r["fact_value"]:
            try:
                parsed = (
                    r["fact_value"]
                    if isinstance(r["fact_value"], dict)
                    else json.loads(r["fact_value"])
                )
                question_value = str(parsed.get("value", ""))[:200]
            except (TypeError, ValueError, json.JSONDecodeError):
                question_value = str(r["fact_value"])[:200]
        out.append(
            ActionCandidate(
                action_type="answer_client_question",
                reason="Client asked a question, no team reply within 24h",
                recommended_action=(
                    f"Answer client question: {question_value}"
                    if question_value
                    else "Answer client question (see source message)"
                ),
                dedup_key=dedup,
                evidence={
                    "extraction_id": int(r["extraction_id"]),
                    "message_id": int(r["message_id"]),
                    "question": question_value,
                    "asked_at": r["message_date"].isoformat() if r["message_date"] else None,
                },
                priority=8,
                owner=_owner_for(r["owner_team_member"]),
                client_id=int(r["client_id"]) if r["client_id"] else None,
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R3 — missing-doc blocker repeated
# ---------------------------------------------------------------------------


async def rule_R3(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """Blockers prefixed 'missing_' mentioned 2+ times for the same
    client_id (any window)."""
    sql = """
        SELECT e.client_id, e.fact_value->>'value' AS blocker_value,
               COUNT(*) AS mentions,
               array_agg(e.extraction_id ORDER BY e.created_at) AS extraction_ids,
               MAX(e.conversation_id) AS conversation_id
        FROM whatsapp_extractions e
        WHERE e.fact_type = 'blocker'
          AND e.fact_value->>'value' LIKE 'missing_%'
          AND e.client_id IS NOT NULL
        GROUP BY e.client_id, e.fact_value->>'value'
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"blocker:{r['client_id']}:{r['blocker_value']}")
        out.append(
            ActionCandidate(
                action_type="resolve_blocker",
                reason=(
                    f"Blocker '{r['blocker_value']}' mentioned {r['mentions']} "
                    f"times for this client"
                ),
                recommended_action=f"Address blocker: {r['blocker_value']}",
                dedup_key=dedup,
                evidence={
                    "client_id": int(r["client_id"]),
                    "blocker_value": r["blocker_value"],
                    "mentions": int(r["mentions"]),
                    "extraction_ids": [int(x) for x in r["extraction_ids"]],
                },
                priority=9,
                owner=DEFAULT_OWNER_FALLBACK,  # No conversation join — owner unknown
                client_id=int(r["client_id"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R4 — payment unresolved
# ---------------------------------------------------------------------------


_PAYMENT_KEYWORD_RE = re.compile(
    r"belum bayar|invoice|transfer|pending|outstanding", re.IGNORECASE
)
_PAID_KEYWORD_RE = re.compile(
    r"\bpaid\b|\blunas\b|\breceived\b|\bpagato\b", re.IGNORECASE
)


async def rule_R4(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """``fact_type='biaya'`` extractions where the source message contains
    payment keywords AND no follow-up message in the same conversation
    contains a 'paid' keyword.

    Uses Python regex post-filter for the 'paid' check to avoid Postgres
    LIKE word-boundary gymnastics.
    """
    sql = """
        SELECT e.extraction_id, e.message_id, e.conversation_id, e.client_id,
               e.fact_value, m.message_date,
               COALESCE(m.body, m.message_text) AS body,
               c.owner_team_member
        FROM whatsapp_extractions e
        JOIN whatsapp_message_context m ON m.id = e.message_id
        LEFT JOIN whatsapp_conversations c ON c.conversation_id = e.conversation_id
        WHERE e.fact_type = 'biaya'
          AND e.created_at > NOW() - INTERVAL '14 days'
          AND COALESCE(m.body, m.message_text) ~* 'belum bayar|invoice|transfer|pending|outstanding'
        ORDER BY m.message_date DESC
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
        out: list[ActionCandidate] = []
        for r in rows:
            # Python-side paid-keyword exclusion (only when conversation_id
            # available; if NULL we can't scope the follow-up search, so we
            # always treat it as unpaid).
            if r["conversation_id"] is not None:
                paid_rows = await conn.fetch(
                    """
                    SELECT COALESCE(body, message_text) AS body
                    FROM whatsapp_message_context
                    WHERE conversation_id = $1
                      AND message_date > $2
                      AND COALESCE(body, message_text) IS NOT NULL
                    LIMIT 50
                    """,
                    r["conversation_id"],
                    r["message_date"],
                )
                if any(_PAID_KEYWORD_RE.search(pr["body"] or "") for pr in paid_rows):
                    continue
            dedup = _sha256(f"payment:{r['message_id']}")
            amount = ""
            if r["fact_value"]:
                try:
                    parsed = (
                        r["fact_value"]
                        if isinstance(r["fact_value"], dict)
                        else json.loads(r["fact_value"])
                    )
                    amount = str(parsed.get("value", ""))[:80]
                except (TypeError, ValueError, json.JSONDecodeError):
                    amount = str(r["fact_value"])[:80]
            out.append(
                ActionCandidate(
                    action_type="followup_payment",
                    reason="Payment mentioned but no 'paid/lunas' confirmation found",
                    recommended_action=(
                        f"Follow up on payment{(': ' + amount) if amount else ''}"
                    ),
                    dedup_key=dedup,
                    evidence={
                        "extraction_id": int(r["extraction_id"]),
                        "message_id": int(r["message_id"]),
                        "amount": amount,
                        "asked_at": r["message_date"].isoformat()
                        if r["message_date"]
                        else None,
                    },
                    priority=8,
                    owner=_owner_for(r["owner_team_member"]),
                    client_id=int(r["client_id"]) if r["client_id"] else None,
                    conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Rule R5 — reentry-permit repeated question
# ---------------------------------------------------------------------------


async def rule_R5(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """``fact_value->>'value' = 'reentry_permit_question'`` mentioned 2+
    times in last 30 days for the same client."""
    sql = """
        SELECT e.client_id, COUNT(*) AS mentions,
               array_agg(e.extraction_id ORDER BY e.created_at) AS extraction_ids,
               MAX(e.conversation_id) AS conversation_id
        FROM whatsapp_extractions e
        WHERE e.fact_value->>'value' = 'reentry_permit_question'
          AND e.created_at > NOW() - INTERVAL '30 days'
          AND e.client_id IS NOT NULL
        GROUP BY e.client_id
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"reentry:{r['client_id']}")
        out.append(
            ActionCandidate(
                action_type="answer_reentry_permit",
                reason=(
                    f"Client asked about re-entry permit {r['mentions']} "
                    f"times in last 30 days"
                ),
                recommended_action="Provide re-entry permit guidance to client",
                dedup_key=dedup,
                evidence={
                    "client_id": int(r["client_id"]),
                    "mentions": int(r["mentions"]),
                    "extraction_ids": [int(x) for x in r["extraction_ids"]],
                },
                priority=7,
                owner=DEFAULT_OWNER_FALLBACK,
                client_id=int(r["client_id"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R6 — stale practice with active chat
# ---------------------------------------------------------------------------


async def rule_R6(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """Practices in `on_process`/`waiting_documents` >=7d old, with a
    customer message in the past 14d but NO team reply in the past 7d."""
    sql = """
        SELECT p.id AS practice_id, p.status, p.created_at AS practice_created_at,
               p.title, p.client_id,
               c.conversation_id, c.owner_team_member
        FROM practices p
        JOIN whatsapp_conversations c ON c.client_id = p.client_id
        WHERE p.status IN ('on_process', 'waiting_documents')
          AND p.created_at < NOW() - INTERVAL '7 days'
          AND c.last_customer_at > NOW() - INTERVAL '14 days'
          AND NOT EXISTS (
              SELECT 1 FROM whatsapp_message_context m
              WHERE m.conversation_id = c.conversation_id
                AND m.sender_role = 'team'
                AND m.message_date > NOW() - INTERVAL '7 days'
          )
        ORDER BY p.created_at
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"stale_practice:{r['practice_id']}")
        title = (r["title"] or "untitled").strip()[:100]
        out.append(
            ActionCandidate(
                action_type="update_stale_practice",
                reason=(
                    f"Practice in '{r['status']}' since "
                    f"{r['practice_created_at'].date().isoformat()}, "
                    f"client active but no team reply in 7d"
                ),
                recommended_action=f"Update client on practice status: {title}",
                dedup_key=dedup,
                evidence={
                    "practice_id": int(r["practice_id"]),
                    "status": r["status"],
                    "title": title,
                    "practice_created_at": r["practice_created_at"].isoformat()
                    if r["practice_created_at"]
                    else None,
                },
                priority=6,
                owner=_owner_for(r["owner_team_member"]),
                client_id=int(r["client_id"]) if r["client_id"] else None,
                practice_id=int(r["practice_id"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R7 — practice-link review pending >=7d
# ---------------------------------------------------------------------------


async def rule_R7(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """``whatsapp_practice_candidates`` rows still ``pending_review`` and
    >=7d old."""
    sql = """
        SELECT pc.candidate_id, pc.conversation_id, pc.message_id,
               pc.practice_id, pc.confidence, pc.created_at,
               c.owner_team_member, c.client_id
        FROM whatsapp_practice_candidates pc
        LEFT JOIN whatsapp_conversations c
               ON c.conversation_id = pc.conversation_id
        WHERE pc.status = 'pending_review'
          AND pc.created_at < NOW() - INTERVAL '7 days'
        ORDER BY pc.created_at
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"review_practice_link:{r['candidate_id']}")
        out.append(
            ActionCandidate(
                action_type="review_practice_link",
                reason=(
                    f"Practice-link candidate pending review since "
                    f"{r['created_at'].date().isoformat()} "
                    f"(confidence={r['confidence']})"
                ),
                recommended_action=(
                    "Review proposed practice→conversation linkage and "
                    "approve or dismiss"
                ),
                dedup_key=dedup,
                evidence={
                    "candidate_id": int(r["candidate_id"]),
                    "practice_id": int(r["practice_id"]),
                    "confidence": float(r["confidence"]),
                },
                priority=4,
                owner=_owner_for(r["owner_team_member"]),
                client_id=int(r["client_id"]) if r["client_id"] else None,
                practice_id=int(r["practice_id"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R8 — identity resolution needs_review
# ---------------------------------------------------------------------------


async def rule_R8(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """``whatsapp_identity_audit`` rows with ``decision='needs_review'``
    in last 14d. One action per message_id (first audit_id wins). Capped
    at 100 by spec default."""
    cap = limit if limit is not None else 100
    sql = """
        SELECT DISTINCT ON (a.message_id)
               a.id AS audit_id, a.message_id, a.attempted_method,
               a.signal_payload, a.created_at,
               m.conversation_id,
               c.owner_team_member
        FROM whatsapp_identity_audit a
        JOIN whatsapp_message_context m ON m.id = a.message_id
        LEFT JOIN whatsapp_conversations c ON c.conversation_id = m.conversation_id
        WHERE a.decision = 'needs_review'
          AND a.created_at > NOW() - INTERVAL '14 days'
        ORDER BY a.message_id, a.id
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, cap)
    out: list[ActionCandidate] = []
    for r in rows:
        dedup = _sha256(f"review_identity:{r['audit_id']}")
        out.append(
            ActionCandidate(
                action_type="review_identity",
                reason=(
                    f"Identity resolver flagged message for manual review "
                    f"(method={r['attempted_method']})"
                ),
                recommended_action=(
                    "Manually match WhatsApp sender to client record"
                ),
                dedup_key=dedup,
                evidence={
                    "audit_id": int(r["audit_id"]),
                    "message_id": int(r["message_id"]),
                    "attempted_method": r["attempted_method"],
                },
                priority=3,
                owner=_owner_for(r["owner_team_member"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule R9 — compliance deadline approaching (30d)
# ---------------------------------------------------------------------------


async def rule_R9(
    pool: asyncpg.Pool, *, limit: int | None
) -> list[ActionCandidate]:
    """Practices with ``completion_date`` in [NOW, NOW+30d] and not
    completed/cancelled."""
    sql = """
        SELECT p.id AS practice_id, p.title, p.status, p.client_id,
               p.completion_date,
               c.conversation_id, c.owner_team_member
        FROM practices p
        LEFT JOIN whatsapp_conversations c ON c.client_id = p.client_id
        WHERE p.completion_date BETWEEN NOW() AND NOW() + INTERVAL '30 days'
          AND p.status NOT IN ('completed', 'cancelled')
        ORDER BY p.completion_date
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit if limit is not None else 100000)
    out: list[ActionCandidate] = []
    for r in rows:
        # iso_week-based dedup so we don't re-create the same action
        # twice in the same week if completion_date jitters.
        iso_year, iso_week, _ = r["completion_date"].isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        dedup = _sha256(f"compliance:{r['practice_id']}:{week_key}")
        title = (r["title"] or "untitled").strip()[:100]
        out.append(
            ActionCandidate(
                action_type="compliance_deadline_approaching",
                reason=(
                    f"Practice '{title}' has completion_date "
                    f"{r['completion_date'].date().isoformat()} (<30d)"
                ),
                recommended_action=(
                    f"Prepare compliance deliverable for: {title}"
                ),
                dedup_key=dedup,
                evidence={
                    "practice_id": int(r["practice_id"]),
                    "title": title,
                    "status": r["status"],
                    "completion_date": r["completion_date"].isoformat(),
                    "iso_week": week_key,
                },
                priority=8,
                owner=_owner_for(r["owner_team_member"]),
                client_id=int(r["client_id"]) if r["client_id"] else None,
                practice_id=int(r["practice_id"]),
                conversation_id=int(r["conversation_id"]) if r["conversation_id"] else None,
                due_at=r["completion_date"],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


RuleFn = Callable[..., Awaitable[list[ActionCandidate]]]

RULES: dict[str, RuleFn] = {
    "R1": rule_R1,
    "R2": rule_R2,
    "R3": rule_R3,
    "R4": rule_R4,
    "R5": rule_R5,
    "R6": rule_R6,
    "R7": rule_R7,
    "R8": rule_R8,
    "R9": rule_R9,
}


async def run_engine(
    pool: asyncpg.Pool,
    *,
    rule_ids: list[str],
    apply: bool,
    limit: int | None,
    batch_size: int,
) -> EngineMetrics:
    """Run the requested rules sequentially and persist (or count) results."""
    t0 = time.monotonic()
    engine_metrics = EngineMetrics(rules_executed=rule_ids[:])

    for rule_id in rule_ids:
        fn = RULES.get(rule_id)
        if fn is None:
            logger.warning("Unknown rule id: %s — skipping", rule_id)
            continue
        rule_metrics = RuleMetrics(rule_id=rule_id)
        t_rule = time.monotonic()
        try:
            candidates = await fn(pool, limit=limit)
            rule_metrics.candidates_found = len(candidates)
            await _insert_actions(
                pool,
                candidates,
                apply=apply,
                metrics=rule_metrics,
                batch_size=batch_size,
            )
            for c in candidates:
                engine_metrics.by_action_type[c.action_type] = (
                    engine_metrics.by_action_type.get(c.action_type, 0) + 1
                )
        except Exception:
            logger.exception("rule %s failed", rule_id)
            rule_metrics.errors += 1
        rule_metrics.wall_ms = int((time.monotonic() - t_rule) * 1000)
        engine_metrics.by_rule[rule_id] = asdict(rule_metrics)
        engine_metrics.total_candidates += rule_metrics.candidates_found
        engine_metrics.total_created += rule_metrics.actions_created
        engine_metrics.total_skipped += rule_metrics.actions_skipped_conflict
        engine_metrics.total_errors += rule_metrics.errors
        logger.info(
            "rule %s done: candidates=%d created=%d skipped=%d errors=%d wall=%dms",
            rule_id,
            rule_metrics.candidates_found,
            rule_metrics.actions_created,
            rule_metrics.actions_skipped_conflict,
            rule_metrics.errors,
            rule_metrics.wall_ms,
        )

    engine_metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return engine_metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432
    (matches the team_promises pattern)."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


def _parse_rule_list(s: str | None) -> list[str]:
    if not s:
        return ALL_RULES[:]
    parts = [p.strip().upper() for p in s.split(",") if p.strip()]
    unknown = [p for p in parts if p not in RULES]
    if unknown:
        raise SystemExit(f"Unknown rule ids: {unknown}; valid: {ALL_RULES}")
    return parts


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="action_queue_rules")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist writes")
    g.add_argument("--dry-run", action="store_true", help="Compute only, no DB writes")
    parser.add_argument(
        "--rule",
        default=None,
        help=f"Comma-separated rule ids (default: all {len(ALL_RULES)})",
    )
    parser.add_argument("--limit", type=int, default=None, help="Per-rule candidate cap")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--metrics-json", default=None)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    rule_ids = _parse_rule_list(args.rule)
    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=5,
        statement_cache_size=0,
        command_timeout=120,
    )
    try:
        em = await run_engine(
            pool,
            rule_ids=rule_ids,
            apply=args.apply,
            limit=args.limit,
            batch_size=args.batch_size,
        )
        combined: dict[str, Any] = {
            "version": ENGINE_VERSION,
            "apply": args.apply,
            "rule_ids": rule_ids,
            "limit": args.limit,
            "batch_size": args.batch_size,
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "engine": asdict(em),
        }
        logger.info(
            "ENGINE done: total_candidates=%d total_created=%d total_skipped=%d "
            "errors=%d wall=%dms",
            em.total_candidates,
            em.total_created,
            em.total_skipped,
            em.total_errors,
            em.wall_ms,
        )
        if args.metrics_json:
            with open(args.metrics_json, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, default=str)
            logger.info("metrics written to %s", args.metrics_json)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
