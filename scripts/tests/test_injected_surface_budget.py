"""Structural and delivery attestation for the repo-side injected surface.

This module is a *structural attestation*: it reconstructs what the harness
WOULD load from repo state and is therefore a structural proxy. It cannot
observe what a live session actually received. The companion *delivery
attestation* lives in the SessionStart hook: it is machine-local, so it sees the
global CLAUDE.md and this machine's own `claudeMdExcludes`, which CI cannot. It
is still a reconstruction from the filesystem, not a transcript — a file the
harness silently declines to load would be counted by both. Only a session's own
transcript witnesses delivery; these two make the number visible enough that a
drift with no repo diff still reaches a reader. This test exists so nobody later reads a green CI run as proof of
live delivery.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

import pytest

INTERIM_BYTE_BUDGET = 120_000  # INTERIM pending a Zero ruling (plan §6.3 default), NOT final.

PINNED_RULES_MEMBERS: frozenset[str] = frozenset({
    "cicatrix-superscar.md",
    "doc-generator-blocklist.md",
    "frontend-nextjs.md",
    "infrastructure.md",
    "python-backend.md",
})

MOVED_SCAR_FILES: frozenset[str] = frozenset({
    "docs/scars/cicatrix-scars.md",
    "docs/scars/cicatrix-scars-archive.md",
})

_NEEDLE = ".claude" + "/rules/cicatrix-scars"  # split so this guard is not its own first hit

# A resolver does not have to spell the path contiguously. `Path(".claude") /
# "rules" / "cicatrix-scars.md"` reads nothing after the move and contains no
# occurrence of _NEEDLE at all, so a substring scan alone is an under-match —
# the shape W94 predicts for every over-match cure. Matched on one line, which
# is how these are written in this repo (checked against all 12 call sites).
_SPLIT_NEEDLE_RE = re.compile(
    r'["\']\.claude["\']\s*/\s*["\']rules["\']\s*/\s*["\']cicatrix-scars'
)

# An exemption is a DECLARATION, not a hole: each entry names the file and why
# it is allowed to keep the old string. A blanket skip would let the next stale
# resolver hide behind the same door (cicatrix-scars.md W108: the guard that
# forbids a string ends up writing it, and the cure is to name the exception,
# never to widen the skip).
# Where an exemption is narrower than "this whole file": the line must ALSO
# contain this marker to be excused.
_EXEMPT_LINE_MARKER: dict[str, str] = {
    "scripts/lint_scar_number_collision.py": "LEGACY_FILE",
}

_EXEMPT: dict[str, str] = {
    "scripts/tests/test_injected_surface_budget.py": (
        "this guard itself — it must hold the needle in order to search for it, "
        "and there is no other module to import it from because this IS the lint"
    ),
    "scripts/lint_scar_number_collision.py": (
        "LEGACY_FILE: a deliberate, dated fallback for the single merge window "
        "in which origin/main still carries only the old path; its own comment "
        "names the condition under which it must be deleted"
    ),
}
_ALLOWED_DOT_DIRS = frozenset({".github", ".husky", ".claude"})
# Skipped by NAME anywhere in the tree. `research/` and `evidence/` are
# write-once records of past runs; the rest are caches and dependency trees.
_SKIPPED_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".next",
        "dist",
        "build",
        "site-packages",
        "research",
        "evidence",
    }
)

# Dated records, skipped on purpose rather than by accident. `docs/audits/2026-04-29-*`,
# `docs/archive/**` and `docs/innervation-2026-04-29/**` cite the old path in prose
# written when the old path was where the file WAS. That sentence is still true;
# rewriting it to match today would be falsifying a record, not maintaining one. The
# rest of `docs/` IS scanned, because `docs/AI_ONBOARDING.md` and friends are live
# navigation — a reader follows them today and must not land on a file that moved.
_ARCHIVAL_PREFIXES = (
    "docs/audits/",
    "docs/archive/",
    "docs/innervation-",
    "docs/superpowers/",
    "docs/ops/",
    "docs/wr2/operator-driven-mode-spec-",
)

# Generated, not authored: `.secrets.baseline` is rewritten in place by the
# security workflow's own scan step (security.yml:956), so a stale key in it is
# cured by the next CI run, not by a hand edit — and hand-editing it produces a
# ~1000-line re-sort that buries the diff a reviewer came to read.
_GENERATED_FILES = frozenset({".secrets.baseline"})


def repo_side_injected_bytes() -> tuple[int, dict[str, int]]:
    """Return the repo-side injected surface in bytes.

    This reads only the repo-root CLAUDE.md and every ``.claude/rules/*.md``.
    The global ``~/.claude/CLAUDE.md`` is deliberately excluded: it is
    machine-local and does not exist on CI runners, so a repo test must not
    depend on it.
    """
    repo_root = Path(__file__).resolve().parents[2]
    files: dict[str, int] = {}

    root_claude = repo_root / "CLAUDE.md"
    if root_claude.is_file():
        files["CLAUDE.md"] = root_claude.stat().st_size

    rules_dir = repo_root / ".claude" / "rules"
    if rules_dir.is_dir():
        # rglob, not glob: a subdirectory is not a hiding place. Whether the
        # harness descends is not the point — an unpinned 1 MB file under
        # `.claude/rules/nested/` must be SEEN and declared either way.
        for path in sorted(rules_dir.rglob("*.md")):
            relpath = path.relative_to(repo_root).as_posix()
            files[relpath] = path.stat().st_size

    return sum(files.values()), files


def _should_skip_dir(name: str) -> bool:
    """Prune directories we do not want to scan for stale resolvers.

    Hidden directories are usually local state; we only keep the explicitly
    tracked dot-prefixed ones. We also skip archival trees and dependency
    caches because any reference inside them is not active code/config.
    """
    if name in _SKIPPED_DIR_NAMES:
        return True
    if name.startswith(".") and name not in _ALLOWED_DOT_DIRS:
        return True
    return False


def _scan_file(file_path: Path, repo_root: Path, hits: list[tuple[str, int]]) -> None:
    """Read a text file and record every line containing the stale needle."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        # Binary or unreadable files cannot contain a stale text resolver.
        return

    rel_path = file_path.relative_to(repo_root).as_posix()
    if rel_path.startswith(_ARCHIVAL_PREFIXES) or rel_path in _GENERATED_FILES:
        return
    exempt_marker = _EXEMPT_LINE_MARKER.get(rel_path)
    if rel_path in _EXEMPT and exempt_marker is None:
        return
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not (_NEEDLE in line or _SPLIT_NEEDLE_RE.search(line)):
            continue
        # A file-wide exemption is a hole: reverting DEFAULT_FILE in the collision
        # lint would slip straight through one. Only the line that carries the
        # declared marker is excused; every other stale line in that same file
        # still fails (cicatrix W105 — judge the entity, not the container).
        if exempt_marker is not None and exempt_marker in line:
            continue
        hits.append((rel_path, line_no))


def _scan_target(target: Path, repo_root: Path, hits: list[tuple[str, int]]) -> None:
    """Scan a single file or directory tree for the stale resolver needle."""
    if not target.exists():
        return

    moved_paths = {repo_root / rel for rel in MOVED_SCAR_FILES}

    if target.is_file():
        if target in moved_paths:
            return
        _scan_file(target, repo_root, hits)
        return

    for dirpath, dirnames, filenames in os.walk(target):
        # Prune skipped directories in-place so we do not descend into them.
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path in moved_paths:
                continue
            _scan_file(file_path, repo_root, hits)


def test_rules_membership_is_pinned() -> None:
    """Hard assertion: only deliberately pinned files may live in .claude/rules.

    This test FAILS hard because unpinned growth is the primary regrowth
    vector: every file in this directory is loaded into every session and
    every subagent. Missing a pinned file is equally bad, because a pin that
    no longer matches reality is worthless.
    """
    repo_root = Path(__file__).resolve().parents[2]
    rules_dir = repo_root / ".claude" / "rules"
    present = (
        {p.relative_to(rules_dir).as_posix() for p in rules_dir.rglob("*.md")}
        if rules_dir.is_dir()
        else set()
    )

    if present == PINNED_RULES_MEMBERS:
        return

    extra = present - PINNED_RULES_MEMBERS
    missing = PINNED_RULES_MEMBERS - present
    messages: list[str] = []

    for name in sorted(extra):
        path = rules_dir / name
        size = path.stat().st_size if path.exists() else 0
        messages.append(
            f"unpinned file present: {name} ({size} B). "
            "Add it to PINNED_RULES_MEMBERS deliberately because every byte there "
            "is paid by every session and every subagent."
        )

    for name in sorted(missing):
        messages.append(f"pinned file missing: {name}")

    pytest.fail("\n".join(messages))


def test_repo_side_byte_budget_is_noticed() -> None:
    """NOTICE the budget; do not FAIL on it.

    This is a NOTICE and not a FAIL because INTERIM_BYTE_BUDGET is an open
    ruling, not a hard limit. The companion TEST A is the assertion that
    actually stops regrowth by forcing deliberate membership review. We do
    assert total > 0 because a resolver that silently finds nothing must not
    read as "budget respected" — that is the classic esiste-ne-armato failure.
    """
    total, files = repo_side_injected_bytes()
    assert total > 0, "resolver found nothing; cannot tell whether budget is respected"

    if total > INTERIM_BYTE_BUDGET:
        table = "\n".join(
            f"  {path}: {size} B"
            for path, size in sorted(files.items(), key=lambda item: -item[1])
        )
        message = (
            f"repo-side injected surface is {total} B, over "
            f"INTERIM_BYTE_BUDGET {INTERIM_BYTE_BUDGET} B\n{table}"
        )
        warnings.warn(message, stacklevel=2)
        print(message)


def test_no_stale_resolvers_point_to_moved_scars() -> None:
    """Anti-regrowth: the scar bodies moved; resolvers must move with them.

    If tracked code or config still points at ``.claude/rules/cicatrix-scars``,
    it will silently load nothing on the next session because the bodies now
    live under ``docs/scars/``.
    """
    repo_root = Path(__file__).resolve().parents[2]
    hits: list[tuple[str, int]] = []

    # Walk the WHOLE repo and subtract, rather than listing directories to
    # visit. An allow-list of targets is a guard whose blind spots are invisible:
    # the previous version named seven directories and could not see `packages/`,
    # `config/`, `tests/`, `kb/` or a single repo-root file — three of which held
    # stale pointers when this move landed, found by a refuter and not by the
    # guard that exists to find them. A deny-list fails the other way: something
    # new in the tree is scanned by default, and anything skipped had to be named.
    targets = [repo_root]

    for target in targets:
        _scan_target(target, repo_root, hits)

    if hits:
        lines = [f"{path}:{line_no}" for path, line_no in hits]
        pytest.fail(
            "stale resolvers still point to .claude/rules/cicatrix-scars:\n"
            + "\n".join(lines)
            + "\nThe body now lives at docs/scars/; a stale resolver will silently read nothing."
        )


def test_module_docstring_declares_structural_and_delivery_attestation() -> None:
    """Honesty check: the module must admit what it cannot prove.

    A green CI run on this file only proves repo structure; it does not prove
    that a live session received the same bytes.

    Anchored to the docstring BODY, never to its summary line: the summary
    already reads "Structural and delivery attestation ...", so a check for the
    bare phrases is satisfied by the title alone and stays green while the
    explanation underneath it is deleted — a guard that cannot fail for the
    reason it exists (superscar #2). Measured 2026-08-31: removing the body's
    "*delivery attestation*" sentence left the phrase-only form passing.
    """
    docstring = __doc__ or ""
    body = docstring.split("\n", 1)[1] if "\n" in docstring else ""
    flat = " ".join(body.split())
    for phrase in ("structural attestation", "delivery attestation"):
        assert phrase in flat, (
            f"the docstring BODY must explain {phrase!r}, not just name it in the "
            "summary line — this test's whole job is that the next reader learns "
            "what a green run does and does not prove"
        )
    for clause in ("structural proxy", "cannot"):
        assert clause in flat, (
            f"the docstring body must keep the honesty clause {clause!r}: without it "
            "the distinction is named but never explained"
        )
