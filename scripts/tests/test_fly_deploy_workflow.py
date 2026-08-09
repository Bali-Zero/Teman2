"""Regression tests for Fly.io production deploy triggers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fly-deploy.yml"


def test_deploy_ignores_test_and_docs_only_changes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '"!apps/backend-rag/**/tests/**"' in workflow
    assert '"!apps/backend-rag/docs/**"' in workflow
    assert '"!apps/backend-rag/**/README.md"' in workflow
    assert "Check migration status (informational)" not in workflow


def test_deploy_never_excludes_runtime_markdown() -> None:
    # A blanket "!**/*.md" exclusion would also skip runtime-read markdown
    # baked into the image (training-data/*.md is COPY'd by the Dockerfile and
    # read by conversation_trainer), stranding merged content undeployed
    # (merged-is-not-live, scar family #2/W86). Only docs-class paths may be
    # excluded, each named explicitly.
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '"!apps/backend-rag/**/*.md"' not in workflow
    assert "!apps/backend-rag/training-data" not in workflow
    assert "!apps/backend-rag/backend" not in workflow
