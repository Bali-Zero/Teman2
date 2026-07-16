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
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[DLQAutopilot %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/logs/dlq_autopilot.log")),
        # ops-hardening fix 2026-05-19: explicit sys.stdout.
        # Default StreamHandler() routes to sys.stderr, which sent
        # 62 INFO "status=TERMINAL — skipping" lines per run to
        # the plist StandardErrorPath (12.7 MB/day error.log).
        logging.StreamHandler(sys.stdout),
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
# Organism heartbeat sidecars (_organism_lib.sh → ~/.organism/last_seen/<node>.<job>.json).
# Used as an INDEPENDENT corpse-sweep freshness source when the launchagent-state-bridge
# stops refreshing AGENT_DIR/state/<job>.last.json (see _organism_recovery_signal).
ORGANISM_DIR = HOME / ".organism" / "last_seen"

# D2.3: Per-machine escalation JSONL — import lazily to avoid circular issues
import sys as _sys

_sys.path.insert(0, str(NUZANTARA_ROOT / "scripts"))
try:
    from sentinel_lib.escalations import write_escalation as _write_escalation
    from sentinel_lib.escalations import mark_resolved as _mark_resolved
except ImportError:
    def _write_escalation(entry: dict) -> None:  # type: ignore[misc]
        pass  # graceful degradation if sentinel_lib not importable

    def _mark_resolved(job_id: str) -> int:  # type: ignore[misc]
        return 0  # graceful degradation if sentinel_lib not importable

# S3 (2026-06-02): per-job escalation cooldown. The sentinel's alerter already
# gates Telegram by a 4h per-job cooldown (escalation_cooldown.json), but the
# DLQ-autopilot escalation path (escalate_to_claude_code) did NOT consult it —
# so a job stuck with an empty/short error re-escalated EVERY 30-min tick,
# growing shared/escalations_pro.jsonl + spamming claude_tasks/*.json for ~5h
# until attempts hit max → TERMINAL (W61 storm relay, ~33 jobs cycled). Reusing
# the SAME cooldown helpers makes the JSONL writer respect the same 4h window.
try:
    from sentinel_lib.alerter import (
        check_escalation_cooldown as _check_escalation_cooldown,
        mark_escalation_sent as _mark_escalation_sent,
    )
except ImportError:
    def _check_escalation_cooldown(job_id: str) -> bool:  # type: ignore[misc]
        return False  # graceful degradation: never suppress if lib unavailable

    def _mark_escalation_sent(job_id: str) -> None:  # type: ignore[misc]
        pass

# ── Tuning constants ───────────────────────────────────────────────────────────
LOCK_STALE_AGE_S = 1500          # 25min — if lock older than this, treat as stale
MAX_ATTEMPTS = 10                 # per DLQ entry (default; per-job override via registry max_attempts)
DLQ_TTL_S = 172800                # 48h — abandon entries older than this with empty error
MIN_ERROR_LEN = 20                # skip reasoning if error_summary shorter than this
# Corpse-sweep freshness window: only drain a "recovered" (status==ok) DLQ entry if
# its state file's "ok" is RECENT. A stale "ok" (job hasn't actually re-run in this
# window) is NOT proof of recovery — draining it just re-arms the blind loop
# (drain → sentinel re-adds on next failure → drain → forever; 90 consecutive blind
# cycles observed 2026-06-20). Genuinely-recovered jobs write a fresh ok on success
# and drain on the next tick. Fail-closed on missing/old ts.
CORPSE_SWEEP_FRESH_S = int(os.getenv("DLQ_CORPSE_SWEEP_FRESH_S", str(6 * 3600)))  # 6h
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

def acquire_lock() -> int | None:
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


def _state_is_fresh(state: dict) -> bool:
    """True iff the state file's timestamp is within CORPSE_SWEEP_FRESH_S of now.

    A missing / zero / unparseable ts is NOT fresh (fail-closed: never drain on an
    absent timestamp). Tolerates the legacy ISO-8601 ts format older writers emitted
    (W54) the same way the sentinel does.
    """
    raw = state.get("ts", 0)
    try:
        ts = float(raw) if raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        try:
            import datetime as _dt
            ts = _dt.datetime.strptime(str(raw), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=_dt.timezone.utc).timestamp()
        except Exception:
            return False
    if ts <= 0:
        return False
    return (time.time() - ts) <= CORPSE_SWEEP_FRESH_S


def _organism_recovery_signal(job: str) -> bool:
    """Fallback recovery proof from the organism heartbeat sidecar.

    Root cause (2026-06-21): the launchagent-state-bridge (a HOME-fork edited
    2026-06-06) silently stopped refreshing AGENT_DIR/state/<job>.last.json for a
    subset of jobs (zombie_hunter, post_publish_poller, post_publish_webhook). Those
    files froze at a stale "ok", so the corpse-sweep's fail-closed freshness check
    parked the jobs DLQ-TERMINAL forever even though they are healthy. Jobs that emit
    the organism heartbeat (_organism_lib.sh → ~/.organism/last_seen/<node>.<job>.json)
    write a genuinely-independent fresh "ok" on every run, so consult it as a SECOND
    freshness source. This never weakens fail-closed: it only ever drains MORE, and
    only when a live independent heartbeat proves recovery. Returns True iff some
    matching organism sidecar is status==ok AND fresh.
    """
    if not ORGANISM_DIR.is_dir():
        return False
    candidates = list(ORGANISM_DIR.glob(f"*.{job}.json")) + [ORGANISM_DIR / f"{job}.json"]
    for sf in candidates:
        try:
            state = json.loads(sf.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if state.get("status") == "ok" and _state_is_fresh(state):
            return True
    return False


def sweep_recovered_corpses(queue: list) -> tuple[list, list]:
    """Drain DLQ entries whose job has since recovered (state.status == 'ok' AND fresh).

    Root cause this fixes (W81 / blind heal-loop, 2026-06-15): process_entry()'s
    TERMINAL guard skips TERMINAL entries forever, and the sentinel's W70-resurrect
    sweep (nuzantara-sentinel.py) only iterates *registry-backed* jobs. Jobs NOT in
    job_registry.json that have recovered therefore rot in the DLQ as false-positive
    corpses. This sweep reads each entry's live state file and removes any whose last
    run succeeded, regardless of DLQ status. If a job regresses, the sentinel re-adds
    it on the next failure. Returns (kept_entries, cleared_job_names).
    """
    state_dir = AGENT_DIR / "state"
    kept: list = []
    cleared: list = []
    for entry in queue:
        job = entry.get("job", "")
        state_file = state_dir / f"{job}.last.json"
        agent_state_ok = False
        try:
            state = json.loads(state_file.read_text())
            agent_state_ok = state.get("status") == "ok" and _state_is_fresh(state)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            agent_state_ok = False
        # Primary signal: agent-state .last.json (launchagent-state-bridge). Fallback:
        # the organism heartbeat sidecar, for jobs the bridge no longer refreshes
        # (2026-06-21 — see _organism_recovery_signal). Both are fail-closed: a stale
        # "ok", status != ok, or an absent file is NOT proof of recovery, so the entry
        # stays parked for audit and the sentinel re-classifies it if it really died.
        if agent_state_ok or _organism_recovery_signal(job):
            cleared.append(job)
        else:
            kept.append(entry)
    return kept, cleared


# ── Telegram ──────────────────────────────────────────────────────────────────
# Migrated to the notification gateway (2026-07-06). Tier semantics:
#   p0     — 🔴 escalations / 🛑 TERMINAL (operator must act)
#   digest — ✅ auto-fixes, 🧹 corpse-sweeps (informative, grouped 2×/day)
# The gateway owns token resolution, dedup and the daily P0 budget.

def send_telegram(message: str, tier: str = "digest", dedup_key: str = "") -> None:
    gateway = Path(__file__).resolve().parent / "tg_notify.py"
    if not gateway.exists():  # HOME-fork copy: fall back to the repo checkout (#1)
        gateway = NUZANTARA_ROOT / "scripts" / "tg_notify.py"
    cmd = [sys.executable, str(gateway), "--tier", tier, "--source", "dlq-autopilot"]
    if dedup_key:
        cmd += ["--dedup-key", dedup_key]
    cmd += ["--", f"🤖 DLQAutopilot | {message}"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception:
        pass


# ── Claude CLI token chain (multi-account fallback) ──────────────────────────

_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|429|exhausted|quota|hit your limit|"
    r"timeout after 90s|possibly rate limit|capacity|overloaded",
    re.IGNORECASE,
)
_EXHAUSTED_TOKENS: dict[str, str] = {}  # label → reason (per-process latch)


def _load_token_chain() -> list[tuple[str, str]]:
    """Load ordered list of (label, oauth_token) to try."""
    chain: list[tuple[str, str]] = []
    for i in (1, 2, 3):
        tok = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
        if tok:
            chain.append((f"token_{i}", tok))
    legacy = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if legacy and not any(t == legacy for _, t in chain):
        chain.append(("token_legacy", legacy))
    chain.append(("keychain", ""))
    return chain


# ── Claude CLI reasoning ───────────────────────────────────────────────────────

def claude_reason(entry: dict) -> dict | None:
    """
    Ask Claude CLI to reason about a DLQ entry.
    Returns {fix_type, fix_instruction, confidence, needs_code_change} or None.
    Multi-account fallback: tries TOKEN_1→2→3→legacy→keychain.
    Latches exhausted tokens per-process to avoid repeated timeouts.
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

    chain = _load_token_chain()

    for label, token in chain:
        if label in _EXHAUSTED_TOKENS:
            logger.info(f"{job}: skip {label} (exhausted: {_EXHAUSTED_TOKENS[label]})")
            continue

        env = {
            **os.environ,
            "PATH": (
                f"{os.path.expanduser('~/.local/bin')}:"
                f"{os.path.expanduser('~/.claude/local')}:"
                "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
            ),
        }
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True,
                text=True,
                timeout=REASONING_TIMEOUT_S,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"{job}: {label} timed out after {REASONING_TIMEOUT_S}s")
            _EXHAUSTED_TOKENS[label] = "timeout"
            continue
        except FileNotFoundError:
            logger.error("claude CLI not found — check PATH")
            return None

        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0 and _RATE_LIMIT_RE.search(combined):
            logger.warning(f"{job}: {label} rate-limited — trying next token")
            _EXHAUSTED_TOKENS[label] = "rate_limit"
            continue

        if result.returncode != 0:
            logger.warning(f"{job}: {label} exit {result.returncode}")
            return None

        # Parse JSON from output
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        start = clean.find("{")
        if start == -1:
            logger.warning(f"{job}: no JSON in claude output ({label})")
            return None

        try:
            data, _ = json.JSONDecoder().raw_decode(clean, start)
        except json.JSONDecodeError:
            logger.warning(f"{job}: no JSON in claude output ({label})")
            return None
        required = {"fix_type", "fix_instruction", "confidence", "needs_code_change"}
        if not required.issubset(data.keys()):
            logger.warning(f"{job}: claude output missing required keys")
            return None
        data["confidence"] = float(data["confidence"])
        data["llm_suggested_only"] = True
        data["_token_used"] = label
        return data

    logger.warning(f"{job}: all Claude tokens exhausted")
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
    reasoning: dict | None,
    aider_failure: str | None = None,
    bypass_cooldown: bool = False,
) -> None:
    """Write a claude_tasks JSON file and send Telegram alert.

    S3 (2026-06-02): unless ``bypass_cooldown`` is True, this is gated by the
    per-job 4h escalation cooldown (sentinel_lib.alerter). A job already
    escalated within the window is skipped entirely (no claude_tasks file, no
    JSONL append, no Telegram) — preventing the W61 every-30-min storm that
    re-grew shared/escalations_pro.jsonl. The cooldown is per-JOB, not per-error:
    a job already known-failing won't re-spam, but the full error history still
    lives in the DLQ entry + the SQLite mirror, and the eventual TERMINAL
    transition escalates with ``bypass_cooldown=True`` so the operator always
    gets the one signal that matters.
    """
    job = entry["job"]

    # S3: suppress repeat escalations for a job on cooldown (state-change
    # escalations — e.g. reaching TERMINAL — pass bypass_cooldown=True).
    if not bypass_cooldown and _check_escalation_cooldown(job):
        logger.info(
            f"{job}: escalation on cooldown (<4h since last) — "
            f"skipping claude_tasks file + JSONL append + Telegram"
        )
        _record_suppressed(job)
        return

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
        f"Task file: {task_file.name}",
        tier="p0",
        dedup_key=f"dlq-escalation:{job}",
    )

    # S3: record the escalation so subsequent ticks within 4h are suppressed.
    # (Mirrors what the sentinel alerter does for its own Telegram alerts.)
    if not bypass_cooldown:
        _mark_escalation_sent(job)


def _record_suppressed(job: str) -> None:
    """S3: bump a per-job ``suppressed_count`` in escalation_cooldown.json.

    The W55 weekly digest (scripts/escalations_suppressed_digest.py) reads these
    counters so the operator sees how many escalations the cooldown hid. The
    cooldown JSON is written by a single machine per file in the 2-node setup
    (Pro writes the pro state), so a best-effort read-modify-write is adequate —
    same locking posture as the existing alerter._save_escalation_state.
    Never raises: a counter miss must not block the autopilot.
    """
    try:
        from sentinel_lib import alerter as _al
        data = _al._load_escalation_state()
        entry = data.get(job) or {}
        entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1
        entry["last_suppressed_at"] = time.time()
        # Preserve escalation_sent_at / _writer if present.
        data[job] = {**entry}
        _al._save_escalation_state(data)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"suppressed-count bump failed for {job} (non-fatal): {exc}")


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
        # S3: TERMINAL is a state-change — the one signal the operator must
        # always receive. Bypass the cooldown so it is never suppressed by the
        # repeated escalations during the climb to max_attempts.
        escalate_to_claude_code(entry, None, bypass_cooldown=True)
        send_telegram(
            f"🛑 TERMINAL: `{job}` reached {max_attempts} autopilot attempts with no fix.\n"
            f"Error: {error[:80]}\n"
            f"Manual intervention required. Run: `dlq clear {job}` after resolving.",
            tier="p0",
            dedup_key=f"dlq-terminal:{job}",
        )
        return "terminal"

    # 2. Entry too old with empty error — misdiagnosed artifact, safe to archive
    added_ts = entry.get("added_ts", 0)
    if not error and (time.time() - added_ts) > DLQ_TTL_S:
        logger.info(f"{job}: empty error + >48h old → archiving")
        return "archived"

    # 3. Classifier itself failed — LLM reasoning would fail for the same reason
    if subtype in CLASSIFIER_FAILURE_SUBTYPES:
        # Noise gate (board-honesty cure, 2026-07-16): a subset of classifier
        # failures carries ZERO diagnostic content — empty/whitespace error_summary
        # AND classification stuck at classifier.py's no_error_text short-circuit
        # (type=UNKNOWN, confidence=0.0). Escalating these produces a content-free
        # board entry an operator can never act on (dropbox_intake: repeat offender
        # in shared/escalations_pro.jsonl). Match the FACT (both fields), not the
        # subtype substring — other CLASSIFIER_FAILURE_SUBTYPES (no_api_key,
        # cli_failed, ...) can carry a real error and stay escalatable.
        if (
            not error.strip()
            and classification.get("type") == "UNKNOWN"
            and classification.get("confidence") == 0.0
        ):
            logger.info(
                f"{job}: subtype={subtype}, empty error + UNKNOWN/0.0 confidence "
                f"— noise gate, logging only (no board write, no Telegram)"
            )
            return "skipped_noise"
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

        # ── Tier 2.5: Codex CLI fix — multi-file, sandboxed ────────────────
        # Aider failed, but this isn't architecturally critical. Let Codex try
        # before bothering Zero. Codex runs sandboxed (workspace-write only).
        logger.info(f"{job}: Aider failed → trying Codex CLI (Tier 2.5)")
        from sentinel_lib.repairer import dispatch_codex_fix
        codex_ok, codex_out = dispatch_codex_fix(
            job=job,
            error_summary=entry.get("error_summary", ""),
            fix_instruction=reasoning["fix_instruction"],
            files_implicated=real_files,
            test_cmd=reg.get("test_cmd"),
            aider_output=aider_out,
        )
        if codex_ok:
            verified, _ = verify_fix(reg["test_cmd"])
            if verified:
                logger.info(f"{job}: Codex fix verified ✅")
                send_telegram(
                    f"✅ Codex auto-fixed `{job}` (after Aider fail): "
                    f"{reasoning['fix_instruction'][:80]}"
                )
                return "codex_fixed"

        logger.warning(f"{job}: Codex also failed → escalating to Claude Code")
        escalate_to_claude_code(entry, reasoning, codex_out or aider_out)
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


def _resolve_swept_escalations(swept: list) -> int:
    """Board-honesty cure (2026-07-16): append a resolution pair for each
    corpse-swept job that has a pending escalation.

    Root cause fixed: sweep_recovered_corpses() drains a DLQ entry once its
    job proves fresh recovery, but nothing ever flipped the matching
    shared/escalations_pro.jsonl entry from pending → resolved — the board
    kept shouting about jobs that had already healed (alert-fatigue,
    scar-family #2 Esiste≠Armato). ``mark_resolved`` is append-only (never
    rewrites the original pending line — immutable log, D2.3) and is a no-op
    (returns 0, writes nothing) for jobs with no matching pending entry, so
    this is safe to call unconditionally for every swept job.
    """
    resolved = 0
    for job in swept:
        try:
            if _mark_resolved(job):
                resolved += 1
        except Exception as exc:  # noqa: BLE001 — must never break the autopilot run
            logger.warning(f"{job}: mark_resolved failed (escalation stays pending): {exc}")
    return resolved


# ── Main ──────────────────────────────────────────────────────────────────────

def run_autopilot() -> None:
    logger.info("=== DLQ Autopilot run start ===")
    start = time.time()

    fd = acquire_lock()
    if fd is None:
        return

    try:
        queue = load_dlq()
        # W81 (2026-06-15): drain recovered corpses before processing. Closes the
        # gap where non-registry jobs that recovered (state=ok) sit forever behind
        # process_entry()'s TERMINAL guard, while the sentinel's W70-resurrect only
        # iterates registry-backed jobs. See sweep_recovered_corpses().
        queue, swept = sweep_recovered_corpses(queue)
        if swept:
            save_dlq(queue)
            resolved_count = _resolve_swept_escalations(swept)
            logger.info(
                f"corpse-sweep: drained {len(swept)} recovered entries: {swept} "
                f"(resolved {resolved_count} pending escalation(s) on the board)"
            )
            send_telegram(
                f"🧹 DLQ corpse-sweep: drained {len(swept)} recovered job(s): "
                f"{', '.join(swept[:8])}"
            )
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
        noise_skipped = sum(1 for a in results.values() if a == "skipped_noise")

        logger.info(
            f"=== DLQ Autopilot done: {len(queue)} processed, "
            f"{fixed} fixed, {escalated} escalated, {skipped} skipped, "
            f"{noise_skipped} noise-gated (no board write) "
            f"in {duration:.1f}s ==="
        )

        # Write sentinel state file so Sentinel can monitor autopilot staleness
        # W54 (2026-05-23): ts must be FLOAT epoch seconds (consistent with all
        # other state files under .agent/decisions/state/*.last.json). Previous
        # code wrote ISO-8601 string via time.strftime(), which broke sentinel's
        # `age = now - last_ts` arithmetic with:
        #   ERROR Error processing dlq_autopilot:
        #     unsupported operand type(s) for -: 'float' and 'str'
        # Empirical: 49 state files surveyed, 48 use int/float, only this one
        # used string. dlq_autopilot.py was the inconsistent writer.
        state_dir = AGENT_DIR / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dlq_autopilot.last.json"
        state_file.write_text(json.dumps({
            "job": "dlq_autopilot",
            "status": "ok",
            "detail": f"processed={len(queue)} fixed={fixed} escalated={escalated}",
            "ts": time.time(),  # W54: float epoch seconds (was strftime ISO-8601)
            "_writer": "dlq_autopilot",  # D1.5: audit trail
        }))

        # UNCONDITIONAL organism heartbeat sidecar (2026-06-28): this script READ
        # ~/.organism/last_seen/ for recovery signals but never WROTE its own, so
        # pro.dlq_autopilot.json froze for 28 days while the cron ran green. The
        # bridge used to refresh it and stopped; now the organ breathes for itself.
        try:
            ORGANISM_DIR.mkdir(parents=True, exist_ok=True)
            organ_path = ORGANISM_DIR / "pro.dlq_autopilot.json"
            organ_tmp = organ_path.with_suffix(f".json.tmp.{os.getpid()}")
            organ_tmp.write_text(json.dumps({
                "ts": time.time(),
                "status": "ok",
                "organ_id": "pro.dlq_autopilot",
                "metadata": {
                    "queue_size": len(queue),
                    "fixed": fixed,
                    "escalated": escalated,
                    "skipped": skipped,
                    "duration_s": round(duration, 1),
                },
            }))
            organ_tmp.replace(organ_path)
        except Exception as exc:  # noqa: BLE001 — heartbeat must never break the run
            logger.warning(f"organ heartbeat emit failed: {exc}")

    finally:
        release_lock(fd)


def requeue_terminal(job_id: str) -> int:
    """W70 (2026-06-12): re-arm a TERMINAL DLQ entry for one more diagnostic pass.

    Twin of `clear`, but instead of removing the entry it resets it to a
    non-terminal, fresh state so process_entry() will actually reason about it
    again on the next autopilot tick:
      - status: TERMINAL -> active (key removed; absence == active)
      - autopilot_attempts: -> 0 (so the max-attempts guard doesn't re-TERMINAL it)
      - first_abandoned_at: -> removed (clean re-entry timestamp on next abandon)

    This is the manual companion to Fix #1 (cron-wrapper now captures real
    stderr): requeue lets a job that went TERMINAL while error_summary was BLIND
    get a real diagnostic pass now that the signal is meaningful.

    Does NOT touch the W61 preserve-terminal logic on the add/process path —
    this is an explicit operator-driven requeue only. Same atomic tmp+replace
    (save_dlq) and the same dlq_autopilot.lock as the autopilot itself, so a
    concurrent autopilot tick can't interleave a half-written queue.

    Returns 0 on success, 1 if no matching TERMINAL entry, 2 if lock busy.
    """
    fd = acquire_lock()
    if fd is None:
        print("Could not acquire lock (autopilot running?) — try again shortly")
        return 2
    try:
        queue = load_dlq()
        matched = 0
        for entry in queue:
            if entry.get("job") == job_id and entry.get("status") == "TERMINAL":
                entry.pop("status", None)          # absence == active (non-terminal)
                entry["autopilot_attempts"] = 0    # fresh attempt budget
                entry.pop("first_abandoned_at", None)
                entry["requeued_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                entry["requeued_by"] = "operator"
                matched += 1
        if matched == 0:
            print(f"No TERMINAL entry found for '{job_id}' in DLQ")
            return 1
        save_dlq(queue)
        print(
            f"Requeued {matched} TERMINAL entry/entries for '{job_id}' "
            f"(status cleared, autopilot_attempts=0) — will get a diagnostic pass next tick"
        )
        logger.info(
            f"dlq_requeue_manual: {job_id} re-armed from TERMINAL by operator "
            f"({matched} entry/entries)"
        )
        return 0
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
    elif len(sys.argv) >= 3 and sys.argv[1] == "requeue":
        sys.exit(requeue_terminal(sys.argv[2]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "sweep":
        _q = load_dlq()
        _kept, _cleared = sweep_recovered_corpses(_q)
        if _cleared:
            save_dlq(_kept)
        print(f"corpse-sweep: cleared {len(_cleared)} recovered entries: {_cleared}")
        print(f"remaining: {len(_kept)}")
    else:
        run_autopilot()
