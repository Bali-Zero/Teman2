#!/usr/bin/env python3
"""typesafe_client.py — minimal System One (Jev) client for CI-side lints.

Stdlib only: this runs in `actions/checkout` + `python3` with nothing installed,
same constraint every other script in .github/workflows/ works under.

The client is deliberately small and has one non-obvious property, which is the
reason it exists as a module rather than as ten lines inside a lint:

    ask() NEVER raises on a service problem. It returns None.

A lint that composes its verdict as `regex_verdict OR jev_verdict` must treat an
unreachable model as "no opinion", not as "no violation" and not as a crash. None
is the shape that forces the caller to say which one it means, and every caller
here means: fall back to the verdict the repo already had.

There is a SECOND silence, added after the Gear-3 gate of PR #6968: this client
refuses to speak unless its endpoint is authorized ON DISK, whatever the
environment holds. A key is not permission. `unavailable_reason()` says which
silence a caller is in, because the two are indistinguishable from outside and a
caller that cannot tell them apart prints something false half the time.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
ENV_VAR = "TYPESAFE_API_KEY"

# THE AUTHORIZATION IS ON DISK, NOT IN THE ENVIRONMENT — and that is the whole
# point of this block. Builder Contract §3 already said a third-party per-token
# vendor is "not yours to install", and it could not reach what actually arms
# one: adding a repository secret. That is a settings page, not a PR — no
# review, no merge, no record. Listing the endpoint HERE puts the decision back
# where a merge can see it, so a secret alone can no longer open an outbound
# path. Gate verdict on PR #6968, condition 3; ruling in docs/rules/RULINGS.md.
AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "infra"
    / "vendor-authorizations"
    / "authorized_endpoints.json"
)

NO_KEY = "no key configured"
NOT_AUTHORIZED = f"{ENDPOINT} is not listed in {AUTHORIZATION.name}"


def authorized() -> bool:
    """True when THIS endpoint is listed on disk.

    Absent, unreadable or malformed authorizes NOTHING — the same choice the
    ban-prose pardon list makes, and for the same reason: failing open would
    make deleting one file the way to arm every vendor.
    """
    try:
        listed = json.loads(AUTHORIZATION.read_text())["endpoints"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if not isinstance(listed, list):
        return False
    return any(
        entry == ENDPOINT or (isinstance(entry, dict) and entry.get("endpoint") == ENDPOINT)
        for entry in listed
    )


def unavailable_reason() -> str | None:
    """Why this client will stay silent, or None when it will speak.

    Two silences that look identical from outside — no key, and no
    authorization — and a caller that cannot tell them apart prints a message
    that is false half the time. An anti-bypass failing open in silence is
    indistinguishable from one that passed; so is a fence nobody can name.
    """
    if not os.environ.get(ENV_VAR, "").strip():
        return NO_KEY
    if not authorized():
        return NOT_AUTHORIZED
    return None

# 429/529 are the documented retryable pair. 5xx other than 529 are not retried:
# a 500 on a malformed request repeats forever and the caller degrades fine.
RETRY_STATUS = {429, 529}
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 0.8
TIMEOUT_S = 25


def available() -> bool:
    """True when this client may speak: a key AND an on-disk authorization.

    Never reports the key itself. A key without an authorization is NOT
    available — which is the fence, and is why the reason is reported
    separately rather than folded into this boolean.
    """
    return unavailable_reason() is None


def ask(
    state: Any, questions: dict[str, dict], *, timeout: int = TIMEOUT_S
) -> dict | None:
    """Send one batched request. Returns the `answers` map, or None.

    None means "no answer available" — no key, network failure, rate limit
    survived the retries, or a malformed response. It never means "no".
    """
    if unavailable_reason() is not None:
        # Before the payload exists, not after: an unauthorized endpoint must
        # never have source text serialised for it, even into a request that
        # is then discarded.
        return None
    key = os.environ.get(ENV_VAR, "").strip()

    payload = json.dumps(
        {"model": MODEL, "state": state, "questions": questions}
    ).encode("utf-8")

    for attempt in range(MAX_ATTEMPTS):
        req = urllib.request.Request(
            ENDPOINT,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            answers = body.get("answers")
            return answers if isinstance(answers, dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_STATUS and attempt < MAX_ATTEMPTS - 1:
                time.sleep(BACKOFF_BASE_S * (2**attempt))
                continue
            return None
        except Exception:
            # Broad on purpose. The docstring promises this returns None on any
            # service problem, and a narrow tuple cannot keep that promise: a
            # non-UTF-8 error page raises UnicodeDecodeError, which is a
            # ValueError and matched none of the previous clauses. Caught by an
            # adversarial reviewer, 2026-09-20 — the exception escaped into a
            # step whose whole contract is that it never fails the build.
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BACKOFF_BASE_S * (2**attempt))
                continue
            return None
    return None


def noul(answers: dict | None, key: str) -> float | None:
    """Probability for a Noul answer, or None when it is absent/malformed."""
    if not answers:
        return None
    entry = answers.get(key)
    if not isinstance(entry, dict):
        return None
    value = entry.get("noul")
    return float(value) if isinstance(value, (int, float)) else None
