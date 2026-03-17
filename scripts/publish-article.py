#!/usr/bin/env python3
"""
publish-article.py — Full publishing pipeline for Bali Zero articles.

Usage:
    python scripts/publish-article.py --slug SLUG --category CATEGORY [options]

What it does (in order):
    1. VALIDATE   — check frontmatter, required fields, image exists + is real JPEG
    2. IMAGE      — optimize cover image (resize to 1920px, compress, real JPEG)
    3. SEO/GEO    — generate seoTitle, seoDescription, aiOptimization, faq via Ollama
    4. TRANSLATE  — translate to id, it, ru, fr via translate-articles.py
    5. HOMEPAGE   — if featured: true, set as hero_main in homepage-layout.json
    6. COMMIT     — git add + commit everything

Options:
    --slug SLUG             Article slug (required)
    --category CATEGORY     Article category (required)
    --lang LANG             Languages to translate: all|id|it|ru|fr|none (default: all)
    --hero                  Force set as hero_main even if featured: false
    --no-translate          Skip translation step
    --no-seo                Skip SEO/GEO generation
    --no-image              Skip image optimization
    --no-commit             Skip git commit
    --dry-run               Preview everything, write nothing
    --model MODEL           Ollama model (default: qwen3.5:9b)
    --force                 Re-run all steps even if already done
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "apps" / "mouth" / "src" / "content" / "articles"
PUBLIC_DIR = ROOT / "apps" / "mouth" / "public"
HOMEPAGE_LAYOUT = ROOT / "apps" / "mouth" / "src" / "content" / "homepage-layout.json"
TRANSLATE_SCRIPT = ROOT / "scripts" / "translate-articles.py"

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

VALID_CATEGORIES = {
    "immigration", "business", "tax-legal", "property",
    "lifestyle", "tech", "bali_news",
}

REQUIRED_FIELDS = ["title", "slug", "description", "excerpt", "category", "coverImage", "locale"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s \033[1m%(levelname)s\033[0m %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("publish")


# ── Frontmatter parser ─────────────────────────────────────────────────────

def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from MDX file. Returns (frontmatter_dict, content)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    end = text.index("---", 3)
    yaml_block = text[3:end].strip()
    content = text[end + 3:].strip()

    fm = {}
    for line in yaml_block.splitlines():
        if ": " in line and not line.startswith(" "):
            key, _, val = line.partition(": ")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            fm[key] = val
        elif line.startswith("  - "):
            # list item under last key
            last_key = list(fm.keys())[-1] if fm else None
            if last_key:
                if not isinstance(fm[last_key], list):
                    fm[last_key] = []
                fm[last_key].append(line.strip("  - ").strip().strip('"').strip("'"))

    return fm, content


def write_frontmatter(path: Path, fm: dict, content: str, dry_run: bool = False) -> None:
    """Write updated frontmatter back to MDX file."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f'  - "{item}"')
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, str) and any(c in v for c in [':', '#', '"', "'"]):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(content)
    new_text = "\n".join(lines)

    if dry_run:
        log.info(f"[DRY RUN] Would write frontmatter to {path.name}")
        return
    path.write_text(new_text, encoding="utf-8")


# ── Step 1: Validate ───────────────────────────────────────────────────────

def step_validate(article_path: Path, fm: dict) -> list[str]:
    """Returns list of errors. Empty = all good."""
    errors = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if not fm.get(field):
            errors.append(f"Missing required field: {field}")

    # Category valid
    cat = fm.get("category", "")
    if cat and cat not in VALID_CATEGORIES:
        errors.append(f"Invalid category '{cat}'. Valid: {', '.join(sorted(VALID_CATEGORIES))}")

    # coverImage exists and is real JPEG/PNG
    cover = fm.get("coverImage", "")
    if cover:
        # Strip leading slash, resolve relative to public/
        img_rel = cover.lstrip("/")
        img_path = PUBLIC_DIR / img_rel
        if not img_path.exists():
            errors.append(f"coverImage not found: {img_path}")
        else:
            # Check real file type
            try:
                from PIL import Image as PILImage
                with PILImage.open(img_path) as img:
                    fmt = img.format
                    if fmt not in ("JPEG", "PNG", "WEBP", "AVIF"):
                        errors.append(f"coverImage has unexpected format: {fmt} (expected JPEG/PNG/WEBP)")
            except Exception as e:
                errors.append(f"coverImage cannot be opened: {e}")

    # status should be published (warn, not error)
    status = fm.get("status", "draft")
    if status != "published":
        log.warning(f"Article status is '{status}' — will publish anyway")

    return errors


# ── Step 2: Image optimization ─────────────────────────────────────────────

def step_optimize_image(fm: dict, dry_run: bool = False) -> str | None:
    """
    Optimize cover image:
    - Ensure real JPEG (not PNG renamed)
    - Resize to max 1920px wide
    - Compress to ~85 quality
    - Strip EXIF metadata
    Returns new coverImage path or None if unchanged.
    """
    cover = fm.get("coverImage", "")
    if not cover:
        return None

    img_rel = cover.lstrip("/")
    img_path = PUBLIC_DIR / img_rel

    if not img_path.exists():
        log.warning(f"Image not found, skipping optimization: {img_path}")
        return None

    try:
        from PIL import Image as PILImage, ExifTags

        with PILImage.open(img_path) as img:
            original_fmt = img.format
            original_size = img_path.stat().st_size
            w, h = img.size

            needs_conversion = original_fmt != "JPEG"
            needs_resize = w > 1920
            needs_processing = needs_conversion or needs_resize or original_size > 500_000

            if not needs_processing:
                log.info(f"Image already optimized: {img_path.name} ({w}x{h}, {original_size//1024}KB)")
                return None

            log.info(f"Optimizing image: {img_path.name} ({original_fmt}, {w}x{h}, {original_size//1024}KB)")

            # Convert to RGB (strip alpha if PNG with transparency)
            if img.mode in ("RGBA", "LA", "P"):
                background = PILImage.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if too wide
            if w > 1920:
                ratio = 1920 / w
                new_h = int(h * ratio)
                img = img.resize((1920, new_h), PILImage.LANCZOS)
                log.info(f"  Resized: {w}x{h} → 1920x{new_h}")

            # Always save as real JPEG with correct extension
            new_ext = img_path.suffix.lower()
            if new_ext not in (".jpg", ".jpeg"):
                # Change extension to .jpg
                new_name = img_path.stem + ".jpg"
                new_path = img_path.parent / new_name
            else:
                new_path = img_path

            if dry_run:
                new_size_estimate = original_size // (3 if needs_conversion else 1)
                log.info(f"  [DRY RUN] Would save as JPEG to {new_path.name} (~{new_size_estimate//1024}KB)")
                return None

            # Save as JPEG, no EXIF
            img.save(new_path, format="JPEG", quality=85, optimize=True)
            new_size = new_path.stat().st_size
            log.info(f"  Saved: {new_path.name} ({new_size//1024}KB, -{(1 - new_size/original_size)*100:.0f}%)")

            # If we renamed (PNG→JPEG), delete old file and update coverImage
            if new_path != img_path:
                img_path.unlink()
                log.info(f"  Removed old file: {img_path.name}")
                return "/" + str(new_path.relative_to(PUBLIC_DIR))

    except ImportError:
        log.warning("PIL not available, skipping image optimization")
    except Exception as e:
        log.warning(f"Image optimization failed: {e}")

    return None


# ── Step 3: SEO/GEO via Ollama ─────────────────────────────────────────────

SEO_PROMPT = """You are an SEO expert for Indonesia/Bali content. Given this article, generate:

1. seoTitle: max 60 chars, compelling, includes primary keyword
2. seoDescription: max 155 chars, includes call-to-action, describes the article value
3. primaryQuestion: the main question this article answers (for featured snippets)
4. answerSnippet: 2-3 sentence direct answer to primaryQuestion (for AI citations)
5. faq: 3-4 FAQ pairs (question + answer) — questions people actually search for
6. tags: 5-8 SEO tags (lowercase, specific)

ARTICLE TITLE: {title}
CATEGORY: {category}
EXCERPT: {excerpt}

CONTENT (first 2000 chars):
{content_preview}

Respond ONLY with valid JSON, no markdown, no explanation:
{{
  "seoTitle": "...",
  "seoDescription": "...",
  "primaryQuestion": "...",
  "answerSnippet": "...",
  "faq": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "tags": ["tag1", "tag2", "tag3"]
}}"""


def step_generate_seo(fm: dict, content: str, model: str, dry_run: bool = False) -> dict:
    """Generate SEO metadata via Ollama. Returns dict of fields to merge into frontmatter."""
    import httpx

    title = fm.get("title", "")
    category = fm.get("category", "")
    excerpt = fm.get("excerpt", "")
    content_preview = content[:2000]

    prompt = SEO_PROMPT.format(
        title=title,
        category=category,
        excerpt=excerpt,
        content_preview=content_preview,
    )

    if dry_run:
        log.info("[DRY RUN] Would generate SEO/GEO via Ollama")
        return {}

    log.info(f"Generating SEO/GEO via Ollama ({model})...")
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.3}},
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json().get("response", "")

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            log.warning("No JSON found in SEO response, skipping")
            return {}

        data = json.loads(json_match.group())

        result = {}

        seo_title = data.get("seoTitle", "")
        if seo_title and not fm.get("seoTitle"):
            result["seoTitle"] = seo_title[:60]

        seo_desc = data.get("seoDescription", "")
        if seo_desc and not fm.get("seoDescription"):
            result["seoDescription"] = seo_desc[:155]

        # Store aiOptimization as JSON string in frontmatter
        primary_q = data.get("primaryQuestion", "")
        answer = data.get("answerSnippet", "")
        if primary_q and answer:
            result["aiOptimization_primaryQuestion"] = primary_q
            result["aiOptimization_answerSnippet"] = answer

        # Merge tags
        new_tags = data.get("tags", [])
        existing_tags = fm.get("tags", [])
        if isinstance(existing_tags, str):
            existing_tags = [existing_tags]
        merged_tags = list(dict.fromkeys(existing_tags + new_tags))[:10]
        if merged_tags != existing_tags:
            result["tags"] = merged_tags

        log.info(f"  seoTitle: {result.get('seoTitle', '(kept existing)')}")
        log.info(f"  seoDescription: {result.get('seoDescription', '(kept existing)')[:60]}...")
        log.info(f"  FAQ items: {len(data.get('faq', []))}")

        # Store FAQ separately for writing
        result["_faq"] = data.get("faq", [])

        return result

    except Exception as e:
        log.warning(f"SEO generation failed: {e}")
        return {}


# ── Step 4: Translate ──────────────────────────────────────────────────────

def step_translate(slug: str, category: str, lang: str, model: str, force: bool, dry_run: bool) -> bool:
    """Run translate-articles.py for the given article."""
    if lang == "none":
        log.info("Translation skipped (--no-translate)")
        return True

    cmd = [
        sys.executable, str(TRANSLATE_SCRIPT),
        "--slug", slug,
        "--category", category,
        "--lang", lang,
        "--model", model,
    ]
    if force:
        cmd.append("--force")
    else:
        cmd.append("--skip-existing")
    if dry_run:
        cmd.append("--dry-run")

    log.info(f"Translating to: {lang} ...")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True, timeout=3600)
        if result.returncode != 0:
            log.warning(f"Translation exited with code {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        log.warning("Translation timed out after 1h")
        return False
    except Exception as e:
        log.warning(f"Translation failed: {e}")
        return False


# ── Step 5: Homepage layout ────────────────────────────────────────────────

def step_update_homepage(slug: str, dry_run: bool = False) -> None:
    """Set article as hero_main in homepage-layout.json."""
    layout = json.loads(HOMEPAGE_LAYOUT.read_text())
    old_hero = layout.get("hero_main")

    if old_hero == slug:
        log.info(f"Already hero_main: {slug}")
        return

    # Shift existing heroes down
    layout["hero_5"] = layout.get("hero_4", layout.get("hero_5"))
    layout["hero_4"] = layout.get("hero_3", layout.get("hero_4"))
    layout["hero_3"] = layout.get("hero_2", layout.get("hero_3"))
    layout["hero_2"] = old_hero
    layout["hero_main"] = slug

    log.info(f"Set hero_main: {slug} (was: {old_hero})")
    log.info(f"  hero_2 → {layout['hero_2']}")

    if dry_run:
        log.info("[DRY RUN] Would update homepage-layout.json")
        return

    HOMEPAGE_LAYOUT.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")


# ── Step 6: Git commit ────────────────────────────────────────────────────

def step_commit(slug: str, category: str, dry_run: bool = False) -> None:
    """git add all article files + homepage-layout.json and commit."""
    article_glob = f"apps/mouth/src/content/articles/{category}/{slug}*.mdx"
    image_glob = "apps/mouth/public/static/news/"

    files_to_add = [
        article_glob,
        str(HOMEPAGE_LAYOUT.relative_to(ROOT)),
        image_glob,
    ]

    if dry_run:
        log.info(f"[DRY RUN] Would git add: {files_to_add}")
        log.info(f"[DRY RUN] Would commit: 'publish({category}): {slug}'")
        return

    for f in files_to_add:
        subprocess.run(["git", "add", f], cwd=ROOT, capture_output=True)

    msg = f"publish({category}): {slug} — SEO + translations + image optimized"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode == 0:
        log.info(f"Committed: {msg}")
    else:
        log.warning(f"Git commit output: {result.stdout.strip()} {result.stderr.strip()}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Full article publishing pipeline")
    parser.add_argument("--slug", required=True, help="Article slug")
    parser.add_argument("--category", required=True, help="Article category")
    parser.add_argument("--lang", default="all", help="Translation languages (all|none|id|it|ru|fr)")
    parser.add_argument("--hero", action="store_true", help="Force set as hero_main")
    parser.add_argument("--no-translate", action="store_true")
    parser.add_argument("--no-seo", action="store_true")
    parser.add_argument("--no-image", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="qwen3.5:9b", help="Ollama model for SEO/translation")
    parser.add_argument("--force", action="store_true", help="Re-run even if already done")
    args = parser.parse_args()

    slug = args.slug
    category = args.category
    dry_run = args.dry_run

    if dry_run:
        log.info("=== DRY RUN MODE — no files will be modified ===")

    # Find article file
    article_path = ARTICLES_DIR / category / f"{slug}.mdx"
    if not article_path.exists():
        log.error(f"Article not found: {article_path}")
        sys.exit(1)

    log.info(f"\n{'='*60}")
    log.info(f"Publishing: {slug} [{category}]")
    log.info(f"{'='*60}\n")

    # Parse frontmatter
    fm, content = parse_frontmatter(article_path)

    # ── Step 1: Validate ──────────────────────────────────────────────────
    log.info("STEP 1/6 — Validate")
    errors = step_validate(article_path, fm)
    if errors:
        log.error("Validation failed:")
        for e in errors:
            log.error(f"  ✗ {e}")
        sys.exit(1)
    log.info("  ✓ All checks passed\n")

    # ── Step 2: Image optimization ────────────────────────────────────────
    if not args.no_image:
        log.info("STEP 2/6 — Optimize image")
        new_cover = step_optimize_image(fm, dry_run)
        if new_cover:
            fm["coverImage"] = new_cover
            log.info(f"  ✓ Updated coverImage → {new_cover}\n")
        else:
            log.info("  ✓ Image OK (no changes)\n")
    else:
        log.info("STEP 2/6 — Image optimization skipped\n")

    # ── Step 3: SEO/GEO ──────────────────────────────────────────────────
    if not args.no_seo:
        log.info("STEP 3/6 — SEO/GEO generation")
        seo_data = step_generate_seo(fm, content, args.model, dry_run)
        if seo_data:
            faq_items = seo_data.pop("_faq", [])
            fm.update({k: v for k, v in seo_data.items() if not k.startswith("_")})

            # Write FAQ block to content if not already present and we have items
            if faq_items and "## FAQ" not in content and not dry_run:
                faq_md = "\n\n## FAQ\n\n"
                for item in faq_items:
                    faq_md += f"### {item['question']}\n\n{item['answer']}\n\n"
                content += faq_md
                log.info(f"  ✓ Added {len(faq_items)} FAQ items to content")

            if not dry_run:
                write_frontmatter(article_path, fm, content)
            log.info("  ✓ SEO/GEO metadata written\n")
        else:
            log.info("  ✓ SEO kept as-is (Ollama unavailable or fields already set)\n")
    else:
        log.info("STEP 3/6 — SEO generation skipped\n")

    # ── Step 4: Translate ────────────────────────────────────────────────
    if not args.no_translate:
        log.info("STEP 4/6 — Translate")
        lang = "none" if args.no_translate else args.lang
        ok = step_translate(slug, category, lang, args.model, args.force, dry_run)
        status = "✓ Done" if ok else "⚠ Partial (check logs)"
        log.info(f"  {status}\n")
    else:
        log.info("STEP 4/6 — Translation skipped\n")

    # ── Step 5: Homepage layout ──────────────────────────────────────────
    is_featured = fm.get("featured", False) is True or fm.get("featured") == "true"
    if is_featured or args.hero:
        log.info("STEP 5/6 — Update homepage (featured: true)")
        step_update_homepage(slug, dry_run)
        log.info("  ✓ Done\n")
    else:
        log.info("STEP 5/6 — Homepage update skipped (featured: false)\n")

    # ── Step 6: Commit ───────────────────────────────────────────────────
    if not args.no_commit:
        log.info("STEP 6/6 — Git commit")
        step_commit(slug, category, dry_run)
        log.info("  ✓ Done\n")
    else:
        log.info("STEP 6/6 — Commit skipped\n")

    log.info(f"{'='*60}")
    log.info(f"✅ Published: {slug}")
    log.info(f"   URL: https://www.balizero.com/{category}/{slug}")
    log.info(f"{'='*60}\n")

    if not dry_run and not args.no_commit:
        log.info("Now run: git push origin main")


if __name__ == "__main__":
    main()
