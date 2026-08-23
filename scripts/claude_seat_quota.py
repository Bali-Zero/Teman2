#!/usr/bin/env python3
"""claude_seat_quota.py — real weekly/session quota for every Claude seat on this machine.

WHY THIS EXISTS (2026-08-23): asked "how much weekly quota is left on the 6 seats?",
the honest answer used to be "not obtainable" — `claude` has no `usage` subcommand, and
`~/scripts/claude-max-usage-watcher.py` (Playwright scraping of claude.ai/settings/usage)
has been DEAD-GREEN for months: it runs hourly, exits 0, and reports SESSION_EXPIRED for
every account because its `~/.claude/usage-watcher/profiles/` directory is empty. It also
only ever knew 3 accounts. A watcher that cannot fail loudly is not a watcher.

The real source is the endpoint the CLI itself calls: GET /api/oauth/usage on
api.anthropic.com. Two facts make it usable, both measured, both non-obvious:

  1. THE CRON TOKENS CANNOT READ IT. A long-lived `CLAUDE_CODE_OAUTH_TOKEN_*` minted by
     `claude setup-token` gets HTTP 403 `permission_error: "OAuth token does not meet
     scope requirement user:profile"`. Only the INTERACTIVE credential stored in the
     macOS Keychain by `claude auth login` carries that scope. So quota is readable per
     LOGGED-IN PROFILE, never per cron seat — a machine whose profiles are logged out can
     hold six perfectly good tokens and still be unable to report a single percentage.

  2. THE KEYCHAIN COPY GOES STALE IN AN HOUR. `accessToken` lives ~1h; the CLI refreshes
     it lazily when it runs. Reading the Keychain cold therefore returns an expired token
     for any profile that has been idle, and the endpoint answers "OAuth access token has
     expired" — which looks exactly like "no data for this account". Measured on
     sianoantonello@ 2026-08-23: cold read = silence, after one real inference call =
     100% session / 95% weekly. So this tool WARMS each profile first (`claude auth
     status`, and `--deep` adds a 1-token inference for profiles that are still stale)
     and only then reads. Skipping the warm-up turns a saturated seat into a blank row.

Output: a table by default, `--json` for machines. Exit codes are the alerting surface:
  0 = every discovered profile reported a number
  1 = at least one profile could not be read (expired/revoked/no scope) — NEVER silent
  2 = zero profiles discovered, or the endpoint was unreachable for all of them
      (an empty run is an infrastructure failure masquerading as calm — never exit 0)

Never prints a token, an accessToken or a refreshToken, not even truncated.

Usage:
    python3 scripts/claude_seat_quota.py                 # table, warm + read
    python3 scripts/claude_seat_quota.py --json          # machine-readable
    python3 scripts/claude_seat_quota.py --deep          # force refresh on stale profiles
    python3 scripts/claude_seat_quota.py --warn-at 85    # exit 1 if any weekly >= 85%
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.anthropic.com"
USAGE_PATH = "/api/oauth/usage"
PROFILE_PATH = "/api/oauth/profile"
# The CLI identifies itself this way; the endpoint is part of its own OAuth surface.
UA = "claude-cli (external, cli)"
OAUTH_BETA = "oauth-2025-04-20"
KEYCHAIN_SERVICE_PREFIX = "Claude Code-credentials"
HTTP_TIMEOUT = 25


def keychain_services() -> list[str]:
    """Every 'Claude Code-credentials[-<hash>]' entry, one per logged-in profile."""
    try:
        out = subprocess.run(
            ["security", "dump-keychain"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = re.findall(r'"svce"<blob>="(Claude Code-credentials[^"]*)"', out)
    return sorted(set(found))


def access_token(service: str) -> str | None:
    """Pull the access token out of one Keychain entry. Never returned to the caller's log."""
    try:
        raw = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if raw.returncode != 0 or not raw.stdout.strip():
        return None
    try:
        blob = json.loads(raw.stdout)
    except json.JSONDecodeError:
        return None
    oauth = blob.get("claudeAiOauth") or blob.get("oauth") or blob
    tok = oauth.get("accessToken") or oauth.get("access_token")
    return tok or None


def api_get(path: str, token: str, attempts: int = 3) -> tuple[int, Any]:
    """GET with backoff on 429.

    Probing ~8 Keychain entries back-to-back trips the endpoint's rate limiter, and a
    rate-limited answer is indistinguishable in shape from a dead credential — it would
    report a healthy seat as unreadable and push the exit code to 1. Retry only the
    retryable status; everything else returns on the first answer.
    """
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": OAUTH_BETA,
            "User-Agent": UA,
        },
    )
    last: tuple[int, Any] = (0, {"error": {"message": "no attempt made"}})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body[:200]}
            last = (exc.code, payload)
            if exc.code not in (429, 500, 502, 503, 529):
                return last
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = (0, {"error": {"message": str(exc)[:160]}})
        if i < attempts - 1:
            time.sleep(2 ** i)
    return last


def config_dirs() -> list[Path]:
    home = Path.home()
    return [d for d in sorted(home.glob(".claude*")) if d.is_dir() and (d / ".claude.json").exists()]


def warm_profiles(deep: bool) -> None:
    """Refresh each profile's Keychain access token before reading it.

    `auth status` is enough for a token that is merely near expiry; a profile idle past
    the ~1h window needs a real call (`--deep`). Without this the endpoint answers
    "token has expired" and a saturated seat reads as a blank row.
    """
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)  # never let a cron seat shadow the profile
    for d in config_dirs():
        e = dict(env, CLAUDE_CONFIG_DIR=str(d))
        try:
            subprocess.run(["claude", "auth", "status"], env=e, capture_output=True,
                           timeout=60, stdin=subprocess.DEVNULL)
            if deep:
                subprocess.run(
                    ["claude", "-p", "hi", "--model", "claude-haiku-4-5-20251001"],
                    env=e, capture_output=True, timeout=120,
                    stdin=subprocess.DEVNULL, cwd="/tmp",
                )
        except (OSError, subprocess.SubprocessError):
            continue


def pct(block: Any) -> float | None:
    if isinstance(block, dict):
        v = block.get("utilization")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def collect(pace: float = 1.2) -> list[dict]:
    """Read every Keychain entry, one at a time.

    `pace` matters: ~9 entries x 2 calls fired back-to-back trips the endpoint's rate
    limiter even with per-call retry, and the result reads as a dead seat. Measured
    2026-08-23 — without pacing, 3 of 9 entries came back "Rate limited" every run.

    An entry whose PROFILE call also fails to name an account is a STALE LEFTOVER (an old
    login whose refresh token is long gone), not a seat in trouble: it is reported, but
    marked `stale` so it never flips the exit code. Conflating the two is what would make
    this tool cry wolf on every run until someone stopped reading it.
    """
    rows: list[dict] = []
    for idx, svc in enumerate(keychain_services()):
        if idx:
            time.sleep(pace)
        tok = access_token(svc)
        if not tok:
            rows.append({"account": None, "stale": True,
                         "error": "no access token in keychain entry"})
            continue
        _, prof = api_get(PROFILE_PATH, tok)
        email = None
        if isinstance(prof, dict):
            acct = prof.get("account") or {}
            email = acct.get("email_address") or acct.get("email")
        code, usage = api_get(USAGE_PATH, tok)
        if code != 200 or not isinstance(usage, dict) or "five_hour" not in usage:
            msg = "unreadable"
            if isinstance(usage, dict):
                msg = (usage.get("error") or {}).get("message", msg)
            rows.append({"account": email, "error": msg[:80], "http": code,
                         "stale": email is None})
            continue
        rows.append({
            "account": email,
            "session_pct": pct(usage.get("five_hour")),
            "weekly_pct": pct(usage.get("seven_day")),
            "weekly_opus_pct": pct(usage.get("seven_day_opus")),
            "weekly_sonnet_pct": pct(usage.get("seven_day_sonnet")),
            "session_resets_at": (usage.get("five_hour") or {}).get("resets_at"),
            "weekly_resets_at": (usage.get("seven_day") or {}).get("resets_at"),
        })
    # One account can hold several Keychain entries (same seat, two config dirs).
    # Collapse by account so the table counts SEATS, not profiles.
    seen: dict[str, dict] = {}
    unnamed: list[dict] = []
    for r in rows:
        key = r.get("account")
        if not key:
            unnamed.append(r)
        elif key not in seen or seen[key].get("error"):
            seen[key] = r
    return sorted(seen.values(), key=lambda r: (r.get("weekly_pct") is None,
                                                -(r.get("weekly_pct") or 0))) + unnamed


def fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.0f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--deep", action="store_true",
                    help="force a 1-token inference on stale profiles (slower, more complete)")
    ap.add_argument("--warn-at", type=float, default=None, metavar="PCT",
                    help="exit 1 if any seat's weekly utilization is >= PCT")
    ap.add_argument("--no-warm", action="store_true",
                    help="skip the refresh pass (faster; idle profiles will read as expired)")
    ap.add_argument("--pace", type=float, default=1.2, metavar="SEC",
                    help="seconds between profiles; too low trips the endpoint rate limiter")
    args = ap.parse_args()

    if sys.platform != "darwin":
        print("claude_seat_quota: Keychain-backed, macOS only", file=sys.stderr)
        return 2

    if not args.no_warm:
        warm_profiles(deep=args.deep)

    rows = collect(pace=args.pace)
    if not rows:
        print("claude_seat_quota: NO profile discovered — this is a failure, not calm.\n"
              "  Log a profile in with: CLAUDE_CONFIG_DIR=$HOME/.claude-<name> claude auth login",
              file=sys.stderr)
        return 2

    readable = [r for r in rows if r.get("weekly_pct") is not None]
    # A stale Keychain leftover has no account name and no live credential: it is noise
    # from an old login, not a seat that failed. Only a NAMED account that could not be
    # read is a real failure.
    stale = [r for r in rows if r.get("stale")]
    broken = [r for r in rows if r.get("error") and not r.get("stale")]

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'account':34s} | {'5h':>5} | {'weekly':>6} | weekly resets at")
        print("-" * 34 + "-+-" + "-" * 5 + "-+-" + "-" * 6 + "-+-" + "-" * 20)
        for r in rows:
            if r.get("error"):
                label = r.get("account") or "(stale keychain entry)"
                print(f"{label:34s} | {'-':>5} | {'-':>6} | {r['error']}")
                continue
            reset = (r.get("weekly_resets_at") or "")[:16].replace("T", " ")
            flag = " <<<" if (r.get("weekly_pct") or 0) >= 85 else ""
            print(f"{r['account']:34s} | {fmt(r.get('session_pct')):>5} | "
                  f"{fmt(r.get('weekly_pct')):>6} | {reset}{flag}")
        if stale:
            print(f"\n{len(stale)} stale keychain entr{'y' if len(stale) == 1 else 'ies'} "
                  f"(old logins, no live credential) — informational, not a seat failure")

    if not readable:
        print("claude_seat_quota: every profile was unreadable — endpoint or auth failure",
              file=sys.stderr)
        return 2
    if broken:
        names = ", ".join(r.get("account") or "?" for r in broken)
        print(f"claude_seat_quota: {len(broken)} named seat(s) unreadable ({names}) "
              f"— re-login or run with --deep", file=sys.stderr)
        return 1
    if args.warn_at is not None:
        hot = [r for r in readable if (r.get("weekly_pct") or 0) >= args.warn_at]
        if hot:
            print(f"claude_seat_quota: {len(hot)} seat(s) at or above {args.warn_at:.0f}% weekly",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
