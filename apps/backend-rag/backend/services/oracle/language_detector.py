"""
Language Detection Service
Responsibility: Detect query language for localization
"""

import logging

logger = logging.getLogger(__name__)


class LanguageDetectionService:
    """
    Service for detecting query language.

    Responsibility: Detect language from query text with Italian focus for Bali Zero clients.
    """

    def __init__(self):
        """Initialize language detection service."""
        # Italian markers
        self.italian_markers = [
            "sto ",
            "vorrei",
            "dammi",
            "dimmi",
            "fammi",
            "parlami",
            "aprire",
            "chiudere",
            "valutando",
            "considerando",
            "potresti",
            "puoi",
            "posso",
            "devo",
            "voglio",
            "ipotesi",
            "opzioni",
            "scenari",
            "situazione",
            "cittadinanza",
            "indonesiana",
            "italiana",
            "straniero",
            "quali sono",
            "come funziona",
            "che cosa",
            "quanto costa",
            "ho bisogno",
            "mi serve",
            "mi interessa",
            " il ",
            " la ",
            " le ",
            " gli ",
            " un ",
            " una ",
            " del ",
            " della ",
            " dei ",
            " delle ",
            " con ",
            " senza ",
            " per ",
            " nel ",
            " nella ",
            "ciao",
            "salve",
            "buongiorno",
            "buonasera",
            "grazie",
            "prego",
        ]

        # Indonesian markers
        self.indonesian_markers = [
            "apa",
            "bagaimana",
            "siapa",
            "dimana",
            "kapan",
            "mengapa",
            "saya",
            "aku",
            "kamu",
            "anda",
            "bisa",
            "mau",
            "ingin",
            "perlu",
            "tolong",
            "terima kasih",
            "selamat",
            "yang",
            "dengan",
            "untuk",
            "dari",
        ]

    def detect_language(self, query: str) -> str:
        """
        Detect language from query text with Italian focus for Bali Zero clients.

        Args:
            query: User query text

        Returns:
            Language code: "it", "id", or "en"
        """
        query_lower = query.lower()

        it_count = sum(1 for m in self.italian_markers if m in query_lower)
        id_count = sum(1 for m in self.indonesian_markers if m in query_lower)

        if it_count > id_count and it_count >= 2:
            return "it"
        if id_count > it_count and id_count >= 2:
            return "id"
        return "en"

    def get_target_language(
        self,
        query: str,
        language_override: str | None = None,
        user_language: str | None = None,
    ) -> str:
        """
        Get target language with priority: override > user preference > detected.

        Args:
            query: User query text
            language_override: Optional language override
            user_language: Optional user language preference

        Returns:
            Target language code
        """
        if language_override:
            return language_override
        if user_language:
            return user_language
        return self.detect_language(query)
