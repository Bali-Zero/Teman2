---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-31-sparse-checkout-excluded-paths-worktreeinclude-behavior

**Date**: 2026-08-31
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 10 / Citations: 14

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   Dato che l'uso di **`worktree.sparsePaths`** restringe programmaticamente la checkout di Git solo a determinate directory nel monorepo [1], in che modo l'interprete di `.worktreeinclude` gestisce la copia di file situati in percorsi che sono stati esclusi dallo sparse-checkout (es. se proviamo a includere `packages/secret-keys/.env` ma `packages/secret-keys` non è presente nell'array dei percorsi)?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

Nell'architettura monorepo di Claude Code e dell'Agent SDK, l'interazione tra l'ottimizzazione del checkout tramite `worktree.sparsePaths` e l'iniezione dei segreti locali tramite `.worktreeinclude` rappresenta un punto di attrito critico. 

---

### **1. Citazioni Verbatim dalle Fonti Canoniche**

*   **Definizione di `worktree.sparsePaths`:**
    > *"worktree.sparsePaths: Directories to check out in each worktree via git sparse-checkout. Only the listed directories plus root-level files are written to disk, which is faster in large monorepos [\"packages/my-app\", \"shared/utils\"]"* [1].

*   **Iniezione dei file gitignored tramite `.worktreeinclude`:**
    > *"To copy gitignored files like .env into new worktrees, use a .worktreeinclude file in your project root instead of a setting."* [1].

*   **Il Bypass dell'inclusione nativa in caso di Hook personalizzato:**
    > *"Because the hook replaces the default behavior entirely, .worktreeinclude is not processed. If you need to copy local configuration files like .env into the new worktree, do it inside your hook script."* [2].

*   **I pericoli dei comportamenti "Unsafe Fallback" o silenti (arXiv - PSN):**
    > *"Unsafe fallback: silent execution failure -> Enforce fail-fast behavior"* [3].
    > *"PSN removes the unsafe fallback and enforces fail-fast behavior, ensuring that execution failures are explicitly surfaced and handled by upstream skills"* [3, 4].

#### **Analisi del comportamento sull'Edge-Case:**
**Le fonti non documentano esplicitamente come l'interprete nativo gestisca l'assenza fisica delle cartelle genitrici** quando si tenta di copiare un file definito in `.worktreeinclude` (es. `packages/secret-keys/.env`) in un percorso che lo sparse-checkout ha escluso dal disco. 

Tuttavia, basandoci sulla logica dei sistemi operativi e sul codice dell'Agent SDK, se un file di configurazione punta a una directory non checkoutata (esclusa da `sparsePaths`), l'operazione di copia nativa si trova davanti a un bivio:
1.  **Fallimento per Directory Mancante (`ENOENT`):** Se il motore interno di Claude Code esegue una copia elementare senza un comando ricorsivo di creazione directory (come `mkdir -p`), il sub-agente fallirà l'inizializzazione del worktree, sollevando un'eccezione non gestita.
2.  **Violazione dei Pattern di Sparse-Checkout:** Se la copia forza la scrittura del file scrivendo sul filesystem, la cartella `packages/secret-keys/` apparirà improvvisamente sul disco ma come entità estranea non tracciata dall'indice sparse di Git, provocando potenziali anomalie o "derive di stato" quando l'agente esegue comandi `git status` o `git diff` nel worktree.

---

### **2. Confronto con l'Infrastruttura Reale di Bali Zero**

Nel nostro monorepo reale, gestiamo costantemente le problematiche legate ai percorsi isolati e alle dipendenze condivise:

*   **Il Caso dei Checkout Concorrenti (Incident 2026-05-06):**
    In passato, l'esecuzione di più sessioni parallele nella stessa directory principale (`~/Desktop/nuzantara`) causava collisioni distruttive poiché le sessioni eseguivano checkout concorrenti alterando la `HEAD` attiva e mandando in blocco il cron di produzione [5]. Per risolvere questo, abbiamo isolato i lavoratori in worktree temporanei (es. `nuzantara-oracle`, `nuzantara-seo`) [6].
*   **La Trappola dei Collegamenti Simbolici (`lessons_backend_rag_venv_symlink`):**
    Il nostro monorepo presenta collegamenti simbolici relativi delicati per l'ambiente virtuale (`apps/backend-rag/.venv -> ../../.venv`) [7]. Quando i sub-agenti venivano instradati nei loro worktree isolati, questi symlink si rompevano o entravano in "self-loop" puntando a se stessi [8], provocando crash a cascata a causa di percorsi orfani [8].
*   **Il Rischio delle Premesse Obsolete (*Brief Stale Premise*):**
    Se usassimo `sparsePaths` per isolare un sub-agente (ad esempio, checkoutando solo la directory `apps/war-room`) ma il lavoratore cercasse di accedere a configurazioni o a indici SQLite esclusi, la pipeline fallirebbe. Attualmente, l'orchestratore mitiga questo rischio eseguendo un pre-brief sweep empirico di 60-120 secondi per convalidare lo stato effettivo di `HEAD` prima di lanciare i lavoratori [9].

---

### **3. Linea di Azione Concreta per la Libreria Bali Zero**

Considerando che l'interprete nativo di `.worktreeinclude` potrebbe fallire in presenza di percorsi esclusi dallo sparse-checkout, non possiamo affidarci a un comportamento probabilistico. Dobbiamo rendere deterministica la creazione dell'ambiente applicando la filosofia del **fail-fast** [3, 4].

*   **Azione:** Implementare un hook **`WorktreeCreate`** personalizzato e centralizzato nella nostra libreria che gestisca programmaticamente sia lo sparse-checkout che la propagazione dei segreti.

*   **Implementazione Operativa (in `.claude/hooks/worktree-create.sh`):**
    1.  **Sostituzione del comportamento nativo:** L'hook intercetta l'evento di creazione del worktree [2, 10].
    2.  **Lettura di `sparsePaths`:** Legge programmaticamente l'array `worktree.sparsePaths` definito in `.claude/settings.json` [1].
    3.  **Configurazione di Git Sparse-Checkout:** Esegue l'inizializzazione del worktree ed applica i filtri corretti:
        ```bash
        git worktree add --no-checkout "$WORKTREE_PATH" "$BASE_REF"
        cd "$WORKTREE_PATH"
        git sparse-checkout init --cone
        git sparse-checkout set "apps/war-room" "shared/utils" # Esempio di percorsi attivi
        ```
    4.  **Generazione deterministica dei percorsi per `.worktreeinclude`:**
        Invece di lasciare che Claude Code copi alla cieca, l'hook analizza il file `.worktreeinclude` della radice. Per ogni riga (es. `packages/secret-keys/.env`):
        *   Usa un comando di pre-flight per estrarre la directory genitrice (`packages/secret-keys`).
        *   Esegue programmaticamente un `mkdir -p "$WORKTREE_PATH/packages/secret-keys"` per creare in modo sicuro la directory prima che Git o la copia generino errori di assenza percorso.
        *   Copia fisicamente il file dal checkout principale: `cp "$CLAUDE_PROJECT_DIR/packages/secret-keys/.env" "$WORKTREE_PATH/packages/secret-keys/.env"`.
    5.  **Output:** Stampa su `stdout` il percorso assoluto del worktree per restituire il controllo a Claude Code [2, 11].

Questo validatore pre-esecuzione garantisce la "Type-Safety" architetturale dell'ambiente di lavoro, prevenendo errori silenziosi di inizializzazione nei nostri monorepo complessi.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Se un file di configurazione (come `.env`) viene copiato forzatamente in un percorso escluso dallo sparse-checkout, come reagisce il demone interno di monitoraggio dei file di Claude Code (**`FileChanged`** [10])? Rileverà le modifiche in background in una cartella esclusa o il filtro di sparse-checkout impedirà del tutto la notifica dell'evento?
2.  In che modo l'uso combinato di **`worktree.symlinkDirectories`** [1] (es. per linkare `node_modules` dal main repo) si comporta quando la directory di destinazione nel worktree non è ancora stata creata a causa delle restrizioni di `sparsePaths`? Il symlink viene creato orfano o si verifica un blocco bloccante?
3.  Considerando che l'Agent SDK applica l'ottimizzazione del prompt-caching tramite l'opzione **`excludeDynamicSections`** [12, 13] (che rimuove la directory corrente e lo stato git dal prompt di sistema), in che modo l'esecuzione in worktree con sparse-checkout asimmetrici influisce sul riutilizzo della cache se i sub-agenti operano con indici di codice incompleti (LSP tool [14])?

***

👉 *Se vuoi, posso scrivere lo script completo dell'hook `WorktreeCreate` in `/workspace/scratch/` e simulare un checkout monorepo parziale per convalidare il comportamento del parser prima di applicarlo al nostro ambiente stabile.*

## Sources used (10)

- `366690aa-8295-4154-a4f6-efbeebf25954`
- `d564912c-d42e-46c0-9824-feafd00f7a9e`
- `92b09121-412d-4ece-a88e-86b922424a15`
- `d3754c90-db00-4a20-a83e-59d84d5dc409`
- `8310211e-4024-4a1f-a9cd-7b27d60e3420`
- `1989f96d-c5c2-4ded-9f71-266d25ca6042`
- `ba6046c6-411b-4f77-9da9-42448ce75238`
- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `c812a01a-17bf-4375-b9fc-6cc7b0bba55c`
- `cf769fec-b4ec-46f5-b30b-b412f846223a`

## Citations verbatim (14)

### [1] source `366690aa…`

> Directories to symlink from the main repository into each worktree to avoid duplicating large directories on disk. No directories are symlinked by default ["node_modules", ".cache"] worktree.sparsePaths Directories to check out in each worktree via git sparse-checkout. Only the listed directories plus root-level files are written to disk, which is faster in large monorepos ["packages/my-app", "shared/utils"] To copy gitignored files like .env into new worktrees, use a .worktreeinclude file in your project root instead of a setting.

### [2] source `d564912c…`

> Field Description watchPaths Array of absolute paths. Replaces the current dynamic watch list (paths from your matcher configuration are always watched). Use this when your hook script discovers additional files to watch based on the changed file FileChanged hooks have no decision control. They cannot block the file change from occurring. WorktreeCreate When you run claude --worktree or a subagent uses isolation: "worktree" , Claude Code creates an isolated working copy using git worktree . If you configure a WorktreeCreate hook, it replaces the default git behavior, letting you use a different version control system like SVN, Perforce, or Mercurial. Because the hook replaces the default behavior entirely, .worktreeinclude is not processed. If you need to copy local configuration files like .env into the new worktree, do it inside your hook script. The hook must return the absolute path to the created worktree directory. Claude Code uses this path as the working directory for the isolated session. Command hooks print it on stdout; HTTP hooks return it via hookSpecificOutput.worktreePath . This example creates an SVN working copy and prints the path for Claude Code to use. Replace the repository URL with your own:

### [3] source `92b09121…`

> Report issue for preceding element E.1 Optimization Taxonomy Report issue for preceding element Across experiments, frequent optimizations of PSN fall into several recurring categories. Table 5 summarizes the most common failure signals and corresponding repair strategies. Report issue for preceding element <cited_table>

### [4] source `92b09121…`

> Report issue for preceding element Example 2: Unsafe Fallback ( ensureFlint). Report issue for preceding element Failure signal. The skill exhibits silent or inconsistent failures when attempting to mine gravel. Root cause. An unsafe fallback bypasses the system's primitive execution contract, preventing proper failure propagation to the planner. Repair. PSN removes the unsafe fallback and enforces fail-fast behavior, ensuring that execution failures are explicitly surfaced and handled by upstream skills. Outcome. The repaired skill behaves consistently and enables reliable replanning under failure.

### [5] source `d3754c90…`

> -------------------------------------------------------------------------------- name: discovery_worktree_deploy_isolation description: Deployment isolation via dedicated git worktree on branch deploy/main, separate da working tree shared con sessioni multi-agent. Wrapper REPO_ROOT punta al worktree pulito. type: discovery originSessionId: 92a63010-c526-4282-a225-e2d72f00dc9c Worktree deploy isolation — Pro production cron stability Problema risolto 2026-05-06 19:17 WITA : 3+ sessioni Claude/Codex parallele attive su ~/Desktop/nuzantara (cwd shared) facevano git checkout su branch diversi ogni 1-3 min. Il wr2-script-wrapper.sh leggeva da ${HOME}/Desktop/nuzantara , quindi a seconda di chi aveva fatto checkout per ultimo, il cron eseguiva versioni diverse del codice. Risultato: PR #478 deployata su origin/main ma working tree del Pro periodicamente su feat/email-branding-followup → cron leggeva versione vecchia senza fix Codex Image-2.

### [6] source `8310211e…`

> Setup Macchina : Air ( <user>@<host> ), 16GB M4, ~/Projects/nuzantara Venv condiviso : creato ~/Projects/nuzantara/apps/backend-rag/.venv (Python 3.13.7) con pytest+httpx, symlinkato nei 4 worktree (pattern lesson osservability POC 21/04) Worktree : 4 branch fresh da origin/main (commit f819c60ee ) session/oracle-tests → ~/Projects/nuzantara-oracle session/seo-integration → ~/Projects/nuzantara-seo session/kg-gaps → ~/Projects/nuzantara-kg session/orchestrator-audit → ~/Projects/nuzantara-orchestrator Wrapper script : ~/launch-wave.sh <session> <worktree> <prompt-file> per evitare shell-escape hell Claude flags : --model claude-opus-4-7[1m] --effort max --dangerously-skip-permissions tmux sessions : wave-oracle , wave-seo , wave-kg , wave-orchestrator

### [7] source `1989f96d…`

> -------------------------------------------------------------------------------- name: lessons_backend_rag_venv_symlink description: apps/backend-rag/.venv è SYMLINK al root .venv del repo, non un venv reale. Trap: sovrascritto in self-loop si rompe in cascata su tutti i 5 worktree. type: feedback originSessionId: 92a63010-c526-4282-a225-e2d72f00dc9c apps/backend-rag/.venv symlink convention + self-loop trap Convention : apps/backend-rag/.venv → ../../.venv (relative symlink) → punta al root venv del repo /Users/nuzantara/Desktop/nuzantara/.venv (Python 3.14, asyncpg + playwright + tutte le deps WR2 installate).

### [8] source `1989f96d…`

> NON è un venv reale . Tutti gli script che usano apps/backend-rag/.venv/bin/python (incluso wr2-script-wrapper.sh:67 ) finiscono per eseguire il root venv via symlink resolution. Stesso pattern nei 5 worktree : ogni .worktrees/*/apps/backend-rag/.venv è symlink al parent .venv , NON al root. Quando il parent symlink si rompe, tutti e 5 i worktree vanno giù in cascata. Why: incident 2026-05-06 14:54 Durante il fix supervisor errno-8 (vedi discovery_wr2_supervisor_dsn_bug_2026_05_06.md ), apps/backend-rag/.venv è stato sovrascritto in self-loop : .venv → /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv (puntava a se stesso).

### [9] source `ba6046c6…`

> Rule Prima di scrivere un brief che derivi da cicatrix entry / MEMORY.md / design doc / spec esistente, l'orchestrator DEVE eseguire empirical sweep di 60-120s contro HEAD. Non basta verificare che i file menzionati esistano; bisogna verificare che lo stato descritto sia ancora vero. Specificamente per ogni claim di scope: <cited_table>

### [10] source `d564912c…`

> When the working directory changes, for example when Claude executes a cd command. Useful for reactive environment management with tools like direnv FileChanged When a watched file changes on disk. The matcher field specifies which filenames to watch WorktreeCreate When a worktree is being created via --worktree or isolation: "worktree" . Replaces default git behavior WorktreeRemove When a worktree is being removed, either at session exit or when a subagent finishes PreCompact Before context compaction PostCompact

### [11] source `d564912c…`

> WorktreeCreate output WorktreeCreate hooks do not use the standard allow/block decision model. Instead, the hook's success or failure determines the outcome. The hook must return the absolute path to the created worktree directory: Command hooks ( type: "command" ): print the path on stdout. HTTP hooks ( type: "http" ): return { "hookSpecificOutput": { "hookEventName": "WorktreeCreate", "worktreePath": "/absolute/path" } } in the response body. If the hook fails or produces no path, worktree creation fails with an error.

### [12] source `9797c0de…`

> No Additional instructions to append to the preset system prompt exclude_dynamic_sections No Move per-session context such as working directory, the git-repo flag, and auto-memory paths from the system prompt into the first user message. Improves prompt-cache reuse across users and machines. See Modify system prompts SettingSource Controls which filesystem-based configuration sources the SDK loads settings from. Value Description Location "user" Global user settings ~/.claude/settings.json "project" Shared project settings (version controlled) .claude/settings.json "local"

### [13] source `c812a01a…`

> The following example pairs a shared append block with excludeDynamicSections so a fleet of agents running from different directories can reuse the same cached system prompt: TypeScript Python Tradeoffs: the working directory, the git-repo flag, the platform, the active shell, the OS version, and auto-memory paths still reach Claude, but as part of the first user message rather than the system prompt. Instructions in the user message carry marginally less weight than the same text in the system prompt, so Claude may rely on them less strongly when reasoning about the current directory or auto-memory paths. Enable this option when cross-session cache reuse matters more than maximally authoritative environment context. For the equivalent flag in non-interactive CLI mode, see --exclude-dynamic-system-prompt-sections .

### [14] source `cf769fec…`

> LSP Tool capabilities (v2.0.74+): The LSP tool provides IDE-like code intelligence: - Go-to-definition : Jump to where a symbol is defined - Find references : List all usages of a symbol across the codebase - Hover docs : Get type information and documentation for any symbol - Works with TypeScript, Python, Go, Rust, and other languages with LSP support - Requires language server to be available (typically installed with your toolchain) Modification tools (require approval): - Edit - Modify existing files - Write - Create new files - Bash - Execute shell commands - WebFetch - Fetch URL contents - NotebookEdit - Modify Jupyter notebooks
