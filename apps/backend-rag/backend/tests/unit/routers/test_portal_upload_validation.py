"""Focused contracts for client-portal upload validation.

All payloads are synthetic and the portal service is mocked, so these tests
exercise no Drive, OCR, email, database, or other external side effect.
"""

from io import BytesIO
from unittest.mock import AsyncMock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import (
    _read_upload_bounded,
    get_current_client,
    get_portal_service,
    router,
)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@pytest.fixture
def portal_service() -> AsyncMock:
    service = AsyncMock()
    service.upload_document.return_value = {"id": 10, "file_name": "synthetic.pdf"}
    return service


@pytest.fixture
def client(portal_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: {
        "client_id": 42,
        "user_id": "synthetic-user",
        "email": "synthetic@example.invalid",
        "name": "Synthetic Client",
    }
    app.dependency_overrides[get_portal_service] = lambda: portal_service
    app.dependency_overrides[get_database_pool] = lambda: AsyncMock()
    return TestClient(app)


def _synthetic_docx() -> bytes:
    payload = BytesIO()
    document = Document()
    document.add_paragraph("Synthetic content without client data")
    document.save(payload)
    return payload.getvalue()


def _synthetic_pdf() -> bytes:
    payload = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(payload)
    return payload.getvalue()


def _synthetic_image(image_format: str) -> bytes:
    payload = BytesIO()
    with Image.new("RGB", (2, 2), color=(24, 48, 72)) as image:
        image.save(payload, format=image_format)
    return payload.getvalue()


def _append_zip_member(content: bytes, name: str, payload: bytes) -> bytes:
    updated = BytesIO(content)
    with ZipFile(updated, "a", ZIP_DEFLATED) as archive:
        archive.writestr(name, payload)
    return updated.getvalue()


def _replace_zip_member(content: bytes, name: str, payload: bytes) -> bytes:
    updated = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(updated, "w") as destination:
        for info in source.infolist():
            destination.writestr(
                info,
                payload if info.filename == name else source.read(info.filename),
            )
    return updated.getvalue()


def _add_explicit_zip_directories(content: bytes, *directories: str) -> bytes:
    updated = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(updated, "w") as destination:
        for directory in directories:
            destination.writestr(directory, b"")
        for info in source.infolist():
            destination.writestr(info, source.read(info.filename))
    return updated.getvalue()


@pytest.mark.asyncio
async def test_bounded_reader_stops_after_limit_plus_one_byte() -> None:
    upload = UploadFile(filename="synthetic.pdf", file=BytesIO(b"0123456789"))

    with pytest.raises(ValueError, match="maximum size"):
        await _read_upload_bounded(upload, max_size=8, chunk_size=3)

    assert upload.file.tell() == 9


def test_upload_accepts_pdf_with_matching_content_signature(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": ("synthetic.pdf", _synthetic_pdf(), "application/pdf")},
    )

    assert response.status_code == 200
    call = portal_service.upload_document.call_args
    assert call.kwargs["mime_type"] == "application/pdf"


def test_upload_accepts_structurally_identified_docx(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "synthetic.docx",
                _synthetic_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert portal_service.upload_document.await_count == 1


def test_upload_accepts_docx_with_explicit_directory_entries(
    client: TestClient,
    portal_service: AsyncMock,
) -> None:
    document = _add_explicit_zip_directories(_synthetic_docx(), "_rels/", "word/")

    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "explicit-directories.docx",
                document,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert portal_service.upload_document.await_count == 1


@pytest.mark.parametrize(
    ("filename", "payload", "declared_type", "trusted_type"),
    [
        ("synthetic.jpg", _synthetic_image("JPEG"), "image/jpg", "image/jpeg"),
        ("synthetic.png", _synthetic_image("PNG"), "image/png", "image/png"),
    ],
)
def test_upload_accepts_each_supported_binary_signature(
    client: TestClient,
    portal_service: AsyncMock,
    filename: str,
    payload: bytes,
    declared_type: str,
    trusted_type: str,
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": (filename, payload, declared_type)},
    )

    assert response.status_code == 200
    call = portal_service.upload_document.call_args
    assert call.kwargs["mime_type"] == trusted_type


@pytest.mark.parametrize(
    ("filename", "payload", "declared_type"),
    [
        ("renamed.pdf", b"not a pdf", "application/pdf"),
        ("renamed.png", _synthetic_pdf(), "image/png"),
        (
            "renamed.docx",
            b"PK\x03\x04not-office",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_upload_rejects_extension_content_mismatch_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
    filename: str,
    payload: bytes,
    declared_type: str,
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": (filename, payload, declared_type)},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "File content does not match its extension"
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_declared_mime_mismatch_before_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": ("synthetic.pdf", _synthetic_pdf(), "image/png")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Declared file type does not match its extension"
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_empty_file_before_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": ("synthetic.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File is empty"
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_oversize_before_service_call(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "synthetic.pdf",
                b"%PDF-1.4\n" + b"x" * MAX_UPLOAD_SIZE,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    portal_service.upload_document.assert_not_awaited()


@pytest.mark.parametrize(
    ("filename", "payload", "declared_type"),
    [
        ("prefix.pdf", b"%PDF-1.7\n%%EOF", "application/pdf"),
        ("prefix.jpg", b"\xff\xd8\xff\xe0synthetic\xff\xd9", "image/jpeg"),
        ("prefix.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png"),
        (
            "prefix.docx",
            b"PK\x03\x04synthetic",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_upload_rejects_prefix_only_payloads_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
    filename: str,
    payload: bytes,
    declared_type: str,
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": (filename, payload, declared_type)},
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


@pytest.mark.parametrize(
    ("filename", "payload", "declared_type"),
    [
        (
            "polyglot.pdf",
            _synthetic_pdf() + b"synthetic-trailing-payload",
            "application/pdf",
        ),
        (
            "polyglot.jpg",
            _synthetic_image("JPEG") + b"synthetic-trailing-payload",
            "image/jpeg",
        ),
        (
            "polyglot.png",
            _synthetic_image("PNG") + b"synthetic-trailing-payload",
            "image/png",
        ),
    ],
)
def test_upload_rejects_trailing_polyglot_content_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
    filename: str,
    payload: bytes,
    declared_type: str,
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": (filename, payload, declared_type)},
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_active_pdf_before_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    payload = _synthetic_pdf().replace(b"%%EOF", b"/JavaScript\n%%EOF")
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={"file": ("active.pdf", payload, "application/pdf")},
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_reviewer_docx_traversal_probe_before_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    malicious = _append_zip_member(
        _synthetic_docx(),
        "word/../../synthetic-payload.exe",
        b"synthetic executable marker",
    )
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "malicious.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_raw_dot_docx_member_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
) -> None:
    malicious = _append_zip_member(
        _synthetic_docx(),
        "word/./evil.bin",
        b"synthetic binary marker",
    )

    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "raw-dot-member.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    assert portal_service.upload_document.await_count == 0


def test_upload_rejects_doctype_entity_in_main_document_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
) -> None:
    original = _synthetic_docx()
    with ZipFile(BytesIO(original)) as archive:
        document_xml = archive.read("word/document.xml")
    declaration_end = document_xml.index(b"?>") + 2
    malicious_xml = (
        document_xml[:declaration_end]
        + b'<!DOCTYPE w:document [<!ENTITY synthetic "synthetic text">]>'
        + document_xml[declaration_end:]
    ).replace(
        b"</w:body>",
        b"<w:p><w:r><w:t>&synthetic;</w:t></w:r></w:p></w:body>",
        1,
    )
    malicious = _replace_zip_member(original, "word/document.xml", malicious_xml)

    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "doctype-main.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    assert portal_service.upload_document.await_count == 0


def test_upload_rejects_doctype_entity_in_unreferenced_xml_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
) -> None:
    malicious = _append_zip_member(
        _synthetic_docx(),
        "customXml/synthetic.xml",
        (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<!DOCTYPE synthetic [<!ENTITY probe "synthetic text">]>'
            b"<synthetic>&probe;</synthetic>"
        ),
    )

    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "doctype-unreferenced.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    assert portal_service.upload_document.await_count == 0


@pytest.mark.parametrize(
    "member_name",
    [
        "/absolute/synthetic.xml",
        "word\\synthetic.xml",
        "word/vbaProject.bin",
        "word/embeddings/synthetic.bin",
    ],
)
def test_upload_rejects_unsafe_docx_members_before_side_effects(
    client: TestClient,
    portal_service: AsyncMock,
    member_name: str,
) -> None:
    malicious = _append_zip_member(_synthetic_docx(), member_name, b"synthetic")
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "malicious.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_high_ratio_docx_member_before_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    malicious = _append_zip_member(
        _synthetic_docx(),
        "word/media/synthetic.bin",
        b"0" * (2 * 1024 * 1024),
    )
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "bomb.docx",
                malicious,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 415
    portal_service.upload_document.assert_not_awaited()


def test_upload_rejects_legacy_doc_before_reading_or_side_effects(
    client: TestClient, portal_service: AsyncMock
) -> None:
    response = client.post(
        "/api/portal/documents/upload",
        data={"document_type": "synthetic"},
        files={
            "file": (
                "legacy.doc",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1synthetic",
                "application/msword",
            )
        },
    )

    assert response.status_code == 400
    assert ".docx" in response.json()["detail"]
    portal_service.upload_document.assert_not_awaited()
