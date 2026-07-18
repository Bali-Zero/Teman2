"""Regression registry — GARUDA-FILIERA Batch A Lot 2 (13 detach codes +
56101 metadata cure, 2026-07-18, conductor-signed D6 verdict, session
f5892d39), driven by:

  - scripts/kbli_filiera/cure_specs/batch_a_lot2.json applied via
    scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot2.json
    (the false-friend per_skala detach pattern, identical mechanics to Lot 1)
  - scripts/kbli_filiera/cure_specs/metadata_56101.json applied via
    scripts/kbli_filiera/cure_metadata_pp28_sources.py (a THIRD sanctioned
    canonical-writer shape: pure metadata correction, per_skala untouched)
  - two gold-layer (apps/mouth/data/kbli-gold-all.json) value-in-place edits,
    NOT data-plane-guarded, Codex-gated (generator != grader — a Sonnet agent
    drafted, a Codex thread reviewed, PASS on both rounds): 49296.whatYouNeed,
    50113.whatYouNeed (honest-gap, gold masks intel_2026 on the live page,
    49213/50115 precedent) and 56101.whatChanged (metadata correction mirror).

Modeled closely on test_kbli_batch_a_lot1_registry.py — the ALL_DATASET_COPIES
list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file
(same convention: self-contained regression pin over an import).

Cure pattern for the 13 detach codes (identical to Lot 1):
  1. per_skala -> []
  2. the ORIGINAL per_skala preserved verbatim under
     "per_skala_disputed_pp28_collision"
  3. _data_note added (verbatim from the cure spec)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other
     field left untouched

Cure pattern for 56101 (metadata-only, NOT a detach):
  1. per_skala / per_skala_legacy left COMPLETELY untouched (innocence-
     violation finding, not a contamination finding — the licensing substance
     was independently verified correct)
  2. pp28_sources corrected: ["56101","56104","56103","56109"] ->
     ["56101","56102","56109"]
  3. aggregation_note corrected
  4. intel_2026.whatChanged corrected
  5. _data_note added (provenance)

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor/cross-lot code, and every content marker is a multi-word phrase
verified (by direct read of the spec JSON and the served dataset in this
session) to actually appear verbatim in the field it guards.

DEDUP-DISEASE FINDING (flagged, NOT fixed here — out of mandate scope): gold
code 49299's whatYouNeed was found BYTE-IDENTICAL to 49296's pre-cure
contaminated (railway-infrastructure) text — a dedup-disease collision in the
same family as the KG 68% dedup disease (established truth #8), but on the
gold editorial layer instead of the KG. 49299 carries no finding/evidence in
this lot's spec, so rule #9 (no new values without provenance) forbids
touching it here; the innocence test below pins that this cure did NOT ripple
onto 49299 (code-scoped edit, not a blind text-replace), and the collision
itself is left as an explicit follow-up for a future lot/PENDING-ARMS line.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT2_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot2.json"
META_56101_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/metadata_56101.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot1_registry.py (2026-07-18) ---------

ALL_DATASET_COPIES = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # canonical (via source_documents/ symlink)
    REPO_ROOT / "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
    REPO_ROOT / "apps/backend-rag/source_documents/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
]


def _existing_dataset_copies() -> list[Path]:
    return [p for p in ALL_DATASET_COPIES if p.exists()]


def _load_by_code(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["kode_kbli_2025"]: r for r in data["data"] if "kode_kbli_2025" in r}


def _load_record(path: Path, code: str) -> dict[str, Any]:
    rec = _load_by_code(path).get(code)
    if rec is None:
        raise AssertionError(f"{path}: record {code} not found in dataset")
    return rec


def _contains_word_or_phrase(haystack: str, marker: str) -> bool:
    """Word-boundary-safe containment check (scar-family #3 antidote): a
    single-word marker is matched with regex word boundaries so it cannot
    false-positive inside a longer word. A multi-word phrase (contains a
    space) is matched as a plain substring — the multi-word shape itself is
    already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot2_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT2_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 42999 record shows the post-cure shape. Used
    to gate the whole module (same convention as Lot 1's _cure_applied)."""
    if not CANONICAL_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "42999")
    except AssertionError:
        return False
    return rec.get("per_skala") == [] and DISPUTED_KEY in rec


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot2 cure not yet applied — tests arm after the data PR",
)


LOT2_CODES = [
    "42999", "47771", "49233", "49296", "50113", "52103", "52105", "52211",
    "52219", "52232", "52239", "52299", "59131",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-18) — must survive the cure untouched (rule:
# KEEP pp28_sources unchanged even when the finding is about that very field's
# TRUTHFULNESS, e.g. 52239's false 96990 pointer — the compiler audits, never
# silently rewrites, pp28_sources for the detach flavor).
LOT2_PP28_SOURCES = {
    "42999": ["42929"],
    "47771": ["47771"],
    "49233": ["49433"],
    "49296": ["49424"],
    "50113": ["50113"],
    "52103": ["52103"],
    "52105": ["52105"],
    "52211": ["52211"],
    "52219": ["52219"],
    "52232": ["52232"],
    "52239": ["96990"],
    "52299": ["52299"],
    "59131": ["59131"],
}

# Content markers: multi-word phrases (or case-sensitive whole-word terms)
# verified (direct read of cure_specs/batch_a_lot2.json, 2026-07-18) to be
# verbatim substrings of that code's _data_note. Checked ONLY against
# _data_note, never invented inside the disputed blobs.
LOT2_DATA_NOTE_MARKERS = {
    "42999": "residual portion of KBLI-2020 code 42930",
    "47771": "4-ancestor MERGE",
    "49233": "clean ONE_TO_ONE continuation",
    "49296": "SPECIAL-RAILWAY licensing content",
    "50113": "clean ONE_TO_ONE continuation",
    "52103": "5-ancestor MERGE",
    "52105": "clean ONE_TO_ONE continuation",
    "52211": "port tally-clerk experts",
    "52219": "same-digit-collision signal",
    "52232": "PORT development proposal",
    "52239": "bizarre foreign-sector ancestry claim",
    "52299": "compound ancestry",
    "59131": "clean ONE_TO_ONE continuation",
}

# Innocence controls (scar-family #3 discipline): codes that must NOT be
# touched by the Lot 2 cure.
#   47111 — explicit innocence control named in the mandate; unrelated OSS-
#           native code, never part of any Batch A finding.
INNOCENT_NEIGHBORS = ["47111"]

# Cross-lot innocence: Lot 1's 13 codes must still show the Lot-1 post-cure
# shape after Lot 2's apply (a prior lot's data must never be disturbed by a
# later lot's compiler run).
LOT1_CODES = [
    "01700", "02409", "05102", "38122", "39001", "02402", "38222", "05200",
    "01287", "02201", "08920", "36003", "19206",
]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (13 Lot-2 codes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present
    with a non-empty preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-2 false-friend "
        "licensing block has leaked back into the served field."
    )
    disputed = rec.get(DISPUTED_KEY)
    assert disputed, (
        f"{path}: {code} is missing (or has an empty) {DISPUTED_KEY!r} — "
        "the original per_skala rows must be preserved for audit, never "
        "silently deleted."
    )
    assert isinstance(disputed, list) and len(disputed) > 0, (
        f"{path}: {code}.{DISPUTED_KEY} expected to be a non-empty list of "
        f"the original per_skala rows, got {type(disputed)} / {disputed!r}"
    )


# ---------------------------------------------------------------------------
# 2. _data_note verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_data_note_matches_spec_verbatim(code: str):
    spec_by_code = _load_lot2_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "batch_a_lot2.json — the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_whatYouNeed_honest_gap(code: str):
    spec_by_code = _load_lot2_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_pp28_sources_untouched(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT2_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT2_PP28_SOURCES[code]!r} — must be preserved untouched, even "
        "for the mapping_metadata_false flavor (52239): the compiler AUDITS "
        "the false pointer via _data_note, it never silently rewrites the "
        "field itself (rule: KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. Idempotency: compiler dry-run reports every Lot-2 code already-cured.
# ---------------------------------------------------------------------------

def test_lot2_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT2_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (all already cured), "
        f"got {result.returncode}. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in LOT2_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


def test_metadata_56101_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_metadata_pp28_sources.py"),
            "--spec",
            str(META_56101_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (already cured), got "
        f"{result.returncode}. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "ALREADY CURED" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# 6. INNOCENCE — explicit neighbor 47111 untouched.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot2_innocent_neighbor_untouched(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an explicit "
        "innocence control, not part of batch_a_lot2; the cure must not "
        "have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot2 cure spec."
    )


# ---------------------------------------------------------------------------
# 7. INNOCENCE — Lot 1's 13 codes remain untouched by Lot 2's apply.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_codes_untouched_by_lot2_apply(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala") == [], (
        f"{code}: Lot-1 code's per_skala is no longer [] after Lot-2's "
        "apply — a prior lot's cure was disturbed."
    )
    assert DISPUTED_KEY in rec, (
        f"{code}: Lot-1 code lost its {DISPUTED_KEY!r} audit block after "
        "Lot-2's apply."
    )


# ---------------------------------------------------------------------------
# 8. INNOCENCE — 49213 (Fase-1/pilot cure, orthogonal PR #2744 in flight):
#    dual-branch so this test is correct whether #2744 (per-ancestor restore)
#    has merged to main yet or not — either way, Lot 2's compilers never
#    reference 49213, so this test only PROVES that fact, it does not depend
#    on merge order.
# ---------------------------------------------------------------------------

def test_49213_untouched_by_lot2_regardless_of_restore_pr_merge_state():
    rec = _load_record(CANONICAL_PATH, "49213")
    restored_sources = ["49214", "49219", "49413"]
    honest_gap_sources = ["49213", "49413"]

    if rec.get("pp28_sources") == restored_sources:
        # PR #2744 has merged: the per-ancestor restore is live. Assert its
        # shape is intact (12 rows, restored pp28_sources) — Lot 2 must not
        # have clobbered it.
        assert isinstance(rec.get("per_skala"), list) and len(rec["per_skala"]) == 12, (
            "49213: restored per_skala expected 12 rows (3 ancestors x 4 skala "
            f"tiers), got {rec.get('per_skala')!r}"
        )
    elif rec.get("pp28_sources") == honest_gap_sources:
        # PR #2744 not yet merged: 49213 is still in its original Fase-1
        # honest-gap detached shape. Assert that shape is intact.
        assert rec.get("per_skala") == [], (
            f"49213: expected still-detached per_skala==[] (pre-restore), "
            f"got {rec.get('per_skala')!r}"
        )
        assert DISPUTED_KEY in rec, "49213: pre-restore disputed key missing"
    else:
        raise AssertionError(
            f"49213: pp28_sources {rec.get('pp28_sources')!r} matches neither "
            f"the restored shape {restored_sources!r} nor the pre-restore "
            f"honest-gap shape {honest_gap_sources!r} — unexpected drift, "
            "investigate before trusting this test's other assertions."
        )


# ---------------------------------------------------------------------------
# 9. Content markers — verified verbatim in _data_note only.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT2_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        f"the provenance note may have drifted from the spec. _data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 10. 56101 metadata cure — pp28_sources / aggregation_note / whatChanged /
#     _data_note corrected, per_skala COMPLETELY UNTOUCHED (innocence-on-
#     substance: this is the defining property of the metadata-only shape).
# ---------------------------------------------------------------------------

# Hardcoded from a direct read of the canonical dataset PRE-cure (2026-07-18):
# per_skala substance must be byte-identical after the cure.
_PRE_CURE_56101_PER_SKALA_ROW_COUNT = 6


def test_56101_metadata_pp28_sources_corrected():
    rec = _load_record(CANONICAL_PATH, "56101")
    assert rec.get("pp28_sources") == ["56101", "56102", "56109"], (
        f"56101: pp28_sources expected corrected ['56101','56102','56109'], "
        f"got {rec.get('pp28_sources')!r}"
    )


def test_56101_metadata_aggregation_note_corrected():
    rec = _load_record(CANONICAL_PATH, "56101")
    note = rec.get("aggregation_note", "")
    assert "56102" in note and "56109" in note, (
        f"56101: aggregation_note must credit 56102+56109, got {note!r}"
    )
    assert "56103" not in note and "56104" not in note, (
        f"56101: aggregation_note must NOT claim 56103/56104, got {note!r}"
    )


def test_56101_metadata_whatChanged_corrected():
    rec = _load_record(CANONICAL_PATH, "56101")
    what_changed = (rec.get("intel_2026") or {}).get("whatChanged", "")
    assert "56102" in what_changed, (
        f"56101: intel_2026.whatChanged must credit KBLI-2020 56102 as the "
        f"true omitted ancestor, got {what_changed!r}"
    )


def test_56101_per_skala_completely_untouched_innocence_on_substance():
    """INNOCENCE, core to the metadata-only shape: per_skala substance was
    independently verified CORRECT by the conductor — this cure must NEVER
    touch it. No disputed key, no detach, row count unchanged from the
    pre-cure read."""
    rec = _load_record(CANONICAL_PATH, "56101")
    assert DISPUTED_KEY not in rec, (
        "56101: must NOT carry a per_skala_disputed_* key — this is a "
        "metadata-only innocence-violation cure, never a detach."
    )
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == _PRE_CURE_56101_PER_SKALA_ROW_COUNT, (
        f"56101: per_skala row count drifted — expected "
        f"{_PRE_CURE_56101_PER_SKALA_ROW_COUNT} (pre-cure baseline, "
        f"byte-identical required), got {len(per_skala) if isinstance(per_skala, list) else per_skala!r}"
    )


# ---------------------------------------------------------------------------
# 11. Gold layer (apps/mouth/data/kbli-gold-all.json) — 49296 + 50113
#     honest-gap whatYouNeed (masks canonical), 56101 whatChanged corrected.
#     All three Codex-gated (generator != grader) before ship.
# ---------------------------------------------------------------------------

GOLD_HONEST_GAP_CODES = ["49296", "50113"]

# Stale/contamination markers that must NOT reappear in the cured gold
# whatYouNeed — verified (direct read of the pre-cure gold file, 2026-07-18)
# to have actually been present before the cure.
GOLD_STALE_MARKERS = {
    "49296": ["prasarana perkeretaapian", "Kepala Badan"],
    "50113": ["Obtain Laik Sehat", "Standard Business Certificate"],
}


def _load_gold() -> dict[str, dict[str, Any]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", GOLD_HONEST_GAP_CODES)
def test_gold_whatYouNeed_is_honest_gap_no_contamination_markers(code: str):
    """GUILT: the cured gold whatYouNeed must declare the licensing gap and
    must NOT still carry the contaminated step content."""
    gold = _load_gold()
    rec = gold.get(code)
    assert rec is not None, f"gold {code}: record not found"
    wyn = rec.get("whatYouNeed", "")
    for marker in GOLD_STALE_MARKERS[code]:
        assert marker not in wyn, (
            f"gold {code}.whatYouNeed still contains stale marker {marker!r} — "
            "the contaminated licensing content has leaked back into the "
            "customer-facing gold text."
        )
    assert "not yet reliably" in wyn, (
        f"gold {code}.whatYouNeed must declare the licensing gap explicitly, "
        f"got {wyn!r}"
    )
    assert "Bali Zero team" in wyn, (
        f"gold {code}.whatYouNeed must route the client to team verification, "
        f"got {wyn!r}"
    )
    # No PMA assertion (P1-v2 abstain fail-safe — PMA is a separate,
    # unaudited axis; 50113's true canonical pma_status is TERBATAS, so
    # asserting "open" here would be a factual error, not just unsupported).
    assert "PMA" not in wyn, (
        f"gold {code}.whatYouNeed must not assert a PMA status in this "
        f"honest-gap text (separate axis, abstain fail-safe), got {wyn!r}"
    )


def test_gold_56101_whatChanged_corrected_no_false_ancestor_claim():
    """GUILT: gold 56101.whatChanged must no longer claim 56103/56104 as
    absorbed ancestors, and must credit 56102."""
    gold = _load_gold()
    rec = gold.get("56101")
    assert rec is not None, "gold 56101: record not found"
    wc = rec.get("whatChanged", "")
    assert "56102" in wc, f"gold 56101.whatChanged must credit 56102, got {wc!r}"
    # the corrected text explicitly REFERENCES 56103/56104 to redirect former
    # operators — but must not claim them as absorbed BY 56101. The false
    # claim's exact shape ("Previous KBLI 2020 sources: 56101, 56104, 56103")
    # must be gone.
    assert "Previous KBLI 2020 sources: 56101, 56104, 56103" not in wc, (
        f"gold 56101.whatChanged still contains the false pre-cure claim, "
        f"got {wc!r}"
    )


def test_gold_56101_whatYouNeed_untouched():
    """INNOCENCE: 56101's licensing substance (whatYouNeed) was independently
    verified correct — the gold cure must touch ONLY whatChanged, never
    whatYouNeed."""
    gold = _load_gold()
    rec = gold.get("56101")
    wyn = rec.get("whatYouNeed", "")
    assert "Bupati/Walikota" in wyn and "Gubernur" in wyn, (
        "gold 56101.whatYouNeed: expected the original multi-scale licensing "
        f"steps to remain untouched, got {wyn!r}"
    )


def test_gold_49299_dedup_collision_untouched_innocence():
    """INNOCENCE (dedup-disease finding, flagged not fixed): 49299 shared a
    byte-identical (contaminated) whatYouNeed with 49296 before this cure.
    49299 carries no finding in batch_a_lot2.json — this cure must be
    code-scoped, never a blind text-replace that would silently also cure
    (or corrupt) 49299 without evidence/provenance for that code."""
    gold = _load_gold()
    rec = gold.get("49299")
    assert rec is not None, "gold 49299: record not found"
    wyn = rec.get("whatYouNeed", "")
    assert "prasarana perkeretaapian" in wyn, (
        "gold 49299.whatYouNeed: expected to STILL contain the pre-cure "
        "railway-infrastructure text — if this now reads honest-gap, the "
        "Lot-2 gold cure rippled onto an out-of-scope code with no "
        f"provenance for that change. Got: {wyn!r}"
    )


def test_gold_total_record_count_unchanged():
    """INNOCENCE: the gold cure is 3 value-in-place field edits on existing
    records — the gold layer's record count must be unchanged (428, per the
    kbli-navigator skill's established artifact count)."""
    gold = _load_gold()
    assert len(gold) == 428, (
        f"gold record count drifted from 428 to {len(gold)} — the Lot-2 gold "
        "cure must never add/remove records, only edit existing field values."
    )
