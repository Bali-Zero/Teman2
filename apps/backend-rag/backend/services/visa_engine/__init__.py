"""Visa Oracle v2 rule engine — the only recommendation authority (spec §0.1).

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` and ``docs/plans/2026-07-17-visa-oracle-v2/00-product-
design.md``. Qdrant and LLMs may explain a persisted decision; they never
determine eligibility, candidates, rank, or price (spec §0 binding decision
#2). This package is greenfield and unused by any live surface until the
strangler adapters land in PR6 — it does not touch ``match_tree.py``,
``visa_oracle_service.py``, or any router.

PR1 delivers: typed contracts (``models.py``), the condition AST
(``ast.py``), the fact catalog (``fact_registry.py``), static RulePack
validation (``compiler.py``), JSON Schema export (``schema_export.py``), and
the error taxonomy (``errors.py``). Signing/verification (``bundle.py``),
the evaluator (``evaluator.py``, ``trace.py``), pricing/catalog/clock,
persistence (``repository.py``), and the v1 strangler adapters
(``compat.py``, ``service.py``) are later PRs — see each module's docstring
for exactly what it defers and why.

# PR-scope map (round 3, Codex round-2 re-review finding 3 residue, R3-F)

Every class/function spec §1's module-layout snippet names, and exactly
which PR lands it — so a reviewer sees a plan, not an unexplained gap. Names
present in this package today are marked **done**; every deferral below is
already documented at its own future home's call site (``compiler.py``'s
``compile_rule_pack`` docstring, ``models.py``'s module docstring,
``fact_registry.py``'s module docstring) — this table just collects them in
one place.

- **enums.py** — done (PR1, all of it: ``TruthValue``, ``DecisionState``,
  ``RuleStage``, ``EngineMode``, ``EngineSurface``, and every closed
  vocabulary ``models.py``/``ast.py``/``fact_registry.py`` import from it).
- **models.py** — done (PR1) for ``RulePack``, ``Rule``,
  ``VisaProductVersion``, ``ApplicantFacts``, ``Decision``, ``PriceQuote``,
  ``SourceRecord``, ``CandidateDecision`` (``Candidate`` alias — see that
  module's docstring for the §1/§2 naming resolution). **Deferred to
  PR3-PR4** (runtime evaluation + consent — orchestrator triage, verbatim):
  ``ConsentEvent``, ``EvaluationContext`` — neither is referenced by any PR1
  module.
- **fact_registry.py** — done (PR1) for ``FactSpec``/``FactRegistry.spec()``/
  ``FactRegistry.missing_paths()`` (the static catalog). **Deferred to PR3**
  (needs the evaluator to define what "resolving" a fact means
  operationally): ``FactSnapshot``, ``FactRegistry.derive()``,
  ``canonical_fact_payload()``.
- **ast.py** — done (PR1) for the 16 ``Condition`` variants, the
  ``Condition`` discriminated union, and the tree-traversal helpers
  (``iter_nodes``, ``collect_fact_paths``, ``collect_leaf_operators``,
  ``validate_ast_limits``). **Deferred to PR3-PR4**: ``ConditionResult``,
  ``evaluate_condition()`` (needs ``FactSnapshot`` from ``fact_registry.py``,
  itself PR3).
- **bundle.py** — done (PR2b, 2026-07-18 — ported from a discarded earlier
  "B" API draft to this package's actual "A" models.py, see that module's
  own docstring for the adaptation notes): ``TrustedSigningKey``,
  ``TrustStore``, ``StaticTrustStore`` (+ ``from_env``), ``VerifiedRulePack``,
  ``canonicalize_json()``, ``verify_rule_pack()`` (RFC 8785 JCS
  canonicalization of the raw wire envelope, Ed25519 verify-on-load BEFORE
  any Pydantic parsing, UNSIGNED-DEV firebreak fail-closed by default),
  ``validate_activation()`` (pure anti-rollback gate: sequence, hash-chain,
  environment, engine-version). **Deliberately NOT included** (PR2's own
  mandate is signature/trust only): a ``compile_verified_rule_pack`` seam in
  front of ``compiler.py`` — this package's ``compile_rule_pack`` returns a
  ``CompilationReport`` (validate-and-report), not the discarded draft's
  ``CompiledRulePack`` (evaluate-ready form); wiring a seam between the two
  would mean inventing a new compiler concept, which is PR3 territory (see
  ``compiler.py``'s own "done (PR1)" entry below for what it already covers).
  No key generation/registration script exists or will (FIREBREAK — the
  Ed25519 signing ceremony is the operator's, offline, never autonomous
  code).
- **compiler.py** — done (PR1) for ``CompilationError``,
  ``CompilationReport``, and ``compile_rule_pack(pack: RulePack, *,
  fact_registry) -> CompilationReport`` — spec's own signature takes a
  ``bundle.VerifiedRulePack`` (PR2 concept); PR1 substitutes a plain
  ``models.RulePack`` since PR1 has no ``bundle.py`` yet (see that
  function's own docstring). ``CompilationReport``, not spec's
  ``CompiledRulePack``, is PR1's return type by design — PR1's job is
  validate-and-report, not compile-to-evaluator-runtime-form.
  **Deferred to PR3** (needs the evaluator to define what "compiled" means
  operationally): ``CompiledRule``, ``CompiledProduct``, ``CompiledRulePack``,
  and the ``VerifiedRulePack``-taking ``compile_rule_pack`` overload/wrapper.
- **evaluator.py**, **trace.py** — not started. **Deferred to PR3**: the
  entire evaluator (``ProductProofStatus``, ``ProductProof``,
  ``DecisionDraft``, ``evaluate()``) and deterministic trace-building
  (``TraceNode``, ``EvaluationTrace``, ``TraceBuilder``, ``trace_sha256()``).
- **pricing.py**, **catalog.py**, **clock.py**, **repository.py**,
  **crypto.py**, **retention.py**, **flags.py** — not started. **Deferred to
  PR4+** (persistence/pricing/clock/consent-adjacent infrastructure; exact PR
  boundary not yet numbered — these depend on the evaluator existing first).
- **consent.py** — not started. **Deferred to PR3-PR4** alongside
  ``ConsentEvent``/``EvaluationContext`` above.
- **compat.py**, **service.py** — not started. **Deferred to PR6** (the
  strangler adapters this module's own opening paragraph already names —
  ``VisaDecisionService``, the v1-request-to-``ApplicantFacts`` translators,
  and the v1-response-shape translators).
- **schema_export.py**, **errors.py** — done (PR1), both match spec §1's
  signature exactly (``export_schemas(output_dir: Path) -> None``; the
  five-exception taxonomy under ``VisaEngineError``).
"""

from __future__ import annotations
