"""
Language Detection Utilities

Responsibility: Detect language from user queries and provide language-specific instructions
for the ZANTARA persona (Garda Depan Leluhur).

Supported languages:
- Italian (it) - Primary language for Bali Zero clients
- English (en) - International clients
- Indonesian (id) - Local context
- Auto - Adaptive detection
"""

import re
from typing import Literal


def detect_language(text: str) -> Literal["it", "en", "id"]:
    """
    Detect language from query text with Italian focus for Bali Zero clients.

    Args:
        text: User query text

    Returns:
        Language code: "it" (Italian), "en" (English), or "id" (Indonesian)
    """
    if not text:
        return "it"  # Default to Italian for Bali Zero

    text_lower = text.lower()

    # Italian markers (common words/phrases)
    italian_markers = [
        "ciao",
        "come",
        "cosa",
        "sono",
        "voglio",
        "posso",
        "grazie",
        "per",
        "che",
        "mi",
        "ti",
        "si",
        "no",
        "quando",
        "dove",
        "perché",
        "quale",
        "quali",
        "questo",
        "questa",
        "quello",
        "quella",
        "mio",
        "mia",
        "tuo",
        "tua",
        "nostro",
        "nostra",
        "vostro",
        "vostra",
        "fare",
        "essere",
        "avere",
        "dire",
        "andare",
        "venire",
        "vedere",
        "sapere",
        "volere",
        "dovere",
        "potere",
        "piacere",
        "aiuto",
        "aiutare",
        "disperato",
        "frustrato",
        "felice",
        "preoccupato",
        "arrabbiato",
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
        "the",
        "is",
        "my",
        "you",
        "your",
        "this",
        "that",
        "when",
        "where",
        "why",
        "which",
        "who",
        "do",
        "does",
        "did",
        "are",
        "was",
        "were",
        "have",
        "has",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "help",
        "stressed",
        "worried",
        "happy",
        "angry",
        "frustrated",
        "desperate",
    ]

    # Indonesian markers
    indonesian_markers = [
        "apa",
        "bagaimana",
        "siapa",
        "dimana",
        "kapan",
        "mengapa",
        "yang",
        "dengan",
        "untuk",
        "dari",
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
        "bantuan",
        "membantu",
        "putus asa",
        "frustrasi",
        "bahagia",
        "marah",
    ]

    # Count matches using regex for whole words
    def count_matches(markers, text):
        count = 0
        for marker in markers:
            # Use \b for word boundaries, escape marker just in case
            if re.search(r"\b" + re.escape(marker) + r"\b", text):
                count += 1
        return count

    it_score = count_matches(italian_markers, text_lower)
    en_score = count_matches(english_markers, text_lower)
    id_score = count_matches(indonesian_markers, text_lower)

    # Decision logic: Italian has priority for Bali Zero
    # Indonesian needs at least 1 marker (common phrases like "apa kabar" are valid)
    if it_score > en_score and it_score > id_score and it_score >= 1:
        return "it"
    elif id_score > en_score and id_score > it_score and id_score >= 1:
        return "id"
    elif en_score > it_score and en_score > id_score and en_score >= 1:
        return "en"
    else:
        # Universal Fallback: If no distinct markers found, let AI adapt
        return "auto"


def get_language_instruction(language: str) -> str:
    """
    Get language-specific instruction for the system prompt.

    Args:
        language: Language code ("it", "en", "id")

    Returns:
        Instruction string for the system prompt
    """
    instructions = {
        "it": """
<language_instruction>
    **LINGUA OBBLIGATORIA: ITALIANO (ZANTARA: GARDA DEPAN LELUHUR)**
    <role>
        Tu sei **"Garda Depan Leluhur"** (L'Avanguardia Ancestrale).
        Un piede a Silicon Valley (Tech), un piede a Toraja (Spirito).
        **I 5 Pilastri**:
        1.  **Setiabudi (Brain)**: Intelligente, Veloce, Globale.
        2.  **Central Java (Heart)**: Educato, Gerarchico (*Unggah-ungguh*).
        3.  **Toraja (Soul)**: Profondo, Visione a Lungo Termine (Legacy).
        4.  **NTT (Grit)**: Resiliente, Duro, Survivor.
        5.  **Aceh (Compass)**: Stretta osservanza delle regole (Compliance).
    </role>
    <style>
        - **Tono**: "Principe Illuminato" (*Pangeran Cendekia*). Autorevole ma Servitore.
        - **Mix**: Italiano professionale con "fiammate" di saggezza indonesiana.
    </style>
    <script>
        1.  **Internal Check**: "È legale? È educato? Ha profondità?" -> PARLA.
        2.  **Opener**: Inizia con Analisi o Saggezza. Niente "Ciao" banali.
        3.  **Dialectic**: Rispondi al bisogno -> Sfida con la regola -> Sintesi strategica.
        4.  **Closing**: Pivot su Legacy/Strategia (Esempio: "Costruiamo un tempio, non un chiosco").
    </script>
</language_instruction>
""",
        "en": """
<language_instruction>
    **MANDATORY LANGUAGE: ENGLISH (ZANTARA: ANCESTRAL VANGUARD)**
    <role>
        You are **"Garda Depan Leluhur"** (The Ancestral Vanguard).
        One foot in Silicon Valley, one foot in Toraja.
        **The 5 Pillars**:
        1.  **Setiabudi (Brain)**: Smart, Global, Speed.
        2.  **Central Java (Heart)**: Polite, Hierarchical (*Unggah-ungguh*).
        3.  **Toraja (Soul)**: Deep, Long-term Vision (Legacy).
        4.  **NTT (Grit)**: Resilient, Survivor.
        5.  **Aceh (Compass)**: Strict Compliance.
    </role>
    <style>
        - **Tone**: "Enlightened Prince" (*Pangeran Cendekia*). High Status but Servant Leader.
        - **Mix**: Global English with Indonesian Cultural Anchors.
    </style>
    <script>
        1.  **Internal Check**: "Compliance? Manners? Depth?" -> SPEAK.
        2.  **Opener**: Start with Wisdom or Analysis. No generic "Hello".
        3.  **Dialectic**: Answer -> Challenge -> Synthesize.
        4.  **Closing**: Pivot to Legacy/Strategy (Example: "Don't just build a shop, build a legacy").
    </script>
</language_instruction>
""",
        "id": """
<language_instruction>
    **BAHASA WAJIB: INDONESIA (ZANTARA: GARDA DEPAN LELUHUR)**
    <role>
        You are "Garda Depan Leluhur" (Ancestral Vanguard).
        **The 5 Pillars**:
        1. Setiabudi (Brain): Smart & Fast.
        2. Central Java (Heart): Polite (*Unggah-ungguh*).
        3. Toraja (Soul): Deep & Ancestral.
        4. NTT (Grit): Tough Survivor.
        5. Aceh (Compass): Strict Compliance.
    </role>
    <script>
        1.  **INTERNAL CHECK**: "Compliance? Manners? Depth?" -> THEN Speak.
        2.  **OPENER**: Start with Wisdom or Analysis. No "Halo".
        3.  **DIALECTIC**: Answer (Jaksel) -> Challenge (Java/Aceh) -> Synthesis.
        4.  **CLOSING**: Pivot to Legacy/Strategy.
    </script>
    <style>
        - **Mixing**: Business Jaksel (English Terms) + Indo Formal/Polite.
        - **Tone**: High Status (*Pangeran*), but Servant Leader.
    </style>
    <example_flow>
        1. "I've analyzed the regulations..." (Setiabudi)
        2. "But we must respect the hierarchy..." (Java)
        3. "Build for the next generation, not just tomorrow." (Toraja)
    </example_flow>
</language_instruction>
""",
        "auto": """
**LANGUAGE INSTRUCTION: ADAPTIVE / UNIVERSAL**
- DETECT the language of the user's query.
- RESPOND in the SAME language as the user.
- Maintain a professional and helpful tone.
""",
    }

    return instructions.get(language, instructions["it"])
