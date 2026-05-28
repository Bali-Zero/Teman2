import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from scripts.wr2_canva_headless_apply import (
    acquire_master_lock,
    quota_ok_to_run,
    release_master_lock,
)


@pytest.mark.asyncio
async def test_acquire_master_lock_uses_template_id_key():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    got = await acquire_master_lock(conn, "DAHKzVykbbA")
    assert got is True
    key = int(hashlib.sha256(b"DAHKzVykbbA").hexdigest()[:15], 16)
    conn.fetchval.assert_awaited_once_with("SELECT pg_try_advisory_lock($1)", key)


@pytest.mark.asyncio
async def test_release_master_lock():
    conn = AsyncMock()
    await release_master_lock(conn, "DAHKzVykbbA")
    key = int(hashlib.sha256(b"DAHKzVykbbA").hexdigest()[:15], 16)
    conn.execute.assert_awaited_once_with("SELECT pg_advisory_unlock($1)", key)


def test_quota_ok_when_auth_status_clean():
    with patch("subprocess.run") as m:
        m.return_value.returncode = 0
        m.return_value.stdout = "Logged in as kaiser198719871987@gmail.com"
        m.return_value.stderr = ""
        assert quota_ok_to_run() is True


def test_quota_blocked_on_limit_string():
    with patch("subprocess.run") as m:
        m.return_value.returncode = 0
        m.return_value.stdout = "usage limit reached, resets in 2h"
        m.return_value.stderr = ""
        assert quota_ok_to_run() is False
