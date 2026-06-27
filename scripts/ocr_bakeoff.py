#!/usr/bin/env python3
"""Local OCR model bake-off for Indonesian identity documents.

Runs N local vision models over the SAME real-document gold-set with the SAME
JSON-schema prompt, against Ollama localhost (Law 2: documents never leave the
machine). Captures per-doc latency + extracted JSON.

PII discipline: full model outputs (which contain real NIK/passport/NPWP) are
written ONLY to a local results file on this machine for hand-scoring. STDOUT
prints AGGREGATE metrics only — never a raw field value. The operator scores
high-stakes fields by opening the local results file directly.

Usage (on the Pro):
    python scripts/ocr_bakeoff.py --goldset ~/bakeoff-goldset \
        --models qwen2.5vl:7b qwen3-vl:8b glm-ocr \
        --out ~/bakeoff-results.jsonl
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

import httpx

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# One fixed schema prompt for every model + every doc — the only fair comparison.
PROMPT = (
    "You are an OCR + structured-extraction engine for Indonesian official "
    "documents (KTP, passport, NPWP, NIB, KITAS/KITAP, akta). Read the image and "
    "return ONLY a single JSON object, no prose, no markdown fence. Use these keys "
    "when present, else omit: doc_type, nama, nik, no_passport, npwp, no_kitas, "
    "tempat_lahir, tanggal_lahir, alamat, kewarganegaraan, masa_berlaku, "
    "jenis_kelamin, pekerjaan. Transcribe values EXACTLY as printed. If a field is "
    "unreadable, set it to null. Do not invent digits."
)

# High-stakes fields: a single wrong digit here is a real-world error.
CRITICAL_FIELDS = ("nik", "no_passport", "npwp", "no_kitas", "tanggal_lahir", "masa_berlaku")


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _run_one(client: httpx.Client, model: str, img_b64: str) -> dict:
    t0 = time.time()
    try:
        r = client.post(
            f"{OLLAMA}/api/generate",
            json={
                "model": model,
                "prompt": PROMPT,
                "images": [img_b64],
                "stream": False,
                "think": False,  # required for non-thinking determinism (qwen)
                "options": {"temperature": 0.0},
            },
            timeout=180,
        )
        r.raise_for_status()
        resp = r.json().get("response", "")
        ok = True
        err = None
    except Exception as exc:  # noqa: BLE001 — bake-off harness, capture everything
        resp = ""
        ok = False
        err = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - t0, 2)
    # try to parse a JSON object out of the response
    parsed = None
    if resp:
        s = resp.strip()
        # strip accidental ```json fences
        if s.startswith("```"):
            s = s.split("```")[1] if "```" in s[3:] else s.lstrip("`")
            s = s[4:] if s.lower().startswith("json") else s
        a, b = s.find("{"), s.rfind("}")
        if a != -1 and b != -1:
            try:
                parsed = json.loads(s[a : b + 1])
            except json.JSONDecodeError:
                parsed = None
    return {
        "elapsed_s": elapsed,
        "ok": ok,
        "error": err,
        "raw_len": len(resp),
        "json_valid": parsed is not None,
        "parsed": parsed,
        "raw": resp,
    }


def _metrics(parsed: dict | None) -> dict:
    if not parsed:
        return {"fields": 0, "critical_present": 0, "doc_type": None}
    fields = sum(1 for v in parsed.values() if v not in (None, "", "null"))
    crit = sum(1 for k in CRITICAL_FIELDS if parsed.get(k) not in (None, "", "null"))
    return {"fields": fields, "critical_present": crit, "doc_type": parsed.get("doc_type")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldset", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", required=True, help="local JSONL results (PII — stays on host)")
    args = ap.parse_args()

    gold = sorted(
        p
        for p in Path(args.goldset).expanduser().iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )
    out_path = Path(args.out).expanduser()
    out_f = out_path.open("w")

    print(f"=== OCR bake-off: {len(gold)} docs x {len(args.models)} models ===")
    print(f"  models: {', '.join(args.models)}")
    print(f"  full outputs (PII) -> {out_path}  (LOCAL, hand-score there)\n")

    # aggregate accumulators per model
    agg: dict[str, dict] = {m: {"t": 0.0, "n": 0, "valid": 0, "fields": 0, "crit": 0, "fail": 0} for m in args.models}

    # Model-major loop: load ONE vision model, run it over the whole gold-set,
    # then move on. This caps GPU model-loads at len(models) instead of
    # len(docs)*len(models) — critical when a 32B sibling (SEA-LION) contends
    # for the same GPU. First call per model warms it (cold-load); we flag it.
    results: dict[str, dict] = {doc.stem: {"doc": doc.stem, "size_kb": round(doc.stat().st_size / 1024)} for doc in gold}
    with httpx.Client() as client:
        for m in args.models:
            print(f"\n--- model: {m} (first doc = cold-load, warm after) ---")
            for idx, doc in enumerate(gold):
                img = _b64(doc)
                res = _run_one(client, m, img)
                met = _metrics(res["parsed"])
                cold = idx == 0
                results[doc.stem][m] = {
                    **{k: res[k] for k in ("elapsed_s", "ok", "json_valid", "raw_len", "error")},
                    **met, "cold": cold, "raw": res["raw"], "parsed": res["parsed"],
                }
                a = agg[m]
                # exclude cold-load from latency average (it's not representative)
                if not cold:
                    a["t"] += res["elapsed_s"]; a["n"] += 1
                a["valid"] += int(res["json_valid"]); a["fields"] += met["fields"]; a["crit"] += met["critical_present"]
                a["fail"] += int(not res["ok"])
                tag = "COLD" if cold else f"{res['elapsed_s']:>5}s"
                print(f"  {doc.stem:<20} {tag:>7} f={met['fields']:<2} c={met['critical_present']} {'✓json' if res['json_valid'] else '✗json'} dt={str(met['doc_type'])[:10]}{'' if res['ok'] else '  ERR:'+str(res['error'])[:40]}")
    for stem, line in results.items():
        out_f.write(json.dumps(line) + "\n")
    out_f.flush()

    out_f.close()
    print("\n=== AGGREGATE (PII-safe) ===")
    print(f"  {'model':<16} {'avg_s':>7} {'json_ok':>8} {'avg_fields':>11} {'avg_crit':>9} {'fails':>6}")
    for m in args.models:
        a = agg[m]; n = max(1, a["n"])
        print(f"  {m:<16} {a['t']/n:>7.1f} {a['valid']}/{a['n']:>6} {a['fields']/n:>11.1f} {a['crit']/n:>9.1f} {a['fail']:>6}")
    print(f"\n  -> hand-score critical fields (NIK/passport/NPWP/dates) in {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
