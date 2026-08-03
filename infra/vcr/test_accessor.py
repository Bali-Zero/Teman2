"""Tests for infra/vcr/accessor.py — the ONE enforced entry point (R1/R2/R6/§5.4).

No real subprocess/network/filesystem-outside-tmp_path anywhere: run_probe_fn,
machine_label_fn and check_verifier_fn are all injected. Guilt AND innocence
throughout (scar #3), with one test specifically pinned to the dedup bug found
during build (a cache-only re-read of an unchanged report must not fake a
second hysteresis-confirming observation).
"""

from __future__ import annotations

import json

import pytest

from infra.vcr import accessor as acc
from infra.vcr import store as store_mod
from infra.vcr.records import CURRENT, EXPIRED, HEALTHY, MISSING, PRESENT, STALE, TRUE, FALSE
from infra.vcr.registry import ExpectedClaim


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VCR_STORE_HOME", str(tmp_path))
    report_path = tmp_path / "arsenal_last.json"
    prober_path = tmp_path / "fake_arsenal_probe.py"
    prober_path.write_text("# fake prober\n")
    reg = [
        ExpectedClaim(seat="claude", host="m5", auth_context="interactive",
                       ttl_s=3600, latency_budget_ms=15000, certified_hash=None),
    ]
    return {
        "tmp_path": tmp_path, "report_path": report_path, "prober_path": prober_path,
        "registry": reg,
    }


def _write_report(path, seat="claude", status="LIVE", ts="2026-08-03T12:00:00Z", evidence="PONG"):
    path.write_text(json.dumps({
        "ts": ts,
        "seats": [{"seat": seat, "status": status, "evidence": evidence, "latency_ms": 100}],
    }))


def _healthy_verifier(_prober_path, _certified_hash):
    return HEALTHY, "ok"


def _m5(_prober_path):
    return "m5"


def test_unregistered_pair_raises(env):
    with pytest.raises(acc.UnregisteredClaimError):
        acc.get_state(
            "claude", "pro", "interactive", allow_probe=False,
            registry=env["registry"], report_path=env["report_path"],
            prober_path=env["prober_path"], machine_label_fn=_m5,
            check_verifier_fn=_healthy_verifier,
        )


def test_no_report_yet_is_coverage_missing(env):
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier,
    )
    assert st.coverage_state == MISSING
    assert st.truth_state != TRUE


def test_fresh_live_report_is_present_and_true(env):
    _write_report(env["report_path"])
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    assert st.coverage_state == PRESENT
    assert st.truth_state == TRUE
    assert st.freshness_state == CURRENT
    assert st.verifier_state == HEALTHY


def test_remote_host_is_unverified_and_missing(env):
    """A registered pair whose host isn't THIS machine must never silently
    resolve — it's an explicit, documented v1 limitation, not a crash and not
    a false healthy."""
    reg = env["registry"] + [
        ExpectedClaim(seat="claude", host="mini", auth_context="cron-token-1",
                       ttl_s=1200, latency_budget_ms=15000, certified_hash=None)
    ]
    st = acc.get_state(
        "claude", "mini", "cron-token-1", allow_probe=True,
        registry=reg, report_path=env["report_path"], prober_path=env["prober_path"],
        machine_label_fn=_m5,  # local machine is m5, query is for mini
        check_verifier_fn=_healthy_verifier,
    )
    assert st.coverage_state == MISSING
    assert st.freshness_state == EXPIRED
    assert "!= this machine" in st.reason


def test_cache_only_mode_never_triggers_a_probe(env):
    probe_calls = []

    def _spy_probe(*args, **kwargs):
        probe_calls.append(args)
        return 0

    _write_report(env["report_path"])
    acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, run_probe_fn=_spy_probe,
    )
    assert probe_calls == [], "run_probe_fn must not be called in cache-only (allow_probe=False) mode"


def test_stale_report_with_allow_probe_triggers_probe(env):
    """Innocence's mirror of the cache-only test: with allow_probe=True and a
    genuinely stale report, run_probe_fn MUST be invoked."""
    _write_report(env["report_path"], ts="2020-01-01T00:00:00Z")
    calls = []

    def _spy_probe(seat, timeout_s, prober_path):
        calls.append(seat)
        _write_report(env["report_path"], status="LIVE", ts="2026-08-03T12:05:00Z")
        return 0

    # force staleness regardless of tmp file mtime by using a far-future `now`
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=True,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, run_probe_fn=_spy_probe,
        now=2000000000.0,
    )
    assert calls == ["claude"]
    assert st.truth_state == TRUE


def test_dedup_bug_fix_repeated_cache_reads_of_unchanged_report_append_once(env):
    """GUILT case for the bug found during build: calling get_state() twice in
    cache-only mode against the SAME report ts must log exactly ONE observation,
    never two — two would fake a hysteresis-confirming pair from a single
    real probe result."""
    _write_report(env["report_path"], ts="2026-08-03T12:00:00Z")
    for _ in range(3):
        acc.get_state(
            "claude", "m5", "interactive", allow_probe=False,
            registry=env["registry"], report_path=env["report_path"],
            prober_path=env["prober_path"], machine_label_fn=_m5,
            check_verifier_fn=_healthy_verifier, now=1754222400.0,
        )
    from infra.vcr.records import ClaimContext
    obs, _ = store_mod.read_observations("claude", ClaimContext(host="m5", auth_context="interactive"))
    assert len(obs) == 1, f"expected exactly 1 observation after 3 identical cache reads, got {len(obs)}"


def test_innocence_a_genuinely_new_report_ts_does_append_again(env):
    """Innocence's mirror: when the underlying report DOES change (new ts),
    a second observation must be logged — the dedup rule must not swallow
    genuinely new information."""
    _write_report(env["report_path"], ts="2026-08-03T12:00:00Z", status="LIVE")
    acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    _write_report(env["report_path"], ts="2026-08-03T12:05:00Z", status="AUTH_DEAD")
    acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222700.0,
    )
    from infra.vcr.records import ClaimContext
    obs, _ = store_mod.read_observations("claude", ClaimContext(host="m5", auth_context="interactive"))
    assert len(obs) == 2
    assert [o.raw_status for o in obs] == ["LIVE", "AUTH_DEAD"]


def test_verifier_drifted_is_reflected_in_materialized_state(env):
    def _drifted(_prober_path, _certified_hash):
        return "DRIFTED", "hash mismatch"

    _write_report(env["report_path"])
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_drifted, now=1754222400.0,
    )
    assert st.verifier_state == "DRIFTED"
    assert st.all_healthy() is False


def test_verifier_unhealthy_short_circuits_before_touching_the_prober_again(env):
    """Codex red-team, 2026-08-03 (accessor.py:156/176): once check_verifier_fn
    says the prober is DRIFTED/FAILED, get_state() must return BEFORE calling
    machine_label_fn (imports+execs the module) or run_probe_fn (subprocess-
    execs it again) — checking a hash and then running the file anyway
    defeats the entire point of the check. Both spies raise if called."""

    def _drifted(_prober_path, _certified_hash):
        return "DRIFTED", "hash mismatch: certified=aaa… actual=bbb…"

    def _never_call_machine_label(_prober_path):
        raise AssertionError("machine_label_fn must not run after a DRIFTED verdict")

    def _never_call_probe(*_args, **_kwargs):
        raise AssertionError("run_probe_fn must not run after a DRIFTED verdict")

    _write_report(env["report_path"])
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=True,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"],
        machine_label_fn=_never_call_machine_label,
        run_probe_fn=_never_call_probe,
        check_verifier_fn=_drifted, now=1754222400.0,
    )
    assert st.verifier_state == "DRIFTED"
    assert st.coverage_state == MISSING
    assert st.all_healthy() is False


def test_verifier_healthy_still_calls_machine_label_and_probe_as_before(env):
    """Innocence mirror: a HEALTHY verifier must NOT short-circuit anything —
    machine_label_fn still runs (needed for the host-match check)."""
    calls = []

    def _spy_machine_label(_prober_path):
        calls.append("machine_label")
        return "m5"

    _write_report(env["report_path"])
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_spy_machine_label,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    assert calls == ["machine_label"]
    assert st.truth_state == TRUE


def test_sliding_window_bug_fix_confirmed_state_survives_beyond_twenty_observations(env):
    """Codex red-team, 2026-08-03 (accessor.py:193): the old code capped
    store.read_observations at limit=20 before folding into
    derive_truth_state, which treats observations[0] as the debounce
    baseline with NO prior history. A fixed window silently discarded
    whatever had been confirmed before it. Reproduces Codex's exact
    counter-example, hand-verified against derive_truth_state's algorithm:
    20 observations alternating T,F,T,F,...,T,F fold (full-history) to a
    confirmed TRUE baseline (every F is immediately followed by a
    resetting T, so pending_count never reaches 2). Adding ONE new TRUE
    observation (21st) must still report TRUE under a full-history fold —
    but a limit=20 WINDOW would drop the oldest (TRUE) observation, re-seed
    the windowed baseline from what slides into position 0 (FALSE), and
    flip the reported state to FALSE — the OPPOSITE of what the new sample
    said (this is the actual mutation-tested regression: this same test,
    run against the pre-fix code with limit=20 restored, fails asserting
    TRUE because the windowed fold reports FALSE)."""
    from infra.vcr.records import ClaimContext, ClaimObservation

    ctx = ClaimContext(host="m5", auth_context="interactive")
    pattern = [TRUE if i % 2 == 0 else FALSE for i in range(20)]  # T,F,T,F,...,T,F
    for i, val in enumerate(pattern):
        obs = ClaimObservation(
            claim_id=f"claude::{ctx.key()}", claim_type="seat_health", subject_id="claude",
            context=ctx, observed_at=f"2026-08-01T00:{i:02d}:00Z",
            raw_status=("LIVE" if val == TRUE else "AUTH_DEAD"),
            raw_evidence="seed", latency_ms=100, truth_state=val,
            truth_reason="seed", source_report_ts=f"2026-08-01T00:{i:02d}:00Z",
        )
        store_mod.append_observation(obs)

    # The 21st (brand new) observation: TRUE.
    _write_report(env["report_path"], ts="2026-08-03T12:00:00Z", status="LIVE")
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    assert st.truth_state == TRUE, (
        "full-history fold must confirm TRUE; a limit=20 window drops the "
        "oldest seeded observation and wrongly flips this to FALSE"
    )


def test_sliding_window_bug_fix_a_real_flip_still_needs_two_consecutive_observations(env):
    """Innocence mirror: with the full-history fold, a GENUINE flip still
    requires 2 consecutive disagreeing observations — the fix to stop
    windowing must not accidentally make debounce a no-op."""
    from infra.vcr.records import ClaimContext, ClaimObservation

    ctx = ClaimContext(host="m5", auth_context="interactive")
    for i in range(5):
        obs = ClaimObservation(
            claim_id=f"claude::{ctx.key()}", claim_type="seat_health", subject_id="claude",
            context=ctx, observed_at=f"2026-08-01T00:{i:02d}:00Z", raw_status="LIVE",
            raw_evidence="PONG", latency_ms=100, truth_state=TRUE,
            truth_reason="seed", source_report_ts=f"2026-08-01T00:{i:02d}:00Z",
        )
        store_mod.append_observation(obs)
    # ONE new disagreeing (FALSE) observation must NOT flip the confirmed state yet.
    _write_report(env["report_path"], ts="2026-08-03T12:00:00Z", status="AUTH_DEAD")
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    assert st.truth_state == TRUE, "a single disagreeing observation must not flip a confirmed state"


def test_freshness_derived_from_report_content_ts_not_filesystem_mtime(env):
    """Codex red-team, 2026-08-03 (accessor.py:171): freshness used to be
    computed purely from the report FILE's mtime — a copy or `touch` of an
    old report would silently promote a stale observation to CURRENT. Write
    a report with an OLD content ts but a fresh mtime (the file was just
    written by this test, so mtime IS "now") and confirm freshness reads
    the CONTENT age, not the fresh mtime."""
    _write_report(env["report_path"], ts="2020-01-01T00:00:00Z")  # old content, fresh mtime
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=env["report_path"],
        prober_path=env["prober_path"], machine_label_fn=_m5,
        check_verifier_fn=_healthy_verifier, now=1754222400.0,  # ~2025-08, long after 2020
    )
    assert st.freshness_state == EXPIRED, "content ts is ancient; mtime-only freshness would wrongly read CURRENT"


def test_dedup_key_falls_back_to_content_hash_when_report_has_no_ts(env):
    """Codex red-team, 2026-08-03 (accessor.py:190): a report lacking a `ts`
    field used to dedup-key on an empty string every time — two DIFFERENT
    raw statuses, both missing ts, were wrongly treated as "the same
    report" and the second was silently never logged."""
    path = env["report_path"]
    path.write_text(json.dumps({
        "seats": [{"seat": "claude", "status": "LIVE", "evidence": "PONG", "latency_ms": 100}],
    }))  # no top-level "ts"
    acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=path, prober_path=env["prober_path"],
        machine_label_fn=_m5, check_verifier_fn=_healthy_verifier, now=1754222400.0,
    )
    path.write_text(json.dumps({
        "seats": [{"seat": "claude", "status": "AUTH_DEAD", "evidence": "denied", "latency_ms": 50}],
    }))  # still no top-level "ts", but genuinely DIFFERENT content
    acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=env["registry"], report_path=path, prober_path=env["prober_path"],
        machine_label_fn=_m5, check_verifier_fn=_healthy_verifier, now=1754222700.0,
    )
    from infra.vcr.records import ClaimContext
    obs, _ = store_mod.read_observations("claude", ClaimContext(host="m5", auth_context="interactive"))
    assert len(obs) == 2, f"expected both distinct ts-less reports to be logged, got {len(obs)}"
    assert [o.raw_status for o in obs] == ["LIVE", "AUTH_DEAD"]


def test_dedup_lock_serializes_concurrent_appenders(env):
    """Codex red-team, 2026-08-03 (accessor.py:112, reproduced live): the
    old check-and-append was not atomic — two concurrent cache-only callers
    could both read the same "last observation", both decide to append, and
    both append a duplicate row, faking a hysteresis-confirming pair from
    ONE real probe event. The flock around the critical section must
    serialize this even under real thread concurrency."""
    import threading

    _write_report(env["report_path"], ts="2026-08-03T12:00:00Z")
    errors = []

    def _call():
        try:
            acc.get_state(
                "claude", "m5", "interactive", allow_probe=False,
                registry=env["registry"], report_path=env["report_path"],
                prober_path=env["prober_path"], machine_label_fn=_m5,
                check_verifier_fn=_healthy_verifier, now=1754222400.0,
            )
        except Exception as e:  # pragma: no cover — surfaced via `errors`, not swallowed
            errors.append(e)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"unexpected exceptions under concurrency: {errors}"
    from infra.vcr.records import ClaimContext
    obs, _ = store_mod.read_observations("claude", ClaimContext(host="m5", auth_context="interactive"))
    assert len(obs) == 1, f"expected exactly 1 observation after 8 racing cache reads, got {len(obs)}"


def test_real_certified_hash_mismatch_flows_end_to_end_through_get_state(env):
    """GLM + Codex red-team, 2026-08-03: every OTHER accessor test uses
    check_verifier_fn as an injected mock (or certified_hash=None in the
    fixture registry) — meaning the REAL check_verifier() hash-comparison
    branch was never exercised end-to-end through get_state(). This uses
    the REAL check_verifier function (no mock) with a genuinely wrong
    certified_hash, proving DRIFTED actually flows through when nothing is
    injected to fake it."""
    from infra.vcr.registry import ExpectedClaim
    from infra.vcr.verifier import check_verifier

    wrong_hash = "0" * 64
    reg = [
        ExpectedClaim(seat="claude", host="m5", auth_context="interactive",
                       ttl_s=3600, latency_budget_ms=15000, certified_hash=wrong_hash),
    ]
    _write_report(env["report_path"])
    st = acc.get_state(
        "claude", "m5", "interactive", allow_probe=False,
        registry=reg, report_path=env["report_path"], prober_path=env["prober_path"],
        check_verifier_fn=check_verifier,  # the REAL function, not a mock
        now=1754222400.0,
    )
    assert st.verifier_state == "DRIFTED"
    assert "mismatch" in st.reason
    assert st.all_healthy() is False


# ---------------------------------------------------------------------------
# derive_freshness() — pure function, tested directly (guilt + innocence)
# ---------------------------------------------------------------------------

def test_freshness_current_within_ttl():
    assert acc.derive_freshness(100, ttl_s=3600) == CURRENT


def test_freshness_stale_beyond_ttl_within_3x():
    assert acc.derive_freshness(3700, ttl_s=3600) == STALE


def test_freshness_expired_beyond_3x_ttl():
    assert acc.derive_freshness(20000, ttl_s=3600) == EXPIRED


def test_freshness_none_age_is_expired_not_current():
    """Guilt: a missing report (age=None) must never be read as CURRENT."""
    assert acc.derive_freshness(None, ttl_s=3600) == EXPIRED
