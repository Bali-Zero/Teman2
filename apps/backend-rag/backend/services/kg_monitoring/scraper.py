"""
Legal Website Scraper - Phase 8

Monitors Indonesian legal websites for new regulations and updates:
- https://jdih.kemenkumham.go.id/ (Legal database)
- https://peraturan.bpk.go.id/ (Regulations)

Features:
- Async HTTP scraping with retry logic
- Content extraction with BeautifulSoup
- Rate limiting and polite crawling
- Structured document output
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Types of legal sources"""

    LEGAL_DATABASE = "legal_database"
    REGULATION_PORTAL = "regulation_portal"
    GOVERNMENT_SITE = "government_site"


@dataclass
class SourceConfig:
    """Configuration for a monitored source"""

    source_id: str
    name: str
    base_url: str
    source_type: SourceType
    search_paths: list[str] = field(default_factory=list)
    detail_path_pattern: str = ""
    selectors: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": "Mozilla/5.0 (compatible; ZantaraBot/1.0; +https://balizero.com/bot)"
        }
    )
    rate_limit_delay: float = 1.0  # seconds between requests
    timeout: int = 30
    max_retries: int = 3
    enabled: bool = True


@dataclass
class ScrapedDocument:
    """A scraped legal document"""

    document_id: str
    source_id: str
    title: str
    url: str
    content: str
    raw_html: str
    scraped_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    document_hash: str = ""  # MD5 hash of content for change detection

    def __post_init__(self):
        if not self.document_hash:
            self.document_hash = hashlib.md5(f"{self.title}:{self.content}".encode()).hexdigest()


class LegalScraper:
    """
    Scraper for Indonesian legal websites.

    Monitors:
    - JDIH Kemenkumham (legal database)
    - Peraturan BPK (regulations)
    """

    # Default source configurations
    DEFAULT_SOURCES: dict[str, SourceConfig] = {
        "jdih_kemenkumham": SourceConfig(
            source_id="jdih_kemenkumham",
            name="JDIH Kemenkumham",
            base_url="https://jdih.kemenkumham.go.id",
            source_type=SourceType.LEGAL_DATABASE,
            search_paths=["/arsip/cari", "/arsip/tipe/uu", "/arsip/tipe/perpu"],
            detail_path_pattern="/arsip/produk/",
            selectors={
                "document_list": ".arsip-list .item",
                "title": "h3 a, .title a",
                "link": "h3 a, .title a",
                "date": ".date, .meta-date",
                "content": ".content, .document-content",
                "category": ".category, .tipe",
            },
            rate_limit_delay=2.0,
        ),
        "peraturan_bpk": SourceConfig(
            source_id="peraturan_bpk",
            name="Peraturan BPK",
            base_url="https://peraturan.bpk.go.id",
            source_type=SourceType.REGULATION_PORTAL,
            search_paths=["/Home/Index", "/Home/Search"],
            detail_path_pattern="/Details/",
            selectors={
                "document_list": ".search-result-item, .regulation-item",
                "title": "h4 a, .title",
                "link": "h4 a, .title a",
                "date": ".date, .published-date",
                "content": ".document-text, .full-text",
                "category": ".category-badge, .jenis",
            },
            rate_limit_delay=1.5,
        ),
    }

    def __init__(self, custom_sources: dict[str, SourceConfig] | None = None) -> None:
        """
        Initialize the legal scraper.

        Args:
            custom_sources: Optional custom source configurations
        """
        self.sources = custom_sources or self.DEFAULT_SOURCES.copy()
        self.scrape_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "documents_found": 0,
            "last_run": None,
        }
        self._client: httpx.AsyncClient | None = None

        logger.info("✅ LegalScraper initialized")
        logger.info(f"   Sources configured: {len(self.sources)}")
        for _src_id, src in self.sources.items():
            status = "✅ enabled" if src.enabled else "❌ disabled"
            logger.info(f"   - {src.name}: {status}")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client.

        Headers and timeouts are passed per-request (in _fetch_with_retry) so that
        each SourceConfig can use its own values without leaking between sources.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("LegalScraper HTTP client closed.")

    async def scrape_source(
        self,
        source_id: str,
        max_pages: int = 5,
        per_page: int = 10,
    ) -> list[ScrapedDocument]:
        """
        Scrape documents from a specific source.

        Args:
            source_id: Source identifier
            max_pages: Maximum pages to scrape
            per_page: Documents per page

        Returns:
            List of scraped documents
        """
        source = self.sources.get(source_id)
        if not source:
            raise ValueError(f"Unknown source: {source_id}")

        if not source.enabled:
            logger.warning(f"Source {source_id} is disabled")
            return []

        logger.info(f"🔍 Scraping {source.name} (max {max_pages} pages)")

        documents = []
        client = self._get_client()
        for page in range(1, max_pages + 1):
            page_docs = await self._scrape_page(client, source, page, per_page)
            documents.extend(page_docs)

            if len(page_docs) < per_page:
                logger.info(f"   Reached end of results at page {page}")
                break

        self.scrape_stats["documents_found"] += len(documents)
        self.scrape_stats["last_run"] = datetime.now().isoformat()

        logger.info(f"✅ Scraped {len(documents)} documents from {source.name}")
        return documents

    async def _scrape_page(
        self,
        client: httpx.AsyncClient,
        source: SourceConfig,
        page: int,
        per_page: int,
    ) -> list[ScrapedDocument]:
        """Scrape a single page from the source"""
        documents = []

        for search_path in source.search_paths:
            try:
                url = self._build_search_url(source, search_path, page, per_page)
                logger.debug(f"   Fetching: {url}")

                response = await self._fetch_with_retry(client, url, source)
                if not response:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select(source.selectors.get("document_list", ".item"))

                for item in items:
                    try:
                        doc = self._parse_document_item(item, source)
                        if doc:
                            documents.append(doc)
                    except Exception as e:
                        logger.warning(f"   Failed to parse item: {e}")

            except Exception as e:
                logger.error(f"   Error scraping {search_path}: {e}")

        return documents

    def _build_search_url(
        self,
        source: SourceConfig,
        search_path: str,
        page: int,
        per_page: int,
    ) -> str:
        """Build search URL with pagination"""
        base = urljoin(source.base_url, search_path)

        # Add query parameters based on source
        if source.source_id == "jdih_kemenkumham":
            return f"{base}?page={page}&per_page={per_page}"
        elif source.source_id == "peraturan_bpk":
            return f"{base}?page={page}&size={per_page}"

        return f"{base}?page={page}"

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        source: SourceConfig,
    ) -> httpx.Response | None:
        """Fetch URL with retry logic"""
        import asyncio

        for attempt in range(source.max_retries):
            try:
                self.scrape_stats["total_requests"] += 1
                response = await client.get(
                    url,
                    headers=source.headers,
                    timeout=source.timeout,
                )
                response.raise_for_status()
                self.scrape_stats["successful_requests"] += 1

                # Rate limiting
                await asyncio.sleep(source.rate_limit_delay)
                return response

            except httpx.HTTPStatusError as e:
                self.scrape_stats["failed_requests"] += 1
                logger.warning(f"   HTTP {e.response.status_code} for {url}")
                if e.response.status_code == 429:  # Rate limited
                    wait_time = (attempt + 1) * 5
                    logger.info(f"   Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif attempt < source.max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

            except Exception as e:
                self.scrape_stats["failed_requests"] += 1
                logger.warning(f"   Request error: {e}")
                if attempt < source.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error(f"   Failed to fetch {url} after {source.max_retries} attempts")
        return None

    def _parse_document_item(
        self,
        item: BeautifulSoup,
        source: SourceConfig,
    ) -> ScrapedDocument | None:
        """Parse a document item from HTML"""
        selectors = source.selectors

        # Extract title
        title_elem = item.select_one(selectors.get("title", "h3 a"))
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title:
            return None

        # Extract URL
        link_elem = item.select_one(selectors.get("link", "a"))
        href = link_elem.get("href", "") if link_elem else ""
        full_url = urljoin(source.base_url, href)

        # Extract metadata
        date_elem = item.select_one(selectors.get("date", ".date"))
        date_text = date_elem.get_text(strip=True) if date_elem else ""

        category_elem = item.select_one(selectors.get("category", ".category"))
        category = category_elem.get_text(strip=True) if category_elem else ""

        # Generate document ID from URL or title
        doc_id = self._generate_document_id(full_url or title)

        # Get content (from item or placeholder for detail fetch)
        content_elem = item.select_one(selectors.get("content", ".content"))
        content = content_elem.get_text(strip=True) if content_elem else title

        return ScrapedDocument(
            document_id=doc_id,
            source_id=source.source_id,
            title=title,
            url=full_url,
            content=content,
            raw_html=str(item),
            scraped_at=datetime.now(),
            metadata={
                "date_text": date_text,
                "category": category,
                "page_url": full_url,
            },
        )

    async def fetch_document_detail(
        self,
        document: ScrapedDocument,
    ) -> ScrapedDocument:
        """
        Fetch full document content from detail page.

        Args:
            document: Document with URL to fetch

        Returns:
            Document with full content
        """
        source = self.sources.get(document.source_id)
        if not source or not document.url:
            return document

        logger.debug(f"   Fetching detail: {document.url}")

        client = self._get_client()
        response = await self._fetch_with_retry(client, document.url, source)
        if not response:
            return document

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract full content
        content_selectors = [
            source.selectors.get("content"),
            ".document-content",
            ".full-text",
            "article",
            ".content",
            "#content",
        ]

        for selector in content_selectors:
            if selector:
                elem = soup.select_one(selector)
                if elem:
                    document.content = elem.get_text(separator="\n", strip=True)
                    document.raw_html = str(elem)
                    # Update hash with new content
                    document.document_hash = hashlib.md5(
                        f"{document.title}:{document.content}".encode()
                    ).hexdigest()
                    break

        return document

    def _generate_document_id(self, identifier: str) -> str:
        """Generate unique document ID"""
        return hashlib.md5(identifier.encode()).hexdigest()[:16]

    async def scrape_all_sources(
        self,
        max_pages: int = 5,
        per_page: int = 10,
    ) -> dict[str, list[ScrapedDocument]]:
        """
        Scrape all enabled sources.

        Args:
            max_pages: Maximum pages per source
            per_page: Documents per page

        Returns:
            Dict mapping source_id to list of documents
        """
        results = {}

        for source_id, source in self.sources.items():
            if not source.enabled:
                continue

            try:
                documents = await self.scrape_source(source_id, max_pages, per_page)
                results[source_id] = documents
            except Exception as e:
                logger.error(f"Failed to scrape {source_id}: {e}")
                results[source_id] = []

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get scraper statistics"""
        total = self.scrape_stats["total_requests"]
        success = self.scrape_stats["successful_requests"]
        success_rate = (success / total * 100) if total > 0 else 0

        return {
            **self.scrape_stats,
            "success_rate": f"{success_rate:.1f}%",
            "sources_configured": len(self.sources),
            "sources_enabled": sum(1 for s in self.sources.values() if s.enabled),
        }

    def add_source(self, source: SourceConfig) -> None:
        """Add a new source configuration"""
        self.sources[source.source_id] = source
        logger.info(f"➕ Added source: {source.name}")

    def disable_source(self, source_id: str) -> None:
        """Disable a source"""
        if source_id in self.sources:
            self.sources[source_id].enabled = False
            logger.info(f"⛔ Disabled source: {source_id}")

    def enable_source(self, source_id: str) -> None:
        """Enable a source"""
        if source_id in self.sources:
            self.sources[source_id].enabled = True
            logger.info(f"✅ Enabled source: {source_id}")
