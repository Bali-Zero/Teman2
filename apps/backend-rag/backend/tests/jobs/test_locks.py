"""Tests for Postgres advisory-lock helper."""
from __future__ import annotations

import asyncio

import pytest

from backend.jobs.locks import advisory_lock, stable_hash_int64


def test_stable_hash_int64_is_deterministic():
    a = stable_hash_int64("job:x:2026-04-18T00:00:00")
    b = stable_hash_int64("job:x:2026-04-18T00:00:00")
    assert a == b


def test_stable_hash_int64_fits_signed_64():
    h = stable_hash_int64("some:key")
    assert -(2**63) <= h < 2**63


async def test_advisory_lock_acquires_when_free(pg_conn):
    async with advisory_lock(pg_conn, "job:x:tick1") as got:
        assert got is True


async def test_advisory_lock_second_acquirer_fails(pg_pool):
    async with pg_pool.acquire() as c1, pg_pool.acquire() as c2:
        async with advisory_lock(c1, "job:x:tick2") as got1:
            assert got1 is True
            async with advisory_lock(c2, "job:x:tick2") as got2:
                assert got2 is False


async def test_advisory_lock_released_after_context(pg_pool):
    async with pg_pool.acquire() as c1:
        async with advisory_lock(c1, "job:x:tick3"):
            pass
    async with pg_pool.acquire() as c2:
        async with advisory_lock(c2, "job:x:tick3") as got:
            assert got is True


async def test_advisory_lock_released_on_exception(pg_pool):
    async with pg_pool.acquire() as c1:
        with pytest.raises(RuntimeError):
            async with advisory_lock(c1, "job:x:tick4"):
                raise RuntimeError("boom")
    async with pg_pool.acquire() as c2:
        async with advisory_lock(c2, "job:x:tick4") as got:
            assert got is True
