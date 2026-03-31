"""Tier dispatch: retry (T1), aider-fix (T2), Claude Code alert (T3), Zero alert (T4)."""
import json
import os
import stat
import subprocess
import time
from typing import Optional

# D1.4: idempotency token uses run-slot granularity (not date.today())
DEFAULT_INTERVAL_S = 86400


def make_idempotency_token(job_id: str, interval_s: Optional[int] = None) -> str:
    """Return a stable dedup token for the current run-slot of a job.

    Unlike date.today(), this is granular to the job's actual schedule interval,
    preventing false deduplication of jobs that run multiple times per day.
    """
    effective_interval = interval_s or DEFAULT_INTERVAL_S
    slot = int(time.time() // effective_interval)
    return f"{job_id}:{slot}"


DLQ_FILE = os.path.expanduser("~/.agent/decisions/dlq.json")
NUZANTARA_ROOT = os.path.realpath(os.path.expanduser("~/Desktop/nuzantara"))
ALLOWED_CMDS_FILE = os.path.expanduser("~/.agent/decisions/allowed_cmds.txt")

# D2.1: Shell metacharacter blocklist — includes null byte, newline, CR (Codex PARTIAL C5)
_SHELL_METACHAR_BLOCKLIST = (
    "&&", "||", ";", "|", "$(", "`", ">", "<", ">>",
    "\x00", "\n", "\r",
)

# D2.1: Allowed command root directories
_ALLOWED_ROOTS = (
    NUZANTARA_ROOT,
    "/usr/bin",
    "/opt/homebrew/bin",
    "/opt/homebrew/lib/node_modules",  # Node.js-based CLIs (openclaw)
    "/opt/homebrew/Cellar",            # Homebrew-managed binaries (fly/flyctl, etc.)
    os.path.expanduser("~/.local/bin"),
    "/usr/local/bin",
)


def _load_allowlist() -> set:
    """Load allowed_cmds.txt and harden its permissions to 0o444 (read-only).

    Returns set of allowed command prefixes. An empty set means no allowlist
    is configured — validation falls back to root-pinning only.
    """
    if not os.path.exists(ALLOWED_CMDS_FILE):
        return set()
    try:
        # Harden: set read-only so AI agents cannot modify during a session
        current_mode = os.stat(ALLOWED_CMDS_FILE).st_mode
        if current_mode & 0o222:  # writable bits set
            os.chmod(ALLOWED_CMDS_FILE, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        with open(ALLOWED_CMDS_FILE) as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        return set(lines)
    except OSError:
        return set()


def validate_restart_cmd(cmd: str) -> tuple[bool, str]:
    """D2.1 + D2.2: Validate restart_cmd before execution.

    Checks (in order):
    1. Null / empty
    2. Shell metacharacter injection (includes \\x00, \\n, \\r)
    3. Path traversal: realpath of first token must be under an allowed root
    4. Allowlist: if allowed_cmds.txt exists, first token must match a prefix

    Returns (ok: bool, reason: str).
    """
    if not cmd or not cmd.strip():
        return False, "empty command"

    # Check metacharacters
    for meta in _SHELL_METACHAR_BLOCKLIST:
        if meta in cmd:
            return False, f"blocked metacharacter in command: {meta!r}"

    # Extract the executable (first token)
    first_token = cmd.split()[0]
    # Resolve symlinks and normalise (collapses ../../ traversals)
    try:
        resolved = os.path.realpath(os.path.expanduser(first_token))
    except Exception as exc:
        return False, f"path resolution error: {exc}"

    # Root-pinning: executable must live under an allowed root
    allowed_by_root = any(resolved.startswith(root) for root in _ALLOWED_ROOTS)
    if not allowed_by_root:
        return False, f"command root not allowed: {resolved}"

    # Allowlist check (optional — only applied if file exists)
    allowlist = _load_allowlist()
    if allowlist:
        allowed_by_list = any(cmd.startswith(prefix) for prefix in allowlist)
        if not allowed_by_list:
            return False, f"command not in allowed_cmds.txt: {cmd[:80]}"

    return True, "ok"


def _load_dlq() -> dict:
    try:
        return json.loads(open(DLQ_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"queue": []}


def _save_dlq(data: dict) -> None:
    with open(DLQ_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_to_dlq(job: str, error_summary: str, classification: dict, log_tail: str,
               files_implicated: list, aider_attempts: int = 0,
               aider_failure_reason: Optional[str] = None) -> None:
    """Add job to DLQ. Idempotent — won't add duplicate entries."""
    data = _load_dlq()
    # Remove existing entry for this job (will re-add with fresh info)
    data["queue"] = [e for e in data["queue"] if e.get("job") != job]
    data["queue"].append({
        "job": job,
        "added_ts": time.time(),
        "error_summary": error_summary,
        "log_tail": log_tail[-2000:],  # last 2000 chars
        "classification": classification,
        "files_implicated": files_implicated,
        "aider_attempts": aider_attempts,
        "aider_failure_reason": aider_failure_reason,
        "status": "needs_claude_code" if aider_attempts > 0 else "needs_aider",
    })
    _save_dlq(data)


def clear_dlq_entry(job: str) -> None:
    """Remove job from DLQ after successful fix."""
    data = _load_dlq()
    data["queue"] = [e for e in data["queue"] if e.get("job") != job]
    _save_dlq(data)


def retry_job(restart_cmd: str, host: str = "Nuzantara") -> tuple:
    """
    Execute restart_cmd (locally or via SSH if host != current hostname).
    D2.2: Performs its own allowlist + realpath validation before execution —
    defense-in-depth against callers that skip validate_restart_cmd().
    Returns (success, output).
    """
    # D2.2: defense-in-depth — validate even if caller already validated
    valid, reason = validate_restart_cmd(restart_cmd)
    if not valid:
        return False, f"command rejected by retry_job allowlist: {reason}"

    import socket
    current_host = socket.gethostname()

    if host != current_host and host != "localhost":
        cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", host, restart_cmd]
    else:
        cmd = ["bash", "-c", restart_cmd]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Retry command timed out after 30s"
    except Exception as e:
        return False, str(e)


def dispatch_aider_fix(job: str, error_summary: str, fix_instruction: str,
                       files_implicated: list, test_cmd: Optional[str]) -> tuple:
    """
    Dispatch ai-dispatch.sh aider-fix with structured prompt.
    Returns (success, output).
    """
    files_str = ", ".join(files_implicated) if files_implicated else "unknown"
    verify_str = f"\nVerify by running: {test_cmd}" if test_cmd else ""

    prompt = (
        f"Fix automation job '{job}'.\n"
        f"Error: {error_summary}\n"
        f"Fix: {fix_instruction}\n"
        f"Files: {files_str}"
        f"{verify_str}"
    )

    dispatch_script = os.path.join(NUZANTARA_ROOT, "scripts", "ai-dispatch.sh")
    if not os.path.exists(dispatch_script):
        return False, f"ai-dispatch.sh not found at {dispatch_script}"

    try:
        result = subprocess.run(
            ["bash", dispatch_script, "aider-fix", prompt],
            capture_output=True, text=True, timeout=300, cwd=NUZANTARA_ROOT
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "aider-fix timed out after 5min"
    except Exception as e:
        return False, str(e)


def verify_fix(test_cmd: str, host: str = "Nuzantara") -> tuple:
    """Run test_cmd to verify a fix worked. Returns (passed, output)."""
    return retry_job(test_cmd, host)


def trigger_openclaw_job(openclaw_id: str, timeout_ms: int = 660000) -> tuple:
    """
    Trigger an OpenClaw cron job via CLI and wait for completion.

    ARCHITECTURE NOTE:
    `openclaw cron run <id>` is a SYNCHRONOUS blocking call — it holds the
    WebSocket open until the agent turn completes, then returns JSON.
    The gateway-side handler awaits executeJobCoreWithTimeout() before respond()ing.

    Response shapes (from gateway source):
      {"ok": true,  "ran": true,  ...}         -> job ran and finished
      {"ok": true,  "ran": false, "reason": "already-running"} -> in-progress, not a failure
      {"ok": true,  "ran": false, "reason": "not-due"}         -> schedule guard, not a failure
      {"ok": false, ...}                        -> gateway error

    timeout_ms should be >= 660000 (11 min) for agentTurn jobs.
    The CLI's own default for `cron run` is 600000ms (10 min). We set
    11 min here so the subprocess wrapper never fires before the CLI does.

    Returns (success, output).
    """
    # Gateway CLI default for `cron run` is 600000ms. Set slightly above so the
    # subprocess timeout never races with the CLI's own timeout handling.
    gateway_timeout_ms = min(timeout_ms, 600000)
    subprocess_timeout_s = gateway_timeout_ms / 1000 + 90  # +90s grace for gateway shutdown

    try:
        result = subprocess.run(
            ["openclaw", "cron", "run", openclaw_id, "--timeout", str(gateway_timeout_ms)],
            capture_output=True,
            text=True,
            timeout=subprocess_timeout_s,
            env={**os.environ, "PATH": f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"},
        )
        output = (result.stdout.strip() + result.stderr.strip()).strip()

        # Parse JSON response from gateway
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            # Non-JSON output — fall back to exit code
            return result.returncode == 0, output

        ok = data.get("ok", False)
        ran = data.get("ran", False)
        reason = data.get("reason", "")

        # "already-running": job is mid-run from a previous cycle, not a failure
        # "not-due": schedule guard fired (mode=due), normal
        if ok and not ran and reason in ("already-running", "not-due"):
            return True, f"skipped ({reason}): {output}"

        # Job ran and finished successfully
        if ok and ran:
            return True, output

        # ok=false or ran=false with unexpected reason
        return False, output

    except subprocess.TimeoutExpired:
        # The gateway continues running the job after CLI disconnects.
        # This is NOT a definitive failure — log as ambiguous, not False.
        # Caller should check job state via jobs.json before escalating.
        return False, (
            f"openclaw cron run timed out after {gateway_timeout_ms}ms — "
            f"gateway may still be running the job. Check jobs.json state."
        )
    except FileNotFoundError:
        return False, "openclaw CLI not found in PATH (/opt/homebrew/bin/openclaw)"
    except Exception as e:
        return False, str(e)


def is_openclaw_running() -> bool:
    """
    Check if OpenClaw gateway is alive.

    Uses `openclaw gateway status` (the correct subcommand for v2026.3.7).
    Falls back to a direct TCP probe of port 18789 if the CLI call fails.
    """
    # Primary: openclaw gateway status (fast, no agent interaction)
    try:
        result = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True, text=True, timeout=8,
            env={**os.environ, "PATH": f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"},
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback: TCP probe on port 18789
    import socket as _socket
    try:
        with _socket.create_connection(("127.0.0.1", 18789), timeout=2):
            return True
    except OSError:
        return False


def restart_openclaw() -> tuple:
    """
    Restart OpenClaw gateway.

    Uses `openclaw gateway restart` which wraps `launchctl kickstart -k` on macOS
    (verified working on v2026.3.7). The -k flag kills any zombie process first.
    Gateway has KeepAlive=true + ThrottleInterval=1 in the plist, so launchd
    respawns within 1s even after a kill.

    Returns (success, output).
    """
    try:
        result = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"},
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            # Wait for gateway to bind port 18789
            for _ in range(6):  # up to 6s
                time.sleep(1)
                if is_openclaw_running():
                    return True, f"OpenClaw restarted OK. {output}"
            return False, f"Restart command succeeded but gateway not responding after 6s. {output}"
        return False, f"Restart failed (exit {result.returncode}): {output}"
    except subprocess.TimeoutExpired:
        return False, "openclaw gateway restart timed out after 30s"
    except Exception as e:
        return False, str(e)
