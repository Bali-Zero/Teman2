"""Client-card enrichment from intake-extracted document fields.

When the HITL reviewer approves an intake document (passport/KITAS/NPWP/NIB), the
*file* is filed as a `documents` row — but the document also carries **structured
identity data** that belongs on the client's record (passport number + expiry feed
the renewal-alert clock; date_of_birth/nationality fill the profile). Before this
module the intake commit path filed the file and **threw the extracted fields away**
(see ``writer._document_payload`` — every column the CRM card needs was left unset).

This module mirrors the enrichment the manual CRM endpoints already do
(``crm_clients_documents.py::extract-passport-enhanced`` / ``extract-npwp`` /
``extract-nib``), but driven by the *intake extract schema* key names (``passport_no``,
``dob``, ``expiry`` — NOT ``passport_number``/``date_of_birth``/``expiry_date`` which
are the manual-endpoint's own renamed keys). It runs **inside the same atomic
transaction** as the document write in ``execute_commit`` (FASE 5C), so the file and
the card update commit or roll back together.

Reuse over duplication: a single declarative map (doc_type → [(extract_key, column,
coercion)]) is the source of truth, so adding a doc_type is a one-line change.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("zantara.intake.client_enricher")

# Columns the GATE-11 verified-promotion check applies to (identity_backfill
# provenance is only ever recorded for these two — see research/operations/
# 2026-07-18-intake-identity-backfill-design.md §3 rule 6/11).
_BACKFILL_PROVENANCE_COLUMNS = ("passport_number", "kitas_number")


def _normalize_for_promotion(value: Any) -> str:
    """Loose identifier normaliser for the GATE-11 verified-promotion check.

    Broader than the CRM's own passport/kitas normalisers (strips ANY
    non-alnum char, not just separators): this only decides "is the document
    confirming the SAME identifier already on the card", not how the value
    is canonically stored.
    """
    return re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()


def _to_date(value: Any) -> date | None:
    """Coerce an extracted date string to a ``date``.

    The extractor is asked to "prefer YYYY-MM-DD" but is not guaranteed to comply,
    so accept the common variants and give up (return None → field skipped) rather
    than raise: a bad date must never roll back the whole document commit.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.warning("client_enricher: unparseable date %r — skipping field", s)
    return None


def _digits_only(value: Any) -> str | None:
    """Strip all non-digits (NPWP/NIB are stored canonical, no dots/dashes)."""
    if value is None:
        return None
    cleaned = re.sub(r"\D", "", str(value))
    return cleaned or None


def _npwp_digits(value: Any) -> str | None:
    """NPWP digits, written only when a COMPLETE number was read.

    A valid NPWP is exactly 15 (legacy) or 16 (NIK-format) digits — the same
    gate the intake matcher applies (``routing._match_person_strong``, m248),
    and the same ASCII-only ``[^0-9]`` projection (``\\D`` is Unicode-aware and
    would let non-ASCII digits survive into the stored value, which the
    matcher's SQL ``[^0-9]`` projection then counts differently). A partial OCR
    fragment stored here would pollute the CRM key book that strong-id
    corroboration reads from, so incomplete reads are dropped, never stored.
    """
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9]", "", str(value))
    if len(cleaned) not in (15, 16):
        return None
    return cleaned


# Advisory-lock seed shared by every strong-id writer/verifier on this DB.
# The auto-attach gates take the same per-value xact lock before re-verifying
# ownership; the enricher takes it before writing a strong-id column. This
# serializes "verify then commit" against "write a new owner" for the same
# identifier value — closing the in-TX TOCTOU (Codex 2026-07-19 round 3).
STRONG_ID_LOCK_SEED = 4248

_STRONG_ID_LOCK_KINDS = {
    "passport_number": "passport",
    "kitas_number": "kitas",
    "npwp": "npwp",
}


def strong_id_lock_value(kind: str, raw: object) -> str:
    """Canonical lock-key projection for one strong-id value.

    EVERY lock participant must project the value the same way, or two
    formatting-equivalent strings ("2X-123.456/YZ" vs "2X123456YZ") hash to
    DIFFERENT advisory keys and silently miss each other's lock (Codex
    2026-07-19 round 4, F2). Mirrors the matcher normalization per kind:
    npwp → ASCII digits; passport/kitas → separator-stripped upper-case.
    """
    s = str(raw)
    if kind == "npwp":
        return re.sub(r"[^0-9]", "", s)
    return re.sub(r"[\s.\-/]", "", s).upper()


class StrongIdLockBusy(TimeoutError):
    """The bounded advisory-lock wait expired — the strong-id value is
    contended by a concurrent transaction. Dedicated type so callers can treat
    LOCK contention as a benign skip without swallowing unrelated timeouts
    (Codex 2026-07-19 round 6, F9)."""


async def acquire_strong_id_lock(conn: asyncpg.Connection, kind: str, value: str) -> None:
    """Take a transaction-scoped advisory lock on one strong-id value.

    The value is canonicalized (``strong_id_lock_value``) so verifier and
    writer converge on the same key regardless of stored formatting.
    ``pg_advisory_xact_lock`` is reentrant within the session and auto-released
    at TX end, so the gate (verify) and the enricher (write) can nest inside
    the same commit without deadlocking themselves. The client-side timeout
    bounds the wait so a stuck peer TX cannot occupy a worker lane forever
    (round-4 F6); expiry raises :class:`StrongIdLockBusy` — NOTE: the enclosing
    transaction is aborted by the cancelled statement, so callers must let this
    propagate out of their transaction context (rollback), never continue in it.
    """
    try:
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, $2))",
            f"strongid:{kind}:{strong_id_lock_value(kind, value)}",
            STRONG_ID_LOCK_SEED,
            timeout=10.0,
        )
    except TimeoutError as exc:
        raise StrongIdLockBusy(f"advisory lock busy for strong-id kind={kind}") from exc


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _name_is_junk(value: Any) -> bool:
    if value is None:
        return True
    name = " ".join(str(value).split()).strip().lower()
    if not name:
        return True
    if name == "unknown" or name.startswith("lead +") or name.startswith("lead+"):
        return True
    return name.replace("+", "").replace(" ", "").replace("-", "").isdigit()


def _name_is_better(new: Any, current: Any) -> bool:
    candidate = _clean_str(new)
    if not candidate or _name_is_junk(candidate):
        return False
    return _name_is_junk(current)


def _unwrap(raw: Any) -> Any:
    """Pull the scalar out of an intake-extract field.

    FASE-3 stores each extracted field as ``{"value": X, "confidence": .., "source_page": ..}``
    (extract.py:252), NOT a flat scalar. The HITL ``final_fields`` override path, by
    contrast, may pass flat scalars. Accept both shapes so this enricher works whether
    the values come straight from the pipeline or from a reviewer edit.
    """
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


# doc_type → list of (extract_field_key, clients_column, coercion_fn).
# Keys are the INTAKE EXTRACT SCHEMA names (backend/services/intake/extract.py),
# NOT the manual CRM endpoint's renamed keys. Columns verified to exist on the
# `clients` table (migration 041/042). Mirrors the UPDATE clients SET ... blocks in
# crm_clients_documents.py (passport L420-469, npwp L697-703, nib L834-840) and extends
# them with KITAS (columns exist; no manual endpoint enriched them before).
ENRICHMENT_MAP: dict[str, list[tuple[str, str, Callable[[Any], Any]]]] = {
    "passport": [
        ("name", "full_name", _clean_str),
        ("passport_no", "passport_number", _clean_str),
        ("expiry", "passport_expiry", _to_date),
        ("dob", "date_of_birth", _to_date),
        ("nationality", "nationality", _clean_str),
    ],
    "kitas": [
        ("name", "full_name", _clean_str),
        ("kitas_no", "kitas_number", _clean_str),
        ("expiry", "kitas_expiry_date", _to_date),
    ],
    "npwp": [
        ("npwp_number", "npwp", _npwp_digits),
    ],
    "nib": [
        ("nib_number", "nib", _digits_only),
    ],
}


async def enrich_client_from_extracted_fields(
    conn: asyncpg.Connection,
    client_id: int | None,
    doc_type: str | None,
    extracted_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Write intake-extracted identity fields onto the client's card.

    Pure-DB, single ``UPDATE clients`` (or a no-op skip). MUST be called inside the
    caller's transaction so it commits/rolls back atomically with the document write.

    Conservative by design:
    * unknown ``doc_type`` → no-op (returns ``{}``)
    * ``client_id is None`` (archive-only / no client) → no-op
    * a field absent or empty in ``extracted_fields`` → that column is left untouched
      (never overwrite an existing card value with NULL)
    * a value that fails coercion (e.g. garbage date) → that one field is skipped,
      the rest still apply; the document commit is never jeopardised by a bad field.

    Returns a ``{column: value}`` dict of what was written (for audit/response), or an
    empty dict if nothing was updated.
    """
    if client_id is None or not doc_type:
        return {}
    mapping = ENRICHMENT_MAP.get(doc_type)
    if not mapping:
        return {}
    fields = extracted_fields if isinstance(extracted_fields, dict) else {}

    # Schema-drift guard: only write columns that ACTUALLY exist on this database's
    # `clients` table. nuzantara_dev (Pro) and the Fly prod DB diverge (dev lacks
    # npwp/nib/tax_id/kitas_expiry_date as of 2026-06-16); an UPDATE naming a missing
    # column would raise UndefinedColumnError and roll back the WHOLE document commit.
    # Enrichment is best-effort metadata — it must never take down the file write.
    existing_cols = {
        r["column_name"]
        for r in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'clients' AND table_schema = current_schema()"
        )
    }

    # One upfront read of everything the loop below needs: full_name (the
    # placeholder-name guard) plus passport_number/kitas_number/custom_fields
    # (the GATE-11 verified-promotion check — a document that CONFIRMS an id
    # already on the card promotes its backfill provenance verified:false ->
    # true). Schema-drift-guarded like every column below: a DB missing one
    # of these (e.g. an older dev snapshot) just gets None for it.
    fetch_cols = [
        c for c in ("full_name", "passport_number", "kitas_number", "custom_fields")
        if c in existing_cols
    ]
    current: dict[str, Any] = {}
    if fetch_cols:
        row = await conn.fetchrow(
            f"SELECT {', '.join(fetch_cols)} FROM clients WHERE id = $1", client_id
        )
        if row:
            current = dict(row)
    current_full_name: str | None = current.get("full_name")

    written: dict[str, Any] = {}
    set_parts: list[str] = []
    params: list[Any] = []
    idx = 1
    promoted_columns: list[str] = []
    for extract_key, column, coerce in mapping:
        if column not in existing_cols:
            continue  # column not present on this DB — skip silently (schema drift)
        raw = _unwrap(fields.get(extract_key))
        if raw is None:
            continue
        value = coerce(raw)
        if value is None:
            continue
        if column == "full_name":
            if not _name_is_better(value, current_full_name):
                continue
        set_parts.append(f"{column} = ${idx}")
        params.append(value)
        written[column] = value
        idx += 1

        if column in _BACKFILL_PROVENANCE_COLUMNS:
            current_value = current.get(column)
            if current_value and _normalize_for_promotion(current_value) == _normalize_for_promotion(value):
                promoted_columns.append(column)

    # GATE-11 verified-promotion (research/operations/2026-07-18-intake-identity-
    # backfill-design.md §3 rule 11): the document just CONFIRMED an id the
    # backfill batch wrote as unverified — flip that provenance entry to
    # verified so future strong-id matches on it stop degrading to
    # LINK_CANDIDATE (see routing._classify_decision GATE-11 branch). Never
    # allowed to break the enrichment: any failure here is logged and
    # swallowed, the identifier column write above still commits.
    if promoted_columns and "custom_fields" in existing_cols:
        try:
            cf = current.get("custom_fields")
            if isinstance(cf, str):
                cf = json.loads(cf)
            if not isinstance(cf, dict):
                cf = {}
            backfill = cf.get("identity_backfill")
            mutated = False
            if isinstance(backfill, dict):
                for col in promoted_columns:
                    entry = backfill.get(col)
                    if isinstance(entry, dict) and entry.get("verified") is False:
                        entry["verified"] = True
                        entry["verified_at"] = datetime.now(timezone.utc).isoformat()
                        entry["verified_by"] = "doc-commit"
                        mutated = True
            if mutated:
                # ::text::jsonb, not a bare jsonb-typed param: some callers run
                # this on the FastAPI app pool (jsonb codec registered,
                # encoder=json.dumps) and some on the intake worker's plain
                # pool (no codec) — see writer.py's _load_json_list docstring.
                # A bare jsonb param would get double-encoded on the codec
                # pool (cicatrix discovery_jsonb_double_encoding_systemic /
                # migration 243); typing the param as text and casting
                # server-side is correct on BOTH pools.
                set_parts.append(f"custom_fields = ${idx}::text::jsonb")
                params.append(json.dumps(cf))
                idx += 1
                logger.info(
                    "intake.client_enricher: GATE-11 promoted verified=true "
                    "client=%s columns=%s",
                    client_id,
                    promoted_columns,
                )
        except Exception:
            logger.warning(
                "intake.client_enricher: GATE-11 verified-promotion failed "
                "client=%s columns=%s (enrichment continues)",
                client_id,
                promoted_columns,
                exc_info=True,
            )

    if not set_parts:
        return {}

    # Serialize against concurrent strong-id verification/writes on the same
    # value. Sorted on the CANONICAL (kind, projected value) key — the same
    # ordering every other participant uses — for a deterministic acquisition
    # order (no AB-BA between two multi-value transactions).
    lock_keys = sorted(
        (kind, strong_id_lock_value(kind, val))
        for kind, val in (
            (_STRONG_ID_LOCK_KINDS[col], val)
            for col, val in written.items()
            if col in _STRONG_ID_LOCK_KINDS and val
        )
    )
    for kind, val in lock_keys:
        await acquire_strong_id_lock(conn, kind, val)

    params.append(client_id)
    sql = f"UPDATE clients SET {', '.join(set_parts)}, updated_at = NOW() WHERE id = ${idx}"
    await conn.execute(sql, *params)
    logger.info(
        "intake.client_enricher: client=%s doc_type=%s enriched columns=%s",
        client_id,
        doc_type,
        sorted(written.keys()),
    )
    return written
