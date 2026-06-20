#!/usr/bin/env python3
"""
Merge validated L3 editorial (DeepSeek, fact-gated PASS) into KBLI_2025_FINAL_CLEAN.json.

The generators (kbli_l3_generate.py) emitted records with the simpler editorial schema
  {whatItMeans, baliReality, whoThisIsFor}
but the frontend (apps/mouth/src/app/kbli/[code]/page.tsx) and the 504 already-merged
records use the richer intel_2026 schema
  {whatItMeans, whatYouNeed, whatChanged, baliContext, zantaraOpener, whoThisIsFor, _l3_regen}.

A naive copy would render half-empty pages (whatYouNeed / whatChanged blank). This script
applies a faithful FIELD SHIM, deriving the missing fields from facts ALREADY in FINAL_CLEAN
(L0/L2/L4) — never inventing:
  - whatYouNeed   <- baliReality (the national-vs-Bali registrability prose)
  - whatChanged   <- synthesized from status_mapping (MATCH_LANGSUNG => "Direct 1:1 match
                     from KBLI 2020 — code and scope unchanged."; else a neutral note)
  - baliContext   <- l4_bali.reason (verbatim authoritative Bali reason)
  - zantaraOpener <- composed from judul + risk + pma_status (same template as the 504)

Idempotent: only fills MUTE records (no existing intel_2026.whatItMeans). Never overwrites
the curated 504 or gold content. Provenance stamped (_l3_regen, confidence LOW, fact_gate PASS).

DRY-RUN by default; --apply writes the file.
"""
import json, os, sys, argparse

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = f"{WT}/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
GEN_CORE = f"{WT}/data/kbli_schema_v2/_l3_generated.json"
GEN_NONCORE = f"{WT}/data/kbli_schema_v2/_l3_generated_noncore.json"
KEY = "kode_kbli_2025"

RISK_LABEL = {  # status_mapping / kategori risk surfaces vary; keep generic, fact-anchored
}


def synth_what_changed(rec):
    sm = rec.get("status_mapping")
    if sm == "MATCH_LANGSUNG":
        return "Direct 1:1 match from KBLI 2020 — code and scope unchanged."
    if isinstance(sm, str) and sm:
        return f"KBLI 2020→2025 mapping: {sm.replace('_', ' ').lower()}."
    return ""


def synth_zantara_opener(rec):
    judul = rec.get("judul") or ""
    kode = rec.get(KEY)
    pma = rec.get("pma_status") or ""
    pma_h = {"TERBUKA": "Open", "TERTUTUP": "Closed", "TERBATAS": "Restricted"}.get(pma, pma)
    base = f"Looking into {judul} ({kode})?"
    if pma_h:
        base += f" Nationally this carries PMA status: {pma_h}."
    return (base + " Let me walk you through what it means for a foreign-owned setup.").strip()


def shim(gen_intel, fc_rec):
    """Map the simple generated schema -> rich intel_2026 schema, deriving missing fields
    only from facts already present in fc_rec (FINAL_CLEAN)."""
    l4 = fc_rec.get("l4_bali") or {}
    return {
        "whatItMeans": gen_intel.get("whatItMeans", ""),
        "whatYouNeed": gen_intel.get("baliReality", ""),
        "whatChanged": synth_what_changed(fc_rec),
        "baliContext": l4.get("reason", "") or "",
        "zantaraOpener": synth_zantara_opener(fc_rec),
        "whoThisIsFor": gen_intel.get("whoThisIsFor", ""),
        "_l3_regen": {
            "source": "LLM_EDITORIAL_GROUNDED",
            "model": "deepseek-v4-pro",
            "confidence": "LOW",
            "fact_gate": "PASS",
            "regen": "2026-06-21-merge",
        },
    }


def load_pass(path):
    out = {}
    if not os.path.exists(path):
        return out
    for k, v in json.load(open(path)).items():
        if v.get("provenance", {}).get("fact_gate") == "PASS" and v.get("intel"):
            out[str(k)] = v["intel"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    fc = json.load(open(FINAL))
    data = fc.get("data", fc)
    by_code = {str(r.get(KEY)): r for r in data}

    gen = {}
    gen.update(load_pass(GEN_CORE))
    gen.update(load_pass(GEN_NONCORE))
    print(f"FINAL_CLEAN records: {len(data)}")
    print(f"generated PASS pool: {len(gen)}")

    filled = skipped_has_intel = missing_in_fc = 0
    for code, gintel in gen.items():
        rec = by_code.get(code)
        if rec is None:
            missing_in_fc += 1
            continue
        if (rec.get("intel_2026") or {}).get("whatItMeans"):
            skipped_has_intel += 1  # never overwrite curated/gold
            continue
        rec["intel_2026"] = shim(gintel, rec)
        filled += 1

    mute_after = sum(1 for r in data if not (r.get("intel_2026") or {}).get("whatItMeans"))
    print(f"FILLED: {filled}")
    print(f"skipped (already had intel): {skipped_has_intel}")
    print(f"generated codes not in FINAL_CLEAN: {missing_in_fc}")
    print(f"MUTE remaining after merge: {mute_after}")

    if args.apply:
        json.dump(fc, open(FINAL, "w"), ensure_ascii=False, indent=1)
        print(f"WROTE {FINAL}")
    else:
        print("DRY-RUN (use --apply to write)")
        # show one shimmed sample
        for code in list(gen)[:1]:
            r = by_code.get(code)
            if r and r.get("intel_2026"):
                print("\nSAMPLE shimmed", code, ":")
                for k, v in r["intel_2026"].items():
                    print(f"  {k}: {str(v)[:140]}")


if __name__ == "__main__":
    main()
