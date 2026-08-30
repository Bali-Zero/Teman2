# SYNTHESIS — sixteen lanes, read together

**Corpus**: twelve web-grounded lanes (L01–L12) + four cross-family seats (X-agy Gemini 3.1 Pro, X-codex GPT-5.6, X-kimi Kimi K3, X-qwen Qwen 3.8 Max). Aggregate source ledger as declared by the lanes themselves: **254 `VERIFIED-LIVE`, 111 `FROM-MEMORY (unverified)`**.

**On `X-agy.md`**: **real, not truncated.** The run log records `agy rc=0 bytes=12021 secs=848`, `run.err` is empty, and the file terminates on a complete final sentence of a complete final section. It carries every required part — frontmatter, five-point summary, four findings in the four-part shape, a "what I could not verify" section. Its only defect is an unclosed opening ` ```markdown ` fence. It is short (1,772 words vs a corpus median near 3,900) **by the model's own choice**, and two things follow that matter: it delivers four findings where the other lanes deliver six to ten, and its five `VERIFIED-LIVE` citations are **bare homepage fetches with no quoted text** — which does not meet the CONTRACT's own sourcing bar ("fetch the page and quote it"). Treat X-agy as a strong *direction* paper with nominal verification, not as evidence. `X-kimi.md` has a separate, cosmetic defect: the file opens with three lines of CLI transcript chatter and the report body is indented two spaces.

---

## 1. Convergences that matter

Ranked by how many independent lanes reached the conclusion, weighted by consequence. None of these lanes could see each other's work.

### C1 — Motion applied to a settled number is a lie, and it is greppable. **(8 lanes)**

**Lanes**: L02 §4 · L04 F7/F8 · L05 F10 · L06 F1/F5 · L08 §2 · L12 §2/§4.2 · X-kimi Device 9 · X-codex F5.

Eight lanes, working on colour, typography, price, verdict, checkout, social proof, motion and "why a page feels expensive", independently arrived at the same prohibition and — remarkably — at the same *dividing line*. L04: "legitimate motion happens *before* first meaningful paint or in response to *the user's own input*… Illegitimate motion happens *to* a settled number." L12 states it as state: "The dividing line is whether the delay communicates real state or manufactures a fictional one." L05 turns it into an engineering artefact: "**A `DELAY_MS`, a `setTimeout` on the success path, or a progress animation whose duration is not bound to a real promise is a defect** — greppable, so make it a lint rule."

**Most load-bearing evidence**: L05's asymmetry argument, which is the only one that explains *why the effect size doesn't matter*. The labour illusion (Buell & Norton 2011, `FROM-MEMORY` — INFORMS 403'd) may genuinely buy a few points of perceived value; L05's answer is that "one caught lie on the verdict screen correctly re-prices every other claim on the page, including the true ones. The asymmetry is not close." L05 also isolates the equivocation the fad depends on: the 2025 ACM "false front" paper (DOI 10.1145/3735593, `FROM-MEMORY` — dl.acm.org 403'd) is about showing a real page *sooner than it is ready* — a **speed** illusion. The labour illusion slows a *finished* result down — a **cost** illusion. "They point in opposite directions, and the fad cites the first to justify the second."

The only `VERIFIED-LIVE` anchor under any of this is L12's fetch of NN/g's skeleton-screens and response-times articles — which, L12 notes with unusual honesty, "cites 1968–1991 (Miller, Card/Newell)" and contains **no skeleton or spinner research at all**, so treating it as a pattern guide "overstates what NN/g actually published."

### C2 — A trust signal is worth exactly what it costs to fake, so only outward-resolving artifacts count. **(7 lanes)**

**Lanes**: L01 F9 · L05 F6 · L07 §1/§2/§4/§8 · L08 §1/§2/§4 · L10 §7 · X-codex F2/F4 · X-qwen §3 (partially — see K3).

**Most load-bearing evidence**: Chrome's own retirement of the padlock, quoted by L07 verbatim from the Chromium Blog (`VERIFIED-LIVE`): "only 11% of study participants correctly understood the precise meaning of the lock icon… **nearly all phishing sites use HTTPS, and therefore also display the lock icon**." L07 generalises this into the spine of the whole corpus: "**discriminating power is inversely proportional to adoption cost.** Any signal you can add for free this afternoon, a scammer added this morning."

The same mechanism appears three more times from unrelated directions and nobody connected them: L10 §7 finds that an accessibility overlay is now "evidence used *against* a defendant, not a shield"; L07 §8 finds the star-rating strip moved "from *proof* to *contested claim*" in eighteen months under the UK DMCC Act; L08 §2 finds that a status page showing *past incidents* "builds more trust than one that shows none, because a spotless history reads as either lucky or hidden." The unifying rule, which no single lane states: **a signal is evidence only if something outside your control could have made it come out differently.** L07's operational test is the sharpest form: "**who renders the artifact**: your own server → decoration; a registrar, regulator or platform → evidence."

### C3 — The fad, the scam and the lookalike mockup are the same defect: an artefact that cannot name its input. **(6 lanes, with the strongest independent corroboration in the corpus)**

**Lanes**: L01 F9 · L02 §6 · L03 §8 · L09 §6 · L12 §6 · X-agy §3.

**Most load-bearing evidence**: **L01 and L03 independently traced the same 2026 cliché to the same 2019 origin from different sources.** L01, citing 925studios (`VERIFIED-LIVE`): "**The blue-to-purple gradient is the single loudest AI tell in 2026**," traced to "Tailwind's indigo-500 default." L03, citing prg.sh and related 2026 commentary via search index: the same gradient, traced to "Tailwind UI's default `bg-indigo-500` button, apologized for publicly by its creator." Two lanes, two source families, one origin. That is the closest thing to replication this corpus contains.

Both quote the same feedback mechanism, in different words. L01's source: a model "returns the median of every example in its training data." L03's: "When a striking site with a purple gradient gets enough attention, it makes its way into the next round of training data, which teaches the next generation of models that purple gradients are even more normal than before."

L01 supplies the test that generalises it and is the most useful single sentence in the corpus: "**what input produced this, and would a different input produce something different?** An indigo→purple gradient has no input — it is a constant. A glass panel's opacity has no input — it is a taste. A surface at `oklch(21.3% κ·1.3 H_base)` has two inputs, both defensible, both variable. **Anything in this design that cannot name its input is the fad.**"

L09 adds an independent detection rule with a different mechanism: "A trend that arrives and gets its failure mode documented in the same publishing cycle is a trend that peaked before it shipped widely" — evidenced by one 2026 trends article naming bento grids *and* flagging their "operational paradox" in the same piece. L12 adds the supply-side cause: "the barrier to entry dropped from 'hire a WebGL engineer' to 'one CSS property,' and the technique got used because it's now easy, not because it serves the page."

### C4 — The one thing a copycat cannot generate is a legal identity, and the identity must be reachable *before* the payment wall. **(6 lanes)**

**Lanes**: L05 F5/F7 · L07 §2 · L08 §4 · L11 §1 · X-codex F4/F6 · X-qwen §3/§6.

**Most load-bearing evidence — and the single strongest empirical finding in the entire corpus**: L07's live autopsy of `indonesia-evoa.com`, the fake e-VOA site Yogyakarta Immigration publicly named in December 2022 and which is **still serving traffic in August 2026, on the same AWS CloudFront range that fronts the real `evisa.imigrasi.go.id`** (`VERIFIED-LIVE`). It has adopted the entire honest-intermediary playbook: a non-affiliation disclaimer, an outbound link to the government site, the concession that "An application can also be submitted for a lower cost through the Government's website here," twelve languages, SSL language, "More than 50 specialized employees." What it does not have, verbatim from its own About page:

> "www.indonesia-evoa.com belongs to ."
> "Our headquarters are located at , phone , email info@indonesia-evoa.com"

Three unfilled template variables. L07's conclusion: "a copycat can generate every trust signal in existence **except a name, an address, and a registration number that resolves in someone else's database**."

Four lanes independently converge on where that identity must sit. L11 (`VERIFIED-LIVE` from oss.go.id): OSS "literally lists 'WhatsApp,' 'Email,' 'Tatap Muka' [face-to-face], 'Panggilan Video' [video call] as first-class contact options, not a buried footer link," and names the inverse as "the single clearest tell of a low-trust site to this audience." X-codex: "Put the named case owner beside the passport request, even if formal assignment occurs after payment." X-qwen: "for many Indonesian users, self-serve plus a reachable human *is* the product." And L05 finds the named human is simultaneously a legal instrument: a human empowered to override "*is* the Art. 22(3) safeguard, and a conversion asset rather than a compliance cost."

L05 also supplies the falsifier the other three lack: "**The same face answers on WhatsApp after payment** — this is the whole mechanism. A named human on the verdict with a bot behind it is worse than no face at all: it converts a trust asset into a caught lie."

### C5 — The price must be legible before a single field is filled, and no payment control may sit on an uncertain state. **(6 lanes)**

**Lanes**: L04 F1 · L05 F6/F9 · L06 F4 · L07 §3 · X-codex F2/F4 · X-qwen §1.

**Most load-bearing evidence**: L07's reading of the UK CAP/ASA copycat-website rulings (`VERIFIED-LIVE`), which is a *placement* rule with a defined granularity — disclosure must appear "**immediately alongside every call to action … and the most prominent price statements on each page**," "presented separately from other information to ensure it is prominent." L07 then shows the named fake failing exactly there: "our standard processing service fee of **up to** $92 … **in addition to** the Government fees," resolved only "on the payment page." L07's verdict: "**You must complete the entire form before you learn the price.**" And its acceptance test, binary and runnable by one person in one minute: "**can a stranger on a 360px phone learn the total price without typing anything? If no, the surface fails.**"

Baymard supplies the cost from the other side (L04 and L06 fetched it independently): 70.22% average cart abandonment across 50 studies, with **40% citing extra costs revealed too late** as the top non-browsing reason, and "33% of the benchmarked mobile sites fail to display the total order cost – at any point during checkout – before asking for credit card data."

Two lanes then add the clause the price-lanes missed: **the price is not a payment prompt.** L05 F9 on a borderline verdict: "zero price on the check; and **no payment control on the screen**. A payment control on a borderline verdict converts uncertainty into revenue — the defining behaviour of the agents this company is being distinguished from." X-codex reaches the same place from the state machine: ambiguity "must open a human-review lane with no payment, not force a false yes/no."

### C6 — Hierarchy carried by tone alone does not survive this audience's conditions. **(6 lanes)**

**Lanes**: L01 F7/F8 · L02 §3 · L03 §4 (partially — see K2) · L10 §2/§6 · X-agy §1 · X-kimi Device 8.

**Most load-bearing evidence**: not the perceptual argument but the **mechanical** one, from L10 §6 (`VERIFIED-LIVE`, MDN): under `@media (forced-colors: active)`, "**box-shadow is force-stripped to none — don't rely on it for affordance**," and system colours override author colours. That is not a preference or a percentile; it is a rendering guarantee. Every tonal-elevation and inset-highlight technique in the corpus evaporates for that user, unconditionally.

L01 supplies the second, environmental proof with its own ambient-flare model (constants `FROM-MEMORY` and explicitly flagged by L01 as engineering estimates, not fetched): at ~10,000 lux on a 400-nit phone, a Material-3 elevation step reaches **1.05:1** and a dark hairline **1.15:1** — both invisible — while body text survives at 3:1, "badly." L01's own note that WCAG's contrast formula embeds a 0.05 flare constant corresponding to "~1,400 lux on a 400-nit phone — a bright office, not a Bali street" is the mechanism, and it is published maths even where its constants are estimates.

L10 §2 adds the third: APCA's own documentation states WCAG 2's ratio "far overstates contrast for dark colors" and "**cannot be used for guidance designing dark mode**." L01 measures what that means for this brand: `#C8102E` as ink gives **Lc +77.1 on white but Lc −24.0 on `#141218`**, and "I searched the whole hue for a single lightness that clears Lc 60 on both grounds: **the maximum achievable is 50.6**. It does not exist."

The consequence all six lanes point at without any of them writing it: **every hierarchy relation a user must read to complete a task needs at least one non-tonal encoding** — scale, weight, position, glyph, word, or a rule at a stated contrast. L01 F7 already builds it for the verdict: "glyph + word + lightness step + hue, in that order of load-bearing."

### C7 — Performance is a trust signal here, and the reason it is at risk is CPU, not bandwidth. **(6 lanes, with a correction to the brief)**

**Lanes**: L03 §2 · L09 §5 · L10 §5 · L12 §2 · X-agy §2 · X-qwen §5.

**Most load-bearing evidence**: L09's correction, which contradicts the CONTRACT itself. "I expected to find 'slow Bali connection' data; the verified number runs the other way. **Indonesia's median mobile download speed via cellular was 45.01 Mbps as of late 2025, up 53.1% year-on-year**" (`VERIFIED-LIVE`, DataReportal). L09's inference: the CONTRACT's framing "is more safely read as a **device/CPU** problem (mid-range Android parsing JS, decoding images, painting layout — the actual driver of the 48%-vs-56% mobile INP gap) than a raw-bandwidth problem. That changes the fix: it isn't primarily 'compress the video harder,' it's 'reduce main-thread work and defer anything non-critical until after the LCP element paints.'"

L09 also fetched the 2026 baseline that makes the target concrete: **only 55.9% of all origins pass all three Core Web Vitals; mobile 48% vs desktop 56%**, from May 2026 CrUX across 18.4M origins.

L10 states the trust consequence the others imply: "a slow-loading VOA payment page does not just lose a sale, it *confirms the suspicion* that this is not a legitimate operation. That reframes performance from an SEO concern into the same trust-signal category as the proof strip." X-agy, from a different family, lands on the identical sentence: "**Performance is the deepest form of brand trust.**"

### C8 — Copy the government/bank register, not the marketplace register. **(6 lanes)**

**Lanes**: L03 §9 · L05 F1/F2 · L07 §5 · L11 §1 · X-agy §4 · X-kimi §3 · X-qwen §2.

**Most load-bearing evidence**: L11's live comparison, which shows the split is *within* Indonesia, not between Indonesia and the West — killing the "Indonesian users like density" premise before it can be applied. Traveloka, BCA, imigrasi.go.id and oss.go.id all fetched `VERIFIED-LIVE`: "navy/white, card-based service categories, generous whitespace," regulatory statements "in full sentences, not badges." Against that, the academic Shopee/Tokopedia/Lazada comparison in which "**29.2% of study participants named clutter — icons, banners, ads stacked without hierarchy — as their explicit usability complaint**." L11's rule: "Density in Indonesian digital design is a *category signal*, not a cultural universal."

X-qwen, with no browsing and from a different family, produces the same finding as a self-refutation of its own thesis: "Gojek's home is dense, but its ride-booking task screen is sparse (`FROM-MEMORY`). Same users, same day, both modes. **'Asian users like density' is false; they like density that pays.**"

L03 adds the local counter-signal from the commercial side: Gojek's most recent redesign "drew documented backlash for an 'over-complicated interface' after leaning into 'bolder and brighter colours'" — and concludes that "for a once-per-decision, trust-critical, scam-adjacent transaction like a visa filing, the Stripe/Linear register … is the better-evidenced fit, **not the locally-dominant superapp register**."

### C9 — Indonesian text expansion is a real, *unmeasured* layout risk; the correct response is structural, not a percentage. **(5 lanes)**

**Lanes**: L02 §5 · L05 F1 · L07 §5 · L11 §3 · X-agy §1.

**Most load-bearing evidence**: the one hard number in the corpus, from Canva's own Apps SDK localization guidance (L02, `VERIFIED-LIVE`, quoted directly): translating the button label "**Generate an image" into Indonesian increases the string's length by about 40%**, enough to overflow its container — and Canva's own fix is to design the *shorter* English label so the Indonesian expansion still fits.

The second-strongest finding here is an **absence, independently confirmed twice**. L11 checked four dedicated localization-industry sources (LocaleProof, i18nAgent, POEditor, and the Indonesian agency PeMad) and reports: "**None of the four gives a Bahasa Indonesia-specific percentage.**" L02, separately, could not find one either and marked its own 20–35% inference `FROM-MEMORY (unverified)`, warning: "treat the verified 40% button-label number as the one hard data point, **not a general multiplier**." Two lanes independently failing to find a number is stronger evidence that none exists than either lane's estimate is evidence of a value.

L11 names the specific casualty: "The one genuinely dangerous term is **'all-inclusive'** on the GARUDA VOA price card: English fits a badge in one word-pair; Indonesian needs a clause" — *"Sudah termasuk semua"* / *"Harga sudah termasuk semuanya."* L07 independently measures the same pressure on the banner: Imigrasi's own authenticity strip "drops to `0.65rem` under 425px" to fit its Bahasa string.

### C10 — The verdict is a second-person sentence, not a badge, a score, or a hedge. **(5 lanes)**

**Lanes**: L02 §1 (counter-example) · L04 F5 · L05 F1/F3/F5 · L11 §4 · X-codex F3.

**Most load-bearing evidence**: L05 walked GOV.UK's live visa checker to two terminal states (`VERIFIED-LIVE`) and read the actual H1s: "**You'll need a visa to come to the UK**" / body "Apply for a Standard Visitor visa"; and "You'll need an electronic travel authorisation (ETA) or a visa." Not a badge, not a card, not a celebration. L05's derived test is one line and needs no tooling: "**Pronoun test — if the largest text on screen contains no 'you', it is a badge.**"

Three lanes converge on the *shape of the caveat* from three legal traditions. L05: "State the limit of certainty by naming the actor, not by hedging the outcome. 'Immigration decides' is a sentence about who holds the pen. '*subject to approval' is an asterisk, and asterisks are what scam sites use." L04, on the same glyph from the pricing side: "avoid an asterisk. `IDR 790.000*` destroys in one glyph everything the paragraph above it built." L11, from the register side: BCA states its LPS deposit guarantee "as a complete sentence rather than compressed into badges," and the *Anda* register is "short declarative clauses… No exclamation marks in either example."

L05 supplies the deletion test that makes this checkable: "delete it; if the verdict is now false it was load-bearing and stays, if still true it was decoration and goes."

And the thing that must not ship, with evidence: L05 F5 cites a 2025 study (arXiv 2504.11020, `VERIFIED-LIVE`; 12 retired Dutch police officers + 180 lay users, four explanation conditions) finding "**no form of explanations helped in fostering appropriate trust**," and — the load-bearing part — that where hybrid explanations *did* raise subjective trust among experts, the authors call it "worrisome, as it does not lead to better decisions." L05's application: "`AI-powered eligibility score: 94%`. A percentage on a binary legal question is a fabrication with a decimal point… precisely how a confident scam beats an honest agency."

### C11 — Restraint is not an accessibility concession on this brief; it is the design target. **(4 lanes)**

**Lanes**: L03 §1 · L10 §6 · L12 §5 · X-kimi Device 10.

**Most load-bearing evidence**: L12's statement of the coincidence, which is the cleanest reframing in the corpus. "A first-time visitor 'often afraid of being scammed,' on a slow connection, at night, is under real cognitive load even without a vestibular condition, and the same restraint that serves a vestibular-disorder user — less unsolicited motion, clear step-by-step confirmation, nothing that starts moving on its own — reads to an anxious buyer as *calm competence* rather than *accessibility compliance*. **The design target and the accessibility target are, for this specific brief, close to the same target.**"

L03 states the inverse as a hard ordering: "For a scam-wary, low-bandwidth, low-light Android audience, **an illegible premium effect is worse than a flat one**: flat is honest, illegible-glass reads as evasive." And it supplies the receipt: Apple shipped Liquid Glass in June 2025, NN/g documented the contrast failure, and by June 2026 Apple was "updating the foundations of how Liquid Glass is built to ensure exceptional readability" and adding a slider "from ultra clear to fully tinted" (`VERIFIED-LIVE`, TechCrunch 2026-06-08). L03's rule of thumb: "**A trend that ships with an off-switch twelve months later is a trend with a known expiry date**" — that sentence is L01's, from an independent fetch of the same two sources.

---

## 2. Contradictions, unresolved

Nine. The first is the one that was expected; five of the rest are contradictions nobody flagged.

### K1 — Never split the price (L04) vs the split *is* the anti-scam device (L05). L07 is load-bearing on both.

**L04 at its strongest.** The literature does not say all-inclusive converts better — it says the opposite, for the seller who splits. Robbert & Roth 2014 (abstract `VERIFIED-LIVE`, n=95): "underestimation of the total price of an offering is significantly weaker when prices are presented sequentially rather than partitioned" — i.e. **partitioning causes stronger underestimation of the total**. L04's consequence: "Bali Zero's single number will read as more expensive than a split quote **even when it is cheaper**, and no amount of tone fixes that." And its prohibition: "The instant a 'Government fee 500.000 / Service 290.000' line exists, Bali Zero has manufactured the exact anchor its competitors use — and hands every visitor a number to shop against." L04's replacement is a **non-numeric inclusion list** — three or four ticked lines, no figures — which "satisfies the FTC's 'clear, conspicuous, most prominent' test **by construction** (no component numeral exists to overshadow anything)."

**L05 at its strongest.** "Print the arithmetic, not the adjective": government fee / Bali Zero / total, "every line independently checkable; the government line links to the `.go.id` source." The documented Bali scam has two shapes, one of which is agents "who do legitimately get their clients a visa but **charge above and beyond what should be paid**." Against *that* competitor, the total alone is unfalsifiable and the split is falsifiable: "**showing the split is the one move they cannot copy without exposing their margin.**" L05 also has the trust-badge argument on its side: "A slogan asserts; a breakdown invites verification."

**Where the corpus actually stands.** L05, X-agy ("a strict line-item table (Government Fee, Agency Fee, Total)") and X-qwen ("Show government fee and service fee as two visible lines summing to the total") want the numeric split. L04 and X-codex ("avoid splitting 'government fee' into a late checkout addition; the all-inclusive price is a core trust promise") want the total only. **L07 wants a third thing neither addressed**: the ASA copycat standard obliges a non-official site to disclose "the non-official nature of the service" *and* "**the additional cost**" versus the official channel, adjacent to every CTA. That is a delta, not a split — and it is mandatory under the standard L07 adopts as spec.

**My ruling: print both, gate the split on live verification, and degrade automatically.** Three reasons, and the first is decisive.

1. **L04's rule is stronger than L04's own cited authority, and its own table proves it.** The FTC sentence L04 quotes is permissive: "**Can a business itemize mandatory fees or charges?** *Yes, but itemization must not overshadow the total price.*" And L04's own regulatory table records EU Reg. 1008/2008 Art. 23 requiring **both simultaneously**: "The final price to be paid shall at all times be indicated" *and* a breakdown of fare/taxes/charges that is "**mandatory**." Airline law does precisely what L04 forbids and L05 requires, at the same time. No cited authority anywhere in L04 says "do not itemise"; every one of them says "do not let the itemisation dominate." That is a typographic ratio, and L04 itself supplies it (Finding 2: total ≥2.5× any component line, no component line bolder than the total).
2. **The two lanes are measuring different competitors.** Robbert & Roth is about a buyer comparing *offers*; the split makes the *rival's* total look smaller than it is. L05 is about a buyer checking whether *you* are stealing; the split is the only claim on the page an outsider can falsify. Both mechanisms are real and they do not cancel — the cure for the first is that the total dominates, which is exactly the FTC ratio.
3. **L04 flagged its own evidence as too thin to carry this**: "Only the Robbert & Roth 2014 abstract was actually fetched, and it carries the load-bearing 'partitioning increases underestimation' claim on **n=95, one scenario**. That is thin evidence for a strategically important conclusion." I agree with L04's self-assessment and therefore disagree with L04's rule.

**The condition neither lane stated, and it is the one that decides whether the split is safe at all.** L05's split is only an anti-scam device if the government figure is true and current — and **three lanes independently failed to verify it, and one verified a different number.** L04: "I fetched `evisa.imigrasi.go.id` live today; the homepage carries **no fee figure at all** … I therefore state **no** government-fee amount anywhere above." L05: "Confirm both against the official site before printing IDR 500.000 or any government URL live. **That number is the first thing a hostile reader checks, and it changes.**" L07: "I believe it is IDR 500.000 — **do not publish on my word**," having verified only IDR 1.500.000 for a 60-day extendable visit visa on the official FAQ. And L07 found that the government's own anti-scam page still names `molina.imigrasi.go.id` as the sole official site — a hostname that **resolves NXDOMAIN** (verified by `dig`/`nslookup`, 2026-08-31).

So: **ship the total dominant at ≥2.5× (L04's ratio), ship the split as two checkable lines with the government line linked to a live `.go.id` URL (L05's device), and stamp both with "Government fee verified against [URL] on [date]" wired to a recurring check (L07's own §6 device, applied to itself). If the check goes stale or the URL dies, the surface must fall back automatically to L04's non-numeric inclusion list — never to a stale number.** A split with an unverified government figure is not an anti-scam device; it is a falsifiable claim on the one screen where, by L05's own asymmetry argument, being caught once re-prices every other claim on the page.

**What would settle it.** (a) Read the two papers nobody could fetch — Santana, Dallas & Morwitz in *Marketing Science*, and the full 58-page CMA209 guidance. (b) **Run L04's own acceptance test on both treatments side by side**: five-second exposure of the card to ten people, then "How much will you pay in total?" and "Is there anything else to pay later?", ship at ≥90% correct on both. L04 wrote that test and nobody ran it. It settles this in a week for the cost of ten strangers, and it measures the thing that actually matters — comprehension of the total — rather than the thing the literature measures, which is comparison against a rival.

### K2 — "Encode depth as colour instead of geometry" (L03) vs "hierarchy must not be carried by tone at all" (L01). L10 breaks the tie mechanically.

**L03 at its strongest.** Its §4 is the corpus's most direct answer to *scialba e piatta*, and it converges from three shipped systems: Linear's four-step surface ladder, Google's dark-theme overlay guidance ("each layer up adds 4-8% lightness"), and a second source describing the same physics independently. Its conclusion is explicit and well-argued: "**The rule isn't 'remove depth,' it's 'encode depth as colour instead of geometry.'**" It also correctly identifies the failure it is guarding against — a designer told "no drop-shadows" who makes every surface the same flat colour, "which reproduces the original complaint."

**L01 at its strongest.** L03 never modelled ambient light. L01 did, and found the ladder dies: at ~10,000 lux a Material-3 elevation step reaches **1.05:1** and a hairline **1.15:1**. Its ruling for the transactional surface is categorical: "On the GARUDA VOA flow specifically — a payment path someone will complete standing outside an immigration office — **hierarchy must not be carried by tone at all**: use scale, weight, whitespace, and a hard 1px line at `--border-strong`, all of which are shape and survive flare."

**The tie-breaker neither lane had.** L10 §6, `VERIFIED-LIVE` against MDN: under `forced-colors: active`, "`box-shadow` is force-stripped to `none`." L03's technique #2 is `box-shadow: inset 0 1px 0 0 rgba(255,255,255,.06)` — gone. L01's own hairline recommendation, `color-mix(in srgb, currentColor 17%, transparent)`, is an author colour — overridden. **Only one proposal in sixteen reports survives this by construction**: X-agy's "1px solid `CanvasText`" — a system colour, which is exactly what `forced-colors` preserves. Neither L01 nor L03 noticed that X-agy's least-evidenced report contains the only forced-colors-safe border primitive in the corpus.

**My ruling, and it is not a split of the difference: L03's ladder stays; it just stops being load-bearing.** Tone-based elevation is permitted as an enhancement that carries no information. **Every hierarchy relation a user must read to complete a task must additionally be encoded in at least one of: scale, weight, position, glyph/word, or a 1px rule using a system colour under forced-colors.** L03 is right that removing depth reproduces the flatness complaint; L01 is right that tone alone cannot be trusted to deliver it. Both tests are cheap and both already exist in the corpus: L01's — screenshot, apply `filter: contrast(0.35) brightness(1.4)`, "if the only thing left is a grey rectangle, the hierarchy was tonal"; L10's — render the page under `forced-colors: active` and confirm every affordance is still findable. Run both on every mockup.

### K3 — How dense should the *verify* screens be? X-qwen vs L05 vs X-kimi — and X-kimi contradicts itself.

**X-qwen at its strongest.** "Classify every screen *verify* or *act*." On verify screens, "everything visible at once, **zero accordions hiding price, fees or license terms**," because "in markets with real scam prevalence, hidden content — accordions, 'read more', a second page — **reads as concealment**." Its ruling: "The Visa Oracle **verdict page** should be the densest screen in the product."

**L05 at its strongest, with research behind it.** NHS's confirmation-page pattern (`VERIFIED-LIVE`): "**Avoid including too many different components on a confirmation page. Research suggests they can overwhelm people.**" L05 turns it into a number: "Component types on screen ≤ 7." It also has a hard structural constraint from GOV.UK that no other lane found: interactive elements inside the confirmation panel "**will not be accessible**."

**X-kimi at its strongest.** "Exactly one element per viewport may sit at maximum contrast/size/saturation; everything else is deliberately demoted, and the promoted element must be the thing the user came to decide." Its diagnosis of the three rejected rounds is the best single explanation of *scialba* in the corpus: "Every round distributed emphasis evenly … because distributing evenly is what 'clean' means to a model without an allocation decision. **Calm is the product of a decision about what *not* to emphasize.**"

**My ruling: all three, because they are three different axes that each lane collapsed into the word "density."** X-qwen is talking about *completeness of information*. L05 is talking about *variety of component types*. X-kimi is talking about *allocation of emphasis*. A verdict page can simultaneously show everything, use ≤7 component types, and have exactly one element at maximum emphasis — and that joint spec is stronger than anything any lane wrote. The one thing all three jointly forbid, which only X-qwen names and L05's rule would otherwise permit, is **the accordion**: it reduces component variety and it hides price information, so it satisfies L05 while violating X-qwen. Ban it on any surface carrying a price, a fee, or a licence term.

**The residual, genuine disagreement — and X-kimi is inconsistent with itself.** Device 1 wants the home hero at ≤40% content area with the H1 "nearly alone above the fold," complaining it "currently shares the viewport with the tagline, dateline, proof strip, and four doors." Device 9 wants "the proof strip [to become] **the most expensive element on the home page**." Those cannot both be true of one viewport. X-qwen independently wants that same numeric strip to be "the densest object on the home page." **The resolution nobody wrote, and it also satisfies L09's geometry finding** (that four doors "do not fit above the fold on this viewport at any readable type size… it's geometry"): the hero holds the dateline, the H1 and one affordance; **the proof strip is the first thing the scroll earns.** That satisfies Device 1, Device 9, X-qwen's numeric strip and L09's arithmetic simultaneously — and it gives the H1 the job L09's evidence says it actually has, which is to earn the scroll, not to expose the doors.

### K4 — The dateline: liability (L07, L09) vs the seed of the whole direction (X-kimi). And the two lanes that read it disagree on the arithmetic.

**L07 and L09 independently fetched balizero.com and both read a stale dateline.** L07: "Bali Zero's dateline reads 'Bali Zero · Dispatch · April 2026 · Kerobokan' — **four months stale today**. A dateline is a freshness promise; a stale one is a self-inflicted hit on the highest-authority line of the page." L09: the same string, "**five months stale** against today's date," with the consequence stated more sharply: "if the date is genuinely static rather than server-rendered to 'now,' a dateline is worse than no dateline: it converts a trust signal into evidence of exactly the neglect this audience is afraid of."

**X-kimi builds an entire direction on the dateline being real.** "'Bali Zero · Dispatch · Kerobokan' is a newspaper dateline. **No model has taken it literally**, because every brief hands out web-design references and models return what they're handed… gazettes are signed, dated, and located ('Kerobokan'). Scam sites are placeless and timeless. A dateline and an edition rhythm ('Dispatch No. 47') is **provenance, and provenance is the visual form of trust**."

**Two corrections before the ruling.** First, the arithmetic: April 2026 → 31 August 2026 is **four months**. L07 is right; L09's "five" is wrong. Small, but it is exactly the class of number that must not be laundered forward. Second, **both lanes read the string through a summarising fetcher, not raw HTML**, and both said so — L09 explicitly: "this went through a summarizing intermediary, not a raw byte-for-byte HTML read, so it needs a direct `curl`/browser check before anyone treats 'the dateline is stale' as confirmed fact rather than a flagged risk." Two independent summarisers returning the same string is good evidence and not proof.

**My ruling: X-kimi's direction is right and is conditional on a fact nobody has checked.** The dateline is provenance only if it is generated, not typed. **Ship it only if it is server-rendered from the same query that generates "Filed this month: 47 KITAS, 9 PT PMAs." If those two lines can have different truth values, delete the dateline and keep the counter.** No lane wrote "same source or neither," and it is the only formulation under which L07's liability and X-kimi's direction are the same object. Note the open dependency L09 flagged and could not close: whether the "47 KITAS" figure itself "update[s] automatically or [is] hand-edited monthly." If it is hand-edited, the gazette direction is unavailable and L07's liability finding stands unopposed.

### K5 — "Often on slow connections" (CONTRACT, X-qwen, L10) vs the measured national median (L09).

**L09 measured**: 45.01 Mbps median mobile download, +53.1% YoY (`VERIFIED-LIVE`). **X-qwen reasoned from the opposite premise**: its third mechanism for Asian density is "**Data economics.** Where a megabyte costs money and the connection drops, one dense page that loads once beats five sparse pages reached by navigation." **L10 asserted without a source**: "a real Bali 4G connection (effective throughput often closer to a slow-3G/fast-3G profile at night or in Kerobokan backstreets)."

**My ruling: L09's number wins on the national median and changes the *diagnosis*; it does not license dropping the *budget*.** Two reasons. First, a national median is not the p75 of a roaming tourist on a throttled international eSIM in a Kerobokan backstreet at 11pm, and L09 concedes exactly this: "That is a *national median*, not a guarantee for a specific villa's indoor signal." The Core Web Vitals bar is a **75th-percentile** measure (L10, L09, both verified against web.dev), so the median is the wrong statistic for the gate regardless of its value. Second, L10's payload budget is cheap and its cost of being wrong is zero.

What L09's number **does** kill is X-qwen's *justification*. If bandwidth is not the binding constraint, "one dense page that loads once" loses its data-economics argument and has to stand on its trust argument alone (concealment-aversion, K3) — which it can. And it moves the engineering work: **reduce main-thread JS and defer everything non-critical until after the LCP element paints**, rather than only compressing assets.

### K6 — QRIS as a trust mark shown before commitment (X-qwen) vs QRIS as a segment-specific option that must never lead (L06).

**L06, with the strongest verified evidence in the payment lane**: QRIS Cross-Border is bilateral, country by country — Thailand, Malaysia, Singapore, Japan, with Korea and China in progress. "A tourist from the US, UK, Australia, EU, or anywhere outside that named list **has no domestic app that will scan an Indonesian QRIS code**." Their only path is registering a local e-wallet with an international card, "which typically also wants an Indonesian SIM for the OTP verification step." L06's ruling: "QRIS should be presented as the option for 'already in Bali with GoPay/OVO/DANA,' **never as the default or first-listed option for someone paying from abroad** … it will read as a broken checkout." And: "Don't advertise 'Pay by QRIS' as a universal, borderless feature."

**X-qwen** (`FROM-MEMORY`): "Show the QRIS mark, BCA/Mandiri VA, and card logos *before* commitment," listing the QRIS mark among "the local grammar of legitimacy."

**My ruling: both, because they are about different objects — but the ranking matters.** The QRIS **mark** stays in the rail row shown before commitment; X-qwen is right that it is local legitimacy grammar, and displaying a mark is not the same as pre-selecting a rail. The QRIS **rail** is never pre-selected, and the pre-selection is derived from segment — L06's inference, which nobody else made: "segment the checkout by the passport-upload step's implied context, not by defaulting to whichever payment method is technically first in the gateway's SDK." Where they collide, L06 wins: its country list is `VERIFIED-LIVE` and X-qwen's entire report is `FROM-MEMORY` by construction.

### K7 — Where does the money boundary sit? Pay at the verdict (L04's adjacency rule, as applied) vs pay after passport preflight (X-codex).

**L04's rule**, which is sound on its own terms: "price block and primary CTA share one card with **≤ 24px** of vertical gap and no divider between them; the pair must be reachable without scroll after the last question." L05 puts the price "*inside* the verdict block, under 'supported', above the named human."

**X-codex's objection**, which is the whole reason its lane exists: "**Do not charge at the provisional verdict**: show IDR 790,000 first, inspect the passport, then request payment immediately before submission." Its structure table names the failure precisely — pay-immediately-after-verdict "charges before Bali Zero knows whether the passport is usable" — and its cost is stated honestly: pay-after-preflight means "Bali Zero bears the cost of reviewing non-buyers."

**The collision nobody noticed.** Applied to the Visa Oracle verdict, L04's adjacency rule puts a *payment control* immediately beneath a verdict computed from **four unverified, self-reported answers**. X-codex's entire 30-row state table exists to prevent exactly that, and L05 F9 independently forbids it for the borderline case ("no payment control on the screen"). The CONTRACT itself is inconsistent between surfaces: GARUDA VOA is described as "4 questions → price → passport upload → payment" (X-codex's order already), while the Oracle verdict is "the verdict, the exact all-inclusive price, a named human who takes the case after payment."

**My ruling: keep L04's adjacency, change the verb.** The control adjacent to the price is **"Continue — we check your passport before you pay,"** not "Pay." That satisfies L04's rule as written (a CTA is adjacent to the price, in the same card, within 24px), satisfies X-codex's boundary, satisfies L05 F9, and satisfies X-codex's own information-order requirement that "the price must appear before passport upload." No lane wrote this sentence, because L04 was not thinking about document risk and X-codex was not thinking about layout adjacency.

### K8 — Red as the primary CTA: arithmetically fine as a fill (L01), locally correct (X-qwen), the alarm register to avoid (X-kimi) — and it fails in daylight (L01, again).

**L01's arithmetic** settles half of it: `#C8102E` cannot be ink on dark (Lc −24 on `#141218`), but as a **fill** it is comfortable — "white on `#C8102E` measures Lc −82.4, comfortably above the Lc 75 body-text minimum." So a red fill CTA is defensible on contrast grounds.

**X-qwen's cultural argument**, which is the one a Western-trained designer would refuse: "A red **Bayar sekarang** button reads locally as energetic and national, not alarming." It also supplies the honest counter-evidence itself: "I know of no solid study showing red CTAs convert better than neutral ones anywhere; the case for red here is **identity and local meaning, not lift**."

**X-kimi's objection** is narrower than it looks: "avoid bright red CTAs **on black** (the alarm)." Its remedy is to invert the flag — red becomes the deep field (oxblood), warm off-white becomes the light. **L01 F6 independently agrees the ground is the problem, not the red**: blue-black ground + saturated red accent is "the maximum-span pair" for chromostereopsis (measured hue distances from `#C8102E`: blue-black `#0B1020` at 112.8°, M3's `#141218` at 81.9°, a warm near-black `#0F0D0C` at 26.1°) — "If the brand red stays, the ground must move *toward* it in hue."

**The finding nobody else had, and it decides the implementation.** L01's flare table puts **white on `#C8102E` at 2.79:1 in shaded ~10,000-lux daylight** — below the 3:1 non-text threshold. The red CTA's label washes out in the exact environment where someone stands outside an immigration office.

**My ruling: red fill CTA, on a warm near-black (26–46° from the accent hue) rather than a blue-black, and the control must additionally carry a non-tonal affordance** — a 1px system-colour border plus a size/weight step — so the button is findable when its label washes out. That is not a compromise; it is the only configuration that satisfies L01's contrast arithmetic, L01's chromostereopsis measurement, L01's flare measurement, X-qwen's identity argument and X-kimi's objection at once. **Caveat carried forward**: L01's flare constants are its own engineering estimates (`FROM-MEMORY`), and its APCA numbers came from a locally reimplemented algorithm that L01 itself says must be re-run through `apcacontrast.com` before being used as a gate. Measure this one on a real phone in Kerobokan at midday before shipping it.

### K9 — Which typeface register? Text serif on the verdict (L02) vs no serif at all (L02's own counter-example) vs display serif gazette (X-kimi) vs system fonts (X-agy).

**L02 argues both sides and names its own counter-example.** For the serif: "the **Visa Oracle verdict** page is the one surface here that is genuinely long-form … the one place on the three surfaces where a text serif earns its keep, because there is real reading to do." Against: "GOV.UK itself uses **no serif at all** … its argument is that road-sign legibility at a glance beats literary gravitas for a service people are using under stress. Bali Zero's audience (scam-wary, on a slow connection, at night) has more in common with someone reading a GOV.UK benefits form than someone reading a magazine."

**X-kimi wants the display serif** as the core of the gazette direction ("a masthead, a dateline, column rules, a display serif for headlines"), while simultaneously ruling in Device 2 that "**two families is the ceiling; three is a moodboard**" and "three type sizes, two weights, one family." **X-agy wants neither**: "Typography as UI … High-contrast (Lc 90), large (18px base) **system-font** typography."

**The constraint that decides it, and it is L02's own, two sections away from its serif recommendation.** L02 §2 found a live, unresolved report against Google's own font repo of "visible variable-font rendering corruption specifically on Chrome for Android" (`VERIFIED-LIVE`, github.com/google/fonts/issues/2815) and concluded: "Given the brief's stated audience — 'mostly on 360–390px Android phones' — this is not a theoretical edge case; **it is the primary device class**." Its own recommendation for the price screen follows: "self-host a **single static instance** per weight actually used … this sidesteps the Android Chrome variable-font rendering risk entirely on the one screen where a rendering glitch is a trust event."

**My ruling: system-font-first on both transactional surfaces; at most one licensed text face on the home page; zero display serifs anywhere.** A second family on the verdict costs a font file and a rendering risk on the primary device class, on the screen L02 itself designates as the one where a glyph glitch is a trust event. If a second family ships anywhere, it ships with the metric-matched fallback `@font-face` block (`size-adjust` / `ascent-override` / `descent-override` / `line-gap-override`) that L02 verified produced **CLS 0** in a documented production case. X-kimi's gazette direction survives this intact: L02's own GOV.UK counter-example proves the "document-like, serious" register is achievable with **no serif at all** — the gazette's load-bearing devices are the dateline, the column rules, the tabular figures and the single loud headline, none of which require a serif.

---

## 3. The hard floor

*This section is written to be pasted verbatim into a design brief. Every line is checkable by a person or a script. `(Lnn)` is the source lane. `[M]` marks a number the source lane itself marked `FROM-MEMORY (unverified)` — it is still the best number the corpus has, but it must not be quoted to a client as measured.*

**Standing caveat on all APCA figures below**: L01 computed them with a locally reimplemented APCA-W3 0.1.9 that reproduces two canonical reference values exactly but was not independently validated. **Re-run every Lc gate through `apcacontrast.com` before wiring it into CI** (L01, its own instruction). OKLCH conversions and WCAG 2.x ratios are unambiguous published maths and are solid.

### 3.1 Contrast and colour

| # | Gate | Number | Lane |
|---|---|---|---|
| 1 | Body text | WCAG 2.x **≥ 4.5:1** *and* APCA **\|Lc\| ≥ 75** — both, not either | L10, L01 |
| 2 | Large text (≥18px, or ≥14px bold) and UI text | **≥ 3:1** *and* **\|Lc\| ≥ 60** | L10, L01 |
| 3 | Any border/rule that carries meaning (`--border-strong`) | **≥ 3:1** (WCAG SC 1.4.11) *and* **\|Lc\| ≥ 26** | L01 F3 |
| 4 | Decorative separator (`--border-subtle`) | **\|Lc\| ≤ 14** — deliberately below the non-text threshold, and it may carry no obligation | L01 F3 |
| 5 | Focus indicator | **≥ 3:1** against the unfocused state of the same pixels, covering **≥ a 2px perimeter** | L10 (WCAG 2.4.13) |
| 6 | Neutral surface chroma | OKLCH **C peak ≤ 0.018** across the whole neutral ramp. Above it, the surface stops being a surface and becomes a colour | L01 F2 |
| 7 | Any two semantic state colours that can co-occur | **≥ 12 OKLCH L-points** apart, *plus* a glyph, *plus* a word | L01 F7 |
| 8 | Dark-mode surface elevation step | **≥ +7 L** per level (dark ladder needs 1.2–1.6× the travel of the light ladder) | L01 F1 |
| 9 | Light-mode surface elevation step | **≥ −3.5 L** per level | L01 F1 |
| 10 | Brand red as **ink** on a dark ground | **Forbidden.** `#C8102E` on `#141218` measures **Lc −24**; no lightness of that hue clears Lc 60 on both a near-black and a near-white ground (max achievable 50.6) | L01 F3/F5 |
| 11 | Brand red as **fill** | Permitted. White on `#C8102E` = **Lc −82.4** | L01 F5 |
| 12 | Hue distance, ground to accent | **26–46°** (warm near-black), never the ~113° of a blue-black — that is the maximum-span chromostereopsis pair | L01 F6 |

**Three tests, run on every mockup, no tooling beyond a browser:**
- **Greyscale test** — desaturate the screenshot to greyscale and hand it to someone. If they cannot read the verdict, it fails. *(This test fails Radix's own step-9 palette, which is why "use a good design system" is not a substitute for running it.)* (L01 F7)
- **Daylight test** — apply `filter: contrast(0.35) brightness(1.4)`. If the only thing left is a grey rectangle, the hierarchy was tonal and must be re-encoded in scale/weight/position/rule. (L01 F8)
- **Forced-colors test** — render under `@media (forced-colors: active)`. `box-shadow` is stripped to `none` and author colours are overridden; every affordance must still be findable. (L10 §6)

### 3.2 Targets, motor and reach

| # | Gate | Number | Lane |
|---|---|---|---|
| 13 | Tap target, legal floor | **≥ 24 × 24 CSS px** (WCAG 2.2 SC 2.5.8) | L10 |
| 14 | Tap target, design target | **44 × 44px (Apple) / 48 × 48dp (Material)** ≈ 9mm physical `[M]` | L10 |
| 15 | Undersized adjacent targets | **≥ 24px** centre-to-centre spacing (the SC 2.5.8 spacing exception) | L10 |
| 16 | Gap between adjacent targets | **≥ 8dp** `[M]` | L10 |
| 17 | Swipe-gesture target | **≥ 45px** tall and wide | L10 |
| 18 | Input field height | **≥ 44px**, with a label that stays visible on focus — never a placeholder-as-label `[M]` | L10 |
| 19 | Primary CTA and price position | Bottom third of the viewport (thumb zone) on **every** mobile step | L10 |
| 20 | Dragging | No functionality requires it without a single-pointer alternative (WCAG 2.5.7) | L10 |

### 3.3 Motion

| # | Gate | Number | Lane |
|---|---|---|---|
| 21 | Micro-feedback (press, toggle, check) | **50–150ms** | L12 (Carbon + Atlassian converged) |
| 22 | Panel/modal/transition | **150–400ms** | L12 |
| 23 | Ceiling for anything habitual | **≤ 500ms**; over that "starts to feel like a real drag" | L12 (NN/g) |
| 24 | Token scale for *this* client (biased fast: phone, night, anxious) | instant **80ms** / fast **150ms** / base **220ms** / slow **320ms**. Nothing on any surface exceeds 320ms | L12 |
| 25 | Exit vs entrance | Exit shorter — a 300ms entrance exits in **200–250ms** | L12 (NN/g) |
| 26 | INP | **≤ 200ms** at p75 | L10, L12, X-agy |
| 27 | Wait < 1s | **No indicator at all** — the flash reads as a glitch | L12 (NN/g) |
| 28 | Wait 1–10s | Spinner for a single module; **named-step skeleton** for a page. A skeleton with no content placeholders is worse than nothing | L12 (NN/g) |
| 29 | Wait > 10s | Percent-done indicator **and** a way to interrupt | L12 (NN/g) |
| 30 | Artificial delay | **Zero.** No `setTimeout` on any success path; every animated duration bound to a real promise. **Make it a grep-based lint rule** | L05 F10 |
| 31 | `prefers-reduced-motion: reduce` | Kill decorative classes **by name**, then compress everything else to **0.001ms** — do not delete the transition property (a component depending on `transitionend` breaks silently) | L12 (A11y Project) |
| 32 | `backdrop-filter`, if used at all | Radius **8–16px**, small static area only, never animated, never on content that scrolls. Cost scales with blurred area × radius; stacked blurs multiply | L03 |

### 3.4 Performance and payload

| # | Gate | Number | Lane |
|---|---|---|---|
| 33 | LCP | **≤ 2.5s** at p75, on a **throttled mid-tier Android / 4G profile** — not desktop wifi | L10, L09 |
| 34 | CLS | **≤ 0.1** at p75 | L10 |
| 35 | First-viewport total weight | **≤ 500KB compressed** (take L10's tighter bound; X-qwen independently arrives at ~500KB) | L10, X-qwen |
| 36 | Hero image | **≤ 150–200KB**, WebP/AVIF, sized for 390px — not a scaled-down desktop asset | L10 |
| 37 | Critical JS | **≤ 150KB compressed** | L10 |
| 38 | Hero video / WebGL / canvas | **Zero.** A `<video>` is not itself the LCP candidate, but it competes for bandwidth and main thread with whatever is | L09, L10 |
| 39 | Above-the-fold elements | Explicit `width`/`height` or `aspect-ratio` reserved on every one | L10 |
| 40 | Fonts | One **static instance per weight actually used**, subset to Latin; plus a metric-matched fallback `@font-face` (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) targeting **CLS 0** | L02 |
| 41 | Passport image | Client-side resize to **≤ 1.5–2MB** before upload, with visible progress and a plain receipt ("Received: passport.jpg, 1.3 MB") `[M]` | X-qwen |

*Context for the budget, not a licence to relax it: Indonesia's median mobile download was **45.01 Mbps**, +53.1% YoY (L09, verified). The binding constraint is **CPU at p75**, not the median pipe. Only **55.9% of origins pass all three Core Web Vitals; mobile 48% vs desktop 56%** (L09, May 2026 CrUX, 18.4M origins).*

### 3.5 Type

| # | Gate | Number | Lane |
|---|---|---|---|
| 42 | Scale | A **discrete step table**, pixel-checked at exactly **360px and 1440px**. `clamp()` is permitted only on display/hero type nobody QAs at in-between widths — never on a price, a verdict, or body copy | L02 |
| 43 | Mobile line length | **30–50 characters**, min **14–15px**, line-height **≥ 1.3** | L02 (Baymard) |
| 44 | Desktop line length | **≤ 80 characters** (WCAG 1.4.8); copy set wider was **skipped 41% more often** than copy at 60–70 | L02 (Baymard) |
| 45 | Base body size | **≥ 16px**; **18px** on the transactional surfaces. Gojek deliberately raised its base to 12pt "for legibility" for exactly this audience | L02, X-agy |
| 46 | Type tiers | **Three sizes, two weights, one family.** Two families is the ceiling | X-kimi |
| 47 | Line-heights | Rounded to the nearest **4px**, so long Indonesian strings do not break the vertical rhythm | X-agy, L02 (Gojek's 1.3× scale, rounded to 4px) |
| 48 | Every price, deadline, reference number | `font-variant-numeric: tabular-nums lining-nums` — **five lanes independently** | L02, L03, L04, X-agy, X-kimi |
| 49 | Currency token | **~0.55× numeral height, baseline-aligned. Never superscript** — superscript currency is the airline/SaaS tell | L04 |
| 50 | Total vs components | Total's type size **≥ 2.5× any component or caveat line**; no component line bolder than the total. At 360px ≈ **40px/600** against **14px/400** | L04 (from the FTC's "most prominent") |
| 51 | Currency and figure | Joined by a **non-breaking space** so a 360px viewport can never split them | L02 |
| 52 | Wrapping | `text-wrap: balance` on every heading (91.63% support), `text-wrap: pretty` on paragraphs. Both degrade harmlessly | L02 |
| 53 | Hyphenation | **Do not rely on `hyphens: auto` for Indonesian** — no `id` dictionary confirmed in any engine | L02 |

### 3.6 Bilingual EN/ID

| # | Gate | Rule | Lane |
|---|---|---|---|
| 54 | `id` surface price | **`Rp790.000`** — dot thousands, **no space**; strip the U+00A0 that ICU inserts | L04 (measured), L11 (BCA, verified), X-qwen |
| 55 | `en` surface price | **`IDR 790,000`** — `currencyDisplay:'code'`, en-US grouping. `IDR` beats `Rp` because a suspicious buyer can paste it into a converter | L04 |
| 56 | Formatters | **Two, keyed to page language. Never one.** Never `notation:'compact'` (emits `Rp 790 rb`, which is a rounding, not a price) | L04 |
| 57 | Parsing | **Never `parseFloat` an `id-ID` price string.** `parseFloat("790.000")` returns **790** — a two-order-of-magnitude error that throws nothing | L02 |
| 58 | Buttons, chips, badges, pills | **No fixed pixel/rem width.** min-width + wrap + a min-height that tolerates two lines | L11, L02 |
| 59 | Truncation | **Never** `text-overflow: ellipsis` on a price, a verdict word, or "all-inclusive" / "sudah termasuk" | L11, L02 |
| 60 | Width budget for ID short strings | **+35–50%** working assumption. The single measured data point is **+40%** on one Canva button label; **no vendor publishes an ID-specific figure** (confirmed independently by two lanes) | L02 (verified), L11 |
| 61 | Bahasa banner/strip | Budget **~30%** extra width; Imigrasi's own drops to **0.65rem** under 425px | L07 |
| 62 | Language switcher | Text **"EN · ID"**, never flags. Persistent, top-right, same position on every surface. Auto-detect from `Accept-Language` on first load with a one-tap override; **never a geo-IP redirect the user cannot undo**; **must not lose form state mid-flow** | L11 |
| 63 | URLs | `/id/` subdirectory with **bidirectional** hreflang. A cookie-only switch is invisible to crawlers | L11 |
| 64 | Timestamps | Suffixed **WITA** explicitly, always | L11 |
| 65 | Name field | One **"Full name (as in passport)"** field. Never a first/last split — it silently rejects valid single-name Indonesian passports | L11 |
| 66 | Register | **`Anda`**, never `kamu`, on any surface touching money or legal status. Short declarative clauses, benefit named first, no exclamation marks (BCA/OSS pattern, verified live) | L11 |
| 67 | Phone/WhatsApp | Pre-formatted **`+62 8xx-xxxx-xxxx`** (trunk 0 dropped) so it dials from both a local and a foreign handset | L11 |

### 3.7 Forms, checkout and payment

| # | Gate | Rule | Lane |
|---|---|---|---|
| 68 | Numeric fields | `type="text" inputmode="numeric"` — **not** `type="number"` (spinner arrows) | L06 (web.dev) |
| 69 | Autofill | Exact tokens: `cc-number`, `cc-name`, `cc-exp-month`, `cc-exp-year`, `given-name`, `family-name`, `address-line1/2`, `tel`, `email` | L06 |
| 70 | Keyboard hygiene | `autocorrect="off"`, `autocapitalize="off"` where applicable. **60% of the top 50 mobile-optimised sites fail ≥2 of 5** keyboard optimisations | L06 (Baymard) |
| 71 | Layout | **Single column**, one field group visible at a time, at 360–390px. Not a style choice — it is what the screen width physically allows | L06 |
| 72 | Guest checkout | Labelled **explicitly and equally weighted**. 60% of test subjects could not *locate* it when it was not a clearly separate choice; forced account creation is 18% of abandonment | L06 (Baymard) |
| 73 | Redundant entry | **Nothing the user already gave is asked for twice** in the same process without auto-populate or select (WCAG 3.3.7) — a direct hit on passport number/name between intake and payment | L10 |
| 74 | Authentication | OTP / magic-link **supports paste and autofill**; no memorisation-only path (WCAG 3.3.8) | L10 |
| 75 | Help mechanism | Same relative position on **every** page of the flow (WCAG 3.2.6) | L10 |
| 76 | Focus | Never *entirely* obscured by a sticky header, banner or chat widget (WCAG 2.4.11) | L10 |
| 77 | Errors | **Inline**, not only summarised at the top | L10 |
| 78 | Validation timing | On completion, **never as-you-type** — premature error states increase abandonment `[M]` | L12 |
| 79 | Virtual Account screen | Large **tap-to-copy** VA number (never retyped); **visible countdown** to expiry; **collapsible per-channel** instructions (ATM / m-banking / internet banking); an explicit "we're watching for your payment" state; and email/WhatsApp as the *actual* delivery channel | L06 |
| 80 | QRIS screen | Show the QR **immediately** with an explicit instruction line ("Open GoPay, OVO, DANA, ShopeePay or your bank app → Scan → Confirm") plus a manual "I've paid" fallback. **No fake "Waiting for scan…" indicator** — most integrations get a webhook only on final payment | L06 |
| 81 | QRIS placement | Never pre-selected for a buyer paying from abroad. Cross-border QRIS covers **only** MY/TH/SG/JP (+KR, CN in progress) domestic apps | L06 |
| 82 | MDR | **Never passed to the buyer.** Bank Indonesia, verbatim: *"Biaya MDR ini ditanggung oleh merchant dan tidak boleh dibebankan kepada konsumen"* | L06 |
| 83 | Card step | Warn **before** the step that a 3DS/OTP prompt will arrive **from the buyer's own bank** on a page Bali Zero does not control. Suppress any DCC "pay in your home currency" toggle. On decline, never name a cause the gateway cannot confirm ("Do Not Honor" code 05 is a catch-all) — offer QRIS/VA, not a second card retry | L06 |
| 84 | Payment truth | Success is derived from the **provider's server notification**, never from the browser returning to a success URL. Idempotency on payment creation, document submission and refund | X-codex |

### 3.8 The money moment — binary gates

| # | Gate | Rule | Lane |
|---|---|---|---|
| 85 | **The stranger test** | Can a stranger on a 360px phone learn the **total price without typing anything**? If no, the surface fails. Binary | L07 |
| 86 | Adjacency | Price block and primary CTA in **one card**, **≤ 24px** vertical gap, no divider between them, reachable without scroll after the last question. If the page scrolls it away, a sticky bar carries **price + CTA together** — never a lone sticky CTA, which is the drip-pricing shape | L04 |
| 87 | Monotonicity | **The number the user first sees never goes up.** No "from IDR 790.000" | L04 |
| 88 | Asterisks | **Zero.** `IDR 790.000*` destroys in one glyph everything above it | L04 |
| 89 | Inclusion line | Same card, **≤ 48px** below the price, **≤ 8 words**, contains *included* / *sudah termasuk* | L04 |
| 90 | Zero-state line | Explicit, and almost always omitted: **"Nothing is added at the end." / "Tidak ada biaya tambahan."** | L04 |
| 91 | Tooltips | The inclusion claim may **not** live only in a tooltip — a disclosure must be *unavoidable*, and a tooltip is by definition avoidable | L04 |
| 92 | Accordions | **Forbidden** on any surface carrying a price, a fee, or a licence term — hidden content reads as concealment to this audience | X-qwen, K3 |
| 93 | **Comprehension test — ship gate** | Five-second exposure of the price card to 10 people, then two questions: *"How much will you pay in total?"* and *"Is there anything else to pay later?"* **Ship only at ≥ 90% correct on both** | L04 |
| 94 | Two prices (790.000 / 850.000) | Rendered as a **timeline, never a tier menu**: `Today — IDR 790.000 — 30 days` → `Day ~25, if you want to stay — IDR 850.000 — 30 more days`, with the **sum stated plainly** underneath. Same type size for both (they are equally real), no default selection, no "most popular" badge | L04 |
| 95 | Payment control on an uncertain verdict | **Zero.** A borderline state gets its own colour token (not a tint of "supported"), its own verb ("Needs a check" / "Perlu dicek"), a named person, a clock, **no price and no payment control** | L05 |
| 96 | FX line, if shown | **0.5× size**, low emphasis, directly beneath: `≈ €44 · mid-market rate, 31 Aug — your bank sets the final amount`. Visually subordinate, and it names who decides | L04 |

### 3.9 The verdict screen

| # | Gate | Rule | Lane |
|---|---|---|---|
| 97 | H1 | Second person, indicative, **< 10 words**, no conditional clause, no adverb of degree. **Pronoun test: if the largest text on screen contains no "you", it is a badge and it fails** | L05 |
| 98 | Sentence length | Split anything over **25 words**; paragraphs **≤ 5 sentences** (GOV.UK's own published standard) | L05 |
| 99 | Component types on screen | **≤ 7** | L05 (NHS) |
| 100 | Verdict panel | **Nothing interactive inside it** — GOV.UK states plainly that interactive elements in the panel "will not be accessible" | L05 |
| 101 | Block order | verdict → price → "what happens next" *with a `when` on every step* → the four answers with Change links → the named human → contact → save-a-record | L05 |
| 102 | Answers | Four rows, each *key · value · Change*, with visually-hidden text so a screen reader hears "Change name", not "Change". Editing costs **two taps and one return**, never restarts the flow, and **if the edit flips the verdict, the page says so explicitly** | L05 |
| 103 | Save-a-record | One-tap PDF/permalink carrying a **reference code, the price, the named handler and the date**. Highest-value item on the screen and almost always omitted | L05 |
| 104 | Must not ship | A confidence score, a probability, a decision-tree visualisation, or a "how we calculated this" expander containing pseudo-reasoning | L05 |
| 105 | The caveat | A complete sentence naming a **real actor** ("Indonesian Immigration makes the decision"), placed once, after the verdict and after the price, never inside the H1, never as an asterisk. **Deletion test**: delete it — if the verdict is now false it stays; if still true it was decoration and goes | L05 |
| 106 | A refusal | Four obligatory parts: the determination in one sentence; **the specific reason naming the answer that caused it**, with a Change link on that exact answer; **the route that does work, priced, on the same screen**; and a named human — do not downgrade the human on bad news | L05 |
| 107 | AI disclosure | If a language model touches this page, **one line saying so** — EU AI Act Art. 50 applies from **2 August 2026** | L05 |

### 3.10 Copy and legal — CI-checkable

| # | Gate | Rule | Lane |
|---|---|---|---|
| 108 | String blocklist, failing the build on a hit | `official partner` · `official` / `approved` (affiliation sense) · `resmi` · `guaranteed` / `dijamin` · `100%` · `no risk` / `tanpa risiko` · `#1` · `first reseller` | L07 |
| 109 | Statutory hooks (these are not house style) | UU 8/1999 **Pasal 9(1)(c)(d)(j)(k)** and **Pasal 10**; penalties **Pasal 62(1)** up to 5 years or **Rp 2.000.000.000**, and **Pasal 63** includes **revocation of the business licence** | L07 |
| 110 | Compliant form of a strong claim | The claim **with its conditions attached**, not a weakened claim. Pasal 9(1)(j)'s escape hatch is *"tanpa keterangan yang lengkap"*. "We filed 47 KITAS this month" is fine **with the period, definition and date stated**; "#1" is not fine at any length | L07 |
| 111 | Urgency devices | Zero countdowns, "X people viewing", "N slots left" — **unless wired to a real, checkable deadline** (a VA expiry is real; a marketing timer is not) | L06, L11, X-qwen |
| 112 | Success states | **No confetti.** A drawn checkmark (300–400ms, no bounce), the amount, a reference ID, the next step | L05, L12, X-codex |
| 113 | Accessibility overlays | **Zero, on any surface, ever.** Over 1,030 signatories: "full compliance cannot be achieved with an overlay" | L10 |
| 114 | Self-issued badges | No Bali Zero-branded "verified"/"licensed" badge graphic. **Test: who serves the asset, and where does the click land?** | L07, L08 |
| 115 | Preference media queries | All four implemented and tested: `prefers-reduced-motion`, `prefers-contrast`, `forced-colors`, `prefers-color-scheme`. All are Baseline widely available — there is no excuse in 2026 | L10 |
| 116 | Dark mode | Honour the OS `prefers-color-scheme` on **first load** — never require a toggle click to respect a preference the OS already announced | L10 |

**Standing dates**: WCAG 2.2 is a **W3C Recommendation of 12 December 2024** and is the enforceable floor; WCAG 3.0 is "an incomplete draft," not expected before ~2028, and **its contrast algorithm is undecided** (APCA was removed from the draft in July 2023) — do not design to Bronze/Silver/Gold (L10). EAA obligations for services applied from **28 June 2025**, via EN 301 549 → WCAG 2.2 AA, with a **microenterprise exemption at <10 employees and ≤ €2M turnover** (Art. 4(5)/3(23)) (L10).

---

## 4. What we must stop doing

### 4.1 Things on the live site today, caught by a lane

*Provenance caveat: L07 and L09 fetched `balizero.com` on 2026-08-31 through summarising fetchers, not raw HTML. Two independent fetchers agreeing is strong evidence, not proof. **Confirm each string with a direct `curl` before acting.***

| # | What is there now | Why it must go | Replaced by |
|---|---|---|---|
| 1 | **`4.9 ★ · 693 Reviews · 5,000+ Clients · Licensed Notary & Tax Agent`**, run **twice, as a marquee** | Every number is unfalsifiable against a third party. "Signal for signal, it is what the scam sites print" (L07). Fake/incentivised reviews became a **banned practice** under the UK DMCC Act in April 2025; the CMA opened five ratings investigations on **27 March 2026** with fines to 10% of global turnover | Keep **4.9 and 693 numerically** — L08 shows they sit in the empirically optimal band (Spiegel: purchase likelihood peaks 4.0–4.7 and *falls* toward 5.0; Baymard: 4.5★/12 ratings beat 5.0★/2). Make the string a **live link to the Google Business Profile**. Test: *could this element still render if the underlying reviews vanished tomorrow?* Prefer the one that breaks (L07, L08) |
| 2 | **`— Marco R. · Ital[y]`** testimonial | Initial-only attribution is the canonical fake-testimonial format; the FTC's rule (effective 21 Oct 2024, **$51,744/violation**) treats undisclosed composite or fictional testimonials as fake | A **screenshot of a real Google review** with the reviewer's own display name and Google's UI chrome — un-fakeable metadata the brand does not control — or nothing (L08) |
| 3 | **`<title>` "Bali Zero \| #1 Visa & PT PMA Experts in Bali, Indonesia"** | An unverifiable superlative in the **highest-weight string on the site**, squarely in the UU 8/1999 Pasal 9(1)(j) family (*"kata-kata yang berlebihan"*) | L07's falsifiable version: *"Bali Zero — PT PMA, KITAS and tax filing in Bali. Licensed. Kerobokan."* |
| 4 | **`Licensed konsultan pajak · Registered PPJK`** | Licence **adjectives**, not licence **numbers**. "'Licensed konsultan pajak' is a copycat-grade claim" (L07); "a *claim*, not a *credential*" (L08) | The **izin praktik number**, the **NPPPJK**, the **NIB**, plus lookups: `ahu.go.id/pencarian/profil-pt`, `oss.go.id`, and SIKOP's public `carikonsultan` search at `sikop.kemenkeu.go.id` — the one genuinely public registry in this stack (L07, L08) |
| 5 | **`Office in Kerobokan`** | "The same information content as 'offices in Europe and the United States'" — which is what the named fake says (L07) | The **full street address** and a map |
| 6 | **Dateline "Bali Zero · Dispatch · April 2026 · Kerobokan"** | Four months stale. "A dateline is a freshness promise; a stale one is a self-inflicted hit on the highest-authority line of the page" (L07) | **Server-render it from the same query that generates "Filed this month," or delete it.** See K4 — and note L07's own count of *four* months is right; L09's *five* is arithmetically wrong |
| 7 | **`Filed this month: 47 KITAS, 9 PT PMAs`**, undated | "An undated live counter is indistinguishable from the fake-urgency counters regulators are now targeting" (L07) | **Keep this line — L08 calls it the rarest and strongest asset in its lane.** Strengthen it on the three axes that make USCIS/Stripe/Cloudflare credible: state the **methodology**, state the **as-of date** ("as of 31 Aug 2026" / "per 31 Agustus 2026"), and **let it dip** — "a month where the number dips slightly and stays visible is worth more, credibility-wise, than a month silently swapped out." Do **not** merge it with the lifetime "5,000+ clients" figure; mixing an aggregate-since-founding number into the live-this-month unit collapses the signal that makes the second one work (L08, L07, X-qwen) |
| 8 | **H1 "Most people moving to Bali pick the wrong visa in the first month."** | **Not a defect — keep it.** L09 found real evidence: a Copyhackers home-page A/B test of a PAS (Problem–Agitate–Solve) opener returned **+49% and +46% paid lift at 99% confidence**, and the mechanism is stage-of-awareness matching — PAS wins with a *problem-aware* audience, which a first-time visa buyer is by definition | Listed here so nobody "fixes" it. L09: "do not let a stakeholder's discomfort with a 'negative' headline talk this back into 'Your visa, handled.'" But flip to certainty framing on the verdict and on GARUDA VOA, where the visitor has already self-diagnosed |

### 4.2 Techniques that are dead

- **Any number that animates.** Count-up odometers, "was" prices fading in, "you saved…" lines, a price pulse on re-render. **Eight lanes.** "A number that changes state after the user has read it is theatre, and on a page selling to people who are afraid of being scammed, theatre reads as sleight of hand" (L04). → State the number once, tabular, static.
- **The artificial "analysing your case…" delay**, and any progress animation whose duration is not bound to a real promise (L05). → Compute client-side and render in <300ms; if a server call is genuinely pending, render what is already known while it resolves.
- **`#121212` and blue-black as the dark ground.** L01 measured the envelope every reference system stays inside — none is `#000000`, none is `#121212`, all land at **L ≈ 18–20% with C ≤ 0.018**. A blue-black is "κ≈0.03 at H≈265°, i.e. **outside** the envelope every reference system stays inside — and it is the exact hue that maximises the chromostereopsis span against a red accent." **Note that L10's own recommended snippet ships `#121212`** — the folklore hex is inside this corpus, not only outside it. Tell: *if you can name the colour of the background ("navy", "midnight blue"), κ is too high.*
- **Padlock / SSL-seal / "100% secure" iconography.** Chrome retired the padlock in 2023 because "nearly all phishing sites use HTTPS." Worse, the trap L07 found: **Indonesia's own government authenticity banner teaches the public a padlock test that the named fake passes.** Any Bali Zero content repeating "look for the padlock" arms the scam.
- **Accessibility overlay widgets** (accessiBe, UserWay et al.). 1,030+ signatories: "no overlay product on the market can cause a website to become fully compliant"; disabled users describe them as "a hellish experience." FTC action against accessiBe, ~$1M final order `[M]` (L10 — ftc.gov 403'd, figures unverified). Overlays are now cited **against** defendants.
- **`text-overflow: ellipsis`** as the silent fix for overflow. "A truncated Indonesian string reads as broken, not tidy, to the exact audience the brief says is already primed to suspect a scam" (L02).
- **`clamp()` on a price, a verdict, or body copy.** "It means nobody has ever actually looked at what 'IDR 790.000' renders as at 1023px, because the formula, not a tested value, is doing the work" (L02).
- **One `Intl.NumberFormat` for both locales**; `notation:'compact'` on a payable price; `parseFloat` on an `id-ID` string (L04, L02).
- **Flags as the language switcher** — settled UX doctrine, and Indonesia is the textbook case that breaks it (L11).
- **Hero video, WebGL heroes, scroll-jacking, parallax, kinetic/scroll-scrubbed headline type, magnetic-hover and gooey-blob cursors.** Cursor effects are "meaningless on a 360px touchscreen with no cursor at all, i.e. **inapplicable to 100% of this audience by construction**" (L12). Scrolljacking: NN/g measured disorientation in most participants and outright abandonment among task-oriented users.
- **Full-page `backdrop-filter`, glass-on-glass stacking, animated blur radius** (L03). The part of Liquid Glass that reads as premium "is a GPU shader effect, not a CSS property."
- **Indigo→purple gradient with a glow; a bento grid for the four segment doors; the floating pill navbar; unmodified Inter at default weights** (L01, L03, L02, X-agy). The single most legible tell is the **glow**: `box-shadow: 0 0 60px rgba(purple,.4)`.
- **Auto-advancing banner carousels** — persist because they serve ad operations, not users `[M]` (X-qwen).
- **Placeholder-as-label**; multi-column checkout at 360–390px; a decorative micro-icon as the *only* tap target for a critical action (L10, L06).
- **`kamu` register** on any surface touching money or legal status — "it reads as a downgrade in institutional seriousness to an Indonesian reader exactly the way an immigration lawyer texting 'hey bestie' would read to an English one" (L11).
- **Batik/wayang/Garuda as decoration.** And the second-order instruction nobody else would think to write: **name this as an explicit exclusion in any image-generation brief**, because "those motifs dominate stock-photo and tourism-brand training data" and a generator will reach for them unprompted (L11).

### 4.3 Things that are now legal risk, not taste

- **A comparison table naming a competitor with an asserted number.** "Under Indonesian practice that is a defamation and unfair-competition exposure, and — worse for this brand — it makes Bali Zero sound like the agents it is differentiating from" (L04). You may state a competitor's **structure** truthfully; never their **amount**. Note that the "Us vs Government" grid is the *copycat's own signature device* (L07).
- **Composite testimonials** ("Sarah from Perth" blended from several real clients). "The single highest-risk pattern for this client specifically" — the FTC rule treats an undisclosed composite as a fake testimonial (L08).
- **AI-voice or AI-avatar video testimonials** — the FTC's 2024 consent order against Rytr put this on notice as a live enforcement target (L08).
- **A confidence percentage on a binary legal question** — plus the GDPR Art. 22 / EU AI Act Art. 86 surface. If an LLM touches the verdict page, Art. 50 requires a disclosure line from **2 August 2026**, with fines to €15m or 3% of turnover, and Bali Zero serves EU nationals (L05).
- **Any fabricated urgency device.** For this audience it "actively confirms the exact fear (scam operator) the whole redesign exists to dispel" (L06).
- **DCC-adjacent card-brand routing** that offers "pay in your home currency" — "it directly contradicts the 'the price is the whole price' promise the brief opens with" (L06).
- **QRIS advertised as universal.** Accurate only for six named nationalities' domestic apps plus anyone with an existing local e-wallet; "overclaiming it is exactly the kind of 'guaranteed'-adjacent overreach the brief already forbids" (L06).
- **An employee photograph without written, per-surface consent and a documented takedown SLA.** UU 27/2022 (PDP) Pasal 4 covers an identifiable facial image on a public page. "A face still live after someone leaves is both a compliance failure and a trust liability, because clients ask for that person by name" — and weigh harassment risk soberly, "since this same face also delivers refusals" (L05).
- **Passing MDR to the buyer.** Bank Indonesia forbids it outright — which is why "IDR 790.000, all-inclusive" is "not just marketing language — it's the legally accurate description of what BI enforces, so the page can say it with a straight face" (L06).

---

## 5. The mechanisms, not the mood board

Three rounds converged because **the brief shipped values where it should have shipped equations, envelopes and an acceptance test**. The fix is not "supply nothing" — a model given nothing returns the median of its training data, which is the same failure by another route. The fix is to supply **the generator and the envelope**, require the designer to state **which input was varied and why**, and gate the output on a test that does not care about taste.

L01 states the principle for its own domain and it generalises to all of them: "**Ship the generator, not the palette.** … the answer to 'the last three rounds all looked the same' is a **parameter sweep**, not a prompt."

### 5.1 The eleven knobs

Each of these, varied alone, produces visibly different and equally defensible work. This is the machinery.

**1 — `κ` (kappa): the chroma of the neutral.** Envelope **0.000 to 0.018** OKLCH, measured across three shipped systems (Carbon 0.0000; Radix `slateDark` 0.0041→0.0155; M3 0.0124 at hue 300°). κ=0.000 gives a Carbon-like industrial neutral; κ=0.006 gives a surface that whispers the brand hue. L01: "*two different values of κ produce two visibly different products from the same brand colour* — which is the divergence the previous rounds could not manufacture." **This is the single highest-yield knob in the corpus and it costs one number.**

**2 — `H_ground − H_accent`: the hue distance from ground to accent.** Measured from `#C8102E` (H=22.3°): warm near-black `#0F0D0C` = 26.1°; M3's `#141218` = 81.9°; blue-black `#0B1020` = 112.8°. Varying this changes the *entire* character of the dark mode **and** changes its chromostereopsis behaviour by ~4×. Constraint from §3: stay in 26–46°.

**3 — Polarity: is red the ink, or the field?** Binary, and it produces the most radically different outputs of any knob here. X-kimi's proposal — "**Invert the flag instead of darkening it.** At night, make red the field: a deep oxblood/maroon background, with warm off-white as the light" — is the only proposal in sixteen reports that no other seat reached, and X-kimi correctly diagnoses why: **all fifteen rejected night modes chose the same polarity.** Its hex ranges are explicitly reasoned proposals, not measured values — treat them as a starting point for the sweep, not an answer.

**4 — `dark_travel_multiplier`.** Range **1.2–1.6** (measured: Radix `gray` 1.56×, `slate` 1.57×, `red` 1.43×, `grass` 1.21×). This is the number that decides whether a dark mode reads as *layered* or *flat*: M3's dark ladder packs seven tiers into 16 L-points, "which is precisely why M3 dark reads as *flat* unless you also use its tint" (L01).

**5 — The spacing ratio.** Not the spacing — the **ratio** between inside-section gaps (16–24px) and between-section gaps (64–96px), i.e. **3–4×**. X-kimi supplies the best one-line diagnosis of *scialba e piatta* in the entire corpus: "**The *ratio* between small and large gaps is what creates rhythm; uniform 24px everywhere is what creates scialba.** … Uniformity is the single most common cause of the flatness the owner rejected."

**6 — The intensity budget: *which* element gets the one peak.** X-kimi's rule — "exactly one element per viewport may sit at maximum contrast/size/saturation, and the promoted element must be the thing the user came to decide" — is a *parameter*, not a style: the same layout with a different promoted element is a different product. Its allocation for this client: on GARUDA VOA the price; on the Visa Oracle the verdict plus the named human; on the home page the H1. **And the failure mode it explains**: "Every round distributed emphasis evenly … because distributing evenly is what 'clean' means to a model without an allocation decision. The eye completes its sweep in one pass, finds no peak, and files the page as *unfinished* rather than *serene*."

**7 — The type ratio, base and tier count.** Ratio (Polaris 1.2, Gojek 1.3), base size (Gojek raised its base to 12pt deliberately; X-agy wants 18px), tier count (X-kimi: three sizes, two weights, one family). All three vary independently; all three are rounded to 4px multiples so long Indonesian strings do not break the rhythm.

**8 — Easing family: "productive" vs "expressive".** Carbon ships **two complete curve families from one system** for exactly this reason — `standard.productive cubic-bezier(0.2, 0, 0.38, 0.9)` vs `standard.expressive cubic-bezier(0.4, 0.14, 0.3, 1)`. "The split exists because Carbon serves both IBM's own SaaS dashboards and public-facing product pages from one system, and a single curve family tested badly on one or the other" (L12). One token swap, two feels, both defensible.

**9 — Grain and texture, as bounded parameters not effects.** `feTurbulence baseFrequency` **0.7–1.0**, opacity **0.08–0.20**, `stitchTiles='stitch'`; halftone dot scale **0.75–1.25em**, monochrome/duotone only. L03: grain reads as *crafted* inside those bands and as *damage* above 0.3. Zero HTTP requests, inline in the same `<style>` block.

**10 — Awareness stage, per surface.** PAS/problem-first for **problem-aware** cold traffic (home page); benefit/certainty framing for **solution-aware** traffic (verdict, GARUDA VOA). Same product, different copy machinery, chosen by funnel position rather than taste (L09, with the +49%/+46% test behind the first half).

**11 — The verify/act classifier.** X-qwen's: tag **every** screen `verify` or `act`. Verify screens show everything at once and hide nothing behind an accordion. Act screens carry exactly one primary CTA, zero promotional modules, zero carousels. This is a generative rule that produces a whole information architecture from one boolean per screen — and it is derived from a real precedent, not a preference: "Gojek's home is dense, but its ride-booking task screen is sparse. Same users, same day, both modes."

### 5.2 The arithmetic that keeps it defensible

Four equations, from L01, citing Matt Ström's published generator and confirmed empirically against Radix's shipped values:

- **Lightness**: `L(n) = 1 − n`, with the branch flipping when background luminance crosses `Y_b = 0.18`. *That branch **is** the light/dark sibling rule, stated as arithmetic.*
- **Chroma envelope**: `S(n) = −4n² + 4n` — a parabola, zero at both ends, peak at mid-ramp. L01 verified it shipped: Radix `slateDark` runs 0.0041 → 0.0155 → 0.0029 across steps 1→8→12.
- **Hue drift compensation**: `H(n) = H_base + 5·(1 − n)` — 5° counteracting the Bezold–Brücke effect. Radix's `redDark` shows the same drift, 12.7° at step 3 → 23.0° at step 9.
- **The contract is contrast, not colour**: Radix guarantees **Lc 60 and Lc 90 APCA** for steps 11 and 12 against a step-2 background, and holds in both modes at different hex values.

And the rule that makes two themes **siblings rather than inversions**: Radix holds **step 9 — and only step 9 — byte-identical across light and dark** for every chromatic scale, re-deriving all eleven others per mode against the Lc contract. **The brand identity is one fixed point; everything else is derived.** L01's discriminator: "siblings have **matched Lc and different L**; inversions have **matched L-complement and unpredictable Lc**."

Applied to this project, the accent is defined not as a hex but as **"the step whose Lc against the current surface is ≥ 60"** — which resolves to a different value in each mode, automatically.

### 5.3 The two acceptance tests that gate the whole thing

**Test A — derivability (L01 F9).** For every colour, effect, spacing value and duration in the mockup: *what input produced this, and would a different input produce something different?* **Anything that cannot name its input is the fad.** This is checkable in a review by pointing at things and asking.

**Test B — falsifiability (L07 §1).** For every claim on the page: *name the external record that would falsify it.* No record → it is decoration sitting where a checkable fact should be. **Who renders the artifact?** Your own server → decoration. A registrar, regulator or platform → evidence.

### 5.4 The thing that is not a knob: the state machine

X-codex's contribution is orthogonal to all of the above and it is the one that changes what gets designed at all. **The five-screen funnel is not the product; the case ledger is, and the number of screens is an output of the state inventory, not an input to it.** Its table enumerates thirty-plus states, most of which no mockup in this project has ever depicted: *upload unreadable · passport contradicts answers · quote expired before payment · payment pending (bank may have completed this — do not pay again) · duplicate payment · paid but application cannot be assembled · submission attempted, provider unavailable · disputed or charged back · opened on second device · shared link opened by another person.*

Each row carries what the screen must say, what the system owes the user, and — the column no design system has — **who is out of pocket right now**. Its own summary of the failure mode: "Avoid the fashionable single progress bar — 'Step 4 of 5' — when the underlying process contains waiting, correction and refusal. A progress bar describes page position, not legal or financial state. **It becomes deceptive when '90% complete' remains unchanged for three days.**"

**Caveat, stated because X-codex states it**: all ten of its sources are `FROM-MEMORY (unverified)` by lane design. The state table is a **design artefact, not evidence** — it must not be cited as precedent, only used as a checklist. But as a checklist it is the most complete thing in the corpus, and every state it names is a screen someone will eventually see.

---

## 6. Decisions only the owner can make

Each is a closed question. None should be decided by a session.

**Q1 — Do we print the government/service split as two numbers, or only the total with a non-numeric inclusion list?**
*Recommendation: **print the split**, gated on a live-verified government figure with automatic fallback to the inclusion list if the check goes stale (K1).*
Cost of yes: you hand every visitor a service-fee figure to shop against, and you own a number that changes without warning — if it goes stale you are caught on the one screen where being caught re-prices everything. Cost of no: you forfeit the only claim on the page a stranger can independently falsify, against a competitor whose documented behaviour is charging "above and beyond what should be paid." **Prerequisite either way: someone must pin the current PNBP figure to a primary source. Three lanes tried and failed.**

**Q2 — Do we publish employee photographs and full names on public surfaces?**
*Recommendation: **name + role + licence number + a measured response-time commitment, yes. Photograph only with written, per-surface, revocable consent and a documented takedown SLA.***
Cost of yes: UU 27/2022 exposure, an ongoing takedown obligation, and the harassment risk L05 names plainly — "this same face also delivers refusals." Cost of no: you give up the single asset the copycat cannot fabricate, and L07's autopsy shows that is precisely where the fake's template variables are empty. Note L05's own limit: NN/g's research supports *photos of real employees over stock*, but "does not, as far as I could verify, isolate the effect of a full name, a role, or a published response time." **Never print a response time you cannot compute from your own outbox.**

**Q3 — Where does the payment boundary sit: at the verdict, or after passport preflight?**
*Recommendation: **after preflight**, with the verdict CTA reading "Continue — we check your passport before you pay" (K7).*
Cost of yes: Bali Zero absorbs review time on people who never buy. Cost of no: you charge before you know whether you can perform, which manufactures the refund cases in Q4 and puts a payment control on a verdict computed from four unverified self-reported answers.

**Q4 — What is the refund matrix, case by case?**
*No recommendation — this is a commercial and legal decision, and **the interface cannot ship without it**.* X-codex names the six cases the UI must render: customer cancellation, failed document check, duplicate charge, Bali Zero error, government-system outage, Immigration refusal. Its own warning about its placeholder copy applies: "The phrase 'may be non-refundable' is intentionally provisional here: the production copy must replace it with the verified rule and exact refundable amount. **A vague legal footnote is not acceptable.**"

**Q5 — Does Bali Zero's EU-facing entity fall under the EAA microenterprise exemption?**
*Recommendation: **design to WCAG 2.2 AA regardless**, but establish the fact.* This is a headcount/turnover question (<10 employees, ≤ €2M turnover — Art. 4(5)/3(23)), not a research question. Cost of assuming exempt: extraterritorial exposure on a payment flow that is unambiguously consumer e-commerce. Cost of assuming bound: none, since 2.2 AA is the right bar for this product anyway (L10).

**Q6 — Do we publish a "how to check any Bali visa agent — including us" page?**
*Recommendation: **yes**, dated, versioned, and wired to a real recurring check.*
Cost of yes: it raises scam salience at the moment of payment and may depress conversion — L07 searched and found **no controlled study** measuring that on an intermediary's own conversion, and explicitly refused to invent one. Cost of no: you leave the strongest available discriminator on the table. **Hard condition**: "the only thing worse than no warning page is one pointing at a dead domain" — the government's own anti-scam page currently points at `molina.imigrasi.go.id`, which resolves NXDOMAIN.

**Q7 — Do we ship the WhatsApp exit ramp at the verdict, and count a return within 72 hours as a conversion?**
*Recommendation: **yes**, with X-qwen's own falsifier attached.* The argument: "in a scam-saturated, chat-first market, the exit *is* the trust ritual. Designing it out does not keep users in the funnel; it moves the consultation somewhere you cannot measure, and somewhere you cannot bring them back from." Cost of yes: standard CRO doctrine says every exit costs conversions, and X-qwen concedes it "cannot cite a study proving chat handoffs raise completed payments." **Its 20% demotion threshold is explicitly invented, not a benchmark — do not treat it as one.** Privacy guardrail, non-negotiable: the handoff carries a case ID and a summary, **never the passport file, never personal data into chat**.

**Q8 — Does a language model touch the Visa Oracle verdict page?**
*Recommendation: **if yes, ship the disclosure line** — it is not optional.* EU AI Act Art. 50 applies from **2 August 2026**; people must be informed "in a clear and distinguishable manner at the latest at the time of the first interaction." Fines to €15m or 3% of turnover, and Bali Zero serves EU nationals. Cost of the line: one sentence. Cost of omitting it: a regulatory exposure on the screen whose whole purpose is being believed.

**Q9 — Red as the primary CTA fill: yes, and do we A/B it?**
*Recommendation: **yes to red, yes to the A/B.*** The case for red is identity and local reading, not lift — X-qwen says so itself: "I know of no solid study showing red CTAs convert better than neutral ones anywhere." Cost of yes: for the foreign visitor the Western alarm reading fires simultaneously, so red must never *also* carry error states. Cost of no: you discard the one palette move that is native to this market and unavailable to a Western-trained default.

**Q10 — Night-mode polarity: dark neutral ground with red accent, or X-kimi's inverted maroon field?**
*Recommendation: **do not decide this in prose — build both from the same generator and choose from two rendered outputs.*** This is exactly what §5 exists for: it is one binary knob, both settings are defensible, and choosing between two artefacts is a brand decision the owner is entitled to make on sight. Choosing between two arguments is not.

---

## 7. What this corpus could not verify

Aggregated from all sixteen "what I could not verify" sections, plus contradictions on points of fact that the lanes did not notice about each other. **Nothing in this section may be built on without being re-checked first.**

### 7.1 Red flags — a future session must NOT build on these

1. **The official e-VOA government fee. This is the most dangerous unverified item in the corpus, and it is load-bearing for K1.** Three lanes, three states of knowledge: **L04** fetched `evisa.imigrasi.go.id` and found "**no fee figure at all**," and consequently printed no government-fee amount anywhere. **L05** has IDR 500.000 only via The Bali Sun quoting Immigration, and warns "that number is the first thing a hostile reader checks, and it changes." **L07** verified a *different* figure — **IDR 1.500.000 for a 60-day extendable visit visa** — on the official FAQ, could not find the e-VOA fee, and wrote: "I believe it is IDR 500.000 — **do not publish on my word.**" Pin it to a primary source (the PNBP regulation for Kemenkumham/Imigrasi, or a live checkout) before any split, any comparison, or any `.go.id` link ships.
2. **The brand red itself. Two lanes used two different hexes and neither sourced it.** L01's entire colour arithmetic — the Lc −24 finding, the chroma ceiling, the hue-distance measurements — assumes **`#C8102E`**. X-qwen's contrast claim ("White on #CE1126 computes to ≈ 5.6:1") assumes **`#CE1126`**, and flags its own uncertainty ("the official spec must be verified"). **Nobody in sixteen reports verified which hex is Bali Zero's brand red, and §3's colour gates depend on it.** Resolve this first; it is a one-minute question to the owner.
3. **X-agy's target-size claim is wrong on the standard.** It states "Minimum **48x48dp** (the Android Material 3 standard, **aligning with WCAG 2.2 SC 2.5.8**)". WCAG 2.2 SC 2.5.8 is **24×24 CSS px**, as L10 verified directly against the W3C Understanding page. 48dp is Material's recommendation, not the criterion. Use L10's numbers; do not cite X-agy's.
4. **Every APCA figure in L01** was produced by a locally reimplemented APCA-W3 0.1.9 (constants from memory; validated against two canonical reference values only). L01's own instruction: "**Every Lc number in this report should be re-run through https://apcacontrast.com before it is used as a gate.**"
5. **L01's entire ambient-flare model.** The structure is sound (WCAG's 0.05 is a flare term; `E·ρ/π` is standard Lambertian) but ρ = 4.5%, 400 nits, and the 10,000/20,000 lux figures are the lane's own engineering estimates. The daylight collapse of tonal hierarchy (K2) rests on these. Replace with a photometer reading on an actual target device before quoting any ratio.
6. **`indonesia-evoa.com`'s current legal status.** L07 verified the 2022 Immigration statement naming it and that the site is live today with the quoted content — **not** whether it has since been sanctioned or become a lawfully-disclosed intermediary. In any published copy, call it "the site Immigration named in 2022, still live today, with these characteristics" — **never "a scam site."**
7. **The live `balizero.com` strings** in §4.1 were read through summarising fetchers by both L07 and L09, and the two lanes disagreed on the dateline arithmetic (four months vs five; four is correct). `curl` the page before acting on any of them.
8. **Whether "Filed this month: 47 KITAS, 9 PT PMAs" is auto-generated or hand-edited.** L09 flagged this as outside its scope. It is the load-bearing dependency for K4 — if the counter is hand-edited, the gazette direction is unavailable.

### 7.2 Numbers that are directional only — never quote these to a client as measured

- **Coulter & Coulter (2005) "Size Does Matter"** and **Huang (2025, J. Consumer Behaviour)** on price type size — publisher pages 403'd (L04).
- **Santana, Dallas & Morwitz, "Consumer Reactions to Drip Pricing" (Marketing Science)** and **Moriuchi & Murdy (2025)** — 403'd. Only the Robbert & Roth abstract was fetched, and it carries K1's load on **n=95, one scenario** (L04).
- **Buell & Norton, "The Labor Illusion" (2011)** and the **2025 ACM "false front" paper (DOI 10.1145/3735593)** — both 403'd. C1's two-sided evidence rests on search corroboration of title/venue/direction, not on reading either paper (L05).
- **Iyengar & Lepper (2000) jam-study percentages** — L09 carries ~3%/~30% from memory while search returned ~4%/~31%, with no fetch to adjudicate.
- **The 57%/43% above-the-fold mobile split** — attributed to NN/g by a secondary aggregator with no citation link; L09 could not find the primary study. NN/g's own directly-fetched figure (80.3%/19.7%) is **2010 desktop data**.
- **"53% of mobile users abandon past 3 seconds" and "7% conversion loss per second"** — secondary aggregation only (L10); X-qwen independently flags the same figure as "2016-era DoubleClick/Google, probably dated."
- **FTC v. accessiBe** (~$1M, April 2025), **UsableNet 2024** (~25% of ADA suits targeted overlay-equipped sites), **AudioEye 2026** (38.5%) — ftc.gov 403'd; the rest are secondary (L10).
- **Baymard's per-badge percentages and testimonial-lift figures** (2–5% generic / 15–25% detailed-with-photo) — **L07 and L08 independently caught these as secondary-aggregator inventions not present on Baymard's own pages.** The 70.22% abandonment, 40% extra-costs and 35.26% lift figures **were** confirmed directly.
- **Video-testimonial statistics** (8.2/10 vs 6.4/10 authenticity, 39% vs 22%) — 2025–26 industry blogs aggregating unnamed A/B tests (L08).
- **The Clutch June 2026 "36% cite real people as top loyalty driver" survey** — search snippet only (L08).
- **Countdown-timer lift figures (20–35%) and the "60% test by refreshing" behaviour** — marketing-blog aggregation; L06 says take the direction, not the numbers.
- **Wise's "80% within 2 hours" and its API-to-UI label remapping** (L06); **Xendit's "198% card acceptance improvement"** — vendor marketing, no methodology (L06).
- **X-qwen's carousel statistic** (~1% CTR, slide-1 concentration, attributed to Erik Runyon/Notre Dame) — "attribution and numbers both uncertain."
- **Chua, Morrison & Nisbett (2005)** on cross-cultural scene viewing — X-qwen cites it and then advises against acting on it: "Treat it as interesting, not actionable."
- **The 6%-of-men deuteranomaly prevalence** (L01) and **WCAG SC 1.4.11 / 1.4.1 threshold wording** — applied from memory, not fetched.
- **X-qwen's invented 20% WhatsApp-return threshold** — its own words: "invented as a testing target, not a benchmark."

### 7.3 Sources that defeated the whole corpus (JS-rendered SPAs)

Four lanes independently failed on the same two properties, which is itself worth recording: **`m3.material.io`** (L02 for the full type scale, L03 for the dp→opacity elevation table, L12 for the motion tokens, X-kimi for the dark-theme guidance) and **`developer.apple.com/design/human-interface-guidelines`** (L10 for 44×44pt, L12 for motion durations). Every Material 3 and Apple HIG number in this synthesis is therefore `[M]` — well-corroborated across secondary sources and design-community consensus, but not quoted from a primary page in this run. If any of them becomes load-bearing, open a browser.

Also unfetchable: **Linear's and Stripe's design tokens** (no public spec; the values in L03 come from third-party reverse-engineered catalogues, and L01's attempt at `designmd.cc` returned 403 — "do not cite those hexes"); **Shopify Polaris motion tokens** (URL redirected, repo layout changed — L12 dropped them rather than guess); **GOV.UK's loading-time guidance** (404; the current pattern index lists no loading/progress pattern at all); **Tokopedia's and Shopee's live homepages** (both returned SPA shells to L11 — the density claims rest on an academic comparison study, not a direct fetch); **ASPI's QRIS pages** (403 on every attempt); **`pse.komdigi.go.id`** (JS-rendered — confirm the register is actually publicly searchable before publishing a PSE number as a checkable signal); **`ejaan.kemdikbud.go.id`** (DNS failure — the "Rp with no space" orthographic rule rests on Wikipedia plus BCA's live copy, not on the primary authority).

### 7.4 Genuine open questions — nobody knows the answer

- **Indonesian text expansion has no published figure.** Two lanes searched independently and found none (L02, L11). The 35–50% budget in §3 is an engineering margin, not a measurement.
- **Whether any browser ships an `id` hyphenation dictionary** for `hyphens: auto`. L02: "no source confirmed or denied this directly; I'm recommending against relying on it based on **absence of evidence, which is not the same as evidence of absence**."
- **Display-P3 coverage on budget Indonesian Android.** Flagged independently by **L01 and X-agy** — two seats, same gap. Measure on the actual devices in the Kerobokan office before P3 affects any decision.
- **Whether Indonesia's BSN has adopted ISO/IEC 40500 as a binding SNI for private commercial sites.** L10: "a genuine open question, not a claim either direction."
- **Whether a large review count with no inspectable individual reviews measurably erodes trust.** L08 found no source addressing this scenario; its recommendation is inferred from adjacent Baymard findings.
- **Whether the October 2026 expansion of 0% QRIS MDR to all merchants up to Rp 100,000 is real.** L06 found it in search results and then **failed to corroborate it on direct fetch** — the fetched page restated only the March 2025 rule. "Do not build pricing copy on it."
- **EAA per-country penalty amounts** — set by each of 27 Member States, not enumerated in anything reachable (L10).
- **Whether the modern web-credibility literature exists at all.** L07's honest weak point, and the most important methodological caveat in the corpus: "The canonical citable work is *old* (Stanford/Fogg ~2002; Nielsen 1999; NN/g 2016). I could not surface a 2020–2026 replication of comparable authority. **Do not let anyone present 'the research says X about trust signals' as settled 2026 knowledge.**" What *is* defensible: the mechanism (signal death), the regulator rules (ASA, SRA, CMA, UU 8/1999), and the live autopsy.
- **Whether self-service converts better than a human-first WhatsApp journey for this audience.** X-codex: "Any controlled evidence… The proposed experiment is required before trusting that conclusion." Nobody has run it.
- **GOV.UK's own admitted gap, and it is exactly this project's screen.** The confirmation-pages pattern states: "*Research is needed on the best way to confirm transactions that are part of a wider user task.*" L05's conclusion is the right posture for the whole redesign: "The best design system in government has not solved this screen. **Assume version one is wrong, and instrument it.**"

### 7.5 Structural caveats on the four cross-family seats

- **X-agy**: five `VERIFIED-LIVE` citations, all bare homepage fetches with **no quoted text** — this does not meet the CONTRACT's own sourcing bar. Four findings where the web lanes deliver six to ten. Strong on direction ("Bank-Grade Ledger", `CanvasText` borders — the only forced-colors-safe primitive in the corpus), unreliable on specifics (see §7.1 #3).
- **X-codex**: **zero** live sources; all ten `FROM-MEMORY` by lane design. Its state table is a design artefact, not evidence.
- **X-kimi**: 3 verified of 14. **Every product reference in its §1 and §3 is `FROM-MEMORY`** — The Row, Stripe, Linear, Toss, Nod Young, BASAO/Tea'stone, MUJI/Hara — and its maroon hex ranges are "reasoned proposals, not tested values." Its convergence explanation for the fifteen night modes ("training-data gravity") is, in its own words, "a reasoned hypothesis about model behavior, not an established finding."
- **X-qwen**: **zero** live sources; 23 `FROM-MEMORY`, and every named interface is a pre-2026 snapshot of a product that "change[s] quarterly." Its own closing note is the correct way to read it: the mechanism-based recommendations "stand on logic and named precedent, not on studies — and they are each testable within a week of launch."
