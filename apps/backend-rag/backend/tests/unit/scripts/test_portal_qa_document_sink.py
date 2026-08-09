"""Tests for the loopback-only portal QA document sink service."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.scripts.portal_qa_document_sink import (
    QADocumentSinkSettings,
    create_app,
)

_KEY = "synthetic_document_sink_key_00000001"
_NAME = "synthetic-portal-upload-chromium.pdf"
_INVOICE_FILE_ID = "synthetic_invoice_pdf_fixture_00000001"


def _pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


def _client() -> TestClient:
    return TestClient(
        create_app(
            QADocumentSinkSettings(
                key=_KEY,
                invoice_file_id=_INVOICE_FILE_ID,
            ),
        ),
    )


def test_document_sink_requires_a_strong_key_and_reserved_invoice_fixture() -> None:
    for environment in (
        {},
        {"MY_PORTAL_QA_DOCUMENT_SINK_KEY": "weak"},
        {
            "MY_PORTAL_QA_DOCUMENT_SINK_KEY": _KEY,
            "MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID": "drive-file-id",
        },
    ):
        try:
            QADocumentSinkSettings.from_environment(environment)
        except RuntimeError as error:
            assert "MY_PORTAL_" in str(error)
        else:
            raise AssertionError("Expected the document sink settings to fail closed")


def test_document_sink_rejects_key_name_and_content_mismatches() -> None:
    client = _client()
    headers = {
        "Content-Type": "application/pdf",
        "X-QA-Sink-Key": _KEY,
        "X-QA-Document-Name": _NAME,
    }
    assert (
        client.post("/qa/documents", headers={**headers, "X-QA-Sink-Key": "wrong"}).status_code
        == 401
    )
    assert (
        client.post(
            "/qa/documents",
            headers={**headers, "X-QA-Document-Name": "passport.pdf"},
            content=_pdf_bytes(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/qa/documents",
            headers=headers,
            content=b"not a pdf",
        ).status_code
        == 415
    )


def test_document_sink_round_trip_and_count_only_receipt() -> None:
    client = _client()
    pdf = _pdf_bytes()
    headers = {
        "Content-Type": "application/pdf",
        "X-QA-Sink-Key": _KEY,
        "X-QA-Document-Name": _NAME,
    }

    uploaded = client.post("/qa/documents", headers=headers, content=pdf)
    assert uploaded.status_code == 201
    file_id = uploaded.json()["file_id"]
    assert isinstance(file_id, str)

    assert client.get(f"/qa/documents/{file_id}").status_code == 401
    downloaded = client.get(
        f"/qa/documents/{file_id}",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content == pdf

    receipt = client.get(
        "/qa/receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert receipt.status_code == 200
    assert receipt.json() == {
        "documents": 2,
        "uploads": 1,
        "downloads": 1,
        "rejected_uploads": 0,
    }
    assert set(receipt.json()) == {
        "documents",
        "uploads",
        "downloads",
        "rejected_uploads",
    }

    fresh = _client()
    empty_receipt = fresh.get(
        "/qa/receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert empty_receipt.json() == {
        "documents": 1,
        "uploads": 0,
        "downloads": 0,
        "rejected_uploads": 0,
    }


def test_document_sink_rejects_one_armed_upload_without_persisting_it() -> None:
    client = _client()
    headers = {
        "Content-Type": "application/pdf",
        "X-QA-Sink-Key": _KEY,
        "X-QA-Document-Name": _NAME,
    }

    assert client.post("/qa/fail-next-upload").status_code == 401
    assert (
        client.post(
            "/qa/fail-next-upload",
            headers={"X-QA-Sink-Key": _KEY},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/qa/fail-next-upload",
            headers={"X-QA-Sink-Key": _KEY},
        ).status_code
        == 409
    )

    rejected = client.post("/qa/documents", headers=headers, content=_pdf_bytes())
    assert rejected.status_code == 503
    receipt = client.get(
        "/qa/receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert receipt.json() == {
        "documents": 1,
        "uploads": 0,
        "downloads": 0,
        "rejected_uploads": 1,
    }

    accepted = client.post("/qa/documents", headers=headers, content=_pdf_bytes())
    assert accepted.status_code == 201
    receipt = client.get(
        "/qa/receipt",
        headers={"X-QA-Sink-Key": _KEY},
    )
    assert receipt.json() == {
        "documents": 2,
        "uploads": 1,
        "downloads": 0,
        "rejected_uploads": 1,
    }


def test_document_sink_preloads_the_reserved_invoice_pdf() -> None:
    client = _client()

    response = client.get(
        f"/qa/documents/{_INVOICE_FILE_ID}",
        headers={"X-QA-Sink-Key": _KEY},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
