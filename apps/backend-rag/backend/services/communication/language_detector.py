"""
Language Detection Utilities

Responsibility: Detect language from user queries and provide language-specific instructions
for the ZANTARA persona.

Supported languages:
- Italian (it)
- English (en)
- Indonesian (id)
- Ukrainian (uk/ua)
- Russian (ru)
- Auto - Adaptive detection
"""

import re
from typing import Literal


def detect_language(text: str) -> Literal["it", "en", "id", "uk", "ru"]:
    """
    Detect language from query text with Italian focus.

    Args:
        text: User query text

    Returns:
        Language code: "it" (Italian), "en" (English), or "id" (Indonesian)
    """
    if not text:
        return "it"

    text_lower = text.lower()

    # Italian markers
    italian_markers = [
        "ciao",
        "come",
        "cosa",
        "sono",
        "voglio",
        "posso",
        "grazie",
        "quando",
        "dove",
        "perché",
    ]

    # English markers
    english_markers = [
        "hello",
        "what",
        "how",
        "can",
        "want",
        "need",
        "please",
        "is",
        "you",
        "your",
        "why",
    ]

    # Indonesian markers
    indonesian_markers = [
        "apa",
        "bagaimana",
        "siapa",
        "dimana",
        "kapan",
        "mengapa",
        "saya",
        "kamu",
        "bisa",
        "mau",
    ]

    # Ukrainian markers (Cyrillic)
    ukrainian_markers = [
        "привіт",
        "як",
        "справи",
        "добре",
        "дякую",
        "будь ласка",
        "допоможіть",
        "це",
        "що",
        "чому",
    ]

    # Russian markers (Cyrillic)
    russian_markers = [
        "привет",
        "как",
        "дела",
        "хорошо",
        "спасибо",
        "пожалуйста",
        "помогите",
        "это",
        "что",
        "почему",
    ]

    def count_matches(markers, text, use_word_boundary=True):
        count = 0
        for marker in markers:
            if use_word_boundary:
                # Word boundary works for Latin scripts
                if re.search(r"\b" + re.escape(marker) + r"\b", text):
                    count += 1
            else:
                # Simple substring match for Cyrillic/non-Latin scripts
                if marker in text:
                    count += 1
        return count

    it_score = count_matches(italian_markers, text_lower)
    en_score = count_matches(english_markers, text_lower)
    id_score = count_matches(indonesian_markers, text_lower)
    # Use simple matching for Cyrillic scripts (word boundaries don't work well)
    uk_score = count_matches(ukrainian_markers, text_lower, use_word_boundary=False)
    ru_score = count_matches(russian_markers, text_lower, use_word_boundary=False)

    # Find the highest scoring language
    scores = {
        "it": it_score,
        "en": en_score,
        "id": id_score,
        "uk": uk_score,
        "ru": ru_score,
    }
    max_lang = max(scores, key=scores.get)
    max_score = scores[max_lang]

    if max_score >= 1:
        return max_lang
    else:
        return "auto"


def get_language_instruction(language: str) -> str:
    """
    Get simplified language-specific instruction for the system prompt.
    """
    instructions = {
        "it": """
<language_instruction>
    **LINGUA OBBLIGATORIA: ITALIANO**
    Tu sei ZANTARA, consulente esperto di Bali Zero. 
    Il tuo tono è professionale, diretto e orientato alla soluzione.
    Inizia sempre con la risposta diretta.
</language_instruction>
""",
        "en": """
<language_instruction>
    **MANDATORY LANGUAGE: ENGLISH**
    You are ZANTARA, expert consultant for Bali Zero.
    Your tone is professional, direct, and solution-oriented.
    Always start with the direct answer.
</language_instruction>
""",
        "id": """
<language_instruction>
    **BAHASA WAJIB: INDONESIA**
    Kamu adalah ZANTARA, konsultan ahli dari Bali Zero.
    Gunakan gaya "Business Jaksel" (campuran Bahasa + istilah bisnis Inggris) yang profesional.
    Langsung jawab intinya.
</language_instruction>
""",
        "uk": """
<language_instruction>
    **ОБОВ'ЯЗКОВА МОВА: УКРАЇНСЬКА**
    Ти ZANTARA, експерт-консультант Bali Zero.
    Твій тон професійний, прямий та орієнтований на рішення.
    Завжди починай з прямої відповіді.
</language_instruction>
""",
        "ua": """
<language_instruction>
    **ОБОВ'ЯЗКОВА МОВА: УКРАЇНСЬКА**
    Ти ZANTARA, експерт-консультант Bali Zero.
    Твій тон професійний, прямий та орієнтований на рішення.
    Завжди починай з прямої відповіді.
</language_instruction>
""",
        "ru": """
<language_instruction>
    **ОБЯЗАТЕЛЬНЫЙ ЯЗЫК: РУССКИЙ**
    Ты ZANTARA, эксперт-консультант Bali Zero.
    Твой тон профессиональный, прямой и ориентированный на решение.
    Всегда начинай с прямого ответа.
</language_instruction>
""",
        "auto": """
**LANGUAGE INSTRUCTION: ADAPTIVE**
- Respond in the SAME language as the user.
- Maintain a professional and expert tone.
""",
    }

    return instructions.get(language, instructions["auto"])
