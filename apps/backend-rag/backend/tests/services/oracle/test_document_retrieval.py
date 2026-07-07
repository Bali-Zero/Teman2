from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.services.oracle import document_retrieval as retrieval_module
from backend.services.oracle.document_retrieval import DocumentRetrievalService


class FakeExecute:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def execute(self) -> dict[str, Any]:
        return self.payload


class FakeFilesResource:
    def __init__(self, files_payload: list[dict[str, str]]) -> None:
        self.files_payload = files_payload
        self.queries: list[str] = []
        self.media_file_id: str | None = None

    def list(self, **kwargs: Any) -> FakeExecute:
        self.queries.append(kwargs["q"])
        return FakeExecute({"files": self.files_payload})

    def get_media(self, fileId: str) -> object:
        self.media_file_id = fileId
        return object()


class FakeDriveService:
    def __init__(self, files_payload: list[dict[str, str]]) -> None:
        self.files_resource = FakeFilesResource(files_payload)

    def files(self) -> FakeFilesResource:
        return self.files_resource


class FakeDownloader:
    def __init__(self, file_stream: Any, request: object) -> None:
        self.file_stream = file_stream

    def next_chunk(self) -> tuple[None, bool]:
        self.file_stream.write(b"%PDF fake")
        return None, True


def test_download_pdf_from_drive_returns_none_without_drive_service(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval_module, "google_services", SimpleNamespace(drive_service=None))

    assert DocumentRetrievalService().download_pdf_from_drive("missing.pdf") is None


def test_download_pdf_from_drive_searches_and_writes_temp_pdf(
    monkeypatch,
) -> None:
    temp_path = Path("/tmp/codex-oracle-document-test.pdf")
    if temp_path.exists():
        temp_path.unlink()
    drive = FakeDriveService(
        [{"id": "drive-file-1", "name": temp_path.name, "size": "8", "createdTime": "now"}],
    )
    monkeypatch.setattr(retrieval_module, "google_services", SimpleNamespace(drive_service=drive))
    monkeypatch.setattr(retrieval_module, "MediaIoBaseDownload", FakeDownloader)

    result = DocumentRetrievalService().download_pdf_from_drive("folder/codex_oracle_document_test.pdf")

    try:
        assert result == str(temp_path)
        assert temp_path.read_bytes() == b"%PDF fake"
        assert drive.files_resource.media_file_id == "drive-file-1"
        assert "codex_oracle_document_test" in drive.files_resource.queries[0]
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_download_pdf_from_drive_returns_none_when_no_match(monkeypatch) -> None:
    drive = FakeDriveService([])
    monkeypatch.setattr(retrieval_module, "google_services", SimpleNamespace(drive_service=drive))

    assert DocumentRetrievalService().download_pdf_from_drive("unknown.pdf") is None
    assert len(drive.files_resource.queries) == 4
