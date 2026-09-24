#!/usr/bin/env python3
"""nlm_watchdog.py — M5 organ that checks, over ssh to Pro, the NotebookLM layer the
ingestion pipelines on Pro depend on, and records the verdict where M5's SessionStart digest
(scripts/organism_digest.py) reads it. ~/.organism/ is per-host, so the prober runs on M5.

One tick (scripts/nlm_watchdog_cron.sh, launchd StartInterval 21600s) runs three checks:
  (a) Pro's `~/.local/bin/nlm login --check` (Pro's cookie, not M5's);
  (b) each notebook's `source_count` in Pro's daily inventory
      (~/nuzantara/research/nb-health/nb-inventory-live.json, written by
      scripts/nb_generate_inventory.py) against --cap-warn (default 450). The account's
      per-notebook cap is 500 (Google plan table, checked 2026-09-25); the heartbeat's
      `max_source_count` is the value to re-check it against;
  (c) the inventory's `generated_at` is younger than --stale-hours (default 30).
If auth_sentinel cannot be imported, the tick skips (a)-(c) and reports `import_failed`.

Output: ~/.organism/last_seen/nlm-watchdog.json, replaced atomically on every tick:
`status` (ok|degraded), `codes`, the inventory figures when it was read (`max_source_count`,
`notebook_count`, `inventory_age_h`, `near_cap_ids`), and on degraded `note`/`last_error`.
Telegram (scripts/tg_notify.py) is secondary: a send is attempted when status, codes or
near_cap_ids differ from the previous heartbeat, except on a first tick that is ok; its
outcome never changes the exit code.

Boundary: raw CLI output stays inside classify_login(); notebooks are named only by the first
8 characters of their id, never by title; failure reasons carry only an exception type name.

Usage:
    python3 scripts/nlm_watchdog.py                              # one tick
    python3 scripts/nlm_watchdog.py --cap-warn 400 --dry-run      # probe + print, no side effects

Exit: 0 ok; 1 degraded, or the heartbeat could not be written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def _run(cmd: list[str] | str, timeout: int = 30, shell: bool = False,
         env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run a command and never raise. Returns (rc, stdout+stderr);
    TimeoutExpired -> (124, "TIMEOUT"), FileNotFoundError -> (127, "NOT_FOUND"),
    any other exception -> (1, its type name). Defined here rather than imported,
    so ssh probes and Telegram sends work even when auth_sentinel cannot be
    imported."""
    try:
        p = subprocess.run(
            cmd, shell=shell, timeout=timeout,
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, env=env,
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except FileNotFoundError:
        return 127, "NOT_FOUND"
    except Exception as e:  # noqa: BLE001 — must never crash the caller
        return 1, type(e).__name__


# From auth_sentinel: its auth-dead regex (one shared judgement of what a dead cookie looks
# like) and _hostname. If the import fails, main() reports import_failed without probing and
# _hostname falls back to socket.gethostname().
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from auth_sentinel import _AUTH_DEAD_RE, _hostname
    AUTH_SENTINEL_IMPORT_ERROR: str | None = None
except Exception as _imp_exc:  # noqa: BLE001 — see comment above; must never propagate
    AUTH_SENTINEL_IMPORT_ERROR = type(_imp_exc).__name__
    _AUTH_DEAD_RE = re.compile(r"(?!)")  # matches nothing; unreachable when the guard trips

    def _hostname() -> str:  # type: ignore[no-redef]
        import socket
        return socket.gethostname().split(".")[0]

HOME = Path.home()
REPO = Path(__file__).resolve().parents[1]

HEARTBEAT_PATH = HOME / ".organism" / "last_seen" / "nlm-watchdog.json"
TG_NOTIFY = REPO / "scripts" / "tg_notify.py"

DEFAULT_CAP_WARN = 450
DEFAULT_STALE_HOURS = 30.0
DEFAULT_INVENTORY_RETRY_DELAY_S = 5.0
FUTURE_SKEW_TOLERANCE_MIN = 10
SSH_CONNECT_TIMEOUT = 15
SSH_TIMEOUT = 40

PRO_NLM_BIN = "~/.local/bin/nlm"
# Canonical checkout on Pro (verified 2026-09-25: ~/Desktop/nuzantara is a symlink to this;
# nb-curator-daily.sh's own plist invokes the script from here, so this is where
# nb_generate_inventory.py actually writes — not the symlink).
PRO_INVENTORY_PATH = "~/nuzantara/research/nb-health/nb-inventory-live.json"

MAX_REASON_LEN = 500


class Code:
    """Stable, comparable reason codes — the alert-transition key, never the
    free-text `reasons` (which changes on every count/hour fluctuation)."""
    LOGIN_DEAD = "login_dead"
    LOGIN_UNKNOWN = "login_unknown"
    CAP_NEAR = "cap_near"
    INVENTORY_MISSING = "inventory_missing"
    INVENTORY_MALFORMED = "inventory_malformed"
    INVENTORY_STALE = "inventory_stale"
    INVENTORY_TIMESTAMP_INVALID = "inventory_timestamp_invalid"
    IMPORT_FAILED = "import_failed"
    CRASHED = "crashed"


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    codes: set[str] = field(default_factory=set)
    ctx: dict = field(default_factory=dict)


# --- PII-boundary helper (unit-testable, no I/O) ----------------------------

def _display_name(nb_id: object) -> str:
    """First 8 characters of the notebook id, or "unknown". Titles are never
    shown: a title can carry a client name."""
    i = str(nb_id or "")
    return i[:8] if i else "unknown"


# --- pure classification (unit-testable, no I/O) ---------------------------

# Word-bounded: "Authentication invalid" must never read as valid.
_SUCCESS_RE = re.compile(r"\bauthentication\s+valid\b", re.I)
# auth_sentinel's _AUTH_DEAD_RE covers `invalid_grant` but not a bare `invalid`.
_INVALID_RE = re.compile(r"\binvalid\b", re.I)


def classify_login(rc: int, out: str) -> tuple[bool, str, str | None]:
    """Classify Pro's `nlm login --check`. Dead markers are checked before the
    success sentinel. Returns (ok, reason, code); code is None iff ok. The
    reason is fixed text, never `out`."""
    if _AUTH_DEAD_RE.search(out) or _INVALID_RE.search(out) or "expired" in out.lower():
        return False, "pro nlm login dead (run `nlm login --clear` on Pro interactively)", Code.LOGIN_DEAD
    if rc == 0 and _SUCCESS_RE.search(out):
        return True, "", None
    # Anything not confirmed valid (timeout, ssh failure, unknown text) degrades.
    return False, "pro nlm login unknown/unreachable (ssh or nlm probe did not confirm valid)", Code.LOGIN_UNKNOWN


def _try_parse_inventory(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def evaluate_inventory_data(
    data: dict, cap_warn: int, stale_hours: float, now: datetime
) -> tuple[bool, list[str], dict, set[str]]:
    """Pure logic over the ALREADY-PARSED daily inventory produced by
    scripts/nb_generate_inventory.py on Pro. Returns (ok, reasons, ctx, codes)."""
    reasons: list[str] = []
    codes: set[str] = set()
    ctx: dict = {}

    notebooks = data.get("notebooks")
    if not isinstance(notebooks, list):
        reasons.append("nb-inventory-live.json has no 'notebooks' list")
        codes.add(Code.INVENTORY_MALFORMED)
        notebooks = []

    near_entries: list[tuple[str, int | float]] = []
    max_count = 0
    bad_count_n = 0
    for nb in notebooks:
        if not isinstance(nb, dict):
            continue
        count = nb.get("source_count")
        # A non-numeric count (JSON true/false included) is skipped and reported,
        # so it cannot crash the tick and discard the login verdict.
        if isinstance(count, bool) or not isinstance(count, (int, float)):
            bad_count_n += 1
            continue
        max_count = max(max_count, count)
        if count >= cap_warn:
            near_entries.append((_display_name(nb.get("id")), count))
    ctx["max_source_count"] = max_count
    ctx["notebook_count"] = len(notebooks)
    if bad_count_n:
        reasons.append(f"{bad_count_n} notebook(s) with non-numeric source_count")
        codes.add(Code.INVENTORY_MALFORMED)
    # Persisted so maybe_alert notices a second notebook crossing the threshold
    # while the code set stays {cap_near}.
    near_ids_sorted = sorted({i for i, _c in near_entries})
    ctx["near_cap_ids"] = near_ids_sorted
    if near_entries:
        text = "; ".join(f"{i} ({c})" for i, c in sorted(near_entries))
        reasons.append(f"near cap (>= {cap_warn}): " + text)
        codes.add(Code.CAP_NEAR)

    gen = data.get("generated_at")
    age_h = None
    if isinstance(gen, str):
        try:
            ts = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            age_h = (now - ts).total_seconds() / 3600
        except (ValueError, TypeError):
            # TypeError: a tz-naive `generated_at` minus an aware `now`.
            age_h = None

    if age_h is None:
        reasons.append("inventory generated_at missing/unreadable")
        codes.add(Code.INVENTORY_TIMESTAMP_INVALID)
    elif age_h < -(FUTURE_SKEW_TOLERANCE_MIN / 60):
        reasons.append(
            f"inventory generated_at is {abs(age_h):.2f}h in the future (clock skew)"
        )
        codes.add(Code.INVENTORY_TIMESTAMP_INVALID)
        ctx["inventory_age_h"] = round(age_h, 2)
    else:
        ctx["inventory_age_h"] = round(age_h, 1)
        if age_h > stale_hours:
            reasons.append(
                f"inventory stale {age_h:.0f}h (nb-curator-daily not producing)"
            )
            codes.add(Code.INVENTORY_STALE)

    return (len(reasons) == 0), reasons, ctx, codes


def _fetch_inventory_data(
    inventory_fn: Callable[[], tuple[int, str]],
    sleep_fn: Callable[[float], None],
    retry_delay_s: float,
) -> tuple[dict | None, str | None, str | None]:
    """Fetch and parse Pro's inventory JSON. nb_generate_inventory.py rewrites
    the file in place (no tempfile+rename), so a read can land on an empty or
    truncated body: an empty or unparseable first read is retried once after
    retry_delay_s; an ssh failure (rc != 0) is not retried. Returns
    (data, reason, code); data is None iff nothing parseable was read."""
    rc, raw = inventory_fn()
    if rc != 0:
        return None, f"nb-inventory-live.json missing or unreadable on Pro (ssh rc={rc})", Code.INVENTORY_MISSING

    data = _try_parse_inventory(raw) if raw.strip() else None
    if data is not None:
        return data, None, None

    sleep_fn(retry_delay_s)
    rc2, raw2 = inventory_fn()
    if rc2 != 0 or not raw2.strip():
        # ssh failure or still empty: missing. Non-empty but unparseable: malformed (below).
        return None, f"nb-inventory-live.json missing or unreadable on Pro (ssh rc={rc2})", Code.INVENTORY_MISSING

    data2 = _try_parse_inventory(raw2)
    if data2 is not None:
        return data2, None, None

    return (
        None,
        "nb-inventory-live.json unreadable after retry (producer writes non-atomically)",
        Code.INVENTORY_MALFORMED,
    )


# --- I/O (real ssh; injectable so tests never touch a network) -------------

def _ssh_pro(remote_cmd: str, connect_timeout: int, timeout: int) -> tuple[int, str]:
    return _run(
        ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={connect_timeout}",
         "pro", remote_cmd],
        timeout=timeout,
    )


def live_login_probe(connect_timeout: int, timeout: int) -> tuple[int, str]:
    return _ssh_pro(f"{PRO_NLM_BIN} login --check", connect_timeout, timeout)


def live_inventory_fetch(connect_timeout: int, timeout: int) -> tuple[int, str]:
    return _ssh_pro(f"cat {PRO_INVENTORY_PATH}", connect_timeout, timeout)


# --- composition -------------------------------------------------------------

def run_once(
    login_fn: Callable[[], tuple[int, str]],
    inventory_fn: Callable[[], tuple[int, str]],
    cap_warn: int = DEFAULT_CAP_WARN,
    stale_hours: float = DEFAULT_STALE_HOURS,
    now: datetime | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    retry_delay_s: float = DEFAULT_INVENTORY_RETRY_DELAY_S,
) -> Verdict:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    codes: set[str] = set()
    ctx: dict = {}

    rc, out = login_fn()
    login_ok, login_reason, login_code = classify_login(rc, out)
    if not login_ok:
        reasons.append(login_reason)
        codes.add(login_code)

    data, inv_fail_reason, inv_fail_code = _fetch_inventory_data(inventory_fn, sleep_fn, retry_delay_s)
    if data is None:
        reasons.append(inv_fail_reason)
        codes.add(inv_fail_code)
    else:
        inv_ok, inv_reasons, inv_ctx, inv_codes = evaluate_inventory_data(data, cap_warn, stale_hours, now)
        reasons.extend(inv_reasons)
        codes.update(inv_codes)
        ctx.update(inv_ctx)

    return Verdict(ok=(len(reasons) == 0), reasons=reasons, codes=codes, ctx=ctx)


# --- heartbeat (G2) + transition-gated Telegram (secondary channel) --------

def write_heartbeat(verdict: Verdict, path: Path | None = None) -> bool:
    """Write the heartbeat atomically (tmp file in the same dir + os.replace).
    Returns False on any write failure, never raises; main() then exits 1."""
    path = path or HEARTBEAT_PATH
    payload: dict = {
        "organ": "nlm-watchdog",
        "host": _hostname(),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if verdict.ok else "degraded",
        "codes": sorted(verdict.codes),
    }
    if verdict.reasons:
        note = "; ".join(verdict.reasons)[:MAX_REASON_LEN]
        # organism_stale_detector.py reads `note` or `last_error`.
        payload["note"] = note
        payload["last_error"] = note
    payload.update(verdict.ctx)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def read_previous_state(path: Path | None = None) -> tuple[str | None, set[str], list[str]]:
    path = path or HEARTBEAT_PATH
    try:
        data = json.loads(path.read_text())
        near_cap_ids = data.get("near_cap_ids") or []
        if not isinstance(near_cap_ids, list):
            near_cap_ids = []
        return data.get("status"), set(data.get("codes") or []), sorted(str(i) for i in near_cap_ids)
    except Exception:
        return None, set(), []


def maybe_alert(
    verdict: Verdict,
    previous_status: str | None,
    previous_codes: set[str] | None = None,
    previous_near_cap_ids: list[str] | None = None,
) -> bool:
    """Attempt a Telegram send when status, the code set or near_cap_ids
    differ from the previous heartbeat. No send on a first tick (no previous
    heartbeat) that is ok. Returns True iff tg_notify.py was invoked; its
    result is ignored."""
    previous_codes = previous_codes or set()
    previous_near_cap_ids = sorted(previous_near_cap_ids or [])
    new_status = "ok" if verdict.ok else "degraded"
    new_near_cap_ids = sorted(verdict.ctx.get("near_cap_ids") or [])
    if (
        previous_status == new_status
        and verdict.codes == previous_codes
        and new_near_cap_ids == previous_near_cap_ids
    ):
        return False
    if previous_status is None and new_status == "ok":
        return False
    host = _hostname()
    if new_status == "degraded":
        msg = f"nlm-watchdog [{host}]: {'; '.join(verdict.reasons)}"[:MAX_REASON_LEN]
        tier = "p0"
    else:
        msg = f"nlm-watchdog [{host}]: recovered (ok)"
        tier = "digest"
    if not TG_NOTIFY.exists():
        return False
    code_tag = "-".join(sorted(verdict.codes)) or "none"
    _run(
        ["python3", str(TG_NOTIFY), "--tier", tier, "--source", "nlm-watchdog",
         "--dedup-key", f"nlm-watchdog-{host}-{new_status}-{code_tag}", msg],
        timeout=30,
    )
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="NLM cross-host watchdog: Pro login liveness + notebook "
                     "source-cap + inventory freshness"
    )
    ap.add_argument("--cap-warn", type=int, default=DEFAULT_CAP_WARN)
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    ap.add_argument("--ssh-connect-timeout", type=int, default=SSH_CONNECT_TIMEOUT)
    ap.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT)
    ap.add_argument("--no-heartbeat", action="store_true",
                     help="skip the ~/.organism/last_seen/ write")
    ap.add_argument("--dry-run", action="store_true",
                     help="probe + print verdict only: no heartbeat, no Telegram")
    ap.add_argument("--once", action="store_true", help="alias; a tick is always one-shot")
    args = ap.parse_args(argv)

    if AUTH_SENTINEL_IMPORT_ERROR is not None:
        # Without auth_sentinel's dead-cookie regex the login verdict cannot be
        # trusted, so this tick reports import_failed and skips the probes.
        verdict = Verdict(
            ok=False,
            reasons=[f"auth_sentinel import failed ({AUTH_SENTINEL_IMPORT_ERROR}) — probes skipped"],
            codes={Code.IMPORT_FAILED},
        )
    else:
        try:
            verdict = run_once(
                login_fn=lambda: live_login_probe(args.ssh_connect_timeout, args.ssh_timeout),
                inventory_fn=lambda: live_inventory_fetch(args.ssh_connect_timeout, args.ssh_timeout),
                cap_warn=args.cap_warn,
                stale_hours=args.stale_hours,
            )
        except Exception as e:  # noqa: BLE001 — G9 fail-visible: a crash must still leave a trace
            # Type name only: an exception message could carry CLI output.
            verdict = Verdict(
                ok=False,
                reasons=[f"nlm_watchdog crashed: {type(e).__name__}"],
                codes={Code.CRASHED},
            )

    write_hb = not (args.no_heartbeat or args.dry_run)
    do_alert = not args.dry_run

    previous_status, previous_codes, previous_near_cap_ids = (
        read_previous_state() if do_alert else (None, set(), [])
    )
    hb_write_ok = True
    if write_hb:
        hb_write_ok = write_heartbeat(verdict)
    if do_alert:
        try:
            maybe_alert(verdict, previous_status, previous_codes, previous_near_cap_ids)
        except Exception:  # noqa: BLE001 — the verdict is already recorded; an alert bug must not turn it into a crash
            pass

    print(json.dumps({
        "status": "ok" if verdict.ok else "degraded",
        "codes": sorted(verdict.codes),
        "reasons": verdict.reasons,
        **verdict.ctx,
    }))
    if write_hb and not hb_write_ok:
        # The verdict was not recorded: never report success.
        return 1
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
