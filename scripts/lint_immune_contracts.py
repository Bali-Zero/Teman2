#!/usr/bin/env python3
"""lint_immune_contracts.py — CI lint over infra/immune-contracts/contracts.json.

The immune-contracts registry pairs EMITTERS with CONSUMERS. This script exists
because of W120: the producer emitted ``"class"`` while the consumer read
``"classification"`` via ``e.get(...)``. The mismatch passed all existing tests,
the filter stayed empty, and 262 overdue rows read as silence.

The lint anchors both sides to source where possible: it AST-parses declared
Python producer/consumer functions and checks them against the registry. A
registry whose two halves only agree with each other is a fixture, not a contract.

Exit codes:
    0  clean
    1  violations found
    2  usage error or registry unreadable
    3  CANNOT-VERIFY — a declared source file is missing or unparseable
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


@dataclass(frozen=True)
class Violation:
    cid: str
    check: str
    key: str
    producer: str
    consumer: str
    msg: str

    def line(self) -> str:
        return f"[{self.cid}] {self.check}: {self.msg} (producer: {self.producer}, consumer: {self.consumer})"


@dataclass(frozen=True)
class Unchecked:
    cid: str
    reason: str

    def line(self) -> str:
        return f"[{self.cid}] UNCHECKED: {self.reason}"


@dataclass(frozen=True)
class KnownGap:
    """A violation the registry DECLARES, with a reason, instead of hiding.

    The alternative to this is worse in both directions: a lint that goes red on
    a gap nobody can close today gets disarmed within a week, and a lint whose
    author quietly deletes the offending declaration is a lint that lies. A gap
    is therefore allowed to exist, must carry a reason and a ledger pointer, is
    PRINTED on every run, and is counted on its own line — never folded into
    "clean".

    The list may only SHRINK against origin/main (`--no-regrowth`), the same
    monotone discipline as infra/tg-gateway/grandfathered.json, so it cannot
    become a dumping ground.
    """
    cid: str
    check: str
    key: str
    reason: str
    ledger: str

    def line(self) -> str:
        return f"[{self.cid}] KNOWN-GAP {self.check} {self.key!r}: {self.reason} [ledger: {self.ledger}]"


@dataclass(frozen=True)
class CannotVerify:
    cid: str
    reason: str

    def line(self) -> str:
        return f"[{self.cid}] CANNOT-VERIFY: {self.reason}"

# AST collectors

class _Taint:
    """Which names in a function body hold (part of) the producer payload.

    THE POINT OF THIS CLASS, and the defect it exists to close: the first
    version of C3 collected every string literal used as a `.get()`/subscript
    anywhere in the consumer function and then kept only those that were ALREADY
    declared producer keys. That rule cannot see W120 — the actual scar this
    whole registry is built around — because `classification` is precisely a key
    the producer does NOT declare, so it was discarded as ordinary code and the
    lint exited 0 on the exact shape it was written to catch. A cross-family
    reviewer reproduced it against the submitted code: C1=[], C3=[], C4=[],
    exit 0.

    The cure is provenance, not a wider net: a read counts when it comes off a
    value that flows from the payload. `os.environ.get("HOME")` stays invisible
    because `os.environ` is not tainted; `e.get("classification")` where `e`
    came out of `data["entries"]` is a contract read whatever the registry says
    about it.

    Deliberately a small fixed-point, not real dataflow: three passes over the
    body, propagating through assignment, for-targets, comprehensions, with-items
    and tuple unpacking. It does not follow calls into helpers, and says so —
    an honest limit beats a silent one.
    """

    _READ_WRAPPERS = {"lower", "upper", "strip", "casefold", "str"}

    def __init__(self, roots: set[str]) -> None:
        self.tainted: set[str] = set(roots)

    def is_tainted_expr(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.tainted
        if isinstance(node, ast.Subscript):
            return self.is_tainted_expr(node.value)
        if isinstance(node, ast.Attribute):
            # `.items()` / `.values()` keep provenance; an arbitrary attribute
            # does not (`payload.foo` is not a payload READ, it is an object).
            return node.attr in {"items", "values", "get"} and self.is_tainted_expr(node.value)
        if isinstance(node, ast.Call):
            return self.is_tainted_expr(node.func)
        if isinstance(node, ast.BoolOp):
            return any(self.is_tainted_expr(v) for v in node.values)
        if isinstance(node, ast.IfExp):
            return self.is_tainted_expr(node.body) or self.is_tainted_expr(node.orelse)
        if isinstance(node, (ast.Starred,)):
            return self.is_tainted_expr(node.value)
        return False

    def _bind(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.tainted.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._bind(elt)
        elif isinstance(target, ast.Starred):
            self._bind(target.value)

    def propagate(self, func: ast.AST) -> None:
        for _ in range(3):  # fixed point; three passes settle every shape here
            before = len(self.tainted)
            for node in ast.walk(func):
                if isinstance(node, ast.Assign) and self.is_tainted_expr(node.value):
                    for t in node.targets:
                        self._bind(t)
                elif isinstance(node, (ast.For, ast.AsyncFor)) and self.is_tainted_expr(node.iter):
                    self._bind(node.target)
                elif isinstance(node, ast.comprehension) and self.is_tainted_expr(node.iter):
                    self._bind(node.target)
                elif isinstance(node, ast.withitem) and self.is_tainted_expr(node.context_expr):
                    if node.optional_vars is not None:
                        self._bind(node.optional_vars)
                elif isinstance(node, ast.NamedExpr) and self.is_tainted_expr(node.value):
                    self._bind(node.target)
            if len(self.tainted) == before:
                break

    def read_key(self, node: ast.AST) -> Optional[str]:
        """If `node` reads a literal key off a tainted value, return that key."""
        # unwrap str()/.lower()/.strip() chains so a normalised read still counts
        while True:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in self._READ_WRAPPERS and not node.args:
                node = node.func.value
                continue
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "str" and len(node.args) == 1:
                node = node.args[0]
                continue
            break
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str) and self.is_tainted_expr(node.value):
            return node.slice.value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) \
                and self.is_tainted_expr(node.func.value):
            return node.args[0].value
        return None


class _ConsumerReadCollector(ast.NodeVisitor):
    """Keys read OFF THE PAYLOAD, and the literals the source compares them to.

    `keys` feeds C3 (every payload read must be declared). `compares` feeds C2b
    (every literal the SOURCE compares a key against must be in the producer's
    declared domain) — without which C2 compares two registry lists to each
    other and a consumer that starts comparing "live" instead of "LIVE" sails
    through while every seat is misreported.
    """

    def __init__(self, taint: "_Taint") -> None:
        self.taint = taint
        self.keys: set[str] = set()
        self.compares: dict[str, set[str]] = {}
        self._store_depth = 0

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # A write into a tainted dict is not a READ of the contract.
        for t in node.targets:
            self._store_depth += 1
            self.visit(t)
            self._store_depth -= 1
        self.visit(node.value)

    def _record(self, node: ast.AST) -> None:
        if self._store_depth:
            return
        key = self.taint.read_key(node)
        if key is not None:
            self.keys.add(key)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        self._record(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self._record(node)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: N802
        def literals(n: ast.AST) -> list[str]:
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                return [n.value]
            if isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                return [e.value for e in n.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            return []

        sides = [node.left, *node.comparators]
        for i, side in enumerate(sides):
            key = self.taint.read_key(side)
            if key is None:
                continue
            for j, other in enumerate(sides):
                if i == j:
                    continue
                for lit in literals(other):
                    self.compares.setdefault(key, set()).add(lit)
        self.generic_visit(node)


class _ProducerEmitCollector(ast.NodeVisitor):
    """Collect string literals the producer writes into its output dict."""

    def __init__(self) -> None:
        self.keys: set[str] = set()

    def visit_Dict(self, node: ast.Dict) -> None:  # noqa: N802
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self.keys.add(key.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Attribute) and node.func.attr == "setdefault" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.keys.add(first.value)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
                self.keys.add(target.slice.value)
        self.generic_visit(node)

# AST helpers

# ---------------------------------------------------------------------------
# DECLARED LIMITS of the AST layer (v1). Each was raised by a cross-family
# reviewer, is REAL, and is recorded here rather than fixed, because each needs
# a design decision this PR is not the place for. A limit written down is debt;
# an undocumented one is a lie about coverage.
#
#  * `_find_function` takes the FIRST definition with that name. Two methods
#    sharing a name, a definition under `if TYPE_CHECKING`, or a decorator that
#    replaces the runtime function will anchor the contract to the wrong body.
#    Cure would be a qualified name (`Class.method`) in the registry.
#  * Dynamic keys are invisible: `.get(key_variable)`, an f-string, a key built
#    by concatenation, or a producer that returns `dict(entries=rows)` or a dict
#    comprehension. Consumer-side this MISSES (false green); producer-side it
#    would false-flag, which `caller_supplied` exists to absorb.
#  * A read inside a helper the declared consumer CALLS is not followed. The
#    producer side follows one level (plus declared `emit_helpers`); the
#    consumer side follows none.
#  * `writer_function` / `on_disk_path` in the registry are documentation only:
#    nothing checks that the in-memory dict this lint verifies is the object
#    that actually reaches disk.
# ---------------------------------------------------------------------------


def _find_function(module: ast.Module, name: str):
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _parse(path: Path, side: str):
    """AST or CannotVerify. Every read failure is CANNOT-VERIFY, never exit 2.

    UnicodeDecodeError / PermissionError used to escape to main()'s generic
    handler and come back as 2 ("registry unreadable") — a different, wrong
    answer about a different thing (found by the cross-family gate).
    """
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CannotVerify("", f"{side} file missing: {path}")
    except SyntaxError as exc:
        return CannotVerify("", f"{side} file unparseable: {path} ({exc.msg})")
    except (UnicodeDecodeError, OSError) as exc:
        return CannotVerify("", f"{side} file unreadable: {path} ({type(exc).__name__})")


def _consumer_reads(path: Path, function_name: str, payload_param: Optional[str]):
    """(keys, compares) read OFF THE PAYLOAD, or CannotVerify."""
    tree = _parse(path, "consumer")
    if isinstance(tree, CannotVerify):
        return tree
    func = _find_function(tree, function_name)
    if func is None:
        return CannotVerify("", f"consumer function {function_name!r} not found in {path}")
    args = [a.arg for a in list(func.args.posonlyargs) + list(func.args.args)]
    if payload_param:
        roots = {payload_param}
    else:
        roots = set(args[:1])
        # Most real consumers here take NO argument: they shell out to the
        # producer and parse its stdout themselves. The payload is then whatever
        # came out of the json parse, and that is a perfectly good provenance
        # root — insisting on a parameter would have declared three of this
        # repo's five live consumers unanchorable.
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            call = node.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                    and call.func.attr in {"loads", "load"} \
                    and isinstance(call.func.value, ast.Name) and call.func.value.id == "json":
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        roots.add(t.id)
        if not roots:
            return CannotVerify(
                "",
                f"consumer {function_name!r} has no payload parameter and no json parse to "
                "taint from — declare payload_param in the registry, or mark it unchecked")
    taint = _Taint(roots)
    taint.propagate(func)
    collector = _ConsumerReadCollector(taint)
    collector.visit(func)
    return collector.keys, collector.compares


def _producer_emits(path: Path, function_name: str, helpers: Optional[list] = None):
    """Keys the producer writes, following ONE level of module-level helpers.

    The one level matters: `build_json` builds its entry dicts in `_entry_dict`
    and its counts in `compute_counts`, so a function-local scan sees the top
    level only and calls every nested key "never written" (or, worse, misses a
    rename inside the helper). One level is a declared limit, not a silent one —
    a producer whose payload is assembled two calls deep should declare THAT
    function in the registry.
    """
    tree = _parse(path, "producer")
    if isinstance(tree, CannotVerify):
        return tree
    func = _find_function(tree, function_name)
    if func is None:
        return CannotVerify("", f"producer function {function_name!r} not found in {path}")

    collector = _ProducerEmitCollector()
    collector.visit(func)
    keys = set(collector.keys)

    called = {
        n.func.id for n in ast.walk(func)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    # Explicitly declared helpers, because a real producer hands its builder to
    # an executor rather than calling it: `pool.submit(probe_seat, ...)` names
    # `probe_seat` as an ARGUMENT, so no Call(func=Name) ever mentions it.
    # Following every bare Name would be a wider net in the FALSE-GREEN
    # direction — an unrelated function could satisfy a claimed key by accident
    # — so the registry names them and the lint follows only those.
    called |= set(helpers or [])
    for name in called:
        helper = _find_function(tree, name)
        if helper is None or helper is func:
            continue
        sub = _ProducerEmitCollector()
        sub.visit(helper)
        keys |= sub.keys
    return keys

# Registry resolution helpers

def _declared_producer_keys(producer: dict) -> set[str]:
    """All key-like strings the registry claims the producer can emit."""
    keys: set[str] = set(producer.get("emits", []))
    for path, subkeys in producer.get("nested", {}).items():
        keys.add(path)
        keys.add(path.replace("[]", ""))
        keys.update(subkeys)
    return keys


def _expand_reads(reads: list[str]) -> set[str]:
    """Expand registry ``reads`` paths into the set of key segments they cover."""
    expanded: set[str] = set()
    for read in reads:
        expanded.add(read)
        expanded.update(read.replace("[]", "").split("."))
    return expanded


def _path_is_wellformed(read: str) -> bool:
    """`counts.` and `counts..x` used to RESOLVE. A declaration that is not even
    a path should be rejected, not interpreted (cross-family gate)."""
    if not read or read != read.strip():
        return False
    return all(seg.strip() for seg in read.replace("[]", "").split("."))


def _resolve_read(read: str, emits: list[str], nested: dict[str, list[str]]) -> bool:
    """Return True if ``read`` resolves against the producer schema."""
    emits_set = set(emits)
    if read in emits_set:
        return True
    head, _, tail = read.partition(".")
    head_base = head.replace("[]", "")
    if head_base not in emits_set and head not in nested:
        return False
    subkeys = nested.get(head, nested.get(head_base, []))
    for segment in (tail.split(".") if tail else []):
        if segment not in subkeys:
            return False
    return True

# Per-contract checks

def _declared_gaps(contract: dict) -> tuple[list[KnownGap], list[Violation]]:
    """Parse `known_gaps`. A gap without a reason or a ledger pointer is itself a
    violation — otherwise "declare it" degrades into "silence it"."""
    cid = contract.get("id", "<no-id>")
    gaps: list[KnownGap] = []
    bad: list[Violation] = []
    for g in contract.get("known_gaps", []) or []:
        check = str(g.get("check", "")).strip()
        key = str(g.get("key", "")).strip()
        reason = str(g.get("reason", "")).strip()
        ledger = str(g.get("ledger", "")).strip()
        if not (check and key and reason and ledger):
            bad.append(Violation(cid, "C0", key or "<no-key>", "", "",
                                 f"known_gaps entry is incomplete (needs check, key, reason, ledger): {g!r}"))
            continue
        gaps.append(KnownGap(cid, check, key, reason, ledger))
    return gaps, bad


# Return order is (violations, known_gaps, unchecked, cannot_verify, anchored)
# — gaps SECOND, because `_apply_gaps` returns the (violations, gaps) pair and
# it is splatted here. The hint said otherwise for one commit; a type hint that
# disagrees with the return is the W95 shape and passes every checker, because
# the tuple is positional and nobody validates the annotation at runtime.
def _check_contract(
    contract: dict, repo_root: Path, sibling_reads: Optional[set[str]] = None
) -> tuple[list[Violation], list[KnownGap], list[Unchecked], list[CannotVerify], bool]:
    violations: list[Violation] = []
    unchecked: list[Unchecked] = []
    cannot_verify: list[CannotVerify] = []
    anchored = False

    cid = contract.get("id", "<no-id>")
    producer = contract.get("producer", {})
    consumer = contract.get("consumer", {})

    producer_path = repo_root / producer.get("path", "")
    consumer_path = repo_root / consumer.get("path", "")
    producer_kind = producer.get("kind", "python")
    consumer_kind = consumer.get("kind", "python")
    producer_function = producer.get("function")
    consumer_function = consumer.get("function")

    producer_unchecked = producer_function is None or producer_kind != "python"
    consumer_unchecked = consumer_function is None or consumer_kind != "python"

    # C1 — registry consistency: every consumer read must resolve.
    emits = producer.get("emits", [])
    nested = producer.get("nested", {})
    for read in consumer.get("reads", []):
        if not _path_is_wellformed(read):
            violations.append(Violation(
                cid, "C1", read, str(producer_path), str(consumer_path),
                f'consumer read path "{read}" is malformed (empty segment) — a declaration that '
                "is not a path cannot be checked against one"))
        elif not _resolve_read(read, emits, nested):
            violations.append(Violation(cid, "C1", read, str(producer_path), str(consumer_path), f'consumer reads "{read}" but producer does not emit it'))

    # C2 — enum domain: consumer literals must live inside producer domains.
    producer_enums = producer.get("enums", {})
    for path, literals in consumer.get("enum_literals", {}).items():
        domain = producer_enums.get(path)
        if domain is None:
            unchecked.append(Unchecked(cid, f"enum_literals[{path!r}] has no matching producer enums domain"))
            continue
        for literal in literals:
            if literal not in domain:
                # The key carries its PATH. With a bare literal, one gap
                # declared for "BAD" silenced "BAD" at orders[].status AND at
                # jobs[].status — two independent findings excused by one
                # sentence (cross-family gate).
                violations.append(Violation(
                    cid, "C2", f"{path}={literal}", str(producer_path), str(consumer_path),
                    f'consumer enum literal "{literal}" at {path!r} is not in producer domain {domain}'))

    # Unchecked reasons must always be printed.
    if producer_function is None:
        unchecked.append(Unchecked(cid, producer.get("unchecked_reason") or "producer function is null and no unchecked_reason given"))
    elif producer_kind != "python":
        unchecked.append(Unchecked(cid, f"producer kind={producer_kind!r} is not AST-anchored in v1"))

    if consumer_function is None:
        unchecked.append(Unchecked(cid, consumer.get("unchecked_reason") or "consumer function is null and no unchecked_reason given"))
    elif consumer_kind != "python":
        unchecked.append(Unchecked(cid, f"consumer kind={consumer_kind!r} is not AST-anchored in v1"))

    # ONE uncheckable side must not disable the OTHER side's anchor. The early
    # return here used to skip BOTH C3 and C4 as soon as either half was
    # non-python, so a perfectly parseable Python consumer went unchecked
    # because its producer happened to be a shell script (cross-family gate).
    # Each anchor now runs on its own merits.

    # C3 — consumer anchor: every key the code reads OFF THE PAYLOAD must be
    # declared. Not "every declared key it reads" — that was the version that
    # could not see W120 at all, because `classification` is exactly a key the
    # producer does NOT declare and was therefore discarded as ordinary code.
    consumer_reads_ok = False
    if not consumer_unchecked:
        got = _consumer_reads(consumer_path, consumer_function, consumer.get("payload_param"))
        if isinstance(got, CannotVerify):
            cannot_verify.append(CannotVerify(cid, got.reason))
        else:
            consumer_ast_keys, source_compares = got
            consumer_reads_ok = True
            # UNION across every contract declaring the same consumer function.
            # `organism_digest.stale_heartbeats` globs one directory that TWO
            # producers write into, so its payload reads are split across two
            # contracts by construction; asking each contract to account for all
            # of them would redden both for telling the truth.
            registry_reads = _expand_reads(consumer.get("reads", [])) | (sibling_reads or set())
            for key in sorted(consumer_ast_keys):
                if key not in registry_reads:
                    violations.append(Violation(
                        cid, "C3", key, str(producer_path), str(consumer_path),
                        f'consumer code reads "{key}" off the payload but the registry does not '
                        "declare it (undeclared read — this is the W120 shape)"))

            # C2b — the same question C2 asks, but of the SOURCE. C2 alone
            # compares two registry lists to each other, so a consumer that
            # quietly starts comparing "live" instead of "LIVE" stays green
            # while every seat is misreported.
            producer_enums = producer.get("enums", {})
            for key, literals in sorted(source_compares.items()):
                domain = _domain_for_key(producer_enums, key)
                if domain is None:
                    continue  # no declared domain: C2's own UNCHECKED path covers it
                for literal in sorted(literals):
                    if literal not in domain:
                        violations.append(Violation(
                            cid, "C2b", f"{key}={literal}", str(producer_path), str(consumer_path),
                            f'consumer CODE compares "{key}" against "{literal}", which is not in '
                            f"the producer's declared domain {domain}"))

    # C4 — producer anchor: every key the registry claims, including nested
    # ones, must actually be written. `nested` was not checked at all, so a
    # rename inside an entry dict was invisible.
    producer_emits_ok = False
    if not producer_unchecked:
        producer_ast_keys = _producer_emits(producer_path, producer_function, producer.get("emit_helpers"))
        if isinstance(producer_ast_keys, CannotVerify):
            cannot_verify.append(CannotVerify(cid, producer_ast_keys.reason))
        else:
            producer_emits_ok = True
            claimed = list(producer.get("emits", []))
            for group in (producer.get("nested") or {}).values():
                claimed.extend(group)
            # A producer that spreads a caller's dict (`{**entry, ...}`) really
            # does emit keys its own function never names. Those are declared
            # once, by key, and become UNCHECKED — visible, with a reason — not
            # a violation the author cannot fix and not a silence either.
            caller_supplied = set(producer.get("caller_supplied") or [])
            # `caller_supplied_variants` is the grounded form the registry
            # already uses: each entry cites a real call site and the keys IT
            # supplies. Reading it here means the registry states the fact once,
            # with its provenance, instead of twice.
            for variant in producer.get("caller_supplied_variants") or []:
                caller_supplied.update(variant.get("keys") or [])
            for key in sorted(caller_supplied):
                unchecked.append(Unchecked(
                    cid, f'producer key "{key}" is caller-supplied via a dict spread; '
                         "not anchorable to the producer function itself"))
            for key in sorted(set(claimed) - caller_supplied):
                if key not in producer_ast_keys:
                    violations.append(Violation(
                        cid, "C4", key, str(producer_path), str(consumer_path),
                        f'registry claims the producer emits "{key}" but its code never writes it'))

    # ANCHORED means both sides were AST-parsed and actually compared against
    # their source. It is the only honest thing to call "checked": the previous
    # summary counted contracts that had produced a VIOLATION, so a perfectly
    # clean registry reported "0 checked" — a number indistinguishable from
    # "the lint did nothing", on the one surface whose job is proving it looked.
    anchored = consumer_reads_ok and producer_emits_ok and not cannot_verify
    return (*_apply_gaps(contract, violations), unchecked, cannot_verify, anchored)

def _domain_for_key(enums: dict, key: str) -> Optional[list]:
    """The declared domain for a bare key, whatever path shape it was declared under.

    The registry writes paths (`entries[].class`); the source only ever gives us
    the last segment (`class`). Matching on the last segment keeps the two
    languages talking; an ambiguous key declared under two different paths with
    DIFFERENT domains returns None rather than guessing, and falls through to
    C2's UNCHECKED path.
    """
    hits = [v for k, v in (enums or {}).items() if k.split(".")[-1] == key or k == key]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1 and all(h == hits[0] for h in hits):
        return hits[0]
    return None


def _apply_gaps(contract: dict, violations: list[Violation]) -> tuple[list[Violation], list[KnownGap]]:
    """Split violations into (still-violations, declared-gaps).

    A declared gap matches on (check, key). Anything undeclared stays a
    violation; a declaration that matches nothing is itself reported, because a
    stale gap is how an allowlist outlives the thing it excused.
    """
    gaps, malformed = _declared_gaps(contract)
    remaining: list[Violation] = list(malformed)
    matched: list[KnownGap] = []
    used: set[tuple[str, str]] = set()
    for v in violations:
        hit = next((g for g in gaps if g.check == v.check and g.key == v.key), None)
        if hit is None:
            remaining.append(v)
        else:
            matched.append(hit)
            used.add((hit.check, hit.key))
    for g in gaps:
        if (g.check, g.key) not in used:
            remaining.append(Violation(
                g.cid, "C0", g.key, "", "",
                f"known_gaps declares {g.check} {g.key!r} but nothing violates it any more — "
                "delete the entry (this list may only shrink)"))
    return remaining, matched


def _gap_count(registry: dict) -> int:
    return sum(len(c.get("known_gaps") or []) for c in registry.get("contracts", []))


def _gap_set(registry: dict) -> set[tuple[str, str, str]]:
    """Identity of every declared gap: (contract, check, key).

    A COUNT is defeatable by trade: delete one gap in contract A, add a
    different one in contract B, totals unchanged, new debt approved (measured
    by the cross-family gate). A set makes each gap a named thing that has to be
    named again to survive.
    """
    out: set[tuple[str, str, str]] = set()
    for c in registry.get("contracts", []):
        cid = c.get("id", "<no-id>")
        for g in c.get("known_gaps") or []:
            out.add((cid, str(g.get("check", "")), str(g.get("key", ""))))
    return out


def _no_regrowth(registry_path: Path, registry: dict, base_ref: str) -> tuple[list[Violation], list[CannotVerify]]:
    """`known_gaps` may only SHRINK against `base_ref`.

    Without this the declare-instead-of-hide escape becomes an allowlist: every
    inconvenient finding gets a paragraph and the lint never goes red again.
    Monotone-shrink is the same discipline infra/tg-gateway/grandfathered.json
    already runs on, and it is the only thing that makes a declared gap a debt
    rather than a permission.

    A base that cannot be read is CANNOT-VERIFY, never a pass: on a shallow CI
    clone with no origin/main this must say so rather than quietly approve
    growth (W84).
    """
    rel = registry_path.name
    cwd = str(registry_path.parent)

    def _git(argv):
        try:
            return subprocess.run(["git", "-C", cwd, *argv], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError) as exc:
            return None, exc

    # Two different failures wearing one exit code, and they need opposite
    # answers: a ref that does not resolve is CANNOT-VERIFY, while a ref that
    # resolves and simply has no such FILE is the bootstrap window — the registry
    # is introduced by this very PR, so its baseline is legitimately zero. Folding
    # them together would either redden the introducing PR forever or approve
    # growth on a shallow clone.
    r = _git(["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"])
    if isinstance(r, tuple) or r.returncode != 0 or not r.stdout.strip():
        detail = "git unavailable" if isinstance(r, tuple) else (r.stderr or "").strip() or "ref does not resolve"
        return [], [CannotVerify("<registry>", f"cannot resolve {base_ref}: {detail}")]
    # Pin the SHA and use it from here on. Resolving a NAME twice invites the ref
    # to move between the two calls (a concurrent fetch), and the verdict would
    # then be about a commit nobody verified (cross-family gate).
    base_sha = r.stdout.strip()

    # Existence by exit code, not by matching an English error string: git
    # localises its messages, and a translated "does not exist" would turn the
    # bootstrap window into a red required check (cross-family gate).
    exists = _git(["cat-file", "-e", f"{base_sha}:./{rel}"])
    file_missing = isinstance(exists, tuple) or exists.returncode != 0

    proc = _git(["show", f"{base_sha}:./{rel}"])
    if isinstance(proc, tuple):
        return [], [CannotVerify("<registry>", f"cannot read {base_ref}: {type(proc[1]).__name__}")]
    if proc.returncode != 0:
        if file_missing:
            print(
                f"note: {rel} does not exist at {base_ref} — bootstrap window, "
                "baseline known_gaps = 0 (this is the PR that introduces the registry)"
            )
            base = {"contracts": []}
            now = _gap_count(registry)
            if now > 0:
                print(f"note: {now} known-gap(s) declared at introduction; this list may only shrink from here")
            return [], []
        reason = stderr.strip().splitlines()
        return [], [CannotVerify("<registry>", f"cannot read {base_ref}: {reason[-1] if reason else 'git failed'}")]
    try:
        base = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], [CannotVerify("<registry>", f"{base_ref} copy is not valid JSON: {exc}")]

    added = sorted(_gap_set(registry) - _gap_set(base))
    if added:
        return [Violation(
            "<registry>", "C5", "known_gaps", str(registry_path), str(registry_path),
            f"known_gaps gained {len(added)} entry/entries against {base_ref} — "
            f"{', '.join(f'{c}:{k}:{v}' for c, k, v in added)}. This list may only shrink; "
            "removing a different gap elsewhere does not pay for a new one.")], []
    return [], []


# Registry loading and top-level lint

def _load_registry(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _lint_registry(registry_path: Path, repo_root: Path) -> tuple[list[Violation], list[Unchecked], list[CannotVerify], list[KnownGap], int, int]:
    registry = _load_registry(registry_path)
    violations: list[Violation] = []
    unchecked: list[Unchecked] = []
    cannot_verify: list[CannotVerify] = []
    gaps: list[KnownGap] = []
    anchored = 0
    total = 0
    # Pre-index reads by (consumer path, function) so a reader serving two
    # producers is judged against everything its contracts declare, not against
    # one contract's slice of it.
    by_reader: dict[tuple, set[str]] = {}
    for contract in registry.get("contracts", []):
        cons = contract.get("consumer", {})
        key = (cons.get("path"), cons.get("function"))
        by_reader.setdefault(key, set()).update(_expand_reads(cons.get("reads", [])))

    if not registry.get("contracts"):
        # Replacing the registry with `{}` used to report 0/0 and exit 0, so the
        # gate could be disarmed by deleting its CONTENT rather than its code
        # (cross-family gate). A registry with nothing in it is a defect, not a
        # clean tree.
        violations.append(Violation(
            "<registry>", "C6", "contracts", str(registry_path), str(registry_path),
            "registry declares no contracts — an empty registry is a disarmed gate, not a clean one"))

    for contract in registry.get("contracts", []):
        total += 1
        cons = contract.get("consumer", {})
        siblings = by_reader.get((cons.get("path"), cons.get("function")), set())
        v, g, u, c, was_anchored = _check_contract(contract, repo_root, siblings)
        violations.extend(v)
        gaps.extend(g)
        unchecked.extend(u)
        cannot_verify.extend(c)
        anchored += 1 if was_anchored else 0
    return violations, unchecked, cannot_verify, gaps, anchored, total

# Reporting

def _report_text(violations, unchecked, cannot_verify, gaps=(), anchored=0, total=0) -> None:
    for item in list(violations) + list(cannot_verify) + list(gaps) + list(unchecked):
        print(item.line())
    print(
        f"{anchored}/{total} contracts anchored to source, "
        f"{len(unchecked)} unchecked, {len(gaps)} known-gap, "
        f"{len(cannot_verify)} cannot-verify, {len(violations)} violations"
    )


def _report_json(violations, unchecked, cannot_verify, gaps=(), anchored=0, total=0) -> None:
    print(json.dumps({
        "violations": [{"contract_id": v.cid, "check": v.check, "key": v.key, "producer_path": v.producer, "consumer_path": v.consumer, "message": v.msg} for v in violations],
        "unchecked": [{"contract_id": u.cid, "reason": u.reason} for u in unchecked],
        "cannot_verify": [{"contract_id": c.cid, "reason": c.reason} for c in cannot_verify],
        "known_gaps": [{"contract_id": g.cid, "check": g.check, "key": g.key, "reason": g.reason, "ledger": g.ledger} for g in gaps],
        "summary": {"anchored": anchored, "contracts": total, "unchecked": len(unchecked),
                    "known_gaps": len(gaps), "violations": len(violations),
                    "cannot_verify": len(cannot_verify)},
    }, indent=2))

# Self-test

def _contract(
    cid: str,
    *,
    emits: list[str],
    reads: list[str],
    nested: dict[str, list[str]] | None = None,
    enums: dict[str, list[str]] | None = None,
    enum_literals: dict[str, list[str]] | None = None,
    producer_func: str | None = "build_json",
    consumer_func: str | None = "consume",
    unchecked_reason: str | None = None,
) -> dict:
    producer: dict = {"path": "producer.py", "function": producer_func, "kind": "python", "emits": emits}
    if nested is not None:
        producer["nested"] = nested
    if enums is not None:
        producer["enums"] = enums
    if unchecked_reason is not None:
        producer["unchecked_reason"] = unchecked_reason
    consumer: dict = {"path": "consumer.py", "function": consumer_func, "kind": "python", "reads": reads}
    if enum_literals is not None:
        consumer["enum_literals"] = enum_literals
    return {"id": cid, "producer": producer, "consumer": consumer}


def _run_selftest() -> int:
    failures: list[str] = []

    def expect(name: str, cond: bool) -> None:
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    def by_check(violations: list[Violation], check: str) -> list[Violation]:
        return [v for v in violations if v.check == check]

    def for_cid(violations: list[Violation], cid: str) -> list[Violation]:
        return [v for v in violations if v.cid == cid]

    P_ITEMS = 'def build_json():\n    return {"items": [{"status": "NORMAL"}]}\n'
    C_ITEMS_OK = 'def consume(data):\n    for i in data.get("items", []):\n        if i.get("status") == "OK":\n            yield i\n'
    C_ITEMS_NORMAL = 'def consume(data):\n    for i in data.get("items", []):\n        if i.get("status") == "NORMAL":\n            yield i\n'

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "w120_producer.py").write_text('def build_json():\n    return {"counts": {"total": 1, "tech_debt_overdue": 1}, "entries": [{"class": "TECH-DEBT", "overdue": True, "artifact": "x", "age_days": 3}], "now": "2026-01-01T00:00:00Z"}\n')
        (root / "w120_consumer.py").write_text('def consume(data):\n    for e in data.get("entries", []):\n        if e.get("classification") == "TECH-DEBT":\n            yield e\n')
        (root / "enum_producer.py").write_text(P_ITEMS)
        (root / "enum_consumer.py").write_text('def consume(data):\n    for i in data.get("items", []):\n        if i.get("status") == "normal":\n            yield i\n')
        (root / "drift_producer.py").write_text(P_ITEMS)
        (root / "drift_consumer.py").write_text(C_ITEMS_OK)
        (root / "phantom_producer.py").write_text('def build_json():\n    return {"counts": {}}\n')
        (root / "phantom_consumer.py").write_text('def consume(data):\n    return data.get("counts")\n')
        (root / "matched_producer.py").write_text(P_ITEMS)
        (root / "matched_consumer.py").write_text(C_ITEMS_NORMAL)
        (root / "unchecked_producer.py").write_text('def build_json():\n    return {}\n')
        (root / "unchecked_consumer.py").write_text('def consume(data):\n    pass\n')

        registry = {
            "version": 1,
            "contracts": [
                _contract("w120_guilt", emits=["counts", "entries", "now"],
                          nested={"counts": ["total", "tech_debt_overdue"], "entries[]": ["class", "overdue", "artifact", "age_days"]},
                          enums={"entries[].class": ["TECH-DEBT"]},
                          reads=["counts", "counts.tech_debt_overdue", "entries", "entries[].classification"],
                          enum_literals={"entries[].class": ["TECH-DEBT"]}),
                _contract("enum_guilt", emits=["items"], nested={"items[]": ["status"]},
                          enums={"items[].status": ["NORMAL"]}, reads=["items", "items[].status"],
                          enum_literals={"items[].status": ["normal"]}),
                _contract("drift_guilt", emits=["items"], nested={"items[]": ["status"]}, reads=["items"]),
                _contract("phantom_guilt", emits=["counts", "entries"], reads=["counts"]),
                _contract("matched_innocent", emits=["items"], nested={"items[]": ["status"]},
                          enums={"items[].status": ["NORMAL"]}, reads=["items", "items[].status"],
                          enum_literals={"items[].status": ["NORMAL"]}),
                _contract("unchecked_innocent", emits=[], reads=[], producer_func=None,
                          unchecked_reason="external emitter, not AST-anchored"),
            ],
        }
        for contract in registry["contracts"]:
            prefix = contract["id"].split("_")[0]
            contract["producer"]["path"] = f"{prefix}_producer.py"
            contract["consumer"]["path"] = f"{prefix}_consumer.py"

        registry_path = root / "contracts.json"
        registry_path.write_text(json.dumps(registry))
        v, u, c, g, anchored, total = _lint_registry(registry_path, root)
        expect("guilt W120: one C1 violation", len(by_check(for_cid(v, "w120_guilt"), "C1")) == 1)
        expect("guilt W120: names drifted key", any("classification" in x.key for x in by_check(for_cid(v, "w120_guilt"), "C1")))
        expect("guilt enum: one C2 violation", len(by_check(for_cid(v, "enum_guilt"), "C2")) == 1)
        expect("guilt enum: names bad literal AND its path",
               any(x.key == "items[].status=normal" for x in by_check(for_cid(v, "enum_guilt"), "C2")))
        expect("guilt drift: one C3 violation", len(by_check(for_cid(v, "drift_guilt"), "C3")) == 1)
        expect("guilt drift: names omitted key", any("status" == x.key for x in by_check(for_cid(v, "drift_guilt"), "C3")))
        expect("guilt phantom: one C4 violation", len(by_check(for_cid(v, "phantom_guilt"), "C4")) == 1)
        expect("guilt phantom: names phantom key", any("entries" == x.key for x in by_check(for_cid(v, "phantom_guilt"), "C4")))
        expect("innocence matched: zero violations", len(for_cid(v, "matched_innocent")) == 0)
        expect("innocence unchecked: zero violations", len(for_cid(v, "unchecked_innocent")) == 0)
        expect("innocence unchecked: one unchecked line", len([x for x in u if x.cid == "unchecked_innocent"]) == 1)
        expect("innocence unchecked: line is printed", any(x.cid == "unchecked_innocent" and "external emitter" in x.reason for x in u))
        expect("no cannot-verify", not c)

        # THE case this whole registry exists for, and the one the first version
        # could not see. A cross-family reviewer reproduced it against the
        # submitted code and got C1=[], C3=[], C4=[], exit 0: `classification`
        # is precisely a key the producer does NOT declare, so the old C3 —
        # which only flagged keys that WERE declared — discarded it as ordinary
        # code. Provenance is what fixed it: the read comes off a value that
        # flows from the payload, so it is a contract read whatever the registry
        # says about it. If this case ever stops firing, the gate is decorative.
        (root / "w120real_producer.py").write_text('def build_json():\n    return {"entries": [{"class": "TECH-DEBT"}]}\n')
        (root / "w120real_consumer.py").write_text('def consume(data):\n    for e in data.get("entries", []):\n        if e.get("classification") == "TECH-DEBT":\n            yield e\n')
        real = _contract("w120real", emits=["entries"], nested={"entries[]": ["class"]},
                         enums={"entries[].class": ["TECH-DEBT"]}, reads=["entries"])
        real["producer"]["path"] = "w120real_producer.py"
        real["consumer"]["path"] = "w120real_consumer.py"
        rp_real = root / "w120real.json"
        rp_real.write_text(json.dumps({"version": 1, "contracts": [real]}))
        v_real, *_ = _lint_registry(rp_real, root)
        expect("guilt W120 AS IT ACTUALLY HAPPENED: an undeclared payload read is caught",
               any(x.check == "C3" and x.key == "classification" for x in v_real))

        # Its innocence twin: an ordinary string literal that never touches the
        # payload must stay invisible, or the cure is just a wider net.
        (root / "prose_producer.py").write_text('def build_json():\n    return {"entries": []}\n')
        (root / "prose_consumer.py").write_text(
            'import os\n'
            'def consume(data):\n'
            '    home = os.environ.get("HOME")\n'
            '    cfg = {"classification": "x"}\n'
            '    return data.get("entries"), home, cfg["classification"]\n')
        prose = _contract("prose", emits=["entries"], reads=["entries"])
        prose["producer"]["path"] = "prose_producer.py"
        prose["consumer"]["path"] = "prose_consumer.py"
        rp_prose = root / "prose.json"
        rp_prose.write_text(json.dumps({"version": 1, "contracts": [prose]}))
        v_prose, *_ = _lint_registry(rp_prose, root)
        expect("innocence: a literal that never touches the payload is not a contract read",
               not v_prose)
        # The counter that previously counted VIOLATIONS while calling itself
        # "checked": a clean registry summarised as "0 checked", indistinguishable
        # from "the lint did nothing", on the one surface whose job is proving it
        # looked. 5 of the 6 contracts here are AST-anchored; the 6th is the
        # declared-UNCHECKED one and must NOT be counted as anchored.
        expect("anchored counts SOURCE-ANCHORED contracts, not violations", (anchored, total) == (5, 6))

        # --- known_gaps: declare-instead-of-hide, and its own guards -----------
        (root / "gap_producer.py").write_text(P_ITEMS)
        (root / "gap_consumer.py").write_text('def consume(data):\n    for i in data.get("items", []):\n        if i.get("status") == "normal":\n            yield i\n')

        def gap_registry(gaps):
            c = _contract("gap_case", emits=["items"], nested={"items[]": ["status"]},
                          enums={"items[].status": ["NORMAL"]}, reads=["items", "items[].status"],
                          enum_literals={"items[].status": ["normal"]})
            c["producer"]["path"] = "gap_producer.py"
            c["consumer"]["path"] = "gap_consumer.py"
            if gaps is not None:
                c["known_gaps"] = gaps
            rp = root / "gap_contracts.json"
            rp.write_text(json.dumps({"version": 1, "contracts": [c]}))
            return rp

        rp = gap_registry([{"check": "C2", "key": "items[].status=normal", "reason": "measured, tracked", "ledger": "issue #5319"},
             {"check": "C2b", "key": "status=normal", "reason": "same finding, source-anchored", "ledger": "issue #5319"}])
        v2, _u2, _c2, g2, _a2, _t2 = _lint_registry(rp, root)
        # TWO gaps, because the same drift is now found twice: once by C2 (the
        # registry declares the literal) and once by C2b (the SOURCE compares
        # it). That is the point of C2b — one of them was previously invisible.
        expect("gap: declared gaps downgrade both the registry and the source finding",
               not v2 and len(g2) == 2 and {x.check for x in g2} == {"C2", "C2b"})
        expect("gap: the reason and ledger are printed",
               all("#5319" in x.line() for x in g2) and any("measured, tracked" in x.line() for x in g2))

        rp = gap_registry([{"check": "C2", "key": "items[].status=normal", "reason": "", "ledger": "issue #5319"}])
        v3, *_ = _lint_registry(rp, root)
        expect("gap: an empty reason is itself a violation", any(x.check == "C0" for x in v3))

        rp = gap_registry([{"check": "C1", "key": "items[].status=normal", "reason": "wrong check", "ledger": "issue #5319"}])
        v4, *_ = _lint_registry(rp, root)
        expect("gap: matching is on (check, key), not key alone", any(x.check == "C2" for x in v4))

        rp = gap_registry([
            {"check": "C2", "key": "items[].status=normal", "reason": "real", "ledger": "issue #5319"},
            {"check": "C2b", "key": "status=normal", "reason": "real", "ledger": "issue #5319"},
            {"check": "C2", "key": "nothing-violates-this", "reason": "stale", "ledger": "issue #5319"},
        ])
        v5, *_ = _lint_registry(rp, root)
        expect("gap: a STALE gap is a violation, so the list cannot outlive its excuse",
               any(x.check == "C0" and "nothing-violates-this" in x.key for x in v5))

    if failures:
        print(f"SELFTEST FAILED: {len(failures)} case(s) misbehaved")
        return 1
    print("SELFTEST OK")
    return 0

# CLI

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Lint immune-contracts registry.")
    parser.add_argument("--check", action="store_true", default=True, help="lint the real registry (default)")
    parser.add_argument("--registry", default="infra/immune-contracts/contracts.json", help="path to contracts.json")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent), help="repository root")
    parser.add_argument("--selftest", action="store_true", help="run synthetic guilt/innocence tests")
    parser.add_argument("--json", action="store_true", help="emit results as JSON")
    parser.add_argument(
        "--no-regrowth",
        metavar="BASE_REF",
        default=None,
        help=(
            "Also assert that known_gaps has not GROWN against BASE_REF (e.g. origin/main). "
            "Without this the declare-instead-of-hide escape becomes a permanent allowlist."
        ),
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    repo_root = Path(args.repo_root).resolve()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path

    try:
        violations, unchecked, cannot_verify, gaps, anchored, total = _lint_registry(registry_path, repo_root)
    except FileNotFoundError as exc:
        print(f"registry not found: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"registry is not valid JSON: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"cannot load registry: {exc}", file=sys.stderr)
        return 2

    if args.no_regrowth:
        try:
            reg = _load_registry(registry_path)
        except Exception as exc:  # already reported above if unreadable
            reg = {}
            cannot_verify.append(CannotVerify("<registry>", f"re-read failed: {exc}"))
        rv, rc = _no_regrowth(registry_path, reg, args.no_regrowth)
        violations.extend(rv)
        cannot_verify.extend(rc)

    if args.json:
        _report_json(violations, unchecked, cannot_verify, gaps, anchored, total)
    else:
        _report_text(violations, unchecked, cannot_verify, gaps, anchored, total)

    if cannot_verify:
        return 3
    if violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
