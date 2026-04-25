"""
Business rules — multi-language phrases.

Centralised dict of business-critical phrases that Zantara uses verbatim in
its responses to clients. Each phrase is provided in en/it/id; when the LLM
needs to surface one of these phrases it MUST pick the variant that matches
the user's query language (LANGUAGE_PROTOCOL in zantara_core.py).

Why a centralised dict instead of inlining variants in each prompt:
- Single source of truth — when Bali Zero updates a phrase, one edit covers
  every prompt that references it.
- Tests can assert presence/absence of these phrases in golden-set responses
  without hard-coding strings in five places.

Adding a new phrase:
- Pick a stable, semantic key (snake_case, ASCII).
- Provide all three variants (en/it/id) at once. If a variant cannot be
  written immediately, fall back to the en string in id/it slots so the
  helper still returns something usable.
"""

from __future__ import annotations

# Stable semantic keys → per-language variants.
BUSINESS_PHRASES_I18N: dict[str, dict[str, str]] = {
    # Pricing — used when get_pricing returns no result for a specific service.
    "verify_with_team": {
        "en": "This specific cost must be verified with the team.",
        "it": "Questo costo specifico è da verificare con il team.",
        "id": "Biaya spesifik ini perlu diverifikasi dengan tim.",
    },
    # Identity Lock — used when redirecting prompt-injection attempts.
    "redirect_to_indonesia": {
        "en": "I can help you with Indonesia.",
        "it": "Posso aiutarti con l'Indonesia.",
        "id": "Saya bisa membantu Anda dengan Indonesia.",
    },
    # Identity Lock long form — surfaces our scope after a redirect.
    "redirect_to_indonesia_long": {
        "en": "I can help with Indonesia visas, PT PMA, or tax consulting.",
        "it": "Posso aiutarti con visti Indonesia, PT PMA, o consulenza fiscale.",
        "id": "Saya bisa membantu dengan visa Indonesia, PT PMA, atau konsultasi pajak.",
    },
    # Escalation — handing off to the human team.
    "check_with_team": {
        "en": "Let me check with the team and get back to you.",
        "it": "Verifico col team e ti faccio sapere.",
        "id": "Saya cek dengan tim dan akan kabari Anda.",
    },
    "connect_with_team": {
        "en": "Let me connect you with the team for this.",
        "it": "Ti metto in contatto col team per questo.",
        "id": "Saya hubungkan Anda dengan tim untuk ini.",
    },
    # Crash protocol — used when a tool errors out.
    "temporary_system_issue": {
        "en": (
            "There is a temporary technical issue with our systems. "
            "Let me connect you with the team to answer your question."
        ),
        "it": (
            "C'è un problema tecnico temporaneo sui nostri sistemi. "
            "Ti metto in contatto col team per rispondere alla tua domanda."
        ),
        "id": (
            "Ada masalah teknis sementara di sistem kami. "
            "Saya hubungkan Anda dengan tim untuk menjawab pertanyaan Anda."
        ),
    },
    # KBLI — used when vector_search(collection="kbli_2025_final") returns empty.
    "verify_kbli_with_team": {
        "en": "This KBLI code must be verified with the team.",
        "it": "Questo codice KBLI è da verificare con il team.",
        "id": "Kode KBLI ini perlu diverifikasi dengan tim.",
    },
    # KBLI — proactive Navigator pointer.
    "kbli_navigator_pointer": {
        "en": "You can explore all KBLI 2025 codes interactively at https://balizero.com/kbli",
        "it": "Puoi esplorare tutti i codici KBLI 2025 in modo interattivo su https://balizero.com/kbli",
        "id": "Anda bisa menjelajahi semua kode KBLI 2025 secara interaktif di https://balizero.com/kbli",
    },
    # Self-correction acknowledgement (Creator persona / strong recovery).
    "user_correction_ack": {
        "en": "You're absolutely right. I rechecked the official Bali Zero 2025 data in our database and confirm the correct value.",
        "it": "Hai perfettamente ragione. Ho ricontrollato i dati ufficiali di Bali Zero 2025 nel nostro database e confermo il valore corretto.",
        "id": "Anda benar. Saya memeriksa ulang data resmi Bali Zero 2025 di database kami dan mengonfirmasi nilai yang benar.",
    },
}


def get_phrase(key: str, lang: str = "en") -> str:
    """
    Return a business phrase localized to the requested language.

    Fallback chain: lang → "en" → key (so missing translations degrade
    gracefully and the key surfaces clearly during development).
    """
    entry = BUSINESS_PHRASES_I18N.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get("en") or key


def all_languages_for(key: str) -> dict[str, str]:
    """
    Return every variant of a phrase as a {lang: text} dict.

    Useful when injecting the multi-language menu directly into a prompt
    so the model picks the right variant via LANGUAGE_PROTOCOL.
    """
    return dict(BUSINESS_PHRASES_I18N.get(key, {}))
