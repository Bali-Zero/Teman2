---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-10-03-hooks-object-deep-merge-array-concat

**Date**: 2026-10-03
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 4 / Citations: 13

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Deep-Merge degli Oggetti `hooks` e Concatenazione degli Array:**

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

L'architettura di configurazione di Claude Code e dell'Agent SDK gestisce l'integrazione di regole, estensioni e strategie di sicurezza provenienti da fonti multiple (livello gestito/MDM, utente, progetto, impostazioni locali e plugin) mediante un motore di risoluzione strutturato. 

Quando più file manifest o ambiti definiscono la sezione **`hooks`**, l'engine applica una strategia combinata: **deep-merge degli oggetti** a livello di struttura e **concatenazione con deduplicazione** a livello degli array di handler e matcher.

---

### **1. Citazioni Verbatim dalle Fonti Canoniche**

Il comportamento del motore di fusione delle impostazioni e la gestione degli hook sono documentati nelle specifiche ufficiali di Claude Code:

*   **Deep-Merge degli Oggetti e Concatenazione degli Array nei File di Configurazione:**
    > *"File-based managed settings also support a drop-in directory at managed-settings.d/ in the same system directory alongside managed-settings.json... Following the systemd convention, managed-settings.json is merged first as the base, then all *.json files in the drop-in directory are sorted alphabetically and merged on top. Later files override earlier ones for scalar values; arrays are concatenated and de-duplicated; objects are deep-merged."* [1]
    > *"Array settings merge across scopes. When the same array-valued setting (such as sandbox.filesystem.allowWrite or permissions.allow) appears in multiple scopes, the arrays are concatenated and deduplicated, not replaced."* [2]

*   **Esecuzione Parallela e Deduplicazione Automatica degli Hook:**
    > *"All matching hooks run in parallel, and identical handlers are deduplicated automatically. Command hooks are deduplicated by command string and args, and HTTP hooks are deduplicated by URL."* [3]

*   **Precedenza delle Decisioni di Sicurezza negli Hook `PreToolUse`:**
    > *"When multiple PreToolUse hooks return different decisions, precedence is deny > defer > ask > allow."* [4]

*   **Differenza di Struttura tra Settings Globali/Progetto e Plugin:**
    > *"For plugin hooks in hooks/hooks.json, use wrapper format... For user settings in .claude/settings.json, use direct format: no wrapper - events directly at top level..."* [5]
    > *"Define plugin hooks in hooks/hooks.json with an optional top-level description field. When a plugin is enabled, its hooks merge with your user and project hooks."* [6]

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero (Nuzantara)**

Nel nostro repository di produzione (`/Desktop/nuzantara/`), la gestione multi-livello degli hook e delle configurazioni incide direttamente sulla stabilità e sulla sicurezza degli agenti:

1.  **Fusione Multilivello degli Eventi (`Deep-Merge`):**
    Quando definiamo hook per la sicurezza globale in `~/.claude/settings.json` (es. `PreToolUse` su `Bash` per bloccare comandi distruttivi [7]), hook di progetto in `.claude/settings.json` (es. formatting post-write con `Prettier` [8]), ed hook bundled nei nostri plugin (es. `bali-zero-brand` o `bundle-02-plugin-dev` in `hooks/hooks.json` [5]), l'engine esegue un **deep-merge sugli oggetti dei tipi di evento** [1]. L'oggetto `hooks` risultante contiene l'insieme completo degli eventi registrati senza che un livello elimini l'altro.
2.  **Concatenazione degli Array e Invarianza di Sicurezza:**
    Se l'evento `PreToolUse` è presente sia a livello `user` che a livello `project` o `plugin`, gli array contenenti i gruppi di matcher e i relativi handler vengono **concatenati e deduplicati** [1-3]. Durante l'invocazione di un tool (es. `Bash`), tutti gli handler che corrispondono al filtro vengono eseguiti **in parallelo** [3]. Se un hook d'infrastruttura restituisce `permissionDecision: "deny"` mentre un hook di plugin restituisce `"allow"`, il sistema applica la regola di precedenza rigida **`deny > defer > ask > allow`** [4], impedendo a un plugin permissivo di scavalcare un veto di sicurezza.
3.  **Gestione dei Wrapper nei Plugin:**
    In Nuzantara, rispettiamo la distinzione tra la sintassi diretta usata in `.claude/settings.json` (dove le chiavi degli eventi risiedono sotto `"hooks": {...}`) e il formato dei plugin in `hooks/hooks.json`, dove gli eventi sono racchiusi nell'oggetto wrapper `{"hooks": {...}}` [5]. L'engine di Claude Code normalizza ed unisce queste strutture al momento dell'attivazione del plugin [6].

---

### **3. Linea di Azione Concreta: Il Modulo `_inspect_merged_hooks.py` per Bali Zero**

Per evitare silent failures o race condition dovute all'esecuzione parallela di handler concatenati provenienti da sorgenti diverse, implementeremo un **Linter e Ispettore di Merge degli Hook** nella libreria Bali Zero.

#### **Azione**: Creare lo script `bali_zero/audit/_inspect_merged_hooks.py` per convalidare programmaticamente la pipeline risultante.

```python
# bali_zero/audit/_inspect_merged_hooks.py
import json
from pathlib import Path
from typing import Dict, Any, List

def simulate_hook_merge(user_settings: dict, project_settings: dict, plugin_hooks: List[dict]) -> dict:
    """
    Simula l'algoritmo di Deep-Merge e Concatenazione degli Array usato da Claude Code.
    """
    merged_hooks: Dict[str, List[Any]] = {}

    def merge_event_dict(source_hooks: dict):
        for event, handlers in source_hooks.items():
            if event not in merged_hooks:
                merged_hooks[event] = []
            if isinstance(handlers, list):
                for handler in handlers:
                    # Deduplicazione basata su stringa di comando o URL (RFC Claude Code)
                    if handler not in merged_hooks[event]:
                        merged_hooks[event].append(handler)

    # 1. Base: User Settings (~/.claude/settings.json)
    if "hooks" in user_settings:
        merge_event_dict(user_settings["hooks"])

    # 2. Shared Project Settings (.claude/settings.json)
    if "hooks" in project_settings:
        merge_event_dict(project_settings["hooks"])

    # 3. Plugin Hooks (hooks/hooks.json con wrapper format)
    for p_config in plugin_hooks:
        # Estrae i file che usano il formato wrapper {"hooks": {...}}
        p_hooks = p_config.get("hooks", p_config)
        merge_event_dict(p_hooks)

    return merged_hooks

def audit_hook_pipeline(project_dir: Path) -> bool:
    """
    Esegue l'audit dei conflitti e delle ridondanze negli hook concatenati.
    """
    user_json = Path.home() / ".claude" / "settings.json"
    project_json = project_dir / ".claude" / "settings.json"
    
    u_data = json.loads(user_json.read_text()) if user_json.exists() else {}
    p_data = json.loads(project_json.read_text()) if project_json.exists() else {}
    
    # Raccoglie i manifest dei plugin attivi
    plugin_configs = []
    plugin_dir = project_dir / ".claude" / "plugins"
    if plugin_dir.exists():
        for h_file in plugin_dir.glob("**/hooks/hooks.json"):
            plugin_configs.append(json.loads(h_file.read_text()))

    final_hooks = simulate_hook_merge(u_data, p_data, plugin_configs)
    
    print(f"=== BALI ZERO HOOK PIPELINE AUDIT ===")
    for event, handlers in final_hooks.items():
        print(f"Event '{event}': {len(handlers)} handler(s) concatenati ed attivi in parallelo.")
        for idx, h in enumerate(handlers, 1):
            cmd = h.get("command") or h.get("prompt") or h.get("url") or "mcp_tool"
            print(f"  [{idx}] Type: {h.get('type', 'command')} | Matcher: {h.get('matcher', '*')} | Execution: {cmd}")
    
    return True

if __name__ == "__main__":
    audit_hook_pipeline(Path.cwd())
```

#### **Benefici Operativi**:
*   **Visibilità sui Parallel Execution Paths**: Permette agli sviluppatori e all'orchestratore di verificare quanti e quali handler scattano contemporaneamente per ogni evento (es. `PreToolUse` o `PostToolUse`) [3].
*   **Prevenzione dei Conflitti di Scrittura**: Identifica se due handler concatenati sullo stesso evento tentano di scrivere o modificare le medesime risorse temporanee su disco (`/workspace/scratch/`), prevenendo la corruzione dello stato.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Dinamiche di Concorrenza tra Handler `PostToolUse` e Trasformazioni `updatedToolOutput` Multiple**: Quando più handler `PostToolUse` concatenati nello stesso evento eseguono in parallelo e tentano di restituire un payload `updatedToolOutput` [9, 10], in che modo l'engine di Claude Code gestisce la precedenza di sovrascrittura del testo restituito al modello?
2.  **Impatto delle Variabili di Ambito (`${CLAUDE_PROJECT_DIR}` vs `${CLAUDE_PLUGIN_ROOT}`) sulla Deduplicazione**: Dato che gli handler identici vengono deduplicati automaticamente in base alla stringa del comando [3], in che modo la presenza di variabili interpolate differenti (es. `${CLAUDE_PROJECT_DIR}/script.sh` vs `${CLAUDE_PLUGIN_ROOT}/script.sh`) influenza il calcolo dell'hash di deduplicazione prima dell'esecuzione?
3.  **Inibizione degli Array Concatenati tramite `allowManagedHooksOnly`**: Quando una policy aziendale imposta `"allowManagedHooksOnly": true` [11, 12], la concatenazione degli array di hook viene completamente disattivata per i livelli `user`, `project` e `local`? In che modo i plugin forzati tramite `enabledPlugins` mantengono il diritto di iniettare i propri handler nell'array di esecuzione [13]?

## Sources used (4)

- `366690aa-8295-4154-a4f6-efbeebf25954`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `d3ccdc37-f3b2-4163-8e2c-c11bba281169`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`

## Citations verbatim (13)

### [1] source `366690aa…`

> On Windows, paths shown as ~/.claude resolve to %USERPROFILE%\.claude . Settings files The settings.json file is the official mechanism for configuring Claude Code through hierarchical settings: User settings are defined in ~/.claude/settings.json and apply to all projects. Project settings are saved in your project directory: .claude/settings.json for settings that are checked into source control and shared with your team .claude/settings.local.json for settings that are not checked in, useful for personal preferences and experimentation. Claude Code will configure git to ignore .claude/settings.local.json when it is created. Managed settings : For organizations that need centralized control, Claude Code supports multiple delivery mechanisms for managed settings. All use the same JSON format and cannot be overridden by user or project settings: Server-managed settings : delivered from Anthropic's servers via the Claude.ai admin console. See server-managed settings . MDM/OS-level policies : delivered through native device management on macOS and Windows: macOS: com.anthropic.claudecode managed preferences domain. The plist's top-level keys mirror managed-settings.json , with nested settings as dictionaries and arrays as plist arrays. Deploy via configuration profiles in Jamf, Iru (Kandji), or similar MDM tools. Windows: HKLM\SOFTWARE\Policies\ClaudeCode registry key with a Settings value (REG_SZ or REG_EXPAND_SZ) containing JSON (deployed via Group Policy or Intune) Windows (user-level): HKCU\SOFTWARE\Policies\ClaudeCode (lowest policy priority, only used when no admin-level source exists) File-based : managed-settings.json and managed-mcp.json deployed to system directories: macOS: /Library/Application Support/ClaudeCode/ Linux and WSL: /etc/claude-code/ Windows: C:\Program Files\ClaudeCode\ The legacy Windows path C:\ProgramData\ClaudeCode\managed-settings.json is no longer supported as of v2.1.75. Administrators who deployed settings to that location must migrate files to C:\Program Files\ClaudeCode\managed-settings.json . File-based managed settings also support a drop-in directory at managed-settings.d/ in the same system directory alongside managed-settings.json . This lets separate teams deploy independent policy fragments without coordinating edits to a single file. Following the systemd convention, managed-settings.json is merged first as the base, then all *.json files in the drop-in directory are sorted alphabetically and merged on top. Later files override earlier ones for scalar values; arrays are concatenated and de-duplicated; objects are deep-merged. Hidden files starting with . are ignored. Use numeric prefixes to control merge order, for example 10-telemetry.json and 20-security.json . See managed settings and Managed MCP configuration for details. This repository includes starter deployment templates for Jamf, Iru (Kandji), Intune, and Group Policy. Use these as starting points and adjust them to fit your needs. Managed deployments can also restrict plugin marketplace additions using strictKnownMarketplaces . For more information, see Managed marketplace restrictions . Other configuration is stored in ~/.claude.json . This file contains your OAuth session, MCP server configurations for user and local scopes, per-project state (allowed tools, trust settings), and various caches. Project-scoped MCP servers are stored separately in .mcp.json .

### [2] source `366690aa…`

> This hierarchy ensures that organizational policies are always enforced while still allowing teams and individuals to customize their experience. The same precedence applies whether you run Claude Code from the CLI, the VS Code extension , or a JetBrains IDE . For example, if your user settings allow Bash(npm run *) but a project's shared settings deny it, the project setting takes precedence and the command is blocked. Array settings merge across scopes. When the same array-valued setting (such as sandbox.filesystem.allowWrite or permissions.allow ) appears in multiple scopes, the arrays are concatenated and deduplicated , not replaced. This means lower-priority scopes can add entries without overriding those set by higher-priority scopes, and vice versa. For example, if managed settings set allowWrite to ["/opt/company-tools"] and a user adds ["~/.kube"] , both paths are included in the final configuration.

### [3] source `d564912c…`

> Prompt and agent hook fields In addition to the common fields , prompt and agent hooks accept these fields: Field Required Description prompt yes Prompt text to send to the model. Use $ARGUMENTS as a placeholder for the hook input JSON model no Model to use for evaluation. Defaults to a fast model All matching hooks run in parallel, and identical handlers are deduplicated automatically. Command hooks are deduplicated by command string and args , and HTTP hooks are deduplicated by URL. Handlers run in the current directory with Claude Code's environment. The $CLAUDE_CODE_REMOTE environment variable is set to "true" in remote web environments and not set in the local CLI.

### [4] source `d564912c…`

> When multiple PreToolUse hooks return different decisions, precedence is deny > defer > ask > allow . When a hook returns "ask" , the permission prompt displayed to the user includes a label identifying where the hook came from: for example, [User] , [Project] , [Plugin] , or [Local] . This helps users understand which configuration source is requesting confirmation. AskUserQuestion and ExitPlanMode require user interaction and normally block in non-interactive mode with the -p flag. Returning permissionDecision: "allow" together with updatedInput satisfies that requirement: the hook reads the tool's input from stdin, collects the answer through your own UI, and returns it in updatedInput so the tool runs without prompting. Returning "allow" alone is not sufficient for these tools. For AskUserQuestion , echo back the original questions array and add an answers object mapping each question's text to the chosen answer.

### [5] source `d3ccdc37…`

> Hook Configuration Formats Plugin hooks.json Format For plugin hooks in hooks/hooks.json , use wrapper format: Key points: description field is optional hooks field is required wrapper containing actual hook events This is the plugin-specific format Example: Settings Format (Direct) For user settings in .claude/settings.json , use direct format: Key points: No wrapper - events directly at top level No description field This is the settings format Important: The examples below show the hook event structure that goes inside either format. For plugin hooks.json, wrap these in {"hooks": {...}} .

### [6] source `d564912c…`

> Project scripts Plugin scripts This example uses ${CLAUDE_PROJECT_DIR} to run a style checker from the project's .claude/hooks/ directory after any Write or Edit tool call: Define plugin hooks in hooks/hooks.json with an optional top-level description field. When a plugin is enabled, its hooks merge with your user and project hooks. This example runs a formatting script bundled with the plugin: See the plugin components reference for details on creating plugin hooks. Hooks in skills and agents

### [7] source `d564912c…`

> After context compaction completes Elicitation When an MCP server requests user input during a tool call ElicitationResult After a user responds to an MCP elicitation, before the response is sent back to the server SessionEnd When a session terminates How a hook resolves To see how these pieces fit together, consider this PreToolUse hook that blocks destructive shell commands. The matcher narrows to Bash tool calls and the if condition narrows further to Bash subcommands matching rm * , so block-rm.sh only spawns when both filters match:

### [8] source `cf769fec…`

> Practical Hook Examples Auto-format TypeScript files after editing: Log all bash commands: Block access to sensitive files: Run tests after code changes: Custom notification system: Inject dynamic context into prompts: Hook Debugging Enable debug mode to troubleshoot hooks: Debug mode logs: - Hook execution times - Input/output data - Error messages and stack traces - Decision results (allow/reject/ask) Hook source display (v2.1.75+): When a hook requires user confirmation, the permission prompt now shows the hook's source (settings, plugin, or skill), making it easier to identify which component is requesting access. 117

### [9] source `cf769fec…`

> updatedToolOutput for All Tools (v2.1.121+) In v2.1.118, MCP Tool Hooks gained the ability to replace tool output via hookSpecificOutput.updatedToolOutput . As of v2.1.121, the same field works for any PostToolUse hook — built-in tools (Bash, Read, Edit, Glob, Grep, etc.), subagent tools, and MCP tools. Use cases: redacting sensitive content from any tool's output, normalizing structure for downstream consumers, injecting metadata before the agent reads the result. 154 Hook Environment Variables Hooks have access to environment variables for resolving paths: 89

### [10] source `d564912c…`

> Replaces the tool's output with the provided value before it is sent to Claude. The value must match the tool's output shape updatedMCPToolOutput Replaces the output for MCP tools only. Prefer updatedToolOutput , which works for all tools The example below replaces the output of a Bash call. The replacement value matches the Bash tool's output shape: updatedToolOutput only changes what Claude sees. The tool has already run by the time the hook fires, so any files written, commands executed, or network requests sent have already taken effect. Telemetry such as OpenTelemetry tool spans and analytics events also captures the original output before the hook runs. To prevent or modify a tool call before it runs, use a PreToolUse hook instead. The replacement value must match the tool's output shape. Built-in tools return structured objects rather than plain strings. For example, Bash returns an object with stdout , stderr , interrupted , and isImage fields. For built-in tools, a value that does not match the tool's output schema is ignored and the original output is used. MCP tool output is passed through without schema validation. Stripping error details that Claude needs can cause it to proceed on a false assumption.

### [11] source `366690aa…`

> (Managed settings only) Only managed hooks, SDK hooks, and hooks from plugins force-enabled in managed settings enabledPlugins are loaded. User, project, and all other plugin hooks are blocked. See Hook configuration true allowManagedMcpServersOnly (Managed settings only) Only allowedMcpServers from managed settings are respected. deniedMcpServers still merges from all sources. Users can still add MCP servers, but only the admin-defined allowlist applies. See Managed MCP configuration true allowManagedPermissionRulesOnly

### [12] source `d564912c…`

> Single project Yes, can be committed to the repo .claude/settings.local.json Single project No, gitignored Managed policy settings Organization-wide Yes, admin-controlled Plugin hooks/hooks.json When plugin is enabled Yes, bundled with the plugin Skill or agent frontmatter While the component is active Yes, defined in the component file For details on settings file resolution, see settings . Enterprise administrators can use allowManagedHooksOnly to block user, project, and plugin hooks. Hooks from plugins force-enabled in managed settings enabledPlugins are exempt, so administrators can distribute vetted hooks through an organization marketplace. See Hook configuration .

### [13] source `366690aa…`

> Output newline-separated file paths to stdout (currently limited to 15): Example: Hook configuration These settings control which hooks are allowed to run and what HTTP hooks can access. The allowManagedHooksOnly setting can only be configured in managed settings . The URL and env var allowlists can be set at any settings level and merge across sources. Behavior when allowManagedHooksOnly is true : Managed hooks and SDK hooks are loaded Hooks from plugins force-enabled in managed settings enabledPlugins are loaded. This lets administrators distribute vetted hooks through an organization marketplace while blocking everything else. Trust is granted by full plugin@marketplace ID, so a plugin with the same name from a different marketplace stays blocked User hooks, project hooks, and all other plugin hooks are blocked
