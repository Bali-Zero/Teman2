"""1st of month 04:30 WITA — full monthly retrain.

Invoked by `com.balizero.sota.m13-monthly.plist` through
`scripts/wr2-cron-wrapper.sh backend.services.sota_loop.m13_monthly`.

Re-runs: baseline snapshot, competitor scraping (if CSV ready),
persona inference, Consiglio. Archives 09_wr2_weights_YYYY-MM.json.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("sota.m13.monthly")


def _repo_root() -> Path:
    env = os.environ.get("NUZANTARA_REPO_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4]


def run(cmd: list[str], *, timeout: int = 1800) -> int:
    logger.info("run: %s", " ".join(cmd))
    r = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if r.returncode != 0:
        logger.warning("cmd rc=%s stderr=%s", r.returncode, r.stderr[-400:])
    return r.returncode


def main() -> int:
    repo = _repo_root()
    research = repo / "research" / "sota-social-2026-v1"

    dsn = os.environ["DATABASE_URL"]
    result = subprocess.run(
        [
            "psql",
            dsn,
            "-tAc",
            "SELECT value FROM system_settings WHERE key='sota_m13_monthly_enabled'",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip() != "true":
        logger.info("monthly kill switch OFF — exit")
        return 0

    month = datetime.now(timezone.utc).strftime("%Y-%m")

    # Step 1: re-fetch Ahrefs snapshot (subset of baseline)
    run(["python", str(repo / "scripts" / "sota_build_baseline.py")])

    # Step 2: re-ingest competitor corpus IF new CSV available AND ingest
    # script exists. Task 13 (sota_ingest_competitors.py) was deferred from
    # Fase 0 — monthly cron should not crash if it's still missing.
    csv_path = research / "competitor_raw.csv"
    ingest_script = repo / "scripts" / "sota_ingest_competitors.py"
    if csv_path.is_file():
        mtime = datetime.fromtimestamp(csv_path.stat().st_mtime, tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - mtime).days
        if age_days >= 35:
            logger.warning(
                "competitor CSV is %d days old — ask team to re-scrape", age_days
            )
        elif not ingest_script.is_file():
            logger.warning(
                "competitor CSV ready but ingest script missing — Task 13 still TODO; skipping"
            )
        else:
            run(["python", str(ingest_script)])

    # Step 3: re-infer personas (both waves)
    run(
        [
            "python",
            str(repo / "scripts" / "sota_infer_personas.py"),
            "--wave=both",
        ]
    )

    # Step 4: Consiglio v1 final pass
    rc = run(
        [
            "python",
            str(repo / "scripts" / "sota_consiglio_playbook.py"),
            "--wave=final",
        ]
    )

    # Step 5: archive WR2 weights for this month
    weights_path = research / "09_wr2_weights.json"
    if weights_path.is_file():
        new_weights = json.loads(weights_path.read_text())
        archive_path = research / f"09_wr2_weights_{month}.json"
        archive_path.write_text(
            json.dumps(new_weights, indent=2), encoding="utf-8"
        )
        logger.info("archived weights to %s", archive_path)

    # Write monthly report
    report = research / f"monthly_report_{month}.md"
    report.write_text(
        f"# SOTA Monthly Report {month}\n\n"
        f"Run at: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"Steps executed: ahrefs snapshot, competitor ingest, personas, Consiglio\n\n"
        f"Consiglio return code: {rc}\n\n"
        f"See `retrain_log.jsonl` and weekly reports for KPI deltas.\n",
        encoding="utf-8",
    )
    logger.info("monthly retrain complete: %s", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
