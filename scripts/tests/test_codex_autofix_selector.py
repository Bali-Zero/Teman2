"""Guilt+innocence for the codex-nightly-autofix-ci.sh eligibility filter.

Recursion bite 2026-07-06: the generator chased its own codex/auto-fix-ci-*
branches — each failed fix PR became the next cycle's target (#2063 -> #2064
-> #2065, hourly, bounded only by the daily cap). Root of the chain was a
failing dependabot mega-bump, whose branch is force-push mutable and thus a
fragile base for a fix PR.

The filter must never select:
  - its own output branches (codex/auto-fix-ci-*)  [recursion brake]
  - dependabot/* branches (mutable base)           [fragile-base guard]
and must still select a genuine feature-branch failure (innocence).

Runs the REAL script in CODEX_AUTOFIX_DRY_RUN=1 with injected failed-runs
JSON — no gh, no codex, no network, no git mutations (dry-run exits before
any checkout).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "codex" / "codex-nightly-autofix-ci.sh"
)


def _mkrun(
    run_id: int,
    branch: str,
    name: str = "Tests & Coverage",
    *,
    actor: str = "Balizero1987",
    triggering_actor: str | None = None,
    event: str = "pull_request",
    head_repository: str = "Bali-Zero/Teman2",
) -> dict:
    return {
        "databaseId": run_id,
        "name": name,
        "headBranch": branch,
        "headSha": "a" * 40,
        "displayTitle": f"run on {branch}",
        "createdAt": "2026-07-06T17:00:00Z",
        "event": event,
        "actor": {"login": actor},
        "triggering_actor": {"login": triggering_actor or actor},
        "head_repository": {"full_name": head_repository},
    }


def _run(
    tmp_path: Path,
    runs: list[dict],
    *,
    api_metadata: dict | None = None,
    api_failure: bool = False,
) -> subprocess.CompletedProcess:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(exist_ok=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        "#!/bin/sh\n"
        'if [ "${CODEX_TEST_GH_API_FAILURE:-0}" = "1" ]; then exit 1; fi\n'
        'printf "%s\\n" "$CODEX_TEST_GH_API_RESPONSE"\n'
    )
    fake_gh.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "CODEX_AUTOFIX_DRY_RUN": "1",
            "CODEX_AUTOFIX_FAILED_RUNS_JSON": json.dumps(runs),
            "CODEX_AUTOFIX_STATE_DIR": str(tmp_path / "state"),
            "CODEX_AUTOFIX_LOG_DIR": str(tmp_path / "logs"),
            "CODEX_AUTOFIX_REPO_ROOT": str(repo_root),
            # Point at a nonexistent lib so the HOME automation lib is never sourced.
            "CODEX_AUTOMATION_LIB": str(tmp_path / "no-such-lib.sh"),
            # The injected records carry live-API-equivalent provenance, so the
            # script must never need a network lookup during this hermetic test.
            "CODEX_AUTOFIX_CANONICAL_REPO": "Bali-Zero/Teman2",
            "CODEX_TEST_GH_API_RESPONSE": json.dumps(api_metadata or {}),
            "CODEX_TEST_GH_API_FAILURE": "1" if api_failure else "0",
            "CODEX_AUTOFIX_GH_BIN": str(fake_gh),
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _api_record(run: dict, *, sha: str | None = None) -> dict:
    """REST run record equivalent to the provenance fields the selector needs."""
    return {
        "actor": run["actor"],
        "triggering_actor": run["triggering_actor"],
        "event": run["event"],
        "head_repository": run["head_repository"],
        "head_branch": run["headBranch"],
        "head_sha": sha or run["headSha"],
    }


def _strip_list_provenance(run: dict) -> dict:
    """Simulate gh run list, which does not provide actor/fork provenance."""
    listing = run.copy()
    listing.pop("actor")
    listing.pop("triggering_actor")
    listing.pop("head_repository")
    return listing


def test_guilt_own_autofix_branch_never_selected(tmp_path):
    """A failure on codex/auto-fix-ci-* must be invisible (recursion brake)."""
    proc = _run(tmp_path, [_mkrun(111, "codex/auto-fix-ci-99999")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout
    assert "selected run_id" not in proc.stdout


def test_guilt_dependabot_branch_never_selected(tmp_path):
    """A failure on dependabot/* must be invisible (mutable fix base)."""
    proc = _run(
        tmp_path, [_mkrun(222, "dependabot/pip/apps/backend-rag/minor-and-patch-x")]
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_main_branch_never_selected(tmp_path):
    """Pre-existing guard pinned: main failures are not auto-fix targets."""
    proc = _run(tmp_path, [_mkrun(233, "main")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_innocence_feature_branch_selected(tmp_path):
    """A genuine feature-branch failure must still be selected."""
    proc = _run(tmp_path, [_mkrun(333, "agent/air-m5/feature/x")])
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=333" in proc.stdout


def test_innocence_real_failure_behind_own_branch_selected(tmp_path):
    """Own-branch noise ahead in the list must not shadow a real failure."""
    proc = _run(
        tmp_path,
        [
            _mkrun(444, "codex/auto-fix-ci-123"),
            _mkrun(555, "feature/real-work"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=555" in proc.stdout


def test_guilt_untrusted_run_actor_never_selected(tmp_path):
    """A same-repo branch by an unapproved actor is not an unattended target."""
    proc = _run(tmp_path, [_mkrun(666, "feature/untrusted", actor="outsider")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_rerun_cannot_launder_an_untrusted_original_actor(tmp_path):
    """A trusted user clicking rerun does not bless someone else's failed run."""
    proc = _run(
        tmp_path,
        [
            _mkrun(
                667,
                "feature/rerun-laundering",
                actor="Balizero1987",
                triggering_actor="outsider",
            )
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_fork_run_never_selected(tmp_path):
    """The failed run must originate from this exact repository, not a fork."""
    proc = _run(
        tmp_path,
        [_mkrun(668, "feature/fork", head_repository="outsider/Teman2")],
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_unsanctioned_event_never_selected(tmp_path):
    """Only push and pull_request failures are approved unattended inputs."""
    proc = _run(
        tmp_path,
        [_mkrun(669, "feature/workflow-dispatch", event="workflow_dispatch")],
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_unapproved_branch_namespace_never_selected(tmp_path):
    """Actor provenance does not turn an arbitrary branch namespace into input."""
    proc = _run(tmp_path, [_mkrun(670, "release/unattended-target")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_innocence_push_from_trusted_actor_is_selected(tmp_path):
    """A direct, same-repo trusted feature push remains eligible."""
    proc = _run(tmp_path, [_mkrun(671, "fix/real-ci", event="push")])
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=671" in proc.stdout


def test_innocence_rest_provenance_is_resolved_before_selection(tmp_path):
    """Real gh run list lacks actor/fork data; REST metadata restores it safely."""
    run = _mkrun(672, "feature/rest-provenance")
    proc = _run(
        tmp_path,
        [_strip_list_provenance(run)],
        api_metadata=_api_record(run),
    )
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=672" in proc.stdout


def test_guilt_provenance_api_failure_never_selects_a_run(tmp_path):
    """Metadata ambiguity is fail-closed; an API outage cannot widen the target set."""
    run = _mkrun(673, "feature/api-outage")
    proc = _run(tmp_path, [_strip_list_provenance(run)], api_failure=True)
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_rest_metadata_sha_mismatch_never_selects_a_run(tmp_path):
    """The branch fetched for repair must be the exact commit whose run failed."""
    run = _mkrun(674, "feature/sha-race")
    proc = _run(
        tmp_path,
        [_strip_list_provenance(run)],
        api_metadata=_api_record(run, sha="b" * 40),
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout
