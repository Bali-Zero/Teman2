#!/usr/bin/env python3
"""A runbook section number is a citation target, so a duplicate silently breaks every `§N`
reference pointing at it.

This has now happened twice in two days, both times while FIXING the previous instance: #4557
numbered a new section `6quater`, which the Dependabot section had held since #3381; the repair
renamed it to `6quinquies`, which the Ledger-PRs section already held. Both collisions shipped
green, because nothing checked. A citation that resolves to two different sections is worse than
a dangling one — the reader gets a confident, wrong answer.

The check is deliberately mechanical: heading text before the first '.' must be unique per file.

Scope, stated deliberately (superscar #3 — a guard needs its match surface stated, not implied):
this guard only looks at `##` headings using the single-token ordinal-suffix convention this file's
own docstring documents (`6bis`, `6quater`, ...). `###` numbered headings exist in the corpus in two
other, incompatible shapes — plain integers (`### 1. Title`, e.g. `agent-worktree-broker.md`) and
dotted multi-level numbers (`### 2.3 Title`, e.g. `2026-06-03-residual-ops-hub.md`) — and ARE cited
via `§N.M`. Folding them in needs a second regex for the dotted shape plus a decision on whether
`##`- and `###`-numbered namespaces are shared or separate; that is a real judgment call, not a
"widen the regex" fix, and is deliberately left open (`.claude/skills/modus/PENDING-ARMS.md`,
opened 2026-08-22, "The section-number guard is blind to `###` headings and to code fences").
What IS fixed here: the guard used to also match a `## N.`-shaped line sitting inside a fenced code
block (no live occurrence today, but nothing stopped one from appearing and wrongly accusing an
innocent PR — over-match, same family). Fenced-block lines are now excluded from consideration.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNBOOKS = sorted((REPO / "docs" / "runbooks").glob("*.md"))

_FENCE_RE = re.compile(r"^\s*```")
_HEADING_RE = re.compile(r"^##\s+([0-9]+[a-z]*)\.\s")


def _numbered_headings(text: str) -> list[str]:
    """Heading labels that look like citation targets: '## 6bis. ...' -> '6bis'.

    Prose headings ('## Session discipline') are not citation targets and are skipped, so this
    cannot fire on ordinary editorial headings. Lines inside fenced code blocks (``` ... ```) are
    never headings regardless of their text, so they are skipped too — a code sample showing
    '## 6. example' must never be read as a real, duplicate-checkable section.
    """
    out = []
    in_fence = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
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


def test_fenced_code_block_headings_are_not_counted():
    """Innocence: a '## N.'-shaped line sitting inside a fenced code sample is not a real
    heading and must never trip the duplicate check — it is documentation, not structure."""
    innocent = (
        "## 6bis. real section\n\n"
        "example output:\n```\n## 6bis. this looks the same but is inside a fence\n```\n"
    )
    assert _numbered_headings(innocent) == ["6bis"]


def test_a_real_duplicate_outside_a_fence_still_fails():
    """Guilt, to prove the fence-tracking above didn't accidentally swallow real duplicates too."""
    guilty = (
        "## 6bis. first\n\n"
        "example output:\n```\n## not a heading, just fence text\n```\n\n"
        "## 6bis. second\n"
    )
    labels = _numbered_headings(guilty)
    assert labels == ["6bis", "6bis"], labels
