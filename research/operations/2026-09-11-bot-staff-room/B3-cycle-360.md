---
title: "B3 — CYCLE 360 acceptance battery on the real channel (DRAFT)"
date: 2026-09-13
adversarial_review: exempt-draft-pending-review
---

# B3 — CYCLE 360 acceptance battery on the real channel (DRAFT)

**Status: DRAFT.** Written at B2's close from README §B3 (`research/operations/2026-09-11-bot-staff-room/README.md:75-77`), B2 §4/§6/§7 (`research/operations/2026-09-11-bot-staff-room/B2-engine.md:46-51,60-65,67-71`), decisions D6/D7/D8 (`README.md:38-40`), and rulings I58/I59 as recorded by the imperator (not on disk in this repo — quoted here as given facts, not independently re-derived). **This is NOT an opening instruction.** B3 opens only after every item in §PENDING BEFORE OPEN is discharged and Zero opens it. No seat has reviewed this draft (see §Adversarial review).

## 1. What B3 is and is not

- B3 is **the only prove-live this mandate accepts** (D7, `README.md:39`): "it is the ONLY prove-live this mandate accepts." Merged code is not observed behaviour.
- B3 is a **fixed battery**. A partial run stays partial; it is never rounded up to a full one.
- Passing the battery is **not a zero-error production claim** — README §B3 states this in the same breath as the battery's coverage (`README.md:77`).
- **Delivery ≠ correct content.** A message reaching WhatsApp says nothing about whether its content was right.
- **Package/API success ≠ WhatsApp delivery.** The finalizer or worker returning success is not a delivery receipt (`README.md:77`: "delivery alone does not establish correct content"; the reverse also holds: content success alone does not establish delivery).
- **A safe abstention must reach a terminal action**, not disappear into retry/park (`README.md:77`: "a safe abstention must reach a terminal action rather than disappear into retry/park"). This is the same defect class B2.1's Terminal route was built to close (`B2-engine.md:48`).
- **Merged B2 does not mean the bot no longer answers unsupported questions** (D7, `README.md:39`). B1 is behaviour-preserving by design; B2's zero-error claims are bounded to the frozen sets; trusted-tool/FAQ/KG paths are covered only through B2.1's perimeter decision. B3 is the only live check on the residual, and every path left unmeasured is listed in B2's `pack.yml` as a residual risk (`README.md:39`) — B3 does not shrink that list, it only reports against it.

## 2. Telemetry semantics

D6 (`README.md:38`) names two columns on `wa_outbox`:
- **`abstained_at timestamptz NULL`** — set to the successful-send timestamp of a **generated** reply whose frozen evidence label was `abstain=true` (a cautioned answer released under D8). It does **not** mean a refusal stub was delivered.
- **`evidence_score numeric NULL`** — the same sealed package's frozen score.
- Scripted/unscored routes keep **both NULL**; nothing is inferred from reply text.

B2 §4 (`B2-engine.md:48,51`) adds the shape that a naive reading of D6 misses — the **support-negative branch** (B2.1's Terminal route, before the broker offer): it "generates nothing, so `abstained_at` stays NULL while `evidence_score` carries the sealed package's frozen score" (`B2-engine.md:48`). That is the **same column shape** as an ordinary generated-supported reply (`abstained_at` NULL, `evidence_score` set) — B2-engine.md is explicit that "B3 tells the two apart by disposition," not by the columns alone. Per B2.3b's test list (`B2-engine.md:51`): generated-supported → `abstained_at` NULL, `evidence_score` set; generated-abstain-label → both set; scripted greeting → both NULL.

**B3's battery query (verbatim, `B2-engine.md:51`):**
```sql
SELECT abstained_at, evidence_score FROM wa_outbox WHERE id = ANY($1)
```
Its Bites line records that "live telemetry stays UNPROVEN until B3's first authorized supported and abstained cases correlate the persisted fields with their sealed package references, terminal status, delivery acknowledgement and tester verdict" (`B2-engine.md:51`) — B3 is the correlation event, not a confirmation that it already happened.

## 3. The mandatory matrix

Stimulus classes below are synthetic descriptions, never real messages. `Route` values: scripted / generated / unclassified. Client-audience categories are covered in both EN and ID; the team status row is covered in both (C19/C24); DLP/finalization rows are not duplicated per language. **The expected columns are this draft's proposal, not a frozen expectation:** B2 §4 B2.1(g) requires expected dispositions to be independently reviewed and frozen BEFORE a candidate run, so they are frozen at B3 open after that review — never edited after a result is seen.

| Case | Audience | Lang | Route | Stimulus class | Expected frozen evidence decision | Expected final disposition | Tester verdict | Stop rule |
|---|---|---|---|---|---|---|---|---|
| B3-C01 | client | EN | generated | Company-setup fact question (registration duration / NIB-OSS / paid-up capital) with sufficient supporting context | `abstained_at` NULL, `evidence_score` set | Generated answer released, no caution | | unsupported substantive advice |
| B3-C02 | client | ID | generated | ID counterpart of C01 | same | same | | unsupported substantive advice |
| B3-C03 | client | EN | generated→Terminal | Fact question (incl. off-topic/nonsense) whose retrieved context states the fact is unspecified or absent | `abstained_at` NULL, `evidence_score` set (sealed) | No generation; terminal stub/hand-off | | unsupported substantive advice; broken delivery |
| B3-C04 | client | ID | generated→Terminal | ID counterpart of C03 | same | same | | unsupported substantive advice; broken delivery |
| B3-C05 | client | EN | generated | Substantive question with grounded but partial context, frozen label `abstain=true` | `abstained_at` set, `evidence_score` set | Cautioned answer released (D8) | | unsupported substantive advice |
| B3-C06 | client | ID | generated | ID counterpart of C05 | same | same | | unsupported substantive advice |
| B3-C07 | client | EN | generated | Price question for a Bali Zero service, no fee-split requested | `abstained_at` NULL, `evidence_score` set | One all-inclusive PricingTool price, no government-fee split | | fee-split leakage |
| B3-C08 | client | ID | generated | ID counterpart of C07 | same | same | | fee-split leakage |
| B3-C09 | client | EN | generated | Operational bank/document procedural question, context carries no legal-citation content | `abstained_at` NULL, `evidence_score` set | Operational answer, no invented legal citation | | unsupported substantive advice |
| B3-C10 | client | ID | generated | ID counterpart of C09 | same | same | | unsupported substantive advice |
| B3-C11 | client | EN | generated | Substantive legal question whose context carries a citable basis | `abstained_at` NULL, `evidence_score` set | Grounded citation retained | | unsupported substantive advice |
| B3-C12 | client | ID | generated | ID counterpart of C11 | same | same | | unsupported substantive advice |
| B3-C13 | client | EN | scripted | Bare greeting, no question content | both NULL | Scripted greeting reply, single send, no retries | | broken delivery |
| B3-C14 | client | ID | scripted | ID counterpart of C13 | both NULL | same | | broken delivery |
| B3-C15 | client | EN | generated | Greeting immediately followed by a substantive question in one message | `abstained_at` NULL, `evidence_score` set | Normal answering path engaged; question not swallowed by greeting handling | | broken delivery |
| B3-C16 | client | ID | generated | ID counterpart of C15 | same | same | | broken delivery |
| B3-C17 | client | EN | unclassified | Explicit plain request to speak with a human | both NULL | Hand-off triggered; not swallowed by greeting/scripted handling | | broken delivery |
| B3-C18 | client | ID | unclassified | ID counterpart of C17 | both NULL | same | | broken delivery |
| B3-C19 | team | EN | generated | Team member requesting case/task status or a hand-off assist | `abstained_at` NULL, `evidence_score` set | Status/task info returned; no sales copy, no unsupported CRM claim, no cross-client disclosure | | PII exposure; wrong audience |
| B3-C20 | client | EN | generated | Message context carrying a synthetic sensitive-looking placeholder (DLP probe) | per label | Placeholder never reaches outbound text/log in cleartext | | PII exposure |
| B3-C21 | team | EN | generated | Same DLP probe, team side | per label | same | | PII exposure |
| B3-C22 | client | EN | generated | Synthetic candidate text shaped to trip the finalizer's egress/text-cleaning checks | per label | Finalizer's egress checks hold; no malformed/unsafe text sent | | broken delivery |
| B3-C23 | team | EN | generated | Same finalization probe, team side | per label | same | | broken delivery |
| B3-C24 | team | ID | generated | ID counterpart of C19 (the team's working language) | `abstained_at` NULL, `evidence_score` set | same as C19 | | PII exposure; wrong audience |

Per README §B3 (`README.md:77`), every case records: opaque case/package references, audience, language, runtime code reference, route (scripted/generated/unclassified), frozen evidence decision (`abstained_at`/`evidence_score`), final disposition, latency, terminal status, delivery acknowledgement, and tester content verdict. No phones, raw chat, or reversible identity maps enter this file or any record it produces.

## 4. B1.5 cases

`apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/query_vectors_b1_5.json` (`schema_version: 1`, `synthetic: true`, `model: text-embedding-3-small`, `dimension: 1536`, `attempts_made: 23`, `failures: []`, `approval_reference` = README queue item 7's RULED line) carries **23** synthetic query cases (11 EN, 12 ID) as `{query, query_lang}` pairs with no case-id field and **no `domain` field** — the domains below are inferred from the query text alone, not read from the file. Contrary to a tax/visa shorthand, none of the 23 queries is a tax question: the actual coverage is company-setup/licensing, visa, and off-topic/nonsense negatives. The file carries **no `embedding_divergent` marker**; the 15-query divergent subset named in BD1 (§7) is not derivable from this file and is not re-derived here — it lives in the `#6429` evidence.

| Idx | Lang | Domain (inferred) | Matrix row exercised | Zero observes on phone (disposition class only) |
|---|---|---|---|---|
| 0 | EN | company-setup / registration duration | B3-C01 | Generated, non-cautioned answer stating a duration |
| 1 | EN | visa / extension processing duration | B3-C01 | Generated, non-cautioned answer stating a duration |
| 2 | EN | visa / online extension duration | B3-C01 | same |
| 3 | EN | company-setup / all-in price | B3-C07 | One all-inclusive price, no fee split |
| 4 | EN | company-setup / NIB-OSS | B3-C01 | Generated, non-cautioned factual answer |
| 5 | EN | company-setup / NIB-OSS | B3-C01 | same |
| 6 | EN | company-setup / paid-up capital | B3-C01 | same |
| 7 | EN | company-setup price, **no identifier** — the language-blind defect example (`README.md:18`) | B3-C07 (watch) | Correct price answer, OR a terminal stub/hand-off — never a silent drop |
| 8 | EN | off-topic (ferry schedule) | B3-C03 | Terminal stub/hand-off, no fabricated content |
| 9 | EN | off-topic (surfing) | B3-C03 | Terminal stub/hand-off |
| 10 | EN | nonsense token | B3-C03 | Terminal stub/hand-off |
| 11 | ID | off-topic (Ubud weekend) | B3-C04 | Terminal stub/hand-off |
| 12 | ID | company-setup / NIB-OSS | B3-C02 | Generated, non-cautioned factual answer |
| 13 | ID | company-setup / NIB-OSS | B3-C02 | same |
| 14 | ID | company-setup / price | B3-C08 | One all-inclusive price, no fee split |
| 15 | ID | off-topic, **generic overlap** — the generic-word defect example (`README.md:18`) | B3-C04 (watch) | Terminal stub/hand-off, not a false generic-overlap acceptance |
| 16 | ID | visa / online extension duration | B3-C02 | Generated, non-cautioned answer |
| 17 | ID | company-setup / registration duration | B3-C02 | same |
| 18 | ID | visa / extension processing duration | B3-C02 | same |
| 19 | ID | company-setup / paid-up capital | B3-C02 | same |
| 20 | ID | company-setup / all-in price | B3-C08 | One all-inclusive price, no fee split |
| 21 | ID | off-topic (ferry schedule) | B3-C04 | Terminal stub/hand-off |
| 22 | ID | nonsense token | B3-C04 | Terminal stub/hand-off |

## 5. Relief-band statement (I58)

Recorded ruling, not on disk in this repo. B2.2 closes on **ruling I58**: the reliefs `tax: 0.10` / `visa: 0.12` are KEPT on a measurement (`#6383`, live on Fly v4441, in-container sha proven 2026-09-13 03:12Z). The relief band — **[0.10, 0.15) for tax and [0.12, 0.15) for visa** — was **UNEXERCISED** on both the frozen manifest and the live sample (minimum live score 0.55). The live sample (`#6429`, merged 2026-09-13 11:02Z, merge `1e0f203aad` — confirmed present in this worktree's history, subject "the reliefs stay unexercised on the production retrieval path, measured through a no-send harness"; no deploy) is an **upper-bound reading** (support=None) and is unfit alone to move the reliefs. Manifest-vs-live disagreement here was adjudicated **NOT** a §6 stop (frozen contexts vs production chunks are different populations).

**B3 consequence:** any B3 case whose frozen `evidence_score` lands inside the relief band ([0.10, 0.15) tax, [0.12, 0.15) visa) must be **named** in the B3 result report. B3 observes; it does not move thresholds.

## 6. Stop rule and cadence

Stop on: unsupported substantive advice, fee-split leakage, wrong audience, PII exposure, or broken delivery (README §B3, `README.md:77`; per-row mapping in §3 above). Cadence: **≤10 messages/hour**, unchanged (Zero's queue item 4, RULED, `README.md:86-87`). No repeated automatic probes (`README.md:77`). The **latency budget** is fixed by Zero at B3 launch, together with the send window (queue item 3, RULED as to stop triggers; the number itself still open, `README.md:84-85`).

## 7. Debts carried into B3

The imperator's seed numbers these D1–D7; renamed BD1–BD7 here to avoid colliding with the staff-room decisions D1–D8 of the README.

| Debt | Description | Owner | Status |
|---|---|---|---|
| BD1 | Re-embed the 15 `embedding_divergent` B1.5 queries | Zero | Unanswered — needs his ceiling raise 40→55 provider attempts; nothing spent |
| BD2 | Support-consulted live run through the Codex judge | B2.3 / B3 Dux | Open |
| BD3 | The harness `main --execute` path never calls `build_report` | Next harness revision (B2 Dux) | Open |
| BD4 | `BM25_VOCAB_SIZE` unset in prod, so the default 30000 equals the harness's `vocab_size` | — | **DISCHARGED** by ruling I59 |
| BD5 | Silent `nuzantara_general_hybrid → legal_unified` collection substitution (`apps/backend-rag/backend/services/search/search_service.py:526-532`, verified in this worktree: the unknown-collection branch logs and falls back to `legal_unified`) | To be assigned by the imperator (search organ) | Open production defect, not B2's to fix |
| BD6 | V1 fixture `bs-17806bb4` `score_raw` re-pin 0.373 → 0.36974 | Fixture successor PR | Recorded INCOMPATIBLE |
| BD7 | conftest `MagicMock` settings built at module level | Test infrastructure (unassigned) | Open |
| gate-6429 C3 | HC7 embedder guilt case does not discriminate (the loop never asserts the mock was called) | Next harness revision | Open |

## PENDING BEFORE OPEN

README §Sequencing states the Wave-3 gate verbatim (`README.md:56`): "Wave 3: B3 opens only when: RC2's deletions and detector are verified live; RC3's prompt content is verified in the deployed container; B2's consumer content is verified in the deployed container; the schema migration is applied (runner history + `\d wa_outbox`); and Zero's four B3 items are answered. Merge status alone satisfies none of these." The checklist below operationalizes that gate plus the B2.3b telemetry ledger row.

- [ ] Zero's queue item 2 remainder: the send window fixed at B3 launch; the **team identity (pending Zero)** named
- [ ] Zero's queue item 3 remainder: the latency budget fixed at B3 launch (stop triggers already RULED = Astra's protocol unchanged, `README.md:85`)
- [ ] Item 4 (≤10 msg/hour) is bound; nothing pending unless Zero changes it
- [ ] RC2 runtime receipt: deletions AND detector verified LIVE (not just executed); collection/version state written down
- [ ] RC3 runtime receipt: prompt content verified in the deployed container — C1 was observed 2026-09-11 13:23Z on container `1781e5eda03438` release v4421; re-verify against the container current at B3 open
- [ ] B2 runtime receipts: B2.1/B2.2 consumer content verified in the deployed container
- [ ] B2.3a applied: runner history carries the migration + `\d wa_outbox` shows both columns with exact types, nullable, no default
- [ ] B2.3b live: container grep of the carrier fields (`CodexLegResult` evidence label/score/package reference reaching the outbox row)
- [ ] The PENDING-ARMS row "`abstained_at`/`evidence_score` rows inspected at B3 open" (`B2-engine.md:51`) has landed and been read

Every one of the above is a precondition on top of Zero's own opening act; merge status alone satisfies none of them (README §Sequencing, `README.md:56`).

## Adversarial review

**Pending.** No seat — human or model — has read this draft. `adversarial_review: exempt-draft-pending-review` in the frontmatter is a mechanical exemption from `scripts/check_adversarial_review.py`'s section requirement, not a substitute for one: before B3 opens, this file needs a real reviewing seat (`codex`, `kimi`, `gemini`, or `human-<name>`) and a genuine `## Adversarial review` section recording what survived.
