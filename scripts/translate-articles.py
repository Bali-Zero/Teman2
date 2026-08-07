#!/usr/bin/env python3
"""
Batch translate MDX articles using Ollama (local LLM).

Usage:
    python scripts/translate-articles.py --lang both --limit 5 --dry-run
    python scripts/translate-articles.py --lang id --category immigration --limit 10 --force
    python scripts/translate-articles.py --lang it --skip-existing
"""

import argparse
import hashlib
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
REPO_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = REPO_ROOT / "apps" / "mouth" / "src" / "content" / "articles"

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
    # Insert before the closing delimiter, keeping the tail verbatim — the
    # rstrip form used to swallow the blank line before the body (see
    # stamp_frontmatter).
    head, sep, tail = fm_block.rpartition("---")
    if not sep:
        return fm_block
    return f'{head}locale: "{locale}"\n{sep}{tail}'


# ── Freshness stamp (scar 2026-07-28) ──────────────────────────────────────
#
# This organ used to skip on the EXISTENCE of the target file:
#
#     if out_path.exists(): return False   # "SKIP (exists)"
#
# so every translation was frozen the moment it was first written. Correcting
# an English article never reached its translations, and the hourly run
# reported ``DONE: 0 translated, 1592 skipped/failed in 0s`` — green, loud and
# empty, every hour. Measured when it was found: 1275 of 2664 translations
# (48%) were behind their English source.
#
# We now skip on FRESHNESS: each translation records the sha256 of the source
# BODY it was made from. Deliberately NOT mtime — a fresh clone or checkout
# stamps every file with the checkout time, so an mtime comparison would call
# the whole corpus fresh (or stale) depending on nothing but checkout order.
# The digest travels inside the file, so it survives clone, rsync and rebase.
STAMP_FIELD = "source_sha256"
_STAMP_RE = re.compile(
    rf'^{STAMP_FIELD}:\s*"?([0-9a-f]{{64}})"?\s*$', re.MULTILINE
)


def source_digest(body: str) -> str:
    """sha256 of the source BODY (frontmatter excluded — see stamp_frontmatter)."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_stamp(fm_block: str) -> str | None:
    """Return the recorded source digest, or None if this file predates stamping."""
    m = _STAMP_RE.search(fm_block)
    return m.group(1) if m else None


def stamp_frontmatter(fm_block: str, digest: str) -> str:
    """Set source_sha256: in frontmatter. Add it if missing.

    Inserts before the closing delimiter with rpartition and re-appends the
    tail VERBATIM. The obvious `fm_block.rstrip().rsplit("---", 1)[0] + ...`
    is wrong here, and measurably so: FRONTMATTER_RE closes on ``---\\s*\\n``
    and ``\\s`` eats newlines, so the blank line that separates frontmatter
    from body is captured INSIDE fm_block — rstrip then deletes it. Stamping
    the corpus that way produced `1294 insertions(+), 1009 deletions(-)`:
    a metadata-only pass silently reflowing a thousand article bodies.
    """
    if _STAMP_RE.search(fm_block):
        return _STAMP_RE.sub(f'{STAMP_FIELD}: "{digest}"', fm_block)
    head, sep, tail = fm_block.rpartition("---")
    if not sep:  # no delimiter at all — leave it alone rather than corrupt it
        return fm_block
    return f'{head}{STAMP_FIELD}: "{digest}"\n{sep}{tail}'


def freshness_verdict(existing_fm: str | None, digest: str) -> str:
    """Decide what to do with an existing translation. Pure — unit-tested.

    'absent'    — no translation yet, write one
    'unstamped' — predates stamping: we CANNOT tell if it is current, so we
                  never re-translate it on a guess. It is counted and reported
                  until someone stamps it deliberately (--stamp-baseline).
    'fresh'     — the source body has not changed since this was written
    'stale'     — the source body HAS changed: re-translate
    """
    if existing_fm is None:
        return "absent"
    stamp = read_stamp(existing_fm)
    if stamp is None:
        return "unstamped"
    return "fresh" if stamp == digest else "stale"


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


# ── Orphan detection (2026-08-07) ───────────────────────────────────────────
#
# discover_articles() derives every translation target as
# ``<slug>.mdx`` -> ``<slug>.<lang>.mdx`` IN THE SAME DIRECTORY. If an
# English article is later moved to a different category folder, any
# translation left behind next to the old (now-absent) source becomes
# permanently invisible to this organ: never fresh, never stale, never
# counted — it is not reachable from discover_articles() by construction,
# so the freshness loop can silently drift from a whole-tree disk census
# forever with no signal anywhere.
#
# Measured live 2026-08-07: disk census of id+it translation files = 1593,
# while discover_articles() x {id,it} visits 1592 slots. The one-file gap is
# apps/mouth/src/content/articles/immigration/driving-license-bali-foreigners-2026.id.mdx
# — its English source and .it sibling both live under lifestyle/ now; the
# immigration/ copy has no <slug>.mdx neighbour left.
#
# This pass is REPORT-ONLY by design: it costs nothing (pure filesystem
# glob+exists, no model call), covers all four language suffixes regardless
# of --lang/targets, and must never change `targets`, never trigger a
# translation, and never affect the process exit code. Disposition of an
# orphan (move the file back, delete it, restore the English source) is a
# client-facing content call for a human, not something this cron decides.
_ORPHAN_SUFFIX_RE = re.compile(r"^(.+)\.(id|it|ru|fr)\.mdx$")


def discover_orphan_translations(category: str | None = None) -> list[Path]:
    """Translation files whose English `<slug>.mdx` source is missing from
    their own directory. Pure filesystem check — no model, no writes."""
    orphans: list[Path] = []
    if not ARTICLES_DIR.exists():
        return orphans

    for cat_dir in sorted(ARTICLES_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        if category and category != "all" and cat_dir.name != category:
            continue

        for mdx_file in sorted(cat_dir.glob("*.mdx")):
            name = mdx_file.name
            if ".sync-conflict-" in name:
                continue
            m = _ORPHAN_SUFFIX_RE.match(name)
            if not m:
                continue  # an English source itself, not a translation
            stem = m.group(1)
            src_path = cat_dir / f"{stem}.mdx"
            if not src_path.exists():
                orphans.append(mdx_file)

    return orphans


def _log_orphans(orphans: list[Path]) -> None:
    """Shared reporting for both --dry-run and the real run. Never gates."""
    if not orphans:
        return
    logger.warning(
        f"\n{len(orphans)} ORPHAN translation(s): no <slug>.mdx source in the "
        f"same directory (never fresh/stale/unstamped — invisible to every "
        f"freshness check above). Report only — not translated, not moved:"
    )
    for o in orphans:
        try:
            rel = o.relative_to(REPO_ROOT)
        except ValueError:
            rel = o
        logger.warning(f"  ORPHAN: {rel}")


def translate_article(article: dict, lang: str, force: bool, skip_existing: bool) -> str:
    """Translate one article. Returns a verdict (see freshness_verdict + main)."""
    src_path: Path = article["path"]
    slug = article["slug"]
    out_path = src_path.parent / f"{slug}.{lang}.mdx"

    # Read source FIRST — the freshness decision needs its digest, so this can
    # no longer wait until after the exists-check.
    # An index entry whose .mdx vanished (e.g. a deleted test/ article) must
    # skip, not kill the whole run for every article after it
    # (translate_hourly heartbeat was degraded exactly this way).
    try:
        source = src_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"  SKIP (source vanished): {src_path}")
        return "skipped"
    fm_block, body = split_frontmatter(source)

    if not body.strip():
        logger.warning(f"  SKIP (empty body): {src_path.name}")
        return "skipped"

    digest = source_digest(body)

    existing_fm: str | None = None
    if out_path.exists():
        if skip_existing:
            logger.info(f"  SKIP (exists): {out_path.name}")
            return "skipped"
        existing_fm, _ = split_frontmatter(out_path.read_text(encoding="utf-8"))

    verdict = freshness_verdict(existing_fm, digest)

    if verdict == "fresh" and not force:
        # Source body unchanged: leave the file completely alone.
        #
        # An earlier draft ALSO re-derived the translation's frontmatter from
        # the source here, on the theory that it is a verbatim copy and free
        # to refresh. Measured before shipping: 1398 of 2559 translations
        # carry frontmatter that DIFFERS from their source — seoDescription,
        # excerpt, faq, seoTitle, translated by hand. "Refreshing" them would
        # have reverted all of it to English. Frontmatter propagation is not
        # worth re-opening, on the metadata, the exact hole this commit
        # closes on the body.
        logger.info(f"  FRESH (source unchanged): {out_path.name}")
        return "fresh"

    if verdict == "unstamped" and not force:
        # Predates stamping. We cannot tell whether it matches its source, and
        # guessing costs either a wrong page or an overwritten human fix — so
        # we do neither. It stays visible in the run summary until stamped.
        logger.info(f"  UNSTAMPED (no {STAMP_FIELD}, left untouched): {out_path.name}")
        return "unstamped"

    if verdict == "stale":
        logger.info(f"  STALE (source changed since translation): {out_path.name}")
    elif verdict != "absent":
        logger.info(f"  Replacing old translation: {out_path.name}")

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
        return "failed"
    elapsed = time.time() - t0

    if not translated or len(translated) < 50:
        logger.error(f"  FAIL: Translation too short ({len(translated)} chars) for {slug}")
        return "failed"

    leak = looks_like_reasoning_leak(translated)
    if leak:
        # Never persist chain-of-thought as an article (scar 2026-07-21). Fail
        # loudly so a re-run/human handles it — do NOT write partial garbage.
        logger.error(f"  FAIL: reasoning leak in output for {slug} [{leak!r}] — not written")
        return "failed"

    # Build output. The stamp goes in with the text it describes: a translation
    # written without its digest would read as 'unstamped' forever.
    #
    # On a RE-translation, keep the frontmatter the file already has and only
    # re-stamp it. The stale thing is the body; the metadata may well have been
    # translated by hand (measured: 1398 of 2559 translations carry frontmatter
    # that differs from their source), and deriving it from the English source
    # again would silently revert that work. A new file has no frontmatter of
    # its own, so it still inherits the source's.
    base_fm = existing_fm if existing_fm else fm_block
    patched_fm = stamp_frontmatter(patch_frontmatter_locale(base_fm, lang), digest)
    output = patched_fm + translated + "\n"

    # Write
    out_path.write_text(output, encoding="utf-8")
    logger.info(f"  OK: {out_path.name} ({len(translated)} chars, {elapsed:.1f}s)")
    return "retranslated" if verdict == "stale" else "written"


def stamp_baseline(list_path: Path) -> int:
    """Stamp already-existing translations with their CURRENT source digest.

    Calls no model and translates nothing: it only records "this translation
    corresponds to the source as it stands now". That is a CLAIM, so it is
    never made in bulk by default — the caller must pass an explicit list of
    files it is prepared to vouch for. Stamping the whole corpus would bless
    the stale half as fresh and make it invisible, which is the same defect
    as skipping on existence, one level up.

    Returns a process exit code.
    """
    try:
        raw = list_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error(f"Cannot read --stamp-baseline list {list_path}: {exc}")
        return 1

    entries = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("#")]
    if not entries:
        # An empty set must not read as success — it looks identical to
        # "stamped everything" in the summary line otherwise.
        logger.error(f"--stamp-baseline list {list_path} is empty — refusing to report success")
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    stamped = already = missing = 0
    for entry in entries:
        out_path = Path(entry)
        if not out_path.is_absolute():
            out_path = repo_root / out_path
        m = re.match(r"^(?P<stem>.+)\.(?P<lang>id|it|ru|fr)\.mdx$", out_path.name)
        if not m or not out_path.exists():
            logger.warning(f"  SKIP (not a translation, or absent): {entry}")
            missing += 1
            continue
        src_path = out_path.parent / f"{m.group('stem')}.mdx"
        if not src_path.exists():
            logger.warning(f"  SKIP (source absent): {src_path.name}")
            missing += 1
            continue

        _, src_body = split_frontmatter(src_path.read_text(encoding="utf-8"))
        digest = source_digest(src_body)
        fm_block, body = split_frontmatter(out_path.read_text(encoding="utf-8"))
        if read_stamp(fm_block) == digest:
            already += 1
            continue
        out_path.write_text(stamp_frontmatter(fm_block, digest) + body, encoding="utf-8")
        stamped += 1

    logger.info(f"\nSTAMPED: {stamped} newly stamped, {already} already current, {missing} unusable")
    return 0 if missing == 0 else 2


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
                        help="Re-translate regardless of freshness (default: only stale)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip articles that already have translations")
    parser.add_argument("--stamp-baseline", metavar="LISTFILE", default=None,
                        help="Record the current source digest into the translations named in "
                             "LISTFILE (one path per line). Calls no model. The list is required "
                             "on purpose: stamping is a claim that those translations are current.")
    parser.add_argument("--model", default=None,
                        help="Override Ollama model (default: aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m)")
    args = parser.parse_args()

    global MODEL
    if args.model:
        MODEL = args.model

    if args.stamp_baseline:
        # Runs before the Ollama reachability check on purpose: stamping needs
        # no model, and must stay usable when the model host is down.
        sys.exit(stamp_baseline(Path(args.stamp_baseline)))

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

    # Orphan translations (2026-08-07): scanned once, over the full category
    # scope, independent of --slug/--limit/--lang — report-only, never gates.
    orphans = discover_orphan_translations(args.category)

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
        # The dry run answers the same question the real run does — freshness,
        # not existence. A preview that says SKIP where the run re-translates
        # is worse than no preview.
        logger.info("\n=== DRY RUN ===")
        preview: dict[str, int] = {}
        for art in articles:
            try:
                _, src_body = split_frontmatter(art["path"].read_text(encoding="utf-8"))
            except OSError:
                continue
            digest = source_digest(src_body)
            for lang in targets:
                out = art["path"].parent / f"{art['slug']}.{lang}.mdx"
                existing_fm = None
                if out.exists():
                    existing_fm, _ = split_frontmatter(out.read_text(encoding="utf-8"))
                verdict = freshness_verdict(existing_fm, digest)
                action = {
                    "absent": "CREATE",
                    "stale": "RE-TRANSLATE",
                    "fresh": "FORCE" if args.force else "fresh",
                    "unstamped": "FORCE" if args.force else "unstamped",
                }[verdict]
                preview[action] = preview.get(action, 0) + 1
                if action in ("CREATE", "RE-TRANSLATE", "FORCE"):
                    logger.info(f"  [{action}] {art['category']}/{art['slug']}.{lang}.mdx")
        summary = ", ".join(f"{v} {k}" for k, v in sorted(preview.items())) or "nothing"
        orphan_note = f", {len(orphans)} orphan(s)" if orphans else ""
        logger.info(f"\nTotal: {len(articles)} articles x {len(targets)} languages — {summary}{orphan_note}")
        _log_orphans(orphans)
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
    tally: dict[str, int] = {}
    t_start = time.time()

    for i, art in enumerate(articles, 1):
        logger.info(f"\n[{i}/{len(articles)}] {art['category']}/{art['slug']}")
        for lang in targets:
            verdict = translate_article(art, lang, args.force, args.skip_existing)
            tally[verdict] = tally.get(verdict, 0) + 1

    elapsed = time.time() - t_start
    written = tally.get("written", 0) + tally.get("retranslated", 0)
    fresh = tally.get("fresh", 0)
    unstamped = tally.get("unstamped", 0)
    failed = tally.get("failed", 0)
    skipped = tally.get("skipped", 0)

    logger.info(f"\n{'='*60}")
    # 'skipped/failed' used to be ONE number, so a genuine failure was
    # indistinguishable from a file we deliberately left alone. Never merge
    # these two again: one is work, the other is damage.
    logger.info(
        f"DONE in {elapsed:.0f}s: {tally.get('written', 0)} new, "
        f"{tally.get('retranslated', 0)} re-translated (stale source), "
        f"{fresh} already fresh, "
        f"{unstamped} unstamped, {skipped} skipped, {failed} FAILED, "
        f"{len(orphans)} orphan(s)"
    )
    logger.info(f"Average: {elapsed/max(written,1):.1f}s per translation")
    if unstamped:
        logger.warning(
            f"{unstamped} translation(s) carry no {STAMP_FIELD} and are therefore invisible to "
            f"freshness checking. They are NOT auto-translated. To vouch for a set of them: "
            f"--stamp-baseline <listfile>"
        )
    _log_orphans(orphans)

    # Innervation W1.3 sidecar emission. Best-effort — never raises back to
    # the caller. The genome aggregator polls this file; absent file =
    # treated as silent (dead) in the next pulse, so a write failure
    # surfaces naturally without us needing alarmist error handling here.
    try:
        import json as _json
        from pathlib import Path as _Path
        out_dir = _Path.home() / ".organism" / "last_seen"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Health is judged on FRESHNESS, not on having done work.
        #
        # The 2026-05-09 mapping sent "0 translated, everything skipped" to
        # "ok — idle: nothing new to translate". Under skip-on-existence that
        # was true by construction; under skip-on-freshness it is the exact
        # state this organ must never call healthy, because "I skipped
        # everything" and "I cannot tell whether anything is current" print
        # the same. So: a run that leaves files it cannot vouch for is
        # DEGRADED, and says how many.
        if failed:
            sidecar_status = "degraded"
        elif unstamped:
            sidecar_status = "degraded"
        else:
            sidecar_status = "ok"  # every target is provably current
        # orphan_translations is informational ONLY — it must never flip
        # sidecar_status. Orphans are a pre-existing filesystem condition
        # (source moved category), not something this run caused or can fix;
        # an hourly cron that starts alarming on day-1 of a new counter is a
        # new W-class problem (Family #2), not a cure.
        (out_dir / "pro.translate_hourly.json").write_text(_json.dumps({
            "ts": time.time(),
            "status": sidecar_status,
            "organ_id": "pro.translate_hourly",
            "metadata": {
                "total": total,
                "written": written,
                "fresh": fresh,
                "unstamped": unstamped,
                "skipped": skipped,
                "failed": failed,
                "orphan_translations": len(orphans),
                "elapsed_s": round(elapsed, 1),
            },
        }), encoding="utf-8")
    except Exception as _exc:  # noqa: BLE001
        logger.warning(f"organ_last_seen emit failed for pro.translate_hourly: {_exc}")


if __name__ == "__main__":
    main()
