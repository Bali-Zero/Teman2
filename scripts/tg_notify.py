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
DEDUP_HOURS = _env_num("TG_DEDUP_HOURS", 6, float)
# A condition that PERSISTS is not news each time it is re-measured. After the
# first send, each further send of the same live condition mutes it for longer.
# Replayed over the real corpus (5202 events / 29.5d, 1525 of them P0, today
# 51.6 P0/day): identity alone with a flat 6h window leaves 28.9 P0/day, this
# ladder leaves 15.9, and re-tiering the 24 timer-driven sources to digest
# leaves 4.7 — which IS the real alarm rate (138 of 1525 P0 are alarms; the
# other 1387 are scheduled reports wearing an alarm's clothes).
#
# An earlier replay of this same line said 12.6 and "~3". It simulated a streak
# that never resets, so windows grew without bound and it under-counted; the
# shipped rule restarts the ladder when a condition goes quiet. The numbers
# above are from the replay that models what this file actually does.
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
DRY_RUN = os.environ.get("TG_DRY_RUN", "") == "1"
RELAY_SSH = os.environ.get("TG_RELAY_SSH", "")  # e.g. "pro" on M5
RELAY_GATEWAY = os.environ.get(
    "TG_RELAY_GATEWAY", "/Users/nuzantara/nuzantara/scripts/tg_notify.py"
)

TIERS = ("p0", "digest", "log")
API_TIMEOUT = 6


# ---------------------------------------------------------------- identity
# A condition's IDENTITY must not contain its MEASUREMENTS.
#
# The derived dedup key used to be sha1(source|text[:160]) — raw. Every one of
# the three loudest sources embeds a changing number inside those 160 chars
# ("= 4.7 MB", "reconnect_attempt=591", "for 115 consecutive cycles"), so every
# repeat hashed to a brand-new key and the dedup window never once applied.
# Measured on the live 31-day corpus: 5202 events collapsed to 2791 "distinct"
# conditions — i.e. dedup was decorative. With this normalisation: 362.
#
# Identity is the FIRST SENTENCE of the FIRST LINE. Everything after it is
# EVIDENCE (log tails, stack frames, counters) — unbounded variability that no
# prefix truncation can reliably exclude, which is why we cut on structure.
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
    tmp.replace(p)


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


def _append(spool: Path, name: str, record: dict) -> None:
    spool.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    # O_APPEND single-write keeps concurrent senders line-atomic (<4k).
    fd = os.open(str(spool / name), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
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
    except Exception:
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
            # Silent for more than two windows => the condition DIED. The next
            # occurrence is a new birth, so the ladder restarts from the top.
            if since > 2 * win:
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

        if budget["sent"] >= P0_BUDGET:
            # A cron JOB FAILURE draws on its own small reserve once the shared
            # budget is gone. Measured 2026-07-27 on Pro: the P0 budget is hit on
            # 8 of 21 days and 68% of it (155 of 228 sent P0s) is one chatty
            # source — so on a busy day a genuine existential alert loses its slot
            # to conversation notices. That is not hypothetical: on 2026-07-26 at
            # 03:21 "the Postgres backup failed" returned p0_overflow_spooled and
            # went to the digest, and production then spent 27 hours with no
            # backup at all.
            if key.startswith("cron-fail:") and budget.get("cron_reserve", 0) < CRON_FAIL_RESERVE:
                budget["cron_reserve"] = budget.get("cron_reserve", 0) + 1
                drew_from_reserve = True
                record["p0_cron_reserve"] = True
                _save_state(spool, state)
                over = False
            else:
                budget["overflow"] += 1
                record["p0_overflow"] = True
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
        global DRY_RUN, P0_BUDGET
        DRY_RUN, P0_BUDGET = True, 2
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
        global CRON_FAIL_RESERVE
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
