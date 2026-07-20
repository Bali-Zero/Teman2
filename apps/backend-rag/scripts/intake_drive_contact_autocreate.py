"""CLIENTI-NON-A-CRM — drive contact auto-create (wave 1).

Census v2.1 implementation of the design spec
``research/operations/2026-07-19-drive-contact-autocreate-design.md`` (v3 +
gate round-3 fixes). Read-only: census mode touches ONLY temp state in the
session; apply/rollback are honest NO-GO stubs until the adversarial re-gate
returns GO-WAVE-1.

The candidate predicate lives HERE, once, in Python
(:func:`classify_perimeter`): census and the future apply mode share it by
construction (v3 §3 — apply re-runs the FULL predicate per candidate in-TX).
Creation validity comes from
``backend.services.intake.drive_autocreate_validity`` (v3 §6), whose
projections mirror ``routing.py`` verbatim (round-3 R3-4).

Round-3 gate fixes carried here:
- R3-1: the drive-root ALLOWLIST is part of the predicate, not commentary.
- R3-2: perimeter = LATEST proposal per queue; the manifest binds proposal
  ids, queue ids, blob hashes, per-doc fields fingerprints, the validate
  branch, thresholds, allowlist and code version — not just sid|name.
- R3-3: STRICT validate branch rejects missing/null stages too (no fail-open).
- R3-8: the book is ATTESTED local (current_database + server locality)
  before anything runs — census and apply alike.
- R3-9: the evidence bar is DECLARED single-document (name + valid id +
  strict-validated extraction from one doc); multi-doc disagreement
  quarantines, agreement is not pretended to add confirmation.
- R3-10: name clustering runs on ELIGIBLE candidates only (post earlier
  gates) and only pairs spanning DIFFERENT sids count.
- R3-11: buckets are reported in execution order.

PII discipline (Law 2): stdout/report carry COUNTS, kinds, root labels and
digests only — never a name, id value or phone.

Run (census):
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/intake_drive_contact_autocreate.py --census
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import asyncpg

from backend.services.intake.drive_autocreate_validity import (
    VALIDATORS,
    canonical_alnum,
    valid_name,
)

logger = logging.getLogger("zantara.intake.drive_autocreate")

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
APPROVED_DATABASE = "nuzantara_dev"

# doc_type -> (sid kind, extract-field key). KTP/NIK is deliberately ABSENT:
# wave 1 excludes it entirely (v3 §4).
DOCTYPE_TO_KIND: dict[str, tuple[str, str]] = {
    "passport": ("passport", "passport_no"),
    "visa": ("passport", "passport_no"),
    "kitas": ("kitas", "kitas_no"),
    "npwp": ("npwp", "npwp_number"),
}

# Declared client-service Drive roots (R3-1): observed 2026-07-19, all Bali
# Zero staff/service folders. A drive doc whose root is NOT here is excluded
# by the PREDICATE — the allowlist is enforceable state, not a comment.
DRIVE_ROOT_ALLOWLIST = frozenset(
    {
        "DATA ADI",
        "PEMEGANG KITAS",
        "EXTEND VISA",
        "ADITYA",
        "MEGI",
        "NOVI",
        "YANTI",
        "YUDI",
        "LIA",
        "DINOK",
        "DAVID",
        "YOYOK",
        "MERP",
        "VISA OFFSHORE",
        "gendu",
        "gendu (Selective Sync Conflict 1)",
    }
)

EXISTING_NAME_SIM = 0.45  # v2 B3 — candidate vs existing live client names
CROSS_SID_SIM = 0.60  # v2 B4 — candidate-vs-candidate name clustering
VALIDATE_COVERAGE_STRICT = 0.50  # branch threshold (v3 §6)

# Bucket names in PREDICATE EXECUTION ORDER (R3-11) — first match wins.
EXECUTION_ORDER = [
    "C_discard",
    "B_incomplete",
    "B_nondrive_provenance",
    "B_root_not_allowlisted",
    "ledgered_skip",
    "B_id_already_exists",
    "B_npwp_person_ambiguous",
    "B_name_conflict",
    "B_validate_not_true",
    "B_validate_false",
    "B_possible_existing_person",
    "B_multisid_or_cluster",
    "B_live_gate_would_flag",
    "A_effective",
]

# Latest proposal per queue (R3-2): an older superseded proposal must not
# resurrect a doc the pipeline has since moved on.


def _sql_field_proj(key_expr: str) -> str:
    """Fail-closed extraction of one extract-field value (R10-4a).

    An object yields ONLY its ``value`` member (NULL when absent), a scalar
    string/number yields its own text, and every other shape — array, bool,
    null, missing key — is NULL. The previous oracle
    ``COALESCE(fl->k->>'value', fl->>k)`` SERIALIZED a value-less object to
    text, and the digit-stripping npwp validator can mint a "valid" SID out
    of ``{"confidence": 0.123456789012345}`` (→ 0123456789012345); a
    malformed name object likewise became a literal-JSON client name.
    Malformed shapes must never reach a validator: they fail closed here, in
    ONE projection shared by the census, the perimeter re-derive and both
    live name probes (divergence between census and probe was R9-2).

    ``key_expr`` is either a quoted literal key (``"'name'"``) or a bind
    placeholder (``"$2"``) — both are valid jsonb subscripts.

    R11-1: the ``value`` member itself must ALSO be scalar-typed —
    ``->>'value'`` SERIALIZES a nested object/array to JSON text
    (``{"value":{"label":"JOHN SMITH"}}`` → ``{"label": "JOHN SMITH"}``),
    and the name validator accepts any letter-bearing text, so a nested
    shape could mint a client whose full_name is literal JSON.
    """
    f = f"fl->{key_expr}"
    v = f"{f}->'value'"
    return (
        f"CASE jsonb_typeof({f}) "
        f"WHEN 'object' THEN ("
        f"CASE jsonb_typeof({v}) "
        f"WHEN 'string' THEN {f}->>'value' "
        f"WHEN 'number' THEN {f}->>'value' "
        "ELSE NULL END) "
        f"WHEN 'string' THEN fl->>{key_expr} "
        f"WHEN 'number' THEN fl->>{key_expr} "
        "ELSE NULL END"
    )


PERIMETER_SQL = f"""
SELECT p.id AS pid,
       q.id AS qid,
       p.status,
       COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') AS doc_type,
       q.blob_hash,
       q.source_ref,
       split_part(COALESCE(q.source_path, ''), '/', 1) AS root_segment,
       {_sql_field_proj("'name'")} AS raw_name,
       {_sql_field_proj("$2")} AS raw_id,
       q.stage_output->'validate'->>'valid' AS validate_valid,
       (q.stage_output ? 'validate') AS has_validate,
       (q.stage_output->'extract'->'fields')::text AS fields_text
FROM (
    SELECT DISTINCT ON (queue_id) *
    FROM document_routing_proposal
    ORDER BY queue_id, id DESC
) p
JOIN intake_queue q ON q.id = p.queue_id
CROSS JOIN LATERAL (SELECT q.stage_output->'extract'->'fields') AS t(fl)
WHERE p.status IN ('review_pending', 'quarantine')
  AND q.stage_output->'extract'->'fields' IS NOT NULL
  AND COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') = $1
"""

# Existing strong-id key book. Passport/kitas use routing._normalize_id's OWN
# projection ([\s.-/] strip — R3-4: NOT a strip-everything class); npwp uses
# the ASCII digit class. Companies npwp column resolved at runtime.
CLIENT_KEYS_SQL = r"""
SELECT 'passport:' || upper(regexp_replace(passport_number, '[\s.\-/]', '', 'g')) AS k
FROM clients
WHERE passport_number IS NOT NULL
  AND length(regexp_replace(passport_number, '[\s.\-/]', '', 'g')) >= 1
UNION
SELECT 'kitas:' || upper(regexp_replace(kitas_number, '[\s.\-/]', '', 'g'))
FROM clients
WHERE kitas_number IS NOT NULL
  AND length(regexp_replace(kitas_number, '[\s.\-/]', '', 'g')) >= 1
UNION
SELECT 'npwp:' || regexp_replace(npwp, '[^0-9]', '', 'g')
FROM clients
WHERE npwp IS NOT NULL
  AND length(regexp_replace(npwp, '[^0-9]', '', 'g')) >= 1
"""


@dataclass
class Doc:
    pid: int
    qid: int
    status: str
    kind: str
    blob_hash: str | None
    is_drive: bool
    root_segment: str
    name: str | None
    canonical: str | None
    has_validate: bool
    validate_valid: str | None
    fields_fp: str
    # Pre-bound canonical length (passport kind only) — feeds the histogram
    # the re-gate reviews to see what the 6-9 bound cuts.
    raw_len: int | None = None
    bucket: str | None = None


@dataclass
class CensusResult:
    buckets: Counter = field(default_factory=Counter)
    per_kind_a: Counter = field(default_factory=Counter)
    a_sids: dict[str, str] = field(default_factory=dict)  # sid -> name
    a_docs: list[Doc] = field(default_factory=list)
    validate_coverage: float = 0.0
    validate_branch: str = ""
    passport_len_hist: Counter = field(default_factory=Counter)
    roots: Counter = field(default_factory=Counter)
    manifest_digest: str = ""
    companies_npwp_col: str | None = None
    ledgered_skipped: int = 0


def _code_version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


async def attest_local_book(conn: asyncpg.Connection) -> None:
    """Refuse to run against anything but the approved LOCAL book (R3-8).

    ``--dsn``/env are conveniences, not authority: the program attests
    ``current_database()`` and server locality (unix socket or loopback)
    before touching anything, census and apply alike.
    """
    dbname = await conn.fetchval("SELECT current_database()")
    if dbname != APPROVED_DATABASE:
        raise SystemExit(
            f"ATTESTATION FAILED: current_database()={dbname!r}, "
            f"approved={APPROVED_DATABASE!r} — refusing to run."
        )
    addr = await conn.fetchval("SELECT inet_server_addr()::text")
    if addr is not None and addr.split("/")[0] not in {"127.0.0.1", "::1"}:
        raise SystemExit(
            f"ATTESTATION FAILED: server address {addr!r} is not local — refusing to run."
        )


async def _resolve_companies_npwp_col(conn: asyncpg.Connection) -> str | None:
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'companies' AND column_name IN ('npwp_company', 'npwp')
        """
    )
    cols = {r["column_name"] for r in rows}
    if "npwp_company" in cols:
        return "npwp_company"
    if "npwp" in cols:
        return "npwp"
    return None


async def _ledgered_keys(conn: asyncpg.Connection) -> set[str]:
    """Tombstoned keys from intake_identity_ledger, if it exists (v2 B10)."""
    exists = await conn.fetchval("SELECT to_regclass('intake_identity_ledger') IS NOT NULL")
    if not exists:
        return set()
    rows = await conn.fetch("SELECT kind, canonical_value FROM intake_identity_ledger")
    return {f"{r['kind']}:{r['canonical_value']}" for r in rows}


def _doc_from_row(r: object, kind: str) -> Doc:
    canonical = VALIDATORS[kind](r["raw_id"])  # type: ignore[index]
    raw_canon = canonical_alnum(r["raw_id"]) if kind == "passport" else None  # type: ignore[index]
    return Doc(
        pid=r["pid"],  # type: ignore[index]
        qid=r["qid"],  # type: ignore[index]
        status=r["status"],  # type: ignore[index]
        kind=kind,
        blob_hash=r["blob_hash"],  # type: ignore[index]
        is_drive=(r["source_ref"] or "").startswith("drive:"),  # type: ignore[index]
        root_segment=r["root_segment"] or "",  # type: ignore[index]
        name=valid_name(r["raw_name"]),  # type: ignore[index]
        canonical=canonical,
        has_validate=r["has_validate"],  # type: ignore[index]
        validate_valid=r["validate_valid"],  # type: ignore[index]
        fields_fp=hashlib.sha256(
            (r["fields_text"] or "").encode()  # type: ignore[index]
        ).hexdigest(),
        raw_len=len(raw_canon) if raw_canon else None,
    )


async def load_perimeter(conn: asyncpg.Connection) -> list[Doc]:
    docs: list[Doc] = []
    for doc_type, (kind, id_key) in DOCTYPE_TO_KIND.items():
        rows = await conn.fetch(PERIMETER_SQL, doc_type, id_key)
        for r in rows:
            docs.append(_doc_from_row(r, kind))
    return docs


# Single-qid re-derivation for the apply-time locked recheck (R6-4): same
# projection as PERIMETER_SQL, latest proposal for ONE queue row, no status
# filter (the comparison against the census Doc carries the expectation).
PERIMETER_ONE_SQL = f"""
SELECT p.id AS pid,
       q.id AS qid,
       p.status,
       COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') AS doc_type,
       q.blob_hash,
       q.source_ref,
       split_part(COALESCE(q.source_path, ''), '/', 1) AS root_segment,
       {_sql_field_proj("'name'")} AS raw_name,
       {_sql_field_proj("$2")} AS raw_id,
       q.stage_output->'validate'->>'valid' AS validate_valid,
       (q.stage_output ? 'validate') AS has_validate,
       (q.stage_output->'extract'->'fields')::text AS fields_text
FROM document_routing_proposal p
JOIN intake_queue q ON q.id = p.queue_id
CROSS JOIN LATERAL (SELECT q.stage_output->'extract'->'fields') AS t(fl)
WHERE q.id = $1
ORDER BY p.id DESC
LIMIT 1
"""


# R7-2 / R8-1: scoped LIVE re-run of the census NAME gates. Census semantics
# being mirrored (classify_perimeter): B_name_conflict = the SAME sid carries
# more than one distinct valid name; B_multisid_or_cluster = the same (or
# trigram>=CROSS_SID_SIM similar) name appears on a DIFFERENT sid. Two arms:
# (A) id-keyed — live docs of this kind whose id canonicalizes to the
# candidate's canonical, whatever their name; (B) name-keyed — live identity
# docs whose collapsed name equals OR is trigram-similar to the candidate's.
# SQL name projection mirrors valid_name exactly: upper → collapse
# whitespace → btrim (R8-1: btrim BEFORE collapse missed tab/newline edges),
# over the fail-closed field oracle (R10-4a).
_SQL_NAME_PROJ = (
    "btrim(regexp_replace(upper(" + _sql_field_proj("'name'") + r"), '\s+', ' ', 'g'))"
)

# R10-1: NO status filter on either probe — a conflicting doc does not stop
# being a conflict because it advanced to auto_routed/routed; the previous
# review-only window let a same-sid different-name doc get auto-attached and
# then vanish from BOTH the apply-time gates and the delayed verifier.
SID_NAME_PROBE_SQL = f"""
SELECT q.blob_hash,
       {_sql_field_proj("'name'")} AS raw_name,
       {_sql_field_proj("$2")} AS raw_id
FROM (
    SELECT DISTINCT ON (queue_id) *
    FROM document_routing_proposal
    ORDER BY queue_id, id DESC
) p
JOIN intake_queue q ON q.id = p.queue_id
CROSS JOIN LATERAL (SELECT q.stage_output->'extract'->'fields') AS t(fl)
WHERE COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') = ANY($1::text[])
  AND ({_sql_field_proj("$2")}) IS NOT NULL
"""

# R9-2: Arm B must read each row's OWN raw id through the EXACT census
# projection (now the shared fail-closed oracle — R10-4a). The previous
# consumer parsed fields_json in Python and returned None for an object with
# no 'value' member while the census minted a SID from it: the same row
# formed a census SID but vanished from Arm B, letting a cluster through.
# The id keys are a closed code-constant set (DOCTYPE_TO_KIND), never input.
_ARM_B_ID_KEYS = sorted({ik for _k, ik in DOCTYPE_TO_KIND.values()})
_ARM_B_ID_PROJ = ",\n       ".join(
    f"{_sql_field_proj(chr(39) + ik + chr(39))} AS raw_id_{ik}"
    for ik in _ARM_B_ID_KEYS
)

NAME_CLUSTER_PROBE_SQL = f"""
SELECT q.blob_hash,
       COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') AS doc_type,
       {_sql_field_proj("'name'")} AS raw_name,
       {_ARM_B_ID_PROJ}
FROM (
    SELECT DISTINCT ON (queue_id) *
    FROM document_routing_proposal
    ORDER BY queue_id, id DESC
) p
JOIN intake_queue q ON q.id = p.queue_id
CROSS JOIN LATERAL (SELECT q.stage_output->'extract'->'fields') AS t(fl)
WHERE COALESCE(p.entity_resolution->>'doc_type', p.routing->>'doc_type') = ANY($2::text[])
  AND ({_SQL_NAME_PROJ} = $1 OR similarity({_SQL_NAME_PROJ}, $1) >= $3)
"""


async def _live_name_gates(
    conn: asyncpg.Connection, kind: str, canonical: str, entry: dict
) -> str | None:
    """Re-run the census NAME gates against the LIVE latest proposals for
    this one candidate (R7-2/R8-1). Returns a skip reason or None.

    Arm A (census B_name_conflict, scoped): any live doc whose same-kind id
    canonicalizes to THIS canonical but carries a DIFFERENT valid name.
    Arm B (census B_multisid_or_cluster, scoped): any live identity doc
    whose name equals or is trigram>=CROSS_SID_SIM similar to the
    candidate's, under a DIFFERENT sid (any kind)."""
    kind_doc_types = [dt for dt, (k, _ik) in DOCTYPE_TO_KIND.items() if k == kind]
    id_key = dict(DOCTYPE_TO_KIND.values())[kind]

    rows = await conn.fetch(SID_NAME_PROBE_SQL, kind_doc_types, id_key)
    for r in rows:
        if VALIDATORS[kind](r["raw_id"]) != canonical:
            continue
        nm = valid_name(r["raw_name"])
        if nm is not None and nm != entry["name"]:
            return "name_conflict_appeared"

    all_doc_types = list(DOCTYPE_TO_KIND)
    rows = await conn.fetch(
        NAME_CLUSTER_PROBE_SQL, entry["name"], all_doc_types, CROSS_SID_SIM
    )
    for r in rows:
        mapped = DOCTYPE_TO_KIND.get(r["doc_type"])
        if not mapped:
            continue
        r_kind, r_id_key = mapped
        # R9-2: the row's own id comes from the SQL census projection, never
        # from a Python re-parse with different missing-'value' semantics.
        other = VALIDATORS[r_kind](r[f"raw_id_{r_id_key}"])
        if other and (r_kind != kind or other != canonical):
            return "cluster_appeared"
    return None


async def _lock_evidence_rows(conn: asyncpg.Connection, docs: list[Doc]) -> None:
    """Claim ALL evidence rows in the GLOBAL lock order (R8-6): every queue
    row first, ascending qid, THEN every latest proposal row, same order.
    Reroute and rollback follow the same queues-then-proposals order, so the
    paths cannot deadlock each other."""
    for d in sorted(docs, key=lambda x: x.qid):
        await conn.execute(
            "SELECT id FROM intake_queue WHERE id = $1 FOR UPDATE", d.qid
        )
    for d in sorted(docs, key=lambda x: x.qid):
        await conn.execute(
            "SELECT id FROM document_routing_proposal WHERE queue_id = $1 "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE",
            d.qid,
        )


async def _locked_evidence_matches(conn: asyncpg.Connection, d: Doc) -> bool:
    """Re-derive the FULL Doc through the census parser (rows already locked
    by _lock_evidence_rows); the create proceeds only if every
    predicate-bearing field is byte-identical to the census evidence (R6-4 —
    id/status/fingerprint alone left validate state, provenance, root, kind
    and blob unchecked)."""
    kind_to_id_key = dict(DOCTYPE_TO_KIND.values())
    r = await conn.fetchrow(PERIMETER_ONE_SQL, d.qid, kind_to_id_key[d.kind])
    if r is None:
        return False
    mapped = DOCTYPE_TO_KIND.get(r["doc_type"])
    if not mapped or mapped[0] != d.kind:
        return False
    fresh = _doc_from_row(r, d.kind)
    return (
        fresh.pid == d.pid
        and fresh.status == d.status
        and fresh.blob_hash == d.blob_hash
        and fresh.is_drive == d.is_drive
        and fresh.root_segment == d.root_segment
        and fresh.name == d.name
        and fresh.canonical == d.canonical
        and fresh.has_validate == d.has_validate
        and fresh.validate_valid == d.validate_valid
        and fresh.fields_fp == d.fields_fp
    )


async def _names_similar_to_existing(
    conn: asyncpg.Connection, names: set[str], threshold: float
) -> set[str]:
    """Candidate names trigram-similar to ANY live client full_name (v2 B3)."""
    if not names:
        return set()
    rows = await conn.fetch(
        """
        WITH cand(name) AS (SELECT unnest($1::text[]))
        SELECT DISTINCT cand.name
        FROM cand
        JOIN clients c
          ON c.deleted_at IS NULL
         AND c.full_name IS NOT NULL
         AND similarity(upper(c.full_name), cand.name) >= $2
        """,
        list(names),
        threshold,
    )
    return {r["name"] for r in rows}


async def _similar_name_pairs(
    conn: asyncpg.Connection, names: set[str], threshold: float
) -> set[frozenset[str]]:
    """Distinct-name pairs trigram-similar >= threshold."""
    if len(names) < 2:
        return set()
    rows = await conn.fetch(
        """
        WITH cand(name) AS (SELECT unnest($1::text[]))
        SELECT a.name AS n1, b.name AS n2
        FROM cand a
        JOIN cand b ON a.name < b.name
        WHERE similarity(a.name, b.name) >= $2
        """,
        list(names),
        threshold,
    )
    return {frozenset((r["n1"], r["n2"])) for r in rows}


def _clustered_names(
    eligible_sid_names: dict[str, set[str]],
    similar_pairs: set[frozenset[str]],
) -> set[str]:
    """Names that collide across DIFFERENT eligible sids (R3-10).

    Two flavours, both requiring sid diversity:
    - exact: the same name attached to >=2 eligible sids;
    - fuzzy: a trigram pair whose two names belong to different eligible sids.
    A name similar only to itself (or to names of the SAME sid — e.g. two
    spellings on the same passport) does not cluster.
    """
    name_to_sids: dict[str, set[str]] = defaultdict(set)
    for sid, names in eligible_sid_names.items():
        for n in names:
            name_to_sids[n].add(sid)

    clustered = {n for n, sids in name_to_sids.items() if len(sids) > 1}
    for pair in similar_pairs:
        a, b = tuple(pair)
        if name_to_sids.get(a, set()) - name_to_sids.get(b, set()) or (
            name_to_sids.get(b, set()) - name_to_sids.get(a, set())
        ):
            clustered |= {a, b}
    return clustered


def classify_perimeter(
    docs: list[Doc],
    *,
    existing_keys: set[str],
    ledgered: set[str],
    similar_to_existing: set[str],
    cluster_names: set[str] | None,
    validate_strict: bool,
) -> CensusResult:
    """The shared candidate predicate — census and apply both run THIS.

    First-match-wins in EXECUTION_ORDER. ``cluster_names`` is computed on the
    ELIGIBLE candidate set between the pre-pass (``cluster_names=None``) and
    the final pass (R3-10) — never on raw perimeter names.

    Evidence bar (R3-9, declared): ONE strictly-validated document carrying a
    coherent name + creation-valid strong id is sufficient; duplicate blobs
    neither confirm nor conflict (agreement is counted over DISTINCT blobs
    only, and agreement is not treated as extra evidence).
    """
    res = CensusResult()

    # sid -> distinct-blob name sets (conflict detection, v2 B2).
    sid_blob_names: dict[str, dict[str | None, set[str]]] = defaultdict(dict)
    for d in docs:
        if d.canonical and d.name:
            sid = f"{d.kind}:{d.canonical}"
            sid_blob_names[sid].setdefault(d.blob_hash, set()).add(d.name)
    sid_names: dict[str, set[str]] = {
        sid: set().union(*by_blob.values()) for sid, by_blob in sid_blob_names.items()
    }

    for d in docs:
        sid = f"{d.kind}:{d.canonical}" if d.canonical else None
        if d.is_drive:
            res.roots[d.root_segment] += 1
        if d.kind == "passport" and d.raw_len is not None:
            res.passport_len_hist[d.raw_len] += 1

        if sid is None and d.name is None:
            d.bucket = "C_discard"
        elif sid is None or d.name is None:
            d.bucket = "B_incomplete"
        elif not d.is_drive:
            d.bucket = "B_nondrive_provenance"
        elif d.root_segment not in DRIVE_ROOT_ALLOWLIST:
            d.bucket = "B_root_not_allowlisted"
        elif sid in ledgered:
            d.bucket = "ledgered_skip"
        elif sid in existing_keys:
            d.bucket = "B_id_already_exists"
        elif d.kind == "npwp":
            # R10-4b: a bare NPWP document is person/company AMBIGUOUS by
            # routing's own semantics — absence from the current company book
            # does not prove personhood, so an npwp sid never mints a person
            # card in wave 1. Review is the correct terminal.
            d.bucket = "B_npwp_person_ambiguous"
        elif len(sid_names.get(sid, set())) > 1:
            d.bucket = "B_name_conflict"
        elif validate_strict and d.validate_valid != "true":
            # R3-3: STRICT means strictly true — a MISSING/NULL validate stage
            # is a rejection, not a pass-through.
            d.bucket = "B_validate_not_true"
        elif not validate_strict and d.validate_valid == "false":
            d.bucket = "B_validate_false"
        elif d.name in similar_to_existing:
            d.bucket = "B_possible_existing_person"
        elif cluster_names is not None and d.name in cluster_names:
            d.bucket = "B_multisid_or_cluster"
        else:
            d.bucket = "A_effective"
            res.a_sids[sid] = d.name
            res.a_docs.append(d)

        res.buckets[d.bucket] += 1

    for sid in res.a_sids:
        res.per_kind_a[sid.split(":", 1)[0]] += 1
    res.ledgered_skipped = res.buckets.get("ledgered_skip", 0)
    return res


def _file_sha256(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return "unreadable"


def _build_manifest(
    res: CensusResult,
    *,
    validate_branch: str,
    validate_coverage: float,
    companies_col: str | None,
) -> tuple[str, dict]:
    """Candidate manifest + digest (R3-2 / round-4 R4-2).

    Binds WHAT would be created from WHICH evidence under WHICH gates and
    WHICH exact code: per-document TUPLES ``(pid,qid,status,blob,ffp)`` (not
    separately-sorted pools — a status flip or evidence reshuffle must change
    the digest) and the sha256 of THIS script's and the validator's exact
    bytes (a dirty-worktree git SHA alone binds nothing — R4-2).
    """
    import backend.services.intake.auto_attach as _auto_attach_mod
    import backend.services.intake.client_enricher as _enricher_mod
    import backend.services.intake.drive_autocreate_validity as _validity_mod
    import backend.services.intake.routing as _routing_mod
    import backend.services.intake.stages as _stages_mod
    import backend.services.intake.worker as _worker_mod
    import backend.services.intake.writer as _writer_mod

    per_sid: dict[str, dict] = {}
    for d in res.a_docs:
        sid = f"{d.kind}:{d.canonical}"
        entry = per_sid.setdefault(sid, {"name": res.a_sids[sid], "docs": []})
        entry["docs"].append(
            (d.pid, d.qid, d.status, d.blob_hash or "", d.fields_fp)
        )

    header = {
        "validate_branch": validate_branch,
        "validate_coverage": round(validate_coverage, 4),
        "existing_name_sim": EXISTING_NAME_SIM,
        "cross_sid_sim": CROSS_SID_SIM,
        "root_allowlist": sorted(DRIVE_ROOT_ALLOWLIST),
        "companies_npwp_column": companies_col,
        "git_head": _code_version(),
        "script_sha256": _file_sha256(os.path.abspath(__file__)),
        "validator_sha256": _file_sha256(_validity_mod.__file__),
        # R6-5: the digest must bind every load-bearing dependency's exact
        # bytes, not just this script — the auto-attach suppression lives in
        # routing.py and the strong-id lock in client_enricher.py; editing
        # either must invalidate an approved manifest.
        "routing_sha256": _file_sha256(_routing_mod.__file__),
        "client_enricher_sha256": _file_sha256(_enricher_mod.__file__),
        # R10-5: drain transitions and dead-queue behavior (worker.py),
        # LEVA gate concordance (auto_attach.py) and commit semantics
        # (writer.py) are equally load-bearing to the safety proof — a
        # change to any of them must invalidate an approved digest too.
        "worker_sha256": _file_sha256(_worker_mod.__file__),
        "auto_attach_sha256": _file_sha256(_auto_attach_mod.__file__),
        "writer_sha256": _file_sha256(_writer_mod.__file__),
        # R11-3: stages.py is the dispatcher that hands a drained queue to
        # route_stage — a stubbed/stale dispatcher drains without producing
        # the proposal the freshness check requires. Bind it too.
        "stages_sha256": _file_sha256(_stages_mod.__file__),
    }
    lines = [json.dumps(header, sort_keys=True, ensure_ascii=False)]
    for sid in sorted(per_sid):
        e = per_sid[sid]
        doc_tuples = ";".join(
            ":".join(str(x) for x in t) for t in sorted(e["docs"])
        )
        lines.append("|".join([sid, e["name"], doc_tuples]))
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return digest, header


async def _live_gate_preflight(
    conn: asyncpg.Connection, res: CensusResult
) -> None:
    """R11-2: census/apply symmetry pre-flight. The census cluster pass runs
    on ELIGIBLE candidates only (pre.a_sids), but the APPLY-time probes scan
    EVERY latest proposal — including npwp docs parked in
    B_npwp_person_ambiguous and any non-candidate proposal carrying a
    colliding name/sid. A candidate the live gates would skip TODAY must not
    be sold by the manifest as a would-be create: run the exact apply-time
    gates per candidate now and demote failures in place. (Apply still
    re-runs them under lock — this is manifest honesty, not the gate.)"""
    for sid in sorted(res.a_sids):
        kind, canon = sid.split(":", 1)
        gate = await _live_name_gates(conn, kind, canon, {"name": res.a_sids[sid]})
        if gate:
            del res.a_sids[sid]
            demoted = [d for d in res.a_docs if f"{d.kind}:{d.canonical}" == sid]
            res.a_docs = [
                d for d in res.a_docs if f"{d.kind}:{d.canonical}" != sid
            ]
            for d in demoted:
                d.bucket = "B_live_gate_would_flag"
            res.buckets["A_effective"] -= len(demoted)
            res.buckets["B_live_gate_would_flag"] += len(demoted)
    res.per_kind_a = Counter(k.split(":", 1)[0] for k in res.a_sids)


async def _compute_census(conn: asyncpg.Connection) -> dict:
    """Full census pipeline — shared verbatim by census mode and apply-time
    manifest re-derivation (R5-1: the apply consumer must re-derive the SAME
    digest from the SAME code path, never a parallel reimplementation)."""
    docs = await load_perimeter(conn)

    with_validate = sum(1 for d in docs if d.has_validate)
    coverage = with_validate / len(docs) if docs else 0.0
    validate_strict = coverage >= VALIDATE_COVERAGE_STRICT

    existing_keys = {r["k"] for r in await conn.fetch(CLIENT_KEYS_SQL) if r["k"]}
    comp_col = await _resolve_companies_npwp_col(conn)
    if comp_col:
        comp_rows = await conn.fetch(
            f"""
            SELECT 'npwp:' || regexp_replace({comp_col}, '[^0-9]', '', 'g') AS k
            FROM companies
            WHERE {comp_col} IS NOT NULL
              AND length(regexp_replace({comp_col}, '[^0-9]', '', 'g')) >= 1
            """
        )
        existing_keys |= {r["k"] for r in comp_rows if r["k"]}

    ledgered = await _ledgered_keys(conn)

    # PRE-PASS (R3-10): find the eligible candidate set with NO name-based
    # exclusions, so trigram gates run on candidates only — not on
    # evidence already discarded by validity/provenance/key gates.
    pre = classify_perimeter(
        docs,
        existing_keys=existing_keys,
        ledgered=ledgered,
        similar_to_existing=set(),
        cluster_names=None,
        validate_strict=validate_strict,
    )
    eligible_names = set(pre.a_sids.values())
    similar_to_existing = await _names_similar_to_existing(
        conn, eligible_names, EXISTING_NAME_SIM
    )

    # Cluster on the FULL post-hard-gate eligible set (round-4 R4-3):
    # trigram similarity is not transitive — if A~existing and A~B
    # (different sid) but B!~existing, dropping A before pairing would let
    # B into A-effective although B is exactly the renewed-id/name-variant
    # risk. The bucket ORDER still sends A to possible_existing and B to
    # multisid_or_cluster.
    eligible_sid_names: dict[str, set[str]] = defaultdict(set)
    for sid, name in pre.a_sids.items():
        eligible_sid_names[sid].add(name)
    pairs = await _similar_name_pairs(conn, eligible_names, CROSS_SID_SIM)
    cluster_names = _clustered_names(eligible_sid_names, pairs)

    res = classify_perimeter(
        docs,
        existing_keys=existing_keys,
        ledgered=ledgered,
        similar_to_existing=similar_to_existing,
        cluster_names=cluster_names,
        validate_strict=validate_strict,
    )
    res.validate_coverage = coverage
    res.validate_branch = (
        "STRICT valid IS TRUE"
        if validate_strict
        else "ABSENT-BY-CONSTRUCTION (only explicit valid=false excludes)"
    )
    res.companies_npwp_col = comp_col

    await _live_gate_preflight(conn, res)

    digest, manifest_header = _build_manifest(
        res,
        validate_branch=res.validate_branch,
        validate_coverage=coverage,
        companies_col=comp_col,
    )

    return {
        "docs": docs,
        "pre": pre,
        "res": res,
        "digest": digest,
        "manifest_header": manifest_header,
        "coverage": coverage,
        "validate_strict": validate_strict,
        "existing_keys": existing_keys,
        "similar_to_existing": similar_to_existing,
        "cluster_names": cluster_names,
        "comp_col": comp_col,
        "ledgered": ledgered,
    }


async def run_census(dsn: str, out_json: str | None) -> int:
    conn = await asyncpg.connect(dsn)
    try:
        await attest_local_book(conn)
        c = await _compute_census(conn)
        docs, pre, res = c["docs"], c["pre"], c["res"]
        coverage, digest, manifest_header = c["coverage"], c["digest"], c["manifest_header"]
        similar_to_existing, cluster_names = c["similar_to_existing"], c["cluster_names"]
        comp_col, existing_keys, ledgered = c["comp_col"], c["existing_keys"], c["ledgered"]

        report = {
            "perimeter_docs": len(docs),
            "validate_stage_coverage": round(coverage, 4),
            "validate_branch": res.validate_branch,
            "companies_npwp_column": comp_col,
            "existing_key_book_size": len(existing_keys),
            "ledgered_keys": len(ledgered),
            # R3-11: execution order, not frequency order.
            "buckets_docs_execution_order": {
                b: res.buckets.get(b, 0) for b in EXECUTION_ORDER
            },
            "A_effective_contacts": len(res.a_sids),
            "A_per_kind": dict(res.per_kind_a),
            "eligible_prepass_contacts": len(pre.a_sids),
            "names_similar_to_existing": len(similar_to_existing),
            "clustered_names": len(cluster_names),
            "passport_canonical_len_hist": {
                str(k): v for k, v in sorted(res.passport_len_hist.items())
            },
            "drive_roots": dict(res.roots.most_common()),
            "manifest_header": manifest_header,
            "manifest_digest": digest,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if out_json:
            with open(out_json, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
            logger.info("census report written to %s", out_json)
        return 0
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Apply / rollback (built for the round-6 gate; ARMED only by GO-WAVE-1:
# killswitch env + --manifest digest are the two independent authorities)
# ---------------------------------------------------------------------------

KILLSWITCH_ENV = "INTAKE_DRIVE_AUTOCREATE_ENABLED"
HARD_BATCH_CAP = 200
PIPELINE_TAG = "v2.3-drive-autocreate"  # matches routing's suppression set


def _batch_uid(batch_id: str) -> str:
    """Last dash-segment of a batch id (the uuid4-hex8 uniqueness carrier)."""
    return batch_id.rsplit("-", 1)[-1][:8]


def run_tag_for(batch_id: str) -> str:
    """Batch-qualified reroute tag (R10-2a), fitted to VARCHAR(32).

    ``pipeline_version`` is VARCHAR(32) on both intake_queue and
    document_routing_proposal, so the qualifier is the batch id's terminal
    uuid4-hex8 segment, not the full id: ``v2.3-drive-autocreate:<uid8>``
    (30 chars). Distinguishing invocations needs uniqueness, not
    reversibility — the ledger's batch_id column keeps the full value.
    """
    return f"{PIPELINE_TAG}:{_batch_uid(batch_id)}"


def rb_tag_for(batch_id: str) -> str:
    """Rollback-reset variant of :func:`run_tag_for` (``r`` prefix, 31 chars) —
    a rollback retry must recognize its own earlier resets as distinct from
    the batch's forward reroute generation."""
    return f"{PIPELINE_TAG}:r{_batch_uid(batch_id)}"
DRIVE_ORIGIN = "drive-intake"
AUTOCREATE_CREATED_BY = "system:drive-intake-autocreate"
DRAIN_POLL_SECONDS = 300

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS intake_identity_ledger (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    canonical_value TEXT NOT NULL,
    full_name TEXT NOT NULL,
    client_id BIGINT,
    batch_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned','created','rerouted','rolled_back')),
    source_proposal_ids BIGINT[] NOT NULL,
    source_queue_ids BIGINT[] NOT NULL,
    blob_hashes TEXT[] NOT NULL,
    fields_fps TEXT[] NOT NULL,
    business_fingerprint TEXT,
    business_columns TEXT[],
    reroute_verified BOOLEAN NOT NULL DEFAULT FALSE,
    reroute_proposal_ids BIGINT[],
    guard_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, canonical_value)
)
"""

# Reroute contract — verbatim from scripts/intake_reprocess_backlog.py (m227/
# m248): supersede the LATEST proposal, reset the queue row at the validate
# stage, stage_output PRESERVED (the blobs are retention-evicted; the saved
# fields are the only copy).
SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE id = ANY($1::bigint[])
   AND status IN ('review_pending', 'quarantine')
RETURNING id, queue_id
"""
RESET_QUEUE_SQL = """
UPDATE intake_queue
   SET status           = 'validated',
       stage            = 'validate',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       last_error       = NULL,
       pipeline_version = $2,
       updated_at       = now()
 WHERE id = ANY($1::bigint[])
   AND status = 'done'
   AND (lease_owner IS NULL OR lease_expires_at < now())
"""
# ^ R7-4 fence: only settled rows (the drive backlog book is status='done',
# stage='route') with no ACTIVE worker lease may be reset — a fence miss
# shows up as a cardinality shortfall, which rolls the whole reroute TX back.

# R10-2b: a queue our reroute reset can exhaust its worker retries and land
# status='dead' (worker._fail) — the docs then never return to review.
# Rollback REVIVES such a queue (same SET as the reset, fence on 'dead');
# leaving it dead while reporting rollback success would be a silent loss.
REVIVE_DEAD_QUEUE_SQL = """
UPDATE intake_queue
   SET status           = 'validated',
       stage            = 'validate',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       last_error       = NULL,
       pipeline_version = $2,
       updated_at       = now()
 WHERE id = ANY($1::bigint[])
   AND status = 'dead'
"""

# Matcher-projection existence probes (routing's own SQL classes).
ID_ON_CLIENTS_SQL = {
    "passport": r"SELECT id FROM clients WHERE deleted_at IS NULL AND "
    r"UPPER(REGEXP_REPLACE(passport_number, '[\s.\-/]', '', 'g')) = $1 LIMIT 3",
    "kitas": r"SELECT id FROM clients WHERE deleted_at IS NULL AND "
    r"UPPER(REGEXP_REPLACE(kitas_number, '[\s.\-/]', '', 'g')) = $1 LIMIT 3",
    "npwp": "SELECT id FROM clients WHERE deleted_at IS NULL AND "
    "regexp_replace(COALESCE(npwp,''), '[^0-9]', '', 'g') = $1 LIMIT 3",
}


class _RerouteCardinality(RuntimeError):
    """A reroute step touched fewer rows than the lot requires (R7-4).

    Raised INSIDE the reroute transaction so supersede and reset roll back
    together — a freeze must never leave half-mutated proposals/queues."""


class _PostInsertGuard(RuntimeError):
    """A post-insert in-TX recheck failed for a NON-collision reason (R7-2:
    a similar client committed mid-candidate). Rolls the create back; the
    candidate is skipped, the batch continues."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class CollisionDetected(RuntimeError):
    """A strong-id key owner-count violation observed around a create.

    Raised INSIDE the create TX (rolls it back — nothing persists) or by the
    post-commit verify (created row stands but the batch freezes). A DB
    unique constraint cannot exist here — the live book already carries
    duplicate keys (the 62130 anomaly: 7 clients, one passport) — so the
    authority is detect-fast + freeze + ledger-reversible, and the residual
    two-uncommitted-writers window is caught by the post-commit re-count and
    the lot sweeps (R6-1). Carries NO canonical value (R6-8)."""

    def __init__(self, kind: str, owners: dict):
        self.kind = kind
        self.owners = owners
        super().__init__(f"collision kind={kind} owners={owners}")


def _batch_id() -> str:
    # R7-5: second-resolution timestamps collide across concurrent
    # invocations and make --rollback-batch ambiguous — suffix with a random
    # component so the rollback pointer is invocation-unique.
    from datetime import datetime, timezone

    return (
        "w1-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )


async def _business_columns(conn: asyncpg.Connection) -> list[str]:
    """Every clients column EXCEPT non-business bookkeeping (R3-7: the
    fingerprint must cover everything a human might edit — id/created_at/
    updated_at excluded; deleted_at INCLUDED so an archived card drifts)."""
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'clients'
          AND column_name NOT IN ('id', 'created_at', 'updated_at')
        ORDER BY column_name
        """
    )
    return [r["column_name"] for r in rows]


def _row_fingerprint(row: object, cols: list[str]) -> str:
    payload = {c: str(row[c]) for c in cols}  # type: ignore[index]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


async def _fk_references(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT kcu.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'clients' AND ccu.column_name = 'id'
        """
    )
    return [(r["table_name"], r["column_name"]) for r in rows]


async def _fk_sweep(
    conn: asyncpg.Connection, refs: list[tuple[str, str]], client_id: int
) -> list[str]:
    hits = []
    for table, col in refs:
        # identifiers come from information_schema, not user input
        exists = await conn.fetchval(
            f'SELECT EXISTS(SELECT 1 FROM "{table}" WHERE "{col}" = $1)', client_id
        )
        if exists:
            hits.append(f"{table}.{col}")
    return hits


async def _key_owner_count(
    conn: asyncpg.Connection, kind: str, canonical: str, comp_col: str | None
) -> int:
    rows = await conn.fetch(ID_ON_CLIENTS_SQL[kind], canonical)
    count = len(rows)
    if kind == "npwp" and comp_col:
        count += await conn.fetchval(
            f"SELECT count(*) FROM companies WHERE "
            f"regexp_replace(COALESCE({comp_col},''), '[^0-9]', '', 'g') = $1",
            canonical,
        )
    return count


async def _key_owners(
    conn: asyncpg.Connection, kind: str, canonical: str, comp_col: str | None
) -> dict:
    """Live owners of a canonical key: client ids + companies count. The
    canonical VALUE never leaves this function's arguments (R6-8)."""
    rows = await conn.fetch(ID_ON_CLIENTS_SQL[kind], canonical)
    owners = {"client_ids": sorted(r["id"] for r in rows), "companies": 0}
    if kind == "npwp" and comp_col:
        owners["companies"] = await conn.fetchval(
            f"SELECT count(*) FROM companies WHERE "
            f"regexp_replace(COALESCE({comp_col},''), '[^0-9]', '', 'g') = $1",
            canonical,
        )
    return owners


async def _sweep_keys(
    conn: asyncpg.Connection,
    keys: list[tuple[str, str]],
    comp_col: str | None,
    *,
    expect_max: int,
) -> list[dict]:
    """Duplicate sweep (R2-2/R3-5): every key must own at most ``expect_max``
    live rows. Violations carry kind + integer ids ONLY — the canonical
    strong-id value is PII and never enters a report (R6-8)."""
    bad = []
    for kind, canonical in keys:
        o = await _key_owners(conn, kind, canonical, comp_col)
        if len(o["client_ids"]) + o["companies"] > expect_max:
            bad.append(
                {
                    "kind": kind,
                    "client_ids": o["client_ids"],
                    "companies": o["companies"],
                }
            )
    return bad


WORKER_LABEL = "com.nuzantara.intake-worker"
_SHELL_INTERPRETER_BASENAMES = frozenset(
    {"bash", "sh", "zsh", "python", "python3", "python3.11", "python3.14"}
)
DEPLOY_ROOT_ENV = "INTAKE_DEPLOY_ROOT"
# Env that must NOT appear in the live daemon's environment: the stub
# drains without routing (R11-3), and the attach flags are armed in the
# BATCH process env only, never fleet-wide (SKILL arming pattern).
_FORBIDDEN_WORKER_ENV = (
    "INTAKE_WORKER_STUB",
    "INTAKE_AUTO_ATTACH_ENABLED",
    "INTAKE_NAMEID_AUTO_ATTACH_ENABLED",
    "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED",
)
_ATTESTED_DEPLOY_FILES = {
    "routing.py": "routing_sha256",
    "worker.py": "worker_sha256",
    "auto_attach.py": "auto_attach_sha256",
    "client_enricher.py": "client_enricher_sha256",
    "writer.py": "writer_sha256",
    "stages.py": "stages_sha256",
    "drive_autocreate_validity.py": "validator_sha256",
}


def _etime_seconds(etime: str) -> int | None:
    """Parse `ps -o etime=` ([[dd-]hh:]mm:ss) — locale-independent."""
    m = re.fullmatch(
        r"(?:(?:(\d+)-)?(\d+):)?(\d+):(\d+)", etime.strip()
    )
    if not m:
        return None
    days, hours, mins, secs = (int(g) if g else 0 for g in m.groups())
    return ((days * 24 + hours) * 60 + mins) * 60 + secs


def _worker_attestation(manifest_header: dict) -> list[str]:
    """R11-3: attest that the LIVE reroute consumer executes the audited
    bytes. Matching disk hashes in the WORKTREE prove nothing about the
    long-running launchd worker, which (a) runs from the DEPLOY checkout,
    not this worktree, and (b) keeps whatever modules it imported at boot.
    Three claims, all mandatory before an armed apply:

    1. every intake module in the deploy checkout is byte-identical to the
       manifest-bound worktree module (deploy has the audited code);
    2. the worker process booted AFTER the newest of those files' mtimes
       (the audited code is the LOADED code, not just the on-disk code);
    3. the daemon env carries neither the stub switch nor any auto-attach
       arming flag (batch-process-only arming, SKILL §1).

    Returns failure strings; empty list = attested. Fail-visible: any
    probe error is a failure, never a pass-through (W84)."""
    failures: list[str] = []
    deploy_root = os.environ.get(
        DEPLOY_ROOT_ENV, os.path.expanduser("~/nuzantara-deploy")
    )
    base = os.path.join(
        deploy_root, "apps", "backend-rag", "backend", "services", "intake"
    )
    newest_mtime = 0.0
    for fname, hkey in _ATTESTED_DEPLOY_FILES.items():
        path = os.path.join(base, fname)
        sha = _file_sha256(path)
        if sha == "unreadable":
            failures.append(f"deploy_file_unreadable:{fname}")
            continue
        if sha != manifest_header.get(hkey):
            failures.append(f"deploy_bytes_mismatch:{fname}")
        try:
            newest_mtime = max(newest_mtime, os.path.getmtime(path))
        except OSError:
            failures.append(f"deploy_mtime_unreadable:{fname}")
    try:
        out = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{WORKER_LABEL}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"launchctl_error:{type(exc).__name__}")
        return failures
    if out.returncode != 0:
        failures.append("worker_not_loaded")
        return failures
    text = out.stdout
    if "state = running" not in text:
        failures.append("worker_not_running")
    for env_name in _FORBIDDEN_WORKER_ENV:
        # Presence check is deliberately over-broad (a `FLAG=0` line still
        # fails): conservative direction, a human reads the plist.
        if env_name in text:
            failures.append(f"forbidden_daemon_env:{env_name}")
    pid_m = re.search(r"\bpid = (\d+)", text)
    if not pid_m:
        failures.append("worker_pid_unknown")
        return failures
    ps = subprocess.run(
        ["ps", "-o", "etime=", "-p", pid_m.group(1)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    elapsed = _etime_seconds(ps.stdout) if ps.returncode == 0 else None
    if elapsed is None:
        failures.append("worker_start_time_unknown")
        return failures
    if (time.time() - elapsed) < newest_mtime:
        failures.append("worker_booted_before_code")

    # R12-2/R13-2/R14-1: matching hashes at INTAKE_DEPLOY_ROOT prove
    # nothing about WHICH checkout the PID actually executes — attest
    # provenance too. R13-2 tightened this to the EXECUTABLE token only
    # (argv[0], or argv[1] when argv[0] is a known shell/interpreter
    # basename, per this repo's launchd convention: `/bin/bash
    # <deploy_root>/…/worker-run.sh`). R14-1 closed the hole THAT fix
    # left open: cwd was still accepted as an INDEPENDENT alternative —
    # an external executable (`/somewhere/else/worker.py`) running with
    # its cwd merely SET to the deploy root attested. cwd now has exactly
    # one legitimate role: resolving a RELATIVE executable token (rare,
    # but `ps` can report one) to an absolute path BEFORE the same
    # under-root check — it is never accepted on its own.
    root_real = os.path.realpath(deploy_root)
    ps_cmd = subprocess.run(
        ["ps", "-o", "command=", "-p", pid_m.group(1)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    argv = ps_cmd.stdout.split() if ps_cmd.returncode == 0 else []
    exe_token = None
    if argv:
        if os.path.basename(argv[0]) in _SHELL_INTERPRETER_BASENAMES and len(argv) > 1:
            exe_token = argv[1]
        else:
            exe_token = argv[0]
    if not exe_token:
        failures.append("worker_not_running_from_deploy_root")
        return failures
    if not os.path.isabs(exe_token):
        lsof = subprocess.run(
            ["lsof", "-a", "-p", pid_m.group(1), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        cwds = [
            ln[1:]
            for ln in lsof.stdout.splitlines()
            if ln.startswith("n") and lsof.returncode == 0
        ]
        if not cwds:
            failures.append("worker_cwd_unknown")
            return failures
        exe_token = os.path.join(cwds[0], exe_token)
    if not os.path.realpath(exe_token).startswith(root_real + os.sep):
        failures.append("worker_not_running_from_deploy_root")
    return failures


async def _apply_one(
    conn: asyncpg.Connection,
    *,
    kind: str,
    canonical: str,
    entry: dict,
    comp_col: str | None,
    batch: str,
    biz_cols: list[str],
    report: dict,
) -> int | None:
    """One candidate, one transaction: strong-id lock, under-lock
    revalidation, ledger 'planned' → clients INSERT → in-TX collision
    re-count → ledger 'created' with the full-row fingerprint. Returns the
    ledger id on create, None on skip (reason already in report). Raises
    StrongIdLockBusy on advisory-lock contention (caller converts to skip)
    and CollisionDetected on a post-insert owner-count violation (caller
    freezes the batch — the raise rolls this TX back, so nothing persists)."""
    from backend.services.intake.client_enricher import acquire_strong_id_lock

    async with conn.transaction():
        await acquire_strong_id_lock(conn, kind, canonical)

        # Under-lock revalidation (R2-3): the census predicate ran minutes
        # ago; re-check what can have CHANGED since — key still absent, name
        # still not similar to a live client, evidence rows untouched.
        if await _key_owner_count(conn, kind, canonical, comp_col):
            report["skipped"].append({"sid_kind": kind, "reason": "id_appeared"})
            return None
        sim = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM clients WHERE deleted_at IS NULL "
            "AND full_name IS NOT NULL AND similarity(upper(full_name), $1) >= $2)",
            entry["name"],
            EXISTING_NAME_SIM,
        )
        if sim:
            report["skipped"].append(
                {"sid_kind": kind, "reason": "possible_existing_appeared"}
            )
            return None
        await _lock_evidence_rows(conn, entry["docs"])
        for d in entry["docs"]:
            if not await _locked_evidence_matches(conn, d):
                report["skipped"].append({"sid_kind": kind, "reason": "evidence_moved"})
                return None

        # R7-2/R8-1: live scoped re-run of the census NAME gates — a doc
        # arrived after census can put a different name on this sid
        # (name_conflict) or this name on a different sid (cluster).
        _name_gate = await _live_name_gates(conn, kind, canonical, entry)
        if _name_gate:
            report["skipped"].append({"sid_kind": kind, "reason": _name_gate})
            return None

        ledger_id = await conn.fetchval(
            """
            INSERT INTO intake_identity_ledger
                (kind, canonical_value, full_name, batch_id, status,
                 source_proposal_ids, source_queue_ids, blob_hashes,
                 fields_fps)
            VALUES ($1,$2,$3,$4,'planned',$5,$6,$7,$8)
            ON CONFLICT (kind, canonical_value) DO NOTHING
            RETURNING id
            """,
            kind,
            canonical,
            entry["name"],
            batch,
            [d.pid for d in entry["docs"]],
            [d.qid for d in entry["docs"]],
            sorted({d.blob_hash for d in entry["docs"] if d.blob_hash}),
            sorted({d.fields_fp for d in entry["docs"]}),
        )
        if ledger_id is None:
            report["skipped"].append({"sid_kind": kind, "reason": "ledgered"})
            return None

        id_col = {
            "passport": "passport_number",
            "kitas": "kitas_number",
            "npwp": "npwp",
        }[kind]
        # nosemgrep: id_col from a closed dict above
        row = await conn.fetchrow(
            f"""
            INSERT INTO clients
                (full_name, {id_col}, status, origin, created_by,
                 lead_metadata, created_at, updated_at)
            VALUES ($1, $2, 'unlabeled', $3, $4, $5::jsonb, now(), now())
            RETURNING *
            """,
            entry["name"],
            canonical,
            DRIVE_ORIGIN,
            AUTOCREATE_CREATED_BY,
            json.dumps(
                {
                    "auto_created_from_drive": True,
                    "batch_id": batch,
                    "sid_kind": kind,
                }
            ),
        )
        await conn.execute(
            """
            UPDATE intake_identity_ledger
               SET status = 'created', client_id = $2,
                   business_fingerprint = $3, business_columns = $4,
                   updated_at = now()
             WHERE id = $1
            """,
            ledger_id,
            row["id"],
            _row_fingerprint(row, biz_cols),
            biz_cols,
        )

        # In-TX collision re-count (R6-1): under READ COMMITTED this second
        # count sees any competing write COMMITTED between the pre-check and
        # here; a violation raises → this whole TX rolls back, no contact.
        o = await _key_owners(conn, kind, canonical, comp_col)
        if o["client_ids"] != [row["id"]] or o["companies"] != 0:
            raise CollisionDetected(kind, o)

        # R7-2: similarity re-check AFTER the insert — a similar live client
        # committed since the pre-check makes this create quarantine-grade;
        # roll it back and skip (not a red-line collision, no freeze).
        sim2 = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM clients WHERE deleted_at IS NULL "
            "AND id <> $3 AND full_name IS NOT NULL "
            "AND similarity(upper(full_name), $1) >= $2)",
            entry["name"],
            EXISTING_NAME_SIM,
            row["id"],
        )
        if sim2:
            raise _PostInsertGuard("possible_existing_appeared_post")

        # R9-3: repeat the DOCUMENT name gates after the insert too — the
        # pre-insert probes read unlocked predicates under READ COMMITTED, so
        # a conflicting proposal committed between probe and insert was
        # invisible to them. This in-TX re-run sees anything committed up to
        # this statement. The residual (a competitor committing between here
        # and our COMMIT) is DETECTED by the delayed --verify-batch at
        # T+delay and T+1d, not prevented (R11-5): routing keeps dup keys in
        # AMBIGUOUS/never-auto, but a HUMAN reviewer can attach documents to
        # this client before verify runs, and attach evidence makes the
        # automated rollback refuse (fk_refs/content_drift → guarded, exit
        # 4, human triage — never a blind delete). Consequence bound =
        # detection + guarded rollback + short verify delay, not immunity.
        gate2 = await _live_name_gates(conn, kind, canonical, entry)
        if gate2:
            raise _PostInsertGuard(f"{gate2}_post")
    return ledger_id


async def _verify_lot_freshness(
    conn: asyncpg.Connection,
    qids: list[int],
    pre_reset_pid: dict[int, int],
    started_at,
    run_tag: str,
) -> tuple[str | None, dict[int, int]]:
    """Detective assertions (R2-1 + R6-2 + R7-3 + R8-5): every queue must
    show a proposal NEWER than the id captured under lock immediately before
    reset, stamped with THIS RUN's batch-qualified tag (R10-2: a global tag
    made two invocations indistinguishable), in a human-review terminal;
    zero auto_routed; zero new commit-audit rows. Returns
    (failure_reason_or_None, fresh_pid_by_qid)."""
    latest = await conn.fetch(
        """
        SELECT DISTINCT ON (queue_id) queue_id, id, status, pipeline_version
        FROM document_routing_proposal
        WHERE queue_id = ANY($1::bigint[])
        ORDER BY queue_id, id DESC
        """,
        qids,
    )
    fresh = {
        r["queue_id"]: r["id"]
        for r in latest
        if r["id"] > pre_reset_pid.get(r["queue_id"], 0)
        and r["pipeline_version"] == run_tag
        and r["status"] in ("review_pending", "quarantine")
    }
    auto_routed = sum(1 for r in latest if r["status"] == "auto_routed")
    new_audit = await conn.fetchval(
        """
        SELECT count(*) FROM intake_commit_audit a
        JOIN document_routing_proposal p ON p.id = a.proposal_id
        WHERE p.queue_id = ANY($1::bigint[]) AND a.committed_at >= $2
        """,
        qids,
        started_at,
    )
    if (
        len(latest) != len(qids)
        or len(fresh) != len(qids)
        or auto_routed
        or new_audit
    ):
        return (
            f"reroute assertion failed: latest={len(latest)}/{len(qids)} "
            f"fresh_ok={len(fresh)} auto_routed={auto_routed} "
            f"new_audit={new_audit}",
            fresh,
        )
    return None, fresh


async def _reroute_lot(
    conn: asyncpg.Connection,
    *,
    lot_qids: set[int],
    sup_pids: list[int],
    lot_ledger: list[tuple[int, list[int]]],
    started_at,
    run_tag: str,
    poll_seconds: int = DRAIN_POLL_SECONDS,
    attest: object = None,
) -> str | None:
    """Post-create reroute with causal verification. Returns a freeze reason
    or None on success.

    R7-4: supersede + reset + their cardinality checks share ONE transaction
    — a shortfall rolls BOTH back before freezing. R8-6: queues are locked
    FIRST (ascending), then proposals — the same global order as evidence
    locking and rollback. R8-5: the latest proposal id per queue is captured
    UNDER the queue lock immediately before reset; freshness then requires a
    proposal NEWER than that capture AND tagged AND in a human-review
    terminal — a pre-reset proposal from any earlier same-tag reroute can
    never satisfy it. R8-4: the fresh proposal ids are recorded per ledger
    row (reroute_proposal_ids) so rollback can compare-and-swap against
    exactly this generation."""
    qids = sorted(lot_qids)
    pre_reset_pid: dict[int, int] = {}
    try:
        async with conn.transaction():
            for qid in qids:
                await conn.execute(
                    "SELECT id FROM intake_queue WHERE id = $1 FOR UPDATE", qid
                )
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (queue_id) queue_id, id
                FROM document_routing_proposal
                WHERE queue_id = ANY($1::bigint[])
                ORDER BY queue_id, id DESC
                """,
                qids,
            )
            pre_reset_pid = {r["queue_id"]: r["id"] for r in rows}
            # R10-3 preventive CAS: BEFORE mutating anything, every queue's
            # CURRENT latest proposal (read under the queue locks) must be
            # exactly the census-time source this lot is superseding — a
            # foreign proposal that appeared while the lot's contacts were
            # being created freezes the lot with ZERO foreign state touched
            # (detection used to happen only after supersede+reset).
            sup_set = set(sup_pids)
            foreign = sorted(
                q for q in qids if pre_reset_pid.get(q) not in sup_set
            )
            if foreign:
                raise _RerouteCardinality(
                    f"pre-supersede CAS: {len(foreign)} of {len(qids)} queues "
                    "carry a proposal newer than the census sources"
                )
            sup_rows = await conn.fetch(SUPERSEDE_SQL, sup_pids)
            if len(sup_rows) != len(sup_pids):
                raise _RerouteCardinality(
                    f"supersede cardinality: {len(sup_rows)} != {len(sup_pids)}"
                )
            reset_tag = await conn.execute(RESET_QUEUE_SQL, qids, run_tag)
            reset_n = int(reset_tag.split()[-1]) if reset_tag else -1
            if reset_n != len(qids):
                raise _RerouteCardinality(
                    f"queue-reset cardinality: {reset_n} != {len(qids)} "
                    "(status/lease fence miss?)"
                )
    except _RerouteCardinality as exc:
        return str(exc)

    # Drain-poll: a timeout is a FAILURE, not a pass — an idle worker means
    # the reroute was never actually exercised. Drained terminal shape is
    # stage='route' AND status='done' (probed live on the m227/m248 reroute
    # populations — 24,239 + 129 rows all landed exactly there).
    deadline = asyncio.get_event_loop().time() + poll_seconds
    drained = False
    pending = None
    while asyncio.get_event_loop().time() <= deadline:
        # NULL-safe pending predicate (Codex round 9, R9-4): stage is a
        # nullable column, and NOT (stage='route' AND status='done') evaluates
        # to NULL — row silently excluded — for stage IS NULL. IS DISTINCT
        # FROM keeps the null shape PENDING (fail closed), never drained.
        pending = await conn.fetchval(
            "SELECT count(*) FROM intake_queue WHERE id = ANY($1::bigint[]) "
            "AND (stage IS DISTINCT FROM 'route' OR status IS DISTINCT FROM 'done')",
            qids,
        )
        if pending == 0:
            drained = True
            break
        await asyncio.sleep(5)
    if not drained:
        return (
            f"drain timeout after {poll_seconds}s: "
            f"{pending} of {len(qids)} queues still pending"
        )

    failure, fresh = await _verify_lot_freshness(
        conn, qids, pre_reset_pid, started_at, run_tag
    )
    if failure:
        return failure

    # R12-3: the pre-apply attestation is a snapshot, not a fence — the
    # worker can restart or the deploy files can change during the drain
    # window. Re-attest AFTER the drain, BEFORE certifying the lot: a
    # divergence freezes (reroute_verified stays FALSE, human triage),
    # bounding the TOCTOU to detection-in-the-same-run. The residual
    # (attach by a rogue worker DURING the window) is already caught by
    # freshness's zero-auto_routed/zero-audit assertions above.
    if attest is not None:
        post_failures = attest()
        if post_failures:
            return f"post_drain_attestation: {post_failures}"

    for ledger_id, led_qids in lot_ledger:
        await conn.execute(
            """
            UPDATE intake_identity_ledger
               SET reroute_verified = TRUE, reroute_proposal_ids = $2,
                   updated_at = now()
             WHERE id = $1
            """,
            ledger_id,
            sorted(fresh[q] for q in led_qids if q in fresh),
        )
    return None


async def run_apply(
    dsn: str,
    *,
    manifest: str,
    batch_size: int,
    max_batches: int,
    out_json: str | None,
    skip_worker_attest: bool = False,
) -> int:
    from datetime import datetime, timezone

    armed = os.environ.get(KILLSWITCH_ENV, "").strip().lower() in {"1", "true", "yes", "on"}

    # Wave-1 limits are ENFORCED, not defaulted (R6-6): one lot, 1..200.
    # A different scale requires a new gate round, not a CLI flag.
    if max_batches != 1:
        print(f"REFUSED: wave-1 authorizes exactly 1 batch (got --max-batches {max_batches}).")
        return 2
    if not 1 <= batch_size <= HARD_BATCH_CAP:
        print(f"REFUSED: batch size must be 1..{HARD_BATCH_CAP} (got {batch_size}).")
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        await attest_local_book(conn)

        # Manifest binding (R1-B14/R4-2/R5-1): re-derive the digest from the
        # SAME code path and refuse on mismatch — the approved GO binds to
        # exactly this candidate set under exactly this code.
        c = await _compute_census(conn)
        if c["digest"] != manifest:
            print(
                f"MANIFEST MISMATCH: recomputed {c['digest']} != approved {manifest} "
                "— candidate set or code changed since GO. Refusing."
            )
            return 3
        res: CensusResult = c["res"]
        comp_col = c["comp_col"]

        # Candidate bundles from the census evidence (sid -> docs).
        per_sid: dict[str, dict] = {}
        for d in res.a_docs:
            sid = f"{d.kind}:{d.canonical}"
            e = per_sid.setdefault(sid, {"name": res.a_sids[sid], "docs": []})
            e["docs"].append(d)
        candidates = [(sid, per_sid[sid]) for sid in sorted(per_sid)]

        if not armed:
            print(
                json.dumps(
                    {
                        "mode": "DRY-RUN (killswitch off)",
                        "manifest_ok": True,
                        "candidates": len(candidates),
                        "batch_size": batch_size,
                        "batches_planned": min(
                            max_batches,
                            (len(candidates) + batch_size - 1) // batch_size,
                        ),
                    },
                    indent=2,
                )
            )
            return 0

        # R11-3: an ARMED apply requires an attested live worker — the
        # reroute lot is consumed by the launchd daemon in the DEPLOY
        # checkout, and disk hashes here say nothing about what that
        # process has LOADED. Escape hatch is a visible CLI choice for
        # dev/test rigs only, never the wave default.
        if not skip_worker_attest:
            attest_failures = _worker_attestation(c["manifest_header"])
            if attest_failures:
                print(
                    json.dumps(
                        {
                            "mode": "REFUSED (worker attestation failed)",
                            "failures": attest_failures,
                        },
                        indent=2,
                    )
                )
                return 3

        await conn.execute(LEDGER_DDL)
        await conn.execute(
            "ALTER TABLE intake_identity_ledger "
            "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
        )
        biz_cols = await _business_columns(conn)
        batch = _batch_id()
        started_at = datetime.now(timezone.utc)
        report = {
            "batch_id": batch,
            "created": 0,
            "skipped": [],
            "lots": 0,
            "frozen": None,
        }
        created_keys: list[tuple[str, str]] = []

        from backend.services.intake.client_enricher import StrongIdLockBusy

        lots = [
            candidates[i : i + batch_size]
            for i in range(0, len(candidates), batch_size)
        ][:max_batches]

        for lot_no, lot in enumerate(lots, start=1):
            # Delayed re-sweep of everything created so far (R3-5): a human
            # write committed after an earlier immediate sweep surfaces here.
            bad = await _sweep_keys(conn, created_keys, comp_col, expect_max=1)
            if bad:
                report["frozen"] = f"delayed re-sweep found multi-owner keys: {bad}"
                break

            lot_qids: set[int] = set()
            lot_ledger: list[tuple[int, list[int]]] = []
            for sid, entry in lot:
                kind, canonical = sid.split(":", 1)
                try:
                    ledger_id = await _apply_one(
                        conn,
                        kind=kind,
                        canonical=canonical,
                        entry=entry,
                        comp_col=comp_col,
                        batch=batch,
                        biz_cols=biz_cols,
                        report=report,
                    )
                except StrongIdLockBusy:
                    # Advisory-lock contention (another writer holds this
                    # strong-id): a per-candidate skip, never a batch abort.
                    report["skipped"].append({"sid_kind": kind, "reason": "lock_busy"})
                    continue
                except _PostInsertGuard as exc:
                    # The create's TX rolled back for a quarantine-grade
                    # reason (similar client appeared mid-candidate) — skip.
                    report["skipped"].append({"sid_kind": kind, "reason": exc.reason})
                    continue
                except CollisionDetected as exc:
                    # In-TX owner-count violation: the TX rolled back, no
                    # contact persists — but a competing writer is ACTIVE on
                    # this key space, so the whole batch freezes (R6-1).
                    report["frozen"] = (
                        f"in-tx collision kind={exc.kind} owners={exc.owners}"
                    )
                    break
                if ledger_id is not None:
                    report["created"] += 1
                    created_keys.append((kind, canonical))
                    lot_qids |= {d.qid for d in entry["docs"]}
                    lot_ledger.append(
                        (ledger_id, sorted({d.qid for d in entry["docs"]}))
                    )
                    # Post-COMMIT verify (R6-1): catches a competing writer
                    # whose TX was uncommitted during both in-TX counts and
                    # committed after ours. The created row stands (ledger-
                    # reversible); the batch freezes for triage.
                    o = await _key_owners(conn, kind, canonical, comp_col)
                    if len(o["client_ids"]) + o["companies"] > 1:
                        report["frozen"] = (
                            f"post-commit collision kind={kind} "
                            f"client_ids={o['client_ids']} companies={o['companies']}"
                            " — run --rollback-batch for this batch"
                        )
                        break
            if report["frozen"]:
                break

            # Immediate post-lot key sweep (R2-2): freeze on any key that now
            # owns more than the one row this lot just minted.
            lot_keys = [
                (s.split(":", 1)[0], s.split(":", 1)[1])
                for s, _ in lot
                if (s.split(":", 1)[0], s.split(":", 1)[1]) in created_keys
            ]
            bad = await _sweep_keys(conn, lot_keys, comp_col, expect_max=1)
            if bad:
                report["frozen"] = f"post-lot sweep found multi-owner keys: {bad}"
                break

            # Post-create reroute (route-only; suppression rides the tag).
            if lot_qids:
                sup_pids = sorted(
                    {d.pid for _, e in lot for d in e["docs"] if d.qid in lot_qids}
                )
                freeze = await _reroute_lot(
                    conn,
                    lot_qids=lot_qids,
                    sup_pids=sup_pids,
                    lot_ledger=lot_ledger,
                    started_at=started_at,
                    run_tag=run_tag_for(batch),
                    attest=(
                        None
                        if skip_worker_attest
                        else lambda: _worker_attestation(c["manifest_header"])
                    ),
                )
                if freeze:
                    report["frozen"] = freeze
                    break

            report["lots"] = lot_no

        # Final end-of-program sweep (R3-5 delayed detection).
        if not report["frozen"]:
            bad = await _sweep_keys(conn, created_keys, comp_col, expect_max=1)
            if bad:
                report["frozen"] = f"final sweep found multi-owner keys: {bad}"

        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        if out_json:
            with open(out_json, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
        return 4 if report["frozen"] else 0
    finally:
        await conn.close()


async def run_rollback(dsn: str, batch_id: str) -> int:
    armed = os.environ.get(KILLSWITCH_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    conn = await asyncpg.connect(dsn)
    try:
        await attest_local_book(conn)
        if not armed:
            print(f"DRY-RUN (killswitch off): would roll back batch {batch_id}")

        from backend.services.intake.client_enricher import StrongIdLockBusy

        # R11-4: an unknown/mistyped batch must NOT be a vacuous success —
        # zero rows in ANY status means this batch id never existed here,
        # and automation reading exit 0 would treat the typo as "reverted".
        known = await conn.fetchval(
            "SELECT count(*) FROM intake_identity_ledger WHERE batch_id = $1",
            batch_id,
        )
        if not known:
            print(
                json.dumps(
                    {"batch_id": batch_id, "error": "unknown_batch"},
                    ensure_ascii=False,
                )
            )
            return 2

        refs = await _fk_references(conn)
        rows = await conn.fetch(
            "SELECT * FROM intake_identity_ledger WHERE batch_id = $1 "
            "AND status IN ('created')",
            batch_id,
        )
        report = {"batch_id": batch_id, "rolled_back": 0, "guarded": []}
        for led in rows:
            if not armed:
                continue
            try:
                await _rollback_one(conn, led, refs, report)
            except StrongIdLockBusy:
                report["guarded"].append(
                    {"ledger_id": led["id"], "reason": "lock_busy"}
                )
                continue
            except _RerouteCardinality as exc:
                # R8-4 CAS abort: the whole per-candidate TX rolled back —
                # the client soft-delete included. Human triage.
                report["guarded"].append(
                    {"ledger_id": led["id"], "reason": f"cas_abort: {exc}"}
                )
                continue

        # R12-4: an UNARMED invocation over live 'created' rows is NOT a
        # rollback — it touched nothing. Exit 0 here would let automation
        # read "killswitch forgotten" as "batch reverted". Exit 6 = armed
        # action required, rows untouched (distinct from 4 = partial).
        if not armed and rows:
            report["mode"] = "DRY-RUN (killswitch off)"
            report["created_rows_untouched"] = len(rows)
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            return 6

        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        # R10-6: an incomplete rollback is NOT success — any guarded row
        # means a created contact is still alive, and automation reading
        # exit 0 would treat the batch as reverted. Exit 4 = partial,
        # human triage on the guarded reasons.
        return 4 if report["guarded"] else 0
    finally:
        await conn.close()


async def _rollback_one(
    conn: asyncpg.Connection,
    led: object,
    refs: list[tuple[str, str]],
    report: dict,
) -> None:
    from backend.services.intake.client_enricher import acquire_strong_id_lock

    async with conn.transaction():
        await acquire_strong_id_lock(conn, led["kind"], led["canonical_value"])
        # Re-read + lock the ledger row inside the TX (R6-7): the pre-fetched
        # copy may be stale (concurrent rollback / status change).
        led = await conn.fetchrow(
            "SELECT * FROM intake_identity_ledger WHERE id = $1 "
            "AND status = 'created' FOR UPDATE",
            led["id"],
        )
        if led is None:
            report["guarded"].append({"reason": "ledger_moved"})
            return
        row = await conn.fetchrow(
            "SELECT * FROM clients WHERE id = $1 FOR UPDATE", led["client_id"]
        )
        if row is None:
            report["guarded"].append({"ledger_id": led["id"], "reason": "row_gone"})
            return
        # Schema-drift guard (R6-7): a business column added AFTER creation
        # can carry human data invisible to the stored fingerprint — the
        # column SETS must match exactly, else no delete.
        if set(await _business_columns(conn)) != set(led["business_columns"]):
            await conn.execute(
                "UPDATE intake_identity_ledger SET guard_reason='schema_drift', "
                "updated_at=now() WHERE id=$1",
                led["id"],
            )
            report["guarded"].append(
                {"ledger_id": led["id"], "reason": "schema_drift"}
            )
            return
        fp = _row_fingerprint(row, list(led["business_columns"]))
        if fp != led["business_fingerprint"]:
            # Content drift = a human touched it (W88: content, never
            # updated_by proxies) — leave it alone, report.
            await conn.execute(
                "UPDATE intake_identity_ledger SET guard_reason='content_drift', "
                "updated_at=now() WHERE id=$1",
                led["id"],
            )
            report["guarded"].append(
                {"ledger_id": led["id"], "reason": "content_drift"}
            )
            return
        fk_hits = await _fk_sweep(conn, refs, led["client_id"])
        if fk_hits:
            await conn.execute(
                "UPDATE intake_identity_ledger SET guard_reason=$2, "
                "updated_at=now() WHERE id=$1",
                led["id"],
                f"fk_refs:{','.join(fk_hits)}",
            )
            report["guarded"].append(
                {"ledger_id": led["id"], "reason": f"fk_refs:{fk_hits}"}
            )
            return
        await conn.execute(
            "UPDATE clients SET deleted_at = now() WHERE id = $1",
            led["client_id"],
        )
        # R7-4/R8-4/R9-1: restore the evidence queues in the SAME TX with a
        # PHASE-AWARE compare-and-swap. reroute_proposal_ids exists only
        # after a VERIFIED reroute — any earlier freeze (post-commit
        # collision, sweep, drain timeout, crash) leaves it NULL, and the old
        # CAS then read NULL as the empty set, classified every queue as
        # "moved on" and made rollback structurally impossible (R9-1). The
        # ledger's source_proposal_ids (each queue's latest pid, captured
        # under the evidence locks at create time) is the pre-reroute
        # expected set. Per-queue verdict, queues locked FIRST (R8-6):
        #   verified reroute  → latest ∈ reroute_proposal_ids → supersede+
        #     reset (fresh candidates may reference the deleted client);
        #   unverified-fresh  → latest carries OUR pipeline tag in review →
        #     product of a reroute that froze pre-verify → supersede+reset;
        #   mid-reroute       → latest ∈ source_proposal_ids but superseded
        #     → the queue is already primed to re-route; nothing to restore;
        #   pre-reroute       → latest ∈ source_proposal_ids still in review
        #     → the original proposals never saw the client; nothing to do;
        #   anything else     → foreign writer → raise → TX abort → nothing,
        #     including the soft-delete, persists. Cardinalities are exact.
        qids = sorted(set(led["source_queue_ids"] or []))
        if qids:
            own_reroute = set(led["reroute_proposal_ids"] or [])
            own_original = set(led["source_proposal_ids"] or [])
            # R10-2a: only THIS batch's qualified tags are "ours" — the bare
            # global tag proved nothing (another invocation is
            # indistinguishable). ``-rb`` is a prior partial rollback of the
            # SAME batch (a retry must recognize its own earlier resets).
            own_tags = {
                run_tag_for(led["batch_id"]),
                rb_tag_for(led["batch_id"]),
            }
            rb_tag = rb_tag_for(led["batch_id"])
            for qid in qids:
                await conn.execute(
                    "SELECT id FROM intake_queue WHERE id = $1 FOR UPDATE", qid
                )
            queue_state = {
                r["id"]: r["status"]
                for r in await conn.fetch(
                    "SELECT id, status FROM intake_queue WHERE id = ANY($1::bigint[])",
                    qids,
                )
            }
            cur = await conn.fetch(
                """
                SELECT DISTINCT ON (queue_id) id, queue_id, status, pipeline_version
                FROM document_routing_proposal
                WHERE queue_id = ANY($1::bigint[])
                ORDER BY queue_id, id DESC
                """,
                qids,
            )
            restore: list[tuple[int, int]] = []  # (pid, qid)
            revive_dead: list[int] = []  # qids stuck at status='dead'
            moved: list[int] = []
            for r in cur:
                if r["id"] in own_reroute:
                    restore.append((r["id"], r["queue_id"]))
                elif own_reroute:
                    # A verified batch expects EVERY latest to be its own.
                    moved.append(r["queue_id"])
                elif r["pipeline_version"] in own_tags and r["status"] in (
                    "review_pending",
                    "quarantine",
                ):
                    restore.append((r["id"], r["queue_id"]))
                elif r["id"] in own_original and r["status"] == "superseded":
                    # Mid-reroute. R10-2b: "already headed back to review" is
                    # only true while the queue is actually re-processing — a
                    # worker that exhausted retries left it 'dead' and the
                    # docs would never return; revive it. Any other queue
                    # state here is an anomaly → fail closed.
                    qs = queue_state.get(r["queue_id"])
                    if qs == "validated":
                        continue
                    if qs == "dead":
                        revive_dead.append(r["queue_id"])
                    else:
                        moved.append(r["queue_id"])
                elif r["id"] in own_original and r["status"] in (
                    "review_pending",
                    "quarantine",
                ):
                    continue  # pre-reroute: originals never saw the client
                else:
                    moved.append(r["queue_id"])
            if len(cur) != len(qids) or moved:
                raise _RerouteCardinality(
                    f"rollback CAS: {len(moved)} of {len(qids)} queues moved on "
                    "since this batch's create/reroute — human triage required"
                )
            if restore:
                sup_rows = await conn.fetch(SUPERSEDE_SQL, [p for p, _q in restore])
                if len(sup_rows) != len(restore):
                    raise _RerouteCardinality(
                        f"rollback supersede cardinality: {len(sup_rows)} != {len(restore)}"
                    )
                restore_qids = sorted({q for _p, q in restore})
                reset_tag = await conn.execute(RESET_QUEUE_SQL, restore_qids, rb_tag)
                reset_n = int(reset_tag.split()[-1]) if reset_tag else -1
                if reset_n != len(restore_qids):
                    raise _RerouteCardinality(
                        f"rollback reset cardinality: {reset_n} != {len(restore_qids)}"
                    )
            if revive_dead:
                revive_tag = await conn.execute(
                    REVIVE_DEAD_QUEUE_SQL, sorted(revive_dead), rb_tag
                )
                revive_n = int(revive_tag.split()[-1]) if revive_tag else -1
                if revive_n != len(revive_dead):
                    raise _RerouteCardinality(
                        f"rollback dead-revive cardinality: {revive_n} != {len(revive_dead)}"
                    )
        await conn.execute(
            "UPDATE intake_identity_ledger SET status='rolled_back', "
            "updated_at=now() WHERE id=$1",
            led["id"],
        )
        report["rolled_back"] += 1


async def run_verify(dsn: str, batch_id: str) -> int:
    """Delayed batch verification (R7-1, hardened per R8-2/R8-3). The
    two-uncommitted-writers residual is undetectable while apply runs — a
    competitor's TX can commit AFTER our final sweep. This read-only mode
    re-verifies a batch at ANY later time; the wave protocol runs it at
    T+delay AND again at T+1d (a single check cannot bound competitor TX
    lifetime — repetition does).

    Non-vacuous by construction (R8-3): an unknown/mistyped batch id is exit
    2, never a clean pass; each created key must be owned by EXACTLY the
    ledger's own client_id (not merely "at most one owner"). R8-2: a
    same-name different-id competitor is a NAME violation, not a key one —
    each created full_name is re-screened for live trigram-similar
    neighbours (quarantine-grade signal, human triage)."""
    conn = await asyncpg.connect(dsn)
    try:
        await attest_local_book(conn)
        comp_col = await _resolve_companies_npwp_col(conn)
        known = await conn.fetchval(
            "SELECT count(*) FROM intake_identity_ledger WHERE batch_id = $1",
            batch_id,
        )
        if not known:
            print(f"UNKNOWN BATCH: no ledger rows carry batch_id={batch_id!r}")
            return 2
        rows = await conn.fetch(
            "SELECT id, kind, canonical_value, full_name, client_id, reroute_verified "
            "FROM intake_identity_ledger WHERE batch_id = $1 AND status = 'created'",
            batch_id,
        )
        owner_violations = []
        name_violations = []
        attach_info = []
        for r in rows:
            o = await _key_owners(conn, r["kind"], r["canonical_value"], comp_col)
            if o["client_ids"] != [r["client_id"]] or o["companies"] != 0:
                owner_violations.append(
                    {
                        "ledger_id": r["id"],
                        "kind": r["kind"],
                        "expected_client_id": r["client_id"],
                        "client_ids": o["client_ids"],
                        "companies": o["companies"],
                    }
                )
            similar = await conn.fetch(
                "SELECT id FROM clients WHERE deleted_at IS NULL AND id <> $2 "
                "AND full_name IS NOT NULL "
                "AND similarity(upper(full_name), upper($1)) >= $3 ORDER BY id",
                r["full_name"],
                r["client_id"],
                EXISTING_NAME_SIM,
            )
            if similar:
                name_violations.append(
                    {
                        "ledger_id": r["id"],
                        "similar_client_ids": [s["id"] for s in similar],
                    }
                )
            # R9-3: the delayed pass re-runs the DOCUMENT name gates too —
            # a conflicting proposal whose TX committed after apply's final
            # in-TX re-check is visible here (R10-1: the probes scan EVERY
            # proposal status, so a conflict that advanced to auto_routed
            # can no longer vanish from this check); two runs (T+delay,
            # T+1d) bound the competitor-TX-lifetime residual.
            doc_gate = await _live_name_gates(
                conn,
                r["kind"],
                r["canonical_value"],
                {"name": r["full_name"]},
            )
            if doc_gate:
                name_violations.append(
                    {"ledger_id": r["id"], "document_gate": doc_gate}
                )
                # R11-5: persist the verdict — stdout dies with the process,
                # and the rollback/triage path reads the LEDGER. A verify
                # conflict must survive as durable state on the row.
                await conn.execute(
                    "UPDATE intake_identity_ledger SET guard_reason = $2, "
                    "updated_at = now() WHERE id = $1 AND guard_reason IS NULL",
                    r["id"],
                    f"verify_conflict:{doc_gate}",
                )
            # R10-1 triage visibility: docs COMMITTED onto this created
            # contact since the batch ran. A clean strong-id attach is the
            # program's intended payoff, not a violation — but a triager
            # reading a document_gate violation needs to know whether an
            # attach already happened (fk_refs will also guard rollback).
            attached = await conn.fetchval(
                "SELECT count(*) FROM intake_commit_audit "
                "WHERE client_id = $1 AND outcome = 'committed'",
                r["client_id"],
            )
            if attached:
                attach_info.append(
                    {"ledger_id": r["id"], "committed_docs": attached}
                )
        unrerouted = [r["id"] for r in rows if not r["reroute_verified"]]
        report = {
            "batch_id": batch_id,
            "ledger_rows_any_status": known,
            "created_rows": len(rows),
            "owner_violations": owner_violations,
            "name_violations": name_violations,
            "attached_docs_info": attach_info,
            "reroute_unverified_ledger_ids": unrerouted,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return 4 if (owner_violations or name_violations or unrerouted) else 0
    finally:
        await conn.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--census", action="store_true", help="run the read-only census")
    ap.add_argument("--apply", action="store_true", help="apply (needs --manifest + killswitch env)")
    ap.add_argument("--manifest", help="approved census manifest digest (required with --apply)")
    ap.add_argument("--batch-size", type=int, default=HARD_BATCH_CAP)
    ap.add_argument("--max-batches", type=int, default=1)
    ap.add_argument("--rollback-batch", help="roll back a batch by id (killswitch env required)")
    ap.add_argument(
        "--verify-batch",
        help="read-only delayed re-verification of a batch (R7-1 wave protocol: run at T+delay)",
    )
    ap.add_argument("--out-json", help="also write the report to this path")
    ap.add_argument(
        "--skip-worker-attest",
        action="store_true",
        help="skip the R11-3 live-worker attestation (dev/test rigs ONLY — "
        "an armed wave apply must never pass this)",
    )
    ap.add_argument(
        "--dsn", default=os.environ.get("INTAKE_DATABASE_URL", DEFAULT_DSN)
    )
    args = ap.parse_args()

    try:
        if args.verify_batch:
            return asyncio.run(run_verify(args.dsn, args.verify_batch))
        if args.rollback_batch:
            return asyncio.run(run_rollback(args.dsn, args.rollback_batch))
        if args.apply:
            if not args.manifest:
                print("--apply requires --manifest <digest> (the approved census digest)")
                return 2
            return asyncio.run(
                run_apply(
                    args.dsn,
                    manifest=args.manifest,
                    batch_size=args.batch_size,
                    max_batches=args.max_batches,
                    out_json=args.out_json,
                    skip_worker_attest=args.skip_worker_attest,
                )
            )
        if not args.census:
            print("nothing to do — pass --census, --apply, --verify-batch or --rollback-batch")
            return 2
        return asyncio.run(run_census(args.dsn, args.out_json))
    except SystemExit:
        raise
    except Exception as exc:  # R7-6 redaction boundary
        # R7-6: an uncaught DB/driver exception can embed inserted VALUES
        # (names, canonical ids) in its message — never print raw detail.
        print(
            f"FATAL {type(exc).__name__} — detail suppressed (PII boundary); "
            "inspect the ledger and DB state directly.",
            file=sys.stderr,
        )
        return 5


if __name__ == "__main__":
    sys.exit(main())
