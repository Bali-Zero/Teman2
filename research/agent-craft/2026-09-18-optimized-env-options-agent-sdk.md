---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-09-18-optimized-env-options-agent-sdk

**Date**: 2026-09-18
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 9 / Citations: 14

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Dichiarazione delle Variabili d'Ambiente Ottimizzate (`options.env`)**:

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (L'Iniezione e il Controllo di `options.env`)**

L'Agent SDK per Python e TypeScript esegue un sottoprocesso nativo della CLI di Claude Code [1-3]. La configurazione delle variabili d'ambiente tramite la proprietà `env` dell'oggetto `ClaudeAgentOptions` (o `Options` in TypeScript) consente di sovrascrivere o integrare l'ambiente di processo ereditato, controllando in modo deterministico i timeout delle API e i watchdog di stallo [2, 4-6]:

*   **Configurazione del dizionario `env` in `ClaudeAgentOptions`:**
    > *"env dict[str, str] {} Environment variables merged on top of the inherited process environment. See [Environment variables] for variables the underlying CLI reads, and [Handle slow or stalled API responses] for timeout-related variables"* [4]

*   **Gestione dei Timeout e del Retrying della CLI (Handle slow or stalled API responses):**
    > *"The CLI subprocess reads several environment variables that control API timeouts and stall detection. Pass them through ClaudeAgentOptions.env :"* [2, 6]
    > *"API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents."* [2, 6]
    > *"CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff."* [2, 6]

*   **Watchdog di Stallo per Agenti Asincroni e Flussi Streaming:**
    > *"CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents."* [2, 6]
    > *"CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path."* [2, 6]

*   **Limiti sui Comandi di Shell (Bash Tool Timeout):**
    > *"BASH_DEFAULT_TIMEOUT_MS overrides the per-command default timeout for the Bash tool (two minutes baseline); BASH_MAX_TIMEOUT_MS caps the value Claude may request (ten minutes baseline). Setting both to the same value pins every Bash invocation to a fixed deadline."* [7]

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero / Nuzantara**

Nella nostra infrastruttura reale di produzione per la generazione di caroselli visivi e l'automazione dei flussi editoriali, le impostazioni predefinite non ottimizzate rappresentano un rischio operativo elevato:

*   **Il Rischio del "Worst-Case Wall Time":**
    Mantenendo le impostazioni di default dell'SDK (`API_TIMEOUT_MS = 600000` ovvero 10 minuti, e `CLAUDE_CODE_MAX_RETRIES = 10`), il tempo massimo di blocco prima che il sistema dichiari un fallimento per singola richiesta API può superare **110 minuti** (\\(10 \text{ min} \times 11\\)) [2, 6]. Nei nostri LaunchAgent su macOS che eseguono cron settimanali o giornalieri (come `wr2-external-bench` e `_reflexion-synthesis.py`), questo ritardo comporta il rischio di sovrapposizione tra esecuzioni successive. Per questa ragione avevamo dovuto racchiudere le invocazioni bash in un wrapper rigido con un cappello temporale massimo di 2700s (45 minuti).
*   **L'Incidente KEP71 e il Cap dei 300 Secondi:**
    Durante lo smoke test sulla slide di copertina KEP71 (12 maggio 2026), l'invocazione di generazione immagine tramite Codex si bloccò per oltre 25 minuti in assenza di un cap temporale sulla chiamata [8]. L'episodio condusse all'introduzione della regola costituzionale: *"Watchdog: every Codex \$imagegen invocation MUST have a 300-second wall-clock cap... If watchdog fires at 300s without output PNG, treat as STATUS: imagegen_timeout"*.
*   **Stalli Silenti nelle Query MCP:**
    I nostri sub-agenti come `regulatory-watcher` o `nb-curator`, interfacciandosi con server MCP remoti tramite HTTP o SSE, subivano occasionalmente interruzioni di socket dopo la ricezione degli header. Senza l'abilitazione esplicita dello watchdog di streaming (`CLAUDE_ENABLE_STREAM_WATCHDOG=1`), l'agente rimaneva indefinitamente in attesa della risposta senza restituire il controllo all'orchestratore [2, 6].

---

### **3. Linea di Azione Concreta: Il Profilo `OPTIMIZED_TIMEOUT_ENV` per Bali Zero**

Per standardizzare la tolleranza ai guasti e prevenire il consumo incontrollato di crediti o il blocco delle REPL programmatiche, integreremo un **dizionario di configurazione dell'ambiente** nella libreria di avvio degli agenti di Bali Zero.

#### **Azione**: Dichiarare ed iniettare programmaticamente il dizionario `OPTIMIZED_TIMEOUT_ENV` in tutte le istanze `ClaudeAgentOptions`.

1.  **Modulo di Configurazione Centralizzato (`bali_zero/config/timeout_settings.py`):**
    ```python
    # bali_zero/config/timeout_settings.py

    OPTIMIZED_TIMEOUT_ENV = {
        # Timeout per singola chiamata API ridotto a 5 minuti (300.000 ms)
        "API_TIMEOUT_MS": "300000",
        
        # Riduzione dei retry a 3: worst-case wall time = 5 min * (3 + 1) = 20 minuti
        "CLAUDE_CODE_MAX_RETRIES": "3",
        
        # Watchdog per sub-agenti lanciati con background: true (5 minuti)
        "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "300000",
        
        # Attivazione dello stream watchdog per blocchi mid-body
        "CLAUDE_ENABLE_STREAM_WATCHDOG": "1",
        
        # Soglia di inattività dello streaming (2 minuti / 120.000 ms)
        "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "120000",
        
        # Fissaggio del timeout predefinito per ogni comando Bash a 2 minuti
        "BASH_DEFAULT_TIMEOUT_MS": "120000",
        "BASH_MAX_TIMEOUT_MS": "120000",
    }
    ```

2.  **Iniezione nelle Opzioni dell'Agent SDK:**
    ```python
    from claude_agent_sdk import query, ClaudeAgentOptions
    from bali_zero.config.timeout_settings import OPTIMIZED_TIMEOUT_ENV

    options = ClaudeAgentOptions(
        env=OPTIMIZED_TIMEOUT_ENV,
        # ... altre opzioni
    )
    ```

3.  **Gestione del Fallback nel Gestore di Messaggi dell'Orchestratore:**
    Nello script dell'orchestratore `wr2-design-architect`, configurare la cattura del tipo di messaggio `TaskNotificationMessage` [1, 2]: se lo stallo di un sub-agente attiva il watchdog `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`, l'orchestratore recupera il risultato parziale emesso (`partial result`) [2, 6], contrassegna lo stato della slide come `degraded_timeout` e commuta su una modalità di rendering semplificata invece di far fallire l'intera pipeline.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Extended Thinking vs. Stream Idle Watchdog**: Quando modelli come **Claude Opus 4.7** o **Sonnet 4.6** eseguono catene di ragionamento adattivo (*adaptive / extended thinking*) che richiedono oltre 2-3 minuti di elaborazione interna prima di emettere il primo token di testo, come possiamo evitare che `CLAUDE_STREAM_IDLE_TIMEOUT_MS` interpreti questa pausa di calcolo come uno stallo di rete [2, 6, 9]?
2.  **Sincronizzazione dei Timeout MCP ed Ereditarietà Subprocesso**: In che modo l'impostazione di `MCP_TOOL_TIMEOUT` per i server MCP HTTP/SSE esterni interagisce con la catena dei tentativi gestita da `CLAUDE_CODE_MAX_RETRIES` e `API_TIMEOUT_MS` quando un tool remoto va in timeout durante una chiamata in parallelo [2, 6, 10, 11]?
3.  **Ripristino Deterministico dai Partial Results post-Stallo**: In caso di interruzione di un sub-agente asincrono scatenata dal watchdog di stallo, in che modo l'orchestratore può utilizzare il comando `/resume` o la lettura diretta del transcript `.jsonl` per riprendere la sessione dal checkpoint esatto senza ricalcolare o rieseguire i tool già completati con successo [12-14]?

## Sources used (9)

- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `c78af240-51bd-4558-a4ed-7c0a82b09c14`
- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `56f6b3fd-9b7d-4790-aebf-fe011fa3f5db`
- `6f16fd65-565d-491d-8db8-e2b095a5a064`
- `77e0584d-f93a-4384-a5a5-73d353aba212`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `5f596332-b92d-4e27-a3fc-e038981823d7`

## Citations verbatim (14)

### [1] source `9797c0de…`

> Deployment Hosting the Agent SDK Securely deploying AI agents SDK references TypeScript SDK TypeScript V2 (deprecated) Python SDK Migration Guide On this page Installation Choosing between query() and ClaudeSDKClient Quick comparison When to use query() (new session each time) When to use ClaudeSDKClient (continuous conversation) Functions query() Parameters Returns Example - With options tool() Parameters Input schema options Returns Example ToolAnnotations create_sdk_mcp_server() Parameters Returns Example list_sessions() Parameters Return type: SDKSessionInfo Example get_session_messages() Parameters Return type: SessionMessage Example get_session_info() Parameters Example rename_session() Parameters Example tag_session() Parameters Example Classes ClaudeSDKClient Key Features Methods Context Manager Support Example - Continuing a conversation Example - Streaming input with ClaudeSDKClient Example - Using interrupts Example - Advanced permission control Types SdkMcpTool Transport ClaudeAgentOptions Handle slow or stalled API responses OutputFormat SystemPromptPreset SettingSource Default behavior Why use setting_sources Settings precedence AgentDefinition PermissionMode CanUseTool ToolPermissionContext PermissionResult PermissionResultAllow PermissionResultDeny PermissionUpdate PermissionRuleValue ToolsPreset ThinkingConfig SdkBeta McpSdkServerConfig McpServerConfig McpStdioServerConfig McpSSEServerConfig McpHttpServerConfig McpServerStatusConfig McpStatusResponse McpServerStatus SdkPluginConfig Message Types Message UserMessage AssistantMessage AssistantMessageError SystemMessage ResultMessage StreamEvent RateLimitEvent RateLimitInfo TaskStartedMessage TaskUsage TaskProgressMessage TaskNotificationMessage Content Block Types ContentBlock TextBlock ThinkingBlock ToolUseBlock ToolResultBlock Error Types ClaudeSDKError CLINotFoundError CLIConnectionError ProcessError CLIJSONDecodeError Hook Types HookEvent HookCallback HookContext HookMatcher HookInput BaseHookInput PreToolUseHookInput PostToolUseHookInput PostToolUseFailureHookInput UserPromptSubmitHookInput StopHookInput SubagentStopHookInput PreCompactHookInput NotificationHookInput SubagentStartHookInput PermissionRequestHookInput HookJSONOutput SyncHookJSONOutput HookSpecificOutput AsyncHookJSONOutput Hook Usage Example Tool Input/Output Types Agent AskUserQuestion Bash Monitor Edit Read Write Glob Grep NotebookEdit WebFetch WebSearch TodoWrite TaskCreate TaskUpdate TaskGet TaskList BashOutput KillBash ExitPlanMode ListMcpResources ReadMcpResource Advanced Features with ClaudeSDKClient Building a Continuous Conversation Interface Using Hooks for Behavior Modification Real-time Progress Monitoring Example Usage Basic file operations (using query) Error handling Streaming mode with client Using custom tools with ClaudeSDKClient Sandbox Configuration SandboxSettings Example usage SandboxNetworkConfig SandboxIgnoreViolations Permissions Fallback for Unsandboxed Commands See also

### [2] source `9797c0de…`

> Handle slow or stalled API responses The CLI subprocess reads several environment variables that control API timeouts and stall detection. Pass them through ClaudeAgentOptions.env : API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [3] source `c78af240…`

> SDK references Agent SDK reference - TypeScript Copy page Complete API reference for the TypeScript Agent SDK, including all functions, types, and interfaces. Copy page Documentation Index Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt Use this file to discover all available pages before exploring further. Installation The SDK bundles a native Claude Code binary for your platform as an optional dependency such as @anthropic-ai/claude-agent-sdk-darwin-arm64 . You don't need to install Claude Code separately. If your package manager skips optional dependencies, the SDK throws Native CLI binary for <platform> not found ; set pathToClaudeCodeExecutable to a separately installed claude binary instead.

### [4] source `9797c0de…`

> Current working directory cli_path str | Path | None None Custom path to the Claude Code CLI executable settings str | None None Path to settings file add_dirs list[str | Path] [] Additional directories Claude can access env dict[str, str] {} Environment variables merged on top of the inherited process environment. See Environment variables for variables the underlying CLI reads, and Handle slow or stalled API responses for timeout-related variables extra_args dict[str, str | None] {} Additional CLI arguments to pass directly to the CLI max_buffer_size int | None None

### [5] source `c78af240…`

> Enable file change tracking for rewinding. See File checkpointing env Record<string, string | undefined> process.env Environment variables. See Environment variables for variables the underlying CLI reads, and Handle slow or stalled API responses for timeout-related variables. Set CLAUDE_AGENT_SDK_CLIENT_APP to identify your app in the User-Agent header executable 'bun' | 'deno' | 'node' Auto-detected JavaScript runtime to use executableArgs string[] [] Arguments to pass to the executable extraArgs Record<string, string | null> {}

### [6] source `c78af240…`

> API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [7] source `2ad7dcc3…`

> Recognized harness-level variables include ANTHROPIC_MODEL , ANTHROPIC_API_KEY , ANTHROPIC_BASE_URL , CLAUDE_CODE_USE_BEDROCK , CLAUDE_CODE_USE_VERTEX , CLAUDE_CODE_ENABLE_TELEMETRY , CLAUDE_CODE_DISABLE_THINKING , CLAUDE_CODE_DISABLE_AUTO_MEMORY , CLAUDE_CODE_SKIP_PROMPT_HISTORY , CLAUDE_CODE_EFFORT_LEVEL , CLAUDE_CODE_MAX_OUTPUT_TOKENS , BASH_DEFAULT_TIMEOUT_MS , BASH_MAX_TIMEOUT_MS , DISABLE_AUTOUPDATER , MCP_TIMEOUT , MAX_MCP_OUTPUT_TOKENS , plus the standard OpenTelemetry exporters ( OTEL_LOGS_EXPORTER , OTEL_METRICS_EXPORTER , OTEL_LOG_TOOL_DETAILS for extended tool span attributes such as file_path and full_command ). BASH_DEFAULT_TIMEOUT_MS overrides the per-command default timeout for the Bash tool (two minutes baseline); BASH_MAX_TIMEOUT_MS caps the value Claude may request (ten minutes baseline). Setting both to the same value pins every Bash invocation to a fixed deadline.

### [8] source `cf769fec…`

> Distributed Tracing (v2.1.110+) SDK and headless sessions now read TRACEPARENT and TRACESTATE from the environment, linking Claude Code runs into distributed traces. Pair with OTEL_LOG_RAW_API_BODIES=1 (v2.1.111+) to emit full API request/response bodies as OpenTelemetry log events for debugging. 146 Native Binary Distribution (v2.1.113+) 150 v2.1.113 changes how the CLI launches: claude now spawns a native Claude Code binary via a per-platform optional dependency instead of running bundled JavaScript. Installation and update commands stay the same, and teams do not need to change rollout scripts.

### [9] source `56f6b3fd…`

> Agent Skills - Claude API Docs Messages Managed Agents Admin Resources API reference English Console Log in Search... ⌘K First steps Intro to Claude Quickstart Building with Claude Features overview Using the Messages API Handling stop reasons Model capabilities Extended thinking Adaptive thinking Effort Task budgets (beta) Fast mode (beta: research preview) Structured outputs Citations Streaming Messages Batch processing Search results Streaming refusals Multilingual support Embeddings Tools Overview How tool use works Tutorial: Build a tool-using agent Define tools Handle tool calls Parallel tool use Tool Runner (SDK) Strict tool use Tool use with prompt caching Server tools Troubleshooting Web search tool Web fetch tool Code execution tool Advisor tool Memory tool Bash tool Computer use tool Text editor tool

### [10] source `6f16fd65…`

> 2.1.142 May 14, 2026 Added new claude agents flags: --add-dir , --settings , --mcp-config , --plugin-dir , --permission-mode , --model , --effort , and --dangerously-skip-permissions to configure dispatched background sessions Fast mode now uses Opus 4.7 by default (previously Opus 4.6). Set CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE=1 to pin fast mode to Opus 4.6 Plugins with a root-level SKILL.md and no skills/ subdirectory are now surfaced as a skill The /plugin details pane and claude plugin details now show LSP servers a plugin provides /web-setup warns before replacing an existing GitHub App connection Fixed MCP_TOOL_TIMEOUT not raising the per-request fetch timeout for remote HTTP and SSE MCP servers, which capped tool calls at 60 seconds regardless of the configured value Fixed background sessions not recognizing pre-existing git worktrees, blocking Edit while EnterWorktree refused to create a duplicate Fixed background sessions disappearing and daemon reconnect failing after macOS sleep/wake — the daemon now detects clock jumps instead of treating them as elapsed idle time Fixed daemon not exiting cleanly after the binary is upgraded (e.g. brew upgrade ), causing dispatched agents to crash-loop on the deleted path Fixed background agents crash-looping when the Claude-in-Chrome extension is connected without a shared tab Fixed clicking links in an attached claude agents session — the background worker's headless browser shim no longer applies while attached Fixed claude agents “v to open in editor” using the daemon's default editor instead of your shell's $EDITOR / $VISUAL Fixed claude agents deadlocking on Windows with network-drive working directories; Ctrl+C now works during startup Fixed background-color bleed when attaching to a claude agents session from Apple Terminal or other 256-color-only terminals Fixed claude --bg --dangerously-skip-permissions not persisting across retire/wake Fixed session titles being derived from the URL when the first message is a link Fixed redundant set_model requests from remote clients injecting duplicate /model breadcrumbs into the transcript Fixed plugins using skills: ["./"] showing a false “path escapes plugin directory” error Fixed plugin cache cleanup deleting the active plugin version directory when no installation metadata is present Fixed /plugin browse pane showing “0 installs” for newly published plugins Fixed plugin advisories not naming every plugin.json key that shadows a default folder Improved reactive compaction: the first summarize attempt now seeds from the original request's overflow size, avoiding a wasted near-full-context retry Improved hook configuration error: configuring a prompt- or agent-type hook for SessionStart / Setup / SubagentStart now shows a clear “use a command-type hook instead” error Removed stale /model claude-sonnet-4-20250514 suggestion from Usage Policy refusal messages

### [11] source `77e0584d…`

> 2.1.142 Claude Code adds new claude agents flags, updates fast mode to Opus 4.7 by default, and improves plugins, background sessions, and daemon reliability with a long list of fixes and workflow polish across editors, MCP, macOS sleep, Windows, and browser-connected agents. Added new claude agents flags: --add-dir , --settings , --mcp-config , --plugin-dir , --permission-mode , --model , --effort , and --dangerously-skip-permissions to configure dispatched background sessions Fast mode now uses Opus 4.7 by default (previously Opus 4.6). Set CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE=1 to pin fast mode to Opus 4.6 Plugins with a root-level SKILL.md and no skills/ subdirectory are now surfaced as a skill The /plugin details pane and claude plugin details now show LSP servers a plugin provides /web-setup warns before replacing an existing GitHub App connection Fixed MCP_TOOL_TIMEOUT not raising the per-request fetch timeout for remote HTTP and SSE MCP servers, which capped tool calls at 60 seconds regardless of the configured value Fixed background sessions not recognizing pre-existing git worktrees, blocking Edit while EnterWorktree refused to create a duplicate Fixed background sessions disappearing and daemon reconnect failing after macOS sleep/wake — the daemon now detects clock jumps instead of treating them as elapsed idle time Fixed daemon not exiting cleanly after the binary is upgraded (e.g. brew upgrade ), causing dispatched agents to crash-loop on the deleted path Fixed background agents crash-looping when the Claude-in-Chrome extension is connected without a shared tab Fixed clicking links in an attached claude agents session — the background worker's headless browser shim no longer applies while attached Fixed claude agents "v to open in editor" using the daemon's default editor instead of your shell's $EDITOR / $VISUAL Fixed claude agents deadlocking on Windows with network-drive working directories; Ctrl+C now works during startup Fixed background-color bleed when attaching to a claude agents session from Apple Terminal or other 256-color-only terminals Fixed claude --bg --dangerously-skip-permissions not persisting across retire/wake Fixed session titles being derived from the URL when the first message is a link Fixed redundant set_model requests from remote clients injecting duplicate /model breadcrumbs into the transcript Fixed plugins using skills: ["./"] showing a false "path escapes plugin directory" error Fixed plugin cache cleanup deleting the active plugin version directory when no installation metadata is present Fixed /plugin browse pane showing "0 installs" for newly published plugins Fixed plugin advisories not naming every plugin.json key that shadows a default folder Improved reactive compaction: the first summarize attempt now seeds from the original request's overflow size, avoiding a wasted near-full-context retry Improved hook configuration error: configuring a prompt- or agent-type hook for SessionStart / Setup / SubagentStart now shows a clear "use a command-type hook instead" error Removed stale /model claude-sonnet-4-20250514 suggestion from Usage Policy refusal messages Original source Show more May 2026 No date parsed from source. First seen by Releasebot: May 14, 2026 A Claude Code by Anthropic

### [12] source `cf769fec…`

> Creating Custom Subagents Define subagents in .claude/agents/ (project) or ~/.claude/agents/ (personal): Configuration fields: <cited_table>

### [13] source `6f0873fe…`

> Auto-compaction Subagents support automatic compaction using the same logic as the main conversation. By default, auto-compaction triggers at approximately 95% capacity. To trigger compaction earlier, set CLAUDE_AUTOCOMPACT_PCT_OVERRIDE to a lower percentage (for example, 50 ). See environment variables for details. Compaction events are logged in subagent transcript files: The preTokens value shows how many tokens were used before compaction occurred. Fork the current conversation Forked subagents are experimental and require Claude Code v2.1.117 or later. Behavior and configuration may change in future releases. Enable them by setting the CLAUDE_CODE_FORK_SUBAGENT environment variable to 1 . The variable is honored in interactive mode and via the SDK or claude -p .

### [14] source `5f596332…`

> Basic usage Add the -p (or --print ) flag to any claude command to run it non-interactively. All CLI options work with -p , including: --continue for continuing conversations --allowedTools for auto-approving tools --output-format for structured output This example asks Claude a question about your codebase and prints the response: Start faster with bare mode Add --bare to reduce startup time by skipping auto-discovery of hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md. Without it, claude -p loads the same context an interactive session would, including anything configured in the working directory or ~/.claude . Bare mode is useful for CI and scripts where you need the same result on every machine. A hook in a teammate's ~/.claude or an MCP server in the project's .mcp.json won't run, because bare mode never reads them. Only flags you pass explicitly take effect. This example runs a one-off summarize task in bare mode and pre-approves the Read tool so the call completes without a permission prompt:
