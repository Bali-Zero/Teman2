---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-11-subagent-silent-tool-denial-recovery-patterns

**Date**: 2026-08-11
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 14 / Citations: 33

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   Dato che i sub-agenti considerano automaticamente come **"denied"** qualsiasi chiamata a uno strumento che ricade sotto una regola interattiva di `ask` [9], quali sono i pattern migliori per gestire i fallimenti silenziosi dei tool di scrittura o esecuzione bash quando i sub-agenti tentano di applicare patch a codice protetto o a file temporanei?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Gestione dei fallimenti dei tool nei sub-agenti: Meccanismi e Fonti Canoniche**

Quando i sub-agenti operano in ambienti di produzione complessi, l'interazione con il sistema di sicurezza e di permessi di Claude Code introduce dinamiche che possono dar luogo a fallimenti silenziosi. Le nostre fonti delineano tre aspetti architetturali critici:

#### **A. Il muro del gating non-interattivo**
I sub-agenti non possono presentare prompt di autorizzazione interattivi all'operatore umano: **"Subagents cannot present interactive permission prompts to the user. If a subagent invokes a tool that matches an ask rule, the call is treated as denied"** [1]. Nei sub-agenti eseguiti in background, questo comportamento si traduce in un blocco automatico: **"Background subagents [...] run with the permissions already granted in the session and auto-deny any tool call that would otherwise prompt"** [2].

#### **B. La "Permission Denial Resilience" (Il paradosso della resilienza)**
A partire dalla versione `v2.1.0`, Anthropic ha introdotto un meccanismo di tolleranza ai blocchi: **"subagents continue working after permission denials instead of stopping entirely. When a subagent hits a permissions wall, it tries alternative approaches automatically"** [3]. Sebbene questo aumenti la flessibilità, introduce un rischio drastico di fallimento silenzioso in presenza di codice protetto o file temporanei. Senza istruzioni di arresto, l'agente inizia a "indovinare" alternative o a ipotizzare che l'azione sia andata a buon fine, accelerando il deterioramento del contesto (context rot) consumando inutilmente token [4].

#### **C. Antidoto: Enforce Fail-Fast & Validation**
Nel framework *Evolving Programmatic Skill Networks* (PSN) [5], la presenza di un fallback ingenuo o silenzioso (es. il caso reale `ensureFlint` in cui un'istruzione aggirava il contratto di esecuzione) è classificata come una violazione grave ("Unsafe Fallback") [6, 7]. La riparazione canonica consiste nel rimuovere le scorciatoie e forzare un comportamento di arresto immediato: **"PSN removes the unsafe fallback and enforces fail-fast behavior, ensuring that execution failures are explicitly surfaced and handled by upstream skills"** [6]. Questo si ottiene abbinando:
1.  **Pre-execution validators**: che verificano programmaticamente i requisiti (es. esistenza dei permessi, stato del worktree) prima di agire [8].
2.  **Post-execution validators**: script deterministici che certificano l'esito dell'azione sul disco (es. controllando il checksum o la presenza fisica dei file) anziché affidarsi alla risposta dell'LLM [8, 9].
3.  **Bypass o Deferral controllato**: L'utilizzo di `acceptEdits` o `bypassPermissions` consente di evitare i prompt per modifiche interne alla directory del progetto [10-12]. In contesti headless/SDK, i hook `PreToolUse` possono restituire la decisione `"defer"` per congelare l'operazione in attesa dell'approvazione asincrona del client [13, 14].

---

### **2. Confronto con lo Stack Reale (Nuzantara / Bali Zero)**

Nel nostro stack, queste dinamiche vengono gestite applicando il principio del minimo privilegio e la centralizzazione delle operazioni di scrittura:

*   **Lavoratori stateless e a basso privilegio**: I sub-agenti sequenziali di scrittura come `wr2-brief-interpreter` o `wr2-storyboarder` non effettuano modifiche dirette all'infrastruttura. Il nostro sub-agente di revisione `wr2-critic` è totalmente privo di autorizzazioni di scrittura: **"Never modify slides yourself. You are read-only"** [15]. Questo limita drasticamente la superficie dei blocchi per via dei permessi.
*   **Orchestrator come gatekeeper**: Solo l'orchestratore principale `wr2-design-architect` (che opera con il livello di permessi autorizzato) esegue operazioni di scrittura e modifiche su file strutturali [16, 17].
*   **Audit centralizzato**: Invece di far verificare l'esito ai singoli sub-agenti con decine di chiamate bash intermedie (che rischierebbero di attivare le regole `ask`), l'orchestratore Bali Zero delega l'intero ciclo di validazione a uno script di controllo unificato (`_audit-checklist.sh`) richiamato esattamente 4 volte durante l'intera esecuzione (nelle modalità `preflight`, `setup-outdir`, `hero-sha`, `render-check` e `final-audit`) [18, 19].
*   **Stato machine di fallback**: Quando la generazione fallisce o viene bloccata dai limiti di chiamata o dai controlli di brand, il nostro orchestratore interrompe la pipeline, scrive lo stato `needs_human_edit` e invia una notifica `POST` al server di coda locale `http://localhost:8765/api/flag-needs-human-edit`, colorando di giallo la richiesta nella UI di Damar [20, 21].

---

### **3. Linea di azione concreta per la libreria Bali Zero**

Per gestire i fallimenti silenziosi e intercettare programmaticamente i tentativi di scrittura falliti dei sub-agenti all'interno della libreria Bali Zero, implementeremo un **"Silent Denial Watchdog"** strutturato come segue:

1.  **Configurazione del Hook `PermissionDenied`**:
    Aggiungere un handler globale per l'evento `PermissionDenied` [22-24] in `.claude/settings.json`. Questo hook intercetta programmaticamente tutte le negazioni automatiche emesse dal classificatore `auto` [22] o dal sistema di permessi, leggendo la variabile `agent_id` [25, 26] per verificare se la chiamata ha avuto origine all'interno di un sub-agente.
2.  **Modifica dello Script di Audit (`_audit-checklist.sh`)**:
    Implementare una modalità `validate-write-access` che esegua un preflight rapido di scrittura (tramite `touch` o test di directory) all'interno dei path temporanei o di destinazione prima di lanciare `wr2-layout-composer`.
3.  **Firma del Contratto Fail-Fast nel Body del Sub-agente**:
    Inserire nel body Markdown di `wr2-layout-composer.md` e dei futuri agenti operativi una clausola imperativa (Expert-Specified Constraint) [27]:
    > *"CRITICAL: After attempting any Edit, Write, or Bash execution, you MUST execute a Read or Glob call to verify that the file actually exists and contains your updates. If the file is missing or unchanged, you MUST abort execution immediately, outputting a JSON with `status: \"write_denied\"` and the exact file path, rather than attempting fallback guesses."* [6, 28]

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Dato che l'evento `SDKPermissionDeniedMessage` [29] consente di intercettare in tempo reale i blocchi di sicurezza dell'applicazione host, in che modo possiamo integrare questo flusso di eventi asincroni nel nostro client Python per bloccare preventivamente le chiamate API downstream di un sub-agente non appena viene rilevata una negazione automatica?
2.  Se una sub-session esegue modifiche in un ambiente isolato con `isolation: "worktree"` [30, 31], come possiamo garantire la corretta propagazione dei token di autenticazione e delle variabili d'ambiente caricate all'avvio nel file `.env` senza rischiare perdite di configurazione o esporre le credenziali fuori dal perimetro protetto [32, 33]?
3.  In presenza di collisioni o race condition sui file di lock del database SQLite (`wr2-episodic.db`) indotte dall'esecuzione parallela di sub-agenti asincroni, quali sono i migliori pattern di coordinamento (es. polling dello stato del disco o code di messaggi asincrone) per stabilizzare la persistenza della memoria episodica in produzione [34]?

## Sources used (14)

- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `92b09121-412d-4ece-a88e-86b922424a15`
- `5f596332-b92d-4e27-a3fc-e038981823d7`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `1826e81e-6d39-4285-956a-464b315e3f3f`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `6f16fd65-565d-491d-8db8-e2b095a5a064`
- `c78af240-51bd-4558-a4ed-7c0a82b09c14`
- `4001017f-0461-4321-b6a2-49f427986150`
- `23608d41-319c-4d8e-a906-748f9c05125e`
- `b67fe2b2-5ee8-460a-b793-ccb71d1b752d`

## Citations verbatim (33)

### [1] source `2ad7dcc3…`

> Note: Subagents cannot present interactive permission prompts to the user. If a subagent invokes a tool that matches an ask rule, the call is treated as denied. The recommended pattern is to restrict subagents to read-only tool sets (omit Edit , Write , and NotebookEdit from the frontmatter tools: list) and to defer all Edit / Write / NotebookEdit / Bash work to the parent agent that can handle approval prompts. Built-in subagents whose job is to edit files (for example, statusline-setup ) are exempt because their edit scope is narrow and predictable.

### [2] source `6f0873fe…`

> The CLI flag overrides the setting if both are present. Run subagents in foreground or background Subagents can run in the foreground (blocking) or background (concurrent): Foreground subagents block the main conversation until complete. Permission prompts are passed through to you as they come up. Background subagents run concurrently while you continue working. They run with the permissions already granted in the session and auto-deny any tool call that would otherwise prompt. If a background subagent needs to ask clarifying questions, that tool call fails but the subagent continues.

### [3] source `cf769fec…`

> Async agents return results via the unified TaskOutputTool, enabling efficient pipeline-style workflows. Permission Denial Resilience (v2.1.0+) Starting in v2.1.0, subagents continue working after permission denials instead of stopping entirely. When a subagent hits a permissions wall, it tries alternative approaches automatically. The change makes autonomous workflows more resilient and reduces the need for human intervention. 40 Agent Teams (February 2026, Research Preview) Agent Teams coordinate multiple Claude Code instances working together. One session acts as the team lead , spawning teammates that work independently in their own context windows, communicating directly with each other via a shared mailbox and task list. 79 84

### [4] source `f6c76ff7…`

> In enterprise agent deployments, the Institutional Impedance Mismatch described in Section 1 creates a specific mechanism that accelerates context rot. When an agent lacks the institutional knowledge required for a task, it resorts to inference from its general training—guessing at deployment targets, fabricating service names, or applying generic procedures where organization-specific ones are required. These guesses fail. The human operator provides a correction. The agent revises its approach and retries. Each cycle of guess, failure, correction, and retry consumes tokens: the failed attempt, the user's correction, the agent's revised reasoning, and the second attempt all persist in the context window. After several such cycles, the window is dominated by the detritus of failed interactions rather than actionable guidance, and the agent's performance degrades further—a vicious cycle.

### [5] source `92b09121…`

> Report issue for preceding element We compare PSN against representative LLM-agent baselines and ablations. ReAct (Yao et al., 2023 ) , a prompting-based agent that interleaves reasoning and action without persistent structured skills. Reflexion (Shinn et al., 2023 ) , an agent self-reflects over failures but does not maintain a compositional programmatic skill network. AutoGPT (Significant Gravitas, 2023 ) , a planning-centric agent that decomposes tasks into multi-step plans and executes generated code or action sequences autonomously. It maintains a short-term memory of past actions and observations, but treats generated plans and code fragments as ephemeral artifacts rather than persistent, reusable skills. Voyager (Wang et al., 2024a ) , an agent that maintains a flat skill library and retrieves skills via similarity, without trace-based symbolic credit assignment and canonical structural refactor as in PSN.

### [6] source `92b09121…`

> Report issue for preceding element Example 2: Unsafe Fallback ( ensureFlint). Report issue for preceding element Failure signal. The skill exhibits silent or inconsistent failures when attempting to mine gravel. Root cause. An unsafe fallback bypasses the system's primitive execution contract, preventing proper failure propagation to the planner. Repair. PSN removes the unsafe fallback and enforces fail-fast behavior, ensuring that execution failures are explicitly surfaced and handled by upstream skills. Outcome. The repaired skill behaves consistently and enables reliable replanning under failure.

### [7] source `92b09121…`

> Report issue for preceding element E.1 Optimization Taxonomy Report issue for preceding element Across experiments, frequent optimizations of PSN fall into several recurring categories. Table 5 summarizes the most common failure signals and corresponding repair strategies. Report issue for preceding element <cited_table>

### [8] source `f6c76ff7…`

> Pre-execution validators verify preconditions before the agent acts. Examples include confirming that the change management window is open, that the requesting identity holds the required permissions, that all continuous integration checks have passed, and that the target service is registered in the organization's service catalog. Post-execution validators verify outcomes after the action completes. These may confirm that a deployed service is healthy, that no policy violations were introduced, and that rollback capability has been established for the new deployment.

### [9] source `f6c76ff7…`

> Validators. A key mechanism for operationalizing governance without human bottlenecks is the validator : a deterministic script embedded within the skill that automatically verifies whether the agent's actions meet organizational standards. Validators are implemented as executable code—shell scripts, Python checks, or policy-as-code rules (e.g., Open Policy Agent)—that produce pass/fail results with structured logs. Unlike human approvers, validators are consistent (they apply identical rules every time), scalable (they execute in milliseconds regardless of volume), and auditable (every decision is logged with its inputs and the rule applied). By encoding governance checks as validators rather than human review gates, the framework enables governance teams to shift from governance-as-approval to governance-as-code : authoring deterministic governance artifacts that scale with the skill library rather than with headcount.

### [10] source `5f596332…`

> For programmatic streaming with callbacks and message objects, see Stream responses in real-time in the Agent SDK documentation. Auto-approve tools Use --allowedTools to let Claude use certain tools without prompting. This example runs a test suite and fixes failures, allowing Claude to execute Bash commands and read/edit files without asking for permission: To set a baseline for the whole session instead of listing individual tools, pass a permission mode . dontAsk denies anything not in your permissions.allow rules or the read-only command set , which is useful for locked-down CI runs. acceptEdits lets Claude write files without prompting and also auto-approves common filesystem commands such as mkdir , touch , mv , and cp . Other shell commands and network requests still need an --allowedTools entry or a permissions.allow rule, otherwise the run aborts when one is attempted:

### [11] source `cf769fec…`

> The first time a modification tool runs, Claude Code prompts for approval. Approvals persist for the session unless explicitly configured otherwise. Permission Modes <cited_table> Auto Mode (v2.1.85+): A safer replacement for --dangerously-skip-permissions . A separate classifier model (Sonnet 4.6) reviews each action before execution, checking that it matches user intent and is safe. 124

### [12] source `2ad7dcc3…`

> 3.8 Auto-Accept and Permission Modes Claude Code runs in one of several permission modes that change how often it prompts the user before tool execution. <cited_table>

### [13] source `d564912c…`

> PreToolUse previously used top-level decision and reason fields, but these are deprecated for this event. Use hookSpecificOutput.permissionDecision and hookSpecificOutput.permissionDecisionReason instead. The deprecated values "approve" and "block" map to "allow" and "deny" respectively. Other events like PostToolUse and Stop continue to use top-level decision and reason as their current format. Defer a tool call for later "defer" is for integrations that run claude -p as a subprocess and read its JSON output, such as an Agent SDK app or a custom UI built on top of Claude Code. It lets that calling process pause Claude at a tool call, collect input through its own interface, and resume where it left off. Claude Code honors this value only in non-interactive mode with the -p flag. In interactive sessions it logs a warning and ignores the hook result.

### [14] source `d564912c…`

> The defer value requires Claude Code v2.1.89 or later. Earlier versions do not recognize it and the tool proceeds through the normal permission flow. The AskUserQuestion tool is the typical case: Claude wants to ask the user something, but there is no terminal to answer in. The round trip works like this: Claude calls AskUserQuestion . The PreToolUse hook fires. The hook returns permissionDecision: "defer" . The tool does not execute. The process exits with stop_reason: "tool_deferred" and the pending tool call preserved in the transcript. The calling process reads deferred_tool_use from the SDK result, surfaces the question in its own UI, and waits for an answer. The calling process runs claude -p --resume <session-id> . The same tool call fires PreToolUse again. The hook returns permissionDecision: "allow" with the answer in updatedInput . The tool executes and Claude continues.

### [15] source `1826e81e…`

> Output format Return a JSON object. Each slide MUST also receive a binary verdict (Hamel Husain shadowing doctrine — keep numeric rubrics for diagnosis, but the carousel-level go/no-go is binary): binary_carousel_verdict derivation: PASS only if every slide is PASS AND carousel_level_failures is empty. Any slide FAIL OR any carousel-level hard fail → carousel FAIL. Orchestrator uses binary_carousel_verdict as the gate; numeric rubrics inform retry prompts. Hard rules (process) Hard fail = retry max 2 in orchestrator. Your job is to produce clear failure descriptions so retry can converge. Soft fail = no block , route to human review queue. Pass = release to publisher . Never modify slides yourself . You are read-only. Never call other subagents . You communicate with the orchestrator only via your output JSON. Cite the constitution article for every hard failure (e.g., "Article 6.4 — paraphrased citation Permenkumham 22/2023 should be verbatim"). Never invent rules . If a slide does something the constitution doesn't address, score 100 on that dimension and note in verbal_feedback for human discretion.

### [16] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [17] source `d0adf453…`

> Hard guardrails (process-level) Centralized state : you are the orchestrator. Subagents (critic, future layout-composer, future brief-interpreter) are stateless workers reading shared files. NEVER let subagents talk to each other peer-to-peer (Google's 17.2× error-amplification finding). Human-in-loop on publish : you do NOT publish to Instagram. Damar publishes manually. Your output stops at Canva (via existing wr2-canva-apply skill). No autonomous skill writes to main : skill changes go to _proposed/ . Antonello commits to main weekly. Cost = zero : only OAuth Claude (Opus/Sonnet/Haiku via subagents), free Gemini CLI for cross-check, NotebookLM for ground-truth RAG, DeepSeek API ($0.01/query OK). NEVER use ANTHROPIC_API_KEY, OpenAI API, Vertex AI billed runtime. No emoji in user-facing output : respond in clean text. Antonello has hard rule on this in CLAUDE.md.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [18] source `d0adf453…`

> Test-5 cost $10.07 / 29min because the orchestrator made 107 Bash + 50 Read = 165 tool calls for verifications that fit into ONE bash script. Test-6 onward MUST use the consolidated audit script: Modes (pass via env vars MODE , SLUG , DOMAIN ): MODE=preflight SLUG=<slug> DOMAIN=<tax|visa|property|regulatory|health> bash _audit-checklist.sh — runs all preflight checks (4 subagents present, brand cortex files, domain anchor sha, codex CLI version, slug uniqueness) in ONE invocation. Replaces ~12 separate Bash probes. MODE=setup-outdir SLUG=<slug> bash _audit-checklist.sh — creates output dir + copies logo/_base.css/hammurabi-stele in one shot. Replaces ~5 cp/mkdir calls. MODE=hero-sha SLUG=<slug> DOMAIN=<domain> bash _audit-checklist.sh — Article 5.10 verification: computes anchor sha + every hero sha, asserts each per slide_spec.image_source declaration. Replaces 5 separate shasum calls + sliding logic. MODE=render-check SLUG=<slug> bash _audit-checklist.sh — verifies all PNG renderings exist + 1080×1350 dimensions via sips. Replaces sips loop. MODE=final-audit SLUG=<slug> bash _audit-checklist.sh — Step 0 self-audit: counts Agent calls, NB queries, imagegen sessions, anchor reuse declared, placeholders reused. Outputs the 4 self-audit lines.

### [19] source `d0adf453…`

> Output is structured (KEY=value lines), parse via grep '^KEY=' . Exit code 0 = PASS, non-zero = audit failed (orchestrator must abort and report). Hard rule : in Step 0, run MODE=preflight ONCE. After Step 4, run MODE=hero-sha ONCE. After Playwright render, run MODE=render-check ONCE. Before READY emission, run MODE=final-audit ONCE. That is 4 audit Bash calls total , not 30+. Any verification you can derive from the script's output, do NOT re-run separately. Contract A — Fan-out (mandatory) You MUST invoke the four specialist subagents through the Agent tool. Inline replacement of their work is forbidden, even if you "could do it faster". The fan-out is what we're testing — not the artifact quality.

### [20] source `d0adf453…`

> ~/.claude/agents/wr2-design-architect-resources/deep-research.md — academic + industry research synthesis. ~/.claude/agents/wr2-design-architect-resources/architecture-patterns.md — multi-vendor architecture patterns. NB-DESIGN-AGENT ( 815b081c-d477-48b0-9780-45f12c1d664f ) — 13 curated sources on agent design, accessible via mcp__notebooklm-mcp-cli__chat . Failure mode If you cannot produce a carousel that passes critic panel after 2 retries: Write STATUS: needs_human_edit to the output slides.json . POST to http://localhost:8765/api/flag-needs-human-edit with {item_id, reason, retry_count, critic_report_path} so Damar's queue UI shows the yellow pill. Surface the issue clearly to the user (which rubric failed, which slides). STOP.

### [21] source `d0adf453…`

> Hard fail on rubric 1 or 2 → return slides to layout-composer with verbal feedback. Soft fail (rubric 3 or 4) → flag for human review queue, do NOT block. Max 2 retry rounds. After 2 retries, surface the carousel with STATUS: needs_human_edit AND POST to the local queue server so Damar's UI flags the row: If queue server is unreachable (server not running on Pro), still write STATUS: needs_human_edit to slides.json and surface clearly to user. Never infinite-loop. Never claim success on a flagged carousel.

### [22] source `d564912c…`

> Runs when the auto mode classifier denies a tool call. This hook only fires in auto mode: it does not run when you manually deny a permission dialog, when a PreToolUse hook blocks a call, or when a deny rule matches. Use it to log classifier denials, adjust configuration, or tell the model it may retry the tool call. Matches on tool name, same values as PreToolUse. PermissionDenied input In addition to the common input fields , PermissionDenied hooks receive tool_name , tool_input , tool_use_id , and reason .

### [23] source `6f16fd65…`

> 2.1.89 April 1, 2026 Added "defer" permission decision to PreToolUse hooks — headless sessions can pause at a tool call and resume with -p --resume to have the hook re-evaluate Added CLAUDE_CODE_NO_FLICKER=1 environment variable to opt into flicker-free alt-screen rendering with virtualized scrollback Added PermissionDenied hook that fires after auto mode classifier denials — return {retry: true} to tell the model it can retry Added named subagents to @ mention typeahead suggestions Added MCP_CONNECTION_NONBLOCKING=true for -p mode to skip the MCP connection wait entirely, and bounded --mcp-config server connections at 5s instead of blocking on the slowest server Auto mode: denied commands now show a notification and appear in /permissions → Recent tab where you can retry with r Fixed Edit(//path/**) and Read(//path/**) allow rules to check the resolved symlink target, not just the requested path Fixed voice push-to-talk not activating for some modifier-combo bindings, and voice mode on Windows failing with “WebSocket upgrade rejected with HTTP 101” Fixed Edit/Write tools doubling CRLF on Windows and stripping Markdown hard line breaks (two trailing spaces) Fixed StructuredOutput schema cache bug causing ~50% failure rate when using multiple schemas Fixed memory leak where large JSON inputs were retained as LRU cache keys in long-running sessions Fixed a crash when removing a message from very large session files (over 50MB) Fixed LSP server zombie state after crash — server now restarts on next request instead of failing until session restart Fixed prompt history entries containing CJK or emoji being silently dropped when they fall on a 4KB boundary in ~/.claude/history.jsonl Fixed /stats undercounting tokens by excluding subagent usage, and losing historical data beyond 30 days when the stats cache format changes Fixed -p --resume hangs when the deferred tool input exceeds 64KB or no deferred marker exists, and -p --continue not resuming deferred tools Fixed claude-cli:// deep links not opening on macOS Fixed MCP tool errors truncating to only the first content block when the server returns multi-element error content Fixed skill reminders and other system context being dropped when sending messages with images via the SDK Fixed PreToolUse/PostToolUse hooks to receive file_path as an absolute path for Write/Edit/Read tools, matching the documented behavior Fixed autocompact thrash loop — now detects when context refills to the limit immediately after compacting three times in a row and stops with an actionable error instead of burning API calls Fixed prompt cache misses in long sessions caused by tool schema bytes changing mid-session Fixed nested CLAUDE.md files being re-injected dozens of times in long sessions that read many files Fixed --resume crash when transcript contains a tool result from an older CLI version or interrupted write Fixed misleading “Rate limit reached” message when the API returned an entitlement error — now shows the actual error with actionable hints Fixed hooks if condition filtering not matching compound commands ( ls && git push ) or commands with env-var prefixes ( FOO=bar git push ) Fixed collapsed search/read group badges duplicating in terminal scrollback during heavy parallel tool use Fixed notification invalidates not clearing the currently-displayed notification immediately Fixed prompt briefly disappearing after submit when background messages arrived during processing Fixed Devanagari and other combining-mark text being truncated in assistant output Fixed rendering artifacts on main-screen terminals after layout shifts Fixed voice mode failing to request microphone permission on macOS Apple Silicon Fixed Shift+Enter submitting instead of inserting a newline on Windows Terminal Preview 1.25 Fixed periodic UI jitter during streaming in iTerm2 when running inside tmux Fixed PowerShell tool incorrectly reporting failures when commands like git push wrote progress to stderr on Windows PowerShell 5.1

### [24] source `d564912c…`

> PostToolBatch decision control PostToolBatch hooks can inject context for Claude. In addition to the JSON output fields available to all hooks, your hook script can return these event-specific fields: Field Description additionalContext Context string injected once before the next model call. See Add context for Claude for delivery details, what to put in it, and how resumed sessions handle past values Returning decision: "block" or continue: false stops the agentic loop before the next model call. PermissionDenied

### [25] source `c78af240…`

> Name of the tool that was denied tool_use_id string ID of the tool_use block this denial answers agent_id string Subagent ID when the denied call originated inside a subagent. Mirrors the field on can_use_tool for host-side routing decision_reason_type string Discriminator for the component that decided, such as "rule" , "mode" , "classifier" , or "asyncAgent" decision_reason string Human-readable reason from the deciding component, when available message string Rejection message returned to the model in the tool_result

### [26] source `d564912c…`

> Name of the event that fired When running with --agent or inside a subagent, two additional fields are included: Field Description agent_id Unique identifier for the subagent. Present only when the hook fires inside a subagent call. Use this to distinguish subagent hook calls from main-thread calls. agent_type Agent name (for example, "Explore" or "security-reviewer" ). Present when the session uses --agent or the hook fires inside a subagent. For subagents, the subagent's type takes precedence over the session's --agent value. For custom subagents , this is the name field from the agent's frontmatter, not the filename.

### [27] source `4001017f…`

> Effective interventions. Two interventions proved effective at supplying the missing tacit knowledge: Literature guidance (Task 1): Providing a reference paper and asking the agent to extract methodology into experience notes. The agent correctly identified sigma-based selection bands and other key parameters, and applied them in subsequent active learning iterations. This leverages the agent's strength in reading comprehension to compensate for its lack of domain experience. Expert-specified constraints (Tasks 1 and 2): Adding specific requirements to the task description (“at least 20 ps per MD trajectory”; “verify convergence with a pilot MD”). These one-sentence constraints encode tacit knowledge as explicit instructions, dramatically improving result quality with minimal human effort.

### [28] source `c78af240…`

> SDKPermissionDeniedMessage Stream event emitted when the permission system auto-denies a tool call without an interactive prompt. Use it to render the denial in your UI as it happens, rather than only observing the is_error tool result that follows. The interactive ask path reaches your application separately through the canUseTool callback. Denials issued by a PreToolUse hook are not reported through this event. This event requires Claude Code v2.1.136 or later. Field Type Description tool_name string

### [29] source `6f0873fe…`

> Supported frontmatter fields The following fields can be used in the YAML frontmatter. Only name and description are required. <cited_table>

### [30] source `2ad7dcc3…`

> <cited_table>

### [31] source `d564912c…`

> Field Description watchPaths Array of absolute paths. Replaces the current dynamic watch list (paths from your matcher configuration are always watched). Use this when your hook script discovers additional files to watch based on the changed file FileChanged hooks have no decision control. They cannot block the file change from occurring. WorktreeCreate When you run claude --worktree or a subagent uses isolation: "worktree" , Claude Code creates an isolated working copy using git worktree . If you configure a WorktreeCreate hook, it replaces the default git behavior, letting you use a different version control system like SVN, Perforce, or Mercurial. Because the hook replaces the default behavior entirely, .worktreeinclude is not processed. If you need to copy local configuration files like .env into the new worktree, do it inside your hook script. The hook must return the absolute path to the created worktree directory. Claude Code uses this path as the working directory for the isolated session. Command hooks print it on stdout; HTTP hooks return it via hookSpecificOutput.worktreePath . This example creates an SVN working copy and prints the path for Claude Code to use. Replace the repository URL with your own:

### [32] source `23608d41…`

> -------------------------------------------------------------------------------- name: Plist live env paths must reference main checkout, NEVER worktree description: Sub-session che modifica plist live setta PYTHONPATH/ORGANISM_RULES_PATH al proprio worktree path. Quando worktree muore (auto-cleanup post-merge o manual remove), daemon entra in error loop FileNotFoundError. Pattern P1 verificato 2026-05-08 04:00→08:24. type: feedback originSessionId: 4f7ba8d0-464c-4ff4-bcb9-152c25d3c709 Plist live env paths — main checkout only

### [33] source `b67fe2b2…`

> fact-checker wrote round0 to disk + went idle WITHOUT SendMessage to lead. source-auditor did SendMessage as instructed. Fix v2 : rely on disk-state polling, not SendMessage, as canonical delivery signal. How to apply (v2 template) For future cross-LLM verifier runs on Bali Zero claims: Create claim file: ~/Desktop/nuzantara/research/verification/<YYYY-MM-DD>-<slug>/CLAIM.md (convention adopted from 2026-05-13) Open fresh terminal: claude --teammate-mode tmux Reuse the LEAD-PROMPT template from ~/Desktop/nuzantara/research/dev-tools/pilot-cross-llm-2026-05-12/LEAD-PROMPT.md (adapt CLAIM path + output dir) Lead spawns 4 teammate with subagent reuse, output to /tmp/pilot-cross-llm/round0-<name>.json After 3 rounds OR convergence, lead writes VERDICT-TABLE + ROUND-LOG + EVALUATION Clean up team
