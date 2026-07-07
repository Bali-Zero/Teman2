from backend.services.intel.intel_classification_service import IntelClassificationService


def test_classify_intel_type_uses_direct_visa_category() -> None:
    service = IntelClassificationService()
    category = next(iter(service.visa_categories))

    result = service.classify_intel_type(
        category=category,
        title="General update",
        content="No explicit keyword needed when category maps directly",
    )

    assert result == "visa"


def test_classify_intel_type_promotes_keyword_matches_to_visa() -> None:
    service = IntelClassificationService()
    keywords = service.visa_keywords[: service.min_visa_keywords]

    result = service.classify_intel_type(
        category="general",
        title=" ".join(keywords),
        content="Government immigration update",
    )

    assert result == "visa"


def test_classify_intel_type_defaults_to_news() -> None:
    service = IntelClassificationService()

    result = service.classify_intel_type(
        category="economy",
        title="Regional business confidence improves",
        content="Tourism and retail indicators increased this quarter.",
    )

    assert result == "news"
