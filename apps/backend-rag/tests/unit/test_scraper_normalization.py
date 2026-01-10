"""
Comprehensive Tests for Scraper Data Normalization
Tests data normalization from various scraper sources with error handling
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Mock scraper data structures
class MockScraperData:
    """Mock scraper data structure for testing"""

    @staticmethod
    def raw_news_article():
        """Raw news article from scraper"""
        return {
            "title": "Breaking: New Visa Policy Announced",
            "content": "The government announced new visa policies today affecting tourists...",
            "url": "https://example.com/news/visa-policy",
            "published_date": "2024-01-15T10:30:00Z",
            "source": "News Portal",
            "author": "John Doe",
            "tags": ["visa", "policy", "tourism"],
            "category": "immigration",
            "language": "en",
            "word_count": 456,
            "summary": "Government announces new visa policy changes",
            "raw_html": "<html>...</html>",
            "images": ["https://example.com/image1.jpg"],
            "links": ["https://example.com/related"],
            "scraped_at": "2024-01-15T11:00:00Z",
            "scraper_id": "news_scraper_v1",
            "confidence_score": 0.85,
        }

    @staticmethod
    def raw_visa_info():
        """Raw visa information from scraper"""
        return {
            "visa_type": "Tourist Visa",
            "description": "For tourism purposes only",
            "requirements": ["Valid passport", "Proof of funds", "Return ticket"],
            "processing_time": "5-7 business days",
            "fees": "USD 50",
            "validity": "30 days",
            "extensions": "Can be extended once",
            "source_url": "https://immigration.gov.id/tourist-visa",
            "country": "Indonesia",
            "last_updated": "2024-01-10T00:00:00Z",
            "scraped_at": "2024-01-15T12:00:00Z",
            "scraper_type": "government_site",
            "data_quality": "high",
        }

    @staticmethod
    def malformed_data():
        """Malformed scraper data"""
        return {
            "title": None,
            "content": "",
            "url": "invalid-url",
            "published_date": "not-a-date",
            "source": 123,  # Wrong type
            "tags": "not-a-list",
            "scraped_at": "future-date",
        }

    @staticmethod
    def duplicate_data():
        """Duplicate data for deduplication testing"""
        return {
            "title": "Same Title",
            "content": "Same content that should be detected as duplicate",
            "url": "https://example.com/duplicate",
            "hash": "abc123",
            "fingerprint": "unique_fingerprint_123",
        }


class ScraperDataNormalizer:
    """Mock scraper data normalizer for testing"""

    def __init__(self):
        self.processed_items = []
        self.duplicates_detected = []
        self.errors = []

    def normalize_news_article(self, raw_data: dict) -> dict:
        """Normalize news article data"""
        try:
            # Validate required fields
            if not raw_data.get("title") or not raw_data.get("content"):
                raise ValueError("Missing required fields: title or content")

            # Normalize dates
            published_date = self._normalize_date(raw_data.get("published_date"))
            scraped_at = self._normalize_date(raw_data.get("scraped_at"))

            # Clean content
            cleaned_content = self._clean_text(raw_data.get("content", ""))

            # Normalize tags
            tags = self._normalize_tags(raw_data.get("tags", []))

            # Calculate quality score
            quality_score = self._calculate_quality_score(raw_data)

            normalized = {
                "id": f"news_{int(time.time())}_{hash(raw_data['url']) % 10000}",
                "title": raw_data["title"].strip(),
                "content": cleaned_content,
                "summary": raw_data.get("summary", ""),
                "url": self._normalize_url(raw_data["url"]),
                "source": str(raw_data.get("source", "Unknown")).strip(),
                "author": raw_data.get("author", ""),
                "published_date": published_date,
                "scraped_at": scraped_at,
                "tags": tags,
                "category": raw_data.get("category", "general"),
                "language": raw_data.get("language", "en"),
                "word_count": len(cleaned_content.split()),
                "quality_score": quality_score,
                "data_type": "news_article",
                "normalized_at": datetime.utcnow().isoformat(),
                "raw_data_hash": hash(str(raw_data)),
            }

            self.processed_items.append(normalized)
            return normalized

        except Exception as e:
            self.errors.append({"data": raw_data, "error": str(e)})
            raise

    def normalize_visa_info(self, raw_data: dict) -> dict:
        """Normalize visa information data"""
        try:
            # Validate required fields
            if not raw_data.get("visa_type"):
                raise ValueError("Missing required field: visa_type")

            # Normalize requirements
            requirements = self._normalize_requirements(raw_data.get("requirements", []))

            # Normalize fees
            fees = self._normalize_fees(raw_data.get("fees", ""))

            # Normalize processing time
            processing_time = self._normalize_processing_time(raw_data.get("processing_time", ""))

            normalized = {
                "id": f"visa_{int(time.time())}_{hash(raw_data.get('source_url', '')) % 10000}",
                "visa_type": raw_data["visa_type"].strip(),
                "description": raw_data.get("description", "").strip(),
                "requirements": requirements,
                "processing_time": processing_time,
                "fees": fees,
                "validity": raw_data.get("validity", ""),
                "extensions": raw_data.get("extensions", ""),
                "source_url": self._normalize_url(raw_data.get("source_url", "")),
                "country": raw_data.get("country", "Indonesia"),
                "last_updated": self._normalize_date(raw_data.get("last_updated")),
                "scraped_at": self._normalize_date(raw_data.get("scraped_at")),
                "data_type": "visa_info",
                "normalized_at": datetime.utcnow().isoformat(),
                "data_quality": raw_data.get("data_quality", "unknown"),
            }

            self.processed_items.append(normalized)
            return normalized

        except Exception as e:
            self.errors.append({"data": raw_data, "error": str(e)})
            raise

    def detect_duplicates(self, items: list) -> list:
        """Detect duplicate items based on content similarity"""
        duplicates = []
        seen_hashes = set()

        for item in items:
            content_hash = hash(item.get("content", "") + item.get("title", ""))

            if content_hash in seen_hashes:
                duplicates.append(item)
                self.duplicates_detected.append(item)
            else:
                seen_hashes.add(content_hash)

        return duplicates

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
            return datetime.utcnow().isoformat()

        except Exception:
            return datetime.utcnow().isoformat()

    def _clean_text(self, text: str) -> str:
        """Clean text content"""
        if not text:
            return ""

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove HTML tags (basic)
        import re

        text = re.sub(r"<[^>]+>", "", text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r"[^\w\s.,!?;:\-']", " ", text)

        return text.strip()

    def _normalize_tags(self, tags) -> list:
        """Normalize tags to consistent format"""
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",")]
        elif not isinstance(tags, list):
            tags = []

        # Clean and standardize tags
        normalized_tags = []
        for tag in tags:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower().replace(" ", "_")
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

    def _calculate_quality_score(self, data: dict) -> float:
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

    def _normalize_requirements(self, requirements) -> list:
        """Normalize visa requirements"""
        if not isinstance(requirements, list):
            return []

        normalized = []
        for req in requirements:
            if isinstance(req, str):
                clean_req = req.strip().capitalize()
                if clean_req:
                    normalized.append(clean_req)

        return normalized

    def _normalize_fees(self, fees: str) -> dict:
        """Normalize fee information"""
        if not fees:
            return {"amount": 0, "currency": "USD", "text": ""}

        # Extract currency and amount
        import re

        currency_match = re.search(r"(USD|IDR|EUR|GBP)", fees.upper())
        currency = currency_match.group(1) if currency_match else "USD"

        amount_match = re.search(r"(\d+)", fees)
        amount = int(amount_match.group(1)) if amount_match else 0

        return {"amount": amount, "currency": currency, "text": fees.strip()}

    def _normalize_processing_time(self, time_str: str) -> dict:
        """Normalize processing time information"""
        if not time_str:
            return {"days_min": 0, "days_max": 0, "text": ""}

        # Extract day ranges
        import re

        day_matches = re.findall(r"(\d+)", time_str)

        if len(day_matches) >= 2:
            days_min = int(day_matches[0])
            days_max = int(day_matches[1])
        elif len(day_matches) == 1:
            days_min = days_max = int(day_matches[0])
        else:
            days_min = days_max = 0

        return {"days_min": days_min, "days_max": days_max, "text": time_str.strip()}


class TestScraperDataNormalization:
    """Test scraper data normalization functionality"""

    def test_normalize_news_article_success(self):
        """Test successful news article normalization"""
        normalizer = ScraperDataNormalizer()
        raw_data = MockScraperData.raw_news_article()

        result = normalizer.normalize_news_article(raw_data)

        # Verify basic structure
        assert "id" in result
        assert result["data_type"] == "news_article"
        assert result["title"] == "Breaking: New Visa Policy Announced"
        assert len(result["content"]) > 0
        assert result["url"].startswith("https://")
        assert result["quality_score"] > 0

        # Verify normalized fields
        assert isinstance(result["tags"], list)
        assert all(isinstance(tag, str) for tag in result["tags"])
        assert result["word_count"] > 0
        assert "normalized_at" in result

        # Verify it was tracked
        assert len(normalizer.processed_items) == 1
        assert normalizer.processed_items[0] == result

    def test_normalize_visa_info_success(self):
        """Test successful visa information normalization"""
        normalizer = ScraperDataNormalizer()
        raw_data = MockScraperData.raw_visa_info()

        result = normalizer.normalize_visa_info(raw_data)

        # Verify basic structure
        assert "id" in result
        assert result["data_type"] == "visa_info"
        assert result["visa_type"] == "Tourist Visa"
        assert result["country"] == "Indonesia"

        # Verify normalized requirements
        assert isinstance(result["requirements"], list)
        assert all(isinstance(req, str) for req in result["requirements"])

        # Verify normalized fees
        assert "fees" in result
        assert result["fees"]["currency"] == "USD"
        assert result["fees"]["amount"] == 50

        # Verify normalized processing time
        assert "processing_time" in result
        assert result["processing_time"]["days_min"] == 5
        assert result["processing_time"]["days_max"] == 7

        # Verify it was tracked
        assert len(normalizer.processed_items) == 1

    def test_normalize_malformed_data(self):
        """Test handling of malformed data"""
        normalizer = ScraperDataNormalizer()
        malformed_data = MockScraperData.malformed_data()

        with pytest.raises(ValueError, match="Missing required fields"):
            normalizer.normalize_news_article(malformed_data)

        # Verify error was tracked
        assert len(normalizer.errors) == 1
        assert "Missing required fields" in normalizer.errors[0]["error"]

    def test_detect_duplicates(self):
        """Test duplicate detection"""
        normalizer = ScraperDataNormalizer()

        # Create similar items
        item1 = {"title": "Same Title", "content": "Same content", "url": "https://example.com/1"}
        item2 = {"title": "Same Title", "content": "Same content", "url": "https://example.com/2"}
        item3 = {
            "title": "Different Title",
            "content": "Different content",
            "url": "https://example.com/3",
        }

        items = [item1, item2, item3]
        duplicates = normalizer.detect_duplicates(items)

        # Should detect one duplicate
        assert len(duplicates) == 1
        assert duplicates[0]["url"] == "https://example.com/2"
        assert len(normalizer.duplicates_detected) == 1

    def test_normalize_text_cleaning(self):
        """Test text cleaning functionality"""
        normalizer = ScraperDataNormalizer()

        dirty_text = "  <p>This is   dirty text with   <b>HTML</b> tags!</p>  "
        clean_text = normalizer._clean_text(dirty_text)

        # Should remove HTML and extra whitespace
        assert "<p>" not in clean_text
        assert "<b>" not in clean_text
        assert "This is dirty text with HTML tags!" == clean_text

    def test_normalize_tags(self):
        """Test tag normalization"""
        normalizer = ScraperDataNormalizer()

        # Test string input
        tags_string = "visa, policy, tourism, immigration"
        result = normalizer._normalize_tags(tags_string)
        assert isinstance(result, list)
        assert "visa" in result
        assert "policy" in result

        # Test list input
        tags_list = ["Visa", "Policy", "  Tourism  ", ""]
        result = normalizer._normalize_tags(tags_list)
        assert isinstance(result, list)
        assert "visa" in result
        assert "policy" in result
        assert "tourism" in result
        assert "" not in result

        # Test invalid input
        result = normalizer._normalize_tags("not_a_list")
        assert isinstance(result, list)

    def test_normalize_url(self):
        """Test URL normalization"""
        normalizer = ScraperDataNormalizer()

        # Test with https
        result = normalizer._normalize_url("https://example.com")
        assert result == "https://example.com"

        # Test without protocol
        result = normalizer._normalize_url("example.com")
        assert result == "https://example.com"

        # Test invalid input
        result = normalizer._normalize_url("")
        assert result == ""
        result = normalizer._normalize_url(None)
        assert result == ""

    def test_calculate_quality_score(self):
        """Test quality score calculation"""
        normalizer = ScraperDataNormalizer()

        # High quality data
        high_quality = {
            "content": "This is a long article with substantial content. " * 20,
            "title": "Proper Title",
            "author": "John Doe",
            "published_date": "2024-01-15",
            "tags": ["tag1", "tag2"],
            "source": "News Source",
            "confidence_score": 0.9,
        }
        score = normalizer._calculate_quality_score(high_quality)
        assert score > 0.8

        # Low quality data
        low_quality = {
            "content": "Short",
            "title": "",
            "author": "",
            "published_date": "",
            "tags": [],
            "source": "",
            "confidence_score": 0.1,
        }
        score = normalizer._calculate_quality_score(low_quality)
        assert score < 0.5

    def test_normalize_fees(self):
        """Test fee normalization"""
        normalizer = ScraperDataNormalizer()

        result = normalizer._normalize_fees("USD 50")
        assert result["amount"] == 50
        assert result["currency"] == "USD"
        assert result["text"] == "USD 50"

        result = normalizer._normalize_fees("IDR 750000")
        assert result["amount"] == 750000
        assert result["currency"] == "IDR"

        result = normalizer._normalize_fees("")
        assert result["amount"] == 0
        assert result["currency"] == "USD"

    def test_normalize_processing_time(self):
        """Test processing time normalization"""
        normalizer = ScraperDataNormalizer()

        result = normalizer._normalize_processing_time("5-7 business days")
        assert result["days_min"] == 5
        assert result["days_max"] == 7

        result = normalizer._normalize_processing_time("10 days")
        assert result["days_min"] == 10
        assert result["days_max"] == 10

        result = normalizer._normalize_processing_time("")
        assert result["days_min"] == 0
        assert result["days_max"] == 0


class TestNormalizationPerformance:
    """Test performance of normalization operations"""

    def test_batch_normalization_performance(self):
        """Test performance of batch normalization"""
        normalizer = ScraperDataNormalizer()

        # Create test data
        articles = [MockScraperData.raw_news_article() for _ in range(100)]

        start_time = time.time()

        for article in articles:
            # Vary the data slightly
            article["title"] = f"Article {len(normalizer.processed_items)}"
            normalizer.normalize_news_article(article)

        duration = time.time() - start_time

        # Should process 100 items quickly
        assert len(normalizer.processed_items) == 100
        assert duration < 5.0  # Should be under 5 seconds
        assert len(normalizer.errors) == 0

    def test_duplicate_detection_performance(self):
        """Test performance of duplicate detection"""
        normalizer = ScraperDataNormalizer()

        # Create items with some duplicates
        items = []
        for i in range(1000):
            if i % 10 == 0:  # Every 10th item is a duplicate
                items.append(
                    {
                        "title": "Duplicate Title",
                        "content": "Duplicate content",
                        "url": f"https://example.com/duplicate_{i // 10}",
                    }
                )
            else:
                items.append(
                    {
                        "title": f"Unique Title {i}",
                        "content": f"Unique content {i}",
                        "url": f"https://example.com/unique_{i}",
                    }
                )

        start_time = time.time()
        duplicates = normalizer.detect_duplicates(items)
        duration = time.time() - start_time

        # Should detect 100 duplicates quickly
        assert len(duplicates) == 100
        assert duration < 1.0  # Should be very fast


class TestIntegrationScenarios:
    """Integration tests for realistic normalization scenarios"""

    def test_end_to_end_news_processing(self):
        """Test complete news processing pipeline"""
        normalizer = ScraperDataNormalizer()

        # Simulate raw data from different scrapers
        raw_articles = [
            MockScraperData.raw_news_article(),
            MockScraperData.malformed_data(),
            MockScraperData.raw_news_article(),  # Duplicate
        ]

        # Vary the slightly duplicate
        raw_articles[2]["url"] = "https://different-url.com/same-news"

        processed = []
        errors = []

        for article in raw_articles:
            try:
                normalized = normalizer.normalize_news_article(article)
                processed.append(normalized)
            except Exception as e:
                errors.append({"article": article, "error": str(e)})

        # Detect duplicates
        duplicates = normalizer.detect_duplicates(processed)

        # Verify results
        assert len(processed) == 2  # One failed, two succeeded
        assert len(errors) == 1  # One malformed
        assert len(duplicates) == 1  # One duplicate detected

        # Verify processed items have required structure
        for item in processed:
            assert "id" in item
            assert "data_type" in item
            assert "quality_score" in item
            assert item["quality_score"] > 0

    def test_mixed_data_type_processing(self):
        """Test processing mixed data types (news + visa info)"""
        normalizer = ScraperDataNormalizer()

        mixed_data = [
            MockScraperData.raw_news_article(),
            MockScraperData.raw_visa_info(),
        ]

        processed = []

        # Process news article
        news_item = normalizer.normalize_news_article(mixed_data[0])
        processed.append(news_item)

        # Process visa info
        visa_item = normalizer.normalize_visa_info(mixed_data[1])
        processed.append(visa_item)

        # Verify both were processed correctly
        assert len(processed) == 2
        assert processed[0]["data_type"] == "news_article"
        assert processed[1]["data_type"] == "visa_info"

        # Verify different structures
        assert "tags" in processed[0]
        assert "requirements" in processed[1]
        assert "fees" in processed[1]
        assert "author" in processed[0]
        assert "visa_type" in processed[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
