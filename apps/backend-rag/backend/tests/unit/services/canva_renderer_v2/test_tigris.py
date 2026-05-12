"""Tigris S3 client: put_object with retry + delete + URL build."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.canva_renderer_v2._tigris import (
    build_public_url,
    delete_pdf,
    upload_pdf,
    TigrisError,
)


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    monkeypatch.setattr("backend.services.canva_renderer_v2._tigris.time.sleep", lambda *_: None)


@pytest.fixture
def fake_s3():
    """boto3 client stub. Return success unless overridden by test."""
    client = MagicMock()
    client.put_object.return_value = {"ETag": '"abc123"'}
    client.delete_object.return_value = {}
    return client


def test_upload_pdf_success(tmp_path, fake_s3):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n...\n%%EOF")
    url = upload_pdf(fake_s3, pdf, draft_id="abc-123", prefix="wr2-pdf")
    assert url == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc-123.pdf"
    fake_s3.put_object.assert_called_once()
    call = fake_s3.put_object.call_args
    assert call.kwargs["Key"] == "wr2-pdf/abc-123.pdf"
    assert call.kwargs["ContentType"] == "application/pdf"
    assert call.kwargs["ACL"] == "public-read"


def test_upload_pdf_retries_on_transient_error(tmp_path):
    from botocore.exceptions import ClientError
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    s3 = MagicMock()
    # Fail twice (503), succeed third
    s3.put_object.side_effect = [
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        {"ETag": '"abc"'},
    ]
    url = upload_pdf(s3, pdf, draft_id="abc", prefix="wr2-pdf")
    assert url.endswith("/wr2-pdf/abc.pdf")
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
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")
    fake_s3.delete_object.assert_called_once()
    # Must not raise even if delete fails
    fake_s3.delete_object.side_effect = Exception("boom")
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")  # no raise


def test_build_public_url():
    url = build_public_url("abc", prefix="wr2-pdf")
    assert url == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc.pdf"
    url2 = build_public_url("xyz", prefix="wr2-pdf-tests")
    assert url2 == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf-tests/xyz.pdf"
