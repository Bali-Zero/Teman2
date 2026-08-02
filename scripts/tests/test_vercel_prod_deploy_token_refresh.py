#!/usr/bin/env python3
"""Corpus for `vercel_prod_deploy._token` — an EXPIRED credential is not an ABSENT one.

WHY THIS EXISTS
---------------
The Vercel CLI token lives for hours, so `403 {"invalidToken": true}` is the ordinary state
a few hours after any login — and `auth.json` carries a `refreshToken` for exactly that.

On 2026-08-02 a credential census read that 403 on M5 (plus a placeholder file on Pro and
none on Mini) and concluded no working credential existed anywhere on the fleet. A frontend
cure that was merged, built and READY sat unserved on a client-facing surface, waiting on an
interactive `vercel login` recorded as "the irreducible operator[gui] step". It was not
irreducible: `vercel whoami` redeemed the refresh token in about a second, and the same
session promoted with it. Reading expiry as absence is how a session invents a human step
and parks work it can do — so the behaviour is pinned here rather than left to a docstring,
which is what it was before (the file already SAID "refresh with `vercel whoami`" and then
told the caller to go do it).

Both directions matter. Guilt: an expired token must actually trigger the refresh and then
use the NEW value. Innocence: a valid token must never shell out — a script that re-logs on
every call is its own outage, and `_api` calls `_token()` once per request.

No network, no real CLI: `subprocess.run` is replaced per-case and the credential file is a
tmp fixture.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

STALE = "stale-token-value"
FRESH = "fresh-token-value"


def _write(path: pathlib.Path, token: str, expires_at: float | None) -> None:
    path.write_text(json.dumps({"token": token, "refreshToken": "rt", "expiresAt": expires_at}))


@pytest.fixture()
def auth(tmp_path, monkeypatch):
    path = tmp_path / "auth.json"
    monkeypatch.setattr(vpd, "AUTH_JSON", str(path))
    return path


def _spy(rc=0, rewrite: tuple[pathlib.Path, str, float] | None = None):
    """Stand in for `vercel whoami`; optionally rewrite auth.json as the real CLI does."""
    calls = []

    def fake(cmd, **kwargs):
        calls.append(cmd)
        if rewrite is not None:
            _write(rewrite[0], rewrite[1], rewrite[2])
        return subprocess.CompletedProcess(cmd, rc, stdout="zero-4013\n", stderr="")

    return fake, calls


def test_an_expired_token_is_refreshed_and_the_new_value_is_used(auth, monkeypatch):
    """Guilt. This is the case that was reported as 'no credential on the fleet'."""
    _write(auth, STALE, time.time() - 60)
    fake, calls = _spy(rc=0, rewrite=(auth, FRESH, time.time() + 3600))
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH, "must re-read the file, not return the value it already had"
    assert len(calls) == 1 and calls[0][:2] == ["vercel", "whoami"]


def test_a_valid_token_never_shells_out(auth, monkeypatch):
    """Innocence. _api calls _token() per request; refreshing each time is its own outage."""
    _write(auth, FRESH, time.time() + 3600)
    fake, calls = _spy(rc=0)
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert calls == []


def test_a_missing_expiry_is_not_treated_as_expired(auth, monkeypatch):
    """Innocence. `expiresAt: null` means unknown; guessing 'expired' would refresh forever."""
    _write(auth, FRESH, None)
    fake, calls = _spy(rc=0)
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert calls == []


def test_a_failed_refresh_names_the_login_as_the_remaining_step(auth, monkeypatch):
    """The operator step is real HERE and only here — the message must say so."""
    _write(auth, STALE, time.time() - 60)
    fake, _ = _spy(rc=1)
    monkeypatch.setattr(subprocess, "run", fake)

    with pytest.raises(SystemExit) as exc:
        vpd._token()
    assert "vercel login" in str(exc.value)


def test_an_absent_cli_degrades_to_the_same_honest_exit(auth, monkeypatch):
    """A machine without the CLI cannot refresh; it must say that, not traceback."""
    _write(auth, STALE, time.time() - 60)

    def boom(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(SystemExit) as exc:
        vpd._token()
    assert "vercel login" in str(exc.value)


def test_a_refresh_that_exits_zero_without_renewing_is_still_a_failure(auth, monkeypatch):
    """`whoami` succeeding is a proxy; the credential's own expiry is the fact (W88)."""
    _write(auth, STALE, time.time() - 60)
    fake, _ = _spy(rc=0)  # exits 0 and rewrites nothing
    monkeypatch.setattr(subprocess, "run", fake)

    with pytest.raises(SystemExit) as exc:
        vpd._token()
    assert "still expired" in str(exc.value)


# --- `expiresAt` normalisation -------------------------------------------------------------
# Found by an independent review (GLM 5.2, which did not write the code) and reproduced on
# disk before being believed. The file's own docstring had warned about the millisecond case
# since it was written and the code enforced nothing — the warning was decoration, which is
# the same shape as the defect the rest of this corpus covers.


def test_epoch_zero_is_expired_not_falsy(auth, monkeypatch):
    """`bool(0)` is False, so a plain truthiness guard reads 1970 as 'not expired'."""
    _write(auth, STALE, 0)
    fake, calls = _spy(rc=0, rewrite=(auth, FRESH, time.time() + 3600))
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert len(calls) == 1, "epoch 0 is a real timestamp in the past, not a missing one"


def test_a_millisecond_expiry_in_the_past_is_expired(auth, monkeypatch):
    """The trap the docstring names: read as seconds, ms looks valid until the year 58000."""
    _write(auth, STALE, (time.time() - 60) * 1000)
    fake, calls = _spy(rc=0, rewrite=(auth, FRESH, time.time() + 3600))
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert len(calls) == 1


def test_a_millisecond_expiry_in_the_future_is_still_valid(auth, monkeypatch):
    """Innocence for the same conversion — it must not declare every ms value expired."""
    _write(auth, FRESH, (time.time() + 3600) * 1000)
    fake, calls = _spy(rc=0)
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert calls == []


def test_a_numeric_string_expiry_does_not_raise(auth, monkeypatch):
    """`"1785659937" < time.time()` is a TypeError, and nothing caught it."""
    _write(auth, STALE, str(int(time.time() - 60)))
    fake, calls = _spy(rc=0, rewrite=(auth, FRESH, time.time() + 3600))
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert len(calls) == 1


def test_an_unreadable_expiry_resolves_to_expired_not_to_valid(auth, monkeypatch):
    """Fail-safe direction: an extra 1s refresh beats handing out a dead token."""
    _write(auth, STALE, "not-a-timestamp")
    fake, calls = _spy(rc=0, rewrite=(auth, FRESH, time.time() + 3600))
    monkeypatch.setattr(subprocess, "run", fake)

    assert vpd._token() == FRESH
    assert len(calls) == 1
