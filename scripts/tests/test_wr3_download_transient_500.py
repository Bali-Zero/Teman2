"""Download-poll transient-error handling tests (2026-05-30 C5a render unblock).

Root cause empirically reproduced 2026-05-30 01:17-01:18: Google Flow `/v1/media/<id>`
returns `{"detail":{"error":{"code":500,"status":"INTERNAL"}}}` for the FIRST few
seconds after generate-video, while the media is still being materialized, THEN
returns `{"name","video":{"encodedVideo": <mp4 base64>}}` once ready (~43s later).

The pre-fix `_download_video_media` raised FlowkitError on any `code != 404`, so it
killed the job at poll #0 on the transient 500 instead of waiting. All 18 C5a shots
failed this way. These tests pin the contract: 500/INTERNAL (and 503) during the poll
window are PENDING, not fatal — only sleep+retry; a real terminal error still fails.
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REAL_SLEEP = asyncio.sleep  # captured before any patch to avoid recursion


async def _no_sleep(*_a, **_k):
    # yield control once without an actual delay (no recursion into patched sleep)
    await _REAL_SLEEP(0)


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_flowkit_client import (  # noqa: E402
    EpisodeContext,
    FlowkitError,
    FlowkitTimeoutError,
    _download_video_media,
)


def _ready_payload() -> dict:
    # Minimal valid MP4: 'ftyp' box at offset 4.
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
    return {"name": "video-media-ccc", "video": {"encodedVideo": base64.b64encode(mp4).decode()}}


def _err(code, status="INTERNAL") -> dict:
    return {"detail": {"error": {"code": code, "message": "Internal error encountered.", "status": status}}}


@pytest.fixture
def ctx():
    return EpisodeContext(
        project_id="p", video_id="v", project_name="t",
        endpoint="http://127.0.0.1:8100", paygate="PAYGATE_TIER_TIER1P5",
    )


@pytest.mark.asyncio
async def test_transient_500_then_ready_succeeds(ctx, tmp_path):
    """500 INTERNAL on first polls, then ready → MP4 written, NO error raised."""
    responses = iter([_err(500), _err(500), _ready_payload()])

    async def fake_get(url, timeout_s):
        return next(responses)

    dest = tmp_path / "s001.mp4"
    with patch("wr3_flowkit_client._http_get_json", new=fake_get), \
         patch("wr3_flowkit_client.asyncio.sleep", new=_no_sleep):
        await _download_video_media(ctx, media_id="video-media-ccc", dest=dest,
                                    timeout_s=120, poll_interval_s=0)
    assert dest.exists()
    assert b"ftyp" in dest.read_bytes()[:32]


@pytest.mark.asyncio
async def test_transient_503_then_ready_succeeds(ctx, tmp_path):
    """503 is also transient (extension/backend hiccup) → retry then succeed."""
    responses = iter([_err(503, "UNAVAILABLE"), _ready_payload()])

    async def fake_get(url, timeout_s):
        return next(responses)

    dest = tmp_path / "s002.mp4"
    with patch("wr3_flowkit_client._http_get_json", new=fake_get), \
         patch("wr3_flowkit_client.asyncio.sleep", new=_no_sleep):
        await _download_video_media(ctx, media_id="m", dest=dest, timeout_s=120, poll_interval_s=0)
    assert dest.exists()


@pytest.mark.asyncio
async def test_terminal_400_fails_loud(ctx, tmp_path):
    """A genuine 400 INVALID_ARGUMENT is NOT transient → fail loud, no infinite retry."""
    async def fake_get(url, timeout_s):
        return _err(400, "INVALID_ARGUMENT")

    with patch("wr3_flowkit_client._http_get_json", new=fake_get), \
         patch("wr3_flowkit_client.asyncio.sleep", new=_no_sleep):
        with pytest.raises(FlowkitError, match="400|INVALID_ARGUMENT|download error"):
            await _download_video_media(ctx, media_id="m", dest=tmp_path / "x.mp4",
                                        timeout_s=120, poll_interval_s=0)


@pytest.mark.asyncio
async def test_persistent_500_eventually_times_out(ctx, tmp_path):
    """If 500 NEVER clears within the window, raise Timeout (not silent hang, not crash)."""
    async def fake_get(url, timeout_s):
        return _err(500)

    # Deterministic clock so the deadline is reached after a bounded number of polls.
    t = {"now": 0.0}

    def fake_time():
        t["now"] += 5.0
        return t["now"]

    with patch("wr3_flowkit_client._http_get_json", new=fake_get), \
         patch("wr3_flowkit_client.asyncio.sleep", new=_no_sleep), \
         patch.object(asyncio.get_event_loop(), "time", new=fake_time):
        with pytest.raises((FlowkitTimeoutError, FlowkitError)):
            await _download_video_media(ctx, media_id="m", dest=tmp_path / "y.mp4",
                                        timeout_s=30, poll_interval_s=0)
