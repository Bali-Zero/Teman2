---
lane: L04 — How a price is displayed
seat: Claude Opus 5 (claude-opus-5[1m]), effort xhigh
date: 2026-08-31
sources_verified_live: 24
sources_from_memory: 8
---

## Executive summary

1. The research does **not** say all-inclusive pricing converts better. It says the opposite is true for the *seller who splits*: partitioned prices make buyers **underestimate the total** (Robbert & Roth 2014). Bali Zero's honest number is a real commercial handicap and the design has to pay for it deliberately — not assume virtue is legible.
2. The best-drafted description of "honest" anywhere in 2026 is the FTC's Rule on Unfair or Deceptive Fees (16 CFR Part 464, in force 12 May 2025). Its operative sentence is not "never itemise" — it is **"itemization must not overshadow the total price"**. That converts Bali Zero's policy into a *typographic ratio*, which is testable.
3. The single strongest device found live is Wise's: the fee line exists, and its value is the word **"Included in IDR amount"** — not a number to add. Copy the grammar, not the layout.
4. `Intl.NumberFormat('id-ID', {currency:'IDR'})` emits `Rp 790.000` — a non-breaking space Indonesian house style does not use, and a `.` that an English reader parses as a decimal point. **Never ship one formatter for both locales.** Verified by running it today.
5. The 790.000 / 850.000 pair is a **sequence in time**, not a tier menu. Render it as a timeline. Any "Basic vs Pro" card table invents a choice the buyer does not have yet, and that is where the dark-pattern line sits.

---

## Finding 1 — The total must be the last thing the eye touches before the button, and it must be in the same box

**Named example.** Wise's transfer calculator (`https://wise.com/gb/send-money/`, VERIFIED-LIVE fetched 2026-08-31). The card is a single bounding box containing, in order: `You send exactly` → `Total fees and taxes / Included in IDR amount` → `Recipient gets` → `Arrives / Today – in seconds` → the CTA. There is no point in the flow where the operative number is off-screen from the button.

**The measurable rule.** Baymard's benchmark (`https://baymard.com/blog/mobile-ecommerce-checkout-forms`, VERIFIED-LIVE): *"33% of the benchmarked mobile sites fail to display the total order cost – at any point during checkout – before asking for credit card data."* Their payment-UX guideline (`https://baymard.com/learn/payment-ux`, VERIFIED-LIVE) states it as a hard requirement: *"The complete order total — inclusive of all shipping costs, taxes, and fees — must be visible before users are asked to enter payment details."* Their abandonment list (`https://baymard.com/lists/cart-abandonment-rate`, VERIFIED-LIVE, last updated 22 Sept 2025) puts **40% "Extra costs too high (shipping, tax, fees)"** as the top non-browsing reason, against a 70.22% average abandonment rate across 50 studies. And on the *product* page, before commitment: **64% of users looked for shipping costs on the product page before deciding to add to cart**, while **43% of sites show none** (`https://baymard.com/blog/show-shipping-costs-on-product-pages`, VERIFIED-LIVE).

Implementable spec at 360px: price block and primary CTA share one card with **≤ 24px** of vertical gap and no divider between them; the pair must be reachable without scroll after the last question is answered; on any page long enough to scroll it away, a sticky bottom bar carries **price + CTA together** (never the CTA alone — a lone sticky CTA is the drip-pricing shape).

**Steal for Bali Zero.** On **GARUDA VOA**, question 4's answer transition should resolve directly into the price card — the price is not a separate "quote" screen. On the **Visa Oracle verdict**, the price sits *inside* the verdict block, under "supported", above the named human — not in a footer. It replaces any "get a quote" or "see pricing" affordance anywhere on either surface.

**What to avoid.** The fad version is the *hero* "from IDR 790.000" with the real number 3 screens later. "From" is drip pricing with better manners. Tell them apart with one question: **does the number the user first sees ever go up?** If yes, it is a lure regardless of how honestly the increase is later disclosed.

---

## Finding 2 — Size: the FTC accidentally wrote the type scale

**Named example.** The FTC Rule on Unfair or Deceptive Fees FAQ (`https://www.ftc.gov/business-guidance/resources/rule-unfair-or-deceptive-fees-frequently-asked-questions`, VERIFIED-LIVE fetched 2026-08-31 via curl; page 403s to plain fetchers). Verbatim:

> **Can a business itemize mandatory fees or charges?** *Yes, but itemization must not overshadow the total price.* A business may itemize fees or charges for mandatory goods or services required to be included in the total price, **but the total price must be clear, conspicuous, and most prominent.**

and

> A business must display the total price **more prominently than other pricing information**, except for the final amount of payment.

The rule binds only US live-event ticketing and short-term lodging — it has zero force over an Indonesian visa agency. Cite it as a *drafting standard*, never as a compliance claim.

**The measurable rule.** "Most prominent" is not a vibe; make it a ratio and lint it. Proposed, testable: **the total's type size ≥ 2.5× any component or caveat line; the total's text/background contrast ≥ that of every other numeral on screen; no component line is bolder than the total.** At 360px that lands around a 40px/600-weight total against 14px/400 supporting lines.

The evidence on *absolute* size is split and you should know it: Coulter & Coulter, *Size Does Matter* (J. Consumer Psychology, 2005) found **smaller** type makes a price *feel* smaller; Huang (J. Consumer Behaviour, 2025) found **larger** numerals raise perceived message strength across four studies (both FROM-MEMORY, unverified — publisher pages 403'd). They don't actually conflict here: Bali Zero isn't trying to make 790.000 feel *small*, it's trying to make it feel **final**.

Two typography details that matter more than size: set the price in `font-variant-numeric: tabular-nums` so 790.000 and 850.000 align digit-for-digit; and set the currency token at **~0.55× numeral height, baseline-aligned — never superscript**. Superscript currency is the airline/SaaS tell — it exists to shrink the part of the number you're meant to skim past.

**Steal.** One price per screen on all three surfaces. On the home page the price should **not** appear in the hero — a number without a scope creates the "from" problem.

**Avoid.** A price so large it out-competes the CTA. And any price that *animates in* (see Finding 7).

---

## Finding 3 — All-inclusive vs itemised: the literature says splitting wins, which is exactly the problem

This is the finding that should change the brief.

**Named study.** Robbert & Roth, *The flip side of drip pricing* (Journal of Product & Brand Management 23(6), 2014; abstract VERIFIED-LIVE at `emerald.com/jpbm/article-abstract/23/6/413/236391`, n=95, virtual travel-agent scenario): *"underestimation of the total price of an offering is significantly weaker when prices are presented sequentially rather than partitioned."* Read it backwards: **partitioned presentation causes stronger underestimation of the total.** A competitor who quotes "service fee IDR 350.000" and adds the government fee later is not merely hiding — the presentation makes buyers *misremember the total as lower than it is*. Drip pricing, in the same paper, reduces that underestimation but costs purchase intent and fairness perception.

So: Bali Zero's single number will read as more expensive than a split quote **even when it is cheaper**, and no amount of tone fixes that. Only arithmetic shown on the page fixes it.

**What is in force in 2026** (all VERIFIED-LIVE):

| Regime | Status | The operative line |
|---|---|---|
| FTC 16 CFR Part 464 | In force 12 May 2025; US tickets + lodging only | Total price "most prominent"; itemisation permitted but must not overshadow; penalties up to **$51,744/violation** (Morgan Lewis, 3 Jan 2025) |
| UK DMCCA + CMA209 | Guidance published 18 Nov 2025, summary 7 Jan 2026 | *"It's illegal to hide additional fees, taxes or other charges that the customer will have to pay until later in the purchase process (sometimes called 'drip pricing')."* CMA defines **partitioned pricing** separately: *"when component parts of a price are given, but the overall price a customer would pay is not."* |
| EU Directive 98/6/EC Art. 2 | In force | Selling price = *"the final price for a unit of the product … including VAT and all other taxes"* |
| EU Reg. 1008/2008 Art. 23 | In force | *"The final price to be paid shall at all times be indicated"* — **and** a breakdown of fare / taxes / airport charges / other charges is **mandatory** |
| EU Digital Fairness Act | Commission proposal expected **Q3–Q4 2026** | Targets dark patterns, drip pricing, personalised pricing (Goodwin alert, 19 Nov 2025) |
| Japan 総額表示 | Mandatory since 1 Apr 2021 | Tax-inclusive figure must be on every tag, flyer and website |

**The contradiction you must hold.** Airline law *requires* the split. NN/g's 2018 guidance (Kim Flaherty, `nngroup.com/articles/ecommerce-taxes-fees`, VERIFIED-LIVE) holds up **Airbnb's itemisation** — nightly price, cleaning fee, service fee, then total — as best practice. Six years later NN/g's own *Sneaking* article (Connor Chan, 4 Oct 2024, VERIFIED-LIVE) names **Airbnb** as a hidden-costs offender. Same company, same itemisation, opposite verdicts. The variable that changed was **ordering**, not itemisation: Airbnb's numbers moved from "shown together on the product page" to "revealed at checkout."

**Steal.** Keep the never-split policy for the *number*, and drop it for the *contents*. Under the 790.000, a **non-numeric inclusion list** — three or four ticked lines, no figures: `Government fee — included` / `Our filing and follow-up — included` / `Tracking until Immigration decides — included`. This satisfies the FTC's "clear, conspicuous, most prominent" test by construction (no component numeral exists to overshadow anything), satisfies CMA209's total-price rule, and gives the buyer the comprehension that itemisation normally buys. It replaces any expandable "price breakdown" accordion.

**Avoid.** A numeric breakdown that adds to 790.000. The instant a "Government fee 500.000 / Service 290.000" line exists, Bali Zero has manufactured the exact anchor its competitors use — and hands every visitor a number to shop against.

---

## Finding 4 — When the competitor's headline is lower

**Named example.** Wise's own pricing page (`https://wise.com/gb/pricing/`, VERIFIED-LIVE): *"Always know what you're paying upfront, unlike others who hide their cut"* and *"Other providers hide fees in the exchange rate to charge you more. Not Wise."* Wise attacks the **mechanism**, never a named competitor, and places the attack immediately adjacent to its own number.

**The measurable rule.** Do on the page the arithmetic the buyer would otherwise do at the airport. Two columns, one row each, no logos, no names: `A typical agent quote` → *service fee only; the government fee paid separately, later* vs `Bali Zero` → *IDR 790.000, nothing added*. The constraint: you may state the competitor's *structure* truthfully, never assert their *amount*. The FTC's mirror obligation applies to you — its violation examples include *"A ticket seller says a 'usage fee' is required by the government when it is not."* If you say the government fee is inside, it must be, provably.

Local precedent worth stealing the *sentence* from — **Traveloka** (`traveloka.com/id-id/help/.../what-does-the-package-price-include`, VERIFIED-LIVE): *"Semua biaya dan pajak sudah termasuk, tidak ada biaya tersembunyi!"* That is the Bahasa formulation your audience already recognises; use **"sudah termasuk"** and **"tidak ada biaya tersembunyi"** as literal strings. The counter-example is the same company: Traveloka's hotel search still ships a *Tampilan Harga* toggle whose "Termasuk pajak & biaya" option must be switched **on**. Indonesia's largest OTA defaults to a partitioned hotel price — being all-in is not the local norm, which is exactly why saying it out loud is worth something.

**Avoid.** A comparison table with a named competitor and an invented number. Under Indonesian practice that is a defamation and unfair-competition exposure, and — worse for this brand — it makes Bali Zero sound like the agents it is differentiating from.

---

## Finding 5 — Making "all-inclusive" legible in one glance

**Named example.** Wise again, and this is the whole finding: the fee row's value is the string **"Included in IDR amount"**, not a figure to be added. The label is `Total fees and taxes`; the value is a preposition. The two input labels are `You send exactly` and `Recipient gets` — both verbs of finality.

**The measurable rule.** The inclusion claim must be (a) inside the same card as the price, (b) within ~48px below it, (c) **≤ 8 words**, (d) containing the word *included* / *sudah termasuk*, and (e) paired with an explicit **zero-state**: `Nothing is added at the end.` / `Tidak ada biaya tambahan.` The zero-state line is the one most designs omit, and it is the one that answers the fear. Falsifiable acceptance test, runnable this week: a 5-second exposure of the card to 10 people, then two questions — *"How much will you pay in total?"* and *"Is there anything else to pay later?"* Ship only at **≥ 90% correct on both**. Anything less means the layout is not carrying the claim.

Japan's 総額表示 gives the honest caveat: mandating the inclusive figure on the tag does **not** dictate which figure is set biggest, and Japanese retailers routinely print the tax-excluded number larger. Legibility is a design decision even where inclusiveness is a legal one.

**Steal.** On **GARUDA VOA**: price → inclusion line → zero-state line → three ticked inclusions → CTA, one card. On the **Visa Oracle verdict**: the same block, with the named human directly beneath the CTA so that "who takes this" and "what it costs" are one visual unit.

**Avoid.** An asterisk. `IDR 790.000*` destroys in one glyph everything the paragraph above it built — an asterisk beside a price is the universally learned signal for *there is a catch*. Also avoid a tooltip as the only home for the inclusion claim: FTC's clear-and-conspicuous test for interactive media is that the disclosure must be **"unavoidable"**, and a tooltip is by definition avoidable.

---

## Finding 6 — IDR formatting for an international audience

**Measured, not remembered.** Run on this machine today (Node v26.5.0):

```
Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR'}).format(790000)
  → "Rp 790.000"        codepoints: 52 70 a0 37 39 30 2e 30 30 30
  → resolvedOptions(): maximumFractionDigits = 0   (IDR needs no ,00 guard)
Intl.NumberFormat('en-US',{style:'currency',currency:'IDR'}).format(790000)  → "IDR 790,000"
Intl.NumberFormat('de-DE',{style:'currency',currency:'IDR'}).format(790000)  → "790.000 IDR"
Intl.NumberFormat('id-ID',{notation:'compact',...}).format(790000)           → "Rp 790 rb"
```

Three traps, all real:

1. **The `.` trap.** `Rp 790.000` shown to an English-reading tourist is ambiguous at best — `790.000` parses as *seven hundred ninety point zero*. An unparseable total is worse than a hidden one.
2. **The NBSP trap.** ICU emits U+00A0 between `Rp` and the digits. Indonesian house style has no space at all — Wikipedia's Indonesian rupiah article (VERIFIED-LIVE): *"In Indonesian writing, the symbol has no full stop or intervening space, while full stops separate thousands and a comma precedes decimal fractions; an amount may therefore be written as Rp50.000,00."* It also records that **Bank Indonesia's own English material uses English punctuation, as in Rp50,000**. The platform default is wrong for *both* audiences.
3. **`compact` is a landmine.** `Rp 790 rb` for a price you are asking someone to pay is not a price, it is a rounding.

**The rule to implement.** Do not use one formatter. Two, keyed to page language, both with an explicit currency-display override:

- `id` → `Rp790.000` (no space; strip the NBSP that ICU inserts)
- `en` → `IDR 790,000` (`currencyDisplay:'code'`, en-US grouping)

`IDR` beats `Rp` for the English surface for one non-obvious reason: `Rp` is an unfamiliar glyph a scam-wary reader has to decode, whereas `IDR` is an ISO 4217 code they can paste into a converter. The suspicious buyer *wants* to leave and check; make that trivial and they come back.

**FX.** Do not quote a rate you cannot honour. Show, at 0.5× size, low emphasis, directly beneath: `≈ €44 · mid-market rate, 31 Aug — your bank sets the final amount`. Two properties make this honest rather than a lure: it is **visually subordinate** (so it can never be mistaken for the price) and it **names who decides** (not you). Wise is the citable precedent for the honesty of naming the mid-market rate as the reference. The alternative — offering to charge in EUR — is dynamic currency conversion and reintroduces exactly the hidden margin this brand is positioned against.

---

## Finding 7 — Two prices, honestly: 790.000 now, 850.000 later

**The structural point first.** 790.000 (the VOA) and 850.000 (the extension) are **not a menu**. One is bought today; the other is a decision available in ~30 days. Rendering them as two cards side by side — with or without a "Most popular" badge — invents a choice the buyer does not have and is the single most likely way this page slides into dark-pattern territory.

**The device: a timeline, not a comparison.** One horizontal rail: `Today — IDR 790.000 — 30 days` → `Day ~25, if you want to stay — IDR 850.000 — 30 more days`. Directly under it, the sum, stated plainly: `60 days in total = IDR 1.640.000.` Stating the sum is the whole ethical move — it is precisely the arithmetic that partitioned pricing suppresses (Robbert & Roth), and doing it unprompted is the strongest single trust signal on the page.

**The regulated boundary.** EU Directive 98/6/EC Art. 6a (VERIFIED-LIVE): a "was" price in a reduction announcement must be *"the lowest price applied by the trader during a period of time not shorter than 30 days prior to the application of the price reduction."* The CMA has been enforcing the same terrain since April 2025 under the DMCCA; the Digital Fairness Act proposal (Q3–Q4 2026) is expected to add dark patterns, drip pricing and **personalised pricing** on top. The Commission's own 2022 behavioural study (two experiments, several thousand EU consumers) found that *"Hidden information"* and *"Toying with emotions"* scenarios *"led to making choices that are inconsistent with their preferences"* (FROM-MEMORY — search-snippet only; the op.europa.eu PDF was not fetched).

**Crosses the line, concretely:** pre-selecting the extension; a strikethrough on a price never charged; a "save X" claim when nothing was saved; a countdown next to either price; framing 850.000 as a discount off a fictional 1.200.000; making the extension the visually dominant card so the cheaper, correct-today product looks like the downgrade.

**Stays on the right side:** both numbers the same type size (they are equally real), the sum shown, the second one explicitly deferred ("you can decide then"), and no default selection.

---

## Finding 8 — The fad that will age worst

**Named: the price that assembles itself on screen.** Odometer count-up numerals, a strikethrough "was" that fades in, a *"you saved…"* line, all inside a glass-morphic card. It is everywhere in 2025–26 checkout and pricing UI, and it fails a single test: **a number that changes state after the user has read it is theatre, and on a page selling to people who are afraid of being scammed, theatre reads as sleight of hand.** The tell that separates it from legitimate motion: legitimate motion happens *before* first meaningful paint or in response to *the user's own input* (Wise's total recalculating as you type is fine, and honest). Illegitimate motion happens *to* a settled number.

**Runner-up: the BNPL split-price line** — `or 4× IDR 197.500`. It is spreading into non-credit contexts as pure framing, and its regulatory clock is running: the FCA's PS26/1 makes deferred payment credit a **regulated activity from 15 July 2026** in the UK, with financial-promotion rules attached (FROM-MEMORY — search-snippet only, PS26/1 not fetched). Its sibling — `$29/month` displayed for a plan billed annually — is already being litigated as a dark pattern. For a one-off IDR 790.000 government-inclusive service, a split-payment line would be the exact same move Bali Zero refuses to make with the government fee, just on the time axis instead of the component axis.

---

## What I could not verify

- **The official e-VOA government fee (IDR 500.000) and the extension fee.** I fetched `evisa.imigrasi.go.id` live today; the homepage carries **no fee figure at all**, and `imigrasi.go.id/en/visa-on-arrival/` and two e-visa sub-paths returned 404. I therefore state **no** government-fee amount anywhere above. Before any "790.000 vs a typical agent's quote" comparison ships, someone must pin the current PNBP figure to a primary source (PP on PNBP for Kemenkumham/Imigrasi, or a live checkout).
- **Coulter & Coulter (2005) "Size Does Matter"** and **Huang (2025, J. Consumer Behaviour, doi 10.1002/cb.2465)** — search snippets only; all publisher pages 403'd. Both font-size claims are unverified.
- **Santana, Dallas & Morwitz, "Consumer Reactions to Drip Pricing" (Marketing Science)** and **Moriuchi & Murdy (2025)** — publisher pages 403'd. Only the Robbert & Roth 2014 abstract was actually fetched, and it carries the load-bearing "partitioning increases underestimation" claim on **n=95, one scenario**. That is thin evidence for a strategically important conclusion. It is directionally corroborated by the CMA's and FTC's rulemaking rationale, but read the Marketing Science paper before building a pricing argument on it.
- **EU Commission behavioural study on dark patterns (2022)** and **FCA PS26/1 (BNPL, 15 July 2026)** — search summaries only, PDFs not fetched.
- **CMA209 full guidance (58pp PDF, updated 7 Jan 2026)** — I fetched only the gov.uk landing page and the HTML summary. Its detailed rules on reference/"was" prices are unread; my Art. 6a statement rests on the EU directive text, which I did fetch.
- **WCAG 2.2 SC 2.5.8 (24×24 target size)** — asserted from memory, not fetched this session.
- **Wise's visual hierarchy.** I read the calculator through text extraction; which label is actually largest I did not measure. Screenshot it at 360px before copying the hierarchy.
- **The Indonesian orthographic rule** ("Rp" with no space) rests on Wikipedia alone — the primary authority (EYD/PUEBI, `ejaan.kemdikbud.go.id`) **failed DNS from this machine**. The ICU output, by contrast, is measured and reliable.
- **Monzo** appears in the lane brief; I did not fetch it and deliberately make no claim about it.
