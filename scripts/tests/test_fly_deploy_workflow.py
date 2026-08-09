"""Regression tests for Fly.io production deploy triggers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fly-deploy.yml"


def test_deploy_ignores_test_and_markdown_only_changes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '"!apps/backend-rag/**/tests/**"' in workflow
    assert '"!apps/backend-rag/**/*.md"' in workflow
    assert "Check migration status (informational)" not in workflow
