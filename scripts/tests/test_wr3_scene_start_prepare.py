"""Fail-closed tests for the WR3 scene-first still preparation helper."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image, ImageDraw

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_scene_start_prepare import (  # noqa: E402
    AnchorLineage,
    ProjectScope,
    SceneStartConfig,
    SceneStartContext,
    SceneStartDuplicateRunError,
    SceneStartError,
    SceneStartPreflightError,
    _download_flow_image_bytes,
    build_generate_image_payload,
    load_context,
    normalize_and_validate_raster,
    prepare_scene_start,
    record_identity_gate_result,
)


def _png_bytes(
    size: tuple[int, int] = (900, 1600),
    color: tuple[int, int, int] = (154, 123, 91),
    *,
    alpha: int | None = None,
) -> bytes:
    mode = "RGBA" if alpha is not None else "RGB"
    fill: tuple[int, ...] = (*color, alpha) if alpha is not None else color
    image = Image.new(mode, size, fill)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _jpeg_bytes(
    size: tuple[int, int] = (900, 1600),
    color: tuple[int, int, int] = (154, 123, 91),
) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="JPEG")
    return output.getvalue()


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _config(
    tmp_path: Path,
    *,
    real_run: bool,
    run_id: str = "e13-f01-v03-scene-start",
    anchor_bytes: bytes | None = None,
) -> SceneStartConfig:
    anchor_data = anchor_bytes or _png_bytes((1402, 1122), (118, 91, 76))
    anchor_path = tmp_path / "a007.png"
    anchor_path.write_bytes(anchor_data)
    project_id = "project-fresh-1"
    context = SceneStartContext(
        episode_id="s01e13-residency-permit-probes-f01-v03",
        project=ProjectScope(
            project_id=project_id,
            video_id="video-fresh-1",
            project_name="s01e13-scene-start-v03",
            endpoint="http://127.0.0.1:8100",
            paygate="PAYGATE_TIER_TIER1P5",
            fresh_for_run=True,
        ),
        anchor=AnchorLineage(
            project_id=project_id,
            media_id="a007-media-in-project-1",
            path=anchor_path,
            sha256=_sha256(anchor_data),
        ),
    )
    return SceneStartConfig(
        run_id=run_id,
        context=context,
        prompt=(
            "A full-frame 9:16 scene-first still of Zantara already standing "
            "inside a quiet limestone and glass atrium in natural window light."
        ),
        destination=tmp_path / "start-frame.png",
        source_destination=tmp_path / "start-frame.source.img",
        manifest_path=tmp_path / "start-frame-manifest.json",
        receipt_path=tmp_path / "start-frame-receipt.jsonl",
        shot_index=103,
        real_run=real_run,
    )


def _dual_config(tmp_path: Path, *, real_run: bool) -> SceneStartConfig:
    config = _config(tmp_path, real_run=real_run, run_id="e13-m01-dual-scene-start")
    a002_data = _png_bytes((630, 730), (92, 71, 59))
    a002_path = tmp_path / "a002.png"
    a002_path.write_bytes(a002_data)
    context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=config.context.anchor,
        additional_identity_references=(
            AnchorLineage(
                project_id=config.context.project.project_id,
                media_id="a002-media-in-project-1",
                path=a002_path,
                sha256=_sha256(a002_data),
                reference_token="A002",
            ),
        ),
    )
    return SceneStartConfig(**{**config.__dict__, "context": context})


def _image_response(
    download_url: str = (
        "https://flow-content.google/image/generated-scene-media-1"
        "?secret=must-not-persist"
    ),
) -> dict[str, Any]:
    return {
        "media": [
            {
                "name": "generated-scene-media-1",
                "image": {
                    "generatedImage": {
                        "mediaId": "generated-scene-media-1",
                        "fifeUrl": download_url,
                        "modelNameType": "GEM_PIX_2",
                        "seed": 314159,
                    }
                },
                "dimensions": {"width": 900, "height": 1600},
            }
        ]
    }


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8100",
        "http://localhost:8100",
        "http://127.0.0.1:8101",
        "http://127.0.0.1:8100/api",
        "http://127.0.0.1:8100/?token=secret",
        "http://127.0.0.1:8100/#fragment",
        "http://user@127.0.0.1:8100",
        "http://127.0.0.1\n:8100",
    ],
)
@pytest.mark.asyncio
async def test_flowkit_endpoint_is_exact_and_fails_before_spend(
    tmp_path: Path,
    endpoint: str,
) -> None:
    config = _config(tmp_path, real_run=True)
    project = ProjectScope(
        **{
            **config.context.project.__dict__,
            "endpoint": endpoint,
        }
    )
    context = SceneStartContext(
        **{
            **config.context.__dict__,
            "project": project,
        }
    )
    invalid = SceneStartConfig(**{**config.__dict__, "context": context})
    calls = {"authorize": 0, "submit": 0}

    def authorize(**_kwargs: Any) -> None:
        calls["authorize"] += 1

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return _image_response()

    with pytest.raises(SceneStartPreflightError, match="http loopback"):
        await prepare_scene_start(
            invalid,
            submit_image=submit,
            download_image=lambda _url: _async_value(_png_bytes()),
            authorize_spend=authorize,
        )

    assert calls == {"authorize": 0, "submit": 0}
    assert not config.receipt_path.exists()


@pytest.mark.parametrize(
    "endpoint",
    ["http://127.0.0.1:8100", "http://127.0.0.1:8100/", "http://[::1]:8100"],
)
@pytest.mark.asyncio
async def test_exact_flowkit_endpoint_variants_are_accepted(
    tmp_path: Path,
    endpoint: str,
) -> None:
    config = _config(tmp_path, real_run=False)
    project = ProjectScope(**{**config.context.project.__dict__, "endpoint": endpoint})
    context = SceneStartContext(**{**config.context.__dict__, "project": project})
    valid = SceneStartConfig(**{**config.__dict__, "context": context})

    result = await prepare_scene_start(valid)

    assert result["mode"] == "dry-run"


@pytest.mark.asyncio
async def test_flow_image_download_accepts_only_allowlisted_redirect_chain() -> None:
    image_bytes = _png_bytes()
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "flow-content.google":
            return httpx.Response(
                302,
                headers={
                    "location": (
                        "https://lh3.googleusercontent.com/generated/image.png"
                        "?signature=ephemeral"
                    )
                },
            )
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=image_bytes,
        )

    result = await _download_flow_image_bytes(
        "https://flow-content.google/image/media-1?signature=ephemeral",
        timeout_s=5,
        transport=httpx.MockTransport(handler),
    )

    assert result == image_bytes
    assert requested_hosts == ["flow-content.google", "lh3.googleusercontent.com"]


@pytest.mark.asyncio
async def test_flow_image_download_rejects_unapproved_initial_host() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=_png_bytes())

    with pytest.raises(SceneStartPreflightError, match="approved HTTPS media hosts"):
        await _download_flow_image_bytes(
            "https://cdn.invalid/image.png?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 0


@pytest.mark.asyncio
async def test_flow_image_download_rejects_redirect_to_unapproved_host() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"location": "https://cdn.invalid/image.png?signature=ephemeral"},
        )

    with pytest.raises(SceneStartPreflightError, match="approved HTTPS media hosts"):
        await _download_flow_image_bytes(
            "https://flow-content.google/image/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 1


@pytest.mark.asyncio
async def test_flow_image_download_enforces_redirect_limit() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "/image/next"})

    with pytest.raises(SceneStartPreflightError, match="redirect limit"):
        await _download_flow_image_bytes(
            "https://flow-content.google/image/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 4


@pytest.mark.asyncio
async def test_flow_image_download_rejects_oversize_content_length() -> None:
    import wr3_scene_start_prepare as scene_start

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "image/png",
                "content-length": str(scene_start._FLOW_IMAGE_MAX_BYTES + 1),
            },
            content=b"",
        )

    with pytest.raises(SceneStartPreflightError, match="Content-Length exceeds"):
        await _download_flow_image_bytes(
            "https://flow-content.google/image/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_flow_image_download_enforces_streaming_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import wr3_scene_start_prepare as scene_start

    image_bytes = _png_bytes()
    monkeypatch.setattr(scene_start, "_FLOW_IMAGE_MAX_BYTES", len(image_bytes) - 1)

    class UnboundedStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield image_bytes

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            stream=UnboundedStream(),
        )

    with pytest.raises(SceneStartPreflightError, match="download exceeds"):
        await _download_flow_image_bytes(
            "https://flow-content.google/image/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.parametrize(
    ("content_type", "content", "error_match"),
    [
        ("text/html", _png_bytes(), "unsupported Content-Type"),
        ("image/png", _jpeg_bytes(), "does not match its byte signature"),
        (
            "image/png",
            b"\x89PNG\r\n\x1a\nnot-a-raster",
            "cannot be decoded as a raster",
        ),
    ],
)
@pytest.mark.asyncio
async def test_flow_image_download_rejects_mime_magic_or_decode_mismatch(
    content_type: str,
    content: bytes,
    error_match: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            content=content,
        )

    with pytest.raises(SceneStartPreflightError, match=error_match):
        await _download_flow_image_bytes(
            "https://flow-content.google/image/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_response_rejects_unapproved_fife_url_without_downloading(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    calls = {"submit": 0, "download": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return _image_response("https://cdn.invalid/image?secret=must-not-persist")

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes()

    with pytest.raises(SceneStartError, match="unusable metadata"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=download,
            authorize_spend=lambda **_kwargs: None,
        )

    assert calls == {"submit": 1, "download": 0}
    receipt_text = config.receipt_path.read_text()
    assert "cdn.invalid" not in receipt_text
    assert "secret=must-not-persist" not in receipt_text


def test_load_context_requires_project_video_id(tmp_path: Path) -> None:
    anchor = tmp_path / "a007.png"
    anchor.write_bytes(b"approved-anchor")
    context_path = tmp_path / "scene-start-context.json"
    context_path.write_text(
        json.dumps(
            {
                "schema_version": "wr3.scene-start-context.v1",
                "episode_id": "s01e13-probe-f01-test",
                "project": {
                    "id": "project-fresh-1",
                    "name": "s01e13-scene-start-test",
                    "fresh_for_run": True,
                    "endpoint": "http://127.0.0.1:8100",
                    "paygate": "PAYGATE_TIER_TIER1P5",
                },
                "anchor_lineage": {
                    "role": "identity_reference_only",
                    "project_id": "project-fresh-1",
                    "media_id": "a007-media-in-project-1",
                    "path": str(anchor.resolve()),
                    "sha256": _sha256(anchor.read_bytes()),
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SceneStartPreflightError, match=r"project\.video_id"):
        load_context(context_path)


def test_load_context_accepts_ordered_a007_a002_lineage(tmp_path: Path) -> None:
    a007_data = _png_bytes((1402, 1122), (118, 91, 76))
    a002_data = _png_bytes((630, 730), (92, 71, 59))
    a007_path = tmp_path / "a007.png"
    a002_path = tmp_path / "a002.png"
    a007_path.write_bytes(a007_data)
    a002_path.write_bytes(a002_data)
    context_path = tmp_path / "dual-context.json"
    context_path.write_text(
        json.dumps(
            {
                "schema_version": "wr3.scene-start-context.v1",
                "episode_id": "s01e13-m01",
                "project": {
                    "id": "project-fresh-1",
                    "video_id": "video-fresh-1",
                    "name": "s01e13-m01",
                    "fresh_for_run": True,
                    "endpoint": "http://127.0.0.1:8100",
                    "paygate": "PAYGATE_TIER_TIER1P5",
                },
                "anchor_lineage": {
                    "role": "identity_reference_only",
                    "project_id": "project-fresh-1",
                    "media_id": "a007-media-in-project-1",
                    "path": str(a007_path.resolve()),
                    "sha256": _sha256(a007_data),
                },
                "additional_identity_references": [
                    {
                        "reference_token": "A002",
                        "role": "identity_reference_only",
                        "project_id": "project-fresh-1",
                        "media_id": "a002-media-in-project-1",
                        "path": str(a002_path.resolve()),
                        "sha256": _sha256(a002_data),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    context = load_context(context_path)

    assert [
        item.reference_token
        for item in (context.anchor, *context.additional_identity_references)
    ] == [
        "A007",
        "A002",
    ]
    assert [
        item.media_id
        for item in (context.anchor, *context.additional_identity_references)
    ] == [
        "a007-media-in-project-1",
        "a002-media-in-project-1",
    ]


def test_dual_reference_payload_preserves_a007_then_a002_order(
    tmp_path: Path,
) -> None:
    config = _dual_config(tmp_path, real_run=False)

    payload = build_generate_image_payload(config)

    assert payload["character_media_ids"] == [
        "a007-media-in-project-1",
        "a002-media-in-project-1",
    ]


@pytest.mark.asyncio
async def test_dual_reference_manifest_and_receipt_bind_full_lineage(
    tmp_path: Path,
) -> None:
    config = _dual_config(tmp_path, real_run=True)
    captured: dict[str, Any] = {}

    async def submit(payload: dict[str, Any]) -> dict[str, Any]:
        captured["payload"] = payload
        return _image_response()

    await prepare_scene_start(
        config,
        submit_image=submit,
        download_image=lambda _url: _async_value(_png_bytes()),
        authorize_spend=lambda **_kwargs: None,
    )

    expected_media_ids = [
        "a007-media-in-project-1",
        "a002-media-in-project-1",
    ]
    assert captured["payload"]["character_media_ids"] == expected_media_ids
    manifest = json.loads(config.manifest_path.read_text())
    assert manifest["anchor_lineage"]["media_id"] == expected_media_ids[0]
    assert manifest["generation"]["character_media_ids"] == expected_media_ids
    lineages = manifest["identity_reference_lineages"]
    assert [item["reference_token"] for item in lineages] == ["A007", "A002"]
    assert [item["media_id"] for item in lineages] == expected_media_ids
    assert [item["path"] for item in lineages] == [
        str(config.context.anchor.path),
        str(config.context.additional_identity_references[0].path),
    ]
    assert [item["sha256"] for item in lineages] == [
        config.context.anchor.sha256,
        config.context.additional_identity_references[0].sha256,
    ]
    reservation = _events(config.receipt_path)[0]
    assert reservation["character_media_ids"] == expected_media_ids
    assert reservation["identity_reference_lineages"] == lineages


@pytest.mark.parametrize("duplicate_field", ["media_id", "sha256"])
@pytest.mark.asyncio
async def test_duplicate_dual_reference_identity_is_rejected(
    tmp_path: Path,
    duplicate_field: str,
) -> None:
    config = _dual_config(tmp_path, real_run=False)
    secondary = config.context.additional_identity_references[0]
    duplicate = AnchorLineage(
        project_id=secondary.project_id,
        media_id=(
            config.context.anchor.media_id
            if duplicate_field == "media_id"
            else secondary.media_id
        ),
        path=secondary.path,
        sha256=(
            config.context.anchor.sha256
            if duplicate_field == "sha256"
            else secondary.sha256
        ),
        reference_token="A002",
    )
    context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=config.context.anchor,
        additional_identity_references=(duplicate,),
    )
    invalid = SceneStartConfig(**{**config.__dict__, "context": context})

    with pytest.raises(SceneStartPreflightError, match=f"{duplicate_field} values"):
        await prepare_scene_start(invalid)


@pytest.mark.asyncio
async def test_cross_project_secondary_reference_is_rejected(tmp_path: Path) -> None:
    config = _dual_config(tmp_path, real_run=False)
    secondary = config.context.additional_identity_references[0]
    cross_project = AnchorLineage(
        project_id="different-project",
        media_id=secondary.media_id,
        path=secondary.path,
        sha256=secondary.sha256,
        reference_token="A002",
    )
    context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=config.context.anchor,
        additional_identity_references=(cross_project,),
    )
    invalid = SceneStartConfig(**{**config.__dict__, "context": context})

    with pytest.raises(SceneStartPreflightError, match="must equal project.id"):
        await prepare_scene_start(invalid)


@pytest.mark.asyncio
async def test_non_a002_secondary_reference_is_rejected(tmp_path: Path) -> None:
    config = _dual_config(tmp_path, real_run=False)
    secondary = config.context.additional_identity_references[0]
    wrong_reference = AnchorLineage(
        project_id=secondary.project_id,
        media_id=secondary.media_id,
        path=secondary.path,
        sha256=secondary.sha256,
        reference_token="A003",
    )
    context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=config.context.anchor,
        additional_identity_references=(wrong_reference,),
    )
    invalid = SceneStartConfig(**{**config.__dict__, "context": context})

    with pytest.raises(SceneStartPreflightError, match="must be 'A002'"):
        await prepare_scene_start(invalid)


@pytest.mark.asyncio
async def test_more_than_two_total_identity_references_are_rejected(
    tmp_path: Path,
) -> None:
    config = _dual_config(tmp_path, real_run=False)
    second_data = _png_bytes((640, 740), (72, 61, 53))
    second_path = tmp_path / "forbidden-third.png"
    second_path.write_bytes(second_data)
    forbidden_third = AnchorLineage(
        project_id=config.context.project.project_id,
        media_id="forbidden-third-media",
        path=second_path,
        sha256=_sha256(second_data),
        reference_token="A002",
    )
    context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=config.context.anchor,
        additional_identity_references=(
            config.context.additional_identity_references[0],
            forbidden_third,
        ),
    )
    invalid = SceneStartConfig(**{**config.__dict__, "context": context})

    with pytest.raises(SceneStartPreflightError, match="no more than 2"):
        await prepare_scene_start(invalid)


@pytest.mark.asyncio
async def test_dry_run_is_network_free_and_does_not_reserve(tmp_path: Path) -> None:
    config = _config(tmp_path, real_run=False)
    calls = {"submit": 0, "download": 0, "authorize": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return _image_response()

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes()

    def authorize(**_kwargs: Any) -> None:
        calls["authorize"] += 1

    result = await prepare_scene_start(
        config,
        submit_image=submit,
        download_image=download,
        authorize_spend=authorize,
    )

    assert result["mode"] == "dry-run"
    assert result["network_calls"] == 0
    assert calls == {"submit": 0, "download": 0, "authorize": 0}
    assert not config.receipt_path.exists()


@pytest.mark.asyncio
async def test_local_validation_failure_has_no_authorization_or_network(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    bad_anchor = AnchorLineage(
        project_id=config.context.anchor.project_id,
        media_id=config.context.anchor.media_id,
        path=config.context.anchor.path,
        sha256="0" * 64,
    )
    bad_context = SceneStartContext(
        episode_id=config.context.episode_id,
        project=config.context.project,
        anchor=bad_anchor,
    )
    bad_config = SceneStartConfig(
        **{**config.__dict__, "context": bad_context},
    )
    calls = {"submit": 0, "download": 0, "authorize": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return _image_response()

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes()

    def authorize(**_kwargs: Any) -> None:
        calls["authorize"] += 1

    with pytest.raises(SceneStartPreflightError, match="sha256 mismatch"):
        await prepare_scene_start(
            bad_config,
            submit_image=submit,
            download_image=download,
            authorize_spend=authorize,
        )

    assert calls == {"submit": 0, "download": 0, "authorize": 0}
    assert not config.receipt_path.exists()


@pytest.mark.asyncio
async def test_project_scoped_character_media_and_receipt_precedes_download(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    captured: dict[str, Any] = {}
    ordered: list[str] = []

    async def submit(payload: dict[str, Any]) -> dict[str, Any]:
        ordered.append("submit")
        captured["payload"] = payload
        return _image_response()

    async def download(_url: str) -> bytes:
        ordered.append("download")
        phases = [event["phase"] for event in _events(config.receipt_path)]
        assert phases == [
            "submission_reserved",
            "submission_response_received",
            "image_submitted",
        ]
        receipt_text = config.receipt_path.read_text()
        assert "secret=must-not-persist" not in receipt_text
        return _png_bytes()

    result = await prepare_scene_start(
        config,
        submit_image=submit,
        download_image=download,
        authorize_spend=lambda **_kwargs: None,
    )

    assert ordered == ["submit", "download"]
    assert captured["payload"] == {
        "prompt": config.prompt,
        "project_id": "project-fresh-1",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": "PAYGATE_TIER_TIER1P5",
        "character_media_ids": ["a007-media-in-project-1"],
    }
    assert result["submits_made"] == 1
    assert result["retries_made"] == 0
    assert result["image_generation_count"] == 1
    assert result["video_generation_count"] == 0
    with Image.open(config.destination) as generated:
        assert generated.size == (720, 1280)
        assert generated.mode == "RGB"

    manifest = json.loads(config.manifest_path.read_text())
    assert manifest["anchor_lineage"]["role"] == "identity_reference_only"
    assert manifest["project"]["video_id"] == "video-fresh-1"
    assert manifest["anchor_lineage"]["media_id"] == "a007-media-in-project-1"
    assert manifest["identity_reference_lineages"] == [
        {
            "reference_token": "A007",
            "role": "identity_reference_only",
            "project_id": "project-fresh-1",
            "media_id": "a007-media-in-project-1",
            "path": str(config.context.anchor.path),
            "sha256": config.context.anchor.sha256,
        }
    ]
    assert manifest["start_frame"]["role"] == "scene_composition_i2v_start_frame"
    assert manifest["start_frame"]["media_id"] == "generated-scene-media-1"
    assert manifest["anchor_lineage"]["sha256"] != manifest["start_frame"]["sha256"]
    assert manifest["generation_counts"] == {
        "image_generation_count": 1,
        "video_generation_count": 0,
    }
    assert manifest["generation"]["ledger_write_performed"] is False
    assert (
        manifest["generation"]["cost_measurement_method"] == "flow_credits_before_after"
    )
    events = _events(config.receipt_path)
    assert all(
        event["character_media_ids"] == ["a007-media-in-project-1"]
        for event in events[:3]
    )
    recovery = events[1]["recovery_metadata"]
    assert recovery["candidate_media_id"] == "generated-scene-media-1"
    assert recovery["download_url_present"] is True
    assert recovery["signed_download_url_persisted"] is False
    assert events[2]["image_generation_count"] == 1
    assert events[2]["video_generation_count"] == 0
    assert events[2]["ledger_write_performed"] is False
    assert events[2]["cost_measurement_method"] == "flow_credits_before_after"
    assert "secret=must-not-persist" not in config.manifest_path.read_text()


@pytest.mark.asyncio
async def test_missing_dimensions_are_inferred_from_same_returned_asset(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    response = _image_response()
    response["media"][0].pop("dimensions")
    calls = {"submit": 0, "download": 0}
    received_urls: list[str] = []

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return response

    async def download(url: str) -> bytes:
        calls["download"] += 1
        received_urls.append(url)
        phases = [event["phase"] for event in _events(config.receipt_path)]
        assert phases == [
            "submission_reserved",
            "submission_response_received",
            "image_submitted",
        ]
        return _png_bytes((900, 1600))

    result = await prepare_scene_start(
        config,
        submit_image=submit,
        download_image=download,
        authorize_spend=lambda **_kwargs: None,
    )

    assert calls == {"submit": 1, "download": 1}
    assert received_urls == [
        "https://flow-content.google/image/generated-scene-media-1"
        "?secret=must-not-persist"
    ]
    assert result["quality"]["source_dimensions"] == [900, 1600]
    manifest = json.loads(config.manifest_path.read_text())
    assert manifest["generation"]["reported_dimensions"] is None
    assert manifest["generation"]["source_dimension_authority"] == "decoded_raster"
    assert manifest["start_frame"]["source_dimensions"] == [900, 1600]

    events = _events(config.receipt_path)
    response_event = events[1]
    assert response_event["phase"] == "submission_response_received"
    assert response_event["start_frame_media_id"] == "generated-scene-media-1"
    assert response_event["recovery_metadata"]["dimensions_complete"] is False
    assert response_event["recovery_metadata"]["reported_dimensions"] is None
    assert events[2]["dimension_source"] == "decoded_raster_pending"
    assert events[-1]["source_dimension_authority"] == "decoded_raster"
    assert "secret=must-not-persist" not in config.receipt_path.read_text()
    assert "secret=must-not-persist" not in config.manifest_path.read_text()


@pytest.mark.asyncio
async def test_missing_dimensions_still_fail_closed_on_decoded_landscape(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    response = _image_response()
    response["media"][0]["dimensions"] = {"width": 900}
    calls = {"submit": 0, "download": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return response

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes((1600, 900))

    with pytest.raises(SceneStartPreflightError, match="must be portrait"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=download,
            authorize_spend=lambda **_kwargs: None,
        )

    assert calls == {"submit": 1, "download": 1}
    assert config.source_destination.is_file()
    assert not config.destination.exists()
    assert [event["phase"] for event in _events(config.receipt_path)] == [
        "submission_reserved",
        "submission_response_received",
        "image_submitted",
        "validation_failed",
    ]


@pytest.mark.asyncio
async def test_download_failure_never_resubmits_and_run_id_is_burned(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    submit_calls = 0

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal submit_calls
        submit_calls += 1
        return _image_response()

    async def fail_download(_url: str) -> bytes:
        raise OSError("simulated CDN outage")

    with pytest.raises(SceneStartError, match="no retry"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=fail_download,
            authorize_spend=lambda **_kwargs: None,
        )
    assert submit_calls == 1
    assert [event["phase"] for event in _events(config.receipt_path)] == [
        "submission_reserved",
        "submission_response_received",
        "image_submitted",
        "download_failed",
    ]

    with pytest.raises(SceneStartDuplicateRunError, match="no resubmit"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=fail_download,
            authorize_spend=lambda **_kwargs: None,
        )
    assert submit_calls == 1


@pytest.mark.asyncio
async def test_non_portrait_response_metadata_stops_before_download(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    response = _image_response()
    response["media"][0]["dimensions"] = {"width": 1600, "height": 900}
    calls = {"submit": 0, "download": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return response

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes()

    with pytest.raises(SceneStartError, match="unusable metadata"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=download,
            authorize_spend=lambda **_kwargs: None,
        )

    assert calls == {"submit": 1, "download": 0}
    events = _events(config.receipt_path)
    assert [event["phase"] for event in events] == [
        "submission_reserved",
        "submission_response_received",
        "submission_response_invalid",
    ]
    assert all(
        event["character_media_ids"] == ["a007-media-in-project-1"] for event in events
    )


@pytest.mark.asyncio
async def test_invalid_response_persists_bounded_media_recovery_before_reject(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, real_run=True)
    response = _image_response()
    generated = response["media"][0]["image"]["generatedImage"]
    generated.pop("fifeUrl")
    generated["diagnostic"] = "https://should-never-be-persisted.invalid/?sig=leak"
    calls = {"submit": 0, "download": 0}

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        calls["submit"] += 1
        return response

    async def download(_url: str) -> bytes:
        calls["download"] += 1
        return _png_bytes()

    with pytest.raises(SceneStartError, match="unusable metadata"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=download,
            authorize_spend=lambda **_kwargs: None,
        )

    assert calls == {"submit": 1, "download": 0}
    events = _events(config.receipt_path)
    assert [event["phase"] for event in events] == [
        "submission_reserved",
        "submission_response_received",
        "submission_response_invalid",
    ]
    recovery = events[1]["recovery_metadata"]
    assert recovery["candidate_media_id"] == "generated-scene-media-1"
    assert recovery["download_url_present"] is False
    assert recovery["reported_dimensions"] == [900, 1600]
    receipt = config.receipt_path.read_text()
    assert "should-never-be-persisted" not in receipt
    assert "sig=leak" not in receipt


@pytest.mark.asyncio
async def test_response_dimensions_must_match_decoded_raster(tmp_path: Path) -> None:
    config = _config(tmp_path, real_run=True)
    submit_calls = 0

    async def submit(_payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal submit_calls
        submit_calls += 1
        return _image_response()

    with pytest.raises(SceneStartPreflightError, match="do not match decoded"):
        await prepare_scene_start(
            config,
            submit_image=submit,
            download_image=lambda _url: _async_value(_png_bytes((720, 1280))),
            authorize_spend=lambda **_kwargs: None,
        )

    assert submit_calls == 1
    assert config.source_destination.is_file()
    assert not config.destination.exists()
    assert [event["phase"] for event in _events(config.receipt_path)] == [
        "submission_reserved",
        "submission_response_received",
        "image_submitted",
        "validation_failed",
    ]


def test_normalization_is_cover_crop_resize_without_fill(tmp_path: Path) -> None:
    anchor = _png_bytes((1402, 1122), (88, 67, 54))
    portrait_scene = _png_bytes((1000, 1400), (171, 131, 96))

    result = normalize_and_validate_raster(
        portrait_scene,
        anchor_sha256=_sha256(anchor),
    )

    assert result.normalization == "center_cover_crop_resize"
    assert result.crop_box == (106, 0, 893, 1400)
    assert result.report()["fill_method"] is None
    with Image.open(io.BytesIO(result.png_bytes)) as normalized:
        assert normalized.size == (720, 1280)


@pytest.mark.parametrize("size", [(1600, 900), (1000, 1000)])
def test_non_portrait_source_is_rejected(size: tuple[int, int]) -> None:
    anchor = _png_bytes((1402, 1122), (88, 67, 54))

    with pytest.raises(SceneStartPreflightError, match="must be portrait"):
        normalize_and_validate_raster(
            _png_bytes(size, (171, 131, 96)),
            anchor_sha256=_sha256(anchor),
        )


def test_transparency_black_border_and_anchor_reuse_are_rejected() -> None:
    anchor = _png_bytes((720, 1280), (100, 80, 60))
    anchor_sha = _sha256(anchor)
    with pytest.raises(SceneStartPreflightError, match="equals A007"):
        normalize_and_validate_raster(anchor, anchor_sha256=anchor_sha)

    translucent = _png_bytes((720, 1280), (140, 110, 90), alpha=220)
    with pytest.raises(SceneStartPreflightError, match="transparent"):
        normalize_and_validate_raster(translucent, anchor_sha256=anchor_sha)

    bordered = Image.new("RGB", (720, 1280), (0, 0, 0))
    draw = ImageDraw.Draw(bordered)
    draw.rectangle((0, 120, 719, 1159), fill=(155, 123, 92))
    output = io.BytesIO()
    bordered.save(output, format="PNG")
    with pytest.raises(SceneStartPreflightError, match="near-black border"):
        normalize_and_validate_raster(output.getvalue(), anchor_sha256=anchor_sha)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("face_count", "cosine", "expected"),
    [
        (1, 0.600, "PASS"),
        (1, 0.599, "REJECT"),
        (1, 0.549, "HARD_FAIL"),
        (0, None, "HARD_FAIL"),
        (2, None, "REJECT"),
    ],
)
async def test_identity_gate_exact_thresholds_without_insightface_dependency(
    tmp_path: Path,
    face_count: int,
    cosine: float | None,
    expected: str,
) -> None:
    config = _config(tmp_path, real_run=True)
    await prepare_scene_start(
        config,
        submit_image=lambda _payload: _async_value(_image_response()),
        download_image=lambda _url: _async_value(_png_bytes()),
        authorize_spend=lambda **_kwargs: None,
    )
    frame_sha = _sha256(config.destination.read_bytes())
    result_path = tmp_path / "identity-result.json"

    result = record_identity_gate_result(
        manifest_path=config.manifest_path,
        receipt_path=config.receipt_path,
        result_path=result_path,
        run_id=config.run_id,
        measurement={
            "mock_mode": False,
            "verifier": "unit-real-result-recorder",
            "face_count": face_count,
            "cosine": cosine,
            "image_sha256": frame_sha,
        },
    )

    assert result["verdict"] == expected
    assert result["image_generation_count"] == 1
    assert result["video_generation_count"] == 0
    assert json.loads(result_path.read_text())["mock_mode"] is False
    assert _events(config.receipt_path)[-1]["phase"] == "identity_gate_recorded"


@pytest.mark.asyncio
async def test_identity_gate_refuses_mock_result(tmp_path: Path) -> None:
    config = _config(tmp_path, real_run=True)
    await prepare_scene_start(
        config,
        submit_image=lambda _payload: _async_value(_image_response()),
        download_image=lambda _url: _async_value(_png_bytes()),
        authorize_spend=lambda **_kwargs: None,
    )
    result_path = tmp_path / "mock-result.json"

    with pytest.raises(SceneStartPreflightError, match="mock_mode=false"):
        record_identity_gate_result(
            manifest_path=config.manifest_path,
            receipt_path=config.receipt_path,
            result_path=result_path,
            run_id=config.run_id,
            measurement={
                "mock_mode": True,
                "face_count": 1,
                "cosine": 0.99,
                "image_sha256": _sha256(config.destination.read_bytes()),
            },
        )
    assert not result_path.exists()
    assert _events(config.receipt_path)[-1]["phase"] == "raster_preflight_completed"


async def _async_value(value: Any) -> Any:
    return value
