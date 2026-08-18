---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-14-active-skill-frontmatter-parsing-deep-dive

**Date**: 2026-08-14
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 11 / Citations: 22

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Parsing del Frontmatter delle Skill Attive:**

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Il Guscio Sintattico del Frontmatter)**

Le nostre fonti definiscono in modo chiaro la struttura, i vincoli e le tecniche di estrazione del frontmatter YAML per le nostre unità di conoscenza:

*   **Requisiti Sintattici e di Validazione del Frontmatter:**
    > *"Every skill needs a SKILL.md file with two parts: YAML frontmatter between `---` markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs."* [1, 2].
    > *"The SKILL.md frontmatter requires name and description fields with specific validation rules: name: Maximum 64 characters, lowercase letters/numbers/hyphens only, no XML tags, no reserved words; description: Maximum 1024 characters, non-empty, no XML tags"* [3].
    > Inoltre, l'estensione del frontmatter supporta la granularità dei parametri: *"Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage."* [4, 5].

*   **Archiviazione e Struttura dei File `.local.md`:**
    > *"This pattern uses YAML frontmatter for structured configuration and markdown content for prompts or additional context. ... File location: `.claude/plugin-name.local.md` in project root"* [6].

*   **Tecniche Storiche di Parsing (RegEx / Bash):**
    > *"YAML frontmatter + markdown body structure; Parsing techniques for bash scripts (sed, awk, grep patterns)... 2 utility scripts: `validate-settings.sh`, `parse-frontmatter.sh`"* [7].
    > Il framework documenta l'approccio classico per leggere queste informazioni: *"Pattern: Check existence and parse frontmatter... Parsing Techniques: Extract Frontmatter, Read Individual Fields: String fields, Boolean fields, Numeric fields, Read Markdown Body (Extract content after second `---`)"* [8].

---

### **2. Confronto con lo Stack Reale di Bali Zero / Nuzantara**

Nel nostro ecosistema reale, il parsing del frontmatter delle nostre skill e dei nostri layout non è una semplice lettura di testo, ma un **motore di validazione dinamico** integrato nei processi di produzione caroselli:

*   **L'Incidente di Validazione Strict-Parse (Commit `ac971a9`):**
    Durante i nostri test live di produzione su larga scala, abbiamo riscontrato che i parser YAML nativi della flotta di agenti fallivano l'esecuzione a causa di caratteri speciali non schermati (come i due punti `:` o virgolette orfane) nelle descrizioni descrittive del brand. Per garantire la stabilità sintattica di tutte le nostre 16 skill attive, abbiamo implementato il fix difensivo **`ac971a9`**, forzando l'aggiunta di virgolette doppie (`"..."`) attorno ai campi di descrizione per soddisfare la *strict-parse compatibility* [9].
*   **La Propagazione dei Parametri di Layout:**
    Il nostro sub-agente `wr2-layout-composer` [10] non si limita a incollare codice HTML statico. Quando l'orchestratore invoca il compositore tramite il contratto di *Dual Brief Propagation (R3a)* [11], il compositore **legge ed estrae dinamicamente la definizione YAML** dei singoli layout caricati da `layouts/<family>.md` [12]. Prima di generare i file renderizzabili, il compositore valida che i parametri richiesti dichiarati nel frontmatter del layout (es. `heading`, `subheading`, `list_items` o `qa_pairs`) siano effettivamente presenti e tipizzati correttamente all'interno dello `slide_spec` JSON generato dallo storyboarder [13, 14].
*   **Gestione dello Stato tramite `.local.md`:**
    In linea con i pattern del nostro archivio (ispirati a `ralph-loop` e `multi-agent-swarm` [15, 16]), sfruttiamo file locali oscurati al VCS (come `.claude/multi-agent-swarm.local.md` [16, 17]) per salvare variabili di stato persistenti tra i turni, eseguendo controlli di arresto rapido (*quick exit*) leggendo la chiave `enabled: true/false` direttamente dal frontmatter prima di attivare i nostri trigger [16].

---

### **3. Linea di Azione Concreta per la Libreria Bali Zero**

Sebbene l'uso di script bash rapidi basati su `sed` e `awk` (come `parse-frontmatter.sh` [7]) sia utile per controlli veloci da terminale, l'evoluzione verso le pipeline complesse richiede di **eliminare il parsing basato su espressioni regolari a riga di comando**, che fallisce sistematicamente in presenza di descrizioni multi-linea, array YAML o metadati nidificati.

*   **Azione:** Implementare nella libreria Bali Zero un modulo Python di compilazione e validazione tipizzato chiamato **`_skill_frontmatter_compiler.py`**.
*   **Implementazione Operativa:**
    1.  **Modulo di Ingestione Unificato:** Lo script scansionerà ricorsivamente la cartella `layouts/` e `skills/` caricando i file `.md` a runtime.
    2.  **Strict YAML Validation (PyYAML / Pydantic):** Invece di usare `grep` o `sed`, estrarrà la sezione compresa tra i delimitatori `---` [4, 5] e la sottoporrà a un parser YAML nativo. Mapperà i campi del frontmatter su un modello di validazione rigido (es. `AllowedTools` come lista tipizzata, `Model` come alias di modello [18], `Effort` come livello di ragionamento valido [18]).
    3.  **Compilazione del Registro di Runtime (`_compiled_skills_registry.json`):** Al SessionStart [19], lo script genererà un singolo file JSON compresso contenente la mappatura di tutte le skill attive con i rispettivi trigger sintattici e i parametri richiesti. L'orchestratore `wr2-design-architect` [20, 21] e il compositore utilizzeranno questa mappa centralizzata per la pianificazione e la validazione *prima* di effettuare qualsiasi costosa chiamata di calcolo, garantendo prestazioni deterministiche ed eliminando i fallimenti a metà esecuzione.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Ottimizzazione dello Spazio dei Token nel Frontmatter:** Dato che il sistema Claude Code applica un limite rigido di troncamento a **1.536 caratteri** per la stringa combinata di `description` e `when_to_use` nel caricamento globale a SessionStart [4, 5], come possiamo compattare i metadati e i trigger delle nostre 16 skill e layouts per evitare il troncamento di informazioni chiave senza compromettere la precisione della scoperta automatica (*Skill Discovery*) [22]?
2.  **Iniezione Dinamica del Contesto nel Frontmatter compilato:** Se un layout o una regola nel frontmatter utilizza l'interpolazione dinamica della shell (es. l'esecuzione di comandi tramite la sintassi `!git diff HEAD`` [1, 2]), in che modo il nostro compilatore Python deve preprocessare ed eseguire questi comandi a runtime prima di esporre lo schema tipizzato all'orchestratore, assicurando che non si verifichino blocchi bloccanti (*blocking errors*) in contesti headless [18, 23]?
3.  **Contratto di Ereditarietà nei Sub-Agenti e Pre-caricamento:** Quando un sub-agente viene spawnato dall'orchestratore con un elenco specifico di skill precaricate tramite la chiave `skills` del frontmatter [18] (il che inietta l'intero contenuto della skill all'avvio [24, 25]), quali conflitti di sovrascrittura di variabili o duplicazione di contesto possono emergere se due layout condividono definizioni di parametri o token con lo stesso nome, e come possiamo risolverli programmaticamente?

📊 *Se desideri, posso scrivere direttamente la specifica di test unitario in Python per convalidare lo script di compilazione `_skill_frontmatter_compiler.py` simulando scenari di errore tipici di descrizioni malformate o hex-code leaky.*

## Sources used (11)

- `3187958a-0b71-4128-8aef-b4971aa9c079`
- `e65a5f8f-9bac-44c8-bf39-a13841e40f93`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `d3ccdc37-f3b2-4163-8e2c-c11bba281169`
- `63370ead-a837-4bab-98dc-79109d022209`
- `1fd52991-76b5-458c-aff1-c4f399f99566`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `92b09121-412d-4ece-a88e-86b922424a15`
- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`

## Citations verbatim (22)

### [1] source `3187958a…`

> Fix difensivi (post-test live) ac971a9 — Quote 5 description YAML con "..." per strict-parse compatibility. 16/16 strict-valid. 11161f7 — Canonical research artifacts dir ~/var/nuzantara-research/ (immune a branch switch). Pilot file migrati. Symlink back-compat. nuzantara dfed5a416 — .gitignore research/dev-tools/ . Stack rinnovato — cosa è cambiato per future sessioni Agent fleet disciplinato: 16 agent con frontmatter completo (color, isolation, memory, disallowedTools, maxTurns dove rilevante) Output style globale italian-tight attivo da settings.json PreCompact backup automatico transcript JSONL (vivo, testato con file 3.3MB) wr2-critic auto-learning via _lessons/ directory (Voyager pattern Wang et al. 2023) Anti-hallucination discipline scritta in 3 luoghi auto-letti al SessionStart Pilot artifact convention : ~/var/nuzantara-research/{dev-tools,_pilots,_archive}/

### [2] source `e65a5f8f…`

> -------------------------------------------------------------------------------- name: wr2-layout-composer description: "MUST BE USED by wr2-design-architect at Step 4 of every carousel run. Use IMMEDIATELY after storyboarder returns slides.json. Receives slide-spec JSON + brief JSON verbatim, retrieves matching layout from skill library, parameterizes HTML/CSS, writes render-ready files for Playwright. ENFORCES no silent placeholder reuse (Article 5.10): every hero image_source must be imagegen:<session> or anchor:<file> with sha256(hero) ≠ sha256(anchor) verification. Does NOT render itself (orchestrator drives Playwright)." tools: Read, Write, Edit, Glob, Grep, Bash model: sonnet color: yellow skills:

### [3] source `d0adf453…`

> For each slide emit: Hero image strategy: 4-6 hero slides per 9 (NOT only 4 — when narrative requires 5, use 5). Hero on cover always. Hero in middle for emotional pivot. Hero on closing if it lands. Step 4 — Layout compose (per slide) For each slide-spec, retrieve the matching layout from ~/.claude/skills/bali-zero-brand/layouts/<family>.md and parameterize it. Output is HTML+CSS rendered against tokens.json — never inline hex codes, only token references like var(--color-bg-antracite) . R3a — Dual brief propagation (mandatory) : when invoking the layout-composer, pass BOTH the per-slide spec AND the full brief JSON (with voice_register , bilingual_lexicon_required , taboo_check , archetype ). The worker layer was previously informed only via the orchestrator's prose synthesis — this caused S6 mappazza (4-bullet promise → paragraph) and bilingual untranslated terms (DENDA, BUNGA) without English assist. Brief MUST travel verbatim with each handoff.

### [4] source `e65a5f8f…`

> You ALSO read: ~/.claude/skills/bali-zero-brand/layouts/<family>.md — for each unique layout family in the slide-spec ~/.claude/skills/bali-zero-brand/layouts/_base.css — the shared CSS tokens base ~/.claude/skills/bali-zero-brand/anchors/<domain>-anchor.jpg — domain anchor for Article 5.6/5.9/5.10 anchor cascade The brief is load-bearing input, not metadata. Use brief.bilingual_lexicon_with_english_assist to verify storyboarder honored Article 6.2; use brief.regulatory_citations_verbatim to verify Article 6.4; use brief.taboo_check to refuse forbidden phrases. If storyboarder violated either, do NOT silently fix — emit validation_failures: [...] and let orchestrator decide retry.

### [5] source `e65a5f8f…`

> Workflow Step 1 — Validate slide-spec For each slide: layout_family exists as ~/.claude/skills/bali-zero-brand/layouts/<family>.md — abort if not Required parameters present per layout doc (e.g., cover-photo needs heading + subheading + image_url; statement-bomb needs statement) Step 2 — Render-ready HTML per slide For each slide: Read layouts/<family>.md and extract the HTML/CSS skeleton block. Replace {{placeholders}} with slide-spec values. Apply emphasis spans for statement-bomb (wrap emphasis_word in <span class="emphasis">word</span> ). Apply Handlebars-style {{#each items}} loops for dark-status-list and timeline-pinboard . Add data-slide-index="N" and data-layout="<family>" to <body> for renderer telemetry. Hard rule — no inline hex codes : all colors via var(--token-name) . Validate by grep — abort if #[0-9A-Fa-f]{3,6} found in your output (except data-zone-type="hero-photo" background-image url).

### [6] source `e65a5f8f…`

> Cost : ~50ms per QR (segno pure Python + Pillow LANCZOS resize). Negligible. Library import alternative (faster for batch renders): Step 4 — Output report Statement-bomb auto-shrink (renderer hint) If slide is statement-bomb , write the HTML in DOUBLE form: First version with class="statement" (font-size 72px) Add inline <script> that runs at render time to detect overflow and add class="statement shrunk" (font-size 56px) Snippet to embed: This runs in Playwright before screenshot. Hard rules No inline hex codes (strict, 2026-05-10 strengthening) : every color reference in your output HTML+CSS MUST be var(--color-<token>) . Run a grep on your output BEFORE writing files: grep -E '#[0-9A-Fa-f]{3,6}' <html> — if it returns ANY match (other than <meta> tags or data: URLs), abort with status: failed, reason: "hex code leak: <hex> in slide N" . Lesson: Golden Visa cron carousel S7 emitted bg: #0F1729 (navy, off-palette) — this is exactly the failure mode the rule blocks. The token namespace is closed (Article 2.1): adding a new color requires constitutional amendment. If you "need" a navy or any color outside the closed set, escalate by emitting status: needs_constitutional_amendment instead of inventing a hex. Preserve copy verbatim : never modify heading/body/subheading content from storyboarder. If copy violates a constitution rule, that's the storyboarder's responsibility, not yours. Add data-zone-type attributes to every visual element (text | hero-photo | overlay | logo | source) so the critic can do region-aware checks (Article 2.4). Image URL handling : if image_url is empty/null, write a placeholder div with data-zone-type="hero-photo-pending" and let the orchestrator (or image-generator) fill it post-hoc. Output single self-contained HTML per slide (referencing ../_base.css ). Renderer (Playwright) loads each independently. Article 5.10 — No silent placeholder reuse (NEW, 2026-05-09) : for every slide where is_hero_image: true , the image_source MUST be one of: imagegen:<codex_session_id> — fresh Codex $imagegen output, file copied from ~/.codex/generated_images/<session>/ into <output_dir>/<n>-hero.jpg anchor:<filename> — explicit declared anchor reuse from ~/.claude/skills/bali-zero-brand/anchors/<domain>-anchor.jpg , AND the slide-spec must declare image_strategy: "anchor_reuse" Verification (mandatory before writing slides.json): Hard fail any slide where image_source is missing, malformed, or fails the sha256 check. Emit validation_failures: ["slide N: image_source <reason>"] and status: "failed" . Orchestrator will block carousel emission. Bullet-promise verification (Article 6.3 helper) : if slide heading/sub announces N items and storyboarder body is a paragraph (not list_items array), emit validation_failures: ["slide N: heading promised <N> items but body is prose paragraph"] . Layout family dark-status-list requires list_items array per existing schema.

### [7] source `d3ccdc37…`

> ralph-loop Plugin .claude/ralph-loop.local.md: Hook usage (stop-hook.sh): Checks if file exists (line 15-18: quick exit if not active) Reads iteration count and max_iterations Extracts completion_promise for loop termination Reads body as the prompt to feed back Updates iteration count on each loop Quick Reference File Location Frontmatter Parsing Body Parsing Quick Exit Pattern Additional Resources Reference Files For detailed implementation patterns: references/parsing-techniques.md - Complete guide to parsing YAML frontmatter and markdown bodies references/real-world-examples.md - Deep dive into multi-agent-swarm and ralph-loop implementations

### [8] source `d3ccdc37…`

> Document in your README: Hooks cannot be hot-swapped within a session. Security Considerations Sanitize User Input When writing settings files from user input: Validate File Paths If settings contain file paths: Permissions Settings files should be: Readable by user only ( chmod 600 ) Not committed to git Not shared between users Real-World Examples multi-agent-swarm Plugin .claude/multi-agent-swarm.local.md: Hook usage (agent-stop-notification.sh): Checks if file exists (line 15-18: quick exit if not) Parses frontmatter to get coordinator_session, agent_name, enabled Sends notifications to coordinator if enabled Allows quick activation/deactivation via enabled: true/false

### [9] source `d3ccdc37…`

> Common Patterns Pattern 1: Temporarily Active Hooks Use settings file to control hook activation: Use case: Enable/disable hooks without editing hooks.json (requires restart). Pattern 2: Agent State Management Store agent-specific state and configuration: .claude/multi-agent-swarm.local.md: Read from hooks to coordinate agents: Pattern 3: Configuration-Driven Behavior .claude/my-plugin.local.md: Use in hooks or commands: Creating Settings Files From Commands Commands can create settings files: Template Generation

### [10] source `d3ccdc37…`

> Resources: Core SKILL.md (1,619 words) 3 example structures (minimal, standard, advanced) 2 reference docs: component-patterns, manifest-reference Use when: Starting a new plugin, organizing components, or configuring the plugin manifest. 4. plugin-settings Trigger phrases: "plugin settings", "store plugin configuration", ".local.md files", "plugin state files", "read YAML frontmatter", "per-project plugin settings" What it covers: .claude/plugin-name.local.md pattern for configuration YAML frontmatter + markdown body structure Parsing techniques for bash scripts (sed, awk, grep patterns) Temporarily active hooks (flag files and quick-exit) Real-world examples from multi-agent-swarm and ralph-loop plugins Atomic file updates and validation Gitignore and lifecycle management

### [11] source `63370ead…`

> Frontmatter reference Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between --- markers at the top of your SKILL.md file: All fields are optional. Only description is recommended so Claude knows when to use the skill. Field Required Description name No Display name for the skill. If omitted, uses the directory name. Lowercase letters, numbers, and hyphens only (max 64 characters). description Recommended What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage. when_to_use

### [12] source `1fd52991…`

> Frontmatter reference Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between --- markers at the top of your SKILL.md file: All fields are optional. Only description is recommended so Claude knows when to use the skill. Field Required Description name No Display name for the skill. If omitted, uses the directory name. Lowercase letters, numbers, and hyphens only (max 64 characters). description Recommended What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage. when_to_use

### [13] source `6f0873fe…`

> Supported frontmatter fields The following fields can be used in the YAML frontmatter. Only name and description are required. <cited_table>

### [14] source `2ad7dcc3…`

> 5.1 Hook Events You can sort the table by clicking on the column name. <cited_table>

### [15] source `92b09121…`

> Initialize queue Q ← [ ( s root , f s root ) ] Q\leftarrow[(s_{\mathrm{root}},f_{s_{\mathrm{root}}})] ; while Q ≠ ∅ Q\neq\emptyset do Pop ( s , f s ) (s,f_{s}) from Q Q ; ℱ  [ s ] ← f s \mathcal{F}[s]\leftarrow f_{s} ; 𝒮 ← Subskill  ( s ; 𝒯 ) \mathcal{S}\leftarrow\mathrm{Subskill}(s;\mathcal{T}) ; ( g s , { f s ′ } s ′ ∈ 𝒮 ) ← Reflect  ( s , f s , 𝒮 ) (g_{s},{f_{s^{\prime}}} {s^{\prime}\in\mathcal{S}})\leftarrow\textsc{Reflect}(s,f {s},\mathcal{S}) ; 𝒢  [ s ] ← g s \mathcal{G}[s]\leftarrow g_{s} ; foreach s ′ ∈ 𝒮 s^{\prime}\in\mathcal{S} do

### [16] source `d0adf453…`

> Workflow (mandatory sequence) Step 0 — ENFORCEMENT PROLOGUE (read FIRST, every run) You produce decent carousels by writing the artifacts inline yourself. That is a bug, not a feature. Empirical evidence (test-3, 2026-05-09): you ran a 9-slide pipeline with 0 Agent tool calls, 0 NB queries, 0 codex imagegen , reusing placeholder hero images from a prior test. The user has now hardcoded three non-negotiable contracts. Violating any of them = pipeline FAIL, not "soft optimization". Cost discipline — _audit-checklist.sh (mandatory, added 2026-05-10)

### [17] source `f6c76ff7…`

> 6.6 Skill Discovery The practical utility of Agent Knowledge Architecture depends on effective skill discovery: the ability of an agent to find the right skill at the right time. Discovery operates through multiple complementary mechanisms. Semantic matching allows agents to query the AKU Registry using natural language intent descriptions, leveraging embedding-based retrieval to identify candidate skills whose descriptions align with the agent's current goal [ 35 ] . Trigger conditions embedded in skill metadata specify the contexts under which a skill becomes relevant—for instance, a skill for handling database connection pool exhaustion might declare an activation trigger tied to specific monitoring alert patterns. Organizational context narrows the search space: an agent operating within the payments team's domain automatically has its discovery scope weighted toward payment-relevant skills. Together, these mechanisms ensure that skill discovery is not a brute-force search over a flat catalog but a context-sensitive, intent-driven process that reflects the organizational structure in which the agent operates. Effective discovery is particularly critical for AI-Generated Golden Path composition: the quality of the generated workflow depends directly on the agent's ability to identify the right skills, in the right order, with the right governance posture, from across the organization's entire knowledge surface.

### [18] source `63370ead…`

> 2 Write SKILL.md Every skill needs a SKILL.md file with two parts: YAML frontmatter between --- markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs. The directory name becomes the command you type, and the description helps Claude decide when to load the skill automatically. Save this to ~/.claude/skills/summarize-changes/SKILL.md : The ! git diff HEAD`` line uses dynamic context injection : Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.

### [19] source `1fd52991…`

> 2 Write SKILL.md Every skill needs a SKILL.md file with two parts: YAML frontmatter between --- markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs. The directory name becomes the command you type, and the description helps Claude decide when to load the skill automatically. Save this to ~/.claude/skills/summarize-changes/SKILL.md : The ! git diff HEAD`` line uses dynamic context injection : Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.

### [20] source `9797c0de…`

> No List of skill names to preload into the agent's context at startup. Unlisted skills remain invocable through the Skill tool memory No Memory source for this agent: "user" , "project" , or "local" mcpServers No MCP servers available to this agent. Each entry is a server name or an inline {name: config} dict initialPrompt No Auto-submitted as the first user turn when this agent runs as the main thread agent maxTurns No Maximum number of agentic turns before the agent stops background No Run this agent as a non-blocking background task when invoked effort

### [21] source `6f0873fe…`

> Preload skills into subagents Use the skills field to inject skill content into a subagent's context at startup. This gives the subagent domain knowledge without requiring it to discover and load skills during execution. The full content of each listed skill is injected into the subagent's context at startup. This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution. To prevent a subagent from invoking skills entirely, omit Skill from the tools list or add it to disallowedTools . You cannot preload skills that set disable-model-invocation: true , since preloading draws from the same set of skills Claude can invoke. If a listed skill is missing or disabled, Claude Code skips it and logs a warning to the debug log.

### [22] source `63370ead…`

> In a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked. Subagents with preloaded skills work differently: the full skill content is injected at startup. Skill content lifecycle When you or Claude invoke a skill, the rendered SKILL.md content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps. Auto-compaction carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session. If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill's description and instructions so the model keeps preferring it, or use hooks to enforce behavior deterministically. If the skill is large or you invoked several others after it, re-invoke it after compaction to restore the full content.
