"""Regression registry — GARUDA-FILIERA Batch A Lot 2 false-friend per_skala
collisions + one mapping-metadata correction (13 codes, divisions 42->59,
2026-07-18), driven by scripts/kbli_filiera/cure_specs/batch_a_lot2.json and
applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
batch_a_lot2.json.

Modeled closely on test_kbli_batch_a_lot1_registry.py (Lot 1 registry,
2026-07-18) — the ALL_DATASET_COPIES list and the _existing_dataset_copies /
_load_by_code / _load_record / _contains_word_or_phrase helpers below are
COPIED VERBATIM from that file (comment marks the origin instead of
importing, to keep this file self-contained and independently readable as
its own regression pin, same convention Lot 1 used).

Cure pattern for the 12 detach-only codes (identical to Lot 1, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / every other field left untouched

47771 ADDITIONALLY gets a metadata correction (Lot 2 extension to the
compiler, 2026-07-18): status_mapping corrected from the canonical's false
'MATCH_LANGSUNG' to 'MATCH_CON_AGGREGAZIONE' (the merge-aware enum value),
and intel_2026.whatChanged corrected from the false "Unchanged from KBLI
2020 -- direct match" -- both verbatim from the spec's
status_mapping_correction / whatChanged_correction keys. pp28_sources is
NOT touched (stays ['47771']) -- the 4 BPS crosswalk ancestors are recorded
as provenance inside _data_note only, per the Lot 1 detach convention (this
compiler never authors new source values).

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 2
cure is applied to the canonical dataset (this file lands ahead of / together
with the data PR that runs cure_canonical_collisions.py --apply). The whole
module is skipped via a module-level pytestmark until the canonical 47771
record shows the post-cure shape (per_skala == [] and status_mapping ==
'MATCH_CON_AGGREGAZIONE') -- at that point the module arms itself
automatically, no edit needed. 47771 is used as the canary (not 05102, which
is a Lot 1 canary) because it is the one code in this lot whose cure touches
TWO independent surfaces (detach + metadata) -- the strongest single-code
gate available for this lot.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor code, and every content marker is a multi-word phrase verified (by
direct read of the spec JSON in this session) to actually appear verbatim in
that code's _data_note -- never a bare substring.

ADJUDICATION HISTORY (2026-07-18): conductor D6 gate on lane run
wf_ec5c5f93-64b (v2 registry #2740, v2 runner #2741), SIGNED -- second
signing, post codex-sol-xhigh red-team (4 BLOCKER + 2 MAJOR + 1 MINOR, all
cured) + cross-family GLM blind pass (Appendix A: m1 5/5=1.00, m5 4/4
valid=1.00). Outcome: 13/13 in-scope QUARANTINE, 0 certified. Categories:
payload_cross_contamination (8: 49296, 52103, 52105, 52211, 52219, 52232,
52239, 52299) -- source_absent_in_vault (4: 42999, 49233, 50113, 59131) --
mapping_metadata_false (1: 47771, upgraded at second signing to
detach+metadata). Full report: research/operations/2026-07-18-kbli-batch-a-
lot2-conductor-gate.md (PR #2753). The two innocence controls discussed in
that same report (52101, 46100) are OUT OF SCOPE for this cure -- both turned
out contaminated too, but get their own standalone metadata-fix cure
elsewhere (their per_skala stays untouched, healthy OSS-native); they are
included below as EXTRA innocence controls precisely because they are the
most adversarial choice available (same report, explicitly discussed,
explicitly not part of this spec).
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
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
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
    false-positive inside a longer word (e.g. bare 'SPA' inside 'aerospace').
    A multi-word phrase (contains a space) is matched as a plain substring --
    the multi-word shape itself is already a strong disambiguator."""
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
    """True once the canonical 47771 record shows the post-cure shape (both
    the detach AND the metadata correction — the strongest single-code gate
    available for this lot). Pre-apply, per_skala is non-empty and
    status_mapping == 'MATCH_LANGSUNG'; post-apply, per_skala == [] and
    status_mapping == 'MATCH_CON_AGGREGAZIONE'. If the canonical file or the
    47771 record is missing entirely, treat the cure as NOT applied (module
    stays skipped rather than erroring at collection time)."""
    if not CANONICAL_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "47771")
    except AssertionError:
        return False
    return rec.get("per_skala") == [] and rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE"


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot2 cure not yet applied — tests arm after the data PR",
)


LOT2_CODES = [
    "42999", "47771", "49233", "49296", "50113", "52103", "52105", "52211",
    "52219", "52232", "52239", "52299", "59131",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-18) — must survive the cure untouched (including
# on 47771, whose status_mapping DOES change but whose pp28_sources does not).
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

# Content markers: multi-word phrases verified (direct read of
# cure_specs/batch_a_lot2.json, 2026-07-18) to be verbatim substrings of that
# code's _data_note. Checked ONLY against _data_note.
LOT2_DATA_NOTE_MARKERS = {
    "42999": "TWO-parent BPS merge",
    "47771": "FOUR-source merge in BOTH crosswalk directions",
    "49233": "unresolvable_source_pointer",
    "49296": "0 of \"ojek\"",
    "50113": "gold-set content is topically consistent",
    "52103": "FISHERY-PORT licensing",
    "52105": "SEAPORT-OPERATOR licensing block",
    "52211": "PORT CARGO-TALLY AGENT",
    "52219": "SHIP-BROKER",
    "52232": "PORT-CONSTRUCTION PROPOSAL block",
    "52239": "LOW-confidence (72%) auto-match",
    "52299": "preregistered divergence rule",
    "59131": "clean self-referencing crosswalk",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# untouched by this cure, PLUS the two out-of-lot controls (52101, 46100)
# discussed in the same conductor gate report but explicitly given their own
# standalone metadata-fix cure elsewhere (their per_skala must stay healthy
# and untouched by THIS spec).
#   42101 — division-42 neighbor of 42999 (road construction, unrelated code)
#   47772 — division-47 neighbor of 47771 (LPG retail, unrelated code)
#   52102 — division-52 neighbor of 52103/52105 (cold-storage warehousing)
#   59132 — division-59 neighbor of 59131 (private, not government, distribution)
#   52101 — Lot 2 gate report control: 5-parent MERGE, standalone cure (§3.3), NOT this spec
#   46100 — Lot 2 gate report control: 2-parent MERGE, standalone cure (§1), NOT this spec
INNOCENT_NEIGHBORS = ["42101", "47772", "52102", "59132", "52101", "46100"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
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
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the
    provenance note (rule #9 no-new-values-without-provenance)."""
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
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text
    VERBATIM — replacing the stale client-facing prose derived from the
    detached (contaminated) per_skala rows."""
    spec_by_code = _load_lot2_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim — the compiler must copy whatYouNeed verbatim, never "
        "paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including 47771 whose status_mapping DOES change)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged
    — even for 47771, whose status_mapping IS corrected: the compiler never
    authors new source values (Lot 1 detach convention, extended to Lot 2's
    metadata-correction capability)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT2_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT2_PP28_SOURCES[code]!r} — must be preserved untouched (rule: "
        "KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. 47771-specific: the metadata correction (Lot 2 extension)
# ---------------------------------------------------------------------------

def test_lot2_47771_status_mapping_corrected():
    rec = _load_record(CANONICAL_PATH, "47771")
    assert rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE", (
        "47771: status_mapping must be corrected from the false 'MATCH_LANGSUNG' "
        "to the merge-aware 'MATCH_CON_AGGREGAZIONE' enum value."
    )


def test_lot2_47771_whatchanged_corrected():
    spec_by_code = _load_lot2_spec_by_code()
    rec = _load_record(CANONICAL_PATH, "47771")
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatChanged") == spec_by_code["47771"]["whatChanged_correction"], (
        "47771: intel_2026.whatChanged must be corrected verbatim from the spec's "
        "whatChanged_correction — the false 'Unchanged from KBLI 2020 — direct "
        "match' narrative must not survive the cure."
    )


def test_lot2_47771_data_note_names_all_four_bps_ancestors():
    """The 4 BPS crosswalk ancestors must be named in _data_note (provenance),
    NEVER injected into pp28_sources (checked separately above)."""
    rec = _load_record(CANONICAL_PATH, "47771")
    note = rec.get("_data_note", "")
    for ancestor in ("47771", "47892", "47919", "47996"):
        assert ancestor in note, (
            f"47771: BPS crosswalk ancestor {ancestor!r} not named in _data_note "
            f"— all 4 ancestors must be recorded as provenance. _data_note: {note!r}"
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code
#    already-cured (no-op), exercising the compiler's real detection logic —
#    including the metadata-correction branch for 47771.
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


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes AND the two
#    out-of-lot controls (52101, 46100) must be untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot2_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors or out-of-lot controls and are
    NOT part of this cure — if the cure ever over-reaches onto one of them,
    this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 13 Lot-2 codes; the cure must not have "
        "touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot2 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only (never invented
#    inside the disputed blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT2_CODES)
def test_lot2_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT2_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 9. Byte-identical payload-contamination cluster (52219/52239/52299): the
#    disputed blocks preserved for audit must still show the shared "ship
#    broker" contamination signature this cure detached them for.
# ---------------------------------------------------------------------------

def test_lot2_ship_broker_cluster_disputed_blocks_share_signature():
    marker = "perantara jual beli dan/atau sewa kapal"
    for code in ("52219", "52239", "52299"):
        rec = _load_record(CANONICAL_PATH, code)
        disputed = rec.get(DISPUTED_KEY)
        blob = json.dumps(disputed, ensure_ascii=False)
        assert marker in blob, (
            f"{code}: preserved disputed block no longer carries the "
            f"ship-broker signature {marker!r} — audit trail may have drifted."
        )
