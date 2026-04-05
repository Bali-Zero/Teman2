#!/usr/bin/env python3
"""
BZ Content Broadcaster — Morning News Script + Audio Briefing

Runs AFTER the Intel Scraper pipeline (06:00 WITA).
Reads published articles from the latest pipeline run, generates:
  1. Morning News script (markdown) for NLM cinematic video
  2. Audio briefing for team via NLM studio_create on NB-11

Usage:
    python scripts/bz_content_broadcaster.py
    python scripts/bz_content_broadcaster.py --dry-run
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Paths
SCRAPER_DATA = Path(__file__).parent.parent / "apps" / "bali-intel-scraper" / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "apps" / "evaluator" / "nlm_deep_research" / "output"
NLM_CLI = "nlm"

# NB-11: Bali Zero Ops Live — WRITE PERMITTED (audio briefing generation)
NB_OPS_ID = "2072e518-e6f9-437d-93ea-f9037ec54052"

# NB Morning News — WRITE PERMITTED (cinematic video generation)
NB_MORNING_NEWS_ID = "7f12203a-fc7a-4ef9-b918-07c395a39d71"

# NOTE: NB core notebooks (NB-2/3/4/5/6) are READ-ONLY and must NEVER
# appear in write/create operations. Only NB_OPS_ID and NB_MORNING_NEWS_ID
# are write-permitted in this module.

# Domain priority for Morning News (1 story per domain)
DOMAIN_ORDER = ["immigration", "business", "tax", "property", "business_regulations"]


def find_latest_pipeline_output() -> Optional[Path]:
    """Find the most recent pipeline run state file.

    Checks both data/pipeline/ and /tmp fallback. Warns if the latest
    file is older than 8 hours (likely stale from a previous day).
    """
    candidates = []

    # Check primary location
    pipeline_dir = SCRAPER_DATA / "pipeline"
    if pipeline_dir.exists():
        candidates.extend(pipeline_dir.glob("run_*.json"))

    # Also check /tmp fallback (pipeline writes here on PermissionError)
    tmp_dir = Path("/tmp/intel_pipeline_runs")
    if tmp_dir.exists():
        candidates.extend(tmp_dir.glob("run_*.json"))

    if not candidates:
        return None

    # Sort by modification time (newest first)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest = candidates[0]

    # Staleness check
    age_hours = (datetime.now().timestamp() - latest.stat().st_mtime) / 3600
    if age_hours > 8:
        logger.warning(
            "Latest pipeline state is %.1fh old: %s — may be stale",
            age_hours, latest.name,
        )

    return latest


def load_enriched_articles(state_file: Path) -> List[Dict]:
    """Load enriched articles from a pipeline state file."""
    try:
        with open(state_file) as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Corrupted or unreadable pipeline state %s: %s", state_file.name, e)
        return []

    articles = state.get("articles", [])
    enriched = [a for a in articles if isinstance(a.get("enrichment"), dict) and a["enrichment"]]
    logger.info("Loaded %d enriched articles from %s", len(enriched), state_file.name)
    return enriched


def _normalize_domain(cat: str) -> str:
    """Normalize scraper category to Morning News domain."""
    if cat in ("tax-legal", "tax"):
        return "tax"
    if cat in ("legal", "compliance"):
        return "business_regulations"
    return cat


# Human-friendly labels for domains
DOMAIN_LABELS = {
    "immigration": "IMMIGRATION",
    "business": "COMPANY SETUP",
    "tax": "TAX & FISCAL",
    "property": "PROPERTY",
    "business_regulations": "COMPLIANCE",
}


def select_top_per_domain(articles: List[Dict]) -> List[Dict]:
    """Select top 1 article per domain, ordered by DOMAIN_ORDER."""
    by_domain: Dict[str, Dict] = {}
    for a in articles:
        cat = a.get("qwen_category", a.get("category", "general"))
        domain = _normalize_domain(cat)
        # Store the normalized domain on the article for later use
        a["_news_domain"] = domain

        if domain not in by_domain:
            by_domain[domain] = a
        elif a.get("quality_score", 0) > by_domain[domain].get("quality_score", 0):
            by_domain[domain] = a

    selected = []
    for domain in DOMAIN_ORDER:
        if domain in by_domain:
            selected.append(by_domain[domain])

    # Fill remaining slots from other domains
    for domain, article in by_domain.items():
        if domain not in DOMAIN_ORDER and len(selected) < 5:
            selected.append(article)

    return selected[:5]


def generate_morning_news_script(articles: List[Dict]) -> str:
    """Generate markdown script for Morning News video."""
    date_str = datetime.now().strftime("%B %d, %Y")
    sections = []

    sections.append(f"# BALI ZERO MORNING NEWS — {date_str}\n")
    sections.append("## OPENING\n")
    sections.append(
        f"The Indonesian regulatory landscape continues to evolve. "
        f"This week, {len(articles)} critical developments that every foreign "
        f"business owner in Bali needs to know.\n"
    )

    for i, article in enumerate(articles, 1):
        enr = article.get("enrichment", {})
        nlm = article.get("nlm_context", {})
        title = enr.get("headline", article.get("title", ""))
        facts = enr.get("the_facts", "")
        take = enr.get("bali_zero_take", "")
        next_steps = enr.get("next_steps", "")
        legal = nlm.get("legal_basis", "")

        domain = article.get("_news_domain", article.get("category", "general"))
        domain_label = DOMAIN_LABELS.get(domain, domain.upper().replace("_", " "))

        sections.append(f"## STORY {i}: {domain_label} — {title}\n")
        if facts:
            sections.append(f"{facts}\n")
        if legal:
            sections.append(f"**Legal basis:** {legal[:500]}\n")
        if take:
            sections.append(f"{take}\n")
        if next_steps:
            sections.append(f"**Action required:** {next_steps}\n")
        sections.append("---\n")

    sections.append("## CLOSING\n")
    sections.append(
        f"{len(articles)} stories. {len(articles)} sets of deadlines. "
        f"Indonesia's regulatory machinery is no longer passive. "
        f"Contact your Bali Zero consultant for a personalized compliance review.\n\n"
        f"This has been the Bali Zero Morning News for {date_str}.\n"
    )

    return "\n".join(sections)


def save_script(script: str) -> Optional[Path]:
    """Save morning news script to output directory."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = OUTPUT_DIR / f"{date_str}_morning_news_script.md"
        filepath.write_text(script)
        logger.info("Morning News script saved: %s", filepath)
        return filepath
    except OSError as e:
        logger.error("Failed to save Morning News script: %s", e)
        return None


def generate_audio_briefing(dry_run: bool = False) -> Optional[Path]:
    """Generate audio briefing via NLM studio_create on NB-11."""
    if dry_run:
        logger.info("[DRY RUN] Would generate audio briefing on NB-11")
        return None

    try:
        # NLM CLI syntax: nlm audio create <notebook_id> --format brief --confirm
        # Note: NLM audio does not support --focus or --lang flags.
        # Audio persona is controlled by the pinned note in NB-11.
        result = subprocess.run(
            [NLM_CLI, "audio", "create", NB_OPS_ID,
             "--format", "brief",
             "--confirm"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            logger.info("Audio briefing generation started on NB-11")
        else:
            logger.warning("Audio briefing failed: %s", result.stderr[:200])
    except Exception as e:
        logger.warning("Audio briefing error: %s", e)

    return None


def notify_telegram(message: str) -> None:
    """Send notification to Telegram."""
    import os
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "413539912")

    if not bot_token:
        logger.info("No TELEGRAM_BOT_TOKEN — skipping notification")
        return

    try:
        import httpx
        httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram notification failed: %s", type(e).__name__)


def main():
    parser = argparse.ArgumentParser(description="BZ Content Broadcaster")
    parser.add_argument("--dry-run", action="store_true", help="Don't generate media")
    args = parser.parse_args()

    # 1. Find latest pipeline output
    state_file = find_latest_pipeline_output()
    if not state_file:
        logger.error("No pipeline output found")
        sys.exit(1)

    # 2. Load enriched articles
    articles = load_enriched_articles(state_file)
    if not articles:
        logger.warning("No enriched articles — nothing to broadcast")
        sys.exit(0)

    # 3. Select top 5 (1 per domain)
    top5 = select_top_per_domain(articles)
    logger.info("Selected %d articles for Morning News", len(top5))

    # 4. Generate Morning News script
    script = generate_morning_news_script(top5)
    script_path = save_script(script)

    if args.dry_run:
        logger.info("[DRY RUN] Script generated at %s", script_path)
        logger.info("Script preview:\n%s", script[:2000])
        return

    # 5. Generate audio briefing
    generate_audio_briefing(dry_run=args.dry_run)

    # 6. Notify
    date_str = datetime.now().strftime("%Y-%m-%d")
    notify_telegram(
        f"*BZ Content Broadcaster*\n"
        f"Morning News script ready: `{date_str}_morning_news_script.md`\n"
        f"Audio briefing generating on NB-11.\n"
        f"Review script and trigger video when ready."
    )

    logger.info("Content Broadcaster complete")


if __name__ == "__main__":
    main()
