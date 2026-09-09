"""Guilt + innocence pins for the `antidotes` ledger-only diet tier (2026-09-09).

The disease: a diff touching ONLY `.claude/skills/modus/PENDING-ARMS.md` (the
harness ledger, >= 9 healer-tick PRs a day) matched the sentinel glob
`.claude/skills/*/*.md` and paid the full antidotes battery — 121 s of unit
tests plus ~100 s of seat corpora — twice, once on the PR and once in the merge
group. The cure adds a second sentinel output, `ledger_only`, gates every
heavy step on it, and runs only the ledger's own readers instead.

These pins are string-level on purpose (no YAML dependency on the runner),
scoped to the `antidotes` job: `collision-matrix-case-folding` has its own
`id: paths` step and its own `relevant` gates, which this tier does not touch.
"""

from __future__ import annotations

import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "immune-enforcement.yml"
LEDGER_PATH = ".claude/skills/modus/PENDING-ARMS.md"
LEDGER_STEP_NAME = "Ledger-only diff: run the ledger's own readers"
RELEVANT_GATE = "steps.paths.outputs.relevant == 'true'"
LEDGER_GUARD = "steps.paths.outputs.ledger_only != 'true'"


def _antidotes_job() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("\n  antidotes:\n")
    end = text.index("\n  collision-matrix-case-folding:\n")
    return text[start:end]


def _ledger_step_block(job: str) -> str:
    marker = f"      - name: \"{LEDGER_STEP_NAME}\"\n"
    assert marker in job, "the ledger-only step is missing from the antidotes job"
    after = job.split(marker, 1)[1]
    return after.split("\n      - name: ", 1)[0]


def test_guilt_every_relevant_gate_in_antidotes_also_honours_ledger_only() -> None:
    job = _antidotes_job()
    offenders = [
        line.strip()
        for line in job.splitlines()
        if "if:" in line and RELEVANT_GATE in line and LEDGER_GUARD not in line
    ]
    assert not offenders, (
        "a heavy step is gated on `relevant` alone and would run on a ledger-only "
        f"diff — add `&& {LEDGER_GUARD}`: {offenders}"
    )
    assert job.count(LEDGER_GUARD) >= 40, "the diet lost most of its gates"


def test_innocence_ledger_step_exists_and_is_gated_on_ledger_only() -> None:
    block = _ledger_step_block(_antidotes_job())
    assert "if: steps.paths.outputs.ledger_only == 'true'" in block


def test_self_maintaining_every_pending_arms_test_is_a_ledger_reader() -> None:
    block = _ledger_step_block(_antidotes_job())
    readers = sorted(
        str(Path(p).relative_to(ROOT))
        for p in glob.glob(str(ROOT / "scripts" / "tests" / "test_pending_arms*.py"))
    )
    assert readers, "no scripts/tests/test_pending_arms*.py found — the glob drifted"
    missing = [r for r in readers if r not in block]
    assert not missing, f"ledger readers not run on a ledger-only diff: {missing}"


def test_sentinel_matches_the_ledger_as_an_entity_and_fails_closed() -> None:
    job = _antidotes_job()
    assert f'LEDGER_PATH="{LEDGER_PATH}"' in job, "sentinel lost the exact ledger path"
    assert 'grep -cxF "$LEDGER_PATH"' in job, "sentinel must match whole lines (entity, not substring)"
    assert "LEDGER_ONLY=false" in job and 'echo "ledger_only=$LEDGER_ONLY"' in job
    # Both SHAs empty (workflow_dispatch) -> stays false: the assignment to true is
    # inside the `-n`/`-n` guard.
    guard = job.index('if [ -n "$LEDGER_BASE_SHA" ] && [ -n "$LEDGER_HEAD_SHA" ]')
    assert job.index("LEDGER_ONLY=true") > guard


def test_guilt_a_deleted_ledger_is_not_a_ledger_only_diff() -> None:
    # kimi-code/k3 (2026-09-09): a diff that DELETES the ledger lists exactly one
    # path, so the count alone says ledger_only=true and the readers pass
    # vacuously (their real-ledger tests skipif). The blob must exist at HEAD.
    job = _antidotes_job()
    assert 'git cat-file -e "$LEDGER_HEAD_SHA:$LEDGER_PATH"' in job
    assert job.index('git cat-file -e "$LEDGER_HEAD_SHA:$LEDGER_PATH"') > job.index("LEDGER_ONLY=true")


def test_collision_job_is_untouched_by_the_tier() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    tail = text[text.index("\n  collision-matrix-case-folding:\n") :]
    assert LEDGER_GUARD not in tail and LEDGER_STEP_NAME not in tail
