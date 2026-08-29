#!/usr/bin/env python3
"""lint_hermetic_instruments.py — every declared MEASUREMENT INSTRUMENT must
run through scripts/hermetic_verify.sh, in every workflow that invokes it.

WHY THIS EXISTS (cicatrix-scars.md W121, "mutation testing on poisoned
bytecode"). A measurement instrument is any tool whose OUTPUT IS A NUMBER
SOMEONE QUOTES — a mutation-testing score, a kill count, a coverage delta.
`scripts/mutation_incremental.py` is exactly this class: it mutates and
restores source files in the shape W121 measured as corruptible (same byte
length, same-second restore), and at authoring time it carried ZERO
occurrences of PYTHONDONTWRITEBYTECODE / dont_write_bytecode / __pycache__ /
cacheprovider — every number it had ever produced was exposed to stale
bytecode reuse, silently, in either direction (a survivor reported as a
kill, or a kill reported as a survivor). `scripts/hermetic_verify.sh` is the
cure: it exports the write-suppression env, sweeps stale caches, and proves
(a self-canary reproducing W121's exact shape) that the environment it hands
to a wrapped command cannot reuse stale bytecode. This lint is the guard
that a NEXT instrument — or a future edit to an existing one — does not
regress back to running bare, unwrapped, in a workflow.

WHAT THIS DOES: for every tracked `.github/workflows/*.yml`/`*.yaml`
(`git ls-files`, never a bare glob — same rule as
check_required_workflow_conformance.py and lint_unreachable_workflow_
conditions.py: judge only what git tracks), the file is split into `run:`
BLOCKS by line + indentation only (never a YAML-semantic parse — this is a
deliberately textual, line-based rule, not a YAML analyser: a `run:` key
(optionally preceded by a YAML list-item `- ` marker, the `- run: ...`
shape) followed by a non-block-scalar remainder is a one-line block; a
`run: |`/
`run: >` (with an optional `-`/`+` chomping indicator) starts a block-scalar
whose content lines are every subsequent line indented strictly more than
the `run:` key, stopping at the first non-blank line that is not). Within
each block, every occurrence of a declared instrument's path is required to
have an occurrence of `scripts/hermetic_verify.sh` EARLIER in that SAME
block — an earlier line, or an earlier column on the same line (the wrapped
single-line shape: `python3 scripts/hermetic_verify.sh -- python3
scripts/mutation_incremental.py -v`). An instrument mention with no such
earlier wrapper mention in its own block is a violation; a wrapper mention
occurring only AFTER the instrument mention (out of order) does not excuse
it — the instrument already ran unprotected before the wrapper is invoked.

DECLARED SCOPE LIMIT: this is a textual substring/position rule, not a
shell parser — it cannot see that an instrument mention lives inside a
quoted string being merely echoed, or that a `hermetic_verify.sh` mention on
an earlier line belongs to an unrelated, already-exited subshell. Both are
rare in this repo's workflow style (a `run:` step's lines are one
sequential shell script) and the bias is toward FALSE POSITIVES (reporting
a wrapped call as unwrapped) rather than false negatives, which is the
safer direction for a guard whose job is catching an unwrapped instrument.

Blind-scan guard (W84 "esiste ≠ armato"): zero tracked workflow files
scanned, or an empty INSTRUMENTS tuple, is CANNOT VERIFY, never a clean
pass. A declared instrument whose path does not exist on disk is also
CANNOT VERIFY — a lint guarding a file that no longer exists is guarding
nothing.

Usage:
    python3 scripts/ci/lint_hermetic_instruments.py [--repo-root .]
    python3 scripts/ci/lint_hermetic_instruments.py --selftest

Exit codes: 0 clean · 1 one or more unwrapped instrument invocations found ·
3 CANNOT VERIFY (zero workflows scanned, INSTRUMENTS empty, or a declared
instrument path missing from disk).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Grows as instruments are added — each entry is a tool whose OUTPUT IS A
# NUMBER SOMEONE QUOTES, exactly the class W121 corrupts.
INSTRUMENTS: tuple[str, ...] = ("scripts/mutation_incremental.py",)

WRAPPER = "scripts/hermetic_verify.sh"

_RUN_KEY_RE = re.compile(r"^(?P<indent>[ \t]*)(?:-\s+)?run:\s*(?P<rest>.*)$")
_BLOCK_SCALAR_RE = re.compile(r"^[|>][+-]?\s*$")


@dataclass(frozen=True)
class RunBlock:
    file: str
    lines: tuple[tuple[int, str], ...]  # (1-based line number, full line text)


def find_run_blocks(text: str, file_label: str) -> list[RunBlock]:
    """Splits a workflow's raw text into `run:` blocks by indentation only —
    no YAML-semantic parse (module docstring, "WHAT THIS DOES")."""
    lines = text.splitlines()
    blocks: list[RunBlock] = []
    i, n = 0, len(lines)
    while i < n:
        m = _RUN_KEY_RE.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group("indent"))
        rest = m.group("rest").strip()
        if rest and not _BLOCK_SCALAR_RE.match(rest):
            blocks.append(RunBlock(file_label, ((i + 1, lines[i]),)))
            i += 1
            continue
        content: list[tuple[int, str]] = [(i + 1, lines[i])]
        j = i + 1
        while j < n:
            nxt = lines[j]
            if nxt.strip() == "":
                content.append((j + 1, nxt))
                j += 1
                continue
            if len(nxt) - len(nxt.lstrip(" \t")) <= indent:
                break
            content.append((j + 1, nxt))
            j += 1
        blocks.append(RunBlock(file_label, tuple(content)))
        i = j
    return blocks


def _strip_shell_comment(text: str) -> str:
    """Everything before the first unquoted `#`, with the tail blanked out.

    The tail is replaced by spaces rather than removed so every surviving
    character keeps its original column — the caller compares wrapper and
    instrument positions on the same line, and shifting them would silently
    reorder the two.
    """
    in_single = in_double = False
    for i, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return text[:i] + " " * (len(text) - i)
    return text


def find_unwrapped_mentions(block: RunBlock, instruments: tuple[str, ...]) -> list[str]:
    """Every instrument mention in `block` with no `WRAPPER` mention earlier
    in the SAME block (earlier line, or earlier column on the same line)."""
    # A wrapper mention inside a `#` comment is not an invocation. Without
    # this, `# scripts/hermetic_verify.sh -- disabled for now` above a bare
    # instrument call reads as protection and the lint exits 0 — measured.
    # That is the same form-for-entity substitution this lint exists to stop,
    # committed inside the lint. Shell comments only: everything after an
    # unquoted `#` on a line cannot execute.
    wrapper_positions = [
        (line_no, m.start())
        for line_no, text in block.lines
        for m in re.finditer(re.escape(WRAPPER), _strip_shell_comment(text))
    ]

    def wrapped_before(line_no: int, col: int) -> bool:
        return any(wl < line_no or (wl == line_no and wc < col) for wl, wc in wrapper_positions)

    violations: list[str] = []
    for line_no, text in block.lines:
        live = _strip_shell_comment(text)
        for instrument in instruments:
            for m in re.finditer(re.escape(instrument), live):
                if not wrapped_before(line_no, m.start()):
                    violations.append(f"{block.file}:{line_no}: {text.strip()}")
    return violations


def evaluate_workflows(
    workflow_paths: list[Path], instruments: tuple[str, ...]
) -> list[str]:
    violations: list[str] = []
    for path in workflow_paths:
        text = path.read_text(encoding="utf-8")
        for block in find_run_blocks(text, str(path)):
            violations.extend(find_unwrapped_mentions(block, instruments))
    return violations


def discover_tracked_workflows(repo_root: Path) -> list[Path] | None:
    """None on any failure to enumerate — never an empty list a caller could
    mistake for 'zero workflows, all clean' (W84)."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--", ".github/workflows/*.yml", ".github/workflows/*.yaml"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return sorted(repo_root / line for line in proc.stdout.splitlines() if line.strip())


# ------------------------------------------------------------------- selftest


def selftest() -> int:
    """Guilt: instrument invoked bare in its own run: block -> violation.
    Innocence: the same call routed through the wrapper (same line, earlier
    column) -> clean. Innocence: a workflow that never mentions the
    instrument at all -> clean."""
    instrument = "scripts/fake_instrument_for_selftest.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "scripts").mkdir()
        (root / "scripts" / "fake_instrument_for_selftest.py").write_text("# fixture\n")
        wf_dir = root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)

        (wf_dir / "guilty.yml").write_text(
            "jobs:\n  x:\n    steps:\n      - run: python3 " + instrument + " -v\n"
        )
        (wf_dir / "innocent-wrapped.yml").write_text(
            "jobs:\n  x:\n    steps:\n      - run: python3 "
            + WRAPPER
            + " -- python3 "
            + instrument
            + " -v\n"
        )
        (wf_dir / "innocent-unrelated.yml").write_text(
            "jobs:\n  x:\n    steps:\n      - run: echo hello\n"
        )

        workflows = sorted(wf_dir.glob("*.yml"))
        if len(workflows) != 3:
            print(f"selftest FAILED — fixture setup wrote {len(workflows)} workflow(s), expected 3")
            return 1

        violations = evaluate_workflows(workflows, (instrument,))
        bad = [v for v in violations if "guilty.yml" not in v]
        if bad:
            print(f"selftest FAILED — innocence violated: {bad}")
            return 1
        hits = [v for v in violations if "guilty.yml" in v]
        if not hits:
            print("selftest FAILED — guilt fixture (bare instrument call) went undetected")
            return 1

    print(f"selftest OK — {len(hits)} guilt finding(s), 0 false positive(s) on 2 innocent fixtures")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--selftest", action="store_true", help="run guilt+innocence fixtures and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    repo_root = Path(args.repo_root).resolve()

    if not INSTRUMENTS:
        print("lint_hermetic_instruments: CANNOT VERIFY — INSTRUMENTS is empty (an empty scan is not a pass)", file=sys.stderr)
        return 3

    missing = [i for i in INSTRUMENTS if not (repo_root / i).exists()]
    if missing:
        print(
            f"lint_hermetic_instruments: CANNOT VERIFY — declared instrument path(s) do not exist on disk: "
            f"{', '.join(missing)} (a lint guarding a deleted file guards nothing)",
            file=sys.stderr,
        )
        return 3

    workflows = discover_tracked_workflows(repo_root)
    if workflows is None:
        print("lint_hermetic_instruments: CANNOT VERIFY — `git ls-files` failed", file=sys.stderr)
        return 3
    if not workflows:
        print("lint_hermetic_instruments: CANNOT VERIFY — zero tracked workflow files found", file=sys.stderr)
        return 3

    violations = evaluate_workflows(workflows, INSTRUMENTS)

    print(
        f"lint_hermetic_instruments: {len(workflows)} workflow(s) scanned, "
        f"{len(INSTRUMENTS)} instrument(s) tracked, {len(violations)} violation(s)"
    )
    for v in violations:
        print(f"  ✗ {v}")
    if not violations:
        print(f"  ✓ every instrument invocation runs through {WRAPPER}")
        return 0
    print(f"\n  A measurement instrument invoked without {WRAPPER} may be measuring stale bytecode, not the diff (W121).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
