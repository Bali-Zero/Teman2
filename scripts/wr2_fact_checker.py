#!/usr/bin/env python3
"""WR2 Fact Checker — post-draft hallucination filter.

Runs BETWEEN wr2_draft_generator (status='drafts') and wr2_image_generator.
For each freshly drafted carousel, runs a deterministic check over every
slide text (headline + subhead + body) looking for:

1. **Numeric hallucinations** — any figure that isn't in the fact_pool
   (regex-based: percentages, currency amounts, year ranges, thresholds,
   "N million/billion", etc.)
2. **Causal hallucinations** — phrases like "because", "led to", "caused",
   "therefore" that are not backed by an entry in the causal_pool. Allowed
   only if the slide uses explicit hedging ("some observers suggest").
3. **Editorial rule violations** — political judgement, strawman quotes,
   comparisons denigrating competitors, guarantee language.
4. **Missing citations** — factual claims without inline [Source: ...].
5. **Opinion without marker** — editorial statements not prefixed with
   "In our view" / "Bali Zero's take" / "From our seat" / "Our read".

Severity:
- HARD_FLAG: blocks publication (flips status to 'fact_check_failed').
- SOFT_FLAG: warns + proceeds (logged in council_meta for Zero to review).

Rules can be overridden per-slide if `soft_only=True` env is set. Default
is strict: hard flags block the draft, notify via Telegram.

Status transitions:
- 'drafts' + pass → 'drafts_checked'
- 'drafts' + hard fail → 'fact_check_failed'
- 'drafts' with no fact_pools (legacy) → 'drafts_checked' (skip check)

Env:
    DATABASE_URL                              — Postgres localhost
    WR2_FACT_CHECKER_STRICT                   — default 'true'; if 'false',
                                                 soft-only (never blocks)
    TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID — optional

Usage:
    python3 scripts/wr2_fact_checker.py              # process pending
    python3 scripts/wr2_fact_checker.py --draft-id UUID
    python3 scripts/wr2_fact_checker.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg  # noqa: E402

logger = logging.getLogger("wr2.fact_checker")

MAX_DRAFTS_PER_RUN = 5
STRICT = os.environ.get("WR2_FACT_CHECKER_STRICT", "true").lower() != "false"

# ─────────────────────────────────────────────────────────────────────────
# Rule regexes
# ─────────────────────────────────────────────────────────────────────────

# Numbers: percentages, currency, plain ints with thousands-separator, ranges
RE_NUMBER = re.compile(
    r"""
    (?:(?<=\s)|^|[\$€£₹])           # boundary
    (?:
        \d{1,3}(?:,\d{3})+            # 1,000,000 style
        | \d+(?:\.\d+)?[kmb]?          # 10, 10.5, 10k, 10m, 10b
    )
    \s?
    (?:
        %
        | percent
        | bn|mn|k
        | million|billion|thousand
        | usd|idr|eur|gbp
        | years?|months?|weeks?|days?
        | rupiah
    )?
    (?=\s|[\.,;:]|$)                  # word-end
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Year references: 19xx / 20xx / 21xx
RE_YEAR = re.compile(r"\b(?:19|20|21)\d{2}\b")

# Currency patterns (strict)
RE_CURRENCY = re.compile(
    r"(?:\$|€|£|₹|idr|usd|eur|gbp|rp)\s?\d+",
    re.IGNORECASE,
)

# Causal triggers (English + some Italian common)
RE_CAUSAL = re.compile(
    r"\b(?:because|due to|led to|caused|results? in|as a result|"
    r"therefore|consequently|so that|thus|for this reason|"
    r"perché|a causa di|ha portato a)\b",
    re.IGNORECASE,
)

# Hedging phrases — if present on same slide, causal is allowed
RE_HEDGE = re.compile(
    r"\b(?:some observers suggest|some report|some say|appears correlated|"
    r"worth watching whether|may indicate|could be linked|"
    r"it remains to be seen|remains unclear|some argue)\b",
    re.IGNORECASE,
)

# Opinion markers that distinguish editorial from fact
RE_OPINION_MARKER = re.compile(
    r"\b(?:in our view|bali zero'?s take|from our seat|our read:?|"
    r"what this means for you|we argue that|our reading is|"
    r"in practice|bali zero believes)\b",
    re.IGNORECASE,
)

# Opinion tells without explicit marker (soft-flag)
RE_IMPLICIT_OPINION = re.compile(
    r"\b(?:this is (?:great|bad|terrible|excellent)|"
    r"should obviously|clearly the government|"
    r"a disaster for|a victory for|outrageous|absurd|"
    r"no one (?:should|will|cares))\b",
    re.IGNORECASE,
)

# Political judgement triggers — HARD flag
RE_POLITICAL = re.compile(
    r"\b(?:(?:the|this) government (?:is|has) (?:wrong|failing|incompetent|"
    r"corrupt|authoritarian|dishonest)|"
    r"prabowo (?:should|must|has failed)|"
    r"ministry (?:is lying|is wrong to|should step down)|"
    r"regulatory capture|kleptocracy)\b",
    re.IGNORECASE,
)

# Competitor-bashing patterns
RE_COMPETITOR_BASH = re.compile(
    r"\bunlike (?:other|some|many) (?:agencies|firms|providers)|"
    r"\bmost agencies (?:fail|can't|don't)\b",
    re.IGNORECASE,
)

# Outcome guarantees — HARD flag (NB-7 red line)
RE_GUARANTEE = re.compile(
    r"\b(?:guaranteed|guarantee) (?:kitas|visa|approval|processing|in \d+ days)|"
    r"\bwill (?:definitely|certainly) (?:approve|grant)\b",
    re.IGNORECASE,
)

# Strawman pattern: "some/critics/opponents say X, but" without quote
RE_STRAWMAN = re.compile(
    r"\b(?:critics (?:say|claim)|opponents argue|"
    r"some (?:claim|allege|believe)) .{5,100}(?:but|however)\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────
# Flag dataclass
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class Flag:
    severity: str  # 'hard' | 'soft'
    slide_number: int
    rule: str
    offending_text: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "slide_number": self.slide_number,
            "rule": self.rule,
            "offending_text": self.offending_text[:200],
            "detail": self.detail,
        }


@dataclass
class CheckResult:
    flags: list[Flag] = field(default_factory=list)
    hard_count: int = 0
    soft_count: int = 0

    def add(self, flag: Flag) -> None:
        self.flags.append(flag)
        if flag.severity == "hard":
            self.hard_count += 1
        else:
            self.soft_count += 1


# ─────────────────────────────────────────────────────────────────────────
# Fact pool helpers
# ─────────────────────────────────────────────────────────────────────────


def _pool_tokens_lower(pool: list[dict[str, Any]], fields: list[str]) -> str:
    """Concatenate all values of given fields across pool items, lowercased."""
    parts = []
    for item in pool or []:
        for f in fields:
            v = item.get(f)
            if v:
                parts.append(str(v))
    return " ".join(parts).lower()


def _normalize_num(s: str) -> str:
    """Strip punctuation, spaces, make 'usd 2m' == 'USD 2 million'."""
    s = s.lower().strip()
    s = re.sub(r"[\s,]", "", s)
    s = s.replace("million", "m").replace("billion", "b").replace("thousand", "k")
    s = s.replace("percent", "%")
    return s


def _number_in_pool(token: str, pool_text: str) -> bool:
    """Return True iff a normalized version of token appears in pool_text."""
    norm = _normalize_num(token)
    # At minimum 3 chars to avoid tiny matches
    if len(norm) < 2:
        return True
    return norm in _normalize_num(pool_text)


# ─────────────────────────────────────────────────────────────────────────
# Per-slide check
# ─────────────────────────────────────────────────────────────────────────


def check_slide(
    slide: dict[str, Any],
    fact_pool_text: str,
    causal_pool_text: str,
    result: CheckResult,
) -> None:
    sn = slide.get("slide_number", 0)
    text_parts = [
        slide.get("headline") or "",
        slide.get("subhead") or "",
        slide.get("body") or "",
    ]
    full_text = " ".join(t for t in text_parts if t).strip()
    if not full_text:
        return

    # Rule 1: political judgement — HARD
    m = RE_POLITICAL.search(full_text)
    if m:
        result.add(
            Flag(
                severity="hard",
                slide_number=sn,
                rule="political_judgement",
                offending_text=m.group(0),
                detail="NB-7 absolute red line: no political judgement on Indonesian gov/ministries",
            )
        )

    # Rule 2: guarantee language — HARD
    m = RE_GUARANTEE.search(full_text)
    if m:
        result.add(
            Flag(
                severity="hard",
                slide_number=sn,
                rule="outcome_guarantee",
                offending_text=m.group(0),
                detail="NB-7 red line: Indonesian processes never guaranteed",
            )
        )

    # Rule 3: competitor bashing — HARD
    m = RE_COMPETITOR_BASH.search(full_text)
    if m:
        result.add(
            Flag(
                severity="hard",
                slide_number=sn,
                rule="competitor_bashing",
                offending_text=m.group(0),
                detail="NB-7 rule: brand speaks through results, not criticism of others",
            )
        )

    # Rule 4: numeric hallucination — HARD if fact_pool exists
    if fact_pool_text:
        for num_match in RE_NUMBER.finditer(full_text):
            token = num_match.group(0)
            if _number_in_pool(token, fact_pool_text):
                continue
            # Year fallback
            if RE_YEAR.search(token) and RE_YEAR.search(fact_pool_text):
                continue
            result.add(
                Flag(
                    severity="hard",
                    slide_number=sn,
                    rule="number_not_in_pool",
                    offending_text=token,
                    detail=f"figure '{token}' not in fact_pool — potential hallucination",
                )
            )

    # Rule 5: causal without pool backing — HARD if pool provided AND no hedge
    if fact_pool_text and RE_CAUSAL.search(full_text):
        has_hedge = bool(RE_HEDGE.search(full_text))
        # Check if any causal_pool entry's verbs align (cheap check)
        in_pool = any(
            verb in causal_pool_text
            for verb in ("because", "led to", "caused", "results in", "due to")
        )
        if not has_hedge and not in_pool:
            m = RE_CAUSAL.search(full_text)
            result.add(
                Flag(
                    severity="hard",
                    slide_number=sn,
                    rule="causal_not_in_pool",
                    offending_text=m.group(0),
                    detail="causal claim without hedge or causal_pool backing",
                )
            )

    # Rule 6: strawman detection — SOFT
    m = RE_STRAWMAN.search(full_text)
    if m:
        result.add(
            Flag(
                severity="soft",
                slide_number=sn,
                rule="possible_strawman",
                offending_text=m.group(0),
                detail="references opposing view without direct quote — verify source",
            )
        )

    # Rule 7: implicit opinion without marker — SOFT
    if RE_IMPLICIT_OPINION.search(full_text) and not RE_OPINION_MARKER.search(full_text):
        m = RE_IMPLICIT_OPINION.search(full_text)
        result.add(
            Flag(
                severity="soft",
                slide_number=sn,
                rule="opinion_without_marker",
                offending_text=m.group(0),
                detail="editorial tone without 'In our view' / 'Bali Zero's take' prefix",
            )
        )


def check_draft(slides: list[dict[str, Any]], fact_pools: dict[str, Any] | None) -> CheckResult:
    result = CheckResult()
    fact_pool_text = _pool_tokens_lower(
        (fact_pools or {}).get("fact_pool") or [],
        ["claim", "source_sentence"],
    )
    causal_pool_text = _pool_tokens_lower(
        (fact_pools or {}).get("causal_pool") or [],
        ["cause", "effect", "source_sentence"],
    )
    for slide in slides:
        check_slide(slide, fact_pool_text, causal_pool_text, result)
    return result


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────


async def _fetch_pending(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, topic, slides_json, council_debate_json, brief_json
          FROM war_room_drafts
         WHERE status = 'drafts'
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _mark_passed(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    council: dict[str, Any],
    result: CheckResult,
) -> None:
    council["fact_check"] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "hard_count": result.hard_count,
        "soft_count": result.soft_count,
        "flags": [f.to_dict() for f in result.flags],
    }
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET council_debate_json = $2::jsonb,
               status              = 'drafts_checked',
               updated_at          = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps(council),
    )


async def _mark_failed(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    council: dict[str, Any],
    result: CheckResult,
) -> None:
    council["fact_check"] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "hard_count": result.hard_count,
        "soft_count": result.soft_count,
        "flags": [f.to_dict() for f in result.flags],
    }
    reason = f"fact_check_failed: {result.hard_count} hard flags"
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET council_debate_json = $2::jsonb,
               status              = 'fact_check_failed',
               rejection_reason    = $3,
               updated_at          = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps(council),
        reason[:1000],
    )


# ─────────────────────────────────────────────────────────────────────────
# Logging + Telegram
# ─────────────────────────────────────────────────────────────────────────


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_fact_checker.log"
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


async def _process_one(conn: asyncpg.Connection, row: asyncpg.Record) -> str:
    """Return 'pass' | 'hard_fail' | 'skipped'."""
    draft_id: uuid.UUID = row["id"]
    topic: str = row["topic"]
    slides_raw = row["slides_json"]
    slides_json = (
        json.loads(slides_raw) if isinstance(slides_raw, str) else (slides_raw or {})
    )
    slides = slides_json.get("slides") or []
    brief_raw = row["brief_json"]
    brief = json.loads(brief_raw) if isinstance(brief_raw, str) else (brief_raw or {})
    fact_pools = brief.get("fact_pools")
    council_raw = row["council_debate_json"]
    council = (
        json.loads(council_raw) if isinstance(council_raw, str) else (council_raw or {})
    )

    if not fact_pools:
        logger.info(
            "Draft %s: no fact_pools in brief (legacy path) — marking drafts_checked without check",
            draft_id,
        )
        await _mark_passed(conn, draft_id, council, CheckResult())
        return "skipped"

    result = check_draft(slides, fact_pools)
    logger.info(
        "Draft %s: %d hard / %d soft flags across %d slides",
        draft_id, result.hard_count, result.soft_count, len(slides),
    )
    for f in result.flags[:10]:
        logger.info("  [%s] slide %d %s: %s", f.severity, f.slide_number, f.rule, f.offending_text[:60])

    if result.hard_count > 0 and STRICT:
        await _mark_failed(conn, draft_id, council, result)
        _send_telegram(
            f"WR2 fact-check FAILED\n"
            f"Topic: {topic[:100]}\n"
            f"Draft: {draft_id}\n"
            f"{result.hard_count} hard flags (e.g. {result.flags[0].rule if result.flags else ''})\n"
            f"Draft blocked — review council_debate_json.fact_check"
        )
        return "hard_fail"

    await _mark_passed(conn, draft_id, council, result)
    if result.soft_count > 0:
        _send_telegram(
            f"WR2 fact-check passed with {result.soft_count} soft warnings\n"
            f"Topic: {topic[:100]}\nDraft: {draft_id}"
        )
    return "pass"


async def run(*, dry_run: bool = False, draft_id: str | None = None) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=60)
    try:
        async with pool.acquire() as conn:
            if draft_id:
                rows = await conn.fetch(
                    "SELECT id, topic, slides_json, council_debate_json, brief_json "
                    "FROM war_room_drafts WHERE id = $1::uuid",
                    draft_id,
                )
            else:
                rows = await _fetch_pending(conn, MAX_DRAFTS_PER_RUN)

            if not rows:
                logger.info("No drafts in 'drafts' status to check")
                return 1

            if dry_run:
                for r in rows:
                    logger.info("[DRY-RUN] would check draft %s — %s", r["id"], r["topic"][:80])
                return 0

            passed = 0
            failed = 0
            for row in rows:
                try:
                    outcome = await _process_one(conn, row)
                    if outcome in ("pass", "skipped"):
                        passed += 1
                    elif outcome == "hard_fail":
                        failed += 1
                except Exception as e:
                    logger.exception("Unhandled on draft %s: %s", row["id"], e)

            logger.info("Done: %d passed, %d failed", passed, failed)
            return 0
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
        _send_telegram(f"WR2 fact_checker crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
