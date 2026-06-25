"""Patch the LIVE kbli_2025_final_hybrid Qdrant collection's Bali-block fields in place.

WHY in-place (no re-embed): only the L4-Bali verdict changed, not the embedding text.
Re-embedding 4424 chunks would cost OpenAI calls and risk reshaping the (untracked)
chunked {text, metadata-nested} format. We only rewrite metadata.bali_blocked /
bali_status / bali_reason per chunk, using the OFFICIAL per-scala-Besar rule.

Chunk model (discovered by inspecting the live collection):
  - chunk_type="per_skala": one chunk per (kode x scala-group). Carries
    metadata.skala_usaha (list) + metadata.kategori_risiko (that group's risk).
  - chunk_type="uraian": the per-code parent chunk.

Rule (per-scala-Besar, decided by Zero):
  - A PMA is scale Besar by law -> only the Besar risk row matters.
  - per_skala chunk whose skala_usaha includes "Besar":
        blocked = risk in {Rendah, Menengah Rendah}
  - per_skala chunk WITHOUT Besar (pure Mikro/Kecil/Menengah, UMKM scales a PMA
        cannot use): blocked = False, reason "non-PMA scale".
  - uraian (parent) chunk: use the code-level verdict from the L2 dataset
        (BLOCKED / AMBIGUOUS / OPEN), so the parent reflects the whole-code answer.

Idempotent: running twice yields the same payloads. Dry-run prints the diff counts
and a sample without writing.

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/patch_qdrant_bali_l4.py --dry-run
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/patch_qdrant_bali_l4.py --apply
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import httpx

COLLECTION = "kbli_2025_final_hybrid"
BLOCK_RISKS = {"rendah", "menengah rendah"}
# statuses that are NOT risk-derived (closed/restricted lists) -> never overwrite
PRESERVE_STATUSES = {"TERTUTUP", "TERBATAS", "CHIUSO_BALI", "CHIUSO_BALI_PROPOSTO",
                     "TERTUTUP_CANDIDATE", "TERBATAS_CANDIDATE"}
L2_DATASET = Path("/tmp/kbli-l2-risk/data/source_documents/KBLI_2025_FINAL_CLEAN.json")

REASON_BLOCKED = "OSS risk at scale Besar is Rendah/Menengah-Rendah -> Bali moratorium 13/5/26 blocks PMA"
REASON_OPEN = "OSS risk at scale Besar is Menengah-Tinggi/Tinggi -> not blocked by moratorium"
REASON_AMBIG = ("OSS risk at scale Besar is low on some scope but higher on others -> "
                "registrable as PMA only by declaring the higher-risk scope (verify live OSS)")
REASON_NONPMA = "non-PMA scale (PMA operates at scale Besar by law); chunk informational only"
REASON_NO_BESAR = ("OSS has no Usaha Besar scale row -> activity reserved for UMKM "
                   "(Perpres 49/2021 Annex II); a PT PMA (Besar by law) cannot register it")
REASON_NEEDS_REVIEW = ("no OSS-RBA scope (special/sectoral regime: OJK/BI/BPOM/etc.) -> "
                       "Bali registrability needs manual sectoral verification")


def code_verdict_map():
    """kode -> code-level verdict from the L2 dataset.

    Uses l4_bali.verdict when present (BLOCKED/AMBIGUOUS/OPEN/NO_BESAR). For the
    no-OSS-scope special-regime codes (no verdict, status relabelled), maps to the
    synthetic verdict "NEEDS_REVIEW" so the parent chunk reflects it.
    """
    ds = json.loads(L2_DATASET.read_text(encoding="utf-8"))
    out = {}
    for rec in ds["data"]:
        code = str(rec.get("kode_kbli_2025") or "")
        if not code:
            continue
        v = (rec.get("l4_bali") or {}).get("verdict")
        if v:
            out[code] = v
        elif (rec.get("l4_bali") or {}).get("status") == "NEEDS_REVIEW_NO_OSS_SCOPE":
            out[code] = "NEEDS_REVIEW"
    return out


def chunk_bali(md, verdicts):
    """Return (blocked, status, reason) or None if the chunk must be left untouched."""
    ct = md.get("chunk_type")
    kode = str(md.get("kode") or md.get("kode_kbli_2025") or "")
    # never overwrite a non-risk-derived status (TERTUTUP/TERBATAS/closed lists)
    if (md.get("bali_status") or "") in PRESERVE_STATUSES:
        return None
    if ct == "uraian":
        v = verdicts.get(kode, "OPEN")
        if v == "BLOCKED":
            return True, "BLOCCATO_CLASSE_RISCHIO", REASON_BLOCKED
        if v == "AMBIGUOUS":
            return False, "BLOCCATO_DIPENDE_SCOPE", REASON_AMBIG
        if v == "NO_BESAR":
            return True, "CHIUSO_PMA_NO_BESAR", REASON_NO_BESAR
        if v == "NEEDS_REVIEW":
            return True, "NEEDS_REVIEW_NO_OSS_SCOPE", REASON_NEEDS_REVIEW
        return False, "OK_or_HIGHER_RISK", REASON_OPEN
    # per_skala chunk
    skala = md.get("skala_usaha") or []
    risk = (md.get("kategori_risiko") or "").strip().lower()
    if "Besar" in skala:
        blocked = risk in BLOCK_RISKS
        if blocked:
            return True, "BLOCCATO_CLASSE_RISCHIO", REASON_BLOCKED
        return False, "OK_or_HIGHER_RISK", REASON_OPEN
    # pure non-Besar scales: a PMA cannot use them
    return False, "OK_NON_PMA_SCALE", REASON_NONPMA


def scroll_all(client, url, headers):
    points = []
    offset = None
    while True:
        body = {"limit": 250, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        r = client.post(f"{url}/collections/{COLLECTION}/points/scroll", json=body, headers=headers)
        r.raise_for_status()
        res = r.json()["result"]
        points.extend(res["points"])
        offset = res.get("next_page_offset")
        if offset is None:
            break
    return points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        args.dry_run = True

    url = os.environ["QDRANT_URL"].rstrip("/")
    key = os.environ.get("QDRANT_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["api-key"] = key

    verdicts = code_verdict_map()
    print(f"L2 dataset: {len(verdicts)} code-level verdicts loaded")

    with httpx.Client(timeout=120) as client:
        points = scroll_all(client, url, headers)
        print(f"scrolled {len(points)} live points from {COLLECTION}")

        changes = []           # (id, full_new_metadata, kode, old_status, new_status)
        stat_old = Counter()
        stat_new = Counter()
        ct_count = Counter()
        for p in points:
            md = p.get("payload", {}).get("metadata", {})
            ct_count[md.get("chunk_type")] += 1
            old_blocked = md.get("bali_blocked")
            old_status = md.get("bali_status")
            stat_old[bool(old_blocked)] += 1
            verdict = chunk_bali(md, verdicts)
            if verdict is None:
                stat_new["preserved"] += 1
                continue
            new_blocked, new_status, new_reason = verdict
            stat_new[new_blocked] += 1
            if old_blocked != new_blocked or old_status != new_status:
                # CRITICAL: Qdrant set_payload REPLACES the whole `metadata` object
                # (no deep-merge — verified by round-trip test that wiped 16 fields).
                # So we must rewrite the FULL metadata: existing fields + new bali_*.
                full_md = dict(md)
                full_md["bali_blocked"] = new_blocked
                full_md["bali_status"] = new_status
                full_md["bali_reason"] = new_reason
                changes.append((p["id"], full_md, md.get("kode"), old_status, new_status))

        print(f"chunk_type distribution: {dict(ct_count)}")
        print(f"OLD bali_blocked: {dict(stat_old)}")
        print(f"NEW bali_blocked: {dict(stat_new)}")
        print(f"CHANGES: {len(changes)} chunks change verdict")
        flip_to_open = sum(1 for c in changes if not c[4].startswith("BLOCCATO_C"))
        flip_to_blocked = sum(1 for c in changes if c[4] == "BLOCCATO_CLASSE_RISCHIO")
        print(f"  -> now NOT classe-blocked: {flip_to_open}")
        print(f"  -> now classe-blocked: {flip_to_blocked}")
        for cid, full_md, kode, os_, ns in changes[:15]:
            print(f"    {kode}: {os_} -> {ns}")

        if not args.apply:
            print("\n(dry-run — pass --apply to write FULL-metadata set_payload to the live collection)")
            return

        # apply: rewrite the FULL metadata per changed point (set_payload replaces metadata).
        # one point per call to be safe (full metadata differs per point).
        print(f"\nAPPLYING full-metadata set_payload to {len(changes)} chunks (one per call)...")
        applied = 0
        for cid, full_md, kode, _, _ in changes:
            payload = {"payload": {"metadata": full_md}, "points": [cid]}
            r = client.post(
                f"{url}/collections/{COLLECTION}/points/payload",
                json=payload, headers=headers,
            )
            if r.status_code != 200:
                print(f"  ERROR set_payload on {cid} ({kode}): {r.status_code} {r.text[:200]}")
                sys.exit(1)
            applied += 1
            if applied % 250 == 0:
                print(f"  patched {applied}/{len(changes)}")
        print(f"\nDONE. {applied} chunks patched in {COLLECTION}.")


if __name__ == "__main__":
    main()
