#!/usr/bin/env python3
"""lint_unreachable_workflow_conditions.py — catches the security.yml class
of bug: an `on:` trigger narrowing that leaves a job/step `if:` condition a
standing contradiction, so it can never fire again.

WHY THIS EXISTS (cicatrix-superscar.md #9, "State-schema mutation drift" —
an `if:` is a measurement of the world, frozen the day it was written; a
later `on:` narrowing does not re-take that measurement, W106/W106b).
Commit `4e2d8367e` (#4218, 2026-08-16) narrowed `security.yml`'s
`on.push.branches` from `[main, develop]` to `[develop]` and left a Telegram
alert step's `if: event_name=='push' && ref=='refs/heads/main'` untouched.
GitHub's own branch filter means `event_name=='push'` now IMPLIES
`ref=='refs/heads/develop'` — the conjunct against `refs/heads/main` became
a standing contradiction, and the step could never fire. The daily
`schedule` backstop the commit message named as the intended replacement
never satisfies `event_name=='push'` either. The alarm was armed and mute
for four days, until an unbuildable production image (2026-08-20, upstream
`claude-code@2.1.237` published without its `linux-x64` tarball) alarmed
nobody. See `.github/workflows/security.yml`'s own comment above that step
for the full story, and this cure's sibling PR for the fix.

WHAT THIS DOES: for every tracked `.github/workflows/*.yml` (`git ls-files`,
never a glob — rule 5, judge only what git tracks), parses the `on:` block
into the set of (event, ref-constraint) TRIGGER PATHS the workflow can
actually run under (`extract_trigger_paths()`), then for every job-level and
step-level `if:` that mentions `github.event_name` or `github.ref` (the only
two fields this module reasons about — an `if:` that never names either is
entirely out of scope and is not even counted as undecided, e.g.
`needs.build.result == 'success'`), decides whether the condition can
possibly evaluate true under AT LEAST ONE of those trigger paths. An `if:`
that is false under every trigger path the workflow's OWN `on:` block can
produce is reported as a finding: file, line (best-effort), the verbatim
`if:` text, the relevant `on:` fragment, and a per-trigger-path mechanism
trace auto-derived from the same evaluator that made the call (never
hand-authored prose that could drift from the code that decided).

DECLARED LIMITS (rule 2 — printed as a clearly separated "not analyzed"
list, never silently folded into a "0 findings" clean report — W84/W102: an
empty finding list from a blind or capped scan must never read as clean):

  1. DECIDABLE EXPRESSION SHAPE — only conjunctions/disjunctions of
     `github.event_name == '<literal>'` and `github.ref == '<literal>'`
     (either operand order), combined with `&&` / `||` / parentheses, with
     `failure()` / `success()` / `always()` / `cancelled()` treated as free
     (always true — this module never reasons about job/step outcome, only
     about which trigger reached it). `!=`, `!` (NOT), any function call
     with arguments (`contains(...)`, `startsWith(...)`, ...), any other
     `github.*`/`steps.*`/`needs.*`/`inputs.*` field, and any literal that
     isn't a quoted string are all OUTSIDE this shape. Encountering any of
     them anywhere in an `if:` marks the WHOLE condition UNDECIDED — this
     module never partially evaluates one side of a boundary-crossing `&&`.
  2. REF SEMANTICS PER EVENT — only `push: branches: [...]` (exact names or
     glob patterns, matched via `fnmatch` against the branch component of a
     `refs/heads/...` literal) is modeled precisely. `branches-ignore:`,
     `tags:`, `tags-ignore:`, or a `push:` with none of these keys, and
     EVERY OTHER event (`pull_request`, `pull_request_target`,
     `merge_group`, `schedule`, `workflow_dispatch`, `workflow_call`, or any
     event key this module does not special-case) all get an unconstrained
     ref — `github.ref == '<anything>'` is treated as POSSIBLY true. This is
     deliberate: rule 4 of the build spec requires bias toward silence — an
     unconstrained/unknown ref can only produce a MISSED unreachable
     condition (e.g. a `schedule`-only `if:` that names a `ref` value the
     default branch never actually is), never a FALSE accusation. In
     particular `schedule` genuinely always runs against the repo's default
     branch (GitHub docs), but that branch's NAME is a repo-config fact this
     module cannot read from a workflow file — asserting it here would be a
     guess dressed as a fact (cicatrix-superscar W106b: don't hardcode a
     measurement of the world), so `schedule`'s ref is left unconstrained
     rather than guessed. Same reasoning for `merge_group` (real ref is
     `refs/heads/gh-readonly-queue/...`, never asserted equal to anything).
     Within the modeled `branches:` glob subset, only `fnmatch`'s own
     metacharacters (`*`, `?`, `[seq]`, `[!seq]`) are given GitHub's
     meaning; a pattern using `+` ("one or more of the preceding char" in
     GitHub's own filter-pattern glob) or `\\` (GitHub's escape character) is
     OUTSIDE that subset — `fnmatch` treats both as ordinary literal
     characters (verified empirically: `fnmatch.fnmatch('maaan', 'ma+n')`
     is `False`, but GitHub's glob would match it) — so any `branches:`
     entry containing either character collapses that push trigger's ref to
     UNCONSTRAINED rather than mismodeling it (same bias-to-silence
     reasoning as above: more matches -> more satisfiable -> only ever a
     missed detection, never a false accusation). The opposite kind of gap
     — `fnmatch`'s `*`/`?` matching across a `/` where GitHub's glob would
     not — is left unaddressed on purpose: it makes `fnmatch` MORE
     permissive than GitHub in that one case, which can only widen
     "satisfiable", i.e. it is a missed-detection risk, never a
     false-accusation one.
  3. `on.push.paths` / `on.pull_request.paths` and any `types:` filter are
     never modeled — they gate whether a run STARTS at all, not what
     `github.event_name`/`github.ref` it carries once it does; irrelevant to
     this module's question.
  4. STRING COMPARISON CASE-FOLDING — GitHub's own `==`/`!=` operators
     ignore case for the whole compared string ("GitHub ignores case when
     comparing strings" — docs.github.com/en/actions/reference/
     workflows-and-actions/expressions, verified 2026-08-20), so
     `github.event_name == 'Push'` is true on an actual `push` event and
     `github.ref == 'REFS/HEADS/MAIN'` is true against the real
     `refs/heads/main`. This module casefolds both sides of every
     `event_name`/`ref` comparison to match. Inside `_push_ref_matcher`,
     the ref literal's `refs/heads/` prefix check is casefolded for that
     same documented reason; whether the extracted branch text then matches
     one of `branches:`'s glob patterns is ALSO matched casefolded, but
     that second fold is a separate, deliberate PERMISSIVE BIAS, not a
     claim about GitHub's real (case-sensitive, per git) branch-name
     matching — see `_push_ref_matcher`'s docstring.

A condition judged satisfiable ONLY because at least one witnessing trigger
path's ref was `_any_ref` (unconstrained/unknown, declared limit #2) — i.e.
no trigger path this workflow's `on:` block can produce proves it true
without that assumption — is never folded into the "every in-scope if: is
satisfiable" clean report. It is counted and printed in its own
"SATISFIABLE ONLY UNDER AN ASSUMED/UNKNOWN REF" section instead (exit code
unchanged): a decision made on a value this module admits it cannot know
must never be presented as the same kind of coverage as a proven one.

Usage:
    python3 scripts/ci/lint_unreachable_workflow_conditions.py [--repo-root .]

Exit codes: 0 zero findings (an UNDECIDED-only, assumed-satisfiable-only, or
fully-clean run — none of these are a "finding") · 1 one or more unreachable
`if:` conditions found ·
2 CANNOT VERIFY — PyYAML missing, `git ls-files` failed, zero tracked
workflow files matched, or a workflow file failed to parse as YAML
(W84 "esiste ≠ armato": a blind/broken scan must never exit 0).
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:
    print(
        "lint_unreachable_workflow_conditions: CANNOT VERIFY — PyYAML is not "
        "installed (pip install pyyaml)",
        file=sys.stderr,
    )
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Only these two fields are modeled. An `if:` that never names either, as a
# whole word (so `github.ref_name`/`github.ref_type`/`github.ref_protected`
# do NOT count as naming `github.ref` — different fields, deliberately not
# matched by a bare substring per cicatrix-superscar #3's own rule: judge
# the entity, not the form), is entirely out of this guard's scope.
_RELEVANT_FIELD_RE = re.compile(r"\bgithub\.(event_name|ref)\b")
_FREE_FUNCS = ("failure", "success", "always", "cancelled")


# --------------------------------------------------------------- trigger model


@dataclass(frozen=True)
class TriggerPath:
    """One (event, ref-constraint) pair a workflow's `on:` block can actually
    deliver a `failure()`-eligible run through. `ref_matcher` decides, for a
    literal like `'refs/heads/main'`, whether THIS trigger path could ever
    carry that as `github.ref`. `description` is a short human label for
    reporting — never used for the decision itself."""

    event: str
    ref_matcher: Callable[[str], bool]
    description: str

    def ref_satisfies(self, ref_literal: str) -> bool:
        return self.ref_matcher(ref_literal)


def _any_ref(_: str) -> bool:
    """Ref is unconstrained/unknown for this trigger path — bias toward
    'satisfiable' (declared limit #2 above). Named, not a bare lambda, so a
    trace built from it reads clearly."""
    return True


_REFS_HEADS_PREFIX = "refs/heads/"

# GitHub's filter-pattern glob defines `+` ("one or more of the preceding
# character") and `\` (escape the next character) on top of the `*`/`?`/
# `[seq]`/`[!seq]` subset `fnmatch` already shares the meaning of. `fnmatch`
# treats both as ordinary literal characters instead (declared limit #2) —
# a `branches:` entry using either is outside the modeled subset.
_GITHUB_GLOB_ONLY_METACHARS = ("+", "\\")


def _branches_use_unmodeled_glob_syntax(branches: list[str]) -> bool:
    return any(any(ch in b for ch in _GITHUB_GLOB_ONLY_METACHARS) for b in branches)


def _push_ref_matcher(branches: list[str]) -> Callable[[str], bool]:
    """Decides whether a `github.ref == '<ref_literal>'` comparison could be
    true for a push trigger constrained to `branches:` patterns.

    Two DIFFERENT case-folding decisions live here, kept deliberately
    distinct (declared limit #4):

      1. The `refs/heads/` PREFIX check on `ref_literal` is casefolded
         because GitHub's `==` operator itself ignores case for the whole
         compared string (docs.github.com/en/actions/reference/
         workflows-and-actions/expressions: "GitHub ignores case when
         comparing strings") — this fold is CORRECT per GitHub's documented
         expression semantics, not a bias.
      2. Whether the branch text extracted from `ref_literal` then matches
         one of `branches:`'s glob patterns is ALSO matched casefolded, but
         real git branch names ARE case-sensitive, so this second fold is
         NOT a claim about how GitHub actually matches branch names — it is
         a DELIBERATE PERMISSIVE BIAS (rule 4: bias toward silence). It can
         only turn a real finding into a missed detection (more matches ->
         more satisfiable), never manufacture a false accusation.
    """

    def matcher(ref_literal: str) -> bool:
        if not ref_literal.casefold().startswith(_REFS_HEADS_PREFIX.casefold()):
            return False
        branch = ref_literal[len(_REFS_HEADS_PREFIX) :]
        return any(
            fnmatch.fnmatch(branch.casefold(), pattern.casefold())
            for pattern in branches
            if isinstance(pattern, str)
        )

    return matcher


def _is_exact_branch_push(cfg: dict[str, Any]) -> bool:
    """True only when `branches:` is the SOLE ref-relevant filter key present.
    Combining it with `branches-ignore`/`tags`/`tags-ignore` changes the
    semantics in ways this module does not model (declared limit #2) — falls
    back to `_any_ref` instead of guessing."""
    if "branches" not in cfg or not isinstance(cfg["branches"], list):
        return False
    return not any(k in cfg for k in ("branches-ignore", "tags", "tags-ignore"))


def extract_trigger_paths(on_block: Any) -> list[TriggerPath]:
    """Builds the trigger-path set from a parsed `on:` block. Accepts all
    three YAML shapes GitHub allows: a bare string (`on: push`), a list
    (`on: [push, pull_request]`), or a mapping (the common case)."""
    if on_block is None:
        return []
    if isinstance(on_block, str):
        return [TriggerPath(event=on_block, ref_matcher=_any_ref, description=on_block)]
    if isinstance(on_block, list):
        return [
            TriggerPath(event=e, ref_matcher=_any_ref, description=e)
            for e in on_block
            if isinstance(e, str)
        ]
    if not isinstance(on_block, dict):
        return []

    paths: list[TriggerPath] = []
    for event, cfg in on_block.items():
        if not isinstance(event, str):
            continue
        if event == "push" and isinstance(cfg, dict) and _is_exact_branch_push(cfg):
            branches = [b for b in cfg["branches"] if isinstance(b, str)]
            if _branches_use_unmodeled_glob_syntax(branches):
                paths.append(
                    TriggerPath(
                        event="push",
                        ref_matcher=_any_ref,
                        description=(
                            f"push (branches: {branches!r}, glob syntax outside the "
                            "modeled subset [+ or \\ present] -> ref unconstrained)"
                        ),
                    )
                )
            else:
                paths.append(
                    TriggerPath(
                        event="push",
                        ref_matcher=_push_ref_matcher(branches),
                        description=f"push (branches: {branches!r})",
                    )
                )
        else:
            paths.append(TriggerPath(event=event, ref_matcher=_any_ref, description=event))
    return paths


def _on_block(doc: Any) -> Any:
    """PyYAML parses a bare `on:` key as the boolean `True` (YAML 1.1 boolean
    literal) — `doc.get(True) or doc.get('on')` covers both spellings, same
    pattern as scripts/ci/check_required_workflow_conformance.py and
    scripts/verify_main_watch_schedule_scope.py."""
    if not isinstance(doc, dict):
        return None
    if True in doc:
        return doc[True]
    return doc.get("on")


# --------------------------------------------------------------- expression parser
#
# A hand-rolled recursive-descent parser/evaluator for the DELIBERATELY
# NARROW shape declared in the module docstring. This is not, and must never
# grow into, a general GitHub Actions expression interpreter (same "known
# limit" discipline as scripts/verify_main_watch_schedule_scope.py and
# scripts/check_watcher_coverage.py) — anything outside the shape raises
# _UnsupportedExpression, which the caller turns into an UNDECIDED entry,
# never a guess.


class _UnsupportedExpression(Exception):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<lparen>\()  |
        (?P<rparen>\))  |
        (?P<and>&&)     |
        (?P<or>\|\|)    |
        (?P<eq>==)      |
        (?P<ne>!=)      |
        (?P<bang>!)     |
        (?P<string>'[^']*'|"[^"]*") |
        (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
    )
    """,
    re.VERBOSE,
)


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    n = len(expr)
    while pos < n:
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            if expr[pos:].strip() == "":
                break
            raise _UnsupportedExpression(f"unrecognized character at position {pos}: {expr[pos:pos + 12]!r}")
        pos = m.end()
        kind = m.lastgroup
        assert kind is not None
        tokens.append(_Token(kind, m.group(kind)))
    return tokens


def _unquote(raw: str) -> str:
    return raw[1:-1]


def _resolve_field(ident: str) -> str | None:
    if ident == "github.event_name":
        return "event_name"
    if ident == "github.ref":
        return "ref"
    return None


# AST nodes are plain tuples: ("free",) | ("cmp", field, literal) |
# ("and", lhs, rhs) | ("or", lhs, rhs). Kept untyped deliberately — this
# parser's whole surface is ~60 lines and a dataclass hierarchy would cost
# more than it clarifies here.


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> _Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self) -> _Token:
        tok = self._peek()
        if tok is None:
            raise _UnsupportedExpression("unexpected end of expression")
        self.pos += 1
        return tok

    def parse(self) -> tuple:
        if not self.tokens:
            raise _UnsupportedExpression("empty expression")
        node = self._parse_or()
        if self.pos != len(self.tokens):
            raise _UnsupportedExpression(f"unexpected trailing token {self._peek()!r}")
        return node

    def _parse_or(self) -> tuple:
        node = self._parse_and()
        while self._peek() is not None and self._peek().kind == "or":
            self._advance()
            node = ("or", node, self._parse_and())
        return node

    def _parse_and(self) -> tuple:
        node = self._parse_unary()
        while self._peek() is not None and self._peek().kind == "and":
            self._advance()
            node = ("and", node, self._parse_unary())
        return node

    def _parse_unary(self) -> tuple:
        tok = self._peek()
        if tok is None:
            raise _UnsupportedExpression("unexpected end of expression")
        if tok.kind == "bang":
            raise _UnsupportedExpression("`!` (logical NOT) is outside the analyzable shape")
        if tok.kind == "lparen":
            self._advance()
            node = self._parse_or()
            close = self._peek()
            if close is None or close.kind != "rparen":
                raise _UnsupportedExpression("unbalanced parentheses")
            self._advance()
            return node
        if tok.kind == "ident":
            ident = self._advance()
            nxt = self._peek()
            if nxt is not None and nxt.kind == "lparen":
                self._advance()
                close = self._peek()
                if close is None or close.kind != "rparen":
                    raise _UnsupportedExpression(
                        f"function call `{ident.value}(...)` with arguments is outside the analyzable shape"
                    )
                self._advance()
                if ident.value not in _FREE_FUNCS:
                    raise _UnsupportedExpression(
                        f"function `{ident.value}()` is outside the analyzable shape "
                        f"(only {'/'.join(_FREE_FUNCS)} are treated as free)"
                    )
                return ("free",)
            return self._parse_comparison(("ident", ident.value))
        if tok.kind == "string":
            self._advance()
            return self._parse_comparison(("string", _unquote(tok.value)))
        raise _UnsupportedExpression(f"unexpected token {tok!r}")

    def _parse_comparison(self, lhs: tuple[str, str]) -> tuple:
        op = self._peek()
        if op is None or op.kind not in ("eq", "ne"):
            raise _UnsupportedExpression(
                "expected `==` — a bare identifier/string outside a comparison is outside the analyzable shape"
            )
        if op.kind == "ne":
            raise _UnsupportedExpression("`!=` is outside the analyzable shape (only `==` is modeled)")
        self._advance()
        rhs_tok = self._advance()
        if rhs_tok.kind == "string":
            rhs: tuple[str, str] = ("string", _unquote(rhs_tok.value))
        elif rhs_tok.kind == "ident":
            rhs = ("ident", rhs_tok.value)
        else:
            raise _UnsupportedExpression("comparison operand is outside the analyzable shape")

        if lhs[0] == "ident" and rhs[0] == "string":
            field_tok, literal = lhs[1], rhs[1]
        elif rhs[0] == "ident" and lhs[0] == "string":
            field_tok, literal = rhs[1], lhs[1]
        else:
            raise _UnsupportedExpression("comparison is not `<field> == '<literal>'` shape")

        field = _resolve_field(field_tok)
        if field is None:
            raise _UnsupportedExpression(
                f"`{field_tok}` is not a modeled field (only github.event_name / github.ref)"
            )
        return ("cmp", field, literal)


def _evaluate(node: tuple, trigger: TriggerPath) -> bool:
    """`event_name` comparisons are casefolded per GitHub's documented `==`
    semantics ("GitHub ignores case when comparing strings" — declared
    limit #4); `ref` comparisons delegate to `trigger.ref_satisfies`, which
    does its own casefolding (see `_push_ref_matcher`)."""
    kind = node[0]
    if kind == "free":
        return True
    if kind == "cmp":
        _, cfield, literal = node
        if cfield == "event_name":
            return trigger.event.casefold() == literal.casefold()
        return trigger.ref_satisfies(literal)
    if kind == "and":
        return _evaluate(node[1], trigger) and _evaluate(node[2], trigger)
    if kind == "or":
        return _evaluate(node[1], trigger) or _evaluate(node[2], trigger)
    raise AssertionError(f"unknown AST node kind {kind!r}")  # pragma: no cover


def _evaluate_certain(node: tuple, trigger: TriggerPath) -> bool:
    """Same shape and casefolding as `_evaluate`, but a `ref` comparison
    against a trigger path whose ref is UNCONSTRAINED (`trigger.ref_matcher
    is _any_ref`) counts as UNKNOWN — i.e. NOT true — rather than assumed
    true. Used only to separate 'genuinely satisfiable' (this function
    returns True for some trigger path) from 'satisfiable only because an
    unknown ref could not be disproven' (`_evaluate` says True, this
    function says False for every trigger path) — declared limit #4's third
    bucket. Deliberately conservative on `and`/`or`: an unknown operand
    reads as False here even where the real value might make the whole
    expression true, because the question this function answers is 'is
    there a trigger path that proves it WITHOUT guessing', not 'what is the
    real value'."""
    kind = node[0]
    if kind == "free":
        return True
    if kind == "cmp":
        _, cfield, literal = node
        if cfield == "event_name":
            return trigger.event.casefold() == literal.casefold()
        if trigger.ref_matcher is _any_ref:
            return False
        return trigger.ref_satisfies(literal)
    if kind == "and":
        return _evaluate_certain(node[1], trigger) and _evaluate_certain(node[2], trigger)
    if kind == "or":
        return _evaluate_certain(node[1], trigger) or _evaluate_certain(node[2], trigger)
    raise AssertionError(f"unknown AST node kind {kind!r}")  # pragma: no cover


def _explain(node: tuple, trigger: TriggerPath) -> tuple[bool, str]:
    """Same evaluator as `_evaluate`, but also returns a human-readable trace
    of how the verdict was reached — auto-derived from the AST that made the
    call, so it can never drift from the decision the way hand-authored
    prose could (cicatrix-superscar #6: don't trust a report a tool didn't
    just produce)."""
    kind = node[0]
    if kind == "free":
        return True, "(free)"
    if kind == "cmp":
        _, cfield, literal = node
        if cfield == "event_name":
            val = trigger.event.casefold() == literal.casefold()
            return val, f"event_name=='{literal}' is {val} (trigger event: '{trigger.event}')"
        val = trigger.ref_satisfies(literal)
        return val, f"ref=='{literal}' is {val}"
    if kind == "and":
        lv, lt = _explain(node[1], trigger)
        rv, rt = _explain(node[2], trigger)
        return (lv and rv), f"({lt} && {rt})"
    if kind == "or":
        lv, lt = _explain(node[1], trigger)
        rv, rt = _explain(node[2], trigger)
        return (lv or rv), f"({lt} || {rt})"
    raise AssertionError(f"unknown AST node kind {kind!r}")  # pragma: no cover


def mentions_relevant_fields(if_text: str) -> bool:
    """Pre-filter: an `if:` that never names `github.event_name`/`github.ref`
    is entirely out of this guard's scope — e.g. `needs.build.result ==
    'success'` — and is not even added to the 'not analyzed' list (that list
    is for conditions this guard's DOMAIN covers but whose SHAPE it cannot
    decide, not for every condition in every workflow)."""
    return bool(_RELEVANT_FIELD_RE.search(if_text))


def analyze_condition(
    if_text: str, trigger_paths: list[TriggerPath]
) -> tuple[bool | None, str, tuple | None]:
    """Returns (satisfiable, reason, ast). `satisfiable` is True/False when
    the expression is inside the analyzable shape and the workflow has at
    least one trigger path; None means UNDECIDED, with `reason` explaining
    why (parse failure, or zero trigger paths to evaluate against)."""
    try:
        tokens = _tokenize(if_text)
        ast = _Parser(tokens).parse()
    except _UnsupportedExpression as e:
        return None, str(e), None
    if not trigger_paths:
        return None, "workflow's `on:` block yielded zero trigger paths — cannot evaluate", ast
    satisfiable = any(_evaluate(ast, tp) for tp in trigger_paths)
    return satisfiable, "", ast


# --------------------------------------------------------------- workflow structure


@dataclass
class IfCondition:
    file: str
    scope: str
    text: str
    line: int | None = None


_IF_LINE_RE = re.compile(r"^(?P<indent>\s*)if:\s?(?P<rest>.*)$")
_BLOCK_SCALAR_INDICATORS = (">", ">-", ">+", "|", "|-", "|+")


def _fold_block_scalar_body(indicator: str, indent_len: int, lines: list[str], start: int) -> tuple[str, int]:
    """Approximates YAML's real block-scalar folding for the body starting
    at `lines[start]` (the line after `if: <indicator>`), well enough to
    usually reconstruct PyYAML's own parsed string for line-matching
    (`_attach_line_numbers` never trusts a MISmatch here to attach a wrong
    line — a folding gap just means one more condition falls back to no
    line number, never a wrong one). Returns (folded_text, next_index).

    LITERAL (`|`, `|-`, `|+`): every line break is kept verbatim — this
    module never folds a `|` scalar.
    FOLDED (`>`, `>-`, `>+`, the shape this repo's own multi-line `if:`
    conditions actually use, verified live 2026-08-20 against
    `main-push-failure-watch.yml`): a line break between two lines both at
    the block's OWN base indentation folds to a single space; a break next
    to a blank line, or a line indented MORE than the base, is kept
    literal, per YAML's documented folding rule — this is what lets a
    `>`-folded condition's wrapped continuation lines reconstruct the exact
    same string PyYAML parses.
    """
    literal = indicator.startswith("|")
    base_indent_len: int | None = None
    segments: list[str] = []
    prev_kind: str | None = None  # "normal" | "more_indented" | "blank" | None (first line)
    j = start
    while j < len(lines):
        line = lines[j]
        if line.strip() == "":
            if base_indent_len is None:
                # Leading blank lines inside the block are part of the
                # scalar too, but with no content yet to anchor a fold
                # decision on — treat as a paragraph break once content
                # starts; skip for now (matches YAML: leading blanks don't
                # set the indentation).
                j += 1
                continue
            segments.append("\n")
            prev_kind = "blank"
            j += 1
            continue
        cur_indent_len = len(line) - len(line.lstrip())
        if base_indent_len is None:
            if cur_indent_len <= indent_len:
                break
            base_indent_len = cur_indent_len
        if cur_indent_len < base_indent_len:
            break
        content = line[base_indent_len:]
        if literal:
            segments.append(content if prev_kind is None else "\n" + content)
        else:
            more_indented = content.startswith((" ", "\t"))
            kind = "more_indented" if more_indented else "normal"
            if prev_kind is None:
                segments.append(content)
            elif prev_kind == "normal" and kind == "normal":
                segments.append(" " + content)
            else:
                segments.append("\n" + content)
            prev_kind = kind
        j += 1
    return "".join(segments), j


def _raw_if_lines(text: str) -> list[tuple[int, str]]:
    """Best-effort (file line number, folded if-text) pairs scanned straight
    from the raw file text, in document order — used ONLY to attach a line
    number to each structurally-found `if:` for reporting. The actual
    satisfiability analysis always uses PyYAML's parsed value (declared
    limit: `_fold_block_scalar_body`'s folding is an approximation of
    YAML's real folding rules, good enough to locate a line for the common
    shapes this repo uses, not trusted for anything else — a mismatch here
    can only cost a line number via `_attach_line_numbers`'s exact-text
    match, never attach a wrong one)."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        m = _IF_LINE_RE.match(lines[i])
        if m:
            indent = m.group("indent")
            rest = m.group("rest").rstrip()
            if rest in _BLOCK_SCALAR_INDICATORS:
                rest, next_i = _fold_block_scalar_body(rest, len(indent), lines, i + 1)
                out.append((i + 1, rest))
                i = next_i
                continue
            out.append((i + 1, rest))
        i += 1
    return out


def _iter_if_conditions(doc: dict[str, Any], file_rel: str) -> list[IfCondition]:
    conditions: list[IfCondition] = []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return conditions
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        job_if = job.get("if")
        if isinstance(job_if, str):
            conditions.append(IfCondition(file=file_rel, scope=f"job:{job_id}", text=job_if))
        steps = job.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_if = step.get("if")
                if isinstance(step_if, str):
                    step_name = step.get("name", "<unnamed step>")
                    conditions.append(
                        IfCondition(file=file_rel, scope=f"job:{job_id} step:{step_name!r}", text=step_if)
                    )
    return conditions


def _normalize_raw_if_text(rest: str) -> str:
    """Strips one layer of matching outer quotes from a raw if:-line's tail
    (the common `if: "expr"` / `if: 'expr'` shape) so it can be compared
    against PyYAML's already-unquoted parsed value. Never attempts full
    YAML scalar folding beyond what `_raw_if_lines` already does for block
    scalars — a text that still does not match after this is left
    unmatched, not guessed at."""
    if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ("'", '"'):
        return rest[1:-1]
    return rest


def _attach_line_numbers(conditions: list[IfCondition], raw_lines: list[tuple[int, str]]) -> None:
    """Matches each condition to its raw file line BY TEXT, never by
    traversal ORDER. `conditions` is a STRUCTURAL traversal (job `if:`
    always visited before that job's step `if:`s, per `_iter_if_conditions`
    — regardless of where the job-level `if:` key actually sits in the
    file); `raw_lines` is a RAW top-to-bottom scan. A job-level `if:`
    written textually AFTER `steps:` (legal YAML — key order inside a
    mapping is free) makes the two lists visit the same two conditions in
    OPPOSITE order, so a positional zip silently SWAPS their line numbers
    (verified live, 2026-08-20 — reproduced with exactly this shape; the
    old docstring here claimed this "degrades to a missing line number …
    never a WRONG line", which was false — the claim was the worse half of
    the defect, see this PR's commit message).

    A condition's (quote-normalized) text that occurs EXACTLY ONCE among
    `conditions` and EXACTLY ONCE among `raw_lines` is unambiguous and gets
    that line. Any text that repeats — on either side — is genuinely
    ambiguous (which occurrence is which cannot be recovered from text
    alone) and is left with `line=None` for every condition sharing it:
    an absent line number, never a guessed one."""
    text_to_lines: dict[str, list[int]] = {}
    for line_no, rest in raw_lines:
        text_to_lines.setdefault(_normalize_raw_if_text(rest), []).append(line_no)
    cond_text_counts = Counter(c.text for c in conditions)

    for cond in conditions:
        candidate_lines = text_to_lines.get(cond.text, [])
        if len(candidate_lines) == 1 and cond_text_counts[cond.text] == 1:
            cond.line = candidate_lines[0]
        # else: zero raw matches, or the text repeats somewhere -> ambiguous,
        # leave cond.line at its default (None).


@dataclass
class Finding:
    condition: IfCondition
    on_summary: str
    mechanism: str


@dataclass
class Undecided:
    condition: IfCondition
    reason: str


@dataclass
class AssumedSatisfiable:
    """A condition this module calls 'satisfiable', where every trigger
    path that makes it true does so only via an UNCONSTRAINED
    (`_any_ref`) ref — i.e. this module could not DISPROVE it, but the
    verdict is not proven against a real, modeled ref either (declared
    limit #4's third bucket). Never counted as a clean, proven pass."""

    condition: IfCondition
    on_summary: str
    mechanism: str


@dataclass
class WorkflowResult:
    file: str
    parse_error: str | None = None
    findings: list[Finding] = field(default_factory=list)
    undecided: list[Undecided] = field(default_factory=list)
    assumed_satisfiable: list[AssumedSatisfiable] = field(default_factory=list)
    in_scope_count: int = 0


def _summarize_on_block(on_block: Any, trigger_paths: list[TriggerPath]) -> str:
    if not trigger_paths:
        return f"on: {on_block!r} (no trigger paths extracted)"
    return "on: " + ", ".join(tp.description for tp in trigger_paths)


def analyze_workflow(path: Path, repo_root: Path) -> WorkflowResult:
    rel = str(path.relative_to(repo_root))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return WorkflowResult(file=rel, parse_error=f"could not read file: {e}")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return WorkflowResult(file=rel, parse_error=f"YAML parse error: {e}")
    if not isinstance(doc, dict):
        return WorkflowResult(file=rel, parse_error="workflow document is not a mapping")

    on_block = _on_block(doc)
    trigger_paths = extract_trigger_paths(on_block)
    on_summary = _summarize_on_block(on_block, trigger_paths)

    structural = _iter_if_conditions(doc, rel)
    raw_lines = _raw_if_lines(text)
    _attach_line_numbers(structural, raw_lines)

    result = WorkflowResult(file=rel)
    for cond in structural:
        if not mentions_relevant_fields(cond.text):
            continue
        result.in_scope_count += 1
        satisfiable, reason, ast = analyze_condition(cond.text, trigger_paths)
        if satisfiable is None:
            result.undecided.append(Undecided(condition=cond, reason=reason))
        elif satisfiable is False:
            assert ast is not None
            mechanism = "\n".join(f"    - {tp.description}: {_explain(ast, tp)[1]}" for tp in trigger_paths) or (
                "    (workflow's `on:` block produced zero trigger paths)"
            )
            result.findings.append(Finding(condition=cond, on_summary=on_summary, mechanism=mechanism))
        else:
            assert ast is not None
            if any(_evaluate_certain(ast, tp) for tp in trigger_paths):
                continue  # proven true against at least one modeled/real trigger path
            witnesses = [tp for tp in trigger_paths if _evaluate(ast, tp)]
            mechanism = "\n".join(f"    - {tp.description}: {_explain(ast, tp)[1]}" for tp in witnesses)
            result.assumed_satisfiable.append(
                AssumedSatisfiable(condition=cond, on_summary=on_summary, mechanism=mechanism)
            )
    return result


# --------------------------------------------------------------- driver


def discover_tracked_workflows(repo_root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--", ".github/workflows/*.yml", ".github/workflows/*.yaml"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"lint_unreachable_workflow_conditions: CANNOT VERIFY — `git ls-files` failed: {e}", file=sys.stderr)
        sys.exit(2)
    if proc.returncode != 0:
        print(
            f"lint_unreachable_workflow_conditions: CANNOT VERIFY — `git ls-files` exited "
            f"{proc.returncode}: {proc.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    return sorted(repo_root / line for line in proc.stdout.splitlines() if line.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    workflows = discover_tracked_workflows(repo_root)
    if not workflows:
        print(
            "lint_unreachable_workflow_conditions: CANNOT VERIFY — zero tracked "
            ".github/workflows/*.yml files found (blind scan, W84)",
            file=sys.stderr,
        )
        return 2

    parse_errors: list[tuple[str, str]] = []
    all_findings: list[Finding] = []
    all_undecided: list[Undecided] = []
    all_assumed: list[AssumedSatisfiable] = []
    total_in_scope = 0

    for wf in workflows:
        result = analyze_workflow(wf, repo_root)
        if result.parse_error:
            parse_errors.append((result.file, result.parse_error))
            continue
        total_in_scope += result.in_scope_count
        all_findings.extend(result.findings)
        all_undecided.extend(result.undecided)
        all_assumed.extend(result.assumed_satisfiable)

    if parse_errors:
        print(
            f"lint_unreachable_workflow_conditions: CANNOT VERIFY — {len(parse_errors)} "
            f"workflow(s) failed to parse:",
            file=sys.stderr,
        )
        for f, err in parse_errors:
            print(f"  ✗ {f}: {err}", file=sys.stderr)
        return 2

    print(
        f"lint_unreachable_workflow_conditions: {len(workflows)} workflow(s) scanned, "
        f"{total_in_scope} if: condition(s) in scope (name github.event_name/github.ref), "
        f"{len(all_findings)} finding(s), {len(all_undecided)} not analyzed, "
        f"{len(all_assumed)} satisfiable-only-under-assumed-ref"
    )

    if all_findings:
        print("\nUNREACHABLE — false under every trigger path this workflow's own `on:` block can produce:")
        for finding in all_findings:
            c = finding.condition
            loc = f"{c.file}:{finding.condition.line}" if finding.condition.line else c.file
            print(f"  ✗ {loc} [{c.scope}]")
            print(f"    if: {c.text}")
            print(f"    {finding.on_summary}")
            print(f"    mechanism (evaluated per trigger path):")
            print(finding.mechanism)

    if all_undecided:
        print(f"\nNOT ANALYZED ({len(all_undecided)} of {total_in_scope} in-scope condition(s)) — outside the")
        print("decidable shape (declared limit #1 in this script's module docstring), never counted as clean:")
        for u in all_undecided:
            c = u.condition
            loc = f"{c.file}:{c.line}" if c.line else c.file
            print(f"  ? {loc} [{c.scope}]: {c.text}")
            print(f"    reason: {u.reason}")

    if all_assumed:
        print(
            f"\nSATISFIABLE ONLY UNDER AN ASSUMED/UNKNOWN REF ({len(all_assumed)} of "
            f"{total_in_scope} in-scope condition(s)) — this guard could not DISPROVE"
        )
        print(
            "these, but the 'satisfiable' verdict rests entirely on an unconstrained trigger "
            "path (declared limit #2/#4), never a proven reachable ref — not the same kind of "
            "coverage as a proven pass, and never counted as one:"
        )
        for a in all_assumed:
            c = a.condition
            loc = f"{c.file}:{c.line}" if c.line else c.file
            print(f"  ~ {loc} [{c.scope}]: {c.text}")
            print(f"    {a.on_summary}")
            print(f"    mechanism (evaluated per assumed-ref trigger path):")
            print(a.mechanism)

    if not all_findings and not all_undecided and not all_assumed:
        print("  ✓ every in-scope if: is satisfiable under at least one real trigger path")

    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
