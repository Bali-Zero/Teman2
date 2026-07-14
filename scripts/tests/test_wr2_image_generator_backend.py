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
from unittest.mock import AsyncMock, MagicMock

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
async def test_backend_auto_codex_ok_flowkit_not_called(wig):
    """auto + codex_available=True + codex succeeds → FlowKit never called.

    Codex remains primary in auto mode; the 2026-07-14 fallback fix must not
    regress the "prefer Codex" rule when Codex is healthy.
    """
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    wig._acquire_bytes_via_codex = AsyncMock(return_value=(fake_bytes, None))
    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,
        slide_number=10,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        codex_available=True,
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 10
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_codex.assert_awaited_once()
    wig._acquire_bytes_via_flowkit.assert_not_awaited()


@pytest.mark.asyncio
async def test_backend_auto_codex_fails_falls_back_to_flowkit(wig):
    """auto + Codex fails + FlowKit available → FlowKit is tried per-slide.

    Regression guard 2026-07-14: the Codex-primary call site in `_process_one`
    used to hardcode backend="codex" (never "auto") and never pass
    flowkit_available, so this fallback — even though already implemented in
    `_gen_image_with_semaphore` — was unreachable in production. Every real
    Codex failure dead-ended as image_failed while FlowKit sat idle.
    """
    import asyncio

    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    wig._acquire_bytes_via_codex = AsyncMock(
        return_value=(None, "latest PNG older than 600s window"),
    )
    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(fake_bytes, None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,
        slide_number=11,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        codex_available=True,
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 11
    assert url is not None
    assert err is None
    wig._acquire_bytes_via_codex.assert_awaited_once()
    wig._acquire_bytes_via_flowkit.assert_awaited_once()


@pytest.mark.asyncio
async def test_backend_codex_strict_never_falls_back_to_flowkit(wig):
    """backend="codex" (explicit, not "auto") + Codex fails → honest error,
    FlowKit NEVER called even if flowkit_available=True.

    An explicit WR2_IMAGE_BACKEND=codex request must stay codex-only — the
    2026-07-14 fallback fix only widens the "auto" per-slide backend, it must
    not silently cascade a strict operator choice.
    """
    import asyncio

    wig._acquire_bytes_via_codex = AsyncMock(
        return_value=(None, "codex exit=1: some codex error"),
    )
    wig._acquire_bytes_via_flowkit = AsyncMock(return_value=(b"WRONG", None))

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,
        slide_number=12,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="codex",
        codex_available=True,
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 12
    assert url is None
    assert err is not None
    assert "codex" in err
    wig._acquire_bytes_via_codex.assert_awaited_once()
    wig._acquire_bytes_via_flowkit.assert_not_awaited()


@pytest.mark.asyncio
async def test_backend_auto_codex_and_flowkit_both_fail_returns_honest_error(wig):
    """auto + Codex fails + FlowKit fails + no Playwright context → honest
    error tuple, no crash, no false success.

    Mirrors the real Codex-primary call site (`_process_one` passes
    context=None — Playwright is never launched in that path).
    """
    import asyncio

    wig._acquire_bytes_via_codex = AsyncMock(
        return_value=(None, "latest PNG older than 600s window"),
    )
    wig._acquire_bytes_via_flowkit = AsyncMock(
        return_value=(None, "flowkit unhandled error: connection refused"),
    )

    sem = asyncio.Semaphore(1)
    result = await wig._gen_image_with_semaphore(
        sem,
        context=None,
        slide_number=13,
        image_prompt="A test prompt",
        draft_id="abcd-1234",
        backend="auto",
        codex_available=True,
        flowkit_available=True,
    )
    slide_number, url, err = result
    assert slide_number == 13
    assert url is None
    assert err is not None
    wig._acquire_bytes_via_codex.assert_awaited_once()
    wig._acquire_bytes_via_flowkit.assert_awaited_once()


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
# _process_one — call-site wiring (the actual 2026-07-14 bug)
#
# The dispatch logic tested above already lived in _gen_image_with_semaphore
# before this fix; the bug was that the "Codex-primary" call site in
# _process_one hardcoded backend="codex" and never passed flowkit_available,
# making that fallback logic unreachable in production. These tests pin the
# call-site wiring itself, not just the dispatch function.
# ─────────────────────────────────────────────────────────────────────────


def _make_hero_row(draft_id):
    return {
        "id": draft_id,
        "topic": "Test topic",
        "slides_json": {
            "slides": [
                {"slide_number": 1, "is_hero_image": True, "image_prompt": "p1"},
            ]
        },
        "council_debate_json": {},
    }


@pytest.mark.asyncio
async def test_process_one_auto_mode_passes_auto_backend_and_flowkit_available(wig, monkeypatch):
    """IMAGE_BACKEND=auto + both probes True → _gen_image_with_semaphore is
    called with backend="auto" (NOT "codex") and flowkit_available=True.
    """
    import uuid

    monkeypatch.setattr(wig, "_send_telegram", MagicMock())
    wig._probe_codex_available = AsyncMock(return_value=True)
    wig._probe_flowkit_available = AsyncMock(return_value=True)
    captured_calls = []

    async def fake_gen(sem, context, slide_number, prompt, draft_id, **kwargs):
        captured_calls.append(kwargs)
        return slide_number, "https://example.test/x.png", None

    wig._gen_image_with_semaphore = fake_gen

    conn = MagicMock()
    conn.execute = AsyncMock()
    draft_id = uuid.uuid4()
    row = _make_hero_row(draft_id)

    ok = await wig._process_one(conn, row, dry_run=False)
    assert ok is True
    assert len(captured_calls) == 1
    assert captured_calls[0]["backend"] == "auto"
    assert captured_calls[0]["codex_available"] is True
    assert captured_calls[0]["flowkit_available"] is True


@pytest.mark.asyncio
async def test_process_one_explicit_codex_mode_stays_codex_only(monkeypatch):
    """WR2_IMAGE_BACKEND=codex (explicit, strict) → _gen_image_with_semaphore
    is called with backend="codex" even when FlowKit is also available —
    an explicit operator choice must never silently cascade.
    """
    import uuid

    sys.modules.pop("wr2_image_generator", None)
    sys.modules.pop("wr2_flowkit_client", None)
    monkeypatch.setenv("WR2_IMAGE_BACKEND", "codex")
    monkeypatch.setenv("WR2_IMAGE_VLM_VALIDATION", "false")
    spec = importlib.util.spec_from_file_location("wr2_image_generator", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_send_telegram", MagicMock())

    mod._probe_codex_available = AsyncMock(return_value=True)
    mod._probe_flowkit_available = AsyncMock(return_value=True)
    captured_calls = []

    async def fake_gen(sem, context, slide_number, prompt, draft_id, **kwargs):
        captured_calls.append(kwargs)
        return slide_number, "https://example.test/x.png", None

    mod._gen_image_with_semaphore = fake_gen

    conn = MagicMock()
    conn.execute = AsyncMock()
    draft_id = uuid.uuid4()
    row = _make_hero_row(draft_id)

    ok = await mod._process_one(conn, row, dry_run=False)
    assert ok is True
    assert len(captured_calls) == 1
    assert captured_calls[0]["backend"] == "codex"


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


def test_desk_pen_cliche_ban_reaches_final_image_prompt(wig):
    """The document/deed-on-a-desk-with-a-pen cliché ban (Antonello 2026-06-13)
    must be in the prompt that EVERY image backend actually receives.

    Regression guard for the wiring bug found 2026-06-13: the draft-generator's
    NEGATIVE_PROMPT/BRAND_SUFFIX ban only ever reached the LLM that writes the
    image_prompt — never the image model. The only anti-cliché text that reaches
    Gemini/gpt-image-2/FlowKit is ANTI_CLICHE_SUFFIX via _compose_final_prompt;
    the ban therefore has to live there to take effect at generation time.
    """
    final = wig._compose_final_prompt("a property transaction in Bali")
    low = final.lower()
    assert "document" in low and "desk" in low, final
    assert "fountain pen" in low or "signing pen" in low, final
    assert "notary-desk still life" in low, final
    # every tonal-palette variant carries the ban too (suffix is palette-agnostic)
    for palette in ("warm-ochre", "cool-teal", "monochrome", None):
        assert "notary-desk still life" in wig._compose_final_prompt("x", palette).lower()
