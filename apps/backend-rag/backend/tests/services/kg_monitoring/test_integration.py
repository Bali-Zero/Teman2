"""
Integration Tests for KG Monitoring Service - Phase 8

Tests the full pipeline from scraping to ingestion.
"""

from datetime import datetime, timezone

import pytest

from backend.services.kg_monitoring import (
    AutoIngestionService,
    ChangeDetector,
    LegalScraper,
    QualityCheckService,
)
from backend.services.kg_monitoring.change_detector import ChangeType
from backend.services.kg_monitoring.scraper import ScrapedDocument


class TestMonitoringPipeline:
    """Test the full monitoring pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline_new_document(self):
        """Test full pipeline with a new document"""
        # Setup components
        LegalScraper()
        detector = ChangeDetector(alert_on_change=False)
        quality = QualityCheckService()
        ingestion = AutoIngestionService(quality_service=quality)

        # Create test document
        doc = ScrapedDocument(
            document_id="test_pipeline_doc",
            source_id="test_source",
            title="UU Test Pipeline",
            url="https://example.com/test",
            content="Pasal 1: Testing the pipeline " * 20,
            raw_html="<article>Test</article>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        # Step 1: Detect changes (should be NEW)
        changes = await detector.detect_changes([doc], "test_source")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NEW

        # Step 2: Quality check
        # First need to extract structured data
        extracted = await ingestion._extract_document(doc)
        report = await quality.validate(extracted)

        # Should be acceptable or have clear issues
        assert report.overall_score >= 0
        assert report.document_id == "test_pipeline_doc"

    @pytest.mark.asyncio
    async def test_full_pipeline_updated_document(self):
        """Test full pipeline with an updated document"""
        detector = ChangeDetector(alert_on_change=False)

        # Pre-populate with existing document
        from backend.services.kg_monitoring.change_detector import DocumentState

        detector._state_cache["update_test"] = DocumentState(
            document_id="update_test",
            source_id="test",
            url="https://example.com",
            title="Old Title",
            content_hash="old_hash_123",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )

        # Create updated document
        updated_doc = ScrapedDocument(
            document_id="update_test",
            source_id="test",
            title="New Title",
            url="https://example.com",
            content="New content with different hash",
            raw_html="<p>New</p>",
            scraped_at=datetime.now(tz=timezone.utc),
            document_hash="new_hash_456",
        )

        # Detect changes
        changes = await detector.detect_changes([updated_doc], "test")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.UPDATED
        assert changes[0].old_hash == "old_hash_123"
        assert changes[0].new_hash == "new_hash_456"

    @pytest.mark.asyncio
    async def test_scraper_to_detector_integration(self):
        """Test scraper output works with detector"""
        LegalScraper()
        detector = ChangeDetector(alert_on_change=False)

        # Mock scraping to return test documents
        test_docs = [
            ScrapedDocument(
                document_id=f"int_test_{i}",
                source_id="test_source",
                title=f"Document {i}",
                url=f"https://example.com/{i}",
                content=f"Content {i} " * 50,
                raw_html=f"<p>Doc {i}</p>",
                scraped_at=datetime.now(tz=timezone.utc),
            )
            for i in range(3)
        ]

        # All should be new
        changes = await detector.detect_changes(test_docs, "test_source")

        new_changes = [c for c in changes if c.change_type == ChangeType.NEW]
        assert len(new_changes) == 3

    def test_quality_service_integration(self):
        """Test quality service with various document types"""
        from backend.services.kg_monitoring.auto_ingestion import DocumentType, ExtractedDocument
        from backend.services.kg_monitoring.quality_check import QualityLevel

        # Test with strict quality service
        quality = QualityCheckService(min_accept_score=0.60, strict_mode=True)

        # Test various document types
        test_cases = [
            {
                "doc": ExtractedDocument(
                    document_id="good",
                    source_id="test",
                    title="UU No. 13 Tahun 2003 Tentang Ketenagakerjaan Yang Sangat Penting",
                    document_type=DocumentType.UNDANG_UNDANG,
                    document_number="UU No. 13 Tahun 2003",
                    issuing_authority="DPR RI",
                    full_text="Pasal 1: Ketentuan umum tentang ketenagakerjaan di Indonesia. "
                    * 100,
                    key_points=["Point 1", "Point 2", "Point 3"],
                    confidence_score=0.9,
                ),
                "expected_quality": [QualityLevel.GOOD, QualityLevel.EXCELLENT],
            },
            {
                "doc": ExtractedDocument(
                    document_id="bad",
                    source_id="test",
                    title="X",
                    document_type=DocumentType.OTHER,
                    full_text="Too short",
                ),
                "expected_quality": [QualityLevel.POOR, QualityLevel.REJECT],
            },
        ]

        for case in test_cases:
            # Run async validation in sync context
            import asyncio

            report = asyncio.run(quality.validate(case["doc"]))

            # Check quality level matches expectation
            assert report.quality_level in case["expected_quality"], (
                f"Expected {case['doc'].document_id} to have quality in {case['expected_quality']}, got {report.quality_level}"
            )


class TestEndToEndScenarios:
    """Test end-to-end scenarios"""

    @pytest.mark.asyncio
    async def test_no_changes_scenario(self):
        """Test scenario with no changes"""
        detector = ChangeDetector(alert_on_change=False)

        # Add existing document to cache
        from backend.services.kg_monitoring.change_detector import DocumentState

        detector._state_cache["unchanged"] = DocumentState(
            document_id="unchanged",
            source_id="test",
            url="https://example.com",
            title="Same",
            content_hash="same_hash",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )

        # Scrape same document
        doc = ScrapedDocument(
            document_id="unchanged",
            source_id="test",
            title="Same",
            url="https://example.com",
            content="Content for same_hash",
            raw_html="<p>Same</p>",
            scraped_at=datetime.now(tz=timezone.utc),
            document_hash="same_hash",
        )

        changes = await detector.detect_changes([doc], "test")

        # Should detect as unchanged
        unchanged = [c for c in changes if c.change_type == ChangeType.UNCHANGED]
        assert len(unchanged) == 1

    @pytest.mark.asyncio
    async def test_mixed_changes_scenario(self):
        """Test scenario with mixed changes (new, updated, unchanged)"""
        detector = ChangeDetector(alert_on_change=False)

        # Pre-populate with some existing documents
        from backend.services.kg_monitoring.change_detector import DocumentState

        detector._state_cache["existing_unchanged"] = DocumentState(
            document_id="existing_unchanged",
            source_id="test",
            url="https://example.com/1",
            title="Unchanged",
            content_hash="hash1",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )
        detector._state_cache["existing_updated"] = DocumentState(
            document_id="existing_updated",
            source_id="test",
            url="https://example.com/2",
            title="Will Update",
            content_hash="old_hash",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )

        # Scrape mixed documents
        docs = [
            ScrapedDocument(
                document_id="new_doc",
                source_id="test",
                title="Brand New",
                url="https://example.com/new",
                content="New content",
                raw_html="<p>New</p>",
                scraped_at=datetime.now(tz=timezone.utc),
            ),
            ScrapedDocument(
                document_id="existing_unchanged",
                source_id="test",
                title="Unchanged",
                url="https://example.com/1",
                content="Content for hash1",
                raw_html="<p>Same</p>",
                scraped_at=datetime.now(tz=timezone.utc),
                document_hash="hash1",
            ),
            ScrapedDocument(
                document_id="existing_updated",
                source_id="test",
                title="Updated",
                url="https://example.com/2",
                content="New content here",
                raw_html="<p>Updated</p>",
                scraped_at=datetime.now(tz=timezone.utc),
                document_hash="new_hash",
            ),
        ]

        changes = await detector.detect_changes(docs, "test")

        # Verify each type
        by_type = {}
        for c in changes:
            by_type.setdefault(c.change_type, []).append(c)

        assert ChangeType.NEW in by_type
        assert ChangeType.UNCHANGED in by_type
        assert ChangeType.UPDATED in by_type

    @pytest.mark.asyncio
    async def test_document_deletion_scenario(self):
        """Test scenario where documents are deleted"""
        detector = ChangeDetector(alert_on_change=False)

        # Pre-populate with document that won't be in scrape
        from backend.services.kg_monitoring.change_detector import DocumentState

        detector._state_cache["deleted_doc"] = DocumentState(
            document_id="deleted_doc",
            source_id="test",
            url="https://example.com/gone",
            title="Deleted",
            content_hash="hash",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
            is_active=True,
        )

        # Empty scrape (document is gone)
        changes = await detector.detect_changes([], "test")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.DELETED
        assert changes[0].document_id == "deleted_doc"
