"""
Intel Classification Service

Handles classification of Intel articles into categories (visa/news).
"""

import logging
import time
from typing import Literal

from backend.app.core.constants import IntelConstants
from backend.app.metrics import intel_classification_duration, intel_classification_total

logger = logging.getLogger(__name__)


class IntelClassificationService:
    """
    Service for classifying Intel articles.

    Classifies articles as 'visa' or 'news' based on category and content keywords.
    """

    def __init__(self) -> None:
        """Initialize the classification service."""
        self.visa_categories = IntelConstants.VISA_CATEGORIES
        self.visa_keywords = IntelConstants.VISA_KEYWORDS
        self.min_visa_keywords = IntelConstants.MIN_VISA_KEYWORDS

    def classify_intel_type(
        self, category: str, title: str, content: str
    ) -> Literal["visa", "news"]:
        """
        Classify article as 'visa' or 'news' for routing to correct staging folder.

        Args:
            category: Original category from scraper
            title: Article title
            content: Article content

        Returns:
            "visa" or "news"
        """
        start_time = time.time()

        # Direct category mapping
        if category.lower() in self.visa_categories:
            classification = "visa"
        else:
            # Keyword-based classification
            text_lower = f"{title} {content}".lower()
            visa_mentions = sum(1 for keyword in self.visa_keywords if keyword in text_lower)

            # If minimum visa keywords found, classify as visa
            if visa_mentions >= self.min_visa_keywords:
                classification = "visa"
            else:
                # Default to news
                classification = "news"

        # Track metrics
        duration = time.time() - start_time
        intel_classification_duration.observe(duration)
        intel_classification_total.labels(
            category_input=category, classified_as=classification
        ).inc()

        logger.debug(
            "Article classified",
            extra={
                "category_input": category,
                "classified_as": classification,
                "duration_ms": duration * 1000,
            },
        )

        return classification
