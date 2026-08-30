---
date: 2026-08-28
domain: operations
part: B6 domain-decision-engines
scope: visa_oracle/visa_engine/visa_unified/visa_check/garuda_flow/pricing/prime/tools services, decision routers, kbli-navigator, signed rule pack, gold corpus
sources:
  - https://openfisca.org/doc/index.html
  - https://discuss.digital.govt.nz/blog/turning-the-rules-of-government-into-code-using-openfisca/
  - https://www.policyengine.org/us/research/policyengine-atlanta-fed-mou-prd
  - https://www.policyengine.org/us/taxsim
  - https://github.com/PolicyEngine/policyengine-us
  - https://arxiv.org/abs/2103.03198
  - https://docs.camunda.io/docs/components/best-practices/modeling/choosing-the-dmn-hit-policy/
  - https://www.aserto.com/blog/secure-software-supply-chain-opa-policies
  - https://18f.gsa.gov/2018/10/16/exploring-a-new-way-to-make-eligibility-rules-easier-to-implement/
  - https://github.com/18F/eligibility-rules-service/blob/master/README.md
  - https://beeckcenter.georgetown.edu/wp-content/uploads/2022/02/Benefit-Eligibility-Rules.pdf
  - https://gds.blog.gov.uk/2012/02/16/smart-answers-are-smart/
  - https://www.gov.uk/check-uk-visa
  - https://www.boundless.com/
  - https://bryter.com/no-code-platform/
  - https://www.neotalogic.com/
  - https://developers.redhat.com/articles/2021/06/24/automating-rule-based-services-java-and-kogito
  - https://github.com/github/scientist
status: DONE
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B6 — Domain Decision Engines (Beyond-SOTA lane)

## Anatomy (as measured)

All paths relative to repo root; measured at pinned `origin/main` `11a3c89a2e`.

### Engine inventory — five generations coexist

1. **`visa_engine` (Visa Oracle v2)** — the flagship: **20,423 lines across 23 Python modules** plus JSON Schema contracts (`apps/backend-rag/backend/services/visa_engine/contracts/contract.schema.json` — 4,759 lines). Core pieces: tri-state condition AST (`ast.py`, 707 ln), pack compiler (`compiler.py`, 1,471 ln), pure evaluator (`evaluator.py`, 1,453 ln), HTTP-path orchestration (`evaluate_path.py`, 2,000 ln), Ed25519 signing/verification (`bundle.py`, 1,009 ln), HMAC identity (`crypto.py`, 415 ln), typed fact catalog (`fact_registry.py`, 891 ln), wire models (`models.py`, 1,502 ln), plus shadow evaluation (`shadow.py` 744 + `shadow_evidence.py` 634), decision sealing (`decision_seal.py`), claim ledger, idempotency, retention, and privacy-policy modules.
2. **`garuda_flow`** — the GARUDA VOA product engine: a pure, no-I/O eligibility screen encoding SOP-v0-GARUDA-B1 §1 (`garuda_flow/eligibility.py:1-14`) that collects **every** failing reason instead of short-circuiting (`eligibility.py:16-18`), a wire-safe verdict orchestration seam (`public_api.py:1-6`), and an exact-key PricingTool bridge where "prices are never literals" (`garuda_flow/pricing.py:1-5`; `_ISSUANCE_PRICE_KEY = "B1 Visa on Arrival (VOA)"` at `pricing.py:21`).
3. **`visa_check`** — the deterministic Visa Match wizard: additive, documented scoring rubric (base +0.50, budget_fit +0.25, … multi_entry −0.30) printed verbatim in `visa_check/match_tree.py:17-25`.
4. **`visa_oracle`** — the legacy recommender: keyword/category scoring over PricingService data, "no LLM calls" (`visa_oracle/visa_oracle_service.py:1-6`), purpose→category maps and keyword lists hardcoded (`visa_oracle_service.py:24-48`).
5. **`visa_unified/bridge.py`** — a facade that injects a completed wizard run into the Oracle RAG chat as ground truth (30-day TTL, `bridge.py:1-18`).

Supporting engines: `pricing/pricing_service.py` (official 2026 JSON catalog, "NO AI GENERATION", `pricing_service.py:1-4`), `pricing/dynamic_pricing_service.py` (multi-collection scenario cost aggregator, `dynamic_pricing_service.py:1-17`), `prime/` (geo/property/tax/nexus), `tools/` (KG tool + tool definitions). KBLI side: router `kbli_notebook.py` (BPS 2025 + PP 28/2025 integration, Haiku-backed chat per `apps/backend-rag/CLAUDE.md` model table), and `apps/kbli-navigator` (63,137 lines of TS/TSX; `data/kbli-2025.json` holds **1,559 codes** — measured `data` list length).

### Rule-pack format, signing, and the DB as the only truth

The pack is a single JSON document: `rule_pack_id`, monotonic `sequence`, `version` (e.g. `2026.8.23`), engine version bounds (`engine_min_version`/`engine_max_version`), `jurisdiction`, `decision_domain`, `hit_policy`, `valid_period`, a **hash chain** (`previous_payload_sha256`, `rollback_of_payload_sha256`), `products`, `rules`, and `source_records` (regulatory provenance). Measured on `contracts/packs/rulepack-prod-013.source.json`: **111 rules, 38 products, 258 KB**. Each rule carries `rule_id, stage, scope, priority, valid_period, when, effect, on_unknown, required_facts, source_refs, explanation_key, safety_critical, product_version_ids`. Fourteen production pack versions live on disk (`contracts/packs/rulepack-prod-001..014`, signed + source pairs).

Signing is Ed25519 over an RFC 8785 (JCS) canonicalization (`bundle.py`; vectors tested in `test_bundle_rfc8785_vectors.py`). Storage is an **append-only `visa_rule_packs` table whose `visa_rule_packs_immutable` trigger rejects any UPDATE/DELETE** (`visa_engine/repository.py:24-27`); activation goes through the SECURITY DEFINER function `public.visa_activate_rule_pack` (`repository.py:37-38`), and the read path is the bitemporal `load_active_rule_pack` (`repository.py:185`), which reconstructs the exact signed envelope for `verify_rule_pack` and never trusts payload columns (`repository.py:16-21`). This **confirms the live-context claim: the ACTIVE pack is read from the DB, not from docs** — the on-disk `.source.json` files are authoring artifacts, not runtime truth. DDL series: migrations `250..268` (19 files: core, activation writer + hardening, write substrate, shadow evidence, traffic source, idempotency, response HMAC, retention policy/evidence/binding, trace integrity — `backend/db/migrations_v2/`).

### Fact model and the askability boundary

`fact_registry.py` catalogs **44 collected + 4 derived fact paths** (`fact_registry.py:5-6`) with value kind, allowed values, PII class, and a commercial/legal split the compiler enforces ("no `commercial.*` fact in a legal-stage rule", `fact_registry.py:14-16`). The compiler also enforces `required_facts == collect_fact_paths(when)` (`compiler.py:456`) and fact-path-typed literals. Derived facts are grounded against the *frontend's* actual option vocabulary — `_VISIT_CLASS_STATUS_CODES` documents the exact 8 option keys `apps/mouth`'s `current_status_code` question can send (`fact_registry.py:57-85`), plus the synthesized `NO_STAY_PERMIT` sentinel from the offshore-reachability fix PR #4727 (`fact_registry.py:87-108`). The askability doctrine ("a fact that is ASKABLE arms every rule that uses it") is real but lives as *manual grounding discipline in comments plus frontend `fact-mapper.ts`* — I found **no compiler invariant** that mechanically proves every `required_facts` path is reachable from the live interview (grep for askable/interview-coverage in `compiler.py`: absent).

### Evaluation flow

`evaluator.evaluate()` is a **pure function** — no I/O, no wall clock, "same inputs must produce a byte-identical Decision" (`evaluator.py:13-15`). Tri-state semantics with a frozen state-precedence table; the "UNKNOWN never increases eligibility" invariant is enforced and was *adversarially audited*: the module docstring records gate round 1 (2026-07-19) where two cross-family seats (Codex GPT-5.6-sol + Kimi K3) independently found P0s — inverted purpose-coverage UNKNOWN handling, inverted global state precedence, a refuted "folded GLOBAL review pre-pass" equivalence claim with three concrete counterexamples — all fixed and documented in place (`evaluator.py:17-90`). Decision identity is an HMAC-SHA256 facts fingerprint from an operator-provisioned key store with kid rotation, validity windows, revocation, and a 256-bit key floor (`crypto.py:21-31, 62-64`); final public decisions are sealed with an HMAC over the RFC 8785 canonical payload including `trace_sha256` (`decision_seal.py:28-37`). The HTTP shell (`routers/visa_oracle_evaluate.py:1-60`) carries red-team-driven abuse controls: incremental 32 KB body cap via `request.stream()`, strict duplicate-key/non-finite JSON rejection, a 30/min dedicated rate bucket, a required `traffic_source` label with a constant-time-compared driver token for synthetic/gold-replay traffic, and a separate canary-mode token (SHADOW/ENFORCE) so replay credentials never confer mode authority.

### Gold corpus and shadow

The gold harness (`backend/tests/services/visa_engine/gold_harness/`) replays **23 gold personas × 11 products = 253 proof assertions** against the real evaluator + compiler, asserting proof state, reason codes, covered/missing purposes and missing facts exactly, with an explicit never-raises sweep over the deliberately-contradictory persona #20 (`test_gold_replay.py:1-36, 63`); persona files range from `01_tourist_simple.json` to `23_second_home_deposit_wrong_bank.json`. A metamorphic-properties suite sits beside it (`test_metamorphic_properties.py`), and `replay_report.py` emits an evidence artifact from the same single evaluation run. The whole `visa_engine` test tree is **35,061 lines across ~57 files**, including determinism, state-precedence, truth-table, RFC 8785 vector, pack-chain, retention-FK and per-sequence pack-witness suites. Shadow mode (`shadow.py:1-23`) re-evaluates real `/api/visa/match` traffic fire-and-forget into `visa_decisions` under a default-OFF flag, never logging raw applicant facts, fail-closing on missing identity material.

### VOA funnel (live path)

`routers/garuda_voa_public.py` implements exactly three contract-frozen operations of `products/garuda-voa/contracts/openapi.yaml`; it was wired into the app 2026-08-25 (`20ef324d1`) — the docstring honestly preserves its own stale "Not wired" history (`garuda_voa_public.py:16-23`). `GARUDA_PUBLIC_ENABLED` is read per-request from the environment so the flag flips without restart (`garuda_voa_public.py:25-30`). Persistence is fail-closed by construction: `UnconfiguredCheckStore` returns `PERSISTENCE_POLICY_UNAVAILABLE` (503) until a retention-policy row is signed (`public_api.py:9-23`). The single `price_idr` comes from exact catalogue keys through PricingService with freshness checks (`garuda_flow/pricing.py`). This is code-consistent with the live-context claim (prod 2026-08-28: anonymous visitor → 201 `verdict:ACCEPT`, single `price_idr`); the prod observation itself is outside this read-only lane (unverified here; verified by the 2026-08-28 session).

## Honest state vs. SOTA

**Genuinely good — at or beyond commercial practice:**

- **Policy-as-code with cryptographic provenance**: Ed25519-signed, RFC 8785-canonicalized, hash-chained, append-only, bitemporally activated rule packs with SECURITY DEFINER activation are *stronger* than what typical Camunda DMN or Drools deployments ship (they version rules; they do not sign them, chain them, or make the store append-only by trigger).
- **Determinism as a contract**: a pure evaluator with byte-identical output, sealed decisions bound to a trace hash, and idempotency binding is regulator-grade auditability.
- **Tri-state semantics done seriously**: per-rule `on_unknown`, "UNKNOWN never increases eligibility", fewest-missing-facts selection — the hard problem of eligibility engines, solved with an adversarial audit trail written into the module itself.
- **Gold replay + metamorphic tests as merge gates**, with a dedicated authenticated replay-driver credential for labeling corpus traffic against prod.

**Theater / broken / dead:**

- **Five generations of engine coexist and disagree by construction.** `visa_oracle_service.py` (keyword scoring), `visa_check/match_tree.py` (additive rubric), and `visa_engine` (signed rule packs) answer overlapping questions from three different truth models; only the last is signed and audited. Two paths green on their own tests can answer the same applicant differently — a scar class the fleet has already recorded.
- **Contract clauses with no implementation**: the three truth-freshness gates (`x-truth-freshness-max-age-days`) in the VOA openapi.yaml "have no implementation anywhere in `garuda_flow` today" — the router says so itself (`garuda_voa_public.py:11-14`). Honest, but a live contract promise the engine does not keep.
- **KBLI has no decision engine at all**: `apps/kbli-navigator/data/gold/` contains a README of *voice guidelines*, not a gold corpus; KBLI eligibility (foreign ownership, risk tier, capital floors) is answered by RAG/LLM chat (`kbli_notebook.py` + Haiku), i.e. the same class of question the visa side deliberately stopped trusting an LLM with.
- **Askability is discipline, not an invariant**: nothing in the compiler fails a pack whose `required_facts` include a path the live interview can never produce; the grounding lives in comments and in `apps/mouth`'s `fact-mapper.ts`, split across two surfaces (`fact_registry.py:57-108`).
- **Pack authoring is raw JSON by hand** (258 KB per pack): no authoring DSL, no semantic diff-review tooling, no simulation UI; the schema and the per-sequence witness tests are the only guardrails.

## Deep research: the world's best

**OpenFisca (France, NZ, AU, CA — government rules-as-code)**. The engineering core is a strict split between *formulas* (Python-subset DSL) and *time-varying parameters*, so a legislated threshold changes by adding a dated parameter value, not by editing code; *reforms* are first-class overlays applied to a baseline system so a proposed change can be simulated and diffed against the status quo before it is law; tests are a **declarative YAML corpus** run against the engine; the web API serves both computations and the legislation's parameters themselves ([OpenFisca docs](https://openfisca.org/doc/index.html); [NZ government experience](https://discuss.digital.govt.nz/blog/turning-the-rules-of-government-into-code-using-openfisca/)). The transferable pattern: **counterfactual evaluation is a product feature of the engine**, not an ad-hoc script.

**PolicyEngine (US/UK, built on OpenFisca)**. Its distinguishing engineering practice is **multi-model validation**: it built an open-source emulator of NBER's TAXSIM and runs representative household samples through both engines, diffing results ([TAXSIM partnership](https://www.policyengine.org/us/taxsim)); it signed an MOU with the Atlanta Fed to validate against the Policy Rules Database covering SNAP, Medicaid, vouchers and credits ([announcement](https://www.policyengine.org/us/research/policyengine-atlanta-fed-mou-prd); [policyengine-us](https://github.com/PolicyEngine/policyengine-us)). The pattern: a gold corpus is necessary but *internal*; SOTA validation is **agreement with an independent implementation you do not control**.

**Catala (INRIA — a programming language for the law)**. Literate programming where the statute text is interleaved with the code that formalizes it; *default logic* (general rule + exceptions) mirrors how statutes are actually written, instead of encoding exceptions as priority hacks; the compiler's core passes are proven correct in F*, and formalizing §121 of the US tax code uncovered a bug in the official implementation ([Catala paper, arXiv:2103.03198](https://arxiv.org/abs/2103.03198)). The pattern: **keep the legal text adjacent to the rule and make exception structure native**, so a lawyer can review the pair.

**Camunda DMN / Drools-Kogito (industrial BRMS)**. DMN standardizes *hit policies* (UNIQUE, FIRST, COLLECT…) and treats the choice as a readability/maintainability decision reviewable by domain experts; decision requirements diagrams decompose multi-table decisions ([Camunda hit-policy best practices](https://docs.camunda.io/docs/components/best-practices/modeling/choosing-the-dmn-hit-policy/)). Kogito compiles rule units into an executable model at build time and its testing culture is scenario-based: one business case per test, boundary values, overlapping-rule matches asserted explicitly ([Red Hat Kogito article](https://developers.redhat.com/articles/2021/06/24/automating-rule-based-services-java-and-kogito)). Nuzantara's compiler + gold personas already match this; what DMN adds is an **authoring representation a non-engineer can read**.

**OPA/Rego + Open Policy Containers + Sigstore (policy supply chain)**. The reference pattern for shipping policy: build policy bundles as **OCI artifacts**, tag/version them in a registry, sign with cosign (Sigstore: keyless signatures bound to an OIDC identity, recorded in an **append-only transparency log** with inclusion proofs), and have the engine pull only verified bundles ([Aserto: secure supply chain for OPA policies](https://www.aserto.com/blog/secure-software-supply-chain-opa-policies)). Nuzantara's Ed25519 + append-only table equals or beats the storage half; the transparency-log half (public, third-party-verifiable) is the part nobody in the small-firm legal-tech space does — a genuine beyond-SOTA opening.

**18F Eligibility APIs + Beeck Center (US government eligibility)**. 18F prototyped federal SNAP eligibility as a **central API states consume**, so a policy change propagates to every consumer at once; their hardest-won lesson is explicitly anti-BRMS: "don't assume you need a separate business rules engine product — rules can be implemented more easily… directly in code using a general purpose programming language" with a cross-functional team ([18F blog](https://18f.gsa.gov/2018/10/16/exploring-a-new-way-to-make-eligibility-rules-easier-to-implement/); [eligibility-rules-service README](https://github.com/18F/eligibility-rules-service/blob/master/README.md); [Beeck Center report](https://beeckcenter.georgetown.edu/wp-content/uploads/2022/02/Benefit-Eligibility-Rules.pdf)). Nuzantara's choice — plain typed Python with a compiler, no Drools — is validated by the people who tried both.

**GOV.UK Smart Answers ("Check if you need a UK visa")**. A decision tree rendered as a minimal-question flow, where **the answer trail is encoded in the URL** (`gov.uk/check-uk-visa/y/stateless-or-refugee/tourism/no`) — every outcome is addressable, shareable, cacheable, and the whole state machine is enumerable for regression sweeps ([GDS blog](https://gds.blog.gov.uk/2012/02/16/smart-answers-are-smart/); [live tool](https://www.gov.uk/check-uk-visa)). Nuzantara's mouth interview has no equivalent enumerable/addressable outcome space.

**Visa-tech commercial (Boundless; BRYTER/Neota for legal no-code)**. Boundless's shape: eligibility quiz → answers become complete government forms + a personalized document checklist → independent attorney review as the productized human failsafe ([boundless.com](https://www.boundless.com/)). BRYTER and Neota sell lawyers a **no-code authoring surface** for decision trees with risk scoring, full action logging and human-escalation governance ([BRYTER](https://bryter.com/no-code-platform/); [Neota](https://www.neotalogic.com/)). The commercial lesson: the engine's decision is the *top of a fulfillment funnel*, and the authoring surface for the domain expert is the product bottleneck.

**GitHub Scientist (shadow experiments on critical paths)**. Control vs candidate run on real traffic, mismatches published as metrics, promotion only when mismatch rate converges to zero ([github/scientist](https://github.com/github/scientist)). Nuzantara's `shadow.py` *is* this pattern applied to a decision engine — already implemented; what is missing is the Scientist discipline of **mismatch metrics as the explicit SHADOW→ENFORCE promotion gate**.

## Gap table

| Dimension | Nuzantara today (measured) | Sector SOTA | Gap |
|---|---|---|---|
| Rule representation | Typed JSON pack, condition AST, tri-state, per-rule `on_unknown` (`compiler.py`, `ast.py`) | DMN tables (Camunda), default logic (Catala), Rego | **At/above** on semantics; below on expert readability |
| Provenance & signing | Ed25519 + RFC 8785, hash chain, append-only table, SECURITY DEFINER activation (`repository.py:24-38`) | OCI + cosign + Sigstore transparency log (OPA world) | At SOTA privately; **no public transparency log** |
| Temporal model | Bitemporal activation + `valid_period` per rule/product | OpenFisca dated parameters + reform overlays | **No counterfactual/reform simulation** before signing |
| Fact model | 44+4 typed paths, PII class, commercial/legal split (`fact_registry.py`) | OpenFisca variables/entities | At SOTA; askability not machine-enforced |
| Testing | 23 personas × 11 products gold replay + metamorphic + witness suites (35k test lines) | PolicyEngine cross-engine validation vs TAXSIM/Atlanta Fed | Internal corpus strong; **no independent-implementation cross-check** |
| Rollout | Shadow mode + canary tokens (`shadow.py`, evaluate router) | Scientist mismatch-metric promotion gates | Shadow exists; **no quantified promotion criterion** |
| Explanation | `explanation_key`, `source_refs`, sealed trace | Catala statute-adjacent literate rules; GOV.UK addressable outcomes | Citations exist; **statute text not adjacent; outcomes not addressable** |
| Pricing | Exact-key catalog, fail-closed, freshness-checked (`garuda_flow/pricing.py`) | Commercial quote engines | At SOTA for scope |
| KBLI domain | RAG/LLM chat only; no rules, no gold corpus (`kbli_notebook.py`; empty `data/gold/`) | Same engine substrate the visa side already has | **Whole domain unengined** |
| Engine consolidation | 5 engines coexist (visa_oracle, visa_check, visa_unified, garuda_flow, visa_engine) | One decision authority per domain (18F central API) | **Duplication with divergent answers** |
| Contract honesty | Truth-freshness gates declared in openapi.yaml, unimplemented (`garuda_voa_public.py:11-14`) | Contract tests enforce declared gates | Declared ≠ enforced |

## Recommendations — reach SOTA

1. **P0 — Make askability a compiler/CI invariant.** Export the set of fact paths the live interview can actually produce (from `apps/mouth`'s `fact-mapper.ts`, as a generated JSON artifact committed beside the engine contracts) and add a compiler/CI check: a pack fails if any rule's `required_facts` contains a path neither askable nor derivable. *Acceptance (falsifiable): a CI test that goes red when a synthetic pack references a never-askable fact, green on the active pack; the artifact regenerates in CI so frontend drift breaks the build, not the product.*
2. **P0 — One decision authority per question.** Fence the legacy engines: every router that returns an eligibility *verdict* must source it from `visa_engine`/`garuda_flow`; `visa_oracle_service` and `visa_check` either route through the engine or are relabeled as non-authoritative "suggestions" in their response envelopes. *Acceptance: an allowlist test enumerating which routers may emit `verdict`/`recommended_visa` fields and from which service, red if a new surface bypasses it; zero production surfaces returning engine-shaped verdicts computed outside the two engines.*
3. **P1 — Implement the declared truth-freshness gates.** The `x-truth-freshness-max-age-days` clauses in the VOA contract get a real implementation in `garuda_flow` (the freshness machinery already exists for pricing — `freshness.py`); stale truth degrades the response per contract instead of silently serving. *Acceptance: a contract test that reads the openapi.yaml gate values and proves the API returns the degraded/503 shape when a truth source's age exceeds them; removing the implementation turns the test red.*
4. **P1 — Pack-diff replay as a signing precondition (OpenFisca "reforms", scaled down).** Before a pack N+1 is signed, replay the full gold corpus plus the recent real (pseudonymized-fingerprint) fact snapshots through pack N and N+1 and emit a verdict-diff artifact; every flip must be named in the pack's changelog. *Acceptance: every `rulepack-prod-*.signed.json` from the next sequence onward has a committed replay-diff artifact; a CI check refuses a signed pack without one; zero undocumented verdict flips per sequence.*
5. **P1 — Give KBLI the substrate it already owns.** The pack format has a `decision_domain` field (measured in prod-013 top keys); encode the top ~50 client-relevant KBLI codes' foreign-ownership/risk/capital rules as a signed KBLI pack on the same engine, with its own gold personas; the LLM narrates the engine's verdict instead of generating it. *Acceptance: a KBLI gold harness ≥15 personas × covered codes green in CI; for covered codes, `chat_kbli` responses carry engine `source_refs` and the engine verdict, and an eval shows 0 contradictions between chat answer and engine verdict on the gold set.*
6. **P2 — Human-readable pack review surface.** Generate, from any two pack sources, a semantic diff (rules added/removed/changed, per-rule statute refs, affected products) as markdown for PR review — the DMN-table readability benefit without adopting a BRMS (18F's anti-BRMS lesson says stay in code). *Acceptance: the artifact is generated in CI on any `contracts/packs/**` change; a reviewer can name every changed rule without opening the JSON.*

## Recommendations — beyond SOTA

1. **P1 — Public transparency log for packs (Sigstore pattern, self-hosted scale).** Publish the pack hash chain (sequence, payload sha256, activation timestamp — no rule content required) to an external, independently-writable log (a dedicated public git repo is enough at this scale). Decision envelopes already carry pack identity; a client or auditor can then verify a decision was made under a publicly-logged pack. Nobody in small-firm legal-tech does this. *Acceptance: every activated pack's hash appears in the external log before first production decision; a probe cross-checks DB activations against the log daily and pages on divergence.*
2. **P1 — Mismatch-metric promotion gates for shadow (Scientist discipline).** Define the SHADOW→ENFORCE criterion numerically: N real evaluations, mismatch rate vs the legacy path below X%, every residual mismatch triaged to a named cause. *Acceptance: the promotion PR must link a generated mismatch report; flipping ENFORCE without one fails a CI policy check.*
3. **P2 — Cross-family independent re-implementation audit (PolicyEngine pattern, agent-fleet sized).** Quarterly: a different model family (Codex or Kimi seat) re-implements a sampled rule subset *from the cited statute text alone*, blind to the pack; run both over the gold corpus and diff. This is PolicyEngine-vs-TAXSIM built from the fleet the organism already pays for. *Acceptance: a quarterly report with agreement rate and a triaged divergence list; each divergence closes as pack bug, statute ambiguity (→ HUMAN_REVIEW rule), or audit-implementation error.*
4. **P2 — Statute-adjacent literate packs (Catala pattern).** Extend `source_records` to carry the verbatim Pasal text for every `safety_critical` rule and render rule-vs-statute side-by-side pages for review; the refuter seat checks the pair, not just the rule. *Acceptance: 100% of `safety_critical` rules in the active pack render adjacent statute text; the pack compiler warns on a safety-critical rule whose source record lacks verbatim text.*
5. **P2 — Addressable outcome trails (GOV.UK pattern).** Encode the interview answer trail into a canonical, shareable outcome URL/token; nightly, enumerate all reachable interview paths and replay them, diffing the outcome distribution against the previous night. Turns the whole funnel into an enumerable regression surface and gives marketing shareable, pre-answered landing pages. *Acceptance: the nightly sweep reports path count + verdict distribution; an unexplained day-over-day flip pages.*

## §Meta-pattern

The organism treats **decisions as artifacts** — signed, sealed, hash-chained, replayable — and on the one engine that got the full cathedral (`visa_engine`) it is genuinely past commercial SOTA. But the strength is distributed like a spotlight, not like daylight: four sibling engines and the entire KBLI domain still answer eligibility questions with keyword scores or an LLM, and two load-bearing doctrines (askability; truth-freshness) exist as **prose without an enforcing mechanism**. This is the same meta-disease the fleet has already named elsewhere: *the artifact written/armed/announced is taken to be the thing in force*. Every "reach SOTA" item above is one move — take a rule that today lives as a comment, a contract clause, or a memory line, and give it a red/green mechanical form (compiler invariant, contract test, CI artifact gate). The "beyond SOTA" items are the same move pointed outward: make the enforcement *publicly verifiable* (transparency log, independent re-implementation), which is what turns audit-grade engineering into a trust asset a one-man agency can sell.

## §Solo-operatore

Decisions only Zero can take (business, spend, risk — Legge 5):

1. **Retire or demote the legacy recommenders** (`visa_oracle_service`, `visa_check`): changes what public surfaces answer today; product call, not an engineering one.
2. **KBLI pack investment**: encoding ~50 codes as signed rules is curation labor with real opportunity cost against visa work; only Zero can rank the two revenue lanes.
3. **Public transparency log**: publishing pack hashes is an irreversible external commitment (and a marketing claim); needs an explicit GO.
4. **SHADOW→ENFORCE risk appetite**: the mismatch threshold X% and sample size N are a risk tolerance, not a derivable number.
5. **Truth-freshness SLA values**: how stale immigration truth may be before the funnel degrades is a compliance/liability stance.
6. **Key ceremonies** (Ed25519 trust store, facts-fingerprint HMAC rotation) remain `operator[secret]` by design (`crypto.py:25-27`).
7. **Xendit secret for the order path** (the known 503-by-design gate) — credential only Zero holds.

## Sources

1. OpenFisca documentation — https://openfisca.org/doc/index.html
2. NZ Digital Government: Turning the rules of government into code using OpenFisca — https://discuss.digital.govt.nz/blog/turning-the-rules-of-government-into-code-using-openfisca/
3. PolicyEngine × Atlanta Fed Policy Rules Database validation MOU — https://www.policyengine.org/us/research/policyengine-atlanta-fed-mou-prd
4. PolicyEngine TAXSIM emulator — https://www.policyengine.org/us/taxsim
5. PolicyEngine US rules engine (GitHub) — https://github.com/PolicyEngine/policyengine-us
6. Merigoux, Chataing, Protzenko — *Catala: A Programming Language for the Law* — https://arxiv.org/abs/2103.03198
7. Camunda best practices: Choosing the DMN hit policy — https://docs.camunda.io/docs/components/best-practices/modeling/choosing-the-dmn-hit-policy/
8. Aserto: A secure software supply chain for OPA policies — https://www.aserto.com/blog/secure-software-supply-chain-opa-policies
9. 18F: Exploring a new way to make eligibility rules easier to implement — https://18f.gsa.gov/2018/10/16/exploring-a-new-way-to-make-eligibility-rules-easier-to-implement/
10. 18F eligibility-rules-service README — https://github.com/18F/eligibility-rules-service/blob/master/README.md
11. Beeck Center (Georgetown): Benefit Eligibility Rules as Code — https://beeckcenter.georgetown.edu/wp-content/uploads/2022/02/Benefit-Eligibility-Rules.pdf
12. GDS blog: Smart answers are smart — https://gds.blog.gov.uk/2012/02/16/smart-answers-are-smart/
13. GOV.UK: Check if you need a UK visa — https://www.gov.uk/check-uk-visa
14. Boundless Immigration — https://www.boundless.com/
15. BRYTER no-code platform — https://bryter.com/no-code-platform/
16. Neota Logic — https://www.neotalogic.com/
17. Red Hat Developer: Automating rule-based services with Java and Kogito — https://developers.redhat.com/articles/2021/06/24/automating-rule-based-services-java-and-kogito
18. GitHub Scientist — https://github.com/github/scientist
