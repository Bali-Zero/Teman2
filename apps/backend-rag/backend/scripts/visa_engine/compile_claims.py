"""Offline CLI: compile a claim-backed rule-authoring manifest into engine
``Rule`` objects, gated by two hard lints.

E5 increment 1 (Visa Oracle doctrine-factory execution plan, vertical
slice: D1/D2/D12/E31B/E31D). This is a NEW compiler stage that sits
*before* ``compile_pack.py``: it consumes the claim ledgers written by the
E2a/E2b/E3a research passes (``research/visa/doctrine-factory/claims/
*.md``, parsed by ``backend.services.visa_engine.claim_ledger``) plus a
hand-authored rule-authoring manifest (a JSON file listing each rule's
``when``/``effect``/... alongside the ``claim_id``s that back it) and
emits validated ``Rule`` JSON — the reformed slice rules described in the
task brief (E31B's fail-open ``known`` gate closed to a value-checked
enum, E31D's over-broad ``intersects[FAMILY]``-only rules given real
discriminating facts) plus D1/D2/D12 passed through with claim provenance
attached.

Two hard lints, both compile errors (never warnings):

1. **VERIFIED-only.** Every ``claim_id`` a rule declares must resolve in
   the loaded ledgers and be at state ``VERIFIED`` or
   ``VERIFIED-WITH-CAVEAT``. A claim at ``CONFLICTING``/``STALE``/
   ``UNVERIFIED``/``SUPERSEDED``/``UNSTATED`` feeding a rule is a hard
   compile error naming the claim_id and the rule_id — this is the literal
   task-brief requirement ("a claim in state CONFLICTING/STALE/UNVERIFIED
   feeding a rule => hard compile error naming the claim_id"). A
   ``VERIFIED-WITH-CAVEAT`` claim is allowed only when the rule's manifest
   entry carries a matching caveat note in its ``caveats`` array — the
   caveat is required to be PROPAGATED into the rule's provenance, not
   silently dropped, per the same brief.

2. **R-OVERSTAY-PLANNING** (Zero, 2026-08-18, verbatim ruling — see the E5
   task brief and CP2 decision pack): a rule whose condition tree
   references ``immigration.overstay_days`` anywhere must have that
   reference gated behind ``immigration.currently_in_indonesia == true``
   in the same AND-chain (i.e. every ALL-ancestor between the tree root
   and the overstay leaf). ``overstay_days`` is pertinent ONLY onshore —
   an ungated reference is exactly the seq-6 smoke symptom the ruling
   names ("incomplete facts -> NEEDS_INPUT naming immigration.
   overstay_days" for an applicant who never said they were in
   Indonesia). This lint fires on the CONDITION STRUCTURE, independent of
   which product/claim the rule belongs to — it is a standing invariant
   for every rule this compiler ever emits, not a per-rule opt-in.

E5 increment 2 (2026-08-18) adds two more hard lints, each motivated by a
real defect confirmed in the active pack ``rulepack-prod-007.source.json``:

3. **UNSATISFIABLE-CONDITION.** ``el.e33e.deposit-income-basis`` is
   logically unsatisfiable: brute-force over the boolean abstraction (each
   *distinct* leaf condition — by canonical-JSON identity — treated as an
   independent atom) finds zero of its 64 assignments (6 distinct leaves)
   that satisfy the ``when``. Treating identical leaves as the SAME atom is
   what makes the contradiction visible at all — E33E's outer ``all``
   re-asserts ``bank_deposit_usd/at_state_bank/in_own_name/
   passive_monthly_income_usd`` as a plain conjunction while its inner
   branch demands their XOR, and only sharing the atom across both
   occurrences lets brute-force see that. This check is sound for
   UNSAT-by-*structure* (independent atoms is the most permissive possible
   reading: if even that has no satisfying assignment, the rule can never
   fire under any stricter, arithmetic-aware semantics either) but
   deliberately blind to *arithmetic* contradictions — e.g. it cannot see
   that ``x > 5`` and ``x < 3`` are the same variable and treats them as
   two unrelated atoms. Do not extend this into an arithmetic solver; that
   is a different, much harder tool. Guarded: a ``when`` with more than 20
   distinct leaves is not brute-forced (2**20 is already over a million
   assignments per rule) — the compiler emits an explicit
   "satisfiability not checked (N leaves > 20)" report note instead of
   silently skipping.

4. **VACUOUS-RULE.** ``el.e33g.income-60k-manual`` claims (by name) to
   gate on income but its ``when`` is the same remote-work block
   literally duplicated twice — it references zero income facts, and the
   literal ``60000`` appears nowhere in the pack. Two purely mechanical
   checks (never rule-name/intent inference — that is form, not entity):
   (a) duplicate-subtree: an ``all``/``any`` node with two
   structurally-identical (canonical-JSON-equal) children is a compile
   error — the duplication itself is the smell; (b) an OPTIONAL manifest
   entry field ``must_reference_facts: [fact paths]`` lets an author
   assert "this rule is about fact X" and have the compiler prove every
   listed fact actually appears in the derived ``required_facts``.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.compile_claims \\
        --claims research/visa/doctrine-factory/claims/e2a-claim-ledger.md \\
                 research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md \\
                 research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md \\
                 research/visa/doctrine-factory/claims/e3a-cf1-resolution.md \\
        --manifest research/visa/doctrine-factory/e5/slice-rule-manifest.json \\
        --out /tmp/e5-slice-compiled.json

Exit code 0 only when every rule compiles clean; 1 on any lint violation or
malformed input (never a bare traceback for a data problem — see ``main``).

Deliberately NOT in scope here (task brief, "increment 1"): assembling a
full signed ``RulePackPayload`` (that needs a ``source_records`` array and
the sequence/rollback chain a whole pack carries — ``compile_pack.py`` /
``sign_pack.py`` / ``activate_pack.py`` own that, later increment), and
never touches a signed pack on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.services.visa_engine.ast import collect_fact_paths, parse_condition
from backend.services.visa_engine.claim_ledger import (
    ClaimLedgerError,
    ClaimRecord,
    load_claim_ledgers,
)
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.models import Rule

#: The overstay-planning invariant's two facts, by name (matches
#: ``enums.FactPath`` exactly — see the module docstring's rationale).
_OVERSTAY_FACT = FactPath.IMMIGRATION_OVERSTAY_DAYS.value
_ONSHORE_FACT = FactPath.IMMIGRATION_CURRENTLY_IN_INDONESIA.value


class CompileClaimsError(ValueError):
    """A manifest entry failed a hard lint or failed to parse/validate."""


class LintFinding:
    """One compile error, always naming the offending rule_id and (when
    applicable) the offending claim_id — never a bare "compilation failed".
    """

    __slots__ = ("message", "rule_id")

    def __init__(self, rule_id: str, message: str) -> None:
        self.rule_id = rule_id
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.rule_id}: {self.message}"

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"LintFinding(rule_id={self.rule_id!r}, message={self.message!r})"


class CompiledEntry:
    """One successfully-compiled rule plus its provenance."""

    __slots__ = ("caveats", "claim_ids", "product_code", "rule")

    def __init__(
        self,
        *,
        product_code: str,
        claim_ids: list[str],
        caveats: list[dict[str, str]],
        rule: Rule,
    ) -> None:
        self.product_code = product_code
        self.claim_ids = claim_ids
        self.caveats = caveats
        self.rule = rule

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_code": self.product_code,
            "claim_ids": self.claim_ids,
            "caveats": self.caveats,
            "rule": json.loads(self.rule.model_dump_json()),
        }


# ---------------------------------------------------------------------------
# Lint 1: VERIFIED-only
# ---------------------------------------------------------------------------


def lint_verified_only(
    *,
    rule_id: str,
    claim_ids: list[str],
    caveats: list[dict[str, str]],
    ledger: dict[str, ClaimRecord],
    product_code: str = "",
) -> list[LintFinding]:
    """VERIFIED-only lint (task brief, literal requirement).

    ``product_code`` resolves a PRODUCT-CONDITIONAL claim (kimi-k3
    adversarial finding, 2026-08-18: ``CL-D-FUNDS`` is VERIFIED for
    D1/D12 but VERIFIED-WITH-CAVEAT for D2 on one state line) to the
    state that actually applies to THIS rule's product, via
    ``ClaimRecord.state_for_product``/``compilable_for_product`` — a
    claim-wide ``.state``/``.compilable`` would silently pick the first
    token found and apply it to every product, exactly the bypass the
    review caught live (a D2 rule citing CL-D-FUNDS compiling with no
    caveat requirement).

    A rule with zero declared claim_ids is itself a finding — this
    compiler's entire purpose is claim-backed rule authoring, so a rule
    with no provenance at all is not a degenerate-but-legal case, it is a
    manifest authoring error.

    Malformed ``caveats`` entries (missing/empty ``claim_id`` or ``note``,
    or a non-dict entry) are reported as findings, never a bare crash — a
    kimi-k3 adversarial review (2026-08-18) caught the original
    ``{c["claim_id"] for c in caveats}`` set-comprehension raising
    ``KeyError``/``TypeError`` on exactly this kind of manifest typo,
    contradicting this module's own "never a bare traceback for a data
    problem" contract. A caveat with an empty ``note`` is ALSO now a
    finding — the task brief requires the caveat be "propagated", and an
    empty string satisfies no reader; the earlier version only checked for
    the *entry's presence*, not that it actually said anything.
    """

    findings: list[LintFinding] = []
    if not claim_ids:
        findings.append(
            LintFinding(
                rule_id, "declares zero claim_ids — every compiled rule must be claim-backed"
            )
        )
        return findings

    caveated_claim_ids: set[str] = set()
    for i, caveat in enumerate(caveats):
        if not isinstance(caveat, dict):
            findings.append(LintFinding(rule_id, f"caveats[{i}] is not an object: {caveat!r}"))
            continue
        cid = caveat.get("claim_id")
        note = caveat.get("note")
        if not isinstance(cid, str) or not cid:
            findings.append(
                LintFinding(rule_id, f"caveats[{i}] has a missing/empty claim_id: {caveat!r}")
            )
            continue
        if not isinstance(note, str) or not note.strip():
            findings.append(
                LintFinding(rule_id, f"caveats[{i}] for claim_id {cid!r} has a missing/empty note")
            )
            continue
        caveated_claim_ids.add(cid)

    for claim_id in claim_ids:
        record = ledger.get(claim_id)
        if record is None:
            findings.append(
                LintFinding(rule_id, f"claim_id {claim_id!r} does not resolve in any loaded ledger")
            )
            continue
        effective_state = record.state_for_product(product_code)
        if not record.compilable_for_product(product_code):
            findings.append(
                LintFinding(
                    rule_id,
                    f"claim {claim_id!r} is at state {effective_state!r} "
                    f"for product {product_code!r} ({record.source_file}) — "
                    "VERIFIED-only violation: a "
                    "CONFLICTING/STALE/UNVERIFIED/SUPERSEDED/UNSTATED claim "
                    "may never back a compiled rule",
                )
            )
            continue
        if effective_state == "VERIFIED-WITH-CAVEAT" and claim_id not in caveated_claim_ids:
            findings.append(
                LintFinding(
                    rule_id,
                    f"claim {claim_id!r} is VERIFIED-WITH-CAVEAT but the rule's "
                    "manifest entry carries no matching caveat note — the "
                    "caveat must be propagated into provenance, never dropped",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Lint 2: R-OVERSTAY-PLANNING
# ---------------------------------------------------------------------------


def _walk_overstay_gating(condition: Any, *, all_ancestor_facts: frozenset[str]) -> list[str]:
    """Return every path (as human-readable breadcrumbs, empty list if none)
    where ``immigration.overstay_days`` is referenced WITHOUT
    ``immigration.currently_in_indonesia == true`` present among the
    sibling/ancestor conditions of every enclosing ``all`` node.

    ``all_ancestor_facts`` accumulates the set of facts proven true by a
    direct ``{"op": "eq", "fact": ..., "value": true}`` (or the onshore
    fact's own presence check — see below) sibling anywhere in the current
    ``all``-chain: AND is associative, so a guard several ``all`` levels up
    still gates a leaf several levels down. It does NOT cross an ``any`` or
    ``not`` boundary — a guard inside one branch of an ``any`` does not
    protect a leaf in a sibling branch (the whole point of ``any`` is that
    either branch alone can make the condition true), and a guard is
    meaningless once inverted by ``not``.
    """

    if not isinstance(condition, dict):
        return []

    op = condition.get("op")

    if op == "all":
        args = condition.get("args", [])
        local_true_facts = {
            a["fact"]
            for a in args
            if isinstance(a, dict)
            and a.get("op") == "eq"
            and a.get("value") is True
            and isinstance(a.get("fact"), str)
        }
        combined = all_ancestor_facts | local_true_facts
        violations: list[str] = []
        for arg in args:
            violations.extend(_walk_overstay_gating(arg, all_ancestor_facts=combined))
        return violations

    if op == "any":
        # Each branch is independently sufficient — a guard elsewhere in
        # the tree (even a sibling ALL ancestor above this `any`) still
        # protects every branch, since AND-of-ancestors still applies; only
        # a NEW guard local to one `any` branch does not protect its
        # siblings. Re-walk each branch with the SAME ancestor set (not
        # widened), since branches don't share new local facts.
        violations = []
        for arg in condition.get("args", []):
            violations.extend(_walk_overstay_gating(arg, all_ancestor_facts=all_ancestor_facts))
        return violations

    if op == "not":
        # Negation strips any protective value from ancestor guards that
        # live ONLY inside this subtree (there are none reachable here
        # since we pass the same ancestor set down, unchanged), and a fact
        # referenced under `not` isn't itself a new guard either way.
        return _walk_overstay_gating(condition.get("arg"), all_ancestor_facts=all_ancestor_facts)

    # Leaf condition.
    fact = condition.get("fact")
    if fact == _OVERSTAY_FACT:
        if _ONSHORE_FACT not in all_ancestor_facts:
            return [
                f"leaf condition on {_OVERSTAY_FACT!r} has no "
                f"{_ONSHORE_FACT!r}==true guard among its ALL-ancestors"
            ]
        return []
    return []


def lint_overstay_planning(*, rule_id: str, when: dict[str, Any]) -> list[LintFinding]:
    """R-OVERSTAY-PLANNING lint (Zero ruling 2026-08-18, see module docstring)."""

    violations = _walk_overstay_gating(when, all_ancestor_facts=frozenset())
    return [LintFinding(rule_id, v) for v in violations]


# ---------------------------------------------------------------------------
# Lint 3: UNSATISFIABLE-CONDITION
# ---------------------------------------------------------------------------

#: Above this many DISTINCT leaves, 2**N brute-force assignments becomes
#: too expensive to run per-rule at compile time (2**21 already exceeds two
#: million). This is a declared limit, not a silent skip — the compiler
#: reports the exact leaf count in a report note when it is hit.
_MAX_LEAVES_FOR_SAT_CHECK = 20


def _canonical_key(node: Any) -> str:
    """Canonical-JSON identity for a condition node — the basis on which
    two leaves (Lint 3) or two subtrees (Lint 4) are considered "the same".
    """

    return json.dumps(node, sort_keys=True)


def _safe_args(condition: dict[str, Any]) -> list[Any]:
    """``condition.get("args", [])`` is not safe on its own: a manifest can
    carry the KEY with a JSON ``null`` (or any non-list) value, in which
    case the default never applies and iterating the result raises —
    exactly the "bare traceback for a data problem" this module's own
    docstring forbids (kimi-k3 finding, 2026-08-18). Malformed ``args`` is
    treated as "no children" here; ``Rule.model_validate`` (later in
    ``compile_manifest``) is what actually rejects the malformed shape.
    """

    args = condition.get("args")
    return args if isinstance(args, list) else []


#: A compiled boolean "shape" node: ``("const", bool)`` for a fixed truth
#: value, ``("leaf", canonical_key)`` for a boolean atom, or
#: ``("all"|"any", tuple[_Shape, ...])`` / ``("not", _Shape)`` for a
#: combinator. Compiling `when` into this form ONCE means the brute-force
#: loop below evaluates plain tuples/strings — no `json.dumps` re-run per
#: leaf per assignment (kimi-k3 perf finding, 2026-08-18: the naive
#: re-serialize-every-lookup approach did ~2**20 x leaf-count `json.dumps`
#: calls at exactly the boundary this lint is documented to still check).
_Shape = tuple[Any, ...]


def _compile_boolean_shape(condition: Any, leaves: dict[str, Any]) -> _Shape:
    """Compile ``condition`` into a ``_Shape`` AND collect every distinct
    leaf (by canonical-JSON identity) into ``leaves`` — same traversal that
    used to be two separate functions, now one pass so collection and
    evaluation can never disagree about what counts as a leaf.
    """

    if not isinstance(condition, dict):
        # Malformed/non-dict node: never fabricate an UNSAT finding out of
        # a shape this walker doesn't understand — `Rule.model_validate`
        # owns rejecting it.
        return ("const", True)

    op = condition.get("op")
    if op in ("all", "any"):
        children = tuple(_compile_boolean_shape(a, leaves) for a in _safe_args(condition))
        return (op, children)
    if op == "not":
        return ("not", _compile_boolean_shape(condition.get("arg"), leaves))

    key = _canonical_key(condition)
    leaves[key] = condition
    return ("leaf", key)


def _evaluate_boolean_shape(shape: _Shape, assignment: dict[str, bool]) -> bool:
    """Evaluate a pre-compiled ``_Shape`` under a full leaf assignment —
    pure structural boolean algebra (AND/OR/NOT), no arithmetic, no fact
    semantics.
    """

    kind = shape[0]
    if kind == "const":
        return bool(shape[1])
    if kind == "all":
        return all(_evaluate_boolean_shape(c, assignment) for c in shape[1])
    if kind == "any":
        return any(_evaluate_boolean_shape(c, assignment) for c in shape[1])
    if kind == "not":
        return not _evaluate_boolean_shape(shape[1], assignment)
    return assignment[shape[1]]  # kind == "leaf"


def lint_unsatisfiable_condition(
    *, rule_id: str, when: dict[str, Any]
) -> tuple[list[LintFinding], str | None]:
    """UNSATISFIABLE-CONDITION lint (see module docstring, Lint 3).

    Returns ``(findings, skip_note)`` — ``skip_note`` is set (and
    ``findings`` empty) when the leaf count exceeds
    ``_MAX_LEAVES_FOR_SAT_CHECK``: the check was NOT run, and that must be
    visible in the report rather than silently indistinguishable from
    "checked and satisfiable".

    A `when` with ZERO distinct leaves (e.g. ``{"op": "any", "args": []}``)
    is still fully evaluated, not short-circuited as trivially satisfiable
    — an empty ``any`` is Kleene-FALSE and genuinely unsatisfiable, and an
    early "no leaves -> pass" return would have missed exactly that
    (kimi-k3 finding, 2026-08-18). The brute-force loop below handles this
    for free: 0 leaves means ``2**0 == 1`` assignment (the empty one), and
    that single evaluation IS the answer.
    """

    leaves: dict[str, Any] = {}
    shape = _compile_boolean_shape(when, leaves)

    if len(leaves) > _MAX_LEAVES_FOR_SAT_CHECK:
        return [], (
            f"{rule_id}: satisfiability not checked "
            f"({len(leaves)} leaves > {_MAX_LEAVES_FOR_SAT_CHECK})"
        )

    keys = list(leaves.keys())
    total = 1 << len(keys)
    for bits in range(total):
        assignment = {key: bool((bits >> i) & 1) for i, key in enumerate(keys)}
        if _evaluate_boolean_shape(shape, assignment):
            return [], None

    return (
        [
            LintFinding(
                rule_id,
                "condition is UNSATISFIABLE — brute-force over "
                f"{len(keys)} distinct leaf condition(s) (each treated as an "
                f"independent boolean atom) finds zero of {total} assignments "
                "that satisfy `when`; this rule can never fire. NOTE: this "
                "check is sound for UNSAT-by-structure but blind to "
                "arithmetic contradictions between different leaves (e.g. "
                "x>5 AND x<3) — if this fired, the tree really is "
                "structurally self-contradictory, not merely "
                "arithmetic-narrow.",
            )
        ],
        None,
    )


# ---------------------------------------------------------------------------
# Lint 4: VACUOUS-RULE
# ---------------------------------------------------------------------------


def _find_duplicate_subtrees(condition: Any, rule_id: str) -> list[LintFinding]:
    """Mechanical duplicate-subtree detection (see module docstring, Lint 4a):
    an ``all``/``any`` node with two structurally-identical
    (canonical-JSON-equal) children is a compile error — the duplication
    itself is the smell, independent of what the rule is named or what it
    claims to be about.
    """

    findings: list[LintFinding] = []
    if not isinstance(condition, dict):
        return findings

    op = condition.get("op")
    if op in ("all", "any"):
        args = _safe_args(condition)
        seen: dict[str, int] = {}
        for i, arg in enumerate(args):
            key = _canonical_key(arg)
            first_index = seen.get(key)
            if first_index is not None:
                findings.append(
                    LintFinding(
                        rule_id,
                        f"{op!r} node has two structurally identical children "
                        f"(args[{first_index}] == args[{i}]) — a duplicated "
                        "child adds no logical content beyond a single copy "
                        "(VACUOUS-RULE): if the intent was two DIFFERENT "
                        "conditions, one of them was never actually written",
                    )
                )
            else:
                seen[key] = i
        for arg in args:
            findings.extend(_find_duplicate_subtrees(arg, rule_id))
    elif op == "not":
        findings.extend(_find_duplicate_subtrees(condition.get("arg"), rule_id))

    return findings


def lint_duplicate_subtree(*, rule_id: str, when: dict[str, Any]) -> list[LintFinding]:
    """VACUOUS-RULE lint, part (a): duplicate-subtree detection (see module
    docstring, Lint 4).
    """

    return _find_duplicate_subtrees(when, rule_id)


def lint_must_reference_facts(
    *, rule_id: str, must_reference_facts: list[str], derived_facts: list[str]
) -> list[LintFinding]:
    """VACUOUS-RULE lint, part (b): the OPTIONAL manifest field
    ``must_reference_facts`` (see module docstring, Lint 4). An author
    declares "this rule is about fact X"; the compiler proves every listed
    fact actually appears in the ``when``-derived ``required_facts`` — a
    mechanical proof, never an inference from the rule's name or claim_ids.
    """

    findings: list[LintFinding] = []
    derived_set = set(derived_facts)
    for i, fact in enumerate(must_reference_facts):
        if not isinstance(fact, str):
            # A non-string (and possibly unhashable, e.g. a dict/list)
            # entry must never crash `fact not in derived_set` — that is
            # exactly the bare-traceback-on-a-data-problem contract this
            # module's own docstring forbids (kimi-review-adjacent finding,
            # 2026-08-18: team-lead's parallel gate on this diff).
            findings.append(
                LintFinding(rule_id, f"must_reference_facts[{i}] is not a string: {fact!r}")
            )
            continue
        if fact not in derived_set:
            findings.append(
                LintFinding(
                    rule_id,
                    f"manifest entry declares must_reference_facts includes "
                    f"{fact!r} but the rule's condition tree never references "
                    f"it (derived required_facts: {sorted(derived_set)!r}) — "
                    "VACUOUS-RULE: the rule claims to be about a fact it "
                    "never actually checks",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Compiler entrypoint
# ---------------------------------------------------------------------------


class CompilationReport:
    def __init__(self) -> None:
        self.findings: list[LintFinding] = []
        self.compiled: list[CompiledEntry] = []
        #: Declared-limit notes (never silent) — e.g. Lint 3's
        #: satisfiability-not-checked skip when a `when` has too many
        #: distinct leaves to brute-force.
        self.notes: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.findings

    def render(self) -> str:
        lines = []
        if self.ok:
            lines.append(f"OK — {len(self.compiled)} rule(s) compiled clean.")
        else:
            lines.append(f"FAILED — {len(self.findings)} finding(s):")
            for f in self.findings:
                lines.append(f"  - {f}")
        if self.notes:
            lines.append(f"NOTES — {len(self.notes)} declared-limit note(s):")
            for note in self.notes:
                lines.append(f"  - {note}")
        return "\n".join(lines)


def compile_manifest(
    manifest: dict[str, Any],
    ledger: dict[str, ClaimRecord],
) -> CompilationReport:
    report = CompilationReport()

    entries = manifest.get("rules")
    if not isinstance(entries, list) or not entries:
        report.findings.append(
            LintFinding("<manifest>", "manifest.rules must be a non-empty array")
        )
        return report

    for entry in entries:
        if not isinstance(entry, dict):
            report.findings.append(
                LintFinding("<manifest>", f"manifest entry is not an object: {entry!r}")
            )
            continue

        rule_src = entry.get("rule")
        rule_id = rule_src.get("rule_id") if isinstance(rule_src, dict) else "<unknown>"
        claim_ids = entry.get("claim_ids") or []
        caveats = entry.get("caveats") or []
        product_code = entry.get("product_code", "<unknown>")

        if not isinstance(rule_src, dict):
            report.findings.append(LintFinding(rule_id, "manifest entry has no 'rule' object"))
            continue

        entry_findings_start = len(report.findings)

        # Lint 1 — VERIFIED-only (runs even if the Rule itself fails to
        # parse, so a claim problem is never masked by a schema problem).
        report.findings.extend(
            lint_verified_only(
                rule_id=rule_id,
                claim_ids=claim_ids,
                caveats=caveats,
                ledger=ledger,
                product_code=product_code if isinstance(product_code, str) else "<unknown>",
            )
        )

        when = rule_src.get("when")
        if isinstance(when, dict):
            report.findings.extend(lint_overstay_planning(rule_id=rule_id, when=when))

            # Lint 3 — UNSATISFIABLE-CONDITION.
            unsat_findings, skip_note = lint_unsatisfiable_condition(rule_id=rule_id, when=when)
            report.findings.extend(unsat_findings)
            if skip_note is not None:
                report.notes.append(skip_note)

            # Lint 4a — VACUOUS-RULE: duplicate-subtree detection.
            report.findings.extend(lint_duplicate_subtree(rule_id=rule_id, when=when))

        # Derive required_facts from `when` — never trust a manifest-supplied
        # value (mirrors compile_pack.py's compiler-level invariant, applied
        # here at authoring time instead of at pack-assembly time). Parse
        # `when` into the real discriminated `Condition` union first —
        # `collect_fact_paths` walks typed nodes (`node.fact`), not raw
        # dicts, so calling it on the manifest's plain dict silently visits
        # nothing and derives an empty required_facts set (caught live by
        # this compiler's own tests before this comment existed).
        try:
            parsed_when = parse_condition(when)
            derived_facts = sorted(collect_fact_paths(parsed_when))
        except (ValidationError, ValueError, TypeError) as exc:
            report.findings.append(
                LintFinding(rule_id, f"condition tree could not be parsed: {exc}")
            )
            continue

        # Lint 4b — VACUOUS-RULE: optional must_reference_facts assertion.
        # Absent (key missing, or explicit JSON null) means "not declared" —
        # anything else that isn't a list is malformed and must be flagged,
        # never silently coerced to "not declared" (kimi-k3 finding,
        # 2026-08-18: `entry.get(...) or []` previously swallowed falsy-but-
        # present values like `""`/`0` as if the field were simply absent).
        raw_must_reference_facts = entry.get("must_reference_facts")
        if raw_must_reference_facts is None:
            pass
        elif isinstance(raw_must_reference_facts, list):
            report.findings.extend(
                lint_must_reference_facts(
                    rule_id=rule_id,
                    must_reference_facts=raw_must_reference_facts,
                    derived_facts=derived_facts,
                )
            )
        else:
            report.findings.append(
                LintFinding(
                    rule_id, "manifest entry's must_reference_facts must be a list when present"
                )
            )

        rule_payload = {**rule_src, "required_facts": derived_facts}
        try:
            rule = Rule.model_validate(rule_payload)
        except ValidationError as exc:
            report.findings.append(LintFinding(rule_id, f"Rule schema validation failed: {exc}"))
            continue

        # A rule that failed a lint above (VERIFIED-only or R-OVERSTAY-
        # PLANNING) must never be added to `compiled`, even though it may
        # have gone on to parse structurally clean — a lint failure makes
        # the WHOLE rule uncompilable, not just the finding cosmetic.
        if len(report.findings) > entry_findings_start:
            continue

        report.compiled.append(
            CompiledEntry(
                product_code=product_code, claim_ids=claim_ids, caveats=caveats, rule=rule
            )
        )

    return report


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--claims", nargs="+", required=True, type=Path, help="claim ledger markdown file(s)"
    )
    parser.add_argument("--manifest", required=True, type=Path, help="rule-authoring manifest JSON")
    parser.add_argument(
        "--out", type=Path, default=None, help="write compiled rules JSON here on success"
    )
    args = parser.parse_args(argv)

    try:
        ledger = load_claim_ledgers(args.claims)
    except (OSError, ClaimLedgerError) as exc:
        print(f"error loading claim ledgers: {exc}", file=sys.stderr)
        return 1

    try:
        manifest = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error loading manifest: {exc}", file=sys.stderr)
        return 1

    report = compile_manifest(manifest, ledger)
    print(report.render())

    if not report.ok:
        return 1

    if args.out is not None:
        args.out.write_text(
            json.dumps([e.to_dict() for e in report.compiled], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(report.compiled)} compiled rule(s) to {args.out}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
