"""Provider-agnostic OCR quality checks for intake samples.

These tests keep provider benchmarking offline: feed OCR text that a provider
already produced, then score the same classify/extract pipeline against expected
fields. CI never calls Ollama or Gemini here.
"""

from __future__ import annotations

from backend.services.intake import ocr_quality


def test_score_expected_fields_counts_matches_missing_and_mismatches():
    fields = {
        "name": {"value": "MARIO   LUCA ROSSI"},
        "passport_no": {"value": "x1234567"},
        "expiry": {"value": None},
        "sponsor": {"value": "PT OTHER"},
    }

    result = ocr_quality.score_expected_fields(
        {
            "name": "Mario Luca Rossi",
            "passport_no": "X1234567",
            "expiry": "2031-12-24",
            "sponsor": "PT BALI ZERO TEST",
        },
        fields,
    )

    assert result["score"] == 0.5
    assert result["matched_fields"] == ["name", "passport_no"]
    assert result["missing_fields"] == ["expiry"]
    assert result["mismatched_fields"] == ["sponsor"]


async def test_evaluate_ocr_text_runs_current_intake_pipeline_without_live_vision():
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    result = await ocr_quality.evaluate_ocr_text(
        provider="ollama",
        ocr_text=(
            "REPUBLIK INDONESIA\n"
            "IZIN TINGGAL TERBATAS\n"
            "Permit No: 2C11AB98765\n"
            "Name: MARIO LUCA ROSSI\n"
            "Nationality: ITALIA\n"
            "Valid Until: 2027-06-25\n"
            "Sponsor: PT BALI ZERO TEST"
        ),
        expected_doc_type="kitas",
        expected_fields={
            "kitas_no": "2C11AB98765",
            "name": "Mario Luca Rossi",
            "expiry": "2027-06-25",
            "sponsor": "PT BALI ZERO TEST",
        },
        generate_fn=_gen,
    )

    assert called["n"] == 0
    assert result["provider"] == "ollama"
    assert result["classification"]["type"] == "itas"
    assert result["extracted_doc_type"] == "kitas"
    assert result["doc_type_match"] is True
    assert result["field_score"]["score"] == 1.0
    assert result["field_score"]["matched_fields"] == [
        "kitas_no",
        "name",
        "expiry",
        "sponsor",
    ]


async def test_evaluate_ocr_text_scores_expected_alias_fields_for_benchmark_docs():
    result = await ocr_quality.evaluate_ocr_text(
        provider="gemini-agy",
        ocr_text=(
            "BUKTI TRANSFER\n"
            "Reference No: TRX-2026-778899\n"
            "Payer: MARIO LUCA ROSSI\n"
            "Amount: IDR 15,000,000\n"
            "Date: 2026-06-25\n"
            "Bank: BCA"
        ),
        expected_doc_type="payment_receipt",
        expected_fields={
            "reference": "TRX-2026-778899",
            "payer": "Mario Luca Rossi",
            "amount": "IDR 15,000,000",
            "date": "2026-06-25",
        },
        generate_fn=lambda _model, _prompt: "{}",
    )

    assert result["doc_type_match"] is True
    assert result["field_score"]["score"] == 1.0
    assert result["field_score"]["matched_fields"] == [
        "reference",
        "payer",
        "amount",
        "date",
    ]


async def test_evaluate_ocr_text_scores_unknown_without_crashing():
    result = await ocr_quality.evaluate_ocr_text(
        provider="gemini",
        ocr_text="blurred unreadable fragment",
        expected_doc_type="passport",
        expected_fields={"passport_no": "X1234567", "name": "Mario Luca Rossi"},
    )

    assert result["classification"]["type"] == "unknown"
    assert result["extracted_doc_type"] == "unknown"
    assert result["doc_type_match"] is False
    assert result["field_score"]["score"] == 0.0
    assert result["field_score"]["missing_fields"] == ["passport_no", "name"]


def test_summarize_evaluations_groups_by_provider():
    summary = ocr_quality.summarize_evaluations(
        [
            {
                "provider": "ollama",
                "doc_type_match": True,
                "field_score": {"score": 1.0, "matched_count": 4, "missing_count": 0},
                "seconds": 40.0,
                "error": None,
            },
            {
                "provider": "ollama",
                "doc_type_match": False,
                "field_score": {"score": 0.25, "matched_count": 1, "missing_count": 3},
                "elapsed_s": 20.0,
                "error": "timeout",
            },
            {
                "provider": "gemini",
                "doc_type_match": True,
                "field_score": {"score": 0.5, "matched_count": 2, "missing_count": 2},
                "seconds": 10.0,
                "error": "",
            },
        ]
    )

    assert summary["sample_count"] == 3
    assert summary["provider_summary"]["ollama"] == {
        "samples": 2,
        "doc_type_matches": 1,
        "doc_type_match_rate": 0.5,
        "avg_field_score": 0.625,
        "matched_fields": 5,
        "missing_fields": 3,
        "error_count": 1,
        "elapsed_total_s": 60.0,
        "elapsed_avg_s": 30.0,
        "elapsed_min_s": 20.0,
        "elapsed_max_s": 40.0,
    }
    assert summary["provider_summary"]["gemini"]["avg_field_score"] == 0.5
    assert summary["provider_summary"]["gemini"]["error_count"] == 0
    assert summary["provider_summary"]["gemini"]["elapsed_avg_s"] == 10.0
