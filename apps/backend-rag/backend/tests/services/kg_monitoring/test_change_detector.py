"""
Tests for ChangeDetector - Phase 8
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.services.kg_monitoring.change_detector import (
    ChangeDetector,
    ChangeEvent,
    ChangeType,
    DocumentState,
)
from backend.services.kg_monitoring.scraper import ScrapedDocument


class TestChangeType:
    """Test ChangeType enum"""

    def test_change_type_values(self):
        """Test change type enum values"""
        assert ChangeType.NEW.value == "new"
        assert ChangeType.UPDATED.value == "updated"
        assert ChangeType.UNCHANGED.value == "unchanged"
        assert ChangeType.DELETED.value == "deleted"


class TestDocumentState:
    """Test DocumentState dataclass"""

    def test_state_creation(self):
        """Test creating document state"""
        now = datetime.now(tz=timezone.utc)
        state = DocumentState(
            document_id="doc123",
            source_id="test_source",
            url="https://example.com/doc",
            title="Test Doc",
            content_hash="abc123hash",
            first_seen=now,
            last_checked=now,
        )

        assert state.document_id == "doc123"
        assert state.change_count == 0
        assert state.is_active is True

    def test_to_db_dict(self):
        """Test conversion to database dict"""
        now = datetime.now(tz=timezone.utc)
        state = DocumentState(
            document_id="doc123",
            source_id="test_source",
            url="https://example.com",
            title="Test",
            content_hash="hash",
            first_seen=now,
            last_checked=now,
        )

        db_dict = state.to_db_dict()
        assert db_dict["document_id"] == "doc123"
        assert db_dict["source_id"] == "test_source"
        assert "first_seen" in db_dict

    def test_from_db_dict(self):
        """Test creation from database dict"""
        now = datetime.now(tz=timezone.utc)
        data = {
            "document_id": "doc123",
            "source_id": "test",
            "url": "https://example.com",
            "title": "Test",
            "content_hash": "hash",
            "first_seen": now.isoformat(),
            "last_checked": now.isoformat(),
            "last_changed": None,
            "change_count": 2,
            "metadata": {"key": "value"},
            "is_active": True,
        }

        state = DocumentState.from_db_dict(data)
        assert state.document_id == "doc123"
        assert state.change_count == 2
        assert state.metadata == {"key": "value"}


class TestChangeEvent:
    """Test ChangeEvent dataclass"""

    def test_event_creation(self):
        """Test creating change event"""
        event = ChangeEvent(
            document_id="doc123",
            source_id="test_source",
            change_type=ChangeType.NEW,
            detected_at=datetime.now(tz=timezone.utc),
            new_hash="hash123",
            title="Test Doc",
            url="https://example.com",
        )

        assert event.change_type == ChangeType.NEW
        assert event.old_hash is None

    def test_to_dict(self):
        """Test conversion to dict"""
        now = datetime.now(tz=timezone.utc)
        event = ChangeEvent(
            document_id="doc123",
            source_id="test",
            change_type=ChangeType.UPDATED,
            detected_at=now,
            old_hash="old",
            new_hash="new",
            title="Test",
            url="https://example.com",
            details={"key": "value"},
        )

        d = event.to_dict()
        assert d["document_id"] == "doc123"
        assert d["change_type"] == "updated"
        assert d["old_hash"] == "old"
        assert d["details"]["key"] == "value"


class TestChangeDetector:
    """Test ChangeDetector functionality"""

    def test_initialization(self):
        """Test detector initialization"""
        detector = ChangeDetector(alert_on_change=False)

        assert detector.alert_on_change is False
        assert detector._state_cache == {}
        assert detector.detection_stats["total_checked"] == 0

    def test_initialization_with_alert(self):
        """Test detector with alerts enabled"""
        detector = ChangeDetector(alert_on_change=True)

        assert detector.alert_on_change is True
        assert detector.alert_service is not None

    @pytest.mark.asyncio
    async def test_detect_new_document(self):
        """Test detecting a new document"""
        detector = ChangeDetector(alert_on_change=False)

        doc = ScrapedDocument(
            document_id="new_doc",
            source_id="test_source",
            title="New Document",
            url="https://example.com/new",
            content="New content",
            raw_html="<p>New</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        changes = await detector.detect_changes([doc], "test_source")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NEW
        assert changes[0].document_id == "new_doc"
        assert detector.detection_stats["new_documents"] == 1

    @pytest.mark.asyncio
    async def test_detect_unchanged_document(self):
        """Test detecting an unchanged document"""
        detector = ChangeDetector(alert_on_change=False)

        doc_id = "existing_doc"
        content_hash = "existing_hash"

        # Pre-populate cache
        detector._state_cache[doc_id] = DocumentState(
            document_id=doc_id,
            source_id="test_source",
            url="https://example.com",
            title="Existing",
            content_hash=content_hash,
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )

        # Create document with same hash
        doc = ScrapedDocument(
            document_id=doc_id,
            source_id="test_source",
            title="Existing",
            url="https://example.com",
            content="Content that produces same hash",
            raw_html="<p>Same</p>",
            scraped_at=datetime.now(tz=timezone.utc),
            document_hash=content_hash,
        )

        changes = await detector.detect_changes([doc], "test_source")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.UNCHANGED

    @pytest.mark.asyncio
    async def test_detect_updated_document(self):
        """Test detecting an updated document"""
        detector = ChangeDetector(alert_on_change=False)

        doc_id = "update_doc"

        # Pre-populate cache with old hash
        detector._state_cache[doc_id] = DocumentState(
            document_id=doc_id,
            source_id="test_source",
            url="https://example.com",
            title="Old Title",
            content_hash="old_hash",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
            change_count=0,
        )

        # Create document with new hash
        doc = ScrapedDocument(
            document_id=doc_id,
            source_id="test_source",
            title="New Title",
            url="https://example.com",
            content="New content for new hash",
            raw_html="<p>New</p>",
            scraped_at=datetime.now(tz=timezone.utc),
            document_hash="new_hash",
        )

        changes = await detector.detect_changes([doc], "test_source")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.UPDATED
        assert changes[0].old_hash == "old_hash"
        assert changes[0].new_hash == "new_hash"
        assert detector.detection_stats["updated_documents"] == 1
        assert detector._state_cache[doc_id].change_count == 1

    @pytest.mark.asyncio
    async def test_detect_deleted_document(self):
        """Test detecting a deleted document"""
        detector = ChangeDetector(alert_on_change=False)

        # Pre-populate cache with document that's no longer in scrape
        detector._state_cache["deleted_doc"] = DocumentState(
            document_id="deleted_doc",
            source_id="test_source",
            url="https://example.com/deleted",
            title="Deleted Doc",
            content_hash="hash",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
            is_active=True,
        )

        # Empty scrape result
        changes = await detector.detect_changes([], "test_source")

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.DELETED
        assert changes[0].document_id == "deleted_doc"
        assert detector._state_cache["deleted_doc"].is_active is False

    @pytest.mark.asyncio
    async def test_multiple_changes(self):
        """Test detecting multiple changes at once"""
        detector = ChangeDetector(alert_on_change=False)

        # Pre-populate with existing docs
        detector._state_cache["existing1"] = DocumentState(
            document_id="existing1",
            source_id="test",
            url="https://example.com/1",
            title="Doc 1",
            content_hash="hash1",
            first_seen=datetime.now(tz=timezone.utc),
            last_checked=datetime.now(tz=timezone.utc),
        )

        docs = [
            # New document
            ScrapedDocument(
                document_id="new_doc",
                source_id="test",
                title="New",
                url="https://example.com/new",
                content="New content",
                raw_html="<p>New</p>",
                scraped_at=datetime.now(tz=timezone.utc),
            ),
            # Unchanged document
            ScrapedDocument(
                document_id="existing1",
                source_id="test",
                title="Doc 1",
                url="https://example.com/1",
                content="Content for hash1",
                raw_html="<p>Same</p>",
                scraped_at=datetime.now(tz=timezone.utc),
                document_hash="hash1",
            ),
        ]

        changes = await detector.detect_changes(docs, "test")

        assert len(changes) == 2
        types = {c.change_type for c in changes}
        assert ChangeType.NEW in types
        assert ChangeType.UNCHANGED in types

    def test_get_stats(self):
        """Test getting detector statistics"""
        detector = ChangeDetector(alert_on_change=False)
        detector.detection_stats = {
            "total_checked": 100,
            "new_documents": 10,
            "updated_documents": 5,
            "unchanged_documents": 80,
            "deleted_documents": 5,
            "last_run": datetime.now(tz=timezone.utc).isoformat(),
        }
        detector._state_cache = {"doc1": MagicMock(), "doc2": MagicMock()}

        stats = detector.get_stats()

        assert stats["total_checked"] == 100
        assert stats["cached_states"] == 2

    def test_compute_hash(self):
        """Test hash computation"""
        hash1 = ChangeDetector.compute_hash("test content")
        hash2 = ChangeDetector.compute_hash("test content")
        hash3 = ChangeDetector.compute_hash("different content")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 32  # MD5 hex is 32 chars
