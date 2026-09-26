#!/usr/bin/env python3
"""healer_receptor_garuda_outbox.py — the GARUDA outbox, heard off Telegram.

WHY THIS EXISTS. `count_undrained`'s `exhausted` counts the rows the drain
loop will never claim again — a money-anomaly page that died is one of them.
Until today its only non-test consumer was `_send_outbox_alarm` in
`main_api.py`, which pages over Telegram. So the number that says "a job died"
could only be heard on the wire that dies with it. Measured 2026-09-20: row 36
(`staff_page_charge_without_webhook` — a charge with no webhook) burned five
attempts on `400 Bad Request: can't parse entities` and nobody knew for a day.
Cause and signal shared a wire, and the silence was indistinguishable from
health (superscar #2; W84 — healthy silence must be provable).

THE SECOND PATH, END TO END. This receptor reads `/health/garuda-outbox` on
the Fly app (HTTP, no Telegram, no credential) and hands its verdict to the
healer, which pages through `scripts/tg_notify.py` — the FLEET's gateway, a
different process on a different machine holding a different token from the
one the API uses. Neither half of the loop shares a failure mode with the
Telegram send that broke.

BLIND IS LOUD. If the endpoint cannot be read at all, this exits 2, which the
healer treats as actionable exactly like receptor 4's exit 2: a receptor that
lost its senses is silent coverage loss, which is the disease, not a quiet day.

Exit codes:
  0 = nothing owed (or kill switch set)
  1 = ACTIONABLE: rows exhausted, or undrained past 24h, or the API says it
      could not look ("unknown")
  2 = BLIND: no answer, or an answer this receptor cannot parse

Kill switch: HEALER_GARUDA_OUTBOX_OFF=1 (exit 0, and the reason is printed —
a switch that hides itself is a second silence).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://nuzantara-rag.fly.dev/health/garuda-outbox"
KILL_SWITCH_ENV = "HEALER_GARUDA_OUTBOX_OFF"
URL_ENV = "GARUDA_OUTBOX_HEALTH_URL"
#: Two short attempts beat one long one on a flapping link (#8), and the whole
#: receptor still finishes inside the healer's per-receptor patience.
TIMEOUT_S = 8.0
ATTEMPTS = 2

EXIT_CLEAN = 0
EXIT_ACTIONABLE = 1
EXIT_BLIND = 2


def classify(payload: object) -> tuple[int, str]:
    """Pure: the verdict is a function of the payload, so it is testable.

    Kept out of the fetch on purpose — a classifier that can only be exercised
    by standing up a server gets exercised once, by its author.
    """
    if not isinstance(payload, dict):
        return EXIT_BLIND, f"payload is {type(payload).__name__}, not an object"

    status = payload.get("status")
    if status == "unknown":
        # The API answered and said it could not look. That is NOT health, and
        # it is not blindness on this side either: the page must name which.
        return EXIT_ACTIONABLE, f"the API could not read the outbox: {payload.get('error', 'no reason given')}"
    if status != "ok":
        return EXIT_BLIND, f"unexpected status {status!r}"

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        return EXIT_BLIND, "no counts object in the answer"

    try:
        exhausted = int(counts.get("exhausted", 0))
        undispatched = int(counts.get("undispatched", 0))
        older_24h = int(counts.get("older_than_24h", 0))
        older_1h = int(counts.get("older_than_1h", 0))
    except (TypeError, ValueError):
        return EXIT_BLIND, "counts are not integers"

    if exhausted:
        return (
            EXIT_ACTIONABLE,
            f"{exhausted} exhausted row(s) in garuda_order_outbox — they will "
            f"never be claimed again ({undispatched} undispatched in total)",
        )
    if older_24h:
        return (
            EXIT_ACTIONABLE,
            f"{older_24h} undrained row(s) older than 24h — not exhausted yet, "
            "so nothing else will say so",
        )
    if older_1h:
        # The UNROUTABLE shape (codex/gpt-5.6-terra, council on this diff): a row
        # whose job_type has no handler has its attempt bump rolled back, so it
        # never exhausts and never ages into the 24h term until a full day has
        # passed. The drain loop sleeps seconds; an hour undispatched is stuck.
        return (
            EXIT_ACTIONABLE,
            f"{older_1h} undrained row(s) older than 1h with 0 exhausted — the shape "
            "an UNROUTABLE job makes: its attempts roll back, so it never exhausts",
        )
    return EXIT_CLEAN, f"nothing owed ({undispatched} undispatched, 0 exhausted)"


def fetch(url: str) -> tuple[object | None, str | None]:
    """Returns (payload, error). Never raises: a receptor that crashes is mute."""
    last: str | None = None
    for _ in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:  # noqa: S310
                raw = resp.read()
            return json.loads(raw.decode("utf-8")), None
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last = f"unreachable: {exc.reason}"
        except TimeoutError:
            # A CONNECT-phase timeout comes back wrapped as URLError above.
            # A READ-phase timeout (connection opened, response never
            # finished) propagates as a bare TimeoutError instead — urllib's
            # do_open() only wraps the request()/connect() call in
            # `except OSError: raise URLError(...)`, not getresponse().
            # Uncaught, this crashed the receptor outright, the exact
            # opposite of this function's documented "never raises"
            # contract (scar family #8 — network flap must degrade to a
            # verdict, not a traceback).
            last = "read timed out"
        except (ValueError, UnicodeDecodeError) as exc:
            last = f"unreadable answer: {type(exc).__name__}"
    return None, last or "no attempt succeeded"


def sibling_live_url(url: str) -> str:
    """`/health/garuda-outbox` -> `/health/live` on the same host.

    String surgery, not urlparse-and-rebuild: the only shape this receptor ever
    points at is a /health/* route, and a helper that silently rewrites an
    arbitrary URL is a bigger surface than the one question it answers.
    """
    return url.rsplit("/", 1)[0] + "/live"


def explain_404(url: str) -> str:
    """A 404 has two very different meanings, and the page must say which.

    Found by the kimi/k3 council seat on this diff: between merging this PR and
    the Fly deploy that carries the route, the endpoint 404s while the API is
    perfectly healthy. Reporting that as a bare "unreadable" would page the
    fleet about a deploy window — an alarm that cries during its own rollout is
    an alarm people learn to ignore.
    """
    _, err = fetch(sibling_live_url(url))
    if err is None:
        return (
            "the API is UP but /health/garuda-outbox is not there (404) — the route is "
            "not deployed yet, or was rolled back. Not an outbox problem; coverage is "
            "missing until the deploy lands"
        )
    return f"HTTP 404 and /health/live is also unreadable ({err}) — the app itself is the suspect"


def selftest() -> int:
    """Guilt AND innocence, because a classifier only proves one of them.

    Every case names the shape it stands for: a green that was never red on a
    real defect is decoration (guard-conformance, family #3).
    """
    cases: list[tuple[str, object, int]] = [
        ("clean queue", {"status": "ok", "counts": {"undispatched": 0, "exhausted": 0, "older_than_24h": 0}}, EXIT_CLEAN),
        ("busy but healthy", {"status": "ok", "counts": {"undispatched": 3, "exhausted": 0, "older_than_24h": 0}}, EXIT_CLEAN),
        ("GUILT: one exhausted row", {"status": "ok", "counts": {"undispatched": 1, "exhausted": 1, "older_than_24h": 0}}, EXIT_ACTIONABLE),
        ("GUILT: stuck a day, not exhausted", {"status": "ok", "counts": {"undispatched": 2, "exhausted": 0, "older_than_24h": 2}}, EXIT_ACTIONABLE),
        ("GUILT: the unroutable shape — an hour old, never exhausts", {"status": "ok", "counts": {"undispatched": 1, "exhausted": 0, "older_than_1h": 1, "older_than_24h": 0}}, EXIT_ACTIONABLE),
        ("GUILT: the API could not look", {"status": "unknown", "error": "no database pool on app.state"}, EXIT_ACTIONABLE),
        ("BLIND: counts missing", {"status": "ok"}, EXIT_BLIND),
        ("BLIND: counts not numbers", {"status": "ok", "counts": {"exhausted": "two"}}, EXIT_BLIND),
        ("BLIND: not an object", ["ok"], EXIT_BLIND),
    ]
    failed = 0
    for name, payload, expected in cases:
        got, reason = classify(payload)
        ok = got == expected
        failed += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {name}: exit {got} (expected {expected}) — {reason}")
    print(f"\n  passed: {len(cases) - failed}   failed: {failed}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable verdict on stdout")
    parser.add_argument("--url", default=os.environ.get(URL_ENV, DEFAULT_URL))
    parser.add_argument("--selftest", action="store_true", help="run the classifier's guilt/innocence corpus")
    args, unknown = parser.parse_known_args()
    if unknown:
        # A receptor that absorbs a flag it does not know is a receptor that
        # silently does something other than what the caller asked.
        print(f"ERROR: unknown argument(s) {unknown} — known: --json --url --selftest", file=sys.stderr)
        return EXIT_BLIND

    if args.selftest:
        return selftest()

    if os.environ.get(KILL_SWITCH_ENV) == "1":
        out = {"exit": EXIT_CLEAN, "reason": f"disabled by {KILL_SWITCH_ENV}=1", "url": args.url}
        print(json.dumps(out) if args.json else out["reason"])
        return EXIT_CLEAN

    payload, error = fetch(args.url)
    if payload is None:
        detail = explain_404(args.url) if error == "HTTP 404" else error
        reason = f"could not read {args.url}: {detail}"
        code = EXIT_BLIND
    else:
        code, reason = classify(payload)

    out = {"exit": code, "reason": reason, "url": args.url}
    if isinstance(payload, dict) and isinstance(payload.get("counts"), dict):
        out["counts"] = payload["counts"]
    print(json.dumps(out) if args.json else reason)
    return code


if __name__ == "__main__":
    sys.exit(main())
