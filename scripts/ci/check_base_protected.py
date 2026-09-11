#!/usr/bin/env python3
"""check_base_protected.py — an integration branch inherits main's gates or
the PR into it goes red (S5 check-half, ASSEMBLY-LINE.md "The integration
branch must be protected BEFORE the first lane opens a PR").

WHY THIS EXISTS. Measured live 2026-08-27: exactly 2 GitHub rulesets exist in
this repo, both scoped to `main`/`~DEFAULT_BRANCH` — `merge-queue-main` (id
19779175) and `Copilot review for default branch` (id 20608865). Nothing
covers `refs/heads/feature/*`. In the 48h window 2026-08-25/26, 52 PRs merged
into `feature/kb-current` (26), `feature/garuda-voa` (23) and `feature/due-bot`
(2) with ZERO required checks — documented in ASSEMBLY-LINE.md as a real
incident: a 15-file customer-facing PR merged unreviewed, and a magic-link PR
merged with two backend shards red. `gh pr merge --auto` on an unprotected
branch does not mean "merge when green" — red CI never holds it, because there
is nothing there to hold it. This script is the CHECK-half: it runs on every
PR and fails the PR's own checks (not merge-blocking by itself — becoming
required-status-check-blocking is a separate, deliberately NOT-taken step; see
"SCOPE" below) whenever the PR's base branch is not covered by a ruleset
carrying the main-equivalent minimum required checks. The ARM-half — actually
creating that ruleset — is `scripts/ci/setup_merge_queue_ruleset.sh
--branch-pattern <pattern>`, print-only unless `--apply`, an operator[control-
plane] action this script only ever prints the command for, never runs.

A CORRECTED PREMISE (anti-hallucination discipline: verify, don't assume).
The natural first design was "read main's OWN ruleset's required_status_checks
rule and pin the minimum from there." That is WRONG, verified live:
`gh api repos/Bali-Zero/Teman2/rulesets/19779175` carries exactly one rule,
type `merge_queue` — no `required_status_checks` rule at all. Main's real 27
required contexts live in CLASSIC branch protection
(`branches/main/protection/required_status_checks`), a separate, older
mechanism that cannot glob-match a branch that doesn't exist yet (which is
exactly why it can't cover `feature/*` on its own). So "read the ruleset's
rules" would always find zero contexts and either pin nothing or crash. The
real minimum-contexts list is hand-picked from classic protection's 27 and
lives in `infra/required.d/integration-branch-minimum-contexts.json` — see
that file's own `_corrected_premise_2026_08_27` field. This module never reads
ruleset 19779175 to derive the minimum; it reads that JSON file instead.

WHAT COUNTS AS "COVERED". For a non-default base ref, this module computes the
UNION of `required_status_checks` contexts across every ACTIVE, target=branch
ruleset whose `conditions.ref_name` matches the base ref (honoring `~ALL` and
`~DEFAULT_BRANCH`, plus fnmatch-style globs against the full
`refs/heads/<name>` ref — declared scope limit: no tag-ruleset or non-branch-
target handling, matching this repo's `required_context_map.py` style of a
narrow, stated limit rather than a general rules-engine). The union — not a
single ruleset — because GitHub's real model lets multiple rulesets cover the
same ref cumulatively; main itself splits its own protection across a ruleset
(merge_queue mechanics) and classic protection (required checks), so a
feature/* ruleset carrying BOTH in one object, or split across two, must both
count as covered. If the pinned minimum is a subset of that union, the base is
covered; otherwise it is not, regardless of the base ref matching some
ruleset's include pattern only for an unrelated rule (e.g. Copilot review).

SCOPE (declared, not hidden): the base==default-branch case always exits 0
without ever calling `gh api rulesets` — main's own protection is classic
branch protection, verified live, and out of this module's job entirely. Only
a non-default base pays the rulesets API cost. This job does NOT add itself to
required_status_checks (that repo-settings mutation is the operator's arm-
half, per the PR contract this script shipped under: "never mutate repo
settings/rulesets, this lane ships the CHECK-half only") — so today, a red run
is a visible, honest signal on the PR's Checks tab, not yet a merge-blocking
one. That second step is exactly what creating the feature/* ruleset (arm-
half) provides, once an operator runs `--apply`.

DECLARED RESIDUAL LIMITS (found by a cross-family refuter, 2026-08-27,
verified before accepting):
  - Pagination: `gh api repos/<repo>/rulesets` is called WITHOUT `--paginate`.
    This repo has exactly 2 rulesets today (verified live), well under any
    plausible page size, so this is inert in practice — but a repo with 30+
    rulesets could have a real covering ruleset sit on a page this call never
    fetches, silently missing it. Not fixed here: `gh api --paginate`'s exact
    JSON-array-concatenation shape (vs `--slurp`, which nests pages instead of
    flattening them) could not be verified against a real multi-page response
    in this repo, and guessing wrong would risk breaking the common case to
    fix a rare one. Fix only after confirming the exact shape against a real
    paginated response.
  - A non-default base ref that is protected via CLASSIC branch protection
    (rather than a ruleset) is reported UNPROTECTED regardless — this module
    only ever reads rulesets. Not fixed here: classic protection cannot
    glob-match a branch pattern anyway (the whole reason the arm-half creates
    a RULESET, never classic protection, for feature/*), so this asymmetry
    only bites a branch someone protected by hand via the classic UI — narrow,
    and worth knowing, not worth the scope creep of also querying classic
    protection for arbitrary branch names here.
  - Whether the pinned minimum contexts' defining workflows actually trigger
    on a PR into a non-default base — VERIFIED, not just assumed (the exact
    Codex-F12 trap `check_required_workflow_conformance.py` exists to catch
    elsewhere in this repo): none of the 5 pinned workflows' `on.pull_request`
    blocks carry a `branches:` restriction, so all 5 fire on a PR into
    `feature/*` exactly as they do into `main`.

Exit codes: 0 covered (base is the default branch, or a non-default base is
covered by the union of active rulesets) · 1 UNPROTECTED (guilt: no covering
ruleset, or a covering ruleset lacks required_status_checks for the pinned
minimum) · 1 BLIND (a genuine API/resolution error — cannot verify, must not
certify; distinguished from UNPROTECTED only by message prefix, per this
mandate's own spec: both are "fail closed", not two different postures).

Usage:
    python3 scripts/ci/check_base_protected.py --base-ref feature/kb-current \\
        [--repo Bali-Zero/Teman2] [--default-branch main] \\
        [--min-contexts-json infra/required.d/integration-branch-minimum-contexts.json] \\
        [--rulesets-json <file>]

`--repo`/`--default-branch` are free in CI (`${{ github.repository }}` /
`${{ github.event.repository.default_branch }}` need no extra API call) —
omit them only for manual/local invocation, where they fall back to
`gh repo view` / `gh api repos/<repo>` (each a genuine live call that can
itself go BLIND). `--rulesets-json <file>` is the test fixture path: a JSON
array of FULL ruleset objects (id/name/target/enforcement/conditions/rules —
the shape `gh api repos/<repo>/rulesets/<id>` returns for ONE ruleset, one
entry per ruleset here), bypassing `gh` entirely so tests never touch the
network.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MIN_CONTEXTS_JSON = (
    REPO_ROOT / "infra" / "required.d" / "integration-branch-minimum-contexts.json"
)


# --------------------------------------------------------------------- gh IO


def _gh(args: list[str]) -> tuple[bool, str]:
    """Runs `gh` and returns (ok, stdout). Never raises — a missing binary,
    a timeout, or a non-zero exit are all ordinary, expected outcomes this
    module fails CLOSED on, never a crash (W84: an empty/failed call must
    never be silently read as 'nothing here')."""
    try:
        out = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    if out.returncode != 0:
        return False, ""
    return True, out.stdout


def resolve_repo(override: str | None) -> str | None:
    if override:
        return override
    ok, out = _gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not ok or not out.strip():
        return None
    return out.strip()


def resolve_default_branch(repo: str, override: str | None) -> str | None:
    if override:
        return override
    ok, out = _gh(["api", f"repos/{repo}", "--jq", ".default_branch"])
    if not ok or not out.strip():
        return None
    return out.strip()


def fetch_live_rulesets(repo: str) -> list[dict] | None:
    """Two-tier fetch, verified empirically against this repo 2026-08-27: the
    LIST endpoint (`repos/<repo>/rulesets`) returns only id/name/target/
    enforcement — no `conditions`/`rules` — so each ruleset needs its own GET
    for the fields this check actually needs. Returns None (never a partial
    list) on ANY failure along the way: a partial ruleset set is worse than
    none, because it could make a real covering ruleset silently vanish from
    consideration and this check pass when it should have failed closed."""
    ok, out = _gh(["api", f"repos/{repo}/rulesets"])
    if not ok:
        return None
    try:
        summaries = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(summaries, list):
        return None

    detailed: list[dict] = []
    for summary in summaries:
        rid = summary.get("id") if isinstance(summary, dict) else None
        if rid is None:
            return None
        ok, out = _gh(["api", f"repos/{repo}/rulesets/{rid}"])
        if not ok:
            return None
        try:
            detailed.append(json.loads(out))
        except json.JSONDecodeError:
            return None
    return detailed


def load_minimum_contexts(path: Path) -> set[str] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    contexts = data.get("minimum_contexts")
    if not isinstance(contexts, list) or not contexts:
        return None
    if not all(isinstance(c, str) and c for c in contexts):
        return None
    return set(contexts)


# ------------------------------------------------------------- ref matching


def normalize_ref(ref: str, *, is_full_ref: bool) -> str:
    """Strips a leading `refs/heads/` ONLY when the caller asserts `ref` IS a
    full ref (`github.event.merge_group.base_ref`, which GitHub itself always
    populates as a full ref) — NEVER guessed from the string's own content.

    A cross-family refuter found the real bypass this guards against
    (2026-08-27): `github.base_ref` on `pull_request` events is ALWAYS a short
    name by GitHub's own contract, but a branch can legitimately be NAMED
    something that itself starts with the literal text `refs/heads/` (git
    permits slashes in branch names — `git push origin HEAD:refs/heads/refs
    /heads/main` creates exactly this). The previous version of this function
    stripped that prefix unconditionally whenever it was present, so a PR
    based on a real branch literally named `refs/heads/main` was silently
    treated as targeting the DEFAULT branch and exempted from every check.
    The fix is not a smarter guess — it's to never guess at all: the CALLER
    (the CI job, or a test) must say which shape it's handing in, because
    only the caller genuinely knows which GHA context field supplied it."""
    if not is_full_ref:
        return ref
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def _translate_ref_glob(pattern: str) -> re.Pattern[str]:
    """Compiles a GitHub ruleset ref-name glob to a regex matching GitHub's
    OWN documented semantics — Ruby's `File.fnmatch` with `FNM_PATHNAME`,
    verified against GitHub's docs (2026-08-27, a cross-family refuter caught
    this before it shipped): a single `*` does NOT cross a `/` (`qa/*`
    matches `qa/foo` but NOT `qa/foo/bar`); `**` DOES cross `/` (`qa/**/*`
    matches `qa/foo/bar/foobar/hello-world`). Python's stdlib `fnmatch`
    module has no FNM_PATHNAME equivalent — its `*` always crosses `/` — so
    using it directly (the original version of this function did) made a
    ruleset scoped to `refs/heads/feature/*` falsely appear to cover a nested
    branch like `feature/a/b` that GitHub itself would NOT apply that ruleset
    to: a false "protected" verdict on a branch that in fact is not. Hand-
    translated rather than adding a dependency, matching this repo's other
    CI scripts' "pure stdlib" preference (required_context_map.py)."""
    i, n = 0, len(pattern)
    out: list[str] = []
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("(?:" + "".join(out) + ")\\Z")


def _pattern_matches(pattern: str, ref_name: str, default_branch: str) -> bool:
    """One include/exclude pattern's verdict for this branch. GitHub ruleset
    ref-name conditions use two special tokens plus a path-aware glob (see
    `_translate_ref_glob`) evaluated against the FULL ref
    (`refs/heads/<name>`):
      - `~ALL`             matches every branch
      - `~DEFAULT_BRANCH`  matches only the repo's current default branch
      - anything else      a path-aware glob against `refs/heads/<ref_name>`
    Declared scope limit (same style as required_context_map.py's matrix
    scope): tag-ruleset tokens (`~ALL` for tags, etc.) are not handled — this
    module only ever evaluates `target: branch` rulesets (see
    `ruleset_covers_ref`), so a branch ref-name condition is all that reaches
    here in practice."""
    if pattern == "~ALL":
        return True
    if pattern == "~DEFAULT_BRANCH":
        return ref_name == default_branch
    return _translate_ref_glob(pattern).match(f"refs/heads/{ref_name}") is not None


def ruleset_covers_ref(ruleset: dict, ref_name: str, default_branch: str) -> bool:
    if ruleset.get("target") != "branch":
        return False
    if ruleset.get("enforcement") != "active":
        return False
    conditions = ruleset.get("conditions") or {}
    ref_name_cond = conditions.get("ref_name") or {}
    include = ref_name_cond.get("include") or []
    exclude = ref_name_cond.get("exclude") or []
    if not any(_pattern_matches(p, ref_name, default_branch) for p in include):
        return False
    if any(_pattern_matches(p, ref_name, default_branch) for p in exclude):
        return False
    return True


def required_status_check_contexts(ruleset: dict) -> set[str] | None:
    """The `required_status_checks` RULE inside a ruleset's `rules` array —
    NOT classic branch protection, and NOT necessarily present at all (main's
    own `merge-queue-main` ruleset carries none; see module docstring). None
    means "this ruleset has no such rule", distinct from an empty set (a rule
    present but declaring zero contexts, which would be its own kind of
    misconfiguration worth surfacing, though not one this module treats
    specially — it just contributes nothing to the coverage union)."""
    for rule in ruleset.get("rules") or []:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        checks = params.get("required_status_checks") or []
        return {c.get("context") for c in checks if isinstance(c, dict) and c.get("context")}
    return None


def suggest_pattern(base_ref: str) -> str:
    """Heuristic only, declared not resolved: the base ref's first path
    segment plus a wildcard (`feature/kb-current` -> `feature/*`). The printed
    operator command protects the WHOLE CLASS of branch this base belongs to
    — tomorrow's PR opens against a different branch name in the same family,
    and a ruleset scoped to today's exact branch name would silently miss it."""
    if "/" in base_ref:
        head, _rest = base_ref.split("/", 1)
        return f"{head}/*"
    return base_ref


# --------------------------------------------------------------------- core


def evaluate(
    base_ref: str,
    default_branch: str,
    rulesets: list[dict],
    minimum_contexts: set[str],
    *,
    is_full_ref: bool = False,
) -> tuple[int, str]:
    """Returns (exit_code, message). exit_code is 0 or 1 only — "cannot
    verify" is exit 1 too here (message-prefix distinguished as BLIND), per
    this check's own spec: both postures are "fail closed", not two
    different ones.

    `is_full_ref` MUST be set by the caller based on which GHA context field
    supplied `base_ref` (true only for `github.event.merge_group.base_ref`) —
    never inferred from the string, see `normalize_ref`'s own docstring for
    the bypass this guards against."""
    ref_name = normalize_ref(base_ref, is_full_ref=is_full_ref)

    if ref_name == default_branch:
        return (
            0,
            f"OK: base '{ref_name}' is the default branch — protected by main's "
            "own classic branch protection, out of this check's scope",
        )

    covering = [rs for rs in rulesets if ruleset_covers_ref(rs, ref_name, default_branch)]
    if not covering:
        return 1, _unprotected_message(ref_name, default_branch, missing=minimum_contexts, covering_names=[])

    have: set[str] = set()
    covering_names = [rs.get("name", "<unnamed>") for rs in covering]
    for rs in covering:
        ctxs = required_status_check_contexts(rs)
        if ctxs:
            have |= ctxs

    missing = minimum_contexts - have
    if missing:
        return 1, _unprotected_message(ref_name, default_branch, missing=missing, covering_names=covering_names)

    return (
        0,
        f"OK: base '{ref_name}' is covered by ruleset(s) {covering_names} carrying "
        f"all {len(minimum_contexts)} pinned required contexts",
    )


def _unprotected_message(
    base_ref: str, default_branch: str, missing: set[str], covering_names: list[str]
) -> str:
    pattern = suggest_pattern(base_ref)
    cmd = f"scripts/ci/setup_merge_queue_ruleset.sh --branch-pattern '{pattern}' --apply"
    if covering_names:
        coverage_note = (
            f"ruleset(s) {covering_names} cover refs/heads/{base_ref} but carry no "
            f"required_status_checks rule for: {sorted(missing)}"
        )
    else:
        coverage_note = f"no active branch ruleset covers refs/heads/{base_ref} at all"
    return (
        f"UNPROTECTED: base '{base_ref}' is not gated like '{default_branch}' — "
        f"{coverage_note}. 52 PRs merged into uncovered integration branches in "
        f"the 2026-08-25/26 window with zero required checks (ASSEMBLY-LINE.md). "
        f"To arm coverage: `{cmd}` (already includes --apply — this actually "
        f"creates the ruleset ACTIVE immediately, no separate enable step; drop "
        f"--apply to only preview the body first — operator[control-plane])"
    )


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="e.g. `github.base_ref` (pull_request) or `github.event.merge_group.base_ref`",
    )
    parser.add_argument(
        "--base-ref-full",
        action="store_true",
        help="assert that --base-ref is a FULL ref (refs/heads/...) — true only for "
        "merge_group's base_ref, which GitHub always populates as a full ref. Omit for "
        "a short branch name (pull_request's base_ref/base.ref), used VERBATIM and "
        "NEVER guessed at from its own content — a branch literally named "
        "'refs/heads/main' must not silently become 'main'.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="owner/name. Default: `gh repo view` (an extra live call — pass "
        "--repo '${{ github.repository }}' in CI, it's free)",
    )
    parser.add_argument(
        "--default-branch",
        default=None,
        help="Default: `gh api repos/<repo>` (an extra live call — pass "
        "--default-branch '${{ github.event.repository.default_branch }}' in CI, it's free)",
    )
    parser.add_argument("--min-contexts-json", default=str(DEFAULT_MIN_CONTEXTS_JSON))
    parser.add_argument(
        "--rulesets-json",
        default=None,
        help="test fixture: path to a JSON array of FULL ruleset objects "
        "(id/name/target/enforcement/conditions/rules), bypassing `gh` entirely",
    )
    args = parser.parse_args(argv)

    minimum_contexts = load_minimum_contexts(Path(args.min_contexts_json))
    if minimum_contexts is None:
        print(
            f"BLIND: {args.min_contexts_json} is missing, unparseable, or "
            "declares zero minimum_contexts"
        )
        return 1

    repo = resolve_repo(args.repo)
    if not repo:
        print("BLIND: could not resolve repo slug (pass --repo, or check `gh auth status`)")
        return 1

    default_branch = resolve_default_branch(repo, args.default_branch)
    if not default_branch:
        print(f"BLIND: could not resolve the default branch for {repo} (pass --default-branch)")
        return 1

    # SCOPE (module docstring: "the base==default-branch case always exits 0
    # without ever calling `gh api rulesets`") — this MUST be checked before
    # any rulesets fetch, not after. The original ordering called
    # fetch_live_rulesets()/read --rulesets-json unconditionally first, so a
    # PR into main itself paid an avoidable API call and could go BLIND on a
    # transient `gh` failure for the one case that never needed the network
    # (or a fixture file) at all. Caught 2026-08-27 by a test whose own
    # docstring claimed "no network call" while `_gh` was monkeypatched to
    # prove it — and, until this fix, it wasn't true. Reuses `evaluate()`
    # verbatim (with an empty rulesets list, which it never inspects on this
    # path) so the OK message has exactly one source of truth.
    if normalize_ref(args.base_ref, is_full_ref=args.base_ref_full) == default_branch:
        code, message = evaluate(
            args.base_ref, default_branch, [], minimum_contexts, is_full_ref=args.base_ref_full
        )
        print(message)
        return code

    if args.rulesets_json:
        try:
            rulesets = json.loads(Path(args.rulesets_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(f"BLIND: --rulesets-json {args.rulesets_json} is missing or unparseable")
            return 1
        if not isinstance(rulesets, list):
            print(f"BLIND: --rulesets-json {args.rulesets_json} is not a JSON array")
            return 1
    else:
        rulesets = fetch_live_rulesets(repo)
        if rulesets is None:
            print(
                f"BLIND: could not list/read rulesets for {repo} via `gh api` — "
                "a check that cannot see the rulesets must not certify the base"
            )
            return 1

    code, message = evaluate(
        args.base_ref,
        default_branch,
        rulesets,
        minimum_contexts,
        is_full_ref=args.base_ref_full,
    )
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
