"""kg_kbli_licensing_from_canonical.py — Lot 0 of the KG licensing-class cure.

Spec: docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md (r4), §5.4 and
§5.9. This revision carries ONLY the two phase-independent Lot 0 gestures. The
licence BUILD modes of §5 (Phase 1a/1b) are not here and nothing in this file
writes a licence, a status change on an existing node, or a Qdrant point.

  --placeholders-only    delete the REQUIRES edges to the three §2.1 placeholder
                         nodes (a "licence" named after a status) on each --only
                         code, archived first into the KBLI node's
                         `properties._replaced_requires_pp28v10` (append, never
                         overwrite). Nothing else moves: no status, no property
                         beyond the archive key. 17 codes on PROD (2026-09-21).
  --create-missing-node  insert the `kbli:<code>` row for a canonical code that
                         has none (today exactly one: 01122, served as HTTP 404).
                         Properties hold ONLY what the canonical proves; no edge
                         and no licence is written, so the proof is the honest
                         S2 shape — 200 with `licenses: []`.

Scope discipline shared with `kg_kbli_license_fix.py`: `--only` mandatory (no
sweep, ever), dry-run default, one transaction per code with the node row
locked, refusal instead of guessing. `--apply` against the unpinned default
dataset URL is refused (`kbli_documents_phantom_cure.py` precedent): pass a
commit-pinned raw URL or a local file, and the sha256 of the bytes used is
recorded in `_created_by`.

Not in this file, on purpose: `permit:kitas` edges — a true relational fact in
the wrong bucket, re-bucketed by `kbli_requires_kind.py` (PR #6807) and never
deleted (spec §2.3); `kategori_risiko` on the new node — the rows carry more
than one tier and the router reads risk from Qdrant / licence rows, not from
the KBLI node, so no single value is invented; `sektor_id` / `pp28_sources`
when the canonical does not carry them.

After `--apply`: `kbli_inspect_cache_bust.py --only <codes> --apply`, then a
FRESH `inspect_kbli` read (a probe made before the cure is poisoned for up to
30 days).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx

logger = logging.getLogger("kg_kbli_licensing_from_canonical")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

# The three §2.1 placeholder nodes — and ONLY those. Verified on PROD
# 2026-09-21: 10 + 6 + 1 REQUIRES edges from 17 distinct KBLI nodes.
PLACEHOLDER_TARGETS: frozenset[str] = frozenset(
    {
        "status_perizinan_pending",
        "izin_usaha_pending",
        "izin_usaha_status_pending_regulation",
    },
)
ARCHIVE_KEY = "_replaced_requires_pp28v10"
SCALE_ORDER: tuple[str, ...] = ("Mikro", "Kecil", "Menengah", "Besar")
NEW_NODE_SOURCE_COLLECTION = "kbli_2025_canonical"


class Refusal(Exception):
    """A code this run will not act on; the reason is the message."""


@dataclass
class PlaceholderPlan:
    code: str
    remove: list[str] = field(default_factory=list)  # placeholder targets present


@dataclass
class MissingNodePlan:
    code: str
    name: str
    description: str
    properties: dict


def plan_placeholder_removal(code: str, node_exists: bool, edge_targets: list[str]) -> PlaceholderPlan:
    """Pure decision: which of this code's REQUIRES targets are placeholders.

    A code with no node is refused (there is no row to archive on). A code
    with no placeholder edge yields an empty plan — the second run is a no-op.
    Every non-placeholder target, `permit:kitas` included, is left alone.
    """
    if not node_exists:
        raise Refusal(f"{code}: no kbli:{code} node — nothing to archive on, refusing")
    present = sorted({t for t in edge_targets if t in PLACEHOLDER_TARGETS})
    return PlaceholderPlan(code=code, remove=present)


def derive_skala_usaha(rows: list[dict]) -> list[str]:
    seen = {s for r in rows for s in (r.get("skala_usaha") or [])}
    return [s for s in SCALE_ORDER if s in seen]


def build_missing_node(
    code: str,
    record: dict | None,
    node_exists: bool,
    *,
    run_id: str,
    at: str,
    dataset_sha256: str,
) -> MissingNodePlan:
    """Pure decision: the node to insert, from canonical-proven fields only."""
    if node_exists:
        raise Refusal(f"{code}: kbli:{code} already exists — --create-missing-node refuses")
    if record is None:
        raise Refusal(f"{code}: not in the canonical dataset — refusing to create a node")
    rows = record.get("per_skala") or []
    if not rows:
        raise Refusal(
            f"{code}: canonical per_skala is [] — its status is a §3 allowlist decision, not a Lot 0 gesture",
        )
    judul = (record.get("judul") or "").strip()
    uraian = (record.get("uraian") or "").strip()
    if not judul or not uraian:
        raise Refusal(f"{code}: canonical judul/uraian empty — refusing")
    props: dict = {
        "kode": code,
        "uraian": uraian,
        "skala_usaha": derive_skala_usaha(rows),
        "licensing_status": "REGULATED",  # spec §3: per_skala rows > 0
        "_created_by": {
            "run": run_id,
            "at": at,
            "reason": "canonical code without a KG node (spec §5.9); no edge, no licence written",
            "dataset_sha256": dataset_sha256,
        },
    }
    if record.get("sektor_id"):
        props["sektor_id"] = record["sektor_id"]
    if record.get("pp28_sources"):
        props["pp28_sources"] = [str(s) for s in record["pp28_sources"]]
    return MissingNodePlan(code=code, name=judul, description=uraian, properties=props)


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


async def load_dataset(source: str) -> tuple[dict[str, dict], str]:
    if _looks_like_local_path(source):
        raw = Path(source).read_bytes()
    else:
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.get(source)
            r.raise_for_status()
            raw = r.content
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)["data"]
    logger.info("dataset: %d codes, sha256=%s", len(data), digest[:16])
    return {str(r.get("kode_kbli_2025")): r for r in data}, digest


async def _node_exists(conn: asyncpg.Connection, code: str, *, lock: bool) -> bool:
    sql = "SELECT 1 FROM kg_nodes WHERE entity_id = $1" + (" FOR UPDATE" if lock else "")
    return await conn.fetchval(sql, f"kbli:{code}") is not None


async def _edge_targets(conn: asyncpg.Connection, code: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT target_entity_id FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES'",
        f"kbli:{code}",
    )
    return [r["target_entity_id"] for r in rows]


async def apply_placeholder_plan(conn: asyncpg.Connection, plan: PlaceholderPlan, *, run_id: str, at: str) -> int:
    """Archive then delete, in one transaction on the locked node row."""
    entity_id = f"kbli:{plan.code}"
    async with conn.transaction():
        await _node_exists(conn, plan.code, lock=True)
        entries = [{"target": t, "at": at, "run": run_id, "reason": "placeholder"} for t in plan.remove]
        await conn.execute(
            "UPDATE kg_nodes SET properties = properties || jsonb_build_object($2::text, "
            "COALESCE(properties->$2::text, '[]'::jsonb) || $3::text::jsonb), updated_at = NOW() WHERE entity_id = $1",
            entity_id,
            ARCHIVE_KEY,
            json.dumps(entries),
        )
        tag = await conn.execute(
            "DELETE FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES' "
            "AND target_entity_id = ANY($2::text[])",
            entity_id,
            plan.remove,
        )
        deleted = int(tag.split()[-1])
        if deleted < len(plan.remove):
            raise RuntimeError(f"{plan.code}: planned {len(plan.remove)} deletions, tag says {tag} — rolling back")
    return deleted


async def apply_missing_node(conn: asyncpg.Connection, plan: MissingNodePlan) -> None:
    async with conn.transaction():
        tag = await conn.execute(
            "INSERT INTO kg_nodes (entity_id, entity_type, name, name_id, description, properties, "
            "confidence, source_collection) VALUES ($1, 'kbli', $2, $2, $3, $4::text::jsonb, 1.0, $5) "
            "ON CONFLICT (entity_id) DO NOTHING",
            f"kbli:{plan.code}",
            plan.name,
            plan.description,
            json.dumps(plan.properties, ensure_ascii=False),
            NEW_NODE_SOURCE_COLLECTION,
        )
        if tag != "INSERT 0 1":
            raise RuntimeError(f"{plan.code}: expected INSERT 0 1, got {tag} — rolling back")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", required=True, help="comma-separated 5-digit codes (never swept)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--placeholders-only", action="store_true")
    mode.add_argument("--create-missing-node", action="store_true")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=DATASET_URL, help="canonical dataset: local path or commit-pinned raw URL")
    ap.add_argument("--cure-run", default=None, help="run id recorded in the archive / _created_by")
    args = ap.parse_args(argv)
    args.codes = [c.strip() for c in args.only.split(",") if c.strip()]
    if not args.codes:
        ap.error("--only produced an empty code list")
    if args.apply and args.create_missing_node and args.dataset == DATASET_URL:
        ap.error("--apply with the unpinned default dataset is refused — pass a commit-pinned URL or a local file")
    return args


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = args.cure_run or f"kbli_lot0:{at[:10]}"
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    by_code: dict[str, dict] = {}
    digest = ""
    if args.create_missing_node:
        by_code, digest = await load_dataset(args.dataset)

    conn = await asyncpg.connect(dsn)
    acted = skipped = refused = 0
    try:
        for code in args.codes:
            try:
                exists = await _node_exists(conn, code, lock=False)
                if args.placeholders_only:
                    plan = plan_placeholder_removal(code, exists, await _edge_targets(conn, code))
                    if not plan.remove:
                        logger.info("%s: no placeholder edge — nothing to do", code)
                        skipped += 1
                        continue
                    logger.info("%s: %s placeholder edge(s) → %s", code, "DELETE+ARCHIVE" if args.apply else "would delete", plan.remove)
                    if args.apply:
                        apply_placeholder_plan_n = await apply_placeholder_plan(conn, plan, run_id=run_id, at=at)
                        logger.info("%s: deleted %d, archived under %s", code, apply_placeholder_plan_n, ARCHIVE_KEY)
                else:
                    node = build_missing_node(code, by_code.get(code), exists, run_id=run_id, at=at, dataset_sha256=digest)
                    logger.info("%s: %s node name=%r status=%s skala=%s keys=%s", code, "INSERT" if args.apply else "would insert",
                                node.name, node.properties["licensing_status"], node.properties["skala_usaha"], sorted(node.properties))
                    if args.apply:
                        await apply_missing_node(conn, node)
                acted += 1
            except Refusal as exc:
                logger.warning("REFUSED %s", exc)
                refused += 1
    finally:
        await conn.close()
    verb = "APPLIED" if args.apply else "DRY-RUN"
    logger.info("%s: %d acted | %d nothing-to-do | %d refused (of %d asked)", verb, acted, skipped, refused, len(args.codes))
    return 2 if refused else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(asyncio.run(main()))
