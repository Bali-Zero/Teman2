"""Generate textual summaries for Louvain communities (GraphRAG 2.0).

For each `kg_communities` row without a populated `summary`, build a compact
prompt from the top entities and member names, call the local Ollama model
(fallback to a deterministic templated summary), and persist the summary.

Design:
- Resume-safe: only processes communities where summary IS NULL or '' via
  an explicit query filter. Idempotent — rerunning is a no-op on done rows.
- Concurrency-limited: asyncio.Semaphore bounds Ollama inflight calls.
- Telegram digest every TELEGRAM_STEP communities (default 500).
- Fallback: on Ollama error we write a deterministic summary from top
  entities so the community is not re-tried forever.

Usage:
    PYTHONPATH=. python scripts/generate_community_summaries.py \
        --model qwen3:4b --limit 6310 --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Any

import asyncpg
import httpx

def _require_env(name: str) -> str:
    import os as _os
    val = _os.environ.get(name)
    if not val:
        raise SystemExit(f"{name} env var is required (no hardcoded fallback for security)")
    return val




logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("community_summaries")


DB_URL = _require_env("ENTITY_LINKER_DB_URL")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

PROGRESS_STEP = int(os.environ.get("COMMUNITY_PROGRESS_STEP", "100"))
TELEGRAM_STEP = int(os.environ.get("COMMUNITY_TELEGRAM_STEP", "500"))


async def _maybe_notify(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.debug("Telegram skipped (no token): %s", message)
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "disable_notification": True,
                },
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram notify failed: %s", exc)


SYSTEM_PROMPT = (
    "You write concise one-paragraph summaries of clusters of legal/business "
    "entities extracted from Indonesian regulations. Output Italian, plain "
    "text, 2-3 sentences, factual, no preamble, no bullet points, no markdown."
)

# Qwen3:4b tends to emit reasoning preambles even with `think: false`. We
# detect these and strip them. If nothing usable remains, we treat the call
# as a soft failure and fall back to the deterministic summary.
_PREAMBLE_MARKERS = (
    "okay,", "okay.", "sure,", "first, i", "first i need",
    "let me", "let's tackle", "let's break", "the user wants",
    "the user is asking", "i need to", "to start",
)


def _fallback_summary(community_id: str, top_entities: list[str], member_count: int) -> str:
    entities = ", ".join(top_entities[:8]) if top_entities else "voci eterogenee"
    return (
        f"Cluster KG Louvain {community_id} ({member_count} membri) centrato su: "
        f"{entities}. Raggruppamento automatico, riepilogo semantico non "
        f"disponibile."
    )


async def _fetch_member_names(pool: asyncpg.Pool, community_id: str, limit: int = 20) -> list[str]:
    rows = await pool.fetch(
        """
        SELECT n.name
        FROM kg_node_community nc
        JOIN kg_nodes n ON n.entity_id = nc.entity_id
        WHERE nc.community_id = $1
        ORDER BY n.name
        LIMIT $2
        """,
        community_id,
        limit,
    )
    return [r["name"] for r in rows if r["name"]]


async def _call_ollama(
    client: httpx.AsyncClient,
    model: str,
    prompt: str,
    timeout: float = 30.0,
) -> str:
    """Call Ollama /api/chat. Returns assistant text or raises."""
    resp = await client.post(
        "/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 200},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    content = ((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError(f"empty content: {data}")

    return _strip_preamble(content)


def _strip_preamble(content: str) -> str:
    import re as _re

    content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()
    # Keep stripping early paragraphs that start with a reasoning preamble.
    while content:
        lowered = content.lstrip().lower()
        if not any(lowered.startswith(marker) for marker in _PREAMBLE_MARKERS):
            break
        idx = content.find("\n\n")
        if idx == -1:
            idx = content.find(". ")
            if idx == -1:
                return ""
            content = content[idx + 2 :].lstrip()
        else:
            content = content[idx + 2 :].lstrip()
    # Last line guard: if final paragraph still looks like English reasoning,
    # prefer Italian-detected paragraphs.
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if paragraphs:
        italian = [p for p in paragraphs if any(w in p.lower() for w in (" è ", " il ", " la ", " di ", " un ", " cluster", " normativ", " riguarda"))]
        if italian:
            content = italian[-1]
        else:
            content = paragraphs[-1]
    return content.strip()


def _build_prompt(
    community_id: str,
    member_count: int,
    top_entities: list[str],
    member_names: list[str],
) -> str:
    top = ", ".join(top_entities[:15]) if top_entities else "—"
    members = ", ".join(member_names[:20]) if member_names else "—"
    return (
        f"Cluster `{community_id}` ({member_count} entità).\n"
        f"Top entità: {top}\n"
        f"Esempi membri: {members}\n\n"
        f"Scrivi una frase di 2-3 righe in italiano che spieghi l'argomento "
        f"principale del cluster. Solo testo, nessun elenco puntato."
    )


async def _generate_one(
    pool: asyncpg.Pool,
    ollama_client: httpx.AsyncClient,
    model: str,
    semaphore: asyncio.Semaphore,
    row: asyncpg.Record,
) -> tuple[str, bool]:
    community_id = row["community_id"]
    top_entities = list(row["top_entities"] or [])
    member_count = int(row["member_count"])

    member_names = await _fetch_member_names(pool, community_id)
    prompt = _build_prompt(community_id, member_count, top_entities, member_names)

    summary: str
    ok = True
    try:
        async with semaphore:
            summary = await _call_ollama(ollama_client, model, prompt)
        if not summary or len(summary) < 40:
            raise RuntimeError(f"ollama returned too-short output: {summary!r}")
    except Exception as exc:
        logger.warning("Ollama failed for %s: %s — using fallback", community_id, exc)
        summary = _fallback_summary(community_id, top_entities, member_count)
        ok = False

    summary = summary.strip()
    if len(summary) > 2000:
        summary = summary[:2000]

    await pool.execute(
        "UPDATE kg_communities SET summary = $1, updated_at = NOW() WHERE community_id = $2",
        summary,
        community_id,
    )
    return community_id, ok


async def run(
    model: str,
    concurrency: int,
    limit: int | None,
    sample_n: int,
    min_members: int,
) -> dict[str, Any]:
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=max(4, concurrency + 1))
    # trust_env=False: macOS system proxy is configured on 127.0.0.1:8888 and
    # would intercept localhost:11434 Ollama traffic, causing ConnectError.
    ollama = httpx.AsyncClient(base_url=OLLAMA_URL, trust_env=False)

    total_to_do_row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM kg_communities "
        "WHERE (summary IS NULL OR summary = '') AND member_count >= $1",
        min_members,
    )
    total_to_do = int(total_to_do_row["n"])
    already_done_row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM kg_communities WHERE summary IS NOT NULL AND summary <> ''"
    )
    already_done = int(already_done_row["n"])
    logger.info(
        "communities: pending=%d (filter member_count>=%d), already_done=%d",
        total_to_do,
        min_members,
        already_done,
    )
    await _maybe_notify(
        f"*Community summaries* start\nmodel: `{model}`\n"
        f"pending: {total_to_do} (>= {min_members} members)\n"
        f"already: {already_done}"
    )

    semaphore = asyncio.Semaphore(concurrency)
    processed = 0
    ollama_ok = 0
    fallback = 0
    start = time.time()
    sample_rows: list[tuple[str, str]] = []
    last_telegram = 0

    try:
        while True:
            batch_limit = 256
            if limit is not None:
                remaining = limit - processed
                if remaining <= 0:
                    logger.info("Hit limit=%d, stopping", limit)
                    break
                batch_limit = min(batch_limit, remaining)

            rows = await pool.fetch(
                """
                SELECT community_id, level, member_count, top_entities
                FROM kg_communities
                WHERE (summary IS NULL OR summary = '')
                  AND member_count >= $1
                ORDER BY member_count DESC
                LIMIT $2
                """,
                min_members,
                batch_limit,
            )
            if not rows:
                break

            tasks = [_generate_one(pool, ollama, model, semaphore, r) for r in rows]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r, outcome in zip(rows, results, strict=False):
                processed += 1
                if isinstance(outcome, Exception):
                    logger.error("Task error for %s: %s", r["community_id"], outcome)
                    continue
                cid, ok = outcome
                if ok:
                    ollama_ok += 1
                else:
                    fallback += 1
                if len(sample_rows) < sample_n:
                    summary = await pool.fetchval(
                        "SELECT summary FROM kg_communities WHERE community_id = $1",
                        cid,
                    )
                    sample_rows.append((cid, summary or ""))

            if processed // PROGRESS_STEP != (processed - len(rows)) // PROGRESS_STEP:
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(
                    "progress processed=%d ollama=%d fallback=%d rate=%.1f/s elapsed=%.0fs",
                    processed,
                    ollama_ok,
                    fallback,
                    rate,
                    elapsed,
                )

            if processed - last_telegram >= TELEGRAM_STEP:
                last_telegram = processed
                await _maybe_notify(
                    f"*Community summaries* progress\n"
                    f"processed: {processed}/{total_to_do}\n"
                    f"ollama: {ollama_ok}, fallback: {fallback}\n"
                    f"elapsed: {time.time() - start:.0f}s"
                )

    finally:
        await ollama.aclose()
        await pool.close()

    elapsed = time.time() - start
    stats = {
        "processed": processed,
        "ollama_ok": ollama_ok,
        "fallback": fallback,
        "elapsed_s": round(elapsed, 1),
        "rate_per_s": round(processed / elapsed, 2) if elapsed > 0 else 0,
    }
    logger.info("DONE %s", stats)
    logger.info("Sample summaries (%d):", len(sample_rows))
    for cid, summary in sample_rows:
        logger.info("  [%s] %s", cid, summary[:200])

    await _maybe_notify(
        f"*Community summaries* DONE\n"
        f"processed: {processed}\n"
        f"ollama_ok: {ollama_ok}, fallback: {fallback}\n"
        f"elapsed: {elapsed:.0f}s"
    )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample-n", type=int, default=20)
    parser.add_argument(
        "--min-members",
        type=int,
        default=3,
        help="Skip communities with fewer members (default 3)",
    )
    args = parser.parse_args()

    stats = asyncio.run(
        run(
            model=args.model,
            concurrency=args.concurrency,
            limit=args.limit,
            sample_n=args.sample_n,
            min_members=args.min_members,
        )
    )
    print("FINAL_STATS:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
