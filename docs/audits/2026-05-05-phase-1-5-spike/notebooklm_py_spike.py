#!/usr/bin/env python3
"""Phase 1.5 spike — empirical rate-limit + latency test for notebooklm-py v0.3.4.

Compressed window (target 30 min wall-clock max), instead of 60 min, to honor
NB-META as a binding study artifact (deletes are full hard deletes per API).

Operations:
- 8 source_add_url (using public arXiv URL — repeated benign add is idempotent-ish)
- 12 source_get_fulltext (random IDs from existing NB-META 78 sources)
- 30 chat.ask (mixed prompts)

Concurrency: 3 workers per category (asyncio.Semaphore). Total ~50 ops.
Abort early if 10+ 429s in any 5-min window.
Cleanup: delete all source_add'd URLs at end.

Output:
- /tmp/notebooklm_py_spike_results.json
- /tmp/notebooklm_py_spike_decision.txt
"""
from __future__ import annotations

import asyncio
import json
import random
import statistics
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import notebooklm
from notebooklm import RateLimitError, AuthError, ServerError, NetworkError

AUTH_PATH = "/tmp/nlm-py-spike/storage_state.json"
NB_META_ID = "6164fbb6-e079-4d2a-a1cc-c38ea5a086b7"
RESULTS = Path("/tmp/notebooklm_py_spike_results.json")
DECISION = Path("/tmp/notebooklm_py_spike_decision.txt")

# Public, benign arXiv URLs (rotating to mimic real ingestion patterns)
TEST_URLS = [
    "https://arxiv.org/abs/2401.04088",
    "https://arxiv.org/abs/2402.03300",
    "https://arxiv.org/abs/2403.08540",
    "https://arxiv.org/abs/2404.07143",
]
QUERY_PROMPTS = [
    "Summarize the key findings in two sentences.",
    "What are the main topics covered?",
    "List 3 key entities mentioned.",
    "Provide a brief overview.",
    "What questions does this raise?",
]
N_ADD = 8
N_GET = 12
N_QUERY = 30
CONCURRENCY = 3
ABORT_429_WINDOW_S = 300
ABORT_429_THRESHOLD = 10

operations: list[dict] = []
auth_refresh_count = 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_op(op: str, status: str, latency_ms: float, error: str | None, **extra) -> None:
    operations.append({
        "op": op,
        "ts": now_iso(),
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "error": error,
        **extra,
    })


def count_429_recent(window_s: float) -> int:
    cutoff = time.time() - window_s
    n = 0
    for op in operations:
        try:
            ts_epoch = datetime.fromisoformat(op["ts"]).timestamp()
        except ValueError:
            continue
        if ts_epoch >= cutoff and op.get("status") == "429":
            n += 1
    return n


def classify_exc(e: BaseException) -> tuple[str, str]:
    """Return (status_label, short_error_str)."""
    name = type(e).__name__
    if isinstance(e, RateLimitError):
        return "429", f"{name}: {e}"
    if isinstance(e, AuthError):
        return "401", f"{name}: {e}"
    if isinstance(e, ServerError):
        return "5xx", f"{name}: {e}"
    if isinstance(e, NetworkError):
        return "net_err", f"{name}: {e}"
    if isinstance(e, asyncio.TimeoutError):
        return "timeout", f"{name}: timeout"
    return "exc", f"{name}: {e}"


async def add_source(client, sem: asyncio.Semaphore, idx: int) -> str | None:
    """Returns source_id of added source for cleanup, or None on failure."""
    url = TEST_URLS[idx % len(TEST_URLS)]
    async with sem:
        if count_429_recent(ABORT_429_WINDOW_S) >= ABORT_429_THRESHOLD:
            log_op("source_add", "abort_skipped", 0.0, "429 storm threshold reached")
            return None
        t = time.time()
        try:
            src = await client.sources.add_url(NB_META_ID, url, wait=False)
            log_op("source_add", "200", (time.time() - t) * 1000, None,
                   url=url, source_id=src.id)
            return src.id
        except Exception as e:
            status, err = classify_exc(e)
            log_op("source_add", status, (time.time() - t) * 1000, err, url=url)
            return None


async def get_fulltext(client, sem: asyncio.Semaphore, source_id: str) -> None:
    async with sem:
        if count_429_recent(ABORT_429_WINDOW_S) >= ABORT_429_THRESHOLD:
            log_op("source_get_fulltext", "abort_skipped", 0.0, "429 storm threshold reached")
            return
        t = time.time()
        try:
            ft = await client.sources.get_fulltext(NB_META_ID, source_id)
            log_op("source_get_fulltext", "200", (time.time() - t) * 1000, None,
                   source_id=source_id, content_chars=len(getattr(ft, "content", "") or ""))
        except Exception as e:
            status, err = classify_exc(e)
            log_op("source_get_fulltext", status, (time.time() - t) * 1000, err,
                   source_id=source_id)


async def chat_ask(client, sem: asyncio.Semaphore, idx: int) -> None:
    prompt = QUERY_PROMPTS[idx % len(QUERY_PROMPTS)]
    async with sem:
        if count_429_recent(ABORT_429_WINDOW_S) >= ABORT_429_THRESHOLD:
            log_op("chat_ask", "abort_skipped", 0.0, "429 storm threshold reached")
            return
        t = time.time()
        try:
            res = await client.chat.ask(NB_META_ID, prompt)
            answer = getattr(res, "answer", None) or ""
            log_op("chat_ask", "200", (time.time() - t) * 1000, None,
                   answer_chars=len(answer))
        except Exception as e:
            status, err = classify_exc(e)
            log_op("chat_ask", status, (time.time() - t) * 1000, err)


async def main() -> int:
    started_at = now_iso()
    overall_t0 = time.time()
    print(f"[{started_at}] Phase 1.5 empirical spike start")

    # 1. Get list of existing sources for fulltext sampling
    async with await notebooklm.NotebookLMClient.from_storage(AUTH_PATH) as client:
        try:
            existing_srcs = await client.sources.list(NB_META_ID)
            existing_ids = [s.id for s in existing_srcs]
            print(f"  existing sources in NB-META: {len(existing_ids)}")
        except Exception as e:
            print(f"FAIL: unable to list sources: {e}")
            return 2
        sample_ids = random.sample(existing_ids, min(N_GET, len(existing_ids)))

        # 2. Run all ops with bounded concurrency
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = []
        added_ids: list[str] = []

        async def add_and_track(i: int) -> None:
            sid = await add_source(client, sem, i)
            if sid:
                added_ids.append(sid)

        for i in range(N_ADD):
            tasks.append(add_and_track(i))
        for sid in sample_ids:
            tasks.append(get_fulltext(client, sem, sid))
        for i in range(N_QUERY):
            tasks.append(chat_ask(client, sem, i))

        random.shuffle(tasks)  # interleave
        await asyncio.gather(*tasks, return_exceptions=False)

        elapsed_s = time.time() - overall_t0
        print(f"  ops completed in {elapsed_s:.1f}s")

        # 3. Cleanup added sources
        print(f"  cleanup: deleting {len(added_ids)} added sources")
        for sid in added_ids:
            t = time.time()
            try:
                ok = await client.sources.delete(NB_META_ID, sid)
                log_op("cleanup_delete", "200" if ok else "fail",
                       (time.time() - t) * 1000, None if ok else "delete returned False",
                       source_id=sid)
            except Exception as e:
                status, err = classify_exc(e)
                log_op("cleanup_delete", status, (time.time() - t) * 1000, err,
                       source_id=sid)

    ended_at = now_iso()
    # Compute summary
    success_count = sum(1 for o in operations if o["status"] == "200")
    count_429 = sum(1 for o in operations if o["status"] == "429")
    count_401 = sum(1 for o in operations if o["status"] == "401")
    count_5xx = sum(1 for o in operations if o["status"] == "5xx")
    count_neterr = sum(1 for o in operations if o["status"] == "net_err")
    count_timeout = sum(1 for o in operations if o["status"] == "timeout")
    latencies = [o["latency_ms"] for o in operations if o["status"] == "200"]
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)
    errors_first5 = [o["error"] for o in operations if o.get("error")][:5]

    summary = {
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_s": round(time.time() - overall_t0, 2),
        "total_ops": len(operations),
        "success_count": success_count,
        "429_count": count_429,
        "401_count": count_401,
        "5xx_count": count_5xx,
        "net_err_count": count_neterr,
        "timeout_count": count_timeout,
        "auth_refresh_events": auth_refresh_count,
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "errors_first5": errors_first5,
    }

    out = {"summary": summary, "operations": operations}
    RESULTS.write_text(json.dumps(out, indent=2))

    # Decision
    decision = "PROCEED"
    reasons = []
    # Scale 429 threshold by total runtime — KPI is <5/hr
    duration_h = summary["duration_s"] / 3600.0
    rate_429_per_hr = (count_429 / duration_h) if duration_h > 0 else 0
    if rate_429_per_hr >= 5:
        decision = "ABORT"
        reasons.append(f"429 rate {rate_429_per_hr:.1f}/hr >= 5/hr KPI K6")
    if auth_refresh_count >= 3:
        decision = "ABORT"
        reasons.append(f"auth_refresh_events={auth_refresh_count} >= 3")
    if p95 >= 10000:
        decision = "ABORT"
        reasons.append(f"p95={p95:.0f}ms >= 10000ms")
    if success_count == 0:
        decision = "ABORT"
        reasons.append("zero successes")
    if not reasons:
        reasons.append(f"429={rate_429_per_hr:.1f}/hr<5, auth_refresh={auth_refresh_count}<3, p95={p95:.0f}ms<10000ms, success_rate={success_count}/{len(operations)}")
    DECISION.write_text(f"{decision}: {' & '.join(reasons)}\n")

    print()
    print(json.dumps(summary, indent=2))
    print()
    print(f"DECISION: {decision} — {' & '.join(reasons)}")
    print(f"results: {RESULTS}")
    print(f"decision: {DECISION}")
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception:
        traceback.print_exc()
        DECISION.write_text(f"ABORT: top-level exception\n{traceback.format_exc()}")
        rc = 99
    raise SystemExit(rc)
