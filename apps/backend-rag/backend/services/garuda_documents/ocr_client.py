"""Local-first OCR over qwen2.5vl:7b (guardrail G-OCR-LOCAL — never a cloud endpoint).

qwen3.5 Q4_K_M strips vision weights (CLAUDE.md §9): qwen2.5vl:7b is the only model on
this fleet confirmed to do vision OCR, and it must be called with the Ollama chat
`"images": [base64]` shape.

Confidence design (DECISIONS.md Q7 defers the THRESHOLD to L5, but not to an unverifiable
number): qwen2.5vl has no native per-field confidence score, and an LLM's own self-rated
confidence is not, on its own, trustworthy evidence. This client therefore runs the
extraction TWICE per document (independent chat turns) and treats per-field agreement
between the two passes as the primary confidence signal — a field only both passes read
identically is far more likely correct than one either pass alone reports high self-rated
confidence for. `confidence.py` combines this with the self-rating; it does not use the
self-rating alone.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from backend.app.core.config import settings
from backend.services.garuda_documents.models import PassportReviewFieldName

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "qwen2.5vl:7b"

_PROMPT = """You are reading a passport biodata page photo. Extract exactly these fields:
full_name, passport_number, nationality, passport_expiry_date (ISO YYYY-MM-DD if legible).
If a field is not legible or not present, set its value to null.
Respond with ONLY a JSON object, no prose, no markdown fences:
{"full_name": "...", "passport_number": "...", "nationality": "...", \
"passport_expiry_date": "...", "self_confidence": {"full_name": 0.0-1.0, ...}}
"""

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=120.0,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
    return _client


async def close_ocr_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()


@dataclass(frozen=True)
class OcrPassResult:
    values: dict[str, str | None]
    self_confidence: dict[str, float]


async def is_ocr_available() -> bool:
    try:
        client = _get_client()
        resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return False
        names = {m.get("name") for m in resp.json().get("models", [])}
        return OLLAMA_MODEL in names
    except (httpx.HTTPError, ValueError, KeyError):
        logger.debug("garuda_documents: Ollama not reachable at %s", settings.ollama_url)
        return False


async def _run_one_pass(image_base64: str) -> OcrPassResult | None:
    client = _get_client()
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": _PROMPT, "images": [image_base64]}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    try:
        resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        parsed = json.loads(content)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("garuda_documents: OCR pass failed (%s)", type(exc).__name__)
        return None

    values = {f.value: parsed.get(f.value) for f in PassportReviewFieldName}
    raw_conf = parsed.get("self_confidence") or {}
    self_confidence = {
        f.value: float(raw_conf.get(f.value, 0.0)) if _is_number(raw_conf.get(f.value)) else 0.0
        for f in PassportReviewFieldName
    }
    return OcrPassResult(values=values, self_confidence=self_confidence)


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


async def extract_passport_biodata_dual_pass(
    image_base64: str,
) -> tuple[OcrPassResult, OcrPassResult] | None:
    """Runs the extraction twice. Returns None if either pass fails outright
    (service.py treats that as DOCUMENT_PROCESSING_UNAVAILABLE, never as a silent
    zero-confidence result).
    """
    pass_a = await _run_one_pass(image_base64)
    if pass_a is None:
        return None
    pass_b = await _run_one_pass(image_base64)
    if pass_b is None:
        return None
    return pass_a, pass_b
