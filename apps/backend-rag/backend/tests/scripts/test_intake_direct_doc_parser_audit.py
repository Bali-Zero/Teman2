"""Pure tests for scripts/intake_direct_doc_parser_audit.py.

The live parser audit runs on the Pro against nuzantara_dev. These tests keep
the direct-doc placement contract stable without touching the WA mirror DB or
raw client documents.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "intake_direct_doc_parser_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("idpa_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_workspace_bucket_matches_dashboard_taxonomy() -> None:
    audit = _load()
    assert audit.workspace_bucket_for_doc_type("passport") == "immigration"
    assert audit.workspace_bucket_for_doc_type("ITAS") == "immigration"
    assert audit.workspace_bucket_for_doc_type("birth_certificate") == "immigration"
    assert audit.workspace_bucket_for_doc_type("nib") == "company"
    assert audit.workspace_bucket_for_doc_type("profil_perseroan") == "company"
    assert audit.workspace_bucket_for_doc_type("npwp") == "tax"
    assert audit.workspace_bucket_for_doc_type("bank_statement") == "finance"
    assert audit.workspace_bucket_for_doc_type("ktp") == "identity"
    assert audit.workspace_bucket_for_doc_type("unknown") == "review"


def test_parser_bucket_explains_direct_doc_next_action() -> None:
    audit = _load()
    assert audit.parser_bucket_for_row({"queue_status": "dead"}) == "failed_pipeline"
    assert audit.parser_bucket_for_row({"doc_type": "unknown"}) == "needs_doc_type_parser"
    assert audit.parser_bucket_for_row({"doc_type": "passport", "type_confidence": 0.55}) == "low_confidence_review"
    assert (
        audit.parser_bucket_for_row(
            {"doc_type": "passport", "type_confidence": 0.8, "entity_decision": "AUTO_ATTACH"}
        )
        == "workspace_review_ready"
    )
    assert (
        audit.parser_bucket_for_row(
            {"doc_type": "passport", "type_confidence": 0.8, "routed_non_stub": True}
        )
        == "workspace_review_ready"
    )
    assert (
        audit.parser_bucket_for_row(
            {"doc_type": "passport", "type_confidence": 0.8, "proposal_status": "routed"}
        )
        == "already_routed"
    )
    assert audit.parser_bucket_for_row({"doc_type": "passport", "type_confidence": 0.8}) == "needs_routing_proposal"


def test_action_bucket_splits_unknown_docs_by_ocr_readiness() -> None:
    audit = _load()
    assert audit.action_bucket_for_row({"queue_status": "dead", "doc_type": "unknown", "ocr_chars": 500}) == "failed_pipeline"
    assert audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 0}) == "needs_ocr_vision_batch"
    assert audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 99}) == "needs_manual_review_short_ocr"
    assert audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 100}) == "needs_text_parser_qwen_candidate"
    assert audit.action_bucket_for_row({"doc_type": "passport", "type_confidence": 0.55}) == "low_confidence_review"
    assert (
        audit.action_bucket_for_row(
            {"doc_type": "passport", "type_confidence": 0.8, "entity_decision": "AUTO_ATTACH"}
        )
        == "workspace_review_ready"
    )


def test_summarize_direct_rows_is_aggregate_only_and_sorts_counts() -> None:
    audit = _load()
    summary = audit.summarize_direct_rows(
        [
            {
                "queue_status": "done",
                "doc_type": "passport",
                "type_confidence": 0.82,
                "extracted_non_stub": True,
                "routed_non_stub": True,
                "entity_decision": "AUTO_ATTACH",
            },
            {
                "queue_status": "done",
                "doc_type": "unknown",
                "type_confidence": 0,
                "extracted_non_stub": False,
                "routed_non_stub": False,
                "ocr_chars": 0,
            },
            {
                "queue_status": "done",
                "doc_type": "bank_statement",
                "type_confidence": 0.42,
                "extracted_non_stub": True,
                "routed_non_stub": False,
            },
        ],
        top_doc_types=10,
    )

    assert summary["totals"] == {
        "direct_docs": 3,
        "known_doc_type": 2,
        "unknown_doc_type": 1,
        "high_confidence": 1,
        "low_confidence_known": 1,
    }
    assert summary["unknown_ocr_quality"] == {
        "unknown_docs": 1,
        "ocr_empty": 1,
        "ocr_1_99": 0,
        "ocr_100_499": 0,
        "ocr_500_plus": 0,
    }
    assert summary["direct_parser"][0] == {"bucket": "workspace_review_ready", "docs": 1}
    assert {"bucket": "needs_doc_type_parser", "docs": 1} in summary["direct_parser"]
    assert {"bucket": "low_confidence_review", "docs": 1} in summary["direct_parser"]
    assert {"bucket": "needs_ocr_vision_batch", "docs": 1} in summary["direct_actions"]
    assert {"bucket": "workspace_review_ready", "docs": 1} in summary["direct_actions"]
    assert {"bucket": "low_confidence_review", "docs": 1} in summary["direct_actions"]
    assert summary["workspace_buckets"] == [
        {"bucket": "immigration", "docs": 1},
        {"bucket": "review", "docs": 1},
        {"bucket": "finance", "docs": 1},
    ]
    assert summary["direct_doc_types"][0]["doc_type"] == "passport"
    assert "phone" not in str(summary).lower()
    assert "group_subject" not in str(summary).lower()


def test_qwen_answer_parser_accepts_only_known_doc_type_tokens() -> None:
    audit = _load()
    assert audit.parse_qwen_doc_type_answer("passport") == "passport"
    assert audit.parse_qwen_doc_type_answer("BANK_STATEMENT.") == "bank_statement"
    assert audit.parse_qwen_doc_type_answer("This looks like a passport") is None
    assert audit.parse_qwen_doc_type_answer("driver_license") is None


def test_qwen_text_sample_counts_classifier_errors_as_unclassified() -> None:
    audit = _load()

    async def fail_classify(*args, **kwargs):  # noqa: ANN002, ANN003
        raise TimeoutError("local model timeout")

    audit._qwen_classify_text = fail_classify

    result = asyncio.run(
        audit.run_qwen_text_sample(
            [
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["KITAS example text"]}},
                }
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
        )
    )

    assert result["attempted"] == 1
    assert result["failed_attempts"] == 1
    assert result["not_classified_due_error"] == 1
    assert result["errors"] == {"TimeoutError": 1}
    assert result["transitions"] == {"unknown->error": 1}
    assert result["still_unknown"] == 0


def test_qwen_text_sample_uses_configurable_saved_ocr_limit() -> None:
    audit = _load()
    captured: list[str] = []

    async def capture_text(*args, ocr_text: str, **kwargs):  # noqa: ANN002, ANN003
        captured.append(ocr_text)
        return "passport"

    audit._qwen_classify_text = capture_text

    result = asyncio.run(
        audit.run_qwen_text_sample(
            [
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["A" * 50]}},
                }
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
            ocr_max_chars=12,
        )
    )

    assert captured == ["A" * 12]
    assert result["ocr_max_chars"] == 12
    assert result["transitions"] == {"unknown->passport": 1}


def test_qwen_text_sample_reports_kita_workspace_placement_preview() -> None:
    audit = _load()
    answers = iter(["passport", "npwp", "unknown"])

    async def classify_sequence(*args, **kwargs):  # noqa: ANN002, ANN003
        return next(answers)

    audit._qwen_classify_text = classify_sequence

    result = asyncio.run(
        audit.run_qwen_text_sample(
            [
                {"doc_type": "unknown", "stage_output": {"classify": {"ocr_text_per_page": ["passport text"]}}},
                {"doc_type": "unknown", "stage_output": {"classify": {"ocr_text_per_page": ["tax text"]}}},
                {"doc_type": "unknown", "stage_output": {"classify": {"ocr_text_per_page": ["unclear"]}}},
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
        )
    )

    assert result["kita_workspace_candidates"] == 2
    assert result["review_after_qwen"] == 1
    assert result["placement_preview"] == [
        {
            "from_doc_type": "unknown",
            "proposed_doc_type": "passport",
            "workspace_bucket": "immigration",
            "docs": 1,
        },
        {
            "from_doc_type": "unknown",
            "proposed_doc_type": "npwp",
            "workspace_bucket": "tax",
            "docs": 1,
        },
        {
            "from_doc_type": "unknown",
            "proposed_doc_type": "unknown",
            "workspace_bucket": "review",
            "docs": 1,
        },
    ]


def test_sql_and_parser_are_read_only_and_pii_safe_by_shape() -> None:
    audit = _load()
    args = audit.build_parser().parse_args(["--pretty", "--limit", "10", "--qwen-ocr-max-chars", "1200"])
    assert args.pretty is True
    assert args.limit == 10
    assert args.qwen_ocr_max_chars == 1200
    assert not hasattr(args, "apply")

    sql_values = [
        value
        for name, value in vars(audit).items()
        if name.endswith("_SQL") and isinstance(value, str)
    ]
    assert sql_values
    joined = "\n".join(sql_values).lower()
    for forbidden in (" insert ", " update ", " delete ", " alter ", " drop ", " truncate "):
        assert forbidden not in joined
    for pii_field in ("sender_phone", "counterpart_phone", "phone_normalized", "group_subject"):
        assert pii_field not in joined
    assert "ocr_chars >= $2" in audit.DIRECT_DOC_QWEN_SAMPLE_SQL
