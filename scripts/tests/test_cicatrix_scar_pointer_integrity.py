"""
Guilt AND innocence for the `→ dettaglio:` pointers in cicatrix-superscar.md.

PENDING-ARMS 2026-07-30: `cicatrix-superscar.md` opens with "Per il dettaglio
di una scar specifica → segui il ponte" and each family's `→ dettaglio:`
line names which W-numbers live in `cicatrix-scars.md` vs
`cicatrix-scars-archive.md`. A fresh parse (2026-08-09, this file's own
authoring turn) found 27 of 40 cited W-numbers had no `^###`/`^####` body in
the file the pointer named — 11 actually live in the OTHER body file, 16
live in NEITHER (their only detail is the inline prose in the family's own
MEMBRI bullet). A session that trusts the pointer and greps only the named
file concludes the detail does not exist.

This guard is deliberately NOT a rewrite of the missing bodies — writing a
TRAUMA/ANTIBODY/GOTCHA for a scar this test's author did not witness is
fabrication (W65), which is the disease, not the cure. It only asserts the
POINTER tells the truth: every W-number claimed to live in
`cicatrix-scars.md` or `archive` really does have a body there. A W-number
tagged `inline-only` makes no such claim and is exempt by design.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / ".claude" / "rules"
# The two scar BODIES moved out of the auto-injected rules dir (L02-PR1); the
# superscar BRIDGE stayed, because being injected is its job. This guard reads
# both, so it needs both directories, not one.
SCARS_DIR = REPO_ROOT / "docs" / "scars"

# Segment file-labels this guard verifies bodies for. "inline-only" and any
# other free-text label (dates, `scar query "..."` commands) make no
# file-residency claim and are never checked.
CHECKED_FILE_LABELS = {
    "cicatrix-scars.md": "cicatrix-scars.md",
    "archive": "cicatrix-scars-archive.md",
}

_WNUM_RE = re.compile(r"^(W\d+[a-z]?)$")
_HEADING_WNUM_RE = re.compile(r"\bW(\d+)([a-z]?)\b")


def _headings(markdown_text: str) -> set[str]:
    """W-numbers that have their own `### `/`#### ` body in this text."""
    ids: set[str] = set()
    for line in markdown_text.splitlines():
        if line.startswith("### ") or line.startswith("#### "):
            m = _HEADING_WNUM_RE.search(line)
            if m:
                ids.add(f"W{m.group(1)}{m.group(2)}")
    return ids


def find_pointer_violations(bridge_text: str, bodies: dict[str, str]) -> list[str]:
    """
    Return one message per (dettaglio line, W-number) pair that claims
    residency in a named file but has no `###`/`####` body there.

    `bodies` maps the body-file BASENAME (e.g. "cicatrix-scars.md") to its
    full text — the caller reads the files so this function stays pure and
    trivially testable against fabricated fixtures.
    """
    headings_by_file = {name: _headings(text) for name, text in bodies.items()}
    violations: list[str] = []

    for lineno, line in enumerate(bridge_text.splitlines(), start=1):
        if not line.strip().startswith("**→ dettaglio:**"):
            continue
        # Strip the trailing `scar query "..."` / memory-name commands —
        # everything after the first middle-dot separator.
        body = line.split("·")[0]
        for segment in re.split(r"\s\+\s", body):
            seg_match = re.match(r".*?\b(cicatrix-scars\.md|archive)\s*\(([^)]*)\)", segment)
            if not seg_match:
                continue
            file_label, items_str = seg_match.group(1), seg_match.group(2)
            target_basename = CHECKED_FILE_LABELS.get(file_label)
            if target_basename is None:
                continue
            target_headings = headings_by_file.get(target_basename)
            if target_headings is None:
                continue
            for raw_item in items_str.split("/"):
                item = raw_item.strip().strip("*")
                wnum_match = _WNUM_RE.match(item)
                if not wnum_match:
                    continue
                wnum = wnum_match.group(1)
                if wnum not in target_headings:
                    violations.append(
                        f"line {lineno}: pointer claims {wnum} lives in "
                        f"{target_basename}, but no ###/#### body found there"
                    )
    return violations


class TestGuiltAFabricatedPointerIsCaught:
    def test_a_pointer_to_a_body_that_does_not_exist_is_flagged(self) -> None:
        bridge = (
            '**→ dettaglio:** cicatrix-scars.md (W9999) · `scar query "fake"`\n'
        )
        bodies = {
            "cicatrix-scars.md": "### 🐛 W1 (P1): unrelated real scar\n",
            "cicatrix-scars-archive.md": "### ✅ RESOLVED: W9999 — actually lives here\n",
        }
        violations = find_pointer_violations(bridge, bodies)
        assert len(violations) == 1
        assert "W9999" in violations[0]
        assert "cicatrix-scars.md" in violations[0]

    def test_a_pointer_to_a_body_absent_from_either_file_is_flagged(self) -> None:
        bridge = '**→ dettaglio:** archive (W12345) · `scar query "fake"`\n'
        bodies = {
            "cicatrix-scars.md": "### 🐛 W1 (P1): unrelated real scar\n",
            "cicatrix-scars-archive.md": "### 🐛 W2 (P1): also unrelated\n",
        }
        violations = find_pointer_violations(bridge, bodies)
        assert len(violations) == 1
        assert "W12345" in violations[0]
        assert "cicatrix-scars-archive.md" in violations[0]


class TestInnocenceOfTheGuardItself:
    def test_a_correct_pointer_raises_nothing(self) -> None:
        bridge = '**→ dettaglio:** cicatrix-scars.md (W1) + archive (W2) · `scar query "ok"`\n'
        bodies = {
            "cicatrix-scars.md": "### 🐛 W1 (P1): lives here\n",
            "cicatrix-scars-archive.md": "### ✅ RESOLVED: W2 — lives here\n",
        }
        assert find_pointer_violations(bridge, bodies) == []

    def test_inline_only_tag_is_never_checked(self) -> None:
        """A W-number with no ### body anywhere is legitimate under `inline-only`."""
        bridge = '**→ dettaglio:** cicatrix-scars.md (W1) + inline-only (W404) · `scar query "ok"`\n'
        bodies = {
            "cicatrix-scars.md": "### 🐛 W1 (P1): lives here\n",
            "cicatrix-scars-archive.md": "",
        }
        assert find_pointer_violations(bridge, bodies) == []

    def test_a_hash_four_subheading_counts_as_a_real_body(self) -> None:
        """W67b/W67c are `#### ` twin-scar subheadings, not `### ` — both must count."""
        bridge = '**→ dettaglio:** archive (W67b) · `scar query "ok"`\n'
        bodies = {
            "cicatrix-scars.md": "",
            "cicatrix-scars-archive.md": "#### W67b — the follow-up\n",
        }
        assert find_pointer_violations(bridge, bodies) == []

    def test_non_w_number_tokens_are_never_checked(self) -> None:
        """Free-text labels (dates, `P0-cell.env`, `evolver`, ...) are out of scope."""
        bridge = '**→ dettaglio:** cicatrix-scars.md (P0-cell.env) + archive (2026-04-29/evolver) · `scar query "ok"`\n'
        bodies = {"cicatrix-scars.md": "", "cicatrix-scars-archive.md": ""}
        assert find_pointer_violations(bridge, bodies) == []

    def test_a_line_that_is_not_a_dettaglio_pointer_is_ignored(self) -> None:
        bridge = "Some unrelated prose mentioning cicatrix-scars.md (W9999) in passing.\n"
        bodies = {"cicatrix-scars.md": "", "cicatrix-scars-archive.md": ""}
        assert find_pointer_violations(bridge, bodies) == []


class TestTheRealLedgerIsClean:
    """The actual guard run — pins the corrected index, catches the next rot."""

    def test_every_real_dettaglio_pointer_resolves(self) -> None:
        bridge_text = (RULES_DIR / "cicatrix-superscar.md").read_text()
        bodies = {
            "cicatrix-scars.md": (SCARS_DIR / "cicatrix-scars.md").read_text(),
            "cicatrix-scars-archive.md": (SCARS_DIR / "cicatrix-scars-archive.md").read_text(),
        }
        violations = find_pointer_violations(bridge_text, bodies)
        assert violations == [], "\n".join(violations)
