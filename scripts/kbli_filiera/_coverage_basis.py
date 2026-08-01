"""Structural predicates for "is this fact sourced, declared-missing, or bare?".

This is the measurement layer of the KBLI completion programme (kbli-navigator
corner §5). The Definition of DONE for the navigator is one sentence:

    every rendered fact is government-sourced WITH A LOCATOR + VINTAGE,
    or an honestly DECLARED GAP — and nothing in between.

"Nothing in between" has a name here: **bare**. A bare fact is a value the
catalogue asserts to a client while carrying nothing on the record that says
where it came from. It is not necessarily wrong; it is *unfalsifiable*, which
is the state this programme exists to eliminate.

Everything below is STRUCTURAL — key presence, enum identity, row shape. No
sentence is pattern-matched to decide provenance (cicatrix superscar #3: a
guard that reads prose measures the form, never the entity). And no axis is
scored from a value that is IDENTICAL on every record: `pma_source` reads
"Perpres 10/2021, 49/2021" on all 1,559 codes, so it is a layer annotation and
can never evidence a per-code verdict — the same shape that made
`moratorium.rule` useless as a per-code basis on 111 pages (corner §1 L2.10).

THE THREE AXES, AND WHY THEY ARE SCORED SEPARATELY
--------------------------------------------------
They are at wildly different stages, and a single blended number would hide
that. Measured on the live canonical at the time of writing: the licensing axis
is complete for honesty, the PMA axis is at ~1%, and they cover different
populations (221 vs 1,559). One number would have read "mostly done".

1. LICENSING (`per_skala`) — the risk/permit rows.
2. PMA (`pma_max_asing` / `pma_status`) — the foreign-ownership verdict, the
   single most-read fact on `/kbli/<code>`.
3. CROSSWALK (`bps_2020_ancestors`) — which KBLI-2020 code this descends from.

A NOTE ON THE CROSSWALK AXIS, so nobody "fixes" it into a false red: a
mechanically-parsed ancestor carrying `inheritance_verdict: not-adjudicated`
is HONEST and is rendered as such ("provenance only, not a licensing claim").
It counts as LOCATED. Whether the 2020 regulatory regime transfers is a
separate question, tracked as the `adjudicated` sub-metric — a number that
matters for the programme but is not a defect while the page does not claim it.
"""

from __future__ import annotations

from typing import Any

CODE_FIELD = "kode_kbli_2025"

# The one `_l2_source` value that names a vintage-2025 government endpoint.
# EXACT match, never a substring: an unrecognised marker must fall through to
# `bare` rather than be granted provenance it did not earn (the TRACK-P
# provenance badge already learned this — corner §1).
OSS_2025_SOURCE = "OSS_RBA_resiko_2025"

# `_l2_status` written by `build_kbli_l2_oss_risk.py` when OSS served no scope:
# a missing dump line, ANY non-200, or `success: false`. It does NOT mean 404
# (corner §4 rule F12) — it means "not retrievable when this dataset was built".
NO_OSS_RISK = "no_oss_risk"

# --- states -----------------------------------------------------------------
# LOCATED_* : the record names where the value came from.
# DECLARED_*: the record says, on itself, that it has no verified value.
# BARE      : a value asserted with neither. THE defect this programme closes.

LIC_SOURCED_OSS_2025 = "sourced_oss_2025"
LIC_SOURCED_PP28_VINTAGE_PENDING = "sourced_pp28_vintage_pending"
LIC_DECLARED_GAP = "declared_gap"
LIC_BARE = "bare"

PMA_LOCATED = "located"
PMA_DECLARED_UNVERIFIED = "declared_unverified"
PMA_BARE = "bare"

XW_LOCATED = "located"
XW_DECLARED_GAP = "declared_gap"
XW_ABSENT = "absent"

# States that count as honest for the ratchet. Everything else is a defect.
HONEST_LICENSING = frozenset(
    {LIC_SOURCED_OSS_2025, LIC_SOURCED_PP28_VINTAGE_PENDING, LIC_DECLARED_GAP}
)
HONEST_PMA = frozenset({PMA_LOCATED, PMA_DECLARED_UNVERIFIED})
HONEST_CROSSWALK = frozenset({XW_LOCATED, XW_DECLARED_GAP})

# STRONG states: a per-code government locator of the CURRENT vintage. Honesty
# alone is not enough for the ratchet, and the reason is measured, not theoretical:
# wiping `per_skala` on all 1,342 codes that have rows turns every one of them
# into `declared_gap`, which is honest — so the aggregate score reads a PERFECT
# 1,559/1,559 while the entire verified licensing layer has been destroyed. Run
# on the real dataset 2026-08-01, the count-only ratchet passed that mutation.
# A gate that rewards deleting data is worse than no gate.
#
# So the ratchet also asserts, per code: a code that HELD a strong state may
# never stop holding it.
#
# `sourced_pp28_vintage_pending` is deliberately NOT strong. Detaching a
# vintage-2020 PP28 row into a declared gap is this programme's own cure (Batch
# A did it 122 times); marking it strong would make the gate fire on exactly the
# work it exists to protect. A pp28 code that degrades to `bare` is still caught
# — by the bare-count arm.
STRONG_LICENSING = frozenset({LIC_SOURCED_OSS_2025})
STRONG_PMA = frozenset({PMA_LOCATED})
STRONG_CROSSWALK = frozenset({XW_LOCATED})


def _rows(record: dict[str, Any]) -> list:
    value = record.get("per_skala")
    return value if isinstance(value, list) else []


def classify_licensing(record: dict[str, Any]) -> str:
    """Where do this record's licensing/risk rows come from?

    `declared_gap` is checked FIRST and unconditionally: an empty `per_skala`
    is the detach primitive this programme uses to say "we do not have a
    verified licensing basis for this code", and it is honest regardless of
    what any source marker says.
    """
    rows = _rows(record)
    if not rows:
        return LIC_DECLARED_GAP
    if record.get("_l2_source") == OSS_2025_SOURCE:
        return LIC_SOURCED_OSS_2025
    if record.get("_l2_status") == NO_OSS_RISK and record.get("pp28_sources"):
        # Rows kept from the PP28 lampiran with the lampiran row named. The
        # source IS on the record — but PP28 is KBLI-2020 vintage, so this is
        # located-but-pending, never conflated with the 2025-native class.
        return LIC_SOURCED_PP28_VINTAGE_PENDING
    return LIC_BARE


def classify_pma(record: dict[str, Any]) -> str:
    """Does the foreign-ownership verdict name its basis?

    `pma_official_basis` is the only per-code locator in this layer (it quotes
    the Perpres lampiran and line). `pma_source` is deliberately NOT consulted:
    it is one identical string on every record.

    Precedence is LOCATED over DECLARED_UNVERIFIED — a record that carries a
    real adjudicated basis is located even if an older `pma_cap_verified: false`
    is still sitting on it; the basis is the stronger, later statement.
    """
    basis = record.get("pma_official_basis")
    if isinstance(basis, str) and basis.strip():
        return PMA_LOCATED
    if record.get("pma_cap_verified") is False:
        return PMA_DECLARED_UNVERIFIED
    return PMA_BARE


def classify_crosswalk(record: dict[str, Any]) -> str:
    """Is the KBLI-2020 ancestry recorded with a document locator?

    LOCATED requires a non-empty `source_locator` — the ancestor codes alone
    are a claim, the lampiran/page reference is what makes it checkable.
    """
    ancestors = record.get("bps_2020_ancestors")
    if isinstance(ancestors, dict):
        locator = ancestors.get("source_locator")
        if isinstance(locator, list) and locator:
            return XW_LOCATED
        if ancestors.get("no_ancestor_recorded") is True:
            return XW_DECLARED_GAP
    return XW_ABSENT


def crosswalk_is_adjudicated(record: dict[str, Any]) -> bool:
    """Sub-metric, NOT a defect state: has a human/gate ruled on whether the
    2020 regulatory regime actually transfers to this 2025 code?

    `not-adjudicated` is the honest mechanical default and is what the page
    renders. This counter exists so the programme can see the real remaining
    work without the scoreboard calling honest provenance a defect."""
    ancestors = record.get("bps_2020_ancestors")
    if not isinstance(ancestors, dict):
        return False
    verdict = ancestors.get("inheritance_verdict")
    return isinstance(verdict, str) and verdict not in ("", "not-adjudicated")


AXES: dict[str, tuple] = {
    "licensing": (classify_licensing, HONEST_LICENSING, STRONG_LICENSING),
    "pma": (classify_pma, HONEST_PMA, STRONG_PMA),
    "crosswalk": (classify_crosswalk, HONEST_CROSSWALK, STRONG_CROSSWALK),
}
