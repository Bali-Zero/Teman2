---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 2 (lane: glm-5.2)
status: round-2 raw lane output, faithfully preserved
---

# Visa Oracle — Round 2: The Interview Design

**Legend:** ⚑ = content team to verify exact code/threshold against current Permenkumhu (NB-INTEL Immigration grounding pass recommended before this hits the content team). Everything else is design judgment I'm committing to.

A note on grounding before I start: this is a **design and copy** deliverable, not a regulatory claim. Where a specific visa code, fee, or threshold appears, I've flagged it ⚑ rather than asserting it as truth — those get one NotebookLM grounding pass on NB-INTEL Immigration before the content team writes finals. The **interview logic, question wording, and UX copy** below are the actual deliverable.

---

## 1. Q0 architecture — keep, but make it Q1, not the literal first frame

**Decision: keep "Are you in Indonesia right now?" — promote the framing card in front of it, and let the onshore branch be expiry-clock-driven.**

Why Q0 stays as the master branch: no other single question carries as much downstream weight.

- **Time becomes a first-class variable only onshore.** Offshore, a visa is a plan; onshore, a visa is a *countdown*. The "days remaining" tile, the urgency colour, and whether overstay/bridging lanes even exist all depend on this one answer. You cannot honestly render the same screen for both.
- **The catalog narrows.** Onshore, the universe shrinks to what's *convertible* (you can't apply for a fresh offshore visa while sitting in Bali on an expired stamp). Offshore is the full ~110. One branch, two genuinely different products.
- **It mirrors how the person frames their own problem.** "I'm stuck / running out of time" vs "I want to get there." Designing the question they're already asking reduces the urge to game the tool.

**Refinements:**

**(a) Insert a framing screen before Q0.** A single quiet card, not a question:

> *Visa Oracle is a map, not an application. Answer a few questions — honestly, including "I don't know" — and we'll show you which Indonesian visa paths genuinely fit. Nothing here is filed. Nothing is decided for you.*

Purpose: lower the stakes so people answer truthfully instead of strategically (the TurboTax problem — if it feels like a test, people cheat; if it feels like a tool, they tell the truth). This is also where the **"paths remaining" counter** is introduced ("you start with ~110 possible paths") so the number going *down* later reads as honesty, not failure.

**(b) Onshore branch is driven by a date, not a yes/no.** When the answer is *Yes, I'm here now*, the very next thing is:

> **"When does your current stay permit or visa expire?"** *(date picker — or "It already expired")*

That single date routes the onshore lanes automatically and sets the UI urgency:

| Days remaining | Lane | UI behaviour |
|---|---|---|
| Already expired (≤0) | **Overstay-help** | Reassuring red, straight to human-review intake, no alarm copy |
| 1–7 days | **Bridging / urgent extend** | Amber, expiry tile prominent, time-sensitive copy |
| 8–60 days | **Extend or Convert** | Neutral, full choice presented |
| 60+ days / permit healthy | **Convert / Extend (planned)** | Neutral planning tone |

**The four onshore lanes, hung off that date:**

1. **Extend** — "I have an active visit visa / VOA / ITK and want to stay longer." → VOA +30, B211A visit extension, ITK extension. ⚑
2. **Convert** — "I'm here on a visit visa and want to switch to a stay permit (e.g., I got a job / married / investing)." → onshore conversion, historically via Bridging Visa then D-family residence. ⚑
3. **Bridging** — "My current permit is expiring but I already have a new application in progress." → Bridging Visa (Visa Kunjungan Saat Berlaku, 60-day transition) ⚑ — *the under-marketed branch Bali Zero should own.*
4. **Overstay-help** — "My permit already expired / I've overstayed." → **never an algorithmic verdict.** Always human-review, with the IDR 1,000,000/day statutory fine stated *as information, not threat*, and the reassurance line: *"Overstay is fixable. It is not the end of your story here. A person will walk through it with you."*

**(c) The three honest escape valves on Q0 itself:** *dual citizen / I just left and need to come back / I'm on a visa run* → these don't pick a lane, they surface a small clarifier and, if unresolved, route to human-review. We never force someone into onshore-or-offshore when their reality is neither cleanly.

---

## 2. Category-first layer

Category-first beats one universal flow (Australia finding) — but Bali Zero's population is narrower than Australia's, so **10 categories, not 20**. Order is by expected Bali-Zero frequency, not alphabet. Each is shown as a tile with EN name / ID name / one-line plain-language description. The engine treats category as a *soft* router — a category narrows but never kills cross-category candidates until the behavioral tree confirms.

| # | EN | ID | One-line | Index families reachable |
|---|---|---|---|---|
| 1 | **Tourism & short visit** | Wisata & kunjungan singkat | Holiday, visiting someone, or any quick trip under ~60 days. | Visa on Arrival (VOA/BMP), B211A (tourist & socio-cultural), B211 medical/short-purpose ⚑ |
| 2 | **Business (no work)** | Bisnis (bukan kerja) | Meetings, negotiation, site visits, conferences — no employment, no pay drawn in Indonesia. | B211 business single-entry, D12 multiple-entry business ⚑ |
| 3 | **Work & employment** | Bekerja & ketenagakerjaan | You'll be employed and paid in Indonesia by an Indonesian entity. | D-family work temporary stay (ex-KITAS work / E33-class) ⚑ + RPTKA/IMTA work permit (sibling document, not a visa) |
| 4 | **Invest & golden** | Investasi & golden visa | You're committing significant capital — into a company, bonds, or property-backed residence — or qualifying by merit. | E28A / E28B / E28C / E28D / E28F ⚑ |
| 5 | **Remote worker** | Pekerja jarak jauh | You work for clients/employers outside Indonesia; Indonesia is your base, not your market. | Remote-work stay permit (digital-nomad tier) ⚑, B211A + remote-work tolerance (lighter) ⚑ |
| 6 | **Family & marriage** | Keluarga & pernikahan | Joining a spouse or family here, or marrying an Indonesian. | Spouse-sponsored / dependent D-family (mixed-marriage KITAS lineage), follow-to-join ⚑ |
| 7 | **Retirement & second home** | Pensiun & second home | 55+ and retiring here, or you want long-term residence without employment. | Retirement temporary stay (D-family), Second-Home / Golden residential ⚑ |
| 8 | **Study** | Belajar / pendidikan | Studying, exchange, research, or training at an Indonesian institution. | Student temporary stay (D-family), research visa ⚑ |
| 9 | **Diaspora & ex-WNI** | Diaspora & eks-WNI | You're a former Indonesian citizen, of Indonesian descent, or held WNI status before. | F-family ex-WNI KITAS/KITAP, diaspora golden, second-passport handling ⚑ |
| 10 | **Something else** | Lainnya | Not sure where you fit, or a purpose not listed. | None killed — routes to a light human-review intake |

**Two design rules for the category screen:**
- **"Something else" is mandatory, not a courtesy.** It is the GOV.UK "never dead-end" principle at the top of the funnel. It must feel as legitimate as the others — same tile weight, no greyed-out styling.
- **Medical treatment folds under Tourism & short visit**, with an internal flag that escalates to human-review (medical-purpose B211 ⚑ has provider-letter requirements we shouldn't auto-decide). Not a separate tile — 10 is the ceiling for restrained atmosphere.

---

## 3. Behavioral question trees — full draft

Notation: each question carries Q text (EN / ID), options, *why we ask* (EN / ID + regulation family), skip/unknown behaviour with the **assumption text** that goes on the honesty receipt, and **keeps / kills**. Review-gate questions are shared across lanes and marked ★. Modal path target: ≤6 questions.

---

### (a) Work & employment

The behavioral spine: **who pays you, and is the payer an Indonesian-registered entity?** That single fact separates "work" from "remote worker" from "investor-who-works." We never ask "do you need D13."

**W1 — the splitter**
> **EN:** "Will an Indonesian-registered company or foundation (PT / yayasan) employ and pay you here?"
> **ID:** "Apakah Anda akan dipekerjakan dan digaji oleh perusahaan atau yayasan terdaftar di Indonesia (PT / yayasan) di sini?"
- Options: *Yes* / *No — my employer is abroad, but I'll be in Indonesia* / *I'll work for my own / a company I own* / *I'm not sure*
- *Why we ask* (EN): "Whether your payer is Indonesian decides if this is a work permit matter or a different path entirely." / **ID:** "Pemberi kerja Anda orang Indonesia atau bukan menentukan apakah ini urusan izin kerja atau jalur lain."
- Regulation family: D-family work temporary stay; RPTKA/IMTA work-permit regime ⚑
- Skip / "Not sure": **conservative branch = human-review.** Assumption receipt: *"You weren't sure who pays you, so we won't guess a visa. A person will help you place this correctly."* (Nothing auto-killed — held for review.)
- Keeps / kills:
  - *Yes* → keeps D13-class work + RPTKA/IMTA ⚑; kills Business-no-work, Remote, Invest, Golden
  - *No, employer abroad* → **redirect to Remote worker lane** (with a flag: working physically in Indonesia for a foreign employer can still trigger permit need → human-review for the activity boundary)
  - *Own company* → **redirect to Invest & golden** (entrepreneur-investor)

**W2 — role class**
> **EN:** "What kind of role is it?"
> **ID:** "Pekerjaan apa yang akan Anda jalani?"
- Options: *Professional / expert consultant* · *Teacher or education* · *Religious / clergy* · *Arts, entertainment, sport* · *Oil, gas, mining, energy* · *Manager or director* · *Skilled trade / technician* · *Other*
- *Why we ask*: "Work-permit approval route and fee differ by position class; some roles have quotas." / **ID:** "Jalur persetujuan dan biaya izin kerja berbeda per jabatan; sebagian ada batas kuota."
- Family: RPTKA position streams ⚑
- Skip: assume *general professional/expert*; keeps D13-class alive; receipt: *"We assumed a general professional role — tell the adviser your exact title so fees are right."*
- Keeps/kills: none killed; refines the D13 candidate + fee band.

**W3 — nationality ★-adjacent (calling-visa screen)**
> **EN:** "What passport will you travel on?"
> **ID:** "Paspor apa yang akan Anda gunakan?"
- Options: nationality selector (full ISO list) + *"I hold two passports"* / *"Diplomatic / official passport"*
- *Why we ask*: "Some nationalities need advance clearance before a visa is issued; official passports follow a separate route." / **ID:** "Sebagian kewarganegaraan perlu persetujuan terlebih dahulu; paspor dinas melalui jalur tersendiri."
- Family: calling-visa / prapenelitian regime ⚑
- Skip: **conservative = assume calling-visa treatment** (adds time, flags review). Receipt: *"We didn't assume your nationality was clear-cut — some passports need pre-clearance, which a person will confirm."* Dual passport and diplomatic → **human-review immediately.**
- Keeps/kills: keeps path but moves calling-visa nationalities + diplomatic to review; no clean kill.

**W4 — review-gate ★**
> **EN:** "Does any of the following apply to you?"
> **ID:** "Apakah ada dari hal-hal berikut yang berlaku untuk Anda?"
- Options (multi): *Criminal record* · *Serious health condition requiring ongoing care* · *Prior visa refusal* · *Past overstay in Indonesia* · *Currently on an Indonesian blacklist / moratorium* · *None of these*
- *Why we ask*: "These legally require a human assessment — we will never auto-decide them." / **ID:** "Hal-hal ini wajib dinilai oleh manusia — kami tidak pernah memutuskannya secara otomatis."
- Family: admissibility / security / health review regime
- Skip / "I'd rather not say": **conservative = human-review.** Receipt: *"You preferred not to say, so we hold this for an adviser rather than guessing you're clear."* **Any non-"None" answer → HUMAN_REVIEW_REQUIRED, no verdict rendered.**
- Keeps/kills: gates the entire lane. Nothing killed algorithmically; verdict deferred.

**W5 — duration**
> **EN:** "How long is the engagement?"
> **ID:** "Berapa lama penugasannya?"
- Options: *Up to 6 months* · *6–12 months* · *More than 1 year* · *Indefinite / open-ended*
- *Why we ask*: "Permit duration and renewal cycle depend on how long you'll stay." / **ID:** "Lama izin dan siklus perpanjangan tergantung durasi Anda."
- Family: ITAS / D-family duration tiers ⚑
- Skip: assume *12 months* (renewable); keeps D13-class; receipt: *"We assumed a 12-month stay — easy to adjust."*

**W6 — family ★ (shared, optional)**
> **EN:** "Will a spouse or children come with you?"
> **ID:** "Apakah pasangan atau anak Anda akan ikut?"
- Options: *No, just me* · *Yes — spouse and/or children under 18* · *Yes — other family*
- *Why we ask*: "Companions may need their own linked permits; minors have extra steps." / **ID:** "Pendamping mungkin perlu izin tersendiri; anak di bawah umur ada langkah tambahan."
- Family: dependent / follow-to-join permits ⚑
- Skip: assume *no companions* (trivially editable later). *Other family* or *children under 18* → adds **minors human-review trigger.**

**Modal path:** W1 → W2 → W3 → W4 → W5 = **5 questions** (+ W6 if family). Winner: **D13-class work temporary stay + RPTKA/IMTA work permit** ⚑. Human-review fires at W3 (calling-visa/diplomatic/dual), W4 (any flag), W6 (minors).

---

### (b) Invest & golden

Behavioral spine: **what qualifies you — capital, merit, family link, or property-backed residence — and roughly how much capital?** The E28 family splits along exactly these lines; we ask in plain terms, never "E28A."

**I1 — the sub-type router**
> **EN:** "How would you like to qualify for long-term residence?"
> **ID:** "Bagaimana Anda ingin memenuhi syarat untuk tinggal jangka panjang?"
- Options: *(a) Investing my own capital* · *(b) By achievement or global-talent credentials* · *(c) A family member already holds a Golden Visa and I'm joining them* · *(d) Long-term residence tied to property or savings, not a business* · *Not sure*
- *Why we ask*: "Each route is a different permit with different requirements and cost." / **ID:** "Setiap jalur adalah izin berbeda dengan syarat dan biaya berbeda."
- Family: E28A (individual capital) / E28B (corporate capital) / E28C (global talent) / E28D (family) / E28F (second-home/property) ⚑
- Skip / "Not sure": **human-review.** Receipt: *"Choosing how to qualify isn't something to guess — an adviser will lay out the routes against your situation."*
- Keeps/kills: each option keeps exactly its E28 sub-type family and kills the others; *Not sure* holds all for review.

**I2 — investment vehicle** *(shown if I1 = a)*
> **EN:** "Where will the capital go?"
> **ID:** "Ke mana modal akan dialamatkan?"
- Options: *Into a company I'll own or part-own in Indonesia* · *Indonesian government bonds / sukuk* · *Bank deposit or other financial instrument* · *Not sure yet*
- *Why we ask*: "The vehicle sets the permit sub-type and minimum amount." / **ID:** "Wahana investasi menentukan sub-jenis izin dan nilai minimumnya."
- Family: E28A vs E28B split ⚑
- Skip: assume *company equity*; flag for review. Receipt: *"We assumed company equity — the adviser will confirm the right vehicle."*

**I3 — amount band** *(shown if I1 = a or d)*
> **EN:** "Roughly how much are you ready to commit?"
> **ID:** "Kira-kira berapa besar komitmen yang siap Anda berikan?"
- Options: *Under USD 130k* · *USD 130k–350k* · *USD 350k–1M* · *Over USD 1M* · *Over USD 2.5M* · *Not sure* ⚑ (thresholds TBD)
- *Why we ask*: "The amount decides which tier is possible — and, honestly, whether Golden Visa is an option at all." / **ID:** "Jumlahnya menentukan tingkatan yang mungkin — dan jujur, apakah Golden Visa menjadi pilihan."
- Family: E28A/E28B/E28F threshold tiers ⚑
- Skip / "Not sure": **human-review** (never guess money). Receipt: *"We won't pick a tier without knowing your number — an adviser will match it."*
- Keeps/kills: below the lowest threshold → **NO_SUPPORTED_PATH for Golden, but the outcome page offers alternatives** (Second-Home residential, Retirement, D12 business, Remote worker). Never dead-end.

**I4 — active involvement**
> **EN:** "Will you also work in, or actively run, the company here?"
> **ID:** "Apakah Anda juga akan bekerja atau menjalankan perusahaan di sini?"
- Options: *Yes, I'll be a director / active operator* · *No, passive investor only* · *Both — I invest and I work* · *Not sure*
- *Why we ask*: "Some investor permits include limited work rights; passive investment and active management are different permits." / **ID:** "Sebagian izin investor mencakup hak kerja terbatas; investor pasif dan pengelola aktif berbeda izinnya."
- Family: investor work-rights layer ⚑
- Skip: assume **passive** (conservative — passive has fewer requirements). Receipt: *"We assumed passive investment; if you'll actively run it, the permit and fees change."*
- *Both* → adds a **work-permit layer** (RPTKA) to the candidate; keeps E28 + adds D13-class work flag.

**I5 — enhanced due-diligence gate ★** *(investor-tuned)*
> **EN:** "For investor applications we ask a few extra things. Does any apply?"
> **ID:** "Untuk permohonan investor, ada beberapa hal tambahan yang kami tanyakan. Ada yang berlaku?"
- Options (multi): *Difficulty documenting source of funds* · *I am or have been a politically exposed person (PEP)* · *Subject to sanctions screening concerns* · *Dual citizenship* · *Prior visa refusal / overstay / blacklist* · *Criminal record* · *None of these*
- *Why we ask*: "Investor permits carry enhanced background checks; some of these legally require manual review." / **ID:** "Izin investor melalui cek latar belakang ketat; sebagian wajib ditinjau manual."
- Family: EDD / PEP / sanctions / admissibility ⚑
- Skip / "prefer not to say": **conservative = human-review.** **Any non-"None" → HUMAN_REVIEW_REQUIRED.** Receipt (empathetic): *"These don't disqualify you — but they do mean a person, not a form, should handle your case."*

**I6 — duration tier**
> **EN:** "How long do you want the residence to last?"
> **ID:** "Berapa lama Anda ingin izin tinggalnya berlaku?"
- Options: *5 years* · *10 years* · *Path toward permanent (KITAP-class)* · *Not sure*
- *Why we ask*: "Golden tiers run 5 or 10 years; longer paths lead toward permanent residence." / **ID:** "Tingkatan Golden berjalan 5 atau 10 tahun; jalur lebih panjang menuju izin tetap."
- Family: E28 5/10-year tiers; ITAP/KITAP path ⚑
- Skip: assume *5 years*; keeps E28 main candidate.

**Special honesty note for I1 = d (property-backed):** this is where Bali Zero's own scar tissue (W68 — villa leasehold zoning) must surface. The confirmation card and outcome copy state plainly:

> *A residence permit tied to property does **not** give you land ownership. Foreign individuals cannot hold freehold land (hak milik) in Indonesia. You would hold leasehold (hak sewa) or another use-right. The permit and the property are two different things — do not let anyone blend them.*

This is a Bali-Zero-specific scar turned into a design feature: we are the ones who tell you the uncomfortable truth your villa broker won't.

**Modal path:** I1 → I2 → I3 → I4 → I5 → I6 = **6 questions** (fewer if I1 = b/c/d short-circuits I2). Winner: the matching E28 sub-type. Human-review fires at I3 below-threshold-with-nuance, I5 (any flag / PEP / source-of-funds), I1 = d (property → legal review of land tenure), dual citizenship.

---

### (c) Remote worker

Behavioral spine: **where is your income sourced, and are you serving the Indonesian market?** The bright line is geographic: foreign clients + foreign pay + presence in Indonesia = remote-worker tolerance; Indonesian clients or Indonesian pay = you're employed here, different lane.

**R1 — the splitter**
> **EN:** "Where are your clients or employer based?"
> **ID:** "Di mana klien atau pemberi kerja Anda berdomisili?"
- Options: *(a) All outside Indonesia* · *(b) Mostly outside, but some in Indonesia* · *(c) In Indonesia* · *(d) I work for myself / several clients*
- *Why we ask*: "If your work is aimed at the Indonesian market or paid by an Indonesian entity, you're employed here — a different permit entirely." / **ID:** "Jika pekerjaan Anda menyasar pasar Indonesia atau dibayar entitas Indonesia, Anda bekerja di sini — izin yang berbeda."
- Family: remote-work stay permit ⚑ vs D-family work
- Skip / "Not sure": **conservative = human-review** (activity boundary, do not guess). Receipt: *"Where your clients sit changes the permit — we won't assume; a person will place it."*
- Keeps/kills:
  - *(a)* → keeps remote-worker path; kills work-employment, business-no-work
  - *(b)* → keeps remote-worker path **but flags mixed → human-review** (activity boundary)
  - *(c)* → **redirect to Work & employment**
  - *(d)* → keeps remote-worker (freelancer, foreign clients)

**R2 — income floor**
> **EN:** "Roughly what's your monthly income?"
> **ID:** "Kira-kira berapa pendapatan Anda per bulan?"
- Options: *Under the remote-worker minimum* · *Above it* · *Not sure / varies* ⚑ (floor figure TBD)
- *Why we ask*: "This permit has an income floor; we'd rather tell you now than after you've paid." / **ID:** "Izin ini punya batas pendapatan minimum; lebih baik Anda tahu sekarang daripada setelah membayar."
- Family: remote-work tier income requirement ⚑
- Skip / "Not sure / varies": **human-review.** Receipt: *"We won't guess your income against the floor — an adviser will check it."*
- Keeps/kills: below floor → not killed outright but **downgraded to the lighter B211A + tolerance alternative** with an honest note; above → keeps the full remote-work permit.

**R3 — length & the tax-honesty question**
> **EN:** "How long do you want to stay — total, across visits?"
> **ID:** "Berapa lama Anda ingin tinggal — total, gabungan dari semua kunjungan?"
- Options: *Short visits, under ~60 days each* · *Up to a year* · *Longer / I plan to settle*
- *Why we ask*: "Crossing about 183 days in a year can change your tax status in Indonesia. That's not a gate — it's something you deserve to know before you choose." / **ID:** "Melebihi sekitar 183 hari dalam setahun dapat mengubah status pajak Anda di Indonesia. Itu bukan syarat — tetapi hal yang layak Anda tahu sebelum memilih."
- Family: tax-residency 183-day rule ⚑ + remote-work duration tiers
- Skip: assume *up to a year*; keeps path; receipt flags the 183-day note regardless.
- Keeps/kills: nothing killed; *Longer/settle* → adds a **tax-residency honesty block** to the outcome (foreign-sourced income treatment ⚑) — surfaced as a consequence, not a disqualifier.

**R4 — activity boundary**
> **EN:** "Beyond working on your laptop, will you do business activities here — client meetings, sales, site work?"
> **ID:** "Selain bekerja dengan laptop, apakah Anda akan melakukan aktivitas bisnis di sini — pertemuan klien, penjualan, pekerjaan lapangan?"
- Options: *No, purely remote* · *Yes, occasionally* · *Yes, regularly* · *Not sure*
- *Why we ask*: "Meetings and sales can layer in a business-permit need; pure remote work is the clean path." / **ID:** "Pertemuan dan penjualan dapat menambah kebutuhan izin bisnis; kerja murni jarak jauh adalah jalur yang bersih."
- Family: B211/D12 business layer vs pure remote ⚑
- Skip: assume **purely remote** (conservative); keeps clean path; receipt: *"We assumed purely remote work; if you'll meet clients here, a business layer may apply."*
- *Yes, regularly* or *Not sure* → **human-review** (activity boundary trigger).

**R5 — review-gate ★** (same shared gate as W4)

**R6 — family ★** (shared)

**Modal path:** R1 → R2 → R3 → R4 → R5 = **5 questions** (+ R6 if family). Winner: **remote-work stay permit** ⚑ (or the lighter B211A+tolerance alternative if income below floor). Human-review fires at R1=b (mixed clients), R4 (business activity / not sure), R5 (any flag), R3=longer (tax-residency advisory, not a block).

---

## 4. Human-review handoff moments & screen copy

**Where triggers fire (consolidated across all lanes):**

| Trigger | Typical firing point | Notes |
|---|---|---|
| Dual citizenship | Q0 clarifier or W3/passport | Always review — affects which passport, tax, and military/consular duties |
| Calling-visa nationality | passport question | Adds pre-clearance time; flagged, not blocked |
| Minors (<18) as primary or accompanying | family question | Extra consents, birth-certificate auth |
| Mixed marriage / divorce / spouse-status ambiguity | Family lane or W6 | Auth of foreign marriage/divorce docs |
| Ex-WNI / diaspora status complexity | Diaspora lane | Former-WNI has bespoke route (F-family) ⚑ |
| Overstay / refusal / blacklist history | review-gate ★ | Always review |
| Criminal record / serious health | review-gate ★ | Always review |
| Diplomatic / official passport | passport question | Separate route |
| Ambiguous sponsor | Work/Family lanes | "Who is the sponsor?" unclear |
| Activity boundary | W1-redirect, R1=b, R4 | Meetings vs work, local clients, content creation, volunteering |
| Multi-purpose trip | category screen or Q0 | "I'm both investing and working" |
| Onshore conversion | Q0 onshore branch | Bridging + conversion sequence |
| Investor PEP / sanctions / source-of-funds | I5 | Enhanced due-diligence by nature |
| "Not sure" on a load-bearing gate | any ★ splitter | Never guess on money, payer, or clients |

**The handoff screen — master template (EN):**

> **Head:** A person should look at this with you.
>
> **Body:** Based on your answers, part of your situation needs a human adviser — not because something is wrong, but because the rules around it are worth getting right the first time. That's normal, and it's most of what we do.
>
> **What we'll need from you** *(bulleted, dynamic — only the items the trigger surfaced):*
> - A scan of the passport(s) you'll travel on
> - Any documents about the flag we found *(e.g., "the prior overstay decision letter", "your marriage certificate and its authentication")*
> - A short note on what you're trying to achieve
>
> **What happens next:** An adviser reviews and comes back to you — usually within one working day. Nothing is filed in your name until you say go.
>
> **Reassurance (always present):** You're not in trouble, and you're not starting over. This conversation just moves to a person who can see the full picture.
>
> **CTA:** *Talk to an adviser*  ·  *Save my answers and come back later*

Copy rules for this screen: **no fabricated urgency** ("act now!", "limited time"), **no alarm colour beyond warm amber**, **no mention of penalties unless the user themselves surfaced an overstay** (and even then, framed as information). The word "trouble" appears only in reassurance, never in accusation.

ID divergence note: the ID version leads with the body, not the head ("Ada baiknya ada yang mendampingi Anda" / "Pantas ditinjau oleh penasihat"), because ID formal register reads headline-assertions as bureaucratic. ⚑ ID finals to be reviewed by a native speaker, not back-translated.

---

## 5. Confirmation card — content & layout before the verdict

Before any verdict, one screen collects the answers for a final honest look. This is the **honesty receipt** made visible.

**Layout (top to bottom):**

1. **"Here's what you told us"** — grouped, editable, one tap to change any answer.
   - *You & your passport* — nationality, dual status, onshore/offshore, expiry date if onshore
   - *Your purpose* — category chosen + key behavioral answers (W1/R1/I1 etc.)
   - *Your details* — duration, family, role/income as applicable
2. **Assumptions we made** (only if any skips occurred) — flagged, each with an *Edit* to supply the real answer:
   > ⚠ *You skipped "how much you'll invest" — we held this for an adviser rather than guessing a tier.*
   >
   > ⚠ *You preferred not to answer the background-check question — we treated that as "needs review", not "clear".*
3. **The honesty ledger preview** — a small two-line note that the next screen will show **official fees and agency fees separately, never blended**. Sets the expectation so the verdict's split ledger doesn't surprise.
4. **Paths remaining counter** — final number of candidate paths still alive (e.g., "3 paths still fit your answers"). If it's 1, the next screen is the single-winner verdict; if 0, it's the no-path-but-not-dead-end screen.
5. **CTA:** *See my options* (primary) · *Edit an answer* (secondary)

Design rule: **every assumption is editable in one tap and written in plain language**, because the whole trust model collapses if a hidden assumption drives the verdict. This is the skip-with-assumptions honesty receipt from Round 1, given a concrete home.

---

## 6. Outcome page copy skeletons

### SUPPORTED_CANDIDATES — single winner

> **Head:** One path fits your answers clearly.
>
> **Verdict tile:** **[Visa name + code ⚑]** — *[stay duration]*
> *One-line plain-language description of what this permit lets you do.*
>
> **What it gives you** (3–4 bullets): rights, duration, renewability, work rights (or explicit "no work rights").
>
> **What it doesn't** (1–2 bullets, honesty): e.g., "Does not give land ownership", "Does not let you be paid by an Indonesian employer".
>
> **Honest ledger:**
> - Official government fees: **IDR / USD [range ⚑]** — *goes to the state*
> - Bali Zero service fee: **[range]** — *goes to us*
> - *(these are never combined into one number)*
> - Plus anything you must arrange yourself *(e.g., investment capital, medical, documents)*
>
> **What you'll need** (document checklist, honest about authentication/apostille where relevant).
>
> **Timeline ⚑** and **renewal path.**
>
> **CTA:** *Start this application with us* · *Download my answers as a PDF* · *See why other paths didn't fit*

### SUPPORTED_CANDIDATES — 2–3 trade-offs

> **Head:** A few paths fit. Here's how they actually differ.
>
> **Three verdict tiles**, each compact (name, one-line, duration, total-from ledger, one "best for" tag): *Best for shortest setup* · *Best for longest stay* · *Best for lowest cost*.
>
> **A short trade-off table** — not a fake ranking, just the axes that matter (cost, duration, work rights, renewal, lead time) so the user compares on facts.
>
> **No "recommended" badge unless the engine has a real, stated reason** (e.g., "the only one your income qualifies for"). If there's no factual basis, we say *"Any of these works — choose by what matters most to you."*
>
> **CTA per tile:** *Start [name]* · top: *Compare side by side* · *Talk it through with an adviser*

### HUMAN_REVIEW_REQUIRED

(See Section 4 master template. Verdict tile replaced by the handoff. No fees shown — premature.)

### NO_SUPPORTED_PATH — never dead-end

> **Head:** None of the standard paths fit your answers — and that's useful to know before you spend anything.
>
> **Body:** Based on what you told us, the visas we cover don't line up cleanly. That's not a verdict on you; it usually means one of three things.
>
> **Three "what instead" blocks:**
> 1. *You might fit a different category.* *(links back to the category screen with the closest alternatives pre-highlighted)*
> 2. *Your situation has a detail that needs a human.* *(→ human-review intake)*
> 3. *The rule you're hoping for may not exist the way it's sometimes described.* *(an honest reality-check paragraph — e.g., "There is no general 'digital nomad pays no tax' rule; what exists is a specific permit with specific conditions.")*
>
> **Reassurance:** You haven't wasted this — your answers are saved, and an adviser can often find a path the tool can't.
>
> **CTA:** *Talk to an adviser* · *Revisit my answers* · *Browse all categories anyway*

The forbidden pattern: a dead-end page with only "no results." Every NO_SUPPORTED_PATH screen must offer at least one forward action.

### TEMPORARILY_UNAVAILABLE — regulation just changed

> **Head:** The rules around this just changed — we're updating, not guessing.
>
> **Body:** Indonesian immigration regulations for **[area ⚑]** were updated recently. Rather than give you advice that might already be out of date, we've paused this path in the tool while we confirm the new requirements.
>
> **What you can do:** an adviser already tracking this change can give you a current answer — usually the same day.
>
> **CTA:** *Get a current answer from an adviser* · *Save my answers — notify me when this path is back*
>
> *(No invented dates, no "coming soon" theatre. If we don't know when, we say so.)*

ID divergence: outcome heads in ID favour the affirmative body line over the headline ("Ada satu jalur yang pas" reads warmer than a bald "Hasil: E28A"). ⚑ native review.

---

## 7. Microcopy register guide — 10 rules

Warmth without gamification; authority without bureaucratese. Each rule: principle → ✗ bad → ✓ good (EN / ID).

**1. Name the person's situation, not the permit code.**
✗ "You qualify for E28A."
✓ "You can stay long-term by investing your own capital." / *"Anda bisa tinggal jangka panjang dengan menanamkan modal sendiri."*
Permit codes appear only as small secondary labels, never as the headline.

**2. Tell them what a permit does *and* what it doesn't.**
✗ "This visa lets you live in Indonesia."
✓ "This visa lets you stay up to 5 years. It does not give you the right to work for an Indonesian employer, or to own land." / *"Izin ini berlaku hingga 5 tahun. Tidak memberi hak bekerja untuk pemberi kerja Indonesia, dan tidak memberi hak milik atas tanah."*

**3. Never blend fees. Always split official from agency.**
✗ "Total cost: IDR 15,000,000."
✓ "Official fee IDR 12,000,000 (to the state) + Bali Zero fee IDR 3,000,000 (to us)." / *"Biaya resmi Rp 12.000.000 (untuk negara) + biaya layanan Bali Zero Rp 3.000.000 (untuk kami)."*

**4. Make "I don't know" a first-class answer, and reward it with honesty.**
✗ *(required field, no skip)*
✓ "Not sure? That's fine — we'll hold this for an adviser rather than guess." / *"Belum yakin? Tidak apa-apa — kami simpan untuk penasihat, bukan menebak."*

**5. Explain consequences, never threaten penalties.**
✗ "Overstaying incurs a fine of IDR 1,000,000/day — act now!"
✓ "If you stay past your permit's expiry, a daily fee applies by law. Overstay is fixable; an adviser can sort it with you." / *"Jika melebihi masa berlaku izin, berlaku biaya harian menurut undang-undang. Ini bisa diselesaikan; penasihat akan membantu."*

**6. Use plain verbs. Avoid "application", "applicant", "facility" where "apply / you / permit" work.**
✗ "Applicant must submit the facility application."
✓ "To apply, you'll send us these documents." / *"Untuk mengajukan, Anda mengirimkan dokumen berikut kepada kami."*

**7. No gamification language — no scores, badges, "you're 80% there", progress bars dressed as achievement.**
✗ "Great job! You're 80% to your visa! 🎉"
✓ "Three questions left." / *"Tiga pertanyaan lagi."*
The paths-remaining counter is a fact, not a celebration.

**8. Reassure before you redirect.**
✗ "You don't qualify. Pick another category."
✓ "This path doesn't fit your answers — but another might. Let's look together." / *"Jalur ini tidak cocok dengan jawaban Anda — tetapi mungkin yang lain. Mari kita lihat bersama."*

**9. When the regulation is unclear or changing, say that — don't paper over it.**
✗ "This is always allowed."
✓ "The rule here was updated recently; we'd rather an adviser confirm than risk out-of-date advice." / *"Aturan ini baru berubah; penasihat kami konfirmasikan agar tidak menyesatkan."*

**10. Address the reader directly and warmly, in semi-formal register — not stiff, not slang.**
✗ "The user is advised that…" / *"Pemohon diharapkan…"*
✓ "Here's what we'd suggest for you." / *"Ini yang kami sarankan untuk Anda."*
(Use *Anda*, never *kamu*, in this government-adjacent context; avoid the bureaucratic passive entirely in ID.)

---

## Handoff notes

- **One grounding pass needed before content finals:** every ⚑ — exact visa codes (post-2024-reform D/E/F lettering), income floor for remote work, Golden Visa thresholds, VOA/B211 extension mechanics, Bridging Visa mechanics, 183-day tax rule treatment — should be confirmed against **NB-INTEL Immigration** (80 sources) via a `wr2-brief-interpreter`-style query. I deliberately did not assert those as facts.
- **Bali-Zero texture already embedded:** the W68 villa-leasehold honesty note (Section 3b) turns a real scar into a design feature — we are the ones who refuse to blend "permit" and "property ownership." That's a brand differentiator worth keeping loud.
- **The shared review-gate ★ (W4/R5) and family ★ (W6/R6) questions are identical across lanes** — build them once, compose them in. That keeps the engine honest and the content team's surface area small.

Want me to (a) run the NB-INTEL grounding pass on the ⚑ items and return a verified appendix, (b) draft the same full tree for the next three categories (Family & marriage, Retirement & second home, Diaspora & ex-WNI), or (c) save this as a research capture under `research/visa/`?
