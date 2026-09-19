#!/usr/bin/env python3
"""lint_workflow_script.py — PR3a (2026-09-18), mandate MANDATE-builder.md PR3 section
(split by the 2026-09-18 addendum; this lint's CI consumer is PR3c, a separate hot-zone
PR that only has to NAME scripts/tests/test_lint_workflow_script.py).

For every workflow-harness script under infra/workflows/*.js:

  RULE 1 (model pin) — every `agent(` call's options object carries a literal `model:`
    property. infra/claude-hooks/model_routing_gate.py enforces the analogous rule for
    THIS session's own Agent tool dispatches; it never sees infra/workflows/*.js, whose
    `agent()` is a different, workflow-harness-local function. A RUNTIME backstop exists
    for exactly ONE file in this family, not all of it (corrected 2026-09-18, DEFECT
    :11, PR3d — the prior wording claimed it covered "that same file family"):
    infra/workflows/run-second-army.mjs:121's `assertModelPinned` throws when a lane's
    `opts.model` is missing, but that runner only ever loads second-army.js
    (run-second-army.mjs:26's own DEFAULT_SCRIPT_PATH) — the other five live files
    (kbli-batch-a-lot.js, kbli-pilot-a1.js, modus-bench.js, saetta.js, verify-template.js)
    are native Workflow DSL with no such runner, so a missing `model:` there silently
    inherits the session model instead (.claude/skills/workflow/SKILL.md:38). This
    static lint is the only guard those five have. The wrapper-indirection exemption
    below stays for the same reason either way: all three live callSeat(...) sites pin
    `model: "sonnet"` themselves (see CONDITION 3, documented_bypass.js).

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

Regex literals are neutralized too (item 1, PR3e, 2026-09-18, gate-10 obs 1, HIGH): a
`/` opens a regex literal only immediately after one of `(`, `,`, `=`, `:`, `[`, `!`,
`&`, `|`, `?`, `{`, `}`, `;`, the keyword `return`/`typeof`, or start-of-line (skipping
whitespace) — see `_regex_may_open`. This is tokenizer-level, not the "second JS
parser" this docstring otherwise forbids: it is one more prefix-token rule alongside
the quote/backtick/comment openers already handled above, not a grammar-aware parse.
Before this rule existed, no branch handled `/` as a regex opener at all:
`.replace(/'/g, "")` was misread as opening a STRING (blanking the rest of the FILE);
`/https:\\/\\//` was misread as opening a LINE COMMENT (blanking the rest of the LINE) —
either way, every `agent(`/loop after the mistake went invisible and the file falsely
reported CLEAN. Where the rule cannot decide (a `/` after `)`, `]`, an identifier or a
digit — all four stay division, not a regex open), it is left as code. Safety net: if
the paren/brace balance of the neutralized file is non-zero, `_assert_balanced` REFUSES
the file with exit 2 naming file+line rather than trust a desynced count (cicatrix #2:
never report CLEAN on text you could not read).

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

Known accusing-side limits (documented, not behavior changes):

  * RULE 1 does not recognise a QUOTED `model` key (`"model": "sonnet"`) as a pin (item
    2, PR3e, 2026-09-18, gate-10 obs 2): `_neutralize_js` blanks a quoted string's OWN
    delimiting quote characters along with its contents, so a quoted key is lexically
    invisible by the time RULE 1 inspects the object's entries — reported unpinned BY
    DESIGN (false accusation, fail-safe). Every live `agent(` call already uses a
    bareword `model:` key (see clean.js); use one.
  * RULE 1 accuses shorthand (`{ model }`), computed (`{ ["model"]: m }`), and spread
    (`{ ...opts }`) keys the same as a genuinely-missing `model:` (item 4, PR3e,
    2026-09-18, gate-10 obs 4/5/6) — none of the three is a `model\\s*:` match, so the
    lint cannot prove a pin through any of them lexically. To avoid the false
    accusation, route through the same opaque-identifier indirection
    `documented_bypass.js` already uses (the module docstring's first exemption) —
    that is the honest, documented way to keep one of these shapes off this lint's
    radar, not a fix to the accusation itself.
  * RULE 3 accuses `for (;;)` with a break-on-cap, `while (i++ < CAP)`, and
    `do { ... } while (n < CAP)` the same as a genuinely-uncapped loop, whenever `CAP`
    is not itself a literal integer or a CAP_NAME_RE name — same false-accusation
    shape as RULE 1's three key forms above. The workaround today is the one RULE 3
    already rewards: name the cap constant per CAP_NAME_RE (or use a literal int)
    anywhere in the phase(...) span. The span-wide search itself is not narrowed to
    the flagged loop's own header/body in this PR; that narrowing is deferred — see
    this PR's own body.

Known, accepted limit (same spirit as infra/guard-conformance's own C4 note — a
documented bound, not a second JS parser): `_neutralize_js` does not recurse into a
quoted string OR a regex literal that itself sits inside a `${...}` template
interpolation — a stray `{` or `}` character inside such a nested construct could
misalign interpolation-depth tracking. None of the infra/workflows/*.js files in this
repo do that today (verified 2026-09-19, each interpolation is a bare property access, a
ternary, or a JSON.stringify(...) call with no nested template/string/regex containing a
brace — second-army.js:612's `"(n/a)"` is a nested STRING inside a `${...}`, not a
regex, and has no brace either way). A future file that needs one would need a real JS
parser, not a regex-based lint — do not "fix" this file by writing one.

    python3 scripts/lint_workflow_script.py [path ...]

Default sweep (no argv): infra/workflows/*.js. Exit 0 clean, 1 violations found,
2 blind scan (default sweep traversed zero files — cicatrix #2/#4, "exists != armed")
OR a file's paren/brace count is unbalanced after neutralization (item 1, PR3e,
2026-09-18 — refuses rather than risk a false CLEAN; see _assert_balanced). The same
zero-scan rule binds an EXPLICIT target too (PR3c, 2026-09-19): a nonexistent path or
an existing directory that yields zero .js files both blind-scan at exit 2; only an
explicit FILE of the wrong suffix stays legitimately off-scope and exits 0.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

AGENT_CALL_RE = re.compile(r"\bagent\s*\(")
PHASE_CALL_RE = re.compile(r"""\bphase\(\s*(['"`])([^'"`]+)\1\s*\)""")
MODEL_KEY_RE = re.compile(r"\bmodel\s*:")
LABEL_VALUE_RE = re.compile(r"""\blabel\s*:\s*(`[^`]*`|'[^']*'|"[^"]*")""")
# OBSERVATION 5 (PR3a', 2026-09-18): `for await (` is valid JS (async iteration) and
# must be recognised as a loop like plain `for (` — the optional `await` sits between
# the keyword and the paren. group(1) still captures only "for"/"while".
LOOP_RE = re.compile(r"\b(while|for)\b(?:\s+await)?\s*\(")
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

# Prefix-token rule (item 1, PR3e, 2026-09-18, gate-10 obs 1, HIGH): a `/` opens a
# regex literal only immediately after one of these characters, the keyword
# return/typeof, or start-of-line -- never after `)`, `]`, an identifier or a digit
# (all four stay division; JS grammar itself cannot always disambiguate this without a
# full parser, and neither can we, so those four are left undecided -> code).
_REGEX_OPENER_CHARS = frozenset("(,=:[!&|?{};")
_REGEX_OPENER_KEYWORDS = frozenset({"return", "typeof"})


def _regex_may_open(out: list[str], i: int) -> bool:
    """True when position `i` in `out` (the in-progress neutralization buffer) sits
    where JS grammar allows a regex literal to open. Scans BACKWARD over `out`, not
    `src`: every position before `i` has already been visited by _neutralize_js's own
    loop this call, so string/comment/regex content there is already blanked to
    spaces -- this reads exactly the "previous token" a real tokenizer would see."""
    j = i - 1
    while j >= 0 and out[j] in (" ", "\t"):
        j -= 1
    if j < 0 or out[j] == "\n":
        return True
    c = out[j]
    if c in _REGEX_OPENER_CHARS:
        return True
    if c.isalnum() or c in "_$":
        k = j
        while k >= 0 and (out[k].isalnum() or out[k] in "_$"):
            k -= 1
        word = "".join(out[k + 1 : j + 1])
        return word in _REGEX_OPENER_KEYWORDS
    return False


def _neutralize_js(src: str) -> str:
    """Same-length copy of `src` with comment/string/template-literal/regex-literal
    CONTENTS blanked to spaces, so a naive paren-depth counter over the result cannot
    be desynced by a stray bracket character inside prose or code-as-text (a prompt
    string ending "...even the refuter hallucinates)" is exactly the failure mode this
    exists to prevent). A `/` opens a regex literal only where JS grammar allows one --
    see _regex_may_open -- so a division like `a / b` is never misread as a comment or
    string opener (item 1, PR3e, 2026-09-18, gate-10 obs 1). `${...}` template
    interpolations are real code and are left live so their own parens/braces still
    count -- see the module docstring's documented limit."""
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
        if c == "/" and _regex_may_open(out, i):
            j = i + 1
            in_class = False
            closed = False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "\n":
                    break
                if ch == "[":
                    in_class = True
                    j += 1
                    continue
                if ch == "]":
                    in_class = False
                    j += 1
                    continue
                if ch == "/" and not in_class:
                    j += 1
                    closed = True
                    break
                j += 1
            if closed:
                while j < n and src[j].isalpha():
                    j += 1
                for k in range(i, j):
                    if src[k] != "\n":
                        out[k] = " "
                i = j
                continue
            # not closed before EOL/EOF -- not actually a regex; leave as code (division)
        i += 1
    return "".join(out)


def _unwrap_parens(text: str) -> str:
    """Strips matched wrapping parens (`((x))` -> `x`), but leaves an expression like
    `(a)+(b)` alone: a wrapping pair only counts when its OWN matching close is the
    LAST character of `text` -- depth returns to zero exactly once, at the very end.
    DEFECT :184 (PR3d, 2026-09-18): a parenthesized object literal such as
    `agent(p, ({ label: "x" }))` was skipped entirely as unreadable indirection; it is
    exactly as readable as the unwrapped form once this strips the wrapping paren."""
    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        close_idx = -1
        for idx, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    close_idx = idx
                    break
        if close_idx != len(text) - 1:
            break  # the first "(" closes before the end -- not a wrapping pair
        text = text[1:-1].strip()
    return text


def _last_top_level_arg(call_neutral: str) -> str:
    """call_neutral is the full, neutralized `agent(...)` call text (outer parens
    included). Returns the LAST top-level argument's own neutralized text, with any
    wrapping indirection parens stripped (see _unwrap_parens)."""
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
    # OBSERVATION 4 (PR3a', 2026-09-18): zero top-level commas means a SINGLE argument,
    # not "nothing to check" — if that lone argument is itself an object literal, it IS
    # the last (and only) argument, same as a multi-arg call's tail. Previously this
    # returned False unconditionally here, silently skipping `agent({...})` calls.
    last_arg = inner[top_commas[-1] + 1 :].strip() if top_commas else inner.strip()
    return _unwrap_parens(last_arg)


def _options_arg_is_object_literal(call_neutral: str) -> bool:
    """True only when the LAST top-level argument (see _last_top_level_arg) looks like
    an object literal (`{...}`) — see the module docstring's first exemption. False for
    a bare identifier/expression there (nothing to lexically check; not accused)."""
    return _last_top_level_arg(call_neutral).startswith("{")


def _top_level_entries(obj_inner: str) -> list[str]:
    """obj_inner is a neutralized object literal's content WITHOUT its outer braces.
    Splits on top-level commas only (same depth-tracking idiom as
    _last_top_level_arg) so a `model:` key inside a NESTED value (e.g.
    `schema: { properties: { model: {...} } }`) is never mistaken for one of THIS
    object's own top-level entries — DEFECT :229, PR3d, 2026-09-18."""
    depth = 0
    start = 0
    entries: list[str] = []
    for idx, ch in enumerate(obj_inner):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            entries.append(obj_inner[start:idx])
            start = idx + 1
    entries.append(obj_inner[start:])
    return entries


def _entry_key_is_model(entry: str) -> bool:
    """entry is one top-level `key: value` slice from _top_level_entries. True only
    when a `model\\s*:` match is the entry's OWN key — nothing but whitespace precedes
    it in this entry's own text — never a `model:` occurring deeper inside that same
    entry's value (the exact shape DEFECT :229 missed). DOCUMENTED LIMIT (item 2,
    PR3e, 2026-09-18, gate-10 obs 2): a QUOTED key (`"model": ...`) is NOT recognised
    here -- _neutralize_js already blanked the quote characters along with the
    string's contents, so plain whitespace is all that is left to strip; stripping
    quote characters too would (wrongly) also accept a quoted key. Reported unpinned
    BY DESIGN -- see the module docstring's "Known accusing-side limits"."""
    m = MODEL_KEY_RE.search(entry)
    if not m:
        return False
    return not entry[: m.start()].strip()


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


class _UnbalancedAfterNeutralization(Exception):
    """Raised by _assert_balanced when neutralized text has a non-zero paren/brace
    count -- proof _neutralize_js could not fully read the file (e.g. a phantom regex
    span swallowed one side of a real pair). find_violations refuses to report CLEAN
    on this rather than trust a desynced count (cicatrix #2: never report CLEAN on
    text you could not read); main() catches this and exits 2 -- see item 1, PR3e,
    2026-09-18."""

    def __init__(self, line_no: int):
        self.line_no = line_no
        super().__init__(
            f"unbalanced paren/brace count after neutralization at line {line_no}"
        )


def _assert_balanced(src: str, neutral: str) -> None:
    """Two INDEPENDENT scalar counters (paren, brace) over the neutralized text --
    same paren-only idiom as _find_matching_paren, not a combined type-matching stack.
    Raises at the first negative-going index (an extra close), or -- if the file ends
    with either counter still non-zero (a dangling open) -- at the last line."""
    paren = 0
    brace = 0
    last_line = 1
    for idx, ch in enumerate(neutral):
        if ch == "\n":
            last_line += 1
        elif ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
            if paren < 0:
                raise _UnbalancedAfterNeutralization(src[:idx].count("\n") + 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1
            if brace < 0:
                raise _UnbalancedAfterNeutralization(src[:idx].count("\n") + 1)
    if paren != 0 or brace != 0:
        raise _UnbalancedAfterNeutralization(last_line)


def find_violations(path: Path) -> list[tuple[int, str]]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    neutral = _neutralize_js(src)
    _assert_balanced(src, neutral)
    violations: list[tuple[int, str]] = []

    for m in AGENT_CALL_RE.finditer(neutral):
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(neutral, open_idx)
        call_neutral = neutral[open_idx : close_idx + 1]
        call_original = src[open_idx : close_idx + 1]
        line_no = src[: m.start()].count("\n") + 1
        if not _options_arg_is_object_literal(call_neutral):
            continue  # indirection (e.g. a provenance wrapper) — not lexically checkable
        obj_literal = _last_top_level_arg(call_neutral)
        # DEFECT :229 (PR3d, 2026-09-18): MODEL_KEY_RE.search(call_neutral) used to match
        # `model:` at ANY nesting depth, so a `model:` buried inside a nested `schema:
        # { properties: { model: {...} } }` value passed this check unpinned. Require
        # `model:` as a genuine TOP-LEVEL key of the options object literal itself.
        if not any(
            _entry_key_is_model(entry) for entry in _top_level_entries(obj_literal[1:-1])
        ):
            violations.append((line_no, "agent( call has no literal `model:`"))
        label_m = LABEL_VALUE_RE.search(call_original)
        if label_m and "gate" in label_m.group(1).lower():
            violations.append(
                (line_no, f"agent( call's label {label_m.group(1)} contains \"gate\"")
            )

    phase_calls = [(m.start(), m.group(2)) for m in PHASE_CALL_RE.finditer(src)]
    # DEFECT :245 (PR3d, 2026-09-18): spans used to start at the FIRST phase( call, so
    # any loop above it — and every loop in a file with no phase( at all — sat outside
    # every span and was never scanned. An implicit leading span (name=None) covers
    # exactly that gap; it stands in for the WHOLE file when phase_calls is empty.
    spans = [(0, None)] + phase_calls
    for idx, (start, name) in enumerate(spans):
        end = spans[idx + 1][0] if idx + 1 < len(spans) else len(src)
        span_neutral = neutral[start:end]
        for loop_m in LOOP_RE.finditer(span_neutral):
            loop_open = start + loop_m.end() - 1
            loop_close = _find_matching_paren(neutral, loop_open)
            header_neutral = neutral[loop_open : loop_close + 1]
            if _is_bounded_for_of_in(loop_m.group(1), header_neutral[1:-1]):
                continue  # bounded by its own finite collection — not a round-cap risk
            has_int = bool(INT_LITERAL_RE.search(header_neutral))
            # DEFECT :253 (PR3d, 2026-09-18): this used to search src[start:end] — the
            # UN-neutralized source — so a cap name mentioned only in a comment or a
            # prompt string above an actually-uncapped loop silenced the rule
            # (cicatrix #3: substring/text match, not a real code entity). Search the
            # already-neutralized span instead: a comment or string mention is blanked
            # there, so only a REAL cap-name token in code can satisfy the rule.
            has_cap_name = bool(CAP_NAME_RE.search(span_neutral))
            if not has_int and not has_cap_name:
                line_no = src[:loop_open].count("\n") + 1
                # ITEM 3 (PR3e, 2026-09-18, gate-10 obs 7): a file that HAS phase(
                # calls, just not before THIS loop, is not the same as a file with no
                # phase( call anywhere -- the wording must say which.
                if name is not None:
                    where = f'phase("{name}")'
                elif phase_calls:
                    where = "before first phase("
                else:
                    where = "no phase("
                violations.append(
                    (
                        line_no,
                        f"{where} has a {loop_m.group(1)}( loop with no numeric "
                        "cap or maxRounds-style constant in its span",
                    )
                )
    return violations


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    explicit = bool(argv)
    dir_contributions: dict[Path, int] = {}
    if explicit:
        raw_targets = [repo_root / p for p in argv]
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
        targets = sorted((repo_root / DEFAULT_GLOB_DIR).glob(DEFAULT_GLOB_PATTERN))

    bad: list[tuple[Path, int, str]] = []
    scanned = 0
    for path in targets:
        if not path.is_file() or path.suffix != ".js":
            continue
        scanned += 1
        try:
            file_violations = find_violations(path)
        except _UnbalancedAfterNeutralization as exc:
            print(
                f"❌ lint_workflow_script: {path}:{exc.line_no}: refusing to report "
                "CLEAN -- neutralization left an unbalanced paren/brace count "
                "(cicatrix #2: never report CLEAN on text you could not read).",
                file=sys.stderr,
            )
            return 2
        for line_no, msg in file_violations:
            bad.append((path, line_no, msg))

    if not explicit and scanned == 0:
        print(
            "❌ lint_workflow_script: BLIND SCAN — infra/workflows/*.js traversed ZERO "
            "files.\nRefusing to report 'clean': a scan that sees nothing proves nothing "
            "(cicatrix #2, \"exists != armed\").",
            file=sys.stderr,
        )
        return 2

    # OBSERVATION 6 (PR3a', 2026-09-18) + PR3c blind-scan closure widened after
    # independent adversarial review (2026-09-19, Sol and Kimi both reproduced): each
    # explicit raw target is judged ON ITS OWN — missing from disk, or an existing
    # directory that glob-expanded to zero in-scope files — INDEPENDENT of whether
    # other targets in the same invocation scanned something. A global `scanned == 0`
    # gate let one productive target mask a sibling blind one (`lint empty_dir
    # real.js` went green, silently ignoring empty_dir) — cicatrix #2 one level
    # deeper than the single-target case. An explicit EXISTING FILE of the wrong
    # suffix stays legitimately off-scope (never glob-expanded, never expected to
    # be) — test_innocence_explicit_non_js_file_is_still_green's case, unchanged.
    if explicit:
        missing = [p for p in raw_targets if not p.exists()]
        empty_dirs = [p for p, n in dir_contributions.items() if n == 0]
        guilty = missing + empty_dirs
        if guilty:
            names = ", ".join(str(p) for p in guilty)
            print(
                f"❌ lint_workflow_script: BLIND SCAN — target(s) yielded zero .js files: {names}.\n"
                "Refusing to report 'clean': a scan that sees nothing proves nothing "
                "(cicatrix #2, \"exists != armed\").",
                file=sys.stderr,
            )
            return 2

    if not bad:
        print(f"✅ lint_workflow_script: no violations ({scanned} file(s) scanned)")
        return 0

    print(f"❌ lint_workflow_script: {len(bad)} violation(s) in {scanned} file(s) scanned.\n")
    for path, line_no, msg in bad:
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            # an explicit target outside repo_root (e.g. a gate's /tmp reproduction) has
            # no relative form — fall back to the absolute path rather than traceback.
            rel = path
        print(f"  {rel}:{line_no}: {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
