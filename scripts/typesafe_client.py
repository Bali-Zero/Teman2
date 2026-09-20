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
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
# Pinned, not `jev-latest`. This client feeds a CI lint whose firing threshold
# (0.80) was calibrated against THIS model version: 15/17 recall on the cases the
# greps miss, 0/20 false alarms, reproduced from a seat outside the lane on
# 2026-09-21. A moving alias lets TypeSafe reissue the model under our feet and
# silently invalidate that calibration — the verdict would drift with nothing in
# the diff to show it. The vendor's own docs recommend pinning for this reason.
# Raising this version is therefore a bench re-run, not an edit.
MODEL = "jev-1.13.0"
ENV_VAR = "TYPESAFE_API_KEY"

# 429/529 are the documented retryable pair. 5xx other than 529 are not retried:
# a 500 on a malformed request repeats forever and the caller degrades fine.
RETRY_STATUS = {429, 529}
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 0.8
TIMEOUT_S = 25


def available() -> bool:
    """True when a key is present. Never reports the key itself."""
    return bool(os.environ.get(ENV_VAR, "").strip())


def ask(
    state: Any, questions: dict[str, dict], *, timeout: int = TIMEOUT_S
) -> dict | None:
    """Send one batched request. Returns the `answers` map, or None.

    None means "no answer available" — no key, network failure, rate limit
    survived the retries, or a malformed response. It never means "no".
    """
    key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        return None

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
