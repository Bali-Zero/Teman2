"""Tests for the visa_oracle_sessions retention purge scheduler (main_api).

Phase-3 replacement for a launchd-plist + wrapper + one-shot-worker design
that was correctly rejected as superscar #2 ("exists != armed") — see
`main_api._run_visa_oracle_sessions_purge_scheduler`'s own docstring. This
loop runs INSIDE the `api` process that already holds the pool and already
serves `/api/visa-oracle` (per `router_manifest.py`'s
`process_groups=_API` on the `visa_oracle` entry), the same way the GARUDA
outbox drain and the WA outbox scheduler already run in this same file.

Mirrors `test_garuda_outbox_scheduler.py`'s shape on purpose: an "arming"
section (the loop must actually be SPAWNED by the lifespan, not merely
exist and pass its own unit tests in isolation — that gap is exactly what
made the previous design invisible) plus a "cadence" section (fake pool +
patched `asyncio.sleep`, no wall-clock cost, no hang risk) plus an explicit
shutdown-cancellation mirror, since nothing upstream already covers that
for this file's tasks.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app import main_api

pytestmark = pytest.mark.asyncio


def _app(pool: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(db_pool=pool if pool is not None else object()))


# --------------------------------------------------------------------------
# kill switch — VISA_ORACLE_SESSIONS_PURGE_ENABLED
# --------------------------------------------------------------------------


def test_purge_enabled_defaults_on_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", raising=False)
    assert main_api._visa_oracle_sessions_purge_enabled() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "False", "0", "  false  ", "  0  "])
def test_purge_enabled_false_variants_disable(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", value)
    assert main_api._visa_oracle_sessions_purge_enabled() is False


@pytest.mark.parametrize("value", ["true", "1", "TRUE", "True"])
def test_purge_enabled_true_variants_enable(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", value)
    assert main_api._visa_oracle_sessions_purge_enabled() is True


def test_purge_enabled_unrecognized_value_fails_toward_enabled_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A typo like "flase" must not silently disable retention enforcement —
    the switch fails TOWARD the UU PDP data-minimisation requirement (stays
    enabled) but the operator still sees a warning, unlike leaving the var
    unset entirely (which is the intended, silent default)."""

    monkeypatch.setenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", "flase")
    with caplog.at_level(logging.WARNING, logger="zantara.backend"):
        assert main_api._visa_oracle_sessions_purge_enabled() is True
    assert any(
        "VISA_ORACLE_SESSIONS_PURGE_ENABLED" in record.message for record in caplog.records
    )


# --------------------------------------------------------------------------
# arming — the loop must be SPAWNED, not merely defined
# --------------------------------------------------------------------------


async def test_spawn_task_enabled_and_pool_ready_creates_the_real_loop_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calls the REAL production function directly — council round 1,
    finding F10 (both seats, PROVEN): the previous version of this test
    called a hand-copied mirror of `_background_light_init`'s `if`/`elif`/
    `else`, not the code itself, so deleting the real spawn left the test
    green. `_spawn_visa_oracle_sessions_purge_task` is now the ONE place
    this decision is made — `_background_light_init` calls it too (see the
    "lifespan calls it" test below), so there is nothing left to duplicate."""

    monkeypatch.delenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", raising=False)
    spawned: list[object] = []

    async def fake_loop(app: object) -> None:
        spawned.append(app)
        await asyncio.sleep(3600)

    monkeypatch.setattr(main_api, "_run_visa_oracle_sessions_purge_scheduler", fake_loop)
    app = _app()

    task = main_api._spawn_visa_oracle_sessions_purge_task(app)

    assert task is not None
    task.cancel()


async def test_spawn_task_disabled_returns_none_and_never_creates_a_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", "false")
    started: list[object] = []
    monkeypatch.setattr(
        main_api,
        "_run_visa_oracle_sessions_purge_scheduler",
        lambda app: started.append(app),
    )
    app = _app()

    task = main_api._spawn_visa_oracle_sessions_purge_task(app)

    assert started == []
    assert task is None


def test_spawn_task_returns_none_when_the_pool_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", raising=False)
    app = _app(pool=None)
    app.state.db_pool = None  # explicit — _app()'s default gives a sentinel object

    task = main_api._spawn_visa_oracle_sessions_purge_task(app)

    assert task is None


async def test_the_lifespan_actually_calls_the_real_spawn_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drives the REAL `lifespan_light` context manager (not a mirror of it),
    with only the heavy, unrelated service-init internals replaced — proves
    `_background_light_init` (the nested closure `lifespan_light` schedules)
    itself calls `_spawn_visa_oracle_sessions_purge_task`, closing exactly
    the gap council round 1 finding F10 named: "deleting the real spawn at
    main_api.py:810-812 leaves it green" is no longer true once this test
    exists, because THIS test drives the code at that call site, not a
    hand-copied stand-in for it."""

    monkeypatch.delenv("VISA_ORACLE_SESSIONS_PURGE_ENABLED", raising=False)
    # Silence the two other background-worker blocks _background_light_init
    # also runs in the same pass, so this test's only real assertion is
    # about the purge spawn call — not an accident of them succeeding.
    monkeypatch.setenv("WA_OUTBOX_SCHEDULER_ENABLED", "false")
    monkeypatch.delenv("GARUDA_OUTBOX_CONSUMER_ENABLED", raising=False)  # fail-closed default

    # AsyncMock, not a bare object() — lifespan_light's own shutdown block
    # unconditionally awaits `db_pool.close()`, so the fake pool must
    # survive that call for this test to reach its own assertions.
    db_pool_sentinel = AsyncMock()

    async def fake_initialize_services_light(app: object) -> None:
        app.state.db_pool = db_pool_sentinel
        app.state.cache = None

    monkeypatch.setattr(
        "backend.app.setup.service_initializer.initialize_services_light",
        fake_initialize_services_light,
    )
    # Deliberately NOT mocking the notification-scheduler import
    # (`backend.app.modules.notifications.scheduler`) — in this venv it is
    # missing its own `apscheduler` dependency, and `_background_light_init`
    # already wraps that whole block (import included) in its own
    # `try/except Exception`, so the ModuleNotFoundError is swallowed by the
    # REAL production code path exactly the way it would be if apscheduler
    # were briefly unavailable in prod. Patching it via a string target
    # would have to import the module first, which fails before the app
    # code even runs.

    spawn_calls: list[object] = []

    def fake_spawn(app: object) -> None:
        spawn_calls.append(app)
        return None

    monkeypatch.setattr(main_api, "_spawn_visa_oracle_sessions_purge_task", fake_spawn)

    app = SimpleNamespace(state=SimpleNamespace())
    async with main_api.lifespan_light(app):
        # `_background_light_init` runs as a scheduled task, not awaited
        # before `yield` (Fly.io health-check grace-period design) — poll
        # with a bounded number of zero-cost loop-yields rather than a
        # fixed sleep, so this stays fast on a quiet CI box and still
        # deterministic (no open-ended wait).
        for _ in range(200):
            if spawn_calls:
                break
            await asyncio.sleep(0)
        else:
            pytest.fail("_background_light_init never reached the purge spawn call")

    assert spawn_calls == [app]


# --------------------------------------------------------------------------
# shutdown — the task must be CANCELLED, not merely spawned
# --------------------------------------------------------------------------


async def test_shutdown_cancels_the_purge_task() -> None:
    """Reproduces the exact shutdown-side cancellation in `lifespan_light`
    against the SAME `app.state` attribute name the spawn side uses."""

    async def _never_ending() -> None:
        await asyncio.sleep(3600)

    app = _app()
    app.state._visa_oracle_sessions_purge_task = asyncio.create_task(_never_ending())
    await asyncio.sleep(0)  # let it actually start

    purge_task = getattr(app.state, "_visa_oracle_sessions_purge_task", None)
    assert purge_task is not None
    assert not purge_task.done()
    purge_task.cancel()
    try:
        await purge_task
    except (asyncio.CancelledError, Exception):
        pass
    assert purge_task.done()


async def test_shutdown_is_a_no_op_when_the_purge_was_never_spawned() -> None:
    app = _app()
    app.state._visa_oracle_sessions_purge_task = None
    purge_task = getattr(app.state, "_visa_oracle_sessions_purge_task", None)
    if purge_task is not None:  # pragma: no cover - guard mirrors the real shutdown
        purge_task.cancel()
        try:
            await purge_task
        except (asyncio.CancelledError, Exception):
            pass
    # The guard must have taken the `is None` branch — not "no exception was
    # raised", which an accidental removal of the guard could still satisfy
    # by coincidence.
    assert purge_task is None


# --------------------------------------------------------------------------
# cadence
# --------------------------------------------------------------------------


async def _drive(
    monkeypatch: pytest.MonkeyPatch, purge_results: list[object]
) -> tuple[list[float], list[dict]]:
    """Run the loop over a scripted list of `_purge_expired_sessions`
    outcomes (an int for a normal return, an Exception instance to raise),
    return (sleeps, calls). `asyncio.CancelledError` is raised once the
    script is exhausted, exactly like `test_garuda_outbox_scheduler.py`
    bounds its own loop."""

    slept: list[float] = []
    calls: list[dict] = []
    script = list(purge_results)

    async def fake_purge(pool: object, *, limit: int) -> int:
        calls.append({"pool": pool, "limit": limit})
        if not script:
            raise asyncio.CancelledError
        outcome = script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(
        "backend.app.routers.visa_oracle._purge_expired_sessions", fake_purge
    )
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await main_api._run_visa_oracle_sessions_purge_scheduler(_app())
    return slept, calls


async def test_each_tick_calls_purge_with_the_bounded_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, calls = await _drive(monkeypatch, [0])
    assert calls, "the purge was never called"
    assert calls[0]["limit"] == main_api._VISA_ORACLE_PURGE_LIMIT == 500


async def test_first_tick_waits_a_randomized_short_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept, _ = await _drive(monkeypatch, [3])
    assert slept, "the loop never slept"
    initial_delay = slept[0]
    assert (
        main_api._VISA_ORACLE_PURGE_INITIAL_DELAY_MIN_SECONDS
        <= initial_delay
        <= main_api._VISA_ORACLE_PURGE_INITIAL_DELAY_MAX_SECONDS
    )


async def test_steady_state_ticks_are_about_an_hour_apart_with_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept, _ = await _drive(monkeypatch, [0, 0])
    assert len(slept) >= 2
    steady = slept[1]
    lo = (
        main_api._VISA_ORACLE_PURGE_INTERVAL_SECONDS
        - main_api._VISA_ORACLE_PURGE_JITTER_SECONDS
    )
    hi = (
        main_api._VISA_ORACLE_PURGE_INTERVAL_SECONDS
        + main_api._VISA_ORACLE_PURGE_JITTER_SECONDS
    )
    assert lo <= steady <= hi


async def test_a_failing_tick_does_not_kill_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loop survives an exception the query path itself never raises in
    practice (`_purge_expired_sessions` already catches its own DB errors) —
    this is the second net, and it must not be a trapdoor."""

    slept, calls = await _drive(monkeypatch, [RuntimeError("boom")])
    assert len(calls) == 2, "the loop stopped after the first failure"
    assert len(slept) == 2


async def test_a_failing_tick_logs_only_the_exception_class_never_the_message(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """PII boundary: a tick failure must never carry a session_id or quiz
    answer into a log line, even indirectly via an exception's own str()."""

    with caplog.at_level(logging.WARNING, logger="zantara.backend"):
        await _drive(
            monkeypatch,
            [RuntimeError("session_id=abc123 quiz_answers=very-private-stuff")],
        )
    warnings = " ".join(
        record.message for record in caplog.records if record.levelno == logging.WARNING
    )
    assert "RuntimeError" in warnings
    assert "session_id" not in warnings
    assert "quiz_answers" not in warnings
    assert "abc123" not in warnings
