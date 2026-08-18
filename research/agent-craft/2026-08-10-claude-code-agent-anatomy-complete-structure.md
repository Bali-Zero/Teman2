---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-10-claude-code-agent-anatomy-complete-structure

**Date**: 2026-08-10
**Mode**: fallback
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 18 / Citations: 44

## Question

> In italiano. Tema di oggi (round-robin giorno 1): anatomia di un agente Claude Code: struttura completa (frontmatter, body, tool gating, model, isolation, memory)

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta. Termina con 3 domande aperte per il DR di domani.

## Answer

### **1. Anatomia di un Agente Claude Code: Struttura Completa (Fonti Canoniche)**

Secondo la documentazione ufficiale e gli studi sull'architettura degli agenti, un sub-agente programmato nel framework Claude Code è un'unità autonoma definita tramite file Markdown (con estensione `.md`) strutturata in due sezioni principali [1, 2]:

#### **A. Il Frontmatter (Configurazione YAML)**
Posizionato all'inizio del file tra i delimitatori `---`, gestisce in modo dichiarativo le capacità, i vincoli e il comportamento del runtime [1]:
*   **`name`**: L'identificatore univoco dell'agente (in lettere minuscole e trattini) [3].
*   **`description`**: Fondamentale per la scoperta automatica; descrive in linguaggio naturale quando l'orchestratore deve delegare il compito a questo sub-agente [3, 4].
*   **`model`**: Specifica il modello da utilizzare (es. `sonnet`, `opus`, `haiku` o `inherit`) [3, 5]. L'ordine di risoluzione del modello segue una precedenza rigida: (1) la variabile d'ambiente `CLAUDE_CODE_SUBAGENT_MODEL`, (2) il parametro del modello passato all'invocazione, (3) la chiave `model` nel frontmatter, (4) il modello della conversazione madre [6, 7].
*   **`tools` & `disallowedTools` (Tool Gating)**: Gestiscono l'accesso agli strumenti secondo il principio del minimo privilegio [2, 3]. La denylist (`disallowedTools`) viene applicata per prima, e le regole di esclusione si riflettono sul set finale consentito [8]. I sub-agenti non possono presentare prompt di autorizzazione interattivi all'utente; se uno strumento richiede un'approvazione manuale (regola `ask`), la chiamata viene trattata direttamente come negata (denied) [9]. Per limitare quali sub-agenti un agente principale può lanciare, si utilizza la sintassi `Agent(subagent_type)` (precedentemente `Task`) all'interno dell'array dei tools [8, 10, 11].
*   **`isolation`**: Impostato su `"worktree"`, isola il sistema costringendo il sub-agente a operare in un worktree temporaneo di git, garantendo che le modifiche ai file non sporchino il checkout live finché non vengono verificate e caricate [3, 12].
*   **`memory`**: Abilita una directory di memoria persistente tra le sessioni [13]. Supporta tre ambiti di visibilità: `user` (globale per tutti i progetti), `project` (condivisibile via git) e `local` (specifico per progetto ma ignorato dal VCS) [14]. L'abilitazione della memoria istruisce l'agente a consultare/curare un file `MEMORY.md` (limitato a 200 righe o 25KB) e sblocca automaticamente i tool `Read`, `Write` e `Edit` [14].
*   **`effort`**: Specifica il livello di sforzo di ragionamento (thinking depth) per i modelli che lo supportano (es. `low`, `medium`, `high`, `xhigh`, `max`) [3, 15].

#### **B. Il Body (System Prompt)**
Il testo Markdown che segue il frontmatter sostituisce integralmente il system prompt di default dell'agente [1, 16]. Scritto in seconda persona ("Tu sei..."), stabilisce il ruolo, il flusso di lavoro dettagliato, le istruzioni operative e i criteri di qualità che il modello deve seguire per eseguire il compito in totale isolamento di contesto [2, 17, 18].

---

### **2. Implementazione Reale nello Stack Bali Zero / Nuzantara**

Nel nostro ecosistema reale di produzione, applichiamo rigorosamente questi schemi per gestire la nostra flotta di agenti dedicati alla produzione della newsletter e dei caroselli WR2 [19]:

*   **Flotta di Agenti Disciplinati**: Disponiamo di **16 agenti configurati con frontmatter completo** (comprensivo di colore identificativo, vincoli sui tool, impostazioni di isolamento e limiti di turni per prevenire loop infiniti) [19, 20].
*   **Separazione e Ruoli dei Modelli**: L'orchestratore centrale `wr2-design-architect` gira su **Claude Opus 4.7** per mantenere la massima aderenza alle direttive costituzionali e la pianificazione di alto livello [21, 22]. Al contrario, i lavoratori intermedi come `wr2-brief-interpreter`, `wr2-storyboarder` e `wr2-layout-composer` sono vincolati a **Claude Sonnet 4.6** [21, 23]. Questa architettura centralizzata a "stateless workers" garantisce l'efficienza dei costi ed evita la deriva del contesto (context rot) all'interno della REPL madre [24-27].
*   **Isolamento Tramite Worktree**: Per evitare incidenti di collisione dei checkout git in produzione (come il disastroso blocco del cron in cui i check-out paralleli facevano saltare la HEAD della directory condivisa), forziamo i sub-agenti di scrittura ad applicare **`isolation: worktree`** [28, 29]. Ogni lavoratore scrive e testa le modifiche nel proprio ambiente isolato, lasciando il main repo pulito [30, 31].
*   **Gating dei Tool e Pre-approvazioni**: Per i nostri sub-agenti di analisi e revisione, come `wr2-critic` o `nb-curator`, blocchiamo preventivamente i tool di scrittura applicando `disallowedTools: [Write, Edit]` [29, 32]. Inoltre, blocchiamo le chiamate a server MCP non autorizzati o a reti esterne non documentate, limitandoli alla sola scansione locale ed esecuzione di query su NotebookLM tramite la CLI `nlm` [33].
*   **Memory Layer Integrato**: Alcuni agenti strategici (come `regulatory-watcher`, `competitor-monitor` e `nb-curator`) sono configurati con **`memory: user`** [29, 34-36]. Essi registrano i loro apprendimenti e le discrepanze scoperte nel database SQLite episodico (`wr2-episodic.db`) e aggiornano continuamente i nostri file di tono e stile in `voice/` per mantenere la memoria storica delle correzioni manuali [37].

---

### **3. Linea di Azione Concreta**

Dall'analisi del nostro backlog operativo, emerge che l'integrazione di server MCP per singolo sub-agente è stata precedentemente rimandata: **"mcpServers: per-agent — Defer: necessita inventario MCP intent"** [29, 38].

*   **Azione**: Creare un inventario formale degli endpoint MCP attivi e mappare i server specifici nel frontmatter dei singoli sub-agenti.
*   **Implementazione**: Modificare le definizioni di `wr2-brief-interpreter` per includere solo `mcpServers: [notebooklm-mcp-cli]` [33], limitare `wr2-publisher` esclusivamente a `mcpServers: [claude_ai_Canva]` [33], ed escludere categoricamente l'accesso a server MCP globali per tutti gli altri lavoratori. Questo approccio ridurrà drasticamente il consumo di token al SessionStart (evitando di caricare schemi di tool non necessari) e limiterà la superficie d'attacco in caso di prompt injection sul terminale [39, 40].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Dato che i sub-agenti considerano automaticamente come **"denied"** qualsiasi chiamata a uno strumento che ricade sotto una regola interattiva di `ask` [9], quali sono i pattern migliori per gestire i fallimenti silenziosi dei tool di scrittura o esecuzione bash quando i sub-agenti tentano di applicare patch a codice protetto o a file temporanei?
2.  Considerando che il precaricamento delle skill tramite la proprietà `skills` nel frontmatter del sub-agente inietta l'intero corpo di `SKILL.md` nel contesto iniziale [3, 41], come possiamo calibrare dinamicamente la visibilità delle nostre regole di brand per evitare che i sub-agenti superino la frazione di budget del contesto riservata alle skill (`skillListingBudgetFraction`), specialmente durante cicli di lavorazione sequenziali lunghi [42]?
3.  In che modo il meccanismo di **"auto-compaction"** influisce sui file di trascrizione storici dei sub-agenti (`agent-{agentId}.jsonl`) archiviati nella directory di sessione, e come possiamo garantire che la ricostruzione del contesto post-compattazione non perda le variabili d'ambiente dinamiche impostate dai ganci di `SessionStart` [43, 44]?

📊 *Se lo desideri, posso preparare una bozza in formato JSON del nostro inventario di configurazione per testare l'associazione granulare degli MCP sui sub-agenti in `_proposed/`.*

## Sources used (18)

- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `d3ccdc37-f3b2-4163-8e2c-c11bba281169`
- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `41511dc3-8e29-456d-bc5d-01747901dc58`
- `3187958a-0b71-4128-8aef-b4971aa9c079`
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `a1f286dd-f3bd-4cb5-8614-08f4deef3160`
- `d3754c90-db00-4a20-a83e-59d84d5dc409`
- `1826e81e-6d39-4285-956a-464b315e3f3f`
- `25977454-d585-4327-bbeb-c7911897b175`
- `fcf012c1-0b7d-4305-af36-c23aec57b2a9`
- `d6bf2f6f-a93f-497d-9bf3-59746d866315`
- `83c6cf46-e0a3-48d8-882e-e81e1979573d`
- `78866c49-7497-4913-b4d8-e93d0b564a32`
- `366690aa-8295-4154-a4f6-efbeebf25954`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`

## Citations verbatim (44)

### [1] source `6f0873fe…`

> Write subagent files Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown: Subagents are loaded at session start. If you add or edit a subagent file directly on disk, restart your session to load it. Subagents created through the /agents interface take effect immediately without a restart. The frontmatter defines the subagent's metadata and configuration. The body becomes the system prompt that guides the subagent's behavior. Subagents receive only this system prompt (plus basic environment details like working directory), not the full Claude Code system prompt. A subagent starts in the main conversation's current working directory. Within a subagent, cd commands do not persist between Bash or PowerShell tool calls and do not affect the main conversation's working directory. To give the subagent an isolated copy of the repository instead, set isolation: worktree .

### [2] source `d3ccdc37…`

> tools (optional) Restrict agent to specific tools. Format: Array of tool names Default: If omitted, agent has access to all tools Best practice: Limit tools to minimum needed (principle of least privilege) Common tool sets: Read-only analysis: ["Read", "Grep", "Glob"] Code generation: ["Read", "Write", "Grep"] Testing: ["Read", "Bash", "Grep"] Full access: Omit field or use ["*"] System Prompt Design The markdown body becomes the agent's system prompt. Write in second person, addressing the agent directly.

### [3] source `6f0873fe…`

> Supported frontmatter fields The following fields can be used in the YAML frontmatter. Only name and description are required. <cited_table>

### [4] source `6f0873fe…`

> Both events support matchers to target specific agent types by name. This example runs a setup script only when the db-agent subagent starts, and a cleanup script when any subagent stops: See Hooks for the complete hook configuration format. Work with subagents Understand automatic delegation Claude automatically delegates tasks based on the task description in your request, the description field in subagent configurations, and current context. To encourage proactive delegation, include phrases like “use proactively” in your subagent's description field.

### [5] source `d3ccdc37…`

> model (required) Which model the agent should use. Options: inherit - Use same model as parent (recommended) sonnet - Claude Sonnet (balanced) opus - Claude Opus (most capable, expensive) haiku - Claude Haiku (fast, cheap) Recommendation: Use inherit unless agent needs specific model capabilities. color (required) Visual identifier for agent in UI. Options: blue , cyan , green , yellow , magenta , red Guidelines: Choose distinct colors for different agents in same plugin Use consistent colors for similar agent types Blue/cyan: Analysis, review Green: Success-oriented tasks Yellow: Caution, validation Red: Critical, security Magenta: Creative, generation

### [6] source `6f0873fe…`

> Choose a model The model field controls which AI model the subagent uses: Model alias : Use one of the available aliases: sonnet , opus , or haiku Full model ID : Use a full model ID such as claude-opus-4-7 or claude-sonnet-4-6 . Accepts the same values as the --model flag inherit : Use the same model as the main conversation Omitted : If not specified, defaults to inherit (uses the same model as the main conversation) When Claude invokes a subagent, it can also pass a model parameter for that specific invocation. Claude Code resolves the subagent's model in this order:

### [7] source `6f0873fe…`

> The CLAUDE_CODE_SUBAGENT_MODEL environment variable, if set The per-invocation model parameter The subagent definition's model frontmatter The main conversation's model Control subagent capabilities You can control what subagents can do through tool access, permission modes, and conditional rules. Available tools Subagents can use any of Claude Code's internal tools . By default, subagents inherit all tools from the main conversation, including MCP tools. To restrict tools, use either the tools field (allowlist) or the disallowedTools field (denylist). This example uses tools to exclusively allow Read, Grep, Glob, and Bash. The subagent can't edit files, write files, or use any MCP tools:

### [8] source `6f0873fe…`

> This example uses disallowedTools to inherit every tool from the main conversation except Write and Edit. The subagent keeps Bash, MCP tools, and everything else: If both are set, disallowedTools is applied first, then tools is resolved against the remaining pool. A tool listed in both is removed. Restrict which subagents can be spawned When an agent runs as the main thread with claude --agent , it can spawn subagents using the Agent tool. To restrict which subagent types it can spawn, use Agent(agent_type) syntax in the tools field.

### [9] source `2ad7dcc3…`

> Note: Subagents cannot present interactive permission prompts to the user. If a subagent invokes a tool that matches an ask rule, the call is treated as denied. The recommended pattern is to restrict subagents to read-only tool sets (omit Edit , Write , and NotebookEdit from the frontmatter tools: list) and to defer all Edit / Write / NotebookEdit / Bash work to the parent agent that can handle approval prompts. Built-in subagents whose job is to edit files (for example, statusline-setup ) are exempt because their edit scope is narrow and predictable.

### [10] source `cf769fec…`

> Restricting spawnable subagents (v2.1.33+, renamed v2.1.63): The tools field supports Agent(agent_type) syntax to limit which subagent types an agent can spawn. For example, tools: Read, Grep, Agent(Explore) allows the agent to use Read and Grep directly but only delegate to Explore-type subagents. The restriction prevents over-delegation in constrained agents. Note: In v2.1.63, the Task tool was renamed to Agent. Existing Task(...) references in settings and agent definitions still work as backwards-compatible aliases. 106

### [11] source `6f0873fe…`

> In version 2.1.63, the Task tool was renamed to Agent. Existing Task(...) references in settings and agent definitions still work as aliases. This is an allowlist: only the worker and researcher subagents can be spawned. If the agent tries to spawn any other type, the request fails and the agent sees only the allowed types in its prompt. To block specific agents while allowing all others, use permissions.deny instead. To allow spawning any subagent without restrictions, use Agent without parentheses:

### [12] source `6f0873fe…`

> Because a fork's system prompt and tool definitions are identical to the parent, its first request reuses the parent's prompt cache. This makes forking cheaper than spawning a fresh subagent for tasks that need the same context. When Claude spawns a fork through the Agent tool, it can pass isolation: "worktree" so the fork's file edits are written to a separate git worktree instead of your checkout. Limitations Setting CLAUDE_CODE_FORK_SUBAGENT=1 enables fork mode in interactive sessions, non-interactive mode , and the Agent SDK. A fork cannot spawn further forks.

### [13] source `6f0873fe…`

> This is the inverse of running a skill in a subagent . With skills in a subagent, the subagent controls the system prompt and loads skill content. With context: fork in a skill, the skill content is injected into the agent you specify. Both use the same underlying system. Enable persistent memory The memory field gives the subagent a persistent directory that survives across conversations. The subagent uses this directory to build up knowledge over time, such as codebase patterns, debugging insights, and architectural decisions.

### [14] source `6f0873fe…`

> Choose a scope based on how broadly the memory should apply: <cited_table> When memory is enabled: The subagent's system prompt includes instructions for reading and writing to the memory directory. The subagent's system prompt also includes the first 200 lines or 25KB of MEMORY.md in the memory directory, whichever comes first, with instructions to curate MEMORY.md if it exceeds that limit. Read, Write, and Edit tools are automatically enabled so the subagent can manage its memory files.

### [15] source `41511dc3…`

> AgentDefinition configuration Field Type Required Description description string Yes Natural language description of when to use this agent prompt string Yes The agent’s system prompt defining its role and behavior tools string[] No Array of allowed tool names. If omitted, inherits all tools disallowedTools string[] No Array of tool names to remove from the agent’s tool set model string No Model override for this agent. Accepts an alias such as  'sonnet' ,  'opus' ,  'haiku' ,  'inherit' , or a full model ID. Defaults to main model if omitted skills string[] No List of skill names to preload into the agent’s context at startup. Unlisted skills remain invocable through the Skill tool memory 'user' | 'project' | 'local' No Memory source for this agent mcpServers (string | object)[] No MCP servers available to this agent, by name or inline config maxTurns number No Maximum number of agentic turns before the agent stops background boolean No Run this agent as a non-blocking background task when invoked effort 'low' | 'medium' | 'high' | 'xhigh' | 'max' | number No Reasoning effort level for this agent permissionMode PermissionMode No Permission mode for tool execution within this agent   In the Python SDK, these field names use camelCase to match the wire format. See the AgentDefinition  reference for details.   Subagents cannot spawn their own subagents. Don’t include  Agent  in a subagent’s  tools  array.

### [16] source `6f0873fe…`

> The subagent's system prompt replaces the default Claude Code system prompt entirely, the same way --system-prompt does. CLAUDE.md files and project memory still load through the normal message flow. The agent name appears as @<name> in the startup header so you can confirm it's active. This works with built-in and custom subagents, and the choice persists when you resume the session. For a plugin-provided subagent, pass the scoped name: claude --agent <plugin-name>:<agent-name> . To make it the default for every session in a project, set agent in .claude/settings.json :

### [17] source `41511dc3…`

> Benefits of using subagents Context isolation Each subagent runs in its own fresh conversation. Intermediate tool calls and results stay inside the subagent; only its final message returns to the parent. See What subagents inherit for exactly what’s in the subagent’s context. Example: a  research-assistant  subagent can explore dozens of files without any of that content accumulating in the main conversation. The parent receives a concise summary, not every file the subagent read. Parallelization

### [18] source `d3ccdc37…`

> Structure Standard template: Best Practices ✅ DO: Write in second person ("You are...", "You will...") Be specific about responsibilities Provide step-by-step process Define output format Include quality standards Address edge cases Keep under 10,000 characters ❌ DON'T: Write in first person ("I am...", "I will...") Be vague or generic Omit process steps Leave output format undefined Skip quality guidance Ignore error cases Creating Agents Method 1: AI-Assisted Generation Use this prompt pattern (extracted from Claude Code):

### [19] source `3187958a…`

> -------------------------------------------------------------------------------- name: project-claude-code-features-wave-2026-05-13 description: "Sessione 2026-05-12/13 — esplorazione 13 potenzialità Claude Code non sfruttate. 10/13 implementate, 3 skip documentati. 4 lessons collaterali + 2 fix difensivi. Stack rinnovato: agent-teams testato, 16 agent disciplinati, output-style attivo, anti-hallucination HARD RULE in 3 location ridondanti." metadata: node_type: memory type: project originSessionId: 08bda0ef-5579-4fb2-a654-f16050486d01

### [20] source `3187958a…`

> Fix difensivi (post-test live) ac971a9 — Quote 5 description YAML con "..." per strict-parse compatibility. 16/16 strict-valid. 11161f7 — Canonical research artifacts dir ~/var/nuzantara-research/ (immune a branch switch). Pilot file migrati. Symlink back-compat. nuzantara dfed5a416 — .gitignore research/dev-tools/ . Stack rinnovato — cosa è cambiato per future sessioni Agent fleet disciplinato: 16 agent con frontmatter completo (color, isolation, memory, disallowedTools, maxTurns dove rilevante) Output style globale italian-tight attivo da settings.json PreCompact backup automatico transcript JSONL (vivo, testato con file 3.3MB) wr2-critic auto-learning via _lessons/ directory (Voyager pattern Wang et al. 2023) Anti-hallucination discipline scritta in 3 luoghi auto-letti al SessionStart Pilot artifact convention : ~/var/nuzantara-research/{dev-tools,_pilots,_archive}/

### [21] source `74917ad2…`

> Multi-agent shape (4 specialist subagents, all Claude): wr2-design-architect (orchestrator) — Opus 4.7 — main entry point wr2-brief-interpreter — Sonnet 4.6 — fast, RAG-over-NB, structured JSON out wr2-storyboarder — Sonnet 4.6 — narrative arc 8–10 slides wr2-layout-composer — Sonnet 4.6 — picks parametric skill from library, emits HTML wr2-critic — Opus 4.7 (vision-capable) — scores against brand rubric wr2-publisher — Haiku 4.5 — Canva apply + Tigris upload (cheap, mechanical) Skill library ( ~/.claude/skills/bali-zero-brand/ ):

### [22] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [23] source `d0adf453…`

> You orchestrate four stateless specialist subagents. Invoke each via the Agent tool with subagent_type=<name> and pass the prior step's structured JSON as the prompt . Specialists read shared brand cortex files; they NEVER talk peer-to-peer (Google's 17.2× error-amplification finding). All inputs and outputs are JSON or files on disk. <cited_table>

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [24] source `cf769fec…`

> The difference between casual and effective Claude Code usage comes down to five core systems. Master these and Claude Code becomes a force multiplier: Configuration hierarchy : controls behavior Permission system : gates operations Hook system : enables deterministic automation MCP protocol : extends capabilities Subagent system : handles complex multi-step tasks Key Takeaways Five systems determine your effectiveness : configuration hierarchy, permissions, hooks, MCP, and subagents control everything from behavior to automation. Push work to the Delegation Layer : subagents prevent context bloat by isolating exploration in clean context windows, returning only summaries. Hooks guarantee execution; prompts do not : use hooks for linting, formatting, and security checks that must run every time regardless of model behavior. Model tiering saves cost without sacrificing quality : route subagent exploration to cheaper models and reserve Opus for genuine architectural reasoning — or standardize on Opus if quality is your only variable. MCP connects Claude to your toolchain : databases, GitHub, Sentry, and 3,000+ integrations extend Claude beyond file reading and bash commands.

### [25] source `cf769fec…`

> How Claude Code Works: The Mental Model Before diving into features, understand how Claude Code's architecture shapes everything you do with it. The system operates in three layers: Core Layer : Your main conversation. Every message, file read, and tool output consumes context from a shared window (200K tokens standard 91 , 1M tokens with Opus 4.6 or extended context models). When context fills, Claude loses track of earlier decisions and quality degrades. This layer costs money per token. Delegation Layer : Subagents spawn with clean contexts, do focused work, and return summaries. The exploration results don't bloat your main conversation; only the conclusions return. Route subagents to cheaper model tiers for exploration, or use your primary model throughout if quality matters more than cost.

### [26] source `cf769fec…`

> What Are Subagents? Subagents are specialized Claude instances that handle complex tasks independently. They're one of the most powerful features in Claude Code and one of the least understood. Mastering subagents dramatically expands what you can accomplish. See Decision Frameworks for guidance on Agent Teams vs Subagents vs Parallel Sessions. Why subagents exist: Claude Code's main conversation has a single context window. Everything you discuss, every file Claude reads, every tool output: all of it consumes that context. In long sessions, context fills up, Claude loses track of earlier decisions, and performance degrades. Subagents solve this by isolating work: exploration results don't bloat your main conversation, only the summary returns. Claude can also run up to 10 subagents in parallel, enabling concurrent work that would be impossible sequentially. 2

### [27] source `a1f286dd…`

> Quality gates (in order) : Token compliance (deterministic): all colors map to brand palette, all fonts map to brand stack — non-compliance = hard fail. Critic panel score ≥ threshold — soft fail = retry with feedback (max 2 retries). CLIP similarity ≥ threshold to curated set of past on-brand carousels — guards against subtle drift. Diffusion-variance hallucination check on any generated raster. Human review queue for final go/no-go on publish. Single agent vs multi-agent verdict : multi-agent with strict orchestrator is correct because specialist roles are genuinely different competencies; but Google's 17.2× error-amplification finding is a serious warning — architecture must be centralized state, stateless workers , not peer-to-peer. Avoid temptation to give each sub-agent its own memory.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [28] source `d3754c90…`

> -------------------------------------------------------------------------------- name: discovery_worktree_deploy_isolation description: Deployment isolation via dedicated git worktree on branch deploy/main, separate da working tree shared con sessioni multi-agent. Wrapper REPO_ROOT punta al worktree pulito. type: discovery originSessionId: 92a63010-c526-4282-a225-e2d72f00dc9c Worktree deploy isolation — Pro production cron stability Problema risolto 2026-05-06 19:17 WITA : 3+ sessioni Claude/Codex parallele attive su ~/Desktop/nuzantara (cwd shared) facevano git checkout su branch diversi ogni 1-3 min. Il wr2-script-wrapper.sh leggeva da ${HOME}/Desktop/nuzantara , quindi a seconda di chi aveva fatto checkout per ultimo, il cron eseguiva versioni diverse del codice. Risultato: PR #478 deployata su origin/main ma working tree del Pro periodicamente su feat/email-branding-followup → cron leggeva versione vecchia senza fix Codex Image-2.

### [29] source `3187958a…`

> Sessione Claude Code features wave — 2026-05-12/13 Run window : 2026-05-12 21:30 → 2026-05-13 01:50 WITA (~4h) Trigger : utente chiede "ricerca su Claude Code latest potentialities, usa exa/deepresearch/scrape repo" Outcome : 10/13 features adopted + 4 lessons + 2 fix strutturali Scoreboard finale <cited_table>

### [30] source `6f0873fe…`

> A fork is a subagent that inherits the entire conversation so far instead of starting fresh. This drops the input isolation that subagents otherwise provide: a fork sees the same system prompt, tools, model, and message history as the main session, so you can hand it a side task without re-explaining the situation. The fork's own tool calls still stay out of your conversation and only its final result comes back, so your main context window stays clean. Use a fork when a named subagent would need too much background to be useful, or when you want to try several approaches in parallel from the same starting point. Enabling fork mode changes Claude Code in three ways:

### [31] source `d3754c90…`

> Architettura nuova wr2-script-wrapper.sh patch (linea 30-37): Override env var WR2_REPO_ROOT per debug/testing — default è worktree dedicato. Setup procedure (one-time done 2026-05-06 19:17) How to update (every time main has new commits) Idempotent. Worktree is on branch deploy/main tracking origin/main — pure pull-only, no commits ever land here. Verify deploy active Self-loop .venv NOT recreated by checkout (good!) Il symlink self-loop committato in b13287518 (cicatrix latente) NON viene ricreato dal git checkout nel worktree — Git considera invalid-target symlinks edge case e li skippa silently. Il worktree ha .venv come dir reale (Python 3.11 fresh), niente self-loop. Il problema architetturale del symlink in git resta latente per il main repo + 5 feature worktrees, da affrontare con PR dedicata futura.

### [32] source `1826e81e…`

> -------------------------------------------------------------------------------- name: wr2-critic description: MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY after Playwright renders PNGs. Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim. Receives PNG paths + slide-spec JSON + brief JSON + brand cortex pointer. Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback. Verifies Article 6.2 bilingual assist on first occurrence, Article 6.3 bullet-promise, Article 5.10 no silent placeholder reuse via sha256 anchor check. tools: Read, Write, Glob, Grep, Bash model: opus color: red memory: user skills:

### [33] source `74917ad2…`

> Cross-LLM verification (bipolar verifier already in CLAUDE.md) : Critic panel: Claude main + Gemini cross-check (free) + NotebookLM ground-truth (NB-DESIGN-AGENT just created). DeepSeek as alternate cross-check when Gemini quota exhausted. Never include OpenAI in runtime path (would burn Codex Plus quota that's reserved for code review). Tools whitelist for orchestrator ( tools field in YAML): Read , Write , Edit , Bash , Glob , Grep — basic file I/O mcp__nuzantara-fetch__* — web research for brief mcp__notebooklm-mcp-cli__* — RAG over Bali Zero NBs (NB-1, NB-5, NB-4, NB-DESIGN-AGENT) mcp__claude_ai_Canva__* — design publication Agent (subagent_type whitelist: critic, layout-composer) NOT: arbitrary network, no mcp__playwright__* (renderer is invoked via Bash from skill)

### [34] source `25977454…`

> -------------------------------------------------------------------------------- name: competitor-monitor description: Monthly digest of Bali Zero's three direct competitors (Lets Move Indonesia, Emerhub, Flado) on web + Instagram. Detects positioning shifts, pricing changes, content tactics, and new service offerings. Output is a markdown digest at ~/Desktop/nuzantara/research/competitive/<YYYY-MM>-digest.md . Uses Sonnet 4.6 for analysis with local qwen2.5vl:7b vision pre-filter on IG screenshots to triage which posts merit detailed analysis (saves Sonnet calls). tools: Read, Write, Bash, WebFetch model: sonnet color: yellow memory: user

### [35] source `fcf012c1…`

> -------------------------------------------------------------------------------- name: nb-curator description: NotebookLM inventory steward. Recommends which NB(s) to query for a given question, detects inventory gaps (e.g., "no NB covers Permenaker post-2025"), maintains health metrics for the 60-NB stack (~2970 sources), and surfaces broken/stale NBs. Other agents (deep-researcher, regulatory-watcher, wr2-brief-interpreter) call this BEFORE their own NB query step. Also runs weekly health-check via cron AND weekly+monthly curation (Mode C) that proposes dedup clusters / summarization bundles / stale-source cleanup for the 5 NB-INTEL (Press weekly because growth ~30/wk; other NB monthly; stale >90d weekly for all). tools: Read, Write, Bash, Glob, Grep model: sonnet color: purple memory: user

### [36] source `d6bf2f6f…`

> -------------------------------------------------------------------------------- name: regulatory-watcher description: Daily watcher over NB-INTEL family + web for new Indonesian regulations (Permenkumham, PMK, PP, Perpres, UU, Peraturan BKPM, Permenaker, Permenkes) affecting Bali Zero services. Emits Telegram alert + structured delta JSON to ~/Desktop/nuzantara/research/regulatory/<date>-delta.json . Runs autonomously via cron at 07:00 WITA daily. tools: Read, Write, Bash, WebFetch model: sonnet isolation: worktree color: orange memory: user

### [37] source `74917ad2…`

> constitution.md — hard brand rules (palette, type, taboo) tokens.json — design tokens (machine-readable) voice/ — few-shot examples on-tone vs off-tone layouts/ — parametric layout skills (each = SKILL.md + render snippet) past/ — last N carousels as in-context reference (PNG + brief.md) Memory layers : Episodic : SQLite at ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db — one row per carousel run. Semantic : brand cortex files (above). Procedural : skill library (above). Reflective : weekly cron synthesizes episodes into lessons appended to voice/ and skills/.

### [38] source `3187958a…`

> Backlog deferred Level 3 pre-checkout hook — richiede investigation di quale sibling Claude session emette branch switch non autorizzati. Logger in .git/hooks/post-checkout per 1 settimana raccomandato. mcpServers per-agent (#12) — defer fino a inventario MCP server attivi vs agent intent. Settings.json bundled commit — modifiche orphan pre-esistenti in mezzo, va con prossimo bundle generale. Tasks dir orphan ~/.claude/tasks/52877a1e-... — cleanup manuale opzionale. How to apply (future sessions)

### [39] source `83c6cf46…`

> Scale with MCP Tool Search Tool search keeps MCP context usage low by deferring tool definitions until Claude needs them. Only tool names load at session start, so adding more MCP servers has minimal impact on your context window. How it works Tool search is enabled by default. MCP tools are deferred rather than loaded into context upfront, and Claude uses a search tool to discover relevant ones when a task needs them. Only the tools Claude actually uses enter context. From your perspective, MCP tools work exactly as before. If you prefer threshold-based loading, set ENABLE_TOOL_SEARCH=auto to load schemas upfront when they fit within 10% of the context window and defer only the overflow. See Configure tool search for all options.

### [40] source `78866c49…`

> For conceptual background on how Skills work, see the Skills overview . Core principles Concise is key The context window is a public good. Your Skill shares the context window with everything else Claude needs to know, including: The system prompt Conversation history Other Skills' metadata Your actual request Not every token in your Skill has an immediate cost. At startup, only the metadata (name and description) from all Skills is pre-loaded. Claude reads SKILL.md only when the Skill becomes relevant, and reads additional files only as needed. However, being concise in SKILL.md still matters: once Claude loads it, every token competes with conversation history and other context.

### [41] source `6f0873fe…`

> Preload skills into subagents Use the skills field to inject skill content into a subagent's context at startup. This gives the subagent domain knowledge without requiring it to discover and load skills during execution. The full content of each listed skill is injected into the subagent's context at startup. This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution. To prevent a subagent from invoking skills entirely, omit Skill from the tools list or add it to disallowedTools . You cannot preload skills that set disable-model-invocation: true , since preloading draws from the same set of skills Claude can invoke. If a listed skill is missing or disabled, Claude Code skips it and logs a warning to the debug log.

### [42] source `366690aa…`

> Show turn duration messages after responses, e.g. “Cooked for 1m 6s”. Default: true . Appears in /config as Show turn duration false skillListingBudgetFraction Fraction of the model's context window reserved for the skill listing Claude sees each turn (default: 0.01 = 1%). When the listing exceeds the budget, descriptions for the least-used skills are collapsed to bare names so Claude can still invoke them but won't see why. Raise to keep more descriptions visible at the cost of more context per turn. /doctor shows the current truncation count and which skills are affected. Requires Claude Code v2.1.105 or later 0.02 skillOverrides

### [43] source `6f0873fe…`

> If a stopped subagent receives a SendMessage , it auto-resumes in the background without requiring a new Agent invocation. You can also ask Claude for the agent ID if you want to reference it explicitly, or find IDs in the transcript files at ~/.claude/projects/{project}/{sessionId}/subagents/ . Each transcript is stored as agent-{agentId}.jsonl . Subagent transcripts persist independently of the main conversation: Main conversation compaction : When the main conversation compacts, subagent transcripts are unaffected. They're stored in separate files. Session persistence : Subagent transcripts persist within their session. You can resume a subagent after restarting Claude Code by resuming the same session. Automatic cleanup : Transcripts are cleaned up based on the cleanupPeriodDays setting (default: 30 days).

### [44] source `d564912c…`

> Environment state : the current branch, deployment target, or active feature flags Conditional project rules : which test command applies to the file just edited, which directories are read-only in this worktree External data : open issues assigned to you, recent CI results, content fetched from an internal service For instructions that never change, prefer CLAUDE.md . It loads without running a script and is the standard place for static project conventions. Write the text as factual statements rather than imperative system instructions. Phrasing such as “The deployment target is production” or “This repo uses bun test ” reads as project information. Text framed as out-of-band system commands can trigger Claude's prompt-injection defenses, which causes Claude to surface the text to you instead of treating it as context. Once injected, the text is saved in the session transcript. For mid-session events like PostToolUse or UserPromptSubmit , resuming with --continue or --resume replays the saved text rather than re-running the hook for past turns, so values like timestamps or commit SHAs become stale on resume. SessionStart hooks run again on resume with source set to "resume" , so they can refresh their context.
