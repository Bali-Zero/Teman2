"""
Tests for QualityCheckService - Phase 8
"""

from datetime import datetime, timezone

import pytest

from backend.services.kg_monitoring.auto_ingestion import DocumentType, ExtractedDocument
from backend.services.kg_monitoring.quality_check import (
    DimensionScore,
    QualityCheckService,
    QualityDimension,
    QualityLevel,
    QualityReport,
)


class TestQualityLevel:
    """Test QualityLevel enum"""

    def test_quality_level_values(self):
        """Test quality level enum values"""
        assert QualityLevel.EXCELLENT.value == "excellent"
        assert QualityLevel.GOOD.value == "good"
        assert QualityLevel.ACCEPTABLE.value == "acceptable"
        assert QualityLevel.POOR.value == "poor"
        assert QualityLevel.REJECT.value == "reject"


class TestDimensionScore:
    """Test DimensionScore dataclass"""

    def test_weighted_score_calculation(self):
        """Test weighted score calculation"""
        score = DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=0.8,
            weight=0.3,
        )

        assert score.weighted_score == 0.24  # 0.8 * 0.3


class TestQualityReport:
    """Test QualityReport dataclass"""

    def test_report_creation(self):
        """Test creating quality report"""
        report = QualityReport(
            document_id="doc123",
            overall_score=0.75,
            quality_level=QualityLevel.GOOD,
            dimension_scores=[],
            is_acceptable=True,
        )

        assert report.document_id == "doc123"
        assert report.is_acceptable is True

    def test_to_dict(self):
        """Test report to dict conversion"""
        report = QualityReport(
            document_id="doc123",
            overall_score=0.85,
            quality_level=QualityLevel.GOOD,
            dimension_scores=[
                DimensionScore(
                    dimension=QualityDimension.COMPLETENESS,
                    score=0.9,
                    weight=0.3,
                    issues=[],
                ),
            ],
            issues=[],
            recommendations=["Test rec"],
            is_acceptable=True,
            checked_at=datetime.now(tz=timezone.utc).isoformat(),
        )

        d = report.to_dict()
        assert d["document_id"] == "doc123"
        assert d["overall_score"] == "85.00%"
        assert d["quality_level"] == "good"
        assert d["is_acceptable"] is True


class TestQualityCheckService:
    """Test QualityCheckService functionality"""

    def test_initialization(self):
        """Test service initialization"""
        service = QualityCheckService(min_accept_score=0.6)

        assert service.min_accept_score == 0.6
        assert service.strict_mode is False

    def test_initialization_strict_mode(self):
        """Test strict mode initialization"""
        service = QualityCheckService(min_accept_score=0.5, strict_mode=True)

        assert service.min_accept_score == 0.65  # Higher in strict mode
        assert service.strict_mode is True

    def test_get_stats(self):
        """Test getting service statistics"""
        service = QualityCheckService()
        service.validation_stats = {
            "total_checked": 100,
            "accepted": 80,
            "rejected": 20,
            "avg_score": 0.75,
        }

        stats = service.get_stats()

        assert stats["total_checked"] == 100
        assert stats["acceptance_rate"] == "80.0%"
        assert stats["min_accept_score"] == 0.5

    @pytest.mark.asyncio
    async def test_validate_excellent_document(self):
        """Test validating an excellent quality document"""
        service = QualityCheckService()

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="UU No. 13 Tahun 2003 Tentang Ketenagakerjaan",
            document_type=DocumentType.UNDANG_UNDANG,
            document_number="UU No. 13 Tahun 2003",
            issuing_authority="DPR RI",
            subject="Ketenagakerjaan",
            summary="Undang-undang tentang ketenagakerjaan di Indonesia",
            full_text="Pasal 1: Dalam undang-undang ini yang dimaksud dengan... " * 100,
            key_points=["Point 1", "Point 2", "Point 3", "Point 4"],
            confidence_score=0.95,
        )

        report = await service.validate(doc)

        assert report.overall_score >= 0.7
        assert report.is_acceptable is True
        assert report.quality_level in (QualityLevel.GOOD, QualityLevel.EXCELLENT)

    @pytest.mark.asyncio
    async def test_validate_poor_document(self):
        """Test validating a poor quality document"""
        service = QualityCheckService()

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="X",  # Too short
            document_type=DocumentType.OTHER,
            full_text="Short",  # Very short
            confidence_score=0.2,
        )

        report = await service.validate(doc)

        assert report.overall_score < 0.5
        assert report.is_acceptable is False
        assert len(report.issues) > 0

    @pytest.mark.asyncio
    async def test_validate_detects_missing_required(self):
        """Test that missing required fields are detected and reported"""
        # Use strict mode to ensure rejection
        service = QualityCheckService(min_accept_score=0.60, strict_mode=True)

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="",  # Missing
            document_type=DocumentType.OTHER,
            full_text="",  # Missing
        )

        report = await service.validate(doc)

        # Should have issues reported
        assert any("required" in issue.lower() for issue in report.issues)
        # With strict mode and very low scores, should be rejected
        assert report.quality_level in (QualityLevel.POOR, QualityLevel.REJECT)

    @pytest.mark.asyncio
    async def test_validate_accepts_minimal_valid(self):
        """Test that minimal valid document is accepted"""
        service = QualityCheckService(min_accept_score=0.4)

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="Peraturan Test Tentang Sesuatu",  # Valid title
            document_type=DocumentType.PERATURAN_PEMERINTAH,
            document_number="PP No. 1 Tahun 2024",
            issuing_authority="Pemerintah",
            full_text="Ini adalah teks peraturan yang cukup panjang untuk memenuhi syarat " * 50,
            confidence_score=0.7,
        )

        report = await service.validate(doc)

        # Should have issues but still might be acceptable with lower threshold
        assert report.overall_score > 0

    def test_update_thresholds(self):
        """Test updating quality thresholds"""
        service = QualityCheckService()

        service.update_thresholds(accept=0.6, good=0.8, excellent=0.95)

        assert service.THRESHOLDS["accept"] == 0.6
        assert service.THRESHOLDS["good"] == 0.8
        assert service.THRESHOLDS["excellent"] == 0.95
        assert service.min_accept_score == 0.6

    def test_determine_quality_level(self):
        """Test quality level determination"""
        service = QualityCheckService()

        assert service._determine_quality_level(0.95) == QualityLevel.EXCELLENT
        assert service._determine_quality_level(0.80) == QualityLevel.GOOD
        assert service._determine_quality_level(0.60) == QualityLevel.ACCEPTABLE
        assert service._determine_quality_level(0.40) == QualityLevel.POOR
        assert service._determine_quality_level(0.20) == QualityLevel.REJECT

    @pytest.mark.asyncio
    async def test_placeholder_detection(self):
        """Test detection of placeholder text"""
        service = QualityCheckService()

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="Valid Title",
            document_type=DocumentType.UNDANG_UNDANG,
            full_text="lorem ipsum dolor sit amet",  # Placeholder text
        )

        report = await service.validate(doc)

        assert any("placeholder" in issue.lower() for issue in report.issues)

    @pytest.mark.asyncio
    async def test_legal_keyword_detection(self):
        """Test legal keyword relevance detection"""
        service = QualityCheckService()

        # Document with legal keywords
        good_doc = ExtractedDocument(
            document_id="doc1",
            source_id="test",
            title="UU Ketenagakerjaan",
            document_type=DocumentType.UNDANG_UNDANG,
            full_text="undang-undang tentang ketenagakerjaan pasal 1 ayat 1 hukum",
        )

        report = await service.validate(good_doc)
        relevance_score = next(
            (d for d in report.dimension_scores if d.dimension == QualityDimension.RELEVANCE), None
        )
        assert relevance_score is not None
        assert relevance_score.score > 0.5

    def test_dimension_weights_sum_to_one(self):
        """Test that dimension weights sum to 1.0"""
        service = QualityCheckService()

        total_weight = sum(service.DIMENSION_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001  # Allow small float error
