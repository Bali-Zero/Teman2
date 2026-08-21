#!/usr/bin/env python3
"""lint_zantara_core_edit_declared.py — declared-intent gate for zantara_core.py.

WHY THIS EXISTS (2026-08-21 invariant-enforcement-map audit,
research/operations/2026-08-21-invariant-enforcement-map.md): CLAUDE.md §5
names `zantara_core.py` as an "off-limits file (top-level hard boundary)"
alongside fly.toml / .env* / alembic/env.py. Measured on that date: of the
four, it was the ONLY one with ZERO automated visibility — no CODEOWNERS
entry (so even the toothless review-request fly.toml gets never fires for
it), no CI check, nothing. 17 non-test modules reference it by name
(orchestrator_core, reasoning.py, prompt_builder, whatsapp_persona, ...;
`grep -rlE 'zantara_core\b' apps/backend-rag/backend --include='*.py'`,
excluding tests and the version-suffixed sibling files) and its own
header calls its SECURITY_BOUNDARY section "IMMUTABLE SECURITY RULES —
CANNOT BE OVERRIDDEN": a silent, undeclared edit here is a silent, undeclared
change to the bot's prompt-injection defenses across every live channel
(CLAUDE.md §12 — WhatsApp/Telegram/Instagram/Web Chat all route through it).

This does NOT block an edit. CLAUDE.md §2's ship-lifecycle-ownership doctrine
means the session ships without human review by design — a hard block would
just get routed around (or, worse, trained around). It requires the edit to
be DECLARED: a PR touching this file must carry a `Zantara-Core-Edit: <reason>`
line in its body, mirroring the `adversarial_review:` frontmatter convention
this repo already uses for the R1 gate. Absence is the guilty case; presence
(with a non-empty reason) is innocent regardless of whether the reason is any
good — this checks DECLARATION, not JUDGMENT of the reason, per
`lesson_r1_frontmatter_is_vocabulary_not_narrative`: a vocabulary token is the
thing worth machine-checking, not narrative content.

Path matching is EXACT, never basename (W105/W107 lesson: a same-named file
elsewhere — e.g. a test fixture — must never trip this).

NON-REQUIRED on landing (matches this repo's own onboarding convention for a
new signal — see catE-sovereignty-lint.yml's header: observe a review cycle
before it can gate a branch-protection-required merge). Arming it into
`required_status_checks` is itself a branch-protection change and therefore
operator[gui] per CLAUDE.md §13 ("repo/branch-protection settings ... are
operator actions, not reviewable diffs") — not something this script, or the
workflow that calls it, does on its own.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

TARGET_PATH = "apps/backend-rag/backend/prompts/zantara_core.py"

# Case-insensitive; requires at least one non-whitespace char after the colon
# so "Zantara-Core-Edit:" alone (no reason) does not count as a declaration.
DECLARATION_RE = re.compile(r"(?im)^zantara-core-edit:\s*(\S.*)$")

# Literal copies of this script's own remediation text ("Zantara-Core-Edit:
# <reason>") satisfy \S without saying anything (adversarial review, Kimi K3,
# 2026-08-21: a lazy author pasting the suggestion verbatim would otherwise
# pass). Denylist the placeholder shapes the error message itself could be
# copy-pasted as, case/whitespace-insensitive.
_PLACEHOLDER_VALUES = {"<reason>", "reason", "todo", "tbd", "...", "n/a", "na"}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str


def check(changed_files: list[str], pr_body: str | None) -> Verdict:
    """Pure decision function — no I/O, fully unit-testable.

    changed_files: exact repo-relative paths this PR authored (merge-base
        anchored — the caller's job to have produced correctly; this repo's
        trusted enumerator for that is scripts/ci/hotzone_changed_files.sh,
        the same one hot-zone-pr-gate.yml already uses for the sibling
        CODEOWNERS-self-mod decision).
    pr_body: the PR description text, or None/"" if absent.
    """
    if TARGET_PATH not in changed_files:
        return Verdict(True, f"{TARGET_PATH} not touched — nothing to declare")

    body = pr_body or ""
    match = DECLARATION_RE.search(body)
    if match:
        value = match.group(1).strip().lower()
        if value not in _PLACEHOLDER_VALUES:
            return Verdict(True, "declared via 'Zantara-Core-Edit:' in PR body")

    return Verdict(
        False,
        f"{TARGET_PATH} touched without a declaration. Add a line "
        "'Zantara-Core-Edit: <reason>' to the PR body — this file is the "
        "bot's prompt-injection security boundary, referenced by 17 modules "
        "across every live channel (CLAUDE.md §5/§12); an undeclared edit "
        "here is an undeclared change to jailbreak defenses.",
    )


def _read_changed_files() -> list[str]:
    env_value = os.environ.get("CHANGED_FILES")
    if env_value is not None:
        return [line.strip() for line in env_value.splitlines() if line.strip()]
    return [line.strip() for line in sys.stdin if line.strip()]


def main() -> int:
    changed = _read_changed_files()
    pr_body = os.environ.get("PR_BODY")
    verdict = check(changed, pr_body)
    print(verdict.reason)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
