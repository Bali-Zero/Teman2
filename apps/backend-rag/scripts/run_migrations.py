#!/usr/bin/env python3
"""
run_migrations.py — CI migration runner for Fly.io deployment.

Called from .github/workflows/fly-deploy.yml between gate and deploy.
Uses flyctl ssh console to run migrations on the running app instance.

Exit codes:
  0 — success (migrations applied or nothing pending)
  1 — failure (blocks deploy to prevent schema drift)
"""

import os
import subprocess
import sys
from datetime import datetime, timezone


def log(msg: str) -> None:
    print(f"[run_migrations {datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    app = os.environ.get("FLY_APP", "nuzantara-rag")
    log(f"Running migrations on app: {app}")

    # flyctl ssh console runs a command on a live machine.
    # We run the migration manager which is already in the image.
    cmd = [
        "flyctl", "ssh", "console",
        "--app", app,
        "--command", "python -m backend.db.migrate apply-all",
    ]

    try:
        result = subprocess.run(
            cmd,
            timeout=180,
            text=True,
        )
    except subprocess.TimeoutExpired:
        log("ERROR: Migration timed out after 180s — blocking deploy")
        sys.exit(1)
    except FileNotFoundError:
        log("ERROR: flyctl not found in PATH")
        sys.exit(1)

    if result.returncode == 0:
        log("Migrations completed successfully")
        sys.exit(0)
    else:
        log(f"ERROR: Migration failed (exit={result.returncode}) — blocking deploy")
        sys.exit(1)


if __name__ == "__main__":
    main()
