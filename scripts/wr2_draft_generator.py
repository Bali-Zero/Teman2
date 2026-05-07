#!/usr/bin/env python3
"""WR2 Draft Generator — Claude writes 11 English slides, Imagen generates cover only.

Daily cron (05:15 WITA): picks drafts with status='briefed', calls Claude
OAuth to compose the 11-slide JSON (English content, register in the 7
Council tones), runs Imagen 4 Ultra for the cover only (body slides keep
image_url=None and carry image_prompt for manual generation by the team),
uploads the cover to Tigris, persists slides_json to the draft and flips
status to 'drafts'.

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

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
TIGRIS_PUBLIC_BASE = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev"

# Inline 4-layer prompt builder (mirror of backend.services.visual.prompt_builder).
# We copy instead of importing because backend.services.visual.__init__ triggers
# Settings() which requires JWT_SECRET_KEY etc. — unacceptable for a cron entry.
BRAND_SUFFIX: str = (
    "Editorial style, high resolution, no stock imagery, "
    "no handshakes, no generic passports, cinematic lighting"
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
    "deformed hands, extra fingers, distorted faces, illegible text"
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

GOAL: produce the 11-slide structure of an Instagram carousel that reads like a NARRATIVE (Wired/The Atlantic editorial), not a legal brief.

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
- Body max 280 characters
- Slide 1 = cover (is_cover: true, is_hero_image: true ALWAYS)
- Slide 11 = CTA to Bali Zero
- Every slide must include image_prompt: editorial scene in Wired/Bloomberg style, NO stock photos, NO handshakes, NO passport close-ups

HERO IMAGE SELECTION (MANDATORY):
You MUST mark exactly 4 slides as `is_hero_image: true`:
- Slide 1 (cover) — ALWAYS hero
- Slide 11 (CTA closer "What This Means For You") — ALWAYS hero
- 2 mid-carousel slides at NARRATIVE TURNING POINTS — pick the slides that
  open a new beat (e.g. "the shift", "the stakes", "fiction vs substance"),
  not the ones that list facts or numbers.

The remaining 7 slides have `is_hero_image: false` — they keep the
template's tipografia layout without an image. Hero slides get a
full-bleed photo as background; non-hero slides are clean text-on-color.

Output exactly 4 slides with `is_hero_image: true`. Not 3, not 5.

STORYTELLING DIRECTIVES (overrides any default factual mode):

1. Body is a STORY, not a citation. Open with a HOOK (a person, a moment, a
   contradiction, a stake), not with a law article. Citations belong at the
   END of the body in the form "[Source: <law-or-doc>]" — never at the
   beginning, never as the entire body.

2. Body length: TARGET ~50-70 words (≈350-450 characters). Hard cap 280
   characters per the format constraint above. If you cannot fit the story
   in 280 chars, cut the citation, not the story. The skill that paints
   these onto Canva slides has fixed text boxes; longer copy will overflow
   and look bad.

3. Headline is the HOOK, not the topic title. "Sham Investor KITAS: The
   Clock Is Ticking" is good (urgency, stakes). "Field Inspections Are
   Legal" is bad (sounds like a Wikipedia heading). Make headlines READ
   like a magazine cover line.

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

7. Bali Zero "take" slides (typically slide 2 and slide 11): write as
   first-person editorial voice ("Our read:", "What we are seeing:"),
   NOT as a third-party legal summary.

8. The "What This Means For You" type closer (slide 11): SHORT, DIRECT,
   action-oriented. Two sentences max. Ends with the Bali Zero CTA.

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
      "headline": "...",
      "subhead": "...",
      "body": "...",
      "image_prompt": "editorial scene, 1-2 sentences"
    },
    // ... 10 more slides ...
    {
      "slide_number": 11,
      "slide_type": "cta",
      "is_cover": false,
      "headline": "...",
      "body": "Bali Zero — Link in bio for a consultation"
    }
  ]
}
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
) -> str:
    """Build the slide-composition prompt.

    PR-1 §C: when an enrichment object is available we hand Claude the full
    structured brief (1400-2000 words across the_facts, bali_zero_take,
    in_practice, next_steps, faq) instead of a truncated paragraph. This
    is gated by WR2_USE_FULL_ENRICHED_PROMPT so the legacy path stays
    available for back-compat / rollback.

    Falls back to summary[:3500] when:
      - WR2_USE_FULL_ENRICHED_PROMPT != "true" (legacy mode), OR
      - enrichment dict is empty / missing all expected fields.
    """
    use_full_enriched = os.environ.get("WR2_USE_FULL_ENRICHED_PROMPT", "false").lower() == "true"

    body = ""
    if use_full_enriched and enrichment:
        body = _build_enriched_brief(enrichment, live_reasons)

    if not body:
        # Legacy path: truncated summary. Always available as fallback.
        body = summary[:3500]

    return f"""{SYSTEM_INSTRUCTIONS}

---

ARTICLE TO TURN INTO A CAROUSEL:

Title: {topic}

Source: {source_url or "n/a"}

Content:
{body}

---

Produce the full 11-slide JSON NOW. English content. No text outside the JSON object.
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
) -> dict[str, Any]:
    prompt = _build_draft_prompt(
        topic, summary, source_url,
        enrichment=enrichment, live_reasons=live_reasons,
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
        slide = {
            "slide_number": i,
            "slide_type": raw.get("slide_type", "body"),
            "is_cover": bool(raw.get("is_cover", i == 1)),
            "headline": (raw.get("headline") or "").strip()[:80],
            "subhead": (raw.get("subhead") or "").strip()[:120],
            "body": (raw.get("body") or "").strip()[:500],
            "image_prompt": (raw.get("image_prompt") or "").strip()[:600],
            "image_url": None,  # filled later for cover only
        }
        normalised.append(slide)

    if normalised:
        normalised[0]["is_cover"] = True
        for s in normalised[1:]:
            s["is_cover"] = False

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

    logger.info(
        "─── processing draft %s ─── topic=%r enrichment=%s live_score=%s",
        draft_id, topic[:80],
        bool(enrichment), brief.get("live_news_score"),
    )

    try:
        parsed = await claude_compose_slides(
            topic=topic, summary=summary, source_url=source_url,
            enrichment=enrichment, live_reasons=live_reasons,
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

    cover_status = "OK (Imagen Ultra)" if cover_url else f"FAILED: {(cover_err or '')[:60]}"
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
