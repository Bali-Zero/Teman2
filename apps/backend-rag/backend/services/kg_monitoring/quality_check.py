"""
Quality Check Service - Phase 8

Validates extracted documents for quality and completeness before ingestion.
Provides quality metrics and automated rejection of low-quality content.

Features:
- Multi-dimensional quality scoring
- Content validation rules
- Automated rejection criteria
- Quality report generation
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    """Quality assessment levels"""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 70-89%
    ACCEPTABLE = "acceptable"  # 50-69%
    POOR = "poor"  # 30-49%
    REJECT = "reject"  # 0-29%


class QualityDimension(str, Enum):
    """Dimensions of quality assessment"""

    COMPLETENESS = "completeness"  # Required fields present
    ACCURACY = "accuracy"  # Data appears accurate
    CLARITY = "clarity"  # Content is clear and readable
    RELEVANCE = "relevance"  # Content is relevant to legal domain
    STRUCTURE = "structure"  # Proper formatting and structure


@dataclass
class DimensionScore:
    """Score for a single quality dimension"""

    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    weight: float  # Importance weight
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        """Weighted score."""
        return self.score * self.weight


@dataclass
class QualityReport:
    """Complete quality assessment report"""

    document_id: str
    overall_score: float  # 0.0 to 1.0
    quality_level: QualityLevel
    dimension_scores: list[DimensionScore]
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    is_acceptable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "document_id": self.document_id,
            "overall_score": f"{self.overall_score:.2%}",
            "quality_level": self.quality_level.value,
            "dimensions": {
                d.dimension.value: {
                    "score": f"{d.score:.2%}",
                    "weight": d.weight,
                    "issues": d.issues,
                }
                for d in self.dimension_scores
            },
            "issues": self.issues,
            "recommendations": self.recommendations,
            "is_acceptable": self.is_acceptable,
            "checked_at": self.checked_at,
        }


class QualityCheckService:
    """
    Service for validating document quality before ingestion.

    Performs multi-dimensional quality checks and generates reports.
    """

    # Quality thresholds
    THRESHOLDS = {
        "accept": 0.50,  # Minimum score to accept
        "good": 0.70,  # Good quality threshold
        "excellent": 0.90,  # Excellent quality threshold
    }

    # Dimension weights (must sum to 1.0)
    DIMENSION_WEIGHTS = {
        QualityDimension.COMPLETENESS: 0.30,
        QualityDimension.ACCURACY: 0.25,
        QualityDimension.CLARITY: 0.20,
        QualityDimension.RELEVANCE: 0.15,
        QualityDimension.STRUCTURE: 0.10,
    }

    # Required fields for legal documents
    REQUIRED_FIELDS = [
        "title",
        "document_type",
        "full_text",
    ]

    # Optional but recommended fields
    RECOMMENDED_FIELDS = [
        "document_number",
        "issuing_authority",
        "summary",
        "publication_date",
    ]

    def __init__(
        self,
        min_accept_score: float = 0.50,
        strict_mode: bool = False,
    ) -> None:
        """
        Initialize quality check service.

        Args:
            min_accept_score: Minimum score to accept document (0.0-1.0)
            strict_mode: If True, apply stricter quality standards
        """
        self.min_accept_score = min_accept_score
        self.strict_mode = strict_mode

        if strict_mode:
            self.min_accept_score = 0.65
            self.THRESHOLDS["accept"] = 0.65

        self.validation_stats = {
            "total_checked": 0,
            "accepted": 0,
            "rejected": 0,
            "avg_score": 0.0,
            "last_run": None,
        }

        logger.info("✅ QualityCheckService initialized")
        logger.info(f"   Min accept score: {min_accept_score:.0%}")
        logger.info(f"   Strict mode: {strict_mode}")

    async def validate(self, extracted_doc) -> QualityReport:
        """
        Validate an extracted document.

        Args:
            extracted_doc: ExtractedDocument to validate

        Returns:
            QualityReport with scores and assessment
        """
        from datetime import datetime

        document_id = extracted_doc.document_id
        dimension_scores = []
        all_issues = []
        recommendations = []

        # Check each dimension
        completeness = self._check_completeness(extracted_doc)
        dimension_scores.append(completeness)
        all_issues.extend(completeness.issues)

        accuracy = self._check_accuracy(extracted_doc)
        dimension_scores.append(accuracy)
        all_issues.extend(accuracy.issues)

        clarity = self._check_clarity(extracted_doc)
        dimension_scores.append(clarity)
        all_issues.extend(clarity.issues)

        relevance = self._check_relevance(extracted_doc)
        dimension_scores.append(relevance)
        all_issues.extend(relevance.issues)

        structure = self._check_structure(extracted_doc)
        dimension_scores.append(structure)
        all_issues.extend(structure.issues)

        # Calculate overall score
        total_weighted = sum(d.weighted_score for d in dimension_scores)
        overall_score = total_weighted  # Weights sum to 1.0

        # Determine quality level
        quality_level = self._determine_quality_level(overall_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(dimension_scores)

        # Determine if acceptable
        is_acceptable = overall_score >= self.min_accept_score

        # Update stats
        self.validation_stats["total_checked"] += 1
        if is_acceptable:
            self.validation_stats["accepted"] += 1
        else:
            self.validation_stats["rejected"] += 1

        # Update average score
        n = self.validation_stats["total_checked"]
        current_avg = self.validation_stats["avg_score"]
        self.validation_stats["avg_score"] = (current_avg * (n - 1) + overall_score) / n
        self.validation_stats["last_run"] = datetime.now().isoformat()

        return QualityReport(
            document_id=document_id,
            overall_score=overall_score,
            quality_level=quality_level,
            dimension_scores=dimension_scores,
            issues=all_issues,
            recommendations=recommendations,
            is_acceptable=is_acceptable,
            checked_at=datetime.now().isoformat(),
        )

    def _check_completeness(self, doc) -> DimensionScore:
        """Check if document has all required fields"""
        issues = []
        notes = []

        # Check required fields
        missing_required = []
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(doc, field_name, None)
            if not value or (isinstance(value, str) and len(value.strip()) < 3):
                missing_required.append(field_name)

        if missing_required:
            issues.append(f"Missing required fields: {', '.join(missing_required)}")

        # Check recommended fields
        missing_recommended = []
        for field_name in self.RECOMMENDED_FIELDS:
            value = getattr(doc, field_name, None)
            if not value or (isinstance(value, str) and len(value.strip()) < 2):
                missing_recommended.append(field_name)

        if missing_recommended:
            notes.append(f"Missing recommended fields: {', '.join(missing_recommended)}")

        # Calculate score
        required_score = 1.0 - (len(missing_required) / len(self.REQUIRED_FIELDS))
        recommended_score = 1.0 - (len(missing_recommended) / len(self.RECOMMENDED_FIELDS))

        # Weight: required 70%, recommended 30%
        score = (required_score * 0.7) + (recommended_score * 0.3)

        return DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=max(0.0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.COMPLETENESS],
            issues=issues,
            notes=notes,
        )

    def _check_accuracy(self, doc) -> DimensionScore:
        """Check if document data appears accurate"""
        issues = []
        notes = []
        score = 1.0

        # Check confidence score from LLM
        if hasattr(doc, "confidence_score") and doc.confidence_score:
            if doc.confidence_score < 0.5:
                issues.append(f"Low LLM confidence: {doc.confidence_score:.2%}")
                score -= 0.3
            elif doc.confidence_score < 0.7:
                notes.append(f"Moderate LLM confidence: {doc.confidence_score:.2%}")
                score -= 0.1
            else:
                notes.append(f"High LLM confidence: {doc.confidence_score:.2%}")

        # Check for suspicious patterns
        if hasattr(doc, "full_text") and doc.full_text:
            # Check for very short content
            if len(doc.full_text) < 100:
                issues.append("Document content is suspiciously short")
                score -= 0.3

            # Check for placeholder text
            placeholder_patterns = ["lorem ipsum", "placeholder", "[insert", "todo:", "xxx"]
            text_lower = doc.full_text.lower()
            for pattern in placeholder_patterns:
                if pattern in text_lower:
                    issues.append(f"Contains placeholder text: '{pattern}'")
                    score -= 0.4
                    break

        # Check document number format (if present)
        if hasattr(doc, "document_number") and doc.document_number:
            doc_num = doc.document_number.lower()
            # Check for common Indonesian document patterns
            valid_prefixes = ["uu", "pp", "perpres", "perm", "kep", "se"]
            has_valid_prefix = any(doc_num.startswith(p) for p in valid_prefixes)
            if not has_valid_prefix and len(doc.document_number) > 5:
                notes.append("Document number format may be unusual")
                score -= 0.1

        return DimensionScore(
            dimension=QualityDimension.ACCURACY,
            score=max(0.0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.ACCURACY],
            issues=issues,
            notes=notes,
        )

    def _check_clarity(self, doc) -> DimensionScore:
        """Check if content is clear and readable"""
        issues = []
        notes = []
        score = 1.0

        content = getattr(doc, "full_text", "") or ""

        # Check content length
        if len(content) < 200:
            issues.append("Content is too short for meaningful analysis")
            score -= 0.4
        elif len(content) < 500:
            notes.append("Content is relatively short")
            score -= 0.1

        # Check for excessive special characters
        special_chars = sum(1 for c in content if not c.isalnum() and not c.isspace())
        special_ratio = special_chars / max(len(content), 1)
        if special_ratio > 0.3:
            issues.append("Content has excessive special characters (possible encoding issues)")
            score -= 0.3

        # Check title clarity
        title = getattr(doc, "title", "")
        if title:
            if len(title) < 10:
                issues.append("Title is too short")
                score -= 0.2
            elif len(title) > 200:
                notes.append("Title is very long")
                score -= 0.1

        # Check summary clarity (if present)
        summary = getattr(doc, "summary", "")
        if summary:
            if len(summary) < 20:
                notes.append("Summary is very brief")
                score -= 0.05
        else:
            notes.append("No summary provided")
            score -= 0.1

        return DimensionScore(
            dimension=QualityDimension.CLARITY,
            score=max(0.0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.CLARITY],
            issues=issues,
            notes=notes,
        )

    def _check_relevance(self, doc) -> DimensionScore:
        """Check if content is relevant to legal domain"""
        issues = []
        notes = []
        score = 1.0

        content = (getattr(doc, "full_text", "") or "").lower()
        title = (getattr(doc, "title", "") or "").lower()

        # Legal keywords
        legal_keywords = [
            "undang-undang",
            "peraturan",
            "keputusan",
            "pasal",
            "ayat",
            "UU",
            "PP",
            "Perpres",
            "Permen",
            "Kep",
            "SE",
            "hukum",
            "legal",
            "regulation",
            "law",
            "article",
            "section",
            "ketentuan",
            "syarat",
            "wajib",
            "larangan",
            "sanksi",
            "pajak",
            "visa",
            "kitas",
            "izin",
            "nib",
            "kbli",
        ]

        # Check for legal keywords
        keyword_matches = sum(
            1 for kw in legal_keywords if kw.lower() in content or kw.lower() in title
        )
        if keyword_matches < 2:
            issues.append("Content lacks legal domain keywords")
            score -= 0.4
        elif keyword_matches < 5:
            notes.append("Limited legal terminology detected")
            score -= 0.1
        else:
            notes.append(f"Strong legal terminology ({keyword_matches} keywords)")

        # Check document type
        doc_type = getattr(doc, "document_type", None)
        if doc_type and doc_type.value == "other":
            notes.append("Document type is generic ('other')")
            score -= 0.1

        return DimensionScore(
            dimension=QualityDimension.RELEVANCE,
            score=max(0.0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.RELEVANCE],
            issues=issues,
            notes=notes,
        )

    def _check_structure(self, doc) -> DimensionScore:
        """Check if document has proper structure"""
        issues = []
        notes = []
        score = 1.0

        content = getattr(doc, "full_text", "") or ""

        # Check for structural elements
        has_paragraphs = "\n\n" in content or "\n" in content
        has_numbering = any(f"{i}." in content for i in range(1, 10))
        has_headers = any(marker in content.lower() for marker in ["pasal", "bab", "bagian"])

        if not has_paragraphs and len(content) > 500:
            issues.append("Content lacks paragraph structure")
            score -= 0.2

        if not has_numbering and len(content) > 1000:
            notes.append("Content lacks numbered sections")
            score -= 0.1

        if not has_headers:
            notes.append("No clear section headers found")
            score -= 0.1
        else:
            notes.append("Document has section headers")

        # Check key points structure
        key_points = getattr(doc, "key_points", [])
        if not key_points:
            notes.append("No key points extracted")
            score -= 0.1
        elif len(key_points) < 3:
            notes.append("Few key points extracted")
            score -= 0.05

        return DimensionScore(
            dimension=QualityDimension.STRUCTURE,
            score=max(0.0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.STRUCTURE],
            issues=issues,
            notes=notes,
        )

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """Determine quality level from score"""
        if score >= self.THRESHOLDS["excellent"]:
            return QualityLevel.EXCELLENT
        if score >= self.THRESHOLDS["good"]:
            return QualityLevel.GOOD
        if score >= self.THRESHOLDS["accept"]:
            return QualityLevel.ACCEPTABLE
        if score >= 0.30:
            return QualityLevel.POOR
        return QualityLevel.REJECT

    def _generate_recommendations(self, dimension_scores: list[DimensionScore]) -> list[str]:
        """Generate improvement recommendations"""
        recommendations = []

        for dim in dimension_scores:
            if dim.score < 0.5:
                recommendations.append(
                    f"Improve {dim.dimension.value}: {', '.join(dim.issues[:2])}"
                )
            elif dim.score < 0.7:
                recommendations.append(f"Consider enhancing {dim.dimension.value}")

        return recommendations[:5]  # Limit to top 5

    def get_stats(self) -> dict[str, Any]:
        """Get validation statistics"""
        total = self.validation_stats["total_checked"]
        accepted = self.validation_stats["accepted"]
        acceptance_rate = (accepted / total * 100) if total > 0 else 0

        return {
            **self.validation_stats,
            "acceptance_rate": f"{acceptance_rate:.1f}%",
            "min_accept_score": self.min_accept_score,
            "strict_mode": self.strict_mode,
        }

    def update_thresholds(
        self,
        accept: float | None = None,
        good: float | None = None,
        excellent: float | None = None,
    ) -> None:
        """Update quality thresholds"""
        if accept is not None:
            self.THRESHOLDS["accept"] = accept
            self.min_accept_score = accept
        if good is not None:
            self.THRESHOLDS["good"] = good
        if excellent is not None:
            self.THRESHOLDS["excellent"] = excellent

        logger.info(f"Updated quality thresholds: {self.THRESHOLDS}")
