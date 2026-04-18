"""Tests for retry policy + exception taxonomy."""
from __future__ import annotations

import asyncio

import asyncpg
import httpx
import pytest

from backend.jobs.retry import (
    DEFAULT_RETRY,
    CostExceeded,
    JobError,
    OAuthViolation,
    PermanentError,
    RetryPolicy,
    TransientError,
    classify,
    transient_on,
)


def test_default_retry_policy():
    assert DEFAULT_RETRY.max_attempts == 3
    assert DEFAULT_RETRY.backoff_seconds == (0.5, 2.0)


def test_custom_retry_policy_rejects_mismatched_backoff_length():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=3, backoff_seconds=(0.5, 2.0, 8.0))


def test_classify_transient_is_retryable():
    assert classify(TransientError("net")) == "transient"


def test_classify_permanent_is_not_retryable():
    assert classify(PermanentError("bad input")) == "permanent"


def test_classify_oauth_violation_is_permanent():
    assert classify(OAuthViolation("leak")) == "permanent"


def test_classify_cost_exceeded_is_permanent():
    assert classify(CostExceeded("over budget")) == "permanent"


def test_classify_unknown_defaults_to_permanent():
    assert classify(ValueError("oops")) == "permanent"


def test_oauth_and_cost_exceeded_subclass_joberror():
    assert issubclass(OAuthViolation, JobError)
    assert issubclass(CostExceeded, JobError)


@pytest.mark.asyncio
async def test_transient_on_decorator_wraps_known_exceptions():
    @transient_on(asyncpg.PostgresConnectionError, httpx.ConnectError, asyncio.TimeoutError)
    async def handler():
        raise asyncpg.PostgresConnectionError("connection refused")

    with pytest.raises(TransientError) as excinfo:
        await handler()
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresConnectionError)


@pytest.mark.asyncio
async def test_transient_on_decorator_passes_through_other_exceptions():
    @transient_on(asyncpg.PostgresConnectionError)
    async def handler():
        raise ValueError("bad value")

    with pytest.raises(ValueError):
        await handler()
