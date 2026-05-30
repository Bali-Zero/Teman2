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


from scripts.wr2_canva_headless_apply import canva_tools_loaded_in_stream


def test_canva_tools_loaded_true_when_present():
    jsonl = '{"type":"system","tools":["ToolSearch"]}\n{"message":{"content":[{"type":"tool_use","name":"mcp__claude_ai_Canva__start-editing-transaction"}]}}\n'
    assert canva_tools_loaded_in_stream(jsonl) is True


def test_canva_tools_loaded_false_when_absent():
    jsonl = '{"type":"system","tools":["ToolSearch"]}\n{"message":{"content":[{"type":"text","text":"NO CANVA MCP"}]}}\n'
    assert canva_tools_loaded_in_stream(jsonl) is False


import json as _json
from pathlib import Path


@pytest.mark.asyncio
async def test_apply_headless_writes_carousel_canva_json(tmp_path):
    pending = tmp_path / "canva_pending.json"
    out = tmp_path / "carousel_canva.json"
    pending.write_text(_json.dumps({"status": "applied", "design_id": "DAHKxyz",
                                     "topic": "t", "slides_count": 11}))
    conn = AsyncMock(); conn.fetchval.return_value = True
    stream = '{"message":{"content":[{"type":"tool_use","name":"mcp__claude_ai_Canva__commit-editing-transaction"}]}}'
    # apply_headless reads ~/.claude/skills/canva-apply.md via Path.read_text. That
    # file may not exist in CI → FileNotFoundError before the test can assert. Route
    # a dummy ONLY for the skills path; the pending/out reads use tmp_path real files.
    real_read = Path.read_text
    def _read(self, *a, **k):
        if self.name == "canva-apply.md":
            return "DUMMY SKILL BODY"
        return real_read(self, *a, **k)
    with patch("scripts.wr2_canva_headless_apply.quota_ok_to_run", return_value=True), \
         patch.object(Path, "read_text", _read), \
         patch("subprocess.run") as m:
        m.return_value.stdout = stream
        m.return_value.returncode = 0
        from scripts.wr2_canva_headless_apply import apply_headless
        res = await apply_headless(conn, pending, "DAHKtmpl", out)
    assert res[0] == "DAHKxyz"
    assert _json.loads(out.read_text())["design_id"] == "DAHKxyz"
    conn.execute.assert_awaited()  # release called
