#!/usr/bin/env python3
"""
DLQ Autopilot — processes rotting DLQ entries autonomously.

Pipeline per entry:
  Pre-flight → Claude CLI reasoning → retry / aider-fix / escalate_to_claude_code

Runs every 30min via LaunchAgent com.nuzantara.dlq-autopilot.
Lock: ~/.agent/locks/dlq_autopilot.lock (fcntl, stale-lock detection).
"""
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[DLQAutopilot %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/logs/dlq_autopilot.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("dlq_autopilot")

# ── Paths ──────────────────────────────────────────────────────────────────────
HOME = Path.home()
AGENT_DIR = HOME / ".agent" / "decisions"
DLQ_FILE = AGENT_DIR / "dlq.json"
REGISTRY_FILE = AGENT_DIR / "job_registry.json"
LOCKS_DIR = AGENT_DIR / "locks"
LOCK_FILE = LOCKS_DIR / "dlq_autopilot.lock"
CLAUDE_TASKS_DIR = AGENT_DIR / "claude_tasks"
NUZANTARA_ROOT = HOME / "Desktop" / "nuzantara"

# D2.3: Per-machine escalation JSONL — import lazily to avoid circular issues
import sys as _sys
_sys.path.insert(0, str(NUZANTARA_ROOT / "scripts"))
try:
    from sentinel_lib.escalations import write_escalation as _write_escalation
except ImportError:
    def _write_escalation(entry: dict) -> None:  # type: ignore[misc]
        pass  # graceful degradation if sentinel_lib not importable

# ── Tuning constants ───────────────────────────────────────────────────────────
LOCK_STALE_AGE_S = 1500          # 25min — if lock older than this, treat as stale
MAX_ATTEMPTS = 10                 # per DLQ entry (default; per-job override via registry max_attempts)
DLQ_TTL_S = 172800                # 48h — abandon entries older than this with empty error
MIN_ERROR_LEN = 20                # skip reasoning if error_summary shorter than this
CONFIDENCE_RETRY = 0.95           # no-code-change retry threshold
CONFIDENCE_AIDER = 0.90           # code-change aider threshold
REASONING_TIMEOUT_S = 90          # claude --print timeout

# Jobs that Aider must never touch
AIDER_BLOCKLIST = {
    "core_guardian",
    "daily_ops_autopilot",
    "learning_pipeline",
    "seo_auto_fixer",
    "weekly_review",
    "weekly_report",
}

# Subtypes that indicate the classifier itself failed — no LLM reasoning needed
CLASSIFIER_FAILURE_SUBTYPES = {"no_api_key", "llm_failed", "no_error_text", "unclassified"}


# ── Lock helpers ───────────────────────────────────────────────────────────────

def acquire_lock() -> Optional[int]:
    """Acquire lock file. Returns fd or None if already locked.

    Stale lock detection: if the flock is blocked AND the lock file is older
    than LOCK_STALE_AGE_S, the previous holder is presumed dead. We close the
    fd, unlink, and retry once — racing processes resolve via the retry flock.
    """
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = str(LOCK_FILE)

    for _attempt in range(2):  # at most one stale-lock retry
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except BlockingIOError:
            age = time.time() - os.fstat(fd).st_mtime
            os.close(fd)
            if age > LOCK_STALE_AGE_S and _attempt == 0:
                logger.warning(f"Stale lock detected ({age:.0f}s old) — removing and retrying")
                LOCK_FILE.unlink(missing_ok=True)
                continue
            logger.info("Lock held by another process — skipping this run")
            return None

    logger.info("Lock held by another process — skipping this run")
    return None


def release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ── DLQ I/O ───────────────────────────────────────────────────────────────────

def load_dlq() -> list:
    try:
        return json.loads(DLQ_FILE.read_text()).get("queue", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_dlq(queue: list) -> None:
    tmp = DLQ_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"queue": queue}, indent=2))
    tmp.replace(DLQ_FILE)


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_FILE.read_text()).get("jobs", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> None:
    import urllib.request, urllib.parse
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "413539912")
    if not token:
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": f"🤖 DLQAutopilot | {message}",
        }).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
            ),
            timeout=10,
        )
    except Exception:
        pass


# ── Claude CLI reasoning ───────────────────────────────────────────────────────

def claude_reason(entry: dict) -> Optional[dict]:
    """
    Ask Claude CLI to reason about a DLQ entry.
    Returns {fix_type, fix_instruction, confidence, needs_code_change} or None.
    Falls back gracefully on timeout, missing CLI, or JSON parse failure.
    """
    job = entry["job"]
    error = entry.get("error_summary", "")
    log_tail = entry.get("log_tail", "")[-500:]
    files = entry.get("files_implicated", [])

    prompt = f"""You are diagnosing a failed automation job on a macOS production server.

Job name: {job}
Error summary: {error}
Log tail (last 500 chars): {log_tail}
Files implicated: {files}

Respond with JSON only (no markdown, no explanation):
{{
  "fix_type": "restart|config|code|unknown",
  "fix_instruction": "one concrete sentence describing the exact fix",
  "confidence": 0.0,
  "needs_code_change": false
}}

Rules:
- confidence must be 0.0-1.0
- needs_code_change=true only if source code files need editing
- If error is empty or ambiguous, set confidence <= 0.5
- Do not fabricate fixes for empty errors"""

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=REASONING_TIMEOUT_S,
            env={**os.environ, "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        if result.returncode != 0:
            logger.warning(f"{job}: claude --print exit {result.returncode}")
            return None

        # Strip ANSI codes and extract first JSON object (handles nested braces correctly)
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        start = clean.find("{")
        if start == -1:
            logger.warning(f"{job}: no JSON in claude output")
            return None

        try:
            data, _ = json.JSONDecoder().raw_decode(clean, start)
        except json.JSONDecodeError:
            logger.warning(f"{job}: no JSON in claude output")
            return None
        required = {"fix_type", "fix_instruction", "confidence", "needs_code_change"}
        if not required.issubset(data.keys()):
            logger.warning(f"{job}: claude output missing required keys")
            return None
        data["confidence"] = float(data["confidence"])
        # D4.2: LLM output is advisory only — mark so caller never acts on it directly
        data["llm_suggested_only"] = True
        return data

    except subprocess.TimeoutExpired:
        logger.warning(f"{job}: claude --print timed out after {REASONING_TIMEOUT_S}s")
        return None
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"{job}: JSON parse error: {e}")
        return None
    except FileNotFoundError:
        logger.error("claude CLI not found — check PATH")
        return None


# ── Aider dispatch ────────────────────────────────────────────────────────────

def dispatch_aider(entry: dict, reasoning: dict, registry: dict) -> tuple[bool, str]:
    """
    Dispatch aider-fix via ai-dispatch.sh. Returns (success, output).
    Pre-conditions verified by caller:
      - files_implicated has ≥1 real path on disk
      - test_cmd is present in registry
      - job not in AIDER_BLOCKLIST
    """
    job = entry["job"]
    files = entry.get("files_implicated", [])
    test_cmd = registry.get(job, {}).get("test_cmd", "")
    fix_instruction = reasoning["fix_instruction"]

    prompt = (
        f"Fix automation job '{job}'.\n"
        f"Error: {entry.get('error_summary', '')}\n"
        f"Fix: {fix_instruction}\n"
        f"Files: {', '.join(files)}\n"
        f"Verify by running: {test_cmd}"
    )

    dispatch_script = str(NUZANTARA_ROOT / "scripts" / "ai-dispatch.sh")
    if not os.path.exists(dispatch_script):
        return False, f"ai-dispatch.sh not found at {dispatch_script}"

    # Stash before aider runs — allow git rollback on failure
    stash_label = f"dlq_autopilot_{job}_{int(time.time())}"
    stash_result = subprocess.run(
        ["git", "stash", "push", "-m", stash_label],
        cwd=str(NUZANTARA_ROOT),
        capture_output=True,
        text=True,
    )
    stash_created = "No local changes to stash" not in stash_result.stdout

    try:
        result = subprocess.run(
            ["bash", dispatch_script, "aider-fix", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(NUZANTARA_ROOT),
        )
        success = result.returncode == 0
        output = (result.stdout + result.stderr)[:500]

        if not success and stash_created:
            # Restore stash on failure
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(NUZANTARA_ROOT),
                capture_output=True,
            )

        return success, output
    except subprocess.TimeoutExpired:
        if stash_created:
            subprocess.run(["git", "stash", "pop"], cwd=str(NUZANTARA_ROOT), capture_output=True)
        return False, "aider-fix timed out after 5min"
    except Exception as e:
        return False, str(e)


def verify_fix(test_cmd: str) -> tuple[bool, str]:
    """Run test_cmd to verify a fix worked."""
    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, (result.stdout + result.stderr)[:300]
    except subprocess.TimeoutExpired:
        return False, "test_cmd timed out after 60s"
    except Exception as e:
        return False, str(e)


# ── Escalation ────────────────────────────────────────────────────────────────

def escalate_to_claude_code(
    entry: dict,
    reasoning: Optional[dict],
    aider_failure: Optional[str] = None,
) -> None:
    """Write a claude_tasks JSON file and send Telegram alert."""
    job = entry["job"]
    CLAUDE_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = CLAUDE_TASKS_DIR / f"{job}_{int(time.time())}.json"

    payload: dict = {
        "job": job,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error_summary": entry.get("error_summary", ""),
        "log_tail": entry.get("log_tail", "")[-1000:],
        "files_implicated": entry.get("files_implicated", []),
        "classification": entry.get("classification", {}),
        "dlq_reasoning": reasoning,
        "fix_instruction": reasoning.get("fix_instruction") if reasoning else None,
        "aider_failure_reason": aider_failure,
        "test_cmd": None,
        "priority": (
            "HIGH"
            if entry.get("classification", {}).get("type") == "DETERMINISTIC"
            else "NORMAL"
        ),
    }

    try:
        reg = load_registry()
        payload["test_cmd"] = reg.get(job, {}).get("test_cmd")
    except Exception:
        pass

    task_file.write_text(json.dumps(payload, indent=2))
    logger.info(f"{job}: escalated to Claude Code → {task_file}")

    # D2.3: Also write to per-machine escalation JSONL (federation bus)
    _write_escalation({
        "job": job,
        "type": "dlq_autopilot_escalation",
        "error_summary": entry.get("error_summary", "")[:200],
        "priority": payload["priority"],
        "task_file": str(task_file.name),
    })

    send_telegram(
        f"🔴 Escalated to Claude Code: `{job}`\n"
        f"Error: {entry.get('error_summary', '(empty)')[:80]}\n"
        f"Task file: {task_file.name}"
    )


# ── Main entry processor ──────────────────────────────────────────────────────

def process_entry(entry: dict, registry: dict) -> str:
    """
    Process one DLQ entry. Returns action taken:
    'skipped_terminal', 'skipped_preflight', 'retried_ok', 'aider_fixed', 'escalated', 'terminal', 'archived'
    """
    job = entry["job"]
    error = entry.get("error_summary", "")
    classification = entry.get("classification", {})
    subtype = classification.get("subtype", "")
    attempts = entry.get("autopilot_attempts", 0)
    files = entry.get("files_implicated", [])
    reg = registry.get(job, {})

    # ── D0.1: TERMINAL state guard — MUST be first check ──────────────────────
    # Jobs with status=TERMINAL are dead-ends. Skip entirely — do NOT increment
    # attempts, do NOT re-escalate, do NOT send alerts. Operator must run:
    #   python3 scripts/dlq_autopilot.py clear <job_id>
    # to remove from DLQ after manual resolution.
    if entry.get("status") == "TERMINAL":
        logger.info(f"{job}: status=TERMINAL — skipping (use 'dlq clear {job}' to remove)")
        return "skipped_terminal"

    # ── Pre-flight checks ──────────────────────────────────────────────────────

    # 1. Max attempts exceeded → TERMINAL (not "abandoned" — abandoned re-enters loop)
    max_attempts = reg.get("max_attempts", MAX_ATTEMPTS)
    if attempts >= max_attempts:
        logger.warning(f"{job}: max attempts ({max_attempts}) reached → TERMINAL")
        entry["status"] = "TERMINAL"
        entry["first_abandoned_at"] = entry.get("first_abandoned_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        escalate_to_claude_code(entry, None)
        send_telegram(
            f"🛑 TERMINAL: `{job}` reached {max_attempts} autopilot attempts with no fix.\n"
            f"Error: {error[:80]}\n"
            f"Manual intervention required. Run: `dlq clear {job}` after resolving."
        )
        return "terminal"

    # 2. Entry too old with empty error — misdiagnosed artifact, safe to archive
    added_ts = entry.get("added_ts", 0)
    if not error and (time.time() - added_ts) > DLQ_TTL_S:
        logger.info(f"{job}: empty error + >48h old → archiving")
        return "archived"

    # 3. Classifier itself failed — LLM reasoning would fail for the same reason
    if subtype in CLASSIFIER_FAILURE_SUBTYPES:
        logger.info(f"{job}: subtype={subtype} (classifier failure) → escalating directly")
        escalate_to_claude_code(entry, None)
        return "skipped_preflight"

    # 4. Error too short to reason about reliably
    if len(error) < MIN_ERROR_LEN:
        logger.info(f"{job}: error too short ({len(error)} chars) → escalating directly")
        escalate_to_claude_code(entry, None)
        return "skipped_preflight"

    # ── LLM Reasoning ─────────────────────────────────────────────────────────
    reasoning = claude_reason(entry)
    if reasoning is None:
        logger.warning(f"{job}: reasoning failed → escalating")
        escalate_to_claude_code(entry, None)
        return "escalated"

    # D4.2: LLM output is advisory-only — must be validated before dispatch.
    # claude_reason() always sets llm_suggested_only=True. If this flag is ever
    # absent (e.g., a future code path returns raw output), reject it outright.
    if not reasoning.get("llm_suggested_only"):
        logger.error(
            f"{job}: reasoning missing llm_suggested_only flag — rejecting to prevent "
            f"unvalidated LLM action dispatch. Escalating."
        )
        escalate_to_claude_code(entry, None)
        return "escalated"

    confidence = reasoning["confidence"]
    needs_code = reasoning["needs_code_change"]
    logger.info(
        f"{job}: reasoning → confidence={confidence:.2f} "
        f"needs_code={needs_code} type={reasoning['fix_type']}"
    )

    # ── Tier 1: high-confidence no-code retry ─────────────────────────────────
    if confidence >= CONFIDENCE_RETRY and not needs_code:
        restart_cmd = reg.get("restart_cmd")
        if restart_cmd:
            try:
                result = subprocess.run(
                    ["bash", "-c", restart_cmd],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"{job}: retry OK ✅")
                    send_telegram(f"✅ Auto-retried `{job}` successfully")
                    return "retried_ok"
            except Exception as e:
                logger.warning(f"{job}: retry failed: {e}")

    # ── Tier 2: high-confidence code change via Aider ─────────────────────────
    real_files = [
        f for f in files
        if f != "unknown" and os.path.exists(os.path.expanduser(f))
    ]
    if (
        confidence >= CONFIDENCE_AIDER
        and needs_code
        and job not in AIDER_BLOCKLIST
        and real_files
        and reg.get("test_cmd")
    ):
        logger.info(f"{job}: dispatching Aider (files: {real_files})")
        aider_ok, aider_out = dispatch_aider(entry, reasoning, registry)

        if aider_ok:
            verified, _ = verify_fix(reg["test_cmd"])
            if verified:
                logger.info(f"{job}: Aider fix verified ✅")
                send_telegram(
                    f"✅ Aider auto-fixed `{job}`: {reasoning['fix_instruction'][:80]}"
                )
                return "aider_fixed"

        logger.warning(f"{job}: Aider failed or unverified → escalating")
        escalate_to_claude_code(entry, reasoning, aider_out)
        return "escalated"

    # ── Tier 3: escalate to Claude Code ───────────────────────────────────────
    reason = (
        f"confidence={confidence:.2f}<threshold"
        if confidence < CONFIDENCE_AIDER
        else f"job_in_blocklist={job in AIDER_BLOCKLIST} no_real_files={not real_files}"
    )
    logger.info(f"{job}: {reason} → escalating to Claude Code")
    escalate_to_claude_code(entry, reasoning)
    return "escalated"


# ── Main ──────────────────────────────────────────────────────────────────────

def run_autopilot() -> None:
    logger.info("=== DLQ Autopilot run start ===")
    start = time.time()

    fd = acquire_lock()
    if fd is None:
        return

    try:
        queue = load_dlq()
        registry = load_registry()
        logger.info(f"DLQ entries: {len(queue)}")

        if not queue:
            logger.info("DLQ empty — nothing to do")
            return

        results: dict[str, str] = {}
        updated_queue = []

        for entry in queue:
            job = entry["job"]
            action = process_entry(entry, registry)
            results[job] = action

            if action in ("retried_ok", "aider_fixed", "archived"):
                pass  # Remove from DLQ
            elif action == "skipped_terminal":
                # TERMINAL entries stay in DLQ for audit — DO NOT increment attempts
                updated_queue.append(entry)
            elif action == "terminal":
                # Just transitioned to TERMINAL — keep for audit, no increment
                updated_queue.append(entry)
            else:
                # escalated / skipped_preflight — keep in DLQ, increment attempts
                entry["status"] = action
                entry["autopilot_attempts"] = entry.get("autopilot_attempts", 0) + 1
                updated_queue.append(entry)

        save_dlq(updated_queue)

        duration = time.time() - start
        fixed = sum(1 for a in results.values() if a in ("retried_ok", "aider_fixed"))
        escalated = sum(1 for a in results.values() if a == "escalated")
        skipped = sum(1 for a in results.values() if a == "skipped_preflight")

        logger.info(
            f"=== DLQ Autopilot done: {len(queue)} processed, "
            f"{fixed} fixed, {escalated} escalated, {skipped} skipped "
            f"in {duration:.1f}s ==="
        )

        # Write sentinel state file so Sentinel can monitor autopilot staleness
        state_dir = AGENT_DIR / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dlq_autopilot.last.json"
        state_file.write_text(json.dumps({
            "job": "dlq_autopilot",
            "status": "ok",
            "detail": f"processed={len(queue)} fixed={fixed} escalated={escalated}",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "_writer": "dlq_autopilot",  # D1.5: audit trail
        }))

    finally:
        release_lock(fd)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "clear":
        job_id = sys.argv[2]
        queue = load_dlq()
        before = len(queue)
        queue = [e for e in queue if not (e["job"] == job_id and e.get("status") == "TERMINAL")]
        after = len(queue)
        if before == after:
            print(f"No TERMINAL entry found for '{job_id}' in DLQ")
        else:
            save_dlq(queue)
            print(f"Cleared TERMINAL entry for '{job_id}' from DLQ ({before - after} removed)")
            logger.info(f"dlq_clear_manual: {job_id} removed from DLQ by operator")
    else:
        run_autopilot()
