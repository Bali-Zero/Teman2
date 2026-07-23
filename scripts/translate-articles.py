#!/usr/bin/env python3
"""
Batch translate MDX articles using Ollama (local LLM).

Usage:
    python scripts/translate-articles.py --lang both --limit 5 --dry-run
    python scripts/translate-articles.py --lang id --category immigration --limit 10 --force
    python scripts/translate-articles.py --lang it --skip-existing
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

import httpx

# ── Configuration ──────────────────────────────────────────────────────────

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Default model: SEA-LION-32B-IT (SEA-tuned, present on the H24 host). The old
# gemma3:27b default was NOT pulled on the runner — the translate.hourly cron
# silently produced no output until OLLAMA_MODEL was overridden in the plist.
# Keep the code default in sync with the host so a manual run works out of the box.
MODEL = os.environ.get("OLLAMA_MODEL", "aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m")
ARTICLES_DIR = Path(__file__).resolve().parent.parent / "apps" / "mouth" / "src" / "content" / "articles"

LANG_NAMES = {
    "id": "Bahasa Indonesia",
    "it": "Italian",
    "ru": "Russian",
    "fr": "French",
}

VALID_CATEGORIES = [
    "immigration", "business", "tax-legal", "tax", "property",
    "lifestyle", "digital-nomad", "tech", "bali_news", "business_regulations",
]

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    # ops-hardening fix 2026-05-19: explicit sys.stdout.
    # Default basicConfig routes to sys.stderr, which sent 1438+
    # INFO "SKIP (exists)" lines per run to error.log (148 MB at
    # peak — biggest log noise in the system).
    stream=sys.stdout,
)
logger = logging.getLogger("translate")

# ── Prompt ─────────────────────────────────────────────────────────────────

TRANSLATION_PROMPT = """You are an expert translator specializing in legal, immigration, and business content about Indonesia.

Translate the following MDX article content from English to {lang_name}.

CRITICAL RULES:
1. Translate ONLY the human-readable text (headings, paragraphs, list items, alt text).
2. DO NOT translate or modify:
   - MDX/JSX component tags: <InfoCard>, <Checklist>, <CallToAction>, <ComparisonTable>, etc.
   - Component prop names and their string values (e.g. title="..." stays as-is only if it's a component prop)
   - Markdown links: keep the URL unchanged, translate only the link text [translated text](original-url)
   - Image paths and src attributes
   - Code blocks and inline code
   - HTML tags and attributes
   - Frontmatter (it is NOT included — only the body is given to you)
3. DO NOT translate proper nouns, acronyms, or Indonesian technical terms:
   KITAS, KITAP, KBLI, PT PMA, PT PMDN, NPWP, NIB, OSS, BKPM, RPTKA, IMTA, ITAS,
   Directorate General of Immigration, Kantor Imigrasi, Notaris, PPAT, Hak Pakai,
   Hak Guna Bangunan, Hak Milik, Surat Keterangan, Bali, Jakarta, Indonesia
4. Keep the same Markdown formatting (headings ##, bold **, italic *, lists -, numbered lists).
5. Output ONLY the translated content. No preamble, no explanation, no code fences.
6. Maintain the exact same structure and paragraph breaks as the original.

CONTENT TO TRANSLATE:
{content}"""

# ── Helpers ────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split MDX into (frontmatter_block, body). Frontmatter includes --- delimiters."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    end = m.end()
    return text[:end], text[end:]


def patch_frontmatter_locale(fm_block: str, locale: str) -> str:
    """Set locale: in frontmatter. Add it if missing."""
    if re.search(r'^locale:\s', fm_block, re.MULTILINE):
        return re.sub(r'^locale:\s.*$', f'locale: "{locale}"', fm_block, flags=re.MULTILINE)
    # Insert before closing ---
    return fm_block.rstrip().rsplit("---", 1)[0] + f'locale: "{locale}"\n---\n'


# Post-generation guard (scar 2026-07-21). The old pipeline wrote raw
# reasoning-model chain-of-thought straight into 20 .id.mdx files (``Thinking...``,
# ``Wait, looking at the input:``, ``TESTO DA TRADURRE``). ``think: false`` +
# the "no preamble" prompt make that rare now, but a model can still ignore both
# — so we REFUSE to write output that narrates its own translation process.
_REASONING_LEAK_RE = re.compile(
    r"thinking\.\.\.|<think>|\bwait,\s+(looking at|the input|the source|the original|the prompt)"
    r"|\bthe (input|source) text is\b|\blooking at the (input|source|prompt|original)\b"
    r"|\bonly the translation\b|\bno explanations?\b[\s.,:*]*(only|output|the translation)"
    r"|\brispondi solo con la traduzione\b|\btesto da tradurre\b|\bas an ai\b"
    r"|\*+\s*self[-\s]?correction|\bthe user (provided|forgot|wants|hasn'?t)\b",
    re.IGNORECASE,
)


def looks_like_reasoning_leak(text: str) -> str | None:
    """Return the offending snippet if the model leaked its reasoning, else None."""
    m = _REASONING_LEAK_RE.search(text)
    return m.group(0) if m else None


def call_ollama(prompt: str, timeout: float = 1200) -> str:
    """Call Ollama chat API. Returns the generated text."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 16384,
        },
    }
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=30)) as client:
        resp = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("message", {}).get("content", "").strip()


def discover_articles(category: str | None = None) -> list[dict]:
    """Find all English .mdx articles (excluding translations and sync conflicts)."""
    articles = []
    if not ARTICLES_DIR.exists():
        logger.error(f"Articles directory not found: {ARTICLES_DIR}")
        return articles

    for cat_dir in sorted(ARTICLES_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        if category and category != "all" and cat_dir.name != category:
            continue

        for mdx_file in sorted(cat_dir.glob("*.mdx")):
            name = mdx_file.name
            # Skip translation files and sync conflicts
            if (name.endswith(".id.mdx") or name.endswith(".it.mdx")
                    or name.endswith(".ru.mdx") or name.endswith(".fr.mdx")):
                continue
            if ".sync-conflict-" in name:
                continue

            slug = name.removesuffix(".mdx")
            if not slug:
                continue  # skip empty-slug files
            articles.append({
                "path": mdx_file,
                "category": cat_dir.name,
                "slug": slug,
            })

    return articles


def translate_article(article: dict, lang: str, force: bool, skip_existing: bool) -> bool:
    """Translate one article. Returns True if translation was written."""
    src_path: Path = article["path"]
    slug = article["slug"]
    out_path = src_path.parent / f"{slug}.{lang}.mdx"

    # Check existing
    if out_path.exists():
        if skip_existing:
            logger.info(f"  SKIP (exists): {out_path.name}")
            return False
        if force:
            logger.info(f"  Replacing old translation: {out_path.name}")
        else:
            logger.info(f"  SKIP (exists, use --force to replace): {out_path.name}")
            return False

    # Read source — an index entry whose .mdx vanished (e.g. a deleted
    # test/ article) must skip, not kill the whole run for every article
    # after it (translate_hourly heartbeat was degraded exactly this way).
    try:
        source = src_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"  SKIP (source vanished): {src_path}")
        return False
    fm_block, body = split_frontmatter(source)

    if not body.strip():
        logger.warning(f"  SKIP (empty body): {src_path.name}")
        return False

    # Truncate very long articles to avoid OOM (keep first ~12000 words)
    words = body.split()
    if len(words) > 12000:
        logger.warning(f"  Truncating from {len(words)} to 12000 words")
        body = " ".join(words[:12000])

    # Build prompt
    lang_name = LANG_NAMES[lang]
    prompt = TRANSLATION_PROMPT.format(lang_name=lang_name, content=body)

    # Call Ollama
    t0 = time.time()
    try:
        translated = call_ollama(prompt)
    except Exception as e:
        logger.error(f"  FAIL: Ollama error for {slug}: {e}")
        return False
    elapsed = time.time() - t0

    if not translated or len(translated) < 50:
        logger.error(f"  FAIL: Translation too short ({len(translated)} chars) for {slug}")
        return False

    leak = looks_like_reasoning_leak(translated)
    if leak:
        # Never persist chain-of-thought as an article (scar 2026-07-21). Fail
        # loudly so a re-run/human handles it — do NOT write partial garbage.
        logger.error(f"  FAIL: reasoning leak in output for {slug} [{leak!r}] — not written")
        return False

    # Build output
    patched_fm = patch_frontmatter_locale(fm_block, lang)
    output = patched_fm + translated + "\n"

    # Write
    out_path.write_text(output, encoding="utf-8")
    logger.info(f"  OK: {out_path.name} ({len(translated)} chars, {elapsed:.1f}s)")
    return True


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Translate MDX articles using Ollama")
    parser.add_argument("--lang", choices=["id", "it", "ru", "fr", "both", "all"], default="both",
                        help="Target language(s): id, it, ru, fr, both (id+it), all (id+it+ru+fr)")
    parser.add_argument("--category", default="all",
                        help="Article category folder (e.g., immigration, business, all)")
    parser.add_argument("--slug", default=None,
                        help="Translate only this specific article slug")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max articles to translate (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be translated without doing it")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing translations (default: skip)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip articles that already have translations")
    parser.add_argument("--model", default=None,
                        help="Override Ollama model (default: aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m)")
    args = parser.parse_args()

    global MODEL
    if args.model:
        MODEL = args.model

    # Determine target languages
    if args.lang == "both":
        targets = ["id", "it"]
    elif args.lang == "all":
        targets = ["id", "it", "ru", "fr"]
    else:
        targets = [args.lang]

    # Discover articles
    articles = discover_articles(args.category)
    if not articles:
        logger.error("No articles found. Check ARTICLES_DIR path.")
        sys.exit(1)

    # Filter by slug if specified
    if args.slug:
        articles = [a for a in articles if a["slug"] == args.slug]
        if not articles:
            logger.error(f"Slug '{args.slug}' not found in category '{args.category}'")
            sys.exit(1)

    if args.limit > 0:
        articles = articles[:args.limit]

    logger.info(f"Found {len(articles)} article(s) to process")
    logger.info(f"Target language(s): {', '.join(targets)}")
    logger.info(f"Model: {MODEL}")
    logger.info(f"Force: {args.force}, Skip existing: {args.skip_existing}")

    if args.dry_run:
        logger.info("\n=== DRY RUN ===")
        for art in articles:
            for lang in targets:
                out = art["path"].parent / f"{art['slug']}.{lang}.mdx"
                exists = out.exists()
                action = "REPLACE" if exists and args.force else "SKIP" if exists else "CREATE"
                logger.info(f"  [{action}] {art['category']}/{art['slug']}.{lang}.mdx")
        logger.info(f"\nTotal: {len(articles)} articles x {len(targets)} languages = {len(articles) * len(targets)} files")
        return

    # Check Ollama connectivity
    try:
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            if MODEL not in models:
                logger.error(f"Model '{MODEL}' not found. Available: {models}")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Cannot reach Ollama at {OLLAMA_URL}: {e}")
        sys.exit(1)

    # Translate
    total = len(articles) * len(targets)
    done = 0
    success = 0
    skipped = 0
    t_start = time.time()

    for i, art in enumerate(articles, 1):
        logger.info(f"\n[{i}/{len(articles)}] {art['category']}/{art['slug']}")
        for lang in targets:
            done += 1
            result = translate_article(art, lang, args.force, args.skip_existing)
            if result:
                success += 1
            elif result is False:
                # Could be skip or fail — counted in translate_article logging
                skipped += 1

    elapsed = time.time() - t_start
    logger.info(f"\n{'='*60}")
    logger.info(f"DONE: {success} translated, {skipped} skipped/failed in {elapsed:.0f}s")
    logger.info(f"Average: {elapsed/max(success,1):.1f}s per translation")

    # Innervation W1.3 sidecar emission. Best-effort — never raises back to
    # the caller. The genome aggregator polls this file; absent file =
    # treated as silent (dead) in the next pulse, so a write failure
    # surfaces naturally without us needing alarmist error handling here.
    try:
        import json as _json
        from pathlib import Path as _Path
        out_dir = _Path.home() / ".organism" / "last_seen"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Map: success=ok, partial-skipped = degraded, no work to do = ok-but-idle.
        # Note (2026-05-09): skipped==total + success==0 used to map to "fail",
        # but in steady state it just means "everything already translated" —
        # a healthy idle, not a failure. Reserve "fail" for genuine errors
        # (which would surface elsewhere as exceptions/non-zero exit codes).
        if total == 0 or success > 0 and skipped == 0:
            sidecar_status = "ok"
        elif success == 0 and skipped == total:
            sidecar_status = "ok"  # idle: nothing new to translate
        else:
            sidecar_status = "degraded"
        (out_dir / "pro.translate_hourly.json").write_text(_json.dumps({
            "ts": time.time(),
            "status": sidecar_status,
            "organ_id": "pro.translate_hourly",
            "metadata": {
                "total": total,
                "success": success,
                "skipped": skipped,
                "elapsed_s": round(elapsed, 1),
            },
        }), encoding="utf-8")
    except Exception as _exc:  # noqa: BLE001
        logger.warning(f"organ_last_seen emit failed for pro.translate_hourly: {_exc}")


if __name__ == "__main__":
    main()
