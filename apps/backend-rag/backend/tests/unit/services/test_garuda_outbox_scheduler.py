"""Tests for the GARUDA outbox scheduler — the loop that finally calls
`drain_once`.

The property that matters most here is not the cadence but the ARMING: for
months every part of the GARUDA outbox existed and nothing invoked it, which
looked exactly like a working system. So the first two tests below assert that
the lifespan spawns the task when the switch says the literal string "true" and
does NOT spawn it otherwise — those are the ones that go red if this wiring is
ever quietly removed again.

The `while True:` loop is bounded the way `test_wa_outbox_scheduler.py` bounds
its own: a scripted sequence of drain results that raises `CancelledError` once
exhausted, plus a fake `sleep` that records the requested duration instead of
spending it. No wall-clock cost, no hang risk.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.app import main_api
from backend.services.garuda_orders.outbox_consumer import DrainStats

pytestmark = pytest.mark.asyncio


class _FakePool:
    """Enough of an asyncpg pool for the loop: `acquire()` as async context."""

    def __init__(self) -> None:
        self.acquired = 0

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                pool.acquired += 1
                return object()

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _app(pool=None) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(db_pool=pool or _FakePool()))


async def _drive(monkeypatch, results, *, poll="5") -> list[float]:
    """Run the loop over a scripted list of DrainStats, return the sleeps."""

    monkeypatch.setenv("GARUDA_OUTBOX_POLL_SECONDS", poll)
    slept: list[float] = []
    script = list(results)

    async def fake_drain(conn, handlers, **kw):
        if not script:
            raise asyncio.CancelledError
        return script.pop(0)

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        "backend.services.garuda_orders.outbox_consumer.drain_once", fake_drain
    )
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await main_api._run_garuda_outbox_scheduler(_app())
    return slept


# --------------------------------------------------------------------------
# arming — the reason this file exists
# --------------------------------------------------------------------------


def test_the_scheduler_reuses_the_consumers_own_kill_switch() -> None:
    """RED if someone introduces a second, laxer switch. `is_consumer_enabled`
    accepts the literal "true" and nothing else, and that fail-closed default is
    what makes the queue deployable-but-dark."""

    from backend.services.garuda_orders.outbox_consumer import (
        KILL_SWITCH_ENV,
        is_consumer_enabled,
    )

    assert KILL_SWITCH_ENV == "GARUDA_OUTBOX_CONSUMER_ENABLED"
    assert is_consumer_enabled({KILL_SWITCH_ENV: "true"}) is True
    for lookalike in ("1", "yes", "TRUE", "True", "on", "", "false"):
        assert is_consumer_enabled({KILL_SWITCH_ENV: lookalike}) is False, lookalike
    assert is_consumer_enabled({}) is False


async def test_the_lifespan_spawns_the_drain_when_the_switch_is_true(monkeypatch) -> None:
    """The arming test. Before this wiring existed, every GARUDA outbox row sat
    undispatched forever while every component test passed."""

    monkeypatch.setenv("GARUDA_OUTBOX_CONSUMER_ENABLED", "true")
    spawned: list[object] = []

    async def fake_loop(app):
        spawned.append(app)
        await asyncio.sleep(3600)

    monkeypatch.setattr(main_api, "_run_garuda_outbox_scheduler", fake_loop)
    task = await _spawn_via_lifespan(monkeypatch)
    await asyncio.sleep(0)  # let the freshly created task reach its first line
    assert spawned, "the drain loop was never started"
    assert task is not None
    task.cancel()


async def test_the_lifespan_leaves_the_drain_disarmed_by_default(monkeypatch) -> None:
    """No env var set at all — the dark-launch default. RED if the switch ever
    becomes opt-out."""

    monkeypatch.delenv("GARUDA_OUTBOX_CONSUMER_ENABLED", raising=False)
    started = []
    monkeypatch.setattr(
        main_api, "_run_garuda_outbox_scheduler", lambda app: started.append(app)
    )
    task = await _spawn_via_lifespan(monkeypatch)
    assert started == []
    assert task is None


async def _spawn_via_lifespan(monkeypatch):
    """Run only the spawn decision, not the whole lifespan.

    Driving `lifespan_light` end to end would drag in service initialisation
    this test has no opinion about. The decision under test is small and
    self-contained, so it is reproduced here against the SAME predicate and the
    SAME attribute name the lifespan uses — `test_the_scheduler_reuses_the_
    consumers_own_kill_switch` above is what keeps the predicate honest.
    """

    from backend.services.garuda_orders.outbox_consumer import is_consumer_enabled

    app = _app()
    if not is_consumer_enabled():
        app.state._garuda_outbox_scheduler_task = None
    else:
        app.state._garuda_outbox_scheduler_task = asyncio.create_task(
            main_api._run_garuda_outbox_scheduler(app)
        )
    return app.state._garuda_outbox_scheduler_task


# --------------------------------------------------------------------------
# cadence
# --------------------------------------------------------------------------


async def test_it_drains_fast_while_dispatching_and_backs_off_when_idle(monkeypatch) -> None:
    slept = await _drive(
        monkeypatch,
        [DrainStats(claimed=1, dispatched=1), DrainStats(claimed=0)],
        poll="7",
    )
    assert slept == [0.1, 7.0]


async def test_a_pass_that_only_finds_unroutable_work_backs_off(monkeypatch) -> None:
    """RED-if-wrong, and the reason the cadence keys on `dispatched` rather than
    `claimed`: a queue holding only unroutable or failing rows would otherwise
    be spun on at 0.1s, burning their whole attempt budget in seconds. That is
    precisely what `exclude_ids` prevents WITHIN one pass; keying on `claimed`
    would reintroduce it ACROSS passes."""

    slept = await _drive(
        monkeypatch,
        [
            DrainStats(claimed=1, unroutable=1, unroutable_types=frozenset({"refund_email"})),
            DrainStats(claimed=1, failed=1),
        ],
        poll="4",
    )
    assert slept == [4.0, 4.0]


async def test_a_failing_tick_does_not_kill_the_loop(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_OUTBOX_POLL_SECONDS", "2")
    slept: list[float] = []
    calls = {"n": 0}

    async def fake_drain(conn, handlers, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient database hiccup")
        raise asyncio.CancelledError

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        "backend.services.garuda_orders.outbox_consumer.drain_once", fake_drain
    )
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await main_api._run_garuda_outbox_scheduler(_app())

    assert calls["n"] == 2, "the loop stopped after the first failure"
    assert slept == [2.0]


async def test_a_bad_poll_interval_does_not_crash_startup(monkeypatch) -> None:
    for bad in ("banana", "0", "-3"):
        monkeypatch.setenv("GARUDA_OUTBOX_POLL_SECONDS", bad)
        assert main_api._garuda_outbox_poll_seconds() == 5.0, bad
    monkeypatch.setenv("GARUDA_OUTBOX_POLL_SECONDS", "12.5")
    assert main_api._garuda_outbox_poll_seconds() == 12.5


async def test_the_http_client_is_closed_on_cancellation(monkeypatch) -> None:
    """The sender takes an INJECTED client so it is not rebuilt per call
    (Golden Rule #10), which makes closing it this loop's job. RED if the
    client is built and never closed: a cancelled scheduler would leak the
    connection pool on every restart.

    THIS ASSERTS ON `is_closed`, NOT ON A COUNT OF `aclose()` CALLS, and the
    difference is not cosmetic. The first version of this test counted calls to
    `httpx.AsyncClient.aclose`, which is exactly right for a `try/finally` that
    calls it by name and exactly WRONG for `async with`: httpx's `__aexit__`
    sets the state to CLOSED and closes the transport and mounts DIRECTLY
    (`_client.py`, verified on the pinned version in this venv), never routing
    through `self.aclose()`. So the old probe read 0 against an implementation
    that closes the client perfectly — a red that accused correct code. Chasing
    it would have argued for tagging the line `# golden-rule-10-exempt` to keep
    a shape the guard already sanctions. The state is the property we actually
    care about; the method name was a proxy for it.
    """

    import httpx

    built: list[httpx.AsyncClient] = []
    real_cls = httpx.AsyncClient

    class RecordingAsyncClient(real_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            built.append(self)

    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
    await _drive(monkeypatch, [])
    assert len(built) == 1, "the loop must build exactly one shared client"
    assert built[0].is_closed is True


def test_the_lifespan_ITSELF_still_spawns_the_drain() -> None:
    """The test that actually guards the arming, and the reason the two above
    are not enough on their own.

    `_spawn_via_lifespan` reproduces the lifespan's decision rather than running
    it, so it would keep passing if someone deleted the spawn from
    `lifespan_light` entirely — which is precisely the failure this whole PR
    exists to undo. This one reads the real source of `lifespan_light` and
    insists the wiring is present AND gated. It is a structural assertion
    because the alternative, driving the full lifespan, drags in service
    initialisation that has nothing to do with the property.

    RED if: the spawn is removed, the guard is removed, the task handle stops
    being stored under the name shutdown looks for, or the shutdown cancel is
    dropped.
    """

    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(main_api.lifespan_light))
    assert "_run_garuda_outbox_scheduler" in src, "lifespan no longer spawns the drain"
    assert "is_consumer_enabled" in src, "the spawn is no longer gated by the kill switch"
    assert "_garuda_outbox_scheduler_task" in src, "the task handle is not stored"
    # Named explicitly, not counted. The first draft asserted
    # `src.count("_garuda_outbox_scheduler_task") >= 2` and was worthless: the
    # spawn block alone already mentions the attribute three times, so deleting
    # the entire shutdown path left the test green. Mutation testing is what
    # exposed it — a guard that cannot fail is not a guard.
    assert "garuda_task.cancel()" in src, (
        "the drain task is stored but never cancelled — shutdown would close the "
        "pool out from under a running drain and leak its httpx client"
    )
    assert "await garuda_task" in src, (
        "the drain task is cancelled but not awaited, so its `finally` never runs"
    )


# --------------------------------------------------------------------------
# OP-04 checkout-expiry sweep — the SECOND job that had no caller
# --------------------------------------------------------------------------


class _LockConn:
    """A conn that answers the advisory-lock round trip and records it."""

    def __init__(self, *, grant: bool = True) -> None:
        self.grant = grant
        self.calls: list[str] = []

    async def fetchval(self, sql, *args):
        if "pg_try_advisory_lock" in sql:
            self.calls.append("lock")
            return self.grant
        if "pg_advisory_unlock" in sql:
            self.calls.append("unlock")
            return True
        raise AssertionError(f"unexpected query in the sweep block: {sql!r}")


class _LockPool:
    def __init__(self, conn: _LockConn) -> None:
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


async def _drive_one_tick(monkeypatch, *, repository, conn, sweep):
    """One drain pass with the periodic block armed, then CancelledError.

    `next_alarm_check` starts at 0.0, so the FIRST iteration always enters the
    periodic block — one scripted pass is enough to exercise the sweep.
    """
    monkeypatch.setenv("GARUDA_OUTBOX_POLL_SECONDS", "5")
    script = [DrainStats(claimed=0)]

    async def fake_drain(c, handlers, **kw):
        if not script:
            raise asyncio.CancelledError
        return script.pop(0)

    async def fake_count_undrained(c, **kw):
        # Not under test here; keep the alarm half silent so a failure in the
        # sweep half cannot be mistaken for the alarm's.
        return {"exhausted": 0}

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(
        "backend.services.garuda_orders.outbox_consumer.drain_once", fake_drain
    )
    monkeypatch.setattr(
        "backend.services.garuda_orders.outbox_consumer.count_undrained",
        fake_count_undrained,
    )
    monkeypatch.setattr(
        "backend.services.garuda_orders.reconciliation.reconcile_expired_checkouts", sweep
    )
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)

    app = SimpleNamespace(state=SimpleNamespace(db_pool=_LockPool(conn)))
    if repository is not None:
        app.state.garuda_order_repository = repository
    with pytest.raises(asyncio.CancelledError):
        await main_api._run_garuda_outbox_scheduler(app)


async def test_the_periodic_tick_calls_the_op04_sweep_once_the_order_lane_is_wired(
    monkeypatch,
) -> None:
    """THE arming assertion. `reconcile_expired_checkouts` shipped with exactly
    one file naming it — its own definition — while its docstring claimed an
    "intended cadence". This is that cadence. Red if the call is ever removed.
    """
    called: list[tuple] = []

    async def sweep(pool, repository, **kw):
        called.append((pool, repository))
        return SimpleNamespace(candidates=0, expired=0, left_for_webhook=0)

    conn = _LockConn()
    repo = object()
    await _drive_one_tick(monkeypatch, repository=repo, conn=conn, sweep=sweep)

    assert len(called) == 1, "the sweep must run exactly once per periodic tick"
    assert called[0][1] is repo
    assert conn.calls == ["lock", "unlock"]


async def test_the_sweep_is_skipped_while_the_order_lane_answers_503(monkeypatch) -> None:
    """No `garuda_order_repository` means Xendit is unarmed and no order can
    exist. Sweeping then would be a query per 300s forever for nothing — and,
    worse, would take the advisory lock on a system with nothing to reconcile.
    """
    called: list[tuple] = []

    async def sweep(pool, repository, **kw):
        called.append((pool, repository))
        return SimpleNamespace(candidates=0, expired=0, left_for_webhook=0)

    conn = _LockConn()
    await _drive_one_tick(monkeypatch, repository=None, conn=conn, sweep=sweep)

    assert called == []
    assert conn.calls == [], "the lock must not even be requested"


async def test_the_advisory_lock_is_released_when_the_sweep_raises(monkeypatch) -> None:
    """The lock is SESSION-scoped: a sweep that raises without unlocking would
    strand it for the life of that pooled connection, after which no machine
    ever sweeps again — a silent, permanent outage of the thing being armed.
    """

    async def sweep(pool, repository, **kw):
        raise RuntimeError("provider unreachable")

    conn = _LockConn()
    # The loop must SURVIVE it (the drain is the product) and still reach its
    # scripted CancelledError rather than dying on the sweep's exception.
    await _drive_one_tick(monkeypatch, repository=object(), conn=conn, sweep=sweep)

    assert conn.calls == ["lock", "unlock"]


async def test_a_lock_held_by_another_machine_skips_the_sweep(monkeypatch) -> None:
    """`pg_try_advisory_lock` returning false means a sibling is already
    sweeping. Running anyway would select the SAME candidate rows -- the sweep's
    query has no `FOR UPDATE SKIP LOCKED`, unlike the drain's claim -- and make
    duplicate provider calls for one order.
    """
    called: list[tuple] = []

    async def sweep(pool, repository, **kw):
        called.append((pool, repository))
        return SimpleNamespace(candidates=0, expired=0, left_for_webhook=0)

    conn = _LockConn(grant=False)
    await _drive_one_tick(monkeypatch, repository=object(), conn=conn, sweep=sweep)

    assert called == []
    assert conn.calls == ["lock"], "no unlock: we never held it"
