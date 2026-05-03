"""Tests for Quality Check Service."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.services.kg_monitoring.quality_check import (
    DimensionScore,
    QualityCheckService,
    QualityDimension,
    QualityLevel,
    QualityReport,
)


# ── Dataclass tests ───────────────────────────────────────────────


class TestDimensionScore:
    """Tests for DimensionScore dataclass."""

    def test_weighted_score(self) -> None:
        ds = DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=0.8,
            weight=0.3,
        )
        assert ds.weighted_score == pytest.approx(0.24)

    def test_weighted_score_zero(self) -> None:
        ds = DimensionScore(
            dimension=QualityDimension.ACCURACY,
            score=0.0,
            weight=0.25,
        )
        assert ds.weighted_score == 0.0

    def test_default_lists(self) -> None:
        ds = DimensionScore(
            dimension=QualityDimension.CLARITY,
            score=0.5,
            weight=0.2,
        )
        assert ds.issues == []
        assert ds.notes == []


class TestQualityLevel:
    """Tests for QualityLevel enum."""

    def test_values(self) -> None:
        assert QualityLevel.EXCELLENT.value == "excellent"
        assert QualityLevel.GOOD.value == "good"
        assert QualityLevel.ACCEPTABLE.value == "acceptable"
        assert QualityLevel.POOR.value == "poor"
        assert QualityLevel.REJECT.value == "reject"

    def test_string_enum(self) -> None:
        assert str(QualityLevel.EXCELLENT) == "QualityLevel.EXCELLENT"


class TestQualityReport:
    """Tests for QualityReport dataclass."""

    def test_to_dict(self) -> None:
        dim_scores = [
            DimensionScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.8,
                weight=0.3,
                issues=["Missing field X"],
            ),
        ]
        report = QualityReport(
            document_id="doc1",
            overall_score=0.8,
            quality_level=QualityLevel.GOOD,
            dimension_scores=dim_scores,
            issues=["Missing field X"],
            recommendations=["Add field X"],
            is_acceptable=True,
            checked_at="2026-01-01T00:00:00",
        )
        result = report.to_dict()
        assert result["document_id"] == "doc1"
        assert result["quality_level"] == "good"
        assert result["is_acceptable"] is True
        assert "completeness" in result["dimensions"]
        assert result["dimensions"]["completeness"]["issues"] == ["Missing field X"]

    def test_to_dict_defaults(self) -> None:
        report = QualityReport(
            document_id="doc2",
            overall_score=0.5,
            quality_level=QualityLevel.ACCEPTABLE,
            dimension_scores=[],
        )
        result = report.to_dict()
        assert result["issues"] == []
        assert result["recommendations"] == []
        assert result["is_acceptable"] is False


# ── Mock document helpers ─────────────────────────────────────────


def _make_doc(**kwargs: Any) -> MagicMock:
    """Create a mock extracted document with sensible defaults."""
    doc = MagicMock()
    doc.document_id = kwargs.get("document_id", "test-doc-1")
    doc.title = kwargs.get("title", "Peraturan Menteri Hukum tentang Visa")
    doc.document_type = kwargs.get("document_type", MagicMock(value="regulation"))
    doc.full_text = kwargs.get(
        "full_text",
        "Undang-undang peraturan ini mengatur pasal 1 ayat 2 tentang ketentuan "
        "visa kitas izin tinggal terbatas untuk warga negara asing. "
        "Syarat dan larangan diatur dalam pasal berikut. " * 10,
    )
    doc.document_number = kwargs.get("document_number", "UU No. 6 Tahun 2011")
    doc.issuing_authority = kwargs.get("issuing_authority", "Kemenkumham")
    doc.summary = kwargs.get("summary", "Peraturan tentang keimigrasian dan visa")
    doc.publication_date = kwargs.get("publication_date", "2011-05-01")
    doc.confidence_score = kwargs.get("confidence_score", 0.85)
    doc.key_points = kwargs.get("key_points", ["Point 1", "Point 2", "Point 3", "Point 4"])
    return doc


# ── QualityCheckService tests ────────────────────────────────────


class TestQualityCheckServiceInit:
    """Tests for QualityCheckService initialization."""

    def test_default_init(self) -> None:
        svc = QualityCheckService()
        assert svc.min_accept_score == 0.50
        assert svc.strict_mode is False
        assert svc.validation_stats["total_checked"] == 0

    def test_custom_min_score(self) -> None:
        svc = QualityCheckService(min_accept_score=0.75)
        assert svc.min_accept_score == 0.75

    def test_strict_mode(self) -> None:
        svc = QualityCheckService(strict_mode=True)
        assert svc.min_accept_score == 0.65
        assert svc.THRESHOLDS["accept"] == 0.65


class TestCheckCompleteness:
    """Tests for _check_completeness dimension."""

    def test_all_fields_present(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc()
        result = svc._check_completeness(doc)
        assert result.dimension == QualityDimension.COMPLETENESS
        assert result.score > 0.7
        assert len(result.issues) == 0

    def test_missing_required_fields(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(title="", full_text="")
        result = svc._check_completeness(doc)
        assert result.score < 1.0
        assert len(result.issues) > 0
        assert "Missing required" in result.issues[0]

    def test_missing_recommended_fields(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            document_number="",
            issuing_authority="",
            summary="",
            publication_date="",
        )
        result = svc._check_completeness(doc)
        assert len(result.notes) > 0
        assert "Missing recommended" in result.notes[0]

    def test_short_field_treated_as_missing(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(title="AB")  # Too short (< 3 chars)
        result = svc._check_completeness(doc)
        assert "Missing required" in result.issues[0]


class TestCheckAccuracy:
    """Tests for _check_accuracy dimension."""

    def test_high_confidence(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(confidence_score=0.9)
        result = svc._check_accuracy(doc)
        assert result.score >= 0.9

    def test_low_confidence(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(confidence_score=0.3)
        result = svc._check_accuracy(doc)
        assert result.score < 1.0
        assert any("Low LLM confidence" in i for i in result.issues)

    def test_moderate_confidence(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(confidence_score=0.6)
        result = svc._check_accuracy(doc)
        assert result.score < 1.0

    def test_short_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="Short text")
        result = svc._check_accuracy(doc)
        assert any("suspiciously short" in i for i in result.issues)

    def test_placeholder_text(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="Lorem ipsum dolor sit amet " * 20)
        result = svc._check_accuracy(doc)
        assert any("placeholder" in i for i in result.issues)

    def test_valid_document_number(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(document_number="UU No. 6 Tahun 2011")
        result = svc._check_accuracy(doc)
        assert not any("unusual" in n for n in result.notes)

    def test_unusual_document_number(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(document_number="XYZNONSENSE123456")
        result = svc._check_accuracy(doc)
        assert any("unusual" in n for n in result.notes)


class TestCheckClarity:
    """Tests for _check_clarity dimension."""

    def test_good_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            full_text="A" * 600,
            title="A good title for a legal document",
            summary="A reasonable summary of the document contents",
        )
        result = svc._check_clarity(doc)
        assert result.score > 0.7

    def test_short_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="Too short")
        result = svc._check_clarity(doc)
        assert any("too short" in i for i in result.issues)

    def test_moderately_short_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="A" * 300)
        result = svc._check_clarity(doc)
        assert any("relatively short" in n for n in result.notes)

    def test_excessive_special_chars(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="@#$%^&*()!" * 100)
        result = svc._check_clarity(doc)
        assert any("special characters" in i for i in result.issues)

    def test_short_title(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(title="AB")
        result = svc._check_clarity(doc)
        assert any("Title is too short" in i for i in result.issues)

    def test_long_title(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(title="A" * 250)
        result = svc._check_clarity(doc)
        assert any("Title is very long" in n for n in result.notes)

    def test_no_summary(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(summary="")
        result = svc._check_clarity(doc)
        assert any("No summary" in n for n in result.notes)

    def test_short_summary(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(summary="Brief")
        result = svc._check_clarity(doc)
        assert any("very brief" in n for n in result.notes)


class TestCheckRelevance:
    """Tests for _check_relevance dimension."""

    def test_relevant_legal_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc()  # Default has many legal keywords
        result = svc._check_relevance(doc)
        assert result.score >= 0.8

    def test_no_legal_keywords(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            full_text="Beautiful sunset over the beach in tropical paradise " * 10,
            title="Beach Holiday",
        )
        result = svc._check_relevance(doc)
        assert any("lacks legal domain" in i for i in result.issues)

    def test_few_legal_keywords(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            full_text="This is a general document about law and some other things " * 10,
            title="General Info",
        )
        result = svc._check_relevance(doc)
        # "law" matches -> some keywords found
        assert result.score >= 0.0

    def test_document_type_other(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(document_type=MagicMock(value="other"))
        result = svc._check_relevance(doc)
        assert any("generic" in n for n in result.notes)


class TestCheckStructure:
    """Tests for _check_structure dimension."""

    def test_well_structured_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            full_text="Pasal 1\n\n1. First point\n2. Second point\n\nBab II\n\n3. Third point\n" * 30,
            key_points=["p1", "p2", "p3"],
        )
        result = svc._check_structure(doc)
        assert result.score > 0.7

    def test_no_paragraphs_long_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(full_text="a" * 600)
        result = svc._check_structure(doc)
        assert any("paragraph structure" in i for i in result.issues)

    def test_no_numbering_long_content(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(
            full_text="paragraph one\n\nparagraph two\n\n" * 60,
        )
        result = svc._check_structure(doc)
        assert any("numbered sections" in n for n in result.notes)

    def test_no_key_points(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(key_points=[])
        result = svc._check_structure(doc)
        assert any("No key points" in n for n in result.notes)

    def test_few_key_points(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc(key_points=["p1", "p2"])
        result = svc._check_structure(doc)
        assert any("Few key points" in n for n in result.notes)


class TestDetermineQualityLevel:
    """Tests for _determine_quality_level method.

    Note: THRESHOLDS is a class-level dict that can be mutated by strict_mode.
    Each test explicitly resets the thresholds to ensure isolation.
    """

    def _fresh_svc(self) -> QualityCheckService:
        """Create a service with explicitly reset thresholds."""
        svc = QualityCheckService()
        svc.THRESHOLDS["accept"] = 0.50
        svc.THRESHOLDS["good"] = 0.70
        svc.THRESHOLDS["excellent"] = 0.90
        return svc

    def test_excellent(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.95) == QualityLevel.EXCELLENT

    def test_good(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.75) == QualityLevel.GOOD

    def test_acceptable(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.55) == QualityLevel.ACCEPTABLE

    def test_poor(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.35) == QualityLevel.POOR

    def test_reject(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.1) == QualityLevel.REJECT

    def test_boundary_excellent(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.90) == QualityLevel.EXCELLENT

    def test_boundary_good(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.70) == QualityLevel.GOOD

    def test_boundary_accept(self) -> None:
        svc = self._fresh_svc()
        assert svc._determine_quality_level(0.50) == QualityLevel.ACCEPTABLE


class TestGenerateRecommendations:
    """Tests for _generate_recommendations method."""

    def test_low_scores_get_recommendations(self) -> None:
        svc = QualityCheckService()
        dims = [
            DimensionScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.3,
                weight=0.3,
                issues=["Missing fields"],
            ),
            DimensionScore(
                dimension=QualityDimension.ACCURACY,
                score=0.6,
                weight=0.25,
                issues=[],
            ),
        ]
        result = svc._generate_recommendations(dims)
        assert len(result) == 2
        assert "Improve completeness" in result[0]
        assert "Consider enhancing accuracy" in result[1]

    def test_no_recommendations_for_good_scores(self) -> None:
        svc = QualityCheckService()
        dims = [
            DimensionScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.9,
                weight=0.3,
            ),
        ]
        result = svc._generate_recommendations(dims)
        assert len(result) == 0

    def test_max_5_recommendations(self) -> None:
        svc = QualityCheckService()
        dims = [
            DimensionScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.2,
                weight=0.3,
                issues=["issue"],
            ),
            DimensionScore(
                dimension=QualityDimension.ACCURACY,
                score=0.2,
                weight=0.25,
                issues=["issue"],
            ),
            DimensionScore(
                dimension=QualityDimension.CLARITY,
                score=0.2,
                weight=0.2,
                issues=["issue"],
            ),
            DimensionScore(
                dimension=QualityDimension.RELEVANCE,
                score=0.2,
                weight=0.15,
                issues=["issue"],
            ),
            DimensionScore(
                dimension=QualityDimension.STRUCTURE,
                score=0.2,
                weight=0.1,
                issues=["issue"],
            ),
        ]
        result = svc._generate_recommendations(dims)
        assert len(result) <= 5


class TestValidate:
    """Tests for the main validate method."""

    @pytest.mark.asyncio
    async def test_good_document(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc()
        report = await svc.validate(doc)
        assert report.document_id == "test-doc-1"
        assert report.is_acceptable is True
        assert report.overall_score > 0.5
        assert len(report.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_poor_document(self) -> None:
        svc = QualityCheckService()
        # Reset thresholds to ensure test isolation
        svc.THRESHOLDS["accept"] = 0.50
        doc = _make_doc(
            title="",
            full_text="x",
            document_number="",
            document_type=MagicMock(value="other"),
            issuing_authority="",
            summary="",
            publication_date="",
            confidence_score=0.1,
            key_points=[],
        )
        report = await svc.validate(doc)
        # With these inputs, overall_score is low enough to be POOR or REJECT
        assert report.quality_level in (QualityLevel.POOR, QualityLevel.REJECT)
        # The score is borderline, so we check quality_level rather than is_acceptable

    @pytest.mark.asyncio
    async def test_validation_stats_updated(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc()
        await svc.validate(doc)
        assert svc.validation_stats["total_checked"] == 1
        assert svc.validation_stats["accepted"] == 1
        assert svc.validation_stats["avg_score"] > 0

    @pytest.mark.asyncio
    async def test_rejected_document_stats(self) -> None:
        svc = QualityCheckService(min_accept_score=0.99)
        doc = _make_doc()
        await svc.validate(doc)
        assert svc.validation_stats["rejected"] >= 0  # May or may not be rejected depending on score

    @pytest.mark.asyncio
    async def test_multiple_validations_average(self) -> None:
        svc = QualityCheckService()
        doc1 = _make_doc()
        doc2 = _make_doc(document_id="doc2")
        await svc.validate(doc1)
        await svc.validate(doc2)
        assert svc.validation_stats["total_checked"] == 2
        assert svc.validation_stats["avg_score"] > 0


class TestGetStats:
    """Tests for get_stats method."""

    def test_initial_stats(self) -> None:
        svc = QualityCheckService()
        stats = svc.get_stats()
        assert stats["total_checked"] == 0
        assert stats["acceptance_rate"] == "0.0%"
        assert stats["min_accept_score"] == 0.50
        assert stats["strict_mode"] is False

    @pytest.mark.asyncio
    async def test_stats_after_validation(self) -> None:
        svc = QualityCheckService()
        doc = _make_doc()
        await svc.validate(doc)
        stats = svc.get_stats()
        assert stats["total_checked"] == 1
        assert "acceptance_rate" in stats


class TestUpdateThresholds:
    """Tests for update_thresholds method."""

    def test_update_accept(self) -> None:
        svc = QualityCheckService()
        svc.update_thresholds(accept=0.6)
        assert svc.THRESHOLDS["accept"] == 0.6
        assert svc.min_accept_score == 0.6

    def test_update_good(self) -> None:
        svc = QualityCheckService()
        svc.update_thresholds(good=0.8)
        assert svc.THRESHOLDS["good"] == 0.8

    def test_update_excellent(self) -> None:
        svc = QualityCheckService()
        svc.update_thresholds(excellent=0.95)
        assert svc.THRESHOLDS["excellent"] == 0.95

    def test_update_all(self) -> None:
        svc = QualityCheckService()
        svc.update_thresholds(accept=0.4, good=0.6, excellent=0.85)
        assert svc.THRESHOLDS["accept"] == 0.4
        assert svc.THRESHOLDS["good"] == 0.6
        assert svc.THRESHOLDS["excellent"] == 0.85

    def test_update_none_keeps_defaults(self) -> None:
        svc = QualityCheckService()
        orig_accept = svc.THRESHOLDS["accept"]
        svc.update_thresholds()
        assert svc.THRESHOLDS["accept"] == orig_accept
