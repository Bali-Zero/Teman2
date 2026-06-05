#!/usr/bin/env python3
# chronic_failure_digest.py — weekly chronic-failure digest (W55 suppression-family fix)
#
# WHY THIS EXISTS
#   `~/scripts/audit-launchd-daily.sh` alerts ONLY on a *delta* (new-since-yesterday
#   unhealthy plists / hot-1h errors). A job that has been red for many consecutive
#   days produces ZERO delta after day 1, so it silently drops off the daily radar
#   — the exact W55 "suppression after first alert" failure family that masked the
#   2026-05-25 evolver/deploy-puller 32h drift and the 6 stale ops worktrees (W62).
#
#   This digest is the COMPLEMENT: it re-reads the last N daily JSON snapshots,
#   computes per-job CONSECUTIVE-day red streaks, cross-references the
#   circuit-breaker registry (OPEN) + the dead-letter queue (TERMINAL), and emits
#   ONE weekly Telegram message listing every job red for >= THRESHOLD days.
#
# READ-ONLY · NO LLM · PURE AGGREGATION.
#   Reads:
#     ~/logs/audit-launchd-daily-snapshots/YYYY-MM-DD.json   (audit snapshots)
#     ~/.agent/decisions/circuit_breakers.json               (breaker registry)
#     ~/.agent/decisions/dlq.json                            (dead-letter queue)
#   Writes: nothing but its own stdout (launchd log) + one Telegram POST.
#
# Invoked by com.nuzantara.chronic-failure-digest.weekly.plist (Mon 08:30 WITA).
#
# Env knobs (all optional):
#   CHRONIC_DIGEST_ENABLED   "true"/"false"  — kill switch (default true)
#   CHRONIC_DIGEST_THRESHOLD int             — min consecutive red days (default 3)
#   CHRONIC_DIGEST_WINDOW    int             — # of recent snapshots to scan (default 8)
#   SNAPSHOT_DIR             path            — override snapshots dir (tests)
#   STATE_DIR               path            — override ~/.agent/decisions (tests)
#   TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID — sourced by the .sh wrapper
#   CHRONIC_DIGEST_DRY_RUN   "1"             — print digest, do NOT POST to Telegram

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HOME", str(Path.home())))
SNAPSHOT_DIR = Path(
    os.environ.get("SNAPSHOT_DIR", HOME / "logs" / "audit-launchd-daily-snapshots")
)
STATE_DIR = Path(os.environ.get("STATE_DIR", HOME / ".agent" / "decisions"))
CIRCUIT_BREAKERS = STATE_DIR / "circuit_breakers.json"
DLQ = STATE_DIR / "dlq.json"

THRESHOLD = int(os.environ.get("CHRONIC_DIGEST_THRESHOLD", "3"))
WINDOW = int(os.environ.get("CHRONIC_DIGEST_WINDOW", "8"))
DRY_RUN = os.environ.get("CHRONIC_DIGEST_DRY_RUN", "") in ("1", "true", "yes")

# Breaker states that count as "still tripped" (defense-in-depth: anything not
# explicitly healthy). CLOSED == healthy; everything else is a signal.
BREAKER_TRIPPED_STATES = {"OPEN", "HALF_OPEN", "TERMINAL"}
# DLQ statuses that count as a permanently-abandoned job.
DLQ_DEAD_STATES = {"TERMINAL"}


def log(msg: str) -> None:
    print(f"[chronic-failure-digest] {msg}", flush=True)


def load_json(path: Path):
    try:
        with path.open() as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:  # noqa: BLE001 — corrupt file must not crash a watchdog
        log(f"WARN: could not parse {path}: {e}")
        return None


def recent_snapshots(window: int) -> list[tuple[str, dict]]:
    """Return up to `window` most-recent snapshots, OLDEST→NEWEST.

    Each item is (date_str, parsed_json). Date is the file stem (YYYY-MM-DD),
    which sorts lexicographically == chronologically.
    """
    if not SNAPSHOT_DIR.is_dir():
        return []
    files = sorted(SNAPSHOT_DIR.glob("*.json"))  # chronological by name
    files = files[-window:]  # keep the most recent `window`
    out: list[tuple[str, dict]] = []
    for fp in files:
        data = load_json(fp)
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            out.append((fp.stem, data))
    return out


# Diagnosis prefixes that constitute a genuine FAILED / NOT-LOADED / STALE
# *operational* failure (vs. a config-shape smell). A diagnosis string looks like
# "NONZERO_EXIT=1" / "STALE(last_activity=...)" / "NEVER_FIRED_OR_NOT_LOADED" /
# "DEGRADING_RECENT=2 ...". We match on the leading token.
FAILURE_DIAG_PREFIXES = (
    "NONZERO_EXIT",
    "NEVER_FIRED_OR_NOT_LOADED",
    "STALE",
    "DEGRADING_RECENT",
)
# A config smell the daily audit also flags as unhealthy, but which is NOT a
# runtime FAILED/NOT-LOADED state. Reporting these chronically would just relist
# the static plist-shape backlog every week — exactly the noise this digest must
# avoid. A row that is unhealthy ONLY for this reason is not "red" here.
CONFIG_SMELL_PREFIXES = (
    "USES_LC_ANTIPATTERN",
    "HISTORICAL_ERRORS",
    "HIGH_NOISE",
)


def row_is_red(row: dict) -> bool:
    """A job is RED for a day if the audit marked it FAILED / NOT-LOADED / STALE.

    The daily audit's `healthy: false` is the entry gate (it folds STALE /
    NONZERO_EXIT / NEVER_FIRED_OR_NOT_LOADED *and* config smells like
    USES_LC_ANTIPATTERN into one boolean). For a *chronic-failure* digest we then
    narrow to genuine operational failure signals and exclude rows that are
    unhealthy ONLY for a static config smell — otherwise the weekly digest would
    relist the whole plist-shape backlog (~15 lc-antipattern plists) every week
    and bury the real chronic failures it exists to surface.

    Red iff: not healthy AND (
        a real recent stderr error  OR  a non-zero/IO/config exit code
        OR  a failure-class diagnosis (NONZERO_EXIT / NOT_LOADED / STALE / DEGRADING)
    ).
    """
    if row.get("healthy") is not False:
        return False
    # Real runtime stderr in the last 24h is unambiguous failure.
    if int(row.get("stderr_real_recent_24h", 0) or 0) > 0:
        return True
    if int(row.get("stderr_real_hot_1h", 0) or 0) > 0:
        return True
    # Non-zero exit (sysexits like 74/75/78, or plain 1/2). "0" and the
    # placeholders "(never exited)" / "—" / None are not failures here.
    le = row.get("last_exit")
    if isinstance(le, int) and le != 0:
        return True
    if isinstance(le, str) and le not in ("0", "(never exited)", "—", "None", ""):
        return True
    # Diagnosis-based failure (covers NOT-LOADED, STALE, DEGRADING even when the
    # process left no stderr — e.g. a job that simply never fired / went stale).
    diag = row.get("diagnosis") or []
    has_failure = any(
        str(d).startswith(FAILURE_DIAG_PREFIXES) for d in diag
    )
    return has_failure


def last_error_line(row: dict) -> str:
    """Best one-line error summary for a red job from a single snapshot row."""
    sample = row.get("stderr_sample") or []
    if sample:
        # last non-empty line of the captured traceback/stderr tail
        for line in reversed(sample):
            line = (line or "").strip()
            if line:
                return line
    diag = row.get("diagnosis") or []
    if diag:
        return "; ".join(str(d) for d in diag)
    le = row.get("last_exit")
    if le not in (None, "0", 0):
        return f"last_exit={le}"
    return "(no error line captured)"


def compute_streaks(
    snapshots: list[tuple[str, dict]],
) -> dict[str, dict]:
    """Consecutive red-day streak per job, anchored at the MOST RECENT snapshot.

    We only report jobs that are red in the newest snapshot (an actively-broken
    job), then count backwards how many consecutive prior days it was also red.
    A healthy day OR an absence (job not in that day's snapshot) breaks the streak.
    """
    if not snapshots:
        return {}

    # Index each day's rows by label for O(1) lookup. Use `label` (stable id);
    # fall back to `plist` when a row lacks a label.
    def key(row: dict) -> str:
        return row.get("label") or row.get("plist") or "(unknown)"

    by_day: list[dict[str, dict]] = []
    for _date, data in snapshots:
        by_day.append({key(r): r for r in data["rows"]})

    newest_date, newest_data = snapshots[-1]
    newest_rows = by_day[-1]

    results: dict[str, dict] = {}
    for jk, newest_row in newest_rows.items():
        if not row_is_red(newest_row):
            continue
        # Walk backwards from newest day, counting the unbroken red streak.
        streak = 0
        for day_rows in reversed(by_day):
            r = day_rows.get(jk)
            if r is not None and row_is_red(r):
                streak += 1
            else:
                break  # healthy day or absent → streak ends
        results[jk] = {
            "label": jk,
            "plist": newest_row.get("plist", jk),
            "streak": streak,
            "since_date": snapshots[-streak][0] if streak <= len(snapshots) else newest_date,
            "diagnosis": newest_row.get("diagnosis") or [],
            "last_error": last_error_line(newest_row),
            "loaded": newest_row.get("loaded"),
            "last_exit": newest_row.get("last_exit"),
        }
    return results


def load_breakers() -> dict[str, str]:
    """Map job-name → tripped breaker state (only non-CLOSED breakers)."""
    data = load_json(CIRCUIT_BREAKERS)
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for name, rec in data.items():
            if isinstance(rec, dict):
                state = str(rec.get("state", "")).upper()
                if state in BREAKER_TRIPPED_STATES:
                    out[name] = state
    return out


def load_dlq_terminal() -> dict[str, str]:
    """Map job-name → DLQ status for TERMINAL (permanently abandoned) jobs."""
    data = load_json(DLQ)
    out: dict[str, str] = {}
    queue = []
    if isinstance(data, dict):
        queue = data.get("queue") or []
    elif isinstance(data, list):
        queue = data
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).upper()
        if status in DLQ_DEAD_STATES:
            job = entry.get("job")
            if job:
                out[str(job)] = status
    return out


def _norm(s: str) -> str:
    """Loosely normalise a label/plist/job-name for cross-source matching.

    Snapshots use plist labels like 'com.balizero.fly-pg-backup'; the breaker /
    DLQ registries use short names like 'fly_pg_backup'. Normalise both to a bag
    of alnum tokens so we can substring-match the short name inside the label.
    """
    return s.lower().replace(".", " ").replace("-", " ").replace("_", " ").strip()


def cross_ref(job_label: str, plist: str, registry: dict[str, str]) -> str | None:
    """Return the registry state if any registry key matches this job, else None."""
    hay = f"{_norm(job_label)} {_norm(plist)}"
    hay_tokens = set(hay.split())
    for name, state in registry.items():
        ntoks = set(_norm(name).split())
        if ntoks and ntoks.issubset(hay_tokens):
            return state
        # also allow the compact form to appear as a contiguous substring
        if _norm(name).replace(" ", "") in hay.replace(" ", ""):
            return state
    return None


def build_digest(threshold: int, window: int):
    snapshots = recent_snapshots(window)
    if not snapshots:
        log(f"no snapshots found under {SNAPSHOT_DIR}; nothing to do")
        return None, []

    streaks = compute_streaks(snapshots)
    breakers = load_breakers()
    dlq_terminal = load_dlq_terminal()

    chronic = [v for v in streaks.values() if v["streak"] >= threshold]
    chronic.sort(key=lambda x: -x["streak"])

    span = f"{snapshots[0][0]}..{snapshots[-1][0]} ({len(snapshots)} snapshots)"

    if not chronic:
        log(f"clean: 0 jobs red >= {threshold} consecutive days over {span}")
        return None, []

    lines = []
    lines.append("\U0001F4C9 *Chronic failure digest (weekly)*")
    lines.append(f"Window: {span} · threshold: >= {threshold} consecutive red days")
    lines.append("")
    for item in chronic:
        tags = []
        bstate = cross_ref(item["label"], item["plist"], breakers)
        if bstate:
            tags.append(f"breaker={bstate}")
        dstate = cross_ref(item["label"], item["plist"], dlq_terminal)
        if dstate:
            tags.append(f"dlq={dstate}")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        err = item["last_error"]
        if len(err) > 200:
            err = err[:197] + "..."
        lines.append(
            f"• *{item['plist']}* — RED {item['streak']}d "
            f"(since {item['since_date']}){tag_str}\n"
            f"  ↳ {err}"
        )
    lines.append("")
    lines.append(
        f"_{len(chronic)} chronic job(s). Complements the daily delta audit "
        f"(this catches steady-state red the daily alert suppresses — W55 family)._"
    )
    return "\n".join(lines), chronic


def send_telegram(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
    if not token or not chat:
        log("WARN: TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID missing; skipping POST")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat, "text": message, "parse_mode": "Markdown"}
    ).encode()
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            ok = 200 <= resp.status < 300
        log(f"telegram POST status ok={ok} chat={chat}")
        return ok
    except Exception as e:  # noqa: BLE001 — alert delivery must never crash the cron
        log(f"WARN: telegram POST failed: {e}")
        return False


def main() -> int:
    if os.environ.get("CHRONIC_DIGEST_ENABLED", "true").lower() in ("0", "false", "no"):
        log("disabled via CHRONIC_DIGEST_ENABLED; exiting 0")
        return 0

    message, chronic = build_digest(THRESHOLD, WINDOW)
    if not message:
        return 0  # clean week or no data — stay silent (digest, not heartbeat)

    log(f"{len(chronic)} chronic job(s) >= {THRESHOLD}d red")
    print(message)  # always emit to launchd stdout log for audit trail

    if DRY_RUN:
        log("dry-run: not sending Telegram")
        return 0

    send_telegram(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
