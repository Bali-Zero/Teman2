#!/usr/bin/env python3
"""Refuse any code that READS `legal_status`. Writing it is still allowed.

Measured 2026-08-25 across all 84,283 points of `legal_unified_hybrid_hybrid`:
the field is derived by `STATUS_PATTERNS` in backend/core/legal/constants.py —
two bare regexes over chunk text, first match wins by dict order:

    dicabut: DICABUT|TIDAK BERLAKU|DIGANTI
    berlaku: BERLAKU|MASIH BERLAKU

The two OVERLAP: "TIDAK BERLAKU" contains "BERLAKU", so both match the same
string and only dict order decides. Consequences, all reproduced against live
text rather than reasoned about:

  * "Ketentuan ini tidak berlaku bagi warga negara asing" — a provision that
    does not apply to a class of PERSON marks the whole chunk revoked.
  * "penjamin dapat digantikan" — DIGANTI matches inside `digantikan`, so a
    guarantor being substituted revokes the regulation.
  * A law's own closing clause revoking its PREDECESSOR marks the CURRENT,
    still-valid law dead. That is the live PP_31_2013 case.

The field therefore names a document-level fact and holds chunk-level noise:
9 document_ids carry BOTH named values across their own points (Permen_1_2026:
dicabut 931 / berlaku 575). A document cannot honestly be both. Corpus-wide,
42,420 points say `dicabut` and 26,107 say `berlaku`; the two largest documents
marked revoked — UU_40_2007 and UU_6_2023 — are both independently confirmed in
force.

Zero signed (2026-08-25, decision 5) MARK over REMOVE, and the mark lives in
`kb/topics/<topic>.yaml`: per document, sourced, with an explicit
`source_verified`, gated by the G3 contract. This lint exists so the broken
signal cannot quietly become load-bearing before it is re-derived. As of
2026-08-25 the write site itself was also retired (PR #4948) — `main()` counts
write sites rather than asserting a fixed one exists, so that fact stays
measured, not remembered (see `count_writes` / "clean — 0 reads, N write
site(s)." below; this is the second time in one day this file asserted a fact
it had not measured — see `git log -- scripts/ci/legal_status_read_lint.py`).

WHAT THIS CATCHES, AND WHAT IT CANNOT (read before trusting a green run)
The promise here is NOT "no read escapes" — it is "no *statically resolvable*
read escapes, and this is exactly what that boundary is." A guard that claims
the absolute while it can only ever deliver the relative is worse than one
that names its own edge, which is the whole point of this campaign.

Caught, because every one of these is a fixed shape an AST can fold or match
without running the code: a dict-literal key (`{"legal_status": ...}`), a
`.get()`/subscript read, an attribute read (`point.legal_status`), a
class-pattern match keyword (`case Point(legal_status=x):` — `MatchClass`'s
`kwd_attrs` names the attribute being READ off `point`, same as the attribute
case), a dict-pattern match key (`case {"legal_status": x}:` — `MatchMapping`
keys are ordinary `ast.Constant` nodes, so the existing constant check already
covers this, nothing new needed), and any of these four STRING-BUILDING shapes
so long as every operand is itself a literal: `+`-concatenation
(`"legal_" + "status"`), `%`-formatting (`"legal_%s" % "status"`), `.format()`
(`"legal_{}".format("status")`), and `"".join()` of a literal tuple/list
(`"".join(("legal", "_status"))`). An earlier version of this file's docstring
claimed `.format()`/`%` could not be caught by any AST lint — that claim was
wrong for exactly this fully-literal case (it IS resolvable without running
the code, the same way `+`-concatenation always was) and has been removed;
what stays true is that NONE of these four fold when any operand is not a
literal — see below.

NOT caught, and each for a different reason, not one blanket "dynamic" excuse:

  * A name assembled from something that only exists at runtime — a config
    value, an environment variable, an f-string with a computed part,
    `getattr(obj, name)` with a dynamic `name`, or a name built one character
    at a time. Genuinely unknowable without running the code.
  * A field-name CONSTANT imported from another module and aliased
    (`from external_contract import LEGAL_STATUS as KEY; payload[KEY]`). The
    value is static, but resolving it means reading a DIFFERENT file, tracking
    what it exports, and handling re-exports/relative imports — cross-module
    constant propagation is a materially bigger undertaking than folding one
    expression in the file already being scanned, and is not attempted here.
  * A keyword ARGUMENT whose name happens to be `legal_status`
    (`consume(legal_status=value)`) is not a read at all — it is a value being
    PASSED under that name, the call-argument equivalent of a dict-literal
    write, and this lint does not flag it (an `ast.keyword`'s `.arg` is a raw
    Python string, never visited as an expression node, so there is nothing
    here that would flag it — this is not a special case, just what the
    visitor already does not do).
  * `**payload` / `{**payload}` spreads: these read EVERY key `payload`
    happens to hold, `legal_status` included if present — but there is no
    literal string "legal_status" anywhere in the source for this shape to
    match against. Catching it soundly needs to know whether the spread
    SOURCE is payload-shaped at all, which is type/dataflow information this
    lint does not have; catching it unsoundly (flagging every `**name` spread
    in the codebase regardless of what `name` is) would bury the real findings
    in noise from every unrelated kwargs-forwarding call. Named here as a
    known, accepted gap rather than attempted.

A lint that implied completeness on any of the above would be exactly the
failure this campaign exists to correct — a false certificate is worse than an
honestly incomplete one — so this scans the shapes it can see and says so,
rather than the reverse.

SCOPE: scanned roots are named by `_roots()` and printed in every run's first
line — see that function for which directories, and why, before trusting a
"0 reads" from a run whose scanned-roots line you have not read.

Exit 0 clean · 1 a read was found · 2 the lint could not run.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FIELD = "legal_status"
NESTED = "metadata.legal_status"


def _roots(repo: Path) -> list[Path]:
    """Every directory this lint actually walks — read this before trusting a
    "0 reads" from `main()`'s summary line, which prints these paths verbatim.

    Narrowed to `apps/backend-rag/backend` alone until 2026-08-26: a Qdrant
    payload field like `legal_status` is not backend-rag-only in principle —
    ANY app that queries the collection directly, and any ops script under
    `scripts/` (this repo's own consumer-map audits, e.g. the one behind
    a475bddb7, explicitly scope themselves "whole repo, not just
    apps/backend-rag/backend"), can read it too. The narrow root let a lint
    that scanned ONE app claim "0 reads" as if it had checked the whole
    surface — stronger than what it measured.

    Scanned now: every app under `apps/` (not just backend-rag), `scripts/`
    (ops tooling — where a genuine external consumer would live), and `kb/`
    (this KB's own tooling, including this file's neighbours). NOT scanned,
    and this is a real boundary, not an oversight: `infra/`, `packages/`,
    root-level `tests/`, `research/`, and any one-off top-level script outside
    these three roots. A truly unbounded "whole repo" walk was considered and
    rejected — it would also crawl `output/`, `tmp/`, `snapshots/`, `vendor/`,
    and other non-source dumps this repo carries at its root, trading a
    smaller blind spot for a slower, noisier one with no source code in it.
    """
    return [repo / "apps", repo / "scripts", repo / "kb"]


_SELF = Path(__file__).resolve()


def _skip(path: Path) -> bool:
    # This lint's OWN file is excluded by exact identity, never by name or
    # directory pattern (a name-based skip would be the same fragile-magic-
    # string shortcut this module refuses elsewhere). It is a special case of
    # exactly one: `FIELD = "legal_status"` / `NESTED = "metadata.legal_status"`
    # are this file's comparison vocabulary, not a payload read — but a
    # variable assignment that folds to the field name is, BY DESIGN,
    # supposed to stay guilty everywhere else (`field = "legal_" + "status"`
    # is "the reviewer's exact evasion #1" in the guilt matrix, an assignment
    # is exactly where that evasion lives) — so this is deliberately NOT a
    # general "assignment is exempt" rule, which would silently reopen that
    # evasion for every other file in the scanned tree.
    if path.resolve() == _SELF:
        return True
    parts = set(path.parts)
    return bool(parts & {
        "tests", "__pycache__", ".venv", "venv", "migrations_v2",
        "node_modules", "dist", "build", ".next",
    })


def _folded_str(node: ast.AST) -> str | None:
    """Fold a fully-literal string expression into the value it evaluates to —
    or None the moment any part of it is not itself a string literal.

    Four shapes fold, each recursively so a multi-part chain folds too
    (`"le" + "gal_" + "status"`, `"legal".join(("_", "status"))` nested inside
    a further `%`, etc.):

      * `ast.Constant` — the base case, a plain literal.
      * `ast.BinOp(Add)` — `"legal_" + "status"`. (`"legal_" "status"`,
        adjacent literals with no operator, is already merged into one
        `ast.Constant` by the parser itself, so it never reaches this branch.)
      * `ast.BinOp(Mod)` — `"legal_%s" % "status"` or `"%s_%s" % (a, b)`;
        folded inline below via Python's own `%` operator on the resolved
        literal operands.
      * `ast.Call` to `.format()` / `"".join(...)` — delegates to
        `_folded_call`, the one shape that needs an actual method call
        (`str.format`/`str.join`) rather than a bare operator to evaluate.

    Every branch is wrapped so an operand that fails to fold, or a fold that
    itself raises (a malformed format spec, a `%`-arity mismatch), returns
    None rather than propagating — a string this function cannot prove folds
    to a fixed value must never be treated as if it does not exist at all.
    Deliberately does NOT attempt: an f-string with any non-literal part, or
    anything requiring information from outside this one expression (a name
    bound elsewhere, an import from another module) — see the module
    docstring's "NOT caught" section for why those specific cases are out of
    reach for a single-expression AST fold, not merely unimplemented here.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _folded_str(node.left)
        right = _folded_str(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = _folded_str(node.left)
        if left is None:
            return None
        if isinstance(node.right, ast.Tuple):
            values = [_folded_str(elt) for elt in node.right.elts]
            if any(v is None for v in values):
                return None
            operand: object = tuple(values)
        else:
            value = _folded_str(node.right)
            if value is None:
                return None
            operand = value
        try:
            return left % operand
        except (TypeError, ValueError):
            return None
    if isinstance(node, ast.Call):
        return _folded_call(node)
    return None


def _folded_call(node: ast.Call) -> str | None:
    """Fold `"...".format(...)` and `"sep".join((...))` when the base string
    and every argument are themselves fully literal — the SAME "resolvable
    within this one expression, no other file, no runtime value" contract
    `_folded_str` applies everywhere else, just for the two call-shaped forms
    a bare operator cannot express. A `**kwargs` spread into `.format()`
    bails out (returns None) rather than guessing what it might contain — the
    same "don't flag what isn't provably literal" discipline as everywhere
    else in this module. Actually calls `str.format`/`str.join` on the folded
    literal operands rather than reimplementing their semantics, so a
    malformed spec (`{0}` with no positional arg, mismatched braces) fails
    the same way Python itself would — caught and folded to None, never
    raised into the caller.
    """
    if not isinstance(node.func, ast.Attribute):
        return None
    base = _folded_str(node.func.value)
    if base is None:
        return None
    if node.func.attr == "format":
        args = [_folded_str(a) for a in node.args]
        if any(a is None for a in args):
            return None
        kwargs: dict[str, str] = {}
        for kw in node.keywords:
            if kw.arg is None:  # a `**spread` — not a fixed, named set of kwargs
                return None
            value = _folded_str(kw.value)
            if value is None:
                return None
            kwargs[kw.arg] = value
        try:
            return base.format(*args, **kwargs)
        except (KeyError, IndexError, ValueError):
            return None
    if node.func.attr == "join":
        if len(node.args) != 1 or node.keywords:
            return None
        items = node.args[0]
        if not isinstance(items, (ast.Tuple, ast.List)):
            return None
        parts = [_folded_str(elt) for elt in items.elts]
        if any(p is None for p in parts):
            return None
        return base.join(parts)
    return None


class _Reads(ast.NodeVisitor):
    """Every mention of the field that is NOT a key in a dict being built.

    A dict literal key is the ingestion WRITE — `{"legal_status": ...}` — and
    stays legal, whether the key is a plain string literal or a folded literal
    expression (concatenation, `%`, `.format()`, `.join()`) that evaluates to
    the same name. An attribute WRITE (`obj.legal_status = ...`, `ast.Attribute`
    with `Store` context) is legal for the same reason: this lint refuses
    reads, never writes, on principle — see the module docstring.

    Everything else that names the field is a read: `.get("legal_status")`,
    `payload["legal_status"]`, a Qdrant filter on "metadata.legal_status",
    `point.legal_status` (an `ast.Attribute` with `Load` context), any of the
    four literal string-building shapes `_folded_str` can fold (built anywhere
    other than a dict-literal key), or a class-pattern match keyword
    (`case Point(legal_status=x):` — `kwd_attrs` names an attribute being
    matched/READ off the subject, the pattern-matching analogue of
    `point.legal_status`). A dict-PATTERN match key (`case {"legal_status":
    x}:`) needs no dedicated visitor: `ast.MatchMapping.keys` are ordinary
    `ast.Constant` nodes, so `visit_Constant` already sees them via the normal
    tree walk — do not add a second mechanism for something already covered,
    per the "redundancy in a rule is redundancy in its proof" note below.
    """

    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []
        self.writes = 0
        self._written: set[int] = set()

    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if key is None:  # a **spread entry has no key node to fold
                continue
            folded = _folded_str(key)
            if folded in (FIELD, NESTED):
                self._written.add(id(key))
                self.writes += 1
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value in (FIELD, NESTED) and id(node) not in self._written:
            self.hits.append((node.lineno, str(node.value)))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        # A concatenation/%-format whose top-level Constant/BinOp children
        # already got walked on the way down does not double-report:
        # "legal_" and "status" alone never equal FIELD/NESTED, so only the
        # fully-folded node at the top of the chain can ever hit.
        if isinstance(node.op, (ast.Add, ast.Mod)) and id(node) not in self._written:
            folded = _folded_str(node)
            if folded in (FIELD, NESTED):
                self.hits.append((node.lineno, folded))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # `.format()` / `"".join(...)` — see _folded_call. Same non-double-
        # report reasoning as visit_BinOp: a literal argument alone never
        # equals FIELD/NESTED, only the fully-folded call can.
        if id(node) not in self._written:
            folded = _folded_call(node)
            if folded in (FIELD, NESTED):
                self.hits.append((node.lineno, folded))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # NESTED ("metadata.legal_status") is a dotted STRING, never a single
        # Python attribute name, so only FIELD applies here.
        if node.attr == FIELD:
            if isinstance(node.ctx, ast.Load):
                self.hits.append((node.lineno, node.attr))
            else:  # Store (obj.legal_status = ...) or Del: a write, stays legal
                self.writes += 1
        self.generic_visit(node)

    def visit_MatchClass(self, node: ast.MatchClass) -> None:
        # `kwd_attrs` is a list[str] — raw Python strings, never AST Constant
        # nodes — so this is the one shape visit_Constant structurally cannot
        # see no matter how the tree is walked; it needs its own visitor.
        # Always a read (matching an attribute out of the subject), never a
        # write — there is no Store-context equivalent for a match pattern.
        for attr, pattern in zip(node.kwd_attrs, node.kwd_patterns):
            if attr == FIELD:
                self.hits.append((pattern.lineno, attr))
        self.generic_visit(node)


def count_writes(src: str) -> int:
    """Dict-literal mentions in one module — the legal shape."""
    finder = _Reads()
    finder.visit(ast.parse(src))
    return finder.writes


def scan_source(src: str) -> list[tuple[int, str]]:
    """Public for tests: reads found in one module's source."""
    # ONE mechanism PER SHAPE, deliberately: visit_Dict marks a dict-literal
    # key's node id (plain or folded-concatenation) before generic_visit
    # descends into it, so a write is always seen first; visit_Attribute
    # exempts Store context the same way, at the same node, with no separate
    # pre-walk. An earlier version of the Dict/Constant pair also pre-walked
    # the tree marking the same keys — harmless, but it made the exemption
    # unfalsifiable: disabling either half left the other doing the job, and
    # the mutation that should have turned this file red stayed green.
    # Redundancy in a rule is redundancy in its proof — each shape below still
    # gets exactly one mechanism deciding it, never two agreeing by accident.
    finder = _Reads()
    finder.visit(ast.parse(src))
    return sorted(finder.hits)


ALLOW_MARKER = "legal-status-lint: allow"


def _is_marked_allow(src_lines: list[str], lineno: int) -> bool:
    """True if the physical line the read was found on carries an explicit,
    grep-able opt-in comment: `# legal-status-lint: allow — <why>`.

    This exists because widening `_roots()` (2026-08-26) makes this lint scan
    its OWN diagnostic tooling for the first time — `scripts/kb/audit_*.py`
    and friends exist specifically to INSPECT the broken field (report its
    distribution, propose a targeted repair), which is a materially different
    act from a production path making the broken signal load-bearing again.
    A directory-wide exemption for "the KB's own tooling" was considered and
    rejected: it is the same shape of blind spot the scope-widening exists to
    close, just moved rather than removed — a future genuine consumer landing
    in that same directory would get a silent free pass. A per-SITE marker
    instead requires an explicit, visible decision at the exact line, is
    always `grep`-able (`grep -rn "legal-status-lint: allow"`), and is never
    applied by this file — scan_source/main only make an already-present
    marker visible in the summary, they do not decide whether one is
    warranted. That judgment belongs to whoever reviews the diff adding the
    marker, the same as any other `MARK over REMOVE` decision this campaign
    already makes explicitly rather than silently (see module docstring,
    Zero decision 5).
    """
    if lineno < 1 or lineno > len(src_lines):
        return False
    return ALLOW_MARKER in src_lines[lineno - 1]


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    findings: list[str] = []
    allowed: list[str] = []
    scanned = 0
    writes = 0
    for root in _roots(repo):
        if not root.exists():
            print("BROKEN — %s does not exist; nothing was scanned." % root,
                  file=sys.stderr)
            return 2
        for path in sorted(root.rglob("*.py")):
            if _skip(path):
                continue
            scanned += 1
            try:
                src = path.read_text(encoding="utf-8")
                hits = scan_source(src)
                writes += count_writes(src)
            except SyntaxError as exc:
                print("BROKEN — %s could not be parsed: %s" % (path, exc),
                      file=sys.stderr)
                return 2
            src_lines = src.splitlines()
            for lineno, what in hits:
                entry = "%s:%d reads %r" % (path.relative_to(repo), lineno, what)
                if _is_marked_allow(src_lines, lineno):
                    allowed.append(entry)
                else:
                    findings.append(entry)

    if scanned == 0:
        print("BROKEN — 0 files scanned. A lint that reads nothing passes "
              "everything.", file=sys.stderr)
        return 2

    scanned_roots = ", ".join(str(r.relative_to(repo)) for r in _roots(repo))
    print("scanned %d module(s) under %s (see _roots() for the boundary)"
          % (scanned, scanned_roots))
    if allowed:
        print("ALLOWED (marked `# %s` at the site, NOT blocking) — %d read(s):"
              % (ALLOW_MARKER, len(allowed)))
        for a in allowed:
            print("  ~ %s" % a)
    if findings:
        print("REFUSED — %d read(s) of a field measured untrustworthy:" % len(findings))
        for f in findings:
            print("  ! %s" % f)
        print()
        print("`legal_status` is derived by an over-matching regex over chunk text "
              "and is wrong on")
        print("the two largest documents it marks revoked. Read the per-document "
              "`status` in")
        print("kb/topics/<topic>.yaml instead — sourced, gated, and decided by a "
              "person.")
        return 1
    print("clean — 0 statically resolvable reads (see module docstring for the "
          "boundary), %d write site(s)." % writes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
