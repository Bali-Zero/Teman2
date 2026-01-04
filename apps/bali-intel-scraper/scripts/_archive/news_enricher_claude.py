#!/usr/bin/env python3
"""
News Enricher using Claude Max Subscription
Processes raw news articles and enriches them with AI analysis

Uses `claude -p` CLI which runs on your Claude Max subscription (no API costs!)
"""

import subprocess
import json
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/news_enricher_{time}.log", rotation="1 day", retention="7 days")


class ClaudeNewsEnricher:
    """Enrich news articles using Claude Max subscription via CLI"""

    ENRICHMENT_PROMPT = """You are the Senior Editor at Bali Zero, an Intelligent Business Operating System for expats and investors in Indonesia.
Analizza questa news e rispondi SOLO con JSON valido (nessun testo prima o dopo):

ROLE:
- Sei "L'Insider Intelligente" - l'esperto che legge le leggi noiose e dice solo cosa conta.
- Tono: "Autorevolezza Rilassata". Come un advisor esperto davanti a un caffè.

NEWS TITLE: {title}
NEWS CONTENT: {content}
SOURCE: {source}

Rispondi con questo formato JSON esatto:
{{
  "relevance_score": <numero 0-100, quanto è rilevante per expat/investitori a Bali>,
  "category": "<immigration|business|tax|property|lifestyle|tech|legal>",
  "priority": "<high|medium|low>",
  "ai_summary": "<Executive Summary professionale in inglese, max 280 caratteri, focus sul benefit/rischio>",
  "key_points": ["<punto chiave 1 specifico>", "<punto chiave 2 specifico>", "<punto chiave 3 specifico>"],
  "ai_tags": ["<tag1>", "<tag2>", "<tag3>"],
  "is_relevant": <true se score >= 40, false altrimenti>,
  "bali_zero_take": "<interpretazione strategica breve: cosa non dicono i giornali>"
}}"""

    def __init__(self, api_url: str = "https://balizero.com"):
        self.api_url = api_url

    def enrich_with_claude(self, article: Dict) -> Optional[Dict]:
        """Call Claude CLI to enrich a single article"""
        prompt = self.ENRICHMENT_PROMPT.format(
            title=article.get("title", ""),
            content=article.get("content", article.get("summary", "")),
            source=article.get("source", "Unknown"),
        )

        try:
            # Call Claude CLI with -p (print mode) - uses your subscription!
            result = subprocess.run(
                ["claude", "-p", "--output-format", "text", prompt],
                capture_output=True,
                text=True,
                timeout=180,  # 180 second timeout (Claude can be slow to start)
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return None

            # Parse JSON from response
            response_text = result.stdout.strip()

            # Extract JSON from markdown code block if present
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            enrichment = json.loads(response_text)
            logger.success(
                f"Enriched: {article['title'][:50]}... (score: {enrichment.get('relevance_score', 'N/A')})"
            )
            return enrichment

        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLI timeout for: {article['title'][:50]}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw response: {result.stdout[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error enriching article: {e}")
            return None

    async def fetch_pending_articles(self) -> List[Dict]:
        """Fetch articles that need enrichment from API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get articles without AI enrichment
                response = await client.get(
                    f"{self.api_url}/api/news",
                    params={"needs_enrichment": "true", "limit": 20},
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        articles = data.get("data", [])
                        # Filter articles without enrichment
                        pending = [a for a in articles if not a.get("ai_summary")]
                        logger.info(f"Found {len(pending)} articles needing enrichment")
                        return pending

            return []
        except Exception as e:
            logger.error(f"Error fetching articles: {e}")
            return []

    async def update_article(self, article_id: str, enrichment: Dict) -> bool:
        """Update article with enrichment data"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{self.api_url}/api/news/{article_id}",
                    json={
                        "ai_summary": enrichment.get("ai_summary"),
                        "ai_tags": enrichment.get("ai_tags", []),
                        "priority": enrichment.get("priority", "medium"),
                        "relevance_score": enrichment.get("relevance_score"),
                    },
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return False

    async def process_batch(self, limit: int = 10) -> Dict:
        """Process a batch of articles"""
        logger.info("=" * 60)
        logger.info("🤖 NEWS ENRICHER - Starting (Claude Max subscription)")
        logger.info(f"📅 Time: {datetime.now().isoformat()}")
        logger.info("=" * 60)

        articles = await self.fetch_pending_articles()

        if not articles:
            logger.info("No articles to process")
            return {"processed": 0, "enriched": 0, "skipped": 0}

        processed = 0
        enriched = 0
        skipped = 0

        for article in articles[:limit]:
            processed += 1

            # Enrich with Claude
            enrichment = self.enrich_with_claude(article)

            if enrichment:
                # Check relevance threshold
                if (
                    enrichment.get("is_relevant", True)
                    and enrichment.get("relevance_score", 0) >= 50
                ):
                    # Update article in database
                    if await self.update_article(article["id"], enrichment):
                        enriched += 1
                        logger.success(f"✅ Updated: {article['title'][:40]}...")
                    else:
                        logger.error(f"❌ Failed to update: {article['id']}")
                else:
                    skipped += 1
                    logger.info(
                        f"⏭️ Skipped (low relevance): {article['title'][:40]}..."
                    )
            else:
                logger.warning(f"⚠️ No enrichment for: {article['title'][:40]}...")

            # Rate limit: wait between requests
            await asyncio.sleep(2)

        logger.info("=" * 60)
        logger.info(
            f"📊 Results: Processed={processed}, Enriched={enriched}, Skipped={skipped}"
        )
        logger.info("=" * 60)

        return {"processed": processed, "enriched": enriched, "skipped": skipped}


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich news with Claude Max subscription"
    )
    parser.add_argument(
        "--api-url", default="https://balizero.com", help="BaliZero API URL"
    )
    parser.add_argument("--limit", type=int, default=10, help="Max articles to process")
    parser.add_argument("--test", action="store_true", help="Test with sample article")

    args = parser.parse_args()

    enricher = ClaudeNewsEnricher(api_url=args.api_url)

    if args.test:
        # Test with sample article
        sample = {
            "id": "test-123",
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "content": "The Indonesian government announced a new policy extending the digital nomad visa validity from 1 year to 5 years. The visa will cost $500 and allow holders to work remotely while living in Bali.",
            "source": "Jakarta Post",
        }

        logger.info("Testing with sample article...")
        enrichment = enricher.enrich_with_claude(sample)

        if enrichment:
            print("\n📋 ENRICHMENT RESULT:")
            print(json.dumps(enrichment, indent=2))
        else:
            print("❌ Enrichment failed")
    else:
        # Process batch
        result = await enricher.process_batch(limit=args.limit)
        print(f"\n✅ Done! {result}")


if __name__ == "__main__":
    asyncio.run(main())
