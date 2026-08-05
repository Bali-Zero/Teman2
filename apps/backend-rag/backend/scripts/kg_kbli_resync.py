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
  - properties.pma_status     ← pma_status
  - properties.pp28_sources   ← pp28_sources (the OTHER codes a record's PP
    28/2025 licensing rows were carried from; `inspect_kbli` reads it to
    disclose inherited licences — see backend/services/kbli_pp28_provenance.py)
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


def merge_node_props(props: dict, rec: dict) -> dict:
    """The canonical fields folded onto a kg_node's existing `properties`.

    Two DELIBERATELY different merge rules live here, and the asymmetry is the
    whole point:

    - `pma_status` and the intel keys are **only ever added**. Canonical not
      carrying a value means "nothing to say", not "delete what the graph has"
      — those fields have other writers and other derivations.
    - `pp28_sources` is **authoritative**: written when canonical has it,
      REMOVED when canonical does not. `inspect_kbli` turns this field into a
      client-facing sentence naming other KBLI codes; a stale list left behind
      would disclose an inheritance the dataset no longer records, and a wrong
      provenance claim is worse than no note at all.

    Pure, so both rules are exercisable — the previous version of this merge
    lived inline in `main()` under a live DSN, where nothing could reach it.
    """
    new_props = dict(props)

    pma = rec.get("pma_status")
    if pma:
        new_props["pma_status"] = pma

    intel = rec.get("intel_2026") or {}
    for key in INTEL_KEYS:
        value = intel.get(key)
        if value:
            new_props[key] = value

    raw_sources = rec.get("pp28_sources")
    sources: list[str] = []
    if isinstance(raw_sources, list):
        for entry in raw_sources:
            # `str(None)` is "None" — a source code that does not exist. Reject
            # non-strings BEFORE stringify, matching
            # backend/services/kbli_pp28_provenance.content_inherited_from.
            if not isinstance(entry, (str, int)) or isinstance(entry, bool):
                continue
            text = str(entry).strip()
            if text:
                sources.append(text)
    if sources:
        new_props["pp28_sources"] = sources
    else:
        new_props.pop("pp28_sources", None)

    return new_props


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
    pp28_changes: list[str] = []
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
            en = titles.get(code, "")

            row = rows.get(f"kbli:{code}")
            if row is None:
                missing.append(code)
                continue

            props = json.loads(row["properties"]) if row["properties"] else {}
            name = f"{en.upper()} ({judul.upper()})" if en else judul.upper()

            new_props = merge_node_props(props, rec)

            if row["name"] == name and row["description"] == uraian and new_props == props:
                unchanged += 1
                continue

            if props.get("pma_status") != new_props.get("pma_status"):
                pma_flips.append(f"{code}: {props.get('pma_status')} -> {new_props.get('pma_status')}")
            if props.get("pp28_sources") != new_props.get("pp28_sources"):
                pp28_changes.append(code)
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
    # A count, not the list: 1,384 codes carry the field, so printing them all
    # would bury the pma flips above. The count IS the audit — it must land on
    # the number the canonical says, and a silent 0 means the field never synced.
    logger.info("  pp28_sources changed on %d node(s)", len(pp28_changes))
    if missing:
        logger.info("  missing nodes: %s", " ".join(missing))
    if not args.apply and updated:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
