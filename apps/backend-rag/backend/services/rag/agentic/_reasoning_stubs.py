"""
Localized stub messages for the ReAct reasoning engine.

Pulled out of ``reasoning.py`` (refactor/split-reasoning) so the stub
table is a single source of truth, separate from the reasoning logic.

Public API:
    - STUB_MESSAGES: dict[key, dict[language, text]] — the full table.
    - get_localized_stub: resolve a (key, language) pair with fallback
      order Requested Language → ENGLISH → generic hardcoded message.
"""

from __future__ import annotations

_FALLBACK_MESSAGE = "I'm sorry, I cannot fulfill this request."

STUB_MESSAGES: dict[str, dict[str, str]] = {
    "abstain": {
        "ITALIAN": (
            "Mi dispiace, non ho trovato informazioni rilevanti per questa domanda."
        ),
        "INDONESIAN": (
            "Maaf, saya tidak menemukan informasi yang relevan untuk pertanyaan ini."
        ),
        "ENGLISH": (
            "I'm sorry, I couldn't find relevant information for this question."
        ),
    },
    "abstain_detailed": {
        "ITALIAN": (
            "Per questa domanda specifica non ho informazioni verificate sufficienti nei documenti ufficiali.\n\n"
            "Posso aiutarti con:\n"
            "• Informazioni su visti e KITAS\n"
            "• Setup aziendale (PT PMA)\n"
            "• Questioni fiscali e legali\n"
            "• Procedure e documentazione\n\n"
            "Prova a riformulare la domanda o chiedi qualcosa di più specifico!"
        ),
        "INDONESIAN": (
            "Untuk pertanyaan spesifik ini, saya tidak memiliki informasi terverifikasi yang cukup dalam dokumen resmi.\n\n"
            "Saya dapat membantu Anda dengan:\n"
            "• Informasi visa dan KITAS\n"
            "• Pendirikan perusahaan (PT PMA)\n"
            "• Masalah perpajakan dan hukum\n"
            "• Prosedur dan dokumentasi\n\n"
            "Coba reformulasikan pertanyaan atau tanyakan sesuatu yang lebih spesifik!"
        ),
        "ENGLISH": (
            "For this specific question, I don't have sufficient verified information in the official documents.\n\n"
            "I can help you with:\n"
            "• Visa and KITAS information\n"
            "• Company setup (PT PMA)\n"
            "• Tax and legal matters\n"
            "• Procedures and documentation\n\n"
            "Try rephrasing the question or ask something more specific!"
        ),
    },
    "error": {
        "ITALIAN": (
            "Mi dispiace, non sono riuscito a completare la richiesta. Riprova."
        ),
        "INDONESIAN": (
            "Maaf, saya tidak dapat menyelesaikan permintaan tersebut. Silakan coba lagi."
        ),
        "ENGLISH": (
            "I'm sorry, I couldn't complete the request. Please try again."
        ),
    },
    "confused": {
        "ITALIAN": (
            "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla? "
            "Posso aiutarti con visti, aziende e leggi in Indonesia."
        ),
        "INDONESIAN": (
            "Maaf, saya tidak mengerti permintaan Anda. Bisakah Anda merumuskannya kembali? "
            "Saya dapat membantu Anda dengan visa, perusahaan, dan hukum di Indonesia."
        ),
        "ENGLISH": (
            "I'm sorry, I didn't quite understand your request. Could you rephrase it? "
            "I can help you with visas, companies, and laws in Indonesia."
        ),
    },
}


def get_localized_stub(key: str, language: str) -> str:
    """Resolve (key, language) → stub text.

    Fallback order: requested language → ENGLISH → generic hardcoded message.
    Returns the generic message if the key itself is unknown.
    """
    lang_stubs = STUB_MESSAGES.get(key, {})
    return lang_stubs.get(language, lang_stubs.get("ENGLISH", _FALLBACK_MESSAGE))
