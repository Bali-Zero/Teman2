# UNADJUDICATED FIRST PASS — not accepted findings

Retained for provenance. Several priorities and factual inferences were corrected in adjudication.md and the final accepted report. This source-only pass did not see screenshots. Prior-registry claims about blocked destinations are not fresh independent production observations by Claude.

---

# Bali Zero Homepage — Independent Strategic Review

Evidence base: source files supplied. No rendering was observed; nothing below describes actual visual output. Labels: **(F)** fact from source, **(I)** inference, **(Idea)** proposal, **(?)** unknown.

## 1. Core proposition and audience priority

**(F)** The site declares one proposition in `layout.tsx`: "Immigration, company setup, tax and property guidance in Indonesia", and `Hero` repeats it with a four-way chooser. **(F)** The emotional layer ("Good advice starts with people", named hosts Surya/Ari, `Reviews` framing) is consistently human-first.

**(I)** The proposition is *category-complete but stage-blind*: it tells visitors which of four domains they are in, never where they are in their journey (deciding / arriving / staying / operating / exiting). Two very different people — a tourist needing an E-VOA and a PT PMA owner facing annual reporting — receive the same four doors.

Recommended priority: **1)** high-intent movers (KITAS/company/property, highest value, highest anxiety) **2)** arriving visitors (E-VOA, volume + lowest friction entry into the ecosystem) **3)** existing clients (already have My Bali Zero; they need a *fast* route, not persuasion) **4)** researchers/Journal readers. **(F)** The current DOM order (Hero → Services → E-VOA → Second Home → Reviews → Portal → Journal → Team → Contact) serves 1 and 2 first, which is correct; **(I)** placing Portal and Journal *before* Contact means the two audiences most likely to leave the page are given exits before the conversion block.

## 2. Five highest-impact findings

| # | Finding | Evidence | P | Treatment | Risk | Validation |
|---|---|---|---|---|---|---|
| 1 | **No persistent conversion path.** Contact is terminal and unreachable except by scrolling. | **(F)** `Entry.tsx` `navigation` = Explore/Services/Journal/Our team + account; no contact entry. **(F)** `page.tsx` places `Contact` last. **(F)** QA-001 was closed by *removing* the fixed contact control. | P0 | Add a header-level "Talk to us" link (in-flow, not overlay) resolving to WhatsApp or `#contact`; keep per-section hosts. **(Idea)** A sticky footer bar only on ≤680px, tested against the QA-001 collision criterion. | Reintroducing the overlap that QA-001 fixed. | % sessions reaching any contact action; scroll depth at first contact click; WhatsApp opens per 100 sessions. |
| 2 | **Journal exports traffic mid-funnel.** | **(F)** `Journal.tsx` `StoryLink`/`feature`/`archive-pick` all use `finalSourceUrl ?? sourceUrl`; all six records in `journal.ts` point to `balizero.com`. **(F)** Section sits above `Team` and `Contact`. | P1 | Render the six stories on the local `/journal` route, or mark them as external and add a "still deciding? talk to us" block *inside* the Journal section. | Duplicate content vs `balizero.com/news` **(?)** whether canonical strategy exists. | Exit rate on story links; % of story-clickers who return; assisted conversions. |
| 3 | **Promise calibration is inverted: tools over-claim, the portal under-claims.** | **(F)** `services.ts` labels "Visa Oracle" / "Open Visa Oracle"; audit shows `visa.balizero.com` REDIRECTs to a "public Bali visa selector" and `taxIntelligence` intentMatch = **PARTIAL**. **(F)** `Portal.tsx` carries three disclaimers ("do not establish which features are available", "availability is not confirmed"). | P1 | Name each tool by what the visitor will actually see; add one line per tool: what it does / what it cannot decide. Replace portal hedging with a single honest statement of verified scope (sign-in), and cut the three illustrative tabs until features are verified. | Losing "Oracle" brand equity; a shorter Portal block looks thin. | 5 unmoderated first-click tests per tool: "what will this button do?"; tool→return rate; support messages asking "does the portal have X". |
| 4 | **Decision overload and duplicated entry points.** | **(F)** Hero renders 4 category links to `/services/*`; `Services.tsx` renders the same 4 routes *plus* an external tool link *plus* a WhatsApp link per card (12 actions), plus "Explore all services", plus `Team` and `Contact` CTAs. | P1 | One primary action per card (the service route); demote the tool link to a secondary line; keep "Talk to our team" as tertiary. Let Hero own category choice or Services own it — not both. | Reduced tool discovery. | Click distribution across the 12 actions; first-click test success on "where would you go to set up a company?". |
| 5 | **No price, scope or timeline anywhere.** | **(F)** `Evoa.tsx` price block reads "Plan your arrival." and defers fees to the destination. **(F)** No `service-pages.ts` entry contains cost, duration or deliverables. **(F)** A live pricing endpoint exists in evidence (`pricingExactKey`, 200). | P0 | Publish "from" ranges or an explicit "how our fees work" section, sourced server-side from the authoritative pricing service. **Do not** expose the raw endpoint. | Anchoring, staleness, competitor undercutting; **(?)** whether fee publication is constrained (see Q1/Q2). | Share of first WhatsApp messages that are "how much?"; qualified-lead ratio; time-to-quote. |

Secondary **(F)**: `layout.tsx` title is "Website development" and robots is `noindex, nofollow` — correct for preview, launch-blocking if shipped. The approved `/team` destination is currently `https://balizero.com/team` in `Team.tsx` and `Footer.tsx`.

## 3. Ecosystem coverage by lifecycle

| Stage | Visible **(F)** | Missing **(I)** | Unverified **(F/?)** |
|---|---|---|---|
| Consider | Hero chooser, Journal, Reviews, Team | Cost-of-living/decision framing; "is Bali right for me" | Journal category/search (audit: MISMATCH) |
| Arrive | E-VOA section + service | Extension of VOA; airport/on-arrival edge cases | E-VOA canonical resolves to `/visa` |
| Stay | Immigration service page, Visa Oracle, Second Home Studio | **KITAS/KITAP renewal & extension; dependants/family; work permit (RPTKA) for employers** | Visa Oracle destination is a selector, not an oracle |
| Establish | Company setup page, KBLI Navigator | Post-incorporation: NIB→licence sequencing, capital, bank account, office/domicile | — |
| Operate | Tax service page, Tax Compliance Calendar | **LKPM/annual reporting, payroll & BPJS, individual SPT, audit** | Tax product scope (audit: PARTIAL) |
| Own property | Property page, Property Check | Lease vs Hak Pakai vs PT PMA structures; due-diligence checklist | — |
| Client life | My Bali Zero, human advisory, WhatsApp/email/phone | **Renewal reminders, document expiry, an "existing client" fast lane in the header** | Portal features (audit: LOGIN_REQUIRED only) |
| Exit / change | — | **Company closure, visa cancellation, tax de-registration, selling property** | — |

**Do not expose:** `nuzantara-rag.fly.dev/api/pricing/service` (raw backend), `t.me/Balizerobot` **(F: BLOCKED, unrelated adult/spam content)**, `my.balizero.com/portal/login-upgraded` internals, the destination/evidence registries, and `developmentOnlyArticleFixture`. Consume pricing server-side only.

## 4. Beauty, within cream / forest / terracotta

**(F)** The palette is already codified (`#f6f3ed` cream, `#202824`/`#253e33` forest, `#f7e3d1` terracotta wash) with a strict editorial register. **(Idea)**, none dependent on rendering:

- **Rhythm over uniformity.** Alternate cream and a deeper forest field per section so E-VOA / Second Home / Portal read as distinct chapters rather than a single scroll.
- **One accent, used scarcely.** Reserve terracotta (`.button.copper`) exclusively for the single primary action per section; make every secondary action a `.textlink`. Scarcity reads as confidence.
- **Typographic hierarchy instead of more boxes.** The Journal masthead is the strongest asset; extend that broadsheet logic (rules, eyebrows, indexed items) to Services so the tool cards feel edited, not gridded.
- **Let the artwork breathe.** Hero, E-VOA panorama and the Second Home book are the identity; give each more vertical room and fewer competing controls above the fold.
- **Consistent art captions.** "AI ILLUSTRATION" appears on the hero; apply the same quiet caption convention to every generated image for honesty and visual consistency.

## 5. Five research questions for Gemini

1. **Fee transparency.** Among Indonesian visa/company-setup/tax intermediaries and comparable regulated-service marketplaces, who publishes fees, at what granularity, and does any Indonesian rule (immigration agent, *konsultan pajak*, advertising) constrain it? *Counter-hypothesis: publishing fees commoditizes the offer and lowers qualified-lead quality.*
2. **Permissible claims.** What licensing and titling rules govern a non-law, non-licensed entity presenting "tax", "legal" or "due diligence" advice in Indonesia, and what disclaimer patterns do peers use? *Counter-hypothesis: disclaimers measurably reduce trust and no rule is triggered.*
3. **Tools vs advisory.** In high-anxiety regulated services, do self-serve eligibility tools increase advisory conversion or cannibalize it? Seek controlled/comparative evidence, not vendor claims. *Counter-hypothesis: tool users self-serve and never contact.*
4. **Audience composition.** From Imigrasi/BPS/authoritative arrival and permit data, what is the nationality and language composition of foreigners in Bali who incorporate, hold KITAS/Second Home, or own property — is English-only leaving a material segment? *Counter-hypothesis: English is sufficient lingua franca for these segments.*
5. **Recurring-obligation demand.** Which post-arrival obligations (KITAS extension, LKPM, SPT, BPJS, licence renewal) generate the highest recurring demand and search intent, and do reminder/calendar products actually improve retention in advisory firms? *Counter-hypothesis: retention is driven by the human relationship; tooling adds cost without lift.*