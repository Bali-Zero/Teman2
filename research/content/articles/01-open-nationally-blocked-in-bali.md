---
date: 2026-06-21
domain: compliance
client_case: none
kbli_codes:
  - "55203 — Aktivitas Vila — National: TERBUKA 100% — Bali: CHIUSO_PMA_NO_BESAR (blocked)"
status: published-draft
adversarial_review: codex
---
# Your KBLI Is Open Nationally — and Blocked in Bali

There is a specific kind of silence that falls over a Seminyak consulting office the moment a foreigner discovers the gap. They arrive with a printout. The printout is correct. The national investment list says, in plain ink, that their chosen business is one hundred percent open to foreign ownership. And then the consultant offers the apologetic half-smile that veterans of this island have learned to dread, and explains that the printout is the beginning of due diligence, not the end of it.

Welcome to the single most expensive misunderstanding in Indonesian business: **national-open is not the same as Bali-registrable.**

## What actually happened on 13 May 2026

On that date, the Bali provincial government enacted a sweeping block — Governor letter **B.27.000/642/PM/DPMPTSP** — that froze new PMA (foreign-owned company) registration for any business activity the national OSS system classifies as **"low" or "medium-low" risk**, island-wide. The stated goals are familiar to anyone who has watched the island's last decade: slow the explosion of foreign micro-businesses, manage runaway development, and preserve economic room for Balinese families.

The mechanism is brutally simple. When you input a Bali address into the OSS portal for a low-risk KBLI code as a PMA, the system physically refuses the application. The computer says no. There is no appeal window at the counter, no "we'll make an exception." It is a structural wall, not a discretionary one.

And the trapdoor underneath it: you **cannot** register the PMA at a virtual office in Jakarta to dodge the Bali rule. Virtual offices are now banned as a PMA domicile here. The moratorium assumes a genuine, verifiable Bali presence — which is exactly the presence that triggers the block.

## The number nobody wants to print

When you run the full 2025 classification through this filter, the result is stark: a large minority of Bali-relevant business codes — on the order of **four in ten** — are now closed to new foreign investment, not because the national law forbids them, but because the provincial risk-class filter does.

The villa code is the textbook case. **KBLI 55203 (Aktivitas Vila)** is `TERBUKA` — 100% open — on the national list. In Bali, it is blocked. (The precise mechanism is a touch more elegant than "low-risk": Annex II of Perpres 10/2021, as amended by 49/2021, allocates the _Vila_ line of business to cooperatives and MSMEs, and a reserved _bidang usaha_ is closed to a PT PMA at any scale, anywhere in Indonesia — the annex is a national instrument, not a Bali rule. The outcome for the foreigner is identical: you cannot register it.)

This is the pattern, repeated across hospitality, food and beverage, retail, real estate, and creative services. The national door is open. The provincial door is locked. They are different doors.

## Why the old blogs will hurt you

Indonesia has decentralised aggressively over two decades. A provincial governor's decree can neutralise a national mandate on the ground — and it does not appear in bold red letters on the national investment portals that the English-language expat blogs quote. Those blogs were written before 13 May 2026. They describe a world that no longer exists. Following them is how confident, well-capitalised people sign a 25-year land lease for a business they will never be permitted to operate.

The honest map looks like this:

- **Verify nationally first** — is the code open to PMA at all? (Many are.)
- **Then verify the Bali risk-class status** — is the activity low/medium-low risk, or reserved-for-UMKM? If so, it is blocked here regardless of the national answer.
- **Then verify the pivot** — is there a higher-risk sibling code (apart-hotel, intermediation, IT-services, bar) that survives the filter and still gets you most of what you wanted?

There is almost always a pivot. The villa dreamer becomes an apart-hotel (55204) or a management company (55400). The café becomes a bar (56301). The discretionary cost is capital and compliance, not the dream itself.

The point of this whole series is to walk you, code by verified code, from the national fantasy to the provincial reality — using ground-truth 2025 classification data, never a five-year-old forum post.

_Before you wire a deposit or sign a lease, check the live Bali status of your exact KBLI code on the Bali Zero KBLI Navigator at balizero.com — the two-branch view shows you the national status and the Bali status side by side, so the gap can never surprise you._

## Adversarial review

- Seat: Codex `gpt-5.6-sol` (reasoning xhigh), refute stance, cross-family — reviewed the
  2026-08-12 retraction-cure diff touching this file, verified against
  `KBLI_2025_FINAL_CLEAN.json` (the cured dataset).
- Outcome: FIX-FIRST → fixed in this same PR. 10 findings (9 confirmed/accommodated, 1 HOLDS): 96220 national status corrected to TERBATAS 0% (measured); 55201/55203 restated as the same Annex II entry 48 (sub-rows *Pondok Wisata* / *Vila*); the annex stated as a national instrument (articles 01/02); honest-map wording corrected (33.2% = almost exactly one in three; all but FOUR of the 372 nationally open; 1,041 = "not blocked", not "open"); surf-coliving guest-house-scope reading stated as OSS's call, not the founder's certainty; stale ID fact-sheet row (55203 "tanpa Besar") cured. Every fix re-measured against KBLI_2025_FINAL_CLEAN.json before applying.
- Note: this section and the `adversarial_review` frontmatter key are R1-gate metadata;
  the book/PDF composer strips the frontmatter block and this section from rendered output.
