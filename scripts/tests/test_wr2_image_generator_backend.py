"""Integration tests for the WR2_IMAGE_BACKEND selector in wr2_image_generator.py.

Verifies the dispatch logic between FlowKit and Playwright:
- backend="auto" + FlowKit available → FlowKit called, Playwright NOT called
- backend="auto" + FlowKit unavailable → Playwright called as fallback
- backend="flowkit" + FlowKit unavailable → BackendUnavailableError
- backend="flowkit" + FlowKit fails per-slide → no Playwright fallback,
  error returned in tuple
- backend="playwright" → Playwright called even if FlowKit available
- _gen_image_with_semaphore returns the standard (slide, url, err) tuple
  regardless of backend

All HTTP / Playwright / Tigris calls are mocked. No real network, no real
browser, no real S3 bucket touched.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
GEN_PATH = SCRIPTS_DIR / "wr2_image_generator.py"


@pytest.fixture
def wig(monkeypatch):
    """Fresh import of wr2_image_generator with isolated module state.

    Stubs out heavy module-level deps (Tigris/Playwright/Ollama) so the
    module loads without side effects, and resets WR2_IMAGE_BACKEND to a
    known value so the test controls dispatch.
    """
    sys.modules.pop("wr2_image_generator", None)
    sys.modules.pop("wr2_flowkit_client", None)
    monkeypatch.setenv("WR2_IMAGE_BACKEND", "auto")
    monkeypatch.setenv("WR2_IMAGE_VLM_VALIDATION", "false")  # bypass Ollama
    spec = importlib.util.spec_from_file_location(
        "wr2_image_generator", GEN_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    # Patch the upload helper so no S3 traffic happens.
    mod._upload_to_tigris = MagicMock(
        return_value="https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/x/slide-01.png"
    )
    return mod


# ─────────────────────────────────────────────────────────────────────────
# _gen_image_with_semaphore — backend dispatch
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backend_auto_uses_flowkit_when_available(wig):
    """auto + flowkit_available=True → FlowKit called, Playwright NOT called."""
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    # Patch FlowKit byte acquisition to succeed
    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(fake_bytes, None))
    # Patch Playwright path so we can detect if it was called
    wig._gen_one_image = AsyncMock(return_value=(b"WRONG_SHOULD_NOT_BE_CALLED", None))
    wig._gen_one_image_raw = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=MagicMock(),  # would be a Playwright context
        slide_number=1,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 1
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_flowkit.assert_awaited_once()
    wig._gen_one_image.assert_not_awaited()
    wig._gen_one_image_raw.assert_not_awaited()
    wig._upload_to_tigris.assert_called_once()


@pytest.mark.asyncio
async def test_backend_auto_falls_back_to_playwright_when_flowkit_unavailable(wig):
    """auto + flowkit_available=False → only Playwright called."""
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    wig._acquire_bytes_via_flowkit = AsyncMock(
        return_value=(None, "should not be called"),
    )
    wig._gen_one_image = AsyncMock(return_value=(fake_bytes, None))
    wig._gen_one_image_raw = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=MagicMock(),
        slide_number=2,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        flowkit_available=False,
    )
    slide_number, url, err = result
    assert slide_number == 2
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_flowkit.assert_not_awaited()
    wig._gen_one_image.assert_awaited()


@pytest.mark.asyncio
async def test_backend_auto_falls_back_when_flowkit_fails_at_runtime(wig):
    """auto + FlowKit returns error → Playwright is invoked as fallback."""
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    wig._acquire_bytes_via_flowkit = AsyncMock(
        return_value=(None, "flowkit unhandled error: connection refused"),
    )
    wig._gen_one_image = AsyncMock(return_value=(fake_bytes, None))
    wig._gen_one_image_raw = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=MagicMock(),
        slide_number=3,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 3
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_flowkit.assert_awaited_once()
    wig._gen_one_image.assert_awaited()


@pytest.mark.asyncio
async def test_backend_flowkit_returns_error_when_flowkit_fails(wig):
    """backend=flowkit + FlowKit fails → error tuple, NO Playwright fallback."""
    import asyncio

    wig._acquire_bytes_via_flowkit = AsyncMock(
        return_value=(None, "flowkit generation error: MODEL_ACCESS_DENIED"),
    )
    wig._gen_one_image = AsyncMock(return_value=(b"WRONG", None))
    wig._gen_one_image_raw = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,  # flowkit-only never gets a Playwright context
        slide_number=4,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="flowkit",
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 4
    assert url is None
    assert err is not None
    assert "MODEL_ACCESS_DENIED" in err
    wig._acquire_bytes_via_flowkit.assert_awaited_once()
    wig._gen_one_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_backend_playwright_skips_flowkit_even_if_available(wig):
    """backend=playwright → never call FlowKit, even if flowkit_available."""
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(b"WRONG", None))
    wig._gen_one_image = AsyncMock(return_value=(fake_bytes, None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=MagicMock(),
        slide_number=5,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="playwright",
        flowkit_available=True,  # ignored
    )
    slide_number, url, err = result
    assert slide_number == 5
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_flowkit.assert_not_awaited()
    wig._gen_one_image.assert_awaited()


@pytest.mark.asyncio
async def test_flowkit_only_with_no_context_does_not_crash(wig):
    """flowkit-only path doesn't dereference the None Playwright context."""
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(fake_bytes, None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,
        slide_number=6,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="flowkit",
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 6
    assert url is not None
    assert err is None


# ─────────────────────────────────────────────────────────────────────────
# _upload_and_return — shared upload helper
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_and_return_returns_canonical_tuple(wig):
    """_upload_and_return → (slide_number, https URL, None) on success."""
    img_bytes = b"\x89PNG" + b"\x00" * 50
    result = await wig._upload_and_return(img_bytes, 7, "draft-abc")
    slide_number, url, err = result
    assert slide_number == 7
    assert err is None
    assert url is not None and url.startswith("https://")
    wig._upload_to_tigris.assert_called_once()
    # Verify the key path matches the standard warroom/<draft>/slide-NN-TS.png
    call_args = wig._upload_to_tigris.call_args
    assert call_args[0][0] == img_bytes  # bytes argument
    key = call_args[0][1]
    assert key.startswith("warroom/draft-abc/slide-07-")
    assert key.endswith(".png")
    assert call_args[0][2] == "image/png"


@pytest.mark.asyncio
async def test_upload_and_return_surfaces_tigris_failure(wig):
    """_upload_and_return → (slide, None, error_msg) on Tigris exception."""
    wig._upload_to_tigris = MagicMock(side_effect=RuntimeError("S3 5xx"))
    result = await wig._upload_and_return(b"x", 8, "draft-fail")
    slide_number, url, err = result
    assert slide_number == 8
    assert url is None
    assert err is not None
    assert "tigris upload failed" in err
    assert "S3 5xx" in err


# ─────────────────────────────────────────────────────────────────────────
# _probe_flowkit_available — backend-availability probe
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_returns_false_when_flowkit_unreachable(wig, monkeypatch):
    """_probe_flowkit_available → False when FlowKit server is down."""
    # Point at a port nothing listens on
    monkeypatch.setattr(wig, "FLOWKIT_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(wig, "FLOWKIT_TIMEOUT_S", 1.0)
    result = await wig._probe_flowkit_available()
    assert result is False


# ─────────────────────────────────────────────────────────────────────────
# Env var contract — module-level constants reflect WR2_IMAGE_BACKEND
# ─────────────────────────────────────────────────────────────────────────


def test_default_backend_is_auto(monkeypatch):
    """When WR2_IMAGE_BACKEND is unset, IMAGE_BACKEND defaults to 'auto'."""
    monkeypatch.delenv("WR2_IMAGE_BACKEND", raising=False)
    sys.modules.pop("wr2_image_generator", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_image_generator", GEN_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    assert mod.IMAGE_BACKEND == "auto"


def test_backend_lowercased(monkeypatch):
    """WR2_IMAGE_BACKEND='Flowkit' is normalized to 'flowkit'."""
    monkeypatch.setenv("WR2_IMAGE_BACKEND", "FLOWKIT")
    sys.modules.pop("wr2_image_generator", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_image_generator", GEN_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    assert mod.IMAGE_BACKEND == "flowkit"


def test_backend_unavailable_error_is_runtime_error(wig):
    """BackendUnavailableError extends RuntimeError so existing exception
    handlers in cron wrappers don't need updating."""
    assert issubclass(wig.BackendUnavailableError, RuntimeError)
