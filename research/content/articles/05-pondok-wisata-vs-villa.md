---
date: 2026-06-21
domain: compliance
client_case: none
kbli_codes:
  - "55201 — Aktivitas Rumah Tinggal Sewa (Homestay / Pondok Wisata) — National: TERBUKA 100% — Bali: CHIUSO_PMA_NO_BESAR (blocked — allocated to cooperatives/MSMEs, Perpres 10/2021 as amended by 49/2021, Annex II)"
  - "55203 — Aktivitas Vila — National: TERBUKA 100% — Bali: CHIUSO_PMA_NO_BESAR (blocked)"
  - "55204 — Aktivitas Apartemen Hotel — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
status: published-draft
adversarial_review: codex
---
# Pondok Wisata vs Villa: Why Foreigners Can't Own the Cheap One

Walk through any conversation about Bali accommodation and you'll hear the word _pondok wisata_ tossed around as if it were the budget-friendly cousin of the villa — same idea, smaller, cheaper, lighter paperwork. That framing is half right and entirely dangerous. The pondok wisata is indeed the smaller, cheaper, more local model. It is also the one a foreigner is _most_ completely shut out of. Understanding why is one of the cleanest lessons in how Bali property actually works.

## Two codes, two different kinds of "no"

Both of these codes read `TERBUKA` — 100% open — on the national investment list. Both are closed to a foreign-owned company — and by the *same* line of the same annex: entry 48 of Annex II, Perpres 10/2021 as amended by 49/2021, which allocates traditional lodging to cooperatives and MSMEs. What differs is the sub-row each code falls under, and what that means for the business model.

- **55201 — Aktivitas Rumah Tinggal Sewa (Homestay / Pondok Wisata).** The code covers short-term accommodation, rented daily or weekly, in a residential building **that the owner lives in.** Bali status: **blocked** — the annex's *Pondok Wisata* sub-row of entry 48 (against the 2020 code 55130) is allocated to cooperatives and MSMEs, and the traditional Bali rules add an owner-resident model with a small room cap. It is, by design, a livelihood for a Balinese family living on their own land — not an investment vehicle.

- **55203 — Aktivitas Vila.** The boutique villa. Bali status: **blocked** — the *Vila* sub-row of the same entry 48 (against the 2020 code 55193): a PT PMA cannot take a reserved _bidang usaha_ at any scale.

So: villa and pondok wisata fall on the same reserved line, and neither offers a door a foreign company can fit through. The pondok wisata is further from reach in practice — the owner-resident, family-run model is the very thing the reservation protects.

## Why the "cheap one" is the forbidden one

The instinct — "if the villa is hard, I'll just do the smaller homestay version" — runs exactly backwards. The pondok wisata is reserved _because_ it's the small, local, owner-occupied model. The entire policy logic of the May 2026 moratorium and the surrounding investment rules is to keep the low-end, easy-entry, livelihood-scale accommodation business in Balinese hands. The cheaper and more local the model, the more firmly it is fenced off from foreign capital.

There is a hard edge to this you must respect: the classic foreigner's "solution" — putting the pondok wisata in a local nominee's name and operating it behind the scenes — has moved from grey-area risk to **criminal** territory under Bali's recent nominee crackdown. The catalogue may say the activity is nationally "open," but the local rules close it to you, and the workaround is the kind that ends careers and capital, not the kind that gets quietly tolerated. Do not build a plan on it.

## The one that actually lets a foreigner in

If you genuinely want to own and operate accommodation as a foreigner in Bali, the small-and-local codes are not your road. The road is the **higher-risk, higher-capital** sibling:

- **55204 — Aktivitas Apartemen Hotel (Apart-Hotel).** National: open. Bali: **REGISTRABLE.** Its medium-high/high risk class lifts it clear of the moratorium. The cost is real — it's a commercial facility with a heavier building permit (PBG), environmental requirements, and capital deployment, and you must verify zoning (ITR) per exact parcel — but it's a door your foreign company can legally walk through.

The mental model to carry away: in Bali accommodation, **legality scales with capital and risk class, not down.** The smaller and cheaper the model, the more likely it is reserved for locals. The foreigner's legitimate path is up-market — apart-hotel, intermediation, genuine commercial scale — not the cosy little homestay that looked like the easy way in.

_See 55201, 55203, and 55204 mapped side by side — national status vs Bali status — on the Bali Zero KBLI Navigator at balizero.com, so you can tell the reserved-for-locals codes from the ones a foreigner can actually register before you fall for the "cheap one."_

## Adversarial review

- Seat: Codex `gpt-5.6-sol` (reasoning xhigh), refute stance, cross-family — reviewed the
  2026-08-12 retraction-cure diff touching this file, verified against
  `KBLI_2025_FINAL_CLEAN.json` (the cured dataset).
- Outcome: FIX-FIRST → fixed in this same PR. 10 findings (9 confirmed/accommodated, 1 HOLDS): 96220 national status corrected to TERBATAS 0% (measured); 55201/55203 restated as the same Annex II entry 48 (sub-rows *Pondok Wisata* / *Vila*); the annex stated as a national instrument (articles 01/02); honest-map wording corrected (33.2% = almost exactly one in three; all but FOUR of the 372 nationally open; 1,041 = "not blocked", not "open"); surf-coliving guest-house-scope reading stated as OSS's call, not the founder's certainty; stale ID fact-sheet row (55203 "tanpa Besar") cured. Every fix re-measured against KBLI_2025_FINAL_CLEAN.json before applying.
- Note: this section and the `adversarial_review` frontmatter key are R1-gate metadata;
  the book/PDF composer strips the frontmatter block and this section from rendered output.
