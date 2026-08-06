"""The tier ratchet advanced on classification, so verifying the cure muted it.

TRAUMA (2026-08-06, found in PROVE-LIVE of #3690 — hours after it merged).

`should_alert` fires only on a strictly-more-severe transition. For a
once-per-lifetime event like "the OAuth token expired" that means there is
exactly ONE chance to speak, ever. And `main()` spent it in the wrong place:

    save_state(new_state)          # line 532 — ran FIRST, unconditionally
    ...
    sent = _send_telegram(...)     # line 538 — its bool was printed, then dropped

So the ratchet recorded "I have told them about tier X" on the strength of
having CLASSIFIED tier X, never on having DELIVERED it.

The sequence, measured on Pro rather than reasoned about:

  * `google_drive_tokens` — both rows expired, the live one on 2026-07-25
    (`expires_at > now()` is false, 12 days ago);
  * #3690 removed the PATH defect that had stopped the watchdog from ever
    reading that row, and the run that VERIFIED #3690 was therefore the first
    ever to classify `critical_expired`. It wrote that to the state file;
  * the state file on Pro then read
    `{"last_oauth_tier": "critical_expired", "last_oauth_days_left": -12}`;
  * so the next run took the de-escalation branch and printed
    **"tutto OK (token valido, SA key OK)"** about a dead credential.

Curing a mute watchdog, and then muting it with the act of proving the cure.
Same family as W96 (a test writing production state) and as the standing
lesson that arming a guard before the entrance deletes the last true signal —
here the "test" was a live verification run and the state it wrote was real.

Three ways the old order lost the one message, all covered below: a
verification run, a send that fails, and a cron environment with no
TELEGRAM_BOT_TOKEN (`_send_telegram` returns False on exactly that).

    GUILT ×2     — a failed delivery must NOT advance the ratchet, and the
                   very next run must still speak. Asserted on the real
                   historical shape (first-ever `critical_expired`) and on an
                   escalation between two live tiers.
    INNOCENCE ×2 — a successful delivery DOES advance it (or the next run
                   would spam), and a clean token still records TIER_OK so a
                   later escalation reads as a transition.
    ORDER        — send happens before the write. Pinned directly, because
                   the fix is the ORDER and a future refactor that restores
                   the old sequence would pass every value-level assertion
                   above on the happy path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "drive_token_watchdog.py"


def _load():
    spec = importlib.util.spec_from_file_location("drive_token_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec — the module defines a @dataclass and dataclasses
    # resolves annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def wd(tmp_path, monkeypatch):
    """The watchdog with its state file redirected to tmp and every outbound
    path stubbed. W96: this corpus must never touch the real state file — the
    real one is precisely what the trauma above corrupted."""
    mod = _load()
    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "DRY_RUN", False)
    # SA-key lane out of the way: gcloud is not present in CI and its absence
    # would otherwise decide the test instead of the code under test (W108).
    monkeypatch.setattr(mod, "_check_sa_key_age", lambda: None)
    monkeypatch.setattr(mod, "_load_env", lambda: {"TELEGRAM_BOT_TOKEN": "t"})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    return mod


def _token(expires_at: str):
    return ({"expires_at": expires_at, "created_at": "2026-04-07 23:31:07+00"}, None)


def _saved_tier(mod):
    if not mod.STATE_FILE.exists():
        return None
    return json.loads(mod.STATE_FILE.read_text()).get("last_oauth_tier")


# ------------------------------------------------------------------- guilt
def test_a_failed_send_does_not_burn_the_one_expiry_alert(wd, monkeypatch):
    """THE defect, in its exact historical shape.

    First run ever to see the expired token; delivery fails. Under the old
    order the ratchet advanced anyway and the next run went silent forever.
    """
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-25 20:02:03+00"))
    sends: list[str] = []

    def failing_send(text, bot_token, condition="alert"):
        sends.append(text)
        return False

    monkeypatch.setattr(wd, "_send_telegram", failing_send)

    assert wd.main() == 0
    assert sends, "nothing was even attempted — the probe measured its own setup"
    assert "SCADUTO" in sends[0], f"wrong alert body: {sends[0][:120]}"
    assert _saved_tier(wd) != wd.TIER_EXPIRED, (
        "the ratchet advanced on a FAILED delivery — the next run will read "
        "this as 'already told them' and print 'tutto OK' about a dead token")

    # And the proof that matters: the NEXT run still speaks.
    sends.clear()
    assert wd.main() == 0
    assert sends, "the retry was silenced — the one alert that mattered is gone"


def test_a_failed_send_of_an_escalation_still_retries(wd, monkeypatch):
    """Not only the first-ever transition: any escalation whose delivery fails
    must remain owed. 14 days -> 7 days with a dead gateway."""
    wd.STATE_FILE.write_text(json.dumps({"last_oauth_tier": wd.TIER_14_DAYS}))
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token(
                            (wd.datetime.now(wd.timezone.utc)
                             + wd.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S+00")))
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert": False)

    assert wd.main() == 0
    assert _saved_tier(wd) == wd.TIER_14_DAYS, (
        f"tier moved to {_saved_tier(wd)} despite the send failing")


def test_the_sa_key_lane_has_the_same_defect_and_the_same_cure(wd, monkeypatch):
    """SYMMETRY (W101-recidiva): a fix that covers only the lane that bit you
    is half a fix.

    `last_sa_alert_age` is the SA lane's ratchet — it alerts only when the age
    has gone UP since the last alert — and it was written by the same
    unconditional `save_state` call. Without this case, removing `and
    delivered` from the SA branch is invisible: the OAuth tests stub
    `_check_sa_key_age` to None, so that branch never executes in them.
    """
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token(
                            (wd.datetime.now(wd.timezone.utc)
                             + wd.timedelta(days=80)).strftime("%Y-%m-%d %H:%M:%S+00")))
    monkeypatch.setattr(wd, "_check_sa_key_age", lambda: wd.SA_KEY_MAX_AGE_DAYS + 5)
    sends: list[str] = []

    def failing_send(text, bot_token, condition="alert"):
        sends.append(text)
        return False

    monkeypatch.setattr(wd, "_send_telegram", failing_send)

    assert wd.main() == 0
    assert sends and "SA Key" in sends[0], f"SA alert never raised: {sends}"
    saved = json.loads(wd.STATE_FILE.read_text())
    assert saved.get("last_sa_alert_age") is None, (
        "the SA ratchet advanced on a FAILED delivery — the rotation warning "
        "is owed and would never be re-sent at this age")

    sends.clear()
    assert wd.main() == 0
    assert sends, "the SA retry was silenced"


# --------------------------------------------------------------- innocence
def test_a_successful_send_does_advance_the_ratchet(wd, monkeypatch):
    """INNOCENCE, and it is load-bearing: if a delivered alert did NOT advance
    the tier, this organ would re-send the same p0 every six hours. The fix
    must gate on delivery, not disable the ratchet."""
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-25 20:02:03+00"))
    sends: list[str] = []
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert": (sends.append(text), True)[1])

    assert wd.main() == 0
    assert _saved_tier(wd) == wd.TIER_EXPIRED, "a delivered alert must be recorded"

    sends.clear()
    assert wd.main() == 0
    assert not sends, "same tier re-sent — the ratchet stopped ratcheting"


def test_a_healthy_token_still_records_its_tier(wd, monkeypatch):
    """INNOCENCE: with nothing to send there is nothing to deliver, so the
    write must still happen — otherwise TIER_OK is never stored and a later
    escalation has no baseline to be a transition FROM."""
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token(
                            (wd.datetime.now(wd.timezone.utc)
                             + wd.timedelta(days=80)).strftime("%Y-%m-%d %H:%M:%S+00")))
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert": pytest.fail("nothing should be sent"))

    assert wd.main() == 0
    assert _saved_tier(wd) == wd.TIER_OK


# ------------------------------------------------------------------- order
def test_the_send_happens_before_the_state_write(wd, monkeypatch):
    """The fix IS the order, so the order is pinned directly.

    Every assertion above passes on the happy path even with the old
    sequence — save-then-send only diverges when the send fails. A refactor
    that quietly restores `save_state` to the top would sail through them all
    and re-open the exact hole. This test fails the moment it does.
    """
    seq: list[str] = []
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-25 20:02:03+00"))
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert": (seq.append("send"), True)[1])
    real_save = wd.save_state
    monkeypatch.setattr(wd, "save_state",
                        lambda st: (seq.append("save"), real_save(st))[1])

    assert wd.main() == 0
    assert seq == ["send", "save"], f"wrong order: {seq}"


# --------------------------------------------- the key names the CONDITION
# Found in the gateway's own state on Pro, minutes after the read finally
# worked (2026-08-06):
#
#   drive-token-watchdog:Nuzantara  count=4  ts=18:00
#   last_text = "🔴 Drive OAuth SCADUTO (12 giorni fa)"
#
# The `ts` is the 18:00 send — the LAST "impossibile connettersi" noise — so
# the 18:42 expiry message was recorded and SUPPRESSED as a repeat of the very
# noise it replaces. One key for two different facts: the loud condition's
# 6/24/72/168h ladder swallows the quiet one, and the quiet one is the whole
# reason the organ exists.


def _key_of(sends):
    return sends[-1]


def test_a_read_failure_and_an_expiry_do_not_share_a_dedup_key(wd, monkeypatch):
    """THE defect. Two runs, two different facts; if the keys match, the
    second is swallowed by the first's ladder inside the gateway."""
    keys: list[str] = []
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert":
                        (keys.append(condition), True)[1])

    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: (None, "fly ssh rifiutato"))
    assert wd.main() == 0

    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-25 20:02:03+00"))
    assert wd.main() == 0

    assert len(keys) == 2, f"expected both to alert, got {keys}"
    assert keys[0] != keys[1], (
        f"read-failure and expiry share the condition {keys[0]!r} — the "
        "expiry will be suppressed as a repeat of the noise it replaces")
    assert "read-failure" in keys[0] and wd.TIER_EXPIRED in keys[1], keys


def test_the_key_carries_the_tier_but_never_the_day_count(wd, monkeypatch):
    """INNOCENCE + #3677: the key must be stable across runs of the SAME
    condition. A tier is a condition; `days_left` is a measurement, and a
    measurement in the key mints a fresh key per run and defeats every window.
    """
    keys: list[str] = []
    monkeypatch.setattr(wd, "_send_telegram",
                        lambda text, bot_token, condition="alert":
                        (keys.append(condition), True)[1])
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-25 20:02:03+00"))

    assert wd.main() == 0
    wd.STATE_FILE.write_text("{}")          # forget, so it alerts again
    monkeypatch.setattr(wd, "_check_drive_token_via_fly",
                        lambda: _token("2026-07-20 20:02:03+00"))  # -17 days now
    assert wd.main() == 0

    assert len(keys) == 2 and keys[0] == keys[1], (
        f"the key moved with the day count: {keys}")
    assert "-12" not in keys[0] and "-17" not in keys[1], (
        f"a measurement leaked into the key: {keys}")


def test_the_condition_actually_reaches_the_dedup_key_on_the_wire(wd, monkeypatch, tmp_path):
    """The two tests above assert the CONDITION main() computes. Mutation
    caught that this is not the same claim: deleting `{condition}` from the
    key that `_send_telegram` builds left them both green.

    The defect lived IN THE KEY — that is the string the gateway's ladder
    matches on — so it has to be read off the actual argv, one layer below
    where the earlier assertions stop.
    """
    calls: list[list[str]] = []

    class _Result:
        returncode = 0

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _Result()

    gateway = tmp_path / "tg_notify.py"
    gateway.write_text("")
    monkeypatch.setattr(wd, "PROJECT_ROOT", tmp_path.parent)
    monkeypatch.setattr(wd.subprocess, "run", fake_run)
    monkeypatch.setattr(wd.Path, "is_file", lambda self: True)

    assert wd._send_telegram("body", "token", "critical_expired") is True
    assert wd._send_telegram("body", "token", "read-failure") is True

    keys = [c[c.index("--dedup-key") + 1] for c in calls]
    assert len(keys) == 2, keys
    assert "critical_expired" in keys[0], f"the condition never reached the key: {keys[0]}"
    assert "read-failure" in keys[1], f"the condition never reached the key: {keys[1]}"
    assert keys[0] != keys[1], (
        f"both conditions produced the SAME key {keys[0]!r} — this is exactly "
        "the state found on Pro, where the expiry was swallowed by the ladder "
        "of the connection-error noise it replaces")
