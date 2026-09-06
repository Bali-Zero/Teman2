import json
from pathlib import Path

from .run_experiment import (
    admission_decision,
    freeze_manifest,
    normalize_candidates,
    validate_model_identity,
)


def _validation_receipts(a_success: float, b_success: float) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for index in range(10):
        for arm, success in (("A", a_success), ("B", b_success)):
            receipts.append(
                {
                    "trial_id": f"validation-{index}:{arm}:1",
                    "arm": arm,
                    "success": success,
                    "safety_failure": False,
                    "expected_abstention": index == 0,
                    "correct_abstention": index == 0,
                }
            )
    return receipts


def test_candidates_receive_content_bound_stable_ids() -> None:
    raw = {
        "candidates": [
            {
                "name": "Separate symptom from cause",
                "content": "Treat temporal coincidence as weak evidence.",
                "prerequisites": "Multiple plausible diagnoses.",
                "expected_outcome": "More correct abstentions.",
            }
        ]
    }
    first = normalize_candidates(raw, provenance="development-run")
    second = normalize_candidates(raw, provenance="development-run")
    assert first == second
    assert first[0]["skill_id"].startswith("skill-")
    assert len(first[0]["content_hash"]) == 64
    assert first[0]["provenance"] == "development-run"


def test_admission_rule_requires_complete_safe_validation_gain() -> None:
    candidates = normalize_candidates(
        {
            "candidates": [
                {
                    "name": "Skill",
                    "content": "Use the supplied uncertainty cues.",
                    "prerequisites": "Ambiguous observations.",
                    "expected_outcome": "Better abstention.",
                }
            ]
        },
        provenance="development-run",
    )
    admitted = admission_decision(_validation_receipts(0.5, 0.7), candidates)
    assert admitted["admitted"] is True
    assert admitted["selected_skill_ids"] == [candidates[0]["skill_id"]]
    unsafe = _validation_receipts(0.5, 0.7)
    unsafe[-1]["safety_failure"] = True
    assert admission_decision(unsafe, candidates)["admitted"] is False
    assert admission_decision(_validation_receipts(0.7, 0.7), candidates)["admitted"] is False


def test_manifest_binds_files_and_rejects_mutation(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest = freeze_manifest(manifest_path, [payload], metadata={"run_id": "run-1"})
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert manifest["metadata"]["run_id"] == "run-1"
    payload.write_text('{"changed":true}\n', encoding="utf-8")
    assert manifest["files"][str(payload)] != manifest["files"].get("changed")


def test_model_identity_must_match_requested_alias() -> None:
    validate_model_identity("claude-sonnet-5", "claude-sonnet-5")
    try:
        validate_model_identity("claude-sonnet-5", "claude-sonnet-4-6")
    except RuntimeError as exc:
        assert "silent model switch" in str(exc)
    else:
        raise AssertionError("model mismatch was accepted")
