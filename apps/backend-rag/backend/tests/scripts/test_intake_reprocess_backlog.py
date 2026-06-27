"""Unit tests for scripts/intake_reprocess_backlog.py (pure parts only).

No Postgres: covers the watermark-file parsing, the row→enqueue mapping (whose
source_ref format is the anti-join dedup key — drift would break idempotency),
the CLI defaults (dry-run!), and the load-bearing predicates baked into the SQL
constants. The DB-side effects run on the Pro at rollout (dry-run first).
"""

from __future__ import annotations

import importlib.util
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
        "chat_type": "direct",
        "group_jid": None,
        "group_subject_snapshot": None,
    }
    kw = irb.row_to_enqueue_kwargs(row)
    assert kw == {
        "source": "whatsapp",
        "source_ref": "wa-mirror:ABCDEF",  # the dedup key format — do not drift
        "blob_path": "/blobs/x.pdf",
        "mime_type": "application/pdf",
        "received_by": "ari@balizero.com",
        "sender_phone": "+62 812-0000-1111",
        "source_context": {
            "transport": "wa-mirror",
            "context_version": "wa-mirror-v1",
            "chat_type": "direct",
            "crm_identity_policy": "phone_keyed_direct_chat",
            "routing_identity_policy": "sender_phone_enabled",
            "sender_phone_forwarded": True,
        },
    }


def test_row_to_enqueue_kwargs_suppresses_group_sender_phone() -> None:
    irb = _load()
    row = {
        "id": 123,
        "baileys_message_id": "ABCDEF",
        "media_stored_path": "/blobs/x.pdf",
        "media_mime": "application/pdf",
        "media_type": "document",
        "team_member_email": "ari@balizero.com",
        "sender_phone": "+62 812-0000-1111",
        "chat_type": "group",
        "group_jid": "120363000000000000@g.us",
        "group_subject_snapshot": "Bali Zero Team Internal",
    }

    kw = irb.row_to_enqueue_kwargs(row)
    assert kw["sender_phone"] is None
    context = kw["source_context"]
    assert context["chat_type"] == "group"
    assert context["crm_identity_policy"] == "disabled_for_group"
    assert context["routing_identity_policy"] == "group_participant_phone_suppressed"
    assert context["sender_phone_forwarded"] is False
    assert "group_jid_hash" in context
    assert "group_subject_hash" in context
    assert "120363000000000000@g.us" not in str(context)
    assert "Bali Zero Team Internal" not in str(context)


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
    args = irb.build_parser().parse_args(["--backfill", "--scrub-group-phone"])
    assert args.apply is False
    assert args.backfill is True
    assert args.scrub_group_phone is True
    assert args.backfill_source_context is False
    assert args.reprocess is False
    assert args.autocatalog_direct_unknown_text is False
    assert args.pipeline_version == irb.DEFAULT_PIPELINE_VERSION
    assert args.autocatalog_pipeline_version == irb.DEFAULT_AUTOCATALOG_PIPELINE_VERSION
    assert args.watermark is None


def test_parser_backfill_source_context_is_dry_run() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--backfill-source-context"])
    assert args.apply is False
    assert args.backfill_source_context is True


def test_parser_pipeline_version_override() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        ["--reprocess", "--apply", "--pipeline-version", "v9-test"]
    )
    assert args.apply is True
    assert args.pipeline_version == "v9-test"


def test_parser_autocatalog_direct_unknown_text_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--autocatalog-direct-unknown-text"])
    assert args.apply is False
    assert args.autocatalog_direct_unknown_text is True
    assert args.autocatalog_pipeline_version == irb.DEFAULT_AUTOCATALOG_PIPELINE_VERSION
    assert args.autocatalog_min_ocr_chars == irb.DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS
    assert args.autocatalog_limit == irb.DEFAULT_AUTOCATALOG_LIMIT


def test_parser_autocatalog_direct_unknown_text_overrides() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--autocatalog-direct-unknown-text",
            "--apply",
            "--autocatalog-pipeline-version",
            "v9-qwen",
            "--autocatalog-min-ocr-chars",
            "250",
            "--autocatalog-limit",
            "25",
        ]
    )
    assert args.apply is True
    assert args.autocatalog_pipeline_version == "v9-qwen"
    assert args.autocatalog_min_ocr_chars == 250
    assert args.autocatalog_limit == 25


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


def test_backfill_select_is_anti_join_below_watermark() -> None:
    irb = _load()
    sql = irb.BACKFILL_SELECT_SQL
    assert "NOT EXISTS" in sql
    assert "'wa-mirror:' || w.baileys_message_id" in sql
    assert "w.id <= $2" in sql
    assert "direction = 'inbound'" in sql
    assert "media_stored_path IS NOT NULL" in sql
    assert "sender_phone" in sql
    assert "chat_type" in sql and "group_jid" in sql
    assert "group_subject_snapshot" in sql


def test_scrub_group_phone_sql_only_targets_group_wa_mirror_rows() -> None:
    irb = _load()
    select_sql = irb.SCRUB_GROUP_PHONE_SELECT_SQL
    apply_sql = irb.SCRUB_GROUP_PHONE_APPLY_SQL

    assert "'wa-mirror:' || w.baileys_message_id" in select_sql
    assert "q.source = 'whatsapp'" in select_sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in select_sql
    assert "w.chat_type = 'group' OR w.group_jid IS NOT NULL" in select_sql
    assert "q.sender_phone IS NOT NULL OR q.client_id_hint IS NOT NULL" in select_sql

    assert "sender_phone = NULL" in apply_sql
    assert "client_id_hint = NULL" in apply_sql


def test_source_context_backfill_sql_targets_unannotated_wa_mirror_rows() -> None:
    irb = _load()
    select_sql = irb.SOURCE_CONTEXT_BACKFILL_SELECT_SQL
    apply_sql = irb.SOURCE_CONTEXT_BACKFILL_APPLY_SQL

    assert "'wa-mirror:' || w.baileys_message_id" in select_sql
    assert "q.source = 'whatsapp'" in select_sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in select_sql
    assert "q.source_context = '{}'::jsonb" in select_sql
    assert "group_subject_snapshot" in select_sql
    assert "source_context = $2::jsonb" in apply_sql


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


def test_direct_unknown_text_autocatalog_select_guards_are_all_present() -> None:
    irb = _load()
    sql = irb.DIRECT_UNKNOWN_TEXT_AUTOCATALOG_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in sql
    assert "'wa-mirror:' || w.baileys_message_id" in sql
    assert "q.status <> 'dead'" in sql
    assert "doc_type', 'unknown') = 'unknown'" in sql
    assert "ocr_text_per_page" in sql
    assert "jsonb_typeof(page.value) = 'string'" in sql
    assert "ocr_chars >= $1" in sql
    assert "w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL" in sql
    assert "p.status = 'review_pending'" in sql
    assert "LIMIT $2" in sql
