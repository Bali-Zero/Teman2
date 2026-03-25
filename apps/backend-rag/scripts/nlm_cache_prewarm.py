"""NLM Cache Pre-warm Script.

Pre-populates the Redis cache with answers to common questions for each
NotebookLM notebook.  This eliminates cold-start latency (~50s per query)
for the most frequently asked domain questions.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/nlm_cache_prewarm.py

Options:
    --domain immigration        Only warm one domain
    --bridge-url URL            Custom NLM bridge URL (default: http://localhost:18790)
    --bridge-secret SECRET      HMAC secret (default: NLM_BRIDGE_SECRET env var)
    --delay SECONDS             Delay between queries (default: 5)
    --dry-run                   Show what would be warmed without querying
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService
from backend.utils.hmac_utils import sign_request

logger = logging.getLogger("nlm_cache_prewarm")

# ---------------------------------------------------------------------------
# Domain question bank
# ---------------------------------------------------------------------------

PREWARM_QUESTIONS: dict[str, dict[str, Any]] = {
    "immigration": {
        "notebook_id": "84375bc3-12d0-4405-a774-9b89189d8c39",
        "questions": [
            "What are the KITAS requirements for 2026?",
            "How to renew a KITAS visa?",
            "What documents are needed for a work permit (IMTA)?",
            "What is the difference between KITAS and KITAP?",
            "How long does KITAS processing take?",
            "What are the visa options for digital nomads in Bali?",
            "Requirements for investor KITAS in Indonesia",
            "How to sponsor a foreign worker in Indonesia?",
            "What is the RPTKA process?",
            "Immigration penalties for overstaying in Indonesia",
        ],
    },
    "company": {
        "notebook_id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4",
        "questions": [
            "How to set up a PT PMA in Bali?",
            "What is the minimum investment for PT PMA?",
            "KBLI codes for restaurant business in Indonesia",
            "Difference between PT PMA and PT PMDN",
            "OSS licensing process for new companies",
            "How to get NIB for a company in Indonesia?",
            "What are the requirements for foreign ownership?",
            "How to close a PT PMA company?",
            "Annual reporting requirements for PT PMA",
            "Can a foreigner own 100% of a company in Indonesia?",
        ],
    },
    "tax": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "questions": [
            "How to get NPWP in Indonesia?",
            "What are the tax obligations for PT PMA?",
            "LKPM reporting requirements and deadlines",
            "PPh 21 employee income tax rates Indonesia",
            "PPN VAT rules for businesses in Bali",
            "Coretax registration process 2026",
            "BPJS requirements for foreign workers",
            "Tax treaty benefits for foreigners in Indonesia",
            "Annual corporate tax return deadline Indonesia",
            "Withholding tax rates for foreign payments",
        ],
    },
    "property": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "questions": [
            "Can a foreigner buy property in Bali?",
            "What is Hak Pakai vs HGB in Indonesia?",
            "Leasehold vs freehold for foreign buyers",
            "Zoning regulations for villas in Bali",
            "Property ownership through PT PMA structure",
            "Land use permit requirements in Bali",
            "Building permit (IMB/PBG) process in Indonesia",
            "Best areas for property investment in Bali",
            "Tax implications of property ownership for foreigners",
            "How to do due diligence on Bali property",
        ],
    },
    "lifestyle": {
        "notebook_id": "1143b525-dd3f-40d7-a34d-2e9263b44460",
        "questions": [
            "Cost of living in Bali for expats 2026",
            "Best international schools in Bali",
            "Healthcare options for expats in Indonesia",
            "Digital nomad visa requirements Indonesia",
            "How to open a bank account as a foreigner in Bali",
        ],
    },
}


# ---------------------------------------------------------------------------
# Bridge client (standalone — no app context needed)
# ---------------------------------------------------------------------------


async def query_nlm_bridge(
    client: httpx.AsyncClient,
    bridge_url: str,
    bridge_secret: str,
    notebook_id: str,
    question: str,
    timeout: float = 60.0,
) -> dict[str, Any] | None:
    """Send a single query to the NLM bridge and return the response.

    Returns:
        Parsed JSON dict on success, or None on any failure.
    """
    payload = json.dumps(
        {"notebook_id": notebook_id, "question": question},
        separators=(",", ":"),
    )

    signature = sign_request(payload, bridge_secret)

    headers = {
        "Content-Type": "application/json",
        "X-Bridge-Signature": signature,
    }

    try:
        response = await client.post(
            f"{bridge_url}/nlm/query",
            content=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    except httpx.TimeoutException:
        logger.error("Bridge timeout for notebook=%s question=%r", notebook_id, question[:60])
        return None

    except httpx.ConnectError:
        logger.error("Bridge unreachable at %s", bridge_url)
        return None

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Bridge returned HTTP %d for notebook=%s",
            exc.response.status_code,
            notebook_id,
        )
        return None

    except Exception:
        logger.exception("Unexpected error querying NLM bridge")
        return None


# ---------------------------------------------------------------------------
# Main pre-warm logic
# ---------------------------------------------------------------------------


async def prewarm(
    domains: list[str],
    bridge_url: str,
    bridge_secret: str,
    delay: float,
    dry_run: bool,
) -> dict[str, int]:
    """Run the pre-warm loop for the specified domains.

    Returns:
        Summary dict with cached/skipped/failed/total counts.
    """
    stats = {"cached": 0, "skipped": 0, "failed": 0, "total": 0}

    # Initialize Redis first (required for cache service)
    from backend.core.redis_manager import RedisManager
    manager = RedisManager.get_instance()
    manager.initialize()
    logger.info("Redis available: %s", manager.available)

    # Initialize cache service
    cache = NotebookLMCacheService()
    await cache.initialize()

    if not dry_run and cache.redis_client is None:
        logger.error("Redis not available — cannot pre-warm cache. Exiting.")
        return stats

    async with httpx.AsyncClient() as client:
        for domain in domains:
            config = PREWARM_QUESTIONS[domain]
            notebook_id: str = config["notebook_id"]
            questions: list[str] = config["questions"]

            logger.info(
                "=== Domain: %s (%d questions, notebook=%s) ===",
                domain,
                len(questions),
                notebook_id,
            )

            for idx, question in enumerate(questions, start=1):
                stats["total"] += 1

                if dry_run:
                    logger.info(
                        "[%s] Q%d/%d: %r  [DRY RUN — would query]",
                        domain,
                        idx,
                        len(questions),
                        question,
                    )
                    stats["skipped"] += 1
                    continue

                # Check if already cached
                existing = await cache.get(question, notebook_id=notebook_id)
                if existing is not None:
                    logger.info(
                        "[%s] Q%d/%d: %r  -> ALREADY CACHED (%d chars)",
                        domain,
                        idx,
                        len(questions),
                        question,
                        len(existing.get("answer", "")),
                    )
                    stats["skipped"] += 1
                    continue

                # Query bridge
                t0 = time.monotonic()
                result = await query_nlm_bridge(
                    client=client,
                    bridge_url=bridge_url,
                    bridge_secret=bridge_secret,
                    notebook_id=notebook_id,
                    question=question,
                )
                elapsed = time.monotonic() - t0

                if result is None:
                    logger.warning(
                        "[%s] Q%d/%d: %r  -> FAILED (%.1fs)",
                        domain,
                        idx,
                        len(questions),
                        question,
                        elapsed,
                    )
                    stats["failed"] += 1
                else:
                    answer = result.get("answer", "")
                    citations = result.get("citations", [])
                    metadata = {
                        "domain": domain,
                        "notebook_id": notebook_id,
                        "source": "prewarm",
                        "citations": citations,
                    }

                    success = await cache.set(
                        question=question,
                        answer=answer,
                        metadata=metadata,
                        notebook_id=notebook_id,
                    )

                    if success:
                        logger.info(
                            "[%s] Q%d/%d: %r  -> %d chars, %.1fs",
                            domain,
                            idx,
                            len(questions),
                            question,
                            len(answer),
                            elapsed,
                        )
                        stats["cached"] += 1
                    else:
                        logger.warning(
                            "[%s] Q%d/%d: %r  -> CACHE WRITE FAILED (%.1fs)",
                            domain,
                            idx,
                            len(questions),
                            question,
                            elapsed,
                        )
                        stats["failed"] += 1

                # Rate-limit between queries to respect Google limits
                if idx < len(questions):
                    logger.debug("Sleeping %.1fs before next query...", delay)
                    await asyncio.sleep(delay)

    await cache.close()
    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pre-warm the NLM Redis cache with common domain questions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  PYTHONPATH=. python scripts/nlm_cache_prewarm.py --dry-run\n"
            "  PYTHONPATH=. python scripts/nlm_cache_prewarm.py --domain immigration\n"
            "  PYTHONPATH=. python scripts/nlm_cache_prewarm.py --bridge-url http://localhost:18790\n"
        ),
    )
    parser.add_argument(
        "--domain",
        choices=list(PREWARM_QUESTIONS.keys()),
        default=None,
        help="Only warm a single domain (default: all domains)",
    )
    parser.add_argument(
        "--bridge-url",
        default=os.getenv("NLM_BRIDGE_URL", "http://localhost:18790"),
        help="NLM bridge URL (default: $NLM_BRIDGE_URL or http://localhost:18790)",
    )
    parser.add_argument(
        "--bridge-secret",
        default=os.getenv("NLM_BRIDGE_SECRET", ""),
        help="HMAC bridge secret (default: $NLM_BRIDGE_SECRET env var)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds between queries to respect rate limits (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be warmed without actually querying the bridge",
    )
    return parser.parse_args()


async def main() -> None:
    """Entry point."""
    args = parse_args()

    # Determine which domains to warm
    if args.domain:
        domains = [args.domain]
    else:
        domains = list(PREWARM_QUESTIONS.keys())

    total_questions = sum(len(PREWARM_QUESTIONS[d]["questions"]) for d in domains)

    logger.info("NLM Cache Pre-warm")
    logger.info("  Domains:    %s", ", ".join(domains))
    logger.info("  Questions:  %d", total_questions)
    logger.info("  Bridge URL: %s", args.bridge_url)
    logger.info("  Delay:      %.1fs", args.delay)
    logger.info("  Dry run:    %s", args.dry_run)
    if not args.dry_run:
        est_minutes = (total_questions * (50 + args.delay)) / 60
        logger.info("  Est. time:  ~%.0f minutes", est_minutes)
    logger.info("")

    t_start = time.monotonic()
    stats = await prewarm(
        domains=domains,
        bridge_url=args.bridge_url,
        bridge_secret=args.bridge_secret,
        delay=args.delay,
        dry_run=args.dry_run,
    )
    t_total = time.monotonic() - t_start

    # Summary
    logger.info("")
    logger.info("=== Pre-warm Summary ===")
    logger.info("  Total:   %d questions", stats["total"])
    logger.info("  Cached:  %d (new)", stats["cached"])
    logger.info("  Skipped: %d (already cached or dry-run)", stats["skipped"])
    logger.info("  Failed:  %d", stats["failed"])
    logger.info("  Time:    %.1fs (%.1f min)", t_total, t_total / 60)
    logger.info("========================")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
