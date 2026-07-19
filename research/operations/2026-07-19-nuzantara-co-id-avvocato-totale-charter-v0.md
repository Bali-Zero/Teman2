---
date: 2026-07-19
domain: operations
project: NUZANTARA (nuzantara.co.id)
status: RATIFIED by Zero 2026-07-20 (Legge 5) — pilot=ketenagakerjaan · infra=offline-first (no Fly for now) · principle=one brain, two bodies
adversarial_review: codex
client_case: none
sources:
  - 2026-07-19 full KB audit (4-reader sweep: Qdrant, Postgres prod, disk corpus, Drive+NotebookLM — session 932b2e53)
  - apps/backend-rag/backend/db/migrations_v2/250_visa_engine_core.sql (bitemporal substrate reference design)
  - .claude/rules/cicatrix-superscar.md (10 scar families → design principles)
  - .claude/skills/kbli-navigator (filiera D0-D6 cross-family validation method)
---

# NUZANTARA — The Total Lawyer (Avvocato Totale) · Charter v0

> **One line:** Zantara for Indonesians — an autonomous, self-healing, self-developing
> legal-knowledge organism at **nuzantara.co.id**, born from everything Bali Zero's
> organism learned, and deliberately **not** a load on Bali Zero's back.

## 0. Ratification (Zero, 2026-07-20)

Zero ratified this charter with three binding decisions:

1. **Charter confirmed** ("1 confermo").
2. **Phase-0 pilot domain = ketenagakerjaan** ("2 ketenagakerjaan") — labor law:
   UU 13/2003 + Cipta Kerja stack (UU 6/2023) + PP 35/2021 + PP 36/2021 + Permenaker.
3. **Infra = offline-first, no Fly for now** ("3 teniamo offline al momento, senza
   fly... poi vediamo") — Phase 0/1 run entirely on local machines: local norm-store,
   local embeddings (bge-m3), no new cloud app until Zero re-opens the question.

**Founding principle, dictated verbatim by Zero:** *"il cervello dovrà sempre essere
uno... ma ci saranno due corpi"* — **one brain, two bodies**. One brain: Zantara —
the method, the engine, the scars, one monorepo. Two bodies: Bali Zero (expats,
balizero.com) and NUZANTARA (Indonesians, nuzantara.co.id) — separate brands,
separate delivery surfaces, separate data planes.

**What crosses between bodies (the brain's abstract layer ONLY):** method, code,
schemas, scars, validation patterns, infrastructure — artifacts that are PII-free
by construction (Law 2). **What NEVER crosses:** client/citizen data, query
content, conversation logs, gold sets or eval material derived from one body's
real queries, embeddings of client content. Learning derived from one body's
usage enters the shared brain only as **aggregate, redacted, provenance-tagged
artifacts** (topic buckets, missing-norm identifiers, counts) — never as raw or
reversibly-pseudonymized records. "The brain learns from both bodies" means the
method improves; it never means one body's data becomes visible to the other.

**Offline-first, scoped precisely:** runtime, serving, and ALL data live on local
nodes; no new cloud infrastructure and no new cloud spend. Dev-time validation
(the D0-D6 filiera) keeps using the already-paid flat CLI seats (Codex/Gemini/
Kimi OAuth) exactly as the rest of the monorepo does today — that is quota use,
not new infra. If flat seats ever disappear, the filiera degrades to local model
families (Ollama) with stricter thresholds — the validation GATE is structural;
which seats fill it is fungible.

**Phase 0 is LIVE:** `apps/nuzantara-lex/` shipped 2026-07-19 (PR #2846) — seed
manifest of 15 ketenagakerjaan norms (5 verified on BPK with sha256), fetcher with
content-identity verification (confusable-tolerant, scoped to the NOMOR…TAHUN
anchor), one-brain-two-bodies rules encoded in its README.

## 1. Mission & positioning

- **Who it serves:** Indonesian citizens and small businesses (UMKM) — in **Bahasa
  Indonesia** first. Not expats. Bali Zero keeps serving foreigners; NUZANTARA serves
  the 270M people whose own legal system is opaque to them.
- **What it is:** the "maestro della legge" — full-corpus Indonesian legal knowledge
  (norms, hierarchy, temporal validity, jurisprudence) with verified citations,
  delivered as accessible guidance.
- **What it is NOT (structural, non-negotiable):** it is **legal information and
  education, not legal services**. UU 18/2003 (Advokat) reserves paid legal services
  to licensed advocates. NUZANTARA answers "what does the law say, verbatim, in
  force today, and what does it mean" — and **refers to human advocates** for
  representation, disputes, and formal opinions. The abstain architecture (see §3.4)
  is therefore not just anti-hallucination engineering: it is the deontological
  boundary implemented in code.
- **Relationship to Bali Zero:** sibling, not parasite. Separate brand, separate
  delivery surface, separate data plane (see §5). Shared: the lessons, the patterns,
  selected components as libraries.

## 2. Why now (the audit's verdict, 2026-07-19)

The full KB audit measured Bali Zero's organism at "elite specialized para-legal,
~5-10% of the corpus a total lawyer needs, zero jurisprudence" — with an
architecture **designed above state-of-the-art** for the job: hybrid retrieval with
Pasal-aware chunking, 5-gate abstain policy, LangGraph multi-hop KG (116k nodes),
a signed bitemporal rule substrate (migration 250), and a proven cross-family
validation method (KBLI filiera).

**Honesty clause (adversarial review K3 — the audit's own meta-pattern applied to
this sentence):** "designed" is not "armed". As of ratification: hybrid search and
reranker are OFF in prod, migration 250 is merged but not yet applied (applies with
the next deploy, in flight), and the visa engine carries zero production rule
content. What is PROVEN is the **method** (the filiera ran end-to-end on KBLI; the
abstain gates run live; the 250 substrate is test-verified) — the full stack
running armed is precisely what the activation plan exists to close. NUZANTARA
inherits a proven method and a partially-armed skeleton, not a finished machine.

**The bottleneck is corpus loading + continuous validation**, plus finishing that
arming. That is exactly the kind of problem an autonomous organism is built to
grind through. NUZANTARA is the project that takes the skeleton and gives it the
full body of Indonesian law.

## 3. The inheritance — 7 design principles (scar-derived, non-negotiable)

Every principle below is a lesson Bali Zero's organism paid for in blood. In
NUZANTARA they are **birth constraints**, not retrofits.

1. **No scaffolding without cargo** (anti "Esiste≠Armato", scar family #2 — the
   audit's meta-pattern). A component is not "done" when built; it is done when
   loaded with data, armed in prod, and owning a maintenance loop. Every roadmap
   item ships as *substrate + initial corpus + refresh loop + liveness receptor*,
   or it does not ship.
2. **Bitemporality is universal.** Migration 250's design (legal_period ×
   system_period TSTZRANGE, DB-enforced non-overlap, append-only, signed packs)
   generalizes from visa rules to **every norm in the corpus**: "what was in force
   at date T, as known at date K" is the primitive every legal answer stands on.
   Norm lifecycle (berlaku / diubah / dicabut / dicabut-sebagian) is first-class.
3. **Cross-family validation by construction** (W100: same-family agreement lies).
   The KBLI filiera's D0-D6 protocol (independent seats from different model
   families, image/source-grounded re-extraction, signed reports, red-team before
   ship) becomes the **standard ingestion gate**: no norm enters the canonical
   layer on a single model's word.
4. **Abstain-first** (the 5 named gates, panel-ruled divergence). For a system
   speaking law to citizens, a wrong answer is worse than no answer. Evidence
   thresholds per legal domain, verbatim-citation-or-silence policy, and the
   UU Advokat boundary (§1) all enforced at the same gate layer.
5. **Self-healing as an organ, not a hope** (heartbeat sidecars, reconciliation
   reports, liveness detectors — W81/W84 lineage). Every organ ships with: a
   heartbeat probe that reads OUTPUT not exit codes, a built-but-not-armed
   reconciler, and a documented cure path. Green-but-dead is a design bug.
6. **Self-development as a closed loop with an operator gate.** The organism
   grows itself: failed/abstained queries → gap detector → targeted ingestion
   proposals → filiera validation → eval against gold sets → promote. Skills and
   prompts evolve through the same loop (Reflexion-style weekly synthesis).
   **Structural changes still pass Zero** (Legge 5) — autonomy of execution,
   not of constitution.
   **PII rule of the loop (enforceable, not aspirational):** the gap detector
   consumes only aggregate/redacted derivatives of failed queries — topic
   buckets, missing-norm identifiers, domain counts — NEVER raw or reversibly
   pseudonymized query text. Gold sets are built from SYNTHETIC,
   filiera-validated questions, never from copied user queries. No query
   content enters any shared ledger, report, trace, gold set, or
   model-improvement artifact in a form that can be traced back to a person
   (same gate class as the 5 abstain gates: a lint/test on the loop's outputs,
   not a promise in prose).
7. **PII sovereignty is the product** (UU PDP 27/2022, Law 2 output boundary).
   For Indonesian citizens asking about divorce, debt, inheritance, employment
   disputes: query content IS sensitive personal data. No cleartext PII in any
   log/memory/artifact; redaction before any cloud egress; local processing
   lanes for sensitive transforms. Compliance is a feature Indonesians can trust.

## 4. Architecture — seven layers (L0→L6)

```
L0  SOURCES      JDIH network (peraturan.go.id, per-ministry JDIH, JDIH BPK),
                 Lembaran/Berita Negara, Direktori Putusan MA, MK decisions,
                 DJP/OSS/Kemnaker circulars & technical rules
L1  INGESTION    watchers + fetchers; dedup; OCR where needed;
                 Pasal-aware parsing (LegalChunker lineage); source manifests
                 with checksums; NO manual one-shot scripts (audit lesson).
                 Phase 0/1: BATCH-class (invoked or low-frequency cron), NOT
                 standing daemons — continuous watchers only when a venue for
                 standing organs exists (operator decision, §9.4-adjacent)
L2  CANON        the norm-store: bitemporal per-norm + per-pasal records
                 (250-style envelope, Ed25519-signed packs), plus the
                 norm-graph: mengubah / mencabut / melaksanakan /
                 menimbang-cites edges at pasal granularity
L3  VALIDATION   filiera D0-D6 cross-family gates; provenance states
                 (verified / pending / not-classifiable — TRACK-P lineage);
                 gold sets per domain; NAGA-style claim ledger kept ALIVE
L4  REASONING    hybrid retrieval (BM25+dense+RRF+rerank ON by default);
                 subsumption engine (facts → applicable norms via KG);
                 conflict resolution (lex superior/specialis/posterior) as
                 explicit rules, not LLM vibes; multi-hop LangGraph subgraphs
                 per domain; abstain gates wrapping everything
L5  DELIVERY     nuzantara.co.id (web, Bahasa Indonesia), WA channel later;
                 answers = plain-language explanation + verbatim pasal quotes
                 + in-force status + "when to see an advokat" referral block
L6  ORGANISM     heartbeats, reconciliation, gap-driven self-development,
                 eval dashboards, budget governors, immune system
```

**Reuse from Bali Zero (as libraries/patterns, not shared runtime):** LegalChunker,
abstain policy layer, visa-engine substrate schema (generalized to norm-engine),
filiera protocol + tooling, KG subgraph pattern, arsenal routing doctrine.

## 5. Separation model — "non deve appesantire Bali Zero"

| Plane | Bali Zero | NUZANTARA | Shared |
|---|---|---|---|
| Brand/domain | balizero.com | nuzantara.co.id | — |
| Backend/runtime | nuzantara-rag (Fly) | **offline-first on local nodes** (Zero 2026-07-20: no Fly for now — "poi vediamo"; a cloud surface is a later, separate decision) | patterns, code as libs |
| Vector store | existing Qdrant Cloud cluster/collections | **own local store** (bge-m3 embeddings, independent of the frozen Bali Zero embedding) | embedding discipline |
| Relational | nuzantara-postgres | **own local norm-store** (bitemporal, cloned from the 250 design; norm-store scale ≫ CRM scale) | migration discipline |
| Corpus | 5 expat domains, curated | full national corpus, staged by domain | validation method |
| Machines/cron | Pro/Mini load today | Phase 0/1 = batch dev-class on Pro/Mini (invoked jobs / low-frequency cron — NO new standing daemons, the §7 invariant); a venue for standing organs (new node, or reopening cloud) is a FUTURE operator decision, not presupposed here | arsenal quotas |
| Compliance | UU PDP for client files | UU PDP for citizen queries + UU Advokat boundary | Law 2 output rule |

Costs, hosting, and whether ingestion compute lives on a new machine or cloud are
**operator decisions** (§9) — flagged, not assumed.

## 6. Phasing — corpus-first, one domain proven end-to-end before widening

- **Phase 0 — Foundation (the data spine).** Stand up L1+L2 for ONE pilot domain
  and prove the full chain: JDIH fetch → parse → bitemporal canon → filiera
  validation → gold set → served answer with verbatim citations.
  **Pilot domain (Zero's pick, 2026-07-20): ketenagakerjaan** (UU 13/2003 + Cipta
  Kerja stack + PP 35/2021 + Permenaker) — highest dispute volume among ordinary
  Indonesians. Started: `apps/nuzantara-lex/` (PR #2846, seed manifest + verified
  fetcher). Runners-up kept for later widening: KUHP baru (UU 1/2023), UMKM/OSS
  (PP 7/2021) — in that order, unless Zero reorders.
- **Phase 1 — Engine.** Generalize migration-250 substrate to norm-packs; build the
  norm-graph edges; subsumption + conflict-resolution rules; reranker/hybrid ON
  from day one (no disarmed quality levers — audit lesson).
- **Phase 2 — Jurisprudence + public beta.** Targeted putusan MA/MK ingestion for
  the pilot domains (from zero to first thousands, selection-based not exhaustive);
  nuzantara.co.id beta with the referral-to-advokat block; feedback loop live.
  **Declared dependency (not an assumption):** Phase 2 cannot START until Zero
  decides §9.4 (hosting/web surface) and §9.5 (legal review) — offline-first
  Phase 0/1 produces a locally-verifiable engine; making it public is a separate,
  operator-gated act.
- **Phase 3 — Autonomy.** Gap-driven self-development loop fully closed (failed
  queries → ingestion proposals → validation → promote) with Zero gating only
  constitution-level changes; domain-by-domain widening toward the full corpus.

Each phase has a hard exit gate measured on the metrics below — no phase is "done"
by narrative (Legge 7). **Metric-definition gate (F8/K6):** every §7 metric gets
its operational definition (denominator, labeling protocol, threshold, sampling
plan) written into the Phase-0 eval-harness doc BEFORE the first exit-gate
evaluation; until then §7 is a metric catalog, not a passable gate. False-answer
rate in particular requires a named labeling loop (sampled served answers,
filiera-verified) — without a labeler it is not a metric.

## 7. Metrics (Legge 7 — no number, no improvement)

- **Coverage:** norms in canon / norms in scope for active domains (per-domain %).
  Denominator = the domain's **seed-manifest registry** (append-only, versioned —
  ketenagakerjaan starts at 15), NOT "all national norms" (no authoritative count
  exists; a closed, auditable registry per domain is the only honest denominator).
- **Freshness lag:** median days from Lembaran Negara publication → validated in canon.
- **Citation integrity:** % of served answers where every legal claim carries a
  verbatim, source-linked, in-force-checked citation. Target 100% enforced by the
  L4 gate — **and measured independently of it** (K6: a gate measuring itself reads
  100% by construction): a periodic filiera-style sample audit re-verifies served
  answers against sources with a seat that is not the serving stack.
- **Accuracy:** gold-set score per domain (filiera-validated), measured per release.
- **Abstain quality:** abstain rate + false-answer rate (the pair, never one alone).
- **Organism health:** % organs with live heartbeat; built-but-not-armed count
  (target: 0 standing); mean-time-to-self-heal.
- **Load isolation:** zero net new standing daemons on Pro/Mini attributable to
  NUZANTARA runtime (dev excluded) — the "non appesantire" invariant, measured.

## 8. Risks & mitigations

1. **UU Advokat boundary drift** — disclaimers alone do NOT hold this line
   (adversarial review F3). Structural mitigations, all L4-enforced: (a) an
   **advice-vs-information classifier** in front of delivery — queries asking to
   apply law to the asker's personal facts hard-route to the referral block
   (general-education answer + "see an advokat", never an individualized
   opinion); (b) **no paid feature may ever sit on the advice side** of that
   classifier — monetization, if any, stays on information/education surfaces;
   (c) referral block + abstain gate remain structural (L4); (d) the boundary
   and ToS are reviewed by a licensed advokat before any public beta (§9.5);
   (e) **composition-layer test (K8)**: the classifier on the incoming query is
   not enough — the COMPOSED answer passes a generality check before delivery
   (no "in your case you should…" constructions; guilt+innocence test corpus per
   superscar #3, so the guard neither blesses advice nor blocks plain education).
2. **Wrong-answer harm to citizens** — mitigation: citation-or-silence policy,
   cross-family validation, per-domain evidence thresholds stricter than Bali Zero's.
3. **Corpus scale (93k → millions of chunks)** — mitigation: staged domains, own
   infra plane, ingestion budget governor; never big-bang. **Throughput-budget
   gate (K5):** before widening past the pilot domain, the Phase-1 exit gate must
   include measured validation throughput math — norms/day per seat, cost per
   validated norm, projected backlog at that rate (Legge 7). If the math says the
   full corpus takes decades on free quota, that surfaces HERE, as a number Zero
   can act on — not as silent drift.
4. **Source instability** (JDIH outages, format drift, anti-bot walls — already seen
   at Bali Zero: hukumonline 403, pajak.go.id JS-shell) — mitigation: multi-source
   redundancy per norm, checksum manifests, honest blocked-source ledger (the
   regulatory-watcher already models this behavior well).
5. **Quota/compute pressure on the existing arsenal** — mitigation: NUZANTARA
   ingestion/validation lanes get their own budget envelope; Bali Zero lanes have
   priority on MAX windows by default until Zero rules otherwise.
6. **Two organisms, one team** — mitigation: strict lane separation in PENDING-ARMS
   ledgers; NUZANTARA work never blocks a Bali Zero P0.

## 9. §Solo-operatore — decisions only Zero can make

Closed 2026-07-20 (see §0): ~~1. Ratify this charter~~ ✅ ratified ·
~~2. Pilot domain pick~~ ✅ ketenagakerjaan · ~~3. Infra & budget envelope~~ ✅
offline-first, no Fly for now, no new cloud spend ("poi vediamo").

Still open (operator-only):

4. **Domain plumbing**: confirm nuzantara.co.id registrar/DNS control and renewal
   state (bought ~2025 — verify expiry), decide hosting target for the web surface
   (moot until the offline-first phase produces something to serve publicly).
5. **Legal review of the information-vs-services boundary** (§1) with a licensed
   advokat before any public beta.
6. **Brand**: is the public face "Zantara" (shared persona) or a NUZANTARA-native
   persona? Affects trust architecture and Bali Zero separation. (One-brain-two-bodies
   §0 constrains but does not settle this: the brain is one; whether the second body
   *speaks* as Zantara is a brand call.)

## 10. Immediate next steps (ratified — in motion)

1. ✅ Phase-0 spike STARTED: `apps/nuzantara-lex/` (PR #2846) — BPK fetcher with
   content-identity verification + seed manifest (15 norms, 5 verified sha256).
   Next iteration: Pasal parser + local bitemporal norm-store cloned from the 250
   design + bge-m3 embeddings — **with its initial corpus loaded** (principle #1).
2. Generalize the filiera runbook from KBLI codes to norms (D0-D6 mapping doc).
3. Gold set v0 for ketenagakerjaan (50-100 QA pairs, filiera-validated).
4. Eval harness wired before the first public answer, not after.

---
*Charter drafted 2026-07-19 by the session that ran the full KB audit, as the
design child of that audit. Supersedes nothing; proposes everything.*

## Adversarial review

**Seats (cross-family, generator≠grader):** Codex `gpt-5.6-sol` (reasoning effort
high) — verdict **REJECT**, 5×P0 + 3×P1 — and Kimi `K3` — verdict
**SHIP-WITH-FIXES**, 2×P0 + 3×P1 + 3×P2. Run 2026-07-20 on the ratified draft
(post-§0). Strong cross-family convergence on the PII boundary, the metrics, and
the UU Advokat gap. Every finding was cured in-place in this same commit (W86
discipline); disposition below. Codex's REJECT was judged correct against the
PRE-cure text — the cures below are what turned it shippable.

| # | Finding (seat) | Disposition |
|---|---|---|
| F1/K1 [P0] | "everything the brain learns is shared" contradicts "data NEVER shared" — learning artifacts can carry query-derived PII across bodies | **Fixed** §0: explicit crosses/never-crosses lists; learning crosses only as aggregate, redacted, provenance-tagged artifacts |
| F2 [P0] | failed queries feed self-development with no enforceable PII rule | **Fixed** §3.6: gap detector consumes only aggregate/redacted derivatives; gold sets synthetic-only; lint/test-class gate on loop outputs |
| F3/K8 [P0/P2] | disclaimers don't hold the UU Advokat line; no advice-vs-information enforcement | **Fixed** §8.1: advice-vs-information classifier, no-paid-advice rule, composition-layer generality check with guilt+innocence corpus, advokat review pre-beta |
| F4 [P0] | hybrid/reranker flip without recalibrating the 5 abstain gates | **Fixed in activation plan** lever #1/#2 gate: abstain-matrix before/after + low-evidence must-stay-abstained set |
| F5 [P0] | re-ingestion without pinning embedding/chunking/point-IDs | **Fixed in activation plan** lever #13 gate: pin `text-embedding-3-small`/1536, identical chunking, deterministic IDs, per-vector spot-check |
| K2 [P0] | L1 continuous watchers + L6 heartbeats = standing daemons with no permitted venue | **Fixed** §4 L1 + §5 machines row: Phase 0/1 is batch dev-class; continuous organs only when a venue exists (operator decision, not presupposed) |
| F6 [P1] | offline-first vs cross-family validation compute | **Fixed** §0: offline-first scoped to runtime/serving/data; dev validation uses existing flat CLI seats (no new infra/spend); local-family degradation path named |
| F7 [P1] | Phase 2 assumes hosting that doesn't exist | **Fixed** §6: Phase 2 has a declared dependency on §9.4+§9.5 — cannot start before |
| K3 [P1] | §2 "proven/above-SOTA" contradicted by sibling plan (hybrid OFF, 250 unapplied) | **Fixed** §2: honesty clause — method proven, skeleton partially armed; 250 applies with next deploy |
| K4 [P1] | activation lever #2(b) external reranker = PII egress | **Fixed in activation plan**: option (b) requires explicit PDP/redaction gate; local ONNX preferred |
| K5 [P1] | corpus-scale validation unbudgeted | **Fixed** §8.3: Phase-1 exit gate includes measured throughput math (norms/day, cost/norm, backlog projection) |
| F8/K6 [P1/P2] | metrics unfalsifiable; citation-integrity gate measures itself | **Fixed** §6+§7: metric-definition gate pre-exit-eval; coverage denominator = seed-manifest registry; independent sample audit for citation integrity; false-answer rate requires named labeler |
| K7 [P2] | lever #11 would grant a role to an RBAC-`unknown` principal | **Fixed in activation plan**: identity resolution FIRST, grant only to an identified principal |
