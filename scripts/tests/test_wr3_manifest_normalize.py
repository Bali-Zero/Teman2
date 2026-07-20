"""Tests for the F20 cure — manifest normalizer makes the validator non-dead-code.

Born from cicatrix F20: validate_manifest() (18 fields) was wired into nothing and
the only real manifest on disk (17 keys, critic_verdict="PASS-WITH-NOTES",
claim_ids=None, wr3_room_version=None) would hard-fail all four gates. These tests
prove: (1) the REAL assembler manifest shape, after normalization, PASSES validation;
(2) the validator still REJECTS a genuinely-bad manifest (no claim_ids); (3) the
PASS-WITH-NOTES verdict the live critic emits is now accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_episode_manifest import (  # noqa: E402
    ALLOWED_VERDICTS,
    MANDATORY_FIELDS,
    ManifestValidationError,
    finalize_episode_manifest,
    normalize_assembler_manifest,
    validate_manifest,
)

# A faithful miniature of the only real manifest on disk
# (content-creator-3-roads-2026-05-29/episode_manifest.json) — 17 keys, divergent names.
REAL_SHAPE = {
    "episode_id": "content-creator-3-roads-2026-05-29",
    "slug": "content-creator-3-roads",
    "assembled_at": "2026-05-30T12:30:00+08:00",
    "master_mp4": {"path": "/x/master.mp4", "sha256": "abc123", "size_bytes": 44019984,
                   "has_video": True, "has_audio": True},
    "duration_s": 144.0,
    "variants": {"tiktok": "/x/tiktok.mp4", "ig-reels": "/x/ig.mp4",
                 "yt-shorts": "/x/yt.mp4", "fb": "/x/fb.mp4"},
    "variants_detail": {}, "variants_failed": [],
    "clips_count": 18, "vo_lufs": -13.8, "vo_path": "/x/vo.wav",
    "music_path": "/x/music.mp3", "subtitles_ass": "/x/subs.ass",
    "identity_gate": 0.79, "render_cost_cr": 360,
    "degradation_flags": ["subtitle_loss"], "critic_verdict": "PASS-WITH-NOTES",
}

BRIEF = {
    "topic": "Content creator in Indonesia — the 3 legal roads",
    "audience_segment": "digital-nomad",
    "regulatory_citations": [
        {"claim_id": "claim-q9r0s1t2", "citation": "UU 6/2011 Pasal 75"},
        {"claim_id": "claim-a1b2c3d4", "citation": "Permenkumham X"},
    ],
    "key_numbers": [{"claim_id": "claim-num-1", "value": "USD 60k"}],
}

IDENTITY = {"overall_cosine_avg": 0.7901841575449162, "hard_fail_triggered": False}


def test_real_shape_fails_validation_raw():
    """Sanity: the raw assembler manifest really IS incompatible (the F20 finding)."""
    with pytest.raises(ManifestValidationError):
        validate_manifest(REAL_SHAPE)


def test_normalized_real_shape_passes_validation():
    """The headline F20 cure: normalize the real shape -> all 18 fields present + valid."""
    out = normalize_assembler_manifest(REAL_SHAPE, brief=BRIEF, identity_report=IDENTITY)
    # all 18 mandatory fields present
    assert set(MANDATORY_FIELDS).issubset(out.keys())
    # field mapping correct
    assert out["topic"] == BRIEF["topic"]
    assert out["audience_segment"] == "digital-nomad"
    assert out["duration_master_ms"] == 144000
    assert out["flow_credits_spent"] == 360
    assert out["lufs_measured"] == -13.8
    assert out["identity_overall_cosine_avg"] == pytest.approx(0.79018, rel=1e-3)
    assert out["variants_delivered"] == ["tiktok", "ig-reels", "yt-shorts", "fb"]
    assert out["asset_hashes"]["master.mp4"] == "abc123"
    assert out["claim_ids"] == ["claim-q9r0s1t2", "claim-a1b2c3d4", "claim-num-1"]
    assert out["wr3_room_version"] == "0.1.0"
    # and it VALIDATES (the whole point)
    validate_manifest(out)  # must not raise


def test_pass_with_notes_now_accepted():
    assert "PASS-WITH-NOTES" in ALLOWED_VERDICTS
    out = normalize_assembler_manifest(REAL_SHAPE, brief=BRIEF, identity_report=IDENTITY)
    assert out["critic_verdict"] == "PASS-WITH-NOTES"
    validate_manifest(out)


def test_no_claim_ids_still_rejected():
    """The validator must STILL reject a genuinely-bad episode (zero claims). Not toothless."""
    out = normalize_assembler_manifest(REAL_SHAPE, brief={}, identity_report=IDENTITY)
    assert out["claim_ids"] == []
    with pytest.raises(ManifestValidationError, match="claim_ids"):
        validate_manifest(out)


def test_finalize_writes_normalized_sibling(tmp_path: Path):
    ep = tmp_path / "ep-1"
    ep.mkdir()
    (ep / "episode_manifest.json").write_text(json.dumps(REAL_SHAPE))
    (ep / "brief.json").write_text(json.dumps(BRIEF))
    (ep / "identity-report.json").write_text(json.dumps(IDENTITY))
    out = finalize_episode_manifest(ep)
    normalized_path = ep / "episode_manifest.normalized.json"
    assert normalized_path.exists()
    # original NOT overwritten
    assert json.loads((ep / "episode_manifest.json").read_text()) == REAL_SHAPE
    assert json.loads(normalized_path.read_text())["topic"] == BRIEF["topic"]


def test_malformed_future_manifest_fails_loud():
    """Refuter CLAIM-1 hardening: a future/malformed assembler manifest must NOT slide
    through silently. A shape with no claims + no derivable verdict is REJECTED, not
    normalized into a fake-green pass."""
    malformed = {"episode_id": "future-x", "slug": "future",
                 "assembled_at": "2026-07-01T00:00:00+08:00",
                 "duration_s": 60.0, "variants": {}, "critic_verdict": "WHATEVER-NEW-VERDICT"}
    out = normalize_assembler_manifest(malformed, brief={}, identity_report={})
    # unknown verdict not in the (deliberately) widened enum -> rejected
    with pytest.raises(ManifestValidationError):
        validate_manifest(out)


REAL_EPISODE = Path("/Users/nuzantara/nuzantara/apps/war-room/output/episode/"
                    "content-creator-3-roads-2026-05-29")


@pytest.mark.skipif(not REAL_EPISODE.exists(),
                    reason="real episode dir not present (CI/clean checkout)")
def test_against_the_actual_on_disk_manifest():
    """Strongest proof: the ACTUAL manifest on disk, normalized, passes — not a mock."""
    out = finalize_episode_manifest(REAL_EPISODE, write=False)
    validate_manifest(out)
    assert out["critic_verdict"] == "PASS-WITH-NOTES"
    assert len(out["claim_ids"]) >= 1
