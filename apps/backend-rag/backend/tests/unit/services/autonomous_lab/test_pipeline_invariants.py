from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.services.autonomous_lab.command_policy import (
    ADMIN_DASHBOARD_LINT_COMMAND,
    GENERIC_GIT_DIFF_CHECK_COMMAND,
    PYTEST_AUTONOMOUS_LAB_COMMAND,
    CommandExecutionPlan,
    contains_blocked_command_verb,
    git_diff_check_env,
    plan_for_allowlisted_command,
    require_safe_command_arg,
    verification_commands_for_paths,
)
from backend.services.autonomous_lab.evaluator import (
    AutonomousLabEvaluator,
    EvaluationVerdict,
)
from backend.services.autonomous_lab.experiment_spec import build_experiment_spec
from backend.services.autonomous_lab.normalizer import normalize_and_dedupe_materials
from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    MaterialSourceType,
    ResearchMaterial,
)
from backend.services.autonomous_lab.receipt_safety import (
    contains_receipt_sensitive_value,
    receipt_safe_command_output,
    receipt_safe_source_uri,
)
from backend.services.autonomous_lab.reviewer import invalid_autonomous_lab_target_path_reason
from backend.services.autonomous_lab.sandbox_policy import default_sandbox_policy
from backend.services.autonomous_lab.sandbox_runner import (
    LocalWorktreeSandboxRunner,
    SandboxCommandResult,
)
from backend.services.autonomous_lab.shadow_run import build_shadow_run
from backend.services.autonomous_lab.source_adapters import (
    SourceAdapterKind,
    SourceAdapterSpec,
    build_shadow_watchtower_tick,
)

SENSITIVE_SAMPLES = (
    "operator@example.com",
    "+62 812 3456 7890",
    "6281234567890@s.whatsapp.net",
    "api_key=sk-proj-abcdefghijklmnop",
    "https://example.test/path?token=abcdef1234567890&sig=123",
    "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
)


def _receipt_text(payload: object) -> str:
    return json.dumps(payload, sort_keys=True)


def test_receipt_safety_detects_and_redacts_common_sensitive_shapes() -> None:
    for sample in SENSITIVE_SAMPLES:
        assert contains_receipt_sensitive_value(sample), sample

    output = "\n".join(SENSITIVE_SAMPLES)
    receipt = receipt_safe_command_output(output, source="stdout", hash_only=False)

    assert "[REDACTED_EMAIL]" in receipt
    assert "[REDACTED_PHONE]" in receipt
    assert "[REDACTED_WHATSAPP_HANDLE]" in receipt
    assert "[REDACTED_SECRET_ASSIGNMENT]" in receipt
    assert "?REDACTED_QUERY" in receipt
    assert "[REDACTED_RAW_MARKER]" in receipt
    for sample in SENSITIVE_SAMPLES:
        assert sample not in receipt


def test_source_uri_redaction_strips_queries_and_private_adapter_paths() -> None:
    public_uri = receipt_safe_source_uri(
        "https://papers.example/research/123?token=abcdef1234567890",
        "web",
    )
    private_uri = receipt_safe_source_uri(
        "notebooklm://shadow/private/source/123?token=abcdef1234567890",
        "other",
        preserve_public_host=False,
    )

    assert public_uri.startswith("https://papers.example/source_fingerprint:sha256:")
    assert "research/123" not in public_uri
    assert "token=" not in public_uri
    assert private_uri.startswith("other:source_fingerprint:sha256:")
    assert "private/source" not in private_uri


def test_shadow_pipeline_receipts_never_echo_sensitive_objective_text() -> None:
    objective = (
        "Study agentic papers for operator@example.com, phone +62 812 3456 7890, "
        "api_key=sk-proj-abcdefghijklmnop, RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    )

    shadow = build_shadow_run(
        objective=objective,
        target_paths=("apps/backend-rag/backend/services/autonomous_lab",),
        task_id="dirty-objective",
        created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    receipt_text = _receipt_text(shadow.to_receipt())

    assert shadow.external_calls == 0
    assert shadow.execution_allowed is False
    assert shadow.curator_decision.promotion_allowed is False
    assert "operator@example.com" not in receipt_text
    assert "+62 812 3456 7890" not in receipt_text
    assert "sk-proj-abcdefghijklmnop" not in receipt_text
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in receipt_text
    assert "evidence_fingerprint:sha256:" in receipt_text


def test_shadow_tick_with_no_adapters_is_idle_and_receipt_safe() -> None:
    tick = build_shadow_watchtower_tick(
        objective="idle watch",
        adapters=(),
        captured_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )

    receipt = tick.to_receipt()

    assert tick.idle is True
    assert tick.external_calls == 0
    assert receipt["signals"] == []
    assert receipt["signal_count"] == 0


def test_shadow_tick_private_adapter_keeps_only_fingerprint_source() -> None:
    adapter = SourceAdapterSpec(
        key="operator_dirty_note",
        kind=SourceAdapterKind.OPERATOR_NOTE,
        source_type=MaterialSourceType.OPERATOR_NOTE,
        read_policy="metadata only",
        write_policy="no writes",
        freshness_window_hours=1,
    )

    tick = build_shadow_watchtower_tick(
        objective="private note",
        adapters=(adapter,),
        captured_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    source_uri = tick.to_receipt()["signals"][0]["source_uri"]

    assert source_uri.startswith("operator_note:source_fingerprint:sha256:")
    assert "shadow/operator_dirty_note" not in source_uri


def test_command_policy_blocks_verbs_inside_compound_commands() -> None:
    blocked = (
        "git push origin main",
        "gh pr merge 123",
        "fly deploy --strategy rolling",
        "npm run deploy:prod",
    )

    for command in blocked:
        assert contains_blocked_command_verb(command), command

    assert verification_commands_for_paths(["apps/mouth/app/page.tsx"]) == [
        "cd apps/mouth && npm run lint"
    ]
    assert verification_commands_for_paths(
        ["apps/admin-dashboard/app/autonomous-lab/page.tsx"]
    ) == [ADMIN_DASHBOARD_LINT_COMMAND]


def test_safe_command_slug_rejects_shell_metacharacters() -> None:
    with pytest.raises(ValueError, match="safe slug"):
        require_safe_command_arg("ops;rm-rf", "worktree_lane")

    with pytest.raises(ValueError, match="safe slug"):
        require_safe_command_arg("../escape", "task_id")


def test_target_paths_reject_control_characters_before_planning() -> None:
    bad_path = "apps/backend-rag/backend/services/autonomous_lab/planner.py\nBAD"

    assert invalid_autonomous_lab_target_path_reason(bad_path) == (
        "target path must not contain control characters"
    )

    planner = AutonomousLabPlanner()
    material = ResearchMaterial(
        material_id="mat-control-path",
        source_type=MaterialSourceType.OPERATOR_NOTE,
        source_uri="note://local/control-path",
        title="Control path",
        text="Target path validation must reject invisible multiline input.",
        captured_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
        metadata={"scope": "path-validation"},
    )

    with pytest.raises(ValueError, match="control characters"):
        planner.draft_run(
            objective="reject multiline target path",
            materials=[material],
            target_paths=[bad_path],
            task_id="control-path-check",
            created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
        )


def test_plan_for_allowlisted_command_returns_none_without_backend_venv(tmp_path: Path) -> None:
    assert (
        plan_for_allowlisted_command(
            PYTEST_AUTONOMOUS_LAB_COMMAND,
            repo_root=tmp_path,
            backend_root=tmp_path / "apps" / "backend-rag",
    )
        is None
    )


def test_plan_for_admin_dashboard_lint_is_shell_free(tmp_path: Path) -> None:
    plan = plan_for_allowlisted_command(
        ADMIN_DASHBOARD_LINT_COMMAND,
        repo_root=tmp_path,
        backend_root=tmp_path / "apps" / "backend-rag",
    )

    assert plan is not None
    assert plan.command == ADMIN_DASHBOARD_LINT_COMMAND
    assert plan.argv[0].endswith("/npm")
    assert plan.argv[1:] == ["run", "lint"]
    assert plan.cwd == tmp_path / "apps" / "admin-dashboard"
    assert plan.env is not None
    assert plan.env["CI"] == "true"
    assert "PATH" in plan.env


def test_sandbox_runner_refuses_empty_argv_before_policy_execution(tmp_path: Path) -> None:
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path)
    plan = CommandExecutionPlan(
        command=GENERIC_GIT_DIFF_CHECK_COMMAND,
        argv=[],
        cwd=tmp_path,
    )

    with pytest.raises(ValueError, match="must include argv"):
        runner.run(plan)


def test_evaluator_passes_only_after_policy_commands_sandbox_and_novelty_pass() -> None:
    planner = AutonomousLabPlanner()
    material = ResearchMaterial(
        material_id="mat-1",
        source_type=MaterialSourceType.WEB,
        source_uri="https://research.example/agent/1",
        title="Agent research",
        text="Unique metadata-only synthesis for protected evaluator implementation.",
        captured_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
        metadata={"tags": "research,eval"},
    )
    run = planner.draft_run(
        objective="safe evaluation pass",
        materials=[material],
        target_paths=["research/operations/autonomous-lab/map.md"],
        task_id="evaluator-pass",
        created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    batch = normalize_and_dedupe_materials(
        materials=[material],
        planner=planner,
        created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    spec = build_experiment_spec(run=run, candidate_summary="research-only verifier")
    sandbox_result = SandboxCommandResult(
        command="git diff --check -- research/operations/autonomous-lab",
        argv=("git", "diff", "--check", "--", "research/operations/autonomous-lab"),
        cwd=Path("/tmp/repo"),
        returncode=0,
        stdout_reference="stdout_fingerprint:sha256:aaaa-bbbb-cccc; chars:2; redacted_chars:2",
        stderr_reference="stderr_fingerprint:sha256:dddd-eeee-ffff; chars:0; redacted_chars:0",
    )

    report = AutonomousLabEvaluator().evaluate(
        spec=spec,
        sandbox_results=(sandbox_result,),
        normalized_batch=batch,
    )

    assert report.verdict is EvaluationVerdict.PASS
    assert report.promotion_eligible is True
    assert report.failure_count == 0
    assert report.pending_count == 0


def test_evaluator_fails_on_dangerous_policy_failed_sandbox_and_low_novelty() -> None:
    planner = AutonomousLabPlanner()
    materials = [
        ResearchMaterial(
            material_id=f"dup-{index}",
            source_type=MaterialSourceType.WEB,
            source_uri=f"https://research.example/dup/{index}",
            title=f"Duplicate {index}",
            text="Same exact duplicated content",
            captured_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
            metadata={"tags": "research"},
        )
        for index in range(3)
    ]
    run = planner.draft_run(
        objective="unsafe evaluation fail",
        materials=materials,
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/evaluator.py"],
        task_id="evaluator-fail",
        created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    policy = replace(default_sandbox_policy(), production_writes_allowed=True)
    spec = build_experiment_spec(
        run=run,
        candidate_summary="unsafe policy",
        sandbox_policy=policy,
    )
    failed_result = SandboxCommandResult(
        command=GENERIC_GIT_DIFF_CHECK_COMMAND,
        argv=("git", "diff", "--check"),
        cwd=Path("/tmp/repo"),
        returncode=1,
        stdout_reference="stdout_fingerprint:sha256:aaaa-bbbb-cccc; chars:0; redacted_chars:0",
        stderr_reference="stderr_fingerprint:sha256:dddd-eeee-ffff; chars:10; redacted_chars:10",
        allowed=True,
    )
    batch = normalize_and_dedupe_materials(
        materials=materials,
        planner=planner,
        created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
    )

    report = AutonomousLabEvaluator().evaluate(
        spec=spec,
        sandbox_results=(failed_result,),
        normalized_batch=batch,
    )
    metrics = {metric.name: metric.status.value for metric in report.metrics}

    assert report.verdict is EvaluationVerdict.FAIL
    assert metrics["sandbox_policy"] == "fail"
    assert metrics["sandbox_execution"] == "fail"
    assert metrics["novelty"] == "fail"


def test_sandbox_runner_executes_allowed_plan_and_never_uses_shell(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    plan = CommandExecutionPlan(
        command=GENERIC_GIT_DIFF_CHECK_COMMAND,
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env=git_diff_check_env(),
    )

    result = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run).run(plan)

    assert result.returncode == 0
    assert result.allowed is True
    assert result.executed is True
    assert calls[0]["argv"] == ["git", "diff", "--check"]
    assert "shell" not in calls[0]
