#!/usr/bin/env python3
"""nlm_watchdog.py — M5-resident cross-host probe for the two NLM failure modes that hit
NB-INTEL-Press silently for ~2 months (2026-07-18): (a) a notebook approaching Google's
500-source-per-notebook cap, and (b) Pro's `nlm` CLI cookie going dead independently of M5's
own cookie (M5 expired 2026-09-24 while Pro stayed valid — the two sessions are unrelated).

WHY M5, not Pro (2026-09-25 ground report): `~/.organism/` is per-host and NOT synced
cross-host (scripts/organism_heartbeat_brief.py:21-22, verified). The one channel a human
reliably sees is the M5 SessionStart digest (scripts/organism_digest.py), which only ever
reads M5's own `~/.organism/last_seen/`. Rather than invent a sync mechanism, M5 becomes the
active prober over SSH — the same idiom `scripts/proprioception.py` and
`scripts/organism_stale_detector.py` already document ("bootstrap-safe remote").

WHAT THIS FIXES that existing pieces did not:
  - `scripts/auth_sentinel.py:probe_nlm()` only ever checks M5's OWN cookie, never Pro's —
    and its ACTION-only alert filter leaves a `network_error`/`TIMEOUT` shape as silent
    UNKNOWN forever (found, not fixed here — see PR body "Found, not fixed here").
  - `mata_garuda/scripts/nb_monitor/run.py` never calls its own `fetch_source_count()` — dead
    code, no cap awareness at all.
  - `scripts/nb_generate_inventory.py` (cron on Pro, 04:00 daily) DOES compute `near_cap` per
    notebook into `~/nuzantara/research/nb-health/nb-inventory-live.json` — but
    `scripts/nb-curator-daily.sh`'s Telegram-trigger condition never reads it, so a notebook
    sitting at the cap for weeks never alerts anyone. This watchdog reads that SAME daily file
    (no new nlm calls, no new multi-minute `notebook list` round trip) and actually wires the
    already-computed field to a signal a human sees.

THREE PROBES, one tick (see scripts/nlm_watchdog_cron.sh, StartInterval 21600s / 6h):
  (a) Pro nlm login liveness — `ssh pro '~/.local/bin/nlm login --check'`.
  (b) Notebook source-cap warning — read Pro's inventory JSON, flag any notebook whose
      `source_count >= --cap-warn`.
  (c) Inventory freshness — the same file's `generated_at` must be < --stale-hours old
      (default 30h); this incidentally also watches nb-curator-daily.sh itself.

THE CAP NUMBER (Gear-3 council finding #9, codex): Google's NotebookLM plan table caps
sources at 500 per notebook (measured 2026-09-25, AI Ultra tier — see PR body for the
verification command). `--cap-warn` defaults to 450, a margin below that hard vendor limit,
not an independently-chosen threshold. `nb_generate_inventory.py`'s own `NEAR_CAP_THRESHOLD`
(480) is a DIFFERENT consumer's independent margin over the SAME 500 — the two constants are
never meant to be kept in lockstep. If Google ever raises or lowers 500, this organ's own
`max_source_count` in its heartbeat/stdout is the re-measure: a `max_source_count` that keeps
landing suspiciously below every `--cap-warn` a human tries is the signal to go re-check the
vendor's plan table, not a hardcoded constant anywhere in this file.

OUTPUT CONTRACT (G2 heartbeat gene): `~/.organism/last_seen/nlm-watchdog.json`, written
ATOMICALLY (tmp file + os.replace — Gear-3 finding, a concurrent `organism_digest.py` read
must never observe a partial write) on BOTH the ok and the degraded path, and on an unhandled
crash or even an `auth_sentinel` import failure (G9 fail-visible — see the module-level import
guard below). Carries `status` (organism_digest.py's own key), `note`/`last_error` (the
human-readable reason, organism_stale_detector.py's supported keys — `detail` is not read by
either consumer), `codes` (a stable, comparable set of machine reason-codes — see `Code`
below; this is what a status-unchanged-but-reason-changed tick alerts on, since comparing free
text would false-fire on every count/hour fluctuation embedded in the human string), and
`near_cap_ids` (a sorted, deduped list of the id8 of every notebook currently at/above
`--cap-warn` — round 2 finding, codex #3: two notebooks near-cap both only ever contribute the
SAME `CAP_NEAR` code, so a second notebook newly crossing the threshold changed nothing in
`codes`; comparing this list too closes that gap).

SECONDARY CHANNEL: `scripts/tg_notify.py`, fired when ANY of (status, code set, near-cap id8
set) changes while degraded (Gear-3 finding: a plain status-only transition gate silently
swallows "the login recovered but a NEW, different problem appeared" — degraded stays
degraded, nobody is told the problem changed). A Telegram send failure never changes the exit
code or the heartbeat already written.

PII BOUNDARY: never store raw `nlm`/ssh CLI stdout/stderr in the heartbeat or in a Telegram
message — the real `nlm login --check` success output includes an `Account: <email>` line
(measured 2026-09-25, read-only, on Pro — the email itself is never reproduced anywhere in
this file, its tests, or this PR). `classify_login()` only ever returns a FIXED reason string,
never `out` itself. Notebook TITLES are the second leak surface a council review found
(Gear-3, kimi #1) — and round 2 (codex #1, BLOCKING) rejected the first fix: gating on a
`^NB-[A-Za-z0-9]` PREFIX still let an operator-renamed title like `NB-CLIENT-CASE Jane Doe`
through verbatim, since nothing stops a client name from following a curated-looking prefix. A
prefix match is not a privacy boundary, so this file no longer looks at the title AT ALL:
`_display_name()` shows only the first 8 chars of the notebook's opaque id (or "unknown"),
unconditionally. A near-cap entry is `<id[:8]> (<count>)` — never a title, curated or not.

Usage:
    python3 scripts/nlm_watchdog.py                              # one tick, real ssh+heartbeat+telegram
    python3 scripts/nlm_watchdog.py --cap-warn 400 --dry-run      # probe + print only, no side effects
    python3 scripts/nlm_watchdog.py --no-heartbeat                # probe + telegram, skip the heartbeat write

Exit codes: 0 = ok, 1 = degraded OR the heartbeat itself failed to write (a monitoring organ
that cannot record its own verdict must never report success).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Reuse, don't duplicate: same directory as auth_sentinel.py, which already owns the
# auth-dead regex and the timeout-safe subprocess runner. A divergent regex here would be
# exactly the "two copies of the same judgement" failure this repo keeps scarring on.
#
# GUARDED (Gear-3 council finding, qwen #1): a bare module-level `from auth_sentinel import
# ...` means a future rename/move/signature change over there raises ImportError before
# main() ever runs, the cron wrapper's `|| true` swallows the traceback, and NO heartbeat is
# written — this organ goes fully silent (violates G9). The try/except below ensures the
# module always finishes importing; main() checks AUTH_SENTINEL_IMPORT_ERROR and writes a
# degraded heartbeat instead of ever reaching a NameError. Verified separately (see PR body):
# `_run` itself already catches every subprocess exception (FileNotFoundError, OSError, ...)
# in its own final `except Exception` branch, so it is a total function today — this guard is
# specifically for the IMPORT surface, not a claim that `_run` could newly start raising.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from auth_sentinel import _AUTH_DEAD_RE, _hostname, _run
    AUTH_SENTINEL_IMPORT_ERROR: str | None = None
except Exception as _imp_exc:  # noqa: BLE001 — see comment above; must never propagate
    AUTH_SENTINEL_IMPORT_ERROR = type(_imp_exc).__name__
    _AUTH_DEAD_RE = re.compile(r"(?!)")  # matches nothing; unreachable when the guard trips

    def _hostname() -> str:  # type: ignore[no-redef]
        import socket
        return socket.gethostname().split(".")[0]

    def _run(*_a, **_kw):  # type: ignore[no-redef]
        raise RuntimeError("auth_sentinel unavailable")

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
    """A notebook is NEVER shown by title (Gear-3 council round 2, codex #1
    BLOCKING: a `^NB-...` prefix gate is not a privacy boundary — a title
    like `NB-CLIENT-CASE Jane Doe` matched the old prefix check and still
    leaked the client name verbatim). Only the first 8 chars of the opaque
    id ever reach a heartbeat/Telegram/log; "unknown" if there is no id."""
    i = str(nb_id or "")
    return i[:8] if i else "unknown"


# --- pure classification (unit-testable, no I/O) ---------------------------

# Word-bounded so "invalid" can never satisfy this — `"valid" in out.lower()`
# (the original, pre-council shape) also matched "Authentication invalid",
# which real CLIs print with exit 0 (a status line, not a process failure).
_SUCCESS_RE = re.compile(r"\bauthentication\s+valid\b", re.I)
# `_AUTH_DEAD_RE` (auth_sentinel.py) has `invalid_grant` but no bare `invalid`
# — added locally rather than widening the shared regex, which other probes
# in auth_sentinel.py also depend on and which this PR does not touch.
_INVALID_RE = re.compile(r"\binvalid\b", re.I)


def classify_login(rc: int, out: str) -> tuple[bool, str, str | None]:
    """Pro's OWN cookie — separate from M5's (2026-09-24: M5 expired, Pro did not).

    The dead-check runs FIRST (Gear-3 council finding, codex/kimi #3): the old
    order let `"valid" in out.lower()` accept "Authentication invalid" outright,
    since the dead-regex check on the next line never ran once the first
    `return` fired — the worst possible direction for a watchdog. Returns
    (ok, human_reason, code); code is None iff ok."""
    if _AUTH_DEAD_RE.search(out) or _INVALID_RE.search(out) or "expired" in out.lower():
        return False, "pro nlm login dead (run `nlm login --clear` on Pro interactively)", Code.LOGIN_DEAD
    if rc == 0 and _SUCCESS_RE.search(out):
        return True, "", None
    # Unlike auth_sentinel.py's probe_nlm(), this shape is never silently
    # swallowed as an unalerted UNKNOWN (found, not fixed there — PR body).
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
        # Gear-3 council round 2 (kimi MINOR2, qwen MINOR1): the old
        # `count = nb.get("source_count") or 0` let a non-numeric producer
        # value (e.g. a string) pass `or 0` truthy, then raise TypeError at
        # `max()`/`>=` — which escaped run_once entirely and let main's
        # crash handler discard the login probe's verdict for the whole
        # tick. A non-numeric entry is now SKIPPED (never crashes) and
        # counted into its own reason/code instead. `bool` is explicitly
        # excluded even though it is a `int` subclass in Python — a JSON
        # `true`/`false` is not a source count.
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
    # Gear-3 council round 2 (codex #3, MAJOR): the alert signature used to be
    # just (status, codes) — while one notebook stayed near-cap, a SECOND
    # notebook could newly cross the threshold without ever changing the
    # code set (both only ever contribute `CAP_NEAR`), so no alert fired for
    # a genuinely new near-cap notebook. `near_cap_ids` (sorted, deduped id8
    # list) is now part of the persisted state maybe_alert compares against.
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
            # TypeError: a tz-naive `generated_at` minus an aware `now` — the
            # live producer writes `+00:00` today (verified 2026-09-25), but
            # nothing enforces that upstream (Gear-3 council, MINOR).
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
    """Fetch + parse Pro's inventory JSON, retrying ONCE after a short delay if
    the first read lands mid-write. `scripts/nb_generate_inventory.py` writes
    non-atomically (`open('w')` truncates in place, then streams `json.dump`
    directly — confirmed 2026-09-25, no tempfile+rename), so a concurrent
    `cat` from this organ's own daily tick can genuinely observe EITHER a
    truncated non-empty body OR a momentarily EMPTY file (the truncate lands
    before any bytes are written back) — Gear-3 council round 2 (codex #2,
    kimi MAJOR2, qwen NIT3): the first cut treated `rc==0` + empty as an
    immediate INVENTORY_MISSING with no retry, but that is the exact same
    race window as a truncated non-empty read and deserves the exact same
    retry. Only a hard ssh-level failure (`rc != 0`) is never retried — that
    is not a race, it is Pro being unreachable. Returns (data, reason,
    code) — data is None iff unrecoverable after the retry."""
    rc, raw = inventory_fn()
    if rc != 0:
        return None, f"nb-inventory-live.json missing or unreadable on Pro (ssh rc={rc})", Code.INVENTORY_MISSING

    data = _try_parse_inventory(raw) if raw.strip() else None
    if data is not None:
        return data, None, None

    sleep_fn(retry_delay_s)
    rc2, raw2 = inventory_fn()
    if rc2 != 0 or not raw2.strip():
        # Post-retry: a hard ssh failure OR a still-empty file both mean
        # "nothing readable on Pro" — reported as MISSING (Gear-3 council
        # round 2 spec), not MALFORMED (that code is reserved for a
        # non-empty body that still won't parse, see below).
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
    """Written ATOMICALLY (tmp file in the same dir + os.replace) — Gear-3
    council finding: `organism_digest.py` does a plain `json.loads` on this
    file, so a non-atomic write racing a read reports a spurious "unreadable"
    heartbeat line. Returns False on any write failure (never raises) so
    main() can force a non-zero exit — a monitoring organ that cannot record
    its own verdict must never look identical to one reporting ok."""
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
        # organism_stale_detector.py's `_sidecar_note()` reads a flat `note` or
        # `last_error` key (verified 2026-09-25) — `detail` is read by neither
        # consumer. Both are set to the same string; no reader needs to guess
        # which key this organ chose.
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
    """Telegram fires when ANY of (status, sorted reason-code set, sorted
    near-cap id8 list) changes — Gear-3 council finding (codex #4, qwen #4;
    round 2 codex #3 MAJOR added the third term): a status+codes-only gate
    suppressed a NEW notebook crossing the cap while an OLD one was already
    near it (both only ever contribute the same `CAP_NEAR` code, so the code
    SET never changed even though the set of affected notebooks did) — the
    same "a new failure hides behind an older one" shape this organ exists
    to prevent, one layer down. A send failure must never change the exit
    code or the heartbeat already committed, so its result is deliberately
    discarded (`_run` never raises).

    Returns True iff a send was ATTEMPTED — not whether it was delivered.

    First-run guard: `previous_status is None` means no heartbeat exists yet
    (fresh install). Treating that as "different from ok" would fire a
    nonsensical "recovered (ok)" message on the very first-ever tick. A first
    tick that is ALREADY degraded still alerts — a genuine new finding, not a
    false transition."""
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
        # G9 fail-visible: the import guard tripped at module load — probes
        # cannot run (they all depend on `_run`/`_AUTH_DEAD_RE`), but a
        # heartbeat still must be written so the organ never goes silent.
        verdict = Verdict(
            ok=False,
            reasons=[f"auth_sentinel import failed ({AUTH_SENTINEL_IMPORT_ERROR}) — probes cannot run"],
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
            # Exception TYPE name only, never the message (Gear-3 council finding: an
            # embedded `{e}` is the one non-fixed-vocabulary string that could cross
            # the PII boundary if a future exception ever wrapped raw CLI output).
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
        maybe_alert(verdict, previous_status, previous_codes, previous_near_cap_ids)

    print(json.dumps({
        "status": "ok" if verdict.ok else "degraded",
        "codes": sorted(verdict.codes),
        "reasons": verdict.reasons,
        **verdict.ctx,
    }))
    if write_hb and not hb_write_ok:
        # A monitoring organ that could not record its own verdict must never
        # report success — this is its own failure mode, not the probes'.
        return 1
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
