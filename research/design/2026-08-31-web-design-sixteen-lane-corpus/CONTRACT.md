---
adversarial_review: exempt-input-brief-issued-before-the-research-not-a-finding
---

# RESEARCH CONTRACT — Bali Zero web design, 2026 state of the art

Read this before you research anything. It defines who the client is, what the work is for, and the
exact shape your report must take. It is identical for all twelve lanes.

## 1. The client and the surfaces

**Bali Zero** is a licensed agency in Bali, Indonesia, handling immigration, company setup, tax and
property matters for foreigners. Voice: an honest professional who knows the rules — never hospitality
fluff, never "guaranteed approval" (forbidden by law and by the company's own charter). What the buyer
should feel: *this is the real thing, run by people who know the rules, and the price is the whole price.*

Three public surfaces are being redesigned:

- **Home page** (balizero.com). Live copy today: dateline "Bali Zero · Dispatch · Kerobokan"; tagline
  "Your Bali, from Zero."; H1 "Most people moving to Bali pick the wrong visa in the first month.";
  four segment doors under "Start where you are." (moving / starting a business / taxes / property);
  proof strip "4.9 ★ · 693 Google reviews · 5,000+ clients since 2019 · Licensed notary & tax agent"
  and "Filed this month: 47 KITAS, 9 PT PMAs".
- **GARUDA VOA landing** — a self-serve flow for the electronic Visa on Arrival: 4 questions → an
  all-inclusive price (IDR 790.000, government fee included) → passport upload → payment on local rails
  (QRIS, virtual account BCA/Mandiri, card) → tracking until Immigration decides.
- **Visa Oracle verdict** — a decision tree ends here: the verdict ("supported"), the exact
  all-inclusive price, a named human who takes the case after payment, every answer still editable.

**The audience**: first-time tourists, long-stayers, families, small investors. Mostly on 360–390px
Android phones, frequently on slow connections, often at night, and — this matters — often afraid of
being scammed, because the visa-agent market around them is full of scams.

**Languages**: English and Bahasa Indonesia. Indonesian words run longer; layouts must absorb that.

## 2. What has already failed here (so you do not repeat it)

Three rounds of AI-generated design have been rejected by the owner. The failures, in order:

1. Mockups that were technically correct and emotionally flat — "la UI è scialba e piatta".
2. Fifteen night-mode designs that all looked identical, because the brief handed out reference colour
   tokens and every model anchored on them.
3. The follow-up round diverged in colour once the tokens were banned — but three of five models then
   took their *names and metaphors* from the list of suggestions the brief offered. **Whatever the brief
   supplies, the models return.** That is the deepest lesson so far, and it applies to you: do not give
   this project a shopping list of trends. Give it evidence and mechanism.

## 3. What a good report looks like — the only shape accepted

Your report is worthless if it is a list of trends. Every claim must be traceable to something that
exists and to a reason it works. For each substantive finding, give all four of these:

1. **The named example** — the actual site, product, or system, with a URL. Not "many fintechs do X".
2. **The measurable rule** — the mechanism, stated so someone could implement it or test it. Numbers
   where numbers exist (contrast ratios, timings in ms, sizes in px/rem, measured conversion or
   comprehension effects with the study behind them).
3. **What to steal for Bali Zero** — concretely, on which of the three surfaces, and what it replaces.
4. **What to avoid** — the fad version of the same idea, and how to tell the two apart.

### Sourcing rules (anti-hallucination — this is enforced)

- **Verify every source you cite.** If you have web tools, fetch the page and quote it. Mark each source
  `VERIFIED-LIVE (fetched <date>)` with the URL.
- If you cannot fetch it, mark it `FROM-MEMORY (unverified)` and say so plainly. An honest
  `FROM-MEMORY` line is welcome; a fabricated URL or an invented study is the one unforgivable error
  here, and every citation will be checked.
- **Prefer 2025–2026 material.** Where you cite something older, say why it still holds.
- Sources worth hitting, depending on the lane: award bodies (Awwwards, FWA, CSS Design Awards, Webby);
  serious design systems (GOV.UK Design System, Stripe, Linear, Vercel, Apple HIG, Material 3
  Expressive, IBM Carbon, Atlassian, Shopify Polaris); real research (Nielsen Norman Group, Baymard
  Institute, WCAG 2.2 / APCA / W3C drafts, Chrome/web.dev performance data); and for the local axis,
  Indonesian and South-East Asian sources (Tokopedia, Gojek/GoTo, Traveloka, Bank Indonesia / QRIS
  documentation, local design writing).
- Cite what contradicts your recommendation too. A finding with a known counter-example is more useful
  than a clean one that hides it.

### Length and tone

Aim for 1,500–3,000 words of substance. No filler, no restating the brief, no "in today's fast-paced
digital landscape". Write for a designer who will implement this tomorrow and for an owner who will
smell hedging instantly. Where the honest answer is "the evidence is thin", say that — it is more
valuable than a confident invention.

## 4. Deliverable

One Markdown file at the path your lane brief names. Start it with this frontmatter:

```
---
lane: <lane id and title>
seat: <which model you are>
date: 2026-08-31
sources_verified_live: <n>
sources_from_memory: <n>
---
```

Then: a 5-line executive summary a busy owner can act on, then the findings in the four-part shape
above, then a final section **"What I could not verify"** listing every claim you would want checked
before it is trusted. That last section is not a weakness — it is the part that makes the rest usable.
