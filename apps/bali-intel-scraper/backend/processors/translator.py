"""
Translation service for multilingual content.

Translates non-English articles to English for processing.
"""

from dataclasses import dataclass
from langdetect import detect, LangDetectException

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="translator")


@dataclass
class TranslationResult:
    """Translation result."""

    translated_text: str
    source_language: str
    confidence: float
    was_translated: bool


class Translator:
    """Translate content to English."""

    SUPPORTED_LANGUAGES = {
        "id": "Indonesian",
        "ms": "Malay",
        "jv": "Javanese",
        "su": "Sundanese",
        "en": "English",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "th": "Thai",
        "vi": "Vietnamese",
        "tl": "Tagalog",
    }

    def __init__(self, target_lang: str = "en"):
        self.target_lang = target_lang

    def detect_language(self, text: str) -> tuple[str, float]:
        """Detect language of text."""
        try:
            # Use first 1000 chars for detection
            sample = text[:1000]
            lang = detect(sample)

            # langdetect doesn't give confidence, assume high
            return lang, 0.9

        except LangDetectException:
            return "unknown", 0.0

    async def translate(
        self, text: str, source_lang: str | None = None
    ) -> TranslationResult:
        """
        Translate text to English.

        Args:
            text: Text to translate
            source_lang: Source language code (auto-detect if None)

        Returns:
            Translation result
        """
        if not text or len(text.strip()) < 10:
            return TranslationResult(
                translated_text=text,
                source_language=source_lang or "unknown",
                confidence=1.0,
                was_translated=False,
            )

        # Detect language if not provided
        if not source_lang:
            source_lang, confidence = self.detect_language(text)
        else:
            confidence = 1.0

        # Skip if already English
        if source_lang == "en":
            return TranslationResult(
                translated_text=text,
                source_language="en",
                confidence=confidence,
                was_translated=False,
            )

        # Translate using AI
        try:
            translated = await self._translate_with_ai(text, source_lang)

            logger.info(
                f"Translated from {source_lang}",
                action=LogAction.TRANSFORM,
                metadata={"source_lang": source_lang, "confidence": confidence},
            )

            return TranslationResult(
                translated_text=translated,
                source_language=source_lang,
                confidence=confidence,
                was_translated=True,
            )

        except Exception as e:
            logger.error(f"Translation failed: {e}", action=LogAction.ERROR)

            # Return original on failure
            return TranslationResult(
                translated_text=text,
                source_language=source_lang,
                confidence=confidence,
                was_translated=False,
            )

    async def _translate_with_ai(self, text: str, source_lang: str) -> str:
        """Translate using AI."""
        lang_name = self.SUPPORTED_LANGUAGES.get(source_lang, source_lang)

        prompt = f"""Translate this {lang_name} text to English. Only return the translation, no explanation:

{text[:4000]}"""

        response = await ai_engine.process(
            prompt,
            task_type="translate",
            provider=AIProvider.OPENAI,
            temperature=0.1,
            max_tokens=2000,
        )

        return response.content.strip()

    async def translate_if_needed(self, text: str) -> TranslationResult:
        """Translate only if text is not in English."""
        return await self.translate(text)

    def is_english(self, text: str) -> bool:
        """Quick check if text is English."""
        try:
            lang = detect(text[:1000])
            return lang == "en"
        except:
            return True  # Assume English on error


translator = Translator()


async def translate_text(
    text: str, source_lang: str | None = None
) -> TranslationResult:
    """Quick function to translate text."""
    return await translator.translate(text, source_lang)


__all__ = [
    "Translator",
    "TranslationResult",
    "translator",
    "translate_text",
]
