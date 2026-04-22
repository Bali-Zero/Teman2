"""Tests for empirical_ig_analyzer — loads + will classify 25 own posts."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from backend.services.research.empirical_ig_analyzer import (
    EmpiricalIGAnalyzer,
    ClassifiedPost,
)


@pytest.mark.asyncio
async def test_load_posts_excludes_last_4():
    """Spec requires posts 5-29 (last 4 too recent for mature engagement)."""
    mock_sensor = AsyncMock()
    fake_posts = [{"post_id": f"p{i}", "likes": 10} for i in range(1, 30)]
    mock_sensor.read_posts.return_value = fake_posts
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert len(loaded) == 25
    assert loaded[0]["post_id"] == "p5"  # first post is the 5th newest
    assert loaded[-1]["post_id"] == "p29"


@pytest.mark.asyncio
async def test_load_posts_handles_short_account():
    """If account has fewer than 29 posts, skip 4 newest and return the rest."""
    mock_sensor = AsyncMock()
    fake_posts = [{"post_id": f"p{i}"} for i in range(1, 11)]  # 10 posts
    mock_sensor.read_posts.return_value = fake_posts
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert len(loaded) == 6  # 10 - 4 newest
    assert loaded[0]["post_id"] == "p5"


@pytest.mark.asyncio
async def test_load_posts_returns_empty_when_too_few():
    """If account has <= 4 posts, return empty list."""
    mock_sensor = AsyncMock()
    mock_sensor.read_posts.return_value = [{"post_id": "p1"}, {"post_id": "p2"}]
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert loaded == []


def test_classified_post_schema_has_all_attrs():
    cp = ClassifiedPost(
        post_id="p5", caption="Hook one\nBody here",
        format="CAROUSEL_ALBUM", hook_type="question",
        tone_register="pedagogico", topic="visa",
        posted_hour_wita=12, likes=100, comments=5, saves=20, reach=1500,
    )
    assert cp.engagement_rate == pytest.approx((100 + 5 + 20) / 1500, rel=0.01)


def test_classified_post_engagement_rate_zero_reach():
    cp = ClassifiedPost(
        post_id="p5", caption="x", format="IMAGE", hook_type="question",
        tone_register="tecnico", topic="tax", posted_hour_wita=10,
        likes=5, comments=0, saves=1, reach=0,
    )
    assert cp.engagement_rate == 0.0


# ── Task 8: hook classifier ─────────────────────────────────────────


def test_classify_hooks_parses_claude_json_output():
    """classify_hooks_batch returns {post_id: hook_type} from claude -p JSON."""
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [
        {"post_id": "p1", "caption": "Did you know KBLI 2025 changed?"},
        {"post_id": "p2", "caption": "3 lies about PT PMA"},
    ]
    fake_stdout = (
        "I analyzed the posts.\n"
        '{"classifications":[{"post_id":"p1","hook_type":"question"},'
        '{"post_id":"p2","hook_type":"list"}]}'
    )
    fake_proc = type("P", (), {"returncode": 0, "stdout": fake_stdout, "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_hooks_batch(posts)
    assert result["p1"] == "question"
    assert result["p2"] == "list"


def test_classify_hooks_falls_back_on_rc_nonzero():
    """If claude -p exits nonzero, return 'unknown' for every post."""
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [{"post_id": "p1", "caption": "x"}]
    fake_proc = type("P", (), {"returncode": 1, "stdout": "", "stderr": "err"})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_hooks_batch(posts)
    assert result == {"p1": "unknown"}


def test_classify_hooks_falls_back_on_unparseable_output():
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [{"post_id": "p1", "caption": "x"}, {"post_id": "p2", "caption": "y"}]
    fake_proc = type("P", (), {"returncode": 0, "stdout": "just prose, no JSON", "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_hooks_batch(posts)
    assert result == {"p1": "unknown", "p2": "unknown"}


def test_classify_hooks_sends_batch_prompt_to_claude():
    """Verify the subprocess call uses `claude -p` with a prompt mentioning
    hook_type categories and all post_ids."""
    from unittest.mock import patch, MagicMock
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [
        {"post_id": "p1", "caption": "A"},
        {"post_id": "p2", "caption": "B"},
    ]
    fake_proc = type("P", (), {
        "returncode": 0,
        "stdout": '{"classifications":[{"post_id":"p1","hook_type":"stat"},{"post_id":"p2","hook_type":"story"}]}',
        "stderr": "",
    })()
    with patch("subprocess.run", return_value=fake_proc) as run_mock:
        analyzer.classify_hooks_batch(posts)
    args, kwargs = run_mock.call_args
    cmd = args[0]
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    prompt = cmd[2]
    # Prompt must include the allowed hook categories + both post_ids
    for cat in ("question", "stat", "story", "contrarian", "list"):
        assert cat in prompt
    assert "p1" in prompt
    assert "p2" in prompt


# ── Task 9: tone classifier + Gate 2 skew check ─────────────────────


def test_classify_tones_parses_gemini_json_output():
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [
        {"post_id": "p1", "caption": "In linea con la normativa BKPM..."},
        {"post_id": "p2", "caption": "Another visa horror story from our client..."},
    ]
    fake_stdout = (
        '{"classifications":[{"post_id":"p1","tone_register":"tecnico"},'
        '{"post_id":"p2","tone_register":"rituale"}]}'
    )
    fake_proc = type("P", (), {"returncode": 0, "stdout": fake_stdout, "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_tones_batch(posts)
    assert result["p1"] == "tecnico"
    assert result["p2"] == "rituale"


def test_classify_tones_uses_gemini_cli():
    """Must shell out to `gemini -m gemini-3.1-pro-preview -p <prompt>`."""
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [{"post_id": "p1", "caption": "x"}]
    fake_proc = type("P", (), {
        "returncode": 0,
        "stdout": '{"classifications":[{"post_id":"p1","tone_register":"pedagogico"}]}',
        "stderr": "",
    })()
    with patch("subprocess.run", return_value=fake_proc) as run_mock:
        analyzer.classify_tones_batch(posts)
    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "gemini"
    assert cmd[1] == "-m"
    assert "3.1" in cmd[2]  # model flag value contains 3.1
    assert cmd[3] == "-p"
    prompt = cmd[4]
    for reg in ("pedagogico", "analitico", "tecnico", "rituale",
                "poetico", "ironico", "militante"):
        assert reg in prompt


def test_classify_tones_falls_back_on_rc_nonzero():
    from unittest.mock import patch
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [{"post_id": "p1", "caption": "x"}, {"post_id": "p2", "caption": "y"}]
    fake_proc = type("P", (), {"returncode": 2, "stdout": "", "stderr": "boom"})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_tones_batch(posts)
    assert result == {"p1": "unknown", "p2": "unknown"}


def test_check_skew_flags_dominant_tone():
    """Gate 2: if one tone >60% of sample, flag as skewed."""
    dist = {"pedagogico": 18, "analitico": 3, "tecnico": 2, "ironico": 1,
            "rituale": 1, "militante": 0, "poetico": 0}  # 72% pedagogico
    ok, dominant, pct = EmpiricalIGAnalyzer.check_skew(dist, threshold=0.6)
    assert ok is False
    assert dominant == "pedagogico"
    assert pct == pytest.approx(0.72, abs=0.01)


def test_check_skew_ok_when_balanced():
    dist = {"pedagogico": 10, "analitico": 8, "tecnico": 4, "ironico": 1,
            "rituale": 1, "militante": 1, "poetico": 0}
    ok, _, _ = EmpiricalIGAnalyzer.check_skew(dist, threshold=0.6)
    assert ok is True


def test_check_skew_handles_empty_distribution():
    ok, dominant, pct = EmpiricalIGAnalyzer.check_skew({}, threshold=0.6)
    assert ok is True
    assert dominant == ""
    assert pct == 0.0
