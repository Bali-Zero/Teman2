"""
Build KBLI L1 (normalized) by re-aligning our dataset to the OSS ground-truth.

OSS is authoritative for:
  - judul   (Title Case, complete — fixes our UPPERCASE + truncated titles)
  - uraian  (complete — fixes our truncated descriptions)
  - ruang_lingkup (scope detail list — a field we did NOT have at all)

We PRESERVE everything else from our dataset (per_skala, pma_*, status_mapping,
intel_2026, l4_bali, _source, etc.) — OSS has none of that.

NOTE (verified 2026-06-20): OSS judul_en/uraian_en are NOT real English — they
are copies of the Indonesian text. So we do NOT import them; English stays a
separate LLM cantiere (L3), out of scope here.

The 4 phantom codes (26120/60111/82920/85598) exist in our old dataset but NOT in
OSS 2025 → dropped.

Writes BOTH tracked copies:
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json
  - apps/mouth/data/KBLI_2025_FINAL_CLEAN.json
(byte-identical, single source of truth).

Usage:
    python scripts/build_kbli_l1_from_oss.py [--dry-run]
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OSS_FILE = ROOT / "data" / "source_documents" / "KBLI_2025_OSS_GROUND_TRUTH.json"
TARGETS = [
    ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json",
    ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json",
]
PHANTOMS = {"26120", "60111", "82920", "85598"}


def normalize_ruang_lingkup(rl: list) -> list:
    """Keep the Indonesian scope detail; drop the fake _en + null deskripsi noise."""
    out = []
    for item in rl or []:
        if not isinstance(item, dict):
            continue
        entry = {
            "id": item.get("id"),
            "uraian": item.get("uraian_id") or "",
        }
        desk = item.get("deskripsi_id")
        if desk:
            entry["deskripsi"] = desk
        out.append(entry)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    oss_raw = json.loads(OSS_FILE.read_text(encoding="utf-8"))
    oss = {
        str(x["kode"]): x
        for x in oss_raw["data"]
        if isinstance(x, dict) and x.get("digits") == 5
    }
    logger.info(f"OSS 5-digit codes: {len(oss)}")

    # our dataset (both copies are identical; read the source one)
    ours = json.loads(TARGETS[0].read_text(encoding="utf-8"))
    records = ours["data"]
    logger.info(f"our records (before): {len(records)}")

    stats = {
        "judul_fixed": 0,
        "uraian_fixed": 0,
        "ruang_lingkup_added": 0,
        "phantoms_dropped": 0,
        "not_in_oss_kept": 0,
        "unchanged": 0,
    }
    new_records = []
    for r in records:
        code = str(r.get("kode_kbli_2025") or r.get("kode_kbli") or "")
        if code in PHANTOMS:
            stats["phantoms_dropped"] += 1
            continue
        o = oss.get(code)
        if not o:
            stats["not_in_oss_kept"] += 1
            new_records.append(r)
            continue

        changed = False
        # judul: OSS Title Case complete
        oss_judul = (o.get("judul_id") or "").strip()
        if oss_judul and oss_judul != (r.get("judul") or "").strip():
            r["judul"] = oss_judul
            stats["judul_fixed"] += 1
            changed = True
        # uraian: OSS complete (only overwrite when OSS is non-empty and longer/different)
        oss_uraian = (o.get("uraian_id") or "").strip()
        cur_uraian = (r.get("uraian") or "").strip()
        if oss_uraian and oss_uraian != cur_uraian:
            r["uraian"] = oss_uraian
            stats["uraian_fixed"] += 1
            changed = True
        # ruang_lingkup: brand-new field. Always set it (even to []) so the schema
        # is uniform — a consumer must distinguish "scope known-empty" from "field
        # absent / not processed". (Codex review caveat, 2026-06-20.)
        rl = normalize_ruang_lingkup(o.get("ruang_lingkup"))
        if "ruang_lingkup" not in r or r.get("ruang_lingkup") != rl:
            r["ruang_lingkup"] = rl
            if rl:
                stats["ruang_lingkup_added"] += 1
            changed = True
        # provenance bump
        if changed:
            r["_l1_source"] = "OSS_RBA_2025_id_version_fff4053d"
        else:
            stats["unchanged"] += 1
        new_records.append(r)

    ours["data"] = new_records
    md = ours.setdefault("metadata", {})
    md["version"] = "v9.0-L1-oss-aligned"
    md["l1_realign"] = {
        "source": "KBLI_2025_OSS_GROUND_TRUTH.json (gw.oss.go.id v2, id_version fff4053d)",
        "judul_fixed": stats["judul_fixed"],
        "uraian_fixed": stats["uraian_fixed"],
        "ruang_lingkup_added": stats["ruang_lingkup_added"],
        "phantoms_dropped": sorted(PHANTOMS),
    }

    logger.info(f"records (after): {len(new_records)}")
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")

    if args.dry_run:
        sample = next(r for r in new_records if str(r.get("kode_kbli_2025")) == "55203")
        logger.info("\nsample 55203 after:")
        logger.info(f"  judul: {sample.get('judul')}")
        logger.info(f"  uraian[:80]: {sample.get('uraian', '')[:80]}")
        logger.info(f"  ruang_lingkup[0]: {json.dumps((sample.get('ruang_lingkup') or [{}])[0], ensure_ascii=False)[:120]}")
        logger.info(f"  l4_bali preserved: {bool(sample.get('l4_bali'))}")
        logger.info(f"  per_skala preserved: {len(sample.get('per_skala', []))} groups")
        logger.info(f"  intel_2026 preserved: {bool(sample.get('intel_2026'))}")
        logger.info("DRY-RUN — no files written")
        return

    blob = json.dumps(ours, ensure_ascii=False, indent=2)
    for t in TARGETS:
        t.write_text(blob, encoding="utf-8")
        logger.info(f"wrote {t} ({len(blob)} bytes)")
    logger.info("Done — L1 OSS realignment.")


if __name__ == "__main__":
    main()
