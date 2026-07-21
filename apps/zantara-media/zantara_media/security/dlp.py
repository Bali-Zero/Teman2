"""Data Loss Prevention (DLP) module for Indonesian PII detection.

Three-layer detection:
  Layer 1 — Filename trigger words.
  Layer 2 — Regex patterns for common Indonesian PII.
  Layer 3 — LLM classifier via Ollama (only when layers 1+2 pass).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns & triggers
# ---------------------------------------------------------------------------

INDONESIAN_PII_PATTERNS: dict[str, str] = {
    "NIK": r"\b\d{16}\b",
    "KITAS_NUMBER": r"\b\d{2}[A-Z]{2}\d{4,7}\b",
    "PASSPORT_ID": r"\b[A-Z]\d{7}\b",
    "NPWP": r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b",
    "BANK_ACCOUNT_RUPIAH": r"\bIDR\s*\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "PHONE_INDONESIAN": r"\b\+?62[\d\s-]{8,15}\b",
}

FILENAME_TRIGGERS: list[str] = [
    "passport",
    "kitas",
    "npwp",
    "client_",
    "invoice",
    "contract",
    "akta",
]

# Compiled regex cache (compiled once at module load)
_COMPILED_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern) for name, pattern in INDONESIAN_PII_PATTERNS.items()
}

# Ollama config
_OLLAMA_BASE_URL = "http://localhost:11434"
_LLM_PRIMARY_MODEL = "gemma4:26b"
_LLM_FALLBACK_MODEL = "gemma3:27b"
_LLM_TIMEOUT_S = 30.0
_LLM_PROMPT = (
    "Does this text contain any personal identification information (PII), "
    "names of real people, contact details, or private data? "
    'Answer in JSON: {"contains_pii": bool, "reason": str}'
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DLPResult:
    """Result of a DLP check."""

    has_pii: bool
    patterns: list[str] = field(default_factory=list)
    confidence: float = 0.0
    quarantine_reason: dict = field(default_factory=dict)
    indeterminate: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def dlp_check(text: str, filename: str) -> DLPResult:
    """Run all three DLP layers on *text* / *filename*.

    Args:
        text: Extracted text content to inspect.
        filename: Original filename for trigger matching.

    Returns:
        :class:`DLPResult` with detection details.
    """
    found_patterns: list[str] = []
    quarantine_reason: dict = {}

    # ------------------------------------------------------------------
    # Layer 1: filename triggers
    # ------------------------------------------------------------------
    lower_name = filename.lower()
    triggered: list[str] = [t for t in FILENAME_TRIGGERS if t in lower_name]
    if triggered:
        quarantine_reason["filename_triggers"] = triggered
        found_patterns.extend(f"FILENAME:{t}" for t in triggered)
        logger.debug("DLP Layer 1 hit for %s: %s", filename, triggered)

    # ------------------------------------------------------------------
    # Layer 2: regex patterns
    # ------------------------------------------------------------------
    for pattern_name, compiled in _COMPILED_PATTERNS.items():
        if compiled.search(text):
            found_patterns.append(pattern_name)
            logger.debug("DLP Layer 2 hit for %s: pattern=%s", filename, pattern_name)

    # If either layer 1 or 2 found something, we're done — no need for LLM.
    if found_patterns:
        n = len(found_patterns)
        confidence = 1.0 if n >= 2 else 0.7
        return DLPResult(
            has_pii=True,
            patterns=found_patterns,
            confidence=confidence,
            quarantine_reason=quarantine_reason,
        )

    # ------------------------------------------------------------------
    # Layer 3: LLM classifier (only reached when layers 1+2 found nothing)
    # ------------------------------------------------------------------
    llm_result = await _llm_classify(text)
    if llm_result is None:
        return DLPResult(
            has_pii=True,
            patterns=["LLM_CLASSIFIER_UNAVAILABLE"],
            confidence=0.0,
            quarantine_reason={"classifier_status": "unavailable"},
            indeterminate=True,
        )
    if llm_result.get("contains_pii", False):
        return DLPResult(
            has_pii=True,
            patterns=["LLM_CLASSIFIER"],
            confidence=0.5,
            quarantine_reason={"classifier_status": "pii_detected"},
        )

    return DLPResult(has_pii=False, confidence=0.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _llm_classify(text: str) -> dict[str, Any] | None:
    """Call the local classifier, returning ``None`` when no model is authoritative."""
    truncated = text[:4000]  # keep prompt short
    full_prompt = f"{_LLM_PROMPT}\n\nText:\n{truncated}"

    for model in (_LLM_PRIMARY_MODEL, _LLM_FALLBACK_MODEL):
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=_LLM_TIMEOUT_S) as client:
                response = await client.post(
                    f"{_OLLAMA_BASE_URL}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                payload_body = response.json()
                if not isinstance(payload_body, dict):
                    logger.warning("DLP LLM returned an invalid envelope (model=%s)", model)
                    continue
                raw_response = payload_body.get("response")
                if not isinstance(raw_response, str):
                    logger.warning("DLP LLM returned an invalid response (model=%s)", model)
                    continue
                parsed = _parse_llm_json(raw_response)
                if parsed is not None:
                    return parsed
                logger.warning("DLP LLM returned an invalid classification (model=%s)", model)
        except httpx.TimeoutException:
            logger.warning("DLP LLM timed out (model=%s)", model)
        except Exception:
            logger.warning("DLP LLM unavailable (model=%s)", model)

    return None


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Extract a closed classifier result without retaining the raw response."""
    # Try to find a JSON object anywhere in the response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        parsed = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"contains_pii", "reason"}
        or not isinstance(parsed.get("contains_pii"), bool)
        or not isinstance(parsed.get("reason"), str)
    ):
        return None
    return parsed
