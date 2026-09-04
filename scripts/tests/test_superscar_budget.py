"""
Byte-budget + completeness tripwire for `cicatrix-superscar.md`.

Boot-tax audit (2026-08-21, `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`):
`cicatrix-superscar.md` is loaded in full at every session AND every subagent
start. Measured at 73,854 bytes on disk despite its own header claiming
"~2k token" — it had quietly relapsed into the exact disease its own
docstring says it exists to cure (superscar family #2, "Esiste ≠ Armato":
a artefact that claims to be a thin bridge but is secretly carrying full
TRAUMA/ANTIBODY/GOTCHA paragraphs in its MEMBRI bullet lists instead of
`cicatrix-scars.md`, where the full corpus lives).

This guard is two things, deliberately kept together because they trade off
against each other — shrinking the file is only safe if nothing fell off
the truck on the way down:

1. A byte-budget assertion: `cicatrix-superscar.md` stays <=8192 bytes.
2. A completeness assertion: every `W\\d+[a-z]?` token that appears anywhere
   in `cicatrix-superscar.md` resolves to a real body heading in either
   `cicatrix-scars.md` or `cicatrix-scars-archive.md`.

Deliberately MORE tolerant than the sibling guard
`test_cicatrix_scar_pointer_integrity.py`: that file only recognizes `### `
and `#### ` as heading prefixes, which makes it blind to the `## W<N> — ...`
heading form used by many of the more recent, richer scar entries (W90,
W91, W94, W95, W97, W98, W99, W100, W104, W105, W106, W108, W109, W114,
W115, W116, ...). This guard's job is different — not "does the pointer
line's specific file-claim resolve" but "does the token even exist
somewhere, in any recognized heading form" — so it matches `##`/`###`/`####`
alike. It intentionally does NOT rewrite or judge which FILE a token lives
in (that is `test_cicatrix_scar_pointer_integrity.py`'s job); a token found
in either file satisfies this guard.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / ".claude" / "rules"

SCARS_DIR = REPO_ROOT / "docs" / "scars"

SUPERSCAR = RULES_DIR / "cicatrix-superscar.md"
# The bodies live OUTSIDE `.claude/rules/` since L02-PR1: everything in that
# directory is auto-injected into every session and every subagent, and the two
# bodies were 693 KB of it. The bridge stays there on purpose. This guard still
# reads all three — it just reads them from two places now.
SCARS = SCARS_DIR / "cicatrix-scars.md"
ARCHIVE = SCARS_DIR / "cicatrix-scars-archive.md"

BYTE_BUDGET = 8_192

_WNUM_TOKEN_RE = re.compile(r"\bW\d+[a-z]?\b")
_HEADING_RE = re.compile(r"^#{2,4} ")
_HEADING_WNUM_RE = re.compile(r"(?<![A-Za-z0-9-])W\d+[a-z]?(?![A-Za-z0-9-])")


def tokens_in(text: str) -> set[str]:
    """Every W-number token mentioned anywhere in `text` (MEMBRI bullets,
    prose, cross-family notes — everywhere, not just dettaglio pointers)."""
    return set(_WNUM_TOKEN_RE.findall(text))


def headings_with_wnums(text: str) -> set[str]:
    """The PRIMARY W-number subject of every `##`/`###`/`####` heading line,
    tolerant of the mixed heading-level conventions actually used across
    cicatrix-scars.md and cicatrix-scars-archive.md.

    Only the FIRST W-number token per heading line counts as that heading's
    subject — a heading is free to mention a RELATED scar later in its own
    title prose (e.g. "## W94 — ... + latent W83 twin — 2026-07-11" is W94's
    heading, not W83's), and crediting every number a heading merely mentions
    would repeat the exact guard-over-match / phantom-coverage class of bug
    this corpus itself documents (cicatrix-scars.md W78/W105/W109 lineage:
    judge the ENTITY a heading is about, never any substring it contains)."""
    found: set[str] = set()
    for line in text.splitlines():
        if _HEADING_RE.match(line):
            m = _HEADING_WNUM_RE.search(line)
            if m:
                found.add(m.group(0))
    return found


def missing_tokens(superscar_text: str, body_texts: list[str]) -> list[str]:
    """W-number tokens mentioned in the superscar with no heading anywhere
    in the given body texts. Returns a sorted list (empty = clean)."""
    covered: set[str] = set()
    for body in body_texts:
        covered |= headings_with_wnums(body)
    return sorted(tokens_in(superscar_text) - covered)


class TestGuiltAMissingBodyIsCaught:
    def test_a_token_with_no_heading_anywhere_is_flagged(self) -> None:
        superscar = "**MEMBRI:** W1 (real, has a body) · W99999 (fabricated, no body anywhere).\n"
        bodies = ["### 🐛 W1 (P1): lives here\n"]
        missing = missing_tokens(superscar, bodies)
        assert missing == ["W99999"]

    def test_a_token_only_in_a_hash4_subheading_is_still_missing_if_absent(self) -> None:
        superscar = "**MEMBRI:** W404 (fabricated).\n"
        bodies = ["#### W403 — unrelated twin-scar subheading\n"]
        assert missing_tokens(superscar, bodies) == ["W404"]


class TestInnocenceOfTheGuardItself:
    def test_a_double_hash_heading_counts_as_a_real_body(self) -> None:
        """`## W90 — ...` is a real body — the sibling pointer-integrity
        guard is blind to this form, this guard must not be."""
        superscar = "**MEMBRI:** W90 (ground-truth verifier stantio).\n"
        bodies = ["## W90 — Il ground-truth verifier serve uno snapshot stantio\n"]
        assert missing_tokens(superscar, bodies) == []

    def test_a_triple_hash_heading_counts_as_a_real_body(self) -> None:
        superscar = "**MEMBRI:** W110 (heartbeat sull'organo sbagliato).\n"
        bodies = ["### 🐛 W110 (P1 STRUCTURAL): un residuo non tracciato\n"]
        assert missing_tokens(superscar, bodies) == []

    def test_a_hash4_subheading_counts_as_a_real_body(self) -> None:
        """W67b/W67c are `#### ` twin-scar subheadings."""
        superscar = "**MEMBRI:** W67b (wa-mirror reconnect storm follow-up).\n"
        bodies = ["#### W67b — the loggedOut (401) follow-up\n"]
        assert missing_tokens(superscar, bodies) == []

    def test_a_token_covered_in_the_second_body_file_is_not_flagged(self) -> None:
        superscar = "**MEMBRI:** W47 (archived elsewhere).\n"
        bodies = ["### unrelated\n", "### 🐛 W47 — archived here\n"]
        assert missing_tokens(superscar, bodies) == []

    def test_a_token_mentioned_only_in_prose_not_as_a_heading_subject_is_not_a_false_pass(
        self,
    ) -> None:
        """A W-number cited IN PASSING inside another entry's body (e.g.
        "see also W90") must not silently satisfy coverage for a DIFFERENT
        token that has no heading of its own."""
        superscar = "**MEMBRI:** W12345 (no real body, only cross-referenced elsewhere).\n"
        bodies = ["### 🐛 W1 (P1): mentions W12345 in passing prose, not as a heading\n"]
        assert missing_tokens(superscar, bodies) == ["W12345"]


class TestTheRealLedgerIsClean:
    """The actual guard run — pins the corrected state, catches the next relapse."""

    def test_superscar_stays_under_the_byte_budget(self) -> None:
        size = SUPERSCAR.stat().st_size
        assert size <= BYTE_BUDGET, (
            f"cicatrix-superscar.md is {size} bytes, over the {BYTE_BUDGET}-byte "
            "boot-tax budget (research/operations/2026-08-21-token-ceremony-ci-"
            "system-audit.md). Move any long-form scar body verbatim into "
            "cicatrix-scars.md and leave only a 3-8-word MEMBRI reference here."
        )

    def test_every_wnumber_mentioned_has_a_body_somewhere(self) -> None:
        superscar_text = SUPERSCAR.read_text(encoding="utf-8")
        body_texts = [
            SCARS.read_text(encoding="utf-8"),
            ARCHIVE.read_text(encoding="utf-8"),
        ]
        missing = missing_tokens(superscar_text, body_texts)
        assert missing == [], (
            f"{len(missing)} W-number token(s) mentioned in cicatrix-superscar.md "
            f"have no heading in cicatrix-scars.md or cicatrix-scars-archive.md: "
            f"{missing}. Every scar the bridge names must have a body somewhere — "
            "write it (verbatim, no fabrication) in cicatrix-scars.md before "
            "trimming the bridge's own mention down."
        )

    def test_all_three_cicatrix_files_are_prettier_ignored(self) -> None:
        # Asserted by the file's CURRENT path, not by the directory it used to
        # live in: the bodies moved to docs/scars/ in L02-PR1 and a .prettierignore
        # entry that still names .claude/rules/ would be an entry protecting
        # nothing while reading as protection (superscar #2).
        prettierignore = (REPO_ROOT / ".prettierignore").read_text(encoding="utf-8")
        for rel in (
            ".claude/rules/cicatrix-superscar.md",
            "docs/scars/cicatrix-scars.md",
            "docs/scars/cicatrix-scars-archive.md",
        ):
            assert rel in prettierignore, (
                f"{rel} is not listed in .prettierignore — Prettier "
                "rewrites literal text inside these scar records as markdown "
                "emphasis delimiters (cicatrix-scars.md W112) and silently "
                "corrupts the content."
            )
