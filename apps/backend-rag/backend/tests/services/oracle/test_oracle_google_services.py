import pytest

from backend.services.oracle.oracle_google_services import GoogleServices


def test_google_services_start_uninitialized() -> None:
    services = GoogleServices()

    assert services._gemini_initialized is False
    assert services._drive_service is None
    assert services._genai_client is None


def test_get_model_name_strips_models_prefix() -> None:
    services = GoogleServices()

    assert services.get_model_name("models/gemini-2.0-flash-lite") == "gemini-2.0-flash-lite"
    assert services.get_model_name("gemini-2.0-flash-lite") == "gemini-2.0-flash-lite"


def test_gemini_model_helpers_require_initialized_client() -> None:
    services = GoogleServices()

    with pytest.raises(RuntimeError, match="Gemini AI not initialized"):
        services.get_gemini_model_name()

    with pytest.raises(RuntimeError, match="Gemini AI not initialized"):
        services.get_zantara_model_name()


def test_model_helpers_return_flash_lite_for_supported_use_cases() -> None:
    services = GoogleServices()
    services._gemini_initialized = True

    assert services.get_gemini_model_name("models/gemini-2.0-flash-lite") == (
        "gemini-2.0-flash-lite"
    )
    assert services.get_zantara_model_name("legal_reasoning") == "gemini-2.0-flash-lite"
    assert services.get_zantara_model_name("unknown") == "gemini-2.0-flash-lite"


def test_properties_call_lazy_initializer(monkeypatch: pytest.MonkeyPatch) -> None:
    services = GoogleServices()

    def fake_initialize() -> None:
        services._gemini_initialized = True
        services._drive_service = object()
        services._genai_client = object()  # type: ignore[assignment]

    monkeypatch.setattr(services, "_ensure_services_initialized", fake_initialize)

    assert services.gemini_available is True
    assert services.drive_service is not None
    assert services.genai_client is not None
