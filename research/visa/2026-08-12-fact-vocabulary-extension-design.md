---
date: 2026-08-12
domain: visa
client_case: none
sources:
  - Gemini 3.1 Pro regulatory lane (2026-08-12, this session)
  - GPT-5.6-sol architecture + red-team lane (2026-08-12, this session)
adversarial_review: codex
---

# Fact vocabulary extension design for unreachable products

## Problem

Eleven of 38 products in rule-pack sequence 7 cannot be returned as `SUPPORTED_CANDIDATES`: the present interview vocabulary contains no legally discriminating fact for their sibling/product boundary. The supplied regulatory lane names seven of those codes directly: student twins `E30E`/`E30F`, work twins `E23U`/`E23V`, and sponsor/talent tiers `E33A`/`E33B`/`E33C`. It proposes a minor/guardian repair as the remaining safety boundary, but does **not** identify the four additional minor-affected product codes. Do not infer them.

## CRITICAL EPISTEMIC CAVEAT

The regulatory lane's citations are mostly **GENERIC**: it names instruments such as “Permen Imipas / Kepmen M.IP-08/2025” without a pinpoint article for most rows. These candidate facts are a **research lead, not grounded law**. **No rule may be authored into a signed pack until every discriminator has been verified against the primary source text, article by article.** This is a hard precondition for the entire plan, including question wording, enum semantics, positive witnesses and sibling-negative controls. A generic citation below records what the lane said; it is not authority to encode the asserted condition.

The supplied lane also makes assertions which need particular scrutiny before authoring: an E30 university/non-university split; E23U/E23V mapping to technical service versus long-term RPTKA employment; E33 Top-100, three-year, GPA and 90-day agreement criteria; and a legal rule that an under-18 applicant cannot independently hold a stay permit without the specified guardian arrangement. The lane cites neither a pinpoint provision nor a primary-text extract for these assertions.

## Proposed fact vocabulary

The first column is a **proposed FactPath-style target**, not an already-approved enum. The parenthetical source identifier preserves the regulatory lane's exact proposed identifier. `person.birth_date` and derived `derived.is_minor` already exist in the current vocabulary; they should be reused rather than duplicated if the legal review confirms the need. `sponsor.type` also already exists, but the lane's three proposed sponsor values are not thereby approved as its enum values.

| Proposed FactPath-style name (source identifier) | Interview question (English) | Answer type / enum | Knowability rating | Products unlocked | Cited legal source in supplied lane |
| --- | --- | --- | --- | --- | --- |
| `study.institution_level` (`education_institution_level`) | What level of educational institution in Indonesia will you be enrolled in? | `Enum`: `HIGHER_EDUCATION_UNIVERSITY`; `PRIMARY_SECONDARY_K12_OR_VOCATIONAL` | `APPLICANT-KNOWABLE` | `E30E` (university); `E30F` (K-12/vocational) | Permen Imipas / Kepmen M.IP-08/2025; UU 6/2011 Art. 31 — generic; no pinpoint supplied |
| `work.employment_engagement_nature` (`employment_engagement_nature`) | What is the primary nature of your work assignment in Indonesia? | `Enum`: `TECHNICAL_SERVICE_INSTALLATION_AUDIT_CONSULTANCY`; `FULL_TIME_EXPATRIATE_EMPLOYMENT_RPTKA` | `KNOWABLE-WITH-DOCUMENT-IN-HAND` | `E23U` (technical/audit); `E23V` (full expatriate employment) | Permen Imipas / Kepmen M.IP-08/2025; PP 34/2021; UU 6/2011 Art. 39 — generic; no pinpoint supplied |
| `education.university_global_rank` (`applicant_university_global_rank`) | Did you graduate within the last 3 years from a university ranked in the Top 100 globally (e.g., QS, THE, ARWU)? | `Enum`: `TOP_100_GLOBAL_UNIVERSITY`; `NOT_TOP_100` | `APPLICANT-KNOWABLE` | `E33A` (Top-100 graduates) | Permen Imipas / Kepmen M.IP-08/2025 — generic; no pinpoint supplied |
| `education.institutional_cooperation_duration_status` (`institutional_cooperation_duration_status`) | Is your academic/research stay based on an active official cooperation agreement between your home institution/government and an Indonesian entity that has been in force for at least 90 days? | `Enum`: `ACTIVE_AGREEMENT_GTE_90_DAYS`; `NO_QUALIFYING_90DAY_AGREEMENT` | `SPONSOR-ONLY` / `KNOWABLE-WITH-DOCUMENT-IN-HAND` | `E33B` (G2G / 90-Day Agreement Talent) | Permen Imipas / Kepmen M.IP-08/2025 — generic; no pinpoint supplied |
| `education.academic_gpa_band` (`academic_gpa_band`) | What was your cumulative GPA or academic achievement score upon graduation? | `Enum`: `GPA_3_50_OR_ABOVE_EQUIVALENT`; `GPA_BELOW_3_50` | `APPLICANT-KNOWABLE` | `E33A` / `E33C` discriminator | Permen Imipas / Kepmen M.IP-08/2025 — generic; no pinpoint supplied |
| `sponsor.indonesian_tier` (`indonesian_sponsor_tier`) | What type of entity is sponsoring your stay in Indonesia? | `Enum`: `INDONESIAN_GOVERNMENT_OR_STATE_BODY`; `ACCREDITED_PRIVATE_INSTITUTION`; `SELF_SPONSORED_NO_LOCAL_SPONSOR` | `APPLICANT-KNOWABLE` | `E33B` versus `E33C` discriminator | Permen Imipas / Kepmen M.IP-08/2025 — generic; no pinpoint supplied |
| `person.birth_date` (proposed as `applicant_date_of_birth`) | What is the applicant's date of birth? | `Date` (`YYYY-MM-DD`); derive `derived.is_minor` as `age < 18` relative to the application date | `APPLICANT-KNOWABLE` | Activates the minor-status rule; supplied lane does not name the affected product codes | UU 6/2011 Art. 31 & Art. 39 — generic application; no pinpoint support for the asserted age rule supplied |
| `family.legal_guardian_accompaniment_status` (`legal_guardian_accompaniment_status`) | Will the applicant be living in Indonesia with a parent or legally designated adult guardian? | `Enum`: `ACCOMPANIED_BY_PARENT_OR_LEGAL_GUARDIAN`; `UNACCOMPANIED_WITH_NOTARIZED_LOCAL_GUARDIAN_DEED`; `UNACCOMPANIED_NO_GUARDIAN` | `APPLICANT-KNOWABLE` | Forces `MANUAL HUMAN REVIEW` / abstention for `UNACCOMPANIED_NO_GUARDIAN`; supplied lane does not name the affected product codes | UU 6/2011 Art. 31; “Permenkumham Protection Standards” — vague; no pinpoint supplied |

The lane's source identifiers use snake case; proposed dotted paths above follow the existing `FactPath` convention. Their names, namespaces and enum membership remain contract decisions after primary-source verification. Do not treat `sponsor.indonesian_tier` as a rename of the existing `sponsor.type` until the enum mapping is legally and technically reviewed.

## Extension strategy

Use **additive-optional-first**, retaining `extra="forbid"`, with a lightweight fact-schema capability fence. Do not use `extra="ignore"`: it would silently discard new legal facts and typos. Do not use an untyped extension bag: that weakens validation, provenance and typo detection. Full parallel v7/v8 schema negotiation is unnecessary for the single Next.js writer; use capability negotiation and a controlled down-conversion retry.

The candidate delta `ΔF` is accepted by the reader only after it has passed the legal precondition above. An omitted new key normalises to `NOT_ASKED`; an explicit `"UNKNOWN"` means the question was asked but no determinate answer was obtained; a known enum/date is legally usable evidence. `null` must be rejected or retained as a separately specified state: it must never ambiguously collapse omission and `UNKNOWN`.

`UNKNOWN` and `NOT_ASKED` both evaluate as non-TRUE and cannot establish eligibility, but remain distinct in the trace. `UNKNOWN` is an applicant/evidence gap. `NOT_ASKED` is an interview/version coverage gap. A trace must never blame the applicant for a question the system did not ask.

Deploy in this exact order, still in `SHADOW`:

1. **Backend reader first.** Add optional-in-presence `ΔF`, preserve `extra="forbid"`, distinguish omission from `UNKNOWN`, and keep sequence 7 authoritative and inert to `ΔF`. Advertise reader revision 8 only after every backend instance is healthy; capability represents the fleet minimum.
2. **Frontend writer second.** Add the four discriminator question families. Send revision-8 fields only when the backend advertises revision 8. Send `NOT_ASKED` for unreached branches; send `"UNKNOWN"` only after presentation of the question. On schema rejection, strip **only** the new fields and retry once as a revision-7 payload.
3. **Signed pack sequence 8 last.** Its manifest declares required FactPaths, minimum reader revision and compatibility base hash. Activate only after fleet-wide reader readiness, observed revision-8 interview traffic, and the whole-pack proof below. Pack activation needs no deploy; it is therefore not evidence that the frontend can supply the facts.

Mismatch behaviour is intentional and reversible:

| Runtime disagreement | Required behaviour | Reversibility |
| --- | --- | --- |
| New backend; old frontend | Missing `ΔF` becomes `NOT_ASKED`; sequence 7 ignores it and its verdict is unchanged. | Revert backend before writer; after writer, lower capability first and let clients down-convert. Prefer retaining acceptance as a compatibility tombstone while disabling semantics. |
| New backend; mixed frontend | Sequence 7 ignores additional facts. | Revert the frontend; v7 payloads remain accepted. |
| Sequence 8; stale frontend/tab | New facts remain `NOT_ASKED`; existing verdicts remain unchanged and only the eleven new paths remain unresolved. | A new pack must preserve the compatibility identity; stale clients do not receive a false support. |
| Reverted backend; new frontend | Capability selects revision 7; a stale capability cache is protected by one down-converted retry. | The frontend can resume v7 payloads without a terminal 422. |

For every old-vocabulary payload `x`, let `UΔ` set all new facts to `UNKNOWN`, `NΔ` omit them (thus `NOT_ASKED`), and let `D` be the normalised business verdict excluding IDs, timestamps, pack metadata and trace hashes. Before activation the following identities are required:

```text
D(P8, x ⊕ UΔ) = D(P7, x)
D(P8, x ⊕ NΔ) = D(P7, x)
```

Thus vocabulary expansion alone cannot change an existing `SUPPORTED` product, final state, review precedence or candidate ordering. A known discriminator may separate siblings; that is new evidence. New paths must not enter GLOBAL review rules that can mask existing support, and cannot alter already-supported products unless separately justified by new evidence.

For proof, extract every enum member, membership boundary, numeric/date threshold and operator from sequences 7 and 8; build finite equivalence partitions; solve every satisfiable region once with `ΔF=UNKNOWN` and once with `ΔF=NOT_ASKED`; and require UNSAT/no counterexample for “sequence 7 supported, sequence 8 not identical”. Supplement this with gold personas, production-safe replays, randomised property tests, and TRUE/FALSE/UNKNOWN witnesses for every new rule.

## PR sequence

| PR | Independently shippable change | CI must prove | Independent reversal |
| --- | --- | --- | --- |
| 1. Backend contract | Add optional-in-presence `ΔF`; retain `extra="forbid"`; preserve omission/`UNKNOWN` distinction; advertise reader revision 8 only after fleet readiness. Sequence 7 ignores `ΔF`. | Existing payload corpus still returns 200 with byte-equivalent normalised verdicts; reviewed new facts validate; unknown aliases still 422; omission and `UNKNOWN` remain distinct; OpenAPI additions are non-required; cache/idempotency includes schema and pack identity. | Ordinary revert before PR2. After PR2, lower advertised capability first; frontend down-converts/retries. Retain acceptance as a compatibility tombstone where safe. |
| 2. Frontend interview | Add the four discriminator question families and capability-gated revision-8 writer. | Contract-generated payloads validate; old-backend simulation succeeds via v7 fallback; mixed old/new bundles do not terminally 422; edit/restart posts the final mapped payload; each answer maps to exactly one legally reviewed enum. | Revert frontend: it sends v7 payloads accepted by the expanded backend. |
| 3. Rule-pack sequence 8 | After primary-text legal verification, sign a pack referencing `ΔF`, with positive and sibling-negative controls for all eleven products; activate in `SHADOW` only. | Signature/JCS/hash-chain and bitemporal checks; compiler dependency manifest; exact `UNKNOWN` and `NOT_ASKED` differential proof; eleven positive witnesses; sibling mutual-exclusion; gold replay; no new GLOBAL review mask. Activation preflight proves observed revision-8 writer telemetry, not merely reader capability. | Never reactivate sequence 7 through anti-rollback. Prepare sequence 9 with sequence-7 semantics and sequence 8 as previous hash; activate it prospectively. `OFF` is the emergency kill switch. |

## Red-team findings

Ranked findings preserved from the architecture lane:

1. **Critical — a pack can outrun the frontend.** Pack activation needs **no deploy**. Backend readiness is not writer readiness. Activation needs observed revision-8 interviews; the `UNKNOWN`/`NOT_ASKED` differential identity remains the primary safety control.
2. **Critical — cache or idempotent decisions can cross pack boundaries.** Cache keys include `ruleset_activation_id` or pack hash, engine version and normalised fact states. Stored decisions remain immutable with their original pack/schema meaning. A retry with the same idempotency key returns the original decision; changed facts need a new key; same key with different payload is rejected.
3. **Critical — guardian repair can conflict with “never regress a supported product”.** If sequence 7 supports a minor solely through a mis-keyed sponsor boolean, “never regress” conflicts with “never recommend an unsupported product”. Do not bury this in sequence 8. Either preserve the legacy result only for missing guardian evidence, or make an explicit safety correction with legal approval, a recorded counterexample and a reset gate.
4. **High — the ≥1,000-request G-a evidence window becomes semantically MIXED.** Partition evidence at least by `(ruleset_activation_id, fact-schema revision, interview build/version, engine version, traffic source)`. Sequence-7 and sequence-8 rows cannot jointly satisfy the gate. Start a fresh ≥7-day/≥1,000-request window after sequence-8 activation and frontend stabilisation. **OWNER DECISION:** this directly determines whether the `ENFORCE` gate can be reached at current organic traffic; do not assume the impact is acceptable.
5. **High — `UNKNOWN` and `NOT_ASKED` can be collapsed accidentally.** They may share three-valued evaluator truth, never produce support, and yet must retain distinct audit/remediation meaning. `NOT_ASKED` is a system coverage failure; `UNKNOWN` is answered-but-unresolved.
6. **High — a rolling backend can advertise revision 8 too early.** Report the minimum supported revision across the fleet. Keep it at 7 until all instances are healthy; frontend retry remains the final guard.
7. **Medium — new fields can change fingerprints and inflate evidence.** Keep full-input audit hashes separate from decision cache/idempotency semantics. Retries, edits and rollout payload-shape changes must not count as distinct real applicants.
8. **Medium — correct plumbing does not prove correct questions.** Each enum needs primary-source-backed wording, contradiction tests and positive/negative sibling pairs. A mapper error can make an unreachable product dangerously reachable.

## Open owner decisions

The following are owner-gated; this design does not choose them.

- **Legal authorisation:** accept or reject each proposed discriminator only after article-by-article primary-source verification, including its FactPath name, enum values, question wording and product mapping.
- **Unidentified four products:** identify the four minor-affected products included in “11 of 38”; do not author a broad guardian rule before their intended scope is explicit.
- **Guardian conflict:** rule whether missing guardian evidence preserves legacy support temporarily, or whether sequence 8 may make the explicit safety correction that regresses a currently supported minor case; record the approved legal basis, counterexample and any evidence-gate reset.
- **G-a cohort reset:** accept that sequence-8 activation and frontend stabilisation starts a fresh ≥7-day/≥1,000-request evidence cohort, or explicitly define another defensible gate policy. The decision affects ENFORCE reachability at current organic traffic.
- **Activation threshold:** define what observed revision-8 writer telemetry is sufficient to permit pack activation; reader capability alone is insufficient.
- **Null semantics:** decide whether JSON `null` is rejected or represented as a distinct fact state; it cannot be allowed to collapse into omission or `UNKNOWN`.
- **Schema placement:** approve the reviewed mapping of lane proposals to existing paths (`person.birth_date`/`derived.is_minor`, `sponsor.type`) or author genuinely new paths only where their semantics differ.

## Adversarial review

The GPT-5.6-sol architecture lane was the adversarial pass over the Gemini regulatory proposal. It accepted the need for a reviewed discriminator delta but rejected any implementation that weakens the closed vocabulary, assumes backend deployment proves frontend readiness, or treats generic legal citations as sufficient authoring authority.

Surviving objections and dispositions:

| Objection | Disposition in this design |
| --- | --- |
| Generic regulatory references cannot ground operative rules. | Unresolved; primary-source, article-level verification is a hard precondition before any signed-pack rule. |
| A closed `extra="forbid"` contract can break in either deploy order. | Resolved structurally by additive optional fields, a fleet-minimum capability fence, controlled v7 down-conversion and sequence-8-last activation. |
| Omission and `UNKNOWN` become indistinguishable in evaluator/audit handling. | Resolved as a required contract and trace invariant; both fail closed, but remain semantically distinct. |
| Pack activation requires no deploy and may therefore outrun the writer. | Unresolved operationally until owner-approved telemetry threshold and observed revision-8 traffic exist; activation is blocked on them. |
| Sequence-7 and sequence-8 traffic could be pooled to reach G-a. | Rejected; evidence must be partitioned and a fresh post-activation cohort is required, pending the owner decision on the resulting traffic cost. |
| Guardian repair may make a previously supported result no longer supported. | Unresolved owner/legal ruling; must be explicit, not hidden in the pack. |
| Cache, idempotency and fingerprint changes can misattribute decisions or inflate evidence. | Resolved only when PR1 CI and runtime implementation include pack/schema/engine identity and prevent retry/edit inflation. |
| The lane’s FactPath names and sponsor enum mapping may not match the existing closed vocabulary. | Unresolved pending legal and contract review; the table labels them proposed rather than approved. |
