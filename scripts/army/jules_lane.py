#!/usr/bin/env python3
"""scripts/army/jules_lane.py — Armata H24 lane 2: queued dispatch + harvest
for Jules (Google's async cloud implementer, `scripts/jules_dispatch.py`).

Born 2026-08-14. Jules was armed 2026-07-06 ("coinvolgilo attivamente nel
workflow, senza teatro") and has been dormant since: zero automation has
called it. Quota is ~300 sessions/day — the real constraint was always
verification bandwidth, not dispatch volume. This lane turns the arm into a
standing, capped, two-mode cron: `--dispatch` puts new tasks in flight,
`--harvest` polls open sessions and hands COMPLETED ones to an interactive
session for independent verification. It never verifies, lands, or merges
anything itself.

Contract (unchanged from docs/runbooks/jules-dispatch.md — this lane is a
scheduler around that contract, not a replacement for it):
    "Jules generates; Fable grades." This tool dispatches and reads state.
    It can never merge, push to main, or approve its own output.

Design rationale, cicatrix-superscar.md constraints, and the Phase 2 plan
live in research/operations/2026-08-14-armata-h24-standing-lanes.md.

Modes:
    jules_lane.py --dispatch   [tick 09:00 WITA] up to ARMY_JULES_DAILY_CAP
                                (default 3) new tasks/day from
                                infra/army/jules-queue/*.md.
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
                                verify).

Credential: macOS Keychain item `jules-api-key`, same as jules_dispatch.py.
This lane NEVER reads or copies the key's value — it only probes presence
(`security find-generic-password -s jules-api-key`, no `-w`) before
shelling out to jules_dispatch.py, which resolves the credential itself.
If the key is absent on this machine (true today on Pro — the key lives in
M5's Keychain only), the lane reports status=blocked and does nothing else.
That is an expected, not exceptional, condition until the operator
provisions the key on the target machine — see the design doc's
proof-of-armed table.

Exit codes: always 0 on a normal tick (success, no-op, blocked, quota-
backoff, and per-task failures are all "handled", not crashes) — this
mirrors scripts/army/spark_lane.sh and the repo's pro-healer.sh /
mini-fleet-watch.sh wrapper convention: the wrapper OWNS alerting via
tg_notify.py and the heartbeat sidecar, so cron-runner.sh's own P0 stays
reserved for a genuine wrapper-level crash (uncaught exception -> exit 1).
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


def telegram(paths: Paths, tier: str, dedup_key: str, text: str) -> None:
    """The ONE gateway. Never a raw curl, never a hardcoded token."""
    gateway = paths.repo / "scripts" / "tg_notify.py"
    if not gateway.is_file():
        logger.warning("NO GATEWAY at %s — alert NOT sent: %s", gateway, text[:80])
        return
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
            logger.info("tg_notify[%s]: rc=%s %s", dedup_key, proc.returncode,
                        (proc.stdout or proc.stderr).strip()[-200:])
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("tg_notify invocation failed: %s", exc)
            return
    logger.warning("no python3 found — alert NOT sent: %s", text[:80])


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


# --------------------------------------------------------------- escalations
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


def _session_id(session: str) -> str:
    return session.split("/", 1)[1] if "/" in session else session


# --------------------------------------------------------------- dispatch
def cmd_dispatch(paths: Paths) -> str:
    """Returns the heartbeat status for this tick."""
    daily_cap = _env_int("ARMY_JULES_DAILY_CAP", 3)
    today = time.strftime("%Y-%m-%d")
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
        })
        done_keys.add(key)
        with dispatched_list.open("a", encoding="utf-8") as fh:
            fh.write(key + "\n")
        logger.info("dispatched %s -> %s", task_file.name, session_name)

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

    outcome = "ok"
    changed = False
    for s in open_sessions:
        session = s.get("session", "")
        if not session:
            continue
        rc, out, err = run_jules_dispatch(paths, ["status", session, "--json"])
        if rc != 0:
            logger.warning("status check failed rc=%s for %s: %s — leaving open", rc, session, err[:200])
            outcome = "degraded" if outcome == "ok" else outcome
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            logger.warning("non-JSON status response for %s — leaving open", session)
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
        # else: still in progress — leave open, no action.

    if changed:
        save_jsonl(sessions_file, sessions)
    return outcome


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

    # G5 kill switch
    if os.environ.get("ARMY_JULES_ENABLED", "true").lower() == "false":
        logger.info("kill switch ARMY_JULES_ENABLED=false — exiting")
        heartbeat(paths, "disabled", "kill switch")
        return 0

    # G4 node guard
    ok, node = node_ok()
    if not ok:
        logger.info("node guard: %s is not the required node — exiting", node)
        heartbeat(paths, "disabled", f"wrong-node {node}")
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
            return 0

    # credential presence — never copy the key, only probe it
    if not credential_present():
        logger.info("jules-api-key not resolvable on this machine — blocked")
        telegram(paths, "digest", "army-jules:blocked-no-credential",
                 "🔑 army.jules_lane: jules-api-key non presente su questa macchina — "
                 "lane bloccata (attesa provisioning Keychain, mai copiata a mano).")
        heartbeat(paths, "disabled", "blocked: credential not present on this machine")
        return 0

    pidfile = _env_path(f"ARMY_JULES_PIDFILE_{mode_name.upper()}", paths.state_dir / f"{mode_name}.pid")
    with SingleInstance(pidfile) as lock:
        if not lock.acquired:
            logger.info("previous %s run still alive — skipping", mode_name)
            heartbeat(paths, "ok", f"skipped: previous {mode_name} run alive")
            return 0

        try:
            status = cmd_dispatch(paths) if args.dispatch else cmd_harvest(paths)
        except Exception as exc:  # noqa: BLE001 — a genuine bug: fail visible, not silent
            logger.exception("unexpected failure in %s", mode_name)
            heartbeat(paths, "error", f"{mode_name} crashed: {exc}")
            return 1

    heartbeat(paths, status, f"{mode_name} tick done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
