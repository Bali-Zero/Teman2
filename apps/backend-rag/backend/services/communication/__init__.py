"""
Communication utilities for response formatting and analysis.

This package provides utilities for:
- Language detection and language-specific instructions
- Emotional content detection and empathetic response formatting
- Procedural question detection and step-by-step formatting
- Domain-specific formatting (Visa, Tax, Company)
- Explanation level detection (simple, standard, expert)

This module maintains backward compatibility with the original communication_utils module
by re-exporting all functions from the focused sub-modules.

Example usage:
    from services.communication import detect_language, has_emotional_content

    language = detect_language(query)
    if has_emotional_content(query):
        instruction = get_emotional_response_instruction(language)
"""

# Language detection and instructions
# Domain formatting
from .domain_formatter import get_domain_format_instruction

# Emotion analysis
from .emotion_analyzer import get_emotional_response_instruction, has_emotional_content

# Explanation level detection
from .explanation_detector import (
    build_alternatives_instructions,
    build_explanation_instructions,
    detect_explanation_level,
    needs_alternatives_format,
)
from .language_detector import detect_language, get_language_instruction

# Procedural formatting
from .procedural_formatter import get_procedural_format_instruction, is_procedural_question

__all__ = [
    # Language detection
    "detect_language",
    "get_language_instruction",
    # Emotion analysis
    "has_emotional_content",
    "get_emotional_response_instruction",
    # Procedural formatting
    "is_procedural_question",
    "get_procedural_format_instruction",
    # Domain formatting
    "get_domain_format_instruction",
    # Explanation level
    "detect_explanation_level",
    "needs_alternatives_format",
    "build_explanation_instructions",
    "build_alternatives_instructions",
]
