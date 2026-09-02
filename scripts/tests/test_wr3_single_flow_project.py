"""Regression tests for the one-Flow-project-per-episode contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_flowkit_client as fk  # noqa: E402


ENDPOINT = "http://127.0.0.1:8100"
PAYGATE = "PAYGATE_TIER_TIER1P5"
EPISODE_ID = "s01e13-residency-permit"
PROJECT_ID = "45198d2f-832d-416e-a583-886e439dcd60"
VIDEO_ID = "8a3b10d2-1fda-4086-a27d-32c0dbf0f7a7"


@pytest.mark.asyncio
async def test_character_tests_and_scenes_create_exactly_one_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = tmp_path / "flow-project-binding.json"
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_post(
        url: str,
        payload: dict[str, Any],
        timeout_s: int,
    ) -> dict[str, Any]:
        assert timeout_s == 30
        calls.append((url, payload))
        if url.endswith("/api/projects"):
            return {"id": PROJECT_ID}
        if url.endswith("/api/videos"):
            assert payload["project_id"] == PROJECT_ID
            return {"id": VIDEO_ID}
        raise AssertionError(f"unexpected endpoint: {url}")

    monkeypatch.setattr(fk, "_http_post_json", fake_post)

    character_context = await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
    )
    outfit_test_context = await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
    )
    scene_one_context = await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
    )
    scene_two_context = await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
    )

    assert [url.rsplit("/", 1)[-1] for url, _ in calls] == ["projects", "videos"]
    contexts = (
        character_context,
        outfit_test_context,
        scene_one_context,
        scene_two_context,
    )
    assert {context.project_id for context in contexts} == {PROJECT_ID}
    assert {context.video_id for context in contexts} == {VIDEO_ID}
    persisted = json.loads(binding.read_text(encoding="utf-8"))
    assert persisted["policy"] == fk.PROJECT_BINDING_POLICY
    assert persisted["episode_id"] == EPISODE_ID
    assert persisted["project_id"] == PROJECT_ID
    assert persisted["video_id"] == VIDEO_ID


@pytest.mark.asyncio
async def test_existing_m05_project_can_become_canonical_without_creating_another(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = tmp_path / "flow-project-binding.json"

    async def network_must_not_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("canonical project import attempted a network creation")

    monkeypatch.setattr(fk, "_http_post_json", network_must_not_run)
    context = await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
        expected_project_id=PROJECT_ID,
        expected_video_id=VIDEO_ID,
    )

    assert context.project_id == PROJECT_ID
    assert context.video_id == VIDEO_ID
    assert binding.is_file()


@pytest.mark.asyncio
async def test_divergent_project_is_rejected_before_every_flow_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = tmp_path / "flow-project-binding.json"
    await fk.setup_episode_context(
        EPISODE_ID,
        endpoint=ENDPOINT,
        paygate=PAYGATE,
        project_binding_path=binding,
        expected_project_id=PROJECT_ID,
        expected_video_id=VIDEO_ID,
    )

    async def network_must_not_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("project mismatch reached Flow")

    monkeypatch.setattr(fk, "_http_post_json", network_must_not_run)
    with pytest.raises(
        fk.FlowkitProjectBindingError,
        match="rejects a second project",
    ):
        await fk.setup_episode_context(
            EPISODE_ID,
            endpoint=ENDPOINT,
            paygate=PAYGATE,
            project_binding_path=binding,
            expected_project_id="99999999-9999-4999-8999-999999999999",
            expected_video_id=VIDEO_ID,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("episode_id", "another-episode", "different episode"),
        ("project_id", "", "non-blank exact string"),
        ("policy", "project_per_scene", "policy must be"),
    ],
)
def test_corrupt_or_cross_episode_binding_fails_closed(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    binding = tmp_path / "flow-project-binding.json"
    payload = {
        "schema_version": fk.PROJECT_BINDING_SCHEMA,
        "policy": fk.PROJECT_BINDING_POLICY,
        "episode_id": EPISODE_ID,
        "project_id": PROJECT_ID,
        "video_id": VIDEO_ID,
        "endpoint": ENDPOINT,
        "paygate": PAYGATE,
    }
    payload[field] = value
    binding.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(fk.FlowkitProjectBindingError, match=message):
        fk.load_episode_project_binding(
            binding,
            episode_id=EPISODE_ID,
            endpoint=ENDPOINT,
            paygate=PAYGATE,
        )


def test_camera_probe_cli_requires_shared_project_binding() -> None:
    import wr3_camera_probe_run as runner

    action = next(
        item
        for item in runner._build_parser()._actions
        if item.dest == "project_binding"
    )
    assert action.required is True
