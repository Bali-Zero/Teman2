#!/usr/bin/env python3
"""WR2 Draft Generator — Claude writes variable-length English slides (5-13).

Daily cron (05:15 WITA): picks drafts with status='briefed', calls Claude
OAuth to compose the slides JSON (English content, register in the 7
Council tones, length tier-driven: breaking 5-7 / explainer 8-10 / deep 11-13).
Image generation is delegated to wr2_image_generator.py (Playwright + Gemini
Nano Banana 2 Pro) — this script only marks which slides need images via
the `is_hero_image` flag and writes image_prompt. Status flips to 'drafts'
when slides are ready; wr2_image_generator then flips to 'drafts_imaged'.

Env:
    DATABASE_URL           — localhost form
    CLAUDE_CODE_OAUTH_TOKEN[_{BACKUP,CRON}] — Claude Max plan
    TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID  — optional
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

logger = logging.getLogger("wr2.draft_generator")

MAX_DRAFTS_PER_RUN = 2
VALID_TONES = {
    "rituale",
    "analitico",
    "ironico",
    "militante",
    "pedagogico",
    "poetico",
    "tecnico",
}

# Image generation moved to wr2_image_generator.py (Playwright + Gemini Nano
# Banana 2 Pro via persistent profile ~/.nuzantara/playwright-profiles/gemini).
# No more Imagen API calls from this script — it only composes text + prompts.


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_draft_generator.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
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
# Claude prompt (English output)
# ─────────────────────────────────────────────────────────────────────────

SYSTEM_INSTRUCTIONS = """You are the Draft Composer of War Room 2.0 for Bali Zero (https://balizero.com).

Bali Zero is an Indonesian business-services agency serving international expats, foreign investors, digital nomads and retirees — primarily English-speaking, from ~50 countries. The Italian community is one slice among many; never default to Italian.

GOAL: produce a variable-length Instagram carousel (4:5 portrait) based on a news / regulation article, with tier-driven length and curated image prompts for 5 hero slides.

LENGTH POLICY (choose ONE tier based on topic depth):
- **breaking** (5-7 slides): single-fact news, visa alert, simple regulation change. Hook → fact → who-it-affects → immediate-action → CTA.
- **explainer** (8-10 slides): how-to, step-by-step procedure, category overview. Hook → context → steps → pitfall → summary → CTA.
- **deep** (11-13 slides): regulatory overhaul with implications, multi-layer analysis, before/after. Hook → context → old-vs-new → impacts → timeline → FAQ → summary → CTA.

Default to **explainer (9 slides)** if unsure. Never fewer than 5 or more than 13.

TONE REGISTERS (pick ONE of the 7 based on content):
- rituale (ritual): symbolic events, cultural anniversaries, turning points
- analitico (analytic): data, numbers, systems (default for tax / visa / regulation)
- ironico (ironic): obvious contradictions, bureaucratic absurdity
- militante (militant): injustices toward expats / foreign investors
- pedagogico (pedagogic): step-by-step breakdown of complex systems
- poetico (poetic): stories of people, life transitions
- tecnico (technical): pure procedures, checklists, mechanics

Keep the register key itself in its Italian slug (e.g. "analitico") for compatibility with the backend WR2 tone validator. The slide CONTENT is English.

HERO SLIDES (AI-generated images) — exactly 5 slides get unique AI images:
- Slide 1 (cover) — scroll-stopper hook
- Slide 3 — the "stakes / problem / what's at risk"
- Slide N/2 (rounded down) — pivot / core insight / data visualization metaphor
- Slide N-2 — climax / solution / the "why it matters"
- All other slides (including slide N, the CTA) = NO AI image, use template typography-as-art

For each hero slide, produce an `image_prompt` that is a **purely visual scene description** (a physical metaphor, an object, a macro shot, an architectural detail — NOT a transcript of the slide text). Examples:
- Tax penalty → "A heavy steel vault door slightly ajar in a dark underground room, single overhead light, deep shadows"
- Visa delay → "Empty waiting room at dusk, rain-slicked window, a single folder on a metal desk, long exposure"
- PT PMA setup → "Macro shot of an ink stamp hovering above a stack of ledger papers on dark marble"

For non-hero slides: `image_prompt` can be empty string or null — they'll use Text-as-Art (massive League Spartan typography on pure charcoal #1a1a1a background).

HARD RULES:
- NEVER use tones "cinico" or "istituzionale_severo" (legacy WR1, FORBIDDEN)
- Language: ENGLISH (international expat audience)
- Headlines max 60 characters
- Body max 280 characters
- Slide 1 = cover (is_cover: true, is_hero_image: true)
- Slide N (last) = CTA to Bali Zero, is_hero_image: false
- Image prompts MUST follow these constraints:
  * Editorial dark moody: low-key lighting, cinematic chiaroscuro, desaturated charcoal/slate/ochre
  * 35mm film grain, editorial photography, Wired/Bloomberg/Monocle aesthetic
  * NO people's faces (silhouette/shadow/turned-away only if any human)
  * NO palm trees, laptops on beaches, digital nomad clichés, infinity pools, neon
  * NO temples, Balinese dancers, religious offerings (cultural appropriation)
  * YES brutalist architecture, dark wood, smoked glass, concrete textures, rain-slicked streets, macro shots of objects

OUTPUT FORMAT: valid JSON, no text outside the JSON object, no markdown fences.

Structure:
{
  "content_tier": "breaking" | "explainer" | "deep",
  "tier_reason": "one-line justification for tier choice based on topic depth",
  "register": "analitico",
  "register_reason": "one-line justification for the register choice",
  "slides": [
    {
      "slide_number": 1,
      "slide_type": "cover",
      "is_cover": true,
      "is_hero_image": true,
      "headline": "...",
      "subhead": "...",
      "body": "...",
      "image_prompt": "A physical visual scene, 1-2 sentences, no abstractions"
    },
    {
      "slide_number": 2,
      "slide_type": "body",
      "is_cover": false,
      "is_hero_image": false,
      "headline": "...",
      "body": "...",
      "image_prompt": ""
    },
    // ... N more slides, exactly 4 more with is_hero_image:true (slides 3, N/2, N-2) ...
    {
      "slide_number": N,
      "slide_type": "cta",
      "is_cover": false,
      "is_hero_image": false,
      "headline": "...",
      "body": "Bali Zero — Link in bio for a consultation",
      "image_prompt": ""
    }
  ]
}
"""


def _build_draft_prompt(topic: str, summary: str, source_url: str) -> str:
    return f"""{SYSTEM_INSTRUCTIONS}

---

ARTICLE TO TURN INTO A CAROUSEL:

Title: {topic}

Source: {source_url or "n/a"}

Content (excerpt):
{summary[:3500]}

---

Produce the full variable-length (5-13) slides JSON NOW. English content. No text outside the JSON object.
Pick content_tier based on topic depth. Mark exactly 5 slides with is_hero_image:true (cover + slide 3 + slide N/2 + slide N-2 + … compensate if N < 7 so image_prompt slides are: 1, middle, N-1).
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


async def claude_compose_slides(topic: str, summary: str, source_url: str) -> dict[str, Any]:
    prompt = _build_draft_prompt(topic, summary, source_url)
    logger.info("Calling Claude OAuth for slide composition (prompt %d chars)", len(prompt))
    t0 = time.perf_counter()
    resp = await complete_async(
        prompt,
        model="claude-opus-4-7",
        timeout_s=300,
        endpoint="wr2_draft_generator",
    )
    dt = time.perf_counter() - t0
    logger.info("Claude responded in %.1fs (token=%s)", dt, resp.token_label)
    return _extract_json(resp.text)


# ─────────────────────────────────────────────────────────────────────────
# Slide normalisation
# ─────────────────────────────────────────────────────────────────────────


VALID_TIERS: tuple[str, ...] = ("breaking", "explainer", "deep")
TIER_LENGTH_RANGE: dict[str, tuple[int, int]] = {
    "breaking": (5, 7),
    "explainer": (8, 10),
    "deep": (11, 13),
}
HERO_SLIDES_COUNT = 5  # cover + 4 AI images interni


def _compute_hero_indices(n_slides: int) -> set[int]:
    """Return the 1-based slide indices that get AI-generated images.

    Always: 1 (cover), 3, N/2, N-2. For short carousels (N<=6) collapse to
    1, middle, N-1 so we never place a hero on the CTA slide.
    """
    if n_slides < 5:
        return {1}
    if n_slides <= 6:
        return {1, n_slides // 2 + 1, n_slides - 1}
    # Standard 7+: cover, stakes, mid, pre-CTA (dedup in case of overlap)
    return {
        1,
        3,
        max(3, n_slides // 2),
        max(4, n_slides - 2),
    }


def _normalise_slides(parsed: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    """Return (register, content_tier, slides)."""
    register = (parsed.get("register") or "").strip().lower()
    if register not in VALID_TONES:
        raise ValueError(
            f"Claude returned invalid register={register!r} (allowed: {sorted(VALID_TONES)})",
        )

    content_tier = (parsed.get("content_tier") or "explainer").strip().lower()
    if content_tier not in VALID_TIERS:
        logger.warning(
            "Unknown content_tier=%r, defaulting to explainer",
            content_tier,
        )
        content_tier = "explainer"

    slides = parsed.get("slides") or []
    n = len(slides)
    lo, hi = TIER_LENGTH_RANGE[content_tier]
    # Allow graceful drift beyond tier range, but clamp to global 5-13
    if n < 5 or n > 13:
        raise ValueError(f"Expected 5-13 slides, got {n}")
    if n < lo or n > hi:
        logger.info(
            "Slide count %d drifts from tier %s range %d-%d (accepting)",
            n,
            content_tier,
            lo,
            hi,
        )

    hero_indices = _compute_hero_indices(n)
    logger.info("Hero slide indices for N=%d: %s", n, sorted(hero_indices))

    normalised: list[dict[str, Any]] = []
    for i, raw in enumerate(slides, start=1):
        is_cover = i == 1
        is_hero = i in hero_indices
        slide = {
            "slide_number": i,
            "slide_type": raw.get("slide_type", "cover" if is_cover else ("cta" if i == n else "body")),
            "is_cover": is_cover,
            "is_hero_image": is_hero,
            "headline": (raw.get("headline") or "").strip()[:80],
            "subhead": (raw.get("subhead") or "").strip()[:120],
            "body": (raw.get("body") or "").strip()[:500],
            "image_prompt": (raw.get("image_prompt") or "").strip()[:600] if is_hero else "",
            "image_url": None,  # filled by wr2_image_generator.py
        }
        normalised.append(slide)

    # Safety: if Claude gave no image_prompt to a hero slide, build a fallback
    for slide in normalised:
        if slide["is_hero_image"] and not slide["image_prompt"]:
            # Fallback: derive from headline + brand modifiers
            slide["image_prompt"] = (
                f"A dark editorial scene representing: {slide['headline'][:80]}. "
                "Macro shot or architectural detail, no human faces visible."
            )
            logger.warning(
                "Hero slide %d lacked image_prompt — used headline fallback",
                slide["slide_number"],
            )

    return register, content_tier, normalised


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────


async def _fetch_briefed_drafts(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
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


async def _persist_ready(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    register: str,
    slides: list[dict[str, Any]],
    council_meta: dict[str, Any],
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET slides_json         = $2::jsonb,
               register            = $3,
               council_debate_json = $4::jsonb,
               status              = 'drafts',
               updated_at          = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps({"slides": slides}),
        register,
        json.dumps(council_meta),
    )


async def _mark_rejected(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    reason: str,
) -> None:
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
# Main loop
# ─────────────────────────────────────────────────────────────────────────


async def _process_one(conn: asyncpg.Connection, row: asyncpg.Record) -> bool:
    draft_id: uuid.UUID = row["id"]
    topic: str = row["topic"]
    brief_raw = row["brief_json"]
    brief = json.loads(brief_raw) if isinstance(brief_raw, str) else (brief_raw or {})
    summary = brief.get("article_summary") or ""
    source_url = brief.get("source_url") or ""

    logger.info("─── processing draft %s ─── topic=%r", draft_id, topic[:80])

    try:
        parsed = await claude_compose_slides(topic=topic, summary=summary, source_url=source_url)
    except (ClaudeOAuthError, ClaudeOAuthNotAvailable) as e:
        logger.error("Claude OAuth failed: %s", e)
        await _mark_rejected(conn, draft_id, f"claude_failed: {e}")
        _send_telegram(f"WR2 draft_generator Claude failed\ndraft {draft_id}\n{str(e)[:200]}")
        return False
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Claude output parse failed: %s", e)
        await _mark_rejected(conn, draft_id, f"parse_error: {e}")
        return False

    try:
        register, content_tier, slides = _normalise_slides(parsed)
    except ValueError as e:
        logger.error("Normalisation failed: %s", e)
        await _mark_rejected(conn, draft_id, f"normalise_error: {e}")
        return False

    hero_count = sum(1 for s in slides if s["is_hero_image"])
    logger.info(
        "Slides composed: tier=%s register=%s count=%d heroes=%d",
        content_tier,
        register,
        len(slides),
        hero_count,
    )

    council_meta = {
        "content_tier": content_tier,
        "tier_reason": parsed.get("tier_reason", ""),
        "register_reason": parsed.get("register_reason", ""),
        "hero_slide_indices": [s["slide_number"] for s in slides if s["is_hero_image"]],
        "composed_at": datetime.now(timezone.utc).isoformat(),
    }
    await _persist_ready(conn, draft_id, register, slides, council_meta)
    logger.info(
        "Draft %s → status=drafts (images pending, %d hero slides)",
        draft_id,
        hero_count,
    )

    _send_telegram(
        "WR2 draft composed\n"
        f"Topic: {topic[:120]}\n"
        f"Tier: {content_tier} ({len(slides)} slides)\n"
        f"Register: {register}\n"
        f"Hero images to generate: {hero_count}\n"
        f"Draft: {draft_id}\n"
        "Image Generator runs next",
    )
    return True


async def run(*, dry_run: bool = False, draft_id: str | None = None) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=300)
    try:
        async with pool.acquire() as conn:
            if draft_id:
                rows = await conn.fetch(
                    "SELECT id, topic, brief_json FROM war_room_drafts WHERE id = $1::uuid",
                    draft_id,
                )
            else:
                rows = await _fetch_briefed_drafts(conn, MAX_DRAFTS_PER_RUN)

            if not rows:
                logger.info("No briefed drafts to process")
                return 1

            if dry_run:
                logger.info("[DRY-RUN] would process %d drafts:", len(rows))
                for r in rows:
                    logger.info("  %s — %s", r["id"], r["topic"][:80])
                return 0

            successes = 0
            for row in rows:
                try:
                    ok = await _process_one(conn, row)
                    if ok:
                        successes += 1
                except Exception as e:
                    logger.exception("Unhandled error on draft %s: %s", row["id"], e)
                    try:
                        await _mark_rejected(conn, row["id"], f"unhandled: {e}")
                    except Exception:
                        pass

            logger.info("Done: %d/%d drafts promoted to 'drafts'", successes, len(rows))
            return 0 if successes > 0 else 2
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--draft-id", type=str, default=None)
    args = parser.parse_args()

    _configure_logging()
    try:
        return asyncio.run(run(dry_run=args.dry_run, draft_id=args.draft_id))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        _send_telegram(f"WR2 draft_generator crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
