"""
Fallback Messages - Localized error messages

Centralized fallback messages for error scenarios.
"""

# Fallback messages by language
FALLBACK_MESSAGES = {
    "it": {
        "connection_error": (
            "Mi scusi, ho riscontrato un problema di connessione. "
            "Provi tra qualche istante o contatti il supporto."
        ),
        "service_unavailable": ("Mi scusi, il servizio non è disponibile. Contatti il supporto."),
        "api_key_error": (
            "Mi scusi, c'è un problema con la configurazione del servizio AI. "
            "Il team tecnico è stato notificato. Provi più tardi."
        ),
        "generic_error": "Mi scusi, ho riscontrato un problema. Provi più tardi.",
    },
    "en": {
        "connection_error": (
            "Sorry, we encountered a connection issue. "
            "Please try again in a moment or contact support."
        ),
        "service_unavailable": (
            "Sorry, the service is currently unavailable. Please contact support."
        ),
        "api_key_error": (
            "Sorry, there's an issue with the AI service configuration. "
            "The technical team has been notified. Please try again later."
        ),
        "generic_error": "Sorry, we encountered an issue. Please try again later.",
    },
    "id": {
        "connection_error": (
            "Maaf, kami mengalami masalah koneksi. "
            "Silakan coba lagi sebentar lagi atau hubungi dukungan."
        ),
        "service_unavailable": ("Maaf, layanan tidak tersedia saat ini. Silakan hubungi dukungan."),
        "api_key_error": (
            "Maaf, ada masalah dengan konfigurasi layanan AI. "
            "Tim teknis telah diberitahu. Silakan coba lagi nanti."
        ),
        "generic_error": "Maaf, kami mengalami masalah. Silakan coba lagi nanti.",
    },
}


def get_fallback_message(message_type: str, language: str = "en") -> str:
    """
    Get localized fallback message.

    Args:
        message_type: Type of message ('connection_error', 'service_unavailable', 'generic_error')
        language: Language code ('it', 'en', 'id')

    Returns:
        Localized message string
    """
    lang_messages = FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["en"])
    return lang_messages.get(message_type, FALLBACK_MESSAGES["en"]["generic_error"])
