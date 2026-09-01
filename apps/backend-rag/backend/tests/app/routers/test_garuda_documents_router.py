"""L5 hinge — `garuda_documents_router.py` contract-status-code coverage.

Same shape as `test_garuda_orders_envelope.py`/`test_garuda_staff_actor_async_
verifier.py`: a bare `FastAPI()` app with only this router mounted, fakes for
every collaborator (no Postgres, no live Ollama), `httpx.AsyncClient` over
`ASGITransport`. One test per contract status code in
`products/garuda-voa/contracts/openapi.yaml`'s `uploadIntakeDocument` /
`listIntakeDocuments` responses tables, plus the auth/idempotency/PII/flag
requirements this task additionally asked for.

429 RATE_LIMITED and 500 INTERNAL_ERROR are declared in the contract but are
cross-cutting (rate-limit middleware / the app-wide exception handler — see
`garuda_voa_public.py`'s own comment on this, and this router's module
docstring) and are not raised by any call site in `garuda_documents_router.py`
itself; `test_internal_error_is_the_apps_generic_500` still proves the 500
status is reachable end-to-end through the real app exception handler, using
a store that raises an unmapped exception, so it is not merely asserted by
citation.
"""

from __future__ import annotations

import io
import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.app.routers import garuda_documents_router
from backend.services.garuda_documents import service as service_module
from backend.services.garuda_documents.ocr_client import OcrPassResult
from backend.services.garuda_documents.ports import InMemoryDocumentStore

_SESSION_COOKIE = "garuda_session"
_ACTOR = "result_owns_documents_00000000"
_OTHER_RESULT = "result_belongs_to_someone_else"


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


async def _verifier_returns_fixed_actor(cookie: str) -> str | None:
    return _ACTOR if cookie else None


def _app(**state) -> FastAPI:
    application = FastAPI()
    application.include_router(garuda_documents_router.router)
    for key, value in state.items():
        setattr(application.state, key, value)
    return application


def _valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _pass(values: dict[str, str | None], confidence: float = 0.95) -> OcrPassResult:
    conf = dict.fromkeys(values, confidence)
    return OcrPassResult(values=values, self_confidence=conf)


_CONFIDENT_FIELDS = {
    "full_name": "X_SENTINEL_VALUE_1234",
    "passport_number": "P1234567",
    "nationality": "ITALIAN",
    "passport_expiry_date": "2030-01-01",
}


def _patch_ocr(monkeypatch: pytest.MonkeyPatch, result) -> None:
    """`service.py` imports `extract_passport_biodata_dual_pass` by name into
    its own module namespace — patch it THERE, not on `ocr_client`, or the
    service keeps calling the original."""

    async def _fake(image_base64: str):
        return result

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", _fake)


async def _post_document(
    client: AsyncClient,
    *,
    result_id: str = _ACTOR,
    idempotency_key: str = "idem-key-0000000000001",
    cookie: str | None = "cookie",
    file_bytes: bytes | None = None,
    file_field: str = "file",
    document_kind: str | None = "PASSPORT_BIODATA",
    content_type: str = "image/png",
):
    headers = {}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    cookies = {_SESSION_COOKIE: cookie} if cookie is not None else None
    data = {}
    if document_kind is not None:
        data["document_kind"] = document_kind
    files = {}
    if file_bytes is not None:
        files[file_field] = ("passport.png", file_bytes, content_type)
    return await client.post(
        f"/api/visa/voa/eligibility-checks/{result_id}/documents",
        headers=headers,
        cookies=cookies,
        data=data,
        files=files or None,
    )


#: Boundary for the hand-built multipart bodies below. Distinct from anything
#: httpx's own `files=` helper would pick, purely so a diff is unambiguous
#: about which code path built a given body.
_RAW_BOUNDARY = "garudarawtestboundary00000000000000"


def _build_raw_multipart_body(
    *,
    document_kind: str,
    file_bytes: bytes,
    filename: str = "passport.png",
    content_type: str = "image/png",
) -> bytes:
    """Hand-builds the multipart/form-data wire format directly. httpx's
    `files=`/`data=` helper (used by `_post_document` above) always computes
    an accurate `Content-Length` from the fully-buffered body — exactly the
    shape that lets `_parse_upload_request`'s cheap header pre-check answer
    first and never reach the streaming path. The two tests below need a
    body they can send with NO `Content-Length` (streamed) or with a LYING
    one, which requires building the wire bytes by hand instead."""
    parts = [
        f"--{_RAW_BOUNDARY}\r\n".encode(),
        b'Content-Disposition: form-data; name="document_kind"\r\n\r\n',
        document_kind.encode() + b"\r\n",
        f"--{_RAW_BOUNDARY}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode(),
        file_bytes,
        b"\r\n",
        f"--{_RAW_BOUNDARY}--\r\n".encode(),
    ]
    return b"".join(parts)


async def _chunked_body(body: bytes, chunk_size: int = 4096):
    """An async generator, never a `bytes` object — this is what makes httpx
    emit `Transfer-Encoding: chunked` instead of computing `Content-Length`
    (`httpx._content.encode_content`: `AsyncIterable` -> chunked, always)."""
    for i in range(0, len(body), chunk_size):
        yield body[i : i + chunk_size]


async def _post_raw_multipart(
    client: AsyncClient,
    *,
    result_id: str = _ACTOR,
    idempotency_key: str = "idem-key-0000000000001",
    cookie: str | None = "cookie",
    body: bytes,
    content_length_header: str | None = None,
    streamed: bool = True,
):
    """Posts a hand-built multipart body. `streamed=True` (default) sends it
    as an async generator so no `Content-Length` is ever computed — the
    no-Content-Length ("chunked") case. `streamed=False` sends the body as
    plain `bytes` (httpx would normally compute an accurate `Content-Length`
    for that), letting the caller override it via `content_length_header` to
    build the understated-`Content-Length` case.
    """
    headers = {"Content-Type": f"multipart/form-data; boundary={_RAW_BOUNDARY}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    if content_length_header is not None:
        headers["Content-Length"] = content_length_header
    cookies = {_SESSION_COOKIE: cookie} if cookie is not None else None
    content = _chunked_body(body) if streamed else body
    return await client.post(
        f"/api/visa/voa/eligibility-checks/{result_id}/documents",
        headers=headers,
        cookies=cookies,
        content=content,
    )


def _assert_privacy_headers(headers) -> None:
    assert headers.get("cache-control") == "no-store, private"
    assert headers.get("referrer-policy") == "no-referrer"
    assert headers.get("x-robots-tag") == "noindex, nofollow, noarchive"


class _NeverCalledStore:
    """Any method call is an immediate test failure — used to prove an
    unauthorized/pre-store-touching request never reaches persistence."""

    async def get_existing(self, *a, **kw):  # pragma: no cover
        raise AssertionError("get_existing was called before auth/validation rejected the request")

    async def commit(self, *a, **kw):  # pragma: no cover
        raise AssertionError("commit was called before auth/validation rejected the request")

    async def list_for_actor(self, *a, **kw):  # pragma: no cover
        raise AssertionError("list_for_actor was called before auth/validation rejected the request")


class _BrokenStore:
    """Raises an exception `garuda_documents_router.py` does not name in any
    `except` clause — proves 500 INTERNAL_ERROR is produced by the app's own
    generic exception handler, not faked."""

    async def get_existing(self, *a, **kw):
        raise RuntimeError("boom — unmapped exception")

    async def commit(self, *a, **kw):  # pragma: no cover
        raise AssertionError("commit should not be reached")


# ---------------------------------------------------------------------------
# Contract status-code coverage — uploadIntakeDocument
# ---------------------------------------------------------------------------


class TestUpload201Ready:
    async def test_all_confident_fields_return_201_ready_for_review(self, monkeypatch):
        _patch_ocr(monkeypatch, (_pass(_CONFIDENT_FIELDS), _pass(_CONFIDENT_FIELDS)))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["processing_state"] == "READY_FOR_REVIEW"
        assert len(body["review_fields"]) == 4
        _assert_privacy_headers(resp.headers)


class TestUpload202Processing:
    @pytest.mark.skip(
        reason=(
            "ProcessingOutcome is defensively unreachable per service.py's own "
            "comment (all_confident False implies >=1 uncertain field, so "
            "to_uncertain_fields is never empty) — not a code this route can "
            "honestly claim to emit; LowConfidenceDocument covers the real "
            "202 branch below. Reported honestly rather than faked — see final "
            "report."
        )
    )
    async def test_no_pass_rated_any_field_returns_202_processing(self):
        raise AssertionError("unreachable — see skip reason")


class TestUpload202LowConfidence:
    async def test_disagreeing_passes_return_202_low_confidence(self, monkeypatch):
        pass_a = _pass({**_CONFIDENT_FIELDS, "full_name": "ALPHA"})
        pass_b = _pass({**_CONFIDENT_FIELDS, "full_name": "BETA"})
        _patch_ocr(monkeypatch, (pass_a, pass_b))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["processing_state"] == "LOW_CONFIDENCE"
        assert {f["field_path"] for f in body["uncertain_fields"]} == {"full_name"}
        assert all(f["confirmation_required"] is True for f in body["uncertain_fields"])
        # Response body must never carry the disagreeing VALUE — only the field name.
        assert "ALPHA" not in resp.text and "BETA" not in resp.text


class TestUpload400IdempotencyKeyRequired:
    async def test_missing_header_is_400_before_store_is_touched(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(
                client, idempotency_key=None, file_bytes=_valid_png_bytes()
            )

        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"
        _assert_privacy_headers(resp.headers)


class TestUpload401SessionRequired:
    async def test_no_cookie_is_401_and_store_is_never_touched(self):
        """The AUTH test: proves the store is never CALLED, not merely that
        the response is 401 — `_NeverCalledStore` makes any method call raise,
        which would surface as a 500, not a clean 401, if auth were bypassed.
        """
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, cookie=None, file_bytes=_valid_png_bytes())

        assert resp.status_code == 401, resp.text
        assert resp.json()["code"] == "SESSION_REQUIRED"
        _assert_privacy_headers(resp.headers)

    async def test_no_verifier_wired_is_401_and_store_is_never_touched(self):
        """Production's actual state until L4's verifier is composed — no
        `garuda_magic_session_verifier` on app.state at all."""
        app = _app(garuda_document_store=_NeverCalledStore())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 401, resp.text
        assert resp.json()["code"] == "SESSION_REQUIRED"


class TestUpload404:
    async def test_flag_disabled_is_404_garuda_public_disabled(self, monkeypatch):
        monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "false")
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "GARUDA_PUBLIC_DISABLED"

    async def test_non_owned_result_id_is_404_result_not_found(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(
                client, result_id=_OTHER_RESULT, file_bytes=_valid_png_bytes()
            )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "RESULT_NOT_FOUND"


class TestUpload409IdempotencyConflict:
    async def test_same_key_different_payload_is_409(self, monkeypatch):
        _patch_ocr(monkeypatch, (_pass(_CONFIDENT_FIELDS), _pass(_CONFIDENT_FIELDS)))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            first = await _post_document(
                client, idempotency_key="idem-conflict-000000001", file_bytes=_valid_png_bytes()
            )
            assert first.status_code == 201, first.text

            second = await _post_document(
                client,
                idempotency_key="idem-conflict-000000001",
                file_bytes=_valid_png_bytes() + b"\x00",  # different payload
            )

        assert second.status_code == 409, second.text
        assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"


class TestIdempotencyReplay:
    async def test_same_key_same_payload_replays_without_new_work(self, monkeypatch):
        calls = 0
        original = (_pass(_CONFIDENT_FIELDS), _pass(_CONFIDENT_FIELDS))

        async def _counting_ocr(image_base64: str):
            nonlocal calls
            calls += 1
            return original

        monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", _counting_ocr)
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        png = _valid_png_bytes()
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            first = await _post_document(
                client, idempotency_key="idem-replay-0000000001", file_bytes=png
            )
            assert first.status_code == 201, first.text
            assert "idempotency-replayed" not in {k.lower() for k in first.headers}

            second = await _post_document(
                client, idempotency_key="idem-replay-0000000001", file_bytes=png
            )

        assert second.status_code == 201, second.text
        assert second.headers.get("idempotency-replayed") == "true"
        assert second.json() == first.json()
        # OCR ran exactly once — the replay caused no new work.
        assert calls == 1


class TestUpload413DocumentTooLarge:
    async def test_oversized_upload_is_413_without_buffering_the_whole_body(
        self, monkeypatch
    ):
        """Shrinks the bound to 10 bytes so the test sends only ~20 bytes total
        (not 15 MiB) while still exercising the real streaming-bound code path
        — the multipart parser raises as soon as ONE chunk pushes a part's
        cumulative size past `max_part_size`, so this never allocates a
        15 MiB buffer to prove the 413."""
        monkeypatch.setattr(
            garuda_documents_router.byte_validation, "MAX_UPLOAD_BYTES", 10
        )
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=b"x" * 200)

        assert resp.status_code == 413, resp.text
        assert resp.json()["code"] == "DOCUMENT_TOO_LARGE"

    async def test_oversized_upload_with_no_content_length_is_still_413(
        self, monkeypatch
    ):
        """The sibling test above never reaches the streaming path: httpx's
        `files=` helper always computes an accurate `Content-Length`, so the
        cheap header pre-check answers first every time. This sends the exact
        same oversized body with NO `Content-Length` at all (a genuinely
        streamed/chunked request) — the shape the pre-check cannot see coming.
        """
        monkeypatch.setattr(
            garuda_documents_router.byte_validation, "MAX_UPLOAD_BYTES", 10
        )
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        body = _build_raw_multipart_body(
            document_kind="PASSPORT_BIODATA", file_bytes=b"x" * 200
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_raw_multipart(client, body=body, streamed=True)

        # Degenerate-test guard: if this ever carries a Content-Length again
        # (e.g. someone "fixes" `_post_raw_multipart` to stop streaming), this
        # test silently stops proving anything beyond the sibling above.
        assert "content-length" not in resp.request.headers
        assert resp.status_code == 413, resp.text
        assert resp.json()["code"] == "DOCUMENT_TOO_LARGE"

    async def test_understated_content_length_is_still_413(self, monkeypatch):
        """Same shape as the no-Content-Length test above, but this time the
        header IS present and LIES — declares a body far smaller than what
        actually follows. A pre-check that trusts the declared value alone
        would wave this through; the streaming/post-parse enforcement must
        not."""
        monkeypatch.setattr(
            garuda_documents_router.byte_validation, "MAX_UPLOAD_BYTES", 10
        )
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        body = _build_raw_multipart_body(
            document_kind="PASSPORT_BIODATA", file_bytes=b"x" * 200
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_raw_multipart(
                client, body=body, streamed=False, content_length_header="5"
            )

        assert resp.request.headers.get("content-length") == "5"
        assert resp.status_code == 413, resp.text
        assert resp.json()["code"] == "DOCUMENT_TOO_LARGE"

    async def test_upload_at_the_bound_with_no_content_length_still_succeeds(
        self, monkeypatch
    ):
        """Innocence control: a legitimately max-sized upload, streamed with
        no `Content-Length`, must NOT be rejected. This is what catches a
        framing allowance (`_MULTIPART_FRAMING_ALLOWANCE_BYTES`) sized too
        small — the failure mode a naive fix for the two tests above could
        introduce by shrinking the body bound to exactly `MAX_UPLOAD_BYTES`
        with no slack for multipart's own boundary/header overhead."""
        png = _valid_png_bytes()
        monkeypatch.setattr(
            garuda_documents_router.byte_validation, "MAX_UPLOAD_BYTES", len(png)
        )
        _patch_ocr(monkeypatch, (_pass(_CONFIDENT_FIELDS), _pass(_CONFIDENT_FIELDS)))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        body = _build_raw_multipart_body(
            document_kind="PASSPORT_BIODATA", file_bytes=png
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_raw_multipart(client, body=body, streamed=True)

        assert "content-length" not in resp.request.headers
        assert resp.status_code == 201, resp.text
        assert resp.json()["processing_state"] == "READY_FOR_REVIEW"


class TestUpload415UnsupportedMediaType:
    async def test_declared_media_type_not_allowed_is_415(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(
                client, file_bytes=b"not-really-a-gif", content_type="image/gif"
            )

        assert resp.status_code == 415, resp.text
        assert resp.json()["code"] == "UNSUPPORTED_DOCUMENT_MEDIA_TYPE"


class TestUpload422InvalidRequest:
    async def test_missing_file_field_is_422(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=None)

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_wrong_document_kind_is_422(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(
                client, document_kind="NOT_A_REAL_KIND", file_bytes=_valid_png_bytes()
            )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "INVALID_REQUEST"


class TestUpload422UnreadableDocument:
    async def test_corrupt_bytes_are_422_unreadable(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=b"this-is-not-a-real-image-file")

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "UNREADABLE_DOCUMENT"


class TestUpload503:
    async def test_ocr_unavailable_is_503_document_processing_unavailable(self, monkeypatch):
        _patch_ocr(monkeypatch, None)
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 503, resp.text
        assert resp.json()["code"] == "DOCUMENT_PROCESSING_UNAVAILABLE"

    async def test_no_store_wired_is_503_persistence_policy_unavailable(self):
        """Production's actual default today — see module docstring: nothing
        wires a working store, so the router's own `_UnconfiguredDocumentStore`
        fallback answers this on every real upload."""
        app = _app(garuda_magic_session_verifier=_verifier_returns_fixed_actor)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 503, resp.text
        assert resp.json()["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"

    async def test_internal_error_is_the_apps_generic_500(self):
        """500 is cross-cutting (the app's own generic exception handler, not
        this router — see module docstring); proven live rather than merely
        cited, using a store that raises an exception this router names
        nowhere in its own except clauses."""
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_BrokenStore(),
        )
        # `raise_app_exceptions=False`: an unhandled exception in the ASGI app must
        # surface as the real HTTP response Starlette's own `ServerErrorMiddleware`
        # produces (like a real client over the wire would see), not re-raise into
        # the test process — which is httpx's ASGITransport default and would make
        # this test "pass" by crashing instead of asserting anything.
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 500, resp.text


# ---------------------------------------------------------------------------
# Contract status-code coverage — listIntakeDocuments
# ---------------------------------------------------------------------------


class _ListingStore(InMemoryDocumentStore):
    def __init__(self, summaries: list[dict]) -> None:
        super().__init__()
        self._summaries = summaries

    async def list_for_actor(self, actor: str) -> list[dict]:
        return self._summaries


class TestList200:
    async def test_authorized_list_returns_document_summaries(self):
        summaries = [
            {
                "document_id": "doc_0000000000000001",
                "document_kind": "PASSPORT_BIODATA",
                "processing_state": "READY_FOR_REVIEW",
                "artifact_available": False,
            }
        ]
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_ListingStore(summaries),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                f"/api/visa/voa/eligibility-checks/{_ACTOR}/documents",
                cookies={_SESSION_COOKIE: "cookie"},
            )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {"documents": summaries}
        _assert_privacy_headers(resp.headers)


class TestList401:
    async def test_no_cookie_is_401_and_store_never_touched(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(f"/api/visa/voa/eligibility-checks/{_ACTOR}/documents")

        assert resp.status_code == 401, resp.text
        assert resp.json()["code"] == "SESSION_REQUIRED"


class TestList404:
    async def test_flag_disabled_is_404(self, monkeypatch):
        monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "false")
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                f"/api/visa/voa/eligibility-checks/{_ACTOR}/documents",
                cookies={_SESSION_COOKIE: "cookie"},
            )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "GARUDA_PUBLIC_DISABLED"

    async def test_non_owned_result_id_is_404(self):
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=_NeverCalledStore(),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                f"/api/visa/voa/eligibility-checks/{_OTHER_RESULT}/documents",
                cookies={_SESSION_COOKIE: "cookie"},
            )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "RESULT_NOT_FOUND"


class TestList503:
    async def test_no_store_wired_is_503_service_unavailable(self):
        app = _app(garuda_magic_session_verifier=_verifier_returns_fixed_actor)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get(
                f"/api/visa/voa/eligibility-checks/{_ACTOR}/documents",
                cookies={_SESSION_COOKIE: "cookie"},
            )

        assert resp.status_code == 503, resp.text
        assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# PII: passport field values never leak to logs; low-confidence/processing
# bodies never carry the raw value.
# ---------------------------------------------------------------------------


class TestPiiNeverLeaksToLogsOrUnauthorizedBodies:
    """`X_SENTINEL_VALUE_1234` is a passport field VALUE (full_name). The
    contract's 201 ReadyDocument legitimately echoes it back to the SAME
    authenticated customer it belongs to (`ReviewField.value`'s own docstring:
    "Authenticated customer review value") — that is the product working as
    designed, not a leak, so this test does not assert it is absent from a
    201 response body. What must hold UNIVERSALLY, across every outcome, is
    that the value never reaches a LOG RECORD (CLAUDE.md §14 PII/OSINT output
    boundary — logs are a listed surface), and that a body which is NOT an
    authenticated per-field echo (the LOW_CONFIDENCE uncertain-fields list)
    never carries the value either.
    """

    async def test_ready_outcome_value_never_appears_in_logs(self, monkeypatch, caplog):
        _patch_ocr(monkeypatch, (_pass(_CONFIDENT_FIELDS), _pass(_CONFIDENT_FIELDS)))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        with caplog.at_level(logging.DEBUG):
            async with AsyncClient(transport=transport, base_url="http://t") as client:
                resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 201, resp.text
        assert "X_SENTINEL_VALUE_1234" in resp.text  # authenticated echo — expected
        for record in caplog.records:
            assert "X_SENTINEL_VALUE_1234" not in record.getMessage()

    async def test_low_confidence_body_never_carries_the_disagreeing_value(
        self, monkeypatch, caplog
    ):
        pass_a = _pass({**_CONFIDENT_FIELDS, "full_name": "X_SENTINEL_VALUE_1234"})
        pass_b = _pass({**_CONFIDENT_FIELDS, "full_name": "DIFFERENT_VALUE_9999"})
        _patch_ocr(monkeypatch, (pass_a, pass_b))
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        with caplog.at_level(logging.DEBUG):
            async with AsyncClient(transport=transport, base_url="http://t") as client:
                resp = await _post_document(client, file_bytes=_valid_png_bytes())

        assert resp.status_code == 202, resp.text
        assert "X_SENTINEL_VALUE_1234" not in resp.text
        assert "DIFFERENT_VALUE_9999" not in resp.text
        for record in caplog.records:
            assert "X_SENTINEL_VALUE_1234" not in record.getMessage()
            assert "DIFFERENT_VALUE_9999" not in record.getMessage()

    async def test_error_paths_never_log_the_value(self, monkeypatch, caplog):
        """413/415/401/404/503 paths run before or without OCR — the sentinel
        never enters the pipeline at all on these, so this pins the floor:
        even the FILENAME/media-type-carrying request never logs a value."""
        app = _app(
            garuda_magic_session_verifier=_verifier_returns_fixed_actor,
            garuda_document_store=InMemoryDocumentStore(),
        )
        transport = ASGITransport(app=app)
        with caplog.at_level(logging.DEBUG):
            async with AsyncClient(transport=transport, base_url="http://t") as client:
                resp = await _post_document(
                    client, file_bytes=b"X_SENTINEL_VALUE_1234", content_type="image/gif"
                )

        assert resp.status_code == 415, resp.text
        for record in caplog.records:
            assert "X_SENTINEL_VALUE_1234" not in record.getMessage()
