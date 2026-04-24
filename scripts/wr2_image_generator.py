#!/usr/bin/env python3
"""WR2 Image Generator — Playwright + Gemini app (Nano Banana 2 Pro).

Runs between wr2_draft_generator.py and wr2_canva_desktop_apply.py.
Picks drafts with status='drafts' and `hero_slide_indices` in council_debate_json,
generates one image per hero slide via the logged-in Gemini web app (no API),
uploads each image to Tigris, writes image_url back into slides_json, and
flips status to 'drafts_imaged'.

Generation strategy:
- One fresh Gemini tab per image (each tab = isolated conversation)
- Up to MAX_CONCURRENT_TABS in parallel (default 3)
- Model: "2.5 Pro" with "Nano Banana 2 Pro" image-generation mode
- Download the PNG via hover-reveal download button
- Upload to Tigris bucket nuzantara-warroom-images under warroom/{draft_id}/

Env:
    DATABASE_URL                              — Postgres DSN (localhost)
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY — Tigris S3
    WR2_GEMINI_PROFILE_DIR                    — override profile path
    WR2_IMAGE_MAX_CONCURRENT                  — override MAX_CONCURRENT_TABS (default 3)
    WR2_IMAGE_TIMEOUT_PER_SLIDE               — seconds to wait per image (default 180)
    TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID — optional

Usage:
    python3 scripts/wr2_image_generator.py              # process pending drafts
    python3 scripts/wr2_image_generator.py --draft-id UUID
    python3 scripts/wr2_image_generator.py --dry-run    # no DB writes, no image gen
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg  # noqa: E402

logger = logging.getLogger("wr2.image_generator")

# ─────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────

GEMINI_PROFILE_DIR = Path(
    os.environ.get(
        "WR2_GEMINI_PROFILE_DIR",
        str(Path.home() / ".nuzantara" / "playwright-profiles" / "gemini"),
    ),
)
GEMINI_URL = "https://gemini.google.com/app"

MAX_CONCURRENT_TABS = int(os.environ.get("WR2_IMAGE_MAX_CONCURRENT", "1"))
TIMEOUT_PER_SLIDE = int(os.environ.get("WR2_IMAGE_TIMEOUT_PER_SLIDE", "240"))
MAX_DRAFTS_PER_RUN = 2

# Gemini web reliably degrades when many tabs share one persistent profile
# in parallel or even serially within a single browser context (Send button
# sometimes never renders; images occasionally never arrive). Default now
# isolates each hero slide in a freshly-launched browser context.
# Empirical data (Apr 25, 2026, Ultra plan):
#   parallel=3 tabs, one context:  1/3 OK
#   serial=1, one context:          1/4 OK
#   serial + fresh context/slide:   3/4 OK (at 240s/slide)
# Set WR2_IMAGE_ISOLATE_BROWSER=false to restore the old shared-context mode.
ISOLATE_PER_SLIDE = os.environ.get("WR2_IMAGE_ISOLATE_BROWSER", "true").lower() == "true"

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
TIGRIS_PUBLIC_BASE = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev"

# Brand modifiers appended to every hero-slide image_prompt before sending to
# Gemini. Keep aligned with the 8 visual constraints encoded in the draft
# generator SYSTEM_INSTRUCTIONS. Repeating them here acts as defense-in-depth:
# even if Claude drifts, Gemini still sees the rules.
BRAND_SUFFIX = (
    "Editorial photography, shot on 35mm film, subtle film grain, "
    "chiaroscuro lighting, low-key exposure, desaturated muted palette of "
    "deep charcoals and warm ochre accents. Minimalist composition with "
    "vast negative space. No human faces visible — silhouettes or objects only. "
    "Photorealistic. 4:5 portrait orientation."
)

ANTI_CLICHE_SUFFIX = (
    "Strictly NO palm trees, NO laptops on beaches, NO digital nomad cliches, "
    "NO infinity pools, NO neon lights. NO Balinese temples, religious offerings, "
    "or traditional dancers. NO AI-art fingerprints: no hyperrealistic faces, "
    "no glowing edges, no fantasy elements."
)

GEMINI_PROMPT_PREFIX = "Please generate a photograph for an editorial magazine carousel. Describe the image based on this concept:\n\n"
GEMINI_PROMPT_SUFFIX = f"\n\n{BRAND_SUFFIX}\n\n{ANTI_CLICHE_SUFFIX}"

# ─────────────────────────────────────────────────────────────────────────
# Playwright selectors — verified 2026-04-24 on /gemini profile
# ─────────────────────────────────────────────────────────────────────────

SEL_INPUT = "div.ql-editor[contenteditable='true']"
SEL_SEND = "button[aria-label='Send message']"
# Image response: <img> src on googleusercontent NOT on /ogw/ (avatar path)
# AND not a profile picture. We filter programmatically in Python.

# ─────────────────────────────────────────────────────────────────────────
# Logging + Telegram
# ─────────────────────────────────────────────────────────────────────────


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_image_generator.log"
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
# Tigris upload
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
# Playwright worker
# ─────────────────────────────────────────────────────────────────────────


def _compose_final_prompt(image_prompt: str) -> str:
    return f"{GEMINI_PROMPT_PREFIX}{image_prompt.strip()}{GEMINI_PROMPT_SUFFIX}"


async def _gen_one_image(
    context: Any,  # playwright BrowserContext
    slide_number: int,
    image_prompt: str,
    timeout_s: int = TIMEOUT_PER_SLIDE,
) -> tuple[bytes | None, str | None]:
    """Wraps a bare image_prompt with brand+anti-cliche modifiers and sends.
    Prefer this path for variant 1 (primary). Use _gen_one_image_raw to send
    a literal prompt (variants 2/3)."""
    final = _compose_final_prompt(image_prompt)
    return await _gen_one_image_raw(context, slide_number, final, timeout_s=timeout_s)


async def _gen_one_image_raw(
    context: Any,  # playwright BrowserContext
    slide_number: int,
    literal_prompt: str,
    timeout_s: int = TIMEOUT_PER_SLIDE,
) -> tuple[bytes | None, str | None]:
    """Send `literal_prompt` VERBATIM (no brand/anti-cliche wrapping) and
    return (bytes, error_msg).

    Detection (verified 2026-04-24 via DOM inspection of live Gemini):
      - Generated image is <img class="image animate loaded">
      - src is a blob: URL (blob:https://gemini.google.com/<uuid>)
      - alt == ", AI generated"
      - parent is <button class="image-button">
      - Download full-res via aria-label="Download full-sized image" button
    """
    page = await context.new_page()
    try:
        await page.goto(GEMINI_URL, timeout=60000, wait_until="load")
        await page.wait_for_selector(SEL_INPUT, timeout=30000)

        # Route to image-gen mode via the explicit "Create image" tool button
        # (revealed in the compose toolbar). This forces the correct model
        # pathway. If not visible, fall back to default model selection.
        try:
            await page.locator("button[aria-label*='Create image' i]").first.click(timeout=5000)
            await asyncio.sleep(1.5)
            logger.debug("Clicked 'Create image' tool button")
        except Exception:
            # Fallback to model switcher (older UI)
            try:
                await page.get_by_role("button", name="Model").click(timeout=3000)
                await page.get_by_text("2.5 Pro", exact=False).click(timeout=3000)
            except Exception:
                logger.debug("No 'Create image' button and no model switcher — using default")

        # Type prompt. `delay=5` lets Quill rerender as each key arrives;
        # bulk `fill()` would drop into the DOM in one event and sometimes
        # leave Gemini's compose toolbar in a stale state where the Send
        # button never renders.
        await page.click(SEL_INPUT)
        await page.keyboard.type(literal_prompt, delay=5)
        # Small trailing keypress to force Quill to commit the composition
        # buffer — observed empirically: without this, `input` events
        # sometimes don't fire and the Send button stays hidden.
        await page.keyboard.press("End")
        await asyncio.sleep(3)
        send_btn = page.locator(SEL_SEND)
        try:
            await send_btn.wait_for(state="visible", timeout=60000)
            # Some Gemini builds keep the Send button present but disabled
            # until the text is committed. Poll until enabled (or timeout).
            for _ in range(30):
                disabled = await send_btn.get_attribute("aria-disabled")
                is_disabled_attr = await send_btn.get_attribute("disabled")
                if disabled in (None, "false") and is_disabled_attr is None:
                    break
                await asyncio.sleep(0.5)
        except Exception:
            # Fallback: send via Enter key on the input — Quill accepts
            # Shift+Enter for newline and plain Enter for submit.
            try:
                await page.locator(SEL_INPUT).focus()
                await page.keyboard.press("Enter")
                logger.debug("Send button never appeared; used keyboard Enter fallback")
            except Exception as e:
                return None, f"send button never ready and Enter fallback failed: {e}"
        else:
            await send_btn.click(timeout=15000)

        # Wait for generated image
        start = time.time()
        img_bytes: bytes | None = None
        last_err: str | None = None
        found_img_el = None
        while time.time() - start < timeout_s:
            await asyncio.sleep(3)
            # Primary selector: Gemini's stable generated-image class
            gen = page.locator("img.image.loaded, img[alt*='AI generated']")
            count = await gen.count()
            for i in range(count):
                img = gen.nth(i)
                try:
                    src = await img.get_attribute("src") or ""
                    alt = await img.get_attribute("alt") or ""
                except Exception:
                    continue
                if not src:
                    continue
                if "/ogw/" in src or alt.lower() == "profile picture":
                    continue
                # Get natural dimensions — reject tiny icons
                try:
                    w = await img.evaluate("(e) => e.naturalWidth")
                    h = await img.evaluate("(e) => e.naturalHeight")
                except Exception:
                    w, h = 0, 0
                if (w or 0) < 200 or (h or 0) < 200:
                    continue
                found_img_el = img
                break
            if found_img_el:
                break
        if not found_img_el:
            return None, last_err or f"timeout {timeout_s}s — no image appeared"

        # Three-pronged fetch:
        #   (1) browser-side fetch(blob_url) → arrayBuffer → base64
        #   (2) click "Download full-sized image" button + intercept event
        #   (3) last resort: Playwright element.screenshot() of the <img>
        #       (always works but recompresses to PNG at display size, not
        #        full source resolution)
        import base64

        try:
            b64 = await found_img_el.evaluate(
                """async (img) => {
                    const resp = await fetch(img.src);
                    const blob = await resp.blob();
                    const buf = await blob.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let binary = '';
                    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
                    return btoa(binary);
                }"""
            )
            img_bytes = base64.b64decode(b64)
            logger.debug("Fetched image via in-page fetch (%d bytes)", len(img_bytes))
        except Exception as e:
            last_err = f"in-page fetch failed: {e}"
            logger.warning("In-page fetch failed, trying Download button: %s", e)
            try:
                async with page.expect_download(timeout=30000) as dl_info:
                    await page.locator("button[aria-label*='Download full-sized image' i]").first.click()
                download = await dl_info.value
                path = await download.path()
                if path:
                    from pathlib import Path as _P
                    img_bytes = _P(path).read_bytes()
                    logger.debug("Fetched image via Download button (%d bytes)", len(img_bytes))
            except Exception as e2:
                last_err = f"{last_err}; download button failed: {e2}"
                logger.warning("Download button failed, trying element screenshot: %s", e2)
                try:
                    # Scroll image into view and grab its visible pixels as PNG.
                    # This is a display-size capture, not source-resolution, but
                    # it's enough to populate the carousel template.
                    await found_img_el.scroll_into_view_if_needed(timeout=5000)
                    img_bytes = await found_img_el.screenshot(timeout=15000)
                    logger.debug("Fetched image via element screenshot (%d bytes)", len(img_bytes))
                except Exception as e3:
                    return None, f"{last_err}; screenshot fallback failed: {e3}"

        if not img_bytes:
            return None, last_err or "no bytes captured"
        return img_bytes, None
    finally:
        await page.close()


MAX_RETRIES_PER_SLIDE = int(os.environ.get("WR2_IMAGE_MAX_RETRIES", "3"))


def _build_prompt_variants(image_prompt: str) -> list[str]:
    """Ordered list of prompts to try when the primary prompt fails.

    Gemini sometimes silently refuses a prompt (no image, no error). Common
    triggers observed empirically: "bound with red string", "sealed", "blood
    red", multi-page negative lists (ANTI_CLICHE_SUFFIX). We progressively
    strip aggressive modifiers and negative lists to increase the odds of
    generating *some* editorial-style image.
    """
    core = image_prompt.strip()
    full = _compose_final_prompt(core)  # noqa: F821 — defined below in module
    # Variant 2: drop ANTI_CLICHE_SUFFIX (the huge negative list).
    v2 = f"{GEMINI_PROMPT_PREFIX}{core}\n\n{BRAND_SUFFIX}"
    # Variant 3: minimal — core concept + brand only, no PROMPT_PREFIX decor.
    v3 = f"{core}. {BRAND_SUFFIX}"
    return [full, v2, v3]


async def _gen_image_with_semaphore(
    sem: asyncio.Semaphore,
    context: Any,
    slide_number: int,
    image_prompt: str,
    draft_id: str,
) -> tuple[int, str | None, str | None]:
    """Generate + upload one hero image. Returns (slide_number, url, error).

    Retries up to MAX_RETRIES_PER_SLIDE times on failure (Gemini UI flakiness
    is intermittent — page sometimes stalls while loading or the send button
    vanishes briefly; a fresh tab usually succeeds). After exhausting retries
    on the primary prompt, falls back to progressively stripped prompt
    variants (see _build_prompt_variants) — this recovers from silent safety
    refusals that ignore a fraction of phrasings.
    """
    async with sem:
        last_err: str | None = None
        img_bytes: bytes | None = None
        prompt_variants = _build_prompt_variants(image_prompt)
        overall_attempt = 0
        for variant_idx, prompt_to_use in enumerate(prompt_variants):
            variant_label = "primary" if variant_idx == 0 else f"variant{variant_idx + 1}"
            for attempt in range(1, MAX_RETRIES_PER_SLIDE + 1):
                overall_attempt += 1
                logger.info(
                    "[slide %d] generating image (overall %d, %s attempt %d/%d) — prompt=%r",
                    slide_number,
                    overall_attempt,
                    variant_label,
                    attempt,
                    MAX_RETRIES_PER_SLIDE,
                    prompt_to_use[:80],
                )
                t0 = time.time()
                try:
                    # Pass the RAW prompt string (without _compose_final_prompt
                    # wrapping) on variants ≥ 2; _gen_one_image always wraps
                    # what we pass via _compose_final_prompt, so undo here by
                    # stripping the prefix/suffix that _compose adds.
                    if variant_idx == 0:
                        img_bytes, err = await _gen_one_image(context, slide_number, image_prompt)
                    else:
                        # Send the literal variant via a bypass path
                        img_bytes, err = await _gen_one_image_raw(context, slide_number, prompt_to_use)
                except Exception as e:
                    img_bytes, err = None, f"unhandled exception: {e}"
                dt = time.time() - t0
                if img_bytes:
                    logger.info(
                        "[slide %d] ok on %s attempt %d (%.1fs, %d bytes)",
                        slide_number, variant_label, attempt, dt, len(img_bytes),
                    )
                    break
                last_err = err
                logger.warning(
                    "[slide %d] %s attempt %d failed after %.1fs: %s",
                    slide_number, variant_label, attempt, dt, err,
                )
                if attempt < MAX_RETRIES_PER_SLIDE:
                    # Cool-down: Gemini backend needs time to settle
                    await asyncio.sleep(15)
            if img_bytes:
                break  # exit variant loop too
            logger.info(
                "[slide %d] variant %s exhausted, trying next variant",
                slide_number, variant_label,
            )

        if not img_bytes:
            logger.error("[slide %d] all variants+attempts failed, last err=%s", slide_number, last_err)
            return slide_number, None, last_err or "all retries failed"

        logger.info("[slide %d] uploading to Tigris", slide_number)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        key = f"warroom/{draft_id}/slide-{slide_number:02d}-{ts}.png"
        try:
            url = _upload_to_tigris(img_bytes, key, "image/png")
        except Exception as e:
            return slide_number, None, f"tigris upload failed: {e}"
        logger.info("[slide %d] uploaded → %s", slide_number, url)
        return slide_number, url, None


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────


async def _fetch_pending(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    # Accept 'drafts_checked' (post fact_checker, new normal path) and
    # 'drafts' (legacy path when fact_checker is disabled). Rejected
    # 'fact_check_failed' drafts are NOT picked up — they wait for human
    # intervention.
    return await conn.fetch(
        """
        SELECT id, topic, slides_json, council_debate_json
          FROM war_room_drafts
         WHERE status IN ('drafts_checked', 'drafts')
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _persist_imaged(
    conn: asyncpg.Connection,
    draft_id: uuid.UUID,
    slides: list[dict[str, Any]],
    council_meta: dict[str, Any],
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET slides_json         = $2::jsonb,
               council_debate_json = $3::jsonb,
               status              = 'drafts_imaged',
               updated_at          = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps({"slides": slides}),
        json.dumps(council_meta),
    )


async def _mark_image_failed(conn: asyncpg.Connection, draft_id: uuid.UUID, reason: str) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status           = 'image_failed',
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


async def _process_one(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    *,
    dry_run: bool,
) -> bool:
    draft_id: uuid.UUID = row["id"]
    topic: str = row["topic"]
    slides_json_raw = row["slides_json"]
    slides_json = (
        json.loads(slides_json_raw) if isinstance(slides_json_raw, str) else (slides_json_raw or {})
    )
    slides = slides_json.get("slides") or []
    council_raw = row["council_debate_json"]
    council = (
        json.loads(council_raw) if isinstance(council_raw, str) else (council_raw or {})
    )

    hero_slides = [s for s in slides if s.get("is_hero_image")]
    if not hero_slides:
        logger.info("Draft %s has no hero slides — nothing to generate", draft_id)
        return False

    logger.info(
        "─── draft %s ─── topic=%r heroes=%d",
        draft_id,
        topic[:80],
        len(hero_slides),
    )

    if dry_run:
        for s in hero_slides:
            logger.info(
                "[DRY-RUN] slide %d: prompt=%r",
                s["slide_number"],
                (s.get("image_prompt") or "")[:100],
            )
        return True

    # Launch Playwright with the gemini profile
    from playwright.async_api import async_playwright

    results: list[Any] = []
    if ISOLATE_PER_SLIDE:
        # Serial with fresh browser context per slide — slowest but most robust
        # (eliminates cross-slide state bleed through Gemini's persistent
        # session). Pair with a small inter-slide cooldown to give any
        # server-side rate-limit a chance to clear.
        logger.info("ISOLATE_PER_SLIDE=true — fresh browser per hero slide")
        async with async_playwright() as p:
            for idx, s in enumerate(hero_slides):
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(GEMINI_PROFILE_DIR),
                    headless=True,
                    viewport={"width": 1440, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                )
                try:
                    sem = asyncio.Semaphore(1)
                    r = await _gen_image_with_semaphore(
                        sem,
                        context,
                        s["slide_number"],
                        s.get("image_prompt") or "",
                        str(draft_id),
                    )
                    results.append(r)
                finally:
                    await context.close()
                # Inter-slide cooldown except after last
                if idx < len(hero_slides) - 1:
                    await asyncio.sleep(5)
    else:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(GEMINI_PROFILE_DIR),
                headless=True,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                sem = asyncio.Semaphore(MAX_CONCURRENT_TABS)
                tasks = [
                    _gen_image_with_semaphore(
                        sem, context, s["slide_number"], s.get("image_prompt") or "", str(draft_id)
                    )
                    for s in hero_slides
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                await context.close()

    # Stitch URLs back into slides
    url_by_slide: dict[int, str] = {}
    errors_by_slide: dict[int, str] = {}
    for r in results:
        if isinstance(r, Exception):
            logger.exception("Worker raised: %s", r)
            continue
        slide_number, url, err = r
        if url:
            url_by_slide[slide_number] = url
        if err:
            errors_by_slide[slide_number] = err

    successes = len(url_by_slide)
    failures = len(errors_by_slide)
    logger.info("Draft %s: %d/%d images OK", draft_id, successes, successes + failures)

    for s in slides:
        if s.get("is_hero_image"):
            sn = s["slide_number"]
            if sn in url_by_slide:
                s["image_url"] = url_by_slide[sn]
            else:
                s["image_url"] = None
                s["image_error"] = errors_by_slide.get(sn, "unknown")

    council.update(
        {
            "image_generated_at": datetime.now(timezone.utc).isoformat(),
            "image_success_count": successes,
            "image_failure_count": failures,
            "image_errors": errors_by_slide,
        }
    )

    if successes == 0:
        logger.error("Draft %s: all %d images failed", draft_id, failures)
        await _mark_image_failed(
            conn,
            draft_id,
            f"all_images_failed: {list(errors_by_slide.values())[:3]}",
        )
        _send_telegram(
            f"WR2 image_generator FAILED\n"
            f"Draft: {draft_id}\n"
            f"Topic: {topic[:100]}\n"
            f"All {failures} hero images failed"
        )
        return False

    await _persist_imaged(conn, draft_id, slides, council)
    logger.info("Draft %s → status=drafts_imaged", draft_id)

    _send_telegram(
        "WR2 images ready\n"
        f"Topic: {topic[:120]}\n"
        f"Images: {successes}/{successes + failures} OK\n"
        f"Draft: {draft_id}\n"
        "Canva Apply next"
    )
    return True


async def run(*, dry_run: bool = False, draft_id: str | None = None) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    if not GEMINI_PROFILE_DIR.exists():
        logger.error(
            "Gemini profile not found at %s — run "
            "`bash scripts/playwright/login-all.sh gemini` first",
            GEMINI_PROFILE_DIR,
        )
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=600)
    try:
        async with pool.acquire() as conn:
            if draft_id:
                rows = await conn.fetch(
                    """
                    SELECT id, topic, slides_json, council_debate_json
                      FROM war_room_drafts
                     WHERE id = $1::uuid
                    """,
                    draft_id,
                )
            else:
                rows = await _fetch_pending(conn, MAX_DRAFTS_PER_RUN)

            if not rows:
                logger.info("No drafts in 'drafts' status to process")
                return 1

            if dry_run:
                logger.info("[DRY-RUN] would process %d drafts:", len(rows))

            successes = 0
            for row in rows:
                try:
                    ok = await _process_one(conn, row, dry_run=dry_run)
                    if ok:
                        successes += 1
                except Exception as e:
                    logger.exception("Unhandled error on draft %s: %s", row["id"], e)
                    try:
                        await _mark_image_failed(conn, row["id"], f"unhandled: {e}")
                    except Exception:
                        pass

            logger.info("Done: %d/%d drafts imaged", successes, len(rows))
            return 0 if successes > 0 else (0 if dry_run else 2)
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
        _send_telegram(f"WR2 image_generator crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
