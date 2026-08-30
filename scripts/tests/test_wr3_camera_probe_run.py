"""Focused invariants for the deterministic one-shot camera-probe runner."""

from __future__ import annotations

import fcntl
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wr3_camera_probe_run as runner  # noqa: E402
import wr3_camera_probe_recover as probe_recovery  # noqa: E402
import wr3_originality_gate as originality  # noqa: E402


EXISTING_PROJECT_ID = "11111111-1111-4111-8111-111111111111"
EXISTING_VIDEO_ID = "22222222-2222-4222-8222-222222222222"
SCENE_START_MEDIA_ID = "33333333-3333-4333-8333-333333333333"
AUTHORIZATION_ID = "44444444-4444-4444-8444-444444444444"


def _write_runtime_pack(
    tmp_path: Path,
    *,
    bind_originality: bool = True,
    bind_publication: bool = True,
) -> tuple[Path, Path, str]:
    anchor = tmp_path / "a007.png"
    anchor.write_bytes(b"approved-a007-test-anchor")
    anchor_sha = hashlib.sha256(anchor.read_bytes()).hexdigest()
    negative = "visible text, camera overlays, extra people"
    shots = []
    for number in range(1, 5):
        variant = f"v{number:02d}"
        positive = f"A007 walks through architectural space, camera variant {number}."
        shots.append(
            {
                "index": 100 + number,
                "shot_id": f"s01{number:02d}",
                "global_probe_id": f"probe:f01:{variant}",
                "variant_id": variant,
                "variant_seed_id": f"00000000-0000-5000-8000-00000000000{number}",
                "family_id": "f01-fluid-approach",
                "creative_seed_id": "9fc9b711-be3b-45f8-9de0-fe4a7c99264e",
                "shot_type": "zantara-camera-probe",
                "prompt_positive": positive,
                "positive_prompt": positive,
                "prompt_negative": negative,
                "negative_prompt": negative,
                "identity_tokens": ["A007"],
                "duration_s": 8,
                "resolution": "720x1280",
                "aspect": "9:16",
                "audio_mode": "native-dub-safe-ambient",
            }
        )
    pack = {
        "schema_version": "wr3-camera-probe-runtime/1.0",
        "adapter_version": "1.2",
        "episode_id": "s01e13-probe-f01-test",
        "family_id": "f01-fluid-approach",
        "creative_seed_id": "9fc9b711-be3b-45f8-9de0-fe4a7c99264e",
        "identity_token": "A007",
        "anchor_image_path": str(anchor),
        "anchor_sha256": anchor_sha,
        "aspect_ratio": "9:16",
        "resolution": "720x1280",
        "shots": shots,
    }
    path = tmp_path / "runtime" / "f01-fluid-approach" / "shot-pack.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    if bind_originality:
        _bind_originality(path, tmp_path)
    if bind_publication:
        _bind_publication(path)
    return path, anchor, negative


@pytest.fixture(autouse=True)
def _test_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)


def _config(pack: Path, episode_dir: Path, **overrides: Any) -> runner.RunConfig:
    values: dict[str, Any] = {
        "shot_pack": pack,
        "variant_id": "v02",
        "episode_dir": episode_dir,
        "endpoint": "http://127.0.0.1:8100",
        "paygate": "PAYGATE_TIER_TIER1P5",
        "credit_cap": 240,
        "accounted_credits": 10,
        "measured_clip_cost": 10,
        "timeout_s": 5,
    }
    values.update(overrides)
    manifest = values.get("scene_start_manifest")
    if isinstance(manifest, Path):
        authorization = manifest.with_name("scene-start-video-authorization.json")
        values.setdefault("scene_start_authorization", authorization)
        if authorization.is_file():
            values.setdefault(
                "scene_start_authorization_sha256",
                hashlib.sha256(authorization.read_bytes()).hexdigest(),
            )
    return runner.RunConfig(**values)


def _bind_originality(pack_path: Path, root: Path) -> tuple[Path, Path, Path]:
    request = {
        "schema_version": "wr3.originality-request.v1",
        "episode_id": "s01e13-residency-permit",
        "seed_id": "9fc9b711-be3b-45f8-9de0-fe4a7c99264e",
        "parent_seed_id": None,
        "description": (
            "Fluid movement through architectural thresholds resolves into deliberate "
            "stillness and neutral light."
        ),
        "signature_axes": {
            "narrative_engine_id": "continuous-rights-unbundling",
            "spatial_metaphor_id": "invisible-thresholds",
            "opening_image_id": "warm-forward-passage",
            "emotional_turn_id": "confidence-to-calm-authority",
            "final_image_id": "neutral-locked-closeup",
            "camera_grammar_id": "tracking-compression-lockoff",
            "transition_motif_id": "architectural-occlusion",
            "sound_motif_id": "dry-latch-bridge",
            "color_arc_id": "warm-mixed-neutral",
            "blocking_id": "advance-constrain-voluntary-stop",
            "hero_prop_id": "none-body-architecture",
            "wardrobe_arc_id": "constant-ivory-gold",
        },
    }
    request_path = root / "originality-request.json"
    receipt_path = root / "originality-receipt.json"
    ledger_path = root / "originality-ledger.jsonl"
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    receipt = originality.check_and_record(
        ledger_path,
        request,
        register_root=True,
    )
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["adapter_version"] = "1.2"
    pack["originality_gate"] = {
        "verdict": "PASS",
        "registration_kind": "root",
        "signature_sha256": receipt["signature_sha256"],
        "description_sha256": receipt["description_sha256"],
        "request_path": request_path.name,
        "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "receipt_path": receipt_path.name,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "ledger_path": ledger_path.name,
        "ledger_sha256_at_registration": hashlib.sha256(
            ledger_path.read_bytes()
        ).hexdigest(),
        "ledger_record_count_at_registration": 1,
    }
    pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    return request_path, receipt_path, ledger_path


def _bind_publication(pack_path: Path) -> tuple[Path, Path]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_sha = hashlib.sha256(pack_path.read_bytes()).hexdigest()
    family_id = pack["family_id"]
    family_dir = pack_path.parent
    receipt_path = family_dir / "lineage-receipt.json"
    verdict_path = family_dir.parent / "probe-gate-verdict.json"
    receipt = {
        "schema_version": "wr3-camera-probe-lineage/1.0",
        "adapter_version": "1.2",
        "family_id": family_id,
        "creative_seed_id": pack["creative_seed_id"],
        "originality_gate": pack.get("originality_gate"),
        "source_pack": "test-source-pack.json",
        "source_pack_sha256": "a" * 64,
        "runtime_episode_id": pack["episode_id"],
        "runtime_pack": f"{family_id}/shot-pack.json",
        "runtime_pack_sha256": pack_sha,
        "transformations": [],
        "variants": [],
    }
    verdict = {
        "schema_version": "wr3-camera-probe-gate/1.0",
        "adapter_version": "1.2",
        "verdict": "PASS",
        "checks": {
            "authorization": {"passed": True, "generation_count": 4},
            "originality": {
                "passed": True,
                "signature_sha256": (pack.get("originality_gate") or {}).get(
                    "signature_sha256"
                ),
            },
        },
        "errors": [],
        "families": [
            {
                "family_id": family_id,
                "episode_id": pack["episode_id"],
                "source_pack_sha256": "a" * 64,
                "runtime_pack_sha256": pack_sha,
                "shot_count": len(pack["shots"]),
            }
        ],
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    verdict_path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    return receipt_path, verdict_path


def test_v12_runtime_requires_intact_originality_evidence_before_network(
    tmp_path: Path,
) -> None:
    pack_path, _, _ = _write_runtime_pack(tmp_path)
    receipt_path = tmp_path / "originality-receipt.json"

    validated = runner.validate_run(_config(pack_path, tmp_path / "episode"))
    assert validated.pack["originality_gate"]["verdict"] == "PASS"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["signature_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(runner.ProbeValidationError, match="receipt SHA mismatch"):
        runner.validate_run(_config(pack_path, tmp_path / "episode"))


def test_v12_runtime_without_originality_binding_fails_before_network(
    tmp_path: Path,
) -> None:
    pack_path, _, _ = _write_runtime_pack(
        tmp_path,
        bind_originality=False,
        bind_publication=False,
    )

    with pytest.raises(runner.ProbeValidationError, match="originality_gate"):
        runner.validate_run(_config(pack_path, tmp_path / "episode"))


@pytest.mark.parametrize("forged_version", ["1.1", "1.1-forged", "1.10"])
def test_legacy_or_forged_adapter_version_cannot_enter_charged_runner(
    tmp_path: Path,
    forged_version: str,
) -> None:
    pack_path, _, _ = _write_runtime_pack(tmp_path)
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["adapter_version"] = forged_version
    pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(runner.ProbeValidationError, match="exact adapter_version"):
        runner.validate_run(_config(pack_path, tmp_path / "episode"))


def test_current_fail_verdict_invalidates_stale_runtime_pack_before_network(
    tmp_path: Path,
) -> None:
    pack_path, _, _ = _write_runtime_pack(tmp_path)
    verdict_path = pack_path.parent.parent / "probe-gate-verdict.json"
    _rewrite_json(
        verdict_path,
        lambda payload: payload.update(
            {"verdict": "FAIL", "errors": ["new derivation failed"]}
        ),
    )

    with pytest.raises(
        runner.ProbeValidationError,
        match="current probe gate verdict must be exactly PASS",
    ):
        runner.validate_run(_config(pack_path, tmp_path / "episode"))


def test_tampered_lineage_receipt_invalidates_runtime_pack_before_network(
    tmp_path: Path,
) -> None:
    pack_path, _, _ = _write_runtime_pack(tmp_path)
    lineage_path = pack_path.parent / "lineage-receipt.json"
    _rewrite_json(
        lineage_path,
        lambda payload: payload.update({"runtime_pack_sha256": "0" * 64}),
    )

    with pytest.raises(
        runner.ProbeValidationError,
        match="probe lineage runtime-pack SHA mismatch",
    ):
        runner.validate_run(_config(pack_path, tmp_path / "episode"))


def _write_scene_start_evidence(
    tmp_path: Path,
    *,
    project_id: str = EXISTING_PROJECT_ID,
    video_id: str = EXISTING_VIDEO_ID,
    media_id: str = SCENE_START_MEDIA_ID,
    verdict: str = "PASS",
    manifest_sha: str | None = None,
    gate_sha: str | None = None,
) -> Path:
    frame = tmp_path / "scene-start.png"
    frame.write_bytes(b"normalized-generated-scene-start")
    actual_sha = hashlib.sha256(frame.read_bytes()).hexdigest()
    result = tmp_path / "scene-start-identity-gate.json"
    manifest = tmp_path / "scene-start-manifest.json"
    expected_sha = manifest_sha or actual_sha
    result.write_text(
        json.dumps(
            {
                "schema_version": "wr3.scene-start-identity-gate.v1",
                "run_id": "e13-f01-v03-scene-start",
                "episode_id": "s01e13-probe-f01-test",
                "project_id": project_id,
                "start_frame_path": str(frame.resolve()),
                "start_frame_sha256": gate_sha or expected_sha,
                "mock_mode": False,
                "verifier": "insightface-arcface-real",
                "face_count": 1,
                "cosine": 0.712345,
                "pass_cosine_threshold": 0.6,
                "hard_fail_cosine_threshold": 0.55,
                "verdict": verdict,
                "image_generation_count": 1,
                "video_generation_count": 0,
                "measurement": {
                    "mock_mode": False,
                    "verifier": "insightface-arcface-real",
                    "face_count": 1,
                    "cosine": 0.712345,
                    "image_sha256": gate_sha or expected_sha,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "wr3.scene-start-manifest.v1",
                "run_id": "e13-f01-v03-scene-start",
                "episode_id": "s01e13-probe-f01-test",
                "project": {"id": project_id, "video_id": video_id},
                "start_frame": {
                    "role": "scene_composition_i2v_start_frame",
                    "project_id": project_id,
                    "media_id": media_id,
                    "path": str(frame.resolve()),
                    "sha256": expected_sha,
                },
                "generation_counts": {
                    "image_generation_count": 1,
                    "video_generation_count": 0,
                },
                "identity_gate": {
                    "status": "pending_real_arcface",
                    "result_path": str(result.resolve()),
                },
            }
        ),
        encoding="utf-8",
    )
    runtime_pack = tmp_path / "runtime" / "f01-fluid-approach" / "shot-pack.json"
    pack = json.loads(runtime_pack.read_text(encoding="utf-8"))
    shot = next(item for item in pack["shots"] if item["variant_id"] == "v02")
    authorization = tmp_path / "scene-start-video-authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "schema_version": "wr3.scene-start-video-authorization.v1",
                "authorization_id": AUTHORIZATION_ID,
                "authorization_scope": "single_video_generation",
                "run_id": "e13-f01-v03-scene-start",
                "episode_id": "s01e13-probe-f01-test",
                "runtime_pack_sha256": hashlib.sha256(
                    runtime_pack.read_bytes()
                ).hexdigest(),
                "variant_id": "v02",
                "shot_id": shot["shot_id"],
                "global_probe_id": shot["global_probe_id"],
                "project_id": project_id,
                "video_id": video_id,
                "media_id": media_id,
                "bindings": {
                    "manifest_path": str(manifest.resolve()),
                    "manifest_sha256": hashlib.sha256(
                        manifest.read_bytes()
                    ).hexdigest(),
                    "identity_gate_path": str(result.resolve()),
                    "identity_gate_sha256": hashlib.sha256(
                        result.read_bytes()
                    ).hexdigest(),
                    "start_frame_path": str(frame.resolve()),
                    "start_frame_sha256": actual_sha,
                },
                "identity_decision": {
                    "verdict": verdict,
                    "mock_mode": False,
                    "verifier": "insightface-arcface-real",
                    "face_count": 1,
                    "cosine": 0.712345,
                    "pass_cosine_threshold": 0.6,
                    "hard_fail_cosine_threshold": 0.55,
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _authorization_path(manifest: Path) -> Path:
    return manifest.with_name("scene-start-video-authorization.json")


def _gate_path(manifest: Path) -> Path:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return Path(payload["identity_gate"]["result_path"])


def _rewrite_json(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _replace_selected_positive(pack: Path, words: int) -> None:
    phrase = " ".join(f"word{number}" for number in range(1, words + 1))

    def mutate(payload: dict[str, Any]) -> None:
        shot = next(item for item in payload["shots"] if item["variant_id"] == "v02")
        shot["positive_prompt"] = phrase
        shot["prompt_positive"] = phrase

    _rewrite_json(pack, mutate)
    _bind_publication(pack)


def _refresh_authorization_gate_binding(manifest: Path) -> None:
    gate = _gate_path(manifest)
    authorization = _authorization_path(manifest)

    def refresh(payload: dict[str, Any]) -> None:
        payload["bindings"]["identity_gate_sha256"] = hashlib.sha256(
            gate.read_bytes()
        ).hexdigest()

    _rewrite_json(authorization, refresh)


def _install_gateway_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    episode_dir: Path,
    negative: str,
    download_fails: bool = False,
    expected_start_image_media_id: str = "anchor-media-1",
) -> dict[str, Any]:
    calls: dict[str, Any] = {
        "http": [],
        "setup": 0,
        "scene": 0,
        "upload": 0,
        "generate": 0,
        "download": 0,
        "flow_prompt": None,
        "clip_cost_cr": None,
        "download_workflow_id": None,
        "download_dest": None,
    }

    async def fake_http_get_json(url: str, timeout_s: int) -> dict[str, Any]:
        calls["http"].append((url, timeout_s))
        if url.endswith("/health"):
            return {"status": "ok", "extension_connected": True}
        if url.endswith("/api/flow/credits"):
            credit_reads = sum(
                1
                for called_url, _ in calls["http"]
                if called_url.endswith("/api/flow/credits")
            )
            return {"credits": 120 if credit_reads == 1 else 110}
        raise AssertionError(f"unexpected HTTP call: {url}")

    async def fake_setup(
        name: str,
        *,
        endpoint: str,
        paygate: str,
        timeout_s: int,
    ) -> runner.fk.EpisodeContext:
        calls["setup"] += 1
        return runner.fk.EpisodeContext(
            project_id="project-1",
            video_id="video-1",
            project_name=name,
            endpoint=endpoint,
            paygate=paygate,
        )

    async def fake_scene(
        ctx: runner.fk.EpisodeContext,
        *,
        shot_index: int,
        positive_prompt: str,
        timeout_s: int,
    ) -> str:
        calls["scene"] += 1
        persisted = json.loads((episode_dir / runner.CONTEXT_NAME).read_text())
        assert persisted["anchor_image_path"] == ctx.anchor_image_path
        ctx.scene_ids[shot_index] = "scene-1"
        return "scene-1"

    async def fake_upload(
        ctx: runner.fk.EpisodeContext,
        *,
        image_path: Path,
        timeout_s: int,
    ) -> str:
        calls["upload"] += 1
        assert str(image_path) == ctx.anchor_image_path
        return "anchor-media-1"

    async def fake_generate(
        ctx: runner.fk.EpisodeContext,
        *,
        start_image_media_id: str,
        scene_id: str,
        prompt: str,
        timeout_s: int,
        shot_index: int,
        clip_cost_cr: int,
    ) -> tuple[str, str]:
        calls["generate"] += 1
        calls["flow_prompt"] = prompt
        calls["clip_cost_cr"] = clip_cost_cr
        persisted = json.loads((episode_dir / runner.CONTEXT_NAME).read_text())
        assert persisted["anchor_image_path"] == ctx.anchor_image_path
        assert persisted["scene_ids"] == {str(shot_index): "scene-1"}
        assert start_image_media_id == expected_start_image_media_id
        assert scene_id == "scene-1"
        assert prompt.count(negative) == 1
        return "workflow-1", "media-1"

    async def fake_download(
        ctx: runner.fk.EpisodeContext,
        *,
        media_id: str,
        dest: Path,
        timeout_s: int,
        workflow_id: str,
        poll_interval_s: int = 10,
    ) -> None:
        del poll_interval_s
        calls["download"] += 1
        calls["download_workflow_id"] = workflow_id
        calls["download_dest"] = dest
        assert media_id == "media-1"
        assert workflow_id == "workflow-1"
        if download_fails:
            raise runner.fk.FlowkitError("legacy media endpoint: 400 INVALID_ARGUMENT")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)

    monkeypatch.setattr(runner.fk, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runner.fk, "setup_episode_context", fake_setup)
    monkeypatch.setattr(runner.fk, "_create_scene", fake_scene)
    monkeypatch.setattr(runner.fk, "_upload_image_asset", fake_upload)
    monkeypatch.setattr(runner.fk, "_generate_video", fake_generate)
    monkeypatch.setattr(runner.fk, "_download_video_media", fake_download)
    monkeypatch.setattr(probe_recovery, "_download_video_media", fake_download)
    monkeypatch.setattr(probe_recovery, "_http_get_json", fake_http_get_json)
    return calls


@pytest.mark.asyncio
async def test_one_variant_makes_one_generate_call_and_persists_anchor_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, anchor, negative = _write_runtime_pack(tmp_path)
    episode_dir = tmp_path / "episode"
    calls = _install_gateway_stubs(
        monkeypatch,
        episode_dir=episode_dir,
        negative=negative,
    )

    receipt = await runner.run_one(_config(pack, episode_dir))

    assert calls["setup"] == 1
    assert calls["scene"] == 1
    assert calls["upload"] == 1
    assert calls["generate"] == 1
    assert calls["download"] == 1
    assert calls["flow_prompt"].count(negative) == 1
    assert calls["clip_cost_cr"] == 10
    assert calls["download_workflow_id"] == "workflow-1"
    assert calls["download_dest"].name.endswith(".recovery-stage.mp4")
    assert receipt["flow"]["generate_call_count"] == 1
    assert receipt["flow"]["workflow_id"] == "workflow-1"
    assert receipt["flow"]["media_id"] == "media-1"
    assert receipt["generation_status"] == "successful"
    assert receipt["retrieval_status"] == "successful"
    assert receipt["credits"]["live_before"] == 120
    assert receipt["credits"]["declared_clip_cost"] == 10
    assert receipt["credits"]["clip_cost_source"] == (
        "operator_supplied_paygate_parameter"
    )
    assert receipt["credits"]["live_after_generation"] == 110
    assert receipt["credits"]["live_balance_delta_after_generation_observed"] == 10
    assert receipt["credits"]["live_after_generation_observation_error"] is None
    assert receipt["credits"]["live_after"] == 110
    assert receipt["credits"]["live_delta"] == 10
    assert receipt["credits"]["live_balance_delta_observed"] == 10
    assert receipt["credits"]["live_delta_scope"] == (
        "global_account_balance_observation_not_per_workflow"
    )
    assert receipt["credits"]["live_delta_is_exact_workflow_cost"] is False
    assert receipt["artifact"]["bytes"] > 32
    assert receipt["recovery"]["staging"]["status"] == "published"
    assert not calls["download_dest"].exists()
    assert Path(receipt["artifact"]["mp4_path"]).is_file()
    persisted = json.loads((episode_dir / runner.CONTEXT_NAME).read_text())
    assert persisted["anchor_image_path"] == str(anchor.resolve())


@pytest.mark.asyncio
async def test_measured_clip_cost_reaches_sole_generation_call_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, negative = _write_runtime_pack(tmp_path)
    episode_dir = tmp_path / "episode"
    calls = _install_gateway_stubs(
        monkeypatch,
        episode_dir=episode_dir,
        negative=negative,
    )

    receipt = await runner.run_one(_config(pack, episode_dir, measured_clip_cost=7))

    assert calls["clip_cost_cr"] == 7
    assert calls["generate"] == 1
    assert calls["download"] == 1
    assert receipt["flow"]["generate_call_count"] == 1
    assert receipt["flow"]["download_call_count"] == 1
    assert receipt["credits"]["measured_clip_cost"] == 7
    assert receipt["credits"]["declared_clip_cost"] == 7
    assert receipt["credits"]["projected_accounted_after"] == 17


@pytest.mark.asyncio
async def test_generated_workflow_selects_workflow_aware_recovery_without_resubmit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, negative = _write_runtime_pack(tmp_path)
    episode_dir = tmp_path / "episode"
    calls = _install_gateway_stubs(
        monkeypatch,
        episode_dir=episode_dir,
        negative=negative,
    )

    receipt = await runner.run_one(_config(pack, episode_dir))

    assert calls["generate"] == 1
    assert calls["download"] == 1
    assert calls["download_workflow_id"] == "workflow-1"
    assert receipt["flow"]["workflow_id"] == "workflow-1"
    assert receipt["flow"]["generate_call_count"] == 1
    assert receipt["flow"]["download_call_count"] == 1


@pytest.mark.asyncio
async def test_existing_scene_start_reuses_context_and_never_uploads_raw_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, negative = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    episode_dir = tmp_path / "episode"
    calls = _install_gateway_stubs(
        monkeypatch,
        episode_dir=episode_dir,
        negative=negative,
        expected_start_image_media_id=SCENE_START_MEDIA_ID,
    )

    receipt = await runner.run_one(
        _config(
            pack,
            episode_dir,
            existing_project_id=EXISTING_PROJECT_ID,
            existing_video_id=EXISTING_VIDEO_ID,
            scene_start_media_id=SCENE_START_MEDIA_ID,
            scene_start_manifest=manifest,
        )
    )

    assert calls["setup"] == 0
    assert calls["scene"] == 1
    assert calls["upload"] == 0
    assert calls["generate"] == 1
    assert calls["download"] == 1
    assert receipt["flow"]["context_mode"] == "existing_scene_start"
    assert receipt["flow"]["project_id"] == EXISTING_PROJECT_ID
    assert receipt["flow"]["video_id"] == EXISTING_VIDEO_ID
    assert receipt["flow"]["anchor_media_id"] is None
    assert receipt["flow"]["start_image_media_id"] == SCENE_START_MEDIA_ID
    assert receipt["source"]["scene_start_manifest"] == str(manifest.resolve())
    assert receipt["source"]["scene_start_gate_verdict"] == "PASS"
    assert receipt["source"]["scene_start_gate_verifier"] == "insightface-arcface-real"
    assert receipt["source"]["scene_start_gate_pass_cosine_threshold"] == 0.6
    assert receipt["source"]["scene_start_gate_hard_fail_cosine_threshold"] == 0.55
    assert receipt["source"]["scene_start_authorization"] == str(
        _authorization_path(manifest).resolve()
    )
    assert (
        receipt["source"]["scene_start_authorization_sha256"]
        == hashlib.sha256(_authorization_path(manifest).read_bytes()).hexdigest()
    )
    persisted = json.loads((episode_dir / runner.CONTEXT_NAME).read_text())
    assert persisted["project_id"] == EXISTING_PROJECT_ID
    assert persisted["video_id"] == EXISTING_VIDEO_ID
    assert persisted["anchor_image_path"] is None


@pytest.mark.parametrize(
    ("project_id", "video_id", "media_id"),
    [
        (EXISTING_PROJECT_ID, None, None),
        (None, EXISTING_VIDEO_ID, None),
        (None, None, SCENE_START_MEDIA_ID),
        (EXISTING_PROJECT_ID, EXISTING_VIDEO_ID, None),
        (EXISTING_PROJECT_ID, None, SCENE_START_MEDIA_ID),
        (None, EXISTING_VIDEO_ID, SCENE_START_MEDIA_ID),
    ],
)
def test_existing_context_requires_all_three_ids_together(
    tmp_path: Path,
    project_id: str | None,
    video_id: str | None,
    media_id: str | None,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)

    with pytest.raises(
        runner.ProbeValidationError,
        match="must be supplied together",
    ):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=project_id,
                existing_video_id=video_id,
                scene_start_media_id=media_id,
                scene_start_manifest=manifest,
            )
        )


def test_existing_context_requires_scene_start_manifest(tmp_path: Path) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)

    with pytest.raises(runner.ProbeValidationError, match="manifest is required"):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
            )
        )


@pytest.mark.parametrize(
    ("authorization", "authorization_sha256", "error"),
    [
        (None, None, "scene_start_authorization is required"),
        (
            "valid",
            None,
            "scene_start_authorization_sha256 is required",
        ),
    ],
)
def test_existing_context_requires_pinned_scene_start_authorization(
    tmp_path: Path,
    authorization: str | None,
    authorization_sha256: str | None,
    error: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    authorization_path = (
        _authorization_path(manifest) if authorization == "valid" else None
    )

    with pytest.raises(runner.ProbeValidationError, match=error):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
                scene_start_authorization=authorization_path,
                scene_start_authorization_sha256=authorization_sha256,
            )
        )


def test_scene_start_manifest_cannot_select_mode_without_existing_ids(
    tmp_path: Path,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)

    with pytest.raises(
        runner.ProbeValidationError,
        match="only valid with all three existing-context IDs",
    ):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.parametrize("verdict", ["pass", "PASS_WITH_CONDITIONS", "REJECT"])
def test_existing_context_requires_exact_scene_start_pass(
    tmp_path: Path,
    verdict: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path, verdict=verdict)

    with pytest.raises(runner.ProbeValidationError, match="exactly 'PASS'"):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.parametrize(
    ("evidence_project_id", "evidence_media_id", "error"),
    [
        (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            SCENE_START_MEDIA_ID,
            "project lineage",
        ),
        (
            EXISTING_PROJECT_ID,
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "media lineage",
        ),
    ],
)
def test_existing_context_rejects_scene_start_media_lineage_mismatch(
    tmp_path: Path,
    evidence_project_id: str,
    evidence_media_id: str,
    error: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(
        tmp_path,
        project_id=evidence_project_id,
        media_id=evidence_media_id,
    )

    with pytest.raises(runner.ProbeValidationError, match=error):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.asyncio
async def test_existing_context_rejects_scene_start_video_lineage_mismatch_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(
        tmp_path,
        video_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )

    async def network_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("video lineage mismatch reached network")

    monkeypatch.setattr(runner.fk, "_http_get_json", network_must_not_run)
    with pytest.raises(runner.ProbeValidationError, match="video lineage"):
        await runner.run_one(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.parametrize(
    ("manifest_sha", "gate_sha", "error"),
    [
        ("0" * 64, None, "file SHA"),
        (None, "f" * 64, "gate image SHA"),
    ],
)
def test_existing_context_rejects_scene_start_sha_mismatch(
    tmp_path: Path,
    manifest_sha: str | None,
    gate_sha: str | None,
    error: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(
        tmp_path,
        manifest_sha=manifest_sha,
        gate_sha=gate_sha,
    )

    with pytest.raises(runner.ProbeValidationError, match=error):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.asyncio
async def test_replaced_authorization_fails_against_external_pin_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    config = _config(
        pack,
        tmp_path / "episode",
        existing_project_id=EXISTING_PROJECT_ID,
        existing_video_id=EXISTING_VIDEO_ID,
        scene_start_media_id=SCENE_START_MEDIA_ID,
        scene_start_manifest=manifest,
    )
    authorization = _authorization_path(manifest)
    authorization.write_text(
        authorization.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    async def network_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("replaced authorization reached network")

    monkeypatch.setattr(runner.fk, "_http_get_json", network_must_not_run)
    with pytest.raises(runner.ProbeValidationError, match="externally pinned value"):
        await runner.run_one(config)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["manifest", "identity_gate", "start_frame"])
async def test_replaced_gate_chain_file_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    if target == "manifest":
        _rewrite_json(manifest, lambda payload: payload.update({"tampered": True}))
    elif target == "identity_gate":
        _rewrite_json(
            _gate_path(manifest),
            lambda payload: payload.update({"reason": "replacement"}),
        )
    else:
        frame_path = Path(
            json.loads(manifest.read_text(encoding="utf-8"))["start_frame"]["path"]
        )
        frame_path.write_bytes(frame_path.read_bytes() + b"replacement")

    async def network_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(f"replaced {target} reached network")

    monkeypatch.setattr(runner.fk, "_http_get_json", network_must_not_run)
    with pytest.raises(runner.ProbeValidationError, match="SHA|sha256"):
        await runner.run_one(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


def test_reauthorized_gate_still_rejects_measurement_not_bound_to_frame(
    tmp_path: Path,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    gate = _gate_path(manifest)

    def replace_measurement_sha(payload: dict[str, Any]) -> None:
        payload["measurement"]["image_sha256"] = "f" * 64

    _rewrite_json(gate, replace_measurement_sha)
    _refresh_authorization_gate_binding(manifest)

    with pytest.raises(runner.ProbeValidationError, match="measurement image SHA"):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pass_cosine_threshold", 0.61),
        ("hard_fail_cosine_threshold", 0.54),
        ("verdict", "REJECT"),
    ],
)
def test_authorization_must_bind_exact_gate_thresholds_and_verdict(
    tmp_path: Path,
    field: str,
    value: float | str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)

    def mutate_decision(payload: dict[str, Any]) -> None:
        payload["identity_decision"][field] = value

    _rewrite_json(_authorization_path(manifest), mutate_decision)

    with pytest.raises(
        runner.ProbeValidationError,
        match=f"identity decision disagrees with gate: {field}",
    ):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_pack_sha256", "0" * 64),
        ("variant_id", "v03"),
        ("shot_id", "substituted-shot"),
        ("media_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    ],
)
def test_authorization_is_scoped_to_exact_selected_video_run(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    _rewrite_json(
        _authorization_path(manifest),
        lambda payload: payload.update({field: value}),
    )

    with pytest.raises(
        runner.ProbeValidationError,
        match=f"authorization {field} does not match the selected run",
    ):
        runner.validate_run(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )


@pytest.mark.asyncio
async def test_gate_replacement_during_preflight_stops_before_scene_or_spend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    gate = _gate_path(manifest)
    calls = {"http": 0, "scene": 0, "generate": 0}

    async def fake_http_get_json(url: str, timeout_s: int) -> dict[str, Any]:
        del timeout_s
        calls["http"] += 1
        if url.endswith("/health"):
            _rewrite_json(
                gate,
                lambda payload: payload.update({"reason": "concurrent replacement"}),
            )
            return {"status": "ok", "extension_connected": True}
        if url.endswith("/api/flow/credits"):
            return {"credits": 120}
        raise AssertionError(f"unexpected HTTP call: {url}")

    async def scene_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        calls["scene"] += 1
        raise AssertionError("replaced gate reached scene creation")

    async def generate_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        calls["generate"] += 1
        raise AssertionError("replaced gate reached charged generation")

    monkeypatch.setattr(runner.fk, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runner.fk, "_create_scene", scene_must_not_run)
    monkeypatch.setattr(runner.fk, "_generate_video", generate_must_not_run)

    with pytest.raises(runner.ProbeValidationError, match="changed after validation"):
        await runner.run_one(
            _config(
                pack,
                tmp_path / "episode",
                existing_project_id=EXISTING_PROJECT_ID,
                existing_video_id=EXISTING_VIDEO_ID,
                scene_start_media_id=SCENE_START_MEDIA_ID,
                scene_start_manifest=manifest,
            )
        )
    assert calls == {"http": 2, "scene": 0, "generate": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    ["originality_request", "originality_ledger", "lineage", "verdict"],
)
async def test_probe_authorization_replacement_during_preflight_stops_before_spend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    targets = {
        "originality_request": tmp_path / "originality-request.json",
        "originality_ledger": tmp_path / "originality-ledger.jsonl",
        "lineage": pack.parent / "lineage-receipt.json",
        "verdict": pack.parent.parent / "probe-gate-verdict.json",
    }
    calls = {"http": 0, "setup": 0, "scene": 0, "generate": 0}

    async def fake_http_get_json(url: str, timeout_s: int) -> dict[str, Any]:
        del timeout_s
        calls["http"] += 1
        if url.endswith("/health"):
            path = targets[target]
            path.write_bytes(path.read_bytes() + b" ")
            return {"status": "ok", "extension_connected": True}
        if url.endswith("/api/flow/credits"):
            return {"credits": 120}
        raise AssertionError(f"unexpected HTTP call: {url}")

    async def setup_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        calls["setup"] += 1
        raise AssertionError("changed creative authorization reached setup")

    async def scene_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        calls["scene"] += 1
        raise AssertionError("changed creative authorization reached scene")

    async def generate_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        calls["generate"] += 1
        raise AssertionError("changed creative authorization reached generation")

    monkeypatch.setattr(runner.fk, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runner.fk, "setup_episode_context", setup_must_not_run)
    monkeypatch.setattr(runner.fk, "_create_scene", scene_must_not_run)
    monkeypatch.setattr(runner.fk, "_generate_video", generate_must_not_run)

    with pytest.raises(runner.ProbeValidationError, match="changed after validation"):
        await runner.run_one(_config(pack, tmp_path / "episode"))
    assert calls == {"http": 2, "setup": 0, "scene": 0, "generate": 0}


@pytest.mark.parametrize(
    "field",
    ["existing_project_id", "existing_video_id", "scene_start_media_id"],
)
def test_existing_context_rejects_non_uuid_ids(tmp_path: Path, field: str) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    manifest = _write_scene_start_evidence(tmp_path)
    overrides: dict[str, Any] = {
        "existing_project_id": EXISTING_PROJECT_ID,
        "existing_video_id": EXISTING_VIDEO_ID,
        "scene_start_media_id": SCENE_START_MEDIA_ID,
        "scene_start_manifest": manifest,
        field: "not-a-flow-uuid",
    }

    with pytest.raises(runner.ProbeValidationError, match="canonical UUID"):
        runner.validate_run(_config(pack, tmp_path / "episode", **overrides))


@pytest.mark.asyncio
async def test_download_failure_preserves_ids_and_rerun_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, negative = _write_runtime_pack(tmp_path)
    episode_dir = tmp_path / "episode"
    calls = _install_gateway_stubs(
        monkeypatch,
        episode_dir=episode_dir,
        negative=negative,
        download_fails=True,
    )
    config = _config(pack, episode_dir)

    with pytest.raises(runner.ProbeRetrievalError, match="do not resubmit"):
        await runner.run_one(config)

    assert calls["generate"] == 1
    assert calls["download"] == 1
    assert calls["clip_cost_cr"] == 10
    receipt = json.loads((episode_dir / runner.RECEIPT_NAME).read_text())
    assert receipt["generation_status"] == "successful"
    assert receipt["retrieval_status"] == "failed"
    assert receipt["flow"]["project_id"] == "project-1"
    assert receipt["flow"]["video_id"] == "video-1"
    assert receipt["flow"]["scene_id"] == "scene-1"
    assert receipt["flow"]["workflow_id"] == "workflow-1"
    assert receipt["flow"]["media_id"] == "media-1"

    async def network_must_not_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("rerun reached network")

    monkeypatch.setattr(runner.fk, "_http_get_json", network_must_not_run)
    with pytest.raises(runner.ProbeValidationError, match="never resubmitted"):
        await runner.run_one(config)
    assert calls["generate"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8100",
        "http://localhost:8100",
        "http://127.0.0.1:8101",
        "http://user@127.0.0.1:8100",
        "http://127.0.0.1:8100/api",
        "http://127.0.0.1:8100?target=remote",
        "http://127.0.0.1:8100#fragment",
        "http://flowkit.test:8100",
    ],
)
async def test_unsafe_endpoint_fails_before_every_network_or_client_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)

    async def must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unsafe endpoint reached network/client code")

    for name in (
        "_http_get_json",
        "setup_episode_context",
        "_create_scene",
        "_upload_image_asset",
        "_generate_video",
        "_download_video_media",
    ):
        monkeypatch.setattr(runner.fk, name, must_not_run)

    with pytest.raises(runner.ProbeValidationError, match="loopback FlowKit gateway"):
        await runner.run_one(_config(pack, tmp_path / "episode", endpoint=endpoint))


@pytest.mark.asyncio
async def test_cap_failure_happens_before_every_network_or_client_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)

    async def must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("invalid cap reached network/client code")

    for name in (
        "_http_get_json",
        "setup_episode_context",
        "_create_scene",
        "_upload_image_asset",
        "_generate_video",
        "_download_video_media",
    ):
        monkeypatch.setattr(runner.fk, name, must_not_run)

    with pytest.raises(
        runner.ProbeValidationError, match="credit cap exceeded before network"
    ):
        await runner.run_one(
            _config(
                pack,
                tmp_path / "episode",
                accounted_credits=231,
                measured_clip_cost=10,
                credit_cap=240,
            )
        )


@pytest.mark.asyncio
async def test_destination_lock_rejects_concurrent_run_before_network_or_client_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    episode_dir = tmp_path / "episode"
    episode_dir.mkdir()
    lock_path = episode_dir / runner.RUN_LOCK_NAME

    async def must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("locked destination reached network/client code")

    for name in (
        "_http_get_json",
        "setup_episode_context",
        "_create_scene",
        "_upload_image_asset",
        "_generate_video",
        "_download_video_media",
    ):
        monkeypatch.setattr(runner.fk, name, must_not_run)

    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(runner.ProbeValidationError, match="already in progress"):
            await runner.run_one(_config(pack, episode_dir))

    assert lock_path.is_file()


@pytest.mark.asyncio
async def test_positive_prompt_over_tier1_cap_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    _replace_selected_positive(pack, runner.MAX_POSITIVE_PROMPT_WORDS + 1)

    async def must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("overlong prompt reached network/client code")

    for name in (
        "_http_get_json",
        "setup_episode_context",
        "_create_scene",
        "_upload_image_asset",
        "_generate_video",
        "_download_video_media",
    ):
        monkeypatch.setattr(runner.fk, name, must_not_run)

    with pytest.raises(
        runner.ProbeValidationError,
        match=r"Tier-1 dialect cap before network: 26>25 words",
    ):
        await runner.run_one(_config(pack, tmp_path / "episode"))


def test_positive_prompt_at_tier1_cap_is_accepted(tmp_path: Path) -> None:
    pack, _, _ = _write_runtime_pack(tmp_path)
    _replace_selected_positive(pack, runner.MAX_POSITIVE_PROMPT_WORDS)

    validated = runner.validate_run(_config(pack, tmp_path / "episode"))

    assert len(validated.positive_prompt.split()) == runner.MAX_POSITIVE_PROMPT_WORDS
