"""Pipeline Heartbeat Monitor — ARCH-9.

Centralized heartbeat tracking for all NLM pipelines.
Detects silent failures (auth expiry, OOM, timeouts) by monitoring
time since last successful run of each pipeline.

Classifies pipeline health as:
    OK       — within max_age
    WARNING  — 1x missed window
    CRITICAL — 2x missed window
    DEAD     — 3x missed window
    NEVER_RAN — no state file found

Usage:
    # Record a pipeline success
    python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --record nb2_pipeline

    # Check all pipelines and alert on failures
    python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --check

    # Send daily digest
    python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --digest

    # Dry run (print instead of Telegram)
    python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --check --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WITA = timezone(timedelta(hours=8))

REGISTRY_FILE = Path(__file__).resolve().parent / "pipeline_heartbeat_registry.json"

STATE_DIR = Path.home() / ".agent" / "decisions" / "state"

TELEGRAM_API_BASE = "https://api.telegram.org"

# Status classifications
STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_CRITICAL = "CRITICAL"
STATUS_DEAD = "DEAD"
STATUS_NEVER_RAN = "NEVER_RAN"

# Status emoji mapping
STATUS_EMOJI: dict[str, str] = {
    STATUS_OK: "\u2705",         # check mark
    STATUS_WARNING: "\u26a0\ufe0f",  # warning
    STATUS_CRITICAL: "\U0001f534",   # red circle
    STATUS_DEAD: "\U0001f480",       # skull
    STATUS_NEVER_RAN: "\u2753",      # question mark
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def load_registry(registry_path: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    """Load the pipeline heartbeat registry from JSON.

    Args:
        registry_path: Override path to registry JSON.

    Returns:
        Dict mapping pipeline_name -> config dict with schedule, max_age_hours.
    """
    path = registry_path or REGISTRY_FILE
    if not path.exists():
        logger.error("Registry file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Record Success
# ---------------------------------------------------------------------------


def record_success(
    pipeline_name: str,
    duration_seconds: Optional[float] = None,
    state_dir: Optional[Path] = None,
) -> None:
    """Write a success timestamp for a pipeline.

    Uses atomic write (tempfile + rename) for safe concurrent access.

    Args:
        pipeline_name: Pipeline identifier (must match registry key).
        duration_seconds: How long the pipeline run took.
        state_dir: Override state directory for testing.
    """
    sdir = state_dir or STATE_DIR
    sdir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=WITA)
    payload = {
        "pipeline": pipeline_name,
        "last_success": now.isoformat(),
        "duration_seconds": round(duration_seconds, 1) if duration_seconds is not None else None,
    }

    target = sdir / f"heartbeat_{pipeline_name}.json"

    # Atomic write: write to temp file in the same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(sdir),
        prefix=f".heartbeat_{pipeline_name}_",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.rename(tmp_path, str(target))
        logger.info("Heartbeat recorded for %s at %s", pipeline_name, now.isoformat())
    except OSError:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Read State
# ---------------------------------------------------------------------------


def _read_heartbeat_state(
    pipeline_name: str,
    state_dir: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Read the heartbeat state file for a pipeline.

    Args:
        pipeline_name: Pipeline identifier.
        state_dir: Override state directory.

    Returns:
        Parsed JSON dict or None if file missing/corrupt.
    """
    sdir = state_dir or STATE_DIR
    target = sdir / f"heartbeat_{pipeline_name}.json"
    if not target.exists():
        return None
    try:
        with open(target, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read heartbeat state for %s: %s", pipeline_name, exc)
        return None


# ---------------------------------------------------------------------------
# Check All Heartbeats
# ---------------------------------------------------------------------------


def _classify_staleness(
    age_hours: float,
    max_age_hours: float,
) -> str:
    """Classify pipeline health based on staleness.

    Args:
        age_hours: Hours since last successful run.
        max_age_hours: Configured max age before WARNING.

    Returns:
        One of STATUS_OK, STATUS_WARNING, STATUS_CRITICAL, STATUS_DEAD.
    """
    if age_hours <= max_age_hours:
        return STATUS_OK
    ratio = age_hours / max_age_hours
    if ratio <= 2.0:
        return STATUS_WARNING
    if ratio <= 3.0:
        return STATUS_CRITICAL
    return STATUS_DEAD


def check_all_heartbeats(
    registry_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Check all pipeline heartbeats against registry config.

    Args:
        registry_path: Override registry JSON path.
        state_dir: Override state directory.

    Returns:
        List of status dicts, one per pipeline, with keys:
            pipeline, status, last_success, age_hours, max_age_hours,
            duration_seconds, schedule
    """
    registry = load_registry(registry_path)
    if not registry:
        logger.error("Empty registry — nothing to check")
        return []

    now = datetime.now(tz=WITA)
    statuses: list[dict[str, Any]] = []

    for pipeline_name, config in registry.items():
        max_age_hours = config.get("max_age_hours", 26)
        schedule = config.get("schedule", "unknown")

        state = _read_heartbeat_state(pipeline_name, state_dir)

        if state is None:
            statuses.append({
                "pipeline": pipeline_name,
                "status": STATUS_NEVER_RAN,
                "last_success": None,
                "age_hours": None,
                "max_age_hours": max_age_hours,
                "duration_seconds": None,
                "schedule": schedule,
            })
            continue

        last_success_str = state.get("last_success")
        if not last_success_str:
            statuses.append({
                "pipeline": pipeline_name,
                "status": STATUS_NEVER_RAN,
                "last_success": None,
                "age_hours": None,
                "max_age_hours": max_age_hours,
                "duration_seconds": None,
                "schedule": schedule,
            })
            continue

        try:
            last_success = datetime.fromisoformat(last_success_str)
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp for %s: %s", pipeline_name, last_success_str)
            statuses.append({
                "pipeline": pipeline_name,
                "status": STATUS_NEVER_RAN,
                "last_success": last_success_str,
                "age_hours": None,
                "max_age_hours": max_age_hours,
                "duration_seconds": None,
                "schedule": schedule,
            })
            continue

        # Ensure timezone-aware comparison
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=WITA)

        age = now - last_success
        age_hours = age.total_seconds() / 3600

        status = _classify_staleness(age_hours, max_age_hours)

        statuses.append({
            "pipeline": pipeline_name,
            "status": status,
            "last_success": last_success.isoformat(),
            "age_hours": round(age_hours, 1),
            "max_age_hours": max_age_hours,
            "duration_seconds": state.get("duration_seconds"),
            "schedule": schedule,
        })

    return statuses


# ---------------------------------------------------------------------------
# Memory Pressure
# ---------------------------------------------------------------------------


def check_memory_pressure() -> dict[str, Any]:
    """Check macOS memory pressure via vm_stat and sysctl.

    Returns:
        Dict with swap_used_mb, pressure (ok/warning/critical).
    """
    swap_used_mb = 0.0

    try:
        # Use sysctl for swap info on macOS
        result = subprocess.run(
            ["sysctl", "vm.swapusage"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Output: "vm.swapusage: total = 2048.00M  used = 123.45M  free = 1924.55M"
            line = result.stdout.strip()
            for part in line.split():
                if part.endswith("M") and "used" in line[:line.index(part)]:
                    # Find the "used = X.XXM" value
                    pass
            # More robust parsing
            parts = line.split("used =")
            if len(parts) >= 2:
                used_str = parts[1].strip().split()[0]
                used_str = used_str.rstrip("M").rstrip("m")
                swap_used_mb = float(used_str)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError) as exc:
        logger.warning("Failed to check swap usage: %s", exc)

    # Also try vm_stat for additional context
    try:
        result = subprocess.run(
            ["vm_stat"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse "Swapins" and "Swapouts" from vm_stat output
            for line in result.stdout.splitlines():
                if "Swapins" in line or "Swapouts" in line:
                    logger.debug("vm_stat: %s", line.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.debug("vm_stat not available: %s", exc)

    # Classify pressure
    if swap_used_mb > 1024:
        pressure = "critical"
    elif swap_used_mb > 512:
        pressure = "warning"
    else:
        pressure = "ok"

    return {
        "swap_used_mb": round(swap_used_mb, 1),
        "pressure": pressure,
    }


# ---------------------------------------------------------------------------
# Telegram Alerts
# ---------------------------------------------------------------------------


def _send_telegram(text: str, dry_run: bool = False) -> bool:
    """Send a message via Telegram Bot API.

    Args:
        text: Message text (supports HTML — <b>, <i>, <code>).
        dry_run: If True, print instead of sending.

    Returns:
        True if sent successfully.
    """
    if dry_run:
        print(f"[DRY RUN] Telegram message:\n{text}")
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set — cannot send alert")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    # Renaissance follow-up #2 (2026-04-30): switched parse_mode from
    # "Markdown" (legacy v1) to "HTML" because pipeline names contain
    # underscores ("nb1_daily_refresh", "t4_monitor") which Markdown v1
    # interprets as italic delimiters. Unbalanced underscores → HTTP 400.
    # gap_scanner.py uses HTML and works reliably; we copy that pattern.
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                logger.info("Telegram alert sent successfully")
                return True
            logger.warning("Telegram API returned status %d", resp.status)
            return False
    except urllib.error.URLError as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return False


def _format_last_run(last_success: Optional[str]) -> str:
    """Format the last success time for display.

    Args:
        last_success: ISO 8601 timestamp or None.

    Returns:
        Human-readable relative time string.
    """
    if not last_success:
        return "never"
    try:
        dt = datetime.fromisoformat(last_success)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WITA)
        age = datetime.now(tz=WITA) - dt
        hours = age.total_seconds() / 3600
        if hours < 1:
            return f"{int(age.total_seconds() / 60)}m ago"
        if hours < 24:
            return f"{hours:.1f}h ago"
        days = hours / 24
        return f"{days:.1f}d ago"
    except (ValueError, TypeError):
        return "invalid"


def send_alert(statuses: list[dict[str, Any]], dry_run: bool = False) -> None:
    """Send Telegram alert if any pipelines are unhealthy.

    Only sends if there are WARNING, CRITICAL, DEAD, or NEVER_RAN statuses.

    Args:
        statuses: Output from check_all_heartbeats().
        dry_run: Print instead of sending.
    """
    alert_statuses = [
        s for s in statuses
        if s["status"] in (STATUS_WARNING, STATUS_CRITICAL, STATUS_DEAD, STATUS_NEVER_RAN)
    ]

    if not alert_statuses:
        logger.info("All pipelines healthy — no alert needed")
        return

    lines = ["\U0001f6a8 <b>NLM Pipeline Alert</b>", ""]

    for s in alert_statuses:
        emoji = STATUS_EMOJI.get(s["status"], "?")
        last_run = _format_last_run(s.get("last_success"))
        lines.append(f"{emoji} <code>{s['pipeline']}</code> — {s['status']} ({last_run})")

    ok_count = sum(1 for s in statuses if s["status"] == STATUS_OK)
    total = len(statuses)
    lines.append("")
    lines.append(f"Healthy: {ok_count}/{total}")

    _send_telegram("\n".join(lines), dry_run=dry_run)


def send_daily_digest(
    statuses: list[dict[str, Any]],
    memory: Optional[dict[str, Any]] = None,
    dry_run: bool = False,
) -> None:
    """Send a full daily digest of all pipeline statuses.

    Args:
        statuses: Output from check_all_heartbeats().
        memory: Output from check_memory_pressure(). Auto-fetched if None.
        dry_run: Print instead of sending.
    """
    if memory is None:
        memory = check_memory_pressure()

    lines = ["\U0001f3e5 <b>NLM Pipeline Health \u2014 Daily Digest</b>", ""]

    for s in statuses:
        emoji = STATUS_EMOJI.get(s["status"], "?")
        last_run = _format_last_run(s.get("last_success"))
        duration = ""
        if s.get("duration_seconds") is not None:
            duration = f" ({s['duration_seconds']}s)"
        lines.append(f"{emoji} <code>{s['pipeline']}</code> \u2014 {last_run}{duration}")

    # Summary counts
    ok_count = sum(1 for s in statuses if s["status"] == STATUS_OK)
    warn_count = sum(1 for s in statuses if s["status"] == STATUS_WARNING)
    crit_count = sum(1 for s in statuses if s["status"] == STATUS_CRITICAL)
    dead_count = sum(1 for s in statuses if s["status"] == STATUS_DEAD)
    never_count = sum(1 for s in statuses if s["status"] == STATUS_NEVER_RAN)

    lines.append("")
    parts = [f"\u2705 {ok_count}"]
    if warn_count:
        parts.append(f"\u26a0\ufe0f {warn_count}")
    if crit_count:
        parts.append(f"\U0001f534 {crit_count}")
    if dead_count:
        parts.append(f"\U0001f480 {dead_count}")
    if never_count:
        parts.append(f"\u2753 {never_count}")
    lines.append("Summary: " + " | ".join(parts))

    # Memory pressure
    lines.append("")
    swap_mb = memory.get("swap_used_mb", 0)
    pressure = memory.get("pressure", "ok")
    pressure_emoji = {
        "ok": "\u2705",
        "warning": "\u26a0\ufe0f",
        "critical": "\U0001f534",
    }.get(pressure, "?")
    lines.append(f"{pressure_emoji} Swap: {swap_mb:.0f}MB ({pressure})")

    _send_telegram("\n".join(lines), dry_run=dry_run)


# ---------------------------------------------------------------------------
# Truth dashboard — cross 3 signals (S0.5 2026-04-25)
# ---------------------------------------------------------------------------


def truth_dashboard(
    registry: Optional[dict[str, dict[str, Any]]] = None,
    state_dir: Optional[Path] = None,
    logs_dir: Optional[Path] = None,
    today: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Cross 3 independent signals per pipeline to detect silent failures.

    Designed to catch the "self-repair cieco" pattern (2026-04-19 lesson)
    where ``mtime`` of gateway-written ``.last.json`` is fresh but the
    internal ``ts`` is stale. Reports each signal independently so that
    disagreement between them flags a compromised pipeline.

    Three signals per pipeline:

    1. **arch9**: ``heartbeat_{name}.json`` written by ``record_success()``.
       Ground truth — only set when the pipeline actually completed.
    2. **log**: today's log file ``logs/{name}_YYYYMMDD.log`` size > 0.
       Proves ``run_nbN_pipeline.sh`` actually invoked Python.
    3. **gateway**: what ``nlm_{name}.last.json`` (openclaw-gateway
       projection) claims. May be stale; shown for contrast.

    Args:
        registry: Pipeline registry (defaults to on-disk).
        state_dir: Override for ``~/.agent/decisions/state/``.
        logs_dir: Override for ``apps/evaluator/nlm_deep_research/logs/``.
        today: Override "today" for testing (defaults to WITA now).

    Returns:
        List of dicts with keys: ``pipeline``, ``arch9`` (dict), ``log``
        (dict), ``gateway`` (dict), ``verdict`` (str).
    """
    reg = registry if registry is not None else load_registry()
    sdir = state_dir or STATE_DIR
    ldir = logs_dir or (
        Path(__file__).resolve().parent / "logs"
    )
    now = today or datetime.now(tz=WITA)
    today_stamp = now.strftime("%Y%m%d")

    rows: list[dict[str, Any]] = []
    for pipeline_name in reg:
        # Signal 1: ARCH-9 heartbeat
        hb = _read_heartbeat_state(pipeline_name, sdir)
        arch9_present = hb is not None
        arch9_age_h: Optional[float] = None
        if arch9_present:
            last_success = hb.get("last_success")  # type: ignore[union-attr]
            if last_success:
                try:
                    ts = datetime.fromisoformat(last_success)
                    arch9_age_h = round((now - ts).total_seconds() / 3600, 1)
                except (ValueError, TypeError):
                    arch9_age_h = None

        # Signal 2: today's log file exists + non-empty
        log_candidates = list(ldir.glob(f"{pipeline_name}_{today_stamp}.log"))
        # Fallback: short name variants (nb2_pipeline → nb2 prefix)
        if not log_candidates:
            short = pipeline_name.split("_")[0]  # nb2_pipeline → nb2
            log_candidates = list(ldir.glob(f"{short}_*_{today_stamp}.log"))
            if not log_candidates:
                log_candidates = list(ldir.glob(f"{short}_{today_stamp}.log"))
        log_exists = bool(log_candidates)
        log_size = log_candidates[0].stat().st_size if log_exists else 0

        # Signal 3: gateway .last.json projection.
        # Gateway naming convention differs: ARCH-9 uses {name}_pipeline,
        # gateway uses nlm_{nbN}_{domain_suffix} (e.g. nlm_nb3_company_setup).
        # Match by {nbN} prefix when the exact name is missing.
        gateway_file = sdir / f"nlm_{pipeline_name}.last.json"
        if not gateway_file.exists():
            # Try stripping _pipeline suffix
            alt = sdir / f"nlm_{pipeline_name.replace('_pipeline', '')}.last.json"
            if alt.exists():
                gateway_file = alt
            else:
                # Fuzzy match by nbN prefix (nb3_pipeline → nlm_nb3_*)
                short = pipeline_name.split("_")[0]  # nb3_pipeline → nb3
                if short.startswith("nb"):
                    candidates = sorted(sdir.glob(f"nlm_{short}_*.last.json"))
                    if candidates:
                        gateway_file = candidates[0]
        gateway_data: Optional[dict] = None
        gateway_age_h: Optional[float] = None
        if gateway_file.exists():
            try:
                gateway_data = json.loads(gateway_file.read_text())
                gateway_ts = gateway_data.get("ts")
                if isinstance(gateway_ts, (int, float)) and gateway_ts > 0:
                    gateway_age_h = round(
                        (now.timestamp() - gateway_ts) / 3600, 1
                    )
            except (OSError, json.JSONDecodeError):
                pass

        # Verdict: combine the 3 signals.
        # - all green (arch9 fresh + log today + gateway fresh): OK
        # - arch9 fresh but gateway stale: gateway projection lies, real state OK
        # - log today but arch9 missing: script ran but didn't record success → incomplete
        # - nothing today: pipeline dead
        max_age = reg[pipeline_name].get("max_age_hours", 24)
        arch9_fresh = arch9_age_h is not None and arch9_age_h <= max_age
        gateway_fresh = gateway_age_h is not None and gateway_age_h <= max_age

        if arch9_fresh and log_exists:
            verdict = "OK"
        elif arch9_fresh and not log_exists:
            verdict = "HEARTBEAT_ONLY"  # heartbeat recorded but no log today (maybe just resumed)
        elif log_exists and not arch9_fresh:
            verdict = "LOG_NO_HEARTBEAT"  # script running but not completing successfully
        elif gateway_fresh and not arch9_fresh and not log_exists:
            verdict = "GATEWAY_LIES"  # classic self-repair-blind pattern
        elif not arch9_present and not log_exists:
            verdict = "DEAD"
        else:
            verdict = "DEGRADED"

        rows.append({
            "pipeline": pipeline_name,
            "arch9": {
                "present": arch9_present,
                "age_h": arch9_age_h,
                "fresh": arch9_fresh,
            },
            "log": {
                "exists_today": log_exists,
                "size_bytes": log_size,
            },
            "gateway": {
                "present": gateway_data is not None,
                "age_h": gateway_age_h,
                "fresh": gateway_fresh,
                "status": (gateway_data or {}).get("status"),
            },
            "max_age_hours": max_age,
            "verdict": verdict,
        })

    return rows


def print_truth_dashboard(rows: list[dict[str, Any]]) -> None:
    """Pretty-print truth_dashboard output as a 1-comando 9-row table."""
    verdict_emoji = {
        "OK": "✅",
        "HEARTBEAT_ONLY": "ℹ️",
        "LOG_NO_HEARTBEAT": "⚠️",
        "GATEWAY_LIES": "\U0001f534",
        "DEGRADED": "\U0001f7e1",
        "DEAD": "\U0001f480",
    }
    # Header
    print(f"{'pipeline':<30} {'arch9':<10} {'log_today':<12} {'gateway':<10} {'verdict'}")
    print("-" * 80)
    for r in rows:
        a = r["arch9"]
        arch9_str = f"{a['age_h']}h" if a["age_h"] is not None else "-"
        log_str = f"{r['log']['size_bytes']}B" if r["log"]["exists_today"] else "✗"
        g = r["gateway"]
        gw_str = f"{g['age_h']}h" if g["age_h"] is not None else "-"
        emoji = verdict_emoji.get(r["verdict"], "?")
        print(
            f"{r['pipeline']:<30} {arch9_str:<10} {log_str:<12} "
            f"{gw_str:<10} {emoji} {r['verdict']}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for heartbeat monitor."""
    parser = argparse.ArgumentParser(
        description="NLM Pipeline Heartbeat Monitor (ARCH-9)",
    )
    parser.add_argument(
        "--record",
        metavar="PIPELINE",
        help="Record a success for the given pipeline name",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duration in seconds (used with --record)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check all pipelines and alert if needed",
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Send daily digest of all pipeline statuses",
    )
    parser.add_argument(
        "--truth",
        action="store_true",
        help="Cross-check 3 signals (ARCH-9 heartbeat, today's log, gateway projection) to detect silent failures",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print instead of sending Telegram messages",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not any([args.record, args.check, args.digest, args.truth]):
        parser.print_help()
        sys.exit(1)

    if args.record:
        record_success(args.record, duration_seconds=args.duration)
        logger.info("Recorded heartbeat for %s", args.record)

    if args.check:
        statuses = check_all_heartbeats()
        send_alert(statuses, dry_run=args.dry_run)
        # Print summary to stdout
        for s in statuses:
            emoji = STATUS_EMOJI.get(s["status"], "?")
            print(f"{emoji} {s['pipeline']}: {s['status']} (age={s.get('age_hours', '?')}h)")

    if args.digest:
        statuses = check_all_heartbeats()
        send_daily_digest(statuses, dry_run=args.dry_run)

    if args.truth:
        rows = truth_dashboard()
        print_truth_dashboard(rows)


if __name__ == "__main__":
    main()
