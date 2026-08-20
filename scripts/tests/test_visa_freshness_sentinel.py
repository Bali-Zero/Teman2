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
    now = BOUNDARY + timedelta(days=100)  # far past what WOULD be a boundary
    record = _portal_record(
        "66666666-6666-6666-6666-666666666666", VERIFIED_AT.isoformat(), with_policy=False
    )
    verdict = vfs.classify_freshness([record], now)

    assert verdict.outcome == vfs.OUTCOME_OK
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

    approaching_verdict = dataclasses.replace(base, outcome=vfs.OUTCOME_APPROACHING, pack_sequence=11)
    assert vfs.dedup_key(approaching_verdict) == "visa-freshness:approaching:11"

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
    assert call_args[call_args.index("--dedup-key") + 1] == "visa-freshness:approaching:7"


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
