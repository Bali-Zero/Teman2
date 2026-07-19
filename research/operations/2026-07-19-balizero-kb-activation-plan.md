---
date: 2026-07-19
domain: operations
project: Bali Zero KB activation (Lane A of the twin mandate)
status: ACTIVE — working ledger, update as levers land
adversarial_review: codex
client_case: none
sources:
  - 2026-07-19 full KB audit (4-reader sweep, session 932b2e53)
  - research/operations/2026-07-19-nuzantara-co-id-avvocato-totale-charter-v0.md (Lane B sibling)
---

# Bali Zero KB — Activation Plan (post-audit, 2026-07-19)

> Mandate (Zero, 2026-07-19): *"iniziamo l'attivazione e potenziamento di quello che
> manca a Bali Zero"* — twin of the NUZANTARA charter. This file is the operative
> ledger for Lane A: every disarmed/degraded lever found by the audit, with owner,
> gate, and verified state. **Rule of the lane: arm what exists before building
> anything new** (the audit's meta-pattern was Esiste≠Armato applied to knowledge).

## Levers, by leverage order

| # | Lever | Verified state (2026-07-19) | Action | Owner | Gate/risk |
|---|---|---|---|---|---|
| 1 | **Hybrid search ON in prod** | `enable_hybrid_search=False` default (`config.py:346-350`); collections carry BM25 sparse vectors since migration 031b; no fly.toml override | Flip via env on Fly + A/B smoke on golden queries (visa/kbli/tax) before+after; watch p95 latency. **Abstain-recalibration gate (adversarial F4): hybrid fusion changes the score distribution the 5 named abstain gates were calibrated on — before the flip goes live, run the golden abstain matrix (`test_abstain_policy_hardening.py`) PLUS a low-evidence query set that MUST remain abstained, before/after; any formerly-abstained answer that now passes = BLOCKER, re-derive thresholds with the panel rule** | session lane | Low risk on latency, NOT on abstain semantics (see gate). Verify per-collection sparse-vector presence FIRST — 031b covered tax_genius, pricing, training, visa_oracle, legal_unified; NOT necessarily kbli/news/curated_qa |
| 2 | **Reranker in prod** | Code-complete, `enable_reranker=False` ("Saves ~5GB Docker image"); `visa_oracle.py:918` says "cross-encoder not available on Fly"; nuzantara-rag = shared-2x/2GB RAM | NOT a blind flip. Spike doc comparing: (a) torch-free ONNX cross-encoder in rag process, (b) zerank2/ZeroEntropy external API, (c) stay off. Measure answer-quality delta on gold sets. Same abstain-recalibration gate as lever #1 (F4). **PDP egress gate (adversarial K4): option (b) sends raw query+chunk text to a third party — queries/chunks can carry client PII, so (b) is admissible ONLY behind an explicit redaction gate + DPA review; "already wired" is plumbing, not compliance. Default preference: (a) local ONNX or (c) stay off** | session lane (spike) | Image size + RAM ceiling on 2GB machine; external API = new cost → needs Zero if paid, AND PDP gate (K4) regardless of cost |
| 3 | **Migration 250 applied to prod** | Re-verified live this morning via `scripts/pg.sh`: tracker tops at `248_clients_npwp_strongid` (03:00 UTC). PR #2804 merged, file on main | Belongs to **lane S3 (visa-engine session)** — do not touch from other lanes (quad-session anti-collision). If still unapplied at next reconciliation, raise with Zero | lane S3 | Migration class = operator-adjacent gates; DB-state probe after apply per modus SHIP |
| 4 | **Visa rule-pack CONTENT + activation writer** | Substrate shipped (250), key ceremony done 2026-07-19 (session memory; visaoracle skill not yet updated), but zero production rule content, no writer (deferred "STEP 6") | Lane S3 roadmap: author first real rule-packs (114-code catalog → declarative rules), build activation writer | lane S3 | The engine stays ornamental until cargo loads (charter principle #1) |
| 5 | **`/api/drive/*` regression fix** | ALL 3 endpoints broken: `FileItem` Pydantic model requires `type`, constructor doesn't populate it (404 stats / 500 files / 500 search, correlation IDs in audit) | Locate model + constructor, fix (populate from mimeType or default), add regression test | **this session (in flight)** | Small, CI-gated; L2 auto-merge |
| 6 | **Peraturan feeder (Sheet→PDF→NB-6)** | Dead 5+ weeks: every run fails on missing `GOOGLE_SERVICE_ACCOUNT_JSON` (log last entry 2026-06-16) | Operator provides/rotates the credential; then session re-arms + proves one green run end-to-end | operator[credential] → session | Without it NB-6 compliance ground truth stales |
| 7 | **Regulatory-watcher cadence** | 33 deltas over 64 days ≈ 52% day-coverage (gaps 05-31→06-10, 06-18→06-28); per-day quality high | Read the wrapper's own logs for gap-days: quota-cascade vs launchd death vs TCC (W84 class). Fix the actual cause, add day-coverage metric to proprioception | session lane | Don't guess the cause — read the log first (anti-pattern rule) |
| 8 | **KBLI schema drift vs CLAUDE.md §9** | Live table `kbli_documents`: `sektor_id`/`pma_status` NESTED in `metadata` jsonb on all 1,563 rows; `kategori_risiko` absent everywhere; `skala_usaha`→`per_skala`. CLAUDE.md §9 says flat/never-nested | Reconcile WITH the kbli-navigator lane: either the invariant doc is stale (likely — table carries newer keys like `kode_kbli_2025`, `pp28_sources`) or the table regressed. Update whichever is wrong; add tripwire test | kbli lane + session | CLAUDE.md §9 is marked NEVER VIOLATE — the contradiction itself is the bug |
| 9 | **NAGA claim ledger** | 3,119 claims / 6,980 evidence rows, stale since 2026-05-07 | Zero decides: revive as the claim-verification organ (charter L3 wants it alive) or archive formally. No zombie middle state | operator[business] | — |
| 10 | **NB hygiene** | 96 NBs / 5,643 sources; 24 empty shells, 11 never-populated "Research" shells, 6 self-marked deprecated (MERGED/ARCHIVED 2026-05-07) still live | Propose deletion/merge list to Zero (NB deletion = confirm-gated); populate-or-delete ruling for the 11 shells | session proposes, Zero confirms | notebook_delete is destructive → explicit confirm |
| 11 | **MCP observability lies** | `get_collection_stats` + `get_qdrant_metrics` return the same zeroed op-counter, NOT per-collection stats (tool description promises otherwise); MCP caller has RBAC role `unknown` → all content tools 403 | Fix handlers to hit Qdrant `/collections` for real. **Identity-first rule (adversarial K7): the RBAC role resolving as `unknown` is the defect — fix identity resolution FIRST; a role is granted only to an IDENTIFIED principal, never to whatever `unknown` happens to be. If the block is intended, document it; never grant-to-unknown as a shortcut** | session lane | Small; restores self-inspection ability the audit had to work around |
| 12 | **Orphan corpora** | `apps/kb/data/immigration/` 84 raw txt (unreferenced anywhere); `apps/kbli-navigator/data/` second KBLI dataset copy, sync unverified; `backend/kb/raw/top5_wave3/` empty stubs | Archive or re-wire the 84 txt; add sync check (or single-source) for kbli-navigator data; delete stub scaffold | session lane | Low; reduces fragmentation (audit found ≥6 uncoordinated KB locations) |
| 13 | **Tier1 legal PDFs → automated re-ingestion** | 517MB verified on disk (`data/kb_sources/`), wired to `ingest_tier1_gaps.py`/`ingest_2026_laws.py` but MANUAL invocation only; Qdrant freshness unconfirmed | Run a verified re-ingestion pass (dry-run → apply), then decide cadence (event-driven on new PDFs, not blind cron). **Embedding-invariant gate (adversarial F5): the pass MUST pin `text-embedding-3-small`/1536 dims explicitly, keep chunking config byte-identical to the collections' existing strategy, and use deterministic point IDs (idempotent re-runs, no silent duplicates). Proof = point-count delta AND per-vector spot-check (named-vector config + dims + a sampled cosine sanity on unchanged docs) — count alone cannot detect mixed embeddings (frozen-invariant breach)** | session lane | Needs Qdrant write path + before/after proof per the F5 gate (Legge 7) |

## Done this session

- Audit itself (4 readers + final-gate spot checks) — findings in memory
  `AUDIT KB COMPLETO 2026-07-19`, report delivered in session.
- Live re-verification of migration-250 non-application (pg.sh, tracker at 248).
- Prod health disambiguation: `zantara.balizero.com/health` = 200 healthy; the
  "critical/search unavailable" seen via MCP is the local MCP api-process path,
  not prod (fly-split-brain class, no P0).
- Lever #5 (`/api/drive/*` fix): started by this session — see PR reference below
  once opened.

## Standing rules for this ledger

1. A lever is DONE only at PROVE-LIVE (output observed, not exit code).
2. Levers owned by other live lanes (S3 visa) are tracked here but never executed
   from this lane — reconcile at boundaries, don't collide (scar family #5).
3. New levers discovered while working land HERE first, then get an owner.

## Adversarial review

**Seats (cross-family):** Codex `gpt-5.6-sol` (REJECT pre-cure) + Kimi `K3`
(SHIP-WITH-FIXES), run 2026-07-20 together with the sibling charter — full finding
table and dispositions live in the charter's `## Adversarial review` section
(single source, same PR). Findings that landed IN THIS FILE, cured in-place:

- **F4 [P0]** levers #1/#2 — hybrid/reranker flips change score distributions:
  added the abstain-recalibration gate (golden abstain matrix + must-stay-abstained
  low-evidence set, before/after; regression = BLOCKER).
- **K4 [P1]** lever #2(b) — external reranker API egresses query+chunk text:
  added the PDP/redaction gate; local ONNX preferred by default.
- **F5 [P0]** lever #13 — re-ingestion could breach the frozen-embedding invariant:
  added the embedding-invariant gate (pin model/dims, identical chunking,
  deterministic IDs, per-vector spot-check — count alone proves nothing).
- **K7 [P2]** lever #11 — never grant a role to an RBAC-`unknown` principal:
  identity resolution first, grant only to an identified principal.
