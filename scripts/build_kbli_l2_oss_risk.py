"""Build KBLI L2 from OSS official risk (KbliResikos) + recompute L4-Bali blocks.

Input:
  - /tmp/oss_risk_raw.jsonl  (raw ruang-lingkup/{uuid} dumps, one per code)
  - the L1 dataset (base) at data/source_documents/KBLI_2025_FINAL_CLEAN.json

For each code with scope, rebuild per_skala from the OFFICIAL KbliResikos:
  skala_usaha, kategori_risiko (Resiko), jangka_waktu, perizinan (KbliIzins),
  persyaratan (KbliPersyaratans), kewajiban (KbliKewajibans), kewenangan.
Mark provenance _l2_source = OSS_RBA_resiko. Keep the OLD per_skala under
per_skala_legacy for audit. Codes with no OSS risk (404/no-scope) keep the old
per_skala and are flagged _l2_status="no_oss_risk".

Then RECOMPUTE l4_bali.blocked from the official lowest risk:
  - if any scale is Rendah or Menengah Rendah  -> BLOCCATO_CLASSE_RISCHIO (moratorium)
  - else (Menengah Tinggi / Tinggi only)        -> OK_or_HIGHER_RISK
  - TERTUTUP / TERBATAS / CHIUSO_* statuses are PRESERVED (they are not risk-derived).

Writes a COMPARISON report (old vs new) to stdout. Does NOT write the dataset unless
--apply is passed (Zero must see the divergence first).

Usage:
    python scripts/build_kbli_l2_oss_risk.py            # report only
    python scripts/build_kbli_l2_oss_risk.py --apply    # write the dataset
"""
import argparse, json
from collections import Counter
from pathlib import Path

ROOT = Path("/tmp/kbli-l2-risk")
RAW = Path("/tmp/oss_risk_raw.jsonl")
TARGETS = [
    ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json",
    ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json",
]
BLOCK_RISKS = {"rendah", "menengah rendah"}            # → moratorium blocks PMA Bali
PRESERVE_STATUSES = {"TERTUTUP", "TERBATAS", "CHIUSO_BALI", "CHIUSO_BALI_PROPOSTO",
                     "TERTUTUP_CANDIDATE", "TERBATAS_CANDIDATE"}


def loc(d, lang="id", field="uraian"):
    if not isinstance(d, dict):
        return None
    l = d.get("localization")
    if not isinstance(l, dict):
        return None
    sub = l.get(lang)
    if not isinstance(sub, dict):
        return None
    return sub.get(field)


def parse_per_skala(raw_data):
    """Return list of official per_skala dicts from one code's raw ruang-lingkup payload.

    Each ruang lingkup (scope) is kept SEPARATE — its uraian (the sub-activity the
    PMA declares in the NIB) decides which risk row applies. We tag every per_skala
    row with `scope_index` + `scope_uraian` so the Bali-block verdict can be computed
    per-scope (a PMA is scale Besar by law, so only the Besar row of the CHOSEN scope
    matters). Dedup is per-scope (skala, risk), not global.
    """
    out = []
    for si, rl in enumerate(raw_data.get("data", []) or []):
        scope_uraian = loc(rl) or ""
        seen = set()
        for res in rl.get("KbliResikos", []) or []:
            skala = loc(res.get("SkalaUsaha"))
            risk = loc(res.get("Resiko"))
            if not skala:
                continue
            # normalize "Usaha Mikro" -> "Mikro"
            skala_norm = skala.replace("Usaha ", "").strip()
            key = (skala_norm, risk)
            if key in seen:
                continue
            seen.add(key)
            izin = [loc(x) for x in (res.get("KbliIzins") or []) if loc(x)]
            pers = [loc(x) for x in (res.get("KbliPersyaratans") or []) if loc(x)]
            kew = [loc(x) for x in (res.get("KbliKewajibans") or []) if loc(x)]
            kewn = []
            for k in (res.get("KbliResikoKewenangans") or []):
                kw = k.get("Kewenangan") if isinstance(k, dict) else None
                v = loc(kw) if kw else None
                if v:
                    kewn.append(v)
            out.append({
                "skala_usaha": [skala_norm],
                "kategori_risiko": risk,
                "jangka_waktu": res.get("jangka_waktu") or "",
                "scope_index": si,
                "scope_uraian": scope_uraian,
                "perizinan": izin,
                "persyaratan": pers,
                "kewajiban": kew,
                "kewenangan": kewn,
            })
    return out


def besar_block_verdict(per_skala):
    """Bali moratorium verdict from the OFFICIAL per-scope risk at scale Besar.

    A PMA is scale Besar by law (modal >=10 bn). The OSS computes risk at the
    applicant's scale, so ONLY the Besar row of each scope matters. Per scope:
      - Besar risk in {Rendah, Menengah Rendah}  -> that scope is BLOCKED
      - otherwise                                 -> that scope is OPEN
    Roll up across the code's scopes:
      - every scope with a Besar row is blocked, none open -> "BLOCKED"   (D-all)
      - some scopes blocked, some open                     -> "AMBIGUOUS" (passable
                                                              by declaring the open
                                                              scope, e.g. 47901 PPMSE)
      - no scope blocked at Besar                          -> "OPEN"
      - no Besar row anywhere                              -> "NO_BESAR" (flag)
    """
    blocked_scopes = 0
    open_scopes = 0
    besar_seen = False
    for ps in per_skala:
        if "Besar" not in (ps.get("skala_usaha") or []):
            continue
        besar_seen = True
        r = (ps.get("kategori_risiko") or "").strip().lower()
        if r in BLOCK_RISKS:
            blocked_scopes += 1
        else:
            open_scopes += 1
    if not besar_seen:
        return "NO_BESAR"
    if blocked_scopes and not open_scopes:
        return "BLOCKED"
    if blocked_scopes and open_scopes:
        return "AMBIGUOUS"
    return "OPEN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    raw = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        raw[r["kode"]] = r

    ds = json.loads(TARGETS[0].read_text(encoding="utf-8"))
    records = ds["data"]

    stats = Counter()
    block_changes = []          # codes whose l4 blocked flips
    perskala_fixed = []         # codes whose per_skala scale-count changed
    risk_mismatch = []          # codes whose risk text differs from old

    for rec in records:
        code = str(rec.get("kode_kbli_2025") or "")
        r = raw.get(code)
        old_ps = rec.get("per_skala", []) or []
        old_l4 = rec.get("l4_bali", {}) or {}
        old_status = old_l4.get("status")

        if not r or r.get("status") != 200 or not r.get("data", {}).get("success"):
            stats["no_oss_risk"] += 1
            # 221 codes have no OSS scope (404). Most are special-regime activities
            # (central bank, OJK-regulated finance 64xxx/66xxx, narcotics, radioactive
            # waste, bonded warehouse) that sit OUTSIDE the ordinary RBA flow — the old
            # "BLOCCATO_CLASSE_RISCHIO" is a fictitious risk-derived verdict we cannot
            # re-confirm. Relabel as NEEDS_REVIEW (sectoral check), but PRESERVE the
            # non-risk-derived closed statuses (TERTUTUP/TERBATAS) untouched.
            was_blocked = bool((old_l4 or {}).get("blocked"))
            if args.apply:
                rec["_l2_status"] = "no_oss_risk"
                if old_status not in PRESERVE_STATUSES and was_blocked:
                    rec["_l4_needs_review"] = "no_oss_scope_special_regime"
                    rec["l4_bali"]["status"] = "NEEDS_REVIEW_NO_OSS_SCOPE"
                    rec["l4_bali"]["blocked"] = True  # stay conservative until sectoral check
                    rec["l4_bali"]["reason"] = (
                        "no OSS-RBA scope (special/sectoral regime: OJK/BI/BPOM/etc.) — "
                        "Bali registrability needs manual sectoral verification")
                    stats["needs_review_no_scope_blocked"] += 1
            elif old_status not in PRESERVE_STATUSES and was_blocked:
                stats["needs_review_no_scope_blocked"] += 1
            continue

        new_ps = parse_per_skala(r["data"])
        if not new_ps:
            rec["_l2_status"] = "empty_oss_risk"
            stats["empty_oss_risk"] += 1
            continue

        # scale-count change?
        if len(new_ps) != len(old_ps):
            perskala_fixed.append((code, len(old_ps), len(new_ps)))
        # risk text change (lowest)?
        old_risks = {(p.get("kategori_risiko") or "").lower() for p in old_ps}
        new_risks = {(p.get("kategori_risiko") or "").lower() for p in new_ps}
        if old_risks != new_risks:
            risk_mismatch.append((code, sorted(old_risks), sorted(new_risks)))

        # recompute Bali block (only for risk-derived statuses) using the
        # OFFICIAL per-scope risk at scale Besar (Regola D, chosen by Zero 2026-06-20).
        if old_status not in PRESERVE_STATUSES:
            verdict = besar_block_verdict(new_ps)   # BLOCKED / AMBIGUOUS / OPEN / NO_BESAR
            new_blocked = verdict == "BLOCKED"       # binary block flag (D-all)
            new_l4_status = {
                "BLOCKED": "BLOCCATO_CLASSE_RISCHIO",
                "AMBIGUOUS": "BLOCCATO_DIPENDE_SCOPE",
                "OPEN": "OK_or_HIGHER_RISK",
                # no Besar row at all = activity reserved for UMKM (Perpres 49/2021 Annex II);
                # a PMA (Besar by law) cannot register it. NB-3 verbatim: "unavailable / fails
                # validation for a PT PMA profile". This is a CLOSURE, not openness.
                "NO_BESAR": "CHIUSO_PMA_NO_BESAR",
            }[verdict]
            # NO_BESAR is a block (PMA cannot register), like BLOCKED
            new_blocked = verdict in ("BLOCKED", "NO_BESAR")
            stats[f"verdict_{verdict}"] += 1
            old_blocked = bool(old_l4.get("blocked"))
            # a "flip" = the binary block flag changed vs the old (paraphrase) data
            if new_blocked != old_blocked:
                block_changes.append((code, old_status, new_l4_status,
                                      sorted(new_risks)))
            if args.apply:
                rec.setdefault("per_skala_legacy", old_ps)
                rec["per_skala"] = new_ps
                rec["_l2_source"] = "OSS_RBA_resiko_2025"
                rec["l4_bali"]["blocked"] = new_blocked
                rec["l4_bali"]["status"] = new_l4_status
                rec["l4_bali"]["verdict"] = verdict
                if verdict == "NO_BESAR":
                    # has OSS scope but no Besar risk row — can't derive PMA verdict
                    rec["_l4_needs_review"] = "oss_scope_present_but_no_besar_risk_row"
                rec["l4_bali"]["rule"] = "per-scala-Besar (OSS risk at scale Besar; PMA is Besar by law)"
                if verdict == "BLOCKED":
                    rec["l4_bali"]["reason"] = (
                        "OSS risk at scale Besar is Rendah/Menengah-Rendah on every scope "
                        "→ blocked by Bali moratorium 13/5/26")
                elif verdict == "AMBIGUOUS":
                    rec["l4_bali"]["reason"] = (
                        "OSS risk at scale Besar is low on SOME scope(s) but higher on other(s): "
                        "registrable as PMA in Bali only by declaring the higher-risk scope "
                        "(e.g. PPMSE for platform-trade codes) — verify live OSS per exact activity")
                elif verdict == "NO_BESAR":
                    rec["l4_bali"]["reason"] = (
                        "OSS has no Usaha Besar scale row → activity reserved for UMKM "
                        "(Perpres 49/2021 Annex II); a PT PMA (Besar by law) cannot register it")
                else:
                    rec["l4_bali"]["reason"] = (
                        "OSS risk at scale Besar is Menengah-Tinggi/Tinggi → not blocked by moratorium")
        elif args.apply:
            rec.setdefault("per_skala_legacy", old_ps)
            rec["per_skala"] = new_ps
            rec["_l2_source"] = "OSS_RBA_resiko_2025"
        stats["l2_applied"] += 1

    # ---- REPORT ----
    print("=" * 70)
    print("KBLI L2 OSS-risk re-anchor — DIVERGENCE REPORT (old vs official OSS)")
    print("=" * 70)
    print(f"records: {len(records)}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nper_skala scale-count CHANGED (was incomplete): {len(perskala_fixed)}")
    for c, o, n in perskala_fixed[:15]:
        print(f"  {c}: {o} scales -> {n} scales")
    print(f"\nrisk text CHANGED: {len(risk_mismatch)}")
    for c, o, n in risk_mismatch[:15]:
        print(f"  {c}: {o} -> {n}")
    print("\n*** L4-BALI VERDICT (per-scala-Besar, Regola D) ***")
    print(f"  BLOCKED   (Besar low on every scope): {stats.get('verdict_BLOCKED', 0)}")
    print(f"  AMBIGUOUS (Besar low on some scope)  : {stats.get('verdict_AMBIGUOUS', 0)}  -> flagged BLOCCATO_DIPENDE_SCOPE")
    print(f"  OPEN      (Besar never low)          : {stats.get('verdict_OPEN', 0)}")
    print(f"  NO_BESAR  (no Besar row at all)      : {stats.get('verdict_NO_BESAR', 0)}  -> treated OPEN, needs_review")
    print(f"\n*** L4-BALI BLOCK FLIPS vs old paraphrase data: {len(block_changes)} ***")
    flips_to_blocked = [x for x in block_changes if x[2] == "BLOCCATO_CLASSE_RISCHIO"]
    flips_to_open = [x for x in block_changes if x[2] != "BLOCCATO_CLASSE_RISCHIO"]
    print(f"  newly BLOCKED (were open): {len(flips_to_blocked)}")
    print(f"  newly OPEN/ambiguous (were blocked): {len(flips_to_open)}")
    for c, os_, ns, risks in block_changes[:20]:
        print(f"    {c}: {os_} -> {ns}  (official risk {risks})")

    if args.apply:
        ds["metadata"]["version"] = "v10.0-L2-oss-risk"
        blob = json.dumps(ds, ensure_ascii=False, indent=2)
        for t in TARGETS:
            t.write_text(blob, encoding="utf-8")
        print(f"\nAPPLIED. wrote {len(blob)} bytes to both targets. version v10.0-L2-oss-risk")
    else:
        print("\n(report only — pass --apply to write the dataset)")


if __name__ == "__main__":
    main()
