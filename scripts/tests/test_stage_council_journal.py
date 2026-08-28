"""Guilt + innocence corpus for scripts/ci/stage_council_journal.py.

WHAT THIS PINS (measured 2026-08-29, before the fix existed): harness-floor.yml's pack-lint step
stages only the pack and the brief into its synthetic /tmp/evidence-check tree, while R9
(evidence_pack_lint.py::check_council_run_gear3) resolves the pack's `council_run:` against the
PACK'S OWN directory. A fully compliant Gear-3 pack — journal committed beside it, two distinct
qualifying review seats in it — therefore lints in CI as "declares no council_run journal". R9 is
phased, so that is a NOTICE today and a hard FAIL for every Gear-3 PR from 2026-09-02.

The two tests that carry the acceptance criterion run the SAME fixture pack through the SAME
staging routine, differing only in whether the staging script runs:

  GUILT     — staged the pre-fix way (pack + brief only): R9 reports a violation post-flip, on a
              pack that is not at fault. This is the reproduced red, frozen.
  INNOCENCE — staged with the script: R9 finds the quorum and returns clean, no notice.

Deleting the script, or making it stage the wrong path, turns the innocence test red. The third
kind of regression — the workflow silently ceasing to CALL the script — is invisible to a pytest
that only exercises the script (the exact gap test_harness_floor_brief_diff_membership.sh's round-2
correction was written about), so the wiring is pinned statically against the YAML as well.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ci" / "stage_council_journal.py"
HARNESS_FLOOR = REPO / ".github" / "workflows" / "harness-floor.yml"

sys.path.insert(0, str(REPO / "scripts"))
from evidence_pack_lint import (  # noqa: E402
    R9_R11_ENFORCEMENT_DATE,
    check_council_run_gear3,
)

#: The pack dir shape a real per-PR pack uses (evidence/<YYYY-MM>/<slug>/).
PACK_DIR_REL = "evidence/2026-08/agent-test-council-run-staging"

#: Two DISTINCT seats from COUNCIL_REVIEW_SEATS, both ok:true — exactly quorum.
JOURNAL_LINES = (
    {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": "2026-08-29T10:00:00Z"},
    {"seat": "kimi-code/k3", "role": "review", "ok": True, "ts": "2026-08-29T11:00:00Z"},
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _git_show_bytes(repo: Path, sha: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{path}"], capture_output=True, check=True
    )
    return proc.stdout


def _make_repo(tmp_path: Path, council_run: str, journal_at: str | None) -> tuple[Path, str]:
    """A throwaway repo carrying a Gear-3 pack that declares `council_run: <council_run>`.

    `journal_at` is the pack-dir-relative path the journal is actually committed at, or None to
    commit no journal at all (a pack declaring a file it never authored).
    """
    repo = tmp_path / "repo"
    pack_dir = repo / PACK_DIR_REL
    pack_dir.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "corpus@example.invalid")
    _git(repo, "config", "user.name", "corpus")

    (pack_dir / "pack.yml").write_text(
        f"brief_ref: evidence/brief.yml\ncouncil_run: {council_run}\ngear: 3\n", encoding="utf-8"
    )
    (pack_dir / "brief.yml").write_text("gear: 3\n", encoding="utf-8")
    if journal_at is not None:
        journal = pack_dir / journal_at
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(
            "".join(json.dumps(entry) + "\n" for entry in JOURNAL_LINES), encoding="utf-8"
        )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "corpus: gear-3 pack with a council journal")
    return repo, _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_script(repo: Path, staged_pack: Path, source_path: str, head_sha: str):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--staged-pack",
            str(staged_pack),
            "--source-path",
            source_path,
            "--head-sha",
            head_sha,
            "--repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
    )


def _stage_like_ci(repo: Path, head_sha: str, staging_root: Path, run_the_fix: bool) -> Path:
    """Reproduces harness-floor.yml's pack-lint staging and returns the staged pack dir.

    Pre-fix, that is exactly two files under the canonical evidence/{pack,brief}.yml names,
    regardless of where the real pack lives — the two `git show` / `cp` lines in the workflow.
    """
    staged = staging_root / "evidence"
    staged.mkdir(parents=True)
    pack_rel = f"{PACK_DIR_REL}/pack.yml"
    (staged / "pack.yml").write_bytes(_git_show_bytes(repo, head_sha, pack_rel))
    (staged / "brief.yml").write_bytes(
        _git_show_bytes(repo, head_sha, f"{PACK_DIR_REL}/brief.yml")
    )
    if run_the_fix:
        proc = _run_script(repo, staged / "pack.yml", pack_rel, head_sha)
        assert proc.returncode == 0, f"staging script failed: {proc.stdout}{proc.stderr}"
    return staged


def _verdict(staged: Path):
    import yaml

    pack = yaml.safe_load((staged / "pack.yml").read_text(encoding="utf-8"))
    return check_council_run_gear3(pack, staged, gear=3, today=R9_R11_ENFORCEMENT_DATE)


# ---- the acceptance pair ---------------------------------------------------


def test_guilt_pre_fix_staging_fails_a_compliant_pack_post_flip(tmp_path):
    """GUILT: staged the pre-fix way, a pack whose journal carries a real quorum is a hard R9
    violation on the enforcement date — the defect this PR removes, frozen so it cannot return."""
    repo, head_sha = _make_repo(tmp_path, "council-journal.jsonl", "council-journal.jsonl")
    staged = _stage_like_ci(repo, head_sha, tmp_path / "ci-pre-fix", run_the_fix=False)

    assert not (staged / "council-journal.jsonl").exists()
    violations, notice = _verdict(staged)
    assert violations and "council_run" in violations[0]
    assert notice is None


def test_innocence_staged_journal_clears_a_compliant_pack_post_flip(tmp_path):
    """INNOCENCE: the same pack, staged with the script, reaches R9 with its journal and passes
    on the enforcement date — no violation, no notice."""
    repo, head_sha = _make_repo(tmp_path, "council-journal.jsonl", "council-journal.jsonl")
    staged = _stage_like_ci(repo, head_sha, tmp_path / "ci-fixed", run_the_fix=True)

    staged_journal = staged / "council-journal.jsonl"
    assert staged_journal.is_file()
    assert json.loads(staged_journal.read_text(encoding="utf-8").splitlines()[0])["seat"] == (
        JOURNAL_LINES[0]["seat"]
    )
    assert _verdict(staged) == ([], None)


# ---- what the script refuses to stage --------------------------------------


def test_nested_council_run_is_staged_with_its_parent_directories(tmp_path):
    """A `council_run:` naming a subdirectory of the pack dir stages at that same relative path —
    R9 resolves it there, so the staged tree must reproduce the nesting, not flatten it."""
    repo, head_sha = _make_repo(tmp_path, "council/journal.jsonl", "council/journal.jsonl")
    staged = _stage_like_ci(repo, head_sha, tmp_path / "ci", run_the_fix=True)

    assert (staged / "council" / "journal.jsonl").is_file()
    assert _verdict(staged) == ([], None)


@pytest.mark.parametrize(
    "council_run", ["/etc/passwd", "../../../etc/passwd", "../sibling/journal.jsonl"]
)
def test_absolute_or_escaping_council_run_stages_nothing(tmp_path, council_run):
    """GUILT: R9 refuses an absolute or pack-dir-escaping `council_run` itself. Staging one would
    launder a path-confinement violation into a pass, so the script declines and says why — the
    pack stays a violation, and nothing is written outside the staged pack dir."""
    repo, head_sha = _make_repo(tmp_path, council_run, "council-journal.jsonl")
    staging_root = tmp_path / "ci"
    staged = _stage_like_ci(repo, head_sha, staging_root, run_the_fix=True)

    assert sorted(p.name for p in staged.iterdir()) == ["brief.yml", "pack.yml"]
    violations, _ = _verdict(staged)
    assert violations and "council_run" in violations[0]


def test_declared_but_uncommitted_journal_stages_nothing_and_exits_clean(tmp_path):
    """GUILT: a pack declaring a journal it never committed is precisely what R9 exists to catch.
    The script exits 0 (it renders no verdict) having staged nothing, and R9 does the judging."""
    repo, head_sha = _make_repo(tmp_path, "council-journal.jsonl", journal_at=None)
    staged = _stage_like_ci(repo, head_sha, tmp_path / "ci", run_the_fix=True)

    assert not (staged / "council-journal.jsonl").exists()
    violations, _ = _verdict(staged)
    assert violations and "council_run" in violations[0]


def test_pack_declaring_no_council_run_stages_nothing(tmp_path):
    """A pack with no `council_run:` at all is left exactly as staged — the script never invents
    a journal for it."""
    repo = tmp_path / "repo"
    pack_dir = repo / PACK_DIR_REL
    pack_dir.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "corpus@example.invalid")
    _git(repo, "config", "user.name", "corpus")
    (pack_dir / "pack.yml").write_text("brief_ref: evidence/brief.yml\ngear: 3\n", encoding="utf-8")
    (pack_dir / "brief.yml").write_text("gear: 3\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "corpus: gear-3 pack with no council_run")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    staged = _stage_like_ci(repo, head_sha, tmp_path / "ci", run_the_fix=True)
    assert sorted(p.name for p in staged.iterdir()) == ["brief.yml", "pack.yml"]


# ---- the wiring, pinned against the workflow itself ------------------------


def test_harness_floor_stages_the_council_journal_before_running_the_pack_lint():
    """The corpus above exercises the script; only this pins that harness-floor.yml still CALLS
    it, with the staged pack it is about to lint, BEFORE linting it. A workflow that stops
    invoking the script would leave every test above green while restoring the whole defect."""
    text = HARNESS_FLOOR.read_text(encoding="utf-8")

    invocation = "python3 scripts/ci/stage_council_journal.py"
    assert invocation in text
    for flag in (
        "--staged-pack /tmp/evidence-check/evidence/pack.yml",
        '--source-path "$PACK_PATH"',
        '--head-sha "$HEAD_SHA"',
    ):
        assert flag in text, f"harness-floor.yml no longer passes {flag}"

    assert text.index(invocation) < text.index("--repo-root /tmp/evidence-check")
