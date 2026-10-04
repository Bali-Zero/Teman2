"""The fact gate must outlive a request, not occupy its transport for minutes."""

import asyncio
import os
import signal
import sys
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastmcp import Client, FastMCP

from nuzantara_mcp.tools import workspace_marketing as marketing

REAL_NOTEBOOK_QUERY = marketing._query_notebooklm


@pytest_asyncio.fixture
async def gate(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    article = {
        "item_id": "news_async",
        "title": "Public report",
        "category": "business",
        "content": "A public business claim.",
        "source_url": "https://example.go.id",
    }
    backend = AsyncMock(side_effect=lambda *a, **kw: dict(article))
    query = AsyncMock(return_value="Grounding evidence")
    reviewer = AsyncMock(
        return_value={
            "verdict": "PASS",
            "notebooklm_verdict": "PASS",
            "checked_claims": 2,
            "findings": ["Supported by the primary source."],
        }
    )
    monkeypatch.setattr(marketing, "_query_notebooklm", query)
    monkeypatch.setattr(marketing, "_run_independent_fact_reviewer", reviewer)
    tools = {}

    class Capture:
        def tool(self, **kwargs):
            def register(fn):
                tools[fn.__name__] = fn
                return fn

            return register

    marketing.register(Capture(), backend)
    yield tools, article, query, reviewer, backend
    tasks = list(getattr(marketing, "_FACT_GATE_TASKS", {}).values())
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def finish():
    await asyncio.gather(*list(marketing._FACT_GATE_TASKS.values()))


@pytest.mark.asyncio
async def test_gate_returns_promptly_then_reads_durable_result_without_rerun(gate):
    tools, _, query, reviewer, _ = gate
    release = asyncio.Event()

    async def slow_query(*args):
        await release.wait()
        return "Grounding evidence"

    query.side_effect = slow_query
    first = await asyncio.wait_for(tools["newsroom_fact_gate"]("news_async"), 0.2)
    assert first["status"] == "running"
    assert "ok" not in first  # In progress is neither PASS nor BLOCK.
    repeated = await tools["newsroom_fact_gate"]("news_async")
    assert repeated == first
    read = await tools["newsroom_get_article"]("news_async")
    assert read["fact_gate"]["status"] == "running"
    release.set()
    await finish()
    done = await tools["newsroom_fact_gate"]("news_async")
    assert done["ok"] is True and done["status"] == "completed"
    query.assert_awaited_once()
    reviewer.assert_awaited_once()
    assert (await tools["newsroom_get_article"]("news_async"))["fact_gate"][
        "status"
    ] == "PASS"


@pytest.mark.asyncio
async def test_real_mcp_call_returns_while_provider_waits_and_read_still_works(gate):
    _, _, query, _, backend = gate
    release = asyncio.Event()

    async def slow(*args):
        await release.wait()
        return "Evidence"

    query.side_effect = slow
    server = FastMCP("fact-gate-transport-test")
    marketing.register(server, backend)
    async with Client(server) as client:
        result = await asyncio.wait_for(
            client.call_tool(
                "newsroom_fact_gate",
                {"item_id": "news_async"},
            ),
            2,
        )
        assert not result.is_error and "running" in str(result)
        read = await asyncio.wait_for(
            client.call_tool(
                "newsroom_get_article",
                {"item_id": "news_async"},
            ),
            2,
        )
        assert not read.is_error and "Public report" in str(read)
        release.set()
        await finish()
        done = await client.call_tool("newsroom_fact_gate", {"item_id": "news_async"})
        assert not done.is_error and "completed" in str(done)


@pytest.mark.asyncio
async def test_provider_failure_is_durable_redacted_and_needs_fresh_key(gate):
    tools, _, query, _, _ = gate
    query.side_effect = RuntimeError("private-provider-output-must-not-escape")
    await tools["newsroom_fact_gate"]("news_async", request_key="first-attempt")
    await finish()
    result = await tools["newsroom_fact_gate"](
        "news_async", request_key="first-attempt"
    )
    assert result["status"] == "failed"
    assert "private-provider" not in str(result)
    assert query.await_count == 1
    await tools["newsroom_fact_gate"]("news_async", request_key="fresh-attempt")
    await finish()
    assert query.await_count == 2


@pytest.mark.asyncio
async def test_only_one_provider_job_even_for_different_articles(gate):
    tools, article, query, _, _ = gate
    release = asyncio.Event()

    async def slow(*args):
        await release.wait()
        return "Evidence"

    query.side_effect = slow
    await tools["newsroom_fact_gate"]("news_async")
    article["item_id"] = "news_other"
    with pytest.raises(RuntimeError, match="already running"):
        await tools["newsroom_fact_gate"]("news_other")


@pytest.mark.asyncio
async def test_changed_copy_does_not_receive_a_stale_verdict(gate):
    tools, article, query, _, _ = gate
    release = asyncio.Event()

    async def slow(*args):
        await release.wait()
        return "Evidence"

    query.side_effect = slow
    await tools["newsroom_fact_gate"]("news_async")
    article["content"] = "Different public claim."
    release.set()
    await finish()
    assert marketing._load_fact_gate("news_async") is None


@pytest.mark.asyncio
async def test_historical_key_replays_its_result_and_invalidated_cover_rejects_it(gate):
    tools, _, query, _, _ = gate
    await tools["newsroom_fact_gate"]("news_async", request_key="old-attempt")
    await finish()
    old = await tools["newsroom_fact_gate"]("news_async", request_key="old-attempt")
    await tools["newsroom_fact_gate"]("news_async", request_key="new-attempt")
    await finish()
    assert (
        await tools["newsroom_fact_gate"]("news_async", request_key="old-attempt")
        == old
    )
    assert query.await_count == 2
    await marketing._invalidate_fact_gate("news_async")
    with pytest.raises(ValueError, match="another editorial revision"):
        await tools["newsroom_fact_gate"]("news_async", request_key="old-attempt")


@pytest.mark.asyncio
async def test_invalidation_before_worker_starts_releases_provider_lock(gate):
    tools, _, query, _, _ = gate
    await tools["newsroom_fact_gate"]("news_async")
    await marketing._invalidate_fact_gate("news_async")
    assert marketing._load_fact_gate("news_async") is None
    assert not marketing._FACT_GATE_TASKS
    assert (await tools["newsroom_fact_gate"]("news_async"))["status"] == "running"
    await finish()
    query.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_provider_is_killed_and_reaped(monkeypatch):
    original = asyncio.create_subprocess_exec
    spawned = []
    ready = asyncio.Event()

    async def capture(*args, **kwargs):
        proc = await original(*args, **kwargs)
        spawned.append(proc)
        ready.set()
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    task = asyncio.create_task(
        marketing._run_public_subprocess(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout_seconds=60,
            env={"PATH": "/usr/bin:/bin"},
        )
    )
    await ready.wait()
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert spawned[0].returncode is not None
    finally:
        if spawned[0].returncode is None:
            spawned[0].kill()
            await spawned[0].wait()


@pytest.mark.asyncio
async def test_failed_notebook_part_reaps_siblings_before_releasing_lease(
    gate, monkeypatch
):
    tools, article, _, _, _ = gate
    sibling_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleanup_allowed = asyncio.Event()
    cleaned = asyncio.Event()
    calls = 0

    async def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            await sibling_started.wait()
            raise marketing.EditorialProviderFailure("nlm", "auth_required")
        sibling_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup_started.set()
            await cleanup_allowed.wait()
            cleaned.set()
            raise

    monkeypatch.setattr(marketing, "_query_notebooklm", REAL_NOTEBOOK_QUERY)
    monkeypatch.setattr(
        marketing, "_split_article_for_notebooklm", lambda a: ["one", "two"]
    )
    monkeypatch.setattr(marketing.shutil, "which", lambda *a, **kw: "/fake/nlm")
    monkeypatch.setattr(marketing, "_run_public_subprocess", provider)
    try:
        await tools["newsroom_fact_gate"]("news_async")
        await asyncio.wait_for(cleanup_started.wait(), 1)
        assert not cleaned.is_set()
        article["item_id"] = "news_other"
        with pytest.raises(RuntimeError, match="already running"):
            await tools["newsroom_fact_gate"]("news_other")
    finally:
        cleanup_allowed.set()
    await finish()
    assert cleaned.is_set() and calls == 2
    assert marketing._load_fact_job("news_async")["error_kind"] == "auth_required"


@pytest.mark.asyncio
async def test_cancelled_cover_request_cannot_restore_old_verdict_or_revision(
    gate, monkeypatch
):
    tools, article, query, _, backend = gate
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    await tools["newsroom_fact_gate"]("news_async", request_key="before-cover")
    await finish()
    started, stopping, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            stopping.set()
            await release.wait()
            raise

    query.side_effect = slow
    backend.side_effect = lambda path, **kw: (
        {"success": True} if path.endswith("/cover") else dict(article)
    )
    await tools["newsroom_fact_gate"]("news_async", request_key="during-cover")
    await started.wait()
    edit = asyncio.create_task(
        tools["newsroom_attach_cover"](
            "news_async",
            "c2FmZQ==",
            "cover.jpg",
        )
    )
    try:
        await asyncio.wait_for(stopping.wait(), 1)
        edit.cancel()
        with pytest.raises(asyncio.CancelledError):
            await edit
        assert marketing._load_fact_gate("news_async") is None
        with pytest.raises(ValueError, match="another editorial revision"):
            await tools["newsroom_fact_gate"]("news_async", request_key="before-cover")
    finally:
        release.set()
        await asyncio.gather(
            *list(marketing._FACT_GATE_TASKS.values()), return_exceptions=True
        )
    assert marketing._load_fact_job("news_async")["revision"] == 1
    assert marketing._load_fact_job("news_async")["status"] == "invalidated"


@pytest.mark.asyncio
async def test_cancel_reaps_grandchild_that_inherited_output_pipes(
    tmp_path, monkeypatch
):
    marker = tmp_path / "owned-child.pid"
    original = asyncio.create_subprocess_exec
    processes = []

    async def capture(*args, **kwargs):
        proc = await original(*args, **kwargs)
        processes.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    program = (
        "import subprocess,sys,time,pathlib; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"pathlib.Path({str(marker)!r}).write_text(str(p.pid)); time.sleep(30)"
    )
    task = asyncio.create_task(
        marketing._run_public_subprocess(
            [sys.executable, "-c", program],
            timeout_seconds=60,
            env={"PATH": "/usr/bin:/bin"},
        )
    )
    try:

        async def ready():
            while not marker.exists():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(ready(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert processes[0].returncode is not None
    finally:
        if processes and processes[0].returncode is None:
            os.killpg(processes[0].pid, signal.SIGKILL)
        await asyncio.gather(task, return_exceptions=True)
