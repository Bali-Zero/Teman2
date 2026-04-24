#!/usr/bin/env python3
"""WR2 Fact Extractor — builds the fact_pool + causal_pool from the article.

Runs BETWEEN wr2_topic_selector (status='briefed') and wr2_draft_generator.
For each briefed draft, calls Claude Haiku (OAuth) with temperature 0.0 to
extract a structured list of verifiable claims from the article summary:

- fact_pool:   [{claim, source_sentence, category}] — factual statements
               with numbers, dates, percentages, or named entities
- causal_pool: [{cause, effect, source_sentence}] — explicit causal claims
               "X led to Y" / "because X, Y" / "due to X"
- quotes_pool: [{speaker, quote, source_sentence}] — attributed statements

These pools are then used by:
- wr2_draft_generator: as the "allowed fact pool" passed to Claude Opus,
  reducing hallucination surface
- wr2_fact_checker (post-draft): to verify every numeric/causal/attributed
  claim in the final slides can be traced back to a source sentence

Status transition: briefed → briefed_facted (new), on failure → rejected.
If disabled via env WR2_FACT_EXTRACTOR_ENABLED=false, draft_generator will
accept 'briefed' as fallback (backwards compatibility).

Env:
    DATABASE_URL                              — Postgres localhost
    CLAUDE_CODE_OAUTH_TOKEN[_{BACKUP,CRON}]   — Claude Max plan
    WR2_FACT_EXTRACTOR_ENABLED                — default 'true'
    TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID — optional

Usage:
    python3 scripts/wr2_fact_extractor.py              # process pending
    python3 scripts/wr2_fact_extractor.py --draft-id UUID
    python3 scripts/wr2_fact_extractor.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.llm.claude_oauth_client import (  # noqa: E402
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

logger = logging.getLogger("wr2.fact_extractor")

MAX_DRAFTS_PER_RUN = 2
ENABLED = os.environ.get("WR2_FACT_EXTRACTOR_ENABLED", "true").lower() != "false"

# ─────────────────────────────────────────────────────────────────────────
# Claude extractor prompt — deterministic (temp 0.0 equivalent)
# ─────────────────────────────────────────────────────────────────────────

SYSTEM_EXTRACT = """You are a STRICT FACT EXTRACTOR. Your output must be:

1. deterministic — no interpretation, no editorial, no paraphrasing
2. traceable — every claim cites the verbatim source sentence that contains it
3. exhaustive on numeric/causal/attributed claims — these are the ones that
   get hallucinated by downstream LLMs, so they must be captured here

EXTRACT FROM THE ARTICLE BELOW:

A) fact_pool — factual statements with at least one of:
   - a number, percentage, date, year, monetary amount, threshold
   - a named entity (law reference: UU/PP/PMK, company, agency, city)
   - a concrete procedure step or requirement
   For each: {claim, source_sentence (verbatim), category}
   Categories: "regulation" | "number" | "entity" | "procedure" | "date"

B) causal_pool — EXPLICIT causal claims present in the text:
   Triggers: "because", "due to", "led to", "caused", "resulted in",
             "as a result of", "so that", "therefore", "consequently".
   For each: {cause, effect, source_sentence (verbatim)}
   If the article does NOT explicitly claim causality, return [].
   DO NOT infer causality — only extract what's textually present.

C) quotes_pool — attributed statements (anyone said X):
   Direct quotes OR clear paraphrases attributed to a named source.
   For each: {speaker, quote, source_sentence (verbatim)}
   Speaker must be named in the source. If anonymous ("officials said"),
   still include but mark speaker as "unnamed_official".

HARD RULES:
- source_sentence MUST be verbatim substring of the article
- If you're not sure a claim is in the article, DO NOT include it
- Empty arrays are fine — better empty than fabricated
- OUTPUT VALID JSON ONLY, no text outside the JSON object, no markdown fences
"""


def _build_prompt(topic: str, summary: str, source_url: str) -> str:
    return f"""{SYSTEM_EXTRACT}

---

ARTICLE TITLE: {topic}
ARTICLE URL: {source_url or "n/a"}

ARTICLE BODY (verbatim):
{summary[:4000]}

---

Output JSON now:
{{
  "fact_pool": [...],
  "causal_pool": [...],
  "quotes_pool": [...]
}}
"""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_BLOCK_RE.search(text)
    if m:
        text = m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


# ─────────────────────────────────────────────────────────────────────────
# Validation: every source_sentence must be a substring of summary
# ─────────────────────────────────────────────────────────────────────────


def _normalise_text(s: str) -> str:
    """Lower-case + collapse whitespace for lenient substring match."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def _validate_sourcing(pools: dict[str, Any], summary: str) -> tuple[dict, list[str]]:
    """Drop entries whose source_sentence is not verbatim in summary.

    Returns (cleaned_pools, warnings).
    """
    warnings: list[str] = []
    norm_summary = _normalise_text(summary)
    cleaned: dict[str, list] = {"fact_pool": [], "causal_pool": [], "quotes_pool": []}

    for pool_name in cleaned:
        raw_items = pools.get(pool_name) or []
        for i, item in enumerate(raw_items):
            ss = (item.get("source_sentence") or "").strip()
            if not ss or len(ss) < 10:
                warnings.append(f"{pool_name}[{i}] missing/too-short source_sentence")
                continue
            if _normalise_text(ss) in norm_summary:
                cleaned[pool_name].append(item)
            else:
                # Try a more lenient match: first 40 chars present?
                head = _normalise_text(ss)[:40]
                if head and head in norm_summary:
                    cleaned[pool_name].append(item)
                else:
                    warnings.append(
                        f"{pool_name}[{i}] source_sentence not found in article — dropped"
                    )
    return cleaned, warnings


# ─────────────────────────────────────────────────────────────────────────
# Claude call
# ─────────────────────────────────────────────────────────────────────────


async def extract_facts(topic: str, summary: str, source_url: str) -> dict[str, Any]:
    prompt = _build_prompt(topic, summary, source_url)
    logger.info("Calling Claude Haiku for fact extraction (prompt %d chars)", len(prompt))
    t0 = time.perf_counter()
    resp = await complete_async(
        prompt,
        model="claude-haiku-4-5-20251001",
        timeout_s=120,
        endpoint="wr2_fact_extractor",
    )
    dt = time.perf_counter() - t0
    logger.info("Claude responded in %.1fs (token=%s)", dt, resp.token_label)
    parsed = _extract_json(resp.text)
    cleaned, warnings = _validate_sourcing(parsed, summary)
    for w in warnings[:5]:
        logger.warning("sourcing: %s", w)
    if len(warnings) > 5:
        logger.warning("...and %d more sourcing warnings", len(warnings) - 5)
    return {
        "fact_pool": cleaned["fact_pool"],
        "causal_pool": cleaned["causal_pool"],
        "quotes_pool": cleaned["quotes_pool"],
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "sourcing_warnings_count": len(warnings),
    }


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────


async def _fetch_briefed(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, topic, brief_json
          FROM war_room_drafts
         WHERE status = 'briefed'
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _persist_facted(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    brief_json: dict[str, Any],
    pools: dict[str, Any],
) -> None:
    # Attach pools into brief_json under a dedicated key
    brief_json["fact_pools"] = pools
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET brief_json = $2::jsonb,
               status     = 'briefed_facted',
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps(brief_json),
    )


async def _mark_rejected(conn: asyncpg.Connection, draft_id: uuid.UUID, reason: str) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status           = 'rejected',
               rejection_reason = $2,
               updated_at       = NOW()
         WHERE id = $1
        """,
        draft_id,
        reason[:1000],
    )


# ─────────────────────────────────────────────────────────────────────────
# Logging + Telegram (shared pattern)
# ─────────────────────────────────────────────────────────────────────────


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_fact_extractor.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────


async def _process_one(conn: asyncpg.Connection, row: asyncpg.Record) -> bool:
    draft_id: uuid.UUID = row["id"]
    topic: str = row["topic"]
    brief_raw = row["brief_json"]
    brief = json.loads(brief_raw) if isinstance(brief_raw, str) else (brief_raw or {})
    summary = brief.get("article_summary") or ""
    source_url = brief.get("source_url") or ""

    if not summary or len(summary) < 100:
        logger.warning("Draft %s summary too short (%d chars) — skipping", draft_id, len(summary))
        await _mark_rejected(conn, draft_id, "summary_too_short_for_extraction")
        return False

    logger.info("─── draft %s ─── topic=%r", draft_id, topic[:80])

    try:
        pools = await extract_facts(topic=topic, summary=summary, source_url=source_url)
    except (ClaudeOAuthError, ClaudeOAuthNotAvailable) as e:
        logger.error("Claude OAuth failed: %s", e)
        await _mark_rejected(conn, draft_id, f"fact_extractor_claude_failed: {e}")
        _send_telegram(f"WR2 fact_extractor Claude failed\n{draft_id}\n{str(e)[:200]}")
        return False
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Parse failed: %s", e)
        await _mark_rejected(conn, draft_id, f"fact_extractor_parse: {e}")
        return False

    f_n = len(pools["fact_pool"])
    c_n = len(pools["causal_pool"])
    q_n = len(pools["quotes_pool"])
    logger.info(
        "Draft %s extracted: %d facts / %d causal / %d quotes",
        draft_id, f_n, c_n, q_n,
    )

    await _persist_facted(conn, draft_id, brief, pools)
    logger.info("Draft %s → status=briefed_facted", draft_id)
    return True


async def run(*, dry_run: bool = False, draft_id: str | None = None) -> int:
    if not ENABLED:
        logger.info("WR2_FACT_EXTRACTOR_ENABLED=false — nothing to do")
        return 1

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=240)
    try:
        async with pool.acquire() as conn:
            if draft_id:
                rows = await conn.fetch(
                    "SELECT id, topic, brief_json FROM war_room_drafts WHERE id=$1::uuid",
                    draft_id,
                )
            else:
                rows = await _fetch_briefed(conn, MAX_DRAFTS_PER_RUN)

            if not rows:
                logger.info("No briefed drafts to process")
                return 1

            if dry_run:
                for r in rows:
                    logger.info("[DRY-RUN] would extract: %s %s", r["id"], r["topic"][:80])
                return 0

            ok_count = 0
            for row in rows:
                try:
                    if await _process_one(conn, row):
                        ok_count += 1
                except Exception as e:
                    logger.exception("Unhandled on draft %s: %s", row["id"], e)
                    try:
                        await _mark_rejected(conn, row["id"], f"unhandled: {e}")
                    except Exception:
                        pass

            logger.info("Done: %d/%d drafts facted", ok_count, len(rows))
            return 0 if ok_count > 0 else 2
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--draft-id", help="Process a specific draft UUID")
    args = parser.parse_args()

    _configure_logging()
    try:
        return asyncio.run(run(dry_run=args.dry_run, draft_id=args.draft_id))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        _send_telegram(f"WR2 fact_extractor crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
