"""
Clarification Service - Detect ambiguous queries and request clarification
Improves response quality by ensuring the AI understands user intent clearly

This service detects when a user's question is ambiguous or incomplete,
prompting for clarification before generating a potentially incorrect response.

Author: ZANTARA Development Team
Date: 2025-10-16
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AmbiguityType(Enum):
    """Types of ambiguity that require clarification"""

    VAGUE = "vague"  # "Tell me about visas" - which visa?
    INCOMPLETE = "incomplete"  # "How much does it cost?" - what costs?
    MULTIPLE_INTERPRETATIONS = "multiple"  # "Can I work?" - work where? as what?
    UNCLEAR_CONTEXT = "unclear_context"  # Pronoun without antecedent
    NONE = "none"  # Clear question


class ClarificationService:
    """
    Detects ambiguous queries and generates clarification requests

    Features:
    - Pattern-based ambiguity detection
    - Context-aware clarification questions
    - Multi-language support (EN, IT, ID)
    - Confidence scoring for ambiguity detection
    """

    def __init__(self, search_service=None):
        """
        Initialize clarification service

        Args:
            search_service: Optional SearchService instance (for test compatibility)
        """
        self.search_service = search_service
        self.ambiguity_threshold = 0.6  # Confidence threshold for triggering clarification
        logger.info("✅ ClarificationService initialized")

    def detect_ambiguity(
        self, query: str, conversation_history: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Detect if a query is ambiguous and needs clarification

        Args:
            query: User's question
            conversation_history: Previous conversation for context

        Returns:
            {
                "is_ambiguous": bool,
                "confidence": float,  # 0.0-1.0
                "ambiguity_type": str,
                "reasons": List[str],  # Why it's ambiguous
                "clarification_needed": bool
            }
        """
        query_lower = query.lower().strip()
        reasons = []
        ambiguity_type = AmbiguityType.NONE
        confidence = 0.0

        # Check for various ambiguity patterns

        # 1. VAGUE QUESTIONS (no specifics)
        vague_patterns = [
            "tell me about",
            "what about",
            "how about",
            "info on",
            "information about",
            "explain",
            "describe",
        ]
        vague_triggers = [
            "visa",
            "tax",
            "business",
            "company",
            "permit",
            "service",
            "it",
            "this",
            "that",
        ]

        for pattern in vague_patterns:
            if pattern in query_lower:
                # Check if followed by vague trigger
                for trigger in vague_triggers:
                    if trigger in query_lower:
                        confidence += 0.3
                        reasons.append(f"Vague question: '{pattern} {trigger}' without specifics")
                        ambiguity_type = AmbiguityType.VAGUE
                        break

        # 2. INCOMPLETE QUESTIONS (missing key info)
        incomplete_patterns = [
            "how much",  # How much what?
            "how long",  # How long for what?
            "when can",  # When can what?
            "where is",  # Where is what?
            "who can",  # Who can what?
        ]

        for pattern in incomplete_patterns:
            if query_lower.startswith(pattern) and len(query.split()) <= 4:
                confidence += 0.4
                reasons.append(f"Incomplete question: starts with '{pattern}' but lacks context")
                ambiguity_type = AmbiguityType.INCOMPLETE

        # 3. PRONOUN WITHOUT ANTECEDENT (in first message)
        has_conversation = conversation_history and len(conversation_history) > 0
        pronouns = ["it", "this", "that", "these", "those", "they", "them"]

        if not has_conversation:
            for pronoun in pronouns:
                # Check if pronoun is used as subject
                if query_lower.startswith(pronoun + " ") or f" {pronoun} " in query_lower:
                    confidence += 0.5
                    reasons.append(f"Pronoun '{pronoun}' used without prior context")
                    ambiguity_type = AmbiguityType.UNCLEAR_CONTEXT

        # 4. MULTIPLE POSSIBLE INTERPRETATIONS
        multi_interpretation_keywords = {
            "work": ["work visa", "work permit", "job", "employment"],  # Which aspect?
            "cost": ["registration cost", "service cost", "government fee", "annual cost"],
            "register": ["company registration", "tax registration", "visa registration"],
            "open": ["open company", "open bank account", "open office"],
        }

        for keyword, interpretations in multi_interpretation_keywords.items():
            if keyword in query_lower and len(query.split()) <= 5:
                # Short query with ambiguous keyword
                confidence += 0.3
                reasons.append(
                    f"Keyword '{keyword}' has multiple interpretations: {', '.join(interpretations[:2])}"
                )
                ambiguity_type = AmbiguityType.MULTIPLE_INTERPRETATIONS

        # 5. TOO SHORT (< 3 words) without clear intent
        if len(query.split()) < 3 and not any(
            greeting in query_lower for greeting in ["hi", "hello", "ciao", "halo"]
        ):
            confidence += 0.2
            reasons.append(f"Very short query ({len(query.split())} words) - may need more detail")

        # Determine if clarification is needed
        is_ambiguous = confidence >= self.ambiguity_threshold
        clarification_needed = is_ambiguous and ambiguity_type != AmbiguityType.NONE

        result = {
            "is_ambiguous": is_ambiguous,
            "confidence": min(confidence, 1.0),
            "ambiguity_type": ambiguity_type.value,
            "reasons": reasons,
            "clarification_needed": clarification_needed,
        }

        if clarification_needed:
            logger.info(
                f"🤔 [Clarification] Ambiguous query detected (confidence: {confidence:.2f}, type: {ambiguity_type.value})"
            )
            for reason in reasons:
                logger.info(f"   - {reason}")
        else:
            logger.info(f"✅ [Clarification] Query is clear (confidence: {confidence:.2f})")

        return result

    def generate_clarification_request(
        self, query: str, ambiguity_info: dict[str, Any], language: str = "en"
    ) -> str:
        """
        Generate a natural clarification request

        Args:
            query: User's original question
            ambiguity_info: Result from detect_ambiguity()
            language: Language code (en, it, id)

        Returns:
            Clarification request string
        """
        ambiguity_type = ambiguity_info["ambiguity_type"]
        query.lower()

        # Language-specific clarification templates
        templates = {
            AmbiguityType.VAGUE.value: {
                "en": "I'd be happy to help! Could you be more specific about what aspect of {topic} you're interested in?",
                "it": "Sono felice di aiutarti! Potresti essere più specifico su quale aspetto di {topic} ti interessa?",
                "id": "Senang bisa membantu! Bisakah Anda lebih spesifik tentang aspek {topic} yang Anda minati?",
            },
            AmbiguityType.INCOMPLETE.value: {
                "en": "I'd like to help, but I need a bit more information. Could you clarify what you're asking about?",
                "it": "Vorrei aiutarti, ma ho bisogno di qualche informazione in più. Potresti chiarire cosa stai chiedendo?",
                "id": "Saya ingin membantu, tapi butuh sedikit informasi tambahan. Bisakah Anda jelaskan lebih lanjut?",
            },
            AmbiguityType.MULTIPLE_INTERPRETATIONS.value: {
                "en": "I can help with that! To give you the most accurate answer, could you specify which {topic} you mean?",
                "it": "Posso aiutarti! Per darti la risposta più accurata, potresti specificare quale {topic} intendi?",
                "id": "Saya bisa bantu! Untuk jawaban yang akurat, bisa sebutkan {topic} yang mana?",
            },
            AmbiguityType.UNCLEAR_CONTEXT.value: {
                "en": "I'd love to help! Could you provide a bit more context about what you're referring to?",
                "it": "Vorrei aiutarti! Potresti fornire un po' più di contesto su cosa ti riferisci?",
                "id": "Senang membantu! Bisakah Anda kasih konteks lebih tentang yang Anda maksud?",
            },
        }

        # Extract potential topic from query
        topic = self._extract_main_topic(query)

        # Get template
        template = templates.get(ambiguity_type, templates[AmbiguityType.VAGUE.value])

        message = template.get(language, template["en"])

        # Replace {topic} placeholder
        if "{topic}" in message and topic:
            message = message.format(topic=topic)
        else:
            message = message.replace(" {topic}", "")

        # Add specific clarification options if detected
        options = self._generate_clarification_options(query, ambiguity_type, language)
        if options:
            if language == "en":
                message += f"\n\nFor example:\n{options}"
            elif language == "it":
                message += f"\n\nAd esempio:\n{options}"
            elif language == "id":
                message += f"\n\nContohnya:\n{options}"

        return message

    def _extract_main_topic(self, query: str) -> str | None:
        """Extract main topic from query"""
        query_lower = query.lower()

        # Topic keywords
        topics = {
            "visa": ["visa", "visto", "permit"],
            "tax": ["tax", "pajak", "tassa", "npwp"],
            "business": ["business", "company", "bisnis", "azienda", "pt pma"],
            "cost": ["cost", "price", "fee", "biaya", "costo"],
            "registration": ["register", "registration", "daftar", "registrazione"],
        }

        for topic, keywords in topics.items():
            if any(keyword in query_lower for keyword in keywords):
                return topic

        return None

    def _generate_clarification_options(
        self, query: str, _ambiguity_type: str, language: str
    ) -> str | None:
        """Generate specific clarification options based on query"""
        query_lower = query.lower()

        # Visa-related clarifications
        visa_options = {
            "en": "- Tourist visa\n- Business visa (KITAS)\n- Work permit\n- Visa extension",
            "it": "- Visto turistico\n- Visto business (KITAS)\n- Permesso di lavoro\n- Estensione visto",
            "id": "- Visa turis\n- Visa bisnis (KITAS)\n- Izin kerja\n- Perpanjangan visa",
        }
        if "visa" in query_lower or "permit" in query_lower:
            return visa_options.get(language)

        # Tax-related clarifications
        tax_options = {
            "en": "- Corporate tax\n- Personal income tax\n- VAT\n- Tax registration",
            "it": "- Tasse aziendali\n- Tasse personali\n- IVA\n- Registrazione fiscale",
            "id": "- Pajak perusahaan\n- Pajak penghasilan\n- PPN\n- Pendaftaran NPWP",
        }
        if "tax" in query_lower or "pajak" in query_lower:
            return tax_options.get(language)

        # Business-related clarifications
        business_options = {
            "en": "- Starting a new company\n- PT PMA registration\n- Business licenses\n- Company requirements",
            "it": "- Aprire una nuova azienda\n- Registrazione PT PMA\n- Licenze commerciali\n- Requisiti aziendali",
            "id": "- Buka perusahaan baru\n- Daftar PT PMA\n- Izin usaha\n- Persyaratan perusahaan",
        }
        if "business" in query_lower or "company" in query_lower:
            return business_options.get(language)

        return None

    def should_request_clarification(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        force_threshold: float = 0.7,
    ) -> bool:
        """
        Determine if clarification should be requested

        Args:
            query: User's question
            conversation_history: Previous conversation
            force_threshold: Confidence threshold for forcing clarification (default: 0.7)

        Returns:
            True if clarification should be requested
        """
        ambiguity_info = self.detect_ambiguity(query, conversation_history)

        # Always request if very high confidence
        if ambiguity_info["confidence"] >= force_threshold:
            return True

        # Request if ambiguous and no recent conversation
        if ambiguity_info["is_ambiguous"]:
            has_recent_context = conversation_history and len(conversation_history) > 0
            if not has_recent_context:
                return True

        return False

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for clarification service

        Returns:
            {
                "status": "healthy",
                "features": {...}
            }
        """
        return {
            "status": "healthy",
            "features": {
                "ambiguity_detection": True,
                "pattern_based": True,
                "context_aware": True,
                "supported_languages": ["en", "it", "id"],
                "ambiguity_types": [t.value for t in AmbiguityType],
            },
            "configuration": {"ambiguity_threshold": self.ambiguity_threshold},
        }
