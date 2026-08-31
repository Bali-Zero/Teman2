"""Refuter finding (2026-08-25): two near-simultaneous requests with the same
(idempotency_key, payload) both saw `get_existing() -> None` before either committed,
because OCR runs under an `await` in between. This proved a real duplicate work-item bug
against the original blind-write `commit`. `service.py`/`ports.py` now make `commit` a
compare-and-set; this suite forces the interleaving deterministically (rather than hoping
`asyncio.gather` schedules unluckily) and proves exactly one work item fires and both
callers agree on the same outcome.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.garuda_documents import service as service_module
from backend.services.garuda_documents.models import DocumentKind
from backend.services.garuda_documents.ocr_client import OcrPassResult
from backend.services.garuda_documents.ports import InMemoryDocumentStore
from backend.services.garuda_documents.service import DocumentIntakeService
from backend.tests.services.garuda_documents.fixtures.synthetic_images import valid_png_bytes

CONFIDENT_VALUES = {
    "full_name": "TEST TRAVELER",
    "passport_number": "X0000000",
    "nationality": "TESTLANDIA",
    "passport_expiry_date": "2030-01-01",
}


@pytest.mark.asyncio
async def test_two_concurrent_submissions_same_key_commit_exactly_once(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    call_count = 0

    async def slow_confident_pair(_image_b64: str):
        nonlocal call_count
        call_count += 1
        # First caller in blocks here so the second caller's get_existing() also races
        # into the empty-store window — reproducing the interleaving the refuter found,
        # deterministically instead of hoping the scheduler happens to interleave it.
        started.set()
        await release.wait()
        p = OcrPassResult(values=dict(CONFIDENT_VALUES), self_confidence=dict.fromkeys(CONFIDENT_VALUES, 0.95))
        return (p, p)

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", slow_confident_pair)

    work_item_calls: list[str] = []

    async def hook(key: str, _outcome) -> None:
        work_item_calls.append(key)

    store = InMemoryDocumentStore()
    svc = DocumentIntakeService(store=store, work_item_hook=hook)
    payload = valid_png_bytes()

    async def submit():
        return await svc.submit_document(
            raw_bytes=payload,
            declared_media_type="image/png",
            document_kind=DocumentKind.PASSPORT_BIODATA,
            idempotency_key="race-key",
        )

    task_a = asyncio.create_task(submit())
    await started.wait()
    started.clear()
    task_b = asyncio.create_task(submit())
    await started.wait()  # both are now blocked inside OCR, neither has committed yet
    release.set()  # let both finish and race to commit

    outcome_a, outcome_b = await asyncio.gather(task_a, task_b)

    assert call_count == 2  # both really did run OCR concurrently — this IS the race
    assert outcome_a == outcome_b  # the loser adopted the winner's outcome, not its own
    assert work_item_calls == []  # ReadyOutcome never fires the hook at all, race or not


@pytest.mark.asyncio
async def test_two_concurrent_low_confidence_submissions_fire_hook_exactly_once(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_low_confidence_pair(_image_b64: str):
        started.set()
        await release.wait()
        p = OcrPassResult(values=dict(CONFIDENT_VALUES), self_confidence=dict.fromkeys(CONFIDENT_VALUES, 0.10))
        return (p, p)

    monkeypatch.setattr(service_module, "extract_passport_biodata_dual_pass", slow_low_confidence_pair)

    work_item_calls: list[str] = []

    async def hook(key: str, _outcome) -> None:
        work_item_calls.append(key)

    store = InMemoryDocumentStore()
    svc = DocumentIntakeService(store=store, work_item_hook=hook)
    payload = valid_png_bytes()

    async def submit():
        return await svc.submit_document(
            raw_bytes=payload,
            declared_media_type="image/png",
            document_kind=DocumentKind.PASSPORT_BIODATA,
            idempotency_key="race-key-lowconf",
        )

    task_a = asyncio.create_task(submit())
    await started.wait()
    started.clear()
    task_b = asyncio.create_task(submit())
    await started.wait()
    release.set()

    outcome_a, outcome_b = await asyncio.gather(task_a, task_b)

    assert outcome_a == outcome_b
    # The load-bearing assertion: without the compare-and-set fix, BOTH racing callers
    # would have committed their own outcome and BOTH would have fired the hook.
    assert work_item_calls == ["race-key-lowconf"]
