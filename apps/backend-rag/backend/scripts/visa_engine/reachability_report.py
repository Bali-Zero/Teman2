"""Read-only reachability / gap report generator for a signed Visa Engine RulePack.

QW-3 (Visa Oracle doctrine-factory execution plan, §1): today the 27/11
static-reachability split lives only as asserts inside
``backend/tests/services/visa_engine/test_seq6_refuter_witnesses.py``, pinned
against ``rulepack-prod-006.source.json`` — a pack that is no longer the one
in production. This script generalizes that one-off check into a reusable,
pack-agnostic CLI so the same measurement can be re-run against whichever
pack is ACTUALLY active, without re-deriving the logic by hand each time.

Given a RulePack SOURCE JSON (the unsigned legal content — see
``compile_pack.py``'s docstring for the authoring format), this script
reports, purely from static analysis:

  * **Reachable vs blocked products** — a product is statically reachable
    iff at least one ``SUPPORT``-effect rule names it, either explicitly in
    ``product_version_ids`` (``scope: PRODUCTS``) or implicitly because the
    rule is ``scope: GLOBAL`` (``product_version_ids: null``), which the
    real evaluator applies to every product in the pack (a ``GLOBAL``
    ``SUPPORT`` rule is unusual — no rule in the current active pack has
    one — but this script must not silently misreport if a future pack
    adds one). Everything else is blocked: either every rule that names it
    is ``EXCLUDE``/``REQUIRE_REVIEW``, or no rule names it at all.
  * **FactPaths referenced by zero rules** — the engine's closed fact
    vocabulary (``fact_registry.DEFAULT_FACT_REGISTRY``, 44 paths: 41
    applicant-collected + 3 ``derived.*``) minus every path
    ``ast.collect_fact_paths(rule.when)`` actually finds in this pack's
    condition trees — the AUTHORITATIVE source, because it reads what the
    evaluator would actually walk. ``rule.required_facts`` (a separate,
    author-declared field) is cross-checked against it and reported
    separately as ``required_facts_ast_mismatches``: the compiler enforces
    ``required_facts == collect_fact_paths(when)`` as an invariant, but that
    invariant is Pydantic-independent — a *pack that validates against the
    Pydantic schema* is not the same claim as *a pack that compiles*, so a
    parsable-but-uncompilable pack could carry a stale ``required_facts``
    that disagrees with the AST. Trusting the declared field instead of the
    AST would silently launder that disagreement into a wrong fact-usage
    report.
  * **NOT_ASKED facts** — the facts the live production interview
    (``apps/mouth/.../visa-oracle/_lib/fact-mapper.ts``) hard-codes to
    ``UNKNOWN(NOT_ASKED)`` unconditionally, regardless of what the applicant
    answered. This is read from the frontend source file directly (a
    best-effort text scan documented below), not from the pack — the pack
    has no opinion on what the UI asks.
  * **Orphan rules** — rules whose ``product_version_ids`` name a
    product_version_id that is not in this pack's ``products`` list. The
    Pydantic model layer already forbids the degenerate case (an empty or
    null list on a PRODUCTS-scope rule fails validation before this script
    ever sees it), so this check is specifically for dangling UUID
    references to a product that plain doesn't exist in this pack.
    **This is NOT a silent no-op the pack "compiles clean" through** — an
    earlier draft of this docstring claimed that, and it was wrong:
    ``compiler.py``'s ``_check_product_reference_integrity`` collects it as
    an ``UNKNOWN_PRODUCT_REFERENCE`` ``CompilationError``, and
    ``compiler.py``'s higher-level ``compile_pack``-style entry point
    raises ``RulePackCompilationError`` on any non-empty error list — so a
    pack with an orphan rule is schema-VALID (this script can load and
    report on it) but compilation-INVALID (it would never be signable via
    ``sign_pack.py``). This script deliberately reports it anyway, on the
    valid products, precisely so a would-be author sees the defect before
    running the real compile step.
  * **Products with zero product-scoped rules** — distinct from "blocked":
    a product can be blocked *and* have rules (excluded by name), or
    blocked because literally nothing in the pack ever names it (no
    HARD_FILTER, SUPPORT, REQUIRE_REVIEW, *or* ``ADD_SCORE``/``RANKING``
    rule scoped to it — it is only ever touched by GLOBAL rules, if at
    all).
  * **Products without a positive persona** — cross-referenced against the
    20-persona corpus in
    ``backend/tests/services/visa_engine/test_evaluator_gold.py``.
    **CAVEAT, load-bearing:** per the visaoracle skill's 2026-08-12 LIVE
    STATE entry, that corpus replays against a HAND-WRITTEN FIXTURE pack,
    never the signed pack this script inspects, and the two packs' product
    codes diverge (the fixture's ``E31`` vs this pack's ``E31A``..``E31J``).
    A low/zero overlap here does not mean "0 products have ever been
    positively exercised" — it measures the persona corpus's vocabulary gap
    against THIS pack, which nothing had quantified before.

This script never mutates a pack file, never signs anything, and never
touches the DB / Fly / network — pure offline static analysis: read pack
JSON -> typed model -> report. It never imports the pytest test module for
the persona cross-reference (that would require pytest machinery at import
time and couples a production script to a test file); instead it reads the
`expected_candidates=(...)` tuples out of that file's source text, which is
documented and covered by its own test (`test_gold_persona_extraction_is_
still_accurate` in the sibling test file) so a drift in that file's shape
fails loud here instead of silently going stale.

Usage (from ``apps/backend-rag``)::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.reachability_report \\
      --pack backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json \\
      --out-dir ../../research/visa/doctrine-factory/reachability

Exit code is 0 on a successful report (regardless of what the report finds —
"11 blocked products" is data, not a script failure), non-zero only on a
read/parse/validation failure of the pack file itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import ValidationError

from backend.scripts.visa_engine.compile_pack import load_rule_pack_payload
from backend.services.visa_engine.ast import collect_fact_paths
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import Rule, RulePackPayload, VisaProductVersion

#: Monorepo root, derived from this file's own location rather than the
#: caller's cwd (``PYTHONPATH=. python -m ...`` is conventionally invoked
#: from ``apps/backend-rag``, not the repo root — see this module's own
#: usage example — so a cwd-relative default would break the moment someone
#: follows that convention). This file lives at
#: ``apps/backend-rag/backend/scripts/visa_engine/reachability_report.py``,
#: five parents up from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]

#: Default location of the live production interview's fact-mapper — the
#: ONLY place that hard-codes which facts are never asked regardless of
#: applicant answers.
DEFAULT_FACT_MAPPER_PATH = (
    _REPO_ROOT / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts"
)

#: Default location of the 20-gold-persona corpus this script
#: cross-references for the "positive persona" check.
DEFAULT_GOLD_PERSONA_TEST_PATH = (
    _REPO_ROOT / "apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py"
)

#: Isolates the `const data: ApplicantFactsDataWire = { ... };` object
#: literal in the fact-mapper before the NOT_ASKED regex runs over it —
#: scoping the scan to the one block that actually assigns wire facts, so a
#: `"x.y": unknownFact(NOT_ASKED),`-shaped comment or template-literal
#: string elsewhere in the file can't false-positive into the result (a
#: real gap a cross-family review found in an earlier draft that scanned
#: the whole file).
_DATA_LITERAL_RE = re.compile(r"const data: ApplicantFactsDataWire = \{(.*?)\n  \};", re.DOTALL)

#: Matches a `"path.name": unknownFact(NOT_ASKED)` assignment inside the
#: isolated data-literal block — the unconditional (no ternary, no `?? `)
#: NOT_ASKED sentinel. Deliberately narrow: a conditional NOT_ASKED
#: (`value === undefined ? unknownFact(...) : ...`) means the fact CAN be
#: collected and is out of scope for this "never asked, full stop" list.
_UNCONDITIONAL_NOT_ASKED_RE = re.compile(r'"([a-z_]+\.[a-z_]+)":\s*unknownFact\(NOT_ASKED\),')

#: Matches an `expected_candidates=("CODE", "CODE2"),` tuple literal in the
#: gold-persona dataclass instances.
_EXPECTED_CANDIDATES_RE = re.compile(r"expected_candidates=\(([^)]*)\)")

#: Product codes: `PRODUCT_CODE_PATTERN` in models.py is
#: `^[A-Z][A-Z0-9-]{0,31}$` — a leading uppercase letter, then uppercase
#: letters/digits/HYPHENS. An earlier draft of this regex was `[A-Z0-9]+`,
#: which would silently drop a hyphenated code (e.g. a hypothetical
#: `"E-31"`) out of the persona-corpus cross-reference and falsely inflate
#: `products_without_positive_persona`.
_QUOTED_CODE_RE = re.compile(r'"([A-Z][A-Z0-9-]{0,31})"')


@dataclass(frozen=True, slots=True)
class ProductReachability:
    product_code: str
    product_version_id: str
    reachable: bool
    support_rule_ids: tuple[str, ...]
    exclude_rule_ids: tuple[str, ...]
    require_review_rule_ids: tuple[str, ...]
    add_score_rule_ids: tuple[str, ...]

    @property
    def has_any_scoped_rule(self) -> bool:
        return bool(
            self.support_rule_ids
            or self.exclude_rule_ids
            or self.require_review_rule_ids
            or self.add_score_rule_ids
        )


@dataclass(frozen=True, slots=True)
class OrphanRuleFinding:
    rule_id: str
    dangling_product_version_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReachabilityReport:
    pack_path: str
    rule_pack_id: str
    sequence: int
    version: str
    environment: str
    product_count: int
    rule_count: int
    reachable_product_codes: tuple[str, ...]
    blocked_product_codes: tuple[str, ...]
    products_with_zero_scoped_rules: tuple[str, ...]
    unused_fact_paths: tuple[str, ...]
    used_fact_paths: tuple[str, ...]
    total_fact_paths: int
    required_facts_ast_mismatches: tuple[str, ...]
    not_asked_facts: tuple[str, ...]
    not_asked_facts_source: str
    orphan_rules: tuple[OrphanRuleFinding, ...]
    products_without_positive_persona: tuple[str, ...]
    persona_corpus_product_codes: tuple[str, ...]
    persona_corpus_codes_absent_from_pack: tuple[str, ...]
    persona_corpus_source: str
    products: tuple[ProductReachability, ...] = field(repr=False)


def _extract_not_asked_facts(fact_mapper_path: Path) -> tuple[str, ...]:
    """Best-effort text scan of the frontend fact-mapper for unconditional
    ``unknownFact(NOT_ASKED)`` assignments, scoped to the
    ``data: ApplicantFactsDataWire = { ... }`` object literal — not the
    whole file — so a comment or unrelated string elsewhere can't
    false-positive into the result. Raises ``ValueError`` if that literal
    can't be located at all (the file's shape changed enough that a silent
    empty result would be worse than a loud failure).
    """
    text = fact_mapper_path.read_text(encoding="utf-8")
    match = _DATA_LITERAL_RE.search(text)
    if match is None:
        raise ValueError(
            f"{fact_mapper_path}: could not locate the "
            "`const data: ApplicantFactsDataWire = { ... };` block — the file's "
            "shape has drifted; update _DATA_LITERAL_RE rather than trust an "
            "empty NOT_ASKED result"
        )
    return tuple(sorted(set(_UNCONDITIONAL_NOT_ASKED_RE.findall(match.group(1)))))


def _extract_gold_persona_product_codes(gold_test_path: Path) -> tuple[str, ...]:
    """Best-effort text scan of the 20-gold-persona test file for every
    product code that appears as an ``expected_candidates`` entry — i.e.
    every product code at least one persona positively supports.
    """
    text = gold_test_path.read_text(encoding="utf-8")
    codes: set[str] = set()
    for tuple_body in _EXPECTED_CANDIDATES_RE.findall(text):
        codes.update(_QUOTED_CODE_RE.findall(tuple_body))
    return tuple(sorted(codes))


def _rule_effective_product_ids(rule: Rule, all_product_ids: tuple[str, ...]) -> tuple[str, ...]:
    """The product_version_ids this rule actually applies to.

    ``scope: PRODUCTS`` names them explicitly. ``scope: GLOBAL`` (encoded
    as ``product_version_ids: None``) applies to EVERY product in the pack
    — that is what the real evaluator does, and an earlier draft of this
    script treated GLOBAL as "applies to nothing", which would silently
    under-report reachability the moment a pack ever adds a GLOBAL SUPPORT
    rule (none exists in the pack this script currently ships against, but
    nothing prevents a future one).
    """
    if rule.product_version_ids is None:
        return all_product_ids
    return tuple(str(pid) for pid in rule.product_version_ids)


def _rule_scoped_product_ids(rule: Rule) -> tuple[str, ...]:
    """The product_version_ids EXPLICITLY named by this rule (empty for
    GLOBAL) — used only for orphan-reference detection, which is
    meaningless for a GLOBAL rule (it names nothing to be dangling)."""
    if rule.product_version_ids is None:
        return ()
    return tuple(str(pid) for pid in rule.product_version_ids)


def _display_path(path: Path) -> str:
    """Repo-relative when possible, so the report is reproducible byte-for-byte
    across machines/worktrees instead of embedding an absolute local path."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(_REPO_ROOT))
    except ValueError:
        return str(resolved)


def build_report(
    pack_path: Path,
    *,
    fact_mapper_path: Path | None = None,
    gold_persona_test_path: Path | None = None,
) -> ReachabilityReport:
    """Load ``pack_path`` and compute the full reachability/gap report.

    Raises whatever ``load_rule_pack_payload`` raises (``OSError``,
    ``json.JSONDecodeError``, ``pydantic.ValidationError``) on a pack that
    cannot be parsed or does not validate — this script never reports on a
    pack it cannot trust the shape of. Also raises ``ValueError`` if two
    products in the pack share a ``product_code`` (this script reports per
    code, and refuses to silently conflate two distinct product versions —
    see the in-function comment) or if the fact-mapper's data literal
    can't be located (see ``_extract_not_asked_facts``).
    """
    payload: RulePackPayload = load_rule_pack_payload(pack_path)

    products_by_id: dict[str, VisaProductVersion] = {
        str(p.product_version_id): p for p in payload.products
    }
    all_product_ids = tuple(products_by_id)

    # Guard against a P2 finding from the cross-family review: reachability
    # and persona-coverage are both reported per product_code, but the
    # model only guarantees `product_version_id` uniqueness — two DIFFERENT
    # versions of the same product_code (a real, intended shape per the
    # bitemporal RulePack design) would otherwise silently collapse into
    # one row, hiding a genuine "version A reachable, version B blocked"
    # split. Fail loud instead of reporting a number that quietly means
    # something narrower than it claims.
    codes_seen: dict[str, str] = {}
    for pid, product in products_by_id.items():
        prior = codes_seen.get(product.product_code)
        if prior is not None:
            raise ValueError(
                f"{pack_path}: product_code {product.product_code!r} is shared by "
                f"product_version_id {prior!r} and {pid!r} — this script reports "
                "per product_code and cannot distinguish multiple versions of the "
                "same code without a design change; refusing to report a number "
                "that would silently conflate them"
            )
        codes_seen[product.product_code] = pid

    support_by_product: dict[str, list[str]] = {pid: [] for pid in products_by_id}
    exclude_by_product: dict[str, list[str]] = {pid: [] for pid in products_by_id}
    review_by_product: dict[str, list[str]] = {pid: [] for pid in products_by_id}
    add_score_by_product: dict[str, list[str]] = {pid: [] for pid in products_by_id}
    orphan_rules: list[OrphanRuleFinding] = []
    used_facts: set[str] = set()
    ast_mismatches: list[str] = []

    for rule in payload.rules:
        named_ids = _rule_scoped_product_ids(rule)
        dangling = tuple(pid for pid in named_ids if pid not in products_by_id)
        if dangling:
            orphan_rules.append(
                OrphanRuleFinding(rule_id=rule.rule_id, dangling_product_version_ids=dangling)
            )

        effect_type = rule.effect.type
        for pid in _rule_effective_product_ids(rule, all_product_ids):
            if pid not in products_by_id:
                continue
            if effect_type == "SUPPORT":
                support_by_product[pid].append(rule.rule_id)
            elif effect_type == "EXCLUDE":
                exclude_by_product[pid].append(rule.rule_id)
            elif effect_type == "REQUIRE_REVIEW":
                review_by_product[pid].append(rule.rule_id)
            elif effect_type == "ADD_SCORE":
                add_score_by_product[pid].append(rule.rule_id)

        # AST-derived is authoritative (see module docstring) — `required_facts`
        # is only a cross-check, never the reported figure.
        ast_facts = collect_fact_paths(rule.when)
        used_facts |= ast_facts
        rule_facts = {str(f.value) for f in rule.required_facts}
        if ast_facts != rule_facts:
            ast_mismatches.append(rule.rule_id)

    products: list[ProductReachability] = []
    for pid, product in sorted(products_by_id.items(), key=lambda kv: kv[1].product_code):
        support = tuple(support_by_product[pid])
        products.append(
            ProductReachability(
                product_code=product.product_code,
                product_version_id=pid,
                reachable=bool(support),
                support_rule_ids=support,
                exclude_rule_ids=tuple(exclude_by_product[pid]),
                require_review_rule_ids=tuple(review_by_product[pid]),
                add_score_rule_ids=tuple(add_score_by_product[pid]),
            )
        )

    reachable_codes = tuple(sorted(p.product_code for p in products if p.reachable))
    blocked_codes = tuple(sorted(p.product_code for p in products if not p.reachable))
    zero_scoped_codes = tuple(sorted(p.product_code for p in products if not p.has_any_scoped_rule))

    all_fact_paths = {str(p.value) for p in DEFAULT_FACT_REGISTRY.all_paths()}
    unused_facts = tuple(sorted(all_fact_paths - used_facts))

    fact_mapper_path = fact_mapper_path or DEFAULT_FACT_MAPPER_PATH
    gold_persona_test_path = gold_persona_test_path or DEFAULT_GOLD_PERSONA_TEST_PATH

    not_asked = _extract_not_asked_facts(fact_mapper_path)
    persona_codes = _extract_gold_persona_product_codes(gold_persona_test_path)

    pack_codes = {p.product_code for p in payload.products}
    persona_codes_absent = tuple(sorted(set(persona_codes) - pack_codes))
    positively_covered = pack_codes & set(persona_codes)
    without_positive_persona = tuple(sorted(pack_codes - positively_covered))

    return ReachabilityReport(
        pack_path=_display_path(pack_path),
        rule_pack_id=str(payload.rule_pack_id),
        sequence=payload.sequence,
        version=payload.version,
        environment=payload.environment.value
        if hasattr(payload.environment, "value")
        else str(payload.environment),
        product_count=len(payload.products),
        rule_count=len(payload.rules),
        reachable_product_codes=reachable_codes,
        blocked_product_codes=blocked_codes,
        products_with_zero_scoped_rules=zero_scoped_codes,
        unused_fact_paths=unused_facts,
        used_fact_paths=tuple(sorted(used_facts)),
        total_fact_paths=len(all_fact_paths),
        required_facts_ast_mismatches=tuple(ast_mismatches),
        not_asked_facts=not_asked,
        not_asked_facts_source=_display_path(fact_mapper_path),
        orphan_rules=tuple(orphan_rules),
        products_without_positive_persona=without_positive_persona,
        persona_corpus_product_codes=persona_codes,
        persona_corpus_codes_absent_from_pack=persona_codes_absent,
        persona_corpus_source=_display_path(gold_persona_test_path),
        products=tuple(products),
    )


def report_to_json(report: ReachabilityReport) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True)


def report_to_markdown(report: ReachabilityReport) -> str:
    lines: list[str] = []
    # This file lives under `research/**/*.md`, in scope of
    # `scripts/check_adversarial_review.py` (the R1 gate — every file there
    # must declare an `adversarial_review:` frontmatter key). This is a pure
    # machine-generated snapshot (no `sources`/`client_case`/`discovered_by`
    # claims — see the W109 scar's distinction between a generated artifact
    # and a research deliverable that merely lacks the key), so
    # `exempt-generated-artifact` is the honest declaration, not a
    # workaround: it is regenerable byte-for-byte by re-running this script
    # against the same pack file. The narrated deliverable that interprets
    # these numbers carries its own real `adversarial_review:` seat.
    lines.append("---")
    lines.append(
        "adversarial_review: exempt-generated-artifact # regenerable snapshot, not a research deliverable — see the sibling dated report"
    )
    lines.append("---")
    lines.append("")
    lines.append(f"# Reachability report — {Path(report.pack_path).name}")
    lines.append("")
    lines.append(
        f"Pack `{report.rule_pack_id}` sequence **{report.sequence}** "
        f"(version `{report.version}`, environment `{report.environment}`) — "
        f"{report.product_count} products, {report.rule_count} rules."
    )
    lines.append("")
    lines.append("## Reachability")
    lines.append("")
    lines.append(
        f"- **Reachable (has ≥1 SUPPORT rule): {len(report.reachable_product_codes)}** — "
        + ", ".join(report.reachable_product_codes)
    )
    lines.append(
        f"- **Blocked (zero SUPPORT rules): {len(report.blocked_product_codes)}** — "
        + ", ".join(report.blocked_product_codes)
    )
    if report.products_with_zero_scoped_rules:
        lines.append(
            f"- Of the blocked set, **{len(report.products_with_zero_scoped_rules)} have "
            "ZERO product-scoped rules at all** (never named by HARD_FILTER, SUPPORT, "
            "REQUIRE_REVIEW, or ADD_SCORE — only ever reachable via GLOBAL rules, if at "
            "all): " + ", ".join(report.products_with_zero_scoped_rules)
        )
    lines.append("")
    lines.append("## Fact-path coverage")
    lines.append("")
    lines.append(
        f"- {len(report.used_fact_paths)}/{report.total_fact_paths} FactPaths referenced by "
        "at least one rule."
    )
    lines.append(
        f"- **{len(report.unused_fact_paths)} FactPaths referenced by zero rules**: "
        + ", ".join(report.unused_fact_paths)
    )
    if report.required_facts_ast_mismatches:
        lines.append(
            "- ⚠️ **required_facts != collect_fact_paths(when)** for rule(s): "
            + ", ".join(report.required_facts_ast_mismatches)
            + " — the compiler's own invariant should make this impossible; treat as a bug."
        )
    lines.append("")
    lines.append("## NOT_ASKED facts (live production interview)")
    lines.append("")
    lines.append(
        f"Source: `{report.not_asked_facts_source}` — facts the interview hard-codes to "
        f"`UNKNOWN(NOT_ASKED)` unconditionally, regardless of applicant answers."
    )
    lines.append("")
    lines.append(f"- **{len(report.not_asked_facts)} facts**: " + ", ".join(report.not_asked_facts))
    overlap = sorted(set(report.not_asked_facts) & set(report.unused_fact_paths))
    if overlap:
        lines.append(
            f"- {len(overlap)} of these are ALSO referenced by zero rules in this pack "
            "(expected — an unasked fact cannot be usefully gated on): " + ", ".join(overlap)
        )
    asked_but_unused = sorted(set(report.unused_fact_paths) - set(report.not_asked_facts))
    if asked_but_unused:
        lines.append(
            f"- {len(asked_but_unused)} facts the interview DOES collect but this pack "
            "references in zero rules (collected data the pack does not yet use): "
            + ", ".join(asked_but_unused)
        )
    lines.append("")
    lines.append("## Orphan rules")
    lines.append("")
    if report.orphan_rules:
        lines.append(
            f"**{len(report.orphan_rules)} rule(s) name a product_version_id absent from "
            "this pack's product list.** This pack is schema-VALID (loadable, hence this "
            "report exists) but compilation-INVALID: `compiler.py` would collect this as "
            "an `UNKNOWN_PRODUCT_REFERENCE` error and refuse to compile/sign it."
        )
        for orphan in report.orphan_rules:
            lines.append(
                f"- `{orphan.rule_id}` -> {', '.join(orphan.dangling_product_version_ids)}"
            )
    else:
        lines.append("None — every rule's `product_version_ids` resolves to a real product.")
    lines.append("")
    lines.append("## Products without a positive persona")
    lines.append("")
    lines.append(f"Source: `{report.persona_corpus_source}` (the 20-gold-persona corpus).")
    lines.append("")
    lines.append(
        "**CAVEAT (do not read the number below as the whole story):** that corpus replays "
        "against a hand-written FIXTURE pack, never this signed pack — a known LIVE STATE gap "
        "(visaoracle skill, 2026-08-12). Its product-code vocabulary can diverge from this "
        "pack's; see the absent-codes list below."
    )
    lines.append("")
    lines.append(
        f"- Persona corpus positively supports (`expected_candidates`) "
        f"{len(report.persona_corpus_product_codes)} distinct code(s): "
        + ", ".join(report.persona_corpus_product_codes)
    )
    if report.persona_corpus_codes_absent_from_pack:
        lines.append(
            f"- **{len(report.persona_corpus_codes_absent_from_pack)} of those codes do not "
            "exist in this pack at all** (vocabulary drift between the fixture and this pack): "
            + ", ".join(report.persona_corpus_codes_absent_from_pack)
        )
    lines.append(
        f"- **{len(report.products_without_positive_persona)}/{report.product_count} products "
        "in this pack are never a persona's `expected_candidates`**: "
        + ", ".join(report.products_without_positive_persona)
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, required=True, help="Path to a RulePack source JSON.")
    parser.add_argument(
        "--fact-mapper",
        type=Path,
        default=None,
        help="Path to the frontend fact-mapper.ts (default: repo-relative standard location).",
    )
    parser.add_argument(
        "--gold-persona-test",
        type=Path,
        default=None,
        help="Path to test_evaluator_gold.py (default: repo-relative standard location).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="If set, write <pack-stem>-reachability.json and .md into this directory.",
    )
    args = parser.parse_args(argv)

    try:
        report = build_report(
            args.pack,
            fact_mapper_path=args.fact_mapper,
            gold_persona_test_path=args.gold_persona_test,
        )
    except (OSError, ValueError, ValidationError) as exc:
        print(f"error: could not build report for {args.pack}: {exc}", file=sys.stderr)
        return 1

    json_text = report_to_json(report)
    md_text = report_to_markdown(report)

    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        stem = args.pack.stem.replace(".source", "")
        (args.out_dir / f"{stem}-reachability.json").write_text(json_text, encoding="utf-8")
        (args.out_dir / f"{stem}-reachability.md").write_text(md_text, encoding="utf-8")
        print(f"wrote {args.out_dir / f'{stem}-reachability.json'}", file=sys.stderr)
        print(f"wrote {args.out_dir / f'{stem}-reachability.md'}", file=sys.stderr)
    else:
        print(md_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
