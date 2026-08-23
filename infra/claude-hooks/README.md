# claude-hooks (reference copies — audit trail)

⚠️ **Queste sono COPIE REFERENCE, non l'origine eseguibile.**

I PreToolUse hook worktree-isolation vivono in `~/.claude/hooks/` (HOME, non
versionato) e sono invocati dal harness Claude Code prima di ogni `Bash`/`Write`.
Questa dir nel repo esiste solo per **audit trail** + **diff Pro-vs-M5** — mitiga il
rischio HOME-fork drift documentato nelle cicatrici W50/W51/W52 (due macchine
credono di avere world-state diverso, drift silenzioso).

Se modifichi un hook: la fonte di verità resta `~/.claude/hooks/`. Aggiorna QUI la
copia reference dopo ogni modifica (e su entrambe le macchine Pro+M5), per tenere
l'audit trail allineato. Verifica drift con:

```bash
shasum -a 256 ~/.claude/hooks/worktree_isolation.py infra/claude-hooks/worktree_isolation.py
```

## worktree_isolation.py — PreToolUse(Bash)

Blocca git op mutanti (`checkout|switch|stash|reset|merge|rebase|pull`,
`commit -a/-am/--all`, `add -A/-a/--all/.`) quando il target effettivo è il main
checkout. Permette: read-only (`status|log|diff`), `git -C <worktree> ...`,
`commit -m` (no -a), `push`, op fuori dal repo.

## worktree_file_write_check.py — PreToolUse(Edit|Write|MultiEdit)

Blocca scritture file sotto il main checkout ma fuori da ogni worktree registrato
(copre il pattern Write-orphan che la sola enforcement Bash non intercetta).

## Path-aware (2026-06-01)

Entrambi derivano `REPO_ROOT` a runtime (non più hardcoded `/Users/nuzantara/...`),
così girano identici su Pro (`/Users/nuzantara/nuzantara`) e Air-M5
(`/Users/balizero/nuzantara`). Ordine di derivazione in `_derive_repo_root()`:

1. env `NUZ_REPO_ROOT` (override esplicito)
2. parent di `git rev-parse --git-common-dir`, **solo se** il root ha la firma
   `scripts/agent_start.py` (guard contro cwd dentro un altro repo, es. `~/.claude`)
3. fallback `~/nuzantara`

## Kill switch

`AGENT_WORKTREE_ENFORCEMENT=false` (env var) disarma entrambi gli hook.
Su Pro al 2026-06-01 è `false` in `~/.claude/settings.json` (single-operator
interactive). Su M5 è armato (`true`) per il caso multi-agente "8 finestre × N
agenti che committano". Decisione: memory `session_2026_06_01_m5_worktree_hooks_fix.md`.

## mailbox_inject.py — PostToolUse/Stop (context only)

Legge `~/.nuzantara-mailbox/<session_id>/*.md` (diretto) e
`~/.nuzantara-mailbox/broadcast/*.md` (tutte le sessioni), inietta fino a 3
messaggi non consegnati via `hookSpecificOutput.additionalContext`. Su `Stop`
questo fa proseguire il turno — wake-up cross-macchina voluto. Non blocca MAI
un comando: registrato in `guard-conformance/registry.json`
`command_hooks.exempt` (come `dispatch_nudge.py`), non `entries`.

Mittente: `scripts/fleet_mail.sh <host> <session_id|broadcast> "<msg>"` (host
∈ `local|pro|mini`), scrittura atomica (`.tmp-*` poi `mv`), dir sessione
0700; il file diretto consegnato è rinominato `<name>.delivered-<ts>`.

**Kill switch**: `NUZ_MAILBOX_OFF=1`. Root override: `NUZ_MAILBOX_DIR`.

**Sicurezza**: superficie di prompt-injection per costruzione — root 0700
(scrivibile solo via ssh con la chiave dell'operatore), ogni messaggio porta
un trailer che lo etichetta input non fidato di un teammate, mai istruzione
elevata né l'utente che parla.

## Test regressione regex

```bash
python3 infra/claude-hooks/test_block_regex.py
```

Valida i 20 casi block/allow del `BLOCKED_SUBCMD_RE` (incl. il guard contro falsi
positivi tipo `git commit -m "add a feature"`). Eseguilo dopo ogni modifica alla regex.
