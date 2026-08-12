---
date: 2026-06-21
domain: compliance
client_case: none
kbli_codes:
  - "55203 — Aktivitas Vila — National: TERBUKA 100% — Bali: CHIUSO_PMA_NO_BESAR (blocked)"
  - "55204 — Aktivitas Apartemen Hotel — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
  - "55400 — Aktivitas Jasa Intermediasi Akomodasi — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
status: published-draft
adversarial_review: codex
---
# The Villa Dream Has a New Wall (KBLI 55203)

Everyone arrives with the same Pinterest board. Reclaimed teak pillars, polished concrete, an infinity pool catching the bruised-purple Pererenan sky, and somewhere in the spreadsheet, a line that reads _passive income._ The villa is the island's most seductive business plan because it doesn't feel like a business — it feels like buying your way into a life.

And the national law agrees with you. **KBLI 55203 — Aktivitas Vila** — is listed as `TERBUKA`, one hundred percent open to foreign ownership. So you set up the PMA, lease the land, and start construction next month. Right?

Not in Bali. Not anymore.

## The wall, precisely

KBLI 55203 covers short-term accommodation in private homes rented to tourists and managed by the owner — the classic boutique villa. On the national investment list it is wide open to a PMA. But when you try to register a PT PMA against 55203 with a Bali address, the OSS system has no path for you.

The reason is worth understanding, because it is _not_ simply "low-risk moratorium" in this case. The villa business is **explicitly reserved**: Annex II of Perpres 10/2021, as amended by Perpres 49/2021, lists _Vila_ among the lines of business allocated to cooperatives and MSMEs (p.15, entry 48, against the 2020 code 55193, ticked _dialokasikan_). A reserved _bidang usaha_ is not open to a PT PMA at any scale, so there is nothing to register against. The wall is the same height whether it is the risk-class moratorium or an annex reservation — with one difference worth knowing: the annex is a national instrument, so **a foreign-owned company cannot register a villa in Bali or anywhere else in Indonesia.**

One footnote that saves grief: 55203 was renumbered from the old 2020 code **55193**. If a contract, an old quote, or a forum post still says 55193, it's describing the same activity — and the same wall.

## The pivots that actually clear the filter

Here is the part the doom-scrolling expat groups miss. The villa dream doesn't die at the wall — it has to _change shape_. Two sibling codes survive the moratorium because the OSS system classifies them as **medium-high or high risk**, which lifts them out of the blocked bucket entirely:

- **55204 — Aktivitas Apartemen Hotel (Apart-Hotel).** National: open. Bali: **REGISTRABLE.** Because the apart-hotel model carries a higher risk class (medium-high/high at large scale), it clears the filter. The trade-off is real — you are now licensing a commercial accommodation facility, not a private home, so the building permit (PBG), environmental requirements, and capital all step up. But the door is open. You must still verify zoning (ITR) for the exact parcel.

- **55400 — Aktivitas Jasa Intermediasi Akomodasi (Accommodation Intermediation).** National: open. Bali: **REGISTRABLE.** Under this code you are the management or booking company — you operate, market, and manage accommodation owned by others, rather than owning the physical villa yourself as a foreigner. For many investors this is the cleaner play: it keeps the foreign capital in the operating company and the land risk with local owners.

There is a third route that lives outside Bali entirely: register the 55203 PMA in a province where the moratorium doesn't apply (Jakarta, Lombok, elsewhere) and accept that the operating asset cannot legally be a Bali villa under that company. Useful for some structures, useless for the person who specifically wants a Seseh villa. Be honest with yourself about which one you are.

## The reality the pivot buys you

A pivot to 55204 or 55400 is not a downgrade — it's a different, more capital-intensive, more compliant business. The commercial-build timeline from land lease to first paying guest runs closer to a year-and-a-half than to six months once you're in apart-hotel territory, and the "Bali tax" (notary fees, PBG, banjar contributions for road access, ceremony budget) is real overhead, not a footnote. We deal in ranges here because Bali numbers are as fleeting as the tide — but the order of magnitude is "a serious commercial project," not "a side hustle that pays for surfing."

What the pivot really buys you is the right to exist legally. The graveyard of Bali investments is full of people who wired the money against 55203, signed the 30-year lease, and only then learned the OSS system would never let them open the doors.

_Run 55203, 55204, and 55400 through the Bali Zero KBLI Navigator at balizero.com before you commit a rupiah — the two-branch view shows national-open vs Bali-registrable side by side, so you choose the pivot before you sign the lease, not after._

## Adversarial review

- Seat: Codex `gpt-5.6-sol` (reasoning xhigh), refute stance, cross-family — reviewed the
  2026-08-12 retraction-cure diff touching this file, verified against
  `KBLI_2025_FINAL_CLEAN.json` (the cured dataset).
- Outcome: FIX-FIRST → fixed in this same PR. 10 findings (9 confirmed/accommodated, 1 HOLDS): 96220 national status corrected to TERBATAS 0% (measured); 55201/55203 restated as the same Annex II entry 48 (sub-rows *Pondok Wisata* / *Vila*); the annex stated as a national instrument (articles 01/02); honest-map wording corrected (33.2% = almost exactly one in three; all but FOUR of the 372 nationally open; 1,041 = "not blocked", not "open"); surf-coliving guest-house-scope reading stated as OSS's call, not the founder's certainty; stale ID fact-sheet row (55203 "tanpa Besar") cured. Every fix re-measured against KBLI_2025_FINAL_CLEAN.json before applying.
- Note: this section and the `adversarial_review` frontmatter key are R1-gate metadata;
  the book/PDF composer strips the frontmatter block and this section from rendered output.
