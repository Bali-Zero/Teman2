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

MERGE POLICY on --apply (spec docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md
§6 rulings 1-4, PR-B). The transform OWNS only the L2 field set — per_skala[].{skala_usaha,
kategori_risiko, scope_index, scope_uraian, perizinan, persyaratan, kewajiban, kewenangan}
plus _l2_source/_l2_status. Everything else on the record was written by LATER layers
(scripts/enrich_kbli_jangka_waktu.py, scripts/derive_fiktif_positif.py, the l4 cure
scripts, scripts/resolve_kbli_l4_needs_review.py) and is merged, never clobbered:
  - per_skala rows are matched by scope identity (scope_uraian, skala_usaha,
    kategori_risiko), each canonical row donating once. A matched row keeps every
    non-L2-owned key of the canonical row (jangka_waktu_source, fiktif_positif, pb_umku,
    sanksi_*, ...) and keeps its jangka_waktu when jangka_waktu_source is set or OSS sends
    a dirty value. A row whose scope was split/renamed carries only the (code, tier)-level
    facts from a same-tier row. An unmatched (new/changed-tier) row is fresh from OSS;
    Rendah / Menengah Rendah tiers get jangka_waktu "Otomatis" (PP 28/2025 Pasal 130/131,
    the same rule enrich_kbli_jangka_waktu.py applies) — fiktif_positif is left to its
    owner, derive_fiktif_positif.py, which is idempotent on unchanged rows.
  - l4_bali is rewritten ONLY when the recomputed verdict or block flag differs from the
    one the canonical carries; otherwise the later cure labels (CHIUSO_MORATORIA_BALI,
    NON_CLASSIFICABILE, ...) stand. A NO_BESAR verdict never rewrites l4_bali: the
    "no Usaha Besar row = reserved for UMKM" inference is WITHDRAWN and the closure of
    those codes is the Perpres 49/2021 Lampiran II layer's (this supersedes §6 ruling 2,
    which pre-dated that withdrawal — recorded in spec §7).
  - a code with no OSS scope keeps per_skala AND l4_bali untouched; _l4_needs_review is
    never written (the #1814 pass resolved and removed every such flag).
  - a code whose per_skala is quarantined by a later cure (any `per_skala_disputed_*` key:
    PP28 collision / false friend, 119 codes) is skipped entirely — cure-owned.
  - a code that HAD OSS scope (_l2_source set) and is 404 now is NOT applied as absent:
    _l2_status = "absent_pending_corroboration", absent_probes += [--fetched], per_skala
    kept (methodology P3: a single 404 is not absence).

Usage:
    python scripts/build_kbli_l2_oss_risk.py            # report only
    python scripts/build_kbli_l2_oss_risk.py --apply    # write the dataset
"""
import argparse, json, re
from collections import Counter
from pathlib import Path

# A clean jangka_waktu the card can render: "Otomatis", a bare day count or "N Hari[ Kerja]" —
# the same acceptance scripts/enrich_kbli_jangka_waktu.py uses; OSS sends "-" on some rows and
# a dirty value is never written over a clean or empty one.
_VALID_JW = re.compile(r"^(Otomatis|\d{1,3}|\d{1,3}\s*[Hh]ari(\s*[Kk]erja)?)$")


def is_clean_jangka(jw) -> bool:
    return bool(jw) and bool(_VALID_JW.match(str(jw).strip()))

ROOT = Path("/tmp/kbli-l2-risk")
RAW = Path("/tmp/oss_risk_raw.jsonl")
TARGETS = [
    ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json",
    ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json",
]
BLOCK_RISKS = {"rendah", "menengah rendah"}            # → moratorium blocks PMA Bali
AUTOMATIC_RISKS = BLOCK_RISKS                          # same tiers: NIB/NIB+SS instant → "Otomatis"
L2_OWNED_PER_SKALA_FIELDS = (
    "skala_usaha", "kategori_risiko", "scope_index", "scope_uraian",
    "perizinan", "persyaratan", "kewajiban", "kewenangan",
)
L2_SOURCE = "OSS_RBA_resiko_2025"
ABSENT_PENDING = "absent_pending_corroboration"
QUARANTINE_PREFIX = "per_skala_disputed"     # cure-owned per_skala: the transform never touches it
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


TIER_LEVEL_CARRY = ("jangka_waktu_source", "fiktif_positif")   # facts of (code, tier), not of a scope row


def _row_key(p):
    return ((p.get("scope_uraian") or "").strip(), tuple(p.get("skala_usaha") or []),
            (p.get("kategori_risiko") or "").strip().lower())


def _tier_key(p):
    return (tuple(p.get("skala_usaha") or []), (p.get("kategori_risiko") or "").strip().lower())


def _drop_donor(pool, key, donor):
    """Remove `donor` (by identity) from the OTHER pool so a canonical row never
    donates twice — once by scope identity and again by tier (Kimi K3 PR-B H1)."""
    rows = pool.get(key)
    if rows:
        pool[key] = [r for r in rows if r is not donor]


def _pop_donor(pool, key):
    rows = pool.get(key)
    return rows.pop(0) if rows else None


def merge_per_skala(old_ps, new_ps, stats=None):
    """Merge policy (module docstring): new_ps rows are authoritative for the L2-owned
    fields. A row matched in old_ps by SCOPE IDENTITY (scope uraian, skala, tier) carries
    the canonical row's later-layer keys through and keeps its jangka_waktu when a later
    layer sourced it or OSS sends a dirty value. A row whose scope was split/renamed but
    whose (skala, tier) existed on the code carries only the TIER-LEVEL facts (jangka
    enrichment keyed by (code, tier), fiktif_positif) — never scope-specific keys such as
    pb_umku/sanksi_*. Each canonical row donates at most once (codex PR-B F1, F2)."""
    stats = stats if stats is not None else Counter()
    by_scope, by_tier = {}, {}
    for p in old_ps or []:
        by_scope.setdefault(_row_key(p), []).append(p)
        by_tier.setdefault(_tier_key(p), []).append(p)
    merged = []
    for n in new_ps:
        row = dict(n)
        o = _pop_donor(by_scope, _row_key(n))
        if o is not None:
            _drop_donor(by_tier, _tier_key(o), o)
            for k, v in o.items():
                if k not in L2_OWNED_PER_SKALA_FIELDS and k != "jangka_waktu":
                    row[k] = v
            if o.get("jangka_waktu_source") or not is_clean_jangka(row.get("jangka_waktu")):
                row["jangka_waktu"] = o.get("jangka_waktu")
                stats["rows_jangka_preserved"] += 1
            stats["rows_carried"] += 1
            merged.append(row)
            continue
        t = _pop_donor(by_tier, _tier_key(n))
        if t is not None:
            _drop_donor(by_scope, _row_key(t), t)
            for k in TIER_LEVEL_CARRY:
                if k in t:
                    row[k] = t[k]
            if t.get("jangka_waktu_source") or not is_clean_jangka(row.get("jangka_waktu")):
                row["jangka_waktu"] = t.get("jangka_waktu")
                stats["rows_jangka_preserved"] += 1
            stats["rows_carried_tier"] += 1
            merged.append(row)
            continue
        if (row.get("kategori_risiko") or "").strip().lower() in AUTOMATIC_RISKS:
            row["jangka_waktu"] = "Otomatis"
            row["jangka_waktu_source"] = "PP28_rule_risk_class"
        elif not is_clean_jangka(row.get("jangka_waktu")):
            row["jangka_waktu"] = ""          # dirty ("-") is never written; empty is honest
        stats["rows_fresh"] += 1
        merged.append(row)
    return merged


def l4_verdict_moved(old_l4, verdict, old_blocked, new_blocked):
    """True only when the OSS-derived verdict actually moved. A canonical l4_bali that
    carries no `verdict` key (a later cure layer wrote `verdict_state` instead) has no
    verdict to compare, so only a flip of the binary block flag counts — otherwise the
    transform would manufacture a move and clobber the cure's labels (Kimi K3 PR-B H2)."""
    if new_blocked != old_blocked:
        return True
    return "verdict" in old_l4 and verdict != old_l4.get("verdict")


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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--root", type=Path, default=ROOT,
                     help="checkout root holding data/source_documents/... and "
                          "apps/mouth/data/... (default: today's literal, keeps the "
                          "June run reproducible)")
    ap.add_argument("--raw", type=Path, default=RAW,
                     help="jsonl of {kode,uuid,status,data} records, e.g. produced by "
                          "vault_to_risk_jsonl.py (default: today's literal)")
    ap.add_argument("--version", default="v10.0-L2-oss-risk",
                     help="metadata.version written on --apply")
    ap.add_argument("--fetched", default=None,
                     help="ISO date of the snapshot (metadata.l2_snapshot.fetched and the "
                          "absent_probes entry for codes that lost their OSS scope)")
    ap.add_argument("--snapshot-vault", default=None, help="metadata.l2_snapshot.vault")
    ap.add_argument("--snapshot-manifest-sha256", default=None,
                     help="metadata.l2_snapshot.manifest_sha256 (vault_manifest.py --out file)")
    ap.add_argument("--snapshot-codes-changed", type=int, default=None,
                     help="metadata.l2_snapshot.codes_changed — the pinned-triple change set "
                          "(scripts/kbli_filiera/vault_tier_changeset.py), quoted not derived")
    ap.add_argument("--source-fix", nargs=2, metavar=("OLD", "NEW"), default=None,
                     help="substring replacement applied to metadata.source on --apply "
                          "(e.g. PP28_2024 PP28_2025, finding C-CLAIM-014)")
    args = ap.parse_args(argv)

    root = args.root
    raw_path = args.raw
    targets = [
        root / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json",
        root / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json",
    ]

    raw = {}
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        raw[r["kode"]] = r

    ds = json.loads(targets[0].read_text(encoding="utf-8"))
    records = ds["data"]

    stats = Counter()
    block_changes = []          # codes whose l4 blocked flips
    perskala_fixed = []         # codes whose per_skala scale-count changed
    risk_mismatch = []          # codes whose risk text differs from old
    per_skala_changed = []      # codes whose per_skala differs by full json equality
    l4_rewritten = []           # codes whose l4_bali is rewritten (verdict/blocked moved)
    absent_pending = []         # codes that had OSS scope before and are 404 now (P3)
    quarantined = []            # codes whose per_skala is cure-owned (per_skala_disputed_*)

    for rec in records:
        code = str(rec.get("kode_kbli_2025") or "")
        r = raw.get(code)
        old_ps = rec.get("per_skala", []) or []
        old_l4 = rec.get("l4_bali", {}) or {}
        old_status = old_l4.get("status")

        if any(k.startswith(QUARANTINE_PREFIX) for k in rec):
            # per_skala is QUARANTINED by a later cure (PP28 collision / false friend —
            # scripts/tests/test_kbli_false_friend_registry.py): cure-owned, never
            # re-derived here. The OSS rows for these codes are evidence for the
            # quarantine owner, not data for this transform.
            stats["quarantined_skipped"] += 1
            quarantined.append(code)
            continue

        if not r or r.get("status") not in (200, 404) or (
                r.get("status") == 200 and not r.get("data", {}).get("success")):
            # not evidence of anything (missing record, 5xx, 200 without success):
            # the record is left exactly as it is (codex PR-B F3)
            stats["no_evidence"] += 1
            continue

        if r.get("status") == 404:
            # No OSS scope today. per_skala and l4_bali stay as the later layers left
            # them (the #1814 pass resolved every _l4_needs_review flag — none is written).
            had_scope = rec.get("_l2_source") == L2_SOURCE and rec.get("_l2_status") != "no_oss_risk"
            if had_scope:
                # was present in the previous snapshot: a single 404 is not absence (P3)
                stats["absent_pending"] += 1
                absent_pending.append(code)
                if args.apply:
                    rec["_l2_status"] = ABSENT_PENDING
                    probes = list(rec.get("absent_probes") or [])
                    if args.fetched and args.fetched not in probes:
                        probes.append(args.fetched)
                    rec["absent_probes"] = probes
            else:
                stats["no_oss_risk"] += 1
                if args.apply:
                    rec["_l2_status"] = "no_oss_risk"
            continue

        new_ps = parse_per_skala(r["data"])
        if not new_ps:
            if args.apply:
                rec["_l2_status"] = "empty_oss_risk"
            stats["empty_oss_risk"] += 1
            continue
        new_ps = merge_per_skala(old_ps, new_ps, stats)

        # scale-count change?
        if len(new_ps) != len(old_ps):
            perskala_fixed.append((code, len(old_ps), len(new_ps)))
        # risk text change (lowest)?
        old_risks = {(p.get("kategori_risiko") or "").lower() for p in old_ps}
        new_risks = {(p.get("kategori_risiko") or "").lower() for p in new_ps}
        if old_risks != new_risks:
            risk_mismatch.append((code, sorted(old_risks), sorted(new_risks)))
        # full per_skala change (json equality) — the number rule 4 needs
        if new_ps != old_ps:
            per_skala_changed.append(code)

        # recompute Bali block (only for risk-derived statuses) using the
        # OFFICIAL per-scope risk at scale Besar (Regola D, chosen by Zero 2026-06-20).
        if old_status not in PRESERVE_STATUSES:
            verdict = besar_block_verdict(new_ps)   # BLOCKED / AMBIGUOUS / OPEN / NO_BESAR
            stats[f"verdict_{verdict}"] += 1
            old_blocked = bool(old_l4.get("blocked"))
            if verdict == "NO_BESAR":
                # A missing Usaha Besar row decides NOTHING by itself (Permeninves 5/2025
                # Pasal 26(1): Besar is a consequence of PMA status). Whether the code is
                # closed to PMA is the Perpres 49/2021 Lampiran II allocation layer's
                # call (scripts/kbli_filiera/cure_l4bali_perpres_adjudication.py), which
                # owns l4_bali for these codes — the old "reserved for UMKM" inference is
                # WITHDRAWN (scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py).
                new_blocked, new_l4_status, l4_moved = old_blocked, old_status, False
            else:
                new_blocked = verdict == "BLOCKED"
                new_l4_status = {
                    "BLOCKED": "BLOCCATO_CLASSE_RISCHIO",
                    "AMBIGUOUS": "BLOCCATO_DIPENDE_SCOPE",
                    "OPEN": "OK_or_HIGHER_RISK",
                }[verdict]
                # a "flip" = the binary block flag changed vs the canonical
                if new_blocked != old_blocked:
                    block_changes.append((code, old_status, new_l4_status,
                                          sorted(new_risks)))
                # l4 is rewritten only when the OSS-derived verdict moved; the labels the
                # later cure layers put on an unchanged verdict are theirs, not ours.
                l4_moved = l4_verdict_moved(old_l4, verdict, old_blocked, new_blocked)
            if l4_moved:
                l4_rewritten.append(code)
            if args.apply:
                rec.setdefault("per_skala_legacy", old_ps)
                rec["per_skala"] = new_ps
                rec["_l2_source"] = L2_SOURCE
                rec.pop("_l2_status", None)
                rec.pop("absent_probes", None)      # presence closes the episode (F4)
            if args.apply and l4_moved:
                rec["l4_bali"]["blocked"] = new_blocked
                rec["l4_bali"]["status"] = new_l4_status
                rec["l4_bali"]["verdict"] = verdict
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
                else:
                    rec["l4_bali"]["reason"] = (
                        "OSS risk at scale Besar is Menengah-Tinggi/Tinggi → not blocked by moratorium")
        elif args.apply:
            rec.setdefault("per_skala_legacy", old_ps)
            rec["per_skala"] = new_ps
            rec["_l2_source"] = L2_SOURCE
            rec.pop("_l2_status", None)
            rec.pop("absent_probes", None)
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
    print(f"  NO_BESAR  (no Besar row at all)      : {stats.get('verdict_NO_BESAR', 0)}  -> l4 untouched (Perpres Lampiran II layer owns it)")
    print(f"\n*** L4-BALI BLOCK FLIPS vs old paraphrase data: {len(block_changes)} ***")
    flips_to_blocked = [x for x in block_changes if x[2] == "BLOCCATO_CLASSE_RISCHIO"]
    flips_to_open = [x for x in block_changes if x[2] != "BLOCCATO_CLASSE_RISCHIO"]
    print(f"  newly BLOCKED (were open): {len(flips_to_blocked)}")
    print(f"  newly OPEN/ambiguous (were blocked): {len(flips_to_open)}")
    for c, os_, ns, risks in block_changes[:20]:
        print(f"    {c}: {os_} -> {ns}  (official risk {risks})")

    # machine-readable line for the reproduction/diff gates (spec rules 4-5):
    # changed_codes = codes whose per_skala (full json equality) or l4_bali
    # block flag differs from the current canonical.
    changed_set = set(per_skala_changed) | {c for c, *_ in block_changes}
    needs_review = 0
    print(f"\nabsent_pending_corroboration (had scope, 404 now): {len(absent_pending)}")
    print("  " + " ".join(absent_pending[:40]))
    print(f"quarantined per_skala skipped (cure-owned): {len(quarantined)}")
    print(f"l4_bali rewritten (verdict/blocked moved): {len(l4_rewritten)}")
    print("  " + " ".join(l4_rewritten[:40]))
    print(
        f"\nSUMMARY changed_codes={len(changed_set)} "
        f"no_oss_risk={stats.get('no_oss_risk', 0)} "
        f"empty_oss_risk={stats.get('empty_oss_risk', 0)} "
        f"needs_review={needs_review} "
        f"per_skala_changed={len(per_skala_changed)} "
        f"l4_changed={len(block_changes)} "
        f"l4_rewritten={len(l4_rewritten)} "
        f"absent_pending={len(absent_pending)} "
        f"quarantined_skipped={len(quarantined)} "
        f"rows_carried={stats.get('rows_carried', 0)} "
        f"rows_carried_tier={stats.get('rows_carried_tier', 0)} "
        f"no_evidence={stats.get('no_evidence', 0)} "
        f"rows_jangka_preserved={stats.get('rows_jangka_preserved', 0)} "
        f"rows_fresh={stats.get('rows_fresh', 0)}"
    )

    if args.apply:
        md = ds["metadata"]
        md["version"] = args.version
        if args.source_fix:
            md["source"] = str(md.get("source", "")).replace(args.source_fix[0], args.source_fix[1])
        if any((args.snapshot_vault, args.fetched, args.snapshot_manifest_sha256,
                args.snapshot_codes_changed is not None)):
            md["l2_snapshot"] = {
                "vault": args.snapshot_vault,
                "manifest_sha256": args.snapshot_manifest_sha256,
                "fetched": args.fetched,
                "codes_changed": args.snapshot_codes_changed,
                "absent_pending": len(absent_pending),
            }
        blob = json.dumps(ds, ensure_ascii=False, indent=2)
        for t in targets:
            t.write_text(blob, encoding="utf-8")
        print(f"\nAPPLIED. wrote {len(blob)} bytes to both targets. version {args.version}")
    else:
        print("\n(report only — pass --apply to write the dataset)")


if __name__ == "__main__":
    main()
