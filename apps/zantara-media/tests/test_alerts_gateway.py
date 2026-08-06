"""The organ that KNEW the credential was dead could not speak, 141 nights running.

TRAUMA (2026-08-06). `zantara_media.alerts.send_critical_alert` POSTed straight
to the Telegram API with a token read from the caller's environment:

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot send alert: %s", message)
        return

`garuda-indexer` runs from cron (`36 20 * * *` on Pro), and cron's environment
does not carry that variable. Measured on Pro before touching anything:

    $ grep -c invalid_grant ~/logs/cron-tmp/garuda-indexer.log
    141
    ... 2026-08-05 20:36:12 [WARNING] zantara_media.alerts:
        TELEGRAM_BOT_TOKEN not set — cannot send alert:
        💥 GARUDA indexer CRASHED: ('invalid_grant: Token has been expired or revoked', ...)

Google was answering `invalid_grant` on every nightly run since at least
2026-07-27. The indexer exited 1 each time. The alarm logged its own silence
and returned. W108: the alarm depended on something the environment it runs in
does not provide, and left the failure in a log nobody reads.

This is also the reason the Drive outage was found by hand rather than
reported: the watchdog that was SUPPOSED to warn was blind for unrelated
reasons (#3690 PATH, then the fly credential, then a day-ladder over a
one-hour clock), and the organ that actually KNEW was muted here.

The cure is not to teach this module to find the secret — that is the
gateway's job, and `scripts/tg_notify.py` already falls back to
`~/.nuzantara-secrets.env` when the environment is bare.

    GUILT      — with NO TELEGRAM_BOT_TOKEN in the environment, the exact
                 production shape, the alert still leaves the process
    GUILT      — a missing gateway is reported at ERROR *with the payload*,
                 never a quiet return
    GUILT      — a non-zero gateway rc is surfaced, not swallowed
    INNOCENCE  — never raises, whatever happens; the indexer must still exit
                 on its own terms
    KEY        — distinct conditions get distinct dedup keys, or one failure's
                 repeat ladder swallows another's first occurrence
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from zantara_media import alerts


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    """A repo-shaped tmp dir with a tg_notify.py the tests can point at."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "tg_notify.py").write_text("")
    monkeypatch.setenv("NUZANTARA_REPO_ROOT", str(tmp_path))
    return scripts / "tg_notify.py"


class _Proc:
    def __init__(self, rc: int, stderr: bytes = b""):
        self.returncode = rc
        self._stderr = stderr

    async def communicate(self):
        return b"", self._stderr


def _record_exec(monkeypatch, rc: int = 0, stderr: bytes = b""):
    """Capture the argv the gateway would be invoked with."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _Proc(rc, stderr)

    monkeypatch.setattr(alerts.asyncio, "create_subprocess_exec", fake_exec)
    return calls


# ------------------------------------------------------------------- guilt
def test_it_speaks_with_no_telegram_token_in_the_environment(
    gateway, monkeypatch
):
    """THE defect, in its exact production shape. `send_critical_alert` used
    to check `os.getenv("TELEGRAM_BOT_TOKEN")` first and return when it was
    absent — which, under cron, is always."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    calls = _record_exec(monkeypatch)

    ok = asyncio.run(alerts.send_critical_alert("indexer died", condition="x"))

    assert ok is True
    assert calls, (
        "nothing was invoked with a bare environment — this is the 141-night "
        "silence, reproduced"
    )
    argv = calls[0]
    assert str(gateway) in argv, argv
    assert "indexer died" in argv[-1], argv


def test_a_missing_gateway_is_loud_and_carries_the_payload(monkeypatch, caplog):
    """If the alert cannot leave the machine, the log is the last place it
    exists — so it must be there at ERROR, with the body. The old code logged
    at WARNING and let the urgency drain out with the message."""
    monkeypatch.setenv("NUZANTARA_REPO_ROOT", "/nonexistent")
    monkeypatch.setattr(alerts.Path, "home", staticmethod(lambda: alerts.Path("/nonexistent")))
    monkeypatch.setattr(alerts, "_resolve_gateway", lambda: None)

    with caplog.at_level(logging.ERROR):
        ok = asyncio.run(alerts.send_critical_alert("the roof is on fire"))

    assert ok is False
    assert any(
        r.levelno >= logging.ERROR and "the roof is on fire" in r.getMessage()
        for r in caplog.records
    ), f"the payload never reached the log: {[r.getMessage() for r in caplog.records]}"


def test_a_failing_gateway_is_surfaced_not_swallowed(gateway, monkeypatch, caplog):
    _record_exec(monkeypatch, rc=3, stderr=b"budget exhausted")

    with caplog.at_level(logging.ERROR):
        ok = asyncio.run(alerts.send_critical_alert("boom"))

    assert ok is False
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "rc=3" in joined, joined
    assert "budget exhausted" in joined, joined


def test_the_rc_is_logged_even_on_success(gateway, monkeypatch, caplog):
    """A silent success is how you end up unable to tell "it sent" from "it
    never ran" — which is the whole shape of this trauma."""
    _record_exec(monkeypatch, rc=0)

    with caplog.at_level(logging.INFO):
        assert asyncio.run(alerts.send_critical_alert("fine")) is True

    assert any("rc=0" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------- innocence
@pytest.mark.parametrize("boom", [OSError("no exec"), asyncio.TimeoutError()])
def test_it_never_raises_whatever_happens(gateway, monkeypatch, boom):
    """An alert must not crash the indexer. Both the "cannot invoke" and the
    "hangs forever" paths return False instead of propagating."""

    async def exploding(*args, **kwargs):
        raise boom

    monkeypatch.setattr(alerts.asyncio, "create_subprocess_exec", exploding)
    assert asyncio.run(alerts.send_critical_alert("x")) is False


# --------------------------------------------------------------------- key
def test_distinct_conditions_get_distinct_dedup_keys(gateway, monkeypatch):
    """A crash and a nightly "files archived" summary must not share a key:
    the ladder of whichever fires first would swallow the other's FIRST
    occurrence, and that is the one that matters (#3677)."""
    calls = _record_exec(monkeypatch)

    asyncio.run(alerts.send_critical_alert("crashed", condition="indexer-crash"))
    asyncio.run(alerts.send_critical_alert("archived 3", condition="gc-summary"))

    keys = [argv[argv.index("--dedup-key") + 1] for argv in calls]
    assert len(keys) == 2, keys
    assert keys[0] != keys[1], f"both conditions produced {keys[0]!r}"
    assert "indexer-crash" in keys[0] and "gc-summary" in keys[1], keys


def test_the_key_is_stable_across_runs_of_the_same_condition(gateway, monkeypatch):
    """INNOCENCE for the above: the key must NOT move with the message body,
    or every night mints a fresh key and the repeat ladder never applies."""
    calls = _record_exec(monkeypatch)

    asyncio.run(alerts.send_critical_alert("CRASHED: error at 20:36:12", condition="c"))
    asyncio.run(alerts.send_critical_alert("CRASHED: error at 20:36:14", condition="c"))

    keys = [argv[argv.index("--dedup-key") + 1] for argv in calls]
    assert keys[0] == keys[1], f"the key moved with the message: {keys}"
