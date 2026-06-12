"""Merge duplicate CRM clients / companies (same real-world entity, 2 records).

Context (2026-06-12): after the Drive cleanup, the dedup sweep found:
  - 12 client groups with the SAME passport_number AND same full_name = the
    same person entered twice.
  - 3 company pairs sharing the SAME google_drive_folder_id; 2 are true
    name-identical duplicates, 1 has DIFFERENT names (a link anomaly, NOT a
    merge — reported, never merged).

Keeper rule (operator choice 2026-06-12): keeper = the record with the MOST
data (documents + practices + interactions + links); tie-break = oldest (min
id). Every loser's child rows are reparented to the keeper; the loser is
archived. Loser Drive folders are LEFT INTACT and reported (files stay
reachable), never trashed by this script.

Reparenting per client loser:
  - documents.client_id      -> keeper   (live rows only; deleted stay put)
  - practices.client_id      -> keeper
  - interactions.client_id   -> keeper
  - client_company_links     -> keeper, but DELETE a loser link whose company
                                is already linked to the keeper (no dup link)
  - loser: deleted_at=NOW(), deleted_by='dedup-merge', notes appended
Per company loser (companies has NO deleted_at column):
  - client_company_links.company_id -> keeper (dedupe as above)
  - documents/practices referencing the company via metadata are NOT touched
    (no FK; reported as a manual follow-up if found)
  - loser: status='inactive', custom_fields.merged_into=keeper

Safety: deterministic keeper (data score, then min id) => idempotent re-runs;
dry-run by default; --apply required; each loser handled in its own tx.

WARNING: merging clients can create NEW (client_id, content_hash) document
duplicates on the keeper. Re-run crm_dedup_documents.py afterwards.

Usage (Fly rag machine; colocate drive_twin_folder_cleanup.py same dir):
  python scripts/crm_merge_duplicates.py --entity clients              # dry-run
  python scripts/crm_merge_duplicates.py --entity clients --apply
  python scripts/crm_merge_duplicates.py --entity companies            # dry-run
  python scripts/crm_merge_duplicates.py --entity companies --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("crm-merge")


def _write_dsn() -> str:
    import os

    for key in ("DATABASE_URL", "DATABASE_URL_FLY", "DATABASE_URL_LOCAL"):
        if os.environ.get(key):
            return os.environ[key]
    from drive_twin_folder_cleanup import _readonly_dsn

    return _readonly_dsn()


# Critical fields to BACKFILL keeper <- loser when keeper's value is NULL/blank.
# Prevents the merge from discarding legal/identity data that lived only on the
# loser (e.g. company 4050 had NIB+NPWP while the older keeper 2710 did not).
CLIENT_BACKFILL_FIELDS = [
    "passport_number", "passport_expiry", "npwp", "nib", "tax_id",
    "current_visa_type", "current_visa_sponsor", "visa_expiry_date",
    "kitas_expiry_date", "kitas_number", "date_of_birth", "birth_date",
    "email", "phone", "whatsapp", "nationality", "address",
]
COMPANY_BACKFILL_FIELDS = [
    "nib", "npwp_company", "akta_pendirian_no", "akta_pendirian_date",
    "akta_perubahan_no", "akta_perubahan_date", "sk_menhumkam_no",
    "sk_menhumkam_date", "kbli_code", "kbli_description",
    "registered_address", "office_address",
]


async def _backfill(conn, table: str, keeper: int, loser: int, fields: list[str],
                    apply: bool) -> list[str]:
    """Copy each field from loser to keeper when keeper's value is NULL/blank.

    Returns the list of field names that were (or would be) backfilled.
    """
    krow = await conn.fetchrow(
        f"SELECT {', '.join(fields)} FROM {table} WHERE id=$1", keeper
    )
    lrow = await conn.fetchrow(
        f"SELECT {', '.join(fields)} FROM {table} WHERE id=$1", loser
    )
    filled: list[str] = []
    for f in fields:
        kv, lv = krow[f], lrow[f]
        k_blank = kv is None or (isinstance(kv, str) and kv.strip() == "")
        l_has = lv is not None and not (isinstance(lv, str) and lv.strip() == "")
        if k_blank and l_has:
            filled.append(f)
            if apply:
                await conn.execute(
                    f"UPDATE {table} SET {f}=$1 WHERE id=$2", lv, keeper
                )
    return filled


async def _client_score(conn, cid: int) -> dict[str, int]:
    docs = await conn.fetchval(
        "SELECT count(*) FROM documents WHERE client_id=$1 AND status<>'deleted'", cid
    )
    prac = await conn.fetchval("SELECT count(*) FROM practices WHERE client_id=$1", cid)
    inter = await conn.fetchval("SELECT count(*) FROM interactions WHERE client_id=$1", cid)
    links = await conn.fetchval("SELECT count(*) FROM client_company_links WHERE client_id=$1", cid)
    return {"docs": docs, "practices": prac, "interactions": inter, "links": links,
            "score": docs + prac + inter + links}


async def _merge_client_groups(conn, apply: bool) -> list[dict[str, Any]]:
    groups = await conn.fetch(
        """
        SELECT array_agg(id ORDER BY id) AS ids
        FROM clients
        WHERE deleted_at IS NULL AND passport_number IS NOT NULL AND passport_number<>''
        GROUP BY upper(passport_number), lower(trim(full_name))
        HAVING count(*)>1 AND count(DISTINCT lower(trim(full_name)))=1
        """
    )
    out: list[dict[str, Any]] = []
    for g in groups:
        ids = list(g["ids"])
        scores = {cid: await _client_score(conn, cid) for cid in ids}
        # keeper = max score, tie-break min id
        keeper = sorted(ids, key=lambda c: (-scores[c]["score"], c))[0]
        losers = [c for c in ids if c != keeper]
        rec: dict[str, Any] = {
            "entity": "client", "keeper": keeper, "keeper_score": scores[keeper],
            "losers": [], "status": "dry_run" if not apply else "merged",
        }
        for loser in losers:
            drive = await conn.fetchval(
                "SELECT google_drive_folder_id FROM clients WHERE id=$1", loser
            )
            moved = {"documents": 0, "practices": 0, "interactions": 0,
                     "links_moved": 0, "links_dropped": 0}
            backfilled: list[str] = []
            if apply:
                async with conn.transaction():
                    backfilled = await _backfill(
                        conn, "clients", keeper, loser, CLIENT_BACKFILL_FIELDS, apply=True
                    )
                    moved["documents"] = int((await conn.execute(
                        "UPDATE documents SET client_id=$1, updated_at=NOW() "
                        "WHERE client_id=$2 AND status<>'deleted'", keeper, loser
                    )).split()[-1])
                    moved["practices"] = int((await conn.execute(
                        "UPDATE practices SET client_id=$1, updated_at=NOW() WHERE client_id=$2",
                        keeper, loser
                    )).split()[-1])
                    moved["interactions"] = int((await conn.execute(
                        "UPDATE interactions SET client_id=$1 WHERE client_id=$2", keeper, loser
                    )).split()[-1])
                    loser_links = await conn.fetch(
                        "SELECT id, company_id FROM client_company_links WHERE client_id=$1", loser
                    )
                    for ln in loser_links:
                        dup = await conn.fetchval(
                            "SELECT 1 FROM client_company_links WHERE client_id=$1 AND company_id=$2 LIMIT 1",
                            keeper, ln["company_id"],
                        )
                        if dup:
                            await conn.execute("DELETE FROM client_company_links WHERE id=$1", ln["id"])
                            moved["links_dropped"] += 1
                        else:
                            await conn.execute(
                                "UPDATE client_company_links SET client_id=$1 WHERE id=$2",
                                keeper, ln["id"],
                            )
                            moved["links_moved"] += 1
                    await conn.execute(
                        "UPDATE clients SET deleted_at=NOW(), deleted_by='dedup-merge', "
                        "notes = COALESCE(notes,'') || $2 WHERE id=$1",
                        loser, f"\n[merged into client {keeper} on {time.strftime('%Y-%m-%d')}]",
                    )
            else:
                backfilled = await _backfill(
                    conn, "clients", keeper, loser, CLIENT_BACKFILL_FIELDS, apply=False
                )
                moved = {
                    "documents": scores[loser]["docs"],
                    "practices": scores[loser]["practices"],
                    "interactions": scores[loser]["interactions"],
                    "links_total": scores[loser]["links"],
                }
            rec["losers"].append({"id": loser, "score": scores[loser], "moved": moved,
                                  "backfilled": backfilled, "orphan_drive_folder": drive})
        out.append(rec)
    return out


async def _company_score(conn, cid: int) -> dict[str, Any]:
    links = await conn.fetchval("SELECT count(*) FROM client_company_links WHERE company_id=$1", cid)
    row = await conn.fetchrow(
        "SELECT (nib IS NOT NULL) hn, (npwp_company IS NOT NULL) hp, lower(trim(company_name)) nm "
        "FROM companies WHERE id=$1", cid
    )
    return {"links": links, "has_nib": row["hn"], "has_npwp": row["hp"], "name": row["nm"],
            "score": links + (1 if row["hn"] else 0) + (1 if row["hp"] else 0)}


async def _merge_company_groups(conn, apply: bool) -> list[dict[str, Any]]:
    groups = await conn.fetch(
        """SELECT google_drive_folder_id g, array_agg(id ORDER BY id) ids
           FROM companies WHERE google_drive_folder_id IS NOT NULL
           GROUP BY google_drive_folder_id HAVING count(*)>1"""
    )
    out: list[dict[str, Any]] = []
    for g in groups:
        ids = list(g["ids"])
        scores = {cid: await _company_score(conn, cid) for cid in ids}
        names = {scores[c]["name"] for c in ids}
        if len(names) > 1:
            out.append({"entity": "company", "status": "ANOMALY_not_merged",
                        "shared_drive_folder": g["g"], "ids": ids,
                        "reason": "companies share a Drive folder but have DIFFERENT names "
                                  "— likely a wrong link, needs manual review"})
            continue
        keeper = sorted(ids, key=lambda c: (-scores[c]["score"], c))[0]
        losers = [c for c in ids if c != keeper]
        rec: dict[str, Any] = {"entity": "company", "keeper": keeper,
                               "keeper_score": scores[keeper], "shared_drive_folder": g["g"],
                               "losers": [], "status": "dry_run" if not apply else "merged"}
        for loser in losers:
            moved = {"links_moved": 0, "links_dropped": 0, "links_total": scores[loser]["links"]}
            backfilled: list[str] = []
            if not apply:
                backfilled = await _backfill(
                    conn, "companies", keeper, loser, COMPANY_BACKFILL_FIELDS, apply=False
                )
            if apply:
                async with conn.transaction():
                    backfilled = await _backfill(
                        conn, "companies", keeper, loser, COMPANY_BACKFILL_FIELDS, apply=True
                    )
                    loser_links = await conn.fetch(
                        "SELECT id, client_id FROM client_company_links WHERE company_id=$1", loser
                    )
                    for ln in loser_links:
                        dup = await conn.fetchval(
                            "SELECT 1 FROM client_company_links WHERE company_id=$1 AND client_id=$2 LIMIT 1",
                            keeper, ln["client_id"],
                        )
                        if dup:
                            await conn.execute("DELETE FROM client_company_links WHERE id=$1", ln["id"])
                            moved["links_dropped"] += 1
                        else:
                            await conn.execute(
                                "UPDATE client_company_links SET company_id=$1 WHERE id=$2",
                                keeper, ln["id"],
                            )
                            moved["links_moved"] += 1
                    await conn.execute(
                        "UPDATE companies SET status='inactive', updated_at=NOW(), "
                        "custom_fields = COALESCE(custom_fields,'{}'::jsonb) || "
                        "jsonb_build_object('merged_into', $2::text) WHERE id=$1",
                        loser, str(keeper),
                    )
            rec["losers"].append({"id": loser, "score": scores[loser], "moved": moved,
                                  "backfilled": backfilled})
        out.append(rec)
    return out


def main() -> int:
    import asyncio

    import asyncpg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", required=True, choices=["clients", "companies"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--out",
        default=str(Path.home() / "logs" / f"crm-merge-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"),
    )
    args = parser.parse_args()

    async def run() -> list[dict[str, Any]]:
        conn = await asyncpg.connect(_write_dsn())
        try:
            if args.entity == "clients":
                return await _merge_client_groups(conn, args.apply)
            return await _merge_company_groups(conn, args.apply)
        finally:
            await conn.close()

    rows = asyncio.run(run())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    summary = Counter(r["status"] for r in rows)
    total_losers = sum(len(r.get("losers", [])) for r in rows)
    logger.info("SUMMARY entity=%s apply=%s groups=%d losers=%d %s report=%s",
                args.entity, args.apply, len(rows), total_losers, dict(summary), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
