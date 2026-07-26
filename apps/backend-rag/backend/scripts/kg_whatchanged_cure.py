#!/usr/bin/env python3
"""kg_whatchanged_cure.py — apply the `whatChanged` provenance cure to the KG.

WHY A SEPARATE SCRIPT, AND WHY IT CARRIES NO LOGIC
--------------------------------------------------
`kg_nodes.properties.whatChanged` is the THIRD live surface of a field that also
lives in the canonical dataset and in `apps/mouth/data/kbli-gold-all.json`. It is
read by `inspect_kbli`, i.e. WhatsApp / webchat / kbli-explorer — so a cure that
lands only in the repo leaves the same sentence being spoken to clients on every
conversational channel. (Measured 2026-07-25 on prod: 1,554 nodes carry the
field, 45 open with the template renumbering claim, 13 are cut mid-word at
exactly 216 characters.)

The decision of WHAT to rewrite is NOT re-implemented here. It lives once in
`scripts/kbli_filiera/_whatchanged_basis.py::plan_text`, which is not importable
from inside the Fly image, so this script consumes a **pre-computed spec** that
the repo-side compiler emitted from those same predicates. A second
implementation of the predicates on this side is exactly how two surfaces drift
into disagreeing about what is true — the failure this whole lane exists to fix.

FAIL-CLOSED ON DRIFT (W88 — verify by CONTENT, never by a proxy)
----------------------------------------------------------------
Every spec entry pins `md5` of the text as it stood when the spec was emitted.
At apply time the live value is hashed and compared. A node whose text changed
in between is SKIPPED and reported, never rewritten: the new text was computed
against something that is no longer there, and applying it would silently
overwrite whatever landed in the meantime. A run with any drift exits non-zero.

The pre-cure text is preserved verbatim on the node under `_whatChanged_cure`,
so the rewrite is auditable and reversible from the row itself.

USAGE (dry-run is the default; nothing is written without --apply):
    python backend/scripts/kg_whatchanged_cure.py --spec <path-or-raw-URL>
    python backend/scripts/kg_whatchanged_cure.py --spec <...> --only kbli:64995
    python backend/scripts/kg_whatchanged_cure.py --spec <...> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("kg_whatchanged_cure")

ENTITY_TYPE = "kbli"
PROPERTY = "whatChanged"
ARCHIVE_KEY = "_whatChanged_cure"


def load_spec(location: str) -> dict[str, Any]:
    if location.startswith(("http://", "https://")):
        with urllib.request.urlopen(location, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    else:
        with open(location, encoding="utf-8") as handle:
            payload = json.load(handle)
    if "entries" not in payload:
        raise SystemExit(f"spec {location} has no 'entries' — wrong file?")
    return payload


def _md5(text: str) -> str:
    # md5 is an integrity pin against accidental drift here, never a security control.
    return hashlib.md5(text.encode("utf-8")).hexdigest()


async def cure(conn: asyncpg.Connection, spec: dict[str, Any], only: set[str], apply: bool) -> int:
    entries = [e for e in spec["entries"] if not only or e["entity_id"] in only]
    if only:
        unknown = only - {e["entity_id"] for e in spec["entries"]}
        if unknown:
            raise SystemExit(f"--only names entity_ids absent from the spec: {sorted(unknown)}")

    stamp = datetime.now(timezone.utc).isoformat()
    counts = {"cured": 0, "already_cured": 0, "missing": 0, "drift": 0}

    for entry in entries:
        entity_id = entry["entity_id"]
        row = await conn.fetchrow(
            "SELECT properties FROM kg_nodes WHERE entity_id = $1 AND entity_type = $2",
            entity_id,
            ENTITY_TYPE,
        )
        if row is None:
            counts["missing"] += 1
            logger.warning("%s: no %s node — skipped", entity_id, ENTITY_TYPE)
            continue

        properties = json.loads(row["properties"]) if isinstance(row["properties"], str) else dict(row["properties"])
        live = str(properties.get(PROPERTY) or "")

        if live == entry["new"]:
            counts["already_cured"] += 1
            logger.info("%s: already carries the cured text — skipped", entity_id)
            continue

        if _md5(live) != entry["md5"]:
            counts["drift"] += 1
            logger.error(
                "%s: DRIFT — live text hashes %s, spec pinned %s. The replacement was computed "
                "against different content; re-emit the spec. NOT written.",
                entity_id,
                _md5(live)[:12],
                entry["md5"][:12],
            )
            continue

        counts["cured"] += 1
        logger.info("%s: %s", entity_id, ",".join(entry["passes"]))
        logger.info("    OLD: %s", live[:110])
        logger.info("    NEW: %s", entry["new"][:110])
        if not apply:
            continue

        properties[PROPERTY] = entry["new"]
        properties[ARCHIVE_KEY] = {
            "pre_cure_text": live,
            "passes": entry["passes"],
            "spec_id": spec.get("spec_id"),
            "applied_at": stamp,
        }
        # `$1::text::jsonb`, not `$1::jsonb` (W89). This script opens a codec-LESS
        # connection, where binding a json.dumps() string to `::jsonb` happens to be
        # correct — but the cast that is correct on BOTH pools costs nothing, and the
        # class-guard freezes that shape precisely so a later edit cannot move this
        # write onto the codec-on pool and silently start double-encoding it into a
        # jsonb string scalar, invisible to every ->>'key' reader downstream.
        await conn.execute(
            "UPDATE kg_nodes SET properties = $1::text::jsonb, updated_at = now() "
            "WHERE entity_id = $2 AND entity_type = $3",
            json.dumps(properties, ensure_ascii=False),
            entity_id,
            ENTITY_TYPE,
        )

    logger.info(
        "%s — cured=%d already_cured=%d missing=%d drift=%d (of %d spec entries considered)",
        "APPLIED" if apply else "DRY-RUN",
        counts["cured"],
        counts["already_cured"],
        counts["missing"],
        counts["drift"],
        len(entries),
    )
    if not apply:
        logger.info("dry-run complete — rerun with --apply to write")
    return 1 if counts["drift"] else 0


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, help="path or commit-pinned raw URL of the cure spec")
    ap.add_argument("--only", default="", help="comma-separated entity_ids to narrow the run")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)

    if args.apply and args.spec.startswith("http") and "/main/" in args.spec:
        raise SystemExit(
            "--apply with a moving 'main' raw URL is refused — pin the spec to a commit SHA "
            "so the run is reproducible against exactly the reviewed content."
        )

    spec = load_spec(args.spec)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        return await cure(conn, spec, only, args.apply)
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
