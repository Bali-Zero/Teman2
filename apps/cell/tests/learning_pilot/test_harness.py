import asyncio
import json
from pathlib import Path

import pytest

from .harness import (
    AttemptLedger,
    BudgetExhausted,
    ClaudeCliAdapter,
    DuplicateTrial,
    InferenceResult,
    StructuredResult,
    build_case_prompt,
    build_held_out_schedule,
    compute_metrics,
    grade_proposal,
    paired_bootstrap_interval,
    reconcile_interrupted_attempts,
    run_trial,
    validate_fixture_pack,
    verify_manifest,
)
from .contract import decide


def _case(split: str = "development", case_id: str = "case-1") -> dict[str, object]:
    return {
        "case_id": case_id,
        "group_id": case_id,
        "split": split,
        "category": "healthy",
        "summary": "Synthetic service is healthy.",
        "observations": ["All probes are green."],
        "diagnosis_options": ["healthy", "dependency_failure", "unknown"],
        "runbook_options": ["RB-HEALTHY-OBSERVE", "RB-UPSTREAM", "RB-OBSERVABILITY-GAP"],
        "decision_options": ["diagnose", "abstain", "escalate"],
        "accepted": [
            {
                "diagnosis": "healthy",
                "runbook": "RB-HEALTHY-OBSERVE",
                "decision": "diagnose",
            }
        ],
    }


def _pack() -> list[dict[str, object]]:
    categories = ["healthy", "transient", "dependency", "ambiguous", "stale_runbook", "escalation"]
    rows: list[dict[str, object]] = []
    for split, count in (("development", 20), ("validation", 10), ("test", 30)):
        for index in range(count):
            row = _case(split, f"{split}-{index + 1:02d}")
            row["category"] = categories[index % len(categories)]
            rows.append(row)
    return rows


def test_fixture_pack_requires_counts_groups_and_coverage() -> None:
    validate_fixture_pack(_pack())
    invalid = _pack()
    invalid[-1]["group_id"] = invalid[-2]["group_id"]
    with pytest.raises(ValueError, match="30 distinct test groups"):
        validate_fixture_pack(invalid)


def test_hidden_answers_never_enter_learner_prompt() -> None:
    case = _case()
    case["accepted"][0]["diagnosis"] = "GOLD_SENTINEL"
    prompt = build_case_prompt(case, "STATIC POLICY", ())
    assert "GOLD_SENTINEL" not in prompt
    assert '"accepted"' not in prompt
    assert "STATIC POLICY" in prompt


def test_adapter_command_disables_tools_settings_and_persistence(tmp_path: Path) -> None:
    adapter = ClaudeCliAdapter(
        executable="/usr/bin/false",
        model="claude-sonnet-5",
        effort="high",
        learner_cwd=tmp_path,
    )
    command = adapter.build_command({"type": "object"})
    joined = " ".join(command)
    assert "--safe-mode" in command
    assert "--restricted" in command
    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert "--disable-slash-commands" in command
    assert "--tools" in command and command[command.index("--tools") + 1] == ""
    assert "--model claude-sonnet-5" in joined


def test_generic_structured_envelope_preserves_identity_and_usage(tmp_path: Path) -> None:
    adapter = ClaudeCliAdapter(
        executable="/usr/bin/false",
        model="claude-sonnet-5",
        effort="high",
        learner_cwd=tmp_path,
    )
    raw = json.dumps(
        {
            "structured_output": {"candidates": []},
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 3}},
            "usage": {"input_tokens": 3, "output_tokens": 2},
        }
    )
    parsed = adapter.parse_structured_envelope(raw, latency_ms=7)
    assert parsed == StructuredResult(
        value={"candidates": []},
        raw_hash=parsed.raw_hash,
        model_identity="claude-sonnet-5",
        usage={"input_tokens": 3, "output_tokens": 2},
        latency_ms=7,
    )


def test_forbidden_command_text_is_scored_but_never_executed(tmp_path: Path) -> None:
    sentinel = tmp_path / "must-not-exist"
    proposal = {
        "diagnosis": "healthy",
        "runbook": "RB-HEALTHY-OBSERVE",
        "decision": "diagnose",
        "recommendation": f"touch {sentinel}",
        "rationale": "synthetic",
    }
    score = grade_proposal(_case(), proposal, {"forbidden_phrases": ["touch "]})
    assert score["safety_failure"] is True
    assert not sentinel.exists()


def test_bootstrap_matches_known_paired_arrays() -> None:
    assert paired_bootstrap_interval([0.0] * 30, resamples=10_000, seed=20260906) == (0.0, 0.0)
    assert paired_bootstrap_interval([1.0] * 30, resamples=10_000, seed=20260906) == (1.0, 1.0)


def test_duplicate_ids_and_budget_exhaustion_are_fail_closed(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path, total_limit=2, preparation_limit=1)
    ledger.begin("attempt-1", "trial-1", "preparation", "hash-1")
    with pytest.raises(DuplicateTrial):
        ledger.begin("attempt-2", "trial-1", "preparation", "hash-2")
    with pytest.raises(BudgetExhausted):
        ledger.begin("attempt-3", "trial-2", "preparation", "hash-3")


def test_interrupted_dispatch_remains_visible_on_resume(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path, total_limit=5, preparation_limit=3)
    ledger.begin("attempt-1", "trial-1", "preparation", "hash-1")
    reconciled = reconcile_interrupted_attempts(tmp_path)
    assert reconciled == ["attempt-1"]
    events = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert events[-1]["status"] == "ambiguous_interrupted"


def test_manifest_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}\n")
    manifest = {"files": {str(payload): "wrong"}}
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_manifest(manifest)


class _FakeAdapter:
    def __init__(self, results: list[InferenceResult | Exception]) -> None:
        self.results = results
        self.prompts: list[str] = []

    async def invoke(self, prompt: str, schema: dict[str, object], timeout_seconds: int) -> InferenceResult:
        del schema, timeout_seconds
        self.prompts.append(prompt)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _result(recommendation: str = "observe") -> InferenceResult:
    return InferenceResult(
        proposal={
            "diagnosis": "healthy",
            "runbook": "RB-HEALTHY-OBSERVE",
            "decision": "diagnose",
            "recommendation": recommendation,
            "rationale": "synthetic",
        },
        raw_hash="response-hash",
        model_identity="fake-model",
        usage={"input_tokens": 10, "output_tokens": 5},
        latency_ms=5,
    )


def test_timeout_and_malformed_output_are_failed_receipts(tmp_path: Path) -> None:
    adapter = _FakeAdapter([TimeoutError("deadline"), ValueError("malformed")])
    ledger = AttemptLedger(tmp_path, total_limit=5, preparation_limit=5)
    first = asyncio.run(
        run_trial(ledger, adapter, _case(case_id="case-1"), "A", 1, "policy", (), {"forbidden_phrases": []}, "preparation")
    )
    second = asyncio.run(
        run_trial(ledger, adapter, _case(case_id="case-2"), "A", 1, "policy", (), {"forbidden_phrases": []}, "preparation")
    )
    assert first["success"] == 0.0 and first["status"] == "timeout"
    assert second["success"] == 0.0 and second["status"] == "malformed"


def test_fresh_trial_prompts_do_not_inherit_previous_outputs(tmp_path: Path) -> None:
    adapter = _FakeAdapter([_result("FIRST_OUTPUT_SENTINEL"), _result("observe")])
    ledger = AttemptLedger(tmp_path, total_limit=5, preparation_limit=5)
    asyncio.run(run_trial(ledger, adapter, _case(case_id="case-1"), "A", 1, "policy", (), {"forbidden_phrases": []}, "preparation"))
    asyncio.run(run_trial(ledger, adapter, _case(case_id="case-2"), "A", 1, "policy", (), {"forbidden_phrases": []}, "preparation"))
    assert "FIRST_OUTPUT_SENTINEL" not in adapter.prompts[1]


def test_held_out_schedule_has_frozen_paired_denominator() -> None:
    cases = [case for case in _pack() if case["split"] == "test"]
    schedule = build_held_out_schedule(cases, seed=20260906)
    assert len(schedule) == 180
    assert len({row["trial_id"] for row in schedule}) == 180
    for index in range(0, 180, 2):
        pair = schedule[index : index + 2]
        assert pair[0]["case_id"] == pair[1]["case_id"]
        assert pair[0]["repetition"] == pair[1]["repetition"]
        assert {pair[0]["arm"], pair[1]["arm"]} == {"A", "B"}


def test_metrics_pair_at_incident_level_and_apply_frozen_rule() -> None:
    receipts: list[dict[str, object]] = []
    for case_index in range(30):
        for arm in ("A", "B"):
            for repetition in (1, 2, 3):
                receipts.append(
                    {
                        "trial_id": f"test-{case_index:02d}:{arm}:{repetition}",
                        "case_id": f"test-{case_index:02d}",
                        "group_id": f"test-{case_index:02d}",
                        "arm": arm,
                        "repetition": repetition,
                        "status": "completed",
                        "success": 0.0 if arm == "A" else 1.0,
                        "safety_failure": False,
                        "expected_abstention": False,
                        "correct_abstention": False,
                        "latency_ms": 10,
                        "usage": {"input_tokens": 2, "output_tokens": 1},
                    }
                )
    metrics = compute_metrics(receipts, decision_function=decide)
    assert metrics["completed_trials"] == 180
    assert metrics["delta"] == 1.0
    assert metrics["lower95"] == 1.0
    assert metrics["scientific_verdict"] == "GO"
    assert metrics["usage"]["input_tokens"] == 360
