#!/usr/bin/env python3
"""lint_doc_executable_refs.py — CI antidote for "docs assert an entry point
that doesn't exist on disk" (2026-07-14 WR2 deep audit,
research/operations/2026-07-14-wr2-deep-audit.md §2, §8, §10.11):

    "A fresh agent reading `wr2-carousel-pipeline` SKILL.md runs a file that
    isn't there" — `scripts/wr2_carousel_orchestrator.py` and
    `scripts/wr2_telegram_publish_gate.py` were cited as live entry points in
    docs long after they stopped existing on disk (the retired Canva lane,
    PR #2396, is the same disease at the pipeline-doc level).

THE DISEASE: this is the documentation-layer instance of the audit's §8
meta-pattern — "surfaces assert states they never verified, because the
asserting organ and the knowing organ are different organs that don't share
a nerve." A doc is the asserting organ; the filesystem is the knowing organ;
nothing ever re-checks the doc against disk after the file it cites is
deleted or renamed. Generalizes W65/W81 (verify file:line claims before
building on them) to CI: the doc drift ITSELF becomes a build-blocking fact
instead of a rediscovered-per-audit one.

THE ANTIDOTE: scan a configured set of "living documentation" surfaces
(`infra/doc-lint/executable-refs-config.json`) for `scripts/<path>.(py|sh)`
references and FAIL if the referenced file is absent from the repo tree.

HISTORICAL EXEMPTION (deliberate, not a loophole): a point-in-time snapshot
that says "on 2026-05-08 the pipeline used scripts/wr2_canva_apply.py" is not
lying — it is dated. Point-in-time docs are exempted by default via two
mechanisms, both config-driven:
  1. `exclude_prefixes` — directory-level historical archives (research/,
     .claude/rules/cicatrix*, docs/superpowers/plans/ — audit reports, scar
     bodies, superseded plans).
  2. `exclude_dated_filenames` (default true) — any doc whose BASENAME embeds
     an ISO date (YYYY-MM-DD) is presumed a dated snapshot and exempted. This
     mirrors the repo's own dated-slug convention (CLAUDE.md §15,
     `research/<domain>/YYYY-MM-DD-slug.md`) rather than inventing a new
     rule — `docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md` and
     `docs/wr2/pipeline-architecture-2026-05-10.md` are exempted by the SAME
     logic that already exempts research/, not a hand-picked list.

Scope (deliberate, per mandate): starts wr2-scoped (`docs/wr2/*.md` +
`.claude/skills/wr2-carousel-pipeline/**/*.md`, harmless today since that
skill is currently HOME-only and not repo-tracked — see PENDING-ALIGN note in
the PR that shipped this lint) and is config-driven so new "living doc"
surfaces can be added without touching this file.

Exit code: 0 = clean · 1 = ghost reference(s) found · 4 = operational error
(config unreadable, or zero files matched by include_globs — a scan that
finds nothing to scan is not "clean", W84 discipline: fail-visible on blind
scans, not silent-pass).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _canonical_repo_root() -> Path:
    """Repo root, worktree-hardened (mirrors scripts/lint_home_fork.py): running
    from .worktrees/<lane>/ must lint against the MAIN checkout — a worktree is
    ephemeral, treating it as the source of truth would misreport findings that
    don't exist on the branch this PR will actually land on."""
    root = Path(__file__).resolve().parent.parent
    parts = root.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        return Path(*parts[:idx])
    return root


REPO_ROOT = _canonical_repo_root()
DEFAULT_CONFIG = REPO_ROOT / "infra" / "doc-lint" / "executable-refs-config.json"

EXEC_REF_RE = re.compile(r"scripts/[A-Za-z0-9_./-]+\.(?:py|sh)")
DATED_BASENAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"lint_doc_executable_refs: cannot read config {config_path}: {exc}")
    data.setdefault("include_globs", [])
    data.setdefault("exclude_prefixes", [])
    data.setdefault("exclude_dated_filenames", True)
    return data


def resolve_candidates(repo_root: Path, include_globs: list[str]) -> list[Path]:
    """Every file matched by any include_glob, relative to repo_root, deduped
    and sorted for deterministic output."""
    seen: set[Path] = set()
    for pattern in include_globs:
        for match in repo_root.glob(pattern):
            if match.is_file():
                seen.add(match.resolve())
    return sorted(seen)


def is_excluded(rel_posix: str, basename: str, exclude_prefixes: list[str], exclude_dated: bool) -> bool:
    if exclude_dated and DATED_BASENAME_RE.search(basename):
        return True
    for prefix in exclude_prefixes:
        if rel_posix.startswith(prefix):
            return True
    return False


def scan_file(path: Path, repo_root: Path) -> list[str]:
    """Return the ghost references (scripts/... paths cited but absent) in one file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    ghosts: list[str] = []
    # NOTE: findall() with a non-capturing group (?:py|sh) returns the full
    # match string, but finditer()+group(0) is used explicitly for clarity
    # and to stay robust if the group ever needs to become capturing.
    refs = sorted({m.group(0) for m in EXEC_REF_RE.finditer(text)})
    for ref in refs:
        if not (repo_root / ref).exists():
            ghosts.append(ref)
    return ghosts


def run_lint(config: dict[str, Any], repo_root: Path) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Returns (ghosts_by_file, scanned_files_rel, errors)."""
    candidates = resolve_candidates(repo_root, config["include_globs"])
    exclude_prefixes = config["exclude_prefixes"]
    exclude_dated = bool(config["exclude_dated_filenames"])

    errors: list[str] = []
    scanned: list[str] = []
    ghosts_by_file: dict[str, list[str]] = {}

    if not candidates:
        errors.append(
            f"zero files matched include_globs={config['include_globs']!r} — "
            "scan is blind, not clean (W84 discipline)"
        )
        return ghosts_by_file, scanned, errors

    for path in candidates:
        rel = path.relative_to(repo_root).as_posix()
        if is_excluded(rel, path.name, exclude_prefixes, exclude_dated):
            continue
        scanned.append(rel)
        ghosts = scan_file(path, repo_root)
        if ghosts:
            ghosts_by_file[rel] = ghosts

    return ghosts_by_file, scanned, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    ghosts_by_file, scanned, errors = run_lint(config, args.repo_root)

    exit_code = (1 if ghosts_by_file else 0) | (4 if errors else 0)

    if args.json:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "scanned_files": scanned,
                    "ghosts_by_file": ghosts_by_file,
                    "errors": errors,
                    "exit": exit_code,
                },
                indent=2,
            )
        )
        return exit_code

    print(f"[doc-executable-refs] scanned {len(scanned)} living-doc file(s)")
    if ghosts_by_file:
        print(f"  ghost references found in {len(ghosts_by_file)} file(s):")
        for rel, ghosts in ghosts_by_file.items():
            for g in ghosts:
                print(f"    - {rel}: cites `{g}` — does not exist on disk")
    else:
        print("  clean — every scripts/*.py|.sh reference in a living doc resolves to a real file")
    if errors:
        print(f"[errors] {len(errors)} operational error(s) — scan is PARTIAL, not clean:")
        for e in errors:
            print(f"  - {e}")
    if exit_code:
        print(
            f"DOC-EXECUTABLE-REFS LINT FAIL (exit {exit_code}: 1=ghost-ref 4=scan-error) — "
            "either the script was renamed/deleted and the doc is stale (fix the doc), or "
            "this doc is a dated historical snapshot that should be excluded "
            "(infra/doc-lint/executable-refs-config.json exclude_prefixes / "
            "exclude_dated_filenames)"
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
