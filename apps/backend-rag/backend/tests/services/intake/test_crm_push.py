"""Unit tests for the Pro→Fly CRM delivery module (backend.services.intake.crm_push).

NO database, NO network: HTTP is faked via httpx.MockTransport injected into
the module's persistent client. Asserts the request matches the REAL Fly
endpoint contract (path /api/crm/clients/{id}/documents/upload + the
DocumentUploadBase64 field names) and the response parsing
({"success", "document_id", "file_url"}).
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from backend.services.intake import crm_push

pytestmark = pytest.mark.asyncio

CLIENT_ID = 77
BLOB_BYTES = b"%PDF-1.4 fake intake blob bytes"
DRIVE_FILE_ID = "1AbC2dEfG3hIjK4LmNoP"
DRIVE_URL = f"https://drive.google.com/file/d/{DRIVE_FILE_ID}/view?usp=drivesdk"


@pytest.fixture
def blob(tmp_path: Path) -> Path:
    p = tmp_path / "passport-scan.pdf"
    p.write_bytes(BLOB_BYTES)
    return p


@pytest_asyncio.fixture
async def mock_client() -> AsyncIterator[Callable[..., list[httpx.Request]]]:
    """Install a MockTransport-backed client into the module; restore after.

    Usage: ``requests = mock_client(handler)`` — returns the (live) list of
    captured requests; the handler decides each response.
    """
    captured: list[httpx.Request] = []
    saved = crm_push._client

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
        def _wrapped(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return handler(request)

        crm_push._client = httpx.AsyncClient(transport=httpx.MockTransport(_wrapped))
        return captured

    yield install

    if crm_push._client is not None and not crm_push._client.is_closed:
        await crm_push._client.aclose()
    crm_push._client = saved


def _push_kwargs(blob: Path, **overrides: object) -> dict:
    kwargs: dict = {
        "bearer_token": "jwt-token-abc",
        "client_id": CLIENT_ID,
        "file_name": "passport-scan.pdf",
        "document_type": "passport",
        "blob_path": str(blob),
        "practice_id": 12,
        "document_category": "immigration",
        "mime_type": "application/pdf",
        "notes": "intake:wa-123",
        "base_url": "http://fly.test",
    }
    kwargs.update(overrides)
    return kwargs


# --------------------------------------------------------------------------- #
async def test_success_parses_doc_id_file_url_and_drive_file_id(mock_client, blob):
    """200 → ok=True, document_id/file_url parsed, Drive file id extracted."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "document_id": 321,
                "file_url": DRIVE_URL,
                "ocr_triggered": True,
                "company_document_id": None,
            },
        )

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 321
    assert result.file_url == DRIVE_URL
    assert result.file_id == DRIVE_FILE_ID

    # Exactly one request, against the REAL endpoint path, with the reviewer JWT.
    assert len(requests) == 1
    req = requests[0]
    assert req.url.path == f"/api/crm/clients/{CLIENT_ID}/documents/upload"
    assert req.headers["authorization"] == "Bearer jwt-token-abc"

    # Body matches DocumentUploadBase64 field names exactly.
    body = json.loads(req.content)
    assert base64.b64decode(body["file"]) == BLOB_BYTES
    assert body["file_name"] == "passport-scan.pdf"
    assert body["document_type"] == "passport"
    assert body["document_category"] == "immigration"
    assert body["mime_type"] == "application/pdf"
    assert body["notes"] == "intake:wa-123"
    assert body["practice_id"] == 12
    # Fields the endpoint does NOT accept must not be sent.
    assert "extracted_fields" not in body
    # None optionals are dropped, not sent as null.
    assert "expiry_date" not in body
    assert "family_member_id" not in body


async def test_service_key_uses_internal_upload_endpoint(mock_client, blob):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"success": True, "document_id": 322, "file_url": DRIVE_URL},
        )

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, bearer_token=None, crm_write_key="service-key-abc")
    )

    assert result.ok is True
    assert result.status == "pushed"
    assert len(requests) == 1
    req = requests[0]
    assert req.url.path == f"/api/crm/internal/clients/{CLIENT_ID}/documents/upload"
    assert req.headers["x-crm-write-key"] == "service-key-abc"
    assert "authorization" not in req.headers


async def test_403_denied_rbac_no_retry(mock_client, blob):
    requests = mock_client(lambda r: httpx.Response(403, json={"detail": "nope"}))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "denied_rbac"
    assert "403" in (result.detail or "")
    assert len(requests) == 1  # no retry on auth failures


async def test_401_denied_rbac_no_retry(mock_client, blob):
    requests = mock_client(lambda r: httpx.Response(401, json={"detail": "expired"}))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "denied_rbac"
    assert len(requests) == 1


async def test_other_4xx_rejected_no_retry(mock_client, blob):
    requests = mock_client(lambda r: httpx.Response(400, json={"detail": "Invalid base64"}))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "rejected"
    assert len(requests) == 1


async def test_500_then_200_retried_ok(mock_client, blob):
    responses = iter(
        [
            httpx.Response(500, text="upstream burp"),
            httpx.Response(200, json={"success": True, "document_id": 9, "file_url": DRIVE_URL}),
        ]
    )
    requests = mock_client(lambda r: next(responses))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 9
    assert len(requests) == 2  # one retry


async def test_500_twice_server_error(mock_client, blob):
    requests = mock_client(lambda r: httpx.Response(500, text="dead"))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "server_error"
    assert len(requests) == 2


async def test_connect_error_twice_unreachable(mock_client, blob):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "unreachable"
    assert "ConnectError" in (result.detail or "")
    assert len(requests) == 2  # initial + ONE retry


async def test_oversize_blob_too_large_without_http_call(mock_client, blob, monkeypatch):
    monkeypatch.setenv("INTAKE_CRM_PUSH_MAX_MB", "0.00001")  # ~10 bytes
    requests = mock_client(lambda r: httpx.Response(200, json={"success": True}))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "too_large"
    assert requests == []  # size guard fires BEFORE any HTTP


async def test_missing_blob_no_http_call(mock_client, tmp_path):
    requests = mock_client(lambda r: httpx.Response(200, json={"success": True}))
    result = await crm_push.push_committed_document(
        **_push_kwargs(tmp_path / "ghost.pdf")
    )

    assert result.ok is False
    assert result.status == "missing_blob"
    assert requests == []


async def test_no_token_no_http_call(mock_client, blob):
    requests = mock_client(lambda r: httpx.Response(200, json={"success": True}))
    result = await crm_push.push_committed_document(**_push_kwargs(blob, bearer_token=None))

    assert result.ok is False
    assert result.status == "no_token"
    assert requests == []


def test_push_enabled_default_and_kill_switch(monkeypatch):
    monkeypatch.delenv("INTAKE_CRM_PUSH_ENABLED", raising=False)
    assert crm_push.push_enabled() is True
    monkeypatch.setenv("INTAKE_CRM_PUSH_ENABLED", "0")
    assert crm_push.push_enabled() is False
    monkeypatch.setenv("INTAKE_CRM_PUSH_ENABLED", "false")
    assert crm_push.push_enabled() is False
    monkeypatch.setenv("INTAKE_CRM_PUSH_ENABLED", "1")
    assert crm_push.push_enabled() is True


def test_parse_drive_file_id():
    assert crm_push._parse_drive_file_id(DRIVE_URL) == DRIVE_FILE_ID
    assert crm_push._parse_drive_file_id(None) is None
    assert crm_push._parse_drive_file_id("https://example.com/no-drive") is None


# --------------------------------------------------------------------------- #
# Cross-DB identity self-heal: local client_id absent on Fly -> phone-upsert.    #
# GUILT (404 + service-key + phone -> upsert -> retry on Fly id) and INNOCENCE   #
# (200 first try, or 404 with no phone) — the upsert must fire ONLY when needed. #
# --------------------------------------------------------------------------- #
FLY_CLIENT_ID = 4321


async def test_404_phone_upsert_then_retry_succeeds(mock_client, blob):
    """GUILT: a local pk (87262) that 404s on Fly is phone-upserted, and the
    upload is re-aimed at the RETURNED Fly id and retried — and succeeds."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/upsert-by-phone"):
            return httpx.Response(
                200, json={"client_id": FLY_CLIENT_ID, "was_created": True, "matched_count": 0}
            )
        # upload endpoint: 404 for the local id, 200 for the Fly id
        if f"/clients/{FLY_CLIENT_ID}/documents/upload" in path:
            return httpx.Response(
                200, json={"success": True, "document_id": 55, "file_url": DRIVE_URL}
            )
        return httpx.Response(404, json={"detail": "Client not found"})

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(
            blob,
            bearer_token=None,
            crm_write_key="service-key-abc",
            client_id=87262,
            sender_phone="+62 812-3456-7890",
            client_full_name="Jane Doe",
        )
    )

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 55
    paths = [r.url.path for r in requests]
    # initial upload (local id, 404) -> upsert-by-phone -> retry upload (fly id)
    assert paths[0] == "/api/crm/internal/clients/87262/documents/upload"
    assert paths[1] == "/api/crm/clients/upsert-by-phone"
    assert paths[2] == f"/api/crm/internal/clients/{FLY_CLIENT_ID}/documents/upload"
    # the upsert body carries ONLY derived contact fields (Law 2), digits-only phone
    upsert_body = json.loads(requests[1].content)
    assert upsert_body["phone_normalized"] == "6281234567890"
    assert upsert_body["full_name"] == "Jane Doe"
    assert upsert_body["create_if_missing"] is True
    assert "file" not in upsert_body  # never the document blob


async def test_200_first_try_never_upserts(mock_client, blob):
    """INNOCENCE: a clean 200 must NOT trigger any phone-upsert call."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert not request.url.path.endswith("/upsert-by-phone"), "must not upsert on success"
        return httpx.Response(
            200, json={"success": True, "document_id": 7, "file_url": DRIVE_URL}
        )

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(
            blob,
            bearer_token=None,
            crm_write_key="service-key-abc",
            sender_phone="+62 812-3456-7890",
        )
    )
    assert result.ok is True
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/documents/upload")


async def test_404_without_phone_does_not_upsert(mock_client, blob):
    """INNOCENCE: a 404 with NO sender_phone cannot self-heal — stays rejected,
    and never calls upsert (no phone to key on)."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert not request.url.path.endswith("/upsert-by-phone")
        return httpx.Response(404, json={"detail": "Client not found"})

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, bearer_token=None, crm_write_key="service-key-abc")
    )
    assert result.ok is False
    assert result.status == "rejected"
    assert len(requests) == 1  # just the failed upload, no upsert


async def test_404_with_bearer_token_does_not_upsert(mock_client, blob):
    """INNOCENCE: reviewer-JWT path is human-driven against Fly directly — the
    cross-DB bridge is service-key-only, so a JWT 404 must NOT upsert."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert not request.url.path.endswith("/upsert-by-phone")
        return httpx.Response(404, json={"detail": "Client not found"})

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, sender_phone="+62 812-3456-7890")  # keeps bearer_token
    )
    assert result.ok is False
    assert result.status == "rejected"
    assert len(requests) == 1
