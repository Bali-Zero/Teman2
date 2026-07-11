#!/usr/bin/env python3
"""
Paraphrase the raw-Indonesian `intel_2026.whatItMeans` into clean English for the 200 KBLI
navigator records whose whatItMeans still contains the official OSS uraian verbatim ("Kelompok ...").

Why: 200 of 1559 records in apps/mouth/data/KBLI_2025_FINAL_CLEAN.json serve English readers a
whatItMeans that is (partly or wholly) untranslated Indonesian — the official "Kelompok ini
mencakup ..." uraian. Factually correct, reads badly. This rewrites ONLY whatItMeans into a
faithful 2-3 sentence English paraphrase. Every other field is left byte-identical.

Pattern reuse: same DeepSeek-call + fact-gate approach as scripts/kbli_l3_generate.py
(key in ~/.openclaw/workspace/.env.master, model deepseek-v4-pro, curl subprocess, JSON parse,
fact_gate rejecting any output that introduces a foreign KBLI code).

Safety:
- FACT-GATE each result. REJECT if the paraphrase introduces a KBLI code (\d{4,5}) that is not the
  record's own code (years 19xx/20xx allowed), OR is empty / too short (<40 chars). On REJECT the
  ORIGINAL whatItMeans is KEPT (never blanked).
- Idempotent: a record already marked `_l3_regen.paraphrased` is skipped on re-run, and any record
  whose whatItMeans no longer contains "Kelompok" is not a candidate.
- Checkpoint every 25 processed records (writes back to disk in --apply mode).
- DRY-RUN by default. --apply writes. --limit N for a small test slice.

Traceability: each rewritten record gets `intel_2026._l3_regen.paraphrased = "2026-06-21"`. If the
record has no `_l3_regen` (140 of 200 don't), a minimal one is created carrying only that marker so
the edit is auditable; existing _l3_regen fields are preserved.

KBLI = public economic classification. ZERO PII. DeepSeek V4 Pro pre-authorized (~$0.01/q).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = f"{WT}/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"

URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-pro"
PARAPHRASE_DATE = "2026-06-21"
MIN_LEN = 40
CANDIDATE_MARKER = "Kelompok"


def key():
    k = os.environ.get("DEEPSEEK_API_KEY")
    if k:
        return k
    path = os.path.expanduser("~/.openclaw/workspace/.env.master")
    for line in open(path):
        line = line.strip()
        if line.startswith(("export DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEY=")):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no DEEPSEEK key")


KEY = key()

SYS = (
    "You translate and paraphrase Indonesian business-activity descriptions (the official KBLI "
    "uraian) into clean, faithful English for foreign readers of a business-setup navigator.\n\n"
    "Translate/paraphrase the given Indonesian description into 2-3 clear English sentences "
    "describing what the activity covers. Output ONLY the English text, no preamble, no quotes, "
    "no markdown.\n\n"
    "HARD RULES:\n"
    "- Be faithful to the source. Do NOT invent details, do NOT add prices, laws, processing "
    "days, or KBLI code numbers that are not already in the source text.\n"
    "- Do NOT include the literal word 'Kelompok' or copy Indonesian phrases verbatim — render "
    "them in natural English.\n"
    "- Keep it concise: 2-3 sentences, plain professional English."
)


def source_text(rec):
    """The Indonesian uraian to paraphrase. Prefer the top-level `uraian` (cleanest), fall back to
    the whatItMeans body itself. Strip an English lead-in like 'This KBLI covers ... Officially:'
    so we hand DeepSeek the Indonesian, not a half-translated mix."""
    uraian = rec.get("uraian")
    if isinstance(uraian, str) and uraian.strip():
        return uraian.strip()[:1200]
    wim = rec["intel_2026"]["whatItMeans"]
    # drop an "Officially:" English preamble if present
    if "Officially:" in wim:
        wim = wim.split("Officially:", 1)[1]
    return wim.strip()[:1200]


OTHER_CODE_RE = re.compile(r"\b\d{4,5}\b")


def _is_year(c):
    return len(c) == 4 and (c.startswith("19") or c.startswith("20"))


def fact_gate(english, kode, source):
    """Reject if the paraphrase introduces a KBLI code not in {own code} ∪ {codes already in the
    source uraian}, or if it is empty / too short. (Years 19xx/20xx are allowed.)"""
    if not isinstance(english, str):
        return {"ok": False, "reason": "non-string output"}
    english = english.strip()
    if len(english) < MIN_LEN:
        return {"ok": False, "reason": f"too short ({len(english)} chars)"}
    if CANDIDATE_MARKER in english:
        return {"ok": False, "reason": "still contains Indonesian 'Kelompok'"}
    source_codes = {c for c in OTHER_CODE_RE.findall(source or "") if not _is_year(c)}
    allowed = {kode} | source_codes
    foreign = {c for c in OTHER_CODE_RE.findall(english) if not _is_year(c) and c not in allowed}
    if foreign:
        return {"ok": False, "reason": f"introduced foreign codes {sorted(foreign)}"}
    return {"ok": True}


def call(rec):
    kode = rec["kode_kbli_2025"]
    src = source_text(rec)
    payload = {
        "model": MODEL,
        "reasoning_effort": "low",
        "stream": False,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": src},
        ],
    }
    for attempt in range(3):
        r = subprocess.run(
            ["curl", "-sS", "-m", "120", URL, "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {KEY}", "-d", json.dumps(payload)],
            capture_output=True, text=True,
        )
        try:
            content = json.loads(r.stdout)["choices"][0]["message"]["content"]
            content = re.sub(r"^```[a-z]*|```$", "", content.strip()).strip().strip('"').strip()
            verdict = fact_gate(content, kode, src)
            return kode, content, verdict
        except Exception:
            if attempt == 2:
                return kode, None, {"ok": False, "reason": "parse/api fail"}
            time.sleep(1.5 * (attempt + 1))


def is_candidate(rec):
    intel = rec.get("intel_2026")
    if not isinstance(intel, dict):
        return False
    wim = intel.get("whatItMeans")
    if not isinstance(wim, str):
        return False
    if CANDIDATE_MARKER not in wim:
        return False
    # idempotency: already paraphrased in a prior run -> not a candidate
    l3 = intel.get("_l3_regen")
    if isinstance(l3, dict) and l3.get("paraphrased"):
        return False
    return True


def mark_paraphrased(intel):
    l3 = intel.get("_l3_regen")
    if isinstance(l3, dict):
        l3["paraphrased"] = PARAPHRASE_DATE
    else:
        intel["_l3_regen"] = {
            "source": "PARAPHRASE_EN",
            "model": MODEL,
            "paraphrased": PARAPHRASE_DATE,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="process at most N candidates (test)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    doc = json.load(open(TARGET))
    data = doc["data"]
    by_code = {}
    for r in data:
        by_code.setdefault(r["kode_kbli_2025"], r)

    cands = [r for r in data if is_candidate(r)]
    print(f"records: {len(data)} | candidates (Kelompok in whatItMeans, not yet paraphrased): "
          f"{len(cands)}", flush=True)
    if args.limit:
        cands = cands[:args.limit]
        print(f"--limit -> processing {len(cands)}", flush=True)

    if not args.apply:
        print("DRY-RUN: no DeepSeek calls, no writes. Re-run with --apply to rewrite.", flush=True)
        for r in cands[:3]:
            print(f"  would rewrite {r['kode_kbli_2025']}: "
                  f"{r['intel_2026']['whatItMeans'][:90]!r} ...", flush=True)
        print(f"DRY-RUN candidate count = {len(cands)}", flush=True)
        return

    rewritten = 0
    rejected = 0
    processed = 0

    def checkpoint():
        json.dump(doc, open(TARGET, "w"), ensure_ascii=False, indent=1)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(call, r): r["kode_kbli_2025"] for r in cands}
        for f in as_completed(futs):
            kode, english, verdict = f.result()
            processed += 1
            rec = by_code[kode]
            intel = rec["intel_2026"]
            if verdict.get("ok") and english:
                intel["whatItMeans"] = english
                mark_paraphrased(intel)
                rewritten += 1
            else:
                # KEEP original whatItMeans; do NOT mark paraphrased (so it stays a re-runnable
                # candidate). Record the reject reason for audit on the rejects list.
                rejected += 1
                print(f"  REJECT {kode}: {verdict.get('reason')}", flush=True)
            if processed % 25 == 0:
                checkpoint()
                print(f"  checkpoint {processed}/{len(cands)} | rewritten={rewritten} "
                      f"rejected={rejected}", flush=True)

    checkpoint()
    print(f"DONE: processed={processed} rewritten={rewritten} rejected(kept original)={rejected} "
          f"-> {TARGET}", flush=True)


if __name__ == "__main__":
    main()
