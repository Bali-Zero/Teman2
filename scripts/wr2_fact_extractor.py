#!/usr/bin/env python3
"""WR2 Fact Extractor — Sprint B B-bis (2026-05-08).

Reads `war_room_drafts` rows in status='drafts_imaged' and, for each
slide body, asks Claude OPUS (via OAuth subprocess) to extract the
factual claims that need verification. Saves the result in
`fact_check_json.claims` and advances status to `drafts_imaged_facted`.

This is a NET-NEW build — the original scripts/wr2_fact_extractor.py
was never written; only the launchd plist was registered (and disabled
2026-05-07 in PR #299). The supervisor's TRANSITIONS map references
this stage but the stop-gap routed `drafts_imaged → canva-apply`
directly. This PR restores the full chain.

Flow per draft
    1. Fetch (id, topic, register, slides_json) WHERE
       status='drafts_imaged' AND fact_check_json IS NULL.
    2. For each slide, build an OPUS prompt that asks for a JSON list
       of claims (text, slide_index, type ∈ {number, date, law, quote,
       other}).
    3. Validate the JSON against `_ClaimsResult` (pydantic) — retry once
       on schema fail.
    4. UPDATE war_room_drafts SET fact_check_json=$json,
       status='drafts_imaged_facted', updated_at=NOW().
    5. Telegram-alert per draft on success and on persistent extractor
       error (3-attempt cap).

Kill switch
    `system_settings.wr2_fact_extractor_enabled` must be 'true'.

Env
    DATABASE_URL                    Fly Postgres tunnel (port 15432)
    TELEGRAM_BOT_TOKEN              optional
    TELEGRAM_OWNER_CHAT_ID          optional
    WR2_FACT_EXTRACTOR_BATCH        max drafts per run (default 3)
    WR2_FACT_EXTRACTOR_MODEL        Claude model (default claude-opus-4-7)
    WR2_FACT_EXTRACTOR_TIMEOUT_S    per-slide subprocess timeout (default 180)

Anthropic invariant (OB-3)
    Calls go through `backend.llm.claude_oauth_client.complete_async`
    which spawns the `claude` CLI with CLAUDE_CODE_OAUTH_TOKEN — never
    ANTHROPIC_API_KEY, never the SDK. See project CLAUDE.md Golden Rule.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# Make backend-rag importable when run from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.llm.claude_oauth_client import (  # noqa: E402
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

logger = logging.getLogger("wr2.fact_extractor")

# Tunables
MAX_DRAFTS_PER_RUN = int(os.environ.get("WR2_FACT_EXTRACTOR_BATCH", "3"))
DEFAULT_MODEL = os.environ.get("WR2_FACT_EXTRACTOR_MODEL", "claude-opus-4-7")
DEFAULT_TIMEOUT_S = int(os.environ.get("WR2_FACT_EXTRACTOR_TIMEOUT_S", "180"))
TELEMETRY_PATH = Path.home() / "logs" / "wr2_fact_extractor_telemetry.jsonl"

# Allowed claim types — JSON validation guard.
ALLOWED_CLAIM_TYPES = ("number", "date", "law", "quote", "other")


# ─────────────────────────────────────────────────────────────────────────
# Logging + Telegram
# ─────────────────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    fh = logging.FileHandler(str(log_dir / "wr2_fact_extractor.log"))
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", e)


def _log_telemetry(record: dict) -> None:
    """Append-only JSONL. Never raises."""
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.warning("telemetry write failed (non-fatal): %s", e)


# ─────────────────────────────────────────────────────────────────────────
# Prompt + parser
# ─────────────────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are a fact-extraction assistant for the Bali Zero War Room pipeline.
For the slide body below, extract every factual claim that should be
verified before publication. Focus on:

- numbers (deadlines, fees, percentages, statistics)
- dates (specific dates, years, deadlines)
- laws (regulation/decree references like "PP 28/2025", "PMK 81/2024")
- quotes (direct attributions to people or institutions)
- other (named entities, locations, organisations) — only if unambiguously checkable

Topic: {topic}
Register: {register}
Slide index: {slide_index}
Slide title: {title}
Slide body:
\"\"\"{body}\"\"\"

Return ONE JSON object on its own line, with this exact shape:

{{
  "claims": [
    {{"claim": "<verbatim text or paraphrase ≤150 chars>",
      "slide_index": {slide_index},
      "type": "number|date|law|quote|other",
      "context": "<where it appears, ≤80 chars>"}}
  ]
}}

If the slide has zero verifiable claims, return: {{"claims": []}}

Output ONLY the JSON object — no markdown fences, no prose.
"""


def _parse_claims_json(raw: str, slide_index: int) -> list[dict[str, Any]] | None:
    """Extract `{"claims": [...]}` from a model response.

    Tolerates markdown fences (`json ... `) and leading/trailing prose.
    Returns None on parse failure so the caller can retry.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    if text.startswith("```"):
        # Drop the first line and the last fence.
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Find the first { ... } block.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    claims = obj.get("claims")
    if not isinstance(claims, list):
        return None
    # Filter + normalise per claim.
    cleaned: list[dict[str, Any]] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        claim_text = str(c.get("claim", "")).strip()
        if not claim_text:
            continue
        ctype = str(c.get("type", "other")).strip().lower()
        if ctype not in ALLOWED_CLAIM_TYPES:
            ctype = "other"
        ci = c.get("slide_index", slide_index)
        try:
            ci_int = int(ci)
        except (TypeError, ValueError):
            ci_int = slide_index
        ctx = str(c.get("context", ""))[:120]
        cleaned.append(
            {
                "claim": claim_text[:200],
                "slide_index": ci_int,
                "type": ctype,
                "context": ctx,
            }
        )
    return cleaned


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────

async def _kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    val = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_fact_extractor_enabled'"
    )
    return val == "true"


async def _fetch_ready_drafts(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    """Drafts that finished image-generation and have NOT been fact-extracted yet.

    Filter on `fact_check_json IS NULL` so a re-run of the launchd job
    doesn't double-extract the same draft.
    """
    return await conn.fetch(
        """
        SELECT id, topic, register, slides_json
          FROM war_room_drafts
         WHERE status = 'drafts_imaged'
           AND fact_check_json IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _persist_facted(
    conn: asyncpg.Connection, draft_id: UUID, claims: list[dict[str, Any]]
) -> None:
    """Save claims + advance status. fact_check_status stays NULL — only
    the fact-checker can set it (this stage just enumerates claims).
    """
    payload = json.dumps({"claims": claims, "extracted_at": datetime.now(timezone.utc).isoformat()})
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET fact_check_json = $2::jsonb,
               status          = 'drafts_imaged_facted',
               updated_at      = NOW()
         WHERE id = $1
        """,
        draft_id,
        payload,
    )


# ─────────────────────────────────────────────────────────────────────────
# Per-slide extraction
# ─────────────────────────────────────────────────────────────────────────

async def _extract_one_slide(
    *,
    topic: str,
    register: str,
    slide: dict[str, Any],
    model: str,
    timeout_s: int,
) -> list[dict[str, Any]]:
    """Run OPUS on a single slide; return claims list (possibly empty).

    Retries once on JSON-parse failure (the model occasionally wraps
    output in fences or trailing commentary). Returns [] on persistent
    parse failure — the caller decides whether to fail or degrade.
    """
    slide_index = int(slide.get("index", 0))
    title = str(slide.get("title", ""))[:200]
    body = str(slide.get("body", ""))
    if not body.strip():
        return []

    prompt = _PROMPT_TEMPLATE.format(
        topic=topic[:200],
        register=register or "pedagogico",
        slide_index=slide_index,
        title=title,
        body=body[:2000],  # Cap body so prompt stays small.
    )

    for attempt in (1, 2):
        try:
            resp = await complete_async(
                prompt,
                model=model,
                timeout_s=timeout_s,
                endpoint="wr2.fact_extractor",
            )
        except ClaudeOAuthNotAvailable:
            raise
        except ClaudeOAuthError:
            # Surface to caller; retry happens at the draft level.
            raise

        claims = _parse_claims_json(resp.text or "", slide_index)
        if claims is not None:
            return claims

        logger.warning(
            "slide %d: JSON parse failed on attempt %d (head=%r)",
            slide_index, attempt, (resp.text or "")[:120],
        )

    return []  # degraded — no claims for this slide


async def _process_one_draft(conn: asyncpg.Connection, row: asyncpg.Record) -> bool:
    draft_id: UUID = row["id"]
    topic: str = row["topic"]
    register: str = row["register"] or "pedagogico"
    slides_json = row["slides_json"]

    if isinstance(slides_json, str):
        slides_json = json.loads(slides_json)
    slides = (
        slides_json.get("slides")
        if isinstance(slides_json, dict)
        else slides_json
    ) or []

    if not slides:
        logger.warning("Draft %s: no slides — skipping", draft_id)
        return False

    t0 = time.time()
    all_claims: list[dict[str, Any]] = []
    for slide in slides:
        try:
            claims = await _extract_one_slide(
                topic=topic,
                register=register,
                slide=slide if isinstance(slide, dict) else {},
                model=DEFAULT_MODEL,
                timeout_s=DEFAULT_TIMEOUT_S,
            )
        except (ClaudeOAuthError, ClaudeOAuthNotAvailable) as exc:
            duration = time.time() - t0
            logger.error(
                "Draft %s: OPUS extraction failed: %s — %s",
                draft_id, type(exc).__name__, exc,
            )
            _log_telemetry(
                {
                    "draft_id": str(draft_id),
                    "outcome": "oauth_error",
                    "duration_s": round(duration, 1),
                    "exc_head": f"{type(exc).__name__}: {str(exc)[:200]}",
                }
            )
            _send_telegram(
                f"🚨 *WR2 fact-extractor OAuth failure*\n"
                f"draft: `{draft_id}`\ntopic: {topic[:80]}\n"
                f"error: `{type(exc).__name__}: {str(exc)[:300]}`"
            )
            return False
        all_claims.extend(claims)

    duration = time.time() - t0
    await _persist_facted(conn, draft_id, all_claims)
    logger.info(
        "Draft %s facted — %d claims across %d slides in %.1fs",
        draft_id, len(all_claims), len(slides), duration,
    )
    _log_telemetry(
        {
            "draft_id": str(draft_id),
            "outcome": "success",
            "duration_s": round(duration, 1),
            "claims_count": len(all_claims),
            "slides_count": len(slides),
        }
    )
    return True


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

async def run() -> int:
    _configure_logging()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        if not await _kill_switch_enabled(conn):
            logger.info("wr2_fact_extractor_enabled != true — exiting quietly")
            return 0

        drafts = await _fetch_ready_drafts(conn, MAX_DRAFTS_PER_RUN)
        if not drafts:
            logger.info("no drafts ready for fact extraction")
            return 0

        logger.info("processing %d draft(s)", len(drafts))
        successes = 0
        started = time.monotonic()
        for row in drafts:
            try:
                ok = await _process_one_draft(conn, row)
            except Exception as exc:  # noqa: BLE001 — never crash mid-run
                logger.exception("Draft %s: unexpected error: %s", row["id"], exc)
                ok = False
            if ok:
                successes += 1

        logger.info(
            "run complete — %d/%d ok in %.1fs",
            successes, len(drafts), time.monotonic() - started,
        )
        return 0 if successes == len(drafts) else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
