---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-09-20-agent-craft-daily

**Date**: 2026-09-20
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 7 / Citations: 13

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **L'Anti-Pattern del "Worst-Case Wall Time":**

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (L'Anti-Pattern del Worst-Case Wall Time)**

L'anti-pattern del **Worst-Case Wall Time** si verifica quando la combinazione delle impostazioni predefinite dei timeout di richiesta e del numero massimo di tentativi di riprova (retries) calcola un tempo massimo teorico di blocco insostenibile prima di sollevare un fallimento esplicito [1, 2].

*   **La formula del Worst-Case Wall Time:**
    > *"API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents."* [1, 2]
    > *"CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff."* [1, 2]

*   **Watchdog per Sub-agenti Asincroni e Streaming Stalled:**
    > *"CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result."* [1, 2]
    > *"CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path."* [1, 2]

*   **Cap e Vincoli sui Comandi Shell:**
    > *"BASH_DEFAULT_TIMEOUT_MS overrides the per-command default timeout for the Bash tool (two minutes baseline); BASH_MAX_TIMEOUT_MS caps the value Claude may request (ten minutes baseline). Setting both to the same value pins every Bash invocation to a fixed deadline."* [3]

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero / Nuzantara**

Nel nostro ecosistema reale, i valori predefiniti dell'Agent SDK generano una grave vulnerabilità architetturale:

*   **L'Impatto dei Valori di Default (Oltre 110 Minuti di Blocco):**
    Con un `API_TIMEOUT_MS` di 10 minuti (600.000 ms) e `CLAUDE_CODE_MAX_RETRIES = 10`, se una richiesta API incontra errori riprovabili o stalli di rete, il tempo massimo di esecuzione *wall-clock* per un singolo turno prima di cedere il controllo può superare **110 minuti** (\\(10 \text{ min} \times (10 + 1) + \text{backoff}\\)) [1, 2].
*   **Contromisure nei LaunchAgent e nei Cron di Produzione:**
    Nei nostri LaunchAgent automatizzati (come `wr2-external-bench.md`), per evitare che un cron bloccato in background rimanesse sospeso per ore sovrapponendosi all'esecuzione successiva, avevamo dovuto inserire manualmente nei wrapper bash la direttiva `Hard timeout: 2700s (45 min)` [4].
*   **L'Incidente KEP71 e la Regola del Wall-Clock Cap:**
    Durante lo smoke test sulla slide KEP71 (12 maggio 2026), l'invocazione di generazione immagine via Codex si bloccò per oltre 25 minuti [5]. Questo portò all'introduzione della regola costituzionale in `wr2-design-architect.md`:
    > *"Watchdog (added 2026-05-12 after smoke test KEP71 cover hang) : every Codex \$imagegen invocation MUST have a 300-second wall-clock cap... If watchdog fires at 300s without output PNG, treat as STATUS: imagegen_timeout... NEVER spin-wait via until ! pgrep without a hard wall-clock cap."* [5]
*   **Pianificazione dei Retry dell'Orchestratore:**
    Il nostro orchestratore `wr2-design-architect` impone un limite massimo di **2 tentativi di retry** (`Max 2 retry rounds`) prima di contrassegnare il carosello come `needs_human_edit` e passarlo alla coda di revisione di Damar, evitando di riprovare indefinitamente [6].

---

### **3. Linea di Azione Concreta: Il "Worst-Case Wall Time Shield" per Bali Zero**

Per disinnescare questo anti-pattern in tutte le chiamate della libreria Bali Zero, implementeremo un profilo di configurazione delle variabili d'ambiente che riduca matematicamente il Worst-Case Wall Time da **>110 minuti a un massimo controllabile di 15-20 minuti**.

#### **Azione:** Dichiarare ed iniettare il dizionario `WALL_TIME_SHIELD_ENV` nel modulo `bali_zero/config/timeout_settings.py` [1-3].

```python
# bali_zero/config/timeout_settings.py
from typing import Dict

WALL_TIME_SHIELD_ENV: Dict[str, str] = {
    # 1. Riduzione del timeout per singola chiamata API a 5 minuti (300.000 ms)
    "API_TIMEOUT_MS": "300000",
    
    # 2. Abbassamento dei retry massimi dell'SDK da 10 a 2 o 3.
    # Con API_TIMEOUT_MS=300000 e MAX_RETRIES=2, il worst-case wall time passa da 110m a soli 15m!
    "CLAUDE_CODE_MAX_RETRIES": "2",
    
    # 3. Watchdog di stallo per sub-agenti lanciati con background: true (5 minuti)
    "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "300000",
    
    # 4. Attivazione dello stream watchdog per blocchi mid-body
    "CLAUDE_ENABLE_STREAM_WATCHDOG": "1",
    "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "120000", # 2 minuti
    
    # 5. Cap per comandi Bash
    "BASH_DEFAULT_TIMEOUT_MS": "120000",
    "BASH_MAX_TIMEOUT_MS": "120000",
}
```

#### **Iniezione nell'Agent SDK e Gestione degli Eventi:**
*   Il dizionario viene iniettato nell'oggetto `ClaudeAgentOptions(env=WALL_TIME_SHIELD_ENV)` [1, 2].
*   In modalità `stream-json`, lo script dell'orchestratore ascolta gli eventi `subtype: "api_retry"` [7, 8]. Se il contatore `attempt` raggiunge il limite massimo, l'orchestratore intercetta l'evento prima dell'abort definitivo e commuta su una modalità di rendering di riserva (*degraded mode*).

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Impatto di `CLAUDE_CODE_MAX_RETRIES=2` sulle Invocazioni Billed vs Subscribed:** Riducendo i retry a 2, come varia la resilienza del sistema in presenza di errori di rate-limiting di picco (`429 rate_limit_error` o `529 overloaded_error`), e in che modo le notifiche `RateLimitEvent` possono attivare un backoff esponenziale guidato dall'orchestratore prima che scatti il crollo del retry [9, 10]?
2.  **Extended Thinking e Interazione con lo Stream Idle Timeout:** Se attiviamo l'effetto ragionamento adattivo (*adaptive thinking*) su **Claude Opus 4.7** con livello `xhigh`, quali accorgimenti dobbiamo adottare affinché le lunghe pause di pensiero interno del modello non vengano erroneamente scambiate per uno stallo dello stream da parte di `CLAUDE_STREAM_IDLE_TIMEOUT_MS` [1, 2, 11]?
3.  **Persistenza dello Stato e Resumption post-Timeout:** Qualora un sub-agente venga interrotto dallo stallo di un tool esogeno, come possiamo utilizzare la combinazione di `enable_file_checkpointing` e il comando `/resume` per consentire al sub-agente di ripartire dall'ultimo checkpoint valido senza dover ricalcolare i primi token del prompt [12, 13]?

⏱️ *Se desideri, posso preparare uno script di test per simulare il comportamento di `WALL_TIME_SHIELD_ENV` sotto condizioni di inattività di rete simulate.*

## Sources used (7)

- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `c78af240-51bd-4558-a4ed-7c0a82b09c14`
- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `2c1da571-c4d1-408e-9d46-f7e2c07316c6`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `5f596332-b92d-4e27-a3fc-e038981823d7`
- `9d6cef05-7059-49bb-b44a-cd479d6a5c8e`

## Citations verbatim (13)

### [1] source `9797c0de…`

> Handle slow or stalled API responses The CLI subprocess reads several environment variables that control API timeouts and stall detection. Pass them through ClaudeAgentOptions.env : API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [2] source `c78af240…`

> API_TIMEOUT_MS : per-request timeout on the Anthropic client, in milliseconds. Default 600000 . Applies to the main loop and all subagents. CLAUDE_CODE_MAX_RETRIES : maximum API retries. Default 10 . Each retry gets its own API_TIMEOUT_MS window, so worst-case wall time is roughly API_TIMEOUT_MS × (CLAUDE_CODE_MAX_RETRIES + 1) plus backoff. CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS : stall watchdog for subagents launched with run_in_background . Default 600000 . Resets on each stream event; on stall it aborts the subagent, marks the task failed, and surfaces the error to the parent with any partial result. Does not apply to synchronous subagents. CLAUDE_ENABLE_STREAM_WATCHDOG=1 with CLAUDE_STREAM_IDLE_TIMEOUT_MS : aborts the request when headers have arrived but the response body stops streaming. Off by default. CLAUDE_STREAM_IDLE_TIMEOUT_MS defaults to 300000 and is clamped to that minimum. The aborted request goes through the normal retry path.

### [3] source `2ad7dcc3…`

> Recognized harness-level variables include ANTHROPIC_MODEL , ANTHROPIC_API_KEY , ANTHROPIC_BASE_URL , CLAUDE_CODE_USE_BEDROCK , CLAUDE_CODE_USE_VERTEX , CLAUDE_CODE_ENABLE_TELEMETRY , CLAUDE_CODE_DISABLE_THINKING , CLAUDE_CODE_DISABLE_AUTO_MEMORY , CLAUDE_CODE_SKIP_PROMPT_HISTORY , CLAUDE_CODE_EFFORT_LEVEL , CLAUDE_CODE_MAX_OUTPUT_TOKENS , BASH_DEFAULT_TIMEOUT_MS , BASH_MAX_TIMEOUT_MS , DISABLE_AUTOUPDATER , MCP_TIMEOUT , MAX_MCP_OUTPUT_TOKENS , plus the standard OpenTelemetry exporters ( OTEL_LOGS_EXPORTER , OTEL_METRICS_EXPORTER , OTEL_LOG_TOOL_DETAILS for extended tool span attributes such as file_path and full_command ). BASH_DEFAULT_TIMEOUT_MS overrides the per-command default timeout for the Bash tool (two minutes baseline); BASH_MAX_TIMEOUT_MS caps the value Claude may request (ten minutes baseline). Setting both to the same value pins every Bash invocation to a fixed deadline.

### [4] source `2c1da571…`

> Implementation (Task F, 2026-05-12) : Plist: ~/Library/LaunchAgents/com.balizero.wr2.external-bench.monthly.plist Wrapper: ~/scripts/wr2-external-bench-run.sh (executable, 4 KB) Bootstrap: launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.external-bench.monthly.plist macOS StartCalendarInterval cannot express "first Monday of month" natively, so plist fires every Monday 07:00 and wrapper enforces day-of-month <= 7 guard Idempotent: skips if _external-bench-YYYY-MM.md already exists non-empty (delete to force re-run) Hard timeout: 2700s (45 min) Telegram failure alert via TELEGRAM_BOT_TOKEN from ~/.nuzantara-secrets.env Verified 2026-05-12 with dry-run: skips correctly on non-first-Monday Next live firing: lunedì 2 giugno 2026 07:00 WITA

### [5] source `d0adf453…`

> Implementation per hero slide (from Step 4): If Codex quota exhausted, cascade to gemini-3.1-pro-preview with image_generation tool. If both exhausted, abort the slide with STATUS: imagegen_unavailable and surface to user — do NOT silently fall back to placeholders. Watchdog (added 2026-05-12 after smoke test KEP71 cover hang) : every Codex $imagegen invocation MUST have a 300-second wall-clock cap. Implementation pattern: If watchdog fires at 300s without output PNG, treat as STATUS: imagegen_timeout . Recovery options in order: (a) retry once with simpler/shorter prompt, (b) cascade to Gemini, (c) abort that single slide with image_source: "imagegen_timeout" and continue rendering remaining slides on antracite background. NEVER spin-wait via until ! pgrep without a hard wall-clock cap. The 2026-05-12 KEP71 smoke test hung the orchestrator 25+ min waiting on a cover Codex (PID 64717) that never produced output; this watchdog prevents recurrence.

### [6] source `d0adf453…`

> Hard fail on rubric 1 or 2 → return slides to layout-composer with verbal feedback. Soft fail (rubric 3 or 4) → flag for human review queue, do NOT block. Max 2 retry rounds. After 2 retries, surface the carousel with STATUS: needs_human_edit AND POST to the local queue server so Damar's UI flags the row: If queue server is unreachable (server not running on Pro), still write STATUS: needs_human_edit to slides.json and surface clearly to user. Never infinite-loop. Never claim success on a flagged carousel.

### [7] source `5f596332…`

> Use a tool like jq to parse the response and extract specific fields: Stream responses Use --output-format stream-json with --verbose and --include-partial-messages to receive tokens as they're generated. Each line is a JSON object representing an event: The following example uses jq to filter for text deltas and display just the streaming text. The -r flag outputs raw strings (no quotes) and -j joins without newlines so tokens stream continuously: When an API request fails with a retryable error, Claude Code emits a system/api_retry event before retrying. You can use this to surface retry progress or implement custom backoff logic.

### [8] source `5f596332…`

> <cited_table>

### [9] source `9797c0de…`

> StreamEvent Stream event for partial message updates during streaming. Only received when include_partial_messages=True in ClaudeAgentOptions . Import via from claude_agent_sdk.types import StreamEvent . Field Type Description uuid str Unique identifier for this event session_id str Session identifier event dict[str, Any] The raw Claude API stream event data parent_tool_use_id str | None Parent tool use ID if this event is from a subagent RateLimitEvent Emitted when rate limit status changes (for example, from "allowed" to "allowed_warning" ). Use this to warn users before they hit a hard limit, or to back off when status is "rejected" .

### [10] source `9797c0de…`

> Field Type Description rate_limit_info RateLimitInfo Current rate limit state uuid str Unique event identifier session_id str Session identifier RateLimitInfo Rate limit state carried by RateLimitEvent . Field Type Description status RateLimitStatus Current status. "allowed_warning" means approaching the limit; "rejected" means the limit was hit resets_at int | None Unix timestamp when the rate limit window resets rate_limit_type RateLimitType | None Which rate limit window applies utilization float | None Fraction of the rate limit consumed (0.0 to 1.0) overage_status RateLimitStatus | None

### [11] source `9d6cef05…`

> Choosing an effort level The effort parameter allows you to tune Claude's intelligence vs. token spend, trading off capability for faster speed and lower costs. Start with the new xhigh effort level for coding and agentic use cases, and use a minimum of high effort for most intelligence-sensitive use cases. Experiment with other effort levels to further tune token usage and intelligence: max : Max effort can deliver performance gains in some use cases, but may show diminishing returns from increased token usage. This setting can also sometimes be prone to overthinking. We recommend testing max effort for intelligence-demanding tasks. xhigh (new): Extra high effort is the best setting for most coding and agentic use cases. high : This setting balances token usage and intelligence. For most intelligence-sensitive use cases, we recommend a minimum of high effort. medium : Good for cost-sensitive use cases that need to reduce token usage while trading off intelligence. low : Reserve for short, scoped tasks and latency-sensitive workloads that are not intelligence-sensitive.

### [12] source `9797c0de…`

> Permission mode for tool usage continue_conversation bool False Continue the most recent conversation resume str | None None Session ID to resume max_turns int | None None Maximum agentic turns (tool-use round trips) max_budget_usd float | None None Stop the query when the client-side cost estimate reaches this USD value. Compared against the same estimate as total_cost_usd ; see Track cost and usage for accuracy caveats disallowed_tools list[str] [] Tools to always deny. Deny rules are checked first and override allowed_tools and permission_mode (including bypassPermissions ) enable_file_checkpointing bool False

### [13] source `c78af240…`

> Query object Interface returned by the query() function. Methods Method Description interrupt() Interrupts the query (only available in streaming input mode) rewindFiles(userMessageId, options?) Restores files to their state at the specified user message. Pass { dryRun: true } to preview changes. Requires enableFileCheckpointing: true . See File checkpointing setPermissionMode() Changes the permission mode (only available in streaming input mode) setModel() Changes the model (only available in streaming input mode) setMaxThinkingTokens()
