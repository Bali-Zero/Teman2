"""Tests for the WR3 zero-spend packet: placeholder clip render + spend gate.

Hermetic and offline by construction:
  - `wr3_placeholder_clip` never opens a socket — it only shells out to a
    local `ffmpeg` binary and renders with local PIL. No Flow/Veo job is
    ever submitted here.
  - `wr3_spend_authority` is stdlib-only and touches only `tmp_path`-scoped
    files via `log_path`/`WR3_SPEND_DECISION_LOG` — never the real
    `~/.cache/wr3/spend-decisions.jsonl` unless a test explicitly opts in.

Run: `python3 -m pytest scripts/tests/test_wr3_zero_spend.py -q`
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_placeholder_clip import (  # noqa: E402
    PlaceholderRenderError,
    render_placeholder_clip,
)
from wr3_spend_authority import (  # noqa: E402
    SpendDecision,
    SpendNotAuthorizedError,
    assert_spend_authorized,
    log_decision,
    parse_decision,
    zero_spend_enabled,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
FFPROBE_AVAILABLE = shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(
    not (FFMPEG_AVAILABLE and FFPROBE_AVAILABLE),
    reason="ffmpeg/ffprobe not on PATH — placeholder-clip tests are hermetic but need the local binary",
)


def _ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_entries",
            "stream=codec_name,width,height,duration,pix_fmt:format=duration",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Module 1: wr3_placeholder_clip
# ---------------------------------------------------------------------------


@requires_ffmpeg
def test_placeholder_render_produces_real_file_with_expected_geometry(tmp_path: Path) -> None:
    dest = tmp_path / "clip.mp4"
    out = render_placeholder_clip(episode_id="EP01", shot_index=1, dest=dest)

    assert out == dest
    assert dest.exists()
    assert dest.stat().st_size > 0

    probe = _ffprobe_json(dest)
    video_streams = [s for s in probe["streams"] if s.get("codec_name") is not None]
    assert len(video_streams) == 1
    stream = video_streams[0]
    assert stream["codec_name"] == "h264"
    assert stream["pix_fmt"] == "yuv420p"
    assert stream["width"] == 720
    assert stream["height"] == 1280

    duration = float(probe["format"]["duration"])
    assert abs(duration - 8.0) <= 0.3


@requires_ffmpeg
def test_placeholder_render_determinism_byte_identical(tmp_path: Path) -> None:
    """Determinism claim ACTUALLY ACHIEVED on this machine: byte-identical
    sha256, not merely frame-identical framemd5. Verified via
    `-fflags +bitexact -flags:v +bitexact`, `-map_metadata -1`, a fixed
    `-metadata:s:v:0 encoder=` tag, `-threads 1` + `sliced_threads=0`, a
    fixed frame rate/`-fps_mode cfr`, and a timestamp-free PIL PNG overlay.
    """
    import hashlib

    dest_a = tmp_path / "a.mp4"
    dest_b = tmp_path / "b.mp4"

    render_placeholder_clip(episode_id="EP01", shot_index=3, dest=dest_a)
    render_placeholder_clip(episode_id="EP01", shot_index=3, dest=dest_b)

    sha_a = hashlib.sha256(dest_a.read_bytes()).hexdigest()
    sha_b = hashlib.sha256(dest_b.read_bytes()).hexdigest()
    assert sha_a == sha_b, "identical inputs must render byte-identical output"


@requires_ffmpeg
def test_placeholder_render_different_shot_index_differs(tmp_path: Path) -> None:
    """A placeholder that looked the same for every shot would let the
    assembler silently mix shots up — the label must actually vary."""
    import hashlib

    dest_shot3 = tmp_path / "shot3.mp4"
    dest_shot4 = tmp_path / "shot4.mp4"

    render_placeholder_clip(episode_id="EP01", shot_index=3, dest=dest_shot3)
    render_placeholder_clip(episode_id="EP01", shot_index=4, dest=dest_shot4)

    sha3 = hashlib.sha256(dest_shot3.read_bytes()).hexdigest()
    sha4 = hashlib.sha256(dest_shot4.read_bytes()).hexdigest()
    assert sha3 != sha4


@requires_ffmpeg
def test_placeholder_render_different_episode_id_differs(tmp_path: Path) -> None:
    import hashlib

    dest_a = tmp_path / "epa.mp4"
    dest_b = tmp_path / "epb.mp4"

    render_placeholder_clip(episode_id="EP01", shot_index=1, dest=dest_a)
    render_placeholder_clip(episode_id="EP02", shot_index=1, dest=dest_b)

    sha_a = hashlib.sha256(dest_a.read_bytes()).hexdigest()
    sha_b = hashlib.sha256(dest_b.read_bytes()).hexdigest()
    assert sha_a != sha_b


def test_placeholder_render_missing_ffmpeg_raises_named_error(tmp_path: Path) -> None:
    dest = tmp_path / "clip.mp4"
    with pytest.raises(PlaceholderRenderError):
        render_placeholder_clip(
            episode_id="EP01",
            shot_index=1,
            dest=dest,
            ffmpeg_bin="/definitely/not/a/real/ffmpeg-binary",
        )
    # Never a silent 0-byte artifact.
    assert not dest.exists()


@requires_ffmpeg
def test_placeholder_render_ffmpeg_failure_leaves_no_partial_file(tmp_path: Path) -> None:
    dest = tmp_path / "clip.mp4"
    with pytest.raises(PlaceholderRenderError):
        render_placeholder_clip(episode_id="EP01", shot_index=1, dest=dest, duration_s=0)
    assert not dest.exists()


# ---------------------------------------------------------------------------
# Module 2: wr3_spend_authority — zero_spend_enabled
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("yes", True),
        ("YES", True),
        ("on", True),
        ("On", True),
        (" 1 ", True),
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("off", False),
        ("", False),
        ("garbage", False),
        ("2", False),
    ],
)
def test_zero_spend_enabled_truthy_falsy_matrix(monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
    monkeypatch.setenv("WR3_ZERO_SPEND", raw)
    assert zero_spend_enabled() is expected


def test_zero_spend_enabled_unset_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    assert zero_spend_enabled() is False


# ---------------------------------------------------------------------------
# Module 2: wr3_spend_authority — parse_decision
# ---------------------------------------------------------------------------


def test_parse_decision_happy_path() -> None:
    decision = parse_decision("EP01:zero@balizero.com:2026-08-23")
    assert decision == SpendDecision(
        episode_id="EP01",
        who="zero@balizero.com",
        date=date(2026, 8, 23),
        raw="EP01:zero@balizero.com:2026-08-23",
    )


def test_parse_decision_strips_surrounding_whitespace() -> None:
    decision = parse_decision("  EP01:zero:2026-08-23  ")
    assert decision.episode_id == "EP01"
    assert decision.who == "zero"
    assert decision.date == date(2026, 8, 23)


@pytest.mark.parametrize(
    "raw",
    [
        "EP01:zero",  # 2 fields
        "EP01:zero:2026-08-23:extra",  # 4 fields
        "EP01",  # 1 field
        "",  # empty
        "   ",  # blank
        "EP01:zero:2026-8-1",  # non-strict date format
        "EP01:zero:2026/08/23",  # wrong separator in date
        "EP01:zero:20260823",  # no dashes
        "EP01:zero:2026-13-40",  # invalid calendar date
        "EP 01:zero:2026-08-23",  # internal whitespace in episode_id
        "EP01: zero:2026-08-23",  # internal whitespace padding who
        "EP01:zero :2026-08-23",  # internal whitespace padding who
        "EP01:ze ro:2026-08-23",  # internal whitespace inside who
        "EP01:zero:2026- 08-23",  # internal whitespace inside date field
        ":zero:2026-08-23",  # empty episode_id
        "EP01::2026-08-23",  # empty who
        "EP01:zero:",  # empty date
        "EP#01:zero:2026-08-23",  # invalid char in episode_id
        "EP01:zero!:2026-08-23",  # invalid char in who
    ],
)
def test_parse_decision_rejects_invalid_tokens(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_decision(raw)


# ---------------------------------------------------------------------------
# Module 2: wr3_spend_authority — assert_spend_authorized
# ---------------------------------------------------------------------------


@pytest.fixture()
def decision_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Route the decision log to a tmp_path file for every test in this
    section, so no test ever touches the real ~/.cache/wr3 log."""
    log_path = tmp_path / "spend-decisions.jsonl"
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(log_path))
    return log_path


def test_assert_spend_authorized_raises_when_env_unset(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.delenv("WR3_SPEND_DECISION", raising=False)
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")
    assert not decision_log.exists()


def test_assert_spend_authorized_raises_when_env_empty(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setenv("WR3_SPEND_DECISION", "")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_two_fields(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setenv("WR3_SPEND_DECISION", "EP01:zero")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_four_fields(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero:{today}:extra")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_bad_date_format(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setenv("WR3_SPEND_DECISION", "EP01:zero:2026-8-1")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_internal_whitespace(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP 01:zero:{today}")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_wrong_episode_id(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP02:zero:{today}")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_yesterdays_date(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero:{yesterday}")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_on_tomorrows_date(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero:{tomorrow}")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")


def test_assert_spend_authorized_raises_even_with_valid_token_when_zero_spend_on(
    monkeypatch: pytest.MonkeyPatch, decision_log: Path
) -> None:
    """Zero-spend always wins over a decision token — this is a required
    safety behaviour, not an incidental ordering detail."""
    monkeypatch.setenv("WR3_ZERO_SPEND", "1")
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero@balizero.com:{today}")
    with pytest.raises(SpendNotAuthorizedError):
        assert_spend_authorized(episode_id="EP01")
    # Zero-spend refusal must not even attempt to log an "authorization"
    # that never happened.
    assert not decision_log.exists()


def test_assert_spend_authorized_happy_path_returns_decision_and_logs_once(
    monkeypatch: pytest.MonkeyPatch, decision_log: Path
) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero@balizero.com:{today}")

    decision = assert_spend_authorized(episode_id="EP01")

    assert decision.episode_id == "EP01"
    assert decision.who == "zero@balizero.com"
    assert decision.date == date.today()

    assert decision_log.exists()
    lines = decision_log.read_text(encoding="utf-8").strip("\n").split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["episode_id"] == "EP01"
    assert record["who"] == "zero@balizero.com"
    assert record["decision_date"] == today
    assert record["raw"] == f"EP01:zero@balizero.com:{today}"
    assert "ts" in record


def test_assert_spend_authorized_accepts_explicit_now_override(monkeypatch: pytest.MonkeyPatch, decision_log: Path) -> None:
    """`now=` lets a caller pin "today" for testing without touching the
    system clock — the decision token must match that pinned date."""
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    fixed_today = date(2030, 1, 1)
    monkeypatch.setenv("WR3_SPEND_DECISION", "EP01:zero:2030-01-01")

    decision = assert_spend_authorized(episode_id="EP01", now=fixed_today)
    assert decision.date == fixed_today


def test_log_path_unwritable_raises_and_does_not_return(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed contract: if the decision log can't be written, the
    call must raise SpendNotAuthorizedError — never return a decision."""
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir(mode=0o500)
    unwritable_log = readonly_dir / "spend-decisions.jsonl"

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP01:zero:{today}")
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(unwritable_log))

    try:
        with pytest.raises(SpendNotAuthorizedError):
            assert_spend_authorized(episode_id="EP01")
    finally:
        readonly_dir.chmod(0o700)  # allow tmp_path cleanup

    assert not unwritable_log.exists()


def test_log_decision_direct_unwritable_path_raises(tmp_path: Path) -> None:
    readonly_dir = tmp_path / "readonly2"
    readonly_dir.mkdir(mode=0o500)
    unwritable_log = readonly_dir / "spend-decisions.jsonl"
    decision = SpendDecision(episode_id="EP01", who="zero", date=date.today(), raw="EP01:zero:2026-01-01")
    try:
        with pytest.raises(SpendNotAuthorizedError):
            log_decision(decision, episode_id="EP01", log_path=unwritable_log)
    finally:
        readonly_dir.chmod(0o700)


def test_log_decision_sets_mode_0600(tmp_path: Path) -> None:
    log_path = tmp_path / "spend-decisions.jsonl"
    decision = SpendDecision(episode_id="EP01", who="zero", date=date.today(), raw="EP01:zero:2026-01-01")
    log_decision(decision, episode_id="EP01", log_path=log_path)
    mode = log_path.stat().st_mode & 0o777
    assert mode == 0o600


# ---------------------------------------------------------------------------
# Module 3: wr3_flowkit_client — zero-spend wiring (2026-08-23 P03 packet)
#
# The gate wiring itself: assert_spend_authorized() at the top of the two
# functions that actually POST a charging request (_generate_start_image,
# _generate_video); the zero-spend short-circuit in submit_clip/
# render_shot_pack; and the fix for the defect where a real Veo charge could
# be recorded 0x (download failed) or up to 3x (wr3_render_episode.py's
# per-shot retry) because the ledger write used to fire only after a
# successful download instead of at the actual charge.
# ---------------------------------------------------------------------------


@requires_ffmpeg
@pytest.mark.asyncio
async def test_submit_clip_zero_spend_renders_placeholder_and_opens_no_socket(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Under WR3_ZERO_SPEND, submit_clip must render a real placeholder mp4,
    report cost_credits=0, and never reach any charging/network call site —
    proven by making every one of them explode if reached."""
    monkeypatch.setenv("WR3_ZERO_SPEND", "1")

    import wr3_flowkit_client as fk

    async def _boom(*_a, **_k):
        raise AssertionError("network path reached")

    with patch.object(fk, "_create_scene", new=_boom), \
         patch.object(fk, "_generate_start_image", new=_boom), \
         patch.object(fk, "_generate_video", new=_boom), \
         patch.object(fk, "_download_video_media", new=_boom), \
         patch.object(fk, "setup_episode_context", new=_boom):
        req = fk.ClipRequest(shot_index=5, positive_prompt="a placeholder shot")
        result = await fk.submit_clip(req, episode_dir=tmp_path)

    assert result.cost_credits == 0
    expected_path = tmp_path / "clips" / "05.mp4"
    assert result.mp4_path == expected_path
    assert expected_path.exists()
    assert expected_path.stat().st_size > 0
    assert result.veo_job_id.startswith("placeholder:")


@requires_ffmpeg
@pytest.mark.asyncio
async def test_render_shot_pack_zero_spend_renders_all_placeholders_no_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """render_shot_pack under zero-spend on a 3-shot fixture: 3 placeholder
    mp4s, all cost_credits==0, setup_episode_context never called (it opens
    sockets to create the Flow project/video shell)."""
    monkeypatch.setenv("WR3_ZERO_SPEND", "1")

    import wr3_flowkit_client as fk

    async def _boom(*_a, **_k):
        raise AssertionError("network path reached")

    shot_pack = {
        "episode_id": "ep-zero-spend-pack",
        "shots": [
            {"index": 1, "positive_prompt": "shot one"},
            {"index": 2, "positive_prompt": "shot two"},
            {"index": 3, "positive_prompt": "shot three"},
        ],
    }
    sp_path = tmp_path / "shot-pack.json"
    sp_path.write_text(json.dumps(shot_pack))

    with patch.object(fk, "_create_scene", new=_boom), \
         patch.object(fk, "_generate_start_image", new=_boom), \
         patch.object(fk, "_generate_video", new=_boom), \
         patch.object(fk, "_download_video_media", new=_boom), \
         patch.object(fk, "setup_episode_context", new=_boom):
        results = await fk.render_shot_pack(sp_path, tmp_path)

    assert len(results) == 3
    for r in results:
        assert r.cost_credits == 0
        assert r.mp4_path.exists()
        assert r.mp4_path.stat().st_size > 0
    # setup_episode_context creates this on success — its absence is direct
    # evidence the boomed fake was never actually called (had it been
    # called, this test would already have failed on the AssertionError).
    assert not (tmp_path / "_flowkit_context.json").exists()


@pytest.mark.asyncio
async def test_download_failure_after_generate_video_still_records_real_spend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE regression this packet fixes. The Veo charge happens at
    _generate_video (the POST that actually costs credits), not at
    _download_video_media. Before the fix, record_spend lived in submit_clip
    AFTER a successful download — so a download failure (timeout, transient
    5xx, ...) left a real charge completely unlogged, and
    wr3_render_episode.py's up-to-3x per-shot retry could then charge the
    SAME shot multiple times while logging it zero times. This proves the
    ledger records the charge exactly once, at the moment it actually
    happens, independent of what happens to the download afterward.

    This test is written to FAIL against the pre-fix code (0 ledger rows,
    because the download exception aborts submit_clip before its old
    post-download record_spend call) and PASS against the fix (1 row,
    written inside _generate_video itself).
    """
    import wr3_flowkit_client as fk
    from wr3_credit_ledger import read_records

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    today = date.today().isoformat()
    monkeypatch.setenv("WR3_SPEND_DECISION", f"EP-regression:pytest:{today}")
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(tmp_path / "spend-decisions.jsonl"))

    ledger_path = tmp_path / "credit-ledger.jsonl"
    monkeypatch.setenv("WR3_CREDIT_LEDGER", str(ledger_path))

    ctx = fk.EpisodeContext(
        project_id="p", video_id="v", project_name="EP-regression",
        endpoint="http://127.0.0.1:8100", paygate="PAYGATE_TIER_ONE",
    )
    # start_image_media_id preset → _generate_start_image is never called,
    # isolating this test to the _generate_video charge under test.
    req = fk.ClipRequest(
        shot_index=7, positive_prompt="regression shot",
        start_image_media_id="preset-start-img",
    )

    async def _ok_scene(ctx, *, shot_index, positive_prompt, timeout_s=30):
        return f"scene-{shot_index}"

    async def _fake_post_json(url, payload, timeout_s):
        # Only _generate_video's POST is reached in this test — the scene
        # create is faked above, and the start image is preset on the
        # request, so _generate_start_image is never invoked.
        return {
            "workflows": [{"name": "wf-real-charge-007"}],
            "media": [{"name": "vmedia-abc"}],
        }

    async def _fail_download(ctx, *, media_id, dest, timeout_s=120, poll_interval_s=10):
        raise fk.FlowkitTimeoutError("simulated download timeout AFTER the Veo charge")

    with patch.object(fk, "_create_scene", new=_ok_scene), \
         patch.object(fk, "_http_post_json", new=_fake_post_json), \
         patch.object(fk, "_download_video_media", new=_fail_download):
        with pytest.raises(fk.FlowkitTimeoutError):
            await fk.submit_clip(req, episode_dir=tmp_path, episode_context=ctx)

    records = read_records(ledger_path=ledger_path)
    real_video_rows = [
        r for r in records
        if r["mode"] == "real"
        and r["source"] == "_generate_video"
        and r["episode_id"] == "EP-regression"
        and r["shot_index"] == 7
    ]
    assert len(real_video_rows) == 1, (
        f"expected exactly ONE real _generate_video ledger row for shot 7 "
        f"despite the download failure — got {len(real_video_rows)}. "
        f"All records: {records}"
    )
    assert real_video_rows[0]["veo_job_id"] == "wf-real-charge-007"


@pytest.mark.asyncio
async def test_generate_video_direct_call_blocked_without_decision_no_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scripts/wr3_probe_single_clip.py calls _generate_video DIRECTLY,
    bypassing submit_clip entirely — this proves the gate protects that path
    for free: no valid WR3_SPEND_DECISION → SpendNotAuthorizedError, and the
    HTTP layer is never touched (assert_spend_authorized runs before any
    socket opens)."""
    import wr3_flowkit_client as fk

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.delenv("WR3_SPEND_DECISION", raising=False)

    async def _boom_http(*_a, **_k):
        raise AssertionError("network path reached")

    ctx = fk.EpisodeContext(
        project_id="p", video_id="v", project_name="EP-direct-video",
        endpoint="http://127.0.0.1:8100", paygate="PAYGATE_TIER_ONE",
    )
    with patch.object(fk, "_http_post_json", new=_boom_http):
        with pytest.raises(SpendNotAuthorizedError):
            await fk._generate_video(
                ctx, start_image_media_id="img", scene_id="scene", prompt="p",
            )


@pytest.mark.asyncio
async def test_generate_start_image_direct_call_blocked_without_decision_no_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same contract for _generate_start_image — the other direct call site
    scripts/wr3_probe_single_clip.py exercises."""
    import wr3_flowkit_client as fk

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.delenv("WR3_SPEND_DECISION", raising=False)

    async def _boom_http(*_a, **_k):
        raise AssertionError("network path reached")

    ctx = fk.EpisodeContext(
        project_id="p", video_id="v", project_name="EP-direct-image",
        endpoint="http://127.0.0.1:8100", paygate="PAYGATE_TIER_ONE",
    )
    with patch.object(fk, "_http_post_json", new=_boom_http):
        with pytest.raises(SpendNotAuthorizedError):
            await fk._generate_start_image(ctx, prompt="p")


@pytest.mark.asyncio
async def test_submit_clip_real_mode_blocked_without_decision_no_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The PUBLIC entrypoint wr3-clip-renderer actually calls — submit_clip,
    not _generate_start_image/_generate_video directly — must refuse the same
    way. No WR3_ZERO_SPEND, no WR3_SPEND_DECISION -> SpendNotAuthorizedError
    before any charging HTTP call. Scene creation is faked to succeed so the
    assertion is isolated to the charging call site (_generate_start_image,
    the first one submit_clip reaches when no start image is preset), proving
    the whole real-mode spend-submission path is unreachable end-to-end
    through the same call chain wr3_render_episode.py drives, not merely
    through its internal helpers."""
    import wr3_flowkit_client as fk

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.delenv("WR3_SPEND_DECISION", raising=False)

    async def _ok_scene(ctx, *, shot_index, positive_prompt, timeout_s=30):
        return f"scene-{shot_index}"

    async def _boom_http(*_a, **_k):
        raise AssertionError("network path reached")

    ctx = fk.EpisodeContext(
        project_id="p", video_id="v", project_name="EP-submit-clip-guard",
        endpoint="http://127.0.0.1:8100", paygate="PAYGATE_TIER_ONE",
    )
    req = fk.ClipRequest(shot_index=3, positive_prompt="unauthorized shot")

    with patch.object(fk, "_create_scene", new=_ok_scene), \
         patch.object(fk, "_http_post_json", new=_boom_http):
        with pytest.raises(SpendNotAuthorizedError):
            await fk.submit_clip(req, episode_dir=tmp_path, episode_context=ctx)


@requires_ffmpeg
@pytest.mark.asyncio
async def test_submit_clip_zero_spend_placeholders_differ_by_shot_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end through submit_clip (not just render_placeholder_clip
    directly): two shots of the same zero-spend episode must not produce
    identical mp4s — the burned-in label must actually vary per shot, or a
    downstream stage could silently mix shots up."""
    import hashlib

    monkeypatch.setenv("WR3_ZERO_SPEND", "1")

    import wr3_flowkit_client as fk

    req_a = fk.ClipRequest(shot_index=1, positive_prompt="shot one")
    req_b = fk.ClipRequest(shot_index=2, positive_prompt="shot two")

    result_a = await fk.submit_clip(req_a, episode_dir=tmp_path)
    result_b = await fk.submit_clip(req_b, episode_dir=tmp_path)

    sha_a = hashlib.sha256(result_a.mp4_path.read_bytes()).hexdigest()
    sha_b = hashlib.sha256(result_b.mp4_path.read_bytes()).hexdigest()
    assert sha_a != sha_b
