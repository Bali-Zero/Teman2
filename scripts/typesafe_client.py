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

A THIRD thing narrowed after the Gear-3 gate of PR #6989: authorizing an
endpoint bound the FIRST HOP ONLY. `urlopen`'s default opener follows a
redirect and Python's own `HTTPRedirectHandler` carries the `Authorization`
header to the new host — including over plain HTTP — so an authorized
endpoint that answers `302` could send the bearer token anywhere. This client
builds its own `OpenerDirector` that refuses every redirect, kept local to
this module rather than installed process-wide, because `install_opener()`
would strip redirects from every OTHER caller of `urlopen` in the same
interpreter. The defect predates PR #6989 — the base client already called
`urlopen` with the same header and no custom opener — so this narrows a
pre-existing window rather than fixing a regression.
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
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
    """True when THIS endpoint is listed on disk WITH a file perimeter.

    Absent, unreadable or malformed authorizes NOTHING — the same choice the
    ban-prose pardon list makes, and for the same reason: failing open would
    make deleting one file the way to arm every vendor. The same failure mode
    exists one level down: an entry's `_doc` describes the file, not itself,
    so `{endpoint, ruling}` alone leaves the ENTRY with no field for what it
    is permitted to touch — an entry with no perimeter authorizes everything,
    which is the fail-open the file exists to prevent. `paths` closes that
    for the ENTRY SHAPE: a matching entry without a non-empty list of
    non-empty string `paths` authorizes NOTHING, same as the file absent. A
    bare string entry can never carry `paths`, so it is skipped outright
    rather than entity-matched and then refused for lacking one — a
    comparison whose result can never change the outcome is dead code, and
    dead code is where an unkillable mutant hides. `endpoint` and `paths` are
    the two fields this function actually checks; `ruling` and `use` are
    conventionally required by `authorized_endpoints.json`'s own `_doc` but
    are NOT read here — an entry naming only `{endpoint, paths}` authorizes
    exactly as much as one that also carries `ruling` and `use`. Overclaiming
    otherwise is the same prose defect PR #6989's own gate found once already
    (finding f): a docstring naming a discrimination the code does not
    perform.

    What this function does NOT do: it does not check any `paths` glob
    against a target file, because nothing calls it with one. The registry
    shipped EMPTY in the PR that added this field; its first entry (RULED
    2026-09-21-bis) declares `["**"]`, so a per-request check would match
    everything — dead code until a NARROWER entry exists, which is when
    wiring it becomes the job. `paths` is validated as a SHAPE requirement
    on the entry today, and `scripts/tests/test_vendor_authorization_fence.py`
    validates every shipped entry's shape and ruling at merge time. Successor
    to PR #6989's Gear-3 gate.
    """
    try:
        listed = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))["endpoints"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        # RecursionError is neither a ValueError nor an OSError: deeply nested
        # JSON raises it out of the parser and it would escape into a step
        # whose whole contract is that it never fails a build. Same shape as
        # the UnicodeDecodeError that escaped `ask` — a narrow tuple cannot
        # keep a promise this broad. Raised by a refuting seat.
        return False
    if not isinstance(listed, list):
        return False
    for entry in listed:
        if not isinstance(entry, dict):
            continue
        if entry.get("endpoint") != ENDPOINT:
            continue
        paths = entry.get("paths")
        if (
            isinstance(paths, list)
            and paths
            and all(isinstance(p, str) and p for p in paths)
        ):
            return True
    return False


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


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect instead of following it.

    `redirect_request` returning `None` tells `HTTPRedirectHandler` NOT to
    issue a second request. Verified empirically against CPython 3.11's real
    handler rather than assumed: `OpenerDirector` then falls through to
    `HTTPDefaultErrorHandler`, which raises `HTTPError` carrying the
    redirect's own status code (e.g. 302) — it does NOT hand back the
    redirect response for the caller to parse. `ask()` catches `HTTPError`,
    finds the code outside `RETRY_STATUS`, and returns `None` on the FIRST
    attempt with no retry. Either way, no second request is ever attempted,
    so the bearer token never reaches whatever host the `Location` header
    names.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102, N802
        return None


# Built once, held module-local. Never `urllib.request.install_opener()`: that
# call is process-wide and would strip redirects from every OTHER caller of
# `urlopen` in the same interpreter — most of which have nothing to do with
# this vendor and may legitimately need them.
_OPENER = urllib.request.build_opener(_NoRedirects())


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
            with _OPENER.open(req, timeout=timeout) as resp:
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
    """Probability for a Noul answer, or None when it is absent/malformed.

    Malformed means MORE than "not a number", and the day the step was armed
    that distinction started to matter (codex council finding on RULED
    2026-09-21-ter): `bool` is an `int`, so `{"noul": true}` used to become
    1.0 — a finding, and a red build — and `1.5`, `inf` and `nan` passed the
    same isinstance check. A probability is a non-bool finite number in
    [0, 1]; anything else is no opinion, never a verdict.
    """
    if not answers:
        return None
    entry = answers.get(key)
    if not isinstance(entry, dict):
        return None
    value = entry.get("noul")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    prob = float(value)
    if not math.isfinite(prob) or not 0.0 <= prob <= 1.0:
        return None
    return prob
