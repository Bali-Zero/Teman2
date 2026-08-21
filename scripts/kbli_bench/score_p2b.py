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
        recs = {c: record_slice(by_code[c]) for c in q.get("expected", {}).get("codes", []) if c in by_code}
        payload = {
            "qid": qid, "class": q["class"], "question": q["text"],
            "expected": q.get("expected", {}), "ground_truth_records": recs,
            "answers": [{"run": r["run"], "text": served_text(r)} for r in runs],
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
    per_q = {}
    for q in corpus["questions"]:
        qid, qclass = q["id"], q["class"]
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
    floors = {
        "i_zero_fabrications": {"pass": not fabrications, "count": len(fabrications)},
        "ii_accuracy": {"pass": n_s > 0 and acc / n_s >= 0.80, "value": f"{acc}/{n_s}"},
        "iii_wrongful_abstention": {"pass": n_s > 0 and wrongful_abst / n_s <= 0.10, "value": f"{wrongful_abst}/{n_s}"},
        "iv_gap_abstention": {"pass": gap_ok == n_g, "value": f"{gap_ok}/{n_g}"},
    }
    sample = random.Random(20260820).sample(
        [(q["id"], r["run"]) for q in corpus["questions"] for r in byq.get(q["id"], [])],
        k=max(1, int(0.2 * sum(len(v) for v in byq.values()))),
    )
    report = {
        "floors": floors, "gate": all(f["pass"] for f in floors.values()),
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
