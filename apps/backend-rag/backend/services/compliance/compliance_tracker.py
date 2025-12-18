"""
Compliance Tracker Service
Responsibility: Track compliance items
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComplianceItem:
    """Single compliance tracking item"""

    item_id: str
    client_id: str
    compliance_type: str  # ComplianceType enum value
    title: str
    description: str
    deadline: str  # ISO date
    requirement_details: str
    estimated_cost: float | None = None
    required_documents: list[str] = field(default_factory=list)
    renewal_process: str | None = None
    source_oracle: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ComplianceTrackerService:
    """
    Service for tracking compliance items.

    Responsibility: Add, retrieve, and manage compliance items.
    """

    def __init__(self):
        """Initialize compliance tracker service."""
        # Storage (in production, use database)
        self.compliance_items: dict[str, ComplianceItem] = {}
        self.tracker_stats = {
            "total_items_tracked": 0,
            "active_items": 0,
            "compliance_type_distribution": {},
        }

    def add_compliance_item(
        self,
        client_id: str,
        compliance_type: str,
        title: str,
        deadline: str,
        description: str = "",
        estimated_cost: float | None = None,
        required_documents: list[str] | None = None,
        metadata: dict | None = None,
    ) -> ComplianceItem:
        """
        Add a new compliance item to track.

        Args:
            client_id: Client identifier
            compliance_type: Type of compliance
            title: Item title
            deadline: Deadline (ISO date)
            description: Item description
            estimated_cost: Estimated cost in IDR
            required_documents: List of required documents
            metadata: Additional metadata

        Returns:
            ComplianceItem instance
        """
        item_id = f"{compliance_type}_{client_id}_{int(datetime.now().timestamp())}"

        item = ComplianceItem(
            item_id=item_id,
            client_id=client_id,
            compliance_type=compliance_type,
            title=title,
            description=description,
            deadline=deadline,
            requirement_details=description,
            estimated_cost=estimated_cost,
            required_documents=required_documents or [],
            metadata=metadata or {},
        )

        self.compliance_items[item_id] = item

        # Update stats
        self.tracker_stats["total_items_tracked"] += 1
        self.tracker_stats["active_items"] += 1
        self.tracker_stats["compliance_type_distribution"][compliance_type] = (
            self.tracker_stats["compliance_type_distribution"].get(compliance_type, 0) + 1
        )

        logger.info(f"📋 Added compliance item: {item_id} - {title} (deadline: {deadline})")

        return item

    def get_compliance_item(self, item_id: str) -> ComplianceItem | None:
        """
        Get compliance item by ID.

        Args:
            item_id: Compliance item identifier

        Returns:
            ComplianceItem instance or None
        """
        return self.compliance_items.get(item_id)

    def get_upcoming_deadlines(
        self, client_id: str | None = None, days_ahead: int = 90
    ) -> list[ComplianceItem]:
        """
        Get upcoming compliance deadlines.

        Args:
            client_id: Optional filter by client
            days_ahead: Look ahead window in days

        Returns:
            List of upcoming compliance items
        """
        from datetime import timedelta

        cutoff_date = datetime.now() + timedelta(days=days_ahead)

        upcoming = []
        for item in self.compliance_items.values():
            if client_id and item.client_id != client_id:
                continue

            deadline_date = datetime.fromisoformat(item.deadline.replace("Z", ""))
            if deadline_date <= cutoff_date:
                upcoming.append(item)

        # Sort by deadline
        upcoming.sort(key=lambda x: x.deadline)

        return upcoming

    def resolve_compliance_item(self, item_id: str) -> bool:
        """
        Mark compliance item as resolved.

        Args:
            item_id: Compliance item identifier

        Returns:
            True if resolved
        """
        if item_id not in self.compliance_items:
            return False

        # Remove from active tracking
        del self.compliance_items[item_id]

        # Update stats
        self.tracker_stats["active_items"] -= 1

        logger.info(f"✅ Resolved compliance item: {item_id}")
        return True

    def get_all_items(self, client_id: str | None = None) -> list[ComplianceItem]:
        """
        Get all compliance items, optionally filtered by client.

        Args:
            client_id: Optional client filter

        Returns:
            List of compliance items
        """
        if client_id:
            return [item for item in self.compliance_items.values() if item.client_id == client_id]
        return list(self.compliance_items.values())

    def get_stats(self) -> dict:
        """Get tracker statistics."""
        return {
            **self.tracker_stats,
            "total_items": len(self.compliance_items),
        }
