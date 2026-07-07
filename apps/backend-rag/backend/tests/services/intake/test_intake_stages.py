"""Unit tests for the real intake stage dispatcher."""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import stages


class _FakePool:
    def __init__(self, stage_output: dict[str, Any]) -> None:
        self.stage_output = stage_output

    async def fetchrow(self, query: str, queue_id: int) -> dict[str, Any]:  # noqa: ARG002
        return {"stage_output": self.stage_output}


@pytest.mark.asyncio
async def test_extract_can_skip_fields_for_proposal_only_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in rollout flag must avoid the heavy SEA-LION extract call."""

    async def _should_not_extract(job: dict[str, Any], stage: str) -> dict[str, Any]:
        raise AssertionError("extract_stage should not run when proposal-only skip is enabled")

    monkeypatch.setenv("INTAKE_PROPOSAL_ONLY_SKIP_EXTRACT", "1")
    monkeypatch.setattr(stages, "extract_stage", _should_not_extract)

    handler = stages.build_real_stage_handler(
        _FakePool(
            {
                "classify": {
                    "doc_type": "payment_receipt",
                    "ocr_text_per_page": [{"text": "receipt text"}],
                }
            }
        )
    )

    out = await handler({"id": 123}, "extract")

    assert out["doc_type"] == "payment_receipt"
    assert out["fields"] == {}
    assert out["skipped"] == "proposal_only_skip_extract"
    assert out["_metric"]["model"] == "proposal-only-skip-extract"


@pytest.mark.asyncio
async def test_extract_runs_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default production behavior still calls the real extract stage."""

    seen: dict[str, Any] = {}

    async def _fake_extract(job: dict[str, Any], stage: str) -> dict[str, Any]:
        seen["stage"] = stage
        seen["ocr_text_per_page"] = job["ocr_text_per_page"]
        return {
            "doc_type": job["doc_type"],
            "fields": {"receipt_number": {"value": "R-1"}},
            "extraction_model": "fake",
        }

    monkeypatch.delenv("INTAKE_PROPOSAL_ONLY_SKIP_EXTRACT", raising=False)
    monkeypatch.setattr(stages, "extract_stage", _fake_extract)

    handler = stages.build_real_stage_handler(
        _FakePool(
            {
                "classify": {
                    "doc_type": "payment_receipt",
                    "ocr_text_per_page": [{"text": "receipt text"}],
                }
            }
        )
    )

    out = await handler({"id": 124}, "extract")

    assert out["fields"]["receipt_number"]["value"] == "R-1"
    assert seen == {"stage": "extract", "ocr_text_per_page": ["receipt text"]}
