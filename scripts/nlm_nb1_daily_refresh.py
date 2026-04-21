#!/usr/bin/env python3
"""
NB-1 Daily Bundle Refresh for NotebookLM Knowledge Fabric.

Regenerates only the codebase bundles that changed in the last 24h,
then replaces them in NB-1 via nlm CLI.

Schedule: OpenClaw cron, 04:30 WITA daily
Duration: ~2 minutes
Cost: $0 (file operations + nlm CLI only)

Usage:
    python3 scripts/nlm_nb1_daily_refresh.py              # auto-detect changes
    python3 scripts/nlm_nb1_daily_refresh.py --force-all   # regenerate all bundles
    python3 scripts/nlm_nb1_daily_refresh.py --dry-run     # show what would change
"""

import glob
import json
import logging
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── ARCH-8 snapshot import (optional — graceful if evaluator not in sys.path) ──
try:
    _EVAL_DIR = Path(__file__).resolve().parent.parent / "apps" / "evaluator"
    if str(_EVAL_DIR) not in sys.path:
        sys.path.insert(0, str(_EVAL_DIR))
    from nlm_deep_research.source_snapshot import take_snapshot as _take_snapshot
    _SNAPSHOT_AVAILABLE = True
except Exception:
    _SNAPSHOT_AVAILABLE = False

# ── Config ──────────────────────────────────────────────
NB1_ID = "f6ecd115-dd89-4c9b-b3dd-071e0e2f1876"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "tmp_notebooklm"
NLM_BIN = Path.home() / ".local" / "bin" / "nlm"
LOG_DIR = PROJECT_ROOT / "logs"

# Bundle → git path mapping: which directories trigger which bundle
BUNDLE_MAP = {
    "backend_01_app_and_agents.txt": {
        "triggers": ["apps/backend-rag/backend/app/", "apps/backend-rag/backend/channels/"],
        "patterns": [
            "apps/backend-rag/backend/app/**/*.py",
            "apps/backend-rag/backend/channels/**/*.py",
        ],
        "excludes": ["__pycache__", ".pytest_cache", ".venv"],
    },
    "backend_02_services.txt": {
        "triggers": ["apps/backend-rag/backend/services/"],
        "patterns": ["apps/backend-rag/backend/services/**/*.py"],
        "excludes": ["__pycache__", ".pytest_cache", ".venv"],
    },
    "backend_03_core_and_misc.txt": {
        "triggers": [
            "apps/backend-rag/backend/core/",
            "apps/backend-rag/backend/llm/",
            "apps/backend-rag/backend/middleware/",
            "apps/backend-rag/backend/prompts/",
        ],
        "patterns": [
            "apps/backend-rag/backend/core/**/*.py",
            "apps/backend-rag/backend/llm/**/*.py",
            "apps/backend-rag/backend/middleware/**/*.py",
            "apps/backend-rag/backend/prompts/**/*.py",
        ],
        "excludes": ["__pycache__", ".venv"],
    },
    "nuzantara_frontend_mouth.txt": {
        "triggers": ["apps/mouth/src/"],
        "patterns": [
            "apps/mouth/src/**/*.tsx",
            "apps/mouth/src/**/*.ts",
        ],
        "excludes": ["node_modules", ".next", "out", "build"],
    },
    "nuzantara_mcp_ecosystem.txt": {
        "triggers": ["apps/nuzantara-mcp/", "apps/nuzantara-mcp-advanced/"],
        "patterns": [
            "apps/nuzantara-mcp/**/*.py",
            "apps/nuzantara-mcp-advanced/**/*.py",
        ],
        "excludes": ["node_modules", "dist", "build", ".venv", "__pycache__"],
    },
    "nuzantara_specific_apps.txt": {
        "triggers": [
            "apps/federation/",
            "apps/bali-intel-scraper/",
            "apps/evaluator/",
        ],
        "patterns": [
            "apps/federation/**/*.py",
            "apps/bali-intel-scraper/**/*.py",
            "apps/evaluator/**/*.py",
        ],
        "excludes": ["node_modules", ".venv", "__pycache__", "build", "dist"],
    },
    "nuzantara_infrastructure.txt": {
        "triggers": ["fly.toml", "Dockerfile", "docker-compose", "vercel.json", ".github/"],
        "patterns": [
            "docker-compose*.yml",
            "fly.toml",
            "**/Dockerfile",
            "vercel.json",
            ".github/**/*.yml",
        ],
        "excludes": ["node_modules", ".venv"],
    },
    "nuzantara_rules_and_docs.txt": {
        "triggers": ["CLAUDE.md", "docs/"],
        "patterns": ["./*.md", "docs/**/*.md"],
        "excludes": [".venv", "node_modules", ".git", ".next", ".cache"],
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NB1-Refresh] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nb1-refresh")


def get_changed_files(hours: int = 24) -> list[str]:
    """Get files changed in the last N hours via git."""
    try:
        result = subprocess.run(
            ["git", "log", f"--since={hours} hours ago", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return list(set(files))
    except Exception as e:
        log.warning(f"git log failed: {e}, treating as full refresh")
        return ["FORCE_ALL"]


def detect_impacted_bundles(changed_files: list[str]) -> list[str]:
    """Determine which bundles need regeneration based on changed files."""
    if "FORCE_ALL" in changed_files:
        return list(BUNDLE_MAP.keys())

    impacted = set()
    for bundle_name, config in BUNDLE_MAP.items():
        for changed_file in changed_files:
            for trigger in config["triggers"]:
                if changed_file.startswith(trigger) or trigger in changed_file:
                    impacted.add(bundle_name)
                    break
    return sorted(impacted)


def create_bundle(bundle_name: str, patterns: list[str], excludes: list[str]) -> Path:
    """Create a single bundle file from glob patterns."""
    output_path = OUTPUT_DIR / bundle_name
    files_to_include = set()

    for pattern in patterns:
        full_pattern = str(PROJECT_ROOT / pattern)
        for filepath in glob.glob(full_pattern, recursive=True):
            if os.path.isfile(filepath):
                # Use path component matching, not substring (avoids "out" matching "mouth")
                path_parts = Path(filepath).parts
                if not any(ex in path_parts for ex in excludes):
                    files_to_include.add(filepath)

    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"# BUNDLE: {bundle_name}\n")
        outfile.write(f"# Generated: {datetime.now().isoformat()}\n")
        outfile.write(f"# Files: {len(files_to_include)}\n\n")

        for filepath in sorted(files_to_include):
            try:
                with open(filepath, "r", encoding="utf-8") as infile:
                    content = infile.read()
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                outfile.write(f"\n{'=' * 60}\n")
                outfile.write(f"--- FILE: {rel_path} ---\n")
                outfile.write(f"{'=' * 60}\n\n")
                outfile.write(content)
                outfile.write("\n")
            except Exception:
                pass

    size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"  {bundle_name}: {size_mb:.1f}MB, {len(files_to_include)} files")
    return output_path


def get_nb1_sources() -> dict[str, list[str]]:
    """Get current NB-1 sources mapping: title -> list of source_ids.

    Uses `nlm source list` which returns proper JSON.
    Multiple source_ids per title means duplicates exist.
    The list is ordered by position (last = newest).
    """
    try:
        result = subprocess.run(
            [str(NLM_BIN), "source", "list", NB1_ID],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.warning(f"nlm source list failed: {result.stderr[:200]}")
            return {}

        raw = result.stdout.strip()
        if not raw:
            return {}

        data = json.loads(raw)

        # nlm CLI may wrap in {"value": [...]} or return a list directly
        sources_raw: list[dict]
        if isinstance(data, list):
            sources_raw = data
        elif isinstance(data, dict) and "value" in data:
            sources_raw = data["value"] if isinstance(data["value"], list) else []
        elif isinstance(data, dict) and "sources" in data:
            sources_raw = data["sources"] if isinstance(data["sources"], list) else []
        else:
            sources_raw = []

        # Build title -> [source_ids] mapping (preserving order = position)
        title_to_ids: dict[str, list[str]] = {}
        for s in sources_raw:
            source_id = s.get("source_id") or s.get("id") or s.get("sourceId", "")
            title = s.get("title") or s.get("name", "")
            if source_id and title:
                title_to_ids.setdefault(title, []).append(str(source_id))

        log.info(f"NB-1 has {sum(len(v) for v in title_to_ids.values())} sources across {len(title_to_ids)} unique titles")
        return title_to_ids
    except Exception as e:
        log.warning(f"Could not get NB-1 sources: {e}")
        return {}


def nlm_replace_source(bundle_name: str, bundle_path: Path, old_source_ids: list[str] | None) -> bool:
    """Delete ALL old sources with the same title, then add the new bundle to NB-1.

    Implements delete-before-add to prevent duplicate accumulation.

    Args:
        bundle_name: Bundle filename (used for logging).
        bundle_path: Path to the regenerated bundle file.
        old_source_ids: List of existing source IDs to delete before adding.
                        Can be None or empty if no existing sources found.

    Returns:
        True if upload succeeded, False otherwise.
    """
    try:
        # Delete ALL old sources with the same title
        if old_source_ids:
            for old_id in old_source_ids:
                log.info(f"  Deleting old source: {old_id}")
                try:
                    subprocess.run(
                        [str(NLM_BIN), "source", "delete", old_id, "--confirm"],
                        capture_output=True, text=True, timeout=30,
                    )
                    time.sleep(1.0)  # Rate limiting between deletes
                except Exception as del_err:
                    log.warning(f"  Failed to delete {old_id}: {del_err} (continuing)")

        # Add new source
        log.info(f"  Uploading: {bundle_name}")
        result = subprocess.run(
            [str(NLM_BIN), "source", "add", NB1_ID, "--type", "file", "--file", str(bundle_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            log.info(f"  {bundle_name} uploaded OK")
            return True
        else:
            log.error(f"  Upload failed: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        log.error(f"  Upload timeout for {bundle_name}")
        return False
    except Exception as e:
        log.error(f"  Upload error: {e}")
        return False


MAX_SOURCES_THRESHOLD = 60


def _check_source_count_invariant() -> None:
    """Post-refresh invariant: warn if NB-1 source count exceeds threshold.

    If total sources > MAX_SOURCES_THRESHOLD, log a WARNING.
    This catches runaway duplication early.
    """
    try:
        sources = get_nb1_sources()
        total = sum(len(ids) for ids in sources.values())
        if total > MAX_SOURCES_THRESHOLD:
            msg = (
                f"⚠️ NB-1 source count ALERT: {total} sources "
                f"(threshold: {MAX_SOURCES_THRESHOLD}). "
                f"Possible duplicate accumulation — run nlm_nb1_dedup_cleanup.py"
            )
            log.warning(msg)
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
            if bot_token:
                try:
                    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
                    urllib.request.urlopen(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data=data,
                        timeout=10,
                    )
                except Exception:
                    pass
        else:
            log.info(f"Source count OK: {total}/{MAX_SOURCES_THRESHOLD}")
    except Exception as e:
        log.warning(f"Could not check source count invariant: {e}")


def main():
    force_all = "--force-all" in sys.argv
    dry_run = "--dry-run" in sys.argv

    start_time = time.time()
    log.info("=" * 50)
    log.info("NB-1 Daily Bundle Refresh")
    log.info(f"Project: {PROJECT_ROOT}")
    log.info(f"NLM CLI: {NLM_BIN} ({'found' if NLM_BIN.exists() else 'MISSING'})")
    log.info(f"Mode: {'FORCE ALL' if force_all else 'DRY RUN' if dry_run else 'auto-detect'}")

    # Step 1: Detect changes
    if force_all:
        changed_files = ["FORCE_ALL"]
    else:
        changed_files = get_changed_files(24)
        log.info(f"Changed files (24h): {len(changed_files)}")

    if not changed_files:
        log.info("No changes detected. Nothing to refresh.")
        return

    # Step 2: Determine impacted bundles
    impacted = detect_impacted_bundles(changed_files)
    log.info(f"Impacted bundles: {len(impacted)}/{len(BUNDLE_MAP)}")
    for b in impacted:
        log.info(f"  → {b}")

    if not impacted:
        log.info("No bundles impacted. Nothing to refresh.")
        return

    if dry_run:
        log.info("DRY RUN — would regenerate these bundles:")
        for b in impacted:
            log.info(f"  {b}")
        return

    # Step 3: Regenerate impacted bundles
    log.info("Regenerating bundles...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    regenerated = []
    for bundle_name in impacted:
        config = BUNDLE_MAP[bundle_name]
        bundle_path = create_bundle(bundle_name, config["patterns"], config["excludes"])
        regenerated.append((bundle_name, bundle_path))

    # Step 4: Upload to NLM (if nlm CLI available)
    if not NLM_BIN.exists():
        log.warning(f"nlm CLI not found at {NLM_BIN} — bundles regenerated but NOT uploaded")
        log.info("Upload manually: nlm source add NB1_ID --type file --file <bundle>")
    else:
        log.info("Uploading to NB-1 (delete-before-add)...")

        # ARCH-8: snapshot before any mutation
        if _SNAPSHOT_AVAILABLE:
            try:
                snap_path = _take_snapshot(NB1_ID, "nb1_codebase")
                log.info(f"ARCH-8 snapshot saved: {snap_path.name}")
            except Exception as snap_err:
                log.warning(f"ARCH-8 snapshot failed (continuing): {snap_err}")
        else:
            log.debug("ARCH-8 snapshot not available (evaluator not in path)")

        # Fetch current sources to find existing IDs by title
        existing_sources = get_nb1_sources()

        uploaded = 0
        total_deleted = 0
        for bundle_name, bundle_path in regenerated:
            # Find all existing source IDs matching this bundle title
            old_ids = existing_sources.get(bundle_name, [])
            if old_ids:
                log.info(f"  Found {len(old_ids)} existing source(s) for {bundle_name} — will delete before add")
                total_deleted += len(old_ids)
            else:
                log.info(f"  No existing source for {bundle_name} — adding fresh")

            if nlm_replace_source(bundle_name, bundle_path, old_source_ids=old_ids):
                uploaded += 1

        log.info(f"Uploaded: {uploaded}/{len(regenerated)}, deleted {total_deleted} old sources")

        # Invariant check: warn if total source count exceeds threshold
        _check_source_count_invariant()

    # Step 5: Log summary
    duration = time.time() - start_time
    summary = {
        "timestamp": datetime.now().isoformat(),
        "duration_s": round(duration, 1),
        "changed_files": len(changed_files),
        "bundles_regenerated": len(regenerated),
        "bundles": [b[0] for b in regenerated],
    }

    log.info(f"Completed in {duration:.1f}s")
    log.info(json.dumps(summary, indent=2))

    # Save log
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = LOG_DIR / "nlm_nb1_refresh.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(summary) + "\n")

    # Staleness alert: warn if the log hasn't recorded any refresh in >48h
    _check_staleness_alert(log_file)

    # Sentinel heartbeat
    import pathlib, socket as _sock
    state_dir = pathlib.Path.home() / ".agent" / "decisions" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    _h = _sock.gethostname()
    _ts = int(time.time())
    (state_dir / "nlm_nb1_daily_refresh.last.json").write_text(
        f'{{"job":"nlm_nb1_daily_refresh","ts":{_ts},"status":"ok","host":"{_h}"}}'
    )


def _check_staleness_alert(log_file: Path) -> None:
    """Alert via Telegram if no NB-1 refresh has been logged in the last 48 hours."""
    import urllib.parse
    import urllib.request

    threshold_hours = 48
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "1125336968")

    if not log_file.exists():
        return

    now_ts = time.time()
    last_run_ts: float | None = None

    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                    if last_run_ts is None or ts > last_run_ts:
                        last_run_ts = ts
                except Exception:
                    pass
    except Exception:
        return

    if last_run_ts is None:
        return

    age_hours = (now_ts - last_run_ts) / 3600
    if age_hours > threshold_hours:
        msg = f"⚠️ NB-1 refresh STALE: last run was {age_hours:.0f}h ago (threshold: {threshold_hours}h)"
        log.warning(msg)
        if bot_token:
            try:
                data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
                urllib.request.urlopen(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage", data, timeout=10
                )
            except Exception as e:
                log.warning(f"Telegram alert failed: {e}")


if __name__ == "__main__":
    main()
