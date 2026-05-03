#!/usr/bin/env python3
"""Parse JSON files produced by Claude Drive Panel batches and write to DB.

Reads /Users/nuzantara/Desktop/crm_summaries/client_*.json, validates each
against L1ClientSummary (Pydantic), and writes clients.ai_summary + audit
event. Files that fail validation are moved to _rejects/ with the error.

Usage:
    python scripts/crm_guardian_ingest_summaries.py --dry-run
    python scripts/crm_guardian_ingest_summaries.py --apply
    python scripts/crm_guardian_ingest_summaries.py --apply --archive
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

from backend.services.crm_guardian.schemas import L1ClientSummary, SCHEMA_VERSION  # noqa: E402

LOG = logging.getLogger("crm_guardian.ingest")

SUMMARIES_DIR = Path.home() / "Desktop" / "crm_summaries"
REJECTS_DIR = SUMMARIES_DIR / "_rejects"
ARCHIVE_DIR = SUMMARIES_DIR / "_processed"
CLIENT_FILE_RE = re.compile(r"^client_(\d+)\.json$")


def _resolve_db_url() -> str:
    secrets = Path.home() / ".nuzantara-secrets.env"
    if not secrets.exists():
        raise RuntimeError(f"Secrets file not found: {secrets}")
    # Support lines like "DATABASE_URL=…", "export DATABASE_URL=…",
    # or "DATABASE_URL_LOCAL=…" (direct localhost URL, flyctl proxy).
    lines = secrets.read_text().splitlines()
    # 1) Prefer DATABASE_URL_LOCAL (no rewrite needed)
    for line in lines:
        stripped = line.lstrip().lstrip("export ").strip()
        if stripped.startswith("DATABASE_URL_LOCAL="):
            return stripped.split("=", 1)[1].strip().strip('"')
    # 2) Fall back to DATABASE_URL with host rewrite
    for line in lines:
        stripped = line.lstrip().lstrip("export ").strip()
        if stripped.startswith("DATABASE_URL="):
            url = stripped.split("=", 1)[1].strip().strip('"')
            return re.sub(r"@[^:/]+(\.internal)?:\d+", "@localhost:15432", url)
    raise RuntimeError("DATABASE_URL / DATABASE_URL_LOCAL not found in .nuzantara-secrets.env")


async def ingest_file(conn, path: Path, dry_run: bool, run_id: str) -> dict:
    m = CLIENT_FILE_RE.match(path.name)
    if not m:
        return {"file": path.name, "status": "skipped", "error": "filename pattern"}
    client_id = int(m.group(1))

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"file": path.name, "status": "error", "error": f"json parse: {e}"}

    # Handle explicit error marker from Claude
    if isinstance(raw, dict) and raw.get("error"):
        return {
            "file": path.name, "client_id": client_id, "status": "error",
            "error": f"worker reported: {raw.get('error')}",
        }

    # Check client exists + has folder
    client = await conn.fetchrow(
        "SELECT id, google_drive_folder_id FROM clients WHERE id=$1 AND deleted_at IS NULL",
        client_id,
    )
    if not client:
        return {"file": path.name, "client_id": client_id, "status": "error",
                "error": "client not found or deleted"}

    folder_id = client["google_drive_folder_id"]

    # Enrich metadata Gemini can't know
    raw.setdefault("schema_version", SCHEMA_VERSION)
    raw["client_id"] = client_id
    raw["generated_at"] = raw.get("generated_at") or datetime.now(timezone.utc).isoformat()
    raw["source_folder_id"] = raw.get("source_folder_id") or folder_id
    raw["source_file_count"] = raw.get("source_file_count") or 0
    raw["source_file_fingerprint"] = raw.get("source_file_fingerprint") or ("manual_" + uuid.uuid4().hex[:24])

    try:
        summary = L1ClientSummary.model_validate(raw)
    except Exception as e:
        return {"file": path.name, "client_id": client_id, "status": "error",
                "error": f"pydantic: {str(e)[:200]}"}

    if dry_run:
        return {
            "file": path.name, "client_id": client_id, "status": "dry_run",
            "archetype": summary.profile.archetype, "tier": summary.profile.tier,
            "confidence": summary.extraction_confidence,
        }

    await conn.execute(
        """
        UPDATE clients
        SET ai_summary = $1::jsonb,
            ai_summary_generated_at = NOW(),
            ai_summary_file_hash = $2,
            ai_summary_schema_version = $3
        WHERE id = $4
        """,
        summary.model_dump_json(),
        raw["source_file_fingerprint"],
        SCHEMA_VERSION,
        client_id,
    )
    await conn.execute(
        """
        INSERT INTO crm_guardian_events
        (invariant_id, action, target_type, target_id, client_id,
         after_state, status, dry_run, run_id, notes)
        VALUES ('I10_summary_l1', 'generate_summary', 'client', $1, $2,
                $3::jsonb, 'success', false, $4::uuid, $5)
        """,
        str(client_id), client_id, summary.model_dump_json(),
        run_id, f"ingest_from_claude_drive_panel file={path.name}",
    )
    return {
        "file": path.name, "client_id": client_id, "status": "success",
        "archetype": summary.profile.archetype, "tier": summary.profile.tier,
        "confidence": summary.extraction_confidence,
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--apply", action="store_true", default=False)
    ap.add_argument("--archive", action="store_true", default=False,
                    help="Move processed files to _processed/ after success")
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        ap.error("specify --dry-run or --apply")
    dry_run = args.dry_run or not args.apply

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not SUMMARIES_DIR.exists():
        LOG.error("Directory %s does not exist", SUMMARIES_DIR)
        return 2
    REJECTS_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)

    files = sorted(SUMMARIES_DIR.glob("client_*.json"))
    if not files:
        LOG.info("No client_*.json files found in %s", SUMMARIES_DIR)
        return 0

    import asyncpg
    conn = await asyncpg.connect(_resolve_db_url())
    run_id = str(uuid.uuid4())
    LOG.info("Ingesting %d files  dry_run=%s  run_id=%s", len(files), dry_run, run_id)

    results: list[dict] = []
    for path in files:
        try:
            r = await ingest_file(conn, path, dry_run, run_id)
        except Exception as e:
            LOG.exception("crash on %s", path.name)
            r = {"file": path.name, "status": "error", "error": f"crash: {e}"}
        results.append(r)
        LOG.info("%s", r)

        if not dry_run and args.archive:
            if r["status"] == "success":
                shutil.move(str(path), str(ARCHIVE_DIR / path.name))
            elif r["status"] == "error":
                # write sidecar .err.json with the error
                err_path = REJECTS_DIR / (path.stem + ".err.json")
                err_path.write_text(json.dumps(r, indent=2, default=str))
                shutil.move(str(path), str(REJECTS_DIR / path.name))

    await conn.close()

    # Summary
    ok = sum(1 for r in results if r["status"] in ("success", "dry_run"))
    err = sum(1 for r in results if r["status"] == "error")
    skip = sum(1 for r in results if r["status"] == "skipped")
    print(json.dumps({
        "run_id": run_id, "dry_run": dry_run,
        "counts": {"success_or_dry": ok, "error": err, "skipped": skip},
        "results": results,
    }, indent=2, default=str))
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
