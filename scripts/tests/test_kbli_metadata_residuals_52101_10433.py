"""Regression registry — GARUDA-FILIERA metadata-residuals micro-fix
(2026-07-19, M5 lane): closes 2 field-vs-note contradictions left on main by
PR #2777 (the 46100/52101/10433 standalone metadata-fix trio, itself the
PR #2753 residual scope).

Driven by scripts/kbli_filiera/cure_specs/metadata_residuals_2026_07_19.json
and applied via scripts/kbli_filiera/cure_canonical_collisions.py --spec
metadata_residuals_2026_07_19.json --only 52101 10433. Uses the SAME
compiler and the SAME "action": "metadata_only" entry-type #2777 already
shipped and tested — zero compiler extension needed for this fix. Does NOT
modify #2777's own merged spec (metadata_fixes_2026_07_19.json) — this is a
separate, additive spec whose data_note APPENDS to (never erases) that
spec's original text.

THE TWO CONTRADICTIONS (both verified live on main BEFORE this fix, both
already flagged as "known follow-up, not silently left undocumented" inside
#2777's own _data_note prose):

  1. 52101 — the record's own _data_note/whatChanged already correctly named
     the true five-parent BPS crosswalk merge (KBLI-2020 03143/03241/03243/
     03263/52108 -> KBLI-2025 52101), but pp28_sources was still the false
     same-digit self-reference ['52101']. Corrected here to the true
     5-parent list.
  2. 10433 — pp28_sources was already correctly shrunk to ['10433'] by
     #2777 (10490 removed, correctly re-attributed to 10419), but
     status_mapping remained 'MATCH_CON_AGGREGAZIONE' and whatChanged still
     said "match con aggregazione" despite there being only a single true
     ancestor left. Corrected here to 'MATCH_LANGSUNG' + a clean 1:1
     narrative.

CONVENTION RULING (conductor comment on PR #2777, 2026-07-19, posted by
Balizero1987/owner): both are FALSITY in the field (not incompleteness) —
the record's own note already stated the truth the field contradicted — so
each is corrected using the SAME already-image-verified BPS Lampiran
citation the pre-existing _data_note already cites (52101: BPS Vol.2
Lampiran 10 p.403/printed-389; 10433: p.340/printed-326), not a fresh
independent PP28-corpus hunt. Same class as the #2754/56101 precedent.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion (the 2 codes ARE corrected) is paired with an
innocence assertion — the full-dataset diff-vs-origin/main check, the
per-code byte-identical controls, and the disputed-key-set-unchanged sweep.

Scar W88 discipline: the diff-vs-origin/main innocence check below uses
SUBSET comparison (changed ⊆ {"52101","10433"}), never strict equality —
equality is structurally unsatisfiable once this PR itself merges (main==
main gives an empty diff), so subset degrades gracefully post-merge instead
of rotting permanently red.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RESIDUALS_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/metadata_residuals_2026_07_19.json"
ORIGINAL_TRIO_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/metadata_fixes_2026_07_19.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
CANONICAL_REL = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- dataset copies (pattern shared with test_kbli_metadata_fixes_registry.py) ---

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


def _load_spec_entries(spec_path: Path) -> dict[str, dict[str, Any]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return {e["code"]: e for e in spec["codes"]}


def _git_show_by_code(ref: str, rel_path: str) -> dict[str, dict[str, Any]]:
    out = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    data = json.loads(out)
    return {r["kode_kbli_2025"]: r for r in data["data"] if "kode_kbli_2025" in r}


_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]

RESIDUAL_CODES = ["52101", "10433"]

# ---------------------------------------------------------------------------
# 1. GUILT — 52101: pp28_sources corrected, status_mapping UNCHANGED.
# ---------------------------------------------------------------------------

EXPECTED_52101_PP28_SOURCES = ["03143", "03241", "03243", "03263", "52108"]


def test_52101_pp28_sources_corrected_on_all_copies():
    spec_entries = _load_spec_entries(RESIDUALS_SPEC_PATH)
    assert spec_entries["52101"]["pp28_sources_correction"] == EXPECTED_52101_PP28_SOURCES
    for path in _existing_dataset_copies():
        rec = _load_record(path, "52101")
        assert rec.get("pp28_sources") == EXPECTED_52101_PP28_SOURCES, (
            f"{path}: 52101.pp28_sources is {rec.get('pp28_sources')!r}, expected the "
            f"true 5-parent BPS crosswalk list {EXPECTED_52101_PP28_SOURCES!r} — the false "
            "same-digit self-reference ['52101'] must not survive."
        )


def test_52101_status_mapping_survives_unchanged():
    """52101's residual fix touches whatChanged + pp28_sources only —
    status_mapping was ALREADY correct from #2777 (MATCH_CON_AGGREGAZIONE)
    and must not be re-touched here."""
    for path in _existing_dataset_copies():
        rec = _load_record(path, "52101")
        assert rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE", (
            f"{path}: 52101.status_mapping drifted from the untouched "
            f"pre-residual-fix value — got {rec.get('status_mapping')!r}."
        )


def test_52101_whatchanged_no_longer_claims_pp28_sources_unchanged():
    """The specific stale claim this residual fix removes: #2777's original
    whatChanged closed with 'pp28_sources REMAINS [\"52101\"] UNCHANGED' — that
    exact claim must no longer be asserted as current truth now that
    pp28_sources has itself been corrected."""
    rec = _load_record(CANONICAL_PATH, "52101")
    what_changed = (rec.get("intel_2026") or {}).get("whatChanged", "")
    assert "pp28_sources remains" not in what_changed.lower(), (
        f"52101: whatChanged still asserts pp28_sources 'remains' unchanged — stale "
        f"claim survived the residual fix: {what_changed!r}"
    )
    for parent in EXPECTED_52101_PP28_SOURCES:
        assert parent in what_changed, (
            f"52101: whatChanged missing true parent {parent!r} — {what_changed!r}"
        )


# ---------------------------------------------------------------------------
# 2. GUILT — 10433: status_mapping + whatChanged corrected, pp28_sources
#    UNCHANGED.
# ---------------------------------------------------------------------------


def test_10433_status_mapping_corrected_to_match_langsung_on_all_copies():
    spec_entries = _load_spec_entries(RESIDUALS_SPEC_PATH)
    assert spec_entries["10433"]["status_mapping_correction"] == "MATCH_LANGSUNG"
    for path in _existing_dataset_copies():
        rec = _load_record(path, "10433")
        assert rec.get("status_mapping") == "MATCH_LANGSUNG", (
            f"{path}: 10433.status_mapping is {rec.get('status_mapping')!r}, expected "
            "'MATCH_LANGSUNG' — the stale merge-aware label must not survive now that "
            "10490 is correctly attributed to 10419, not 10433."
        )


def test_10433_pp28_sources_survives_unchanged():
    """10433's residual fix touches status_mapping + whatChanged only —
    pp28_sources was ALREADY correct from #2777 (['10433'], 10490 removed)
    and must not be re-touched here."""
    for path in _existing_dataset_copies():
        rec = _load_record(path, "10433")
        assert rec.get("pp28_sources") == ["10433"], (
            f"{path}: 10433.pp28_sources drifted from the untouched "
            f"pre-residual-fix value — got {rec.get('pp28_sources')!r}."
        )


def test_10433_whatchanged_is_clean_1to1_narrative():
    rec = _load_record(CANONICAL_PATH, "10433")
    what_changed = (rec.get("intel_2026") or {}).get("whatChanged", "")
    assert what_changed != "KBLI 2020→2025 mapping: match con aggregazione.", (
        "10433: whatChanged still reads the stale pre-residual-fix text."
    )
    assert "10433->10433" in what_changed or "10433" in what_changed, (
        f"10433: whatChanged missing the 1:1 continuation narrative — {what_changed!r}"
    )
    assert "10490" in what_changed, (
        f"10433: whatChanged should explain the 10490 re-attribution — {what_changed!r}"
    )


# ---------------------------------------------------------------------------
# 3. GUILT — _data_note APPENDS to (never erases) #2777's original note.
# ---------------------------------------------------------------------------


def test_data_note_appends_to_original_trio_note_never_erases():
    original_entries = _load_spec_entries(ORIGINAL_TRIO_SPEC_PATH)
    residual_entries = _load_spec_entries(RESIDUALS_SPEC_PATH)
    for code in RESIDUAL_CODES:
        original_note = original_entries[code]["data_note"]
        residual_note = residual_entries[code]["data_note"]
        assert residual_note.startswith(original_note), (
            f"{code}: the residual spec's data_note does not START WITH #2777's "
            "original note — team convention requires APPEND, never erase, "
            "the pre-existing conductor-gate evidence trail."
        )
        assert "RESIDUAL FIX" in residual_note, (
            f"{code}: residual spec's data_note is missing a 'RESIDUAL FIX' marker "
            "paragraph."
        )


def test_canonical_data_note_matches_residual_spec_verbatim():
    residual_entries = _load_spec_entries(RESIDUALS_SPEC_PATH)
    for code in RESIDUAL_CODES:
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("_data_note") == residual_entries[code]["data_note"], (
            f"{code}: canonical _data_note drifted from "
            "metadata_residuals_2026_07_19.json — the compiler must copy data_note "
            "verbatim."
        )


# ---------------------------------------------------------------------------
# 4. GUILT/INNOCENCE combined — per_skala byte-invariant, no disputed key,
#    aggregation_note left untouched (documented stale/None — not this
#    compiler's field).
# ---------------------------------------------------------------------------

PRE_CURE_PER_SKALA_ROW_COUNT = {"52101": 8, "10433": 4}


def test_per_skala_row_count_and_no_disputed_key():
    for code in RESIDUAL_CODES:
        for path in _existing_dataset_copies():
            rec = _load_record(path, code)
            per_skala = rec.get("per_skala")
            assert isinstance(per_skala, list) and len(per_skala) == PRE_CURE_PER_SKALA_ROW_COUNT[code], (
                f"{path}: {code}.per_skala row count drifted — expected "
                f"{PRE_CURE_PER_SKALA_ROW_COUNT[code]}, got {per_skala!r}"
            )
            assert DISPUTED_KEY not in rec, (
                f"{path}: {code} unexpectedly carries {DISPUTED_KEY!r} — this "
                "metadata_only residual fix must never detach a healthy per_skala."
            )


def test_aggregation_note_left_untouched_documented_stale():
    """cure_canonical_collisions.py's metadata_only action never writes
    aggregation_note — confirm this residual fix did not silently start
    doing so, matching the documented 'known follow-up' in both spec
    entries' aggregation_note_flag key."""
    rec_52101 = _load_record(CANONICAL_PATH, "52101")
    assert rec_52101.get("aggregation_note") is None
    rec_10433 = _load_record(CANONICAL_PATH, "10433")
    assert rec_10433.get("aggregation_note") == "Dati da 10433 + 1 codici figli PP28", (
        "10433: aggregation_note changed — this residual fix does not write that "
        "field; if it changed, something else touched this record."
    )


# ---------------------------------------------------------------------------
# 5. INNOCENCE — diff vs origin/main is a SUBSET of {52101, 10433} (scar W88:
#    never strict equality — that's structurally unsatisfiable once this PR
#    merges, since main==main gives an empty diff).
# ---------------------------------------------------------------------------


def test_canonical_diff_vs_origin_main_is_subset_of_residual_codes():
    main_by_code = _git_show_by_code("origin/main", CANONICAL_REL)
    disk_by_code = _load_by_code(REPO_ROOT / CANONICAL_REL)
    assert set(main_by_code.keys()) == set(disk_by_code.keys()), (
        "record set (code membership) drifted vs origin/main — this fix must "
        "never add/remove records."
    )
    changed = {code for code in main_by_code if main_by_code[code] != disk_by_code[code]}
    assert changed <= set(RESIDUAL_CODES), (
        f"canonical diff vs origin/main touches {sorted(changed - set(RESIDUAL_CODES))} "
        f"beyond the intended {RESIDUAL_CODES} — scope leak."
    )


def test_disputed_key_membership_set_unchanged_vs_origin_main():
    """Whole-dataset sweep (not just the 2 target codes): the set of records
    carrying per_skala_disputed_pp28_collision must be byte-identical to
    origin/main — proves this metadata_only residual fix never triggered a
    detach anywhere in the dataset, not only on 52101/10433."""
    main_by_code = _git_show_by_code("origin/main", CANONICAL_REL)
    disk_by_code = _load_by_code(REPO_ROOT / CANONICAL_REL)
    main_disputed = {c for c, r in main_by_code.items() if DISPUTED_KEY in r}
    disk_disputed = {c for c, r in disk_by_code.items() if DISPUTED_KEY in r}
    assert main_disputed == disk_disputed, (
        f"disputed-key membership changed vs origin/main: "
        f"+{sorted(disk_disputed - main_disputed)} -{sorted(main_disputed - disk_disputed)}"
    )


# ---------------------------------------------------------------------------
# 6. INNOCENCE — named neighbor/control codes byte-identical vs origin/main.
# ---------------------------------------------------------------------------

INNOCENT_CONTROLS = ["46100", "56101", "49213", "10419"]


def test_innocent_controls_byte_identical_vs_origin_main():
    """46100 (fully conformant from #2777, no residual needed), 56101 (Lot 2's
    own standalone metadata-only cure), 49213 (long-standing per-ancestor
    control cited across the program), 10419 (the innocence control the
    10433 finding is built on — legitimately owns 10490 as its ancestor)."""
    main_by_code = _git_show_by_code("origin/main", CANONICAL_REL)
    disk_by_code = _load_by_code(REPO_ROOT / CANONICAL_REL)
    for code in INNOCENT_CONTROLS:
        assert main_by_code[code] == disk_by_code[code], (
            f"{code}: unexpectedly diverged from origin/main — this residual fix "
            "must not touch this control code."
        )


# ---------------------------------------------------------------------------
# 7. Sync — all existing dataset copies byte-identical to each other.
# ---------------------------------------------------------------------------


def test_all_dataset_copies_byte_identical():
    copies = _existing_dataset_copies()
    assert len(copies) >= 2, "expected at least the tracked canonical + production copies to exist"
    reference = copies[0].read_bytes()
    for path in copies[1:]:
        assert path.read_bytes() == reference, (
            f"{path} is not byte-identical to {copies[0]} — run scripts/sync_kbli_dataset.sh"
        )


# ---------------------------------------------------------------------------
# 8. Idempotency — re-running the residual spec reports both codes already
#    cured (no-op).
# ---------------------------------------------------------------------------


def test_residual_spec_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(RESIDUALS_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run should exit 0, got {result.returncode}. "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in RESIDUAL_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 9. Spec shape sanity — both entries are metadata_only, disputed_key is the
#    shared program-wide constant.
# ---------------------------------------------------------------------------


def test_spec_disputed_key_matches_program_constant():
    spec = json.loads(RESIDUALS_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY


def test_both_entries_are_metadata_only_action():
    spec_entries = _load_spec_entries(RESIDUALS_SPEC_PATH)
    for code in RESIDUAL_CODES:
        assert spec_entries[code].get("action") == "metadata_only", (
            f"{code}: spec entry must carry 'action': 'metadata_only' — without it, "
            "the compiler would detach this code's healthy per_skala."
        )
