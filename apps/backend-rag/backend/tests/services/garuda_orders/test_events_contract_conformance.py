"""`products/garuda-voa/contracts/events.yaml` describes every journal event
this lane emits, and until this file NOTHING compared it to the code.

The contract suite next to the YAML holds twelve tests and every one of them
validates the file's INTERNAL consistency — refs resolve, error codes match the
catalogue, reason codes match the engine enum. None of them looks at an event
the code actually writes. On the other side, nothing under
`apps/backend-rag/backend` parses the file at all: every mention of
`events.yaml` there is prose in a docstring. A gate session measured what that
allows — flipping `customer_visible` from true to false on
`PaymentRefundedAfterLateCase` left the whole `garuda_orders` suite at its
baseline. Superscar #2 read on a document instead of a daemon: the contract
EXISTS, nothing ARMS it.

WHY STATIC ANALYSIS RATHER THAN DRIVING EVERY EVENT. Driving 21 events end to
end would need 21 fixtures and would still prove only what it drove. The
emission sites are the population that can drift, so they are what is read:
every `journal.append_event(...)` call in the backend, resolved from the AST.

THE UNDER-MATCH THIS FILE REFUSES TO HAVE (superscar #3). A scan that silently
skipped call sites whose kwargs are not literals would be a guard with a hole
exactly where the interesting writers live — `staff_transitions.py` passes
`spec.event_name` out of a table. So a non-literal call site is not skipped: it
must be named in `_DYNAMIC_EMITTERS` with a resolver, or this file fails and
names it.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
import yaml

_HERE = pathlib.Path(__file__).resolve()
_REPO_ROOT = next(p for p in _HERE.parents if (p / "products" / "garuda-voa").is_dir())
_CONTRACT = _REPO_ROOT / "products" / "garuda-voa" / "contracts" / "events.yaml"
_BACKEND = _REPO_ROOT / "apps" / "backend-rag" / "backend"

#: Call sites that pass a non-literal `event_name` or `transition_id`. Each is
#: resolved by importing the TABLE it reads, never by guessing: a table is data,
#: and reading it is exact where an AST heuristic would be plausible.
_DYNAMIC_EMITTERS = {
    "services/garuda_portal/staff_transitions.py": "_resolve_staff_transitions",
    "services/garuda_orders/repository.py": "_resolve_paired_assignments",
}

#: (event, attribute) pairs the contract deliberately leaves UNPINNED, with the
#: reason. Listed rather than skipped: dropping a `const` from the YAML weakens
#: the contract silently, and this set is what notices.
_UNPINNED = {
    # one event, three transitions (PR-03 from Received, PR-05 from In_review,
    # PR-08 from Submitted) — a single const could only be wrong twice.
    ("practice.blocked", "transition_id"),
    # same shape: PR-09 resumes to In_review, PR-10 to Submitted.
    ("practice.resumed", "transition_id"),
}

_ATTRS = ("event_name", "aggregate_type", "transition_id", "customer_visible")


def _contract_events() -> dict[str, dict]:
    doc = yaml.safe_load(_CONTRACT.read_text())
    out: dict[str, dict] = {}
    for name, entry in (doc.get("$defs") or {}).items():
        if not isinstance(entry, dict) or "x-event-name" not in entry:
            continue
        consts: dict[str, object] = {}
        for branch in entry.get("allOf", []):
            for key, spec in (branch.get("properties") or {}).items():
                if isinstance(spec, dict) and "const" in spec:
                    consts[key] = spec["const"]
        assert consts.get("event_name") == entry["x-event-name"], (
            f"{name}: x-event-name and the event_name const disagree"
        )
        out[entry["x-event-name"]] = {k: consts[k] for k in _ATTRS if k in consts} | {
            "$defs": name
        }
    return out


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return _UNRESOLVED


_UNRESOLVED = object()


def _append_event_calls() -> list[tuple[pathlib.Path, ast.Call]]:
    found: list[tuple[pathlib.Path, ast.Call]] = []
    for path in sorted(_BACKEND.rglob("*.py")):
        if "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a file that does not parse is CI's problem
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name != "append_event":
                continue
            if any(kw.arg == "event_name" for kw in node.keywords):
                found.append((path, node))
    return found


def _emissions() -> tuple[list[dict], list[str]]:
    """Every (event_name, aggregate_type, transition_id, customer_visible) the
    code can write, plus the call sites this file could not resolve."""

    emissions: list[dict] = []
    unresolved: list[str] = []
    for path, call in _append_event_calls():
        rel = str(path.relative_to(_BACKEND))
        kwargs = {kw.arg: _literal(kw.value) for kw in call.keywords if kw.arg in _ATTRS}
        if all(kwargs.get(a) is not _UNRESOLVED for a in _ATTRS) and len(kwargs) == len(_ATTRS):
            emissions.append({**kwargs, "site": f"{rel}:{call.lineno}"})
            continue
        resolver = _DYNAMIC_EMITTERS.get(rel)
        if resolver is not None:
            resolved = globals()[resolver](path, rel, call, kwargs)
            if resolved:
                emissions.extend(resolved)
                continue
        unresolved.append(f"{rel}:{call.lineno}")
    return emissions, unresolved


def _resolve_paired_assignments(
    path: pathlib.Path, rel: str, call: ast.Call, kwargs: dict
) -> list[dict]:
    """`handle_refund_event` picks its event name and transition id TOGETHER,
    one tuple assignment per branch (`transition_id, event_name = "OP-05",
    "payment.refunded_out_of_order"`). Reading the two names independently would
    cross the branches and invent pairs that no code path can produce, so the
    pairs are kept whole: each tuple assignment in the enclosing function is one
    candidate emission."""

    tree = ast.parse(path.read_text())
    enclosing = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= call.lineno <= (node.end_lineno or node.lineno):
                if enclosing is None or node.lineno > enclosing.lineno:
                    enclosing = node
    if enclosing is None:  # pragma: no cover - a call outside any function
        return []
    dynamic = {a for a in _ATTRS if kwargs.get(a) is _UNRESOLVED}
    pairs: list[dict] = []
    for node in ast.walk(enclosing):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target, value = node.targets[0], node.value
        if not (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)):
            continue
        names = [n.id for n in target.elts if isinstance(n, ast.Name)]
        values = [_literal(v) for v in value.elts]
        if len(names) != len(target.elts) or _UNRESOLVED in values:
            continue
        bound = dict(zip(names, values, strict=True))
        if not dynamic <= bound.keys():
            continue
        pairs.append(
            {
                **{a: kwargs[a] for a in _ATTRS if a not in dynamic},
                **{a: bound[a] for a in dynamic},
                "site": f"{rel}:{node.lineno} (paired with {rel}:{call.lineno})",
            }
        )
    return pairs


def _resolve_staff_transitions(
    path: pathlib.Path, rel: str, call: ast.Call, kwargs: dict
) -> list[dict]:
    """`staff_transitions.py` writes one event per entry of its own
    `TRANSITIONS` table: the key IS the transition id and the spec carries the
    event name. The table is imported, not parsed."""

    from backend.services.garuda_portal.staff_transitions import TRANSITIONS

    fixed = {a: kwargs.get(a) for a in ("aggregate_type", "customer_visible")}
    assert _UNRESOLVED not in fixed.values(), (
        f"{rel}:{call.lineno} varies aggregate_type/customer_visible too — this resolver "
        "only knows how to expand event_name and transition_id from TRANSITIONS"
    )
    return [
        {
            "event_name": spec.event_name,
            "transition_id": transition_id,
            **fixed,
            "site": f"{rel}:{call.lineno} (TRANSITIONS[{transition_id!r}])",
        }
        for transition_id, spec in TRANSITIONS.items()
    ]


def test_every_append_event_call_site_is_readable():
    """The guard's own coverage, asserted first: a call site this file cannot
    resolve is a HOLE, not a pass. It must be added to `_DYNAMIC_EMITTERS` with
    a resolver — which is a deliberate act, visible in review."""

    _emissions_, unresolved = _emissions()
    assert unresolved == [], (
        "append_event call sites with non-literal arguments and no resolver: "
        f"{unresolved} — add the table-reading resolver rather than widening the skip"
    )


def test_every_event_the_code_emits_is_in_the_contract():
    contract = _contract_events()
    emissions, _unresolved = _emissions()
    missing = sorted({e["event_name"] for e in emissions} - set(contract))
    assert missing == [], (
        f"events emitted with no `$defs` entry in {_CONTRACT.name}: {missing} — "
        "this is the direction a new writer breaks first"
    )


def test_every_contract_entry_matches_the_code_that_emits_it():
    contract = _contract_events()
    emissions, _unresolved = _emissions()
    drift = []
    for emission in emissions:
        described = contract.get(emission["event_name"])
        if described is None:
            continue  # covered by the test above, with a better message
        for attr in ("aggregate_type", "transition_id", "customer_visible"):
            if attr not in described:
                continue  # unpinned on purpose — `test_the_contract_pins_what_it_can`
            if described[attr] != emission[attr]:
                drift.append(
                    f"{emission['site']}: {emission['event_name']}.{attr} is "
                    f"{emission[attr]!r} in code, {described[attr]!r} in the contract"
                )
    assert drift == [], "contract and code disagree:\n" + "\n".join(drift)


def test_every_contract_entry_has_a_writer():
    """The other direction: an entry nothing emits is a description of a system
    that does not exist, and it reads exactly like one that does."""

    contract = _contract_events()
    emissions, _unresolved = _emissions()
    emitted = {e["event_name"] for e in emissions}
    orphans = sorted(set(contract) - emitted)
    assert orphans == [], (
        f"`$defs` entries no code emits: {orphans} — either the writer was never "
        "built or it was removed and the contract still promises the event"
    )


def test_the_contract_pins_what_it_can():
    """An attribute with no `const` is not compared, so the set of unpinned
    attributes IS the guard's blind spot — it is written down, and growing it
    has to be deliberate."""

    contract = _contract_events()
    unpinned = {
        (name, attr)
        for name, described in contract.items()
        for attr in ("aggregate_type", "transition_id", "customer_visible")
        if attr not in described
    }
    assert unpinned == _UNPINNED, (
        f"the contract's unpinned attributes changed: {sorted(unpinned ^ _UNPINNED)} — "
        "a dropped `const` weakens the contract without failing anything else"
    )


@pytest.mark.parametrize("attr", ["aggregate_type", "transition_id", "customer_visible"])
def test_the_comparison_is_falsifiable(attr):
    """Innocence for the guard itself: mutate the CONTRACT in memory and the
    comparison must notice. Without this, a scan that silently emitted zero
    emissions would pass every assertion above."""

    contract = _contract_events()
    emissions, _unresolved = _emissions()
    assert emissions, "the AST scan found no emissions at all — the guard is inert"
    victim = next(
        e for e in emissions if attr in contract.get(e["event_name"], {})
    )
    described = dict(contract[victim["event_name"]])
    flipped = {
        "aggregate_type": "NOT_A_REAL_AGGREGATE",
        "transition_id": "OP-NOPE",
        "customer_visible": not described["customer_visible"],
    }[attr]
    described[attr] = flipped
    assert described[attr] != victim[attr], (
        f"mutating {attr} in the contract did not change it relative to the code — "
        "the comparison cannot be failing for the right reason"
    )
