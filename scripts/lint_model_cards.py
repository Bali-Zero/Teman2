#!/usr/bin/env python3
"""lint_model_cards.py — PR3a (2026-09-18), mandate MANDATE-builder.md PR3 section
(split by the 2026-09-18 addendum; this lint's CI consumer is PR3c, a separate hot-zone
PR that only has to NAME scripts/tests/test_lint_model_cards.py).

For every arsenal card under docs/arsenal/cards/*.md:

  RULE 1 (tagged claims) — every top-level markdown bullet (`- ` or `* ` at column 0) in
    the body is tagged `SELF:`, `MEASURED:` or `PUBLIC:` immediately after the marker.
    Known, accepted limit: an INDENTED/nested bullet is not itself swept (neither required
    to be tagged nor validated if it is) — write cards flat, one level of claim bullets.

  RULE 2 (MEASURED: is checkable) — a `MEASURED:` bullet names a backtick-quoted path
    right after the tag, and that path either:
      * exists in the repo (resolved from repo root), or
      * is shaped like a memory slug:
        `{decision|discovery|lesson|project|fact|reference}_words_YYYY_MM_DD[.md]`
        (the exact pattern this repo's own memory files use — see MEMORY_SLUG_RE).
    The memory directory itself (~/.claude/projects/<cwd-slug>/memory/, resolved the same
    way scripts/context_budget_audit.py's `_memory_slug()` does) is local, per-user,
    per-machine — it never exists on a CI runner. A memory-slug MEASURED: claim is
    therefore FORMAT-checked only, never existence-checked, or this rule would be
    permanently unsatisfiable in CI (verified 2026-09-18, not speculative).

  RULE 3 (freshness) — frontmatter `date: YYYY-MM-DD` must be within FRESHNESS_DAYS (30)
    of the day the lint runs, else FAIL "expired". A card that ages past its own claimed
    freshness is a stale claim, not a false one — re-date it after re-checking it.

  RULE 4 (roles) — frontmatter `roles_allowed:` is a non-empty, comma-separated subset of
    ALLOWED_ROLES (builder, refuter, gate, quorum, pii-lane, grunt, judge).

  RULE 5 (seat resolves) — frontmatter `seat:` must resolve to a known vendor family via
    scripts/dynamic_workflow.py's OWN FAMILY_MAP/_SEAT_ALIASES/_seat_family, imported
    READ-ONLY (this lint only imports already-defined names; it never edits that file or
    its tests — PR3a's mandate explicitly forbids that). A card whose seat: is not a real,
    wired seat is not describing anything the dispatcher can actually route to.

Frontmatter shape — this repo's existing bare `^key:.*$` idiom (see
scripts/dynamic_workflow.py's SEAT_LINE_RE/SHA_LINE_RE), not real YAML, no parser
dependency: `seat:`, `date:` and `roles_allowed:` are matched as line-anchored patterns
anywhere in the file (conventionally the first three lines, before the body).

    python3 scripts/lint_model_cards.py [path ...]

Default sweep (no argv): docs/arsenal/cards/*.md. Exit 0 clean, 1 violations, 2 blind scan
(default sweep traversed zero files — cicatrix #2/#4, "exists != armed"). The same
zero-scan rule binds an EXPLICIT target too (PR3c, 2026-09-19): a nonexistent path or
an existing directory that yields zero .md files both blind-scan at exit 2; only an
explicit FILE of the wrong suffix stays legitimately off-scope and exits 0.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GLOB_DIR = "docs/arsenal/cards"
DEFAULT_GLOB_PATTERN = "*.md"
FRESHNESS_DAYS = 30
ALLOWED_ROLES = {"builder", "refuter", "gate", "quorum", "pii-lane", "grunt", "judge"}

SEAT_FM_RE = re.compile(r"^seat:\s*(.+?)\s*$", re.MULTILINE)
DATE_FM_RE = re.compile(r"^date:\s*(\S+)\s*$", re.MULTILINE)
ROLES_FM_RE = re.compile(r"^roles_allowed:\s*(.+?)\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^[-*]\s+(.*)$", re.MULTILINE)
TAGGED_BULLET_RE = re.compile(r"^(SELF|MEASURED|PUBLIC):\s*(.*)$")
MEASURED_PATH_RE = re.compile(r"^MEASURED:\s*`([^`]+)`")
MEMORY_SLUG_RE = re.compile(
    r"^(?:decision|discovery|lesson|project|fact|reference)_[a-z0-9_]+_\d{4}_\d{2}_\d{2}(?:\.md)?$"
)


def _load_dynamic_workflow():
    """Read-only import of scripts/dynamic_workflow.py for FAMILY_MAP/_seat_family.
    Safe: that module's only top-level side effects are its own self-locating sys.path
    setup and importing _redact_pii / scripts.lib.codex_seat (both existing, already-
    imported-elsewhere repo modules); real work happens only under its own
    `if __name__ == "__main__": main()` guard (verified 2026-09-18)."""
    path = REPO_ROOT / "scripts" / "dynamic_workflow.py"
    spec = importlib.util.spec_from_file_location("dynamic_workflow_ro", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_violations(path: Path, dw, today: date | None = None) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    today = today or date.today()
    violations: list[tuple[int, str]] = []

    seat_m = SEAT_FM_RE.search(text)
    if not seat_m:
        violations.append((1, "missing frontmatter `seat:` line"))
    elif dw._seat_family(seat_m.group(1)) is None:
        violations.append(
            (1, f"seat `{seat_m.group(1)}` does not resolve via FAMILY_MAP/_SEAT_ALIASES")
        )

    date_m = DATE_FM_RE.search(text)
    if not date_m:
        violations.append((1, "missing frontmatter `date: YYYY-MM-DD` line"))
    else:
        try:
            card_date = datetime.strptime(date_m.group(1), "%Y-%m-%d").date()
        except ValueError:
            violations.append((1, f"unparseable frontmatter date `{date_m.group(1)}`"))
        else:
            age = (today - card_date).days
            if age > FRESHNESS_DAYS:
                violations.append(
                    (1, f"expired: date {date_m.group(1)} is {age}d old (> {FRESHNESS_DAYS}d)")
                )

    roles_m = ROLES_FM_RE.search(text)
    if not roles_m:
        violations.append((1, "missing frontmatter `roles_allowed:` line"))
    else:
        roles = [r.strip() for r in roles_m.group(1).split(",") if r.strip()]
        bad_roles = sorted(r for r in roles if r not in ALLOWED_ROLES)
        if not roles:
            violations.append((1, "roles_allowed: is empty"))
        elif bad_roles:
            violations.append(
                (1, f"roles_allowed: {bad_roles} not a subset of {sorted(ALLOWED_ROLES)}")
            )

    for m in BULLET_RE.finditer(text):
        bullet_text = m.group(1)
        line_no = text[: m.start()].count("\n") + 1
        tag_m = TAGGED_BULLET_RE.match(bullet_text)
        if not tag_m:
            violations.append(
                (line_no, "claim bullet not tagged SELF:/MEASURED:/PUBLIC:")
            )
            continue
        if tag_m.group(1) != "MEASURED":
            continue
        path_m = MEASURED_PATH_RE.match(bullet_text)
        if not path_m:
            violations.append((line_no, "MEASURED: has no backtick-quoted path"))
            continue
        named = path_m.group(1)
        if (REPO_ROOT / named).exists() or MEMORY_SLUG_RE.match(named):
            continue
        violations.append(
            (line_no, f"MEASURED: path `{named}` not in repo and not memory-slug shaped")
        )

    return violations


def main(argv: list[str]) -> int:
    explicit = bool(argv)
    dir_contributions: dict[Path, int] = {}
    if explicit:
        raw_targets = [REPO_ROOT / p for p in argv]
        targets: list[Path] = []
        for raw in raw_targets:
            if raw.is_dir():
                expanded = sorted(raw.glob(DEFAULT_GLOB_PATTERN))
                dir_contributions[raw] = len(expanded)
                targets.extend(expanded)
            else:
                targets.append(raw)
    else:
        raw_targets = []
        targets = sorted((REPO_ROOT / DEFAULT_GLOB_DIR).glob(DEFAULT_GLOB_PATTERN))

    dw = _load_dynamic_workflow()
    bad: list[tuple[Path, int, str]] = []
    scanned = 0
    for path in targets:
        if not path.is_file() or path.suffix != ".md":
            continue
        scanned += 1
        for line_no, msg in find_violations(path, dw):
            bad.append((path, line_no, msg))

    if not explicit and scanned == 0:
        print(
            "❌ lint_model_cards: BLIND SCAN — docs/arsenal/cards/*.md traversed ZERO "
            "files.\nRefusing to report 'clean': a scan that sees nothing proves nothing "
            "(cicatrix #2, \"exists != armed\").",
            file=sys.stderr,
        )
        return 2

    # OBSERVATION 6 (PR3a', 2026-09-18) + PR3c blind-scan closure widened after
    # independent adversarial review (2026-09-19, Sol and Kimi both reproduced): each
    # explicit raw target is judged ON ITS OWN — missing from disk, or an existing
    # directory that glob-expanded to zero in-scope files — INDEPENDENT of whether
    # other targets in the same invocation scanned something. Mirrors
    # lint_workflow_script.py's guard. A global `scanned == 0` gate let one productive
    # target mask a sibling blind one (`lint empty_dir real.md` went green, silently
    # ignoring empty_dir) — cicatrix #2 one level deeper than the single-target case.
    # An explicit EXISTING FILE of the wrong suffix stays legitimately off-scope (never
    # glob-expanded, never expected to be) — test_innocence_explicit_non_md_file_is_
    # still_green's case, unchanged.
    if explicit:
        missing = [p for p in raw_targets if not p.exists()]
        empty_dirs = [p for p, n in dir_contributions.items() if n == 0]
        guilty = missing + empty_dirs
        if guilty:
            names = ", ".join(str(p) for p in guilty)
            print(
                f"❌ lint_model_cards: BLIND SCAN — target(s) yielded zero .md files: {names}.\n"
                "Refusing to report 'clean': a scan that sees nothing proves nothing "
                "(cicatrix #2, \"exists != armed\").",
                file=sys.stderr,
            )
            return 2

    if not bad:
        print(f"✅ lint_model_cards: no violations ({scanned} file(s) scanned)")
        return 0

    print(f"❌ lint_model_cards: {len(bad)} violation(s) in {scanned} file(s) scanned.\n")
    for path, line_no, msg in bad:
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            # an explicit target outside REPO_ROOT has no relative form — fall back to
            # the absolute path rather than traceback (same cure as lint_workflow_script.py).
            rel = path
        print(f"  {rel}:{line_no}: {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
