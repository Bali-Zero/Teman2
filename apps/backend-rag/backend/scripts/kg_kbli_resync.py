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
  - properties.pma_*          ← fail-closed public PMA disclosure
  - properties.bali_*         ← fail-closed public Bali disclosure
  - properties.pp28_sources   ← pp28_sources (the OTHER codes a record's PP
    28/2025 licensing rows were carried from; `inspect_kbli` reads it to
    disclose inherited licences — see backend/services/kbli_pp28_provenance.py)
  - properties.{whatItMeans, whatYouNeed, baliContext, whatChanged,
    zantaraOpener}            ← intel_2026.* only for an exact certification
                                 registry match; otherwise removed atomically
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
import math
import os
import re
import sys

import asyncpg
import httpx

from backend.services.kbli_editorial_certification import (
    assert_certified_source_dataset,
    matches_editorial_certification,
    validate_editorial_registry,
    with_neutral_kbli_chat_opener,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kg_kbli_resync")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"
EN_GENERATED_URL = f"{RAW_BASE}/apps/mouth/src/lib/kbli-english-generated.ts"
EN_CURATED_URL = f"{RAW_BASE}/apps/mouth/src/lib/kbli-english.ts"
EDITORIAL_REGISTRY_URL = f"{RAW_BASE}/data/kbli-filiera/pma-editorial-certifications.json"

INTEL_KEYS = ("whatItMeans", "whatYouNeed", "baliContext", "whatChanged", "zantaraOpener")
EDITORIAL_KEYS = (
    *INTEL_KEYS,
    "youllAlsoNeed",
    "tkaInfo",
    "editorial",
    "intel_2026",
    "gold_content",
    "expert_legal",
    "has_intel_2026",
    "has_gold_content",
    "editorial_disclosed",
)
PMA_KEYS = (
    "pma_status",
    "pma_max_asing",
    "pma_verification_status",
    "pma_official_basis",
    "pma_source_vintage",
    "pma_kondisi",
    "pma_prioritas",
    "pma_nota",
    "pma_cap_special",
    "pma_cap_verified",
)
BALI_KEYS = ("bali_status", "bali_blocked", "bali_reason", "has_bali_l4")
PMA_ALLOWED_STATUSES = frozenset({"TERBUKA", "TERBATAS", "TERTUTUP"})
TS_ENTRY_RE = re.compile(r'"(\d{5})":\s*"((?:[^"\\]|\\.)*)"')


def parse_ts_title_map(source: str) -> dict[str, str]:
    """Extract the {code: english title} pairs from a generated .ts map."""
    return {code: title.replace('\\"', '"') for code, title in TS_ENTRY_RE.findall(source)}


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _public_pma_cap(rec: dict) -> int | float | str | None:
    value = rec.get("pma_max_asing")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return "special" if value == "special" and rec.get("pma_cap_special") is True else None


def _pma_claims_verified(rec: dict) -> bool:
    status = rec.get("pma_status")
    return bool(
        rec.get("pma_verification_status") == "located"
        and isinstance(status, str)
        and status in PMA_ALLOWED_STATUSES
        and _clean_text(rec.get("pma_official_basis"))
        and _clean_text(rec.get("pma_source_vintage"))
    )


def _disclose_pma(rec: dict) -> dict:
    if not _pma_claims_verified(rec):
        return {
            "pma_status": "NOT_VERIFIED",
            "pma_max_asing": None,
            "pma_verification_status": "declared_gap",
            "pma_official_basis": None,
            "pma_source_vintage": None,
            "pma_kondisi": None,
            "pma_prioritas": None,
            "pma_nota": None,
            "pma_cap_special": False,
            "pma_cap_verified": False,
        }
    cap = _public_pma_cap(rec)
    return {
        "pma_status": rec["pma_status"],
        "pma_max_asing": cap,
        "pma_verification_status": "located",
        "pma_official_basis": _clean_text(rec.get("pma_official_basis")),
        "pma_source_vintage": _clean_text(rec.get("pma_source_vintage")),
        "pma_kondisi": _clean_text(rec.get("pma_kondisi")),
        "pma_prioritas": rec.get("pma_prioritas") is True,
        "pma_nota": _clean_text(rec.get("pma_nota")),
        "pma_cap_special": cap == "special",
        "pma_cap_verified": cap is not None and rec.get("pma_cap_verified") is True,
    }


def _disclose_bali(rec: dict) -> dict:
    neutral = {
        "bali_status": None,
        "bali_blocked": None,
        "bali_reason": "",
        "has_bali_l4": False,
    }
    if not _pma_claims_verified(rec):
        return neutral
    l4 = rec.get("l4_bali")
    if not isinstance(l4, dict):
        return neutral
    status = l4.get("status")
    blocked = l4.get("blocked")
    if (
        not isinstance(status, str)
        or not status.strip()
        or status != status.strip()
        or not isinstance(blocked, bool)
    ):
        return neutral
    reason = l4.get("reason")
    return {
        "bali_status": status,
        "bali_blocked": blocked,
        "bali_reason": reason.strip() if isinstance(reason, str) else "",
        "has_bali_l4": True,
    }


def merge_node_props(props: dict, rec: dict, registry: dict | None = None) -> dict:
    """The canonical fields folded onto a kg_node's existing `properties`.

    The PMA/Bali/editorial disclosure atom and ``pp28_sources`` are
    authoritative.  A partial PMA tuple clears raw ownership, Bali and
    generated editorial claims instead of preserving stale values from an old
    graph load.
    - `pp28_sources` is **authoritative**: written when canonical has it,
      REMOVED when canonical does not. `inspect_kbli` turns this field into a
      client-facing sentence naming other KBLI codes; a stale list left behind
      would disclose an inheritance the dataset no longer records, and a wrong
      provenance claim is worse than no note at all.

    Pure, so both rules are exercisable — the previous version of this merge
    lived inline in `main()` under a live DSN, where nothing could reach it.
    """
    new_props = dict(props)

    for key in tuple(new_props):
        if key.startswith("pma_") or key.startswith("bali_") or key == "l4_bali":
            new_props.pop(key, None)
    new_props.update({key: value for key, value in _disclose_pma(rec).items() if value is not None})
    new_props.update(
        {key: value for key, value in _disclose_bali(rec).items() if value is not None}
    )

    # The editorial layer is authoritative and atomic. Clear every legacy
    # editorial alias first, even for a located tuple, then re-add only an
    # exact block whose content and PMA fingerprint are in the review registry.
    for key in EDITORIAL_KEYS:
        new_props.pop(key, None)
    intel = rec.get("intel_2026")
    if isinstance(intel, dict) and matches_editorial_certification(
        "canonicalIntel",
        str(rec.get("kode_kbli_2025") or ""),
        rec,
        intel,
        registry,
    ):
        intel = with_neutral_kbli_chat_opener(str(rec["kode_kbli_2025"]), intel)
        for key in INTEL_KEYS:
            value = intel.get(key)
            if isinstance(value, str) and value.strip():
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


async def fetch_inputs() -> tuple[list[dict], dict[str, str], dict]:
    async with httpx.AsyncClient(timeout=60) as http:
        responses = {}
        for key, url in (
            ("dataset", DATASET_URL),
            ("generated", EN_GENERATED_URL),
            ("curated", EN_CURATED_URL),
            ("registry", EDITORIAL_REGISTRY_URL),
        ):
            r = await http.get(url)
            r.raise_for_status()
            responses[key] = r
        registry = validate_editorial_registry(responses["registry"].json())
        assert_certified_source_dataset(responses["dataset"].content, registry)
        dataset = responses["dataset"].json()["data"]
        generated = parse_ts_title_map(responses["generated"].text)
        curated = parse_ts_title_map(responses["curated"].text)
    titles = {**generated, **curated}  # curated wins (kbli-data.ts precedence)
    logger.info(
        "canonical: %d codes | EN titles: %d (%d curated)", len(dataset), len(titles), len(curated)
    )
    return dataset, titles, registry


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--only", help="restrict to one 5-digit code")
    args = ap.parse_args()

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    dataset, titles, registry = await fetch_inputs()
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

            new_props = merge_node_props(props, rec, registry)

            if row["name"] == name and row["description"] == uraian and new_props == props:
                unchanged += 1
                continue

            if props.get("pma_status") != new_props.get("pma_status"):
                pma_flips.append(
                    f"{code}: {props.get('pma_status')} -> {new_props.get('pma_status')}"
                )
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
    logger.info(
        "%s: %d to update | %d unchanged | %d missing in KG",
        mode,
        len(updated),
        unchanged,
        len(missing),
    )
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
