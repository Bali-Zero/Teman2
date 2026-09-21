#!/usr/bin/env python3
"""tg_notify.py — the ONE gate every Telegram notification passes through.

Born 2026-07-06 from Zero's mandate: "stiamo riorganizzando telegram perché non
posso più ricevere 600 messaggi al giorno". ~240 files in the repo could send
Telegram directly, each deciding alone. This gateway makes the decision once:

  --tier p0      actionable NOW (prod hotfix, guardian red, money, client blocked)
                 → sent immediately, subject to a small daily budget + dedup.
  --tier digest  informative (cron green, cures, merges, watcher findings)
                 → spooled; tg_digest_flush.py sends ONE grouped message per slot.
  --tier log     heartbeat / liveness / retry-ok
                 → disk only (counted in digest footer, never sent).

Design contracts (scar families they answer):
  - NEVER fails the caller: any internal error → spool best-effort, exit 0 (#7).
  - Fail-VISIBLE, not silent: unsendable P0 is spooled as `p0_unsent` and the
    next digest/organism_digest surfaces it (#2 esiste≠armato).
  - Identity ≠ measurement: the derived dedup key is the condition's first
    sentence with numbers/sizes/dates/hashes stripped, so a repeat that only
    moved a counter is the SAME condition (#3 under-match — the raw key made
    dedup decorative for its whole life).
  - A persisting condition gets QUIETER: each further send mutes it for the
    next rung of TG_REPEAT_LADDER_H (first rung = TG_DEDUP_HOURS). Silence
    past two windows means it died, so the ladder restarts. A re-sent repeat
    always declares how many it swallowed — muting must not hide magnitude.
  - Budget: max TG_P0_BUDGET P0/day/machine; overflow → digest + ONE meta-P0.
  - Stdlib only, no repo imports: runs from launchd, HOME copies, any machine.
  - Token chain: env → ~/.nuzantara-secrets.env → ssh relay (M5) → spool-only.

Usage:
  tg_notify.py --tier p0 --source healer-pro --dedup-key wa-bridge-down "msg"
  echo "msg" | tg_notify.py --tier digest --source fly-watcher
  tg_notify.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- env knobs
# Every root is env-overridable so --selftest fixtures a fake world (same
# pattern as organism_digest.py).


def _spool_dir() -> Path:
    return Path(os.environ.get("TG_SPOOL_DIR", str(Path.home() / ".organism" / "tg_spool")))


def _secrets_file() -> Path:
    return Path(os.environ.get("TG_SECRETS_FILE", str(Path.home() / ".nuzantara-secrets.env")))


def _owner_reserved(key: str) -> bool:
    """Does this condition require the OWNER — not a seat — to close it?"""
    return (key.split(":", 1)[0] if key else "") in OWNER_FAMILIES


def _board_path() -> Path:
    """The escalation board a seat already reads (SessionStart injects it).

    This gateway is stdlib-only and runs from launchd, from HOME copies and
    from any machine, so the repo is not guaranteed to be next to it. Resolution
    order mirrors every other root here: env first, then the checkout this file
    actually lives in. A HOME copy with no `shared/` falls back to the spool —
    the row is still written and still readable, just not on the shared board.
    """
    override = os.environ.get("TG_BOARD_PATH", "")
    if override:
        return Path(override)
    # DRY_RUN means "no effect outside this process", and the board is the most
    # shared state this file touches. Measured 2026-09-21: two separate suites
    # appended junk rows to the real board on their first run after routing
    # existed, and BOTH cleanup reflexes reached for `git checkout --`, which
    # discards whatever a peer appended in the same window. Fixing each fixture
    # cures the two that were caught; fixing the default cures the ones nobody
    # has written yet.
    if DRY_RUN:
        return _spool_dir() / "escalations_local.jsonl"
    shared = Path(__file__).resolve().parents[1] / "shared"
    if shared.is_dir():
        return shared / "escalations_pro.jsonl"
    return _spool_dir() / "escalations_local.jsonl"


def _append_board(record: dict, origin_tier: str) -> bool:
    """Append one pending row in the board's existing schema. Never raises.

    Schema is NOT invented here — it is the one `dlq_autopilot.py` and
    `healer_receptor_main_red.py` already write and the SessionStart receptor
    already renders, so a routed condition shows up on the same board as every
    other one, HIGH-first, with no reader change.
    """
    row = {
        "ts": record["ts"],
        "type": "gateway_routed",
        "job": record.get("key", "?"),
        # ALWAYS normal, and the asymmetry with origin_tier is the whole point.
        # HIGH on this board means "a human looks at this now" — the SessionStart
        # receptor renders HIGH first, every session. A condition routed here was
        # routed BECAUSE no human action is required; marking it HIGH would move
        # the 10.5/day from Telegram onto Zero's board and change nothing.
        # origin_tier below keeps the p0 provenance for audit without the volume.
        "priority": "NORMAL",
        "status": "pending",
        "error_summary": str(record.get("text", ""))[:400],
        "context": record.get("source", "unknown"),
        "machine": record.get("machine", "?"),
        "_writer": "tg-gateway",
        # The demotion must stay VISIBLE: a board row that hides it was once a
        # p0 is a p0 nobody can audit (superscar #2 — green is not working).
        "origin_tier": origin_tier,
        "cure_lane": {"owner": "seat", "note": "routed by tg_notify: no owner action required"},
    }
    try:
        path = _board_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _env_num(name: str, default: float, cast=float):
    """Garbage in an env knob must never crash a caller (fail-open contract)."""
    try:
        return cast(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return cast(default)


P0_BUDGET = _env_num("TG_P0_BUDGET", 12, int)
# Reserve for `cron-fail:*` keys, drawn ONLY once the shared budget is gone.
# Small on purpose: a flapping cron must not become the next source that eats
# the channel. See the comment at the budget decision below for the measurement.
CRON_FAIL_RESERVE = _env_num("TG_CRON_FAIL_RESERVE", 3, int)
# ── Daytime reserve (2026-08-07) ─────────────────────────────────────────────
# The budget was spent first-come-first-served, and the nightly cron batch
# empties it before dawn. Measured on Pro over 7 clean days (07-31 → 08-06):
# **68 of the 98 sent P0s (69%) fired between 00:00 and 02:59**, and between
# 08:00 and 23:00 essentially nothing got through except cron-fail reserve
# draws — while 275 further P0s (74% of a true demand of 53/day) went to the
# digest. The lane was therefore CLOSED during the hours its only reader is
# awake: anything breaking at 14:00 could not reach him. 18 of those 68
# pre-dawn slots were green bulletins that never carried a red in seven days.
#
# So the night may spend at most P0_BUDGET - DAY_RESERVE; the remainder is held
# for the daytime window. This changes WHICH P0s interrupt, not how many.
#
# `cron-fail:` is EXEMPT from the night sub-cap, deliberately: W106 IS a 03:21
# "the Postgres backup failed", and holding one back to protect the afternoon
# would be that same scar wearing a new face. A cron failure at night still
# faces only the full budget and its own reserve, exactly as before.
DAY_RESERVE = _env_num("TG_P0_DAY_RESERVE", 5, int)
DAY_START_H = _env_num("TG_P0_DAY_START_HOUR", 8, int)
DAY_END_H = _env_num("TG_P0_DAY_END_HOUR", 24, int)
DEDUP_HOURS = _env_num("TG_DEDUP_HOURS", 6, float)
# A condition that PERSISTS is not news each time it is re-measured. After the
# first send, each further send of the same live condition mutes it for longer.
# Replayed over the real corpus (5202 events / 29.5d, 1525 of them p0) modelling
# BOTH branches of `dedup_key or identity` — recorded key where the producer
# supplied one, the new identity where it did not:
#
#   all tiers   176.1/day -> 42.4/day        p0   51.6/day -> 22.8/day
#   wa-attention 20.45 -> 1.49   system-doctor 2.27 -> 0.14
#   log-size-watchdog 60.9 -> 4.2   wa-mirror-bridge 48.9 -> 4.5
#
# Replaying with recorded keys ONLY (i.e. ignoring the identity branch) gives
# 28.6 p0/day. That is the control, not the result: it is what the ladder alone
# would buy. A replay is only worth its digits if it models the branch the code
# actually takes, and this one has two.
#
# The control that makes this trustworthy: replaying a FLAT 6h window over the
# same keys reproduces the observed rate exactly (176.1 -> 176.1). The old
# window was not broken and was not being bypassed — 93.2% of events carry a
# producer-supplied dedup_key, and what the archive holds is precisely what
# survived a working 6h window. Four sends a day, forever, of a condition that
# is simply still true. That is what the ladder is for, and it is where all of
# the reduction above comes from.
#
# Where it does NOT bite: sentinel, 12.8 -> 10.6/day, because its producer key
# is md5(the whole message) and the message carries a counter — 378 events, 255
# distinct keys. A producer key that MOVES is worse than no key at all: it
# bypasses condition_identity() below (explicit key wins) and then defeats every
# window, because each re-measurement is a brand-new condition. Those producers
# need fixing at the source; the gateway cannot rescue them.
#
# The FIRST rung is TG_DEDUP_HOURS: this replaces a flat window with a growing
# one, it does not retire the knob that names the first window. Deriving the
# default instead of writing a literal 6 is the whole point — an operator who
# tightens TG_DEDUP_HOURS to hear a condition sooner must not be silently
# ignored by a hardcoded ladder (a knob that parses and does nothing is
# superscar #2 wearing a config file).
REPEAT_LADDER_H = [
    float(x) for x in os.environ.get("TG_REPEAT_LADDER_H", "").split(",") if x.strip()
] or [DEDUP_HOURS, 24.0, 72.0, 168.0]
# A condition is only DEAD after this much silence, even when the ladder's own
# window is shorter. 36h clears a daily cadence (24h) with margin for cron
# jitter, and stays well under 48h so a genuinely two-day-silent condition is
# still news. See _death_silence_h() for the measurement that set it.
DEATH_FLOOR_H = float(os.environ.get("TG_DEATH_FLOOR_H", "36"))
DRY_RUN = os.environ.get("TG_DRY_RUN", "") == "1"
RELAY_SSH = os.environ.get("TG_RELAY_SSH", "")  # e.g. "pro" on M5
RELAY_GATEWAY = os.environ.get(
    "TG_RELAY_GATEWAY", "/Users/nuzantara/nuzantara/scripts/tg_notify.py"
)

TIERS = ("p0", "digest", "log", "act")
API_TIMEOUT = 6

# ---------------------------------------------------------------- owner reserve
# MEASURED 2026-09-21 on this gateway's own archive-p0.jsonl: 315 p0 in 30 days
# (10.5/day) across 120 distinct keys, of which cron-fail alone is 39.7%. Almost
# none of it is an emergency — it is work, and work belongs to a seat.
#
# The cut is NOT a volume heuristic, it is CLAUDE.md's BUILDER CONTRACT §5 read
# literally: "What stays with the human: business decisions, credentials and
# consents, and physical/GUI actions." A condition an LLM seat CAN close must
# never reach the owner; a condition it CANNOT close must always reach him. On
# the measured corpus that is ~28 events per 30 days — 0.9/day.
#
# Matched on the ENTITY (the family before the first ':'), never as a substring
# — superscar #3 is symmetric, and `key.startswith("price-review")` would also
# swallow a hypothetical `price-review-bot-debug`. A key with no ':' is its own
# family, so a bare `disk-watchdog` still classifies.
OWNER_FAMILIES = frozenset(
    f.strip() for f in os.environ.get(
        "TG_OWNER_FAMILIES",
        "cost-breaker-deadman,price-review,meta-one-token-dead,wa-bridge,"
        "wa-mirror-bridge-liveness",
    ).split(",") if f.strip()
)
# wa-mirror-bridge-liveness is here for a reason worth keeping: the archive of
# SENT p0s is a FILTERED view — the ladder mutes chronic conditions, so a family
# can be near-invisible there and still be owner-work. This one was found by
# reading its alert text rather than its volume: it ends in "Re-link: ... --qr",
# which is a physical action (§5), and it is a SECOND family for the same
# physical fault already covered as `wa-bridge`. Derive this list from what a
# condition REQUIRES, never from how often it currently pages.
# Kill switch. Empty families OR this set to 0/false/no restores the pre-2026-09-21
# behaviour (every p0 pages the owner) without touching any of the 204 callers.
ACT_ROUTING_ENABLED = os.environ.get(
    "TG_ACT_ROUTING_ENABLED", "true").strip().lower() not in ("0", "false", "no")


# ---------------------------------------------------------------- identity
# A condition's IDENTITY must not contain its MEASUREMENTS.
#
# This is the FALLBACK, taken only when the caller passes no --dedup-key. Scope
# it honestly: on the measured corpus that is 6.8% of events (355 of 5202) —
# the other 93.2% name their own condition and never reach this function. It
# matters anyway, because a producer that names nothing gets the sane default
# instead of a key that changes whenever a number does.
#
# The old fallback was sha1(source|text[:160]) — raw, so a repeat that only
# moved a counter ("= 4.7 MB", "reconnect_attempt=591") became a brand-new
# condition. Replayed over just those 355 no-key events: 167 -> 35 conditions.
#
# Identity is the FIRST SENTENCE of the FIRST LINE. Everything after it is
# EVIDENCE (log tails, stack frames, counters) — unbounded variability that no
# prefix truncation can reliably exclude, which is why we cut on structure.
#
# The same normalisation is what a producer with an UNSTABLE explicit key
# should be passing (see sentinel, above) instead of a hash of its own text.
_ID_SUBS = (
    (re.compile(r"<[^>]+>"), ""),                                # html tags
    (re.compile(r"\b\d{4}-\d{2}-\d{2}([T ][\d:.,+]*)?"), "#D"),  # dates
    (re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b"), "#T"),           # clock
    (re.compile(r"\b[0-9a-f]{8,}\b"), "#H"),                     # hashes / uuids
    (re.compile(r"\b\d[\d.,]*\s*(MB|GB|KB|B|s|ms|%|h|d|min)\b"), "#S"),  # sizes / durations
    (re.compile(r"\b\d[\d.,]*\b"), "#N"),                        # bare numbers
)


def condition_identity(source: str, text: str) -> str:
    """Stable identity for one CONDITION, independent of how it is measured."""
    t = str(text or "")
    t = _ID_SUBS[0][0].sub("", t)
    t = t.split("\n")[0]                        # first line
    t = re.split(r"(?<=[.!?])\s", t)[0]         # first sentence
    t = " ".join(t.split())
    for rx, rep in _ID_SUBS[1:]:
        t = rx.sub(rep, t)
    return f"{source}|{t[:120]}"


def _mute_window_h(streak: int) -> float:
    """Hours to stay silent after the streak-th consecutive send of a condition."""
    if streak <= 0:
        return 0.0
    return REPEAT_LADDER_H[min(streak - 1, len(REPEAT_LADDER_H) - 1)]


def _death_silence_h(streak: int) -> float:
    """Silence after which a condition counts as DEAD (its next hit is a new birth).

    Why this is not simply `2 * mute_window` (2026-08-07). It used to be, and the
    consequence was measured live: the ladder could never quieten a ONCE-A-DAY
    condition, which is most of this fleet's traffic. At rung 1 the window is
    DEDUP_HOURS (6h), so "dead" meant 12h of silence — SHORTER than the 24h period
    of a daily cron. Every nightly recurrence therefore looked like a brand-new
    condition, reset the streak to 1, and sent at full volume forever.

    Measured on Pro over 7 days, from the gateway's own dedup state:

        wa-bridge:* (fires several times a day)   8 days running -> streak 3
        cron-fail:garuda_indexer                  7 days running -> streak 1
        cron-fail:nightly_autofix_ci              7 days running -> streak 1
        cron-agent:conversation-cleanup           7 days running -> streak 1
        cron-fail:nb_agents_daily_dr              7 days running -> streak 1
        cron-fail:run_gap_scanner_layer_a         7 days running -> streak 1

    Chatty conditions climb; daily ones are pinned at rung 1. Those five alone
    are five P0 every single day. The comment two functions below —
    "else a chronic condition loses its streak and the ladder silently restarts
    at 6h forever" — names this exact failure and guards the PRUNE path; this is
    the other door into the same room.

    The floor only bites at rung 1 (2*6=12 -> 36). From rung 2 on, `2 * win`
    already dominates (48, 144, 336) and this changes nothing — so a condition
    that has genuinely climbed keeps exactly the death semantics it has today.
    """
    return max(2.0 * _mute_window_h(streak), DEATH_FLOOR_H)


# ---------------------------------------------------------------- token chain
def _parse_env_file(path: Path) -> dict:
    """Read a shell-style secrets file into a dict.

    `export FOO=bar` is the SAME key as `FOO=bar`: the file is sourced by shell
    wrappers (which need `export` to reach child processes) AND read by this
    parser, so both forms must resolve. Without the prefix strip the key became
    the literal "export FOO" and the secret was invisible — measured 2026-08-06:
    19 keys on Mini (incl. TELEGRAM_BOT_TOKEN, DATABASE_URL), 6 on Pro, 4 on M5.
    Never `lstrip("export ")`: lstrip strips CHARACTERS, so it would turn
    EVENTBUS_URL into VENTBUS_URL. The prefix is anchored and must be followed by
    whitespace, so `exportFOO=1` and `export=1` stay keys in their own right.
    """
    out: dict = {}
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = re.sub(r"^\s*export\s+", "", k).strip()
            if not k:  # `export =v` — malformed shell, names nothing
                continue
            out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def resolve_credentials() -> tuple[str, str]:
    """Return (token, chat_id); empty strings when unavailable."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = (
        os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
        or os.environ.get("TELEGRAM_ZERO_CHAT_ID", "")
        or os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
    )
    if not token or not chat:
        env = _parse_env_file(_secrets_file())
        token = token or env.get("TELEGRAM_BOT_TOKEN", "")
        chat = (
            chat
            or env.get("TELEGRAM_OWNER_CHAT_ID", "")
            or env.get("TELEGRAM_ZERO_CHAT_ID", "")
            or env.get("TELEGRAM_ADMIN_CHAT_ID", "")
        )
    return token, chat


# ---------------------------------------------------------------- state/spool
def _load_state(spool: Path) -> dict:
    p = spool / "state.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(spool: Path, state: dict) -> None:
    p = spool / "state.json"
    tmp = p.with_suffix(f".json.tmp{os.getpid()}")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    # The temp file inherits the umask and `replace` carries ITS mode onto the
    # destination, so hardening `p` afterwards would be undone by the next
    # save. Harden the source of the rename.
    harden(tmp)
    tmp.replace(p)
    harden(p)


class _spool_lock:
    """flock over the whole spool: appends, rotation and state.json updates
    share it so no path can lose lines or dedup/budget counts (Codex finding,
    2026-07-06). Held for microseconds — NEVER across a network send."""

    def __init__(self, spool: Path):
        spool.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(spool / ".spool.lock"), os.O_CREAT | os.O_RDWR, 0o600)

    def __enter__(self):
        import fcntl
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        return False


def harden(path: Path) -> Path:
    """Force 0600 on a spool file, self-healing whatever mode it already has.

    THE one place this rule lives, because the spool has three writers and only
    one of them was applying it. `_append` below opens with 0o600 and the flock
    file is 0o600 — so the author knew — but `_save_state` used
    `Path.write_text` and `tg_digest_flush._archive` used `open("a")`, both of
    which take the umask (0644 on Pro). Measured 2026-08-06:

        archive-p0.jsonl        -rw-------   (the one that used _append)
        state.json              -rw-r--r--
        archive/2026-*.jsonl    -rw-r--r--   1.6 MB, 33 days, every event

    The unprotected two are the bigger exposure, not the smaller: state.json
    carries `last_text` (200 chars of every alert) and the daily archive is the
    complete record, including 560 rows whose dedup key still carries a raw
    client phone number from before the 2026-07-26 grouping fix. Superscar #4 —
    the restriction is applied where the author was thinking about it and
    missed where a different idiom was used.

    O_CREAT's mode argument only applies when the file is CREATED, so a chmod
    is what repairs the files already on disk. Doing it on every write costs a
    syscall and needs no separate repair pass — the next flush heals the spool.
    Never raises: a spool the process cannot chmod (foreign owner) must not
    take down the alert it is carrying.

    Two steps, and the first one is the one this fix originally got WRONG:
    a chmod alone protects only files that ALREADY exist, so the first write of
    each new day still went through `open("a")` and was born 0644 under the
    umask — the cure carrying the shape of the disease. Creating the file
    privately first closes that, and the chmod then repairs the ones already on
    disk. Both are needed; neither is sufficient.
    """
    try:
        # O_CREAT without O_EXCL: creates at 0600, or opens an existing file
        # and changes nothing. Closed immediately — the caller does the writing.
        os.close(os.open(str(path), os.O_CREAT | os.O_WRONLY, 0o600))
        if path.stat().st_mode & 0o077:
            os.chmod(path, 0o600)
    except OSError:
        # Swallowed ON PURPOSE, and pinned by an innocence test
        # (test_hardening_never_takes_down_the_alert_it_carries): a spool the
        # process cannot chmod — foreign owner, read-only mount — must degrade
        # to a looser file, never abort the send. An alerter that dies because
        # it could not tidy its own permissions has traded a privacy defect for
        # a silence defect, which is the worse of the two.
        pass
    return path


def _append(spool: Path, name: str, record: dict) -> None:
    spool.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    # O_APPEND single-write keeps concurrent senders line-atomic (<4k).
    fd = os.open(str(harden(spool / name)), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


# ---------------------------------------------------------------- send paths
def send_telegram(token: str, chat: str, text: str) -> bool:
    if DRY_RUN:
        _append(_spool_dir(), "sent-dry.jsonl", {"ts": time.time(), "text": text})
        return True
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            return json.loads(resp.read().decode()).get("ok", False)
    except urllib.error.HTTPError as e:
        # Telegram's error body names the real cause (bad token, chat not
        # found, blocked, rate-limited, ...) — never the token itself, which
        # lives in the URL, not the response. Swallowing this (bare `except
        # Exception: return False`) left every past failure undiagnosable:
        # "SEND FAILED" in the caller's log with no reason, ever.
        try:
            detail = e.read().decode(errors="replace")[:300]
        except Exception:
            detail = ""
        print(f"[tg_notify] send_telegram HTTPError {e.code} {e.reason}: {detail}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[tg_notify] send_telegram {type(e).__name__}: {e}", file=sys.stderr)
        return False


def send_via_relay(args_tier: str, source: str, dedup_key: str, text: str) -> bool:
    """M5 has no token: forward the P0 to the Pro gateway over ssh."""
    if not RELAY_SSH:
        return False
    import shlex
    # OpenSSH concatenates argv into ONE remote shell string: every token must
    # be quoted or log content inside `text` executes on the relay host.
    remote = ["python3", RELAY_GATEWAY, "--tier", args_tier, "--source", source]
    if dedup_key:
        remote += ["--dedup-key", dedup_key]
    remote += ["--", text]
    cmd = ["ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes", RELAY_SSH,
           " ".join(shlex.quote(t) for t in remote)]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=15).returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------- core logic
def notify(tier: str, source: str, text: str, dedup_key: str = "") -> str:
    """Route one notification. Returns a status string (for tests/logs).

    Two-phase locking: decision + spool writes happen under the spool flock;
    the network send happens OUTSIDE it (a hung API must not serialize other
    senders); the outcome (budget commit / rollback) re-takes the lock.
    """
    spool = _spool_dir()
    now = time.time()
    machine = socket.gethostname().split(".")[0]
    key = dedup_key or hashlib.sha1(condition_identity(source, text).encode()).hexdigest()[:16]

    record = {
        "ts": now,
        "tier": tier,
        "source": source,
        "machine": machine,
        "key": key,
        "text": text,
    }

    send_meta = False
    drew_from_reserve = False
    held_for_day = False
    today = time.strftime("%Y-%m-%d", time.localtime(now))

    with _spool_lock(spool):
        state = _load_state(spool)
        dedup = state.setdefault("dedup", {})
        entry = dedup.get(key)
        suppressed = 0
        streak = 1
        if entry:
            streak = int(entry.get("streak", 1))
            # Window grows with the streak: a condition that keeps being true
            # gets quieter, it does not get louder.
            win = _mute_window_h(streak) * 3600
            since = now - entry.get("ts", 0)
            if since < win:
                entry["count"] = entry.get("count", 1) + 1
                entry["last_text"] = text[:200]
                _save_state(spool, state)
                return "deduped"
            # Silent for longer than the death threshold => the condition DIED.
            # The next occurrence is a new birth, so the ladder restarts at the
            # top. NOT `2 * win`: at rung 1 that is 12h, shorter than a daily
            # cron's own period, so every nightly recurrence read as a rebirth
            # and the ladder could never climb. See _death_silence_h().
            if since > _death_silence_h(streak) * 3600:
                streak = 1
                suppressed = 0
            else:
                streak += 1
                suppressed = max(0, entry.get("count", 1) - 1)
        dedup[key] = {
            "ts": now,
            "count": 1,
            "streak": streak,
            "first_ts": (entry or {}).get("first_ts", now) if streak > 1 else now,
            "last_text": text[:200],
        }
        # A repeat must carry HOW MUCH it repeated while muted, or suppressing it
        # silently would hide the magnitude of a worsening condition.
        if suppressed:
            hrs = (now - dedup[key]["first_ts"]) / 3600
            record["suppressed"] = suppressed
            record["streak"] = streak
            text = f"{text}\n\n(ripetuta {suppressed}× nelle ultime {hrs:.0f}h — silenziata fino a +{_mute_window_h(streak):.0f}h)"
            record["text"] = text
        # Prune only beyond the LONGEST window, else a chronic condition loses
        # its streak and the ladder silently restarts at 6h forever.
        horizon = now - 2 * max(REPEAT_LADDER_H) * 3600
        state["dedup"] = {k: v for k, v in dedup.items() if v.get("ts", 0) >= horizon}

        # ---- routing to the board, decided AFTER the ladder and BEFORE the
        # p0 budget. After the ladder on purpose: a condition that repeats every
        # 15 minutes must not append a board row every 15 minutes either — that
        # is exactly the W61 storm that re-grew this same file for ~5h. Before
        # the budget because a routed p0 must not spend a slot it never used.
        #
        # Fail-OPEN toward the human: if the board cannot be written, the p0
        # falls through to Telegram unchanged. An alarm that is silently dropped
        # because its destination was unwritable is worse than a noisy one.
        routed = tier == "act" or (
            tier == "p0" and ACT_ROUTING_ENABLED and OWNER_FAMILIES and not _owner_reserved(key)
        )
        if routed and _append_board(record, origin_tier=tier):
            _save_state(spool, state)
            # "spooled", not a fourth verdict: 204 callers already know it
            # ("taken into custody, not handed to a human"), and a NEW word
            # breaks the class of them that copied the vocabulary instead of
            # importing tg_gateway_verdict.py. Observability lives where it
            # belongs — the board row (type=gateway_routed, origin_tier).
            return "spooled"

        if tier == "log":
            _append(spool, "log-only.jsonl", record)
            _save_state(spool, state)
            return "logged"

        if tier == "digest":
            _append(spool, "pending.jsonl", record)
            _save_state(spool, state)
            return "spooled"

        # ---- tier == p0: decide under lock, reserve the budget slot ----
        budget = state.setdefault("p0_budget", {})
        if budget.get("date") != today:
            budget.clear()
            budget.update({"date": today, "sent": 0, "overflow": 0, "cron_reserve": 0})

        hour = time.localtime(now).tm_hour
        is_day = DAY_START_H <= hour < DAY_END_H
        is_cron_fail = key.startswith("cron-fail:")
        night_cap = max(0, P0_BUDGET - DAY_RESERVE)
        # A cron failure is never subject to the night sub-cap (see DAY_RESERVE).
        effective = P0_BUDGET if (is_day or is_cron_fail) else night_cap

        if budget["sent"] >= effective:
            # A cron JOB FAILURE draws on its own small reserve once the shared
            # budget is gone. Measured 2026-07-27 on Pro: the P0 budget is hit on
            # 8 of 21 days and 68% of it (155 of 228 sent P0s) is one chatty
            # source — so on a busy day a genuine existential alert loses its slot
            # to conversation notices. That is not hypothetical: on 2026-07-26 at
            # 03:21 "the Postgres backup failed" returned p0_overflow_spooled and
            # went to the digest, and production then spent 27 hours with no
            # backup at all.
            if is_cron_fail and budget.get("cron_reserve", 0) < CRON_FAIL_RESERVE:
                budget["cron_reserve"] = budget.get("cron_reserve", 0) + 1
                drew_from_reserve = True
                record["p0_cron_reserve"] = True
                _save_state(spool, state)
                over = False
            else:
                budget["overflow"] += 1
                record["p0_overflow"] = True
                # Distinguish "the day's budget is gone" from "the night has
                # spent its share and the rest is held for daylight" — they are
                # different states, and the meta message below must not claim
                # the first while the second is true (W106's second-degree
                # defect: the diagnosis that ages with the cure).
                if not is_day and budget["sent"] < P0_BUDGET:
                    record["p0_night_holdback"] = True
                    held_for_day = True
                _append(spool, "pending.jsonl", record)
                send_meta = budget["overflow"] == 1
                _save_state(spool, state)
                over = True
        else:
            budget["sent"] += 1  # reserved; rolled back below if the send fails
            _save_state(spool, state)
            over = False

    if over:
        if send_meta:
            token, chat = resolve_credentials()
            if held_for_day:
                meta = (
                    f"🌙 [{machine}] Quota P0 notturna esaurita "
                    f"({max(0, P0_BUDGET - DAY_RESERVE)}/{P0_BUDGET}); "
                    f"{DAY_RESERVE} slot restano per le "
                    f"{int(DAY_START_H):02d}-{int(DAY_END_H):02d}. I P0 notturni "
                    f"successivi vanno nel digest — i cron-fail passano lo stesso."
                )
            else:
                meta = (
                    f"🔕 [{machine}] Budget P0 esaurito ({P0_BUDGET}/{P0_BUDGET} oggi). "
                    f"I successivi P0 finiscono nel digest."
                )
            if DRY_RUN or (token and chat):
                send_telegram(token, chat, meta)
            else:
                send_via_relay("p0", "tg-gateway", f"p0-budget-{today}", meta)
        return "p0_overflow_spooled"

    # ---- the send, outside the lock ----
    token, chat = resolve_credentials()
    msg = f"🔴 [{source}@{machine}] {text}"
    sent = False
    if DRY_RUN or (token and chat):
        sent = send_telegram(token, chat, msg)
    if not sent and send_via_relay("p0", source, dedup_key, text):
        sent = True
        record["relayed"] = True

    with _spool_lock(spool):
        state = _load_state(spool)
        budget = state.setdefault("p0_budget", {"date": today, "sent": 1, "overflow": 0})
        if sent:
            record["sent"] = True
            _append(spool, "archive-p0.jsonl", record)
            _save_state(spool, state)
            return "sent"
        # Unsendable P0: roll back the reserved slot; fail-visible, never fail the caller.
        if budget.get("date") == today:
            # Roll back the counter we actually drew from, not the shared one.
            if drew_from_reserve and budget.get("cron_reserve", 0) > 0:
                budget["cron_reserve"] -= 1
            elif budget.get("sent", 0) > 0:
                budget["sent"] -= 1
        record["p0_unsent"] = True
        _append(spool, "pending.jsonl", record)
        _save_state(spool, state)
    print("tg_notify: P0 unsendable (no token/relay) — spooled as p0_unsent", file=sys.stderr)
    return "p0_unsent_spooled"


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Guilt+innocence fixtures in a throwaway spool. No network (TG_DRY_RUN)."""
    import tempfile

    failures = []
    with tempfile.TemporaryDirectory() as td:
        os.environ["TG_SPOOL_DIR"] = td
        os.environ["TG_DRY_RUN"] = "1"
        os.environ["TG_SECRETS_FILE"] = "/dev/null"  # hermetic: never read host secrets
        global DRY_RUN, P0_BUDGET, CRON_FAIL_RESERVE, DAY_RESERVE, DAY_START_H, DAY_END_H
        global ACT_ROUTING_ENABLED
        DRY_RUN, P0_BUDGET = True, 2
        # Board routing OFF for the budget/ladder blocks below, and the pin is
        # the point rather than a convenience: those checks assert what the p0
        # LANE does (budget, night cap, cron reserve, escalation ladder), and
        # that lane is unchanged by 2026-09-21. Routing is a layer ABOVE it and
        # gets its own block at the end, where it is switched back on. Leaving
        # it on here would have rewritten ~14 assertions to say "spooled" —
        # indistinguishable from the digest spool — and quietly deleted the
        # coverage of the budget itself.
        ACT_ROUTING_ENABLED = False
        # Pin the day/night window, exactly as the two blocks below already do
        # ("the window is pinned by the knobs, not by the wall clock"). Without
        # it THIS block inherited the real local hour, and at night
        # `effective = max(0, P0_BUDGET - DAY_RESERVE)` = max(0, 2-5) = 0, so the
        # very first p0 overflowed and six checks went red — measured 2026-08-08
        # on M5 and Pro at 03:40 WITA, while the same commit passed at 19:40 UTC.
        # A gateway selftest that is green in CI's timezone and red during the
        # hours the cron fleet actually runs proves nothing at the moment it
        # matters, and `tg-gateway.yml` is path-filtered, so nobody sees it.
        DAY_START_H, DAY_END_H = 0, 24  # every hour qualifies -> always day
        spool = Path(td)

        def check(name, cond):
            print(("  ok  " if cond else "  FAIL") + f" {name}")
            if not cond:
                failures.append(name)

        check("digest spools", notify("digest", "t", "hello") == "spooled")
        check("dup deduped", notify("digest", "t", "hello") == "deduped")
        check("log stays on disk", notify("log", "t", "beat") == "logged")
        # Distinct CONDITIONS, not the same condition re-measured. The old
        # fixtures were "fire-1"/"fire-2"/"fire-3", which differ only by a
        # number — under the identity rule those ARE one condition, and the
        # test was silently asserting that dedup does not work.
        check("p0 sends (dry)", notify("p0", "t", "the disk is full") == "sent")
        check("p0 sends (dry) 2", notify("p0", "t", "the token was revoked") == "sent")
        check(
            "p0 over budget → spool",
            notify("p0", "t", "the backup did not run") == "p0_overflow_spooled",
        )
        pending = (spool / "pending.jsonl").read_text().strip().splitlines()
        check("pending has digest+overflow", len(pending) == 2)
        check("log-only file exists", (spool / "log-only.jsonl").exists())
        sent_dry = (spool / "sent-dry.jsonl").read_text().strip().splitlines()
        check("dry sends: 2 p0 + 1 budget meta", len(sent_dry) == 3)
        state = json.loads((spool / "state.json").read_text())
        check("dedup counted ×2", any(v.get("count") == 2 for v in state["dedup"].values()))

        # ---- cron-fail reserve (2026-07-27) --------------------------------
        # GUILT: with the shared budget spent, a cron JOB FAILURE must still get
        # through — the measured hole was a real "no Postgres backup" alert
        # demoted to digest because a chatty source had eaten the day's 12.
        # INNOCENCE: the reserve is not a bypass — a NON-cron P0 still overflows
        # with the budget spent, and the reserve itself runs out.
        CRON_FAIL_RESERVE = 2
        check(
            "cron-fail passes on a spent budget",
            notify("p0", "cron:x", "boom-1", "cron-fail:job-a") == "sent",
        )
        check(
            "cron-fail passes again while the reserve holds",
            notify("p0", "cron:x", "boom-2", "cron-fail:job-b") == "sent",
        )
        check(
            "the reserve itself runs out",
            notify("p0", "cron:x", "boom-3", "cron-fail:job-c") == "p0_overflow_spooled",
        )
        check(
            "a non-cron P0 is NOT let through by the reserve",
            notify("p0", "t", "an unrelated failure", "other:thing") == "p0_overflow_spooled",
        )

        # ---- daytime reserve (2026-08-07) ----------------------------------
        # GUILT: the nightly batch spent the whole budget before dawn (68 of 98
        # sent P0s fired 00:00-02:59 on the live fleet), so the lane was shut
        # for the hours its reader is awake. The night must now stop at
        # P0_BUDGET - DAY_RESERVE.
        # INNOCENCE ×2, and the second is the one that matters: the very P0 the
        # night refused goes through in daylight (the slots are held, not
        # destroyed), and a `cron-fail:` at night is NEVER held — W106 is a
        # 03:21 backup failure, and protecting the afternoon with it would be
        # the same scar with a new face.
        # The window is pinned by the knobs, not by the wall clock, so this is
        # deterministic at any hour CI happens to run.
        P0_BUDGET, CRON_FAIL_RESERVE, DAY_RESERVE = 4, 2, 2  # night may spend 2 of 4

        night = spool / "night"
        night.mkdir()
        os.environ["TG_SPOOL_DIR"] = str(night)
        DAY_START_H, DAY_END_H = 25, 25  # no hour qualifies → always night
        check("night: 1st P0 sends", notify("p0", "n", "the disk is full") == "sent")
        check("night: 2nd P0 sends", notify("p0", "n", "the token was revoked") == "sent")
        check(
            "night: 3rd P0 is HELD for the day",
            notify("p0", "n", "a third distinct thing broke") == "p0_overflow_spooled",
        )
        nstate = json.loads((night / "state.json").read_text())
        check(
            "…and the budget is NOT exhausted (2 of 4 spent)",
            nstate["p0_budget"]["sent"] == 2 and nstate["p0_budget"]["sent"] < P0_BUDGET,
        )
        held = [json.loads(x) for x in (night / "pending.jsonl").read_text().splitlines()]
        check("…the held record says WHY", any(r.get("p0_night_holdback") for r in held))
        meta = (night / "sent-dry.jsonl").read_text()
        check("…and the meta message does not claim the budget is spent",
              "notturna" in meta and "Budget P0 esaurito" not in meta)
        # The exemption cannot be proven by ONE night cron-fail: without it the
        # call still succeeds — by drawing the cron reserve. The difference is
        # only visible once that reserve would be gone, and it is the whole
        # point: night cron-fails must not BURN the reserve that the 03:21
        # backup failure needs. With the exemption the budget (4) carries them
        # and the reserve (2) is still untouched behind it, so four pass;
        # without it only the two the reserve can cover do. A first draft
        # asserted a single cron-fail here and a mutation that deleted the
        # exemption sailed straight through it.
        for i, what in enumerate(
            ["the backup did not run", "the mirror died", "the disk filled", "the token expired"]
        ):
            check(
                f"night: cron-fail {i + 1}/4 passes WITHOUT burning the reserve (W106)",
                notify("p0", "cron:x", what, f"cron-fail:job-{i}") == "sent",
            )

        day = spool / "day"
        day.mkdir()
        os.environ["TG_SPOOL_DIR"] = str(day)
        DAY_START_H, DAY_END_H = 0, 24  # every hour qualifies → always day
        check("day: 1st P0 sends", notify("p0", "d", "the disk is full") == "sent")
        check("day: 2nd P0 sends", notify("p0", "d", "the token was revoked") == "sent")
        check(
            "day: the 3rd — refused at night — GOES THROUGH",
            notify("p0", "d", "a third distinct thing broke") == "sent",
        )
        os.environ["TG_SPOOL_DIR"] = str(spool)

        # ---- identity: measurements are not identity (2026-08-06) ----------
        # GUILT: the three loudest sources on the live fleet each embed a
        # changing number in their text; under the old raw key every repeat
        # hashed anew and the dedup window never applied even once.
        check(
            "same condition, different measurement → deduped",
            notify("digest", "lsw", "Log size alert: ~/logs/a.log = 4.5 MB (>1MB threshold). tail A")
            == "spooled"
            and notify(
                "digest", "lsw", "Log size alert: ~/logs/a.log = 9.9 MB (>1MB threshold). tail Z"
            )
            == "deduped",
        )
        # INNOCENCE: two DIFFERENT logs stay two conditions — the normalisation
        # strips measurements, never nouns.
        check(
            "different log → still its own condition",
            notify("digest", "lsw", "Log size alert: ~/logs/b.log = 2.5 MB (>1MB threshold). x")
            == "spooled",
        )
        state = json.loads((spool / "state.json").read_text())
        check("reserve counted exactly twice", state["p0_budget"].get("cron_reserve") == 2)

        # ---- the repeat ladder must climb for a DAILY condition (2026-08-07) --
        # The clock is a HOLDER the test advances, never an iterator of ticks:
        # `logging` calls time.time() once per LogRecord and would drain a list
        # sized to the number of notifies (P3 FLAKY, cured 2026-08-02).
        real_time = time.time
        clock = [real_time()]
        time.time = lambda: clock[0]
        try:
            ladder = spool / "ladder"
            ladder.mkdir()
            os.environ["TG_SPOOL_DIR"] = str(ladder)
            DAY_START_H, DAY_END_H = 0, 24
            P0_BUDGET = 99  # the ladder is what is under test here, not the budget

            # GUILT: seven consecutive days of ONE standing condition. Before the
            # floor this sent 7/7 — every 24h gap exceeded 2*6h and reset the
            # streak to 1 forever, which is exactly what the five live cron-fail
            # keys were doing. Days 1-3 climb the ladder and are heard; from day
            # 4 the 72h rung swallows them.
            outcomes = []
            for _ in range(7):
                outcomes.append(notify("p0", "cron:x", "the indexer died", "cron-fail:daily"))
                clock[0] += 24 * 3600
            # The exact sequence, asserted rather than summarised — day 6 is the
            # 72h rung expiring, not a defect, and a looser assertion hid it.
            #   d1 rung1(6h)  send -> streak 2
            #   d2 24h>6h     send -> streak 3
            #   d3 24h>24h    send -> streak 4 window 72h
            #   d4 24h<72h    mute
            #   d5 48h<72h    mute
            #   d6 72h        send (carries "ripetuta 2x") -> rung 168h
            #   d7 24h<168h   mute      => 4 sends where there were 7, then 1/week
            check(
                "daily condition: 4 sends in 7 days, not 7",
                outcomes == ["sent", "sent", "sent", "deduped", "deduped", "sent", "deduped"],
            )
            lstate = json.loads((ladder / "state.json").read_text())
            check(
                "…and the ladder actually CLIMBED (streak > 1)",
                int(lstate["dedup"]["cron-fail:daily"]["streak"]) > 1,
            )
            sent_text = (ladder / "sent-dry.jsonl").read_text()
            check(
                "…and the escape carries how much it repeated while muted",
                "ripetuta" in sent_text,
            )

            # INNOCENCE 1: a condition that genuinely DIES must come back at full
            # volume — 48h of silence is past the 36h floor, so the next hit is a
            # NEW BIRTH. Assert the streak, not the outcome: a first draft checked
            # `== "sent"`, which is true whether the ladder resets or climbs, so a
            # mutation that raised the floor to 500h sailed straight through it.
            # The observable that actually distinguishes the two worlds is the rung.
            clock[0] += 48 * 3600
            notify("p0", "cron:y", "the mirror died", "cron-fail:intermittent")
            clock[0] += 48 * 3600
            check(
                "a condition silent past the floor is REBORN (streak back to 1)",
                notify("p0", "cron:y", "the mirror died", "cron-fail:intermittent") == "sent"
                and int(
                    json.loads((ladder / "state.json").read_text())["dedup"][
                        "cron-fail:intermittent"
                    ]["streak"]
                )
                == 1,
            )

            # INNOCENCE 2: the floor must be inert wherever 2*win already exceeds
            # it. Touching the high rungs would change death semantics for the
            # chatty conditions that ALREADY climb correctly today.
            check(
                "floor is inert from rung 2 up",
                _death_silence_h(2) == 2 * _mute_window_h(2)
                and _death_silence_h(3) == 2 * _mute_window_h(3)
                and _death_silence_h(4) == 2 * _mute_window_h(4),
            )
            check("floor bites only at rung 1", _death_silence_h(1) == DEATH_FLOOR_H)
        finally:
            time.time = real_time
            os.environ["TG_SPOOL_DIR"] = str(spool)

        # ---- board routing (2026-09-21). GUILT and INNOCENCE both, because
        # this gate decides what wakes a human at 3am: a routing that swallows
        # a credential failure is as broken as one that pages for a cron.
        global OWNER_FAMILIES
        _saved_families = OWNER_FAMILIES
        with tempfile.TemporaryDirectory() as bd:
            board = Path(bd) / "board.jsonl"
            routed_spool = Path(bd) / "spool"
            os.environ["TG_SPOOL_DIR"] = str(routed_spool)
            os.environ["TG_BOARD_PATH"] = str(board)
            ACT_ROUTING_ENABLED = True
            OWNER_FAMILIES = frozenset({"cost-breaker-deadman", "price-review", "disk-watchdog"})
            try:
                check("entity match, not substring",
                      _owner_reserved("cost-breaker-deadman:governance-mute")
                      and not _owner_reserved("price-review-bot:x"))
                check("a key with no ':' is its own family",
                      _owner_reserved("disk-watchdog") and not _owner_reserved("dlq-terminal"))

                # The SHIPPED default, not the pinned fixture: both families that
                # end in "scan a QR code" must be reserved. They are two names for
                # one physical fault and only one of them is loud enough to show
                # up in the sent-p0 archive — the quiet one is the trap.
                check("both QR-relink families are reserved by DEFAULT",
                      {"wa-bridge", "wa-mirror-bridge-liveness"} <= _saved_families)

                # GUILT: work an LLM seat can close never reaches the owner.
                check("p0 a seat can cure is routed",
                      notify("p0", "cron:x", "the indexer died", "cron-fail:indexer") == "spooled")
                rows = [json.loads(ln) for ln in board.read_text().splitlines() if ln.strip()]
                check("routed row lands on the board, pending, auditable",
                      len(rows) == 1 and rows[0]["status"] == "pending"
                      and rows[0]["origin_tier"] == "p0"
                      and rows[0]["job"] == "cron-fail:indexer"
                      and rows[0]["cure_lane"]["owner"] == "seat")
                # The routed p0 must NOT arrive HIGH: the SessionStart receptor
                # renders HIGH first, so HIGH here would just move the 10.5/day
                # from Telegram onto the owner's board.
                check("a routed p0 is NORMAL on the board, never HIGH",
                      rows[0]["priority"] == "NORMAL")

                # The ladder governs the board too: a 15-minute repeat must not
                # append a row every 15 minutes (the W61 storm, in reverse).
                check("a routed repeat is deduped, not appended twice",
                      notify("p0", "cron:x", "the indexer died", "cron-fail:indexer") == "deduped"
                      and len([ln for ln in board.read_text().splitlines() if ln.strip()]) == 1)

                # INNOCENCE 1: what only the owner can close still pages him.
                check("a credential failure is NOT routed",
                      notify("p0", "meta", "token revoked", "cost-breaker-deadman:x") == "sent")

                # An explicit act tier is board-only and NORMAL, never HIGH.
                check("explicit act tier is NORMAL",
                      notify("act", "seat", "tidy this", "housekeeping:x") == "spooled")
                rows = [json.loads(ln) for ln in board.read_text().splitlines() if ln.strip()]
                check("act tier row is NORMAL", rows[-1]["priority"] == "NORMAL")

                # INNOCENCE 2: an unwritable board must not EAT the alarm.
                os.environ["TG_BOARD_PATH"] = "/dev/null/nope/board.jsonl"
                check("unwritable board fails OPEN to the human",
                      notify("p0", "cron:x", "another death", "cron-fail:other") == "sent")

                # INNOCENCE 3: the kill switch restores the old world whole.
                ACT_ROUTING_ENABLED = False
                os.environ["TG_BOARD_PATH"] = str(board)
                check("kill switch restores paging",
                      notify("p0", "cron:x", "yet another", "cron-fail:third") == "sent")
            finally:
                OWNER_FAMILIES = _saved_families
                os.environ.pop("TG_BOARD_PATH", None)
                os.environ["TG_SPOOL_DIR"] = str(spool)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", choices=TIERS)
    ap.add_argument("--source", default="unknown")
    ap.add_argument("--dedup-key", default="")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("text", nargs="*")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.tier:
        ap.error("--tier is required")

    text = " ".join(args.text).strip() or sys.stdin.read().strip()
    if not text:
        return 0
    try:
        status = notify(args.tier, args.source, text, args.dedup_key)
        print(f"tg_notify: {status}", file=sys.stderr)
    except Exception as exc:  # NEVER fail the caller
        try:
            _append(_spool_dir(), "pending.jsonl",
                    {"ts": time.time(), "tier": args.tier, "source": args.source,
                     "text": text, "gateway_error": str(exc)[:200]})
        except Exception:
            pass
        print(f"tg_notify: internal error ({exc}) — best-effort spooled", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
# PWC-7054 probe (draft PR, never merged): a change to this file alone must run the cron-wrapper corpus.
