---
date: 2026-07-18
domain: operations
client_case: none (infrastructure — CRM identity backfill)
sources:
  - local DB nuzantara_dev census (this session, read-only)
  - prod DB nuzantara_rag census via scripts/pg.sh (read-only)
  - .claude/skills/intake corner (LIVE STATE 2026-07-18)
  - apps/backend-rag/backend/services/intake/{auto_attach,writer,client_enricher}.py (re-read this session)
adversarial_review: codex
---

# Identity-backfill — design spec (S4 mandate, 2026-07-18)

**North star (intake corner):** drain the queue with ZERO mis-attribution. The auto-commit
bottleneck is structural: the CRM lacks strong identifiers to corroborate against
(`discovery_refinery_panel_width_is_second_order_2026_07_18`). This mandate fills the keys.

**A wrong identity write is WORSE than a wrong attach**: a mis-backfilled passport number on a
client turns every FUTURE deterministic auto-attach for that number into a confident
mis-attribution. Rigor here is the foundation of everything downstream.

## 1. Census baseline (Legge 7 — the "before")

| Metric | LOCAL `nuzantara_dev` | PROD `nuzantara_rag` |
|---|---|---|
| Active clients | 11,754 | 1,753 |
| passport (normalized ≥6) | **337 (2.9%)** | **1,306 (74.5%)** |
| kitas | 3 | 0 |
| phone_normalized | 10,731 (91.3%) | 1,351 |
| email | 1,048 | 552 |
| no identifier at all | 57 | — |
| passport-dup groups | 17 (36 rows) | — |
| phone-dup groups | 622 (1,286 rows) | — |

Queue: 35,742 `review_pending`; 5,091 carry a doc strong-id; DET_match_now = 2
(20 − 18 drained by refinery-deterministic on 2026-07-18 ✓).

Cross-DB overlap (hash-only, no cleartext PII): 1,247/1,753 prod clients match a local
client (phone 1,209 / exact-name 888 / email 71); 906 phone-pairs are bidirectionally
unique (1:1 both ways).

## 2. The four fuels, ranked by evidence independence

| Fuel | Size | Signals | Verdict |
|---|---|---|---|
| **A. Cross-DB (prod→local)** | **277 STRICT** (+220 fuzzy-name tail) | phone exact 1:1 bidirectional ∧ full-name exact — two independent signals; source is the team-curated prod CRM | AUTO tier (with guards below) |
| **B. Queue docs w/ independent 2nd signal** | 142 sender_phone + 33 folder | doc strong-id resolves candidate + doc-subject-name concordance (LEVA-2/3 gates, already built) | AUTO via existing gates, armed surgically |
| **C. Human-committed docs, pre-enricher** | 7 passport + 6 kitas clients | attach human-validated — but the attach validated the FILE↔client link, NOT the extracted id's ownership (multi-person docs: an akta's page-2 passport may belong to a co-director) | REVIEW-GATED: full human adjudication of all 13 (refuter-c); doc_type restricted to single-subject (passport/kitas) + doc-name↔client-name concordance |
| **D. Queue docs, fuzzy-name-only** | 1,129 proposals / ~482 clients overlap w/ B | candidate found BY name; doc-name concordance is the SAME signal (not independent) | NEVER auto — quarantine/review queue, pre-filled |

Calibration evidence for Fuel A — WITH the refuter's corrections (2026-07-18 council):
among the 906 unique pairs where BOTH sides already have a passport, the name-exact stratum
shows 94 concordant vs 5 divergent; 2 of the 5 have identical DOB (passport renewals).
Honest reading: observed mis-pair 3/99, Wilson 95% CI ≈ [0.6%, 8.5%], measured on a
CURATED stratum (both-sides-passport) that does NOT transport to the target population
(empty-column rows). This number is a LEAD, not a bound (W90 family). Structural
containment therefore does not rely on the rate: it relies on gate 11 (verified:false —
backfilled ids cannot trigger AUTO_COMMIT) + human adjudication of a dry-run sample drawn
from the REAL target shape.

Signal nature (refuter-d, measured): P(name-exact | phone-1:1) = 65.9% on the 906 pairs —
the name gate genuinely rejects 1/3 of phone-matched pairs, so it carries real
discriminating power, but the two signals share a capture source (contact-book style) and
are NOT independent in the Fellegi-Sunter sense. Claim reformulated: phone-1:1 ∧ name-exact
establishes SAME-CONTACT-ENTITY with measured joint specificity; the residual correlated
error channel (shared phone + identical name, e.g. family homonyms) is contained by gate 11,
not by an independence assumption. In known-shared phones (622 local dup groups, 724 pairs),
18% also share the exact name — mostly double-imports of the same contact (dedup leads).

Known traps measured: 89 local clients whose queue docs carry >1 distinct passport
(agency-funnel / family docs — matches the existing `_FUNNEL_*` anti-funnel scar);
14 unique-pair cross-DB passport conflicts; 36 nationality "conflicts" in Fuel A that are
mostly format drift (`italian` vs `italiana`) — nationality corroborates ONLY after
demonym→country normalization, and a surviving conflict demotes to review, never blocks alone.

## 3. Non-negotiable gates (from the scars)

1. **Fill-only, never overwrite.** The backfill writes `passport_number`/`kitas_number` ONLY
   where the target column is empty/short (<6 normalized chars). Conflicting values are a
   REVIEW lead (possible renewal), never an update.
2. **Per-identifier-type thresholds.** Exact passport/kitas equality (normalized
   `[^A-Za-z0-9]→''`, upper, ≥6) is the only "match" for ids. Names: token-overlap
   (`auto_attach._name_concordant`) with a raised bar for identity writes:
   `IDENTITY_BACKFILL_NAME_RATIO=1.0` (exact token-set) for Fuel A auto; <1.0 → review.
3. **Two independent signals or nothing.** Name-only NEVER writes (2026-05-17 scar). The
   signal that FOUND the candidate cannot also be the signal that CONFIRMS it (Fuel D).
4. **Bidirectional uniqueness.** A phone/id used for pairing must be unique on BOTH sides;
   any 1:N or N:1 → quarantine (275 ambiguous prod phones measured).
5. **Anti-funnel.** Clients fed by a sender with ≥8 docs across ≥5 types, or clients with >1
   distinct doc passport (89 measured), are excluded from doc-derived backfill.
6. **Explainability.** Every write carries provenance JSON: source (prod-crm/doc), evidence
   (signal types + ratios), operator tag, batch id — into `clients.custom_fields.identity_backfill`
   (append) so every value answers "why do you believe this?" without a session transcript.
7. **Idempotence + reversibility.** Re-running a batch is a no-op (fill-only + provenance
   check). Every batch writes a rollback artifact (client_id, column, old value=NULL) and is
   reversible by batch id. Soft-deleted clients skipped (writer P0#3 semantics).
8. **Quarantine is a terminal state.** Ambiguous cases land in a dedicated review queue
   (pre-filled proposal + evidence), they are NOT forced.
9. **PII output boundary (Law 2).** Reports/logs/memory carry counts, client_ids, ratios —
   never passport/kitas values, names, phones. Cross-DB comparison runs on md5 hashes.
10. **Cache invalidation** after every mutation batch: `crm_clients_stats`, `crm_practices`.
11. **Provenance-verified matching (the refuter-b antibody — load-bearing).** Backfilled ids
    are born `verified:false` in their provenance record. A strong-id candidate match that
    rests on an UNVERIFIED id must NOT reach AUTO_COMMIT on its own: it yields
    HUMAN_CONFIRM (pre-filled, prioritized) — or AUTO only when a THIRD independent signal
    concords (document subject name match AND sender-phone match). Promotion to
    `verified:true` happens when a committed document carries the same normalized id with
    a concordant subject name (doc-confirmed). This severs the poisoning loop: a wrong
    fill can no longer trigger a confident wrong attach before any human sees it.
    Enforcement lives in the CONSUMER (refinery gate / auto_attach), not only in the writer.
12. **Fill/consume separation in acceptance.** §7 must measure not only "no overwrite" but
    "zero auto-commit rested on an unverified backfilled id" (audit query + injective
    fixture test: write a known-wrong id on a fixture client via the fill path, run the
    auto-attach on a matching doc, assert the gate refuses AUTO).

## 4. Write paths (topology)

- LOCAL `nuzantara_dev` (the intake matcher's store): backfill script runs on Pro against
  127.0.0.1:5432 via asyncpg, same transaction discipline as `client_enricher` (fill-only
  UPDATE with column-existence guard). Local role `nuzantara` already has UPDATE (verified).
- PROD `nuzantara_rag`: NOT written directly. Any prod-side enrichment goes through the
  backend CRM code-path (API on Fly) in a later phase, gated separately. THIS mandate's
  prod use is READ-ONLY (source for Fuel A).
- Direction — ANSWERED by the db-topology sweep (2026-07-18): local `nuzantara_dev` is an
  INDEPENDENT store (born as a manual prod snapshot via `scripts/nuz_db_refresh.sh`, then
  organically diverged through wa-mirror lead-minting + intake OCR enrichment). The two DBs
  do not share a client_id namespace (`crm_push.py:126-134`). Intake's entity-resolution
  candidates come EXCLUSIVELY from local (`routing.py` matchers on the worker pool,
  Law 2) — so raising LOCAL strong-id coverage is precisely what unlocks auto-commit.
  The only local→prod bridge is a lazy per-document phone-upsert (`crm_push.py::
  _ensure_client_on_fly`); no passport/kitas bridge exists. Prod enriches itself via its
  own OCR dispatcher (`crm_enhanced_documents.py`).
- ⚠️ **Refresh trap**: `nuz_db_refresh.sh` is `pg_restore --clean` — a manual re-run DROPS
  the local DB (backfill AND ~10k wa-mirror-only client rows). Mitigation: the backfill
  script is fully re-runnable from live sources (idempotent, no one-shot state); flagged
  to the operator in §Solo-operatore.

## 5. Reuse-first verdict (splink)

Entity-resolution at volume is a solved problem (splink: Fellegi-Sunter/EM, probabilistic).
Evaluated and NOT adopted for the auto tier because:
- The auto tier is DETERMINISTIC BY DESIGN (scar 2026-05-17: probabilistic/name-frequency
  auto-attach is the exact failure mode being cured).
- The volumes at stake for auto (277+142+33+13) are 3 orders of magnitude below where
  splink's EM training pays; the panel-width lesson (2026-07-18) showed adding model power
  adds 0 auto-commits when keys are absent.
- Its natural fit here is REVIEW-QUEUE ORDERING (score = review priority for Fuel D's 1,129
  + the 622 phone-dup clusters). Deferred: quarantine ordering can use trigram similarity
  (pg_trgm already installed) at zero new dependencies; splink reconsidered only if the
  human tail proves too slow to drain.

Primitives REUSED from the repo instead of rebuilt: `auto_attach._name_concordant` /
`_name_tokens` (order-insensitive name compare), anti-funnel thresholds, `writer.plan_commit`
/`execute_commit` (doc commits), `client_enricher.ENRICHMENT_MAP` semantics (schema-drift
guard, never-NULL-overwrite), `intake_commit_audit` audit pattern, pg_trgm.

## 6. Batches (execution order)

0. **GATE-11 first** (consumer safety before any fill): implement the unverified-id gate in
   the consumer path + the injective fixture test proving a wrong fill cannot cascade.
   No batch applies until this test is green (refuter-b).
1. **BATCH-C** (13 clients) — REVIEW-GATED: full per-case adjudication against document
   evidence (doc_type single-subject only, name concordance); ambiguous → quarantine.
   Also proves the write path end-to-end.
2. **BATCH-A** (277 STRICT) — cross-DB fill-only with provenance `verified:false`;
   normalized-nationality conflict demotes to review. Dry-run → hand-validated sample drawn
   from the real target shape (Fable, vs evidence) → apply in lots of 50 with rollback
   artifact + cache invalidation.
3. **BATCH-B** (142+33) — arm LEVA-2/LEVA-3 flags surgically in a batch-process env only
   (never the live daemon), restricted to the measured proposal ids; the doc attach AND the
   enrichment land together via the existing writer path (these ids are doc-confirmed at
   birth → `verified:true`).
4. **QUARANTINE queue** — Fuel D (1,129) + conflicts (89 multi-pass, 14 cross-DB, 17 local
   dup groups) + 220 fuzzy-name tail: pre-filled review items, ordered by trigram score.
5. **WIRE + MEASURE** — refinery tier respects gate 11 (verified-id → AUTO possible;
   unverified → HUMAN_CONFIRM); measure DET_MATCH delta, auto-commit rate delta, queue
   depth delta on a fixed sample.

## 7. Falsifiable acceptance criteria

- Zero writes outside fill-only semantics (audit query proves: no UPDATE changed a non-empty
  normalized id) — verified post-batch by content (W88).
- **Zero auto-commit rested on an unverified backfilled id** (audit query on auto_routed ×
  provenance + the injective fixture test in the repo test suite) — refuter-b boundary.
- Local passport coverage: 337 → ≥550 clients (batches A+B+C) with 100% provenance records.
- DET_MATCH_NOW on the remaining queue rises (new corroboration keys) — measured before/after.
- Auto-commit-eligible rate of the refinery on a fixed sample: measured before/after (with
  gate 11 semantics: eligible = verified id, or unverified + third signal).
- 0 PII values in any artifact produced by this mandate (grep-audited).

## Adversarial review

See §8 below (R1 gate — generator != grader, this design's author is Fable 5, the reviewing
seats are Codex/GLM/Gemini, none of them wrote the design they're reviewing).

## 8. Council verdict + accepted fixes (v3, 2026-07-18)

Council: Codex gpt-5.6-sol xhigh (red-team, 16 findings, NO-GO on v1 tiers) · GLM 5.2
(refuter, 4 falsifications) · Gemini 3.1 Pro (MDM literature width) · Explore (db topology).
Convergent core (all three, independently): **a backfilled id must not become an operative
matching key until independently confirmed** (MDM "error contagion" mitigation = GATE-11).

Verified-on-code findings and accepted fixes:
- **F1 enricher not fill-only** (client_enricher.py:179 — unconditional UPDATE except
  full_name): identifier columns become fill-only in the enricher; a conflicting extracted
  id → logged review lead, never overwrite. (In-perimeter patch.)
- **F2 rollback blind to enrichment + auto_routed** (writer.py:1130 — only `status='routed'`
  reopened; enriched id survives rollback): rollback gains (a) `auto_routed → review_pending`
  transition, (b) CAS de-enrichment of identifier columns written by the rolled-back doc.
- **F3 `_name_concordant` ratio 1.0 ≠ exact** (normalizes by the SMALLER token set): the
  backfill defines its own `exact_token_set_match` (a == b, ≥2 informative tokens) — the
  Fuel A STRICT pairing already used whole-string hash equality, which is genuinely exact.
- **F8 Fuel B ≠ existing gates** (LEVA-2 has no name/anti-funnel leg; LEVA-3 presupposes the
  id already resolves): B is NOT "arm existing flags" — it becomes pre-filled REVIEW items
  through the quarantine queue path, with its own evidence bundle.
- **F11 normalization divergence** (matcher strips only `[\s.\-/]`; census strips all
  non-alnum): SSOT canonicalizer in the backfill; a value whose two normalizations disagree
  is quarantined, and values are written in matcher-compatible form.
- **F13 atomicity**: column value + provenance mutate in ONE UPDATE statement; fill-only
  WHERE + RETURNING = natural CAS; single sequential batch process.
- **F14 rollback vs later human edit**: rollback is CAS on value_md5 + appends a `reverted`
  provenance event (never deletes history).
- **F15 cohort disjointness**: an immutable MANIFEST is computed BEFORE any write — the
  conflict set (89 multi-pass clients, 14 cross-DB conflicts, 17 local dup groups, funnel
  senders) is subtracted GLOBALLY from A/B/C first.
- **F16 md5 enumerable**: cross-DB comparison files use keyed HMAC-SHA256 (ephemeral session
  key), chmod 600, deleted after use; no stable digests in reports. (value_md5 inside the
  DB provenance sits next to the cleartext column itself — no added exposure.)
- F4/F5/F6 (signal non-independence, calibration non-transport): absorbed structurally —
  ALL backfilled values are PROVISIONAL (`verified:false`), never auto-operative; promotion
  only via doc-confirmation or human review. This satisfies the red-team's "A → REVIEW"
  verdict in structural form: the write happens, but its CONSUMPTION is review-gated.
- F9/F12 (attach-validated ≠ field-validated, OCR misreads): BATCH-C adjudicated field-level
  BY EVIDENCE (12/14 promoted, proposals 3470+12923 quarantined — 12923 is the corner's
  known scar case); OCR-derived fills (B/C) stay review-tier.
- F10 (anti-funnel bypass): the backfill cohort filter uses its own exclusions (multi-pass
  clients measured directly, all-decision counting), not the runtime gate.
- **queue-contradiction gate** (implementation-time follow-up, not a numbered red-team
  finding): documentary triangulation against the live queue found that of the 277 Fuel A
  STRICT pairs, 23 are independently CONFIRMED by a queue document (same passport, client
  named as candidate) and 33 are CONTRADICTED (a queue doc names the client with a
  DIFFERENT passport — funnel/family noise). `decide_pair` gained a gate: any local client
  with a contradicting queue-doc passport is excluded from the write (`SKIP
  queue-contradiction`); a confirming doc never blocks and is surfaced as `doc-confirmed`
  in the batch report (validation-sample signal, not a stronger auto tier — still
  `verified:false` per GATE-11 uniformity). Net: ~244 clean pairs enter the first apply lot.

Final tiers (v3): **A = provisional fill (auto-write, review-gated consumption)** ·
**B = pre-filled review** · **C = 12 promoted after field-level adjudication, 2 quarantined** ·
**D = never auto** (unchanged).

## §Meta-pattern (Gear 3 duty)

The malattia-delle-malattie here: **the organism kept trying to solve an identity-data gap
with more inference power** (bigger panels, more re-OCR, wider models) when the missing
ingredient was a KEY, not a judgment. Same family as W89/"exists≠armed": the data existed
(1,306 passports in prod CRM, 127 in committed docs) but was never ARMED into the store the
matcher actually reads. The backfill is literally an arming pass over data the organism
already owns.

## §Solo-operatore

- Restore-vs-reroute decision for the 3 soft-deleted-client proposals (82041/82021/82034).
- Any client-facing contact arising from renewal-conflict findings (Legge 5).
- CRM dedup MERGE of duplicate client records (62130 family): proposals only from this
  mandate; merging records is a business-data decision.
- `scripts/nuz_db_refresh.sh` is now DESTRUCTIVE of live local-only data (~10k wa-mirror
  client rows + all intake enrichment/backfill): its `pg_restore --clean` semantics predate
  the local DB becoming an organism of its own. Recommend retiring or converting it to a
  merge-refresh before it is ever run again. Operator decision.
