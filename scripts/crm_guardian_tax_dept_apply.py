#!/usr/bin/env python3
"""Tax Department Federator — APPLY (writes companies.tax_dept_folder_id).

Reads a discovery report JSON produced by
`crm_guardian_tax_dept_discovery.py` and populates the
`companies.tax_dept_folder_id` column for matched entries.

Behavior:
  - Only writes when the column is currently NULL OR --force is passed
  - Skips matches with edit_distance > MAX_EDIT_DISTANCE (default 3)
  - Optionally restricts to a specific match tier
  - Idempotent: re-running with same report = no-op

Side effect (cascade):
  After apply, the next crm_guardian_gemini_cli_worker tick processes
  the affected client and the worker's fetch_linked_companies extension
  (Phase 1.6 patch) reads tax_dept_folder_id as a 3rd source folder.

Usage:
    # Dry-run preview (read-only):
    python scripts/crm_guardian_tax_dept_apply.py --report <latest> --dry-run

    # Apply (writes companies.tax_dept_folder_id):
    python scripts/crm_guardian_tax_dept_apply.py --report <latest>

    # Force overwrite existing values:
    python scripts/crm_guardian_tax_dept_apply.py --report <latest> --force

If --report is omitted, uses the most recent discovery JSON in
~/.crm_guardian/tax_dept_discovery_*.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

import asyncpg

LOG = logging.getLogger("tax_dept_apply")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

REPORTS_DIR = Path.home() / ".crm_guardian"
MAX_EDIT_DISTANCE_ACCEPTED = 3


def _resolve_db_url() -> str:
    secrets = Path.home() / ".nuzantara-secrets.env"
    for line in secrets.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("DATABASE_URL_LOCAL="):
            return stripped.split("=", 1)[1].strip('"').strip("'")
    raise RuntimeError("DATABASE_URL_LOCAL not found")


def _find_latest_report() -> Path:
    candidates = sorted(
        REPORTS_DIR.glob("tax_dept_discovery_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"No discovery report found in {REPORTS_DIR}")
    return candidates[0]


async def apply_report(
    report_path: Path,
    *,
    dry_run: bool,
    force: bool,
    accepted_tiers: set[str],
    max_distance: int,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text())
    matches = report.get("matched", [])
    LOG.info(
        "loaded %d matched entries from %s (run %s)",
        len(matches),
        report_path.name,
        report.get("started_at", "?"),
    )

    db_url = _resolve_db_url()
    conn = await asyncpg.connect(db_url)

    counters = {
        "inserted": 0,
        "already_set_same": 0,
        "overwritten": 0,
        "skipped_already_set_different": 0,
        "skipped_tier": 0,
        "skipped_distance": 0,
        "skipped_no_clients": 0,
        "errors": 0,
    }
    actions: list[dict[str, Any]] = []

    try:
        for m in matches:
            tier = m.get("match_tier")
            dist = m.get("edit_distance") or 0
            company_id = m.get("matched_company_id")
            company_name = m.get("matched_company_name")
            folder_id = m.get("company_folder_id")
            folder_name = m.get("company_folder_name")
            clients_count = m.get("linked_clients_count", 0)

            if tier not in accepted_tiers:
                counters["skipped_tier"] += 1
                actions.append({"action": "skip_tier", "company_id": company_id, "tier": tier})
                continue
            if dist > max_distance:
                counters["skipped_distance"] += 1
                actions.append({"action": "skip_distance", "company_id": company_id, "distance": dist})
                continue
            if clients_count == 0:
                counters["skipped_no_clients"] += 1
                actions.append({
                    "action": "skip_no_clients",
                    "company_id": company_id,
                    "company_name": company_name,
                    "folder_name": folder_name,
                })
                continue

            # Read current value
            row = await conn.fetchrow(
                "SELECT tax_dept_folder_id FROM companies WHERE id=$1",
                company_id,
            )
            if row is None:
                LOG.warning("company_id %s not found in DB", company_id)
                counters["errors"] += 1
                continue
            current = row["tax_dept_folder_id"]

            if current == folder_id:
                counters["already_set_same"] += 1
                actions.append({
                    "action": "already_set_same",
                    "company_id": company_id,
                    "folder_id": folder_id,
                })
                continue
            if current is not None and not force:
                counters["skipped_already_set_different"] += 1
                actions.append({
                    "action": "skip_already_set_different",
                    "company_id": company_id,
                    "current": current,
                    "would_set": folder_id,
                })
                continue

            if dry_run:
                action_label = "would_overwrite" if current is not None else "would_insert"
                if current is not None:
                    counters["overwritten"] += 1
                else:
                    counters["inserted"] += 1
                actions.append({
                    "action": action_label,
                    "company_id": company_id,
                    "company_name": company_name,
                    "folder_name": folder_name,
                    "folder_id": folder_id,
                    "previous": current,
                    "clients_count": clients_count,
                })
                continue

            # Real write
            await conn.execute(
                "UPDATE companies SET tax_dept_folder_id=$1 WHERE id=$2",
                folder_id,
                company_id,
            )
            if current is None:
                counters["inserted"] += 1
                actions.append({
                    "action": "inserted",
                    "company_id": company_id,
                    "company_name": company_name,
                    "folder_id": folder_id,
                    "clients_count": clients_count,
                })
                LOG.info(
                    "  INSERT company_id=%s '%s' → tax_dept_folder_id=%s (clients=%d)",
                    company_id, company_name, folder_id, clients_count,
                )
            else:
                counters["overwritten"] += 1
                actions.append({
                    "action": "overwritten",
                    "company_id": company_id,
                    "previous": current,
                    "folder_id": folder_id,
                })
                LOG.info(
                    "  OVERWRITE company_id=%s '%s' (was %s → now %s)",
                    company_id, company_name, current, folder_id,
                )
    finally:
        await conn.close()

    return {
        "report_path": str(report_path),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "force": force,
        "accepted_tiers": sorted(accepted_tiers),
        "max_distance": max_distance,
        "counters": counters,
        "actions": actions,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", type=Path, default=None,
                    help="Discovery report JSON (default: most recent in ~/.crm_guardian/)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview only — no DB writes")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing tax_dept_folder_id values")
    ap.add_argument("--tier", action="append", default=None,
                    help="Accept only these tiers (default: T1_exact + T2_normalized + T3_fuzzy)")
    ap.add_argument("--max-distance", type=int, default=MAX_EDIT_DISTANCE_ACCEPTED,
                    help="Max Levenshtein distance for T3 matches (default 3)")
    args = ap.parse_args()

    report_path = args.report or _find_latest_report()
    accepted_tiers = set(args.tier) if args.tier else {"T1_exact", "T2_normalized", "T3_fuzzy"}

    audit = asyncio.run(apply_report(
        report_path=report_path,
        dry_run=args.dry_run,
        force=args.force,
        accepted_tiers=accepted_tiers,
        max_distance=args.max_distance,
    ))

    # Write audit log
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = REPORTS_DIR / f"tax_dept_apply_{ts}.json"
    out.write_text(json.dumps(audit, indent=2, default=str))

    cnt = audit["counters"]
    print()
    print(f"  Tax-dept apply — {audit['executed_at']}")
    print(f"  -------------------------------------")
    print(f"  report             : {Path(audit['report_path']).name}")
    print(f"  dry_run            : {audit['dry_run']}")
    print(f"  force              : {audit['force']}")
    print(f"  accepted_tiers     : {audit['accepted_tiers']}")
    print(f"  max_distance       : {audit['max_distance']}")
    print()
    print(f"  inserted                       : {cnt['inserted']}")
    print(f"  overwritten                    : {cnt['overwritten']}")
    print(f"  already_set_same               : {cnt['already_set_same']}")
    print(f"  skipped_already_set_different  : {cnt['skipped_already_set_different']}")
    print(f"  skipped_tier                   : {cnt['skipped_tier']}")
    print(f"  skipped_distance               : {cnt['skipped_distance']}")
    print(f"  skipped_no_clients             : {cnt['skipped_no_clients']}")
    print(f"  errors                         : {cnt['errors']}")
    print()
    print(f"  audit              : {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
