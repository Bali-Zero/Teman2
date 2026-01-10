"""
Scraper Data Normalization Service
Normalizes data from various scrapers with structured logging and metrics
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.metrics import metrics_collector

from .ingestion_logger import IngestionStage, ingestion_logger

logger = logging.getLogger(__name__)


@dataclass
class NormalizationConfig:
    """Configuration for data normalization"""

    enable_content_cleaning: bool = True
    enable_duplicate_detection: bool = True
    min_content_length: int = 50
    max_content_length: int = 1000000  # 1MB
    required_fields: list[str] | None = None

    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = ["title", "content"]


class ScraperDataNormalizer:
    """
    Normalizes scraper data from various sources with comprehensive logging and metrics.

    Features:
    - Content cleaning and standardization
    - Duplicate detection
    - Quality scoring
    - Structured logging
    - Metrics tracking
    """

    def __init__(self, config: NormalizationConfig | None = None):
        """
        Initialize the scraper data normalizer.

        Args:
            config: Normalization configuration
        """
        self.config = config or NormalizationConfig()
        self.processed_items: list[dict[str, Any]] = []
        self.duplicates_detected: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

        logger.info("ScraperDataNormalizer initialized")

    async def normalize_news_article(
        self,
        raw_data: dict[str, Any],
        source: str = "scraper",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Normalize news article data from scraper.

        Args:
            raw_data: Raw scraper data
            source: Source identifier
            trace_id: Trace ID for correlation

        Returns:
            Normalized article data
        """
        start_time = time.time()
        document_id = None

        try:
            # Generate document ID
            content_hash = self._generate_content_hash(raw_data.get("content", ""))
            document_id = f"news_{int(start_time)}_{content_hash[:8]}"

            # Start structured logging
            document_id = ingestion_logger.start_ingestion(
                file_path=raw_data.get("url", "scraper_data"),
                document_id=document_id,
                source=source,
                trace_id=trace_id,
            )

            # Validate required fields
            self._validate_required_fields(raw_data, ["title", "content"])

            # Normalize data
            normalized = await self._normalize_article_data(raw_data, document_id)

            # Record metrics
            duration = time.time() - start_time
            metrics_collector.record_scraper_data_normalized(
                scraper_type="news",
                source=raw_data.get("source", "unknown"),
                status="success",
                duration_seconds=duration,
            )

            # Log completion
            ingestion_logger.scraper_data_normalized(
                document_id=document_id,
                source_url=raw_data.get("url", ""),
                normalized_fields=normalized,
                duration_ms=duration * 1000,
                trace_id=trace_id,
            )

            self.processed_items.append(normalized)
            return normalized

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            # Record error metrics
            metrics_collector.record_scraper_normalization_error(
                scraper_type="news", error_type=error_type
            )

            # Log error
            ingestion_logger.ingestion_failed(
                document_id=document_id or f"news_failed_{int(start_time)}",
                file_path=raw_data.get("url", "scraper_data"),
                error=e,
                stage=IngestionStage.CLEANING,
                duration_ms=duration * 1000,
                source=source,
                trace_id=trace_id,
            )

            self.errors.append({"data": raw_data, "error": str(e)})
            raise

    async def normalize_visa_information(
        self,
        raw_data: dict[str, Any],
        source: str = "scraper",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Normalize visa information data from scraper.

        Args:
            raw_data: Raw scraper data
            source: Source identifier
            trace_id: Trace ID for correlation

        Returns:
            Normalized visa data
        """
        start_time = time.time()
        document_id = None

        try:
            # Generate document ID
            content_hash = self._generate_content_hash(str(raw_data))
            document_id = f"visa_{int(start_time)}_{content_hash[:8]}"

            # Start structured logging
            document_id = ingestion_logger.start_ingestion(
                file_path=raw_data.get("source_url", "scraper_data"),
                document_id=document_id,
                source=source,
                trace_id=trace_id,
            )

            # Validate required fields
            self._validate_required_fields(raw_data, ["visa_type"])

            # Normalize data
            normalized = await self._normalize_visa_data(raw_data, document_id)

            # Record metrics
            duration = time.time() - start_time
            metrics_collector.record_scraper_data_normalized(
                scraper_type="visa",
                source=raw_data.get("source", "unknown"),
                status="success",
                duration_seconds=duration,
            )

            # Log completion
            ingestion_logger.scraper_data_normalized(
                document_id=document_id,
                source_url=raw_data.get("source_url", ""),
                normalized_fields=normalized,
                duration_ms=duration * 1000,
                trace_id=trace_id,
            )

            self.processed_items.append(normalized)
            return normalized

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            # Record error metrics
            metrics_collector.record_scraper_normalization_error(
                scraper_type="visa", error_type=error_type
            )

            # Log error
            ingestion_logger.ingestion_failed(
                document_id=document_id or f"visa_failed_{int(start_time)}",
                file_path=raw_data.get("source_url", "scraper_data"),
                error=e,
                stage=IngestionStage.CLEANING,
                duration_ms=duration * 1000,
                source=source,
                trace_id=trace_id,
            )

            self.errors.append({"data": raw_data, "error": str(e)})
            raise

    def detect_duplicates(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect duplicate items based on content similarity.

        Args:
            items: List of normalized items

        Returns:
            List of duplicate items
        """
        if not self.config.enable_duplicate_detection:
            return []

        duplicates = []
        seen_hashes = set()
        seen_urls = set()

        for item in items:
            # Check content hash
            content_hash = item.get("content_hash", "")
            url = item.get("url", "")

            is_duplicate = False

            if content_hash and content_hash in seen_hashes or url and url in seen_urls:
                is_duplicate = True

            if is_duplicate:
                duplicates.append(item)
                self.duplicates_detected.append(item)
            else:
                if content_hash:
                    seen_hashes.add(content_hash)
                if url:
                    seen_urls.add(url)
        logger.info(f"Detected {len(duplicates)} duplicates out of {len(items)} items")
        return duplicates

    async def _normalize_article_data(
        self, raw_data: dict[str, Any], document_id: str
    ) -> dict[str, Any]:
        """Normalize article data"""

        # Clean and validate content
        title = self._clean_text(raw_data.get("title", ""))
        content = self._clean_text(raw_data.get("content", ""))

        if len(content) < self.config.min_content_length:
            raise ValueError(f"Content too short: {len(content)} characters")

        if len(content) > self.config.max_content_length:
            logger.warning(f"Content very long: {len(content)} characters, truncating")
            content = content[: self.config.max_content_length]

        # Normalize dates
        published_date = self._normalize_date(raw_data.get("published_date"))
        scraped_at = self._normalize_date(raw_data.get("scraped_at"))

        # Normalize tags
        tags = self._normalize_tags(raw_data.get("tags", []))

        # Calculate quality score
        quality_score = self._calculate_quality_score(raw_data)

        # Generate content hash for duplicate detection
        content_hash = self._generate_content_hash(title + content)

        normalized = {
            "id": document_id,
            "title": title,
            "content": content,
            "summary": self._clean_text(raw_data.get("summary", "")),
            "url": self._normalize_url(raw_data.get("url", "")),
            "source": str(raw_data.get("source", "Unknown")).strip(),
            "author": self._clean_text(raw_data.get("author", "")),
            "published_date": published_date,
            "scraped_at": scraped_at,
            "tags": tags,
            "category": raw_data.get("category", "general"),
            "language": raw_data.get("language", "en"),
            "word_count": len(content.split()),
            "character_count": len(content),
            "quality_score": quality_score,
            "content_hash": content_hash,
            "data_type": "news_article",
            "normalized_at": datetime.now().isoformat(),
            "scraper_id": raw_data.get("scraper_id", ""),
            "confidence_score": raw_data.get("confidence_score", 0.0),
        }

        return normalized

    async def _normalize_visa_data(
        self, raw_data: dict[str, Any], document_id: str
    ) -> dict[str, Any]:
        """Normalize visa data"""

        # Clean basic fields
        visa_type = self._clean_text(raw_data.get("visa_type", ""))
        description = self._clean_text(raw_data.get("description", ""))

        if not visa_type:
            raise ValueError("Visa type is required")

        # Normalize requirements
        requirements = self._normalize_requirements(raw_data.get("requirements", []))

        # Normalize fees
        fees = self._normalize_fees(raw_data.get("fees", ""))

        # Normalize processing time
        processing_time = self._normalize_processing_time(raw_data.get("processing_time", ""))

        # Normalize dates
        last_updated = self._normalize_date(raw_data.get("last_updated"))
        scraped_at = self._normalize_date(raw_data.get("scraped_at"))

        # Generate content hash
        content_hash = self._generate_content_hash(visa_type + description + str(requirements))

        normalized = {
            "id": document_id,
            "visa_type": visa_type,
            "description": description,
            "requirements": requirements,
            "processing_time": processing_time,
            "fees": fees,
            "validity": self._clean_text(raw_data.get("validity", "")),
            "extensions": self._clean_text(raw_data.get("extensions", "")),
            "source_url": self._normalize_url(raw_data.get("source_url", "")),
            "country": raw_data.get("country", "Indonesia"),
            "last_updated": last_updated,
            "scraped_at": scraped_at,
            "content_hash": content_hash,
            "data_type": "visa_info",
            "normalized_at": datetime.now().isoformat(),
            "scraper_type": raw_data.get("scraper_type", "unknown"),
            "data_quality": raw_data.get("data_quality", "unknown"),
        }

        return normalized

    def _validate_required_fields(self, data: dict[str, Any], required_fields: list[str]):
        """Validate that required fields are present and not empty"""
        missing_fields = []

        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    def _clean_text(self, text: str) -> str:
        """Clean text content"""
        if not text:
            return ""

        if not isinstance(text, str):
            text = str(text)

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove HTML tags (basic)
        text = re.sub(r"<[^>]+>", "", text)

        # Remove excessive special characters but keep basic punctuation
        text = re.sub(r"[^\w\s.,!?;:\-'\n]", " ", text)

        # Clean up multiple spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to ISO format"""
        if not date_str:
            return datetime.utcnow().isoformat()

        try:
            # Try parsing ISO format first
            if "T" in date_str:
                return date_str

            # Try other common formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.isoformat()
                except ValueError:
                    continue

            # If all fails, return current time
            return datetime.now().isoformat()

        except Exception:
            return datetime.now().isoformat()

    def _normalize_tags(self, tags) -> list[str]:
        """Normalize tags to consistent format"""
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",")]
        elif not isinstance(tags, list):
            tags = []

        # Clean and standardize tags
        normalized_tags = []
        for tag in tags:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower().replace(" ", "_").replace("-", "_")
                if clean_tag and len(clean_tag) > 1:
                    normalized_tags.append(clean_tag)

        return list(set(normalized_tags))  # Remove duplicates

    def _normalize_url(self, url: str) -> str:
        """Normalize URL format"""
        if not url or not isinstance(url, str):
            return ""

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _normalize_requirements(self, requirements) -> list[str]:
        """Normalize visa requirements"""
        if not isinstance(requirements, list):
            return []

        normalized = []
        for req in requirements:
            if isinstance(req, str):
                clean_req = self._clean_text(req)
                if clean_req:
                    normalized.append(clean_req)

        return normalized

    def _normalize_fees(self, fees: str) -> dict[str, Any]:
        """Normalize fee information"""
        if not fees:
            return {"amount": 0, "currency": "USD", "text": ""}

        # Extract currency and amount
        currency_match = re.search(r"(USD|IDR|EUR|GBP)", fees.upper())
        currency = currency_match.group(1) if currency_match else "USD"

        amount_match = re.search(r"(\d+(?:,\d+)*)", fees.replace(",", ""))
        amount = int(amount_match.group(1)) if amount_match else 0

        return {"amount": amount, "currency": currency, "text": fees.strip()}

    def _normalize_processing_time(self, time_str: str) -> dict[str, Any]:
        """Normalize processing time information"""
        if not time_str:
            return {"days_min": 0, "days_max": 0, "text": ""}

        # Extract day ranges
        day_matches = re.findall(r"(\d+)", time_str)

        if len(day_matches) >= 2:
            days_min = int(day_matches[0])
            days_max = int(day_matches[1])
        elif len(day_matches) == 1:
            days_min = days_max = int(day_matches[0])
        else:
            days_min = days_max = 0

        return {"days_min": days_min, "days_max": days_max, "text": time_str.strip()}

    def _calculate_quality_score(self, data: dict[str, Any]) -> float:
        """Calculate data quality score"""
        score = 0.0

        # Content length
        content = data.get("content", "")
        if len(content) > 500:
            score += 0.3
        elif len(content) > 100:
            score += 0.2

        # Has title
        if data.get("title"):
            score += 0.2

        # Has author
        if data.get("author"):
            score += 0.1

        # Has valid date
        if data.get("published_date"):
            score += 0.1

        # Has tags
        if data.get("tags"):
            score += 0.1

        # Has source
        if data.get("source"):
            score += 0.1

        # Confidence score from scraper
        confidence = data.get("confidence_score", 0)
        score += confidence * 0.1

        return min(score, 1.0)

    def _generate_content_hash(self, content: str) -> str:
        """Generate content hash for duplicate detection"""
        if not content:
            return ""

        # Normalize content for hashing
        normalized = content.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)  # Normalize whitespace

        return hashlib.md5(normalized.encode()).hexdigest()

    def get_statistics(self) -> dict[str, Any]:
        """Get processing statistics"""
        return {
            "total_processed": len(self.processed_items),
            "duplicates_detected": len(self.duplicates_detected),
            "errors": len(self.errors),
            "success_rate": (
                len(self.processed_items) / max(1, len(self.processed_items) + len(self.errors))
            )
            * 100,
            "data_types": list(
                set(item.get("data_type", "unknown") for item in self.processed_items)
            ),
            "average_quality_score": sum(
                item.get("quality_score", 0) for item in self.processed_items
            )
            / max(1, len(self.processed_items)),
        }


# Global normalizer instance
scraper_normalizer = ScraperDataNormalizer()
