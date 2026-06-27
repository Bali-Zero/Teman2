"""Unit tests for scripts/intake_reprocess_backlog.py (pure parts only).

No Postgres: covers the watermark-file parsing, the row→enqueue mapping (whose
source_ref format is the anti-join dedup key — drift would break idempotency),
the CLI defaults (dry-run!), and the load-bearing predicates baked into the SQL
constants. The DB-side effects run on the Pro at rollout (dry-run first).
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path

import httpx
import pytest

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


def test_load_scoped_wa_mirror_delivery_env_uses_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    irb = _load()
    for name in irb.SCOPED_WA_MIRROR_DELIVERY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".wa-mirror.env"
    env_file.write_text(
        "\n".join(
            [
                "WA_MIRROR_CRM_WRITE_KEY='wa-secret'",
                "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=true",
                "WA_MIRROR_SESSION_LABEL=Bali Zero Main",
                "INTAKE_DATABASE_URL=postgresql://wrong/db",
            ]
        )
    )

    loaded = irb.load_scoped_wa_mirror_delivery_env(env_file)

    assert loaded == (
        "WA_MIRROR_CRM_WRITE_KEY",
        "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED",
    )
    assert os.environ["WA_MIRROR_CRM_WRITE_KEY"] == "wa-secret"
    assert os.environ["INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED"] == "true"
    assert "WA_MIRROR_SESSION_LABEL" not in os.environ
    assert "INTAKE_DATABASE_URL" not in os.environ


def test_crm_push_write_key_prefers_intake_specific_key(monkeypatch: pytest.MonkeyPatch) -> None:
    irb = _load()
    monkeypatch.setattr(irb, "WA_MIRROR_ENV_FILE", Path("/tmp/does-not-exist-wa-env"))
    monkeypatch.setenv("WA_MIRROR_CRM_WRITE_KEY", "wa-key")
    monkeypatch.setenv("INTAKE_CRM_PUSH_WRITE_KEY", "intake-key")
    assert irb._crm_push_write_key_from_env() == "intake-key"


def test_crm_service_write_preflight_status_contract() -> None:
    irb = _load()
    assert irb._crm_service_write_preflight_accepted(422) is True
    assert irb._crm_service_write_preflight_accepted(401) is False
    assert irb._crm_service_write_preflight_accepted(404) is False


def test_crm_service_write_preflight_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    irb = _load()
    monkeypatch.setattr(irb, "WA_MIRROR_ENV_FILE", Path("/tmp/does-not-exist-wa-env"))
    monkeypatch.delenv("WA_MIRROR_CRM_WRITE_KEY", raising=False)
    monkeypatch.delenv("INTAKE_CRM_PUSH_WRITE_KEY", raising=False)

    with pytest.raises(irb.CrmServiceWritePreflightError, match="missing"):
        asyncio.run(irb.assert_crm_service_write_preflight())


def test_crm_service_write_preflight_accepts_validation_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    irb = _load()
    monkeypatch.setattr(irb, "WA_MIRROR_ENV_FILE", Path("/tmp/does-not-exist-wa-env"))
    monkeypatch.setenv("WA_MIRROR_CRM_WRITE_KEY", "secret")

    async def run() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(422, json={}))
        async with httpx.AsyncClient(transport=transport) as client:
            await irb.assert_crm_service_write_preflight(client=client)

    asyncio.run(run())


def test_crm_service_write_preflight_rejects_auth_middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    irb = _load()
    monkeypatch.setattr(irb, "WA_MIRROR_ENV_FILE", Path("/tmp/does-not-exist-wa-env"))
    monkeypatch.setenv("WA_MIRROR_CRM_WRITE_KEY", "secret")

    async def run() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"detail": "Authentication required"})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(irb.CrmServiceWritePreflightError, match="HTTP 401"):
                await irb.assert_crm_service_write_preflight(client=client)

    asyncio.run(run())


def test_delivery_readiness_report_masks_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    irb = _load()
    for name in irb.SCOPED_WA_MIRROR_DELIVERY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".wa-mirror.env"
    env_file.write_text(
        "\n".join(
            [
                "WA_MIRROR_CRM_WRITE_KEY=super-secret",
                "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=1",
                "INTAKE_CRM_PUSH_BASE_URL=https://example.test",
            ]
        )
    )
    monkeypatch.setattr(irb, "WA_MIRROR_ENV_FILE", env_file)
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")

    async def run() -> dict:
        transport = httpx.MockTransport(lambda request: httpx.Response(422, json={}))
        async with httpx.AsyncClient(transport=transport) as client:
            return await irb.run_delivery_readiness_report(client=client)

    report = asyncio.run(run())

    assert report["preflight"] == "accepted"
    assert report["crm_write_key_present"] is True
    assert report["direct_phone_auto_attach_enabled"] is True
    assert report["intake_writer_enabled"] is True
    assert report["auto_attach_enabled"] is True
    assert "super-secret" not in str(report)


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
    assert args.autocatalog_preclassify_saved_ocr is False
    assert args.autocatalog_preclassify_vision is False
    assert args.auto_attach_eligible is False
    assert args.auto_attach_direct_phone is False
    assert args.delivery_readiness_report is False
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


def test_parser_autocatalog_preclassify_saved_ocr_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--autocatalog-preclassify-saved-ocr"])
    assert args.apply is False
    assert args.autocatalog_preclassify_saved_ocr is True
    assert args.autocatalog_pipeline_version == irb.DEFAULT_AUTOCATALOG_PIPELINE_VERSION
    assert args.autocatalog_provider == irb.DEFAULT_AUTOCATALOG_PROVIDER
    assert args.autocatalog_model == irb.DEFAULT_AUTOCATALOG_TEXT_MODEL
    assert args.autocatalog_ollama_url == irb.DEFAULT_AUTOCATALOG_OLLAMA_URL
    assert args.autocatalog_mlx_base_url == irb.DEFAULT_AUTOCATALOG_MLX_BASE_URL
    assert args.autocatalog_mlx_model == irb.DEFAULT_AUTOCATALOG_MLX_MODEL
    assert args.autocatalog_timeout_seconds == irb.DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS
    assert args.autocatalog_ocr_max_chars == irb.DEFAULT_AUTOCATALOG_OCR_MAX_CHARS


def test_parser_autocatalog_preclassify_saved_ocr_mlx_overrides() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--autocatalog-preclassify-saved-ocr",
            "--autocatalog-provider",
            "mlx",
            "--autocatalog-mlx-base-url",
            "http://mini:8080/v1",
            "--autocatalog-mlx-model",
            "mlx-community/Qwen3-8B-4bit",
        ]
    )
    assert args.autocatalog_provider == "mlx"
    assert args.autocatalog_mlx_base_url == "http://mini:8080/v1"
    assert args.autocatalog_mlx_model == "mlx-community/Qwen3-8B-4bit"


def test_parser_autocatalog_preclassify_vision_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--autocatalog-preclassify-vision"])
    assert args.apply is False
    assert args.autocatalog_preclassify_vision is True
    assert args.autocatalog_vision_model == irb.DEFAULT_AUTOCATALOG_VISION_MODEL
    assert args.autocatalog_vision_max_pages == irb.DEFAULT_AUTOCATALOG_VISION_MAX_PAGES
    assert (
        args.autocatalog_vision_image_max_side
        == irb.DEFAULT_AUTOCATALOG_VISION_IMAGE_MAX_SIDE
    )
    assert args.autocatalog_ollama_url == irb.DEFAULT_AUTOCATALOG_OLLAMA_URL
    assert args.autocatalog_timeout_seconds == irb.DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS


def test_parser_autocatalog_preclassify_vision_overrides() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--autocatalog-preclassify-vision",
            "--autocatalog-vision-model",
            "qwen2.5vl:7b",
            "--autocatalog-vision-max-pages",
            "1",
            "--autocatalog-vision-image-max-side",
            "640",
            "--autocatalog-timeout-seconds",
            "9",
        ]
    )
    assert args.autocatalog_vision_model == "qwen2.5vl:7b"
    assert args.autocatalog_vision_max_pages == 1
    assert args.autocatalog_vision_image_max_side == 640
    assert args.autocatalog_timeout_seconds == 9


def test_parser_auto_attach_eligible_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--auto-attach-eligible"])
    assert args.apply is False
    assert args.auto_attach_eligible is True
    assert args.auto_attach_limit == irb.DEFAULT_AUTO_ATTACH_LIMIT


def test_parser_auto_attach_eligible_override() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        ["--auto-attach-eligible", "--apply", "--auto-attach-limit", "17"]
    )
    assert args.apply is True
    assert args.auto_attach_limit == 17


def test_parser_auto_attach_direct_phone_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--auto-attach-direct-phone"])
    assert args.apply is False
    assert args.auto_attach_direct_phone is True
    assert args.auto_attach_limit == irb.DEFAULT_AUTO_ATTACH_LIMIT


def test_parser_auto_attach_direct_phone_reuses_limit() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        ["--auto-attach-direct-phone", "--apply", "--auto-attach-limit", "23"]
    )
    assert args.apply is True
    assert args.auto_attach_limit == 23


def test_parser_promote_direct_new_prospects_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--promote-direct-new-prospects"])
    assert args.apply is False
    assert args.promote_direct_new_prospects is True
    assert args.new_prospect_pipeline_version == irb.DEFAULT_NEW_PROSPECT_PIPELINE_VERSION
    assert args.auto_attach_limit == irb.DEFAULT_AUTO_ATTACH_LIMIT


def test_parser_review_backlog_report_defaults() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--review-backlog-report"])
    assert args.apply is False
    assert args.review_backlog_report is True
    assert args.autocatalog_min_ocr_chars == irb.DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS


def test_saved_ocr_pages_normalizes_downstream_shape() -> None:
    irb = _load()
    pages = irb._saved_ocr_pages(
        {
            "classify": {
                "ocr_text_per_page": [
                    {"page": 3, "ocr_text": "Nomor Induk Berusaha"},
                    "PASSPORT",
                ]
            }
        }
    )
    assert pages == [
        {"page": 3, "ocr_text": "Nomor Induk Berusaha", "text": "Nomor Induk Berusaha"},
        {"page": 1, "text": "PASSPORT"},
    ]


def test_saved_ocr_preclassify_payload_preserves_ocr_and_marks_review_band() -> None:
    irb = _load()
    payload = irb._build_saved_ocr_preclassify_payload(
        {"classify": {"ocr_text_per_page": [{"page": 0, "text": "boarding pass"}]}},
        doc_type="travel_ticket",
        model="qwen3.5:9b",
    )
    assert payload["doc_type"] == "travel_ticket"
    assert payload["type_confidence"] == irb.TEXT_LLM_CLASSIFY_CONF
    assert payload["classified_via"] == "saved_ocr_local_text_llm_preclassify"
    assert payload["classify_llm_model"] == "qwen3.5:9b"
    assert payload["ocr_text_per_page"] == [{"page": 0, "text": "boarding pass"}]
    assert payload["_metric"] == {
        "model": "qwen3.5:9b",
        "provider": irb.DEFAULT_AUTOCATALOG_PROVIDER,
        "confidence": irb.TEXT_LLM_CLASSIFY_CONF,
    }


def test_keyword_classify_saved_ocr_uses_existing_scorer_floor() -> None:
    irb = _load()
    doc_type, confidence, scores = irb._keyword_classify_saved_ocr_text(
        "BANK STATEMENT\nStatement of Account\nAccount Statement"
    )
    assert doc_type == "bank_statement"
    assert confidence >= irb.KEYWORD_CLASSIFY_MIN_CONFIDENCE
    assert scores["bank_statement"] >= confidence

    weak_type, weak_confidence, weak_scores = irb._keyword_classify_saved_ocr_text(
        "Passenger name only"
    )
    assert weak_type is None
    assert weak_confidence < irb.KEYWORD_CLASSIFY_MIN_CONFIDENCE
    assert weak_scores["travel_ticket"] == weak_confidence


def test_saved_ocr_keyword_preclassify_payload_marks_keyword_provider() -> None:
    irb = _load()
    payload = irb._build_saved_ocr_preclassify_payload(
        {"classify": {"ocr_text_per_page": [{"page": 0, "text": "bank statement"}]}},
        doc_type="bank_statement",
        provider=irb.KEYWORD_CLASSIFY_PROVIDER,
        model=irb.KEYWORD_CLASSIFY_MODEL,
        confidence=0.6,
        type_scores={"bank_statement": 0.6},
        classified_via="saved_ocr_keyword_preclassify",
    )
    assert payload["classified_via"] == "saved_ocr_keyword_preclassify"
    assert payload["classify_keyword_model"] == irb.KEYWORD_CLASSIFY_MODEL
    assert payload["classify_keyword_provider"] == irb.KEYWORD_CLASSIFY_PROVIDER
    assert payload["type_scores"] == {"bank_statement": 0.6}
    assert "classify_llm_model" not in payload


def test_saved_ocr_preclassify_attempt_payload_has_no_document_content() -> None:
    irb = _load()
    payload = irb._build_saved_ocr_preclassify_attempt_payload(
        provider="ollama",
        model="qwen2.5vl:7b",
        pipeline_version="v2.2-qwen-text-autocatalog",
        outcome="unknown",
        ocr_max_chars=1000,
    )
    assert payload == {
        "provider": "ollama",
        "model": "qwen2.5vl:7b",
        "pipeline_version": "v2.2-qwen-text-autocatalog",
        "outcome": "unknown",
        "classified_via": "saved_ocr_local_text_llm_preclassify",
        "ocr_max_chars": 1000,
    }
    assert "ocr_text_per_page" not in payload
    assert "text" not in payload


def test_saved_vision_preclassify_payload_preserves_ocr_and_marks_review_band() -> None:
    irb = _load()
    payload = irb._build_saved_vision_preclassify_payload(
        {"classify": {"ocr_text_per_page": [{"page": 0, "text": "image text"}]}},
        doc_type="passport",
        model="qwen2.5vl:7b",
        source_page=0,
        max_pages=2,
        image_max_side=960,
    )
    assert payload["doc_type"] == "passport"
    assert payload["type_confidence"] == irb.VISION_CLASSIFY_CONF
    assert payload["classified_via"] == "saved_blob_local_vision_preclassify"
    assert payload["classify_vision_model"] == "qwen2.5vl:7b"
    assert payload["ocr_text_per_page"] == [{"page": 0, "text": "image text"}]
    assert payload["vision_max_pages"] == 2
    assert payload["vision_image_max_side"] == 960
    assert payload["_metric"] == {
        "model": "qwen2.5vl:7b",
        "provider": "ollama-vision",
        "confidence": irb.VISION_CLASSIFY_CONF,
    }


def test_saved_vision_preclassify_attempt_payload_has_no_document_content() -> None:
    irb = _load()
    payload = irb._build_saved_vision_preclassify_attempt_payload(
        model="qwen2.5vl:7b",
        pipeline_version="v2.2-qwen-vision-autocatalog",
        outcome="unknown",
        max_pages=2,
        image_max_side=960,
    )
    assert payload == {
        "provider": "ollama-vision",
        "model": "qwen2.5vl:7b",
        "pipeline_version": "v2.2-qwen-vision-autocatalog",
        "outcome": "unknown",
        "classified_via": "saved_blob_local_vision_preclassify",
        "vision_max_pages": 2,
        "vision_image_max_side": 960,
    }
    assert "ocr_text_per_page" not in payload
    assert "blob_path" not in payload
    assert "text" not in payload


def test_vision_preclassify_prompt_uses_bounded_ocr_hint() -> None:
    irb = _load()
    ocr_text = "BANK STATEMENT\n" + ("transaction " * 300)
    prompt = irb._vision_preclassify_prompt(ocr_text)

    assert "OCR excerpt:" in prompt
    assert "Use the visual document layout first" in prompt
    assert "bank statement means account/balance/transaction pages" in prompt
    assert len(prompt) < len(irb._VISION_CLASSIFY_PROMPT) + len(ocr_text)
    assert "transaction" in prompt


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
    assert "AND EXISTS" in sql
    assert "LIMIT $2" in sql


def test_saved_ocr_preclassify_sql_targets_review_pending_direct_unknowns() -> None:
    irb = _load()
    sql = irb.SAVED_OCR_PRECLASSIFY_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in sql
    assert "'wa-mirror:' || w.baileys_message_id" in sql
    assert "p.status = 'review_pending'" in sql
    assert "q.status <> 'dead'" in sql
    assert "doc_type', 'unknown') = 'unknown'" in sql
    assert "ocr_text_per_page" in sql
    assert "ocr_chars >= $1" in sql
    assert "w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL" in sql
    assert "stage_output" in sql
    assert "AND EXISTS" in sql
    assert "local_text_llm_preclassify_attempts" in sql
    assert "jsonb_build_object('model', $2::text, 'pipeline_version', $3::text)" in sql
    assert "LIMIT $4" in sql


def test_saved_ocr_preclassify_update_resumes_after_classify_without_reocr() -> None:
    irb = _load()
    sql = irb.SAVED_OCR_PRECLASSIFY_UPDATE_SQL
    assert "status           = 'ocr_done'" in sql
    assert "stage            = 'classify'" in sql
    assert "lease_owner      = NULL" in sql
    assert "lease_expires_at = NULL" in sql
    assert "attempts         = 0" in sql
    assert "stage_output     = jsonb_build_object('classify', $2::jsonb)" in sql
    assert "pipeline_version = $3" in sql


def test_saved_ocr_preclassify_attempt_update_preserves_review_state() -> None:
    irb = _load()
    sql = irb.SAVED_OCR_PRECLASSIFY_ATTEMPT_SQL
    assert "local_text_llm_preclassify_attempts" in sql
    assert "jsonb_set" in sql
    assert "jsonb_build_array($2::jsonb)" in sql
    assert "WHERE id = $1" in sql
    assert "status           = 'ocr_done'" not in sql
    assert "document_routing_proposal" not in sql


def test_saved_vision_preclassify_sql_targets_review_pending_direct_unknowns() -> None:
    irb = _load()
    sql = irb.SAVED_VISION_PRECLASSIFY_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in sql
    assert "'wa-mirror:' || w.baileys_message_id" in sql
    assert "p.status = 'review_pending'" in sql
    assert "q.status <> 'dead'" in sql
    assert "q.blob_path IS NOT NULL" in sql
    assert "w.media_mime" in sql
    assert "doc_type', 'unknown') = 'unknown'" in sql
    assert "ocr_text_per_page" in sql
    assert "ocr_chars >= $1" in sql
    assert "w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL" in sql
    assert "stage_output" in sql
    assert "AND EXISTS" in sql
    assert "local_vision_preclassify_attempts" in sql
    assert "jsonb_build_object('model', $2::text, 'pipeline_version', $3::text)" in sql
    assert "WHEN media_mime LIKE 'image/%' THEN 0" in sql
    assert "LIMIT $4" in sql


def test_saved_vision_preclassify_attempt_update_preserves_review_state() -> None:
    irb = _load()
    sql = irb.SAVED_VISION_PRECLASSIFY_ATTEMPT_SQL
    assert "local_vision_preclassify_attempts" in sql
    assert "jsonb_set" in sql
    assert "jsonb_build_array($2::jsonb)" in sql
    assert "WHERE id = $1" in sql
    assert "status           = 'ocr_done'" not in sql
    assert "document_routing_proposal" not in sql


def test_auto_attach_eligible_sql_targets_safe_review_bucket() -> None:
    irb = _load()
    sql = irb.AUTO_ATTACH_ELIGIBLE_SELECT_SQL
    assert "JOIN intake_queue q ON q.id = p.queue_id" in sql
    assert "q.source = 'whatsapp'" in sql
    assert "p.status = 'review_pending'" in sql
    assert "auto_attach_eligible" in sql
    assert "LIMIT $1" in sql


def test_direct_phone_auto_attach_sql_targets_safe_direct_bucket() -> None:
    irb = _load()
    sql = irb.DIRECT_PHONE_AUTO_ATTACH_SELECT_SQL
    assert "JOIN intake_queue q ON q.id = p.queue_id" in sql
    assert "q.source = 'whatsapp'" in sql
    assert "p.status = 'review_pending'" in sql
    assert "p.entity_resolution->>'decision' = 'LINK_CANDIDATE'" in sql
    assert "q.source_context->>'chat_type' = 'direct'" in sql
    assert "q.source_context->>'routing_identity_policy' = 'sender_phone_enabled'" in sql
    assert "p.routing->>'client_id' IS NOT NULL" in sql
    assert "p.routing->>'doc_type' = ANY($2::text[])" in sql
    assert "LIKE 'sender phone%'" in sql
    assert "LIMIT $1" in sql


def test_direct_new_prospect_sql_targets_safe_direct_no_match_bucket() -> None:
    irb = _load()
    sql = irb.DIRECT_NEW_PROSPECT_SELECT_SQL
    assert "SELECT DISTINCT ON (q.id)" in sql
    assert "q.source = 'whatsapp'" in sql
    assert "LEFT JOIN whatsapp_message_context w" in sql
    assert "latest.status = 'review_pending'" in sql
    assert "decision = 'NO_MATCH'" in sql
    assert "chat_type = 'direct'" in sql
    assert "sender_phone IS NOT NULL" in sql
    assert "doc_type = ANY($2::text[])" in sql
    assert "LIMIT $1" in sql


def test_direct_new_prospect_reset_resumes_route_only() -> None:
    irb = _load()
    sql = irb.DIRECT_NEW_PROSPECT_RESET_SQL
    assert "status           = 'validated'" in sql
    assert "stage            = 'validate'" in sql
    assert "client_id_hint   = $2" in sql
    assert "source_context   = CASE" in sql
    assert "pipeline_version = $4" in sql
    assert "lease_owner      = NULL" in sql
    assert "lease_expires_at = NULL" in sql
    assert "attempts         = 0" in sql


def test_review_backlog_report_sql_is_latest_aggregate_and_pii_safe() -> None:
    irb = _load()
    sql = irb.REVIEW_BACKLOG_REPORT_SQL
    assert "SELECT DISTINCT ON (q.id)" in sql
    assert "q.source = 'whatsapp'" in sql
    assert "LEFT JOIN whatsapp_message_context w" in sql
    assert "latest.mirror_chat_type = 'group'" in sql
    assert "latest.status = 'review_pending'" in sql
    assert "auto_attach_eligible" in sql
    assert "direct_phone_auto_catalog" in sql
    assert "direct_new_prospect_candidate" in sql
    assert "direct_unknown_reclassify" in sql
    assert "group_human_review" in sql
    assert "missing_context_review" in sql
    assert "doc_type = ANY($2::text[])" in sql
    assert "ocr_chars >= $1" in sql
    assert "sender phone%" in sql
    assert "SELECT 'automation_bucket'" in sql
