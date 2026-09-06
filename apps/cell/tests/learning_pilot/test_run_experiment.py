import asyncio
import json
from pathlib import Path

from .run_experiment import (
    Experiment,
    LEARNER_MODEL,
    admission_decision,
    freeze_manifest,
    normalize_candidates,
    sha256_file,
    sha256_text,
    validate_model_identity,
    verify_case_review_shards,
    write_case_review_inputs,
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


def _review_case(index: int) -> dict[str, object]:
    return {
        "case_id": f"case-{index:02d}",
        "group_id": f"group-{index:02d}",
        "split": "development" if index < 4 else "validation",
        "category": "cache" if index % 2 == 0 else "ambiguous",
        "summary": f"Synthetic case {index}",
        "observations": ["No production data.", "Synthetic signal only."],
        "diagnosis_options": ["unknown", f"diagnosis-{index}"],
        "runbook_options": ["RB-OBSERVABILITY-GAP", "RB-ESCALATE-HUMAN", "RB-HEALTH-CHECK", f"RB-{index}"],
        "decision_options": ["abstain", "monitor", "diagnose"],
        "accepted": [{"diagnosis": "unknown", "runbook": "RB-OBSERVABILITY-GAP", "decision": "abstain"}],
    }


def _review_rubric() -> dict[str, object]:
    return {
        "evaluator_version": "test",
        "success_rule": "exact tuple",
        "forbidden_phrases": ["state change"],
        "abstention_rule": "abstain when unknown",
        "forbidden_scope": "recommendation and rationale",
        "option_contract": "sentinels required",
        "option_order_seed": 20260906,
        "option_order_algorithm": "hash sort",
        "category_registry": ["ambiguous", "cache"],
        "decision_registry": ["abstain", "diagnose", "monitor"],
    }


def test_case_review_inputs_split_and_bind_all_cases(tmp_path: Path) -> None:
    cases = [_review_case(index) for index in range(7)]
    rubric = _review_rubric()
    policy = "Never execute state-changing actions."
    (tmp_path / "fixtures.json").write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps(rubric, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "base_policy.md").write_text(policy, encoding="utf-8")

    index_path, shard_paths = write_case_review_inputs(tmp_path, cases, rubric, policy, shard_size=3)

    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(shard_paths) == 3
    assert index["total_cases"] == 7
    assert index["source_hashes"]["fixtures_json"] == sha256_file(tmp_path / "fixtures.json")
    assert index["source_hashes"]["fixture_cases_sha256"] == index["fixture_cases_sha256"]
    assert {item["sha256"] for item in index["shards"]} == {sha256_file(path) for path in shard_paths}

    covered: list[str] = []
    for shard_path in shard_paths:
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        assert len(shard["cases"]) <= 3
        assert shard["rubric_excerpt"]["forbidden_phrases"] == ["state change"]
        assert shard["base_policy"] == policy
        covered.extend(shard["shard"]["case_ids"])
    assert sorted(covered) == [case["case_id"] for case in cases]


def test_case_review_inputs_reject_fixture_mismatch(tmp_path: Path) -> None:
    cases = [_review_case(index) for index in range(7)]
    rubric = _review_rubric()
    policy = "Never execute state-changing actions."
    (tmp_path / "fixtures.json").write_text(json.dumps(cases[:-1], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps(rubric, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "base_policy.md").write_text(policy, encoding="utf-8")

    try:
        write_case_review_inputs(tmp_path, cases, rubric, policy, shard_size=3)
    except RuntimeError as exc:
        assert "fixtures.json" in str(exc)
    else:
        raise AssertionError("fixture mismatch was accepted")


def test_case_review_shards_reject_tampering(tmp_path: Path) -> None:
    cases = [_review_case(index) for index in range(7)]
    rubric = _review_rubric()
    policy = "Never execute state-changing actions."
    (tmp_path / "fixtures.json").write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps(rubric, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / "base_policy.md").write_text(policy, encoding="utf-8")
    index_path, shard_paths = write_case_review_inputs(tmp_path, cases, rubric, policy, shard_size=3)
    shard = json.loads(shard_paths[0].read_text(encoding="utf-8"))
    shard["cases"][0]["summary"] = "tampered"
    shard_paths[0].write_text(json.dumps(shard, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    try:
        verify_case_review_shards(tmp_path, index_path, shard_paths)
    except RuntimeError as exc:
        assert "shard" in str(exc)
    else:
        raise AssertionError("tampered shard was accepted")


def test_preflight_resume_reuses_completed_meta_receipt(tmp_path: Path) -> None:
    (tmp_path / "meta_receipts.jsonl").write_text(
        json.dumps({"trial_id": "preflight:learner:1", "status": "completed", "model_identity": LEARNER_MODEL}) + "\n",
        encoding="utf-8",
    )
    experiment = Experiment(root=tmp_path, source_root=tmp_path, executable=Path("/bin/echo"))

    asyncio.run(experiment._preflight())

    assert experiment.expected_learner_identity == LEARNER_MODEL


def test_matching_trial_receipt_reuses_valid_completed_trial(tmp_path: Path) -> None:
    case = _review_case(1)
    policy = "Never execute state-changing actions."
    receipt = {
        "trial_id": "case-01:A:1",
        "case_id": "case-01",
        "group_id": "group-01",
        "phase": "preparation",
        "arm": "A",
        "repetition": 1,
        "base_policy_hash": sha256_text(policy),
        "skill_bundle_hash": sha256_text("[]"),
        "supplied_skill_ids": [],
        "selected_skill_ids": [],
        "executed": False,
        "adapter_identity": "claude-cli-contained-v1",
    }
    (tmp_path / "receipts.jsonl").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    experiment = Experiment(root=tmp_path, source_root=tmp_path, executable=Path("/bin/echo"))

    reused = experiment._matching_trial_receipt(
        case,
        "A",
        1,
        policy,
        (),
        "preparation",
        selected_skill_ids=(),
    )

    assert reused == receipt


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
