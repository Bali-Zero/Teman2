"""
Tests for KG Schema Validator

Validates that schema_validator correctly enforces ontology constraints
and quarantines invalid edges.
"""

import pytest

from backend.services.knowledge_graph.schema_validator import (
    QuarantinedEdge,
    SchemaValidator,
    ValidationResult,
    validate_edge,
)


class TestValidateEdge:
    """Tests for the validate_edge function."""

    def test_valid_edge_pasal_has_procedure(self) -> None:
        """PASAL -> PROSES via HAS_PROCEDURE should pass."""
        assert validate_edge("pasal", "proses", "HAS_PROCEDURE") is True

    def test_valid_edge_kitas_issued_by_imigrasi(self) -> None:
        """KITAS -> IMIGRASI via ISSUED_BY should pass."""
        assert validate_edge("kitas", "imigrasi", "ISSUED_BY") is True

    def test_valid_edge_pt_pma_requires_nib(self) -> None:
        """PT_PMA -> NIB via REQUIRES should pass."""
        assert validate_edge("pt_pma", "nib", "REQUIRES") is True

    def test_valid_edge_kitas_has_fee_biaya(self) -> None:
        """KITAS -> BIAYA via HAS_FEE should pass."""
        assert validate_edge("kitas", "biaya", "HAS_FEE") is True

    def test_invalid_edge_pasal_issued_by_kementerian(self) -> None:
        """PASAL -> KEMENTERIAN via ISSUED_BY should fail.

        ISSUED_BY source_types are [NIB, KITAS, IMTA], not PASAL.
        """
        assert validate_edge("pasal", "kementerian", "ISSUED_BY") is False

    def test_invalid_edge_wrong_target(self) -> None:
        """NIB -> PASAL via ISSUED_BY should fail.

        ISSUED_BY target_types are [OSS, IMIGRASI, KEMENAKER], not PASAL.
        """
        assert validate_edge("nib", "pasal", "ISSUED_BY") is False

    def test_invalid_edge_unknown_relation(self) -> None:
        """Unknown relation type should fail."""
        assert validate_edge("pasal", "proses", "INVENTED_RELATION") is False

    def test_invalid_edge_unknown_source_type(self) -> None:
        """Unknown source entity type should fail."""
        assert validate_edge("nonexistent_type", "nib", "REQUIRES") is False

    def test_invalid_edge_unknown_target_type(self) -> None:
        """Unknown target entity type should fail."""
        assert validate_edge("pt_pma", "nonexistent_type", "REQUIRES") is False

    def test_valid_edge_no_schema_defined(self) -> None:
        """Relations without schema definitions should pass (open-world)."""
        # BLOCKED_BY and ALLOWED_IF have no schema in RELATION_SCHEMAS
        assert validate_edge("kitas", "proses", "BLOCKED_BY") is True

    def test_case_insensitive_types(self) -> None:
        """Entity types should be case-insensitive."""
        assert validate_edge("PASAL", "PROSES", "HAS_PROCEDURE") is True
        assert validate_edge("Pasal", "Proses", "has_procedure") is True

    def test_empty_inputs(self) -> None:
        """Empty inputs should fail gracefully."""
        assert validate_edge("", "", "") is False

    def test_valid_amends_relation(self) -> None:
        """UU -> UU via AMENDS should pass."""
        assert validate_edge("undang_undang", "undang_undang", "AMENDS") is True

    def test_valid_implements_relation(self) -> None:
        """PP -> UU via IMPLEMENTS should pass."""
        assert validate_edge("peraturan_pemerintah", "undang_undang", "IMPLEMENTS") is True

    def test_invalid_implements_wrong_source(self) -> None:
        """PASAL -> UU via IMPLEMENTS should fail (PASAL not in source_types)."""
        assert validate_edge("pasal", "undang_undang", "IMPLEMENTS") is False

    def test_valid_tax_obligation(self) -> None:
        """PT_PMA -> PPH via TAX_OBLIGATION should pass."""
        assert validate_edge("pt_pma", "pph", "TAX_OBLIGATION") is True

    def test_valid_classified_as(self) -> None:
        """PT_PMA -> KBLI via CLASSIFIED_AS should pass."""
        assert validate_edge("pt_pma", "kbli", "CLASSIFIED_AS") is True

    def test_valid_part_of(self) -> None:
        """AYAT -> PASAL via PART_OF should pass."""
        assert validate_edge("ayat", "pasal", "PART_OF") is True

    def test_valid_references(self) -> None:
        """PASAL -> UU via REFERENCES should pass."""
        assert validate_edge("pasal", "undang_undang", "REFERENCES") is True


class TestSchemaValidator:
    """Tests for the SchemaValidator batch validator."""

    def test_batch_validation_mixed(self) -> None:
        """Test batch with mix of valid and invalid edges."""
        validator = SchemaValidator()

        # Valid edge
        result1 = validator.check(
            source_id="entity_1",
            target_id="entity_2",
            source_type="kitas",
            target_type="imigrasi",
            relation_type="ISSUED_BY",
            evidence="KITAS diterbitkan oleh Imigrasi",
            confidence=0.9,
        )
        assert result1 is True

        # Invalid edge
        result2 = validator.check(
            source_id="entity_3",
            target_id="entity_4",
            source_type="pasal",
            target_type="kementerian",
            relation_type="ISSUED_BY",
            evidence="fake evidence",
            confidence=0.5,
        )
        assert result2 is False

        # Check result counts
        assert validator.result.valid_count == 1
        assert validator.result.invalid_count == 1
        assert validator.result.total == 2
        assert len(validator.result.quarantined) == 1

    def test_quarantine_captures_details(self) -> None:
        """Quarantined edges should contain full context."""
        validator = SchemaValidator()
        validator.check(
            source_id="src_123",
            target_id="tgt_456",
            source_type="pasal",
            target_type="kementerian",
            relation_type="ISSUED_BY",
            evidence="some evidence text",
            confidence=0.75,
        )

        assert len(validator.result.quarantined) == 1
        quarantined = validator.result.quarantined[0]
        assert quarantined.source_id == "src_123"
        assert quarantined.target_id == "tgt_456"
        assert quarantined.source_type == "pasal"
        assert quarantined.target_type == "kementerian"
        assert quarantined.relation_type == "ISSUED_BY"
        assert quarantined.evidence == "some evidence text"
        assert quarantined.confidence == 0.75
        assert "not allowed" in quarantined.reason or "Unknown" in quarantined.reason

    def test_summary_output(self) -> None:
        """Summary dict should have correct keys and values."""
        result = ValidationResult(valid_count=10, invalid_count=3)
        summary = result.summary()
        assert summary["valid"] == 10
        assert summary["invalid"] == 3
        assert summary["total"] == 13
        assert summary["quarantined_count"] == 0

    def test_all_valid_batch(self) -> None:
        """Batch with all valid edges."""
        validator = SchemaValidator()
        validator.check("e1", "e2", "pt_pma", "nib", "REQUIRES")
        validator.check("e3", "e4", "kitas", "biaya", "HAS_FEE")
        validator.check("e5", "e6", "ayat", "pasal", "PART_OF")

        assert validator.result.valid_count == 3
        assert validator.result.invalid_count == 0
        assert len(validator.result.quarantined) == 0

    def test_all_invalid_batch(self) -> None:
        """Batch with all invalid edges."""
        validator = SchemaValidator()
        validator.check("e1", "e2", "pasal", "kementerian", "ISSUED_BY")
        validator.check("e3", "e4", "biaya", "pasal", "REQUIRES")

        assert validator.result.valid_count == 0
        assert validator.result.invalid_count == 2
        assert len(validator.result.quarantined) == 2
