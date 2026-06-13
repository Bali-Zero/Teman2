"""Tests for the WR3 reflexion synthesizer (F21 cure).

Born from cicatrix F21 / W74: the previous synthesizer was an 816-byte stub that
`sys.exit(0)`'d every Sunday, synthesizing nothing ("green cron != working").
These tests assert the REAL thing happens: episodes are read, lessons are written,
AND — crucially — the Delta Gate records every run so a NO_INPUT run is auditable
on disk instead of a silent exit (the Mythos "Omeostasi Tautologica" counter-measure).

No live LLM call: call_llm_synthesis is monkeypatched. We test the plumbing
(read episode dirs -> build prompt -> write lessons.md -> record state), which is
exactly the load-bearing logic the stub never had.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_reflexion_synthesis as rs  # noqa: E402


def _make_episode(repo_root: Path, name: str, *, manifest: dict | None = None) -> Path:
    ep = repo_root / "apps/war-room/output/episode" / name
    ep.mkdir(parents=True, exist_ok=True)
    (ep / "episode_manifest.json").write_text(json.dumps(manifest or {
        "episode_id": name,
        "critic_verdict": "PASS-WITH-NOTES",
        "degradation_flags": ["audio_fallback"],
        "render_cost_cr": 120,
    }))
    (ep / "identity-report.json").write_text(json.dumps({
        "overall_cosine_avg": 0.61, "hard_fail_triggered": False, "clips_failed": 0,
    }))
    return ep


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    skill = tmp_path / "skill"
    (repo / "apps/war-room/output/episode").mkdir(parents=True)
    monkeypatch.setenv("WR3_REPO_ROOT", str(repo))
    monkeypatch.setenv("WR3_SKILL_DIR", str(skill))
    # re-read module-level path helpers honor env at call time
    return repo, skill


def test_no_input_records_delta_gate_not_silent_exit(env, monkeypatch):
    """The headline F21 fix: an empty window does NOT silently exit — it records NO_INPUT."""
    repo, skill = env
    # No episodes created. LLM must NOT be called.
    monkeypatch.setattr(rs, "call_llm_synthesis",
                        lambda p: pytest.fail("LLM called on empty input"))
    rc = rs.main()
    assert rc == 0
    state = json.loads((skill / "_reflexion-state.json").read_text())
    assert len(state) == 1
    assert state[0]["status"] == "NO_INPUT"
    assert state[0]["episodes_found"] == 0
    assert state[0]["lessons_written"] == 0


def test_synthesizes_lessons_from_recent_episode(env, monkeypatch):
    """An in-window episode + a (mocked) LLM => lessons.md written under the agent dir."""
    repo, skill = env
    _make_episode(repo, "ep-recent-2026")
    monkeypatch.setattr(rs, "call_llm_synthesis", lambda prompt: {
        "week": "2026-W24",
        "lessons": [{
            "lesson_text": "audio_fallback fired — pre-check Veo native audio LUFS earlier",
            "agent": "audio-asset-producer",
            "category": "audio",
            "confidence": "medium",
            "motivating_episode_ids": ["ep-recent-2026"],
            "proposes_skill_draft": True,
            "suggested_addition": "If degradation_flags includes audio_fallback, raise LUFS gate.",
        }],
        "synthesis_notes": "one audio fallback this week",
    })
    rc = rs.main()
    assert rc == 0
    lessons_md = skill / "audio-asset-producer" / "lessons.md"
    assert lessons_md.exists()
    body = lessons_md.read_text()
    assert "audio_fallback" in body
    assert "ep-recent-2026" in body
    # skill draft proposed
    drafts = list((skill / "_proposed").glob("*.md"))
    assert len(drafts) == 1
    # delta gate records SYNTHESIZED
    state = json.loads((skill / "_reflexion-state.json").read_text())
    assert state[-1]["status"] == "SYNTHESIZED"
    assert state[-1]["lessons_written"] == 1


def test_llm_failure_with_input_is_loud_exit_1(env, monkeypatch):
    """Episodes present but LLM cascade fails => exit 1 + LLM_FAILED recorded (not silent green)."""
    repo, skill = env
    _make_episode(repo, "ep-recent-2026")
    monkeypatch.setattr(rs, "call_llm_synthesis", lambda prompt: None)
    rc = rs.main()
    assert rc == 1
    state = json.loads((skill / "_reflexion-state.json").read_text())
    assert state[-1]["status"] == "LLM_FAILED"


def test_old_episode_outside_window_is_no_input(env, monkeypatch):
    """An episode dir older than the window is correctly excluded (honest NO_INPUT)."""
    repo, skill = env
    ep = _make_episode(repo, "ep-old-2026")
    # backdate dir mtime 30 days
    import os, time
    old = time.time() - 30 * 86400
    os.utime(ep, (old, old))
    monkeypatch.setattr(rs, "call_llm_synthesis",
                        lambda p: pytest.fail("LLM called on out-of-window episode"))
    rc = rs.main()
    assert rc == 0
    state = json.loads((skill / "_reflexion-state.json").read_text())
    assert state[-1]["status"] == "NO_INPUT"


def test_lessons_capped_at_max(env, monkeypatch):
    """More than MAX_LESSONS proposed => capped (no runaway append)."""
    repo, skill = env
    _make_episode(repo, "ep-recent-2026")
    many = [{
        "lesson_text": f"lesson {i}", "agent": "critic", "category": "brand",
        "confidence": "low", "motivating_episode_ids": ["ep-recent-2026"],
        "proposes_skill_draft": False, "suggested_addition": f"add {i}",
    } for i in range(25)]
    monkeypatch.setattr(rs, "call_llm_synthesis",
                        lambda prompt: {"week": "2026-W24", "lessons": many})
    rc = rs.main()
    assert rc == 0
    body = (skill / "critic" / "lessons.md").read_text()
    assert body.count("*Reflexion") == rs.MAX_LESSONS
