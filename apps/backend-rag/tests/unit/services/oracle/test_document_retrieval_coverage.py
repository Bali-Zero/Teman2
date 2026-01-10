import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import mock_open, patch

services_pkg = types.ModuleType("services")
services_pkg.__path__ = []
oracle_pkg = types.ModuleType("backend.services.oracle")
oracle_pkg.__path__ = []
sys.modules.setdefault("services", services_pkg)
sys.modules.setdefault("backend.services.oracle", oracle_pkg)
google_services_module = types.ModuleType("backend.services.oracle.oracle_google_services")
google_services_module.google_services = types.SimpleNamespace(drive_service=None, redis_url='redis://localhost:6379')
sys.modules.setdefault("backend.services.oracle.oracle_google_services", google_services_module)

module_path = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "oracle"
    / "document_retrieval.py"
)
spec = importlib.util.spec_from_file_location("backend.services.oracle.document_retrieval", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DocumentRetrievalService = module.DocumentRetrievalService


class DummyDownloader:
    def __init__(self, stream, request):
        self._stream = stream
        self._request = request
        self._done = False

    def next_chunk(self):
        if not self._done:
            self._stream.write(b"pdf-bytes")
            self._done = True
        return (None, self._done)


class DummyFiles:
    def __init__(self, results_sequence, raise_on_execute=False):
        self._results = results_sequence
        self._index = 0
        self._raise_on_execute = raise_on_execute

    def list(self, **_kwargs):
        return self

    def execute(self):
        if self._raise_on_execute:
            raise RuntimeError("drive down")
        result = self._results[self._index]
        self._index += 1
        return result

    def get_media(self, fileId):
        return f"request:{fileId}"


class DummyDriveService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


def test_download_pdf_drive_not_available():
    service = DocumentRetrievalService()
    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = None
        assert service.download_pdf_from_drive("sample.pdf") is None


def test_download_pdf_success_writes_file():
    service = DocumentRetrievalService()
    results = [
        {"files": []},
        {"files": [{"id": "123", "name": "sample.pdf"}]},
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()) as open_file:
                path = service.download_pdf_from_drive("sample.pdf")

    assert path == "/tmp/sample.pdf"
    open_file.assert_called_once()


def test_download_pdf_no_results():
    service = DocumentRetrievalService()
    results = [{"files": []}] * 4
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        assert service.download_pdf_from_drive("missing.pdf") is None


def test_download_pdf_handles_exception():
    service = DocumentRetrievalService()
    files = DummyFiles([], raise_on_execute=True)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        assert service.download_pdf_from_drive("boom.pdf") is None


def test_download_pdf_found_on_second_query():
    """Test finding PDF on second search query (covers alternative query paths)"""
    service = DocumentRetrievalService()
    # First query returns no results, second query finds it
    results = [
        {"files": []},  # First query (exact match)
        {"files": [{"id": "456", "name": "sample document.pdf"}]},  # Second query (with spaces)
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()):
                path = service.download_pdf_from_drive("sample_document.pdf")

    assert path == "/tmp/sample document.pdf"


def test_download_pdf_found_on_third_query():
    """Test finding PDF on third search query"""
    service = DocumentRetrievalService()
    results = [
        {"files": []},  # First query
        {"files": []},  # Second query
        {"files": [{"id": "789", "name": "sample-doc.pdf"}]},  # Third query (with dash)
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()):
                path = service.download_pdf_from_drive("sample-doc.pdf")

    assert path == "/tmp/sample-doc.pdf"


def test_download_pdf_found_on_fourth_query():
    """Test finding PDF on fourth search query"""
    service = DocumentRetrievalService()
    results = [
        {"files": []},  # First query
        {"files": []},  # Second query
        {"files": []},  # Third query
        {"files": [{"id": "999", "name": "sampledoc.pdf"}]},  # Fourth query (no separators)
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()):
                path = service.download_pdf_from_drive("sample_doc.pdf")

    assert path == "/tmp/sampledoc.pdf"


def test_download_pdf_filename_with_path():
    """Test download_pdf with filename containing path (tests basename extraction)"""
    service = DocumentRetrievalService()
    results = [
        {"files": [{"id": "path123", "name": "document.pdf"}]},
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()):
                # Filename with path - should extract basename
                path = service.download_pdf_from_drive("/some/path/to/document.pdf")

    assert path == "/tmp/document.pdf"


def test_download_pdf_filename_without_extension():
    """Test download_pdf with filename without extension"""
    service = DocumentRetrievalService()
    results = [
        {"files": [{"id": "noext123", "name": "document.pdf"}]},
    ]
    files = DummyFiles(results)
    drive_service = DummyDriveService(files)

    with patch("backend.services.oracle.document_retrieval.google_services") as gs:
        gs.drive_service = drive_service
        with patch("backend.services.oracle.document_retrieval.MediaIoBaseDownload", DummyDownloader):
            with patch("builtins.open", mock_open()):
                path = service.download_pdf_from_drive("document")

    assert path == "/tmp/document.pdf"
