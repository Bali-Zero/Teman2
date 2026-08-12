---
date: 2026-06-21
domain: compliance
client_case: none
kbli_codes:
  - "86105 — Aktivitas Klinik Swasta (Private clinic) — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
  - "96220 — Aktivitas Perawatan Kecantikan dan Perawatan Kecantikan Lainnya (Beauty care) — National: TERBATAS (0% foreign) — Bali: CHIUSO_PMA_NO_BESAR (blocked — allocated to cooperatives/MSMEs: Perpres 10/2021 as amended by 49/2021, Annex II p.16 entry 57, salon kecantikan)"
  - "96230 — Aktivitas SPA (Sante Par Aqua) — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable — risk class clears the moratorium)"
status: published-draft
adversarial_review: codex
---
# Wellness & Aesthetics: One of the Open Doors — and a Hidden Wall (86105 vs 96220)

After eight articles of walls, here is some relief: in the wellness and medical-aesthetics space, Bali still has a door that's genuinely open to foreign capital. But — because this is Bali, and nothing is allowed to be simple — the open door and the closed wall sit _right next to each other_, separated by what looks like a hair's breadth and is in fact a chasm. The clinic is open. The beauty salon is blocked. Knowing which side of the line your business lands on is the entire game.

## 86105: the clinic is registrable

**KBLI 86105 — Aktivitas Klinik Swasta** (private clinic) covers the provision of primary and/or advanced health services — outpatient and/or inpatient care — run by private providers. It is the code for a medically-supervised operation: a clinic with doctors, a wellness-and-recovery centre with clinical oversight, a medical-aesthetics practice operating under a physician.

National: open. Bali: **REGISTRABLE.** Its risk class at large scale runs medium-high to high — which is exactly what you'd expect from an activity involving medical care and patient safety — and that higher risk class is precisely what lifts it clear of the May 2026 moratorium. It's also a stable, unchanged code (a direct match from KBLI 2020), so older references to 86105 are still accurate. The licensing is heavier — health-sector permits, facility standards, medical-personnel requirements — but those are the requirements that _make it registrable_. The friction is the feature.

This is the optimistic mirror-image of the moratorium's logic. Everywhere else in this series, "higher risk" sounds like a burden. In health, the higher risk class is the thing that keeps the door open to a foreign-owned PMA.

## 96220: the beauty salon is blocked

Now the wall, and it's a surprising one. **KBLI 96220 — Aktivitas Perawatan Kecantikan dan Perawatan Kecantikan Lainnya** (beauty care and other beauty treatments) covers beauty treatments **not performed by a specialist physician** — the work of a cosmetologist: facials, beauty-focused treatments, the classic aesthetics-salon offering. It's a brand-new 2025 code (in 2020 this was lumped into broader personal-service codes; the 2025 system breaks beauty out on its own).

National: **closed to foreign ownership** — the catalogue lists 96220 as TERBATAS at 0%, the annex allocation carried into the national list itself. Bali: **BLOCKED** — and the basis is an explicit reservation, not a missing registration row. Perpres 10/2021, as amended by Perpres 49/2021, allocates _salon kecantikan_ to cooperatives and MSMEs in its Annex II (p.16, entry 57, against KBLI 96112, ticked _dialokasikan_). A PT PMA cannot take a reserved _bidang usaha_, so a foreign-owned beauty salon or aesthetics studio operating under 96220 cannot be registered here.

**The reservation does not reach the spa.** Sante Par Aqua (SPA), sauna and steam-bath services are their own 2025 code — **96230** — and it is not blocked in Bali: its risk class is high enough to clear the moratorium. Read the scopes before you file, because OSS writes them narrowly: the large-scale (Besar) row for 96230 is scoped to _spa operations already tending toward medical spa_, and the micro-to-medium rows cover everything except that. Verify your exact scope against OSS for the treatments you actually intend to offer.

So the line that decides everything is **not** clinical-versus-cosmetic — it is which code your activity actually falls under. The Annex II reservation is written against named lines of business (_salon kecantikan_, _pangkas rambut_), not against cosmetic work as a category, which is why 96230 stays open while 96220 does not. On the open side: the private clinic (86105) and the spa (96230). On the closed side: the cosmetologist's salon (96220). To the customer walking in for a "glow-up facial," the businesses look nearly identical. To the OSS system, they are different verdicts.

## How to land on the right side of the line

The strategic move for a foreign investor in this space is to build the business with a genuine **clinical spine** and register it under **86105**, rather than as a pure beauty salon under the blocked 96220. That's not a labelling trick — substance-based inspection is now the norm, and a "clinic" with no medical supervision is a 96220 wearing a lab coat. It means actually structuring around medical oversight: the right personnel, the right permits, the right facility standards. Do that, and you have one of the few foreign-friendly doors left open in Bali. Skip it and register the bare beauty-care code, and the OSS system simply won't let your PMA through.

The wellness sector, in short, rewards the operator who builds the heavier, more clinical, more regulated version of the business — and quietly shuts out the lighter cosmetic one. Same customer, same glow, completely different legal fate.

_Check 86105, 96220 and 96230 side by side on the Bali Zero KBLI Navigator at balizero.com — the two-branch national-vs-Bali view shows you which side of the Annex II reservation your exact code falls on, and whether your wellness business is an open door or a hidden wall._

## Adversarial review

- Seat: Codex `gpt-5.6-sol` (reasoning xhigh), refute stance, cross-family — reviewed the
  2026-08-12 retraction-cure diff touching this file, verified against
  `KBLI_2025_FINAL_CLEAN.json` (the cured dataset).
- Outcome: FIX-FIRST → fixed in this same PR. 10 findings (9 confirmed/accommodated, 1 HOLDS): 96220 national status corrected to TERBATAS 0% (measured); 55201/55203 restated as the same Annex II entry 48 (sub-rows *Pondok Wisata* / *Vila*); the annex stated as a national instrument (articles 01/02); honest-map wording corrected (33.2% = almost exactly one in three; all but FOUR of the 372 nationally open; 1,041 = "not blocked", not "open"); surf-coliving guest-house-scope reading stated as OSS's call, not the founder's certainty; stale ID fact-sheet row (55203 "tanpa Besar") cured. Every fix re-measured against KBLI_2025_FINAL_CLEAN.json before applying.
- Note: this section and the `adversarial_review` frontmatter key are R1-gate metadata;
  the book/PDF composer strips the frontmatter block and this section from rendered output.
