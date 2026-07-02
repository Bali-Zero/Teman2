---
date: 2026-07-03
domain: kbli
client_case: none (internal data-quality audit)
sources:
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (dataset SSOT, pma_cap_verified provenance flags)
  - NB-3 "Company Setup — Indonesia 2025" (933509f9), queries 9d8db1f675f1 / fa8dcce04979 / 8da4a7c91097
  - Perpres 10/2021 official lampiran resolution of 2026-06-27 (memory discovery_kbli_pma_status_not_from_oss_2026_06_27, commits d8f5835/1e683cd/2e8695b)
  - scripts/kbli_triangle/ledgers/ (2026-06-30 editorial pass + LEDGER-run2-2026-07-03.json)
---

# KBLI Registry Card Audit — RUN 2 (Triangle pattern)

**Mandate:** continue the registry-card audit — verify run-1 P1s on disk (content, not memory),
audit the next unaudited card fields, NB ground-truth every regulatory claim (confirm or ABSTAIN),
fix in small batches. GEAR 3, flight session M2, worktree `kbli-registry-audit-run2`.

**Outcome in one line:** 7/10 run-1 P1s were already cured on disk; run 2 found and fixed a
**10-code / 14-field editorial-drift class** (prose written before the 2026-06-27 official
Perpres-lampiran resolution still telling clients the pre-resolution numbers), discovered that
**NB-3's own KBLI+PMA catalogue source is stale** (it returned 3 pre-resolution verdicts), and
left 3 genuinely unresolved authority conflicts explicitly ABSTAINED for the operator.

---

## 1. Run-1 P1 status, verified on disk

| Code | Run-1 finding | On-disk verdict (2026-07-02) |
|---|---|---|
| 86101 | "100% foreign" on closed hospital code | **FIXED** — text now says CLOSED, routed to Swasta sibling |
| 86102, 86993, 68112 | ownership contradictions | **FIXED** — coherent with TERBUKA/100 |
| 84111, 84112 | TERTUTUP national, Bali layer absent | **FIXED** — bali_blocked=true |
| 59112 | internal contradiction | **FIXED** — #1911 moratorium prose (baliContext now empty, inventory note) |
| 90120 | opener sells "easiest code to activate" on Bali-blocked code | **STILL BROKEN → fixed this run** |
| 69102 | opener omits reserved-profession block | **STILL BROKEN → fixed this run** (was IN the 2026-06-30 redo ledger but never applied — built≠armed at field level) |
| 85102 | "49-51% bilateral cap + Yayasan mandatory" vs TERBUKA/100 | **STILL BROKEN → fixed this run** (cap claim removed per NB; Yayasan softened to practice note) |

Notable: 90120 was **not even in** the 2026-06-30 redo ledger — the earlier finder's patterns
missed the "enthusiastic opener on blocked code" phrasing. Run-2's Lane A2 pattern now catches it.

## 2. What run 2 audited (new surface)

- **Lane A (cross-field, deterministic, 1559 codes × 6 intel fields):** ownership-% claims vs
  `pma_max_asing`/`pma_status` (A1); blocked codes framed as doable without qualifier (A2);
  inverse false-block claims (A3); intra-card contradictions (A4).
- **Lane B (never-audited fields `whatItMeans`, `whatChanged`, `whoThisIsFor`):** invented KBLI
  mentions (B1), regulation-citation inventory (B2: only PP28/PP5 — clean), placeholder leakage
  and empty-field inventory (B3).
- Raw: 1825 findings → after innocence filtering: **18 real P1 candidates → 10 codes fixed,
  5 ABSTAINED** (see ledger for every verdict).

### Fixes shipped (14 field edits, 10 codes)

**Moratorium/structural-block qualifiers (A2 class):** 90120 (opener + baliContext), 69102
(opener, UU 18/2003 from l4 reason), 55209 (baliContext — no Usaha Besar row → UMKM-reserved,
PT PMA cannot register), 77210 (opener + baliContext).

**Prose realigned to the OFFICIAL pma layer (A1 class):** 50122/50123 ("100% permitted" → 49%
sea-cabotage cap, official), 47221 ("max 49%" → special distribution-network conditions, official
lampiran III), 47222 ("TERBATAS 49% + partner" → UMKM-reserved, closed to PT PMA, official V-list),
03110 ("30% barrier" → open per lampiran-absence, kemitraan nelayan lokal kept), 85102 (unsupported
"49-51% bilateral" removed; SPK-merger fact added, NB-confirmed).

All patches: PMA fingerprint sha256 asserted unchanged (`5d1d445e…`), old-segment guards, idempotent,
consumers synced (`sync_kbli_dataset.sh`), post-patch finder re-run: A2 P1 3→0, A1 P1 14→6 where
the 6 are exactly the declared ABSTAIN set. No new findings introduced.

### ABSTAINED (no invented facts — operator decides)

1. **73100 advertising (3 fields)** — genuine authority conflict: official 2021-lampiran read
   (absent → open 100, current data, `pma_cap_verified=true`) vs the generated matrix + NB claiming
   TERBATAS 49% per **Perpres 14/2024** (never checked as primary source). Highest-priority residual:
   it's the #1 digital-nomad money question.
2. **41011 construction** — NB contradictory (67% JV cap vs catalogue open); our l4 layer itself
   encodes 67%+IUJK; IUJK is abolished post-OSS. Needs the same judul-match-vs-lampiran method that
   cured sector 50.
3. **65111 insurance** — "80% cap, POJK 23/2023" unverifiable at NB-3 (no sectoral insurance sources).
4. **69101** — benign: the text explicitly acknowledges the data divergence (correct curation form).
5. **85571 whatChanged** — "from KBLI 78421 (2017)" is a vintage code with identical judul; plausible,
   mapping file too partial to arbitrate.

## 3. §Meta-pattern (the malattia-delle-malattie)

**Authority-inversion drift: the organism re-grounds one stratum against an official source and
nobody re-audits the strata that were derived from — or verify against — the old truth.**

Four independent observations, one defective belief ("fixing the data layer completes the fix"):

1. The pma layer was officially resolved against the Perpres 10/2021 lampiran on 2026-06-27
   (`pma_cap_verified=true`), but the **editorial prose** written weeks earlier kept serving the
   pre-resolution numbers (30%, 49%, 100%-where-49) — today's entire A1 class.
2. **NB-3, the Triangle's own ground-truth corner, still holds the pre-resolution catalogue**: it
   "confirmed" 30% for 03110 and "denied" the 49% cabotage cap for 50122/50123 — three stale verdicts
   in one run. A bipolar verifier is only as fresh as its sources; run-1's rule "Claude hallucinates
   regulations, NB confirms" silently became "NB remembers our old mistakes".
3. The **generated guide** (`kbli_foreign_ownership_matrix_2025.txt`, the COM-025 matrix) asserts a
   73100 reclassification per Perpres 14/2024 that was never reconciled with the lampiran read —
   derived artifacts carry forward claims their source layer has since outgrown.
4. The 2026-06-30 editorial pass itself: 69102's opener was **flagged in the redo ledger but the fix
   never landed** (built≠armed at the field level), and 90120 was missed by the finder patterns.

**Structural antidote (proposed):** every re-grounding of a truth layer must emit an invalidation
list of its derived surfaces (prose fields, NB source exports, generated guides) — and the Triangle's
NB corner needs a freshness contract: the NB catalogue source must carry the dataset's resolution
date and be rejected as ground truth when older than the layer it verifies.

## 4. §Solo-operatore

1. **Refresh NB-3's KBLI+PMA sources** (curated NB — not touched autonomously): replace the stale
   catalogue/matrix sources (incl. the doc answering as "PMA: TERBATAS max 30% WNA" for 03110) with
   a current dataset export + `lampiran_full.txt`. Until then, NB-3 verdicts on pma percentages are
   untrustworthy despite correct citations elsewhere.
2. **Perpres 14/2024 primary-source check** (deep-research candidate) to close 73100 — then fix
   prose+data coherently in one commit.
3. **41011 construction cap**: run the judul-match against the official lampiran (method that cured
   sector 50); modernize IUJK → SBU/PB-UMKU wording in the same pass.
4. **65111 insurance**: source the sectoral instrument (OJK/PP) before trusting the 80% claim.
5. **47222 `pma_nota`** says "Perdagangan eceran minuman beralkohol di bar" on the NON-alcoholic
   retail code — pma-family metadata, left untouched (frozen family); cosmetic fix in the next
   operator-gated pma batch.
6. Editorial-lane decisions: 21 "BPS_ONLY" jargon leaks in client-facing prose; baliContext empty on
   1138/1559 codes (by-design sparsity — decide target coverage).

## 5. Loop hygiene (what the audit process itself learned)

- **Lane A3 killed by innocence test:** 269/269 candidates were the legitimate #1911 moratorium
  template on non-blocked codes — the substring guard over-matched (superscar #3 avoided in-flight
  by adversarially sampling 8/8 before acting on the lane).
- **Near-miss W90 (scar filed):** NB's three stale verdicts almost drove text patches in the WRONG
  direction (e.g. rewriting 50122 to "100% open"). The save came from re-grounding against the
  on-disk provenance flags before patching. Verifier verdicts are leads, not verdicts — even the
  ground-truth corner.

## 6. Acceptance criteria (from the run-2 spec, all probed)

1. ✅ Findings ledger on disk (`LEDGER-run2-2026-07-03.json`) covering Lane A (1559×6) + Lane B (1559×3).
2. ✅ Run-1 P1 residuals fixed (90120, 69102, 85102) or ABSTAINED with NB evidence recorded.
3. ✅ PMA fingerprint sha256 unchanged before/after every patch.
4. ✅ Tracked dataset copies byte-identical (CI `check-kbli-dataset-sync` green expected).
5. ✅ This report exists with §Meta-pattern + §Solo-operatore.
