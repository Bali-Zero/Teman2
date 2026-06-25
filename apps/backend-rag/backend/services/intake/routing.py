"""Document-intake entity-resolution + routing proposal (FASE 4).

Replaces the FASE-3 ``_route_stage_stub`` with REAL entity-resolution and a
routing proposal. **READ-ONLY w.r.t. the CRM**: this module reads
``clients`` / ``companies`` / ``client_company_links`` / ``practices`` to find
candidate matches for the extracted document, but the ONLY structured write it
performs is a single ``document_routing_proposal`` row (a *proposal* a human
approves in FASE-5). It NEVER INSERTs/UPDATEs clients, companies, practices or
documents — attaching the document to a client is FASE-5 (HITL + writer).

PII / Symbiosis Law 2: all matching runs against the LOCAL Postgres only. Zero
cloud, zero third-party endpoints.

Reuse (reuse-first discipline)
------------------------------
* ``backend.services.crm.client_core.validate_passport`` — passport-number normaliser
  (upper-case + format guard), reused so the document identifier is normalised
  the same way the CRM stores/validates it.
* The pg_trgm ``%`` / ``similarity()`` fuzzy-name + ambiguity-margin cascade is
  lifted from the proven ``services/wa_copilot/identity_resolver.py`` (same
  thresholds: apply >= 0.70, review band 0.40-0.70, ambiguity margin 0.15).

Why not splink
--------------
``splink`` (DuckDB probabilistic ER, cited in spec 05e as a reuse candidate) is
NOT installed and is not warranted here: the document identifiers we match on
(passport_no, npwp, nib, akta number) are quasi-unique keys — an *exact* lookup
resolves the AUTO_ATTACH case deterministically, and pg_trgm covers the residual
fuzzy-name case natively in-DB. Adding a DuckDB-backed ER engine would be a heavy
new dependency for zero marginal precision on this key-driven problem. If a future
FASE needs many-field probabilistic linkage (e.g. dedup across noisy CRM rows),
revisit splink then.

Decision matrix (C4)
--------------------
* ``AUTO_ATTACH``    — exactly one candidate via a STRONG identifier
  (passport / npwp / nib / akta number) → high confidence, no human needed.
* ``LINK_CANDIDATE`` — a single probable match via the sender-phone signal
  (m225, conf ~0.90 — phones can be shared by spouse/agent so never auto) or
  via fuzzy name only (no strong identifier) → human confirmation recommended.
* ``AMBIGUOUS``      — >= 2 plausible candidates (homonyms!), a strong-identifier
  collision, OR a sender-phone match whose OCR subject name DISAGREES with the
  matched client (sender ≠ subject: the phone matched the FORWARDER, not the
  document holder — reason carries ``sender_subject_mismatch: true``) → human
  review mandatory, never one-click attach.
* ``NO_MATCH``       — no candidate at all → potential new client, human review.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

import asyncpg

from backend.services.intake.enqueue import PIPELINE_VERSION

logger = logging.getLogger("zantara.intake.routing")

# SSOT: the pipeline version is defined ONCE in enqueue.PIPELINE_VERSION and
# imported everywhere. Historically routing defined its own "v1" while enqueue
# used "intake-v1" — a silent drift that made routing_key
# (= sha256(queue_id|doc_index|pipeline_version)) diverge between the row that
# was enqueued and the route stage that should match it. A re-process that
# bumped the version on the queue row but left a reader on the old constant
# produced orphaned/duplicate proposals. Keep this an ALIAS, never a literal.
PIPELINE_VERSION_DEFAULT = PIPELINE_VERSION

# --- Decision-matrix C4 outcomes ---
DECISION_AUTO_ATTACH = "AUTO_ATTACH"
DECISION_LINK_CANDIDATE = "LINK_CANDIDATE"
DECISION_AMBIGUOUS = "AMBIGUOUS"
DECISION_NO_MATCH = "NO_MATCH"

# --- Thresholds (mirror wa_copilot/identity_resolver) ---
FUZZY_APPLY_THRESHOLD = 0.70       # sim >= this on a SINGLE name match → LINK_CANDIDATE
FUZZY_REVIEW_LOW = 0.40            # below this → ignore the fuzzy candidate entirely
AMBIGUITY_MARGIN = 0.15            # top1 - top2 < margin → AMBIGUOUS (homonyms)

# Confidence assigned to a strong-identifier exact match.
CONF_STRONG_EXACT = 0.99

# --- LEVA 1: noise pre-filter → quarantine ---------------------------------- #
# A proposal is NOISE (→ status 'quarantine', parked out of the review feed) when
# the document classified as 'unknown' AND OCR produced effectively no legible
# text: nothing classified it AND nothing is readable. This is the empty-OCR
# class that poisoned 782 review_pending rows in the 2026-06-12 backlog run —
# screenshots, blurred photos, stickers, illegible scans. CONSERVATIVE by design:
# an 'unknown' doc that DOES carry text (a real document the classifier merely
# failed to type) stays in normal review — only the genuinely-empty noise is
# parked. Quarantine is consultable and recoverable (never deleted).
#
# Minimum total OCR chars (across all pages) below which an 'unknown' doc is
# noise. 20 mirrors classify._normalize_ocr_text's own legibility floor (a page
# transcript shorter than 20 chars is treated as empty there too).
QUARANTINE_MIN_OCR_CHARS = 20
# Kill-switch: quarantine is ON by default for empty-OCR unknown noise. Set
# INTAKE_QUARANTINE_ENABLED=0/false/no/off (or empty) to disable parking and
# send every proposal to review_pending exactly as before. Read at call time so
# tests/ops can toggle it.
def quarantine_enabled() -> bool:
    """True unless INTAKE_QUARANTINE_ENABLED is explicitly falsy."""
    raw = os.environ.get("INTAKE_QUARANTINE_ENABLED")
    if raw is None:
        return True
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


def _ocr_char_count(classify_out: dict[str, Any]) -> int:
    """Total legible OCR chars across all pages recorded by the classify stage.

    Reads ``classify.ocr_text_per_page`` (list of ``{"text": str, ...}``) — the
    verbatim transcript the OCR stage stored. Whitespace-only text counts as 0.
    """
    pages = classify_out.get("ocr_text_per_page") or []
    total = 0
    for p in pages:
        if isinstance(p, dict):
            text = p.get("text") or ""
            total += len((text if isinstance(text, str) else "").strip())
    return total


def is_noise_proposal(doc_type: str, classify_out: dict[str, Any]) -> bool:
    """LEVA-1 noise verdict: unknown doc-type AND no legible OCR text.

    Pure function of the classify output (no DB, no re-OCR). Returns True only
    when BOTH hold — an unknown-but-legible document is NOT noise (it may be a
    real doc the classifier failed to type) and must stay in human review.
    """
    if doc_type != "unknown":
        return False
    return _ocr_char_count(classify_out) < QUARANTINE_MIN_OCR_CHARS


# --- LEVA 3: dedup wall — already-on-profile pre-filter ---------------------- #
# A document whose subject is ALREADY matched to a CRM client AND that client
# ALREADY carries a document of the same type on their kita profile is a
# RE-ARRIVAL of something already filed. It must NOT re-enter the /review queue
# for a human to catalog again — it is born 'duplicate' (out of the feed,
# consultable for audit). This is the wall Zero asked for: "quando approviamo
# non deve arrivare in pending se è già matchato col profilo e i docs su kita".
#
# Scoped to TYPED docs only (doc_type != 'unknown'): an unknown doc has no type
# to dedup against, and noise is already handled by LEVA 1.
#
# Kill-switch (default OFF): INTAKE_DEDUP_WALL_ENABLED. Read at call time.
def dedup_wall_enabled() -> bool:
    """True only if INTAKE_DEDUP_WALL_ENABLED is explicitly truthy (default OFF)."""
    return os.environ.get("INTAKE_DEDUP_WALL_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def client_already_has_doc_type(
    conn: asyncpg.Connection, client_id: int | None, doc_type: str
) -> bool:
    """True if ``client_id`` already carries a ``documents`` row of ``doc_type``
    (already filed on their kita profile).

    The dedup key is (client_id, document_type) — the SAME logical document
    re-arriving (a fresh photo, a different blob_hash) is caught here, where the
    blob-level idempotency key (writer.compute_idempotency_key) would not.
    Returns False for an unresolved client or an unknown type (nothing to dedup).

    NB: the ``documents`` table has NO ``deleted_at`` column (hard-delete only,
    verified 2026-06-21) — do not add a soft-delete filter here.
    """
    if client_id is None or not doc_type or doc_type == "unknown":
        return False
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM documents
        WHERE client_id = $1
          AND document_type = $2
        LIMIT 1
        """,
        client_id,
        doc_type,
    )
    return row is not None

# Sender-phone exact match (m225). High confidence but NEVER auto-attach: a
# phone can be shared by spouse/agent — the sender is not always the subject.
CONF_PHONE_MATCH = 0.90
# Boost applied when sender phone AND fuzzy name agree on the same client.
PHONE_NAME_AGREE_BOOST = 0.05

# Sender != subject guard (forwarder vs document holder).
# When the sender-phone matches a CRM client but the OCR-extracted SUBJECT name
# disagrees with that client, the match is driven by WHO FORWARDED the document,
# not WHOSE document it is (a Bali Zero agent/staffer forwarding a client doc).
# Such a candidate must NOT be presented as a confident one-click LINK_CANDIDATE.
#
# Calibration (live proposals, 2026-06-17):
#   * 12927 Gennaro Piraino  — phone 0.90, fuzzy name sim 0.6154, SAME client id
#       (sender IS the subject, just OCR noise) → must stay LINK_CANDIDATE.
#   * 12693 Yanti BS / 12682 Adi Bayu Santero / 16251 Andrea 23 Paradise —
#       phone 0.90 but the OCR subject name does NOT resolve to the phone client
#       (no corroborating fuzzy candidate ≥ this floor) → flagged & downgraded.
# The trigger is genuine name DISAGREEMENT (different person / no corroboration
# despite a name being present), NEVER merely "name_sim < 1.0": same-client trgm
# agreement at 0.62 passes, a different-person name is flagged.
SENDER_SUBJECT_AGREE_MIN_SIM = 0.45

# Folder-name match (m227). Drive-intake blobs arrive under a per-client folder
# (Dropbox-Intake/<Client Name>/...): the transport layer knows WHICH FOLDER the
# blob came from, like the phone knows who sent it. Human-typed and shared-folder
# prone → slightly below the phone signal and NEVER auto-attach alone.
CONF_FOLDER_MATCH = 0.85

# Doc-types whose subject is a PERSON (match against ``clients``) vs a COMPANY
# (match against ``companies``). canonical_doc_type() upstream already maps
# aliases (paspor->passport, akta->akta_pendirian, ...).
_PERSON_DOC_TYPES = frozenset(
    {
        "passport", "npwp", "kitas", "itk", "itas", "itap", "ktp", "visa",
        "family_card", "birth_certificate", "marriage_certificate",
    }
)
_COMPANY_DOC_TYPES = frozenset(
    {"nib", "akta_pendirian", "profil_perseroan", "sk_kemenkumham"}
)

# NB: a bare "npwp" doc can be a PERSON npwp or a COMPANY npwp. We try the company
# match first when the npwp resolves a company row, else fall back to person.


# ---------------------------------------------------------------------------
# Field-value extraction helpers (read the FASE-3 extract payload)
# ---------------------------------------------------------------------------

def _field_value(fields: dict[str, Any], name: str) -> Any:
    """Pull a scalar value out of the FASE-3 ``fields`` map.

    extract.py stores each field as ``{"value": v, "confidence": c,
    "source_page": p}``; older/looser payloads may store a bare scalar. A
    ``null``/empty value returns ``None``.
    """
    raw = fields.get(name)
    if isinstance(raw, dict):
        val = raw.get("value")
    else:
        val = raw
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    return val


def _normalize_id(value: Any) -> str | None:
    """Normalise a quasi-unique identifier for exact comparison.

    Strips spaces / dots / dashes (NPWP is often written ``01.234.567.8-901.000``;
    NIB may carry spaces) and upper-cases. Returns None for empties.
    """
    if value is None:
        return None
    s = re.sub(r"[\s.\-/]", "", str(value)).upper()
    return s or None


def _normalize_passport(value):
    """Normalise a passport number: strip separators + upper-case.

    Mirrors backend.services.crm.client_core ClientValidator.validate_passport
    (which upper-cases and guards [A-Z0-9]); we additionally strip separators so a
    document value like "X 123456" matches a stored "X123456".
    """
    norm = _normalize_id(value)
    if not norm:
        return None
    return norm


def _digits_only(value: Any) -> str | None:
    """Digits-only projection (for NPWP/NIB numeric comparison)."""
    if value is None:
        return None
    d = re.sub(r"\D", "", str(value))
    return d or None


def _looks_like_company_name(value: str) -> bool:
    """True for common Indonesian company/entity prefixes."""
    normalized = re.sub(r"\s+", " ", value.strip().upper())
    return normalized.startswith(("PT ", "CV ", "UD ", "YAYASAN ", "PT."))


def normalize_sender_phone(value: Any) -> str | None:
    """Normalise a sender phone for ``clients.phone_normalized`` matching.

    Digits-only (strips spaces / ``+`` / separators), Indonesian leading ``0``
    → ``62``, bare ``8…`` → ``62…``, <8 digits rejected. The algorithm MIRRORS
    ``backend.services.crm.client_core.normalize_phone_e164`` (minus the ``+``
    prefix, dropped so callers can probe BOTH ``phone_normalized`` storage
    variants — same dual-form lookup as wa_copilot/identity_resolver).

    Deliberately INLINED, not imported: the client_core import chain pulls
    ``backend.app.core.config.Settings()`` (requires JWT_SECRET_KEY/API_KEYS
    env), which would crash the sovereign-local intake worker at import time.
    Keep in sync with client_core if the E.164 rules ever change.
    """
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 8:
        return None
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------

async def _match_person_strong(
    conn: asyncpg.Connection, extracted: dict[str, Any]
) -> list[dict[str, Any]]:
    """Strong-identifier match against ``clients`` (passport / kitas number)."""
    candidates: list[dict[str, Any]] = []

    passport = _field_value(extracted, "passport_no") or _field_value(extracted, "passport_number")
    if passport:
        # Normalise the same way the CRM ClientValidator.validate_passport does
        # (upper-case + [A-Z0-9] guard), plus strip separators for robust match.
        norm = _normalize_passport(passport)
        if norm:
            rows = await conn.fetch(
                """
                SELECT id, full_name
                FROM clients
                WHERE deleted_at IS NULL
                  AND UPPER(REGEXP_REPLACE(passport_number, '[\\s.\\-/]', '', 'g')) = $1
                """,
                norm,
            )
            for r in rows:
                candidates.append({
                    "table": "clients", "id": r["id"], "name": r["full_name"],
                    "method": "passport_number", "score": CONF_STRONG_EXACT,
                    "matched_value": norm,
                })

    kitas = (
        _field_value(extracted, "kitas_no")
        or _field_value(extracted, "kitas_number")
        or _field_value(extracted, "itap_no")
        or _field_value(extracted, "itk_no")
        or _field_value(extracted, "stay_permit_no")
    )
    if kitas:
        norm = _normalize_id(kitas)
        if norm:
            rows = await conn.fetch(
                """
                SELECT id, full_name
                FROM clients
                WHERE deleted_at IS NULL
                  AND UPPER(REGEXP_REPLACE(kitas_number, '[\\s.\\-/]', '', 'g')) = $1
                """,
                norm,
            )
            for r in rows:
                candidates.append({
                    "table": "clients", "id": r["id"], "name": r["full_name"],
                    "method": "kitas_number", "score": CONF_STRONG_EXACT,
                    "matched_value": norm,
                })

    return candidates


async def _match_company_strong(
    conn: asyncpg.Connection, extracted: dict[str, Any]
) -> list[dict[str, Any]]:
    """Strong-identifier match against ``companies`` (nib / npwp_company / akta no)."""
    candidates: list[dict[str, Any]] = []

    nib = _field_value(extracted, "nib_number") or _field_value(extracted, "nib")
    if nib:
        norm = _digits_only(nib)
        if norm:
            rows = await conn.fetch(
                """
                SELECT id, company_name
                FROM companies
                WHERE REGEXP_REPLACE(nib, '\\D', '', 'g') = $1
                """,
                norm,
            )
            for r in rows:
                candidates.append({
                    "table": "companies", "id": r["id"], "name": r["company_name"],
                    "method": "nib", "score": CONF_STRONG_EXACT, "matched_value": norm,
                })

    npwp = _field_value(extracted, "npwp_number") or _field_value(extracted, "npwp")
    if npwp:
        norm = _digits_only(npwp)
        if norm:
            rows = await conn.fetch(
                """
                SELECT id, company_name
                FROM companies
                WHERE REGEXP_REPLACE(npwp_company, '\\D', '', 'g') = $1
                """,
                norm,
            )
            for r in rows:
                candidates.append({
                    "table": "companies", "id": r["id"], "name": r["company_name"],
                    "method": "npwp_company", "score": CONF_STRONG_EXACT,
                    "matched_value": norm,
                })

    akta = _field_value(extracted, "akta_pendirian_no")
    if akta:
        norm = _normalize_id(akta)
        if norm:
            rows = await conn.fetch(
                """
                SELECT id, company_name
                FROM companies
                WHERE UPPER(REGEXP_REPLACE(akta_pendirian_no, '[\\s.\\-/]', '', 'g')) = $1
                """,
                norm,
            )
            for r in rows:
                candidates.append({
                    "table": "companies", "id": r["id"], "name": r["company_name"],
                    "method": "akta_pendirian_no", "score": CONF_STRONG_EXACT,
                    "matched_value": norm,
                })

    return candidates


async def _match_sender_phone(
    conn: asyncpg.Connection, sender_phone: str | None
) -> list[dict[str, Any]]:
    """Exact match of the transport-layer sender phone against ``clients``.

    Matches ``clients.phone_normalized`` in both storage variants (with and
    without the leading ``+`` — same dual lookup as wa_copilot's
    identity_resolver). LIMIT 3: one row is the signal; >1 row means the phone
    is shared (spouse/agent/office line) and the decision matrix degrades it to
    AMBIGUOUS rather than guessing.
    """
    norm = normalize_sender_phone(sender_phone)
    if not norm:
        return []
    rows = await conn.fetch(
        """
        SELECT id, full_name
        FROM clients
        WHERE deleted_at IS NULL
          AND phone_normalized IN ($1, $2)
        ORDER BY id
        LIMIT 3
        """,
        norm,
        "+" + norm,
    )
    return [
        {
            "table": "clients", "id": r["id"], "name": r["full_name"],
            "method": "sender_phone", "score": CONF_PHONE_MATCH,
            "matched_value": norm, "basis": "phone",
        }
        for r in rows
    ]


def _clean_folder_segment(value: Any) -> str | None:
    """Normalise the first path segment of ``source_path`` into a name to match.

    Real Dropbox folders carry human decorations — ``###PERPANJANGAN KITAS
    JOHN DOE###``, ``@arsip Cetak (2027)`` — so strip non-name punctuation and
    parenthetical suffixes, collapse whitespace, reject <3 chars.
    """
    if value is None:
        return None
    seg = str(value).split("/", 1)[0]
    seg = re.sub(r"\([^)]*\)", " ", seg)        # drop parenthetical suffixes
    seg = re.sub(r"[#@_*\[\]{}!]+", " ", seg)   # drop decoration characters
    seg = re.sub(r"\s+", " ", seg).strip()
    if len(seg) < 3:
        return None
    return seg


async def _match_folder_name(
    conn: asyncpg.Connection, source_path: str | None
) -> list[dict[str, Any]]:
    """Folder-name match (m227): first ``source_path`` segment vs CRM names.

    Fuzzy (pg_trgm) against ``clients.full_name`` AND ``companies.company_name``;
    only a similarity >= FUZZY_APPLY_THRESHOLD counts as a transport hint (a weak
    folder sim is noise — unlike the OCR-name fuzzy, which has its own review
    band). One clear winner → a single CONF_FOLDER_MATCH candidate; top-2 inside
    the ambiguity margin → both returned so the decision matrix degrades to
    AMBIGUOUS rather than guessing.
    """
    name = _clean_folder_segment(source_path)
    if not name:
        return []
    merged = await _match_fuzzy_name(conn, "clients", "full_name", name)
    merged += await _match_fuzzy_name(conn, "companies", "company_name", name)
    usable = [c for c in merged if c["score"] >= FUZZY_APPLY_THRESHOLD]
    usable.sort(key=lambda c: c["score"], reverse=True)
    if not usable:
        return []

    def _as_hint(c: dict[str, Any]) -> dict[str, Any]:
        return {
            "table": c["table"], "id": c["id"], "name": c["name"],
            "method": "folder_name", "score": CONF_FOLDER_MATCH,
            "matched_value": name, "basis": "folder", "folder_sim": c["score"],
        }

    if len(usable) >= 2 and usable[0]["score"] - usable[1]["score"] < AMBIGUITY_MARGIN:
        return [_as_hint(usable[0]), _as_hint(usable[1])]
    return [_as_hint(usable[0])]


async def _match_fuzzy_name(
    conn: asyncpg.Connection, table: str, name_col: str, name: str
) -> list[dict[str, Any]]:
    """pg_trgm fuzzy match on a name column. Returns top-2 with similarity.

    Reuses the wa_copilot/identity_resolver trgm pattern (``%`` operator + LIMIT 2
    so the caller can apply the ambiguity margin).
    """
    if not name or len(name.strip()) < 3:
        return []
    rows = await conn.fetch(
        f"""
        SELECT id, {name_col} AS name, similarity({name_col}, $1) AS sim
        FROM {table}
        WHERE {name_col} %% $1
        ORDER BY sim DESC
        LIMIT 2
        """.replace("%%", "%"),
        name.strip(),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "table": table, "id": r["id"], "name": r["name"],
            "method": f"fuzzy_{name_col}", "score": round(float(r["sim"]), 4),
            "matched_value": name.strip(),
        })
    return out


def _classify_decision(
    strong: list[dict[str, Any]],
    fuzzy: list[dict[str, Any]],
    phone: list[dict[str, Any]] | None = None,
    subject_name: str | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Apply the C4 decision matrix to strong + transport-hint + fuzzy lists.

    ``phone`` carries the transport-layer hint candidates — sender-phone (m225)
    or folder-name (m227); each candidate self-describes via its ``basis`` key.
    Precedence: strong document identifiers > transport hint > fuzzy name. The
    hint NEVER yields AUTO_ATTACH on its own (a phone can be shared by
    spouse/agent; a folder can hold a family's documents): alone it is a
    LINK_CANDIDATE; agreeing with the top fuzzy name it is a boosted
    LINK_CANDIDATE; disagreeing, BOTH are surfaced for review; matching >1 row
    it degrades to AMBIGUOUS.

    ``subject_name`` is the OCR-extracted SUBJECT name (person or company) of the
    document, when present. It lets the matrix tell apart two phone-only cases
    that otherwise look identical: (a) the doc carries NO subject name → the
    phone is the only signal, keep the conservative LINK_CANDIDATE; (b) the doc
    DOES carry a subject name but it does NOT corroborate the phone-matched
    client → the phone matched WHO FORWARDED the doc, not whose doc it is
    (sender ≠ subject). Case (b) is flagged ``sender_subject_mismatch`` and
    downgraded to AMBIGUOUS so a human must confirm — never one-click attach.

    Returns ``(decision, candidates, reason)``.
    """
    phone = list(phone or [])
    hint_label = (
        "folder name" if phone and phone[0].get("basis") == "folder" else "sender phone"
    )
    hint_score_key = "folder_score" if hint_label == "folder name" else "phone_score"
    # How to phrase the sender != subject downgrade: a phone names a FORWARDER,
    # a folder names a CARRIER context — both are "who delivered it", not "whose".
    hint_role = "the folder" if hint_label == "folder name" else "the FORWARDER"

    # De-dup strong candidates by (table, id).
    seen: set[tuple[str, int]] = set()
    uniq_strong: list[dict[str, Any]] = []
    for c in strong:
        key = (c["table"], c["id"])
        if key not in seen:
            seen.add(key)
            uniq_strong.append(c)

    # 1) Strong identifier(s) present — the phone signal is IGNORED here: the
    #    document identifier describes the SUBJECT, the phone only the SENDER.
    if uniq_strong:
        if len(uniq_strong) == 1:
            return DECISION_AUTO_ATTACH, uniq_strong, {
                "reason": "single strong-identifier match",
                "method": uniq_strong[0]["method"],
            }
        # >1 distinct row sharing the same strong identifier = data collision.
        return DECISION_AMBIGUOUS, uniq_strong, {
            "reason": f"{len(uniq_strong)} rows share a strong identifier (collision)",
        }

    usable = [c for c in fuzzy if c["score"] >= FUZZY_REVIEW_LOW]
    usable.sort(key=lambda c: c["score"], reverse=True)

    # 2) Transport-hint signal — sender phone / folder name (no strong id).
    if phone:
        if len(phone) > 1:
            return DECISION_AMBIGUOUS, phone, {
                "reason": f"{len(phone)} clients share the {hint_label}",
            }
        pc = phone[0]
        # Did the document carry a real SUBJECT name to corroborate the hint?
        has_subject_name = bool(subject_name and subject_name.strip())
        if usable:
            top_f = usable[0]
            if (
                top_f["table"] == pc["table"]
                and top_f["id"] == pc["id"]
                and top_f["score"] >= SENDER_SUBJECT_AGREE_MIN_SIM
            ):
                # Hint + name agree on the SAME client (OCR noise tolerated) →
                # boosted candidate. This is the innocence case (e.g. 12927:
                # same client, name_sim 0.62) — must NOT be flagged.
                boosted = dict(pc)
                boosted["score"] = round(
                    min(CONF_STRONG_EXACT - 0.01, pc["score"] + PHONE_NAME_AGREE_BOOST), 4
                )
                boosted["method"] = f"{pc['method']}+{top_f['method']}"
                return DECISION_LINK_CANDIDATE, [boosted], {
                    "reason": f"{hint_label} and fuzzy name agree on the same client",
                    hint_score_key: pc["score"], "name_sim": top_f["score"],
                }
            # Hint and name point at DIFFERENT clients (the doc subject is a
            # different person than the sender) → sender ≠ subject. Downgrade to
            # AMBIGUOUS: the phone matched the FORWARDER, not the document holder.
            return DECISION_AMBIGUOUS, [pc, top_f], {
                "reason": (
                    f"{hint_label} matched {hint_role}, not the document "
                    f"subject — confirm this is {pc.get('name')}'s document"
                ),
                hint_score_key: pc["score"], "name_sim": top_f["score"],
                "sender_subject_mismatch": True,
                "subject_name": (subject_name or "").strip() or None,
            }
        if has_subject_name:
            # A subject name WAS extracted but resolved to NO client at all (not
            # even a weak fuzzy hit ≥ 0.40): the named subject is unknown to the
            # CRM while the phone matches the sender → sender ≠ subject again.
            # Flag for human confirmation rather than a confident one-click link.
            return DECISION_AMBIGUOUS, [pc], {
                "reason": (
                    f"{hint_label} matched {hint_role}, not the document "
                    f"subject — confirm this is {pc.get('name')}'s document"
                ),
                hint_score_key: pc["score"],
                "sender_subject_mismatch": True,
                "subject_name": subject_name.strip(),
            }
        # No subject name on the document at all → the phone is the only signal
        # and we cannot prove a mismatch. Keep the conservative LINK_CANDIDATE.
        return DECISION_LINK_CANDIDATE, [pc], {
            "reason": f"{hint_label} match (no strong identifier, no fuzzy name)",
            hint_score_key: pc["score"],
        }

    # 3) No strong identifier, no transport hint → fuzzy name candidates only.
    if not usable:
        return DECISION_NO_MATCH, [], {"reason": "no strong identifier, no fuzzy name >= 0.40"}

    top = usable[0]

    # >= 2 plausible names within the ambiguity margin → homonym ambiguity.
    if len(usable) >= 2:
        second = usable[1]
        if top["score"] - second["score"] < AMBIGUITY_MARGIN:
            return DECISION_AMBIGUOUS, usable[:2], {
                "reason": "homonyms: top-2 fuzzy names within ambiguity margin",
                "top_sim": top["score"], "second_sim": second["score"],
            }

    # Single clear fuzzy candidate.
    if top["score"] >= FUZZY_APPLY_THRESHOLD:
        return DECISION_LINK_CANDIDATE, [top], {
            "reason": "single fuzzy name match, no strong identifier",
            "top_sim": top["score"],
        }
    # In review band (0.40-0.70) but below apply → still a (weak) candidate to confirm.
    return DECISION_LINK_CANDIDATE, [top], {
        "reason": "weak fuzzy name match in review band",
        "top_sim": top["score"], "review_band": True,
    }


async def resolve_entity(
    extracted_fields: dict[str, Any],
    doc_type: str | None,
    pool: asyncpg.Pool | asyncpg.Connection,
    *,
    sender_phone: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Resolve the document subject against existing CRM rows (READ-ONLY).

    ``sender_phone`` (m225) is the raw transport-layer sender number; it is
    consulted only when no strong document identifier matched, as a
    high-confidence (~0.90) person hint — see :func:`_classify_decision`.
    ``source_path`` (m227) is the Drive-intake folder path relative to the
    watched root (``<Client Name>/file.pdf``); its first segment is consulted
    only when neither a strong identifier nor the phone resolved (~0.85 hint).

    Returns a dict::

        {
          "decision": "AUTO_ATTACH" | "LINK_CANDIDATE" | "AMBIGUOUS" | "NO_MATCH",
          "candidates": [ {table, id, name, method, score, matched_value}, ... ],
          "reason": {...},
          "subject_kind": "person" | "company" | "unknown",
          "doc_type": <doc_type>,
        }
    """
    dt = (doc_type or "").strip().lower()

    async def _run(conn: asyncpg.Connection) -> dict[str, Any]:
        strong: list[dict[str, Any]] = []
        fuzzy: list[dict[str, Any]] = []
        phone: list[dict[str, Any]] = []
        subject_kind = "unknown"

        # COMPANY-side identifiers (nib/npwp company/akta) — try first when the
        # doc-type is company-ish OR when a company strong-id is present.
        if dt in _COMPANY_DOC_TYPES or dt == "npwp":
            strong += await _match_company_strong(conn, extracted_fields)
            if strong:
                subject_kind = "company"

        # PERSON-side identifiers (passport/kitas) — and person npwp fallback.
        if not strong and (dt in _PERSON_DOC_TYPES or dt == "npwp" or dt == "unknown"):
            strong += await _match_person_strong(conn, extracted_fields)
            if strong:
                subject_kind = "person"

        # If still nothing strong and doc is company-ish, also try person strong
        # (defensive: a misclassified doc still gets a chance).
        if not strong and dt in _COMPANY_DOC_TYPES:
            strong += await _match_person_strong(conn, extracted_fields)
            if strong:
                subject_kind = "person"

        # Sender-phone signal (m225) — the transport layer knows who SENT the
        # blob. Only consulted when no strong identifier resolved (a strong ID
        # names the SUBJECT; the phone names the SENDER — document wins).
        if not strong and sender_phone:
            phone = await _match_sender_phone(conn, sender_phone)
            if phone and subject_kind == "unknown":
                subject_kind = "person"

        # Folder-name signal (m227) — Drive intake knows WHICH FOLDER the blob
        # arrived in (Dropbox-Intake/<Client Name>/...). Consulted only when
        # neither a strong identifier nor the sender phone resolved.
        if not strong and not phone and source_path:
            phone = await _match_folder_name(conn, source_path)
            if phone and subject_kind == "unknown":
                subject_kind = "person" if phone[0]["table"] == "clients" else "company"

        # Fuzzy name fallback (only matters when no strong identifier resolved).
        # ``subject_name`` is the document's OCR-extracted subject (company or
        # person) — passed to the decision matrix so a sender-phone hit whose
        # named subject DISAGREES with the matched client is flagged sender ≠
        # subject (forwarder, not document holder) instead of confident-linked.
        subject_name: str | None = None
        if not strong:
            company_name = _field_value(extracted_fields, "company_name")
            account_holder = _field_value(extracted_fields, "account_holder")
            if (
                not company_name
                and dt == "bank_statement"
                and account_holder
                and _looks_like_company_name(str(account_holder))
            ):
                company_name = account_holder
            person_name = (
                _field_value(extracted_fields, "name")
                or _field_value(extracted_fields, "full_name")
            )
            if (
                not person_name
                and dt == "bank_statement"
                and account_holder
                and not _looks_like_company_name(str(account_holder))
            ):
                person_name = account_holder
            subject_name = (
                str(company_name) if company_name
                else (str(person_name) if person_name else None)
            )
            if company_name:
                fuzzy += await _match_fuzzy_name(conn, "companies", "company_name", str(company_name))
                if fuzzy:
                    subject_kind = "company"
            if person_name:
                pf = await _match_fuzzy_name(conn, "clients", "full_name", str(person_name))
                fuzzy += pf
                if pf and subject_kind == "unknown":
                    subject_kind = "person"

        decision, candidates, reason = _classify_decision(
            strong, fuzzy, phone, subject_name=subject_name
        )
        return {
            "decision": decision,
            "candidates": candidates,
            "reason": reason,
            "subject_kind": subject_kind,
            "doc_type": doc_type,
        }

    if isinstance(pool, asyncpg.Connection):
        return await _run(pool)
    async with pool.acquire() as conn:
        return await _run(conn)


# ---------------------------------------------------------------------------
# Routing target (READ-ONLY lookup of owning client + open practice)
# ---------------------------------------------------------------------------

async def _resolve_routing_target(
    conn: asyncpg.Connection, entity: dict[str, Any]
) -> dict[str, Any]:
    """From the resolved entity, derive where the doc WOULD go (no write).

    * client doc → client_id directly.
    * company doc → the company's PRIMARY linked client via client_company_links.
    Then look up the most recent open practice for that client as a routing hint.
    """
    if entity["decision"] not in (DECISION_AUTO_ATTACH, DECISION_LINK_CANDIDATE):
        return {"client_id": None, "company_id": None, "practice_id": None,
                "practice_hint": None}

    cand = entity["candidates"][0]
    client_id: int | None = None
    company_id: int | None = None

    if cand["table"] == "clients":
        client_id = cand["id"]
    elif cand["table"] == "companies":
        company_id = cand["id"]
        link = await conn.fetchrow(
            """
            SELECT client_id
            FROM client_company_links
            WHERE company_id = $1
            ORDER BY is_primary DESC NULLS LAST, start_date DESC NULLS LAST
            LIMIT 1
            """,
            company_id,
        )
        if link:
            client_id = link["client_id"]

    practice_id = None
    practice_hint = None
    if client_id is not None:
        prow = await conn.fetchrow(
            """
            SELECT id, practice_type_code, status
            FROM practices
            WHERE client_id = $1
              AND status NOT IN ('completed')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            client_id,
        )
        if prow:
            practice_id = prow["id"]
            practice_hint = {
                "practice_type_code": prow["practice_type_code"],
                "status": prow["status"],
            }

    return {
        "client_id": client_id,
        "company_id": company_id,
        "practice_id": practice_id,
        "practice_hint": practice_hint,
    }


# ---------------------------------------------------------------------------
# Proposal builder
# ---------------------------------------------------------------------------

def _make_routing_key(queue_id: int, doc_index: int, pipeline_version: str) -> str:
    raw = f"{queue_id}|{doc_index}|{pipeline_version}"
    return "rk:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


async def build_routing_proposal(
    queue_id: int,
    extracted: dict[str, Any],
    doc_type: str | None,
    pool: asyncpg.Pool | asyncpg.Connection,
    *,
    doc_index: int = 0,
    pipeline_version: str = PIPELINE_VERSION_DEFAULT,
    sender_phone: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Build (but do NOT persist) the routing proposal payload.

    Returns a dict with the four JSONB columns plus routing_key, ready to INSERT
    into ``document_routing_proposal``.
    """
    async def _run(conn: asyncpg.Connection) -> dict[str, Any]:
        entity = await resolve_entity(
            extracted, doc_type, conn,
            sender_phone=sender_phone, source_path=source_path,
        )
        target = await _resolve_routing_target(conn, entity)

        decision = entity["decision"]
        requires_human = decision != DECISION_AUTO_ATTACH

        entity_resolution = {
            "decision": decision,
            "subject_kind": entity["subject_kind"],
            "candidates": entity["candidates"],
            "reason": entity["reason"],
            "doc_type": doc_type,
        }
        routing = {
            "client_id": target["client_id"],
            "company_id": target["company_id"],
            "practice_id": target["practice_id"],
            "practice_hint": target["practice_hint"],
            "doc_type": doc_type,
        }
        commit_gate = {
            "requires_human": requires_human,
            "decision": decision,
            "reason": entity["reason"].get("reason"),
            "auto_attach_eligible": decision == DECISION_AUTO_ATTACH
            and target["client_id"] is not None,
            "fase": "4-routing",
        }
        return {
            "routing_key": _make_routing_key(queue_id, doc_index, pipeline_version),
            "doc_index": doc_index,
            "pipeline_version": pipeline_version,
            "entity_resolution": entity_resolution,
            "routing": routing,
            "commit_gate": commit_gate,
        }

    if isinstance(pool, asyncpg.Connection):
        return await _run(pool)
    async with pool.acquire() as conn:
        return await _run(conn)


# ---------------------------------------------------------------------------
# Stage handler (replaces FASE-3 _route_stage_stub)
# ---------------------------------------------------------------------------

async def _fetch_stage_output(conn: asyncpg.Connection, queue_id: int) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT stage_output FROM intake_queue WHERE id = $1", queue_id
    )
    if row is None or row["stage_output"] is None:
        return {}
    so = row["stage_output"]
    if isinstance(so, str):
        try:
            return json.loads(so)
        except json.JSONDecodeError:
            return {}
    return dict(so)


async def backfill_received_by(
    conn: asyncpg.Connection, queue_id: int, client_id: int | None
) -> str | None:
    """Give an owner-less queue row a reviewer: the matched client's consultant.

    Docs from the SHARED business line (``whatsapp-live:*``) and Drive arrive
    with ``received_by IS NULL`` — nobody's dashboard shows them (admin-only
    pool). When routing resolves a client, the most natural reviewer is that
    client's assigned consultant: backfill ``intake_queue.received_by`` with
    ``clients.assigned_to`` so the document lands on THEIR review feed + login
    gate, exactly like a doc received on their own mirrored chat.

    Never overwrites an existing received_by (own-chat receiver wins). Returns
    the backfilled email, or None when nothing was written.
    """
    if client_id is None:
        return None
    row = await conn.fetchrow(
        """
        UPDATE intake_queue q
           SET received_by = lower(c.assigned_to)
          FROM clients c
         WHERE q.id = $1
           AND q.received_by IS NULL
           AND c.id = $2
           AND c.deleted_at IS NULL
           AND c.assigned_to IS NOT NULL
           AND c.assigned_to <> ''
        RETURNING q.received_by
        """,
        queue_id,
        client_id,
    )
    return row["received_by"] if row else None


async def route_stage(job: dict, stage: str, pool: asyncpg.Pool) -> dict:  # noqa: ARG001 — StageHandler contract
    """FASE-4 real ``route`` stage handler.

    Reads the extracted fields from the job's accumulated ``stage_output``,
    resolves the entity, builds the routing proposal, and INSERTs exactly ONE
    ``document_routing_proposal`` row (status ``review_pending``). Idempotent via
    ``ON CONFLICT (routing_key) DO NOTHING``. ZERO CRM writes.

    Owner backfill: when the queue row has no ``received_by`` (shared business
    line / Drive) and routing resolved a client, the client's assigned
    consultant becomes the reviewer (:func:`backfill_received_by`) — every
    matched document lands on a real person's dashboard.
    """
    queue_id = job["id"]

    async with pool.acquire() as conn:
        so = job.get("stage_output")
        if not isinstance(so, dict) or not so:
            so = await _fetch_stage_output(conn, queue_id)
        classify_out = so.get("classify") or {}
        extract_out = so.get("extract") or {}

        doc_type = (
            extract_out.get("doc_type")
            or classify_out.get("doc_type")
            or "unknown"
        )
        fields = extract_out.get("fields") or {}

        # The worker's claim RETURNING carries neither sender_phone (m225) nor
        # pipeline_version — read BOTH from the queue row. pipeline_version is
        # LOAD-BEARING for the retroactive reprocess: the bumped value must
        # reach _make_routing_key, else the old routing_key collides and
        # ON CONFLICT silently drops the fresh proposal.
        qrow = await conn.fetchrow(
            "SELECT sender_phone, source_path, pipeline_version"
            " FROM intake_queue WHERE id = $1",
            queue_id,
        )
        sender_phone = job.get("sender_phone") or (qrow["sender_phone"] if qrow else None)
        source_path = job.get("source_path") or (qrow["source_path"] if qrow else None)
        pipeline_version = (
            job.get("pipeline_version")
            or (qrow["pipeline_version"] if qrow else None)
            or PIPELINE_VERSION_DEFAULT
        )

        proposal = await build_routing_proposal(
            queue_id, fields, doc_type, conn,
            pipeline_version=pipeline_version,
            sender_phone=sender_phone,
            source_path=source_path,
        )

        # LEVA 1 — noise pre-filter. When the doc is unreadable noise (unknown
        # type + no legible OCR) AND the parking is armed, the proposal is born
        # in 'quarantine' (parked out of the review feed, consultable +
        # recoverable), never review_pending. The verdict is recorded on the
        # commit_gate either way so the reason is auditable.
        noise = is_noise_proposal(doc_type, classify_out)
        proposal["commit_gate"]["noise"] = noise

        # LEVA 3 — dedup wall (Zero 2026-06-21). If the resolved client ALREADY
        # carries a document of this type on their kita profile, this is a
        # re-arrival of something already filed: it must NOT re-enter /review for
        # a human to re-catalog. Born 'duplicate' (parked, consultable), never
        # review_pending. Scoped to typed docs with a resolved client; armed by
        # INTAKE_DEDUP_WALL_ENABLED (default OFF). Checked AFTER noise so genuine
        # noise still wins the 'quarantine' label.
        resolved_client_id = proposal["routing"]["client_id"]
        is_dup = False
        if not noise:
            is_dup = await client_already_has_doc_type(conn, resolved_client_id, doc_type)
        proposal["commit_gate"]["dedup_already_on_profile"] = is_dup

        if noise and quarantine_enabled():
            initial_status = "quarantine"
        elif is_dup and dedup_wall_enabled():
            initial_status = "duplicate"
        else:
            initial_status = "review_pending"

        proposal_id = await conn.fetchval(
            """
            INSERT INTO document_routing_proposal
                (queue_id, doc_index, pipeline_version, routing_key,
                 entity_resolution, routing, commit_gate, status)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8)
            ON CONFLICT (routing_key) DO NOTHING
            RETURNING id
            """,
            queue_id,
            proposal["doc_index"],
            proposal["pipeline_version"],
            proposal["routing_key"],
            json.dumps(proposal["entity_resolution"]),
            json.dumps(proposal["routing"]),
            json.dumps(proposal["commit_gate"]),
            initial_status,
        )

        if proposal_id is None:
            # Conflict: a proposal with this routing_key already existed.
            existing = await conn.fetchrow(
                "SELECT id, status FROM document_routing_proposal WHERE routing_key = $1",
                proposal["routing_key"],
            )
            proposal_id = existing["id"] if existing else None
            already = True

            # ANTI-DEADLOCK GUARD (done-deadlock fix). The bare ON CONFLICT DO
            # NOTHING above silently dropped the fresh proposal whenever the key
            # collided. If the surviving row is 'superseded' (a re-process bumped
            # the version, marked the old proposal superseded, but the same key
            # was re-derived) the document would be lost: the queue advances to
            # 'done' while NO live proposal exists, so it never appears in
            # /review and the worker (which only claims non-'done' rows) never
            # revisits it. Revive a superseded survivor back to 'review_pending'
            # so a re-route always leaves a reviewable proposal. 'rejected'/
            # 'routed'/'review_pending'/'review_claimed' are intentional human
            # (or in-flight) states and are left untouched.
            if existing is not None and existing["status"] == "superseded":
                await conn.execute(
                    """
                    UPDATE document_routing_proposal
                       SET status           = 'review_pending',
                           entity_resolution = $2::jsonb,
                           routing           = $3::jsonb,
                           commit_gate       = $4::jsonb,
                           lease_owner       = NULL,
                           lease_expires_at  = NULL,
                           claim_token       = NULL
                     WHERE id = $1
                       AND status = 'superseded'
                    """,
                    proposal_id,
                    json.dumps(proposal["entity_resolution"]),
                    json.dumps(proposal["routing"]),
                    json.dumps(proposal["commit_gate"]),
                )
                logger.warning(
                    "route(FASE4): revived superseded-orphan proposal_id=%s "
                    "queue=%s back to review_pending (anti-deadlock guard)",
                    proposal_id, queue_id,
                )
        else:
            already = False

        # Owner backfill: a NULL-received_by doc that matched a client goes to
        # that client's consultant dashboard (idempotent: never overwrites).
        backfilled_owner = await backfill_received_by(
            conn, queue_id, proposal["routing"]["client_id"]
        )

    decision = proposal["entity_resolution"]["decision"]
    logger.info(
        "route(FASE4): job=%s proposal_id=%s decision=%s requires_human=%s "
        "client_id=%s status=%s noise=%s dedup=%s (0 CRM writes)",
        queue_id, proposal_id, decision,
        proposal["commit_gate"]["requires_human"],
        proposal["routing"]["client_id"],
        initial_status, noise, is_dup,
    )
    return {
        "routed": False,
        "proposal_id": proposal_id,
        "routing_key": proposal["routing_key"],
        "doc_type": doc_type,
        "decision": decision,
        "requires_human": proposal["commit_gate"]["requires_human"],
        "status": initial_status,
        "noise": noise,
        "dedup_already_on_profile": is_dup,
        "idempotent_skip": already,
        "received_by_backfilled": backfilled_owner,
        "_metric": {"model": "entity-resolution-fase4", "confidence": 1.0},
    }
