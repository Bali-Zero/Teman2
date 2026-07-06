from backend.services.oracle.language_detector import LanguageDetectionService


def test_detect_language_identifies_italian_with_multiple_markers() -> None:
    service = LanguageDetectionService()

    assert service.detect_language("Ciao, vorrei capire quanto costa il KITAS") == "it"


def test_detect_language_identifies_indonesian_with_multiple_markers() -> None:
    service = LanguageDetectionService()

    assert service.detect_language("Apa yang saya perlu untuk visa?") == "id"


def test_detect_language_defaults_to_english_for_weak_signal() -> None:
    service = LanguageDetectionService()

    assert service.detect_language("KITAS pricing update") == "en"


def test_get_target_language_priority_override_then_user_then_detection() -> None:
    service = LanguageDetectionService()

    assert service.get_target_language("plain query", language_override="id") == "id"
    assert service.get_target_language("plain query", user_language="it") == "it"
    assert service.get_target_language("Ciao, vorrei sapere il costo") == "it"
