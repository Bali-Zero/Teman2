"""ARCH-6: Multi-Modal Content Factory.

Scheduled pipeline that generates audio overviews, infographics, mind maps,
and reports for each domain notebook on a weekly rotation.

Schedule (WITA):
    Mon: NB-2 audio (Immigration weekly digest)
    Tue: NB-3 mind-map (Company setup relationships)
    Wed: NB-4 infographic (Tax obligations overview)
    Thu: NB-6 audio (Operations compliance update)
    Fri: NB-7 audio (Editorial/content trends)
    Sun: Full suite — all notebooks

State file: multimodal_state.json (tracks last generated artifact per notebook/type)
Output dir: output/multimodal/

Usage:
    python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run
    python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run --dry-run
    python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run --force  # ignore schedule
    python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DIR = Path(__file__).parent
OUTPUT_DIR = _DIR / "output" / "multimodal"
STATE_FILE = _DIR / "multimodal_state.json"

WITA = timezone(timedelta(hours=8))

NLM_CLI = "nlm"
NLM_TIMEOUT = 300  # 5 min per artifact creation
DOWNLOAD_TIMEOUT = 120  # 2 min per download

# Telegram
_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Notebook registry (NB-2 through NB-8, NB-10)
# ---------------------------------------------------------------------------

NOTEBOOKS: dict[str, dict[str, str]] = {
    "nb2": {
        "id": "cff93ab0-813a-42f2-a8de-36987e724271",
        "label": "Immigration & Visa",
        "domain": "immigration",
    },
    "nb3": {
        "id": "933509f9-1561-403d-bd44-4a7a67a36df2",
        "label": "Company Setup",
        "domain": "company",
    },
    "nb4": {
        "id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
        "label": "Tax & Fiscal",
        "domain": "tax",
    },
    "nb5": {
        "id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
        "label": "Property & Real Estate",
        "domain": "property",
    },
    "nb6": {
        "id": "85207af3-352f-4554-8d2a-18f42cc541ba",
        "label": "Operations & Compliance",
        "domain": "operations",
    },
    "nb7": {
        "id": "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8",
        "label": "Editorial & Content",
        "domain": "editorial",
    },
    "nb8": {
        "id": "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c",
        "label": "Expat Life Bali",
        "domain": "expat",
    },
    "nb10": {
        "id": "f0307c2c-9220-4160-93c8-f4a6ef4a3b65",
        "label": "Team Guides Bali Zero",
        "domain": "team",
    },
}

# ---------------------------------------------------------------------------
# Weekly schedule: day_of_week → list[(notebook_key, artifact_type)]
# 0=Monday, 1=Tuesday, ..., 6=Sunday
# ---------------------------------------------------------------------------

WEEKLY_SCHEDULE: dict[int, list[tuple[str, str]]] = {
    0: [("nb2", "audio")],                          # Mon: Immigration audio
    1: [("nb3", "mind-map")],                        # Tue: Company mind-map
    2: [("nb4", "infographic")],                     # Wed: Tax infographic
    3: [("nb6", "audio")],                           # Thu: Operations audio
    4: [("nb7", "audio")],                           # Fri: Editorial audio
    5: [],                                            # Sat: rest
    6: [                                              # Sun: full suite
        ("nb2", "audio"), ("nb3", "audio"), ("nb4", "audio"),
        ("nb5", "audio"), ("nb6", "audio"), ("nb7", "audio"),
        ("nb8", "audio"), ("nb3", "mind-map"), ("nb4", "infographic"),
    ],
}

# Artifact type → download subcommand and file extension
ARTIFACT_META: dict[str, dict[str, str]] = {
    "audio":       {"download_cmd": "audio",      "ext": "m4a",  "display": "Audio Overview"},
    "infographic": {"download_cmd": "infographic", "ext": "png",  "display": "Infographic"},
    "mind-map":    {"download_cmd": "mind-map",   "ext": "json", "display": "Mind Map"},
    "report":      {"download_cmd": "report",     "ext": "md",   "display": "Report"},
}

# Re-generation interval per artifact type (hours)
MIN_REGEN_INTERVAL: dict[str, int] = {
    "audio":       7 * 24,   # weekly
    "infographic": 7 * 24,
    "mind-map":    7 * 24,
    "report":      7 * 24,
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArtifactRecord:
    """Tracks last successful generation of one artifact."""
    notebook_key: str
    artifact_type: str
    generated_at: str  # ISO UTC
    downloaded_at: Optional[str] = None
    output_path: Optional[str] = None
    artifact_id: Optional[str] = None


@dataclass
class RunResult:
    """Result of a single artifact generation run."""
    notebook_key: str
    artifact_type: str
    status: str          # "ok" | "skipped" | "error" | "dry_run"
    message: str = ""
    output_path: Optional[str] = None
    latency_s: float = 0.0


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _load_state() -> dict[str, Any]:
    """Load multimodal state file."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception as exc:
        logger.warning("Failed to load multimodal state: %s", exc)
        return {}


def _save_state(state: dict[str, Any]) -> None:
    """Save multimodal state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _state_key(notebook_key: str, artifact_type: str) -> str:
    return f"{notebook_key}:{artifact_type}"


def _get_last_generated(
    state: dict[str, Any],
    notebook_key: str,
    artifact_type: str,
) -> Optional[datetime]:
    """Return UTC datetime of last successful generation, or None."""
    record = state.get(_state_key(notebook_key, artifact_type))
    if not record:
        return None
    ts = record.get("generated_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _record_success(
    state: dict[str, Any],
    notebook_key: str,
    artifact_type: str,
    output_path: Optional[str] = None,
) -> None:
    """Record a successful generation in state."""
    key = _state_key(notebook_key, artifact_type)
    state[key] = {
        "notebook_key": notebook_key,
        "artifact_type": artifact_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def get_todays_tasks(now: Optional[datetime] = None) -> list[tuple[str, str]]:
    """Return list of (notebook_key, artifact_type) tasks scheduled for today."""
    if now is None:
        now = datetime.now(WITA)
    day = now.weekday()  # 0=Mon, 6=Sun
    return WEEKLY_SCHEDULE.get(day, [])


def should_generate(
    state: dict[str, Any],
    notebook_key: str,
    artifact_type: str,
    force: bool = False,
) -> tuple[bool, str]:
    """Check if artifact should be regenerated.

    Returns (should_generate, reason_string).
    """
    if force:
        return True, "forced"

    last = _get_last_generated(state, notebook_key, artifact_type)
    if last is None:
        return True, "never generated"

    min_hours = MIN_REGEN_INTERVAL.get(artifact_type, 7 * 24)
    age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    if age_hours < min_hours:
        return False, f"generated {age_hours:.1f}h ago (min {min_hours}h)"

    return True, f"stale ({age_hours:.1f}h old)"


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def _send_telegram(msg: str) -> bool:
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.debug("Telegram not configured — skipping notification")
        return False
    try:
        data = json.dumps({
            "chat_id": _CHAT_ID,
            "text": msg[:4096],
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# NLM CLI wrappers
# ---------------------------------------------------------------------------

def _run_nlm_create(
    artifact_type: str,
    notebook_id: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Create an artifact via nlm CLI.

    Returns (success, message).
    """
    # PR-E1 (2026-04-30): nlm CLI promoted infographic/mindmap to top-level
    # commands (out of the deprecated `studio create` namespace). `studio`
    # now only has status/delete/rename. New shape: `nlm <type> create NOTEBOOK_ID`.
    if artifact_type == "audio":
        cmd = [NLM_CLI, "audio", "create", notebook_id, "--format", "deep_dive", "--confirm"]
    elif artifact_type == "infographic":
        cmd = [NLM_CLI, "infographic", "create", notebook_id, "--confirm"]
    elif artifact_type == "mind-map":
        cmd = [NLM_CLI, "mindmap", "create", notebook_id, "--confirm"]
    elif artifact_type == "report":
        cmd = [NLM_CLI, "report", "create", notebook_id, "--confirm"]
    else:
        return False, f"Unknown artifact type: {artifact_type}"

    if dry_run:
        logger.info("[DRY-RUN] Would run: %s", " ".join(cmd))
        return True, "dry_run"

    logger.info("Creating %s for %s...", artifact_type, notebook_id)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=NLM_TIMEOUT,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            logger.error("nlm create %s failed: %s", artifact_type, err)
            return False, err
        return True, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, f"timeout after {NLM_TIMEOUT}s"
    except Exception as exc:
        return False, str(exc)


def _run_nlm_download(
    artifact_type: str,
    notebook_id: str,
    output_path: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Download an artifact via nlm CLI.

    Returns (success, message).
    """
    meta = ARTIFACT_META.get(artifact_type)
    if not meta:
        return False, f"No download meta for: {artifact_type}"

    cmd = [
        NLM_CLI, "download", meta["download_cmd"],
        notebook_id,
        "--output", output_path,
        "--no-progress",
    ]

    if dry_run:
        logger.info("[DRY-RUN] Would download: %s → %s", artifact_type, output_path)
        return True, "dry_run"

    logger.info("Downloading %s → %s", artifact_type, output_path)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            logger.error("nlm download %s failed: %s", artifact_type, err)
            return False, err
        return True, output_path
    except subprocess.TimeoutExpired:
        return False, f"download timeout after {DOWNLOAD_TIMEOUT}s"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------

def generate_artifact(
    notebook_key: str,
    artifact_type: str,
    state: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
) -> RunResult:
    """Generate one artifact for one notebook.

    Flow: check staleness → nlm create → download → update state.
    """
    t0 = time.monotonic()
    nb_info = NOTEBOOKS.get(notebook_key)
    if not nb_info:
        return RunResult(notebook_key, artifact_type, "error", f"Unknown notebook key: {notebook_key}")

    notebook_id = nb_info["id"]
    nb_label = nb_info["label"]

    # Check if regeneration is needed
    ok, reason = should_generate(state, notebook_key, artifact_type, force=force)
    if not ok:
        logger.info("Skipping %s/%s: %s", notebook_key, artifact_type, reason)
        return RunResult(notebook_key, artifact_type, "skipped", reason)

    logger.info("Generating %s/%s (%s): %s", notebook_key, artifact_type, nb_label, reason)

    # Create artifact
    created, create_msg = _run_nlm_create(artifact_type, notebook_id, dry_run=dry_run)
    if not created:
        return RunResult(
            notebook_key, artifact_type, "error",
            f"create failed: {create_msg}",
            latency_s=time.monotonic() - t0,
        )

    # Prepare output path
    now_wita = datetime.now(WITA)
    date_str = now_wita.strftime("%Y%m%d")
    meta = ARTIFACT_META.get(artifact_type, {})
    ext = meta.get("ext", "bin")
    output_dir = OUTPUT_DIR / notebook_key / artifact_type
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"{date_str}_{notebook_key}.{ext}")

    # Download artifact
    downloaded, dl_msg = _run_nlm_download(artifact_type, notebook_id, output_path, dry_run=dry_run)

    if dry_run:
        _record_success(state, notebook_key, artifact_type, output_path)
        return RunResult(notebook_key, artifact_type, "dry_run", "dry_run ok", output_path)

    if not downloaded:
        # Create succeeded but download failed — still record as partial success
        logger.warning("Created %s/%s but download failed: %s", notebook_key, artifact_type, dl_msg)
        _record_success(state, notebook_key, artifact_type, None)
        return RunResult(
            notebook_key, artifact_type, "error",
            f"created but download failed: {dl_msg}",
            latency_s=time.monotonic() - t0,
        )

    _record_success(state, notebook_key, artifact_type, output_path)
    latency = time.monotonic() - t0
    logger.info("✅ %s/%s done → %s (%.1fs)", notebook_key, artifact_type, output_path, latency)
    return RunResult(
        notebook_key, artifact_type, "ok",
        f"saved to {output_path}",
        output_path=output_path,
        latency_s=latency,
    )


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    tasks: Optional[list[tuple[str, str]]] = None,
    force: bool = False,
    dry_run: bool = False,
) -> list[RunResult]:
    """Run the multimodal pipeline for the given tasks (or today's schedule).

    Args:
        tasks: List of (notebook_key, artifact_type). If None, uses today's schedule.
        force: Ignore staleness check and regenerate everything.
        dry_run: Simulate without executing nlm CLI calls.

    Returns:
        List of RunResult for each task attempted.
    """
    if tasks is None:
        tasks = get_todays_tasks()

    if not tasks:
        logger.info("No multimodal tasks scheduled for today")
        return []

    state = _load_state()
    results: list[RunResult] = []

    logger.info("Multimodal pipeline: %d task(s)%s%s",
                len(tasks),
                " [FORCE]" if force else "",
                " [DRY-RUN]" if dry_run else "")

    for notebook_key, artifact_type in tasks:
        result = generate_artifact(notebook_key, artifact_type, state, force=force, dry_run=dry_run)
        results.append(result)
        if result.status not in ("skipped",):
            # Save state after each non-skipped task
            _save_state(state)

    _save_state(state)
    _send_run_summary(results, dry_run=dry_run)
    return results


def _send_run_summary(results: list[RunResult], dry_run: bool = False) -> None:
    """Send Telegram summary of pipeline run."""
    if not results:
        return

    ok = [r for r in results if r.status == "ok"]
    errors = [r for r in results if r.status == "error"]
    skipped = [r for r in results if r.status == "skipped"]
    dry_runs = [r for r in results if r.status == "dry_run"]

    prefix = "🧪 [DRY-RUN] " if dry_run else ""
    lines = [f"{prefix}🎬 <b>Multimodal Pipeline</b>"]
    lines.append(f"✅ {len(ok)} generated | ⏭️ {len(skipped)} skipped | ❌ {len(errors)} errors")

    for r in ok:
        nb = NOTEBOOKS.get(r.notebook_key, {})
        art = ARTIFACT_META.get(r.artifact_type, {})
        lines.append(f"  • {nb.get('label', r.notebook_key)} — {art.get('display', r.artifact_type)} ({r.latency_s:.0f}s)")

    for r in errors:
        nb = NOTEBOOKS.get(r.notebook_key, {})
        lines.append(f"  ❌ {nb.get('label', r.notebook_key)} — {r.artifact_type}: {r.message[:80]}")

    _send_telegram("\n".join(lines))


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------

def get_status() -> dict[str, Any]:
    """Return current state of all notebook/artifact combinations."""
    state = _load_state()
    now = datetime.now(timezone.utc)
    report: dict[str, Any] = {}

    for nb_key, nb_info in NOTEBOOKS.items():
        report[nb_key] = {"label": nb_info["label"], "artifacts": {}}
        for art_type in ARTIFACT_META:
            last = _get_last_generated(state, nb_key, art_type)
            if last is None:
                age_str = "never"
                fresh = False
            else:
                age_h = (now - last).total_seconds() / 3600
                age_str = f"{age_h:.1f}h ago"
                min_h = MIN_REGEN_INTERVAL.get(art_type, 7 * 24)
                fresh = age_h < min_h
            report[nb_key]["artifacts"][art_type] = {
                "last_generated": last.isoformat() if last else None,
                "age": age_str,
                "fresh": fresh,
            }

    return report


def print_status() -> None:
    """Print human-readable status table."""
    status = get_status()
    today = datetime.now(WITA)
    scheduled = get_todays_tasks(today)
    print(f"\nMultimodal Pipeline Status — {today.strftime('%A %Y-%m-%d %H:%M WITA')}")
    print(f"Today's schedule: {scheduled or '(none)'}\n")

    for nb_key, nb_data in status.items():
        print(f"  {nb_key} — {nb_data['label']}")
        for art_type, art_data in nb_data["artifacts"].items():
            icon = "✅" if art_data["fresh"] else "🔴"
            print(f"    {icon} {art_type:12s}  {art_data['age']}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ARCH-6: Multi-Modal Content Factory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--run", action="store_true", help="Run today's scheduled tasks")
    p.add_argument("--force", action="store_true", help="Force regeneration (ignore staleness)")
    p.add_argument("--dry-run", action="store_true", help="Simulate without CLI calls")
    p.add_argument("--status", action="store_true", help="Show status of all artifacts")
    p.add_argument(
        "--task", metavar="NB:TYPE",
        help="Run specific task (e.g. nb2:audio). Can repeat.",
        action="append", dest="tasks",
    )
    p.add_argument("--all-notebooks", action="store_true", help="Generate audio for all notebooks")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = _build_parser().parse_args(argv)

    if args.status:
        print_status()
        return 0

    # Build task list
    tasks: Optional[list[tuple[str, str]]] = None

    if args.tasks:
        tasks = []
        for t in args.tasks:
            parts = t.split(":")
            if len(parts) != 2:
                logger.error("Invalid task format '%s' — use NB_KEY:ARTIFACT_TYPE", t)
                return 1
            nb_key, art_type = parts
            if nb_key not in NOTEBOOKS:
                logger.error("Unknown notebook key: %s", nb_key)
                return 1
            if art_type not in ARTIFACT_META:
                logger.error("Unknown artifact type: %s (valid: %s)", art_type, list(ARTIFACT_META))
                return 1
            tasks.append((nb_key, art_type))

    elif args.all_notebooks:
        tasks = [(nb_key, "audio") for nb_key in NOTEBOOKS]

    elif args.run:
        tasks = None  # use today's schedule

    else:
        _build_parser().print_help()
        return 0

    results = run_pipeline(tasks=tasks, force=args.force, dry_run=args.dry_run)

    ok = sum(1 for r in results if r.status == "ok")
    errors = sum(1 for r in results if r.status == "error")
    dry = sum(1 for r in results if r.status == "dry_run")
    skipped = sum(1 for r in results if r.status == "skipped")

    print(f"\nDone: {ok} ok, {dry} dry_run, {skipped} skipped, {errors} errors")
    if errors:
        for r in results:
            if r.status == "error":
                print(f"  ❌ {r.notebook_key}/{r.artifact_type}: {r.message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
