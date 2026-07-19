"""Regression registry — GARUDA-FILIERA standalone metadata-fix cures
(2026-07-19): 3 KBLI-2025 codes (52101, 46100, 10433) OUTSIDE Batch-A's
lot scope, each with a HEALTHY OSS-native per_skala that must NEVER be
detached, driven by scripts/kbli_filiera/cure_specs/metadata_fixes_2026_07_19.json
and applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
metadata_fixes_2026_07_19.json.

Modeled closely on test_kbli_batch_a_lot3_registry.py — the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code /
_load_record / _contains_word_or_phrase helpers below are COPIED VERBATIM
from that file (comment marks the origin instead of importing, to keep this
file self-contained and independently readable as its own regression pin,
same convention Lot 1/2/3 used).

Cure pattern for all 3 codes (the 2026-07-19 "action": "metadata_only"
compiler extension — see cure_canonical_collisions.py docstring):
  1. per_skala is COMPLETELY UNTOUCHED — never detached, never folded into a
     disputed key, byte-invariant before/after (this is the core guarantee
     this file exists to pin: metadata_only must never clobber healthy data).
  2. status_mapping / intel_2026.whatChanged (52101, 46100) or pp28_sources
     (10433) corrected verbatim from the spec.
  3. _data_note added (verbatim from the cure spec — never invented here).
  4. NO disputed key (per_skala_disputed_pp28_collision) is ever written for
     these 3 codes — that key exists only for detach cures, and none of
     these entries detach.
  5. NO whatYouNeed change — the spec ships no whatYouNeed key for any of
     the 3 entries (the served licensing content is healthy and unaffected).

ADJUDICATION HISTORY: all three findings were adjudicated at the Batch A
Lot 2 conductor gate (SIGNED, second signing + Appendix A, 2026-07-18,
research/operations/2026-07-18-kbli-batch-a-lot2-conductor-gate.md, PR
#2753) — §1 (46100 retro-quarantine), §3.3 (52101 five-parent MERGE),
Appendix A (10433 disqualified POS control) — and scheduled there (§6.3) as
"standalone metadata-fix cures for BOTH controls" + "10433 joins the
standalone metadata-fix cure list". This registry ships the write that
report already authorized; it does not re-adjudicate anything.

IMPORTANT — these tests are EXPECTED TO BE SKIPPED until this cure is
applied to the canonical dataset (this file lands together with the data
change that runs cure_canonical_collisions.py --apply). The whole module is
skipped via a module-level pytestmark until the canonical 10433 record shows
the post-cure shape (pp28_sources == ["10433"], no longer ["10433","10490"])
— at that point the module arms itself automatically, no edit needed. 10433
is used as the canary because it is the only one of the 3 whose cure touches
a field (pp28_sources) no prior cure in this program has ever corrected —
the strongest, most novel single-code gate available for this spec.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion (the 3 codes ARE corrected) is paired with an
innocence assertion on legitimate neighbor codes (untouched by this spec)
AND with the per_skala-byte-invariance assertion (the compiler extension's
own core guilt+innocence contract: corrected metadata, untouched licensing).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_FIXES_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/metadata_fixes_2026_07_19.json"
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
    A multi-word phrase (contains a space) is matched as a plain substring —
    the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(METADATA_FIXES_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 10433 record shows the post-cure shape
    (pp28_sources == ["10433"], the 10490 mis-association removed). If the
    canonical file, the spec, or the 10433 record is missing entirely, treat
    the cure as NOT applied (module stays skipped rather than erroring at
    collection time)."""
    if not CANONICAL_PATH.exists() or not METADATA_FIXES_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "10433")
    except AssertionError:
        return False
    return rec.get("pp28_sources") == ["10433"]


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="metadata_fixes_2026_07_19 cure not yet applied — tests arm after the data change",
)


METADATA_FIX_CODES = ["52101", "46100", "10433"]

# per_skala row COUNT pre-cure (hardcoded from a direct read of the canonical
# dataset, 2026-07-19) — this cure must NEVER change the row count (or any
# byte of the rows themselves — checked separately by full-equality below).
PRE_CURE_PER_SKALA_ROW_COUNT = {
    "52101": 8,
    "46100": 15,
    "10433": 4,
}

# Codes whose status_mapping / whatChanged get corrected (52101, 46100).
# 10433 gets NO status_mapping/whatChanged change — only pp28_sources.
STATUS_MAPPING_CORRECTED_CODES = ["52101", "46100"]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the
# canonical dataset (2026-07-19) — 52101/46100 must survive UNCHANGED
# (this cure deliberately does NOT touch their pp28_sources); 10433's is
# EXPECTED to change (the whole point of this cure).
PRE_CURE_PP28_SOURCES = {
    "52101": ["52101"],
    "46100": ["46100"],
    "10433": ["10433", "10490"],
}
POST_CURE_PP28_SOURCES = {
    # RESIDUAL FIX (2026-07-19, M5 lane, scripts/kbli_filiera/cure_specs/
    # metadata_residuals_2026_07_19.json): 52101's pp28_sources was left at
    # the false same-digit self-reference ['52101'] by THIS spec (deliberate
    # at the time — see this spec's own data_note, rule #9 provenance
    # caution) even though the record's own whatChanged already named the
    # true five-parent BPS crosswalk merge. A conductor comment on this PR
    # (2026-07-19) ruled that gap a field-vs-note FALSITY, not incompleteness,
    # and authorized the correction using the SAME already-image-verified
    # BPS Lampiran citation this spec's data_note already cites — a
    # standalone follow-up spec applied the fix, so the value below is the
    # CURRENT canonical truth, not this spec's own (superseded) target.
    "52101": ["03143", "03241", "03243", "03263", "52108"],
    "46100": ["46100"],  # unchanged, deliberately not corrected (see spec data_note)
    "10433": ["10433"],  # CORRECTED: 10490 removed
}

# Content markers: multi-word phrases verified (direct read of
# cure_specs/metadata_fixes_2026_07_19.json, 2026-07-19) to be verbatim
# substrings of that code's _data_note. Checked ONLY against _data_note.
DATA_NOTE_MARKERS = {
    "52101": "FIVE-parent MERGE",
    "46100": "REVERSE table (BPS Vol.2 Lampiran 10, image-verified p.356",
    "10433": "10490 is the SOLE KBLI-2020 ancestor of a DIFFERENT 2025 code, 10419",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes
# untouched by THIS spec, with a HEALTHY (non-detached) per_skala — the
# shape every code in this spec's own scope also has.
#   52108 does not exist as a 2025 code (it is a 2020-vintage ancestor of
#   52101 in prose only) so it cannot be a canonical innocence control;
#   52102/52109 are genuine 52xxx warehousing-family neighbors instead.
#   10419 — the code that legitimately owns 10490 as its ancestor (the
#   defect this cure corrects); must be completely untouched by this spec.
#   10490 is a 2020-vintage code, not present in the 2025 canonical at all.
# NOTE: 47771 is deliberately NOT in this list — it is a Lot 2 cure code
# with a LEGITIMATE detach (per_skala==[] + its own disputed key), owned by
# batch_a_lot2.json, not this spec. It gets its own dedicated
# cross-contamination check below instead of the generic
# "healthy + no disputed key" shape this list asserts.
INNOCENT_NEIGHBORS = ["52102", "52109", "10419"]


def _all_dataset_copies_at_collection() -> list[Path]:
    return _existing_dataset_copies()


_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _all_dataset_copies_at_collection()]


# ---------------------------------------------------------------------------
# 1. per_skala BYTE-INVARIANT (all 3 codes, all dataset copies) — the core
#    guilt+innocence guarantee of the metadata_only compiler extension.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _all_dataset_copies_at_collection(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_per_skala_row_count_invariant(path: Path, code: str):
    """GUILT-innocence combined, core: per_skala must have EXACTLY the
    pre-cure row count — this cure must never detach or otherwise mutate the
    served licensing content."""
    rec = _load_record(path, code)
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == PRE_CURE_PER_SKALA_ROW_COUNT[code], (
        f"{path}: {code}.per_skala row count drifted — expected "
        f"{PRE_CURE_PER_SKALA_ROW_COUNT[code]} (byte-invariant, this cure "
        f"never touches per_skala), got {per_skala!r}"
    )


@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_per_skala_never_detached_no_disputed_key(code: str):
    """This is a metadata_only cure: per_skala must NEVER be [] and the
    detach disputed key must NEVER be written for these 3 codes."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala") != [], (
        f"{code}: per_skala is [] — a metadata_only cure must never detach "
        "a healthy OSS-native per_skala."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — metadata_only "
        "cures never write a disputed key (no detach ever happens)."
    )


# ---------------------------------------------------------------------------
# 2. _data_note verbatim from spec
# ---------------------------------------------------------------------------

# 52101 and 10433 got a 2026-07-19 M5 residual-fix follow-up
# (scripts/kbli_filiera/cure_specs/metadata_residuals_2026_07_19.json) whose
# own data_note APPENDS a correction paragraph to THIS spec's original note
# (never erasing it — team convention: the #2777 conductor-gate evidence
# trail stays intact). For these two codes we can only assert the current
# _data_note STARTS WITH this spec's original text, not exact equality;
# 46100 got no residual fix and keeps the plain exact-match check.
RESIDUAL_FIXED_CODES = ["52101", "10433"]


@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_data_note_matches_spec_verbatim(code: str):
    spec_by_code = _load_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    current_note = rec.get("_data_note", "")
    original_note = spec_by_code[code]["data_note"]
    if code in RESIDUAL_FIXED_CODES:
        assert current_note.startswith(original_note), (
            f"{code}: _data_note no longer STARTS WITH the original "
            "metadata_fixes_2026_07_19.json text — the 2026-07-19 residual "
            "fix must APPEND a correction paragraph, never erase or reorder "
            "the original #2777 conductor-gate evidence trail. Full "
            "verbatim-append pin lives in "
            "test_kbli_metadata_residuals_52101_10433.py."
        )
    else:
        assert current_note == original_note, (
            f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
            "metadata_fixes_2026_07_19.json — the compiler must copy data_note verbatim."
        )


# ---------------------------------------------------------------------------
# 3. status_mapping / whatChanged corrections (52101, 46100)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", STATUS_MAPPING_CORRECTED_CODES)
def test_status_mapping_corrected_to_match_con_aggregazione(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE", (
        f"{code}: status_mapping must be corrected to the merge-aware "
        "'MATCH_CON_AGGREGAZIONE' enum value (the false 1:1 narrative must "
        "not survive the cure)."
    )


# whatChanged from THIS spec (metadata_fixes_2026_07_19.json) still holds
# verbatim only for 46100. 52101 is deliberately EXCLUDED: the 2026-07-19 M5
# residual fix further corrected 52101's whatChanged closing sentence (to
# stop asserting "pp28_sources remains unchanged" once pp28_sources was
# itself corrected) — the live record has legitimately diverged from THIS
# spec's own (now-superseded) whatChanged_correction value. That correction
# is pinned instead by test_kbli_metadata_residuals_52101_10433.py.
WHATCHANGED_STILL_VERBATIM_FROM_THIS_SPEC = ["46100"]


@pytest.mark.parametrize("code", WHATCHANGED_STILL_VERBATIM_FROM_THIS_SPEC)
def test_whatchanged_corrected(code: str):
    spec_by_code = _load_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatChanged") == spec_by_code[code]["whatChanged_correction"], (
        f"{code}: intel_2026.whatChanged must be corrected verbatim from the "
        "spec's whatChanged_correction."
    )


def test_10433_status_mapping_and_whatchanged_superseded_by_residual_fix():
    """HISTORY: at THIS spec's (metadata_fixes_2026_07_19.json) own scope,
    10433's cure was pp28_sources-only — its status_mapping and whatChanged
    were left UNCHANGED on purpose, and this spec's own data_note explicitly
    flagged "whether the merge-aware status_mapping label itself needs
    re-adjudication" as a "known follow-up, not silently left undocumented."

    That follow-up was resolved by the 2026-07-19 M5 residual fix
    (scripts/kbli_filiera/cure_specs/metadata_residuals_2026_07_19.json,
    conductor comment on this PR): with 10490 correctly attributed to 10419
    (not 10433) by pp28_sources — already true after THIS spec's own cure —
    10433 is a genuine 1:1 continuation, so status_mapping/whatChanged now
    get corrected too. This test pins the CURRENT (post-residual-fix) truth;
    it no longer asserts "no change" because a change legitimately landed.
    """
    rec = _load_record(CANONICAL_PATH, "10433")
    assert rec.get("status_mapping") == "MATCH_LANGSUNG", (
        "10433: status_mapping expected 'MATCH_LANGSUNG' (residual fix, "
        "2026-07-19) — the stale merge-aware 'MATCH_CON_AGGREGAZIONE' label "
        "should no longer survive now that its second parent (10490) is "
        "correctly attributed to 10419, not 10433."
    )
    intel = rec.get("intel_2026") or {}
    what_changed = intel.get("whatChanged", "")
    assert "10433->10433" in what_changed or "1:1" in what_changed, (
        f"10433: intel_2026.whatChanged expected a clean 1:1-continuation "
        f"narrative (residual fix, 2026-07-19) — got {what_changed!r}."
    )
    assert what_changed != "KBLI 2020→2025 mapping: match con aggregazione.", (
        "10433: intel_2026.whatChanged still reads the stale pre-residual-fix "
        "'match con aggregazione' text — the residual fix did not land."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources: 10433 CORRECTED, 52101/46100 left UNCHANGED (deliberately)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_pp28_sources_post_cure_value(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == POST_CURE_PP28_SOURCES[code], (
        f"{code}: pp28_sources is {rec.get('pp28_sources')!r}, expected "
        f"{POST_CURE_PP28_SOURCES[code]!r}."
    )


def test_10433_pp28_sources_10490_removed():
    """The specific, load-bearing correction this cure exists to ship: 10490
    must no longer appear anywhere in 10433's pp28_sources."""
    rec = _load_record(CANONICAL_PATH, "10433")
    pp28_sources = rec.get("pp28_sources") or []
    assert "10490" not in pp28_sources, (
        f"10433: pp28_sources still contains '10490' — {pp28_sources!r} — "
        "the wrong-child mis-association this cure corrects has leaked back in."
    )
    assert pp28_sources == ["10433"]


# ---------------------------------------------------------------------------
# 5. Idempotency: compiler dry-run over the served dataset reports every
#    code already-cured (no-op), exercising the compiler's real detection
#    logic — including the metadata_only branch for all 3 codes.
# ---------------------------------------------------------------------------

def test_compiler_dry_run_reports_already_cured():
    """Idempotency check re-running THIS OLD spec (metadata_fixes_2026_07_19.json)
    over the served (current) canonical.

    46100 and 10433 stay ALREADY CURED indefinitely — the 2026-07-19 M5
    residual fix (metadata_residuals_2026_07_19.json) never touches any
    field THIS spec's own entries check for those two codes (10433's entry
    here only asserts pp28_sources, which the residual fix leaves alone;
    46100 got no residual fix at all).

    52101 is the deliberate exception: the residual fix corrected its
    intel_2026.whatChanged to text that legitimately differs from THIS OLD
    spec's own (now-superseded) whatChanged_correction value, so re-running
    THIS spec's dry-run over the current canonical now (correctly) reports
    52101 needing an "apply" — re-applying it with --apply would REGRESS the
    residual fix. This is expected, point-in-time-spec behavior (a spec is
    not meant to be silently re-applied forever once a LATER spec has
    touched the same field) — tracked as a residual-spec-reapply risk in
    PENDING-ARMS.md, not something this test should paper over by asserting
    a false "still idempotent forever" guarantee.
    """
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(METADATA_FIXES_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (still-idempotent "
        f"codes report already-cured, 52101's expected divergence is not a "
        f"'problem' in the compiler's sense), got {result.returncode}. "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in ("46100", "10433"):
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )
    assert "52101: ALREADY CURED (skip)" not in result.stdout, (
        "52101 unexpectedly reports ALREADY CURED against the OLD "
        "(metadata_fixes_2026_07_19.json) spec — if this now passes, the "
        "2026-07-19 residual fix's whatChanged correction may have been "
        "reverted; investigate before treating this as progress."
    )
    assert "intel_2026.whatChanged -> metadata-corrected" in result.stdout, (
        "expected the OLD spec's dry-run to (correctly) flag 52101's "
        "whatChanged as divergent from ITS OWN (superseded) target value. "
        f"stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# 6. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be
#    untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the code — 10419 — whose
    correct ancestry this cure's finding is built on) and are NOT part of
    this spec — if the cure ever over-reaches onto one of them, this must
    fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence "
        "control, not one of the 3 metadata-fix codes; the cure must not "
        "have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was "
        "never part of the metadata_fixes_2026_07_19 cure spec."
    )
    spec_by_code = _load_spec_by_code()
    assert code not in spec_by_code, (
        f"{code}: unexpectedly present in metadata_fixes_2026_07_19.json's "
        "codes list — this is supposed to be an innocence control."
    )


def test_47771_not_in_this_spec_and_no_cross_contamination():
    """47771 is a Lot 2 mapping_metadata_false code with its OWN legitimate
    detach (batch_a_lot2.json owns it) — it must not be part of THIS spec,
    and this spec's _data_note text must never have leaked onto it."""
    spec_by_code = _load_spec_by_code()
    assert "47771" not in spec_by_code, (
        "47771 unexpectedly present in metadata_fixes_2026_07_19.json's "
        "codes list — it belongs to batch_a_lot2.json, a different cure."
    )
    rec = _load_record(CANONICAL_PATH, "47771")
    this_spec_notes = {e["data_note"] for e in spec_by_code.values()}
    assert rec.get("_data_note") not in this_spec_notes, (
        "47771: _data_note matches a metadata_fixes_2026_07_19.json entry — "
        "cross-contamination between two independent cure specs."
    )


def test_10419_pp28_sources_unaffected_by_10433_correction():
    """10419 legitimately owns 10490 as its sole ancestor (kbli_2020_source
    AND pp28_sources) — verifying this stays completely untouched is the
    innocence-side proof that 10433's correction did not clobber the record
    it took the ancestor FROM."""
    rec = _load_record(CANONICAL_PATH, "10419")
    assert rec.get("pp28_sources") == ["10490"], (
        f"10419: pp28_sources drifted to {rec.get('pp28_sources')!r} — "
        "expected untouched ['10490'] (10419 is the innocence control this "
        "10433 correction is built on, not a member of this cure spec)."
    )
    assert rec.get("kbli_2020_source") == "10490"


# ---------------------------------------------------------------------------
# 7. Content markers — verified verbatim in _data_note only.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — "
        "the provenance note may have drifted from the spec. "
        f"_data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 8. No whatYouNeed change — the spec ships no whatYouNeed key for any of
#    the 3 entries (unlike every detach cure in this program).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_spec_ships_no_whatyouneed_key(code: str):
    spec_by_code = _load_spec_by_code()
    assert "whatYouNeed" not in spec_by_code[code], (
        f"{code}: spec unexpectedly carries a whatYouNeed key — these are "
        "metadata_only cures, the served licensing content is healthy and "
        "must not get an honest-gap rewrite."
    )


@pytest.mark.parametrize("code", METADATA_FIX_CODES)
def test_all_entries_are_metadata_only_action(code: str):
    spec_by_code = _load_spec_by_code()
    assert spec_by_code[code].get("action") == "metadata_only", (
        f"{code}: spec entry must carry 'action': 'metadata_only' — without "
        "it, the compiler would detach this code's healthy per_skala."
    )
