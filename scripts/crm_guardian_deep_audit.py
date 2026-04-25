#!/usr/bin/env python3
"""
Deep audit for crm-guardian — Pro-local runner.

Reads Fly Postgres via local tunnel (flyctl proxy 15432), queries Drive via service
account (~/.config/gcloud/legacy_credentials/nuzantara-google-drive-sa*/adc.json),
and for each active/prospect/onboarding client finds satellite folders with their
name across all accessible Drive, building a consolidation plan.

Results are written incrementally to research/compliance/ (one row per client in
a .jsonl file + one final summary .json). Fully resumable: re-running skips
already-processed client IDs.

Usage:
    # Must have flyctl proxy open: `flyctl proxy 15432:5432 -a nuzantara-postgres`
    python3 scripts/crm_guardian_deep_audit.py                    # full run
    python3 scripts/crm_guardian_deep_audit.py --limit 20         # smoke test
    python3 scripts/crm_guardian_deep_audit.py --resume           # resume (default behavior anyway)
    python3 scripts/crm_guardian_deep_audit.py --client-ids 10552 # just specific clients

No Fly ssh. No container kills. Runs locally as long as you need.
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import sys
import time
from pathlib import Path

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / "apps" / "backend-rag" / ".env"
OUTPUT_DIR = PROJECT_ROOT / "research" / "compliance" / "deep_audit_2026-04-24"
PARTIAL_FILE = OUTPUT_DIR / "plan.jsonl"
SKIPPED_FILE = OUTPUT_DIR / "skipped.jsonl"
LOG_FILE = OUTPUT_DIR / "run.log"

INDIVIDUAL_CRM_ID = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"
COMPANIES_ID = "1PGRBCSzXc8T3LYqEB1-hucBaH2YW77Av"


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _load_db_url() -> str:
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("DATABASE_URL=") and "@localhost:15432" in line:
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL for localhost:15432 not found in .env")


def _build_drive():
    """Resolve SA credentials, preferring fresh JSON pulled from Fly env.

    Order: $NUZANTARA_DRIVE_SA_PATH  >  ~/.nuzantara-drive-sa.json  >  legacy gcloud.
    The legacy gcloud copy is often stale (Invalid JWT Signature) since the key
    has been rotated in the Fly secrets; the fresh copy is refreshed manually
    from the running Fly container.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    candidates: list[str] = []
    env_path = os.environ.get("NUZANTARA_DRIVE_SA_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append(str(Path.home() / ".nuzantara-drive-sa.json"))
    candidates.extend(
        glob.glob(
            str(Path.home() / ".config/gcloud/legacy_credentials/nuzantara-google-drive-sa*/adc.json")
        )
    )

    for path in candidates:
        if path and Path(path).exists():
            with open(path) as f:
                sa_info = json.load(f)
            creds = service_account.Credentials.from_service_account_info(
                sa_info, scopes=["https://www.googleapis.com/auth/drive"]
            )
            _log(f"SA loaded from {path} (client_email={sa_info.get('client_email', '')[:40]}...)")
            return build("drive", "v3", credentials=creds, cache_discovery=False)

    raise RuntimeError(
        "SA JSON not found. Tried: "
        + ", ".join(candidates)
        + ". To refresh: pull GOOGLE_SERVICE_ACCOUNT_JSON from Fly and write to ~/.nuzantara-drive-sa.json"
    )


def _search(drive, q: str) -> list[dict]:
    out: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": q,
            "fields": "nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime, owners)",
            "pageSize": 1000,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = drive.files().list(**params).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _escape_q(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _children(drive, fid: str) -> list[dict]:
    try:
        return _search(drive, f"'{fid}' in parents and trashed = false")
    except Exception as exc:  # noqa: BLE001
        _log(f"  children({fid[:10]}...) error: {str(exc)[:80]}")
        return []


def _count_recursive(drive, fid: str, max_depth: int = 4, depth: int = 0) -> tuple[int, int]:
    if depth >= max_depth:
        return 0, 0
    children = _children(drive, fid)
    n_files = sum(1 for c in children if c["mimeType"] != "application/vnd.google-apps.folder")
    n_subs = sum(1 for c in children if c["mimeType"] == "application/vnd.google-apps.folder")
    for c in children:
        if c["mimeType"] == "application/vnd.google-apps.folder":
            f, s = _count_recursive(drive, c["id"], max_depth, depth + 1)
            n_files += f
            n_subs += s
    return n_files, n_subs


def _load_processed_ids() -> set[int]:
    ids: set[int] = set()
    for path in (PARTIAL_FILE, SKIPPED_FILE):
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    ids.add(json.loads(line)["client_id"])
                except Exception:
                    pass
    return ids


def _append(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test: max N clients")
    parser.add_argument("--client-ids", type=str, default=None, help="Comma-separated client IDs to process")
    parser.add_argument("--no-resume", action="store_true", help="Reprocess clients already in partial file")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    db_url = _load_db_url()
    drive = _build_drive()

    conn = await asyncpg.connect(db_url)
    where = "full_name IS NOT NULL AND full_name != '' AND status IN ('active', 'prospect', 'onboarding')"
    if args.client_ids:
        ids = [int(x) for x in args.client_ids.split(",")]
        where = f"id = ANY($1::int[])"
        rows = await conn.fetch(
            f"SELECT id, full_name, status, google_drive_folder_id, assigned_to FROM clients WHERE {where} ORDER BY id",
            ids,
        )
    else:
        rows = await conn.fetch(
            f"SELECT id, full_name, status, google_drive_folder_id, assigned_to FROM clients WHERE {where} ORDER BY id"
        )
    await conn.close()

    _log(f"Loaded {len(rows)} clients from DB (active+prospect+onboarding)")

    if not args.no_resume:
        already = _load_processed_ids()
        rows = [r for r in rows if r["id"] not in already]
        _log(f"Resume mode: skipping {len(already)} already-processed, {len(rows)} remaining")

    if args.limit:
        rows = rows[: args.limit]
        _log(f"--limit {args.limit}: truncated to {len(rows)} rows")

    # Index canonical folders
    _log("Listing Individual_CRM children...")
    crm_children = _children(drive, INDIVIDUAL_CRM_ID)
    crm_folders = [c for c in crm_children if c["mimeType"] == "application/vnd.google-apps.folder"]
    canonical_ids = {f["id"] for f in crm_folders}
    _log(f"  {len(crm_folders)} canonical folders indexed in Individual_CRM")

    api_calls = 1
    t0 = time.time()
    total = len(rows)

    for idx, row in enumerate(rows, 1):
        cid = row["id"]
        name = row["full_name"].strip()
        try:
            words = [w for w in name.split() if len(w) > 1]
            if len(words) < 2:
                _append(SKIPPED_FILE, {"client_id": cid, "full_name": name, "reason": "single-word"})
                continue

            parts = sorted(words, key=len, reverse=True)[:2]
            q = (
                "mimeType = 'application/vnd.google-apps.folder' and trashed = false and "
                + " and ".join(f"name contains '{_escape_q(p)}'" for p in parts)
            )
            folders = _search(drive, q)
            api_calls += 1

            tokens = [w.lower() for w in words]
            matched = [f for f in folders if sum(1 for t in tokens if t in f["name"].lower()) >= min(2, len(tokens))]
            if not matched:
                _append(SKIPPED_FILE, {"client_id": cid, "full_name": name, "reason": "no match"})
                continue

            canonical = None
            satellites: list[dict] = []
            for f in matched:
                parents = f.get("parents", [])
                in_crm = f["id"] in canonical_ids or INDIVIDUAL_CRM_ID in parents
                if in_crm:
                    if canonical is None:
                        canonical = f
                    elif row["google_drive_folder_id"] and f["id"] == row["google_drive_folder_id"]:
                        satellites.append(canonical)
                        canonical = f
                    else:
                        satellites.append(f)
                else:
                    satellites.append(f)

            misc_id = None
            if canonical:
                for ch in _children(drive, canonical["id"]):
                    api_calls += 1
                    if ch["mimeType"] == "application/vnd.google-apps.folder" and ch["name"] == "99_Misc":
                        misc_id = ch["id"]
                        break

            sat_detail: list[dict] = []
            total_sat_files = 0
            total_sat_subs = 0
            for s in satellites:
                try:
                    direct = _children(drive, s["id"])
                    api_calls += 1
                    dn_f = sum(1 for c in direct if c["mimeType"] != "application/vnd.google-apps.folder")
                    dn_s = sum(1 for c in direct if c["mimeType"] == "application/vnd.google-apps.folder")
                    total_f, total_s = _count_recursive(drive, s["id"], max_depth=4)
                    api_calls += total_s
                except Exception as exc:  # noqa: BLE001
                    dn_f = dn_s = total_f = total_s = -1
                    _log(f"  satellite count error {s['name']!r}: {str(exc)[:60]}")
                owner_email = (s.get("owners") or [{}])[0].get("emailAddress", "")
                parent_id = (s.get("parents") or [None])[0]
                sat_detail.append(
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "owner_email": owner_email,
                        "parent_id": parent_id,
                        "created": s.get("createdTime"),
                        "modified": s.get("modifiedTime"),
                        "direct_files": dn_f,
                        "direct_subfolders": dn_s,
                        "total_files_recursive": total_f,
                        "total_subfolders_recursive": total_s,
                    }
                )
                total_sat_files += max(0, total_f)
                total_sat_subs += max(0, total_s)

            _append(
                PARTIAL_FILE,
                {
                    "client_id": cid,
                    "full_name": name,
                    "status": row["status"],
                    "assigned_to": row["assigned_to"],
                    "has_canonical": canonical is not None,
                    "canonical_folder_id": canonical["id"] if canonical else None,
                    "canonical_folder_name": canonical["name"] if canonical else None,
                    "canonical_misc_folder_id": misc_id,
                    "n_satellites": len(satellites),
                    "total_satellite_files": total_sat_files,
                    "total_satellite_subfolders": total_sat_subs,
                    "satellites": sat_detail,
                    "scanned_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                },
            )
        except Exception as exc:  # noqa: BLE001
            _append(
                SKIPPED_FILE,
                {"client_id": cid, "full_name": name, "reason": f"exception: {str(exc)[:140]}"},
            )
            _log(f"  error client {cid} {name!r}: {str(exc)[:100]}")

        if idx % 25 == 0 or idx == total:
            elapsed = time.time() - t0
            rate = idx / elapsed if elapsed > 0 else 0
            eta = (total - idx) / rate if rate > 0 else 0
            _log(f"{idx}/{total} clients | api={api_calls} | t={elapsed:.0f}s | rate={rate:.1f}/s | eta={eta:.0f}s")

    elapsed = time.time() - t0
    _log(f"DONE: {total} clients processed in {elapsed:.0f}s, {api_calls} api calls")


if __name__ == "__main__":
    asyncio.run(main())
