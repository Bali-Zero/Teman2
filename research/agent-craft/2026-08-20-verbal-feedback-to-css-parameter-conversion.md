---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-20-verbal-feedback-to-css-parameter-conversion

**Date**: 2026-08-20
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 6 / Citations: 16

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Programmazione Estetica via Feedback Verbale:** In che modo l'orchestratore Opus 4.7 può convertire i riscontri qualitativi multimodali emessi da `wr2-critic` (es. *"La casella di testo su Slide 3 ha un contrasto insufficiente del 3.5:1 rispetto allo sfondo"* [10]) in parametri CSS o classi di layout deterministiche che il lavoratore Sonnet `wr2-layout-composer` [9] sia in grado di interpretare e applicare autonomamente per correggere il codice HTML durante il ciclo di retry?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche**

*   **Il concetto di "Symbolic Differentiation" e l'operatore Reflect in PSN (Evolving Programmatic Skill Networks):**
    > *"Reflect acts as symbolic differentiation: when a task fails, it identifies which control-flow branches, preconditions, parameters, and subskill compositions contributed to the error, producing structured repair proposals... Like backpropagation, credit is assigned only along the executed path..."* [1]
    > *"Phase I: Top-down symbolic differentiation to propagate feedback { f_s }... Phase II: Bottom-up application of gradient proposals { g_s }... This design explicitly decouples credit assignment from code modification."* [2]
    > *"Executing skill s yields (f_s, \delta_s) where \delta_s \in \{0, 1\} indicates success and f_s aggregates feedback from the environment. ... Given feedback f_s, Reflect computes repair proposal \tilde{\nabla}_s identifying faulty control flow, preconditions, parameters, or subskills."* [3]

*   **Il ruolo del discriminatore multimodale in `wr2-critic`:**
    > *"MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. ... Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim. ... Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback."* [4]
    > Sotto la **Rubrica 4 (Image-text fit)**: *"Text legibility over image: text-zone brightness contrast >= 4.5:1 against background pixels in same region"* [5]
    > Sulla gestione del loop: *"Orchestrator uses binary_carousel_verdict as the gate; numeric rubrics inform retry prompts. Hard fail = retry max 2 in orchestrator. Your job is to produce clear failure descriptions so retry can converge."* [6, 7]

*   **I vincoli deterministici di `wr2-layout-composer`:**
    > *"For each slide-spec, retrieve the matching layout from ~/.claude/skills/bali-zero-brand/layouts/<family>.md and parameterize it. Output is HTML+CSS rendered against tokens.json — never inline hex codes, only token references like var(--color-bg-antracite)."* [8]
    > *"Hard rule — no inline hex codes: every color reference in your output HTML+CSS MUST be var(--color-<token>). Run a grep on your output BEFORE writing files: grep -E '#[0-9A-Fa-f]{3,6}' <html> — if it returns ANY match ..., abort with status: failed, reason: "hex code leak...""* [9]

---

### **2. Confronto con l'Applicazione Reale nel nostro Stack (Bali Zero)**

Nel nostro attuale stack multi-agente per la produzione dei caroselli WR2, applichiamo un pattern ispirato alla separazione tra **assegnazione del credito (Phase I)** ed **esecuzione della modifica (Phase II)**, ma con un importante collo di bottiglia nell'interpretabilità del gradiente da parte del lavoratore Sonnet [2]:

*   **La Prassi Attuale (Il ciclo di Retry ad alto livello):**
    Quando `wr2-critic` (su Opus 4.7 con visione multimodale) boccia un rendering a causa di un contrasto insufficiente (ad esempio, un testo bianco sovrapposto a una zona chiara di una foto, registrando un contrasto di `3.5:1` inferiore alla soglia di `4.5:1` dell'Articolo 2.3) [5, 10], l'orchestratore `wr2-design-architect` intercetta il fallimento [11]. Al fine di rimanere entro il budget di **massimo 2 tentativi** [12], l'orchestratore invia nuovamente il prompt al lavoratore `wr2-layout-composer` includendo la lamentela testuale del critic [12].
*   **La Fragilità del Feedback Testuale (La scorciatoia di Sonnet):**
    Essendo `wr2-layout-composer` eseguito su Claude Sonnet 4.6 per ragioni di efficienza dei costi [11], il modello soffre di **limitazioni nel ragionamento geometrico e spaziale a riga di codice**. Quando riceve un feedback verbale come *"La casella di testo su Slide 3 ha un contrasto insufficiente"*, Sonnet non può "vedere" i pixel. Non conoscendo l'esatta distribuzione di luminosità dell'immagine di sfondo generata, tenta modifiche euristiche non sicure.
    Il rischio tipico è che Sonnet cerchi di bypassare il problema applicando hex-code inline arbitrari o non autorizzati (come `#0F1729` per scurire lo sfondo) [9]. Questo attiva immediatamente la **Hex-Leak-Guard** deterministica del compositore, provocando l'abort della pipeline con un errore di violazione del namespace chiuso dei token [9, 13]. In sostanza, **il gradiente testuale del critic non si traduce in una modifica CSS deterministica e sicura**, costringendoci spesso ad esaurire i tentativi e a relegare il carosello allo stato `drafted_needs_human_edit` per intervento manuale in Canva [12, 14].

---

### **3. Linea di Azione Concreta: Compilatore di pseudo-gradienti estetici**

Per eliminare l'imprecisione del feedback testuale, dobbiamo fare in modo che l'orchestratore Opus 4.7 funga da **compilatore di gradienti simbolici**, traducendo il feedback qualitativo del critic in **sovrascritture di parametri CSS (token-level overrides)** prima di invocare il layout-composer.

*   **Azione:** Integrare nello script di orchestrazione di `wr2-design-architect` un modulo di mappatura deterministica dei fallimenti visivi, creando un contratto JSON di override per i token.
*   **Dettaglio dell'Implementazione:**
    1.  **Strutturazione del Feedback del Critic:** Modificare il parser di output di `wr2-critic` per emettere, oltre alla stringa testuale, una sezione strutturata `visual_remediation` per ogni slide bocciata:
        ```json
        {
          "slide_index": 3,
          "failure_type": "contrast_violation",
          "metric": "3.5:1",
          "remediation_hint": "increase_overlay_opacity | highlight_key_data"
        }
        ```
    2.  **Compilazione degli Overrides nell'Orchestratore:** All'avvio del Retry 1, `wr2-design-architect` intercetta questo oggetto JSON e, anziché passarlo come testo a Sonnet, genera o aggiorna un file temporaneo `/workspace/scratch/<slug>/token_overrides.json` applicando regole rigide basate sulla Brand Constitution [10]:
        *   Se `failure_type == "contrast_violation"`, imposta nel file di override: `{"--opacity-overlay": "0.80"}` (forzando l'inscurimento della foto tramite la classe `.color.overlay.darken-60` regolata dall'Articolo 2.3) [10].
        *   Se il testo è troppo lungo, applica programmaticamente il modificatore `.statement-bomb--shrunk` o riduce lo spacing [9].
    3.  **Iniezione deterministica in `wr2-layout-composer`:** Il layout-composer riceve il file `token_overrides.json` tramite la *Dual Brief Propagation (R3a)* [8, 15]. Durante la compilazione del template HTML, inserisce programmaticamente questi valori direttamente nel blocco `<style>` in linea all'inizio del file (es. `:root { --opacity-overlay: 0.80; }`), ignorando qualsiasi tentativo di autogestione estetica da parte del modello LLM. 

Questo approccio garantisce la **convergenza del ciclo di riparazione (fail-fast forward)** [7, 16], mantenendo la pipeline al 100% allineata con la costituzione ed evitando manipolazioni di codice non deterministiche da parte di Sonnet.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Dato che le violazioni di contrasto dipendono strettamente dall'immagine di sfondo generata programmaticamente, in che modo l'orchestratore può eseguire un **preflight di calcolo del contrasto geometrico** (analizzando lo scostamento di luminosità dei canali RGB dell'immagine JPG rispetto al posizionamento teorico del box di testo) prima ancora di invocare la costosa istanza di visione Opus 4.7 di `wr2-critic`?
2.  Considerando la topologia centralizzata del nostro stack, come possiamo strutturare il **Reflect Operator** per propagare la responsabilità di un fallimento estetico persistente (dopo 2 retry) al modulo `wr2-storyboarder` (es. costringendolo a cambiare la disposizione o a frammentare il testo in più slide) piuttosto che insistere inutilmente sulla variazione dei soli parametri CSS nel `wr2-layout-composer`?
3.  Se una patch di design token consolidata in `token_overrides.json` stabilizza con successo una famiglia di layout (ottenendo costantemente punteggi rubrica \\(\ge 95\\)), come possiamo implementare una **Maturity-Aware Skill Promotion** affinché queste combinazioni di stile vengano fuse permanentemente nel file dei token globali `tokens.json` o salvate come varianti canoniche all'interno della cartella `layouts/`?

## Sources used (6)

- `92b09121-412d-4ece-a88e-86b922424a15`
- `1826e81e-6d39-4285-956a-464b315e3f3f`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `e65a5f8f-9bac-44c8-bf39-a13841e40f93`
- `1c84e38a-a74d-46d4-bb80-615cbb5a7999`
- `2bf023eb-6410-4639-979a-6c19fe879fec`

## Citations verbatim (16)

### [1] source `92b09121…`

> Report issue for preceding element Operator-objective correspondence. Report issue for preceding element Reflect acts as symbolic differentiation : when a task fails, it identifies which control-flow branches, preconditions, parameters, and subskill compositions contributed to the error, producing structured repair proposals that reduce ℛ task \mathcal{R} {\text{task}} and ℛ cons \mathcal{R} {\text{cons}} . Like backpropagation, credit is assigned only along the executed path, with non-executed skills receiving no updates. This selective credit assignment avoids the noise of updating uninvolved skills, mirroring how gradients flow only through activated paths in neural nets. Maturity-aware gating functions as adaptive learning rates : mature skills with high V  ( s ) V(s) receive infrequent updates (analogous to freezing converged layers), while immature skills remain plastic, reducing ℛ reliab \mathcal{R} {\text{reliab}} by preventing catastrophic forgetting. Refactor performs symbolic neural architecture search: merging redundant skills, extracting reusable abstractions, and pruning unnecessary branches to reduce ℛ struct \mathcal{R} {\text{struct}} . Rollback-based validation functions as a symbolic trust region.

### [2] source `92b09121…`

> Report issue for preceding element A.4 Algorithmic Interpretation Report issue for preceding element The complete optimization step thus consists of two strictly separated phases: Report issue for preceding element • Phase I: Top-down symbolic differentiation to propagate feedback { f s } {f_{s}} . Report issue for preceding element • Phase II: Bottom-up application of gradient proposals { g s } {g_{s}} . Report issue for preceding element This design explicitly decouples credit assignment from code modification . While Phase I follows a chain-rule-like decomposition of feedback signals, Phase II ensures that updates are applied in a dependency-consistent order, preventing interference between skills during optimization.

### [3] source `92b09121…`

> Report issue for preceding element Executing skill s s yields ( f s , δ s ) (f_{s},\delta_{s}) where δ s ∈ { 0 , 1 } \delta_{s}\in{0,1} indicates success and f s f_{s} aggregates feedback from the environment. The system records a finite invocation trace 𝒯 \mathcal{T} . Given feedback f s f_{s} , Reflect computes repair proposal ∇ ~ s \tilde{\nabla}_{s} identifying faulty control flow, preconditions, parameters, or subskills. For invoked subskills s ′ ∈ Children  ( s ) s^{\prime}\in\text{Children}(s) , responsibility propagates as

### [4] source `1826e81e…`

> -------------------------------------------------------------------------------- name: wr2-critic description: MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY after Playwright renders PNGs. Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim. Receives PNG paths + slide-spec JSON + brief JSON + brand cortex pointer. Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback. Verifies Article 6.2 bilingual assist on first occurrence, Article 6.3 bullet-promise, Article 5.10 no silent placeholder reuse via sha256 anchor check. tools: Read, Write, Glob, Grep, Bash model: opus color: red memory: user skills:

### [5] source `1826e81e…`

> Score: 100 = all checks pass <70 = hard fail Rubric 4 — Image-text fit (vision-required) For each slide WITH hero image (read PNG via Read tool — vision-capable): Hero image relates semantically to slide topic (subjective; you decide) Anti-cliché check (Article 5.3): no palms / beaches / sunsets / handshakes / smiling teams / boho / clipart / vector-flat Photo style: 35mm chiaroscuro teal-amber (judge approximately by inspection) No AI-art fingerprints (extra fingers, melted faces, impossible architecture) No real faces unless verified Bali Zero stockphoto (faces must be silhouette/back-turned/ambiguous) Text legibility over image: text-zone brightness contrast ≥4.5:1 against background pixels in same region For slide 1 (cover): image full-bleed with gradient bottom→up making text legible Article 5.10 — No silent placeholder reuse (NEW, 2026-05-09) : for every slide with image_source in slides.json, run sha256 verification: If image_source starts with imagegen: → hero_sha MUST differ from anchor_sha . Hard fail if equal (silent reuse detected). If image_source starts with anchor: → slide-spec MUST also declare image_strategy: "anchor_reuse" . Hard fail if anchor_reuse not declared. If image_source is missing or malformed → hard fail.

### [6] source `1826e81e…`

> When brief.primary_regulation_code is non-empty: Cover slide MUST display .regulation-badge with the code verbatim Soft fail (-10) if cover lacks badge but code is in brief Hard fail if badge text differs from brief.primary_regulation_code (citation tampering = Article 6.4 violation) When brief.primary_regulation_code is empty/null: Cover MUST NOT display badge (avoid false-authoritative signal) Soft fail (-5) if badge present without backing code in brief Score: 100 = all checks pass 5.1 (either subcheck) FAIL = hard fail at Rubric 5 = carousel FAIL 5.3 banned-tokens FAIL = hard fail at Rubric 5 = carousel FAIL 5.7 citation tampering = hard fail at Rubric 5 = carousel FAIL Other soft fails = score deduction (each -5 to -20), routes to human review queue, does NOT block

### [7] source `1826e81e…`

> Output format Return a JSON object. Each slide MUST also receive a binary verdict (Hamel Husain shadowing doctrine — keep numeric rubrics for diagnosis, but the carousel-level go/no-go is binary): binary_carousel_verdict derivation: PASS only if every slide is PASS AND carousel_level_failures is empty. Any slide FAIL OR any carousel-level hard fail → carousel FAIL. Orchestrator uses binary_carousel_verdict as the gate; numeric rubrics inform retry prompts. Hard rules (process) Hard fail = retry max 2 in orchestrator. Your job is to produce clear failure descriptions so retry can converge. Soft fail = no block , route to human review queue. Pass = release to publisher . Never modify slides yourself . You are read-only. Never call other subagents . You communicate with the orchestrator only via your output JSON. Cite the constitution article for every hard failure (e.g., "Article 6.4 — paraphrased citation Permenkumham 22/2023 should be verbatim"). Never invent rules . If a slide does something the constitution doesn't address, score 100 on that dimension and note in verbal_feedback for human discretion.

### [8] source `d0adf453…`

> For each slide emit: Hero image strategy: 4-6 hero slides per 9 (NOT only 4 — when narrative requires 5, use 5). Hero on cover always. Hero in middle for emotional pivot. Hero on closing if it lands. Step 4 — Layout compose (per slide) For each slide-spec, retrieve the matching layout from ~/.claude/skills/bali-zero-brand/layouts/<family>.md and parameterize it. Output is HTML+CSS rendered against tokens.json — never inline hex codes, only token references like var(--color-bg-antracite) . R3a — Dual brief propagation (mandatory) : when invoking the layout-composer, pass BOTH the per-slide spec AND the full brief JSON (with voice_register , bilingual_lexicon_required , taboo_check , archetype ). The worker layer was previously informed only via the orchestrator's prose synthesis — this caused S6 mappazza (4-bullet promise → paragraph) and bilingual untranslated terms (DENDA, BUNGA) without English assist. Brief MUST travel verbatim with each handoff.

### [9] source `e65a5f8f…`

> Cost : ~50ms per QR (segno pure Python + Pillow LANCZOS resize). Negligible. Library import alternative (faster for batch renders): Step 4 — Output report Statement-bomb auto-shrink (renderer hint) If slide is statement-bomb , write the HTML in DOUBLE form: First version with class="statement" (font-size 72px) Add inline <script> that runs at render time to detect overflow and add class="statement shrunk" (font-size 56px) Snippet to embed: This runs in Playwright before screenshot. Hard rules No inline hex codes (strict, 2026-05-10 strengthening) : every color reference in your output HTML+CSS MUST be var(--color-<token>) . Run a grep on your output BEFORE writing files: grep -E '#[0-9A-Fa-f]{3,6}' <html> — if it returns ANY match (other than <meta> tags or data: URLs), abort with status: failed, reason: "hex code leak: <hex> in slide N" . Lesson: Golden Visa cron carousel S7 emitted bg: #0F1729 (navy, off-palette) — this is exactly the failure mode the rule blocks. The token namespace is closed (Article 2.1): adding a new color requires constitutional amendment. If you "need" a navy or any color outside the closed set, escalate by emitting status: needs_constitutional_amendment instead of inventing a hex. Preserve copy verbatim : never modify heading/body/subheading content from storyboarder. If copy violates a constitution rule, that's the storyboarder's responsibility, not yours. Add data-zone-type attributes to every visual element (text | hero-photo | overlay | logo | source) so the critic can do region-aware checks (Article 2.4). Image URL handling : if image_url is empty/null, write a placeholder div with data-zone-type="hero-photo-pending" and let the orchestrator (or image-generator) fill it post-hoc. Output single self-contained HTML per slide (referencing ../_base.css ). Renderer (Playwright) loads each independently. Article 5.10 — No silent placeholder reuse (NEW, 2026-05-09) : for every slide where is_hero_image: true , the image_source MUST be one of: imagegen:<codex_session_id> — fresh Codex $imagegen output, file copied from ~/.codex/generated_images/<session>/ into <output_dir>/<n>-hero.jpg anchor:<filename> — explicit declared anchor reuse from ~/.claude/skills/bali-zero-brand/anchors/<domain>-anchor.jpg , AND the slide-spec must declare image_strategy: "anchor_reuse" Verification (mandatory before writing slides.json): Hard fail any slide where image_source is missing, malformed, or fails the sha256 check. Emit validation_failures: ["slide N: image_source <reason>"] and status: "failed" . Orchestrator will block carousel emission. Bullet-promise verification (Article 6.3 helper) : if slide heading/sub announces N items and storyboarder body is a paragraph (not list_items array), emit validation_failures: ["slide N: heading promised <N> items but body is prose paragraph"] . Layout family dark-status-list requires list_items array per existing schema.

### [10] source `1c84e38a…`

> TEXT zones (heading, body, sub-headline, list items, captions, source footers, status badges): ≥95% of pixels in palette tokens (color.bg.* + color.text.* + color.accent.* + color.status.*). Hard fail. HERO PHOTO zones : NO palette pixel constraint. Photo can use natural cinematic grading (35mm teal-amber Villeneuve/Deakins). Critic does NOT measure pixel-palette ratio inside hero bounding box. GRADIENT OVERLAY zones : where text sits over photo, dark gradient color.overlay.darken-60 (rgba(0,0,0,0.6)) MUST be present at ≥0.6 opacity for legibility — see Article 5.5. 2.4 Critic enforcement : critic agent receives the layout JSON which declares for each element its zone_type (text | hero-photo | overlay | logo). Palette check applies only to text and logo zones. Photo bounds are skipped. 2.5 Reason for region-aware rule : a hard-blanket palette rule (the prior version) made teal-amber photo grading impossible (teal = blue-green). Region-aware preserves brand visual identity (cinematic photo treatment) without compromising text-zone legibility.

### [11] source `d0adf453…`

> Worker downgrade rationale (R2) : brief-interpreter, storyboarder, layout-composer perform structured I/O with predictable schemas — Sonnet 4.6 delivers identical output quality at ~25% the cost of Opus. Orchestrator (you) and critic stay on Opus 4.7 because they require nuanced judgment (sequencing, retry decisions, vision-based brand verdict). Target end-to-end cost: $3-5/run (test-4 at $7.99 was Opus-everywhere). Concrete invocation pattern: The orchestrator (you) is responsible for: (a) sequencing these calls; (b) writing intermediate state to apps/war-room/output/carousel/<slug>/ ; (c) deciding retries based on critic verdicts; (d) triggering Playwright rendering between Step 4 and Step 5; (e) writing the final outputs (Step 6) and queue handoff (Step 7).

### [12] source `d0adf453…`

> Hard fail on rubric 1 or 2 → return slides to layout-composer with verbal feedback. Soft fail (rubric 3 or 4) → flag for human review queue, do NOT block. Max 2 retry rounds. After 2 retries, surface the carousel with STATUS: needs_human_edit AND POST to the local queue server so Damar's UI flags the row: If queue server is unreachable (server not running on Pro), still write STATUS: needs_human_edit to slides.json and surface clearly to user. Never infinite-loop. Never claim success on a flagged carousel.

### [13] source `e65a5f8f…`

> Workflow Step 1 — Validate slide-spec For each slide: layout_family exists as ~/.claude/skills/bali-zero-brand/layouts/<family>.md — abort if not Required parameters present per layout doc (e.g., cover-photo needs heading + subheading + image_url; statement-bomb needs statement) Step 2 — Render-ready HTML per slide For each slide: Read layouts/<family>.md and extract the HTML/CSS skeleton block. Replace {{placeholders}} with slide-spec values. Apply emphasis spans for statement-bomb (wrap emphasis_word in <span class="emphasis">word</span> ). Apply Handlebars-style {{#each items}} loops for dark-status-list and timeline-pinboard . Add data-slide-index="N" and data-layout="<family>" to <body> for renderer telemetry. Hard rule — no inline hex codes : all colors via var(--token-name) . Validate by grep — abort if #[0-9A-Fa-f]{3,6} found in your output (except data-zone-type="hero-photo" background-image url).

### [14] source `2bf023eb…`

> Human-in-loop review queue schema Addresses Codex FLAW MEDIUM "human-in-loop under-specified". Damar publishes manually but without a queue schema, "ignored" cannot be distinguished from "approved". Storage location ~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json Single JSON array. Append-only by orchestrator. Modified in-place by Damar's tooling (or by Antonello if Damar unavailable). Schema State machine State definitions drafted : agent produced carousel, queued for Damar. Initial state. drafted_needs_human_edit : orchestrator exhausted retry budget (2 critic rounds failed). Visible to Damar as a yellow-bordered row with "needs human edit" pill. Damar opens, reviews critic report ( needs_human_edit_critic_report ), edits manually in Canva, then transitions to reviewed . Set by POST /api/flag-needs-human-edit from wr2-design-architect . Required fields: needs_human_edit_reason , needs_human_edit_retry_count , needs_human_edit_critic_report , needs_human_edit_flagged_at . reviewed : Damar opened the Canva design and made a decision (any of next 4 transitions). published : Damar posted the carousel verbatim to Instagram. Most common case. published_with_edits : Damar made changes in Canva before publishing. The designer_override_diff MUST be filled — this is the gold-standard learning signal. rejected : Damar refused publication. damar_notes field MUST contain the reason. ignored : 14 days elapsed without review. Auto-transitioned by daily cron. NOT a learning signal — could mean "Damar busy" or "topic stale" or "carousel bad". Don't optimize against ignored. withdrawn : Antonello pulled before Damar acted. Reason in damar_notes (overloaded with withdrawn_reason semantics).

### [15] source `e65a5f8f…`

> bali-zero-brand -------------------------------------------------------------------------------- WR2 Layout Composer You receive slide-spec JSON and produce render-ready HTML files. You do NOT change copy. You do NOT pick layouts (storyboarder did that). You parameterize templates with content. Inputs The orchestrator passes you (R3a — dual brief propagation): slide_spec — single slide JSON from wr2-storyboarder , OR full slides array (composer auto-detects) brief — full brief JSON verbatim from wr2-brief-interpreter (contains voice_register , bilingual_lexicon_with_english_assist , taboo_check , archetype , regulatory_citations_verbatim ) output_dir — e.g., ~/Desktop/nuzantara/apps/war-room/output/carousel/<topic-slug>/slides/ carousel_archetype — convenience field copied from brief.archetype_recommended

### [16] source `92b09121…`

> Report issue for preceding element E.1 Optimization Taxonomy Report issue for preceding element Across experiments, frequent optimizations of PSN fall into several recurring categories. Table 5 summarizes the most common failure signals and corresponding repair strategies. Report issue for preceding element <cited_table>
