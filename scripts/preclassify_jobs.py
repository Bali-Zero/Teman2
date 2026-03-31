#!/usr/bin/env python3
"""
D0.5 — Pre-classify jobs in job_registry.json.

Applies deterministic ownership rules to each job and rewrites the registry
with updated `type` fields. Recomputes SHA256 checksum as the last step so
Sentinel's HALT gate (D0.4) remains valid after classification.

Rules (in priority order):
  1. Jobs with a `type` already set to a non-AUTO value → keep as-is
  2. Job name contains 'github_actions' or 'webhook' or 'pg_trigger' → OBSERVE_ONLY
  3. Job has `host: air` → openclaw (runs on Air, Sentinel monitors via heartbeat only)
  4. Job name matches known OpenClaw cron patterns → openclaw
  5. Remaining unknowns → AUTO (will be classified by LLM on first real failure)

Usage:
    python scripts/preclassify_jobs.py [--dry-run]
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REGISTRY_FILE = os.path.expanduser("~/.agent/decisions/job_registry.json")

# Patterns that indicate OBSERVE_ONLY (external triggers — retrying from Sentinel is wrong)
OBSERVE_ONLY_PATTERNS = [
    r"github[_-]?actions?",
    r"webhook",
    r"pg[_-]?trigger",
    r"cloud[_-]?function",
    r"vercel[_-]?cron",
    r"fly[_-]?cron",
]

# Patterns that indicate the job is managed by OpenClaw (local cron, macOS LaunchAgent)
OPENCLAW_PATTERNS = [
    r"openclaw",
    r"nlm[_-]",
    r"bali[_-]intel[_-]scraper",
    r"t4[_-]monitor",
    r"core[_-]guardian",
    r"war[_-]room",
    r"seo[_-]guardian",
    r"dlq[_-]autopilot",
    r"drive[_-]poll",
    r"rag[_-]canary",
    r"ollama[_-]",
    r"ragas[_-]eval",
    r"judgement[_-]day",
    r"system[_-]doctor",
    r"drive[_-]token[_-]watchdog",
]


def _checksum(jobs: dict) -> str:
    canonical = json.dumps(jobs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def classify_job(job_id: str, job_def: dict) -> str:
    """Return the inferred type for a job. Does NOT override explicit non-AUTO types."""
    current_type = job_def.get("type", "AUTO")
    if current_type not in ("AUTO", "", None):
        return current_type  # already classified — preserve

    name = job_id.lower()

    for pat in OBSERVE_ONLY_PATTERNS:
        if re.search(pat, name):
            return "OBSERVE_ONLY"

    # Explicit host override
    if job_def.get("host") == "air":
        return "openclaw"

    for pat in OPENCLAW_PATTERNS:
        if re.search(pat, name):
            return "openclaw"

    return "AUTO"


def run(dry_run: bool = False) -> None:
    try:
        raw = open(REGISTRY_FILE).read()
        data = json.loads(raw)
    except FileNotFoundError:
        logger.error(f"Registry not found: {REGISTRY_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error(f"Registry JSON corrupt: {exc}")
        sys.exit(1)

    jobs = data.get("jobs", {})
    changed: list[str] = []

    for job_id, job_def in jobs.items():
        old_type = job_def.get("type", "AUTO")
        new_type = classify_job(job_id, job_def)
        if old_type != new_type:
            job_def["type"] = new_type
            changed.append(f"  {job_id}: {old_type!r} → {new_type!r}")

    if changed:
        logger.info(f"{len(changed)} jobs reclassified:")
        for line in changed:
            logger.info(line)
    else:
        logger.info("No classification changes needed")

    # Always recompute checksum (jobs dict may have changed, or first run)
    new_checksum = _checksum(jobs)
    old_checksum = data.get("checksum", "<none>")
    data["jobs"] = jobs
    data["checksum"] = new_checksum

    if dry_run:
        logger.info(f"[dry-run] Would write {len(jobs)} jobs, checksum={new_checksum[:16]}…")
        logger.info(f"[dry-run] Old checksum={old_checksum[:16]}…")
        return

    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Registry updated: {len(jobs)} jobs, checksum={new_checksum[:16]}…")

    # Clear any stale HALT file now that registry is freshly validated
    halt_file = os.path.expanduser("~/.agent/decisions/REGISTRY_HALT")
    if os.path.exists(halt_file):
        os.remove(halt_file)
        logger.info("Cleared stale REGISTRY_HALT file")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-classify jobs in job_registry.json")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
