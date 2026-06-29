---
date: 2026-06-25
domain: marketing
client_case: Bali Zero WR2 carousel / WR3 video editorial war-room — "the perfect agentic workflow with all the psychological nuances of SOTA-level communication"
author: deep-researcher (external consultant brief, Antonello/Bali Zero)
status: draft
sources:
  - Instagram 2026 ranking-signal coverage (Socialync, Later, Buffer, Hootsuite, GOSO)
  - Anthropic "How we built our multi-agent research system" (engineering blog)
  - Multi-agent debate empirical critiques 2026 (Iterathon, arXiv MAD analyses)
  - Loewenstein information-gap theory + headline-concreteness backfire study (PMC11704130, Upworthy archive)
  - Slamecka & Graf 1978 generation effect; Zeigarnik effect literature; processing fluency / desirable difficulty (Bjork)
  - Berger STEPPS / social currency (Contagious)
  - Kahneman & Tversky prospect theory / loss aversion; ELM source credibility
  - Voyager (Wang et al. 2023) skill library; Reflexion (Shinn et al. 2023) verbal RL
  - Agentic production failure-mode literature 2026 (runaway cost, hard termination)
partial: false
---

# The Perfect Agentic Workflow with SOTA Communication Psychology

**Date**: 2026-06-25 · **Domain**: marketing · **Author**: deep-researcher (external consultant brief) · **Status**: draft

## Question

(Owner's literal ask, June 2026) "Find the perfect agentic workflow with ALL the psychological nuances of SOTA-level communication" — for an autonomous multi-agent war-room (WR2 Instagram carousels + WR3 short videos) marketing Indonesian regulatory/legal expertise (visa, company setup, tax, property) to expats, founders, investors, nomads, retirees.

## TL;DR (3 bullets)

- The 2026 algorithmic currency is the **DM send (share-to-friend)**, reportedly weighted ~3-5x a like for reaching new audiences and ranked above saves; the entire content architecture should be engineered backwards from "why would one person forward this to one specific other person." Saves (the "I'll need this later" utility bookmark) are the second axis and map naturally onto compliance/regulatory content.
- The correct workflow is a **grounded orchestrator-worker with a maker-checker cost split and a binary JUDGE gate** — NOT a debating committee. The committee earns its ~2x cost only where there is a *measured* failure mode; for a regulatory publisher that failure mode is **hallucinated law**, so the justified "committee" is a 3-station grounding spine (interpreter cites → critic verifies → judge gates), not N agents arguing taste.
- The single biggest lever is **closing the loop**: a self-evolving skill library (Voyager-style executable skills) refined weekly by a Reflexion loop whose reward signal is **real saves/forwards per reach**, not "the draft passed review." This makes the system literally learn what gets forwarded instead of what an LLM guesses is good.

## Part 1 — The psychology of save-and-forward content

### 1.0 Why this is the only metric that matters in 2026

Multiple independent 2026 trade sources converge: Instagram's ranking now treats **sends per reach (DM shares)** as the strongest distribution signal, above likes and above saves, with the share-to-DM being weighted materially higher than a like for reaching *new* (non-follower) audiences — trade coverage puts the share-vs-like multiplier in a ~3-5x band, and reports a published signal hierarchy of impression < view < like < comment < save < share-to-story < **share-to-DM (strongest)** (Socialync 2026; Later 2026; Buffer 2026; GOSO 2026). One concrete benchmark surfaced repeatedly: **"sends per reach"** thresholds of <0.5% = not shareable, 0.5-1% = baseline, 1-2% = solid, 2-3% = strong, >3% = "viral territory" (Socialync).

**Honesty caveat (established vs. emerging):** That sends > saves > likes ordering and the "shares are the strongest signal" framing are **paraphrased from creator-economy trade press citing Mosseri, not from a primary Meta engineering disclosure with published weights.** The *direction* (sends dominant, likes weak) is well-corroborated across sources and consistent with Mosseri's public 2024-2025 statements; the *exact 3-5x multiplier and percentage thresholds* are emerging/industry-estimated, not proven constants. Treat them as design priors, not laws. The behavioral mechanisms below (Loewenstein, Slamecka & Graf, Berger, Kahneman) ARE established peer-reviewed science and are the durable foundation; the algorithm weights are the volatile surface.

For each mechanism: **principle → carousel manifestation → backfire mode.**

### 1.1 Curiosity gap (information-gap theory) — and the vague-gap failure

- **Principle:** Loewenstein (1994) — curiosity is a *deprivation* drive triggered by a perceived gap between what you know and what you could know; a "priming dose" of information sharply raises the drive to close the gap. Curiosity is aversive (it itches), which is what makes it motivating.
- **Manifestation:** Slide 1 names a *specific, consequential* unknown the reader did not realize they had ("Your PT PMA's KBLI code may now be wrong — OSS auto-converted 1,789 codes to 1,559 on 18 Dec 2025"). The gap is between "I assumed my license was fine" and "a deadline clock may be running on me."
- **Backfire mode — THE VAGUE GAP (quantified):** The headline-concreteness study (PMC11704130; meta-analysis of **8,977 A/B tests / 35,910 headlines**, Upworthy archive) found a **curvilinear** relationship. When headlines are already too vague (concreteness < 2.58, ~8.7% of tests), *adding* concreteness lifts clicks ~5.5%; when already concrete (> 3.06, ~50.9% of tests), adding more *cuts* clicks ~9.9%; the sweet spot is "middling" (2.58-3.06). Decision-relevant reading: publishers **systematically err toward over-vagueness**, and a vague-clickbait gap ("This visa change will shock you") underperforms a specific gap ("B211A no longer converts onshore — here's the one exception"). For a *regulatory* publisher the specific gap is also the trust-building gap. **Rule: be specific enough to prove the payoff exists; withhold only the resolution mechanism.**

### 1.2 The generation effect — make the reader's brain do the work

- **Principle:** Slamecka & Graf (1978), robust across cued recall, free recall, and recognition over five experiments and confirmed by later meta-analysis: **self-generated information is remembered better than read information.** Engaging the reader to produce the answer (or a piece of it) deepens encoding.
- **Manifestation:** A mid-carousel slide poses the question and lets the reader predict before the reveal ("Guess which of these 3 triggers an LKPM filing? …"), or a self-check ("If your akta predates 2021, ask: was your KBLI ever remapped?"). The reader generates, then the next slide confirms.
- **Backfire mode:** If generation is too hard or ambiguous (the reader can't plausibly produce an answer) it becomes frustration, not engagement — this is the boundary of *desirable* difficulty (Bjork): difficulty helps memory only while it remains surmountable. A quiz the expat cannot possibly answer reads as gatekeeping and is scrolled past.

### 1.3 Zeigarnik effect / open loops

- **Principle:** Zeigarnik — interrupted/unfinished tasks occupy privileged memory and create a mild tension that seeks closure. **Replication caveat (contested):** the original 1927 effect has a mixed replication record; several attempts failed to reproduce the recall advantage. Treat open-loops as a *reliable attention/retention heuristic in practice* but an *empirically contested lab effect* — do not overclaim it as settled.
- **Manifestation:** A carousel opens a loop on slide 1 ("There are 3 deadlines hidden in PP 28/2025. Most agencies only tell you about one.") and only closes it on the payoff slide. The open loop is the tension that pulls the swipe.
- **Backfire mode:** An opened loop that is never satisfyingly closed (or closed with an anticlimax / a "DM us to find out") converts tension into betrayal — the reader feels baited and is *less* likely to forward, because forwarding bait makes the forwarder look bad (inverse social currency, see 1.6).

### 1.4 Processing fluency vs. desirable difficulty (the tension to manage)

- **Principle:** Two opposed forces. *Processing fluency* — easy-to-process content feels more true, more likeable, and is judged more credible (fluency is mistaken for validity). *Desirable difficulty* (Bjork) — effort improves memory and value. SOTA communication resolves the tension: **fluent surface, deep substance.** The slide should *read* effortlessly (short lines, clean hierarchy, one idea per slide) while the *content* makes the reader think.
- **Manifestation:** Plain-language gloss on a hard legal term (fluency) wrapped around a genuinely non-obvious regulatory consequence (difficulty). The verbatim code in monospace is fluent to *recognize* as authoritative even when the law itself is hard.
- **Backfire mode:** Over-fluent = vapid (looks like every other "5 tips" carousel, no reason to save). Over-difficult = legalese wall, scrolled past. The failure is picking one pole.

### 1.5 Identity / tribe signaling — "this is for people like me"

- **Principle:** People forward content that affirms or advertises their identity. Berger's STEPPS frames this under *social currency* and *public*: sharing is self-presentation.
- **Manifestation:** Slide 1 names the tribe explicitly ("If you run a PT PMA in Bali…", "Foreign property buyers on Hak Pakai…"). The reader self-selects: *this is for me / for someone like me.* Forwarding then becomes "you're in my tribe, this is our problem."
- **Backfire mode:** Naming the tribe too narrowly kills reach (audience too small); too broadly kills the signal (no one feels *seen*, so no one forwards to a specific person). The art is naming a tribe the reader is *proud* or *anxious* to belong to.

### 1.6 The "I'll need this later" utility bookmark (the SAVE instinct)

- **Principle:** Berger's *practical value* — useful content gets passed and stored. Saves are the bookmark for future-self utility; for *compliance/deadline* content the save is rational ("I will need this exact date/code in Q3").
- **Manifestation:** A "reference slide" engineered to be saved: the verbatim regulation code, the deadline, the threshold, laid out as a clean card the reader will want to retrieve. Saves are the *second* currency after sends, and regulatory content is structurally save-rich.
- **Backfire mode:** If the reference is incomplete (date but no code, code but no action) the save loses utility and the content is not re-surfaced — and worse, a *wrong* date destroys the trust moat (see 1.8).

### 1.7 Social currency — why people forward (to look smart / helpful / in-the-know)

- **Principle:** Berger — people share to look clever, informed, or generous. Forwarding a sharp regulatory insight makes the sender look like the friend who is *on top of it*. The forward is a gift that reflects on the giver.
- **Manifestation:** The LAST slide should make forwarding a *flattering act*: "Know a founder who hasn't checked their KBLI conversion? Send them this." The forwarder gets to be the helpful insider.
- **Backfire mode:** Content that makes the *forwarder* look gullible (clickbait, fearmongering, anything that didn't pay off) carries *negative* social currency — people won't risk their reputation forwarding it. This is why vague-gap + unclosed-loop content fails to share even when it gets opens.

### 1.8 Authority / verbatim-citation trust multiplier (the unfakeable moat)

- **Principle:** Source credibility (ELM) raises persuasion, especially as a peripheral cue under low elaboration — and competence/trustworthiness/good-faith is the credibility triad. For a regulatory publisher, **a verbatim, checkable citation (real code + article + date) is an authority signal that competitors using vague paraphrase cannot cheaply fake** — it converts a peripheral cue into a verifiable central one.
- **Manifestation:** "Permenkum 49/2025, in force 17 Dec 2025" in monospace, not "a recent regulation." The specificity is simultaneously a curiosity-gap payoff, a save-worthy reference, and a trust moat. Citing the real artifact is the brand's structural advantage.
- **Backfire mode:** A *fabricated* or stale citation is catastrophic — not a typo but a liability. A reader who acts on a hallucinated visa rule and gets burned never forwards anything again, and a regulatory publisher's entire moat is "we cite the real thing." This is the hard constraint that dictates the workflow's grounding spine (Part 3).

## Part 2 — Content architecture that encodes the mechanisms

### 2.1 Slide-level mandate

- **Slide 1 (the hook) — specific gap, named tribe, opened loop.** Must do three things at once: name *who* this is for (1.5), name a *specific* consequential unknown (1.1, avoiding the vague-gap backfire 1.1), and open a loop (1.3). NOT "Big visa changes you need to know" (vague gap, no tribe). YES "PT PMA owners: OSS just remapped your KBLI code — and a 6-month clock is running."
- **Narrative arc: hook → frame → discovery → payoff → send-reason.**
  - *Frame:* establish stakes and the reader's current (wrong) assumption.
  - *Discovery:* the generation-effect beat — let the reader predict; reveal the non-obvious mechanism.
  - *Payoff:* close the loop with the verbatim citation (1.8) and the save-worthy reference card (1.6).
  - *Send-reason:* explicit forward prompt framed as social currency (1.7).
- **The LAST slide is the forward/save trigger, not a logo.** Its only job is to convert a satisfied reader into a sender: name the *specific other person* to forward to ("a founder who hasn't checked…"), or make the save explicit ("Save the date card — Q3 LKPM is 15 Jul"). A last slide that is just branding wastes the highest-intent moment.
- **Bilingual gloss discipline:** EN default (expat audience), **ID legal term kept verbatim** (KBLI, PT PMA, Hak Pakai, LKPM, RUPS — never translated; the term IS the authority cue), with **one first-use gloss** in plain EN. Pattern: *"LKPM (the quarterly investment-activity report)"* once, then "LKPM" thereafter. The untranslated term is trust (1.8); the one-time gloss is fluency (1.4).

### 2.2 What a "forwardability score" should actually measure

Not "is this good." It should be a weighted predictor of *send-per-reach*, decomposed into the mechanisms so it is diagnosable:

1. **Tribe clarity** (slide 1 names a specific addressable identity) — binary.
2. **Gap specificity** (slide 1 proves a real, specific consequence exists; not vague) — scored against the concreteness sweet-spot, penalize vagueness *and* over-specification.
3. **Loop integrity** (opened on slide 1, *closed* by payoff) — binary; unclosed = fail.
4. **Citation verifiability** (≥1 verbatim code+article+date, verified against ground truth) — binary, hard gate.
5. **Save-utility** (a complete reference: code + date + action) — binary.
6. **Send-reason presence** (last slide gives a flattering forward reason naming a recipient) — binary.
7. **Fluency** (one idea/slide, glossed terms, scannable) — scored.

The score is *predictive of the algorithmic currency*, and (Part 3) is later *calibrated by real saves/forwards* so it stops being taste and becomes a learned function.

## Part 3 — The perfect agentic workflow (the heart)

### 3.1 Orchestrator-worker vs. single-agent — and where the committee is actually justified

- **Established finding:** Anthropic's multi-agent research system (Opus-4 lead + Sonnet-4 subagents) **outperformed a single Opus-4 agent by 90.2%** on their internal research eval — but at **~15x the token cost of a chat** (agents alone ~4x; multi-agent ~15x). Token usage alone explained **~80% of performance variance**. Multi-agent wins specifically on **breadth-first, parallelizable** tasks.
- **The contested counter-finding (emerging, 2026):** In broad cross-benchmark analyses, multi-agent *debate* rarely beats strong single-agent self-consistency/CoT **when compute is matched**; gains concentrate in high-difficulty cases and vanish with scale or easy tasks. Reported case: **+2.1pp (94.3% vs 92.2%) at ~2x cost** and added latency; above ~45% single-agent accuracy, extra agents often yield *negative* returns; planning tasks *degrade* under multi-agent (-39% to -70%) because coordination fragments linear reasoning. **The honest synthesis: multi-agent earns its 2-15x cost only against a *measured* failure of the single agent.**
- **Mapping onto Bali Zero:** Carousel drafting is NOT a breadth-first research task — a single capable agent drafts a carousel fine. So a *debating committee on taste* is unjustified (it would be the -2.1pp-at-2x-cost trap). The justified multi-station structure is **not about argument quality, it is about the one measured failure mode that matters: hallucinated regulation.** The "committee" collapses to a **linear grounding spine** (interpreter → critic → judge), each station cheap and single-purpose, not N agents debating.

### 3.2 The 5 roles

| Role | Type | Job | Model tier |
|---|---|---|---|
| **Producer** | worker | Drafts the carousel/video script from brief + retrieved skills | cheap/fast (drafts are disposable) |
| **Consumer** | worker | Renders (HTML/CSS→PNG for carousel; TTS+video for WR3) | deterministic / non-LLM where possible |
| **Coordinator** | orchestrator | Decomposes topic→brief→slides; routes; enforces caps | mid tier, **hard step ceiling** |
| **CRITIC** | advisory | Scores against the rubric (Part 5) + verifies citations vs. ground truth; returns *fixes*, does not gate | capable (the expensive judgment lives here) |
| **JUDGE** | binary gate | PASS/FAIL only, on the hard constraints (citation verified, loop closed, no banned claim) | capable, *separate context* from producer |

Critic = advisory (improves), Judge = binary (admits). Keeping them distinct prevents the critic's "make it better" from silently becoming "ship it."

### 3.3 Carousel (sync) vs. video (async-with-spend-gates) composition

- **Carousel = synchronous, cheap, fast.** Producer → Critic (fix loop, capped at e.g. 2 rounds) → Judge → render → human veto. Whole cycle is seconds-to-minutes; the UI can poll it on a short interval. No spend-gate needed because cost per artifact is trivial.
- **Video (WR3) = asynchronous, expensive, spend-gated.** Generation (TTS, image/video model calls) costs real money and minutes (a 50-min pipeline is plausible). Here you insert **explicit spend-gates**: the Judge (and optionally the human) must PASS the *script + storyboard* **before** any paid render call fires. You never spend on rendering a video the script would have failed. This is the maker-checker cut placed at the most expensive boundary.

### 3.4 Maker-checker cost asymmetry — where to place the cut

- **Established pattern:** weak-generator + strong-verifier is cost-effective; a weak generator paired with a fixed strong verifier approaches a strong generator's post-verification performance; cascades route most work to small models and escalate only on low confidence — cited industry savings in the **−40-60%** range.
- **The cut for Bali Zero:** **cheap model drafts (Producer), capable model critiques + judges (Critic/Judge).** Drafts are disposable so they should be cheap; the *judgment* (especially citation verification) is where capability must not be skimped. For video, additionally cut **before paid render** (3.3). This is the single largest cost lever after avoiding the unjustified debate-committee.

### 3.5 GROUNDING CONTRACT — the anti-hallucination spine (non-negotiable for a regulatory publisher)

The spine, stated as a contract:

1. **The generator is NEVER the source of truth.** The Producer may write "Permenkum 49/2025" only if it came from a grounded retrieval, never from the model's parametric memory.
2. **A ground-truth interpreter cites authoritative sources** (the agency's regulation corpus / a curated NotebookLM-style RAG over real regulation text), returning verbatim code + article + date with provenance.
3. **The Critic verifies every citation in the draft against that ground truth** — exact-string match on the code, date, and the claimed consequence — and the **Judge FAILS the artifact if any citation is unverifiable.** No "looks plausible." This is binary.

Why this is the spine and not a feature: for a regulatory publisher a hallucinated visa rule is a **liability, not a typo** (1.8 backfire). The grounding contract is the ONE place where the multi-station cost is unambiguously justified by a measured, high-severity failure mode — which is exactly the condition (3.1) under which multi-agent structure earns its cost. Everything else can be a single agent; *this* cannot.

### 3.6 Hard termination everywhere

- **Established failure mode (2026):** uncapped coordinators / retry loops are the **#1 runaway-cost failure**; a 2025 IDC survey found **92% of orgs running agentic AI saw costs above expectations, with runaway loops the named main cause.** Fixes that are now standard: an absolute max step ceiling enforced **in code, not model judgment**; `recursion_limit`; **no-progress detection** (hash each tool+args call, terminate on repeat within a window); retries capped (≈3); per-run hard **token/$ budget** with auto-terminate; circuit breakers on tool calls.
- **For Bali Zero:** every coordinator and critic-fix loop gets a hard round cap (e.g., critic ≤2 fix rounds then escalate to human, never infinite); every video run gets a hard $ ceiling that aborts before overspend; no-progress hash-detection on the fix loop so the producer↔critic ping-pong cannot oscillate forever.

### 3.7 Self-evolving skill library + Reflexion fed by REAL engagement (the loop that makes this "perfect")

- **Voyager (Wang et al. 2023):** skills stored as **executable code**, **indexed by the embedding of the skill's description**, retrieved by querying with the embedding of the current task; the library *grows* and skills *compose*. Skills are deterministically *run*, not re-reasoned each time — so a proven "specific-gap hook for a deadline regulation" becomes a callable, reliable function, not a fresh gamble.
- **Reflexion (Shinn et al. 2023):** agents convert a **feedback signal into verbal self-reflection stored in episodic memory** to improve on the next trial — "verbal reinforcement," a semantic gradient. The critical design choice is **what the feedback signal IS.**
- **Wiring the reward correctly (the lever):** the naive loop refines on "the draft passed the Critic" — that only learns to satisfy the Critic's *taste*. The correct loop refines on **real saves/forwards per reach** pulled back from Instagram Insights after publish. Concretely:
  1. Each published carousel is tagged with which skills produced it and its rubric profile.
  2. After N days, **sends-per-reach and saves-per-reach are fetched** and joined back to the producing skills.
  3. **Weekly Reflexion pass:** the system reflects on the gap between predicted forwardability (rubric) and *actual* sends, writing skill refinements into the library — promoting skills correlated with high real sends, demoting/retiring those that scored well on the rubric but **flopped on real forwards**.
  4. This **calibrates the rubric itself** (Part 5) against ground-truth engagement, so the "forwardability score" stops being an LLM's taste and becomes a *learned predictor of the real algorithmic currency*. This closes psychology → production → measurement → psychology. **It is the single biggest lever** because it is the only component that lets the system *discover* what its audience forwards rather than *assume* it. **Caveat (emerging):** attribution from skill→engagement is noisy (topic, timing, and audience confound); the loop must use enough volume and guard against over-fitting to a single viral outlier — append-on-real-signal-with-decay, not append-on-any-success.

### 3.8 The human gate reduced to its irreducible minimum

- **Two human touchpoints only:** (a) **topic spark** — the human (or an upstream intel agent surfacing a new regulation) decides *what is worth a carousel*; (b) **publish veto** — the human approves the finished, reviewable artifact before it goes live.
- **Everything between is autonomous; nothing auto-publishes.** The grounding contract + caps make the autonomy safe; the publish veto makes a hallucination-that-slipped recoverable. The human is not the safety layer (the grounding spine + judge are); the human is the *taste-and-liability* backstop on an already-verified artifact.

## Part 4 — Integration principle for a native control app

The decision-relevant insight: **latency class dictates UI affordance.**

- **Sync class (carousel queue):** cheap, fast (seconds-minutes), high-volume. The control surface can be a **short-poll action queue** with action buttons — approve, reject, re-render, edit-brief — because the operator's action and the system's response are tightly coupled in time. A 4-second poll is appropriate here.
- **Async class (video, spend-gated):** expensive, slow (tens of minutes), gated by real spend. Bolting this into the sync queue's 4-second-poll action UI is an **anti-pattern**: a 50-minute spend-gated pipeline polled every 4 seconds floods the UI with "still running," invites an impatient operator to mash a button that triggers a *paid* re-run, and hides the one moment that matters (the pre-render spend-gate). The right design is a **separate async surface**: read-mostly **monitor** with explicit **gate prompts** ("Script PASSED — approve $X render? [approve once]"), idempotent actions, and progress as a state machine (queued → script-judged → awaiting-spend-approval → rendering → done) — not a poll spinner.
- **Rule — right tool per latency class:** **expose action buttons where the action is cheap, fast, and reversible (sync carousel); be a read-only monitor with deliberate, idempotent spend-gates where the action is expensive, slow, and irreversible (async video).** One app, two surfaces, because the cost/latency physics differ. (This matches the existing project principle that a WR2 sync queue and a WR3 async spend-gated pipeline should not share one poll loop.)

## Part 5 — The critic-agent scorecard (psychology mechanized into the gate)

This is the rubric the **Critic** scores (advisory fixes) and the **Judge** enforces (hard gates ★). Derived directly from Part 1, calibrated by Part 3.7.

| # | Item | Pass criterion | Fail (backfire) | Maps to |
|---|---|---|---|---|
| 1 | **Tribe named** | Slide 1 names a specific addressable identity ("PT PMA owners", "Hak Pakai buyers") | Generic "everyone in Indonesia" | 1.5 |
| 2 | **Specific gap** | Slide 1 proves a real, specific consequence exists; concreteness in the sweet-spot (not vague, not exhaustive) | Vague clickbait ("shocking visa news") OR full answer dumped on slide 1 | 1.1 |
| 3 ★ | **Loop closed** | Loop opened on slide 1 is resolved by the payoff slide | Opened, never closed, or closed with "DM us" anticlimax | 1.3, 1.7 |
| 4 ★ | **Citation verified** | ≥1 verbatim code + article + date, **exact-match verified against ground truth** | Any citation unverifiable or paraphrased-as-fact | 1.8, 3.5 |
| 5 | **Save-utility complete** | A reference slide carries code + date + concrete action together | Date without code, code without action | 1.6 |
| 6 | **Generation beat** | At least one slide invites the reader to predict before reveal, at surmountable difficulty | No reader work, OR unanswerable quiz | 1.2, 1.4 |
| 7 | **Send-reason** | Last slide gives a flattering forward reason naming a recipient ("send to a founder who…") | Last slide is logo/CTA-to-buy only | 1.7 |
| 8 | **Fluency** | One idea per slide, glossed legal terms (first-use only), scannable | Legalese wall OR vapid-and-generic | 1.4 |
| 9 ★ | **No banned/over-claim** | No guarantee, no fearmongering, no fabricated urgency; deadline framing only on real deadlines | Manufactured scarcity (manipulation, not persuasion) | 1.7, ethics |
| 10 | **Bilingual discipline** | EN default + ID legal term verbatim + one first-use gloss | Translating the term away (loses authority) OR untranslated wall | 2.1, 1.8 |

★ = Judge hard gate (binary FAIL blocks publish). Non-starred = Critic advisory (fix-and-rescore, capped rounds). Items 2, 5, 7 are the ones the **Reflexion loop recalibrates** against real saves/forwards (3.7): their pass-thresholds are *learned*, not fixed by taste.

## Numerical analysis (cost/benefit of the structure)

- **Single capable agent draft:** baseline cost C.
- **Adding a debate committee on taste:** ~2x C for ~+2.1pp quality on a task already >90% — *not justified* (3.1).
- **Adding the grounding spine (interpreter+critic+judge) on citations:** also multiplies cost, BUT the failure it prevents (hallucinated law → client harm → moat destroyed) is high-severity and *measured* (any unverifiable citation is detectable) — *justified* (3.1, 3.5).
- **Maker-checker cut (cheap draft / capable judge):** industry-reported **−40-60%** vs. running the capable model end-to-end (3.4).
- **Net:** the economical optimum is **cheap producer + capable grounding spine + hard caps + spend-gate-before-render**, NOT a uniform expensive committee. Spend the money on *verification and on the irreversible render boundary*, not on *argument*.

## Disagreements / open questions

- **IG signal weights:** trade press (sends 3-5x likes; sends > saves) vs. absence of a primary Meta disclosure. Resolution: trust the *direction* (corroborated across ≥5 sources + Mosseri public statements), treat the *exact multipliers* as design priors to be validated by the system's own A/B + Reflexion loop, not as constants.
- **Multi-agent value:** Anthropic's +90.2% (breadth-first research) vs. 2026 critiques showing +2.1pp-or-negative on matched-compute debate. Resolution: both are right for different task shapes; carousel drafting ≠ breadth-first research, so the committee is replaced by a linear grounding spine justified by a *measured* failure mode (hallucinated law).
- **Zeigarnik replication:** contested in the lab; reliable as a practitioner heuristic. Flagged as emerging, not used as a load-bearing claim.
- **Open:** attribution noise in the engagement→skill reward (3.7). The reward wiring is the highest-value and highest-risk component; it needs volume thresholds and outlier guards before it is trusted to retire skills. Recommend a shadow period (loop *observes* and proposes, human confirms) before it acts autonomously.

## Checklist for action

- [ ] Instrument **sends-per-reach and saves-per-reach** capture from IG Insights per published carousel, tagged with producing skill IDs and rubric profile (prerequisite for the only lever that matters, 3.7).
- [ ] Encode the **Part 5 rubric** as the Critic's scoring function and wire the four ★ items as the Judge's binary publish gate (citation-verify is the non-negotiable one).
- [ ] Implement the **grounding contract** (3.5): Producer cannot emit a citation that did not come from grounded retrieval; Critic exact-match-verifies; Judge FAILs on any unverifiable citation.
- [ ] Add **hard termination** to every coordinator and the producer↔critic fix loop (max rounds + no-progress hash + per-run $ ceiling), and a **spend-gate before any paid video render** (3.3, 3.6).
- [ ] Place the **maker-checker cut**: cheap model for Producer, capable model for Critic/Judge; measure the realized cost delta against an all-capable baseline (target −40-60%, 3.4).
- [ ] Build the control app as **two surfaces**: sync action-queue (short poll + action buttons) for carousels; async read-mostly monitor with idempotent spend-gate prompts for video (Part 4).
- [ ] Stand up the **Voyager skill library** (skills as executable code, embedding-retrieved) and a **weekly Reflexion pass** keyed to real saves/forwards — run it in **shadow mode first** (proposes skill promote/retire, human confirms) until attribution noise is controlled (3.7 open question).
- [ ] Keep the **human gate to two touchpoints only**: topic spark + publish veto; verify nothing in the pipeline can auto-publish (3.8).

## Sources

1. Socialync, "Instagram Algorithm 2026: The Complete Guide" — https://www.socialync.io/blog/instagram-shares-algorithm-complete-guide-2026 (signal hierarchy; sends-per-reach thresholds; Mosseri paraphrase) (fetched 2026-06-25).
2. Later, "Instagram algorithm in 2026: rank signals" — https://later.com/blog/how-instagram-algorithm-works/ ; Buffer — https://buffer.com/resources/instagram-algorithms/ ; Hootsuite — https://blog.hootsuite.com/instagram-algorithm/ ; GOSO "the 4 signals that now matter" — https://goso.io/instagram-updates/instagram-algorithm-change-2026/ (corroborating sends > saves > likes direction; 3-5x band).
3. Anthropic, "How we built our multi-agent research system" — https://www.anthropic.com/engineering/built-multi-agent-research-system (90.2% vs single Opus-4; ~4x/~15x token cost; ~80% variance from token usage; orchestrator-worker; delegation/effort-scaling principles) (fetched 2026-06-25).
4. Iterathon, "Multi-Agent Orchestration Economics: When Single Agents Win 2026" — https://iterathon.tech/blog/multi-agent-orchestration-economics-single-vs-multi-2026 ; arXiv MAD analyses (+2.1pp@2x; >45% accuracy → negative returns; planning -39%/-70%; gains from aggregation not belief).
5. Loewenstein information-gap theory (via Psychology Fanatic / ScienceDirect curiosity review) — https://www.sciencedirect.com/science/article/pii/S0896627315007679 ; headline-concreteness backfire study — https://pmc.ncbi.nlm.nih.gov/articles/PMC11704130/ (8,977 A/B tests; curvilinear; vague <2.58 +5.5%, over-concrete >3.06 −9.9%; sweet-spot 2.58-3.06) (fetched 2026-06-25).
6. Slamecka & Graf (1978), "The Generation Effect: Delineation of a Phenomenon," JEP:HLM 4(6) — https://andymatuschak.org/prompts/Slamecka1978.pdf ; generation-effect meta-analysis — https://link.springer.com/article/10.3758/s13423-020-01762-3 .
7. Zeigarnik effect (incl. replication caveat) — https://en.wikipedia.org/wiki/Zeigarnik_effect ; open-loop application — https://blog.neuromarket.co/the-power-of-open-loops-using-the-zeigarnik-effect-to-create-irresistible-content .
8. Berger, *Contagious* / STEPPS (social currency, practical value) — https://knowledge.wharton.upenn.edu/article/contagious-jonah-berger-on-why-things-catch-on/ ; https://pageblock.io/resources/framework/stepps .
9. Kahneman & Tversky prospect theory / loss aversion — https://www.behavioraleconomics.com/resources/mini-encyclopedia-of-be/loss-aversion/ ; ELM source credibility — https://www.emerald.com/jebde/article/3/1/36/1226999/ .
10. Voyager (Wang et al. 2023) — https://arxiv.org/abs/2305.16291 (skill library as executable code, embedding-indexed/retrieved). Reflexion (Shinn et al. 2023) — https://arxiv.org/abs/2303.11366 (verbal RL; episodic reflection; 91% HumanEval pass@1).
11. Agentic production failure modes 2026 — https://datasciencedojo.com/blog/agentic-loops-explained-from-react-to-loop-engineering-2026-guide/ ; https://byteiota.com/ai-agent-cost-runaway-enterprise-budget-500m-bill/ ; https://machinelearningmastery.com/5-production-scaling-challenges-for-agentic-ai-in-2026/ (hard step ceiling in code; no-progress hashing; retry≤3; per-run $ cap; IDC 92% over-cost, runaway loops main cause).
12. LLM-as-judge / maker-checker cost asymmetry — https://orq.ai/blog/llm-juries-in-practice ; cascaded selective evaluation — https://arxiv.org/html/2410.13341v3 (weak-generator+fixed-verifier; cascades route to small models; −40-60% industry range).
