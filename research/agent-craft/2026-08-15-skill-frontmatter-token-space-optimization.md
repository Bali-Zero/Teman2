---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-15-skill-frontmatter-token-space-optimization

**Date**: 2026-08-15
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 9 / Citations: 21

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Ottimizzazione dello Spazio dei Token nel Frontmatter:** Dato che il sistema Claude Code applica un limite rigido di troncamento a **1.536 caratteri** per la stringa combinata di `description` e `when_to_use` nel caricamento globale a SessionStart [4, 5], come possiamo compattare i metadati e i trigger delle nostre 16 skill e layouts per evitare il troncamento di informazioni chiave senza compromettere la precisione della scoperta automatica (*Skill Discovery*) [22]?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Ottimizzazione dello Spazio dei Token nel Frontmatter: Fonti Canoniche**

Il sistema di caricamento delle **Agent Skills** gestisce la memoria dell'agente a SessionStart tramite un meccanismo di **progressive disclosure** (rivelazione progressiva) strutturato su più livelli, per evitare che l'accumulo di istruzioni provochi il cosiddetto *context rot* (degradazione del contesto) [1-3]. Le nostre fonti stabiliscono regole ferree per preservare questa efficienza:

#### **A. Il Limite Rigido di Troncamento (1.536 Caratteri)**
In fase di avvio, l'agente carica solo i campi `name` e `description` (che include l'eventuale `when_to_use`) di tutte le skill installate per decidere quando applicarle [3-5]. 
*   Come documentato nella guida di configurazione: 
    > *"Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage."* [6, 7].
*   Questo limite può essere calibrato tramite il parametro di configurazione **`maxSkillDescriptionChars`** (introdotto a partire dalla versione `v2.1.105`):
    > *"maxSkillDescriptionChars: Per-skill character cap on the combined description and when_to_use text in the skill listing Claude sees each turn (default: 1536). Text longer than this is truncated. Raise to keep long descriptions intact at the cost of more context per turn; lower to fit more skills under skillListingBudgetFraction."* [8].

#### **B. Il Budget Globale della Skill Listing (`skillListingBudgetFraction`)**
Quando il numero di skill caricate cresce, il sistema applica una politica di collassamento guidata dal budget:
*   La configurazione **`skillListingBudgetFraction`** definisce lo spazio massimo dedicato ai trigger nel prompt di sistema:
    > *"skillListingBudgetFraction: Fraction of the model's context window reserved for the skill listing Claude sees each turn (default: 0.01 = 1%). When the listing exceeds the budget, descriptions for the least-used skills are collapsed to bare names so Claude can still invoke them but won't see why. Raise to keep more descriptions visible at the cost of more context per turn. /doctor shows the current truncation count and which skills are affected."* [9].

#### **C. Claude Search Optimization (CSO): Progettazione dei Trigger**
Per evitare che le descrizioni vengano collassate o troncate a metà, la documentazione sulle *best practices* impone una netta separazione tra il "quando" e il "cosa":
*   **La Regola Aurea del CSO:** 
    > *"CRITICAL: Description = When to Use, NOT What the Skill Does. The description should ONLY describe triggering conditions. Do NOT summarize the skill's process or workflow in the description."* [10].
*   **Il Rischio del Workflow nel Trigger:** Se la descrizione sintetizza le azioni, l'agente prenderà scorciatoie logiche: 
    > *"Testing revealed that when a description summarizes the skill's workflow, Claude may follow the description instead of reading the full skill content. ... The trap: descriptions that summarize workflow create a shortcut Claude will take. The skill body becomes documentation Claude skips."* [11, 12].
*   **Target Word Count:** Si raccomanda di mantenere la descrizione focalizzata: 
    > *"keep individual skill descriptions concise (under 50 words)."* [13] e di formulare trigger descrittivi in terza persona focalizzati sul problema [12, 14].

---

### **2. Confronto con lo Stack Reale (Bali Zero / Nuzantara)**

Nel nostro ecosistema reale di produzione, carichiamo contemporaneamente fino a **16 skill e layouts attivi** per coordinare la pipeline di generazione WR2:

*   **Il Rischio del Collassamento Forzato:** Con 16 skill caricate, se ciascuna descrizione includesse dettagli procedurali (es. *"Questo layout impagina una tabella riassuntiva leggendo le specifiche da slides.json e inserendo i token colore dal database..."*), supereremmo ampiamente la quota dello `0.01` (1%) del nostro contesto riservata alla listing [9]. Claude Code, rilevando il superamento del budget, applicherebbe la **collapsing policy**, riducendo i layout meno utilizzati (come `timeline-pinboard` o `dark-status-list`) a semplici nomi privi di descrizione [9]. L'agente non saprebbe più sotto quali condizioni attivarli (`won't see why`) [9], portando a fallimenti di caricamento a runtime.
*   **La Soluzione Riconquistata (Il Git Commit `ac971a9`):** Durante lo sviluppo, per evitare il troncamento a 1.536 caratteri, abbiamo rimosso tutte le istruzioni di formattazione HTML/CSS dai campi `description` del frontmatter dei nostri layout in `layouts/`, confinando le regole di visualizzazione e di applicazione dei token esclusivamente nel markdown body del file `SKILL.md` (Level 2) o nei file di specifica CSS di supporto (Level 3) [3, 5].

---

### **3. Linea di Azione Concreta per la Libreria Bali Zero**

Per ottimizzare la scoperta delle skill ed eliminare il rischio di collassamento silenzioso dovuto all'espansione della nostra Knowledge Topology, implementeremo un piano di sfoltimento e taratura dei metadati:

#### **A. Refactoring dei Campi `description` in terza persona (CSO-compliant)**
Modificheremo sistematicamente il frontmatter di tutti i layout in `layouts/` per contenere unicamente trigger di attivazione basati su problemi o formati, limitando la lunghezza a **massimo 40 parole**.
*   *Esempio per il layout `layouts/timeline-pinboard.md`:*
    ```yaml
    ---
    name: timeline-pinboard
    description: Visual layout for sequential steps, chronological events, or process milestones. Use automatically when the brief contains historical dates, project timelines, step-by-step roadmaps, or sequential numbering schemas for Bali Zero.
    ---
    ```

#### **B. Ottimizzazione delle Impostazioni di Sessione in `.claude/settings.json`**
Applicheremo una configurazione di progetto che estenda difensivamente la visibilità delle nostre skill core, riducendo lo spazio per quelle non necessarie tramite gli overrides:
```json
{
  "maxSkillDescriptionChars": 800,
  "skillListingBudgetFraction": 0.02,
  "skillOverrides": {
    "cover-photo": "on",
    "timeline-pinboard": "on",
    "statement-bomb": "on",
    "legacy-context": "name-only",
    "deploy": "off"
  }
}
```
*   **Vantaggio:** Raddoppiando il budget al `2%` (0.02) e limitando i trigger sotto gli 800 caratteri, garantiamo matematicamente l'integrità visiva di tutte le nostre 16 skill, escludendo quelle deprecate o non utilizzate a livello di model-discovery [9, 15].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Ciclo di Vita post-Compattazione:** Quando avviene l'auto-compattazione del contesto in una sessione lunga, Claude Code ri-allega le ultime invocazioni delle skill entro un budget combinato di **25.000 token** [16]. In che modo possiamo assicurarci che i nostri layout strutturali più vecchi non vengano completamente rimossi da questa coda di compattazione se abbiamo eseguito molte iterazioni di debug consecutive?
2.  **Interazione tra `isolation: worktree` e Preprocessing Bash (`!`):** Dato che forziamo i nostri sub-agenti a girare in worktree isolati [17], come influisce la presenza di percorsi git separati sull'esecuzione dei comandi di iniezione dinamica della shell (es. comandi del tipo `!git diff HEAD` o `!cat ~/.claude/skills/tokens.json`) dichiarati nel frontmatter delle nostre skill a startup [18, 19]?
3.  **Governance delle Skill nei Monorepo:** In presenza di sotto-cartelle di pacchetto nidificate (es. `packages/frontend/`), Claude Code esegue l'auto-scoperta delle skill risalendo fino alla radice del repository [20, 21]. Come possiamo strutturare una gerarchia di ereditarietà tra le skill globali del brand Bali Zero e le skill di compilazione specifiche di Playwright situate nelle sotto-directory per evitare conflitti di sovrascrittura di metadati?

📊 *Se lo desideri, posso lanciare lo strumento `/doctor` nella nostra sandbox per estrarre la telemetria esatta delle nostre attuali skill e verificare se qualcuna di esse sta subendo una compressione parziale o un troncamento invisibile dei metadati.*

## Sources used (9)

- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `26a3d040-47b7-4e55-bc95-b016c9ba3e37`
- `826c1a72-fe0c-4540-a0e4-1fba8f602a25`
- `35b43480-1d54-402c-8fd2-a745aa534c8d`
- `1fd52991-76b5-458c-aff1-c4f399f99566`
- `63370ead-a837-4bab-98dc-79109d022209`
- `366690aa-8295-4154-a4f6-efbeebf25954`
- `5702f19a-011f-4ca1-9ba4-4c7b0c3e02d7`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`

## Citations verbatim (21)

### [1] source `f6c76ff7…`

> The finite context window of LLMs imposes hard constraints on knowledge delivery. Recent research has identified context rot —the measurable degradation of LLM performance as context windows fill with accumulated irrelevant or redundant content—as a fundamental challenge for long-running agent sessions [ 16 ] . This finding provides empirical motivation for context-efficient knowledge delivery: every token of poorly structured or redundant knowledge injected into an agent's context actively degrades the agent's reasoning capability, making the design of compact, high-signal knowledge primitives not merely an efficiency concern but a correctness requirement [ 5 ] . [ 31 ] addressed the compression dimension through prompt compression techniques that preserve essential information while reducing token counts, demonstrating that significant compression ratios are achievable without proportional performance degradation. [ 10 ] established that LLMs can acquire new capabilities through in-context learning with few-shot examples, suggesting that carefully curated context can substitute for parametric knowledge—but the question of what to place in context, and how to structure it, remains underexplored in enterprise settings.

### [2] source `26a3d040…`

> How Skills work Skills leverage Claude's VM environment to provide capabilities beyond what's possible with prompts alone. Claude operates in a virtual machine with filesystem access, allowing Skills to exist as directories containing instructions, executable code, and reference materials, organized like an onboarding guide you'd create for a new team member. This filesystem-based architecture enables progressive disclosure : Claude loads information in stages as needed, rather than consuming context upfront.

### [3] source `826c1a72…`

> Core design principles Progressive Disclosure Skills use a three-level system: First level (YAML frontmatter): Always loaded in Claude's system prompt. Provides just enough information for Claude to know when each skill should be used without loading all of it into context. Second level (SKILL.md body): Loaded when Claude thinks the skill is relevant to the current task. Contains the full instructions and guidance. Third level (Linked files): Additional files bundled within the skill directory that Claude can choose to navigate and discover only as needed.

### [4] source `26a3d040…`

> Three types of Skill content, three levels of loading Skills can contain three types of content, each loaded at different times: Level 1: Metadata (always loaded) Content type: Instructions . The Skill's YAML frontmatter provides discovery information: Claude loads this metadata at startup and includes it in the system prompt. This lightweight approach means you can install many Skills without context penalty; Claude only knows each Skill exists and when to use it. Level 2: Instructions (loaded when triggered)

### [5] source `35b43480…`

> This is the design principle that makes Skills actually scalable. At agent startup, Claude pre-loads only the name and description from every installed skill into its system prompt. That's Level 1 : enough context to know when a skill is relevant, without bloating the context window. When Claude determines a skill matches the current task, it reads the full SKILL.md body. That's Level 2 . If the task requires sub-specialization (like form-filling vs. general PDF reading), Claude reads the linked files referenced in SKILL.md . That's Level 3+ .

### [6] source `1fd52991…`

> Frontmatter reference Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between --- markers at the top of your SKILL.md file: All fields are optional. Only description is recommended so Claude knows when to use the skill. Field Required Description name No Display name for the skill. If omitted, uses the directory name. Lowercase letters, numbers, and hyphens only (max 64 characters). description Recommended What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage. when_to_use

### [7] source `63370ead…`

> Frontmatter reference Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between --- markers at the top of your SKILL.md file: All fields are optional. Only description is recommended so Claude knows when to use the skill. Field Required Description name No Display name for the skill. If omitted, uses the directory name. Lowercase letters, numbers, and hyphens only (max 64 characters). description Recommended What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined description and when_to_use text is truncated at 1,536 characters in the skill listing to reduce context usage. when_to_use

### [8] source `366690aa…`

> Configure Claude's preferred response language (e.g., "japanese" , "spanish" , "french" ). Claude will respond in this language by default. Also sets the voice dictation language "japanese" maxSkillDescriptionChars Per-skill character cap on the combined description and when_to_use text in the skill listing Claude sees each turn (default: 1536 ). Text longer than this is truncated. Raise to keep long descriptions intact at the cost of more context per turn; lower to fit more skills under skillListingBudgetFraction . Requires Claude Code v2.1.105 or later 2048 minimumVersion

### [9] source `366690aa…`

> Show turn duration messages after responses, e.g. “Cooked for 1m 6s”. Default: true . Appears in /config as Show turn duration false skillListingBudgetFraction Fraction of the model's context window reserved for the skill listing Claude sees each turn (default: 0.01 = 1%). When the listing exceeds the budget, descriptions for the least-used skills are collapsed to bare names so Claude can still invoke them but won't see why. Raise to keep more descriptions visible at the cost of more context per turn. /doctor shows the current truncation count and which skills are affected. Requires Claude Code v2.1.105 or later 0.02 skillOverrides

### [10] source `5702f19a…`

> Claude Search Optimization (CSO) Critical for discovery: Future Claude needs to FIND your skill 1. Rich Description Field Purpose: Claude reads description to decide which skills to load for a given task. Make it answer: "Should I read this skill right now?" Format: Start with "Use when..." to focus on triggering conditions CRITICAL: Description = When to Use, NOT What the Skill Does The description should ONLY describe triggering conditions. Do NOT summarize the skill's process or workflow in the description.

### [11] source `5702f19a…`

> Why this matters: Testing revealed that when a description summarizes the skill's workflow, Claude may follow the description instead of reading the full skill content. A description saying "code review between tasks" caused Claude to do ONE review, even though the skill's flowchart clearly showed TWO reviews (spec compliance then code quality). When the description was changed to just "Use when executing implementation plans with independent tasks" (no workflow summary), Claude correctly read the flowchart and followed the two-stage review process.

### [12] source `5702f19a…`

> The trap: Descriptions that summarize workflow create a shortcut Claude will take. The skill body becomes documentation Claude skips. Content: Use concrete triggers, symptoms, and situations that signal this skill applies Describe the problem (race conditions, inconsistent behavior) not language-specific symptoms (setTimeout, sleep) Keep triggers technology-agnostic unless the skill itself is technology-specific If skill is technology-specific, make that explicit in the trigger Write in third person (injected into system prompt) NEVER summarize the skill's process or workflow

### [13] source `35b43480…`

> Step 4 — Add skills via the API (for developers). The Agent Skills API reference covers the /v1/skills endpoint for programmatic skill versioning and management. In Claude Code, drop the skill folder into your project directory — Claude discovers it automatically at startup. One honest note: keep individual skill descriptions concise (under 50 words). With 10+ skills installed, bloated descriptions add up fast in your system prompt. And since skills can execute code, treat unknown skill sources the same way you'd treat an unreviewed npm package.

### [14] source `5702f19a…`

> SKILL.md Structure Frontmatter (YAML): Two required fields: name and description (see agentskills.io/specification for all supported fields) Max 1024 characters total name : Use letters, numbers, and hyphens only (no parentheses, special chars) description : Third-person, describes ONLY when to use (NOT what it does) Start with "Use when..." to focus on triggering conditions Include specific symptoms, situations, and contexts NEVER summarize the skill's process or workflow (see CSO section for why) Keep under 500 characters if possible

### [15] source `366690aa…`

> Per-skill visibility overrides keyed by skill name. Value is "on" , "name-only" , "user-invocable-only" , or "off" . Lets you hide or collapse a skill without editing its SKILL.md. Does not apply to plugin skills, which are managed through /plugin . The /skills menu writes these to .claude/settings.local.json . See Override skill visibility from settings . Requires Claude Code v2.1.129 or later {"legacy-context": "name-only", "deploy": "off"} skipWebFetchPreflight Skip the WebFetch domain safety check that sends each requested hostname to api.anthropic.com before fetching. Set to true in environments that block traffic to Anthropic, such as Bedrock, Vertex AI, or Foundry deployments with restrictive egress. When skipped, WebFetch attempts any URL without consulting the blocklist true spinnerTipsEnabled

### [16] source `1fd52991…`

> In a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked. Subagents with preloaded skills work differently: the full skill content is injected at startup. Skill content lifecycle When you or Claude invoke a skill, the rendered SKILL.md content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps. Auto-compaction carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session. If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill's description and instructions so the model keeps preferring it, or use hooks to enforce behavior deterministically. If the skill is large or you invoked several others after it, re-invoke it after compaction to restore the full content.

### [17] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [18] source `1fd52991…`

> 2 Write SKILL.md Every skill needs a SKILL.md file with two parts: YAML frontmatter between --- markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs. The directory name becomes the command you type, and the description helps Claude decide when to load the skill automatically. Save this to ~/.claude/skills/summarize-changes/SKILL.md : The ! git diff HEAD`` line uses dynamic context injection : Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.

### [19] source `1fd52991…`

> No Effort level when this skill is active. Overrides the session effort level. Default: inherits from session. Options: low , medium , high , xhigh , max ; available levels depend on the model. context No Set to fork to run in a forked subagent context. agent No Which subagent type to use when context: fork is set. hooks No Hooks scoped to this skill's lifecycle. See Hooks in skills and agents for configuration format. paths No Glob patterns that limit when this skill is activated. Accepts a comma-separated string or a YAML list. When set, Claude loads the skill automatically only when working with files matching the patterns. Uses the same format as path-specific rules . shell

### [20] source `1fd52991…`

> Automatic discovery from parent and nested directories Project skills load from .claude/skills/ in your starting directory and in every parent directory up to the repository root, so starting Claude in a subdirectory still picks up skills defined at the root. When you work with files in subdirectories below your starting directory, Claude Code also discovers skills from nested .claude/skills/ directories on demand. For example, if you're editing a file in packages/frontend/ , Claude Code also looks for skills in packages/frontend/.claude/skills/ . This supports monorepo setups where packages have their own skills. Each skill is a directory with SKILL.md as the entrypoint:

### [21] source `63370ead…`

> Automatic discovery from parent and nested directories Project skills load from .claude/skills/ in your starting directory and in every parent directory up to the repository root, so starting Claude in a subdirectory still picks up skills defined at the root. When you work with files in subdirectories below your starting directory, Claude Code also discovers skills from nested .claude/skills/ directories on demand. For example, if you're editing a file in packages/frontend/ , Claude Code also looks for skills in packages/frontend/.claude/skills/ . This supports monorepo setups where packages have their own skills. Each skill is a directory with SKILL.md as the entrypoint:
