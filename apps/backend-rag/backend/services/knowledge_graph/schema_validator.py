"""
KG Schema Validator

Validates edges against the ontology before persistence.
Invalid edges are quarantined for review rather than silently dropped.

Author: Nuzantara Team
Date: 2026-04-14
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.knowledge_graph.ontology import (
    EntityType,
    RelationType,
    RELATION_SCHEMAS,
)

logger = logging.getLogger(__name__)

# Prometheus metrics
try:
    from prometheus_client import Counter

    kg_schema_violations_total = Counter(
        "kg_schema_violations_total",
        "KG schema validation violations",
        ["relation_type", "source_type", "target_type"],
    )
except ImportError:
    kg_schema_violations_total = None  # type: ignore[assignment]


def _inc_violation(relation_type: str, source_type: str, target_type: str) -> None:
    """Increment violation counter if Prometheus is available."""
    if kg_schema_violations_total is not None:
        kg_schema_violations_total.labels(
            relation_type=relation_type,
            source_type=source_type,
            target_type=target_type,
        ).inc()


@dataclass
class QuarantinedEdge:
    """An edge that failed schema validation."""

    source_id: str
    target_id: str
    source_type: str
    target_type: str
    relation_type: str
    reason: str
    evidence: str = ""
    confidence: float = 0.0


@dataclass
class ValidationResult:
    """Result of schema validation for a batch of edges."""

    valid_count: int = 0
    invalid_count: int = 0
    quarantined: list[QuarantinedEdge] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.valid_count + self.invalid_count

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for logging/metrics."""
        return {
            "valid": self.valid_count,
            "invalid": self.invalid_count,
            "total": self.total,
            "quarantined_count": len(self.quarantined),
        }


def validate_edge(
    source_type: str,
    target_type: str,
    relation_type: str,
) -> bool:
    """
    Validate that an edge conforms to the ontology schema.

    Checks:
    1. relation_type is a known RelationType
    2. If schema exists for the relation, source_type is in allowed source_types
    3. If schema exists for the relation, target_type is in allowed target_types

    Args:
        source_type: Entity type of the source node (e.g. "pasal")
        target_type: Entity type of the target node (e.g. "proses")
        relation_type: Relation type (e.g. "HAS_PROCEDURE")

    Returns:
        True if edge conforms to schema, False otherwise
    """
    # Normalize inputs
    source_type_lower = source_type.lower() if source_type else ""
    target_type_lower = target_type.lower() if target_type else ""
    relation_upper = relation_type.upper() if relation_type else ""

    # Check if relation_type is known
    try:
        rel_enum = RelationType(relation_upper)
    except ValueError:
        logger.warning(
            "Schema violation: unknown relation_type=%s (source=%s, target=%s)",
            relation_type,
            source_type,
            target_type,
        )
        _inc_violation(relation_type, source_type, target_type)
        return False

    # If no schema defined for this relation, allow it (open-world assumption)
    schema = RELATION_SCHEMAS.get(rel_enum)
    if schema is None:
        return True

    # Validate source_type
    try:
        src_enum = EntityType(source_type_lower)
    except ValueError:
        # Unknown source type -- cannot validate, quarantine
        logger.warning(
            "Schema violation: unknown source_type=%s for relation=%s",
            source_type,
            relation_type,
        )
        _inc_violation(relation_type, source_type, target_type)
        return False

    if schema.source_types and src_enum not in schema.source_types:
        logger.warning(
            "Schema violation: source_type=%s not allowed for relation=%s "
            "(allowed: %s)",
            source_type,
            relation_type,
            [t.value for t in schema.source_types],
        )
        _inc_violation(relation_type, source_type, target_type)
        return False

    # Validate target_type
    try:
        tgt_enum = EntityType(target_type_lower)
    except ValueError:
        logger.warning(
            "Schema violation: unknown target_type=%s for relation=%s",
            target_type,
            relation_type,
        )
        _inc_violation(relation_type, source_type, target_type)
        return False

    if schema.target_types and tgt_enum not in schema.target_types:
        logger.warning(
            "Schema violation: target_type=%s not allowed for relation=%s "
            "(allowed: %s)",
            target_type,
            relation_type,
            [t.value for t in schema.target_types],
        )
        _inc_violation(relation_type, source_type, target_type)
        return False

    return True


class SchemaValidator:
    """
    Batch schema validator with quarantine tracking.

    Usage:
        validator = SchemaValidator()
        for relation in relations:
            if validator.check(relation):
                # persist edge
            else:
                # edge is quarantined in validator.result.quarantined
        logger.info(validator.result.summary())
    """

    def __init__(self) -> None:
        self.result = ValidationResult()

    def check(
        self,
        source_id: str,
        target_id: str,
        source_type: str,
        target_type: str,
        relation_type: str,
        evidence: str = "",
        confidence: float = 0.0,
    ) -> bool:
        """
        Validate a single edge and quarantine if invalid.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            source_type: Source entity type
            target_type: Target entity type
            relation_type: Relation type
            evidence: Evidence text for the edge
            confidence: Confidence score

        Returns:
            True if valid, False if quarantined
        """
        if validate_edge(source_type, target_type, relation_type):
            self.result.valid_count += 1
            return True

        # Determine reason
        reason = _build_violation_reason(source_type, target_type, relation_type)

        self.result.invalid_count += 1
        self.result.quarantined.append(
            QuarantinedEdge(
                source_id=source_id,
                target_id=target_id,
                source_type=source_type,
                target_type=target_type,
                relation_type=relation_type,
                reason=reason,
                evidence=evidence,
                confidence=confidence,
            ),
        )
        return False


def _build_violation_reason(
    source_type: str,
    target_type: str,
    relation_type: str,
) -> str:
    """Build a human-readable violation reason."""
    relation_upper = relation_type.upper() if relation_type else ""

    try:
        rel_enum = RelationType(relation_upper)
    except ValueError:
        return f"Unknown relation type: {relation_type}"

    schema = RELATION_SCHEMAS.get(rel_enum)
    if schema is None:
        return f"No schema defined for {relation_type}"

    source_lower = source_type.lower() if source_type else ""
    target_lower = target_type.lower() if target_type else ""

    try:
        src_enum = EntityType(source_lower)
    except ValueError:
        return f"Unknown source entity type: {source_type}"

    if schema.source_types and src_enum not in schema.source_types:
        allowed = [t.value for t in schema.source_types]
        return (
            f"Source type '{source_type}' not allowed for {relation_type}. "
            f"Allowed: {allowed}"
        )

    try:
        EntityType(target_lower)
    except ValueError:
        return f"Unknown target entity type: {target_type}"

    allowed_targets = [t.value for t in schema.target_types]
    return (
        f"Target type '{target_type}' not allowed for {relation_type}. "
        f"Allowed: {allowed_targets}"
    )
