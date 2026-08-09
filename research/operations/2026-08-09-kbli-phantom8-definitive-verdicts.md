---
date: 2026-08-09
domain: operations
topic: kbli-phantom-8-definitive-verdicts
client_case: none — internal KBLI dataset data-quality follow-up, Mandate 9 of the 2026-08-09 gold-content full-population cycle, requested by Zero directly to move past bucket-level grouping to a per-code definitive proposal
discovered_by: kbli-docs-flip subagent, Mandate 9 (team-lead directive, on Zero's request)
sources:
  - "apps/kbli-navigator/lib/kbli-gold-content.ts — read-only, full whatItMeans/whatYouNeed/whatChanged/baliContext text for all 8 phantom codes AND for every candidate heir identified below that already carries a gold entry (85316, 85520, 85572, 85573, 85574, 85575, 85579, 85593, 85595, 85610, 86910, 86991, 86992, 86993, 86995, 96210, 96220, 96230); no edits made"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json — canonical 2025 dataset (1559 records); full official `uraian` (BPS description) read for every candidate code in the relevant families: 641xx (10 codes), 649xx (18 codes), 853xx (13 codes), 854xx (4 codes), 855xx (33 codes), 856xx (6 codes), 862xx (3 codes, cross-check for doctor-administered procedures), 869xx (6 codes), 961xx-969xx (7 codes)"
  - "research/operations/2026-08-09-kbli-phantom8-crosswalk.md (Mandate 8, same lane) — the prior, crosswalk-only bucket verdict this mandate supersedes with per-code, content-grounded evidence"
adversarial_review: codex
---

# KBLI phantom-8: definitive per-code verdicts (RE-KEY / CANCEL / IRRISOLVIBILE)

Mandate 9 (Zero's direct request, via team-lead): Mandate 8's bucket-level crosswalk analysis wasn't
enough to decide — this file goes per-code, matching each phantom's actual authored CONTENT (not just its
code number) against the official BPS description (`uraian`) of every candidate 2025 code in the relevant
family, and checking whether that candidate already has its own gold entry (if so, the phantom's content is
redundant and the proposal is to delete it, not re-key it).

**No edits were made to `kbli-gold-content.ts`.** These are proposed verdicts for Zero to ratify.

## Method

For each of the 8 phantom codes:

1. Read the full gold entry (`whatItMeans` + `whatYouNeed` + `whatChanged` + `baliContext`) to extract the
   actual topic and every named example/activity.
2. Read the full official BPS description (`uraian`, not just the title) of every 2025 code in the
   plausible family (the 3-digit prefix, sometimes wider) from the canonical dataset — the same file
   `index_kbli_gold_content.py::load_kbli_base_data()` reads at apply-time.
3. For every candidate whose `uraian` topically matches, check whether it already has its own entry in
   `kbli-gold-content.ts`. If yes → propose **CANCEL** (the phantom is a redundant duplicate; note names the
   entry/entries to merge into). If no → propose **RE-KEY**.
4. If no candidate's `uraian` matches after reading the family, or the phantom's content genuinely splits
   across candidates in a way a single proposal would misrepresent → propose **IRRISOLVIBILE** with the
   specific reason. Not forced in either direction just to produce a clean answer.

## Table

| Fantasma | Topic gold | Codici 2025 letti | Verdetto proposto | Evidenza (deskripsi citata) | Gold esistente sull'erede? |
|---|---|---|---|---|---|
| **64921** | Savings-and-loan cooperative (Koperasi Simpan Pinjam/KSP) — member deposits + member credit, TERTUTUP to foreign investment | Full 641xx (10 codes) + 649xx (18 codes) families | **RE-KEY → 64191** (conventional) / **64192** (sharia variant, same activity under sharia principles) | `64191` official BPS uraian: *"kegiatan penghimpunan simpanan dari anggota dan penyaluran pinjaman (kredit) kepada anggota... misalnya **koperasi simpan pinjam** primer, koperasi simpan pinjam sekunder, dan unit usaha simpan pinjam dari koperasi"* — names "koperasi simpan pinjam" verbatim, covers BOTH deposit-taking and lending, exactly the phantom's own topic. `64192` is the sharia-principle mirror of the same activity. | **No** — neither 64191 nor 64192 has a gold entry. Clean re-key, no duplicate. |
| **85300** | "Vocational secondary school (SMK)... also covers PMA international schools" — but named benchmarks (Green School Bali, Bali Island School, Indonesian School of Bali) are all GENERAL international-curriculum schools, not vocational | Full 853xx (13 codes, incl. 85311-85318 general/religious secondary, 85321-85324 vocational secondary) + 85330 | **IRRISOLVIBILE (as a single verdict) — content genuinely splits between a duplicate and a real gap; corrected after adversarial review** | Existing gold `85316`: *"Private senior high school — formal education for ages 16-18... final 3-year stage (SMA level)... run by a private entity"* absorbs the GENERAL-school half (the named benchmarks, the Kemendikbud/curriculum step-by-step). But the phantom's own title and lede explicitly claim SMK/vocational focus, and official `85322` ("Pendidikan Menengah Kejuruan Umum Swasta") directly names *"sekolah menengah kejuruan (SMK) swasta"* with tracks incl. *pariwisata, boga, perhotelan, kecantikan dan rambut*, plus *"sekolah menengah kejuruan hasil kerja sama dengan lembaga pendidikan asing"* — a real, currently-uncovered SMK/foreign-partnership code. A single CANCEL (my first draft) discards this half; a single RE-KEY would misrepresent the general-school half as vocational. Neither is honest on its own. | **Split**: 85316 (general half) is gold; **85322/85321 (the literal SMK half) are NOT gold** — a genuine, separate gap. |
| **85491** | Private vocational training centers (LPK) — cooking schools, hospitality training, barista certification, IT bootcamps, beauty academies, diving instructor certification, graphic design courses | Full 855xx job-training sub-family (85560, 85571-85589, 85591-85599) | **IRRISOLVIBILE (as a single verdict) — content splits between duplicated and genuinely uncovered activities; corrected after adversarial review** | Hospitality/IT/creative/business examples ARE duplicated: `85574` names **barista courses** and hotel-management training verbatim; `85572`/`85592` both independently claim **coding bootcamps**; `85573` covers **design**. But two of the phantom's own named activities have a BETTER, still-uncovered match the first draft missed: official `85597` ("Pendidikan Kerajinan dan Industri") explicitly lists *"tata boga/memasak"* (cooking courses) — a closer fit for "cooking schools" than the tourism-oriented 85574 — and official `85594` ("Pendidikan Kesehatan Swasta") explicitly lists *"tata kecantikan... spa... refleksi"* — covering "beauty academies" under a BPS bucket nobody would guess from its title (private HEALTH courses). Both verified independently against the live JSON, both have zero gold coverage. Cancelling the whole entry would discard those two activities' only real code. | **Split**: 85572/85573/85574/85575/85579/85592 (most named activities) are gold; **85597 (cooking) and 85594 (beauty/spa training) are NOT gold** — genuine, separate gaps this mandate's first draft missed. |
| **85499** | Other education — language schools, music schools, arts education, tutoring centers, cultural education (coding bootcamps, digital marketing courses, traditional Balinese arts) | Same 855xx family, plus 85520, 85592, 85593, 85595, 85610, 85575, 85599 | **CANCEL** — content duplicate across five already-gold entries; still holds after adversarial review, evidence broadened | Existing gold entries: `85593` *"Private language education — language courses in English, Indonesian, Mandarin, Japanese..."* (matches "language schools... Bahasa Indonesia for expats"); `85520` *"Cultural education... Dance studios, **music schools**, art workshops"* (matches "music schools... traditional Balinese arts"); `85595` *"Tutoring and academic counseling... bimbel, test preparation"* (matches "tutoring centers"). Adversarial review added two more: `85592` *"IT and computer education... coding bootcamps"* (matches "coding bootcamps" verbatim — independently confirmed in the live file) and `85575` *"...marketing and other business skills"* (matches "digital marketing courses", confirmed). Unlike 85300/85491, no named activity in 85499 was found pointing at a genuinely uncovered code — the residual heir `85599` is real but untouched by this prose. | **Yes** — 85592/85520/85593/85595/85575 (the content's actual targets) are all gold; **85599 itself (the numeric BPS heir) is NOT gold** — open, but would need fresh, narrower content, not this prose re-keyed as-is. |
| **85600** | Education support services — testing centers, educational consulting, curriculum development, edtech, tutoring management, scholarship placement, assessment services | Full 856xx family (85610 gold, 85691-85694, 85699) | **RE-KEY → 85699** | `85699` official BPS uraian, verbatim list: *"konsultasi pendidikan; konseling vokasional dan karier; konseling bimbingan pendidikan; **evaluasi dan pengujian pendidikan**; ... **pengembangan kurikulum**"* — "konsultasi pendidikan" = educational consulting, "evaluasi dan pengujian pendidikan" = testing/assessment (the IELTS/TOEFL-center concept), "pengembangan kurikulum" = curriculum development: a near word-for-word match to the phantom's own list. `85691`-`85694` were checked and ruled out — they certify one's OWN training graduates (LSP-style vocational competency), a different activity from third-party academic testing/consulting. Adversarial review confirmed no better 856xx candidate exists, but flagged that "educational software development" (edtech) isn't named in 85699's own text and may sit closer to a software-development code or `85610` (course/tutor intermediation) instead — a residual scope note for whoever writes the re-keyed content. | **No** — 85699 has no gold entry. Clean re-key, no duplicate. |
| **86903** | Health spa, therapeutic/medical basis — physiotherapy, IV drip, Ayurvedic medicine, hydrotherapy, ozone therapy, botox/fillers/PRP | Full 869xx family (86910, 86991-86995) + 861xx/862xx (86101-86105, 86201-86203, cross-check for clinic/doctor-administered procedures) | **CANCEL** — duplicate, content resolved across four already-gold clinical/wellness entries; supersedes Mandate 8's AMBIGUOUS verdict; evidence tightened after adversarial review flagged an over-read | Official `86991` uraian explicitly lists *"tenaga keterapian fisik"* and *"tenaga fisioterapi"* (physiotherapy personnel) among covered health workers — a genuine OFFICIAL-text match for "physiotherapy"; its own gold entry separately (editorially, not in the official uraian) names "IV drip clinics", which the phantom also uses — the two texts agree even though the official BPS wording doesn't use that phrase. Official `86992` covers traditional/alternative remedies (massage, herbs, cupping) but its OFFICIAL text does not say "Ayurveda" — the match there is with 86992's own gold-entry text, not the BPS description; kept as a partial, softer match. The phantom's own explicit line that botox/fillers/PRP/ozone REQUIRE "a licensed dokter with valid SIP" points to a private clinic or doctor's practice, not a paramedic service — official `86105` ("Aktivitas Klinik Swasta", already gold: *"Private clinics... outpatient care, consultations, and basic medical procedures"*) and `86202` (specialist doctor practice, covers dermatology) are the better-evidenced homes for that half, a candidate the first draft missed. | **Yes** — 86991 (primary, physiotherapy/IV-drip), 86105 (doctor-administered procedures, added after review), 86202 (specialist procedures), and 86992 (softer, traditional/alternative partial overlap) are all gold. |
| **96120** | Beauty salon — hair care, hairdressing, makeup, manicure, pedicure, nail art, lash extensions, brow shaping, waxing | Full 961xx-969xx sweep (96100, 96210, 96220, 96230, 96300, 96400, 96900) | **CANCEL** — duplicate, cleanly split and covered | Existing gold `96210`: *"Hair salon and barbershop — cutting, styling, coloring... hair care"*. `96220`: *"Beauty care and treatments... **Nail studios, manicures, pedicures, nail art**, facials, **lash extensions**, makeup services"* — reuses the phantom's own list almost word for word. | **Yes** — 96210 (hair) + 96220 (everything else named) are both gold and jointly exhaustive. |
| **96130** | Traditional body-care spa — Balinese massage, lulur, reflexology, aromatherapy massage, hot-stone, body wraps | Same 961xx-969xx sweep, plus 86995 (massage, cross-family) | **CANCEL** — duplicate, split across two already-gold entries | Existing gold `96230`: *"Day spas, saunas, steam baths... massage with herbal preparations, **aromatherapy**... This is the Bali spa experience in a code"* — "aromatherapy" verbatim, "herbal preparations" ≈ lulur. `86995`: *"Massage parlours... traditional massage houses, **reflexology** centers"* — "reflexology" verbatim. | **Yes** — 96230 (spa/aromatherapy) + 86995 (massage/reflexology) are both gold and jointly cover the phantom's list. |

## Summary (revised after adversarial review; see below)

The first draft proposed 2 RE-KEY / 6 CANCEL / 0 IRRISOLVIBILE. An independent adversarial pass (`codex`,
read-only, re-deriving every claim from the same source files) refuted 3 of the 8 rows — two of them
(85300, 85491) because it found genuinely uncovered candidate codes the first draft's family sweep missed,
which changes a forced single verdict into an honest split. The table above already reflects the
correction; the tally below is post-review:

- **2 clean RE-KEYs, no duplicate**: 64921→64191/64192 (KSP), 85600→85699 (education support). Both
  candidates have zero existing gold coverage and their official BPS `uraian` matches the phantom's own
  topic almost word for word. Unchanged by review.
- **2 CANCELs, content fully duplicated by existing, more specific gold entries**: 85499 (→85592/85520
  /85593/85595/85575), 96120 (→96210/96220), 96130 (→96230/86995). 86903 also stays CANCEL, but on
  tightened, corrected evidence (→86991/86105/86202/86992, not the original 86991/86992/86202 trio — see
  table). 3 of the 4 CANCELs above were CONFIRMED unchanged by adversarial review; 86903 was REFUTED on
  evidence rigor (an editorial gold-entry phrase was being cited as if it were the official BPS scope) but
  its bottom-line verdict survived once corrected, because every one of its named activities does map to an
  already-gold clinical code — there is no genuine gap here, unlike 85300/85491.
- **2 IRRISOLVIBILE (new, added after adversarial review)**: 85300 and 85491. Both were CANCEL in the first
  draft; the reviewer found real, currently-uncovered candidate codes inside each phantom's own content
  (85322 for the SMK half of 85300; 85597 for cooking and 85594 for beauty/spa training inside 85491) that
  the original family sweep had missed. Forcing either a single CANCEL or a single RE-KEY on these two would
  misrepresent one half of the content — the honest answer is a split, not a forced pick.
- **Net effect of the review**: the "6 CANCEL, 0 IRRISOLVIBILE" first draft undercounted the genuinely open
  gaps by not reading two family members (85597, 85594) closely enough on the first pass — a caution against
  reading "an example phrase reused in an existing gold entry" as proof the WHOLE family is already covered.

## Adversarial review

**Seat**: `codex` (`codex exec -m gpt-5.6-sol`, reasoning effort `high`, `--sandbox read-only`), run against
the first draft of this file, independently re-deriving every claim from the same source files (not shown
this file's prose) and instructed to try to REFUTE, not confirm.

| Code | Verdict | Note |
|---|---|---|
| 64921 | CONFIRMED — RE-KEY → 64191 | The phantom is explicitly a member-only savings-and-loan cooperative. 64191 names "koperasi simpan pinjam" and covers both deposits and credit. No better candidate across the complete 641xx/649xx sweep. Neither candidate has gold content. |
| 85300 | REFUTED | 85316 absorbs only the general/international-school half. The phantom explicitly says "SMK... vocational/technical focus." Official 85322 directly covers "SMK swasta" and has no gold entry. The phantom is internally split between 85316 and uncovered 85322; this requires split/IRRISOLVIBILE, not a duplicate-based CANCEL. |
| 85491 | REFUTED | 85572/85573/85574 absorb IT/design/hospitality examples, but not every named activity. Official 85597's uraian explicitly includes "tata boga/memasak" — the best match for "cooking schools" — and has no gold entry. 85594 explicitly covers "tata kecantikan... spa" and has no gold. "Every named activity already has a home" is false; cancellation would discard still-uncovered subject matter. |
| 85499 | CONFIRMED, WITH CORRECTED BASIS | 85593/85520/85595 absorb languages/culture/tutoring, but the cited triad is not exhaustive: 85592 ("coding bootcamps... digital skills") and 85575 ("marketing and other business skills") also apply. With those added, the content is collectively duplicated. 85599 remains uncovered but its residual scope is not what this prose principally describes. |
| 85600 | CONFIRMED — RE-KEY → 85699 | Official 85699 directly lists "konsultasi pendidikan," "evaluasi dan pengujian pendidikan," and "pengembangan kurikulum". No better candidate within the complete 856xx family, and 85699 has no gold. The re-key should trim or separately classify "educational software development" and tutor-platform activity, not stated in 85699. |
| 86903 | REFUTED | The claimed three-entry absorption is not fully supported by official descriptions alone: "IV drip" and "Ayurveda" appear in existing GOLD prose but not verbatim in the corresponding official uraian — an over-read of editorial text as regulatory scope. The scan also missed existing-gold 86105 (private clinics, outpatient care/basic medical procedures) and should weigh it for the doctor-administered-procedure half. A CANCEL may still be defensible on a corrected, wider evidence set, but the original three-code proof was not rigorous. |
| 96120 | CONFIRMED — CANCEL | Official 96210 covers hair services; 96220 explicitly covers nail art, manicure/pedicure, lash, brow, waxing, makeup. Existing gold reproduces the same division. Together they absorb the phantom's list without leaving an uncovered activity. |
| 96130 | CONFIRMED — CANCEL | Official 96230 covers holistic spa care, herbal-preparation massage, aromatherapy; official 86995 covers traditional massage and reflexology, both with matching existing gold. Together they absorb the phantom's Balinese-massage/lulur/aromatherapy/reflexology content. |

General objections (from the review, verbatim in substance):

- An existing editorial entry repeating an example is not proof its official BPS scope covers that example
  — materially over-read for 86903 ("IV drip"/"Ayurveda" are gold-prose phrases, not official-uraian text).
- The method promises IRRISOLVIBILE when content genuinely splits across codes, yet the first draft forced
  CANCEL for the internally contradictory 85300.
- Multi-code absorption supports cancellation only if every material topic has both canonical support and
  existing coverage — 85491 fails that test because 85597 is a direct, uncovered match for its cooking-school
  example.
- The stated family-breadth counts were independently reproduced and matched: 641xx=10, 649xx=18, 853xx=13,
  854xx=4, 855xx=33, 856xx=6, 862xx=3, 869xx=6, 961xx-969xx=7.

Result reported by the reviewer: 5 confirmed, 3 refuted (85300, 85491, 86903). All three refutations were
independently re-verified against the live files by this mandate before being incorporated (85597's and
85594's official `uraian` text, and 86105's existing gold entry, were re-read directly, not taken on the
reviewer's word alone) and are reflected in the table and summary above.
