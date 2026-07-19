"""Tests for the Batch-B Phase-0 gate machinery (phase0_gate.py) and the
pure helpers of parse_bps_crosswalk.py.

Pins the §1.4 REV-4b frozen procedures against silent drift:
- the rank-key FORMAT string (digest:lampiran:zero-padded-4 printed page),
- draw determinism + stratum minimums + odd/even rank-parity split,
- edge-identity scoring math (multiset per page, L5/L10 left-right mapping),
- the one-shot holdout latch (a second scoring attempt must be REFUSED),
- freeze-labels validation (page-set equality, 5-digit shape),
- the ISO 2859-1 derivation rule (Ac=0 diagonal + 100%-inspection edge) and
  the spec-frozen Tier-1/Tier-2 seed-list sizes (46 / 16) against the REAL
  canonical (a drift there breaks pre-registration and must fail loudly).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import phase0_gate as gate  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures: synthetic run artifacts in a tmp RUN_DIR/GATE_DIR
# ---------------------------------------------------------------------------

DIGEST = "d" * 64


def synth_census():
    """30 pages per lampiran; wrapped/nm flags patterned so the greedy fill
    has real work to do (not every page satisfies every stratum)."""
    census = []
    for lampiran, first in ((5, 131), (10, 325)):
        for i in range(30):
            pdf_page = first + i
            census.append({
                "pdf_page": pdf_page,
                "printed_page": pdf_page - 14,
                "lampiran": lampiran,
                "n_rows": 3,
                "n_unresolved": 0,
                "n_rules": 5,
                "footer_printed_ok": True,
                "label_row_ok": True,
                "has_continuation_first_band": False,
                "has_wrapped_row": (i % 3 == 0),
                "has_nm_relation": (i % 4 == 0),
                "max_title_lines": 2,
            })
    return census


@pytest.fixture()
def gate_env(tmp_path, monkeypatch):
    run_dir = tmp_path / "bps-crosswalk"
    gate_dir = run_dir / "phase0-gate"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(gate, "RUN_DIR", run_dir)
    monkeypatch.setattr(gate, "GATE_DIR", gate_dir)
    (run_dir / "parser-run-manifest.json").write_text(json.dumps({"parser_run_digest": DIGEST}))
    (run_dir / "page-census.json").write_text(json.dumps(synth_census()))
    (run_dir / "edges-lampiran5.json").write_text("[]")
    (run_dir / "edges-lampiran10.json").write_text("[]")
    return run_dir, gate_dir


# ---------------------------------------------------------------------------
# draw
# ---------------------------------------------------------------------------

def test_rank_key_format_is_frozen(gate_env):
    """The rank key MUST be sha256('<digest>:<lampiran>:<printed 0-padded 4>')
    — REV-4b conductor amendment. A format drift reseeds every future draw."""
    run_dir, gate_dir = gate_env
    assert gate.cmd_draw() == 0
    table = json.loads((gate_dir / "page-rank-table.json").read_text())
    row = next(r for r in table["lampiran"]["5"]["full_rank_table"] if r["pdf_page"] == 131)
    expected = hashlib.sha256(f"{DIGEST}:5:{131 - 14:04d}".encode()).hexdigest()
    assert row["rank_hex"] == expected


def test_draw_deterministic_and_stratified(gate_env):
    run_dir, gate_dir = gate_env
    assert gate.cmd_draw() == 0
    first = (gate_dir / "page-rank-table.json").read_bytes()
    assert gate.cmd_draw() == 0
    assert (gate_dir / "page-rank-table.json").read_bytes() == first  # byte-identical
    table = json.loads(first)
    for lamp in ("5", "10"):
        sel = table["lampiran"][lamp]["selected"]
        assert len(sel) == 10
        assert len({s["pdf_page"] for s in sel}) == 10  # never the same page twice
        assert sum(1 for s in sel if s["wrapped"]) >= 3
        assert sum(1 for s in sel if s["nm"]) >= 3
        # split parity on final rank order
        ordered = sorted(sel, key=lambda s: s["rank_hex"])
        for i, s in enumerate(ordered):
            assert s["split"] == ("tuning" if (i + 1) % 2 == 1 else "holdout")
        assert sum(1 for s in sel if s["split"] == "tuning") == 5


def test_draw_greedy_takes_lowest_ranked_satisfying(gate_env):
    """Phase-1 pages must be the lowest-ranked wrapped pages overall."""
    run_dir, gate_dir = gate_env
    gate.cmd_draw()
    table = json.loads((gate_dir / "page-rank-table.json").read_text())
    for lamp in ("5", "10"):
        full = table["lampiran"][lamp]["full_rank_table"]
        sel = table["lampiran"][lamp]["selected"]
        wrapped_sorted = [r["pdf_page"] for r in sorted(full, key=lambda r: r["rank_hex"]) if r["wrapped"]]
        phase1 = [s["pdf_page"] for s in sel if s.get("phase") == "wrapped>=3"]
        assert set(phase1) <= set(wrapped_sorted[: max(3, len(phase1))])


# ---------------------------------------------------------------------------
# scoring math
# ---------------------------------------------------------------------------

def _install_scoring_fixture(run_dir, gate_dir):
    """1 tuning page per lampiran with hand-computable TP/FP/FN."""
    edges5 = [
        {"kbli_2020": "11111", "kbli_2025": "22222", "pdf_page": 131,
         "sebagian_2020": False, "sebagian_2025": False},
        {"kbli_2020": "33333", "kbli_2025": "44444", "pdf_page": 131,  # FP (not in truth)
         "sebagian_2020": False, "sebagian_2025": False},
    ]
    edges10 = [
        {"kbli_2020": "55555", "kbli_2025": "66666", "pdf_page": 325,
         "sebagian_2020": False, "sebagian_2025": False},
    ]
    (run_dir / "edges-lampiran5.json").write_text(json.dumps(edges5))
    (run_dir / "edges-lampiran10.json").write_text(json.dumps(edges10))
    table = {"lampiran": {
        "5": {"selected": [{"pdf_page": 131, "printed_page": 117, "split": "tuning",
                            "rank_hex": "00", "wrapped": True, "nm": True}]},
        "10": {"selected": [{"pdf_page": 325, "printed_page": 311, "split": "tuning",
                             "rank_hex": "01", "wrapped": True, "nm": True}]},
    }}
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / "page-rank-table.json").write_text(json.dumps(table))
    labels = [
        # L5 truth: 11111->22222 (TP) + 77777->88888 (FN; parser missed it)
        {"lampiran": 5, "pdf_page": 131, "printed_page": 117, "rows": [
            {"left_code": "11111", "right_code": "22222", "sebagian_left": False, "sebagian_right": False},
            {"left_code": "77777", "right_code": "88888", "sebagian_left": False, "sebagian_right": False},
        ]},
        # L10 truth: left=2025, right=2020 -> pair (55555, 66666) in 2020->2025 space (TP)
        {"lampiran": 10, "pdf_page": 325, "printed_page": 311, "rows": [
            {"left_code": "66666", "right_code": "55555", "sebagian_left": False, "sebagian_right": False},
        ]},
    ]
    freeze = {"seat": "test", "labels": labels,
              "labels_sha256": hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()}
    (gate_dir / "truth-labels-frozen.json").write_text(json.dumps(freeze))


def test_score_half_math_and_l10_mapping(gate_env):
    run_dir, gate_dir = gate_env
    _install_scoring_fixture(run_dir, gate_dir)
    res = gate.score_half("tuning")
    assert (res["tp"], res["fp"], res["fn"]) == (2, 1, 1)
    assert res["precision"] == pytest.approx(2 / 3, abs=1e-6)
    assert res["recall"] == pytest.approx(2 / 3, abs=1e-6)


def test_holdout_scored_exactly_once(gate_env):
    run_dir, gate_dir = gate_env
    _install_scoring_fixture(run_dir, gate_dir)
    (gate_dir / "holdout-scores.json").write_text("{}")
    assert gate.cmd_score_holdout() == 2  # REFUSED — the latch holds


def test_freeze_refused_after_holdout(gate_env, tmp_path):
    run_dir, gate_dir = gate_env
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / "holdout-scores.json").write_text("{}")
    labels = tmp_path / "labels.json"
    labels.write_text("[]")
    assert gate.cmd_freeze_labels(labels, "kimi-k3", None) == 2


def test_freeze_validates_page_set(gate_env, tmp_path):
    run_dir, gate_dir = gate_env
    gate.cmd_draw()
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps([]))  # empty != drawn pages
    assert gate.cmd_freeze_labels(labels, "kimi-k3", None) == 2


# ---------------------------------------------------------------------------
# AQL derivation (item 10) — against the REAL canonical
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not gate.CANONICAL_PATH.exists(), reason="canonical not present")
def test_aql_rule_and_frozen_seed_lists(gate_env):
    run_dir, gate_dir = gate_env
    gate_dir.mkdir(parents=True, exist_ok=True)
    # synthetic PASS with zero error
    (gate_dir / "holdout-scores.json").write_text(json.dumps(
        {"verdict": "PASS", "precision": 1.0, "recall": 1.0, "holdout_edge_error_rate": 0.0}))
    (run_dir / "consistency-l5-l10.json").write_text(json.dumps(
        {"in_l5_only": [], "in_l10_only": []}))
    assert gate.cmd_aql() == 0
    out = json.loads((gate_dir / "aql-parameters.json").read_text())
    # spec-frozen seed lists (REV-4b §1.5): a drift here breaks pre-registration
    assert out["tier_census"]["tier1"]["count"] == 46
    assert out["tier_census"]["tier2"]["count"] == 16
    assert out["tier_census"]["tier5"]["count"] == 75
    # zero measured error -> smallest standard AQL class, Ac=0 diagonal plan
    assert out["aql_class_pct"] == 0.010
    assert out["acceptance_number_Ac"] == 0
    assert out["sample_size_n"] == 1250
    assert out["rejection_number_Re"] == 1


def test_gil2_letter_lookup():
    assert next(l for lo, hi, l in gate.GIL2_LETTERS if lo <= 1201 <= hi) == "K"
    assert next(l for lo, hi, l in gate.GIL2_LETTERS if lo <= 1200 <= hi) == "J"


# ---------------------------------------------------------------------------
# parser pure helpers (import guarded — pdfplumber may be absent in CI)
# ---------------------------------------------------------------------------

def test_parser_norm_title_and_lines():
    pytest.importorskip("pdfplumber")
    import parse_bps_crosswalk as p  # noqa: E402

    assert p.norm_title("Kacang- Kacangan") == p.norm_title("Kacang-Kacangan")
    assert p.norm_title("Pertanian  Buah") == p.norm_title("pertanian buah")
    assert p.norm_title("A dan B") != p.norm_title("A Dan C")
    # keep_char drops the Arial watermark, keeps Aptos body
    assert p.keep_char({"object_type": "char", "fontname": "GZJQED+Arial-BoldMT"}) is False
    assert p.keep_char({"object_type": "char", "fontname": "AAAAAL+Aptos"}) is True
    assert p.keep_char({"object_type": "rect"}) is True
    words = [
        {"text": "b", "top": 10.0, "x0": 20.0},
        {"text": "a", "top": 10.5, "x0": 10.0},
        {"text": "c", "top": 14.0, "x0": 10.0},
    ]
    assert p.cell_text(words) == "a b c"
