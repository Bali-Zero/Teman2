"""
BALI ZERO INTEL SCRAPER v2 - Resilient & Intelligent
=====================================================
Upgraded scraper with 3 major improvements:

1. UNBREAKABLE EXTRACTION (Llama Fallback)
   CSS -> Trafilatura -> Newspaper3k -> Llama LLM
   If selectors break, Llama understands the content anyway.

2. PRE-SCORING (Filter Before Save)
   Score articles BEFORE downloading full content.
   Saves disk space, avoids irrelevant content.

3. SEMANTIC DEDUPLICATION (Qdrant)
   Vector similarity instead of SHA-256 hash.
   Catches paraphrased/rewritten duplicates.

Cost: ~$0 (uses local Llama for scoring/extraction)
"""

import json
import httpx
import asyncio
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib
from pathlib import Path
from loguru import logger
from urllib.parse import urljoin
from pydantic import BaseModel, HttpUrl, field_validator, ValidationError
from fake_useragent import UserAgent

# Optional imports
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    import numpy as np

    QDRANT_OK = True
except ImportError:
    QDRANT_OK = False
    logger.warning("Qdrant not installed - using SHA-256 fallback for dedup")

try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_OK = True
except ImportError:
    EMBEDDINGS_OK = False
    logger.warning("sentence-transformers not installed - semantic dedup disabled")

# Import our modules
from smart_extractor import SmartExtractor
from ollama_scorer import OllamaScorer

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/scraper_v2_{time}.log", rotation="1 day", retention="7 days")


class ScrapedItem(BaseModel):
    """Validated scraped item with Pydantic"""

    title: str
    content: str
    url: HttpUrl
    source: str
    tier: str
    category: str
    scraped_at: str
    content_id: str
    relevance_score: int = 50
    score_reason: str = ""
    published_at: Optional[str] = "unknown"
    extraction_method: Optional[str] = "css"

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v):
        if len(v) < 100:
            raise ValueError(f"Content too short ({len(v)} chars, minimum 100)")
        return v

    @field_validator("title")
    @classmethod
    def validate_title_length(cls, v):
        if len(v) < 10:
            raise ValueError(f"Title too short ({len(v)} chars, minimum 10)")
        return v


class SemanticDeduplicator:
    """
    Semantic deduplication using Qdrant vector similarity.
    Catches paraphrased/rewritten articles that SHA-256 would miss.
    """

    def __init__(
        self,
        collection_name: str = "balizero_articles",
        similarity_threshold: float = 0.85,
        qdrant_url: str = "http://localhost:6333",
    ):
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.qdrant_url = qdrant_url

        # Initialize components
        self.qdrant: Optional[QdrantClient] = None
        self.encoder: Optional[SentenceTransformer] = None
        self.vector_dim = 384  # all-MiniLM-L6-v2 dimension

        # Fallback to SHA-256 if Qdrant not available
        self.use_semantic = False
        self.seen_hashes: set = set()

    async def initialize(self) -> bool:
        """Initialize Qdrant client and embedding model"""
        if not QDRANT_OK or not EMBEDDINGS_OK:
            logger.warning("Semantic dedup disabled - using SHA-256 fallback")
            return False

        try:
            # Load embedding model (runs locally, ~100MB)
            logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")

            # Connect to Qdrant
            self.qdrant = QdrantClient(url=self.qdrant_url, timeout=10)

            # Create collection if not exists
            collections = self.qdrant.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_dim, distance=Distance.COSINE
                    ),
                )

            self.use_semantic = True
            logger.success("Semantic deduplication enabled (Qdrant + MiniLM)")
            return True

        except Exception as e:
            logger.warning(f"Qdrant initialization failed: {e}")
            logger.info("Falling back to SHA-256 deduplication")
            return False

    def _hash_content(self, content: str) -> str:
        """SHA-256 hash for fallback dedup"""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def is_duplicate(self, title: str, content: str) -> Tuple[bool, str]:
        """
        Check if content is a duplicate.
        Returns (is_duplicate, content_id)
        """
        text_for_check = f"{title} {content[:500]}"

        if self.use_semantic and self.encoder and self.qdrant:
            try:
                # Generate embedding
                embedding = self.encoder.encode(text_for_check).tolist()

                # Search for similar vectors
                results = self.qdrant.search(
                    collection_name=self.collection_name,
                    query_vector=embedding,
                    limit=1,
                    score_threshold=self.similarity_threshold,
                )

                if results:
                    similarity = results[0].score
                    if similarity >= self.similarity_threshold:
                        existing_id = results[0].payload.get("content_id", "unknown")
                        logger.debug(
                            f"Semantic duplicate found (similarity: {similarity:.2f})"
                        )
                        return True, existing_id

                # Not a duplicate - generate new ID and store
                content_id = self._hash_content(text_for_check)

                # Add to Qdrant
                self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=[
                        PointStruct(
                            id=hash(content_id) % (2**63),  # Convert to int64
                            vector=embedding,
                            payload={
                                "content_id": content_id,
                                "title": title[:200],
                                "indexed_at": datetime.now().isoformat(),
                            },
                        )
                    ],
                )

                return False, content_id

            except Exception as e:
                logger.warning(f"Semantic check failed: {e}, using SHA-256 fallback")

        # Fallback to SHA-256
        content_id = self._hash_content(text_for_check)

        if content_id in self.seen_hashes:
            return True, content_id

        self.seen_hashes.add(content_id)
        return False, content_id

    def load_hash_cache(self, cache_file: Path):
        """Load SHA-256 cache from file"""
        if cache_file.exists():
            with open(cache_file, "r") as f:
                self.seen_hashes = set(json.load(f))

    def save_hash_cache(self, cache_file: Path):
        """Save SHA-256 cache to file"""
        with open(cache_file, "w") as f:
            json.dump(list(self.seen_hashes), f)


class BaliZeroScraperV2:
    """
    Unified scraper v2 with:
    - Smart extraction (multi-layer + Llama fallback)
    - Pre-scoring (filter before save)
    - Semantic deduplication (Qdrant)
    """

    def __init__(
        self,
        config_path: str = "config/unified_sources.json",
        max_age_days: int = 5,
        max_concurrent: int = 10,
        min_score: int = 40,
        use_semantic_dedup: bool = True,
    ):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.output_dir = Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Date filtering
        self.max_age_days = max_age_days

        # Minimum score threshold
        self.min_score = min_score

        # User-Agent rotation
        self.ua = UserAgent()

        # Async concurrency control
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Components (initialized lazily)
        self.extractor: Optional[SmartExtractor] = None
        self.scorer: Optional[OllamaScorer] = None
        self.deduplicator: Optional[SemanticDeduplicator] = None

        # Use semantic dedup if available
        self.use_semantic_dedup = use_semantic_dedup

        # Cache file for fallback dedup
        self.cache_file = Path("data/scraper_cache.json")

        # Stats
        self.stats = {
            "total_found": 0,
            "filtered_old": 0,
            "filtered_duplicate": 0,
            "filtered_short": 0,
            "filtered_low_score": 0,
            "saved": 0,
            "extraction_methods": {
                "css": 0,
                "trafilatura": 0,
                "newspaper": 0,
                "llama": 0,
            },
        }

        logger.info("Initialized Bali Zero Scraper v2")
        logger.info(f"Max article age: {max_age_days} days")
        logger.info(f"Min relevance score: {min_score}")
        logger.info(
            f"Semantic dedup: {'enabled' if use_semantic_dedup else 'disabled'}"
        )

    def load_config(self) -> Dict:
        """Load scraper configuration"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing scraper components...")

        # 1. Smart Extractor (with Llama fallback)
        self.extractor = SmartExtractor()
        ollama_ok = await self.extractor.check_ollama()
        if ollama_ok:
            logger.success("Smart Extractor ready (Llama fallback enabled)")
        else:
            logger.warning(
                "Smart Extractor ready (Llama fallback disabled - Ollama not running)"
            )

        # 2. Pre-Scorer (Ollama)
        self.scorer = OllamaScorer()
        scorer_ok = await self.scorer.health_check()
        if scorer_ok:
            logger.success("Pre-Scorer ready (Ollama)")
            # Warm up the model
            await self.scorer.warm_up()
        else:
            logger.warning("Pre-Scorer disabled (Ollama not running)")

        # 3. Semantic Deduplicator
        if self.use_semantic_dedup:
            self.deduplicator = SemanticDeduplicator()
            dedup_ok = await self.deduplicator.initialize()
            if not dedup_ok:
                self.deduplicator.load_hash_cache(self.cache_file)
        else:
            self.deduplicator = SemanticDeduplicator()
            self.deduplicator.load_hash_cache(self.cache_file)

        logger.info("All components initialized")

    def get_headers(self) -> Dict[str, str]:
        """Get headers with rotated User-Agent"""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        }

    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with retry"""
        async with self.semaphore:
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(
                        timeout=30.0, follow_redirects=True
                    ) as client:
                        response = await client.get(url, headers=self.get_headers())
                        response.raise_for_status()
                        return response.text
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Failed to fetch {url}: {e}")
                        return None
                    await asyncio.sleep(2**attempt)
        return None

    def _extract_links_from_index(
        self, html: str, base_url: str, selectors: List[str]
    ) -> List[Dict]:
        """Extract article links from index page"""
        soup = BeautifulSoup(html, "html.parser")
        articles = []

        for selector in selectors:
            elements = soup.select(selector)

            for elem in elements[:15]:  # Max 15 per selector
                # Find link
                link_elem = elem.find("a", href=True)
                if not link_elem:
                    continue

                link = link_elem["href"]
                if link.startswith("/"):
                    link = urljoin(base_url, link)

                # Find title
                title_elem = elem.find(["h1", "h2", "h3", "h4"]) or link_elem
                title = title_elem.get_text(strip=True)

                if len(title) < 10:
                    continue

                # Find summary (optional)
                summary_elem = elem.find(["p", "div.summary", "div.excerpt"])
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                articles.append({"title": title, "summary": summary, "url": link})

            if articles:
                break  # Found articles with this selector

        return articles

    async def scrape_source(self, source: Dict, category: str) -> List[Dict]:
        """
        Scrape a single source with:
        1. Pre-scoring (before full download)
        2. Smart extraction (multi-layer)
        3. Semantic dedup
        """
        logger.info(f"[{category}] Scraping {source['name']} (Tier {source['tier']})")

        items = []

        try:
            # Step 1: Fetch index page
            html = await self._fetch_url(source["url"])
            if not html:
                return []

            # Step 2: Extract article links from index
            # Use default generic selectors if not specified
            default_selectors = [
                "article",
                ".article",
                ".news-item",
                ".post",
                ".entry",
                "div.item",
                ".card",
                "li.result",
                ".search-result",
            ]
            selectors = source.get("selectors", default_selectors)
            articles = self._extract_links_from_index(
                html, source["url"], selectors
            )

            logger.info(f"[{source['name']}] Found {len(articles)} article links")

            for article in articles:
                self.stats["total_found"] += 1

                # Step 3: PRE-SCORE (before downloading full article)
                if self.scorer and await self.scorer.health_check():
                    score, reason = await self.scorer.score_article(
                        article["title"], article["summary"]
                    )

                    if score < self.min_score:
                        self.stats["filtered_low_score"] += 1
                        logger.debug(
                            f"Filtered (score {score}): {article['title'][:50]}..."
                        )
                        continue

                    article["relevance_score"] = score
                    article["score_reason"] = reason
                else:
                    # Default score if Ollama not available
                    article["relevance_score"] = 50
                    article["score_reason"] = "not scored"

                # Step 4: CHECK DUPLICATE (semantic or hash)
                is_dup, content_id = await self.deduplicator.is_duplicate(
                    article["title"], article.get("summary", "")
                )

                if is_dup:
                    self.stats["filtered_duplicate"] += 1
                    logger.debug(f"Duplicate: {article['title'][:50]}...")
                    continue

                # Step 5: SMART EXTRACT (full article)
                result = await self.extractor.extract(
                    url=article["url"],
                    selectors=source.get("article_selectors", []),
                    hint=f"Bali expat news about {category}",
                )

                if not result or len(result.get("content", "")) < 100:
                    self.stats["filtered_short"] += 1
                    continue

                # Track extraction method
                method = result.get("method", "unknown")
                if method in self.stats["extraction_methods"]:
                    self.stats["extraction_methods"][method] += 1

                # Step 6: Build final item
                items.append(
                    {
                        "title": result.get("title") or article["title"],
                        "content": result["content"],
                        "url": article["url"],
                        "source": source["name"],
                        "tier": source["tier"],
                        "category": category,
                        "published_at": result.get("date"),
                        "scraped_at": datetime.now().isoformat(),
                        "content_id": content_id,
                        "relevance_score": article["relevance_score"],
                        "score_reason": article["score_reason"],
                        "extraction_method": method,
                    }
                )

                self.stats["saved"] += 1
                logger.info(
                    f"✅ [{article['relevance_score']}] {article['title'][:50]}..."
                )

                # Rate limit
                await asyncio.sleep(1)

            return items

        except Exception as e:
            logger.error(f"[{category}] Error scraping {source['name']}: {e}")
            return []

    async def scrape_category(self, category_key: str, limit: int = 10) -> int:
        """Scrape all sources for a category"""

        if category_key not in self.config["categories"]:
            logger.error(f"Category '{category_key}' not found")
            return 0

        category = self.config["categories"][category_key]
        logger.info(f"📰 Scraping category: {category['name']}")

        total_items = 0

        for source in category["sources"]:
            source_items = await self.scrape_source(source, category_key)

            for item in source_items:
                await self.save_item(item, category_key)
                total_items += 1

                if total_items >= limit:
                    break

            if total_items >= limit:
                break

        logger.success(f"[{category_key}] Scraped {total_items} items")
        return total_items

    async def save_item(self, item: Dict, category: str):
        """Save scraped item to markdown file and send to backend"""

        try:
            validated = ScrapedItem(**item)
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            return

        # Create category directory
        category_dir = self.output_dir / category
        category_dir.mkdir(exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_slug = item["source"].replace(" ", "_").replace("/", "_")
        filename = f"{timestamp}_{source_slug}.md"

        filepath = category_dir / filename

        # Format as markdown with score
        content = f"""---
title: {item["title"]}
source: {item["source"]}
tier: {item["tier"]}
category: {item["category"]}
url: {item["url"]}
published_at: {item.get("published_at", "unknown")}
scraped_at: {item["scraped_at"]}
content_id: {item["content_id"]}
relevance_score: {item["relevance_score"]}
score_reason: {item["score_reason"]}
extraction_method: {item["extraction_method"]}
---

# {item["title"]}

**Source:** {item["source"]} ({item["tier"]})
**Relevance Score:** {item["relevance_score"]}/100 ({item["score_reason"]})
**Extraction:** {item["extraction_method"]}
**URL:** {item["url"]}

---

{item["content"]}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug(f"Saved: {filepath}")

        # Send to backend Intelligence Center
        await self.send_to_backend(item)

    async def send_to_backend(self, item: Dict):
        """
        Send scraped article to backend Intelligence Center.

        Articles are sent to /api/intel/scraper/submit where they are:
        1. Classified as visa or news
        2. Saved to staging folder
        3. Made available for team approval in Intelligence Center UI
        4. Voted on via Telegram
        5. Ingested to Qdrant if approved
        """
        backend_url = os.getenv(
            "BACKEND_API_URL", "https://nuzantara-rag.fly.dev"
        )
        endpoint = f"{backend_url}/api/intel/scraper/submit"

        payload = {
            "title": item["title"],
            "content": item["content"],
            "source_url": str(item["url"]),
            "source_name": item["source"],
            "category": item["category"],
            "relevance_score": item["relevance_score"],
            "published_at": item.get("published_at"),
            "extraction_method": item.get("extraction_method", "css"),
            "tier": item["tier"],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                result = response.json()

                if result.get("duplicate"):
                    logger.debug(
                        f"Backend: Article already in staging - {item['title'][:50]}"
                    )
                else:
                    logger.info(
                        f"✅ Sent to backend: {result.get('intel_type')} - {item['title'][:50]}"
                    )

        except httpx.HTTPError as e:
            logger.warning(
                f"Failed to send to backend: {e} - {item['title'][:50]}"
            )
            # Don't raise - local save is already done, backend is optional
        except Exception as e:
            logger.warning(
                f"Backend send error: {e} - {item['title'][:50]}"
            )

    async def scrape_all(self, limit: int = 10, categories: List[str] = None):
        """Scrape all categories"""

        logger.info("=" * 70)
        logger.info("🚀 BALI ZERO INTEL SCRAPER v2")
        logger.info("   Smart Extraction | Pre-Scoring | Semantic Dedup")
        logger.info("=" * 70)

        start_time = time.time()

        # Initialize components
        await self.initialize()

        # Determine categories
        if categories:
            category_keys = [k for k in categories if k in self.config["categories"]]
        else:
            category_keys = list(self.config["categories"].keys())

        logger.info(f"📋 Scraping {len(category_keys)} categories")

        results = {}
        total_scraped = 0

        for category_key in category_keys:
            count = await self.scrape_category(category_key, limit=limit)
            results[category_key] = count
            total_scraped += count

        # Save cache
        self.deduplicator.save_hash_cache(self.cache_file)

        # Summary
        duration = time.time() - start_time

        logger.info("=" * 70)
        logger.info("✅ SCRAPING COMPLETE")
        logger.info(f"📊 Total Found: {self.stats['total_found']}")
        logger.info(f"✅ Saved: {self.stats['saved']}")
        logger.info(f"❌ Filtered (low score): {self.stats['filtered_low_score']}")
        logger.info(f"❌ Filtered (duplicate): {self.stats['filtered_duplicate']}")
        logger.info(f"❌ Filtered (short): {self.stats['filtered_short']}")
        logger.info(f"🔧 Extraction methods: {self.stats['extraction_methods']}")
        logger.info(f"⏱️  Duration: {duration:.1f}s")
        logger.info("=" * 70)

        return {
            "success": True,
            "total_scraped": total_scraped,
            "duration_seconds": duration,
            "categories": results,
            "stats": self.stats,
        }


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bali Zero Intel Scraper v2")
    parser.add_argument("--categories", nargs="+", help="Specific categories")
    parser.add_argument("--limit", type=int, default=10, help="Max items per category")
    parser.add_argument("--min-score", type=int, default=40, help="Min relevance score")
    parser.add_argument(
        "--config", default="config/categories.json", help="Config path"
    )
    parser.add_argument(
        "--no-semantic", action="store_true", help="Disable semantic dedup"
    )

    args = parser.parse_args()

    scraper = BaliZeroScraperV2(
        config_path=args.config,
        min_score=args.min_score,
        use_semantic_dedup=not args.no_semantic,
    )

    results = await scraper.scrape_all(limit=args.limit, categories=args.categories)

    print(
        f"\n✅ Complete: {results['total_scraped']} items in {results['duration_seconds']:.1f}s"
    )
    print(f"📊 Stats: {results['stats']}")


if __name__ == "__main__":
    asyncio.run(main())
