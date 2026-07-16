"""
kg_kbli_resync.py — re-sync the KBLI nodes of the Postgres knowledge graph
(`kg_nodes`, entity_id `kbli:<code>`) from the canonical dataset.

WHY (PENDING-ARMS 2026-07-13, found during #2359 prove-live): the KG was loaded
from a pre-#2164 snapshot. `inspect_kbli 02102` still returned the mis-assigned
title "SEED COLLECTION (PENGAMBILAN BENIH HUTAN)" and `pma_status TERBATAS`
while the canonical dataset (post-purge, post-OSS-realign) says timber and
TERBUKA. The catalog file the KG was originally loaded from has no generator
left in the repo, so this script IS the re-sync path from now on.

WHAT IT SYNCS (1:1 canonical fields only — no derivations):
  - name / name_id / name_en  ← judul + English title maps (curated wins over
    generated, mirroring apps/mouth/src/lib/kbli-data.ts precedence)
  - description               ← uraian
  - properties.uraian         ← uraian (2026-07-16: this used to be left
    stale even after a resync — the router (`kbli_notebook.py`
    `props.get("uraian", node["description"])`) PREFERS properties.uraian
    over the description column, so a code whose properties.uraian carried
    old subgroup-bleed text (e.g. 68112's 6812-nonresidential contamination)
    kept serving the wrong text to `inspect_kbli` even though `description`
    itself had already been corrected. Live audit found 930 kbli codes with
    this exact drift. Now synced together with description, same source
    field, same change-detection.)
  - properties.pma_status     ← pma_status
  - properties.{whatItMeans, whatYouNeed, baliContext, whatChanged,
    zantaraOpener}            ← intel_2026.* (only keys present; never nulled)
Fields with unknown original derivation (kategori_risiko, skala_usaha,
licensing_status, sektor_id) are left untouched.

WHERE IT RUNS: the Fly machine (write role via DATABASE_URL). The gitignored
dataset copies are not in the image, so the canonical is fetched from the
public repo raw at origin/main — the same bytes that shipped in #2359.

Usage (dry-run is the default; nothing is written without --apply):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_resync.py [--apply] [--only 02102]"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kg_kbli_resync")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"
EN_GENERATED_URL = f"{RAW_BASE}/apps/mouth/src/lib/kbli-english-generated.ts"
EN_CURATED_URL = f"{RAW_BASE}/apps/mouth/src/lib/kbli-english.ts"

INTEL_KEYS = ("whatItMeans", "whatYouNeed", "baliContext", "whatChanged", "zantaraOpener")
TS_ENTRY_RE = re.compile(r'"(\d{5})":\s*"((?:[^"\\]|\\.)*)"')


def parse_ts_title_map(source: str) -> dict[str, str]:
    """Extract the {code: english title} pairs from a generated .ts map."""
    return {code: title.replace('\\"', '"') for code, title in TS_ENTRY_RE.findall(source)}


async def fetch_inputs() -> tuple[list[dict], dict[str, str]]:
    async with httpx.AsyncClient(timeout=60) as http:
        responses = {}
        for key, url in (("dataset", DATASET_URL), ("generated", EN_GENERATED_URL), ("curated", EN_CURATED_URL)):
            r = await http.get(url)
            r.raise_for_status()
            responses[key] = r
        dataset = responses["dataset"].json()["data"]
        generated = parse_ts_title_map(responses["generated"].text)
        curated = parse_ts_title_map(responses["curated"].text)
    titles = {**generated, **curated}  # curated wins (kbli-data.ts precedence)
    logger.info("canonical: %d codes | EN titles: %d (%d curated)", len(dataset), len(titles), len(curated))
    return dataset, titles


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--only", help="restrict to one 5-digit code")
    args = ap.parse_args()

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    dataset, titles = await fetch_inputs()
    if args.only:
        dataset = [r for r in dataset if str(r.get("kode_kbli_2025")) == args.only]

    conn = await asyncpg.connect(dsn)
    updated, missing, unchanged = [], [], 0
    pma_flips: list[str] = []
    writes: list[tuple] = []
    try:
        # One bulk read: per-row round-trips over the Fly proxy take >5min for 1559 codes.
        rows = {
            r["entity_id"]: r
            for r in await conn.fetch(
                "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_id LIKE 'kbli:%'"
            )
        }
        for rec in dataset:
            code = str(rec.get("kode_kbli_2025"))
            judul = (rec.get("judul") or "").strip()
            uraian = (rec.get("uraian") or "").strip()
            pma = rec.get("pma_status")
            intel = rec.get("intel_2026") or {}
            en = titles.get(code, "")

            row = rows.get(f"kbli:{code}")
            if row is None:
                missing.append(code)
                continue

            props = json.loads(row["properties"]) if row["properties"] else {}
            name = f"{en.upper()} ({judul.upper()})" if en else judul.upper()

            new_props = dict(props)
            if uraian:
                new_props["uraian"] = uraian
            if pma:
                new_props["pma_status"] = pma
            for k in INTEL_KEYS:
                v = intel.get(k)
                if v:
                    new_props[k] = v

            if row["name"] == name and row["description"] == uraian and new_props == props:
                unchanged += 1
                continue

            if props.get("pma_status") != new_props.get("pma_status"):
                pma_flips.append(f"{code}: {props.get('pma_status')} -> {new_props.get('pma_status')}")
            updated.append(code)
            writes.append(
                (f"kbli:{code}", name, judul, en, uraian, json.dumps(new_props, ensure_ascii=False))
            )

        if args.apply and writes:
            await conn.executemany(
                """
                UPDATE kg_nodes
                SET name = $2, name_id = $3, name_en = NULLIF($4, ''),
                    description = $5, properties = $6::jsonb, updated_at = now()
                WHERE entity_id = $1
                """,
                writes,
            )
    finally:
        await conn.close()

    mode = "APPLIED" if args.apply else "DRY-RUN"
    logger.info("%s: %d to update | %d unchanged | %d missing in KG", mode, len(updated), unchanged, len(missing))
    # No display caps: a truncated list reads as the whole list downstream (W97).
    for line in pma_flips:
        logger.info("  pma flip %s", line)
    if missing:
        logger.info("  missing nodes: %s", " ".join(missing))
    if not args.apply and updated:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
