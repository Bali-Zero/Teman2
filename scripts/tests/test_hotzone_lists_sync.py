"""Guilt+innocence proof that HOTZONE_PATTERNS and hot-zone-pr-gate.yml agree.

scripts/evidence_pack_lint.py::HOTZONE_PATTERNS is a DECLARED duplicate of the
bash `case` block in .github/workflows/hot-zone-pr-gate.yml (bash `case`
syntax is not importable from Python — see the comment beside each list). The
two are kept in sync by hand; this test is the mechanical check that catches
drift between them, including the S5 egress-wrapper entries
(docs/specs/2026-09-27-evidence-pack-fixed-point.md).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
WORKFLOW = REPO / ".github" / "workflows" / "hot-zone-pr-gate.yml"

sys.path.insert(0, str(SCRIPTS))
from evidence_pack_lint import HOTZONE_PATTERNS, compute_floor  # noqa: E402

# S5 (2026-09-27): the external-seat egress paths that must appear on BOTH
# lists. This is the guilt+innocence corpus for the sync check below.
S5_EGRESS_PATHS = (
    ".claude/scripts/codex-spalla.sh",
    "scripts/lib/spalla_redact.sh",
    ".claude/hooks/codex-spalla-trigger.sh",
    "scripts/codex_tri_llm_review.py",
    "scripts/review_gate_run.sh",
    "scripts/_redact_pii.py",
    "infra/workflows/second-army.js",
)


def _workflow_case_patterns() -> list[str]:
    """Extract the bash `case "$f" in ... )` pattern list from the workflow.

    Innocence: parses the literal block between `case "$f" in` and the first
    `HOTZONE_MATCH="true"` line that closes it — no regex over the whole file
    that could accidentally match an unrelated case block.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index('case "$f" in')
    end = text.index('HOTZONE_MATCH="true"', start)
    block = text[start + len('case "$f" in') : end]
    # Each continuation line ends in "|\" except the last, which ends in ")".
    raw = block.replace("\\\n", "\n")
    patterns: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.rstrip("|")
        line = re.sub(r"\)\s*$", "", line)
        if line:
            patterns.append(line)
    return patterns


def test_hotzone_lists_are_identical_sets() -> None:
    py_set = set(HOTZONE_PATTERNS)
    yaml_set = set(_workflow_case_patterns())
    missing_from_yaml = py_set - yaml_set
    missing_from_py = yaml_set - py_set
    assert not missing_from_yaml, (
        f"scripts/evidence_pack_lint.py::HOTZONE_PATTERNS has entries missing "
        f"from .github/workflows/hot-zone-pr-gate.yml's case block: "
        f"{sorted(missing_from_yaml)}"
    )
    assert not missing_from_py, (
        f".github/workflows/hot-zone-pr-gate.yml's case block has entries "
        f"missing from scripts/evidence_pack_lint.py::HOTZONE_PATTERNS: "
        f"{sorted(missing_from_py)}"
    )


def test_s5_egress_paths_present_on_both_lists() -> None:
    """Guilt case: every S5 egress path must be hot-zone on BOTH lists."""
    py_set = set(HOTZONE_PATTERNS)
    yaml_set = set(_workflow_case_patterns())
    for path in S5_EGRESS_PATHS:
        assert path in py_set, f"{path} missing from HOTZONE_PATTERNS"
        assert path in yaml_set, f"{path} missing from hot-zone-pr-gate.yml case block"


def test_an_unrelated_path_is_not_hotzone() -> None:
    """Innocence case: an ordinary content path stays off both lists, and
    the real matcher (fnmatch via compute_floor, not set membership — a
    literal-membership check alone would say nothing about a glob entry
    like a directory pattern) floors it at 1, not 3."""
    innocent = "docs/CLAUDE.md"
    py_set = set(HOTZONE_PATTERNS)
    yaml_set = set(_workflow_case_patterns())
    assert innocent not in py_set
    assert innocent not in yaml_set
    assert compute_floor([innocent]) == 1


def test_s5_egress_paths_floor_at_3_via_compute_floor() -> None:
    """Guilt case via the REAL matcher (fnmatch, not set membership): each
    S5 path floors this repo's own compute_floor() at 3 in isolation."""
    for path in S5_EGRESS_PATHS:
        assert compute_floor([path]) == 3, f"{path} does not floor at 3"
