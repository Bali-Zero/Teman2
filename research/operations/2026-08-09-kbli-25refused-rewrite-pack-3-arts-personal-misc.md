---
date: 2026-08-09
domain: operations
topic: kbli-25refused-rewrite-pack-part3
client_case: none — internal `kbli_documents` data-quality follow-up, Mandate 10, part 3 of 3 (arts/personal-services/spa/misc — final 6 codes, plus the full 25-code summary and adversarial review), requested by Zero via team-lead
discovered_by: kbli-docs-flip subagent, Mandate 10 (team-lead directive, on Zero's request)
sources:
  - "Postgres `kbli_documents` (prod, via `mcp__postgres-nuzantara__query`, read-only role) — live `content`/`judul` for the 6 codes in this file, queried this session"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json — canonical 2025 dataset; full `per_skala` array (incl. `scope_uraian`) and top-level `pma_*` fields for all 6 codes"
  - "Part 1 (2026-08-09-kbli-25refused-rewrite-pack-1-agri-finance-tech.md) and Part 2 (...-2-education.md), same lane, same session — this file's summary table covers all 25 codes across all three parts"
adversarial_review: codex
---

# KBLI 25-refused rewrite pack — part 3 of 3 (arts / personal services / spa / misc) + full summary

See Part 1 for the shared method, the re-measured population (still 25, unchanged since 2026-08-02), and
the side-finding that all 25 rows' stored `content` has zero real newline characters. **Proposals only —
nothing in this file was applied to `kbli_documents`.**

---

## 90200 — Aktivitas Seni Pertunjukan

**Prosa attuale (verbatim):**
> KBLI 90200: AKTIVITAS SENI PERTUNJUKANnnWHAT IT MEANS:nPerforming arts...nnBALI CONTEXT:n...Legong,
> Barong, Kecak, and Wayang puppet theater are UNESCO-recognized cultural treasures...traditional Balinese
> performing arts are deeply tied to Hindu religious ceremonies — commercial use of sacred performances
> requires cultural sensitivity and community consent.

**Canonical licensing (12 raw rows):** ALL scales → **Rendah** (low) risk, Otomatis. Official `uraian`
explicitly lists, among other things, *"pengoperasian fasilitas seni yang digunakan untuk kelompok seninya
sendiri"* — operating an arts facility used by one's OWN performing group. `pma_status = TERBUKA`.

**Verdetto: SILENTE on licensing**, but the stored prose's categorical claim needs softening — confirmed
after adversarial review. Both the live `content` and this pack's first-draft rewrite say "this covers the
act of performing, **not** the venue (90310)" as an absolute. Canonical's own `uraian` contradicts the
absolute version: operating a performance facility for one's OWN troupe/group's use is explicitly INSIDE
90200, not 90310. Only operating a venue for THIRD PARTIES (other performers, the general public) is
exclusively 90310's territory. The distinction is who the venue serves, not "performing vs. venue" as a
clean binary.

**Bozza (corrected):**
> **What it means**: Live performing-arts activities — dance, theater, music concerts, opera, puppetry,
> circus, and other staged performances, including a group operating its OWN rehearsal/performance facility
> for its own use. Also explicitly covers actors, dancers, singers/musicians, background singers,
> conductors, models, and — per the official scope — influencers, content creators, and YouTubers appearing
> in video/vlog content, and independent musicians/actors appearing across audiovisual content. Operating a
> venue FOR OTHER performers or the general public (rather than one's own group) is the separate code
> 90310.
>
> **Licensing**: All scales — Rendah (low) risk, NIB issued automatically.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali's performing-arts tradition (Legong, Barong, Kecak, Wayang puppet theater) is
> UNESCO-recognized. The clearest opportunity for foreign artists is contemporary fusion — combining
> Balinese dance with modern choreography or staging international festivals. Traditional Balinese
> performing arts are deeply tied to Hindu ceremony; commercial use of sacred performances requires cultural
> sensitivity and community consent, not just a license.

---

## 90310 — Aktivitas Operasional Tempat dan Fasilitas Kesenian

**Prosa attuale (verbatim):**
> KBLI 90310: AKTIVITAS OPERASIONAL TEMPAT DAN FASILITAS KESENIANnnWHAT IT MEANS:nArts venues and
> facilities — physical spaces dedicated to displaying or hosting artistic and cultural activities. Art
> galleries, performance halls, exhibition spaces, cultural centers, artist studios open to the public, and
> creative coworking spaces focused on arts. You provide the space; artists and performers use it.nnBALI
> CONTEXT:nBali's gallery scene is concentrated in Ubud (ARMA Museum, Neka Art Museum, Agung Rai Fine Art
> Gallery) but expanding into Canggu, Seminyak, and even Tabanan...Combine with 90391 for event programming
> and 85573 for training programs...

**Canonical `uraian` (official BPS text, read in full — the first draft of this card did not quote it, and
as a result reproduced the stored prose's scope error instead of catching it):** covers operating auditoriums
for concerts/theater, cultural centers/**Taman Budaya** (cultural parks), facilities supporting the creation
of visual-art works, and live-music venues/music clubs where performers perform. It then explicitly states
what this code does **NOT** cover: *"perdagangan eceran lukisan dan patung (aktivitas komersial galeri
kesenian), lihat 4769"* (commercial art-gallery retail — separate code 4769), *"pengoperasian berbagai jenis
museum, lihat 9020"* (museum operation — separate code 90200's family), plus cinemas (5914) and ticket sales
(7990). Canonical's per_skala scope for all 4 rows is literally **"Taman Budaya"**.

**Canonical licensing (4 raw rows):** ALL scales → **Rendah**, Otomatis. `pma_status = TERBUKA`.

**Verdetto revised after adversarial review — this is CONTRADICE, not SILENTE, and the defect is in the
LIVE stored prose itself, not just this pack's rewrite.** The stored `content` names ARMA Museum, Neka Art
Museum, and Agung Rai Fine Art Gallery as examples of what 90310 covers — but the official `uraian`
EXPLICITLY EXCLUDES both commercial art galleries (→ 4769) and museums (→ 90200's family) from this code.
Every named example in the live prose is something the code's own scope says does NOT belong here. This
pack's first-draft rewrite reproduced the same error uncritically (kept "galleries" and the same three named
venues) instead of catching it — caught only on independent re-reading of the official `uraian` during
adversarial review.

**Bozza (corrected):**
> **What it means**: Arts venues and facilities — auditoriums and halls for concerts/theater, cultural
> centers and Taman Budaya (cultural parks), facilities supporting visual-art creation, and live-music
> venues/music clubs where performers appear. You operate the venue; performers/artists use it. This
> code explicitly EXCLUDES commercial art-gallery retail (selling paintings/sculptures — that's code 4769)
> and museum operation (that's part of 90200's family) — despite what the current live content says, ARMA
> Museum, Neka Art Museum, and Agung Rai Fine Art Gallery are NOT examples of this code.
>
> **Licensing**: All scales — Rendah (low) risk, NIB issued automatically.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali's Taman Budaya (Denpasar) and various concert/theater auditoriums are the clearest
> fit for this code. A hybrid live-music-venue-plus-café model (Ubud, Canggu, Seminyak) also fits, so long as
> the primary activity is hosting performances rather than selling art or operating a museum. Consider
> pairing with 90391 (event organization) and 85573 (creative-industry training) for a fuller business
> model — but route any actual gallery/museum concept to 4769 or the museum code instead of this one.

---

## 91122 — Aktivitas Kearsipan Swasta

**Prosa attuale (verbatim):**
> KBLI 91122: AKTIVITAS KEARSIPAN SWASTAnnWHAT IT MEANS:nPrivate archiving services...nnBALI CONTEXT:n

**Canonical licensing (8 raw rows):** ALL scales → **Rendah**, Otomatis. `pma_status = TERBUKA`.

**Verdetto: SILENTE**, plus the same empty-BaliContext defect seen on 03232/03233 — the section label is
present with zero content after it.

**Bozza:**
> **What it means**: Private archiving services — building, storing, classifying, and providing access to
> physical or digital archive collections, run by individuals, companies, foundations, or other private
> entities.
>
> **Licensing**: All scales — Rendah (low) risk, NIB issued automatically.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: [no source material in the current row — genuine gap, not filled with invented copy.]

---

## 96230 — Aktivitas Sante Par Aqua (SPA) Harian, Sauna, dan Pemandian Uap

**Prosa attuale (verbatim):**
> KBLI 96230: AKTIVITAS SANTE PAR AQUA (SPA) HARIAN, SAUNA, DANnnWHAT IT MEANS:nDay spas, saunas, and steam
> baths...nnBALI CONTEXT:n...The 2025 code 96230 finally gives spas their own classification. **Since it's
> BPS_ONLY (no PP28 licensing data yet), the detailed requirements are pending.** However, existing spa
> operations typically need: TDUP, health/hygiene certification, trained therapists...

**Canonical licensing (4 raw rows) — corrected after adversarial review, independently re-pulled with full
`skala_usaha`/`scope_uraian` fields (the first draft's Besar-vs-rest framing conflated SCALE with a
different, SUBJECT-MATTER split):** the real split is **Medical Spa vs. non-Medical Spa**, not "large vs.
small". Besar-scale, `scope_uraian = "Usaha Spa yang sudah mengarah kepada Medical Spa"` → **Tinggi**
(high) risk, 14 hari, authority listed as `["Menteri/Kepala Badan", "Menteri/Kepala Badan"]` — the SAME
value listed twice (a data artifact, not two distinct ministries — do not read this as "two sign-offs").
Mikro/Kecil/Menengah, `scope_uraian = "Seluruh, kecuali usaha SPA yang mengarah kepada Medical SPA"` (i.e.
non-medical) → **Menengah Tinggi**, 14 hari, authority Gubernur + Menteri/Kepala Badan (listed in
inconsistent order across the three rows — again likely a data-entry artifact, not a meaningful difference).
Canonical has **no populated row** for a Besar-scale non-medical spa, nor for a Mikro/Kecil/Menengah medical
spa — a real gap in the source, not something this pack invents an answer for. `pma_status = TERBUKA`.

**Verdetto: CONTRADICE — third instance of the same near-miss pattern found in 85573/85574.** *"BPS_ONLY (no
PP28 licensing data yet)... requirements are pending"* is false: canonical carries a complete risk tier, a
14-day timeline, and named authorities for every scale. Same phrasing family as the two education-code
hits, again not literally matching `CONTRADICTED_LICENSING_CLAIM_RE`'s phrase list. Three independent
occurrences of the same evasion, across three unrelated activity domains (creative-industry training,
hospitality training, day spas) — this reads as a systemic pattern in how this content batch was authored
(everything using "BPS_ONLY"/"pending" language was written before PP28 per-skala data existed for these
codes, and never revisited once it landed), not three coincidental one-offs.

**Bozza (corrected):**
> **What it means**: Day spas, saunas, and steam baths — holistic body care combining traditional and modern
> methods: water-based treatments, herbal-preparation massage, aromatherapy, and related wellness services.
>
> **Licensing**: The split in canonical is by whether the operation qualifies as a "Medical Spa", not by
> business scale alone. Non-medical spa, Micro/Small/Medium scale — Menengah Tinggi risk, NIB + Sertifikat
> Standar within 14 working days, provincial (Gubernur) + central authority. Medical-leaning spa, Large
> scale — Tinggi (high) risk, 14 working days, central-ministry authority. Canonical has no populated entry
> for a large-scale non-medical spa or a small/medium-scale medical spa — confirm directly with OSS if your
> case falls in that gap.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali is globally synonymous with spas, from high-end resort spas in Nusa Dua to
> budget massage venues in Kuta. In addition to the NIB/Sertifikat Standar above, operators typically also
> need: Tanda Daftar Usaha Pariwisata (TDUP), health/hygiene certification, therapist competency
> certificates, and SNI spa-standard compliance. A spa marketing itself with medical-adjacent treatments
> (e.g. aesthetic/dermatology-linked services) should confirm whether it is classified as "Medical Spa" for
> licensing purposes before assuming the lighter non-medical tier applies.

---

## 96300 — Aktivitas Pemakaman dan Kegiatan Terkait

**Prosa attuale (verbatim):**
> KBLI 96300: AKTIVITAS PEMAKAMAN DAN KEGIATAN TERKAITnnWHAT IT MEANS:nFuneral and related
> services...nnBALI CONTEXT:n...the Ngaben (cremation) ceremony is one of the most important cultural
> practices. Commercial funeral services for the local Balinese population are virtually non-existent as a
> PMA opportunity...

**Canonical licensing (4 raw rows):** ALL scales → **Rendah**, Otomatis. `pma_status = TERBUKA`.

**Verdetto: SILENTE.** The cultural/market-realism framing is valuable and non-regulatory — preserve as-is.

**Bozza:**
> **What it means**: Funeral and related services — funerals, cremation, burial preparation, cemetery
> management, and memorial services.
>
> **Licensing**: All scales — Rendah (low) risk, NIB issued automatically.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Funeral practice in Bali is deeply tied to Hindu tradition — the Ngaben cremation
> ceremony is central to local culture, and commercial PMA funeral services for the Balinese population are
> effectively not a realistic market (managed through Banjar and family structures instead). The realistic
> PMA angle is serving the international community: expat memorial services, repatriation logistics, and
> pet cremation.

---

## 96400 — Aktivitas Jasa Intermediasi untuk Jasa Perorangan

**Prosa attuale (verbatim):**
> KBLI 96400: AKTIVITAS JASA INTERMEDIASI UNTUK JASA PERORANGANnnWHAT IT MEANS:nPersonal services
> intermediary — a platform that connects clients with personal service providers...nnBALI
> CONTEXT:n...Critical tax issue...'Spa' classified as entertainment can face 40-75% PBJT (entertainment
> tax)...

**Canonical licensing (24 raw rows) — corrected after adversarial review, independently re-pulled row by
row: this is NOT a clean two-track PPMSE/non-PPMSE split.** The first draft's "two tracks, each with its own
risk categorization" framing is too tidy for what's actually there. The 24 rows resolve into (at least)
FOUR overlapping groups, several duplicated near-verbatim across `scope_index` sub-clauses (this pack's own
stated method already flags this as a known raw-data pattern, but this code's duplication is heavier than
most): (1) PPMSE/PSP-registered operators — Mikro **Rendah**/Otomatis, but Kecil/Menengah/Besar **Tinggi**/3
hari (risk does NOT stay constant across scale within this track); (2) non-PPMSE operators ("Selain PPMSE
dan PSP") — Kecil/Menengah **Menengah Rendah**/Otomatis, Besar **Menengah Tinggi**/7 hari (no Mikro row
exists in this specific sub-scope); (3) a broad "Seluruh, kecuali [PPMSE...]" bucket repeated across several
near-identical `scope_index` entries, uniformly **Rendah**/Otomatis for Mikro/Kecil/Menengah; (4) a plain
"Seluruh" (no PPMSE distinction at all) bucket, **Rendah**/Otomatis for ALL FOUR scales including Besar.
Whether groups (3)/(4) are genuinely separate regulatory tracks or raw-data duplication of the same
underlying activity is not something this pack can resolve with confidence — flagged rather than guessed.
`pma_status = TERBUKA`.

**Verdetto: SILENTE on licensing** (the stored prose makes no licensing claim to contradict), and the
tax warning remains a DIFFERENT, non-overlapping regulatory axis (PBJT entertainment tax classification)
that canonical's `per_skala` doesn't address at all — nothing to contradict there either. But the pack's
OWN first-draft rewrite over-simplified a genuinely messy canonical structure into a clean binary that isn't
supported by the raw rows — corrected below to be honest about the mess rather than paper over it.

**Bozza (corrected):**
> **What it means**: Personal-services intermediary — a platform connecting clients with personal-service
> providers (e.g. booking a massage therapist, aggregating spa services). You are the matchmaker, not the
> service provider.
>
> **Licensing**: Whether you operate as a registered PPMSE/PSP (electronic-trading system operator under
> Indonesia's e-commerce regulation) materially affects your risk tier, but the relationship is NOT a simple
> two-track split — canonical's data for this code is unusually complex, with risk tiers varying by BOTH
> registration status and scale (e.g. a PPMSE-registered Mikro-scale operator is Rendah risk, but a
> PPMSE-registered Kecil/Menengah/Besar operator is Tinggi risk). Given the complexity, confirm your specific
> scale + registration status directly against the live OSS system rather than relying on a general rule
> here.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: The platform economy for beauty/wellness bookings is growing fast in Bali. Critical tax
> issue: "spa" services classified as entertainment can face 40-75% PBJT (entertainment tax) — clarify
> whether the platform connects users to "wellness/health" services (lower tax bracket) or "entertainment/
> spa" services (higher bracket); the classification materially affects margins for both the platform and
> its service providers. This tax question is entirely separate from, and does not resolve, the
> PPMSE/scale-dependent licensing question above.

---

## Full summary — all 25 codes

**Table below reflects the verdicts AFTER adversarial review and independent correction — see the review
section for what changed from the first draft.**

| Verdict | Count | Codes |
|---|---|---|
| **CONTRADICE** | 5 | 56400 (topic mismatch — "food trucks" prose on an intermediation-platform code), 85573, 85574, 96230 (all three: false "BPS_ONLY/no PP28 data yet/pending" claims on codes canonical already fully populates), 90310 (live prose names ARMA/Neka/Agung Rai as examples — official scope explicitly EXCLUDES galleries and museums from this code) |
| **COMPATIBILE** | 6 | 65111, 65121 (80% PMA cap independently verified against canonical's own `pma_cap_verified`/official basis), 74192, 85102 (partially corroborated — the "outside OSS" fact is confirmed, the Yayasan-structure/6-12-month claims are hand-authored domain knowledge canonical doesn't independently confirm), 85510, 85520 |
| **SILENTE** | 14 | 03231, 03232, 03233, 62900, 85571, 85572, 85575, 85579, 85693, 85694 (narrowly, electrical-technician sub-scope only), 90200 (with a scope correction, see card), 91122, 96300, 96400 |

**Also flagged, not a licensing verdict**: 03233's stored prose calls its species "freshwater" when
canonical's `uraian` is unambiguously "brackish" throughout — a factual error distinct from the
licensing-contradiction question this mandate scopes (see card).

**Cross-cutting findings, not limited to any one code:**

- **The three CONTRADICE rows sharing "BPS_ONLY/pending" language (85573, 85574, 96230) are a pattern, not
  three coincidences** — all three were evidently written before PP28 per-skala data existed for their
  codes and never revisited once canonical was populated. `CONTRADICTED_LICENSING_CLAIM_RE` in
  `kbli_documents_cure.py` is a literal-phrase probe by its own docstring's admission; these three phrasings
  ("absence of PP28 requirements... for now", "the licensing details are still pending", "no PP28 licensing
  data yet... requirements are pending") are close enough in MEANING but different enough in WORDING to all
  evade it. Worth widening that regex's phrase list with these three as new test cases, independent of
  whether these specific 3 rows get manually rewritten from this pack.
- **56400 and 90310 are qualitatively different from the rest** — neither is a licensing-completeness gap;
  both are the wrong content under the right code (56400: literally the wrong business activity; 90310:
  named venue examples the code's own official scope explicitly excludes). These two should be triaged
  ahead of the others — they're actively misdirecting a reader today, not merely silent.
- **This pack's OWN first draft introduced defects that adversarial review caught, not just inherited ones**
  — 85573's rewrite invented a topic list (yoga/surf/photography/music) that belongs to a different code
  entirely or nowhere in this pack's scope, 90310's rewrite reproduced the live prose's gallery/museum error
  instead of catching it, and 96230/96400's rewrites flattened genuinely messy canonical structures (a
  subject-matter split misread as a scale split; a >20-row structure misread as a clean binary) into
  incorrect simplifications. Lesson for future rounds of this kind of work: reading the official `uraian`
  and the FULL raw `per_skala` array in full, every time, is not optional even when a summarized version
  looks clean enough to trust.
- **Two rows (03232/03233, plus 91122) have a genuinely EMPTY "BALI CONTEXT" section** — the label exists,
  the content after it does not. Not a contradiction, but a gap this pack could not responsibly fill with
  invented copy; flagged rather than guessed.
- **Side-finding (Part 1 §0, repeated here for visibility): 312 rows across the whole `kbli_documents` table
  — far beyond this mandate's 25 — have zero real newline characters in stored `content`**, rendering as a
  run-on wall of text on WhatsApp/webchat. Out of scope for this mandate's rewrite proposals but material
  enough that it should not be buried in a single Part-1 footnote. The adversarial reviewer, working without
  live Postgres access, could not independently confirm the 312-row table-wide count, but confirmed that all
  25 quoted rows in this pack are internally consistent with the artifact (visible "n" where a newline would
  be expected).

## Adversarial review

**Seat**: `codex` (`codex exec -m gpt-5.6-sol`, reasoning effort `high`, `--sandbox read-only`), run against
the first drafts of all three parts of this pack, independently re-querying the canonical dataset (no live
Postgres access in that sandbox — the reviewer treated this pack's verbatim quotes of stored `content` as
the claim under test, but re-derived everything canonical-side itself rather than trusting this pack's
summaries), and asked specifically to (1) independently verify three flagship claims (56400's topic-mismatch
finding, the 85573/85574/96230 false-"pending" pattern, and the 65111/65121 80%-cap corroboration), (2)
judge whether each code's verdict was actually correct, and (3) check every rewrite draft for two failure
modes: contradicting a canonical row, or dropping hand-written value from the original prose. This is the
generator≠grader gate the mandate asked for — the reviewer never saw this pack's internal reasoning, only
its output.

**Result: the review found real, confirmed defects — this was not a rubber-stamp.** All three flagship
claims were confirmed (56400's commission-platform scope and food-truck exclusion; 85573/85574/96230's
fully-populated per_skala rows disproving their "pending" claims; 65111/65121's `pma_cap_verified=true`
matching the 80% claim). But the reviewer also flagged 8 codes with substantive defects and 3 verdicts that
needed correction — every one of which was independently re-verified against `KBLI_2025_FINAL_CLEAN.json`
(and, for the insurance/spa/personal-intermediary rows, against live `kbli_documents.content` via a fresh
Postgres query) **in this session, not accepted on the reviewer's word alone**, per this pack's own stated
discipline. All were confirmed real and have been corrected in place above:

| Code | Reviewer's finding | Independently confirmed? | Fix applied |
|---|---|---|---|
| 03232 | Verdict too weak — canonical's own `uraian` is internally inconsistent (first sentence says "air tawar"/freshwater, title + second sentence say "air payau"/brackish); the draft picked brackish without flagging the source conflict | CONFIRMED — pulled `uraian` directly | Added explicit note of the canonical inconsistency; rewrite states which reading it follows and why |
| 03233 | The stored prose says "freshwater" but canonical is unambiguously "brackish" throughout — a real factual error the SILENTE verdict didn't name | CONFIRMED — pulled `uraian`, no "air tawar" anywhere in it | Verdict annotated to name the error explicitly, rather than let the rewrite silently fix it |
| 56400 | Draft's licensing paragraph applied the risk tiers to "platforms or agencies" broadly, but all 3 canonical rows are scoped ONLY to non-PPMSE/PSP intermediaries | CONFIRMED — all 3 `scope_uraian` values read "Selain PPMSE dan PSP" | Added explicit non-PPMSE scoping caveat |
| 65111 | Draft dropped the original's specific "must meet minimum local market capitalization" claim, replacing it with a differently-sourced OJK-equity citation | CONFIRMED — re-pulled live `content`; both claims are genuinely present in the original stored prose, pack's rewrite let one crowd out the other | Restored the market-capitalization claim explicitly alongside the equity citation |
| 85102 | Verdict overstated as "corroborated" — canonical confirms the "outside OSS" fact but not the specific Yayasan-structure requirement or "6-12 months" duration | CONFIRMED — canonical's only relevant field is the outside-OSS timeline string; no field addresses ownership structure or duration | Verdict language softened to distinguish confirmed vs. hand-authored-but-plausible claims |
| 85510 | Draft diluted "Bali Immigration regularly raids yoga studios and surf camps" into generic "actively enforces", losing frequency and named targets | CONFIRMED — re-pulled live `content`, exact phrase present | Restored the specific claim verbatim in substance |
| 85573 | Draft's Bali-context invented a topic list (yoga, surf, photography, music/film) not in this code's official scope at all — yoga/surf is explicitly 85510 per this SAME pack's own 85510 card | CONFIRMED — official `uraian` covers only crafts/textile/leather/fashion/beauty; no mention of yoga, surf, photography, or music | Bali-context section rewritten to the actual scope, with an explicit note distinguishing this code from 85510 |
| 85579 | Draft's "5 to 30 working days" framing implied every sub-activity has a set timeline; most of the 52 raw rows (nuclear/radiation-safety sub-scopes, K3 consultation, general "other vocational") have NO stated timeline at all | CONFIRMED — read all 52 rows' `jangka_waktu` fields; the majority are empty strings | Licensing text corrected to state that a timeline is the exception, not the rule, for most sub-scopes |
| 85694 | Draft applied "Menengah Tinggi, 5 days" to ALL independent certification (CompTIA, PMI, food safety, sustainability); canonical's only populated sub-scope is electrical-power-technician certification specifically | CONFIRMED — all 4 rows share one identical `scope_uraian`, electrical-technician only | Licensing narrowed explicitly to the electrical-technician sub-scope; named examples (CompTIA etc.) flagged as unconfirmed for licensing purposes |
| 90200 | Draft's "not the venue" claim was too categorical — official `uraian` explicitly includes operating an arts facility for one's OWN performing group | CONFIRMED — `uraian` lists this exact clause | Rewrite corrected: own-group venue use is included; only third-party venue operation is exclusively 90310 |
| 90310 | Draft (and the LIVE stored prose itself) names ARMA Museum, Neka Art Museum, and Agung Rai as examples — official `uraian` explicitly EXCLUDES commercial galleries (→4769) and museums (→90200's family) from this code | CONFIRMED — `uraian`'s "tidak mencakup" clause names both exclusions verbatim; per_skala scope is literally "Taman Budaya" | Verdict upgraded from SILENTE to CONTRADICE; Bali-context section rewritten entirely around auditoriums/Taman Budaya/live-music venues, with the gallery/museum examples explicitly named as wrong |
| 96230 | Draft's Besar-vs-rest framing conflated business SCALE with the real split, which is Medical Spa vs. non-Medical Spa; the "two distinct central-ministry sign-offs" reading of Besar's authority field is wrong — it's the identical value listed twice, not two different ministries | CONFIRMED — re-pulled full `per_skala` with `scope_uraian`; Besar row is scoped to Medical Spa specifically, Mikro/Kecil/Menengah to non-Medical Spa specifically; authority array for Besar is `["Menteri/Kepala Badan","Menteri/Kepala Badan"]`, literally duplicated | Licensing section rewritten around the medical/non-medical split; the population gap (no Besar non-medical row, no small-scale medical row) stated explicitly rather than papered over |
| 96400 | Draft's "two clean tracks" (PPMSE vs. non-PPMSE) oversimplifies a 24-row structure with at least 4 overlapping groups and heavy near-duplication, where risk varies by scale WITHIN each track (e.g. PPMSE-registered Mikro is Rendah, but PPMSE-registered Kecil/Menengah/Besar is Tinggi) | CONFIRMED — re-pulled and read all 24 raw rows individually | Licensing text rewritten to honestly describe the complexity and recommend confirming against live OSS rather than asserting a clean two-track rule |

**General objections, by severity (reviewer's framing, after independent confirmation):**

1. Eight rewrite drafts contained substantive canonical-contradicting or scope-distorting errors introduced
   BY THIS PACK's own first draft, not inherited from the stored prose — all corrected above.
2. Two verdicts (03232, 03233) needed to be more than plain SILENTE because of a genuine content-accuracy
   issue distinct from licensing — corrected above.
3. One verdict (85102) overstated how much of its claim canonical actually corroborates — corrected above.
4. Two edits (65111, 85510) silently dropped hand-authored specific claims in favor of vaguer or
   differently-sourced substitutes — both restored.
5. The table-wide 312-row newline-corruption count could not be independently re-verified by the reviewer
   (no live Postgres access in its sandbox), though nothing in the 25 quoted rows here contradicts it.

No code's verdict needed to move in the other direction (i.e. no reviewer objection was itself found to be
wrong on independent re-check) — every finding the reviewer raised against this pack's first draft held up.
