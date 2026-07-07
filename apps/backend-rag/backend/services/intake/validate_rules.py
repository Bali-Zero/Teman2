"""Deterministic document-intake validation (FASE 3 β — 'validate' stage).

PURE PYTHON — no LLM. Every check is a regex / format / cross-reference rule:
the extraction model (extract.py) may be wrong, so this stage is the hard,
auditable gate. Rules verified against the existing CRM extraction path
(crm_clients_documents.py: NIB 13 digits, NPWP 15 digits; pii_scanner.py:
NPWP_NEW_16 = NIK-based 16-digit format introduced 2024).

KBLI validation is DYNAMIC: a KBLI code is checked for *existence* against the
live canonical KBLI store (Qdrant collection ``kbli_2025_final``, payload field
``metadata.kode_kbli``). NO hardcoded KBLI list (CLAUDE.md §9). The valid-code
set is fetched once and cached process-wide (it is public reference data, not
PII — Law 2 is not violated by reading the public KBLI catalogue).

Return contract::

    {"valid": bool, "rule_failures": [str, ...], "checks_run": [str, ...]}
"""

from __future__ import annotations

import ast
import datetime as _dt
import logging
import os
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import httpx

logger = logging.getLogger("zantara.intake.validate")

# --- Format rules (authoritative, from existing CRM code). ---
_NIB_RE = re.compile(r"^\d{13}$")          # crm_clients_documents.py:804
_NPWP_LEGACY_RE = re.compile(r"^\d{15}$")  # crm_clients_documents.py:669
_NPWP_NIK16_RE = re.compile(r"^\d{16}$")   # pii_scanner.py NPWP_NEW_16 (2024)
_KBLI_RE = re.compile(r"^\d{5}$")          # KBLI codes are 5 digits.
_PASSPORT_RE = re.compile(r"^[A-Z0-9]{6,9}$")

# Expiry sanity window: a permit/passport expiry far in the past is suspect.
_EXPIRY_PAST_GRACE_DAYS = 3650  # 10y — older than this in the past = malformed.

# --- KBLI dynamic source (Qdrant). ---
_KBLI_COLLECTION = os.getenv("INTAKE_KBLI_COLLECTION", "kbli_2025_final")
_KBLI_FETCH_TIMEOUT = float(os.getenv("INTAKE_KBLI_FETCH_TIMEOUT", "30"))

# Process-wide cache of the valid KBLI code set (public data; cheap to cache).
_kbli_code_cache: frozenset[str] | None = None


def _strip_digits(value: Any) -> str:
    """Keep only digits (mirrors crm_clients_documents.py NIB/NPWP cleaning)."""
    return re.sub(r"\D", "", str(value or ""))


def _field_value(fields: dict[str, Any], name: str) -> Any:
    """Read a field's ``value`` from the extract-stage {value, ...} shape.

    Tolerates a bare value too (so validate can be called on plain dicts).
    """
    raw = fields.get(name)
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


# ---------------------------------------------------------------------------
# Dynamic KBLI existence check (live, no hardcode).
# ---------------------------------------------------------------------------

KbliFetchFn = Callable[[], Awaitable[frozenset[str]]]


async def _fetch_kbli_codes_from_qdrant() -> frozenset[str]:
    """Scroll the canonical KBLI collection and collect all ``kode_kbli`` codes.

    ``metadata`` is stored as a stringified dict in this collection, so we
    ``ast.literal_eval`` it. Filtering by ``metadata.kode_kbli`` is NOT possible
    (no payload index), so we scroll the whole collection once (~1.5k codes,
    ~12s) and cache the result. Read-only; public reference data.
    """
    qdrant_url = os.getenv("QDRANT_URL", "")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
    if not qdrant_url or not qdrant_api_key:
        raise RuntimeError("QDRANT_URL / QDRANT_API_KEY not set; cannot validate KBLI")

    codes: set[str] = set()
    offset: Any = None
    headers = {"api-key": qdrant_api_key, "Content-Type": "application/json"}
    url = f"{qdrant_url.rstrip('/')}/collections/{_KBLI_COLLECTION}/points/scroll"
    async with httpx.AsyncClient(timeout=_KBLI_FETCH_TIMEOUT) as client:
        while True:
            body: dict[str, Any] = {
                "limit": 1000,
                "with_payload": ["metadata"],
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            for point in result.get("points", []):
                meta = (point.get("payload") or {}).get("metadata")
                if isinstance(meta, str):
                    try:
                        meta = ast.literal_eval(meta)
                    except (ValueError, SyntaxError):
                        meta = {}
                code = (meta or {}).get("kode_kbli")
                if code:
                    codes.add(str(code).strip())
            offset = result.get("next_page_offset")
            if not offset:
                break
    logger.info("KBLI dynamic set loaded: %d codes from %s", len(codes), _KBLI_COLLECTION)
    return frozenset(codes)


async def get_valid_kbli_codes(
    *, fetch_fn: KbliFetchFn | None = None, force_refresh: bool = False
) -> frozenset[str]:
    """Return the cached valid KBLI code set, loading it live on first use."""
    global _kbli_code_cache
    if _kbli_code_cache is None or force_refresh:
        fetch = fetch_fn or _fetch_kbli_codes_from_qdrant
        _kbli_code_cache = await fetch()
    return _kbli_code_cache


# ---------------------------------------------------------------------------
# Per-field deterministic checks. Each appends to checks_run / rule_failures.
# ---------------------------------------------------------------------------

def _check_nib(value: Any, failures: list[str], checks: list[str]) -> None:
    checks.append("nib_format_13_digits")
    cleaned = _strip_digits(value)
    if not _NIB_RE.match(cleaned):
        failures.append(
            f"nib_number malformed: expected 13 digits, got {len(cleaned)} ('{value}')"
        )


def _check_npwp(value: Any, failures: list[str], checks: list[str]) -> None:
    checks.append("npwp_format_15_or_16_digits")
    cleaned = _strip_digits(value)
    if not (_NPWP_LEGACY_RE.match(cleaned) or _NPWP_NIK16_RE.match(cleaned)):
        failures.append(
            f"npwp_number malformed: expected 15 (legacy) or 16 (NIK) digits, "
            f"got {len(cleaned)} ('{value}')"
        )


def _check_passport(value: Any, failures: list[str], checks: list[str]) -> None:
    checks.append("passport_format")
    norm = str(value or "").strip().upper().replace(" ", "")
    if not _PASSPORT_RE.match(norm):
        failures.append(f"passport_no malformed: expected 6-9 alphanumerics ('{value}')")


def _parse_date(value: Any) -> _dt.date | None:
    """Parse a date in common Indonesian-doc formats. None if unparseable."""
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d %B %Y", "%d %b %Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _is_ambiguous_dmy(value: Any) -> bool:
    """True if a printed date could be read as either DD/MM or MM/DD.

    Indonesian/international documents print dates as DD/MM/YYYY, but the OCR
    model can silently swap day<->month when BOTH the day and month are <= 12
    (e.g. ``05/06/2026`` — 5 June or 6 May?). A day or month > 12 is
    self-disambiguating, so only the both-<=-12 case is flagged. We parse the
    raw printed forms (slash/dash separated D-M-Y), NOT the already-normalised
    ISO value, because the swap risk lives in the human-readable layout.

    Returns False for unparseable input, ISO-only strings, and spelled-out
    months (``05 June 2026`` — unambiguous by construction).
    """
    s = str(value or "").strip()
    if not s:
        return False
    # Only numeric D{sep}M{sep}Y forms carry the swap risk. A spelled-out month
    # or a YYYY-first string is unambiguous.
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if not m:
        return False
    first, second = int(m.group(1)), int(m.group(2))
    # Both positions plausible as either day or month -> genuinely ambiguous.
    return 1 <= first <= 12 and 1 <= second <= 12


def _check_expiry(
    field_name: str,
    value: Any,
    failures: list[str],
    checks: list[str],
    ambiguous: list[str],
) -> None:
    checks.append(f"{field_name}_date_valid_and_not_remote_past")
    # Soft signal (not a hard failure): a DD/MM<->MM/DD-swappable printed date
    # needs a human eyeball against the source, but ~40% of real dates land in
    # this zone, so blocking them all would be worse than the disease.
    if _is_ambiguous_dmy(value):
        checks.append(f"{field_name}_dmy_ambiguity_flagged")
        ambiguous.append(
            f"{field_name} printed as '{value}' is DD/MM<->MM/DD ambiguous "
            "(both fields <=12) — verify day vs month against the document"
        )
    parsed = _parse_date(value)
    if parsed is None:
        failures.append(f"{field_name} unparseable as date ('{value}')")
        return
    today = _dt.date.today()
    if parsed < today - _dt.timedelta(days=_EXPIRY_PAST_GRACE_DAYS):
        failures.append(
            f"{field_name} in remote past ({parsed.isoformat()}): "
            "likely OCR error or expired-beyond-plausible document"
        )


async def _check_kbli_codes(
    codes: Iterable[Any],
    failures: list[str],
    checks: list[str],
    *,
    fetch_fn: KbliFetchFn | None,
) -> None:
    checks.append("kbli_format_5_digits")
    checks.append("kbli_exists_in_live_catalogue")
    valid = await get_valid_kbli_codes(fetch_fn=fetch_fn)
    for raw in codes:
        code = _strip_digits(raw)
        if not _KBLI_RE.match(code):
            failures.append(f"kbli code malformed: expected 5 digits ('{raw}')")
            continue
        if code not in valid:
            failures.append(f"kbli code {code} does not exist in live KBLI catalogue")


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

async def validate_fields(
    doc_type: str | None,
    fields: dict[str, Any],
    *,
    kbli_fetch_fn: KbliFetchFn | None = None,
) -> dict[str, Any]:
    """Run all deterministic rules for ``doc_type`` over extracted ``fields``.

    ``fields`` is the extract-stage shape ({name: {value, confidence, ...}})
    or a flat {name: value} dict. A ``null`` field is SKIPPED (a missing field
    is not a validation failure — the golden rule already null-ed it; routing /
    HITL decides if a null is acceptable). Only PRESENT values are checked.
    """
    canonical = (doc_type or "").strip().lower()
    failures: list[str] = []
    checks: list[str] = []
    ambiguous: list[str] = []

    nib = _field_value(fields, "nib_number")
    if nib is not None:
        _check_nib(nib, failures, checks)

    npwp = _field_value(fields, "npwp_number")
    if npwp is not None:
        _check_npwp(npwp, failures, checks)

    passport = _field_value(fields, "passport_no")
    if passport is not None:
        _check_passport(passport, failures, checks)

    for date_field in ("expiry", "dob", "issue_date", "date"):
        val = _field_value(fields, date_field)
        if val is not None:
            _check_expiry(date_field, val, failures, checks, ambiguous)

    kbli = _field_value(fields, "kbli_codes")
    if kbli is not None:
        if isinstance(kbli, str):
            kbli = [kbli]
        if kbli:  # non-empty list
            await _check_kbli_codes(kbli, failures, checks, fetch_fn=kbli_fetch_fn)

    valid = len(failures) == 0
    logger.info(
        "validate: doc_type=%s valid=%s checks=%d failures=%d ambiguous_dates=%d",
        canonical, valid, len(checks), len(failures), len(ambiguous),
    )
    return {
        "valid": valid,
        "rule_failures": failures,
        "checks_run": checks,
        "ambiguous_dates": ambiguous,
    }


# ---------------------------------------------------------------------------
# Stage handler (worker.py FASE 2 contract: async def(job, stage) -> dict).
# ---------------------------------------------------------------------------

async def validate_stage(job: dict, stage: str) -> dict:
    """Stage handler for the 'validate' stage.

    Reads the extract-stage output from the job's accumulated stage_output and
    runs :func:`validate_fields`. Returns the validation dict to be merged into
    ``stage_output["validate"]``.
    """
    if stage != "validate":
        raise ValueError(f"validate_stage received unexpected stage={stage!r}")

    so = job.get("stage_output") or {}
    extract_out = so.get("extract") or {}
    # test ergonomics: also accept extract output flat on the job.
    if not extract_out and "fields" in job:
        extract_out = job
    doc_type = extract_out.get("doc_type") or job.get("doc_type")
    fields = extract_out.get("fields") or {}
    result = await validate_fields(doc_type, fields)
    logger.info("validate: job=%s valid=%s", job.get("id"), result["valid"])
    return result
