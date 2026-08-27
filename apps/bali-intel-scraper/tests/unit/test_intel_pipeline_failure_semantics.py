from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import httpx


SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import run_intel_pipeline as pipeline_module  # type: ignore  # noqa: E402


def _pipeline(tmp_path: Path, **config: object) -> pipeline_module.IntelPipeline:
    pipeline = pipeline_module.IntelPipeline(dict(config))
    pipeline.pipeline_dir = tmp_path
    pipeline.data_dir = tmp_path
    pipeline.state_file = tmp_path / "run.json"
    pipeline.log = lambda *_args, **_kwargs: None
    return pipeline


def test_zero_enrichments_is_a_failed_step(tmp_path: Path, monkeypatch) -> None:
    pipeline = _pipeline(tmp_path, max_enrich=15)
    pipeline.state["articles"] = [
        {
            "title": "Material Indonesia policy update",
            "url": "https://example.go.id/update",
            "tier": "T1",
            "quality_score": 90,
        }
    ]
    fake_enricher = SimpleNamespace(
        batch_enrich_articles=lambda articles, max_articles: articles
    )
    monkeypatch.setitem(sys.modules, "claude_cli_enricher", fake_enricher)

    success = pipeline.step_enrichment()

    assert success is False
    step = pipeline.state["steps"]["3_enrichment"]
    assert step["status"] == "failed"
    assert step["data"]["reason"] == "all_enrichment_providers_failed"


def test_continue_on_error_never_reports_false_green(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline = _pipeline(tmp_path, continue_on_error=True)
    monkeypatch.setattr(
        pipeline_module,
        "PIPELINE_STEPS",
        ["3_enrichment", "5_seo", "6_approval", "8_images", "7_publishing"],
    )
    latest = tmp_path / "intel_output_latest.json"
    latest.write_text('{"sentinel":"last-known-good"}', encoding="utf-8")
    called: list[str] = []

    def fake_run_step(step: str) -> bool:
        called.append(step)
        pipeline.update_step_status(step, "failed", {"fatal": True})
        return False

    monkeypatch.setattr(pipeline, "run_step", fake_run_step)
    monkeypatch.setattr(pipeline, "print_summary", lambda: None)

    success = pipeline.run()

    assert success is False
    assert pipeline.state["status"] == "completed_with_errors"
    assert pipeline.state["failed_steps"] == [
        "3_enrichment",
        "5_seo",
        "6_approval",
        "8_images",
        "7_publishing",
    ]
    assert called == ["3_enrichment"]
    for step in ("5_seo", "6_approval", "8_images", "7_publishing"):
        assert pipeline.state["steps"][step]["status"] == "blocked"
        assert pipeline.state["steps"][step]["data"]["dependency"] == "3_enrichment"
    assert latest.read_text(encoding="utf-8") == '{"sentinel":"last-known-good"}'


def test_publishing_zero_enriched_is_skipped_without_outward_side_effects(
    tmp_path: Path,
) -> None:
    pipeline = _pipeline(tmp_path)
    pipeline.state["articles"] = [{"title": "Unenriched article"}]

    success = pipeline.step_publishing()

    assert success is True
    step = pipeline.state["steps"]["7_publishing"]
    assert step["status"] == "skipped"
    assert step["data"] == {
        "reason": "no_enriched_articles",
        "selected": 0,
        "submitted": 0,
    }


def test_all_submission_failures_are_fatal_before_telegram(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline = _pipeline(tmp_path)
    pipeline.state["articles"] = [
        {
            "title": "Enriched article",
            "url": "https://example.go.id/update",
            "enrichment": {"headline": "Enriched article"},
        }
    ]
    telegram_calls: list[str] = []

    class FakeResponse:
        status_code = 503

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: telegram_calls.append("called"),
    )

    success = pipeline.step_publishing()

    assert success is False
    assert telegram_calls == []
    step = pipeline.state["steps"]["7_publishing"]
    assert step["status"] == "failed"
    assert step["data"]["reason"] == "all_news_room_submissions_failed"


def test_unhandled_step_exception_is_fatal_and_preserves_latest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline = _pipeline(tmp_path, continue_on_error=True)
    latest = tmp_path / "intel_output_latest.json"
    latest.write_text('{"sentinel":"last-known-good"}', encoding="utf-8")
    monkeypatch.setattr(pipeline_module, "PIPELINE_STEPS", ["1_scraping"])
    monkeypatch.setattr(
        pipeline,
        "step_scraping",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(pipeline, "print_summary", lambda: None)

    success = pipeline.run()

    assert success is False
    assert pipeline.state["status"] == "completed_with_errors"
    assert pipeline.state["failed_steps"] == ["1_scraping"]
    assert pipeline.state["steps"]["1_scraping"]["data"]["fatal"] is True
    assert latest.read_text(encoding="utf-8") == '{"sentinel":"last-known-good"}'


def test_qwen_filter_forces_non_thinking_json_and_reports_actual_model(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline = _pipeline(tmp_path, min_score=30)
    pipeline.state["articles"] = [
        {
            "title": "Indonesia updates investor rules",
            "content": "An official Indonesian policy update for foreign investors.",
            "source": "Official source",
            "tier": "T1",
        }
    ]
    observed_payloads: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    def fake_get(*_args: object, **_kwargs: object) -> FakeResponse:
        return FakeResponse({"models": [{"name": "qwen3.5:9b"}]})

    def fake_post(*_args: object, **kwargs: object) -> FakeResponse:
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        observed_payloads.append(payload)
        return FakeResponse({"response": json.dumps([{"id": 1, "s": 88}])})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    assert pipeline.step_qwen_filter() is True
    assert observed_payloads[0]["think"] is False
    assert observed_payloads[0]["format"] == "json"
    step = pipeline.state["steps"]["2.5_qwen_filter"]
    assert step["data"]["errors"] == 0
    assert step["data"]["method"] == "qwen3.5:9b"
    assert pipeline.state["articles"][0]["quality_score"] == 88
