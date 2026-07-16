---
date: 2026-07-16
domain: operations
client_case: none (execution architecture for the KBLI Filiera program)
adversarial_review: codex
sources:
  - "companion: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, L0-L6, G13-G17)"
  - "mandate: Zero 2026-07-16 — 'ideare il workflow di agenti e LLM, scegliere l'orchestratore-mente-immobile, programma di ricostruzione dei singoli KBLI in maniera scientifica'"
  - "live enumeration 2026-07-16 on KBLI_2025_FINAL_CLEAN.json (119 / 478 / 1,263 / ~175 risk classes)"
  - "adversarial panel 2026-07-16: Codex GPT-5.5 red-team (12 findings, 4 FATAL) + Gemini 3.1 Pro costruttivo (10 suggestions)"
---

# GARUDA-FILIERA — the per-code KBLI reconstruction program (agents, seats, orchestrator)

> The companion methodology doc defines WHAT a correct corpus is. This doc defines WHO builds it
> and HOW: the unmoved-mover orchestration, the seat assignments, the per-code scientific
> protocol, batching, sampling statistics, and failure rules. Discrepancy findings stay INTERNAL
> (Zero, 2026-07-16) — the 68112 clarification letter stays drafted-not-sent.

## 1. The unmoved mover (mente immobile)

**Orchestrator of record: Fable 5 — the interactive session.**
- Doctrine AND hook-enforced no-hands: `model_routing_gate.py` blocks Agent dispatch without an
  explicit implementer model; edit/commit/push belong to implementer seats; Fable keeps triage,
  design, synthesis, and the final on-disk gate.
- The final-gate invariant (never cascades to a weaker judge; window dead → SUSPEND) is exactly
  the adjudicator property a scientific program needs.
- **Accepted SPOF, by design** (red-team F1): Fable is planner + adjudicator + gate. Mitigation is
  durable state (dossier event-logs, quarantine ledger, batch reports all on disk), suspension at
  batch boundaries only, and extraction lanes that keep running on non-blocked codes while the
  adjudication backlog waits. Mitigation is NEVER a weaker substitute judge.

**Three-layer division of labor** (the "hands problem" solved structurally):
1. **Nous (Fable)** — authors batch plans + acceptance criteria BEFORE extraction
   (pre-registration), adjudicates quarantines/collisions, runs the final empirical gate against
   raw vault evidence, signs batch reports. Never extracts, never writes data.
2. **Mechanical layer (Workflow scripts)** — deterministic JS control flow: fan-out, schema
   enforcement (structured output), resume, budget caps. No hands either: all work happens in
   seats or compilers.
3. **Deterministic compilers (Python, no LLM)** — the ONLY writers of dossiers and canonical
   deltas. An LLM never manufactures a deterministic fact (Garuda law): LLM output is always a
   PROPOSAL that a compiler validates against schema + evidence pointers before it lands.

## 2. Seat table

| Seat | Model / tool | Invocation | Role |
|---|---|---|---|
| Mente immobile, final gate | **Fable 5** (max effort) | interactive session | batch plans, quarantine adjudication, final empirical gate, sign-off |
| Mechanical orchestrator | **Workflow scripts** | `Workflow` tool | deterministic fan-out, resume, budget caps |
| Canonical/dossier writers | **Python compilers** | `scripts/kbli_filiera/*.py` | evidence pull, assembly, censuses, invariants, quarantine enforcement, emit |
| Extractor | **Sonnet 5** (`model:"sonnet"`) | Workflow `agent()` | structured extraction from lampiran IMAGE renders; crosswalk mapping proposals with uraian-level rationale |
| Vision locator | **qwen2.5vl:7b** (Ollama, Mini) | local batch | page/row triage on 300-dpi renders — LOCATOR ONLY, never the reader |
| Width / regulatory search | **Gemini via `agy`** | CLI background | normativa search; long-context volume reads; BPS-table ingestion checks |
| Red-team | **Codex GPT-5.5** | `codex exec --sandbox read-only < /dev/null` | attack mapping proposals + batch reports; sandbox checks on compiler outputs |
| Refuter (3rd family) | **GLM 5.2 → DeepSeek v4-pro → (swap rule §6)** | probe-then-cascade | blind re-extraction + falsification of non-deterministic facts |
| Ground truth | **NotebookLM** (bipolar) | MCP | regulatory-claim verification ONLY with W90 freshness check |
| Operator | **Zero** | Legge 5 | batch GO, publish decisions, consents |

**Family-independence pairing rule (red-team F10):** per batch, extractor ≠ refuter ≠ red-team
model FAMILIES. If the refuter cascade lands on Codex, the red-team seat for that batch swaps to
agy. If three families are not available → declared degraded council + tightened sampling (§5),
never silent correlation.

## 3. Per-code scientific protocol (dossier D0→D6)

Dossier = **JSONL event log** (`data/kbli-filiera/dossiers/<code>.jsonl`): each stage appends an
event `(seq, stage, op_id, input_digests, output, sha256(prev_event))` — a light hash chain.
`op_id = sha256(code | stage | input digests)`: re-running a completed op is a no-op
(idempotent resume, red-team F2). One writer per dossier, enforced via the existing Redis lease
registry (`agent_lock:kbli-dossier:<code>`); each batch reads a **pinned vault-manifest
revision**, and the canonical delta PR re-checks the canonical revision at emit (fencing —
red-team F3).

- **D0 Evidence pull (deterministic).** Vault items for the code: BPS row, dated OSS snapshot
  (detail + ruang-lingkup + umku), official crosswalk row(s), PP28 lampiran render(s),
  Perpres 10/49-2021 annex hits, Bali overlay, Kepmenaker rows. **ABSENT is earned, not
  defaulted** (red-team F7): each source has a declared endpoint inventory; a crawl is complete
  only if attempted = enumerated; a 404/absence counts as evidence only when ≥3 attempts over
  ≥72h AND a **negative control** (a known-present code) returned data in the same crawl window.
- **D1 Crosswalk adjudication.** NO deterministic acceptance, not even 1-to-1 (red-team F4: a
  renamed/redefined 1-to-1 code can change semantics): 1-to-1 rows pass an automated
  **uraian-equivalence check** (2020 vs 2025 text; material divergence → LLM semantic comparison);
  splits/merges get full semantic adjudication — Sonnet proposes with uraian-level rationale,
  refuter attacks, disagreement → QUARANTINE for Fable. Title-similarity mapping is forbidden.
- **D2 Extraction (image-verified, self-confirming).** qwen2.5vl locates the row → Sonnet
  extracts structured fields FROM THE IMAGE — and must independently confirm the code string
  appears in the extracted row and report the neighboring rows' codes (locator-poisoning guard,
  red-team F8). Mismatch → quarantine. Every field carries (render digest, page, row locator).
- **D3 Assembly (deterministic).** Candidate facts: strict schema, per-fact provenance +
  temporal validity + vintage tags + element-level confidence + `refutation_history` array.
- **D4 Discrepancy & completeness scan (deterministic core).** Cross-layer comparison
  (BPS/OSS/PP28/Perpres) PLUS **completeness invariants** (red-team F9): row-count reconciliation
  per lampiran page vs extracted rows; census reconciliation per source. Conflicts → collision
  record, INTERNAL intel, never merged silently.
- **D5 Independent verification (anti-correlation, red-team F5).** The refuter does not grade
  the extractor's output: for licensing facts it performs **blind re-extraction** (gets render +
  code, NOT the extractor's answer); compiler diffs the two extractions — agreement certifies,
  divergence quarantines. Inter-extractor agreement is tracked per batch (Gemini: IAA); NLM
  bipolar on regulatory claims with freshness discipline. Per-fact verdict:
  `certified | quarantined(reason,owner) | abstained(reason)`.
- **D6 Batch gate.** Deterministic censuses + G13-G17 → **Fable final empirical gate** (§5
  sampling rules) against raw vault evidence, never seat summaries → sign-off → compiler emits
  canonical vNext delta → worktree PR with tests; every negative finding becomes a permanent
  sentinel code.

**Why "scientific":** pre-registration · falsifiability (every fact refutable against vault
evidence) · reproducibility (same vault + curatela → byte-identical, G16) · independence
(extractor ≠ refuter ≠ red-team families; blind double extraction) · complete audit chain ·
abstention over invention · **calibration and control** (§5: gold-set, control limits, mutation
tests).

## 4. Batching (risk classes, live enumeration 2026-07-16)

| Batch | Set | Size | Inspection regime (§5) | Work shape |
|---|---|---|---|---|
| 0 | Vault bootstrap | — | — | BPS conversion table (Vol.1+2, tokenized web-api link), PP28 lampiran 300-dpi renders, full OSS re-snapshot, Perpres annexes. Blobs: Mini `~/nuzantara-vault/` + **versioned** Tigris bucket; sha256 manifest committed in git (the durable truth — red-team F12). |
| A | PP28-derived licensing, no OSS source | **119** | **100% review** (Gemini: risk-stratified) | full D0-D6; includes the 68112 siblings |
| B | Cross-code stitches (`pp28_sources` → other codes) | **478** | AQL tightened start | D1-heavy; D2 only where licensing inherited |
| C | OSS-native with PP28 secondary | **1,263** | deterministic leak-check + AQL loosening after clean runs | LLM only on flagged anomalies |
| D | Pure OSS-native | ~175 | sampled | deterministic re-derive from OSS snapshot |

Sets overlap; membership resolved A→B→C→D (a code audits once, in its highest class).
**Pilot A1 (first run): ~15 codes** including 68112 and the sentinel set — its purpose is to
MEASURE service times, quota burn, and disagreement rates before any cadence commitment
(red-team F11: no throughput promises before measurement). Batches are processed in taxonomy
order within a class (division/group) to maximize prompt-cache reuse (Gemini).

## 5. Sampling, calibration, control (replaces naive 10%/min-12 — red-team F6)

- **Batch A: 100% Fable review** of all licensing facts (119 codes is affordable; it is also the
  gold-set nursery).
- **Batches B/C/D: AQL-style adaptive acceptance** (ISO 2859 spirit): start tightened; loosen
  only after N consecutive defect-free lots; ANY defect found re-tightens and triggers a
  root-cause pass over the lot (a defect is assumed SYSTEMATIC — stratified by page/template/
  field/source — until proven isolated, because dossier-level random sampling misses stratified
  errors).
- **Hidden gold-set** (Gemini): pre-verified codes injected into every run; a grader/extractor
  miss on a gold item halts the lot (calibration + drift detection).
- **Mutation testing** (Gemini): periodically inject corrupted intermediates; the refuter/compiler
  MUST catch them — an uncaught mutation is a program-level defect (verification theater made
  measurable).
- **Telemetry with control limits** (Gemini): rejection rate, refutation categories, IAA,
  token/dossier — breach of a control limit pauses the lane, alerts, and requires a signed
  resume.
- **Quarantine auto-triage** (Gemini): `schema_error` → back to compiler lane automatically;
  `logic_conflict`/`semantic` → Fable adjudication queue.

## 6. Failure & degradation rules

- Seat probe-dead → declared degraded + pairing-matrix swap (§2) + PENDING-ARMS line for the seat.
- Fable window dead → program SUSPENDS at batch boundary; durable state carries; no substitute
  judge.
- Workflow interruption → resume via `resumeFromRunId`; op_id idempotency makes replays no-ops.
- Compiler exception / schema violation → code to quarantine, batch continues (fail-visible).
- OSS snapshot anomaly (count drift, schema drift, WAF signature) → Batch-0 refresh halts +
  alert; a lone 404 never flips a fact.
- Vault: Mini is primary, Tigris versioned mirror is the durability layer, the git manifest is
  the integrity layer; a batch pins its manifest revision, so a mid-batch vault refresh cannot
  change evidence under a running lot.

## 7. Program state

- `data/kbli-filiera/manifest/` — vault manifest (sha256 + URL + fetch date per item), versioned.
- `data/kbli-filiera/dossiers/<code>.jsonl` — hash-chained stage events (schema-versioned).
- `data/kbli-filiera/quarantine.md` — state machine ledger (reason, owner, resolution criteria).
- `data/kbli-filiera/batch-reports/` — signed reports: censuses, verdicts, IAA, gold-set hits,
  sample lists, measured service times.
- Output feeds Filiera Fase 2 directly: the reproducible canonical builder and the per-code KG
  regenerator consume dossiers, no re-derivation.

## 8. §Solo-operatore

1. **GO per batch** (not per code): pilot A1 first; its measured report is the basis for the
   cadence decision.
2. Consents already given/parked: discrepanze INTERNE (2026-07-16); OSS snapshot cron = Fase 3,
   "se serve", armed only with liveness receptors.
3. Business calls that may emerge from collisions (e.g., how to advise clients on 68112-class
   codes while OSS is silent) — per case, Legge 5.

## Adversarial review (generator≠grader panel record)

- **Codex GPT-5.5 red-team, 12 findings (4 FATAL, 8 MAJOR)** — all incorporated: F1 SPOF →
  accepted-by-design with durable-state mitigation (§1); F2 resume → op_id idempotency + hash
  chain (§3); F3 races → leases + pinned manifests + fencing (§3); F4 crosswalk overreach → no
  deterministic 1-to-1 acceptance, uraian-equivalence check (§3 D1); F5 correlated verification →
  blind re-extraction (§3 D5); F6 sampling under-power → §5 AQL + 100% on A; F7 ABSENT
  underspecified → endpoint inventories + negative controls (§3 D0); F8 locator poisoning →
  self-confirming extraction (§3 D2); F9 omission blindness → completeness invariants (§3 D4);
  F10 fallback correlation → family-pairing swap rule (§2); F11 throughput realism → pilot A1
  measures first (§4); F12 storage durability → JSONL hash chain + versioned Tigris + git
  manifest (§3/§6).
- **Gemini 3.1 Pro costruttivo, 10 suggestions** — incorporated: IAA metrics, hidden gold-set,
  drift telemetry with control limits, AQL/CSP adaptive sampling, risk-stratified inspection,
  topological batching for cache, versioned dossier schema with lineage/confidence/refutation
  history, quarantine auto-triage, mutation testing. **Rejected with reason**: "cheaper frontier
  models as extractor seats" — the extractor stays Sonnet 5 (doctrine implementer tier; legal
  text quality; single-family provenance for the extraction plane), Haiku remains available for
  mechanical classification only.
- DeepSeek seat: not convened (BALANCE_DEAD at last probe) — 2-seat heterogeneous council,
  declared.
