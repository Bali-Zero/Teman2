#!/usr/bin/env python3
"""meta_one_steward.py — the Meta One Advanced Access ledger + probe (Pro-resident).

Spec: docs/marketing/meta-one-advanced-playbook.md §4.3/4.4. Deterministic,
stdlib + urllib only. Runs daily 06:20 WITA through
scripts/meta-one-steward.sh; nothing it does publishes, schedules, or writes
to a Meta endpoint — it only reads the token's health and the local queue,
and keeps `shared/meta_one/ledger.json` honest so nothing paid-for expires
unused.

Subcommands:
    tick     — probe -> ingest -> ledger -> digest -> heartbeat (the cron entry)
    use      — record one benefit spend, idempotent on (month, benefit, ref)
    status   — print the current month's ledger (--json for the raw record)
    --selftest — temp world, no HOME, no network; must name a dead AND a
                 healthy verdict and exit 0 only if each tick's heartbeat
                 status equals that tick's own verdict.

Contracts:
    - The token value is NEVER logged, printed, or persisted. Any URL
      fragment carrying `access_token=...` is redacted before it reaches an
      exception message, a log line or a Telegram text (W-class #4, secret
      in the clear).
    - `unknown` (network/timeout/unexpected-status) is NOT `dead` — only an
      HTTP 400/401 body naming OAuthException classifies as dead. Guilt
      needs positive evidence; the absence of a clean answer is innocence,
      not condemnation (superscar #3, guard-over/under-match).
    - The heartbeat's `status` always equals this run's own verdict — `ok`
      (token alive, nothing expiring), `warning` (token dead/unknown, a
      link-benefit quota expiring, or the newest export past 35 days), or
      `error` (unhandled exception — the heartbeat is still written before
      re-raising the non-zero exit, superscar #2 esiste!=armato).
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from scripts.lib.heartbeat import organism_heartbeat  # noqa: E402
from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

ORGAN_ID = "pro.meta_one_steward"

# Meta Help Centre article 960854640235758 (read 2026-09-16): Advanced Access
# monthly caps for a Business Agent-approved account. One constant, dated,
# per spec §4.3 — never hard-code a quota number anywhere else in this file.
ADVANCED_QUOTAS: dict[str, int] = {
    "ig_post_link": 4,
    "ig_reel_link": 4,
    "fb_post_link": 8,
    "fb_reel_link": 8,
    "support_chat": 1,
    "content_credit": 2,
}

# The four benefits the "quota expiring" P0 rule watches (spec §4.3).
LINK_BENEFITS: tuple[str, ...] = ("ig_post_link", "ig_reel_link", "fb_post_link", "fb_reel_link")

TOKEN_ENV_VARS: tuple[str, ...] = ("INSTAGRAM_ACCESS_TOKEN", "IG_LONG_LIVED_TOKEN")

GRAPH_ME_URL = "https://graph.instagram.com/me?fields=id,username"
GRAPH_METRICS_URL = "https://graph.instagram.com/me?fields=followers_count,media_count"
GRAPH_INSIGHTS_URL = (
    "https://graph.instagram.com/me/insights"
    "?metric=reach,profile_links_taps,follows_and_unfollows"
    "&period=day&metric_type=total_value"
)

EXPORT_STALE_DAYS = 35
QUOTA_EXPIRING_DAYS = 5
QUOTA_EXPIRING_FRACTION = 0.5
HTTP_TIMEOUT_S = 15.0

# All calendar-day semantics (month bucket, days-to-month-end, dead-since
# date) are computed on the WITA business day, not UTC — a 00:00-08:00 UTC
# tick is already the next WITA day. Timestamps (ts, updated_at) stay UTC.
WITA = ZoneInfo("Asia/Makassar")

_ACCESS_TOKEN_RE = re.compile(r"access_token=[^&\s]+")


# ---------------------------------------------------------------- paths


def state_dir() -> Path:
    return Path(os.environ.get("META_ONE_STATE_DIR", str(_REPO / "shared" / "meta_one")))


def ledger_path() -> Path:
    return state_dir() / "ledger.json"


def usage_path() -> Path:
    return state_dir() / "usage.jsonl"


def metrics_dir() -> Path:
    return state_dir() / "metrics"


def exports_dir() -> Path:
    return state_dir() / "exports"


def queue_path() -> Path:
    default = str(Path.home() / "nuzantara" / "apps" / "war-room" / "output" / "queue" / "human-review-queue.json")
    return Path(os.environ.get("META_ONE_QUEUE_JSON", default))


# ---------------------------------------------------------------- redaction


def _redact(text: str) -> str:
    """Strip any `access_token=...` fragment AND any raw configured token
    VALUE (read live from TOKEN_ENV_VARS) before it reaches a log/message.

    The `access_token=` regex alone only catches the token when it is still
    attached to that query-param spelling; an exception message that embeds
    the bare token value (e.g. a urllib error echoing the full request URL
    without that literal, or a downstream library reformatting it) would
    pass through untouched. Every configured token's raw value is therefore
    also scrubbed by literal substring replacement, on every call.
    """
    redacted = _ACCESS_TOKEN_RE.sub("access_token=REDACTED", text)
    for name in TOKEN_ENV_VARS:
        val = os.environ.get(name)
        if val:
            redacted = redacted.replace(val, "REDACTED")
    return redacted


# ---------------------------------------------------------------- atomic IO


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_ledger() -> dict[str, Any]:
    p = ledger_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------- token probe


def _get_token() -> str | None:
    for name in TOKEN_ENV_VARS:
        val = os.environ.get(name)
        if val:
            return val
    return None


def _http_get(url: str, timeout: float) -> tuple[int, str]:
    """GET url. HTTP error responses return (code, body) rather than raising —
    only network/timeout/other failures propagate as exceptions."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        return exc.code, body


def probe_token(
    token: str | None,
    *,
    timeout: float = HTTP_TIMEOUT_S,
    fetch: Callable[[str, float], tuple[int, str]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Classify the token: 'alive' | 'dead' | 'unknown'. Never raises.

    'dead' requires positive evidence: HTTP 400/401 AND the parsed JSON
    body's `error.type == "OAuthException"` (or `error.code == 190`) — never
    a substring match against truncated text. Classification always parses
    the FULL body first; truncation happens only afterwards, for the
    diagnostic copy that gets stored/logged — a long body can never hide the
    evidence, and an unrelated error.type whose free-text `message` merely
    mentions "OAuthException" can never manufacture it either way.
    Everything else — no token, network error, timeout, an unexpected
    status (incl. 500/502/503 even if their body mentions OAuthException), a
    200 without a username — is 'unknown', which is warning-worthy but
    NEVER treated as dead (guilt needs evidence).
    """
    if not token:
        return "unknown", {"reason": "no-token"}
    fetch = fetch or _http_get
    url = f"{GRAPH_ME_URL}&access_token={token}"
    try:
        status, body = fetch(url, timeout)
    except Exception as exc:  # network/timeout/other — never dead
        return "unknown", {"reason": _redact(str(exc))}

    if status == 200:
        try:
            data = json.loads(body)
        except Exception:
            return "unknown", {"reason": "bad-json", "http_status": status}
        if isinstance(data, dict) and data.get("username"):
            return "alive", {"username": data.get("username"), "id": data.get("id")}
        return "unknown", {"reason": "no-username-in-200", "http_status": status}

    redacted_body = _redact(body)[:500]  # diagnostic copy ONLY — never used for classification

    if status in (400, 401):
        error_type = None
        error_code = None
        try:
            data = json.loads(body)  # full, untruncated body
            if isinstance(data, dict):
                err = data.get("error")
                if isinstance(err, dict):
                    error_type = err.get("type")
                    error_code = err.get("code")
        except Exception:
            pass
        if error_type == "OAuthException" or error_code == 190:
            return "dead", {"http_status": status, "error_type": error_type, "body": redacted_body}
        return "unknown", {"http_status": status, "error_type": error_type, "body": redacted_body}

    return "unknown", {"http_status": status, "body": redacted_body}


def _fetch_metrics(token: str, now: datetime, *, timeout: float = HTTP_TIMEOUT_S, fetch: Callable | None = None) -> dict[str, Any]:
    """Best-effort: followers/media counts + day insights. Tolerates missing
    metrics — a partial 200 or a failed insights call never aborts the tick."""
    fetch = fetch or _http_get
    result: dict[str, Any] = {"followers_count": None, "media_count": None, "insights": {}}
    try:
        status, body = fetch(f"{GRAPH_METRICS_URL}&access_token={token}", timeout)
        if status == 200:
            data = json.loads(body)
            result["followers_count"] = data.get("followers_count")
            result["media_count"] = data.get("media_count")
    except Exception:
        pass
    try:
        status, body = fetch(f"{GRAPH_INSIGHTS_URL}&access_token={token}", timeout)
        if status == 200:
            data = json.loads(body)
            for item in data.get("data", []) or []:
                name = item.get("name")
                tv = item.get("total_value") or {}
                if name:
                    result["insights"][name] = tv.get("value")
    except Exception:
        pass
    try:
        day_file = metrics_dir() / f"{now.strftime('%Y-%m-%d')}.json"
        _atomic_write_json(day_file, {**result, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    except Exception:
        pass
    return result


# ---------------------------------------------------------------- quota math


def _to_wita(now: datetime) -> datetime:
    """Timestamps are stored/compared in UTC; every CALENDAR-DAY decision
    (month bucket, days-to-month-end, dead-since date) is made on the WITA
    business day — a tick at 2026-09-30T22:30:00Z is already 2026-10-01
    06:30 in Asia/Makassar, so it must bucket into October, not September."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(WITA)


def _month_key(now: datetime) -> str:
    return _to_wita(now).strftime("%Y-%m")


def days_to_month_end(now: datetime) -> int:
    local = _to_wita(now)
    if local.month == 12:
        last_day = 31
    else:
        first_of_next = local.replace(month=local.month + 1, day=1)
        last_day = (first_of_next - timedelta(days=1)).day
    return last_day - local.day


def build_benefits(usage_counts: dict[str, int]) -> dict[str, dict[str, int]]:
    return {b: {"used": usage_counts.get(b, 0), "quota": q} for b, q in ADVANCED_QUOTAS.items()}


def quota_expiring(benefits: dict[str, dict[str, int]], days_left: int) -> bool:
    if days_left > QUOTA_EXPIRING_DAYS:
        return False
    for b in LINK_BENEFITS:
        info = benefits.get(b, {})
        quota = info.get("quota", 0)
        used = info.get("used", 0)
        if quota > 0 and (used / quota) < QUOTA_EXPIRING_FRACTION:
            return True
    return False


def read_usage(month: str) -> dict[str, int]:
    counts: dict[str, int] = {b: 0 for b in ADVANCED_QUOTAS}
    p = usage_path()
    if not p.is_file():
        return counts
    seen: set[tuple[Any, Any, Any]] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("month") != month:
            continue
        key = (rec.get("month"), rec.get("benefit"), rec.get("ref"))
        if key in seen:
            continue
        seen.add(key)
        b = rec.get("benefit")
        if b in counts:
            counts[b] += 1
    return counts


def _usage_key_exists(key: tuple[Any, Any, Any]) -> bool:
    p = usage_path()
    if not p.is_file():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if (rec.get("month"), rec.get("benefit"), rec.get("ref")) == key:
            return True
    return False


def cmd_use(benefit: str, ref: str, *, now: datetime | None = None) -> int:
    if benefit not in ADVANCED_QUOTAS:
        print(f"meta_one_steward: unknown benefit {benefit!r} (known: {sorted(ADVANCED_QUOTAS)})", file=sys.stderr)
        return 2
    now = now or datetime.now(timezone.utc)
    month = _month_key(now)
    key = (month, benefit, ref)
    p = usage_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Interprocess lock: check-then-append must be one atomic step, or two
    # concurrent `use` calls for the same key can both pass the existence
    # check and each append a line (harmless — the reader dedupes — but not
    # actually idempotent). The lock file is a sidecar, never the data file.
    lock_fh = open(p.with_suffix(p.suffix + ".lock"), "a")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        if _usage_key_exists(key):
            print(f"already recorded: {month} {benefit} {ref}")
            return 0
        rec = {"month": month, "benefit": benefit, "ref": ref, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        print(f"recorded: {month} {benefit} {ref}")
        return 0
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()


# ---------------------------------------------------------------- queue + export


def read_queue_counts() -> dict[str, Any]:
    result: dict[str, Any] = {"drafted": 0, "published": 0, "last_published_at": None}
    p = queue_path()
    if not p.is_file():
        return result
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return result
    if isinstance(data, dict):
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []
    drafted = 0
    published = 0
    last_pub: str | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        state = item.get("state")
        if state == "drafted":
            drafted += 1
        elif state == "published":
            published += 1
            # Real Pro queue schema (verified live 2026-09-16): the key is
            # `instagram_published_at`, not `published_at` — the latter is
            # kept as a fallback only in case an older/synthetic queue uses it.
            pub_at = item.get("instagram_published_at") or item.get("published_at")
            if pub_at and (last_pub is None or pub_at > last_pub):
                last_pub = pub_at
    result.update({"drafted": drafted, "published": published, "last_published_at": last_pub})
    return result


def newest_export_mtime() -> float | None:
    d = exports_dir()
    if not d.is_dir():
        return None
    newest: float | None = None
    for p in d.rglob("*.csv"):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def export_age_days(now: datetime) -> float | None:
    mtime = newest_export_mtime()
    if mtime is None:
        return None
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


# ---------------------------------------------------------------- messages


def _digest_text(entry: dict[str, Any]) -> str:
    lines = ["Meta One — riepilogo giornaliero"]
    benefits = entry.get("benefits", {})
    for b in ADVANCED_QUOTAS:
        info = benefits.get(b, {"used": 0, "quota": ADVANCED_QUOTAS[b]})
        lines.append(f"- {b}: {info['used']}/{info['quota']}")
    lines.append(f"Giorni a fine mese: {entry.get('days_to_month_end')}")
    q = entry.get("queue", {})
    lines.append(f"Coda: {q.get('drafted', 0)} bozze, {q.get('published', 0)} pubblicate")
    age = entry.get("export_age_days")
    if age is not None:
        lines.append(f"Export piu recente: {age:.1f} giorni fa")
    else:
        lines.append("Export piu recente: nessuno trovato")
    lines.append(f"Stato token: {entry.get('token_state')}")
    return "\n".join(lines)


def _p0_token_dead_text(dead_since: str | None) -> str:
    since = dead_since or "data sconosciuta"
    return f"Token Instagram morto dal {since}: nessuna telemetria; serve nuovo token (Zero)."


def _p0_quota_expiring_text(days_left: int, benefits: dict[str, dict[str, int]]) -> str:
    expiring = [
        b for b in LINK_BENEFITS
        if benefits.get(b, {}).get("quota", 0) > 0
        and (benefits[b]["used"] / benefits[b]["quota"]) < QUOTA_EXPIRING_FRACTION
    ]
    names = ", ".join(expiring)
    return f"Quota Meta One in scadenza tra {days_left} giorni sotto il 50% di utilizzo: {names}."


# ---------------------------------------------------------------- telegram


def _tg_notify(tier: str, dedup_key: str, text: str) -> bool:
    """Route through the tg_notify gateway and read its VERDICT — never its
    subprocess return code alone. tg_notify.py's own contract is "never
    fails the caller: any internal error -> spool best-effort, exit 0", so
    `returncode == 0` is true on almost every call regardless of whether the
    message actually reached Telegram — a caller that stops there cannot
    tell a live "sent" P0 from one that was merely `spooled`/`p0_unsent_spooled`
    because the daily budget was exhausted or the token was missing. This
    parses the gateway's `tg_notify: <verdict>` stderr line the sanctioned
    way (same pattern as drive_token_watchdog.py / price_review_sentinel.py
    / wr2_daily_reconciler.py): a digest is "delivered" once it is
    `spooled`/`deduped` (that IS the digest tier's normal, expected
    outcome — it is flushed later in a batch); anything else (p0, log) must
    see the real-time `sent` verdict to count as delivered.
    """
    text = _redact(text)  # defense-in-depth: last gate before the subprocess argv
    try:
        script = _REPO / "scripts" / "tg_notify.py"
        if not script.is_file():
            return False
        res = subprocess.run(
            [
                sys.executable, str(script),
                "--tier", tier,
                "--source", "meta-one-steward",
                "--dedup-key", dedup_key,
                "--", text,
            ],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(res.stderr)
        return res.returncode == 0 and (
            verdict in {"spooled", "deduped"} if tier == "digest" else gateway_delivered(verdict)
        )
    except Exception:
        return False


# ---------------------------------------------------------------- tick core


def tick(
    *,
    now: datetime | None = None,
    probe_fn: Callable[..., tuple[str, dict[str, Any]]] | None = None,
    tg_notify_fn: Callable[[str, str, str], bool] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    probe_fn = probe_fn or probe_token
    notify = tg_notify_fn or _tg_notify

    month = _month_key(now)
    ledger = load_ledger()
    prev_entry = ledger.get(month, {})

    token = _get_token()
    state, _details = probe_fn(token)

    # token_dead_since lives OUTSIDE the month-keyed entries (ledger["_token"])
    # so it survives both a month rollover and a dead->unknown->dead sequence:
    # `unknown` is not evidence of anything (guilt needs evidence, per the
    # classifier's own contract) so it must never erase a previously-observed
    # dead date, and it must never manufacture a fresh one either. Only a
    # CONFIRMED `alive` clears it.
    token_meta = ledger.get("_token", {})
    prev_dead_since = token_meta.get("dead_since") if isinstance(token_meta, dict) else None
    if state == "dead":
        dead_since = prev_dead_since or _to_wita(now).strftime("%Y-%m-%d")
    elif state == "unknown":
        dead_since = prev_dead_since
    else:  # alive
        dead_since = None
    ledger["_token"] = {"dead_since": dead_since}

    followers_count = prev_entry.get("followers_count")
    if state == "alive" and token:
        metrics = _fetch_metrics(token, now)
        if metrics.get("followers_count") is not None:
            followers_count = metrics["followers_count"]

    usage_counts = read_usage(month)
    benefits = build_benefits(usage_counts)
    days_left = days_to_month_end(now)
    queue = read_queue_counts()
    exp_age = export_age_days(now)
    export_stale = exp_age is not None and exp_age > EXPORT_STALE_DAYS
    quota_flag = quota_expiring(benefits, days_left)

    if state in ("dead", "unknown") or quota_flag or export_stale:
        verdict = "warning"
    else:
        verdict = "ok"

    entry = {
        "benefits": benefits,
        "days_to_month_end": days_left,
        "token_state": state,
        "token_dead_since": dead_since,
        "followers_count": followers_count,
        "export_age_days": exp_age,
        "queue": queue,
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # A P0 that only SPOOLED (budget exhausted, gateway down, token missing)
    # is NOT the same as one that reached Telegram — surface that gap
    # instead of reading tg_notify's "never fails the caller, exit 0" as
    # success (the exact blind-caller shape this replaced). Any undelivered
    # P0 forces `warning` even in the (currently unreachable, but not
    # future-proof otherwise) case where the P0-triggering condition itself
    # did not already force it.
    p0_undelivered = False
    if state == "dead":
        if not notify("p0", "meta-one-token-dead", _p0_token_dead_text(dead_since)):
            p0_undelivered = True
    if quota_flag:
        if not notify("p0", "meta-one-quota-expiring", _p0_quota_expiring_text(days_left, benefits)):
            p0_undelivered = True
    notify("digest", "meta-one-steward-digest", _digest_text(entry))

    if p0_undelivered:
        verdict = "warning"
    entry["p0_undelivered"] = p0_undelivered

    ledger[month] = entry
    _atomic_write_json(ledger_path(), ledger)

    return {"verdict": verdict, "entry": entry}


def _run_tick_and_heartbeat(
    *,
    now: datetime | None = None,
    probe_fn: Callable[..., tuple[str, dict[str, Any]]] | None = None,
    tg_notify_fn: Callable[[str, str, str], bool] | None = None,
) -> dict[str, Any]:
    """Run one tick and write the heartbeat with the run's REAL verdict —
    on every path, including an unhandled exception (superscar #2:
    esiste!=armato — a crashed cron must still leave a true verdict) AND a
    heartbeat WRITE that itself fails (organism_heartbeat never raises — it
    reports failure by returning False, which a caller can silently ignore
    unless it checks)."""
    try:
        result = tick(now=now, probe_fn=probe_fn, tg_notify_fn=tg_notify_fn)
        hb_ok = organism_heartbeat(ORGAN_ID, result["verdict"], note=f"token={result['entry']['token_state']}")
        if not hb_ok:
            return {**result, "error": _redact("heartbeat write failed")}
        return {**result, "error": None}
    except Exception as exc:  # noqa: BLE001
        message = _redact(str(exc))
        organism_heartbeat(ORGAN_ID, "error", note=message[:200])
        return {"verdict": "error", "entry": {"token_state": "error"}, "error": message}


def cmd_tick(
    *,
    now: datetime | None = None,
    probe_fn: Callable[..., tuple[str, dict[str, Any]]] | None = None,
    tg_notify_fn: Callable[[str, str, str], bool] | None = None,
) -> int:
    result = _run_tick_and_heartbeat(now=now, probe_fn=probe_fn, tg_notify_fn=tg_notify_fn)
    if result["error"] is not None:
        print(f"meta_one_steward: tick failed: {result['error']}", file=sys.stderr)
        return 1
    return 0


def cmd_status(as_json: bool) -> int:
    now = datetime.now(timezone.utc)
    month = _month_key(now)
    ledger = load_ledger()
    entry = ledger.get(month)
    if as_json:
        print(json.dumps(entry or {}, indent=2, sort_keys=True))
        return 0
    if not entry:
        print(f"meta_one_steward: no ledger entry for {month} yet")
        return 0
    print(_digest_text(entry))
    return 0


# ---------------------------------------------------------------- selftest


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        state_d = Path(td) / "state"
        last_seen_d = Path(td) / "last_seen"
        queue_f = Path(td) / "queue.json"
        queue_f.write_text(json.dumps({"items": []}), encoding="utf-8")

        os.environ["META_ONE_STATE_DIR"] = str(state_d)
        os.environ["ORGANISM_LAST_SEEN_DIR"] = str(last_seen_d)
        os.environ["META_ONE_QUEUE_JSON"] = str(queue_f)
        os.environ["TG_DRY_RUN"] = "1"
        for var in TOKEN_ENV_VARS:
            os.environ.pop(var, None)

        calls = {"n": 0}

        def fake_probe(token: str | None, **_kw: Any) -> tuple[str, dict[str, Any]]:
            calls["n"] += 1
            if calls["n"] == 1:
                return "dead", {"http_status": 400}
            return "alive", {"username": "balizero_selftest", "id": "1"}

        def fake_notify(tier: str, dedup_key: str, text: str) -> bool:
            return True

        # Fixed instant, mid-month in BOTH UTC and WITA, far from any
        # month-end — the alive/empty-usage tick must be able to land on
        # 'ok' deterministically, not flip to 'warning' just because the
        # real wall clock happened to be within QUOTA_EXPIRING_DAYS of a
        # month boundary when someone ran --selftest.
        fixed_now = datetime(2026, 1, 15, 6, 20, tzinfo=timezone.utc)

        ok = True
        summaries = []
        expectations = [("dead", "warning"), ("alive", "ok")]
        for expected_state, expected_verdict in expectations:
            result = _run_tick_and_heartbeat(now=fixed_now, probe_fn=fake_probe, tg_notify_fn=fake_notify)
            token_state = result["entry"]["token_state"]
            verdict = result["verdict"]
            hb_path = last_seen_d / f"{ORGAN_ID}.json"
            hb = json.loads(hb_path.read_text(encoding="utf-8"))
            step_ok = (
                token_state == expected_state
                and verdict == expected_verdict
                and hb["status"] == verdict
            )
            if not step_ok:
                ok = False
            summaries.append(
                f"token_state={token_state} verdict={verdict} heartbeat={hb['status']} "
                f"expected=({expected_state},{expected_verdict})"
            )

        for line in summaries:
            print(f"selftest: {line}")
        return 0 if ok else 1


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meta_one_steward.py")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("tick")

    p_use = sub.add_parser("use")
    p_use.add_argument("--benefit", required=True)
    p_use.add_argument("--ref", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.cmd == "tick":
        return cmd_tick()
    if args.cmd == "use":
        return cmd_use(args.benefit, args.ref)
    if args.cmd == "status":
        return cmd_status(args.json)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
