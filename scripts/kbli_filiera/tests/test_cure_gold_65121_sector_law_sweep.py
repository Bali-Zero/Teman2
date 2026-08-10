"""Guilt and innocence for the 65121 capital-figure sweep (item 2 of the
2026-08-08 sector-law brief): NO capital figures anywhere in cards without a
verified primary source (POJK 23/2023 was never primary-fetched).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_gold_65121_sector_law_sweep as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "gold_65121_sector_law_sweep_2026_08_08.json"
    ).read_text(encoding="utf-8")
)

CAPITAL_NEEDLES = ["IDR 100", "IDR 10B", "100 billion", "10 billion"]


def _gold_file(tmp_path, gold):
    p = tmp_path / "gold.json"
    p.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _base_gold():
    return {
        "65121": {
            "zantaraOpener": (
                "Establishing a general insurance company in Bali? 65121 is "
                "the code, but the reality is tough: IDR 100 billion "
                "capital, 12–24 month OJK approval, intense competition. "
                "Most foreign investors find 66221 (insurance agent) a more "
                "practical entry point. Let me explain both paths."
            ),
            "whatYouNeed": (
                "1. **PT PMA incorporation** — notary deed, AHU "
                "registration; minimum IDR 10B stated capital (~3–5 weeks)\n"
                "5. **Modal disetor minimum** — **IDR 100 billion** paid-up "
                "capital for new general insurance company (POJK "
                "requirement, far higher than PT PMA minimum)\n"
                "**Minimum capital:** IDR 100 billion paid-up (OJK "
                "requirement) + IDR 10B PT PMA stated capital.\n"
                "**PMA:** Capped at 80% of paid-up capital (PP 14/2018 "
                "Pasal 5(1))."
            ),
            "baliContext": (
                "**Establishing a new general insurer is extremely "
                "difficult:** IDR 100B capital requirement, 12–24 month "
                "OJK approval process, intense competition from "
                "established players\n"
                "**More practical path: Insurance agency (66221)** — act "
                "as intermediary selling insurance products on behalf of "
                "existing insurers; much lower capital requirement (IDR "
                "10B PT PMA only), faster licensing, immediate revenue\n"
                "**Acquisition route:** Buying an existing small general "
                "insurer may be faster than new establishment, but PMA cap "
                "(historically 80% for acquisitions) applies — verify "
                "current regulations\n"
                "**IDR 100B capital is real:** This is paid-up capital, "
                "not stated capital; you must actually deposit IDR 100 "
                "billion into the company bank account\n"
                "**Consider agency model first:** 66221 (insurance agent) "
                "is a much more accessible entry point into Bali's "
                "insurance market — test the market before committing IDR "
                "100B to a new insurer"
            ),
            "whatChanged": "unrelated field",
            "whatItMeans": "unrelated field",
            "youllAlsoNeed": "unrelated field",
        }
    }


def _spec(gold=None):
    gold = gold if gold is not None else _base_gold()
    return {
        "code": "65121",
        "old_sha256": H.sha256_of(gold["65121"]),
        "edits": REAL_SPEC["edits"],
    }


# --- the real 65121, post-cure --------------------------------------------------


def test_the_real_65121_has_no_capital_figures():
    gold, _ = mod.load_gold(mod.GOLD_PATH)
    rec = gold["65121"]
    for field in ("zantaraOpener", "whatYouNeed", "baliContext"):
        text = rec[field]
        for needle in CAPITAL_NEEDLES:
            assert needle not in text, f"{field} still names {needle!r}"


def test_the_real_65121_acquisition_line_matches_the_general_cap():
    gold, _ = mod.load_gold(mod.GOLD_PATH)
    rec = gold["65121"]
    assert "historically 80%" not in rec["baliContext"].lower() or (
        "not acquisition-specific" in rec["baliContext"]
    )
    assert "PP 14/2018 Pasal 5(1)" in rec["baliContext"]


def test_the_real_cure_is_a_clean_noop_without_writing():
    gold, _ = mod.load_gold(mod.GOLD_PATH)
    verdict = mod.plan(REAL_SPEC, gold)
    assert verdict["action"] == "noop"


# --- guilt ------------------------------------------------------------------


def test_apply_sweeps_all_nine_edits(tmp_path):
    gold = _base_gold()
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    after, _ = mod.load_gold(path)
    rec = after["65121"]
    for field in ("zantaraOpener", "whatYouNeed", "baliContext"):
        for needle in CAPITAL_NEEDLES:
            assert needle not in rec[field], f"{field} still names {needle!r}"


def test_apply_leaves_unrelated_fields_alone(tmp_path):
    gold = _base_gold()
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    after, _ = mod.load_gold(path)
    assert after["65121"]["whatChanged"] == "unrelated field"
    assert after["65121"]["whatItMeans"] == "unrelated field"
    assert after["65121"]["youllAlsoNeed"] == "unrelated field"


def test_apply_never_touches_the_already_cured_pma_sentence(tmp_path):
    """The closing PMA sentence in whatYouNeed was already fixed by
    cure_gold_pma_line.py — this sweep must leave it exactly alone."""
    gold = _base_gold()
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    after, _ = mod.load_gold(path)
    assert "Capped at 80% of paid-up capital (PP 14/2018 Pasal 5(1))." in after["65121"][
        "whatYouNeed"
    ]


def test_second_run_is_a_noop(tmp_path, capsys):
    gold = _base_gold()
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0
    capsys.readouterr()
    assert mod.main(argv) == 0
    assert "already cured" in capsys.readouterr().out


def test_a_neighbor_code_in_a_fixture_is_never_touched(tmp_path):
    gold = _base_gold()
    gold["66221"] = {"whatYouNeed": "insurance agent, unrelated"}
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    after, _ = mod.load_gold(path)
    assert after["66221"] == {"whatYouNeed": "insurance agent, unrelated"}


def test_dry_run_writes_nothing(tmp_path):
    gold = _base_gold()
    spec = _spec(gold)
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


# --- guilt: refusals -------------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    gold = {"99999": {"whatYouNeed": "x"}}
    spec = _spec(_base_gold())
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_record_has_drifted(tmp_path):
    gold = _base_gold()
    spec = _spec(gold)
    gold["65121"]["whatYouNeed"] += " (a human already edited this)"
    path = _gold_file(tmp_path, gold)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before
