"""Tests for the job registry."""
from __future__ import annotations

import pytest

from backend.jobs.context import JobContext
from backend.jobs.registry import (
    JobDeclaration,
    Registry,
    RegistryError,
)


async def _noop(ctx: JobContext):
    return None


def test_register_then_list():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    names = [d.name for d in reg.all()]
    assert names == ["a"]


def test_register_duplicate_rejected():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    with pytest.raises(RegistryError, match="already registered"):
        reg.register(name="a", cron="0 0 * * *", handler=_noop)


def test_register_skip_middleware_requires_reason():
    reg = Registry()
    with pytest.raises(RegistryError, match="reason"):
        reg.register(
            name="a", cron="*/5 * * * *", handler=_noop,
            skip_middleware=("oauth_guard",),
            skip_reasons={},
        )


def test_register_skip_middleware_with_reason_ok():
    reg = Registry()
    reg.register(
        name="a", cron="*/5 * * * *", handler=_noop,
        skip_middleware=("cost_cap",),
        skip_reasons={"cost_cap": "this job legitimately needs $5/run"},
    )
    decl = reg.get("a")
    assert "cost_cap" in decl.skip_middleware


def test_register_invalid_cron_rejected():
    reg = Registry()
    with pytest.raises(RegistryError, match="cron"):
        reg.register(name="a", cron="not a cron", handler=_noop)


def test_freeze_prevents_further_registration():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    reg.freeze()
    with pytest.raises(RegistryError, match="frozen"):
        reg.register(name="b", cron="*/5 * * * *", handler=_noop)


def test_get_missing_raises():
    reg = Registry()
    with pytest.raises(KeyError):
        reg.get("nope")
