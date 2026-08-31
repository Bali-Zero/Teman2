"""Behavioral contract for the thin, deterministic WR3 Factory control plane.

These tests never open a socket and never invoke Flow.  They exercise the real
filesystem boundary because interruption safety, idempotence, and hash drift are
the behavior under test.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
FULL_DRY_RUN_FIXTURE = (
    SCRIPTS_DIR / "tests" / "fixtures" / "wr3_factory" / "full_dry_run.json"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_factory import (  # noqa: E402
    FactoryError,
    advance_state,
    dry_run_episode,
    package_episode,
    prepare_episode,
    validate_canary_authorization,
    validate_episode,
    canary_episode,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@pytest.fixture()
def factory_repo(tmp_path: Path) -> Path:
    factory = tmp_path / "docs" / "wr3" / "factory"
    episode = factory / "episodes" / "s01e13-residency-permit"
    editorial = factory / "editorial"
    episode.mkdir(parents=True)
    editorial.mkdir(parents=True)

    (factory / "FACTORY_STATE.md").write_text(
        "\n".join(
            [
                "# Zantara Video Factory — Current State",
                "",
                "- factory_phase: `TOPIC_APPROVAL_REQUIRED`",
                "- publication_allowed: `false`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        editorial / "season-01.json",
        {
            "schema_version": "1.0",
            "status": "TOPIC_APPROVAL_REQUIRED",
            "recommended_topics": [
                {
                    "episode_number": number,
                    "candidate_id": f"C{number:02d}",
                    "working_title": f"Episode {number}",
                }
                for number in range(1, 21)
            ],
            "reserve_topics": [
                {"candidate_id": f"R{number:02d}", "working_title": f"Reserve {number}"}
                for number in range(1, 11)
            ],
            "approved_topic_ids": [],
            "safety_switch_values": {
                "ALLOW_FLOW_SPEND": 0,
                "ALLOW_REAL_RENDER": 0,
                "ALLOW_YOUTUBE_UPLOAD": 0,
                "ALLOW_EXTERNAL_PUBLISH": 0,
                "ALLOW_DEPLOY": 0,
            },
        },
    )
    _write_json(
        episode / "context-snapshot.json",
        {
            "schema_version": "1.0",
            "episode_id": "S01E13",
            "candidate_id": "C07",
            "title": "What Your Residency Permit Does Not Come With",
            "identity": {"anchor_id": "A007", "anchor_sha256": "a" * 64},
            "format": {"native_audio": True},
        },
    )
    _write_json(
        episode / "topic-approval.json",
        {
            "schema_version": "1.0",
            "episode_id": "S01E13",
            "candidate_id": "C07",
            "decision": "APPROVED",
            "scope": "bounded_pilot",
            "approved_by": "human",
            "publication_allowed": False,
        },
    )
    return tmp_path


def _stage_english_package(
    factory_repo: Path,
    *,
    claim_ids: tuple[str, ...] = ("claim-001",),
) -> tuple[Path, str]:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state"] = "FINAL_QA_PASS"
    _write_json(manifest_path, manifest)
    (episode / "master.mp4").write_bytes(b"immutable-english-master")
    _write_json(
        episode / "script.json",
        {
            "status": "FROZEN",
            "language": "en",
            "claim_ids": list(claim_ids),
            "text": "Synthetic English source",
        },
    )
    (episode / "captions_en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nSource.\n",
        encoding="utf-8",
    )
    (episode / "captions_en.vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nSource.\n",
        encoding="utf-8",
    )
    return episode, hashlib.sha256((episode / "script.json").read_bytes()).hexdigest()


def _stage_translation_base(
    episode: Path,
    language: str,
    source_script_sha256: str,
    claim_ids: tuple[str, ...],
    *,
    multilingual_level: int,
) -> Path:
    language_dir = episode / "languages" / language
    _write_json(
        language_dir / f"script_{language}.json",
        {
            "status": "LOCKED",
            "language": language,
            "source_script_sha256": source_script_sha256,
            "claim_ids": list(claim_ids),
            "text": "Terjemahan sintetis.",
        },
    )
    (language_dir / f"captions_{language}.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nTerjemahan.\n",
        encoding="utf-8",
    )
    (language_dir / f"captions_{language}.vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nTerjemahan.\n",
        encoding="utf-8",
    )
    _write_json(
        language_dir / f"metadata_{language}.json",
        {
            "multilingual_level": multilingual_level,
            "localized_title": "Judul sintetis",
            "localized_description": "Deskripsi sintetis",
            "semantic_qa_status": "PASS",
            "terminology_qa_status": "PASS",
        },
    )
    return language_dir


def test_prepare_is_byte_idempotent_and_stops_at_first_missing_gate(
    factory_repo: Path,
) -> None:
    first = prepare_episode(factory_repo, "S01E13")
    manifest_path = Path(first["manifest_path"])
    first_bytes = manifest_path.read_bytes()

    second = prepare_episode(factory_repo, "S01E13")

    assert first["state"] == "TOPIC_APPROVED"
    assert first["next_state"] == "GROUNDED"
    assert second["changed"] is False
    assert manifest_path.read_bytes() == first_bytes


def test_state_transition_cannot_skip_a_required_predecessor() -> None:
    manifest = {"state": "TOPIC_APPROVED", "transitions": []}

    with pytest.raises(FactoryError, match="cannot skip"):
        advance_state(manifest, "SCRIPT_LOCKED", evidence=[])


def test_dry_run_is_read_only_and_submits_zero_flow_jobs(factory_repo: Path) -> None:
    prepare_episode(factory_repo, "S01E13")
    episode = (
        factory_repo
        / "docs"
        / "wr3"
        / "factory"
        / "episodes"
        / "s01e13-residency-permit"
    )
    before = {path.relative_to(episode): path.read_bytes() for path in episode.rglob("*") if path.is_file()}

    report = dry_run_episode(factory_repo, "S01E13")

    after = {path.relative_to(episode): path.read_bytes() for path in episode.rglob("*") if path.is_file()}
    assert report["status"] == "BLOCKED"
    assert report["next_state"] == "GROUNDED"
    assert report["flow_jobs_submitted"] == 0
    assert report["flow_credits_consumed"] == 0
    assert before == after


def test_synthetic_fixture_covers_full_nonspending_dry_run_path(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    fixture = json.loads(FULL_DRY_RUN_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["terminal_state"] == "READY_FOR_SPEND"
    assert fixture["contains_flow_render"] is False
    for relative, payload in fixture["files"].items():
        if relative != "pre-render-gate.json":
            _write_json(episode / relative, payload)
    pre_render = dict(fixture["files"]["pre-render-gate.json"])
    pre_render["shot_pack_sha256"] = __import__("hashlib").sha256(
        (episode / "shot-pack.json").read_bytes()
    ).hexdigest()
    _write_json(episode / "pre-render-gate.json", pre_render)
    before = {
        path.relative_to(episode): path.read_bytes()
        for path in episode.rglob("*")
        if path.is_file()
    }

    report = dry_run_episode(factory_repo, "S01E13")

    after = {
        path.relative_to(episode): path.read_bytes()
        for path in episode.rglob("*")
        if path.is_file()
    }
    assert report["current_state"] == "TOPIC_APPROVED"
    assert report["would_advance_to"] == "READY_FOR_SPEND"
    assert report["status"] == "BLOCKED"
    assert report["flow_jobs_submitted"] == 0
    assert report["flow_credits_consumed"] == 0
    assert report["writes_performed"] == 0
    assert report["network_calls"] == 0
    assert before == after
    assert not (episode / "render-report.json").exists()


def test_validate_detects_drift_in_persisted_evidence(factory_repo: Path) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    context = (
        factory_repo
        / "docs"
        / "wr3"
        / "factory"
        / "episodes"
        / "s01e13-residency-permit"
        / "context-snapshot.json"
    )
    context.write_text(context.read_text(encoding="utf-8") + " ", encoding="utf-8")

    report = validate_episode(factory_repo, "S01E13")

    assert report["valid"] is False
    assert report["state"] == prepared["state"]
    assert report["drift"][0]["path"] == "context-snapshot.json"


def test_prepare_refuses_to_advance_from_drifted_evidence(factory_repo: Path) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    context_path = episode / "context-snapshot.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["title"] = "Tampered after approval"
    _write_json(context_path, context)
    _write_json(
        episode / "brief.json",
        {
            "grounding_status": "GROUNDED",
            "claim_ids": ["claim-001"],
        },
    )

    with pytest.raises(FactoryError, match="evidence drift"):
        prepare_episode(factory_repo, "S01E13")

    persisted = json.loads(Path(prepared["manifest_path"]).read_text(encoding="utf-8"))
    assert persisted["state"] == "TOPIC_APPROVED"


def test_untracked_recovered_clip_is_reported_but_cannot_skip_state(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    clip = episode / "clips" / "105.mp4"
    clip.parent.mkdir()
    clip.write_bytes(b"recovered-real-clip-evidence")

    report = validate_episode(factory_repo, "S01E13")

    assert report["state"] == "TOPIC_APPROVED"
    assert report["valid"] is False
    assert report["untracked_artifacts"] == ["clips/105.mp4"]


def test_resume_accepts_already_completed_render_as_both_consecutive_edges(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state"] = "RENDER_AUTHORIZED"
    _write_json(manifest_path, manifest)
    _write_json(
        episode / "render-report.json",
        {
            "status": "OK",
            "rendered": [{"shot_id": "s001", "path": "clips/s001.mp4"}],
            "failed": [],
        },
    )

    report = prepare_episode(factory_repo, "S01E13")

    assert report["state"] == "RENDERED"
    assert report["next_state"] == "ASSEMBLED"


def test_canary_authorization_is_episode_cap_and_shotpack_specific() -> None:
    manifest = {"episode_id": "S01E13", "state": "READY_FOR_SPEND"}
    authorization = {
        "type": "FLOW_CANARY",
        "episode_id": "S01E13",
        "max_credits": 10,
        "clip_count": 1,
        "shot_id": "s001",
        "authorization_text": "AUTHORIZE FLOW CANARY: S01E13 MAX_CREDITS: 10",
        "shot_pack_sha256": "b" * 64,
        "authorized_by": "human",
    }

    assert validate_canary_authorization(
        manifest,
        authorization,
        requested_max_credits=10,
        current_shot_pack_sha256="b" * 64,
    )["authorized"] is True

    for changed in (
        {**authorization, "episode_id": "S01E12"},
        {**authorization, "max_credits": 9},
        {**authorization, "shot_pack_sha256": "c" * 64},
        {**authorization, "clip_count": 2},
        {**authorization, "authorization_text": "yes go ahead"},
    ):
        with pytest.raises(FactoryError):
            validate_canary_authorization(
                manifest,
                changed,
                requested_max_credits=10,
                current_shot_pack_sha256="b" * 64,
            )


def test_package_never_modifies_english_master_and_marks_missing_language_blocked(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest = json.loads(Path(prepared["manifest_path"]).read_text(encoding="utf-8"))
    manifest["state"] = "FINAL_QA_PASS"
    manifest["transitions"] = [
        {"from": "ASSEMBLED", "to": "FINAL_QA_PASS", "evidence": []}
    ]
    _write_json(Path(prepared["manifest_path"]), manifest)
    master = episode / "master.mp4"
    master.write_bytes(b"immutable-english-master")
    (episode / "script.json").write_text(
        json.dumps(
            {
                "status": "FROZEN",
                "language": "en",
                "claim_ids": ["claim-001"],
                "text": "Synthetic English source",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (episode / "captions_en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nSynthetic.\n",
        encoding="utf-8",
    )
    (episode / "captions_en.vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nSynthetic.\n",
        encoding="utf-8",
    )
    master_before = master.read_bytes()

    report = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert master.read_bytes() == master_before
    assert report["state"] == "FINAL_QA_PASS"
    assert report["languages"]["en"]["status"] == "READY"
    assert report["languages"]["id"]["status"] == "BLOCKED"
    assert report["youtube_upload_status"] == "DISABLED"


def test_package_blocks_overlapping_english_subtitle_cues(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state"] = "FINAL_QA_PASS"
    _write_json(manifest_path, manifest)
    (episode / "master.mp4").write_bytes(b"immutable-english-master")
    _write_json(
        episode / "script.json",
        {
            "status": "FROZEN",
            "language": "en",
            "claim_ids": ["claim-001"],
            "text": "Synthetic English source",
        },
    )
    (episode / "captions_en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nFirst.\n\n"
        "2\n00:00:01,900 --> 00:00:03,000\nOverlap.\n",
        encoding="utf-8",
    )
    (episode / "captions_en.vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:02.000\nFirst.\n",
        encoding="utf-8",
    )

    report = package_episode(factory_repo, "S01E13", languages=("en",))

    assert report["status"] == "BLOCKED"
    assert report["state"] == "FINAL_QA_PASS"
    assert "captions_en.srt: cue 2 overlaps cue 1" in report["languages"]["en"][
        "validation_errors"
    ]


def test_translated_package_is_bound_to_frozen_source_and_preserves_claims(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state"] = "FINAL_QA_PASS"
    _write_json(manifest_path, manifest)
    (episode / "master.mp4").write_bytes(b"immutable-english-master")
    _write_json(
        episode / "script.json",
        {
            "status": "FROZEN",
            "language": "en",
            "claim_ids": ["claim-001", "claim-002"],
            "text": "Synthetic English source",
        },
    )
    source_sha256 = hashlib.sha256((episode / "script.json").read_bytes()).hexdigest()
    for suffix, timestamp in (
        ("srt", "00:00:00,000 --> 00:00:01,000"),
        ("vtt", "00:00.000 --> 00:01.000"),
    ):
        (episode / f"captions_en.{suffix}").write_text(
            ("WEBVTT\n\n" if suffix == "vtt" else "1\n")
            + timestamp
            + "\nSource.\n",
            encoding="utf-8",
        )
    language_dir = episode / "languages" / "id"
    _write_json(
        language_dir / "script_id.json",
        {
            "status": "LOCKED",
            "language": "id",
            "source_script_sha256": source_sha256,
            "claim_ids": ["claim-001"],
            "text": "Terjemahan sintetis.",
        },
    )
    (language_dir / "captions_id.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nTerjemahan.\n",
        encoding="utf-8",
    )
    (language_dir / "captions_id.vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nTerjemahan.\n",
        encoding="utf-8",
    )
    _write_json(
        language_dir / "metadata_id.json",
        {
            "localized_title": "Judul sintetis",
            "localized_description": "Deskripsi sintetis",
            "semantic_qa_status": "PASS",
            "terminology_qa_status": "PASS",
        },
    )

    stale = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert stale["languages"]["en"]["status"] == "READY"
    assert stale["languages"]["id"]["status"] == "BLOCKED"
    assert stale["languages"]["id"]["validation_errors"] == [
        "translation claim IDs do not exactly match the frozen English script"
    ]

    translation_path = language_dir / "script_id.json"
    translation = json.loads(translation_path.read_text(encoding="utf-8"))
    translation["claim_ids"] = ["claim-001", "claim-002"]
    _write_json(translation_path, translation)

    ready = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert ready["status"] == "READY"
    assert ready["state"] == "YOUTUBE_PACKAGE_READY"
    assert ready["languages"]["id"]["source_script_sha256"] == source_sha256
    assert ready["languages"]["id"]["claim_ids"] == ["claim-001", "claim-002"]
    assert ready["languages"]["en"]["multilingual_level"] == "CANONICAL"
    assert ready["languages"]["id"]["multilingual_level"] == 1
    assert ready["youtube_upload_status"] == "DISABLED"

    language_manifest = episode / "metadata" / "language_manifest.json"
    frozen_package = language_manifest.read_bytes()
    replay = package_episode(factory_repo, "S01E13", languages=("en", "id"))
    assert replay["state"] == "YOUTUBE_PACKAGE_READY"
    assert language_manifest.read_bytes() == frozen_package

    translation = json.loads(translation_path.read_text(encoding="utf-8"))
    translation["text"] = "Terjemahan yang diubah setelah paket dikunci."
    _write_json(translation_path, translation)

    with pytest.raises(FactoryError, match="cannot replace a locked language package"):
        package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert language_manifest.read_bytes() == frozen_package


def test_level_2_manual_audio_never_claims_perfect_lip_sync(
    factory_repo: Path,
) -> None:
    episode, source_sha256 = _stage_english_package(factory_repo)
    language_dir = _stage_translation_base(
        episode,
        "id",
        source_sha256,
        ("claim-001",),
        multilingual_level=2,
    )
    (language_dir / "dialogue_id.wav").write_bytes(b"synthetic-dialogue")
    (language_dir / "mix_id.wav").write_bytes(b"synthetic-mix")
    metadata_path = language_dir / "metadata_id.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "voice_approval_status": "APPROVED",
            "human_review_status": "APPROVED",
            "duration": 60.1,
            "duration_drift": 0.1,
            "duration_qa_status": "PASS",
            "lip_sync_claim": "PERFECT",
        }
    )
    _write_json(metadata_path, metadata)

    report = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert report["status"] == "BLOCKED"
    assert report["languages"]["id"]["multilingual_level"] == 2
    assert "Level 2 must not claim perfect lip sync" in report["languages"]["id"][
        "validation_errors"
    ]
    assert report["languages"]["id"]["full_mix_asset"] == "languages/id/mix_id.wav"


def test_level_3_native_cut_regenerates_only_sync_foreground_shots(
    factory_repo: Path,
) -> None:
    episode, source_sha256 = _stage_english_package(factory_repo)
    language_dir = _stage_translation_base(
        episode,
        "id",
        source_sha256,
        ("claim-001",),
        multilingual_level=3,
    )
    localized_video = language_dir / "video_id_native.mp4"
    localized_video.write_bytes(b"synthetic-separate-native-flow-cut")
    localized_video_sha256 = hashlib.sha256(localized_video.read_bytes()).hexdigest()
    level_3_manifest = language_dir / "level3-render-manifest.json"
    _write_json(
        level_3_manifest,
        {
            "status": "PASS",
            "language": "id",
            "source_script_sha256": source_sha256,
            "flow_authorization_sha256": "f" * 64,
            "localized_video": "languages/id/video_id_native.mp4",
            "localized_video_sha256": localized_video_sha256,
            "regenerated_shot_classes": ["SYNC_FOREGROUND", "PURE_BROLL"],
            "reused_shot_classes": ["PURE_BROLL", "TRANSITION"],
            "canary_qa_status": "PASS",
            "identity_qa_status": "PASS",
            "voice_qa_status": "PASS",
            "pronunciation_qa_status": "PASS",
            "audio_qa_status": "PASS",
            "lip_sync_qa_status": "PASS",
            "native_speaker_review_status": "PASS",
        },
    )

    rejected = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert rejected["status"] == "BLOCKED"
    assert rejected["languages"]["id"]["multilingual_level"] == 3
    assert "Level 3 may regenerate only SYNC_FOREGROUND shots" in rejected[
        "languages"
    ]["id"]["validation_errors"]

    manifest = json.loads(level_3_manifest.read_text(encoding="utf-8"))
    manifest["regenerated_shot_classes"] = ["SYNC_FOREGROUND"]
    _write_json(level_3_manifest, manifest)

    accepted = package_episode(factory_repo, "S01E13", languages=("en", "id"))

    assert accepted["status"] == "READY"
    assert accepted["languages"]["id"]["voice_approval_status"] == "NATIVE_FLOW_QA_PASS"
    assert accepted["languages"]["id"]["full_mix_asset"] == (
        "languages/id/video_id_native.mp4"
    )


def test_unbound_canary_executor_does_not_consume_or_log_spend_authority(
    factory_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    episode = Path(prepared["manifest_path"]).parent
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["state"] = "READY_FOR_SPEND"
    _write_json(manifest_path, manifest)
    _write_json(
        episode / "shot-pack.json",
        {
            "status": "LOCKED",
            "shots": [{"shot_id": "s001", "shot_class": "SYNC_FOREGROUND"}],
        },
    )
    shot_pack_hash = __import__("hashlib").sha256(
        (episode / "shot-pack.json").read_bytes()
    ).hexdigest()
    _write_json(
        episode / "canary-authorization.json",
        {
            "type": "FLOW_CANARY",
            "episode_id": "S01E13",
            "max_credits": 10,
            "clip_count": 1,
            "shot_id": "s001",
            "authorization_text": "AUTHORIZE FLOW CANARY: S01E13 MAX_CREDITS: 10",
            "shot_pack_sha256": shot_pack_hash,
            "authorized_by": "human",
        },
    )
    spend_log = factory_repo / "spend-decisions.jsonl"
    monkeypatch.setenv("ALLOW_FLOW_SPEND", "1")
    monkeypatch.setenv("ALLOW_REAL_RENDER", "1")
    monkeypatch.setenv(
        "WR3_SPEND_DECISION", f"S01E13:human:{date.today().isoformat()}"
    )
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(spend_log))
    monkeypatch.setattr("wr3_factory.socket.gethostname", lambda: "Nuzantara")

    report = canary_episode(factory_repo, "S01E13")

    assert report["reason"] == "CANARY_EXECUTOR_NOT_BOUND"
    assert report["flow_jobs_submitted"] == 0
    assert not spend_log.exists()


def test_validate_rejects_tampered_evidence_path_outside_episode(
    factory_repo: Path,
) -> None:
    prepared = prepare_episode(factory_repo, "S01E13")
    manifest_path = Path(prepared["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence"]["PROPOSED"][0]["path"] = "../../../../FACTORY_STATE.md"
    _write_json(manifest_path, manifest)

    with pytest.raises(FactoryError, match="escapes"):
        validate_episode(factory_repo, "S01E13")


def test_factory_executable_exposes_the_real_plan_command(factory_repo: Path) -> None:
    executable = SCRIPTS_DIR / "cli" / "factory"
    result = subprocess.run(
        [str(executable), "--repo-root", str(factory_repo), "plan"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "plan"
    assert payload["status"] == "TOPIC_APPROVAL_REQUIRED"
    assert payload["recommended_topics"] == 20
    assert payload["reserve_topics"] == 10
