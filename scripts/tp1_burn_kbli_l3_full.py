#!/usr/bin/env python3
"""Burn lane 1: L3 editorial for the FULL KBLI 2025 schema, grounded + fact-gated.

Extends scripts/kbli_l3_generate.py (core gaps only) to every schema record,
for the 2026-10 TP1 quota-burn cycle (Zero GO 2026-10-05). Same anti-presumption
contract: the model EXPLAINS facts already in the schema, the fact-gate rejects
anything that invents codes or contradicts the Bali status.

Output is a SEPARATE draft queue (_l3_generated_burn_oct26.json): the canonical
_l3_generated.json and the curated KBLI datasets (data-plane guard, AGENTS.md
§0.0.5) are never written by this runner. A canonical writer merges later.

Model follows the window: qwen3.8-max + effort high at night (Night 50% Off),
qwen3.7-plus + effort low by day. Guard: tp1_burn_common.BurnGuard caps.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepseek_client import complete, DeepSeekBudgetExceeded  # noqa: E402
from kbli_l3_generate import SYS, fact_gate  # noqa: E402
from tp1_burn_common import BurnGuard, window_effort, window_model  # noqa: E402

import kbli_l3_generate as kg  # noqa: E402

SCHEMA = kg.SCHEMA
DONE_CANON = kg.OUT
OUT = f"{kg.WT}/data/kbli_schema_v2/_l3_generated_burn_oct26.json"


def call(rec, guard):
    kode = rec["kode"]
    l0 = rec["l0_ground_truth"]
    l2 = rec.get("l2_compliance_national") or {}
    l4 = rec["l4_bali"]["bali_status"]["value"]
    pma = l2.get("pma") or {}
    facts = {
        "kode": kode,
        "judul": l0["judul_id"]["value"],
        "uraian": l0["uraian_id"]["value"][:600],
        "pma_national": f"{(pma.get('pma_status') or {}).get('value')} {(pma.get('pma_max_asing') or {}).get('value')}%",
        "bali_status": l4["status"],
        "bali_reason": l4.get("reason", ""),
    }
    for attempt in range(3):
        model = window_model()
        try:
            result = complete(
                json.dumps(facts, ensure_ascii=False),
                system=SYS,
                model=model,
                reasoning_effort=window_effort(),
                timeout=180,
                purpose="burn-kbli-l3",
            )
            guard.add(result.usage)
            import re as _re
            content = _re.sub(r"^```json|```$", "", result.text.strip()).strip()
            obj = json.loads(content)
            return kode, obj, fact_gate(obj, kode, l4["status"]), model
        except DeepSeekBudgetExceeded:
            raise
        except Exception:
            if attempt == 2:
                return kode, None, {"ok": False, "reason": "parse/api fail"}, model
            time.sleep(1.5 * (attempt + 1))
    return kode, None, {"ok": False, "reason": "unreachable"}, "unknown"


def main():
    workers = int(os.environ.get("BURN_WORKERS", "16"))
    guard = BurnGuard()
    schema = json.load(open(SCHEMA))
    recs = {r["kode"]: r for r in schema["records"]}
    done = {}
    for path in (DONE_CANON, OUT):
        if os.path.exists(path):
            done.update(json.load(open(path)))
    todo = [k for k in recs if k not in done]
    print(f"burn-kbli-l3: {len(recs)} records, {len(done)} done, {len(todo)} todo, "
          f"workers={workers} cap={guard.stats()}", flush=True)

    results = {}
    if os.path.exists(OUT):
        results = json.load(open(OUT))
    rejected = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for k in todo:
            if not guard.ok():
                print("burn guard cap reached — stopping submission", flush=True)
                break
            futs[ex.submit(call, recs[k], guard)] = k
        n = 0
        for f in as_completed(futs):
            kode, obj, verdict, model = f.result()
            n += 1
            if verdict.get("ok") and obj:
                results[kode] = {"intel": obj, "provenance": {"source": "LLM_EDITORIAL",
                                 "model": model, "confidence": "LOW", "fact_gate": "PASS",
                                 "generated": "2026-10-05", "lane": "tp1-burn"}}
            else:
                rejected += 1
                results[kode] = {"intel": None, "provenance": {"fact_gate": "REJECT",
                                 "reason": verdict.get("reason")}}
            if n % 40 == 0:
                json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
                print(f"  {n}/{len(todo)} | rejected={rejected} | {guard.stats()}", flush=True)
            if not guard.ok():
                print("burn guard cap reached mid-run — draining", flush=True)
                break
    json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in results.values() if v.get("provenance", {}).get("fact_gate") == "PASS")
    print(f"DONE burn-kbli-l3: {len(results)} processed, PASS={ok}, REJECT={rejected} "
          f"| {guard.stats()} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
