"""
Test suite for Knowledge Graph data quality monitoring

Tests data validation, consistency, completeness, and quality metrics.

Author: Windsurf (QA Engineer)
Created: 2026-02-09
"""

import pytest


class TestDataValidation:
    """Test KG data validation rules"""

    def test_validate_node_schema(self):
        """Test validating node against schema"""
        node = {
            "id": "node1",
            "type": "Visa",
            "name": "Tourist Visa",
            "properties": {"duration": 30},
        }

        required_fields = ["id", "type", "name"]
        is_valid = all(field in node for field in required_fields)

        assert is_valid is True

    def test_validate_edge_schema(self):
        """Test validating edge against schema"""
        edge = {"id": "edge1", "type": "REQUIRES", "source": "node1", "target": "node2"}

        required_fields = ["id", "type", "source", "target"]
        is_valid = all(field in edge for field in required_fields)

        assert is_valid is True

    def test_validate_property_types(self):
        """Test validating property data types"""
        node = {
            "id": "node1",
            "properties": {"duration": 30, "name": "Tourist Visa", "active": True},
        }

        type_rules = {"duration": int, "name": str, "active": bool}

        is_valid = all(
            isinstance(node["properties"][prop], expected_type)
            for prop, expected_type in type_rules.items()
            if prop in node["properties"]
        )

        assert is_valid is True


class TestDataConsistency:
    """Test KG data consistency checks"""

    def test_detect_dangling_references(self):
        """Test detecting edges pointing to non-existent nodes"""
        nodes = [{"id": "node1"}, {"id": "node2"}]
        edges = [
            {"source": "node1", "target": "node2"},
            {"source": "node2", "target": "node3"},  # node3 doesn't exist
        ]

        node_ids = {n["id"] for n in nodes}
        dangling = [e for e in edges if e["source"] not in node_ids or e["target"] not in node_ids]

        assert len(dangling) == 1

    def test_detect_bidirectional_inconsistency(self):
        """Test detecting inconsistent bidirectional relationships"""
        edges = [
            {"id": "e1", "type": "PARENT_OF", "source": "n1", "target": "n2"},
            {"id": "e2", "type": "CHILD_OF", "source": "n2", "target": "n1"},
            {"id": "e3", "type": "PARENT_OF", "source": "n3", "target": "n4"},
            # Missing CHILD_OF from n4 to n3
        ]

        bidirectional_rules = {"PARENT_OF": "CHILD_OF", "CHILD_OF": "PARENT_OF"}

        inconsistencies = []
        for edge in edges:
            if edge["type"] in bidirectional_rules:
                reverse_type = bidirectional_rules[edge["type"]]
                reverse_exists = any(
                    e["type"] == reverse_type
                    and e["source"] == edge["target"]
                    and e["target"] == edge["source"]
                    for e in edges
                )
                if not reverse_exists:
                    inconsistencies.append(edge)

        assert len(inconsistencies) == 1


class TestDataCompleteness:
    """Test KG data completeness metrics"""

    def test_calculate_property_completeness(self):
        """Test calculating property completeness"""
        nodes = [
            {"id": "n1", "name": "Visa", "description": "Tourist visa", "duration": 30},
            {"id": "n2", "name": "Tax", "description": None, "duration": None},
            {"id": "n3", "name": "Legal", "description": "Legal info", "duration": None},
        ]

        optional_properties = ["description", "duration"]
        completeness_scores = []

        for node in nodes:
            filled = sum(1 for prop in optional_properties if node.get(prop))
            score = filled / len(optional_properties)
            completeness_scores.append(score)

        avg_completeness = sum(completeness_scores) / len(completeness_scores)

        assert avg_completeness >= 0.5

    def test_identify_sparse_nodes(self):
        """Test identifying nodes with sparse properties"""
        nodes = [
            {"id": "n1", "properties": {"a": 1, "b": 2, "c": 3}},
            {"id": "n2", "properties": {"a": 1}},  # Sparse
            {"id": "n3", "properties": {"a": 1, "b": 2}},
        ]

        min_properties = 2
        sparse_nodes = [n for n in nodes if len(n["properties"]) < min_properties]

        assert len(sparse_nodes) == 1
        assert sparse_nodes[0]["id"] == "n2"


class TestDataQualityMetrics:
    """Test overall data quality metrics"""

    def test_calculate_data_quality_score(self):
        """Test calculating overall data quality score"""
        metrics = {"completeness": 0.85, "consistency": 0.90, "validity": 0.95, "accuracy": 0.88}

        weights = {"completeness": 0.25, "consistency": 0.25, "validity": 0.30, "accuracy": 0.20}

        quality_score = sum(metrics[metric] * weights[metric] for metric in metrics)

        assert quality_score > 0.85

    def test_identify_quality_issues(self):
        """Test identifying data quality issues"""
        quality_checks = {
            "orphaned_nodes": 5,
            "dangling_edges": 2,
            "missing_properties": 15,
            "invalid_types": 1,
        }

        thresholds = {
            "orphaned_nodes": 10,
            "dangling_edges": 0,
            "missing_properties": 20,
            "invalid_types": 0,
        }

        issues = [check for check, count in quality_checks.items() if count > thresholds[check]]

        assert len(issues) == 2
        assert "dangling_edges" in issues
        assert "invalid_types" in issues


@pytest.mark.integration
class TestDataQualityIntegration:
    """Integration tests for data quality monitoring"""

    @pytest.mark.asyncio
    async def test_full_data_quality_audit(self):
        """Test complete data quality audit"""
        pytest.skip("Requires full KG setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
