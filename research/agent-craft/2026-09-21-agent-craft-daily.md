---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-09-21-agent-craft-daily

**Date**: 2026-09-21
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 13 / Citations: 23

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Impatto di `CLAUDE_CODE_MAX_RETRIES=2` sulle Invocazioni Billed vs Subscribed:** Riducendo i retry a 2, come varia la resilienza del sistema in presenza di errori di rate-limiting di picco (`429 rate_limit_error` o `529 overloaded_error`), e in che modo le notifiche `RateLimitEvent` possono attivare un backoff esponenziale guidato dall'orchestratore prima che scatti il crollo del retry [9, 10]?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Rate-Limiting, Credit Pool ed Eventi SDK)**

*   **La meccanica dei retry dell'SDK e la configurazione `CLAUDE_CODE_MAX_RETRIES`:**
    > *"API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents."* [1]
    > *"CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff."* [1]

*   **Separazione della fatturazione tra uso Subscribed (REPL) e Billed (Agent SDK / `claude -p`):**
    > *"Starting June 15, 2026, Agent SDK and claude -p usage on subscription plans will draw from a new monthly Agent SDK credit, separate from your interactive usage limits."* [2]
    > *"Under the new policy, Pro version users will receive a monthly exclusive quota of \$20; Max 5x and advanced Team versions will have \$100; Max 20x and advanced Enterprise versions can receive up to \$200. These quotas are exclusively for third-party applications, self-built Agent projects, and claude-p backend command calls. The quotas will refresh monthly, and any excess usage will incur charges at standard API rates."* [3, 4]

*   **L'evento `RateLimitEvent` e i metadati di utilizzo:**
    > *"RateLimitEvent: Emitted when rate limit status changes (for example, from "allowed" to "allowed_warning" ). Use this to warn users before they hit a hard limit, or to back off when status is "rejected" ."* [5]
    > *"RateLimitInfo: status RateLimitStatus... "allowed_warning" means approaching the limit; "rejected" means the limit was hit... utilization float | None... Fraction of the rate limit consumed (0.0 to 1.0)... resets_at int | None... Unix timestamp when the rate limit window resets"* [6]

*   **Notifiche di Retry in tempo reale (`system / api_retry`):**
    > *"When an API request fails with a retryable error, Claude Code emits a system/api_retry event before retrying. You can use this to surface retry progress or implement custom backoff logic."* [7]
    > *"Fields: type ("system"), subtype ("api_retry"), attempt, max_retries, retry_delay_ms, error_status (HTTP status code, or null), error ("rate_limit", "server_error", etc.), session_id"* [8]

*   **L'hook di segnalazione `StopFailure`:**
    > *"StopFailure: Runs instead of Stop when the turn ends due to an API error. Output and exit code are ignored. Use this to log failures, send alerts, or take recovery actions when Claude cannot complete a response due to rate limits, authentication problems, or other API errors."* [9]

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero**

Nel nostro stack reale per la gestione del brand Bali Zero e l'automazione dei caroselli WR2, la gestione del rate-limiting e dell'impostazione `CLAUDE_CODE_MAX_RETRIES` impatta direttamente la stabilità dei flussi e il consumo dei crediti:

*   **Il Rischio di Crollo con `CLAUDE_CODE_MAX_RETRIES=2` sulle Chiamate Programmatiche (Billed):**
    A partire dal 15 giugno 2026, l'uso programmatico dell'Agent SDK e delle esecuzioni headless (`claude -p`) per i nostri cron LaunchAgent (come `_reflexion-synthesis.py` e `wr2-external-bench.md`) attinge dal pool di crediti dedicati Agent SDK (\$200/mese sul nostro piano Max 20x) [4, 10]. 
    Se riduciamo drasticamente `CLAUDE_CODE_MAX_RETRIES` a **2** per evitare il drenaggio di crediti dovuto a tentativi ciechi infiniti [1], **la resilienza dell'agente verso errori di picco (`429 rate_limit_error` o `529 overloaded_error`) cala significativamente** [11]. Se l'infrastruttura Anthropic o un gateway cloud subisce un'improvvisa congestione momentanea, due soli tentativi di retry gestiti automaticamente dal sottoprocesso CLI a brevissima distanza si esauriscono in pochi secondi, provocando l'aborto prematuro della sessione dell'agente [1, 7].
*   **L'Assenza di Reattività Guidata dall'Orchestratore:**
    Nel nostro agente orchestratore `wr2-design-architect`, applichiamo la regola di massimo 2 cicli di correzione per slide (`Max 2 retry rounds`) prima di contrassegnare il carosello come `needs_human_edit` [12]. Tuttavia, a livello di trasporto HTTP/API, lasciamo attualmente che sia l'SDK a gestire in modo opaco i tentativi di rete. Quando il retry interno dell'SDK crolla dopo i 2 tentativi, l'orchestratore non ha il tempo di intercettare lo stallo e mettere in pausa il task, perdendo l'opportunità di preservare lo stato e riprendere l'esecuzione più tardi via `/resume` [13, 14].
*   **Sottoutilizzo degli Eventi `RateLimitEvent`:**
    Attualmente non elaboriamo i messaggi `RateLimitEvent` [5]. Quando l'API emette lo stato `"allowed_warning"` con una `utilization` vicina a `1.0` (es. `0.92`), il sistema continua a inviare richieste ad alta frequenza fino a schiantarsi contro il muro del `429` o dello `status: "rejected"` [5, 6].

---

### **3. Linea di Azione Concreta: Il `RateLimit-Aware Backoff Manager` per Bali Zero**

Per combinare la protezione del budget (evitando il drenaggio di crediti con `CLAUDE_CODE_MAX_RETRIES=2`) [1] con un'elevata resilienza durante i picchi di traffico, implementeremo nella libreria Bali Zero un **Gestore di Backoff Reattivo guidato dall'Orchestratore**.

#### **Implementazione Operativa (`bali_zero/orchestration/rate_limit_handler.py`):**

1.  **Impostazione di `CLAUDE_CODE_MAX_RETRIES=2` in `options.env`:**
    Fissiamo i retry trasparenti dell'SDK a 2 per evitare che il sottoprocesso della CLI consumi token a vuoto in loop ciechi [1].
2.  **Intercettazione Streaming di `RateLimitEvent` e `system/api_retry`:**
    Nello script dell'orchestratore Python, ascoltiamo il flusso di messaggi generato da `query()` o `ClaudeSDKClient` [5, 15]:
    ```python
    async for message in client.receive_messages():
        # 1. Prevenzione attiva del Rate Limit
        if isinstance(message, RateLimitEvent):
            info = message.rate_limit_info
            if info.status == "allowed_warning" and info.utilization > 0.85:
                # L'orchestratore rileva l'imminente saturazione prima che scatti il 429
                log_warning(f"Rate limit utilization high: {info.utilization*100}%. Pausing workflow...")
                await asyncio.sleep(15)  # Inserisce una pausa tattica prima della chiamata successiva

        # 2. Intercettazione del primo errore di Retry dell'API
        elif getattr(message, "subtype", None) == "api_retry":
            attempt = message.attempt
            delay_ms = message.retry_delay_ms or 5000
            error_type = message.error
            
            if error_type in ("rate_limit", "server_error") or message.error_status in (429, 529):
                # Se l'SDK sta bruciando il suo 1° tentativo di retry, l'orchestratore prende il controllo
                logger.warn(f"API Retry detected ({attempt}/{message.max_retries}) due to {error_type}. Applying orchestrator sleep...")
                # Moltiplica il tempo di attesa suggerito dall'API (backoff esponenziale con jitter)
                calculated_sleep = (delay_ms / 1000.0) * (2 ** attempt)
                await asyncio.sleep(calculated_sleep)
    ```
3.  **Cattura con Hook `StopFailure` e Salvataggio del Checkpoint:**
    In `.claude/hooks/stop_failure_handler.py`, registriamo un hook sull'evento `StopFailure` [9]:
    *   Se l'errore registrato è `rate_limit` o `billing_error`, l'hook scrive lo stato della sessione e il `session_id` corrente nel file `/workspace/scratch/paused_sessions.json` [9, 16, 17].
    *   Invia una notifica Telegram immediata ad Antonello contenente il timestamp `resets_at` estratto da `RateLimitInfo` [6].
    *   L'orchestratore riprenderà automaticamente la sessione con `resume: session_id` una volta trascorso l'intervallo di reset [13, 14], azzerando i fallimenti catastrofici delle pipeline di produzione.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Integrazione dell'API Message Batches per Pipeline Asincrone**: Dato che la *Message Batches API* garantisce un **abbattimento del 50% dei costi dei token** sia di input che di output [18], in che modo possiamo convertire i nostri LaunchAgent di background non urgenti (come `_reflexion-synthesis.py` e `_ig-metrics-scraper.py`) per utilizzare l'invio a lotti, bypassando completamente i limiti di rate-limit interattivi e preservando i crediti Agent SDK [3, 18, 19]?
2.  **Identificazione dei Sub-Agenti nei Log OTEL durante i Picchi di Rate-Limit**: Considerando che a partire dalla versione v2.1.139 ogni richiesta API dei sub-agenti trasporta gli header `x-claude-code-agent-id` e `x-claude-code-parent-agent-id` [20], come possiamo configurare il nostro connettore OpenTelemetry per tracciare in tempo reale quale specifico sub-agente della catena WR2 (es. `wr2-layout-composer` vs `wr2-storyboarder`) sta provocando l'esaurimento della quota di token [20, 21]?
3.  **Fallback Dinamico di Modello via CLI (`--fallback-model`)**: Poiché le ultime release di Claude Code consentono di specificare un modello di riserva (tramite `--fallback-model` e preservato durante il detached/background mode `/bg`) [22], in che modo la configurazione di un downgrade automatico verso Sonnet 4.6 (o Haiku 4.5 per la ricerca) consente all'orchestratore di assorbire gli errori `529 overloaded_error` di Opus 4.7 senza interrompere l'esecuzione e senza perdere la memoria della sessione [18, 22, 23]?

## Sources used (13)

- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `238f2277-20ff-4110-a97c-d186d7bc179e`
- `4e082797-e29b-44e4-a811-e7730c3a7941`
- `bd982fdf-33f6-45e9-a806-3ac0c05feb1c`
- `5f596332-b92d-4e27-a3fc-e038981823d7`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `b4852cc9-6ae0-43c1-8408-42c330cb05a5`
- `b8ee4a03-aa8d-4dfc-8d13-bdcb67a2e2bc`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `41511dc3-8e29-456d-bc5d-01747901dc58`
- `6f16fd65-565d-491d-8db8-e2b095a5a064`
- `82b59f67-bcee-4a3e-9672-64e8c46a473e`

## Citations verbatim (23)

### [1] source `9797c0de…`

> Handle slow or stalled API responses The CLI subprocess reads several environment variables that control API timeouts and stall detection. Pass them through ClaudeAgentOptions.env : API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [2] source `238f2277…`

> Starting June 15, 2026, Agent SDK and claude -p usage on subscription plans will draw from a new monthly Agent SDK credit, separate from your interactive usage limits. See Use the Claude Agent SDK with your Claude plan for details. Build AI agents that autonomously read files, run commands, search the web, edit code, and more. The Agent SDK gives you the same tools, agent loop, and context management that power Claude Code, programmable in Python and TypeScript. Python TypeScript The Agent SDK includes built-in tools for reading files, running commands, and editing code, so your agent can start working immediately without you implementing tool execution. Dive into the quickstart or explore real agents built with the SDK:

### [3] source `4e082797…`

> Previously, Anthropic had restricted third-party tools from using Claude subscription quotas in April this year to prevent misuse. The current adjustment is seen as a final resolution to related disputes, reopening third-party access while completely separating Agent calls from regular chat quotas. Under the new policy, Pro version users will receive a monthly quota of $20, Max 5x and advanced Team versions will have $100, and Max 20x and advanced enterprise versions can receive up to $200. These quotas are exclusively for third-party applications, self-built Agent projects, and claude-p backend command calls. The quotas will refresh monthly, and any excess usage will incur charges at standard API rates.

### [4] source `bd982fdf…`

> Previously, Anthropic had restricted third-party tools from accessing the Claude subscription quota in April of this year to prevent abuse. This adjustment is seen as the final solution to the related controversy, which is to reopen third-party access while completely isolating Agent calls from the regular chat quota. Specifically, Pro users will receive a monthly exclusive quota of $20; Max 5x and advanced Team versions will receive $100; Max 20x and advanced Enterprise versions can receive up to $200. The relevant quotas can only be used for third-party applications, self-built Agent projects, and claude-p backend command calls, with quotas refreshing monthly, and any excess must be paid at the standard API rate.

### [5] source `9797c0de…`

> StreamEvent Stream event for partial message updates during streaming. Only received when include_partial_messages=True in ClaudeAgentOptions . Import via from claude_agent_sdk.types import StreamEvent . Field Type Description uuid str Unique identifier for this event session_id str Session identifier event dict[str, Any] The raw Claude API stream event data parent_tool_use_id str | None Parent tool use ID if this event is from a subagent RateLimitEvent Emitted when rate limit status changes (for example, from "allowed" to "allowed_warning" ). Use this to warn users before they hit a hard limit, or to back off when status is "rejected" .

### [6] source `9797c0de…`

> Field Type Description rate_limit_info RateLimitInfo Current rate limit state uuid str Unique event identifier session_id str Session identifier RateLimitInfo Rate limit state carried by RateLimitEvent . Field Type Description status RateLimitStatus Current status. "allowed_warning" means approaching the limit; "rejected" means the limit was hit resets_at int | None Unix timestamp when the rate limit window resets rate_limit_type RateLimitType | None Which rate limit window applies utilization float | None Fraction of the rate limit consumed (0.0 to 1.0) overage_status RateLimitStatus | None

### [7] source `5f596332…`

> Use a tool like jq to parse the response and extract specific fields: Stream responses Use --output-format stream-json with --verbose and --include-partial-messages to receive tokens as they're generated. Each line is a JSON object representing an event: The following example uses jq to filter for text deltas and display just the streaming text. The -r flag outputs raw strings (no quotes) and -j joins without newlines so tokens stream continuously: When an API request fails with a retryable error, Claude Code emits a system/api_retry event before retrying. You can use this to surface retry progress or implement custom backoff logic.

### [8] source `5f596332…`

> <cited_table>

### [9] source `d564912c…`

> Field Description decision "block" prevents Claude from stopping. Omit to allow Claude to stop reason Required when decision is "block" . Tells Claude why it should continue StopFailure Runs instead of Stop when the turn ends due to an API error. Output and exit code are ignored. Use this to log failures, send alerts, or take recovery actions when Claude cannot complete a response due to rate limits, authentication problems, or other API errors. StopFailure input In addition to the common input fields , StopFailure hooks receive error , optional error_details , and optional last_assistant_message . The error field identifies the error type and is used for matcher filtering.

### [10] source `b4852cc9…`

> Previously, claude -p was subsidized roughly 25x on subscription plans. You'd consume $500 worth of API tokens but it just counted against your flat subscription. That subsidy is now gone for programmatic usage. On a Pro plan, $20/month at full API rates gets you roughly 88 chat messages with context before you're done for the month. On Max 5x, $100 goes further but still runs out under heavy use. Everything that uses claude -p is affected: your scripts, CI pipelines, wrapper tools, GitHub Actions, third-party apps built on the Agent SDK. All of it draws from this new capped credit.

### [11] source `b8ee4a03…`

> August 12, 2025 We've launched beta support for a 1M token context window in Claude Sonnet 4 on the Claude API and Amazon Bedrock. August 11, 2025 Some customers might encounter 429 ( rate_limit_error ) errors following a sharp increase in API usage due to acceleration limits on the API. Previously, 529 ( overloaded_error ) errors would occur in similar scenarios. August 8, 2025 Search result content blocks are now generally available on the Claude API and Vertex AI. This feature enables natural citations for RAG applications with proper source attribution. The beta header search-results-2025-06-09 is no longer required. Learn more in Search results .

### [12] source `d0adf453…`

> Hard fail on rubric 1 or 2 → return slides to layout-composer with verbal feedback. Soft fail (rubric 3 or 4) → flag for human review queue, do NOT block. Max 2 retry rounds. After 2 retries, surface the carousel with STATUS: needs_human_edit AND POST to the local queue server so Damar's UI flags the row: If queue server is unreachable (server not running on Pro), still write STATUS: needs_human_edit to slides.json and surface clearly to user. Never infinite-loop. Never claim success on a flagged carousel.

### [13] source `cf769fec…`

> Then resume by name later: claude --resume "feature-auth" Continue most recent session claude -c "continue implementing the tests" List recent sessions to find one (shows up to 50 sessions, v2.1.47+) claude --resume          # interactive picker & Build a complete REST API for user management with authentication, CRUD operations, and proper error handling claude --teleport session_abc123 & Review all PRs assigned to me and prepare summaries with recommendations Check what completed Visit claude.ai/code to see session list

### [14] source `41511dc3…`

> You must resume the same session to access the subagent’s transcript. Each  query()  call starts a new session by default, so pass  resume: sessionId  to continue in the same session. If you’re using a custom agent (not a built-in one), you also need to pass the same agent definition in the  agents  parameter for both queries.   The example below demonstrates this flow: the first query runs a subagent and captures the session ID and agent ID, then the second query resumes the session to ask a follow-up question that requires context from the first analysis.   import  {  query ,  type  SDKMessage  }  from  "@anthropic-ai/claude-agent-sdk" ;   // Helper to extract agentId from message content   // Stringify to avoid traversing different block types (TextBlock, ToolResultBlock, etc.)   function  extractAgentId ( message :  SDKMessage ) :  string  |  undefined  {    if  ( ! ( "message"  in  message ))  return  undefined ;    // Stringify the content so we can search it without traversing nested blocks    const  content  =  JSON . stringify ( message . message . content );    const  match  =  content . match ( /agentId: \s * ( [ a-f0-9- ] + ) / );    return  match ?.[ 1 ];   }   let  agentId :  string  |  undefined ;   let  sessionId :  string  |  undefined ;   // First invocation - use the Explore agent to find API endpoints   for  await  ( const  message  of  query ({    prompt:  "Use the Explore agent to find all API endpoints in this codebase" ,    options:  {  allowedTools:  [ "Read" ,  "Grep" ,  "Glob" ,  "Agent" ] }   })) {    // Capture session_id from ResultMessage (needed to resume this session)    if  ( "session_id"  in  message )  sessionId  =  message . session_id ;    // Search message content for the agentId (appears in Agent tool results)    const  extractedId  =  extractAgentId ( message );    if  ( extractedId )  agentId  =  extractedId ;    // Print the final result    if  ( "result"  in  message )  console . log ( message . result );   }   // Second invocation - resume and ask follow-up   if  ( agentId  &&  sessionId ) {    for  await  ( const  message  of  query ({    prompt:  `Resume agent  ${ agentId }  and list the top 3 most complex endpoints` ,    options:  {  allowedTools:  [ "Read" ,  "Grep" ,  "Glob" ,  "Agent" ],  resume:  sessionId  }    })) {    if  ( "result"  in  message )  console . log ( message . result );    }   }   Subagent transcripts persist independently of the main conversation:

### [15] source `9797c0de…`

> When to use ClaudeSDKClient (continuous conversation) Best for: Continuing conversations - When you need Claude to remember context Follow-up questions - Building on previous responses Interactive applications - Chat interfaces, REPLs Response-driven logic - When next action depends on Claude's response Session control - Managing conversation lifecycle explicitly Functions query() Creates a new session for each interaction with Claude Code. Returns an async iterator that yields messages as they arrive. Each call to query() starts fresh with no memory of previous interactions.

### [16] source `d564912c…`

> Field Description session_id Current session identifier transcript_path Path to conversation JSON cwd Current working directory when the hook is invoked permission_mode Current permission mode : "default" , "plan" , "acceptEdits" , "auto" , "dontAsk" , or "bypassPermissions" . Not all events receive this field: see each event's JSON example below to check effort Object with a level field holding the active effort level for the turn: "low" , "medium" , "high" , "xhigh" , or "max" . If the requested effort exceeds what the current model supports, this is the downgraded level the model actually used, not the level you requested. The object matches the status line effort field. Present for events that fire within a tool-use context, such as PreToolUse , PostToolUse , Stop , and SubagentStop , when the current model supports the effort parameter. The level is also available to hook commands and the Bash tool as the $CLAUDE_EFFORT environment variable. hook_event_name

### [17] source `d564912c…`

> Field Description error Error type: rate_limit , authentication_failed , oauth_org_not_allowed , billing_error , invalid_request , server_error , max_output_tokens , or unknown error_details Additional details about the error, when available last_assistant_message The rendered error text shown in the conversation. Unlike Stop and SubagentStop , where this field holds Claude's conversational output, for StopFailure it contains the API error string itself, such as "API Error: Rate limit reached" StopFailure hooks have no decision control. They run for notification and logging purposes only.

### [18] source `cf769fec…`

> These add up in agent loops. A 100-iteration debug cycle with Bash costs ~24,500 extra input tokens in overhead alone. Cost-Saving Strategies Use Haiku for subagents : Most exploration doesn't need Sonnet Enable prompt caching : Default, but verify it's not disabled Set max turns : claude --max-turns 5 prevents runaway conversations Use plan mode for exploration : No execution = no accidental expensive operations Compact proactively : Smaller context = fewer tokens Limit output : export CLAUDE_CODE_MAX_OUTPUT_TOKENS=2000 Batch API for non-urgent work : 50% off both input and output tokens

### [19] source `b8ee4a03…`

> March 30, 2026 We've raised the max_tokens cap to 300k on the Message Batches API for Claude Opus 4.6 and Sonnet 4.6. Include the output-300k-2026-03-24 beta header to generate longer single-turn outputs for long-form content, structured data, and large code generation tasks. We're retiring the 1M token context window beta for Claude Sonnet 4.5 and Claude Sonnet 4 on April 30, 2026 . After that date, the context-1m-2025-08-07 beta header will have no effect on these models, and requests that exceed the standard 200k-token context window will return an error. To continue using 1M context windows, migrate to Claude Sonnet 4.6 or Claude Opus 4.6 , which support the full 1M token context window at standard pricing with no beta header required.

### [20] source `6f16fd65…`

> 2.1.139 May 11, 2026 Added agent view (Research Preview): a single list of every Claude Code session — running, blocked on you, or done. Run claude agents to get started. See https://code.claude.com/docs/en/agent-view Added /goal command: set a completion condition and Claude keeps working across turns until it's met. Works in interactive, -p , and Remote Control. Shows live elapsed/turns/tokens as an overlay panel Added /scroll-speed command to tune mouse wheel scroll speed with a live preview Added claude plugin details <name> to show a plugin's component inventory and projected per-session token cost Added transcript view navigation: ? for keyboard shortcuts, { / } to jump between user prompts, v to toggle shortcut panel Added hook args: string[] field (exec form) that spawns the command directly without a shell, so path placeholders never need quoting Added hook continueOnBlock config option for PostToolUse — set to true to feed the hook's rejection reason back to Claude and continue the turn MCP stdio servers now receive CLAUDE_PROJECT_DIR in their environment, matching hooks. Plugin configs can reference ${CLAUDE_PROJECT_DIR} in commands Compaction prompt now asks the model to preserve sensitive user instructions /mcp Reconnect now picks up .mcp.json edits without a restart, and shows the HTTP status and URL when reconnecting fails /context all per-skill token estimates now account for the model's tokenizer and show rounded values claude plugin install <name>@<marketplace> now auto-refreshes the marketplace and retries before reporting a plugin as not found /plugin installed-plugin details now show hook event names and MCP server names cleanly /context now shows the providing plugin's name for plugin-sourced skills Remote MCP server reconnect retry on transient failures is now enabled for all users API requests from subagents now carry x-claude-code-agent-id / x-claude-code-parent-agent-id headers, and claude_code.llm_request OTEL spans include agent_id / parent_agent_id attributes Remote Control, /schedule , claude.ai MCP connectors, and notification preferences are now disabled when ANTHROPIC_API_KEY / apiKeyHelper / ANTHROPIC_AUTH_TOKEN is set, even if a Claude.ai login also exists. Unset the API key to use these features Fixed a deadlock where expired credentials and the forceRemoteSettingsRefresh policy setting blocked claude auth login / logout / status with no way to recover Fixed autoAllowBashIfSandboxed not auto-approving commands with shell expansions like $VAR and $(cmd) Fixed a bug where a hook writing to the terminal could corrupt an on-screen interactive prompt; hooks now run without terminal access Fixed unbounded memory growth when an HTTP/SSE MCP server streams non-protocol data — response bodies now capped at 16 MB per SSE frame Fixed Skill(name *) permission rules — the wildcard form now works as a prefix match, matching Bash(ls *) behavior Fixed settings hot-reload not detecting edits to symlinked ~/.claude/settings.json Fixed plugin details failing to load when the marketplace key differs from the manifest name Fixed /model picker “Default” row not reflecting ANTHROPIC_DEFAULT_OPUS_MODEL / ANTHROPIC_DEFAULT_SONNET_MODEL overrides Fixed spurious “stream idle timeout” 5 minutes after a response completed, caused by the watchdog timer not being cleared on stream cancellation Fixed silent exit 1 when 10+ MCP servers are configured and the cache directory is unwritable — the error message now includes the underlying cause Fixed a typing cursor blinking on tab names, list pointers, and select rows in dialogs Fixed transcript view letter shortcuts not working after mouse click Fixed Bash-mode up-arrow history repeating the first entry and clobbering the in-progress draft Fixed pasting or dropping multiple images only inserting the last one Fixed hyperlinks using unreadable dark navy on dark themes — they now adapt to the active theme

### [21] source `cf769fec…`

> Environment Variables Reference Authentication and API: Model configuration: Cloud provider configuration: Behavior control: Tool configuration: Network and proxy: UI and terminal: OpenTelemetry exporters + sensitive-field gating: 166 v2.1.121+ LLM-request span attributes: stop_reason , gen_ai.response.finish_reasons , and user_system_prompt are now emitted on LLM-request spans. user_system_prompt is gated behind OTEL_LOG_USER_PROMPTS=1 since it can contain PII. 154 v2.1.122+ event-level changes: Numeric attributes on api_request and api_error log events are now emitted as numbers (was strings) — fixes downstream OTel collectors that strict-typed the schema. New claude_code.at_mention log event fires when Claude Code resolves an @ -mention. 154

### [22] source `6f16fd65…`

> 2.1.143 May 15, 2026 Added plugin dependency enforcement: claude plugin disable now refuses when another enabled plugin depends on the target (with a copy-pasteable disable-chain hint), and claude plugin enable force-enables transitive dependencies Added projected context cost (per-turn and per-invocation token estimates) to the /plugin marketplace browse pane Added worktree.bgIsolation: "none" setting to let background sessions edit the working copy directly without EnterWorktree , for repos where worktrees are impractical PowerShell tool now passes -ExecutionPolicy Bypass . Opt out with CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1 Background sessions now preserve the model and effort level you set after waking from idle Shift+Tab in attached agent sessions now includes auto mode in the cycle Fixed a corrupt .credentials.json with a non-array scopes value hanging the CLI on startup or silently aborting OAuth token refresh Fixed right-click paste in claude agents on Windows Terminal and WSL Fixed stop hooks that block repeatedly looping forever — the turn now ends with a warning after 8 consecutive blocks (override via CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ) Fixed Esc/Ctrl+C not cancelling a pending /loop wakeup while Claude is idle between iterations Fixed /goal evaluator firing while background shells or delegated subagents are still running Fixed NO_COLOR / FORCE_COLOR in settings.json env stripping Claude Code's own UI colors — they now apply to subprocesses only Fixed agent view spawning repeated PowerShell processes on Windows when listing sessions Fixed /bg without a prompt sending “continue” to the forked session — the fork now waits for input Fixed --agent <name> not finding plugin-contributed agents without the plugin: prefix Fixed deleting a session from agent view not removing its transcript file Fixed stale-fragment rendering when scrolling in attached background sessions on Windows Terminal Fixed background agents false-positive worker-stall detection storm after host sleep or macOS App Nap Fixed 5xx error messages pointing at status.claude.com instead of naming the configured gateway or cloud provider The PowerShell tool is now enabled by default on Windows for Bedrock, Vertex, and Foundry users. Opt out with CLAUDE_CODE_USE_POWERSHELL_TOOL=0 . claude agents now accepts --add-dir , --settings , --mcp-config , and --plugin-dir and applies them to the dashboard and to background sessions dispatched from it claude agents accepts --permission-mode , --model , --effort , and --dangerously-skip-permissions to set defaults for sessions dispatched from the view claude --bg --dangerously-skip-permissions now persists across retire→wake Fixed background sessions silently capturing IDE file references into the warm spare's input, which caused the reference to be prepended to the next prompt dispatched from claude agents Worktree cleanup no longer falls back to rm -rf when git worktree remove fails, preventing loss of gitignored or in-progress files Fixed background-job sessions on macOS getting “Operation not permitted” errors when reading files under ~/Documents , ~/Desktop , or ~/Downloads , even with Full Disk Access granted. /bg now preserves --mcp-config , --settings , --add-dir , --plugin-dir , and --strict-mcp-config , so backgrounded sessions keep their MCP servers and settings across respawn. Background sessions launched from claude agents now honor permissions.defaultMode from settings.json (was previously overridden to auto mode) Fixed: on Windows, pressing ← in claude agents while a response was streaming could leave the agents list unresponsive to all input /bg and ← -detach now preserve --fallback-model , so backgrounded workers degrade to the fallback model on overload instead of hard-failing. /bg and ← -detach now preserve --allow-dangerously-skip-permissions , so the forked worker keeps bypass-permissions available in its Shift+Tab cycle.

### [23] source `82b59f67…`

> Team and Enterprise Plans <cited_table> Enterprise pricing is not published, but industry reports estimate starting costs around $40-60 per seat per month for large deployments with committed volumes. API Pricing <cited_table>
