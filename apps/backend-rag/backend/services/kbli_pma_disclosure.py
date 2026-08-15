"""Fail-closed disclosure helpers for KBLI foreign-ownership claims.

The canonical catalogue deliberately retains historical/adjudication working
values even when their official per-code locator has not been found.  Those
values are useful for remediation work, but they are not publishable facts.
Every runtime consumer must therefore read the complete evidence tuple, not a
bare ``pma_status`` or ``pma_max_asing`` field.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

PMA_NOT_VERIFIED = "NOT_VERIFIED"
PMA_DECLARED_GAP = "declared_gap"
PMA_LOCATED = "located"
PMA_ALLOWED_STATUSES = frozenset({"TERBUKA", "TERBATAS", "TERTUTUP"})

_BALI_NEUTRAL = {
    "bali_status": None,
    "bali_blocked": None,
    "bali_reason": "",
    "has_bali_l4": False,
}


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _public_pma_cap(payload: Mapping[str, Any]) -> int | float | str | None:
    """Preserve canonical cap shapes without boolean or string coercion.

    ``"special"`` is not self-authenticating: it is publishable only with the
    canonical structured marker that distinguishes a real non-percentage
    regime from malformed or legacy text.
    """
    value = payload.get("pma_max_asing")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    if value == "special" and payload.get("pma_cap_special") is True:
        return "special"
    return None


def pma_claims_verified(payload: Mapping[str, Any]) -> bool:
    """Return whether *payload* carries one complete publishable PMA tuple."""
    status = payload.get("pma_status")
    return bool(
        payload.get("pma_verification_status") == PMA_LOCATED
        and isinstance(status, str)
        and status in PMA_ALLOWED_STATUSES
        and _clean_text(payload.get("pma_official_basis"))
        and _clean_text(payload.get("pma_source_vintage"))
    )


def disclose_pma(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the public PMA view of a canonical/Qdrant/KG record.

    The raw fields are retained only for a ``located`` tuple with a non-empty
    official basis and source vintage.  A partial tuple fails closed as one
    atomic declared gap; no individual status, cap, condition, or editorial
    field survives it.
    """
    if not pma_claims_verified(payload):
        return {
            "pma_status": PMA_NOT_VERIFIED,
            "pma_max_asing": None,
            "pma_verification_status": PMA_DECLARED_GAP,
            "pma_official_basis": None,
            "pma_source_vintage": None,
            "pma_kondisi": None,
            "pma_prioritas": None,
            "pma_nota": None,
            "pma_cap_special": False,
            "pma_cap_verified": False,
        }

    cap = _public_pma_cap(payload)
    return {
        "pma_status": _clean_text(payload.get("pma_status")),
        "pma_max_asing": cap,
        "pma_verification_status": PMA_LOCATED,
        "pma_official_basis": _clean_text(payload.get("pma_official_basis")),
        "pma_source_vintage": _clean_text(payload.get("pma_source_vintage")),
        "pma_kondisi": _clean_text(payload.get("pma_kondisi")),
        "pma_prioritas": payload.get("pma_prioritas") is True,
        "pma_nota": _clean_text(payload.get("pma_nota")),
        "pma_cap_special": cap == "special",
        "pma_cap_verified": cap is not None and payload.get("pma_cap_verified") is True,
    }


def disclose_bali(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the public Bali view without coercing malformed source values.

    A Bali verdict is subordinate to the same complete PMA evidence tuple used
    by :func:`disclose_pma`.  It is publishable only when its status is a
    non-blank exact string and ``blocked`` is an actual boolean.  In
    particular, ``"false"`` must never become ``True`` through Python
    truthiness.  The helper accepts both canonical nested ``l4_bali`` records
    and already-flat Qdrant/KG payloads.
    """
    if not pma_claims_verified(payload):
        return dict(_BALI_NEUTRAL)

    nested = payload.get("l4_bali")
    if nested is not None:
        if not isinstance(nested, Mapping):
            return dict(_BALI_NEUTRAL)
        raw_status = nested.get("status")
        raw_blocked = nested.get("blocked")
        raw_reason = nested.get("reason")
    else:
        raw_status = payload.get("bali_status")
        raw_blocked = payload.get("bali_blocked")
        raw_reason = payload.get("bali_reason")

    status = _clean_text(raw_status)
    if status is None or status != raw_status or not isinstance(raw_blocked, bool):
        return dict(_BALI_NEUTRAL)

    return {
        "bali_status": status,
        "bali_blocked": raw_blocked,
        "bali_reason": _clean_text(raw_reason) or "",
        "has_bali_l4": True,
    }


def _extract_generated_section(text: str, heading: str) -> str | None:
    """Extract one known generated section without trusting adjacent prose."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == heading)
    except StopIteration:
        return None
    end = start + 1
    while end < len(lines) and not (
        lines[end].startswith("## ") and not lines[end].startswith("### ")
    ):
        end += 1
    section = "\n".join(lines[start:end]).strip()
    return section or None


def sanitize_kbli_search_result(
    collection_name: str,
    text: object,
    metadata: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Fail-close KBLI vector text and metadata before either reaches an LLM.

    Live Qdrant points can predate the current generator.  For a declared gap
    we therefore do not attempt substring redaction of editorial prose.  We
    rebuild context from the official BPS description and the generated PP28
    licensing section (whose heading and source are fixed).  PMA, Bali, and
    editorial claims are withheld as one atom from both text and metadata.
    """
    safe_metadata = dict(metadata or {})
    original_text = text if isinstance(text, str) else str(text or "")
    if not collection_name.startswith("kbli_2025_final"):
        return original_text, safe_metadata

    disclosure = disclose_pma(safe_metadata)
    safe_metadata.update(disclosure)

    if disclosure["pma_verification_status"] == PMA_LOCATED:
        return original_text, safe_metadata

    # Legacy and future writers can carry additional ``pma_*`` working fields
    # (for example cap notes, alternate routes, or correction annotations).
    # They belong to the same ownership-claim atom: retaining one while the
    # canonical tuple is withheld can still reveal or imply the raw verdict.
    # Keep only the explicit fail-closed public shape returned by
    # ``disclose_pma``; unknown PMA fields are denied by default.
    public_pma_keys = frozenset(disclosure)
    for key in tuple(safe_metadata):
        if key.startswith("pma_") and key not in public_pma_keys:
            safe_metadata.pop(key, None)
        if key.startswith("bali_") or key == "l4_bali":
            safe_metadata.pop(key, None)

    for key in (
        "intel_2026",
        "gold_content",
        "content",
        "text",
        # Legacy gold points used this ambiguous field for generated prose.
        # New writers also carry ``official_description`` explicitly.
        "description",
    ):
        safe_metadata.pop(key, None)
    safe_metadata["has_intel_2026"] = False
    safe_metadata["has_gold_content"] = False

    code = str(
        safe_metadata.get("kode_kbli")
        or safe_metadata.get("kode_kbli_2025")
        or safe_metadata.get("kode")
        or "unknown"
    )
    title = str(safe_metadata.get("judul") or safe_metadata.get("title") or "").strip()
    description = str(
        safe_metadata.get("official_description") or safe_metadata.get("uraian") or ""
    ).strip()

    lines = [f"# KBLI {code}{f': {title}' if title else ''}"]
    if description:
        lines.extend(["", "## Deskripsi (BPS)", description])

    licensing = _extract_generated_section(
        original_text,
        "## Perizinan per Skala Usaha (PP 28/2025)",
    )
    if licensing:
        lines.extend(["", licensing])

    lines.extend(
        [
            "",
            "## Status PMA: NOT_VERIFIED",
            "- Whole-code foreign ownership is withheld: no located official basis and source vintage are recorded.",
        ]
    )

    return "\n".join(lines), safe_metadata
