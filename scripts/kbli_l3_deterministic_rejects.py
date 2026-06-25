#!/usr/bin/env python3
"""
Front A — fill the 60 fact-gate REJECTs with DETERMINISTIC editorial (no LLM).

The DeepSeek L3 generator rejected these 60 codes (53 "contradicts blocked Bali
status", 7 "introduced foreign code") — failures of LLM *phrasing*, not of facts.
Every REJECT code has judul + uraian + pma_status + a precise l4_bali.reason already
in FINAL_CLEAN. So we compose the intel_2026 from those facts via per-status
templates — language-invariant, no foreign-code risk, no contradiction risk.

Same rich schema + provenance as the merge (whatItMeans/whatYouNeed/whatChanged/
baliContext/zantaraOpener/whoThisIsFor + _l3_regen, confidence LOW). Idempotent:
only fills mute records. DRY-RUN by default; --apply writes.
"""
import json, os, sys, argparse

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = f"{WT}/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
GEN_CORE = f"{WT}/data/kbli_schema_v2/_l3_generated.json"
GEN_NONCORE = f"{WT}/data/kbli_schema_v2/_l3_generated_noncore.json"
KEY = "kode_kbli_2025"

PMA_H = {"TERBUKA": "open", "TERTUTUP": "closed", "TERBATAS": "restricted"}

# Per-L4-status "what you need" prose — frames national-open vs Bali, never inventing.
# {jakarta} = a neutral non-Bali reference; status text comes verbatim from the data.
BALI_LINE = {
    "BLOCCATO_CLASSE_RISCHIO":
        "Nationally this activity is {pma} to foreign ownership. In Bali, however, it is currently "
        "blocked for a PT PMA under the 13 May 2026 moratorium, which suspends new foreign-owned "
        "registrations for business lines classified as low / medium-low risk at the large-enterprise "
        "(Besar) scale. A foreign-owned setup is viable outside Bali (e.g. Jakarta); inside Bali this "
        "code is on hold until the moratorium lifts.",
    "CHIUSO_PMA_NO_BESAR":
        "Nationally this activity is {pma} to foreign ownership. But OSS lists no large-enterprise "
        "(Besar) scale for it — it is reserved for micro, small and medium Indonesian enterprises "
        "(Perpres 49/2021). A PT PMA is, by law, a large-scale (Besar) entity, so it cannot register "
        "against this code in Bali. The realistic paths are a domestic structure or an adjacent code "
        "that does carry a Besar scale.",
    "BLOCCATO_DIPENDE_SCOPE":
        "Nationally this activity is {pma} to foreign ownership. In Bali its registrability depends on "
        "scope: the OSS risk class is low on some sub-scopes but higher on others, and only the higher-risk "
        "scope is registrable for a PT PMA under the moratorium. It is conditionally available — only by "
        "declaring the qualifying higher-risk scope. Confirm that scope genuinely fits your operation "
        "before planning a Bali setup.",
    "NEEDS_REVIEW_NO_OSS_SCOPE":
        "Nationally this activity is {pma} to foreign ownership, but it sits under a special sectoral "
        "regime (e.g. OJK / BI / BPOM) rather than the standard OSS risk-based scope. That means Bali "
        "registrability for a PT PMA cannot be read off the moratorium alone — it needs a manual, "
        "sector-specific check with the relevant authority before you commit.",
    "OK_or_HIGHER_RISK":
        "Nationally this activity is {pma} to foreign ownership, and in Bali it is NOT blocked by the "
        "13 May 2026 moratorium — its OSS risk class at the large-enterprise (Besar) scale is "
        "medium-high or high, which the moratorium leaves open. A PT PMA can pursue this code in Bali, "
        "subject to the standard licensing for its risk class.",
}

WHO = {
    "BLOCCATO_CLASSE_RISCHIO":
        "A foreign entrepreneur interested in this line should plan a non-Bali base for now, or wait for the moratorium to lift.",
    "CHIUSO_PMA_NO_BESAR":
        "Best suited to an Indonesian-owned (UMKM) operator; a foreign investor needs an adjacent code or a domestic partner structure.",
    "BLOCCATO_DIPENDE_SCOPE":
        "A foreign entrepreneur whose operation genuinely matches the higher-risk scope — otherwise treat it as blocked in Bali.",
    "NEEDS_REVIEW_NO_OSS_SCOPE":
        "A foreign entrepreneur in a regulated sector who is prepared to clear a sector-specific licensing review before registering.",
    "OK_or_HIGHER_RISK":
        "A foreign entrepreneur who can meet the higher-risk licensing requirements — one of the doors that stays open in Bali.",
}


def short_uraian(u):
    """First sentence of the official ID description, trimmed — used as the factual base."""
    if not u:
        return ""
    s = str(u).strip()
    # cut at first period after ~40 chars, cap length
    cut = s.find(". ", 40)
    if cut != -1:
        s = s[:cut + 1]
    return s[:400]


def what_changed(rec):
    sm = rec.get("status_mapping")
    if sm == "MATCH_LANGSUNG":
        return "Direct 1:1 match from KBLI 2020 — code and scope unchanged."
    if isinstance(sm, str) and sm:
        return f"KBLI 2020→2025 mapping: {sm.replace('_', ' ').lower()}."
    return ""


def compose(rec):
    judul = rec.get("judul") or ""
    kode = rec.get(KEY)
    l4 = rec.get("l4_bali") or {}
    st = l4.get("status")
    pma = PMA_H.get(rec.get("pma_status"), "open")
    uraian = short_uraian(rec.get("uraian"))
    what_it_means = (
        f"This KBLI covers {judul.lower()}." if judul else "This KBLI covers a specific business activity."
    )
    if uraian:
        what_it_means += f" Officially: {uraian}"
    bali = BALI_LINE.get(st, "").format(pma=pma)
    opener = f"Looking into {judul} ({kode})? Here is the honest national-vs-Bali picture before you plan a foreign-owned setup."
    return {
        "whatItMeans": what_it_means[:600],
        "whatYouNeed": bali,
        "whatChanged": what_changed(rec),
        "baliContext": l4.get("reason", "") or "",
        "zantaraOpener": opener,
        "whoThisIsFor": WHO.get(st, ""),
        "_l3_regen": {
            "source": "DETERMINISTIC_GROUNDED",
            "model": "template-from-schema",
            "confidence": "LOW",
            "fact_gate": "DETERMINISTIC",
            "regen": "2026-06-21-front-a",
        },
    }


def reject_codes():
    out = []
    for path in (GEN_CORE, GEN_NONCORE):
        if not os.path.exists(path):
            continue
        for k, v in json.load(open(path)).items():
            if v.get("provenance", {}).get("fact_gate") == "REJECT":
                out.append(str(k))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    fc = json.load(open(FINAL))
    data = fc.get("data", fc)
    by = {str(r.get(KEY)): r for r in data}
    rej = reject_codes()
    print(f"REJECT codes: {len(rej)}")
    filled = skipped = no_template = 0
    for code in rej:
        rec = by.get(code)
        if rec is None:
            continue
        if (rec.get("intel_2026") or {}).get("whatItMeans"):
            skipped += 1
            continue
        st = (rec.get("l4_bali") or {}).get("status")
        if st not in BALI_LINE:
            no_template += 1
            continue
        rec["intel_2026"] = compose(rec)
        filled += 1
    mute = sum(1 for r in data if not (r.get("intel_2026") or {}).get("whatItMeans"))
    print(f"FILLED: {filled}  skipped(had intel): {skipped}  no-template-for-status: {no_template}")
    print(f"MUTE remaining after front A: {mute}")
    if args.apply:
        json.dump(fc, open(FINAL, "w"), ensure_ascii=False, indent=1)
        print(f"WROTE {FINAL}")
    else:
        for code in rej[:1]:
            r = by.get(code)
            if r and r.get("intel_2026", {}).get("_l3_regen", {}).get("regen") == "2026-06-21-front-a":
                print(f"\nSAMPLE {code} [{(r.get('l4_bali') or {}).get('status')}]:")
                for k, v in r["intel_2026"].items():
                    print(f"  {k}: {str(v)[:150]}")
        print("\nDRY-RUN (use --apply to write)")


if __name__ == "__main__":
    main()
