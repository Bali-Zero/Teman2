"""Unit tests for backend/app/routers/asset_upload.py — P1.2 Tigris upload proxy.

Auth/validation paths tested without real Tigris S3 — boto3 client mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.app.routers import asset_upload

    app = FastAPI()
    app.include_router(asset_upload.router)
    return TestClient(app)


@pytest.fixture
def configured_token(monkeypatch):
    monkeypatch.setenv("ASSET_UPLOAD_TOKEN", "test-secret-XYZ")
    return "test-secret-XYZ"


@pytest.fixture
def jpg_payload():
    # Minimal JPEG SOI/APP0 header + filler — 600 bytes total
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 590


def test_health_no_token(client, monkeypatch):
    monkeypatch.delenv("ASSET_UPLOAD_TOKEN", raising=False)
    r = client.get("/api/assets/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded_no_token"
    assert body["token_configured"] is False
    assert body["bucket"] == "nuzantara-warroom-images"


def test_health_with_token(client, configured_token):
    r = client.get("/api/assets/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["token_configured"] is True


def test_upload_503_when_server_token_missing(client, monkeypatch, jpg_payload):
    monkeypatch.delenv("ASSET_UPLOAD_TOKEN", raising=False)
    r = client.post(
        "/api/assets/upload",
        files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "c5a-test"},
        headers={"X-Asset-Upload-Token": "anything"},
    )
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_upload_401_missing_client_token(client, configured_token, jpg_payload):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "c5a-test"},
    )
    assert r.status_code == 401
    assert "X-Asset-Upload-Token" in r.json()["detail"]


def test_upload_401_wrong_token(client, configured_token, jpg_payload):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "c5a-test"},
        headers={"X-Asset-Upload-Token": "WRONG"},
    )
    assert r.status_code == 401


def test_upload_400_bad_prefix(client, configured_token, jpg_payload):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
        data={"prefix": "exfiltration-attempt", "session_id": "c5a"},
        headers={"X-Asset-Upload-Token": configured_token},
    )
    assert r.status_code == 400
    assert "prefix must be" in r.json()["detail"]


def test_upload_415_bad_content_type(client, configured_token):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("evil.exe", b"MZ\x90\x00", "application/x-msdownload")},
        data={"prefix": "wr2-hero", "session_id": "c5a"},
        headers={"X-Asset-Upload-Token": configured_token},
    )
    assert r.status_code == 415


def test_upload_400_bad_session_id_with_slash(client, configured_token, jpg_payload):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "../../../etc/passwd"},
        headers={"X-Asset-Upload-Token": configured_token},
    )
    assert r.status_code == 400


def test_upload_400_empty_body(client, configured_token):
    r = client.post(
        "/api/assets/upload",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "c5a"},
        headers={"X-Asset-Upload-Token": configured_token},
    )
    assert r.status_code == 400


def test_upload_413_oversized(client, configured_token):
    big_body = b"\xff\xd8" + b"\x00" * (26 * 1024 * 1024)
    r = client.post(
        "/api/assets/upload",
        files={"file": ("big.jpg", big_body, "image/jpeg")},
        data={"prefix": "wr2-hero", "session_id": "c5a"},
        headers={"X-Asset-Upload-Token": configured_token},
    )
    assert r.status_code == 413


def test_upload_201_happy_path(client, configured_token, jpg_payload):
    fake_s3 = MagicMock()
    fake_s3.put_object.return_value = {"ETag": '"abc"'}

    with patch(
        "backend.app.routers.asset_upload._tigris.get_s3_client", return_value=fake_s3
    ):
        r = client.post(
            "/api/assets/upload",
            files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
            data={"prefix": "wr2-hero", "session_id": "c5a-konten-kreator"},
            headers={"X-Asset-Upload-Token": configured_token},
        )

    assert r.status_code == 201
    body = r.json()
    assert body["public_url"].startswith(
        "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-hero/c5a-konten-kreator/"
    )
    assert body["tigris_key"].startswith("wr2-hero/c5a-konten-kreator/")
    assert body["tigris_key"].endswith("-01-hero.jpg")
    assert len(body["sha256"]) == 64
    assert body["bytes"] == len(jpg_payload)
    assert body["content_type"] == "image/jpeg"
    fake_s3.put_object.assert_called_once()
    call_kwargs = fake_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "nuzantara-warroom-images"
    assert call_kwargs["ACL"] == "public-read"
    assert call_kwargs["ContentType"] == "image/jpeg"


def test_upload_502_on_tigris_failure(client, configured_token, jpg_payload):
    fake_s3 = MagicMock()
    fake_s3.put_object.side_effect = RuntimeError("simulated S3 outage")

    with patch(
        "backend.app.routers.asset_upload._tigris.get_s3_client", return_value=fake_s3
    ):
        r = client.post(
            "/api/assets/upload",
            files={"file": ("01-hero.jpg", jpg_payload, "image/jpeg")},
            data={"prefix": "wr2-hero", "session_id": "c5a"},
            headers={"X-Asset-Upload-Token": configured_token},
        )

    assert r.status_code == 502
    assert "Tigris upload failed" in r.json()["detail"]


def test_content_addressed_key_is_deterministic(
    client, configured_token, jpg_payload
):
    """Same bytes + same session = same Tigris key (sha8 prefix stable)."""
    fake_s3 = MagicMock()
    fake_s3.put_object.return_value = {}

    keys = []
    with patch(
        "backend.app.routers.asset_upload._tigris.get_s3_client", return_value=fake_s3
    ):
        for _ in range(2):
            r = client.post(
                "/api/assets/upload",
                files={"file": ("hero.jpg", jpg_payload, "image/jpeg")},
                data={"prefix": "wr2-hero", "session_id": "stable"},
                headers={"X-Asset-Upload-Token": configured_token},
            )
            assert r.status_code == 201
            keys.append(r.json()["tigris_key"])

    assert keys[0] == keys[1], f"key drift: {keys}"
