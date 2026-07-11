---
date: 2026-07-08
domain: operations
client_case: none (production data quality — KBLI Navigator)
sources:
  - audit workflow wf_44b7fccb-d12 (58 agents: 47 judges + 11 adversarial verifiers, Sonnet 5)
  - apps/mouth/data/kbli-gold-all.json + KBLI_2025_FINAL_CLEAN.json (2 tracked copies)
  - live balizero.com/kbli/* + nuzantara-rag.fly.dev API probes (2026-07-08)
  - data/source_documents/tka_kbli_README.md (Kepmenaker 228/2019 extraction, Zero ruling 2026-07-01)
adversarial_review: gpt-5.5
---

# KBLI editorial-content audit — 11 mis-assigned codes + 128 cross-tagged tkaInfo

**Trigger**: Subhi's production re-audit (2026-07-08) flagged /kbli/56303 (Cafe) showing
discotheque content. Full audit of both editorial layers followed (GO Zero).

## Method

Two-lane LLM audit (47 judge agents over compact batches, official judul/uraian vs
editorial theme) + adversarial verify pass per flag (default-to-reject) + field-level
re-review by the orchestrator. Deterministic section-vs-category check for tkaInfo
(KBLI division → section map; `sektor_id` is the OSS lampiran id, NOT the section —
first detector version built on that phantom flagged 244; corrected one flags 128).

## Findings — 11/11 CONFIRMED content mis-assignments

| Code | Official activity | Editorial content was about | Wrong layer |
|---|---|---|---|
| 56303 | Rumah Minum/Kafe (cafe) | Discotheques/DJ venues | gold (all fields) + intel (3 fields) |
| 56304 | Kedai Minuman (drink stall) | Karaoke/KTV | gold (5) + intel (2) |
| 56305 | Rumah/Kedai Obat Bahan Alam (jamu house) | Generic coffee shops | gold (5) |
| 56306 | Minuman Keliling (mobile beverage vending) | Shisha/hookah lounges | gold (6) |
| 52292 | Tally Mandiri (port cargo tallying) | Warehousing/3PL | gold (5) |
| 66191 | Pendanaan Transaksi Efek (margin financing) | P2P lending fintech | gold (4) |
| 86102 | Puskesmas | Specialty hospital (RSK) | gold (2) |
| 86201 | Praktik Dokter (independent GP) | Klinik institutional licensing | gold (4) |
| 02102 | Pemanfaatan Kayu Hutan (timber) | Seed collection (= 02103's content) | intel (5) |
| 46492 | Sports equipment wholesale | Furniture wholesale | intel (baliContext+opener) |
| 46530 | Agri machinery wholesale | Construction machinery | intel (baliContext+opener) |

Verifier note: the adversarial pass EXPANDED wrong-field lists on 5 codes, and the
orchestrator's final re-grep caught 2 contaminated `zantaraOpener` fields (46492/46530)
that both judge and verifier had missed — W65 ("even the refuter hallucinates") again.

## Fixes applied (this PR)

1. **8 corrupted gold entries deleted** (52292, 56303, 56304, 56305, 56306, 66191,
   86102, 86201) — `transformCode` falls back to `intel_2026`, whose content for these
   codes is correct (verified field-by-field). Correctness > richness; gold can be
   re-authored later.
2. **intel_2026 rewrites** on 5 codes (56303, 56304, 02102, 46492, 46530), grounded in
   official uraian + `l4_bali` status. For Bali-BLOCKED codes the rewritten
   `baliContext` states the moratorium reality explicitly — this field is the
   "live truth" override used when gold misleads on blocked codes.
3. **128 tkaInfo blocks removed** from gold — categoryName provably inconsistent with
   the code's KBLI section (e.g. "Konstruksi" on legal 69101, film 59112, retail 47xxx;
   "Akomodasi" on travel-agency 79110). Includes Subhi's 70209 finding.
4. Both tracked dataset copies updated in lockstep (byte-identical to each other —
   `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` and
   `data/source_documents/KBLI_2025_FINAL_CLEAN.json`; the separate `kbli-gold-all.json`
   editorial layer is NOT byte-identical to either, by design) + dataset-version
   sidecar bumped (sha256 guard).

## Adversarial review (§, GPT-5.5 seat, sandboxed, fresh context)

Independent re-read of both dataset copies against every claim in this report.
**First-pass verdict: REFUTED.** 3 real findings, all applied before merge:

1. **HIGH — 02102 rewrite contradicted its own record.** The rewritten `intel_2026`
   text said "95% PMA cap", but the same record carries `pma_max_asing: 100` and a
   `pma_official_basis` citing Perpres 10/2021 open-default (explicitly: PBPH/AMDAL
   licensing is not an equity cap). Root cause: the 95% figure was copied from the
   record's own `l4_bali.reason` field, which was itself stale — pre-dating the
   PMA-cap resolution that produced `pma_max_asing`/`pma_official_basis`/
   `pma_cap_verified` (the same freshness trap W90 names: an in-record field can be
   older than its siblings). Fix: rewrote `whatYouNeed`/`baliContext`/`zantaraOpener`
   to 100% PMA + mandatory kemitraan, and corrected `l4_bali.reason` itself so the
   stale source can't mislead the next reader.
2. **MEDIUM — 56304 `youllAlsoNeed` still referenced "karaoke rooms"** after the gold
   entry was deleted (page falls back to raw `intel_2026`, which renders
   `youllAlsoNeed` same as gold). Fixed: replaced with "56301 — Bar activities (if you
   serve alcoholic drinks)".
3. **MEDIUM — 46492 `youllAlsoNeed` still suggested furniture manufacturing** (31029)
   under a sports-equipment-wholesale record, same fallback-rendering path. Fixed:
   replaced with "47620 — Sports equipment retail (if you also sell direct to
   consumers)".

Also flagged and addressed: "byte-identical dataset copies" wording was ambiguous
between the 2 clean-dataset copies (true) and gold-vs-clean (false) — tightened above.
The Qdrant re-ingest claim was overreach given ingestion was still pending — reworded
into an explicit follow-up (§Companion changes) rather than an accomplished fact.

**Second-pass re-check (this session, plain grep, not LLM):** 0 residual "PMA max 95%"
strings in either dataset copy; the 2 remaining "karaoke rooms" hits are on 93291
(Lantai Dansa) and 93292 (Pengelolaan Fasilitas Karaoke) — both LEGITIMATE, since 93292
*is* the actual karaoke-venue KBLI code, not contamination.

**Confirmed by the reviewer:** the mechanical cleanup (8 gold deletions, 128 tkaInfo
removals, sidecar bump) landed exactly as claimed — the defect was in 3 of the 5
narrative rewrites, not in the deletion/removal mechanics.

## §Meta-pattern (the malattia behind the 11)

The monumental overhaul (#2118) verified the REGULATORY layer (judul/uraian/PMA/risk
vs OSS ground truth) but never theme-checked the NARRATIVE layers (gold editorial,
intel_2026 prose, tkaInfo mapping) against the codes they're attached to. An
LLM-generated enrichment layer drifts to *plausible neighboring topics* (disco next to
nightclub codes, karaoke next to drink stalls, Klinik next to doctor codes) — content
that reads professionally and is wrong. **A derived narrative layer needs the same
verification gate as primary data**; "verified vs OSS" on the parent dataset said
nothing about the children. Same generative process produced the tkaInfo cross-tags.

## Residuals / follow-ups

- **intel_2026 of the remaining 420 gold codes** never audited in isolation (masked by
  gold precedence on the page, but embedded into Qdrant content) — follow-up lane.
- **167 `intel_2026.tkaInfo` blocks outside gold** (raw dataset, including fallback
  content for the 8 deleted-gold codes e.g. 56303/56304/86201) were NOT touched by the
  128-removal pass, which only scoped `kbli-gold-all.json` — same per-KBLI-TKA-concept
  question applies to these; folded into the business decision below, not a separate one.
- **8 orphan gold keys** (64921, 85300, 85491, 85499, 85600, 86903, 96120, 96130) not
  in the 1559 dataset — dead keys, left in place, no page renders them.
- **tkaInfo kept where name↔section is coherent** — but `categoryId`↔name was never
  verified against the Kepmen 228/2019 source list, and the per-KBLI TKA section AS A
  CONCEPT contradicts Zero's 2026-07-01 ruling (national positive-list, "no per-KBLI
  join — spreading it across 1559 codes would fake a specificity the law does not
  have"). Keep / redesign as honest national card / remove entirely = **business
  decision (Zero)**.

## Companion changes (separate backend PR)

`[CONTEXT: ...]` embedding header stripped from search/chat snippets · exact-code
fast-path in /search (live probe: "68111" did not return 68111) · chat abstain
threshold recalibrated 0.40 → 0.18 against the live prod score distribution (0.40 sat
above the entire legit band → chat abstained on every natural question, ~1.0s canned
fallback). Qdrant re-ingest of the corrected dataset follows the merge (pending arm of
#2118, prod payload verified stale by content hash).
