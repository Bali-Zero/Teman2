---
lane: L05 — THE VERDICT SCREEN: when a system tells a person the answer about their own life
seat: Claude Opus 5 (1M context), xhigh effort
date: 2026-08-31
sources_verified_live: 22
sources_from_memory: 6
adversarial_review: exempt-raw-lane-output-synthesis-carries-the-review
---

## Executive summary

1. **The determination is one sentence, second person, as the H1, action on the next line.** GOV.UK ships exactly that: *"You'll need a visa to come to the UK" / "Apply for a Standard Visitor visa"*. Not a badge, not a card, not a celebration.
2. **The whole price sits on the verdict, split into government fee + our fee.** Baymard (Sept 2025): unexpected extra costs are the #1 fixable abandonment cause, 39%. The documented Bali scam is agents charging "above and beyond" the state's published IDR 500.000 — a breakdown checkable against a `.go.id` number is the strongest anti-scam device available, and nobody else prints it.
3. **State the limit of certainty by naming the actor, not by hedging the outcome.** "Immigration decides" is a sentence about who holds the pen. "*subject to approval" is an asterisk, and asterisks are what scam sites use.
4. **Show the four answers, editable in place — not the algorithm.** A 2025 study (12 experts + 180 lay users): *"no form of explanations helped in fostering appropriate trust."* Show inputs and the rule that fired; never a confidence percentage.
5. **Refuse the artificial "analysing your case…" delay.** This audience's fear is deception; a fake progress bar is a small, verifiable lie on the one screen where you need to be believed.

---

## F1 — The determination is a sentence, not a badge

**Example.** GOV.UK "Check if you need a UK visa", walked live to two terminal states: `/y/india/no/tourism/no` → H1 **"You'll need a visa to come to the UK"**, body **"Apply for a Standard Visitor visa"**, then a *"Your answers"* summary. `/y/canada/no/tourism` → H1 **"You'll need an electronic travel authorisation (ETA) or a visa"**, then the two named instruments.

**Rule.** The verdict is the page's `h1`: second person, indicative, under 10 words, no conditional clause, no adverb of degree. The single next action is the immediately following line and names a real instrument, not "Continue". GOV.UK's published writing standard produces that compression and is testable: *"Plain English is mandatory for all of GOV.UK"*, *"Try to split up sentences that are over 25 words long"*, *"Paragraphs should have no more than 5 sentences each."*

**Steal.** Visa Oracle H1 becomes `Your e-VOA is supported.` — replacing "Great news! Based on your answers, it looks like you may be eligible…". On GARUDA VOA the price is the second line, same hierarchy, not scrolled to. Indonesian runs longer (*"Visa on Arrival elektronik Anda didukung."*) — let it wrap to two lines rather than shrinking the type.

**Avoid.** The result-card fad: a green `ELIGIBLE ✓` pill with the determination in 14px grey below. A badge is a label a system applies to a record; a person needs a sentence addressed to them. Pronoun test — if the largest text on screen contains no "you", it is a badge.

*`VERIFIED-LIVE (fetched 2026-08-31)`: https://www.gov.uk/check-uk-visa/y/india/no/tourism/no · https://www.gov.uk/check-uk-visa/y/canada/no/tourism · https://www.gov.uk/check-uk-visa/y · https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/*

---

## F2 — The block order is already solved; copy it

**Example.** GOV.UK's confirmation-pages pattern: a confirmation page **must include** *"a reference number, if there is one"*, *"details of what happens next and when"*, *"contact details for the service"*, *"links to information or services that users are likely to need next"*, *"a link to your feedback page"*, and *"a way for users to save a record of the transaction, for example, as a PDF"*. NHS adds a finding — *"In our research, people found the green panel at the top of the confirmation page reassuring"* — and a limit: *"Avoid including too many different components on a confirmation page. Research suggests they can overwhelm people."* GOV.UK adds a hard constraint: interactive elements inside the green panel *"will not be accessible"*.

**Rule.** Verdict panel (nothing interactive inside it) → price → "What happens next" with a *when* on every step → the four answers with Change links → the named human → contact → save-a-record. Component types on screen ≤ 7.

**Steal.** The **save-a-record affordance is the highest-value item here and is almost always omitted.** An anxious buyer at 11pm forwards the quote to a partner on WhatsApp before paying. Give a one-tap PDF/permalink carrying a reference code, the price breakdown, the named handler and the date — GOV.UK prints its reference in the panel (*"Your reference number — HDJ2123F"*).

**Avoid.** CTAs inside the verdict panel (inaccessible), and the dashboard fad of ringing the verdict with six stat tiles. The panel's job is one fact.

*`VERIFIED-LIVE`: https://design-system.service.gov.uk/patterns/confirmation-pages/ · https://service-manual.nhs.uk/design-system/patterns/confirmation-page*

---

## F3 — Certainty and its limit: name the actor, don't hedge the outcome

**Examples.** GOV.UK's confirmation example does it in one sentence of ordinary English: **"They will contact you either to confirm your registration, or to ask for more information."** The state has decided its part and hands over the rest without weakening it. CBP's ESTA approval screen does it with more force — an authorization *"does not guarantee admission to the United States as a CBP officer at a port of entry will have the final determination"*: one clause, a named actor, on an otherwise unambiguous **Authorization Approved** screen. UK mortgage Decision-in-Principle pages name the *reason* for the limit — a DIP *"is based on limited information about you as a borrower, so it is not a guarantee"*.

**Rule.** Four tests: (a) a complete sentence, never an asterisk or superscript; (b) subject is a named actor — *Immigration*, *the officer at the airport* — never passive "results may vary"; (c) once, after the verdict and after the price, never inside the H1; (d) **deletion test** — delete it; if the verdict is now false it was load-bearing and stays, if still true it was decoration and goes. GOV.UK's `warning-text` component exists for *"legal consequences of an action, or lack of action"* (*"You can be fined up to £5,000 if you do not register"*) — give that weight to the money consequence on refusal, not to the verdict.

**Steal.** Three lines on the Visa Oracle verdict, in this order:
> **Your e-VOA is supported.**
> IDR 790.000 all in — government fee IDR 500.000 + Bali Zero IDR 290.000.
> We prepare and file it. Indonesian Immigration makes the decision. If they refuse, [exact refund rule].

"Guaranteed" is forbidden; **"we file, they decide"** replaces it and is strictly stronger, because it is checkable — and because the scam sites cannot write it.

**Avoid.** Hedge-everywhere: `*subject to approval`, an 11px grey legal block, "may be eligible", "should be able to". Indistinguishable from a scam page protecting itself, and it deflates the verdict into mush. A good caveat *adds* a fact (who decides, what happens to your money); a bad one *subtracts* confidence from a fact already stated.

*`VERIFIED-LIVE`: https://design-system.service.gov.uk/patterns/confirmation-pages/ · https://design-system.service.gov.uk/components/warning-text/ · `FROM-MEMORY (unverified — search snippet; help.cbp.gov 403 to my fetcher)` https://www.help.cbp.gov/s/article/Article-1445 · `FROM-MEMORY (unverified — search snippets)` Nationwide / Lloyds / NatWest DIP pages*

---

## F4 — The answers stay on the verdict, editable in place

**Example.** GOV.UK check-answers pattern + summary-list component: *"You should provide a 'Change' link next to each section on your check answers page so that users can add or change the information."* Benefits: it *"reduce[s] error rates as users are given a second chance to notice and correct errors before submitting data"* and *"increase[s] users' confidence… that their data has been captured."* Return behaviour: *"the 'Continue' button should return them to the check answers page. They should not need to go through the rest of the transaction again."* Each action link carries visually-hidden text so a screen reader hears *"Change name"*, not *"Change"*. The live visa checker ships this — the walked pages show *"Your answers"* with a Change control per row plus a separate *Start again*.

**Rule.** Four rows (nationality, purpose, dates, entry point), each key · value · Change-with-hidden-text. Editing costs two taps and one return; never restarts the flow; prior data pre-populated. **If the edit flips the verdict, say so explicitly** — *"Changing your stay to 90 days changed your result."* Otherwise the user cannot tell whether the system re-decided or merely re-rendered.

**Steal.** Sits directly under the price on the Visa Oracle verdict, replacing the "Start over" button. At 360px use summary-card grouping so four rows read as one object, not four stripes.

**Avoid.** A modal edit that loses the verdict; and the opposite fad — a live "playground" where a date slider continuously re-rolls the price. A verdict that mutates under your finger stops being a determination and becomes a configurator.

*`VERIFIED-LIVE`: https://design-system.service.gov.uk/patterns/check-answers/ · https://design-system.service.gov.uk/components/summary-list/ · https://www.gov.uk/check-uk-visa/y/india/no/tourism*

---

## F5 — Show the inputs and the rule. Do not show the algorithm.

**The contradicting evidence, first.** *"Even explanations will not help in trusting [this] fundamentally biased system": A Predictive Policing Case-Study* (arXiv 2504.11020, 2025) — two studies, 12 retired Dutch police officers and 180 crowdsourced lay users, eight decision rounds, four explanation conditions (none/text/visual/hybrid). Finding: **"no form of explanations helped in fostering appropriate trust."** Hybrid explanations raised subjective trust among experts, and the authors' verdict on that is the point: **"an increase in trust is worrisome, as it does not lead to better decisions."** Explanations bought belief without buying accuracy.

**The 2026 backdrop, all in force.** GDPR Art. 22(1): a right *"not to be subject to a decision based solely on automated processing… which produces legal effects concerning him or her or similarly significantly affects him or her"*; 22(3) requires *"the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision."* EU AI Act Art. 86, applicable **2 August 2026**: a right to *"clear and meaningful explanations of the role of the AI system in the decision-making procedure and the main elements of the decision taken."* Art. 50(1)+(5), same date: people must be *"informed that they are interacting with an AI system"*, *"in a clear and distinguishable manner at the latest at the time of the first interaction or exposure."* Fines to €15m or 3% of turnover. Bali Zero serves EU nationals — assume reach.

**Rule.** The verdict owes four things and no fifth: (1) the four inputs, editable; (2) **the rule that fired, one plain sentence naming the instrument** — "Visa on Arrival is open to your nationality; 30 days, extendable once"; (3) a named human empowered to override — which *is* the Art. 22(3) safeguard, and a conversion asset rather than a compliance cost; (4) if a language model touches this page, one line saying so. Must not ship: a confidence score, a probability, a decision-tree visualisation, a "how we calculated this" expander containing pseudo-reasoning.

**Steal.** Turn the obligation into the trust device: *"A person checks every case before we file. If you think this answer is wrong, tell [name] — they can override it."* One sentence discharges Art. 22(3), honours the spirit of Art. 86, and is the most reassuring thing on the page.

**Avoid.** `AI-powered eligibility score: 94%`. A percentage on a binary legal question is a fabrication with a decimal point, and the 2025 evidence says it buys subjective trust *without* better decisions — precisely how a confident scam beats an honest agency. A legitimate explanation cites an instrument you could look up; a fad explanation cites itself.

*`VERIFIED-LIVE`: https://arxiv.org/html/2504.11020 · https://gdpr-info.eu/art-22-gdpr/ · https://artificialintelligenceact.eu/article/86/ · https://artificialintelligenceact.eu/article/50/ · https://www.cooley.com/news/insight/2026/2026-08-03-eu-ai-act-transparency-obligations-take-effect-2-august-2026*

---

## F6 — The price is the verdict's twin, and it must be checkable

**Example.** Baymard cart-abandonment research (meta-analysis updated September 2025, 50 studies, average abandonment 70.22%): *"Extra charges like shipping, taxes, and fees are the leading cause of abandonment; our survey found 39% of users abandoned a checkout for this reason"* (also 19% forced account creation, 18% *"the process felt too difficult"*). NN/g's credibility factor #2 is **Upfront Disclosure** — *"reveal shipping charges immediately rather than waiting until after the user has placed an order"*, documenting *"what is included in a base cost, stating any additional fees or charges."*

**Local anchor.** Reporting Indonesian Immigration: the e-VOA *"costs IDR 500,000 plus any relevant international card charges"*; the documented scam has two shapes — agents *"who do legitimately get their clients a visa but charge above and beyond what should be paid"*, and sites that take money and never file. Immigration: *"These websites are not endorsed by or associated with the Indonesian government."*

**Rule.** Print the arithmetic, not the adjective:
```
Government fee (Imigrasi)   IDR 500.000
Bali Zero                   IDR 290.000
Total                       IDR 790.000   ← nothing else, ever
```
Every line independently checkable; the government line links to the `.go.id` source. Above the fold at 360px, before any form field. Any figure that can change later (card fees, extension) is named here with its trigger, or it does not exist.

**Steal.** Replaces "All-inclusive · no hidden fees" as a slogan on GARUDA VOA, and appears identically on the Visa Oracle verdict. The scammers' signature is quoting one number and charging another at checkout; showing the split is the one move they cannot copy without exposing their margin.

**Avoid.** The trust-badge fad — "100% transparent", padlock glyphs, a "no hidden fees" ribbon. NN/g's finding is that checkable, third-party signals carry credibility; self-assertions do not. A slogan asserts; a breakdown invites verification.

*`VERIFIED-LIVE`: https://baymard.com/learn/reduce-cart-abandonment · https://www.nngroup.com/articles/trustworthy-design/ · https://thebalisun.com/bali-tourists-reminded-there-is-only-one-official-website-for-e-voa/*

---

## F7 — The named human is a commitment, not a portrait

**Evidence.** NN/g, *"About Us" Information on Corporate Websites* (26 May 2019; three rounds, 70+ users observed, 100 sites tested and 65 reviewed; latest round 20 participants aged 24–65): users appreciated *"realistic photography"* and *"photos of real employees"* over stock; *"Content with an honest and straightforward tone of voice eased fears and skepticism, therefore making users more comfortable with sharing their personal information"*; *"stock photography"* and *"walls of text"* hurt satisfaction. NN/g's trustworthy-design article adds the service-industry specific: *"service sites display photos from all stages of the service, not merely the end result"* — testers wanted *"images of the actual cleaning process and who would be doing the cleaning."* The stake, per NN/g's ecommerce trust report (5th ed., 53 guidelines, 350+ sites, 5 countries): *"Trust is essential to the user's willingness to risk time, money, and personal data on a website."*

**Rule — five falsifiable tests for real vs stock theatre.** (1) Shot in the actual Kerobokan office, un-retouched, at a crop and light a stock library would not produce; background context is a feature. (2) Full name — a first name alone reads as a call-centre alias. (3) A specific, checkable role: "Ari — visa lead, files e-VOA and KITAS." (4) A response time that is a **measured, instrumented commitment** ("replies within 4 working hours, Mon–Sat"); if you cannot compute the median from your own outbox, do not print a number. (5) **The same face answers on WhatsApp after payment** — this is the whole mechanism. A named human on the verdict with a bot behind it is worse than no face at all: it converts a trust asset into a caught lie.

**Privacy.** Photo + name + role is personal data about an employee. Indonesia's **UU 27/2022 (PDP)**, enacted 17 October 2022, Pasal 4 lists *data pribadi umum* including full name and any data combined to identify a person; an identifiable facial image on a public page is in scope. Practically: written, specific, revocable consent **per surface** (an internal directory is not a public landing page); a documented takedown SLA on departure — a face still live after someone leaves is both a compliance failure and a trust liability, because clients ask for that person by name; never a personal handle behind the face, always a role inbox; and weigh harassment risk soberly, since this same face also delivers refusals.

**Avoid.** The avatar-row fad: five circular headshots with first names and "Our team is here for you". Theatre scales with headcount; a commitment names the person who will actually reply.

*`VERIFIED-LIVE`: https://www.nngroup.com/articles/about-us-information-on-websites/ · https://www.nngroup.com/articles/trustworthy-design/ · https://www.nngroup.com/reports/ecommerce-ux-trust-and-credibility/ · https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022*

---

## F8 — A "no" must hand over the next real door in the same breath

**Example.** GOV.UK `/y/canada/no/tourism` never stops at the refusal. It names the two instruments that *do* work (ETA, Standard Visitor visa), states precisely what the route cannot do — *"work for a UK company or as self-employed"*, *"claim public funds"*, *"live in the UK through frequent visits"*, *"marry or register a civil partnership without a Marriage Visitor visa"* — then what you must show at the border. No dead end anywhere in the artefact.

**Precedent worth borrowing.** US Regulation B, 12 CFR §1002.9(a)(2)(i): an adverse-action notice must contain *"A statement of specific reasons for the action taken"*; §1002.9(b)(2): it *"must be specific and indicate the principal reason(s) for the adverse action"*, and generic references to internal standards or *"failed to achieve a qualifying score"* are insufficient. It does not bind Bali Zero, but it is the strongest published standard in regulated interface design for what a refusal owes a person, and the right bar here.

**Rule — four obligatory parts.** (1) The determination, one sentence: *"Visa on Arrival will not cover this trip."* (2) **The specific reason, naming the answer that caused it**, with a Change link on that exact answer: *"Because you chose 90 days. VOA runs 30 days, extendable once to 60."* (3) **The route that does work, priced, on the same screen** — not "contact us", but "B211A social-cultural visa, IDR X, 5–7 working days." (4) A named human, same treatment as on the "yes" screen; do not downgrade the human on bad news. Part 3 is load-bearing: it is what stops them opening a new tab and finding the agent who says yes. Here the competitor for a "no" is not another honest agency — it is a scam.

**Avoid.** *"Unfortunately, you may not be eligible. Book a consultation to discuss your options."* A wall wearing a lead-capture form. An honest refusal costs you the sale but names a priced alternative; a fad refusal costs the user time and captures their number.

*`VERIFIED-LIVE`: https://www.gov.uk/check-uk-visa/y/canada/no/tourism · https://www.law.cornell.edu/cfr/text/12/1002.9*

---

## F9 — Borderline needs its own state, and it must never take payment

**Honest position: the evidence is thin.** I found no published, researched three-state eligibility verdict — GOV.UK smart answers are binary by construction. The nearest precedent is the mortgage Decision-in-Principle class, where the *entire artefact* is a provisional state (Nationwide: *"having a Decision in Principle does not guarantee your mortgage application will be successful"*; Lloyds: *"an agreement in principle does not guarantee how much we will lend you"*) — and I read those only as search snippets.

**Rule.** A borderline case gets its own state, never a weak yes: its own colour token, distinct from both others (not a lighter tint of "supported" — that scans as yes); its own verb, *"Needs a check"* / *"Perlu dicek"*, never *"Maybe"* or *"Likely eligible"*; a bounded next action with a person and a clock (*"[Name] checks this against the current rule and answers today"*); zero price on the check; and **no payment control on the screen**. A payment control on a borderline verdict converts uncertainty into revenue — the defining behaviour of the agents this company is being distinguished from.

**Avoid.** A confidence bar, likelihood meter, or amber gauge (see F5). A legitimate third state names a *person and a deadline*; a fad third state names a *number*.

*`FROM-MEMORY (unverified — search snippets only)`: Nationwide / Lloyds / NatWest Decision-in-Principle pages*

---

## F10 — The fad to refuse: the artificial "analysing your case…" delay

**The evidence is two-sided; both halves stated.** *For:* the labour illusion — Buell & Norton (Management Science, 2011) found travel-search users valued results **more** when made to watch the system apparently working, even where the wait was manufactured; TurboTax's "crunching your numbers" bar is the canonical production instance. And a 2025 ACM paper, *"Fake it 'til you load it: User Perceptions and Performance with Fast-Loading 'False Front' Web Pages"* (Proc. ACM Hum.-Comput. Interact., DOI 10.1145/3735593), reports false-front pages *"led to better ratings of responsiveness and speed, faster task completion, and higher preference"* against both a spinner and a skeleton screen.

**The distinction the fad collapses.** That 2025 paper is about showing the real page **sooner than it is ready** — a *speed* illusion, legitimate. The labour illusion is about **slowing a finished result down** so it looks expensive — a *cost* illusion, a deception. They point in opposite directions, and the fad cites the first to justify the second.

**Rule — any latency the user perceives must be latency that actually exists.** A verdict computed client-side from four answers renders in **under 300ms**; there is nothing to animate. If the price needs a server call, render what is already known (the four answers, the verdict skeleton) while it resolves — that is a legitimate false front. **A `DELAY_MS`, a `setTimeout` on the success path, or a progress animation whose duration is not bound to a real promise is a defect** — greppable, so make it a lint rule. Never print "checking with Immigration" unless a request is in flight to Immigration.

**Why here specifically.** The labour illusion buys a few points of perceived value; the downside for this audience is the whole thesis, because one caught lie on the verdict screen correctly re-prices every other claim on the page, including the true ones. The asymmetry is not close.

**Also refuse: confetti.** It celebrates a non-event — nothing has been granted, nobody approved, and the user is about to spend money. It is also the register of consumer growth apps, which is the visual language the scam sites borrow. The correct affect is calm competence: the answer, the price, the person, the receipt.

*`FROM-MEMORY (unverified — dl.acm.org 403 to my fetcher; title/venue/DOI corroborated by two independent search results)`: https://dl.acm.org/doi/10.1145/3735593 · `FROM-MEMORY (unverified — pubsonline.informs.org 403)`: Buell & Norton, "The Labor Illusion", Management Science, 2011*

---

## What I could not verify

*(26 pages were fetched; 22 distinct URLs are cited above as `VERIFIED-LIVE`. The four fetched-but-uncited pages were intermediate steps of the GOV.UK visa flow and NN/g's 1999 trust article, whose substance is carried by the 2016 successor cited in F6.)*

1. **CBP ESTA screen wording.** `help.cbp.gov/s/article/Article-1445` and `esta.cbp.dhs.gov/faq` both returned 403. The F3 clause comes from search snippets citing that page plus the DHS ESTA Privacy Impact Assessment. Very likely right; I did not read the page.
2. **ACM "false front" paper (DOI 10.1145/3735593).** 403. Title, venue and direction corroborated by two independent search results, but I did not read the abstract, the sample sizes, or — critically — whether the authors themselves warn against faking *work* rather than *speed*.
3. **Buell & Norton, "The Labor Illusion" (Management Science, 2011).** HBS and INFORMS URLs 403/404; cited from memory. Re-read the reversal condition (excessive manufactured wait reducing value) before leaning on the effect size.
4. **UK mortgage Decision-in-Principle wording** (Nationwide, Lloyds, NatWest). Search snippets only — consistent across three lenders and plausible, but treat as paraphrase until fetched.
5. **IRCC "Come to Canada" wizard disclaimer.** From third-party blogs, not `canada.ca`; not load-bearing above, do not repeat unchecked.
6. **Indonesian e-VOA official price and domain.** Verified only via The Bali Sun quoting Immigration — `evisa.imigrasi.go.id` returned empty content and `molina.imigrasi.go.id` did not resolve DNS here. **Confirm both against the official site before printing IDR 500.000 or any government URL live.** That number is the first thing a hostile reader checks, and it changes.
7. **UU 27/2022 Pasal 4 detail.** I fetched the official BPK record and the summary of Pasal 4's categories — not the full article text, the lawful-basis articles, or the transition period. Get a lawyer's read before publishing an employee photograph.
8. **NN/g on *named* staff specifically.** The 2019 research supports *photos of real employees over stock*. It does not, as far as I could verify, isolate the effect of a full name, a role, or a published response time — those three rules in F7 are my extrapolation from that finding plus the "who would be doing the cleaning" result. No measured conversion number behind them; A/B it if you want one.
9. **No measured conversion effect for anything here.** Baymard's 39% is an abandonment *cause* statistic, not a lift figure for a fee split. Nothing here should be quoted as "this raises conversion by X%".
10. **GOV.UK's own admitted gap.** The confirmation-pages pattern states: *"Research is needed on the best way to confirm transactions that are part of a wider user task."* The Visa Oracle verdict is exactly that — result, quote and checkout in one. The best design system in government has not solved this screen. Assume version one is wrong, and instrument it.
