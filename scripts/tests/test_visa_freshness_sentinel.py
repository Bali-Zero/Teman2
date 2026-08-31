"""Tests for `scripts/visa_freshness_sentinel.py`.

Guilt/innocence pairs for the pure classification core (`classify_freshness`),
an explicit assertion on the inclusive-boundary semantic anchor (`_is_current`,
mirrored verbatim from evaluate_path.py::_evaluate_source_freshness), and a
gateway-invocation test using a fake `tg_notify.py` in a tmp dir (the W107
fake-world pattern — proves the sentinel calls the gateway with the right
tier/source/dedup-key per outcome, and that a gateway failure never crashes
the caller).
"""

from __future__ import annotations

import json
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import visa_freshness_sentinel as vfs  # noqa: E402

VERIFIED_AT = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
MAX_AGE_SECONDS = 604_800  # 7 days — the live OFFICIAL_PORTAL policy value
BOUNDARY = VERIFIED_AT + timedelta(seconds=MAX_AGE_SECONDS)


def _portal_record(
    record_id: str,
    verified_at_iso: str,
    *,
    title: str = "A portal source",
    max_age_seconds: int = MAX_AGE_SECONDS,
    with_policy: bool = True,
    authority_type: str = "OFFICIAL_PORTAL",
) -> dict:
    record = {
        "source_record_id": record_id,
        "title": title,
        "authority_type": authority_type,
        "verified_at": verified_at_iso,
    }
    if with_policy:
        record["freshness_policy"] = {
            "kind": "MAX_AGE_SINCE_VERIFIED_AT",
            "max_age_seconds": max_age_seconds,
        }
    return record


# ---------------------------------------------------------------------------
# _is_current — the semantic anchor (boundary EXACTLY at verified_at+max_age
# is still CURRENT, inclusive — this is the property the whole sentinel
# exists to never disagree with the engine about).
# ---------------------------------------------------------------------------


def test_is_current_boundary_exactly_at_max_age_is_current():
    assert vfs._is_current(VERIFIED_AT, MAX_AGE_SECONDS, BOUNDARY) is True


def test_is_current_boundary_plus_one_second_is_not_current():
    assert vfs._is_current(VERIFIED_AT, MAX_AGE_SECONDS, BOUNDARY + timedelta(seconds=1)) is False


# ---------------------------------------------------------------------------
# classify_freshness — GUILT
# ---------------------------------------------------------------------------


def test_guilt_record_at_boundary_plus_one_second_is_stale():
    now = BOUNDARY + timedelta(seconds=1)
    record = _portal_record("11111111-1111-1111-1111-111111111111", VERIFIED_AT.isoformat())
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_STALE
    assert len(verdict.stale) == 1
    # Assert on the record ID, not just the count (mutation resistance).
    assert verdict.stale[0].source_record_id == "11111111-1111-1111-1111-111111111111"
    assert verdict.stale[0].short_id == "11111111"
    assert len(verdict.approaching) == 0


def test_guilt_record_47h59m_from_boundary_is_approaching():
    now = BOUNDARY - timedelta(hours=47, minutes=59)
    record = _portal_record("22222222-2222-2222-2222-222222222222", VERIFIED_AT.isoformat())
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_APPROACHING
    assert len(verdict.approaching) == 1
    assert verdict.approaching[0].source_record_id == "22222222-2222-2222-2222-222222222222"
    assert len(verdict.stale) == 0


def test_guilt_zero_portal_records_is_no_portal_records_not_ok():
    # Non-portal records present, but none is OFFICIAL_PORTAL — the sentinel
    # must not read this as "clean" (cicatrix W84: zero traversed != clean).
    non_portal = _portal_record(
        "33333333-3333-3333-3333-333333333333", VERIFIED_AT.isoformat(),
        authority_type="PRIMARY_LAW",
    )
    verdict = vfs.classify_freshness([non_portal], BOUNDARY - timedelta(hours=49))
    assert verdict.outcome == vfs.OUTCOME_NO_PORTAL_RECORDS
    assert verdict.outcome != vfs.OUTCOME_OK
    assert verdict.portal_total == 0

    # And with a genuinely empty pack.
    verdict_empty = vfs.classify_freshness([], BOUNDARY - timedelta(hours=49))
    assert verdict_empty.outcome == vfs.OUTCOME_NO_PORTAL_RECORDS


# ---------------------------------------------------------------------------
# classify_freshness — INNOCENCE
# ---------------------------------------------------------------------------


def test_innocence_record_49h_from_boundary_is_ok():
    now = BOUNDARY - timedelta(hours=49)
    record = _portal_record("44444444-4444-4444-4444-444444444444", VERIFIED_AT.isoformat())
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_OK
    assert len(verdict.approaching) == 0
    assert len(verdict.stale) == 0


def test_innocence_future_verified_at_is_never_stale():
    now = VERIFIED_AT
    future_iso = (VERIFIED_AT + timedelta(days=3)).isoformat()
    record = _portal_record("55555555-5555-5555-5555-555555555555", future_iso)
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome != vfs.OUTCOME_STALE
    assert len(verdict.stale) == 0
    assert len(verdict.future_verified) == 1
    assert verdict.future_verified[0].source_record_id == "55555555-5555-5555-5555-555555555555"
    assert verdict.future_verified[0].reason_code == "SOURCE_VERIFIED_AT_IN_FUTURE"


def test_innocence_missing_freshness_policy_is_policy_missing_not_stale():
    """A record with no readable policy is an ANOMALY, never STALE — and never OK.

    This test kept its original name and its original point: do not misclassify an
    un-ageable record as stale. Its outcome assertion changed on 2026-08-31, from
    OK to ANOMALY, because OK was the bug — `send_alert` returns before formatting
    on OK, so the finding this test proves is detected was silently never sent.
    """
    now = BOUNDARY + timedelta(days=100)  # far past what WOULD be a boundary
    record = _portal_record(
        "66666666-6666-6666-6666-666666666666", VERIFIED_AT.isoformat(), with_policy=False
    )
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_ANOMALY
    assert verdict.outcome != vfs.OUTCOME_OK
    assert len(verdict.stale) == 0
    assert len(verdict.policy_missing) == 1
    assert verdict.policy_missing[0].source_record_id == "66666666-6666-6666-6666-666666666666"
    assert verdict.policy_missing[0].reason_code == "FRESHNESS_POLICY_NOT_DEFINED"


def test_mixed_pack_reports_only_the_stale_id_not_the_healthy_one():
    stale_now = BOUNDARY + timedelta(seconds=1)
    healthy_record = _portal_record(
        "77777777-7777-7777-7777-777777777777",
        (VERIFIED_AT + timedelta(days=6)).isoformat(),  # verified almost at `now`
        title="Healthy source",
    )
    stale_record = _portal_record(
        "88888888-8888-8888-8888-888888888888", VERIFIED_AT.isoformat(), title="Stale source"
    )
    verdict = vfs.classify_freshness([healthy_record, stale_record], stale_now)

    assert verdict.outcome == vfs.OUTCOME_STALE
    stale_ids = {f.source_record_id for f in verdict.stale}
    assert stale_ids == {"88888888-8888-8888-8888-888888888888"}
    assert verdict.portal_total == 2


# ---------------------------------------------------------------------------
# dedup_key — per-CONDITION, stable
# ---------------------------------------------------------------------------


def test_dedup_key_names_the_condition_and_pack_sequence():
    base = vfs.classify_freshness(
        [_portal_record("id", VERIFIED_AT.isoformat())], BOUNDARY + timedelta(seconds=1)
    )
    import dataclasses

    stale_verdict = dataclasses.replace(base, pack_sequence=11)
    assert vfs.dedup_key(stale_verdict) == "visa-freshness:stale:11"

    # An APPROACHING verdict with no findings is incoherent input; it must still
    # produce a stable key rather than raise inside the alert path. Widest bucket.
    approaching_verdict = dataclasses.replace(base, outcome=vfs.OUTCOME_APPROACHING, pack_sequence=11)
    assert vfs.dedup_key(approaching_verdict) == "visa-freshness:approaching:11:t48"

    anomaly_verdict = dataclasses.replace(base, outcome=vfs.OUTCOME_ANOMALY, pack_sequence=11)
    assert vfs.dedup_key(anomaly_verdict) == "visa-freshness:anomaly:11"

    cannot_verify_verdict = dataclasses.replace(base, outcome=vfs.OUTCOME_CANNOT_VERIFY, pack_sequence=None)
    assert vfs.dedup_key(cannot_verify_verdict) == "visa-freshness:cannot-verify"


# ---------------------------------------------------------------------------
# Gateway invocation — fake tg_notify.py in tmp (W107 fake-world pattern)
# ---------------------------------------------------------------------------

_FAKE_GATEWAY_RECORDING = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

args = sys.argv[1:]
Path(sys.argv[0]).with_name("calls.jsonl").open("a").write(json.dumps(args) + "\\n")
print("tg_notify: sent", file=sys.stderr)
sys.exit(0)
"""

_FAKE_GATEWAY_FAILING = """#!/usr/bin/env python3
import sys
print("boom: gateway internal error", file=sys.stderr)
sys.exit(1)
"""


def _write_fake_gateway(tmp_path: Path, body: str) -> Path:
    fake = tmp_path / "fake_tg_notify.py"
    fake.write_text(body)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def test_send_alert_invokes_gateway_with_correct_tier_source_dedup_key(tmp_path):
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)

    stale_now = BOUNDARY + timedelta(seconds=1)
    verdict = vfs.classify_freshness(
        [_portal_record("stale-id", VERIFIED_AT.isoformat())], stale_now
    )
    import dataclasses

    verdict = dataclasses.replace(verdict, pack_sequence=42, pack_version="2026.8.42")

    result = vfs.send_alert(verdict, gateway_path=fake_gateway)
    assert result == "sent"

    calls_file = tmp_path / "calls.jsonl"
    assert calls_file.exists()
    call_args = json.loads(calls_file.read_text().strip().splitlines()[-1])

    assert "--tier" in call_args
    assert call_args[call_args.index("--tier") + 1] == "p0"
    assert "--source" in call_args
    assert call_args[call_args.index("--source") + 1] == "visa-freshness-sentinel"
    assert "--dedup-key" in call_args
    assert call_args[call_args.index("--dedup-key") + 1] == "visa-freshness:stale:42"


def test_send_alert_approaching_uses_p0_tier_and_approaching_dedup_key(tmp_path):
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)

    approaching_now = BOUNDARY - timedelta(hours=1)
    verdict = vfs.classify_freshness(
        [_portal_record("approaching-id", VERIFIED_AT.isoformat())], approaching_now
    )
    import dataclasses

    verdict = dataclasses.replace(verdict, pack_sequence=7)

    vfs.send_alert(verdict, gateway_path=fake_gateway)
    call_args = json.loads((tmp_path / "calls.jsonl").read_text().strip().splitlines()[-1])
    assert call_args[call_args.index("--tier") + 1] == "p0"
    # 1h to the boundary → the tightest bucket of a 48h window.
    assert call_args[call_args.index("--dedup-key") + 1] == "visa-freshness:approaching:7:t6"


def test_send_alert_cannot_verify_uses_digest_tier_and_stable_key(tmp_path):
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)

    verdict = vfs.Verdict(
        outcome=vfs.OUTCOME_CANNOT_VERIFY,
        now=datetime.now(timezone.utc),
        warn_seconds=vfs.DEFAULT_WARN_SECONDS,
        reason="DB: unreachable; repository fallback: no packs found",
    )
    vfs.send_alert(verdict, gateway_path=fake_gateway)
    call_args = json.loads((tmp_path / "calls.jsonl").read_text().strip().splitlines()[-1])
    assert call_args[call_args.index("--tier") + 1] == "digest"
    assert call_args[call_args.index("--dedup-key") + 1] == "visa-freshness:cannot-verify"


def test_send_alert_ok_never_calls_the_gateway(tmp_path):
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)
    ok_now = BOUNDARY - timedelta(hours=49)
    verdict = vfs.classify_freshness(
        [_portal_record("ok-id", VERIFIED_AT.isoformat())], ok_now
    )
    result = vfs.send_alert(verdict, gateway_path=fake_gateway)
    assert result is None
    assert not (tmp_path / "calls.jsonl").exists()


def test_send_alert_gateway_failure_does_not_crash(tmp_path):
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_FAILING)

    stale_now = BOUNDARY + timedelta(seconds=1)
    verdict = vfs.classify_freshness(
        [_portal_record("stale-id", VERIFIED_AT.isoformat())], stale_now
    )
    # Must not raise, and must report "no verdict" rather than fabricate one.
    result = vfs.send_alert(verdict, gateway_path=fake_gateway)
    assert result is None


def test_send_alert_missing_gateway_file_does_not_crash(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    stale_now = BOUNDARY + timedelta(seconds=1)
    verdict = vfs.classify_freshness(
        [_portal_record("stale-id", VERIFIED_AT.isoformat())], stale_now
    )
    result = vfs.send_alert(verdict, gateway_path=missing)
    assert result is None


# ---------------------------------------------------------------------------
# build_verdict — CANNOT_VERIFY when neither DB nor repository answers
# ---------------------------------------------------------------------------


def test_build_verdict_cannot_verify_when_both_sources_fail(monkeypatch):
    monkeypatch.setattr(vfs, "_fetch_active_pack_from_db", lambda: (None, "db is down"))
    monkeypatch.setattr(
        vfs, "_fetch_active_pack_from_repository", lambda: (None, "no packs on disk")
    )
    verdict = vfs.build_verdict(datetime.now(timezone.utc))
    assert verdict.outcome == vfs.OUTCOME_CANNOT_VERIFY
    assert "db is down" in verdict.reason
    assert "no packs on disk" in verdict.reason


def test_build_verdict_labels_repository_fallback_as_a_proxy(monkeypatch):
    monkeypatch.setattr(vfs, "_fetch_active_pack_from_db", lambda: (None, "db is down"))
    fallback_payload = {
        "sequence": 3,
        "version": "2026.1.0",
        "source_records": [_portal_record("proxy-id", VERIFIED_AT.isoformat())],
    }
    monkeypatch.setattr(
        vfs, "_fetch_active_pack_from_repository", lambda: (fallback_payload, None)
    )
    verdict = vfs.build_verdict(BOUNDARY - timedelta(hours=49))
    assert verdict.pack_source == "repository-fallback"
    assert "proxy" in verdict.reason
    assert "not proven active" in verdict.reason


# ---------------------------------------------------------------------------
# lint compliance — this file must never mention the Telegram API domain.
# ---------------------------------------------------------------------------


def test_no_direct_telegram_api_string_in_sentinel_source():
    source_text = (SCRIPTS / "visa_freshness_sentinel.py").read_text()
    assert "api" + ".telegram.org" not in source_text


# ---------------------------------------------------------------------------
# 2026-08-31 — the two repairs. Both were found by cross-family adversarial
# review of a design document, then verified against origin/main before being
# accepted; neither was taken on the reviewer's word.
#
# REPAIR 1 (the serious one): an un-ageable portal record resolved to OK, and
#   `send_alert` returns before formatting on OK — so a pack that lost its
#   freshness_policy on every portal record reported OK and sent NOTHING, while
#   the engine treated those same records as UNKNOWN.
# REPAIR 2: the gateway's mute ladder (6/24/72/168h) can outlast the 48h warning
#   window, so an APPROACHING warning could be muted straight through its own
#   deadline. Urgency now lives in the dedup key.
# ---------------------------------------------------------------------------


def test_guilt_missing_policy_alone_is_anomaly_not_ok():
    """The exact shape that reported OK and sent nothing before 2026-08-31."""
    now = VERIFIED_AT + timedelta(hours=1)  # nothing is stale or approaching
    record = _portal_record("aaaa1111-0000-0000-0000-000000000001", VERIFIED_AT.isoformat(), with_policy=False)
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_ANOMALY
    assert len(verdict.stale) == 0 and len(verdict.approaching) == 0


def test_guilt_malformed_max_age_alone_is_anomaly_not_ok():
    now = VERIFIED_AT + timedelta(hours=1)
    record = _portal_record("aaaa1111-0000-0000-0000-000000000002", VERIFIED_AT.isoformat())
    record["freshness_policy"]["max_age_seconds"] = "seven days"
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_ANOMALY
    assert verdict.policy_missing[0].reason_code == "FRESHNESS_POLICY_MALFORMED"


def test_guilt_future_verified_at_alone_is_anomaly_not_ok():
    now = VERIFIED_AT
    record = _portal_record(
        "aaaa1111-0000-0000-0000-000000000003", (VERIFIED_AT + timedelta(days=3)).isoformat()
    )
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_ANOMALY


def test_guilt_every_portal_record_loses_its_policy_still_alerts(tmp_path):
    """The catastrophic shape, proven end-to-end through the gateway.

    Eighteen portal records, none of them ageable — the state a bad fold could
    produce. Before the repair this reached the gateway zero times.
    """
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)
    records = [
        _portal_record(f"bbbb2222-0000-0000-0000-{i:012d}", VERIFIED_AT.isoformat(), with_policy=False)
        for i in range(18)
    ]
    import dataclasses

    verdict = vfs.classify_freshness(records, VERIFIED_AT + timedelta(hours=1))
    verdict = dataclasses.replace(verdict, pack_sequence=18)

    vfs.send_alert(verdict, gateway_path=fake_gateway)

    calls = (tmp_path / "calls.jsonl").read_text().strip().splitlines()
    assert len(calls) == 1, "the anomaly must reach the gateway"
    call_args = json.loads(calls[-1])
    assert call_args[call_args.index("--tier") + 1] == "p0"
    assert call_args[call_args.index("--dedup-key") + 1] == "visa-freshness:anomaly:18"
    assert "ANOMALY" in call_args[-1] and "18" in call_args[-1]


def test_innocence_a_wholly_healthy_pack_is_still_ok_and_sends_nothing(tmp_path):
    """The repair must not turn a clean pack into an alert."""
    fake_gateway = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_RECORDING)
    records = [
        _portal_record(f"cccc3333-0000-0000-0000-{i:012d}", VERIFIED_AT.isoformat())
        for i in range(18)
    ]
    verdict = vfs.classify_freshness(records, VERIFIED_AT + timedelta(hours=1))

    assert verdict.outcome == vfs.OUTCOME_OK
    assert vfs.send_alert(verdict, gateway_path=fake_gateway) is None
    assert not (tmp_path / "calls.jsonl").exists()


def test_stale_outranks_anomaly_when_both_are_true():
    """A live deadline is the more urgent fact; the anomaly still rides along."""
    stale = _portal_record("dddd4444-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())
    broken = _portal_record(
        "dddd4444-0000-0000-0000-000000000002", VERIFIED_AT.isoformat(), with_policy=False
    )
    verdict = vfs.classify_freshness([stale, broken], BOUNDARY + timedelta(seconds=1))

    assert verdict.outcome == vfs.OUTCOME_STALE
    assert len(verdict.policy_missing) == 1
    assert "missing/unreadable" in vfs.format_alert_text(verdict)


# --- REPAIR 2: urgency buckets -------------------------------------------


def test_urgency_buckets_are_derived_from_the_warn_window_not_hardcoded():
    assert vfs.urgency_buckets(48 * 3600) == (48, 24, 12, 6)
    # The whole point: a wider window must not collapse its top span into one key.
    assert vfs.urgency_buckets(72 * 3600) == (72, 36, 18, 9)
    assert vfs.urgency_buckets(8 * 3600) == (8, 4, 2, 1)
    # Degenerate windows fold levels together rather than emitting duplicates.
    assert vfs.urgency_buckets(3600) == (1,)


def test_guilt_each_bucket_crossing_mints_a_new_key_even_at_the_longest_mute():
    """47h → 23h → 11h → 5h must be four DISTINCT keys.

    With a single key the gateway's ladder reaches a 72h mute at streak 3, which
    is longer than the entire 48h warning window: the last warnings before the
    boundary would be swallowed.
    """
    import dataclasses

    base = vfs.classify_freshness(
        [_portal_record("eeee5555-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())],
        BOUNDARY - timedelta(hours=47),
    )
    keys = []
    for hours_left in (47, 23, 11, 5):
        v = vfs.classify_freshness(
            [_portal_record("eeee5555-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())],
            BOUNDARY - timedelta(hours=hours_left),
        )
        v = dataclasses.replace(v, pack_sequence=17)
        assert v.outcome == vfs.OUTCOME_APPROACHING, hours_left
        keys.append(vfs.dedup_key(v))

    assert keys == [
        "visa-freshness:approaching:17:t48",
        "visa-freshness:approaching:17:t24",
        "visa-freshness:approaching:17:t12",
        "visa-freshness:approaching:17:t6",
    ]
    assert len(set(keys)) == 4
    assert base.outcome == vfs.OUTCOME_APPROACHING


def test_innocence_two_runs_inside_one_bucket_share_a_key():
    """Within a bucket the ladder must still suppress — this is not a spam hose."""
    import dataclasses

    keys = set()
    for hours_left in (23.9, 20.0, 13.0, 12.1):  # all inside the t24 bucket
        v = vfs.classify_freshness(
            [_portal_record("ffff6666-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())],
            BOUNDARY - timedelta(hours=hours_left),
        )
        keys.add(vfs.dedup_key(dataclasses.replace(v, pack_sequence=17)))

    assert keys == {"visa-freshness:approaching:17:t24"}


def test_stale_and_anomaly_keys_carry_no_urgency_suffix():
    """Only APPROACHING has a deadline running; the others stay per-condition."""
    import dataclasses

    stale = vfs.classify_freshness(
        [_portal_record("id", VERIFIED_AT.isoformat())], BOUNDARY + timedelta(seconds=1)
    )
    assert vfs.dedup_key(dataclasses.replace(stale, pack_sequence=17)) == "visa-freshness:stale:17"

    anomaly = vfs.classify_freshness(
        [_portal_record("id", VERIFIED_AT.isoformat(), with_policy=False)],
        VERIFIED_AT + timedelta(hours=1),
    )
    assert vfs.dedup_key(dataclasses.replace(anomaly, pack_sequence=17)) == "visa-freshness:anomaly:17"


# --- REPAIR 3+4: the two defects the refuter on this diff found ----------
#
# Both are the SAME shape as the bug being fixed, one layer further out: the
# ANOMALY is detected correctly and then thrown away by whatever reports it.


def test_guilt_anomaly_does_not_exit_zero():
    """Exit 0 means `heartbeat "ok"` on the sidecar — the surface people read.

    The wrapper writes `heartbeat "ok" "run done"` on ANY zero exit, so an
    ANOMALY returning 0 would be invisible exactly where it matters.
    """
    import dataclasses

    anomaly = vfs.classify_freshness(
        [_portal_record("id", VERIFIED_AT.isoformat(), with_policy=False)],
        VERIFIED_AT + timedelta(hours=1),
    )
    assert anomaly.outcome == vfs.OUTCOME_ANOMALY
    # The exit map lives in main(); assert the contract it implements.
    assert vfs.OUTCOME_ANOMALY not in (vfs.OUTCOME_OK,)
    src = (SCRIPTS / "visa_freshness_sentinel.py").read_text()
    assert "if verdict.outcome == OUTCOME_ANOMALY:" in src
    assert "return 3" in src


def test_guilt_an_anomaly_appearing_during_a_stale_pack_mints_a_new_key():
    """Otherwise a muted STALE key swallows the news that the pack broke.

    STALE outranks ANOMALY, so the anomaly rides along in the alert body and
    gets no outcome of its own. If it also got no KEY of its own, the ladder
    (already climbing on a repeating STALE) would suppress the one message
    carrying the new fact.
    """
    import dataclasses

    stale_only = vfs.classify_freshness(
        [_portal_record("aaaa0000-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())],
        BOUNDARY + timedelta(seconds=1),
    )
    stale_plus_anomaly = vfs.classify_freshness(
        [
            _portal_record("aaaa0000-0000-0000-0000-000000000001", VERIFIED_AT.isoformat()),
            _portal_record(
                "aaaa0000-0000-0000-0000-000000000002",
                VERIFIED_AT.isoformat(),
                with_policy=False,
            ),
        ],
        BOUNDARY + timedelta(seconds=1),
    )
    assert stale_only.outcome == vfs.OUTCOME_STALE
    assert stale_plus_anomaly.outcome == vfs.OUTCOME_STALE  # ranking unchanged

    k1 = vfs.dedup_key(dataclasses.replace(stale_only, pack_sequence=17))
    k2 = vfs.dedup_key(dataclasses.replace(stale_plus_anomaly, pack_sequence=17))
    assert k1 == "visa-freshness:stale:17"
    assert k2 == "visa-freshness:stale:17:anom"
    assert k1 != k2

    # ...and the body actually carries the new fact, so the fresh key is worth
    # spending. (A new key delivering the identical text would be pure noise.)
    assert "missing/unreadable" in vfs.format_alert_text(stale_plus_anomaly)
    assert "missing/unreadable" not in vfs.format_alert_text(stale_only)


def test_guilt_the_same_marker_applies_while_approaching():
    import dataclasses

    approaching_plus_anomaly = vfs.classify_freshness(
        [
            _portal_record("bbbb0000-0000-0000-0000-000000000001", VERIFIED_AT.isoformat()),
            _portal_record(
                "bbbb0000-0000-0000-0000-000000000002",
                # Genuinely ahead of THIS run's clock (BOUNDARY - 23h), not
                # merely ahead of VERIFIED_AT — the anomaly is measured against now.
                (BOUNDARY + timedelta(days=1)).isoformat(),
            ),
        ],
        BOUNDARY - timedelta(hours=23),
    )
    assert approaching_plus_anomaly.outcome == vfs.OUTCOME_APPROACHING
    key = vfs.dedup_key(dataclasses.replace(approaching_plus_anomaly, pack_sequence=17))
    assert key == "visa-freshness:approaching:17:t24:anom"


def test_innocence_a_clean_stale_pack_keeps_its_unsuffixed_key():
    """The marker must not appear when there is no anomaly — otherwise every
    stale alert mints a second key and the ladder never suppresses anything."""
    import dataclasses

    stale = vfs.classify_freshness(
        [_portal_record("cccc0000-0000-0000-0000-000000000001", VERIFIED_AT.isoformat())],
        BOUNDARY + timedelta(seconds=1),
    )
    assert (
        vfs.dedup_key(dataclasses.replace(stale, pack_sequence=17))
        == "visa-freshness:stale:17"
    )
