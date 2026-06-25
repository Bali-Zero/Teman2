#!/usr/bin/env python3
"""scar_test for W82 — content-freshness-sentinel UNDER-match (superscar #3 twin).

THE LOOP THAT FEEDS ITSELF: W82 was registered in verify_the_verifiers_gates.yaml
as `prose_only: true` → the meta-verifier reported it WARN ("Loop-B debt: scar
documented but no executable gate yet"). This file is the answer to that WARN —
the prose scar promoted to an executable gate. (Self-loop plan Anello 1, the
natural loop in action: a visible debt asking for a test gets one.)

WHAT W82 IS (verified verbatim on origin/main 2026-06-23):
  apps/mouth/src/content/content-freshness-sentinel.test.ts is the dead-man's
  switch between published MDX and the regulatory ground-truth ledger. Its core,
  staleHits(), matches a known-stale fact by PURE SUBSTRING:
      if (!lines[i].toLowerCase().includes(needle)) continue;   // line 125
  Two structural holes (both in the scar, both confirmed in code):
    (A) substring, not entity — the SAME KBLI code in a table cell or reworded
        ("perhotelan 55110", "55110 (hotel)") slips past `"hotels (55110)"`.
    (B) translations are structurally skipped — TRANSLATION_SUFFIX excludes
        .it/.id/.ru/... so a stale fact in a translated file stays GREEN.

WHY THIS TEST PASSES (exit 0) WHILE THE BUG IS UNFIXED — read carefully:
  A `scar_test` is GREEN = "the disease is under control / captured", NOT "the
  disease doesn't exist". W82's ANTIBODY (a fact-based sentinel) is a designed-
  but-NOT-armed operator firebreak (Antonello, 2026-06-16) — we must NOT arm it
  here. So this gate does the honest thing the Loop-B allows WITHOUT crossing the
  firebreak: it PINS the documented current (broken) contract and asserts the
  under-match still behaves exactly as the scar describes.
    - GUILT-of-the-bug (the under-match IS real): a reworded / table / translated
      stale fact is NOT caught by the substring matcher  → asserted TRUE.
    - INNOCENCE (the matcher still catches what it claims to): the exact literal
      stale phrase IS caught                              → asserted TRUE.
  Consequence — the self-healing trip-wire: when someone ARMS the fact-based
  sentinel (the firebreak lifts), the under-match will STOP happening, this test
  will FAIL, and the meta-verifier turns this gate DISARMED — a loud, deterministic
  "the W82 contract changed: update this gate / promote the scar to RESOLVED".
  A green prose_only debt becomes a tripwire that fires the moment the cure lands.

  python3 infra/scar-gates/test_W82_content_freshness_undermatch.py
Exit 0 = the documented W82 contract still holds (bug present & captured).
Exit 1 = the contract changed (likely the fact-based fix landed → update the gate).

Reference: cicatrix-scars.md W82 · research/operations/2026-06-23-self-loop-implementation-plan.md
"""
from __future__ import annotations
import re
import sys

# --- Faithful re-implementation of the sentinel's substring matcher ----------
# Mirrors staleHits() (content-freshness-sentinel.test.ts:119-135) verbatim in
# its decisive behaviour: case-insensitive SUBSTRING containment per line, with a
# migration-context excuse window. We test the MATCHER's contract, not the file IO.
MIGRATION_CONTEXT = (
    "superseded", "old kbli 2020", "moved to the 15th", "no longer", "replaced by",
)
TRANSLATION_SUFFIX = re.compile(r"\.(it|id|ru|fr|de|es|nl|ja|zh|ko|pt)\.mdx$")


def stale_hits(content: str, pattern: str) -> list[int]:
    """Substring matcher, faithful to staleHits() in the .test.ts."""
    lines = content.split("\n")
    needle = pattern.lower()
    hits: list[int] = []
    for i, line in enumerate(lines):
        if needle not in line.lower():
            continue
        window = " ".join(
            [lines[i - 1] if i > 0 else "", line, lines[i + 1] if i + 1 < len(lines) else ""]
        ).lower()
        if not any(cue in window for cue in MIGRATION_CONTEXT):
            hits.append(i + 1)
    return hits


def is_audited(filename: str) -> bool:
    """The sentinel only audits English canonical .mdx (collectMdx skips translations)."""
    return filename.endswith(".mdx") and not TRANSLATION_SUFFIX.search(filename)


def main() -> int:
    fails = 0

    def check(name: str, got: bool, expect: bool) -> None:
        nonlocal fails
        ok = got == expect
        if not ok:
            fails += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] got={got!s:5} expect={expect!s:5} | {name}")

    # The canonical stale pattern from the scar: "hotels (55110)".
    STALE = "hotels (55110)"

    # --- INNOCENCE: the matcher DOES catch the exact literal it watches ---------
    exact = "Tourism: hotels (55110) remain open to foreign ownership."
    check("matcher catches the exact literal stale phrase",
          len(stale_hits(exact, STALE)) > 0, True)

    # --- INNOCENCE: a legitimate migration note is excused (not a false alarm) --
    excused = "Note: hotels (55110) — superseded, see KBLI 2025 mapping below."
    check("migration-context note is excused (no false stale-hit)",
          len(stale_hits(excused, STALE)) == 0, True)

    # --- GUILT of W82 (A): the SAME fact reworded / in a table is NOT caught -----
    # This is the under-match. While the bug lives, these MUST slip past (hits==0).
    reworded = "Perhotelan 55110 tetap terbuka untuk kepemilikan asing."  # ID rewording
    check("[under-match A] reworded same KBLI code slips past substring matcher",
          len(stale_hits(reworded, STALE)) == 0, True)

    table_cell = "| Sector | Code |\n| Hotel  | 55110 |"  # code in a table cell, no "hotels ("
    check("[under-match A] KBLI code in a table cell slips past",
          len(stale_hits(table_cell, STALE)) == 0, True)

    # --- GUILT of W82 (B): translations are structurally not audited ------------
    # A stale fact in a translated file is invisible to the sentinel by design.
    check("[under-match B] translated .id.mdx is NOT audited (stale fact invisible)",
          is_audited("retirement-visa.id.mdx"), False)
    check("[under-match B] translated .ru.mdx is NOT audited",
          is_audited("lkpm-deadline.ru.mdx"), False)
    # control: the English canonical IS audited
    check("[control] English canonical .mdx IS audited",
          is_audited("retirement-visa.mdx"), True)

    total = 7
    print(f"\n=== W82 under-match contract: {'HOLDS — ALL ' + str(total) + ' PASS (bug present & captured)' if not fails else str(fails) + '/' + str(total) + ' FAIL — contract CHANGED (fact-based fix landed? update gate)'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
