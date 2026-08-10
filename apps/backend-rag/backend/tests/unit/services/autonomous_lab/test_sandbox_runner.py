from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.services.autonomous_lab.command_policy import (
    ADMIN_DASHBOARD_LINT_COMMAND,
    PYTEST_AUTONOMOUS_LAB_COMMAND,
    CommandExecutionPlan,
    admin_dashboard_lint_env,
    autonomous_lab_pytest_env,
    expected_env_for_allowlisted_command,
    git_diff_check_env,
    plan_for_allowlisted_command,
)
from backend.services.autonomous_lab.sandbox_runner import LocalWorktreeSandboxRunner
from backend.tests.unit.services.autonomous_lab.conftest import FAKE_NPM


def test_command_policy_uses_only_backend_venv_and_minimal_env(tmp_path: Path) -> None:
    # Hermetic: build a repo tree with a stub `.venv/bin/pytest` so the plan
    # resolves deterministically. The previous version relied on the ambient
    # checkout shipping a `.venv` — true on a dev box but NOT in CI, where deps
    # are installed `--system`, so the plan came back None and the assertions
    # never ran (masked by `pytest -x`).
    repo_root = tmp_path
    backend_root = repo_root / "apps" / "backend-rag"
    venv_pytest = backend_root / ".venv" / "bin" / "pytest"
    venv_pytest.parent.mkdir(parents=True, exist_ok=True)
    venv_pytest.touch()

    plan = plan_for_allowlisted_command(
        PYTEST_AUTONOMOUS_LAB_COMMAND,
        repo_root=repo_root,
        backend_root=backend_root,
    )

    assert plan is not None
    assert plan.cwd == backend_root
    assert plan.env == autonomous_lab_pytest_env()
    assert set(plan.env) == {"CI", "PATH", "PYTHONPATH"}
    assert "HOME" not in plan.env
    assert "SECRET" not in "".join(plan.env)
    assert plan.argv[0] == str(backend_root / ".venv" / "bin" / "pytest")


def test_admin_dashboard_lint_plan_is_shell_free_and_exact(tmp_path: Path, fake_npm: str) -> None:
    repo_root = tmp_path

    plan = plan_for_allowlisted_command(
        ADMIN_DASHBOARD_LINT_COMMAND,
        repo_root=repo_root,
        backend_root=repo_root / "apps" / "backend-rag",
    )

    assert plan is not None
    assert plan.cwd == repo_root / "apps" / "admin-dashboard"
    assert plan.env is not None
    assert plan.env["CI"] == "true"
    assert plan.env["PATH"].split(":")[0] == "/fake/toolchain/bin"
    assert plan.argv[0] == fake_npm
    assert plan.argv[1:] == ["run", "lint"]


def test_admin_dashboard_lint_plan_is_none_when_npm_is_absent(
    tmp_path: Path, absent_npm: None
) -> None:
    """Pro and Mini have no npm: the policy must decline, not build a broken plan."""
    plan = plan_for_allowlisted_command(
        ADMIN_DASHBOARD_LINT_COMMAND,
        repo_root=tmp_path,
        backend_root=tmp_path / "apps" / "backend-rag",
    )

    assert plan is None
    assert expected_env_for_allowlisted_command(ADMIN_DASHBOARD_LINT_COMMAND) is None


def test_sandbox_runner_refuses_admin_dashboard_lint_when_npm_is_absent(
    tmp_path: Path, absent_npm: None
) -> None:
    """The runner refuses rather than executing an argv it cannot validate."""

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("the runner must not execute a plan it cannot validate")

    admin_root = tmp_path / "apps" / "admin-dashboard"
    admin_root.mkdir(parents=True)
    plan = CommandExecutionPlan(
        command=ADMIN_DASHBOARD_LINT_COMMAND,
        argv=[FAKE_NPM, "run", "lint"],
        cwd=admin_root,
        env=admin_dashboard_lint_env(FAKE_NPM),
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    # The receipt fingerprints the refusal string, so the reason is only
    # readable at its source. Asserting the fingerprint would pin an opaque
    # constant; asserting the reason pins the behaviour.
    assert runner._plan_refusal_reason(plan) == "executable_not_found"


def test_sandbox_runner_executes_shell_free_and_hashes_output(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="ok token=abcdef1234567890 client@example.com\n",
            stderr="RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR\n",
        )

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env=git_diff_check_env(),
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls[0][0] == ["git", "diff", "--check"]
    assert "shell" not in calls[0][1]
    assert calls[0][1]["timeout"] == 600
    assert calls[0][1]["env"] == git_diff_check_env()
    assert receipt["returncode"] == 0
    assert receipt["stdout"].startswith("stdout_fingerprint:sha256:")
    assert receipt["stderr"].startswith("stderr_fingerprint:sha256:")
    assert "abcdef1234567890" not in str(receipt)
    assert "client@example.com" not in str(receipt)
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in str(receipt)


def test_sandbox_runner_executes_admin_dashboard_lint_shape(tmp_path: Path, fake_npm: str) -> None:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="lint ok", stderr="")

    admin_root = tmp_path / "apps" / "admin-dashboard"
    admin_root.mkdir(parents=True)
    plan = CommandExecutionPlan(
        command=ADMIN_DASHBOARD_LINT_COMMAND,
        argv=[fake_npm, "run", "lint"],
        cwd=admin_root,
        env=admin_dashboard_lint_env(fake_npm),
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls[0][0] == [fake_npm, "run", "lint"]
    assert calls[0][1]["cwd"] == admin_root
    assert calls[0][1]["env"] == admin_dashboard_lint_env(fake_npm)
    assert receipt["allowed"] is True
    assert receipt["executed"] is True


def test_sandbox_runner_returns_timeout_receipt(tmp_path: Path) -> None:
    def fake_timeout(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=argv,
            timeout=1,
            output=b"partial token=abcdef1234567890",
            stderr=b"RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
        )

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env=git_diff_check_env(),
    )
    runner = LocalWorktreeSandboxRunner(
        repo_root=tmp_path,
        timeout_seconds=1,
        run_func=fake_timeout,
    )

    receipt = runner.run(plan).to_receipt()

    assert receipt["returncode"] == 124
    assert receipt["timed_out"] is True
    assert "abcdef1234567890" not in str(receipt)
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in str(receipt)


def test_sandbox_runner_returns_receipt_safe_os_error(tmp_path: Path) -> None:
    def fake_missing(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("token=abcdef1234567890 missing executable")

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env=git_diff_check_env(),
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_missing)

    receipt = runner.run(plan).to_receipt()

    assert receipt["returncode"] == 127
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert "abcdef1234567890" not in str(receipt)
    assert "missing executable" not in str(receipt)


def test_sandbox_runner_rejects_cwd_outside_worktree(tmp_path: Path) -> None:
    outside = tmp_path.parent
    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=outside,
    )

    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path)

    with pytest.raises(ValueError, match="inside the Lab worktree"):
        runner.run(plan)


def test_sandbox_runner_refuses_non_allowlisted_command_without_execution(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="should not run", stderr="")

    plan = CommandExecutionPlan(
        command="git push origin main",
        argv=["git", "push", "origin", "main"],
        cwd=tmp_path,
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls == []
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert receipt["returncode"] == 126


def test_sandbox_runner_refuses_mismatched_argv_without_execution(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="should not run", stderr="")

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=[
            "python",
            "-c",
            "print('token=abcdef1234567890 RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR')",
        ],
        cwd=tmp_path,
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls == []
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert receipt["returncode"] == 126
    assert "argv_not_allowlisted" not in str(receipt)
    assert "abcdef1234567890" not in str(receipt)
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in str(receipt)
    assert all(str(arg).startswith("evidence_fingerprint:sha256:") for arg in receipt["argv"])


def test_sandbox_runner_refuses_allowlisted_command_from_wrong_cwd(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="should not run", stderr="")

    worktree = tmp_path / "repo"
    subdir = worktree / "research"
    subdir.mkdir(parents=True)
    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=subdir,
    )
    runner = LocalWorktreeSandboxRunner(repo_root=worktree, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls == []
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert receipt["returncode"] == 126


def test_sandbox_runner_refuses_unsafe_env_key_without_leaking_value(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="should not run", stderr="")

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env={"PYTHONPATH": ".", "SECRET_TOKEN": "abc123"},
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls == []
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert "SECRET_TOKEN" not in str(receipt)
    assert "abc123" not in str(receipt)


def test_sandbox_runner_refuses_allowlisted_env_value_without_execution(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="should not run", stderr="")

    plan = CommandExecutionPlan(
        command="git diff --check",
        argv=["git", "diff", "--check"],
        cwd=tmp_path,
        env={"CI": "true", "PATH": "/tmp/token-abcdef1234567890:/usr/bin:/bin"},
    )
    runner = LocalWorktreeSandboxRunner(repo_root=tmp_path, run_func=fake_run)

    receipt = runner.run(plan).to_receipt()

    assert calls == []
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert "abcdef1234567890" not in str(receipt)
