"""Populate Individual client 02_Company/ and 03_Tax/ subfolders with Drive shortcuts
to linked Company drive folders and tax_dept_folder.

Strategy:
  - For each client with `client_drive_subfolders` rows (293 clients today)
  - Resolve company links via:
      (1) DB direct client_company_links
      (2) Director name match in company_documents.ocr_extracted_data
      (3) Commissioner name match
  - Create Drive shortcut in:
      02_Company/{COMPANY_NAME} → companies.google_drive_folder_id
      03_Tax/{COMPANY_NAME} → companies.tax_dept_folder_id (if exists)
  - Idempotent: skip if shortcut with same name already exists
  - Uses Domain-Wide Delegation impersonating zero@balizero.com
    (SA scope 'drive' alone has insufficient permissions on My Drive files)

Run:
  cd ~/nuzantara
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/individual_company_tax_shortcuts.py --dry-run
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/individual_company_tax_shortcuts.py --apply
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

import psycopg2
import psycopg2.extras
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA_KEY = "/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"
IMPERSONATE = "zero@balizero.com"
DB = dict(host="localhost", port=15432, dbname="nuzantara_rag",
          user="backend_rag_v2", password="<<ROTATED_2026_05_22_see_DATABASE_URL_env>>")  # pragma: allowlist secret
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

logger = logging.getLogger("individual_shortcuts")


@dataclass
class ShortcutTask:
    client_id: int
    client_name: str
    company_id: int
    company_name: str
    parent_subfolder_id: str
    parent_subfolder_kind: str  # "02_Company" or "03_Tax"
    target_folder_id: str
    target_kind: str  # "company_drive" or "tax_dept_folder"


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY,
        scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def resolve_tasks(cur) -> list[ShortcutTask]:
    """Return all (client, company, target_subfolder) triples we should create."""
    cur.execute("""
        WITH client_subs AS (
          SELECT cl.id AS client_id, cl.full_name,
                 (SELECT subfolder_id FROM client_drive_subfolders
                  WHERE client_id = cl.id AND subfolder_name = '02_Company') AS company_subf,
                 (SELECT subfolder_id FROM client_drive_subfolders
                  WHERE client_id = cl.id AND subfolder_name = '03_Tax') AS tax_subf
          FROM clients cl
          WHERE cl.deleted_at IS NULL
            AND EXISTS (SELECT 1 FROM client_drive_subfolders WHERE client_id = cl.id)
        ),
        linked AS (
          SELECT cs.client_id, cs.full_name, cs.company_subf, cs.tax_subf,
                 c.id AS company_id, c.company_name,
                 c.google_drive_folder_id, c.tax_dept_folder_id,
                 'db_link' AS source
          FROM client_subs cs
          JOIN client_company_links l ON l.client_id = cs.client_id
          JOIN companies c ON c.id = l.company_id
          UNION
          SELECT cs.client_id, cs.full_name, cs.company_subf, cs.tax_subf,
                 c.id, c.company_name, c.google_drive_folder_id, c.tax_dept_folder_id,
                 'director_match'
          FROM client_subs cs
          JOIN company_documents cd
            ON cd.document_type IN ('company_profile','akta_pendirian')
           AND cd.ocr_extracted_data IS NOT NULL
          JOIN companies c ON c.id = cd.company_id
          WHERE EXISTS (
            SELECT 1 FROM jsonb_array_elements(cd.ocr_extracted_data->'directors') AS d
            WHERE UPPER(TRIM(d->>'name')) = UPPER(TRIM(cs.full_name))
          )
          UNION
          SELECT cs.client_id, cs.full_name, cs.company_subf, cs.tax_subf,
                 c.id, c.company_name, c.google_drive_folder_id, c.tax_dept_folder_id,
                 'commissioner_match'
          FROM client_subs cs
          JOIN company_documents cd
            ON cd.document_type IN ('company_profile','akta_pendirian')
           AND cd.ocr_extracted_data IS NOT NULL
          JOIN companies c ON c.id = cd.company_id
          WHERE EXISTS (
            SELECT 1 FROM jsonb_array_elements(cd.ocr_extracted_data->'commissioners') AS d
            WHERE UPPER(TRIM(d->>'name')) = UPPER(TRIM(cs.full_name))
          )
        )
        SELECT * FROM linked ORDER BY full_name, company_name;
    """)
    rows = cur.fetchall()

    tasks: list[ShortcutTask] = []
    seen: set[tuple[int, int, str]] = set()  # dedup same client-company-kind

    for r in rows:
        if r["company_subf"] and r["google_drive_folder_id"]:
            key = (r["client_id"], r["company_id"], "02_Company")
            if key not in seen:
                seen.add(key)
                tasks.append(ShortcutTask(
                    client_id=r["client_id"],
                    client_name=r["full_name"],
                    company_id=r["company_id"],
                    company_name=r["company_name"],
                    parent_subfolder_id=r["company_subf"],
                    parent_subfolder_kind="02_Company",
                    target_folder_id=r["google_drive_folder_id"],
                    target_kind="company_drive",
                ))
        if r["tax_subf"] and r["tax_dept_folder_id"]:
            key = (r["client_id"], r["company_id"], "03_Tax")
            if key not in seen:
                seen.add(key)
                tasks.append(ShortcutTask(
                    client_id=r["client_id"],
                    client_name=r["full_name"],
                    company_id=r["company_id"],
                    company_name=r["company_name"],
                    parent_subfolder_id=r["tax_subf"],
                    parent_subfolder_kind="03_Tax",
                    target_folder_id=r["tax_dept_folder_id"],
                    target_kind="tax_dept_folder",
                ))
    return tasks


def list_existing_shortcuts(svc, parent_id: str) -> dict[str, str]:
    """Return {name: shortcut_id} of existing shortcuts in parent."""
    out: dict[str, str] = {}
    page_token = None
    while True:
        resp = svc.files().list(
            q=f"'{parent_id}' in parents and mimeType='{SHORTCUT_MIME}' and trashed=false",
            fields="nextPageToken, files(id,name,shortcutDetails)",
            pageSize=200,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            out[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def create_shortcut(svc, name: str, parent_id: str, target_id: str) -> str:
    body = {
        "name": name,
        "mimeType": SHORTCUT_MIME,
        "parents": [parent_id],
        "shortcutDetails": {"targetId": target_id},
    }
    sc = svc.files().create(
        body=body,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()
    return sc["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually create shortcuts (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only (default)")
    parser.add_argument("--limit", type=int, default=0, help="Limit N tasks (debug)")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    logger.info("Connecting DB...")
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    tasks = resolve_tasks(cur)
    conn.close()
    logger.info(f"Resolved {len(tasks)} shortcut tasks total")

    if args.limit:
        tasks = tasks[:args.limit]

    logger.info("Connecting Drive (impersonating %s)...", IMPERSONATE)
    svc = get_drive_service()

    # Group tasks by parent_subfolder_id to list existing shortcuts once per parent
    by_parent: dict[str, list[ShortcutTask]] = {}
    for t in tasks:
        by_parent.setdefault(t.parent_subfolder_id, []).append(t)

    created = 0
    skipped = 0
    errors = 0
    plan_lines = []

    for parent_id, parent_tasks in by_parent.items():
        existing = list_existing_shortcuts(svc, parent_id)
        for t in parent_tasks:
            name = t.company_name
            if name in existing:
                skipped += 1
                plan_lines.append(
                    f"  SKIP {t.parent_subfolder_kind} '{name}' in {parent_id[:12]}... "
                    f"(client={t.client_name[:20]}, already exists id={existing[name][:12]}...)"
                )
                continue
            plan_lines.append(
                f"  CREATE {t.parent_subfolder_kind}/{name} -> {t.target_kind}={t.target_folder_id[:12]}... "
                f"in {parent_id[:12]}... (client={t.client_name[:20]})"
            )
            if apply:
                try:
                    sc_id = create_shortcut(svc, name, parent_id, t.target_folder_id)
                    created += 1
                    logger.info("Created %s/%s id=%s", t.parent_subfolder_kind, name, sc_id)
                except HttpError as e:
                    errors += 1
                    logger.error("Failed %s/%s: %s", t.parent_subfolder_kind, name, e)

    print("\n=== PLAN ===")
    for line in plan_lines:
        print(line)
    print("\n=== SUMMARY ===")
    print(f"Total tasks resolved: {len(tasks)}")
    print(f"Already existing (skip): {skipped}")
    print(f"To create: {len(tasks) - skipped}")
    if apply:
        print(f"Actually created: {created}")
        print(f"Errors: {errors}")
    else:
        print("DRY RUN — no shortcuts created. Re-run with --apply to execute.")


if __name__ == "__main__":
    main()
