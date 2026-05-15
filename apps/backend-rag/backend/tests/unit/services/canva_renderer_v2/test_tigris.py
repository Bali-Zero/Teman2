"""Tigris S3 client: put_object with retry + delete + URL build."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.services.canva_renderer_v2._tigris import (
    build_public_url,
    delete_pdf,
    delete_pdf_by_key,
    upload_pdf,
    TigrisError,
)


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    monkeypatch.setattr("backend.services.canva_renderer_v2._tigris.time.sleep", lambda *_: None)


@pytest.fixture
def fake_s3():
    client = MagicMock()
    client.put_object.return_value = {"ETag": '"abc123"'}
    client.delete_object.return_value = {}
    return client


def test_upload_pdf_success_content_addressed(tmp_path, fake_s3):
    """upload_pdf returns (url, key) tuple with content-addressed key by default."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n...\n%%EOF")
    url, key = upload_pdf(fake_s3, pdf, draft_id="abc-123", prefix="wr2-pdf")
    assert "wr2-pdf/abc-123/" in key
    assert key.endswith(".pdf")
    assert key in url
    fake_s3.put_object.assert_called_once()
    call = fake_s3.put_object.call_args
    assert call.kwargs["Key"] == key
    assert call.kwargs["ContentType"] == "application/pdf"
    assert call.kwargs["ACL"] == "public-read"


def test_upload_pdf_legacy_mode(tmp_path, fake_s3):
    """content_addressed=False uses the predictable legacy key."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n...\n%%EOF")
    url, key = upload_pdf(fake_s3, pdf, draft_id="abc-123", prefix="wr2-pdf",
                          content_addressed=False)
    assert key == "wr2-pdf/abc-123.pdf"
    assert url.endswith("/wr2-pdf/abc-123.pdf")


def test_upload_pdf_retries_on_transient_error(tmp_path):
    from botocore.exceptions import ClientError
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    s3 = MagicMock()
    s3.put_object.side_effect = [
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        {"ETag": '"abc"'},
    ]
    url, key = upload_pdf(s3, pdf, draft_id="abc", prefix="wr2-pdf")
    assert "wr2-pdf/abc/" in key
    assert s3.put_object.call_count == 3


def test_upload_pdf_exhausts_retries(tmp_path):
    from botocore.exceptions import ClientError
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    s3 = MagicMock()
    s3.put_object.side_effect = ClientError({"Error": {"Code": "503"}}, "PutObject")
    with pytest.raises(TigrisError, match="exhausted retries"):
        upload_pdf(s3, pdf, draft_id="abc", prefix="wr2-pdf")
    assert s3.put_object.call_count == 3


def test_delete_pdf_best_effort(fake_s3):
    """delete_pdf (legacy) still works — targets old-style key."""
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")
    fake_s3.delete_object.assert_called_once()
    fake_s3.delete_object.side_effect = Exception("boom")
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")  # no raise


def test_delete_pdf_by_key(fake_s3):
    """delete_pdf_by_key deletes exact key, swallows errors."""
    delete_pdf_by_key(fake_s3, key="wr2-pdf/draft-99/abc12345.pdf")
    fake_s3.delete_object.assert_called_once_with(
        Bucket=fake_s3.delete_object.call_args.kwargs["Bucket"],
        Key="wr2-pdf/draft-99/abc12345.pdf",
    )
    fake_s3.delete_object.side_effect = Exception("gone")
    delete_pdf_by_key(fake_s3, key="wr2-pdf/x/y.pdf")  # no raise


def test_build_public_url():
    url = build_public_url("abc", prefix="wr2-pdf")
    assert url == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc.pdf"
    url2 = build_public_url("xyz", prefix="wr2-pdf-tests")
    assert url2 == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf-tests/xyz.pdf"
