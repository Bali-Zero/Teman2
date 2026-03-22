"""
Articles Indexing API Submitter
================================
Sottomette gli articoli MDX di balizero.com a Google Indexing API.
Priorità basata su impressioni GSC reali (dati 28gg).

Usage:
    python articles_indexing_submit.py              # batch del giorno (200 URL)
    python articles_indexing_submit.py --dry-run    # mostra cosa farebbe
    python articles_indexing_submit.py --status     # stato avanzamento
    python articles_indexing_submit.py --batch 50   # batch personalizzato
    python articles_indexing_submit.py --reset      # azzera stato
"""

import argparse
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[ArticlesIdx] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent
ARTICLES_PATH = PROJECT_ROOT / "apps" / "mouth" / "src" / "content" / "articles"
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"
STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "articles_indexing_state.json"

SITE_BASE_URL = "https://balizero.com"
DAILY_LIMIT = 200
BATCH_DELAY_SEC = 0.5

# Folder → URL category mapping (mirrors apps/mouth/src/lib/blog/articles.ts)
CATEGORY_MAP: dict[str, str] = {
    "immigration": "immigration",
    "business": "business",
    "tax": "tax-legal",
    "tax-legal": "tax-legal",
    "property": "property",
    "lifestyle": "lifestyle",
    "digital-nomad": "lifestyle",
    "tech": "tech",
    "news": "business",
    "business_regulations": "business",
    "emerging_trends": "business",
    "bali_news": "lifestyle",
}

# GSC impressions (28gg) — ordine priorità decrescente
# Aggiornato 2026-03-11 da seo_guardian
GSC_PRIORITY: dict[str, int] = {
    "ota-data-crackdown-bali-2026": 1975,
    "indonesia-zero-tax-foreign-income-2026": 1937,
    "driving-license-foreigners": 797,
    "dengue-alert-2026": 536,
    "bali-digital-nomad-complete-guide": 483,
    "education-expat-children": 428,
    "golden-visa-2026-updates": 418,
    "constitutional-clash-bank-statements": 327,
    "emergency-contacts-indonesia": 226,
    "npwp-foreigners-guide": 225,
    "tax-residency-indonesia": 65,
    "rental-income-tax": 177,
    "perfect-storm-bali-2026": 151,
    "suwung-landfill-crisis": 118,
    "maritime-chaos-komodo": 104,
    "airbnb-bali-ban-truth": 89,
    "property-green-zone-alert": 86,
    "freelancing-legally-indonesia": 84,
    "global-citizenship-indonesia": 116,
}


def read_frontmatter(filepath: Path) -> dict[str, Any]:
    """Estrae frontmatter YAML da file MDX."""
    content = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ": " in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(": ")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def discover_articles() -> list[dict[str, Any]]:
    """Scansiona tutti gli articoli MDX e costruisce la lista URL con priorità."""
    articles: list[dict[str, Any]] = []

    for folder in ARTICLES_PATH.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        url_category = CATEGORY_MAP.get(folder.name, folder.name)

        for mdx_file in sorted(folder.glob("*.mdx")):
            # Skip conflict files only (NOT translations — we index all languages)
            if ".sync-conflict-" in mdx_file.name:
                continue

            # Detect language from filename
            lang = "en"
            for lang_suffix in [".id.mdx", ".it.mdx", ".fr.mdx", ".ru.mdx"]:
                if mdx_file.name.endswith(lang_suffix):
                    lang = lang_suffix[1:3]  # "id", "it", "fr", "ru"
                    break

            fm = read_frontmatter(mdx_file)
            slug = fm.get("slug") or mdx_file.stem
            no_index = fm.get("noIndex") == "true" or fm.get("noIndex") is True

            if no_index:
                continue  # Skip noIndex articles

            base_url = f"{SITE_BASE_URL}/{url_category}/{slug}"
            url = base_url if lang == "en" else f"{base_url}?lang={lang}"
            priority = GSC_PRIORITY.get(slug, 0)
            # Deprioritize translations slightly (English first)
            if lang != "en":
                priority = max(priority - 1, 0)

            # Use slug+lang as unique key to avoid collisions
            unique_key = f"{slug}:{lang}" if lang != "en" else slug

            articles.append({
                "slug": unique_key,
                "url": url,
                "category": url_category,
                "folder": folder.name,
                "priority": priority,
                "title": fm.get("title", slug),
                "lang": lang,
            })

    # Sort: GSC priority first (highest impressions), then alphabetical
    articles.sort(key=lambda x: (-x["priority"], x["slug"]))
    logger.info("Discovered %d indexable articles", len(articles))
    return articles


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"submitted": [], "failed": [], "last_run": None, "total_submitted": 0}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def build_service():
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    return build("indexing", "v3", credentials=creds, cache_discovery=False)


def submit_url(service, url: str, dry_run: bool = False) -> tuple[bool, str]:
    if dry_run:
        return True, "dry-run"
    try:
        service.urlNotifications().publish(
            body={"url": url, "type": "URL_UPDATED"}
        ).execute()
        return True, "ok"
    except HttpError as e:
        code = e.resp.status
        if code == 429:
            return False, "RATE_LIMIT"
        if code == 403:
            return False, f"FORBIDDEN: {e}"
        return False, f"HTTP_{code}"
    except Exception as e:
        return False, str(e)


def print_status(state: dict[str, Any], articles: list[dict]) -> None:
    total = len(articles)
    submitted_slugs = set(state.get("submitted", []))
    done = len(submitted_slugs)
    remaining = [a for a in articles if a["slug"] not in submitted_slugs]
    failed = state.get("failed", [])

    print(f"\n=== Articles Indexing Status ===")
    print(f"Total articles: {total}")
    print(f"Submitted:      {done} ({done/total*100:.1f}%)")
    print(f"Remaining:      {len(remaining)}")
    print(f"Failed:         {len(failed)}")
    print(f"Last run:       {state.get('last_run', 'never')}")
    if remaining[:5]:
        print(f"\nNext up:")
        for a in remaining[:5]:
            gsc = f" [GSC: {a['priority']} imp]" if a["priority"] else ""
            print(f"  {a['url']}{gsc}")


def run_batch(batch_size: int = DAILY_LIMIT, dry_run: bool = False) -> None:
    from datetime import datetime

    articles = discover_articles()
    state = load_state()
    submitted_slugs = set(state.get("submitted", []))
    failed_slugs = set(state.get("failed", []))

    pending = [a for a in articles if a["slug"] not in submitted_slugs]

    if not pending:
        logger.info("All articles already submitted!")
        return

    logger.info("Pending: %d articles. Running batch of %d.", len(pending), batch_size)

    service = None if dry_run else build_service()
    batch = pending[:batch_size]

    ok_count = 0
    fail_count = 0
    rate_limit_hits = 0

    for i, article in enumerate(batch):
        url = article["url"]
        gsc_info = f" [GSC: {article['priority']} imp]" if article["priority"] else ""
        logger.info("[%d/%d] %s%s", i + 1, len(batch), url, gsc_info)

        success, reason = submit_url(service, url, dry_run)

        if success:
            state["submitted"].append(article["slug"])
            ok_count += 1
        else:
            if reason == "RATE_LIMIT":
                rate_limit_hits += 1
                logger.warning("Rate limit hit — sleeping 60s")
                time.sleep(60)
                # Retry once
                success2, reason2 = submit_url(service, url, dry_run)
                if success2:
                    state["submitted"].append(article["slug"])
                    ok_count += 1
                else:
                    state["failed"].append(article["slug"])
                    fail_count += 1
                    logger.error("Failed after retry: %s — %s", url, reason2)
            else:
                state["failed"].append(article["slug"])
                fail_count += 1
                logger.error("Failed: %s — %s", url, reason)

        save_state(state)
        time.sleep(BATCH_DELAY_SEC)

    state["last_run"] = datetime.now().isoformat()
    state["total_submitted"] = len(state["submitted"])
    save_state(state)

    total = len(articles)
    done = len(state["submitted"])
    logger.info(
        "Batch done. OK: %d, Failed: %d, Rate limits: %d | Total: %d/%d (%.1f%%)",
        ok_count, fail_count, rate_limit_hits, done, total, done / total * 100,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Articles Indexing API Submitter")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--batch", type=int, default=DAILY_LIMIT)
    args = parser.parse_args()

    if args.reset:
        STATE_PATH.unlink(missing_ok=True)
        logger.info("State reset.")
        return

    articles = discover_articles()

    if args.status:
        state = load_state()
        print_status(state, articles)
        return

    run_batch(batch_size=args.batch, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
