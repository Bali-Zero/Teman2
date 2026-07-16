---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: glm-5.2)
status: round-1 raw lane output, faithfully preserved
---

# Visa Oracle — Design-Language Proposal

Ciao Antonello. Prima di entrare nel dettaglio: la mia raccomandazione di testa è **"albero decisionale vivo" come metafora primaria**, **costellazione/oracolo come sola atmosfera**, e come vero *moat* del prodotto non il quiz ma la **onestà radicale e citabile** (separazione ufficiale vs agenzia, assunzioni dichiarate, fonti Datjen verificate). Sotto il corpo tecnico in inglese (è un design doc, va a designer/dev e pullula di termini tecnici EN) — la riga finale in italiano con i prossimi passi.

---

## Design thesis

Build a **living decision tree** as the core metaphor — honest, legible, infinitely scalable, mobile-friendly, and unmistakably *systematic* (which is exactly what a government audience reads as credible). Wrap it in restrained **constellation / "oracle" atmosphere** for the thematic mystique the name promises, but **never let the atmosphere become the data structure** — that way the product reads as "wise guide," not "fortune teller." Deliver the verdict as a **card**, and build the outcome page around **radical fee-honesty** and **rewritable history**. The credibility skeleton is **GOV.UK**; the craft layer is **Linear / Stripe / Apple**; the Indonesia-mobile reality layer is **Grab / Gojek**. The product's moat is not the quiz — it's the *visible, citable separation of official truth from agency service.* No one in this market does that cleanly; doing it cleanly is the demo-winning move.

> Regulatory specifics below (fee figures, E-codes, PP 21/2022 thresholds, durations) are **illustrative patterns**, not ground-truth — those come from the curated visa KB / NotebookLM at build time. This doc owns the *design language*, not the data.

---

## 1. Wizard UX — 2026 state of the art

**The honest finding:** one-question-per-screen (the Typeform move) is still the best engagement primitive for *branching discovery*, but used blindly it creates three known traps — endless-feeling depth, fake-linear progress, and expensive backtracking. The 2026 SOTA answer is a **hybrid with a seam**:

- **Discovery phase (Q1…Qn): one-question-per-screen.** Every answer changes the tree, so you want focus, low cognitive load, and the satisfying *branch-prune* payoff animation. Mobile-thumb-zone CTA. Keyboard-answerable.
- **Confirmation phase: grouped, editable "your answers" card.** Before generating the verdict, show everything captured in one scannable card, each field inline-editable. This is what gives the flow *government credibility* (transparency, auditability) and kills the Typeform-trap of "I can't see what I said." (Steal this seam from Stripe onboarding.)

**Progress for a variable-depth tree — the core problem.** Do NOT fake a linear % bar on a tree whose depth varies by branch; it lies. Use one (or a pairing) of:
- **"Paths remaining" counter** — a live number ("12 → 3 → 1 possible visas"). Native to a decision tree, more honest than %, and it turns the funnel into a tangible narrowing. Pair it visually with the tree prune (#1 / #2 signature interactions) so you get a dual visual+numeric encoding (also an accessibility win).
- **Branch-aware breadcrumb** — "You're on the Work → E23 lane," not "Step 4 of ?". Shows *path*, not fill.
- **Hide progress in Q1–Q2, reveal once committed.** Don't front-load the perceived cost; once they've answered twice, they're invested — now progress helps.

**"Why are we asking this?" (branching transparency).** Every sensitive question (nationality, income, marital status, criminal record) carries a tiny disclosure glyph → one sentence + the regulation it maps to. *This single pattern is your government-demo armor.* "We ask nationality because eligibility is set by PP 21/2022 and bilateral agreements." Direct from the GOV.UK "why we ask" doctrine.

**Backtracking & editing.** Full history stack; every answer editable; tree re-prunes live on edit; **never "start over."** Back button must be instant (client state, no reload). The "rewritable path minimap" (#6) is the flagship expression of this — it's *uniquely* native to a decision tree and most competitors don't bother.

**Save/resume.** Autosave every answer to `localStorage`, keyed by anonymous session id; no login required to use the public tool. **Encode answers in the URL** (compressed) so any result is shareable/bookmarkable — huge for virality and for the Jakarta demo ("here is a real, generated path"). Offer *"email me my roadmap"* at the end = lead capture (this is, in the end, a business tool).

**Skip-with-assumptions.** A "Not sure?" affordance on questions where a safe guess exists — it takes the conservative branch and **flags the assumption visibly** on the outcome ("We assumed you're applying from abroad — if you're already in Indonesia, revisit Q3"). Keeps momentum *without hiding uncertainty* — the opposite of a magic-8-ball, and it feeds signature interaction #9.

> **Recommendation:** one-question-per-screen for branching discovery → grouped editable confirmation card → verdict. Engagement of Typeform, credibility of GOV.UK.

---

## 2. The visual metaphor

| Metaphor | Elegance | Mobile perf | Gov credibility | Cost | Verdict |
|---|---|---|---|---|---|
| Journey / route map (archipelago) | High, very Bali | Medium | **Medium-low** (touristy) | Med-high | Atmosphere only |
| Subway map | Clever, readable | **Hard** (wide) | Medium | Medium | Pass |
| Garden of forking paths | Poetic (Borges) | Hard (abstract) | Low | High | Pass |
| Constellation / star map | **Very high** | Med-high | Medium (restrained OK) | Medium | **Atmosphere layer** |
| Card / tarot "Oracle" | Thematic | **Excellent** | **Low if literal** (fortune-telling) / High as UI primitive | Low-med | Outcome tile, not nav |
| 3D overworld | Wow | **Poor** | Low (gimmick) | Very high | **Reject** |
| **Living decision tree** | **High** | **High** (vertical/stacked) | **High** (systematic) | Medium | **PRIMARY** |

**Recommendation — a coherent trio, each doing what it's best at:**

1. **PRIMARY structure = the living decision tree.** The product *is* a decision tree; the most elegant move is to **show the tree as the thing**, not disguise it as a subway or a garden. It is honest, legible, scales to 90 visa types, works vertically on mobile, reads to a Jakarta audience as *rigorous and transparent*, and it gives you the signature "tree breathes / prunes" interaction for free. On mobile, render branches as a stacked, scrollable vertical tree (parent above, live children below); on desktop, a fuller radial or left-to-right orchard.
2. **SECONDARY atmosphere = restrained constellation / star-map.** This carries the "Oracle" theme *without* the fortune-telling credibility problem. Slow-drifting points of light behind the tree, in both themes (stars on dark; subtle topographic dots on light). It is **mood, never the data structure**, and never cursor-chasing.
3. **TERTIARY tile = the card.** Reserved for the *outcome* — each recommended visa is a card, dealt by the tree (#4). Not used for navigation.

The word "Oracle" must read as **wise authority / guide**, not fortune-teller. The constellation earns the mystique; the tree earns the trust.

---

## 3. The outcome page (the money screen)

Hierarchy, top→bottom — the verdict dominates above the fold on every viewport:

1. **Verdict headline.** The single strongest path, large and confident: *"Your path: **KITAS E28A — Investor**"* + one-line plain-language summary. If several fit: *"3 paths fit you — here's the strongest,"* then surface the comparison.
2. **Eligibility verdict card.** Never binary. Four states — *Eligible / Likely eligible / Conditionally eligible / Likely not eligible* — each with the specific blocker and one-line reasoning ("Based on investment ≥ threshold and a qualifying sponsor entity"). Color **+ icon + text** (never color alone).
3. **Visa comparison** (when ≥2 fit). Tight cards/table: code, name, duration, renewability, work rights, path-to-permanent, official cost. Sortable. *This is where authority lives.*
4. **Personalized timeline.** Anchored to **TODAY**: Apply → Approval → Issuance → Arrival/Conversion → Renewal. Honest *ranges* (e.g., B211A ~days-to-weeks; KITAS ~weeks via Pra-izin), never false precision.
5. **Cost breakdown — the honesty differentiator.** Two clearly separated columns: **Official fees** (Imigrasi/Ditjen, published, cited) vs **Agency/service fees** (Bali Zero's, transparent). **Never blended.** Show the total. Cite the fee schedule. *This single design choice is what makes the tool demo-able to the government AND trusted by expats* — visible proof Bali Zero hides nothing. (Signature interaction #5.)
6. **Documents checklist.** Grouped by stage, checkable, with "do you have this?" toggles that refine timeline + next-steps. Downloadable.
7. **Your next 3 steps.** Concrete, ordered, time-bound: *"1. Gather passport + sponsor docs (this week). 2. Book a 20-min consult (link). 3. We file within 5 business days."* This is the conversion engine.
8. **Share / Print / PDF roadmap.** Server-rendered, branded, print-optimized PDF of the whole verdict — the artifact an expat forwards to a spouse or employer.
9. **QR → continue on WhatsApp.** A QR that deep-links into Bali Zero's existing WhatsApp channel **with the session pre-loaded** ("Hi, I just used Visa Oracle — got KITAS E28A, session #abc"). Frictionless handoff from tool to human/agent channel. *This is the business payoff.*
10. **Assumptions & caveats footer.** Every skip-with-assumption surfaced here, **dated**, with *"regulations verified as of \<date\>"* and a tap-through to cited sources. Plus the disclaimer: *"Informational guide; final eligibility is determined by Ditjen Imigrasi."* Mandatory for credibility.

**Layout:** single-column stack on mobile; on desktop, two columns (verdict + timeline left, cost + docs right) — but the verdict headline + eligibility card own the first viewport on both.

---

## 4. Motion & micro-interaction

**Principle: motion must encode tree-navigation, not decorate.** Test: *if removing a motion makes the app harder to understand, it earned its place; otherwise cut it.*

**Earns its place (comprehension):**
- **Branch prune/advance transition** — when an answer prunes the tree, dead branches *recede* (fade + contract toward parent) while the chosen branch *advances*. You see *where you moved*. Core payoff of the tree metaphor. Use **FLIP** so the move feels physical, not teleporty.
- **"Paths remaining" count** animating down with a subtle tick — you *feel* the narrowing.
- **Verdict reveal** stages in deliberately (headline → verdict → timeline), with **spring physics** on the card entrance so it lands with weight. This is the emotional *moment*.
- **Skeleton states** during (lightweight) computation — content-shaped placeholders, **never spinners**.

**Cut (noise):** parallax-on-scroll, auto-rotating testimonials, cursor-chasing particles, bouncing icons, decorative swirls. (Cursor-chase reads as a 2010 portfolio site and **kills** gov credibility.)

**Techniques:**
- **View Transitions API** for cross-question navigation — native, handles FLIP where supported (good fit for Next.js App Router), graceful CSS fallback elsewhere.
- **Motion library / Framer Motion** springs on card entrances, the verdict, and the live-count number.
- **Shared-element transition** — the chosen visa *node* in the tree *morphs* into the verdict *card* on the outcome page (#4). High craft, medium cost.
- **Haptics** — subtle Vibration API buzz on 1–2 key commits only (verdict reveal, branch commit); no-op where unsupported; never every tap.
- **`prefers-reduced-motion`** — full support; every effect collapses to instant/crossfade. Non-negotiable for accessibility *and* gov credibility.

---

## 5. Reference class — what to steal from each

| Source | Steal |
|---|---|
| **GOV.UK Design System** | *The entire credibility layer.* "One thing per page," "why we ask," plain language (~grade 8), ruthless WCAG, the validation/error pattern, honest no-nonsense tone. **Your gov-demo armor.** |
| **Stripe onboarding** | The grouped editable confirmation step; calm premium typography; making complex compliance feel manageable; the honest-fee-display DNA. |
| **Linear** | Keyboard-first everything (answer by typing/arrow keys); motion economy; "fast and confident" feel. Steals: **keyboard nav + motion discipline.** |
| **Apple guided setup** | Progressive disclosure; large confident type; whitespace; "someone smart made this for you." Steals: typographic confidence. |
| **Typeform** | Conversational one-question flow; smooth transitions. Steal the *feel* — **not** the endless-depth trap (the tree structure mitigates that). |
| **Duolingo** | Progress that motivates without anxiety; encouraging micro-copy. Steal the copy warmth — **not** the gamification (wrong register for government). |
| **Airbnb search** | Map+list duality (here: tree+detail); mobile filter excellence; "many options → one." Steal the **master-detail pattern** for visa comparison. |
| **Arc Browser onboarding** | Permission to have a restrained point of view; small surprising-but-functional moments. |
| **Grab / Gojek** | **The Indonesia reality layer.** One-handed/thumb-zone CTAs; Bahasa-first register; low-data performance budget; resilience on flaky connections (critical in Indonesia). |
| **WeChat mini-programs** | Instant, no-install, lightweight feel; dense-but-legible mobile UI. |

**Net:** GOV.UK = skeleton · Stripe/Apple = premium typography · Linear = interaction craft · Grab/Gojek = mobile/Indonesia reality · Typeform = flow · Arc/Duolingo = restrained personality.

---

## 6. Multilingual + accessibility

**Languages:** EN + ID as **co-first-class** — not ID-as-translation-of-EN. Both written natively. The ID version uses Imigrasi's own terminology fluently ("Izin Tinggal Terbatas," not an awkward back-translation of "Limited Stay Permit"). *That native fluency is itself a credibility signal in the Jakarta demo.* RU/ZH later as progressive enhancement.

**Language switching mid-funnel:** persist answers in a **language-agnostic shape** (answer keys/ids, never localized strings). Toggling the header flag re-renders the *current* question in the new language **instantly — no reload, no lost place, no lost history.** The PDF is generable in either language on demand.

**WCAG — target AA, aspire AAA on the critical path (this is a government demo):**
- Full keyboard nav (Linear-style), visible focus, logical tab order, **no keyboard traps.**
- Semantic HTML throughout; **live-regions** announce the dynamic "N paths remaining" count and the verdict reveal to screen readers.
- Color contrast AA on all text; eligibility verdict **never color-alone** (always icon + text + color).
- The tree visualization **must have a non-visual equivalent** — a nested list / SR-only path description. A decorative tree can't be the only way to understand structure.
- `prefers-reduced-motion` respected everywhere.
- Plain language (~grade 8) — helps non-native EN speakers too.

**Theming:** dark + light, system-default with manual toggle. **Dark = premium oracle/constellation mode; light = clean government/credibility mode. Default to LIGHT for the Jakarta demo.** Both fully contrast-compliant; the constellation ambiance adapts (stars on dark; subtle topographic dots on light).

---

## 7. Ten signature interactions

1. **"The tree breathes."** As you answer, ineligible branches don't vanish — they fade and curl inward like a plant self-pruning, while live paths glow softly. You *viscerally* feel the decision narrowing. *Feasibility: medium* — SVG/Canvas tree + FLIP on prune; reduced-motion → instant hide.
2. **"Paths remaining" counter.** A live corner number ("12 possible visas" → "3" → "1") ticking down. Turns a vague funnel into a tangible narrowing; pairs with #1 as a dual encoding. *Feasibility: easy.*
3. **"Why we ask" whisper.** Every sensitive question carries a glyph; tap reveals one sentence + the mapped regulation (e.g., PP 21/2022). Makes the invasive feel respectful and citable — the government-credibility workhorse. *Feasibility: easy.*
4. **"The Oracle deals your card."** On verdict, the chosen visa *node detaches* from the tree and resolves into a full hero card with a spring-weighted settle. The thing you were watching *becomes* your answer. *Feasibility: medium* — shared-element transition.
5. **"Honest ledger."** The cost breakdown splits with a physical-feeling motion into two columns — official Imigrasi fees slide from one side, agency fees from the other — meeting at a clear total. *The separation is the trust.* *Feasibility: easy-medium.*
6. **"Your path, rewritable."** A minimap of the route you took lives in a side rail (bottom sheet on mobile); tap any past answer to jump back, change it, and watch downstream re-prune live. **No "start over," ever.** *Feasibility: medium* — history stack + re-evaluation.
7. **"Timeline that anchors to today."** The personalized timeline marks TODAY and runs forward as a river — Apply → Approve → Issue → Arrive → Renew — with honest duration ranges. *Feasibility: easy.*
8. **"QR handoff to a human."** A QR encodes your full session (path, verdict, assumptions) into a WhatsApp deep-link; scanning drops you into the existing Bali Zero channel with context pre-loaded. Frictionless tool→service bridge. *Feasibility: easy.*
9. **"Assumptions, surfaced" — the honesty receipt.** Every "skip-with-assumption" is collected on the outcome as a dated, checkable receipt ("You skipped nationality — we assumed non-ASEAN, conservative"). One tap revisits. *The product's integrity made visible.* *Feasibility: easy.*
10. **"Regulation-verified watermark."** The outcome carries a live *"Verified against Ditjen Imigrasi sources as of \<date\>"* stamp, tap-through to cited regulations. The credential that makes it demo-able in Jakarta and shareable by expats. *Feasibility: easy to render; the "live" freshness needs a verification pipeline (medium ops).*

*Throughline:* interactions 3, 5, 9, 10 are all expressions of one value — **visible honesty** — which is the product's real moat. 1 and 2 are a paired narrowing-encoding. 4 and 6 are the craft flexes. 7 and 8 are the conversion/business bridge. That balance is deliberate.

---

## Anti-patterns — what NOT to do

- **Don't fake a linear progress bar** on a variable-depth tree (it lies).
- **Don't blend official + agency fees** (destroys the moat).
- **Don't use literal tarot/fortune-telling visuals** (kills government credibility — the "Oracle" is a wise guide, not a seer).
- **Don't ship a 3D overworld, parallax, or cursor-chasing particles** (gimmick + perf + accessibility disaster).
- **Don't force login to see the result** (kills conversion and reads as anti-openness to a government audience).
- **Don't auto-play anything** (video, audio, carousel).
- **Don't hide assumptions or caveats** — they are the credential, not a liability.

---

## Implementation-feasibility snapshot

- **Cheap, do on day one:** paths-remaining counter, "why we ask," honest ledger, assumptions receipt, QR→WhatsApp, light/dark theming, EN/ID co-first switching, full keyboard + WCAG.
- **Medium, the craft backbone:** living-tree prune animation (FLIP), rewritable-path minimap, shared-element "card deal" verdict, regulation-verified freshness pipeline.
- **Defer / skip:** 3D overworld, literal tarot visuals, gamification, any motion that doesn't encode navigation.
- **Tech fit:** Next.js App Router + View Transitions API + Motion library + server-rendered PDF + `localStorage`/URL state — all well within a Vercel deploy; the recommendation engine stays thin and client-first (the heavy regulatory truth lives in the curated KB / NotebookLM, surfaced via the existing RAG, not re-derived in the browser).

---

Riga finale in italiano: la mossa vincente non è "fare un bel quiz" — è fare **l'unico strumento nel mercato Indonesia che separa visibilmente la verità ufficiale (Datjen) dal servizio agenzia (Bali Zero), con fonti citate e assumzioni dichiarate**. Il quiz serve a *dimostrarlo*, non a nasconderlo. Metafora: albero vivo + atmosfera costellazione + carta-risultato. Credibilità = GOV.UK, craft = Linear/Stripe/Apple, mobile-Indonesia = Grab/Gojek.

Prossimi passi che ti propongo (dimmi quale vuoi che parta subito):
1. **Salvo questo doc** come design doc nel repo (es. `design/visa-oracle/design-language.md`) così è tracciato e condivisibile col team/dev.
2. **Lo faccio passare dal panel 4-LLM** (Gemini + Codex + DeepSeek + NB ground-truth) come review avversaria sulla tesi di design — prima di buildare, come vuole la regola per spec architetturali.
3. **Prototipo la signature interaction #1 + #4** (tree che respira + carta-risultato) in un mini-demo HTML/CSS/JS per validare "immediatezza estetica" prima di imbarcarla in Next.js.
4. **Mappo i ~90 visti** del KB esistente sull'albero decisionale (nodi, branch, gating) per dimensionare il vero scope dell'intervista.

Quale parto? Non ho usato tool esterni qui: il deliverable è sintesi di design, e i dati regolatori specifici andranno presi dal KB/NotebookLM a build time, non inventati in questo doc — se vuoi posso verificare su web lo stato corrente del View Transitions API o recuperare screenshot dei pattern di riferimento come follow-up.
