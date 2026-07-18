"""Regression registry — GARUDA-FILIERA Batch A Lot 2, 56101 metadata cure
ONLY (2026-07-18, conductor-signed D6 verdict, session f5892d39), driven by:

  - scripts/kbli_filiera/cure_specs/metadata_56101.json applied via
    scripts/kbli_filiera/cure_metadata_pp28_sources.py (a THIRD sanctioned
    canonical-writer shape: pure metadata correction, per_skala untouched)
  - one gold-layer (apps/mouth/data/kbli-gold-all.json) value-in-place edit,
    NOT data-plane-guarded, Codex-gated (generator != grader): 56101.whatChanged
    (metadata correction mirror — gold masks intel_2026 on the live page,
    49213/50115 precedent).

REWORK NOTE (2026-07-19, twin-race concession — plan §8 A-10, PENDING-ARMS.md):
the 13-code Lot-2 detach apply (`batch_a_lot2.json`) was CONCEDED to the Pro
lane's PR #2761, already on origin/main, including an upgraded 47771
disposition (status_mapping -> MATCH_CON_AGGREGAZIONE) this M5 lane never
shipped. This file replaces the retired `test_kbli_batch_a_lot2_registry.py`'s
56101-only assertions (that file itself is now MAIN's version, asserting the
twin's 13-detach + 47771 wording — this file does NOT duplicate those). Scope
here is exclusively the 56101 metadata cure, the ONE orthogonal contribution
of PR #2754 that #2761 does not carry.

Cure pattern for 56101 (metadata-only, NOT a detach):
  1. per_skala / per_skala_legacy left COMPLETELY untouched (innocence-
     violation finding, not a contamination finding — the licensing substance
     was independently verified correct)
  2. pp28_sources corrected: ["56101","56104","56103","56109"] ->
     ["56101","56102","56109"]
  3. aggregation_note corrected (credits 56102+56109, drops the false
     56103/56104 claim)
  4. intel_2026.whatChanged corrected
  5. _data_note added (provenance)
  6. status_mapping is NOT touched by this compiler (it writes exactly
     pp28_sources / aggregation_note / intel_2026.whatChanged / _data_note) —
     56101's status_mapping (MATCH_CON_AGGREGAZIONE) is a pre-existing value,
     unrelated to this cure; asserted here only as an innocence pin, never as
     a guilt marker of this compiler's output.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion is paired with an innocence assertion on a legitimate
neighbor/cross-code, and every content marker is a multi-word phrase verified
(direct read of the spec JSON and the served dataset in this session) to
actually appear verbatim in the field it guards.

Innocence scope (twin-race rework, verified this session against the served
dataset — content-pinned, not a live git diff, so this test stays CI-safe and
deterministic):
  - 56101.per_skala rows byte-unchanged (sha256-pinned, 6 rows)
  - 56102 (the only OTHER KBLI-2025 record among the four codes named in the
    56101 provenance correction — 56103/56104/56109 are KBLI-2020-only
    references, never separate KBLI-2025 records in this dataset) untouched
    (full-record sha256-pinned) and 56103/56104/56109 confirmed to still NOT
    exist as spurious KBLI-2025 records (non-existence invariant)
  - the 13 twin-shipped Lot-2 detaches (via PR #2761) untouched by this cure
  - 49213 (Fase-1/pilot cure, PR #2744, now merged to main) untouched
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
META_56101_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/metadata_56101.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# Scope: the two GIT-TRACKED dataset copies only (the backend-rag copies are
# gitignored local sync targets, not part of this PR's diff).
TRACKED_DATASET_COPIES = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # canonical
]
_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in TRACKED_DATASET_COPIES]


def _load_by_code(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["kode_kbli_2025"]: r for r in data["data"] if "kode_kbli_2025" in r}


def _load_record(path: Path, code: str) -> dict[str, Any]:
    rec = _load_by_code(path).get(code)
    if rec is None:
        raise AssertionError(f"{path}: record {code} not found in dataset")
    return rec


def _sha256(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _cure_applied() -> bool:
    """True once the canonical 56101 record shows the post-cure shape. Gates
    the whole module (same convention as the Lot-1/Lot-2 registries)."""
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    if not canonical.exists():
        return False
    try:
        rec = _load_record(canonical, "56101")
    except AssertionError:
        return False
    return rec.get("pp28_sources") == ["56101", "56102", "56109"]


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="56101 metadata cure not yet applied — tests arm after the data PR",
)


# ---------------------------------------------------------------------------
# 1. GUILT — 56101 metadata fields exact per spec, across both tracked copies.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", TRACKED_DATASET_COPIES, ids=_DATASET_IDS)
def test_56101_pp28_sources_corrected(path: Path):
    rec = _load_record(path, "56101")
    assert rec.get("pp28_sources") == ["56101", "56102", "56109"], (
        f"{path}: 56101.pp28_sources expected corrected "
        f"['56101','56102','56109'], got {rec.get('pp28_sources')!r}"
    )


@pytest.mark.parametrize("path", TRACKED_DATASET_COPIES, ids=_DATASET_IDS)
def test_56101_aggregation_note_corrected(path: Path):
    rec = _load_record(path, "56101")
    note = rec.get("aggregation_note", "")
    assert "56102" in note and "56109" in note, (
        f"{path}: 56101.aggregation_note must credit 56102+56109, got {note!r}"
    )
    assert "56103" not in note and "56104" not in note, (
        f"{path}: 56101.aggregation_note must NOT claim 56103/56104, got {note!r}"
    )


@pytest.mark.parametrize("path", TRACKED_DATASET_COPIES, ids=_DATASET_IDS)
def test_56101_data_note_matches_spec_verbatim(path: Path):
    spec = json.loads(META_56101_SPEC_PATH.read_text(encoding="utf-8"))
    rec = _load_record(path, "56101")
    assert rec.get("_data_note") == spec["data_note"], (
        f"{path}: 56101._data_note drifted from "
        "scripts/kbli_filiera/cure_specs/metadata_56101.json — the compiler "
        "must copy data_note verbatim."
    )


@pytest.mark.parametrize("path", TRACKED_DATASET_COPIES, ids=_DATASET_IDS)
def test_56101_whatChanged_corrected(path: Path):
    rec = _load_record(path, "56101")
    what_changed = (rec.get("intel_2026") or {}).get("whatChanged", "")
    assert "56102" in what_changed, (
        f"{path}: 56101.intel_2026.whatChanged must credit KBLI-2020 56102 "
        f"as the true omitted ancestor, got {what_changed!r}"
    )
    spec = json.loads(META_56101_SPEC_PATH.read_text(encoding="utf-8"))
    assert what_changed == spec["whatChanged"], (
        f"{path}: 56101.intel_2026.whatChanged does not match the spec's "
        "corrected text verbatim."
    )


def test_gold_56101_whatChanged_corrected_no_false_ancestor_claim():
    """GUILT: gold 56101.whatChanged must no longer claim 56103/56104 as
    absorbed ancestors, and must credit 56102."""
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rec = gold.get("56101")
    assert rec is not None, "gold 56101: record not found"
    wc = rec.get("whatChanged", "")
    assert "56102" in wc, f"gold 56101.whatChanged must credit 56102, got {wc!r}"
    assert "Previous KBLI 2020 sources: 56101, 56104, 56103" not in wc, (
        f"gold 56101.whatChanged still contains the false pre-cure claim, "
        f"got {wc!r}"
    )


# ---------------------------------------------------------------------------
# 2. Idempotency — compiler dry-run reports already-cured over the served
#    dataset.
# ---------------------------------------------------------------------------

def test_metadata_56101_compiler_dry_run_reports_already_cured():
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_metadata_pp28_sources.py"),
            "--spec",
            str(META_56101_SPEC_PATH),
            "--canonical",
            str(canonical),
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
# 3. INNOCENCE — 56101.per_skala substance completely untouched (the defining
#    property of the metadata-only shape: an innocence-violation finding,
#    never a detach).
# ---------------------------------------------------------------------------

# Hardcoded from a direct read of the served canonical dataset, 2026-07-19
# (post-cure — the cure never touches per_skala, so this IS the pre-cure
# value too): the substance must stay byte-identical going forward.
_56101_PER_SKALA_ROW_COUNT = 6
_56101_PER_SKALA_SHA256 = (
    "6c62b4a635afc19bae19a759a3241ea81884e0493576e95df5c830d199c1e42f"
)


def test_56101_per_skala_completely_untouched_innocence_on_substance():
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(canonical, "56101")
    assert DISPUTED_KEY not in rec, (
        "56101: must NOT carry a per_skala_disputed_* key — this is a "
        "metadata-only innocence-violation cure, never a detach."
    )
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == _56101_PER_SKALA_ROW_COUNT, (
        f"56101: per_skala row count drifted — expected "
        f"{_56101_PER_SKALA_ROW_COUNT}, got "
        f"{len(per_skala) if isinstance(per_skala, list) else per_skala!r}"
    )
    assert _sha256(per_skala) == _56101_PER_SKALA_SHA256, (
        "56101: per_skala content hash drifted from the pinned pre/post-cure "
        "baseline — the metadata-only cure must never touch the substance."
    )


def test_gold_56101_whatYouNeed_untouched():
    """INNOCENCE: 56101's licensing substance (whatYouNeed) was independently
    verified correct — the gold cure must touch ONLY whatChanged, never
    whatYouNeed."""
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rec = gold.get("56101")
    wyn = rec.get("whatYouNeed", "")
    assert "Bupati/Walikota" in wyn and "Gubernur" in wyn, (
        "gold 56101.whatYouNeed: expected the original multi-scale licensing "
        f"steps to remain untouched, got {wyn!r}"
    )


def test_gold_total_record_count_unchanged():
    """INNOCENCE: this cure is a single value-in-place field edit on an
    existing gold record — the gold layer's record count must be unchanged
    (428, per the kbli-navigator skill's established artifact count)."""
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert len(gold) == 428, (
        f"gold record count drifted from 428 to {len(gold)} — the 56101 gold "
        "cure must never add/remove records, only edit an existing field value."
    )


# ---------------------------------------------------------------------------
# 4. INNOCENCE — the four codes named in 56101's provenance correction
#    (56102/56103/56104/56109): only 56102 is an actual KBLI-2025 record in
#    this dataset (56103/56104/56109 are KBLI-2020-only references cited in
#    prose, never separate KBLI-2025 records) — pin both facts.
# ---------------------------------------------------------------------------

_56102_RECORD_SHA256 = (
    "e0f73a3706433d8ad9c2716ad2d8705be79b5a669cb6be5896c862aea8d74c2b"
)


def test_56102_record_untouched():
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(canonical, "56102")
    assert _sha256(rec) == _56102_RECORD_SHA256, (
        "56102: full-record content hash drifted — the 56101 provenance "
        "correction must never mutate the record it re-credits, only 56101's "
        "own pointer/prose fields."
    )


@pytest.mark.parametrize("code", ["56103", "56104", "56109"])
def test_kbli2020_only_codes_still_absent_as_2025_records(code: str):
    """INNOCENCE: 56103/56104/56109 are KBLI-2020 codes referenced only in
    prose/pointer lists (never separate KBLI-2025 records in this dataset).
    The 56101 metadata cure must never spuriously CREATE a record for one of
    these codes."""
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    by_code = _load_by_code(canonical)
    assert code not in by_code, (
        f"{code}: unexpectedly now exists as a KBLI-2025 record — the 56101 "
        "metadata cure must never create new records, only edit 56101's own "
        "fields."
    )


# ---------------------------------------------------------------------------
# 5. INNOCENCE — the 13 Lot-2 detaches (shipped via the twin's PR #2761, now
#    on origin/main) must remain untouched by this cure.
# ---------------------------------------------------------------------------

TWIN_LOT2_DETACH_CODES = [
    "42999", "47771", "49233", "49296", "50113", "52103", "52105", "52211",
    "52219", "52232", "52239", "52299", "59131",
]


@pytest.mark.parametrize("code", TWIN_LOT2_DETACH_CODES)
def test_twin_lot2_detaches_untouched_by_56101_cure(code: str):
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(canonical, code)
    assert rec.get("per_skala") == [], (
        f"{code}: expected still-detached per_skala==[] (shipped via #2761) "
        f"— the 56101 metadata cure must not disturb it."
    )
    assert DISPUTED_KEY in rec, (
        f"{code}: lost its {DISPUTED_KEY!r} audit block — the 56101 metadata "
        "cure must not disturb prior lots' cures."
    )


# ---------------------------------------------------------------------------
# 6. INNOCENCE — 49213 (Fase-1/pilot per-ancestor restore, PR #2744, merged).
# ---------------------------------------------------------------------------

def test_49213_untouched_by_56101_cure():
    canonical = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(canonical, "49213")
    assert rec.get("pp28_sources") == ["49214", "49219", "49413"], (
        "49213: restored pp28_sources drifted — the 56101 metadata cure must "
        f"not disturb PR #2744's per-ancestor restore. Got {rec.get('pp28_sources')!r}"
    )
    assert isinstance(rec.get("per_skala"), list) and len(rec["per_skala"]) == 12, (
        "49213: restored per_skala expected 12 rows (3 ancestors x 4 skala "
        f"tiers), got {rec.get('per_skala')!r}"
    )
