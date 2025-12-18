"""
Memory Fact Extractor - Automatic key facts extraction from conversations
Extracts important facts to save in user memory for context building
"""

import logging
import re

logger = logging.getLogger(__name__)


class MemoryFactExtractor:
    """
    Extracts key facts from user messages and AI responses

    Facts to extract:
    - User preferences (languages, meeting times, communication style)
    - Business information (company name, KBLI, capital, industry)
    - Personal information (name, nationality, location, profession)
    - Timeline events (deadlines, upcoming events, milestones)
    - Concerns and pain points (what user is worried about)
    """

    def __init__(self):
        """Initialize fact extractor with patterns"""

        # Preference patterns
        self.preference_patterns = [
            (r"preferisco|prefer|mi piace|I like", "preference"),
            (r"voglio|want|desidero|wish", "want"),
            (r"non voglio|don\'t want|non mi piace|I don\'t like", "avoid"),
            (r"favorite|preferito|my favorite", "preference"), # Added
        ]

        # Business patterns
        self.business_patterns = [
            (r"PT PMA|company|azienda|società", "company"),
            (r"KBLI|business code|codice attività", "kbli"),
            (r"capitale|capital|investimento|investment", "capital"),
            (r"settore|industry|sector|campo", "industry"),
        ]

        # Personal patterns
        self.personal_patterns = [
            (r"sono|I am|mi chiamo|my name is", "identity"),
            (r"nazionalità|nationality|passport", "nationality"),
            (r"vivo a|live in|based in|location", "location"),
            (r"lavoro come|work as|profession|mestiere", "profession"),
            (r"secret word|parola segreta|codice segreto", "secret"), # Added for BANANA test
            (r"remember|ricorda|memorizza", "instruction"), # Added for explicit instruction
        ]

        # Timeline patterns
        self.timeline_patterns = [
            (r"scadenza|deadline|entro|by|before", "deadline"),
            (r"prossimo|next|upcoming|futuro", "upcoming"),
            (r"urgente|urgent|rush|quickly", "urgent"),
        ]

    def extract_facts_from_conversation(
        self, user_message: str, ai_response: str, user_id: str
    ) -> list[dict]:
        """
        Extract key facts from a conversation turn

        Args:
            user_message: What user said
            ai_response: What AI responded
            user_id: User identifier

        Returns:
            List of facts: [{"content": str, "type": str, "confidence": float}, ...]
        """
        facts = []

        try:
            # Extract from user message (higher value)
            user_facts = self._extract_from_text(user_message, source="user")
            facts.extend(user_facts)

            # Extract from AI response (lower value, but contains confirmed info)
            ai_facts = self._extract_from_text(ai_response, source="ai")
            facts.extend(ai_facts)

            # Deduplicate and rank by confidence
            facts = self._deduplicate_facts(facts)

            # Log extraction results
            if facts:
                logger.info(f"💎 [FactExtractor] Extracted {len(facts)} facts for {user_id}")
                for fact in facts[:3]:  # Log top 3
                    logger.info(
                        f"   - [{fact['type']}] {fact['content'][:50]}... (conf: {fact['confidence']:.2f})"
                    )

            return facts

        except Exception as e:
            logger.error(f"❌ [FactExtractor] Extraction failed: {e}")
            return []

    def _extract_from_text(self, text: str, source: str = "user") -> list[dict]:
        """Extract facts from a single text (user or AI)"""
        facts = []
        text_lower = text.lower()

        # Base confidence by source
        base_confidence = 0.8 if source == "user" else 0.6

        # Check preference patterns
        for pattern, fact_type in self.preference_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                # Extract context with word boundaries (no truncation)
                context = self._extract_context_with_word_boundaries(
                    text, match.start(), match.end(), chars_before=50, chars_after=50
                )
                context = self._clean_context(context)

                if context and len(context) > 10:
                    facts.append(
                        {
                            "content": context,
                            "type": fact_type,
                            "confidence": base_confidence,
                            "source": source,
                        }
                    )

        # Check business patterns
        for pattern, fact_type in self.business_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                context = self._extract_context_with_word_boundaries(
                    text, match.start(), match.end(), chars_before=30, chars_after=70
                )
                context = self._clean_context(context)

                if context and len(context) > 10:
                    facts.append(
                        {
                            "content": context,
                            "type": fact_type,
                            "confidence": base_confidence + 0.1,  # Business facts are important
                            "source": source,
                        }
                    )

        # Check personal patterns
        for pattern, fact_type in self.personal_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                context = self._extract_context_with_word_boundaries(
                    text, match.start(), match.end(), chars_before=20, chars_after=100
                )
                context = self._clean_context(context)

                if context and len(context) > 10:
                    facts.append(
                        {
                            "content": context,
                            "type": fact_type,
                            "confidence": base_confidence
                            + 0.15,  # Identity facts are very important
                            "source": source,
                        }
                    )

        # Check timeline patterns
        for pattern, fact_type in self.timeline_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                context = self._extract_context_with_word_boundaries(
                    text, match.start(), match.end(), chars_before=40, chars_after=60
                )
                context = self._clean_context(context)

                if context and len(context) > 10:
                    facts.append(
                        {
                            "content": context,
                            "type": fact_type,
                            "confidence": base_confidence + 0.2,  # Timelines are critical
                            "source": source,
                        }
                    )

        return facts

    def _extract_context_with_word_boundaries(
        self,
        text: str,
        match_start: int,
        match_end: int,
        chars_before: int = 50,
        chars_after: int = 50,
    ) -> str:
        """
        Extract context around a match, respecting word boundaries.
        Avoids cutting words in the middle.
        """
        # Find approximate start/end positions
        approx_start = max(0, match_start - chars_before)
        approx_end = min(len(text), match_end + chars_after)

        # Extend to word boundary at start (find previous space or start of text)
        if approx_start > 0:
            # Look backwards for a space
            while approx_start > 0 and text[approx_start] not in " \n\t":
                approx_start -= 1
            # Skip the space itself
            if text[approx_start] in " \n\t":
                approx_start += 1

        # Extend to word boundary at end (find next space or end of text)
        if approx_end < len(text):
            # Look forward for a space or punctuation
            while approx_end < len(text) and text[approx_end] not in " \n\t.,;:!?":
                approx_end += 1

        context = text[approx_start:approx_end].strip()
        return context

    def _clean_context(self, context: str) -> str:
        """Clean extracted context"""
        # Remove markdown
        context = re.sub(r"\*\*|__|\*|_", "", context)

        # Remove extra whitespace
        context = " ".join(context.split())

        # Remove incomplete sentences at start/end
        context = context.lstrip(".,;:!? ")
        context = context.rstrip(".,;:!? ")

        # Capitalize first letter
        if context:
            context = context[0].upper() + context[1:]

        return context

    def _deduplicate_facts(self, facts: list[dict]) -> list[dict]:
        """Remove duplicate facts, keeping highest confidence"""
        if not facts:
            return []

        # Sort by confidence (highest first)
        facts_sorted = sorted(facts, key=lambda x: x["confidence"], reverse=True)

        # Deduplicate by content similarity
        unique_facts = []
        seen_contents = []

        for fact in facts_sorted:
            content_lower = fact["content"].lower()

            # Check if similar fact already exists
            is_duplicate = False
            for seen in seen_contents:
                # Simple similarity: if 70% of words overlap, it's duplicate
                overlap = self._calculate_overlap(content_lower, seen)
                if overlap > 0.7:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_facts.append(fact)
                seen_contents.append(content_lower)

        # Limit to top 3 facts per conversation turn
        return unique_facts[:3]

    def _calculate_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap between two texts"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def extract_quick_facts(self, text: str, max_facts: int = 2) -> list[str]:
        """
        Quick fact extraction for immediate use
        Returns simple strings instead of full dict
        """
        facts_full = self._extract_from_text(text, source="user")

        # Sort by confidence and take top N
        facts_sorted = sorted(facts_full, key=lambda x: x["confidence"], reverse=True)

        # Return just the content strings
        return [f["content"] for f in facts_sorted[:max_facts]]
