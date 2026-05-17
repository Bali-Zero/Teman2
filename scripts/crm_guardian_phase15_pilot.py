#!/usr/bin/env python3
"""Phase 1.5 pilot — re-process the same 6 audited clients with OCR-enabled
worker (Phase 1.5) so we can diff smartness vs the Phase 1 backup.

Clients (matches the Phase 1 smartness audit set):
  70  Oleksandr Ozolin
  83  Sofia Mueller (the bulk-step-1 hallucination case)
  266 Romain Pascal Baillieu
  278 Declan Thompson & Shannon Knowles
  283 Roman Pukhov
  350 Armando Puddu (suspected-deceased filename case)

Mode: enqueue with force=True (bypasses I10b enabled-guard) + run worker
SYNCHRONOUSLY (no LaunchAgent) so we can observe latency + content snippets
per client. Worker may be invoked in --dry-run (audit-only) or production
mode via this script's --dry-run flag.

Usage:
    python scripts/crm_guardian_phase15_pilot.py --dry-run     # safe: no writes to ai_summary
    python scripts/crm_guardian_phase15_pilot.py               # writes ai_summary
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

# Import worker module lazily via spec so we can re-use its run_one_client
_WORKER_PATH = REPO_ROOT / "scripts" / "crm_guardian_gemini_cli_worker.py"
_spec = importlib.util.spec_from_file_location("crm_guardian_worker", _WORKER_PATH)
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)  # type: ignore[union-attr]

import asyncpg
from backend.services.crm_guardian.base import build_drive_service
from backend.services.crm_guardian.summary_queue import enqueue_client

PILOT_CLIENTS: list[int] = [70, 83, 266, 278, 283, 350]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
LOG = logging.getLogger("phase15_pilot")


async def run_pilot(*, dry_run: bool) -> dict[str, Any]:
    db_url = worker._resolve_db_url()
    drive_service = build_drive_service(prefer_user_oauth=True)
    prompt_template = worker.DEFAULT_PROMPT_FILE.read_text(encoding="utf-8")

    started = datetime.now(timezone.utc)
    run_id = str(__import__("uuid").uuid4())
    results: list[dict[str, Any]] = []

    conn = await asyncpg.connect(db_url)
    try:
        for client_id in PILOT_CLIENTS:
            LOG.info("=" * 60)
            LOG.info("PILOT client_id=%d (run_id=%s)", client_id, run_id)
            LOG.info("=" * 60)

            # Enqueue with force=True to bypass I10b guard
            enqueue_result = await enqueue_client(
                conn, client_id,
                enqueued_by=f"phase15_pilot:{run_id}",
                force=True,
            )
            LOG.info("enqueue %s", enqueue_result)

            # Skip if no queue_id (client_not_found / no_drive_folder)
            if enqueue_result["action"] not in ("inserted", "already_pending"):
                results.append({
                    "client_id": client_id, "status": "skipped",
                    "error": enqueue_result["action"],
                })
                continue

            start_ts = time.monotonic()
            try:
                outcome = await worker.run_one_client(
                    conn, drive_service, prompt_template,
                    client_id, dry_run, run_id,
                )
            except Exception as e:
                LOG.exception("worker failed for client %d", client_id)
                outcome = {
                    "client_id": client_id, "status": "error",
                    "error": f"worker_exception: {e}",
                }
            outcome["duration_seconds"] = round(time.monotonic() - start_ts, 1)
            results.append(outcome)

            LOG.info("OUTCOME: %s", json.dumps(outcome, default=str)[:300])

    finally:
        await conn.close()

    finished = datetime.now(timezone.utc)
    return {
        "run_id": run_id,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "dry_run": dry_run,
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Worker runs in dry_run mode (no clients.ai_summary write)",
    )
    ap.add_argument(
        "--clients", type=str, default=None,
        help="Comma-separated client_ids (default: full pilot 70,83,266,278,283,350)",
    )
    args = ap.parse_args()

    if args.clients:
        global PILOT_CLIENTS
        PILOT_CLIENTS = [int(x.strip()) for x in args.clients.split(",") if x.strip()]
        LOG.info("PILOT clients overridden: %s", PILOT_CLIENTS)

    audit = asyncio.run(run_pilot(dry_run=args.dry_run))

    out_dir = Path.home() / ".crm_guardian" / "pilot_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"phase15-{audit['run_id']}.json"
    out_path.write_text(json.dumps(audit, indent=2, default=str))

    print(f"\nPilot finished in {audit['duration_seconds']:.1f}s")
    print(f"Audit file: {out_path}\n")
    for r in audit["results"]:
        cid = r.get("client_id")
        status = r.get("status", "?")
        dur = r.get("duration_seconds", "?")
        extra = (
            f"conf={r.get('confidence', '?')} files={r.get('files_total', '?')}"
            if status == "success" else r.get("error", "")
        )
        print(f"  client {cid:>4} → {status:<8} ({dur}s)  {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
