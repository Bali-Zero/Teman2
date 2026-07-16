---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: codex-gpt-5.6-sol-ultra)
status: round-1 raw lane output, faithfully preserved
adversarial_review: gemini-3.1-pro
---

[Air-M5]

# Visa Oracle — Product Architecture & Red-Team Specification

**Research cut-off:** 17 July 2026  
**Verdict:** the concept is viable, but the current architecture is **NO-GO as a legal eligibility engine or government demo**. It may be shown only as a synthetic UI prototype with a prominent demo banner.

The rebuild should begin with the rule engine and regulatory governance—not the visual redesign. A beautiful interface would only amplify the reputational damage of one unsupported recommendation.

## 1. Non-negotiable product contract

“Zero wrong answers” is not an honest guarantee in a mutable regulatory system. The enforceable contract should be:

> **Zero unsupported recommendations.**

That means:

- Every recommendation is deterministic and reproducible.
- Every decisive condition has a pinpoint official source.
- Every decision records the exact ruleset, sources, prices and effective date used.
- Unknown, conflicting, stale or unsupported facts produce abstention—not an educated guess.
- An LLM can explain an approved result but cannot select, add, remove or rank visa paths.
- “No supported path” never means “Immigration denied your application.”
- The authority to approve or reject remains exclusively with Indonesian immigration authorities.

The engine must keep three concepts separate:

1. **Legal eligibility:** what the regulations permit.
2. **Operational availability:** what eVisa, an immigration office or another authority can currently process.
3. **Bali Zero service availability:** what Bali Zero is willing and able to handle commercially.

A path can be legally possible but operationally unavailable, or legally available while Bali Zero does not offer the service. The engine must never collapse these states.

---

## 2. Immediate blockers found in the current repository

These findings concern the inspected checkout, not a claim about the currently deployed runtime.

| Severity | Finding | Evidence | Required correction |
|---|---|---|---|
| P0 | Nationality is explicitly discarded by the deterministic matcher. | [match_tree.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_check/match_tree.py:315) | Nationality, travel-document issuer and nationality-list versions must be hard eligibility inputs. |
| P0 | Multiple competing “truth engines” exist: hardcoded tree, keyword scorer and RAG/Gemini reasoning. | [visa_oracle_service.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py:180), [visa_oracle.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_oracle.py:665) | Replace them with one canonical deterministic evaluator. |
| P0 | An abstention can be promoted to a recommendation using model pretraining and a system prompt. | [visa_oracle.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_oracle.py:699) | Delete this path. Only new verified facts or a reviewed ruleset may resolve abstention. |
| P0 | A D2 fee can be mapped to D12 as the “closest” pricing row. | [pricing_bridge.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_check/pricing_bridge.py:34) | Pricing requires an exact legal-product-and-tariff mapping; otherwise show “price unavailable.” |
| P0 | The catalogue’s stated provenance includes seed data, memory and NotebookLM, while its visa model lacks effective dates and pinpoint legal citations. | [catalogue.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_check/catalogue.py:1), [catalogue.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_check/catalogue.py:53) | Create an official-source registry and immutable versioned rule packs. NotebookLM may assist research, never serve as legal authority. |
| P0 | Privacy comments say “No PII” while storing nationality, family details, conversation content and an IP hash. | [migration_080a_visa_oracle_sessions.py](/Users/balizero/nuzantara/apps/backend-rag/backend/migrations/migration_080a_visa_oracle_sessions.py:1), [privacy/page.tsx](/Users/balizero/nuzantara/apps/mouth/src/app/visa/privacy/page.tsx:35) | Correct the data inventory, notices, lawful-basis analysis, retention and deletion implementation. |
| P0 | Consent is represented by “By continuing” with only a “Got it” action. | [ConsentBanner.tsx](/Users/balizero/nuzantara/apps/mouth/src/components/visa/ConsentBanner.tsx:43) | Separate necessary processing from optional CRM, WhatsApp and marketing consent. |
| P0 | A result located by a public hash can lead to JWT issuance. | [visa_check.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:314), [test_router_jwt.py](/Users/balizero/nuzantara/apps/backend-rag/backend/tests/services/visa_check/test_router_jwt.py:100) | Use random, scoped, expiring capability tokens and authenticated result retrieval; hashes of answers are not access control. |
| P1 | The bridge prompt instructs the model to “always quote” a recommended visa and cost. | [bridge.py](/Users/balizero/nuzantara/apps/backend-rag/backend/services/visa_unified/bridge.py:115) | The explainer must faithfully render structured output and be permitted to say that no price or recommendation is available. |

Until these issues are removed, the safest current response is a human-review state.

---

## 3. Regulatory model the engine must represent

The source hierarchy begins with [Law 6/2011 on Immigration](https://peraturan.bpk.go.id/Details/39140/uu-no-6-tahun-2011), including later amendments such as [Law 63/2024](https://peraturan.bpk.go.id/Details/304897), followed by implementing government and ministerial regulations.

The core operational framework includes:

- [PP 31/2013](https://peraturan.bpk.go.id/Details/5363) and subsequent amendments, including [PP 40/2023](https://peraturan.bpk.go.id/Details/257736).
- [Permenkumham 22/2023](https://peraturan.bpk.go.id/Details/272044), amended by [Permenkumham 11/2024](https://peraturan.bpk.go.id/Details/285156).
- [Permen Imipas 3/2025](https://peraturan.bpk.go.id/Details/316856/permen-imipas-no-3-tahun-2025), which introduced a diaspora regime and revoked specific articles of the earlier regulation rather than replacing the entire instrument.
- [Permen Imipas 5/2025](https://peraturan.bpk.go.id/Details/316860/permen-imipas-no-5-tahun-2025), the current sponsor-layer regulation located in this review.
- [Kepmen M.IP-08.GR.01.01/2025](https://kemenimipas.go.id/attachments/2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf), which changed the operational visa index classification. The official announcement describes a reduction from 133 to 110 indexes and transitional treatment for already issued visas. [Ditjen Imigrasi announcement](https://imigrasi.go.id/siaran_pers/ditjen-imigrasi-terapkan-kebijakan-terbaru-tentang-klasifikasi-visa)

A recent example shows why this cannot be maintained as static website copy: Permen Imipas 10/2026 was signed on 7 July, became effective on 9 July and added six jurisdictions to the visa-free list only eight days before this research cut-off. [Kemenimipas announcement, 16 July 2026](https://kemenimipas.go.id/berita-utama/kemenimipas-menambah-enam-negara-penerima-bebas-visa-kunjungan-ke-indonesia)

The official live surfaces currently include separate lists for:

- [Visa-free visit eligibility](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-bebas-visa-kunjungan)
- [Visa on arrival eligibility](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival)
- [Calling visa jurisdictions](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa)

Calling-visa status must be represented as a procedural overlay, not invented as another visa class.

### Required provenance chain

A complete recommendation normally needs separate evidence for:

1. Legal visa/stay-permit class.
2. Permitted and prohibited activities.
3. Current ministerial index.
4. Nationality or travel-document eligibility.
5. Sponsor requirements.
6. Duration, entries, extension and conversion rules.
7. Official tariff.
8. Operational availability in the official system.
9. Any Bali Zero professional service and fee.

A marketing label such as “Remote Worker KITAS” must never be the database’s legal primary key.

---

## 4. Decision-engine architecture

### 4.1 Technology choice

| Approach | Decision | Reason |
|---|---|---|
| Hardcoded TypeScript/Python branches | Reject | Difficult to diff, legally review, date and reproduce; encourages duplicated logic across surfaces. |
| LLM/RAG eligibility engine | Prohibit | Non-deterministic, prompt-injectable, difficult to audit and capable of filling gaps with plausible fiction. |
| Full Drools/DMN enterprise runtime | Defer | Useful semantics, but unnecessary runtime and editor complexity for the first rebuild. |
| OPA/Rego | Limited future use | Suitable for boolean safety gates and tenant policies, less natural for guided multi-candidate recommendation. |
| Typed rules-as-data plus a small Python evaluator | **Adopt** | Deterministic, testable, reviewable, signed, versionable and native to the existing backend. |

Use [DMN 1.5](https://www.omg.org/spec/DMN/1.5/About-DMN) concepts—hit policies, decision tables, gap and overlap analysis—without initially adopting a Java runtime. Validate the rule documents against [JSON Schema 2020-12](https://json-schema.org/specification).

YAML can be the human authoring format. The publication artifact should be canonical JSON with a content hash and digital signature.

### 4.2 Architecture

```text
BPK / JDIH / Imigrasi / eVisa / Kemenkeu
                    │
          source snapshots + hashes
                    │
       provision-level semantic diff
                    │
      regulatory review + four-eyes gate
                    │
       compiler / linter / gold tests
                    │
     signed immutable ruleset bundle
                    │
       deterministic Python evaluator
                    │
     decision trace + source manifest
          ┌─────────┴─────────┐
     API / web / SEO      optional explainer
                              │
                 approved claims only; no decisions
          └─────────┬─────────┘
           optional consented CRM handoff
```

### 4.3 Core data model

| Object | Required fields |
|---|---|
| `SourceRecord` | Instrument, issuer, authority rank, official URL, signed document hash, article/annex/page/row pinpoint, publication/promulgation/effective/repeal dates, retrieval time, status and supersession links. |
| `RulePack` | Immutable ID, semantic version, hash, status, legal-valid interval, publication interval, reviewers, source manifest, price-table version and evaluator compatibility. |
| `VisaProductVersion` | Stable internal product ID, legal class, ministerial index, aliases, permitted/prohibited activities, duration, entries, extension/conversion, sponsor and work-right conditions, source references and operational status. |
| `ApplicantFacts` | Travel-document type and issuer, citizenships, present country/status/permit, intended activities, duration, travel cadence, sponsor relationship, family/dependants and reason-coded exception flags. |
| `Rule` | Restricted condition AST, priority/hit policy, explicit unknown behavior, effect, reason code and source references. |
| `Decision` | Evaluation time, legal `as_of` time, exact ruleset, normalized fact snapshot/hash, fired rules, missing facts, candidates, exclusions, abstention reason, source manifest and trace hash. |
| `PriceQuote` | Exact product/index, official tariff components, third-party disbursements, Bali Zero fee, tax, currency, validity interval, source and version. |
| `ConsentReceipt` | Purpose, lawful basis, notice version, affirmative action, timestamp, withdrawal status and data recipients. |

Use **bitemporal records**:

- `valid_from` / `valid_to`: when the rule was legally true.
- `recorded_from` / `recorded_to`: when Visa Oracle knew and published it.

This allows both “what is correct today?” and “what did the engine legitimately know on 10 July?”

### 4.4 Rule format

Illustrative only—not a legal rule:

```yaml
rule_id: visit.b1.country-eligibility.v2026-07
valid_time:
  from: 2026-07-09
source_refs:
  - permen-imipas-10-2026:article-2
  - imigrasi-voa-list:sha256-...
when:
  all:
    - fact: travel_document.issuer
      op: in_set
      value_ref: country_set.voa.2026-07-09
    - fact: intended_activities
      op: subset_of
      value: [tourism, family_visit, government_visit]
unknown_effect: NEEDS_INPUT
then:
  effect: ADD_CANDIDATE
  product_id: VISIT_B1
```

Do not allow arbitrary Python, JavaScript, regex scripts or LLM-generated predicates inside a rule pack. Supported operations should be a small audited vocabulary: equality, numeric/date comparisons, set membership, subset, conjunction, disjunction and negation.

### 4.5 Evaluation semantics

The engine returns one of five states:

- `NEEDS_INPUT`
- `SUPPORTED_CANDIDATES`
- `HUMAN_REVIEW_REQUIRED`
- `NO_SUPPORTED_PATH`
- `TEMPORARILY_UNAVAILABLE`

Rules:

- `UNKNOWN` is a first-class value; it is never silently converted to `false`.
- Hard eligibility filters run before suitability ranking.
- If several candidates remain, show transparent trade-offs instead of manufacturing one winner.
- A commercial margin or Bali Zero service availability can never affect legal ranking.
- Missing or conflicting source evidence disables the affected recommendation.
- Pricing failure does not necessarily suppress a valid legal path; it produces `PRICE_UNAVAILABLE`.
- Do not show vector-similarity percentages as legal confidence. Use evidence states such as `COMPLETE`, `CONDITIONAL`, `CONFLICT` and `STALE`.

### 4.6 Mandatory human-review triggers

Human review must be automatic for:

- Dual citizenship, statelessness, refugee documents or special travel documents.
- Calling-visa jurisdiction.
- Minors and uncertain guardianship.
- Mixed marriage, adoption, divorce, widowhood or unregistered civil status.
- Former Indonesian citizen or diaspora paths.
- Current overstay, refusal, deportation, blacklist or immigration investigation.
- Criminal, security or relevant health declarations.
- Diplomatic/service passports.
- Unclear sponsor authority or relationship.
- Activity-boundary cases: meetings versus work, volunteering, content creation, remote work, performance or paid/unpaid services.
- Multiple purposes in one trip.
- Onshore conversion or uncertain current stay status.
- Conflicting, future-effective, stale or operationally unverified rules.
- Any missing exact fee mapping.
- Cases requiring simultaneous immigration, manpower, company or tax analysis.

The handoff must explain the unresolved issue, list the minimum documents needed for review and still offer the user official self-service links. It must not use fabricated urgency.

---

## 5. Correctness and regulatory-update system

### 5.1 Publication workflow

1. **Monitor official sources separately.** Poll BPK/JDIH, Kemenimipas/Imigrasi, operational lists, eVisa and Kemenkeu sources.
2. **Snapshot every artifact.** Store retrieval time, content hash, signed PDF and metadata.
3. **Create a quarantined change candidate.** A detected change must never auto-publish a legal rule.
4. **Produce a semantic diff.** Identify changed articles, annex rows, country sets, activities, durations, sponsors and tariffs.
5. **Classify impact.**
   - P0: could change eligibility, work rights, duration or money.
   - P1: requirements, documents or operational flow.
   - P2: wording or non-substantive metadata.
6. **Map source to rules.** Regulatory analyst authors the change; a second reviewer verifies both interpretation and pinpoint citation.
7. **Run impact simulation.** Compare old and new results over the complete gold-case corpus.
8. **Compile and sign.** Schema validation, overlap/gap detection, test suite and reviewer signatures.
9. **Activate atomically.** Engine, API, result UI, SEO pages, translations, citation pages and cache tags switch to one ruleset ID.
10. **Verify and monitor.** Run production synthetic cases and retain one-click rollback.

For immediately effective P0 changes, affected routes enter `TEMPORARILY_UNAVAILABLE` or `HUMAN_REVIEW_REQUIRED` until reviewed.

An announcement can trigger an alert. It cannot, by itself, silently replace a signed legal instrument unless the system explicitly records that the official operational list is the authoritative source for that particular fact.

### 5.2 Testing matrix

Every active rule needs:

- At least one positive case.
- At least one negative case.
- At least one missing/unknown-fact case.
- A source and effective-date assertion.

The complete suite should include:

- Legal-reviewed persona-to-outcome gold cases.
- Boundary tests for age, dates, 30/60/180/365-day limits and monetary thresholds.
- Nationality and travel-document set-difference tests.
- Calling-visa overlays.
- Historical and future-effective decisions.
- Grandfathered permits and retired indexes.
- Gap, overlap, unreachable-rule, cycle and orphan-source linting.
- Mutation tests: invert or remove a condition and confirm a gold test fails.
- Differential old-versus-new ruleset reports.
- Property tests:
  - Same facts and ruleset always produce the same trace.
  - Unknown cannot increase eligibility.
  - Adding a prohibited activity cannot improve a result.
  - A price change cannot change legal eligibility.
- Contract tests ensuring wizard, result page, SEO catalogue, API and explainer use the same ruleset.
- Security tests for IDOR, tenant isolation, token replay, consent enforcement and prompt injection.
- Fail-closed tests: no valid bundle means `503`, never a legacy fallback.

### 5.3 Freshness shown to users

Each result should say, in substance:

> Evaluated with ruleset `2026.07.09-1`, using legal sources verified on 17 July 2026 at 14:20 WITA. The controlling country-list change became effective on 9 July 2026.

Also show:

- Ruleset and source-manifest links.
- Effective date versus last verification date.
- Any operational uncertainty.
- A visible warning if the result has since been withdrawn.

Avoid vague badges such as “up to date” without a timestamp and scope.

### 5.4 Correctness SLOs

- 100% of active decision rules have a pinpoint source and validity interval.
- 100% have positive, negative and unknown-case coverage.
- Zero active P0 source conflicts.
- Zero unknown-to-eligible coercions.
- Zero approximate price mappings.
- Atomic ruleset version across all public surfaces.
- P0 source-monitor failure makes affected paths unavailable.
- Every published change has two named reviewers and a reversible activation record.

---

## 6. Trust, privacy and liability

### 6.1 Privacy classification

Under [UU 27/2022 on Personal Data Protection](https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang%2Bnomor%2B27%2Btahun%2B2022), nationality and marital status are personal data. Criminal history, children’s data, health information, biometric/genetic data and financial information receive heightened treatment. An IP address may also identify a person when combined with other data.

Therefore Visa Oracle must not claim that it processes “no PII.”

A DPIA is strongly indicated if the finished system combines systematic profiling, potentially significant automated recommendations, sensitive edge-case declarations, data matching or large-scale monitoring. Whether it is legally mandatory and whether a DPO is required should be determined against the final processing design—not guessed from the prototype.

The privacy design should include:

- Anonymous eligibility evaluation by default.
- No account, phone number or email required to see or export a result.
- Structured answers instead of free-text wherever possible.
- No passport number, document scan, criminal narrative or medical detail in the public wizard.
- Separate retention periods for anonymous decisions, security events, CRM leads and legal case files.
- A working deletion job with monitoring, reconciliation and deletion receipts.
- Data-subject access, correction, withdrawal, objection and deletion processes.
- Recorded processing activity and consent logs.
- Vendor and cross-border-transfer inventory.
- Human review and contest mechanism for any materially consequential automated classification.
- Specific child/guardian flow, also considering [PP 17/2025](https://peraturan.bpk.go.id/Details/316698/pp-no-17-tahun-2025).

### 6.2 Consent design

Do not use one consent for everything.

Present three separate, unticked optional choices after the user receives the result:

1. Share the minimal case summary with Bali Zero for a consultant review.
2. Receive a service message through WhatsApp.
3. Receive future marketing communications.

Necessary technical processing should be described under its actual lawful basis, not disguised as marketing consent.

The WhatsApp handoff must use a user-supplied number and an explicit opt-in, with a route to human support, consistent with the [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/). Detailed documents should be uploaded through a secure portal, not sent through WhatsApp.

### 6.3 Disclaimer hierarchy

A trust-preserving inline notice should communicate four facts:

- This is a private decision-support tool, not an Indonesian government service.
- The result is based on the facts entered and the cited ruleset at a stated date.
- It is not an approval, legal determination or guarantee.
- Complex or uncertain cases are sent to human review.

A second layer can contain full methodology, limitations, complaint process, data policy and source ledger.

Avoid blanket language such as “Bali Zero accepts no liability for anything.” It signals that the publisher does not trust its own product.

### 6.4 Government demonstration mode

The Ditjen Imigrasi demonstration must be a separate tenant with:

- Synthetic personas only.
- `DEMO — PRIVATE — NOT OFFICIAL — NOT FOR CASE DECISIONS`.
- No CRM, marketing, WhatsApp, session replay or document upload.
- No government logo or implied endorsement.
- No indexing by search engines.
- Expiring access and isolated audit logs.
- A visible source ledger and old/new ruleset replay.
- An “abstention demonstration” showing that the system refuses unsafe cases.

Government stakeholders are likely to scrutinize citation precision, neutrality, update cadence, fee separation, data minimization, audit reproducibility, accessibility and whether the tool could be mistaken for an official adjudication channel.

---

## 7. Ethical business integration

### 7.1 Result-page order

The outcome page should present:

1. Decision state and supported candidates.
2. Why each candidate remains or was excluded.
3. Permitted and prohibited activities.
4. Conditions and missing facts.
5. Sources, effective dates and freshness.
6. Document checklist.
7. Timeline range with explicit assumptions.
8. Itemized costs.
9. Official self-service/eVisa link.
10. Exportable result.
11. Only then: optional Bali Zero review.

This ordering demonstrates that the result was not withheld to capture a lead.

### 7.2 Fee ledger

Never display one opaque “visa price.” Separate:

- Official immigration PNBP.
- Other mandatory official charges.
- Third-party disbursements.
- Bali Zero professional fee.
- Applicable tax.
- Currency, validity date and assumptions.

The main immigration PNBP framework includes [PP 45/2024](https://peraturan.bpk.go.id/Details/305293), while particular tariff handling may also depend on instruments such as [PMK 9/2022](https://www.jdih.kemenkeu.go.id/dok/9-pmk-02-2022/summary), [PMK 82/2023](https://www.jdih.kemenkeu.go.id/dok/pmk-82-tahun-2023/files) and applicable zero-tariff procedures. The resolver must attach a source to each tariff row, rather than attaching one remembered price to a marketing name.

### 7.3 CRM handoff

The server—not the browser—constructs the handoff from the canonical decision record.

Send only:

- Decision ID.
- Ruleset ID.
- Human-review reason codes.
- Explicitly selected structured facts.
- User-selected contact method.
- Consent receipt ID.

Do not send the raw chat transcript by default.

Use an opaque, tenant-bound, expiring, single-use handoff token. Never place nationality, visa result, phone number or answer hashes in the URL.

The audit ledger and CRM must remain separate: deleting or editing a CRM lead must not mutate the historical decision trace.

---

## 8. API-first and white-label specification

Document the API with [OpenAPI](https://spec.openapis.org/oas/latest.html) and generate versioned client SDKs.

### Public API surface

- `POST /v1/sessions`
- `POST /v1/evaluations` with `Idempotency-Key`
- `GET /v1/decisions/{decision_id}`
- `POST /v1/decisions/{decision_id}/questions`
- `POST /v1/decisions/{decision_id}/handoffs`
- `GET /v1/rulesets/current`
- `GET /v1/rulesets/{ruleset_id}/sources`
- `GET /v1/catalogue`
- `GET /v1/fees`

### Administrative surface

- `POST /v1/admin/rulesets/validate`
- `POST /v1/admin/rulesets/simulate`
- `POST /v1/admin/rulesets/activate`
- `POST /v1/admin/rulesets/rollback`

Events:

- `ruleset.activated`
- `decision.withdrawn`
- `fee.changed`
- `source.conflict_detected`

A decision response must include:

- `decision_id`
- `status`
- `ruleset_id`
- `as_of`
- `evaluated_at`
- `missing_facts`
- `candidates`
- `decision_trace`
- `source_manifest`
- `price_quote`
- `freshness`

### White-label boundaries

A partner may configure:

- Branding and locale.
- Its own professional service fee.
- Services it offers.
- CTA and contact routing.

A partner may not alter:

- Legal eligibility rules.
- Official sources or tariffs.
- Non-affiliation disclaimer.
- Safety and abstention gates.
- Audit requirements.
- Data-purpose boundaries.

Each tenant requires separate keys, RBAC, encryption context, logs, export policy, webhook secrets, deletion process and kill switch. The platform should continuously verify that an embed has not hidden the disclaimer or altered official-fee presentation.

Hotels and coworking spaces should normally receive the result or referral token—not the applicant’s complete answer set. Depending on their actual purpose and control over processing, partners may become independent or joint controllers regardless of what the contract calls them.

Personalized responses should use `Cache-Control: no-store`. Public catalogue responses can use ETags that include the ruleset ID. Eligibility responses must never use `stale-if-error`.

---

# 9. Adversarial failure catalog

**P0:** potential wrong legal path, privacy/security incident or government embarrassment.  
**P1:** material trust, operational or commercial harm.

## A. Regulatory and content failures

| Sev. | Failure | Concrete mitigation / fail-safe | Acceptance test |
|---|---|---|---|
| P0 | A new regulation is missed. | Independent source monitors, hash snapshots, publication alerts; affected source family becomes stale after monitor failure. | Simulate a new official document and verify quarantine/alert. |
| P0 | A future-effective rule is applied early or late. | Separate promulgation, publication and effective dates; evaluate by `as_of`. | Cases one second before and after activation. |
| P0 | Partial repeal is treated as full repeal or ignored. | Provision-level amendment graph with article/annex relationships. | Replay Permen Imipas 3/2025 against amended 22/2023 provisions. |
| P0 | Transitional/grandfather clauses are lost. | Version permit issuance and validity separately from new-application eligibility. | Existing-visa and new-application personas produce different traces. |
| P0 | Law changes but the official portal is not operationally ready. | Separate `LEGAL_STATUS` and `OPERATIONAL_STATUS`; show review/unavailable state. | Disable portal availability without changing eligibility. |
| P0 | Country-list aliases drift: Macao/Macau, Türkiye/Turkey, territories. | ISO-based jurisdiction registry plus reviewed official aliases and document issuers. | Set-difference and alias-collision tests. |
| P0 | Calling-visa handling is omitted. | Apply it as a procedural overlay before normal recommendation. | Every calling-list issuer forces reviewed handling. |
| P0 | A press release silently outranks a signed instrument. | Authority ranking and source-type policy; announcement only creates a candidate change. | Attempt activation using announcement-only evidence. |
| P0 | OCR misreads a PDF table or footnote. | Preserve signed PDF; dual human verification for extracted tables; row hashes. | Seed an OCR digit/column error and ensure review rejects it. |
| P0 | Two official sources conflict. | Mark source conflict, quarantine affected rules and abstain. | Inject conflicting country sets. |
| P0 | A retired index is treated as an interchangeable alias. | Versioned alias table with validity ranges and transition rules. | Historical and current queries resolve differently. |
| P0 | SEO page, wizard and chatbot contradict each other. | All surfaces consume the same signed catalogue/ruleset; no handwritten eligibility prose. | Cross-surface snapshot tests. |
| P1 | Translation changes legal meaning. | Approved claim IDs and legal-reviewed translations; fall back to source language. | Back-translation and prohibited-term tests. |
| P0 | CDN/ISR retains old rules. | Atomic release tag, cache-tag purge and no-store personalized results. | Activate a rule and probe every edge region. |

## B. Applicant and case-complexity failures

| Sev. | Failure | Concrete mitigation / fail-safe | Acceptance test |
|---|---|---|---|
| P0 | Nationality is ignored. | Require travel-document issuer and citizenship facts; evaluate versioned lists. | Same persona with different issuer changes trace where legally relevant. |
| P0 | Dual citizen chooses the “easier” nationality incorrectly. | Ask which passport will be used and preserve all citizenships; ambiguous cases reviewed. | Dual-national gold cases. |
| P0 | Stateless, refugee or emergency document treated as an ordinary passport. | Typed document categories; unsupported types trigger review. | Non-passport documents cannot reach automatic eligibility. |
| P0 | Minor is routed without guardian analysis. | Age/guardian flow, minimal child data, parental consent and human review. | Boundary at age threshold plus absent guardian. |
| P0 | Mixed marriage, adoption or divorce is simplified incorrectly. | Relationship-status subgraph and evidence checklist; uncertain civil status reviewed. | Registered/unregistered and active/ended relationship cases. |
| P0 | Former Indonesian or diaspora path is missed. | Dedicated former-citizen/diaspora facts and ruleset. | Diaspora cases cannot fall into ordinary nationality routing. |
| P0 | Current permit or onshore conversion is ignored. | Ask current location, stay status and expiry before evaluating transition paths. | Offshore versus onshore cases. |
| P0 | Overstay, refusal, deportation or blacklist is ignored. | Coarse yes/no exception flags; immediate confidential human review. | Any positive answer suppresses automatic recommendation. |
| P0 | Criminal, health or security issue is scored automatically. | Do not collect narratives publicly; reason-code handoff only. | Sensitive flag never appears in ordinary result/log. |
| P0 | Business meetings are confused with employment. | Activity taxonomy with allowed/prohibited examples and follow-up questions. | Boundary cases for meetings, supervision and productive work. |
| P0 | Remote work, content creation, volunteering or performance is mislabeled. | Separate payer, employer, client, location, remuneration and public-output facts. | Legal-reviewed activity matrix. |
| P0 | Multi-purpose travel is reduced to the easiest purpose. | Evaluate every declared activity; incompatible purposes trigger review. | Adding a prohibited purpose cannot improve the result. |
| P0 | Sponsor is legally or operationally invalid. | Version sponsor type, relationship, licensing and operational acceptance. | Invalid sponsor blocks or reviews path. |
| P0 | Dependants are assumed to share the principal’s route. | Evaluate each family member as a linked applicant. | Family graph with different ages/relationships. |
| P0 | Duration, entry or extension limits are off by one. | Zoned date arithmetic and explicit inclusive/exclusive semantics. | Boundary tests across midnight, leap year and expiry date. |
| P0 | Diplomatic/service passport follows ordinary rules. | Travel-document-type gate and human review. | Special passports never silently use ordinary lists. |
| P1 | Immigration result ignores manpower, tax or company consequences. | Label cross-domain dependencies and offer separate expert analysis; do not infer them. | Work/investor paths display dependency warnings. |
| P0 | User answers are missing or contradictory. | Tri-state facts, contradiction detector and `NEEDS_INPUT`; never impute. | Randomly delete/contradict facts and verify no stronger result. |

## C. Fees, funnel and reputational failures

| Sev. | Failure | Concrete mitigation / fail-safe | Acceptance test |
|---|---|---|---|
| P0 | Wrong price is quoted through fuzzy matching. | Exact product/index/tariff key; missing row means `PRICE_UNAVAILABLE`. | No approximate or fallback mapping passes compilation. |
| P0 | Government and agency fees are combined. | Mandatory five-layer fee ledger with individual sources. | UI/API schema rejects a single opaque total. |
| P1 | FX or tax becomes stale. | Timestamp rates, source them and mark estimate/validity; settlement re-quote. | Expired quote cannot be presented as current. |
| P0 | Most profitable product is ranked first. | Legal filters and neutral suitability criteria precede service data; audit ranking inputs. | Modify margins and prove order is unchanged. |
| P1 | Result is hidden until phone/email capture. | Full result and export available anonymously. | E2E flow completes without contact data. |
| P0 | Approval or processing time is guaranteed. | Display ranges, assumptions and external dependencies; prohibited-copy lint. | Copy test rejects “guaranteed,” “approved” and unsupported deadlines. |
| P0 | CRM entry occurs before valid consent. | Server-side consent receipt required for handoff mutation. | API returns denial without purpose-specific receipt. |
| P0 | Passport or sensitive evidence is solicited through WhatsApp. | Secure portal upload; WhatsApp limited to scheduling/status. | Message-template scanner rejects sensitive-document requests. |
| P0 | Government endorsement is implied. | Persistent private/non-official notice; trademark/logo controls. | Government-demo and partner-embed visual audit. |

## D. AI, security, privacy and operational failures

| Sev. | Failure | Concrete mitigation / fail-safe | Acceptance test |
|---|---|---|---|
| P0 | LLM invents or changes the result. | LLM receives signed decision object and approved claim IDs only; output validator forbids new candidates, fees or citations. | Adversarial model attempts are rejected. |
| P0 | Prompt injection in user text changes rules. | No free text enters evaluator prompts; structured facts only; explainer treats text as data. | Injection corpus cannot alter decision JSON. |
| P0 | Vector similarity is presented as legal confidence. | RAG is research/explanation retrieval only; deterministic evidence states. | No similarity value reaches public schema. |
| P0 | Browser alters answers, history or question limits. | Server-owned canonical session, signed transitions and server-side quotas. | Tampered payload and localStorage are ignored/rejected. |
| P0 | Public result hash enables IDOR or JWT issuance. | Random 128-bit IDs, scoped expiring capability, authorization on every fetch. | Enumeration, token replay and cross-user tests. |
| P0 | PII leaks through URLs, analytics, logs or caches. | Data-classification middleware, field allow-lists, log redaction and no-store. | Automated canary PII scan across observability systems. |
| P0 | Unsalted IP hash remains linkable. | Short-retention HMAC with rotating secret, or avoid storage when unnecessary. | Rotation breaks historical linkage. |
| P0 | Retention policy exists only in copy. | Scheduled deletion plus reconciliation, metrics and alerts. | Seed expired data and verify deletion from primary, replica and analytics. |
| P0 | Children or significant profiling are processed without safeguards. | DPIA, guardian flow, human review, objection/contest and data minimization. | Child and review-right E2E tests. |
| P0 | Vendor or cross-border processing changes silently. | Vendor registry, data-flow map, transfer assessment and deployment gate. | CI blocks an unregistered telemetry/AI endpoint. |
| P0 | UI, API and rules activate at different times. | Signed release manifest and atomic ruleset pointer. | Kill deployment halfway and verify old version remains whole. |
| P0 | Rollback restores code but not rules/cache. | Bundle-level rollback including catalogue, prices and purge state. | Disaster-recovery exercise. |
| P0 | Rules service fails and stale eligibility is served. | Fail closed for personalized decisions; no stale-if-error. | Disconnect ruleset storage and expect `503`. |
| P0 | Audit record is mutable or incomplete. | Append-only tamper-evident events, trace hashes and restricted overrides. | Alter an event and verify integrity alarm. |
| P0 | White-label partner edits legal wording or hides disclaimer. | Immutable legal component, signed tenant config and automated embed crawler. | Partner DOM/config tampering disables tenant. |
| P0 | Cross-tenant data leaks or survives offboarding. | Tenant-scoped encryption/auth, negative access tests and deletion runbook. | Cross-tenant fuzzing and offboarding drill. |

---

## 10. Audit trail specification

Record:

- Decision event and tenant IDs.
- Pseudonymous session ID.
- Evaluation and legal `as_of` timestamps.
- Ruleset, schema, evaluator and source-manifest hashes.
- Normalized fact codes or encrypted minimized snapshot.
- Fired rules, exclusions and abstention reason.
- Fee-table version.
- Notice and disclaimer versions.
- Consent purpose, basis, version and time.
- Handoff status.
- Human override, reviewer and reason.
- Software/configuration version.

Do not record in the general audit stream:

- Passport numbers or scans.
- Phone/email unless required in the dedicated CRM system.
- Raw criminal/medical narratives.
- Raw free-text conversations.
- Document URLs or access tokens.
- Raw IP addresses.

An override can append a new event but must never rewrite the machine decision.

---

## 11. Launch gates

### Gate 0 — Safety remediation

- One canonical engine.
- Remove all LLM abstention promotion.
- Nationality and travel document actually evaluated.
- Exact pricing only.
- Privacy inventory and notice corrected.
- Purpose-specific consent implemented.
- Secure decision identifiers.
- Retention deletion proven.

### Gate 1 — Deterministic core

- Source registry.
- Versioned rule packs.
- Deterministic evaluator.
- Legal-reviewed gold corpus.
- Decision trace and source manifest.
- Anonymous result and export.
- No chatbot or CRM required.

### Gate 2 — Roadmap and ethical conversion

- Document roadmap.
- Transparent fee ledger.
- Optional consultant handoff.
- Consent-enforced CRM integration.
- Secure document portal.

### Gate 3 — Constrained explainer

- Explanation only over signed output.
- Approved-claim registry.
- Prompt-injection and hallucination testing.
- Automatic fallback to structured copy.

### Gate 4 — White-label and government pilot

- Tenant isolation.
- Immutable legal core.
- Partner governance.
- Government demo tenant.
- DPIA/privacy review.
- Incident and rollback drill.

## Final go/no-go standard

Do not launch as an authoritative Visa Oracle until:

- Every active rule is sourced, dated and versioned.
- Every rule has positive, negative and unknown-case tests.
- No P0 source conflict remains.
- Wizard, API, SEO, fees and explainer share one ruleset.
- Legal, privacy and security reviewers have signed off.
- Withdrawal, deletion and incident workflows work in practice.
- The system has demonstrated that it can abstain safely.

**Final recommendation:** rebuild Visa Oracle as a small, deterministic regulatory product with an exceptional interface around it. Do not rebuild it as a better-looking chatbot.

## Adversarial review

**Seat:** gemini-3.1-pro (Gemini 3.1 Pro High adversarial grading, 2026-07-17)
**Verdict:** SURVIVES-WITH-CAVEATS

Challenged points:
- Classifying anonymous nationality/marital status as PII under UU 27/2022 is an overclaim absent
  linkable identifiers — the design keeps the conservative posture deliberately anyway.
- Dismissing standard rule engines (OPA/Drools) in favor of a bespoke evaluator carries maintenance and
  correctness risk that the redteam does not fully price in.

This section is an appended R1-gate artifact (generator≠grader); the file body above is preserved
verbatim as the faithful record of this panel lane's original output.
