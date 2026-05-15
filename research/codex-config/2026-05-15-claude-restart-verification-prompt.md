---
date: 2026-05-15
purpose: Prompt da incollare in nuova sessione Claude Code per verificare gli upgrade di config applicati oggi
target: claude 2.1.142, cwd /Users/nuzantara/Desktop/nuzantara
invocation: apri nuovo iTerm tab, `cd ~/Desktop/nuzantara && claude`, poi incolla questo prompt
---

# Prompt da incollare nella nuova sessione

Ciao. Sono Antonello. Nella sessione precedente di oggi (2026-05-15) abbiamo applicato 11+ fix di config Claude+Codex+Nuzantara per portare lo stack a SOTA. Ora apro questa nuova sessione per **verificare end-to-end** che tutto funzioni come previsto. Voglio che tu esegua un audit di verifica in 7 step, riportando per ogni step PASS/FAIL/PARTIAL con evidenza diretta.

## Contesto cosa è cambiato oggi (riferimenti — leggi se serve)

- Memoria pregressa: `~/.claude/scripts/mem recent 30` (importanza ≥7) ti mostra le decisioni di oggi
- Memoria specifica: `~/.claude/scripts/mem query "2026-05-15"` per il deep-dive
- Backup creati oggi (se serve rollback):
  - `~/.claude/settings.json.bak-2026-05-15-pre-sota`
  - `~/.codex/config.toml.pre-sota-2026-05-15`
  - `~/.codex/hooks.json.pre-C4-2026-05-15`
  - `~/Library/LaunchAgents/com.claude-max-api.plist.bak-2026-05-15-pre-anthropic-removal`
  - `~/.claude/memory.db.bak-2026-05-15-pre-retag`
  - `~/Desktop/nuzantara/.mcp.json.bak-2026-05-15-pre-secrets-extraction`

## I 7 step di verifica

### Step 1 — SessionStart hook (Backend venv split)

Atteso: il SessionStart hook stampa "System Python" + "Backend venv" come righe separate, non più "Venv" unico.

Verifica: guarda il banner di apertura di questa sessione (quello che ti ho già mostrato sopra prima del prompt). Cerca:
- `System Python: Python 3.x.x`
- `Backend venv: Python 3.x.x` oppure `Backend venv: MISSING (...)`

Se vedi solo `Venv: Python 3.x.x` → **FAIL** (hook non aggiornato).
Se vedi entrambe → **PASS**.

### Step 2 — MOS memory namespace symlink

Atteso: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory` è un symlink a `../-Users-nuzantara/memory`, e contiene 315+ file .md visibili.

Verifica:
```bash
ls -la ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory | head -3
ls ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/ | wc -l
```

Atteso: symlink visibile (`->` arrow), conteggio file ≥315.

### Step 3 — Sessions MOS retag

Atteso: 196+ sessioni di oggi sono taggate al project canonical `/Users/nuzantara/Desktop/nuzantara` (non più sub-paths).

Verifica:
```bash
~/.claude/scripts/mos-db "SELECT COUNT(*) FROM sessions WHERE project='/Users/nuzantara/Desktop/nuzantara' AND date(started_at) = date('now');"
```

Atteso: ≥196 (il numero esatto cresce con le nuove sessioni di oggi).

### Step 4 — Claude settings.json — excludeDynamicSystemPromptSections

Atteso: setting JSON presente.

Verifica:
```bash
python3 -c "import json; d=json.load(open('/Users/nuzantara/.claude/settings.json')); print('excludeDynamicSystemPromptSections:', d.get('excludeDynamicSystemPromptSections'))"
```

Atteso: `True`. Nota: questo flag potrebbe NON essere letto dal binary 2.1.142 (era ipotesi non documentata Anthropic). Se non lo legge, è inerte ma non rompe. Conferma solo che il setting è valid.

### Step 5 — Codex MCP nuzantara-mcp + nuzantara-mcp-advanced

Atteso: i 2 server Nuzantara appaiono nel `codex mcp list` (9 server totali invece di 8).

Verifica:
```bash
codex mcp list | grep nuzantara
```

Atteso: 2 righe (`nuzantara-mcp` + `nuzantara-mcp-advanced`), entrambe `enabled`.

### Step 6 — .mcp.json secret extraction (Claude side)

Atteso: `.mcp.json` ha `${NUZANTARA_API_KEY}` + `${LANGSMITH_API_KEY}` come ref (no inline), permissions 0400, e shell corrente ha le var dal source `.zshrc` line 146.

Verifica:
```bash
stat -f "%Sp" ~/Desktop/nuzantara/.mcp.json
python3 -c "import json; e=json.load(open('/Users/nuzantara/Desktop/nuzantara/.mcp.json'))['mcpServers']['nuzantara-mcp']['env']; print('NUZANTARA_API_KEY:', e['NUZANTARA_API_KEY']); print('LANGSMITH_API_KEY:', e['LANGSMITH_API_KEY'])"
echo "NUZANTARA_API_KEY: ${NUZANTARA_API_KEY:0:8}... (${#NUZANTARA_API_KEY} chars)"
echo "LANGSMITH_API_KEY: ${LANGSMITH_API_KEY:0:8}... (${#LANGSMITH_API_KEY} chars)"
```

Atteso:
- permissions: `-r--------`
- .mcp.json values: `${NUZANTARA_API_KEY}` e `${LANGSMITH_API_KEY}` (no chars stringhe lunghe)
- shell env: NUZANTARA 19 chars (`zantara-secret-2024`), LANGSMITH 51 chars (`lsv2_pt_...`)

**Se shell mostra 0 chars** → il `.zshrc` line 146 non è stato eseguito per questa shell. Soluzione: `source ~/.nuzantara-secrets.env` manuale oppure chiudere e riaprire.

### Step 7 — Codex config dead-flags cleanup

Atteso: `image_detail_original` e `js_repl` NON più nel `[features]` block.

Verifica:
```bash
python3 -c "import tomllib; f=tomllib.load(open('/Users/nuzantara/.codex/config.toml','rb'))['features']; print('features:', sorted(f.keys())); print('image_detail_original present:', 'image_detail_original' in f); print('js_repl present:', 'js_repl' in f)"
```

Atteso: `image_detail_original present: False`, `js_repl present: False`.

## Bonus check — Telegram chat coherence

```bash
grep TELEGRAM_CHAT_ID /Users/nuzantara/.claude/settings.json /Users/nuzantara/.codex/config.toml
```

Atteso: entrambi `1125336968` (Zero owner).

## Output atteso da te

Una tabella compatta tipo:

| Step | Verdetto | Evidenza |
|---|---|---|
| 1 SessionStart hook | PASS/FAIL/PARTIAL | (1 riga riassunto evidenza) |
| 2 Memory symlink | … | … |
| ... | … | … |

Poi una sezione `## Cose che NON tornano` con eventuali surprise.

Poi una sezione `## Raccomandazioni follow-up` con max 3 azioni se serve.

## Vincoli output

- Italiano colloquiale come al solito
- Max 600 parole totali
- Niente preamboli, niente closing fluff
- Cita gli output verbatim (rispetto anti-hallucination rule)
- Se un test fallisce, NON tentare di fixarlo subito — riporta solo, decideremo insieme

Inizia.
