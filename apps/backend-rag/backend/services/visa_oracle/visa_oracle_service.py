"""Visa Oracle Service

Pure-logic visa recommendation engine. No LLM calls.
Scores visa types from PricingService data based on purpose, duration
and family situation. Returns top-3 results with full details.
"""

import hashlib
import logging
import secrets
from typing import Any

from backend.services.pricing.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map user-declared purpose to the pricing categories that are relevant.
# Order within the list represents preference priority.
PURPOSE_CATEGORY_MAP: dict[str, list[str]] = {
    "visit": ["single_entry_visas", "multiple_entry_visas"],
    "work": ["kitas_permits", "single_entry_visas"],
    "invest": ["kitas_permits", "multiple_entry_visas"],
    "retire": ["kitas_permits"],
    "digital_nomad": ["single_entry_visas", "multiple_entry_visas", "kitas_permits"],
    "family": ["kitas_permits"],
    "study": ["single_entry_visas", "kitas_permits"],
}

# Keywords matched against visa names (case-insensitive) per purpose.
PURPOSE_KEYWORDS: dict[str, list[str]] = {
    "visit": ["tourism", "tourist", "c1", "visit", "business"],
    "work": ["working", "work", "employment", "kitas", "imta"],
    "invest": ["investor", "invest", "business", "kitas"],
    "retire": ["retirement", "retire", "pensioner", "pension"],
    "digital_nomad": ["remote", "freelance", "e33g", "digital", "nomad", "c1"],
    "family": ["spouse", "dependent", "family", "child"],
    "study": ["internship", "student", "c22", "study", "education"],
}

# Short / medium / long duration thresholds (days).
DURATION_THRESHOLDS: dict[str, tuple[int, int]] = {
    "short": (0, 60),
    "medium": (61, 180),
    "long": (181, 99999),
}

# Static visa metadata (duration/validity not stored in PricingService data).
# Keys match exact visa names from the pricing JSON.
VISA_METADATA: dict[str, dict[str, str]] = {
    # Single-entry visas
    "C1 Tourism": {"duration": "30 days", "validity": "Single entry"},
    "C2 Business": {"duration": "60 days", "validity": "Single entry"},
    "C7A&B Music/Art": {"duration": "60 days", "validity": "Single entry"},
    "C18 Work Trial": {"duration": "60 days", "validity": "Single entry"},
    "C22A&B Internship (60 Days)": {"duration": "60 days", "validity": "Single entry"},
    "C22A&B Internship (180 Days)": {"duration": "180 days", "validity": "Single entry"},
    # Multiple-entry visas
    "D12 Business Investigation (1 Year)": {"duration": "Up to 60 days/stay", "validity": "1 year, multiple entry"},
    "D12 Business Investigation (2 Years)": {"duration": "Up to 60 days/stay", "validity": "2 years, multiple entry"},
    # KITAS permits
    "E33G Remote Worker (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS — renewable"},
    "E33G Remote Worker (Extend)": {"duration": "1 year", "validity": "KITAS — renewal"},
    "E33G Remote Worker (Offshore)": {"duration": "1 year", "validity": "KITAS — offshore process"},
    "Freelance E23 (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS — renewable"},
    "Freelance E23 (Offshore)": {"duration": "1 year", "validity": "KITAS — offshore process"},
    "Working KITAS (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS — renewable"},
    "Working KITAS (Offshore)": {"duration": "1 year", "validity": "KITAS — offshore process"},
    "Working KITAS (Extend)": {"duration": "1 year", "validity": "KITAS — renewal"},
    "Investor KITAS 2 Years (Altus/Onshore)": {"duration": "2 years", "validity": "KITAS — renewable"},
    "Investor KITAS 2 Years (Offshore)": {"duration": "2 years", "validity": "KITAS — offshore process"},
    "Investor KITAS 2 Years (Extend)": {"duration": "2 years", "validity": "KITAS — renewal"},
    "Retirement (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS — renewable"},
    "Retirement (Offshore)": {"duration": "1 year", "validity": "KITAS — offshore process"},
    "Retirement (Extend)": {"duration": "1 year", "validity": "KITAS — renewal"},
    "Spouse 1 Year (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS dependent"},
    "Spouse 1 Year (Offshore)": {"duration": "1 year", "validity": "KITAS dependent — offshore"},
    "Spouse 1 Year (Extend)": {"duration": "1 year", "validity": "KITAS dependent — renewal"},
    "Spouse 2 Years (Altus/Onshore)": {"duration": "2 years", "validity": "KITAS dependent"},
    "Spouse 2 Years (Offshore)": {"duration": "2 years", "validity": "KITAS dependent — offshore"},
    "Spouse 2 Years (Extend)": {"duration": "2 years", "validity": "KITAS dependent — renewal"},
    "Dependent 1 Year (Altus/Onshore)": {"duration": "1 year", "validity": "KITAS dependent"},
    "Dependent 1 Year (Offshore)": {"duration": "1 year", "validity": "KITAS dependent — offshore"},
    "Dependent 1 Year (Extend)": {"duration": "1 year", "validity": "KITAS dependent — renewal"},
    "Dependent 2 Years (Altus/Onshore)": {"duration": "2 years", "validity": "KITAS dependent"},
    "Dependent 2 Years (Offshore)": {"duration": "2 years", "validity": "KITAS dependent — offshore"},
    "Dependent 2 Years (Extend)": {"duration": "2 years", "validity": "KITAS dependent — renewal"},
    # KITAP
    "Investor KITAP + MERP": {"duration": "5 years", "validity": "KITAP — permanent residence"},
    "Retirement KITAP + MERP": {"duration": "5 years", "validity": "KITAP — permanent residence"},
    "Dependent KITAP MERP": {"duration": "5 years", "validity": "KITAP dependent"},
    "MERP 1 Year": {"duration": "1 year", "validity": "Re-entry permit"},
    "MERP 2 Year": {"duration": "2 years", "validity": "Re-entry permit"},
    # Visa extensions
    "C1 Tourism Extension": {"duration": "30 days", "validity": "Extension only"},
}

# Score weights
SCORE_KEYWORD_MATCH = 2.0
SCORE_DURATION_FIT = 1.5
SCORE_FAMILY_MATCH = 1.0

WHATSAPP_NUMBER = "+62 813 3805 1876"
WHATSAPP_BASE_URL = "https://wa.me/6281338051876"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class VisaOracleService:
    """Anonymous visa recommendation engine backed by PricingService data."""

    def __init__(self) -> None:
        self._pricing = get_pricing_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend_visas(
        self,
        nationality: str,
        purpose: str,
        duration: str,
        family: bool,
    ) -> list[dict[str, Any]]:
        """Score and rank visa types. Returns top-3 results.

        Args:
            nationality: ISO country code or country name (informational only).
            purpose: One of visit/work/invest/retire/digital_nomad/family/study.
            duration: One of short/medium/long.
            family: True if applicant is bringing a spouse or dependents.

        Returns:
            List of up to 3 dicts with keys:
            visa_name, category, price, duration, validity, notes, score.
        """
        purpose_lower = purpose.lower().strip()
        duration_lower = duration.lower().strip()

        relevant_categories = PURPOSE_CATEGORY_MAP.get(
            purpose_lower,
            ["single_entry_visas", "multiple_entry_visas", "kitas_permits"],
        )
        keywords = PURPOSE_KEYWORDS.get(purpose_lower, [])

        scored: list[dict[str, Any]] = []

        services = self._pricing.prices.get("services", {})

        for category in relevant_categories:
            category_data = services.get(category, {})
            for visa_name, details in category_data.items():
                score = self._score_visa(
                    visa_name=visa_name,
                    details=details,
                    keywords=keywords,
                    duration=duration_lower,
                    family=family,
                )
                meta = VISA_METADATA.get(visa_name, {})
                scored.append(
                    {
                        "visa_name": visa_name,
                        "category": category,
                        "price": details.get("price", ""),
                        "duration": meta.get("duration", details.get("duration", "")),
                        "validity": meta.get("validity", details.get("validity", "")),
                        "notes": details.get("notes", ""),
                        "score": score,
                    }
                )

        # Sort descending by score, then alphabetically for stability
        scored.sort(key=lambda x: (-x["score"], x["visa_name"]))
        top3 = scored[:3]

        logger.debug(
            "recommend_visas: purpose=%s duration=%s family=%s → %d candidates → top3=%s",
            purpose,
            duration,
            family,
            len(scored),
            [r["visa_name"] for r in top3],
        )
        return top3

    def get_all_visa_types(self) -> list[dict[str, Any]]:
        """Return every visa type with name, category and price.

        Returns:
            List of dicts with keys: name, category, price.
        """
        result: list[dict[str, Any]] = []
        services = self._pricing.prices.get("services", {})

        for category, entries in services.items():
            for visa_name, details in entries.items():
                result.append(
                    {
                        "name": visa_name,
                        "category": category,
                        "price": details.get("price", ""),
                    }
                )

        return result

    def build_whatsapp_message(
        self,
        nationality: str,
        purpose: str,
        duration: str,
        visa_name: str,
        price: str,
    ) -> str:
        """Build a pre-filled WhatsApp deep-link message.

        Args:
            nationality: User's nationality (country name or code).
            purpose: Stated purpose (visit/work/etc.).
            duration: Stated duration (short/medium/long).
            visa_name: Recommended visa name.
            price: Official price string (e.g. "5.800.000 IDR").

        Returns:
            Full wa.me URL with pre-filled message.
        """
        text = (
            f"Halo Bali Zero! I'm interested in the {visa_name} "
            f"(approx. {price}). "
            f"My nationality: {nationality}, purpose: {purpose}, "
            f"duration: {duration}. "
            f"Can you help me get started?"
        )
        encoded = text.replace(" ", "%20").replace("\n", "%0A")
        return f"{WHATSAPP_BASE_URL}?text={encoded}"

    def build_telegram_summary(
        self,
        session_id: str,
        quiz_answers: dict[str, Any],
        recommended_visas: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        language: str,
    ) -> str:
        """Build a Telegram notification summary for Damar.

        Args:
            session_id: Anonymous session identifier.
            quiz_answers: Dict with nationality, purpose, duration, family, etc.
            recommended_visas: Top-3 recommendation list.
            messages: Chat turn history.
            language: Detected language code (en, id, ru …).

        Returns:
            Formatted Markdown string for Telegram.
        """
        nationality = quiz_answers.get("nationality", "Unknown")
        purpose = quiz_answers.get("purpose", "Unknown")
        duration = quiz_answers.get("duration", "Unknown")
        family = quiz_answers.get("family", False)

        visa_lines = "\n".join(
            f"  {i+1}. {v.get('visa_name', '?')} — {v.get('price', '?')} "
            f"(score: {v.get('score', 0):.1f})"
            for i, v in enumerate(recommended_visas[:3])
        )

        chat_count = len(messages)
        handoff = any(
            "whatsapp" in str(m.get("content", "")).lower() for m in messages
        )

        summary = (
            f"*Visa Oracle Lead* 🧭\n"
            f"Session: `{session_id[:12]}…`\n"
            f"Language: `{language}`\n\n"
            f"*Quiz Answers*\n"
            f"• Nationality: {nationality}\n"
            f"• Purpose: {purpose}\n"
            f"• Duration: {duration}\n"
            f"• Family: {'Yes' if family else 'No'}\n\n"
            f"*Recommended Visas*\n{visa_lines}\n\n"
            f"*Chat:* {chat_count} messages | "
            f"WhatsApp CTA: {'triggered' if handoff else 'not yet'}"
        )
        return summary

    @staticmethod
    def hash_ip(ip: str) -> str:
        """Return SHA-256 hex digest of an IP address.

        Args:
            ip: IPv4 or IPv6 address string.

        Returns:
            64-character hex string.
        """
        return hashlib.sha256(ip.encode()).hexdigest()

    @staticmethod
    def generate_session_id() -> str:
        """Generate a cryptographically random 32-byte hex session ID.

        Returns:
            64-character hex string.
        """
        return secrets.token_hex(32)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_visa(
        self,
        visa_name: str,
        details: dict[str, Any],
        keywords: list[str],
        duration: str,
        family: bool,
    ) -> float:
        """Compute relevance score for a single visa type.

        Scoring:
        - +2.0 per keyword that appears in visa_name (case-insensitive)
        - +1.5 if stated duration fits the visa's duration field
        - +1.0 if family=True and visa_name contains spouse/dependent/family

        Returns:
            float score (>= 0.0)
        """
        score = 0.0
        name_lower = visa_name.lower()

        # Keyword matching
        for kw in keywords:
            if kw.lower() in name_lower:
                score += SCORE_KEYWORD_MATCH

        # Duration fit
        visa_duration_raw = details.get("duration", "")
        visa_days = self._parse_duration_days(visa_duration_raw)
        if visa_days is not None and duration in DURATION_THRESHOLDS:
            lo, hi = DURATION_THRESHOLDS[duration]
            if lo <= visa_days <= hi:
                score += SCORE_DURATION_FIT

        # Family match
        if family:
            family_keywords = {"spouse", "dependent", "family", "child"}
            if any(fk in name_lower for fk in family_keywords):
                score += SCORE_FAMILY_MATCH

        return score

    @staticmethod
    def _parse_duration_days(duration_str: str) -> int | None:
        """Parse a duration string like '60 days', '180 days', '1 year', '2 years'.

        Returns:
            Integer number of days, or None if unparseable.
        """
        if not duration_str:
            return None

        lower = duration_str.lower().strip()
        parts = lower.split()
        if not parts:
            return None

        try:
            value = int(parts[0])
        except (ValueError, IndexError):
            return None

        unit = parts[1] if len(parts) > 1 else "days"
        if "year" in unit:
            return value * 365
        if "month" in unit:
            return value * 30
        # default: days
        return value


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_visa_oracle_service: VisaOracleService | None = None


def get_visa_oracle_service() -> VisaOracleService:
    """Return the process-level VisaOracleService singleton."""
    global _visa_oracle_service
    if _visa_oracle_service is None:
        _visa_oracle_service = VisaOracleService()
        logger.info("VisaOracleService singleton initialised")
    return _visa_oracle_service
