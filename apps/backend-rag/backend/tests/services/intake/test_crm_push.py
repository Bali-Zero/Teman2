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
        # F5 (rounds 4-5): EVERY upload — bearer included — must phone-resolve
        # the Fly id first; the defaults carry what resolution needs.
        "sender_phone": "+62 812-3456-7890",
        "crm_write_key": "service-key-abc",
    }
    kwargs.update(overrides)
    return kwargs


FLY_CLIENT_ID = 4321


def _serve_upsert(handler):
    """Wrap a handler so the mandatory phone-first resolution succeeds
    unambiguously; the wrapped handler then sees only the UPLOAD requests."""

    def _wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/upsert-by-phone"):
            return httpx.Response(
                200,
                json={"client_id": FLY_CLIENT_ID, "was_created": False, "matched_count": 1},
            )
        return handler(request)

    return _wrapped


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

    requests = mock_client(_serve_upsert(handler))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 321
    assert result.file_url == DRIVE_URL
    assert result.file_id == DRIVE_FILE_ID

    # Phone-resolution first, then ONE upload at the RESOLVED Fly id (never the
    # local pk — F5 applies to the bearer path too), with the reviewer JWT.
    assert len(requests) == 2
    assert requests[0].url.path == "/api/crm/clients/upsert-by-phone"
    req = requests[1]
    assert req.url.path == f"/api/crm/clients/{FLY_CLIENT_ID}/documents/upload"
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
    """Service-key path: the Fly id is phone-resolved FIRST, then the internal
    upload endpoint is addressed with THAT id (never the local pk — F5)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/upsert-by-phone"):
            return httpx.Response(
                200, json={"client_id": 4321, "was_created": False, "matched_count": 1}
            )
        return httpx.Response(
            200,
            json={"success": True, "document_id": 322, "file_url": DRIVE_URL},
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
    assert result.status == "pushed"
    assert len(requests) == 2
    assert requests[0].url.path == "/api/crm/clients/upsert-by-phone"
    req = requests[1]
    assert req.url.path == "/api/crm/internal/clients/4321/documents/upload"
    assert req.headers["x-crm-write-key"] == "service-key-abc"
    assert "authorization" not in req.headers


async def test_403_denied_rbac_no_retry(mock_client, blob):
    requests = mock_client(_serve_upsert(lambda r: httpx.Response(403, json={"detail": "nope"})))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "denied_rbac"
    assert "403" in (result.detail or "")
    assert len(requests) == 2  # upsert + ONE upload, no retry on auth failures


async def test_401_denied_rbac_no_retry(mock_client, blob):
    requests = mock_client(_serve_upsert(lambda r: httpx.Response(401, json={"detail": "expired"})))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "denied_rbac"
    assert len(requests) == 2


async def test_other_4xx_rejected_no_retry(mock_client, blob):
    requests = mock_client(
        _serve_upsert(lambda r: httpx.Response(400, json={"detail": "Invalid base64"}))
    )
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "rejected"
    assert len(requests) == 2


async def test_500_then_200_retried_ok(mock_client, blob):
    responses = iter(
        [
            httpx.Response(500, text="upstream burp"),
            httpx.Response(200, json={"success": True, "document_id": 9, "file_url": DRIVE_URL}),
        ]
    )
    requests = mock_client(_serve_upsert(lambda r: next(responses)))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 9
    assert len(requests) == 3  # upsert + failed upload + retried upload


async def test_500_twice_server_error(mock_client, blob):
    requests = mock_client(_serve_upsert(lambda r: httpx.Response(500, text="dead")))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "server_error"
    assert len(requests) == 3


async def test_connect_error_twice_unreachable(mock_client, blob):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    requests = mock_client(_serve_upsert(handler))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))

    assert result.ok is False
    assert result.status == "unreachable"
    assert "ConnectError" in (result.detail or "")
    assert len(requests) == 3  # upsert + initial upload + ONE retry


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
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, bearer_token=None, crm_write_key=None)
    )

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
# Cross-DB identity bridge (F5, phone-FIRST, rounds 4-5): the local pk is NEVER #
# a valid Fly address — the same number can name a DIFFERENT person there. BOTH #
# auth modes resolve the Fly id by phone BEFORE any upload and fail CLOSED when #
# they cannot (no phone / no key / upsert failure / SHARED phone — F7).         #
# --------------------------------------------------------------------------- #


async def test_phone_first_resolution_never_addresses_local_pk(mock_client, blob):
    """GUILT (F5): the upload must NEVER be addressed with the LOCAL pk — even
    when a row with that number would exist on Fly (it could be a different
    person). Order: upsert-by-phone FIRST, then upload at the RETURNED id."""

    local_pk = 87262

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert f"/clients/{local_pk}/" not in path, "local pk must never reach Fly"
        if path.endswith("/upsert-by-phone"):
            return httpx.Response(
                200, json={"client_id": FLY_CLIENT_ID, "was_created": True, "matched_count": 0}
            )
        return httpx.Response(
            200, json={"success": True, "document_id": 55, "file_url": DRIVE_URL}
        )

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(
            blob,
            bearer_token=None,
            crm_write_key="service-key-abc",
            client_id=local_pk,
            sender_phone="+62 812-3456-7890",
            client_full_name="Jane Doe",
        )
    )

    assert result.ok is True
    assert result.status == "pushed"
    assert result.fly_doc_id == 55
    paths = [r.url.path for r in requests]
    assert paths == [
        "/api/crm/clients/upsert-by-phone",
        f"/api/crm/internal/clients/{FLY_CLIENT_ID}/documents/upload",
    ]
    # the upsert body carries ONLY derived contact fields (Law 2), digits-only phone
    upsert_body = json.loads(requests[0].content)
    assert upsert_body["phone_normalized"] == "6281234567890"
    assert upsert_body["full_name"] == "Jane Doe"
    assert upsert_body["create_if_missing"] is True
    assert "file" not in upsert_body  # never the document blob


async def test_service_key_without_phone_fails_closed(mock_client, blob):
    """INNOCENCE→fail-closed: with no phone there is nothing to resolve the Fly
    identity with — NO HTTP call at all, verdict says identity_unresolved (the
    document stays committed locally; delivery is honestly not claimed)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call may be made without a resolved identity")

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(
            blob, bearer_token=None, crm_write_key="service-key-abc", sender_phone=None
        )
    )
    assert result.ok is False
    assert result.status == "identity_unresolved"
    assert len(requests) == 0


async def test_service_key_upsert_failure_fails_closed(mock_client, blob):
    """GUILT (F5): if the phone-upsert cannot resolve a Fly id, the upload is
    NOT attempted with the local pk — fail closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/upsert-by-phone"):
            return httpx.Response(500, json={"detail": "boom"})
        raise AssertionError("upload must not run without a resolved Fly id")

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(
            blob,
            bearer_token=None,
            crm_write_key="service-key-abc",
            sender_phone="+62 812-3456-7890",
        )
    )
    assert result.ok is False
    assert result.status == "identity_unresolved"
    assert [r.url.path for r in requests] == ["/api/crm/clients/upsert-by-phone"]


async def test_bearer_path_also_resolves_fly_id_first(mock_client, blob):
    """Round-5 F5: the reviewer-JWT path passes a LOCAL plan.client_id too — it
    must resolve the Fly id first exactly like the service-key path, and a 404
    on the RESOLVED id is a clean rejected (never a local-pk upload)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert f"/clients/{CLIENT_ID}/" not in request.url.path
        return httpx.Response(404, json={"detail": "Client not found"})

    requests = mock_client(_serve_upsert(handler))
    result = await crm_push.push_committed_document(**_push_kwargs(blob))  # bearer default
    assert result.ok is False
    assert result.status == "rejected"
    assert [r.url.path for r in requests] == [
        "/api/crm/clients/upsert-by-phone",
        f"/api/crm/clients/{FLY_CLIENT_ID}/documents/upload",
    ]


async def test_bearer_without_phone_fails_closed(mock_client, blob):
    """Round-5 F5 guilt: bearer + no sender phone → identity_unresolved with
    ZERO HTTP calls — the local pk must never be a fallback address."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call may be made without a resolved identity")

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, sender_phone=None)
    )
    assert result.ok is False
    assert result.status == "identity_unresolved"
    assert len(requests) == 0


async def test_shared_phone_ambiguity_fails_closed(mock_client, blob):
    """Round-5 F7 guilt: upsert-by-phone returning matched_count > 1 (shared
    phone — spouse/agent/office line) must NOT deliver: the endpoint picked one
    row arbitrarily and that is exactly the wrong-client vector."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/upsert-by-phone"):
            return httpx.Response(
                200, json={"client_id": 777, "was_created": False, "matched_count": 3}
            )
        raise AssertionError("upload must not run on an ambiguous identity")

    requests = mock_client(handler)
    result = await crm_push.push_committed_document(
        **_push_kwargs(blob, bearer_token=None)
    )
    assert result.ok is False
    assert result.status == "identity_unresolved"
    assert [r.url.path for r in requests] == ["/api/crm/clients/upsert-by-phone"]
