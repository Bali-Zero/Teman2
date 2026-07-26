#!/usr/bin/env python3
"""Intake identity backfill — fills `clients.passport_number` / `clients.kitas_number`
on the LOCAL intake DB (`nuzantara_dev`) from two evidence fuels, per the frozen v3
design (`research/operations/2026-07-18-intake-identity-backfill-design.md`):

* **Fuel C** (`batch-c`) — human-committed documents (`intake_commit_audit`,
  outcome='committed', dry_run=false) whose extracted passport/kitas the client's
  own column is still empty for. Field-level adjudicated: 2 proposal ids are
  quarantined by default (3470, 12923 — corner's known scar case).
* **Fuel A** (`batch-a`) — cross-DB (PROD `nuzantara_rag` → LOCAL `nuzantara_dev`)
  strict fill: bidirectionally-unique phone pairing + exact whole-name match +
  passport-fill-only + nationality non-conflict.

Every write is **fill-only** (never overwrites a non-empty normalized id), carries a
`verified:false` provenance record under `clients.custom_fields.identity_backfill.<col>`
(GATE-11 — a backfilled id must not become an operative matching key until an
independent document confirms it; consumer-side enforcement lives in
`auto_attach`/`routing.py`, patched separately — NOT this script's job), and is
reversible by `batch_id` via the `rollback` subcommand.

**Non-negotiables enforced here** (design §3/§8):
- Fill-only CAS UPDATE (`WHERE ... AND length(normalized(<col>)) < 6`).
- An immutable MANIFEST of conflict-cohorts (multi-passport-doc clients, local
  passport/phone dup-groups, prod phone dup-groups) is computed BEFORE any write and
  subtracted globally from both fuels (F15).
- SSOT canonicalizers (`canon_id`/`canon_name`/`canon_phone`/`canon_nationality`) —
  a value whose ROUTING normalization diverges from its FULL normalization is
  quarantined, never guessed (F11).
- Zero PII on disk: the only artifacts are audit JSONL (`ts/batch_id/rule/client_id/
  column/<ref>/action` — ints and enums only) at
  `~/.nuzantara-identity-backfill/<batch_id>.jsonl` (dir 0700, file 0600), and log
  lines carrying the same shape. Prod data is fetched via `scripts/pg.sh` (read-only
  role) and never written back; it never touches disk, only process memory.

Usage:
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py manifest
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py census
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py batch-c [--apply] [--limit N]
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py batch-a [--apply] [--limit N]
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py rollback --batch-id C-20260718-a1b2
    apps/backend-rag/.venv/bin/python scripts/intake_identity_backfill.py measure

Env:
    INTAKE_DATABASE_URL             LOCAL nuzantara_dev DSN
                                     (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
    IDENTITY_BACKFILL_WRITE_ENABLED must be truthy ("1"/"true"/"yes"/"on") for ANY
                                     `--apply` write to proceed — mirrors
                                     `INTAKE_WRITER_ENABLED` (writer.py).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger("zantara.scripts.identity_backfill")

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG_ROOT = REPO_ROOT / "apps" / "backend-rag"
PG_SH = Path(__file__).resolve().parent / "pg.sh"

AUDIT_DIR = Path.home() / ".nuzantara-identity-backfill"

_CACHE_NAMESPACES: tuple[str, ...] = ("zantara:crm_clients_stats:*", "zantara:crm_practices:*")

_WRITABLE_COLUMNS: tuple[str, ...] = ("passport_number", "kitas_number")

_DEFAULT_EXCLUDE_PROPOSALS = "3470,12923"


# ---------------------------------------------------------------------------
# SSOT canonicalizers — module-level, unit-tested. Every match decision in this
# script routes through these; no ad-hoc regex is allowed to drift from them
# (F11 — the red-team's normalization-divergence finding).
# ---------------------------------------------------------------------------

# Demonym/country -> ISO-2. Unknown input -> None (never guessed).
_NATIONALITY_MAP: dict[str, str] = {
    "italian": "IT", "italiana": "IT", "italiano": "IT", "italy": "IT",
    "indonesian": "ID", "indonesia": "ID", "wni": "ID",
    "australian": "AU", "australia": "AU",
    "american": "US", "usa": "US", "united states": "US",
    "british": "GB", "uk": "GB", "english": "GB",
    "german": "DE", "germany": "DE", "deutsch": "DE",
    "french": "FR", "france": "FR",
    "spanish": "ES", "spain": "ES", "española": "ES",
    "russian": "RU", "russia": "RU",
    "ukrainian": "UA", "ukraine": "UA",
    "dutch": "NL", "netherlands": "NL",
    "swiss": "CH", "switzerland": "CH",
    "indian": "IN", "india": "IN",
    "japanese": "JP", "japan": "JP",
    "chinese": "CN", "china": "CN",
}


def canon_id(v: Any) -> str | None:
    """Canonicalize a strong identifier (passport/kitas number).

    Mirrors the production matcher's ROUTING normalization
    (`routing.py::_normalize_id` — strip only ``[\\s.\\-/]``, upper) and compares it
    against the FULL normalization (strip ALL non-alnum, upper). If the two diverge
    (e.g. a stray ``#`` or other punctuation the matcher would NOT strip but a naive
    census would), the value is quarantined — return ``None`` rather than guess
    (F11, the red-team's normalization-divergence finding).

    Also rejects:
    - empty/whitespace-only values
    - normalized length < 6
    - values that arrived as ``int``/``float`` (not ``str``) whose normalized form is
      all-digit — a JSON/DB numeric column silently drops leading zeros
      (``"0123456"`` -> ``123456``), so a numeric-typed source for an all-digit id is
      treated as untrustworthy (leading-zero loss guard). A ``str`` input that
      happens to be all-digit (e.g. a real all-numeric KITAS number) is NOT rejected.
    """
    if v is None:
        return None
    original_is_numeric = isinstance(v, (int, float)) and not isinstance(v, bool)
    s = str(v).strip()
    if not s:
        return None
    routing_norm = re.sub(r"[\s.\-/]", "", s).upper()
    full_norm = re.sub(r"[^A-Za-z0-9]", "", s).upper()
    if routing_norm != full_norm:
        return None
    if len(full_norm) < 6:
        return None
    if original_is_numeric and full_norm.isdigit():
        return None
    return full_norm


def _name_junk_check(collapsed: str) -> bool:
    """True if a whitespace-collapsed, casefolded name is junk (mirrors
    `client_enricher._name_is_junk`, evaluated BEFORE punctuation is stripped to
    spaces — the 'lead +'/'lead+' markers rely on the literal '+' surviving)."""
    if not collapsed:
        return True
    if collapsed == "unknown":
        return True
    if collapsed.startswith("lead +") or collapsed.startswith("lead+"):
        return True
    digits_only = collapsed.replace("+", "").replace(" ", "").replace("-", "")
    return digits_only.isdigit()


def canon_name(v: Any) -> str | None:
    """Canonicalize a person name: casefold, collapse whitespace, strip punctuation
    to spaces. Returns ``None`` for empty / 'unknown' / WhatsApp lead placeholders
    ('lead +62...') / digits-only junk.

    Junk-detection runs on the casefolded+whitespace-collapsed (but
    punctuation-INTACT) string — the 'lead +' marker's '+' must survive to be
    checked. The final returned value additionally strips punctuation to spaces
    (so hyphenated/dotted names tokenize correctly downstream in `name_tokens`).
    """
    if v is None:
        return None
    collapsed = " ".join(str(v).split()).casefold().strip()
    if _name_junk_check(collapsed):
        return None
    depunctuated = re.sub(r"[^\w\s]", " ", collapsed, flags=re.UNICODE)
    canon = " ".join(depunctuated.split())
    return canon or None


def name_tokens(v: Any) -> frozenset[str]:
    """Informative tokens (len >= 2) of a canonicalized name."""
    canon = canon_name(v)
    if not canon:
        return frozenset()
    return frozenset(tok for tok in canon.split(" ") if len(tok) >= 2)


def exact_token_set(a: Any, b: Any) -> bool:
    """True iff both names produce non-empty, EQUAL token sets with >=2 informative
    tokens on each side. A subset ('ALPHA BETA' vs 'ALPHA BETA GAMMA') is NOT equal."""
    ta, tb = name_tokens(a), name_tokens(b)
    if len(ta) < 2 or len(tb) < 2:
        return False
    return ta == tb


def canon_phone(v: Any) -> str | None:
    """Digits-only phone, with Indonesian leading-'0' <-> '62' equivalence
    (08x == 628x). None if fewer than 8 digits."""
    if v is None:
        return None
    digits = re.sub(r"\D", "", str(v))
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if len(digits) < 8:
        return None
    return digits


def canon_nationality(v: Any) -> str | None:
    """Static demonym/country -> ISO-2. Unknown -> None (never guessed)."""
    if v is None:
        return None
    s = " ".join(str(v).split()).strip().casefold()
    return _NATIONALITY_MAP.get(s)


def _unwrap(raw: Any) -> Any:
    """Pull the scalar out of an intake-extract field: `{"value": X, ...}` or flat."""
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


# ---------------------------------------------------------------------------
# Local DB access
# ---------------------------------------------------------------------------


def _local_dsn() -> str:
    return os.environ.get("INTAKE_DATABASE_URL") or "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"


async def _assert_writable_columns_exist(conn: asyncpg.Connection) -> None:
    """Defensive schema-drift guard (mirrors client_enricher's existing_cols check) —
    this script only ever targets LOCAL nuzantara_dev, but never assume a column
    exists without checking (Golden Rule #9)."""
    existing = {
        r["column_name"]
        for r in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'clients' AND table_schema = current_schema()"
        )
    }
    missing = [c for c in _WRITABLE_COLUMNS if c not in existing]
    if missing:
        raise RuntimeError(f"clients table is missing expected column(s): {missing}")


async def _fetch_local_clients(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        "SELECT id, passport_number, kitas_number, phone_normalized, email, "
        "nationality, full_name, custom_fields "
        "FROM clients WHERE deleted_at IS NULL"
    )
    return [dict(r) for r in rows]


def _fields_from_texts(routing_text: str | None, stage_output_text: str | None) -> dict[str, Any]:
    routing = json.loads(routing_text) if routing_text else {}
    so = json.loads(stage_output_text) if stage_output_text else {}
    fields = (routing or {}).get("fields") or ((so or {}).get("extract") or {}).get("fields") or {}
    return fields if isinstance(fields, dict) else {}


async def _fetch_review_pending_single_candidate(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """review_pending proposals whose entity_resolution has EXACTLY ONE candidate
    and that candidate is a `clients` row (design §manifest(a))."""
    rows = await conn.fetch(
        "SELECT p.id AS proposal_id, "
        "(p.entity_resolution->'candidates'->0->>'id')::bigint AS candidate_id, "
        "p.routing::text AS routing, q.stage_output::text AS stage_output "
        "FROM document_routing_proposal p JOIN intake_queue q ON q.id = p.queue_id "
        "WHERE p.status = 'review_pending' "
        "AND jsonb_typeof(p.entity_resolution->'candidates') = 'array' "
        "AND jsonb_array_length(p.entity_resolution->'candidates') = 1 "
        "AND (p.entity_resolution->'candidates'->0->>'table') = 'clients'"
    )
    return [dict(r) for r in rows]


async def _fetch_review_pending_with_candidates(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        "SELECT p.entity_resolution::text AS er, p.routing::text AS routing, "
        "q.stage_output::text AS stage_output "
        "FROM document_routing_proposal p JOIN intake_queue q ON q.id = p.queue_id "
        "WHERE p.status = 'review_pending' "
        "AND jsonb_typeof(p.entity_resolution->'candidates') = 'array' "
        "AND jsonb_array_length(p.entity_resolution->'candidates') > 0"
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Prod (READ-ONLY) access via scripts/pg.sh — NEVER a direct connection, NEVER a
# mutating statement. Prod data lives ONLY in process memory (Law 2).
# ---------------------------------------------------------------------------

_FORBIDDEN_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|MERGE)\b", re.IGNORECASE
)


def _run_pg_sh(sql: str) -> list[list[str]]:
    """Read-only prod query via `scripts/pg.sh` (SQL fed on stdin). Defense-in-depth
    word-boundary guard against any mutating verb on top of the read-only DB role
    `pg.sh` already authenticates as."""
    if _FORBIDDEN_SQL_RE.search(sql):
        raise ValueError("refusing to run non-SELECT SQL through pg.sh — prod is READ-ONLY for this script")
    proc = subprocess.run(
        ["bash", str(PG_SH), "-tA", "-F", "\t"],
        input=sql,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pg.sh failed (exit {proc.returncode}): {proc.stderr.strip()[:300]}")
    return [ln.split("\t") for ln in proc.stdout.splitlines() if ln != ""]


def _fetch_prod_clients() -> list[dict[str, Any]]:
    rows = _run_pg_sh(
        "SELECT id, passport_number, phone_normalized, full_name, nationality "
        "FROM clients WHERE deleted_at IS NULL;"
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        if len(r) < 5:
            continue
        out.append(
            {
                "id": int(r[0]),
                "passport_number": r[1] or None,
                "phone_normalized": r[2] or None,
                "full_name": r[3] or None,
                "nationality": r[4] or None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Coverage / census helpers (shared by `census` and `measure`)
# ---------------------------------------------------------------------------


def _dup_groups(id_to_canon: dict[int, str | None]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for cid, canon in id_to_canon.items():
        if canon:
            groups[canon].append(cid)
    return {k: v for k, v in groups.items() if len(v) > 1}


def _coverage_counts(clients: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(clients)
    passport_by_id = {c["id"]: canon_id(c.get("passport_number")) for c in clients}
    kitas_by_id = {c["id"]: canon_id(c.get("kitas_number")) for c in clients}
    phone_by_id = {c["id"]: canon_phone(c.get("phone_normalized")) for c in clients}
    n_passport = sum(1 for v in passport_by_id.values() if v)
    n_kitas = sum(1 for v in kitas_by_id.values() if v)
    n_phone = sum(1 for v in phone_by_id.values() if v)
    n_email = sum(1 for c in clients if c.get("email"))
    n_none = sum(
        1
        for c in clients
        if not passport_by_id[c["id"]]
        and not kitas_by_id[c["id"]]
        and not phone_by_id[c["id"]]
        and not c.get("email")
    )
    passport_groups = _dup_groups(passport_by_id)
    phone_groups = _dup_groups(phone_by_id)
    return {
        "total": total,
        "passport": n_passport,
        "kitas": n_kitas,
        "phone": n_phone,
        "email": n_email,
        "no_identifier": n_none,
        "passport_dup_groups": len(passport_groups),
        "passport_dup_rows": sum(len(g) for g in passport_groups.values()),
        "phone_dup_groups": len(phone_groups),
        "phone_dup_rows": sum(len(g) for g in phone_groups.values()),
        "_passport_by_id": passport_by_id,
        "_kitas_by_id": kitas_by_id,
    }


async def _det_match_metrics(
    conn: asyncpg.Connection,
    passport_by_id: dict[int, str | None],
    kitas_by_id: dict[int, str | None],
) -> tuple[int, int]:
    """Returns (DET_MATCH_NOW, proposals_with_any_strong_id_candidate_match).

    DET_MATCH_NOW = proposals where EXACTLY ONE candidate's client passport/kitas
    canon-matches the document's own extracted passport/kitas (the deterministic
    tiebreak the refinery already uses). The looser "any match" count is the
    corroboration-signal indicator referenced by `measure` (design §6.5).
    """
    rows = await _fetch_review_pending_with_candidates(conn)
    det = any_match = 0
    for row in rows:
        er = json.loads(row["er"]) if row["er"] else {}
        candidates = er.get("candidates") or []
        client_ids = [
            int(c["id"]) for c in candidates if c.get("table") == "clients" and c.get("id") is not None
        ]
        if not client_ids:
            continue
        fields = _fields_from_texts(row["routing"], row["stage_output"])
        doc_pp = canon_id(_unwrap(fields.get("passport_no")))
        doc_kt = canon_id(_unwrap(fields.get("kitas_no")))
        if not doc_pp and not doc_kt:
            continue
        hits: set[int] = set()
        for cid in client_ids:
            if doc_pp and passport_by_id.get(cid) == doc_pp:
                hits.add(cid)
            elif doc_kt and kitas_by_id.get(cid) == doc_kt:
                hits.add(cid)
        if hits:
            any_match += 1
            if len(hits) == 1:
                det += 1
    return det, any_match


# ---------------------------------------------------------------------------
# MANIFEST — immutable exclusion sets, computed BEFORE any write, in memory only
# (F15). Shared by `manifest`, `batch-c`, `batch-a`.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestExclusions:
    multi_doc_passport_clients: frozenset[int]  # (a) local clients w/ >1 distinct doc-passport
    local_dup_passport_clients: frozenset[int]  # (b) local passport dup-group members
    local_dup_phone_clients: frozenset[int]  # (c) local phone dup-group members
    prod_dup_phone_clients: frozenset[int]  # (d) prod phone dup-group members


async def _multi_doc_passport_clients(conn: asyncpg.Connection) -> set[int]:
    rows = await _fetch_review_pending_single_candidate(conn)
    by_client: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        cid = r["candidate_id"]
        if cid is None:
            continue
        fields = _fields_from_texts(r["routing"], r["stage_output"])
        pp = canon_id(_unwrap(fields.get("passport_no")))
        if pp:
            by_client[cid].add(pp)
    return {cid for cid, s in by_client.items() if len(s) > 1}


async def _fetch_queue_docs_with_candidates(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Queue documents carrying >=1 `clients` candidate, across the statuses a
    contradiction can meaningfully come from: still-pending, already
    system-auto-attached, or already human-routed (a routed doc's passport is
    the strongest possible contradiction signal — a human already confirmed
    it). Broader than `_fetch_review_pending_with_candidates` (review_pending
    only), which stays narrow because DET_MATCH_NOW is specifically about the
    open review queue."""
    rows = await conn.fetch(
        "SELECT p.entity_resolution::text AS er, p.routing::text AS routing, "
        "q.stage_output::text AS stage_output "
        "FROM document_routing_proposal p JOIN intake_queue q ON q.id = p.queue_id "
        "WHERE p.status IN ('review_pending', 'auto_routed', 'routed') "
        "AND jsonb_typeof(p.entity_resolution->'candidates') = 'array' "
        "AND jsonb_array_length(p.entity_resolution->'candidates') > 0"
    )
    return [dict(r) for r in rows]


async def _client_doc_passport_map(conn: asyncpg.Connection) -> dict[int, frozenset[str]]:
    """client_id -> set of canon doc-passports across EVERY queue proposal (any
    of the statuses above, any candidate-count) that lists the client among
    its candidates.

    Broader than `_multi_doc_passport_clients` (which only looks at
    single-candidate `review_pending` rows): this feeds the batch-a
    queue-contradiction gate, which needs to know "has ANY document in the
    queue ever named a DIFFERENT passport for this client" regardless of how
    many candidates that document resolved to.
    """
    rows = await _fetch_queue_docs_with_candidates(conn)
    by_client: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        er = json.loads(r["er"]) if r["er"] else {}
        candidates = er.get("candidates") or []
        client_ids = [
            int(c["id"]) for c in candidates if c.get("table") == "clients" and c.get("id") is not None
        ]
        if not client_ids:
            continue
        fields = _fields_from_texts(r["routing"], r["stage_output"])
        pp = canon_id(_unwrap(fields.get("passport_no")))
        if not pp:
            continue
        for cid in client_ids:
            by_client[cid].add(pp)
    return {cid: frozenset(s) for cid, s in by_client.items()}


async def build_manifest_exclusions(conn: asyncpg.Connection) -> ManifestExclusions:
    local_clients = await _fetch_local_clients(conn)
    passport_by_id = {c["id"]: canon_id(c.get("passport_number")) for c in local_clients}
    phone_by_id = {c["id"]: canon_phone(c.get("phone_normalized")) for c in local_clients}
    local_dup_passport = {cid for g in _dup_groups(passport_by_id).values() for cid in g}
    local_dup_phone = {cid for g in _dup_groups(phone_by_id).values() for cid in g}
    multi_doc = await _multi_doc_passport_clients(conn)

    prod_clients = _fetch_prod_clients()
    prod_phone_by_id = {c["id"]: canon_phone(c.get("phone_normalized")) for c in prod_clients}
    prod_dup_phone = {cid for g in _dup_groups(prod_phone_by_id).values() for cid in g}

    return ManifestExclusions(
        multi_doc_passport_clients=frozenset(multi_doc),
        local_dup_passport_clients=frozenset(local_dup_passport),
        local_dup_phone_clients=frozenset(local_dup_phone),
        prod_dup_phone_clients=frozenset(prod_dup_phone),
    )


def _print_manifest(excl: ManifestExclusions) -> None:
    union = (
        excl.multi_doc_passport_clients
        | excl.local_dup_passport_clients
        | excl.local_dup_phone_clients
    )
    print("=== MANIFEST exclusion sets (counts only — Law 2) ===")
    print(f"(a) LOCAL clients with >1 distinct doc-passport (multi-pass funnel): {len(excl.multi_doc_passport_clients)}")
    print(f"(b) LOCAL clients in a passport dup-group:                          {len(excl.local_dup_passport_clients)}")
    print(f"(c) LOCAL clients in a phone dup-group:                             {len(excl.local_dup_phone_clients)}")
    print(f"(d) PROD clients in a phone dup-group:                              {len(excl.prod_dup_phone_clients)}")
    print(f"LOCAL union (a ∪ b ∪ c), deduplicated — subtracted from batch-c/batch-a: {len(union)}")


# ---------------------------------------------------------------------------
# census / measure
# ---------------------------------------------------------------------------


def _pct(n: int, total: int) -> str:
    return f"{n} ({n / total:.1%})" if total else str(n)


async def _print_coverage_report(conn: asyncpg.Connection, header: str) -> None:
    local_clients = await _fetch_local_clients(conn)
    local_cov = _coverage_counts(local_clients)
    prod_clients = _fetch_prod_clients()
    prod_cov = _coverage_counts(prod_clients)
    det_now, any_match_now = await _det_match_metrics(
        conn, local_cov["_passport_by_id"], local_cov["_kitas_by_id"]
    )

    print(f"=== {header} ===")
    print(f"{'metric':28s} {'LOCAL':>18s} {'PROD':>18s}")
    print(f"{'active clients':28s} {local_cov['total']:>18d} {prod_cov['total']:>18d}")
    print(
        f"{'passport (>=6 norm)':28s} "
        f"{_pct(local_cov['passport'], local_cov['total']):>18s} "
        f"{_pct(prod_cov['passport'], prod_cov['total']):>18s}"
    )
    print(f"{'kitas':28s} {local_cov['kitas']:>18d} {prod_cov['kitas']:>18d}")
    print(
        f"{'phone_normalized':28s} "
        f"{_pct(local_cov['phone'], local_cov['total']):>18s} "
        f"{_pct(prod_cov['phone'], prod_cov['total']):>18s}"
    )
    print(f"{'email':28s} {local_cov['email']:>18d} {'n/a':>18s}")
    print(f"{'no identifier at all':28s} {local_cov['no_identifier']:>18d} {'n/a':>18s}")
    passport_dup_str = f"{local_cov['passport_dup_groups']}g/{local_cov['passport_dup_rows']}r"
    phone_dup_str = f"{local_cov['phone_dup_groups']}g/{local_cov['phone_dup_rows']}r"
    print(f"{'passport dup-groups':28s} {passport_dup_str:>18s} {'n/a':>18s}")
    print(f"{'phone dup-groups':28s} {phone_dup_str:>18s} {'n/a':>18s}")
    print()
    print(f"DET_MATCH_NOW (single deterministic strong-id hit among candidates): {det_now}")
    print(f"proposals with >=1 strong-id candidate match (corroboration signal): {any_match_now}")


async def run_census(conn: asyncpg.Connection) -> None:
    await _print_coverage_report(conn, "CENSUS baseline (Legge 7)")


async def run_measure(conn: asyncpg.Connection) -> None:
    await _print_coverage_report(conn, "MEASURE after-state")
    print()
    print(
        "(compare against a `census` run captured BEFORE the batches for the actual "
        "before/after delta — this script does not persist a baseline snapshot)"
    )


# ---------------------------------------------------------------------------
# Audit JSONL — the ONLY on-disk artifact besides logs. PII-free by construction:
# only ints, enums, batch/rule/column strings.
# ---------------------------------------------------------------------------


class AuditWriter:
    def __init__(self, batch_id: str) -> None:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(AUDIT_DIR, 0o700)
        self.path = AUDIT_DIR / f"{batch_id}.jsonl"
        self._fh = self.path.open("a", encoding="utf-8")
        os.chmod(self.path, 0o600)

    def write(self, **fields: Any) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), **fields}
        self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "AuditWriter":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Write gate + CAS write mechanics
# ---------------------------------------------------------------------------


def _write_enabled() -> bool:
    return os.environ.get("IDENTITY_BACKFILL_WRITE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _require_write_enabled() -> None:
    if not _write_enabled():
        raise RuntimeError(
            "IDENTITY_BACKFILL_WRITE_ENABLED is not truthy — refusing real write. "
            "Set IDENTITY_BACKFILL_WRITE_ENABLED=true to enable --apply writes "
            "(mirrors the INTAKE_WRITER_ENABLED pattern in writer.py)."
        )


def _new_batch_id(rule: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{rule[0]}-{day}-{secrets.token_hex(2)}"


async def _apply_fill(
    conn: asyncpg.Connection,
    client_id: int,
    column: str,
    value: str,
    provenance: dict[str, Any],
) -> bool:
    """Single atomic fill-only UPDATE (CAS via the WHERE + RETURNING). Returns False
    ("lost-cas-race") if no row matched — e.g. the column was filled by something
    else between our pre-check and this write. That is a benign race, not an error."""
    if column not in _WRITABLE_COLUMNS:
        raise ValueError(f"refusing to write unexpected column {column!r}")
    sql = (
        f"UPDATE clients SET {column} = $1, "
        f"custom_fields = jsonb_set(coalesce(custom_fields,'{{}}'::jsonb), "
        f"'{{identity_backfill,{column}}}', $2::jsonb, true), "
        f"updated_at = NOW() "
        f"WHERE id = $3 AND deleted_at IS NULL "
        f"AND length(upper(regexp_replace(coalesce({column},''),'[^A-Za-z0-9]','','g'))) < 6 "
        f"RETURNING id"
    )
    row = await conn.fetchrow(sql, value, json.dumps(provenance), client_id)
    return row is not None


async def _process_fill(
    conn: asyncpg.Connection,
    *,
    apply: bool,
    client_id: int,
    column: str,
    canon_value: str,
    rule: str,
    batch_id: str,
    source: str,
    src_ref: int,
    counts: dict[str, int],
) -> str:
    """Pre-check (fill-only, fresh read) + dry-run/apply. Returns the action string
    also written to the audit JSONL."""
    row = await conn.fetchrow(
        f"SELECT {column} AS val FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id
    )
    if row is None:
        counts["skip-client-not-found"] += 1
        return "skip-client-not-found"
    if canon_id(row["val"]) is not None:
        counts["skip-already-filled"] += 1
        return "skip-already-filled"
    if not apply:
        counts["would-apply"] += 1
        return "would-apply"
    _require_write_enabled()
    provenance = {
        "verified": False,
        "batch": batch_id,
        "rule": rule,
        "source": source,
        "src_ref": src_ref,
        "value_md5": hashlib.md5(canon_value.encode()).hexdigest(),
        "steward": "system:identity-backfill",
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    ok = await _apply_fill(conn, client_id, column, canon_value, provenance)
    if ok:
        counts["applied"] += 1
        return "applied"
    counts["lost-cas-race"] += 1
    return "lost-cas-race"


def _print_batch_summary(name: str, batch_id: str, counts: dict[str, int]) -> None:
    print(f"=== {name} (batch_id={batch_id}) ===")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    print(f"  TOTAL rows considered: {sum(counts.values())}")


# ---------------------------------------------------------------------------
# Cache invalidation — best-effort, with an empirically-verified fallback path.
# ---------------------------------------------------------------------------


async def _invalidate_identity_backfill_cache() -> None:
    """Best-effort cache invalidation after an applied lot.

    `backend.core.cache.invalidate_cache` IS importable from a bare script (verified
    empirically 2026-07-18) — but `CacheService._try_connect_redis()` reaches Redis
    via `RedisManager.get_instance().get_async_client()` WITHOUT ever calling
    `RedisManager.initialize()`; that call only happens during the FastAPI app
    lifespan. In a standalone script process nothing calls `.initialize()`, so the
    async client is always ``None`` and `invalidate_cache()` silently degrades to an
    ephemeral in-memory cache local to THIS process — a no-op against the real
    running API's cache (an "Esiste ≠ Armato" trap: it returns cleanly, but
    invalidates nothing real). Detect the fallback and warn instead of claiming
    success.
    """
    try:
        if str(BACKEND_RAG_ROOT) not in sys.path:
            sys.path.insert(0, str(BACKEND_RAG_ROOT))
        from backend.core.cache import get_cache_service, invalidate_cache  # noqa: E402
    except Exception as exc:  # pragma: no cover - environment-dependent
        logger.warning(
            "cache invalidation helper not importable in this script context (%s) — "
            "invalidate manually via the API for namespaces: %s",
            exc,
            ", ".join(_CACHE_NAMESPACES),
        )
        return
    for ns in _CACHE_NAMESPACES:
        try:
            await invalidate_cache(ns)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("invalidate_cache(%s) raised %s — invalidate manually via the API", ns, exc)
    backend_kind = get_cache_service().get_stats().get("backend")
    if backend_kind != "redis":
        logger.warning(
            "cache invalidation ran against the in-process '%s' fallback, NOT the shared "
            "Redis the running API reads (RedisManager.initialize() is never called "
            "outside the FastAPI lifespan) — this is a NO-OP for the live app. "
            "Invalidate manually via the API for namespaces: %s",
            backend_kind,
            ", ".join(_CACHE_NAMESPACES),
        )
    else:
        logger.info("cache invalidated via shared Redis for namespaces: %s", ", ".join(_CACHE_NAMESPACES))


# ---------------------------------------------------------------------------
# BATCH-C — Fuel C: human-committed docs
# ---------------------------------------------------------------------------


def _parse_exclude_proposals(raw: str) -> set[int]:
    return {int(x) for x in raw.split(",") if x.strip()}


async def run_batch_c(
    conn: asyncpg.Connection, *, apply: bool, exclude_proposals: str, limit: int | None
) -> None:
    await _assert_writable_columns_exist(conn)
    excluded_proposal_ids = _parse_exclude_proposals(exclude_proposals)
    manifest = await build_manifest_exclusions(conn)
    excluded_clients = (
        manifest.multi_doc_passport_clients
        | manifest.local_dup_passport_clients
        | manifest.local_dup_phone_clients
    )
    if apply:
        _require_write_enabled()

    rows = await conn.fetch(
        "SELECT a.proposal_id, a.client_id, a.plan::text AS plan "
        "FROM intake_commit_audit a "
        "WHERE a.outcome = 'committed' AND a.dry_run = false AND a.client_id IS NOT NULL "
        "ORDER BY a.committed_at ASC"
    )

    rule = "C-doccommitted-v1"
    batch_id = _new_batch_id(rule)
    counts: dict[str, int] = defaultdict(int)
    candidates: list[tuple[int, int, str, str]] = []
    for r in rows:
        proposal_id = r["proposal_id"]
        client_id = r["client_id"]
        if proposal_id in excluded_proposal_ids:
            counts["skip-quarantined-proposal"] += 1
            continue
        plan = json.loads(r["plan"]) if r["plan"] else {}
        doc_type = plan.get("doc_type")
        if doc_type not in ("passport", "kitas"):
            continue  # out of scope for identity backfill (npwp/nib etc.)
        payload = plan.get("payload") or {}
        extracted = payload.get("extracted_fields") or {}
        column, raw_key = ("passport_number", "passport_no") if doc_type == "passport" else (
            "kitas_number",
            "kitas_no",
        )
        canon_value = canon_id(_unwrap(extracted.get(raw_key)))
        if canon_value is None:
            counts["skip-invalid-value"] += 1
            continue
        if client_id in excluded_clients:
            counts["skip-manifest-exclusion"] += 1
            continue
        candidates.append((proposal_id, client_id, column, canon_value))

    if limit is not None:
        candidates = candidates[:limit]

    logger.info(
        "batch-c: %d candidate fills after exclusions (rule=%s, batch=%s, apply=%s)",
        len(candidates),
        rule,
        batch_id,
        apply,
    )
    with AuditWriter(batch_id) as audit:
        for proposal_id, client_id, column, canon_value in candidates:
            action = await _process_fill(
                conn,
                apply=apply,
                client_id=client_id,
                column=column,
                canon_value=canon_value,
                rule=rule,
                batch_id=batch_id,
                source="doc-commit",
                src_ref=proposal_id,
                counts=counts,
            )
            audit.write(
                batch_id=batch_id,
                rule=rule,
                client_id=client_id,
                column=column,
                proposal_id=proposal_id,
                action=action,
            )
    if apply and counts.get("applied"):
        await _invalidate_identity_backfill_cache()
    _print_batch_summary("batch-c", batch_id, counts)


# ---------------------------------------------------------------------------
# BATCH-A — Fuel A: cross-DB strict pairing
# ---------------------------------------------------------------------------


def pair_by_unique_phone(
    prod_rows: Iterable[dict[str, Any]], local_rows: Iterable[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Bidirectionally-unique phone pairing: only pairs where the canon phone is
    UNIQUE among prod rows AND unique among local rows (design gate #4)."""
    prod_by_phone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in prod_rows:
        cp = canon_phone(r.get("phone_normalized"))
        if cp:
            prod_by_phone[cp].append(r)
    local_by_phone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in local_rows:
        cp = canon_phone(r.get("phone_normalized"))
        if cp:
            local_by_phone[cp].append(r)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for phone, prods in prod_by_phone.items():
        locs = local_by_phone.get(phone)
        if len(prods) == 1 and locs is not None and len(locs) == 1:
            pairs.append((prods[0], locs[0]))
    return pairs


def decide_pair(
    prod_row: dict[str, Any], local_row: dict[str, Any], context: dict[str, Any]
) -> tuple[str, str]:
    """Pure decision function for Fuel A STRICT pairing. Returns (verdict, reason)
    with verdict in {"WRITE", "SKIP"}. Does NOT touch the DB — callers pass in
    manifest-exclusion id sets via `context` so this stays independently testable
    on synthetic in-memory rows."""
    excluded_local_ids: set[int] = context.get("excluded_local_ids", set())
    excluded_prod_ids: set[int] = context.get("excluded_prod_ids", set())
    doc_passports_by_local_id: dict[int, frozenset[str]] = context.get(
        "doc_passports_by_local_id", {}
    )

    if local_row.get("id") in excluded_local_ids:
        return "SKIP", "local client in manifest exclusion set"
    if prod_row.get("id") in excluded_prod_ids:
        return "SKIP", "prod client in manifest exclusion set (dup phone)"

    prod_passport = canon_id(prod_row.get("passport_number"))
    if prod_passport is None:
        return "SKIP", "prod passport does not canonize"

    local_passport = canon_id(local_row.get("passport_number"))
    if local_passport is not None:
        return "SKIP", "local passport already filled (fill-only)"

    if not exact_token_set(prod_row.get("full_name"), local_row.get("full_name")):
        return "SKIP", "name mismatch (not exact token set)"

    prod_nat = canon_nationality(prod_row.get("nationality"))
    local_nat = canon_nationality(local_row.get("nationality"))
    if prod_nat is not None and local_nat is not None and prod_nat != local_nat:
        return "SKIP", "nationality conflict (review)"

    # queue-contradiction (council follow-up, 2026-07-18): if ANY document in
    # the local intake queue that names this client as a candidate carries a
    # DIFFERENT valid passport than the one we're about to backfill, the
    # documentary evidence disagrees with the phone/name pairing — demote to
    # review rather than write. Measured live: 33/277 STRICT pairs hit this
    # (mostly family/funnel noise). The inverse case — a queue doc carries the
    # SAME passport — is `doc_confirmed` and strengthens (never weakens) WRITE.
    local_doc_passports = doc_passports_by_local_id.get(local_row.get("id")) or frozenset()
    contradicting = {p for p in local_doc_passports if p != prod_passport}
    if contradicting:
        return "SKIP", "queue-contradiction: a queue document names this client with a different passport"

    doc_confirmed = prod_passport in local_doc_passports
    reason = "phone-1:1 + exact-name + passport-fill-only"
    if doc_confirmed:
        reason += " + doc-confirmed"
    return "WRITE", reason


_BATCH_A_LOT_SIZE = 50


async def run_batch_a(conn: asyncpg.Connection, *, apply: bool, limit: int | None) -> None:
    await _assert_writable_columns_exist(conn)
    manifest = await build_manifest_exclusions(conn)
    if apply:
        _require_write_enabled()

    prod_rows = _fetch_prod_clients()
    local_rows = await conn.fetch(
        "SELECT id, passport_number, phone_normalized, full_name, nationality, custom_fields "
        "FROM clients WHERE deleted_at IS NULL"
    )
    local_rows = [dict(r) for r in local_rows]

    pairs = pair_by_unique_phone(prod_rows, local_rows)
    doc_passports_by_local_id = await _client_doc_passport_map(conn)
    context = {
        "excluded_local_ids": (
            manifest.multi_doc_passport_clients
            | manifest.local_dup_passport_clients
            | manifest.local_dup_phone_clients
        ),
        "excluded_prod_ids": manifest.prod_dup_phone_clients,
        "doc_passports_by_local_id": doc_passports_by_local_id,
    }
    decisions = [(prod, local, *decide_pair(prod, local, context)) for prod, local in pairs]
    writes = [
        (prod, local, "doc-confirmed" in reason)
        for prod, local, verdict, reason in decisions
        if verdict == "WRITE"
    ]
    n_contradictions = sum(
        1 for _p, _l, verdict, reason in decisions if verdict == "SKIP" and "queue-contradiction" in reason
    )
    n_skipped_at_decide = len(decisions) - len(writes)
    n_writes_total = len(writes)
    if n_contradictions:
        logger.info("batch-a: %d pair(s) excluded by queue-contradiction", n_contradictions)

    if limit is not None:
        writes = writes[:limit]

    rule = "A-strict-v1"
    batch_id = _new_batch_id(rule)
    counts: dict[str, int] = defaultdict(int)
    counts["skip-decide-pair"] = n_skipped_at_decide

    logger.info(
        "batch-a: %d unique-phone pairs, %d WRITE-verdict total, %d selected for this run "
        "(rule=%s, batch=%s, apply=%s, limit=%s)",
        len(pairs),
        n_writes_total,
        len(writes),
        rule,
        batch_id,
        apply,
        limit,
    )

    with AuditWriter(batch_id) as audit:
        for lot_start in range(0, len(writes), _BATCH_A_LOT_SIZE):
            lot = writes[lot_start : lot_start + _BATCH_A_LOT_SIZE]
            lot_tally: dict[str, int] = defaultdict(int)
            for prod, local, doc_confirmed in lot:
                canon_value = canon_id(prod["passport_number"])
                assert canon_value is not None  # decide_pair already gated this
                action = await _process_fill(
                    conn,
                    apply=apply,
                    client_id=local["id"],
                    column="passport_number",
                    canon_value=canon_value,
                    rule=rule,
                    batch_id=batch_id,
                    source="prod-crm",
                    src_ref=prod["id"],
                    counts=counts,
                )
                audit.write(
                    batch_id=batch_id,
                    rule=rule,
                    client_id=local["id"],
                    column="passport_number",
                    prod_client_id=prod["id"],
                    action=action,
                    doc_confirmed=doc_confirmed,
                )
                lot_tally[action] += 1
            logger.info(
                "batch-a lot rows %d-%d/%d: %s",
                lot_start + 1,
                lot_start + len(lot),
                len(writes),
                dict(lot_tally),
            )
            if apply and lot_tally.get("applied"):
                await _invalidate_identity_backfill_cache()

    n_doc_confirmed_total = sum(1 for _p, _l, dc in writes if dc)
    _print_batch_summary("batch-a", batch_id, counts)
    print(f"  queue-contradiction excluded (review lead, not written): {n_contradictions}")
    print(f"  doc-confirmed among selected WRITE pairs (validation signal): {n_doc_confirmed_total}")
    if limit is not None and n_writes_total > len(writes):
        print(
            f"  NOTE: --limit {limit} capped processing to {len(writes)}/{n_writes_total} "
            "WRITE-verdict pairs — rerun with a higher/absent --limit to process the rest."
        )


# ---------------------------------------------------------------------------
# ROLLBACK
# ---------------------------------------------------------------------------


async def rollback_batch(conn: asyncpg.Connection, batch_id: str) -> None:
    audit_path = AUDIT_DIR / f"{batch_id}.jsonl"
    if not audit_path.exists():
        raise FileNotFoundError(f"no audit log found for batch {batch_id!r} at {audit_path}")

    entries: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("rollback: skipping malformed audit line in %s", audit_path)

    applied = [e for e in entries if e.get("action") == "applied"]
    reverted = skipped = 0
    for e in applied:
        client_id = e.get("client_id")
        column = e.get("column")
        if column not in _WRITABLE_COLUMNS or not isinstance(client_id, int):
            logger.warning("rollback: malformed audit entry (client=%s column=%s) — skip", client_id, column)
            skipped += 1
            continue

        row = await conn.fetchrow(
            f"SELECT {column} AS current_value, "
            f"(custom_fields->'identity_backfill'->'{column}') AS provenance "
            f"FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )
        if row is None:
            logger.info("rollback: client=%s not found or soft-deleted — skip", client_id)
            skipped += 1
            continue

        prov_raw = row["provenance"]
        prov = json.loads(prov_raw) if isinstance(prov_raw, str) else (prov_raw or {})
        if not prov or prov.get("batch") != batch_id:
            logger.info(
                "rollback: client=%s column=%s provenance batch mismatch — skip", client_id, column
            )
            skipped += 1
            continue

        current_norm = canon_id(row["current_value"]) or ""
        current_md5 = hashlib.md5(current_norm.encode()).hexdigest()
        if current_md5 != prov.get("value_md5"):
            logger.info(
                "rollback: client=%s column=%s value changed since write (human corrected) — skip",
                client_id,
                column,
            )
            skipped += 1
            continue

        merge_patch = json.dumps(
            {"reverted": True, "reverted_at": datetime.now(timezone.utc).isoformat()}
        )
        result = await conn.fetchrow(
            f"UPDATE clients SET {column} = NULL, "
            f"custom_fields = jsonb_set(custom_fields, '{{identity_backfill,{column}}}', "
            f"(custom_fields->'identity_backfill'->'{column}') || $1::jsonb, true), "
            f"updated_at = NOW() "
            f"WHERE id = $2 AND deleted_at IS NULL "
            f"AND (custom_fields->'identity_backfill'->'{column}'->>'batch') = $3 "
            f"AND md5(upper(regexp_replace(coalesce({column},''),'[^A-Za-z0-9]','','g'))) = "
            f"(custom_fields->'identity_backfill'->'{column}'->>'value_md5') "
            f"RETURNING id",
            merge_patch,
            client_id,
            batch_id,
        )
        if result is None:
            logger.warning("rollback: client=%s column=%s lost CAS race at write time — skip", client_id, column)
            skipped += 1
        else:
            reverted += 1

    print(f"=== rollback batch_id={batch_id} ===")
    print(f"  reverted: {reverted}")
    print(f"  skipped: {skipped}")
    print(f"  (audit entries scanned: {len(entries)}, 'applied' entries: {len(applied)})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="intake_identity_backfill",
        description="Backfill strong identifiers (passport/kitas) onto LOCAL intake clients.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("manifest", help="compute + print manifest exclusion-set counts")
    sub.add_parser("census", help="print baseline coverage numbers (Legge 7 'before')")

    p_c = sub.add_parser("batch-c", help="Fuel C: human-committed doc backfill")
    p_c.add_argument("--apply", action="store_true", help="perform real writes (default: dry-run)")
    p_c.add_argument(
        "--exclude-proposals",
        default=_DEFAULT_EXCLUDE_PROPOSALS,
        help="comma-separated proposal ids to quarantine (default: the 2 field-level-adjudicated ones)",
    )
    p_c.add_argument("--limit", type=int, default=None, help="cap on candidate fills processed")

    p_a = sub.add_parser("batch-a", help="Fuel A: cross-DB strict fill")
    p_a.add_argument("--apply", action="store_true", help="perform real writes (default: dry-run)")
    p_a.add_argument(
        "--limit", type=int, default=None, help="cap on WRITE-verdict pairs processed (validation sample)"
    )

    p_r = sub.add_parser("rollback", help="revert a batch by id")
    p_r.add_argument("--batch-id", required=True)

    sub.add_parser("measure", help="print after-state coverage + corroboration delta")

    return p


async def _dispatch(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(dsn=_local_dsn())
    try:
        if args.command == "manifest":
            excl = await build_manifest_exclusions(conn)
            _print_manifest(excl)
        elif args.command == "census":
            await run_census(conn)
        elif args.command == "batch-c":
            await run_batch_c(
                conn, apply=args.apply, exclude_proposals=args.exclude_proposals, limit=args.limit
            )
        elif args.command == "batch-a":
            await run_batch_a(conn, apply=args.apply, limit=args.limit)
        elif args.command == "rollback":
            await rollback_batch(conn, args.batch_id)
        elif args.command == "measure":
            await run_measure(conn)
        else:  # pragma: no cover - argparse guards this
            raise ValueError(f"unknown command {args.command!r}")
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        asyncio.run(_dispatch(args))
    except Exception:
        logger.exception("intake_identity_backfill: %s failed", args.command)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
