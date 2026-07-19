---
date: 2026-07-19
domain: operations
project: NUZANTARA (nuzantara.co.id)
status: PROPOSAL v0 — awaiting Zero's ratification (Legge 5)
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
~5-10% of the corpus a total lawyer needs, zero jurisprudence" — but with an
architecture already **above state-of-the-art** for the job: hybrid retrieval with
Pasal-aware chunking, 5-gate abstain policy, LangGraph multi-hop KG (116k nodes),
a signed bitemporal rule substrate (migration 250), and a proven cross-family
validation method (KBLI filiera). **The bottleneck is not engineering — it is
corpus loading + continuous validation.** That is exactly the kind of problem an
autonomous organism is built to grind through. NUZANTARA is the project that takes
the proven skeleton and gives it the full body of Indonesian law.

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
L1  INGESTION    continuous watchers + fetchers; dedup; OCR where needed;
                 Pasal-aware parsing (LegalChunker lineage); source manifests
                 with checksums; NO manual one-shot scripts (audit lesson)
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
| Backend/runtime | nuzantara-rag (Fly) | **own app** (new Fly app or equivalent — sized for a much larger corpus) | patterns, code as libs |
| Vector store | existing Qdrant Cloud cluster/collections | **own cluster or hard-separated namespace** | embedding discipline |
| Relational | nuzantara-postgres | **own DB** (norm-store scale ≫ CRM scale) | migration discipline |
| Corpus | 5 expat domains, curated | full national corpus, staged by domain | validation method |
| Machines/cron | Pro/Mini load today | must NOT add standing load to Pro/Mini beyond dev; heavy ingestion runs where Zero decides (cloud vs new node) | arsenal quotas |
| Compliance | UU PDP for client files | UU PDP for citizen queries + UU Advokat boundary | Law 2 output rule |

Costs, hosting, and whether ingestion compute lives on a new machine or cloud are
**operator decisions** (§9) — flagged, not assumed.

## 6. Phasing — corpus-first, one domain proven end-to-end before widening

- **Phase 0 — Foundation (the data spine).** Stand up L1+L2 for ONE pilot domain
  and prove the full chain: JDIH fetch → parse → bitemporal canon → filiera
  validation → gold set → served answer with verbatim citations. Candidate pilot
  domains (chosen for citizen impact + bounded corpus; final pick = Zero):
  1. **Ketenagakerjaan** (UU 13/2003 + Cipta Kerja stack + PP 35/2021 + Permenaker) —
     highest dispute volume among ordinary Indonesians;
  2. **KUHP baru** (UU 1/2023, in force since 2026-01-02) — the whole country needs
     to understand the new penal code; bounded (one code + implementing regs);
  3. **UMKM/OSS** (PP 7/2021, perizinan berusaha) — direct reuse of KBLI mastery.
- **Phase 1 — Engine.** Generalize migration-250 substrate to norm-packs; build the
  norm-graph edges; subsumption + conflict-resolution rules; reranker/hybrid ON
  from day one (no disarmed quality levers — audit lesson).
- **Phase 2 — Jurisprudence + public beta.** Targeted putusan MA/MK ingestion for
  the pilot domains (from zero to first thousands, selection-based not exhaustive);
  nuzantara.co.id beta with the referral-to-advokat block; feedback loop live.
- **Phase 3 — Autonomy.** Gap-driven self-development loop fully closed (failed
  queries → ingestion proposals → validation → promote) with Zero gating only
  constitution-level changes; domain-by-domain widening toward the full corpus.

Each phase has a hard exit gate measured on the metrics below — no phase is "done"
by narrative (Legge 7).

## 7. Metrics (Legge 7 — no number, no improvement)

- **Coverage:** norms in canon / norms in scope for active domains (per-domain %).
- **Freshness lag:** median days from Lembaran Negara publication → validated in canon.
- **Citation integrity:** % of served answers where every legal claim carries a
  verbatim, source-linked, in-force-checked citation (target: 100%, enforced by gate).
- **Accuracy:** gold-set score per domain (filiera-validated), measured per release.
- **Abstain quality:** abstain rate + false-answer rate (the pair, never one alone).
- **Organism health:** % organs with live heartbeat; built-but-not-armed count
  (target: 0 standing); mean-time-to-self-heal.
- **Load isolation:** zero net new standing daemons on Pro/Mini attributable to
  NUZANTARA runtime (dev excluded) — the "non appesantire" invariant, measured.

## 8. Risks & mitigations

1. **UU Advokat boundary drift** — mitigation: the referral block + abstain gate are
   structural (L4), reviewed legally before public beta; ToS language operator-approved.
2. **Wrong-answer harm to citizens** — mitigation: citation-or-silence policy,
   cross-family validation, per-domain evidence thresholds stricter than Bali Zero's.
3. **Corpus scale (93k → millions of chunks)** — mitigation: staged domains, own
   infra plane, ingestion budget governor; never big-bang.
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

1. **Ratify this charter** (or amend) — it is a v0 proposal, not doctrine.
2. **Pilot domain pick** (§6 Phase 0: ketenagakerjaan vs KUHP baru vs UMKM/OSS —
   recommendation: ketenagakerjaan for impact, KUHP for momentum; both are defensible).
3. **Infra & budget envelope**: new Fly app? separate Qdrant cluster? a dedicated
   ingestion node? monthly cost ceiling.
4. **Domain plumbing**: confirm nuzantara.co.id registrar/DNS control and renewal
   state (bought ~2025 — verify expiry), decide hosting target for the web surface.
5. **Legal review of the information-vs-services boundary** (§1) with a licensed
   advokat before any public beta.
6. **Brand**: is the public face "Zantara" (shared persona) or a NUZANTARA-native
   persona? Affects trust architecture and Bali Zero separation.

## 10. Immediate next steps (once ratified)

1. Phase-0 spike: JDIH/peraturan.go.id fetcher + Pasal parser against the pilot
   domain's top-20 norms, landing in a `norm_packs` table cloned from the 250
   design — **with its initial corpus loaded** (principle #1).
2. Generalize the filiera runbook from KBLI codes to norms (D0-D6 mapping doc).
3. Gold set v0 for the pilot domain (50-100 QA pairs, filiera-validated).
4. Eval harness wired before the first public answer, not after.

---
*Charter drafted 2026-07-19 by the session that ran the full KB audit, as the
design child of that audit. Supersedes nothing; proposes everything.*
