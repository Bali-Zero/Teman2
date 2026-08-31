---
lane: L07 — Looking legitimate in a market full of scams
seat: Claude Opus 5 (1M context), xhigh effort
date: 2026-08-31
sources_verified_live: 26
sources_from_memory: 3
adversarial_review: exempt-raw-lane-output-synthesis-carries-the-review
---

## Executive summary

1. **A trust signal is worth exactly what it costs to fake.** Chrome retired the padlock in 2023 after its own research found only 11% of users understood it and "nearly all phishing sites use HTTPS." Every signal on Bali Zero's home page today is in that category.
2. **The copycats have already stolen the honest playbook.** The fake e-VOA site Indonesian Immigration publicly named in 2022, `indonesia-evoa.com`, is *still live* — and now carries a "not affiliated with the Government" disclaimer and an outbound link to `evisa.imigrasi.go.id`. Disclosure alone no longer separates you from them.
3. **The one thing it cannot fake is identity.** Its own About page reads "www.indonesia-evoa.com belongs to ." and "Our headquarters are located at , phone ," — unfilled template variables. Counter-move: a company number a stranger can look up on `ahu.go.id`, a street address, named humans with licence numbers.
4. **Price-before-data is the sharpest discriminator.** The copycat charges "up to $92" plus government fees, revealed only on the payment page. GARUDA VOA must resolve to one number before a single field is filled, with the government's own price beside it.
5. **Kill the star-rating strip.** Fake reviews became a banned practice under the UK DMCC Act in April 2025; on 27 March 2026 the CMA opened investigations into five businesses over ratings, fines up to 10% of global turnover. A self-printed "4.9 ★ · 693 Reviews" is now the tell, not the proof.

---

## 1. The law of signal death: a signal dies when it becomes free

**Named example.** Chromium Blog, "An Update on the Lock Icon", 2 May 2023 — `https://blog.chromium.org/2023/05/an-update-on-lock-icon.html` — `VERIFIED-LIVE (fetched 2026-08-31)`.

**The measurable rule.** Verbatim: "As late as 2013, only 14% of the Alexa Top 1M sites supported HTTPS. Today… over 95% of page loads in Chrome on Windows are over a secure channel." And: "our research in 2021 showed that **only 11% of study participants correctly understood the precise meaning of the lock icon**… **nearly all phishing sites use HTTPS, and therefore also display the lock icon**. Misunderstandings are so pervasive that many organizations, including the FBI, publish explicit guidance that the lock icon is not an indicator of website safety."

The spine of this lane: **discriminating power is inversely proportional to adoption cost.** Any signal you can add for free this afternoon, a scammer added this morning.

Apply the test to `https://balizero.com/` (`VERIFIED-LIVE (fetched 2026-08-31)`). Live today: "4.9 ★ · 693 Reviews · 5,000+ Clients · Licensed Notary & Tax Agent" (twice, as a marquee); "Filed this month: 47 KITAS, 9 PT PMAs · Office in Kerobokan"; "Licensed konsultan pajak · Registered PPJK · Since 2019"; a "Google Reviews 4.9 · 693 reviews" block; a testimonial signed "— Marco R. · Ital[y]"; `<title>` "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia". **Cost to fake, each: zero.** Not one number there is checkable against a third party. Signal for signal, it is what the scam sites print.

**What to steal.** Nothing — this is the audit that licenses the rest. Make it a standing rule on all three surfaces: *for each claim, name the external record that would falsify it.* No record → decoration, sitting where a checkable fact should be.

**What to avoid.** The fad response is to *add* signals — an SSL badge, a "100% secure" lockup, a "Verified" pill. That is the copycat's own instinct. Tell them apart by asking **who renders the artifact**: your own server → decoration; a registrar, regulator or platform → evidence.

---

## 2. Autopsy of a live fake: what the copycat can and cannot do

**Named example.** `https://www.indonesia-evoa.com/` and `/about` — `VERIFIED-LIVE (fetched 2026-08-31)`. Not hypothetical: the Yogyakarta Class I Immigration Office publicly named this domain — "Situs www.indonesia-evoa.com palsu yang dibuat oleh oknum-oknum tidak bertanggung jawab untuk mengeruk keuntungan" (`https://jogja.imigrasi.go.id/situs-resmi-pengurusan-e-voa-hanya-di-molina-imigrasi-go-id/`, `VERIFIED-LIVE`, page dated Dec 2022). It is still serving traffic in August 2026, on AWS CloudFront (13.35.1.x) — **the same CDN range fronting the real `evisa.imigrasi.go.id`**. No infrastructure signal separates them.

**What it has.** From the fetched HTML: a footer disclaimer ("not affiliated with the Government or its sponsors"); an outbound link to `https://evisa.imigrasi.go.id/`; the concession "An application can also be submitted for a lower cost through the Government's website here"; 12 languages; "100% Error Free Guarantee"; "Application denial refund policy"; "24/7/365"; "More than 50 specialized employees"; "Since 2014"; "offices… located in Europe and the United States"; "securely encrypted by Secure Sockets Layer (SSL) software"; a table scoring itself against "Government"; production analytics (Amplitude, Datadog RUM). **It has adopted the entire honest-intermediary disclosure playbook.**

**What it does not have.** Its About page, verbatim:

> "www.indonesia-evoa.com belongs to ."
> "Our headquarters are located at , phone , email info@indonesia-evoa.com"
> " assists clients from over 40 countries"

Three unfilled template variables. It runs a shared multi-country copycat template and **has no legal identity to substitute in.** That is this lane's empirical finding: a copycat can generate every trust signal in existence except a name, an address, and a registration number that resolves in someone else's database.

**What to steal.** Build the identity block the template cannot fill, on all three surfaces — replacing today's "Office in Kerobokan · Licensed konsultan pajak · Registered PPJK":

- **PT BAYU BALI NOL**, full legal name, with *"look us up yourself"* and a link to `https://ahu.go.id/pencarian/profil-pt` (`VERIFIED-LIVE` — Ditjen AHU's public company-profile search, free). Add the NIB and `https://oss.go.id/` (`VERIFIED-LIVE`).
- **The street address in full**, plus a map. "Office in Kerobokan" has the same information content as "offices in Europe and the United States."
- **Licence numbers, not licence adjectives.** "Licensed konsultan pajak" is a copycat-grade claim; *"Konsultan Pajak, izin praktik nomor …"* is not. Same for PPJK: publish the NPPPJK.
- **Named humans.** The copycat says "visa experts" and "50 specialized employees" — uncountable nouns. One named consultant with a photograph and a role beats fifty anonymous experts.

**What to avoid.** The fad version is the "Our Team" grid of stock or AI-generated headshots with first names only, plus a badge row. One test: **is the name attached to a third-party-issued credential, and is its number printed?** A face with a first name is decoration.

---

## 3. Price before data — where the ASA already drew the line

**Named example.** UK CAP/ASA copycat-website enforcement — `https://www.asa.org.uk/news/copycat-websites-update.html` and `https://www.asa.org.uk/news/copycat-websites.html`, both `VERIFIED-LIVE (fetched 2026-08-31)`. Letters 23 September 2014, monitoring from 28 October 2014; rulings named include Europe EHIC Services Ltd and TADServices Ltd.

**The measurable rule.** It is a *placement* rule, and it is precise. Non-official sites may not use "official" in the service description or site name, display crown emblems, mimic official design, or use "HM"/"government"/"gov" terms. Disclosure must appear **"immediately alongside every call to action … and the most prominent price statements on each page"**, "clearly worded" and "presented separately from other information to ensure it is prominent", explaining "the non-official nature of the service" *and* "the additional cost" versus the official channel.

`indonesia-evoa.com` fails exactly there: footer-only disclosure, no price on the page. From its About: "our standard processing service fee of **up to** $92 and, when selected by the Customer, our 'Urgent processing fee', **in addition to** the Government fees" — immediately after "There are no surprises and no hidden extra charges", resolved only where "The total cost … will be shown on the payment page." **You must complete the entire form before you learn the price.**

**What to steal.** On the **GARUDA VOA landing**, adopt the ASA rule as spec and exceed it:

- IDR 790.000 rendered **above the first form field**. The four questions determine eligibility, not price; there is no reason to withhold it.
- Adjacent to the price and repeated beside every CTA (not in a footer): *"Bali Zero is not Indonesian Immigration. You can apply yourself at evisa.imigrasi.go.id and pay only the government fee. Our price includes that fee plus IDR X for us to file, check and track it."* The official channel's published tourist-visit-visa fee is IDR 1.500.000, payable via SIMPONI or Mastercard/Visa/JCB only (`https://evisa.imigrasi.go.id/front/faq/dd5c2220-28a7-4024-9a10-82f30a09e0d2`, `VERIFIED-LIVE`) — which is why QRIS/BCA/Mandiri rails are a *service* difference worth stating plainly, not a legitimacy claim.
- **Acceptance test, binary:** can a stranger on a 360px phone learn the total price without typing anything? If no, the surface fails. Same rule on the **Visa Oracle verdict**: price and the not-the-government line belong in the verdict card, not a step later.

**What to avoid.** The fad version is the comparison table — the copycat's signature device, a "Us vs. Government" grid manufacturing features the government "lacks" (photo editing, 24/7 email, "recovery via email"). If you must compare, compare **price and time only**, state that the government wins on price, and say what you actually add.

---

## 4. The device: publish how to complain about you

**Named example.** SRA Transparency Rules, in force **11 April 2025** — `https://www.sra.org.uk/solicitors/standards-regulations/transparency-rules/` and `https://www.sra.org.uk/consumers/choosing/look-out-for-our-logo/`, both `VERIFIED-LIVE (fetched 2026-08-31)`.

**The measurable rule.** Firms must display "its SRA number and the SRA's digital badge" "in a prominent place on its website"; state "authorised and regulated by the Solicitors Regulation Authority" on letterhead and emails; publish "the total cost of the service or, where not practicable, the average cost or range of costs", the basis of charges, disbursements, VAT treatment, "what services are included in the price displayed, including the key stages of the matter and likely timescales"; and publish "details of its complaints handling procedure including, details about how and when a complaint can be made to the Legal Ombudsman and to the SRA."

Two mechanisms matter. **The badge resolves outward** — "The firm is what it says it is. You can check this by clicking on the logo." A copied image does not resolve. And — the strongest device in this report — **the firm publishes the route to escalate above itself.** No scam site will ever name who outranks it, because the escalation route is the thing it exists to avoid.

**What to steal.** On the **home page** footer and **GARUDA VOA**: an "If something goes wrong" block naming (a) the internal complaint path, with a named person and a response time, and (b) the external escalation — Immigration's public-complaint channel (`Pengaduan / Lapor!` is a standing nav item on `https://www.imigrasi.go.id/`, `VERIFIED-LIVE`) and the consumer route under UU 8/1999. Steal the *scope* discipline too: publish what is included, the key stages, the timescale — and **what you cannot do.** "We cannot influence an Immigration decision. If it is refused, here is what you get back and what you do not." Admitting the limit is the cheapest expensive-to-fake signal available, because the copycat's whole pitch is "100% Error Free Guarantee".

**What to avoid.** Do not build a Bali Zero-branded "verified"/"licensed" badge. A self-issued badge is the SSL-seal move (`indonesia-evoa.com`: "securely encrypted by Secure Sockets Layer (SSL) software"). Test: **who serves the asset, and where does the click land?**

---

## 5. The authenticity banner — invert it, do not copy it

**Named examples.** USWDS banner component — `https://designsystem.digital.gov/components/banner/`, `VERIFIED-LIVE (fetched 2026-08-31)`. And Ditjen Imigrasi's equivalent, read from the live markup of `https://www.imigrasi.go.id/` — `VERIFIED-LIVE (fetched 2026-08-31)`.

**The measurable rule.** USWDS: an accordion headed "An official website of the United States government" + "Here's how you know", shown "on every page", using "the provided text without customization", `aria-label="Official website of the United States government"`, passed WCAG 2.1 AA. It teaches exactly two facts: "Official websites use .gov" and "Secure .gov websites use HTTPS — A lock or https:// means you've safely connected."

Indonesia has cloned the pattern, with specs I read out of the live HTML: a 9pt strip, `min-height: 20px`, white ground above a 60px dark-blue header, collapsed by default (`.panel { display: none }`), opened by a `bi-info-circle-fill` trigger, holding two items — (1) "Secara umum, situs web resmi kementerian/lembaga Pemerintah RI berakhiran **.go.id**"; (2) "Situs web yang aman menggunakan HTTPS menampilkan icon(🔒)".

**The trap.** Fact (2), on both banners, is the padlock heuristic Chrome retired in 2023 *because nearly all phishing sites display it*. The Indonesian government is, today, teaching the public a test that `indonesia-evoa.com` passes. Any Bali Zero content repeating "look for the padlock" arms the scam.

**What to steal.** Build the **inverse banner** on every page of all three surfaces — same anatomy (~20px, collapsed, "Here's how you know" trigger), opposite content:

> **Bali Zero is a private agency. It is not Indonesian Immigration.** ▾
> · The government's site is **evisa.imigrasi.go.id**. Only **.go.id** is government.
> · Our price is **IDR 790.000**, including the government fee of IDR X. You can pay the government directly and pay less.
> · We are **PT BAYU BALI NOL**, [address], NIB [n] — check us at ahu.go.id.

This replaces the marquee proof strip: same job (establishing what kind of thing this site is), done with facts that resolve outward instead of claims that resolve inward. On the Bahasa version budget ~30% extra width — "Situs web resmi kementerian/lembaga Pemerintah RI berakhiran .go.id" is materially longer than its English equivalent, which is why Imigrasi's own strip drops to `0.65rem` under 425px.

**What to avoid.** Never copy the *positive* form ("An official website of…", garuda emblems, `.go.id`-mimicking colourways). The ASA rules make this the defining copycat offence and the charter already forbids "official partner". The difference is one word: the banner must say what you are **not**.

---

## 6. Should an honest agency publish "how to spot a fake"? Yes — with one constraint

**Named example.** A direct competitor already does: Flado Indonesia, "Phishing Emails Claiming to Be from Indonesian Immigration (December 2025)" — `https://flado.id/2025/12/05/phishing-emails-claiming-to-be-from-indonesian-immigration-december-2025-how-to-identify-a-fake-and-protect-yourself/`, `VERIFIED-LIVE (fetched 2026-08-31)`.

**What it gets right.** *Falsifiable string comparison*, not vibes: the legitimate sender is `no-reply@notif.imigrasi.go.id`; the phishing sender is `noreply-imigrasigoid@evisaidnglobal.online`, with the mechanism explained — "Fraudsters insert 'imigrasigoid' into the address to visually mimic the official domain." It names the payment tell (USD/crypto demanded where Indonesian immigration charges IDR). It converts the warning into a service: "forward the email to us — we will verify its authenticity for free."

**What it gets wrong — the opening.** It "does not cite its own business registration, license numbers, or official accreditation." It teaches the reader to verify everyone except the author.

**Counter-evidence, stated honestly.** Scam-warning content plausibly raises anxiety at the moment of payment and could depress conversion; I found **no** controlled study measuring that on an intermediary's own conversion, and will not invent one. What the evidence *does* support is that **staleness kills credibility**: NN/g's four factors (`https://www.nngroup.com/articles/trustworthy-design/`, Aurora Harley, 8 May 2016, `VERIFIED-LIVE`) make "comprehensive, correct and **current** content" a top-level factor, and Nielsen's original (`https://www.nngroup.com/articles/communicating-trustworthiness/`, 6 March 1999, `VERIFIED-LIVE`) is blunt: "a single violation of trust can destroy years of slowly accumulated credibility." Two live failures of exactly this kind:

- **Bali Zero's dateline reads "Bali Zero · Dispatch · April 2026 · Kerobokan"** — four months stale today. A dateline is a freshness promise; a stale one is a self-inflicted hit on the highest-authority line of the page.
- **The Yogyakarta Immigration page still tells the public `molina.imigrasi.go.id` is the *only* official e-VOA site. That hostname resolves NXDOMAIN** (verified via `dig` and `nslookup` against 8.8.8.8, 2026-08-31). The government's own anti-scam advice points at a dead domain — the kind a squatter buys.

**What to steal.** Publish a **dated, versioned** "How to check any Bali visa agent — including us" page, cross-linked from GARUDA VOA. Structure it as a checklist the reader applies *to Bali Zero first*: company number → look it up; address → open the map; licence number → here it is; price → here is the government's; "what we cannot do" → here. Stamp it `Last checked: <date>` and wire that to a real recurring check — the only thing worse than no warning page is one pointing at a dead domain.

**What to avoid.** Fear-marketing: "BEWARE! 9 SCAMS THAT WILL RUIN YOUR BALI TRIP", red-alert aesthetic, every danger resolving to "use an agency (us)". One property separates them: **does the page make Bali Zero itself checkable, or only competitors suspect?** A checklist that cannot be turned on its author is advertising in a warning costume.

---

## 7. The Indonesian legal frame — the charter bans have statutory hooks

**Named example.** UU No. 8 Tahun 1999 tentang Perlindungan Konsumen, status **Berlaku** — `https://peraturan.bpk.go.id/Details/45288/uu-no-8-tahun-1999`, full text at `/Download/33784/`, both `VERIFIED-LIVE (fetched 2026-08-31)`. (Pasal 31 was the subject of Constitutional Court ruling 235/PUU-XXIII/2025 — that concerns BPKN's institutional powers, not the advertising articles.)

**The measurable rule.** The four charter bans are not house style; each maps to a subsection, verbatim:

| Charter ban | Hook | Verbatim |
|---|---|---|
| "official partner" | **Pasal 9(1)(d)** | "…dibuat oleh perusahaan yang mempunyai sponsor, persetujuan atau **afiliasi**" |
| "official / approved" | **Pasal 9(1)(c)** | "…telah mendapatkan dan/atau memiliki **sponsor, persetujuan**…" |
| "guaranteed approval" | **Pasal 9(1)(k)** | "menawarkan sesuatu yang mengandung **janji yang belum pasti**" |
| "zero overstay risk" | **Pasal 9(1)(j)** | "menggunakan **kata-kata yang berlebihan**, seperti aman, tidak berbahaya, **tidak mengandung risiko**… tanpa keterangan yang lengkap" |

Pasal 10 separately bars untrue or misleading statements about "harga atau tarif" and about "kondisi, tanggungan, **jaminan**, hak atau ganti rugi". This is not soft: **Pasal 62(1)** attaches up to **5 years' imprisonment or a fine up to Rp 2.000.000.000**, and **Pasal 63** adds supplementary penalties including "perintah penghentian kegiatan tertentu" and **"pencabutan izin usaha"** — revocation of the business licence.

**What to steal.** (a) Convert the charter into a **CI-checkable string blocklist** across all three surfaces — "official partner", "resmi", "guaranteed", "dijamin", "100%", "no risk", "tanpa risiko", "#1", "first reseller" — failing the build on a hit. (b) Note the collateral catch: the live `<title>` "Bali Zero | **#1** Visa & PT PMA Experts in Bali, Indonesia" is an unverifiable superlative in the highest-weight string on the site, squarely in the Pasal 9(1)(j) family. Replace with something falsifiable: "Bali Zero — PT PMA, KITAS and tax filing in Bali. Licensed. Kerobokan."

**What to avoid.** Over-rotating into legalese. Pasal 9(1)(j)'s escape hatch is "tanpa keterangan yang lengkap" — *without complete explanation*. The compliant form of a strong claim is a strong claim **with its conditions attached**, not a weak claim. "We filed 47 KITAS this month" is fine with the period, definition and date stated; "#1" is not fine at any length.

**Honest gap.** Unlike Australia (MARA) or the UK (SRA), **Indonesia has no public register of licensed visa agents.** `https://www.pajak.go.id/id/konsultan-pajak` (`VERIFIED-LIVE`): the licensing regulation describes practice-licence cards and association membership but establishes **no public searchable lookup**; IKPI (`https://ikpi.or.id/`, `VERIFIED-LIVE`) is a members' association with a login-gated area. Bali Zero's checkable anchors are therefore the *company* (AHU/OSS) and the *customs brokerage* (PPJK/NPPPJK), not a visa-agent register — because none exists. **Say so on the page.** Naming the absence of a register is a signal no copycat will copy.

---

## 8. The 2026 negative signal: the self-printed star-rating strip

**Named examples.** CMA/Google undertakings, 24 January 2025 — `https://www.gov.uk/government/news/cma-secures-important-changes-from-google-to-tackle-fake-reviews`. CMA investigations into Autotrader, Feefo, Dignity, Just Eat and Pasta Evangelists, **27 March 2026** — `https://www.gov.uk/government/news/fake-and-misleading-reviews-5-businesses-under-cma-investigation`. Both `VERIFIED-LIVE (fetched 2026-08-31)`.

**The measurable rule.** Under the Digital Markets, Competition and Consumers Act 2024, fake and undisclosed-incentivised reviews became **banned practices in April 2025** — automatically unfair, fines "up to 10% of global turnover". The March 2026 cases are instructive because they are not about invented reviews: Just Eat, over whether "its ratings system has **inflated** certain restaurants' and grocers' star ratings"; Autotrader/Feefo, over whether 1-star reviews "were not published"; Pasta Evangelists, over discounts "in exchange for leaving 5-star reviews … without this being disclosed". Google separately agreed that "businesses found to be boosting their star ratings via fake reviews will have prominent 'warning' alerts added to their Google profiles." Context: 89% of consumers use reviews; £23bn of UK spend is influenced by them.

**Consequence for design.** In eighteen months the aggregate rating moved from *proof* to *contested claim*. The artifact that has gone specifically negative is the **self-hosted rating string** typed into your own HTML: unverifiable, now a regulated claim class, and the most-cloned element on scam sites. Bali Zero runs it twice, as a scrolling marquee, plus an initial-only testimonial ("— Marco R. · Ital…") — the canonical fake-testimonial format.

**What to steal.** On the **home page**, replace the marquee proof strip with the inverse banner (§5) plus the identity block (§2). If a rating survives anywhere it must be **linked outward** to the Google Business Profile, so Google's copy — the one subject to the warning-label regime — is the authority, not yours. Keep "Filed this month: 47 KITAS, 9 PT PMAs" *only* if dated ("as of 31 Aug 2026"), defined, and generated from the actual filing table; an undated live counter is indistinguishable from the fake-urgency counters regulators are now targeting. On **Visa Oracle verdict** and **GARUDA VOA**, social proof should not appear at all: at the point of a regulatory verdict, "5,000+ clients" answers a question nobody is asking, and the space belongs to the price, the named human and the escalation route.

**What to avoid.** The tempting middle path — a Trustpilot/Google review *widget* — beats static text but is still a third-party badge in a period when review platforms themselves (Feefo) are under investigation. Separate good from bad by asking: **could this element still render if the underlying reviews vanished tomorrow?** Static "4.9 ★" would. A live link would not. Prefer the one that breaks.

---

## What I could not verify

- **The official e-VOA fee.** I verified IDR 1.500.000 for a 60-day extendable visit visa on the official FAQ, and that payment runs via SIMPONI / Mastercard / Visa / JCB. I did **not** find the e-VOA fee on `evisa.imigrasi.go.id`; deep paths 404'd. The IDR 790.000 vs government-fee comparison in §3 needs the exact current figure confirmed before it is printed. `FROM-MEMORY (unverified)`: I believe it is IDR 500.000 — **do not publish on my word.**
- **"38% of participants failed to notice any trust seals"** (Kirlappos/Sasse-lineage trust-seal study, ~2012). From a search-result summary; Springer paywalled the chapter on fetch. `FROM-MEMORY (unverified)`.
- **Baymard's "19% abandoned checkout because they didn't trust the site with their credit card information"** — fetched at `https://baymard.com/blog/perceived-security-of-payment-form`, but the page is dated Oct 2016 with partial 2023/2025 updates and exposed no clean per-badge percentages. Treat 19% as directional, badge rankings as unverified. Secondary blogs claiming "Baymard: badges lift conversion 15–30%" — not on Baymard itself; would not cite. `FROM-MEMORY (unverified)`.
- **Baltuttis & Teubner (2024), *Computers & Security* 144:103940** — abstract and DOI verified at `https://depositonce.tu-berlin.de/items/882e2204-5692-4617-bb71-78400416bb30` (`VERIFIED-LIVE`), but the record carried **no sample size and no effect sizes**. I deliberately attached no numbers to it.
- **The state of modern web-credibility research — the honest weak point.** The canonical citable work is *old* (Stanford/Fogg ~2002; Nielsen 1999; NN/g 2016). I could not surface a 2020–2026 replication of comparable authority (WebSearch budget exhausted mid-lane); the strongest recent numbers I fetched come from browser-vendor and regulator sources (Chrome 2023; CMA 2025–26; APWG Q4 2025: 853,244 phishing attacks, published 18 Feb 2026, `https://docs.apwg.org/reports/apwg_trends_report_q4_2025.pdf`, `VERIFIED-LIVE`) rather than academic UX. **Do not let anyone present "the research says X about trust signals" as settled 2026 knowledge.** Defensible here: the mechanism (signal death), the regulator rules (ASA, SRA, CMA, UU 8/1999), the live autopsy of `indonesia-evoa.com`.
- **`indonesia-evoa.com`'s current legal status.** I verified the 2022 Immigration statement naming it and that the site is live today with the quoted content — not whether it has since been sanctioned, changed hands, or become a lawfully-disclosed intermediary. In published copy call it "the site Immigration named in 2022, still live today, with these characteristics" — not "a scam site".
- **PSE/Komdigi registration.** `https://pse.komdigi.go.id/` is live but its search is JS-rendered; every path I probed returned the SPA shell. Confirm the register is actually publicly searchable before publishing a PSE number as a checkable signal.
