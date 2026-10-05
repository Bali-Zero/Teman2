---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-09-15-agent-craft-daily

**Date**: 2026-09-15
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 14 / Citations: 28

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Gestione del ciclo di vita dei Background Subagents (`background: true`)**: Come possiamo monitorare ed ereditare programmaticamente le notifiche di completamento o stallo dei sub-agenti eseguiti in background senza bloccare la REPL dell'orchestratore, evitando race condition sui file di lock del filesystem?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Lifecycle dei Background Subagent e Watchdog)**

Il ciclo di vita dei sub-agenti eseguiti in background (`background: true`) e il controllo della concorrenza nell'Agent SDK e in Claude Code seguono specifiche strutturate per la gestione degli eventi, dei timeout e del filesystem:

*   **Dichiarazione e Comportamento dei Background Subagents (`background: true`):**
    > *"background: Run this agent as a non-blocking background task when invoked"* [1-4]
    > *"Background subagents run concurrently while you continue working. They run with the permissions already granted in the session and auto-deny any tool call that would otherwise prompt."* [5]

*   **Flusso dei Messaggi e Notifiche di Completamento (`task-notification`):**
    > *"When a background task finishes and the SDK injects a synthetic follow-up turn, the resulting SDKResultMessage carries origin: { kind: "task-notification" }. Check this field to distinguish results that answer your prompt from results emitted for background-task follow-ups, so you can route or suppress the latter."* [6]
    > *"SDKTaskNotificationMessage: Notification when a background task completes, fails, or is stopped. Background tasks include run_in_background Bash commands, Monitor watches, and background subagents."* [7]
    > *"Added elapsed duration to background subagent completion notifications (e.g. "Agent completed · 3h 2m 5s")"* [8, 9]

*   **Gestione dello Stallo del Sub-agente (`CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`):**
    > *"CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents."* [10, 11]

*   **Controllo di Fine Esecuzione e Race Condition sui File di Lock:**
    > *"SubagentStop hooks receive stop_hook_active, agent_id, agent_type, agent_transcript_path, and last_assistant_message. ... Returning decision: "block" with a reason keeps the subagent running and delivers reason to the subagent as its next instruction."* [12, 13]
    > *"Fixed an unhandled rejection ( ECOMPROMISED ) when a history or session-log file lock is compromised by clock skew or slow disk"* [14, 15]

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero / Nuzantara**

Nel nostro ecosistema reale di produzione, la gestione dei task asincroni in background presenta dinamiche specifiche che abbiamo affrontato direttamente sul campo:

*   **Notifiche di Lifecycle vs Notifiche di Completamento:**
    Nei nostri esperimenti di orchestrazione con sub-agenti paralleli (es. `project_wave2_pro_2026_04_29`), abbiamo osservato che i sub-agenti in background generano notifiche di avanzamento (*idle notifications*) con una cadenza regolare di 10-30 secondi [16]. Queste notifiche indicano che l'agente è attivo e non devono essere scambiate per il segnale di completamento finale [16].
*   **Affidabilità dello Stato su Disco vs Messaggi tra Agenti:**
    Durante il pilot del verificatore bipolare cross-LLM (`project_pilot_cross_llm_agent_teams_2026_05_13`), abbiamo riscontrato che alcuni sub-agenti in background completavano il loro compito e andavano in stato di riposo (*idle*) scrivendo il proprio output su disco senza inviare il messaggio attivo `SendMessage` all'orchestratore [17, 18]. Questo ha portato alla regola operativa: *"rely on disk-state polling, not SendMessage, as canonical delivery signal"* [18].
*   **Gestione delle Race Condition e dei Lock di Sistema:**
    L'esecuzione simultanea di più sub-agenti in background che tentano di aggiornare le stesse risorse (es. la creazione di issue/PR GitHub o l'aggiornamento di `wr2-episodic.db`) genera finestre di collisione di 5-30 secondi (`lessons_orchestrator_issue_race.md`) [19, 20]. Inoltre, se un sub-agente operante in un worktree temporaneo modifica configurazioni condivise del sistema (come i `.plist` di LaunchD), la cancellazione automatica del worktree al completamento causa un crash-loop per percorsi non trovati (`lessons_plist_worktree_path_trap.md`) [21, 22].

---

### **3. Linea di Azione Concreta: Il "Background Subagent Lifecycle & Lock Guard"**

Per consentire all'orchestratore `wr2-design-architect` di lanciare sub-agenti con `background: true` in totale sicurezza, senza bloccare la REPL e prevenendo la corruzione dei dati su disco, implementeremo un gestore deterministico del ciclo di vita.

#### **Azione**: Implementare il modulo `_background_subagent_guard.py` e configurare gli hook di ciclo di vita.

1.  **Configurazione del Watchdog di Stallo**:
    Impostare esplicitamente la variabile `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS=300000` (5 minuti) nelle opzioni dell'Agent SDK [10, 11]. Se un sub-agente in background si blocca o non produce eventi per più di 5 minuti, l'SDK interromperà l'esecuzione notificando l'errore all'orchestratore con il risultato parziale [10, 11].
2.  **Scrittura Atomica su Disco (Atomic Swap Pattern)**:
    Ogni sub-agente in background scriverà i propri risultati JSON in un file temporaneo (es. `payload.json.tmp`) e ne eseguirà lo scambio atomico (`os.replace`) solo al completamento. L'orchestratore eseguirà il polling sul file finale, evitando di leggere payload incompleti durante la fase di scrittura.
3.  **Integrazione dell'Hook `SubagentStop` per la Notifica Senza Lock**:
    Configurare un hook `SubagentStop` in `.claude/hooks/subagent_stop_handler.py`. Quando il sub-agente termina, l'hook intercetta il campo `last_assistant_message` [12] e aggiorna il database episodico SQLite `wr2-episodic.db` abilitando la modalità WAL (`PRAGMA journal_mode=WAL;`) e impostando un `busy_timeout` di 5000ms. L'hook invia quindi un segnale sintetico all'orchestratore, sbloccando la fase successiva della pipeline senza generare errori di tipo `ECOMPROMISED` o file lock persi [14, 15].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Gestione del Fallback Automatico delle Autorizzazioni in Background**: Poiché i sub-agenti con `background: true` rifiutano automaticamente (`auto-deny`) qualsiasi chiamata a strumenti che richieda un'approvazione interattiva [5], come possiamo strutturare un hook `PermissionDenied` o un meccanismo di escalation per rilanciare automaticamente in foreground il sub-agente fallito senza perdere il contesto già accumulato [23]?
2.  **Propagazione del Caching dei Prompt tra Sessioni Background e Main REPL**: In che modo la nascita e la chiusura rapida di sub-agenti in background influisce sull'indice del Prompt Caching della sessione principale dell'orchestratore, e come possiamo strutturare i loro system prompt per massimizzare il riutilizzo del prefisso di cache globale [24, 25]?
3.  **Pianificazione Multimodale con `Monitor` Tool per i Background Agents**: Come possiamo utilizzare il tool nativo `Monitor` [26-28] in combinazione con i background subagent per ascoltare in tempo reale i log di stdout di un rendering Playwright e innescare un intervento correttivo dell'orchestratore non appena viene rilevato un errore di compilazione CSS, prima ancora del completamento del task?

💡 *Se vuoi, posso preparare la specifica dello script `_background_subagent_guard.py` e testare la simulazione di gestione di un timeout di stallo direttamente nella nostra sandbox.*

## Sources used (14)

- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `c78af240-51bd-4558-a4ed-7c0a82b09c14`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `77e0584d-f93a-4384-a5a5-73d353aba212`
- `a5a300d1-c909-4736-86ce-7aeb659a7c3f`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `6f16fd65-565d-491d-8db8-e2b095a5a064`
- `ab4b8c41-f5fd-4acd-b634-d2e442d8e7f4`
- `b67fe2b2-5ee8-460a-b793-ccb71d1b752d`
- `f223637c-725a-441c-9874-cbb86f2fb519`
- `23608d41-319c-4d8e-a906-748f9c05125e`
- `63370ead-a837-4bab-98dc-79109d022209`
- `238f2277-20ff-4110-a97c-d186d7bc179e`

## Citations verbatim (28)

### [1] source `9797c0de…`

> No List of skill names to preload into the agent's context at startup. Unlisted skills remain invocable through the Skill tool memory No Memory source for this agent: "user" , "project" , or "local" mcpServers No MCP servers available to this agent. Each entry is a server name or an inline {name: config} dict initialPrompt No Auto-submitted as the first user turn when this agent runs as the main thread agent maxTurns No Maximum number of agentic turns before the agent stops background No Run this agent as a non-blocking background task when invoked effort

### [2] source `c78af240…`

> No Run this agent as a non-blocking background task when invoked memory No Memory source for this agent: 'user' , 'project' , or 'local' effort No Reasoning effort level for this agent. Accepts a named level or an integer permissionMode No Permission mode for tool execution within this agent. See PermissionMode criticalSystemReminder_EXPERIMENTAL No Experimental: Critical reminder added to the system prompt AgentMcpServerSpec Specifies MCP servers available to a subagent. Can be a server name (string referencing a server from the parent's mcpServers config) or an inline server configuration record mapping server names to configs.

### [3] source `cf769fec…`

> Creating Custom Subagents Define subagents in .claude/agents/ (project) or ~/.claude/agents/ (personal): Configuration fields: <cited_table>

### [4] source `6f0873fe…`

> Supported frontmatter fields The following fields can be used in the YAML frontmatter. Only name and description are required. <cited_table>

### [5] source `6f0873fe…`

> The CLI flag overrides the setting if both are present. Run subagents in foreground or background Subagents can run in the foreground (blocking) or background (concurrent): Foreground subagents block the main conversation until complete. Permission prompts are passed through to you as they come up. Background subagents run concurrently while you continue working. They run with the permissions already granted in the session and auto-deny any tool call that would otherwise prompt. If a background subagent needs to ask clarifying questions, that tool call fails but the subagent continues.

### [6] source `c78af240…`

> SDKUserMessageReplay Replayed user message with required UUID. SDKResultMessage Final result message. The origin field forwards the SDKMessageOrigin of the user message that triggered this result. When a background task finishes and the SDK injects a synthetic follow-up turn, the resulting SDKResultMessage carries origin: { kind: "task-notification" } . Check this field to distinguish results that answer your prompt from results emitted for background-task follow-ups, so you can route or suppress the latter. The field is absent for results emitted before any user turn, such as startup errors. When a PreToolUse hook returns permissionDecision: "defer" , the result has stop_reason: "tool_deferred" and deferred_tool_use carries the pending tool's id , name , and input . Read this field to surface the request in your own UI, then resume with the same session_id to continue. See Defer a tool call for later for the full round trip.

### [7] source `c78af240…`

> McpSetServersResult Result of a setMcpServers() operation. RewindFilesResult Result of a rewindFiles() operation. SDKStatusMessage Status update message (e.g., compacting). SDKTaskNotificationMessage Notification when a background task completes, fails, or is stopped. Background tasks include run_in_background Bash commands, Monitor watches, and background subagents. SDKToolUseSummaryMessage Summary of tool usage in a conversation. SDKHookStartedMessage Emitted when a hook begins executing. SDKHookProgressMessage

### [8] source `77e0584d…`

> Added Added /resume support for background sessions — sessions started via claude --bg or agent view now appear alongside interactive ones, marked with bg Added elapsed duration to background subagent completion notifications (e.g. "Agent completed 3h 2m 5s") The /plugin browse and discover panes now show when a plugin was last updated /model now changes the model for the current session only; press d in the model picker to set a default for new sessions Renamed "extra usage" to "usage credits" across CLI copy; /extra-usage is now /usage-credits (old name still works)

### [9] source `a5a300d1…`

> Filter Loading Sorry, something went wrong. Uh oh! There was an error while loading. Please reload this page . No results found View all tags v2.1.144 Latest Latest What's changed Added /resume support for background sessions — sessions started via claude --bg or agent view now appear alongside interactive ones, marked with bg Added elapsed duration to background subagent completion notifications (e.g. "Agent completed · 3h 2m 5s") The /plugin browse and discover panes now show when a plugin was last updated /model now changes the model for the current session only; press d in the model picker to set a default for new sessions Renamed "extra usage" to "usage credits" across CLI copy; /extra-usage is now /usage-credits (old name still works) Fixed startup hanging up to 75s when api.anthropic.com is unreachable (captive portal, firewall, VPN issues) — side-channel API calls now time out after 15s Fixed garbled terminal output after a missed window-resize event (e.g. dragging a VS Code split-pane divider) — now self-heals on the next frame instead of requiring Ctrl+L Fixed progressive terminal display corruption (stale/garbled glyphs) that could appear in very long sessions and only cleared on terminal resize or restart Reduced terminal rendering glitches in VS Code by reducing spinner animation color count Fixed macOS background sessions crashing with "exit 1 before init" when the project lives under a Full Disk Access-protected folder (regression in 2.1.143) Fixed an unrecoverable conversation when reading a file whose image extension doesn't match its contents (e.g. HTML saved as .png) — now falls back to text Fewer spurious tool errors during search: head / tail file views now satisfy the read-before-edit check, and a "no matches" result (exit code 1) from egrep , fgrep , git grep , or git diff is no longer reported as a command failure Fixed /branch failing with "No conversation to branch" after entering a worktree or in some background sessions Fixed pressing Escape in the AskUserQuestion notes field aborting the turn instead of returning to answer selection Fixed model selection not applying when changed via the IDE model picker or applyFlagSettings after startup Resumed sessions now keep the model they were using instead of picking up another session's /model choice Fixed Bedrock and Vertex users unable to select "Opus (1M context)" from the /model picker (regression in v2.1.129) Fixed remote-session login failing with "Can't access this organization" for users with forceLoginMethod and forceLoginOrgUUID set Fixed MCP servers with paginated tools/list responses only returning the first page, silently dropping tools Fixed MCP images with unsupported MIME types (e.g. SVG) breaking the conversation — now saved to disk and referenced in the tool result Fixed file descriptor exhaustion when a build runs inside a skill directory — non- .md files no longer trigger skill reloads Fixed session title being generated from plugin monitor output instead of the user's first prompt Fixed Skill tool failing with permission error in headless mode (regression in v2.1.141) Fixed plugins enabled in your own settings showing "not cached" errors after first load on a fresh machine; plugins enabled only by a project's .claude/settings.json now show an actionable claude plugin install hint Fixed claude mcp list silently reporting no servers when .mcp.json can't be parsed (e.g. using VS Code's "servers" key instead of "mcpServers" ) — now shows configuration errors Fixed background side-queries on custom ANTHROPIC_BASE_URL setups and Bedrock Mantle not using Haiku — now falls back correctly when a first-party API key is configured or no Haiku model is set Fixed scrolling in attached background sessions on Windows — PgUp/PgDn, mouse wheel, and Ctrl+O transcript navigation now work Fixed a crash when closing the terminal while attached to a background session Fixed ! <cmd> exec sessions not responding to Ctrl+C while attached — now interrupts the running command

### [10] source `9797c0de…`

> Handle slow or stalled API responses The CLI subprocess reads several environment variables that control API timeouts and stall detection. Pass them through ClaudeAgentOptions.env : API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [11] source `c78af240…`

> API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [12] source `d564912c…`

> SubagentStop Runs when a Claude Code subagent has finished responding. Matches on agent type, same values as SubagentStart. SubagentStop input In addition to the common input fields , SubagentStop hooks receive stop_hook_active , agent_id , agent_type , agent_transcript_path , and last_assistant_message . The agent_type field is the value used for matcher filtering. The transcript_path is the main session's transcript, while agent_transcript_path is the subagent's own transcript stored in a nested subagents/ folder. The last_assistant_message field contains the text content of the subagent's final response, so hooks can access it without parsing the transcript file.

### [13] source `d564912c…`

> Stop input In addition to the common input fields , Stop hooks receive stop_hook_active and last_assistant_message . The stop_hook_active field is true when Claude Code is already continuing as a result of a stop hook. Check this value or process the transcript to prevent Claude Code from running indefinitely. The last_assistant_message field contains the text content of Claude's final response, so hooks can access it without parsing the transcript file. Stop decision control Stop and SubagentStop hooks can control whether Claude continues. In addition to the JSON output fields available to all hooks, your hook script can return these event-specific fields:

### [14] source `6f16fd65…`

> 2.1.133 May 7, 2026 Added worktree.baseRef setting ( fresh | head ) to choose whether --worktree , EnterWorktree , and agent-isolation worktrees branch from origin/<default> or local HEAD . Note: the default fresh changes EnterWorktree 's base back to origin/<default> (it has been local HEAD since 2.1.128) — set worktree.baseRef: "head" to keep unpushed commits in new worktrees Added sandbox.bwrapPath and sandbox.socatPath managed settings (Linux/WSL) to specify custom bubblewrap and socat binary locations Added parentSettingsBehavior admin-tier key ( 'first-wins' | 'merge' ) to let admins opt SDK managedSettings (parent tier) into the policy merge Hooks now receive the active effort level via the effort.level JSON input field and the $CLAUDE_EFFORT environment variable, and Bash tool commands can read $CLAUDE_EFFORT Improved focus mode behavior Improved memory usage by releasing warm-spare background workers under memory pressure Fixed parallel sessions all dead-ending at 401 after a refresh-token race wiped shared credentials Fixed Edit / Write allow rules scoped to a drive root ( C:\ ) or POSIX / matching incorrectly and always prompting Fixed an unhandled rejection ( ECOMPROMISED ) when a history or session-log file lock is compromised by clock skew or slow disk Fixed pressing Esc during conversation compaction showing a spurious “Error compacting conversation” notification Fixed HTTP(S)_PROXY / NO_PROXY / mTLS not being respected for the full MCP OAuth flow including discovery, dynamic client registration, token exchange, and token refresh Fixed Read/Write/Edit being denied on mapped network drives passed via --add-dir / SDK additionalDirectories Fixed Remote Control stop/interrupt from claude.ai not fully canceling the CLI session the same way local Esc does, causing queued messages to never advance after interrupting a stuck tool or prompt Fixed /effort in one session unexpectedly changing the effort level of other concurrent sessions, and a related issue where an IDE effort change could be silently dropped Fixed subagents not discovering project, user, or plugin skills via the Skill tool claude --help now lists --remote-control alongside --remote-control-session-name-prefix [VSCode] Fixed claudeCode.claudeProcessWrapper failing with “Unsupported platform” when the extension build doesn't bundle a Claude binary

### [15] source `77e0584d…`

> 2.1.133 Claude Code adds worktree baseRef controls, custom sandbox paths on Linux/WSL, and admin policy merge options, while exposing effort level to hooks. It also improves focus mode and memory usage and fixes several auth, proxy, drive, session, and VS Code issues. Added worktree.baseRef setting ( fresh | head ) to choose whether --worktree , EnterWorktree , and agent-isolation worktrees branch from origin/<default> or local HEAD . Note: the default fresh changes EnterWorktree 's base back to origin/<default> (it has been local HEAD since 2.1.128) — set worktree.baseRef: "head" to keep unpushed commits in new worktrees Added sandbox.bwrapPath and sandbox.socatPath managed settings (Linux/WSL) to specify custom bubblewrap and socat binary locations Added parentSettingsBehavior admin-tier key ( 'first-wins' | 'merge' ) to let admins opt SDK managedSettings (parent tier) into the policy merge Hooks now receive the active effort level via the effort.level JSON input field and the $CLAUDE_EFFORT environment variable, and Bash tool commands can read $CLAUDE_EFFORT Improved focus mode behavior Improved memory usage by releasing warm-spare background workers under memory pressure Fixed parallel sessions all dead-ending at 401 after a refresh-token race wiped shared credentials Fixed Edit / Write allow rules scoped to a drive root ( C:\ ) or POSIX / matching incorrectly and always prompting Fixed an unhandled rejection ( ECOMPROMISED ) when a history or session-log file lock is compromised by clock skew or slow disk Fixed pressing Esc during conversation compaction showing a spurious "Error compacting conversation" notification Fixed HTTP(S)_PROXY / NO_PROXY / mTLS not being respected for the full MCP OAuth flow including discovery, dynamic client registration, token exchange, and token refresh Fixed Read/Write/Edit being denied on mapped network drives passed via --add-dir / SDK additionalDirectories Fixed Remote Control stop/interrupt from claude.ai not fully canceling the CLI session the same way local Esc does, causing queued messages to never advance after interrupting a stuck tool or prompt Fixed /effort in one session unexpectedly changing the effort level of other concurrent sessions, and a related issue where an IDE effort change could be silently dropped Fixed subagents not discovering project, user, or plugin skills via the Skill tool claude --help now lists --remote-control alongside --remote-control-session-name-prefix [VSCode] Fixed claudeCode.claudeProcessWrapper failing with "Unsupported platform" when the extension build doesn't bundle a Claude binary Original source Show more May 2026 No date parsed from source. First seen by Releasebot: May 7, 2026 A Claude Code by Anthropic

### [16] source `ab4b8c41…`

> Orchestrator pattern (T+85min total wall-clock) TeamCreate wave2-pro (mandatory before Agent calls — primo tentativo fallito: "Team does not exist. Call spawnTeam first"). 3 Agent spawned con team_name="wave2-pro" , run_in_background=true , ognuno con prompt self-contained Phase 1-10. Coordinamento via lock files ~/.claude/locks/ ( coord_* helpers da Wave 1) + team scratchpad. Idle notifications continue (~10-30s cadence) sono normal lifecycle, non completion. Agent-X ha avuto 30+ min di silenzio sostanziale durante deploy verify — ho investigato disk state direttamente per verificare progresso, scoprendo PR #342 già merged. Lesson: orchestrator deve verify-not-trust quando silence cresce, ma evitare di interrompere agent in tool calls lunghe. Final reporting: agent-Y e agent-Z hanno consegnato report DONE espliciti. agent-X non ha mai riportato DONE — verificato direttamente da me via fly ssh + asyncpg query.

### [17] source `b67fe2b2…`

> Lead launched via claude --teammate-mode tmux (auto-detects iTerm2 backend) Each teammate is reuse of an existing subagent definition ( deep-researcher , regulatory-watcher , devils-advocate , general-purpose ) with self-contained prompt at spawn time Claim travels via disk path ( /Users/.../CLAIM.md ), output is JSON files at /tmp/pilot-cross-llm/round0-<name>.json Peer-to-peer debate via SendMessage cross-teammate is enabled (no orchestrator gate), capped at 3 rounds with 2/4-agreement convergence rule

### [18] source `b67fe2b2…`

> fact-checker wrote round0 to disk + went idle WITHOUT SendMessage to lead. source-auditor did SendMessage as instructed. Fix v2 : rely on disk-state polling, not SendMessage, as canonical delivery signal. How to apply (v2 template) For future cross-LLM verifier runs on Bali Zero claims: Create claim file: ~/Desktop/nuzantara/research/verification/<YYYY-MM-DD>-<slug>/CLAIM.md (convention adopted from 2026-05-13) Open fresh terminal: claude --teammate-mode tmux Reuse the LEAD-PROMPT template from ~/Desktop/nuzantara/research/dev-tools/pilot-cross-llm-2026-05-12/LEAD-PROMPT.md (adapt CLAIM path + output dir) Lead spawns 4 teammate with subagent reuse, output to /tmp/pilot-cross-llm/round0-<name>.json After 3 rounds OR convergence, lead writes VERDICT-TABLE + ROUND-LOG + EVALUATION Clean up team

### [19] source `f223637c…`

> -------------------------------------------------------------------------------- name: Orchestrator → sub-session issue/PR race description: Quando orchestrator + sub-session creano contemporaneamente issue/PR per lo stesso task, race window 5-30s genera duplicati. Pre-search obbligatorio. type: feedback originSessionId: 4f7ba8d0-464c-4ff4-bcb9-152c25d3c709 Orchestrator → sub-session issue/PR race Rule Prima di aprire issue/PR mentre una sub-session sta lavorando sullo stesso task, eseguire gh issue list --search '<keyword>' (o gh pr list ) per verificare che la sub-session non abbia già creato l'oggetto.

### [20] source `f223637c…`

> Why 2026-05-07 — orchestrator main session aperto issue #491 (W1.5 9 MISS CRITICI) ~5s prima che SYMBIOSIS A sub-session aprisse #490 sullo stesso topic. Entrambi titoli identici, label sets diversi (#491 solo symbiosis , #490 symbiosis,wave-1.5 ). Risultato: duplicato chiuso post-fatto, +cleanup overhead, GitHub history sporcata. Race window è realistic 5-30s perché: Orchestrator decide "apro issue follow-up" basandosi su sub-session report Sub-session in parallelo sta finalizzando stesso passo (anche se non glielo ha detto) gh issue create è ~1-2s, quindi finestra collisione è ampia

### [21] source `23608d41…`

> -------------------------------------------------------------------------------- name: Plist live env paths must reference main checkout, NEVER worktree description: Sub-session che modifica plist live setta PYTHONPATH/ORGANISM_RULES_PATH al proprio worktree path. Quando worktree muore (auto-cleanup post-merge o manual remove), daemon entra in error loop FileNotFoundError. Pattern P1 verificato 2026-05-08 04:00→08:24. type: feedback originSessionId: 4f7ba8d0-464c-4ff4-bcb9-152c25d3c709 Plist live env paths — main checkout only

### [22] source `23608d41…`

> Rule Quando una sub-session modifica un plist LaunchAgent che è caricato in launchd (live), tutte le EnvironmentVariables con path filesystem devono puntare al main checkout ( ~/Desktop/nuzantara/ ), MAI al worktree path della sub-session ( ~/Desktop/nuzantara-<feature>/ ). Stesso vale per WorkingDirectory , StandardOutPath / StandardErrorPath se contengono path relativi. Why 2026-05-08 04:00 → 08:24 WITA — Supervisor daemon in error loop di 4h 24min , P1 incident. Timeline: 2026-05-07 ~22:30 — sub-session FASE 5 wave Symbiosis activate W2 dispatch lavora in worktree ~/Desktop/nuzantara-fase5-supervisor/ 2026-05-07 ~23:00 — sub-session edita ~/Library/LaunchAgents/com.nuzantara.organism.supervisor.plist settando PYTHONPATH=/Users/nuzantara/Desktop/nuzantara-fase5-supervisor/apps/organism + ORGANISM_RULES_PATH=/Users/nuzantara/Desktop/nuzantara-fase5-supervisor/apps/organism/organism/rules/base.yaml . Bootstrap launchd. Step 6 brief eseguito: production flag flip, daemon entra in W2 active mode. 2026-05-07 ~23:13 — PR #524 merged 19:13 UTC. Sub-session exit cleanly. Worktree auto-removed da ExitWorktree action=remove (default per agent che hanno commit pushed e zero uncommitted). 2026-05-08 04:00:05 — ultimo scheduled_tick event. Da qui il daemon entra in FileNotFoundError su base.yaml ogni 5s (try/except in daemon.py:run_once cattura + log + sleep + retry). 2026-05-08 08:20 — orchestrator scopre durante monitoring post-IG-3 merge. supervisor.err = 2.4MB, ~28k righe stack trace identici. 2026-05-08 08:21 — fix: plutil -replace PYTHONPATH + ORGANISM_RULES_PATH a main checkout, bootout + bootstrap. 2026-05-08 08:24 — primo decision event post-fix.

### [23] source `d564912c…`

> Yes Blocks the configuration change from taking effect (except policy_settings ) StopFailure No Output and exit code are ignored PostToolUse No Shows stderr to Claude (tool already ran) PostToolUseFailure No Shows stderr to Claude (tool already failed) PostToolBatch Yes Stops the agentic loop before the next model call PermissionDenied No Exit code and stderr are ignored (denial already occurred). Use JSON hookSpecificOutput.retry: true to tell the model it may retry Notification No Shows stderr to user only SubagentStart

### [24] source `6f0873fe…`

> How forks differ from named subagents A fork inherits everything the main session has at the moment it spawns. A named subagent starts from its own definition. <cited_table>

### [25] source `63370ead…`

> In a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked. Subagents with preloaded skills work differently: the full skill content is injected at startup. Skill content lifecycle When you or Claude invoke a skill, the rendered SKILL.md content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps. Auto-compaction carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session. If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill's description and instructions so the model keeps preferring it, or use hooks to enforce behavior deterministically. If the skill is large or you invoked several others after it, re-invoke it after compaction to restore the full content.

### [26] source `238f2277…`

> Capabilities Everything that makes Claude Code powerful is available in the SDK: Built-in tools Hooks Subagents MCP Permissions Sessions Your agent can read files, run commands, and search codebases out of the box. Key tools include: <cited_table>

### [27] source `9797c0de…`

> Agent Tool name: Agent (previously Task , which is still accepted as an alias) Input: Output: AskUserQuestion Tool name: AskUserQuestion Asks the user clarifying questions during execution. See Handle approvals and user input for usage details. Input: Output: Bash Tool name: Bash Input: Output: Monitor Tool name: Monitor Runs a background script and delivers each stdout line to Claude as an event so it can react without polling. Monitor follows the same permission rules as Bash. See the Monitor tool reference for behavior and provider availability. Input:

### [28] source `c78af240…`

> Launches a new agent to handle complex, multi-step tasks autonomously. AskUserQuestion Tool name: AskUserQuestion Asks the user clarifying questions during execution. See Handle approvals and user input for usage details. Bash Tool name: Bash Executes bash commands in a persistent shell session with optional timeout and background execution. Monitor Tool name: Monitor Runs a background script and delivers each stdout line to Claude as an event so it can react without polling. Set persistent: true for session-length watches such as log tails. Monitor follows the same permission rules as Bash. See the Monitor tool reference for behavior and provider availability.
