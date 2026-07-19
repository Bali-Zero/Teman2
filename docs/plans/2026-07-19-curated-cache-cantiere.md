# Curated-cache cantiere — build plan (verbatim promotion + full-domain fan-out + auto-regen)

> Mandate: Zero 2026-07-19 — "(1) come far diventare le altre visa FAQ verbatim di qualità;
> (2) preparare il prossimo cantiere dei visti + company/tax/property + auto-regenerazione con
> il perfetto workflow tra agenti e LLM."
>
> This plan EXECUTES `research/operations/2026-07-17-full-domain-cache-design.md` (the
> panel-reviewed design — Codex red-team, 5 FATAL + 10 MAJOR, cures specified in its §8).
> It adds what the design predates: the GARUDA visa corpus is now LIVE in prod Qdrant
> (~170 Q&A across 8 lanes: VOA/B1 20, C1, D12, E23 23, E28A 22, E31 20, E33E ~20, E33G 23 —
> all grounding-only by deliberate sink decision), and the multi-LLM pipeline that produced it
> is PROVEN. Read the design doc first; this file only sequences the build.

## The one-line answer to "how do the other visas become quality verbatim FAQ"

**Promotion, not regeneration.** The GARUDA rows already exist at E33 quality (same pipeline,
adversarially refuted, expert-reviewed). What separates them from the FAQ verbatim sink is a
POLICY GATE, not content quality: verbatim serving bypasses the abstain gates, so only rows that
are safe with zero per-request reasoning may enter it. That gate is the design's
`verbatim_eligible` allowlist: **`JELAS` (settled) + non-price + non-client-specific = eligible;
`BERSYARAT`/`DINAMIS`/`KEBIJAKAN_PENYEDIA`/`BELUM_DIATUR_PUBLIK` stay grounding-only forever** —
a "depends on your case" answer served verbatim with no reasoning is a wrong answer waiting for
the wrong client. Quality verbatim = promote the JELAS subset through the Phase-0 safety rails
below; do NOT bulk-copy 170 rows to Redis.

## Phase 0 — safety rails (the 5 FATALs, blocking; 1 backend PR lane)

No verbatim promotion until these land. All small, all in the harvester/cache layer
(`curated_qa_harvest.py`, `notebooklm_cache_service.py`), specified in design §8:

| #   | Fix                                                                                                                                                                                                        | Cures                                                                 |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 0.1 | **Domain-scoped FAQ key + Qdrant point-id** (domain folded into hash/id) + runtime domain-match check before serving a hit                                                                                 | FATAL 1 (cross-domain collision: "what documents do I need" tax→visa) |
| 0.2 | **`verbatim_eligible` field**, default `false`; harvester writes the FAQ sink ONLY for eligible rows; eligibility = `JELAS` ∧ non-price ∧ non-client-specific                                              | FATAL 3                                                               |
| 0.3 | **Per-batch manifest** (file hashes, gate reports, approval) + fail-closed harvester verification + `batch_id` on every row → batch-scoped purge/rollback + two-sink staging/commit marker                 | FATAL 2, MAJOR 9, MAJOR 10                                            |
| 0.4 | **Delta quarantine**: regulatory-watcher candidate match → same-day `verbatim_eligible=false` / FAQ-copy delete (Qdrant copy stays, marked flagged); watcher `partial`/unmapped-domain → alert + fail-safe | FATAL 4, MAJOR 6                                                      |
| 0.5 | **Deterministic pricing detector in the harvester** (currency markers, ranges, "starting from", spelled-out amounts) — refuses price-bearing rows at write time; prices remain PricingTool-only            | FATAL 13→control                                                      |
| 0.6 | **PII source allowlist** enforced by the batch script (NB collections + reviewed dossiers only; never raw `meta_inbox_messages`)                                                                           | FATAL 5                                                               |
| 0.7 | Class-based TTL/`valid_until` + daily age scan; Qdrant `active`/`invalidated_at` + retrieval-time filter; staleness metrics/alerts                                                                         | MAJOR 7, 8, 11                                                        |

Seat: Sonnet implementer in its own worktree; Codex cross-family verify on the diff; Fable final
gate. Guilt+innocence tests per guard (superscar #3 discipline): collision case, conditional-row
rejection, price-row rejection, quarantine same-day, interrupted-batch recovery — the design
§4's revised acceptance matrix becomes this PR's test suite.

## Phase 1 — verbatim promotion pilot (visa, reuses the LIVE GARUDA corpus)

1. **Split the ~170 GARUDA rows by confidence class** (the class is already on every row —
   e.g. VOA/B1 ships JELAS 6 · BERSYARAT 6 · DINAMIS 3 · KEBIJAKAN_PENYEDIA 5). Expected JELAS
   yield: roughly 40-60 rows across the 8 lanes.
2. **Re-gate each JELAS candidate** through the Phase-0 detectors (price, client-specific,
   domain-key) + the hidden gold-set. 100% Fable review for this first promotion batch (it is
   the gold-set nursery for the promotion path).
3. **Load the FAQ sink PROD-side.** Blood-bought gotcha from the GARUDA ship: M5's
   `REDIS_URL=localhost` is NOT prod — loading FAQ from a dev machine writes a sink the bot
   never reads. Reuse the F1b load path that put the 216 E33 keys in prod Redis (fly-ssh
   in-container invocation), with the Phase-0 manifest.
4. **Prove-live**: battery on cached questions (instant hit, correct answer, `faq_cache_hits`
   metric moves) + non-eligible sibling question still routes through the agentic path with
   grounding + abstain. Final seal = Zero's phone test on the real WA number (same gate as F1
   and GARUDA — still pending from the GARUDA ship; fold both into one phone session).
5. **Commit the JSONL corpora to the repo** (`apps/backend-rag/data/curated_qa/`) — design §7.7:
   prod state must be rebuildable from git (today the 216 live only on a Desktop markdown).

## Phase 2 — fan-out lanes (rest of visas + company/tax/property)

Each lane runs the **standard pipeline** (below), in its own worktree, GO-gated separately.
Disjoint files/partitions by construction — lanes parallelize safely.

| Lane | Domain                                                                          | Content source                                                                                                                             | Expert seal    | Note                                                                                                       |
| ---- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------- | ---------------------------------------------------------------------------------------------------------- |
| 2a   | visa — remaining types (KITAP, E31 sub-codes depth, transit/crew, golden/E28B…) | WA catalog 5313 Q&A (PII-scrubbed, Pro-local) + NB-2 + imigrasi primary                                                                    | Surya/Ari      | same shape as GARUDA lanes                                                                                 |
| 2b   | company (process-only first)                                                    | golden_answers seeds + NB-3; **fact-bearing KBLI claims WAIT for GARUDA-FILIERA Phase-2 canonical** (design §6.5 — Zero's sequencing call) | Surya          | never re-derive KBLI facts in parallel                                                                     |
| 2c   | tax                                                                             | NB-4 + tax-dept dossier                                                                                                                    | Surya/tax-dept | PMK 37/2025 material fresh from WR2 work                                                                   |
| 2d   | property                                                                        | NB-5 + Second Home overlap                                                                                                                 | Ari            | MAJOR 14 first: add `property` branch to `classify_query_domain()` + tuned threshold before the lane opens |

**The content bottleneck is expert time, not engineering** (design §6.2): the pipeline DRAFTS
(as it did for GARUDA — questions distilled from real WA corpus, answers grounded on primary
law), the domain expert reviews FINAL client-facing text. An LLM cannot self-certify "vetted".

## The standard per-lane workflow (proven on GARUDA 2026-07-18 — this IS the "perfetto workflow")

```
grounding pack (primary-law facts + divergences, PII-free allowlist)
  → Sonnet GENERATOR (drafts Q&A in E33 CHATKB format, confidence class per row)
  → Codex GPT-5.6 LEGAL REFUTER (adversarial, cross-family — found 4 real blockers on GARUDA)
  → Fable PRIMARY RE-VERIFY (every load-bearing correction re-checked against the source itself)
  → Sonnet ARBITRATOR (applies only verified fixes; sound rows stay byte-identical)
  → Fable GATE (reads contested rows on disk)
  → GLM 5.2 SAFETY SWEEP (second cross-family refuter; DeepSeek seat is DEAD — 402)
  → DOMAIN EXPERT review (Surya/Ari — business seal, Zero relays)
  → converter (parse-validated, 0 empty answers)
  → harvester (Phase-0 rails: manifest, detectors, verbatim_eligible split, batch_id)
  → PROVE-LIVE (by-id retrieval + generation battery + phone test)
```

Cross-family invariant: generator ≠ any refuter's family; the refuters' verdicts are LEADS —
Fable re-verifies against primary sources before anything is applied (W65/W90/W100 line: the
refuter hallucinates, the ground truth ages, agreement lies).

## Auto-regeneration loop (design §2, with §8 quarantine)

Daily, after regulatory-watcher writes `research/regulatory/<date>-delta.json`:
deterministic `service_line→domain` mapping table (no LLM in the routing) → substring match on
`law_refs` across that domain's rows → matches become `_regen-candidates/<date>.jsonl` AND are
quarantined from verbatim THE SAME DAY (fail-safe; Qdrant copy stays, flagged) → next generation
batch re-verifies candidates with priority → W90 discipline: when re-grounding finds the ground
truth itself was stale, the batch report says so and lists invalidated derived surfaces.
`new_today_count==0 ∧ partial==false` → true no-op. `partial==true` or unmapped service_line →
alert, never silent.

## Sequencing & owners

1. **Phase 0** — 1 Sonnet lane, ~1 session. Blocking everything.
2. **Phase 1** — 1 session after Phase 0 (content exists; it's gating + loading). Ends with the
   combined phone test (GARUDA seal + promotion seal).
3. **Phase 2** — lanes open one at a time on Zero's GO per lane (2a first: content pipeline is
   hot). Each lane ≈ 1-2 sessions through the standard workflow.
4. **Auto-regen script** — small, ships with Phase 0 or immediately after (it depends on the
   quarantine rail).

## §Solo-operatore / business decisions (Zero)

1. **Phone-test seal** (physical device): GARUDA generation seal + Phase-1 promotion seal — one
   WhatsApp session with the handed-over question list.
2. **Lane GOs for Phase 2** + the §6.5 sequencing call (company fact-bearing: wait for
   GARUDA-FILIERA canonical vs process-only now — recommendation: process-only now).
3. **Expert time**: Surya (visa/tax/company) and Ari (property) review slots — the real
   bottleneck for Phase 2.
4. Costs: OAuth/quota only (Sonnet MAX + Codex ChatGPT Pro + GLM); no paid per-token API. No new
   authorization needed.
