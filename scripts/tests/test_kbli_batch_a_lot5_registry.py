"""Regression registry — GARUDA-FILIERA Batch A Lot 5 false-friend per_skala
collisions + two wrong-parent metadata provenance notes (13 codes, divisions
66->70, 2026-07-19), driven by scripts/kbli_filiera/cure_specs/batch_a_lot5.json
and applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
batch_a_lot5.json.

Modeled closely on test_kbli_batch_a_lot4_registry.py (Lot 4 registry,
2026-07-19) — the ALL_DATASET_COPIES list and the _existing_dataset_copies /
_load_by_code / _load_record / _contains_word_or_phrase helpers below are
COPIED VERBATIM from that file (comment marks the origin instead of
importing, to keep this file self-contained and independently readable as
its own regression pin, same convention Lot 1-4 used).

Cure pattern for the 13 detach-only codes (identical to Lot 1-4, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other
     field left untouched

NONE of Lot 5's 13 codes get a status_mapping_correction or
whatChanged_correction key in the spec (same discipline as Lot 4): 68123 and
68126's true parent (68111) is corroborated this session (the confirmed
seven-child 2020-68111 crosswalk fan {68111, 68112, 68123, 68125, 68126,
68127, 68129} + the canonical's own 68122 record independently confirming
68130's real 2025 child is 68122, not 68123) but the relationship SHAPE
stays CODICE_RINUMERATO even once the cited NUMBER (68130/52101) is
understood to be wrong -- the same rule that withheld a correction from Lot
3's 64940 and Lot 4's 64955. 66192's true ancestor (66193, not the
self-cited 66192) is likewise recorded as _data_note provenance only. The
other 10 codes have their crosswalk metadata left UNDISPUTED by this cure --
the defect adjudicated is the served per_skala payload, never an alternate
crosswalk narrative. pp28_sources is NOT touched on any of the 13 codes.

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 5
cure is applied to the canonical dataset (this file lands ahead of / together
with the data PR that runs cure_canonical_collisions.py --apply). The whole
module is skipped via a module-level pytestmark until the canonical 66192
record shows the post-cure shape (per_skala == [] and intel_2026.whatYouNeed
matches the spec's honest-gap text) -- at that point the module arms itself
automatically, no edit needed. 66192 is used as the canary (same convention
as Lot 3's 64940 / Lot 4's 64955 canaries) -- it is the flagship multi-defect
finding of this lot (code-collision + cooperative-rating payload
contamination), corroborated this session against the 2025-dataset's own
66193/66132/66198 records.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor code, and every content marker is a multi-word phrase verified (by
direct read of the spec JSON in this session) to actually appear verbatim in
that code's _data_note -- never a bare substring.

ADJUDICATION HISTORY (2026-07-19): conductor D6 gate on lane run
wf_0f7438f4-a41 (v2 registry categories, same runner infra as Lot 1-4, FIRST
lot run with the neutralized innocence prompt shipped at PR #2776), SIGNED --
first signing, pre-adversarial-pass (a codex sol-xhigh red-team pass was
scheduled on the signed report at spec-authoring time; findings, if any, are
cured into this same PR before it ships). Outcome: 13/13 in-scope
QUARANTINE, 0 certified; 2/2 innocence controls (59140, 59201, THIRD
deliberate reuse) certified GENUINELY BLIND for the first time (the
neutralized innocence prompt no longer announces the expected verdict).
Categories: payload_cross_contamination (10: 66192, 66197, 66211, 66224,
66292, 66299, 66309, 68125, 68127, 68129) -- mapping_metadata_false (2:
68123, 68126) -- source_absent_in_vault (1: 70100). Full report:
research/operations/2026-07-19-kbli-batch-a-lot5-conductor-gate.md (read from
the sibling conductor worktree .worktrees/kbli-pilota-a1-0718/ in this
session -- that PR had not yet merged when this cure was authored, same
chain-of-custody pattern Lot 2/3/4 used for their own not-yet-merged gate
reports). Precondition PR #2777 (kbli/governance-v3 calibration re-salt) was
polled MERGED before this branch was cut from origin/main (hard ordering
constraint, since #2777 also re-emits membership/calibration and this lot's
data apply must build on top of it, not race it).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT5_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot5.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot4_registry.py (2026-07-19) ---------

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


def _load_lot5_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT5_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 66192 record shows the post-cure shape
    (per_skala == [] AND intel_2026.whatYouNeed matches the spec's
    honest-gap text verbatim). Pre-apply, per_skala is non-empty; post-apply,
    per_skala == [] and whatYouNeed is the honest-gap text. If the canonical
    file, the spec, or the 66192 record is missing entirely, treat the cure
    as NOT applied (module stays skipped rather than erroring at collection
    time)."""
    if not CANONICAL_PATH.exists() or not LOT5_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "66192")
        spec_by_code = _load_lot5_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("66192", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot5 cure not yet applied — tests arm after the data PR",
)


LOT5_CODES = [
    "66192", "66197", "66211", "66224", "66292", "66299", "66309", "68123",
    "68125", "68126", "68127", "68129", "70100",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — must survive the cure untouched (including
# on 66192/68123/68126, whose TRUE parents are image/record-verified but
# never injected).
LOT5_PP28_SOURCES = {
    "66192": ["66192"],
    "66197": ["66139"],
    "66211": ["66211"],
    "66224": ["66224"],
    "66292": ["66292"],
    "66299": ["66299"],
    "66309": ["66390"],
    "68123": ["68130"],
    "68125": ["68120", "68130"],
    "68126": ["52101"],
    "68127": ["68111"],
    "68129": ["68111"],
    "70100": ["70100"],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — NONE of Lot 5's 13 codes get a metadata
# correction in this lot (same discipline as Lot 4).
LOT5_PRE_CURE_STATUS_MAPPING = {
    "66192": "MATCH_LANGSUNG",
    "66197": "CODICE_RINUMERATO",
    "66211": "MATCH_LANGSUNG",
    "66224": "MATCH_LANGSUNG",
    "66292": "MATCH_LANGSUNG",
    "66299": "MATCH_LANGSUNG",
    "66309": "CODICE_RINUMERATO",
    "68123": "CODICE_RINUMERATO",
    "68125": "MATCH_CON_AGGREGAZIONE",
    "68126": "CODICE_RINUMERATO",
    "68127": "CODICE_RINUMERATO",
    "68129": "CODICE_RINUMERATO",
    "70100": "MATCH_LANGSUNG",
}

# The 7 codes sharing the byte-identical cooperative-rating (pemeringkatan
# koperasi) contaminated payload, root-traced (report §6, corroborated this
# session against the canonical's own 66198 record) to PP28's own
# 2020-vintage 66292 lampiran row.
LOT5_COOPERATIVE_PAYLOAD_CODES = [
    "66192", "66197", "66211", "66224", "66292", "66299", "66309",
]

# The 2 codes sharing the byte-identical generic hygiene-sanitation
# certification block (68125's first row also matches this signature, but
# 68125 additionally carries a second, distinct row, so it is checked
# separately rather than folded into this byte-identical set).
LOT5_HYGIENE_PAYLOAD_CODES = ["68123", "68126"]

# Content markers: multi-word phrases verified (direct read of
# cure_specs/batch_a_lot5.json, 2026-07-19) to be verbatim substrings of that
# code's _data_note. Checked ONLY against _data_note.
LOT5_DATA_NOTE_MARKERS = {
    "66192": "the digit string '66192' is a code-collision false-positive",
    "66197": "category_mismatch",
    "66211": "THREE true D1-clean-vs-D5-problem seat-agreement",
    "66224": "THREE true D1-clean-vs-D5-problem seat-agreement",
    "66292": "ROOT-CAUSE code of the lot's cooperative-rating contamination cluster",
    "66299": "cooperative-rating licensing block",
    "66309": "distinct crosswalk citation from the other 6",
    "68123": "confirming 68130's actual 2025 child is 68122",
    "68125": "TWO rows are served",
    "68126": "establishes as FALSE by direct contradiction",
    "68127": "this citation is CORRECT",
    "68129": "distinct third contamination signature",
    "70100": "THIRD of the three true D1-clean-vs-D5-problem",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# untouched by this cure.
#   66111 — division-66 neighbor (securities exchange system operation), unrelated
#   66112 — division-66 neighbor (futures exchange), unrelated
#   66121 — division-66 neighbor (securities brokerage excl. carbon units), unrelated
#   66193 — division-66 neighbor, 2025's own "Pemeringkatan Efek" code; the
#            report's true-ancestor read is about the 2020 vintage of this
#            NUMBER, not this 2025 record — untouched by this cure
#   66198 — the TRUE 2025 home of the cooperative-rating payload (own
#            kbli_2020_source='66292', own per_skala legitimately carries the
#            koperasi block) — the corroborating control, untouched
#   68111 — the fan's own hub code (2025), self-cites correctly, untouched
#   68122 — "Pengelolaan Kawasan Industri", the TRUE 2025 child of 68130 (own
#            kbli_2020_source='68130') — the corroborating control for
#            68123's false citation, untouched
#   59140 — Lot 3/4/5 gate reports' OWN reused innocence control (film screening)
#   59201 — Lot 3/4/5 gate reports' OWN reused innocence control (sound recording)
INNOCENT_NEIGHBORS = [
    "66111", "66112", "66121", "66193", "66198", "68111", "68122", "59140", "59201",
]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT5_CODES)
def test_lot5_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present
    with a non-empty preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-5 false-friend "
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

@pytest.mark.parametrize("code", LOT5_CODES)
def test_lot5_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the
    provenance note (rule #9 no-new-values-without-provenance)."""
    spec_by_code = _load_lot5_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "batch_a_lot5.json — the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT5_CODES)
def test_lot5_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text
    VERBATIM — replacing the stale client-facing prose derived from the
    detached (contaminated) per_skala rows."""
    spec_by_code = _load_lot5_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim — the compiler must copy whatYouNeed verbatim, never "
        "paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including 66192/68123/68126 whose true
#    parents are image/record-verified but never injected)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT5_CODES)
def test_lot5_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged
    — even for 66192/68123/68126, whose true parents are established this
    session: the compiler never authors new source values (Lot 1-4 detach
    convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT5_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT5_PP28_SOURCES[code]!r} — must be preserved untouched (rule: "
        "KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. NO metadata corrections in this lot — status_mapping must survive
#    untouched on ALL 13 codes (same discipline as Lot 4)
# ---------------------------------------------------------------------------

def test_lot5_no_code_gets_a_status_mapping_correction():
    """No code in this lot has an independently-verified SHAPE change
    (split/merge) established in the gate report — 66192/68123/68126's true
    parents are found but the relationship stays 1:1 (same rule as Lot 3's
    64940 and Lot 4's 64955); the other 10 have no established replacement
    at all. Every status_mapping must therefore match its pre-cure value
    exactly."""
    for code, expected in LOT5_PRE_CURE_STATUS_MAPPING.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} "
            f"— expected untouched pre-cure value {expected!r} (this lot is "
            "detach-only, no metadata correction on any of its 13 codes)."
        )


def test_lot5_spec_never_declares_a_status_mapping_correction():
    """Guard against the spec itself silently growing a correction key that
    the compiler would then apply — Lot 5's adjudication established no
    independently-verified shape change for any of its 13 codes (rule #9)."""
    spec_by_code = _load_lot5_spec_by_code()
    for code in LOT5_CODES:
        entry = spec_by_code[code]
        assert "status_mapping_correction" not in entry, (
            f"{code}: spec unexpectedly declares status_mapping_correction "
            f"{entry.get('status_mapping_correction')!r} — Lot 5 has no "
            "independently-verified shape change for any code (rule #9)."
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
            f"{code}: spec unexpectedly declares action=metadata_only — "
            "Lot 5 detaches every one of its 13 codes, none is standalone-"
            "metadata-only."
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code
#    already-cured (no-op).
# ---------------------------------------------------------------------------

def test_lot5_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT5_SPEC_PATH),
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
    for code in LOT5_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be
#    untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot5_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the gate reports' own
    pre-verified innocence controls) and are NOT part of this cure — if the
    cure ever over-reaches onto one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 13 Lot-5 codes; the cure must not have "
        "touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot5 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only (never invented
#    inside the disputed blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT5_CODES)
def test_lot5_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT5_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 9. Cooperative-rating payload signature — the preserved disputed block for
#    all 7 cooperative-rating codes must still show the cooperative-rating
#    contamination signature this cure detached them for (verified by direct
#    read of the canonical payload in this session).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT5_COOPERATIVE_PAYLOAD_CODES)
def test_lot5_cooperative_payload_disputed_block_shows_signature(code: str):
    marker = "pemeringkatan koperasi"
    rec = _load_record(CANONICAL_PATH, code)
    disputed = rec.get(DISPUTED_KEY)
    blob = json.dumps(disputed, ensure_ascii=False)
    assert marker in blob, (
        f"{code}: preserved disputed block no longer carries the "
        f"cooperative-rating contamination signature {marker!r} — audit "
        "trail may have drifted."
    )


def test_lot5_all_seven_cooperative_codes_share_byte_identical_disputed_payload():
    """The gate report's finding that these 7 codes carry the IDENTICAL
    cooperative-rating kewajiban payload must survive the cure exactly as
    found: the preserved disputed blocks for all seven must be
    byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT5_COOPERATIVE_PAYLOAD_CODES
    }
    reference_code = LOT5_COOPERATIVE_PAYLOAD_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — "
            "the gate report's finding that all seven codes carry a "
            "byte-identical contaminated payload should be preserved by the cure "
            "(both are audit-only preserved blocks, never mutated)."
        )


def test_lot5_hygiene_payload_codes_share_byte_identical_disputed_payload():
    """68123 and 68126 carry the identical generic hygiene-sanitation
    certification block (verified this session) — must survive byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT5_HYGIENE_PAYLOAD_CODES
    }
    reference_code = LOT5_HYGIENE_PAYLOAD_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — "
            "68123/68126 should share a byte-identical hygiene-sanitation "
            "contaminated payload."
        )


# ---------------------------------------------------------------------------
# 10. True-parent provenance — corroborated this session against the
#     CURRENT KBLI-2025 dataset's own records (66198/68122), per the report's
#     root-cause and fan findings.
# ---------------------------------------------------------------------------

def test_lot5_66292_root_cause_corroborated_against_66198_record():
    rec_66292 = _load_record(CANONICAL_PATH, "66292")
    rec_66198 = _load_record(CANONICAL_PATH, "66198")
    assert "66198" in rec_66292.get("_data_note", ""), (
        "66292: _data_note must name the payload's true 2025 home 66198 as provenance"
    )
    assert rec_66198.get("kbli_2020_source") == "66292", (
        "66198: kbli_2020_source drifted from '66292' — re-verify the 66292 "
        "data_note's root-cause cross-check if this ever changes"
    )


def test_lot5_68123_68126_true_parent_corroborated_against_68122_record():
    rec_68123 = _load_record(CANONICAL_PATH, "68123")
    rec_68126 = _load_record(CANONICAL_PATH, "68126")
    rec_68122 = _load_record(CANONICAL_PATH, "68122")
    assert "68111" in rec_68123.get("_data_note", ""), (
        "68123: _data_note must name the true parent 68111 as provenance"
    )
    assert "68111" in rec_68126.get("_data_note", ""), (
        "68126: _data_note must name the true parent 68111 as provenance"
    )
    assert "68122" in rec_68123.get("_data_note", ""), (
        "68123: _data_note must name 68122 as the corroborating record for "
        "68130's real 2025 child"
    )
    assert rec_68122.get("kbli_2020_source") == "68130", (
        "68122: kbli_2020_source drifted from '68130' — re-verify the "
        "68123/68126 data_notes' cross-check if this ever changes"
    )


# ---------------------------------------------------------------------------
# 11. 70100 _source_relabeled dispute — MANDATORY per the Lot 5 conductor gate
#     SECOND SIGNING (§3, Adjudications item 4): the canonical's own
#     _source_relabeled note (2026-06-27) asserts "content is OSS-RBA-2025 per
#     _l1/_l2", but the record's OWN structured markers (no _l2_source key,
#     _l2_status=no_oss_risk, PP28 vault-exhaustive ABSENT 21 files/11,208
#     pages) refute that prose claim for the per_skala layer. F12: never "not
#     published", always "not retrievable/verifiable".
# ---------------------------------------------------------------------------

def test_lot5_70100_data_note_records_source_relabeled_dispute_and_resolution():
    rec = _load_record(CANONICAL_PATH, "70100")
    note = rec.get("_data_note", "")
    assert "_source_relabeled" in note, (
        "70100: _data_note must explicitly name the _source_relabeled dispute "
        "(gate report §3.4) — a bare detach note is not enough for this code"
    )
    for marker in (
        "OSS-RBA-2025",
        "NO `_l2_source` key",
        "_l2_status='no_oss_risk'",
        "11,208 pages",
        "TRACK-P doctrine",
        "Detach STANDS",
    ):
        assert marker in note, (
            f"70100: _data_note missing expected dispute-resolution marker {marker!r} — "
            "the gate report's structured-markers-beat-prose resolution must be recorded "
            "explicitly, not just alluded to"
        )
    # F12 wording discipline: never "not published" (a claim about regulatory non-existence)
    assert "not published" not in note.lower(), (
        "70100: _data_note uses F12-forbidden 'not published' wording — must say "
        "'not retrievable/verifiable from our sources' instead"
    )


def test_lot5_70100_source_relabeled_dispute_corroborated_against_canonical_markers():
    """Cross-check the _data_note's claims about 70100's OWN structured markers against the
    live canonical record — the dispute-resolution text must describe reality, not merely assert
    it (anti-hallucination discipline)."""
    rec = _load_record(CANONICAL_PATH, "70100")
    assert "_l2_source" not in rec, (
        "70100: canonical unexpectedly now carries an _l2_source key — the data_note's refutation "
        "of the _source_relabeled prose claim depends on this key being genuinely absent"
    )
    assert rec.get("_l2_status") == "no_oss_risk", (
        f"70100: _l2_status drifted to {rec.get('_l2_status')!r} — the data_note's dispute-"
        "resolution text cites this as 'no_oss_risk' verbatim"
    )
