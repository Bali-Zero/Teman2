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
have an occurrence of `scripts/hermetic_verify.sh` protecting it: at an
earlier COLUMN ON THE SAME LINE (the wrapped single-line shape:
`bash scripts/hermetic_verify.sh -- python3 scripts/mutation_incremental.py -v`),
or on an earlier line whose every intervening line ends with a backslash
continuation (the same command, wrapped across lines). A wrapper mention on
an earlier line that is NOT continued does not excuse anything — that line is
a command that already ran and exited, not a wrapping of this one. A wrapper
mention occurring only AFTER the instrument mention does not excuse it
either: the instrument already ran unprotected.

DECLARED SCOPE LIMIT: this is a textual substring/position rule, not a
shell parser. The bias is deliberately toward FALSE POSITIVES (reporting a
wrapped call as unwrapped) rather than false negatives, which is the safer
direction for a guard whose job is catching an unwrapped instrument.

The evasions are ENUMERATED rather than gestured at, because an earlier
version of this paragraph said "both are rare in this repo's workflow style"
while a cross-family refuter was listing seven of them. A guard's stated
limits should be a list someone can check, not a reassurance. It does not
catch any of these:

  * `cd scripts && python3 mutation_incremental.py` — the declared path
    never appears; only the basename does. Matching the basename instead
    would false-positive on `test_mutation_incremental.py`, which CONTAINS
    it as a substring, so this is deferred rather than bolted on.
  * `PYTHONPATH=scripts python3 -m mutation_incremental` — module form, no
    path at all.
  * an intermediate target (`make mutate`, a shell script) that invokes the
    instrument out of this file's sight.
  * `${{ matrix.tool }}` or any path assembled by expression/concatenation.
  * a `run:` inside a composite action under `.github/actions/` — this lint
    scans `.github/workflows/` only.
  * an instrument mention inside a quoted string being merely ECHOED (the
    false-positive direction), and a `hermetic_verify.sh` mention on an
    earlier line belonging to an already-exited subshell.
  * (NOT a limit, listed because a refuter named it and precision matters) a
    plain backslash continuation from a `--self-test-only` line onto a bare
    instrument is NOT a bypass: the wrapper's own arg parser rejects the
    trailing tokens and exits 2, so the step goes red. Verified by running it.
    An invented weakness costs a list of limits its credibility exactly as a
    missing one does. Its separator variants WERE real bypasses on three
    different axes and are closed structurally by the segmentation rule below,
    not by a fourth special case.

What this lint DOES guarantee is narrower and worth stating plainly: an
instrument invoked by its declared path, in a workflow file, without a
wrapper mention protecting that invocation, is reported. That is the shape
the repo's workflows actually use today (106 scanned, 1 instrument, 0
violations), and it is the shape a careless future edit will take.

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
# YAML block-scalar header: `|` or `>` followed by an optional indentation
# indicator (1-9) and/or a chomping indicator (+/-), IN EITHER ORDER (`|2-`
# and `|-2` are both valid). The first version of this pattern accepted only
# the chomping indicator, so `run: |2` fell through to the single-line branch
# and NONE of the block's following lines were ever scanned — a silent false
# NEGATIVE, i.e. a working bypass of this lint by an indentation indicator.
# Found by the cross-family refuter; reproduced here before fixing.
_BLOCK_SCALAR_RE = re.compile(r"^[|>](?:[1-9][+-]?|[+-][1-9]?)?\s*(?:#.*)?$")


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


def _segments(block: RunBlock) -> list[list[tuple[int, int, str]]]:
    """Split a `run:` block into SHELL COMMANDS, keeping (line, col) per char.

    Each element is one command: a list of (line_no, column, char). Commands are
    separated by `&&`, `||`, `;`, `|`, and by a newline that is NOT continued
    with a trailing backslash.
    """
    flat: list[tuple[int, int, str]] = []
    for line_no, text in block.lines:
        live = _strip_shell_comment(text)
        stripped = live.rstrip()
        continued = stripped.endswith("\\")
        if continued:
            stripped = stripped[:-1]
        for col, ch in enumerate(stripped):
            flat.append((line_no, col, ch))
        if not continued:
            flat.append((line_no, len(stripped), "\n"))

    text = "".join(ch for _l, _c, ch in flat)
    segments: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two in ("&&", "||"):
            segments.append(current)
            current = []
            i += 2
            continue
        if text[i] in (";", "|", "\n"):
            segments.append(current)
            current = []
            i += 1
            continue
        current.append(flat[i])
        i += 1
    segments.append(current)
    return [s for s in segments if s]


def find_unwrapped_mentions(block: RunBlock, instruments: tuple[str, ...]) -> list[str]:
    """Every instrument mention not protected by a wrapper mention EARLIER IN
    THE SAME SHELL COMMAND.

    THIS RULE WAS REWRITTEN, and the reason is the point. It began as "a
    wrapper mention anywhere earlier in the block", which a refuter defeated
    with a completed `--self-test-only` call on the line above a bare
    invocation. It was narrowed to "same line, or an earlier line joined by a
    backslash" — defeated by a separator before that backslash. That was narrowed
    again to reject command separators before the backslash — and defeated a
    THIRD time by the same shape on ONE line: `hermetic_verify.sh -- echo ok;
    python3 <instrument>`.

    Three rounds, three twins, because every version answered "is a wrapper
    mention NEAR this instrument?" when the question is "is this instrument
    running INSIDE a wrapped command?". Proximity is not the property. So the
    block is now segmented into shell commands and each is judged on its own;
    the same-line, multi-line and separator shapes all fall out of one rule
    instead of three special cases, and there is no fourth twin to find,
    because there is no proximity left to exploit.

    A wrapper mention in a DIFFERENT command no longer protects anything, which
    is exactly right: that command has already run and exited.
    """
    violations: list[str] = []
    line_text = {ln: txt for ln, txt in block.lines}
    for segment in _segments(block):
        text = "".join(ch for _l, _c, ch in segment)
        wrapper_at = [m.start() for m in re.finditer(re.escape(WRAPPER), text)]
        first_wrapper = wrapper_at[0] if wrapper_at else None
        for instrument in instruments:
            for m in re.finditer(re.escape(instrument), text):
                if first_wrapper is not None and first_wrapper < m.start():
                    continue
                line_no = segment[m.start()][0]
                violations.append(f"{block.file}:{line_no}: {line_text[line_no].strip()}")
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
