#!/usr/bin/env python3
"""D-1 on the third surface: `kg_nodes.properties.whatChanged`, which the conversational channels read.

`cure_d1_whatchanged.py` cures canonical, its copies and gold in the repo. The knowledge graph is a production
database row, so the same nine sentences reach it through this script, run once after the merge by the shipping
session. It starts from `apps/backend-rag/backend/scripts/kg_whatchanged_cure.py`: dry-run by default, a pinned
spec, a drift refusal that is never downgraded. It adds what a one-shot write to production owes its reader:

- **Backup first, outside the repo.** Before anything else, every row the spec names is read and its live value
  saved to a timestamped JSON file under `--backup-dir` (default `~/.local/share/nuzantara/kg-backups/`). A backup
  dir inside the repository is refused. The file restores the field by hand if it is ever needed.
- **Compare-and-set in the UPDATE itself.** A row is written only when the sha256 of its live text equals the
  spec's `old_sha256`, and the UPDATE repeats that condition in SQL. A text that changed between the read and the
  write is not overwritten.
- **Only `whatChanged` moves**, through `jsonb_set`; every other property of the node is left as it is.
- **Read back.** After `--apply`, every written row is read again and must carry the new text.

The two nodes the spec lists under `kg_without_the_field` (01309, 10433) carry no editorial field at all in the
graph today. They are read and reported, never given a field they did not have.

`--snapshot FILE` plans from a JSON export `{entity_id: text|null}` instead of the database. It is how the plan was
proven before the merge, without touching production. It is dry-run only.

USAGE (dry-run is the default; nothing is written without --apply):
    python scripts/kbli_filiera/kg_cure_d1_whatchanged.py                      # DATABASE_URL, dry-run
    python scripts/kbli_filiera/kg_cure_d1_whatchanged.py --apply              # write, then read back
    python scripts/kbli_filiera/kg_cure_d1_whatchanged.py --snapshot kg9.json  # plan from an export
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = (
    Path(__file__).resolve().parent / "cure_specs" / "d1_whatchanged_2026_10_11.json"
)
DEFAULT_BACKUP_DIR = Path.home() / ".local" / "share" / "nuzantara" / "kg-backups"
ENTITY_TYPE = "kbli"
PROPERTY = "whatChanged"

SELECT = "SELECT entity_id, properties->>'whatChanged' AS text FROM kg_nodes WHERE entity_type = $1 AND entity_id = ANY($2::text[])"
UPDATE = (
    "UPDATE kg_nodes SET properties = jsonb_set(properties, '{whatChanged}', to_jsonb($1::text)), updated_at = now() "
    "WHERE entity_type = $2 AND entity_id = $3 "
    "AND encode(sha256(convert_to(properties->>'whatChanged', 'UTF8')), 'hex') = $4"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan(
    spec: dict[str, Any], live: dict[str, str | None]
) -> tuple[list[dict[str, str]], list[str]]:
    """Pure. (rows to write, report lines). A row is written only when its live text hashes to the pinned old."""
    writes, report = [], []
    for entry in spec["kg"]:
        eid, text = entry["entity_id"], live.get(entry["entity_id"])
        if eid not in live:
            report.append(f"{eid}: MISSING — no such node, nothing written")
        elif text == entry["new"]:
            report.append(f"{eid}: already carries the new text")
        elif text is None or sha256_text(text) != entry["old_sha256"]:
            got = "no field" if text is None else sha256_text(text)[:12]
            report.append(
                f"{eid}: DRIFT — live {got}, spec pinned {entry['old_sha256'][:12]}; NOT written"
            )
        else:
            writes.append(entry)
            report.append(
                f"{eid}: WILL WRITE\n    OLD: {text[:110]}\n    NEW: {entry['new'][:110]}"
            )
    for eid in spec.get("kg_without_the_field", []):
        text = live.get(eid)
        state = (
            "MISSING"
            if eid not in live
            else (
                "no whatChanged field"
                if text is None
                else "HAS A FIELD NOW — re-adjudicate"
            )
        )
        report.append(f"{eid}: {state}; the spec gives it no field — nothing written")
    return writes, report


def drifted(report: list[str]) -> bool:
    return any(
        " DRIFT " in line or "MISSING" in line or "re-adjudicate" in line
        for line in report
    )


def backup(rows: dict[str, str | None], spec: dict[str, Any], backup_dir: Path) -> Path:
    backup_dir = backup_dir.expanduser().resolve()
    if backup_dir == REPO_ROOT or REPO_ROOT in backup_dir.parents:
        raise SystemExit(
            f"--backup-dir {backup_dir} is inside the repository — refused"
        )
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"{spec['spec_id']}_{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "spec_id": spec["spec_id"],
                "read_at": stamp,
                "property": PROPERTY,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


async def run_db(
    spec: dict[str, Any], ids: list[str], apply: bool, backup_dir: Path
) -> int:
    import asyncpg  # the database path only; --snapshot runs without it

    conn = await asyncpg.connect(
        os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        live = {
            r["entity_id"]: r["text"]
            for r in await conn.fetch(SELECT, ENTITY_TYPE, ids)
        }
        print(f"backup: {backup(live, spec, backup_dir)}")
        writes, report = plan(spec, live)
        print("\n".join(report))
        if not apply:
            print(
                f"\nDRY-RUN — {len(writes)} row(s) would be written; rerun with --apply"
            )
            return 1 if drifted(report) else 0
        async with conn.transaction():
            for entry in writes:
                status = await conn.execute(
                    UPDATE,
                    entry["new"],
                    ENTITY_TYPE,
                    entry["entity_id"],
                    entry["old_sha256"],
                )
                if status != "UPDATE 1":
                    raise SystemExit(
                        f"{entry['entity_id']}: {status} — the text moved under the write; rolled back"
                    )
        again = {
            r["entity_id"]: r["text"]
            for r in await conn.fetch(
                SELECT, ENTITY_TYPE, [e["entity_id"] for e in writes]
            )
        }
        wrong = [
            e["entity_id"] for e in writes if again.get(e["entity_id"]) != e["new"]
        ]
        if wrong:
            print(f"WROTE BUT READ BACK WRONG on: {wrong}")
            return 2
        print(f"\nAPPLIED — {len(writes)} row(s) written and read back")
        return 1 if drifted(report) else 0
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--spec", default=str(SPEC_PATH))
    ap.add_argument(
        "--apply", action="store_true", help="write, then read back (default: dry-run)"
    )
    ap.add_argument(
        "--snapshot",
        help="plan from a JSON export {entity_id: text|null}; dry-run only",
    )
    ap.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    ids = [e["entity_id"] for e in spec["kg"]] + list(
        spec.get("kg_without_the_field", [])
    )
    if args.snapshot:
        if args.apply:
            raise SystemExit("--snapshot plans only; --apply needs the database")
        live = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        writes, report = plan(spec, {k: v for k, v in live.items() if k in ids})
        print("\n".join(report))
        print(
            f"\nDRY-RUN (snapshot {args.snapshot}) — {len(writes)} row(s) would be written"
        )
        return 1 if drifted(report) else 0
    return asyncio.run(run_db(spec, ids, args.apply, Path(args.backup_dir)))


if __name__ == "__main__":
    sys.exit(main())
