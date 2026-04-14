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
    name: re.compile(pattern)
    for name, pattern in INDONESIAN_PII_PATTERNS.items()
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
    llm_result = await _llm_classify(text, filename)
    if llm_result.get("contains_pii", False):
        return DLPResult(
            has_pii=True,
            patterns=["LLM_CLASSIFIER"],
            confidence=0.5,
            quarantine_reason={"llm_reason": llm_result.get("reason", "")},
        )

    return DLPResult(has_pii=False, confidence=0.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _llm_classify(text: str, filename: str) -> dict:
    """Call Ollama LLM classifier. Returns parsed JSON dict or empty dict on failure."""
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
                raw_response: str = response.json().get("response", "")
                return _parse_llm_json(raw_response, filename)
        except httpx.TimeoutException:
            logger.warning("DLP LLM timed out (model=%s) for %s", model, filename)
            # On timeout, fail open — don't block content
            return {}
        except Exception as exc:
            logger.warning("DLP LLM error (model=%s) for %s: %s", model, filename, exc)

    # Both models failed — fail open
    return {}


def _parse_llm_json(raw: str, filename: str) -> dict:
    """Extract JSON from raw LLM response text. On parse error, returns {}."""
    # Try to find a JSON object anywhere in the response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        logger.debug("DLP LLM returned no JSON for %s: %r", filename, raw[:200])
        return {}
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError as exc:
        logger.debug("DLP LLM JSON parse error for %s: %s | raw=%r", filename, exc, raw[:200])
        return {}
