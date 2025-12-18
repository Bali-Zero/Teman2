"""
Explanation Level Detection Service

Detects user intent for explanation level (simple/expert/standard) and alternative requests.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Triggers for simple explanations
SIMPLIFY_TRIGGERS = [
    "bambino",
    "semplice",
    "facile",
    "non capisco",
    "explain simply",
    "spiegami come",
    "come se fossi",
    "in modo semplice",
    "easy",
    "simple",
    "dumb it down",
    "plain language",
]

# Triggers for expert explanations
EXPERT_TRIGGERS = [
    "esperto",
    "tecnico",
    "dettagli",
    "specifico",
    "professional",
    "avvocato",
    "commercialista",
    "legalmente",
    "normativa",
    "regolamento",
    "spiegazione tecnica",
    "consulenza tecnica",
    "expert",
    "technical",
    "detailed",
    "specific",
    "legally",
    "regulation",
]

# Triggers for alternative requests
ALTERNATIVES_TRIGGERS = [
    "alternative",
    "altre opzioni",
    "invece di",
    "al posto di",
    "non posso permettermi",
    "non ho i soldi",
    "troppo caro",
    "meno costoso",
    "più economico",
    "alternatives",
    "other options",
    "instead of",
    "can't afford",
    "too expensive",
    "cheaper",
    "more affordable",
    "opsi lain",
    "alternatif",
]


def detect_explanation_level(query: str) -> Literal["simple", "standard", "expert"]:
    """
    Detect the requested explanation level from user query.

    Args:
        query: User query text

    Returns:
        "simple", "standard", or "expert"
    """
    query_lower = query.lower()

    # Check for simple triggers first (higher priority)
    if any(trigger in query_lower for trigger in SIMPLIFY_TRIGGERS):
        logger.info(f"Detected SIMPLE explanation level for query: {query[:50]}...")
        return "simple"

    # Check for expert triggers
    if any(trigger in query_lower for trigger in EXPERT_TRIGGERS):
        logger.info(f"Detected EXPERT explanation level for query: {query[:50]}...")
        return "expert"

    # Default to standard
    return "standard"


def needs_alternatives_format(query: str) -> bool:
    """
    Detect if user is asking for alternatives.

    Args:
        query: User query text

    Returns:
        True if user is asking for alternatives
    """
    query_lower = query.lower()

    has_alternative_trigger = any(trigger in query_lower for trigger in ALTERNATIVES_TRIGGERS)

    if has_alternative_trigger:
        logger.info(f"Detected ALTERNATIVES request for query: {query[:50]}...")

    return has_alternative_trigger


def build_explanation_instructions(level: Literal["simple", "standard", "expert"]) -> str:
    """
    Build explanation level instructions for the prompt.

    Args:
        level: Explanation level

    Returns:
        Instruction string for the prompt
    """
    if level == "simple":
        return """
### EXPLANATION LEVEL: SIMPLE
- Use basic vocabulary (avoid technical jargon)
- Use analogies and concrete examples
- Explain concepts step-by-step
- Use everyday language
- If explaining KITAS: "È come un permesso speciale per stare in Indonesia..."
- If explaining PT PMA: "È come aprire una società in Indonesia..."
"""
    elif level == "expert":
        return """
### EXPLANATION LEVEL: EXPERT
- Use technical terminology (KITAS, NIB, NPWP, etc.)
- Reference specific regulations and laws
- Include legal citations when relevant
- Provide detailed procedures and requirements
- Mention specific government agencies (BKPM, Ditjen Imigrasi, etc.)
"""
    else:  # standard
        return """
### EXPLANATION LEVEL: STANDARD
- Balanced explanation: clear but informative
- Use technical terms with brief explanations
- Provide practical examples
- Include relevant details without overwhelming
"""


def build_alternatives_instructions() -> str:
    """
    Build instructions for alternative requests format.

    Returns:
        Instruction string for numbered list format
    """
    return """
### FORMAT REQUIREMENT: ALTERNATIVES REQUEST
The user is asking for alternatives. You MUST format your response as a numbered list:

1) [Option Name] - [Brief description] - [Key benefit]
2) [Option Name] - [Brief description] - [Key benefit]
3) [Option Name] - [Brief description] - [Key benefit]

Example:
1) Digital Nomad con E33G - lavori da remoto legalmente - nessun investimento minimo
2) Partnership con indonesiano via PT Lokal - lui è il proprietario, tu consulente - costi ridotti
3) Freelance con visto B211 - progetti a breve termine - flessibilità temporale

DO NOT use bullet points (-) or paragraphs. Use ONLY numbered list format (1), 2), 3)).
"""
