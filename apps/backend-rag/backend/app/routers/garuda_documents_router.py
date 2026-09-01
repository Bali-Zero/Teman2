"""HTTP shell for GARUDA VOA L5 — document upload + local-first OCR (hinge only).

Implements exactly the two operations `products/garuda-voa/contracts/openapi.yaml`
declares for `/api/visa/voa/eligibility-checks/{result_id}/documents`:
`uploadIntakeDocument` (POST) and `listIntakeDocuments` (GET). Every business rule
(byte validation, OCR, confidence classification, redaction) lives in
`backend.services.garuda_documents` (L5, MERGED #4870) and is called, never
reimplemented, here — this file's only job is translating HTTP <-> that service.

Registered in `router_manifest.py` / `router_registration.py` (`_API`, mirrors
`garuda_voa_public`/`garuda_orders_router` — mount unconditionally, flag
`GARUDA_PUBLIC_ENABLED` re-checked per-request by this module's own
`_require_flag`, wired as a ROUTER-LEVEL dependency so it resolves before every
other `Depends()` and before body parsing, same ordering argument as
`garuda_orders_router.py`'s comment above its own `router = APIRouter(...)`).

WHY THIS ROUTER FAILS CLOSED IN PRODUCTION TODAY (deliberate, not a bug):
`git log` PR #5120 ("the L5 document/OCR lane has no HTTP surface — and the Mini
probe lies") found three stacked blockers, in order: (1) `garuda_documents/ports.py`
ships only `InMemoryDocumentStore`, whose own docstring says it "must never be
wired into a running service" — L1's retention-covered store has not merged for
this table (`ports.py` module docstring: "no garuda-scoped documents migration
exists"), and LANES.md is explicit that a lane must not persist a row before L1
covers it; (2) OCR's only sanctioned host (`qwen2.5vl:7b`) sits on the Mini/Pro
tailnet, not reachable from Fly — a sovereignty/architecture call, not a config
change; (3) then this router. Building this router does not solve (1) or (2), and
must not pretend to: `get_document_store()` below defaults to
`_UnconfiguredDocumentStore`, the documents-lane analogue of
`garuda_flow.public_api.UnconfiguredCheckStore` — every real call answers 503
`PERSISTENCE_POLICY_UNAVAILABLE`/`SERVICE_UNAVAILABLE`, and OCR is never reached
in that path (the store rejection happens before `service.submit_document` gets
to the OCR call). The moment L1 ships a real `DocumentStorePort` adapter and (2)
is resolved, swapping `app.state.garuda_document_store` in `service_initializer.py`
is the only change needed — no router or contract edit — exactly the seam
`garuda_flow/public_api.py`'s own module docstring describes for CheckStore.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.formparsers import MultiPartException, MultiPartParser

from backend.services.garuda_documents import byte_validation
from backend.services.garuda_documents.errors import (
    DocumentTooLargeError,
    UnsupportedMediaTypeError,
)
from backend.services.garuda_documents.models import (
    DocumentKind,
    DocumentOutcome,
    LowConfidenceOutcome,
    ProcessingOutcome,
    ReadyOutcome,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ports import (
    DocumentStorePort,
    IdempotencyConflictError,
)
from backend.services.garuda_documents.service import (
    DocumentIntakeService,
    DocumentProcessingUnavailableError,
)

logger = logging.getLogger(__name__)

_FLAG_ENV_VAR = "GARUDA_PUBLIC_ENABLED"


def _flag_enabled() -> bool:
    # Same permissive reader as garuda_voa_public/garuda_orders_router/
    # garuda_portal_auth (LANES.md file-ownership discipline: a same-shaped
    # LOCAL copy per file, never a shared import) — trimmed, case-insensitive,
    # accepts "1"/"true"/"yes". A stricter/looser reader here would open this
    # one surface out of step with the other three (the exact W-shaped bug
    # `garuda_orders_router.py::_flag_enabled` was corrected for).
    return os.environ.get(_FLAG_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


def _require_flag() -> None:
    if not _flag_enabled():
        raise HTTPException(
            status_code=404, detail={"code": "GARUDA_PUBLIC_DISABLED", "retryable": False}
        )


class _ContractErrorRoute(APIRoute):
    """Rewrite every `HTTPException` this router raises into the frozen
    `errors.yaml` envelope, with the same privacy headers a success path gets.

    Same-shaped local copy of `garuda_orders_router.py`'s route class (LANES.md
    discipline) — see that file's docstring for the full ordering argument on
    why catching `HTTPException` here covers router-level dependency, parameter
    dependency, and handler-body raises uniformly.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        downstream = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await downstream(request)
            except HTTPException as exc:
                code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
                if code not in _ERROR_CATALOG:
                    raise
                return _error(code)

        return handler


router = APIRouter(
    prefix="/api/visa/voa",
    tags=["garuda-documents"],
    route_class=_ContractErrorRoute,
    dependencies=[Depends(_require_flag)],
)


def _privacy_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


#: `errors.yaml` — (http_status, retryable, message_key), restricted to the
#: codes THIS router's own call sites can ever emit (500/429 are cross-cutting
#: — the app-wide exception handler / rate-limit middleware — never raised
#: here directly, same posture as `garuda_voa_public.py`'s own comment).
_ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "GARUDA_PUBLIC_DISABLED": (404, False, "garuda_voa.error.unavailable"),
    "SESSION_REQUIRED": (401, False, "garuda_voa.error.session_required"),
    "IDEMPOTENCY_KEY_REQUIRED": (400, False, "garuda_voa.error.idempotency_key_required"),
    "RESULT_NOT_FOUND": (404, False, "garuda_voa.error.result_not_found"),
    "IDEMPOTENCY_CONFLICT": (409, False, "garuda_voa.error.idempotency_conflict"),
    "DOCUMENT_TOO_LARGE": (413, False, "garuda_voa.error.document_too_large"),
    "UNSUPPORTED_DOCUMENT_MEDIA_TYPE": (
        415,
        False,
        "garuda_voa.error.unsupported_document_media_type",
    ),
    "INVALID_REQUEST": (422, False, "garuda_voa.error.invalid_request"),
    "UNREADABLE_DOCUMENT": (422, False, "garuda_voa.error.unreadable_document"),
    "PERSISTENCE_POLICY_UNAVAILABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "DOCUMENT_PROCESSING_UNAVAILABLE": (
        503,
        True,
        "garuda_voa.error.document_processing_unavailable",
    ),
    "SERVICE_UNAVAILABLE": (503, True, "garuda_voa.error.service_unavailable"),
}


def _error(code: str) -> JSONResponse:
    status_code, retryable, message_key = _ERROR_CATALOG[code]
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "retryable": retryable, "message_key": message_key},
    )
    _privacy_headers(response)
    return response


class _PersistenceUnavailable(Exception):
    """Raised by `_UnconfiguredDocumentStore` on every call — see its docstring."""


class _UnconfiguredDocumentStore:
    """Fail-closed `DocumentStorePort` default — the documents-lane analogue of
    `garuda_flow.public_api.UnconfiguredCheckStore`.

    Not a placeholder to delete later: it is the correct behaviour for as long
    as no retention-covered store exists for `garuda_documents` (module
    docstring above). Holds no bytes and no state; every call raises
    `_PersistenceUnavailable`, which the handlers below map to the contract's
    503 codes. `list_for_actor` is not part of `DocumentStorePort` (`ports.py`
    has no enumeration method at all — a genuine gap, not an oversight this
    router papers over); it is this router's own minimal extension so
    `listIntakeDocuments` has something to call, structurally satisfied by
    duck typing rather than a change to L5's frozen `ports.py`.
    """

    async def get_existing(self, _idempotency_key: str, _payload_hash: str) -> DocumentOutcome | None:
        raise _PersistenceUnavailable()

    async def commit(self, _idempotency_key: str, _payload_hash: str, _outcome: DocumentOutcome) -> bool:
        raise _PersistenceUnavailable()

    async def list_for_actor(self, _actor: str) -> list[dict]:
        raise _PersistenceUnavailable()


_default_store: DocumentStorePort = _UnconfiguredDocumentStore()


def get_document_store(request: Request) -> DocumentStorePort:
    """Reads `app.state.garuda_document_store`, wired by `service_initializer.py`.

    Same `getattr(..., None) or default` shape `garuda_voa_public.get_garuda_check_store`
    uses (never `app.dependency_overrides` for the PRODUCTION default — that dict is
    FastAPI's test mechanism and a process-wide global one unrelated test's teardown
    can clear). Tests override this dependency directly via
    `app.dependency_overrides[get_document_store]`.
    """
    return getattr(request.app.state, "garuda_document_store", None) or _default_store


class _ReplayTrackingStore:
    """Wraps a `DocumentStorePort` to observe whether `DocumentIntakeService.submit_document`
    took the short-circuit existing-outcome path — the one signal that method does not
    return directly (it returns only the outcome, never a `(outcome, replayed)` pair,
    unlike `garuda_orders/repository.py::create_order_and_checkout`). Delegates every
    call unchanged; adds no persistence semantics and duplicates no hashing/business
    logic — it only watches the SAME `get_existing` call `service.py` already makes.

    `replayed` also goes True on the race-lost branch inside `submit_document` (a
    second `get_existing` call after `commit` loses a race) — correct: the response
    the caller receives there IS a previously (concurrently) committed outcome, not
    freshly produced by this call, which is exactly what the header promises.
    """

    def __init__(self, inner: DocumentStorePort) -> None:
        self._inner = inner
        self.replayed = False

    async def get_existing(self, idempotency_key: str, payload_hash: str) -> DocumentOutcome | None:
        existing = await self._inner.get_existing(idempotency_key, payload_hash)
        if existing is not None:
            self.replayed = True
        return existing

    async def commit(self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome) -> bool:
        return await self._inner.commit(idempotency_key, payload_hash, outcome)


async def _require_magic_session_actor(request: Request) -> str:
    """Same-shaped local copy of `garuda_orders_router.py`'s helper (LANES.md
    discipline). Fails closed with SESSION_REQUIRED until the orchestrator wires
    L4's real verifier onto `app.state.garuda_magic_session_verifier`. Returned
    value is the session's own `result_id`, used both as the idempotency-scoping
    actor and the ownership key every read/write below filters on.
    """
    verifier = getattr(request.app.state, "garuda_magic_session_verifier", None)
    cookie = request.cookies.get("garuda_session")
    if verifier is None or not cookie:
        raise HTTPException(status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False})
    actor = await verifier(cookie)
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False})
    return actor


def _idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or len(idempotency_key) < 16 or len(idempotency_key) > 200:
        raise HTTPException(
            status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "retryable": False}
        )
    return idempotency_key


def _require_owned_result(result_id: str, actor: str) -> None:
    """`actor` IS the session's own result_id (see `_require_magic_session_actor`'s
    docstring) — a path `result_id` that does not match it is either malformed,
    absent, or someone else's check. Same 404 RESULT_NOT_FOUND shape for all
    three, deliberately: distinguishing them would open an enumeration oracle
    (`garuda_orders_router.create_order_from_check` makes the identical call).
    """
    if result_id != actor:
        raise HTTPException(status_code=404, detail={"code": "RESULT_NOT_FOUND", "retryable": False})


def _scoped_key(*, actor: str, result_id: str, raw_key: str) -> str:
    """Local scoping (LANES.md discipline: no cross-lane import of
    `garuda_orders.idempotency`) — `DocumentStorePort` itself has no actor/result
    concept (`ports.py` keys purely on the caller-supplied string), so without this
    two different customers' documents could collide on the same literal
    client-supplied Idempotency-Key value.
    """
    digest = hashlib.sha256()
    for part in (actor, result_id, "uploadIntakeDocument", raw_key):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


class _RequestBodyTooLarge(Exception):
    """Raised by `_bounded_body_stream` the instant the running total of bytes
    read from the raw ASGI request stream would exceed the configured limit —
    BEFORE the chunk that would push it over is ever yielded downstream. This
    is what actually bounds memory here: measured empirically against the
    installed Starlette (1.3.1), `MultiPartParser`'s own `max_part_size` only
    bounds a non-file form FIELD (`formparsers.py::on_part_data`, the
    `self._current_part.file is None` branch) — for a FILE part it writes
    every chunk straight to a `SpooledTemporaryFile` with no size check
    whatsoever. So `max_part_size` alone would never reject an oversized
    upload; this exception is the real backstop.
    """


# Multipart framing (boundary lines, per-part `Content-Disposition`/`Content-Type`
# headers, trailing CRLFs) makes the RAW BODY of a legitimately
# MAX_UPLOAD_BYTES-sized upload a little larger than the file it carries. This
# allowance is sized generously above that framing overhead for a single-file
# upload specifically so a legal max-size upload is never rejected by the body
# bound below — it is not itself a size limit on anything.
_MULTIPART_FRAMING_ALLOWANCE_BYTES = 64 * 1024  # 64 KiB


async def _bounded_body_stream(request: Request, limit: int) -> AsyncGenerator[bytes, None]:
    """Wraps `request.stream()`, counting bytes as they arrive from the ASGI
    receive channel and raising `_RequestBodyTooLarge` the moment the running
    total would exceed `limit` — without yielding the chunk that pushes it
    over. Memory stays bounded by construction: this never lets more than
    `limit` bytes of the body reach the multipart parser (and, transitively,
    its `SpooledTemporaryFile`), regardless of `Content-Length`.
    """
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise _RequestBodyTooLarge()
        yield chunk


async def _parse_upload_request(request: Request) -> tuple[DocumentKind, bytes, str]:
    """Parses the multipart body with the size bound enforced DURING streaming.

    Deliberately does NOT call `request.form()`. Starlette 1.3.1's
    `Request._get_form` wraps its own parser call in
    `except MultiPartException as exc: if "app" in self.scope: raise
    HTTPException(status_code=400, detail=exc.message)` — every real request
    through this (or any) ASGI app has `"app"` in scope, so a
    `MultiPartException` raised inside `request.form()` NEVER reaches this
    function as itself; it always surfaces as a plain Starlette
    `HTTPException(400, detail=<human-facing string>)` instead. Classifying
    that would mean pattern-matching a message string — guard-over/under-match
    (repo scar family #3) — instead of an exception TYPE. Driving
    `MultiPartParser` directly (bypassing `request.form()`/`_get_form`
    entirely) keeps `MultiPartException` a real, catchable type here.

    The actual size bound is `_bounded_body_stream` above, not
    `MultiPartParser`'s own `max_part_size` — see `_RequestBodyTooLarge`'s
    docstring: `max_part_size` never bounds the FILE part on this Starlette
    version. `max_part_size` is still passed, set to the same body limit, so
    it cannot reject anything `_bounded_body_stream` wouldn't already have
    rejected first, and it still catches a pathologically oversized non-file
    field (e.g. `document_kind`).
    """
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > byte_validation.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "retryable": False})

    # Read the file bound fresh on every call (never cache/close over it as a
    # module-level constant) — tests monkeypatch `byte_validation.MAX_UPLOAD_BYTES`
    # per-case, and a frozen constant would go stale the moment it did.
    body_limit = byte_validation.MAX_UPLOAD_BYTES + _MULTIPART_FRAMING_ALLOWANCE_BYTES

    try:
        parser = MultiPartParser(
            request.headers,
            _bounded_body_stream(request, body_limit),
            max_part_size=body_limit,
        )
        form = await parser.parse()
    except _RequestBodyTooLarge:
        raise HTTPException(status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "retryable": False})
    except MultiPartException as exc:
        # Malformed body (missing boundary, no Content-Disposition `name`, an
        # oversized non-file field, ...) — genuinely un-wrapped here, unlike
        # `request.form()` (see this function's docstring).
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}) from exc

    raw_kind = form.get("document_kind")
    upload = form.get("file")
    if not isinstance(raw_kind, str) or not hasattr(upload, "read"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    try:
        document_kind = DocumentKind(raw_kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}) from exc

    raw_bytes = await upload.read()
    # Safe to buffer the whole file here without a fresh unbounded-memory risk:
    # `_bounded_body_stream` already capped the ENTIRE raw body (this file's
    # bytes included) at `body_limit`, so `raw_bytes` can never be larger than
    # that regardless of what happens below. This check enforces the tighter,
    # precise per-FILE rule (`MAX_UPLOAD_BYTES`) that `body_limit` deliberately
    # leaves slack for — see `_MULTIPART_FRAMING_ALLOWANCE_BYTES`.
    if len(raw_bytes) > byte_validation.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "retryable": False})
    declared_media_type = upload.content_type or ""
    return document_kind, raw_bytes, declared_media_type


#: Status codes documented for THIS operation, matching the frozen contract's
#: declared set exactly (verified by `test_garuda_voa_openapi_parity.py`).
#: Documentation only (`responses=` in the decorators below) — same shape as
#: `garuda_orders_router.py::_OPERATION_STATUS_CODES`, which documents 500
#: for the same reason: it IS genuinely reachable (any unhandled exception in
#: either handler reaches the app-wide `general_exception_handler`, proven
#: live by `TestUpload503::test_internal_error_is_the_apps_generic_500`), it
#: is simply never raised by a `raise HTTPException(...)` call site in THIS
#: file, so FastAPI would not otherwise put it in the generated schema. 429
#: is not in the frozen contract's set for either operation here, unlike
#: some `garuda_orders_router.py` operations, so it is correctly absent.
_OPERATION_STATUS_CODES: dict[str, tuple[int, ...]] = {
    "uploadIntakeDocument": (201, 202, 400, 401, 404, 409, 413, 415, 422, 500, 503),
    "listIntakeDocuments": (200, 401, 404, 500, 503),
}


def _status_responses(operation_id: str) -> dict[int, dict[str, object]]:
    return {
        status_code: {"description": "See `products/garuda-voa/contracts/errors.yaml`."}
        for status_code in _OPERATION_STATUS_CODES[operation_id]
    }


def _serialize_outcome(outcome: DocumentOutcome) -> tuple[int, dict]:
    """Literal translation of `ReadyDocument`/`ProcessingDocument`/`LowConfidenceDocument`
    (openapi.yaml components, ~line 1203) — never invents a field the contract
    doesn't declare.
    """
    if isinstance(outcome, ReadyOutcome):
        return 201, {
            "document_id": outcome.document_id,
            "processing_state": outcome.processing_state.value,
            "review_fields": [
                {
                    "field_path": f.field_path.value,
                    "value": f.value,
                    "confirmation_required": f.confirmation_required,
                }
                for f in outcome.review_fields
            ],
        }
    if isinstance(outcome, ProcessingOutcome):
        return 202, {
            "document_id": outcome.document_id,
            "processing_state": outcome.processing_state.value,
        }
    if isinstance(outcome, LowConfidenceOutcome):
        return 202, {
            "document_id": outcome.document_id,
            "processing_state": outcome.processing_state.value,
            "uncertain_fields": [
                {"field_path": f.field_path.value, "confirmation_required": f.confirmation_required}
                for f in outcome.uncertain_fields
            ],
        }
    # UnreadableOutcome — models.py's own docstring: "The router (L2) is
    # responsible for mapping it to the 422 error envelope." Handled by the
    # caller via isinstance-else, not reachable here.
    raise AssertionError(f"unhandled outcome type: {type(outcome).__name__}")


@router.post(
    "/eligibility-checks/{result_id}/documents",
    status_code=201,
    operation_id="uploadIntakeDocument",
    responses=_status_responses("uploadIntakeDocument"),
    response_model=None,
)
async def upload_intake_document(
    result_id: str,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    store: DocumentStorePort = Depends(get_document_store),
) -> dict | Response:
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    key = _idempotency_key(idempotency_key)
    _require_owned_result(result_id, actor)

    document_kind, raw_bytes, declared_media_type = await _parse_upload_request(request)
    scoped_key = _scoped_key(actor=actor, result_id=result_id, raw_key=key)

    tracking_store = _ReplayTrackingStore(store)
    service = DocumentIntakeService(store=tracking_store)

    try:
        outcome = await service.submit_document(
            raw_bytes=raw_bytes,
            declared_media_type=declared_media_type,
            document_kind=document_kind,
            idempotency_key=scoped_key,
        )
    except UnsupportedMediaTypeError as exc:
        raise HTTPException(
            status_code=415, detail={"code": "UNSUPPORTED_DOCUMENT_MEDIA_TYPE", "retryable": False}
        ) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "retryable": False}
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "retryable": False}
        ) from exc
    except DocumentProcessingUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail={"code": "DOCUMENT_PROCESSING_UNAVAILABLE", "retryable": True}
        ) from exc
    except _PersistenceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PERSISTENCE_POLICY_UNAVAILABLE", "retryable": False}
        ) from exc

    if tracking_store.replayed:
        response.headers["Idempotency-Replayed"] = "true"

    # UnreadableOutcome carries no PII (only `document_id`) and maps to the 422
    # error envelope per models.py's own docstring — returned via `_error()`
    # directly rather than through `_serialize_outcome`'s isinstance ladder.
    if isinstance(outcome, UnreadableOutcome):
        return _error("UNREADABLE_DOCUMENT")

    status_code, body = _serialize_outcome(outcome)
    response.status_code = status_code
    return body


@router.get(
    "/eligibility-checks/{result_id}/documents",
    operation_id="listIntakeDocuments",
    responses=_status_responses("listIntakeDocuments"),
)
async def list_intake_documents(
    result_id: str,
    request: Request,
    response: Response,
    store: DocumentStorePort = Depends(get_document_store),
) -> dict:
    """Customer-safe metadata only (contract: `DocumentList` -> `DocumentSummary`).

    `list_for_actor` is NOT part of `DocumentStorePort` (`ports.py` has no
    enumeration method at all today — see `_UnconfiguredDocumentStore`'s
    docstring) — called via duck typing so this endpoint has something to call
    without editing L5's frozen file; any store that lacks it, or that raises,
    answers the contract's single documented 503 `SERVICE_UNAVAILABLE`, never a
    stack trace or raw OCR diagnostic.
    """
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    _require_owned_result(result_id, actor)

    list_for_actor = getattr(store, "list_for_actor", None)
    if list_for_actor is None:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True})
    try:
        summaries = await list_for_actor(actor)
    except _PersistenceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        ) from exc

    return {"documents": summaries}
