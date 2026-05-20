"""v2: Extended shortcut creation for Individual clients.

Improvements over v1 (`individual_company_tax_shortcuts.py`):
  - 02_Company shortcut targets (priority cascade):
      1. companies.google_drive_folder_id (legacy) — if not stale
      2. Company_CRM/<PT name> (full CRM bundle: 00_AKTA, 01_NIB, 02_NPWP, 03_Profile_Perseroan, 99_Misc)
  - 03_Tax shortcut targets (priority cascade):
      1. companies.tax_dept_folder_id
      2. TAX_DEPT/Members/Angel/<PT_NAME PT> (or other consultants when DWD available)
  - Name normalization: "PT Bali Budu Group" ↔ "BALI BUDU GROUP PT" ↔ "Bali Budu Group PT"
  - Skip stale Drive IDs (validates with files.get before shortcut create)

Run:
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/individual_shortcuts_v2.py --dry-run
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/individual_shortcuts_v2.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from typing import Optional

import psycopg2
import psycopg2.extras
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA_KEY = "/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"
IMPERSONATE = "zero@balizero.com"
DB = dict(host="localhost", port=15432, dbname="nuzantara_rag",
          user="backend_rag_v2", password="2zEjit43IF6gNUV")
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

COMPANY_CRM_INDEX_PATH = "/tmp/company_crm_folders.json"
TAX_MEMBERS_INDEX_PATH = "/tmp/tax_members_pt_folders.json"

logger = logging.getLogger("v2")


# ---------- Drive ----------

def get_drive_service(impersonate=IMPERSONATE):
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(impersonate)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ---------- Name normalization ----------

_PT_SUFFIX_RE = re.compile(r"\b(PT|CV)\b", re.IGNORECASE)


def norm_pt_name(s: str) -> str:
    """Normalize PT name for matching:
    - Remove 'PT', 'CV' as standalone tokens
    - Uppercase
    - Collapse whitespace
    - Remove punctuation
    """
    if not s:
        return ""
    s = re.sub(r"[.,;:]", " ", s)
    s = _PT_SUFFIX_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s


def fuzzy_match_folder(target_name: str, folder_index: dict[str, str]) -> Optional[str]:
    """Find folder id whose name matches target_name (PT-normalized).
    Returns folder_id or None.
    """
    target = norm_pt_name(target_name)
    if not target:
        return None
    for folder_name, fid in folder_index.items():
        if norm_pt_name(folder_name) == target:
            return fid
    return None


# ---------- DB ----------

def resolve_link_targets(cur) -> list[dict]:
    """For each (client_id, company_id) link where client has subfolders:
    return rows {client_id, full_name, company_id, company_name, comp_subf, tax_subf,
                 legacy_drive_id, tax_dept_folder_id}.
    """
    cur.execute("""
        WITH client_subs AS (
          SELECT cl.id AS client_id, cl.full_name,
                 (SELECT subfolder_id FROM client_drive_subfolders
                  WHERE client_id = cl.id AND subfolder_name = '02_Company') AS comp_subf,
                 (SELECT subfolder_id FROM client_drive_subfolders
                  WHERE client_id = cl.id AND subfolder_name = '03_Tax') AS tax_subf
          FROM clients cl
          WHERE cl.deleted_at IS NULL
            AND EXISTS (SELECT 1 FROM client_drive_subfolders WHERE client_id = cl.id)
        )
        SELECT cs.client_id, cs.full_name, cs.comp_subf, cs.tax_subf,
               c.id AS company_id, c.company_name,
               c.google_drive_folder_id AS legacy_drive_id,
               c.tax_dept_folder_id
        FROM client_subs cs
        JOIN client_company_links l ON l.client_id = cs.client_id
        JOIN companies c ON c.id = l.company_id
        ORDER BY cs.full_name, c.company_name
    """)
    return list(cur.fetchall())


# ---------- Shortcut ops ----------

def list_existing_shortcuts(svc, parent_id: str) -> dict[str, str]:
    out = {}
    page_token = None
    while True:
        resp = svc.files().list(
            q=f"'{parent_id}' in parents and mimeType='{SHORTCUT_MIME}' and trashed=false",
            fields="nextPageToken, files(id,name,shortcutDetails)",
            pageSize=200, supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            out[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def target_alive(svc, fid: str) -> bool:
    try:
        meta = svc.files().get(fileId=fid, fields="id,trashed", supportsAllDrives=True).execute()
        return not meta.get("trashed", False)
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def create_shortcut(svc, name: str, parent_id: str, target_id: str) -> str:
    body = {
        "name": name,
        "mimeType": SHORTCUT_MIME,
        "parents": [parent_id],
        "shortcutDetails": {"targetId": target_id},
    }
    sc = svc.files().create(body=body, fields="id,name", supportsAllDrives=True).execute()
    return sc["id"]


# ---------- Main ----------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--client", type=int, help="Filter to one client_id for debug")
    args = p.parse_args()
    apply = args.apply and not args.dry_run

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Load indices
    with open(COMPANY_CRM_INDEX_PATH) as f:
        company_crm_idx = json.load(f)
    logger.info("Loaded %d Company_CRM folders", len(company_crm_idx))
    with open(TAX_MEMBERS_INDEX_PATH) as f:
        tax_members_idx = json.load(f)
    # Flatten tax member PT folders into single name→id map
    tax_pt_idx = {}
    for member, pts in tax_members_idx.items():
        for pt_name, pt_id in pts.items():
            tax_pt_idx[pt_name] = pt_id
    logger.info("Loaded %d Tax/Members PT folders (Angel only for now)", len(tax_pt_idx))

    # DB
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    links = resolve_link_targets(cur)
    if args.client:
        links = [r for r in links if r["client_id"] == args.client]
    if args.limit:
        links = links[:args.limit]
    logger.info("Resolved %d (client,company) link rows", len(links))
    conn.close()

    svc = get_drive_service()

    stats = dict(
        comp_created=0, comp_skipped=0, comp_no_target=0, comp_errors=0,
        tax_created=0, tax_skipped=0, tax_no_target=0, tax_errors=0,
    )

    # Group by parent subfolder for batch list_existing
    by_parent: dict[str, list[dict]] = {}
    for r in links:
        if r["comp_subf"]:
            by_parent.setdefault(r["comp_subf"], []).append({"row": r, "kind": "02_Company"})
        if r["tax_subf"]:
            by_parent.setdefault(r["tax_subf"], []).append({"row": r, "kind": "03_Tax"})

    for parent_id, parent_tasks in by_parent.items():
        existing = list_existing_shortcuts(svc, parent_id)
        for t in parent_tasks:
            r = t["row"]
            kind = t["kind"]
            name = r["company_name"]
            cstat = "comp" if kind == "02_Company" else "tax"

            if name in existing:
                stats[f"{cstat}_skipped"] += 1
                logger.info("  SKIP %s/%s in %s (already exists)", kind, name, parent_id[:10])
                continue

            # Resolve target with priority cascade
            target_id = None
            target_src = None
            if kind == "02_Company":
                # 1. Try legacy company.google_drive_folder_id
                if r["legacy_drive_id"]:
                    if target_alive(svc, r["legacy_drive_id"]):
                        target_id = r["legacy_drive_id"]
                        target_src = "legacy"
                # 2. Fall back to Company_CRM/<PT>
                if not target_id:
                    crm_id = fuzzy_match_folder(name, company_crm_idx)
                    if crm_id and target_alive(svc, crm_id):
                        target_id = crm_id
                        target_src = "Company_CRM"
            else:  # 03_Tax
                # 1. Try tax_dept_folder_id
                if r["tax_dept_folder_id"]:
                    if target_alive(svc, r["tax_dept_folder_id"]):
                        target_id = r["tax_dept_folder_id"]
                        target_src = "tax_dept"
                # 2. Fall back to TAX/Members/Angel/<PT NAME PT>
                if not target_id:
                    tax_id = fuzzy_match_folder(name, tax_pt_idx)
                    if tax_id and target_alive(svc, tax_id):
                        target_id = tax_id
                        target_src = "tax_members"

            if not target_id:
                stats[f"{cstat}_no_target"] += 1
                logger.info("  NO_TARGET %s/%s (client=%s)", kind, name[:35], r["full_name"][:20])
                continue

            logger.info("  %s %s/%s -> [%s]%s (client=%s)",
                        "CREATE" if not apply else "→",
                        kind, name[:35], target_src, target_id[:12], r["full_name"][:20])

            if apply:
                try:
                    sc_id = create_shortcut(svc, name, parent_id, target_id)
                    stats[f"{cstat}_created"] += 1
                    logger.info("    ✅ id=%s", sc_id)
                except HttpError as e:
                    stats[f"{cstat}_errors"] += 1
                    logger.error("    ❌ %s", e)

    print("\n=== SUMMARY ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if not apply:
        print("\n  DRY RUN — re-run with --apply.")


if __name__ == "__main__":
    main()
