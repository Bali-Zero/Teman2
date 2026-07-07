from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.core import config as core_config

smart_module = importlib.import_module("backend.services.oracle.smart_oracle")


class FakeFilesResource:
    def __init__(self, files_by_call: list[list[dict[str, str]]] | None = None) -> None:
        self.files_by_call = files_by_call or [
            [{"id": "file-1", "name": "Permit Guide.pdf", "mimeType": "application/pdf"}],
        ]
        self.list_calls: list[dict[str, Any]] = []
        self.media_file_id: str | None = None

    def list(self, **kwargs: Any) -> SimpleNamespace:
        self.list_calls.append(kwargs)
        files = self.files_by_call[min(len(self.list_calls) - 1, len(self.files_by_call) - 1)]
        return SimpleNamespace(execute=lambda: {"files": files})

    def get_media(self, *, fileId: str) -> object:
        self.media_file_id = fileId
        return object()


class FakeDriveService:
    def __init__(self, files_resource: FakeFilesResource | None = None) -> None:
        self.files_resource = files_resource or FakeFilesResource()

    def files(self) -> FakeFilesResource:
        return self.files_resource


class FakeDownloader:
    def __init__(self, file_handle: Any, request: object) -> None:
        self.file_handle = file_handle
        self.request = request

    def next_chunk(self) -> tuple[None, bool]:
        self.file_handle.write(b"%PDF fake")
        return None, True


def test_get_oracle_client_initializes_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = SimpleNamespace(is_available=True, _auth_method="api_key")

    monkeypatch.setattr(smart_module, "_genai_client", None)
    monkeypatch.setattr(smart_module, "GENAI_AVAILABLE", True)
    monkeypatch.setattr(smart_module, "get_genai_client", lambda: fake_client)

    assert smart_module.get_oracle_client() is fake_client
    assert smart_module.get_oracle_client() is fake_client


def test_get_drive_service_returns_none_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_settings = SimpleNamespace(google_credentials_json="")
    monkeypatch.setattr(core_config, "settings", fake_settings)

    assert smart_module.get_drive_service() is None


def test_get_drive_service_builds_readonly_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    fake_service = object()

    def fake_from_service_account_info(
        credentials_info: dict[str, Any],
        *,
        scopes: list[str],
    ) -> str:
        captured["credentials_info"] = credentials_info
        captured["scopes"] = scopes
        return "credentials"

    def fake_build(service_name: str, version: str, *, credentials: object) -> object:
        captured["build"] = {
            "service_name": service_name,
            "version": version,
            "credentials": credentials,
        }
        return fake_service

    fake_settings = SimpleNamespace(google_credentials_json='{"client_email": "svc@example.com"}')
    monkeypatch.setattr(core_config, "settings", fake_settings)
    monkeypatch.setattr(
        smart_module.service_account.Credentials,
        "from_service_account_info",
        staticmethod(fake_from_service_account_info),
    )
    monkeypatch.setattr(smart_module, "build", fake_build)

    assert smart_module.get_drive_service() is fake_service
    assert captured == {
        "credentials_info": {"client_email": "svc@example.com"},
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        "build": {
            "service_name": "drive",
            "version": "v3",
            "credentials": "credentials",
        },
    }


def test_download_pdf_from_drive_writes_temp_file_and_uses_clean_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files_resource = FakeFilesResource()
    service = FakeDriveService(files_resource)
    monkeypatch.setattr(smart_module, "get_drive_service", lambda: service)
    monkeypatch.setattr(smart_module, "MediaIoBaseDownload", FakeDownloader)

    path = smart_module.download_pdf_from_drive("folder/Permit_Guide.pdf")

    try:
        assert path == "/tmp/Permit Guide.pdf"
        assert Path(path).read_bytes() == b"%PDF fake"
        assert files_resource.media_file_id == "file-1"
        assert files_resource.list_calls[0]["q"] == (
            "name contains 'Permit_Guide' and mimeType = 'application/pdf' and trashed = false"
        )
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def test_download_pdf_from_drive_retries_with_spaces_when_first_query_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files_resource = FakeFilesResource(
        files_by_call=[
            [],
            [{"id": "file-2", "name": "Permit Guide.pdf"}],
        ],
    )
    service = FakeDriveService(files_resource)
    monkeypatch.setattr(smart_module, "get_drive_service", lambda: service)
    monkeypatch.setattr(smart_module, "MediaIoBaseDownload", FakeDownloader)

    path = smart_module.download_pdf_from_drive("Permit_Guide.pdf")

    try:
        assert path == "/tmp/Permit Guide.pdf"
        assert files_resource.media_file_id == "file-2"
        assert files_resource.list_calls[1]["q"] == (
            "name contains 'Permit Guide' and mimeType = 'application/pdf' and trashed = false"
        )
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_smart_oracle_uploads_downloaded_pdf_and_removes_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    captured: dict[str, Any] = {}

    class FakeUploadFiles:
        def upload(self, *, file: str) -> SimpleNamespace:
            captured["uploaded_file"] = file
            return SimpleNamespace(uri="gs://uploaded", mime_type="application/pdf")

    class FakeGenAI:
        def Client(self, *, api_key: str | None) -> SimpleNamespace:
            captured["api_key"] = api_key
            return SimpleNamespace(files=FakeUploadFiles())

    class FakeClient:
        is_available = True
        _auth_method = "api_key"

        async def generate_content(self, **kwargs: Any) -> dict[str, str]:
            captured["generate_content"] = kwargs
            return {"text": "Answer based on uploaded PDF"}

    monkeypatch.setattr(smart_module, "download_pdf_from_drive", lambda filename: str(pdf_path))
    monkeypatch.setattr(smart_module, "get_oracle_client", lambda: FakeClient())
    monkeypatch.setattr(smart_module, "genai", FakeGenAI())
    monkeypatch.setattr(smart_module, "settings", SimpleNamespace(google_api_key="test-key"))

    result = await smart_module.smart_oracle("What does it require?", "source.pdf")

    assert result == "Answer based on uploaded PDF"
    assert not pdf_path.exists()
    assert captured["uploaded_file"] == str(pdf_path)
    assert captured["api_key"] == "test-key"
    assert captured["generate_content"]["model"] == "gemini-2.0-flash-lite"
    assert captured["generate_content"]["max_output_tokens"] == 8192
    assert captured["generate_content"]["contents"][1]["file_data"] == {
        "file_uri": "gs://uploaded",
        "mime_type": "application/pdf",
    }


@pytest.mark.asyncio
async def test_smart_oracle_returns_missing_document_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_pdf(_: str) -> None:
        return None

    monkeypatch.setattr(smart_module, "download_pdf_from_drive", missing_pdf)

    result = await smart_module.smart_oracle("What does it require?", "missing.pdf")

    assert result == "Original document not found in Drive storage. Unable to perform deep analysis."


def test_test_drive_connection_returns_boolean_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smart_module, "get_drive_service", FakeDriveService)

    assert smart_module.test_drive_connection() is True

    def missing_drive_service() -> None:
        return None

    monkeypatch.setattr(smart_module, "get_drive_service", missing_drive_service)

    assert smart_module.test_drive_connection() is False


def test_smart_oracle_does_not_leave_temp_file_after_failed_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smart_module, "get_drive_service", lambda: None)

    assert smart_module.download_pdf_from_drive("missing.pdf") is None
    assert not os.path.exists("/tmp/missing.pdf")
