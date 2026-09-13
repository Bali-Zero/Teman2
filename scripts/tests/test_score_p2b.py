"""Unit tests for scripts/kbli_bench/score_p2b.py — the P2b benchmark scorer.

Two things are covered, and both exist because of a measured defect:

1. The judge's ground truth. The 2026-08-20 run fed the judge `expected.codes` — the codes
   the corpus AUTHOR expected — while the model answered from `package_codes`, the codes it
   was actually served. 22 of 30 fabrication flags were false, every one of them a code the
   model had been given and the judge had no record for. The rule is now the union of the two,
   and it is asserted here rather than described in a comment.

2. The Bali-moratorium scope class rule. Q23 passed by accident: a code entered its package
   because its description contains the literal word "KBLI". The acceptance for that class is
   now written down in code, with a guilt case AND an innocence case for every criterion —
   a criterion tested on one side only is how a guard ends up judging a substring.

Run:
    python3 -m pytest scripts/tests/test_score_p2b.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "kbli_bench" / "score_p2b.py"
CORPUS_PATH = REPO_ROOT / "scripts" / "kbli_bench" / "p2b_corpus.json"


@pytest.fixture(scope="module")
def score_mod():
    spec = importlib.util.spec_from_file_location("score_p2b_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── the answer a correct system gives, and its named parts ────────────────────────────────
GOOD = (
    "Sejak 13 Mei 2026, moratorium PMA Bali berlaku untuk seluruh KBLI dengan kategori risiko "
    "Rendah dan Menengah Rendah, se-pulau. Larangan ini bersifat permanen, bukan sementara. "
    "Sumber: surat Gubernur B.27.000/642/PM/DPMPTSP."
)


def test_good_answer_passes_every_criterion(score_mod):
    r = score_mod.moratorium_scope_check(GOOD)
    assert r["pass"] is True, r
    assert all(r["required"].values()), r["required"]
    assert r["forbidden"]["claims_temporary"] is False
    assert r["forbidden"]["claims_every_kbli_banned"] == []
    assert r["forbidden"]["quotes_a_moratorium_total"] == []


@pytest.mark.parametrize(
    "removed, missing_criterion",
    [
        ("B.27.000/642/PM/DPMPTSP", "cites_source_letter"),
        ("13 Mei 2026", "cites_effective_date"),
        ("Menengah Rendah", "states_risk_class_scope"),
        ("bersifat permanen, bukan sementara", "states_permanence"),
    ],
)
def test_guilt_each_missing_part_fails_its_own_criterion(score_mod, removed, missing_criterion):
    """GUILT: strike one required part out of an otherwise correct answer and exactly that
    criterion goes false — not a blanket failure that would pass for the wrong reason."""
    mutated = GOOD.replace(removed, "")
    r = score_mod.moratorium_scope_check(mutated)
    assert r["pass"] is False
    assert r["required"][missing_criterion] is False
    others = {k: v for k, v in r["required"].items() if k != missing_criterion}
    assert all(others.values()), (missing_criterion, others)


def test_guilt_claiming_the_ban_is_temporary(score_mod):
    r = score_mod.moratorium_scope_check(GOOD.replace("bersifat permanen, bukan sementara",
                                                      "hanya sementara"))
    assert r["pass"] is False
    assert r["forbidden"]["claims_temporary"] is True


@pytest.mark.parametrize("negated", [
    "Larangan ini permanen dan tidak bersifat sementara.",
    "Larangan ini permanen, bukan hanya sementara.",
    "The restriction is permanent and is not temporary.",
])
def test_innocence_a_negated_temporariness_phrase_is_the_correct_answer(score_mod, negated):
    """INNOCENCE, found by the council (tp1-qwen3.8-max, round 1, VERDICT DEFECT): "tidak
    bersifat sementara" SAYS the ban is not temporary and contains the literal "bersifat
    sementara". A guard matching the substring rejects the right answer — the over-match half
    of the same scar the under-match half of this window is curing."""
    text = (
        "Sumber: B.27.000/642/PM/DPMPTSP. Sejak 13 Mei 2026, moratorium PMA Bali berlaku "
        "untuk KBLI kategori risiko rendah dan menengah rendah. " + negated
    )
    r = score_mod.moratorium_scope_check(text)
    assert r["forbidden"]["claims_temporary"] is False, r
    assert r["pass"] is True, r


def test_guilt_claiming_every_kbli_is_banned(score_mod):
    bad = (
        "Sejak 13 Mei 2026 semua KBLI dilarang untuk PMA di Bali. "
        "Larangan permanen. Kategori risiko Menengah Rendah juga terkena. "
        "Sumber: B.27.000/642/PM/DPMPTSP."
    )
    r = score_mod.moratorium_scope_check(bad)
    assert r["pass"] is False
    assert r["forbidden"]["claims_every_kbli_banned"], r["forbidden"]


def test_innocence_a_qualified_universal_is_not_a_violation(score_mod):
    """INNOCENCE: "all KBLI in the Low and Medium-Low risk classes" is the CORRECT statement.
    A guard that fired on the word "semua" alone would reject the right answer."""
    r = score_mod.moratorium_scope_check(GOOD)
    assert r["forbidden"]["claims_every_kbli_banned"] == []
    en = (
        "Since 13 May 2026 all KBLI in the Low and Medium-Low risk classes are blocked for PMA "
        "across Bali. The restriction is permanent. Source: Gubernur letter B.27.000/642/PM/DPMPTSP."
    )
    r_en = score_mod.moratorium_scope_check(en)
    assert r_en["forbidden"]["claims_every_kbli_banned"] == []
    assert r_en["pass"] is True, r_en


@pytest.mark.parametrize("total", ["518", "48"])
def test_guilt_quoting_a_moratorium_total(score_mod, total):
    """Neither 518 (every blocked record, five causes conflated) nor 48 (only the codes whose
    status literally names the moratorium) answers "which KBLI are under the moratorium"."""
    bad = GOOD + f" Terdapat {total} KBLI yang terkena moratorium."
    r = score_mod.moratorium_scope_check(bad)
    assert r["pass"] is False
    assert r["forbidden"]["quotes_a_moratorium_total"], r["forbidden"]


def test_innocence_an_unrelated_number_is_not_a_total(score_mod):
    """INNOCENCE: a percentage or an article number near the word KBLI is not a code count."""
    r = score_mod.moratorium_scope_check(GOOD + " Kepemilikan asing tetap 100% di luar kategori itu.")
    assert r["forbidden"]["quotes_a_moratorium_total"] == []
    assert r["pass"] is True


def test_abstention_is_not_silently_a_pass(score_mod):
    r = score_mod.moratorium_scope_check("The navigator does not carry that fact.")
    assert r["pass"] is False


# ── which question the class rule applies to ──────────────────────────────────────────────
def test_class_rule_targets_exactly_the_moratorium_question(score_mod):
    corpus = json.loads(CORPUS_PATH.read_text())
    hits = [q["id"] for q in corpus["questions"] if score_mod.is_moratorium_scope_question(q)]
    assert hits == ["Q23"], hits
    # …and it is derived from the frozen corpus, not from a hard-coded id: the selector's own
    # source carries no question id, so re-numbering the corpus cannot silently unhook the rule
    import inspect
    assert "Q23" not in inspect.getsource(score_mod.is_moratorium_scope_question)


# ── the judge's ground truth is the package the model saw ─────────────────────────────────
def test_judge_prompt_carries_served_codes_not_only_expected(score_mod, tmp_path, monkeypatch):
    """The regression that made 22 of 30 fabrication flags false: a code the model was served
    but the corpus did not list arrived at the judge with no record to check it against."""
    corpus = {
        "questions": [{
            "id": "T01", "class": "structured", "text": "kafe di Ubud",
            "expected": {"codes": ["56303"], "behavior": "…"},
        }]
    }
    answers = [{
        "qid": "T01", "run": 1, "raw_answer": "56303 dan 56101.", "gate_ok": True,
        "package_codes": ["56303", "56101"],
    }]
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps(corpus))
    ap = tmp_path / "answers.jsonl"
    ap.write_text("\n".join(json.dumps(a) for a in answers))
    outdir = tmp_path / "prompts"

    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))

    payload = json.loads((outdir / "T01.txt").read_text().split("INPUT:\n", 1)[1])
    gt = payload["ground_truth_records"]
    assert "56303" in gt, "the expected code is still supplied"
    assert "56101" in gt, "the code the model was SERVED is supplied too"
    assert payload["ground_truth_provenance"]["served_package_codes"] == ["56303", "56101"]
    assert payload["answers"][0]["package_codes"] == ["56303", "56101"]


def test_judge_prompt_innocence_a_code_never_served_is_not_invented(score_mod, tmp_path, monkeypatch):
    """INNOCENCE: the union adds what was served; it does not add records at random, and a
    question with no expected codes and an empty package gets no ground truth at all."""
    corpus = {"questions": [{"id": "T02", "class": "known-gap", "text": "modal disetor?",
                             "expected": {"behavior": "abstain"}}]}
    answers = [{"qid": "T02", "run": 1, "raw_answer": "The navigator does not carry that fact.",
                "gate_ok": True, "package_codes": []}]
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps(corpus))
    ap = tmp_path / "answers.jsonl"
    ap.write_text(json.dumps(answers[0]))
    outdir = tmp_path / "prompts"
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))
    payload = json.loads((outdir / "T02.txt").read_text().split("INPUT:\n", 1)[1])
    assert payload["ground_truth_records"] == {}


# ── the floors report their own arithmetic ────────────────────────────────────────────────
def test_floors_carry_denominators_and_the_canonical_command(score_mod, tmp_path, monkeypatch, capsys):
    corpus = json.loads(CORPUS_PATH.read_text())
    rows = []
    for q in corpus["questions"]:
        for run in (1, 2, 3):
            rows.append({"qid": q["id"], "run": run, "gate_ok": True,
                         "raw_answer": GOOD if q["id"] == "Q23" else "The navigator does not carry that fact.",
                         "package_codes": []})
    ap = tmp_path / "answers.jsonl"
    ap.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_score(str(CORPUS_PATH), str(ap), str(tmp_path / "nojudge"))
    report = json.loads(capsys.readouterr().out)

    assert report["denominators"] == {
        "structured": 8, "known_gap_and_out_of_corpus": 21,
        "questions": 29, "runs_per_question": 3, "answer_rows": 87,
    }
    for name, floor in report["floors"].items():
        assert "numerator" in floor and "denominator" in floor and "threshold" in floor, name
    assert report["canonical_command"].startswith("python3 scripts/kbli_bench/score_p2b.py score")
    assert report["judge_ground_truth_rule"].startswith("expected.codes UNION")
    assert report["class_rules"]["bali_moratorium_scope"]["applies_to"] == ["Q23"]
    assert report["class_rules"]["bali_moratorium_scope"]["declared_gap"]
    # the class rule decided Q23, not a judge — and it decided it correct on this fixture
    assert report["per_question"]["Q23"]["runs"] == ["correct", "correct", "correct"]
