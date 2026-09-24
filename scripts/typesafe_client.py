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
import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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


@dataclass
class RequestBudget:
    """A strict wall deadline and HTTP-attempt pool shared across calls."""

    total_deadline_s: float
    max_http_attempts: int
    started_at: float = field(default_factory=time.monotonic)
    http_attempts_used: int = 0

    def remaining_s(self) -> float:
        return max(0.0, self.total_deadline_s - (time.monotonic() - self.started_at))

    def may_attempt(self) -> bool:
        return self.http_attempts_used < self.max_http_attempts and self.remaining_s() > 0

    def consume_attempt(self) -> bool:
        if not self.may_attempt():
            return False
        self.http_attempts_used += 1
        return True


@dataclass(frozen=True)
class AskResult:
    answers: dict | None
    telemetry: dict[str, Any]


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


class _ReadTimedOut(TimeoutError):
    pass


def _open_and_read(req: urllib.request.Request, timeout: float) -> bytes:
    """Bound open plus full-body read by one wall-clock timeout."""
    result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            with _OPENER.open(req, timeout=timeout) as response:
                result.put((True, response.read()))
        except Exception as exc:  # transported, never retained in telemetry
            result.put((False, exc))

    threading.Thread(target=worker, daemon=True).start()
    try:
        ok, value = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise _ReadTimedOut from exc
    if ok and isinstance(value, bytes):
        return value
    if isinstance(value, Exception):
        raise value
    raise RuntimeError("unexpected response worker result")


def available() -> bool:
    """True when this client may speak: a key AND an on-disk authorization.

    Never reports the key itself. A key without an authorization is NOT
    available — which is the fence, and is why the reason is reported
    separately rather than folded into this boolean.
    """
    return unavailable_reason() is None


def _usage(body: object) -> dict[str, int | None]:
    usage = body.get("usage") if isinstance(body, dict) else None

    def numeric(name: str) -> int | None:
        value = usage.get(name) if isinstance(usage, dict) else None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    return {
        "input_tokens": numeric("input_tokens"),
        "output_tokens": numeric("output_tokens"),
    }


def _usable_answer(answer: object, question: object) -> bool:
    """Whether one requested answer is usable by the question's contract."""
    if not isinstance(answer, dict) or not isinstance(question, dict):
        return False
    if question.get("type") != "noul":
        return bool(answer)
    value = answer.get("noul")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    probability = float(value)
    return math.isfinite(probability) and 0.0 <= probability <= 1.0


def _telemetry(
    *,
    attempted: bool,
    response_received: bool,
    schema_valid: bool,
    abstained: bool,
    failure: str | None,
    resolved_model: str | None,
    usage: dict[str, int | None] | None,
    started_at: float,
    http_attempts: int,
) -> dict[str, Any]:
    return {
        "attempted": attempted,
        "response_received": response_received,
        "schema_valid": schema_valid,
        "abstained": abstained,
        "failure": failure,
        "requested_model": MODEL,
        "resolved_model": resolved_model,
        "usage": usage or {"input_tokens": None, "output_tokens": None},
        "latency_ms": (
            round((time.monotonic() - started_at) * 1000, 3) if attempted else 0.0
        ),
        "http_attempts": http_attempts,
        "fallback": not schema_valid or abstained,
    }


def ask_detailed(
    state: Any,
    questions: dict[str, dict],
    *,
    timeout: float = TIMEOUT_S,
    budget: RequestBudget | None = None,
) -> AskResult:
    """Send one batch and return answers plus non-ambiguous call telemetry.

    The optional budget is mutable by design: callers with more than one batch
    share one wall deadline and one HTTP-attempt pool. No response body or
    exception text is retained in telemetry.
    """
    started_at = time.monotonic()
    reason = unavailable_reason()
    if reason is not None:
        failure = "no_key" if reason == NO_KEY else "not_authorized"
        return AskResult(
            None,
            _telemetry(
                attempted=False,
                response_received=False,
                schema_valid=False,
                abstained=False,
                failure=failure,
                resolved_model=None,
                usage=None,
                started_at=started_at,
                http_attempts=0,
            ),
        )

    if budget is None:
        budget = RequestBudget(
            total_deadline_s=(timeout * MAX_ATTEMPTS)
            + sum(BACKOFF_BASE_S * (2**n) for n in range(MAX_ATTEMPTS - 1)),
            max_http_attempts=MAX_ATTEMPTS,
        )

    # Authorization is checked before serializing repository content.
    payload = json.dumps(
        {"model": MODEL, "state": state, "questions": questions}
    ).encode("utf-8")
    key = os.environ.get(ENV_VAR, "").strip()
    attempts = 0
    response_received = False
    last_failure: str | None = None
    last_body: dict | None = None

    while attempts < MAX_ATTEMPTS:
        if not budget.may_attempt():
            failure = (
                "deadline_exhausted"
                if budget.remaining_s() <= 0
                else "retry_budget_exhausted"
            )
            return AskResult(
                None,
                _telemetry(
                    attempted=attempts > 0,
                    response_received=response_received,
                    schema_valid=False,
                    abstained=False,
                    failure=failure,
                    resolved_model=(
                        last_body.get("resolved_model") or last_body.get("model")
                        if isinstance(last_body, dict)
                        else None
                    ),
                    usage=_usage(last_body),
                    started_at=started_at,
                    http_attempts=attempts,
                ),
            )

        budget.consume_attempt()
        attempts += 1
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
            raw = _open_and_read(req, min(timeout, budget.remaining_s()))
            response_received = True
            if budget.remaining_s() <= 0:
                return AskResult(
                    None,
                    _telemetry(
                        attempted=True,
                        response_received=True,
                        schema_valid=False,
                        abstained=False,
                        failure="deadline_exhausted",
                        resolved_model=None,
                        usage=None,
                        started_at=started_at,
                        http_attempts=attempts,
                    ),
                )
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                last_failure = "invalid_json"
            else:
                last_body = body if isinstance(body, dict) else None
                answers = body.get("answers") if isinstance(body, dict) else None
                if isinstance(answers, dict):
                    abstained = not any(
                        _usable_answer(answers.get(key), question)
                        for key, question in questions.items()
                    )
                    resolved = body.get("resolved_model") or body.get("model")
                    if not isinstance(resolved, str):
                        resolved = None
                    return AskResult(
                        answers,
                        _telemetry(
                            attempted=True,
                            response_received=True,
                            schema_valid=True,
                            abstained=abstained,
                            failure=None,
                            resolved_model=resolved,
                            usage=_usage(body),
                            started_at=started_at,
                            http_attempts=attempts,
                        ),
                    )
                last_failure = "invalid_schema"
        except _ReadTimedOut:
            last_failure = (
                "deadline_exhausted"
                if budget.remaining_s() <= 0
                else "network_error"
            )
            if last_failure == "deadline_exhausted":
                break
        except urllib.error.HTTPError as exc:
            last_failure = (
                "retryable_http_exhausted"
                if exc.code in RETRY_STATUS
                else f"http_error_{exc.code}"
            )
            if exc.code not in RETRY_STATUS:
                break
        except Exception:
            # Broad by contract: service failures never escape into the caller.
            last_failure = "network_error"

        if last_failure in {"invalid_json", "invalid_schema"}:
            break
        if attempts >= MAX_ATTEMPTS:
            break
        if not budget.may_attempt():
            if last_failure in {"invalid_json", "invalid_schema"}:
                break
            continue
        sleep_s = min(BACKOFF_BASE_S * (2 ** (attempts - 1)), budget.remaining_s())
        if sleep_s > 0:
            time.sleep(sleep_s)

    if last_failure == "retryable_http_exhausted" and budget.http_attempts_used >= budget.max_http_attempts:
        last_failure = "retry_budget_exhausted"
    return AskResult(
        None,
        _telemetry(
            attempted=attempts > 0,
            response_received=response_received,
            schema_valid=False,
            abstained=False,
            failure=last_failure or "network_error",
            resolved_model=(
                last_body.get("resolved_model") or last_body.get("model")
                if isinstance(last_body, dict)
                else None
            ),
            usage=_usage(last_body),
            started_at=started_at,
            http_attempts=attempts,
        ),
    )


def ask(
    state: Any, questions: dict[str, dict], *, timeout: float = TIMEOUT_S
) -> dict | None:
    """Compatibility surface: answers or None, with the never-raise promise."""
    return ask_detailed(state, questions, timeout=timeout).answers


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
