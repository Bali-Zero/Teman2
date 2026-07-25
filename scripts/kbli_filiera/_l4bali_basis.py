"""Structural predicates for "what does this Bali verdict actually rest on?".

Shared by the census/emitter (`emit_l4bali_gap_disclosure_spec.py`) and the
sanctioned writer (`cure_l4bali_disclosure.py`) so the two can never drift into
disagreeing about which records are stale-certifying — a derivation rule copied
into two files is how this dataset earned its scars in the first place.

Everything here is STRUCTURAL: enum identity, row shape, key presence. No
sentence is pattern-matched to decide a verdict's basis (cicatrix superscar #3).

THE THREE SHAPES OF A DEAD BASIS
--------------------------------
1. `disputed_key`   — every licensing row was disowned into a
                      `per_skala_disputed_*` block; `per_skala` is empty.
2. `no_oss_scope`   — no scope was ever retrievable from OSS for this code
                      (`_l2_status == "no_oss_risk"`) and `per_skala` is empty.
3. `detached_tier`  — a PARTIAL detach: some rows were disowned, others kept, and
                      the tier the stored verdict was computed from is not among
                      the survivors. `per_skala` is NOT empty, which is exactly
                      why shapes 1-2 cannot see it (PR #2921's partial_detach
                      primitive created this class after the wave-1 cure was
                      written).
"""

from __future__ import annotations

from typing import Any

CODE_FIELD = "kode_kbli_2025"
DISCLOSURE_PREFIX = "[derivation under review] "

GAP_BASIS_DISPUTED_KEY = "disputed_key"
GAP_BASIS_NO_OSS_SCOPE = "no_oss_scope"
GAP_BASIS_DETACHED_TIER = "detached_tier"

# Bali verdicts the #1814 pass (`scripts/resolve_kbli_l4_needs_review.py`)
# computes FROM the risk/scale layer. If that layer is a declared gap, the
# verdict rests on nothing retrievable.
RISK_DERIVED_STATUSES = frozenset(
    {
        "OK_or_HIGHER_RISK",
        "APERTO_BALI_RISCHIO_ALTO",
        "BLOCCATO_CLASSE_RISCHIO",
        "BLOCCATO_DIPENDE_SCOPE",
        "CHIUSO_MORATORIA_BALI",
        "CHIUSO_PMA_NO_BESAR",
    }
)

# Verdicts whose basis is a DIFFERENT, intact layer — never in scope. Listed
# explicitly (rather than "everything else") so a new status added upstream
# fails the completeness check instead of being silently ignored.
NON_RISK_DERIVED_STATUSES = frozenset(
    {
        "TERTUTUP",
        "TERBATAS",
        "TERTUTUP_CANDIDATE",
        "TERBATAS_CANDIDATE",
        "CHIUSO_REGOLATORE_SETTORIALE",
        "CHIUSO_BALI",
        "CHIUSO_BALI_PROPOSTO",
        "NEEDS_REVIEW_NO_OSS_SCOPE",
        "NON_CLASSIFICABILE",
    }
)

# The subset of RISK_DERIVED_STATUSES whose derivation is TOTAL and deterministic
# in `besar_risk()` alone (resolve_kbli_l4_needs_review.py:112-125), so a stored
# status can be checked against the rows that survive a partial detach.
# OK_or_HIGHER_RISK / BLOCCATO_CLASSE_RISCHIO / BLOCCATO_DIPENDE_SCOPE are
# DELIBERATELY excluded: they come from a different pass (lowest risk across ALL
# scales, build_kbli_l2_oss_risk.py), so re-deriving them from the Besar row
# would manufacture false mismatches. Their partial-detach residue, if any ever
# appears, needs its own rule — not a guess made here.
BESAR_DERIVED_STATUSES = frozenset(
    {"CHIUSO_PMA_NO_BESAR", "APERTO_BALI_RISCHIO_ALTO", "CHIUSO_MORATORIA_BALI"}
)

# Tiers that survive the Bali moratorium (resolve_kbli_l4_needs_review.py).
HIGH_RISK_TIERS = frozenset({"Tinggi", "Menengah Tinggi"})


def disputed_keys(record: dict[str, Any]) -> list[str]:
    return sorted(k for k in record if k.startswith("per_skala_disputed"))


def besar_risk(record: dict[str, Any]) -> str | None:
    """Risk tier on the row covering 'Besar' — the tier a PT PMA actually faces.

    Byte-for-byte the same rule as `resolve_kbli_l4_needs_review.besar_risk`,
    which is what wrote these verdicts. None when no surviving row covers Besar.
    """
    for row in record.get("per_skala") or []:
        scales = row.get("skala_usaha") or []
        if isinstance(scales, str):
            scales = [scales]
        if any("besar" in (s or "").lower() for s in scales):
            return (row.get("kategori_risiko") or "").strip()
    return None


def status_matches_surviving_rows(status: str | None, record: dict[str, Any]) -> bool | None:
    """Does `status` still follow from the rows the record actually carries?

    Returns None when the question does not apply (status not Besar-derived) —
    UNDECIDABLE is not the same as consistent, and callers must not conflate them.
    """
    if status not in BESAR_DERIVED_STATUSES:
        return None
    tier = besar_risk(record)
    if status == "CHIUSO_PMA_NO_BESAR":
        return tier is None
    if status == "APERTO_BALI_RISCHIO_ALTO":
        return tier in HIGH_RISK_TIERS
    # CHIUSO_MORATORIA_BALI: a Besar row exists and its tier is a blocked one.
    return tier is not None and tier not in HIGH_RISK_TIERS


def gap_basis(record: dict[str, Any]) -> str | None:
    """Which of the three dead-basis shapes applies, if any."""
    keys = disputed_keys(record)
    rows = record.get("per_skala") or []

    if not rows:
        if keys:
            return GAP_BASIS_DISPUTED_KEY
        if record.get("_l2_status") == "no_oss_risk":
            return GAP_BASIS_NO_OSS_SCOPE
        # An empty layer with neither a disputed key nor a recorded no-scope
        # result is NOT assumed to be a gap (F12: absence needs a second signal).
        return None

    # Rows survive. The layer is only dead if the tier THIS verdict was computed
    # from is not among them — and only a partial detach can do that.
    if keys and status_matches_surviving_rows((record.get("l4_bali") or {}).get("status"), record) is False:
        return GAP_BASIS_DETACHED_TIER
    return None


def still_certifies(l4: dict[str, Any]) -> bool:
    """Is the record still presenting this verdict as settled?"""
    if str(l4.get("reason") or "").startswith(DISCLOSURE_PREFIX):
        return False
    return l4.get("confidence") != "LOW" or l4.get("needs_review") is not True
