"""The Drive watchdog called bare `fly`, so it only ever worked interactively.

TRAUMA (2026-08-06). `scripts/drive_token_watchdog.py` exists to warn 7 days
before the Drive OAuth token expires. It ran every 6h from cron and sent
"impossibile connettersi al backend Fly.io" 65 times over 24 days. Meanwhile,
measured on the live production DB this turn:

    google_drive_tokens.expires_at = 2026-07-25 20:02:03+00   (11.5 days ago)

The one alert the organ exists to send was never sent. The noise defect was
not merely noise: it MASKED the failure it was built to catch.

Cause, reproduced both ways on Pro before touching anything:

    PATH=/usr/bin:/bin:/usr/sbin:/sbin            -> _check_drive_token_via_fly() = None
    PATH=/opt/homebrew/bin:/usr/bin:/bin:/sbin    -> {'expires_at': '2026-07-25 ...'}

cron's PATH has no Homebrew; flyctl lives in /opt/homebrew/bin. Same shape as
W108 one level up: the tool the alarm depends on is resolved through an
environment the alarm's own author never ran in.

Second defect, and the one that kept it alive for 24 days: the message said
"Verifica che `fly ssh` funzioni", pointing every reader at fly's auth — which
was fine. A diagnosis aimed away from the cause costs more than silence
(W106: cure and message expire together).

    GUILT      — under cron's PATH the read still succeeds (absolute fallback)
    GUILT      — with flyctl genuinely absent, the failure NAMES the PATH
    GUILT      — a non-zero fly exit is reported with fly's OWN words
    INNOCENCE  — a normal environment is unaffected and returns data
    INNOCENCE  — the operator's own `which fly` still wins over the fallback
    CONTRACT   — the alert text never again prescribes "check that fly ssh works"
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "drive_token_watchdog.py"


def _wire_payload(expires_at: str, updated_at: str) -> str:
    """One `echo` line in the shape the fly side ACTUALLY prints.

    W114: a fake built at the service boundary in the vocabulary the reader
    imagines confirms the reader instead of testing it. These fakes stand in
    for the remote `python3 -c` and must speak its wire format — a `rows`
    list carrying `user_id` / `has_refresh` / `expires_at` / `updated_at`. An
    earlier version of this corpus echoed a flat `{"expires_at": ...}` object
    that the remote side had stopped producing, and stayed green.
    """
    payload = json.dumps(
        {
            "rows": [
                {
                    "user_id": "SYSTEM",
                    "has_refresh": True,
                    "expires_at": expires_at,
                    "updated_at": updated_at,
                }
            ]
        }
    )
    return f"echo '{payload}'\n"


def _load():
    spec = importlib.util.spec_from_file_location("drive_token_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the module defines a @dataclass, and dataclasses
    # resolves annotations through sys.modules[cls.__module__] — absent that
    # entry it dies on AttributeError before a single test body runs.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def wd():
    return _load()


# ------------------------------------------------------------------- guilt
def test_resolves_fly_under_crons_impoverished_path(wd, monkeypatch, tmp_path):
    """THE defect. cron gives /usr/bin:/bin:/usr/sbin:/sbin and nothing else."""
    fake = tmp_path / "flyctl"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    monkeypatch.setattr(wd, "_FLY_CANDIDATES", (str(fake),))

    assert wd._resolve_fly() == str(fake), (
        "with Homebrew off PATH the absolute fallback must still find flyctl — "
        "this is the exact environment in which the watchdog ran 65 times")


def test_a_genuinely_absent_fly_names_the_path_not_ssh(wd, monkeypatch):
    """When flyctl really is missing, the reason must say so — and must not
    send the reader to fly's authentication, which is what the old text did."""
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(wd, "_FLY_CANDIDATES", ())

    data, reason = wd._check_drive_token_via_fly()
    assert data is None
    assert "PATH" in reason, reason
    assert "ssh" not in reason.lower(), (
        f"the reason blames ssh again: {reason!r}")


def test_a_failing_fly_is_reported_in_flys_own_words(wd, monkeypatch, tmp_path):
    """A fly that runs and fails must surface fly's message, never a guess."""
    fake = tmp_path / "flyctl"
    fake.write_text("#!/bin/sh\necho 'Error: Could not find App nuzantara-rag' >&2\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setattr(wd, "_resolve_fly", lambda: str(fake))

    data, reason = wd._check_drive_token_via_fly()
    assert data is None
    assert "Could not find App" in reason, reason


# --------------------------------------------------------------- innocence
def test_a_healthy_environment_still_returns_the_token(wd, monkeypatch, tmp_path):
    """INNOCENCE: the happy path is untouched — and the tuple's data slot is
    what the caller reads. A fix that broke this would blind the organ the
    other way."""
    fake = tmp_path / "flyctl"
    fake.write_text(
        "#!/bin/sh\n"
        "echo 'Connecting to fdaa:...'\n"
        + _wire_payload("2026-12-01 00:00:00+00:00", "2026-11-30 23:00:00+00:00")
    )
    fake.chmod(0o755)
    monkeypatch.setattr(wd, "_resolve_fly", lambda: str(fake))

    data, reason = wd._check_drive_token_via_fly()
    assert reason is None, reason
    assert data["rows"][0]["expires_at"].startswith("2026-12-01")


def test_an_installed_fly_on_path_wins_over_the_fallback(wd, monkeypatch, tmp_path):
    """INNOCENCE: the absolute list is a FALLBACK, not an override. An operator
    who installs flyctl elsewhere must not be silently routed to a stale one."""
    onpath = tmp_path / "bin"
    onpath.mkdir()
    real = onpath / "fly"
    real.write_text("#!/bin/sh\nexit 0\n")
    real.chmod(0o755)
    decoy = tmp_path / "decoy-flyctl"
    decoy.write_text("#!/bin/sh\nexit 0\n")
    decoy.chmod(0o755)

    monkeypatch.setenv("PATH", f"{onpath}:/usr/bin:/bin")
    monkeypatch.setattr(wd, "_FLY_CANDIDATES", (str(decoy),))

    assert wd._resolve_fly() == str(real)


# ---------------------------------------------------------------- contract
def test_the_alert_text_no_longer_prescribes_checking_fly_ssh():
    """The sentence that misdirected every reader for 24 days is gone, and the
    replacement warns that expiry is unguarded while it fires — the fact whose
    absence let a real expiry pass unnoticed."""
    src = SCRIPT.read_text()
    assert "Verifica che <code>fly ssh</code> funzioni" not in src, (
        "the misdirecting diagnosis is back")
    assert "la credenziale NON è sorvegliata" in src, (
        "the alert must say the credential check is blind while this fires")


# ------------------------------------------- second cause: the CREDENTIAL
# Found 2026-08-06 in PROVE-LIVE of the PATH cure above, and it is a distinct
# defect with the same symptom. Measured on Pro, running the REAL command
# rather than `auth whoami` (which passes for a token scoped to another app
# and only dies later, on the work):
#
#   FLY_API_TOKEN from ~/.nuzantara-secrets.env -> Could not find App "nuzantara-rag"
#   FLY_API_TOKEN unset, ~/.fly/config.yml      -> PROBE_OK
#
# cron reaches this script through cron-wrapper.sh, which SOURCES the secrets
# file — so the production path always carried the credential that cannot see
# this app, and the PATH cure alone would never have made the organ see the
# expiry. The earlier verification runs succeeded only because they ran under
# `env -i`, which stripped it: the mirror of W108's dev machine that could not
# reproduce the red.


def _fly_that_needs_no_token(tmp_path, name="flyctl"):
    """A fake fly that FAILS when FLY_API_TOKEN is set and succeeds when it is
    not — the live behaviour, inverted-testable."""
    fake = tmp_path / name
    fake.write_text(
        "#!/bin/sh\n"
        'if [ -n "$FLY_API_TOKEN" ]; then\n'
        "  echo 'Error: Could not find App \"nuzantara-rag\"' >&2\n"
        "  exit 1\n"
        "fi\n"
        + _wire_payload("2026-07-25 20:02:03+00:00", "2026-07-25 19:02:03+00:00")
    )
    fake.chmod(0o755)
    return fake


def test_a_wrongly_scoped_env_token_falls_back_to_the_config_credential(
    wd, monkeypatch, tmp_path
):
    """GUILT: the exact production shape. With only the first credential tried,
    the read fails and the expiry is never seen."""
    monkeypatch.setattr(wd, "_resolve_fly",
                        lambda: str(_fly_that_needs_no_token(tmp_path)))
    monkeypatch.setenv("FLY_API_TOKEN", "FlyV1 scoped-to-another-app")

    data, reason = wd._check_drive_token_via_fly()
    assert reason is None, f"the fallback credential was never tried: {reason}"
    assert data["rows"][0]["expires_at"].startswith("2026-07-25")


def test_when_every_credential_refuses_the_reason_names_each_one(
    wd, monkeypatch, tmp_path
):
    """GUILT: both refuse. The message must say what EACH attempt said —
    a diagnosis aimed away from the cause costs more than silence (W106)."""
    fake = tmp_path / "flyctl"
    fake.write_text("#!/bin/sh\necho 'Error: unauthorized' >&2\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setattr(wd, "_resolve_fly", lambda: str(fake))
    monkeypatch.setenv("FLY_API_TOKEN", "FlyV1 also-dead")

    data, reason = wd._check_drive_token_via_fly()
    assert data is None
    assert "env/inherited" in reason and "config.yml" in reason, reason
    assert "unauthorized" in reason, reason


def test_a_working_env_token_is_used_and_the_fallback_is_never_reached(
    wd, monkeypatch, tmp_path
):
    """INNOCENCE, and it is why this is a PROBE and not a hardcoded `unset`.

    W106 is precisely the story of hardcoding 'the env token is stale, always
    drop it': true the day it was written, the world inverted, and the cure
    threw away the only working credential for 27h. Here the env credential
    works, so it must be the one used — no second attempt, no preference
    frozen into the code.
    """
    counter = tmp_path / "calls"
    fake = tmp_path / "flyctl"
    fake.write_text(
        "#!/bin/sh\n"
        f"echo x >> {counter}\n"
        + _wire_payload("2026-12-01 00:00:00+00:00", "2026-11-30 23:00:00+00:00")
    )
    fake.chmod(0o755)
    monkeypatch.setattr(wd, "_resolve_fly", lambda: str(fake))
    monkeypatch.setenv("FLY_API_TOKEN", "FlyV1 perfectly-good")

    data, reason = wd._check_drive_token_via_fly()
    assert reason is None, reason
    assert data["rows"][0]["expires_at"].startswith("2026-12-01")
    assert counter.read_text().count("x") == 1, (
        "fly was invoked twice — the first credential worked and the fallback "
        "must not have run")
