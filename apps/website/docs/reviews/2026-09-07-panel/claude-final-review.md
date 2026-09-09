# Final Claude review — adjudication still applies

**Capture caveat:** I viewed a 1440×8632 full-page PNG downscaled ~4.3×. Body copy, nav labels, captions, dates and button labels are **unreadable** at that scale. Everything below concerns composition, colour, density and hierarchy only — not wording.

## 1. What the render actually shows

**Strengths.** The two full-bleed photographic bands carry the identity: the E-VOA ocean band is the best composition on the page — dark teal, one headline, one pale button, one host card, nothing competing. The Second Home book diorama holds its own framed field with a caption and reads sculptural rather than decorative. The Journal masthead with flanking rules, and the 3-column magazine grid beneath it, are the most confident typography here. Host cards recur in the same corner position across E-VOA, Second Home and the team lead-in — a real pattern. Section grounds already alternate (photo → white → photo → cream → white → greige → cream → white → footer).

**Weaknesses.** The four service cards each carry a *different* saturated accent — blue, green, red, green — plus coloured eyebrows. It is the only place the cream/forest/terracotta system breaks, and it is the second thing a visitor sees. Each card stacks two full-width buttons plus a text link: twelve actions in one row, reading as a control panel rather than a chooser. The Reviews section's largest element is a cut-out portrait on white; at this scale I see no quote, stars or review text — social proof is *depicted*, not shown. The portal mock is a grey wireframe, the lowest-fidelity artwork on a page of commissioned imagery. Deep forest appears only in buttons and the footer; there is no forest field. The hero chooser appears to be four select-like fields in 2×2 plus a button — a two-step commitment above the fold (control type not confirmable at this scale). No floating assistant is visible, but full-page captures routinely drop fixed elements, so I cannot confirm the FAB either way.

## 2. Corrections to my first review

- **P0 "no contact path" — withdrawn.** Hero `#contact`, per-card WhatsApp and section hosts exist; the render shows contact entries in hero, cards, the "not sure who to speak to?" band and the closing panel. A header CTA is an experiment, not a defect.
- **"Journal exports traffic" — withdrawn as framed.** Same apex is planned; absolute URLs prove nothing. The real defect is the production finding: `/journal` is a HTTP 200 soft-404 while `/news` is the canonical index.
- **Pricing P0 — downgraded.** Absent prices are not P0; I invent none.
- **Portal "under-claims" — I over-corrected.** Source holds real workflows; only the public login was tested, absence was not. Verified outcomes may be stated after a product check; stop repeating implementation disclaimers.
- **"Visa Oracle over-claims" — narrowed.** No rename; add an outcome label. `/visa/clock` is a verified after-arrival utility.
- **"Rhythm over uniformity" — partly wrong.** Alternation already exists; the gap is one forest field, not more variety.
- **Gemini first pass — rejected wholesale:** uplift hypotheses, nationality=language, arrivals=leads, the Article 31 criminal claim, and "disclaimer mitigates risk". Nothing from it is carried forward.

## 3. Five ranked changes

1. **One primary action per service card**, tool link demoted to a text line, WhatsApp tertiary. *Test:* first-click study, 8 participants, two tasks ("set up a company", "check if my stay can be extended"); record first-click target and time-to-first-click; <6/8 correct = fail. Separately audit every remaining link against WCAG 2.4.4 — purpose discernible **in context**, no bare "Explore".
2. **Unify card accents to forest**, terracotta reserved for exactly one primary action per section; differentiate cards by illustration tint only. *Test:* automated palette audit — distinct accent hues outside photography ≤3; plus 5-second exposure recall of "what kind of things are in that row".
3. **Fix the `/journal` soft-404** while keeping the "Journal" label over `/news`. *Test:* crawl asserting one 200 index, zero soft-404s, and `/articles`, `/kbli`, `/visa/clock` still 200; monitor 404-page hits weekly.
4. **Decide one persistent surface** — Zantara FAB *or* a header CTA, never both. *Test:* GOV.UK completion-rate method — count actual starts and completions of the contact transaction; run the QA-001 collision check at 360/768/1440.
5. **Show evidence in Reviews**: one real quote, attribution and rating in-page; Google link secondary. *Test:* clicks-off-site and scroll-past rate before/after, plus 5 qualitative sessions asking what participants recall about other clients.

## 4. Ecosystem placement

**Home:** the renewal/extension moment (one line in E-VOA, "already here?"), an existing-client fast lane, and `/visa/clock` named as an after-arrival utility.
**Service pages:** KITAS/KITAP renewal, dependants, RPTKA; post-incorporation NIB→licence sequencing, capital and domicile; LKPM, annual reporting, payroll/BPJS, SPT; property structures and due diligence; and the entire exit stage — closure, cancellation, de-registration, sale — currently absent everywhere.
**Nowhere public:** the raw pricing endpoint, portal internals, destination/evidence registries, dev fixtures, the blocked Telegram handle, and any internal ecosystem inventory.