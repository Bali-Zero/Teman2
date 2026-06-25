"""Pure tests for scripts/intake_direct_doc_parser_audit.py.

The live parser audit runs on the Pro against nuzantara_dev. These tests keep
the direct-doc placement contract stable without touching the WA mirror DB or
raw client documents.
"""

from __future__ import annotations

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


def test_sql_and_parser_are_read_only_and_pii_safe_by_shape() -> None:
    audit = _load()
    args = audit.build_parser().parse_args(["--pretty", "--limit", "10"])
    assert args.pretty is True
    assert args.limit == 10
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
