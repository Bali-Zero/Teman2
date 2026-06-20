#!/usr/bin/env python3
"""
Generate L3 editorial for CORE-sector KBLI gaps, GROUNDED on schema facts (anti-presumption).

Rules (Zero's mandate: altissima qualità + safety):
- The LLM EXPLAINS facts already in the schema (L0 uraian + L2 PMA/risk + L4 Bali), never invents them.
- Each generated record carries provenance + confidence=LOW + a fact-gate verdict.
- FACT-GATE: reject any output that introduces a KBLI code not equal to the target (Gemini's bug),
  or that contradicts the L4 Bali status. Rejected → left as gap, never written as fact.
- Batched, background-safe, idempotent (skips already-done), proxy-bypass.
"""
import json, os, sys, re, time, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = f"{WT}/data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json"
GAPS = f"{WT}/data/kbli_schema_v2/_l3_gaps_core.json"
OUT = f"{WT}/data/kbli_schema_v2/_l3_generated.json"

URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-pro"

def key():
    k = os.environ.get("DEEPSEEK_API_KEY")
    if k: return k
    for line in open(os.path.expanduser("~/.openclaw/workspace/.env.master")):
        line = line.strip()
        if line.startswith(("export DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEY=")):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no DEEPSEEK key")
KEY = key()

SYS = """You are a senior Indonesian business-setup advisor writing for FOREIGN entrepreneurs in Bali.
You are given the OFFICIAL facts about ONE KBLI 2025 code (title, official description, national PMA
status, risk class, and CRITICALLY the Bali-specific status). Your job is to EXPLAIN these facts in
clear English — NOT to invent new ones.

HARD RULES:
- Do NOT mention any KBLI code number other than the one given. Do NOT invent prices, specific laws,
  or processing days. If you don't have a fact, speak generally ("requires a commercial address").
- The Bali status given is authoritative. If it says BLOCKED/CHIUSO/TERTUTUP, your text MUST reflect
  that a foreign-owned (PMA) company faces that restriction in Bali — do not contradict it.
- Be honest and pragmatic ("Pragmatic Sherpa" voice), warm but not salesy.

Output ONLY valid JSON (no markdown fence):
{"whatItMeans":"2-3 sentences, plain English, what this activity covers (from the description)",
 "baliReality":"2-3 sentences on the Bali registrability reality FROM THE GIVEN STATUS (national vs Bali)",
 "whoThisIsFor":"1 sentence: what kind of foreign entrepreneur this fits"}"""

def call(rec):
    kode = rec["kode"]
    l0 = rec["l0_ground_truth"]; l2 = rec.get("l2_compliance_national") or {}
    l4 = rec["l4_bali"]["bali_status"]["value"]
    pma = (l2.get("pma") or {})
    facts = {
        "kode": kode,
        "judul": l0["judul_id"]["value"],
        "uraian": l0["uraian_id"]["value"][:600],
        "pma_national": f"{(pma.get('pma_status') or {}).get('value')} {(pma.get('pma_max_asing') or {}).get('value')}%",
        "bali_status": l4["status"],
        "bali_reason": l4.get("reason", ""),
    }
    payload = {"model": MODEL, "reasoning_effort": "low", "stream": False,
               "messages": [{"role": "system", "content": SYS},
                            {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}]}
    for attempt in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "120", URL, "-H", "Content-Type: application/json",
                            "-H", f"Authorization: Bearer {KEY}", "-d", json.dumps(payload)],
                           capture_output=True, text=True)
        try:
            content = json.loads(r.stdout)["choices"][0]["message"]["content"]
            content = re.sub(r"^```json|```$", "", content.strip()).strip()
            obj = json.loads(content)
            verdict = fact_gate(obj, kode, l4["status"])
            return kode, obj, verdict
        except Exception:
            if attempt == 2:
                return kode, None, {"ok": False, "reason": "parse/api fail"}
            time.sleep(1.5 * (attempt + 1))

OTHER_CODE_RE = re.compile(r"\b\d{4,5}\b")
def _is_year(c):
    return len(c) == 4 and (c.startswith("19") or c.startswith("20"))
def fact_gate(obj, kode, bali_status):
    """Reject if it invents another KBLI code or contradicts Bali status. Years (19xx/20xx) are OK."""
    text = " ".join(str(v) for v in obj.values())
    foreign_codes = {c for c in OTHER_CODE_RE.findall(text)
                     if c != kode and len(c) >= 4 and not _is_year(c)}
    if foreign_codes:
        return {"ok": False, "reason": f"introduced foreign codes {foreign_codes}"}
    # contradiction check: blocked status but text says "open/allowed for foreigners" without caveat
    blocked = any(s in bali_status for s in ("BLOCCATO", "CHIUSO", "TERTUTUP", "TERBATAS"))
    low = obj.get("baliReality", "").lower()
    if blocked and ("100% foreign" in low or "fully open in bali" in low) and "but" not in low and "however" not in low:
        return {"ok": False, "reason": "contradicts blocked Bali status"}
    return {"ok": True}

def main():
    schema = json.load(open(SCHEMA))
    recs = {r["kode"]: r for r in schema["records"]}
    gaps = json.load(open(GAPS))
    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT))
    todo = [g for g in gaps if g not in done]
    print(f"L3 gen: {len(gaps)} core gaps, {len(done)} already done, {len(todo)} to do", flush=True)

    results = dict(done)
    rejected = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(call, recs[g]): g for g in todo if g in recs}
        n = 0
        for f in as_completed(futs):
            kode, obj, verdict = f.result()
            n += 1
            if verdict.get("ok") and obj:
                results[kode] = {"intel": obj, "provenance": {"source": "LLM_EDITORIAL",
                                 "model": MODEL, "confidence": "LOW", "fact_gate": "PASS",
                                 "generated": "2026-06-19"}}
            else:
                rejected += 1
                results[kode] = {"intel": None, "provenance": {"fact_gate": "REJECT",
                                 "reason": verdict.get("reason")}}
            if n % 40 == 0:
                json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)  # checkpoint
                print(f"  {n}/{len(todo)} | rejected={rejected}", flush=True)
    json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in results.values() if v.get("provenance", {}).get("fact_gate") == "PASS")
    print(f"DONE: {len(results)} processed, PASS={ok}, REJECT={rejected} -> {OUT}", flush=True)

if __name__ == "__main__":
    main()
