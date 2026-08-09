---
date: 2026-08-09
domain: operations
topic: kbli-25refused-rewrite-pack-part2
client_case: none — internal `kbli_documents` data-quality follow-up, Mandate 10, part 2 of 3 (education family — 11 of the 25 codes), requested by Zero via team-lead
discovered_by: kbli-docs-flip subagent, Mandate 10 (team-lead directive, on Zero's request)
sources:
  - "Postgres `kbli_documents` (prod, via `mcp__postgres-nuzantara__query`, read-only role) — live `content`/`judul` for the 11 codes in this file, queried this session"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json — canonical 2025 dataset; full `per_skala` array (incl. `scope_uraian` sub-scope text) and top-level `pma_*` fields for all 11 codes"
  - "apps/backend-rag/backend/scripts/kbli_documents_cure.py::CONTRADICTED_LICENSING_CLAIM_RE — the literal-phrase gate two of this file's rows evade (see 85573/85574 below); its own docstring names this as a declared limit, not a bug"
adversarial_review: codex
---

# KBLI 25-refused rewrite pack — part 2 of 3 (education family)

See Part 1 for the shared method, the re-measured population (still 25, unchanged since 2026-08-02), and
the side-finding that all 25 rows' stored `content` has zero real newline characters. **Proposals only —
nothing in this file was applied to `kbli_documents`.**

---

## 85102 — Pendidikan Taman Kanak-Kanak Umum Swasta

**Prosa attuale (verbatim):**
> KBLI 85102: PENDIDIKAN TAMAN KANAK-KANAK UMUM SWASTAnnWHAT IT MEANS:nPrivate kindergarten...nnBALI
> CONTEXT:n...The Yayasan structure is fundamentally different from a profit-generating PT PMA...The SPK
> framework adds another layer of approval that takes 6-12 months minimum.

**Canonical licensing (16 raw rows, deduplicated):** ALL scales → **Tinggi** (high) risk, timeline *"Izin
Kemendikbud (di luar OSS)"* — a Kemendikbud permit issued OUTSIDE the standard OSS system, for every scale.

**Verdetto: COMPATIBILE — but corroboration is partial, corrected after adversarial review.** Canonical's
"outside OSS" timeline field directly backs ONE claim: that this activity needs a special Kemendikbud
approval process separate from a standard OSS/NIB clock. That much is confirmed. Canonical does **not**,
however, contain a field proving the two more specific hand-written claims — that the operating structure
must be a Yayasan (non-profit foundation) rather than a PT PMA, or that the SPK track "takes 6-12 months
minimum". Those are real, plausible, hand-authored domain knowledge (consistent with Indonesian education
law generally), but this pack cannot independently verify them against `KBLI_2025_FINAL_CLEAN.json` the way
it can the risk tier and the outside-OSS fact — the original draft overstated this as fully "corroborated"
when only part of it is.

**Bozza:**
> **What it means**: Private kindergarten — early childhood education for ages 4-6 (priority enrollment
> 5-6), play-based and holistic.
>
> **Licensing**: All scales — Tinggi (high) risk. The permit is issued by Kemendikbud OUTSIDE the standard
> OSS risk-based system — it does not follow the normal NIB timeline.
>
> **PMA**: Fully open on paper, but the *operating structure* is the real constraint: Indonesian kindergarten
> law requires a non-profit Yayasan foundation, not a profit-generating PT PMA, to hold the school license.
> The SPK (foreign-cooperation school) approval track adds 6-12 months minimum on top of that.
>
> **Bali context**: Rising demand from expat families in Ubud, Sanur, and Canggu. Founders who set up a
> standard PT PMA expecting to run the school directly are the most common failure mode — the Yayasan
> structure changes how money and control flow through the business entirely.

---

## 85510 — Pendidikan Olahraga dan Rekreasi

**Prosa attuale (verbatim):**
> KBLI 85510: PENDIDIKAN OLAHRAGA DAN REKREASInnWHAT IT MEANS:nSports and Recreation Education...surf
> schools, yoga teacher training, martial arts dojos...nnBALI CONTEXT:n...they MUST possess a valid Working
> KITAS with a proper IMTA (work permit) declaring them as 'Master Trainers'. Bali Immigration regularly
> raids yoga studios and surf camps...

**Canonical licensing (8 raw rows):** ALL scales → **Tinggi**, timeline **not specified** in canonical (empty
string on every row — an honest gap in the SSOT itself, not something the prose can be faulted for missing).
`pma_status = TERBUKA`.

**Verdetto: COMPATIBILE.** "Completely open to foreign ownership" matches. The immigration/KITAS warning is
valuable, real-world content canonical has no field for at all — must be preserved verbatim in substance.

**Bozza:**
> **What it means**: Non-degree training and camps in sports/recreation — explicitly includes surf schools,
> yoga teacher training, martial arts, equestrian, swimming, and e-sports coaching by professional
> instructors.
>
> **Licensing**: All scales — Tinggi (high) risk. Canonical does not specify a standard processing timeline
> for this code — treat any quoted timeline as an estimate, not a guarantee.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: The corporate license is rarely the real obstacle — immigration and manpower law is.
> Foreign yoga teachers or surf coaches employed under a PT PMA using this code MUST hold a Working KITAS
> with an IMTA declaring them "Master Trainers". Bali Immigration regularly raids yoga studios and surf
> camps specifically to catch foreigners "teaching" on tourist or investor visas without that KITAS/IMTA.
>
> *(Fix after adversarial review: the first draft of this rewrite diluted "regularly raids yoga studios and
> surf camps" into the vaguer "actively enforces" — losing the frequency and the specific named targets.
> Restored above.)*

---

## 85520 — Pendidikan Kebudayaan

**Prosa attuale (verbatim):**
> KBLI 85520: PENDIDIKAN KEBUDAYAANnnWHAT IT MEANS:nCultural education — non-formal education in arts,
> drama, and music...nnBALI CONTEXT:n...The PT PMA route makes this much more accessible to foreign
> operators than formal education...Dinas Pendidikan still requires curriculum registration, but the process
> is lighter than for formal schools.

**Canonical licensing (8 raw rows):** ALL scales → **Tinggi**, timeline not specified (empty). `pma_status =
TERBUKA`.

**Verdetto: COMPATIBILE, with a nuance worth naming explicitly.** "Lighter than formal schools" is about the
STRUCTURE (PT PMA vs. Yayasan/SPK — genuinely lighter), not the risk CATEGORY, which canonical marks Tinggi
same as any other education code. The rewrite should say both things so a reader doesn't conflate them.

**Bozza:**
> **What it means**: Non-formal cultural education — dance studios, music schools, art workshops, creative
> classes. Training in creative arts, not a path to a formal academic qualification.
>
> **Licensing**: All scales — Tinggi (high) risk, same category as formal education codes; canonical does
> not specify a processing timeline.
>
> **PMA**: Fully open — 100% foreign ownership allowed, via a standard PT PMA — a materially lighter
> corporate structure than the Yayasan/SPK route formal schools require, even though the RISK category
> itself is the same "Tinggi" tier.
>
> **Bali context**: Dance studios, music schools, and art workshops are everywhere in Ubud and Canggu (e.g.
> gamelan classes for tourists). Yoga teacher training programs often overlap with this code. Dinas
> Pendidikan curriculum registration still applies.

---

## 85571 — Pelatihan Kerja Teknik Swasta

**Prosa attuale (verbatim):**
> KBLI 85571: PELATIHAN KERJA TEKNIK SWASTAnnWHAT IT MEANS:nPrivate technical vocational training — welding,
> CNC machining, electrical installation...nnBALI CONTEXT:n...BNSP competency certification is increasingly
> required by large employers. Dinas Ketenagakerjaan Bali oversees LPK (Lembaga Pelatihan Kerja) licensing.

**Canonical licensing (4 raw rows):** ALL scales → **Menengah Tinggi** (medium-high), 5 hari. `pma_status =
TERBUKA`.

**Verdetto: SILENTE.** No claim in the prose to contradict; it just doesn't state the risk tier/timeline.

**Bozza:**
> **What it means**: Private technical vocational training — welding, CNC machining, electrical installation,
> plumbing, automotive/marine mechanics, and similar trades. Training workers, not academic students.
>
> **Licensing**: All scales — Menengah Tinggi (medium-high) risk, NIB + Sertifikat Standar within 5 working
> days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali has an acute shortage of skilled trade workers as construction demand outpaces
> supply. BNSP competency certification is increasingly required by large employers; Dinas Ketenagakerjaan
> Bali oversees the LPK (Lembaga Pelatihan Kerja) licensing track alongside the NIB.

---

## 85572 — Pelatihan Kerja Teknologi Informasi dan Komunikasi Swasta

**Prosa attuale (verbatim):**
> KBLI 85572: PELATIHAN KERJA TEKNOLOGI INFORMASI DAN KOMUNIKASInnWHAT IT MEANS:nPrivate ICT job training —
> ...coding bootcamps, web development courses, cybersecurity workshops...nnBALI CONTEXT:n...Le Wagon ran
> cohorts out of Canggu...Teacher qualifications are strictly checked...

**Canonical licensing (4 raw rows):** ALL scales → **Menengah Tinggi**, 5 hari. `pma_status = TERBUKA`.

**Verdetto: SILENTE.**

**Bozza:**
> **What it means**: Private ICT job training — networking, technical support, cybersecurity, programming,
> and digital skills. Skills-based training, not degree-granting education.
>
> **Licensing**: All scales — Menengah Tinggi risk, NIB + Sertifikat Standar within 5 working days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Coding bootcamps have a real track record in Bali (Le Wagon ran cohorts out of Canggu),
> fed by the digital-nomad community's demand for upskilling. Instructor qualifications are actively checked
> by regulators — don't imply formal certification in marketing unless the school actually holds
> accreditation.

---

## 85573 — Pelatihan Kerja Industri Kreatif Swasta

**Prosa attuale (verbatim):**
> KBLI 85573: PELATIHAN KERJA INDUSTRI KREATIF SWASTAnnWHAT IT MEANS:nCreative industry training...
> nnBALI CONTEXT:n...**The absence of PP28 requirements means lower regulatory friction — for now.** Smart
> operators will get their NIB established early and build their reputation before the full licensing
> framework drops.

**Canonical licensing (4 raw rows):** ALL scales → **Menengah Tinggi**, 5 hari, named authorities
(Bupati/Walikota + Menteri/Kepala Badan). `pma_status = TERBUKA`. Official `uraian` (read in full — the
first draft of this card did not quote it and, as a result, mis-scoped the rewrite below): *"...pelatihan
kerja yang bertujuan untuk menambah ketrampilan/keahlian dalam bidang teknik ukir logam, teknik ukir kayu,
merenda, menyulam, menenun, sablon, anyaman, teknik batik tulis, teknik batik cap, penyamakan kulit,
finishing kulit, pembuatan produk dari kulit, menjahit, teknik bordir, teknik pola, fashion design, fashion
technology, kecantikan kulit, kecantikan rambut..."* — this code is scoped to **traditional craft, textile,
leather, fashion, and beauty-industry vocational training**: metalwork/woodcarving, crochet/embroidery/
weaving, screen-printing, wickerwork, batik (tulis and cap), leather tanning/finishing/leather goods,
sewing/pattern-making, fashion design and fashion technology, and skin/hair beauty training. It says nothing
about yoga, surfing, photography, music, or film.

**Verdetto: CONTRADICE — two independent, unrelated defects on the same code.** (1) The prose asserts *"the
absence of PP28 requirements"* and frames the regulatory picture as still pending — but canonical already
carries a full risk tier, a named 5-day timeline, and named authorities for every scale. This phrasing
("absence of PP28 requirements... for now") is close to, but does not literally match, the cure tool's own
`CONTRADICTED_LICENSING_CLAIM_RE` regex (`no PP28 data|licensing is currently minimal|no licensing data
yet|belum ada data PP28`) — which is exactly why this row landed in the REFUSED bucket instead of being
auto-rebuilt as a caught contradiction. Worth reporting as a near-miss of that regex, not just a one-off row
fix. (2) **Confirmed by adversarial review, independently verified against the official `uraian` above**:
the FIRST DRAFT of this pack's own rewrite named "Yoga teacher training, surf instructor courses,
photography and music-production workshops" as falling under 85573 — none of which the official scope
covers. Yoga/surf training is explicitly 85510 (this same pack's own card for 85510 already says so);
photography and music production appear nowhere in 85573's `uraian` at all. This was this pack's own
authoring error, not something inherited from the stored prose (the live `content`'s "BALI CONTEXT" for
85573 is a general regulatory-friction remark, not a topic list) — caught only because an independent
reviewer re-read the source `uraian` rather than trusting the draft.

**Bozza (corrected):**
> **What it means**: Non-degree creative-industry vocational training — traditional and modern craft skills
> including metal/wood carving, crochet/embroidery/weaving, screen-printing, wickerwork, batik (tulis and
> cap techniques), leather tanning/finishing/leather-goods production, sewing and pattern-making, fashion
> design and fashion technology, and skin/hair beauty training. Teaching hands-on craft/trade skills, not
> granting academic degrees.
>
> **Licensing**: All scales — Menengah Tinggi risk, NIB + Sertifikat Standar within 5 working days.
> Authority is shared between Bupati/Walikota and the central ministry.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali's batik, weaving, leatherwork, silversmithing, and fashion-design ateliers regularly
> run paid apprenticeship/training programs alongside production — this code covers that training activity
> specifically, distinct from the production/retail business itself (which needs its own manufacturing or
> trade code). Beauty-industry training (skin and hair) is also in scope here. Note: yoga/surf instructor
> training is a DIFFERENT code (85510, "Pendidikan Olahraga dan Rekreasi") — don't conflate the two when
> advising a client.

---

## 85574 — Pelatihan Kerja Pariwisata dan Perhotelan Swasta

**Prosa attuale (verbatim):**
> KBLI 85574: PELATIHAN KERJA PARIWISATA DAN PERHOTELAN SWASTAnnWHAT IT MEANS:nPrivate hospitality and
> tourism training — training programs...Barista courses, hotel management training, tour guide
> certification programs...nnBALI CONTEXT:n...**Since this is a BPS_ONLY code, the licensing details are
> still pending** — but the opportunity is clear...

**Canonical licensing (4 raw rows):** ALL scales → **Menengah Tinggi**, 5 hari, named authorities. Same
shape as 85571-85573. `pma_status = TERBUKA`.

**Verdetto: CONTRADICE — the same defect as 85573, independently occurring.** *"Licensing details are still
pending"* is false: canonical holds a complete risk/timeline/authority row for every scale. Two codes in
this same 855xx sibling family making the same now-false claim, in two different phrasings, both missed by
the cure tool's literal regex — this looks like a systematic gap in that regex's phrase list rather than two
unrelated one-offs, worth flagging to whoever maintains `_whatchanged_basis`-style pattern lists.

**Bozza:**
> **What it means**: Private hospitality and tourism job training — barista courses, hotel-management
> training, tour-guide certification, hospitality service-excellence workshops.
>
> **Licensing**: All scales — Menengah Tinggi risk, NIB + Sertifikat Standar within 5 working days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Bali's hospitality sector constantly needs trained staff across hotels, restaurants,
> villas, and tour operators. Programs range from basic housekeeping training to professional barista
> academies to full hospitality-management courses; growing niches include wellness-therapist and
> mixology/bartending training.

---

## 85575 — Pelatihan Kerja Bisnis dan Manajemen Swasta

**Prosa attuale (verbatim):**
> KBLI 85575: PELATIHAN KERJA BISNIS DAN MANAJEMEN SWASTAnnWHAT IT MEANS:nPrivate business and management
> training...nnBALI CONTEXT:n...wellness retreats that include 'business coaching' or 'entrepreneurship
> workshops' often need this code...The line between 'community event' and 'educational service' gets
> blurry...

**Canonical licensing (4 raw rows):** ALL scales → **Menengah Tinggi**, 5 hari. `pma_status = TERBUKA`.

**Verdetto: SILENTE.**

**Bozza:**
> **What it means**: Private business/management training — entrepreneurship, leadership, HR management,
> marketing, and other practical business skills. Non-degree.
>
> **Licensing**: All scales — Menengah Tinggi risk, NIB + Sertifikat Standar within 5 working days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Wellness retreats or co-working spaces that bundle "business coaching" or
> "entrepreneurship workshops" alongside their core offering often need this code too — the line between a
> community event and a chargeable educational service is where operators most often get caught out.

---

## 85579 — Pelatihan Kerja Swasta Lainnya

**Prosa attuale (verbatim):**
> KBLI 85579: PELATIHAN KERJA SWASTA LAINNYAnnWHAT IT MEANS:nOther Private Job Training — personal
> development, motivational training, NLP, career development, K3 methodologies...nnBALI CONTEXT:n...KBLI
> 85579 provides a legal, 100% foreign-owned umbrella for these personal development and NLP training
> businesses...

**Canonical licensing (52 raw rows — the largest per_skala array of the whole 25, reflecting many distinct
`scope_uraian` sub-activities lumped into this "other" catch-all):** every row is **Menengah Tinggi** risk.
Reading the sub-scopes in full (correction after adversarial review — the first draft's "5 to 30 working
days" framing implied every sub-activity has SOME set timeline, which is wrong): the 52 rows are dominated
by nuclear/radiation-safety training sub-scopes (radioactive-waste-facility officers, X-ray equipment
testers, industrial radiography, reactor officers, radiation-protection officers, etc.) plus K3 (occupational
health & safety) consultation, plus a residual "other vocational training outside K3" bucket. Only a MINORITY
of these sub-scopes carry a stated timeline — **5 hari** (e.g. nuclear-installation officers, industrial
radiation-protection officers) or **30 hari** (medical radiation-protection officers) — the rest, including
K3 consultation itself and the general "other vocational" residual bucket, have **no timeline stated at all**
(empty field, not zero). `pma_status = TERBUKA`.

**Verdetto: SILENTE**, with a scope caveat worth stating rather than hiding: because this is a residual
"other" bucket, whether a timeline exists at all — let alone which number — depends entirely on which
sub-activity applies. The prose should not quote a bounded range as if it covers every case; some legitimate
sub-activities under this code have no stated processing timeline in canonical at all.

**Bozza:**
> **What it means**: The residual/catch-all for private, non-formal job training not classified elsewhere —
> personal development, motivational training, NLP, career development coaching, occupational health &
> safety (K3) methodologies, and (a large, Bali-irrelevant share of the official sub-scopes) nuclear/
> radiation-safety officer training.
>
> **Licensing**: All scales — Menengah Tinggi risk. Timeline depends entirely on the specific official
> sub-activity: some carry a stated 5 or 30 working-day timeline, but several sub-scopes — including general
> "other vocational" training and K3 consultation itself — have NO stated timeline in canonical at all.
> Confirm the exact sub-scope before quoting a client any number, and don't assume one exists.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Ubud's "life coach"/breathwork/corporate-wellness-retreat scene previously operated in a
> legal gray area on tourist visas. This code gives a legal, 100% foreign-owned structure for ticketing and
> hosting personal-development and NLP-style paid events, without needing a dedicated facility.

---

## 85693 — Aktivitas Sertifikasi Profesi oleh Asosiasi

**Prosa attuale (verbatim):**
> KBLI 85693: AKTIVITAS SERTIFIKASI PROFESI OLEH ASOSIASInnWHAT IT MEANS:nProfessional certification by
> industry or professional associations...nnBALI CONTEXT:n...IAI, PII, IAPI, PERADI, PKBR...

**Canonical licensing (8 raw rows, two genuinely distinct tracks — not a duplicate artifact):**
"Seluruh, selain Lembaga Sertifikasi Profesi (LSP) Jasa Konstruksi" (everything except construction-sector
LSPs) → **Menengah Tinggi**, **67 hari**. "Lembaga Sertifikasi Profesi (LSP) Jasa Konstruksi" specifically →
**Menengah Tinggi**, **65 hari**. `pma_status = TERBUKA`.

**Verdetto: SILENTE**, with a genuine value-add canonical holds that the prose omits entirely: a
construction-sector carve-out with its own (slightly shorter) timeline.

**Bozza:**
> **What it means**: Professional certification issued by industry/professional associations — validating
> member competency within their own profession (e.g. engineering bodies, medical specialist boards, legal
> associations).
>
> **Licensing**: Menengah Tinggi risk across all scales. Timeline is 67 working days for all sectors EXCEPT
> construction-services professional certification bodies (Lembaga Sertifikasi Profesi Jasa Konstruksi),
> which run on a 65-working-day timeline.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Active associations include IAI (architects), PII (engineers), IAPI (public accountants),
> PERADI (lawyers), and PKBR (public relations). Their certification is increasingly a prerequisite for
> government procurement eligibility; foreign professionals need Indonesian registration in addition to
> home-country credentials.

---

## 85694 — Aktivitas Sertifikasi Profesi Independen

**Prosa attuale (verbatim):**
> KBLI 85694: AKTIVITAS SERTIFIKASI PROFESI INDEPENDENnnWHAT IT MEANS:nIndependent professional certification
> activities...nnBALI CONTEXT:n...CompTIA, PMI, Cisco...Pearson VUE and Prometric testing centers in
> Denpasar...

**Canonical licensing (4 raw rows) — corrected after adversarial review, independently confirmed against
`scope_uraian`:** all 4 rows carry the SAME single `scope_uraian`: *"Usaha dalam kelompok ini adalah usaha
jasa sertifikasi kompetensi tenaga teknik ketenagalistrikan"* (electrical-power-technician competency
certification services). ALL scales → **Menengah Tinggi**, **5 hari** — but this figure is confirmed ONLY
for electrical-technician certification. Canonical carries no separate per_skala entry for other independent
certification activities (IT, project management, food safety, sustainability, sport, etc.) under this code
— the first draft's blanket "All scales — Menengah Tinggi, 5 days" applied to the whole code, including
CompTIA/PMI/Cisco-style certifiers it named, is unsupported for anything outside the electrical-technician
sub-scope.

**Verdetto: SILENTE on the electrical-technician sub-scope** (canonical states a real number, prose doesn't
contradict it — it just never surfaces it), but the ORIGINAL rewrite draft over-generalized a narrowly-scoped
canonical figure to the whole code — flagged and corrected below.

**Bozza (corrected):**
> **What it means**: Independent professional certification — bodies operating apart from both educational
> institutions and professional associations, certifying skills through competency testing alone. Canonical
> covers the *uraian*'s "independent professional certification, including in sports" activity generally,
> but its ONLY priced sub-scope is electrical-technician competency certification specifically.
>
> **Licensing**: For electrical-technician competency certification specifically — all scales, Menengah
> Tinggi risk, NIB + Sertifikat Standar within 5 working days. For other independent-certification
> activities under this code (IT, project management, food safety, sustainability, sport, etc.), canonical
> has no separate per_skala entry — do not assume the same 5-day/Menengah Tinggi figure applies without
> confirming against the live OSS system for that specific activity.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Independent certifiers active locally include IT (CompTIA, PMI, Cisco via authorized
> centers), project management (PMI PMP via Prometric), food safety (ServSafe, HACCP), and sustainability
> (LEED, Green Globe). Pearson VUE and Prometric testing centers in Denpasar administer the exams; BNSP
> oversight applies where a certification claims alignment with Indonesia's national qualifications
> framework. None of these specific examples is the electrical-technician sub-scope canonical actually
> prices — treat the licensing figure above as informative context, not a confirmed number for these
> particular certifiers.

## Adversarial review

**Seat**: `codex` (`codex exec -m gpt-5.6-sol`, reasoning effort `high`, `--sandbox read-only`), run against
the first draft of all three parts of this pack together. Full transcript and the per-code verdict table are
recorded in Part 3 of this pack (`2026-08-09-kbli-25refused-rewrite-pack-3-arts-personal-misc.md`), the
anchor file the reviewer was run against for the whole 25-code pack — cross-reference there for the complete
table, including the 11 codes in this file. This file's own cards above were revised in place (85102, 85510,
85573, 85579, 85694) to incorporate the confirmed findings for its codes; each revision states what changed
and why, independently re-verified against `KBLI_2025_FINAL_CLEAN.json` rather than accepted on the
reviewer's word alone.
