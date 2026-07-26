# WR2 — Adaptive Production, 3-Seat Deep Research + Adoption Roadmap

**Date:** 2026-07-20
**Mandate (Zero, verbatim intent):** "produzione che si adatta al momento/tema, coinvolgente, tutte le leve della comunicazione di qualità" — deep research across 3 external seats + an independent visual review of the last 3 rendered decks.
**Seats dispatched:**

- **Seat 1 — Kimi K3** (Moonshot, via `kimi` CLI, `-m kimi-code/k3`) — lens: how the world's most advanced automated/semi-automated editorial operations produce variety-without-chaos, timeliness, and engagement (mechanisms, not taste).
- **Seat 2 — Gemini 3.1 Pro High** (via `agy` CLI, Antigravity Research Agent) — lens: reuse-first OSS harvest — which already-built open-source projects cure WR2's diagnosed diseases, so nothing gets written from scratch that already exists.
- **Seat 3 — Codex GPT-5.6 sol, effort ultra** (via `codex exec`) — lens: read-only architecture review of the actual WR2 codebase at commit `fe116f0b`, from "prompt-driven output" to "editorial compiler."
- **Orchestrator + final gate — Fable 5** — ran the empirical DB diagnosis (§0), the independent visual review of the last 3 decks (§0b), and the cross-seat synthesis + adoption ruling (§4). Generator≠grader: none of the three research seats saw each other's output before Fable's synthesis, and none of them graded their own findings.

**Method note:** each seat received the _same_ verified diagnosis context (the 5 diagnosed WR2 diseases: single-example anchoring, frozen narrative arc, formulaic cover subheads, layout monoculture, no editorial memory) plus a distinct lens (world-class-mechanisms / OSS-harvest / architecture-review), and worked independently. This is deliberate: convergent findings from three seats with no shared context and different training/tooling are stronger evidence than one seat's self-consistent narrative (cf. cicatrix-scars.md family #6, W100 — same-family agreement can certify false-clean; cross-family convergence is the opposite failure mode and is treated here as real signal). The OSS harvest (Seat 2) was independently verified against live GitHub state on 2026-07-20 before inclusion (see the "Verifica" column in §2 and the summary in §5) — reuse-first discipline requires confirming a candidate dependency actually exists and is licensed as claimed before it enters an adoption roadmap.

---

## 0. Diagnosi empirica di partenza (Fable, DB 30gg)

Prima di dispacciare i 3 seat, l'orchestratore ha condotto un'analisi empirica sul database di produzione WR2 (ultimi 30 giorni, corpus di carousel pubblicati/renderizzati). I fatti che hanno motivato il mandato:

- **Kicker/cover-take frozen fino al 15/7:** 30 carousel su 30 usano la take-slide "Our read:" come formula fissa — zero varianti strutturali, solo il contenuto sotto la label cambia.
- **Rottura post-#2544, ma solo per 3/3:** dopo l'armamento del fix (PR #2544), gli ultimi 3 carousel osservati mostrano "THE SIGNAL" al posto di "Our read:" — la rottura è reale ma la sostituzione è ANCORA una formula fissa singola, non una rotazione. Il pattern "un solo esempio nel prompt diventa lo spec" (single-example anchoring) si è semplicemente spostato di una posizione.
- **Arco narrativo identico 33/33:** ogni carousel osservato nel corpus segue esattamente `cover → editorial take → body slide × N → CTA`, senza eccezioni, indipendentemente da dominio (tax/visa/property) o liveness (breaking/evergreen).
- **Subhead di copertina formulaici:** un pool di 3 esempi di cover-subhead viene riciclato quasi a rotazione fissa — stesso meccanismo di anchoring del kicker, stessa causa radice.
- **4 famiglie di layout su 9 mai superate:** il generator non emette mai i campi strutturati (liste tipizzate, stat, citazioni, turni di dialogo) di cui le altre 5 famiglie di layout avrebbero bisogno per essere selezionate dal renderer — non è un problema di scelta creativa, è un problema di accoppiamento di schema tra generator e renderer.
- **Il register/tone è l'UNICO asse che varia in produzione**, ed è anche l'unico asse con un lookback DB armato (la generazione consulta lo storico register/tone recente e lo evita). Questo è il fatto empirico più importante del dataset: **lo stato iniettato batte l'intento dichiarato, sempre.** Ogni istruzione "varia questo" nel prompt che NON è supportata da uno stato interrogabile viene sistematicamente ignorata dal modello; l'unica istruzione che funziona è quella backed da una query SQL sullo storico.

Questa diagnosi — non una richiesta generica di "più varietà" — è il context condiviso che tutti e 3 i seat hanno ricevuto prima di partire.

---

## 0b. Review visuale ultimi 3 deck (Fable, 2026-07-20)

Review visuale indipendente (non condivisa con i 3 seat prima del loro dispaccio) degli ultimi 3 deck WR2 renderizzati, condotta lo stesso giorno del mandato:

- **CTA Bali Zero ASSENTE su ogni deck:** lo skeleton statement-bomb renderizza solo la statement; la CTA richiesta dalla regola #8 del prompt viene droppata in silenzio (nessun handle/contatto su nessuna slide). Spiegata da Codex finding A: split-brain costituzionale tra il generator (che richiede l'ultima slide come CTA) e il contratto `statement-bomb` (che vieta esplicitamente la CTA e permette solo una statement breve) — vedi §3, Additional limitation A.
- **Liste renderizzate come paragrafi caps:** testo come "No eligible KBLI list. No minimum threshold…" o "FINE. DETENTION. DEPORTATION…" viene prodotto come prosa in maiuscolo invece che come lista/status strutturata — starvation delle famiglie di layout strutturate (status_list, fact_stack) coerente con la diagnosi §0 sulle 4/9 famiglie mai superate.
- **Numeri chiave sepolti nella prosa:** percentuali come 22%, 12%, 0,5% appaiono dentro paragrafi di corpo invece che nel layout `stat-card-hero`, mai usato in nessuno dei 3 deck.
- **Cliché fotografici intra-deck:** 2× "ufficio vuoto" nello stesso deck; 2× consecutive "figura solitaria nel varco" — sintomo dell'assenza di una art-direction card per-story (vedi Kimi M10 in §1).
- **Spazio morto verticale:** la timeline in bahasa è al 55% vuota; la closer slide è al 40% con nulla sotto — segnale di un layout compilato senza vincoli di densità/cardinalità sui campi tipizzati.
- **Istanza viva W89:** heading di circa 24px sotto una foto con body enorme (slide 4, deck influencers, id `2eafa7b8`) — gerarchia tipografica invertita, coerente con la cicatrice W89 già nota (typography lever gap).
- **Swipe affordance debole:** solo un puntino giallo indica la posizione nel carosello; nessun "2/8" testuale, nessun filo narrativo esplicito tra una slide e la successiva.
- **[Zero-gated, non azionabile senza decisione brand]** All-caps anche su body di 60 parole, in violazione della doctrine typography-guard del 2026-07-12; cover headline sempre spinta al fondo con un floor di 60px (cfr. #2750); palette identica su ogni slide del deck — `tonal_palette` esiste come meccanismo ma tocca solo le foto, mai il resto della composizione.

Questa review visuale conferma indipendentemente, su artefatti reali e non su codice statico, diversi finding che i 3 seat sotto raggiungono per vie separate (contratto tipizzato mancante, layout monoculture, assenza di art-direction per-storia, split-brain sul closer).

---

## 1. Seat Kimi K3 — report integrale

# How the Best in the World Do It — Communication/Content Automation Mechanisms for WR2

**Research report — prepared 2026-07-19**
**Subject:** WR2, Bali Zero's autonomous editorial organism (Indonesian regulatory/visa/tax intelligence → Instagram carousels)
**Lens:** mechanisms, not taste — the _systems_ that produce (1) variety without chaos, (2) timeliness/adaptation to the news moment, (3) engagement, in the world's most advanced automated/semi-automated editorial operations.

---

## 0. Framing: what WR2's diseases actually are

Before the landscape, it is worth naming what WR2's five diagnosed diseases have in common, because the world-class systems below are best read as answers to exactly these failure modes:

1. **Single-example anchoring** — the model treats every example in the prompt as a spec, not an illustration. This is not a prompting quirk; it is the defining difference between _example-driven generation_ (what WR2 does) and _constraint-driven generation_ (what every mature system below does).
2. **Frozen narrative arc** — one hardcoded arc (cover → take → body → CTA) copied verbatim 33/33 times. Mature systems never let a generative model choose structure freely; structure is a _selected artifact_ from a finite, curated library.
3. **Formulaic cover subheads** — 3 example kickers recycled. Same root cause as #1.
4. **Layout monoculture** — 4 of 9 layout families used, because the generator never emits the structured fields the other 5 need. This is a _schema coupling_ problem: the downstream renderer has a richer vocabulary than the upstream generator.
5. **No editorial memory** — every "vary it" instruction is unenforceable prose. The one axis with DB lookback injected (register/tone) is the one axis that varies. That is the single most important empirical fact in WR2's diagnostic data: **injected state beats stated intent, every time.**

The through-line of this report: the best systems in the world do not ask models to be creative and varied. They _make variety a property of the system_ — through format libraries, rotation state machines, constraint sampling, and feedback loops — and reduce the model's job to filling well-shaped slots with well-grounded content. Everything below is organized around that principle.

---

## 1. Landscape Map

### Tier (a) — News-industry automation

**Reuters — Lynx Insight + News Tracer ("the cybernetic newsroom").** Reuters' system, built from 2018 under Reg Chua, is the canonical "division of cognitive labor" architecture: machines do speed, breadth, and computation; humans do judgment, context, and questioning. News Tracer scans ~700M tweets/day, clusters candidate breaking stories, and scores their credibility (account history, network structure) before alerting journalists. Lynx Insight sifts Reuters' financial datasets for trends and anomalies, runs a detected pattern through a natural-language generator to produce sentences/drafts (up to two-thirds of an earnings story), and _delivers it to a journalist as a lead_ — via email, messenger, or terminal — rather than publishing it ([Digiday](https://digiday.com/media/uh-oh-reuters-robot-writer-can-churn-earnings-reports/), [Reuters Agency](https://www.reutersagency.com/en/media-center/how-ai-helps-power-trusted-news-at-reuters/), [newsrewired](https://www.newsrewired.com/2018/11/07/cybernetic-newsroom-why-reuters-is-marrying-human-and-robot-journalism/)). Mechanism of variety: the machine proposes _angles_, not articles — different anomalies surface different story shapes, so output variety is driven by data variety, not by asking a writer to "be different this time." Mechanism of timeliness: continuous anomaly detection with trigger thresholds, i.e., a _state machine over the world's data_ that fires the editorial process. Mechanism of engagement: not engagement in the social sense — the mechanism is _relevance density_ (only statistically significant deviations become stories).

**Bloomberg — Cyborg.** Cyborg ingests earnings releases and regulatory filings within seconds of publication, parses the numbers, compares them against analyst expectations, and fills predefined story templates to produce a formatted draft almost instantly; by 2019 roughly one-third of Bloomberg's news volume touched the system ([Klover.ai](https://www.klover.ai/ai-in-journalism-2025-whats-changing-in-newsrooms-and-coverage/), [Stork.ai](https://www.stork.ai/en/bloomberg-cyborg)). The mechanism that matters for WR2: **template-slot generation over a canonical data schema**. Cyborg does not "write about earnings"; it maps a normalized earnings object (revenue, EPS, surprise-vs-consensus, guidance delta) into a small set of story grammars chosen by the _shape of the data_ (beat vs. miss vs. in-line produce different narrative frames). Variety without chaos comes from the combinatorics of data-shapes × templates; timeliness comes from event-driven ingestion; accuracy comes from the fact that the numbers are never generated, only transposed.

**Associated Press + Automated Insights (Wordsmith).** The original at-scale robot-journalism deployment: 3,700+ automated earnings stories per quarter versus ~300 manually before, a 12× coverage expansion with error rates _lower_ than human-written equivalents ([ReplacedByAI](https://www.replacedbai.com/blog/will-ai-replace-journalists)). Wordsmith's architecture is the purest expression of the template-grammar approach: human editors author _branching narrative templates_ ("if EPS beats consensus by >5%, use frame A; if revenue guides down, append paragraph type B"), and the NLG engine renders data through them. Key mechanism: **the editorial judgment is encoded once, in the grammar, by an editor — then executed deterministically, forever.** Variety is authored upfront as branches; consistency is guaranteed by the engine. AP editors oversee the system; they do not write the articles.

**Washington Post — Heliograf.** The Post's in-house NLG system (2016 Rio Olympics, then US elections, high-school sports) generated 850+ stories in its first year. Technically: data pipelines normalize incoming feeds into a canonical schema; records route to an NLG engine of templates with variable slots and connector phrases; a probabilistic model trained on Post copy selects phrasing, and a small neural LM introduces sentence variation specifically to _avoid repetitive phrasing_; a CI pipeline runs templating unit tests and end-to-end quality checks against historical data ([bright-amber case study](https://www.bright-amber.com/case-studies/ai-driven-content-generation-for-marketing), [Spreadbot](https://spreadbot.ai/blog/streamlining-editorial-workflows-the-role-of-content-automation-tools-in-modern-content-strategy/)). Note the explicit anti-repetition component — even a 2016 template system treated "sounds the same every time" as a bug worth an engineered fix. In shadow mode at Rio, editors approved 98% of 300 stories unchanged. Heliograf also pioneered **audience-state variation**: the same election data rendered as a national story, a state story, and a geo-targeted alert — one event, many presentations, chosen by reader context.

**Axios — Smart Brevity as a format system.** Smart Brevity is not a style; it is a _grammar_: a labeled-slot structure (headline ≤ 6 words; "Why it matters:"; "The big picture:"; "Between the lines:"; "The bottom line:") with hard length budgets, strategic bolding, and bullets — a format so formalized that Axios HQ sells software that mechanically enforces it ([Axios HQ checklist](https://www.axioshq.com/research/smart-brevity-communication-checklist), [Bernoff](https://bernoff.com/blog/how-much-is-brevity-worth-if-youre-axios-525-million)). The mechanism lesson is profound and slightly uncomfortable for WR2: **Axios achieves recognizability and engagement through deliberate slot-label repetition.** Readers _want_ "Why it matters" every time. The variety lives in content; the skeleton is a franchise. This complicates WR2's "everything must vary" instinct — the correct target is _variety at the right layers_ (arc, layout, hook, angle) and _deliberate invariance at others_ (a small set of recurring labeled segments that become brand signatures). Axios also demonstrates the labeled-slot rendering pipeline: because every item carries typed slots, it can be re-rendered as newsletter, tweet, or push alert without rewriting.

**BBC News Labs — object-based / atomized media.** BBC R&D's long-running "atomized news" work decomposes stories into semantically tagged objects (explainer, quote, timeline card, fact box, map) stored independently of any article, then _recomposes_ them per format and per audience state — the same event renders as a 40-second summary for a commuter and a deep timeline for a weekend reader [UNVERIFIED in current form — the atomized-news/object-based-media work is well documented historically through BBC R&D and News Labs demos, but its 2024-26 production status is unclear]. Mechanism: **content objects, not articles, as the unit of storage** — variety becomes a rendering decision, not a writing decision.

**Schibsted / Aftonbladet — United Robots + AI hub.** Aftonbladet's Sportbladet uses United Robots' sports robot to auto-generate match reports for _every_ Premier League match the second it ends, extending coverage beyond what reporters could ever staff ([United Robots](https://www.unitedrobots.ai/resources/blog/aftonbladet-use-robot-texts-to-expand-premier-league-coverage)). Schibsted's 2023 AI hub put a cross-functional team (news, sport, podcast, tech) on applied AI full-time ([Schibsted](https://schibsted.com/news/aftonbladet-creates-ai-hub/)), and in 2025 Aftonbladet and VG launched verified AI chat news services in 50 languages ([Schibsted](https://schibsted.com/news/aftonbladet-and-vg-team-up-on-unique-ai-news-services/)). Two mechanisms worth lifting: (1) **robot bylines with explicit provenance labeling** — automated content is labeled as such, which preserves trust while scaling; (2) **the event→article latency race** — being first on structured events is itself the engagement mechanism in sports/breaking; WR2's analog is being the first Bali consultancy to explain a new regulation.

**LLM-era newsroom pipelines (2024–2026).** The industry pattern has consolidated into a standard shape: retrieval-grounded drafting → verification pass → human gate → multi-format rendering. Reuters appointed its first dedicated newsroom AI editor in 2025 and discloses AI involvement per-article ([Tomorrow's Publisher](https://tomorrowspublisher.today/new-formats/reuters-appoints-first-newsroom-ai-editor/)); Bloomberg built BloombergGPT for finance-domain tasks; Ringier Axel Springer, Le Figaro, and others run "generate 3 headline variants → test → promote winner" loops on homepages [UNVERIFIED for specific publishers; the pattern of automated headline A/B on homepages is well established via Chartbeat/Taboola-style tooling]. The distinctive 2024+ addition over the 2016-era systems: **the critic pass** — a second model verifies claims against sources before anything reaches the human gate (WR2 already has this with its fact extractor/checker — it is ahead of many newsrooms here).

### Tier (b) — Social-first editorial machines

**Morning Brew — franchise section architecture + voice system.** The Brew's product is a _fixed container with rotating content_: recurring labeled sections (Markets, Tech, a rotating deep-dive, games/trivia) inside one email, written in one tightly-specified conversational register. The mechanism stack: (1) **franchise slots** give readers ritual and give writers constraints; (2) a **voice bible** so specific (jokes-per-paragraph density, banned words, analogy style) that any writer can produce on-brand copy — the analog of WR2's brand cortex skill; (3) **relentless subject-line and section-order testing** with the referral-loop data flywheel telling them what to expand (Career Brew, Money Scoop etc. were launched _because_ audience behavior signaled demand) ([intro.co](https://intro.co/blog/how-to-approach-content-marketing-in-2025), [gauravmohindra.wordpress.com](https://gauravmohindra.wordpress.com/)). Variety mechanism: rotation within fixed slots — readers know the shape, never the content. This is the healthiest model for WR2: the carousel _format_ should be instantly recognizable as Bali Zero; the arc, angle, and visual treatment inside it should rotate.

**The Hustle — angle-first story system.** The Hustle's signature was not its topics (the same business news as everyone) but its _angles_: each story was assigned a distinct lens — the "what happened / why it matters / the number / the quote" skeleton filled with an opinionated, personality-forward take. Mechanism: **the angle is an explicit editorial artifact chosen before writing**, often the most junior-readable part of the pitch meeting. WR2's analog: the editorial-take slide should not be a structurally fixed slot with a rotating title; the _angle itself_ (contrarian, consequence-map, winner/loser, historical rhyme) should be a first-class field chosen by the planner with memory of recent angles.

**Duolingo social — character IP + trend-hijack state machine.** Zaria Parvez's team grew TikTok from ~50K to 16-17M followers with a documented operating system: (1) a **character with a fixed personality** (Duo: passive-aggressive, obsessed, sassy) that makes every output on-brand regardless of content; (2) an **80/20 test-and-learn cadence** — most posts ride trending audio/formats within hours of the trend peaking, a minority are original bets; (3) **calculated-risk tiers** — the team explicitly classifies ideas by brand risk and matches approval depth to risk tier ("Keep it Simple Stupid" risk framework); (4) long-arc **narrative stunts** (the Dua Lipa slow-burn, the February 2025 "Death of Duo" campaign, executed concept-to-launch in days) that convert accumulated character equity into culture-dominating moments ([Cannes Lions](https://www.canneslions.com/festival/speakers/zaria-parvez-s1-95727), [eCommerce Expo](https://www.ecommerceexpo.co.uk/news/zaria-parvez-senior-global-social-media-manager-duolingo-creativity-community-social-media-strategy), [barbarosozturk.com](https://barbarosozturk.com/blog/the-unhinged-corporate-social-media-playbook-zaria-parvez-the-mastermind/)). Mechanisms for WR2: variety comes from _trend surface area_ (the world's trends rotate, so content rotates); timeliness is a latency target on trend adoption; engagement comes from character consistency. WR2 has no character, but its equivalent is a _consistent editorial persona_ — the house voice as a recognizable "who," not just a "how."

**NYT Instagram team — art-direction-per-story within format series.** The NYT IG operation works like a magazine art desk attached to a wire service: recurring visual series (quote cards, annotated documents, photo-essay carousels, "how we reported it" process posts) provide the _format library_, while each story gets a bespoke **art direction decision** — a designer/editor pair picks the metaphor, palette treatment, and slide-by-slide visual progression for that story specifically [UNVERIFIED in its current internal process details; the format-series pattern is directly observable on the account]. The mechanism: **two-tier creativity** — the system tier (series formats, grids, type rules) is invariant; the story tier (concept, metaphor, pacing) is generated fresh per item. Variety is produced by the story tier; coherence by the system tier. WR2's renderer already has the system tier (9 layout families, brand tokens); what's missing is the per-story art-direction _decision object_ that chooses among them deliberately.

**Bloomberg Quicktake / NowThis-class vertical news — templated motion grammars.** Quicktake's short-form video runs on a motion-graphics grammar: kinetic type for numbers, lower-third citation cards, map-zoom transitions — a finite transition/component library assembled per story [UNVERIFIED specifics]. The transferable mechanism is **component-level templating**: not whole-slide templates but _per-element_ rules (every statistic gets a stat-card treatment; every quote gets a citation treatment), so any story automatically gets correct emphasis hierarchy. WR2's unused layout families (stat-card-hero, source-citation, evidence-carved) are exactly this — they exist but are never triggered because triggering is content-type-driven, and nothing classifies content type.

**The Hustle/Morning Brew shared meta-mechanism — the content matrix.** Both organizations effectively run a two-axis content matrix: _topic verticals_ (markets, tech, crypto…) × _formats_ (news brief, deep dive, explainer, profile, quiz). The matrix guarantees balanced coverage (no vertical dominates), forces format variety (each vertical cycles formats), and creates natural scheduling (each cell has a cadence). This is the simplest possible variety-without-chaos machine and WR2 has neither axis systematized.

### Tier (c) — AI-native pipelines (2024–2026)

**Multi-agent editorial systems (planner/researcher/writer/critic).** The dominant 2024-26 architecture for serious automated content (AutoGen/CrewAI-style orchestration, and its in-house equivalents at content studios) decomposes "write the thing" into specialized roles: a **planner** that selects angle/structure from the brief, a **researcher** that grounds claims in retrieved sources, a **writer** that fills the planned structure, and a **critic/editor** that scores the draft against a rubric and can send it back. The mechanism insight versus WR2's single mega-prompt: **separating the structural decision from the verbal decision is what makes the structural decision controllable.** In one prompt, structure and prose entangle and the model defaults to its strongest prior (WR2's frozen arc). As separate calls, the planner can be _constrained by state_ (recent arcs, recent layouts) while the writer is _freed to be vivid_ within its slot. WR2's single-prompt draft generator is the architectural root of at least three of its five diseases.

**Structure grammars / JSON-schema-first generation.** The 2024+ replacement for prompt examples: instead of showing the model a sample JSON (which it anchors on), you give it a _schema_ (typed slots, enums, length bounds) plus _constraints_ (forbidden recent values, required slot coverage) and let structured-output enforcement do the rest. OpenAI/Anthropic structured outputs, Pydantic validation with retry loops, and grammar-constrained decoding are now standard. This directly cures single-example anchoring: **you cannot anchor on an example you were never shown.**

**Style rotation systems.** Mature AI content operations (newsletter farms, social agencies running LLM pipelines) maintain explicit **style registries** — named, versioned style objects (register, sentence rhythm, rhetorical devices allowed, emoji/typography rules) — and rotate them under control: either round-robin with cooldowns (a style can't recur within N posts) or weighted sampling with recency penalties. The critical property: the rotation is _decided in code_, and the prompt receives exactly one style object, fully specified — never a menu to choose from. WR2's register/tone lookback is a primitive version of this and its success proves the pattern.

**Engagement feedback loops / bandit allocation.** The state of the art in 2024-26 social automation is a **contextual bandit over creative decisions**: each post logs its creative decision vector (format, hook type, arc, layout family, CTA type); engagement metrics arrive delayed (24-72h); a lightweight bandit (epsilon-greedy or Thompson sampling) updates the sampling weights for the next decision. Exploration is bounded (only brand-safe arms), exploitation is automatic (winning combinations get sampled more). This is the mechanism that replaces the human growth-hacker's intuition at scale — and it is strictly better than WR2's current "weekly analyst proposes brand amendments" because it closes the loop _into the generator's sampling distribution_ rather than into prose guidelines the generator will ignore.

**Headline/hook A/B infrastructure (Chartbeat/Upworthy lineage).** Upworthy's famous "write 25 headlines" discipline industrialized into Chartbeat-style real-time headline testing: N variants are shown to small audience fractions, the winner gets promoted, and — crucially — the _winning features are catalogued_ (length, question-vs-statement, number inclusion, emotional valence), building a hook taxonomy from evidence. For an Instagram carousel pipeline the direct analog is: generate 2-3 covers per carousel, let the human reviewer pick (zero extra workflow cost — they already review), log which cover archetype won and how it performed, and let that inform the hook taxonomy weights.

---

## 2. THE MECHANISMS — 12 concrete adoptions for WR2

Each mechanism: **name · who uses it · how it works technically · WR2 implementation (flow position, state, reads/writes) · expected effect · risk.**

---

### M1 — Structured Format Objects (schema-first generation)

**Who uses it:** Heliograf, Wordsmith/AP, Bloomberg Cyborg, Axios Smart Brevity; universally, every mature NLG system.

**How it works technically:** The unit of generation is a _typed object with named slots_, not prose. A story type declares its schema (slots, types, cardinality, length bounds); generation fills slots; rendering maps slots to layout. The model is never asked to invent structure — structure is a closed set, content is open. In the LLM era this is enforced with JSON-schema-constrained decoding and Pydantic validation with automatic retry on violation.

**WR2 implementation:**

- **Where:** `wr2_draft_generator.py`, as the core rewrite of step 3. Split today's single prompt into a typed pipeline.
- **State needed:** a new `format_registry` table — one row per carousel _format_ (e.g. `breaking_alert`, `explainer_deepdive`, `myth_vs_fact`, `qa_dialogue`, `stat_story`, `timeline_story`, `compare_change` old-vs-new rule, `checklist_action`), each with a JSON schema: required slide roles, slide-count range, which layout families it maps to, which structured fields it requires (stat value, citation URL, question/answer pair…).
- **Reads/writes:** the generator first _receives_ a format object (chosen by M2/M3 machinery, not by the model), loads its schema, and generates only the slot content. Writes a `draft_slots` row conforming to the schema; validation failure → targeted retry of the failing slot, not the whole carousel.
- **Renderer coupling:** `wr2_html_renderer/composer.py` already routes on fields; now every format's schema _guarantees_ the fields its layout families need — closing the gap that causes layout monoculture.

**Expected effect:** Kills frozen arc (structure is chosen, not defaulted), kills layout monoculture (schemas force the fields the rich layouts need), converts prompt-anchoring risk into schema compliance. This is the single highest-leverage structural change.

**Risk:** Over-rigid formats could make carousels feel templated in the bad sense — mitigated by having 8-12 formats (combinatorial headroom) and by letting slot _content_ be fully free. Also: schema design is real editorial work; a bad format library just moves the monoculture up one level.

---

### M2 — The Creative Ledger (editorial memory as queryable state)

**Who uses it:** Effectively all rotation systems tier (c); editorially, every magazine "recently covered" check; WR2's own register/tone lookback is the existence proof.

**How it works technically:** Every creative decision made for every published artifact is logged as structured data. Before generating artifact N+1, the system queries the ledger for the last K artifacts and derives _exclusion sets_ and _cooldown states_ per axis. "Vary it" stops being prose and becomes a SQL query.

**WR2 implementation:**

- **Where:** new module, e.g. `wr2_creative_ledger.py`, called at the top of step 3 (draft generation) and consulted by the planner (M4).
- **State needed:** table `creative_ledger(draft_id, published_at, format_id, arc_id, hook_type, kicker_text, cover_subhead_pattern, layout_families[], register, angle_type, cta_type, theme)`. One row per draft, written at generation time, backfilled for the existing 34 carousels by a one-off classifier pass over the archive (cheap: one LLM call per historical carousel to extract its decision vector).
- **Reads:** planner queries last N=10-14 rows; computes per-axis cooldowns (e.g. hook_type not in last 4, arc not in last 3, layout family not in last 5 unless forced by format, kicker first-two-words not equal to any in last 10).
- **Writes:** every generated draft appends its full decision vector. This also becomes the training data for M11's bandit.

**Expected effect:** Directly cures diseases 1, 2, 3 and the unenforceability of "vary it." The register/tone axis proves the effect size: it is the _only_ axis that varies today. Extending the same mechanism to 8 axes multiplies the combinatorial space: with 8 formats × 5 arcs × 6 hook types × 9 layouts, even conservative cooldowns make literal repetition nearly impossible for months.

**Risk:** Cooldowns that are too aggressive can starve the system (all arms cooling down → forced suboptimal picks). Keep cooldown windows short (3-5 items) and always leave a fallback. Backfill misclassification is a minor risk — spot-check the classifier output.

---

### M3 — Constraint Sampling (delete the examples from the prompt)

**Who uses it:** schema-first generation practice tier (c); grammar-constrained decoding; implicit in every template-NLG system since Wordsmith.

**How it works technically:** Single-example anchoring happens because examples in context function as _the highest-weight prior_. The fix is not better examples — it is removing examples entirely and replacing them with (a) a schema, (b) one fully-specified assignment per open variable (the sampled constraints), and (c) negative constraints (forbidden values from the ledger). The model's job shifts from "imitate the example" to "satisfy the assignment" — a much less anchorable task. Where a format demonstration is unavoidable, use _counter_-examples ("do NOT produce these recent kickers: …") which bias away from repetition rather than toward a template.

**WR2 implementation:**

- **Where:** `wr2_draft_generator.py` prompt construction, immediately.
- **Mechanics:** strip all worked examples from the generation prompt (the JSON example, the 7 example kickers, the 3 cover subheads — all of them). Replace with: the format schema (M1), the sampled decision vector from the planner (M4) stated as directives ("Hook type: CONSEQUENCE. Kicker register: terse imperative. Do not use 'Our read', 'THE SIGNAL', or any kicker beginning with 'The'."), and the ledger's forbidden list (M2).
- **Validation:** after generation, run a deterministic checker (not an LLM): kicker ∉ forbidden list, hook*type == assigned, arc == assigned, slide-role sequence matches schema. Any violation → regenerate with the violation named. This makes constraints \_enforced*, not _requested_.

**Expected effect:** Ends the "THE SIGNAL 3/3 times" class of failure at its root. Cheap to implement (mostly deletion + a checker), immediate effect.

**Risk:** Without any examples, early outputs may be blander or off-voice until the constraint vocabulary is well-tuned; mitigate by keeping the brand voice bible (which is _rules_, not examples) fully in context. Also, over-specified prompts can produce stilted copy — sample constraints per-run, don't stack all of them every time.

---

### M4 — Two-Stage Generation: Planner → Slot-Writer (the Lynx split)

**Who uses it:** Reuters Lynx Insight (machine finds the angle, human writes); every multi-agent pipeline tier (c); NYT IG's art-direction decision tier.

**How it works technically:** One model call (or a small deterministic-LLM hybrid) makes the _structural decisions_ — format, arc, angle, hook type, slide-role sequence, art direction — constrained by ledger state and by the news item's properties. Separate call(s) then _fill the slots_ with maximum verbal quality, receiving only their slot's assignment. Structural decisions are auditable, loggable, and constrainable; verbal decisions are free.

**WR2 implementation:**

- **Where:** step 3 becomes two phases inside `wr2_draft_generator.py` (or a new `wr2_planner.py` before it).
- **Planner inputs:** the grounded brief; the item's liveness tier (breaking/developing/evergreen), theme (tax/visa/property), and entity set; the ledger exclusion sets (M2); the format registry (M1). **Planner output (JSON, small):** `decision_vector = {format_id, arc_id, hook_type, angle_type, kicker_directive, slide_roles[], layout_family_per_slide, art_direction{mood, palette_emphasis, hero_image_concept}}`.
- **Planner mechanism:** hybrid — deterministic sampling where possible (format/arc/hook chosen by weighted sample with cooldown masks — _code_, not model), LLM only where judgment is needed (angle*type selection given the story, art-direction concept, kicker directive phrasing). This is important: the axes that must vary should be decided by \_randomized code with memory*, because code is the only component that can actually guarantee non-repetition.
- **Writer inputs:** brief + decision vector + only the slots it owns. Per-slide calls can be parallelized.
- **Writes:** decision vector → `creative_ledger`; slot content → `draft_slots`.

**Expected effect:** The frozen arc cannot survive — arc selection is explicit and memory-constrained. Angle variety (currently nonexistent: every take is "Our read") becomes a first-class rotating dimension. Also improves fact discipline: the writer no longer decides what the story _is_, only how to say its assigned part.

**Risk:** Two+ LLM calls cost more latency/money than one (minor at WR2's scale: one carousel/day). Planner bugs can produce incoherent format↔content pairings (e.g. qa_dialogue format for a story with no natural two voices) — mitigate with a format-eligibility filter keyed on brief features (has numbers → stat_story eligible; has a policy change with before/after → compare_change eligible).

---

### M5 — The Arc Grammar (narrative structures as a combinatorial library)

**Who uses it:** Wordsmith branching grammars; Heliograf's template selection; every story-formatting system tier (b) — Morning Brew's section sequences are arc grammars for email.

**How it works technically:** Define a carousel arc as a _sequence of slide roles_ drawn from a role vocabulary: `HOOK, CONTEXT, MECHANISM(how it works), EVIDENCE(stat stack), STAKEHOLDER_MAP(who wins/loses), TIMELINE, MYTH_CORRECTION, EXPERT_TAKE, ACTION(checklist), CTA, SOURCE`. Each arc is a grammar production, e.g.:

- `news_alert := HOOK → CONTEXT → MECHANISM → ACTION → CTA`
- `consequence_map := HOOK → STAKEHOLDER_MAP → EVIDENCE → EXPERT_TAKE → CTA`
- `myth_buster := HOOK(myth) → MYTH_CORRECTION → EVIDENCE → CONTEXT → CTA`
- `deadline_story := HOOK → TIMELINE → ACTION → SOURCE → CTA`

Slide-role → layout-family mapping is many-to-one with alternates (EVIDENCE can render as evidence-carved _or_ stat-card-hero), so visual variety survives structural reuse.

**WR2 implementation:**

- **Where:** new `arc_grammar.py` (a data file, not much code), consumed by the M4 planner and validated by M3's checker.
- **State:** arc library table; ledger tracks `arc_id` per draft; cooldown mask on arcs.
- **Reads/writes:** planner samples arc (weighted, cooldown-masked, liveness-filtered — see M6); checker validates the generated slide sequence against the grammar production; renderer maps roles → layout families with its own rotation memory.

**Expected effect:** Ends 33/33 identical arcs while keeping every carousel _legible_ — grammar-bounded variety is exactly "variety without chaos." Also makes slide count adaptive (breaking alerts run 5-6 slides, deep dives 9) instead of the fixed 7-9 habit.

**Risk:** Grammar authoring is editorial work — a thin grammar (3 arcs) recreates the problem. Launch with 6-8 arcs and add one per month from metrics. Also, not every story fits every arc: the eligibility filter (M4 risk note) is essential.

---

### M6 — Liveness-Driven Mode Switching (the News Tracer trigger)

**Who uses it:** Reuters News Tracer (credibility-scored breaking triggers); Bloomberg/Cyborg (event-driven publication); Aftonbladet's instant match reports; every breaking-news push system.

**How it works technically:** The pipeline's _mode_ is a function of the news item's state, not a constant. Breaking items take a fast path: stripped format (fewer slides), breaking-specific visual language (dark/status aesthetics signal urgency), tighter fact-check scope, expedited human review. Evergreen items take a craft path: richer formats (explainer, myth-buster, qa-dialogue), more image generation, full designer-loop. Developing items get an update frame ("what changed since X") that explicitly references prior coverage.

**WR2 implementation:**

- **Where:** step 2 (topic selector) tags liveness; M4 planner branches on it. Already 80% present — liveness tiers exist in the scoring step but currently influence nothing downstream.
- **State/mapping:** `liveness=breaking` → formats {news_alert, stat_story}, arcs {news_alert, deadline_story}, layouts biased to {dark-status-list, statement-bomb, source-citation}, slide count 5-6, register: urgent-terse. `liveness=evergreen` → formats {myth_vs_fact, qa_dialogue, checklist_action}, layouts biased to {qa-dialogue, evidence-carved, editorial-text}, full image generation. `developing` → update arc with an explicit "what's new" slide that diffs against the previous carousel on the same story (requires a `story_cluster_id` linking items to earlier drafts — a small addition to the scraper/enricher).
- **Writes:** mode and liveness recorded in the ledger; `story_cluster_id` enables _series_ ("Part 2") treatments.

**Expected effect:** Directly answers the goal "adapts to the moment." Visually, the feed starts to _look_ like a news operation — urgent items look urgent — which is itself an engagement signal. Also unlocks the unused dramatic layout families by giving them a trigger condition.

**Risk:** Liveness misclassification sends evergreen content down the fast path (thin treatment for a story that deserved depth). Keep the tier classifier conservative and let the planner override with a logged reason.

---

### M7 — The Hook Taxonomy with Enforced Rotation

**Who uses it:** Upworthy's 25-headlines discipline → Chartbeat-style testing; Morning Brew subject lines; every creator-economy hook framework (contrarian, number-led, question, negative-warning, insider-secret).

**How it works technically:** Hooks are classified into a finite taxonomy of _types_, each type having a structural recipe (not fixed words). E.g. for WR2's domain:

- `CONSEQUENCE` — "What changes for you on August 1" (stakes-first)
- `NUMBER_LED` — "4 platforms now withhold 0.5%" (stat-first)
- `DEADLINE` — "21 days before…" (clock-first)
- `MYTH` — "No, this is not a visa ban" (correction-first)
- `INSIDER` — "The clause everyone missed" (access-first)
- `QUESTION` — "Still on a B211A?" (self-identification-first)

Rotation is enforced by ledger cooldown (M2); within a type, the recipe is filled fresh by the writer (M4) — so "NUMBER*LED" never produces the same sentence twice, but the \_cognitive move* stays proven.

**WR2 implementation:**

- **Where:** `hook_taxonomy.py` data file + planner assignment + writer recipe + checker validation.
- **State:** taxonomy table (type, recipe, eligibility constraints — e.g. NUMBER_LED requires a usable stat in the brief; DEADLINE requires a date); ledger `hook_type` column.
- **Reads/writes:** planner samples hook_type from eligible set with cooldown; writer receives type + recipe + the brief's facts; checker verifies the emitted hook matches the recipe's structural test (starts with number? contains a date? is a question?) — a regex-level check, not an LLM call.

**Expected effect:** Cures the kicker/cover-subhead diseases (diseases 1 and 3) durably, and does so in the engagement-critical position: the cover is the entire CTR on Instagram.

**Risk:** Recipe checks that are too literal reject good hooks; keep the structural tests loose (one or two features per type) and treat the checker as advisory on borderline cases (log, don't block, after two consecutive failures). Also, hook-type performance will differ — feed results to M11 rather than hand-tuning.

---

### M8 — Deliberate Invariance: Franchise Segments (the Axios counter-move)

**Who uses it:** Axios ("Why it matters" every time), Morning Brew (same sections daily), NYT (recurring series), Duolingo (same character, always).

**How it works technically:** Counter to WR2's current instinct, the mechanism here is _strategic non-variation_. Choose 1-2 slots that are ALWAYS present, with a fixed label and fixed visual treatment, and make them the brand's signature. Variety rotates around these fixed points; the fixed points carry recognizability. The engagement research behind Axios/Morning Brew is that ritual drives habitual opens; total novelty reads as noise, not freshness.

**WR2 implementation:**

- **Where:** format registry (M1) — mark certain slide roles as franchise slots.
- **Candidate franchises for Bali Zero:** a closing "What we'd do" slide (actionable, consultancy-native, always present, always the same labeled treatment — replacing today's generic CTA); and/or a recurring one-line verdict segment ("The Bali Zero read" — note: this _absorbs_ the currently-pathological "Our read" kicker by giving it one sanctified, well-designed home instead of letting it sprawl across covers).
- **Mechanics:** franchise slots are excluded from rotation/cooldown machinery; everything else rotates. The renderer gives franchise slides one canonical layout each (brand-consistent, periodically refreshed quarterly, not per-post).

**Expected effect:** Builds the ritual/recognizability layer WR2 currently lacks (nothing recurs by design, so nothing is memorable), while _concentrating_ sameness where it does brand work instead of letting it leak everywhere.

**Risk:** Choosing the wrong franchise (a segment readers skip) institutionalizes dead weight. Start with one franchise slot, watch saves/shares per post (M11), and be willing to swap it after ~8-10 posts.

---

### M9 — The Near-Duplicate Detector (editorial diversity as a CI gate)

**Who uses it:** Heliograf's CI quality checks against historical data; the neural sentence-variation component in Heliograf specifically built to avoid repetitive phrasing; modern pipelines' critic passes.

**How it works technically:** Before a draft advances to rendering, an automated gate compares it against the last K published carousels across similarity axes: kicker text (exact + fuzzy), first-sentence structure, arc id, layout sequence, headline n-gram overlap. Threshold breach → the draft is sent back with the collision named ("cover headline shares 4-gram 'what you need to know' with drafts #28, #31"). This converts "we noticed 30 identical take-slides after a month" into "draft #4 was blocked on day 4."

**WR2 implementation:**

- **Where:** between step 5 (fact check) and step 6 (render) — or earlier, right after generation, to save render cost on rejected drafts.
- **Mechanics:** mostly deterministic: normalize text, compute Jaccard similarity on 3-grams for headline/subhead/kicker against the last 14 drafts (threshold ~0.5), exact-match checks on kicker and CTA phrasing, arc/layout collision checks from the ledger. One optional LLM call for semantic similarity on the take-slide thesis ("is this the same opinion as a recent one?") — cheap, one call.
- **Writes:** rejection events logged with the axis that tripped; the retry loop feeds the collision description into the regeneration constraints.

**Expected effect:** A hard floor under sameness — the diseases become _impossible to ship_ rather than possible-to-notice. Also generates the cleanest possible regression signal for tuning the cooldown windows in M2.

**Risk:** Over-sensitive thresholds create rejection loops (draft keeps bouncing). Start with loose thresholds, log-only mode for two weeks, then enforce. Keep the human review app able to override with a reason (which itself becomes training data).

---

### M10 — Art Direction Cards (per-story visual concepting)

**Who uses it:** NYT IG's designer/editor pairing per story; magazine art desks; Duolingo's stunt concepts; Bloomberg Quicktake's per-story visual treatment within a motion grammar.

**How it works technically:** Each story gets an explicit, small **art direction object** decided before rendering: `{mood, palette_emphasis, hero_concept (the visual metaphor), image_style, texture/photo-vs-illustration decision}`. The object is sampled from a constrained space (brand tokens bound the palette; the ledger prevents repeating the same hero*concept class back-to-back) and is \_informed by the story's emotional register* (a tax crackdown and an investor-incentive story should not look alike). The renderer consumes the card deterministically; the image generator consumes hero_concept as its prompt seed.

**WR2 implementation:**

- **Where:** planner (M4) emits the card; `wr2_html_renderer/composer.py` and step 4 (hero image generator) consume it.
- **State:** `art_direction` columns in the ledger; a small taxonomy of hero_concept classes (document-still-life, Bali-place-photography, abstract-data-form, human-situation, symbolic-object) with cooldowns.
- **Mechanics:** palette_emphasis rotates within brand tokens (yellow-dominant / dark-dominant / paper-light), hero_concept chosen by LLM from the class taxonomy given the brief, image_style matched to liveness (breaking → stark type-led, maybe no photo; evergreen → richer imagery).

**Expected effect:** Breaks visual rhythm monotony at the feed level — the dimension followers actually perceive when scrolling the grid. Currently WR2 varies layouts (partially) but not _visual mood_; this is the cheapest axis to vary because it's already parameterized in the renderer's design tokens.

**Risk:** Unconstrained "mood" generation drifts off-brand; bound everything to the existing brand cortex tokens and keep the taxonomy small (5 concept classes). Image-gen quality variance per concept class is real — monitor the designer-loop reject rate per class.

---

### M11 — The Feedback Bandit (metrics → sampling weights, not prose amendments)

**Who uses it:** Chartbeat/homepage testing economics; Morning Brew's behavior-driven expansion; tier (c) contextual-bandit content systems; Duolingo's test-and-learn cadence institutionalized.

**How it works technically:** Each published carousel logs its decision vector (M2). IG metrics (reach, saves, shares, profile taps, follows — _weighted_, saves/shares >> likes for a consultancy) arrive in the weekly scrape. A bandit layer maintains per-arm statistics: arms are decision _features_ (hook_type, format, arc, layout family), scored per theme and per liveness tier (a hook that wins for breaking-tax may lose for evergreen-visa). The planner's sampling weights = bandit posterior × cooldown mask × eligibility filter. Exploration floor (~15-20%) guarantees continued variety; exploitation lifts the average.

**WR2 implementation:**

- **Where:** new `wr2_bandit.py` sitting between the weekly metrics analyst (step 8) and the planner (M4).
- **State:** `decision_outcomes(draft_id, decision_vector_json, reach, saves, shares, follows, computed_score, scored_at)`; `arm_stats(feature_type, feature_value, theme, liveness, n, mean_score, updated_at)`.
- **Mechanics:** start dead simple — per-arm exponentially-weighted average of normalized engagement score, epsilon-greedy (ε=0.2) over weights ∝ arm score. Thompson sampling is a later refinement. The weekly analyst's role shifts from "propose prose amendments" (unenforceable) to "set bandit hyperparameters and vet new arms" (enforceable).
- **Guardrails:** brand-safety constraints are _masks_, not weights — the bandit can never explore outside eligible arms. Minimum sample sizes before an arm's weight moves (avoid 1-post verdicts).

**Expected effect:** Converts WR2's existing metrics loop from decorative to causal. This is the engagement mechanism: the system discovers, per audience and per theme, which hooks/formats actually produce saves and follows, and drifts toward them — while cooldowns and ε-exploration prevent convergence to a new monoculture.

**Risk:** Instagram's metrics are noisy and confounded (topic popularity dominates format effects at n=34). Expect weak signals for months; keep update rates slow, pool across themes until per-theme n is adequate, and never let the bandit override fact-honesty or brand rules. The failure mode to avoid is optimizing toward sensational hooks that erode consultancy trust — include a human-set "brand fit" multiplier per arm.

---

### M12 — The Content Matrix (topic × format cadence calendar)

**Who uses it:** Morning Brew/The Hustle vertical-section matrices; every news desk's beat system; Schibsted's desk structure.

**How it works technically:** A simple two-axis schedule: themes (visa, tax, property, company/PT PMA, labor/immigration enforcement) × weekly cadence targets, ensuring no theme exceeds a share cap of recent output and no theme starves. The topic selector (step 2) currently picks the best-scored item; the matrix makes it pick the best-scored item _subject to balance constraints_ — unless a breaking item overrides everything (breaking always wins; that's the news rule).

**WR2 implementation:**

- **Where:** step 2 topic selector, small change.
- **State:** theme distribution over last 14 published carousels (from ledger); per-theme target shares (config, e.g. no theme > 40% of last 10, every core theme ≥ 1 per 14 days).
- **Mechanics:** selector scores items as today, then applies the matrix filter: drop candidates whose theme is over cap (unless liveness=breaking or score exceptionally high), boost starved themes. Log overrides.

**Expected effect:** Ends theme clumping (which the follower perceives as "this account only talks about X lately"), spreads the audience's diverse interests across the calendar, and interacts productively with M11 (each theme accumulates its own arm stats).

**Risk:** Balance constraints occasionally suppress the genuinely best story of the day. The breaking/exception override must be real; keep caps loose. Also, theme taxonomy must match how the audience segments itself — validate against follow/unfollow and per-post reach patterns in M11 data.

---

## 3. Ranked Adoption Shortlist (Top 5)

Ranking criteria: disease-killing leverage ÷ implementation cost, ordered by what unlocks the rest.

### #1 — M2 + M3 combined: Creative Ledger & Constraint Sampling

**"Make 'vary it' a SQL query; delete the examples."** This is the root fix and the cheapest. WR2's own production data is the proof: the one axis with DB lookback is the one axis that varies. Implementation is days, not weeks: one table, one backfill classifier pass, prompt surgery (mostly deletion), one deterministic checker. Every other mechanism on this list _reads from the ledger_ — it is the keystone. Do this first; diseases 1 and 3 die immediately.

### #2 — M1 + M4 combined: Structured Format Objects & the Planner/Writer Split

**"Structure is chosen, never defaulted."** The architectural cure for frozen arc (disease 2) and layout monoculture (disease 4): the planner (part code, part LLM) picks format/arc/hook/layouts under ledger constraints; the writer fills typed slots; schemas guarantee the fields the five dormant layout families need. Bigger build (a format registry, arc grammar, planner module, generator rewrite) — this is the week's-worth-of-work item — but it converts WR2 from "one prompt that hopes" into "a system that decides." Without #1 it would re-anchor; with #1 it is fully constrained.

### #3 — M6: Liveness-Driven Mode Switching

**"Let the news moment set the mode."** The direct answer to the "adapts to the moment" goal, and the trigger that naturally wakes up the dramatic unused layouts (dark-status-list for breaking, qa-dialogue for evergreen). Mostly a mapping table plus planner branches on a field that already exists; the only real new state is `story_cluster_id` for developing-story updates. High perceptual payoff — the feed starts to _look_ like a living newsroom — for modest cost. Requires #2's planner to land first, hence third.

### #4 — M7: Hook Taxonomy with Enforced Rotation

**"Industrialize the cover."** The cover is the entire CTR; WR2's covers are its most formulaic surface. Six hook types with structural recipes, cooldown-enforced rotation, and regex-level validation is a small, self-contained build on top of #1/#2 with an outsized engagement effect. Ranked below mode-switching only because it depends on the same planner infrastructure and solves a narrower (if critical) surface.

### #5 — M11: The Feedback Bandit

**"Close the loop into the sampler, not into prose."** WR2 already scrapes metrics and already has a weekly analyst — but the loop currently terminates in unenforceable brand-amendment prose. Rewiring it into per-arm statistics that shape the planner's sampling weights turns engagement from a hope into a control system. Ranked fifth not for value but for sequencing: it needs the decision vectors from #1/#2 as its input data, and at n≈34 carousels its signals will be weak for months — start it in log-only/shadow mode early, let it govern weights only once per-arm sample sizes justify it.

**Deliberately not in the top 5:** M8 (franchise segments — high brand value, but design decisions should follow a few weeks of rotation data), M9 (near-duplicate gate — fold its deterministic checks into the M3 checker at launch; graduate to a standalone gate later), M10 (art direction cards — real feed-level payoff, but a second-wave refinement), M5 (arc grammar — delivered _inside_ #2's format registry rather than as a separate project), M12 (content matrix — a half-day change to the topic selector; do it opportunistically alongside #3).

---

## 4. The Meta-Lesson

Every world-class system surveyed — from 2014 Wordsmith to 2026 multi-agent pipelines — converges on the same architecture: **curate the space of possible structures; decide structure with stateful, auditable machinery (rotation, cooldowns, bandits); let the model be brilliant only inside the slot it was assigned; verify; measure; feed the measurement back into the machinery.** The model is the last place variety comes from, never the first. WR2's diagnostics show it currently asks prose to do the job of state — and the one place it already has state, it already works. The roadmap above is, in essence, "do the register/tone thing, eight more times, then close the loop."

---

### Sources consulted (web-verified items)

- Reuters Lynx Insight / News Tracer: [Digiday](https://digiday.com/media/uh-oh-reuters-robot-writer-can-churn-earnings-reports/) · [Reuters Agency](https://www.reutersagency.com/en/media-center/how-ai-helps-power-trusted-news-at-reuters/) · [newsrewired](https://www.newsrewired.com/2018/11/07/cybernetic-newsroom-why-reuters-is-marrying-human-and-robot-journalism/) · [Press Gazette](https://pressgazette.co.uk/news/ai-journalism/)
- Bloomberg Cyborg: [Klover.ai](https://www.klover.ai/ai-in-journalism-2025-whats-changing-in-newsrooms-and-coverage/) · [Stork.ai](https://www.stork.ai/en/bloomberg-cyborg)
- AP / Wordsmith: [ReplacedByAI](https://www.replacedbai.com/blog/will-ai-replace-journalists)
- Heliograf: [bright-amber case study](https://www.bright-amber.com/case-studies/ai-driven-content-generation-for-marketing) · [Spreadbot](https://spreadbot.ai/blog/streamlining-editorial-workflows-the-role-of-content-automation-tools-in-modern-content-strategy/)
- Axios Smart Brevity: [Axios HQ checklist](https://www.axioshq.com/research/smart-brevity-communication-checklist) · [Bernoff](https://bernoff.com/blog/how-much-is-brevity-worth-if-youre-axios-525-million) · [CJR](https://www.cjr.org/criticism/axios-smart-brevity-longform.php)
- Schibsted / Aftonbladet: [United Robots](https://www.unitedrobots.ai/resources/blog/aftonbladet-use-robot-texts-to-expand-premier-league-coverage) · [Schibsted AI hub](https://schibsted.com/news/aftonbladet-creates-ai-hub/) · [Schibsted Hej Aftonbladet/HeiVG](https://schibsted.com/news/aftonbladet-and-vg-team-up-on-unique-ai-news-services/)
- Reuters AI editor (2025): [Tomorrow's Publisher](https://tomorrowspublisher.today/new-formats/reuters-appoints-first-newsroom-ai-editor/)
- Morning Brew: [intro.co](https://intro.co/blog/how-to-approach-content-marketing-in-2025)
- Duolingo: [Cannes Lions](https://www.canneslions.com/festival/speakers/zaria-parvez-s1-95727) · [eCommerce Expo](https://www.ecommerceexpo.co.uk/news/zaria-parvez-senior-global-social-media-manager-duolingo-creativity-community-social-media-strategy) · [barbarosozturk.com](https://barbarosozturk.com/blog/the-unhinged-corporate-social-media-playbook-zaria-parvez-the-mastermind/)

Items marked [UNVERIFIED] in the text: BBC News Labs current production status; NYT Instagram internal process specifics; Bloomberg Quicktake motion-grammar details; specific publisher headline-A/B tooling claims; tier (c) agency-pipeline internals (drawn from general 2024-26 practice patterns rather than named published systems).

---

## 2. Seat Gemini 3.1 Pro — report integrale

# 🌾 The "Reuse-First" OSS Harvest for WR2 (2025-2026 Landscape)

**Target:** WR2 — Bali Zero's Autonomous Editorial Organism
**Objective:** Cure diagnosed diseases (Single-Example Anchoring, Frozen Narrative Arc, Formulaic Subheads, Layout Monoculture, No Editorial Memory) via integration of high-leverage open-source projects, moving away from writing from scratch.

---

## Part 1: Full Harvest Table by Category

Here is the comprehensive landscape of open-source projects across your targeted categories, assessed for maturity and relevance to WR2.

| Category & Repo                             | URL                                   | License    | Maturity (Stars/Act.) | What it does                                                     | WR2 Integration Potential                                                                                             | Verifica                                                                                                                        |
| :------------------------------------------ | :------------------------------------ | :--------- | :-------------------- | :--------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **1. Programmatic Design & Render Engines** |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Vercel Satori**                           | github.com/vercel/satori              | MPL-2.0    | High (10k+)           | Converts HTML/CSS to SVG/PNG at the edge.                        | **Medium:** Could replace the heavy Playwright step (`composer.py`) for faster, parallel generation of simple slides. | ✅ verified (MPL-2.0 matches, 13.7k★ active)                                                                                    |
| **html-to-image**                           | github.com/bubkoo/html-to-image       | MIT        | High (4k+)            | Generates images from DOM nodes.                                 | **Medium:** A lighter alternative to Playwright if running in a headless DOM context.                                 | ✅ verified (MIT matches, 7.2k★ active)                                                                                         |
| **OpenPolotno**                             | github.com/therutvikp/OpenPolotno     | MIT        | Low-Med               | Canva-like editor SDK alternative to Polotno.                    | **Low:** Too UI-focused. WR2 needs headless rendering.                                                                | ❌ BLOCKED — HTTP 451 DMCA takedown (blocked 2026-07-08, github/dmca#2026-07-07-polotno). Repo inaccessible; do not integrate.  |
| **html-to-Instagram-carousel**              | github.com/Hanseldemulcent167/...     | MIT        | Low                   | CLI tool to convert HTML to 1080x1350 PNGs.                      | **High:** Directly maps to WR2's exact rendering need.                                                                | ✅ verified (MIT matches, 3★, pushed 2026-07-19 — real but tiny/unproven)                                                       |
| **2. LLM Editorial / Article Pipelines**    |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Stanford STORM**                          | github.com/stanford-oval/storm        | MIT        | High (12k+)           | Simulates multi-perspective conversations to research & outline. | **High:** Plugs into WR2 Stage 2 to enrich the brief and destroy "Frozen Narrative Arcs" before generation.           | ✅ verified (MIT matches; actual 30.1k★, report undercounted "12k+")                                                            |
| **GPT-Researcher**                          | github.com/assafelovic/gpt-researcher | MIT        | Very High (15k+)      | Autonomous web-research agent.                                   | **Medium:** Better for long-form reports than 7-slide IG carousels, but good for deep-dive facts.                     | ⚠️ license mismatch — repo real (Apache-2.0, 28.4k★) but report claims MIT                                                      |
| **GPT-Newspaper**                           | github.com/assafelovic/gpt-newspaper  | MIT        | Medium (2k+)          | Multi-agent publishing house (curator, writer, designer).        | **High:** Architectural inspiration for splitting WR2's "ONE large prompt" into specialized sub-agents.               | ⚠️ moved to rotemweiss57/gpt-newspaper (MIT matches) — STALE, no push since 2024-06-21 (2yr+ dead)                              |
| **CrewAI**                                  | github.com/joaomdmoura/crewai         | MIT        | Very High (20k+)      | Orchestrates role-playing autonomous AI agents.                  | **High:** The engine to rebuild WR2's monolith into a true "newsroom."                                                | ⚠️ renamed/moved to crewAIInc/crewAI (redirect confirmed); MIT matches; 55.8k★ (report undercounted "20k+")                     |
| **3. Social-Content Automation**            |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Postiz**                                  | github.com/gitroomhq/postiz-app       | AGPL-3.0   | High (8k+)            | Agentic social media scheduling & collaboration tool.            | **High:** Could entirely replace your bespoke "macOS human review app."                                               | ✅ verified (AGPL-3.0 matches exactly, 33.5k★ active)                                                                           |
| **Mixpost**                                 | github.com/inovector/mixpost          | MIT        | Medium (3k+)          | Self-hosted social media management platform.                    | **Medium:** A robust, privacy-first scheduling engine.                                                                | ✅ verified (MIT matches, 3.4k★)                                                                                                |
| **open-carrusel**                           | github.com/Hainrixz/open-carrusel     | MIT        | Low                   | AI-powered carousel builder via Claude.                          | **Low:** Good reference, but too manual/chat-based for WR2's automation.                                              | ✅ verified but maturity understated — MIT matches, actual 372★, not "Low"                                                      |
| **4. Constrained & Structured Generation**  |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Instructor**                              | github.com/jxnl/instructor            | MIT        | High (7k+)            | Pydantic-based structured extraction & retries.                  | **Very High:** Forces Claude to pick diverse layout families safely.                                                  | ⚠️ moved to 567-labs/instructor (org rename, redirect confirmed); MIT matches; 13.6k★ (undercounted "7k+")                      |
| **BAML**                                    | github.com/BoundaryML/baml            | Apache-2.0 | Medium (2k+)          | Domain-specific language for LLM type-safety.                    | **High:** Un-breaks layout monoculture by strictly typing the JSON output schema.                                     | ✅ verified (Apache-2.0 matches, 8.6k★)                                                                                         |
| **Outlines**                                | github.com/outlines-dev/outlines      | Apache-2.0 | High (6k+)            | Neural text generation with guaranteed formatting (FSMs).        | **High:** Best if WR2 moves to local/open-weight models (vLLM) to enforce schema natively.                            | ✅ verified — redirects to dottxt-ai/outlines (confirms "may have moved" note); Apache-2.0 matches; 14.6k★ (undercounted "6k+") |
| **5. Prompt / Eval Harnesses (QA)**         |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Promptfoo**                               | github.com/promptfoo/promptfoo        | MIT        | High (5k+)            | CLI to test & eval LLM prompt quality & regressions.             | **Very High:** The cure for "Single-Example Anchoring." Matrix-test your kickers.                                     | ✅ verified (MIT matches, 23.4k★, undercounted "5k+")                                                                           |
| **DeepEval**                                | github.com/confident-ai/deepeval      | Apache-2.0 | High (4k+)            | The "pytest for LLMs" (faithfulness, bias, RAG metrics).         | **High:** Replaces WR2 Stage 5 (Fact extractor/checker) with standardized OSS metrics.                                | ✅ verified (Apache-2.0 matches, 17k★, undercounted "4k+")                                                                      |
| **Braintrust**                              | braintrust.dev (SDK OSS)              | MIT (SDK)  | High                  | Evals, logging, and production observability.                    | **High:** Creates the "Editorial Memory" WR2 currently lacks by logging past outputs to a dataset.                    | ⚠️ not a GitHub repo (SaaS product page) — not independently verified via gh api                                                |
| **6. Editorial QA Linters**                 |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **Vale**                                    | github.com/errata-ai/vale             | MIT        | High (9k+)            | Syntax-aware linter for prose (style-as-code).                   | **Very High:** Enforces the "Bali Zero" brand voice programmatically post-generation.                                 | ⚠️ moved to vale-cli/vale (org rename, redirect confirmed); MIT matches; 5.6k★ (report overstated "9k+")                        |
| **proselint**                               | github.com/amperser/proselint         | MIT        | High (6k+)            | Linter for English prose.                                        | **Medium:** Good baseline, but Vale can run its rules natively.                                                       | ⚠️ license mismatch — repo real (BSD-3-Clause, 4.6k★) but report claims MIT                                                     |
| **alex**                                    | github.com/get-alex/alex              | MIT        | High (5k+)            | Catches insensitive, inconsiderate writing.                      | **Low:** Not the primary issue for tax/visa content, though good practice.                                            | ✅ verified (MIT matches, 5.1k★) — note: stale, last push 2024-11-27                                                            |
| **7. Layout Intelligence**                  |                                       |            |                       |                                                                  |                                                                                                                       |                                                                                                                                 |
| **OpenPencil**                              | github.com/openpencil/openpencil      | MIT        | Emerging              | Open-source design editor using Yoga for auto-layout.            | **Medium:** Could serve as the bridge between layout templates and dynamic HTML generation.                           | ❌ NOT FOUND (HTTP 404 — likely hallucinated or already deleted)                                                                |
| **Style Dictionary**                        | github.com/amzn/style-dictionary      | Apache-2.0 | High (8k+)            | Build system for design tokens.                                  | **High:** Separates WR2's CSS into tokens, allowing dynamic color/theme shifts per topic.                             | ⚠️ moved to style-dictionary/style-dictionary (org rename, redirect confirmed); Apache-2.0 matches; 4.7k★ (overstated "8k+")    |

---

## Part 2: Deep-Dive on the 8 Most Promising Projects (Integration Sketches)

### 1. Instructor (Category 4: Constrained Generation)

- **What it does:** Uses Python's Pydantic to ensure LLMs return perfectly structured JSON, automatically handling validation and retry loops if the model hallucinates a field.
- **The Disease it Cures:** **Layout Monoculture & Frozen Narrative Arc.** Right now, Claude outputs the same 4 layout families because the prompt's examples anchor it.
- **Integration Sketch (WR2 Stage 3 - Draft Generator):**
  Instead of writing a massive prompt asking for JSON, you define Pydantic models for _every_ layout family:

  ```python
  from typing import Union, List
  from pydantic import BaseModel, Field
  import instructor
  from anthropic import Anthropic

  client = instructor.from_anthropic(Anthropic())

  class StatCardHeroSlide(BaseModel):
      layout: str = Field(default="stat-card-hero")
      statistic: str = Field(description="A shocking number, e.g. '30%'")
      context: str

  class EvidenceCarvedSlide(BaseModel):
      layout: str = Field(default="evidence-carved")
      citation: str
      claim: str

  class Carousel(BaseModel):
      slides: List[Union[StatCardHeroSlide, EvidenceCarvedSlide, ...]] = Field(
          description="Generate exactly 7 slides. You MUST use at least 4 DIFFERENT layout types."
      )

  # Claude is now FORCED by the schema to populate the richer layout families.
  ```

- **Effort:** Small (S). Just wrap your existing Claude call in Instructor and map your HTML templates to Pydantic models.

### 2. Promptfoo (Category 5: Prompt/Eval Harnesses)

- **What it does:** A CLI tool to matrix-test prompts against test cases to prevent regressions.
- **The Disease it Cures:** **Single-Example Anchoring & Formulaic Cover Subheads.**
- **Integration Sketch (WR2 Dev Pipeline):**
  You set up a `promptfooconfig.yaml` with your base prompt. You create test cases with different news articles (Tax, Visa, Property). You assert that the generated `subhead` DOES NOT equal "IMMIGRATION ALERT" or "TAX ALERT".
  When you tweak the prompt to fix the anchor, you run `promptfoo eval`. It generates 30 carousels locally in minutes and scores them. You will _know_ empirically if a prompt change caused a regression before pushing to production.
- **Effort:** Medium (M). Requires setting up the eval test suite, but saves hundreds of hours of manual QA.

### 3. CrewAI (Category 2: LLM Editorial Pipelines)

- **What it does:** A framework for orchestrating autonomous AI agents with specific roles, goals, and memories.
- **The Disease it Cures:** **No Editorial Memory & The "One Large Prompt" Monolith.**
- **Integration Sketch (WR2 Stage 2 & 3):**
  Replace `wr2_draft_generator.py` with a Crew.
  - **Agent 1: The Managing Editor.** Has access to a RAG tool connected to your PostgreSQL DB of past IG metrics. Goal: Review the past 30 days and set the "angle/tone" for today to ensure variation.
  - **Agent 2: The Researcher (like STORM).** Grounds the article in facts.
  - **Agent 3: The Copywriter.** Writes the slides based on Agent 1's angle.
  - **Agent 4: The Art Director.** Chooses the layout families and writes the image prompts.
    Instead of Claude trying to balance facts, tone, layout, and image prompts in one breath, specialized agents pass the draft down the assembly line.
- **Effort:** Large (L). Requires a fundamental architecture rewrite of the draft generator, but unlocks true autonomy.

### 4. Stanford STORM (Category 2: Editorial Pipelines)

- **What it does:** Forces the AI to ask multi-perspective questions before writing an outline.
- **The Disease it Cures:** **Frozen Narrative Arc.** Your carousels always follow Cover -> Take -> Body -> CTA because the LLM is lazy.
- **Integration Sketch (WR2 Stage 2 - Topic Selector):**
  Plug STORM in _before_ slide generation. When a news item is picked (e.g., a new Golden Visa rule), STORM creates personas (an Expat, an Indonesian Tax Official, a Real Estate Developer) and has them "interview" an LLM expert. The resulting outline is dramatically richer, forcing the downstream draft generator to adopt diverse narrative arcs (e.g., a Q&A dialogue layout) because the _source material_ is now a multi-perspective debate, not just a summary.
- **Effort:** Medium (M). Can be run as an upstream batch job that enriches the database row.

### 5. Vale (Category 6: Editorial QA Linters)

- **What it does:** A syntax-aware, highly customizable style-as-code linter.
- **The Disease it Cures:** **Tone Drift / Brand Consistency.**
- **Integration Sketch (WR2 Stage 6 - HTML Renderer/QA):**
  Before Playwright renders the HTML, run Vale over the extracted text of the draft JSON. Create a `.vale.ini` config specifically for "Bali Zero."
  Rules to write:
  - `Deny: "Our read:"` (Throws an error if the model regresses to this phrase).
  - `Deny: ["digital nomad", "paradise"]` (Enforce a professional tone, avoiding clichés).
    If Vale fails, the draft is rejected and sent back to the Draft Generator for a rewrite. It acts as an automated copy desk.
- **Effort:** Small (S). Writing the YML rules is trivial; integrating the binary into the Python pipeline is just a subprocess call.

### 6. html-to-Instagram-carousel (Category 1: Render Engines)

- **What it does:** A specialized tool to turn HTML into 1080x1350 slices.
- **The Disease it Cures:** Pipeline fragility and heavy dependencies. Playwright is a massive browser binary; if it breaks or memory-leaks, generation stops.
- **Integration Sketch (WR2 Stage 6 - HTML Renderer):**
  Swap out raw Playwright orchestration. If `composer.py` is struggling with CSS flexbox bugs or geometry checks, mapping your templates to this specialized library (or `html-to-image`) reduces the bespoke code you have to maintain for pixel-perfect slicing.
- **Effort:** Small (S). A near drop-in replacement for your Playwright script.

### 7. Postiz (Category 3: Social-Content Automation)

- **What it does:** Agentic, open-source social media scheduler.
- **The Disease it Cures:** **Human Review Bottlenecks.**
- **Integration Sketch (WR2 Stage 7 - Human Review App):**
  Instead of maintaining a custom macOS app for human review, WR2 pushes the final PNGs and captions via API directly into a self-hosted Postiz instance as a "Draft." The human logs into the beautifully designed Postiz web UI from anywhere, reviews, and clicks "Approve." Postiz handles the actual Instagram Graph API publishing.
- **Effort:** Medium (M). Requires spinning up a Docker container for Postiz and writing a simple API POST request from WR2.

### 8. DeepEval (Category 5: QA/Eval)

- **What it does:** Quantitative metrics for LLM outputs (Faithfulness, Answer Relevance).
- **The Disease it Cures:** **Hallucination Risk in Complex Layouts.**
- **Integration Sketch (WR2 Stage 5 - Fact Checker):**
  Replace your bespoke fact-checker. Use DeepEval's `FaithfulnessMetric`. Pass the source news article as the `retrieval_context` and the generated slides as the `actual_output`. If the Faithfulness score drops below 0.9 (meaning Claude hallucinated a visa requirement to fit a "stat-card-hero" layout), the carousel is auto-parked.
- **Effort:** Small (S). Extremely easy to import into an existing Python pipeline.

---

## Part 3: Ranked Top-5 Adoption Shortlist for WR2

If you have limited engineering cycles this sprint, here is the exact order in which to adopt these OSS tools to cure WR2's most fatal diseases with the highest ROI.

### 🥇 1. Instructor (or BAML)

- **Why:** This is the most urgent fix. It cures **Layout Monoculture** instantly. By enforcing a Pydantic schema that _demands_ specific data structures (like a "Debate" object or a "Stat" object), you bypass the LLM's tendency to take the path of least resistance (the 4 basic layouts). It fundamentally changes the interface from "prompt engineering" to "software engineering."

### 🥈 2. Promptfoo

- **Why:** Cures **Single-Example Anchoring**. Stop guessing if a prompt change will ruin the tone. Build a 20-article test suite in Promptfoo. Run the eval. You will immediately see that taking out "IMMIGRATION ALERT" fixes the cover subhead, but you'll also catch if it accidentally breaks the CTA slide. Confidence to iterate quickly is what WR2 needs most.

### 🥉 3. Vale (Style-as-Code)

- **Why:** Easiest win for quality control. Encoding the "Bali Zero" brand voice into deterministic YML rules ensures that no matter how much Claude hallucinates or drifts, words like "Our read:" or cliché expat jargon will never make it to the renderer. It’s a literal firewall for your brand voice.

### 🏅 4. Postiz

- **Why:** Delete your bespoke macOS review app. It is technical debt. Spinning up a self-hosted Postiz instance gives you a world-class review, scheduling, and publishing UI out-of-the-box, allowing you to focus purely on the generation intelligence of WR2.

### 🏅 5. CrewAI

- **Why:** The long-term cure for **No Editorial Memory** and the **Frozen Narrative Arc**. Splitting WR2 into an Agentic Newsroom (Editor, Researcher, Writer, Designer) allows you to inject IG metrics into the Editor's prompt _only_, freeing the Writer to focus purely on copy. This breaks the monolith and allows true dynamic narrative structures to emerge based on the Editor's daily briefing.

---

_Generated by Antigravity Research Agent — 2026-07-20_

---

## 3. Seat Codex sol ultra — report integrale

[Air-M5]

# WR2 architecture review: from prompt-driven output to an editorial compiler

## Review basis

This is a read-only review of `/Users/balizero/nuzantara` at commit `fe116f0b`. The checkout is ten commits behind its local `origin/main` reference, but the reviewed WR2 core files have no diff against that reference. The Pro was unreachable, so this assesses repository architecture, not current production database/runtime state.

## Executive assessment

WR2’s central limitation is not model quality. It is an architectural contract gap:

```text
grounded brief
    ↓
one prompt decides angle + arc + copy + slide shape + visuals
    ↓
loosely normalized dictionaries
    ↓
downstream code guesses their semantics
    ↓
renderer falls back to four generic layouts
```

The prompt is acting simultaneously as planner, schema, policy engine, diversity controller, and copywriter. The renderer, meanwhile, contains a richer visual language but receives an impoverished legacy representation.

That produces five systemic effects:

1. Variety is aspirational unless it is backed by state.
2. Rich layouts are unreachable because semantic structure is discarded.
3. Failures are repaired by regenerating the whole deck.
4. Fact and language validators see only selected legacy text fields.
5. Production outcomes cannot reliably be attributed to editorial decisions.

The target should be a small editorial compiler:

```text
brief
  → deterministic evidence catalogue
  → candidate angles
  → memory-aware signature reservation
  → parametric arc / beat plan
  → typed slide copy
  → deterministic content validators
  → conditional constrained patch
  → frozen render plan
  → existing visual QA and human approval
```

This does not require rewriting the brand layouts. It requires giving them a typed, enforceable upstream language.

---

# 1. Architecture assessment

## 1.1 One-shot prompt versus staged generation

### Current architecture

The main drafting prompt covers editorial rules, register, image modes, slide topology, wording, CTA, layout-adjacent instructions, and a fully populated JSON example in one block: [wr2_draft_generator.py:316–557](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:316).

The example itself encodes the invariant sequence:

```text
cover → editorial take → body slides → CTA
```

at [wr2_draft_generator.py:470–546](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:470). The model then receives a direct instruction to generate the complete slide JSON “NOW” at [wr2_draft_generator.py:655–742](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:655).

Only one model call produces the entire result: [wr2_draft_generator.py:839–863](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:839). Parsing takes the text between the first `{` and last `}`, which is fragile around commentary or multiple objects: [wr2_draft_generator.py:824–836](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:824).

The result is then reduced to a whitelist of legacy fields by `_normalise_slides`: [wr2_draft_generator.py:1183–1239](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1183). Any richer semantic structure emitted by the model would currently be discarded.

### What staging would buy concretely

Use four logical stages, but not necessarily four LLM calls:

1. **Angle selection**

   Produce 2–3 grounded candidates containing the reader promise, hook type, consequence, evidence coverage, and eligible arc.

2. **Structure**

   Select a candidate against editorial memory and instantiate a typed beat plan. No polished prose yet.

3. **Copy**

   Fill only the fields permitted by each slide shape, bound to evidence claim IDs and word budgets.

4. **Polish**

   Run only when deterministic validation finds a specific problem. Return an allowlisted JSON Patch rather than another complete carousel.

Benefits in this codebase:

- Narrative choice becomes observable rather than buried inside prose.
- Arc variation occurs before wording can anchor structure.
- The renderer receives explicit shapes instead of inferring them from body text.
- Claim IDs survive from evidence to individual facts, statistics, statuses, and answers.
- A long closer triggers a closer-only patch, not a new angle and deck.
- Diversity can be checked before expensive copy/image/render stages.
- Stage-specific failures become retryable and idempotent.
- Stronger models can be reserved for copy while simpler planning/repair stages use cheaper sanctioned capacity.

The current code already performs whole-deck retries for an overlong closer and anti-sameness collision: [wr2_draft_generator.py:1488–1541](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1488). Thus the worst case is already three full generations. A staged happy path of two calls—`angle+structure`, then `copy`—plus conditional repair can improve control without necessarily increasing the worst-case call count.

### What staging would cost

- Two successful model round trips instead of one in the initial rollout.
- More state: prompt versions, stage outputs, model IDs, attempts, validation results.
- Cross-stage drift unless downstream stages receive immutable plan IDs and evidence references.
- Repeated brief context unless the evidence catalogue is compact.
- A resumption protocol for partially completed drafts.
- More schemas and compatibility work around existing queue rows.
- Operational changes to metrics and retry semantics.

The OAuth client already supports structured JSON schemas, so this is not a new client integration: [claude_oauth_client.py:321–337](/Users/balizero/nuzantara/apps/backend-rag/backend/llm/claude_oauth_client.py:321). However, schemas above its size cap or unsupported model paths can fall back to text behavior, so every stage still needs local Pydantic validation: [claude_oauth_client.py:399–422](/Users/balizero/nuzantara/apps/backend-rag/backend/llm/claude_oauth_client.py:399), [claude_oauth_client.py:488–500](/Users/balizero/nuzantara/apps/backend-rag/backend/llm/claude_oauth_client.py:488).

### Recommendation

Implement four logical stages, initially using:

```text
Call 1: angle candidates + selected arc + beat plan
Call 2: typed copy
Call 3: only if needed, constrained JSON Patch
```

Do not begin with four unconditional calls. Split angle and structure later only if stage telemetry shows a measurable benefit.

---

## 1.2 Slide grammar: the missing contract

### Current state

The current compositor declares 15 renderable families, not nine: [composer.py:45–67](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:45). The older renderer documentation still says nine: [renderer.py:27–31](/Users/balizero/nuzantara/scripts/wr2_html_renderer/renderer.py:27).

Despite those 15 families, automatic routing effectively remains:

- first slide → `cover-photo`
- last/CTA → `statement-bomb`
- middle slide with hero → `photo-headline-yellow-sub`
- everything else → `editorial-text`

That routing is explicit at [composer.py:112–172](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:112). The comments correctly acknowledge that richer auto-routing is unsafe because structured fields are absent: [composer.py:130–132](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:130).

The richer contracts already exist:

- Evidence stacks: [evidence-carved.md:13–20](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/evidence-carved.md:13)
- Two-voice dialogue: [qa-dialogue.md:10–19](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/qa-dialogue.md:10)
- Status lists: [dark-status-list.md:11–19](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/dark-status-list.md:11)
- Quantified stat cards: [stat-card-hero.md:10–30](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/stat-card-hero.md:10)
- Source citations: [source-citation.md:3–25](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/source-citation.md:3)

The current fact-stack parser tries to recover structure heuristically from prose: [composer.py:860–978](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:860). That is a useful compatibility mechanism, but it should not be the production authoring protocol.

### Proposed canonical schema

Presentation family and semantic slide shape must be separate concepts. The model should author semantic shapes; the renderer should select compatible visual families.

A Pydantic-style contract:

```python
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field


HookType = Literal[
    "question",
    "number",
    "deadline",
    "contradiction",
    "consequence",
    "human_scene",
    "myth_reversal",
    "before_after",
]

SubheadFormula = Literal[
    "deadline",
    "regulation_code",
    "location",
    "numeric_delta",
    "categorical_verdict",
    "question",
    "contrast",
]


class VisualIntent(BaseModel):
    kind: Literal["none", "hero"] = "none"
    image_mode: str | None = None
    brief: str | None = None


class HookSpec(BaseModel):
    type: HookType
    claim_ids: list[str] = Field(default_factory=list)
    payload: dict[str, str] = Field(default_factory=dict)


class SlideBase(BaseModel):
    index: int = Field(ge=1)
    beat_id: str
    kicker: str | None = None
    visual: VisualIntent = Field(default_factory=VisualIntent)


class CoverSlide(SlideBase):
    shape: Literal["cover"] = "cover"
    role: Literal["cover"] = "cover"
    heading: str
    subheading: str
    hook: HookSpec
    subhead_formula: SubheadFormula


class FactItem(BaseModel):
    label: str | None = None
    text: str
    claim_ids: list[str] = Field(min_length=1)


class EditorialTake(BaseModel):
    label: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)


class FactStackSlide(SlideBase):
    shape: Literal["fact_stack"] = "fact_stack"
    role: Literal["middle"] = "middle"
    heading: str
    facts: list[FactItem] = Field(min_length=2, max_length=5)
    take: EditorialTake | None = None


class DialogueTurn(BaseModel):
    speaker: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)


class QADialogueSlide(SlideBase):
    shape: Literal["qa_dialogue"] = "qa_dialogue"
    role: Literal["middle"] = "middle"
    heading: str
    turns: list[DialogueTurn] = Field(min_length=2, max_length=4)


class StatusItem(BaseModel):
    label: str
    value: str
    status: Literal["neutral", "critical", "positive"]
    claim_ids: list[str] = Field(min_length=1)


class StatusListSlide(SlideBase):
    shape: Literal["status_list"] = "status_list"
    role: Literal["middle"] = "middle"
    heading: str
    items: list[StatusItem] = Field(min_length=3, max_length=6)


class StatPoint(BaseModel):
    label: str
    numeric_value: Decimal
    display_value: str
    claim_ids: list[str] = Field(min_length=1)


class StatCardSlide(SlideBase):
    shape: Literal["stat_card"] = "stat_card"
    role: Literal["middle"] = "middle"
    heading: str
    subheading: str | None = None
    unit: str
    points: list[StatPoint] = Field(min_length=1, max_length=3)
    takeaway: str


class ProseSlide(SlideBase):
    shape: Literal["prose"] = "prose"
    role: Literal["middle"] = "middle"
    heading: str
    subheading: str | None = None
    body: str
    body_claim_ids: list[str] = Field(default_factory=list)


class StatementSlide(SlideBase):
    shape: Literal["statement"] = "statement"
    role: Literal["middle", "closer"]
    statement: str
    emphasis_token: str | None = None
    claim_ids: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    title: str
    issuer: str
    date: str | None = None
    url: str | None = None
    note: str | None = None
    claim_ids: list[str] = Field(default_factory=list)


class SourceCitationSlide(SlideBase):
    shape: Literal["source_citation"] = "source_citation"
    role: Literal["source"] = "source"
    heading: str
    citations: list[Citation] = Field(min_length=1, max_length=5)


AnySlide = Annotated[
    CoverSlide
    | FactStackSlide
    | QADialogueSlide
    | StatusListSlide
    | StatCardSlide
    | ProseSlide
    | StatementSlide
    | SourceCitationSlide,
    Field(discriminator="shape"),
]


class EditorialSignatureRef(BaseModel):
    signature_version: int
    reservation_id: int
    arc_id: str
    hook_type: HookType
    subhead_formula: SubheadFormula
    editorial_kicker: str
    register: str


class CarouselV3(BaseModel):
    schema_version: Literal[3] = 3
    signature: EditorialSignatureRef
    slides: list[AnySlide] = Field(min_length=6, max_length=11)
```

Deck-level validators should enforce:

- contiguous, unique indexes;
- exactly one cover, at index 1;
- exactly one closer, at the final index;
- no CTA body on the closer;
- one source slide at `N-1` when the domain/evidence policy requires it;
- every numeric, legal, date, threshold, and status assertion has a claim ID;
- every claim ID exists in the immutable evidence catalogue;
- exactly one designated editorial-take beat carries the reserved kicker;
- no model-authored `layout_family`;
- shape-specific length and cardinality budgets.

Two shared projections are essential:

```python
def reader_texts(slide: AnySlide) -> tuple[str, ...]: ...

def claim_bearing_segments(
    slide: AnySlide,
) -> tuple[ClaimBearingSegment, ...]: ...
```

Every language gate, fact extractor, caption builder, OCR expectation, and critic should consume these functions. Without that, structured fields will remain invisible to safety checks.

### Routing change

Replace heuristic routing with semantic compilation:

```python
def map_slide_to_family(
    slide: AnySlide,
    *,
    position: int,
    total: int,
    registry: FamilyRegistry,
    trusted_variant: str | None = None,
) -> str:
    if position == 1:
        require(slide.shape == "cover" and slide.role == "cover")
        return "cover-photo"

    if position == total:
        require(slide.shape == "statement" and slide.role == "closer")
        return "statement-bomb"

    default_family = {
        "fact_stack": "evidence-carved",
        "qa_dialogue": "qa-dialogue",
        "status_list": "dark-status-list",
        "stat_card": "stat-card-hero",
        "source_citation": "source-citation",
        "statement": "statement-bomb",
        "prose": (
            "photo-headline-yellow-sub"
            if slide.visual.kind == "hero"
            else "editorial-text"
        ),
    }[slide.shape]

    if trusted_variant is not None:
        registry.require_compatible(
            family=trusted_variant,
            shape=slide.shape,
            role=slide.role,
        )
        return trusted_variant

    return default_family
```

The boundary checks must precede any override. Today, an explicit layout override is evaluated before cover/closer anchors: [composer.py:136–166](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:136). That is safe only because the autonomous normalizer currently drops layout fields. It would become a constitutional bypass if layout were added naively to the new schema.

A family registry should declare:

```python
class FamilyContract(BaseModel):
    family: str
    allowed_shapes: frozenset[str]
    allowed_roles: frozenset[str]
    requires_hero: bool
    static_assets: tuple[str, ...]
    context_model: type[BaseModel]
    min_sample_count: int
    max_sample_count: int
```

The render plan should be compiled once, persisted in the manifest, and reused during all designer-loop rerenders. Current rerenders recalculate routing: [composer.py:1911–1944](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1911).

---

## 1.3 Editorial memory that makes variety enforceable

### Current state

`fetch_recent_same_domain()` reads only the latest two rendered carousels for the same domain and retrieves register plus dominant image mode: [wr2_draft_generator.py:1260–1288](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1260). That context becomes a prompt steer at [wr2_draft_generator.py:1291–1307](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1291).

Hard rejection is feature-flagged off by default: [wr2_draft_generator.py:1421–1432](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1421). After novelty retries are exhausted, the pipeline warns and proceeds: [wr2_draft_generator.py:1512–1541](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1512).

The ledger is written only after rendering, on a best-effort basis. Its schema contains domain, register, dominant mode, one family, and archetype: [216_wr2_topic_type_log.sql:12–32](/Users/balizero/nuzantara/apps/backend-rag/backend/db/migrations_v2/216_wr2_topic_type_log.sql:12). The writer uses `ON CONFLICT DO NOTHING`: [wr2_topic_type_log.py:45–65](/Users/balizero/nuzantara/scripts/wr2_topic_type_log.py:45).

That leaves a concurrency window: two drafts composed concurrently can see the same history and make the same “novel” choice.

### Minimal state

Evolve `topic_type_log`; do not create a competing diversity ledger.

Final-state DDL:

```sql
ALTER TABLE topic_type_log
    ADD COLUMN signature_version SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN liveness_tier TEXT,
    ADD COLUMN hook_type TEXT,
    ADD COLUMN kicker_norm TEXT,
    ADD COLUMN subhead_formula TEXT,
    ADD COLUMN arc_id TEXT,
    ADD COLUMN shape_sequence TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN layout_sequence TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN signature_hash TEXT,
    ADD COLUMN actual_signature JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN reserved_at TIMESTAMPTZ,
    ADD COLUMN reservation_expires_at TIMESTAMPTZ,
    ADD COLUMN released_at TIMESTAMPTZ;

UPDATE topic_type_log
SET reserved_at = rendered_at
WHERE reserved_at IS NULL;

ALTER TABLE topic_type_log
    ALTER COLUMN reserved_at SET NOT NULL,
    ALTER COLUMN reserved_at SET DEFAULT NOW(),
    ALTER COLUMN rendered_at DROP NOT NULL,
    ALTER COLUMN rendered_at DROP DEFAULT;

CREATE INDEX ix_topic_type_log_signature_domain
    ON topic_type_log (domain, reserved_at DESC)
    WHERE deleted_at IS NULL
      AND released_at IS NULL;

CREATE INDEX ix_topic_type_log_signature_global
    ON topic_type_log (reserved_at DESC)
    WHERE deleted_at IS NULL
      AND released_at IS NULL;
```

Do not make `signature_hash` globally unique. Repetition after a sufficient interval is legitimate.

### Lookback

Use the union of:

- last six eligible signatures in the same domain;
- last twelve globally;
- maximum age of 30 days;
- include active, unexpired reservations as well as generated/rendered work;
- exclude released, rejected, deleted, or expired reservations.

This is large enough to detect local formulas and short enough not to ban the brand’s usable vocabulary permanently.

### Prompt injection

Inject categories and blacklists, not historical copy:

```text
EDITORIAL CONTRACT — MUST MATCH EXACTLY

arc_id: developing_known_unknown
hook_type: contradiction
subhead_formula: regulation_code
editorial_kicker: WHAT CHANGES
register: forensic
required_middle_shapes:
  - qa_dialogue
  - status_list
  - fact_stack

FORBIDDEN:
- exact normalized kicker: THE SIGNAL, OUR READ
- arc used by immediately previous same-domain carousel
- exact middle-shape fingerprints:
  fact_stack/prose/prose
  prose/stat_card/prose
- previous two same-domain subhead formulas:
  categorical_verdict, regulation_code
```

Do not inject the previous full headings or a list of suggested alternatives. That merely creates a new anchoring corpus.

### Hard checks after generation

Derive the signature from the output; do not trust self-declared metadata.

```python
def derive_signature(carousel: CarouselV3) -> DerivedSignature: ...

def check_signature(
    *,
    reserved: EditorialSignature,
    actual: DerivedSignature,
    history: EditorialHistory,
) -> tuple[SignatureViolation, ...]: ...
```

Enforce each axis independently:

- **Kicker:** normalized exact value cannot repeat within the configured window.
- **Arc:** cannot equal the immediately previous same-domain arc; maximum two uses in the last six.
- **Subhead formula:** cannot equal either of the previous two same-domain formulas.
- **Hook type:** cannot equal the previous two same-domain hooks; each hook type also has a structural validator.
- **Layout/shape mix:** no exact middle sequence in the last twelve; no more than two identical shapes consecutively; at least three middle shapes when there are five or more middle slots.
- **Register and image mode:** check independently rather than accepting novelty on only one axis.
- **Sequence similarity:** reject near-clones using a normalized longest-common-subsequence threshold, initially in shadow mode.

Hook types need structural predicates. For example:

- `question` requires an interrogative cover hook;
- `number` requires a numeric `claim_id` and displayed value;
- `deadline` requires a date/deadline claim;
- `before_after` requires two named states;
- `human_scene` requires a scene subject and concrete situation.

After a hard violation, repair only the offending field or slide. After bounded retries, park the draft for review. Do not warn and publish a known collision.

### Reservation protocol

1. Generate 2–3 eligible angle/signature candidates.
2. Start a short database transaction.
3. Acquire `pg_advisory_xact_lock(hashtext('wr2:' || domain))`.
4. Re-read history.
5. Select the highest-ranked eligible candidate.
6. Insert or update the reservation with a short expiry.
7. Commit before making the copy call.

No lock is held during an LLM call.

---

## 1.4 Parametric narrative arcs

The current autonomous prompt hardcodes an arc via its filled example. Separately, the interactive storyboarder also specifies a largely fixed cover/frame/facts/discovery/statement progression: [wr2-storyboarder.md:50–140](/Users/balizero/nuzantara/.claude/agents/wr2-storyboarder.md:50). It can emit richer layout-oriented fields, but that path and the autonomous generator are separate schema worlds: [wr2-storyboarder.md:181–227](/Users/balizero/nuzantara/.claude/agents/wr2-storyboarder.md:181).

The correct variation boundary is:

```text
fixed cover role
    +
selected middle arc
    +
conditional source slot
    +
fixed closer role
```

Define arcs as data:

```python
class BeatSpec(BaseModel):
    beat_id: str
    allowed_shapes: frozenset[str]
    evidence_policy: Literal[
        "required",
        "editorial",
        "comparison",
        "source",
    ]
    hero_policy: Literal["forbidden", "allowed", "preferred"]
    max_words: int


class ArcTemplate(BaseModel):
    arc_id: str
    eligible_liveness: frozenset[str]
    beats: tuple[BeatSpec, ...]
```

Initial catalogue:

| Arc                        | Best fit                   | Variable middle                                                            |
| -------------------------- | -------------------------- | -------------------------------------------------------------------------- |
| `breaking_delta`           | Breaking rule/event        | change → affected audience → consequence/deadline → action                 |
| `developing_known_unknown` | Developing story           | signal → known → unknown/Q&A → scenarios/watch → action                    |
| `evergreen_mechanism`      | Explainer                  | misconception/question → mechanism → evidence/stat → comparison → decision |
| `case_to_rule`             | Human/business consequence | scene → conflict → governing rule → consequence → remedy                   |
| `decision_path`            | Visa/tax/company choice    | question → criteria → options/status → trade-off → recommendation          |

Selection should be deterministic and evidence-aware:

```python
def select_arc(
    *,
    evidence: EvidenceCatalogue,
    liveness: str,
    domain: str,
    history: EditorialHistory,
    draft_id: UUID,
) -> ArcTemplate:
    ...
```

The eligibility gate should reject arcs the evidence cannot support. For example, `stat_card` cannot be planned without a grounded quantitative claim, and `qa_dialogue` cannot manufacture a second viewpoint that is absent from the source.

Tie-breaking can be seeded by `draft_id` for replayability, but variation should primarily come from editorial fit and memory—not unbounded randomness.

### Keeping render QA stable

The renderer should never need to understand arcs. It sees only typed slides and a frozen family plan.

That preserves:

- existing geometry checks;
- font and logo gates;
- OCR round trips;
- hero visibility checks;
- family-specific templates;
- designer-loop rerendering.

Arc experimentation happens above the render boundary. New arcs initially use already validated shape/family contracts. A new layout family is a separate rollout from a new narrative arc.

---

## 1.5 Additional limitations found

### A. The generator and closer layout disagree

The generator requires the last slide to be a CTA: [wr2_draft_generator.py:333–340](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:333), [wr2_draft_generator.py:461–468](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:461).

The `statement-bomb` contract says no CTA and only a short statement: [statement-bomb.md:3–18](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/statement-bomb.md:3).

This is constitutional split-brain, not a copy-quality problem. Define one closer contract and enforce it in the typed schema.

### B. Source credibility is specified but structurally unreachable

The source-citation layout says that regulatory, visa, tax, and property carousels should use it at `N-1`: [source-citation.md:3–25](/Users/balizero/nuzantara/skills/bali-zero-brand/layouts/source-citation.md:3).

The generator does not emit citation arrays, `_normalise_slides` would discard them, and the default router never selects `source-citation`. A brand credibility rule currently exists only as dormant template documentation.

### C. Fact extraction already speaks the wrong slide dialect

The fact extractor reads `index`, `title`, and `body`: [wr2_fact_extractor.py:286–312](/Users/balizero/nuzantara/scripts/wr2_fact_extractor.py:286).

The generator emits `slide_number`, `headline`, and `body`. Consequently, body claims may still be extracted, but slide index/title attribution degrades; future facts inside `facts`, `items`, `turns`, or stat points would be skipped completely.

The fact checker also treats `council_debate_json` as part of the external truth corpus: [wr2_fact_checker.py:208–286](/Users/balizero/nuzantara/scripts/wr2_fact_checker.py:208). Generation plans or model reasoning must therefore not be stored in that column.

### D. Language safety gates are blind to rich fields

The reader-facing gate scans heading, subheading, body, statement, and take-related scalar fields: [composer.py:1237–1251](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1237).

It does not naturally inspect fact arrays, dialogue turns, status items, chart labels, or citations. Activating rich layouts without a shared `reader_texts()` projection would widen the safety gap.

### E. Prompt rules are internally contradictory

The prompt says the default should usually be one to three middle heroes: [wr2_draft_generator.py:350–405](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:350), then later requires four to eight hero slides: [wr2_draft_generator.py:548–556](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:548).

Its example uses `warm-amber`, while the allowed mode is `warm-ochre`: [wr2_draft_generator.py:350–355](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:350), [wr2_draft_generator.py:525–535](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:525).

This instruction entropy makes output variance partly accidental and makes failures hard to attribute.

### F. Normalization silently changes meaning

The normalizer uses ordinary Python truth coercion for some flags: [wr2_draft_generator.py:1210–1239](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1210). For example, `"false"` is truthy in Python. Typed parsing should reject the value rather than reinterpret it.

It also truncates headline/body fields using limits different from those in the prompt, creating a second implicit copy policy.

### G. Renderer adapters fail softly

Loop adapters can map aliases and quietly produce empty structures when expected arrays are absent: [composer.py:994–1074](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:994).

The stat renderer extracts the first numeric-looking value rather than consuming an explicit numeric value/unit contract: [composer.py:1631–1658](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1631). Statement emphasis defaults to the final word rather than an authored semantic emphasis: [composer.py:1613–1629](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1613).

These are acceptable legacy adapters, not adequate authoring interfaces.

### H. Fact-stack rendering inserts model text into markup heuristically

The fact-stack path constructs HTML from parsed model text without the same clarity as a typed, escaped context pipeline: [composer.py:934–978](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:934). Besides security hygiene, punctuation or unexpected markup can destabilize geometry.

### I. Topic selection optimizes individual-item relevance, not portfolio composition

The selector considers freshness, domain keywords, liveness, and routine penalties: [wr2_topic_selector.py:123–180](/Users/balizero/nuzantara/scripts/wr2_topic_selector.py:123). It does not consider the recent editorial portfolio.

This can produce a sequence of individually valid but collectively repetitive stories. Portfolio novelty should be a bounded tiebreaker, never a reason to suppress genuinely breaking news.

### J. Identity and observability are split

`wr2_orchestrator_metrics` is keyed to `wr2_carousel_runs`: [203_wr2_orchestrator_metrics.sql:7–35](/Users/balizero/nuzantara/apps/backend-rag/backend/db/migrations_v2/203_wr2_orchestrator_metrics.sql:7). The actual generation pipeline keys work by `war_room_drafts.id`, and the metrics helper documents the mismatch and resolves runs by topic: [wr2_orchestrator_metrics.py:1–34](/Users/balizero/nuzantara/scripts/wr2_orchestrator_metrics.py:1).

Topics can recur. Topic text is not a durable experiment identity.

---

# 2. Five highest-leverage code changes

## Change 1 — Introduce a canonical, versioned Carousel IR

### Design

Add a canonical `CarouselV3` discriminated union using the schema above.

During migration, do not overwrite the legacy list in place:

```sql
ALTER TABLE war_room_drafts
    ADD COLUMN carousel_schema_version SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN carousel_ir JSONB;
```

Create one contract package, for example:

```text
scripts/wr2_contracts/
    carousel_v3.py
    projection.py
    validation.py
    legacy_v1.py
```

Core interfaces:

```python
def parse_carousel(raw: object) -> CarouselV3: ...

def legacy_v1_to_v3(
    slides: list[dict[str, object]],
    *,
    topic: str,
) -> CarouselV3: ...

def v3_to_legacy_slides(
    carousel: CarouselV3,
) -> list[dict[str, object]]: ...

def reader_texts(slide: AnySlide) -> tuple[str, ...]: ...

def claim_bearing_segments(
    slide: AnySlide,
) -> tuple[ClaimBearingSegment, ...]: ...
```

`carousel_ir` becomes canonical after cutover. `slides_json` remains a legacy materialization for historical consumers and rerenders.

### Integration path

1. Add schemas, parser, projections, and legacy adapter.
2. Move fact extraction and language gates to shared projections.
3. Teach the image generator to consume `visual` through an accessor; it currently relies on legacy slide numbers and fields: [wr2_image_generator.py:1457–1485](/Users/balizero/nuzantara/scripts/wr2_image_generator.py:1457).
4. Add v3 support to the compositor.
5. Make the generator dual-write `carousel_ir` and legacy materialization.
6. Migrate remaining readers.
7. Declare `carousel_ir` canonical and freeze legacy writes.

### Migration and rollout

- Replay the existing 34-carousel corpus through `legacy_v1_to_v3`.
- Assert that every current reader-facing string is preserved by `reader_texts()`.
- Assert that all existing body claims remain visible to `claim_bearing_segments()`.
- Dual-read in shadow mode and compare:
  - slide count;
  - reader text;
  - hero intent;
  - selected family;
  - fact extraction coverage.
- Enable v3 production by domain or draft flag, not by replacing all historical rows.

### Risk

The main risk is divergence between canonical IR and legacy materialization. Mitigate it with:

- one-way materialization only;
- a stored content checksum;
- no consumer writing either representation;
- explicit schema versioning;
- immutable historical v1 behavior.

---

## Change 2 — Build editorial memory as a compose-time reservation service

### Design

Extend `topic_type_log` using the DDL in §1.3 and add:

```python
async def fetch_editorial_history(
    conn: asyncpg.Connection,
    *,
    domain: str,
    now: datetime,
) -> EditorialHistory: ...

async def reserve_signature(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID,
    candidates: Sequence[SignatureCandidate],
) -> EditorialSignature: ...

def derive_signature(carousel: CarouselV3) -> DerivedSignature: ...

def validate_signature(
    *,
    reserved: EditorialSignature,
    actual: DerivedSignature,
    history: EditorialHistory,
) -> tuple[SignatureViolation, ...]: ...
```

The signature should cover:

```text
register
dominant image mode
editorial kicker
arc ID
cover hook type
cover subhead formula
middle shape sequence
compiled layout sequence
```

### Integration path

Insert the reservation between planning and copy:

```text
angle/arc candidates
    → transactional reservation
    → copy generation
    → actual-signature derivation
    → hard validation
```

Update the post-render writer from `ON CONFLICT DO NOTHING` to an update that records:

- `rendered_at`;
- actual signature;
- compiled family sequence;
- final signature hash.

Keep post-render logging best-effort. Only the pre-compose reservation and post-copy contract check should gate progression.

### Migration and rollout

1. **Observe:** derive signatures for existing output without changing prompts.
2. **Steer:** inject the selected contract but only log violations.
3. **Enforce categorical axes:** kicker, arc, hook, subhead formula.
4. **Enforce sequence rules:** shape mix and similarity after false-positive calibration.
5. **Enable reservations:** only after updated writers are deployed and `rendered_at` nullability is safe.

Use a full editorial cycle or at least 50 shadow compositions to calibrate thresholds.

### Risk

Over-aggressive novelty can force an unsuitable arc onto a story. Mitigations:

- evidence and liveness eligibility always outrank novelty;
- breaking stories receive an editorial-fit override;
- only the lowest-priority similarity constraint may be relaxed;
- every relaxation is recorded;
- expired reservations are released automatically.

---

## Change 3 — Replace full-deck generation with a staged editorial planner

### Design

Proposed interfaces:

```python
def build_evidence_catalogue(
    brief: GroundedBrief,
) -> EvidenceCatalogue:
    """Deterministic; assigns immutable claim IDs."""


async def generate_angle_candidates(
    *,
    evidence: EvidenceCatalogue,
    liveness: str,
    domain: str,
    history_summary: EditorialHistorySummary,
) -> tuple[AngleCandidate, ...]: ...


def select_angle_and_arc(
    *,
    candidates: Sequence[AngleCandidate],
    history: EditorialHistory,
) -> EditorialPlan: ...


async def generate_storyboard(
    *,
    plan: EditorialPlan,
    evidence: EvidenceCatalogue,
) -> Storyboard: ...


async def write_carousel(
    *,
    storyboard: Storyboard,
    evidence: EvidenceCatalogue,
    signature: EditorialSignature,
) -> CarouselV3: ...


async def patch_carousel(
    *,
    carousel: CarouselV3,
    violations: Sequence[Violation],
) -> tuple[JsonPatchOperation, ...]: ...
```

The polish stage must use an allowlist. It may alter copy paths such as:

```text
/slides/3/body
/slides/5/facts/1/text
/slides/7/statement
```

It may not alter:

```text
schema_version
signature
slide count
indexes
roles
shapes
claim IDs
arc ID
source placement
```

The prompt compiler should contain constraints and schemas, not a fully authored example deck.

### Integration path

- Keep `build_evidence_catalogue()` deterministic and upstream of every LLM call.
- Initially combine angle selection and storyboard into one structured call.
- Use the existing OAuth structured-output interface.
- Replace closer and novelty full-deck retries with validator-driven patches.
- Store stage outputs separately from `council_debate_json`.
- Continue passing `brief_json` as the fact checker’s source of truth.

### Migration and rollout

1. Run the planner against the historical brief corpus without generating copy.
2. Check arc eligibility, evidence coverage, and shape diversity.
3. Shadow-generate v3 copy beside the existing one-shot output.
4. Fact-check both.
5. Render the staged version only when all v3 contracts pass.
6. Canary by one domain, then expand.
7. Remove the filled JSON example only after v3 is stable.

### Risk

- Additional median latency.
- Cross-stage drift.
- Structured-output fallback.
- Planner producing ambitious but weakly evidenced arcs.

Mitigate with compact claim catalogues, local schema validation after every call, immutable plan IDs, per-stage retry budgets, and deterministic evidence eligibility.

---

## Change 4 — Turn the renderer into a typed layout compiler

### Design

Replace generic dictionaries plus regex recovery with:

```python
class RenderPlan(BaseModel):
    draft_id: UUID
    schema_version: int
    slides: tuple[CompiledSlide, ...]


class CompiledSlide(BaseModel):
    index: int
    shape: str
    family: str
    context: BaseModel
    required_assets: tuple[str, ...]
    hero_required: bool
```

Compilation:

```python
def compile_render_plan(
    carousel: CarouselV3,
    *,
    registry: FamilyRegistry,
    trusted_variants: Mapping[int, str] | None = None,
) -> RenderPlan: ...
```

The family mapping should follow the semantic table in §1.2. Each adapter translates typed fields into the existing template’s names—for example, dialogue turns into its current question/answer slots.

Every family contract must fail before Playwright if:

- a required field is absent;
- an array is outside its supported cardinality;
- a placeholder remains unresolved;
- a static asset is unavailable;
- the family is incompatible with the slide shape or role.

### Integration path

- Preserve `map_slide_to_family()` for v1.
- Add `compile_render_plan()` for v3.
- Freeze the compiled plan in the render manifest.
- Use the same plan for initial render and all critic rerenders.
- Restrict layout variants:
  - autonomous v3: registry-selected only;
  - trusted manual flow: compatible variant override;
  - historical v1: preserve current behavior.

The current manifest records topic, count, families, heroes, and palette but not schema, arc, or signature: [composer.py:1877–1891](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1877). Extend it with:

```text
schema_version
signature_hash
arc_id
hook_type
shape_sequence
family_sequence
render_plan_hash
```

### Migration and rollout

Enable rich families incrementally:

1. `fact_stack → evidence-carved`
2. `stat_card → stat-card-hero`
3. `status_list → dark-status-list`
4. `qa_dialogue → qa-dialogue`
5. `source_citation → source-citation`

For each family:

- create min/max cardinality fixtures;
- render representative long and short copy;
- run geometry, contrast, OCR, font, and logo gates;
- compare failure rates with the existing baseline;
- only then activate automatic routing.

### Risk

Rich families can increase render failures through copy density and asset requirements. The mitigation is not to relax visual QA; it is to make family capacity explicit upstream and reject impossible content before Playwright.

---

## Change 5 — Unify run identity, stage observability, and outcome feedback

### Design

Make `war_room_drafts.id` the canonical identity across selection, generation, rendering, review, publication, and metrics.

Reconcile the existing run table:

```sql
ALTER TABLE wr2_carousel_runs
    ADD COLUMN draft_id UUID;

CREATE UNIQUE INDEX ux_wr2_carousel_runs_draft_id
    ON wr2_carousel_runs (draft_id)
    WHERE draft_id IS NOT NULL;
```

Backfill only unambiguous matches. Do not infer identity from recurring topic text.

Persist typed stage artifacts separately:

```sql
CREATE TABLE wr2_generation_stages (
    draft_id UUID NOT NULL,
    attempt SMALLINT NOT NULL,
    stage TEXT NOT NULL CHECK (
        stage IN ('angle', 'structure', 'copy', 'polish')
    ),
    schema_version SMALLINT NOT NULL,
    prompt_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    output_json JSONB,
    validation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    latency_ms BIGINT,
    success BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (draft_id, attempt, stage)
);
```

Store typed decisions and violations, not hidden chain-of-thought or huge duplicated prompts.

Join published outcomes through:

```text
war_room_drafts.id
    → war_room_posts.draft_id
    → post_metrics_history.post_id
```

The metrics schema already retains post-level time series: [128_m13_feedback.sql:28–40](/Users/balizero/nuzantara/apps/backend-rag/backend/db/migrations_v2/128_m13_feedback.sql:28).

Add bounded portfolio scoring to the topic selector:

```python
def score_editorial_candidate(
    *,
    base_score: float,
    liveness: str,
    domain: str,
    recent_portfolio: PortfolioState,
) -> float:
    if liveness == "breaking":
        return base_score

    return (
        base_score
        + bounded_domain_balance_bonus(...)
        + bounded_hook_opportunity_bonus(...)
        + bounded_arc_opportunity_bonus(...)
    )
```

Outcome analysis can then answer:

- Which arcs earn saves versus superficial likes?
- Which hook types produce shares?
- Which layout mixes correlate with completion or rejection?
- Which combinations work by domain and liveness?
- Are novelty failures associated with lower performance?

### Integration path

1. Add `draft_id` to run identity and stop find-or-create-by-topic for new runs.
2. Record stage outputs and validation results.
3. Extend render manifests.
4. Join final outcomes to signatures.
5. Add portfolio novelty as a small selector tiebreaker.
6. Only after sufficient data, propose policy adjustments for human approval.

### Migration and rollout

- Logging first; no selection or prompt behavior changes.
- Validate that every published post resolves to one draft and signature.
- Add selector portfolio bonuses with a strict maximum contribution.
- Never auto-promote a winning formula directly into the prompt.
- Require minimum sample sizes by domain/liveness and preserve a deliberate exploration share.

### Risk

Optimizing directly for engagement can create clickbait, suppress necessary regulatory coverage, and rapidly refreeze a temporary winner. Keep facts, liveness, and human approval as primary objectives; treat engagement as bounded evidence, not the editorial constitution.

---

# 3. Recommended implementation sequence

The dependency-aware sequence is:

1. **Canonical IR and shared projections**
2. **Consumer migration: facts, language gates, images**
3. **Typed render compiler in shadow mode**
4. **Editorial-signature derivation and observational ledger**
5. **Staged planner/copy dual-run**
6. **Signature reservation and hard novelty enforcement**
7. **Family-by-family automatic routing**
8. **Identity reconciliation and outcome-aware portfolio scoring**

Release gates should include:

- 100% of reader-facing fields pass through the shared language gate.
- 100% of claim-bearing fields reach the fact extractor.
- Zero unresolved template placeholders.
- Zero cover/closer/source role violations.
- No regression in current geometry/OCR/font/logo QA.
- Render family decisions remain stable across rerenders.
- Every generated draft has a replayable plan, signature, schema version, and prompt/model identity.
- Known novelty violations never proceed merely with a warning.

---

# 4. What not to change

## Keep the facts-first park behavior

The generator correctly requires usable source material and parks drafts that lack it: [wr2_draft_generator.py:690–718](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:690), [wr2_draft_generator.py:1407–1419](/Users/balizero/nuzantara/scripts/wr2_draft_generator.py:1407).

Do not allow arc or layout ambitions to manufacture evidence.

## Keep generator and grader separate

Do not combine copywriting, fact checking, and visual criticism into one “super prompt.” Staging should separate responsibilities further. The copy model may self-check syntax, but it must not be the authority that certifies its own facts or render quality.

## Keep fixed boundary roles

A fixed branded cover and closer are useful constraints. The problem is that their current contracts disagree, not that they are fixed.

Make their role and shape immutable while allowing the hook, headline, subhead formula, and statement copy to vary within typed rules.

## Keep source credibility as a dedicated slot

For regulatory, visa, tax, and property work, the source slide should become structurally reachable—not be removed because it currently complicates routing.

## Keep the existing visual QA loop

Geometry, OCR, font, contrast, hero visibility, logo, and completeness gates are load-bearing. The typed compiler should fail earlier and make them more reliable; it should not replace them with model self-assessment. The current renderer gate bundle is centralized at [composer.py:1421–1428](/Users/balizero/nuzantara/scripts/wr2_html_renderer/composer.py:1421).

## Keep the layout library

The templates are not the primary disease. They already encode much of the richer visual language. Adapt the authoring contract and compiler before redesigning CSS or adding more families.

## Keep legacy heuristics during migration

The fact-stack parser, field aliases, and v1 router are necessary for historical drafts and rerenders. Isolate them behind `schema_version == 1`; do not delete them during the v3 rollout.

## Keep trusted manual overrides

Manual/historical rerendering may need an exact visual family. Preserve that capability behind a trusted marker and compatibility validation. Do not expose raw layout-family selection to autonomous generation.

## Keep observational logging fail-open

A failure to write post-render analytics must not invalidate a successful render. The new compose-time reservation is a separate control-plane operation and may gate generation; post-render telemetry should remain non-blocking.

## Keep human publication approval

Nothing in this restructuring justifies expanding autonomy to outward publication. The current ledger migration explicitly reflects manual publishing after rendering: [216_wr2_topic_type_log.sql:1–9](/Users/balizero/nuzantara/apps/backend-rag/backend/db/migrations_v2/216_wr2_topic_type_log.sql:1).

---

# Final judgment

WR2 should stop asking a model to “make a varied carousel” and start giving it a selected editorial contract that the system can verify.

The highest-leverage move is a typed intermediate representation shared by generation, fact checking, rendering, and QA. Once that exists:

- narrative arcs become selectable data;
- diversity becomes reservable state;
- rich layout families become reachable;
- repairs become local;
- outcomes become attributable;
- brand rules become executable rather than rhetorical.

Without that contract, additional prompt examples, stronger models, more layout families, and more “avoid sameness” language will continue to produce temporary surface variation followed by a new monoculture.

---

## 4. Sintesi incrociata e valutazione adozioni (Fable, final gate)

---

**Convergenza a tre famiglie.** I tre seat, con lenti e training indipendenti, convergono sulla stessa architettura: (1) contratto slide TIPIZZATO (Kimi M1 ≈ Codex Change 1 ≈ Gemini Instructor/BAML); (2) memoria editoriale come STATO interrogabile (Kimi M2 ≈ Codex Change 2); (3) split Planner→Writer con decisioni strutturali prese da codice con memoria, non dal modello (Kimi M4 ≈ Codex Change 3 ≈ Gemini gpt-newspaper/CrewAI-shape); (4) validatori deterministici post-generazione (Kimi M3/M9 ≈ Codex validators ≈ Gemini Vale/promptfoo). La convergenza cross-family è essa stessa evidenza (W100: l'accordo same-family mente; questo è l'opposto — accordo cross-family su prior diversi).

**Meta-lezione** (Kimi la formula meglio): ogni sistema maturo cura lo SPAZIO delle strutture e decide la struttura con macchinario stateful; il modello è brillante solo dentro uno slot assegnato. Il nostro register/tone lookback è la prova interna: l'unico asse con stato è l'unico che varia.

**ADOTTA ORA (Fase 1):**

- A1 · Carousel IR tipizzata (Codex Change 1) con slide-shape: prose, statement, fact_stack, qa_dialogue, status_list/timeline, stat_card, citation. Pattern Instructor/Pydantic SENZA SDK Anthropic (bannato): validazione+retry sul JSON del CLI OAuth. Include le projections condivise reader_texts()/claim_bearing_segments() che curano anche i finding C/D di Codex (fact extractor su dialetto sbagliato, language gates cieche ai campi ricchi).
- A2 · Creative Ledger (Kimi M2 / Codex Change 2, observational-first): signatures per draft (format, arc, hook_type, kicker, subhead_pattern, layout_families, register, palette, hero_concept_class), backfill dei 34 deck, lookback esteso. Il fix kicker/subhead di oggi (PR in volo) è il primo asse; il ledger li generalizza.
- A3 · Fix puntuali dai fresh-eyes Codex, indipendenti dall'IR: contratto closer unificato (il split-brain CTA è la causa della CTA assente — la FORMA del franchise slot è Zero-gated, la meccanica no); mismatch campi fact-extractor (index/title vs slide_number/headline); contraddizioni prompt (hero count 1-3 vs 4-8; warm-amber vs warm-ochre); coercizione truthy di "false" nel normalizer.
  **ADOTTA DOPO (Fase 2, dipende da A1/A2):**
- B1 · Arc grammar + Planner/Slot-Writer (Kimi M4/M5, Codex Change 3) con eligibility filter e liveness mode-switching (Kimi M6 — i tier esistono già e da stanotte fluiscono; oggi non pilotano nulla a valle del selector).
- B2 · Near-duplicate CI gate (Kimi M9) + suite eval promptfoo (Gemini) come regression-test del prompt.
- B3 · Vale style-as-code (Gemini) come firewall deterministico brand-voice (estende il take_label gate; sposa la cultura guard-conformance guilt+innocence).
  **METRICS-GATED (dopo n≥200, regola già stabilita):**
- C1 · Feedback bandit (Kimi M11) in shadow mode. C2 · Content matrix portfolio-aware nel selector (Kimi M12 / Codex I). C3 · Art-direction cards (Kimi M10) + Style Dictionary palette per tema.
  **RESPINTI (con motivo):**
- Postiz al posto dell'app review: viola il principio costituzionale app+codebase-un-organismo e il flusso Legge 5; l'app è shipped e funzionante.
- CrewAI come framework: adottiamo la DECOMPOSIZIONE, non il framework (lock-in; il nostro pattern è script+launchd+DB; 176 daemon già fragili).
- Swap del renderer (Satori/html-to-image): il loop Playwright+QA visuale è load-bearing e research-saturated (Codex: keep).
  **ZERO-GATED (Legge 5 / brand — decisioni da portare a Zero):**
- Franchise slot alla Axios (Kimi M8): "The Bali Zero read" come casa santificata dell'ex-"Our read" + closer "What we'd do" con CTA fissa — assorbe la patologia in un rituale di brand.
- All-caps body doctrine; palette rotation per tema; fit-policy cover (#2750); la scelta finale dei 6-8 archi.

---

## 5. Provenienza e file grezzi

- **Provenienza scratchpad (sessione 2026-07-20):** i tre report sorgente sono stati prodotti in una sessione di ricerca autonoma dedicata e depositati come file grezzi nello scratchpad di sessione:
  - Seat 1 (Kimi K3): `wr2_world_class_mechanisms_report.md` (340 righe) — dispacciato via `kimi -m kimi-code/k3`.
  - Seat 2 (Gemini 3.1 Pro High): `gemini_full_report.md` (161 righe, firmato in coda "Generated by Antigravity Research Agent — 2026-07-20") — dispacciato via `agy -p`.
  - Seat 3 (Codex GPT-5.6 sol, effort ultra): `codex_report.md` (1298 righe, marcato `[Air-M5]` in testa — eseguito sul checkout M5) — dispacciato via `codex exec -m gpt-5.6-sol -c model_reasoning_effort="ultra"`.
- **Verifica reuse-first (2026-07-20, live via `gh api`):** ogni repo citato nell'harvest OSS di Seat 2 è stato controllato contro lo stato reale di GitHub prima dell'inclusione in questo archivio — esiste 1 riga bloccata da DMCA (`therutvikp/OpenPolotno`, HTTP 451), 1 riga non trovata (`openpencil/openpencil`, HTTP 404, probabile allucinazione), 2 mismatch di licenza (GPT-Researcher dichiarato MIT ma è Apache-2.0; proselint dichiarato MIT ma è BSD-3-Clause), e 6 righe con org/owner spostato ma repo reale (Instructor→567-labs, Vale→vale-cli, CrewAI→crewAIInc, Outlines redirect confermato, Style Dictionary→style-dictionary org, GPT-Newspaper→rotemweiss57 e STALE da 2+ anni). Dettaglio riga-per-riga nella colonna "Verifica" della tabella in §2.
- **Contesto di consegna in parallelo:** la cura per il primo asse "frozen" (kicker/subhead con DB-lookback, lo stesso meccanismo che il register/tone axis già dimostra funzionare — vedi §0) è stata costruita e armata nello stesso giorno di questa ricerca, nel worktree `wr2-kicker-variety`, ed è al secondo round di red-team al momento dell'archiviazione di questo documento. Questo report ne è la cornice strategica: il fix di oggi è l'istanza-zero del pattern A2 (Creative Ledger) che la sintesi §4 raccomanda di generalizzare.
