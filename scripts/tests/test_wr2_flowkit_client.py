"""Unit tests for scripts/wr2_flowkit_client.py.

Covers the public surface of FlowKitClient with httpx.MockTransport so no
real network calls happen. Tests:

- health() returns dict when extension_connected=True, None otherwise
- get_credits() returns dict on 200, None on NO_FLOW_KEY (401 or detail)
- is_available() composes health + credits results
- ensure_project() POSTs once and caches the project_id
- generate_image() parses the empirical FlowKit response shape
- generate_image() raises FlowKitGenerationError on 5xx / detail-error / malformed
- download_image() writes bytes to disk; raises on non-2xx / zero bytes
- _parse_image_response() handles missing fields cleanly

All HTTP traffic is intercepted via httpx.MockTransport — zero real I/O.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

# Load the client module from scripts/ (it is not on PYTHONPATH).
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
CLIENT_PATH = SCRIPTS_DIR / "wr2_flowkit_client.py"


@pytest.fixture
def fk_module():
    """Fresh import of wr2_flowkit_client with clean module-level state."""
    sys.modules.pop("wr2_flowkit_client", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_flowkit_client", CLIENT_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_flowkit_client"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_transport(handler):
    return httpx.MockTransport(handler)


# ─────────────────────────────────────────────────────────────────────────
# health()
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_dict_when_connected(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "version": "0.2.0",
                "extension_connected": True,
                "ws": {},
            },
        )

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.health()
    assert result is not None
    assert result["extension_connected"] is True
    assert result["version"] == "0.2.0"


@pytest.mark.asyncio
async def test_health_returns_none_when_extension_disconnected(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "ok", "extension_connected": False},
        )

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.health()
    assert result is None


@pytest.mark.asyncio
async def test_health_returns_none_on_connection_error(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.health()
    assert result is None


@pytest.mark.asyncio
async def test_health_returns_none_on_5xx(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.health()
    assert result is None


# ─────────────────────────────────────────────────────────────────────────
# get_credits()
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_credits_returns_dict_on_200(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/flow/credits"
        return httpx.Response(
            200,
            json={
                "credits": 26635,
                "userPaygateTier": "PAYGATE_TIER_TWO",
                "sku": "G1_TIER2",
                "topUpCredits": 2500,
                "subscriptionCredits": 24135,
            },
        )

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.get_credits()
    assert result is not None
    assert result["credits"] == 26635
    assert result["userPaygateTier"] == "PAYGATE_TIER_TWO"


@pytest.mark.asyncio
async def test_get_credits_returns_none_on_401_no_flow_key(fk_module):
    """FlowKit returns 401 when extension hasn't yet captured the token."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "NO_FLOW_KEY"})

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.get_credits()
    assert result is None


@pytest.mark.asyncio
async def test_get_credits_returns_none_on_200_with_detail_envelope(fk_module):
    """Some FlowKit builds wrap NO_FLOW_KEY as 200 + detail field."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"detail": "NO_FLOW_KEY"})

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.get_credits()
    assert result is None


# ─────────────────────────────────────────────────────────────────────────
# is_available()
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_available_true_when_health_and_credits_ok(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"extension_connected": True})
        if request.url.path == "/api/flow/credits":
            return httpx.Response(
                200,
                json={"credits": 26635, "userPaygateTier": "PAYGATE_TIER_TWO"},
            )
        return httpx.Response(404)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        assert await fk.is_available() is True


@pytest.mark.asyncio
async def test_is_available_false_when_no_flow_key(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"extension_connected": True})
        if request.url.path == "/api/flow/credits":
            return httpx.Response(401, json={"detail": "NO_FLOW_KEY"})
        return httpx.Response(404)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        assert await fk.is_available() is False


@pytest.mark.asyncio
async def test_is_available_false_when_extension_disconnected(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"extension_connected": False})
        return httpx.Response(404)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        assert await fk.is_available() is False


# ─────────────────────────────────────────────────────────────────────────
# ensure_project()
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_project_creates_and_caches(fk_module):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/projects":
            call_count["n"] += 1
            return httpx.Response(
                201,
                json={"id": "proj-uuid-abc", "name": "test-project"},
            )
        return httpx.Response(404)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        pid1 = await fk.ensure_project("test-project")
        pid2 = await fk.ensure_project("test-project")
    assert pid1 == "proj-uuid-abc"
    assert pid2 == "proj-uuid-abc"
    # Cache should mean only ONE POST.
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_ensure_project_raises_on_500(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitProjectError):
            await fk.ensure_project("test")


# ─────────────────────────────────────────────────────────────────────────
# generate_image()
# ─────────────────────────────────────────────────────────────────────────


_HAPPY_RESPONSE = {
    "media": [
        {
            "name": "media-uuid",
            "workflowId": "workflow-uuid",
            "image": {
                "generatedImage": {
                    "seed": 784277,
                    "mediaGenerationId": "CAMS...",
                    "mediaId": "644aeb34-1ac2-4509-90c8-652fcb8bfead",
                    "modelNameType": "GEM_PIX_2",
                    "fifeUrl": "https://flow-content.google/image/x?Expires=1&Signature=s",
                    "aspectRatio": "IMAGE_ASPECT_RATIO_PORTRAIT",
                }
            },
            "dimensions": {"width": 768, "height": 1376},
        }
    ],
    "workflows": [],
}


@pytest.mark.asyncio
async def test_generate_image_happy_path(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/flow/generate-image"
        return httpx.Response(200, json=_HAPPY_RESPONSE)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        result = await fk.generate_image(
            project_id="proj-1",
            prompt="Editorial photograph of a Bali Zero KITAS",
            orientation="PORTRAIT",
        )
    assert result["media_id"] == "644aeb34-1ac2-4509-90c8-652fcb8bfead"
    assert result["fife_url"].startswith("https://flow-content.google/")
    assert result["model"] == "GEM_PIX_2"
    assert result["width"] == 768
    assert result["height"] == 1376
    assert result["seed"] == 784277


@pytest.mark.asyncio
async def test_generate_image_raises_on_5xx(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitGenerationError):
            await fk.generate_image(project_id="p", prompt="x")


@pytest.mark.asyncio
async def test_generate_image_raises_on_detail_envelope(fk_module):
    """FlowKit sometimes returns 200 + {"detail": "..."} for errors."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"detail": "MODEL_ACCESS_DENIED"},
        )

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitGenerationError):
            await fk.generate_image(project_id="p", prompt="x")


@pytest.mark.asyncio
async def test_generate_image_raises_on_missing_media_id(fk_module):
    def handler(request: httpx.Request) -> httpx.Response:
        bad = {
            "media": [
                {"image": {"generatedImage": {"fifeUrl": "https://x"}}}
            ]
        }
        return httpx.Response(200, json=bad)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitGenerationError):
            await fk.generate_image(project_id="p", prompt="x")


# ─────────────────────────────────────────────────────────────────────────
# download_image()
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_image_writes_bytes_to_disk(fk_module, tmp_path):
    expected = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024  # PNG header + payload

    def handler(request: httpx.Request) -> httpx.Response:
        assert "flow-content" in str(request.url)
        return httpx.Response(200, content=expected)

    dest = tmp_path / "out" / "image.png"
    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        path = await fk.download_image(
            "https://flow-content.google/image/x?Expires=1&Signature=s",
            dest,
        )
    assert path == dest
    assert dest.exists()
    assert dest.read_bytes() == expected


@pytest.mark.asyncio
async def test_download_image_raises_on_404(fk_module, tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitDownloadError):
            await fk.download_image(
                "https://flow-content.google/image/x",
                tmp_path / "x.png",
            )


@pytest.mark.asyncio
async def test_download_image_raises_on_zero_bytes(fk_module, tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    async with fk_module.FlowKitClient(transport=_make_transport(handler)) as fk:
        with pytest.raises(fk_module.FlowKitDownloadError):
            await fk.download_image(
                "https://flow-content.google/image/x",
                tmp_path / "x.png",
            )


# ─────────────────────────────────────────────────────────────────────────
# _parse_image_response — direct unit tests
# ─────────────────────────────────────────────────────────────────────────


def test_parse_image_response_happy(fk_module):
    out = fk_module._parse_image_response(_HAPPY_RESPONSE)
    assert out["media_id"] == "644aeb34-1ac2-4509-90c8-652fcb8bfead"
    assert out["model"] == "GEM_PIX_2"


def test_parse_image_response_raises_on_empty_media(fk_module):
    with pytest.raises(fk_module.FlowKitGenerationError):
        fk_module._parse_image_response({"media": []})


def test_parse_image_response_raises_on_non_dict(fk_module):
    with pytest.raises(fk_module.FlowKitGenerationError):
        fk_module._parse_image_response("not a dict")


def test_parse_image_response_raises_on_detail_envelope(fk_module):
    with pytest.raises(fk_module.FlowKitGenerationError):
        fk_module._parse_image_response({"detail": "MODEL_ACCESS_DENIED"})


# ─────────────────────────────────────────────────────────────────────────
# Context manager guard
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_methods_raise_outside_context_manager(fk_module):
    fk = fk_module.FlowKitClient()
    with pytest.raises(fk_module.FlowKitError):
        await fk.health()
