---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-12-pre-execution-validators-agent-prerequisites-verification

**Date**: 2026-08-12
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 16 / Citations: 23

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Pre-execution validators**: che verificano programmaticamente i requisiti (es. esistenza dei permessi, stato del worktree) prima di agire [8].

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche**

*   **Definizione e scopo del Validator:**
    > *"While governance constraints [...] declare the rules an agent must follow, validators enforce them automatically. A validator is a deterministic script embedded within a skill that verifies whether an agent's actions meet organizational standards—without requiring human approval for the verification itself. Validators transform governance from a declarative annotation into an executable guarantee."* [1]

*   **Pre-execution validators e natura del codice deterministico:**
    > *"Pre-execution validators verify preconditions before the agent acts. Examples include confirming that the change management window is open, that the requesting identity holds the required permissions, that all continuous integration checks have passed..."* [2]
    > *"Critically, validators are code, not prose. They are implemented as shell scripts, Python checks, or policy-as-code frameworks such as Open Policy Agent. They are version-controlled alongside the skills they govern, independently testable in isolation, and produce deterministic pass/fail results..."* [3]

*   **Vantaggio del codice rispetto alle istruzioni testuali:**
    > *"Advanced technique: For critical validations, consider bundling a script that performs the checks programmatically rather than relying on language instructions. Code is deterministic; language interpretation isn't."* [4]

---

### **2. Confronto con l'applicazione reale nel nostro stack (Bali Zero / Nuzantara)**

Nel nostro ecosistema multi-agente di produzione, applichiamo i pre-execution validators per garantire stabilità ed evitare esecuzioni errate:

*   **Preflight unificato tramite `_audit-checklist.sh`:** Invece di consentire all'orchestratore principale `wr2-design-architect` di eseguire decine di singole verifiche inefficienti e costose in termini di token, abbiamo centralizzato il controllo iniziale in un'unica chiamata deterministica: `MODE=preflight SLUG=<slug> DOMAIN=<domain> bash _audit-checklist.sh` [5]. Questo validatore pre-esecuzione verifica in una sola operazione la presenza fisica dei sub-agenti sul disco, l'esistenza dei file della brand cortex, lo SHA dell'ancora di dominio e la versione della CLI prima di autorizzare l'inizio del turno [5].
*   **Pre-brief sweep contro la deriva delle informazioni (*Brief Stale Premise*):** Prima di redigere un brief basato su spec storiche o regole del registro, l'orchestratore esegue un controllo empirico di 60-120 secondi contro `HEAD` (es. interrogando database SQLite o file di configurazione attivi) [6]. Questo reality-check genera un audit log immutabile con timestamp e comandi reali, impedendo l'avvio della pipeline su premesse obsolete [7].
*   **Controlli di pre-condizione dei sub-agenti operativi:** I nostri sub-agenti dedicati alla generazione dei testi e dei layout, come `email-template-builder` o `client-case-quote-generator`, eseguono controlli preventivi sui file di supporto [8, 9]. Se verificano l'assenza della `constitution.md`, del template CSS di base o del dizionario delle forbidden phrases, arrestano immediatamente l'esecuzione emettendo un errore formale (es. *"ERROR brand cortex incomplete"* o *"ERROR internal-print-a4 surface incomplete"*), proteggendo la REPL madre da elaborazioni a vuoto [8, 9].
*   **Pre-flight di isolamento dell'ambiente virtuale (`.venv`):** Nel wrapper di esecuzione `wr2-script-wrapper.sh`, eseguiamo un pre-flight check specifico per proteggere l'ambiente dai temibili loop di collegamenti simbolici generati dai cambi di checkout paralleli [10, 11]. Il controllo verifica che il binario Python nel venv esista e sia effettivamente eseguibile prima di lanciare le pipeline di calcolo (`[[ ! -e ... || ! -x ... ]]`) [11].

---

### **3. Linea di azione concreta per la libreria Bali Zero**

Per istituzionalizzare la difesa contro i fallimenti silenziosi dovuti ai blocchi di sicurezza interattivi (regole `ask` che diventano `denied` automatici nei sub-agenti headless), dobbiamo implementare un validatore di pre-esecuzione standardizzato.

*   **Azione:** Creare e integrare nello script unificato `_audit-checklist.sh` la modalità **`validate-execution-sandbox`**.
*   **Dettaglio dell'implementazione:**
    1.  **Verifica dell'isolamento VCS:** Lo script deve eseguire `git rev-parse --git-common-dir` e verificare se `GIT_DIR != GIT_COMMON` [12]. Se l'agente tenta di operare nel checkout principale condiviso invece di un worktree isolato (violando la deploy isolation), il validatore interrompe l'esecuzione con codice di uscita `2` (Blocking error) [12-14].
    2.  **Verifica dei permessi di scrittura e dei percorsi protetti:** Il validatore esegue un controllo preventivo di scrittura (`touch` e successiva rimozione) nelle directory di destinazione e nei path temporanei prima di lanciare i tool di modifica [15]. Inoltre, scansiona `.claude/settings.json` per assicurarsi che i percorsi critici (es. `.claude/skills` o `.env`) siano protetti e che le policy di default non includano restrizioni incompatibili con i compiti assegnati [16, 17].
    3.  **Sanificazione e disponibilità delle dipendenze esterne:** Lo script convalida la presenza e l'autenticazione delle CLI necessarie (es. `gh` autenticata per i comandi di pull request, `ripgrep` o `ollama` locale) [18, 19]. In caso di fallimento, restituisce un report strutturato in formato JSON tramite `stderr`, impedendo all'agente di procedere ed evitando l'attivazione di risposte di fallback non sicure [20, 21].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Considerando l'analogia della **"Type-Safety" applicata alla composizione dei validatori**, in che modo possiamo fare in modo che quando l'orchestratore progetta dinamicamente una pipeline a runtime (*AI-Generated Golden Path*), l'unione dei validatori pre-esecuzione di ciascuna skill venga ereditata e compilata in un unico preflight logico centralizzato? [22]
2.  Dato che la transizione alla filosofia della **"governance-as-code"** sposta il controllo dall'approvazione umana alla scrittura dei test, come possiamo strutturare una suite di test di regressione isolati per i nostri validatori bash, garantendo che le modifiche alla `constitution.md` vengano tradotte in codice senza introdurre discrepanze o falsi positivi nei controlli di sicurezza? [22-24]
3.  In contesti in cui un pre-execution validator rileva un blocco o una restrizione di accesso (es. un'operazione che richiede un'autorizzazione asincrona elevata), quali sono i pattern migliori per implementare un **"conditional bypass"** basato sul calcolo automatico dell'impatto o del blast radius dell'azione dell'agente? [25-27]

## Sources used (16)

- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `ba6046c6-411b-4f77-9da9-42448ce75238`
- `8d0ba049-2c1b-4b1e-a05f-c284d7abb3ec`
- `3bcf9ef7-b926-4bfa-97d8-2d733b142a12`
- `d3754c90-db00-4a20-a83e-59d84d5dc409`
- `1989f96d-c5c2-4ded-9f71-266d25ca6042`
- `5702f19a-011f-4ca1-9ba4-4c7b0c3e02d7`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `6f16fd65-565d-491d-8db8-e2b095a5a064`
- `366690aa-8295-4154-a4f6-efbeebf25954`
- `7e015fa6-1820-4ef4-8c3d-9365b4dc9a69`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`
- `92b09121-412d-4ece-a88e-86b922424a15`
- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `b4852cc9-6ae0-43c1-8408-42c330cb05a5`

## Citations verbatim (23)

### [1] source `d0adf453…`

> Test-5 cost $10.07 / 29min because the orchestrator made 107 Bash + 50 Read = 165 tool calls for verifications that fit into ONE bash script. Test-6 onward MUST use the consolidated audit script: Modes (pass via env vars MODE , SLUG , DOMAIN ): MODE=preflight SLUG=<slug> DOMAIN=<tax|visa|property|regulatory|health> bash _audit-checklist.sh — runs all preflight checks (4 subagents present, brand cortex files, domain anchor sha, codex CLI version, slug uniqueness) in ONE invocation. Replaces ~12 separate Bash probes. MODE=setup-outdir SLUG=<slug> bash _audit-checklist.sh — creates output dir + copies logo/_base.css/hammurabi-stele in one shot. Replaces ~5 cp/mkdir calls. MODE=hero-sha SLUG=<slug> DOMAIN=<domain> bash _audit-checklist.sh — Article 5.10 verification: computes anchor sha + every hero sha, asserts each per slide_spec.image_source declaration. Replaces 5 separate shasum calls + sliding logic. MODE=render-check SLUG=<slug> bash _audit-checklist.sh — verifies all PNG renderings exist + 1080×1350 dimensions via sips. Replaces sips loop. MODE=final-audit SLUG=<slug> bash _audit-checklist.sh — Step 0 self-audit: counts Agent calls, NB queries, imagegen sessions, anchor reuse declared, placeholders reused. Outputs the 4 self-audit lines.

### [2] source `ba6046c6…`

> Rule Prima di scrivere un brief che derivi da cicatrix entry / MEMORY.md / design doc / spec esistente, l'orchestrator DEVE eseguire empirical sweep di 60-120s contro HEAD. Non basta verificare che i file menzionati esistano; bisogna verificare che lo stato descritto sia ancora vero. Specificamente per ogni claim di scope: <cited_table>

### [3] source `ba6046c6…`

> Pre-brief checklist obbligatoria (prima di scrivere brief) Format brief con verifiche cite Il brief deve includere sezione "Reality-check verified by orchestrator" con: Timestamp empirical sweep Exact command + output usato Source of any number > simple count Esempio (correct): Esempio (wrong, what I did 4×): Cross-ref lessons_close_out_numbers_unverified.md — same family (numbers in close-out) lessons_wave_pacing_design_rigor.md §"orchestrator brief reality-check" — rule for sub-session, but applies to orchestrator first 4 incident docs: W2-D pivot: PR #498 (cell-core ADR) FASE 4 halt: ~/.agent/decisions/halts/fase4_hgt_activation_2026_05_08.md FASE 6 defer: docs/superpowers/specs/2026-05-08-bridge-b-decision.md IG-2 halt: ~/.agent/decisions/halts/ig-2.md + docs/igiene/2026-05-08-ig-2-halt.md (committed but PR #527 closed)

### [4] source `8d0ba049…`

> Before doing anything, verify: ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4.md exists. ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_template.css exists. ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_render.py exists and is executable. ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/example-brief.html exists. If ANY missing, abort with ERROR internal-print-a4 surface incomplete . The surface is required (constitution Article 12). Workflow

### [5] source `3bcf9ef7…`

> Pre-condition check ~/.claude/skills/bali-zero-brand/constitution.md — Articles 2, 3, 6.3-6.7, 7, 8 (cross-surface mandatory). ~/.claude/skills/bali-zero-brand/surfaces/email-template.md — surface-specific spec. ~/.claude/skills/bali-zero-brand/voice/forbidden-phrases.md — closed-set ban. ~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md — voice calibration. ~/.claude/skills/bali-zero-brand/tokens.json — palette tokens. If any missing, abort with ERROR brand cortex incomplete . Workflow

### [6] source `d3754c90…`

> Architettura nuova wr2-script-wrapper.sh patch (linea 30-37): Override env var WR2_REPO_ROOT per debug/testing — default è worktree dedicato. Setup procedure (one-time done 2026-05-06 19:17) How to update (every time main has new commits) Idempotent. Worktree is on branch deploy/main tracking origin/main — pure pull-only, no commits ever land here. Verify deploy active Self-loop .venv NOT recreated by checkout (good!) Il symlink self-loop committato in b13287518 (cicatrix latente) NON viene ricreato dal git checkout nel worktree — Git considera invalid-target symlinks edge case e li skippa silently. Il worktree ha .venv come dir reale (Python 3.11 fresh), niente self-loop. Il problema architetturale del symlink in git resta latente per il main repo + 5 feature worktrees, da affrontare con PR dedicata futura.

### [7] source `1989f96d…`

> Sintomo: bash: ... .venv/bin/python: Too many levels of symbolic links . Mtime del symlink rotto: 14:54:45 — esattamente 67 secondi dopo launchctl bootstrap del supervisor (14:53:38). Causa specifica non identificata; possibili colpevoli: kickstart figlio del supervisor che esegue uno script con ln -s .venv .venv invece di ln -s ../../.venv .venv (manca ../../ ), oppure comando manuale errato. Fix applicato 2026-05-06 14:59 How to apply Mai fare ln -s .venv .venv da dentro apps/backend-rag/ (self-loop). Sempre relative ../../.venv . Se uno script o test deve "ricreare" il venv link: ln -sf ../../.venv .venv (force replace, ma il target deve essere ../../.venv , mai bare .venv ). Pre-flight check da aggiungere a wr2-script-wrapper.sh line 67-69 (già presente come [[ ! -x "$VENV_PY" ]] ) — ESPANDERE a [[ ! -e ... || ! -x ... ]] per catch self-loop early. Health monitor: launchd job che ogni 6h fa readlink apps/backend-rag/.venv e alert se contiene apps/backend-rag/.venv (self-loop).

### [8] source `5702f19a…`

> Announce at start: "I'm using the using-git-worktrees skill to set up an isolated workspace." Step 0: Detect Existing Isolation Before creating anything, check if you are already in an isolated workspace. Submodule guard: GIT_DIR != GIT_COMMON is also true inside git submodules. Before concluding "already in a worktree," verify you are not in a submodule: If GIT_DIR != GIT_COMMON (and not a submodule): You are already in a linked worktree. Skip to Step 3 (Project Setup). Do NOT create another worktree.

### [9] source `d564912c…`

> For most hook events, only exit code 2 blocks the action. Claude Code treats exit code 1 as a non-blocking error and proceeds with the action, even though 1 is the conventional Unix failure code. If your hook is meant to enforce a policy, use exit 2 . The exception is WorktreeCreate , where any non-zero exit code aborts worktree creation. Exit code 2 behavior per event Exit code 2 is the way a hook signals “stop, don't do this.” The effect depends on the event, because some events represent actions that can be blocked (like a tool call that hasn't happened yet) and others represent things that already happened or can't be prevented.

### [10] source `d3754c90…`

> -------------------------------------------------------------------------------- name: discovery_worktree_deploy_isolation description: Deployment isolation via dedicated git worktree on branch deploy/main, separate da working tree shared con sessioni multi-agent. Wrapper REPO_ROOT punta al worktree pulito. type: discovery originSessionId: 92a63010-c526-4282-a225-e2d72f00dc9c Worktree deploy isolation — Pro production cron stability Problema risolto 2026-05-06 19:17 WITA : 3+ sessioni Claude/Codex parallele attive su ~/Desktop/nuzantara (cwd shared) facevano git checkout su branch diversi ogni 1-3 min. Il wr2-script-wrapper.sh leggeva da ${HOME}/Desktop/nuzantara , quindi a seconda di chi aveva fatto checkout per ultimo, il cron eseguiva versioni diverse del codice. Risultato: PR #478 deployata su origin/main ma working tree del Pro periodicamente su feat/email-branding-followup → cron leggeva versione vecchia senza fix Codex Image-2.

### [11] source `6f0873fe…`

> Database query validator A subagent that allows Bash access but validates commands to permit only read-only SQL queries. This example shows how to use PreToolUse hooks for conditional validation when you need finer control than the tools field provides. Claude Code passes hook input as JSON via stdin to hook commands. The validation script reads this JSON, extracts the command being executed, and checks it against a list of SQL write operations. If a write operation is detected, the script exits with code 2 to block execution and returns an error message to Claude via stderr. Create the validation script anywhere in your project. The path must match the command field in your hook configuration:

### [12] source `6f16fd65…`

> 2.1.39 February 10, 2026 Improved terminal rendering performance Fixed fatal errors being swallowed instead of displayed Fixed process hanging after session close Fixed character loss at terminal screen boundary Fixed blank lines in verbose transcript view 2.1.38 February 10, 2026 Fixed VS Code terminal scroll-to-top regression introduced in 2.1.37 Fixed Tab key queueing slash commands instead of autocompleting Fixed bash permission matching for commands using environment variable wrappers Fixed text between tool uses disappearing when not using streaming Fixed duplicate sessions when resuming in VS Code extension Improved heredoc delimiter parsing to prevent command smuggling Blocked writes to .claude/skills directory in sandbox mode

### [13] source `366690aa…`

> Skip the confirmation prompt shown before entering bypass permissions mode via --dangerously-skip-permissions or defaultMode: "bypassPermissions" . Ignored when set in project settings ( .claude/settings.json ) to prevent untrusted repositories from auto-bypassing the prompt true Permission rule syntax Permission rules follow the format Tool or Tool(specifier) . Rules are evaluated in order: deny rules first, then ask, then allow. The first matching rule wins. Quick examples: <cited_table>

### [14] source `6f16fd65…`

> 1.0.120 September 19, 2025 Fix input lag during typing, especially noticeable with large prompts Improved VSCode extension command registry and sessions dialog user experience Enhanced sessions dialog responsiveness and visual feedback Fixed IDE compatibility issue by removing worktree support check Fixed security vulnerability where Bash tool permission checks could be bypassed using prefix matching 1.0.119 September 19, 2025 Fix Windows issue where process visually freezes on entering interactive mode Support dynamic headers for MCP servers via headersHelper configuration Fix thinking mode not working in headless sessions Fix slash commands now properly update allowed tools instead of replacing them

### [15] source `7e015fa6…`

> When to use All pull requests with meaningful changes PRs touching critical code paths PRs from multiple contributors PRs where guideline compliance matters When not to use Closed or draft PRs (automatically skipped anyway) Trivial automated PRs (automatically skipped) Urgent hotfixes requiring immediate merge PRs already reviewed (automatically skipped) Workflow Integration Standard PR review workflow: As part of CI/CD: Requirements Git repository with GitHub integration GitHub CLI ( gh ) installed and authenticated CLAUDE.md files (optional but recommended for guideline checking)

### [16] source `cf769fec…`

> Exit codes control behavior: - 0 : Success: operation proceeds. Stdout shown in verbose mode (Ctrl+O). For UserPromptSubmit and SessionStart , stdout is added to context. - 2 : Blocking error: operation stops. Stderr becomes the error message fed back to Claude. - 1, 3, etc. : Non-blocking error: operation continues. Stderr shown as warning in verbose mode. For advanced control, hooks can output JSON: PreToolUse decision control (preferred format): PreToolUse hooks use hookSpecificOutput for richer control: three outcomes (allow/deny/ask) plus the ability to modify tool input and inject context: 89

### [17] source `92b09121…`

> Report issue for preceding element E.1 Optimization Taxonomy Report issue for preceding element Across experiments, frequent optimizations of PSN fall into several recurring categories. Table 5 summarizes the most common failure signals and corresponding repair strategies. Report issue for preceding element <cited_table>

### [18] source `f6c76ff7…`

> The composability of validators follows a type-safety analogy: just as well-typed functions compose into type-safe programs, skills with comprehensive validators compose into governance-safe workflows. When an agent composes an AI-Generated Golden Path—a workflow assembled at runtime from available skills—the composed path inherits the union of all constituent validators. Governance safety is achieved by construction rather than by post-hoc review. Validators shift the governance team's operational model from governance-as-approval —reviewing individual agent actions as they occur—to governance-as-code —authoring, testing, and maintaining deterministic validation scripts. This shift is analogous to the Infrastructure-as-Code transformation that freed operations teams from ticket-based provisioning: the governance team's mission becomes increasing validator coverage across the skill library, progressively moving more skills toward full autonomy as validator coverage expands.

### [19] source `f6c76ff7…`

> Validators. A key mechanism for operationalizing governance without human bottlenecks is the validator : a deterministic script embedded within the skill that automatically verifies whether the agent's actions meet organizational standards. Validators are implemented as executable code—shell scripts, Python checks, or policy-as-code rules (e.g., Open Policy Agent)—that produce pass/fail results with structured logs. Unlike human approvers, validators are consistent (they apply identical rules every time), scalable (they execute in milliseconds regardless of volume), and auditable (every decision is logged with its inputs and the rule applied). By encoding governance checks as validators rather than human review gates, the framework enables governance teams to shift from governance-as-approval to governance-as-code : authoring deterministic governance artifacts that scale with the skill library rather than with headcount.

### [20] source `f6c76ff7…`

> For enterprise governance. The framework proposes that governance shifts left—from runtime enforcement to knowledge-time specification. Rather than constructing elaborate runtime guardrails that attempt to constrain arbitrary agent behavior, organizations embed governance directly into the knowledge units agents consume (Section 7 ). The validator mechanism transforms governance teams from approval bottlenecks to governance-as-code authors: by encoding standards as deterministic validators embedded in skills, governance scales with the skill library rather than with headcount—a structural resolution to the tension between agent autonomy and enterprise control.

### [21] source `f6c76ff7…`

> Approval Workflows. Skills can specify that certain actions require human sign-off before execution. A skill for scaling a production database cluster might execute autonomously in staging but require explicit confirmation when targeting production. These requirements are encoded as metadata within the skill, not as external process gates, ensuring that they travel with the knowledge unit regardless of which agent invokes it or through which orchestration path it is reached. The mechanism supports multiple patterns: synchronous blocking (the agent waits), asynchronous deferral (the agent proceeds with other tasks and returns when granted), and conditional bypass (required only when specific risk thresholds are exceeded).

### [22] source `b4852cc9…`

> naxmax2019 OP replied to Sudden-Lingonberry-8 3 days ago It doesn't go stale coz iCPG and memory (mnemos) get updated on hooks. It's literally built into the system to keep everything up to date Upvote 1 Downvote Reply reply Share Report r/ClaudeCode • Claude Bootstrap v3.6 — Cross-Agent Intelligence: Claude, Kimi, and Codex working together naxmax2019 OP replied to Deep_Ad1959 3 days ago That's right but it's by definition an impact estimate .. blast radius is just a proxy for impact prediction as I think it has to be. The key here is how accurate blast radius is and how to calculate blast radius.

### [23] source `b4852cc9…`

> ........................├ blast ≥ 8 or security? → attach validator (codex) ........................├ build fallback chain (all higher cost_ranks) ........................└ return RoutingDecision KEY THRESHOLDS: FATIGUE_ROUTING_ESCALATE = 0.60 → skip local + gemini-flash-lite FATIGUE_ROUTING_PREMIUM = 0.75 → force deepseek-pro or higher High-risk = stakes "high" OR task in security/auth/billing → skip 2 cheapest tiers Uncalibrated models (accuracy < 50%) → fallback chain only Validator attached when blast >= 8 or security_sensitive = true
