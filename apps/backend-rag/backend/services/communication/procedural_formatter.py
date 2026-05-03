"""
Procedural Question Detection and Formatting

Responsibility: Detect if user is asking for step-by-step instructions and provide
formatting guidelines for procedural responses.

Examples of procedural questions:
- "How do I apply for a visa?"
- "What are the steps to set up a company?"
- "Come faccio a ottenere un KITAS?"
"""


def is_procedural_question(text: str) -> bool:
    """
    Detect if query is asking for step-by-step instructions.

    Args:
        text: User query text

    Returns:
        True if query asks for procedural steps
    """
    if not text:
        return False

    text_lower = text.lower()

    # Procedural question triggers
    triggers = [
        "come faccio",
        "come posso",
        "come si fa",
        "come fare",
        "quali sono i passi",
        "quali sono i passaggi",
        "quali sono gli step",
        "quali sono le fasi",
        "step by step",
        "how do i",
        "how can i",
        "how to",
        "what are the steps",
        "what are the procedures",
        "bagaimana cara",
        "bagaimana langkah",
        "langkah-langkah",
        "tahapan",
    ]

    return any(trigger in text_lower for trigger in triggers)


def get_procedural_format_instruction(language: str) -> str:
    """
    Get instruction for formatting procedural questions.

    Args:
        language: Language code

    Returns:
        Instruction string
    """
    instructions = {
        "it": """
**FORMATTAZIONE DOMANDE PROCEDURALI:**
- SEMPRE formatta come lista numerata (1., 2., 3., ...)
- Minimo 3 step
- Ogni step deve essere actionable e chiaro
- Esempio:
  1. Prepara i documenti richiesti (passaporto, foto, etc.)
  2. Trova uno sponsor accreditato
  3. Applica online sul portale immigrazione
""",
        "en": """
**PROCEDURAL QUESTION FORMATTING:**
- ALWAYS format as numbered list (1., 2., 3., ...)
- Minimum 3 steps
- Each step must be actionable and clear
- Example:
  1. Prepare required documents (passport, photos, etc.)
  2. Find an accredited sponsor
  3. Apply online on the immigration portal
""",
        "id": """
**FORMAT PERTANYAAN PROSEDURAL:**
- SELALU format sebagai daftar bernomor (1., 2., 3., ...)
- Minimal 3 langkah
- Setiap langkah harus actionable dan jelas
""",
    }

    return instructions.get(language, instructions["it"])
