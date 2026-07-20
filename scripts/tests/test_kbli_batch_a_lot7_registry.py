"""Regression registry — GARUDA-FILIERA Batch A Lot 7 false-friend per_skala collisions (13
codes, divisions 85->91, education/health/museums/heritage/nature-parks, 2026-07-19), driven by
scripts/kbli_filiera/cure_specs/batch_a_lot7.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot7.json.

Modeled closely on test_kbli_batch_a_lot6_registry.py (Lot 6 registry, 2026-07-19) — the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file (comment marks the
origin instead of importing, to keep this file self-contained and independently readable as its
own regression pin, same convention Lot 1-6 used).

Cure pattern for all 13 detach-only codes (identical to Lot 1-6, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet defined" gap
     instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other field left untouched

NONE of Lot 7's 13 codes get a status_mapping_correction, whatChanged_correction, or
pp28_sources_correction key in the spec (same discipline as Lot 1-6), and none uses
action=metadata_only: the true-parent findings corroborated this lot by direct render/cross-
record read (85330->85220, 85401->{51108,85311,85312}, 85404->{85332,85340},
91222->{91024,91029}) are recorded as _data_note provenance ONLY, never injected into
pp28_sources/kbli_2020_source/status_mapping (rule #9).

ADJUDICATION HISTORY (2026-07-19): conductor D6 gate on lane run wf_f557bfcc-249 (30 seats, 0
errors, 686s wall), SIGNED as a SECOND SIGNING after adversarial review (codex sol xhigh
read-only, 1 BLOCKER + 2 MAJOR + 3 MINOR, all cured — the BLOCKER corrected an over-eager
absolution of the 41013 innocence control). Final category census (6/4/1/1/1 = 13):
source_absent_in_vault (6: 85403, 85404, 86109, 86201, 86202, 86203) -- payload_cross_contamination
(4: 85330, 85401, 86102, 91212) -- code_collision (1: 90111) -- illegitimate_inheritance (1: 91222,
FIRST BATCH-A SIGHTING of this category) -- unresolvable_source_pointer (1: 91424). The lot's TWO
FRESH innocence controls (20232, 41013 -- the program's first fresh controls, neither reused) get
NO canonical write from this spec: 20232 joins the standalone metadata cure-list backlog (real
metadata falsity, OSS-native healthy per_skala, never detached per rule #9); 41013 stays
quarantined pending the certification-contract refinement #2 (shipped in the same PR as this
cure spec, #2831) being applied and the 41013 seats being re-run under it -- NOT executed by this
cure. Full report: research/operations/2026-07-19-kbli-batch-a-lot7-conductor-gate.md. This cure's
own PR (#2831) ALSO shipped the certification-contract refinement #2 (derived-fact rule) to
infra/workflows/kbli-batch-a-lot.js and journal provenance to the runner -- unrelated to the data
apply this registry pins, already merged to main.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout: every guilt
assertion is paired with an innocence assertion on a legitimate neighbor code, and every content
marker is a multi-word phrase verified (by direct read of the applied canonical record in this
session) to actually appear verbatim in that code's _data_note -- AND checked for non-collision
across the other 12 codes in this lot (several codes share near-identical boilerplate prose
differing only by the activity name or the "alongside X/Y/Z" sibling list, so markers were
picked/verified to disambiguate, never a bare substring risking a false match on a sibling).

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 7 cure is applied to
the canonical dataset (this file lands together with the data PR that runs
cure_canonical_collisions.py --apply). The whole module is skipped via a module-level pytestmark
until the canonical 91424 record shows the post-cure shape (per_skala == [] and
intel_2026.whatYouNeed matches the spec's honest-gap text) -- at that point the module arms
itself automatically, no edit needed. 91424 is used as the canary (same convention as Lot 3's
64940 / Lot 4's 64955 / Lot 5's 66192 / Lot 6's 80190 canaries) -- it is the lot's sole
unresolvable_source_pointer member and the last code in the spec's own list.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT7_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot7.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot6_registry.py (2026-07-19) ---------

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
    """Word-boundary-safe containment check (scar-family #3 antidote): a single-word marker is
    matched with regex word boundaries so it cannot false-positive inside a longer word (e.g.
    bare 'SPA' inside 'aerospace'). A multi-word phrase (contains a space) is matched as a plain
    substring -- the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot7_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT7_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 91424 record shows the post-cure shape (per_skala == [] AND
    intel_2026.whatYouNeed matches the spec's honest-gap text verbatim). Pre-apply, per_skala is
    non-empty; post-apply, per_skala == [] and whatYouNeed is the honest-gap text. If the
    canonical file, the spec, or the 91424 record is missing entirely, treat the cure as NOT
    applied (module stays skipped rather than erroring at collection time)."""
    if not CANONICAL_PATH.exists() or not LOT7_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "91424")
        spec_by_code = _load_lot7_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("91424", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot7 cure not yet applied — tests arm after the data PR",
)


LOT7_CODES = [
    "85403", "85404", "86109", "86201", "86202", "86203", "85330", "85401",
    "86102", "91212", "90111", "91222", "91424",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the canonical dataset
# (2026-07-19) — must survive the cure untouched (including on 85330/85401/85404/91222, whose
# TRUE parents are image/record-verified but never injected, and 90111, whose citation already
# happens to name the two codes the gate independently verified as the page's true content —
# citing them FOR 90111 is itself the collision this cure adjudicates, rule #9 still applies).
LOT7_PP28_SOURCES = {
    "85403": ["85331"],
    "85404": ["85332"],
    "86109": ["86109"],
    "86201": ["86201"],
    "86202": ["86202"],
    "86203": ["86203"],
    "85330": ["85499"],
    "85401": ["85497", "85496", "85499"],
    "86102": ["86102"],
    "91212": ["91012"],
    "90111": ["90011", "90021"],
    "91222": ["91022"],
    "91424": ["91024"],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the canonical dataset
# (2026-07-19) — NONE of Lot 7's 13 codes get a metadata correction in this lot (same discipline
# as Lot 1-6).
LOT7_PRE_CURE_STATUS_MAPPING = {
    "85403": "CODICE_RINUMERATO",
    "85404": "CODICE_RINUMERATO",
    "86109": "MATCH_LANGSUNG",
    "86201": "MATCH_LANGSUNG",
    "86202": "MATCH_LANGSUNG",
    "86203": "MATCH_LANGSUNG",
    "85330": "CODICE_RINUMERATO",
    "85401": "MATCH_CON_AGGREGAZIONE",
    "86102": "MATCH_LANGSUNG",
    "91212": "MATCH_LANGSUNG",
    "90111": "MATCH_CON_AGGREGAZIONE",
    "91222": "MATCH_LANGSUNG",
    "91424": "MATCH_LANGSUNG",
}

# Byte-identical disputed-payload pairs (verified this session, json-dump byte-comparison):
# 85403/85404 (government/private religious higher education share the same served licensing
# template); 86201/86102 and 86202/86203 (two pairs within the "whole practice-of-medicine
# block" share a generic "klinik" [clinic] licensing template — 86109 stands ALONE, its own
# disputed payload is NOT byte-identical to any of the other 4 health-facility codes).
LOT7_RELIGIOUS_HIGHER_ED_PAIR = ["85403", "85404"]
LOT7_KLINIK_PAIR_A = ["86201", "86102"]
LOT7_KLINIK_PAIR_B = ["86202", "86203"]

# Content markers: multi-word/distinctive phrases verified (direct read of the applied canonical
# dataset, 2026-07-19) to be verbatim substrings of that code's _data_note, AND verified to NOT
# collide with any of the other 12 codes' _data_note in this lot (guard-over-match discipline —
# several codes share near-identical boilerplate prose differing only by activity name or the
# "alongside X/Y/Z" sibling list). Checked ONLY against _data_note.
LOT7_DATA_NOTE_MARKERS = {
    "85403": "the licensing regime this code's citation (85331) would need to legitimately transfer",
    "85404": "vet-trio-incomplete-single-parent shape",
    "86109": "The lane's verdicts are consistent",
    "86201": "alongside 86102/86202/86203",
    "86202": "alongside 86102/86201/86203",
    "86203": "alongside 86102/86201/86202",
    "85330": "PAGINATION ROW-BLEED",
    "85401": "Bidang KETENAGALISTRIKAN",
    "86102": "alongside 86201/86202/86203",
    "91212": "Nomor Pokok Perpustakaan",
    "90111": "ISO-9001 boilerplate matcher trap",
    "91222": "FIRST BATCH-A SIGHTING of the illegitimate_inheritance category",
    "91424": "adjudicated this code as unresolvable_source_pointer",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes untouched by this
# cure, verified this session to carry non-empty per_skala and no disputed key.
#   85312, 85316, 85322 — secondary-education neighbors (junior/senior/vocational, private),
#           untouched (distinct division-85 family, not part of this lot's higher-ed/religious
#           cluster)
#   85402 — "Pendidikan Tinggi Umum Swasta" (private general higher education), the direct
#           private-sector sibling of THIS lot's 85401 (government general higher education) —
#           untouched, sharpest available guard against over-reach onto the general (non-
#           religious) higher-ed family
#   85530 — "Kegiatan Sekolah Mengemudi" (driving school), the code the gate report explicitly
#           names as the TRUE destination of 85330's own cited 2020 parent 85499 — untouched
#   86101, 86103, 86104, 86105 — hospital/clinic neighbors (government/private hospital,
#           government/private clinic) — untouched, distinct from the 5-member
#           source_absent/payload-contamination health cluster this lot cures
#   90112 — "Aktivitas Penciptaan Komposisi Musik" (music composition), the direct creative-arts
#           sibling of THIS lot's 90111 (literary creation) — untouched
#   91429 — "Aktivitas Cagar Alam Lainnya" (other nature reserve activities), the direct
#           division-91 sibling of THIS lot's 91424 (nature recreation park) — untouched
#   20232, 41013 — the lot's OWN two FRESH innocence controls (gate report, cosmetics
#           manufacturing / industrial-building construction) — DELIBERATELY absent from the
#           spec's codes[] array, get NO canonical write from this cure (per the module
#           docstring), untouched
INNOCENT_NEIGHBORS = [
    "85312", "85316", "85322", "85402", "85530",
    "86101", "86103", "86104", "86105",
    "90112", "91429", "20232", "41013",
]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present with a non-empty
    preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-7 false-friend licensing block has "
        "leaked back into the served field."
    )
    disputed = rec.get(DISPUTED_KEY)
    assert disputed, (
        f"{path}: {code} is missing (or has an empty) {DISPUTED_KEY!r} — the original per_skala "
        "rows must be preserved for audit, never silently deleted."
    )
    assert isinstance(disputed, list) and len(disputed) > 0, (
        f"{path}: {code}.{DISPUTED_KEY} expected to be a non-empty list of the original "
        f"per_skala rows, got {type(disputed)} / {disputed!r}"
    )


# ---------------------------------------------------------------------------
# 2. _data_note verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler never authors a
    replacement licensing value or paraphrases the provenance note (rule #9
    no-new-values-without-provenance)."""
    spec_by_code = _load_lot7_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/batch_a_lot7.json — "
        "the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text VERBATIM —
    replacing the stale client-facing prose derived from the detached (absent/contaminated/
    colliding/illegitimate/unresolvable) per_skala rows."""
    spec_by_code = _load_lot7_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap text verbatim — "
        "the compiler must copy whatYouNeed verbatim, never paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including the 4 codes whose true parents are verified but
#    never injected: 85330, 85401, 85404, 91222)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged — even for
    85330/85401/85404/91222, whose true parents are established this session, and 90111, whose
    citation already happens to name the two codes the gate independently verified as the page's
    true content (citing them FOR 90111 IS the collision): the compiler never authors new source
    values (Lot 1-6 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT7_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value {LOT7_PP28_SOURCES[code]!r} — "
        "must be preserved untouched (rule: KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. NO metadata corrections in this lot — status_mapping must survive untouched on ALL 13
#    codes (same discipline as Lot 1-6)
# ---------------------------------------------------------------------------

def test_lot7_no_code_gets_a_status_mapping_correction():
    """No code in this lot has an independently-verified SHAPE change (split/merge) established
    in the gate report that gets INJECTED into the canonical — the true-parent findings for
    85330/85401/85404/91222 are recorded as _data_note provenance only (same rule as Lot 3's
    64940, Lot 4's 64955, Lot 5's 68123/68126/66192, Lot 6's veterinary trio/85321). Every
    status_mapping must therefore match its pre-cure value exactly."""
    for code, expected in LOT7_PRE_CURE_STATUS_MAPPING.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} — expected "
            f"untouched pre-cure value {expected!r} (this lot is detach-only, no metadata "
            "correction on any of its 13 codes)."
        )


def test_lot7_spec_never_declares_a_status_mapping_correction():
    """Guard against the spec itself silently growing a correction key that the compiler would
    then apply — Lot 7's adjudication established no independently-verified shape change for any
    of its 13 codes that gets injected into the canonical (rule #9)."""
    spec_by_code = _load_lot7_spec_by_code()
    for code in LOT7_CODES:
        entry = spec_by_code[code]
        assert "status_mapping_correction" not in entry, (
            f"{code}: spec unexpectedly declares status_mapping_correction "
            f"{entry.get('status_mapping_correction')!r} — Lot 7 has no independently-verified "
            "shape change injected for any code (rule #9)."
        )
        assert "whatChanged_correction" not in entry, (
            f"{code}: spec unexpectedly declares whatChanged_correction "
            f"{entry.get('whatChanged_correction')!r}"
        )
        assert "pp28_sources_correction" not in entry, (
            f"{code}: spec unexpectedly declares pp28_sources_correction "
            f"{entry.get('pp28_sources_correction')!r}"
        )
        assert entry.get("action") != "metadata_only", (
            f"{code}: spec unexpectedly declares action=metadata_only — Lot 7 detaches every one "
            "of its 13 codes, none is standalone-metadata-only."
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code already-cured
#    (no-op).
# ---------------------------------------------------------------------------

def test_lot7_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT7_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (all already cured), got "
        f"{result.returncode}. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in LOT7_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot7_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the gate report's own fresh innocence controls)
    and are NOT part of this cure — if the cure ever over-reaches onto one of them, this must
    fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence control, not one of the "
        "13 Lot-7 codes; the cure must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was never part of the "
        "batch_a_lot7 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only, AND verified non-colliding across
#    the other 12 codes in this lot (several share near-identical boilerplate prose).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT7_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — the provenance note "
        f"may have drifted from the spec. _data_note: {note!r}"
    )


@pytest.mark.parametrize("code", LOT7_CODES)
def test_lot7_data_note_marker_does_not_collide_with_siblings(code: str):
    """Guard-over-match antidote: each code's marker must NOT appear inside any OTHER Lot-7
    code's _data_note — several codes in this lot share near-identical boilerplate prose (the
    6-member source_absent_in_vault cluster description, the 'whole practice-of-medicine block'
    alongside-list), so a marker that is present-but-shared would silently pass this test for the
    wrong code."""
    marker = LOT7_DATA_NOTE_MARKERS[code]
    for other in LOT7_CODES:
        if other == code:
            continue
        other_note = _load_record(CANONICAL_PATH, other).get("_data_note", "")
        assert marker not in other_note, (
            f"{code}'s marker {marker!r} unexpectedly also appears in {other}'s _data_note — "
            "marker is not code-specific, guard-over-match risk."
        )


# ---------------------------------------------------------------------------
# 9. Byte-identical disputed payload pairs — the preserved disputed blocks for the two
#    "whole practice-of-medicine" klinik-template pairs and the religious-higher-ed pair this
#    cure adjudicates must survive the cure exactly as found (verified by direct read of the
#    canonical payload in this session). 86109 stands alone (not identical to any of the other
#    4 health-facility codes).
# ---------------------------------------------------------------------------

def test_lot7_religious_higher_ed_pair_shares_byte_identical_disputed_payload():
    """85403 (government) / 85404 (private) religious higher education share the IDENTICAL
    served licensing template — must survive byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT7_RELIGIOUS_HIGHER_ED_PAIR
    }
    reference_code = LOT7_RELIGIOUS_HIGHER_ED_PAIR[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — 85403/85404 "
            "should share a byte-identical religious-higher-education licensing template."
        )


def test_lot7_klinik_pair_a_shares_byte_identical_disputed_payload():
    """86201 (general doctor practice) / 86102 (Puskesmas) share the IDENTICAL generic 'klinik'
    licensing template — must survive byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT7_KLINIK_PAIR_A
    }
    reference_code = LOT7_KLINIK_PAIR_A[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — 86201/86102 "
            "should share a byte-identical klinik licensing template."
        )
    marker = "Self assesment klinik"
    for code in LOT7_KLINIK_PAIR_A:
        assert marker in blobs[code], (
            f"{code}: preserved disputed block no longer carries the shared klinik-template "
            f"signature {marker!r} — audit trail may have drifted."
        )


def test_lot7_klinik_pair_b_shares_byte_identical_disputed_payload():
    """86202 (specialist doctor practice) / 86203 (dental practice) share the IDENTICAL generic
    'klinik' licensing template (a distinct byte-identical pair from 86201/86102 — differs by a
    'TKWNA'/'TK-WNA' spacing artifact) — must survive byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT7_KLINIK_PAIR_B
    }
    reference_code = LOT7_KLINIK_PAIR_B[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — 86202/86203 "
            "should share a byte-identical klinik licensing template."
        )
    marker = "Self assesment klinik"
    for code in LOT7_KLINIK_PAIR_B:
        assert marker in blobs[code], (
            f"{code}: preserved disputed block no longer carries the shared klinik-template "
            f"signature {marker!r} — audit trail may have drifted."
        )


def test_lot7_86109_disputed_payload_is_not_byte_identical_to_the_klinik_pairs():
    """GUILT+INNOCENCE for the health-facility cluster: 86109 ('Aktivitas Rumah Sakit Lainnya')
    is corroborated PP28-ABSENT alongside 86102/86201/86202/86203, but its disputed payload must
    NOT be byte-identical to either klinik-template pair — it carries its own distinct
    hospital-services template, per the gate report's own finding that only the practice-of-
    medicine block (86102/86201/86202/86203) shares the klinik template."""
    blob_86109 = json.dumps(_load_record(CANONICAL_PATH, "86109").get(DISPUTED_KEY), ensure_ascii=False)
    for pair in (LOT7_KLINIK_PAIR_A, LOT7_KLINIK_PAIR_B):
        for code in pair:
            other_blob = json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
            assert blob_86109 != other_blob, (
                f"86109: preserved disputed block unexpectedly byte-identical to {code}'s — "
                "86109 should carry its own distinct hospital-services template, not the shared "
                "klinik template."
            )


# ---------------------------------------------------------------------------
# 10. True-parent provenance — corroborated this session against the gate's by-eye render/
#     crosswalk findings, recorded as _data_note provenance ONLY (rule #9: never injected into
#     pp28_sources/kbli_2020_source/status_mapping).
# ---------------------------------------------------------------------------

def test_lot7_85330_true_parent_recorded_as_provenance_only():
    """85330's true 2020 parent is 85220 ('Pendidikan Menengah/Aliyah Swasta'), found via the
    PAGINATION ROW-BLEED mechanism — recorded as provenance only, the cited 85499 citation
    (itself a false-friend, true destination 85530) is left unchanged."""
    rec = _load_record(CANONICAL_PATH, "85330")
    note = rec.get("_data_note", "")
    assert "85220" in note, "85330: _data_note must name the true parent 85220 as provenance"
    assert "Pendidikan Menengah/Aliyah Swasta" in note, (
        "85330: _data_note must name 85220's title as provenance"
    )
    assert rec.get("kbli_2020_source") == "85499", (
        "85330: kbli_2020_source drifted — must stay the false-friend citation '85499', the "
        "true parent (85220) is provenance-only per rule #9"
    )
    assert "85220" not in (rec.get("pp28_sources") or []), (
        "85330: pp28_sources unexpectedly contains the true parent 85220 — rule #9 forbids "
        "injecting a replacement/additional source value"
    )


def test_lot7_85401_true_parent_set_recorded_as_provenance_only():
    """85401's true 2020 parent set is {51108, 85311, 85312} (the 51108 residual-bucket fan
    reaching the education division) — recorded as provenance only, the cited 3-parent citation
    ({85497, 85496, 85499}) is left unchanged."""
    rec = _load_record(CANONICAL_PATH, "85401")
    note = rec.get("_data_note", "")
    for marker in ("51108", "85311", "85312", "Angkutan Udara Bukan Niaga"):
        assert marker in note, f"85401: _data_note missing expected true-parent marker {marker!r}"
    assert rec.get("pp28_sources") == ["85497", "85496", "85499"], (
        "85401: pp28_sources drifted from its pre-cure 3-parent citation — the true "
        "{51108, 85311, 85312} parent set is provenance-only per rule #9"
    )


def test_lot7_85404_true_parent_set_recorded_as_provenance_only():
    """85404's true 2020 lineage is a 2-parent merge {85332, 85340} — the current single-parent
    citation (85332 only) omits 85340. Recorded as provenance only."""
    rec = _load_record(CANONICAL_PATH, "85404")
    note = rec.get("_data_note", "")
    assert "85340" in note, "85404: _data_note must name the omitted true second parent 85340"
    assert "85332" in note, "85404: _data_note must name the existing cited parent 85332"
    assert rec.get("kbli_2020_source") == "85332", (
        "85404: kbli_2020_source drifted — must stay the single-parent citation '85332', the "
        "true second parent (85340) is provenance-only per rule #9"
    )
    assert rec.get("pp28_sources") == ["85332"], (
        "85404: pp28_sources drifted — must stay the single-parent citation, true second parent "
        "is provenance-only per rule #9"
    )


def test_lot7_91222_true_parent_set_recorded_as_provenance_only():
    """91222's true 2020 lineage is a 2-parent merge {91024, 91029} — the current self-
    referencing citation (91022, private museums) never crosswalks to 91222 in either direction.
    FIRST BATCH-A SIGHTING of the illegitimate_inheritance category. Recorded as provenance
    only."""
    rec = _load_record(CANONICAL_PATH, "91222")
    note = rec.get("_data_note", "")
    for marker in ("91024", "91029", "91022"):
        assert marker in note, f"91222: _data_note missing expected true-parent marker {marker!r}"
    assert rec.get("pp28_sources") == ["91022"], (
        "91222: pp28_sources drifted from its self-referencing pre-cure value — the true "
        "{91024, 91029} parent set is provenance-only per rule #9"
    )
    assert rec.get("status_mapping") == "MATCH_LANGSUNG"
