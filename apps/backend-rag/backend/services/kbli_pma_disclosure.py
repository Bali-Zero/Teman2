"""Fail-closed disclosure helpers for KBLI foreign-ownership claims.

The canonical catalogue deliberately retains historical/adjudication working
values even when their official per-code locator has not been found.  Those
values are useful for remediation work, but they are not publishable facts.
Every runtime consumer must therefore read the complete evidence tuple, not a
bare ``pma_status`` or ``pma_max_asing`` field.

The one deliberate exception is the Bali provincial closure: Bali's Provincial
Government closed OSS to new PT PMA licensing for 18 business fields (press
release, 24 Jul 2026), independently of whether the national PMA tuple for
that code has been verified. ``disclose_bali`` discloses that sourced closure
— status, scope, confidence and its source URL — even on a ``NOT_VERIFIED``
record; see :func:`is_sourced_bali_closure` for the exact predicate.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

PMA_NOT_VERIFIED = "NOT_VERIFIED"
PMA_DECLARED_GAP = "declared_gap"
PMA_LOCATED = "located"
PMA_ALLOWED_STATUSES = frozenset({"TERBUKA", "TERBATAS", "TERTUTUP"})
BALI_ALLOWED_STATUSES = frozenset(
    {
        "APERTO_BALI_RISCHIO_ALTO",
        "ATTENZIONE_FASCIA_BALI",
        "BLOCCATO_CLASSE_RISCHIO",
        "BLOCCATO_DIPENDE_SCOPE",
        "CHIUSO_BALI",
        "CHIUSO_BALI_PROPOSTO",
        "CHIUSO_MORATORIA_BALI",
        "CHIUSO_PMA_NO_BESAR",
        "CHIUSO_REGOLATORE_SETTORIALE",
        "NON_CLASSIFICABILE",
        "OK_or_HIGHER_RISK",
        "TERBATAS",
        "TERTUTUP",
    }
)

_BALI_NEUTRAL = {
    "bali_status": None,
    "bali_blocked": None,
    "bali_needs_review": None,
    "bali_reason": "",
    "has_bali_l4": False,
    "bali_closure_url": None,
    "bali_closure_scope": None,
    "bali_confidence": None,
}

# The one Bali status that can be disclosed WITHOUT a verified national PMA
# tuple — a sourced provincial closure (Bali Provincial Government press
# release, 24 Jul 2026) speaks about Bali registrability only, never about
# national foreign-ownership.
_CHIUSO_BALI_STATUS = "CHIUSO_BALI"
_BALI_CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})


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
    if payload.get("pma_cap_verified") is not True:
        return None

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


def _valid_http_url(value: object) -> str | None:
    """Return *value* only if it is a non-empty ``http://``/``https://`` string."""
    text = _clean_text(value)
    if text is None:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return None


def is_sourced_bali_closure(
    *,
    status: object,
    blocked: object,
    needs_review: object,
    closure_url: object,
) -> bool:
    """True for the one Bali closure disclosable without a verified PMA tuple.

    Mirrors the website's ``isSourcedBaliClosure``: exact ``"CHIUSO_BALI"``
    status, a real ``blocked is True``, a real bool ``needs_review``, and an
    http(s) closure source URL. Every other status, a non-boolean
    ``needs_review``, a false/absent ``blocked``, or a missing/invalid URL
    falls back to the ordinary national-tuple gate — withheld exactly as
    before on an unverified record.
    """
    return bool(
        status == _CHIUSO_BALI_STATUS
        and blocked is True
        and isinstance(needs_review, bool)
        and _valid_http_url(closure_url) is not None
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
        "pma_cap_verified": cap is not None,
    }


def _bali_raw_fields(
    payload: Mapping[str, Any],
) -> tuple[Any, Any, Any, Any, Any, Any, Any] | None:
    """Read the raw Bali tuple from nested ``l4_bali`` or flat payload keys.

    Returns ``None`` when a nested ``l4_bali`` value is present but is not a
    mapping — the caller must withhold rather than guess a shape.
    """
    nested = payload.get("l4_bali")
    if nested is not None:
        if not isinstance(nested, Mapping):
            return None
        closure = nested.get("closure")
        closure = closure if isinstance(closure, Mapping) else {}
        return (
            nested.get("status"),
            nested.get("blocked"),
            nested.get("needs_review"),
            nested.get("reason"),
            closure.get("url"),
            closure.get("scope_qualifier"),
            nested.get("confidence"),
        )
    return (
        payload.get("bali_status"),
        payload.get("bali_blocked"),
        payload.get("bali_needs_review"),
        payload.get("bali_reason"),
        payload.get("bali_closure_url"),
        payload.get("bali_closure_scope"),
        payload.get("bali_confidence"),
    )


def disclose_bali(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the public Bali view without coercing malformed source values.

    A Bali verdict is ordinarily subordinate to the same complete PMA evidence
    tuple used by :func:`disclose_pma`. The ONE exception is a sourced Bali
    closure (see :func:`is_sourced_bali_closure`): the Bali Provincial
    Government's own 24 Jul 2026 press release closing OSS to new PT PMA
    licensing for 18 business fields is a Bali-only fact with its own citable
    source, and it is disclosable even while the national PMA tuple stays
    ``NOT_VERIFIED`` — the closure asserts nothing about national ownership.

    Every publishable tuple still requires its status to be one of the exact
    canonical Bali tokens and both ``blocked`` and ``needs_review`` to be
    actual booleans. In particular, ``"false"`` must never become ``True``
    through Python truthiness. The helper accepts both canonical nested
    ``l4_bali`` records (reading ``closure.url``/``closure.scope_qualifier``/
    ``confidence``) and already-flat Qdrant/KG payloads (``bali_closure_url``/
    ``bali_closure_scope``/``bali_confidence``).
    """
    raw = _bali_raw_fields(payload)
    if raw is None:
        return dict(_BALI_NEUTRAL)
    (
        raw_status,
        raw_blocked,
        raw_needs_review,
        raw_reason,
        raw_closure_url,
        raw_closure_scope,
        raw_confidence,
    ) = raw

    status = _clean_text(raw_status)
    if (
        status not in BALI_ALLOWED_STATUSES
        or status != raw_status
        or not isinstance(raw_blocked, bool)
        or not isinstance(raw_needs_review, bool)
    ):
        return dict(_BALI_NEUTRAL)

    closure_url = _valid_http_url(raw_closure_url)
    sourced_closure = is_sourced_bali_closure(
        status=status,
        blocked=raw_blocked,
        needs_review=raw_needs_review,
        closure_url=closure_url,
    )
    if not sourced_closure and not pma_claims_verified(payload):
        return dict(_BALI_NEUTRAL)

    confidence = _clean_text(raw_confidence)
    if isinstance(confidence, str):
        confidence = confidence.upper()
    if confidence not in _BALI_CONFIDENCE_LEVELS:
        # Consumers treat None as "not HIGH" (hedged), never as certain.
        confidence = None

    return {
        "bali_status": status,
        "bali_blocked": raw_blocked,
        "bali_needs_review": raw_needs_review,
        "bali_reason": _clean_text(raw_reason) or "",
        "has_bali_l4": True,
        "bali_closure_url": closure_url,
        "bali_closure_scope": _clean_text(raw_closure_scope),
        "bali_confidence": confidence,
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

    Live Qdrant points can predate the current generator.  A complete PMA tuple
    authenticates the structured verdict, not arbitrary prose stored beside it.
    We therefore never return the original KBLI document wholesale.  Context is
    rebuilt from the official description, the known PP28 licensing section,
    and freshly disclosed structured PMA/Bali fields; editorial prose is removed
    from both text and metadata for located and gap records alike.
    """
    safe_metadata = dict(metadata or {})
    original_text = text if isinstance(text, str) else str(text or "")
    if not collection_name.startswith("kbli_2025_final"):
        return original_text, safe_metadata

    disclosure = disclose_pma(safe_metadata)
    bali = disclose_bali(safe_metadata)

    # Legacy and future writers can carry additional ``pma_*`` working fields
    # (for example cap notes, alternate routes, or correction annotations).
    # They belong to the same ownership-claim atom: retaining one while the
    # canonical tuple is withheld can still reveal or imply the raw verdict.
    # Keep only the explicit fail-closed public shape returned by
    # ``disclose_pma``; unknown PMA fields are denied by default.
    for key in tuple(safe_metadata):
        if key.startswith("pma_"):
            safe_metadata.pop(key, None)
        if key.startswith("bali_") or key in {"l4_bali", "has_bali_l4"}:
            safe_metadata.pop(key, None)

    for key in (
        "intel_2026",
        "gold_content",
        "content",
        "text",
        # Legacy gold points used this ambiguous field for generated prose.
        # New writers also carry ``official_description`` explicitly.
        "description",
        "editorial_disclosed",
    ):
        safe_metadata.pop(key, None)
    safe_metadata.update(disclosure)
    if bali["has_bali_l4"]:
        safe_metadata.update(bali)
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

    if disclosure["pma_verification_status"] == PMA_LOCATED:
        lines.extend(["", f"## Status PMA: {disclosure['pma_status']}"])
        if disclosure["pma_cap_verified"] is True:
            cap = disclosure["pma_max_asing"]
            if cap == "special":
                lines.append("- Foreign ownership cap: verified special non-percentage regime")
            elif cap is not None:
                lines.append(f"- Foreign ownership cap: {cap}%")
        else:
            lines.append("- Foreign ownership cap: not verified")
        lines.extend(
            [
                f"- Official basis: {disclosure['pma_official_basis']}",
                f"- Source vintage: {disclosure['pma_source_vintage']}",
            ]
        )
        if disclosure["pma_kondisi"]:
            lines.append(f"- Conditions: {disclosure['pma_kondisi']}")
        if disclosure["pma_nota"]:
            lines.append(f"- Note: {disclosure['pma_nota']}")
        if bali["has_bali_l4"]:
            lines.extend(
                [
                    "",
                    f"## Bali registration status: {bali['bali_status']}",
                    f"- Blocked: {'yes' if bali['bali_blocked'] else 'no'}",
                ]
            )
            if bali["bali_reason"]:
                lines.append(f"- Reason: {bali['bali_reason']}")
            if bali["bali_closure_scope"]:
                lines.append(f"- Scope: {bali['bali_closure_scope']}")
            if bali["bali_closure_url"]:
                lines.append(f"- Source: {bali['bali_closure_url']}")
    else:
        lines.extend(
            [
                "",
                "## Status PMA: NOT_VERIFIED",
                "- Whole-code foreign ownership is withheld: no located official basis and source vintage are recorded.",
            ]
        )
        # `has_bali_l4` can only be True here for the narrow sourced-closure
        # class (see `is_sourced_bali_closure`): the closure has its own
        # published Bali source and is disclosed even though the national
        # tuple above stays withheld. Never let this imply a national verdict.
        if bali["has_bali_l4"]:
            lines.extend(
                [
                    "",
                    f"## Bali registration status: {bali['bali_status']} (Bali-sourced closure)",
                    f"- Blocked: {'yes' if bali['bali_blocked'] else 'no'}",
                ]
            )
            if bali["bali_reason"]:
                lines.append(f"- Reason: {bali['bali_reason']}")
            if bali["bali_closure_scope"]:
                lines.append(f"- Scope: {bali['bali_closure_scope']}")
            if bali["bali_confidence"] and bali["bali_confidence"] != "HIGH":
                lines.append(
                    "- Note: confidence on this closure is "
                    f"{bali['bali_confidence']}; treat as a conservative "
                    "reading pending further verification, not a certified "
                    "legal determination."
                )
            if bali["bali_closure_url"]:
                lines.append(f"- Source: {bali['bali_closure_url']}")

    return "\n".join(lines), safe_metadata
