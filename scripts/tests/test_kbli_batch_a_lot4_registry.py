"""Regression registry — GARUDA-FILIERA Batch A Lot 4 false-friend per_skala
collisions + one wrong-parent metadata provenance note (13 codes, divisions
64->66, 2026-07-19), driven by scripts/kbli_filiera/cure_specs/batch_a_lot4.json
and applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
batch_a_lot4.json.

Modeled closely on test_kbli_batch_a_lot3_registry.py (Lot 3 registry,
2026-07-19) — the ALL_DATASET_COPIES list and the _existing_dataset_copies /
_load_by_code / _load_record / _contains_word_or_phrase helpers below are
COPIED VERBATIM from that file (comment marks the origin instead of
importing, to keep this file self-contained and independently readable as
its own regression pin, same convention Lot 1/2/3 used).

Cure pattern for the 13 detach-only codes (identical to Lot 1/2/3, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other
     field left untouched

UNLIKE Lot 3 (which corrected status_mapping/whatChanged on 3 of its 13
codes), NONE of Lot 4's 13 codes get a status_mapping_correction or
whatChanged_correction: 64955's true parent (64999) is image-verified (same
BPS Lampiran 10 page already read at the Lot 3 gate for 64940) but the
relationship SHAPE stays 1:1 (CODICE_RINUMERATO) even once the cited NUMBER
is understood to be wrong -- the same rule that withheld a correction from
Lot 3's 64940 (defect is the cited number, not the shape; the compiler has
no field to fix the number without inventing one). 64996/64997 have no
independently-verified replacement parent at all (rule #9). The 8
payload_cross_contamination codes (66116, 66123, 66124, 66129, 66131, 66132,
66149, 66159) and the 2 code_collision codes (66113, 66153) have their
crosswalk metadata (status_mapping/pp28_sources) left UNDISPUTED by this
cure -- the defect adjudicated is the served per_skala payload / the
self-citation reliability, never an alternate crosswalk narrative. pp28_sources
is NOT touched on any of the 13 codes, including 64955 (the corrected/true
ancestor, 64999, is recorded as provenance inside _data_note only, per the
Lot 1/2/3 detach convention: this compiler never authors new source values).

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 4
cure is applied to the canonical dataset (this file lands ahead of / together
with the data PR that runs cure_canonical_collisions.py --apply). The whole
module is skipped via a module-level pytestmark until the canonical 64955
record shows the post-cure shape (per_skala == [] and intel_2026.whatYouNeed
matches the spec's honest-gap text) -- at that point the module arms itself
automatically, no edit needed. 64955 is used as the canary (same convention as
Lot 3's 64940 canary) -- it is the flagship, image-verified wrong-parent
finding of this lot, corroborated this session against the 2025-dataset's own
64999 record, and the whatYouNeed check alone is a strong, spec-verbatim gate.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor code, and every content marker is a multi-word phrase verified (by
direct read of the spec JSON in this session) to actually appear verbatim in
that code's _data_note -- never a bare substring.

ADJUDICATION HISTORY (2026-07-19): conductor D6 gate on lane run
wf_66ea406e-b0d (v2 registry, v2 runner, same infra as Lot 1/2/3), SIGNED --
second signing, post TWO codex-sol-xhigh adversarial passes (pass 1 red-team:
FIX-FIRST -- m1 semantics inverted + controls downgraded to anchored
non-blind fixtures + m4 computed + title-similarity re-worded; pass 2 verify:
FIX-FIRST -- payload census undercount corrected to all-ten-66xxx + wording
fixes -- all cured in this second signing). Outcome: 13/13 in-scope
QUARANTINE, 0 certified; 2/2 innocence controls (59140, 59201, reused
deliberately from Lot 3) recorded as ANCHORED NON-BLIND REGRESSION FIXTURES
(the runner's innocence-control prompt announced the expected verdict and
asserted a false "no pp28_sources" claim -- runner defect FILED and cured in
this same PR's second deliverable, infra/workflows/kbli-batch-a-lot.js).
Categories: mapping_metadata_false (3: 64955, 64996, 64997) --
payload_cross_contamination (8: 66116, 66123, 66124, 66129, 66131, 66132,
66149, 66159) -- code_collision (2: 66113, 66153, FIRST SIGHTING of this
category in Batch A). Full report: research/operations/2026-07-19-kbli-
batch-a-lot4-conductor-gate.md (read from the sibling conductor worktree
.worktrees/kbli-pilota-a1-0718/ in this session -- that PR had not yet merged
when this cure was authored, same chain-of-custody pattern Lot 2/3 used for
their own not-yet-merged gate reports).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT4_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot4.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot3_registry.py (2026-07-19) ---------

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
    false-positive inside a longer word (e.g. bare 'SPA' inside 'aerospace').
    A multi-word phrase (contains a space) is matched as a plain substring --
    the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot4_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT4_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 64955 record shows the post-cure shape
    (per_skala == [] AND intel_2026.whatYouNeed matches the spec's
    honest-gap text verbatim). Pre-apply, per_skala is non-empty and
    whatYouNeed is the stale PMA-moratorium narrative; post-apply, per_skala
    == [] and whatYouNeed is the honest-gap text. If the canonical file, the
    spec, or the 64955 record is missing entirely, treat the cure as NOT
    applied (module stays skipped rather than erroring at collection
    time)."""
    if not CANONICAL_PATH.exists() or not LOT4_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "64955")
        spec_by_code = _load_lot4_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("64955", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot4 cure not yet applied — tests arm after the data PR",
)


LOT4_CODES = [
    "64955", "64996", "64997", "66113", "66116", "66123", "66124", "66129",
    "66131", "66132", "66149", "66153", "66159",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — must survive the cure untouched (including
# on 64955, whose TRUE parent 64999 is image-verified but never injected).
LOT4_PP28_SOURCES = {
    "64955": ["64992"],
    "64996": ["64921"],
    "64997": ["64922"],
    "66113": ["66113"],
    "66116": ["66116"],
    "66123": ["66123"],
    "66124": ["66124"],
    "66129": ["66152"],
    "66131": ["66131"],
    "66132": ["66132"],
    "66149": ["66149"],
    "66153": ["66153"],
    "66159": ["66159"],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — NONE of Lot 4's 13 codes get a metadata
# correction in this lot (unlike Lot 3, which corrected 3 of its 13).
LOT4_PRE_CURE_STATUS_MAPPING = {
    "64955": "CODICE_RINUMERATO",
    "64996": "CODICE_RINUMERATO",
    "64997": "CODICE_RINUMERATO",
    "66113": "MATCH_LANGSUNG",
    "66116": "MATCH_LANGSUNG",
    "66123": "MATCH_LANGSUNG",
    "66124": "MATCH_LANGSUNG",
    "66129": "CODICE_RINUMERATO",
    "66131": "MATCH_LANGSUNG",
    "66132": "MATCH_LANGSUNG",
    "66149": "MATCH_LANGSUNG",
    "66153": "MATCH_LANGSUNG",
    "66159": "MATCH_LANGSUNG",
}

# The 8 codes whose defect is the served per_skala payload (identical
# cooperative-rating contamination), plus the 2 code_collision codes which
# ALSO carry that same identical contaminated payload (gate report §2,
# verify-pass MAJOR correction) — all 10 share byte-identical disputed-block
# content once detached.
LOT4_COOPERATIVE_PAYLOAD_CODES = [
    "66113", "66116", "66123", "66124", "66129", "66131", "66132", "66149",
    "66153", "66159",
]

# Content markers: multi-word phrases verified (direct read of
# cure_specs/batch_a_lot4.json, 2026-07-19) to be verbatim substrings of that
# code's _data_note. Checked ONLY against _data_note.
LOT4_DATA_NOTE_MARKERS = {
    "64955": "the TRUE parent is 64999-2020",
    "64996": "no conceptual overlap with conventional BULLION BANKING",
    "64997": "no conceptual overlap with sharia BULLION BANKING",
    "66113": "FIRST SIGHTING of this category in Batch A",
    "66116": "licensing regime for agencies that RATE COOPERATIVES",
    "66123": "SAME cooperative-rating licensing regime documented for 66116 above",
    "66124": "SAME cooperative-rating licensing regime documented for 66116/66123 above",
    "66129": "distinct crosswalk citation from the other 7 payload_cross_contamination codes",
    "66131": "SAME cooperative-rating licensing regime documented above for the other codes",
    "66132": "SAME cooperative-rating licensing regime documented above for the other codes",
    "66149": "the ONE true D1-clean-vs-D5-problem divergence case in this lot",
    "66153": "the same disease class as 66113 above",
    "66159": "SAME cooperative-rating licensing regime documented above for the other codes",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# untouched by this cure.
#   64951 — division-64 neighbor (conventional infrastructure financing), unrelated
#   64994 — division-64 neighbor EXPLICITLY cross-referenced by 64996/64997's own
#            uraian text ("aktivitas perdagangan bulion atas nama sendiri, lihat
#            kelompok 64994") — a legitimate sibling, not part of this cure
#   66111 — division-66 neighbor (securities exchange operation), close in shape
#            to 66113 (digital asset exchange) but untouched
#   66112 — division-66 neighbor (futures exchange), close in shape to 66113/66131
#            cluster but untouched
#   66121 — division-66 neighbor (securities brokerage excl. carbon units), close
#            to the 66123/66124/66129 brokerage cluster but untouched
#   59140 — Lot 3/4 gate reports' OWN reused innocence control (film screening)
#   59201 — Lot 3/4 gate reports' OWN reused innocence control (sound recording)
INNOCENT_NEIGHBORS = ["64951", "64994", "66111", "66112", "66121", "59140", "59201"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT4_CODES)
def test_lot4_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present
    with a non-empty preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-4 false-friend "
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

@pytest.mark.parametrize("code", LOT4_CODES)
def test_lot4_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the
    provenance note (rule #9 no-new-values-without-provenance)."""
    spec_by_code = _load_lot4_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "batch_a_lot4.json — the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT4_CODES)
def test_lot4_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text
    VERBATIM — replacing the stale client-facing prose derived from the
    detached (contaminated) per_skala rows."""
    spec_by_code = _load_lot4_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim — the compiler must copy whatYouNeed verbatim, never "
        "paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including 64955 whose true parent is
#    image-verified but never injected)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT4_CODES)
def test_lot4_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged
    — even for 64955, whose true parent (64999) is image-verified: the
    compiler never authors new source values (Lot 1/2/3 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT4_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT4_PP28_SOURCES[code]!r} — must be preserved untouched (rule: "
        "KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. NO metadata corrections in this lot — status_mapping must survive
#    untouched on ALL 13 codes (unlike Lot 3, which corrected 3 of its 13)
# ---------------------------------------------------------------------------

def test_lot4_no_code_gets_a_status_mapping_correction():
    """UNLIKE Lot 3: none of Lot 4's 13 codes have an independently-verified
    SHAPE change (split/merge) established in the gate report — 64955's true
    parent is found but the relationship stays 1:1 (same rule as Lot 3's
    64940); the other 12 have no established replacement at all. Every
    status_mapping must therefore match its pre-cure value exactly."""
    for code, expected in LOT4_PRE_CURE_STATUS_MAPPING.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} "
            f"— expected untouched pre-cure value {expected!r} (this lot is "
            "detach-only, no metadata correction on any of its 13 codes)."
        )


def test_lot4_spec_never_declares_a_status_mapping_correction():
    """Guard against the spec itself silently growing a correction key that
    the compiler would then apply — Lot 4's adjudication (unlike Lot 3's)
    established no independently-verified shape change for any of its 13
    codes (rule #9)."""
    spec_by_code = _load_lot4_spec_by_code()
    for code in LOT4_CODES:
        entry = spec_by_code[code]
        assert "status_mapping_correction" not in entry, (
            f"{code}: spec unexpectedly declares status_mapping_correction "
            f"{entry.get('status_mapping_correction')!r} — Lot 4 has no "
            "independently-verified shape change for any code (rule #9)."
        )
        assert "whatChanged_correction" not in entry, (
            f"{code}: spec unexpectedly declares whatChanged_correction "
            f"{entry.get('whatChanged_correction')!r}"
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code
#    already-cured (no-op).
# ---------------------------------------------------------------------------

def test_lot4_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT4_SPEC_PATH),
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
    for code in LOT4_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be
#    untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot4_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the gate reports' own
    pre-verified innocence controls) and are NOT part of this cure — if the
    cure ever over-reaches onto one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 13 Lot-4 codes; the cure must not have "
        "touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot4 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only (never invented
#    inside the disputed blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT4_CODES)
def test_lot4_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT4_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 9. Cooperative-rating payload signature — the preserved disputed block for
#    ALL TEN 66xxx codes (the 8 payload_cross_contamination codes PLUS the 2
#    code_collision codes, 66113/66153 — gate report §2 verify-pass MAJOR
#    correction) must still show the cooperative-rating contamination
#    signature this cure detached them for (verified by direct read of the
#    canonical payload in this session).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT4_COOPERATIVE_PAYLOAD_CODES)
def test_lot4_66xxx_disputed_block_shows_cooperative_rating_signature(code: str):
    marker = "pemeringkatan koperasi"
    rec = _load_record(CANONICAL_PATH, code)
    disputed = rec.get(DISPUTED_KEY)
    blob = json.dumps(disputed, ensure_ascii=False)
    assert marker in blob, (
        f"{code}: preserved disputed block no longer carries the "
        f"cooperative-rating contamination signature {marker!r} — audit "
        "trail may have drifted."
    )


def test_lot4_all_ten_66xxx_share_byte_identical_disputed_payload():
    """The gate report's verify-pass MAJOR correction (§2) established that
    ALL TEN in-scope 66xxx records — not just the 8 final-category
    payload_cross_contamination codes — carry the IDENTICAL cooperative-
    rating kewajiban payload, including the 2 code_collision codes (66113,
    66153). This must survive the cure exactly as found: the preserved
    disputed blocks for all ten must be byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT4_COOPERATIVE_PAYLOAD_CODES
    }
    reference_code = LOT4_COOPERATIVE_PAYLOAD_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — "
            "the gate report's finding that all ten 66xxx codes carry a "
            "byte-identical contaminated payload should be preserved by the cure "
            "(both are audit-only preserved blocks, never mutated)."
        )


# ---------------------------------------------------------------------------
# 10. 64955 true-parent provenance — corroborated this session against the
#     CURRENT KBLI-2025 dataset's own 64999 record (whose judul is verbatim
#     identical to the 2020 title the gate report reads off the image).
# ---------------------------------------------------------------------------

def test_lot4_64955_true_parent_corroborated_against_64999_record():
    rec_64955 = _load_record(CANONICAL_PATH, "64955")
    rec_64999 = _load_record(CANONICAL_PATH, "64999")
    assert "64999" in rec_64955.get("_data_note", ""), (
        "64955: _data_note must name the true parent 64999 as provenance"
    )
    assert rec_64999.get("judul") == "Aktivitas Jasa Keuangan Lainnya YTDL, Bukan Asuransi dan Dana Pensiun", (
        "64999: judul drifted from the value this cure's provenance note "
        "corroborates against — re-verify the 64955 data_note's cross-check "
        "if this ever changes"
    )
