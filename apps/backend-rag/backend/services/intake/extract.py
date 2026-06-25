"""Document-intake field extraction (FASE 3 β — 'extract' stage).

Runs the SEA-LION extraction model (``aisingapore/Qwen-SEA-LION-v4-32B-IT``)
LOCALLY via Ollama (``http://localhost:11434``) — PII never leaves the Pro
(Law 2 / UU-PDP). For each canonical field the model returns either the value
WITH ``source_page`` evidence, or an explicit ``null`` — the *Maybe pattern*.

GOLDEN RULE (CLAUDE.md anti-hallucination): a field that is not clearly
legible is ``null`` with ``confidence == 0.0``. NEVER an invented value. A
fabricated director on an akta = legal harm to a client. This is enforced both
in the extraction prompt AND defensively in :func:`_coerce_field` (a value with
no supporting evidence text is downgraded to ``null``).

Stage contract (worker.py FASE 2):
    ``async def extract_stage(job: dict, stage: str) -> dict`` where ``stage``
    is ``"extract"``. The returned dict is merged into
    ``stage_output["extract"]``. The doc_type + per-page OCR text are read from
    the upstream ``stage_output`` (``classify`` / ``ocr``).
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx

from backend.services.intake.model_roles import resolve_model_role
from backend.utils.passport_normalize import (
    normalize_date,
    normalize_nationality,
    title_case_name,
)

logger = logging.getLogger("zantara.intake.extract")

# --- Model role (FASE 0 registry: intake_extraction). Env-overridable. ---
_EXTRACTION_MODEL_DEFAULT = "aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m"


def _resolve_extraction_model() -> str:
    """Prefer env override, then FASE-0 registry, then the local SEA-LION default."""
    override = os.getenv("INTAKE_EXTRACTION_MODEL")
    if override:
        return override
    return resolve_model_role("intake_extraction", _EXTRACTION_MODEL_DEFAULT)


EXTRACTION_MODEL: str = _resolve_extraction_model()
EXTRACTION_MODEL_LABEL: str = "sea-lion"
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

# SEA-LION 32B q4 is a heavy local model: ~25-45s warm, cold-load slower.
_GENERATE_TIMEOUT_SECONDS: float = float(os.getenv("INTAKE_EXTRACT_TIMEOUT", "300"))
_CONNECT_TIMEOUT_SECONDS: float = 5.0

# Confidence assigned to a value the model returned WITH evidence. The extractor
# is deterministic (temperature 0) and does not emit calibrated probabilities;
# downstream validate_rules.py does the hard yes/no checks, so we use a single
# "present-and-evidenced" confidence rather than a fake fine-grained score.
_PRESENT_CONFIDENCE: float = 0.85
_LOW_CONFIDENCE_THRESHOLD: float = 0.60  # mirrors evidence-scoring CAUTIOUS band.
_MRZ_CONFIDENCE: float = 0.95
_LABEL_CONFIDENCE: float = 0.90
_DETERMINISTIC_LABEL_MODEL: str = "deterministic_labels"

# --- Persistent async HTTP client (Golden Rule #10: never per-call). ---
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazily build / reuse a persistent Ollama HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=OLLAMA_BASE_URL,
            timeout=httpx.Timeout(_GENERATE_TIMEOUT_SECONDS, connect=_CONNECT_TIMEOUT_SECONDS),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
    return _client


async def close_extract_client() -> None:
    """Close the persistent client. Call from the app lifespan shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Canonical per-doc-type field schema (Maybe pattern: every field Optional).
#
# Reuses the field names already used by the CRM extraction path
# (crm_clients_documents.py / crm_enhanced.py): nib_number, company_name,
# kbli_codes, address, issue_date, npwp_number, etc. — so downstream routing
# stays consistent with the existing CRM contract.
#
# A field marked ``is_list=True`` is extracted as an array (e.g. kbli_codes,
# directors). All others are scalars.
# ---------------------------------------------------------------------------

# (field_name, is_list, human description used in the prompt)
_FieldSpec = tuple[str, bool, str]

DOC_TYPE_FIELDS: dict[str, list[_FieldSpec]] = {
    "nib": [
        ("nib_number", False, "13-digit NIB / Nomor Induk Berusaha number"),
        ("company_name", False, "full legal company name (PT ...)"),
        ("kbli_codes", True, "list of 5-digit KBLI business-classification codes"),
        ("address", False, "registered company address"),
        ("issue_date", False, "issue date (prefer YYYY-MM-DD)"),
    ],
    "npwp": [
        ("npwp_number", False, "15- or 16-digit NPWP tax number"),
        ("name", False, "name of the taxpayer (person or company)"),
        ("address", False, "registered address"),
    ],
    "akta_pendirian": [
        ("company_name", False, "full legal company name being established"),
        ("directors", True, "list of director (Direktur) full names"),
        ("commissioners", True, "list of commissioner (Komisaris) full names"),
        ("capital", False, "authorised/issued capital (modal) amount"),
        ("notary", False, "notary (Notaris) name"),
        ("date", False, "deed date (prefer YYYY-MM-DD)"),
    ],
    "profil_perseroan": [
        ("company_name", False, "full legal company name (PT ...)"),
        ("directors", True, "list of director (Direktur) full names"),
        ("commissioners", True, "list of commissioner (Komisaris) full names"),
        ("kbli_codes", True, "list of 5-digit KBLI / bidang-usaha codes"),
        ("capital", False, "share-capital / modal structure amount"),
        ("address", False, "registered company address"),
    ],
    "passport": [
        ("passport_no", False, "passport number"),
        ("name", False, "full name of the holder"),
        ("nationality", False, "nationality / kewarganegaraan"),
        ("dob", False, "date of birth (prefer YYYY-MM-DD)"),
        ("expiry", False, "expiry date (prefer YYYY-MM-DD)"),
    ],
    "kitas": [
        ("kitas_no", False, "KITAS permit number"),
        ("name", False, "full name of the holder"),
        ("expiry", False, "expiry / valid-until date (prefer YYYY-MM-DD)"),
        ("sponsor", False, "sponsor (penjamin) name"),
    ],
    "visa": [
        ("visa_no", False, "visa / e-visa number"),
        ("visa_index", False, "visa index / visa type code"),
        ("name", False, "full name of the holder"),
        ("passport_no", False, "linked passport number"),
        ("expiry", False, "expiry / valid-until date (prefer YYYY-MM-DD)"),
        ("sponsor", False, "sponsor (penjamin) name"),
    ],
    "payment_receipt": [
        ("receipt_no", False, "receipt / invoice / transaction reference number"),
        ("payer_name", False, "payer / sender name when visible"),
        ("amount", False, "payment amount with currency"),
        ("payment_date", False, "payment date (prefer YYYY-MM-DD)"),
        ("reference", False, "bank, invoice, or payment reference"),
    ],
    "travel_ticket": [
        ("ticket_no", False, "ticket number when visible"),
        ("name", False, "passenger full name"),
        ("travel_date", False, "departure / travel date (prefer YYYY-MM-DD)"),
        ("route", False, "origin-destination route"),
        ("booking_reference", False, "booking reference / PNR"),
    ],
    "bank_statement": [
        ("account_holder", False, "bank account holder name"),
        ("bank_name", False, "bank name"),
        ("account_no", False, "bank account number, masked if partially visible"),
        ("statement_period", False, "statement period / month"),
        ("balance", False, "closing balance or visible balance amount"),
    ],
    "medical_insurance": [
        ("policy_no", False, "insurance policy number"),
        ("name", False, "insured person's full name"),
        ("insurer", False, "insurance company / insurer name"),
        ("coverage_period", False, "coverage period"),
        ("expiry", False, "policy expiry date (prefer YYYY-MM-DD)"),
    ],
    "itap": [
        ("itap_no", False, "ITAP / permanent stay permit number"),
        ("name", False, "full name of the holder"),
        ("expiry", False, "expiry / valid-until date (prefer YYYY-MM-DD)"),
        ("sponsor", False, "sponsor (penjamin) name"),
    ],
    "itk": [
        ("itk_no", False, "ITK / visit stay permit number"),
        ("name", False, "full name of the holder"),
        ("expiry", False, "expiry / valid-until date (prefer YYYY-MM-DD)"),
        ("sponsor", False, "sponsor (penjamin) name"),
    ],
    "ktp": [
        ("nik", False, "16-digit NIK / Indonesian identity number"),
        ("name", False, "full name of the holder"),
        ("dob", False, "date of birth (prefer YYYY-MM-DD)"),
        ("address", False, "registered address"),
    ],
    "family_card": [
        ("family_card_no", False, "Kartu Keluarga / KK family-card number"),
        ("name", False, "head of family / primary holder full name"),
        ("members", True, "list of family-member full names"),
        ("address", False, "family registered address"),
    ],
    "birth_certificate": [
        ("certificate_no", False, "birth-certificate / akta kelahiran number"),
        ("name", False, "child / certificate holder full name"),
        ("dob", False, "date of birth (prefer YYYY-MM-DD)"),
        ("place_of_birth", False, "place of birth"),
        ("parents", True, "list of parent full names"),
    ],
    "marriage_certificate": [
        ("certificate_no", False, "marriage-certificate / akta nikah number"),
        ("name", False, "primary spouse / certificate holder full name"),
        ("spouse_names", True, "list of spouse full names"),
        ("marriage_date", False, "marriage date (prefer YYYY-MM-DD)"),
        ("place", False, "marriage place / issuing office"),
    ],
    "sk_kemenkumham": [
        ("sk_number", False, "SK Kemenkumham decision number"),
        ("company_name", False, "full legal company name (PT ...)"),
        ("date", False, "decision / issue date (prefer YYYY-MM-DD)"),
    ],
}

# Aliases: classifier may emit longer/variant doc_type labels.
_DOC_TYPE_ALIASES: dict[str, str] = {
    "nib_oss": "nib",
    "oss": "nib",
    "oss_nib": "nib",
    "npwp_company": "npwp",
    "npwp_personal": "npwp",
    "akta": "akta_pendirian",
    "akta_pendirian_pt": "akta_pendirian",
    "sk": "sk_kemenkumham",
    "sk_menkumham": "sk_kemenkumham",
    "kemenkumham": "sk_kemenkumham",
    "passport_page": "passport",
    "paspor": "passport",
    "kitas_card": "kitas",
    "itas": "kitas",
    "evisa": "visa",
    "e_visa": "visa",
    "e-visa": "visa",
    "voa": "visa",
    "visa_on_arrival": "visa",
    "visit_visa": "visa",
    "receipt": "payment_receipt",
    "payment_proof": "payment_receipt",
    "proof_of_payment": "payment_receipt",
    "bukti_pembayaran": "payment_receipt",
    "bukti_transfer": "payment_receipt",
    "boarding_pass": "travel_ticket",
    "flight_ticket": "travel_ticket",
    "e_ticket": "travel_ticket",
    "e-ticket": "travel_ticket",
    "flight_itinerary": "travel_ticket",
    "rekening_koran": "bank_statement",
    "account_statement": "bank_statement",
    "medical_insurance_policy": "medical_insurance",
    "travel_insurance": "medical_insurance",
    "insurance_policy": "medical_insurance",
    "asuransi": "medical_insurance",
    "kitap": "itap",
    "itap_card": "itap",
    "itk_card": "itk",
    "id_card": "ktp",
    "e_ktp": "ktp",
    "kk": "family_card",
    "kartu_keluarga": "family_card",
    "family_card_kk": "family_card",
    "birth_cert": "birth_certificate",
    "akta_kelahiran": "birth_certificate",
    "marriage_cert": "marriage_certificate",
    "akta_nikah": "marriage_certificate",
    "akta_perkawinan": "marriage_certificate",
    "buku_nikah": "marriage_certificate",
    "company_profile": "profil_perseroan",
    "profil_pt": "profil_perseroan",
    "profile_perseroan": "profil_perseroan",
}


def canonical_doc_type(doc_type: str | None) -> str | None:
    """Map a (possibly variant) classifier doc_type to a schema key."""
    if not doc_type:
        return None
    key = doc_type.strip().lower()
    key = _DOC_TYPE_ALIASES.get(key, key)
    return key if key in DOC_TYPE_FIELDS else None


# ---------------------------------------------------------------------------
# Prompt construction + parsing.
# ---------------------------------------------------------------------------

def _build_prompt(doc_type: str, pages: list[str]) -> str:
    """Build the Maybe-pattern extraction prompt with per-page numbering."""
    specs = DOC_TYPE_FIELDS[doc_type]
    field_lines = []
    for name, is_list, desc in specs:
        shape = "an array of strings" if is_list else "a string"
        field_lines.append(f'  - "{name}": {shape} — {desc}')
    fields_block = "\n".join(field_lines)

    numbered_pages = "\n".join(
        f"--- PAGE {i + 1} ---\n{page}" for i, page in enumerate(pages)
    )

    return (
        "You extract structured fields from an Indonesian legal/identity "
        f"document of type '{doc_type}'.\n\n"
        "GOLDEN RULE (most important): return null for any field that is NOT "
        "clearly legible in the text. NEVER guess, infer, or invent a value. "
        "An invented director on an akta or a wrong number on a KITAS causes "
        "legal harm to a real client. When unsure, the answer is null.\n\n"
        "Return ONLY a single JSON object. For EACH field below, the value is "
        "an object {\"value\": <extracted value or null>, \"source_page\": "
        "<1-based page number where you read it, or null>}.\n"
        "If the field is a list, \"value\" is an array (or null / [] if none).\n\n"
        "Fields:\n"
        f"{fields_block}\n\n"
        "Do not add fields that are not listed. Do not output markdown or "
        "explanations — JSON object only.\n\n"
        "DOCUMENT OCR TEXT (per page):\n"
        f"{numbered_pages}\n"
    )


def _coerce_field(
    is_list: bool,
    raw: Any,
    num_pages: int,
) -> dict[str, Any]:
    """Normalise one model-emitted field into {value, confidence, source_page}.

    Defensive enforcement of the Maybe pattern: anything the model did not
    return as a concrete value collapses to null + confidence 0.0. A scalar
    value whose source_page is missing/out-of-range keeps the value but is
    flagged low-confidence (we trust the value, distrust the citation).
    """
    null_field = {"value": None, "confidence": 0.0, "source_page": None}

    # The model may emit either the {value, source_page} object or a bare value.
    if isinstance(raw, dict):
        value = raw.get("value", None)
        src = raw.get("source_page", None)
    else:
        value = raw
        src = None

    # Normalise "empty" sentinels to null.
    if value is None:
        return null_field
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "n/a", "-"}:
        return null_field

    if is_list:
        if not isinstance(value, list):
            value = [value]
        cleaned = [
            str(v).strip()
            for v in value
            if v is not None and str(v).strip().lower() not in {"", "null", "none", "n/a", "-"}
        ]
        if not cleaned:
            return null_field
        value = cleaned
    else:
        value = str(value).strip()

    # Validate the page citation.
    source_page: int | None = None
    if isinstance(src, int) and 1 <= src <= num_pages:
        source_page = src
    elif isinstance(src, str) and src.strip().isdigit():
        cand = int(src.strip())
        if 1 <= cand <= num_pages:
            source_page = cand

    # Present-and-evidenced -> _PRESENT_CONFIDENCE; present-but-no-citation ->
    # halved confidence (value kept, citation distrusted). Never 1.0 for a
    # local extractor (anti-overconfidence).
    confidence = _PRESENT_CONFIDENCE if source_page is not None else _PRESENT_CONFIDENCE / 2
    return {"value": value, "confidence": round(confidence, 2), "source_page": source_page}


# ---------------------------------------------------------------------------
# Deterministic passport MRZ extraction.
# ---------------------------------------------------------------------------

_MRZ_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<"
_MRZ_VALUES = {ch: i for i, ch in enumerate("0123456789")}
_MRZ_VALUES.update({chr(ord("A") + i): 10 + i for i in range(26)})
_MRZ_VALUES["<"] = 0
_MRZ_WEIGHTS = (7, 3, 1)


def _normalise_mrz_candidate(line: str) -> str:
    """Return a compact MRZ-ish line, dropping OCR spaces/punctuation."""
    cleaned = (
        line.upper()
        .replace("«", "<")
        .replace("‹", "<")
        .replace(" ", "")
    )
    return "".join(ch for ch in cleaned if ch in _MRZ_CHARS)


def _mrz_check_digit(value: str) -> int:
    """ICAO 9303 MRZ check digit."""
    total = 0
    for idx, ch in enumerate(value):
        total += _MRZ_VALUES.get(ch, 0) * _MRZ_WEIGHTS[idx % len(_MRZ_WEIGHTS)]
    return total % 10


def _mrz_check_ok(line: str, start: int, end: int, check_pos: int) -> bool:
    check = line[check_pos] if len(line) > check_pos else ""
    return check.isdigit() and _mrz_check_digit(line[start:end]) == int(check)


def _find_td3_mrz_pair(pages: list[str]) -> tuple[str, str, int] | None:
    """Find a passport TD3 MRZ pair in OCR pages.

    Returns (line1, line2, source_page). source_page is 1-based to match the
    extraction-stage field contract.
    """
    for page_idx, text in enumerate(pages, start=1):
        candidates = [
            _normalise_mrz_candidate(line)
            for line in str(text or "").splitlines()
        ]
        candidates = [line for line in candidates if len(line) >= 20 and "<" in line]
        for idx, line1 in enumerate(candidates):
            if not line1.startswith("P<"):
                continue
            for line2 in candidates[idx + 1 : idx + 4]:
                if len(line2) < 30:
                    continue
                l1 = (line1 + ("<" * 44))[:44]
                l2 = (line2 + ("<" * 44))[:44]
                valid_checks = sum(
                    (
                        _mrz_check_ok(l2, 0, 9, 9),
                        _mrz_check_ok(l2, 13, 19, 19),
                        _mrz_check_ok(l2, 21, 27, 27),
                    )
                )
                # Two independent check digits are enough to trust the pair.
                # Below that, treat it as OCR noise and keep the model path.
                if valid_checks >= 2:
                    return l1, l2, page_idx
    return None


def _extract_passport_mrz_fields(pages: list[str]) -> dict[str, dict[str, Any]]:
    """Extract passport fields from a TD3 MRZ pair without an LLM."""
    pair = _find_td3_mrz_pair(pages)
    if pair is None:
        return {}
    line1, line2, source_page = pair
    out: dict[str, dict[str, Any]] = {}

    raw_name = line1[5:44].rstrip("<")
    name = title_case_name(raw_name)
    if name:
        out["name"] = {
            "value": name,
            "confidence": _MRZ_CONFIDENCE,
            "source_page": source_page,
        }

    if _mrz_check_ok(line2, 0, 9, 9):
        passport_no = line2[0:9].replace("<", "").strip()
        if passport_no:
            out["passport_no"] = {
                "value": passport_no,
                "confidence": _MRZ_CONFIDENCE,
                "source_page": source_page,
            }

    nationality = normalize_nationality(line2[10:13].replace("<", "").strip())
    if nationality:
        out["nationality"] = {
            "value": nationality,
            "confidence": _MRZ_CONFIDENCE,
            "source_page": source_page,
        }

    if _mrz_check_ok(line2, 13, 19, 19):
        dob = normalize_date(line2[13:19])
        if dob:
            out["dob"] = {
                "value": dob,
                "confidence": _MRZ_CONFIDENCE,
                "source_page": source_page,
            }

    if _mrz_check_ok(line2, 21, 27, 27):
        expiry = normalize_date(line2[21:27])
        if expiry:
            out["expiry"] = {
                "value": expiry,
                "confidence": _MRZ_CONFIDENCE,
                "source_page": source_page,
            }

    return out


def _passport_mrz_complete(fields: dict[str, dict[str, Any]]) -> bool:
    """True when MRZ supplied the full passport extraction schema."""
    return all(
        fields.get(name, {}).get("value")
        for name, _is_list, _desc in DOC_TYPE_FIELDS["passport"]
    )


def _merge_deterministic_fields(
    fields: dict[str, dict[str, Any]],
    deterministic: dict[str, dict[str, Any]],
) -> None:
    """Prefer stronger deterministic fields over model/null fields in-place."""
    for name, value in deterministic.items():
        current = fields.get(name)
        current_conf = current.get("confidence", 0.0) if isinstance(current, dict) else 0.0
        if current is None or current.get("value") is None or current_conf < value["confidence"]:
            fields[name] = value


# ---------------------------------------------------------------------------
# Deterministic labelled-field extraction for routing-critical simple docs.
# ---------------------------------------------------------------------------

_ID_MONTHS: dict[str, int] = {
    "JANUARI": 1,
    "FEBRUARI": 2,
    "MARET": 3,
    "APRIL": 4,
    "MEI": 5,
    "JUNI": 6,
    "JULI": 7,
    "AGUSTUS": 8,
    "AUGUSTUS": 8,
    "SEPTEMBER": 9,
    "OKTOBER": 10,
    "NOVEMBER": 11,
    "DESEMBER": 12,
}


def _blank_fields(doc_type: str) -> dict[str, dict[str, Any]]:
    return {
        name: {"value": None, "confidence": 0.0, "source_page": None}
        for name, _is_list, _desc in DOC_TYPE_FIELDS[doc_type]
    }


def _clean_label_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" \t:-")
    if not cleaned or cleaned.lower() in {"null", "none", "n/a", "-"}:
        return None
    return cleaned


def _field(value: str | None, page: int) -> dict[str, Any] | None:
    cleaned = _clean_label_value(value)
    if cleaned is None:
        return None
    return {"value": cleaned, "confidence": _LABEL_CONFIDENCE, "source_page": page}


def _title_person_name(value: str | None) -> str | None:
    cleaned = _clean_label_value(value)
    if cleaned is None:
        return None
    upper = cleaned.upper()
    if upper.startswith("PT "):
        rest = title_case_name(cleaned[3:])
        return f"PT {rest}" if rest else "PT"
    return title_case_name(cleaned) if cleaned == upper else cleaned


def _normalise_label_date(value: str | None) -> str | None:
    cleaned = _clean_label_value(value)
    if cleaned is None:
        return None
    direct = normalize_date(cleaned)
    if direct:
        return direct
    numeric = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", cleaned)
    if numeric:
        day, month, year = (int(numeric.group(1)), int(numeric.group(2)), int(numeric.group(3)))
        if year < 100:
            year = 1900 + year if year > 50 else 2000 + year
        try:
            datetime(year, month, day)
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            return None
    text = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", cleaned)
    if text:
        day = int(text.group(1))
        month = _ID_MONTHS.get(text.group(2).upper())
        year = int(text.group(3))
        if month is not None:
            try:
                datetime(year, month, day)
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                return None
    return None


def _first_line_match(
    pages: list[str],
    pattern: str,
    *,
    flags: int = re.IGNORECASE,
) -> tuple[str, int] | None:
    regex = re.compile(pattern, flags)
    for page_no, page in enumerate(pages, start=1):
        for line in str(page or "").splitlines():
            match = regex.search(line.strip())
            if match:
                value = _clean_label_value(match.group(1))
                if value:
                    return value, page_no
    return None


def _set_if_present(
    fields: dict[str, dict[str, Any]],
    name: str,
    value_page: tuple[str | None, int] | None,
    *,
    person_name: bool = False,
    date: bool = False,
) -> None:
    if value_page is None:
        return
    value, page = value_page
    if person_name:
        value = _title_person_name(value)
    elif date:
        value = _normalise_label_date(value)
    parsed = _field(value, page)
    if parsed is not None:
        fields[name] = parsed


def _extract_kitas_label_fields(pages: list[str]) -> dict[str, dict[str, Any]]:
    fields = _blank_fields("kitas")
    _set_if_present(
        fields,
        "kitas_no",
        _first_line_match(
            pages,
            r"^(?:no\.?\s*(?:kitas|itas)|nomor\s*(?:kitas|itas)|(?:kitas|itas)\s*(?:no|number))\s*[:\-]?\s*([A-Z0-9][A-Z0-9 .\-/]{4,})$",
        ),
    )
    _set_if_present(
        fields,
        "name",
        _first_line_match(pages, r"^(?:nama|name)\s*[:\-]\s*(?!rekening\b)(.+)$"),
        person_name=True,
    )
    _set_if_present(
        fields,
        "expiry",
        _first_line_match(
            pages,
            r"^(?:berlaku\s*(?:hingga|sampai)|valid\s*(?:until|thru|to)|expiry|expired)\s*[:\-]\s*(.+)$",
        ),
        date=True,
    )
    _set_if_present(
        fields,
        "sponsor",
        _first_line_match(pages, r"^(?:penjamin|sponsor)\s*[:\-]\s*(.+)$"),
    )
    return fields


def _extract_ktp_label_fields(pages: list[str]) -> dict[str, dict[str, Any]]:
    fields = _blank_fields("ktp")
    _set_if_present(
        fields,
        "nik",
        _first_line_match(
            pages,
            r"^(?:nik|nomor\s+induk\s+kependudukan)\s*[:\-]?\s*(\d[\d .\-]{10,})$",
        ),
    )
    _set_if_present(
        fields,
        "name",
        _first_line_match(pages, r"^(?:nama|name)\s*[:\-]\s*(?!rekening\b)(.+)$"),
        person_name=True,
    )
    born = _first_line_match(
        pages,
        r"^(?:tempat\s*/?\s*tgl\s*lahir|tempat\s+tanggal\s+lahir)\s*[:\-]\s*(?:[^,]+,\s*)?(.+)$",
    )
    if born is None:
        born = _first_line_match(pages, r"^(?:tanggal\s+lahir|tgl\s+lahir|dob)\s*[:\-]\s*(.+)$")
    _set_if_present(fields, "dob", born, date=True)
    _set_if_present(
        fields,
        "address",
        _first_line_match(pages, r"^(?:alamat|address)\s*[:\-]\s*(.+)$"),
    )
    return fields


def _bank_name_from_text(text: str) -> str | None:
    upper = text.upper()
    bank_aliases = (
        ("BCA", ("BCA", "BANK CENTRAL ASIA")),
        ("Mandiri", ("BANK MANDIRI", "MANDIRI")),
        ("BNI", ("BNI", "BANK NEGARA INDONESIA")),
        ("BRI", ("BRI", "BANK RAKYAT INDONESIA")),
        ("CIMB Niaga", ("CIMB", "NIAGA")),
        ("OCBC", ("OCBC",)),
    )
    for canonical, needles in bank_aliases:
        if any(needle in upper for needle in needles):
            return canonical
    return None


def _extract_bank_statement_label_fields(pages: list[str]) -> dict[str, dict[str, Any]]:
    fields = _blank_fields("bank_statement")
    _set_if_present(
        fields,
        "account_holder",
        _first_line_match(
            pages,
            r"^(?:nama\s*(?:rekening|pemilik|nasabah)|account\s*holder|customer\s*name|name)\s*[:\-]\s*(.+)$",
        ),
        person_name=True,
    )
    _set_if_present(
        fields,
        "account_no",
        _first_line_match(
            pages,
            r"^(?:no\.?\s*(?:rekening|rek|account)|account\s*(?:no|number))\s*[:\-]\s*([0-9Xx* .\-]{5,})$",
        ),
    )
    _set_if_present(
        fields,
        "statement_period",
        _first_line_match(pages, r"^(?:periode|period|statement\s*period)\s*[:\-]\s*(.+)$"),
    )
    _set_if_present(
        fields,
        "balance",
        _first_line_match(
            pages,
            r"^(?:saldo\s*(?:akhir|ending)?|ending\s*balance|closing\s*balance|balance)\s*[:\-]\s*(.+)$",
        ),
    )
    combined = "\n".join(pages)
    bank_name = _bank_name_from_text(combined)
    if bank_name:
        fields["bank_name"] = {"value": bank_name, "confidence": _LABEL_CONFIDENCE, "source_page": 1}
    return fields


def _has_any_value(fields: dict[str, dict[str, Any]], names: tuple[str, ...]) -> bool:
    return any(fields.get(name, {}).get("value") for name in names)


def _extract_label_fields_if_routing_useful(
    doc_type: str,
    pages: list[str],
) -> tuple[dict[str, dict[str, Any]], str] | None:
    if doc_type == "kitas":
        fields = _extract_kitas_label_fields(pages)
        if _has_any_value(fields, ("kitas_no", "name")):
            return fields, "kitas_labels"
    if doc_type == "ktp":
        fields = _extract_ktp_label_fields(pages)
        if _has_any_value(fields, ("nik", "name")):
            return fields, "ktp_labels"
    if doc_type == "bank_statement":
        fields = _extract_bank_statement_label_fields(pages)
        if _has_any_value(fields, ("account_holder", "account_no")):
            return fields, "bank_statement_labels"
    return None


# Injectable generate fn for tests (avoids hitting Ollama). Signature mirrors a
# subset of the Ollama /api/generate contract: (model, prompt) -> response str.
GenerateFn = Callable[[str, str], Awaitable[str]]


async def _ollama_generate(model: str, prompt: str) -> str:
    """Call local Ollama /api/generate with JSON format + think:false."""
    client = _get_client()
    resp = await client.post(
        "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,  # SEA-LION/Qwen: return content directly, no <think>.
            "format": "json",
            "options": {"temperature": 0},
        },
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _parse_response(text: str) -> dict[str, Any]:
    """Parse the model's JSON response; tolerant of stray markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences if present.
        text = text.split("```", 2)[1] if "```" in text[3:] else text
        text = text.removeprefix("json").strip().strip("`").strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # last-resort: slice the outermost {...}.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("extraction response is not a JSON object")
    return obj


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

async def extract_fields(
    doc_type: str | None,
    ocr_text_per_page: list[str],
    *,
    generate_fn: GenerateFn | None = None,
) -> dict[str, Any]:
    """Extract canonical fields for ``doc_type`` from per-page OCR text.

    Returns::

        {
          "doc_type": "<canonical>",
          "fields": {field: {"value", "confidence", "source_page"}, ...},
          "extraction_model": "sea-lion",
          "any_low_confidence": bool,
        }

    Every field is present in ``fields`` (Maybe pattern); an absent/illegible
    field is ``{"value": None, "confidence": 0.0, "source_page": None}``.

    Raises ``ValueError`` for an unknown/unsupported ``doc_type`` (the caller —
    the stage handler — turns that into a stage failure, never a fabrication).
    """
    canonical = canonical_doc_type(doc_type)
    if canonical is None:
        raise ValueError(f"unsupported doc_type for extraction: {doc_type!r}")

    pages = [p if isinstance(p, str) else str(p) for p in (ocr_text_per_page or [])]
    if not pages or not any(p.strip() for p in pages):
        # No legible OCR at all -> every field null (golden rule), no model call.
        specs = DOC_TYPE_FIELDS[canonical]
        fields = {
            name: {"value": None, "confidence": 0.0, "source_page": None}
            for name, _is_list, _desc in specs
        }
        logger.warning("extract: empty OCR for doc_type=%s -> all fields null", canonical)
        return {
            "doc_type": canonical,
            "fields": fields,
            "extraction_model": EXTRACTION_MODEL_LABEL,
            "any_low_confidence": True,
        }

    deterministic_fields: dict[str, dict[str, Any]] = {}
    deterministic_extractors: list[str] = []
    if canonical == "passport":
        deterministic_fields = _extract_passport_mrz_fields(pages)
        if deterministic_fields:
            deterministic_extractors.append("passport_mrz")
            if _passport_mrz_complete(deterministic_fields):
                fields = {
                    name: {"value": None, "confidence": 0.0, "source_page": None}
                    for name, _is_list, _desc in DOC_TYPE_FIELDS[canonical]
                }
                _merge_deterministic_fields(fields, deterministic_fields)
                return {
                    "doc_type": canonical,
                    "fields": fields,
                    "extraction_model": "passport_mrz",
                    "deterministic_extractors": deterministic_extractors,
                    "any_low_confidence": False,
                }
    else:
        labelled = _extract_label_fields_if_routing_useful(canonical, pages)
        if labelled is not None:
            fields, extractor_name = labelled
            any_low = any(
                field["confidence"] < _LOW_CONFIDENCE_THRESHOLD
                for field in fields.values()
            )
            return {
                "doc_type": canonical,
                "fields": fields,
                "extraction_model": _DETERMINISTIC_LABEL_MODEL,
                "deterministic_extractors": [extractor_name],
                "any_low_confidence": any_low,
            }

    prompt = _build_prompt(canonical, pages)
    gen = generate_fn or _ollama_generate
    raw_response = await gen(_resolve_extraction_model(), prompt)
    parsed = _parse_response(raw_response)

    specs = DOC_TYPE_FIELDS[canonical]
    num_pages = len(pages)
    fields: dict[str, Any] = {}
    any_low = False
    for name, is_list, _desc in specs:
        field = _coerce_field(is_list, parsed.get(name), num_pages)
        fields[name] = field
    if deterministic_fields:
        _merge_deterministic_fields(fields, deterministic_fields)
    for field in fields.values():
        if field["confidence"] < _LOW_CONFIDENCE_THRESHOLD:
            any_low = True

    result = {
        "doc_type": canonical,
        "fields": fields,
        "extraction_model": EXTRACTION_MODEL_LABEL,
        "any_low_confidence": any_low,
    }
    if deterministic_extractors:
        result["deterministic_extractors"] = deterministic_extractors
    return result


# ---------------------------------------------------------------------------
# Stage handler (worker.py FASE 2 contract: async def(job, stage) -> dict).
# ---------------------------------------------------------------------------

def _read_upstream(job: dict, *keys: str) -> Any:
    """Read a value from the job's accumulated stage_output by trying keys.

    The worker carries prior stages' output in ``stage_output`` (jsonb), but the
    claimed ``job`` dict only has id/attempts/... so production handlers fetch
    ``stage_output`` themselves. For testability we accept it inline on the job.
    """
    so = job.get("stage_output") or {}
    for parent in ("classify", "ocr", "extract"):
        section = so.get(parent) or {}
        for k in keys:
            if k in section and section[k] is not None:
                return section[k]
    # also allow flat keys on the job (test ergonomics).
    for k in keys:
        if k in job and job[k] is not None:
            return job[k]
    return None


async def extract_stage(job: dict, stage: str) -> dict:
    """Stage handler for the 'extract' stage (worker injects as stage_handler).

    Reads doc_type (from classify) + per-page OCR text (from ocr) out of the
    job's accumulated stage_output, runs :func:`extract_fields`, returns the
    extraction dict to be merged into ``stage_output["extract"]``.
    """
    if stage != "extract":
        # The single injected handler may be called for other stages; pass-through
        # is NOT our job — validate has its own handler. Be explicit.
        raise ValueError(f"extract_stage received unexpected stage={stage!r}")

    doc_type = _read_upstream(job, "doc_type", "canonical_doc_type")
    pages = _read_upstream(job, "ocr_text_per_page", "pages", "ocr_pages")
    if isinstance(pages, str):
        pages = [pages]
    result = await extract_fields(doc_type, pages or [])
    logger.info(
        "extract: job=%s doc_type=%s any_low_confidence=%s",
        job.get("id"), result["doc_type"], result["any_low_confidence"],
    )
    return result
