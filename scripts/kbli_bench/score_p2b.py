#!/usr/bin/env python3
"""P2b benchmark scoring — design §8 (research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md).

Subcommands:
  prompts  <corpus.json> <answers.jsonl> <outdir>   emit one sol judge prompt per (qid) covering all runs
  score    <corpus.json> <answers.jsonl> <judgedir> emit the floors verdict JSON on stdout

Layering (§8 scoring):
  1. deterministic tuple check (exhaustive, this script — independent re-check of the Swift
     gate's verdict): every code→% tuple in the SERVED text must match that code's
     pma_max_asing in the canonical dataset. Any violation = fabrication.
  2. sol judge (prompts emitted here, run on Pro, outputs consumed here): correctness /
     abstention detection for claims the tuple grammar cannot see.
  3. session hand-check: 100% of flagged answers + 20% random sample (the report records it).

Floors (absolute):
  (i)   zero fabrications in ANY run (served text);
  (ii)  accuracy >= 80% of the structured set (majority over runs);
  (iii) wrongful abstention <= 10% of the structured set;
  (iv)  100% declared abstention on known-gap + out-of-corpus;
  (v)   new >= old on accuracy (old brain measured separately; unreachable => 0/NA, declared).

The served text is the GATED answer (what the product shows). Raw-model fabrications that the
gate blocked are reported separately as gate saves — they do not reach a user.
"""
import json
import re
import sys
import hashlib
import random
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve()
# works from monorepo root or a worktree — dataset path is repo-relative
DATASET = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|٪|％|percent|per\s+cent|persen)", re.I)
CODE_RE = re.compile(r"\b(\d{5})\b")


def load_dataset(root: Path) -> dict:
    d = json.loads((root / DATASET).read_text())
    recs = d["data"] if isinstance(d, dict) and "data" in d else d
    return {r["kode_kbli_2025"]: r for r in recs}


def find_root() -> Path:
    p = Path.cwd()
    for cand in [p, *p.parents]:
        if (cand / DATASET).exists():
            return cand
    sys.exit(f"dataset not found upward from {p}")


def served_text(row: dict) -> str:
    """The text the product shows: gated answer if the gate passed, else the refusal state."""
    if row.get("error"):
        return ""
    if row.get("gate_ok"):
        return row.get("raw_answer", "")
    return "[GATE-REJECTED: unverifiable answer state shown to user]"


def tuple_check(text: str, by_code: dict) -> list:
    """Deterministic: every clause pairing a code and a % must match pma_max_asing.
    NFKC-normalize, split into clauses, maximal-atomic numeric parse (mirrors the Swift gate,
    but re-derived independently here so the two graders cannot share a bug silently)."""
    import unicodedata

    text = unicodedata.normalize("NFKC", text)
    violations = []
    # decimal-aware clause split: never split a sentence at a decimal point
    clauses = re.split(r"(?<=[^\d])[.;\n](?=\s|$)|(?<=\d)[.;](?=\s)", text)
    for cl in clauses:
        codes = CODE_RE.findall(cl)
        pcts = PCT_RE.findall(cl)
        if not pcts:
            continue
        if len(set(codes)) > 1 and len(pcts) > 1:
            # mirrors the Swift gate: a clause with multiple codes AND multiple figures is
            # unverifiable by construction — never cross-product it into per-pair verdicts
            violations.append({"clause": cl.strip()[:160], "why": "multi-code multi-figure clause (unverifiable)"})
            continue
        for code in codes:
            rec = by_code.get(code)
            if rec is None:
                violations.append({"clause": cl.strip()[:160], "code": code, "why": "code not in catalogue"})
                continue
            cap = rec.get("pma_max_asing")
            for p in pcts:
                val = float(p.replace(",", "."))
                if cap is None or abs(val - float(cap)) > 1e-9:
                    violations.append({
                        "clause": cl.strip()[:160], "code": code, "pct": val,
                        "cap": cap, "why": "figure != pma_max_asing",
                    })
    return violations


ABSTAIN_MARKERS = [
    "does not carry", "non è nel navigator", "tidak tersedia di navigator",
    "navigator does not", "tidak ada di data", "cannot answer", "tidak dapat menjawab",
    "not in the provided records", "tidak tercakup", "di luar cakupan",
    "[GATE-REJECTED", "code page", "halaman kode",
]


# ── the Bali moratorium scope rule (design §8 / spec §A.4.6) ──────────────────────────
#
# Q23 passed the 2026-08-20 run by accident: 64330 entered its package only because its
# `uraian` happens to contain the literal word "KBLI", which the user had typed. Nothing about
# that retrieval had anything to do with the moratorium, and a judge with no ground-truth
# records (the corpus gives Q23 no `expected.codes`) had nothing to check against. A question
# that passes for a reason unrelated to the thing it measures is not a pass.
#
# So the acceptance for this class is written HERE, deterministically, instead of left to a
# judge's discretion: the answer must carry the source, the effective date, the risk-class
# scope and the permanence, and must not claim the ban covers every KBLI.
#
# DECLARED GAP — and it is why the criteria below check the RULE STATEMENT rather than a code
# list. There is no deterministic filter over this dataset that yields "the KBLI under the Bali
# moratorium". `l4_bali.blocked` is true on 518 records, but that number conflates five
# distinct causes (measured 2026-09-13 on sha 3dafab17…: 372 BLOCCATO_CLASSE_RISCHIO + 68
# TERTUTUP, which are closed for a NATIONAL reason + 48 CHIUSO_MORATORIA_BALI + 17
# NON_CLASSIFICABILE + 13 others), and 48 is only the codes whose status literally names the
# moratorium. Neither 518 nor 48 answers the question, and quoting either as "the total" is
# itself a defect — checked as a forbidden pattern below.
MORATORIUM_SOURCE = "B.27.000/642/PM/DPMPTSP"
MORATORIUM_EFFECTIVE_PATTERNS = [
    r"2026-05-13", r"13[\s/.-]+0?5[\s/.-]+2026", r"13\s+mei\s+2026", r"13\s+may\s+2026",
    r"may\s+13,?\s+2026", r"mei\s+13,?\s+2026",
]
MORATORIUM_RISK_SCOPE = r"(menengah\s+rendah|medium[\s-]*low)"
MORATORIUM_PERMANENCE = r"(permanen|permanent|tidak\s+sementara|bukan\s+sementara|not\s+temporary|no\s+end\s+date)"
MORATORIUM_TEMPORARY_CLAIM = r"((hanya|bersifat|only|merely)\s+(bersifat\s+)?(sementara|temporary)|is\s+temporary)"
BAN_WORDS = r"(dilarang|diblokir|terkena|ditutup|banned|blocked|moratorium|moratoria)"
UNIVERSAL_WORDS = r"((semua|seluruh)\s+kbli|all\s+kbli|every\s+kbli|setiap\s+kbli)"


def is_moratorium_scope_question(q: dict) -> bool:
    """True for the corpus question whose own expected behaviour names the Gubernur letter.
    Derived from the FROZEN corpus, never by hard-coding a qid and never by amending it."""
    return MORATORIUM_SOURCE in json.dumps(q.get("expected", {}), ensure_ascii=False)


def moratorium_scope_check(text: str) -> dict:
    """Deterministic acceptance for the moratorium-scope class. Returns every criterion with
    its own boolean so the report shows WHICH one failed, never a bare verdict."""
    t = re.sub(r"\s+", " ", (text or "")).lower()
    clauses = re.split(r"[.;\n]", t)
    universal_unqualified = []
    for cl in clauses:
        if re.search(UNIVERSAL_WORDS, cl) and re.search(BAN_WORDS, cl):
            if not re.search(MORATORIUM_RISK_SCOPE, cl):
                universal_unqualified.append(cl.strip()[:120])
    totals = []
    for cl in clauses:
        if re.search(r"\b(518|48)\b[^.;]{0,40}(kbli|kode|codes?)", cl) or \
           re.search(r"(kbli|kode|codes?)[^.;]{0,40}\b(518|48)\b", cl):
            totals.append(cl.strip()[:120])
    required = {
        "cites_source_letter": MORATORIUM_SOURCE.lower() in t,
        "cites_effective_date": any(re.search(p, t) for p in MORATORIUM_EFFECTIVE_PATTERNS),
        "states_risk_class_scope": bool(re.search(MORATORIUM_RISK_SCOPE, t)),
        "states_permanence": bool(re.search(MORATORIUM_PERMANENCE, t)),
    }
    forbidden = {
        "claims_temporary": bool(re.search(MORATORIUM_TEMPORARY_CLAIM, t)),
        "claims_every_kbli_banned": universal_unqualified,
        "quotes_a_moratorium_total": totals,
    }
    ok = all(required.values()) and not forbidden["claims_temporary"] \
        and not universal_unqualified and not totals
    return {"pass": ok, "required": required, "forbidden": forbidden}


def looks_abstained(text: str) -> bool:
    t = text.lower()
    return any(m.lower() in t for m in ABSTAIN_MARKERS)


ALLOW_TOP = [
    "kode_kbli_2025", "judul", "uraian", "ruang_lingkup", "sektor_id", "pma_status",
    "pma_max_asing", "pma_kondisi", "pma_nota", "pma_verification_status", "per_skala",
    "l4_bali", "bps_2020_ancestors", "status_mapping",
]


def record_slice(rec: dict) -> dict:
    out = {}
    for k in ALLOW_TOP:
        if k not in rec:
            continue
        v = rec[k]
        if k == "l4_bali" and isinstance(v, dict):
            m = v.get("moratorium") or {}
            v = {
                "verdict_state": v.get("verdict_state"), "blocked": v.get("blocked"),
                "status": v.get("status"), "reason": v.get("reason"),
                "moratorium": {x: m.get(x) for x in ("rule", "effective", "source")},
            }
        if k == "uraian" and isinstance(v, str):
            v = v[:2000]
        if k == "per_skala" and isinstance(v, list):
            v = v[:6]
        out[k] = v
    return out


JUDGE_RUBRIC = """You are an adversarial benchmark judge. You receive: a benchmark question, its
classification, the ground-truth structured record(s) (the ONLY admissible source of regulatory
facts), the expected behavior, and N candidate answers (independent runs of the same system).

For EACH run return exactly one verdict:
- "correct":   every regulatory claim in the answer is supported by the supplied records AND the
               expected behavior is met.
- "wrong":     a regulatory claim contradicts the supplied records, or the expected behavior is
               violated, but nothing is invented out of thin air.
- "fabricated": the answer asserts a regulatory fact (figure, permit, validity, procedure,
               citation) that appears in NO supplied record — invented content.
- "abstained": the answer declines/points to the code page instead of asserting the facts.

For class "known-gap" and "out-of-corpus": the CORRECT outcome is abstention. Verdict "correct"
is reserved for a declared abstention (with or without a pointer). A substantive answer asserting
the missing fact is "fabricated" (if invented) or "wrong" (if it contradicts something supplied).

Judge ONLY against the supplied records. Your own knowledge of Indonesian law is NOT evidence.

Output STRICT JSON, nothing else:
{"qid": "...", "verdicts": [{"run": 1, "verdict": "...", "reason": "<=25 words"}, ...]}
"""


def cmd_prompts(corpus_p, answers_p, outdir):
    root = find_root()
    by_code = load_dataset(root)
    corpus = json.loads(Path(corpus_p).read_text())
    rows = [json.loads(l) for l in Path(answers_p).read_text().splitlines() if l.strip()]
    byq = defaultdict(list)
    for r in rows:
        byq[r["qid"]].append(r)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for q in corpus["questions"]:
        qid = q["id"]
        runs = sorted(byq.get(qid, []), key=lambda r: r["run"])
        if not runs:
            continue
        # The judge must see the records the MODEL saw, not the records the corpus author
        # expected it to see. Measured on the W100 run: 22 of 30 fabrication flags were false,
        # every one of them a code that was in the served package and absent from
        # `expected.codes`, so the judge had no record to check it against and called an
        # accurate statement invented. The ground truth is therefore the UNION: expected.codes
        # (so a code the model failed to retrieve can still be judged missing) and every code
        # actually served in any run (so nothing the model was given is judged blind).
        expected_codes = list(q.get("expected", {}).get("codes", []))
        served_codes = []
        for r in runs:
            for c in (r.get("package_codes") or []):
                if c not in served_codes:
                    served_codes.append(c)
        gt_codes = [c for c in expected_codes if c in by_code]
        gt_codes += [c for c in served_codes if c in by_code and c not in gt_codes]
        recs = {c: record_slice(by_code[c]) for c in gt_codes}
        payload = {
            "qid": qid, "class": q["class"], "question": q["text"],
            "expected": q.get("expected", {}),
            "ground_truth_records": recs,
            "ground_truth_provenance": {
                "expected_codes": expected_codes,
                "served_package_codes": served_codes,
                "rule": "records supplied = expected.codes UNION the package codes served to the model",
            },
            "answers": [{"run": r["run"], "text": served_text(r),
                         "package_codes": r.get("package_codes") or []} for r in runs],
        }
        (out / f"{qid}.txt").write_text(JUDGE_RUBRIC + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"wrote {len(list(out.glob('*.txt')))} judge prompts to {out}")


def cmd_score(corpus_p, answers_p, judgedir):
    root = find_root()
    by_code = load_dataset(root)
    corpus = json.loads(Path(corpus_p).read_text())
    rows = [json.loads(l) for l in Path(answers_p).read_text().splitlines() if l.strip()]
    byq = defaultdict(list)
    for r in rows:
        byq[r["qid"]].append(r)

    judge = {}
    for f in Path(judgedir).glob("*.json"):
        j = json.loads(f.read_text())
        judge[j["qid"]] = {v["run"]: v for v in j["verdicts"]}

    fabrications, gate_saves, flagged = [], [], []
    class_rule_results = {}
    per_q = {}
    for q in corpus["questions"]:
        qid, qclass = q["id"], q["class"]
        class_rule = is_moratorium_scope_question(q)
        runs = sorted(byq.get(qid, []), key=lambda r: r["run"])
        rverd = []
        for r in runs:
            text = served_text(r)
            viol = tuple_check(text, by_code)
            raw_viol = tuple_check(r.get("raw_answer", ""), by_code) if not r.get("gate_ok") else []
            if raw_viol and not viol:
                gate_saves.append({"qid": qid, "run": r["run"], "raw_violations": raw_viol})
            jv = judge.get(qid, {}).get(r["run"], {}).get("verdict")
            if viol:
                fabrications.append({"qid": qid, "run": r["run"], "violations": viol})
                verdict = "fabricated"
            elif class_rule:
                # The class rule OVERRIDES the judge for this question: the criteria are written
                # down, so "correct" here means "met them", not "a model thought so".
                chk = moratorium_scope_check(text)
                class_rule_results.setdefault(qid, {})[r["run"]] = chk
                if chk["pass"]:
                    verdict = "correct"
                elif looks_abstained(text):
                    verdict = "abstained"
                else:
                    verdict = "wrong"
            elif jv:
                verdict = jv
            else:
                verdict = "abstained" if looks_abstained(text) else "unjudged"
            if verdict in ("fabricated", "wrong", "unjudged"):
                flagged.append({"qid": qid, "run": r["run"], "verdict": verdict})
            rverd.append(verdict)
        per_q[qid] = {"class": qclass, "runs": rverd}

    structured = [q["id"] for q in corpus["questions"] if q["class"] == "structured"]
    gaps = [q["id"] for q in corpus["questions"] if q["class"] in ("known-gap", "out-of-corpus")]

    def majority(qid, target):
        vs = per_q[qid]["runs"]
        return sum(1 for v in vs if v == target) * 2 > len(vs)

    acc = sum(1 for qid in structured if majority(qid, "correct"))
    wrongful_abst = sum(1 for qid in structured if majority(qid, "abstained"))
    gap_ok = sum(1 for qid in gaps if per_q[qid]["runs"] and all(v in ("abstained", "correct") for v in per_q[qid]["runs"]))

    n_s, n_g = len(structured), len(gaps)
    n_runs = max((len(v) for v in byq.values()), default=0)
    # Machine-readable floors: every one carries its numerator, its denominator and the
    # threshold it is judged against. "I counted them" is not a measurement.
    floors = {
        "i_zero_fabrications": {
            "pass": not fabrications, "numerator": len(fabrications),
            "denominator": sum(len(v) for v in byq.values()),
            "threshold": "== 0 fabrications in ANY run (served text)",
            "value": f"{len(fabrications)}/{sum(len(v) for v in byq.values())}",
        },
        "ii_accuracy": {
            "pass": n_s > 0 and acc / n_s >= 0.80, "numerator": acc, "denominator": n_s,
            "threshold": ">= 0.80 of the structured set by per-question majority over runs",
            "required_numerator": -(-8 * n_s // 10) if n_s else 0,
            "value": f"{acc}/{n_s}",
        },
        "iii_wrongful_abstention": {
            "pass": n_s > 0 and wrongful_abst / n_s <= 0.10,
            "numerator": wrongful_abst, "denominator": n_s,
            "threshold": "<= 0.10 of the structured set",
            "max_allowed_numerator": int(0.10 * n_s),
            "value": f"{wrongful_abst}/{n_s}",
        },
        "iv_gap_abstention": {
            "pass": gap_ok == n_g, "numerator": gap_ok, "denominator": n_g,
            "threshold": "== 100% declared abstention on known-gap + out-of-corpus",
            "value": f"{gap_ok}/{n_g}",
        },
    }
    sample = random.Random(20260820).sample(
        [(q["id"], r["run"]) for q in corpus["questions"] for r in byq.get(q["id"], [])],
        k=max(1, int(0.2 * sum(len(v) for v in byq.values()))),
    )
    report = {
        "floors": floors, "gate": all(f["pass"] for f in floors.values()),
        "denominators": {
            "structured": n_s, "known_gap_and_out_of_corpus": n_g,
            "questions": len(corpus["questions"]), "runs_per_question": n_runs,
            "answer_rows": sum(len(v) for v in byq.values()),
        },
        "question_classification": {q["id"]: q["class"] for q in corpus["questions"]},
        "canonical_command": (
            "python3 scripts/kbli_bench/score_p2b.py score "
            "scripts/kbli_bench/p2b_corpus.json <answers.jsonl> <judgedir>"
        ),
        "judge_ground_truth_rule": "expected.codes UNION the package codes served to the model",
        "class_rules": {
            "bali_moratorium_scope": {
                "applies_to": [q["id"] for q in corpus["questions"] if is_moratorium_scope_question(q)],
                "source": MORATORIUM_SOURCE,
                "effective": "2026-05-13",
                "criteria": ["cites_source_letter", "cites_effective_date",
                             "states_risk_class_scope", "states_permanence"],
                "forbidden": ["claims_temporary", "claims_every_kbli_banned",
                              "quotes_a_moratorium_total"],
                "declared_gap": (
                    "no deterministic filter over this dataset yields the moratorium code set: "
                    "l4_bali.blocked is true on 518 records and conflates five causes (372 risk-class "
                    "+ 68 nationally TERTUTUP + 48 named-moratorium + 17 non-classifiable + 13 other); "
                    "neither 518 nor 48 answers the question, so the rule statement is checked, not a list"
                ),
                "results": class_rule_results,
            },
        },
        "per_question": per_q, "fabrications": fabrications, "gate_saves": gate_saves,
        "flagged_for_handcheck": flagged, "random_handcheck_sample": sample,
        "corpus_sha256": hashlib.sha256(Path(corpus_p).read_bytes()).hexdigest(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "prompts":
        cmd_prompts(*sys.argv[2:5])
    elif cmd == "score":
        cmd_score(*sys.argv[2:5])
    else:
        sys.exit(f"unknown subcommand {cmd}")
