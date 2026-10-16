"""Same-cluster synthetic measurement, not a production capacity claim."""

from __future__ import annotations

import importlib.util
import json
import statistics
import subprocess
import time
from pathlib import Path

import asyncpg
import pytest

from backend.db.repositories.conversation_repository import ConversationRepository
from backend.tests.db.test_universal_conversation_pg import conversation_pool  # noqa: F401

pytestmark = pytest.mark.integration
BASELINE = "a68b75f043479fafee9f7e9cbf1d91d969f614f4"


@pytest.mark.asyncio
async def test_same_cluster_sequential_cost(
    conversation_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    source = subprocess.check_output(
        [
            "git",
            "show",
            BASELINE + ":apps/backend-rag/backend/db/repositories/conversation_repository.py",
        ],
        text=True,
    )
    baseline_path = tmp_path / "baseline_conversation.py"
    baseline_path.write_text(source)
    spec = importlib.util.spec_from_file_location("universal_baseline_conversation", baseline_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async with conversation_pool.acquire() as conn:
        await conn.execute("DROP TRIGGER force_overlap ON conversations")
        await conn.execute("""INSERT INTO conversations(user_id, session_id, messages, metadata)
            SELECT 'synthetic-user', 'synthetic-session-' || n, '[]'::jsonb, '{}'::jsonb
            FROM generate_series(1, 2000) n""")
        await conn.execute("ANALYZE conversations")
        plan = await conn.fetchval("""EXPLAIN (FORMAT JSON) SELECT id, messages, metadata
            FROM conversations WHERE session_id = 'synthetic-session-1000'
            ORDER BY created_at DESC, id DESC LIMIT 1 FOR UPDATE""")
    results = {}
    for name, cls in (
        ("baseline", module.ConversationRepository),
        ("candidate", ConversationRepository),
    ):
        async with conversation_pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET messages='[]'::jsonb, metadata='{}'::jsonb"
            )
        repository = cls(conversation_pool)
        times = []
        for i in range(210):
            started = time.perf_counter()
            result = await repository.save_messages(
                f"synthetic-session-{i + 1}", "synthetic-user", [{"content": name}]
            )
            elapsed = (time.perf_counter() - started) * 1000
            assert result is not None
            if i >= 10:
                times.append(elapsed)
        results[name] = {
            "samples": len(times),
            "median_ms": statistics.median(times),
            "p95_ms": sorted(times)[int(len(times) * 0.95) - 1],
            "max_ms": max(times),
        }
        if name == "baseline":
            # Declared before candidate measurement: permissive regression alarm
            # for local SQL overhead only, not an invented product latency SLO.
            threshold = max(results[name]["p95_ms"] * 2, results[name]["p95_ms"] + 2)
            print(
                "BASELINE_MEASUREMENT "
                + json.dumps({"baseline": results[name], "candidate_p95_limit_ms": threshold}),
                flush=True,
            )
    print(
        "SYNTHETIC_MEASUREMENT "
        + json.dumps({"rows": 2000, "fsync": "on", "results": results, "query_plan": plan}),
        flush=True,
    )
    assert results["candidate"]["p95_ms"] <= threshold
