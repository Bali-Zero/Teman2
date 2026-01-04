import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, mock_open, patch

import pytest


class DummyFiles:
    def __init__(self, results):
        self._results = results
        self._index = 0

    def list(self, **_kwargs):
        return self

    def execute(self):
        result = self._results[self._index]
        self._index += 1
        return result

    def get_media(self, fileId):
        return f"request:{fileId}"


class DummyService:
    def __init__(self, results):
        self._files = DummyFiles(results)

    def files(self):
        return self._files


class DummyDownloader:
    def __init__(self, stream, request):
        self._stream = stream
        self._request = request
        self._done = False

    def next_chunk(self):
        if not self._done:
            self._stream.write(b"pdf")
            self._done = True
        return (None, self._done)


def _load_module(
    *,
    settings_overrides=None,
    genai_available=True,
    genai_present=True,
    genai_client_available=True,
    genai_text="answer",
):
    settings = SimpleNamespace(
        google_credentials_json=json.dumps({"key": "value"}),
        google_api_key="key",
    )
    if settings_overrides:
        for key, value in settings_overrides.items():
            setattr(settings, key, value)

    app_module = types.ModuleType("app")
    app_core_module = types.ModuleType("app.core")
    app_config_module = types.ModuleType("app.core.config")
    app_config_module.settings = settings

    service_account_module = types.ModuleType("google.oauth2.service_account")

    class Credentials:
        @classmethod
        def from_service_account_info(cls, info, scopes=None):
            return "creds"

    service_account_module.Credentials = Credentials

    google_oauth2_module = types.ModuleType("google.oauth2")

    discovery_module = types.ModuleType("googleapiclient.discovery")
    discovery_module.build = lambda *args, **kwargs: None

    http_module = types.ModuleType("googleapiclient.http")
    http_module.MediaIoBaseDownload = DummyDownloader

    llm_module = types.ModuleType("llm")
    genai_client_module = types.ModuleType("llm.genai_client")

    class GenAIClient:
        def __init__(self, api_key=None):
            self.is_available = genai_client_available
            self._auth_method = "api_key"

        async def generate_content(self, contents, model, max_output_tokens):
            return {"text": genai_text}

    def get_genai_client():
        return GenAIClient()

    genai_client_module.GENAI_AVAILABLE = genai_available
    genai_client_module.GenAIClient = GenAIClient
    genai_client_module.get_genai_client = get_genai_client

    if genai_present:

        class Client:
            def __init__(self, api_key=None):
                self.files = self

            def upload(self, file):
                return SimpleNamespace(uri="file://uri", mime_type="application/pdf")

        genai_client_module.genai = types.SimpleNamespace(Client=Client)
    else:
        genai_client_module.genai = None

    sys.modules.update(
        {
            "app": app_module,
            "app.core": app_core_module,
            "app.core.config": app_config_module,
            "google.oauth2": google_oauth2_module,
            "google.oauth2.service_account": service_account_module,
            "googleapiclient.discovery": discovery_module,
            "googleapiclient.http": http_module,
            "llm": llm_module,
            "llm.genai_client": genai_client_module,
        }
    )

    module_path = (
        Path(__file__).resolve().parents[4] / "backend" / "services" / "oracle" / "smart_oracle.py"
    )
    spec = importlib.util.spec_from_file_location("services.oracle.smart_oracle", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_get_drive_service_missing_creds():
    module = _load_module(settings_overrides={"google_credentials_json": None})
    assert module.get_drive_service() is None


def test_get_drive_service_success():
    module = _load_module()
    service = object()
    module.build = lambda *args, **kwargs: service
    assert module.get_drive_service() is service


def test_get_drive_service_invalid_json_fallback():
    module = _load_module(settings_overrides={"google_credentials_json": "not-json"})
    service = object()
    module.build = lambda *args, **kwargs: service
    assert module.get_drive_service() is service


def test_download_pdf_success_primary_query():
    module = _load_module()
    service = DummyService([{"files": [{"id": "1", "name": "doc.pdf"}]}])
    module.get_drive_service = lambda: service
    module.MediaIoBaseDownload = DummyDownloader

    with patch("builtins.open", mock_open()) as open_file:
        path = module.download_pdf_from_drive("doc.pdf")

    assert path == "/tmp/doc.pdf"
    open_file.assert_called_once()


def test_download_pdf_success_alt_query():
    module = _load_module()
    service = DummyService([{"files": []}, {"files": [{"id": "1", "name": "doc.pdf"}]}])
    module.get_drive_service = lambda: service
    module.MediaIoBaseDownload = DummyDownloader
    with patch("builtins.open", mock_open()):
        path = module.download_pdf_from_drive("doc_name.pdf")
    assert path == "/tmp/doc.pdf"


def test_download_pdf_none_when_service_missing():
    module = _load_module()
    module.get_drive_service = lambda: None
    assert module.download_pdf_from_drive("doc.pdf") is None


@pytest.mark.asyncio
async def test_smart_oracle_no_pdf():
    module = _load_module()
    module.download_pdf_from_drive = lambda *_a, **_k: None
    result = await module.smart_oracle("q", "file.pdf")
    assert "Original document not found" in result


@pytest.mark.asyncio
async def test_smart_oracle_genai_unavailable():
    module = _load_module()
    module.download_pdf_from_drive = lambda *_a, **_k: "/tmp/doc.pdf"
    module._genai_client = SimpleNamespace(is_available=False)
    result = await module.smart_oracle("q", "file.pdf")
    assert "AI service not available" in result


@pytest.mark.asyncio
async def test_smart_oracle_sdk_missing():
    module = _load_module(genai_present=False)
    module.download_pdf_from_drive = lambda *_a, **_k: "/tmp/doc.pdf"
    module._genai_client = SimpleNamespace(is_available=True, generate_content=AsyncMock())
    result = await module.smart_oracle("q", "file.pdf")
    assert result == "GenAI SDK not available."


@pytest.mark.asyncio
async def test_smart_oracle_success_removes_file():
    module = _load_module(genai_text="answer")
    module.download_pdf_from_drive = lambda *_a, **_k: "/tmp/doc.pdf"
    module._genai_client = SimpleNamespace(
        is_available=True, generate_content=AsyncMock(return_value={"text": "answer"})
    )

    with patch("os.remove") as remove_file:
        result = await module.smart_oracle("q", "file.pdf")

    assert result == "answer"
    remove_file.assert_called_once_with("/tmp/doc.pdf")


@pytest.mark.asyncio
async def test_smart_oracle_ai_error():
    module = _load_module()
    module.download_pdf_from_drive = lambda *_a, **_k: "/tmp/doc.pdf"
    module._genai_client = SimpleNamespace(
        is_available=True, generate_content=AsyncMock(side_effect=RuntimeError("boom"))
    )
    result = await module.smart_oracle("q", "file.pdf")
    assert result == "Error processing the document with AI."


def test_drive_connection_success():
    module = _load_module()
    service = DummyService([{"files": [{"id": "1", "name": "doc.pdf", "mimeType": "pdf"}]}])
    module.get_drive_service = lambda: service
    assert module.test_drive_connection() is True


def test_drive_connection_failure():
    module = _load_module()
    module.get_drive_service = lambda: None
    assert module.test_drive_connection() is False


def test_get_drive_service_invalid_json_fallback_exception():
    """Test get_drive_service when json.loads fails and build also fails (lines 63-64)"""
    module = _load_module(settings_overrides={"google_credentials_json": "invalid-json"})
    # Mock build to raise exception on first call, and also on fallback
    call_count = [0]

    def failing_build(*args, **kwargs):
        call_count[0] += 1
        raise RuntimeError("build failed")

    module.build = failing_build
    result = module.get_drive_service()
    assert result is None
    assert call_count[0] >= 1  # build was called at least once


def test_download_pdf_no_files_found():
    """Test download_pdf_from_drive when no files found after all queries (lines 114-115)"""
    module = _load_module()
    service = DummyService([{"files": []}, {"files": []}])  # Both queries return empty
    module.get_drive_service = lambda: service
    result = module.download_pdf_from_drive("nonexistent.pdf")
    assert result is None


def test_download_pdf_exception_handling():
    """Test download_pdf_from_drive exception handling (lines 136-138)"""
    module = _load_module()
    service = DummyService([RuntimeError("drive error")])  # Execute raises exception
    module.get_drive_service = lambda: service
    result = module.download_pdf_from_drive("error.pdf")
    assert result is None


def test_drive_connection_exception_handling():
    """Test test_drive_connection exception handling (lines 223-225)"""
    module = _load_module()
    service = DummyService([RuntimeError("connection error")])  # Execute raises exception
    module.get_drive_service = lambda: service
    result = module.test_drive_connection()
    assert result is False
