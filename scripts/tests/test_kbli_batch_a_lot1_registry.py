"""Regression registry — GARUDA-FILIERA Batch A Lot 1 false-friend per_skala
collisions (13 codes, 2026-07-18), driven by
scripts/kbli_filiera/cure_specs/batch_a_lot1.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot1.json.

Modeled closely on test_kbli_false_friend_registry.py (Fase-1 registry,
2026-07-17) — the ALL_DATASET_COPIES list and the _existing_dataset_copies /
_load_by_code / _load_record / _contains_word_or_phrase helpers below are
COPIED VERBATIM from that file (comment marks the origin instead of importing,
to keep this file self-contained and independently readable as its own
regression pin, same convention that file itself used when folding in the
68112 legacy suite).

Cure pattern (identical to Fase-1, see cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" — never silently deleted
  3. _data_note added (verbatim from the cure spec — never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other
     field left untouched

IMPORTANT — these tests are EXPECTED TO BE SKIPPED right now: the Batch A Lot
1 cure has not been applied to the canonical dataset yet (this file lands
ahead of the data PR that runs cure_canonical_collisions.py --apply). The
whole module is skipped via a module-level pytestmark until the canonical
05102 record shows the post-cure shape (per_skala == [] and the disputed key
present) — at that point the module arms itself automatically, no edit
needed.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor code, and every content marker is a multi-word phrase verified (by
direct read of the spec JSON in this session) to actually appear verbatim in
that code's _data_note — never a bare substring.

ADJUDICATION HISTORY (2026-07-18, this file was patched twice as the
conductor's D6 gate closed):
  - v1 (initial build): 7 codes guilty (01700/02409/05102/38122/39001/02402/
    38222), 10 innocence controls including 05200/19206/36003/08920/01287/
    02201 as "Lot-1 adjudicated CLEAN".
  - v2: the blind cross-family extractor (GLM 5.2) flipped 05200 to guilty
    (phantom-source-pointer) -> 8 guilty codes, 9 innocence controls.
  - v3: the same extractor flipped 01287, 02201, 08920, and 36003 to guilty
    too (all phantom-source-pointer / phantom-source-generic-payload /
    payload-cross-contamination flavors, same "pp28_sources cites a code the
    pinned PP28 corpus records ABSENT for" or "payload content belongs to a
    different activity" pattern as the other 8) -> 12 guilty codes total.
    Innocence-neighbor list down to 5: 05101, 38121, 39002, 02102, 19206.
  - v4 (FINAL, this version): post-red-team, 19206 flipped to guilty under
    the plan's PREREGISTERED DIVERGENCE RULE (two independent cross-family
    seats — a Codex refuter dissent and a blind GLM extractor with
    needs_quarantine=true — flagged the cross-vintage generic 19291-basket
    payload against the conductor's initial "clean" call; the conductor
    could not affirmatively certify it) -> 13 guilty codes total (spec
    "flavor" fields were also renamed phantom-source-* -> unresolvable-
    source-* in this pass; the flavor string is not asserted by any test
    here, so it does not touch this file otherwise). Innocence-neighbor list
    now exactly 4: 05101, 38121, 39002, 02102.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT1_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot1.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_false_friend_registry.py (2026-07-17) ---------

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
    A multi-word phrase (contains a space) is matched as a plain substring —
    the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot1_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT1_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 05102 record shows the post-cure shape. Used
    to gate the whole module: pre-apply, per_skala is non-empty and the
    disputed key is absent; post-apply, per_skala == [] and the disputed key
    is present. If the canonical file or the 05102 record is missing
    entirely, treat the cure as NOT applied (module stays skipped rather than
    erroring at collection time)."""
    if not CANONICAL_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "05102")
    except AssertionError:
        return False
    return rec.get("per_skala") == [] and DISPUTED_KEY in rec


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot1 cure not yet applied — tests arm after the data PR",
)


LOT1_CODES = [
    "01700", "02409", "05102", "38122", "39001", "02402", "38222", "05200",
    "01287", "02201", "08920", "36003", "19206",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-18) — must survive the cure untouched.
LOT1_PP28_SOURCES = {
    "01700": ["01711"],
    "02409": ["02409"],
    "05102": ["05100"],
    "38122": ["38120"],
    "39001": ["39000"],
    "02402": ["02402"],
    "38222": ["38220"],
    "05200": ["05200"],
    "01287": ["01287"],
    "02201": ["02201"],
    "08920": ["08920"],
    "36003": ["36003"],
    "19206": ["19291"],
}

# Content markers: multi-word phrases verified (direct read of
# cure_specs/batch_a_lot1.json, 2026-07-18) to be verbatim substrings of that
# code's data_note. Checked ONLY against _data_note — per the task's
# instruction, no markers are invented/asserted inside the disputed blobs.
LOT1_DATA_NOTE_MARKERS = {
    "01700": "single-ancestor inherit on a 6-way merge",
    "02409": "bare-digit join",
    "05102": "mining-CONCESSION regime",
    "38122": "cannot be presumed to govern RADIOACTIVE-waste collection",
    "39001": "Neither row covers carbon CAPTURE",
    "02402": "FOREST-SEED CERTIFICATION content",
    "38222": "PSLB3/B3 regime cannot be presumed to govern RADIOACTIVE-waste processing",
    "05200": "not retrievable from the pinned corpus as hunted",
    "01287": "GENERIC agriculture/estate-crop package",
    "02201": "found contaminating 02402",
    "08920": "SALT extraction (the adjacent code 08930)",
    "36003": "plausibility is not provenance",
    "19206": "preregistered divergence rule",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# that must NOT be touched by this cure — FINAL list per the conductor's
# closed adjudication (2026-07-18): only these 4 were never re-adjudicated to
# guilt across all 4 spec revisions.
#   05101 — true extraction-side sibling of 05102 (05100 SPLITS into 05101/05102)
#   38121 — true non-radioactive sibling of 38122 (38120 SPLITS into 38121/38122)
#   39002 — true carbon-storage sibling of 39001 (39000 SPLITS into 39001/39002/39009)
#   02102 — unrelated forestry code, structural neighbor of 02402/02409's division
#   (05200, 01287, 02201, 08920, 36003 were ALSO in this bucket in earlier
#   spec revisions — the blind cross-family extractor (GLM 5.2) flipped all
#   5 to guilt across v2/v3. 19206 was in this bucket through v3 too — the
#   plan's PREREGISTERED DIVERGENCE RULE (2 independent cross-family seats
#   dissenting from the conductor's initial clean) flipped it in v4,
#   post-red-team. All 6 now live in LOT1_CODES/LOT1_PP28_SOURCES/
#   LOT1_DATA_NOTE_MARKERS instead and have been removed from this list.)
INNOCENT_NEIGHBORS = ["05101", "38121", "39002", "02102"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present
    with a non-empty preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-1 false-friend "
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

@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the
    provenance note (rule #9 no-new-values-without-provenance)."""
    spec_by_code = _load_lot1_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "batch_a_lot1.json — the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text
    VERBATIM — replacing the stale client-facing prose derived from the
    detached (contaminated) per_skala rows."""
    spec_by_code = _load_lot1_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap "
        "text verbatim — the compiler must copy whatYouNeed verbatim, never "
        "paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT1_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value "
        f"{LOT1_PP28_SOURCES[code]!r} — must be preserved untouched (rule: "
        "KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. Idempotency: compiler dry-run over the served dataset reports every code
#    already-cured (no-op), exercising the compiler's real detection logic.
# ---------------------------------------------------------------------------

def test_lot1_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT1_SPEC_PATH),
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
    for code in LOT1_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 6. INNOCENCE (scar #3 discipline) — legitimate neighbor codes untouched.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot1_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or Lot-1 codes adjudicated
    CLEAN) and are NOT part of this cure — if the cure ever over-reaches onto
    one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 13 Lot-1 false-friend collisions; the cure "
        "must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the batch_a_lot1 cure spec."
    )


# ---------------------------------------------------------------------------
# 7. Content markers — verified verbatim in _data_note only (never invented
#    inside the disputed blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT1_CODES)
def test_lot1_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT1_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )
