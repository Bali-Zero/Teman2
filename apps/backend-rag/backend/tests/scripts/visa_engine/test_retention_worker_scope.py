"""L1541: GARUDA retention purge primitives were declared and never called.

Pins two things with no live Postgres required (asyncpg.Pool objects are
never touched here -- every purge/evidence call is replaced with a mock):

1. `SCOPE_PURGE_FUNCTIONS` actually registers every `purge_expired_garuda_*`
   primitive this repo defines -- the guilt case reproduces the exact bug
   (a primitive that exists and is never called) by removing one from the
   registry and asserting the parity test catches it.
2. `run_scope_purge_cycle` / `--scope` actually invoke the registered
   primitives, bounded, and never widen past the default `VISA_DECISION`.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest

from backend.scripts.visa_engine import retention_worker
from backend.services.garuda_flow import check_store as garuda_check_store
from backend.services.garuda_flow import retention as garuda_retention


def _defined_purge_primitives() -> set[object]:
    """Every `purge_expired_*` async function this repo actually defines,
    across the modules `SCOPE_PURGE_FUNCTIONS` is supposed to cover."""
    primitives: set[object] = set()
    for module in (garuda_retention, garuda_check_store):
        for name, obj in vars(module).items():
            if name.startswith("purge_expired_") and inspect.iscoroutinefunction(obj):
                primitives.add(obj)
    return primitives


def _registered_purge_functions() -> set[object]:
    return {
        purge_fn
        for entries in retention_worker.SCOPE_PURGE_FUNCTIONS.values()
        for _label, purge_fn, _signature in entries
    }


def test_every_garuda_purge_primitive_is_registered() -> None:
    """Innocence: today's registry already covers every defined primitive."""
    defined = _defined_purge_primitives()
    assert defined, "sanity: expected at least one purge_expired_garuda_* primitive on disk"
    assert defined <= _registered_purge_functions()


def test_scope_parity_catches_an_unregistered_primitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guilt: reproduces L1541's exact shape -- a purge primitive exists and
    is orphaned from the registry. Mutating the registry to drop one entry
    must make the parity check above fail."""
    trimmed = {
        scope: tuple(e for e in entries if e[0] != "garuda_voa_check_results")
        for scope, entries in retention_worker.SCOPE_PURGE_FUNCTIONS.items()
    }
    monkeypatch.setattr(retention_worker, "SCOPE_PURGE_FUNCTIONS", trimmed)

    defined = _defined_purge_primitives()
    registered = _registered_purge_functions()
    assert not (defined <= registered), "orphaned primitive was not caught by the parity check"


@pytest.mark.asyncio
async def test_run_scope_purge_cycle_drains_bounded_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_a = AsyncMock(side_effect=[1_000, 7])  # two batches, second drains it
    purge_b = AsyncMock(side_effect=[3])
    monkeypatch.setattr(
        retention_worker,
        "SCOPE_PURGE_FUNCTIONS",
        {
            "GARUDA_CHECK": (
                ("table_a", purge_a, "public.purge_a(integer,text)"),
                ("table_b", purge_b, "public.purge_b(integer,text)"),
            )
        },
    )

    results = await retention_worker.run_scope_purge_cycle(
        object(),  # type: ignore[arg-type]
        "GARUDA_CHECK",
        apply=True,
        limit=1_000,
        max_batches=5,
        requested_by="healer-tick",
    )

    by_label = {r.label: r for r in results}
    assert by_label["table_a"].deleted == 1_007
    assert by_label["table_a"].exhausted_batch_cap is False
    assert by_label["table_b"].deleted == 3
    assert purge_a.await_count == 2
    assert purge_b.await_count == 1


@pytest.mark.asyncio
async def test_run_scope_purge_cycle_dry_run_never_calls_purge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_fn = AsyncMock(return_value=999)
    monkeypatch.setattr(
        retention_worker,
        "SCOPE_PURGE_FUNCTIONS",
        {"GARUDA_CHECK": (("table_a", purge_fn, "public.purge_a(integer,text)"),)},
    )

    results = await retention_worker.run_scope_purge_cycle(
        object(),  # type: ignore[arg-type]
        "GARUDA_CHECK",
        apply=False,
        limit=1_000,
        max_batches=5,
        requested_by="healer-tick",
    )

    assert results[0].deleted == 0
    purge_fn.assert_not_called()


@pytest.mark.asyncio
async def test_run_scope_purge_cycle_reports_backlog_when_batch_cap_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_fn = AsyncMock(return_value=1_000)  # never drains below `limit`
    monkeypatch.setattr(
        retention_worker,
        "SCOPE_PURGE_FUNCTIONS",
        {"GARUDA_CHECK": (("table_a", purge_fn, "public.purge_a(integer,text)"),)},
    )

    results = await retention_worker.run_scope_purge_cycle(
        object(),  # type: ignore[arg-type]
        "GARUDA_CHECK",
        apply=True,
        limit=1_000,
        max_batches=3,
        requested_by="healer-tick",
    )

    assert results[0].exhausted_batch_cap is True
    assert purge_fn.await_count == 3


def test_default_scope_is_visa_decision_only() -> None:
    args = retention_worker._parse_args([])
    assert args.scope == ["VISA_DECISION"]


def test_scope_flag_is_repeatable_and_never_implicitly_widens() -> None:
    args = retention_worker._parse_args(["--scope", "GARUDA_CHECK"])
    assert args.scope == ["GARUDA_CHECK"]  # VISA_DECISION not silently added


@pytest.mark.asyncio
async def test_run_rejects_an_unregistered_scope_before_touching_the_database() -> None:
    args = retention_worker._parse_args(["--scope", "GARUDA_CHECK"])
    args.database_url_env = "VISA_ENGINE_RETENTION_DATABASE_URL"
    monkeypatch_registry = {}  # no scopes registered at all
    orig = retention_worker.SCOPE_PURGE_FUNCTIONS
    retention_worker.SCOPE_PURGE_FUNCTIONS = monkeypatch_registry
    try:
        with pytest.raises(ValueError, match="no purge path registered"):
            await retention_worker.run(args)
    finally:
        retention_worker.SCOPE_PURGE_FUNCTIONS = orig
