#!/usr/bin/env python3
"""Tax Department Federator — DISCOVERY (read-only).

Walks the Bali Zero tax-dept Drive structure:
  Members/<TeamMember>/[shortcut→]<TeamMember>/<COMPANY_NAME>/...

For each <COMPANY_NAME> folder found, attempts a 3-tier match against
the `companies` table:

  T1. exact `companies.company_name` match (case-insensitive trim)
  T2. normalized match (strip "PT", uppercase, drop punctuation)
  T3. Levenshtein distance <= 3 fuzzy match

For matched companies, resolves linked clients via
`client_company_links.status='active'`.

Output:
  ~/.crm_guardian/tax_dept_discovery_<ts>.json    — full structured report
  stdout                                          — terse human summary

NO Drive writes. NO DB writes. Pure read + report.

Run once via `python scripts/crm_guardian_tax_dept_discovery.py`. The
follow-up writer script (separate file) will consume the matched_company
ids from this report.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

import asyncpg
from backend.services.crm_guardian.base import build_drive_service

LOG = logging.getLogger("tax_dept_discovery")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

TAX_DEPT_ROOT = "1QkFxr9rwtyIxIf7XaVNi6ehmxIMrWO2S"  # pragma: allowlist secret  # noqa: E501 — Google Drive folder ID, not a credential
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
FOLDER_MIME = "application/vnd.google-apps.folder"

OUT_DIR = Path.home() / ".crm_guardian"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    secrets = Path.home() / ".nuzantara-secrets.env"
    for line in secrets.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("DATABASE_URL_LOCAL="):
            return stripped.split("=", 1)[1].strip('"').strip("'")
    raise RuntimeError("DATABASE_URL_LOCAL not found")


async def fetch_all_companies(conn) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, company_name, google_drive_folder_id, npwp_company
        FROM companies
        """
    )
    return [dict(r) for r in rows]


async def fetch_clients_for_company(conn, company_id: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT c.id, c.full_name, c.google_drive_folder_id, ccl.role, ccl.is_primary
        FROM client_company_links ccl
        JOIN clients c ON c.id = ccl.client_id
        WHERE ccl.company_id = $1 AND ccl.status = 'active'
        ORDER BY ccl.is_primary DESC, c.id ASC
        """,
        company_id,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Drive walkers
# ---------------------------------------------------------------------------

def list_children(drive, folder_id: str) -> list[dict[str, Any]]:
    """Page through direct children of a Drive folder."""
    out: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields=(
                "nextPageToken, files(id,name,mimeType,size,modifiedTime,"
                "shortcutDetails)"
            ),
            pageSize=200,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def resolve_shortcut(drive, file_meta: dict[str, Any]) -> tuple[str, str] | None:
    """Return (target_id, target_mime) for a shortcut, or None."""
    details = file_meta.get("shortcutDetails") or {}
    target_id = details.get("targetId")
    target_mime = details.get("targetMimeType")
    if not target_id:
        return None
    return target_id, target_mime or ""


def walk_tax_dept(drive) -> list[dict[str, Any]]:
    """Walk Members/<TeamMember>/[shortcut→]<TeamMember>/<COMPANY>/...

    Returns flat list of {team_member, company_folder_id, company_folder_name,
                          file_count, sample_filenames[]}.
    """
    findings: list[dict[str, Any]] = []
    members = list_children(drive, TAX_DEPT_ROOT)
    LOG.info("tax-dept root has %d team-member entries", len(members))

    for member in members:
        if member["mimeType"] != FOLDER_MIME:
            continue
        team_member_name = member["name"]
        team_member_folder_id = member["id"]
        LOG.info("scanning team member: %s", team_member_name)

        # Each member folder may have shortcuts that point to their actual
        # working folder OR direct subfolders (companies)
        level1 = list_children(drive, team_member_folder_id)
        target_folder_ids: list[tuple[str, str]] = []  # (id, source_label)

        for entry in level1:
            if entry["mimeType"] == SHORTCUT_MIME:
                resolved = resolve_shortcut(drive, entry)
                if resolved and resolved[1] == FOLDER_MIME:
                    target_folder_ids.append((resolved[0], f"{team_member_name} (via shortcut '{entry['name']}')"))
            elif entry["mimeType"] == FOLDER_MIME:
                target_folder_ids.append((entry["id"], f"{team_member_name} (direct)"))

        if not target_folder_ids:
            LOG.info("  %s: empty (no shortcuts or subfolders)", team_member_name)
            continue

        for working_folder_id, source_label in target_folder_ids:
            companies = list_children(drive, working_folder_id)
            company_folders = [c for c in companies if c["mimeType"] == FOLDER_MIME]
            LOG.info("  %s → %d company folders", source_label, len(company_folders))

            for company in company_folders:
                cf_id = company["id"]
                cf_name = company["name"]
                # Sample files inside the company folder (depth 1 only for discovery)
                inner = list_children(drive, cf_id)
                files = [f for f in inner if f["mimeType"] != FOLDER_MIME]
                subdirs = [f for f in inner if f["mimeType"] == FOLDER_MIME]
                findings.append({
                    "team_member": team_member_name,
                    "source_label": source_label,
                    "company_folder_id": cf_id,
                    "company_folder_name": cf_name,
                    "files_at_root": len(files),
                    "subdirs_at_root": len(subdirs),
                    "sample_filenames": [f["name"] for f in files[:5]],
                    "sample_subdirs": [f["name"] for f in subdirs[:5]],
                })
    return findings


# ---------------------------------------------------------------------------
# Company name matching
# ---------------------------------------------------------------------------

_PT_PREFIX_RE = re.compile(r"^\s*(PT[\.\s]+|PT\b)\s*", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")
_MULTISPACE_RE = re.compile(r"\s+")


def normalize_company_name(s: str) -> str:
    """Lowercase, strip PT prefix, drop punctuation, collapse spaces."""
    s = s or ""
    s = _PT_PREFIX_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _MULTISPACE_RE.sub(" ", s).strip().lower()
    return s


def levenshtein(a: str, b: str) -> int:
    """Iterative Levenshtein distance — small ints, no DP overhead."""
    if a == b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return len(b)
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, 1):
        cur = [i]
        for j, ca in enumerate(a, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def match_company(
    folder_name: str,
    companies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """3-tier match: exact → normalized → fuzzy (Levenshtein <= 3)."""
    if not folder_name:
        return None

    fnorm = normalize_company_name(folder_name)
    if not fnorm:
        return None

    # Tier 1: exact case-insensitive
    for c in companies:
        if (c["company_name"] or "").strip().lower() == folder_name.strip().lower():
            return {"company": c, "tier": "T1_exact", "score": 1.0}

    # Tier 2: normalized match
    for c in companies:
        cnorm = normalize_company_name(c["company_name"])
        if cnorm and cnorm == fnorm:
            return {"company": c, "tier": "T2_normalized", "score": 0.95}

    # Tier 3: fuzzy on normalized form, Levenshtein <= 3, length >= 6 chars
    best = None
    best_dist = 99
    for c in companies:
        cnorm = normalize_company_name(c["company_name"])
        if not cnorm or len(cnorm) < 6:
            continue
        d = levenshtein(fnorm, cnorm)
        if d < best_dist:
            best_dist = d
            best = c
    if best is not None and best_dist <= 3:
        return {
            "company": best,
            "tier": "T3_fuzzy",
            "score": 1.0 - (best_dist / max(len(fnorm), 1)),
            "edit_distance": best_dist,
        }

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_discovery() -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    drive = build_drive_service(prefer_user_oauth=True)
    findings = walk_tax_dept(drive)
    LOG.info("walked tax-dept → %d company folders found", len(findings))

    conn = await asyncpg.connect(_resolve_db_url())
    try:
        companies = await fetch_all_companies(conn)
        LOG.info("loaded %d companies from DB", len(companies))

        matched: list[dict[str, Any]] = []
        unmatched: list[dict[str, Any]] = []

        for f in findings:
            result = match_company(f["company_folder_name"], companies)
            if result is None:
                unmatched.append(f)
                continue
            client_rows = await fetch_clients_for_company(conn, result["company"]["id"])
            matched.append({
                **f,
                "matched_company_id": result["company"]["id"],
                "matched_company_name": result["company"]["company_name"],
                "matched_company_npwp": result["company"]["npwp_company"],
                "match_tier": result["tier"],
                "match_score": result["score"],
                "edit_distance": result.get("edit_distance"),
                "linked_clients": [
                    {"id": r["id"], "full_name": r["full_name"], "role": r["role"], "is_primary": r["is_primary"]}
                    for r in client_rows
                ],
                "linked_clients_count": len(client_rows),
            })
    finally:
        await conn.close()

    # Stats by tier
    by_tier: dict[str, int] = {}
    by_team: dict[str, int] = {}
    for m in matched:
        by_tier[m["match_tier"]] = by_tier.get(m["match_tier"], 0) + 1
        by_team[m["team_member"]] = by_team.get(m["team_member"], 0) + 1

    total_clients_reached = len({
        c["id"]
        for m in matched
        for c in m["linked_clients"]
    })

    report = {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "tax_dept_root_folder": TAX_DEPT_ROOT,
        "totals": {
            "company_folders_found": len(findings),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "unique_clients_reached": total_clients_reached,
        },
        "by_match_tier": by_tier,
        "by_team_member": by_team,
        "matched": matched,
        "unmatched": unmatched,
    }
    return report


def main() -> int:
    report = asyncio.run(run_discovery())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"tax_dept_discovery_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    t = report["totals"]
    print()
    print(f"  Tax-dept discovery — {report['started_at']}")
    print(f"  -----------------------------------------")
    print(f"  company folders found    : {t['company_folders_found']}")
    print(f"  matched to companies     : {t['matched']}")
    print(f"  unmatched                : {t['unmatched']}")
    print(f"  unique CRM clients       : {t['unique_clients_reached']}")
    print()
    print(f"  Match tier breakdown:")
    for tier, n in sorted(report["by_match_tier"].items()):
        print(f"    {tier:<18} {n:>4}")
    print()
    print(f"  Per-team-member:")
    for tm, n in sorted(report["by_team_member"].items(), key=lambda x: -x[1]):
        print(f"    {tm:<20} {n:>4}")
    print()
    print(f"  Report saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
