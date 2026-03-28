"""
Change Detector - Phase 8

Detects changes in scraped legal documents by comparing content hashes.
Stores document states for historical tracking and change detection.

Features:
- MD5 hash-based change detection
- PostgreSQL storage for document states
- Change type classification (new, updated, deleted)
- Historical tracking with timestamps
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.services.monitoring import AlertLevel, get_alert_service

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of document changes"""

    NEW = "new"  # Document never seen before
    UPDATED = "updated"  # Content changed
    UNCHANGED = "unchanged"  # No change
    DELETED = "deleted"  # Document no longer available


@dataclass
class DocumentState:
    """Stored state of a document for change tracking"""

    document_id: str
    source_id: str
    url: str
    title: str
    content_hash: str
    first_seen: datetime
    last_checked: datetime
    last_changed: datetime | None = None
    change_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to dict for database storage"""
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "content_hash": self.content_hash,
            "first_seen": self.first_seen.isoformat(),
            "last_checked": self.last_checked.isoformat(),
            "last_changed": self.last_changed.isoformat() if self.last_changed else None,
            "change_count": self.change_count,
            "metadata": self.metadata,
            "is_active": self.is_active,
        }

    @classmethod
    def from_db_dict(cls, data: dict[str, Any]) -> "DocumentState":
        """Create from database dict"""
        return cls(
            document_id=data["document_id"],
            source_id=data["source_id"],
            url=data["url"],
            title=data["title"],
            content_hash=data["content_hash"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_checked=datetime.fromisoformat(data["last_checked"]),
            last_changed=datetime.fromisoformat(data["last_changed"])
            if data.get("last_changed")
            else None,
            change_count=data.get("change_count", 0),
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", True),
        )


@dataclass
class ChangeEvent:
    """Represents a detected change"""

    document_id: str
    source_id: str
    change_type: ChangeType
    detected_at: datetime
    old_hash: str | None = None
    new_hash: str | None = None
    title: str = ""
    url: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "change_type": self.change_type.value,
            "detected_at": self.detected_at.isoformat(),
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "title": self.title,
            "url": self.url,
            "details": self.details,
        }


class ChangeDetector:
    """
    Detects changes in scraped documents by comparing content hashes.

    Stores document states in PostgreSQL for persistence across runs.
    """

    def __init__(
        self,
        db_pool=None,
        alert_on_change: bool = True,
        slack_webhook: str | None = None,
    ) -> None:
        """
        Initialize change detector.

        Args:
            db_pool: PostgreSQL connection pool
            alert_on_change: Whether to send alerts on changes
            slack_webhook: Slack webhook URL for alerts
        """
        self.db_pool = db_pool
        self.alert_on_change = alert_on_change
        self.slack_webhook = slack_webhook
        self.alert_service = get_alert_service() if alert_on_change else None

        # In-memory cache of document states (backed by DB)
        self._state_cache: dict[str, DocumentState] = {}

        self.detection_stats = {
            "total_checked": 0,
            "new_documents": 0,
            "updated_documents": 0,
            "unchanged_documents": 0,
            "deleted_documents": 0,
            "last_run": None,
        }

        logger.info("✅ ChangeDetector initialized")
        logger.info(f"   Alert on change: {alert_on_change}")

    async def initialize_db(self) -> None:
        """Initialize database tables for change tracking"""
        if not self.db_pool:
            logger.warning("No DB pool provided, using in-memory storage only")
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS kg_monitored_documents (
                        document_id VARCHAR(32) PRIMARY KEY,
                        source_id VARCHAR(64) NOT NULL,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content_hash VARCHAR(32) NOT NULL,
                        first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
                        last_checked TIMESTAMP WITH TIME ZONE NOT NULL,
                        last_changed TIMESTAMP WITH TIME ZONE,
                        change_count INTEGER DEFAULT 0,
                        metadata JSONB DEFAULT '{}',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_monitored_source
                    ON kg_monitored_documents(source_id)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_monitored_active
                    ON kg_monitored_documents(is_active)
                """)

                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS kg_change_events (
                        id SERIAL PRIMARY KEY,
                        document_id VARCHAR(32) NOT NULL,
                        source_id VARCHAR(64) NOT NULL,
                        change_type VARCHAR(20) NOT NULL,
                        detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        old_hash VARCHAR(32),
                        new_hash VARCHAR(32),
                        title TEXT,
                        url TEXT,
                        details JSONB DEFAULT '{}',
                        notified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_changes_document
                    ON kg_change_events(document_id)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_changes_detected
                    ON kg_change_events(detected_at)
                """)

            logger.info("✅ Change tracking tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize DB tables: {e}")
            raise

    async def detect_changes(
        self,
        documents: list,
        source_id: str,
    ) -> list[ChangeEvent]:
        """
        Detect changes in a batch of documents.

        Args:
            documents: List of ScrapedDocument objects
            source_id: Source identifier

        Returns:
            List of detected change events
        """
        changes = []
        current_doc_ids = set()

        # Load existing states for this source
        await self._load_source_states(source_id)

        for doc in documents:
            doc_id = doc.document_id
            current_doc_ids.add(doc_id)

            change_event = await self._check_document(doc, source_id)
            if change_event:
                changes.append(change_event)

        # Check for deleted documents (in DB but not in current scrape)
        deleted_changes = await self._detect_deletions(source_id, current_doc_ids)
        changes.extend(deleted_changes)

        # Update stats
        self.detection_stats["total_checked"] += len(documents)
        self.detection_stats["new_documents"] += sum(
            1 for c in changes if c.change_type == ChangeType.NEW
        )
        self.detection_stats["updated_documents"] += sum(
            1 for c in changes if c.change_type == ChangeType.UPDATED
        )
        self.detection_stats["unchanged_documents"] += sum(
            1 for c in changes if c.change_type == ChangeType.UNCHANGED
        )
        self.detection_stats["deleted_documents"] += len(deleted_changes)
        self.detection_stats["last_run"] = datetime.now(tz=timezone.utc).isoformat()

        # Send alerts for significant changes
        if self.alert_on_change:
            await self._send_change_alerts(changes)

        logger.info(f"🔍 Change detection complete: {len(changes)} changes detected")
        return changes

    async def _check_document(
        self,
        doc,
        source_id: str,
    ) -> ChangeEvent | None:
        """Check a single document for changes"""
        doc_id = doc.document_id
        new_hash = doc.document_hash
        now = datetime.now(tz=timezone.utc)

        # Get existing state
        existing_state = self._state_cache.get(doc_id)

        if not existing_state:
            # New document
            state = DocumentState(
                document_id=doc_id,
                source_id=source_id,
                url=doc.url,
                title=doc.title,
                content_hash=new_hash,
                first_seen=now,
                last_checked=now,
                last_changed=now,
                metadata=doc.metadata,
            )
            self._state_cache[doc_id] = state
            await self._save_state(state)

            return ChangeEvent(
                document_id=doc_id,
                source_id=source_id,
                change_type=ChangeType.NEW,
                detected_at=now,
                new_hash=new_hash,
                title=doc.title,
                url=doc.url,
                details={"first_seen": True},
            )

        # Update check time
        existing_state.last_checked = now

        if existing_state.content_hash == new_hash:
            # Unchanged
            await self._save_state(existing_state)
            return ChangeEvent(
                document_id=doc_id,
                source_id=source_id,
                change_type=ChangeType.UNCHANGED,
                detected_at=now,
                old_hash=existing_state.content_hash,
                new_hash=new_hash,
                title=doc.title,
                url=doc.url,
            )

        # Updated
        old_hash = existing_state.content_hash
        existing_state.content_hash = new_hash
        existing_state.last_changed = now
        existing_state.change_count += 1
        existing_state.title = doc.title  # Update title in case it changed
        existing_state.is_active = True  # Reactivate if it was marked deleted

        await self._save_state(existing_state)

        return ChangeEvent(
            document_id=doc_id,
            source_id=source_id,
            change_type=ChangeType.UPDATED,
            detected_at=now,
            old_hash=old_hash,
            new_hash=new_hash,
            title=doc.title,
            url=doc.url,
            details={
                "change_count": existing_state.change_count,
                "previous_check": existing_state.last_checked.isoformat(),
            },
        )

    async def _detect_deletions(
        self,
        source_id: str,
        current_doc_ids: set[str],
    ) -> list[ChangeEvent]:
        """Detect documents that are no longer available"""
        deletions = []
        now = datetime.now(tz=timezone.utc)

        # Find documents in cache but not in current scrape
        for doc_id, state in self._state_cache.items():
            if state.source_id != source_id:
                continue
            if not state.is_active:
                continue
            if doc_id not in current_doc_ids:
                # Mark as deleted
                state.is_active = False
                state.last_checked = now
                await self._save_state(state)

                deletions.append(
                    ChangeEvent(
                        document_id=doc_id,
                        source_id=source_id,
                        change_type=ChangeType.DELETED,
                        detected_at=now,
                        old_hash=state.content_hash,
                        title=state.title,
                        url=state.url,
                        details={"previously_active": True},
                    )
                )

        return deletions

    async def _load_source_states(self, source_id: str) -> None:
        """Load document states for a source from DB"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM kg_monitored_documents WHERE source_id = $1", source_id
                )

                for row in rows:
                    state = DocumentState(
                        document_id=row["document_id"],
                        source_id=row["source_id"],
                        url=row["url"],
                        title=row["title"],
                        content_hash=row["content_hash"],
                        first_seen=row["first_seen"],
                        last_checked=row["last_checked"],
                        last_changed=row["last_changed"],
                        change_count=row["change_count"],
                        metadata=row["metadata"],
                        is_active=row["is_active"],
                    )
                    self._state_cache[state.document_id] = state

        except Exception as e:
            logger.error(f"Failed to load source states: {e}")

    async def _save_state(self, state: DocumentState) -> None:
        """Save document state to database"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kg_monitored_documents (
                        document_id, source_id, url, title, content_hash,
                        first_seen, last_checked, last_changed, change_count,
                        metadata, is_active, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                    ON CONFLICT (document_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        content_hash = EXCLUDED.content_hash,
                        last_checked = EXCLUDED.last_checked,
                        last_changed = EXCLUDED.last_changed,
                        change_count = EXCLUDED.change_count,
                        metadata = EXCLUDED.metadata,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()
                    """,
                    state.document_id,
                    state.source_id,
                    state.url,
                    state.title,
                    state.content_hash,
                    state.first_seen,
                    state.last_checked,
                    state.last_changed,
                    state.change_count,
                    state.metadata,
                    state.is_active,
                )

                # Log change event if applicable
                await self._log_change_event(state)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def _log_change_event(self, state: DocumentState) -> None:
        """Log change event to database"""
        if not self.db_pool or not state.last_changed:
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kg_change_events (
                        document_id, source_id, change_type, detected_at,
                        new_hash, title, url
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    state.document_id,
                    state.source_id,
                    ChangeType.UPDATED.value if state.change_count > 0 else ChangeType.NEW.value,
                    state.last_changed,
                    state.content_hash,
                    state.title,
                    state.url,
                )
        except Exception as e:
            logger.error(f"Failed to log change event: {e}")

    async def _send_change_alerts(self, changes: list[ChangeEvent]) -> None:
        """Send alerts for significant changes"""
        if not self.alert_service:
            return

        # Only alert on new and updated documents (not unchanged or deleted)
        alert_changes = [
            c for c in changes if c.change_type in (ChangeType.NEW, ChangeType.UPDATED)
        ]

        if not alert_changes:
            return

        # Group by source
        by_source: dict[str, list[ChangeEvent]] = {}
        for change in alert_changes:
            by_source.setdefault(change.source_id, []).append(change)

        for source_id, source_changes in by_source.items():
            new_count = sum(1 for c in source_changes if c.change_type == ChangeType.NEW)
            updated_count = sum(1 for c in source_changes if c.change_type == ChangeType.UPDATED)

            title = f"📄 Legal Documents Changed: {source_id}"
            message = f"Detected {new_count} new and {updated_count} updated documents"

            # Include document titles in details
            doc_list = "\n".join([f"- {c.title[:80]}" for c in source_changes[:5]])
            if len(source_changes) > 5:
                doc_list += f"\n... and {len(source_changes) - 5} more"

            metadata = {
                "source": source_id,
                "new_documents": new_count,
                "updated_documents": updated_count,
                "documents": doc_list,
            }

            level = AlertLevel.INFO if new_count + updated_count < 5 else AlertLevel.WARNING

            try:
                await self.alert_service.send_alert(
                    title=title,
                    message=message,
                    level=level,
                    metadata=metadata,
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics"""
        return {
            **self.detection_stats,
            "cached_states": len(self._state_cache),
        }

    async def get_recent_changes(
        self,
        source_id: str | None = None,
        hours: int = 24,
        change_type: ChangeType | None = None,
    ) -> list[ChangeEvent]:
        """Get recent changes from database"""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                query = f"""
                    SELECT * FROM kg_change_events
                    WHERE detected_at > NOW() - INTERVAL '{hours} hours'
                """

                params = []
                if source_id:
                    query += " AND source_id = $1"
                    params.append(source_id)
                if change_type:
                    query += f" AND change_type = '${len(params) + 1}'"
                    params.append(change_type.value)

                query += " ORDER BY detected_at DESC"

                rows = await conn.fetch(query, *params)

                return [
                    ChangeEvent(
                        document_id=row["document_id"],
                        source_id=row["source_id"],
                        change_type=ChangeType(row["change_type"]),
                        detected_at=row["detected_at"],
                        old_hash=row["old_hash"],
                        new_hash=row["new_hash"],
                        title=row["title"],
                        url=row["url"],
                        details=row["details"],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get recent changes: {e}")
            return []

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute MD5 hash of content"""
        return hashlib.md5(content.encode()).hexdigest()
