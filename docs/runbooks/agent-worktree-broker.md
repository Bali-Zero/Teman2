# Runbook — Agent Worktree Broker

> SOTA L1 2026-05-24. Reference: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

## Cosa fa

`scripts/agent_start.py` crea un git worktree isolato per ogni sessione agent (subagent, cron-spawned `claude`, parallel Claude Code window). Risolve la cicatrix 2026-04-29 (incident #1+#2: `git stash` / `git checkout` da sibling che distrugge WIP altrui) e i 17 stash orphan accumulati 2026-05-23.

Invariante (4/4 panel SOTA): due sessioni non condividono mai lo stesso working tree.

## Come usarlo

### Creare un worktree per una nuova task

```bash
python scripts/agent_start.py --lane wr2 --task-id render-cleanup --ttl-min 60
# stdout: WORKTREE_READY /Users/nuzantara/Desktop/nuzantara/.worktrees/wr2-render-cleanup
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/wr2-render-cleanup
# spawn claude qui (NON nel main checkout)
```

Effetti:

- Branch nuovo `agent/<hostname>/<lane>/<task-id>` (es. `agent/nuzantara/wr2/render-cleanup`) creato da `--base-branch` (default `main`).
- Worktree montato sotto `.worktrees/<lane>-<task-id>/`.
- Symlink env-safe: `apps/backend-rag/.venv`, `apps/backend-rag/.env`, `node_modules/` puntano al main checkout (read-only intent — non modificarli).
- `.agent-task.json` con metadata (task_id / lane / branch / host / created_at / ttl_minutes / pid / base_branch / worktree_path).
- Log su `~/logs/agent-broker.log` (rotation 1MB x 5).

### Vedere worktree attivi

```bash
python scripts/agent_start.py --list
# TASK              LANE   HOST       AGE_MIN  TTL  WIP  BRANCH
# render-cleanup    wr2    nuzantara     12.3   60  yes  agent/nuzantara/wr2/render-cleanup
```

WIP=yes significa file uncommitted (tracked o untracked) presenti.

### Cleanup worktree TTL-expired

```bash
python scripts/agent_start.py --cleanup
# skip <id> (recent activity <10min) — live session, will reap when idle
# WARN: skip <id> (WIP). Commit or stash inside <path>, then re-run --cleanup.
# removed expired worktree <id> (<path>)
```

Due guard proteggono un worktree expired dal drop:

- **WIP-safe** — worktree con modifiche non committate → skip con WARN, exit 1 (operator deve committare/stashare). Forza con `--force`.
- **skip-recent** (W62) — worktree con attività filesystem negli ultimi 10min = sessione viva → skip silenzioso, exit 0 (al prossimo tick, quando idle, verrà preso). Soglia configurabile con `--skip-recent-min N` (0 disabilita). `--force` bypassa anche questo.

### Auto-cleanup (cron) — W62 ANTIBODY #1

`--cleanup` NON è più solo manuale. Il LaunchAgent `com.nuzantara.agent-worktree-cleanup.daily` lo invoca ogni giorno alle 08:15 WITA via `scripts/agent_worktree_cleanup_cron.sh`.

```bash
# install (Pro):
bash infra/launchagents/install_agent_worktree_cleanup.sh
# verify:
launchctl print gui/$(id -u)/com.nuzantara.agent-worktree-cleanup.daily | grep -E 'state|runs'
# log:
tail -f ~/logs/agent-worktree-cleanup.log
# uninstall:
bash infra/launchagents/install_agent_worktree_cleanup.sh --uninstall
```

GOTCHA: il cron usa SEMPRE il main checkout (`~/Desktop/nuzantara/scripts/agent_start.py`). Il broker risolve `WORKTREES_DIR` da `parents[1]` dello script — invocarlo da un worktree scansiona `.worktrees/<wt>/.worktrees/` (inesistente) → no-op silenzioso.

### Orphan detection — W62 ANTIBODY #2

`--list` flagga `ORPHAN` ogni worktree più vecchio di 2× il suo TTL e stampa un sommario WARN finale:

```bash
python scripts/agent_start.py --list
# ... ORPHAN ...
# WARN: 2 orphan worktree(s) detected (age > 2× TTL) — review then run --cleanup or --release.
```

Un orphan non viene rimosso da `--list` (read-only): è un segnale. Usa `--cleanup` (se idle+clean) o `--release <id>`.

### CI hygiene gate — W62 ANTIBODY #3

`tests/integration/test_no_stale_worktrees.py` fallisce in CI (workflow `broker-hygiene.yml`) se il checkout contiene un worktree più vecchio di 24h (cap assoluto, indipendente dal TTL per-task). Lo stesso workflow gira anche `scripts/tests/test_agent_start.py` (prima orfano da CI). Se rompe una PR: `--list` per ispezionare, poi `--cleanup`/`--release`.

### Tear down esplicito a fine task

```bash
python scripts/agent_start.py --release render-cleanup
# released render-cleanup (branch agent/nuzantara/wr2/render-cleanup deleted)
```

Il branch viene cancellato SOLO se merged in `base_branch`. Forza con `--force` (es. branch abbandonato senza merge).

### Kill switch (lesson W33)

```bash
export AGENT_BROKER_ENABLED=false
python scripts/agent_start.py --lane wr2 --task-id ...
# ERROR: broker disabled (AGENT_BROKER_ENABLED=false)...
```

Disabilita create/cleanup/release. `--list` resta abilitato per osservabilità.

## Lane riconosciute

`wr2`, `wr3`, `infra`, `docs`, `db`, `cicatrix-fix`, `mouth` (Subhi reserved), `intel`, `cell`, `organism`, `mata-garuda`, `backend-rag`, `frontend`, `ops`. Lane nuove → aggiungere a `KNOWN_LANES` in `scripts/agent_start.py` o usare `--allow-unknown-lane` una tantum.

## Troubleshooting top 5

### 1. `ERROR: branch '...' already exists`

Un task-id precedente ha lasciato il branch in giro (worktree rimosso ma branch no).

```bash
git branch -D agent/<host>/<lane>/<task-id>
# poi ri-eseguire il create
```

### 2. `ERROR: worktree already exists at .worktrees/<lane>-<id>`

Già attivo. Verifica con `--list`; se l'altra sessione non sta più lavorando, usa `--release <task-id>`.

### 3. Cleanup non rimuove un worktree expired

`--cleanup` skippa worktree con WIP per evitare la cicatrix 2026-04-29 #2. Soluzioni:

- entrare nel worktree, `git add -A && git commit -m "WIP" && git push`, poi `--release <id>`
- oppure (operator escape) `python scripts/agent_start.py --cleanup --force`

### 4. `release` rifiuta "branch not merged"

Comportamento corretto: protegge dal perdere lavoro non-merged. Soluzioni:

- aprire PR, mergiare, poi `--release <id>`
- oppure `--release <id> --force` se il branch è davvero abbandonato

### 5. Symlink mancanti dentro il worktree

Il broker crea symlink solo se il target esiste in main. Se `apps/backend-rag/.venv` non è creato, il symlink viene skippato. Crea il venv nel main checkout una volta, poi ricrea il worktree.

## Per Claude (agent) — quick start

OGNI sessione agent dispatch (subagent dispatch, cron-spawned `claude`, parallel Claude Code window) DEVE:

1. `python scripts/agent_start.py --lane <X> --task-id <Y>`
2. `cd` nel path stampato da `WORKTREE_READY`
3. Lavorare lì. Mai `git stash` / `git checkout` nel main checkout.
4. Quando finito: commit + push + `--release <task-id>` (oppure lascia che `--cleanup` lo prenda al prossimo cron tick).

## Broker-aware spawn convention (W62 ANTIBODY #4)

Il TTL da solo non basta: nessun consumer lo applicava. La hygiene è ora a 3 livelli, in ordine di affidabilità decrescente:

1. **Release esplicito (preferito)** — l'orchestratore/agent chiama `--release <task-id>` a fine task. Tear-down immediato, branch cancellato se merged. È l'unico path che pulisce _subito_.
2. **Cron reaper (rete di sicurezza)** — `com.nuzantara.agent-worktree-cleanup.daily` reape i worktree idle+clean+expired senza intervento. Copre il caso "l'agent è morto senza release". Non tocca WIP né sessioni vive (skip-recent).
3. **CI gate (backstop finale)** — `broker-hygiene.yml` impedisce che un orphan >24h si fossilizzi: la PR fallisce finché il `.worktrees/` non è pulito.

Regole per chi dispatcha worktree (orchestratore o script):

- Un worktree è **effimero**: o lo rilasci tu, o lo reapa il cron. Mai trattarlo come storage persistente.
- Se hai WIP da preservare oltre la sessione: **committa su un branch dedicato e pusha** PRIMA di lasciare il worktree. Né il cron né `--cleanup` rimuovono WIP, ma un worktree con WIP eterno è debito che blocca il CI gate.
- I subagent spawnati via Agent tool girano sotto `.claude/worktrees/agent-<id>/` (path diverso, auto-pulito dall'harness). Questo broker governa SOLO il path user-facing `.worktrees/` usato da spawn manuali o scriptati.
- Convenzione TTL: usa `--ttl-min` realistico per la durata attesa. Il cron reaper rispetta il TTL per-task; il CI gate impone comunque il cap assoluto di 24h.

Il main checkout `~/Desktop/nuzantara` è riservato all'operator interactive + cicatrix hotfix.
