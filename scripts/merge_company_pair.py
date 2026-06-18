"""Force-merge a specific company pair the auto-dedup left as an ANOMALY.

Used for the Hidden Palms case (2026-06-12): companies 2384 "PT The Hidden
Palms" and 4092 "PT. HIDDEN PALMS" share one Drive folder but differ only by
punctuation/case, so crm_merge_duplicates flagged them ANOMALY (different
names) instead of merging. They ARE the same PT PMA with complementary data
(2384 holds the akta; 4092 holds NIB+NPWP + the client link).

This does the same safe merge as crm_merge_duplicates._merge_company_groups
but for one explicit keeper/loser pair, with an optional name override:
  - backfill keeper <- loser on COMPANY_BACKFILL_FIELDS (NULL-on-keeper only;
    free the value on the loser first for UNIQUE columns like nib)
  - reparent client_company_links loser -> keeper (dedupe)
  - optional: set keeper.company_name = --rename
  - archive loser: status='inactive', custom_fields.merged_into=keeper

Dry-run by default; --apply to mutate.

Usage (Fly rag machine):
  python scripts/merge_company_pair.py --keeper 4092 --loser 2384 \
      --rename "PT The Hidden Palms"            # dry-run
  python scripts/merge_company_pair.py --keeper 4092 --loser 2384 \
      --rename "PT The Hidden Palms" --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COMPANY_BACKFILL_FIELDS = [
    "nib", "npwp_company", "akta_pendirian_no", "akta_pendirian_date",
    "akta_perubahan_no", "akta_perubahan_date", "sk_menhumkam_no",
    "sk_menhumkam_date", "kbli_code", "kbli_description",
    "registered_address", "office_address",
]


def _write_dsn() -> str:
    import os

    for key in ("DATABASE_URL", "DATABASE_URL_FLY", "DATABASE_URL_LOCAL"):
        if os.environ.get(key):
            return os.environ[key]
    raise SystemExit("No writable DATABASE_URL in env")


def main() -> int:
    import asyncio

    import asyncpg

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keeper", type=int, required=True)
    ap.add_argument("--loser", type=int, required=True)
    ap.add_argument("--rename", default=None, help="optional new company_name for keeper")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    async def run() -> dict:
        conn = await asyncpg.connect(_write_dsn())
        out: dict = {"keeper": args.keeper, "loser": args.loser, "rename": args.rename}
        try:
            krow = await conn.fetchrow(
                f"SELECT company_name, {', '.join(COMPANY_BACKFILL_FIELDS)} FROM companies WHERE id=$1",
                args.keeper,
            )
            lrow = await conn.fetchrow(
                f"SELECT company_name, {', '.join(COMPANY_BACKFILL_FIELDS)} FROM companies WHERE id=$1",
                args.loser,
            )
            if not krow or not lrow:
                out["status"] = "missing_company"
                return out
            backfill = [f for f in COMPANY_BACKFILL_FIELDS
                        if (krow[f] is None or (isinstance(krow[f], str) and not krow[f].strip()))
                        and lrow[f] is not None and not (isinstance(lrow[f], str) and not lrow[f].strip())]
            out["would_backfill"] = backfill
            loser_links = await conn.fetch(
                "SELECT id, client_id FROM client_company_links WHERE company_id=$1", args.loser
            )
            out["loser_link_count"] = len(loser_links)
            if not args.apply:
                out["status"] = "dry_run"
                return out
            async with conn.transaction():
                for f in backfill:
                    await conn.execute(f"UPDATE companies SET {f}=NULL WHERE id=$1", args.loser)
                    await conn.execute(
                        f"UPDATE companies SET {f}=$1 WHERE id=$2", lrow[f], args.keeper
                    )
                moved = dropped = 0
                for ln in loser_links:
                    dup = await conn.fetchval(
                        "SELECT 1 FROM client_company_links WHERE company_id=$1 AND client_id=$2 LIMIT 1",
                        args.keeper, ln["client_id"],
                    )
                    if dup:
                        await conn.execute("DELETE FROM client_company_links WHERE id=$1", ln["id"])
                        dropped += 1
                    else:
                        await conn.execute(
                            "UPDATE client_company_links SET company_id=$1 WHERE id=$2",
                            args.keeper, ln["id"],
                        )
                        moved += 1
                if args.rename:
                    await conn.execute(
                        "UPDATE companies SET company_name=$1, updated_at=NOW() WHERE id=$2",
                        args.rename, args.keeper,
                    )
                await conn.execute(
                    "UPDATE companies SET status='inactive', updated_at=NOW(), "
                    "custom_fields = COALESCE(custom_fields,'{}'::jsonb) || "
                    "jsonb_build_object('merged_into', $2::text) WHERE id=$1",
                    args.loser, str(args.keeper),
                )
                out.update(status="merged", links_moved=moved, links_dropped=dropped,
                           backfilled=backfill)
            return out
        finally:
            await conn.close()

    print(json.dumps(asyncio.run(run()), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
