#!/usr/bin/env python3
"""KBLI editorial regen — independent grading pass (generator != grader).

Terra (OpenAI) wrote the drafts; Claude grades them (cross-vendor, per the
4-LLM-panel doctrine). Deterministic gates (G2-G6 shape/L10/L3/fabrication
regex) already run every reconcile tick via kbli_apply_editorials --dry-run —
this grader covers what regexes cannot: fidelity of the English body to the
Indonesian scope text, fabrications beyond regex reach, and editorial quality.

Sampling: stride-N stratified over the sorted code list (default 10 -> ~11%,
every sector hit). Batches B drafts per claude call (default 5) to spare quota.

Usage:
  python3 grade_editorials.py [--stride 10] [--batch 5] [--model claude-sonnet-5]
                              [--out grades.jsonl] [--limit 0]

Output: JSONL, one line per graded code:
  {"code", "fidelity", "fabrication_free", "quality", "verdict", "notes"}
scores 1-5 (5 best); verdict in {PASS, WARN, FAIL}. Exit 0 always (report tool);
the consumer decides. Resumable: codes already in --out are skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DRAFTS = HERE / "editorial_drafts"

RUBRIC = """You are an independent grader for KBLI editorial drafts. The WRITER was a
different model; be adversarial, not charitable. For EACH item below you get the SLIM
RECORD (the only source of truth the writer had) and the DRAFT it produced.

Grade each item on three axes, 1-5 (5 = best):
- fidelity: does the English body faithfully render the Indonesian scope_id and the
  record's national-vs-Bali facts (pma_status, pma_max_asing, l4_bali_*)? Omissions of
  the core picture or mistranslations lower this.
- fabrication_free: 5 = every claim traceable to a record field; ANY invented obligation,
  licence, capital figure, timeline, tax, neighbouring-code mention, or number not in the
  record drops this to 2 or 1. Translating/synthesising record content is NOT fabrication.
- quality: magazine-grade prose? headline a real title? standfirst a real dek? body
  coherent 3-4 paragraphs, not listicle, not padded?

verdict: FAIL if fabrication_free <= 2 OR fidelity <= 2; WARN if any axis == 3;
else PASS. notes: one short sentence, only what a fixer would need.

Reply with ONLY a JSON array, one object per item, same order:
[{"code": "...", "fidelity": N, "fabrication_free": N, "quality": N,
  "verdict": "PASS|WARN|FAIL", "notes": "..."}]

ITEMS:
"""


def load_rows() -> dict:
    raw = json.loads(DATASET.read_text())
    rows = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    return {str(r.get("kode_kbli_2025")): r for r in rows}


def slim(rec: dict) -> dict:
    # mirror of editorial_writer.slim — the grader must see exactly what the writer saw
    l4 = rec.get("l4_bali") or {}
    mor = l4.get("moratorium") or {}
    parts = []
    if rec.get("uraian"):
        parts.append(str(rec["uraian"]))
    for rl in (rec.get("ruang_lingkup") or [])[:2]:
        u = rl.get("uraian")
        if u and u not in parts:
            parts.append(str(u))
    scales = []
    for v in rec.get("per_skala") or []:
        for sc in v.get("skala_usaha") or []:
            if sc not in scales:
                scales.append(sc)
    return {
        "code": str(rec.get("kode_kbli_2025")),
        "judul": rec.get("judul"),
        "scope_id": "\n".join(parts)[:1600],
        "pma_status": rec.get("pma_status"),
        "pma_max_asing": rec.get("pma_max_asing"),
        "pma_source": rec.get("pma_source"),
        "scales_open_to": scales,
        "l4_bali_status": l4.get("status"),
        "l4_bali_blocked": bool(l4.get("blocked")),
        "l4_bali_reason": l4.get("reason"),
        "bali_moratorium_rule": mor.get("rule"),
    }


def extract_json_array(text: str) -> list | None:
    for blob in reversed(re.findall(r"\[.*\]", text, re.S)):
        try:
            arr = json.loads(blob)
            if isinstance(arr, list) and all(isinstance(x, dict) and "code" in x for x in arr):
                return arr
        except Exception:
            continue
    return None


def grade_batch(batch: list[tuple[dict, dict]], model: str) -> list | None:
    items = [{"slim_record": s, "draft": d} for s, d in batch]
    prompt = RUBRIC + json.dumps(items, ensure_ascii=False)
    try:
        p = subprocess.run(
            ["claude", "--print", "--model", model, prompt],
            capture_output=True, text=True, timeout=600,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        sys.stderr.write(f"claude exit {p.returncode}: {(p.stderr or '')[-300:]}\n")
        return None
    return extract_json_array(p.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--batch", type=int, default=5)
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--out", default=str(HERE / "grades.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = load_rows()
    out_path = Path(args.out)
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                done.add(json.loads(line)["code"])
            except Exception:
                continue

    codes = sorted(p.stem for p in DRAFTS.glob("[0-9]*.json"))
    sample = [c for c in codes[:: args.stride] if c in rows and c not in done]
    if args.limit:
        sample = sample[: args.limit]
    print(f"grader: {len(sample)} to grade (stride {args.stride}, "
          f"{len(done)} already in {out_path.name}), model {args.model}", flush=True)

    graded = failed = 0
    for i in range(0, len(sample), args.batch):
        chunk = sample[i : i + args.batch]
        batch = []
        for c in chunk:
            try:
                draft = json.loads((DRAFTS / f"{c}.json").read_text())["editorial"]
            except Exception:
                continue
            batch.append((slim(rows[c]), draft))
        if not batch:
            continue
        verdicts = grade_batch(batch, args.model)
        if verdicts is None:
            failed += len(batch)
            print(f"  batch {chunk[0]}..{chunk[-1]}: grader call failed, skipping", flush=True)
            time.sleep(10)
            continue
        with out_path.open("a") as f:
            for v in verdicts:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
        graded += len(verdicts)
        fails = [v["code"] for v in verdicts if v.get("verdict") == "FAIL"]
        print(f"  {graded}/{len(sample)} graded"
              + (f"  FAIL: {','.join(fails)}" if fails else ""), flush=True)
    print(f"grader done: graded={graded} call_failures={failed} -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
