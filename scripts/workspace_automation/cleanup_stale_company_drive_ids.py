"""Step 3 — Cleanup stale companies.google_drive_folder_id by Drive global search.

Pipeline:
  1. Read /tmp/stale_drive_id_remediation.json (precomputed) — 271 entries
  2. For each stale company: Drive name-search `name='<company_name>'`
  3. If exactly 1 alive candidate folder found → UPDATE companies SET google_drive_folder_id = new_id
  4. If 0 candidates → record as 'still_lost' (folder truly gone)
  5. If 2+ candidates → record as 'ambiguous' for manual review

Empirical hit rate from sample: ~10% (low because most stale folders truly
deleted/trashed by users, not just moved). But still: every fix unblocks a
potential shortcut creation downstream.

Run:
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/cleanup_stale_company_drive_ids.py --dry-run
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/cleanup_stale_company_drive_ids.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Optional

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA_KEY = "/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"
IMPERSONATE = "zero@balizero.com"
DB = dict(host="localhost", port=15432, dbname="nuzantara_rag",
          user="backend_rag_v2", password="2zEjit43IF6gNUV")  # pragma: allowlist secret
INPUT_JSON = "/tmp/stale_drive_id_remediation.json"

logger = logging.getLogger("stale_cleanup")


def get_drive():
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def search_folder_by_name(svc, name: str) -> list[dict]:
    safe = name.replace("'", "\\'")
    try:
        r = svc.files().list(
            q=f"name = '{safe}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name,parents,driveId,owners)",
            pageSize=10, supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return r.get("files", [])
    except HttpError as e:
        logger.error("search failed for '%s': %s", name, e)
        return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    apply = args.apply and not args.dry_run

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with open(INPUT_JSON) as f:
        data = json.load(f)
    stale = data.get("no_match", [])
    if args.limit:
        stale = stale[: args.limit]
    logger.info("Processing %d stale companies", len(stale))

    svc = get_drive()
    conn = psycopg2.connect(**DB)

    stats = dict(updated=0, ambiguous=0, still_lost=0)
    report = {"updated": [], "ambiguous": [], "still_lost": []}

    for i, s in enumerate(stale, 1):
        if i % 25 == 0:
            logger.info("Progress %d/%d", i, len(stale))
        candidates = search_folder_by_name(svc, s["name"])
        if not candidates:
            stats["still_lost"] += 1
            report["still_lost"].append(s)
            continue
        if len(candidates) > 1:
            stats["ambiguous"] += 1
            report["ambiguous"].append({**s, "candidates": [{"id": c["id"], "name": c["name"], "parents": c.get("parents", [])} for c in candidates]})
            continue
        # 1 candidate — update
        new_id = candidates[0]["id"]
        new_parents = candidates[0].get("parents", [])
        entry = {**s, "new_drive_id": new_id, "new_drive_name": candidates[0]["name"], "new_parents": new_parents}
        report["updated"].append(entry)
        stats["updated"] += 1
        if apply:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE companies SET google_drive_folder_id = %s, updated_at = NOW()
                    WHERE id = %s AND google_drive_folder_id = %s
                """, (new_id, s["id"], s["stale_drive_id"]))
            conn.commit()
            logger.info("UPDATED %s id=%s → %s", s["name"][:30], s["id"], new_id[:12])
        time.sleep(0.1)

    out_path = f"/tmp/stale_cleanup_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n=== SUMMARY ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  report: {out_path}")
    if not apply:
        print("\n  DRY RUN — re-run with --apply to write UPDATEs.")
    conn.close()


if __name__ == "__main__":
    main()
