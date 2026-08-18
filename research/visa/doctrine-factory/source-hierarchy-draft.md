---
date: 2026-08-16
domain: visa
client_case: none
sources:
  - path: visa-oracle-master-prompt-2026-08-15.md
    lines: "94-121 (§4 Gerarchia delle fonti)"
    note: "repo root, untracked in main checkout — read from /Users/balizero/nuzantara/visa-oracle-master-prompt-2026-08-15.md"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "active pack seq-7 (SHADOW), key source_records[] — 30 records, verified on disk this session via python3/json"
  - path: .worktrees/ops-visaoracle-adjudication/visa-oracle-adjudication/execution-plan.md
    lines: "1-52 (Preambolo, §0 Gate owner registrati), 140-145 (QW-9)"
  - path: .worktrees/ops-visaoracle-adjudication/visa-oracle-adjudication/adjudication-report.md
    lines: "9 (authority_type distribution + freshness_policy seconds, independently cross-checked against source.json and found to match exactly)"
adversarial_review: kimi-k3
---

# Source hierarchy — draft for owner approval (QW-9)

**Status: DRAFT.** This document is the *input* to gate **G-E1** (execution-plan.md §0, "Gate owner
registrati": *"Source hierarchy (QW-9) + artifact home | E1"*). Writing it is unconstrained (QW-9 has
no dependency); **approving it is Zero's decision alone**, taken in phase E1 of the doctrine-factory
execution plan. Nothing in this document should be read as already ratified.

## 0. What this document is for

The master prompt (§4, "Gerarchia delle fonti") mandates an explicit source hierarchy of **7 authority
levels** that every legal claim extracted from NB-2 must be tagged with, so that a claim's *weight* in
conflict resolution is never ambiguous. The master prompt separately requires, in §5 "Fase D — Claim
ledger e contradiction resolution", a "regola che impedisce a una guida interna di superare una fonte
primaria vigente" — a rule that stops an internal guide from silently outranking a still-valid primary
source. This document treats the two requirements as one: the 7-level ranking in §1 *is* that rule, made
concrete and applied mechanically in §3.

The RulePack that will eventually consume these claims (`rulepack-prod-007`, currently in `SHADOW`) has
its own, narrower, machine-level vocabulary: `source_records[].authority_type`, with exactly **3 real
values** on the 30 records that exist today. This document (a) defines the 7 conceptual levels, (b) maps
them onto the 3 real pack values with an honest accounting of what the mapping *cannot* cover yet, (c)
states the binding precedence rule and its consequences for claim compilation (E2/E5 of the execution
plan), and (d) lists exactly what Zero is being asked to approve.

## 1. The 7 authority levels (master prompt §4, verbatim source, English gloss + Indonesian examples)

| # | Master prompt (IT, verbatim) | English gloss | Indonesian instrument examples |
|---|---|---|---|
| 1 | *legge e regolamenti indonesiani vigenti* | Indonesian law and regulations currently in force | **UU** (Undang-Undang, statute — e.g. UU 6/2011 tentang Keimigrasian jo. UU 63/2024); **PP** (Peraturan Pemerintah); **Perpres** (Peraturan Presiden) |
| 2 | *decreti, classificazioni e atti ministeriali ufficiali* | Official ministerial decrees, classifications and acts | **Permen** (Peraturan Menteri — e.g. Permenkumham 22/2023 jo. 11/2024 tentang Visa dan Izin Tinggal); **Kepmen** (Keputusan Menteri — e.g. Kepmen M.IP-08.GR.01.01/2025, visa catalog/classification) |
| 3 | *istruzioni operative ufficiali di Ditjen Imigrasi/eVisa* | Official operational instructions from Ditjen Imigrasi / eVisa | Published pages of `imigrasi.go.id` (e.g. `/wna/daftar-visa-indonesia/<code>`), eVisa portal instructions, official application-process pages |
| 4 | *comunicazioni ufficiali datate* | Dated official communications | **Surat Edaran** (SE, circulars), dated press releases or notices from Ditjen Imigrasi / Kemenimipas that are not themselves regulations but clarify how one is applied on a given date |
| 5 | *interpretazioni legali interne Bali Zero* | Bali Zero internal legal interpretations | Internal legal-team memos reasoning from levels 1-4 to a specific product/fact conclusion where the source itself is silent or ambiguous |
| 6 | *guide operative interne* | Internal operational guides | Bali Zero SOPs, internal checklists, "how we file this" documents — operational, not legal, authority |
| 7 | *fonti secondarie esterne* | External secondary sources | Law-firm blog posts, news articles, competitor explainers, non-official summaries |

Levels 1-4 are **external/official** (the state is the author). Levels 5-7 are **internal or
third-party** (Bali Zero or someone else is the author, reasoning *about* levels 1-4). This split is the
hinge the binding rule in §3 turns on.

## 2. Mapping onto the pack's real `authority_type` values

Verified directly against `rulepack-prod-007.source.json::source_records` this session (30 records,
`python3`/`json`, cross-checked against `adjudication-report.md:9` — both agree exactly):

| `authority_type` | Count | Freshness policy | Publishers observed |
|---|---|---|---|
| `PRIMARY_LAW` | 3 | `MAX_AGE_SINCE_VERIFIED_AT` 31 536 000 s (365 days) | Ditjen Imigrasi (2 records) + Badan Pemeriksa Keuangan RI/BPK (1 record) — all 3 are UU 6/2011 tentang Keimigrasian, one `jo. UU 63/2024`; BPK is the statute-publication authority, Ditjen Imigrasi republishes it in two derivative records |
| `IMPLEMENTING_REGULATION` | 7 | 31 536 000 s (365 days) | Ditjen Imigrasi (4 records), Kemenimipas (1), Kementerian Hukum dan HAM RI/Kemenkumham (2) — Kepmen M.IP-08.GR.01.01/2025, Permenkumham 22/2023 jo. 11/2024, Permen Imipas 10/2026, Permen Imipas 5/2025. Note: only ~4 distinct instruments across the 7 records — several instruments are recorded twice (once via Ditjen Imigrasi republication, once via the primary publisher, e.g. Permenkumham 22/2023 appears both standalone and folded into the `jo. 11/2024` record) — a dedup pass belongs in E2 (claim ledger), not in this hierarchy document |
| `OFFICIAL_PORTAL` | 20 | `MAX_AGE_SINCE_VERIFIED_AT` 604 800 s (7 days) | Ditjen Imigrasi (`imigrasi.go.id` daftar-visa pages) |

### 7 → 3 mapping table

| Master-prompt level | Pack `authority_type` | Rationale |
|---|---|---|
| L1 — law/regulations in force | `PRIMARY_LAW` | Direct match: both mean statute-level, state-authored, highest weight. |
| L2 — ministerial decrees/classifications | `IMPLEMENTING_REGULATION` | Direct match: Permen/Kepmen implement a statute; the pack's freshness policy (365d) treats them the same as `PRIMARY_LAW`, which is *consistent with* (not proof of) the intended L1-adjacent weight — freshness policy alone does not establish precedence, only §3 does that explicitly. |
| L3 — official Ditjen Imigrasi/eVisa operational instructions | `OFFICIAL_PORTAL` | Direct match: the 20 `imigrasi.go.id` pages *are* the official operational instructions. The pack's own freshness policy (7d, vs 365d for L1/L2) already encodes that L3 is operationally weaker/more volatile than L1/L2 — a portal page can change without a regulation changing. |
| L4 — dated official communications (SE, circulars) | **no dedicated value — gap** | No `source_record` in the active pack is a Surat Edaran or dated notice distinct from a portal page. Today an SE would have to be filed under `OFFICIAL_PORTAL` (if published on the portal) or `IMPLEMENTING_REGULATION` (if it amends a Permen), which loses the "dated, narrower-scope, supersedable" semantics the master prompt wants for L4. **Recommendation, not yet implemented**: if/when an SE-type source is added, either introduce a 4th `authority_type` (`OFFICIAL_CIRCULAR`) or, at minimum, tag it distinctly in `document_number`/`legal_period` so the claim ledger can apply L4 precedence rather than L2/L3 precedence. |
| L5 — Bali Zero internal legal interpretations | **not represented — by design** | Zero `source_records` today are internally authored; all 30 are official/state-authored. This is consistent with the master prompt's own instruction (§3) that NB-2 is *query-only* and its answers must be *compiled* into the ledger via the claim pipeline, not injected as sources. If a Bali Zero interpretation ever needs to be cited as a claim's origin, it must be visibly weaker than L1-L4 in the ledger (see §3) — the pack has no mechanism for this today because it has never needed one. |
| L6 — internal operational guides | **not represented — by design** | Same status as L5: no `authority_type` exists for it, and none should be manufactured until a real claim needs it. |
| L7 — external secondary sources | **not represented — by design** | Same status. The pack has zero tolerance today for secondary sources becoming `source_records`; this document does not propose changing that. |

**Honest summary**: the pack's 3 real values cover only L1-L3 of the master prompt's 7-level hierarchy.
L4 is a genuine gap (an SE would be mis-filed today). L5-L7 are correctly *absent*, not missing — the
architecture (NB-2 query-only → claim ledger → compiler) is designed to keep purely internal/secondary
material out of `source_records` entirely; when it needs to be *referenced* (e.g. a Bali Zero
interpretation bridging a gap in L1-L4), it must live in the claim's provenance/rationale field, tagged
at its true (low) authority level, never masquerading as one of the three pack `authority_type` values.

## 3. Binding rule and its operational consequences

> **An internal guide never overrides an in-force primary source.**

This is not a tie-breaker to invoke occasionally — it is meant as a structural constraint on the claim
compiler itself (execution-plan.md §2 E5: *"il compiler consuma SOLO claim `VERIFIED`"*, with a lint
that fails the build on `CONFLICTING`/`STALE`/`UNVERIFIED` input).

### 3.1 Conflict resolution order

When two legal claims that bear on the same fact/product disagree:

1. Rank both claims by authority level (L1 highest … L7 lowest per §1).
2. If the claims are at **different** levels: the higher-level claim wins **provided it is still in
   force** (`legal_period.to` is null or in the future, and it has not been `SUPERSEDED` by a later
   claim at the same or higher level). The lower-level claim is marked `SUPERSEDED` (not
   `CONFLICTING`) — it never blocks compilation, it simply loses precedence. This is the direct
   mechanical form of the binding rule: an L5/L6 claim can never beat an L1/L2 claim that is still valid.
3. If the claims are at the **same** level and disagree (e.g. two `OFFICIAL_PORTAL` pages contradicting
   each other, or a Permen amendment not yet reconciled with the amended Permen): both are marked
   `CONFLICTING`. A same-level conflict is **not** resolved automatically by this hierarchy — it requires
   the independent red-team review the master prompt mandates in **§5 "Fase D — Claim ledger e
   contradiction resolution"** ("independent red-team review", "procedura di escalation quando una norma
   è ambigua"). No `CONFLICTING` claim may produce `SUPPORTED_CANDIDATES` (master prompt §5 Fase D, line
   232: *"Nessun claim `CONFLICTING`, `STALE` o `UNVERIFIED` può produrre automaticamente
   `SUPPORTED_CANDIDATES`."*).
4. If a claim's source has failed its freshness recheck (§2 freshness policies: 365d for L1/L2, 7d for
   L3; L4-L7 policy TBD if/when populated), it is marked `STALE` regardless of its authority level, and
   is excluded from compilation exactly like `CONFLICTING` until re-verified. A `STALE` L1 claim does
   **not** get to keep out-voting a fresh L3 claim while stale — staleness suspends authority, it does
   not preserve it.
5. A claim with no resolvable source pointer (per QW-1's citation-audit contract: every pointer
   extracted from NB-2 prose must resolve against the frozen 131-source snapshot) is `UNVERIFIED` and is
   excluded from compilation, independent of the level it claims to be.

### 3.2 Claim states (master prompt §4, reused verbatim by the execution plan's E2/E5 ledger)

`VERIFIED` · `CONFLICTING` · `STALE` · `UNVERIFIED` · `SUPERSEDED` — five states, one vocabulary, used
identically whether the conflict originates from cross-level disagreement (§3.1.2, resolves to
`SUPERSEDED` for the loser) or same-level disagreement (§3.1.3, both sides `CONFLICTING` until resolved).
This document does not introduce new states; it only fixes *which* rule assigns `SUPERSEDED` vs
`CONFLICTING` when a hierarchy comparison is involved, since the master prompt names the states but does
not spell out which cross-level outcome maps to which state — that gap is what this document closes.

### 3.3 Consequence for claim compilation (E5)

- The compiler's `VERIFIED`-only lint (execution-plan.md E5, item (a)) is unaffected by this document —
  it already refuses `CONFLICTING`/`STALE`/`UNVERIFIED` input. This document adds the missing piece: how
  a claim *reaches* `VERIFIED` vs `SUPERSEDED` when two sources at different authority levels disagree.
- No rule/fact/branch may be compiled from a claim whose provenance is L5/L6/L7 *if* a still-valid L1-L4
  claim exists on the same proposition — the L5-L7 claim is `SUPERSEDED` per §3.1.2 and is excluded.
- An L5/L6/L7 claim **may** be compiled when it fills a genuine gap (no L1-L4 claim exists on that
  proposition) — but it must carry its true low authority level visibly in the claim record, so a
  reader (or a future L1-L4 source) can immediately identify and supersede it later. This is what lets
  the doctrine factory "trasformare dati mancanti in domande utili" (master prompt §1) instead of either
  inventing law or refusing to answer.

## 4. DECISION REQUESTED (gate G-E1)

Per execution-plan.md §0 ("Gate owner registrati", row `G-E1`) and §2 (phase `E1 — Ratifica`), Zero is
asked to approve, as one package:

1. **The source hierarchy itself** — the 7 levels in §1, the 7→3 mapping in §2 (including the
   acknowledged L4 gap and the deliberate L5-L7 absence), and the binding-rule mechanics in §3
   (specifically: cross-level disagreement → `SUPERSEDED` for the loser; same-level disagreement →
   both `CONFLICTING`, human-escalated).
2. **The artifact home**: `research/visa/doctrine-factory/` is the home for the *claim ledger* and all
   working artifacts of the doctrine factory (query logs, source snapshots, conflict reports, freshness
   rechecks — consistent with what already lives there: `nb2-answers/`, `sources/`, `tools/`). The
   `contracts/` tree (`apps/backend-rag/backend/services/visa_engine/contracts/`) is reserved
   **exclusively** for *compiled, versioned, machine-read* artifacts (RulePacks and their
   `source_records`) — never for the ledger's working state. This split matches execution-plan.md's own
   Preambolo ("Read-only sui pack firmati") and keeps the ledger auditable/ad-hoc per CLAUDE.md §15
   without ever being mistaken for a curated, signed artifact.
3. Explicitly **not** requested here: approval of any individual legal claim, the fact schema (CP2, gate
   at E4), or the seq-9 semantic diff (CP3, gate at E5). Those are separate, later gates that consume
   this hierarchy once it is approved — this document only fixes the ranking rule they will be judged
   against.

If Zero approves with changes, the changes should land as an edit to this same file (redeployed/re-committed
under the same path) rather than a parallel document, so `research/visa/doctrine-factory/` keeps one
canonical hierarchy record.

## Adversarial review

Cross-family review run via `kimi -p "REFUTA questo documento" -m kimi-code/k3` (generator≠grader — the
reviewer independently re-derived the pack counts/freshness policies via its own `python3`/`json` read
of `rulepack-prod-007.source.json` before judging, rather than trusting this document's numbers).

**5 findings raised, dispositioned as follows** (re-verified against `rulepack-prod-007.source.json` and
the master prompt this session, independent of the reviewer's own re-derivation):

1. **[P1, CONFIRMED, cured]** §3.1.3 and §0 misattributed the red-team/escalation requirement and the
   "internal guide never overrides primary law" rule to master-prompt §4; both actually live in §5
   "Fase D — Claim ledger e contradiction resolution" (lines ~217-232). §4 (lines 94-121) defines the
   7 levels and the claim schema/states, not the contradiction-resolution procedure. Fixed: citations
   now correctly point to §5 Fase D; §0 now attributes each requirement to its real section.
2. **[P1, CONFIRMED, cured]** §2 "Publishers observed" was wrong for both rows. `PRIMARY_LAW`'s 3
   records are published by Ditjen Imigrasi (2) and BPK (1) — Kementerian Hukum dan HAM RI does not
   appear among them. `IMPLEMENTING_REGULATION`'s 7 records are published by Ditjen Imigrasi (4),
   Kemenimipas (1) and Kementerian Hukum dan HAM RI (2) — BPK does not appear among them. Re-verified
   directly against `source_records[].publisher` this session; table corrected.
3. **[P1, REFUTED — reviewer error]** Claimed `research/visa/doctrine-factory/` does not exist and that
   `nb2-answers/`/`sources/`/`tools/` live elsewhere (`visa-oracle-blueprint/nb2-answers`). Re-verified
   twice in this worktree with `ls`/`find`: `research/visa/doctrine-factory/{nb2-answers,sources,tools}/`
   exist with exactly the files described in §4.2, populated 2026-08-15/16 by prior QW-1 work. The
   reviewer's check evidently ran against a different working directory (its own session context or the
   unrelated `visa-oracle-blueprint/` tree, which is a distinct artifact from an earlier blueprint round —
   not this worktree). No change made; disposition recorded here per generator≠grader discipline (the
   reviewer's claim is checked independently, not accepted on authority).
4. **[P2, CONFIRMED, cured]** The pack's 7 `IMPLEMENTING_REGULATION` records cover only ~4 distinct
   instruments (some recorded once via the primary publisher and again via Ditjen Imigrasi
   republication — e.g. Permenkumham 22/2023 appears both standalone and folded into the `jo. 11/2024`
   record). Not previously flagged. Added a note in §2's mapping table; scoped as an E2 (claim ledger)
   dedup concern, not a change to this hierarchy's ranking rule.
5. **[P2, CONFIRMED, cured]** §2's L2 rationale overstated what equal freshness policy proves ("confirming
   the intended weight" — freshness parity is consistent with, not proof of, precedence). Reworded to
   state the weaker, accurate claim.

Net: 4/5 raised findings were real defects and are cured above; 1/5 was a reviewer-side false negative,
independently re-verified and rejected with evidence rather than taken on trust.
