"""Public-driver boundary for a charged generation whose MP4 retrieval failed."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO_ROOT / "scripts" / "wr3_render_episode.py"
WORKFLOW_ID = "workflow-paid-exact-001"
MEDIA_ID = "media-paid-exact-001"
PROJECT_ID = "project-exact-001"
SCENE_ID = "scene-ambiguous-exact-001"


def _load_driver(monkeypatch: pytest.MonkeyPatch, episode_dir: Path) -> ModuleType:
    monkeypatch.setattr(sys, "argv", [str(DRIVER_PATH), str(episode_dir)])
    spec = importlib.util.spec_from_file_location(
        "wr3_render_episode_retry_boundary_test",
        DRIVER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("boundary_kind", ["retrieval", "ambiguous_generation"])
@pytest.mark.asyncio
async def test_no_resubmit_error_halts_public_driver_after_exactly_one_submit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary_kind: str,
) -> None:
    """The driver's three-attempt loop must stop at either charging boundary."""
    episode_dir = tmp_path / "episode-retrieval-boundary"
    episode_dir.mkdir()
    (episode_dir / "shot-pack.json").write_text(
        json.dumps(
            {
                "resolution": "720x1280",
                "aspect_ratio": "9:16",
                "shots": [
                    {
                        "shot_id": "s001",
                        "prompt_positive": "first paid shot",
                        "duration_s": 8,
                    },
                    {
                        "shot_id": "s002",
                        "prompt_positive": "must never be submitted",
                        "duration_s": 8,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    driver = _load_driver(monkeypatch, episode_dir)
    monkeypatch.setattr(driver, "zero_spend_enabled", lambda: False)
    monkeypatch.setattr(
        driver,
        "_health",
        lambda: {"extension_connected": True, "status": "healthy"},
    )

    context = driver.fk.EpisodeContext(
        project_id=PROJECT_ID,
        video_id="video-exact-001",
        project_name=episode_dir.name,
        endpoint="http://flowkit.test:8100",
        paygate=driver.fk.DEFAULT_PAYGATE,
    )

    async def fake_setup_episode_context(*, name: str, endpoint: str) -> Any:
        assert name == episode_dir.name
        assert endpoint == driver.ENDPOINT
        return context

    destination = episode_dir / "clips" / "01.mp4"
    submit_calls: list[int] = []

    async def retrieval_failure(request: Any, **kwargs: Any) -> Any:
        submit_calls.append(request.shot_index)
        assert kwargs["episode_dir"] == episode_dir
        assert kwargs["episode_context"] is context
        if boundary_kind == "retrieval":
            raise driver.fk.FlowkitRetrievalError(
                workflow_id=WORKFLOW_ID,
                media_id=MEDIA_ID,
                destination=destination,
                cause=driver.fk.FlowkitTimeoutError("signed media still unavailable"),
            )
        raise driver.fk.FlowkitGenerationAmbiguousError(
            project_id=PROJECT_ID,
            scene_id=SCENE_ID,
            cause=driver.fk.FlowkitTimeoutError("generate POST outcome unavailable"),
        )

    monkeypatch.setattr(driver.fk, "setup_episode_context", fake_setup_episode_context)
    monkeypatch.setattr(driver.fk, "submit_clip", retrieval_failure)

    result = await driver.main()

    assert result == 5
    assert submit_calls == [1]
    report = json.loads((episode_dir / "render-report.json").read_text())
    assert report["status"] == "HALT"
    assert report["recovery_required"] is True
    assert report["automatic_resubmit_forbidden"] is True
    assert report["rendered"] == []
    if boundary_kind == "retrieval":
        assert report["recovery"] == {
            "workflow_id": WORKFLOW_ID,
            "media_id": MEDIA_ID,
            "destination": str(destination),
        }
        assert report["failed"] == [
            {
                "shot_id": "s001",
                "reason": "retrieval_failed_after_generation",
                "recovery_required": True,
                "automatic_resubmit_forbidden": True,
                "workflow_id": WORKFLOW_ID,
                "media_id": MEDIA_ID,
                "destination": str(destination),
                "error": "signed media still unavailable",
            }
        ]
    else:
        assert report["recovery"] == {
            "project_id": PROJECT_ID,
            "scene_id": SCENE_ID,
        }
        assert report["failed"] == [
            {
                "shot_id": "s001",
                "reason": "generation_state_ambiguous",
                "recovery_required": True,
                "automatic_resubmit_forbidden": True,
                "project_id": PROJECT_ID,
                "scene_id": SCENE_ID,
                "error": "generate POST outcome unavailable",
            }
        ]

    report_path = episode_dir / "render-report.json"
    report_bytes = report_path.read_bytes()

    def network_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("rerun reached health or context network path")

    async def submit_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("rerun submitted a paid clip")

    monkeypatch.setattr(driver, "_health", network_must_not_run)
    monkeypatch.setattr(driver.fk, "setup_episode_context", submit_must_not_run)
    monkeypatch.setattr(driver.fk, "submit_clip", submit_must_not_run)

    rerun_result = await driver.main()

    assert rerun_result == 6
    assert report_path.read_bytes() == report_bytes
    assert submit_calls == [1]


@pytest.mark.asyncio
async def test_unsafe_endpoint_halts_before_health_or_submit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    episode_dir = tmp_path / "episode-unsafe-endpoint"
    episode_dir.mkdir()
    (episode_dir / "shot-pack.json").write_text(
        json.dumps(
            {"shots": [{"shot_id": "s001", "prompt_positive": "must not submit"}]}
        ),
        encoding="utf-8",
    )
    driver = _load_driver(monkeypatch, episode_dir)
    monkeypatch.setattr(driver, "ENDPOINT", "http://attacker.invalid:8100")
    monkeypatch.setattr(driver, "zero_spend_enabled", lambda: False)

    def network_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unsafe endpoint reached health")

    async def submit_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unsafe endpoint reached paid client")

    monkeypatch.setattr(driver, "_health", network_must_not_run)
    monkeypatch.setattr(driver.fk, "setup_episode_context", submit_must_not_run)
    monkeypatch.setattr(driver.fk, "submit_clip", submit_must_not_run)

    result = await driver.main()

    assert result == 6
    assert not (episode_dir / "render-report.json").exists()
    assert not (episode_dir / "_flowkit_context.json").exists()


@pytest.mark.asyncio
async def test_ordinary_flowkit_error_keeps_existing_three_attempt_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only no-resubmit subclasses cross the new hard retry boundary."""
    episode_dir = tmp_path / "episode-pre-submit-retry"
    episode_dir.mkdir()
    (episode_dir / "shot-pack.json").write_text(
        json.dumps(
            {
                "shots": [
                    {
                        "shot_id": "s001",
                        "prompt_positive": "definitive pre-submit failure",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    driver = _load_driver(monkeypatch, episode_dir)
    monkeypatch.setattr(driver, "zero_spend_enabled", lambda: False)
    monkeypatch.setattr(
        driver,
        "_health",
        lambda: {"extension_connected": True, "status": "healthy"},
    )
    context = driver.fk.EpisodeContext(
        project_id=PROJECT_ID,
        video_id="video-exact-001",
        project_name=episode_dir.name,
        endpoint="http://flowkit.test:8100",
        paygate=driver.fk.DEFAULT_PAYGATE,
    )

    async def fake_setup_episode_context(*, name: str, endpoint: str) -> Any:
        return context

    submit_calls = 0

    async def definitive_pre_submit_failure(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal submit_calls
        submit_calls += 1
        raise driver.fk.FlowkitError("definitive pre-submit rejection")

    monkeypatch.setattr(driver.fk, "setup_episode_context", fake_setup_episode_context)
    monkeypatch.setattr(driver.fk, "submit_clip", definitive_pre_submit_failure)

    result = await driver.main()

    assert result == 1
    assert submit_calls == 3
    report = json.loads((episode_dir / "render-report.json").read_text())
    assert report["status"] == "PARTIAL"
    assert report["recovery_required"] is False
    assert "recovery" not in report
    assert report["failed"] == [
        {
            "shot_id": "s001",
            "reason": "definitive pre-submit rejection",
            "needs_broll_curator": True,
        }
    ]
