"""Regression checks for the non-blocking Claude PR-review invocation."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ai-pr-review.yml"


def _review_step() -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    start = workflow.index("      - name: Run advisory review")
    end = workflow.index("\n      - name:", start)
    return workflow[start:end]


def test_advisory_review_is_data_only_when_workspace_is_untrusted() -> None:
    """Guilt: the legacy bare `claude -p` fails this exact contract."""
    review_step = _review_step()

    assert "claude -p" in review_step
    assert "--safe-mode" in review_step
    assert "--permission-mode plan" in review_step
    assert '--tools ""' in review_step
    assert "--no-chrome" in review_step
    assert "--no-session-persistence" in review_step


def test_advisory_review_does_not_enable_a_permission_bypass() -> None:
    """Innocence: a trust fix must not turn into a general CI bypass."""
    review_step = _review_step()

    assert "--dangerously-skip-permissions" not in review_step
    assert "--allow-dangerously-skip-permissions" not in review_step
    assert "--permission-mode bypassPermissions" not in review_step


def test_advisory_review_fails_visibly_for_missing_output_or_cli_error() -> None:
    """Guilt: the legacy success-on-error branch fails this exact contract."""
    review_step = _review_step()
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    empty_output_guard = "if [ ! -s /tmp/review.txt ]; then"

    assert 'review_workspace="$(mktemp -d)"' in review_step
    assert "trap 'rm -rf" in review_step
    assert review_step.index('cd "$review_workspace"') < review_step.index("claude -p")
    assert "--setting-sources user" in review_step
    assert empty_output_guard in review_step
    assert review_step.index(empty_output_guard) < review_step.index('echo "ok=true"')
    assert review_step.count("exit 1") >= 2
    assert "claude CLI returned empty output" in review_step
    assert "claude CLI exited nonzero" in review_step
    assert "ok=false" not in review_step
    assert "AI review unavailable" not in review_step
    assert "review artifact is missing" in workflow
    assert "empty review output — nothing to post." not in workflow


def test_cli_failure_diagnostics_are_bounded_and_opaque() -> None:
    review_step = _review_step()

    assert "Claude CLI stdout base64 (max 2000 bytes)" in review_step
    assert "head -c 2000 /tmp/review.txt | base64 -w 0" in review_step
    assert "Claude CLI stderr base64 (max 2000 bytes)" in review_step
    assert "head -c 2000 /tmp/review.err | base64 -w 0" in review_step
    assert "head -c 2000 /tmp/review.txt | sed -n" not in review_step
    assert "head -20 /tmp/review.err" not in review_step


def test_base64_diagnostics_terminate_before_workflow_commands() -> None:
    review_step = _review_step()

    assert "head -c 2000 /tmp/review.txt | base64 -w 0\n            echo\n            echo \"::endgroup::\"" in review_step
    assert "head -c 2000 /tmp/review.err | base64 -w 0\n            echo\n            echo \"::endgroup::\"" in review_step
