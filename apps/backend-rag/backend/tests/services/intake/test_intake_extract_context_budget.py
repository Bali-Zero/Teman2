"""PII-free tests for bounded page-local Intake extraction context."""

from __future__ import annotations

import json

from pytest import MonkeyPatch

from backend.services.intake import extract


async def test_page_local_context_budget_preserves_source_page_number(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTAKE_EXTRACT_PAGE_LOCAL_MAX_CHARS", raising=False)
    monkeypatch.delenv("INTAKE_EXTRACT_PAGE_LOCAL_RADIUS", raising=False)
    pages = [f"UNIQUE_PAGE_{index + 1} " + ("x" * 5_000) for index in range(14)]
    captured_prompt = ""

    async def _capture(model: str, prompt: str) -> str:  # noqa: ARG001
        nonlocal captured_prompt
        captured_prompt = prompt
        return json.dumps(
            {
                "receipt_no": {"value": "SAFE-REFERENCE", "source_page": 6},
                "amount": {"value": "IDR 100", "source_page": 1},
            }
        )

    out = await extract.extract_fields(
        "payment_receipt",
        pages,
        source_page=5,
        generate_fn=_capture,
    )

    budgeted = extract._budget_page_local_context("payment_receipt", pages, 5)
    assert sum(len(page) for page in budgeted) <= 12_000
    assert "--- PAGE 6 ---\nUNIQUE_PAGE_6" in captured_prompt
    assert "UNIQUE_PAGE_5" in captured_prompt
    assert "UNIQUE_PAGE_7" in captured_prompt
    assert "UNIQUE_PAGE_1" not in captured_prompt
    assert "--- PAGE 14 ---" in captured_prompt
    assert out["fields"]["receipt_no"]["source_page"] == 6
    assert out["fields"]["amount"]["source_page"] is None
    assert out["fields"]["amount"]["confidence"] < 0.6


async def test_legal_multipage_context_is_never_budgeted(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTAKE_EXTRACT_PAGE_LOCAL_MAX_CHARS", raising=False)
    pages = [f"LEGAL_PAGE_{index + 1} " + ("z" * 1_000) for index in range(14)]
    captured_prompt = ""

    async def _capture(model: str, prompt: str) -> str:  # noqa: ARG001
        nonlocal captured_prompt
        captured_prompt = prompt
        return json.dumps({"company_name": {"value": "PT SYNTHETIC TEST", "source_page": 14}})

    out = await extract.extract_fields(
        "akta_pendirian",
        pages,
        source_page=5,
        generate_fn=_capture,
    )

    assert "--- PAGE 1 ---\nLEGAL_PAGE_1" in captured_prompt
    assert "--- PAGE 14 ---\nLEGAL_PAGE_14" in captured_prompt
    assert out["fields"]["company_name"]["source_page"] == 14


async def test_extract_stage_forwards_classifier_source_page(
    monkeypatch: MonkeyPatch,
) -> None:
    captured_source_page: int | None = None

    async def _extract_fields(
        doc_type: str | None,
        pages: list[str],
        *,
        source_page: int | None = None,
        generate_fn: extract.GenerateFn | None = None,
    ) -> dict[str, object]:
        del doc_type, pages, generate_fn
        nonlocal captured_source_page
        captured_source_page = source_page
        return {"doc_type": "payment_receipt", "fields": {}}

    monkeypatch.setattr(extract, "extract_fields", _extract_fields)
    job = {
        "id": 43,
        "stage_output": {
            "classify": {"doc_type": "payment_receipt", "source_page": 5},
            "ocr": {"ocr_text_per_page": ["synthetic receipt"]},
        },
    }

    await extract.extract_stage(job, "extract")

    assert captured_source_page == 5
