"""Tests for the name-agnostic Codex output-PNG detector (B5, 2026-07-14).

Root cause of the "0/5 images" WR2 outage (research/operations/2026-07-14-
wr2-deep-audit.md §4): `wr2_image_generator.py` globbed
`~/.codex/generated_images/**/ig_*.png` to detect a fresh Codex render.
Codex's `$imagegen` skill silently changed its output filename convention
(`ig_*.png` -> `call_*.png`, later `exec-*.png` observed live) — the glob
then matched nothing NEW ever again, and every run fell through to the
"latest existing PNG" staleness check against a file frozen days in the
past. Every "failed" session directory checked during the live diagnosis
(2026-07-14) actually contained a correctly-generated PNG under the
drifted name — Codex succeeded on 100% of the sampled attempts; only the
detector was blind.

`_select_fresh_codex_png` is the extracted, pure, filename-agnostic
replacement — these tests drive it directly against a tmp_path tree, no
Codex subprocess, no network, no DB.

Guilt+innocence matrix (mandated by the fix's own doctrine — cicatrix
scar family #3, guard-over/under-match): a detector that only recognizes
today's naming is exactly the bug being fixed, so the tests must prove
the NEXT unannounced rename (a fourth, invented prefix) is caught too.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
GEN_PATH = SCRIPTS_DIR / "wr2_image_generator.py"


@pytest.fixture
def wig(monkeypatch):
    """Fresh import of wr2_image_generator with isolated module state.

    Same loader pattern as test_wr2_image_generator_backend.py's `wig`
    fixture — kept independent here (not shared via conftest) so this file
    stays self-contained and matches the existing per-file fixture style.
    """
    sys.modules.pop("wr2_image_generator", None)
    sys.modules.pop("wr2_flowkit_client", None)
    monkeypatch.setenv("WR2_IMAGE_BACKEND", "auto")
    monkeypatch.setenv("WR2_IMAGE_VLM_VALIDATION", "false")  # bypass Ollama
    spec = importlib.util.spec_from_file_location("wr2_image_generator", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    return mod


def _touch(path: Path, mtime: float, content: bytes = b"\x89PNG fake") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    import os as _os
    _os.utime(path, (mtime, mtime))
    return path


# ─────────────────────────────────────────────────────────────────────────
# GUILT — every naming convention Codex has actually used (or could use
# next) must be detected when it's genuinely fresh.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename",
    [
        "ig_0411bf5ebfe8a01c016a51eb7974bc8191acaad17d51377fff.png",  # legacy (pre-2026-07-11)
        "call_eJfQUh5tTZdRW0fEdZFM8LJx.png",  # observed 2026-07-12 onward
        "exec-4e5c122a-9913-401c-a833-b5a920265d11.png",  # observed 2026-07-14 (exec-fallback)
        "xyz_totally_invented_future_prefix.png",  # naming drift #4 — not yet observed anywhere
    ],
)
def test_detects_fresh_png_regardless_of_filename(wig, tmp_path, filename):
    session_dir = tmp_path / "019f5d5a-fake-session"
    start_ts = time.time()
    fresh = _touch(session_dir / filename, mtime=start_ts + 1)

    chosen, err = wig._select_fresh_codex_png(tmp_path, set(), start_ts, slide_number=1)

    assert err is None, f"expected detection, got error: {err}"
    assert chosen == fresh


def test_detects_fresh_png_when_written_to_new_uuid_subdir_not_seen_before(wig, tmp_path):
    """Mirrors the real layout: Codex creates a brand-new per-invocation
    UUID directory, so `pre_existing` (snapshotted before the run) never
    contains it — the file counts as fresh purely by "not in pre_existing",
    independent of the mtime check."""
    old_session = tmp_path / "019f0000-old-session"
    old_png = _touch(old_session / "ig_old.png", mtime=time.time() - 100000)
    pre_existing = {old_png}

    new_session = tmp_path / "019f9999-new-session"
    start_ts = time.time()
    fresh = _touch(new_session / "call_brandnew.png", mtime=start_ts - 5)  # mtime even PRE-dates start_ts slightly (clock skew tolerance) but path is new

    chosen, err = wig._select_fresh_codex_png(tmp_path, pre_existing, start_ts, slide_number=2)

    assert err is None
    assert chosen == fresh


# ─────────────────────────────────────────────────────────────────────────
# INNOCENCE — pre-existing files must never be mistaken for a fresh result.
# ─────────────────────────────────────────────────────────────────────────


def test_pre_existing_file_not_selected_when_a_genuinely_new_one_exists(wig, tmp_path):
    """The exact shape of the real bug in reverse: an old PNG sits in the
    tree (frozen days ago, per the live 2026-07-11 `ig_*.png` freeze) AND a
    genuinely new one lands during this call — the new one must win, never
    the stale one, no matter what either is named."""
    stale = _touch(
        tmp_path / "019f0000-old" / "ig_ancient.png",
        mtime=time.time() - 3 * 24 * 3600,  # 3 days old
    )
    pre_existing = {stale}

    start_ts = time.time()
    fresh = _touch(tmp_path / "019f9999-new" / "call_fresh.png", mtime=start_ts + 2)

    chosen, err = wig._select_fresh_codex_png(tmp_path, pre_existing, start_ts, slide_number=3)

    assert err is None
    assert chosen == fresh
    assert chosen != stale


def test_only_stale_pre_existing_png_and_none_fresh_reports_error(wig, tmp_path):
    """INNOCENCE mirror of the outage itself: if Codex genuinely produced
    nothing new this run, the ONLY png in the tree is the old one, older
    than the mtime window — this must still fail loudly (the fix does not
    paper over real Codex failures, only the false ones)."""
    old_mtime = time.time() - 10000  # well past CODEX_MTIME_WINDOW_SEC (600s)
    stale = _touch(tmp_path / "019f0000-old" / "ig_ancient.png", mtime=old_mtime)
    pre_existing = {stale}
    start_ts = time.time()

    chosen, err = wig._select_fresh_codex_png(
        tmp_path, pre_existing, start_ts, mtime_window_sec=600, slide_number=4,
    )

    assert chosen is None
    assert err is not None
    assert "older than" in err
    assert "name-agnostic" in err  # signals which detector generation produced this


def test_no_png_anywhere_reports_error(wig, tmp_path):
    chosen, err = wig._select_fresh_codex_png(tmp_path, set(), time.time(), slide_number=5)
    assert chosen is None
    assert err == "no PNG found in codex output dir"


def test_missing_output_dir_reports_error(wig, tmp_path):
    missing = tmp_path / "does-not-exist"
    chosen, err = wig._select_fresh_codex_png(missing, set(), time.time(), slide_number=6)
    assert chosen is None
    assert err == "codex output dir does not exist after run"


def test_multiple_fresh_candidates_picks_the_latest(wig, tmp_path):
    """If more than one PNG looks fresh (e.g. a slow-clock race with another
    concurrent Codex session sharing the same machine-wide output dir), the
    most-recently-written one wins — a defensible tiebreak, not a crash."""
    start_ts = time.time()
    older_fresh = _touch(tmp_path / "s1" / "call_a.png", mtime=start_ts + 1)
    newer_fresh = _touch(tmp_path / "s2" / "call_b.png", mtime=start_ts + 5)

    chosen, err = wig._select_fresh_codex_png(tmp_path, set(), start_ts, slide_number=7)

    assert err is None
    assert chosen == newer_fresh
    assert chosen != older_fresh


# ─────────────────────────────────────────────────────────────────────────
# Bounded retry + backoff — _acquire_bytes_via_codex wraps the single-shot
# helper with a small, configurable retry loop.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_codex_retries_on_transient_failure_then_succeeds(wig, monkeypatch):
    monkeypatch.setattr(wig, "CODEX_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(wig, "CODEX_RETRY_BACKOFF_SEC", 0)  # no real sleep in tests
    sleep_calls = []

    async def _fake_sleep(sec):
        sleep_calls.append(sec)

    monkeypatch.setattr(wig.asyncio, "sleep", _fake_sleep)

    fake_bytes = b"\x89PNG" + b"\x00" * 50
    wig._acquire_bytes_via_codex_once = AsyncMock(
        side_effect=[(None, "transient codex hiccup"), (fake_bytes, None)],
    )

    img_bytes, err = await wig._acquire_bytes_via_codex(1, "a prompt", "draft-1")

    assert img_bytes == fake_bytes
    assert err is None
    assert wig._acquire_bytes_via_codex_once.await_count == 2
    assert sleep_calls == [0]  # backed off exactly once, between the two attempts


@pytest.mark.asyncio
async def test_codex_gives_up_after_max_attempts(wig, monkeypatch):
    monkeypatch.setattr(wig, "CODEX_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(wig, "CODEX_RETRY_BACKOFF_SEC", 0)
    monkeypatch.setattr(wig.asyncio, "sleep", AsyncMock())

    wig._acquire_bytes_via_codex_once = AsyncMock(
        return_value=(None, "persistent failure"),
    )

    img_bytes, err = await wig._acquire_bytes_via_codex(1, "a prompt", "draft-1")

    assert img_bytes is None
    assert err == "persistent failure"
    assert wig._acquire_bytes_via_codex_once.await_count == 2


@pytest.mark.asyncio
async def test_codex_succeeds_first_try_no_retry_no_sleep(wig, monkeypatch):
    """Regression guard: the common case (Codex works, as it does 100% of
    the time per the 2026-07-14 diagnosis) must not pay a retry/backoff
    tax it doesn't need."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(wig.asyncio, "sleep", sleep_mock)

    fake_bytes = b"\x89PNG" + b"\x00" * 50
    wig._acquire_bytes_via_codex_once = AsyncMock(return_value=(fake_bytes, None))

    img_bytes, err = await wig._acquire_bytes_via_codex(1, "a prompt", "draft-1")

    assert img_bytes == fake_bytes
    assert err is None
    assert wig._acquire_bytes_via_codex_once.await_count == 1
    sleep_mock.assert_not_awaited()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
