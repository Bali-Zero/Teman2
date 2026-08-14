---
date: 2026-08-15
domain: visa
client_case: none — Visa Oracle v2 G-b family refuter (active sequence 7)
sources:
  - research/visa/2026-08-12-gold-replay-live-report.json
  - research/visa/2026-07-24-w2-factbase-e31-full.md
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
  - apps/backend-rag/backend/tests/services/visa_engine/_gold_fixtures.py
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D
adversarial_review: kimi-k3
status: DRAFT — evidence verified; owner/legal decision required before RulePack authoring
---

# Visa Oracle G-b family refuter — E31B and E31D

**Date:** 2026-08-15  
**Scope:** active RulePack sequence 7 (`2026.8.11`, payload SHA-256
`3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82`)  
**Mode impact:** none — evidence only; no RulePack, signing, activation, ENFORCE,
secret, data or deployment change  
**Disposition:** **BLOCK / unresolved G-b defect** until the family fact vocabulary,
official-source interpretation and signed-pack change are approved independently

## Executive result

The sequence-7 replay result for gold personas 7 and 8 cannot be accepted as a
routine catalogue expansion. Two production-pack rule families manufacture
family products without the facts named by the products and their official
requirements:

- **E31B** treats any known `family.sponsor_status_code` as sufficient. The
  gold baseline is the concrete sentinel `KNOWN("NONE")`, which therefore
  passes even though the product is specifically for the spouse of an
  ITAS/ITAP holder.
- **E31D** has three SUPPORT rules whose effective predicate is only
  `intent.purposes intersects ["FAMILY"]`. It therefore offers a stepchild
  route to an adult spouse without stepchild, WNI-parent, birth-certificate or
  parents'-marriage evidence.

This is fail-open product manufacture, not merely an expected mismatch between
the small gold fixture catalogue and the 38-product live catalogue. G-b remains
red until these rows are fixed or Zero/legal explicitly accepts a different,
officially grounded interpretation in writing.

This finding explicitly supersedes the 2026-08-09 audit's description of the
E31D purpose-only rules as "redundant but harmless". That judgment was made
while broader review rules still masked the product; the active sequence-7
replay now proves that E31D reaches `SUPPORTED_CANDIDATES` for these witnesses.
The canonical fixture changed after that audit only to add the unrelated
`sponsor.type=UNKNOWN` rollout fact; its commit records that all gold decisions
remained unchanged. The changed reachability is therefore not attributed to a
persona-7/8 fixture rewrite.

## Reproduced guilt on the real sequence-7 source

The evaluator was run locally at the pack's pinned witness time
`2026-08-11T12:00:00Z`, using the real sequence-7 source and the canonical gold
fact builder. No database or network was involved. This rerun is corroborative;
the durable replay provenance is the cited machine-readable
`2026-08-12-gold-replay-live-report.json`, which pins the active pack identity,
payload hash, all 20 outcomes and the run timestamp.

| Witness | Relevant facts | Sequence-7 result |
|---|---|---|
| Gold persona 7 shape | adult; FAMILY; relation `SPOUSE`; sponsor nationality `ID`; marriage registered; sponsor confirmed; baseline sponsor status `NONE` | `SUPPORTED_CANDIDATES [C1, E31A, E31B, E31D]` |
| Gold persona 8 shape | adult; same facts, but marriage registration `UNKNOWN` | `SUPPORTED_CANDIDATES [C1, E31D]` |

The results reproduce `research/visa/2026-08-12-gold-replay-live-report.json`.
They also correct the abbreviated table in the companion Markdown report:
persona 7 included **E31D** as well as C1/E31A/E31B.

### E31B predicate defect

`el.e31b-spouse-itas-support` and `el.e31b-sponsor-itas-itap` require:

- FAMILY purpose;
- spouse relationship;
- registered marriage; and
- `family.sponsor_status_code` merely `known`.

The last condition does not test ITAS, ITAP or an equivalent closed set. The
shared gold baseline deliberately uses `KNOWN("NONE")`, so the rule's named
legal discriminator is absent while both E31B rules support the product.

### E31D predicate defect

The effective predicates of all three E31D support rules are identical:

- `el.e31d-stepchild-support`: FAMILY purpose only;
- `el.e31d-step-parent-relation`: FAMILY purpose plus a nested duplicate of
  the same FAMILY-purpose predicate;
- `el.e31d-sponsor-mixed-marriage`: FAMILY purpose plus a nested duplicate of
  the same FAMILY-purpose predicate.

The reason-code names imply step-parent and mixed-marriage checks that the
conditions do not perform. `required_facts` likewise contains only
`intent.purposes` for all three rules.

## Official-source check (retrieved 2026-08-15)

Primary operational pages:

- [E31B — Visa Keluarga Suami/Istri Pemegang ITAS/ITAP](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B)
  identifies the product as the spouse route for an ITAS/ITAP holder, requires
  a sponsor and requires marriage registration/certificate evidence.
- [E31D — Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D)
  identifies the product as the stepchild route in a lawful WNA-WNI mixed
  marriage. Its application evidence includes a request from a WNI parent,
  birth evidence, the parents' marriage evidence and the WNI parent's family
  card.

The repository fact-base reaches the same discriminator-level conclusion:
`research/visa/2026-07-24-w2-factbase-e31-full.md` requires ITAS/ITAP sponsor
status plus spouse relationship for E31B, and step-parent plus mixed-marriage
status for E31D. The present sequence-7 predicates implement neither set.

The E31B official page currently contains an internally inconsistent generic
application-document line referring to a WNI spouse. That line must not be
silently resolved by an agent. It reinforces the need for legal/owner review;
it does not make the current `known("NONE")` predicate safe and must be resolved
explicitly in decision items 1 and 5 below.

## Why a direct pack edit is not authorized

The controlling blocker for both products is governance: an agent is not
authorized to invent the legally operative discriminator values or resolve a
conflict in an official source. Zero/legal may determine that E31B can be
repaired more narrowly with an approved closed set over the existing
`family.sponsor_status_code`; that option does not necessarily require a new
fact path. Until that set and its legal meaning are approved, however, a direct
predicate edit would still be an unauthorised guess.

E31D has the additional representational blocker that the current 41-path fact
contract does not express every discriminator needed for a faithful repair:

- `family.relation_to_sponsor` allows `SPOUSE`, `CHILD`, `PARENT`, `SIBLING`,
  `DEPENDENT`, `OTHER`, but not a distinct stepchild relationship;
- `family.sponsor_status_code` is a visa/status-code string, not a closed
  ITAS/ITAP permit-class fact; and
- the contract has no approved, dedicated fact for the exact WNA-WNI
  mixed-marriage/stepchild basis described by E31D.

Changing only the E31D rule conditions would therefore overload existing facts
with new semantics. That would create another legally misleading boundary. If
Zero/legal selects a vocabulary extension, it must follow the durable order
already recorded for such changes: backend reader, frontend writer, signed
RulePack, independent replay and owner-authorized activation. A narrower E31B
predicate repair still requires the signed-pack, replay and authorization
stages even if it does not require reader/writer changes.

The unsigned sequence-8 draft on `main` does not repair this defect: relative
to sequence 7 it changes product pricing records, not the E31B/E31D rules. This
decision package therefore does not collide with an in-flight family-rule fix.

## Required decision package

Zero is the accountable approver, with legal review recorded in the successor
pack PR or an explicitly linked signed decision note. This is decision-gated,
not deadline-gated: before authoring a successor pack, that forum must approve:

1. the authoritative E31B sponsor discriminator, including how ITAS and ITAP
   are represented independently of a specific visa index and how the official
   page's WNI-spouse inconsistency is resolved;
2. the E31D relationship model and the minimum evidence/facts that distinguish
   a stepchild in a lawful WNA-WNI marriage from an ordinary spouse/child
   family intent;
3. unknown/null behavior — it must abstain or request input, never support by
   mere FAMILY intent;
4. whether correcting these false positives resets any signed-pack/replay
   evidence; and
5. the exact official source records and locators to bind to the new rules,
   including a written disposition of the E31B inconsistency rather than an
   agent inference.

## Acceptance criteria for the eventual fix

- With sponsor permit class `NONE`, persona 7 must not return E31B.
- An adult spouse with no stepchild/mixed-marriage evidence must not return
  E31D, regardless of whether marriage registration is known.
- Unknown required family discriminators produce `NEEDS_INPUT` or
  `HUMAN_REVIEW_REQUIRED`, never `SUPPORTED_CANDIDATES` for E31B/E31D.
- Positive E31B and E31D witnesses prove the approved discriminators actually
  influence the outcome (metamorphic guilt and innocence).
- The active-pack gold replay is regenerated and every changed divergence has
  an accepted written disposition.
- No previously accepted non-E31 outcome flips between supported and
  unsupported without its own evidence and written disposition.
- Generator and grader are different agents; the grader pins the exact pack
  hash and verifies CI before any signing or activation handoff.

Until those criteria are met, the safe state remains SHADOW and these two gold
divergences remain unexplained defects, not accepted explanations.

## Adversarial review

Kimi K3 reviewed the complete non-PII artifact through the repository's pinned
no-tools wrapper and returned **SHIP-WITH-FIXES**. Its strongest objection was
adopted: the earlier draft overstated vocabulary expansion as mandatory for
both products. This revision separates the governance blocker shared by E31B
and E31D from E31D's additional missing-fact blocker, and preserves a lighter
owner-approved E31B closed-set option. It also pins replay provenance to the
machine-readable live report, records the post-audit fixture history, promotes
the official-page inconsistency into the decision package, adds a non-E31
regression floor and names the approval forum.

The cross-family challenge did not weaken the disposition. Even the lighter
E31B repair still needs owner/legal approval, a signed pack and independent
replay; E31D still lacks the required relationship semantics. Separately, a
Fable reviewer with repository access reproduced the sequence-7 results,
checked the source/rule predicates and verified the official-page evidence.
Neither reviewer authorized a pack edit, signing, activation or ENFORCE change.
