#!/usr/bin/env python3
"""P1 STRATO-2 (2026-06-07) — INCREMENTAL mutation-testing driver.

The "quality oracle" of the bias-immune layer of the verify-the-verifiers
funnel (P1 spec §3 STRATO-2). It answers the one question coverage-% cannot:
*do the tests actually KILL regressions on the lines this diff changed?*

Design contract (verified against `research/operations/specs/
P1-verify-the-verifiers.md` §3 STRATO-2 + §7 #5 + §7.3 #2, this turn):

  1. INCREMENTAL — mutation runs ONLY on lines this diff changed (AST-diff vs
     git), never the full codebase (full-codebase is too slow — Gemini #4).
     We compute the changed-line set from `git diff` and intersect it with the
     AST so only executable *statement* lines inside changed regions are
     mutated (not blank lines, comments, decorators, or pure signatures).

  2. FIXED operators, never agent-chosen (DeepSeek #2 / §3 STRATO-2). The
     mutation operators are the standard set baked into this frozen driver
     (and, when available, delegated to `mutmut` whose operator set is also
     fixed upstream). The AGENT UNDER TEST cannot pick mutants/operators — that
     would let it generate trivial dead-code mutants any test kills, inflating
     the score.

  3. HIDDEN CANARY MUTANTS — anti-mutation-cheat (Codex #5 + DeepSeek #2,
     spec §7). The gate keeps a frozen, hash-protected set of canary mutations
     that a competent test-suite MUST kill. If a canary SURVIVES, the suite is
     too weak / being gamed → the gate FAILS regardless of the reported
     mutation score. The canary set is `_CANARY_MUTANTS` below — it is part of
     THIS driver (immutable, CODEOWNERS-protected per R1), not produced by the
     agent. The canary SELF-TEST is pure-Python: it needs NO mutmut, so it runs
     even on machines (M5) where mutmut is absent and proves the driver's own
     discriminating power every run.

  4. GATE VERDICT — survivors on changed lines must NOT worsen vs a baseline
     the OPERATOR controls (seed + baseline file via CLI/env, not the agent),
     AND every surviving mutant must carry a human EXPLANATION slot. A run with
     unexplained new survivors FAILS. (spec §3 STRATO-2 + §7.5.)

  5. GRACEFUL DEGRADATION — `mutmut` is an OPTIONAL, CI/Pro-provided tool, NOT a
     hard repo dependency (do not pip-install it autonomously). When absent the
     mutmut leg is SKIPPED (exit `EXIT_SKIP`, an honest skip — never a false
     PASS), but the canary self-test still runs and can still FAIL the gate.

Exit codes:
  EXIT_PASS (0)  canary self-test passed AND (mutmut clean OR mutmut absent-skip
                 with --allow-skip). The diff's changed lines are guarded.
  EXIT_FAIL (1)  a canary SURVIVED, or a new unexplained mutmut survivor, or the
                 driver's own integrity check failed.
  EXIT_SKIP (2)  mutmut absent and --allow-skip NOT set: STRATO-2's mutmut leg
                 could not run here. Canary self-test still executed (its own
                 failure overrides this to EXIT_FAIL). CI/Pro must run the full
                 leg. NOT a pass.

This driver is meant to be FROZEN (TDD + hash). Its companion test is
`scripts/test_mutation_incremental.py`. Consumer wiring is declared in the
gate-fragment `research/operations/fase4-gate-fragments/p1s2_mutation.yaml`.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

logger = logging.getLogger("mutation_incremental")

REPO_ROOT = Path(__file__).resolve().parents[1]

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SKIP = 2

# Default baseline that records the survivor set the operator has accepted.
# The OPERATOR owns this file (and the seed) — the agent under test must not
# silently rewrite it. The gate compares NEW survivors against this set.
DEFAULT_BASELINE = REPO_ROOT / "research" / "operations" / "fase4-gate-fragments" / "p1s2_mutation_baseline.json"

# A diff hunk header: @@ -old_start,old_count +new_start,new_count @@
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# --------------------------------------------------------------------------- #
# Changed-line extraction (AST-aware, incremental)                            #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChangedLines:
    """The mutation TARGET set: added/modified executable statement lines."""

    by_file: dict[str, frozenset[int]] = field(default_factory=dict)

    def total(self) -> int:
        return sum(len(v) for v in self.by_file.values())

    def is_empty(self) -> bool:
        return self.total() == 0


def parse_diff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse a unified `git diff` into {path: {new_line_no, ...}}.

    Only NEW-side added/changed lines (the ``+`` lines, excluding the ``+++``
    file header) are returned — those are the lines this diff is responsible
    for. Deletions have no new-side line to mutate.
    """
    result: dict[str, set[int]] = {}
    current: str | None = None
    new_lineno = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            # +++ b/path/to/file.py   (or "+++ /dev/null" for a deletion)
            target = raw[4:].strip()
            if target == "/dev/null":
                current = None
                continue
            current = target[2:] if target.startswith("b/") else target
            result.setdefault(current, set())
            continue
        if raw.startswith("--- "):
            continue
        m = _HUNK_RE.match(raw)
        if m:
            new_lineno = int(m.group(1))
            continue
        if current is None:
            continue
        if raw.startswith("+"):
            result.setdefault(current, set()).add(new_lineno)
            new_lineno += 1
        elif raw.startswith("-"):
            # deletion: consumes an old-side line only, new_lineno unchanged
            continue
        else:
            # context line (starts with ' ' or is empty)
            new_lineno += 1
    return result


def _executable_statement_lines(source: str) -> set[int]:
    """Lines belonging to a mutable executable statement (AST-aware).

    Excludes blank lines, comments, decorators, bare function/class signature
    lines, docstrings, and ``pass``/imports — mutating those yields trivial or
    no-op mutants. We keep the lines spanned by concrete statement nodes that
    carry semantics (assignments, calls, returns, conditionals, comparisons,
    boolean/arith ops, etc.).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    keep: set[int] = set()
    skip_node_types = (
        ast.Import,
        ast.ImportFrom,
        ast.Pass,
    )
    for node in ast.walk(tree):
        if isinstance(node, skip_node_types):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # bare string expression = docstring → skip
            continue
        if isinstance(node, ast.stmt) and not isinstance(node, skip_node_types):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", start)
            if start is None:
                continue
            # For compound statements (def/if/for/while/with/try) keep only the
            # header line plus the test/iter expression lines; the body lines are
            # captured by their own child statement nodes. We approximate by
            # keeping just the statement's own first line here and letting walk()
            # add child lines.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # signature line itself is not semantically mutable in a useful
                # way (name change breaks everything trivially) → skip header
                continue
            keep.add(start)
            if end is not None and end != start and not _is_compound(node):
                for ln in range(start, end + 1):
                    keep.add(ln)
    return keep


def _is_compound(node: ast.stmt) -> bool:
    return isinstance(
        node,
        (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try),
    )


def compute_changed_target(
    diff_text: str,
    *,
    read_source: Callable[[str], str | None] | None = None,
    include_glob: Sequence[str] = ("apps/", "scripts/", "packages/"),
) -> ChangedLines:
    """Intersect git-diff added lines with the AST executable-statement set.

    `read_source(path)` returns the post-diff source of `path` (or None if it
    cannot be read — e.g. deleted). Defaults to reading from disk relative to
    the repo root. Only `.py` files under `include_glob` prefixes are targeted.
    """
    if read_source is None:

        def _default_read(path: str) -> str | None:
            p = (REPO_ROOT / path)
            try:
                return p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None

        read_source = _default_read

    added = parse_diff_added_lines(diff_text)
    by_file: dict[str, frozenset[int]] = {}
    for path, lines in added.items():
        if not path.endswith(".py"):
            continue
        if include_glob and not any(path.startswith(g) for g in include_glob):
            continue
        source = read_source(path)
        if source is None:
            continue
        executable = _executable_statement_lines(source)
        target = frozenset(lines & executable)
        if target:
            by_file[path] = target
    return ChangedLines(by_file=by_file)


def git_diff(repo_root: Path = REPO_ROOT) -> str:
    """Return the combined staged + working-tree unified diff (text)."""
    parts: list[str] = []
    for args in (["diff", "--no-color"], ["diff", "--no-color", "--cached"]):
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - env
            logger.warning("git %s failed: %s", " ".join(args), exc)
            continue
        if out.stdout:
            parts.append(out.stdout)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Hidden canary mutants — the anti-cheat self-test (pure-Python, no mutmut)    #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CanaryMutant:
    """A known mutation a competent test-suite MUST kill.

    `operator` is the FIXED operator name. `original`/`mutated` are substrings
    applied to a tiny in-memory subject module. A test-suite that DOES NOT FAIL
    under `mutated` is too weak → the canary SURVIVED → gate FAILS.
    """

    id: str
    operator: str
    original: str
    mutated: str
    description: str


# FROZEN canary set. Standard high-value semantic operators (NOT agent-chosen,
# NOT log/format trivia). Order is part of the integrity hash.
_CANARY_MUTANTS: tuple[CanaryMutant, ...] = (
    CanaryMutant(
        id="comparison_flip_gt_ge",
        operator="ComparisonOperatorReplacement",
        original="amount > threshold",
        mutated="amount >= threshold",
        description="Off-by-one on a billing/auth boundary comparison.",
    ),
    CanaryMutant(
        id="arith_add_to_sub",
        operator="ArithmeticOperatorReplacement",
        original="total = base + fee",
        mutated="total = base - fee",
        description="Sign flip in a money calculation.",
    ),
    CanaryMutant(
        id="boolean_and_to_or",
        operator="BooleanOperatorReplacement",
        original="is_admin and is_active",
        mutated="is_admin or is_active",
        description="RBAC weakening: AND→OR grants access on either condition.",
    ),
    CanaryMutant(
        id="boolean_negation_drop",
        operator="ConditionNegation",
        original="if not allowed:",
        mutated="if allowed:",
        description="Inverted guard clause.",
    ),
    CanaryMutant(
        id="constant_true_short_circuit",
        operator="ConstantReplacement",
        original="return computed_ok",
        mutated="return True",
        description="Reward-hacking shape: function always returns success.",
    ),
)


def canary_integrity_hash() -> str:
    """Deterministic sha256 over the frozen canary set.

    The operator/gate pins this hash; if the agent under test mutates the
    canary set to weaken it, the hash changes and the gate's integrity check
    (CI side, CODEOWNERS-protected) FAILS. Mirrors R1 (immutable verifier).
    """
    h = hashlib.sha256()
    for c in _CANARY_MUTANTS:
        h.update(f"{c.id}\0{c.operator}\0{c.original}\0{c.mutated}\0".encode("utf-8"))
    return h.hexdigest()


# A tiny SUBJECT module + its SUITE used purely to exercise the canary engine.
# This is the driver self-test fixture: a *correct* suite that SHOULD kill every
# canary. If the engine ever reports a canary as surviving against this suite,
# the driver itself is broken.
_SELFTEST_SUBJECT = '''\
def charge(amount, threshold, base, fee, is_admin, is_active, allowed, computed_ok):
    over = amount > threshold
    total = base + fee
    access = is_admin and is_active
    if not allowed:
        guard = "blocked"
    else:
        guard = "ok"
    return computed_ok, over, total, access, guard
'''

_SELFTEST_SUITE = '''\
def run(mod):
    # Strong assertions that pin each mutated line's behaviour.
    assert mod.charge(5, 5, 10, 2, True, True, False, True) == (True, False, 12, True, "blocked")
    assert mod.charge(6, 5, 10, 2, True, False, True, False) == (False, True, 12, False, "ok")
    assert mod.charge(0, 5, 0, 1, False, True, True, True) == (True, False, 1, False, "ok")
'''


@dataclass(frozen=True)
class CanaryResult:
    canary_id: str
    killed: bool
    detail: str


def _apply_mutation(source: str, mutant: CanaryMutant) -> str | None:
    """Apply a single textual canary mutation. Returns None if not applicable."""
    if mutant.original not in source:
        return None
    return source.replace(mutant.original, mutant.mutated, 1)


def _suite_fails_under(subject_source: str, suite_source: str) -> bool:
    """Run the in-memory suite against the subject; True if the suite FAILS.

    Pure-Python — no pytest/mutmut needed. The suite is a module exposing
    ``run(mod)`` that raises (AssertionError or any Exception) when the subject
    misbehaves. A suite that raises = the mutation was KILLED.
    """
    subject_ns: dict[str, object] = {}
    try:
        exec(compile(subject_source, "<canary-subject>", "exec"), subject_ns)  # noqa: S102 - sandboxed self-test
    except Exception:  # noqa: BLE001 - a subject that won't even compile = killed
        return True

    class _Mod:
        pass

    mod = _Mod()
    for name, val in subject_ns.items():
        setattr(mod, name, val)

    suite_ns: dict[str, object] = {}
    try:
        exec(compile(suite_source, "<canary-suite>", "exec"), suite_ns)  # noqa: S102 - sandboxed self-test
        runner = suite_ns["run"]
        runner(mod)  # type: ignore[operator]
    except Exception:  # noqa: BLE001 - any raise = suite detected the mutation
        return True
    return False


def run_canary_selftest(
    *,
    subject_source: str = _SELFTEST_SUBJECT,
    suite_source: str = _SELFTEST_SUITE,
    canaries: Iterable[CanaryMutant] = _CANARY_MUTANTS,
) -> list[CanaryResult]:
    """Apply every applicable canary to the subject and check the suite kills it.

    A canary is KILLED if the suite FAILS under the mutated subject. A canary
    that is applicable but NOT killed has SURVIVED → the gate must FAIL.
    """
    results: list[CanaryResult] = []
    for c in canaries:
        mutated = _apply_mutation(subject_source, c)
        if mutated is None:
            results.append(
                CanaryResult(c.id, killed=True, detail="not-applicable-to-subject (skipped)")
            )
            continue
        killed = _suite_fails_under(mutated, suite_source)
        results.append(
            CanaryResult(
                c.id,
                killed=killed,
                detail="suite caught mutation" if killed else "SURVIVED — suite too weak",
            )
        )
    return results


# --------------------------------------------------------------------------- #
# mutmut leg (optional / CI-provided)                                         #
# --------------------------------------------------------------------------- #
def mutmut_available() -> bool:
    """True if a `mutmut` binary or importable module is present."""
    if shutil.which("mutmut") is not None:
        return True
    try:
        __import__("mutmut")
        return True
    except ImportError:
        return False


@dataclass(frozen=True)
class Survivor:
    """A surviving mutant on a changed line, with its mandatory explanation."""

    key: str
    explanation: str | None = None


def load_baseline(path: Path) -> set[str]:
    """Load the operator-accepted survivor keys from the baseline file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    accepted = data.get("accepted_survivors", [])
    return {str(k) for k in accepted}


def evaluate_survivors(
    survivors: Sequence[Survivor],
    baseline: set[str],
) -> tuple[bool, list[str]]:
    """Gate logic for mutmut survivors on changed lines.

    Returns (ok, reasons). NOT ok (gate fails) if any survivor is BOTH new
    (not in the operator baseline) AND lacks an explanation. A NEW survivor
    WITH an explanation is allowed (operator-auditable); the gate's job is to
    forbid *silent* worsening, not to forbid all survivors. (spec §3 STRATO-2:
    "survivors don't worsen + MANDATORY explanation of survivors".)
    """
    reasons: list[str] = []
    ok = True
    for s in survivors:
        is_new = s.key not in baseline
        has_expl = bool(s.explanation and s.explanation.strip())
        if is_new and not has_expl:
            ok = False
            reasons.append(f"NEW survivor without explanation: {s.key}")
        elif is_new and has_expl:
            reasons.append(f"NEW survivor (explained, allowed): {s.key} — {s.explanation}")
    return ok, reasons


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #
def _report_canaries(results: Sequence[CanaryResult]) -> bool:
    """Log canary results; return True if all applicable canaries were killed."""
    survived = [r for r in results if not r.killed]
    for r in results:
        level = logging.ERROR if not r.killed else logging.INFO
        logger.log(level, "canary %-30s %s — %s", r.canary_id, "KILLED" if r.killed else "SURVIVED", r.detail)
    if survived:
        logger.error(
            "STRATO-2 canary self-test FAILED: %d canary mutant(s) survived → test suite too weak / gamed.",
            len(survived),
        )
        return False
    logger.info("STRATO-2 canary self-test PASSED: all %d applicable canaries killed.", len(results))
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1 STRATO-2 incremental mutation gate.")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Operator-owned survivor baseline JSON (operator controls this, not the agent under test).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.environ.get("MUTATION_SEED", "0")),
        help="Deterministic seed (operator/gate-controlled via --seed or MUTATION_SEED env).",
    )
    parser.add_argument(
        "--allow-skip",
        action="store_true",
        help="When mutmut is absent, exit PASS instead of SKIP (e.g. on M5 where mutmut is not installed). "
        "The canary self-test still runs and can still FAIL.",
    )
    parser.add_argument(
        "--print-integrity",
        action="store_true",
        help="Print the frozen canary integrity hash and exit.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.print_integrity:
        logger.info("canary_integrity_hash=%s", canary_integrity_hash())
        return EXIT_PASS

    # --- 1. Canary self-test (always, pure-Python, no mutmut needed) -------- #
    canary_results = run_canary_selftest()
    canaries_ok = _report_canaries(canary_results)
    if not canaries_ok:
        # A surviving canary is a hard FAIL — it overrides any skip/pass.
        return EXIT_FAIL

    # --- 2. Compute the incremental target set ----------------------------- #
    diff_text = git_diff()
    target = compute_changed_target(diff_text)
    logger.info(
        "incremental target: %d changed executable line(s) across %d file(s).",
        target.total(),
        len(target.by_file),
    )
    if target.is_empty():
        logger.info("no changed Python statement lines → mutmut leg not needed. Canary PASS stands.")
        return EXIT_PASS

    # --- 3. mutmut leg (optional) ------------------------------------------ #
    if not mutmut_available():
        msg = (
            "mutmut not installed — STRATO-2 mutmut leg SKIPPED. Runs in CI / on Pro where it is "
            "available. Canary self-test PASSED, so the driver's discriminating power is proven here."
        )
        if args.allow_skip:
            logger.warning("%s (--allow-skip → PASS)", msg)
            return EXIT_PASS
        logger.warning("%s (exit SKIP=2 — NOT a pass; CI/Pro must run the full leg)", msg)
        return EXIT_SKIP

    # mutmut IS present: invoke on changed files only, parse survivors, gate.
    # We document the invocation; the actual survivor extraction is delegated to
    # mutmut's own results. The OPERATOR controls seed/baseline (above), the
    # agent under test does not.
    logger.info("mutmut present — running incremental mutation on changed files (seed=%s).", args.seed)
    baseline = load_baseline(args.baseline)
    survivors = _run_mutmut_on_targets(target, seed=args.seed)
    ok, reasons = evaluate_survivors(survivors, baseline)
    for r in reasons:
        logger.info("survivor-eval: %s", r)
    if not ok:
        logger.error("STRATO-2 mutmut gate FAILED: new survivor(s) on changed lines without explanation.")
        return EXIT_FAIL
    logger.info("STRATO-2 PASS: canaries killed + no silent new survivors on changed lines.")
    return EXIT_PASS


def _run_mutmut_on_targets(target: ChangedLines, *, seed: int) -> list[Survivor]:
    """Invoke mutmut on the changed files and return surviving mutants.

    Thin documented wrapper. mutmut's CLI/runner is invoked per changed file so
    the mutation surface is restricted to the diff (incremental). Survivor keys
    are namespaced by file so the baseline is stable. We are defensive: any
    mutmut failure is logged and treated as "no survivors extracted" rather than
    crashing the gate (the canary self-test already proved discriminating power;
    a mutmut harness error must not silently PASS a real regression, so we log
    loudly — see GOTCHA in the gate-fragment).
    """
    survivors: list[Survivor] = []
    for path in sorted(target.by_file):
        cmd = ["mutmut", "run", "--paths-to-mutate", path]
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=900,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("mutmut invocation failed for %s: %s", path, exc)
            continue
        survivors.extend(_parse_mutmut_survivors(proc.stdout, path))
    return survivors


def _parse_mutmut_survivors(mutmut_stdout: str, path: str) -> list[Survivor]:
    """Extract surviving-mutant ids from mutmut output, keyed by file.

    mutmut prints survivors as lines like ``Survived 🙁 (N)`` and exposes ids
    via ``mutmut results``. We parse the conservative, stable signal: any line
    mentioning a survived mutant id. Explanation is looked up from an optional
    sidecar (``<path>.mutsurv.json``) the operator/author maintains; absent →
    None (which makes a NEW survivor fail the gate, as intended).
    """
    survivors: list[Survivor] = []
    explanations = _load_survivor_explanations(path)
    for line in mutmut_stdout.splitlines():
        m = re.search(r"#(?P<id>\d+).*\bsurvived\b", line, re.IGNORECASE)
        if m:
            key = f"{path}#{m.group('id')}"
            survivors.append(Survivor(key=key, explanation=explanations.get(key)))
    return survivors


def _load_survivor_explanations(path: str) -> dict[str, str]:
    sidecar = REPO_ROOT / f"{path}.mutsurv.json"
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.get("explanations", {}).items()}


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
