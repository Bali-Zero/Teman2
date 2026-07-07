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
    assert (
        audit.parser_bucket_for_row({"doc_type": "passport", "type_confidence": 0.55})
        == "low_confidence_review"
    )
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
    assert (
        audit.parser_bucket_for_row({"doc_type": "passport", "type_confidence": 0.8})
        == "needs_routing_proposal"
    )


def test_action_bucket_splits_unknown_docs_by_ocr_readiness() -> None:
    audit = _load()
    assert (
        audit.action_bucket_for_row(
            {"queue_status": "dead", "doc_type": "unknown", "ocr_chars": 500}
        )
        == "failed_pipeline"
    )
    assert (
        audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 0})
        == "needs_ocr_vision_batch"
    )
    assert (
        audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 99})
        == "needs_manual_review_short_ocr"
    )
    assert (
        audit.action_bucket_for_row({"doc_type": "unknown", "ocr_chars": 100})
        == "needs_text_parser_qwen_candidate"
    )
    assert (
        audit.action_bucket_for_row({"doc_type": "passport", "type_confidence": 0.55})
        == "low_confidence_review"
    )
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
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["passport text"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["tax text"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear"]}},
                },
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


def test_qwen_text_sample_reports_batch_acceptance_gate() -> None:
    audit = _load()
    answers = iter(["passport", "npwp", "unknown", "unknown"])

    async def classify_sequence(*args, **kwargs):  # noqa: ANN002, ANN003
        return next(answers)

    audit._qwen_classify_text = classify_sequence

    result = asyncio.run(
        audit.run_qwen_text_sample(
            [
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["passport text"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["tax text"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear a"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear b"]}},
                },
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
            min_candidate_rate=0.5,
            min_classified_attempts=4,
        )
    )

    assert result["acceptance_gate"] == {
        "status": "candidate_batch_ready",
        "reason": "candidate_rate_met",
        "candidate_rate": 0.5,
        "min_candidate_rate": 0.5,
        "classified_attempts": 4,
        "min_classified_attempts": 4,
    }


def test_qwen_text_sample_keeps_low_yield_batch_review_only() -> None:
    audit = _load()
    answers = iter(["birth_certificate", "unknown", "unknown", "unknown", "unknown"])

    async def classify_sequence(*args, **kwargs):  # noqa: ANN002, ANN003
        return next(answers)

    audit._qwen_classify_text = classify_sequence

    result = asyncio.run(
        audit.run_qwen_text_sample(
            [
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["birth text"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear a"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear b"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear c"]}},
                },
                {
                    "doc_type": "unknown",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear d"]}},
                },
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
            min_candidate_rate=0.25,
            min_classified_attempts=5,
        )
    )

    assert result["acceptance_gate"] == {
        "status": "review_only",
        "reason": "candidate_rate_below_threshold",
        "candidate_rate": 0.2,
        "min_candidate_rate": 0.25,
        "classified_attempts": 5,
        "min_classified_attempts": 5,
    }


def test_qwen_known_doc_benchmark_reports_workspace_accuracy() -> None:
    audit = _load()
    answers = iter(["passport", "bank_statement", "travel_ticket", "unknown"])

    async def classify_sequence(*args, **kwargs):  # noqa: ANN002, ANN003
        return next(answers)

    audit._qwen_classify_text = classify_sequence

    result = asyncio.run(
        audit.run_qwen_known_doc_benchmark(
            [
                {
                    "doc_type": "passport",
                    "stage_output": {"classify": {"ocr_text_per_page": ["passport text"]}},
                },
                {
                    "doc_type": "payment_receipt",
                    "stage_output": {"classify": {"ocr_text_per_page": ["receipt text"]}},
                },
                {
                    "doc_type": "visa",
                    "stage_output": {"classify": {"ocr_text_per_page": ["flight text"]}},
                },
                {
                    "doc_type": "npwp",
                    "stage_output": {"classify": {"ocr_text_per_page": ["unclear tax"]}},
                },
            ],
            ollama_url="http://127.0.0.1:11434",
            model="qwen3.5:9b",
            timeout_seconds=1.0,
            min_workspace_accuracy=0.7,
            min_classified_attempts=4,
        )
    )

    assert result["attempted"] == 4
    assert result["classified_attempts"] == 4
    assert result["failed_attempts"] == 0
    assert result["exact_doc_type_matches"] == 1
    assert result["workspace_matches"] == 3
    assert result["unknown_predictions"] == 1
    assert result["exact_doc_type_accuracy"] == 0.25
    assert result["workspace_accuracy"] == 0.75
    assert result["benchmark_gate"] == {
        "status": "workspace_benchmark_ready",
        "reason": "workspace_accuracy_met",
        "workspace_accuracy": 0.75,
        "min_workspace_accuracy": 0.7,
        "classified_attempts": 4,
        "min_classified_attempts": 4,
    }
    assert result["confusion_preview"] == [
        {
            "expected_doc_type": "passport",
            "predicted_doc_type": "passport",
            "expected_workspace_bucket": "immigration",
            "predicted_workspace_bucket": "immigration",
            "docs": 1,
        },
        {
            "expected_doc_type": "payment_receipt",
            "predicted_doc_type": "bank_statement",
            "expected_workspace_bucket": "finance",
            "predicted_workspace_bucket": "finance",
            "docs": 1,
        },
        {
            "expected_doc_type": "visa",
            "predicted_doc_type": "travel_ticket",
            "expected_workspace_bucket": "immigration",
            "predicted_workspace_bucket": "immigration",
            "docs": 1,
        },
        {
            "expected_doc_type": "npwp",
            "predicted_doc_type": "unknown",
            "expected_workspace_bucket": "tax",
            "predicted_workspace_bucket": "review",
            "docs": 1,
        },
    ]
    assert "receipt text" not in str(result)


def test_autocatalog_plan_promotes_only_gate_passing_qwen_batches() -> None:
    audit = _load()

    plan = audit.build_autocatalog_plan(
        {
            "direct_actions": [
                {"bucket": "needs_text_parser_qwen_candidate", "docs": 306},
                {"bucket": "needs_ocr_vision_batch", "docs": 592},
                {"bucket": "needs_manual_review_short_ocr", "docs": 98},
                {"bucket": "needs_routing_proposal", "docs": 48},
                {"bucket": "workspace_review_ready", "docs": 255},
                {"bucket": "low_confidence_review", "docs": 347},
            ],
            "qwen_text_sample": {
                "classified_attempts": 50,
                "workspace_buckets": [
                    {"bucket": "review", "docs": 25},
                    {"bucket": "immigration", "docs": 15},
                    {"bucket": "finance", "docs": 10},
                ],
                "placement_preview": [
                    {
                        "from_doc_type": "unknown",
                        "proposed_doc_type": "travel_ticket",
                        "workspace_bucket": "immigration",
                        "docs": 9,
                    },
                    {
                        "from_doc_type": "unknown",
                        "proposed_doc_type": "payment_receipt",
                        "workspace_bucket": "finance",
                        "docs": 6,
                    },
                ],
                "acceptance_gate": {
                    "status": "candidate_batch_ready",
                    "reason": "candidate_rate_met",
                    "candidate_rate": 0.5,
                    "classified_attempts": 50,
                },
            },
            "qwen_known_benchmark": {
                "benchmark_gate": {
                    "status": "workspace_benchmark_ready",
                    "reason": "workspace_accuracy_met",
                    "workspace_accuracy": 0.9,
                    "classified_attempts": 10,
                }
            },
        }
    )

    assert plan["status"] == "ready_for_staged_autocatalog"
    assert plan["write_mode"] == "proposal_only_no_crm_mutation"
    assert plan["worker_required_env"] == {
        "INTAKE_TEXT_LLM_CLASSIFY_ENABLED": "1",
        "INTAKE_TEXT_LLM_MODEL": "qwen3.5:9b",
        "INTAKE_TEXT_LLM_MIN_CHARS": "100",
        "INTAKE_TEXT_LLM_TIMEOUT_SECONDS": "45",
    }
    assert plan["dry_run_command"].endswith(
        "python scripts/intake_reprocess_backlog.py --autocatalog-preclassify-saved-ocr"
    )
    assert plan["apply_command"].endswith(
        "python scripts/intake_reprocess_backlog.py --autocatalog-preclassify-saved-ocr --apply"
    )
    assert plan["safe_to_apply_without_existing_gate"] is False
    assert plan["can_create_kita_proposals"] is True
    assert plan["can_auto_attach_without_review"] is False
    assert plan["totals"]["qwen_text_candidate_docs"] == 306
    assert plan["totals"]["ocr_vision_candidate_docs"] == 592
    assert plan["totals"]["projected_qwen_text_to_kita_docs"] == 153
    assert plan["totals"]["projected_qwen_text_to_review_docs"] == 153
    assert plan["projected_qwen_workspace_buckets"] == [
        {"bucket": "review", "sample_docs": 25, "projected_docs": 153},
        {"bucket": "immigration", "sample_docs": 15, "projected_docs": 92},
        {"bucket": "finance", "sample_docs": 10, "projected_docs": 61},
    ]
    assert plan["stages"][0]["stage"] == "qwen_text_autocatalog"
    assert (
        plan["stages"][0]["destination"]
        == "document_routing_proposal_then_kita_workspace_by_doc_type"
    )


def test_autocatalog_plan_stays_review_only_when_benchmark_is_missing() -> None:
    audit = _load()

    plan = audit.build_autocatalog_plan(
        {
            "direct_actions": [{"bucket": "needs_text_parser_qwen_candidate", "docs": 10}],
            "qwen_text_sample": {
                "acceptance_gate": {
                    "status": "candidate_batch_ready",
                    "reason": "candidate_rate_met",
                    "candidate_rate": 0.8,
                    "classified_attempts": 5,
                }
            },
        }
    )

    assert plan["status"] == "needs_known_doc_benchmark"
    assert plan["can_create_kita_proposals"] is False
    assert plan["can_auto_attach_without_review"] is False


def test_dashboard_snapshot_keeps_qwen_probe_aggregate_only() -> None:
    audit = _load()

    snapshot = audit.build_dashboard_snapshot(
        {
            "pii_policy": "aggregate_only_no_raw_phone_no_raw_group_subject_no_raw_ocr",
            "qwen_text_sample": {
                "attempted": 5,
                "classified_attempts": 5,
                "kita_workspace_candidates": 1,
                "review_after_qwen": 4,
                "acceptance_gate": {
                    "status": "review_only",
                    "reason": "candidate_rate_below_threshold",
                    "candidate_rate": 0.2,
                    "min_candidate_rate": 0.25,
                    "classified_attempts": 5,
                    "min_classified_attempts": 5,
                },
                "placement_preview": [
                    {
                        "from_doc_type": "unknown",
                        "proposed_doc_type": "birth_certificate",
                        "workspace_bucket": "immigration",
                        "docs": 1,
                    }
                ],
                "workspace_buckets": [{"bucket": "immigration", "docs": 1}],
                "transitions": {"unknown->birth_certificate": 1},
                "errors": {},
            },
            "qwen_known_benchmark": {
                "attempted": 4,
                "classified_attempts": 4,
                "workspace_accuracy": 0.75,
                "benchmark_gate": {
                    "status": "workspace_benchmark_ready",
                    "reason": "workspace_accuracy_met",
                    "workspace_accuracy": 0.75,
                    "min_workspace_accuracy": 0.7,
                    "classified_attempts": 4,
                    "min_classified_attempts": 4,
                },
                "confusion_preview": [
                    {
                        "expected_doc_type": "payment_receipt",
                        "predicted_doc_type": "bank_statement",
                        "expected_workspace_bucket": "finance",
                        "predicted_workspace_bucket": "finance",
                        "docs": 1,
                    }
                ],
            },
            "raw_ocr_text": "SHOULD_NOT_LEAK",
            "sender_phone": "+6280000000000",
        },
        generated_at="2026-06-26T04:00:00+00:00",
    )

    assert snapshot["generated_at"] == "2026-06-26T04:00:00+00:00"
    assert snapshot["pii_policy"] == "aggregate_only_no_raw_phone_no_raw_group_subject_no_raw_ocr"
    assert snapshot["qwen_text_sample"] == {
        "attempted": 5,
        "classified_attempts": 5,
        "kita_workspace_candidates": 1,
        "review_after_qwen": 4,
        "acceptance_gate": {
            "status": "review_only",
            "reason": "candidate_rate_below_threshold",
            "candidate_rate": 0.2,
            "min_candidate_rate": 0.25,
            "classified_attempts": 5,
            "min_classified_attempts": 5,
        },
        "placement_preview": [
            {
                "from_doc_type": "unknown",
                "proposed_doc_type": "birth_certificate",
                "workspace_bucket": "immigration",
                "docs": 1,
            }
        ],
        "workspace_buckets": [{"bucket": "immigration", "docs": 1}],
        "transitions": {"unknown->birth_certificate": 1},
        "errors": {},
    }
    assert snapshot["qwen_known_benchmark"] == {
        "attempted": 4,
        "classified_attempts": 4,
        "workspace_accuracy": 0.75,
        "benchmark_gate": {
            "status": "workspace_benchmark_ready",
            "reason": "workspace_accuracy_met",
            "workspace_accuracy": 0.75,
            "min_workspace_accuracy": 0.7,
            "classified_attempts": 4,
            "min_classified_attempts": 4,
        },
        "confusion_preview": [
            {
                "expected_doc_type": "payment_receipt",
                "predicted_doc_type": "bank_statement",
                "expected_workspace_bucket": "finance",
                "predicted_workspace_bucket": "finance",
                "docs": 1,
            }
        ],
    }
    assert snapshot["autocatalog_plan"] == {
        "status": "no_text_candidates",
        "reason": "no_unknown_direct_docs_with_enough_saved_ocr",
        "scope": "direct_whatsapp_docs_only_groups_excluded",
        "write_mode": "proposal_only_no_crm_mutation",
        "worker_required_env": {
            "INTAKE_TEXT_LLM_CLASSIFY_ENABLED": "1",
            "INTAKE_TEXT_LLM_MODEL": "qwen3.5:9b",
            "INTAKE_TEXT_LLM_MIN_CHARS": "100",
            "INTAKE_TEXT_LLM_TIMEOUT_SECONDS": "45",
        },
        "dry_run_command": audit.AUTOCATALOG_DRY_RUN_COMMAND,
        "apply_command": audit.AUTOCATALOG_APPLY_COMMAND,
        "safe_to_apply_without_existing_gate": False,
        "can_create_kita_proposals": False,
        "can_auto_attach_without_review": False,
        "qwen_text_gate_status": "review_only",
        "known_doc_benchmark_status": "workspace_benchmark_ready",
        "totals": {
            "qwen_text_candidate_docs": 0,
            "ocr_vision_candidate_docs": 0,
            "short_ocr_review_docs": 0,
            "low_confidence_review_docs": 0,
            "routing_proposal_needed_docs": 0,
            "workspace_review_ready_docs": 0,
            "already_routed_docs": 0,
            "failed_pipeline_docs": 0,
            "projected_qwen_text_to_kita_docs": 0,
            "projected_qwen_text_to_review_docs": 0,
        },
        "projected_qwen_workspace_buckets": [],
        "projected_qwen_placements": [],
        "stages": [
            {
                "stage": "qwen_text_autocatalog",
                "docs": 0,
                "source_bucket": "needs_text_parser_qwen_candidate",
                "llm": "qwen3.5:9b",
                "destination": "document_routing_proposal_then_kita_workspace_by_doc_type",
                "allowed_when": "candidate_batch_ready_and_workspace_benchmark_ready",
                "expected_kita_docs": 0,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
            {
                "stage": "vision_ocr_autocatalog",
                "docs": 0,
                "source_bucket": "needs_ocr_vision_batch",
                "llm": "qwen2.5vl_local_ocr_then_qwen_text_router",
                "destination": "same_proposal_path_after_ocr",
                "allowed_when": "local_vision_ocr_available_on_pro",
                "expected_kita_docs": 0,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
            {
                "stage": "short_ocr_resolution",
                "docs": 0,
                "source_bucket": "needs_manual_review_short_ocr",
                "llm": "vision_retry_or_manual_review",
                "destination": "review_or_same_proposal_path_after_better_ocr",
                "allowed_when": "ocr_text_below_threshold",
                "expected_kita_docs": 0,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
            {
                "stage": "known_doc_routing",
                "docs": 0,
                "source_bucket": "needs_routing_proposal",
                "llm": "none",
                "destination": "document_routing_proposal_review_pending",
                "allowed_when": "known_doc_type_high_confidence",
                "expected_kita_docs": 0,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
            {
                "stage": "workspace_operator_review",
                "docs": 0,
                "source_bucket": "workspace_review_ready_or_low_confidence_review",
                "llm": "none",
                "destination": "kita_review_queue",
                "allowed_when": "operator_or_existing_auto_attach_gate",
                "expected_kita_docs": 0,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
        ],
    }
    assert "SHOULD_NOT_LEAK" not in str(snapshot)
    assert "+6280000000000" not in str(snapshot)


def test_sql_and_parser_are_read_only_and_pii_safe_by_shape() -> None:
    audit = _load()
    args = audit.build_parser().parse_args(
        [
            "--pretty",
            "--limit",
            "10",
            "--qwen-ocr-max-chars",
            "1200",
            "--qwen-min-candidate-rate",
            "0.4",
            "--qwen-min-classified-attempts",
            "10",
            "--qwen-known-sample",
            "20",
            "--qwen-min-workspace-accuracy",
            "0.7",
        ]
    )
    assert args.pretty is True
    assert args.limit == 10
    assert args.qwen_ocr_max_chars == 1200
    assert args.qwen_min_candidate_rate == 0.4
    assert args.qwen_min_classified_attempts == 10
    assert args.qwen_known_sample == 20
    assert args.qwen_min_workspace_accuracy == 0.7
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
    assert "doc_type <> 'unknown'" in audit.DIRECT_DOC_QWEN_KNOWN_BENCHMARK_SQL
    assert "type_confidence >= $3" in audit.DIRECT_DOC_QWEN_KNOWN_BENCHMARK_SQL
