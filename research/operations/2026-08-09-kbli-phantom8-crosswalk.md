---
date: 2026-08-09
domain: operations
topic: kbli-phantom-8-crosswalk
client_case: none — internal KBLI dataset data-quality follow-up from the gold-319 ledger row (`.claude/skills/modus/PENDING-ARMS.md`), Mandate 8 of the 2026-08-09 gold-content full-population cycle
discovered_by: kbli-docs-flip subagent, Mandate 8 (team-lead directive)
sources:
  - "data/kbli-filiera/phase0/bps_crosswalk.json — BPS's own official 2020↔2025 KBLI conversion table, parsed by scripts/kbli_filiera/bps_crosswalk_parser.py from bps/tabel-konversi-kbli-2020-2025-volume2-2026.pdf (Lampiran 5 forward + Lampiran 10 reverse, 2560 edges each, 1559 2025-codes-with-ancestry); `relation` dict read directly this session and inverted into a 2020→2025 reverse index"
  - "data/kbli-filiera/bps-crosswalk/edges-lampiran5.json and edges-lampiran10.json — the 2560 raw per-row crosswalk edges (both directions), each carrying uraian_2020/uraian_2025 (BPS's own bilingual titles) side by side; grepped this session by exact 2020 code for all 8 phantom codes"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json — canonical 2025 dataset (1559 records); bps_2020_ancestors, whatChanged, and kbli_2020_source fields read this session for every candidate heir found in the crosswalk"
  - "apps/kbli-navigator/lib/kbli-gold-content.ts — read-only, whatItMeans field for all 8 phantom codes (no edits made)"
  - "scripts/kbli_filiera/cure_whatchanged_false_renumber.py (docstring lines 41-50, authored 2026-07-25 by a prior lane) — independent corroboration naming this exact 8-code set as gold entries with no canonical 2025 record"
adversarial_review: codex
---

# KBLI phantom-8 crosswalk: which of the 8 gold-only codes have a 2025 heir

Read-only research prepared for an `operator[business]` decision (Zero): for each of the 8 KBLI codes
that exist in `kbli-gold-content.ts` (Bali Zero's editorial gold layer, 428 codes) but have **no** matching
record in the KBLI-2025 canonical dataset (1559 codes) — `64921 85300 85491 85499 85600 86903 96120 96130` —
determine whether it is a KBLI-2020 code with a KBLI-2025 heir, so the delete-vs-re-key choice is made on
evidence rather than on 8 bare code numbers.

**No edits were made to `kbli-gold-content.ts`.** This file records findings only; the decision belongs to
Zero.

## Method (in the order the mandate specified)

1. `data/kbli-filiera/phase0/bps_crosswalk.json` (`relation`, keyed by 2025 code, 1559 entries — BPS's own
   official Lampiran 5 forward + Lampiran 10 reverse 2020↔2025 conversion table) — checked by building a
   reverse index (2020 code → 2025 heir[s]) **and** by grepping the raw per-row edge tables
   (`edges-lampiran5.json` / `edges-lampiran10.json`, 2560 rows each, which carry both codes' BPS titles
   `uraian_2020`/`uraian_2025` side by side) for each phantom code, so a heir claim can be checked
   title-against-title and not just number-against-number.
2. The canonical 2025 record's `bps_2020_ancestors` field (populated by `populate_bps_ancestors.py` from
   the same crosswalk) plus its `whatChanged`/`kbli_2020_source` text, for every candidate heir found in
   step 1.
3. The phantom code's own gold-entry topic (`kbli-gold-content.ts::whatItMeans`) — cross-checked against
   the BPS title of the candidate heir, never used standalone to invent a heir.

Independent corroboration: `cure_whatchanged_false_renumber.py`'s own docstring (written 2026-07-25 by a
prior, unrelated lane) already names this exact 8-code set as "8 of the 428 gold codes... have no canonical
record" — the same set, reached from a different defect (false renumbering claims in `whatChanged`), which
confirms the phantom set is a known, previously-catalogued condition rather than a one-off finding of this
mandate.

## Table

| Codice fantasma | Titolo del contenuto gold | Erede 2025 candidato | Confidenza | Note |
|---|---|---|---|---|
| **64921** | Savings and loan cooperative (Koperasi Simpan Pinjam / KSP) | 64953 "Aktivitas Gadai Konvensional" (crosswalk-mechanical) | **LOW — likely mismatch** | Crosswalk is unambiguous 1:1 (64921→64953), and BPS's own 2020 title for 64921 is "**Pergadaian Konvensional**" = *conventional pawnshop*, not a savings/loan cooperative. The gold content's topic (member-owned savings/credit coop) does not match what BPS says code 64921 actually was in 2020, nor its 2025 heir. Re-keying to 64953 would file cooperative content under a pawnshop code — wrong regardless of the crosswalk. Topically-closer 2025 codes exist (`64191` "Aktivitas Pemberian Kredit oleh Koperasi Konvensional", `64192` sharia variant) but these are NOT crosswalk-linked to 64921 — this is an editorial observation, not a sourced heir. **Recommend: treat as a content/code mismatch to investigate separately, not a simple re-key.** |
| **85300** | Vocational secondary school (SMK) — incl. PMA international schools at secondary level | — | **UNKNOWN** | Not found in `relation`, not found in either raw edge table (`edges-lampiran5.json`/`edges-lampiran10.json`) by exact code in either direction. BPS's 2020→2025 crosswalk simply does not cover this code. Declared UNKNOWN rather than guessed from the title. |
| **85491** | Private vocational training centers (Lembaga Pelatihan Kerja / LPK) — e.g. cooking schools, hospitality training | 85591 "Pendidikan Manajemen dan Perbankan" (crosswalk-mechanical; **many-to-one merge**, not 1:1 — see adversarial review) | **LOW — likely mismatch** | Crosswalk gives 85491 exactly one heir, 85591, but 85591 is a MERGE of two 2020 ancestors (`bps_2020_ancestors.codes = ['85440', '85491']`) — corrected after adversarial review flagged the original draft's "single 1:1" framing as wrong. `kbli_2020_source=85491` still names 85491 as its primary source. BPS's own 2020 title for 85491 is "**Jasa Pendidikan Manajemen Dan Perbankan**" (management-&-banking education specifically) — much narrower than the gold entry's general LPK/cooking/hospitality-training topic. KBLI 2025 in fact split private vocational training (LPK-swasta) into a dedicated family (85571-85579, e.g. **85574** "Pelatihan Kerja Pariwisata dan Perhotelan Swasta" = private tourism/hospitality training) that fits the gold content's own examples far better than 85591 — but that family isn't what the crosswalk names for code 85491 specifically. **Recommend: treat as a content/code mismatch**, likely candidate family 855xx (LPK-swasta), not 85591. |
| **85499** | Other education — language/music/arts schools, tutoring, enrichment courses (distinct from vocational 85491) | **85599** "Pendidikan Lainnya Swasta" | **HIGH** | Crosswalk splits 85499 into two 2025 codes: 85530 "Kegiatan Sekolah Mengemudi" (driving schools — unrelated topic) and **85599 "Pendidikan Lainnya Swasta"**, which is the BPS 2020 title for 85499 verbatim, unchanged. The gold content's "other education, not vocational" topic matches 85599's preserved title exactly; 85530 is a crosswalk-split red herring, not the real heir. The only one of the 8 that survived adversarial review unchanged as a clean re-key. |
| **85600** | Education support services — testing centers, ed-consulting, curriculum dev, edtech, tutoring management, scholarships | — | **UNKNOWN** | Not found in `relation`, not found in either raw edge table by exact code in either direction. |
| **86903** | Health spa with therapeutic/medically-based treatments — physiotherapy, balneotherapy, Ayurvedic medicine, hydrotherapy | Two live candidates: 86910 "Aktivitas Jasa Intermediasi untuk Kesehatan Medis..." and 86993 "Aktivitas Pelayanan Penunjang Kesehatan" | **AMBIGUOUS — needs adjudication, not a confident re-key** | Originally classified HIGH for 86993 on the strength of its exact-title match plus 86910's own `whatChanged` text denying it ever existed in 2020. **Downgraded after adversarial review (see section below)**: (1) 86993's preserved title is BPS's old GENERIC "health support services" bucket — matching it exactly doesn't establish that it, rather than 86910, is where the gold entry's much NARROWER therapeutic/medical-spa topic actually landed; (2) 86910's `whatChanged` sentence is unverified editorial prose, and it directly CONTRADICTS the mechanical BPS crosswalk edge (which does list 86903 as 86910's ancestor) — prose contradicted by the official crosswalk cannot be used to rule the crosswalk edge out. Both candidates remain live; this one needs a human adjudication call, not a mechanical pick. |
| **96120** | Beauty salon — haircare, hairdressing, makeup, manicure/pedicure, nail art, lash/brow, waxing | — | **UNKNOWN** | Not found in `relation`, not found in either raw edge table by exact code in either direction. |
| **96130** | Traditional body-care spa / non-medical beauty treatments — Balinese massage, lulur, reflexology, aromatherapy, hot-stone, body wraps | — | **UNKNOWN** | Not found in `relation`, not found in either raw edge table by exact code in either direction. |

## Summary — 4 buckets (revised after adversarial review; see below)

The first draft of this file grouped the 8 into 3 buckets (2 HIGH re-key / 2 mismatch / 4 UNKNOWN). An
independent adversarial pass (`codex`, read-only, re-deriving every claim from the same source files rather
than trusting this file's prose) refuted the 86903 HIGH-confidence classification. The table above already
reflects the correction; the buckets below are the post-review count:

- **Bucket A — 1 clean HIGH-confidence re-key**: 85499→**85599**. Corroborated by an exact-title match in
  BPS's own bilingual table, and it is the only one of the 8 that survived adversarial review unchanged.
  Decision needed: GO/NO-GO on this one re-key.
- **Bucket A′ — 1 genuinely AMBIGUOUS split**: 86903, with two live candidates (86910, 86993) that this
  crosswalk extract cannot disambiguate — see table row and adversarial-review section for why the original
  HIGH call on 86993 did not hold up. Decision needed: which of the two candidates (if either) is correct,
  made as a human adjudication call, not inferred from this data alone.
- **Bucket B — 2 content/code mismatches**: 64921, 85491. The mechanical BPS crosswalk gives a heir for the
  CODE NUMBER, but that heir's topic doesn't match what the gold CONTENT actually describes
  (cooperative-savings content vs. a pawnshop code; general vocational-training content vs. a
  banking-education-specific code — and for 85491 the heir is itself a many-to-one merge, not a clean 1:1,
  per the adversarial review). Re-keying these two blindly onto the crosswalk's answer would silently misfile
  the content. Decision needed: what did the original gold-content author actually intend these two entries
  to describe — that intent, not the crosswalk, should drive the eventual code assignment.
- **Bucket C — 4 genuinely UNKNOWN**: 85300, 85600, 96120, 96130. BPS's official crosswalk (both lampiran,
  both directions, checked at the merged-index and raw-row level, confirmed independently by the adversarial
  review) has no record of these codes at all. No re-key candidate exists in this repo's data. Decision
  needed: delete, or investigate against the official BPS 2025 book directly (outside this crosswalk
  extract).

## Adversarial review

**Seat**: `codex` (`codex exec -m gpt-5.6-sol`, reasoning effort `high`, `--sandbox read-only`), run against
the first draft of this file, independently re-deriving every claim from the same source files (not shown
this file's prose — only the source paths and the 8 codes) and instructed to try to REFUTE, not confirm.

| Code | Verdict | Note |
|---|---|---|
| 64921 | CONFIRMED | `relation` and both raw tables contain exactly `64921→64953`. The titles are pawnshop-specific, contradicting the gold cooperative content; LOW-mismatch is justified. |
| 85300 | CONFIRMED | Zero occurrences as either 2020 or 2025 code in `relation`, Lampiran 5, or Lampiran 10. UNKNOWN is correct. |
| 85491 | REFUTED | `85491` has one heir, `85591`, but the mapping is not truly 1:1: `85591` also inherits from `85440`. The LOW content/title mismatch itself is confirmed. |
| 85499 | CONFIRMED | Both tables and `relation` give two heirs: `85530` and `85599`. Only `85599` preserves the exact title "Pendidikan Lainnya Swasta," supporting the selected HIGH-confidence content re-key. |
| 85600 | CONFIRMED | Zero occurrences in either direction at both normalized and raw-row levels. UNKNOWN is correct. |
| 86903 | REFUTED | Both official heirs exist: `86910` and `86993`. Although `86993` preserves the old generic title exactly, that title does not establish the gold entry's much narrower therapeutic/medical-spa topic. Moreover, canonical `whatChanged` cannot "rule out" `86910`: it is editorial prose directly contradicted by the official BPS edge. A clean HIGH-confidence re-key is not established. |
| 96120 | CONFIRMED | Zero occurrences in `relation` or either raw table, in either code field. UNKNOWN is correct. |
| 96130 | CONFIRMED | Zero occurrences in `relation` or either raw table, in either code field. UNKNOWN is correct. |

General objections (verbatim from the review):

- Bucket A does not survive intact: `85499→85599` is supported, but `86903→86993` should be treated as a
  content/code adjudication, not a clean HIGH-confidence re-key.
- Bucket B's mismatch conclusion survives, but `85491→85591` must be described as one-heir/many-to-one, not
  1:1.
- Bucket C survives unchanged: all four codes are genuinely absent from the normalized relation and both raw
  lampiran tables.

Both REFUTED findings were incorporated into the table and bucket summary above (86903 moved from Bucket A
to its own ambiguous Bucket A′; 85491's mapping corrected from "1:1" to "many-to-one merge").
