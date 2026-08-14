"""Fail-closed disclosure helpers for KBLI foreign-ownership claims.

The canonical catalogue deliberately retains historical/adjudication working
values even when their official per-code locator has not been found.  Those
values are useful for remediation work, but they are not publishable facts.
Every runtime consumer must therefore read the complete evidence tuple, not a
bare ``pma_status`` or ``pma_max_asing`` field.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PMA_NOT_VERIFIED = "NOT_VERIFIED"
PMA_DECLARED_GAP = "declared_gap"
PMA_LOCATED = "located"
PMA_ALLOWED_STATUSES = frozenset({"TERBUKA", "TERBATAS", "TERTUTUP"})


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


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
            "pma_cap_verified": False,
        }

    return {
        "pma_status": _clean_text(payload.get("pma_status")),
        "pma_max_asing": payload.get("pma_max_asing"),
        "pma_verification_status": PMA_LOCATED,
        "pma_official_basis": _clean_text(payload.get("pma_official_basis")),
        "pma_source_vintage": _clean_text(payload.get("pma_source_vintage")),
        "pma_kondisi": payload.get("pma_kondisi"),
        "pma_prioritas": payload.get("pma_prioritas"),
        "pma_nota": payload.get("pma_nota"),
        "pma_cap_verified": bool(payload.get("pma_cap_verified")),
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
    rebuild context from the official BPS description, the generated PP28
    licensing section (whose heading and source are fixed), and structured
    Bali booleans.  Raw PMA/editorial fields are removed from metadata too.
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

    for key in (
        "intel_2026",
        "gold_content",
        "bali_reason",
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

    if "bali_blocked" in safe_metadata:
        lines.extend(["", "## Bali-side registration record"])
        if safe_metadata.get("bali_blocked") is True:
            lines.append(
                "- BLOCKED for PT PMA registration in the Bali-side record; national PMA status and cap remain NOT_VERIFIED."
            )
        elif safe_metadata.get("bali_blocked") is False:
            lines.append(
                "- Not marked blocked in the Bali-side record; this is not national PMA permission, whose status and cap remain NOT_VERIFIED."
            )
        else:
            lines.append(
                "- Bali-side registration is unknown; national PMA status and cap remain NOT_VERIFIED."
            )

    return "\n".join(lines), safe_metadata
