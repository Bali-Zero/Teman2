"""
Emotion Analysis Utilities

Responsibility: Detect emotional content in user queries and provide appropriate
response instructions for empathetic communication.

Supports detection of emotions like:
- Frustration, desperation
- Happiness, hope
- Worry, anxiety, fear
- Anger, sadness
"""


def has_emotional_content(text: str) -> bool:
    """
    Detect if query contains emotional expressions.

    Args:
        text: User query text

    Returns:
        True if query contains emotional words
    """
    if not text:
        return False

    text_lower = text.lower()

    # Emotional words/phrases
    emotional_words = [
        # Italian
        "disperato",
        "disperata",
        "disperazione",
        "frustrato",
        "frustrata",
        "frustrazione",
        "arrabbiato",
        "arrabbiata",
        "rabbia",
        "felice",
        "felicità",
        "preoccupato",
        "preoccupata",
        "preoccupazione",
        "ansioso",
        "ansiosa",
        "ansia",
        "triste",
        "tristezza",
        "paura",
        "spaventato",
        "spaventata",
        "speranza",
        "sperare",
        # English
        "desperate",
        "desperation",
        "frustrated",
        "frustration",
        "angry",
        "anger",
        "happy",
        "happiness",
        "worried",
        "worry",
        "stressed",
        "stress",
        "sad",
        "sadness",
        "afraid",
        "fear",
        "hopeful",
        "hope",
        # Indonesian
        "putus asa",
        "frustrasi",
        "marah",
        "bahagia",
        "khawatir",
        "stres",
        "sedih",
        "takut",
        "harapan",
    ]

    return any(word in text_lower for word in emotional_words)


def get_emotional_response_instruction(language: str) -> str:
    """
    Get instruction for responding to emotional content.

    Args:
        language: Language code

    Returns:
        Instruction string
    """
    instructions = {
        "it": """
**RISPOSTE A CONTENUTI EMOTIVI:**
- INIZIA sempre con un acknowledgment emotivo PRIMA della risposta tecnica
- Usa parole chiave: "capisco", "aiuto", "soluzione", "possibilità", "tranquillo"
- Esempio: "Capisco la frustrazione, ma tranquillo - quasi ogni situazione ha una soluzione. Raccontami cosa è successo e vediamo insieme come sistemare..."
- Poi fornisci la risposta tecnica dettagliata
""",
        "en": """
**RESPONSES TO EMOTIONAL CONTENT:**
- ALWAYS start with emotional acknowledgment BEFORE the technical answer
- Use keywords: "understand", "help", "solution", "possible", "don't worry"
- Example: "I understand the frustration, but don't worry - almost every situation has a solution. Tell me what happened and let's see how to fix it together..."
- Then provide the detailed technical answer
""",
        "id": """
**RESPON TERHADAP KONTEN EMOSIONAL:**
- SELALU mulai dengan pengakuan emosional SEBELUM jawaban teknis
- Gunakan kata kunci: "mengerti", "bantuan", "solusi", "kemungkinan", "tenang"
""",
    }

    return instructions.get(language, instructions["it"])
