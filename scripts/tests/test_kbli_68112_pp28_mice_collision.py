"""False-friend regression registry — PP28-vs-KBLI-2025 code-number collisions.

PP 28/2025's Lampiran licensing tables are numbered on the OLD KBLI 2020
codebook. BPS Peraturan 7/2025 defines KBLI 2025 — the codebook OSS actually
uses today. When a 5-digit code number was reassigned to a DIFFERENT activity
between the two codebooks, a naive code-number join (rather than an
activity/judul join) can graft the OLD activity's licensing text onto the NEW
code's served record. The served judul/uraian are correct (they come from the
2025 codebook); only the licensing block (per_skala) — and occasionally an
editorial field that echoes it — carries the wrong activity's requirements.

Confirmed instances so far (full sweep methodology + full result set:
`research/operations/2026-07-16-kbli-false-friend-sweep.{json,md}`):

  - **68112** (fixed 2026-07-16, PR #2508): KBLI 2025 = residential leasing
    (BPS Peraturan 7/2025). PP 28/2025's 68112 (KBLI 2020 numbering) = MICE-venue
    rental (Lampiran I.L, Sektor Pariwisata, p.I.L.44). The contamination also
    leaked into `intel_2026.whatYouNeed` outside per_skala, and separately into
    the curated `apps/mouth/data/kbli-gold-all.json` (a dataset the sync script
    does not propagate to) — third surface fixed same day.
  - **51103 / 51203** (fixed 2026-07-16, this PR): KBLI 2025 = space transport
    for passengers / cargo (BPS Peraturan 7/2025, brand-new codes with no PP28
    equivalent activity). PP 28/2025's 51103/51203 (KBLI 2020 numbering) =
    scheduled international commercial AVIATION for passengers/cargo. Only
    per_skala was contaminated — no leak found in any other field, and neither
    code exists in the gold-curated dataset.

OSS RBA ruang-lingkup returns 404 for all three new codes (verified 2026-07-16)
— there is no published risk-based NSPK to fabricate a real licensing block
from, so the honest fix in every case is: per_skala -> [], the original
collision-derived block preserved verbatim under a `per_skala_disputed_pp28_*`
audit key (never silently deleted), and an advisory `_data_note` naming the
collision.

This test suite is a REGISTRY of all known collisions (`FALSE_FRIEND_REGISTRY`
below), not a single hardcoded case — extend the registry, not the test
functions, when the sweep confirms a new instance. Each entry is scoped to its
OWN code + OWN banned markers: a dataset-wide "ban this substring everywhere"
rule would false-positive on legitimately-matching codes (68124/82300 for
MICE/Venue; 51101/51201 for pesawat udara/penerbangan sipil — real aviation
codes that must keep that text). Guilt+innocence discipline per repo
scar-family #3 (`.claude/rules/cicatrix-superscar.md`): every case in the
registry gets both a colpevolezza test (per_skala clean, whole-record guard)
and an innocenza test (sibling legitimate codes untouched).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# A leaf string outside a case's audit key is allowed to name a banned marker
# ONLY when it is DISCLAIMING the collision (explaining that the text belonged
# to a different activity under the old codebook and does not apply here) —
# never when it ASSERTS the old licensing as this code's own requirement.
# "code-number collision" is the phrase every legitimate disclaimer (the
# `_data_note` and any corrected editorial field) shares verbatim; it is
# absent from contaminated text. Entity/intent match, not a bare substring.
DISCLAIMER_MARKER = "code-number collision"

# Every SERVED/canonical copy that must stay clean. Gitignored RAG runtime
# copies are materialized by scripts/sync_kbli_dataset.sh at build time and
# may be absent on a fresh checkout/CI runner — skipped if missing, same
# convention as that script.
DATASET_PATHS = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # tracked canonical
    REPO_ROOT / "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
]

# The one gold-curated dataset that is NOT propagated by sync_kbli_dataset.sh
# (separate 428-record curated file, keyed directly by code — see the
# gold-specific tests below).
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"


@dataclass(frozen=True)
class FalseFriendCase:
    code: str
    audit_key: str
    banned_markers: tuple[str, ...]
    reference_code: str | None  # nearest sibling code the advisory note should cite, if any
    gold_present: bool  # whether this code also exists in the separate gold dataset
    innocent_controls: tuple[str, ...]  # sibling codes that legitimately carry these markers


FALSE_FRIEND_REGISTRY: tuple[FalseFriendCase, ...] = (
    FalseFriendCase(
        code="68112",
        audit_key="per_skala_disputed_pp28_mice",
        banned_markers=("MICE", "Venue"),
        reference_code="68111",
        gold_present=True,
        innocent_controls=("68124", "82300"),
    ),
    FalseFriendCase(
        code="51103",
        audit_key="per_skala_disputed_pp28_aviation",
        banned_markers=("pesawat udara", "penerbangan sipil"),
        reference_code=None,
        gold_present=False,
        innocent_controls=("51101", "51201"),
    ),
    FalseFriendCase(
        code="51203",
        audit_key="per_skala_disputed_pp28_aviation",
        banned_markers=("pesawat udara", "penerbangan sipil"),
        reference_code=None,
        gold_present=False,
        innocent_controls=("51101", "51201"),
    ),
)

_CASE_IDS = [c.code for c in FALSE_FRIEND_REGISTRY]


def _load_record(path: Path, code: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for rec in data["data"]:
        if rec.get("kode_kbli_2025") == code:
            return rec
    raise AssertionError(f"{path}: record {code} not found in dataset")


def _existing_paths():
    return [p for p in DATASET_PATHS if p.exists()]


_EXISTING_PATH_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_paths()]


def _iter_leaf_strings(obj, path=""):
    """Yield (path, value) for every string leaf in a nested dict/list structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_leaf_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_leaf_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


# --- Colpevolezza: per-case regression tests, run against every dataset copy ---


@pytest.mark.parametrize("path", _existing_paths(), ids=_EXISTING_PATH_IDS)
@pytest.mark.parametrize("case", FALSE_FRIEND_REGISTRY, ids=_CASE_IDS)
def test_per_skala_has_no_collision_markers(case: FalseFriendCase, path: Path):
    rec = _load_record(path, case.code)
    per_skala_blob = json.dumps(rec.get("per_skala") or [], ensure_ascii=False)
    for marker in case.banned_markers:
        assert marker not in per_skala_blob, (
            f"{path}: {case.code} per_skala still contains {marker!r} — the PP28 "
            f"collision-derived licensing has leaked back into this code. Move it "
            f"to {case.audit_key} instead of shipping it as this code's own licensing."
        )


@pytest.mark.parametrize("case", FALSE_FRIEND_REGISTRY, ids=_CASE_IDS)
def test_disputed_block_preserved_for_audit(case: FalseFriendCase):
    """The removed block must be KEPT (not silently deleted) for audit."""
    rec = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json", case.code)
    disputed = rec.get(case.audit_key)
    assert disputed, (
        f"{case.code} must retain the original PP28-collision per_skala under "
        f"{case.audit_key} for audit — it should never be silently deleted."
    )
    blob = json.dumps(disputed, ensure_ascii=False)
    assert any(m in blob for m in case.banned_markers), (
        f"{case.audit_key} should still contain the collision-derived text it was "
        "moved to preserve — if this trips, the audit trail itself was edited."
    )


@pytest.mark.parametrize("case", FALSE_FRIEND_REGISTRY, ids=_CASE_IDS)
def test_has_advisory_data_note(case: FalseFriendCase):
    rec = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json", case.code)
    note = rec.get("_data_note", "")
    assert note, f"{case.code}: missing advisory _data_note"
    assert "OSS" in note and "404" in note, (
        f"{case.code}: advisory note should explain the OSS 404 (no published NSPK yet)"
    )
    assert DISCLAIMER_MARKER in note.lower(), (
        f"{case.code}: advisory note should name the collision using the shared "
        f"disclaimer phrase {DISCLAIMER_MARKER!r}"
    )
    if case.reference_code:
        assert case.reference_code in note, (
            f"{case.code}: advisory note should point to the nearest published "
            f"reference code {case.reference_code}"
        )


@pytest.mark.parametrize("path", _existing_paths(), ids=_EXISTING_PATH_IDS)
@pytest.mark.parametrize("case", FALSE_FRIEND_REGISTRY, ids=_CASE_IDS)
def test_record_has_no_collision_markers_outside_audit_key(case: FalseFriendCase, path: Path):
    """Whole-record guard: no field of this code — intel_2026, l4_bali, pma_*,
    etc. — may ASSERT the old-codebook licensing as applicable, anywhere in the
    record, EXCEPT the intentional audit key (excluded entirely — it exists
    precisely to preserve the original collision-derived block verbatim).

    A field outside the audit key MAY still name a banned marker if — and only
    if — it is disclaiming the collision (contains DISCLAIMER_MARKER): this is
    legitimate explanatory prose, not a resurgence of the bug.
    """
    rec = _load_record(path, case.code)
    rec_without_audit_key = {k: v for k, v in rec.items() if k != case.audit_key}
    for field_path, value in _iter_leaf_strings(rec_without_audit_key):
        if any(marker in value for marker in case.banned_markers):
            assert DISCLAIMER_MARKER in value.lower(), (
                f"{path}: {case.code}.{field_path} contains collision-marker text "
                f"with no {DISCLAIMER_MARKER!r} disclaimer in the same field — looks "
                "like the old-codebook licensing is being ASSERTED as this code's own "
                "requirement again, not disclaimed as the collision it is. Field "
                "value: " + value[:200]
            )


@pytest.mark.parametrize("case", FALSE_FRIEND_REGISTRY, ids=_CASE_IDS)
def test_innocent_controls_untouched(case: FalseFriendCase):
    """Innocenza guard: sibling codes that legitimately carry the SAME banned
    markers in their OWN per_skala (a real, correct match — not a collision)
    must be untouched by this fix. Scoped per-case: this fix only ever touches
    `case.code`, never these controls."""
    data = json.loads(
        (REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8")
    )
    by_code = {r["kode_kbli_2025"]: r for r in data["data"]}
    for code in case.innocent_controls:
        rec = by_code.get(code)
        if rec is None:
            continue
        blob = json.dumps(rec.get("per_skala") or [], ensure_ascii=False)
        assert any(m in blob for m in case.banned_markers), (
            f"{code} unexpectedly lost its legitimate marker text in per_skala — "
            f"this guard is scoped to {case.code} only, do not touch this record."
        )


# --- Third contaminated surface (68112 only): apps/mouth/data/kbli-gold-all.json ---
#
# This gold file is a SEPARATE curated dataset (428 records, keyed directly by code —
# not the `{"data": [...]}` list shape above) consumed by
# apps/mouth/src/lib/kbli-data.server.ts. It is NOT one of the copies
# scripts/sync_kbli_dataset.sh propagates, so PR #2508's per_skala fix never reached
# it. 51103/51203 are NOT gold records (verified 2026-07-16) — no gold treatment
# needed for them, hence _GOLD_CASES below is a filter, not the full registry.

_GOLD_CASES = [c for c in FALSE_FRIEND_REGISTRY if c.gold_present]


def _load_gold_record(code: str) -> dict:
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rec = data.get(code)
    if rec is None:
        raise AssertionError(f"{GOLD_PATH}: record {code} not found")
    return rec


@pytest.mark.parametrize("case", _GOLD_CASES, ids=[c.code for c in _GOLD_CASES])
def test_gold_what_you_need_has_no_medium_low_risk(case: FalseFriendCase):
    """Regression pin for the gold-specific bug: whatYouNeed (the customer-facing
    step list) must never again assert the collision-derived "Medium-Low risk"
    tier as this code's own requirement — not even in disclaimer form. Stricter
    bar than the whole-record guard below: whatYouNeed should describe "not yet
    defined" plainly, not repeat the specific wrong risk-tier label."""
    rec = _load_gold_record(case.code)
    wyn = rec.get("whatYouNeed", "")
    assert "Medium-Low risk" not in wyn, (
        f"{GOLD_PATH}: {case.code}.whatYouNeed still asserts 'Medium-Low risk' — "
        "the collision-derived licensing tier has leaked back into the "
        "customer-facing step list."
    )


@pytest.mark.parametrize("case", _GOLD_CASES, ids=[c.code for c in _GOLD_CASES])
def test_gold_record_has_no_collision_markers_without_disclaimer(case: FalseFriendCase):
    """Whole-gold-record guard, same discipline as
    test_record_has_no_collision_markers_outside_audit_key above: the gold record
    has no `per_skala_disputed_*`-style audit key to exclude (gold never carried
    the raw per_skala block), so every leaf string is in scope."""
    rec = _load_gold_record(case.code)
    for field_path, value in _iter_leaf_strings(rec):
        if any(marker in value for marker in case.banned_markers):
            assert DISCLAIMER_MARKER in value.lower(), (
                f"{GOLD_PATH}: {case.code}.{field_path} contains collision-marker "
                f"text with no {DISCLAIMER_MARKER!r} disclaimer in the same field. "
                "Field value: " + value[:200]
            )


def test_gold_68112_bali_context_untouched_and_innocent():
    """Innocence case (scar-family #3 guilt+innocence discipline): baliContext's
    mention of "Standard Certificate for Hospitality (SLHS)" is a LEGITIMATE
    reference (explaining that daily/Airbnb rentals need a different KBLI + SLHS,
    not this code) — it must survive this fix untouched, and the whole-record
    guard above must not have needed to touch it, because it never names
    "MICE"/"Venue" in the first place."""
    rec = _load_gold_record("68112")
    bali_context = rec.get("baliContext", "")
    assert "SLHS" in bali_context and "Standard Certificate for Hospitality" in bali_context, (
        "baliContext's legitimate SLHS/hospitality explanation must be preserved verbatim."
    )
    assert not any(marker in bali_context for marker in ("MICE", "Venue")), (
        "baliContext should not mention MICE/Venue at all — if it does now, the "
        "disclaimer-aware guard above, not a bare-substring ban, is what must clear it."
    )
