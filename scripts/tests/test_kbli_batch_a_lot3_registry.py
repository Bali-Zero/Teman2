"""Regression registry — GARUDA-FILIERA Batch A Lot 3 false-friend per_skala
collisions + three mapping-metadata corrections (13 codes, divisions 60->64,
2026-07-19), driven by scripts/kbli_filiera/cure_specs/batch_a_lot3.json and
applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
batch_a_lot3.json.

Modeled closely on test_kbli_batch_a_lot2_registry.py (Lot 2 registry,
2026-07-18) — the ALL_DATASET_COPIES list and the _existing_dataset_copies /
_load_by_code / _load_record / _contains_word_or_phrase helpers below are
COPIED VERBATIM from that file (comment marks the origin instead of
importing, to keep this file self-contained and independently readable as
its own regression pin, same convention Lot 1/2 used).

Cure pattern for the 13 detach-only codes (identical to Lot 1/2, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / every other field left untouched

THREE codes ADDITIONALLY get a metadata correction (Lot 2 extension to the
compiler, reused unmodified here): 60101, 60103, 60203 have status_mapping
corrected to 'MATCH_CON_AGGREGAZIONE' (the merge-aware enum value, already
used 195x elsewhere in the dataset) from a false single-parent/no-parent
narrative (60101 was self-referencing MATCH_LANGSUNG masking a genuine SPLIT;
60103/60203 were single-ancestor CODICE_RINUMERATO masking a genuine
two-parent merge), and intel_2026.whatChanged is corrected in lockstep --
both verbatim from the spec's status_mapping_correction / whatChanged_correction
keys. 64940 (the flagship wrong-parent case, true parent 64992-2020
image-verified) deliberately gets NO status_mapping_correction: CODICE_RINUMERATO
remains the correct relationship TYPE even once the cited source number
(53201, a courier code) is understood to be wrong -- the compiler has no
kbli_2020_source-correction field, and per the standing Lot 1/2 invariant
("this compiler never authors new source values") this cure does not add
one; the true parent is recorded as provenance in _data_note only. Likewise
61905, 64920 (mapping_metadata_false with no independently-verified
replacement), 60201, 60311, 64110, 64320, 64330 (source_absent_in_vault),
61909 (payload_cross_contamination), and 64220 (unresolvable_source_pointer)
get NO status_mapping_correction -- detach-only with an honest data_note, per
rule #9 (no replacement value without provenance). pp28_sources is NOT
touched on any of the 13 codes, including the three metadata-corrected ones
-- the corrected/true ancestors are recorded as provenance inside _data_note
only, per the Lot 1/2 detach convention (this compiler never authors new
source values).

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 3
cure is applied to the canonical dataset (this file lands ahead of / together
with the data PR that runs cure_canonical_collisions.py --apply). The whole
module is skipped via a module-level pytestmark until the canonical 64940
record shows the post-cure shape (per_skala == [] and intel_2026.whatYouNeed
matches the spec's honest-gap text) -- at that point the module arms itself
automatically, no edit needed. 64940 is used as the canary (per the task
instruction driving this cure) even though its own cure touches only ONE
surface (detach, no metadata correction) -- it is the flagship,
image-verified wrong-parent finding of this lot and the whatYouNeed check
alone is a strong, spec-verbatim gate.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor code, and every content marker is a multi-word phrase verified (by
direct read of the spec JSON in this session) to actually appear verbatim in
that code's _data_note -- never a bare substring.

ADJUDICATION HISTORY (2026-07-19): conductor D6 gate on lane run
wf_c00a9ec4-c61 (v2 registry, v2 runner, same infra as Lot 1/2), SIGNED --
second signing, post codex-sol-xhigh red-team (1 BLOCKER + 4 MAJOR, all
cured). Outcome: 13/13 in-scope QUARANTINE, 0 certified; 2/2 innocence
controls (59140, 59201) CERTIFIED true-clean (first lot to validate the
amended pre-verify-both-directions control protocol). Categories:
mapping_metadata_false (4: 60101, 61905, 64920, 64940) -- source_absent_in_vault
(5: 60201, 60311, 64110, 64320, 64330) -- illegitimate_inheritance (2: 60103,
60203) -- payload_cross_contamination (1: 61909) -- unresolvable_source_pointer
(1: 64220). Full report: research/operations/2026-07-19-kbli-batch-a-lot3-
conductor-gate.md (read from the sibling conductor worktree
.worktrees/kbli-pilota-a1-0718/ in this session -- that PR had not yet merged
when this cure was authored, same chain-of-custody pattern Lot 2 used for its
own not-yet-merged gate report).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT3_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot3.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot2_registry.py (2026-07-18) ---------

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


def _load_lot3_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT3_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 64940 record shows the post-cure shape
    (per_skala == [] AND intel_2026.whatYouNeed matches the spec's
    honest-gap text verbatim). Pre-apply, per_skala is non-empty and
    whatYouNeed is the stale securitization-licensing narrative; post-apply,
    per_skala == [] and whatYouNeed is the honest-gap text. If the canonical
    file, the spec, or the 64940 record is missing entirely, treat the cure
    as NOT applied (module stays skipped rather than erroring at collection
    time)."""
    if not CANONICAL_PATH.exists() or not LOT3_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "64940")
        spec_by_code = _load_lot3_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("64940", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot3 cure not yet applied — tests arm after the data PR",
)


LOT3_CODES = [
    "60101", "60103", "60201", "60203", "60311", "61905", "61909",
    "64110", "64220", "64320", "64330", "64920", "64940",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — must survive the cure untouched (including
# on 60101/60103/60203, whose status_mapping DOES change, and 64940, whose
# TRUE parent is image-verified but never injected).
LOT3_PP28_SOURCES = {
    "60101": ["60101"],
    "60103": ["60102"],
    "60201": ["60201"],
    "60203": ["60202"],
    "60311": ["63911"],
    "61905": ["61992"],
    "61909": ["61919", "61999", "61929"],
    "64110": ["64110"],
    "64220": ["64200"],
    "64320": ["64300"],
    "64330": ["64300"],
    "64920": ["86902"],
    "64940": ["53201"],
}

# Codes whose status_mapping / whatChanged get corrected by this cure
# (the other 9 are detach-only, per rule #9 no-replacement-without-provenance).
LOT3_METADATA_CORRECTED_CODES = ["60101", "60103", "60203"]

# Content markers: multi-word phrases verified (direct read of
# cure_specs/batch_a_lot3.json, 2026-07-19) to be verbatim substrings of that
# code's _data_note. Checked ONLY against _data_note.
LOT3_DATA_NOTE_MARKERS = {
    "60101": "genuine SPLIT, not the preserved-scope",
    "60103": "60101 AND 60102 both map to KBLI-2025 60103",
    "60201": "ABSENT for code 60201 across all 21 lampiran files",
    "60203": "60201 AND 60202 both map to KBLI-2025 60203",
    "60311": "ABSENT for code 63911 across all 21 lampiran files",
    "61905": "below-100% renumbering-match confidence flagged as a metadata defect by BOTH",
    "61909": "INDUSTRIAL/TRADE licensing text with no telecom relevance",
    "64110": "ABSENT for code 64110 across all 21 lampiran files",
    "64220": "self-confirmation path could not ground the cited pointer",
    "64320": "64330 (this same spec, below) cites the IDENTICAL kbli_2020_source",
    "64330": "the SAME cited 2020 source as 64320 above",
    "64920": "LOW-confidence (69%) auto-match to an UNRELATED 2020 code",
    "64940": "the TRUE single parent, directly corroborated by this code's own uraian text",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# untouched by this cure.
#   60102 — division-60 sibling of 60101/60103 (digital radio, not analog/streaming)
#   60202 — division-60 sibling of 60201/60203 (digital TV, not analog/streaming)
#   59140 — Lot 3 gate report's OWN innocence control (film screening), CERTIFIED clean
#   59201 — Lot 3 gate report's OWN innocence control (sound recording), CERTIFIED clean
#   61901 — division-61 neighbor of 61905/61909 (premium call services, unrelated code)
#   64199 — division-64 neighbor of 64110/64220/64320/64330 (other monetary intermediation)
#   64930 — division-64 neighbor of 64920/64940 (factoring, unrelated code)
INNOCENT_NEIGHBORS = ["60102", "60202", "59140", "59201", "61901", "64199", "64930"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT3_CODES)
def test_lot3_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present
    with a non-empty preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-3 false-friend "
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

@pytest.mark.parametrize("code", LOT3_CODES)
def test_lot3_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the
    provenance note (rule #9 no-new-values-without-provenance)."""
    spec_by_code = _load_lot3_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "batch_a_lot3.json — the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT3_CODES)
def test_lot3_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text
    VERBATIM — replacing the stale client-facing prose derived from the
    detached (contaminated) per_skala rows."""
    spec_by_code = _load_lot3_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim — the compiler must copy whatYouNeed verbatim, never "
        "paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including the 3 metadata-corrected codes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT3_CODES)
def test_lot3_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged
    — even for 60101/60103/60203, whose status_mapping IS corrected, and
    64940, whose true parent is image-verified: the compiler never authors
    new source values (Lot 1/2 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT3_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT3_PP28_SOURCES[code]!r} — must be preserved untouched (rule: "
        "KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. Metadata corrections (Lot 2 extension, reused here) — 60101/60103/60203
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT3_METADATA_CORRECTED_CODES)
def test_lot3_status_mapping_corrected_to_match_con_aggregazione(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE", (
        f"{code}: status_mapping must be corrected to the merge-aware "
        "'MATCH_CON_AGGREGAZIONE' enum value (the false single-parent/"
        "no-parent narrative must not survive the cure)."
    )


@pytest.mark.parametrize("code", LOT3_METADATA_CORRECTED_CODES)
def test_lot3_whatchanged_corrected(code: str):
    spec_by_code = _load_lot3_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatChanged") == spec_by_code[code]["whatChanged_correction"], (
        f"{code}: intel_2026.whatChanged must be corrected verbatim from the "
        "spec's whatChanged_correction."
    )


def test_lot3_non_corrected_codes_keep_original_status_mapping():
    """The 10 detach-only codes (no independently-verified replacement
    established) must NOT have their status_mapping enum touched — only
    60101/60103/60203 get a metadata correction in this lot."""
    pre_cure_status_mapping = {
        "60201": "MATCH_LANGSUNG",
        "60311": "CODICE_RINUMERATO",
        "61905": "CODICE_RINUMERATO",
        "61909": "MATCH_CON_AGGREGAZIONE",
        "64110": "MATCH_LANGSUNG",
        "64220": "MATCH_CON_AGGREGAZIONE",
        "64320": "CODICE_RINUMERATO",
        "64330": "CODICE_RINUMERATO",
        "64920": "CODICE_RINUMERATO",
        "64940": "CODICE_RINUMERATO",
    }
    for code, expected in pre_cure_status_mapping.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} "
            f"— expected untouched pre-cure value {expected!r} (this code is "
            "detach-only, no metadata correction in this cure)."
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code
#    already-cured (no-op), exercising the compiler's real detection logic —
#    including the metadata-correction branch for 60101/60103/60203.
# ---------------------------------------------------------------------------

def test_lot3_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT3_SPEC_PATH),
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
    for code in LOT3_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be
#    untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot3_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the gate report's own
    pre-verified innocence controls) and are NOT part of this cure — if the
    cure ever over-reaches onto one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 13 Lot-3 codes; the cure must not have "
        "touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot3 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only (never invented
#    inside the disputed blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT3_CODES)
def test_lot3_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT3_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 9. 61909 payload-contamination: the preserved disputed block must still
#    show the industrial/trade contamination signature this cure detached
#    it for (verified by direct read of the canonical payload in this
#    session — see the spec's data_note for 61909).
# ---------------------------------------------------------------------------

def test_lot3_61909_disputed_block_shows_industrial_contamination_signature():
    marker = "Menteri Perdagangan"
    rec = _load_record(CANONICAL_PATH, "61909")
    disputed = rec.get(DISPUTED_KEY)
    blob = json.dumps(disputed, ensure_ascii=False)
    assert marker in blob, (
        f"61909: preserved disputed block no longer carries the "
        f"industrial/trade contamination signature {marker!r} — audit trail "
        "may have drifted."
    )


# ---------------------------------------------------------------------------
# 10. 64320/64330 shared-source anomaly: both codes cite the identical
#     pre-cure kbli_2020_source/pp28_sources value ('64300') — this must
#     survive the cure exactly as found (never silently deduplicated or
#     corrected, since no independently-verified replacement exists).
# ---------------------------------------------------------------------------

def test_lot3_64320_64330_share_identical_unverified_source():
    rec_320 = _load_record(CANONICAL_PATH, "64320")
    rec_330 = _load_record(CANONICAL_PATH, "64330")
    assert rec_320.get("pp28_sources") == rec_330.get("pp28_sources") == ["64300"], (
        "64320/64330: expected both to retain the identical unverified "
        f"pp28_sources ['64300'], got {rec_320.get('pp28_sources')!r} and "
        f"{rec_330.get('pp28_sources')!r}."
    )
