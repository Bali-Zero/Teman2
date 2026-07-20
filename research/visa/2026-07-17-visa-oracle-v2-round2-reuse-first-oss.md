---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 2 (lane: sonnet-web-grounded-reuse-first)
status: round-2 raw lane output, faithfully preserved
adversarial_review: codex
---

# Round 2 — Reuse-first OSS survey (live-verified via GitHub API, 2026-07-17)

## ADOPT

- **GoRules ZEN Engine** (github.com/gorules/zen, MIT, Rust core + Python/Node bindings, push
  2026-07-16, JDM decision graphs; hit policies ONLY first/collect; NO gap/overlap analysis; no
  third-party production users found) — saves ~25-30% of the evaluator-core build IF adopted.
  NOTE: subject to Round-3 Opus arbitration vs Codex custom evaluator (UNKNOWN tri-state + 
  COVER_ALL_DECLARED_PURPOSES are not native in ZEN).
- **@xyflow/react** (github.com/xyflow/xyflow, MIT "forever", 37.7k stars, push 2026-07-16) +
  **elkjs** (github.com/kieler/elkjs, EPL-2.0 weak copyleft, safe as unmodified dep) — the
  /visualise interactive ~110-node tree view; ~85-90% of that feature.
- **jsonschema** (Python, Draft 2020-12 reference validator) — canon-mandated.
- **react-jsonschema-form RJSF** (Apache-2.0, 15.8k stars, push 2026-07-16) — INTERNAL tooling
  only (RulePack/ApplicantFacts debug+authoring forms); never the client wizard.
- **GoRules JDM Editor** (github.com/gorules/jdm-editor, MIT, React) — optional visual rule
  authoring.

## IMITATE (patterns, not deps)

- alphagov/smart-answers (MIT, Ruby, push 2026-07-16, live on GOV.UK): Flow/Question/Outcome node
  model + answer-summary-with-edit; frontend walks the same graph the evaluator evaluates.
- alphagov/govuk-frontend (MIT): accessibility mechanics (mandatory back-link, one-question-per-page
  markup, error-summary linking).
- red6/dmn-check (Apache-2.0, push 2026-07-16): gap/overlap/missing-rule detection ALGORITHM — port
  to Python over our Rule AST.
- OpenFisca/openfisca-core (AGPL-3.0 — ADOPTION BLOCKED by network copyleft) + PolicyEngine (AGPL):
  time-versioned parameter trees; our bitemporal model is a superset (they version legal validity
  only).
- MyFriendBen (MPL-2.0, Django+React, push 2026-07-16, live in 3 US states): permissive intake app
  calling isolated AGPL calc engine over HTTP — the clean AGPL-consumption pattern if ever needed.
- Apache KIE/Drools DMN (Apache-2.0, alive): full DMN 1.5 hit-policy semantics reference; JVM
  runtime disproportionate (confirms Round-1 "Defer").
- OPA/Rego: confirmed limited-use (boolean gates only; wrong shape for ranked multi-candidate
  output).

## SKIP (verified reasons)

- OpenFisca/PolicyEngine/openfisca-aotearoa as deps (AGPL); Blawx (MIT but stale 20mo, Prolog); 18F
  eligibility-rules-service (ARCHIVED, docs-only, zero code); CMSgov/BenefitAssist (dead 2018); Code
  for America (no extractable general engine); EU Your Europe (confirmed: no OSS wizard exists);
  Benefit Kitchen (proprietary); json-rules-engine (JS-only), durable_rules (stale 1y, 206 issues),
  venmo/business-rules (dead 2y); XState/xstate-wizards/react-multistep (redundant vs
  @balizero/core AppWizard); **Stepperize (1,586 stars but NO LICENSE file/field — legally
  unusable)**; uniforms (redundant); d3-hierarchy (redundant vs xyflow+elkjs); Mermaid for the live
  tree (caps ~30-40 nodes; fine for small doc diagrams only).

## Net estimate

Adopting the top candidates saves ~30-40% of the combined engine+wizard build, concentrated in
evaluator core + /visualise. Frontend wizard: ~0% external reuse (already covered by
@balizero/core). Regulatory-specific parts (bitemporal signed RulePacks, four-eyes, provenance
chains, visa-tuned gap/overlap) remain custom by necessity.

## Adversarial review

**Seat:** codex (GPT-5.6-terra-high adversarial grading, 2026-07-17)
**Verdict:** SURVIVES-WITH-CAVEATS

Challenged points:
- "Stepperize has no licence" is contested — the published npm package `@stepperize/react` declares MIT
  even though the repo's LICENSE file was missing at review time; recheck before any adoption, stays SKIP
  for now.
- "Adopt ZEN" was pending arbitration at the time this lane was written and was superseded by the round-3
  verdict (custom evaluator; ZEN restricted to authoring/visual tooling only).
- The 25-40% savings figure and "legally safe" conclusions have no measured baseline behind them.

This section is an appended R1-gate artifact (generator≠grader); the file body above is preserved
verbatim as the faithful record of this panel lane's original output.
