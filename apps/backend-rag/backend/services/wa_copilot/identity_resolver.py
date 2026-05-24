"""WA Copilot identity resolver v1.

Cascade ordered by precision/cost:
  1. phone_e164   — normalize phone_number/counterpart_lid → clients.phone_normalized   (conf 0.95)
  2. lid_map      — JOIN whatsapp_lid_phone_map (Baileys) → phone → clients              (conf 0.90)
  3. team_email   — team_member_email → team_members.email                               (conf 1.00)
  4. drive_folder — parse whatsapp_export_batches.source_label → fuzzy clients.full_name (conf 0.70+)
  5. sender_name  — pg_trgm similarity sender_name vs clients.full_name                  (conf 0.40+)

Writes: whatsapp_message_context (client_id, identity_method, identity_confidence,
team_member_id, sender_role) + whatsapp_identity_audit (full trail).

Idempotent: skips messages where resolver_version >= current AND confidence >= apply threshold,
unless --force.

Performance: bulk SELECT 5k → cascade in Python → bulk UPDATE + bulk audit INSERT per batch.
Target wall: ~3-5min for 75k rows on Pro M4.
"""

from __future__ import annotations

import argparse
import asyncio
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

# Reuse existing helper from CRM
from backend.services.crm.client_core import normalize_phone_e164

logger = logging.getLogger(__name__)

RESOLVER_VERSION = "v1.1-2026-05-25"
MIN_APPLY_CONFIDENCE = 0.70
REVIEW_BAND_LOW = 0.40
REVIEW_BAND_HIGH = 0.70
BATCH_SIZE_DEFAULT = 5000
SENDER_NAME_AMBIGUITY_MARGIN = 0.15  # top1-top2 must differ by ≥0.15

# Confidence per method (on exact match)
CONF_PHONE_E164 = 0.95
CONF_PHONE_E164_PARTIAL = 0.85  # last-9-digit match
CONF_LID_MAP = 0.90
CONF_TEAM_EMAIL = 1.00
CONF_TEAM_NAME = 0.85  # sender_push_name fuzzy → team_members.full_name
CONF_DRIVE_FOLDER_THRESHOLD = 0.70
SENDER_NAME_APPLY_THRESHOLD = 0.70  # sim >= this → apply, else needs_review band


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ResolveResult:
    """Single signal resolution outcome."""

    method: str
    client_id: int | None
    confidence: float
    team_member_id: str | None = None  # VARCHAR(36) post-mig201
    sender_role: str | None = None  # 'team' | 'client' | None
    signal_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolverMetrics:
    """Aggregate run metrics."""

    total_scanned: int = 0
    already_resolved_skipped: int = 0
    by_method: dict[str, int] = field(default_factory=dict)
    needs_review_band: int = 0
    unresolved: int = 0
    errors: int = 0
    wall_ms: int = 0
    baseline_pct: float = 0.0
    post_run_pct: float = 0.0
    delta_pp: float = 0.0

    def bump(self, method: str) -> None:
        self.by_method[method] = self.by_method.get(method, 0) + 1


# ---------------------------------------------------------------------------
# Signal resolvers (cascade)
# ---------------------------------------------------------------------------

async def resolve_phone_e164(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #1: normalize phone → JOIN clients.phone_normalized."""
    raw_phone = msg.get("phone_number") or msg.get("counterpart_lid")
    if not raw_phone:
        return None

    e164 = normalize_phone_e164(str(raw_phone))
    if not e164:
        return None

    # Exact match (preferred): phone_normalized includes leading + or not
    candidate = e164.lstrip("+")
    row = await conn.fetchrow(
        """
        SELECT id, full_name FROM clients
        WHERE phone_normalized IN ($1, $2)
        LIMIT 1
        """,
        candidate,
        e164,
    )
    if row:
        return ResolveResult(
            method="phone_e164",
            client_id=row["id"],
            confidence=CONF_PHONE_E164,
            sender_role="client",
            signal_payload={"e164": e164, "match": "exact"},
        )

    # Partial: last 9 digits (handles country code variants)
    if len(candidate) >= 9:
        tail = candidate[-9:]
        row = await conn.fetchrow(
            """
            SELECT id FROM clients
            WHERE phone_normalized LIKE '%' || $1
            LIMIT 1
            """,
            tail,
        )
        if row:
            return ResolveResult(
                method="phone_e164",
                client_id=row["id"],
                confidence=CONF_PHONE_E164_PARTIAL,
                sender_role="client",
                signal_payload={"e164": e164, "match": "tail9"},
            )

    return None


async def resolve_lid_map(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #2: counterpart_lid → whatsapp_lid_phone_map.jid_phone → clients."""
    lid = msg.get("counterpart_lid")
    if not lid:
        return None

    row = await conn.fetchrow(
        """
        SELECT c.id, m.jid_phone
        FROM whatsapp_lid_phone_map m
        LEFT JOIN clients c ON c.phone_normalized = m.jid_phone
                            OR c.phone_normalized = REGEXP_REPLACE(m.jid_phone, '^\\+', '')
        WHERE m.lid = $1 AND m.jid_phone IS NOT NULL
        LIMIT 1
        """,
        str(lid),
    )
    if row and row["id"]:
        return ResolveResult(
            method="lid_map",
            client_id=row["id"],
            confidence=CONF_LID_MAP,
            sender_role="client",
            signal_payload={"lid": str(lid), "jid_phone": row["jid_phone"]},
        )

    return None


async def resolve_team_email(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #3: team_member_email → team_members.email → sender_role='team'."""
    email = msg.get("team_member_email")
    if not email:
        return None

    row = await conn.fetchrow(
        """
        SELECT id::TEXT AS tm_id FROM team_members
        WHERE LOWER(email) = LOWER($1) AND active = true
        LIMIT 1
        """,
        str(email),
    )
    if row:
        return ResolveResult(
            method="team_email",
            client_id=None,  # team msg, not client-side
            confidence=CONF_TEAM_EMAIL,
            team_member_id=row["tm_id"],
            sender_role="team",
            signal_payload={"email": str(email)},
        )

    return None


# Label format A (legacy, ~3 batches):  "WhatsApp Chat - <name>"
# Label format B (slug w/ marker, ~189): "[<prefix>-]?whatsapp-chat-<name>-2026-MM-DD-<suffix>"
#                                         <prefix>=operator slug or date prefix (22-mei-2026)
#                                         <suffix> ∈ {pilot, mass}
# Label format C (slug no marker, ~2):    "<operator>-<name>-2026-MM-DD-<suffix>"
_CHAT_TITLE_RE = re.compile(r"^WhatsApp Chat - (.+?)$", re.IGNORECASE)
# Format B regex — prefer "whatsapp-chat-" marker as anchor when present (greedy
# left-anchor → capture everything between marker and trailing date)
_SLUG_W_MARKER_RE = re.compile(
    r"^.*?whatsapp-chat-"
    r"(?P<name>.+?)"
    r"-2\d{3}-\d{1,2}(?:-\d{1,2})?(?:-[a-z0-9]+)?$",
    re.IGNORECASE,
)
# Format C regex — fallback when no marker present (op-name-date-suffix)
_SLUG_NO_MARKER_RE = re.compile(
    r"^(?:[a-z0-9]+-)?"
    r"(?P<name>.+?)"
    r"-2\d{3}-\d{1,2}(?:-\d{1,2})?(?:-[a-z0-9]+)?$",
    re.IGNORECASE,
)
# Operator slugs to strip from start: known team-member first names (best-effort)
_OPERATOR_PREFIXES = (
    "ari", "krisna", "sahira", "amanda", "antonello", "adit", "aditya",
    "vero", "surya", "suryadi", "asya", "vino", "damar", "zainal",
    "michele", "subhi", "ruslana", "anton",
)


def _parse_label_name(source_label: str) -> str | None:
    """Extract candidate client name from any of the 3 label formats.

    Returns the human-readable name (spaces, original casing where possible) or None.
    """
    label = source_label.strip()
    if not label:
        return None

    # Format A: legacy "WhatsApp Chat - <name>"
    m = _CHAT_TITLE_RE.match(label)
    if m:
        return m.group(1).strip()

    # Format B: slug with "whatsapp-chat-" marker (preferred — unambiguous)
    name_slug: str | None = None
    m = _SLUG_W_MARKER_RE.match(label)
    if m:
        name_slug = m.group("name").strip("-")
    else:
        # Format C: slug without marker (operator-name-date)
        m = _SLUG_NO_MARKER_RE.match(label)
        if m:
            name_slug = m.group("name").strip("-")

    if not name_slug:
        return None

    parts = name_slug.split("-")
    # For Format C only: strip leading operator prefix if present
    # (Format B already strips operator via the .*? prefix in regex)
    if not m or "whatsapp-chat" not in label.lower():
        if len(parts) > 1 and parts[0].lower() in _OPERATOR_PREFIXES:
            parts = parts[1:]
    # Defensive: strip stray duplicate-batch markers / numeric tail tokens
    while parts and (parts[-1].isdigit() or parts[-1].lower() in ("new", "old")):
        parts = parts[:-1]
    if not parts:
        return None

    # slug-to-name: replace hyphens with spaces; preserve trgm fuzzy alignment
    name = " ".join(parts)
    if len(name) < 3:
        return None
    return name


async def resolve_drive_folder(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #4: ingest_batch_id → source_label → parse name → trgm fuzzy clients.full_name."""
    batch_id = msg.get("ingest_batch_id")
    if not batch_id:
        return None

    source_label = msg.get("_batch_source_label")  # pre-joined in batch SELECT
    if not source_label:
        return None

    candidate_name = _parse_label_name(source_label)
    if not candidate_name or len(candidate_name) < 3:
        return None

    # Trigram similarity — only top 1 with margin guard via top 2 (per-batch cached)
    cache = msg.get("_cache_drive_folder")
    cache_key = candidate_name
    if cache is not None and cache_key in cache:
        rows = cache[cache_key]
    else:
        rows = await conn.fetch(
            """
            SELECT id, full_name, similarity(full_name, $1) AS sim
            FROM clients
            WHERE full_name % $1
            ORDER BY sim DESC
            LIMIT 2
            """,
            candidate_name,
        )
        if cache is not None:
            cache[cache_key] = rows
    if not rows:
        return None

    top = rows[0]
    sim_top = float(top["sim"])
    if sim_top < CONF_DRIVE_FOLDER_THRESHOLD:
        # Still surface as needs_review if in band
        if REVIEW_BAND_LOW <= sim_top < REVIEW_BAND_HIGH:
            return ResolveResult(
                method="drive_folder",
                client_id=top["id"],  # candidate, NOT applied
                confidence=sim_top,
                sender_role="client",
                signal_payload={
                    "candidate_name": candidate_name,
                    "matched_name": top["full_name"],
                    "review_band": True,
                },
            )
        return None

    # Ambiguity check
    if len(rows) > 1:
        sim_second = float(rows[1]["sim"])
        if sim_top - sim_second < SENDER_NAME_AMBIGUITY_MARGIN:
            return ResolveResult(
                method="drive_folder",
                client_id=None,  # ambiguous, not applied
                confidence=sim_top,
                sender_role="client",
                signal_payload={
                    "candidate_name": candidate_name,
                    "top_name": top["full_name"],
                    "top_sim": sim_top,
                    "second_sim": sim_second,
                    "ambiguous": True,
                },
            )

    return ResolveResult(
        method="drive_folder",
        client_id=top["id"],
        confidence=sim_top,
        sender_role="client",
        signal_payload={
            "candidate_name": candidate_name,
            "matched_name": top["full_name"],
            "trgm_sim": sim_top,
        },
    )


# Team markers to strip from sender_push_name before trgm match
_TEAM_NAME_NORMALIZER_RE = re.compile(
    r"\s*[\(~\-]?\s*"
    r"(?:bz|bali\s*zero|"
    r"visa\s*&\s*immigration\s*service|"
    r"kitas\s*freelance"
    r")"
    r"\s*\)?\s*",
    re.IGNORECASE,
)


def _normalize_sender_for_team_match(sender: str) -> str:
    """Strip BZ / Bali Zero / role markers to leave the bare name for trgm match."""
    cleaned = _TEAM_NAME_NORMALIZER_RE.sub(" ", sender)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ~-()")
    return cleaned


async def resolve_team_name(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #3b: sender_push_name → fuzzy team_members.full_name.

    Catches "Sahira BZ" / "Ari Bali Zero" / "Krisna - BZ" style push names that
    don't have team_member_email populated. Strips BZ/Bali Zero markers first
    to maximise trigram alignment with bare team member full_names.

    Caches lookup result per normalized name in msg["_cache_team_name"] (set by
    process_message) to avoid re-querying for repeated senders within the same batch.
    """
    sender = msg.get("sender_name") or msg.get("sender")
    if not sender or len(str(sender)) < 3:
        return None

    normalized = _normalize_sender_for_team_match(str(sender))
    if not normalized or len(normalized) < 3:
        return None

    cache = msg.get("_cache_team_name")
    if cache is not None and normalized in cache:
        rows = cache[normalized]
    else:
        rows = await conn.fetch(
            """
            SELECT id::TEXT AS tm_id, full_name, similarity(full_name, $1) AS sim
            FROM team_members
            WHERE active = true
              AND full_name IS NOT NULL
              AND full_name % $1
            ORDER BY sim DESC
            LIMIT 2
            """,
            normalized,
        )
        if cache is not None:
            cache[normalized] = rows
    if not rows:
        return None

    top = rows[0]
    sim_top = float(top["sim"])

    # Strong-match threshold (>= 0.5) → apply as team
    if sim_top >= 0.5:
        # Ambiguity guard if second candidate is close
        if len(rows) > 1:
            sim_second = float(rows[1]["sim"])
            if sim_top - sim_second < SENDER_NAME_AMBIGUITY_MARGIN:
                return ResolveResult(
                    method="team_name",
                    client_id=None,
                    confidence=sim_top,
                    sender_role="team",
                    signal_payload={
                        "sender": str(sender),
                        "normalized": normalized,
                        "top_name": top["full_name"],
                        "top_sim": sim_top,
                        "second_sim": sim_second,
                        "ambiguous": True,
                    },
                )
        return ResolveResult(
            method="team_name",
            client_id=None,
            confidence=CONF_TEAM_NAME if sim_top >= 0.7 else sim_top,
            team_member_id=top["tm_id"],
            sender_role="team",
            signal_payload={
                "sender": str(sender),
                "normalized": normalized,
                "matched_name": top["full_name"],
                "trgm_sim": sim_top,
            },
        )
    return None


async def resolve_sender_name(
    conn: asyncpg.Connection, msg: dict[str, Any]
) -> ResolveResult | None:
    """Signal #5 (last resort): sender_name pg_trgm fuzzy match against clients (per-batch cached)."""
    sender = msg.get("sender_name") or msg.get("sender")
    if not sender or len(str(sender)) < 3:
        return None

    sender_str = str(sender)
    cache = msg.get("_cache_sender_name")
    if cache is not None and sender_str in cache:
        rows = cache[sender_str]
    else:
        rows = await conn.fetch(
            """
            SELECT id, full_name, similarity(full_name, $1) AS sim
            FROM clients
            WHERE full_name % $1
            ORDER BY sim DESC
            LIMIT 2
            """,
            sender_str,
        )
        if cache is not None:
            cache[sender_str] = rows
    if not rows:
        return None

    top = rows[0]
    sim_top = float(top["sim"])
    if sim_top < REVIEW_BAND_LOW:
        return None

    # Ambiguity check — if top and second are within margin, do NOT apply
    ambiguous = False
    sim_second = 0.0
    if len(rows) > 1:
        sim_second = float(rows[1]["sim"])
        if sim_top - sim_second < SENDER_NAME_AMBIGUITY_MARGIN:
            ambiguous = True

    if ambiguous:
        return ResolveResult(
            method="sender_name",
            client_id=None,
            confidence=sim_top,
            sender_role="client",
            signal_payload={
                "sender": str(sender),
                "top_name": top["full_name"],
                "top_sim": sim_top,
                "second_sim": sim_second,
                "ambiguous": True,
            },
        )

    # FIX (v1.1): trust pg_trgm sim DIRECTLY (no artificial 0.65 cap).
    # Previous v1.0 capped at 0.65 then required >= 0.70 to apply, which
    # mathematically made it impossible to apply via sender_name. Exact and
    # near-exact matches (sim >= 0.70) deserve to be applied.
    apply_client_id: int | None = None
    if sim_top >= SENDER_NAME_APPLY_THRESHOLD:
        apply_client_id = top["id"]

    return ResolveResult(
        method="sender_name",
        client_id=apply_client_id,
        confidence=sim_top,
        sender_role="client",
        signal_payload={
            "sender": str(sender),
            "matched_name": top["full_name"],
            "trgm_sim": sim_top,
        },
    )


CASCADE: tuple[Callable[[asyncpg.Connection, dict[str, Any]], Awaitable[ResolveResult | None]], ...] = (
    resolve_phone_e164,
    resolve_lid_map,
    resolve_team_email,
    resolve_team_name,       # v1.1: NEW — sender_push_name → team_members fuzzy
    resolve_drive_folder,
    resolve_sender_name,
)


# ---------------------------------------------------------------------------
# Batch orchestration
# ---------------------------------------------------------------------------

SELECT_BATCH_SQL = """
    SELECT
        m.id,
        COALESCE(m.phone_number, m.sender_phone) AS phone_number,
        COALESCE(m.counterpart_lid, m.sender_lid) AS counterpart_lid,
        m.team_member_email,
        m.sender_push_name_snapshot AS sender_name,
        m.ingest_batch_id,
        m.identity_method,
        m.identity_confidence,
        b.source_label AS _batch_source_label
    FROM whatsapp_message_context m
    LEFT JOIN whatsapp_export_batches b ON b.id = m.ingest_batch_id
    WHERE (
        m.identity_method IS NULL
        OR m.identity_confidence < $1
        OR $4 = true
    )
    AND ($2::timestamptz IS NULL OR COALESCE(m.message_date, m.created_at) >= $2)
    AND ($3::timestamptz IS NULL OR COALESCE(m.message_date, m.created_at) <= $3)
    ORDER BY m.id
    LIMIT $5
    OFFSET $6
"""

UPDATE_MSG_SQL = """
    UPDATE whatsapp_message_context
    SET
        client_id = COALESCE($2::int, client_id),
        identity_method = $3,
        identity_confidence = $4,
        team_member_id = COALESCE($5, team_member_id),
        sender_role = COALESCE($6, sender_role)
    WHERE id = $1
"""

INSERT_AUDIT_SQL = """
    INSERT INTO whatsapp_identity_audit
        (message_id, attempted_method, matched_client_id, confidence,
         signal_payload, decision, resolver_version)
    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
"""


async def process_message(
    conn: asyncpg.Connection,
    msg: dict[str, Any],
    *,
    dry_run: bool,
    metrics: ResolverMetrics,
) -> None:
    """Cascade resolve + write outcome (or skip if dry_run)."""
    result: ResolveResult | None = None
    audit_rows: list[tuple] = []

    for resolver in CASCADE:
        try:
            r = await resolver(conn, msg)
        except Exception as exc:
            logger.exception("resolver %s failed for msg %s: %s",
                             resolver.__name__, msg["id"], exc)
            metrics.errors += 1
            continue

        if r is None:
            continue

        # In review band but ambiguous or below threshold → log as audit, keep cascading
        if (r.client_id is None and r.team_member_id is None) or r.confidence < MIN_APPLY_CONFIDENCE:
            decision = "ambiguous" if r.signal_payload.get("ambiguous") else (
                "needs_review" if REVIEW_BAND_LOW <= r.confidence < REVIEW_BAND_HIGH
                else "skipped_low_conf"
            )
            audit_rows.append((
                msg["id"], r.method, r.client_id, r.confidence,
                json.dumps(r.signal_payload), decision, RESOLVER_VERSION,
            ))
            if decision == "needs_review":
                metrics.needs_review_band += 1
            continue

        # Apply this result
        result = r
        audit_rows.append((
            msg["id"], r.method, r.client_id, r.confidence,
            json.dumps(r.signal_payload), "applied", RESOLVER_VERSION,
        ))
        break

    if result is None:
        # No signal matched
        if not audit_rows:
            audit_rows.append((
                msg["id"], "none", None, 0.0,
                "{}", "no_signal_match", RESOLVER_VERSION,
            ))
        metrics.unresolved += 1
    else:
        metrics.bump(result.method)

    if dry_run:
        return

    # Atomic: UPDATE + INSERT audit in same transaction (the outer batch already in tx)
    if result is not None:
        await conn.execute(
            UPDATE_MSG_SQL,
            msg["id"],
            result.client_id,
            result.method,
            result.confidence,
            result.team_member_id,
            result.sender_role,
        )

    if audit_rows:
        await conn.executemany(INSERT_AUDIT_SQL, audit_rows)


async def resolve_batch(
    pool: asyncpg.Pool,
    *,
    batch_size: int,
    since: str | None,
    until: str | None,
    force: bool,
    dry_run: bool,
    max_batches: int | None = None,
) -> ResolverMetrics:
    """Main batch loop."""
    metrics = ResolverMetrics()
    t0 = time.monotonic()

    # Baseline %
    async with pool.acquire() as conn:
        baseline = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(client_id) AS resolved
            FROM whatsapp_message_context
            """
        )
        if baseline["total"] > 0:
            metrics.baseline_pct = round(100.0 * baseline["resolved"] / baseline["total"], 2)

    batch_idx = 0
    offset = 0
    while True:
        if max_batches is not None and batch_idx >= max_batches:
            break

        async with pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    SELECT_BATCH_SQL,
                    MIN_APPLY_CONFIDENCE,
                    since,
                    until,
                    force,
                    batch_size,
                    offset,
                )
                if not rows:
                    break

                # Per-batch caches (avoid re-running identical trgm lookups
                # for repeated batch_id / sender_push_name / candidate_name).
                cache_drive_folder: dict[str, list] = {}
                cache_team_name: dict[str, list] = {}
                cache_sender_name: dict[str, list] = {}
                for r in rows:
                    msg = dict(r)
                    if msg.get("identity_method") and msg.get("identity_confidence", 0) >= MIN_APPLY_CONFIDENCE and not force:
                        metrics.already_resolved_skipped += 1
                        continue
                    metrics.total_scanned += 1
                    msg["_cache_drive_folder"] = cache_drive_folder
                    msg["_cache_team_name"] = cache_team_name
                    msg["_cache_sender_name"] = cache_sender_name
                    await process_message(conn, msg, dry_run=dry_run, metrics=metrics)

        batch_idx += 1
        offset += batch_size
        logger.info(
            "batch %d done, scanned=%d so far, cache: drive=%d team=%d sender=%d",
            batch_idx, metrics.total_scanned,
            len(cache_drive_folder), len(cache_team_name), len(cache_sender_name),
        )

    # Post %
    async with pool.acquire() as conn:
        post = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(client_id) AS resolved
            FROM whatsapp_message_context
            """
        )
        if post["total"] > 0:
            metrics.post_run_pct = round(100.0 * post["resolved"] / post["total"], 2)
            metrics.delta_pp = round(metrics.post_run_pct - metrics.baseline_pct, 2)

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    # Fallback: parse password from DATABASE_URL_FLY
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url  # caller's problem
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="identity_resolver")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist resolutions")
    g.add_argument("--dry-run", action="store_true", help="Compute only, no DB writes")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--since", default=None, help="ISO date, e.g. 2026-05-01")
    parser.add_argument("--until", default=None, help="ISO date, e.g. 2026-05-25")
    parser.add_argument("--force", action="store_true", help="Re-resolve even if already resolved")
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--metrics-json", default=None, help="Write metrics to JSON file")
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=5,
        statement_cache_size=0,  # PgBouncer-safe
        command_timeout=60,
    )
    try:
        metrics = await resolve_batch(
            pool,
            batch_size=args.batch_size,
            since=args.since,
            until=args.until,
            force=args.force,
            dry_run=args.dry_run,
            max_batches=args.max_batches,
        )
    finally:
        await pool.close()

    payload = {
        "resolver_version": RESOLVER_VERSION,
        "dry_run": args.dry_run,
        **asdict(metrics),
    }
    logger.info("RUN_METRICS %s", json.dumps(payload, indent=2))

    if args.metrics_json:
        with open(args.metrics_json, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info("metrics written to %s", args.metrics_json)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
