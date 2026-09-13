"""Unit tests for scripts/kbli_bench/score_p2b.py — the P2b benchmark scorer.

Everything covered here exists because of a measured defect, and most of it because a
three-round adversarial council kept finding a new way for the same guard to be wrong.

1. The judge's ground truth. The 2026-08-20 run fed the judge `expected.codes` — the codes the
   corpus AUTHOR expected — while the model answered from `package_codes`, the codes it was
   actually served. 22 of 30 fabrication flags were false, every one of them a code the model
   had been given and the judge had no record for. The rule is now the union of the two, and
   each run is still judged against its own package.

2. The Bali-moratorium scope class rule, REDUCED to what tokens decide. Q23 used to pass by
   accident. The first attempt at an acceptance rule tried to decide permanence and
   universality from free text and was wrong three rounds running, in three different ways.
   What is left here is decidable; the rest is declared and handed to the judge.

3. Run integrity: four distinct failure categories, and a row count that cannot be satisfied
   by the wrong rows.

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


def test_good_answer_passes_every_decidable_criterion(score_mod):
    r = score_mod.moratorium_scope_check(GOOD)
    assert r["decidable_pass"] is True, r
    assert all(r["required"].values()), r["required"]
    assert r["forbidden"]["quotes_a_moratorium_total"] == []


@pytest.mark.parametrize(
    "removed, missing_criterion",
    [
        ("B.27.000/642/PM/DPMPTSP", "cites_source_letter"),
        ("13 Mei 2026", "cites_effective_date"),
        ("Menengah Rendah", "names_medium_low_risk_class"),
    ],
)
def test_guilt_each_missing_part_fails_its_own_criterion(score_mod, removed, missing_criterion):
    """GUILT: strike one required part out of an otherwise correct answer and exactly that
    criterion goes false — not a blanket failure that would pass for the wrong reason."""
    r = score_mod.moratorium_scope_check(GOOD.replace(removed, ""))
    assert r["decidable_pass"] is False
    assert r["required"][missing_criterion] is False
    others = {k: v for k, v in r["required"].items() if k != missing_criterion}
    assert all(others.values()), (missing_criterion, others)


def test_council_r3_naming_only_the_medium_low_class_is_not_enough(score_mod):
    """Council round 3, codex-gpt-5.6-sol: the moratorium covers Low AND Medium-Low. An answer
    that names only the second is wrong, and it used to pass."""
    only_medium = (
        "Since 13 May 2026, the Bali PMA moratorium applies only to KBLI in the Medium-Low risk "
        "class. The restriction is permanent. Source: B.27.000/642/PM/DPMPTSP."
    )
    r = score_mod.moratorium_scope_check(only_medium)
    assert r["required"]["names_medium_low_risk_class"] is True
    assert r["required"]["names_low_risk_class"] is False, r["required"]
    assert r["decidable_pass"] is False


def test_innocence_menengah_rendah_does_not_answer_for_rendah(score_mod):
    """INNOCENCE for the same criterion, the other way round: "menengah rendah" CONTAINS
    "rendah", so a naive substring test would call the wrong answer above correct. The low-class
    test runs on the text with the medium-low spans removed, and a real "Rendah dan Menengah
    Rendah" still satisfies both."""
    r = score_mod.moratorium_scope_check(GOOD)
    assert r["required"]["names_low_risk_class"] is True
    assert r["required"]["names_medium_low_risk_class"] is True
    en = (
        "Since 13 May 2026 all KBLI in the Low and Medium-Low risk classes are blocked for PMA "
        "across Bali. The restriction is permanent. Source: Gubernur letter B.27.000/642/PM/DPMPTSP."
    )
    assert score_mod.moratorium_scope_check(en)["decidable_pass"] is True


@pytest.mark.parametrize("total", ["518", "48"])
def test_guilt_quoting_a_moratorium_total(score_mod, total):
    """Neither 518 (every blocked record, five causes conflated) nor 48 (only the codes whose
    status literally names the moratorium) answers "which KBLI are under the moratorium"."""
    r = score_mod.moratorium_scope_check(GOOD + f" Terdapat {total} KBLI yang terkena moratorium.")
    assert r["decidable_pass"] is False
    assert r["forbidden"]["quotes_a_moratorium_total"], r["forbidden"]


def test_innocence_an_unrelated_number_is_not_a_total(score_mod):
    """INNOCENCE: a percentage near the word KBLI is not a code count."""
    r = score_mod.moratorium_scope_check(GOOD + " Kepemilikan asing tetap 100% di luar kategori itu.")
    assert r["forbidden"]["quotes_a_moratorium_total"] == []
    assert r["decidable_pass"] is True


def test_abstention_fails_the_decidable_criteria(score_mod):
    r = score_mod.moratorium_scope_check("The navigator does not carry that fact.")
    assert r["decidable_pass"] is False


@pytest.mark.parametrize("sentence", [
    # round 1: a negated temporariness phrase — the CORRECT answer
    "Larangan ini permanen dan tidak bersifat sementara.",
    # round 3: `sementara` as the conjunction "while" — also the CORRECT answer
    "Larangan ini permanen, sementara kode di luar kategori tersebut tidak terpengaruh.",
    # round 2: a WRONG answer, which the deterministic rule no longer claims to catch
    "Larangan ini tidak permanen dan hanya sementara.",
])
def test_the_semantic_criteria_are_deferred_not_guessed(score_mod, sentence):
    """The three council sentences, together, are the argument for the deferral: two are correct
    and one is wrong, and no version of the regex got all three right. The decidable criteria are
    identical across the three — which is exactly the point. Permanence is the judge's call, and
    the expectations are handed to it verbatim."""
    head = ("Sumber: B.27.000/642/PM/DPMPTSP. Sejak 13 Mei 2026, moratorium PMA Bali berlaku "
            "untuk seluruh KBLI dengan kategori risiko Rendah dan Menengah Rendah. ")
    r = score_mod.moratorium_scope_check(head + sentence)
    assert r["decidable_pass"] is True
    assert r["deferred_to_judge"] == ["states_permanence", "claims_every_kbli_banned"]
    assert r["deferral_reason"]


def test_the_deferred_criteria_reach_the_judge(score_mod, tmp_path, monkeypatch):
    """A criterion that is deferred and then never stated to anyone is not deferred, it is
    dropped. The judge prompt for this class carries both expectations in full."""
    corpus = json.loads(CORPUS_PATH.read_text())
    q23 = [q for q in corpus["questions"] if score_mod.is_moratorium_scope_question(q)]
    assert len(q23) == 1
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps({"questions": q23}))
    ap = tmp_path / "answers.jsonl"
    ap.write_text(json.dumps({"qid": q23[0]["id"], "run": 1, "raw_answer": GOOD,
                              "gate_ok": True, "package_codes": []}))
    outdir = tmp_path / "prompts"
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))
    payload = json.loads((outdir / f"{q23[0]['id']}.txt").read_text().split("INPUT:\n", 1)[1])
    assert len(payload["class_rule_expectations"]) == 2
    assert "PERMANENT" in payload["class_rule_expectations"][0]
    assert "every KBLI" in payload["class_rule_expectations"][1]


# ── which question the class rule applies to ──────────────────────────────────────────────
def test_class_rule_targets_exactly_the_moratorium_question(score_mod):
    corpus = json.loads(CORPUS_PATH.read_text())
    hits = [q["id"] for q in corpus["questions"] if score_mod.is_moratorium_scope_question(q)]
    assert hits == ["Q23"], hits
    # …derived from the frozen corpus, not from a hard-coded id: the selector's own source
    # carries no question id, so re-numbering the corpus cannot silently unhook the rule
    import inspect
    assert "Q23" not in inspect.getsource(score_mod.is_moratorium_scope_question)


# ── the judge's ground truth is the package the model saw ─────────────────────────────────
def test_judge_prompt_carries_served_codes_not_only_expected(score_mod, tmp_path, monkeypatch):
    """The regression that made 22 of 30 fabrication flags false: a code the model was served
    but the corpus did not list arrived at the judge with no record to check it against."""
    corpus = {"questions": [{"id": "T01", "class": "structured", "text": "kafe di Ubud",
                             "expected": {"codes": ["56303"], "behavior": "…"}}]}
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps(corpus))
    ap = tmp_path / "answers.jsonl"
    ap.write_text(json.dumps({"qid": "T01", "run": 1, "raw_answer": "56303 dan 56101.",
                              "gate_ok": True, "package_codes": ["56303", "56101"]}))
    outdir = tmp_path / "prompts"
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))

    payload = json.loads((outdir / "T01.txt").read_text().split("INPUT:\n", 1)[1])
    assert "56303" in payload["ground_truth_records"], "the expected code is still supplied"
    assert "56101" in payload["ground_truth_records"], "the code the model was SERVED is supplied too"
    assert payload["ground_truth_provenance"]["served_package_codes"] == ["56303", "56101"]
    assert payload["answers"][0]["package_codes"] == ["56303", "56101"]


def test_judge_is_told_the_union_is_not_cross_run_credit(score_mod, tmp_path, monkeypatch):
    """Council round 2, codex-gpt-5.6-sol: the union is supplied so nothing arrives unjudged,
    which is not the same as letting run 1 be credited with the package run 2 was shown."""
    corpus = {"questions": [{"id": "T03", "class": "structured", "text": "kafe",
                             "expected": {"codes": ["56303"]}}]}
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps(corpus))
    ap = tmp_path / "answers.jsonl"
    ap.write_text("\n".join(json.dumps(r) for r in [
        {"qid": "T03", "run": 1, "raw_answer": "56101 is fine.", "gate_ok": True, "package_codes": ["56303"]},
        {"qid": "T03", "run": 2, "raw_answer": "56101 is fine.", "gate_ok": True, "package_codes": ["56101"]},
    ]))
    outdir = tmp_path / "prompts"
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))
    text = (outdir / "T03.txt").read_text()
    assert "package_codes" in text
    assert "NOT evidence for this one" in text
    payload = json.loads(text.split("INPUT:\n", 1)[1])
    assert payload["answers"][0]["package_codes"] == ["56303"]
    assert payload["answers"][1]["package_codes"] == ["56101"]


def test_judge_prompt_innocence_a_code_never_served_is_not_invented(score_mod, tmp_path, monkeypatch):
    """INNOCENCE: the union adds what was served; a question with no expected codes and an empty
    package gets no ground truth at all."""
    corpus = {"questions": [{"id": "T02", "class": "known-gap", "text": "modal disetor?",
                             "expected": {"behavior": "abstain"}}]}
    cp = tmp_path / "corpus.json"
    cp.write_text(json.dumps(corpus))
    ap = tmp_path / "answers.jsonl"
    ap.write_text(json.dumps({"qid": "T02", "run": 1, "raw_answer": "The navigator does not carry that fact.",
                              "gate_ok": True, "package_codes": []}))
    outdir = tmp_path / "prompts"
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_prompts(str(cp), str(ap), str(outdir))
    payload = json.loads((outdir / "T02.txt").read_text().split("INPUT:\n", 1)[1])
    assert payload["ground_truth_records"] == {}
    assert "class_rule_expectations" not in payload


# ── the floors report their own arithmetic ────────────────────────────────────────────────
def test_floors_carry_denominators_and_the_canonical_command(score_mod, tmp_path, monkeypatch, capsys):
    corpus = json.loads(CORPUS_PATH.read_text())
    rows = [{"qid": q["id"], "run": run, "gate_ok": True, "package_codes": [],
             "raw_answer": GOOD if q["id"] == "Q23" else "The navigator does not carry that fact."}
            for q in corpus["questions"] for run in (1, 2, 3)]
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
    # with no judge output, a decidably-good Q23 answer is UNJUDGED, never silently correct
    assert set(report["per_question"]["Q23"]["runs"]) == {"unjudged"}


def test_a_decidably_bad_answer_is_wrong_without_any_judge(score_mod, tmp_path, monkeypatch, capsys):
    """The class rule can still FAIL a question on its own — that half is decidable."""
    corpus = json.loads(CORPUS_PATH.read_text())
    rows = [{"qid": q["id"], "run": run, "gate_ok": True, "package_codes": [],
             "raw_answer": "Moratorium Bali berlaku untuk semua KBLI." if q["id"] == "Q23"
             else "The navigator does not carry that fact."}
            for q in corpus["questions"] for run in (1, 2, 3)]
    ap = tmp_path / "answers.jsonl"
    ap.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(score_mod, "find_root", lambda: REPO_ROOT)
    score_mod.cmd_score(str(CORPUS_PATH), str(ap), str(tmp_path / "nojudge"))
    report = json.loads(capsys.readouterr().out)
    assert set(report["per_question"]["Q23"]["runs"]) == {"wrong"}


# ── run integrity: four distinct failure categories ───────────────────────────────────────
@pytest.mark.parametrize(
    "row, expected",
    [
        ({"qid": "Q01", "run": 1, "raw_answer": "56303 is blocked.", "package_outcome": "built"}, "answered"),
        ({"qid": "Q01", "run": 1, "raw_answer": "", "package_outcome": "built"}, "empty_answer"),
        ({"qid": "Q01", "run": 1, "raw_answer": "   \n", "package_outcome": "built"}, "empty_answer"),
        ({"qid": "Q01", "run": 1, "error": "codex timed out after 180s", "package_outcome": "built"}, "timeout"),
        ({"qid": "Q01", "run": 1, "error": "could not parse the runner's JSON envelope", "package_outcome": "built"}, "parse_failed"),
        ({"qid": "Q01", "run": 1, "error": "spawn failed: EAGAIN", "package_outcome": "built"}, "transport_error"),
        ({"qid": "Q01", "run": 1, "raw_answer": "I can't help with that.", "package_outcome": "built"}, "model_refusal"),
        ({"qid": "Q01", "run": 1, "package_outcome": "narrowComparison:1,2,3,4"}, "package_not_built"),
    ],
)
def test_each_failure_shape_gets_its_own_category(score_mod, row, expected):
    """GUILT+INNOCENCE per category: a timeout is not "an error", an empty answer is not a
    refusal, and a refusal by the model is a benchmark result while the other three are not."""
    assert score_mod.classify_row(row) == expected


def test_run_integrity_flags_an_incomplete_run(score_mod):
    corpus = {"questions": [{"id": "Q01", "class": "structured"}, {"id": "Q02", "class": "structured"}]}
    r = score_mod.run_integrity([{"qid": "Q01", "run": 1, "raw_answer": "x", "package_outcome": "built"}],
                                corpus, expected_runs=3)
    assert r["complete"] is False
    assert r["rows"] == 1 and r["expected_rows"] == 6


def test_run_integrity_flags_a_synthesized_row(score_mod):
    corpus = {"questions": [{"id": "Q01", "class": "structured"}]}
    rows = [{"qid": "Q01", "run": 1, "raw_answer": "x", "package_outcome": "built"},
            {"qid": "Q99", "run": 1, "raw_answer": "x", "package_outcome": "built"}]
    r = score_mod.run_integrity(rows, corpus, expected_runs=1)
    assert r["synthesized_rows"] == [("Q99", 1)]
    assert r["complete"] is False


def test_council_r3_a_run_number_out_of_range_is_synthesized(score_mod):
    """Council round 3, codex-gpt-5.6-sol: runs 1,2,4 for one question and 1,2,3 for another
    still total 6 of 6. Counting rows does not notice that (Q01,3) is missing and (Q01,4) never
    existed — the run number has to be inside the range."""
    corpus = {"questions": [{"id": "Q01", "class": "structured"}, {"id": "Q02", "class": "structured"}]}
    rows = [{"qid": "Q01", "run": n, "raw_answer": "x", "package_outcome": "built"} for n in (1, 2, 4)]
    rows += [{"qid": "Q02", "run": n, "raw_answer": "x", "package_outcome": "built"} for n in (1, 2, 3)]
    r = score_mod.run_integrity(rows, corpus, expected_runs=3)
    assert r["rows"] == r["expected_rows"] == 6
    assert r["synthesized_rows"] == [("Q01", 4)]
    assert r["complete"] is False


def test_run_integrity_innocence_a_complete_run_is_complete(score_mod):
    corpus = {"questions": [{"id": "Q01", "class": "structured"}, {"id": "Q02", "class": "structured"}]}
    rows = [{"qid": q, "run": n, "raw_answer": "x", "package_outcome": "built"}
            for q in ("Q01", "Q02") for n in (1, 2, 3)]
    r = score_mod.run_integrity(rows, corpus, expected_runs=3)
    assert r["complete"] is True
    assert r["categories"] == {"answered": 6}
    assert r["duplicate_rows"] == [] and r["synthesized_rows"] == []
