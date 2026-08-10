"""The ratchet advanced on classification, and the ladder measured the wrong clock.

Two traumas in one organ, both found on 2026-08-06, the second while proving
the cure for the first.

TRAUMA A — the ratchet. `should_alert` speaks only on a CHANGE of verdict, so
for a once-per-lifetime event there is exactly ONE chance to speak, and `main()`
spent it in the wrong place:

    save_state(new_state)          # ran FIRST, unconditionally
    ...
    sent = _send_telegram(...)     # its bool was printed, then dropped

The ratchet recorded "I have told them" on the strength of having CLASSIFIED,
never of having DELIVERED. Measured: #3690 removed the PATH defect that had
stopped this watchdog from ever reading the table, so the run that VERIFIED
#3690 was the first ever to classify a failure. It wrote that to the state file
and delivered nothing anyone read; the next run saw the value already recorded
and printed "tutto OK" about a credential it had just declared dead. Curing a
mute watchdog, then muting it with the act of proving the cure.

TRAUMA B — the ladder. The verdict being ratcheted was itself derived from a
30/14/7/1-**day** classification of `google_drive_tokens.expires_at`, which is
the **one-hour access token**:

    google_drive_service.py:163   expires_at = now + expires_in (3600)
    google_drive_service.py:230   refresh when expires_at <= now + 5min

Measured live the same day, both rows: `expires_at - updated_at == 1h` exactly.
So `days_left` was 0 for a token refreshed a minute ago and negative for every
idle row — TIER_30/14/7 unreachable BY CONSTRUCTION, and the two reachable
outcomes were "🚨 scade DOMANI" about a healthy credential and "🔴 SCADUTO"
about one nobody had used today. It never showed only because the read always
failed: curing the read is what would have armed the false alarm.

What replaced it is NOT "no signal at all". Refresh is lazy-on-use, so
`updated_at` advancing IS a consumer succeeding, and when the refresh token was
revoked that column simply froze:

    row 7dfe56b2…  last successful refresh  2026-07-25 19:02
    GARUDA indexer (daily, GARUDA_DRIVE_USER_ID = that row):
        `invalid_grant: Token has been expired or revoked`, every night
    re-authorised by hand                    2026-08-06 11:11

Twelve days frozen, twelve nights of a real outage. So a frozen row IS worth
saying — as a DIGEST note, because it cannot tell "revoked" from "unused" and
the ground truth is the consumer's own failure. The old ladder did shout at
this row, but for a reason that was false, and shouted identically at healthy
ones, which is why it could never be trusted.

    GUILT ×2     — a failed delivery must NOT advance the ratchet, and the very
                   next run must still speak.
    GUILT (B)    — a freshly-refreshed row must be SILENT, and a frozen one must
                   speak at DIGEST. These are the cases the old corpus could not
                   have: it only ever fed invented day-scale numbers to a pure
                   function, never a row.
    SYMMETRY     — the SA lane carries the same ratchet and the same cure.
    INNOCENCE ×3 — a delivered alert DOES advance it (or this spams every 6h);
                   a healthy verdict is still recorded so a later failure reads
                   as a change; and SYSTEM, frozen BY DESIGN since 2026-05-10,
                   is never called stale.
    TIER         — an actionable fact anywhere in the bundle pulls the whole
                   message to p0; digest only when staleness is all there is.
    ORDER        — send before write, pinned directly: every value-level
                   assertion here passes on the happy path under the old
                   sequence, which only diverges when the send fails.
    SCAR-PIN     — the day ladder cannot come back by name.
"""

from __future__ import annotations

import importlib.util
import json
import re
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
    real one is precisely what trauma A corrupted."""
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


def _healthy_rows(mod):
    """The shape measured on production 2026-08-06 — refreshed minutes ago,
    access token good for another 59 minutes. This is what HEALTHY looks like,
    and the old ladder called it "🚨 scade DOMANI"."""
    now = mod.datetime.now(mod.timezone.utc)
    return (
        {
            "rows": [
                {
                    "user_id": "7dfe56b2",
                    "has_refresh": True,
                    "updated_at": (now - mod.timedelta(minutes=1)).strftime(
                        "%Y-%m-%d %H:%M:%S+00"
                    ),
                    "expires_at": (now + mod.timedelta(minutes=59)).strftime(
                        "%Y-%m-%d %H:%M:%S+00"
                    ),
                }
            ]
        },
        None,
    )


def _idle_rows(mod):
    """Also healthy: nobody has used Drive for 12 days, so the access token in
    the row is long expired. Lazy refresh-on-use means this predicts nothing —
    it is the shape the old ladder screamed "🔴 SCADUTO" about."""
    now = mod.datetime.now(mod.timezone.utc)
    return (
        {
            "rows": [
                {
                    "user_id": "7dfe56b2",
                    "has_refresh": True,
                    "updated_at": (now - mod.timedelta(days=12)).strftime(
                        "%Y-%m-%d %H:%M:%S+00"
                    ),
                    "expires_at": (
                        now - mod.timedelta(days=12) + mod.timedelta(hours=1)
                    ).strftime("%Y-%m-%d %H:%M:%S+00"),
                }
            ]
        },
        None,
    )


def _no_refresh_rows(mod):
    """The real failure: a row that can never renew itself."""
    data, _ = _idle_rows(mod)
    data["rows"][0]["has_refresh"] = False
    return data, None


def _no_rows(mod):
    return {"rows": []}, None


def _saved_health(mod):
    if not mod.STATE_FILE.exists():
        return None
    return json.loads(mod.STATE_FILE.read_text()).get("last_oauth_health")


# ------------------------------------------------------------------- guilt
def test_a_failed_send_does_not_burn_the_one_alert(wd, monkeypatch):
    """TRAUMA A in its exact historical shape: first run ever to see the
    failure, delivery fails. Under the old order the ratchet advanced anyway
    and the next run went silent forever."""
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))
    sends: list[str] = []

    def failing_send(text, bot_token, condition="alert", tier="p0"):
        sends.append(text)
        return False

    monkeypatch.setattr(wd, "_send_telegram", failing_send)

    assert wd.main() == 0
    assert sends, "nothing was even attempted — the probe measured its own setup"
    assert "refresh_token" in sends[0], f"wrong alert body: {sends[0][:160]}"
    assert _saved_health(wd) != wd.HEALTH_NO_REFRESH, (
        "the ratchet advanced on a FAILED delivery — the next run will read "
        "this as 'already told them' and stay silent about a dead credential"
    )

    # And the proof that matters: the NEXT run still speaks.
    sends.clear()
    assert wd.main() == 0
    assert sends, "the retry was silenced — the one alert that mattered is gone"


def test_a_failed_send_of_a_changed_failure_still_retries(wd, monkeypatch):
    """Not only the first-ever verdict: a failure that CHANGES is different
    news with a different remedy, and it too must remain owed when the gateway
    is dead."""
    wd.STATE_FILE.write_text(json.dumps({"last_oauth_health": wd.HEALTH_NO_ROWS}))
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))
    monkeypatch.setattr(
        wd, "_send_telegram", lambda text, bot_token, condition="alert", tier="p0": False
    )

    assert wd.main() == 0
    assert _saved_health(wd) == wd.HEALTH_NO_ROWS, (
        f"verdict moved to {_saved_health(wd)} despite the send failing"
    )


def test_a_freshly_refreshed_row_never_speaks(wd, monkeypatch):
    """TRAUMA B, and the case the old corpus was structurally unable to have.

    It tested `classify_tier(30)`, `classify_tier(14)`, `classify_tier(-1)` —
    a pure function fed numbers nobody had ever measured. Feed it the shape
    the table actually produces one minute after a refresh, and the old ladder
    says "🚨 scade DOMANI": `days_left` is 0, because the window is an hour.
    """
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _healthy_rows(wd))
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": pytest.fail(
            f"a healthy row raised an alert: {text[:200]}"
        ),
    )

    assert wd.main() == 0
    assert _saved_health(wd) == wd.HEALTH_OK


def test_a_frozen_row_is_a_digest_note_not_a_critical(wd, monkeypatch):
    """The signal that WOULD have caught the real outage — at the volume it
    deserves.

    Refresh is lazy-on-use, so `updated_at` advancing is a consumer
    succeeding. Row 7dfe56b2 froze at 2026-07-25 19:02 when its refresh token
    was revoked and stayed frozen twelve days while GARUDA collected
    `invalid_grant` nightly. The old ladder DID shout at this row — "🔴
    SCADUTO" — but for the wrong reason (a one-hour window it read as days),
    and it shouted identically at healthy idle rows, which is why it could
    never have been trusted.

    p0 would be wrong too: this cannot tell "revoked" from "unused", and the
    ground truth is the consumer's own failure. Digest.
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _idle_rows(wd))
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (
            sent.append((tier, text)),
            True,
        )[1],
    )

    assert wd.main() == 0
    assert len(sent) == 1, sent
    tier, text = sent[0]
    assert tier == "digest", f"a staleness note went out at {tier}"
    assert "invalid_grant" in text, (
        "the note must tell the reader where the PROOF is — the consumer's "
        "log — since this verdict alone cannot distinguish revoked from unused"
    )
    assert _saved_health(wd) == wd.HEALTH_STALE_REFRESH


def test_an_actionable_fact_in_the_bundle_pulls_the_whole_message_to_p0(
    wd, monkeypatch
):
    """INNOCENCE for the tier choice: one message carries every fact of the
    run, so burying a real P0 inside a digest flush would be the same class of
    mistake as shouting the staleness note."""
    sent: list[str] = []
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _idle_rows(wd))
    monkeypatch.setattr(wd, "_check_sa_key_age", lambda: wd.SA_KEY_MAX_AGE_DAYS + 5)
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (
            sent.append(tier),
            True,
        )[1],
    )

    assert wd.main() == 0
    assert sent == ["p0"], sent


def test_the_system_row_frozen_by_design_is_not_stale(wd, monkeypatch):
    """`_refresh_token` early-returns for SYSTEM since 2026-05-10 — Drive runs
    on ServiceAccountDriveService and that row is left unrefreshed on purpose.
    Its `updated_at` has been frozen since 2026-06-15. Alarming on it would
    fire every six hours, forever, about the intended state."""
    rows, _ = _idle_rows(wd)
    rows["rows"][0]["user_id"] = "SYSTEM"
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: (rows, None))
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": pytest.fail(
            f"SYSTEM's by-design staleness raised an alert: {text[:200]}"
        ),
    )

    assert wd.main() == 0
    assert _saved_health(wd) == wd.HEALTH_OK


def test_the_sa_key_lane_has_the_same_defect_and_the_same_cure(wd, monkeypatch):
    """SYMMETRY (W101-recidiva): a fix that covers only the lane that bit you
    is half a fix.

    `last_sa_alert_age` is the SA lane's ratchet — it alerts only when the age
    has gone UP since the last alert — and it was written by the same
    unconditional `save_state` call. Without this case, removing `and
    delivered` from the SA branch is invisible: the OAuth tests stub
    `_check_sa_key_age` to None, so that branch never executes in them.
    """
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _healthy_rows(wd))
    monkeypatch.setattr(wd, "_check_sa_key_age", lambda: wd.SA_KEY_MAX_AGE_DAYS + 5)
    sends: list[str] = []

    def failing_send(text, bot_token, condition="alert", tier="p0"):
        sends.append(text)
        return False

    monkeypatch.setattr(wd, "_send_telegram", failing_send)

    assert wd.main() == 0
    assert sends and "SA Key" in sends[0], f"SA alert never raised: {sends}"
    saved = json.loads(wd.STATE_FILE.read_text())
    assert saved.get("last_sa_alert_age") is None, (
        "the SA ratchet advanced on a FAILED delivery — the rotation warning "
        "is owed and would never be re-sent at this age"
    )

    sends.clear()
    assert wd.main() == 0
    assert sends, "the SA retry was silenced"


def test_an_undelivered_sa_alert_does_not_freeze_the_oauth_verdict(wd, monkeypatch):
    """`delivered` is ONE boolean for the whole message, and the two lanes
    share it.

    Gating the HEALTHY OAuth verdict on it as well would let an undelivered
    SA-key alert leave `last_oauth_health` stuck on the previous failure — and
    then the next real occurrence of that same failure reads as a repeat and
    stays silent. Nothing has to be delivered for "it is fine now".
    """
    wd.STATE_FILE.write_text(json.dumps({"last_oauth_health": wd.HEALTH_NO_REFRESH}))
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _healthy_rows(wd))
    monkeypatch.setattr(wd, "_check_sa_key_age", lambda: wd.SA_KEY_MAX_AGE_DAYS + 5)
    monkeypatch.setattr(
        wd, "_send_telegram", lambda text, bot_token, condition="alert", tier="p0": False
    )

    assert wd.main() == 0
    assert _saved_health(wd) == wd.HEALTH_OK, (
        "recovery was not recorded because an unrelated SA alert failed to "
        "send — the next genuine no-refresh will be swallowed as a repeat"
    )


# --------------------------------------------------------------- innocence
def test_a_successful_send_does_advance_the_ratchet(wd, monkeypatch):
    """INNOCENCE, and it is load-bearing: if a delivered alert did NOT advance
    the verdict, this organ would re-send the same p0 every six hours. The fix
    must gate on delivery, not disable the ratchet."""
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))
    sends: list[str] = []
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (sends.append(text), True)[1],
    )

    assert wd.main() == 0
    assert _saved_health(wd) == wd.HEALTH_NO_REFRESH, "a delivered alert must be recorded"

    sends.clear()
    assert wd.main() == 0
    assert not sends, "same verdict re-sent — the ratchet stopped ratcheting"


def test_the_old_day_ladder_keys_are_purged_from_the_state_file(wd, monkeypatch):
    """A state file written before today carries `last_oauth_tier:
    critical_expired` and `last_oauth_days_left: -12`, and the Cell's
    oauth_health_sensor reads exactly those. Leaving them behind would paint
    Drive red forever off a measurement whose scale was wrong."""
    wd.STATE_FILE.write_text(
        json.dumps({"last_oauth_tier": "critical_expired", "last_oauth_days_left": -12})
    )
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _healthy_rows(wd))
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": pytest.fail("nothing to send"),
    )

    assert wd.main() == 0
    saved = json.loads(wd.STATE_FILE.read_text())
    assert "last_oauth_tier" not in saved, saved
    assert "last_oauth_days_left" not in saved, saved
    assert saved["last_oauth_health"] == wd.HEALTH_OK


# ------------------------------------------------------------------- order
def test_the_send_happens_before_the_state_write(wd, monkeypatch):
    """The fix IS the order, so the order is pinned directly.

    Every assertion above passes on the happy path even with the old
    sequence — save-then-send only diverges when the send fails. A refactor
    that quietly restores `save_state` to the top would sail through them all
    and re-open the exact hole. This test fails the moment it does.
    """
    seq: list[str] = []
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (seq.append("send"), True)[1],
    )
    real_save = wd.save_state
    monkeypatch.setattr(
        wd, "save_state", lambda st: (seq.append("save"), real_save(st))[1]
    )

    assert wd.main() == 0
    assert seq == ["send", "save"], f"wrong order: {seq}"


# ---------------------------------------------------------------- scar-pin
def test_the_day_scale_ladder_cannot_come_back(wd):
    """The ladder was not wrong in its thresholds; it was wrong in its UNIT.
    A future edit that reintroduces a day-count over `expires_at` re-opens the
    whole thing, and it would look perfectly reasonable in review.

    The first draft of this pin banned `.days` file-wide and failed on
    line 435 — the SA key age, where a day scale is exactly right, because
    SA keys really do rotate on a 30-day policy. A guard on the FORM of the
    expression instead of on the ENTITY it measures (#3, W109). Both halves
    are asserted below: the OAuth clock may not be reduced to days, and the
    SA clock must still be.
    """
    src = SCRIPT.read_text()
    for banned in ("TIER_30_DAYS", "TIER_14_DAYS", "TIER_7_DAYS", "compute_days_left"):
        assert banned not in src, (
            f"{banned} is back — `expires_at` is a one-hour clock, any "
            "day-scale classification of it is unreachable or false"
        )

    both = [
        line
        for line in src.splitlines()
        if re.search(r"\.days\b", line) and "expires" in line
    ]
    assert not both, (
        f"a day reduction over the OAuth clock reappeared: {both} — on a 1h "
        "delta it yields 0 or -1, which is the false CRITICAL this cured"
    )

    body = src[src.index("def classify_oauth_health") : src.index("def load_state")]
    assert ".days" not in body, (
        "classify_oauth_health reduced a delta to days; the only clock it can "
        "see is the one-hour access token"
    )

    # INNOCENCE, and it is what makes this a check on the entity rather than
    # on the shape of the expression: the SA lane's day count is correct and
    # must survive. A tidy-up that deletes it fails here.
    assert re.search(r"age = \(now - key_dt\)\.days", src), (
        "the SA key age lost its day reduction — SA keys DO rotate on a "
        "30-day policy; this pin bans the OAuth clock, not the SA one"
    )


def test_the_remote_query_reads_every_row_and_every_field_the_classifier_uses(wd):
    """The two halves of this script are separated by an `ssh` and a base64
    blob: one builds a SQL string that runs on Fly, the other classifies the
    JSON that comes back. Nothing executes both in a test, so drift between
    them is invisible — W114, where a reader was written against a vocabulary
    the wire never emitted.

    Mutation found this hole: reverting the query to
    `ORDER BY created_at DESC LIMIT 1` — the exact defect being cured, where
    the watchdog guarded whichever row happened to be newest while the row the
    code names by hand (`SYSTEM`) went unwatched — killed no test at all.

    DECLARED LIMIT: this reads the SQL as text. It proves the query asks for
    what the classifier consumes; it cannot prove Postgres answers.
    """
    src = SCRIPT.read_text()
    start = src.index("code = (")
    query = src[start : src.index("asyncio.run(m())", start)]

    assert "LIMIT" not in query.upper(), (
        "the remote query is back to a single row — a dead SYSTEM row hides "
        "behind any per-user row that happens to be newer"
    )
    assert "c.fetch(" in query and "c.fetchrow(" not in query, (
        "fetchrow returns one row; the classifier judges a list"
    )
    # Every key `classify_oauth_health` and `_age_text` read must be selected.
    for field in ("user_id", "has_refresh", "updated_at"):
        assert field in query, (
            f"the classifier reads {field!r} but the query never selects it — "
            "the reader would see None and judge on it"
        )


# --------------------------------------------- the key names the CONDITION
# Found in the gateway's own state on Pro, minutes after the read finally
# worked (2026-08-06):
#
#   drive-token-watchdog:Nuzantara  count=4  ts=18:00
#   last_text = "🔴 Drive OAuth SCADUTO (12 giorni fa)"
#
# The `ts` is the 18:00 send — the LAST "impossibile connettersi" noise — so
# the 18:42 message was recorded and SUPPRESSED as a repeat of the very noise
# it replaces. One key for two different facts: the loud condition's
# 6/24/72/168h ladder swallows the quiet one, and the quiet one is the whole
# reason the organ exists.


def test_a_read_failure_and_a_credential_failure_do_not_share_a_dedup_key(
    wd, monkeypatch
):
    """THE defect. Two runs, two different facts; if the keys match, the
    second is swallowed by the first's ladder inside the gateway."""
    keys: list[str] = []
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (keys.append(condition), True)[1],
    )

    monkeypatch.setattr(
        wd, "_check_drive_token_via_fly", lambda: (None, "fly ssh rifiutato")
    )
    assert wd.main() == 0

    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))
    assert wd.main() == 0

    assert len(keys) == 2, f"expected both to alert, got {keys}"
    assert keys[0] != keys[1], (
        f"read-failure and credential-failure share the condition {keys[0]!r} — "
        "the second will be suppressed as a repeat of the noise it replaces"
    )
    assert "read-failure" in keys[0] and wd.HEALTH_NO_REFRESH in keys[1], keys


def test_the_key_carries_the_verdict_but_never_a_measurement(wd, monkeypatch):
    """INNOCENCE + #3677: the key must be stable across runs of the SAME
    condition. A verdict is a condition; an age or a count is a measurement,
    and a measurement in the key mints a fresh key per run and defeats every
    window."""
    keys: list[str] = []
    monkeypatch.setattr(
        wd,
        "_send_telegram",
        lambda text, bot_token, condition="alert", tier="p0": (keys.append(condition), True)[1],
    )
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: _no_refresh_rows(wd))

    assert wd.main() == 0
    wd.STATE_FILE.write_text("{}")  # forget, so it alerts again

    older, _ = _no_refresh_rows(wd)
    older["rows"][0]["updated_at"] = "2026-01-02 03:04:05+00"
    older["rows"][0]["expires_at"] = "2026-01-02 04:04:05+00"
    monkeypatch.setattr(wd, "_check_drive_token_via_fly", lambda: (older, None))
    assert wd.main() == 0

    assert len(keys) == 2 and keys[0] == keys[1], (
        f"the key moved with the measurement: {keys}"
    )
    assert not re.search(r"\d", keys[0]), f"a measurement leaked into the key: {keys}"


def test_the_condition_actually_reaches_the_dedup_key_on_the_wire(
    wd, monkeypatch, tmp_path
):
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
        # subprocess.run(..., capture_output=True, text=True) ALWAYS returns a
        # CompletedProcess carrying .stderr; a fake without it is not a thinner
        # CompletedProcess, it is a different object. Adding the verdict read to
        # _send_telegram made the gap visible: the fake raised AttributeError,
        # the caller's `except` swallowed it, and the function reported "not
        # sent" for a send that worked — the fake and the code were wrong
        # together, which is why the test stayed green while the fake was unfaithful (W114).
        stderr = "tg_notify: spooled\n"
        stdout = ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _Result()

    gateway = tmp_path / "tg_notify.py"
    gateway.write_text("")
    monkeypatch.setattr(wd, "PROJECT_ROOT", tmp_path.parent)
    monkeypatch.setattr(wd.subprocess, "run", fake_run)
    monkeypatch.setattr(wd.Path, "is_file", lambda self: True)

    assert wd._send_telegram("body", "token", "no-refresh") is True
    assert wd._send_telegram("body", "token", "read-failure") is True

    keys = [c[c.index("--dedup-key") + 1] for c in calls]
    assert len(keys) == 2, keys
    assert "no-refresh" in keys[0], f"the condition never reached the key: {keys[0]}"
    assert "read-failure" in keys[1], f"the condition never reached the key: {keys[1]}"
    assert keys[0] != keys[1], (
        f"both conditions produced the SAME key {keys[0]!r} — this is exactly "
        "the state found on Pro, where the real message was swallowed by the "
        "ladder of the connection-error noise it replaces"
    )
