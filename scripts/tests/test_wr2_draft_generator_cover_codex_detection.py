"""Tests for the cover-image Codex-PNG detector in wr2_draft_generator.py (B14, 2026-07-14).

B5 sibling call-site (superscar family #3, guard-over/under-match class):
`_generate_cover_via_codex()` used to run its OWN duplicate `ig_*.png`-only
glob to find Codex's freshly-written output — a hand-copy of the exact
detector `wr2_image_generator._select_fresh_codex_png` was built to replace
in PR #2443. Codex's `$imagegen` filename convention has drifted at least
twice since (`ig_*.png` -> `call_*.png` -> `exec-*.png`); the duplicate glob
here never saw any of the newer names, so every genuinely-successful Codex
cover render silently fell through to the slower/lower-fidelity Playwright/
Nano-Banana fallback. Live proof: draft 8c8d85fa, 2026-07-14 23:00, a fresh
2.4MB `exec-*.png` cover went undetected by this exact code path.

Cure: `_generate_cover_via_codex` now lazy-imports and calls the canonical
`wr2_image_generator._select_fresh_codex_png` instead of re-diverging a
second copy (DRY — kill the duplication, kill the class: a future rename
only needs fixing once). These tests prove (a) the cover path detects every
naming convention including an invented 4th prefix, (b) it does NOT treat a
stale pre-existing PNG as fresh, and (c) it genuinely delegates to the
shared helper (not a re-implementation that happens to look similar).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def wdg(monkeypatch):
    """Fresh import of wr2_draft_generator with isolated module state.

    Mirrors the `wig` fixture pattern in test_wr2_image_generator_codex_detection.py,
    adapted for wr2_draft_generator's `import wr2_draft_generator` style (used
    directly by test_wr2_draft_generator_closer_guard.py etc. — plain sys.path
    insert + import, no importlib.util spec loader needed here since this
    module has no heavy import-time side effects beyond stdlib + asyncpg).
    """
    sys.modules.pop("wr2_draft_generator", None)
    sys.modules.pop("wr2_image_generator", None)
    sys.path.insert(0, str(SCRIPTS_DIR))
    import wr2_draft_generator as mod
    return mod


def _touch(path: Path, mtime: float, content: bytes = b"\x89PNG fake") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.utime(path, (mtime, mtime))
    return path


def _fake_proc(returncode: int = 0):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"ok", b""))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ─────────────────────────────────────────────────────────────────────────
# GUILT — every Codex filename convention (incl. a not-yet-observed one)
# must be detected as the fresh cover, exactly like the B5 fix's own corpus.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "ig_0411bf5ebfe8a01c016a51eb7974bc8191acaad17d51377fff.png",  # legacy
        "call_eJfQUh5tTZdRW0fEdZFM8LJx.png",  # observed 2026-07-12
        "exec-4e5c122a-9913-401c-a833-b5a920265d11.png",  # observed 2026-07-14 (live outage proof)
        "zzz_totally_invented_future_prefix.png",  # naming drift #4 — not yet observed anywhere
    ],
)
async def test_cover_detects_fresh_png_regardless_of_filename(wdg, tmp_path, monkeypatch, filename):
    monkeypatch.setattr(wdg, "CODEX_OUTPUT_DIR", tmp_path)

    async def _fake_create_subprocess_exec(*args, **kwargs):
        # Simulate Codex writing its output DURING the subprocess call.
        _touch(tmp_path / "019f-session" / filename, mtime=time.time() + 1)
        return _fake_proc(returncode=0)

    monkeypatch.setattr(wdg.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    img_bytes, err = await wdg._generate_cover_via_codex("a scene description")

    assert err is None, f"expected detection, got error: {err}"
    assert img_bytes == b"\x89PNG fake"


# ─────────────────────────────────────────────────────────────────────────
# INNOCENCE — a stale pre-existing PNG must never be mistaken for a fresh
# cover when Codex genuinely produces nothing new this run.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cover_does_not_treat_stale_preexisting_png_as_fresh(wdg, tmp_path, monkeypatch):
    monkeypatch.setattr(wdg, "CODEX_OUTPUT_DIR", tmp_path)
    # A PNG from a much older, unrelated run — well past the mtime window.
    _touch(tmp_path / "019f-old" / "ig_ancient.png", mtime=time.time() - 10_000)

    async def _fake_create_subprocess_exec(*args, **kwargs):
        # Codex "succeeds" (exit 0) but writes nothing new — e.g. a no-op run.
        return _fake_proc(returncode=0)

    monkeypatch.setattr(wdg.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    img_bytes, err = await wdg._generate_cover_via_codex("a scene description")

    assert img_bytes is None
    assert err is not None
    assert "older than" in err
    assert "name-agnostic" in err  # proves the shared detector's message, not a re-implementation


# ─────────────────────────────────────────────────────────────────────────
# DELEGATION — the cover path must call the canonical shared detector, not
# a look-alike re-implementation (the exact failure mode this fix removes).
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cover_path_delegates_to_shared_image_generator_detector(wdg, tmp_path, monkeypatch):
    monkeypatch.setattr(wdg, "CODEX_OUTPUT_DIR", tmp_path)

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _fake_proc(returncode=0)

    monkeypatch.setattr(wdg.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    sys.path.insert(0, str(SCRIPTS_DIR))
    import wr2_image_generator as wig

    fake_png = _touch(tmp_path / "session" / "call_x.png", mtime=time.time() + 1)
    sentinel = MagicMock(return_value=(fake_png, None))
    monkeypatch.setattr(wig, "_select_fresh_codex_png", sentinel)

    img_bytes, err = await wdg._generate_cover_via_codex("a scene description")

    assert err is None
    assert img_bytes == b"\x89PNG fake"
    sentinel.assert_called_once()
    # Positional/keyword args: (output_dir, pre_existing, start_ts, mtime_window_sec=..., slide_number=...)
    call_args, call_kwargs = sentinel.call_args
    assert call_args[0] == tmp_path
    assert call_kwargs.get("slide_number") == "cover"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
