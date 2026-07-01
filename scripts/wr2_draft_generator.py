#!/usr/bin/env python3
"""WR2 Draft Generator — Claude writes 6-11 English slides with SMART hero selection.

Daily cron (05:15 WITA): picks drafts with status='briefed', calls Claude
OAuth to compose the slide JSON (English content, register in the 7
Council tones). Slide count is FLEXIBLE (6-11) and the model decides which
slides deserve a full-bleed photo (is_hero_image=true) based on the story —
the cover is always hero; text-heavy slides (dense lists, citations, pure
editorial takes) stay text-only and render as clean text-on-color (decision
2026-06-13, superseding the 2026-06-12 "every slide hero" rule). Runs Imagen 4
Ultra for the cover only (other hero slides keep image_url=None and carry
image_prompt for downstream generation), uploads the cover to Tigris, persists
slides_json to the draft and flips status to 'drafts'.

Env:
    DATABASE_URL           — localhost form
    GOOGLE_API_KEY         — Imagen 4 Ultra
    CLAUDE_CODE_OAUTH_TOKEN[_{BACKUP,CRON}] — Claude Max plan
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY — Tigris S3
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
# scripts/ on path so the pure topic-type helpers (sibling module) import
# regardless of cwd (launchd runs with an arbitrary working directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncpg  # noqa: E402

import wr2_topic_type as tt  # noqa: E402  (pure, side-effect-free)
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

# ── A1 keystone: liveness_tier propagation (cicatrix #9 schema-drift) ──────────
# The topic selector already computes a liveness_tier and persists it inside
# brief_json (wr2_topic_selector.py: "liveness_tier": top_item.get(...)), but the
# drafter used to read enrichment + live_reasons and DROP this field on the floor.
# A1 wires it end-to-end: read it here, hand Claude a one-line editorial framing so
# the narrative matches the story's timeliness. A1 is framing ONLY — it deliberately
# does NOT constrain slide count (that's A2) or tone (that's A3); those hang off the
# SAME injection point in later PRs. Mirrors selector's LIVENESS_TIER_VALID (SSOT).
LIVENESS_TIER_VALID = {"breaking", "developing", "evergreen"}

# One-line editorial framing per tier. Neutral on length/tone — pure "how timely is
# this" context. "manual" (operator-inserted topics) and anything unknown → no line.
_LIVENESS_FRAMING = {
    "breaking": (
        "EDITORIAL CONTEXT — liveness: BREAKING. This is fast-moving, just-happened news; "
        "write with urgency and a clear 'what changed / what to do now' spine."
    ),
    "developing": (
        "EDITORIAL CONTEXT — liveness: DEVELOPING. This story is still unfolding; frame it as "
        "an evolving situation readers should track, not a settled conclusion."
    ),
    "evergreen": (
        "EDITORIAL CONTEXT — liveness: EVERGREEN. This is durable, reference-grade material; "
        "write it to stay useful for months, explanatory rather than time-pegged."
    ),
}


def _normalise_liveness_tier(raw: Any) -> str:
    """Lower-case + validate against the selector's SSOT set. Unknown / missing /
    'manual' collapse to '' (→ no framing line injected). Never raises."""
    tier = str(raw or "").strip().lower()
    return tier if tier in LIVENESS_TIER_VALID else ""

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
TIGRIS_PUBLIC_BASE = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev"

# Inline 4-layer prompt builder (mirror of backend.services.visual.prompt_builder).
# We copy instead of importing because backend.services.visual.__init__ triggers
# Settings() which requires JWT_SECRET_KEY etc. — unacceptable for a cron entry.
BRAND_SUFFIX: str = (
    "Editorial style, high resolution, no stock imagery, "
    "no handshakes, no generic passports, "
    "NO documents or pens on a desk, NO paperwork close-ups, "
    "cinematic lighting"
)
_DEFAULT_STYLE_MODIFIERS: tuple[str, ...] = (
    "macrografia editoriale",
    "surrealista",
    "stile Wired magazine",
    "stile Bloomberg photography",
)
NEGATIVE_PROMPT: str = (
    "hands holding objects, passport close-ups, generic handshake, "
    "stock photo aesthetic, text overlays, watermark, logo, "
    "deformed hands, extra fingers, distorted faces, illegible text, "
    # 2026-06-13 (Antonello): the document-and-pen-on-a-desk cliché is the
    # single most off-brand image WR2 keeps producing. Ban it explicitly.
    "document on a desk, contract on a table, land deed on a desk, "
    "fountain pen, signing pen, pen resting on paper, hand signing, "
    "official seal close-up, stack of papers, paperwork on a desk, "
    "notary scene, clipboard, ballpoint pen, desk with documents"
)


def build_imagen_prompt(
    scene_core: str,
    *,
    style_modifiers: tuple[str, ...] | None = None,
    brand_suffix: str = BRAND_SUFFIX,
    extra_hints: str | None = None,
) -> str:
    if not scene_core or not scene_core.strip():
        raise ValueError("scene_core is required")
    style = ", ".join(style_modifiers or _DEFAULT_STYLE_MODIFIERS)
    parts = [scene_core.strip(), brand_suffix, style]
    if extra_hints:
        parts.append(extra_hints.strip())
    return ". ".join(p for p in parts if p).strip()


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

GOAL: produce the 6-8 slide structure (flexible: pick the count the story needs) of an Instagram carousel that reads like a NARRATIVE (Wired/The Atlantic editorial), not a legal brief.

TONE REGISTERS (pick ONE of the 7 based on content):
- rituale (ritual): symbolic events, cultural anniversaries, turning points
- analitico (analytic): data, numbers, systems (default for tax / visa / regulation)
- ironico (ironic): obvious contradictions, bureaucratic absurdity
- militante (militant): injustices toward expats / foreign investors
- pedagogico (pedagogic): step-by-step breakdown of complex systems
- poetico (poetic): stories of people, life transitions
- tecnico (technical): pure procedures, checklists, mechanics

Keep the register key itself in its Italian slug (e.g. "analitico") for compatibility with the backend WR2 tone validator. The slide CONTENT is English.

HARD RULES:
- NEVER use tones "cinico" or "istituzionale_severo" (legacy WR1, FORBIDDEN)
- Language: ENGLISH (international expat audience)
- Headlines max 60 characters
- Body max 280 characters AND ~40 words (whichever first; ~25-35 words ideal)
- Slide 1 = cover (is_cover: true, is_hero_image: true ALWAYS)
- LAST slide = CTA to Bali Zero
- HERO slides must include image_prompt: editorial scene in Wired/Bloomberg style, NO stock photos, NO handshakes, NO passport close-ups (text-only slides do NOT need image_prompt)
- BANNED IMAGE CLICHÉ (HARD — Antonello 2026-06-13): NEVER a document / deed /
  contract / form lying on a desk or table with a pen (especially a fountain
  pen) resting on or beside it, NEVER paperwork close-ups, NEVER a hand signing,
  NEVER an official seal close-up. This "papers + pen on a desk" image is the
  single most off-brand stock cliché — the brand rejects it outright. Show the
  HUMAN and PLACE reality behind the rule instead: people in a real moment, a
  Balinese/Indonesian place or building, an architectural detail, a tense
  street/landscape scene — never the lawyer's-desk still life.

TONAL PALETTE (per HERO slide — drives the photographic look, fights monotony):
Each HERO slide MUST include a `tonal_palette` field. Pick ONE
that fits the slide's mood; do NOT use the same palette for every hero slide,
and vary it across carousels on the same topic (the brand forbids two
same-domain carousels looking identical):
- "warm-ochre": warm, intimate, lived-in interior/place mood
- "cool-teal": detached, analytical, institutional, data-heavy
- "monochrome": stark, archival, historical, high-gravity
- "high-contrast": tense, confrontational, urgent
- "bleached-daylight": open, hopeful, resolution, "the way out"

IMAGE MODE (per HERO slide — the SCENE TYPE, drives anti-sameness):
Each HERO slide MUST include an `image_mode` field naming the
KIND of scene. Pick the ONE mode that matches what the photo depicts, and VARY
it across the hero slides (two same-domain carousels must not repeat the same
dominant mode — the brand forbids monotony). Choose from EXACTLY these 9 modes:
- "desk-document": USE SPARINGLY and only for a genuinely novel documentary
  detail — NEVER the banned "document + pen on a desk" still life (see HARD
  rule above). Prefer a different mode whenever possible.
- "event-photo": a real moment/scene with people doing something
- "architecture-or-texture": buildings, surfaces, materials, no people
- "provocation-photo": a tense or confrontational image that unsettles
- "human-silhouette": a person shown as shape/shadow, anonymous, no face
- "object-comparison": two or more objects set against each other
- "calendar-photo": dates, deadlines, time made visible
- "data-visualization": a chart, graph, map, or numbers as the image
- "cultural-photo": Indonesian/Balinese culture, ritual, place, daily life
Use the slug verbatim (e.g. "cultural-photo").

HERO IMAGE SELECTION (SMART + ANTI-BANALITY — decision 2026-06-13):
An image must EARN its place. The enemy is the banal filler photo — an image
generated "tanto per", just so the slide has a picture. A decorative or
generic image is WORSE than no image: it cheapens the whole carousel.

DEFAULT = TEXT-ONLY (`is_hero_image: false`). Mark `is_hero_image: true` ONLY
when a photograph adds meaning the words cannot — a specific real SCENE, a
human face of the story, a charged place, a turning point, a provocation. The
cover is ALWAYS hero. Beyond that, be STINGY: usually only 1-3 mid slides plus
(optionally) the CTA truly deserve a photo. If the best image you can imagine
for a slide is a GENERIC illustration of the topic — a nondescript office, a
generic building, a stock chart, a calendar, a desk, "a person looking at a
laptop", anything that just visualises the concept rather than telling THIS
story — then it is filler: mark the slide text-only instead. When in doubt,
text-only.

The image_prompt for a hero slide must describe a SPECIFIC, concrete,
photographable moment ("a half-built villa fenced off at dusk, one security
lamp on") — never a generic concept ("real estate in Bali", "tax compliance",
"a business meeting"). If you cannot name a specific scene, the slide is
text-only.

Each HERO slide MUST carry `image_prompt`, `tonal_palette` AND `image_mode`
(vary the modes — never let one dominate, and never reach for the generic
"data-visualization"/"calendar-photo"/"object-comparison" modes just to
justify an image; those are the usual filler traps). Non-hero slides do NOT
need `image_prompt`, `tonal_palette` or `image_mode`.

STORYTELLING DIRECTIVES (overrides any default factual mode):

1. Body is a STORY, not a citation. Open with a HOOK (a person, a moment, a
   contradiction, a stake), not with a law article. Citations belong at the
   END of the body in the form "[Source: <law-or-doc>]" — never at the
   beginning, never as the entire body.

2. Body length: TARGET ~25-35 words (≈180-250 characters). HARD cap 280
   characters AND ~40 words — whichever is hit first. Editorial reference
   bodies (NYT/FT carousels) cap at ~25 words / 2-3 short sentences; past
   ~40 words a slide reads as a dense legal-fine-print "text brick" the
   vision critic rejects, ESPECIALLY on photo slides where the body renders
   over an image. If you cannot fit the story, cut the citation, not the
   story. Fixed text boxes overflow and look bad with longer copy.

3. Headline is the HOOK, not the topic title. "Sham Investor KITAS: The
   Clock Is Ticking" is good (urgency, stakes). "Field Inspections Are
   Legal" is bad (sounds like a Wikipedia heading). Make headlines READ
   like a magazine cover line. Write headlines that BALANCE well on two
   lines: keep them short (≤6 words is ideal) and avoid phrasings that
   would leave one tiny orphan word alone on the last wrapped line — two
   even halves or two balanced clauses read best on a slide.

4. Citations: a slide can name ONE law/article, not three. "PP 31/2013
   authorises field inspections" is fine. "Permenkumham 11/2024 Art.
   38-40, 196-197 requires E28A/E28B investor KITAS holders to document
   financial co-..." is a legal brief, not a carousel. Prune.

5. Each slide should answer ONE question or land ONE punch. If your body
   contains "and" twice, you are stacking — split or cut.

6. Forbidden body openings (and forbidden first-clause patterns):
   - "Permenkumham [N]/[year]"
   - "PP No. [N] Tahun [year]"
   - "Article [N]"
   - "Section [N]"
   - any form of "[Law] requires/authorises/states that..."
   Open with a person, a stake, a date with consequence, a question, a
   quoted phrase, or a concrete scene. Then introduce the law later if
   needed.

7. Bali Zero "take" slides (typically slide 2 and the last slide): write as
   first-person editorial voice ("Our read:", "What we are seeing:"),
   NOT as a third-party legal summary.

8. The "What This Means For You" type closer (the last slide): SHORT, DIRECT,
   action-oriented. Two sentences max. Ends with the Bali Zero CTA.

9. The cover "subhead" MUST be 1-6 words maximum — a short tag/category/
   kicker (e.g. "VISA UPDATE", "IMMIGRATION", "TAX ALERT"), NOT a full
   sentence. UPPERCASE. It sits below the headline as a yellow accent
   label. NEVER write a complete sentence in subhead; if you need to
   explain, that goes in the body, not the subhead.

OUTPUT FORMAT: valid JSON, no text outside the JSON object, no markdown fences.

Structure:
{
  "register": "analitico",
  "register_reason": "one-line justification for the register choice",
  "slides": [
    {
      "slide_number": 1,
      "slide_type": "cover",
      "is_cover": true,
      "is_hero_image": true,
      "headline": "...",
      "subhead": "1-6 WORD KICKER",
      "body": "...",
      "image_prompt": "editorial scene, 1-2 sentences",
      "image_mode": "architecture-or-texture"
    },
    {
      "slide_number": 2,
      "slide_type": "take",
      "is_cover": false,
      "is_hero_image": false,
      "headline": "Our read: ...",
      "body": "First-person editorial take — reads as clean text-on-color, no photo needed."
    },
    {
      "slide_number": 3,
      "slide_type": "body",
      "is_cover": false,
      "is_hero_image": true,
      "headline": "The turning point",
      "body": "A scene worth a photo — a moment, a place, a provocation.",
      "image_prompt": "editorial scene, 1-2 sentences",
      "tonal_palette": "cool-teal",
      "image_mode": "event-photo"
    },
    {
      "slide_number": 4,
      "slide_type": "body",
      "is_cover": false,
      "is_hero_image": false,
      "headline": "What changes",
      "body": "A dense list or stacked facts — lives on text, NO image_prompt."
    },
    // ... more slides; mix hero (with image_prompt/tonal_palette/image_mode)
    //     and non-hero (text-only) as the story needs ...
    {
      "slide_number": 7,
      "slide_type": "cta",
      "is_cover": false,
      "is_hero_image": true,
      "headline": "Where this leaves you",
      "body": "One clear consequence, then one concrete next step. Reach Bali Zero when the deadline is yours, not theirs.",
      "image_prompt": "editorial scene, 1-2 sentences",
      "tonal_palette": "bleached-daylight",
      "image_mode": "human-silhouette"
    }
  ]
}

REPEAT (MUST OBEY): the cover (slide 1) MUST have `is_hero_image: true`. For
every OTHER slide, set `is_hero_image` SMARTLY based on whether it carries real
visual value (true) or lives on text (false). EVERY hero slide MUST carry
`image_prompt`, `tonal_palette` and `image_mode`; non-hero slides need none of
those. Typically 4-8 of N slides are hero — never all, never just the cover.

ALSO MANDATORY: vary the `image_mode` (one of the 9 slugs above) across the
HERO slides — use at least 4 DISTINCT modes per carousel; never let one scene
type dominate the whole carousel.
"""


def _build_enriched_brief(enrichment: dict[str, Any], live_reasons: list[str] | None) -> str:
    """Render the structured enrichment object as a labeled brief for Claude.

    The intel-scraper produces 1400-2000 words across these fields:
      - thirty_second_brief: {what, why_it_matters, who, risk_level}
      - the_facts: 3-5 paragraphs of pure journalism, 400-500 words
      - bali_zero_take: 2-3 paragraphs editorial perspective, 150-200 words
      - in_practice: practical implications, 150-200 words
      - next_steps: concrete action items, 100-150 words
      - faq: list of {question, answer} pairs

    The legacy prompt path passed only `summary[:3500]` (≈ 25% of the
    available material) and ignored every Bali-Zero-specific framing the
    enricher produced. This builder turns the structured object into a
    section-tagged ground-truth brief Claude can quote from directly.

    Returns an empty string if enrichment has no usable fields, so the
    caller can fall back to the legacy summary path cleanly.
    """
    parts: list[str] = []

    brief30 = enrichment.get("thirty_second_brief") or {}
    if isinstance(brief30, dict) and brief30:
        what = brief30.get("what") or ""
        why = brief30.get("why_it_matters") or ""
        who = brief30.get("who") or ""
        risk = brief30.get("risk_level") or ""
        if what or why or who:
            parts.append("### 30-second brief")
            if what:
                parts.append(f"What: {what}")
            if why:
                parts.append(f"Why it matters: {why}")
            if who:
                parts.append(f"Who is affected: {who}")
            if risk:
                parts.append(f"Risk level: {risk}")
            parts.append("")

    facts = enrichment.get("the_facts") or ""
    if isinstance(facts, str) and facts.strip():
        parts.append("### The facts (use these as ground truth)")
        parts.append(facts.strip())
        parts.append("")

    take = enrichment.get("bali_zero_take") or ""
    if isinstance(take, str) and take.strip():
        parts.append("### Bali Zero editorial take")
        parts.append(take.strip())
        parts.append("")

    practice = enrichment.get("in_practice") or ""
    if isinstance(practice, str) and practice.strip():
        parts.append("### In practice (for expats/investors)")
        parts.append(practice.strip())
        parts.append("")

    next_steps = enrichment.get("next_steps") or ""
    if isinstance(next_steps, str) and next_steps.strip():
        parts.append("### Next steps")
        parts.append(next_steps.strip())
        parts.append("")

    faq = enrichment.get("faq") or []
    if isinstance(faq, list) and faq:
        parts.append("### FAQ")
        for entry in faq[:6]:  # cap at 6, more is noise
            if not isinstance(entry, dict):
                continue
            q = entry.get("question") or ""
            a = entry.get("answer") or ""
            if q and a:
                parts.append(f"Q: {q}")
                parts.append(f"A: {a}")
                parts.append("")

    if live_reasons:
        parts.append("### Live news signals (why this is timely)")
        for reason in live_reasons[:3]:
            parts.append(f"- {reason}")
        parts.append("")

    return "\n".join(parts).strip()


def _build_draft_prompt(
    topic: str,
    summary: str,
    source_url: str,
    enrichment: dict[str, Any] | None = None,
    live_reasons: list[str] | None = None,
    avoid_steer: str = "",
    liveness_tier: str = "",
) -> str:
    """Build the slide-composition prompt.

    PR-1 §C: when an enrichment object is available we hand Claude the full
    structured brief (1400-2000 words across the_facts, bali_zero_take,
    in_practice, next_steps, faq) instead of a truncated paragraph. This is
    the default path (WR2_USE_FULL_ENRICHED_PROMPT defaults to "true"); set
    WR2_USE_FULL_ENRICHED_PROMPT=false to opt out and force the legacy path
    for back-compat / rollback.

    Falls back to summary[:3500] when:
      - WR2_USE_FULL_ENRICHED_PROMPT == "false" (legacy opt-out), OR
      - enrichment dict is empty / missing all expected fields.
    """
    use_full_enriched = os.environ.get("WR2_USE_FULL_ENRICHED_PROMPT", "true").lower() == "true"

    body = ""
    if use_full_enriched and enrichment:
        body = _build_enriched_brief(enrichment, live_reasons)

    if not body:
        # Legacy path: truncated summary. Always available as fallback.
        body = summary[:3500]

    # A1: inject the liveness framing (empty string when tier is unknown/manual).
    liveness_line = _LIVENESS_FRAMING.get(liveness_tier, "")
    liveness_block = f"\n\n{liveness_line}" if liveness_line else ""

    return f"""{SYSTEM_INSTRUCTIONS}{avoid_steer}{liveness_block}

---

ARTICLE TO TURN INTO A CAROUSEL:

Title: {topic}

Source: {source_url or "n/a"}

Content:
{body}

---

Produce the full 6-8 slide JSON NOW. English content. No text outside the JSON object.
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


async def claude_compose_slides(
    topic: str,
    summary: str,
    source_url: str,
    enrichment: dict[str, Any] | None = None,
    live_reasons: list[str] | None = None,
    avoid_steer: str = "",
    liveness_tier: str = "",
) -> dict[str, Any]:
    prompt = _build_draft_prompt(
        topic, summary, source_url,
        enrichment=enrichment, live_reasons=live_reasons,
        avoid_steer=avoid_steer, liveness_tier=liveness_tier,
    )
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
# Imagen cover + Tigris upload
# ─────────────────────────────────────────────────────────────────────────


def _upload_to_tigris(image_bytes: bytes, key: str, content_type: str = "image/png") -> str:
    import boto3

    s3 = boto3.client("s3", endpoint_url=TIGRIS_ENDPOINT, region_name="auto")
    s3.put_object(
        Bucket=TIGRIS_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
        ACL="public-read",
    )
    return f"{TIGRIS_PUBLIC_BASE}/{key}"


# ─────────────────────────────────────────────────────────────────────────
# Cover provider chain (2026-05-06): Codex `$imagegen` (gpt-image-2) PRIMARY,
# Gemini Nano Banana 2 Pro via Playwright as FALLBACK.
#
# Why ribaltato: Nano Banana via Playwright failed twice under load (4 maggio
# timeout 240s, 6 maggio chromium_headless_shell-1208 missing). Codex CLI
# v0.128.0 (21 apr 2026) ships `$imagegen` skill backed by gpt-image-2,
# included in ChatGPT Pro $200 plan (no per-call billing, OAuth, allineato a
# Golden Rule #13 anti-paid-API). Smoke test 2026-05-06 14:24: 113s wall-clock,
# 2.2 MB PNG, exit code 0.
#
# Trap operativo: Codex IGNORA output path nel prompt — scrive sempre in
# `~/.codex/generated_images/<uuid-v7>/ig_<hash>.png`. Trovare il PNG
# generato by mtime (not by name).
#
# Memo: ~/.claude/projects/-Users-nuzantara/memory/discovery_codex_imagegen_default_path_2026_05_06.md
# ─────────────────────────────────────────────────────────────────────────

CODEX_BIN = "/opt/homebrew/bin/codex"
CODEX_OUTPUT_DIR = Path.home() / ".codex" / "generated_images"
CODEX_TIMEOUT_SEC = 600  # 5x margin over observed 113s
CODEX_MTIME_WINDOW_SEC = 600  # search window for "fresh" PNG (10min)
# Strip provider API keys before spawning Codex subprocess. Mirror of
# backend.services.federation_alerts.actions.codex_image_gen._safe_env().
# OPENAI_API_KEY is held by parent for text-embedding-3-small only;
# image gen MUST go via Codex OAuth Pro $200 plan, never per-call billing.
_CODEX_STRIPPED_ENV_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "AWS_BEDROCK_ANTHROPIC_KEY",
    "VERTEX_AI_ANTHROPIC_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
})


def _codex_safe_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _CODEX_STRIPPED_ENV_KEYS}


async def _generate_cover_via_codex(scene_core: str) -> tuple[bytes | None, str | None]:
    """Generate cover via Codex CLI `$imagegen`. Return (img_bytes, error_msg).

    Never raises. On any failure returns (None, error_msg) so caller can
    fall through to the Playwright/Nano Banana legacy path.
    """
    bare_prompt = scene_core.strip()
    logger.info(
        "Cover via Codex $imagegen (gpt-image-2) — prompt (%d chars): %s...",
        len(bare_prompt),
        bare_prompt[:120],
    )
    # Snapshot pre-existing PNGs so we can identify the fresh one by exclusion.
    pre_existing: set[Path] = set()
    if CODEX_OUTPUT_DIR.exists():
        pre_existing = set(CODEX_OUTPUT_DIR.rglob("ig_*.png"))

    t0 = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            CODEX_BIN,
            "exec",
            f"$imagegen {bare_prompt}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            env=_codex_safe_env(),
        )
        try:
            _stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=CODEX_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None, f"codex $imagegen timed out after {CODEX_TIMEOUT_SEC}s"
        if proc.returncode != 0:
            tail = (_stderr or _stdout or b"").decode("utf-8", errors="replace")[-200:]
            return None, f"codex exit={proc.returncode}: {tail.strip()}"
    except FileNotFoundError:
        return None, f"codex binary not found at {CODEX_BIN}"
    except Exception as e:
        return None, f"codex spawn failed: {e}"

    # Find the freshest PNG NOT in the pre-existing set.
    if not CODEX_OUTPUT_DIR.exists():
        return None, "codex output dir does not exist after run"
    candidates = [p for p in CODEX_OUTPUT_DIR.rglob("ig_*.png") if p not in pre_existing]
    if not candidates:
        # Fallback: take latest by mtime if it falls within the window.
        all_pngs = list(CODEX_OUTPUT_DIR.rglob("ig_*.png"))
        if not all_pngs:
            return None, "no PNG found in codex output dir"
        latest = max(all_pngs, key=lambda p: p.stat().st_mtime)
        if (time.time() - latest.stat().st_mtime) > CODEX_MTIME_WINDOW_SEC:
            return None, f"latest PNG older than {CODEX_MTIME_WINDOW_SEC}s window"
        png_path = latest
    else:
        png_path = max(candidates, key=lambda p: p.stat().st_mtime)

    try:
        img_bytes = png_path.read_bytes()
    except Exception as e:
        return None, f"failed to read codex PNG {png_path}: {e}"

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Codex cover generated: %d bytes from %s (%.0fms)",
        len(img_bytes),
        png_path.name,
        elapsed_ms,
    )
    return img_bytes, None


async def _generate_cover_via_playwright(bare_prompt: str) -> tuple[bytes | None, str | None]:
    """Generate cover via Gemini Nano Banana 2 Pro via Playwright (LEGACY).

    Return (img_bytes, error_msg). Never raises. Used as fallback when
    Codex `$imagegen` fails. Lazy-imports wr2_image_generator so the
    Playwright dependency is not loaded unless we hit this path.
    """
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    try:
        from wr2_image_generator import (  # noqa: E402
            GEMINI_PROFILE_DIR,
            _gen_one_image,
        )
    except Exception as e:
        return None, f"wr2_image_generator import failed: {e}"

    from playwright.async_api import async_playwright  # noqa: E402

    logger.info(
        "Cover via Gemini Nano Banana (FALLBACK) — prompt (%d chars): %s...",
        len(bare_prompt),
        bare_prompt[:120],
    )
    img_bytes: bytes | None = None
    last_err: str | None = None

    # Strictly serial: ONE fresh browser context, ONE tab. Empirical: parallel
    # tabs on the persistent Gemini profile silently degrade output (page
    # returns stock-style content unrelated to the prompt). Cover is the
    # most-important image of the carousel — never speculate on quality.
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(GEMINI_PROFILE_DIR),
                headless=True,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                img_bytes, last_err = await _gen_one_image(context, 0, bare_prompt)
            finally:
                await context.close()
    except Exception as e:
        return None, f"Playwright cover gen failed: {e}"

    if not img_bytes:
        return None, f"cover gen returned no bytes: {last_err or 'unknown'}"
    return img_bytes, None


async def _finalize_cover(
    img_bytes: bytes,
    bare_prompt: str,
    draft_id: str,
    t0: float,
) -> tuple[str | None, str | None]:
    """VLM alignment gate + Tigris upload. Shared between Codex and Playwright paths."""
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    try:
        from wr2_image_generator import (  # noqa: E402
            _score_image_alignment,
            _upload_to_tigris as _img_upload_to_tigris,
            VLM_MIN_SCORE,
        )
    except Exception as e:
        return None, f"wr2_image_generator import failed (finalize): {e}"

    try:
        score, why = await _score_image_alignment(img_bytes, bare_prompt, 0)
        if score < VLM_MIN_SCORE:
            logger.warning(
                "Cover image rejected by VLM (score=%.2f < %.2f): %s",
                score,
                VLM_MIN_SCORE,
                why,
            )
            return None, f"VLM rejected cover (score={score:.2f}): {why}"
    except Exception as e:
        logger.warning("Cover VLM scoring failed: %s — accepting image", e)

    duration_ms = (time.perf_counter() - t0) * 1000
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"warroom/{draft_id}/cover-{ts}.png"
    try:
        url = _img_upload_to_tigris(img_bytes, key, "image/png")
    except Exception as e:
        return None, f"Tigris upload failed: {e}"

    logger.info(
        "Cover %d bytes uploaded → %s (%.0fms)",
        len(img_bytes),
        url,
        duration_ms,
    )
    return url, None


async def generate_cover_image(scene_core: str, draft_id: str) -> tuple[str | None, str | None]:
    """Return (public_url, error_msg). Never raises.

    Provider chain (PRIMARY → FALLBACK):
      1. Codex CLI `$imagegen` (gpt-image-2 via OAuth Pro $200) — preferred
      2. Gemini Nano Banana 2 Pro via Playwright (legacy) — fallback

    On both failures returns a clear error tuple — caller proceeds without cover.
    """
    bare_prompt = scene_core.strip()
    t0 = time.perf_counter()

    # ── PRIMARY: Codex `$imagegen` ──
    img_bytes, codex_err = await _generate_cover_via_codex(bare_prompt)
    if img_bytes is not None:
        return await _finalize_cover(img_bytes, bare_prompt, draft_id, t0)

    logger.warning(
        "Codex cover failed (%s) — falling back to Playwright/Nano Banana",
        codex_err,
    )

    # ── FALLBACK: Playwright + Gemini Nano Banana 2 Pro ──
    img_bytes, pw_err = await _generate_cover_via_playwright(bare_prompt)
    if img_bytes is not None:
        return await _finalize_cover(img_bytes, bare_prompt, draft_id, t0)

    # Both providers failed — return composite error for diagnosis.
    return None, f"Both providers failed: codex={codex_err}; playwright={pw_err}"


# ─────────────────────────────────────────────────────────────────────────
# Slide normalisation
# ─────────────────────────────────────────────────────────────────────────


def _cap_subhead(text: str, max_words: int = 6, max_chars: int = 32) -> str:
    """Hard-cap the cover subhead to the template contract (1-6 words).

    The cover-photo.md template declares subheading = "1-6 words, UPPERCASE,
    yellow accent, often a tag/category". A long subhead overflows the
    rendered box once grow_font enlarges it, so this is the deterministic
    backstop behind the prompt guidance: take at most ``max_words`` words,
    then if still longer than ``max_chars`` trim to a word boundary. No
    ellipsis is appended — a clean shorter kicker beats a truncated one.
    """
    words = text.strip().split()
    if not words:
        return ""
    capped = " ".join(words[:max_words])
    if len(capped) <= max_chars:
        return capped
    # Still too long: trim to max_chars on a word boundary (no mid-word cut).
    trimmed: list[str] = []
    length = 0
    for w in capped.split():
        extra = len(w) + (1 if trimmed else 0)
        if length + extra > max_chars:
            break
        trimmed.append(w)
        length += extra
    # Guarantee at least the first word even if it alone exceeds max_chars.
    if not trimmed:
        trimmed = [capped.split()[0]]
    return " ".join(trimmed)


def _normalise_slides(parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    register = (parsed.get("register") or "").strip().lower()
    if register not in VALID_TONES:
        raise ValueError(
            f"Claude returned invalid register={register!r} (allowed: {sorted(VALID_TONES)})",
        )

    slides = parsed.get("slides") or []
    if len(slides) < 6 or len(slides) > 11:
        raise ValueError(f"Expected 6-11 slides, got {len(slides)}")

    normalised: list[dict[str, Any]] = []
    for i, raw in enumerate(slides, start=1):
        # tonal_palette (2026-06-05): per-hero look selector consumed by
        # wr2_image_generator._resolve_tonal. Passthrough as a lowercase hint;
        # unknown/missing values resolve to the default look downstream, so we
        # store whatever the model gave (or None) without hard-validating here.
        tonal = raw.get("tonal_palette")
        tonal = tonal.strip().lower() if isinstance(tonal, str) and tonal.strip() else None
        # image_mode (2026-06-05, P-4): per-hero scene-mode (constitution Art 5.8,
        # 9 modes) consumed by topic_type_log.derive_dominant_mode for the
        # anti-sameness ledger. Whitelisted here like tonal_palette — without
        # this line the field is stripped at persistence. Lowercased hint; no
        # hard validation (unknown values just don't constrain downstream).
        slide = {
            "slide_number": i,
            "slide_type": raw.get("slide_type", "body"),
            "is_cover": bool(raw.get("is_cover", i == 1)),
            "is_hero_image": bool(raw.get("is_hero_image", False)),
            "headline": (raw.get("headline") or "").strip()[:80],
            "subhead": _cap_subhead(raw.get("subhead") or ""),
            "body": (raw.get("body") or "").strip()[:500],
            "image_prompt": (raw.get("image_prompt") or "").strip()[:600],
            "tonal_palette": tonal,
            "image_mode": (raw.get("image_mode") or "").strip().lower() or None,
            "image_url": None,  # filled later for cover only
        }
        normalised.append(slide)

    if normalised:
        normalised[0]["is_cover"] = True
        for s in normalised[1:]:
            s["is_cover"] = False
        # SMART hero (decision Antonello 2026-06-13, supersedes 2026-06-12
        # option A): the MODEL decides which slides deserve a photo. Minimal
        # defensive rules only:
        #   - the cover (slide 1) is ALWAYS hero (a carousel needs at least one
        #     hero image; the cover is the natural minimum);
        #   - every other slide PRESERVES the model's is_hero_image flag verbatim
        #     (already set above from raw.get(...)) — we do NOT force-promote.
        # If the model marked zero heroes beyond the cover, that is left as-is:
        # the cover alone is hero enough, and text-only slides route to a
        # text-only layout family downstream (composer.map_slide_to_family),
        # never to a photo layout with an empty hero.
        normalised[0]["is_hero_image"] = True

    return register, normalised


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


async def fetch_recent_same_domain(
    conn: asyncpg.Connection, domain: str, limit: int = 2
) -> list[dict[str, Any]]:
    """Last-N rendered carousels in this domain, newest first (P-4, Art 10.6).

    Returns a list of {"register", "dominant_mode"} dicts for the anti-sameness
    steer/reject. Best-effort: any error (e.g. the topic_type_log table not yet
    migrated on this DB) returns [] so generation is never blocked. The "unknown"
    domain bucket is never queried (it must not cross-constrain unrelated topics).
    """
    if not domain or domain == tt.UNKNOWN:
        return []
    try:
        rows = await conn.fetch(
            """
            SELECT register, dominant_mode
              FROM topic_type_log
             WHERE domain = $1
               AND deleted_at IS NULL
             ORDER BY rendered_at DESC
             LIMIT $2
            """,
            domain,
            limit,
        )
    except Exception as exc:  # noqa: BLE001 — table may not exist yet; never block
        logger.warning("fetch_recent_same_domain(%s) failed: %s", domain, exc)
        return []
    return [{"register": r["register"], "dominant_mode": r["dominant_mode"]} for r in rows]


def _build_avoid_steer(recent: list[dict[str, Any]]) -> str:
    """Render the recent same-domain (register, mode) combos as a soft-steer
    block to append to the generation prompt. Empty list -> empty string."""
    if not recent:
        return ""
    combos = ", ".join(
        f"(register={r.get('register') or '?'}, image-mode={r.get('dominant_mode') or '?'})"
        for r in recent
    )
    return (
        "\n\nANTI-SAMENESS (constitution Art 10.6 — MUST OBEY): the last "
        "same-domain carousels we published used these (register, image-mode) "
        f"combinations: {combos}. Your carousel MUST DIFFER in EITHER the "
        "register OR the dominant image-mode from each of them — do not reuse "
        "the same pairing. Prefer a fresh register and a different dominant "
        "scene-mode so two same-domain carousels never look alike."
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
    enrichment = brief.get("enrichment") or None
    live_reasons = brief.get("live_news_reasons") or []
    if not isinstance(live_reasons, list):
        live_reasons = []
    # A1 keystone: the selector already put this in brief_json — read it (was dropped).
    liveness_tier = _normalise_liveness_tier(brief.get("liveness_tier"))

    logger.info(
        "─── processing draft %s ─── topic=%r enrichment=%s live_score=%s liveness_tier=%s",
        draft_id, topic[:80],
        bool(enrichment), brief.get("live_news_score"),
        liveness_tier or "(none)",
    )

    # ── P-4 anti-sameness (constitution Art 10.6) ──────────────────────────
    # Soft steer (ALWAYS ON): derive the prospective domain from the topic,
    # look up the last-2 rendered same-domain carousels, and tell the model to
    # vary register/image-mode away from them. The HARD reject loop below only
    # engages when WR2_ANTIMONOTONE_ENFORCE=true (default OFF) — it ships
    # dormant-but-safe so it can be turned on after topic_type_log fills with
    # real data. The "unknown" domain bucket is never constrained.
    prospective_domain = tt.derive_domain(topic)
    recent = await fetch_recent_same_domain(conn, prospective_domain, limit=2)
    avoid_steer = _build_avoid_steer(recent)
    enforce = os.environ.get("WR2_ANTIMONOTONE_ENFORCE", "false").lower() == "true"
    max_regen = 2  # => up to 3 total generation attempts

    parsed: dict[str, Any] | None = None
    register = ""
    slides: list[dict[str, Any]] = []
    for attempt in range(max_regen + 1):
        try:
            parsed = await claude_compose_slides(
                topic=topic, summary=summary, source_url=source_url,
                enrichment=enrichment, live_reasons=live_reasons,
                avoid_steer=avoid_steer, liveness_tier=liveness_tier,
            )
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
            register, slides = _normalise_slides(parsed)
        except ValueError as e:
            logger.error("Normalisation failed: %s", e)
            await _mark_rejected(conn, draft_id, f"normalise_error: {e}")
            return False

        # Derived signature of THIS draft for the anti-sameness check.
        slides_envelope = {"slides": slides}
        dominant_mode = tt.derive_dominant_mode(slides_envelope)

        if (
            not enforce
            or prospective_domain == tt.UNKNOWN
            or not tt.collides_with_recent(register, dominant_mode, recent)
        ):
            break  # accepted (enforcement off, unknown domain, or no collision)

        if attempt < max_regen:
            logger.warning(
                "Anti-sameness collision (domain=%s register=%s mode=%s) vs recent "
                "%s — regenerating (attempt %d/%d).",
                prospective_domain, register, dominant_mode, recent,
                attempt + 1, max_regen,
            )
            # Strengthen the steer on retry so the model does not repeat itself.
            avoid_steer = _build_avoid_steer(recent) + (
                "\n\nYour PREVIOUS attempt repeated a forbidden combination. "
                f"Do NOT use register={register!r} with image-mode={dominant_mode!r} "
                "again. Change at least one of them."
            )
        else:
            logger.warning(
                "Anti-sameness collision persisted after %d retries "
                "(domain=%s register=%s mode=%s) — proceeding anyway (WARN).",
                max_regen, prospective_domain, register, dominant_mode,
            )

    assert parsed is not None  # loop always sets parsed or returns

    # Intra-carousel variety WARN (autopsy): a single carousel should use >=3
    # distinct image-modes. Becomes meaningful now that §3.0 emits image_mode.
    n_distinct = tt.distinct_mode_count({"slides": slides})
    if n_distinct < 3:
        logger.warning(
            "Draft %s has only %d distinct image-modes (<3) — monotone carousel.",
            draft_id, n_distinct,
        )

    logger.info(
        "Slides composed: register=%s count=%d cover_prompt=%r",
        register,
        len(slides),
        slides[0]["image_prompt"][:80],
    )

    cover_url, cover_err = await generate_cover_image(
        scene_core=slides[0]["image_prompt"],
        draft_id=str(draft_id),
    )
    if cover_url:
        slides[0]["image_url"] = cover_url
    else:
        logger.warning("Cover failed: %s", cover_err)
        slides[0]["image_url"] = None
        slides[0]["image_prompt_fallback"] = True

    council_meta = {
        "register_reason": parsed.get("register_reason", ""),
        "cover_url": cover_url,
        "cover_error": cover_err,
        "composed_at": datetime.now(timezone.utc).isoformat(),
    }
    await _persist_ready(conn, draft_id, register, slides, council_meta)
    logger.info("Draft %s → status=drafts", draft_id)

    cover_status = "OK" if cover_url else f"FAILED: {(cover_err or '')[:60]}"
    body_count = len(slides) - 1
    _send_telegram(
        "WR2 draft pronto per Canva\n"
        f"Topic: {topic[:120]}\n"
        f"Register: {register}\n"
        f"Cover: {cover_status}\n"
        f"Slide body ({body_count}): prompt inline, da generare a mano\n"
        f"Draft: {draft_id}\n"
        "Canva Renderer ogni 5 min",
    )
    return True


async def run(*, dry_run: bool = False, draft_id: str | None = None) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=300)
    # R4.2 drain-loop (P-1): re-fetch until the briefed queue is empty so a
    # supervisor kickstart swallowed while we are busy still gets its draft
    # processed this run. Capped against pathological re-queue loops.
    max_loops = int(os.environ.get("WR2_DRAFT_DRAIN_MAX_LOOPS", "10"))
    try:
        async with pool.acquire() as conn:
            successes = 0
            attempted = 0
            for loop_n in range(max_loops):
                if draft_id:
                    rows = (
                        await conn.fetch(
                            "SELECT id, topic, brief_json FROM war_room_drafts WHERE id = $1::uuid",
                            draft_id,
                        )
                        if loop_n == 0
                        else []
                    )
                else:
                    rows = await _fetch_briefed_drafts(conn, MAX_DRAFTS_PER_RUN)

                if not rows:
                    if attempted == 0:
                        logger.info("No briefed drafts to process")
                        return 1
                    break

                if dry_run:
                    logger.info("[DRY-RUN] would process %d drafts:", len(rows))
                    for r in rows:
                        logger.info("  %s — %s", r["id"], r["topic"][:80])
                    return 0

                for row in rows:
                    attempted += 1
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
                if draft_id:
                    break

            logger.info("Done: %d/%d drafts promoted to 'drafts'", successes, attempted)
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
