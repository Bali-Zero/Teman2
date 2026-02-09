"""
Quality Checker for Cached Conversations

Validates conversation quality before caching:
- Citation presence and format
- Response completeness
- Factual consistency indicators
- Language quality

Author: Nuzantara Team
Date: 2026-02-09
Reference: docs/caching/WORKFLOW_GUIDE.md (Phase 3)
"""

import re
from typing import Dict, List, Tuple


class QualityChecker:
    """
    Quality validation for cached conversations.

    Checks:
    1. Citations: Minimum count, proper format
    2. Completeness: Response length, structure
    3. Language: Readability, professionalism
    4. Factual indicators: Certainty language, hedge words
    """

    MIN_CITATIONS = 2
    MIN_RESPONSE_WORDS = 100
    MAX_RESPONSE_WORDS = 800

    # Patterns for quality checks
    CITATION_PATTERN = re.compile(r"\[Source:\s*[^\]]+\]")
    HEDGE_WORDS = [
        "typically", "generally", "usually", "often", "sometimes",
        "may", "might", "could", "should", "possibly", "probably",
        "da verificare", "to be verified", "to be confirmed"
    ]
    HALLUCINATION_INDICATORS = [
        "I think", "I believe", "in my opinion", "probably around",
        "estimate", "approximately between", "range from"
    ]

    def __init__(self):
        """Initialize quality checker."""
        self.last_check_details: Dict = {}

    def check_conversation(
        self,
        query: str,
        response: str,
        min_citations: int = None
    ) -> Tuple[bool, int, Dict]:
        """
        Check conversation quality.

        Args:
            query: User query
            response: AI response
            min_citations: Override minimum citations (default: 2)

        Returns:
            Tuple of (passed, score, details)
            - passed: True if meets minimum quality
            - score: 0-100 quality score
            - details: Dict with check results
        """
        min_citations = min_citations or self.MIN_CITATIONS

        details = {
            "citations": self._check_citations(response, min_citations),
            "completeness": self._check_completeness(response),
            "language": self._check_language(response),
            "factual": self._check_factual_indicators(response)
        }

        # Calculate weighted score
        score = (
            details["citations"]["score"] * 0.35 +  # 35% weight
            details["completeness"]["score"] * 0.25 +  # 25% weight
            details["language"]["score"] * 0.20 +  # 20% weight
            details["factual"]["score"] * 0.20  # 20% weight
        )

        # Pass threshold: 70/100
        passed = score >= 70

        self.last_check_details = details

        return passed, int(score), details

    def _check_citations(self, response: str, min_citations: int) -> Dict:
        """
        Check citation quality.

        Returns:
            Dict with score and details
        """
        citations = self.CITATION_PATTERN.findall(response)
        citation_count = len(citations)

        # Score based on citation count
        if citation_count >= min_citations + 2:
            score = 100  # Excellent
        elif citation_count >= min_citations:
            score = 85  # Good
        elif citation_count >= 1:
            score = 60  # Acceptable (1 citation)
        else:
            score = 0  # No citations

        return {
            "score": score,
            "citation_count": citation_count,
            "min_required": min_citations,
            "passed": citation_count >= min_citations,
            "citations": citations
        }

    def _check_completeness(self, response: str) -> Dict:
        """
        Check response completeness.

        Returns:
            Dict with score and details
        """
        word_count = len(response.split())

        # Check structure markers
        has_sections = bool(re.search(r"##|###|\*\*", response))
        has_steps = bool(re.search(r"\d+\.|Step \d+|-", response))

        # Score based on length and structure
        if self.MIN_RESPONSE_WORDS <= word_count <= self.MAX_RESPONSE_WORDS:
            length_score = 100
        elif word_count < self.MIN_RESPONSE_WORDS:
            length_score = (word_count / self.MIN_RESPONSE_WORDS) * 100
        else:  # Too long
            length_score = max(60, 100 - (word_count - self.MAX_RESPONSE_WORDS) / 10)

        structure_bonus = 0
        if has_sections:
            structure_bonus += 10
        if has_steps:
            structure_bonus += 10

        score = min(100, length_score + structure_bonus)

        return {
            "score": int(score),
            "word_count": word_count,
            "min_words": self.MIN_RESPONSE_WORDS,
            "max_words": self.MAX_RESPONSE_WORDS,
            "has_sections": has_sections,
            "has_steps": has_steps,
            "passed": word_count >= self.MIN_RESPONSE_WORDS
        }

    def _check_language(self, response: str) -> Dict:
        """
        Check language quality.

        Returns:
            Dict with score and details
        """
        # Calculate average sentence length
        sentences = re.split(r"[.!?]+", response)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0

        # Optimal: 15-25 words per sentence
        if 15 <= avg_sentence_length <= 25:
            readability_score = 100
        elif 10 <= avg_sentence_length < 15 or 25 < avg_sentence_length <= 30:
            readability_score = 85
        else:
            readability_score = 70

        # Check for professional tone (no informal language)
        informal_indicators = [
            "gonna", "wanna", "kinda", "sorta", "yeah", "nope",
            "btw", "fyi", "imho", "lol"
        ]
        has_informal = any(word in response.lower() for word in informal_indicators)
        professionalism_score = 0 if has_informal else 100

        # Combined score
        score = (readability_score * 0.6 + professionalism_score * 0.4)

        return {
            "score": int(score),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "optimal_range": "15-25 words",
            "has_informal_language": has_informal,
            "passed": score >= 70
        }

    def _check_factual_indicators(self, response: str) -> Dict:
        """
        Check for hallucination and certainty indicators.

        Returns:
            Dict with score and details
        """
        response_lower = response.lower()

        # Count hedge words (good - shows appropriate uncertainty)
        hedge_count = sum(1 for word in self.HEDGE_WORDS if word in response_lower)

        # Count hallucination indicators (bad - shows speculation)
        hallucination_count = sum(
            1 for phrase in self.HALLUCINATION_INDICATORS
            if phrase in response_lower
        )

        # Ideal: 1-3 hedge words (appropriate uncertainty)
        # Bad: Any hallucination indicators
        if hallucination_count > 0:
            score = max(30, 100 - (hallucination_count * 20))
        elif 1 <= hedge_count <= 3:
            score = 100
        elif hedge_count == 0:
            score = 85  # Too certain (might be overstating)
        else:  # hedge_count > 3
            score = 70  # Too uncertain

        return {
            "score": score,
            "hedge_count": hedge_count,
            "hallucination_indicators": hallucination_count,
            "has_hallucination_risk": hallucination_count > 0,
            "passed": hallucination_count == 0
        }

    def get_failure_reasons(self, details: Dict) -> List[str]:
        """
        Extract failure reasons from check details.

        Args:
            details: Details dict from check_conversation()

        Returns:
            List of human-readable failure reasons
        """
        reasons = []

        if not details["citations"]["passed"]:
            reasons.append(
                f"Insufficient citations: {details['citations']['citation_count']} "
                f"(min: {details['citations']['min_required']})"
            )

        if not details["completeness"]["passed"]:
            reasons.append(
                f"Response too short: {details['completeness']['word_count']} words "
                f"(min: {details['completeness']['min_words']})"
            )

        if not details["language"]["passed"]:
            if details["language"]["has_informal_language"]:
                reasons.append("Contains informal language")
            else:
                reasons.append("Poor readability (sentence length)")

        if not details["factual"]["passed"]:
            reasons.append(
                f"Hallucination risk: {details['factual']['hallucination_indicators']} indicators found"
            )

        return reasons


# CLI for testing
if __name__ == "__main__":
    import click

    @click.group()
    def cli():
        """Quality checker CLI for testing."""
        pass

    @cli.command()
    @click.argument("query")
    @click.argument("response")
    def check(query: str, response: str):
        """Check conversation quality."""
        checker = QualityChecker()
        passed, score, details = checker.check_conversation(query, response)

        click.echo("\n" + "="*70)
        click.echo("✅ QUALITY CHECK RESULTS" if passed else "❌ QUALITY CHECK FAILED")
        click.echo("="*70)

        click.echo(f"\n📊 Overall Score: {score}/100")
        click.echo(f"🎯 Status: {'PASSED' if passed else 'FAILED'}")

        click.echo(f"\n📚 Citations: {details['citations']['score']}/100")
        click.echo(f"   Count: {details['citations']['citation_count']} (min: {details['citations']['min_required']})")

        click.echo(f"\n📝 Completeness: {details['completeness']['score']}/100")
        click.echo(f"   Words: {details['completeness']['word_count']}")
        click.echo(f"   Sections: {details['completeness']['has_sections']}")

        click.echo(f"\n🗣️ Language: {details['language']['score']}/100")
        click.echo(f"   Avg sentence: {details['language']['avg_sentence_length']} words")
        click.echo(f"   Informal: {details['language']['has_informal_language']}")

        click.echo(f"\n🔍 Factual: {details['factual']['score']}/100")
        click.echo(f"   Hedge words: {details['factual']['hedge_count']}")
        click.echo(f"   Hallucination risk: {details['factual']['has_hallucination_risk']}")

        if not passed:
            reasons = checker.get_failure_reasons(details)
            click.echo(f"\n❌ Failure Reasons:")
            for reason in reasons:
                click.echo(f"   - {reason}")

        click.echo("\n" + "="*70)

    cli()
