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

class _ConsumerReadCollector(ast.NodeVisitor):
    """Collect string literals used to read from the producer payload."""

    def __init__(self) -> None:
        self.keys: set[str] = set()
        self._in_target = False

    def _target(self, node: ast.AST) -> None:
        old = self._in_target
        self._in_target = True
        self.visit(node)
        self._in_target = old

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            self._target(target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self._target(node.target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.target is not None:
            self._target(node.target)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and not self._in_target:
            self.keys.add(node.slice.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.keys.add(first.value)
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

def _find_function(module: ast.Module, name: str):
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _ast_keys(path: Path, function_name: str, collector_cls, side: str) -> set[str] | CannotVerify:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CannotVerify("", f"{side} file missing: {path}")
    except SyntaxError as exc:
        return CannotVerify("", f"{side} file unparseable: {path} ({exc.msg})")
    func = _find_function(tree, function_name)
    if func is None:
        return CannotVerify("", f"{side} function {function_name!r} not found in {path}")
    collector = collector_cls()
    collector.visit(func)
    return collector.keys

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


def _check_contract(contract: dict, repo_root: Path) -> tuple[list[Violation], list[Unchecked], list[CannotVerify], list[KnownGap], bool]:
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
        if not _resolve_read(read, emits, nested):
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
                violations.append(Violation(cid, "C2", literal, str(producer_path), str(consumer_path), f'consumer enum literal "{literal}" at {path!r} is not in producer domain {domain}'))

    # Unchecked reasons must always be printed.
    if producer_function is None:
        unchecked.append(Unchecked(cid, producer.get("unchecked_reason") or "producer function is null and no unchecked_reason given"))
    elif producer_kind != "python":
        unchecked.append(Unchecked(cid, f"producer kind={producer_kind!r} is not AST-anchored in v1"))

    if consumer_function is None:
        unchecked.append(Unchecked(cid, consumer.get("unchecked_reason") or "consumer function is null and no unchecked_reason given"))
    elif consumer_kind != "python":
        unchecked.append(Unchecked(cid, f"consumer kind={consumer_kind!r} is not AST-anchored in v1"))

    if producer_unchecked or consumer_unchecked:
        return (*_apply_gaps(contract, violations), unchecked, cannot_verify, anchored)

    # C3 — consumer anchor: code reads must be present in registry reads.
    consumer_ast_keys = _ast_keys(consumer_path, consumer_function, _ConsumerReadCollector, "consumer")
    if isinstance(consumer_ast_keys, CannotVerify):
        cannot_verify.append(CannotVerify(cid, consumer_ast_keys.reason))
    else:
        declared_keys = _declared_producer_keys(producer)
        registry_reads = _expand_reads(consumer.get("reads", []))
        for key in consumer_ast_keys:
            if key in declared_keys and key not in registry_reads:
                violations.append(Violation(cid, "C3", key, str(producer_path), str(consumer_path), f'consumer code reads "{key}" but registry reads omit it'))

    # C4 — producer anchor: registry emits must be present in code.
    producer_ast_keys = _ast_keys(producer_path, producer_function, _ProducerEmitCollector, "producer")
    if isinstance(producer_ast_keys, CannotVerify):
        cannot_verify.append(CannotVerify(cid, producer_ast_keys.reason))
    else:
        for key in producer.get("emits", []):
            if key not in producer_ast_keys:
                violations.append(Violation(cid, "C4", key, str(producer_path), str(consumer_path), f'registry emits "{key}" but producer code never writes it'))

    # ANCHORED means both sides were AST-parsed and actually compared against
    # their source. It is the only honest thing to call "checked": the previous
    # summary counted contracts that had produced a VIOLATION, so a perfectly
    # clean registry reported "0 checked" — a number indistinguishable from
    # "the lint did nothing", on the one surface whose job is proving it looked.
    anchored = not cannot_verify
    return (*_apply_gaps(contract, violations), unchecked, cannot_verify, anchored)

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

    proc = _git(["show", f"{base_ref}:./{rel}"])
    if isinstance(proc, tuple):
        return [], [CannotVerify("<registry>", f"cannot read {base_ref}: {type(proc[1]).__name__}")]
    if proc.returncode != 0:
        stderr = (proc.stderr or "")
        if "does not exist" in stderr or "exists on disk, but not in" in stderr:
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

    now, was = _gap_count(registry), _gap_count(base)
    if now > was:
        return [Violation(
            "<registry>", "C5", "known_gaps", str(registry_path), str(registry_path),
            f"known_gaps grew {was} -> {now} against {base_ref}; this list may only shrink. "
            "Fix the contract, or if the gap is genuinely new and unavoidable, say so in the PR "
            "body and remove an older one in the same diff.")], []
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
    for contract in registry.get("contracts", []):
        total += 1
        v, g, u, c, was_anchored = _check_contract(contract, repo_root)
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
        expect("guilt enum: names bad literal", any("normal" == x.key for x in by_check(for_cid(v, "enum_guilt"), "C2")))
        expect("guilt drift: one C3 violation", len(by_check(for_cid(v, "drift_guilt"), "C3")) == 1)
        expect("guilt drift: names omitted key", any("status" == x.key for x in by_check(for_cid(v, "drift_guilt"), "C3")))
        expect("guilt phantom: one C4 violation", len(by_check(for_cid(v, "phantom_guilt"), "C4")) == 1)
        expect("guilt phantom: names phantom key", any("entries" == x.key for x in by_check(for_cid(v, "phantom_guilt"), "C4")))
        expect("innocence matched: zero violations", len(for_cid(v, "matched_innocent")) == 0)
        expect("innocence unchecked: zero violations", len(for_cid(v, "unchecked_innocent")) == 0)
        expect("innocence unchecked: one unchecked line", len([x for x in u if x.cid == "unchecked_innocent"]) == 1)
        expect("innocence unchecked: line is printed", any(x.cid == "unchecked_innocent" and "external emitter" in x.reason for x in u))
        expect("no cannot-verify", not c)
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

        rp = gap_registry([{"check": "C2", "key": "normal", "reason": "measured, tracked", "ledger": "issue #5319"}])
        v2, _u2, _c2, g2, _a2, _t2 = _lint_registry(rp, root)
        expect("gap: a declared gap downgrades the violation", not v2 and len(g2) == 1)
        expect("gap: the reason and ledger are printed", "measured, tracked" in g2[0].line() and "#5319" in g2[0].line())

        rp = gap_registry([{"check": "C2", "key": "normal", "reason": "", "ledger": "issue #5319"}])
        v3, *_ = _lint_registry(rp, root)
        expect("gap: an empty reason is itself a violation", any(x.check == "C0" for x in v3))

        rp = gap_registry([{"check": "C1", "key": "normal", "reason": "wrong check", "ledger": "issue #5319"}])
        v4, *_ = _lint_registry(rp, root)
        expect("gap: matching is on (check, key), not key alone", any(x.check == "C2" for x in v4))

        rp = gap_registry([
            {"check": "C2", "key": "normal", "reason": "real", "ledger": "issue #5319"},
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
