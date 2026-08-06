"""Telegram alerter with md5 dedup — routes through the notification gateway.

Since 2026-07-07 (cohort-2, PR #2067 follow-up) the network send is delegated
to scripts/tg_notify.py: CRITICAL/DEADMAN → tier p0 (immediate, daily budget),
WARNING/INFO → tier digest (grouped 2×/day). The gateway owns token resolution
(env → secrets file → ssh relay) and its own 6h dedup; the local md5 dedup here
stays as a 1h fast-path that saves a subprocess. Return contract: True when
the operator has the news (sent / spooled / already delivered inside the mute
window), False only when it did not get through.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

DEDUP_FILE = os.path.expanduser("~/.agent/decisions/alert_dedup.json")
DEDUP_WINDOW_S = 3600  # 1 hour
ESCALATION_COOLDOWN_S = 14400  # D1.2: 4h per-job cooldown to prevent alert storms
_ESCALATION_STATE_FILE = os.path.expanduser("~/.agent/decisions/escalation_cooldown.json")


def _load_dedup() -> dict:
    try:
        return json.loads(open(DEDUP_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_dedup(data: dict) -> None:
    with open(DEDUP_FILE, "w") as f:
        json.dump(data, f)


def _is_duplicate(key: str) -> bool:
    data = _load_dedup()
    entry = data.get(key)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < DEDUP_WINDOW_S


def _mark_sent(key: str) -> None:
    data = _load_dedup()
    data[key] = {"ts": time.time()}
    # Prune old entries
    data = {k: v for k, v in data.items() if (time.time() - v["ts"]) < DEDUP_WINDOW_S * 24}
    _save_dedup(data)


def _load_escalation_state() -> dict:
    try:
        return json.loads(open(_ESCALATION_STATE_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_escalation_state(data: dict) -> None:
    with open(_ESCALATION_STATE_FILE, "w") as f:
        json.dump(data, f)


def check_escalation_cooldown(job_id: str) -> bool:
    """D1.2: Returns True if alert for this job is on cooldown (should NOT send)."""
    data = _load_escalation_state()
    sent_at = data.get(job_id, {}).get("escalation_sent_at", 0)
    return (time.time() - sent_at) < ESCALATION_COOLDOWN_S


def mark_escalation_sent(job_id: str) -> None:
    """D1.2: Record that an escalation alert was just sent for this job."""
    data = _load_escalation_state()
    # Prune entries older than 7 days
    cutoff = time.time() - 7 * 86400
    data = {k: v for k, v in data.items() if v.get("escalation_sent_at", 0) > cutoff}
    data[job_id] = {"escalation_sent_at": time.time(), "_writer": "alerter"}
    _save_escalation_state(data)


def _remember(key: str) -> None:
    """Record the send WITHOUT letting a bookkeeping failure rewrite the verdict.

    `_mark_sent` writes ~/.agent/decisions/alert_dedup.json. Called inside the
    same try/except that decides the return value, a read-only or full disk
    turns "the gateway spooled it" into `False` — and the callers now gate
    their 4h cooldown on that boolean, so a filesystem problem would silently
    re-arm every escalation. The local cache is an optimisation; it must never
    be able to contradict what the gateway said.
    """
    try:
        _mark_sent(key)
    except Exception as exc:  # noqa: BLE001
        print(f"[ALERT-WARN] local dedup cache not updated: {type(exc).__name__}: {exc}")


def _gateway_script() -> str:
    """Locate scripts/tg_notify.py relative to this file, NUZANTARA_ROOT fallback."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tg_notify.py")
    if os.path.isfile(here):
        return here
    root = os.environ.get("NUZANTARA_ROOT", os.path.expanduser("~/nuzantara"))
    return os.path.join(root, "scripts", "tg_notify.py")


def send_alert(message: str, level: str = "INFO", condition: str = "") -> bool:
    """
    Send Telegram alert via the notification gateway (tg_notify.py), with dedup.
    Returns True when the GATEWAY HAS TAKEN RESPONSIBILITY for it — sent, or
    durably spooled for the next digest, or deduped because it already carried
    this condition inside its mute window. Deliberately not "the operator read
    it": `spooled` means the durable queue owns it, which is the bar the whole
    spool-on-failure design (W55) is built on, and the strongest promise a
    caller can be given synchronously. False means the gateway did NOT take it,
    and only then is retrying in five minutes right.
    level: INFO | WARNING | CRITICAL | DEADMAN.

    Tier mapping: CRITICAL/DEADMAN → p0 (immediate, daily budget);
    WARNING/INFO → digest (ONE grouped message 2×/day).

    `condition` NAMES what is wrong, independently of how it is being measured
    right now ("blind_heal_loop", not "16 jobs parked for 99 cycles"). Pass it
    wherever a call site knows its own condition — a name survives rewording of
    the message, which a derived key cannot.

    KEY, and why this changed (2026-08-06, measured on the live 31-day spool):
    this function used to pass `--dedup-key sentinel:<md5(message)>`, and the
    message carries the counter. 378 sentinel events produced 255 DISTINCT keys
    — 36 real conditions wearing 255 identities. An explicit key that MOVES with
    the measurement is worse than no key at all: it wins over the gateway's own
    `condition_identity()` (explicit beats derived) and then defeats every mute
    window, because each re-measurement looks like a brand-new condition.

    So: a named `condition` → `sentinel:<condition>`, stable by construction.
    No name → pass NO key, and let the gateway derive one from the message with
    measurements stripped. That is one implementation of the rule, living where
    the policy lives; re-implementing the normaliser here would create the very
    two-constants-that-must-agree drift this organism keeps relapsing into.

    Replayed over the same 378 events (29.3 days) with the escalating ladder,
    scoring BOTH branches of `dedup_key or derived` — the named producers by
    their name, the unnamed ones through condition_identity() — sentinel drops
    from 12.90 to 3.41 messages/day, and from 5.73 to 0.24/day on p0.
    """
    # LOCAL fast-path only — a guard that saves a subprocess when the SAME
    # alert repeats inside DEDUP_WINDOW_S. It is deliberately NOT the
    # suppression policy (the gateway owns that): its failure mode must be
    # "spawns a subprocess the gateway then dedups", never a lost alert.
    #
    # It keys on (level, condition, message), not on the message alone. Text
    # alone was a collider the moment `condition` existed: two workers whose
    # only difference is the condition ("worker unavailable" for worker:a and
    # worker:b) shared one md5, so the second returned False HERE and the
    # gateway never saw worker:b at all. Same for an INFO that a CRITICAL then
    # repeats verbatim — a severity upgrade is news, and this layer must not
    # be the one that eats it.
    # Length-prefixed, not separator-joined. \x1f was better than `|` and still
    # not injective: condition="a" with message="b\x1fc" serialises exactly like
    # condition="a\x1fb" with message="c", and nothing validates that a message
    # cannot contain the separator. A length prefix cannot be forged by data.
    _parts = (level, condition, message)
    dedup_key = hashlib.md5(
        "".join(f"{len(x)}:{x}" for x in _parts).encode()
    ).hexdigest()
    if _is_duplicate(dedup_key):
        # TRUE — the same answer the gateway gives for its own duplicate, and
        # for the same reason: this exact alert went out within the hour, so
        # the gateway has it. Returning False here while the gateway's dedup
        # returns True would make one meaning wear two values, and the callers
        # now gate their 4h cooldown on that value: a lost escalation-state
        # file plus a warm local dedup would leave the cooldown permanently
        # unmarked. The separator is \x1f (unit separator, never in a message)
        # so `condition="a"|message="b|c"` cannot collide with
        # `condition="a|b"|message="c"`.
        return True

    prefix = {"INFO": "🔧", "WARNING": "🟡", "CRITICAL": "🔴", "DEADMAN": "⚫"}.get(level, "ℹ️")
    # Strip Markdown formatting — gateway sends plain text
    clean_message = message.replace("*", "").replace("`", "").replace("_", "-")
    full_message = f"{prefix} Sentinel | {clean_message}"
    tier = "p0" if level in ("CRITICAL", "DEADMAN") else "digest"

    # W55 retry lives inside the gateway now (spool-on-failure is strictly
    # better than 3 urllib attempts: a lost send resurfaces in the next digest).
    argv = [sys.executable, _gateway_script(), "--tier", tier, "--source", "sentinel"]
    if condition:
        # LEVEL is part of the identity. The gateway resolves the key BEFORE it
        # looks at the tier (tg_notify.py: `key = dedup_key or ...`, then the
        # dedup block returns "deduped" whatever the tier), so a key that spans
        # severities lets a WARNING mute the CRITICAL that follows it. The
        # tier-escalation family does exactly that: one job is classified
        # UNKNOWN/WARNING and later DETERMINISTIC/CRITICAL, and the upgrade is
        # the whole point of the alert. A repeat at the SAME severity still
        # collapses, which is what the ladder is for.
        argv += ["--dedup-key", f"sentinel:{condition}:{level.lower()}"]
    argv += ["--", full_message]

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        # tg_notify prints "tg_notify: <outcome>" on STDERR (stdout stays clean
        # for callers) — scan both streams, last line wins.
        raw = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        outcome = ""
        for line in raw.splitlines():
            if line.startswith("tg_notify:"):
                outcome = line.split(":", 1)[1].strip().split(" ")[0]
        if outcome in ("sent", "spooled", "logged", "p0_overflow_spooled", "p0_unsent_spooled"):
            _remember(dedup_key)
            return True
        if outcome == "deduped":
            # TRUE, and this is load-bearing (changed 2026-08-06 together with
            # gating `mark_escalation_sent` on this return value).
            #
            # "deduped" does not mean the news failed — it means the gateway
            # already took THIS condition inside the current mute window. The
            # caller's question is "is this news the gateway's problem now?",
            # and the answer is yes. Returning False conflated it with a broken
            # pipe, and once the callers started gating their 4h cooldown on
            # this value, that conflation would have re-armed the alert every 5
            # minutes for the whole window — a subprocess storm that changes no
            # message, because the gateway would dedup every one of them.
            #
            # False is now reserved for "it did not get through", which is the
            # only case where retrying in five minutes is the right behaviour.
            _remember(dedup_key)
            return True
        print(f"[ALERT-FAILED] gateway outcome={outcome or 'empty'} rc={proc.returncode} err={(proc.stderr or '')[:200]}")
        return False
    except Exception as e:
        print(f"[ALERT-FAILED] gateway unreachable: {type(e).__name__}: {e}")
        return False


def send_daily_report(fleet_status: dict) -> None:
    """Send daily fleet health summary."""
    healthy = sum(1 for j in fleet_status.values() if j.get("status") == "ok")
    total = len(fleet_status)
    stale = [j for j, s in fleet_status.items() if s.get("status") == "stale"]
    failed = [j for j, s in fleet_status.items() if s.get("status") == "failed"]

    lines = [f"🤖 *Fleet Status* — {total} automations"]
    lines.append(f"✅ {healthy}/{total} healthy")
    if stale:
        lines.append(f"⚠️ Stale: {', '.join(stale)}")
    if failed:
        lines.append(f"🔴 Failed: {', '.join(failed)}")

    send_alert("\n".join(lines), level="INFO")
