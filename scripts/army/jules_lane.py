#!/usr/bin/env python3
"""scripts/army/jules_lane.py — Armata H24 lane 2: queued dispatch + harvest
for Jules (Google's async cloud implementer, `scripts/jules_dispatch.py`).

Born 2026-08-14, amended same day after a cross-family Kimi K3 refutation of
the design closed 10 numbered defects (see
research/operations/2026-08-14-armata-h24-standing-lanes.md for the full
rationale and the amendment log). Jules was armed 2026-07-06 ("coinvolgilo
attivamente nel workflow, senza teatro") and has been dormant since: zero
automation has called it. Quota is ~300 sessions/day — the real constraint
was always verification bandwidth, not dispatch volume. This lane turns the
arm into a standing, capped, two-mode cron: `--dispatch` puts new tasks in
flight, `--harvest` polls open sessions and hands COMPLETED ones to an
interactive session for independent verification. It never verifies, lands,
or merges anything itself.

Contract (unchanged from docs/runbooks/jules-dispatch.md — this lane is a
scheduler around that contract, not a replacement for it):
    "Jules generates; Fable grades." This tool dispatches and reads state.
    It can never merge, push to main, or approve its own output.

Modes:
    jules_lane.py --dispatch   [tick 09:00 WITA] up to ARMY_JULES_DAILY_CAP
                                (default 3) new tasks/day from
                                infra/army/jules-queue/*.md. Refuses to
                                dispatch (backpressure, item 9) while
                                ARMY_JULES_INBOX_BACKPRESSURE (default 6)
                                or more harvested patches are still awaiting
                                verification — the bottleneck is
                                verification bandwidth, not dispatch, so
                                dispatch adapts to it rather than piling on.
    jules_lane.py --harvest    [tick every 3h] polls every session recorded
                                as still open; on COMPLETED, downloads the
                                patch evidence to
                                ~/army/jules/inbox/<session-id>/ and appends
                                ONE NORMAL-priority row to
                                shared/escalations_pro.jsonl (via the
                                existing single-writer
                                scripts/sentinel_lib/escalations.py, never a
                                hand-rolled JSONL append) so an interactive
                                session picks it up; on FAILED, a receipt +
                                digest, no escalation (there is no patch to
                                verify). A session PENDING for more than
                                ARMY_JULES_SESSION_TTL_HOURS (default 72) is
                                marked stale, gets exactly ONE escalation of
                                its own, and is never polled again (item 7).

Credential: macOS Keychain item `jules-api-key`, same as jules_dispatch.py.
This lane NEVER reads or copies the key's value — it only probes presence
(`security find-generic-password -s jules-api-key`, no `-w`) before
shelling out to jules_dispatch.py, which resolves the credential itself.
If the key is absent on this machine (true today on Pro — the key lives in
M5's Keychain only), the lane reports status=blocked and does nothing else.
That is an expected, not exceptional, condition until the operator
provisions the key on the target machine — see the design doc's
proof-of-armed table. Two or more CONSECUTIVE blocked ticks (either mode)
get a distinct digest line (item 10) — a forgotten credential should not
silently degrade to "not applicable" forever.

Exit codes: always 0 on a normal tick (success, no-op, blocked, quota-
backoff, and per-task failures are all "handled", not crashes) — this
mirrors scripts/army/spark_lane.sh and the repo's pro-healer.sh /
mini-fleet-watch.sh wrapper convention: the wrapper OWNS alerting via
tg_notify.py and the heartbeat sidecar, so cron-runner.sh's own P0 stays
reserved for a genuine wrapper-level crash (uncaught exception -> exit 1).

WITA day-boundary discipline: every "today"/"day cap"/"digest hour"
computation in this file goes through `wita_now()` (a fixed UTC+8 offset —
Asia/Makassar carries no DST, so this needs no zoneinfo/tzdata dependency)
rather than `time.strftime()` against ambient system/launchd TZ, which is
not guaranteed to be WITA on every machine/cron environment. Applying this
to only one of the two Armata H24 lanes would be a half-fix (cicatrix
family #9/#2 discipline: a cure that only covers the phase that bit you is
half a cure) — see scripts/army/spark_lane.sh for the bash-side twin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# tg_gateway_verdict lives at the repo root's scripts/ package, not
# relative to this file's own directory (scripts/army/) — resolve from
# __file__, not from Paths.repo, which is env-overridable for test
# fixtures and must not decide where our OWN source tree is
# (scripts/tests/test_gateway_callers_read_the_verdict.py: tg_notify.py
# exits 0 on three "not delivered now" outcomes too, so a caller that
# never parses the verdict cannot tell a page from a swallowed alert).
_REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORTS))

from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

ORGAN_ID = "army.jules_lane"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("army.jules_lane")

QUOTA_MARKERS_RE = re.compile(
    r"out of extra usage|usage limit|quota exceeded|rate.limit|429|"
    r"resource_exhausted|weekly limit",
    re.IGNORECASE,
)
COMPLETED_MARKERS_RE = re.compile(r"complet", re.IGNORECASE)
FAILED_MARKERS_RE = re.compile(r"fail|error|cancel", re.IGNORECASE)

WITA_OFFSET_SECONDS = 8 * 3600  # Asia/Makassar, fixed UTC+8, no DST


def wita_now() -> time.struct_time:
    """WITA "now" as a struct_time, computed from UTC — no zoneinfo/tzdata
    dependency (see module docstring)."""
    return time.gmtime(time.time() + WITA_OFFSET_SECONDS)


def wita_today() -> str:
    return time.strftime("%Y-%m-%d", wita_now())


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else default


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


class Paths:
    """All paths are env-overridable so tests fixture a fake world — same
    pattern as tg_notify.py / organism_digest.py in this repo."""

    def __init__(self) -> None:
        self.repo = _env_path("ARMY_JULES_REPO", Path.home() / "nuzantara")
        self.queue_dir = _env_path(
            "ARMY_JULES_QUEUE_DIR", self.repo / "infra" / "army" / "jules-queue"
        )
        self.inbox_dir = _env_path("ARMY_JULES_INBOX_DIR", Path.home() / "army" / "jules" / "inbox")
        self.state_dir = _env_path("ARMY_JULES_STATE_DIR", Path.home() / "army" / "jules" / "state")
        self.log_dir = _env_path("ARMY_JULES_LOG_DIR", Path.home() / "logs" / "army-jules")
        self.sidecar_dir = _env_path(
            "ARMY_JULES_SIDECAR_DIR", Path.home() / ".organism" / "last_seen"
        )
        self.dispatch_script = _env_path(
            "ARMY_JULES_DISPATCH_SCRIPT", self.repo / "scripts" / "jules_dispatch.py"
        )

    def ensure(self) -> None:
        for d in (self.queue_dir, self.inbox_dir, self.state_dir, self.log_dir, self.sidecar_dir):
            d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------- heartbeat
def heartbeat(paths: Paths, status: str, note: str) -> None:
    """Sidecar every exit path (Esiste≠Armato: prove life, every run).

    Best-effort: a heartbeat failure must never break the caller.
    """
    try:
        paths.sidecar_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "note": note[:500],
        }
        tmp = paths.sidecar_dir / f"{ORGAN_ID}.json.tmp.{os.getpid()}"
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        tmp.replace(paths.sidecar_dir / f"{ORGAN_ID}.json")
    except Exception as exc:  # noqa: BLE001 — heartbeat must never crash the caller
        logger.warning("heartbeat write failed (non-fatal): %s", exc)


def telegram(paths: Paths, tier: str, dedup_key: str, text: str) -> str | None:
    """The ONE gateway. Never a raw curl, never a hardcoded token.

    Returns the gateway's parsed verdict (scripts/tg_gateway_verdict.py) —
    one of the six canonical outcomes tg_notify.py exits 0 on, only one of
    which ("sent") is a real-time delivery. The old version here logged
    `proc.returncode` and moved on, which reads deduped/spooled/
    p0_overflow_spooled/p0_unsent_spooled — all exit 0 — as a delivery
    (W104; scripts/tests/test_gateway_callers_read_the_verdict.py, the
    class guard that caught this file). This lane doesn't currently branch
    dispatch/harvest logic on the verdict, but it no longer misreports
    "the subprocess ran" as "the owner got paged".
    """
    gateway = paths.repo / "scripts" / "tg_notify.py"
    if not gateway.is_file():
        logger.warning("NO GATEWAY at %s — alert NOT sent: %s", gateway, text[:80])
        return None
    for py in ("/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "python3"):
        exe = py if py.startswith("/") else _which(py)
        if not exe:
            continue
        try:
            proc = subprocess.run(
                [exe, str(gateway), "--tier", tier, "--source", "army-jules-lane",
                 "--dedup-key", dedup_key, "--", text],
                capture_output=True, text=True, timeout=30, check=False,
            )
            verdict = extract_gateway_verdict(proc.stderr)
            if verdict is None:
                logger.warning(
                    "tg_notify[%s]: rc=%s — no canonical verdict line found, "
                    "treating as NOT delivered: %s",
                    dedup_key, proc.returncode, (proc.stdout or proc.stderr).strip()[-200:],
                )
            elif gateway_delivered(verdict):
                logger.info("tg_notify: %s [%s]", verdict, dedup_key)
            else:
                logger.info(
                    "tg_notify: %s [%s] — not a real-time delivery (rc=%s means the "
                    "process ran, not that Telegram got it)",
                    verdict, dedup_key, proc.returncode,
                )
            return verdict
        except Exception as exc:  # noqa: BLE001
            logger.warning("tg_notify invocation failed: %s", exc)
            return None
    logger.warning("no python3 found — alert NOT sent: %s", text[:80])
    return None


def _which(name: str) -> str | None:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(p) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


# --------------------------------------------------------------- credential
def credential_present() -> bool:
    """True iff the Jules API key is resolvable on THIS machine.

    Never reads the value — `security find-generic-password` without `-w`
    only proves existence. jules_dispatch.py resolves the actual value
    itself when we shell out to it; this lane never touches it.
    """
    if os.environ.get("JULES_API_KEY", "").strip():
        return True
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", "jules-api-key"],
            capture_output=True, timeout=10, check=False,
        )
        return proc.returncode == 0
    except Exception:
        return False


# --------------------------------------------------------------- node guard
def node_ok(required_node: str | None = None) -> tuple[bool, str]:
    node = os.environ.get("ARMY_JULES_NODE_OVERRIDE", "").strip().lower()
    if not node:
        try:
            proc = subprocess.run(["hostname", "-s"], capture_output=True, text=True,
                                   timeout=5, check=False)
            node = proc.stdout.strip().lower()
        except Exception:
            node = "unknown"
    required = (required_node or os.environ.get("ARMY_JULES_REQUIRED_NODE", "nuzantara")).lower()
    return node == required, node


# --------------------------------------------------------------- pidfile
class SingleInstance:
    def __init__(self, pidfile: Path) -> None:
        self.pidfile = pidfile
        self.acquired = False

    def __enter__(self) -> "SingleInstance":
        if self.pidfile.is_file():
            try:
                pid = int(self.pidfile.read_text().strip())
                os.kill(pid, 0)  # raises if not alive
                return self  # previous run still alive — caller checks .acquired
            except (ValueError, ProcessLookupError, PermissionError):
                pass
            except OSError:
                pass
        self.pidfile.parent.mkdir(parents=True, exist_ok=True)
        self.pidfile.write_text(str(os.getpid()))
        self.acquired = True
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.acquired:
            try:
                self.pidfile.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------- helpers
def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "task"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("skipping malformed sessions.jsonl line: %s", line[:120])
    return out


def save_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


def run_jules_dispatch(paths: Paths, args: list[str], timeout_s: int = 120) -> tuple[int, str, str]:
    cmd = [sys.executable, str(paths.dispatch_script), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        return 124, "", f"timeout after {timeout_s}s: {exc}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", f"{type(exc).__name__}: {exc}"


def _origin_main_head(paths: Paths) -> str:
    """Item 10: base commit recorded per dispatch tick so a later
    verification session can `git apply --check` the harvested patch
    against the commit Jules actually started from, not whatever HEAD
    happens to be when they get around to it."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(paths.repo), "rev-parse", "origin/main"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not resolve origin/main HEAD: %s", exc)
    return ""


# --------------------------------------------------------------- escalations
def escalation_already_exists(paths: Paths, job_key: str) -> bool:
    """Item 8: dedup safety net. The primary guard is in-process (a closed
    session is never re-polled — see cmd_harvest), which already makes a
    duplicate escalation for the SAME tick impossible. This grep-based check
    catches the crash-consistency gap instead: an escalation write that
    succeeded followed by a session-state save that did not land (process
    killed between the two) would otherwise re-fire the same escalation on
    the next tick. Read failures degrade to False — the primary in-process
    dedup still holds in the common case, and this must never be the reason
    a genuinely new escalation goes unwritten.
    """
    needle_a = f'"job": "{job_key}"'
    needle_b = f'"job":"{job_key}"'
    p = paths.repo / "shared" / "escalations_pro.jsonl"
    if not p.is_file():
        return False
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("escalation_already_exists: could not read %s (%s) — treating as not-found", p, exc)
        return False
    return needle_a in text or needle_b in text


def write_jules_escalation(paths: Paths, *, session: str, title: str, task_file: str,
                            inbox_path: Path) -> bool:
    """Append ONE NORMAL-priority row to shared/escalations_pro.jsonl via the
    repo's own single-writer module. Returns True on success; False falls
    back to a local-only receipt (never crashes the harvest tick — a missed
    escalation is visible via the inbox dir + daily digest regardless).
    """
    scripts_dir = str(paths.repo / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from sentinel_lib.escalations import write_escalation  # type: ignore
    except ImportError as exc:
        logger.warning("sentinel_lib.escalations not importable (%s) — "
                        "escalation NOT written, inbox artifact still present", exc)
        return False
    try:
        write_escalation({
            "job": f"jules-patch-{_session_id(session)}",
            "type": "jules_dispatch_completed",
            "source": "army-jules-lane",
            "priority": "NORMAL",
            "test_cmd": None,
            "description": f"Jules patch ready for independent verification: "
                            f"{title} — {inbox_path}",
            "session": session,
            "task_file": task_file,
            "inbox_path": str(inbox_path),
        })
        return True
    except Exception as exc:  # noqa: BLE001 — escalation failure must not crash harvest
        logger.warning("write_escalation failed (non-fatal): %s", exc)
        return False


def write_jules_stale_escalation(paths: Paths, *, session: str, title: str, task_file: str,
                                  age_hours: float) -> bool:
    """Item 7: a session PENDING past the TTL gets exactly ONE escalation of
    its own — there is no patch to verify, so this is an "investigate or
    cancel" prompt, not a "verify this" prompt. Same single-writer module,
    same non-fatal-failure discipline as write_jules_escalation."""
    scripts_dir = str(paths.repo / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from sentinel_lib.escalations import write_escalation  # type: ignore
    except ImportError as exc:
        logger.warning("sentinel_lib.escalations not importable (%s) — "
                        "stale escalation NOT written", exc)
        return False
    try:
        write_escalation({
            "job": f"jules-stale-{_session_id(session)}",
            "type": "jules_session_stale",
            "source": "army-jules-lane",
            "priority": "NORMAL",
            "test_cmd": None,
            "description": f"Jules session stalled >{age_hours:.0f}h with no "
                            f"COMPLETED/FAILED state — investigate or cancel: "
                            f"{title} (session {session}, task {task_file})",
            "session": session,
            "task_file": task_file,
        })
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("write_escalation (stale) failed (non-fatal): %s", exc)
        return False


def _session_id(session: str) -> str:
    return session.split("/", 1)[1] if "/" in session else session


# --------------------------------------------------------------- backpressure
def count_pending_verification(paths: Paths) -> int:
    """Item 9/12: sessions harvested as COMPLETED whose `outcome` a
    verification session has not yet set to applied/rejected/read. This is
    the inbox backlog the dispatcher backs off against, and the number the
    daily digest reports."""
    sessions = load_jsonl(paths.state_dir / "sessions.jsonl")
    return sum(
        1 for s in sessions
        if s.get("closed_reason") == "completed"
        and s.get("outcome") not in ("applied", "rejected", "read")
    )


def count_produced_and_consumed(paths: Paths) -> tuple[int, int]:
    """Item 12: weekly digest "produced vs consumed" ratio. produced =
    every session ever harvested as COMPLETED (a patch was produced);
    consumed = the subset a verification session has since annotated."""
    sessions = load_jsonl(paths.state_dir / "sessions.jsonl")
    produced = sum(1 for s in sessions if s.get("closed_reason") == "completed")
    consumed = sum(
        1 for s in sessions
        if s.get("closed_reason") == "completed" and s.get("outcome") in ("applied", "rejected", "read")
    )
    return produced, consumed


# --------------------------------------------------------------- blocked streak
def _blocked_streak_file(paths: Paths) -> Path:
    return paths.state_dir / "blocked-streak.txt"


def _record_blocked_tick(paths: Paths) -> int:
    f = _blocked_streak_file(paths)
    n = 0
    if f.is_file():
        try:
            n = int(f.read_text().strip() or "0")
        except ValueError:
            n = 0
    n += 1
    f.write_text(str(n))
    return n


def _reset_blocked_streak(paths: Paths) -> None:
    f = _blocked_streak_file(paths)
    if f.is_file():
        try:
            f.write_text("0")
        except Exception:  # noqa: BLE001
            pass


def _blocked_streak(paths: Paths) -> int:
    f = _blocked_streak_file(paths)
    if not f.is_file():
        return 0
    try:
        return int(f.read_text().strip() or "0")
    except ValueError:
        return 0


# --------------------------------------------------------------- dispatch
def cmd_dispatch(paths: Paths) -> str:
    """Returns the heartbeat status for this tick."""
    inbox_limit = _env_int("ARMY_JULES_INBOX_BACKPRESSURE", 6)
    pending_verification = count_pending_verification(paths)
    if pending_verification >= inbox_limit:
        logger.info(
            "inbox backpressure: %d patch(es) pending verification (limit %d) — "
            "dispatch skipped this tick, verification is the bottleneck, not dispatch",
            pending_verification, inbox_limit,
        )
        return "ok"

    daily_cap = _env_int("ARMY_JULES_DAILY_CAP", 3)
    today = wita_today()
    count_file = paths.state_dir / f"dispatch-count-{today}.txt"
    dispatched_list = paths.state_dir / "dispatched-list.txt"
    sessions_file = paths.state_dir / "sessions.jsonl"

    run_count = 0
    if count_file.is_file():
        try:
            run_count = int(count_file.read_text().strip() or "0")
        except ValueError:
            run_count = 0

    remaining = daily_cap - run_count
    if remaining <= 0:
        logger.info("daily cap reached (%d/%d) — nothing dispatched this tick",
                    run_count, daily_cap)
        return "ok"

    done_keys = set()
    if dispatched_list.is_file():
        done_keys = set(dispatched_list.read_text(encoding="utf-8").splitlines())

    candidates = sorted(
        (f for f in paths.queue_dir.glob("*.md") if f.name.lower() != "readme.md"),
        key=lambda f: f.stat().st_mtime,
    )

    pending = []
    for f in candidates:
        key = f"{f.name}:{sha256_of(f)}"
        if key not in done_keys:
            pending.append((f, key))

    if not pending:
        logger.info("jules queue empty or fully dispatched")
        return "ok"

    sessions = load_jsonl(sessions_file)
    base_commit = _origin_main_head(paths)  # item 10, one resolve per tick
    outcome = "ok"
    for task_file, key in pending[:remaining]:
        title_line = task_file.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip() \
            if task_file.stat().st_size else task_file.stem
        title = title_line or task_file.stem
        prompt = task_file.read_text(encoding="utf-8")
        logger.info("dispatching %s (title=%r)", task_file.name, title)

        rc, out, err = run_jules_dispatch(
            paths, ["new", "--prompt", prompt, "--title", title, "--json"],
        )
        run_count += 1
        count_file.write_text(str(run_count))

        combined = f"{out}\n{err}"
        if rc != 0 and QUOTA_MARKERS_RE.search(combined):
            logger.warning("quota marker on dispatch of %s — stopping this tick's loop", task_file.name)
            backoff_hours = _env_int("ARMY_JULES_BACKOFF_HOURS", 6)
            (paths.state_dir / "backoff-until.txt").write_text(
                str(int(time.time()) + backoff_hours * 3600)
            )
            telegram(paths, "digest", "army-jules:quota",
                     f"🐢 army.jules_lane: quota/rate-limit su dispatch — backoff {backoff_hours}h. "
                     f"Task NON consumato: {task_file.name}")
            outcome = "degraded"
            break

        if rc != 0:
            logger.error("jules_dispatch new failed rc=%s for %s: %s", rc, task_file.name, err[:400])
            telegram(paths, "p0", f"army-jules:dispatch-failed:{task_file.name}",
                     f"🔴 army.jules_lane: dispatch fallito su {task_file.name} (rc={rc}). "
                     f"Err: {err[:300]}")
            outcome = "error" if outcome == "ok" else outcome
            # task NOT marked done — retry eligible tomorrow (cap already spent today)
            continue

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            logger.error("jules_dispatch new returned non-JSON despite --json for %s", task_file.name)
            telegram(paths, "p0", f"army-jules:bad-response:{task_file.name}",
                     f"🔴 army.jules_lane: risposta non-JSON da jules_dispatch new su {task_file.name}")
            outcome = "error" if outcome == "ok" else outcome
            continue

        session_name = data.get("name", "")
        if not session_name:
            logger.error("jules_dispatch new returned no session name for %s: %s", task_file.name, out[:300])
            outcome = "error" if outcome == "ok" else outcome
            continue

        sessions.append({
            "ts": time.time(),
            "session": session_name,
            "task_file": task_file.name,
            "title": title,
            "status": "open",
            "base_commit": base_commit,
        })
        done_keys.add(key)
        with dispatched_list.open("a", encoding="utf-8") as fh:
            fh.write(key + "\n")
        logger.info("dispatched %s -> %s (base_commit=%s)", task_file.name, session_name, base_commit or "?")

    save_jsonl(sessions_file, sessions)
    return outcome


# --------------------------------------------------------------- harvest
def cmd_harvest(paths: Paths) -> str:
    sessions_file = paths.state_dir / "sessions.jsonl"
    sessions = load_jsonl(sessions_file)
    open_sessions = [s for s in sessions if s.get("status") == "open"]

    if not open_sessions:
        logger.info("no open jules sessions to harvest")
        return "ok"

    ttl_hours = _env_int("ARMY_JULES_SESSION_TTL_HOURS", 72)
    now = time.time()

    outcome = "ok"
    changed = False
    for s in open_sessions:
        session = s.get("session", "")
        if not session:
            continue

        age_hours = (now - float(s.get("ts", now))) / 3600.0

        rc, out, err = run_jules_dispatch(paths, ["status", session, "--json"])
        if rc != 0:
            logger.warning("status check failed rc=%s for %s: %s — leaving open", rc, session, err[:200])
            outcome = "degraded" if outcome == "ok" else outcome
            # item 7 still applies even when the status probe itself fails —
            # a session we can never successfully poll is exactly the case
            # the TTL exists to catch, not a reason to exempt it.
            if age_hours > ttl_hours:
                _mark_stale(paths, s, age_hours)
                changed = True
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            logger.warning("non-JSON status response for %s — leaving open", session)
            if age_hours > ttl_hours:
                _mark_stale(paths, s, age_hours)
                changed = True
            continue

        state = str(data.get("state", ""))
        title = data.get("title") or s.get("title") or s.get("task_file", session)

        if COMPLETED_MARKERS_RE.search(state):
            inbox_dir = paths.inbox_dir / _session_id(session)
            inbox_dir.mkdir(parents=True, exist_ok=True)
            (inbox_dir / "status.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

            rc2, out2, err2 = run_jules_dispatch(paths, ["activities", session, "--json"])
            if rc2 == 0:
                try:
                    (inbox_dir / "activities.json").write_text(
                        json.dumps(json.loads(out2), indent=2), encoding="utf-8"
                    )
                except json.JSONDecodeError:
                    (inbox_dir / "activities.raw.txt").write_text(out2, encoding="utf-8")
            else:
                logger.warning("activities fetch failed rc=%s for %s: %s", rc2, session, err2[:200])

            job_key = f"jules-patch-{_session_id(session)}"
            if escalation_already_exists(paths, job_key):
                logger.info("escalation for %s already present in shared/escalations_pro.jsonl "
                            "(item 8 dedup) — not re-writing", job_key)
                escalated = True
            else:
                escalated = write_jules_escalation(
                    paths, session=session, title=title, task_file=s.get("task_file", ""),
                    inbox_path=inbox_dir,
                )
            telegram(paths, "digest", f"army-jules:completed:{_session_id(session)}",
                     f"✅ army.jules_lane: sessione completata — {title}. Inbox: {inbox_dir}"
                     + ("" if escalated else " (escalation NON scritta, vedi log)"))
            s["status"] = "closed"
            s["closed_reason"] = "completed"
            s["closed_ts"] = time.time()
            s["outcome"] = None  # item 12: verification session updates this later
            changed = True
            logger.info("harvested %s -> %s", session, inbox_dir)

        elif FAILED_MARKERS_RE.search(state):
            telegram(paths, "digest", f"army-jules:failed:{_session_id(session)}",
                     f"⚠️ army.jules_lane: sessione fallita — {title} (state={state})")
            s["status"] = "closed"
            s["closed_reason"] = "failed"
            s["closed_ts"] = time.time()
            changed = True
            logger.info("session failed, closed: %s state=%s", session, state)

        elif age_hours > ttl_hours:
            _mark_stale(paths, s, age_hours)
            changed = True
        # else: still in progress, within TTL — leave open, no action.

    if changed:
        save_jsonl(sessions_file, sessions)
    return outcome


def _mark_stale(paths: Paths, s: dict, age_hours: float) -> None:
    """Item 7: PENDING past the TTL — mark stale, fire exactly ONE
    escalation (dedup via item 8's grep, same as the completed path), stop
    polling this session forever (status becomes "closed" so it never
    re-enters open_sessions)."""
    session = s.get("session", "")
    title = s.get("title") or s.get("task_file", session)
    job_key = f"jules-stale-{_session_id(session)}"
    if escalation_already_exists(paths, job_key):
        logger.info("stale escalation for %s already present — not re-writing", job_key)
    else:
        write_jules_stale_escalation(
            paths, session=session, title=title, task_file=s.get("task_file", ""),
            age_hours=age_hours,
        )
    telegram(paths, "digest", f"army-jules:stale:{_session_id(session)}",
             f"⏳ army.jules_lane: sessione PENDING da {age_hours:.0f}h (TTL superata) — "
             f"{title}. Escalation aperta, stop polling.")
    s["status"] = "closed"
    s["closed_reason"] = "stale"
    s["closed_ts"] = time.time()
    logger.info("session stale, closed: %s age=%.1fh", session, age_hours)


# --------------------------------------------------------------- daily digest
def _write_daily_digest_if_due(paths: Paths, current_status: str) -> None:
    """Runs at the END of every tick (dispatch or harvest) that got far
    enough to check, regardless of what that tick actually did — item 11:
    a kill-switch-off tick must still report itself in the digest, not go
    silent because the early-exit skipped the digest block entirely."""
    digest_hour = _env_int("ARMY_JULES_DIGEST_HOUR", 7)
    mark = paths.state_dir / "last-digest-date.txt"
    today = wita_today()
    cur_hour = int(time.strftime("%H", wita_now()))
    last = mark.read_text().strip() if mark.is_file() else ""
    if cur_hour < digest_hour or last == today:
        return

    pending = count_pending_verification(paths)
    lines = [
        f"🌅 army.jules_lane digest ({today}):",
        f"inbox: {pending} patch in attesa di verifica",
    ]
    if current_status == "killed":
        lines.append("⚠️ ARMY_JULES_ENABLED=false — lane disabilitata")
    streak = _blocked_streak(paths)
    if streak >= 2:
        lines.append(f"🔑 {streak} tick consecutivi bloccati per credential assente")

    # item 12: weekly produced/consumed rollup, folded into the same daily
    # send on Mondays rather than standing up a second schedule.
    if time.strftime("%u", wita_now()) == "1":
        produced, consumed = count_produced_and_consumed(paths)
        lines.append(f"📊 settimanale: {produced} patch prodotte, {consumed} verificate")

    telegram(paths, "digest", f"army-jules:daily-digest:{today}", " | ".join(lines))
    try:
        mark.write_text(today)
    except Exception as exc:  # noqa: BLE001 — a missed mark just re-sends tomorrow's check
        logger.warning("could not write digest date-mark (non-fatal): %s", exc)


# --------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dispatch", action="store_true")
    mode.add_argument("--harvest", action="store_true")
    args = parser.parse_args(argv)
    mode_name = "dispatch" if args.dispatch else "harvest"

    paths = Paths()
    paths.ensure()

    # G4 node guard — not my machine, not my problem: no digest either (a
    # machine that isn't supposed to run this lane shouldn't be the one
    # reporting on it).
    ok, node = node_ok()
    if not ok:
        logger.info("node guard: %s is not the required node — exiting", node)
        heartbeat(paths, "disabled", f"wrong-node {node}")
        return 0

    rich_status = "ok"  # own vocabulary, richer than heartbeat's normalized set

    # G5 kill switch
    if os.environ.get("ARMY_JULES_ENABLED", "true").lower() == "false":
        logger.info("kill switch ARMY_JULES_ENABLED=false — exiting")
        rich_status = "killed"
        heartbeat(paths, "disabled", "kill switch")
        _write_daily_digest_if_due(paths, rich_status)
        return 0

    # backoff (shared across both modes — a quota condition affects both)
    backoff_file = paths.state_dir / "backoff-until.txt"
    if backoff_file.is_file():
        try:
            backoff_until = int(backoff_file.read_text().strip() or "0")
        except ValueError:
            backoff_until = 0
        if backoff_until > time.time():
            logger.info("backoff active until epoch %s — skipping %s this tick",
                        backoff_until, mode_name)
            heartbeat(paths, "degraded", f"backoff active until {backoff_until}")
            _write_daily_digest_if_due(paths, "backoff")
            return 0

    # credential presence — never copy the key, only probe it
    if not credential_present():
        logger.info("jules-api-key not resolvable on this machine — blocked")
        n_blocked = _record_blocked_tick(paths)
        telegram(paths, "digest", "army-jules:blocked-no-credential",
                 "🔑 army.jules_lane: jules-api-key non presente su questa macchina — "
                 "lane bloccata (attesa provisioning Keychain, mai copiata a mano).")
        if n_blocked >= 2:  # item 10: distinct streak alarm, not a silent repeat receipt
            telegram(paths, "digest", "army-jules:blocked-streak",
                     f"🔑🔑 army.jules_lane: {n_blocked} tick consecutivi bloccati per "
                     f"credential assente — non è un blip isolato.")
        heartbeat(paths, "disabled", "blocked: credential not present on this machine")
        _write_daily_digest_if_due(paths, "blocked")
        return 0

    _reset_blocked_streak(paths)  # credential present this tick — streak broken

    pidfile = _env_path(f"ARMY_JULES_PIDFILE_{mode_name.upper()}", paths.state_dir / f"{mode_name}.pid")
    with SingleInstance(pidfile) as lock:
        if not lock.acquired:
            logger.info("previous %s run still alive — skipping", mode_name)
            heartbeat(paths, "ok", f"skipped-overlap: previous {mode_name} run alive")
            _write_daily_digest_if_due(paths, "skipped-overlap")
            return 0

        try:
            status = cmd_dispatch(paths) if args.dispatch else cmd_harvest(paths)
        except Exception as exc:  # noqa: BLE001 — a genuine bug: fail visible, not silent
            logger.exception("unexpected failure in %s", mode_name)
            heartbeat(paths, "error", f"{mode_name} crashed: {exc}")
            _write_daily_digest_if_due(paths, "error")
            return 1

    heartbeat(paths, status, f"{mode_name} tick done")
    _write_daily_digest_if_due(paths, status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
