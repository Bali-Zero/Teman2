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
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from backend.services.intake.model_roles import resolve_model_role

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
}

# Aliases: classifier may emit longer/variant doc_type labels.
_DOC_TYPE_ALIASES: dict[str, str] = {
    "nib_oss": "nib",
    "npwp_company": "npwp",
    "npwp_personal": "npwp",
    "akta": "akta_pendirian",
    "akta_pendirian_pt": "akta_pendirian",
    "passport_page": "passport",
    "paspor": "passport",
    "kitas_card": "kitas",
    "itas": "kitas",
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
        if field["confidence"] < _LOW_CONFIDENCE_THRESHOLD:
            any_low = True

    return {
        "doc_type": canonical,
        "fields": fields,
        "extraction_model": EXTRACTION_MODEL_LABEL,
        "any_low_confidence": any_low,
    }


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
