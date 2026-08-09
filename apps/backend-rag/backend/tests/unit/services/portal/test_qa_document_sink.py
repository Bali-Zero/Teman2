"""Tests for the fail-closed portal QA document sink client."""

from __future__ import annotations

import pytest

from backend.services.portal.qa_document_sink import QADocumentSinkClient

_KEY = "synthetic_document_sink_key_00000001"


def _environment() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql://nuzantara@127.0.0.1:5432/my_portal_qa_unit",
        "MY_PORTAL_QA_DOCUMENT_SINK_URL": "http://127.0.0.1:18282",
        "MY_PORTAL_QA_DOCUMENT_SINK_KEY": _KEY,
    }


def test_qa_document_sink_is_disabled_without_its_contract() -> None:
    assert QADocumentSinkClient.from_environment({}) is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DATABASE_URL", "postgresql://db.example.test:5432/my_portal_qa_unit"),
        ("DATABASE_URL", "postgresql://127.0.0.1:5432/production"),
        ("MY_PORTAL_QA_DOCUMENT_SINK_URL", "https://my.balizero.com"),
        ("MY_PORTAL_QA_DOCUMENT_SINK_KEY", "weak"),
    ],
)
def test_qa_document_sink_rejects_unsafe_configuration(name: str, value: str) -> None:
    environment = _environment()
    environment[name] = value
    with pytest.raises(RuntimeError):
        QADocumentSinkClient.from_environment(environment)


def test_qa_document_sink_accepts_only_reserved_upload_identity() -> None:
    client = QADocumentSinkClient.from_environment(_environment())
    assert client is not None
    client.validate_synthetic_upload(
        email="portal-active@example.com",
        file_name="synthetic-portal-upload-chromium.pdf",
        mime_type="application/pdf",
    )

    with pytest.raises(RuntimeError, match="uploader identity"):
        client.validate_synthetic_upload(
            email="client@balizero.com",
            file_name="synthetic-portal-upload-chromium.pdf",
            mime_type="application/pdf",
        )
    with pytest.raises(RuntimeError, match="document name"):
        client.validate_synthetic_upload(
            email="portal-active@example.com",
            file_name="passport.pdf",
            mime_type="application/pdf",
        )
