#!/usr/bin/env python3
"""jules_dispatch.py — active dispatch arm for Google Jules (async cloud implementer).

Born 2026-07-06 from Zero's mandate "coinvolgilo attivamente nel workflow, senza teatro".
Jules generates; Fable grades — this tool ONLY dispatches tasks and reads state. It can
NEVER merge, push to main, or approve its own output: landing always goes through the
independent-verification lane (diff review + test re-run + scoped PR), same contract as
the Antigravity arm (CLAUDE.md §5) and the R1 generator≠grader gate.

API: Jules API v1alpha (alpha — shapes may drift; fail-visible, never fail-silent).
  base https://jules.googleapis.com/v1alpha, auth header X-Goog-Api-Key.
Key: macOS Keychain item `jules-api-key` (env JULES_API_KEY overrides, for tests).
The key value is never printed; error bodies are scrubbed before display.

Usage:
    python3 scripts/jules_dispatch.py list-sources [--json]
    python3 scripts/jules_dispatch.py new --prompt "..." [--source <name>] [--branch main]
                                          [--title "..."] [--require-plan-approval] [--json]
    python3 scripts/jules_dispatch.py status <session-id-or-name> [--json]
    python3 scripts/jules_dispatch.py activities <session-id-or-name> [--json] [--limit N]
    python3 scripts/jules_dispatch.py --selftest

Exit codes: 0 ok · 1 API/HTTP error · 2 credential missing · 3 usage error.
Scar refs: #4 (key never on stdout/argv), #8 (bounded retry on 5xx), W81 (a dispatch
tool is armed only when a REAL session ran through it — see runbook), W65 (session
state is re-read from the API, never assumed from memory).
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

BASE = "https://jules.googleapis.com/v1alpha"
DEFAULT_SOURCE = "sources/github/Balizero1987/Teman2"
DEFAULT_BRANCH = "main"
KEYCHAIN_SERVICE = "jules-api-key"
TIMEOUT_S = 30
RETRIES_5XX = 2


def get_api_key() -> str:
    env = os.environ.get("JULES_API_KEY", "").strip()
    if env:
        return env
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10,
        )
        key = proc.stdout.strip()
        if proc.returncode == 0 and key:
            return key
    except Exception:
        pass
    print(
        f"jules_dispatch: no API key — add it with:\n"
        f"  security add-generic-password -a balizero -s {KEYCHAIN_SERVICE} -w '<KEY>'",
        file=sys.stderr,
    )
    sys.exit(2)


def scrub(text: str, key: str) -> str:
    """The key must never reach a transcript, even inside an echoed error body."""
    if key:
        text = text.replace(key, "<REDACTED-KEY>")
    return re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "<REDACTED-KEY>", text)


def api_call(method: str, path: str, key: str, body: dict | None = None) -> dict:
    url = f"{BASE}/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body is not None else None
    last_err = ""
    for attempt in range(1 + RETRIES_5XX):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-Goog-Api-Key", key)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            err_body = scrub(e.read().decode(errors="replace")[:600], key)
            if 500 <= e.code < 600 and attempt < RETRIES_5XX:
                last_err = f"HTTP {e.code} (retry {attempt + 1})"
                time.sleep(2 * (attempt + 1))
                continue
            print(f"jules_dispatch: HTTP {e.code} on {method} {path}\n{err_body}",
                  file=sys.stderr)
            sys.exit(1)
        except Exception as e:  # network layer — bounded retry, then visible failure
            last_err = f"{type(e).__name__}: {scrub(str(e), key)}"
            if attempt < RETRIES_5XX:
                time.sleep(2 * (attempt + 1))
                continue
    print(f"jules_dispatch: request failed after retries — {last_err}", file=sys.stderr)
    sys.exit(1)


def session_path(ref: str) -> str:
    return ref if ref.startswith("sessions/") else f"sessions/{ref}"


# ------------------------------------------------------------------ commands
def cmd_list_sources(key: str, as_json: bool) -> int:
    data = api_call("GET", "sources", key)
    if as_json:
        print(json.dumps(data, indent=2))
        return 0
    for s in data.get("sources", []):
        repo = s.get("githubRepo", {})
        print(f"{s.get('name')}  (default: {repo.get('defaultBranch', {}).get('displayName', '?')})")
    return 0


def cmd_new(key: str, args: argparse.Namespace) -> int:
    body = {
        "prompt": args.prompt,
        "sourceContext": {
            "source": args.source,
            "githubRepoContext": {"startingBranch": args.branch},
        },
        "requirePlanApproval": bool(args.require_plan_approval),
    }
    if args.title:
        body["title"] = args.title
    data = api_call("POST", "sessions", key, body)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"session: {data.get('name', '?')}")
        print(f"state:   {data.get('state', '?')}")
        print(f"url:     {data.get('url', '-')}")
        print("landing contract: Jules output is EVIDENCE — verify diff + re-run tests, "
              "land via your own PR. This tool never merges.")
    return 0


def cmd_status(key: str, ref: str, as_json: bool) -> int:
    data = api_call("GET", session_path(ref), key)
    if as_json:
        print(json.dumps(data, indent=2))
        return 0
    for field in ("name", "state", "title", "url", "createTime", "updateTime"):
        if field in data:
            print(f"{field}: {data[field]}")
    outputs = data.get("outputs") or []
    for o in outputs:
        print(f"output: {json.dumps(o)[:200]}")
    return 0


def cmd_activities(key: str, ref: str, as_json: bool, limit: int) -> int:
    data = api_call("GET", f"{session_path(ref)}/activities?pageSize={limit}", key)
    if as_json:
        print(json.dumps(data, indent=2))
        return 0
    for a in data.get("activities", []):
        kind = next((k for k in a.keys() if k not in
                     ("name", "createTime", "id", "originator")), "?")
        desc = a.get(kind) if isinstance(a.get(kind), str) else json.dumps(
            a.get(kind, {}))[:160]
        print(f"[{a.get('createTime', '?')}] {kind}: {desc}")
    return 0


# ------------------------------------------------------------------ selftest
def _selftest() -> int:
    """Offline guilt+innocence (superscar #3): no network, no real key."""
    failures: list[str] = []
    total = 0

    def expect(name: str, cond: bool) -> None:
        nonlocal total
        total += 1
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    # guilt: scrub removes the exact key and AIza-shaped tokens
    fake = "AIzaFAKEFAKEFAKEFAKEFAKEFAKEfakefake"  # pragma: allowlist secret — fixture proving scrub()
    expect("scrub removes exact key", "<REDACTED-KEY>" in scrub(f"err {fake} end", fake))
    expect("scrub removes AIza-shaped strays",
           "<REDACTED-KEY>" in scrub(f"body has {fake} inline", ""))
    # innocence: scrub leaves clean text alone
    expect("scrub leaves clean text intact", scrub("plain error", "k123") == "plain error")

    # session_path normalization (guilt+innocence)
    expect("session_path adds prefix", session_path("abc123") == "sessions/abc123")
    expect("session_path idempotent", session_path("sessions/abc") == "sessions/abc")

    # credential path: env override wins without touching Keychain
    os.environ["JULES_API_KEY"] = "test-key-env"
    try:
        expect("env JULES_API_KEY override", get_api_key() == "test-key-env")
    finally:
        os.environ.pop("JULES_API_KEY", None)

    print(f"SELFTEST {'OK' if not failures else 'FAILED'} — {total - len(failures)}/{total} checks")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="cmd")

    p_ls = sub.add_parser("list-sources")
    p_ls.add_argument("--json", action="store_true")

    p_new = sub.add_parser("new")
    p_new.add_argument("--prompt", required=True)
    p_new.add_argument("--source", default=DEFAULT_SOURCE)
    p_new.add_argument("--branch", default=DEFAULT_BRANCH)
    p_new.add_argument("--title", default="")
    p_new.add_argument("--require-plan-approval", action="store_true")
    p_new.add_argument("--json", action="store_true")

    p_st = sub.add_parser("status")
    p_st.add_argument("ref")
    p_st.add_argument("--json", action="store_true")

    p_ac = sub.add_parser("activities")
    p_ac.add_argument("ref")
    p_ac.add_argument("--limit", type=int, default=30)
    p_ac.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.selftest:
        return _selftest()
    if not args.cmd:
        parser.print_help()
        return 3

    key = get_api_key()
    if args.cmd == "list-sources":
        return cmd_list_sources(key, args.json)
    if args.cmd == "new":
        return cmd_new(key, args)
    if args.cmd == "status":
        return cmd_status(key, args.ref, args.json)
    if args.cmd == "activities":
        return cmd_activities(key, args.ref, args.json, args.limit)
    return 3


if __name__ == "__main__":
    sys.exit(main())
