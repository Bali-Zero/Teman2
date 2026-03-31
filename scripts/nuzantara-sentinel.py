#!/usr/bin/env python3
"""
Nuzantara Sentinel — 4-tier self-healing automation monitor.
Runs every 5 minutes via launchd. Monitors Pro + Air.

Tier 0: Gateway health (openclaw restart before iterating jobs)
Tier 1: Retry with backoff (TRANSIENT failures)
Tier 2: Aider auto-fix (DETERMINISTIC with high-confidence fix pattern)
Tier 3: DLQ + Claude Code alert (DETERMINISTIC low-confidence or aider failed)
Tier 4: Zero alert (UNKNOWN failures)
"""
import glob
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add sentinel_lib to path
sys.path.insert(0, str(Path(__file__).parent))
from sentinel_lib.classifier import classify, classify_with_llm
from sentinel_lib.circuit_breaker import get_state, record_success, record_failure
from sentinel_lib.alerter import send_alert, send_daily_report, check_escalation_cooldown, mark_escalation_sent
from sentinel_lib.repairer import (
    retry_job, dispatch_aider_fix, verify_fix, add_to_dlq, clear_dlq_entry,
    trigger_openclaw_job, is_openclaw_running, restart_openclaw,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/logs/sentinel.log")),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

STATE_DIR = os.path.expanduser("~/.agent/decisions/state")
REGISTRY_FILE = os.path.expanduser("~/.agent/decisions/job_registry.json")
HEARTBEAT_FILE = os.path.expanduser("~/.pro_heartbeat")
SENTINEL_LOG = os.path.expanduser("~/logs/sentinel.jsonl")
OPENCLAW_RESTART_RECORD = os.path.expanduser("~/.agent/decisions/openclaw_last_restart.json")
PRO_HOST = "Nuzantara"
DEAD_MAN_THRESHOLD_S = 7200  # 2 hours

MAX_RETRIES = 3
BACKOFF_BASE_S = 60
BACKOFF_CAP_S = 600
OPENCLAW_RESTART_COOLDOWN_S = 600  # 10 minutes between restarts
FORCED_HALFOPEN_AGE_S = 7200      # 2 hours — force HALF_OPEN on stuck-OPEN circuits


def _force_halfopen_stale_circuits() -> None:
    """
    Force HALF_OPEN on any circuit that has been OPEN for > FORCED_HALFOPEN_AGE_S.
    Called inside run_sentinel() only — single writer, no race condition with DLQ autopilot.
    Imports _atomic_save from circuit_breaker to use the safe write path (Task 1).
    """
    from sentinel_lib.circuit_breaker import _load, _atomic_save
    data = _load()
    forced = []
    for job, cb in data.items():
        if cb.get("state") != "OPEN":
            continue
        age = time.time() - cb.get("opened_at", 0)
        if age > FORCED_HALFOPEN_AGE_S:
            data[job]["state"] = "HALF_OPEN"
            forced.append(job)
    if forced:
        _atomic_save(data)
        logger.info(f"Forced HALF_OPEN on {len(forced)} stale circuits: {forced}")


REGISTRY_HALT_FILE = os.path.expanduser("~/.agent/decisions/REGISTRY_HALT")
REGISTRY_OVERRIDE_FILE = os.path.expanduser("~/.agent/decisions/REGISTRY_OVERRIDE")
HEALING_DISABLED_FILE = os.path.expanduser("~/.agent/decisions/HEALING_DISABLED")


def _registry_checksum(data: dict) -> str:
    import hashlib
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_registry() -> dict:
    # D0.4: HALT gate — if REGISTRY_HALT exists (and no REGISTRY_OVERRIDE), abort run
    if os.path.exists(REGISTRY_HALT_FILE) and not os.path.exists(REGISTRY_OVERRIDE_FILE):
        msg = open(REGISTRY_HALT_FILE).read().strip()
        logger.error(f"REGISTRY_HALT active — aborting sentinel: {msg}")
        send_alert(f"🚨 Sentinel HALTED: registry checksum mismatch.\n{msg}\nResolve and touch REGISTRY_OVERRIDE to resume.")
        sys.exit(1)

    try:
        raw = open(REGISTRY_FILE).read()
        data = json.loads(raw)
    except FileNotFoundError:
        logger.warning("Registry not found")
        return {}
    except json.JSONDecodeError as exc:
        # Corrupt registry — write HALT file and abort
        halt_msg = f"JSON decode error in {REGISTRY_FILE}: {exc}"
        open(REGISTRY_HALT_FILE, "w").write(halt_msg)
        logger.error(f"Registry corrupt → HALT: {halt_msg}")
        send_alert(f"🚨 Sentinel HALTED: corrupt registry.\n{halt_msg}")
        sys.exit(1)

    jobs = data.get("jobs", {})

    # Verify checksum if present
    stored_checksum = data.get("checksum")
    if stored_checksum:
        actual = _registry_checksum(jobs)
        if actual != stored_checksum:
            halt_msg = f"Checksum mismatch: stored={stored_checksum[:16]}… actual={actual[:16]}…"
            open(REGISTRY_HALT_FILE, "w").write(halt_msg)
            logger.error(f"Registry checksum mismatch → HALT: {halt_msg}")
            send_alert(f"🚨 Sentinel HALTED: {halt_msg}\nTouch REGISTRY_OVERRIDE to resume.")
            sys.exit(1)

    # Clear stale HALT + OVERRIDE if we got here cleanly
    for f in (REGISTRY_HALT_FILE, REGISTRY_OVERRIDE_FILE):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass

    return jobs


def _collect_openclaw_states(registry: dict) -> dict:
    """
    Bridge OpenClaw cron jobs into the Sentinel state format.
    Reads ~/.openclaw/cron/jobs.json and maps lastRunAtMs + consecutiveErrors
    into the {ts, status, last_error} shape that process_job() expects.
    Only synthesises state for jobs in the registry with type=openclaw.
    """
    oc_path = Path.home() / ".openclaw" / "cron" / "jobs.json"
    try:
        oc_data = json.loads(oc_path.read_text())
        oc_jobs = oc_data.get("jobs", [])
    except Exception:
        return {}

    # Build lookup by OpenClaw job id AND by name (dashes)
    oc_by_id: dict = {}
    oc_by_name: dict = {}
    for oj in oc_jobs:
        if oj.get("id"):
            oc_by_id[oj["id"]] = oj
        if oj.get("name"):
            oc_by_name[oj["name"]] = oj

    states = {}
    for job_id, reg in registry.items():
        if reg.get("type") != "openclaw":
            continue

        # Find the matching OpenClaw job
        oc_id = reg.get("openclaw_id", "")
        oj = oc_by_id.get(oc_id)
        if not oj:
            # Fallback: match by name (registry uses underscores, OpenClaw uses dashes)
            oj = oc_by_name.get(job_id.replace("_", "-"))
        if not oj:
            continue

        state = oj.get("state", {})
        last_run_ms = state.get("lastRunAtMs", 0) or 0
        last_run_ts = last_run_ms / 1000  # convert to seconds
        consecutive_errors = state.get("consecutiveErrors", 0)
        last_status = state.get("lastRunStatus") or state.get("lastStatus") or "unknown"

        # Map to Sentinel state format
        if consecutive_errors >= 1:
            sentinel_status = "failed"
            error_msg = f"OpenClaw consecutiveErrors={consecutive_errors}, lastStatus={last_status}"
        elif last_run_ts == 0:
            # Never run — treat as unknown; staleness check will catch it if overdue
            sentinel_status = "unknown"
            error_msg = ""
        else:
            sentinel_status = "ok" if last_status == "ok" else "failed"
            error_msg = f"OpenClaw lastStatus={last_status}" if last_status != "ok" else ""

        states[job_id] = {
            "job": job_id,
            "ts": last_run_ts,
            "status": sentinel_status,
            "last_error": error_msg,
            "retry_attempt": 0,
            "_source": "openclaw_bridge",
        }

    return states


def collect_state_files(registry: Optional[dict] = None) -> dict:
    """Read local + Pro state files + OpenClaw bridge. Returns {job_id: state_dict}."""
    if registry is None:
        registry = load_registry()
    states = {}

    # OpenClaw bridge — synthesise state from ~/.openclaw/cron/jobs.json
    states.update(_collect_openclaw_states(registry))

    # Local state files (override bridge if a .last.json exists)
    for path in glob.glob(os.path.join(STATE_DIR, "*.last.json")):
        try:
            job_id = os.path.basename(path).replace(".last.json", "")
            states[job_id] = json.loads(open(path).read())
        except Exception:
            pass

    # Pro state files via SSH (skip if we are Pro)
    import socket
    if socket.gethostname() != PRO_HOST:
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                 PRO_HOST, f"cat {STATE_DIR}/*.last.json 2>/dev/null || echo '{{}}'"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                # Output is concatenated JSONs — parse each
                for chunk in result.stdout.strip().split("\n"):
                    chunk = chunk.strip()
                    if chunk and chunk != "{}":
                        try:
                            s = json.loads(chunk)
                            job_id = s.get("job")
                            if job_id:
                                states[job_id] = s
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            send_alert(f"Pro unreachable via SSH: {e}", level="CRITICAL")

    return states


def check_dead_man_switch() -> None:
    """Alert if Pro hasn't sent a heartbeat in >2 hours."""
    import socket
    if socket.gethostname() == PRO_HOST:
        return  # We ARE Pro, skip

    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        age = time.time() - mtime
        if age > DEAD_MAN_THRESHOLD_S:
            send_alert(
                f"Pro machine heartbeat STALE — last seen {age/3600:.1f}h ago. Manual check required.",
                level="DEADMAN"
            )
    except FileNotFoundError:
        send_alert("Pro heartbeat file missing — Pro never connected?", level="WARNING")


def exponential_backoff(attempt: int) -> float:
    """Full jitter backoff: random(0, min(cap, base * 2^attempt))."""
    import random
    return random.uniform(0, min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** attempt)))


# ─── Tier 0: OpenClaw gateway health ─────────────────────────────────────────

def _openclaw_restart_on_cooldown() -> bool:
    """Return True if a restart was already attempted within cooldown window."""
    try:
        data = json.loads(open(OPENCLAW_RESTART_RECORD).read())
        last_restart = data.get("ts", 0)
        return (time.time() - last_restart) < OPENCLAW_RESTART_COOLDOWN_S
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return False


def _record_openclaw_restart() -> None:
    """Persist the timestamp of the most recent restart attempt."""
    os.makedirs(os.path.dirname(OPENCLAW_RESTART_RECORD), exist_ok=True)
    with open(OPENCLAW_RESTART_RECORD, "w") as f:
        json.dump({"ts": time.time()}, f)


def check_and_repair_openclaw() -> bool:
    """
    Tier 0: verify OpenClaw gateway is alive before iterating jobs.

    Returns True if gateway is healthy (or not applicable).
    Returns False if gateway is down AND restart failed — callers should
    suppress per-job openclaw escalations to avoid flooding DLQ.

    Uses a cooldown guard to prevent restart flapping every 5 minutes.
    """
    if is_openclaw_running():
        return True  # Gateway is healthy, nothing to do

    logger.warning("Tier 0: OpenClaw gateway is DOWN")

    if _openclaw_restart_on_cooldown():
        logger.info("Tier 0: restart on cooldown, skipping")
        send_alert(
            "OpenClaw gateway DOWN (cooldown active — restart was attempted recently). "
            "All OpenClaw jobs suppressed until gateway recovers.",
            level="WARNING"
        )
        return False

    logger.info("Tier 0: attempting OpenClaw gateway restart")
    _record_openclaw_restart()
    ok, output = restart_openclaw()

    if ok:
        logger.info(f"Tier 0: OpenClaw gateway restarted OK — {output[:80]}")
        send_alert(f"OpenClaw gateway auto-restarted ✅\n{output[:120]}", level="INFO")
        return True

    logger.error(f"Tier 0: OpenClaw gateway restart FAILED — {output[:120]}")
    send_alert(
        f"🚨 OpenClaw gateway DOWN and restart FAILED\n{output[:200]}\n\n"
        f"All OpenClaw jobs are paused. Manual intervention required.",
        level="CRITICAL"
    )
    return False


# ─── Dedicated OpenClaw job handler ──────────────────────────────────────────

def _process_openclaw_job(
    job_id: str,
    openclaw_id: str,
    state: dict,
    reg: dict,
    classification: dict,
    last_error: str,
    retry_attempt: int,
) -> dict:
    """
    Tier 1 handler for type=openclaw jobs.
    Retries via `openclaw cron run <id>` with ambiguous-timeout detection.
    """
    failure_type = classification["type"]
    fix_pattern = classification.get("fix_pattern")

    if failure_type == "TRANSIENT" and retry_attempt < MAX_RETRIES:
        backoff = exponential_backoff(retry_attempt)
        logger.info(f"{job_id}: Tier 1 openclaw retry (attempt {retry_attempt+1}), backoff {backoff:.0f}s")
        time.sleep(backoff)

        success, output = trigger_openclaw_job(openclaw_id)
        if success:
            record_success(job_id)
            return {"action": "retried_ok", "tier": 1, "success": True}

        # Ambiguous timeout: CLI disconnected but gateway may still be running
        if "gateway may still be running" in output:
            live_status = _read_openclaw_job_state(openclaw_id)
            if live_status in ("running", "ok"):
                logger.info(
                    f"{job_id}: trigger timed out but gateway shows status={live_status} — treating as in-progress"
                )
                return {"action": "running_ambiguous", "tier": 1, "success": None}

        logger.warning(f"{job_id}: openclaw trigger failed: {output[:120]}")
        return {"action": "retry_failed", "tier": 1, "success": False}

    if failure_type == "DETERMINISTIC" and fix_pattern and fix_pattern.get("confidence", 0) >= 0.85:
        # Tier 2: Aider fix
        files_implicated = _infer_files(job_id, last_error)
        test_cmd = reg.get("test_cmd")
        logger.info(f"{job_id}: Tier 2 aider-fix (confidence {fix_pattern['confidence']})")
        aider_ok, aider_out = dispatch_aider_fix(
            job=job_id,
            error_summary=last_error[:500],
            fix_instruction=fix_pattern["fix_instruction"],
            files_implicated=files_implicated,
            test_cmd=test_cmd,
        )
        if aider_ok and test_cmd:
            verified, _ = verify_fix(test_cmd, reg.get("host", "Nuzantara"))
            if verified:
                record_success(job_id)
                clear_dlq_entry(job_id)
                send_alert(f"✅ Auto-fixed `{job_id}`: {fix_pattern['fix_instruction'][:80]}", level="INFO")
                return {"action": "aider_fixed", "tier": 2, "success": True}

        # Aider failed — escalate to Tier 3
        add_to_dlq(job_id, last_error[:500], classification, last_error,
                   files_implicated, aider_attempts=1, aider_failure_reason=aider_out[:200])
        send_alert(
            f"Tier 3 needed — `{job_id}`\nError: {last_error[:100]}\n"
            f"Aider failed: {aider_out[:80]}\n\nCheck DLQ: `~/.agent/decisions/dlq.json`",
            level="CRITICAL"
        )
        return {"action": "escalated_tier3", "tier": 3, "success": False}

    # Tier 3/4: Unknown or low-confidence fix
    files_implicated = _infer_files(job_id, last_error)
    add_to_dlq(job_id, last_error[:500], classification, last_error, files_implicated)
    level = "CRITICAL" if failure_type == "DETERMINISTIC" else "WARNING"
    send_alert(
        f"{'Tier 3' if failure_type != 'UNKNOWN' else 'Tier 4'} needed — `{job_id}`\n"
        f"Type: {failure_type} / {classification.get('subtype')}\n"
        f"Error: {last_error[:120]}",
        level=level
    )
    return {"action": "escalated", "tier": 3, "success": False}


# ─── Main job processor ───────────────────────────────────────────────────────

def process_job(job_id: str, state: dict, registry: dict,
                openclaw_is_down: bool = False) -> dict:
    """
    Evaluate one job. Returns action taken: {action, tier, success}.

    openclaw_is_down: when True, skip all type=openclaw jobs to avoid flooding
    the DLQ with duplicate alerts when the gateway itself is the root cause.
    """
    now = time.time()
    circuit = get_state(job_id)
    reg = registry.get(job_id, {})

    # Circuit OPEN → skip
    if circuit == "OPEN":
        logger.info(f"{job_id}: circuit OPEN, skipping")
        return {"action": "skipped_circuit_open", "tier": 0, "success": None}

    status = state.get("status", "unknown")
    last_ts = state.get("ts", 0)
    last_error = state.get("last_error", "") or ""
    retry_attempt = state.get("retry_attempt", 0)

    # Staleness check
    threshold = reg.get("staleness_threshold_s", 93600)
    age = now - last_ts
    if status == "ok" and age > threshold:
        status = "stale"

    if status == "ok":
        record_success(job_id)
        return {"action": "healthy", "tier": 0, "success": True}

    if status == "running":
        # Job is currently running — don't interfere
        return {"action": "running", "tier": 0, "success": None}

    # Optional jobs (e.g. GUI apps) — log but don't escalate
    if reg.get("optional") and status in ("failed", "stale"):
        logger.info(f"{job_id}: optional job failed/stale — skipping escalation")
        return {"action": "skipped_optional", "tier": 0, "success": None}

    # --- FAILURE PATH ---
    logger.warning(f"{job_id}: status={status}, error={last_error[:80]}")

    # Suppress openclaw jobs when gateway is down — gateway is the root cause
    job_type = reg.get("type", "shell")
    if openclaw_is_down and job_type == "openclaw":
        logger.info(f"{job_id}: openclaw job suppressed (gateway down)")
        return {"action": "suppressed_gateway_down", "tier": 0, "success": None}

    # Classify failure
    classification = classify(last_error, retry_attempt)
    if classification["type"] == "UNKNOWN":
        classification = classify_with_llm(last_error, job_id)

    failure_type = classification["type"]
    fix_pattern = classification.get("fix_pattern")
    record_failure(job_id)

    # Dispatch to dedicated OpenClaw handler
    if job_type == "openclaw":
        openclaw_id = reg.get("openclaw_id")
        if not openclaw_id:
            logger.error(f"{job_id}: openclaw type but no openclaw_id in registry — escalating")
            add_to_dlq(job_id, "Missing openclaw_id in job_registry.json", classification,
                       last_error, ["~/.agent/decisions/job_registry.json"])
            send_alert(
                f"Config error — `{job_id}` is type=openclaw but has no openclaw_id\n"
                f"Fix: add openclaw_id to job_registry.json",
                level="CRITICAL"
            )
            return {"action": "config_error", "tier": 0, "success": False}
        return _process_openclaw_job(
            job_id, openclaw_id, state, reg, classification, last_error, retry_attempt
        )

    # ── Shell / LaunchAgent / Cron path — D1.1: mutually exclusive elif chain ──

    is_critical = reg.get("critical", False)
    is_idempotent = reg.get("is_idempotent", True)
    fail_count = state.get("fail_count", 1)
    files_implicated = _infer_files(job_id, last_error)
    restart_cmd = reg.get("restart_cmd")
    test_cmd = reg.get("test_cmd")
    host = reg.get("host", "Nuzantara")

    if failure_type == "TRANSIENT" and retry_attempt < MAX_RETRIES:
        # Tier 1: retry with backoff
        backoff = exponential_backoff(retry_attempt)
        logger.info(f"{job_id}: Tier 1 retry (attempt {retry_attempt+1}), backoff {backoff:.0f}s")
        time.sleep(backoff)
        if restart_cmd:
            success, _ = retry_job(restart_cmd, host)
            if success:
                record_success(job_id)
                return {"action": "retried_ok", "tier": 1, "success": True}
        return {"action": "retry_failed", "tier": 1, "success": False}

    elif (failure_type == "DETERMINISTIC"
          and fix_pattern and fix_pattern.get("confidence", 0) >= 0.85
          and not is_critical):
        # Tier 2: Aider auto-fix — only for non-critical jobs
        logger.info(f"{job_id}: Tier 2 aider-fix (confidence {fix_pattern['confidence']})")
        success, output = dispatch_aider_fix(
            job=job_id,
            error_summary=last_error[:500],
            fix_instruction=fix_pattern["fix_instruction"],
            files_implicated=files_implicated,
            test_cmd=test_cmd,
        )
        if success and test_cmd:
            verified, _ = verify_fix(test_cmd, host)
            if verified:
                record_success(job_id)
                clear_dlq_entry(job_id)
                send_alert(f"Auto-fixed {job_id}: {fix_pattern['fix_instruction'][:80]}", level="INFO")
                return {"action": "aider_fixed", "tier": 2, "success": True}
        # Aider failed → Tier 3
        add_to_dlq(job_id, last_error[:500], classification, last_error,
                   files_implicated, aider_attempts=1, aider_failure_reason=output[:200])
        send_alert(
            f"Tier 3 needed — {job_id}\nError: {last_error[:100]}\n"
            f"Aider failed: {output[:80]}\nCheck DLQ: ~/.agent/decisions/dlq.json",
            level="CRITICAL"
        )
        return {"action": "escalated_tier3", "tier": 3, "success": False}

    elif is_critical and not is_idempotent:
        # Tier 3: critical + non-idempotent → never auto-retry, alert immediately
        add_to_dlq(job_id, last_error[:500], classification, last_error, files_implicated)
        if not check_escalation_cooldown(job_id):
            send_alert(
                f"CRITICAL non-idempotent failure — {job_id}\n"
                f"Type: {failure_type}\nError: {last_error[:120]}\n"
                f"Manual intervention required (non-idempotent — auto-retry UNSAFE)",
                level="CRITICAL"
            )
            mark_escalation_sent(job_id)
        return {"action": "escalated_critical_non_idempotent", "tier": 3, "success": False}

    elif is_critical and is_idempotent and fail_count >= 3:
        # Tier 1 with escalation: retry + warning (idempotent, safe to retry)
        if restart_cmd:
            success, _ = retry_job(restart_cmd, host)
            if success:
                record_success(job_id)
                return {"action": "retried_ok", "tier": 1, "success": True}
        if not check_escalation_cooldown(job_id):
            send_alert(
                f"Critical job repeated failure — {job_id}\n"
                f"fail_count={fail_count}\nError: {last_error[:120]}",
                level="WARNING"
            )
            mark_escalation_sent(job_id)
        return {"action": "retried_with_alert", "tier": 1, "success": False}

    else:
        # Tier 3/4: low-confidence or unknown — add to DLQ
        add_to_dlq(job_id, last_error[:500], classification, last_error, files_implicated)
        level = "CRITICAL" if failure_type == "DETERMINISTIC" else "WARNING"
        if not check_escalation_cooldown(job_id):
            send_alert(
                f"{'Tier 3' if failure_type != 'UNKNOWN' else 'Tier 4'} needed — {job_id}\n"
                f"Type: {failure_type} / {classification.get('subtype')}\n"
                f"Error: {last_error[:120]}",
                level=level
            )
            mark_escalation_sent(job_id)
        return {"action": "escalated", "tier": 3, "success": False}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _read_openclaw_job_state(openclaw_id: str) -> str:
    """
    Re-read jobs.json to get the current live status of an OpenClaw job by id.
    Returns: "running" | "ok" | "error" | "unknown"

    Used after a trigger_openclaw_job() timeout to distinguish between:
    - Job still running in gateway (don't escalate, don't retry)
    - Job genuinely failed (proceed with escalation)
    """
    jobs_path = Path.home() / ".openclaw" / "cron" / "jobs.json"
    try:
        data = json.loads(jobs_path.read_text())
        for job in data.get("jobs", []):
            if job.get("id") == openclaw_id:
                state = job.get("state", {})
                if state.get("runningAtMs") is not None:
                    return "running"
                return state.get("lastRunStatus", "unknown")
    except Exception:
        pass
    return "unknown"


def _infer_files(job_id: str, error_text: str) -> list:
    """Extract file paths from error text."""
    import re
    paths = re.findall(r'(?:File |in )[""]?(/[^\s"\']+\.(?:py|sh))', error_text)
    # Also try common script locations
    for pattern in [f"~/scripts/{job_id.replace('_', '-')}.py",
                    f"~/scripts/{job_id.replace('_', '-')}.sh",
                    f"~/Desktop/nuzantara/scripts/{job_id.replace('_', '-')}.py"]:
        expanded = os.path.expanduser(pattern)
        if os.path.exists(expanded):
            paths.append(expanded)
    return list(set(paths)) or ["unknown"]


# ─── Main ─────────────────────────────────────────────────────────────────────

SENTINEL_STATUS_FILE = os.path.expanduser("~/.agent/decisions/sentinel_status.json")
MAX_RUN_DURATION_S = 240  # D1.7: abort if single run exceeds 4 minutes


def run_sentinel() -> None:
    # D0.6: HEALING_DISABLED file flag — safer than env var (works in LaunchAgent)
    if os.path.exists(HEALING_DISABLED_FILE):
        reason = open(HEALING_DISABLED_FILE).read().strip()
        logger.warning(f"HEALING_DISABLED active — skipping sentinel run: {reason}")
        return

    logger.info("=== Sentinel run start ===")
    start_wall = time.time()
    start_mono = time.monotonic()  # D1.7: monotonic clock for deadline
    deadline_mono = start_mono + MAX_RUN_DURATION_S

    registry = load_registry()
    states = collect_state_files(registry)
    check_dead_man_switch()
    _force_halfopen_stale_circuits()  # Unblock circuits stuck OPEN > 2h

    # Tier 0: verify OpenClaw gateway health before processing jobs
    openclaw_is_down = not check_and_repair_openclaw()
    if openclaw_is_down:
        logger.warning("OpenClaw gateway down — openclaw jobs will be suppressed this cycle")

    results = {}
    timed_out = False
    for job_id, state in states.items():
        # D1.7: monotonic deadline — abort iteration if run is taking too long
        if time.monotonic() >= deadline_mono:
            logger.warning(f"Sentinel deadline reached ({MAX_RUN_DURATION_S}s) — skipping remaining jobs")
            timed_out = True
            break
        try:
            results[job_id] = process_job(job_id, state, registry, openclaw_is_down=openclaw_is_down)
        except Exception as e:
            logger.error(f"Error processing {job_id}: {e}", exc_info=True)

    # Self-log (JSONL)
    duration = time.time() - start_wall
    dlq_path = os.path.expanduser("~/.agent/decisions/dlq.json")
    try:
        dlq_data = json.loads(open(dlq_path).read())
        dlq_entries = len(dlq_data.get("queue", dlq_data if isinstance(dlq_data, list) else []))
        dlq_terminal = sum(
            1 for e in (dlq_data.get("queue", dlq_data) if isinstance(dlq_data, (dict, list)) else [])
            if isinstance(e, dict) and e.get("status") == "TERMINAL"
        )
    except Exception:
        dlq_entries = -1
        dlq_terminal = -1

    log_entry = {
        "ts": time.time(),
        "duration_s": round(duration, 2),
        "jobs_checked": len(results),
        "healthy": sum(1 for r in results.values() if r.get("action") == "healthy"),
        "retried": sum(1 for r in results.values() if "retried" in r.get("action", "")),
        "escalated": sum(1 for r in results.values() if "escalated" in r.get("action", "")),
        "suppressed": sum(1 for r in results.values() if r.get("action") == "suppressed_gateway_down"),
        "openclaw_down": openclaw_is_down,
        "timed_out": timed_out,
        "_writer": "sentinel",
    }
    os.makedirs(os.path.dirname(SENTINEL_LOG), exist_ok=True)
    with open(SENTINEL_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # D1.3: sentinel_status.json — single observable for dashboards and MCP tools
    circuit_states: dict = {}
    try:
        from sentinel_lib.circuit_breaker import _load as _cb_load
        circuit_states = _cb_load()
    except Exception:
        pass

    status_obj = {
        "ts": time.time(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "jobs_total": len(states),
        "jobs_checked": len(results),
        "jobs_healthy": log_entry["healthy"],
        "jobs_circuit_open": sum(1 for v in circuit_states.values() if v.get("state") == "OPEN"),
        "jobs_circuit_terminal": dlq_terminal,
        "jobs_healing": log_entry["retried"],
        "jobs_suppressed": log_entry["suppressed"],
        "dlq_entries": dlq_entries,
        "dlq_terminal": dlq_terminal,
        "healing_actions_24h": log_entry["retried"],  # current cycle; full 24h requires log scan
        "openclaw_gateway": "down" if openclaw_is_down else "healthy",
        "last_sentinel_duration_s": round(duration, 2),
        "timed_out": timed_out,
        "_writer": "sentinel",
    }
    os.makedirs(os.path.dirname(SENTINEL_STATUS_FILE), exist_ok=True)
    with open(SENTINEL_STATUS_FILE, "w") as f:
        json.dump(status_obj, f, indent=2)

    logger.info(f"=== Sentinel done: {log_entry['jobs_checked']} checked, "
                f"{log_entry['healthy']} healthy, {log_entry['escalated']} escalated, "
                f"{log_entry['suppressed']} suppressed in {duration:.1f}s ===")


if __name__ == "__main__":
    # D0.2: PID lock — prevent overlapping runs (LaunchAgent may fire before previous finishes)
    import fcntl
    lock_path = "/tmp/nuzantara_sentinel.lock"
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.warning("Another sentinel instance is running — exiting")
        sys.exit(0)
    try:
        run_sentinel()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
