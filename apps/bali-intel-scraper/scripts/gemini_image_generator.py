#!/usr/bin/env python3
"""
Gemini Image Generator - Browser automation via gemini.google.com/app
Uses Playwright with system Chrome profile (already logged into Google).
Generates editorial cover images for enriched intel articles using Imagen 3.

Selectors last verified: 2026-03-05 from live DOM inspection.

Usage:
    python gemini_image_generator.py <state_file.json> [--limit N] [--headless]
    python gemini_image_generator.py <state_file.json> --refresh-profile   # force recopy cookies
"""

import argparse
import asyncio
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
CHROME_PROFILE_DIR = PROJECT_ROOT / "data" / ".chrome-profile"
IMAGES_DIR.mkdir(exist_ok=True, parents=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gemini_image_gen")

# ---------------------------------------------------------------------------
# Selectors — verified 2026-03-05 against live gemini.google.com DOM
#
# Generated images have:
#   class="image animate loaded"
#   parent: <button class="image-button ng-star-inserted">
#   alt=", AI generated"
#   src="https://lh3.googleusercontent.com/gg-dl/..."
#
# Response completion:
#   <div class="response-footer ... complete">
#
# Enterprise logo (EXCLUDE):
#   class="enterprise-logo"
#   alt="Enterprise logo"
# ---------------------------------------------------------------------------
GEMINI_URL = "https://gemini.google.com/app"

# Input area
SELECTOR_TEXTAREA = 'div[contenteditable="true"]'
SELECTOR_SEND_BTN = 'button[aria-label="Send message"], button[data-mat-icon-name="send"]'

# Response state detection
SELECTOR_RESPONSE_COMPLETE = ".response-footer.complete"
SELECTOR_RESPONSE_FOOTER = ".response-footer"

# Generated image — the definitive selector
SELECTOR_GENERATED_IMG = 'img.image.loaded'
SELECTOR_GENERATED_IMG_ALT = 'img[alt*="AI generated"]'
SELECTOR_IMAGE_BUTTON = "button.image-button"

# Exclude
SELECTOR_ENTERPRISE_LOGO = "img.enterprise-logo"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DELAY_BETWEEN_REQUESTS = 3   # seconds between image requests
IMAGE_GEN_TIMEOUT = 90        # max seconds to wait for image generation
MAX_RETRIES = 1               # retry once on failure
PROFILE_MAX_AGE_HOURS = 48    # recopy Chrome profile after this many hours


# ---------------------------------------------------------------------------
# Chrome profile management
# ---------------------------------------------------------------------------
def _profile_stale(profile_dir: Path) -> bool:
    """Check if the copied Chrome profile is too old (cookies may have expired)."""
    marker = profile_dir / ".copy_timestamp"
    if not marker.exists():
        return True
    age_hours = (time.time() - marker.stat().st_mtime) / 3600
    return age_hours > PROFILE_MAX_AGE_HOURS


def ensure_chrome_profile(force_refresh: bool = False) -> Path:
    """Copy system Chrome profile (cookies, local storage) for Playwright use.

    Only copies essential dirs to keep it lightweight (~50MB).
    Skips Cache dirs to save space and avoid lock conflicts.
    """
    source = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default"
    dest = CHROME_PROFILE_DIR / "Default"

    if not force_refresh and dest.exists() and not _profile_stale(CHROME_PROFILE_DIR):
        logger.info("Chrome profile cache is fresh, reusing")
        return CHROME_PROFILE_DIR

    if force_refresh:
        logger.info("Force-refreshing Chrome profile...")
    else:
        logger.info("Copying Chrome profile from system (cookies + storage)...")

    if dest.exists():
        shutil.rmtree(dest)

    ignore = shutil.ignore_patterns(
        "Cache", "Code Cache", "GPUCache", "Service Worker",
        "ShaderCache", "GrShaderCache", "blob_storage",
        "IndexedDB", "Sessions", "Crashpad",
    )
    shutil.copytree(source, dest, dirs_exist_ok=True, ignore=ignore)

    # Write timestamp marker
    marker = CHROME_PROFILE_DIR / ".copy_timestamp"
    marker.touch()
    logger.info("Chrome profile copied successfully")
    return CHROME_PROFILE_DIR


# ---------------------------------------------------------------------------
# Image prompt builder — Bali Zero Visual Identity
# ---------------------------------------------------------------------------

# Category-specific visual language — Bali Zero IG editorial style
# Matches @balizero0 Instagram feed: dramatic, high-contrast, real subjects,
# editorial compositing. NO text on images (title overlay added by frontend).
_CATEGORY_VISUALS = {
    "immigration": {
        "concept": "Dramatic immigration/visa tension — real people at crossroads",
        "shots": [
            "Indonesian immigration officer in uniform reviewing documents at desk, dramatic side lighting, shallow depth of field, office interior",
            "Foreign man standing at Bali airport immigration counter, seen from behind, warm overhead lights, tension moment",
            "Close-up of hands holding Indonesian visa booklet against Balinese temple background, golden hour",
            "Person walking through ornate Balinese split gate (candi bentar) toward bright light, silhouette, metaphor of passage",
        ],
        "palette": "High contrast, warm gold highlights on dark backgrounds, institutional cool tones mixed with Bali warmth",
        "forbidden": "NO passport stamps close-up, NO flags, NO welcome signs, NO cartoon illustrations",
    },
    "business": {
        "concept": "Business reality in Bali — construction, development, real operations",
        "shots": [
            "Aerial view of massive villa development construction site in Bali rice terraces, dramatic scale contrast nature vs development",
            "Row of identical rental villas seen from drone, repetitive pattern showing market saturation, moody overcast sky",
            "Businessman looking at laptop in open-air Balinese pavilion (bale), Mount Agung in background, contemplative mood",
            "Heavy machinery (excavator/bulldozer) working on Bali construction site, dramatic clouds, golden hour dust particles",
        ],
        "palette": "Earth tones, construction yellow, dramatic sky contrast, tropical green against concrete grey",
        "forbidden": "NO generic stock handshakes, NO arrows pointing up, NO graphs, NO suits in boardrooms",
    },
    "tax": {
        "concept": "Regulation and compliance tension — bureaucracy meets tropical paradise",
        "shots": [
            "Stack of Indonesian legal documents on traditional carved wood desk, single beam of light, dramatic chiaroscuro",
            "Indonesian government building (kantor pajak) exterior with Balinese architectural elements, dramatic sky",
            "Close-up of official Indonesian stamp/seal on document, shallow depth of field, warm side lighting",
            "Person studying documents in traditional Balinese open pavilion, monsoon rain in background, concentrated atmosphere",
        ],
        "palette": "Warm amber documents against cool institutional tones, dramatic light/shadow contrast",
        "forbidden": "NO calculators, NO Western tax forms, NO spreadsheets, NO money piles",
    },
    "property": {
        "concept": "Bali real estate drama — luxury meets reality, market tension",
        "shots": [
            "Stunning infinity pool villa perched on Uluwatu cliff edge at sunset, dramatic clouds, cinematic wide angle",
            "Abandoned half-built villa overgrown with tropical vegetation, cautionary tale, dramatic sky",
            "Aerial drone shot of Bali coastline with dense villa developments encroaching on rice terraces, scale of change",
            "Traditional Balinese temple (pura) framed between two modern villa developments, cultural tension, golden hour",
        ],
        "palette": "Dramatic sunset amber/coral, ocean teal, tropical green, luxury white against raw concrete",
        "forbidden": "NO For Sale signs, NO house keys, NO real estate agents posing, NO blueprints",
    },
    "lifestyle": {
        "concept": "Expat life in Bali — real moments, health alerts, cultural immersion",
        "shots": [
            "Expat on motorbike riding through Bali jungle road, morning mist, cinematic motion blur, adventure mood",
            "Dramatic Bali temple ceremony with smoke and offerings, foreigner observing respectfully from edge, cultural immersion",
            "Surfer silhouette at Uluwatu cliff during golden hour, massive wave in background, dramatic scale",
            "Morning scene at Bali traditional market (pasar), dramatic light rays through roof, vibrant colors of tropical fruit",
        ],
        "palette": "Vibrant tropical saturation, dramatic golden hour, ocean blues, jungle green intensity",
        "forbidden": "NO cocktails with umbrellas, NO tourist selfies, NO Instagram poses, NO beach party scenes",
    },
    "legal": {
        "concept": "Law and authority in Indonesia — power structures, enforcement, tradition",
        "shots": [
            "Indonesian police or satpol PP officers during enforcement operation, dramatic reportage style, shallow depth of field",
            "Grand Balinese temple gate with official government notice posted, clash of tradition and regulation",
            "Dramatic close-up of ancient Balinese stone guardian statue (dvarapala), morning mist, monumental authority",
            "Indonesian courtroom or government hearing room, dramatic overhead lighting, institutional gravity",
        ],
        "palette": "Authoritative dark tones, institutional grey-blue, warm Balinese gold accents, dramatic shadow",
        "forbidden": "NO Western courtrooms, NO gavels, NO Western judge robes, NO handcuffs close-up",
    },
}

_GLOBAL_FORBIDDEN = (
    "ABSOLUTELY NO TEXT, WORDS, LETTERS, NUMBERS, WATERMARKS, OR LOGOS IN THE IMAGE. "
    "The image must be completely free of any written content — no titles, no captions, "
    "no overlays, no branding. Also NO: graphs, arrows, fake smiles, laptop on beach, "
    "stock photo cliches, AI-looking synthetic faces, over-processed HDR."
)


def build_image_prompt(article: dict) -> str:
    """Build a Bali Zero IG-style prompt for Gemini image generation.

    Style: @balizero0 Instagram editorial — dramatic, high-contrast,
    real subjects, compositing feel. NO text (frontend adds title overlay).
    """
    import random

    title = article.get("title", "News Article")
    category = article.get("category", article.get("qwen_category", "general"))

    enrichment = article.get("enrichment", {})
    brief = ""
    if isinstance(enrichment, dict):
        brief = enrichment.get("executive_brief", "")
    context = brief[:200] if brief else title

    # Map category to visual language
    cat_key = category.lower().replace("-", "_").replace("tax_legal", "tax")
    if cat_key not in _CATEGORY_VISUALS:
        cat_key = "business"  # default
    vis = _CATEGORY_VISUALS[cat_key]

    # Pick a random shot suggestion for variety
    shot = random.choice(vis["shots"])

    return (
        f"Generate a dramatic editorial photograph in the style of a news magazine cover image.\n\n"
        f"ARTICLE TOPIC: {title}\n"
        f"CONTEXT: {context}\n\n"
        f"VISUAL CONCEPT: {vis['concept']}\n"
        f"COMPOSITION: {shot}\n"
        f"COLOR PALETTE: {vis['palette']}\n\n"
        f"STYLE: Dramatic photojournalism meets cinematic photography. High contrast, "
        f"deep shadows, punchy highlights. Real people, real places, real tension. "
        f"Think editorial magazine photography — National Geographic meets Bloomberg Businessweek.\n"
        f"Shot on professional camera, shallow depth of field, 16:9 landscape format.\n"
        f"Distinctly Balinese/Indonesian setting and subjects.\n\n"
        f"CRITICAL: The image must contain ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, "
        f"NO NUMBERS, NO LOGOS, NO WATERMARKS of any kind. Pure photography only.\n\n"
        f"{vis['forbidden']}\n"
        f"{_GLOBAL_FORBIDDEN}"
    )


# ---------------------------------------------------------------------------
# Core browser automation
# ---------------------------------------------------------------------------
async def _wait_for_response_complete(page: Page, timeout: int = IMAGE_GEN_TIMEOUT) -> bool:
    """Wait for Gemini to finish generating its response.

    Detects completion via `.response-footer.complete` class.
    Returns True if response completed, False on timeout.
    """
    await page.wait_for_timeout(3000)  # Initial settle time

    deadline = time.time() + timeout
    check_count = 0

    while time.time() < deadline:
        check_count += 1

        # Primary: check for the "complete" class on the response footer
        complete = await page.query_selector(SELECTOR_RESPONSE_COMPLETE)
        if complete:
            logger.info(f"Response complete (detected at check #{check_count})")
            await page.wait_for_timeout(1000)  # Brief settle
            return True

        # Secondary: if footer exists but no "complete" class, still generating
        footer = await page.query_selector(SELECTOR_RESPONSE_FOOTER)
        if footer:
            footer_class = await footer.get_attribute("class") or ""
            if "complete" in footer_class:
                logger.info(f"Response complete via class check (#{check_count})")
                await page.wait_for_timeout(1000)
                return True

        # Early exit: if we already see a generated image, don't wait more
        gen_img = await page.query_selector(SELECTOR_GENERATED_IMG)
        if gen_img:
            alt = await gen_img.get_attribute("alt") or ""
            if "AI generated" in alt:
                logger.info(f"Generated image detected early (#{check_count})")
                await page.wait_for_timeout(1000)
                return True

        await asyncio.sleep(2)

    logger.warning(f"Response timeout after {timeout}s ({check_count} checks)")
    return False


async def _find_generated_image(page: Page) -> Optional[str]:
    """Find the Gemini-generated image in the response DOM.

    Uses precise selectors verified against live DOM.
    Returns the image src URL or None.
    """
    # Strategy 1: img.image.loaded with "AI generated" alt (most reliable)
    imgs = await page.query_selector_all(SELECTOR_GENERATED_IMG)
    for img in imgs:
        alt = await img.get_attribute("alt") or ""
        src = await img.get_attribute("src") or ""
        cls = await img.get_attribute("class") or ""

        # Skip enterprise logos
        if "enterprise-logo" in cls:
            continue

        if "AI generated" in alt and src:
            nw = await img.evaluate("el => el.naturalWidth")
            logger.info(f"Found via img.image.loaded: {nw}px, alt='{alt[:30]}'")
            return src

    # Strategy 2: img[alt*="AI generated"] (alt-text based)
    imgs = await page.query_selector_all(SELECTOR_GENERATED_IMG_ALT)
    for img in imgs:
        src = await img.get_attribute("src") or ""
        if src:
            nw = await img.evaluate("el => el.naturalWidth")
            if nw and int(nw) >= 512:
                logger.info(f"Found via alt-text: {nw}px")
                return src

    # Strategy 3: img inside button.image-button (structural)
    buttons = await page.query_selector_all(SELECTOR_IMAGE_BUTTON)
    for btn in buttons:
        img = await btn.query_selector("img")
        if img:
            src = await img.get_attribute("src") or ""
            if src:
                nw = await img.evaluate("el => el.naturalWidth")
                logger.info(f"Found via image-button: {nw}px")
                return src

    # Strategy 4: fallback — any large googleusercontent image (>512px)
    all_imgs = await page.query_selector_all("img")
    for img in all_imgs:
        try:
            cls = await img.get_attribute("class") or ""
            if "enterprise-logo" in cls:
                continue

            src = await img.get_attribute("src") or ""
            if not src or "googleusercontent" not in src:
                continue

            nw = await img.evaluate("el => el.naturalWidth")
            if nw and int(nw) >= 512:
                logger.info(f"Found via fallback (googleusercontent ≥512px): {nw}px")
                return src
        except Exception:
            continue

    return None


async def _download_image(page: Page, img_src: str, save_path: Path) -> bool:
    """Download an image from the given src URL."""
    try:
        if img_src.startswith("data:image"):
            import base64
            _header, data = img_src.split(",", 1)
            save_path.write_bytes(base64.b64decode(data))
            return True

        # Use Playwright's request context to download (carries cookies)
        response = await page.context.request.get(img_src)
        if response.ok:
            body = await response.body()
            if len(body) < 5000:
                logger.warning(f"Downloaded image too small ({len(body)} bytes), likely not a real image")
                return False
            save_path.write_bytes(body)
            return True
        else:
            logger.warning(f"Download failed: HTTP {response.status}")
            return False
    except Exception as e:
        logger.error(f"Image download error: {e}")
        return False


async def generate_image_for_article(
    context: BrowserContext,
    article: dict,
    attempt: int = 0,
) -> Optional[Path]:
    """Generate a cover image for a single article via Gemini web UI.

    Returns the saved image path or None on failure.
    """
    article_id = article.get("id", "unknown")
    save_path = IMAGES_DIR / f"{article_id}.png"

    if save_path.exists() and save_path.stat().st_size > 5000:
        logger.info(f"Image already exists for {article_id} ({save_path.stat().st_size / 1024:.0f} KB), skipping")
        return save_path

    prompt = build_image_prompt(article)
    logger.info(f"Generating image for: {article.get('title', '')[:60]}...")

    page = await context.new_page()
    try:
        # Navigate to Gemini (new chat each time for clean state)
        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)  # Let Angular hydrate

        # Check if we're logged in
        if "accounts.google.com" in page.url:
            logger.error("Not logged into Google! Profile cookies may be stale.")
            logger.error("Fix: run with --refresh-profile to recopy fresh cookies")
            return None

        # Find and fill the textarea
        textarea = await page.wait_for_selector(SELECTOR_TEXTAREA, timeout=15000)
        if not textarea:
            logger.error("Could not find Gemini input textarea")
            return None

        await textarea.click()
        await page.wait_for_timeout(300)
        await textarea.fill(prompt)
        await page.wait_for_timeout(500)

        # Click send button
        send_btn = await page.query_selector(SELECTOR_SEND_BTN)
        if send_btn:
            await send_btn.click()
        else:
            # Fallback: press Enter
            await textarea.press("Enter")

        logger.info("Prompt sent, waiting for image generation...")

        # Wait for response to complete
        completed = await _wait_for_response_complete(page)

        # Find the generated image
        img_src = await _find_generated_image(page)

        if not img_src:
            if not completed:
                logger.warning(f"Response timed out and no image found for {article_id}")
            else:
                logger.warning(f"Response completed but no image generated for {article_id} (Gemini may have refused)")

            if attempt < MAX_RETRIES:
                logger.info(f"Retrying ({attempt + 1}/{MAX_RETRIES})...")
                await page.close()
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                return await generate_image_for_article(context, article, attempt + 1)
            return None

        # Download the image
        success = await _download_image(page, img_src, save_path)
        if success:
            logger.info(f"Image saved: {save_path.name} ({save_path.stat().st_size / 1024:.0f} KB)")
            return save_path
        else:
            logger.warning(f"Failed to download image for {article_id}")
            if attempt < MAX_RETRIES:
                await page.close()
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                return await generate_image_for_article(context, article, attempt + 1)
            return None

    except Exception as e:
        logger.error(f"Error generating image for {article_id}: {e}")
        if attempt < MAX_RETRIES:
            if not page.is_closed():
                await page.close()
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
            return await generate_image_for_article(context, article, attempt + 1)
        return None
    finally:
        if not page.is_closed():
            await page.close()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
async def run(
    state_file: Path,
    limit: int = 0,
    headless: bool = False,
    refresh_profile: bool = False,
) -> int:
    """Process articles from pipeline state file, generate images, update state."""
    if not state_file.exists():
        logger.error(f"State file not found: {state_file}")
        return 1

    state = json.loads(state_file.read_text())
    articles = state.get("articles", [])

    # Filter to enriched articles only
    enriched = [a for a in articles if a.get("enrichment")]
    if not enriched:
        logger.warning("No enriched articles found in state file")
        return 0

    if limit > 0:
        enriched = enriched[:limit]

    logger.info(f"Generating images for {len(enriched)} enriched articles")

    # Launch browser — prefer CDP (real Chrome, best compatibility), fallback to
    # Playwright persistent context with copied Chrome profile (works headless/nightly)
    async with async_playwright() as p:
        use_cdp = True
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            logger.info("Connected to Chrome via CDP")
        except Exception as e:
            logger.warning(f"CDP not available ({e}) — falling back to Playwright persistent context")
            use_cdp = False
            # Copy / reuse Chrome profile so Google cookies are present
            profile_dir = ensure_chrome_profile(force_refresh=refresh_profile)
            context = await p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--start-minimized",
                ],
                no_viewport=True,
            )

        generated = 0
        failed = 0
        login_failed = False

        for i, article in enumerate(enriched):
            article_id = article.get("id", f"article_{i}")
            logger.info(f"[{i + 1}/{len(enriched)}] Processing: {article.get('title', '')[:50]}...")

            img_path = await generate_image_for_article(context, article)

            if img_path:
                # Update article in state with image path
                article["image_path"] = str(img_path)
                article["image_url"] = f"images/{img_path.name}"
                generated += 1
            elif img_path is None and not login_failed:
                # Check if this was a login failure (stop all further attempts)
                test_page = await context.new_page()
                await test_page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=15000)
                await test_page.wait_for_timeout(2000)
                if "accounts.google.com" in test_page.url:
                    logger.error("Login failed — aborting remaining articles. Run with --refresh-profile")
                    login_failed = True
                    await test_page.close()
                    failed += len(enriched) - i
                    break
                await test_page.close()
                failed += 1
            else:
                failed += 1

            # Delay between requests
            if i < len(enriched) - 1:
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        await context.close()
        if use_cdp:
            await browser.close()

    # Save updated state back
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    logger.info(f"State updated: {state_file.name}")
    logger.info(f"Results: {generated} generated, {failed} failed out of {len(enriched)}")

    return 0 if generated > 0 or failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Gemini Image Generator for Intel Pipeline")
    parser.add_argument("state_file", type=Path, help="Path to pipeline state JSON file")
    parser.add_argument("--limit", type=int, default=0, help="Max images to generate (0 = all)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--refresh-profile", action="store_true", help="Force recopy Chrome profile cookies")
    args = parser.parse_args()

    return asyncio.run(run(args.state_file, args.limit, args.headless, args.refresh_profile))


if __name__ == "__main__":
    sys.exit(main())
