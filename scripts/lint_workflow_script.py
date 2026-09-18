#!/usr/bin/env python3
"""lint_workflow_script.py — PR3a (2026-09-18), mandate MANDATE-builder.md PR3 section
(split by the 2026-09-18 addendum; this lint's CI consumer is PR3c, a separate hot-zone
PR that only has to NAME scripts/tests/test_lint_workflow_script.py).

For every workflow-harness script under infra/workflows/*.js:

  RULE 1 (model pin) — every `agent(` call's options object carries a literal `model:`
    property. infra/claude-hooks/model_routing_gate.py enforces the analogous rule for
    THIS session's own Agent tool dispatches; it never sees infra/workflows/*.js, whose
    `agent()` is a different, workflow-harness-local function. Same failure mode either
    way: an unpinned call silently inherits whatever model the harness defaults to.

  RULE 2 (no self-styled gate) — no `agent(` call's `label:` may contain "gate"
    (case-insensitive). A workflow script that labels one of its own steps a gate is
    self-certifying a verdict; this repo's real gate infrastructure (council_run,
    scripts/check_adversarial_review.py, the on-disk Opus gate) is supposed to own that
    word alone (repo CLAUDE.md, Builder Contract: "generator is never grader").

  RULE 3 (bounded rounds) — every `phase(` whose own span (from that call up to the next
    `phase(` call, or EOF) contains a `while (` / `for (` loop must carry, somewhere in
    that same span, either a literal integer inside the LOOP'S OWN header or a
    rounds/iteration-cap constant (see CAP_NAME_RE — deliberately an explicit list built
    around the mandate's own named example, `maxRounds`, not a loose "contains max"
    substring match: a per-round CONCURRENCY knob like `maxParallel` caps how much of one
    round runs at once, not how many rounds a while-loop may run, and conflating the two
    would hide exactly the silent-spin defect this rule exists to catch).

Two deliberate exemptions, both found necessary against the live repo (2026-09-18), not
speculative:

  * RULE 1/2 fire only when `agent(`'s own last top-level argument is an object literal
    (`{...}`) we can actually read `model:`/`label:` out of. A bare identifier there
    (e.g. kbli-batch-a-lot.js's `callSeat(promptText, opts)` wrapper, whose OWN inner
    `await agent(promptText, opts)` has no literal in sight) is deliberate indirection —
    the real literal lives one call-frame up, at every `callSeat(..., {model: "...", ...})`
    site — and is not itself a dispatch decision. Lexically we cannot verify it either
    way, so we do not accuse it (guard-conformance's own #3 discipline: never judge a
    surface you cannot actually prove guilty).
  * RULE 3 exempts `for (const X of/in Y)` — bounded by its own finite collection,
    categorically not the unbounded-condition risk the rule exists to catch (e.g.
    second-army.js's `for (const seat of builderRoster)`). Only a classic
    `for (init; cond; step)` or a condition-based `while (cond)` needs a nearby cap.

Known, accepted limit (same spirit as infra/guard-conformance's own C4 note — a
documented bound, not a second JS parser): `_neutralize_js` does not recurse into a
quoted string that itself sits inside a `${...}` template interpolation — a stray `{` or
`}` character inside such a nested string could misalign interpolation-depth tracking.
None of the infra/workflows/*.js files in this repo do that today (verified 2026-09-18,
each interpolation is a bare property access, a ternary, or a JSON.stringify(...) call
with no nested template/string containing a brace). A future file that needs one would
need a real JS parser, not a regex-based lint — do not "fix" this file by writing one.

    python3 scripts/lint_workflow_script.py [path ...]

Default sweep (no argv): infra/workflows/*.js. Exit 0 clean, 1 violations found,
2 blind scan (default sweep traversed zero files — cicatrix #2/#4, "exists != armed").
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

AGENT_CALL_RE = re.compile(r"\bagent\s*\(")
PHASE_CALL_RE = re.compile(r"""\bphase\(\s*(['"`])([^'"`]+)\1\s*\)""")
MODEL_KEY_RE = re.compile(r"\bmodel\s*:")
LABEL_VALUE_RE = re.compile(r"""\blabel\s*:\s*(`[^`]*`|'[^']*'|"[^"]*")""")
LOOP_RE = re.compile(r"\b(while|for)\s*\(")
INT_LITERAL_RE = re.compile(r"\d+")
# Explicit, documented vocabulary (see RULE 3 docstring above) rather than a loose
# "contains max/cap" substring match, which "capture"/"capacity"/"escape" would trip.
CAP_NAME_RE = re.compile(
    r"\b(?:MAX_ROUNDS|ROUND_CAP|ROUNDS_CAP|ROUND_LIMIT|MAX_ITERATIONS|ITERATION_CAP|"
    r"maxRounds|roundCap|roundsCap|roundLimit|maxIterations|iterationCap)\b"
)
FOR_OF_IN_RE = re.compile(r"^(?:const|let|var)\s+[^;]+?\s(?:of|in)\s")

DEFAULT_GLOB_DIR = "infra/workflows"
DEFAULT_GLOB_PATTERN = "*.js"


def _neutralize_js(src: str) -> str:
    """Same-length copy of `src` with comment/string/template-literal CONTENTS blanked
    to spaces, so a naive paren-depth counter over the result cannot be desynced by a
    stray bracket character inside prose or code-as-text (a prompt string ending
    "...even the refuter hallucinates)" is exactly the failure mode this exists to
    prevent). `${...}` template interpolations are real code and are left live so their
    own parens/braces still count -- see the module docstring's documented limit."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if src[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c in ("'", '"'):
            q = c
            j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            for k in range(i, j):
                if src[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c == "`":
            j = i + 1
            depth = 0  # ${...} interpolation nesting inside this template
            while j < n:
                if depth == 0 and src[j] == "\\":
                    j += 2
                    continue
                if depth == 0 and src[j] == "`":
                    j += 1
                    break
                if depth == 0 and src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    depth = 1
                    j += 2
                    continue
                if depth > 0:
                    if src[j] == "{":
                        depth += 1
                    elif src[j] == "}":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            continue
                    j += 1
                    continue
                if src[j] != "\n":
                    out[j] = " "
                j += 1
            i = j
            continue
        i += 1
    return "".join(out)


def _options_arg_is_object_literal(call_neutral: str) -> bool:
    """call_neutral is the full, neutralized `agent(...)` call text (outer parens
    included). True only when the LAST top-level argument looks like an object
    literal (`{...}`) — see the module docstring's first exemption. False for a
    bare identifier/expression there (nothing to lexically check; not accused)."""
    inner = call_neutral[1:-1].rstrip()
    if inner.endswith(","):
        # a JS trailing comma before the closing `)` (Prettier's own style) — not a
        # real argument separator; without this, the "last argument" split below
        # would see an empty tail after it and misreport a real object literal
        # (e.g. saetta.js's `{ label: ..., schema: GATE, }`) as a bare expression.
        inner = inner[:-1].rstrip()
    depth = 0
    top_commas: list[int] = []
    for idx, ch in enumerate(inner):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            top_commas.append(idx)
    if not top_commas:
        return False
    last_arg = inner[top_commas[-1] + 1 :].strip()
    return last_arg.startswith("{")


def _is_bounded_for_of_in(loop_keyword: str, header_inner: str) -> bool:
    """header_inner excludes the loop's own outer parens. See the module docstring's
    second exemption. Only `for` is eligible: a `for (const x of/in Y)` header has no
    `;` (unlike a classic `for (init; cond; step)`); a `while` is condition-based
    regardless of any "in"/"of" substring inside its own expression."""
    if loop_keyword != "for" or ";" in header_inner:
        return False
    return bool(FOR_OF_IN_RE.match(header_inner.strip()))


def _find_matching_paren(text: str, open_idx: int) -> int:
    """text[open_idx] == '(' ; index of its matching ')' via depth-count over
    ALREADY-NEUTRALIZED text (brackets inside strings/templates/comments cannot
    desync the count). Falls back to end-of-text if unterminated (malformed input)."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def find_violations(path: Path) -> list[tuple[int, str]]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    neutral = _neutralize_js(src)
    violations: list[tuple[int, str]] = []

    for m in AGENT_CALL_RE.finditer(neutral):
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(neutral, open_idx)
        call_neutral = neutral[open_idx : close_idx + 1]
        call_original = src[open_idx : close_idx + 1]
        line_no = src[: m.start()].count("\n") + 1
        if not _options_arg_is_object_literal(call_neutral):
            continue  # indirection (e.g. a provenance wrapper) — not lexically checkable
        if not MODEL_KEY_RE.search(call_neutral):
            violations.append((line_no, "agent( call has no literal `model:`"))
        label_m = LABEL_VALUE_RE.search(call_original)
        if label_m and "gate" in label_m.group(1).lower():
            violations.append(
                (line_no, f"agent( call's label {label_m.group(1)} contains \"gate\"")
            )

    phase_calls = [(m.start(), m.group(2)) for m in PHASE_CALL_RE.finditer(src)]
    for idx, (start, name) in enumerate(phase_calls):
        end = phase_calls[idx + 1][0] if idx + 1 < len(phase_calls) else len(src)
        span_neutral = neutral[start:end]
        for loop_m in LOOP_RE.finditer(span_neutral):
            loop_open = start + loop_m.end() - 1
            loop_close = _find_matching_paren(neutral, loop_open)
            header_neutral = neutral[loop_open : loop_close + 1]
            if _is_bounded_for_of_in(loop_m.group(1), header_neutral[1:-1]):
                continue  # bounded by its own finite collection — not a round-cap risk
            has_int = bool(INT_LITERAL_RE.search(header_neutral))
            has_cap_name = bool(CAP_NAME_RE.search(src[start:end]))
            if not has_int and not has_cap_name:
                line_no = src[:loop_open].count("\n") + 1
                violations.append(
                    (
                        line_no,
                        f'phase("{name}") has a {loop_m.group(1)}( loop with no numeric '
                        "cap or maxRounds-style constant in its span",
                    )
                )
    return violations


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    explicit = bool(argv)
    if explicit:
        targets = [repo_root / p for p in argv]
    else:
        targets = sorted((repo_root / DEFAULT_GLOB_DIR).glob(DEFAULT_GLOB_PATTERN))

    bad: list[tuple[Path, int, str]] = []
    scanned = 0
    for path in targets:
        if not path.is_file() or path.suffix != ".js":
            continue
        scanned += 1
        for line_no, msg in find_violations(path):
            bad.append((path, line_no, msg))

    if not explicit and scanned == 0:
        print(
            "❌ lint_workflow_script: BLIND SCAN — infra/workflows/*.js traversed ZERO "
            "files.\nRefusing to report 'clean': a scan that sees nothing proves nothing "
            "(cicatrix #2, \"exists != armed\").",
            file=sys.stderr,
        )
        return 2

    if not bad:
        print(f"✅ lint_workflow_script: no violations ({scanned} file(s) scanned)")
        return 0

    print(f"❌ lint_workflow_script: {len(bad)} violation(s) in {scanned} file(s) scanned.\n")
    for path, line_no, msg in bad:
        rel = path.relative_to(repo_root)
        print(f"  {rel}:{line_no}: {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
