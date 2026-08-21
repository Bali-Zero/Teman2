#!/usr/bin/env python3
"""A runbook section number is a citation target, so a duplicate silently breaks every `§N`
reference pointing at it.

This has now happened twice in two days, both times while FIXING the previous instance: #4557
numbered a new section `6quater`, which the Dependabot section had held since #3381; the repair
renamed it to `6quinquies`, which the Ledger-PRs section already held. Both collisions shipped
green, because nothing checked. A citation that resolves to two different sections is worse than
a dangling one — the reader gets a confident, wrong answer.

The check is deliberately mechanical: heading text before the first '.' must be unique per file.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNBOOKS = sorted((REPO / "docs" / "runbooks").glob("*.md"))


def _numbered_headings(text: str) -> list[str]:
    """Heading labels that look like citation targets: '## 6bis. ...' -> '6bis'.

    Prose headings ('## Session discipline') are not citation targets and are skipped, so this
    cannot fire on ordinary editorial headings.
    """
    out = []
    for line in text.split("\n"):
        m = re.match(r"^##\s+([0-9]+[a-z]*)\.\s", line)
        if m:
            out.append(m.group(1))
    return out


def test_runbook_section_numbers_are_unique_within_each_file():
    failures = []
    for path in RUNBOOKS:
        labels = _numbered_headings(path.read_text(encoding="utf-8"))
        dupes = sorted({n for n in labels if labels.count(n) > 1})
        if dupes:
            failures.append(f"{path.relative_to(REPO)}: duplicated section numbers {dupes}")
    assert not failures, (
        "a duplicated section number breaks every citation that points at it:\n  "
        + "\n  ".join(failures)
    )


def test_the_check_can_actually_fail():
    """Innocence is proven by the suite above passing on the real tree; guilt needs a fixture,
    or this guard could be vacuous (it would pass on a file with no numbered headings at all)."""
    guilty = "## 6bis. first\n\ntext\n\n## 6bis. second\n"
    labels = _numbered_headings(guilty)
    assert labels == ["6bis", "6bis"], labels
    innocent = "## 6bis. first\n\n## 6ter. second\n\n## Session discipline\n"
    assert _numbered_headings(innocent) == ["6bis", "6ter"]


def test_at_least_one_runbook_carries_numbered_headings():
    """Guards against the parser silently matching nothing (then uniqueness is trivially true)."""
    total = sum(len(_numbered_headings(p.read_text(encoding="utf-8"))) for p in RUNBOOKS)
    assert total > 0, "parser matched no numbered headings in any runbook — it is probably broken"
