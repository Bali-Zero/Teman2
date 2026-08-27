"""Service-level exercise of corrupt-photo-upload.feature and uncertain-ocr.feature.

Uses a deterministic stubbed OCR pass (monkeypatched) rather than the live model, so this
suite is fast and never flaky on model availability. `test_ocr_client_live.py` proves the
real qwen2.5vl:7b call separately.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_documents import service as service_module
from backend.services.garuda_documents.models import (
    DocumentKind,
    LowConfidenceOutcome,
    ReadyOutcome,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ocr_client import OcrPassResult
from backend.services.garuda_documents.ports import IdempotencyConflictError, InMemoryDocumentStore
from backend.services.garuda_documents.service import (
    DocumentIntakeService,
    DocumentProcessingUnavailableError,
)
from backend.tests.services.garuda_documents.fixtures.synthetic_images import (
    truncated_png_bytes,
    valid_png_bytes,
)

CONFIDENT_VALUES = {
    "full_name": "TEST TRAVELER",
    "passport_number": "X0000000",
    "nationality": "TESTLANDIA",
    "passport_expiry_date": "2030-01-01",
}


def _confident_pair():
    p = OcrPassResult(values=dict(CONFIDENT_VALUES), self_confidence=dict.fromkeys(CONFIDENT_VALUES, 0.95))
    return (p, p)


def _low_confidence_pair():
    p = OcrPassResult(values=dict(CONFIDENT_VALUES), self_confidence=dict.fromkeys(CONFIDENT_VALUES, 0.10))
    return (p, p)


@pytest.fixture
def store():
    return InMemoryDocumentStore()


async def _new_service(store, monkeypatch, pair_factory):
    async def fake_dual_pass(_image_b64: str):
        return pair_factory()

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", fake_dual_pass)
    return DocumentIntakeService(store=store)


@pytest.mark.asyncio
async def test_corrupt_upload_returns_unreadable_document_outcome(store, monkeypatch):
    svc = await _new_service(store, monkeypatch, _confident_pair)
    outcome = await svc.submit_document(
        raw_bytes=truncated_png_bytes(),
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-corrupt-1",
    )
    assert isinstance(outcome, UnreadableOutcome)


@pytest.mark.asyncio
async def test_corrupt_upload_retry_same_key_replays_without_second_outcome(store, monkeypatch):
    """corrupt-photo-upload.feature: 'the same outcome is returned without a second work
    item, document row, image OCR job' — bite-checked below by asserting the OCR stub is
    invoked at most 0 times for a corrupt upload (unreadable bytes short-circuit before
    OCR ever runs) on both the first AND the replayed call.
    """
    calls = 0

    async def counting_dual_pass(_image_b64: str):
        nonlocal calls
        calls += 1
        return _confident_pair()

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", counting_dual_pass)
    svc = DocumentIntakeService(store=store)
    payload = truncated_png_bytes()

    first = await svc.submit_document(
        raw_bytes=payload,
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-corrupt-retry",
    )
    second = await svc.submit_document(
        raw_bytes=payload,
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-corrupt-retry",
    )
    assert first == second
    assert isinstance(first, UnreadableOutcome)
    assert calls == 0  # OCR never runs on unreadable bytes, on either attempt


@pytest.mark.asyncio
async def test_low_confidence_fields_are_never_silently_accepted_as_verified(store, monkeypatch):
    svc = await _new_service(store, monkeypatch, _low_confidence_pair)
    outcome = await svc.submit_document(
        raw_bytes=valid_png_bytes(),
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-lowconf-1",
    )
    assert isinstance(outcome, LowConfidenceOutcome)
    assert len(outcome.uncertain_fields) == len(CONFIDENT_VALUES)
    assert all(f.confirmation_required for f in outcome.uncertain_fields)


@pytest.mark.asyncio
async def test_low_confidence_retry_same_event_produces_no_second_mutation(store, monkeypatch):
    work_item_calls: list[str] = []

    async def hook(key: str, _outcome) -> None:
        work_item_calls.append(key)

    async def fake_dual_pass(_image_b64: str):
        return _low_confidence_pair()

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", fake_dual_pass)
    svc = DocumentIntakeService(store=store, work_item_hook=hook)
    payload = valid_png_bytes()

    await svc.submit_document(
        raw_bytes=payload,
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-lowconf-retry",
    )
    await svc.submit_document(
        raw_bytes=payload,
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-lowconf-retry",
    )
    assert work_item_calls == ["key-lowconf-retry"]  # exactly one, not two


@pytest.mark.asyncio
async def test_confident_upload_returns_ready_document(store, monkeypatch):
    svc = await _new_service(store, monkeypatch, _confident_pair)
    outcome = await svc.submit_document(
        raw_bytes=valid_png_bytes(),
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-ready-1",
    )
    assert isinstance(outcome, ReadyOutcome)
    assert len(outcome.review_fields) == len(CONFIDENT_VALUES)


@pytest.mark.asyncio
async def test_ready_document_never_fires_the_work_item_hook(store, monkeypatch):
    calls: list[str] = []

    async def hook(key: str, _outcome) -> None:
        calls.append(key)

    async def fake_dual_pass(_image_b64: str):
        return _confident_pair()

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", fake_dual_pass)
    svc = DocumentIntakeService(store=store, work_item_hook=hook)
    await svc.submit_document(
        raw_bytes=valid_png_bytes(),
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="key-ready-no-workitem",
    )
    assert calls == []


@pytest.mark.asyncio
async def test_different_payload_under_same_idempotency_key_conflicts(store, monkeypatch):
    svc = await _new_service(store, monkeypatch, _confident_pair)
    await svc.submit_document(
        raw_bytes=valid_png_bytes(width=10, height=10),
        declared_media_type="image/png",
        document_kind=DocumentKind.PASSPORT_BIODATA,
        idempotency_key="shared-key",
    )
    with pytest.raises(IdempotencyConflictError):
        await svc.submit_document(
            raw_bytes=valid_png_bytes(width=99, height=99),
            declared_media_type="image/png",
            document_kind=DocumentKind.PASSPORT_BIODATA,
            idempotency_key="shared-key",
        )


@pytest.mark.asyncio
async def test_ocr_pipeline_unavailable_raises_and_persists_nothing(store, monkeypatch):
    async def unavailable(_image_b64: str):
        return None

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", unavailable)
    svc = DocumentIntakeService(store=store)
    with pytest.raises(DocumentProcessingUnavailableError):
        await svc.submit_document(
            raw_bytes=valid_png_bytes(),
            declared_media_type="image/png",
            document_kind=DocumentKind.PASSPORT_BIODATA,
            idempotency_key="key-unavailable",
        )
    # No outcome was ever committed for this key — a later retry once OCR is back up
    # must be free to succeed, not replay a failure.
    assert await store.get_existing("key-unavailable", "irrelevant") is None
