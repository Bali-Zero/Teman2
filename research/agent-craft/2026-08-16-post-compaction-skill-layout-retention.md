# Agent-craft DR — 2026-08-16-post-compaction-skill-layout-retention

**Date**: 2026-08-16
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 14 / Citations: 18

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Ciclo di Vita post-Compattazione:** Quando avviene l'auto-compattazione del contesto in una sessione lunga, Claude Code ri-allega le ultime invocazioni delle skill entro un budget combinato di **25.000 token** [16]. In che modo possiamo assicurarci che i nostri layout strutturali più vecchi non vengano completamente rimossi da questa coda di compattazione se abbiamo eseguito molte iterazioni di debug consecutive?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **Anatomia della Compattazione e della "Skill Eviction" in Claude Code**

Nel ciclo di vita di una sessione di lavoro prolungata o durante cicli ripetuti di debug, l'auto-compattazione di Claude Code riassume i turni precedenti per liberare spazio nella finestra di contesto [1]. Durante questo processo, le skill e i layout che sono stati caricati vengono gestiti con regole specifiche di ri-allegazione [2]:
*   **La persistenza iniziale**: Una volta attivata, l'intera istruzione di `SKILL.md` entra nella conversazione come un singolo messaggio e vi rimane per tutta la sessione, senza essere riletta ad ogni turno [2].
*   **La ri-allegazione post-compattazione**: Quando scatta la compattazione automatica, il sistema tenta di preservare le skill precedentemente utilizzate ri-allegando l'ultima invocazione di ciascuna di esse subito dopo il riassunto generato, conservando al massimo i primi 5.000 token di ogni skill [2].
*   **Il collo di bottiglia dei 25.000 token**: Queste skill ri-allegate devono condividere un **budget combinato fisso di 25.000 token** [2]. Il sistema satura questo budget partendo **dalla skill invocata più di recente** a ritroso [2]. Di conseguenza, se durante sessioni intense di debug vengono invocati molti layout strutturali o sub-agenti, **le skill più vecchie (comprese quelle di brand o layout fondamentali) vengono rimosse del tutto dal contesto** senza alcun preavviso [2].
*   **Il fallimento silenzioso**: Quando una skill o un layout viene escluso a causa del superamento dei 25.000 token, smette silenziosamente di influenzare il comportamento del modello [2]. L'agente soffre di "amnesia da compattazione" e ricomincia a fare affidamento esclusivamente sulla sua base parametrica [3, 4].

---

### **Confronto con l'applicazione reale nel nostro stack (Bali Zero)**

Nel nostro attuale flusso per la generazione dei caroselli WR2, questo comportamento rappresenta un rischio sistematico:
*   **L'accumulo di layout nella REPL**: Quando l'orchestratore `wr2-design-architect` [5] lancia ripetuti cicli di rifinitura o debug di rendering tramite Playwright (es. modifiche iterative a `timeline-pinboard`, `cover-photo` e `statement-bomb` nello stesso thread [6]), la coda delle invocazioni si riempie rapidamente.
*   **La perdita della Brand Cortex**: I nostri layout core e le regole della `constitution.md` [6, 7] si trovano tipicamente all'inizio della sessione (sono le skill più vecchie). Non appena scatta la compattazione (solitamente intorno all'83% di utilizzo del contesto [4]), la ri-allegazione guidata dalla recenza favorisce gli ultimi layout di debug modificati [2]. Questo **sfratta la Brand Cortex** [6] e le regole globali dal budget di 25.000 token [2]. L'agente, pur continuando a generare codice HTML, inizia improvvisamente a violare le regole del brand (es. leak di hex-code o formati non untranslated) perché non "vede" più le istruzioni costituzionali [2, 8].
*   **Episodic Memory isolata**: Sebbene salviamo lo stato nel nostro database SQLite `wr2-episodic.db` tramite il layer episodico [9], questo database serve all'orchestratore a livello di orchestrazione a lungo termine, ma non impedisce la perdita immediata di contesto della REPL di Claude Code a runtime durante una sessione attiva [10].

---

### **Linea di azione concreta: Il "Two-Layer Restoration Watchdog" per Bali Zero**

Per risolvere l'amnesia da compattazione in modo deterministico, implementeremo un pattern di ripristino in due livelli ispirato all'architettura `Mnemos` [10]. Invece di affidarci al summarizer (che ignora le priorità), useremo un meccanismo di persistenza su disco guidato dai nostri hook di ciclo di vita [10].

#### **Azione**: Configurare un sistema di ripristino automatico basato sugli hook `PreCompact`, `PostCompact` e `PreToolUse`.

1.  **Livello 1: Salvataggio dell'Emergency Checkpoint (`PreCompact`)**
    Implementare un hook `PreCompact` in `.claude/hooks/pre-compact.sh`. Quando questo hook intercetta un evento di compattazione (sia `auto` che `manual` [11]), scrive lo stato attivo della generazione, inclusi i puntatori a tutti i layout strutturali correntemente referenziati in `slides.json` e la Brand Cortex, in un file di checkpoint temporaneo `/workspace/scratch/compaction_checkpoint.json` [10]. Contemporaneamente, crea un file vuoto marcatore su disco: `/workspace/scratch/.bali-zero-just-compacted` [10].

2.  **Livello 2: Re-iniezione forzata post-compattazione (`PreToolUse`)**
    Configurare un hook `PreToolUse` globale (senza filtri restrittivi, in modo che si attivi sulla prima chiamata a strumento successiva alla compattazione [10]). 
    Il funzionamento logico dell'hook sarà deterministico:
    *   Verifica l'esistenza del marcatore `/workspace/scratch/.bali-zero-just-compacted` [10].
    *   Se il file è presente: legge il checkpoint dal disco [10].
    *   Invia programmaticamente un comando di re-invocazione per ciascuna delle skill e dei layout core salvati (es. eseguendo un comando `/skills/bali-zero-brand` o richiamando esplicitamente le regole di brand [2]). Questa azione **forza il ripristino dei layout strutturali e della Brand Cortex portandoli in cima alla coda di recenza** [2], garantendo che rientrino prioritariamente nel budget di 25.000 token post-compattazione [2].
    *   Rimuove il marcatore dal disco per evitare loop infiniti [10].

Questo approccio garantisce la stabilità del contesto: non dipendiamo dalla qualità euristica del riassunto di Claude Code [10, 12], ma forziamo il ripristino deterministico dello stato dal disco direttamente nella conversazione [10].

---

### **Domande aperte per il Deep Research (DR) di Domani**

1.  **Impatto dei Token di Pensiero (Thinking) sulla Compattazione**: Dato che Claude Opus 4.7 utilizza esclusivamente il ragionamento adattivo e calcola i token di pensiero come output [13, 14], in che modo l'accumulo di blocchi di pensiero crittografati influisce sul trigger point dell'auto-compattazione, e come possiamo calibrare la variabile `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` [15] per evitare compattazioni premature durante debug complessi?
2.  **Risoluzione dei conflitti in caso di crash simultaneo di Sub-Agenti**: Nel caso in cui l'orchestratore centralizzato `wr2-design-architect` [5] e un sub-agente (es. `wr2-layout-composer` [16]) subiscano una compattazione simultanea o un crash di sessione, come possiamo coordinare l'albero dei checkpoint per evitare la corruzione dello stato o sovrascritture incrociate nel database SQLite comune `wr2-episodic.db`?
3.  **Ottimizzazione della progressive disclosure tramite "Observation Masking"**: Se i nostri layout generano grandi porzioni di codice HTML/CSS transitorio che accelera la compattazione, possiamo implementare un hook `PostToolUse` [17] che esegua l'oscuramento delle osservazioni (observation masking) [18] — sostituendo l'HTML grezzo visualizzato nei turni passati con un placeholder sintetico contenente solo lo SHA del file — per raddoppiare l'efficienza della nostra finestra di contesto senza perdere la tracciabilità delle modifiche?

---

🔄 Se vuoi, posso preparare una simulazione nella sandbox per forzare una compattazione artificiale e verificare quanti dei nostri layout vengono effettivamente "sfrattati" dal budget dei 25.000 token prima di scrivere i file degli hook di ripristino. Che ne pensi?

## Sources used (14)

- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `1fd52991-76b5-458c-aff1-c4f399f99566`
- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `b4852cc9-6ae0-43c1-8408-42c330cb05a5`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc`
- `3bcf9ef7-b926-4bfa-97d8-2d733b142a12`
- `e65a5f8f-9bac-44c8-bf39-a13841e40f93`
- `6445c350-5740-49cc-aa53-e5eb7fe9512f`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `4277411f-3b2b-4740-9f10-2c052b56eac7`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `4001017f-0461-4321-b6a2-49f427986150`

## Citations verbatim (18)

### [1] source `2ad7dcc3…`

> Memory is for context that should persist across conversations. Anything specific to the current conversation belongs in the todo list, not memory. 3.7 Compaction When the conversation approaches the model's context window, the harness compacts older turns into a summary so that work can continue. Compaction can be automatic (driven by the harness) or manual (via /compact ). <cited_table>

### [2] source `1fd52991…`

> In a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked. Subagents with preloaded skills work differently: the full skill content is injected at startup. Skill content lifecycle When you or Claude invoke a skill, the rendered SKILL.md content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps. Auto-compaction carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session. If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill's description and instructions so the model keeps preferring it, or use hooks to enforce behavior deterministically. If the skill is large or you invoked several others after it, re-invoke it after compaction to restore the full content.

### [3] source `f6c76ff7…`

> In enterprise agent deployments, the Institutional Impedance Mismatch described in Section 1 creates a specific mechanism that accelerates context rot. When an agent lacks the institutional knowledge required for a task, it resorts to inference from its general training—guessing at deployment targets, fabricating service names, or applying generic procedures where organization-specific ones are required. These guesses fail. The human operator provides a correction. The agent revises its approach and retries. Each cycle of guess, failure, correction, and retry consumes tokens: the failed attempt, the user's correction, the agent's revised reasoning, and the second attempt all persist in the context window. After several such cycles, the window is dominated by the detritus of failed interactions rather than actionable guidance, and the agent's performance degrades further—a vicious cycle.

### [4] source `b4852cc9…`

> r/ClaudeCode • 2 mo. ago Locked post Stickied post Archived post Join Report Claude bootstrap v3.3 - I fixed one of the biggest frustrations I've had - making claude code remember what it was doing after context compaction [Hey everyone, back with another update on Claude Bootstrap (the opinionated project initializer for Claude Code). Last time I posted we were at v3.0 with the TDD stop hooks, conditional rules, and agent teams. A lot has happened since then so here's the rundown. Problem that started all this If you've used Claude Code on anything non-trivial, you've hit this: you're deep into a task, context hits ~83%, compaction fires, and Claude suddenly has no idea what it was doing. The built-in summarizer tries its best but it treats everything equally. Your goals, your constraints, that random file listing from 40 messages ago... all get the same treatment. Sometimes it keeps the wrong stuff and drops what actually mattered. It gets worse. Sometimes /compact just doesn't run. Sometimes in multi-agent setups /clear fails and leaves you in a weird state. Crash mid-session? Everything is gone. There's no disk persistence, no structured recovery, nothing. I watched this happen live during a session where I was analyzing a month of token usage data (6.4B tokens, 96% cache reads). Compaction fired. Claude came back with a generic summary and couldn't continue the analysis. That was the moment I decided to actually fix this instead of just complaining about it. v3.2 - iCPG: Intent-Augmented Code Property Graph Before getting to the memory stuff, v3.2 shipped a full implementation of iCPG. The idea is simple: track why code exists, not just what it does. Every code change gets linked to a ReasonNode that captures the intent, postconditions, and invariants. Before the agent edits a file, a PreToolUse hook automatically queries: "what constraints apply to this file?" and "has this code drifted from its original intent?" The practical stuff:

### [5] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [6] source `74917ad2…`

> Skill library evolution : Each new skill enters as _proposed/<name>.md . After 3 successful uses (critic score ≥ threshold) it graduates to layouts/<name>.md . Skills unused for 60 days move to _archived/ . Hard guardrail : skill changes are git-committed. Antonello reviews diffs weekly. No autonomous skill modification merges to main without human commit. -------------------------------------------------------------------------------- 6. Concrete next 7 steps Write ~/.claude/agents/wr2-design-architect.md (orchestrator subagent). Write ~/.claude/skills/bali-zero-brand/constitution.md (hard rules). Write ~/.claude/skills/bali-zero-brand/SKILL.md (entry point with progressive disclosure). Stub ~/.claude/skills/bali-zero-brand/tokens.json (palette + type + spacing — derive from packages/core/tokens/primitives.css + WR2 reference PDFs). Stub ~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md and off-tone-examples.md (5 each from past WR2 winners + 3 known fails). Stub ~/.claude/skills/bali-zero-brand/layouts/ with 3 parametric layouts derived from WR2 reference PDFs (cover-photo, photo-headline-yellow-sub, statement-bomb-closing). Wire critic subagent ( wr2-critic ) with vision capability for PNG quality check.

### [7] source `3bcf9ef7…`

> Pre-condition check ~/.claude/skills/bali-zero-brand/constitution.md — Articles 2, 3, 6.3-6.7, 7, 8 (cross-surface mandatory). ~/.claude/skills/bali-zero-brand/surfaces/email-template.md — surface-specific spec. ~/.claude/skills/bali-zero-brand/voice/forbidden-phrases.md — closed-set ban. ~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md — voice calibration. ~/.claude/skills/bali-zero-brand/tokens.json — palette tokens. If any missing, abort with ERROR brand cortex incomplete . Workflow

### [8] source `e65a5f8f…`

> Failure modes Layout file missing → status: failed, reason: "layout family <X> not found in skill library" Required parameter missing → status: partial , list affected slides in validation_failures Hex code leaked into output → ABORT, status: failed, reason: "hex code leak detected in slide N" More than 50% of slides fail validation → status: failed Cost discipline You are Sonnet 4.6 (faster + cheaper than Opus). For 9 slides this should be ONE invocation, not 9. Read all layout files at start, build HTML files in a loop, write all at end. ~30 carousels/month = 30 composer invocations.

### [9] source `6445c350…`

> Tipo : Claude Code subagent (Type A) in ~/.claude/agents/wr2-design-architect.md Modello : Opus 4.7 via OAuth MAX (zero costi, CLAUDE.md HARD RULE compliance) Pattern : orchestrator centralizzato + 4 specialist subagents (NO peer-to-peer — Google 17.2× error amplification finding) Sub-agents pianificati : brief-interpreter (Sonnet), storyboarder (Sonnet), layout-composer (Sonnet), critic (Opus vision-capable), publisher (Haiku) Skill base : ~/.claude/skills/bali-zero-brand/ — closed-namespace tokens + constitution + voice + layouts Memory layers : episodic (SQLite), semantic (file cortex), procedural (skill library), reflective (weekly cron synthesis) Growth pattern : Voyager curriculum + Reflexion post-mortem Quality gates : token compliance → critic panel (4 rubric) → CLIP similarity → diffusion variance hallucination check → human review

### [10] source `b4852cc9…`

> v3.3 - Mnemos: Task-Scoped Memory That Survives Everything This is the big one. Mnemos is a typed memory graph (MnemoGraph) backed by SQLite on disk. Different types of knowledge get different eviction policies: - GoalNodes and ConstraintNodes are NEVER evicted. These are the things that if lost, the agent literally cannot continue. - ResultNodes get compressed (summary kept, details dropped) before eviction. - ContextNodes (file contents, tool outputs) are freely evictable since they can be re-read from disk. Fatigue monitoring Instead of being blind until 83% and then doing a hard compaction, Mnemos passively monitors 4 behavioral signals from hooks: Signal > What it catches Token utilization (40%) > How full the context window is Scope scatter (25%) > Agent bouncing between too many directories Re-read ratio (20%) > Agent re-reading files it already read (context loss symptom) Error density (15%) > High tool failure rate (agent struggling) This gives you graduated states: FLOW -> COMPRESS -> PRE-SLEEP -> REM -> EMERGENCY. The system auto-checkpoints at 0.6 fatigue, well before compaction fires at 0.83. So when things go wrong, you always have a recent checkpoint. Two-layer post-compaction restoration (v3.3.1) This is what I'm most proud of. When compaction fires: Layer 1: The PreCompact hook writes an emergency checkpoint, builds a task narrative from recent signals ("Editing: auth.py (6x), reading middleware.ts (3x), focus area: src/api/"), and tells the summarizer exactly what to preserve with inline content. It also drops a .mnemos/just-compacted marker file on disk. Layer 2: After compaction, the very first tool call triggers a PreToolUse hook (no matcher, fires on everything). It checks for the marker file. If found, it reads the checkpoint from disk and injects the full structured state back into context: goal, constraints, what you were working on, progress, key files, git state. Then it deletes the marker so it only fires once. Layer 1 is best-effort because the summarizer might ignore our instructions. Layer 2 is the guaranteed path because it doesn't depend on the summarizer at all. It's just "read from disk, inject into context." The fast path (no compaction) adds ~5ms per tool call. Negligible. Why this matters beyond normal compaction The real value isn't just the happy path where compaction works normally. It's all the failure modes: - Session crash? Checkpoint is on disk, SessionStart hook reloads it. - /compact doesn't fire? Fatigue hooks already wrote checkpoints at 0.6. - Multi-agent child dies? Its .mnemos/ directory has the full structured state the parent can read. - Forced restart? Checkpoint survives, loaded automatically. - /clear fails in multi-agent? MnemoGraph is completely independent of Claude Code's internal state machine. "Just write important stuff to a file" is the obvious objection and honestly I considered it. But you immediately run into: what format, when to update, how to prioritize. That's exactly what the typed node model solves. Without it you'd reinvent the same structure or suffer without it. Try it

### [11] source `d564912c…`

> WorktreeRemove input In addition to the common input fields , WorktreeRemove hooks receive the worktree_path field, which is the absolute path to the worktree being removed. WorktreeRemove hooks have no decision control. They cannot block worktree removal but can perform cleanup tasks like removing version control state or archiving changes. Hook failures are logged in debug mode only. PreCompact Runs before Claude Code is about to run a compact operation. The matcher value indicates whether compaction was triggered manually or automatically:

### [12] source `4277411f…`

> Upvote 0 Downvote 29 Go to comments Share Sort by: Best Open comment sort options Best Top New Controversial Old Q&A Search Comments Expand comment search Cancel Comments Section apaas • 4mo ago The Ralph Claude Code plugin is distinctly not a Ralph loop. As it has a hard dependency on compaction. The real value from so-called “Ralph loops” comes from working with completely fresh context windows for each iteration. Claude Code compaction is really bad, in my experience. Upvote 11 Downvote Reply Award Share

### [13] source `cf769fec…`

> Current State (April 2026) Opus 4.7 changed how reasoning works in Claude Code. Opus 4.7 uses adaptive reasoning exclusively — there are no fixed thinking budgets, and MAX_THINKING_TOKENS and CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING do not apply to it. 147 Instead, the model decides whether and how much to think on each step based on task complexity, guided by your /effort setting. On Opus 4.6 and Sonnet 4.6, the legacy extended-thinking system still works: thinking is on by default with a 31,999-token budget, adjustable via MAX_THINKING_TOKENS or /config . 63 You can revert to the previous fixed-budget behavior by setting CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 . 147

### [14] source `cf769fec…`

> Cost consideration: Anthropic bills thinking tokens as output tokens. The default 31,999 budget works well for most tasks, but for simple operations you can save costs by reducing the budget or disabling thinking entirely. How It Works When thinking is enabled, Claude performs internal reasoning that influences the answer but does not appear in the output. Claude Code encrypts the thinking and returns it in a signature field for verification. In multi-turn conversations with tool use, thinking blocks must be passed back to the API to preserve reasoning continuity. Claude Code handles this automatically.

### [15] source `6f0873fe…`

> Auto-compaction Subagents support automatic compaction using the same logic as the main conversation. By default, auto-compaction triggers at approximately 95% capacity. To trigger compaction earlier, set CLAUDE_AUTOCOMPACT_PCT_OVERRIDE to a lower percentage (for example, 50 ). See environment variables for details. Compaction events are logged in subagent transcript files: The preTokens value shows how many tokens were used before compaction occurred. Fork the current conversation Forked subagents are experimental and require Claude Code v2.1.117 or later. Behavior and configuration may change in future releases. Enable them by setting the CLAUDE_CODE_FORK_SUBAGENT environment variable to 1 . The variable is honored in interactive mode and via the SDK or claude -p .

### [16] source `e65a5f8f…`

> -------------------------------------------------------------------------------- name: wr2-layout-composer description: "MUST BE USED by wr2-design-architect at Step 4 of every carousel run. Use IMMEDIATELY after storyboarder returns slides.json. Receives slide-spec JSON + brief JSON verbatim, retrieves matching layout from skill library, parameterizes HTML/CSS, writes render-ready files for Playwright. ENFORCES no silent placeholder reuse (Article 5.10): every hero image_source must be imagegen:<session> or anchor:<file> with sha256(hero) ≠ sha256(anchor) verification. Does NOT render itself (orchestrator drives Playwright)." tools: Read, Write, Edit, Glob, Grep, Bash model: sonnet color: yellow skills:

### [17] source `cf769fec…`

> Available Events <cited_table>

### [18] source `4001017f…`

> When the context exceeds this cap, the agent must compress its history. A common approach is LLM-based compaction , in which an additional LLM call summarizes old messages before discarding them (Kang et al., 2025 ) . This is effective but costly: the summarization call itself consumes tokens, and the generated summary may lose important details. Recent work by Lindenbauer et al. (Lindenbauer et al., 2025 ) showed that a simpler strategy— observation masking , which replaces old tool outputs with placeholders while preserving the agent's reasoning trace—halves cost while matching LLM summarization's task-completion rate on the SWE-bench benchmark.
