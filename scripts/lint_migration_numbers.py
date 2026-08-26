#!/usr/bin/env python3
"""W41 (2026-05-23) — migration-number uniqueness lint.

Closes the direct-push bypass discovered in W40 (cicatrix 2026-05-23):
`.github/workflows/lint-migration-numbers.yml` exists since P0-7
(2026-04-29 cicatrix duplicate 129/130) but only fires on `pull_request`.
L2 autonomous-ops policy allows direct-push to main, which silently
skips the lint. W37 1234c9114 went direct-to-main and dropped
194_organism_incident_ledger.sql while PR #828 was simultaneously
merging 194_reconcile_107_bridge_outbox_tracking.sql. Migration runner
`_assert_unique_migration_numbers` would have hard-failed the next
deploy, blocking ALL pending migrations.

This script is the local-checkout twin of the CI workflow. Used by:
1. `.husky/pre-commit` — fires when staged files include migrations_v2/
2. `.github/workflows/lint-migration-numbers.yml` — also wired to `push`
   in W41 so post-push regression is caught even when PR is bypassed
3. `.github/workflows/hot-zone-pr-gate.yml` — replays it on `pull_request`
   over a materialized merge tree (base + PR head's migrations_v2/)

Exit 0 if clean. Exit 1 with a duplicate report.

The uniqueness algorithm is intentionally INLINED (not imported from
`backend.db.migration_manager`) because the manager's import chain pulls
in `Settings()` which requires JWT_SECRET_KEY/API_KEYS — unavailable in
local dev shells, hook contexts, and CI lint jobs. Drift mitigation:
the algorithm is 6 lines, identical in both places, and there is a
companion test `test_lint_migration_numbers.py` that locks the contract.

CROSS-BRANCH COLLISION CHECK (mig-collision-281, 2026-08-26)
--------------------------------------------------------------
`find_duplicates` above audits ONE tree: files sitting side by side on
disk right now. It says nothing about two BRANCHES that independently
claimed the same number — `feature/due-bot`'s own
`281_team_bot_ingress_leader.sql` and `origin/main`'s independently
authored `281_garuda_voa_retention.sql` were each perfectly unique on
their own branch; `find_duplicates` reported green on both. The
collision only exists BETWEEN the trees, and only surfaces at merge
(`git merge-tree --write-tree origin/main HEAD` lands both 281 files in
the merged tree — exactly what `_assert_unique_migration_numbers` would
then reject at the next deploy). Same superscar family as the
within-tree case (#9 state-schema mutation drift / W40, W128), the
gap this closes is the family's own "guard answers the wrong question"
failure mode (#3): a lint that only ever reads its own branch cannot,
by construction, see a number the OTHER branch already claimed.

`find_cross_branch_collisions` below is the comparison — pure, no git
calls, easy to unit-test with two plain {number: filename} maps.
`check_cross_branch` is the thin glue that resolves a target ref
(`MIGRATION_LINT_MERGE_TARGET` env override > `origin/$GITHUB_BASE_REF`
in CI > `origin/main` default) and lists its migrations_v2/ files via
`git ls-tree`, then calls the pure comparison. It NEVER fetches over the
network and NEVER raises: if the target ref cannot be resolved locally
(a shallow checkout, a repo with no `origin`, a target branch nobody
fetched), it returns `(None, {})` and the caller treats that as "cannot
verify this half", not as failure — cicatrix family #2 (Esiste≠Armato)
in reverse: a check that hard-fails whenever it cannot see the whole
picture gets `SKIP_PREFLIGHT=1`'d into silence by the next person in a
hurry, which is worse than an honest gap. Same number + the SAME
filename on both sides (a file that has already converged across
branches, e.g. `283_wa_reply_claims.sql`) is innocent, not a collision.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "db" / "migrations_v2"
MIGRATIONS_RELPATH = "apps/backend-rag/backend/db/migrations_v2"


def find_duplicates(sql_files: Iterable[Path]) -> dict[int, list[str]]:
    """Inlined twin of `backend.db.migration_manager._assert_unique_migration_numbers`.

    Returns {number: [filename, filename, ...]} for any prefix shared by ≥2
    files. Files that don't start with `NNN_` are ignored (manager logs a
    warning later in its own discovery path).
    """
    seen: dict[int, str] = {}
    duplicates: dict[int, list[str]] = {}
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if num in seen:
            duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
        else:
            seen[num] = sql_file.name
    return duplicates


def _target_ref(env: Mapping[str, str] | None = None) -> str:
    """Which ref to compare against for the cross-branch check.

    Priority: explicit `MIGRATION_LINT_MERGE_TARGET` override > GitHub
    Actions' own `GITHUB_BASE_REF` (set on `pull_request` events to the
    PR's actual base branch — `main` for most PRs, but an integration
    branch like `feature/due-bot` for a lane PR that targets it, which is
    exactly this repo's own due-bot pattern) > `origin/main`, the sane
    default for local dev and for `push` CI events where no PR base
    exists.
    """
    env = os.environ if env is None else env
    override = env.get("MIGRATION_LINT_MERGE_TARGET")
    if override:
        return override
    base_ref = env.get("GITHUB_BASE_REF")
    if base_ref:
        return f"origin/{base_ref}"
    return "origin/main"


def _resolve_ref(ref: str, cwd: Path) -> str | None:
    """Return `ref` if it resolves to a commit `cwd`'s repo already has, else
    None. Local resolution ONLY — never fetches. A lint that reaches for the
    network on every commit touching migrations_v2/ adds latency and an
    offline failure mode nobody asked for; the contract is "check what's
    already there, skip gracefully otherwise" (see module docstring).
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            cwd=cwd,
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None
    return ref


def _list_migration_numbers_at_ref(
    ref: str, cwd: Path, relpath: str = MIGRATIONS_RELPATH
) -> dict[int, str] | None:
    """{number: filename} for every `NNN_*.sql` under `relpath` at `ref`.

    None (never an exception) if the tree can't be read — a missing path
    at that ref, a corrupt/incomplete object, or any other git failure.
    """
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, "--", relpath],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None

    numbers: dict[int, str] = {}
    for line in result.stdout.splitlines():
        name = line.rsplit("/", 1)[-1]
        if not name.endswith(".sql"):
            continue
        try:
            num = int(name.split("_")[0])
        except (ValueError, IndexError):
            continue
        numbers[num] = name
    return numbers


def find_cross_branch_collisions(
    working_numbers: Mapping[int, str], target_numbers: Mapping[int, str]
) -> dict[int, tuple[str, str]]:
    """{number: (working_filename, target_filename)} for every number that
    names a DIFFERENT file in `target_numbers` than in `working_numbers`.

    Pure — no filesystem, no git, no network. Same number + the SAME
    filename on both sides is innocent (a migration already converged
    across branches, e.g. 283_wa_reply_claims.sql landing unchanged on
    both `feature/due-bot` and `origin/main`) and is NOT reported.
    """
    collisions: dict[int, tuple[str, str]] = {}
    for num, working_name in working_numbers.items():
        target_name = target_numbers.get(num)
        if target_name is not None and target_name != working_name:
            collisions[num] = (working_name, target_name)
    return collisions


def check_cross_branch(
    sql_files: Iterable[Path],
    *,
    cwd: Path | None = None,
    target: str | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str | None, dict[int, tuple[str, str]]]:
    """Resolve a merge target and check `sql_files` against it.

    Returns `(resolved_target, collisions)`. `resolved_target` is None when
    the target ref couldn't be resolved locally (degrade-gracefully path —
    see module docstring); the caller must treat that as "not checked", not
    as "clean", but it is NOT a lint failure on its own.
    """
    cwd = REPO_ROOT if cwd is None else cwd
    target = _target_ref(env) if target is None else target
    resolved = _resolve_ref(target, cwd)
    if resolved is None:
        return None, {}

    target_numbers = _list_migration_numbers_at_ref(resolved, cwd)
    if target_numbers is None:
        return None, {}

    working_numbers: dict[int, str] = {}
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        working_numbers[num] = sql_file.name

    return resolved, find_cross_branch_collisions(working_numbers, target_numbers)


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(
            f"❌ migration-numbers lint: directory not found: {MIGRATIONS_DIR}",
            file=sys.stderr,
        )
        return 2

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        # BLIND-SCAN GUARD (cicatrix #4 / W84 — "0 files traversed != clean").
        # The missing-directory case above already exits 2; this closes the
        # narrower sibling: the directory EXISTS but holds no .sql at all.
        # On this repo that is never legitimate — migrations_v2/ is populated on
        # main — so it means the checkout is partial/sparse or the glob stopped
        # matching. A warning is not a gate: downgrade to exit 0 and the lint
        # reports success while having judged nothing.
        print(
            f"❌ migration-numbers lint: BLIND SCAN — {MIGRATIONS_DIR} exists but "
            "contains no .sql files.\nRefusing to report clean: a lint that reads "
            "nothing proves nothing (partial/sparse checkout?).",
            file=sys.stderr,
        )
        return 2

    duplicates = find_duplicates(sql_files)
    if duplicates:
        details = ", ".join(
            f"{num}: [{', '.join(files)}]" for num, files in sorted(duplicates.items())
        )
        print(
            f"❌ migration-numbers lint: duplicate prefixes in migrations_v2/: {details}\n"
            "\n"
            "Resolution (cicatrix W40 2026-05-23 convention):\n"
            "  The file that arrived SECOND (in git log time) yields and is\n"
            "  renamed to the next-available number. Workflow:\n"
            "\n"
            "    git mv apps/backend-rag/backend/db/migrations_v2/NNN_<later>.sql \\\n"
            "           apps/backend-rag/backend/db/migrations_v2/MMM_<later>.sql\n"
            "    # update the SQL header comment to match MMM\n"
            "    # update any tests/* that reference the old NNN_ path\n"
            "    git commit -m 'fix(migrations): rename collision NNN -> MMM'\n"
            "\n"
            "Reference: cicatrix RESOLVED 2026-05-23 W40 +\n"
            "research/operations/2026-05-23-w40-migration-194-collision.md",
            file=sys.stderr,
        )
        return 1

    resolved_target, cross = check_cross_branch(sql_files)
    if resolved_target is None:
        print(
            "ℹ️  migration-numbers lint: cross-branch check skipped — could not "
            "resolve a merge target locally (shallow checkout / no origin / "
            "target branch not fetched). Same-tree check above still applies "
            "in full.",
        )
    elif cross:
        details = ", ".join(
            f"{num}: [working={wf}, {resolved_target}={tf}]"
            for num, (wf, tf) in sorted(cross.items())
        )
        print(
            f"❌ migration-numbers lint: cross-branch collision vs {resolved_target}: "
            f"{details}\n"
            "\n"
            "Two branches independently claimed the same number for two\n"
            "DIFFERENT migrations. find_duplicates() above cannot see this —\n"
            "each file is unique on its own branch; the collision only exists\n"
            "BETWEEN them and would surface at merge time\n"
            "(`git merge-tree --write-tree <target> HEAD`). Resolution:\n"
            "\n"
            "  1. `git ls-tree -r --name-only "
            f"{resolved_target} -- {MIGRATIONS_RELPATH} | sort` and\n"
            "     `gh pr list --state open --json number,files -q '.[] | "
            ".number as $n | .files[]?.path | select(test(\"migrations_v2/"
            "[0-9]+_\")) | \"\\($n): \\(.)\"'` — measure BOTH the target's\n"
            "     confirmed tip AND every open PR's claimed numbers fresh; a\n"
            "     lint only ever compares main + the current PR, never two\n"
            "     branches against each other (this is that missing check).\n"
            "  2. `git mv` this branch's colliding file(s) to the next number\n"
            "     clear of both measurements, update the SQL header and any\n"
            "     tests/docs that name the old number.\n"
            "\n"
            "Reference: mig-collision-281 (2026-08-26), following the W40\n"
            "convention (cicatrix RESOLVED 2026-05-23 +\n"
            "research/operations/2026-05-23-w40-migration-194-collision.md).",
            file=sys.stderr,
        )
        return 1

    print(f"✅ migration-numbers lint: {len(sql_files)} files, all unique prefixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
