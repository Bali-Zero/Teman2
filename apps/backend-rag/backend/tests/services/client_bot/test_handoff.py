"""ClientHandoffService — the durable-insert-before-return contract F10
requires. See handoff.py's own module docstring.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

from backend.channels.profiles import CLIENT_WA_V1
from backend.services.client_bot.contracts import HistoryRole
from backend.services.client_bot.policy.handoff import (
    ClientHandoffService,
    HandoffOutcome,
    HandoffRecord,
)
from backend.tests.duebot.goldens.builders import (
    make_brain_request,
    make_canonical_message,
    make_grounding_bundle,
    make_handoff_candidate,
    make_history_turn,
)


class _RecordingRepository:
    def __init__(self, *, insert_result: bool = True, raise_instead: bool = False) -> None:
        self.insert_result = insert_result
        self.raise_instead = raise_instead
        self.inserted_records: list[HandoffRecord] = []

    async def insert(self, record: HandoffRecord) -> bool:
        if self.raise_instead:
            raise RuntimeError("simulated repository failure")
        self.inserted_records.append(record)
        return self.insert_result


def _request(case_id: str = "handoff-case", history=()):
    message = make_canonical_message(case_id)
    grounding = make_grounding_bundle(case_id, history=history)
    return make_brain_request(case_id, message=message, profile=CLIENT_WA_V1, grounding=grounding)


@pytest.mark.asyncio
async def test_no_repository_wired_reports_insert_failed() -> None:
    service = ClientHandoffService()
    outcome = await service.create_handoff(make_handoff_candidate("handoff-case"), _request())
    assert outcome == HandoffOutcome.ROW_INSERT_FAILED


@pytest.mark.asyncio
async def test_repository_success_reports_row_inserted() -> None:
    repository = _RecordingRepository(insert_result=True)
    service = ClientHandoffService(repository)
    outcome = await service.create_handoff(make_handoff_candidate("handoff-case"), _request())
    assert outcome == HandoffOutcome.ROW_INSERTED
    assert len(repository.inserted_records) == 1


@pytest.mark.asyncio
async def test_repository_returning_false_reports_insert_failed() -> None:
    repository = _RecordingRepository(insert_result=False)
    service = ClientHandoffService(repository)
    outcome = await service.create_handoff(make_handoff_candidate("handoff-case"), _request())
    assert outcome == HandoffOutcome.ROW_INSERT_FAILED


@pytest.mark.asyncio
async def test_repository_raising_is_caught_and_reports_insert_failed() -> None:
    repository = _RecordingRepository(raise_instead=True)
    service = ClientHandoffService(repository)
    outcome = await service.create_handoff(make_handoff_candidate("handoff-case"), _request())
    assert outcome == HandoffOutcome.ROW_INSERT_FAILED


@pytest.mark.asyncio
async def test_context_carried_reflects_nonempty_history() -> None:
    repository = _RecordingRepository(insert_result=True)
    service = ClientHandoffService(repository)
    turn = make_history_turn(HistoryRole.USER, "pertanyaan sebelumnya")
    await service.create_handoff(make_handoff_candidate("handoff-case"), _request(history=(turn,)))
    assert repository.inserted_records[0].context_carried is True


@pytest.mark.asyncio
async def test_no_history_means_context_not_carried() -> None:
    repository = _RecordingRepository(insert_result=True)
    service = ClientHandoffService(repository)
    await service.create_handoff(make_handoff_candidate("handoff-case"), _request())
    assert repository.inserted_records[0].context_carried is False


@pytest.mark.asyncio
async def test_handoff_reason_code_is_carried_into_the_record() -> None:
    repository = _RecordingRepository(insert_result=True)
    service = ClientHandoffService(repository)
    candidate = make_handoff_candidate("handoff-case", handoff_reason_code="PRICE_DISPUTE")
    await service.create_handoff(candidate, _request())
    assert repository.inserted_records[0].handoff_reason_code == "PRICE_DISPUTE"
