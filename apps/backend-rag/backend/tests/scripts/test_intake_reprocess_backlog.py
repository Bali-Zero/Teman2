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
import subprocess
import sys
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
    assert "--retry-typed-missing-fields" in result.stdout


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
    assert args.retry_empty_pdf_ocr is False
    assert args.retry_unschematised_supported is False
    assert args.retry_typed_missing_fields is False
    assert args.quality_sample is False
    assert args.autocatalog_direct_unknown_text is False
    assert args.autocatalog_preclassify_saved_ocr is False
    assert args.autocatalog_preclassify_vision is False
    assert args.auto_attach_eligible is False
    assert args.auto_attach_direct_phone is False
    assert args.delivery_readiness_report is False
    assert args.pipeline_version == irb.DEFAULT_PIPELINE_VERSION
    assert args.empty_pdf_ocr_version == irb.DEFAULT_EMPTY_PDF_OCR_VERSION
    assert args.unschematised_pipeline_version == irb.DEFAULT_UNSCHEMATISED_RECOVERY_VERSION
    assert args.typed_missing_fields_version == irb.DEFAULT_TYPED_MISSING_FIELDS_VERSION
    assert args.quality_sample_size == 100
    assert args.quality_source == "whatsapp"
    assert args.quality_pipeline_version is None
    assert args.quality_statuses is None
    assert args.quality_exclude_stub is False
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


def test_parser_retry_typed_missing_fields_options_are_dry_run() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--retry-typed-missing-fields",
            "--typed-missing-fields-version",
            "v9-typed-fields",
        ]
    )
    assert args.apply is False
    assert args.retry_typed_missing_fields is True
    assert args.typed_missing_fields_version == "v9-typed-fields"


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
    assert "skt" in doc_types
    assert "unknown" not in doc_types

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
    assert "last_error      = NULL" in sql
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
    assert "last_error      = NULL" in sql
    assert "pipeline_version = $2" in sql


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


def test_typed_missing_fields_select_guards_are_all_present() -> None:
    irb = _load()
    sql = irb.TYPED_MISSING_FIELDS_SELECT_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "status IN ('extracted', 'validated', 'done')" in sql
    assert "doc_type = ANY($1::text[])" in sql
    assert "NOT IN ('unknown', 'missing')" in sql
    assert "jsonb_each" in sql
    assert "filled_fields = 0" in sql
    assert "NOT EXISTS" in sql
    assert "NOT IN ('review_pending', 'quarantine', 'superseded')" in sql


def test_typed_missing_fields_supersede_only_review_or_quarantine() -> None:
    irb = _load()
    sql = irb.TYPED_MISSING_FIELDS_SUPERSEDE_SQL
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


# ---------------------------------------------------------------------------
# --backfill-identity (intake-v2 PR-2 identity backfill)
# ---------------------------------------------------------------------------


def test_parser_backfill_identity_is_dry_run_and_batched() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--backfill-identity"])
    assert args.apply is False
    assert args.backfill_identity is True
    assert args.identity_after_id == 0
    assert args.identity_limit == 500


def test_parser_backfill_identity_overrides() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(
        [
            "--backfill-identity",
            "--identity-after-id",
            "194741",
            "--identity-limit",
            "50",
            "--apply",
        ]
    )
    assert args.identity_after_id == 194741
    assert args.identity_limit == 50
    assert args.apply is True


def test_backfill_identity_select_sql_scopes_whatsapp_unstamped_only() -> None:
    irb = _load()
    sql = irb.BACKFILL_IDENTITY_SELECT_SQL
    assert "source = 'whatsapp'" in sql
    assert "sender_phone IS NOT NULL" in sql
    assert "client_id_hint IS NULL" in sql
    assert "id > $1" in sql
    assert "LIMIT $2" in sql


def test_backfill_identity_apply_sql_never_overwrites_existing_hint() -> None:
    irb = _load()
    sql = irb.BACKFILL_IDENTITY_APPLY_SQL
    assert "client_id_hint IS NULL" in sql


def test_backfill_identity_select_sql_excludes_unpolicy_tagged_wa_mirror_rows() -> None:
    """P0-2 (adversarial review, 2026-07-18): the backlog SELECT previously
    matched ANY whatsapp row with a sender_phone + no hint — including
    wa-mirror GROUP rows and staff-forward rows that --scrub-group-phone
    exists to clean. Now scoped to non-mirror rows OR mirror rows already
    tagged sender_phone_enabled by --backfill-source-context."""
    irb = _load()
    sql = irb.BACKFILL_IDENTITY_SELECT_SQL
    assert "source_ref NOT LIKE 'wa-mirror:%'" in sql
    assert "source_context->>'routing_identity_policy' = 'sender_phone_enabled'" in sql


def test_main_runs_scrub_and_source_context_before_identity_backfill() -> None:
    """P0-2 ordering fix: identity-backfill's SELECT scope depends on
    source_context.routing_identity_policy already being correct — running
    it before scrub/backfill-source-context in the SAME invocation risked
    picking up a not-yet-cleaned or not-yet-tagged wa-mirror row."""
    irb = _load()
    import inspect

    src = inspect.getsource(irb.main)
    scrub_pos = src.index("run_scrub_group_phone(")
    ctx_pos = src.index("run_backfill_source_context(")
    identity_pos = src.index("run_backfill_identity(")
    assert scrub_pos < identity_pos
    assert ctx_pos < identity_pos


class _FakeIdentityConn:
    """Minimal asyncpg-shaped fake: fetch() for the candidate SELECT, execute()
    recorded for the apply UPDATE, transaction() a no-op async context."""

    def __init__(
        self,
        rows: list[dict],
        executed: list[tuple],
        update_status_by_id: dict[int, str] | None = None,
    ) -> None:
        self._rows = rows
        self._executed = executed
        self._update_status_by_id = update_status_by_id or {}

    async def fetch(self, _sql: str, *_args):
        return self._rows

    async def execute(self, sql: str, *args):
        self._executed.append((sql, args))
        queue_id = args[0] if args else None
        return self._update_status_by_id.get(queue_id, "UPDATE 1")

    async def fetchval(self, _sql: str, *_args):
        return 0

    def transaction(self):
        return _NoopAsyncCtx()


class _NoopAsyncCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(
        self,
        rows: list[dict],
        executed: list[tuple],
        update_status_by_id: dict[int, str] | None = None,
    ) -> None:
        self._conn = _FakeIdentityConn(rows, executed, update_status_by_id)

    def acquire(self):
        return _AcquireCtx(self._conn)


class _AcquireCtx:
    def __init__(self, conn: _FakeIdentityConn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


def _fake_resolution(kind: str, client_id: int | None):
    from types import SimpleNamespace

    return SimpleNamespace(kind=kind, client_id=client_id, phone_normalized=None, reason="test")


def test_run_backfill_identity_dry_run_never_writes() -> None:
    irb = _load()

    rows = [
        {"id": 100, "sender_phone": "628110000001"},
        {"id": 101, "sender_phone": "628110000002"},
    ]
    executed: list[tuple] = []
    pool = _FakePool(rows, executed)

    resolver_calls: list[bool] = []

    async def fake_resolver(_conn, *, sender_phone, force_no_create=False):
        resolver_calls.append(force_no_create)
        if sender_phone == "628110000001":
            return _fake_resolution("existing", 555)
        return _fake_resolution("ambiguous", None)

    irb.resolve_or_create_contact = fake_resolver  # module-level name used by run_backfill_identity

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=False))

    assert counts["candidates"] == 2
    assert counts["by_kind"] == {"existing": 1, "ambiguous": 1}
    assert counts["stamped"] == 0
    assert counts["errors"] == 0
    assert counts["max_id_seen"] == 101
    assert executed == []  # dry-run must never call the UPDATE
    # P0-1 fix: dry-run must force the resolver's CREATE branch unreachable,
    # independent of INTAKE_AUTOCREATE_CONTACT_ENABLED.
    assert resolver_calls == [True, True]


def test_run_backfill_identity_apply_stamps_only_resolved_rows() -> None:
    irb = _load()

    rows = [
        {"id": 100, "sender_phone": "628110000001"},
        {"id": 101, "sender_phone": "628110000002"},
    ]
    executed: list[tuple] = []
    pool = _FakePool(rows, executed)

    resolver_calls: list[bool] = []

    async def fake_resolver(_conn, *, sender_phone, force_no_create=False):
        resolver_calls.append(force_no_create)
        if sender_phone == "628110000001":
            return _fake_resolution("existing", 555)
        return _fake_resolution("ambiguous", None)

    irb.resolve_or_create_contact = fake_resolver

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=True))

    assert counts["stamped"] == 1
    assert len(executed) == 1
    sql, args = executed[0]
    assert sql is irb.BACKFILL_IDENTITY_APPLY_SQL
    assert args == (100, 555)
    # --apply must NOT force no-create — the resolver's own kill-switch stays
    # the sole gate for CREATE, never re-implemented in this caller.
    assert resolver_calls == [False, False]


def test_run_backfill_identity_resolver_error_is_isolated_per_row() -> None:
    irb = _load()

    rows = [
        {"id": 100, "sender_phone": "628110000001"},
        {"id": 101, "sender_phone": "628110000002"},
    ]
    executed: list[tuple] = []
    pool = _FakePool(rows, executed)

    async def flaky_resolver(_conn, *, sender_phone, force_no_create=False):
        if sender_phone == "628110000001":
            raise RuntimeError("boom")
        return _fake_resolution("existing", 777)

    irb.resolve_or_create_contact = flaky_resolver

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=True))

    assert counts["errors"] == 1
    assert counts["stamped"] == 1
    assert counts["by_kind"] == {"existing": 1}


def test_run_backfill_identity_does_not_count_stamped_on_update_zero() -> None:
    """P1 (adversarial review): a concurrent writer could race this row to a
    non-NULL client_id_hint between our SELECT and this UPDATE — the
    WHERE client_id_hint IS NULL guard then affects zero rows, and
    "stamped" must not lie about it."""
    irb = _load()

    rows = [
        {"id": 100, "sender_phone": "628110000001"},
        {"id": 101, "sender_phone": "628110000002"},
    ]
    executed: list[tuple] = []
    # Row 100's UPDATE loses the race (already stamped by someone else).
    pool = _FakePool(rows, executed, update_status_by_id={100: "UPDATE 0"})

    async def fake_resolver(_conn, *, sender_phone, force_no_create=False):
        if sender_phone == "628110000001":
            return _fake_resolution("existing", 555)
        return _fake_resolution("existing", 556)

    irb.resolve_or_create_contact = fake_resolver

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=True))

    assert len(executed) == 2  # both UPDATEs were attempted
    assert counts["stamped"] == 1  # only row 101's UPDATE actually touched a row
    assert counts["by_kind"] == {"existing": 2}


def test_run_backfill_identity_reports_stale_proposals_for_stamped_rows() -> None:
    """P0-3(b): stamping client_id_hint alone does not re-route an
    already-built proposal — surface the count so operators know to run
    --reprocess, instead of silently claiming the stamp fixed everything."""
    irb = _load()

    rows = [{"id": 100, "sender_phone": "628110000001"}]
    executed: list[tuple] = []
    pool = _FakePool(rows, executed)

    fetchval_calls: list[list[int]] = []

    async def spying_fetchval(sql: str, queue_ids):
        fetchval_calls.append(list(queue_ids))
        return 1

    pool._conn.fetchval = spying_fetchval

    async def fake_resolver(_conn, *, sender_phone, force_no_create=False):
        return _fake_resolution("existing", 555)

    irb.resolve_or_create_contact = fake_resolver

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=True))

    assert counts["stamped"] == 1
    assert counts["stale_proposals_need_reprocess"] == 1
    assert fetchval_calls == [[100]]


def test_run_backfill_identity_dry_run_skips_stale_proposals_count() -> None:
    """Dry-run never stamps, so there is nothing to check staleness on —
    fetchval must not even be called."""
    irb = _load()

    rows = [{"id": 100, "sender_phone": "628110000001"}]
    executed: list[tuple] = []
    pool = _FakePool(rows, executed)

    fetchval_calls: list[list[int]] = []

    async def spying_fetchval(sql: str, queue_ids):
        fetchval_calls.append(list(queue_ids))
        return 1

    pool._conn.fetchval = spying_fetchval

    async def fake_resolver(_conn, *, sender_phone, force_no_create=False):
        return _fake_resolution("existing", 555)

    irb.resolve_or_create_contact = fake_resolver

    counts = asyncio.run(irb.run_backfill_identity(pool, 0, 500, apply=False))

    assert counts["stamped"] == 0
    assert counts["stale_proposals_need_reprocess"] == 0
    assert fetchval_calls == []
def test_reroute_drive_folder_sql_targets_drive_zero_candidate_bucket() -> None:
    irb = _load()
    sql = irb.REROUTE_DRIVE_FOLDER_SELECT_SQL
    assert "SELECT DISTINCT ON (q.id)" in sql
    assert "q.source = 'drive'" in sql
    assert "q.source_path IS NOT NULL" in sql
    # Codex round-2 (m248): pick the LATEST proposal per queue row FIRST, and
    # only then require it to be review_pending — filtering inside the CTE
    # would resurrect rows whose newest proposal is already routed.
    assert "proposal_status = 'review_pending'" in sql
    assert "p.status = 'review_pending'" not in sql
    assert "'NO_MATCH'" in sql
    assert "jsonb_array_length" in sql
    assert "LIMIT $1" in sql


def test_reroute_drive_folder_reset_resumes_route_and_preserves_stage_output() -> None:
    # The load-bearing invariant: 97.7% of these rows' blobs are retention-
    # evicted, so the saved stage_output (OCR/extract fields) is the ONLY copy.
    # A reset that wiped it (like REPROCESS_RESET_SQL does) would be
    # irreversible data loss + a guaranteed pipeline failure at preprocess.
    irb = _load()
    sql = irb.REROUTE_DRIVE_FOLDER_RESET_SQL
    assert "stage_output" not in sql  # NEVER wiped — route-only resume
    assert "status           = 'validated'" in sql
    assert "stage            = 'validate'" in sql
    assert "pipeline_version = $2" in sql
    assert "lease_owner      = NULL" in sql
    assert "lease_expires_at = NULL" in sql
    assert "attempts         = 0" in sql
    # guilt check: the FULL-rerun reset (for contrast) DOES wipe stage_output.
    assert "stage_output" in irb.REPROCESS_RESET_SQL


def test_reroute_drive_folder_supersede_only_review_pending() -> None:
    irb = _load()
    sql = irb.REROUTE_DRIVE_FOLDER_SUPERSEDE_SQL
    assert "SET status = 'superseded'" in sql
    assert "p.status = 'review_pending'" in sql
    # Codex round-4: the sibling sweep is id-bounded BELOW each confirmed
    # proposal — a proposal born after the SELECT is never touched.
    assert "p.id < sel.pid" in sql
    assert "p.queue_id = sel.qid" in sql


def test_reroute_selected_supersede_is_proposal_scoped_and_confirms() -> None:
    # Codex round-3: the CONFIRMING supersede must target the exact selected
    # proposal ids (an older pending sibling must never, alone, confirm a
    # reset while the newer proposal sits claimed under a reviewer).
    irb = _load()
    sql = irb.REROUTE_SUPERSEDE_SELECTED_SQL
    assert "id = ANY($1::bigint[])" in sql
    assert "queue_id = ANY" not in sql
    assert "status = 'review_pending'" in sql
    assert "RETURNING id, queue_id" in sql


def test_reroute_npwp_sql_targets_full_npwp_review_pending() -> None:
    # m248: selects review_pending rows with a FULL extracted npwp (>=15
    # digits after normalization) from either the routed fields or the saved
    # extract payload — no source / candidate-count filter (the docs that can
    # gain the npwp signal already carry folder/fuzzy candidates).
    irb = _load()
    sql = irb.REROUTE_NPWP_SELECT_SQL
    assert "SELECT DISTINCT ON (q.id)" in sql
    assert "proposal_status = 'review_pending'" in sql
    assert "npwp_number" in sql
    # exact-length gate: valid NPWP is 15 or 16 digits, never >=17 garble.
    assert "IN (15, 16)" in sql
    assert ">= 15" not in sql
    assert "LIMIT $1" in sql
    # innocence: it must NOT copy the folder-mode drive/0-candidate filters.
    assert "q.source = 'drive'" not in sql
    assert "jsonb_array_length" not in sql


def test_reroute_npwp_reuses_route_only_reset_contract() -> None:
    # Both modes go through the ONE shared engine — the stage_output
    # preservation invariant is inherited, and neither mode can grow reset
    # SQL of its own that could drift.
    irb = _load()
    assert not hasattr(irb, "REROUTE_NPWP_RESET_SQL")
    assert not hasattr(irb, "REROUTE_NPWP_SUPERSEDE_SQL")
    import inspect

    engine_src = inspect.getsource(irb._run_route_only_reroute)
    assert "REROUTE_DRIVE_FOLDER_RESET_SQL" in engine_src
    assert "REROUTE_SUPERSEDE_SELECTED_SQL" in engine_src
    assert "REROUTE_ELIGIBLE_LOCK_SQL" in engine_src
    for fn in (
        irb.run_reroute_npwp,
        irb.run_reroute_drive_folder,
        irb.run_reroute_identity_backfill,
    ):
        assert "_run_route_only_reroute" in inspect.getsource(fn)


def test_reroute_eligible_lock_never_yanks_active_lease() -> None:
    # Codex round-2: the reset must skip rows the worker is actively
    # processing, inside one transaction, safe under concurrent invocations.
    irb = _load()
    sql = irb.REROUTE_ELIGIBLE_LOCK_SQL
    assert "lease_owner IS NULL OR lease_expires_at <= now()" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_reroute_reset_only_actually_superseded_rows() -> None:
    # Codex round-3: a proposal a human claims between SELECT and supersede
    # (review_pending -> review_claimed) must be left alone entirely — the
    # confirming supersede RETURNs (id, queue_id) and ONLY confirmed queue
    # rows get the sibling sweep + reset.
    irb = _load()
    import inspect

    src = inspect.getsource(irb._run_route_only_reroute)
    assert "REROUTE_SUPERSEDE_SELECTED_SQL, selected_pids" in src
    assert "confirmed_qids_arr" in src and "confirmed_pids" in src
    assert "REROUTE_DRIVE_FOLDER_RESET_SQL, superseded_qids" in src


def test_reroute_pipeline_version_defaults_per_mode() -> None:
    # --reroute-pipeline-version default is None; each mode picks its own tag
    # so each reroute family stays measurable independently.
    irb = _load()
    import inspect

    src = inspect.getsource(irb.main)
    assert 'or "v2.2-m227-folder"' in src
    assert 'or "v2.3-npwp"' in src
    assert 'or "v2.4-identity-backfill"' in src


def test_reroute_identity_backfill_sql_is_narrow_and_malformed_json_safe() -> None:
    irb = _load()
    sql = irb.REROUTE_IDENTITY_BACKFILL_SELECT_SQL

    # Latest proposal first; only a currently reviewable row may be reset.
    assert "SELECT DISTINCT ON (q.id)" in sql
    assert "proposal_status = 'review_pending'" in sql
    assert "p.status = 'review_pending'" not in sql

    # A live, non-reverted passport/KITAS value plus matching provenance is
    # required. A leftover top-level identity_backfill object is insufficient.
    assert "NULLIF(btrim(passport_number), '') IS NOT NULL" in sql
    assert "NULLIF(btrim(kitas_number), '') IS NOT NULL" in sql
    assert "identity_backfill,passport_number,reverted" in sql
    assert "identity_backfill,kitas_number,reverted" in sql
    assert "deleted_at IS NULL" in sql

    # Only documents carrying the same kind of extracted identity field are
    # rerouted; unrelated pending documents for the same client stay put.
    for key in (
        "passport_no",
        "passport_number",
        "kitas_no",
        "kitas_number",
        "itap_no",
        "itk_no",
        "stay_permit_no",
    ):
        assert f"'{key}'" in sql
    assert "jsonb_each(extracted_fields)" in sql

    # Historical malformed candidates fail closed instead of aborting the
    # whole SELECT. Already-strong candidates are not rerouted pointlessly.
    assert "jsonb_typeof(entity_resolution->'candidates') = 'array'" in sql
    assert "WHEN (cand->>'id') ~ '^[0-9]+$'" in sql
    assert "cand->>'table' = 'clients'" in sql
    assert "passport_number|kitas_number" in sql
    assert "LIMIT $1" in sql

    # No accidental inheritance from the Drive/NPWP reroute populations.
    assert "q.source = 'drive'" not in sql
    assert "npwp_number" not in sql


def test_reroute_identity_backfill_dispatches_to_shared_engine() -> None:
    irb = _load()
    captured: dict[str, object] = {}

    async def fake_engine(pool: object, **kwargs: object) -> dict[str, int]:
        captured["pool"] = pool
        captured.update(kwargs)
        return {"proposals": 2, "queue_rows": 2}

    pool = object()
    irb._run_route_only_reroute = fake_engine
    result = asyncio.run(
        irb.run_reroute_identity_backfill(
            pool, "v2.4-identity-backfill", 25, apply=False
        )
    )

    assert result == {"proposals": 2, "queue_rows": 2}
    assert captured == {
        "pool": pool,
        "mode": "reroute-identity-backfill",
        "select_sql": irb.REROUTE_IDENTITY_BACKFILL_SELECT_SQL,
        "pipeline_version": "v2.4-identity-backfill",
        "limit": 25,
        "apply": False,
    }


def test_reroute_identity_backfill_flag_is_wired() -> None:
    irb = _load()
    args = irb.build_parser().parse_args(["--reroute-identity-backfill"])
    assert args.reroute_identity_backfill is True

    import inspect

    main_src = inspect.getsource(irb.main)
    assert "args.reroute_identity_backfill" in main_src
    assert "run_reroute_identity_backfill" in main_src
    assert "--reroute-identity-backfill" in main_src
