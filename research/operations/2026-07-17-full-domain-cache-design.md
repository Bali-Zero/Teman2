---
date: 2026-07-17
domain: compliance
client_case: none (product/data architecture — Zantara WA bot corpus program)
sources:
  - "/bot corner (.claude/skills/bot/SKILL.md, 2026-07-17) — LIVE STATE, Zero rulings §4.6, blood-bought rules §5"
  - "PR #2588 (F1b, merged 2026-07-17): apps/backend-rag/scripts/curated_qa_harvest.py, curated_qa_convert_e33.py, backend/services/caching/notebooklm_cache_service.py, apps/backend-rag/data/curated_qa/README.md"
  - "apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py (check_faq_cache L200-272, _inject_curated_qa_grounding L339-420)"
  - "apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py + reasoning_utils.py L550-680 (5 named abstain gates, domain classifier)"
  - "apps/backend-rag/backend/app/metrics.py (faq_cache_hits/misses/errors_total, curated_qa_injections_total)"
  - "apps/backend-rag/backend/core/collection_registry.py (curated_qa collection registration)"
  - "~/scripts/regulatory-watcher-run.sh + apps/backend-rag/backend/db/migrations_v2/206_wa_meta_inbox.sql"
  - "research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, L0-L6, G13-G17, verification doctrine)"
  - "research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (seat table, D0-D6 dossier protocol, AQL sampling, degradation rules)"
  - "apps/backend-rag/scripts/golden_answers_questions.yaml (28 rows, live-counted this session)"
  - "postgres-nuzantara MCP query on meta_inbox_messages (live-counted this session, 2026-07-17)"
adversarial_review: codex
---

# Full-domain curated-cache program design (visa pilot)

> Mandate: Zero GO 2026-07-17 (`/bot` corner §4.6) — "extend the E33-216 pattern to ALL domains
> (visa, company, tax, property) with automatic regeneration and obsolescence archiving,
> reuse-first." This is a **design doc, not a build** — no code in this phase. Read `/bot`
> corner first; this doc assumes its LIVE STATE and blood-bought rules as ground truth.

## 0. Scope — what this reuses, what is new (reuse-first)

The E33 build (PR #2588) already shipped the entire **sink layer**: `curated_qa_harvest.py`
(FAQ + Qdrant writers, provenance-mandatory, `--purge-domain`), `curated_qa_convert_e33.py`
(3 converter modes), `NotebookLMCacheService` (exact-match verbatim cache, MD5 key, 30-day TTL,
source_priority collision policy), and the `curated_qa` Qdrant collection (flat payload, frozen
`text-embedding-3-small`, grounding-injection consumer in `orchestrator_core.py`). **None of that
is rebuilt here.** This design is about the three things that do NOT exist yet:

1. A **generation pipeline** that produces new `curated_qa` JSONL rows per domain at
   E33-equivalent quality, for domains that have no hand-authored dossier like Ari's E33 markdown.
2. A **regeneration trigger** that reacts to regulatory-watcher deltas and re-verifies affected
   cache entries instead of letting them go silently stale (W90 — "ground truth ages too").
3. An **archiving/obsolescence policy** — today the only cache lifecycle primitives are a
   hardcoded 30-day Redis TTL (`notebooklm_cache_service.py:60`) and a manual
   `--purge-domain` CLI flag. Neither is "obsolescence-aware."

## 1. Generation pipeline per domain

### 1.1 Question mining — honesty check first (this changes the plan)

The instruction was to state sources honestly rather than assume a query-log pipeline exists.
Live-checked this session: **`meta_inbox_messages` holds 214 total rows (72 inbound) since
2026-06-03** — the WA bot is 6 weeks old and has had roughly one real inbound message per day.
This is **not enough volume, per domain, to mine questions statistically** the way a mature
product would (cluster real queries → frequency-rank → cover the head). Mining from real traffic
is a **Phase-2 enrichment**, not the Phase-1 source.

Realistic Phase-1 question sources, per domain, in priority order:

1. **Hand-authored dossiers** (E33 pattern) — a domain expert (Ari for E33, Surya for GARUDA/VOA,
   the tax/setup team for company/tax) writes a markdown Q&A dossier in the E33 format
   (`### Q<N>.` / `**FINAL (client-facing):**` / `**CONFIDENCE:**` / `**LAW REFS:**`).
   `curated_qa_convert_e33.py --domain <d>` already parses this verbatim — zero new code.
   This is the ONLY source with a proven quality bar (216 rows, panel-corrected spec v2).
2. **`golden_answers_questions.yaml`** (28 rows, live-counted: visa 12 / tax 6 / company 6 /
   property 4) — question-only seeds, no vetted answer yet. Useful as a coverage checklist per
   domain, not as generation input on its own.
3. **KBLI Navigator corpus** (for the `company` domain specifically) — the
   `/kbli-navigator` corner is running a much heavier, purpose-built verification program
   (GARUDA-FILIERA, P1-P9/L0-L6/G13-G17) over the same underlying facts (KBLI code licensing,
   PMA eligibility, capital rules). **This cache program must NOT re-derive KBLI facts** — it
   should only cache **process/FAQ-shaped** company questions ("how long does PT PMA setup
   take", "what documents do I need") and, once GARUDA-FILIERA Phase 2 ships a reproducible
   canonical, treat that canonical as the `company` domain's fact source — never a parallel one.
4. **WA/webchat query logs** (deferred — Phase 2, PII-scrubbed, only once volume is meaningful;
   see §7).

Real, hand-authored dossiers do not yet exist for company/tax/property the way E33 exists for
visa (Second Home). **Producing them is Bali Zero domain-expert work** (Surya for
tax/setup, Ari-adjacent for property), not something this pipeline can synthesize from nothing —
an LLM inventing "vetted, client-facing" Q&A without a domain expert's sign-off would violate the
same principle the E33 process already enforces (INTERNAL reasoning is separated from FINAL
client-facing text specifically because a domain expert reviewed and demarcated the line).

### 1.2 Answer grounding

Every answer must resolve to one of:
- **Verbatim from a reviewed dossier** (E33-style — a human wrote/approved the FINAL text).
- **Grounded generation against NB + curated KB**, produced by an implementer seat (Sonnet 5)
  and then blind-verified (§1.4) before it is trusted enough to enter the **exact-match FAQ
  cache** (which bypasses the abstain gate on every hit — the highest-risk surface in this whole
  program, per corner blood-bought rule #1).
- Every row carries `source_ref` + `source_date` regardless of path — the provenance contract in
  `NotebookLMCacheService.set()` already enforces this at the code level; this pipeline must never
  try to route around it.

**Pricing carve-out (hard rule, not new — restates an existing invariant):** no generated Q&A row
whose answer states a price may enter the FAQ verbatim cache. Prices come from `PricingTool` only
and change independently of any dossier's `source_date`. A cached verbatim price is a stale price
waiting to happen. Price-adjacent questions ("how much does X cost") are explicitly OUT of scope
for this corpus — the orchestrator's existing `get_pricing` tool call path handles them, and that
path already runs the abstain gate. If a domain dossier accidentally includes a price in a FINAL
answer, the row must be rejected in D3 assembly (§1.4), not silently harvested.

### 1.3 Confidence classes (reuse E33 taxonomy verbatim)

`JELAS` (clear/settled), `BERSYARAT` (conditional), `BELUM_DIATUR_PUBLIK` (not yet publicly
regulated), `KEBIJAKAN_PENYEDIA` (provider policy, not law), `DINAMIS` (actively changing) —
these five plus `UNSCORED` for question-only seeds are already the live schema
(`curated_qa_convert_e33.py` docstring, any OTHER token kept verbatim and counted, never
silently dropped). No new taxonomy needed. One addition worth making explicit for the
regeneration trigger (§2): `DINAMIS`-classed rows are the ones regulatory-watcher deltas are
most likely to invalidate — they should carry a shorter effective freshness window than the
blanket 30-day Redis TTL (see §3).

### 1.4 Blind verification: generator ≠ grader (adapted from the KBLI filiera method)

The filiera D0-D6 protocol (dossier hash-chains, image-verified extraction, family-independence
pairing) is built for a much higher-stakes artifact (licensing facts with legal force) than a
client-facing FAQ answer. Importing it wholesale would be over-engineering. What DOES transfer,
because the underlying risk (verbatim serving that bypasses the abstain gate) is the same class
of danger as "certifying a fact":

- **Generator ≠ grader, cross-family, every batch.** The domain dossier (or Sonnet-drafted
  candidate answer set) is generated by one seat; a **different model family** blind-verifies
  by re-answering the same question from the underlying KB/NB *without seeing the candidate
  answer*, then a deterministic diff (not an LLM) flags disagreement. Per the corner's model
  routing: implementer = Sonnet 5; verifier = Codex GPT-5.6 or DeepSeek (never the same family
  as the generator for that batch — mirrors the filiera "family-independence pairing rule").
- **Gold-set + AQL, not naive 10% sampling** (filiera §5, red-team-corrected): a small
  hidden gold-set of pre-verified Q&A pairs is mixed into every generation batch; a miss on a
  gold item halts the batch (calibration signal). New domains start at **100% human/Fable
  review** (mirrors filiera Batch-A treatment — small enough to be affordable, and it doubles as
  the gold-set nursery for that domain); only after N consecutive defect-free batches does
  review loosen to AQL-style sampling. Any defect re-tightens (a defect is assumed systematic —
  page/template/field-stratified — until proven isolated, same reasoning as filiera §5).
- **Batch sizes**: small and frequent beats large and rare, mirroring the filiera pilot
  discipline ("measure before promising cadence" — red-team F11 there). Recommended batch = one
  dossier section or ~20-30 questions, never a whole-domain dump in one shot.
- **Final gate**: Fable signs off before a batch is loaded into prod Redis/Qdrant — this is a
  `curated_qa_harvest.py` invocation against prod, which the harvester's own docstring already
  says NOT to run without review ("Do NOT run against prod without Zero's review of the batch").
  That line currently reads "Zero's review" — this design proposes it becomes "Fable's review
  after the blind-verification pass," consistent with the ship-lifecycle rule (the codeowner does
  not review code or corpora; the session does, with an adversarial gate raised for
  client-facing/sensitive content, never lowered to a human).

## 2. Regeneration triggers

### 2.1 Regulatory-watcher delta → affected entries

The regulatory-watcher wrapper (`~/scripts/regulatory-watcher-run.sh`, cron 07:00 WITA daily)
already emits `research/regulatory/<date>-delta.json` with schema
`{run_at, today, new_today_count, partial, deltas:[{citation, title_id, title_en, service_line,
summary, source, verbatim_excerpt}], seen_citations}`. `service_line` is a free-text field
(observed values include visa/immigration, tax, property, regulatory/HR, health) that needs a
**small, deterministic mapping table** to the four cache domains
(`visa`/`kbli`(company)/`tax`/`property`) — not an LLM classification step, since misrouting a
delta means a stale answer stays cached.

Proposed trigger (new, small script — the only meaningfully new code this design calls for
outside the generation batch scripts):

1. Daily, after regulatory-watcher writes its delta, a follow-up step reads
   `deltas[].service_line` + `citation`, maps to a cache domain, and searches `law_refs` across
   that domain's `curated_qa` rows for a citation-string match (simple substring — the same class
   of gate the guard-conformance family (`cicatrix-superscar.md` #3) says never to trust alone;
   this is a *candidate* list, not an auto-invalidation).
2. Matching rows are NOT auto-deleted or auto-regenerated (a delta is a signal, not a proof — the
   filiera doc's "silence → corroborated abstention" principle has a mirror image here: "a new
   citation → corroborated staleness", not blind trust). They are written to a small
   `data/curated_qa/_regen-candidates/<date>.jsonl` list for the next generation batch to review
   with priority.
3. If `new_today_count == 0` (the common case — 2026-07-12 through 2026-07-16 all show
   `new_today_count: 0` in the live delta files checked this session), there is nothing to do —
   this must be a true no-op, not a wasted LLM call.

### 2.2 W90 re-grounding invalidation (ground-truth aging, not just regulation aging)

The `/kbli-navigator` corner's W90 lesson (`discovery_ground_truth_verifier_stale_2026_07_02`,
cited in the cicatrix superscar #6 family) applies here directly: **NotebookLM's own snapshot can
be stale relative to a resolution that already landed elsewhere in the codebase.** Every
re-grounding pass (a generation batch, a manual purge+reload) should emit a small invalidation
note if it discovers the underlying NB content itself was stale — not just regenerate the answer
silently. This is a process discipline, not new code: "when a regeneration finds the ground
truth was wrong, say so in the batch report" (mirrors filiera §3 D6 "every negative finding
becomes a permanent sentinel").

### 2.3 Manual purge path (already exists)

`curated_qa_harvest.py --purge-domain <domain> --faq --qdrant` already deletes every entry for a
domain from both sinks (scans Redis keys under the cache prefix, filters by decoded metadata for
FAQ; scroll+filter for Qdrant). This is the correct escape hatch for "domain corpus is being
rebuilt from scratch" — no new tooling needed, just documenting it as the operator-facing
emergency path in the `/bot` corner (§6 Artifacts & access already lists the corpora paths; add
the purge command there once this design ships).

## 3. Archiving / obsolescence policy

### 3.1 What exists today (and its limits)

- **Redis FAQ cache**: hardcoded `ttl_seconds = 30 * 24 * 60 * 60` (30 days) on every `set()` —
  a blanket expiry regardless of `confidence_class` or `source_date`. A `JELAS` (settled) answer
  and a `DINAMIS` (actively changing) answer expire on the same clock today.
- **Qdrant `curated_qa`**: no TTL mechanism at all — points persist until explicitly deleted via
  `purge_domain_qdrant()`. An obsolete grounding-injection answer can live indefinitely unless
  someone purges it.
- **Collision policy** (`_existing_entry_outranks`): an incoming write is refused only if the
  *existing* entry has a **strictly higher** `source_priority`; equal-or-lower priority allows
  overwrite. This means a same-priority regeneration naturally supersedes the old entry on
  reload — useful, but it is a write-time mechanism, not a scheduled one.

### 3.2 Proposed policy (design-level, not implemented here)

- **Priority tiers by confidence_class**, not a flat CLI default: `JELAS`/verified-dossier rows
  get a high fixed priority (mirrors E33's `--source-priority 80`); `DINAMIS` rows get a
  **lower** priority than settled classes so a future higher-confidence regeneration can always
  displace them, and a **shorter TTL override** at write time (the harvester would need a
  `--ttl-override` passthrough to `cache.set()` — small, additive change, not built here).
- **source_date-based obsolescence, not calendar-only TTL**: a row whose `source_date` predates
  a *confirmed* regulatory change (§2.1's regen-candidate list, once a human/Fable confirms the
  delta actually invalidates it) should be purged immediately, independent of whether its 30-day
  TTL has elapsed. TTL is a safety net for "nobody checked in a month"; it is not the primary
  obsolescence signal — provenance is (blood-bought rule #1: "provenance beats
  freshness-illusion").
- **Priority collisions across domains never happen by construction** — `source_priority` is
  compared only within the same MD5 cache key (same normalized question text), and domain is
  part of the row, not the key. A genuine cross-domain collision would mean two different
  domains produced byte-identical normalized questions, which is a generation-pipeline bug
  (duplicate question text) to catch in D3 assembly (§1.4), not an archiving concern.
- **Hard archiving (not delete) for audit**: before any `--purge-domain` run against prod, the
  purged rows should be captured (the harvester's `purge_domain_faq`/`purge_domain_qdrant` return
  counts, not content — a small change to log the purged question set to
  `data/curated_qa/_archived/<domain>-<date>.jsonl` before deletion would preserve the audit
  trail the E33 corpus itself relies on being reviewable). This is additive, not built here.

## 4. Pilot: domain = visa

**Why visa first**: highest WA volume among the four target domains historically (E33/Second
Home is itself a visa product), the E33 216-row corpus is the only domain with a proven,
panel-corrected generation precedent, and the abstain-policy's per-domain threshold for visa
(0.12) is already tuned and live — no new threshold work needed.

- **Prerequisite (blocking, §8)**: the FAQ cache key must be domain-scoped before this pilot
  loads a single row — even a single-domain pilot inherits the risk the moment a second domain's
  content exists anywhere near it, and the fix is small enough to fold into the pilot PR rather
  than defer it.
- **Scope**: prove the FULL loop (dossier → convert → blind-verify → harvest → prove-live →
  regen-trigger dry-run) on the visa domain using content the pipeline does NOT already have —
  i.e., NOT a re-run of the already-shipped 216 E33 rows, but the **next visa dossier** (GARUDA
  B1/VOA corner has visa-adjacent Q&A material forming; check with Surya before assuming a
  second dossier must be authored from scratch — reuse-first applies to content too, not just
  code).
- **Corpus size target**: 20-40 rows for the pilot batch — large enough to exercise the AQL/gold-
  set machinery meaningfully, small enough that 100%-review is affordable (§1.4).
- **Acceptance gates** (revised per §8/§9 panel — supersedes the original 3-item list): zero
  gold-set misses; zero pricing-carve-out violations, enforced by a harvester-level detector, not
  just reviewer instruction (§1.2, panel #13); every row carries an explicit `verbatim_eligible`
  value and only `JELAS` rows are `true` (panel #3); every row passes the existing
  `curated_qa_harvest.py` schema validation unchanged; prove-live check on the real
  `/api/agentic-rag/query` path for at least 3 of the new questions; PLUS the panel's #15 test
  matrix — an identical cross-domain collision case (two domains, same normalized question text,
  confirm the domain-scoped key keeps them separate), a conditional (`BERSYARAT`) row confirmed
  to land ONLY in Qdrant grounding and never the FAQ sink, a simulated regulatory-delta
  quarantine (confirm the candidate is de-listed from verbatim serving same-day, not next-batch),
  and a price-bearing row confirmed rejected by the harvester.
- **Rollback**: still domain-wide today (`--purge-domain visa --faq --qdrant`) — panel #9
  confirms batch-scoped purge is NOT actually achievable via `source_ref` prefix alone (that's
  metadata, not a delete predicate) without a small harvester change to filter-by-prefix on
  purge. For the pilot's small scope, domain-wide rollback is an acceptable (if blunt) fallback;
  it stops being acceptable once a second batch lands in the same domain — a real gap to close
  before fan-out (§5), not before the pilot.

## 5. Fan-out plan (after pilot GO)

Once the pilot proves the loop end-to-end, four domain lanes can run in parallel, each in its own
worktree/session, because they touch disjoint `data/curated_qa/<domain>-*.jsonl` files and
disjoint Redis/Qdrant domain partitions (no shared-state collision by construction — the same
property that let E33 and the F1a outbox work ship independently):

| Lane | Domain | Owner (content) | Generation seat | Verifier seat | Depends on |
|---|---|---|---|---|---|
| 1 | visa | Ari / Surya (GARUDA-VOA overlap) | Sonnet 5 | Codex or DeepSeek | Pilot result |
| 2 | company (`kbli`) | Surya + `/kbli-navigator` corner | Sonnet 5 | cross-family, ≠ lane-1 verifier if run concurrently | GARUDA-FILIERA Phase-2 canonical (process-only Q&A can start earlier, but fact-bearing company Q&A should wait) |
| 3 | tax | Surya / tax-dept | Sonnet 5 | cross-family | Pilot result |
| 4 | property | Ari (Second Home overlap) | Sonnet 5 | cross-family | Pilot result |

Each lane is GO-gated separately (§6) — this is a fan-out **plan**, not an authorization to start
all four; Zero's 2026-07-17 ruling authorized the *program*, and this doc proposes the pilot as
the next concrete step, with lanes 2-4 opening only after pilot acceptance gates pass.

## 6. §Solo-operatore / §Business decisions (Zero's GO required)

1. **Corpus batch approval before prod load** — this is not new; it is the harvester's existing
   contract ("Do NOT run against prod without review of the batch being loaded"). Under the
   ship-lifecycle rule this review is Fable's, not Zero's, EXCEPT where the content itself
   requires a business call (below).
2. **Domain-expert sign-off on dossier content** is a business decision the session cannot make:
   Surya/Ari/tax-dept must actually write or review the FINAL client-facing text for company/tax/
   property dossiers — an LLM cannot manufacture "vetted" content out of nothing without a human
   who owns that domain's client relationship attesting to it. This is the actual bottleneck for
   lanes 2-4, more than engineering time.
3. **Costs**: this program is LLM-quota-only (Sonnet 5 MAX-plan implementer + Codex/DeepSeek
   verifier per CLAUDE.md routing), zero paid per-token API calls proposed — no new authorization
   needed under the cost-constraint rule. Flagging it anyway per the panel-mandatory review habit.
4. **NB usage**: grounding pulls from existing NB (NB-2 visa / NB-3 company-KBLI-PMA / NB-4 tax /
   NB-5 property per the wr3-brief-interpreter agent's domain mapping) — read-only, no new NB
   creation proposed.
5. **Is the KBLI Navigator's GARUDA-FILIERA canonical a prerequisite for the `company` lane, or
   can process-only company Q&A ship independently?** Recommendation: ship process-only company
   FAQ now (lane 2, "how long does PT PMA take"), defer fact-bearing company Q&A (KBLI-specific
   licensing claims) until GARUDA-FILIERA Phase 2 lands a reproducible canonical — but this
   sequencing call is Zero's, since it trades speed against the exact cross-vintage risk the
   filiera program exists to fix.

## 7. §Meta-pattern + open risks (honest unknowns)

**Meta-pattern**: this program is the filiera methodology's core insight — *"facts joined across
sources by weak keys, inside pipelines that cannot be re-run, with silent substitution on
silence"* — restated for a lower-stakes but higher-blast-radius artifact (a verbatim answer to a
paying client on WhatsApp, served with the abstain gate bypassed). The cure is the same shape:
per-row provenance (already enforced), generator≠grader verification (proposed here, not yet
built), and explicit obsolescence instead of calendar-only expiry (proposed here, not yet built).
The KBLI filiera doc's "malattia-delle-malattie" framing transfers cleanly; the difference in
stakes justifies a *lighter* protocol (no hash-chained dossiers, no D0-D6 image-verification —
there is no OCR-hostile PDF in an FAQ answer), not a different philosophy.

**Open risks, stated plainly:**

1. **Query-log mining is not viable yet** (§1.1) — 214 total WA messages since June 3 is too thin
   to mine per-domain question frequency. This is a volume problem that self-resolves as the bot
   runs longer; revisit in 2-3 months, not before.
2. **PII in any future query-log mining**: `meta_inbox_messages.body` is raw customer text —
   phone numbers, names, sometimes document numbers appear inline. Any future question-mining
   pass over real messages MUST scrub PII before the text reaches any LLM (local Ollama
   pre-filter, never cloud, mirroring the `document-intake-classifier` agent's UU PDP posture) —
   this is a hard constraint for Phase 2, not yet a live risk since Phase 1 doesn't mine logs.
3. **Meta 24h window is irrelevant to this cache** — correctly so; the FAQ cache serves inbound
   questions regardless of window state, and the corner's "WA reactive-only" ruling (§4.2) is
   about outbound business-initiated messages, a different concern entirely. Noting this only to
   confirm it was checked and is a non-issue, not silently assumed.
4. **Cache-bypasses-abstain is the single largest safety surface in this whole program.** Every
   generation-pipeline gate proposed above (pricing carve-out, blind verification, gold-set,
   100%-review-until-proven) exists because a bad FAQ cache write is a bad answer served
   instantly and repeatedly, with no per-request abstain check to catch it. This is the design's
   central risk and the reason the pilot is scoped small (§4) rather than jumping straight to
   fan-out.
5. **`classify_query_domain()` has no `property` branch** (verified this session, reading
   `reasoning_utils.py`) — property-domain queries that MISS the exact-match FAQ cache fall
   through to the `default` abstain threshold (0.15), not a property-tuned one. This doesn't
   block the property lane (curated_qa grounding-injection is domain-agnostic at the 0.90 score
   threshold regardless), but it means property cache MISSES get generic-quality gating on the
   RAG fallback path. Worth a follow-up ticket, out of scope here.
6. **Batch-scoped rollback gap** (§4) — purge is domain-wide, not batch-wide, today. Acceptable
   for a single pilot batch (rollback = domain purge = re-load), a real gap once multiple batches
   land in the same domain over time.
7. **`data/curated_qa/` has zero committed JSONL today** (live-checked this session — the README
   table says "none committed by this build"). The 216 E33 rows live only in
   `~/Desktop/E33-SecondHome/E33-DEFINITIVE-CHATKB-2026-07-15.md` on disk, not in the repo. This
   means the *reproducibility* property the filiera doc insists on (G16: rebuild from vault,
   byte-identical) does NOT yet hold for curated_qa — prod state is not derivable from git alone.
   Recommendation for the pilot: commit the JSONL outputs (post-conversion, post-verification) to
   `apps/backend-rag/data/curated_qa/` in the PR that loads them, closing this gap going forward.

## 8. §Amendments — pilot GO is blocked until the 5 FATALs below are closed

The panel (§9) found a real, already-shipped defect, not just a design gap: **the FAQ cache key
has no domain scoping.** `curated_qa_harvest.py::harvest_to_faq()` calls
`cache.set(row["question"], row["answer"], metadata=metadata)` with no `notebook_id` — and
`NotebookLMCacheService._hash_question()` only namespaces the key by `notebook_id` when one is
passed. With only the 216 visa E33 rows live, this defect was invisible (low collision surface
within one domain's phrasing). It becomes load-bearing the moment `company`/`tax`/`property`
questions ship, because generic phrasings ("how long does this take", "what documents do I
need", "can I do this remotely") are near-certain to collide verbatim across domains — and the
cache would serve one domain's answer to another domain's question with **no abstain check at
all**. This single finding changes §0's "no code, reuse-first" framing: **domain-scoping the FAQ
cache key is a prerequisite code fix, not a documentation nuance** — it must land (small change:
pass `domain` as `notebook_id` or fold it into the hash input) before any second domain's rows
are loaded to prod, and ideally before the visa pilot too, since the pilot's own rollback/purge
story (§4) assumes clean domain boundaries that don't currently exist at the key level.

The other four FATALs (§9 #2-#5) revise this design's posture from "additive TTL/priority tuning"
to "the verbatim-eligible surface needs an explicit allowlist, not an opt-out list":

- **§1.3/§3.2 revised**: add a `verbatim_eligible: bool` field to the schema (not proposed in the
  original draft). Default `false`. Only `JELAS`-classed, non-price, non-client-specific rows are
  `verbatim_eligible=true` and may enter the exact-match FAQ (Redis) sink. `BERSYARAT`,
  `BELUM_DIATUR_PUBLIK`, `KEBIJAKAN_PENYEDIA`, `DINAMIS` rows go to `curated_qa` (Qdrant grounding
  injection) ONLY — they still pass through the abstain gate downstream, which is exactly the
  point: a conditional answer ("depends on your nationality/entity type") is legitimate context
  for the ReAct loop to reason over, but dangerous served verbatim with zero reasoning applied.
- **§2.1 revised**: a row that lands in `_regen-candidates/` must be **quarantined immediately**,
  not left serving until the next batch reviews it — i.e., a candidate match should set
  `verbatim_eligible=false` (or delete the FAQ-sink copy outright, keeping the Qdrant copy
  clearly marked as "regulatory-delta-flagged, not authoritative") the same day the delta lands,
  fail-safe by default. The proposed script in §2.1 needs this as a hard requirement, not an
  optional enhancement.
- **§1.2/§6 revised**: the PII boundary must be enforced at generation time, not just for the
  deferred query-log mining path. Dossier/NB sources feeding the generator/verifier must be
  drawn from a declared PII-free allowlist (NB collections + reviewed markdown dossiers only —
  never raw `meta_inbox_messages` content, which §7.2 already correctly excludes from Phase 1,
  but this needs to be a structural allowlist check in the batch script, not an assumption).
- **§1.2/§4 revised**: the pricing carve-out needs a deterministic detector (regex/keyword scan
  for currency markers, "starting from", ranges, "deposit"/"tax included" phrasing — mirroring
  the existing `trusted_tools_used` pricing-marker detection already live in `reasoning.py`) run
  by the harvester itself, refusing to write any matching row to the FAQ sink — not a D3
  reviewer instruction that depends on a human/Fable catching it by reading.

The MAJOR findings (§9 #6-#15) are real operational gaps (batch atomicity, rollback granularity,
watcher `partial`/unmapped-domain handling, Qdrant grounding freshness, ownership/monitoring,
semantic-equivalence limits of "blind diff" verification, property-domain threshold gap already
flagged in §7.5) that should be resolved before fan-out (§5) even if the pilot (§4, narrowed to
a handful of rows with 100% review and the FATAL fixes applied) can proceed once the FATALs
close — the pilot's small scope is precisely what makes it safe to run before every MAJOR is
resolved; fan-out is not.

## Adversarial review — §Panel Codex GPT-5.6-terra red-team (2026-07-17, effort high, read-only sandbox)

Full findings, verbatim (translated from the panel's Italian output, tags/section-citations
preserved). Verdict stated by the panel: *would not authorize the verbatim-cache pilot until
findings #1-#5 are closed — today they can produce a cross-domain, unapproved, or already-
suspected-stale answer with no abstain gate downstream.*

1. **[FATAL] FAQ Redis is not actually domain-partitioned.** §3.2 claims cross-domain collisions
   "never happen by construction", but the key is only the normalized/MD5 question — `domain` is
   metadata, not part of the key. "What documents do I need?" could serve the tax answer to a
   visa question (or vice versa); priority decides the winner. Same issue in the Qdrant upsert,
   whose point ID is derived only from the question text. Fix: key/ID must include `domain`, plus
   a runtime domain-match check before serving a hit. (§3.2, §5)
2. **[FATAL] "Provenance mandatory" ≠ "approved for abstain bypass".** The design requires
   `source_ref`/`source_date`/etc., but defines no signed/immutable artifact tying each JSONL row
   to its dossier hash, grader report, gold-set pass, and Fable approval. The loader accepts any
   row with the required schema shape. A badly generated JSONL, a broken conversion, or a manual
   load can reach the verbatim sink with plausible-looking metadata. Needs a per-batch approved
   manifest, file hashes, and fail-closed verification in the harvester. (§1.2, §1.4, §4)
3. **[FATAL] Conditional/dynamic classes are admitted to the verbatim surface.** §1.3 includes
   `BERSYARAT`, `BELUM_DIATUR_PUBLIK`, `KEBIJAKAN_PENYEDIA`, `DINAMIS`; §3.2 only proposes
   different priority/TTL for them. No rule restricts the abstain-bypassing cache to universal,
   context-free, `JELAS` answers. A "depends on…" answer can be correct in the dossier and wrong
   for a specific client — the exact hit returns before any ReAct/abstain reasoning runs. Make
   `verbatim_eligible` an explicit field, defaulting to `JELAS`-only, non-price, non-client-
   specific; other classes go to Qdrant grounding only. (§1.3, §3.2)
4. **[FATAL] A suspect delta keeps being served.** §2.1 puts matches into `_regen-candidates` "for
   the next generation batch" — it doesn't mark the row quarantined or block the Redis lookup.
   For potentially-invalidated content, the system keeps answering verbatim until human/Fable
   review and purge — potentially for the whole TTL. A candidate must immediately disable the
   exact hit (fail-safe) or impose an emergency TTL, while Qdrant can remain only as clearly
   marked stale/non-authoritative evidence. (§2.1, §3.2)
5. **[FATAL] The PII boundary is not enforced in Phase-1 generation, nor specified for Phase 2.**
   "NB + curated KB" gets sent to cloud generator/grader with no source allowlist, PII
   classification, or verifiable redaction; a contaminated notebook or dossier could exfiltrate
   client data. For query logs, §7.2 prescribes an Ollama pre-filter but specifies no
   deterministic masks, leakage tests, fail-closed behavior, or a guarantee that residual text
   never reaches JSONL/Redis/Qdrant/archives/cloud prompts. Use only declared PII-free sources;
   redact locally with a deterministic detector plus review; block the batch if even one
   identifier remains. (§1.2, §6.4, §7.2)
6. **[MAJOR] The trigger ignores the watcher's own unreliability signals.** The schema includes
   `partial`, but §2.1 only decides no-op on `new_today_count == 0`. A partial run, a fetch
   error, or an unmapped `service_line` can look like "no delta" and leave stale content alive.
   Needs job-status awareness, a complete mapping-table allowlist, alerts on unmapped/
   partial/failure, and fail-safe mode for affected domains. (§2.1)
7. **[MAJOR] No scheduled revalidation based on true source age.** TTL starts at load time, not
   `source_date` — an already-old source can get another 30 days; the proposed `DINAMIS`-specific
   TTL isn't actually specified as implemented. §2.2 only asks for a note when re-grounding
   discovers staleness, not a periodic job that discovers it. Define `valid_until`/max-age per
   class, a daily scan, and automatic blocking of expired entries. (§2.2, §3.1-§3.2)
8. **[MAJOR] Qdrant can inject stale grounding indefinitely with no validity filter.** The doc
   acknowledges this but the proposed policy depends on manual purge/confirmation. No `active`,
   `invalidated_at`, version, expiry, or retrieval-time filter is defined; an old high-similarity
   point keeps influencing the model even after a regulatory change. (§3.1-§3.2)
9. **[MAJOR] Rollback is not batch-scoped**, despite the text implying a `source_ref` prefix is
   enough. §4 itself admits the purger operates per-domain; a prefix is only metadata and does
   not by itself enable selective deletion. A visa-batch rollback could delete every other visa
   batch, or force leaving the defective one live. Needs purge/disable by `batch_id` + manifest,
   plus verifiable re-activation. (§4, §7.6)
10. **[MAJOR] The two-sink load is neither atomic nor batch-idempotent.** FAQ and Qdrant are
    independent sinks: a mid-batch error/interruption can leave a verbatim subset in Redis with
    Qdrant not updated, or two diverging versions. No staging, commit marker, persisted report, or
    automatic compensation. For a surface that bypasses the abstain gate, publish must be
    all-or-nothing. (§0, §1.4, §4)
11. **[MAJOR] No operational owner, SLA, or monitoring for the full staleness cycle.** §5 assigns
    content owners, not owners for the cron, candidate triage, purge, rollback, or incident
    response. No alerts/metrics defined for candidate-backlog age, watcher `partial`, mapping
    misses, entry age per class, cross-domain collisions, partial loads, hits on quarantined
    entries, or stale Qdrant points. Hit/miss counters alone are not enough. (§2.1-§2.3, §5-§6)
12. **[MAJOR] "Blind + deterministic diff" verification is not semantic proof.** Two correct
    answers can differ textually; two answers with identical wording can share the same false
    premise. Missing: claim-level checks, expected citations, AQL thresholds, a defined `N`, a
    defect definition, report retention, and regression against already-prod answers. Once
    review loosens from 100% to AQL sampling, this becomes a real non-vetted entry path. (§1.4)
13. **[MAJOR] The pricing carve-out is a policy, not a control.** §1.2 says to reject prices in
    D3, but defines no detector, no price-adjacent question taxonomy, no negative tests, and no
    harvester-level enforcement. Prices can appear as ranges, "starting from", deposits, taxes,
    or spelled-out amounts and still reach Redis. The loader must deterministically reject
    price-bearing records and block FAQ publish. (§1.2, §4)
14. **[MAJOR] The property target ships with an incomplete safety posture.** The doc notes that
    property cache misses fall to the default threshold but leaves that out of scope while still
    proposing the property fan-out lane. Don't open that lane until classification, a calibrated
    threshold, and abstain tests exist for property; otherwise a miss falls through to an
    unvalidated protection for that domain. (§5, §7.5)
15. **[MINOR] The pilot proves too little of the wrong thing.** Three live positive queries verify
    the path works, not that it is safe. Acceptance gates should include: an identical
    cross-domain collision, a conditional FAQ with client-specific context, a regulatory-delta
    quarantine candidate, a watcher `partial` run, an interrupted batch, a selective rollback, a
    price-bearing row, and a corpus/query-log sample containing PII. (§4)
