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
  - Dedup: same key within TG_DEDUP_HOURS collapses to a counter (#flapping).
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
DEDUP_HOURS = _env_num("TG_DEDUP_HOURS", 6, float)
DRY_RUN = os.environ.get("TG_DRY_RUN", "") == "1"
RELAY_SSH = os.environ.get("TG_RELAY_SSH", "")  # e.g. "pro" on M5
RELAY_GATEWAY = os.environ.get(
    "TG_RELAY_GATEWAY", "/Users/nuzantara/Desktop/nuzantara/scripts/tg_notify.py"
)

TIERS = ("p0", "digest", "log")
API_TIMEOUT = 6


# ---------------------------------------------------------------- token chain
def _parse_env_file(path: Path) -> dict:
    out: dict = {}
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
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
    key = dedup_key or hashlib.sha1(f"{source}|{text[:160]}".encode()).hexdigest()[:16]

    record = {
        "ts": now,
        "tier": tier,
        "source": source,
        "machine": machine,
        "key": key,
        "text": text,
    }

    send_meta = False
    today = time.strftime("%Y-%m-%d", time.localtime(now))

    with _spool_lock(spool):
        state = _load_state(spool)
        dedup = state.setdefault("dedup", {})
        entry = dedup.get(key)
        if entry and now - entry.get("ts", 0) < DEDUP_HOURS * 3600:
            entry["count"] = entry.get("count", 1) + 1
            entry["last_text"] = text[:200]
            _save_state(spool, state)
            return "deduped"
        dedup[key] = {"ts": now, "count": 1, "last_text": text[:200]}
        # prune dedup entries older than 2 windows so state.json never balloons
        horizon = now - 2 * DEDUP_HOURS * 3600
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
            budget.update({"date": today, "sent": 0, "overflow": 0})

        if budget["sent"] >= P0_BUDGET:
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
        if budget.get("date") == today and budget.get("sent", 0) > 0:
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
        check("p0 sends (dry)", notify("p0", "t", "fire-1") == "sent")
        check("p0 sends (dry) 2", notify("p0", "t", "fire-2") == "sent")
        check("p0 over budget → spool", notify("p0", "t", "fire-3") == "p0_overflow_spooled")
        pending = (spool / "pending.jsonl").read_text().strip().splitlines()
        check("pending has digest+overflow", len(pending) == 2)
        check("log-only file exists", (spool / "log-only.jsonl").exists())
        sent_dry = (spool / "sent-dry.jsonl").read_text().strip().splitlines()
        check("dry sends: 2 p0 + 1 budget meta", len(sent_dry) == 3)
        state = json.loads((spool / "state.json").read_text())
        check("dedup counted ×2", any(v.get("count") == 2 for v in state["dedup"].values()))

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
