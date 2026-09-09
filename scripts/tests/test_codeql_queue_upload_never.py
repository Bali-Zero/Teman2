"""CodeQL under the merge queue analyses but never uploads (2026-09-09).

WHY: the queue's temporary ref (refs/heads/gh-readonly-queue/main/pr-N-<sha>) is
deleted as soon as the group is rebuilt or merged. `codeql-action/analyze` uploads
its SARIF at the END of a ~15-minute python analysis, and that upload then fails
with "ref ... not found" — 4 of the 14 merge_group Security Scanning runs on
2026-09-09 went red this way, on commits the queue had already moved past. The
PR lane uploaded the same findings minutes earlier and the daily schedule covers
main, so the queue run only has to prove the analysis builds and passes.

Guilt + innocence on the SUBJECT (security.yml), entity match on the step's
`with.upload` expression — not a substring grep of the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_YML = REPO_ROOT / ".github" / "workflows" / "security.yml"
ANALYZE_ACTION = "github/codeql-action/analyze@"
EXPECTED_UPLOAD = "${{ github.event_name == 'merge_group' && 'never' || 'always' }}"


def analyze_upload_verdict(workflow_text: str) -> tuple[bool, str]:
    """(ok, reason) for the codeql analyze step's `with.upload` expression."""
    doc = yaml.safe_load(workflow_text)
    steps = [
        step
        for job in (doc.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
        if str(step.get("uses", "")).startswith(ANALYZE_ACTION)
    ]
    if not steps:
        return False, "no codeql-action/analyze step found"
    for step in steps:
        upload = (step.get("with") or {}).get("upload")
        if upload is None:
            return False, "analyze step has no `with.upload` — the queue lane uploads and races the deleted ref"
        if upload.strip() != EXPECTED_UPLOAD:
            return False, f"analyze step uploads with {upload!r}, expected {EXPECTED_UPLOAD!r}"
    return True, f"{len(steps)} analyze step(s) never upload under merge_group"


def test_innocence_live_security_yml_never_uploads_under_merge_group():
    ok, reason = analyze_upload_verdict(SECURITY_YML.read_text())
    assert ok, reason


def test_guilt_analyze_without_upload_is_flagged():
    text = SECURITY_YML.read_text()
    guilty = text.replace(f"          upload: {EXPECTED_UPLOAD}\n", "")
    assert guilty != text, "fixture must actually remove the upload line"
    ok, reason = analyze_upload_verdict(guilty)
    assert not ok and "no `with.upload`" in reason


def test_guilt_analyze_uploading_always_is_flagged():
    text = SECURITY_YML.read_text()
    guilty = text.replace(f"upload: {EXPECTED_UPLOAD}", "upload: always")
    ok, reason = analyze_upload_verdict(guilty)
    assert not ok and "expected" in reason


@pytest.mark.parametrize("text", ["jobs: {}", "jobs:\n  x:\n    steps:\n      - run: echo\n"])
def test_guilt_missing_analyze_step_is_flagged(text):
    ok, reason = analyze_upload_verdict(text)
    assert not ok and "no codeql-action/analyze" in reason
