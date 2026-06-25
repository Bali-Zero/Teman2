"""Unit tests for scripts/intake_reprocess_backlog.py (pure parts only).

No Postgres: covers the watermark-file parsing, the row→enqueue mapping (whose
source_ref format is the anti-join dedup key — drift would break idempotency),
the CLI defaults (dry-run!), and the load-bearing predicates baked into the SQL
constants. The DB-side effects run on the Pro at rollout (dry-run first).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "intake_reprocess_backlog.py"


def _load():
    spec = importlib.util.spec_from_file_location("irb_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_help_does_not_require_app_settings() -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(_REPO_ROOT / "apps" / "backend-rag"),
    }
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--help"],
        cwd=_REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "--retry-unschematised-supported" in result.stdout


# ---------------------------------------------------------------------------
# read_watermark
# ---------------------------------------------------------------------------


def test_read_watermark_parses_int(tmp_path: Path) -> None:
    irb = _load()
    f = tmp_path / "wm.txt"
    f.write_text("49490\n")
    assert irb.read_watermark(f) == 49490


def test_read_watermark_missing_is_none(tmp_path: Path) -> None:
    irb = _load()
    assert irb.read_watermark(tmp_path / "absent.txt") is None


def test_read_watermark_garbage_is_none(tmp_path: Path) -> None:
    irb = _load()
    f = tmp_path / "wm.txt"
    f.write_text("not-a-number")
    assert irb.read_watermark(f) is None


# ---------------------------------------------------------------------------
# row_to_enqueue_kwargs — must mirror the sweeper's enqueue call EXACTLY
# ---------------------------------------------------------------------------


def test_row_to_enqueue_kwargs_mapping() -> None:
    irb = _load()
    row = {
        "id": 123,
        "baileys_message_id": "ABCDEF",
        "media_stored_path": "/blobs/x.pdf",
        "media_mime": "application/pdf",
        "media_type": "document",
        "team_member_email": "ari@balizero.com",
        "sender_phone": "+62 812-0000-1111",
    }
    kw = irb.row_to_enqueue_kwargs(row)
    assert kw == {
        "source": "whatsapp",
        "source_ref": "wa-mirror:ABCDEF",  # the dedup key format — do not drift
        "blob_path": "/blobs/x.pdf",
        "mime_type": "application/pdf",
        "received_by": "ari@balizero.com",
        "sender_phone": "+62 812-0000-1111",
    }


def test_media_types_default_and_custom() -> None:
    irb = _load()
    assert irb._media_types(None) == ("document", "image")
    assert irb._media_types("document") == ("document",)
    assert irb._media_types(" a , b ") == ("a", "b")
    assert irb._media_types("  ") == ("document", "image")


# ---------------------------------------------------------------------------
# CLI defaults — dry-run by default is the safety contract
# ---------------------------------------------------------------------------


def test_parser_defaults_are_dry_run() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--backfill"])
    assert args.apply is False
    assert args.backfill is True
    assert args.reprocess is False
    assert args.retry_empty_pdf_ocr is False
    assert args.retry_unschematised_supported is False
    assert args.quality_sample is False
    assert args.pipeline_version == irb.DEFAULT_PIPELINE_VERSION
    assert args.empty_pdf_ocr_version == irb.DEFAULT_EMPTY_PDF_OCR_VERSION
    assert args.unschematised_pipeline_version == irb.DEFAULT_UNSCHEMATISED_RECOVERY_VERSION
    assert args.quality_sample_size == 100
    assert args.quality_source == "whatsapp"
    assert args.quality_pipeline_version is None
    assert args.quality_statuses is None
    assert args.quality_exclude_stub is False
    assert args.watermark is None


def test_parser_pipeline_version_override() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        ["--reprocess", "--apply", "--pipeline-version", "v9-test"]
    )
    assert args.apply is True
    assert args.pipeline_version == "v9-test"


def test_parser_quality_sample_options_are_read_only() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--quality-sample",
            "--quality-sample-size",
            "25",
            "--quality-source",
            "drive",
            "--quality-pipeline-version",
            "v9-quality",
            "--quality-statuses",
            "done,dead",
            "--quality-exclude-stub",
        ]
    )
    assert args.apply is False
    assert args.quality_sample is True
    assert args.quality_sample_size == 25
    assert args.quality_source == "drive"
    assert args.quality_pipeline_version == "v9-quality"
    assert args.quality_statuses == "done,dead"
    assert args.quality_exclude_stub is True


def test_parser_retry_unschematised_supported_options_are_dry_run() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--retry-unschematised-supported",
            "--unschematised-pipeline-version",
            "v9-unschematised",
        ]
    )
    assert args.apply is False
    assert args.retry_unschematised_supported is True
    assert args.unschematised_pipeline_version == "v9-unschematised"


def test_quality_statuses_default_and_custom() -> None:
    irb = _load()
    assert irb._quality_statuses(None) is None
    assert irb._quality_statuses("  ") is None
    assert irb._quality_statuses("done, dead ") == ("done", "dead")


def test_recoverable_unschematised_doc_types_follow_current_extract_schemas() -> None:
    irb = _load()
    doc_types = irb._recoverable_unschematised_doc_types()
    assert "itap" in doc_types
    assert "ktp" in doc_types
    assert "sk_kemenkumham" in doc_types
    assert "oss" in doc_types  # classifier emits oss, extract canonicalizes to nib
    assert "itas" in doc_types  # classifier emits itas, extract canonicalizes to kitas
    assert "unknown" not in doc_types
    assert "skt" not in doc_types  # classifier knows it, extraction still does not


# ---------------------------------------------------------------------------
# SQL constants — load-bearing predicates
# ---------------------------------------------------------------------------


def test_reprocess_select_targets_weak_review_pending() -> None:
    irb = _load()
    sql = irb.REPROCESS_SELECT_SQL
    assert "'review_pending'" in sql
    assert "doc_type" in sql and "'unknown'" in sql
    assert "'NO_MATCH'" in sql


def test_reset_sql_matches_v2_worker_contract() -> None:
    irb = _load()
    sql = irb.REPROCESS_RESET_SQL
    # The exact v2 reset contract (services/intake/worker.py).
    assert "status           = 'pending'" in sql
    assert "stage            = NULL" in sql
    assert "lease_owner      = NULL" in sql
    assert "lease_expires_at = NULL" in sql
    assert "attempts         = 0" in sql
    assert "next_visible_at  = now()" in sql
    assert "'{}'::jsonb" in sql
    assert "pipeline_version = $2" in sql  # the bump that mints fresh routing keys


def test_priority_retry_reset_frontloads_historical_rows() -> None:
    irb = _load()
    sql = irb.PRIORITY_RETRY_RESET_SQL
    # Same reset shape, but targeted OCR retry must not sit behind newer pending
    # WhatsApp backlog; created_at preserves FIFO urgency for historical rows.
    assert "status           = 'pending'" in sql
    assert "stage            = NULL" in sql
    assert "lease_owner      = NULL" in sql
    assert "lease_expires_at = NULL" in sql
    assert "attempts         = 0" in sql
    assert "next_visible_at  = LEAST(COALESCE(created_at, now()), now())" in sql
    assert "'{}'::jsonb" in sql
    assert "pipeline_version = $2" in sql


def test_backfill_select_is_anti_join_below_watermark() -> None:
    irb = _load()
    sql = irb.BACKFILL_SELECT_SQL
    assert "NOT EXISTS" in sql
    assert "'wa-mirror:' || w.baileys_message_id" in sql
    assert "w.id <= $2" in sql
    assert "direction = 'inbound'" in sql
    assert "media_stored_path IS NOT NULL" in sql
    assert "sender_phone" in sql  # m225 rides along on the backfill


def test_supersede_sql_only_touches_review_pending() -> None:
    irb = _load()
    sql = irb.REPROCESS_SUPERSEDE_SQL
    assert "'superseded'" in sql
    assert "status = 'review_pending'" in sql  # never clobbers claimed/routed rows


def test_revive_stub_select_guards_are_all_present() -> None:
    irb = _load()
    sql = irb.REVIVE_STUB_SELECT_SQL
    # Every guard is load-bearing — losing one widens the recovery scope wrongly.
    assert "stage_output->'route'->>'stub' = 'true'" in sql  # stub passthrough only
    assert "iq.source = 'whatsapp'" in sql  # own-channel, not the admin Drive dump
    assert "iq.sender_phone IS NOT NULL" in sql  # a real owner exists
    assert "NOT EXISTS" in sql  # exclude rows that already carry a proposal
    assert "/groups/" in sql  # the group-chat opt-out predicate
    assert "$1::bool" in sql  # include_groups toggle


def test_empty_pdf_ocr_select_guards_are_all_present() -> None:
    irb = _load()
    sql = irb.EMPTY_PDF_OCR_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "doc_type" in sql and "'unknown'" in sql
    assert "rasterize_failed" in sql
    assert "raw_pdf_fallback" in sql
    assert "ocr_text_per_page" in sql
    assert "SUM(length" in sql
    assert "= 0" in sql
    assert "NOT EXISTS" in sql
    assert "NOT IN ('review_pending', 'quarantine', 'superseded')" in sql


def test_empty_pdf_ocr_supersede_only_touches_review_or_quarantine() -> None:
    irb = _load()
    sql = irb.EMPTY_PDF_OCR_SUPERSEDE_SQL
    assert "status = 'superseded'" in sql
    assert "queue_id = ANY($1::bigint[])" in sql
    assert "status IN ('review_pending', 'quarantine')" in sql


def test_unschematised_supported_select_guards_are_all_present() -> None:
    irb = _load()
    sql = irb.UNSCHEMATISED_SUPPORTED_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "unschematised_doc_type" in sql
    assert "doc_type = ANY($1::text[])" in sql
    assert "NOT EXISTS" in sql
    assert "NOT IN ('review_pending', 'quarantine', 'superseded')" in sql


def test_unschematised_supported_supersede_only_review_or_quarantine() -> None:
    irb = _load()
    sql = irb.UNSCHEMATISED_SUPPORTED_SUPERSEDE_SQL
    assert "status = 'superseded'" in sql
    assert "queue_id = ANY($1::bigint[])" in sql
    assert "status IN ('review_pending', 'quarantine')" in sql


def test_quality_sample_sql_is_bounded_and_redacted() -> None:
    irb = _load()
    sql = irb.QUALITY_SAMPLE_SQL
    assert "LIMIT $3" in sql
    assert "q.source = $1" in sql
    assert "q.pipeline_version = $2" in sql
    assert "q.status = ANY($4::text[])" in sql
    assert "$5::bool IS FALSE" in sql
    assert "ocr_text_per_page" in sql
    assert "SUM(length" in sql
    assert "jsonb_object_agg" in sql
    assert "empty_ocr_unknown" in sql
    assert "legible_unknown" in sql
    assert "stub_stage" in sql
    assert "unsupported_doc_type" in sql
    assert "typed_missing_fields" in sql
    assert "by_extract_skipped" in sql
    assert "quality_issue_by_doc_type" in sql
    assert "extract_skipped_by_doc_type" in sql
    assert "routed_no_match" in sql
    assert "last_error_category" in sql
    assert "sender_phone" not in sql
    assert "blob_path" not in sql
    assert "source_ref" not in sql
    assert "media_stored_path" not in sql
