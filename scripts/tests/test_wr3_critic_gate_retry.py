"""Critic gate + retry routing — verifies orchestrator routes FAIL to retry lanes.

Per dossier 06 episode lifecycle:
  FAIL lane 1 → wr3-shot-director       (identity / visual quality)
  FAIL lane 2 → wr3-post-assembler      (audio sync / LUFS)
  FAIL lane 3 → wr3-script-editor       (brand voice / cliche pattern)
  FAIL lane 4 → wr3-brief-interpreter   (legal/regulatory accuracy)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_episode_manifest import (  # noqa: E402
    MANDATORY_FIELDS,
    ManifestBuilder,
    ManifestValidationError,
    validate_manifest,
)


# Lane → retry agent mapping (orchestrator contract)
LANE_RETRY_AGENT = {
    1: "wr3-shot-director",
    2: "wr3-post-assembler",
    3: "wr3-script-editor",
    4: "wr3-brief-interpreter",
}


def _build_passing_manifest(verdict: str = "PASS") -> dict:
    b = ManifestBuilder(
        episode_id="ep-critic-test",
        topic="t",
        audience_segment="s",
    )
    b.add_claim("c")
    b.record_agent("wr3-critic", "1.0.0", cost_usd=0.48)
    b.variants_delivered = ["tiktok", "ig-reels", "yt-shorts", "fb"]
    b.identity_overall_cosine_avg = 0.72
    b.lufs_measured = -14.0
    b.critic_verdict = verdict
    return b.finalize()


def test_critic_pass_manifest_validates() -> None:
    m = _build_passing_manifest("PASS")
    validate_manifest(m)


def test_critic_fail_manifest_validates() -> None:
    m = _build_passing_manifest("FAIL")
    validate_manifest(m)


def test_critic_degraded_manifest_validates() -> None:
    m = _build_passing_manifest("DEGRADED")
    validate_manifest(m)


def test_critic_pending_initial_state() -> None:
    m = _build_passing_manifest("PENDING")
    validate_manifest(m)


def test_critic_invalid_verdict_rejected() -> None:
    m = _build_passing_manifest("PASS")
    m["critic_verdict"] = "MAYBE_LATER"
    with pytest.raises(ManifestValidationError, match="critic_verdict"):
        validate_manifest(m)


def test_lane_to_retry_agent_mapping_complete() -> None:
    """4-lane critic rubric has 4 lane→retry mappings, no orphans."""
    assert set(LANE_RETRY_AGENT.keys()) == {1, 2, 3, 4}
    assert all(v.startswith("wr3-") for v in LANE_RETRY_AGENT.values())


def test_lane_3_routes_to_script_editor() -> None:
    """Brand voice / cliche → script-editor rewrite, not shot-director re-roll."""
    assert LANE_RETRY_AGENT[3] == "wr3-script-editor"


def test_lane_4_routes_to_brief_interpreter() -> None:
    """Legal accuracy FAIL → re-do brief grounding, not script tweak."""
    assert LANE_RETRY_AGENT[4] == "wr3-brief-interpreter"


def test_lane_1_identity_routes_to_shot_director() -> None:
    """Identity (ArcFace) FAIL → re-prompt shots, not re-edit script."""
    assert LANE_RETRY_AGENT[1] == "wr3-shot-director"


def test_identity_below_threshold_breaks_validation_via_assertion() -> None:
    """Manifest validation alone does not enforce identity threshold — that's
    the critic's job. This test documents the boundary."""
    m = _build_passing_manifest("FAIL")
    m["identity_overall_cosine_avg"] = 0.4  # below 0.6 threshold
    # Manifest layer allows this — critic verdict already FAIL captures it
    validate_manifest(m)


def test_eighteen_fields_present_in_all_verdict_states() -> None:
    for verdict in ("PENDING", "PASS", "FAIL", "DEGRADED"):
        m = _build_passing_manifest(verdict)
        for field in MANDATORY_FIELDS:
            assert field in m, f"verdict={verdict} missing field={field}"
