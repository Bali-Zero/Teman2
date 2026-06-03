---
date: 2026-06-01
domain: operations
client_case: false
sources:
  - https://iterm2.com/shell_integration.html
  - https://iterm2.com/documentation-triggers.html
  - https://iterm2.com/documentation-coprocesses.html
  - https://iterm2.com/documentation-automatic-profile-switching.html
  - https://iterm2.com/features.html
  - https://iterm2.com/python-api/examples/autoalert.html
  - https://iterm2.com/appcasts/full_changes.txt
  - https://medium.com/@apier/iterm2-version-3-6-7f71330b796a
---

# iTerm2 3.6 — Power features per heavy CLI + Claude Code + ssh user

Macchina: Air-M5 (`balizero`), iTerm2 **3.6.10**. Audit config 2026-06-01.

## TL;DR — la tua config attuale ha 2 problemi seri + 1 confusione di profili

1. **Due profili in conflitto.** Esiste un Dynamic Profile `Claude Anthracite` (Menlo 11, scrollback 50000, font coerente) MA il profilo **attivo** è `M5` (nel plist) con: JetBrains 16 + Non-ASCII Monaco 12 (mismatch), **Scrollback Lines = 0**, **Terminal Type = vt100**. Stai usando il profilo sbagliato/regredito.
2. **Scrollback = 0** → perdi lo storico (e con Claude Code che produce output lungo è grave).
3. **Terminal Type = vt100** → `$TERM` sbagliato, colori limitati, rompe tmux/htop/ssh capabilities. Deve essere `xterm-256color`.

---

## A. Le 3 superpotenze che cambiano la vita (priorità MASSIMA)

### 1. Shell Integration — già installata ✅, ma sblocca features nascoste
Hai `~/.iterm2_shell_integration.zsh` in `.zshrc`. Questo abilita, **se le usi**:

- **Marks** — ogni prompt diventa un "mark". Naviga tra comandi con **`Cmd-Shift-↑ / ↓`** (salti da un comando all'altro, non riga per riga). Per un terminale con output lungo (Claude Code, pytest, deploy log) è oro.
- **Command status** — il mark a sinistra del prompt diventa **rosso se il comando è fallito**. Right-click → vedi return code, working dir, durata.
- **Alert on next mark** — dopo aver lanciato un comando lungo (deploy, `fly deploy`, pytest suite): **`Cmd-Opt-A`** → iTerm ti manda una **notifica modale quando il comando finisce**. Smetti di fissare il terminale.
- **`it2attention`** (utility) — uno script può far rimbalzare l'icona nel Dock. Combinabile con i tuoi cron/agent.

### 2. Hotkey Window (Quake-style dropdown) — NON configurata ❌
Terminale globale che scende dall'alto con UN tasto, da qualsiasi app.
- **Settings → Keys → Hotkey → "Create a Dedicated Hotkey Window"**, assegna es. **`⌥Space`** o **`F12`**.
- Per un workflow dove apri e chiudi terminale di continuo (sei sempre tra browser/Claude/ssh) è la singola feature più ergonomica. Apri → comando → chiudi, senza Cmd-Tab.

### 3. tmux `-CC` Native Integration — tmux NON installato ❌
Diverso da tmux normale: `tmux -CC` fa sì che le **finestre tmux diventino finestre/tab NATIVE di iTerm2** (con mouse, scrollback nativo, copy-paste Mac). Sessioni che **sopravvivono alla disconnessione ssh**.
- Install: `brew install tmux`
- Uso locale: `tmux -CC`
- Uso remoto (il vero superpotere per te): `ssh pro -t 'tmux -CC new -A -s main'` → la sessione sul Pro/Mini diventa finestre native sul Mac; se cade la rete (cf. i tuoi problemi M5↔Pro), riconnetti e ritrovi tutto. **Perfetto per la regola Symbiosis "disconnessione non è guasto".**

---

## B. Automazione & navigazione (priorità ALTA)

### 4. Triggers — azioni automatiche su regex nell'output
`Settings → Profiles → Advanced → Triggers → Edit`. Quando l'output matcha una regex, esegue un'azione. Idee per te:
- Highlight in rosso di `ERROR|FAIL|Traceback|429|quota exceeded` (i tuoi pattern di cascade-exhaust!).
- **Set Named Mark** su `Step \d+` o su prompt di deploy → navighi i passaggi.
- **Run Silent Coprocess** su un pattern → triggera uno script (es. alert Telegram quando un cron logga un errore noto).
- Capture `out of extra usage` → highlight giallo: vedi a colpo d'occhio quando un LLM tier è esaurito.

### 5. Captured Output — raccoglie i match in un pannello
Toolbelt che colleziona righe matchanti regex (es. tutti gli errori di un build). `View → Toolbelt → Captured Output`. Click su una riga → salti a quel punto del terminale. Per debug di log lunghi.

### 6. Semantic History — Cmd-click apre file/URL/`file:riga`
`Cmd-click` su un path nell'output apre il file nell'editor; su `path:42` apre **alla riga 42**. Su un URL apre il browser.
- `Settings → Profiles → Advanced → Semantic History` → scegli "Open with editor…" e punta a VS Code / il tuo editor. Click su un traceback Python → editor alla riga giusta.

### 7. Composer (`Cmd-Shift-.`) — editor multi-riga prima di eseguire
Pop-up per comporre comandi lunghi/multi-riga con syntax highlight, poi `Shift-Invio` per inviarli. In 3.6 è migliorato (drag verticale, gestione echo). Utile per heredoc, comandi git complessi, snippet al volo.

---

## C. Comodità quotidiane (priorità MEDIA)

### 8. Snippets — libreria di comandi riusabili
`Settings → General → Snippets` (o pannello toolbelt). Salvi stringhe ricorrenti (es. `ssh pro -t 'tmux -CC new -A -s main'`, `cd ~/Desktop/nuzantara && source .venv/bin/activate`, i tuoi comandi `mem`/`nlm`). Richiamabili con tag e filtrabili per profilo.

### 9. Automatic Profile Switching (APS) — profilo cambia per host/user/path
`Settings → Profiles → Advanced → Automatic Profile Switching`. Regole tipo: quando sei su `ssh pro` → profilo con **sfondo rosso** (= "attenzione, macchina di produzione"). Riduce gli errori "credevo di essere in locale". **Richiede shell integration anche sul Pro/Mini** (verifica con `ssh pro 'ls ~/.iterm2_shell_integration.zsh'`).

### 10. Badges — watermark di contesto sulla sessione
Testo grande semi-trasparente in alto a destra (es. nome host, branch git, `\(session.hostname)`). `Settings → Profiles → General → Badge`. Su ssh ti dice sempre dove sei.

### 11. Status Bar — componenti live in basso
`Settings → Profiles → Session → Configure Status Bar`. Componenti: CPU/mem, git branch, cwd, hostname, current job, batteria, clock. Trascini i moduli. Per ssh + multi-macchina è un cruscotto permanente.

### 12. Timestamps — `Cmd-Shift-E`
Mostra l'ora a fine di ogni riga di output. Utile per capire quanto ci mette ogni step di un deploy/cron.

### 13. Instant Replay — `Cmd-Opt-B`
"Riavvolgi" il contenuto del terminale nel tempo, come un DVR. Recuperi output scrollato via anche dopo clear.

### 14. Password Manager — `Cmd-Opt-F` (o via menu)
Vault integrato (backed da Keychain) per inserire password senza digitarle. NB: per i tuoi secret usi già Keychain + secrets.env — questo è per password interattive (sudo remoti, prompt).

---

## D. Performance & rendering (priorità MEDIA)

### 15. Metal (GPU) Renderer
`Settings → Profiles → Session → "Use built-in Powerline glyphs"` e soprattutto `Settings → General → Magic → GPU Rendering` / `Advanced → "GPU"`. Su Apple Silicon (M5) il renderer Metal rende scroll e output fluidissimi. Verifica: `Settings → Advanced → cerca "Metal"` → "Use Metal renderer when connected to power" + "...on battery". Per M5 (laptop) abilita entrambi se la batteria regge.

### 16. Minimum Contrast & Dimming
- **Minimum Contrast** (`Profiles → Colors`): forza leggibilità anche con color scheme di programmi che scrivono testo scuro su scuro (alcuni TUI). Hai `Minimum Contrast (Light) = 0` → considera 0.1–0.2.
- **Dim inactive split panes** (`Appearance`): hai `SplitPaneDimmingAmount` presente → split inattivi si oscurano, focus visivo migliore.

---

## E. 3.6-specific (novità da conoscere)

### 17. AI Chat — ora è un PLUGIN separato
In 3.6 le feature AI sono state spostate in un **plugin installabile a parte** (verbiage OpenAI rimosso, ora provider-agnostic). **Non serve API key per modelli self-hosted** → puoi puntarlo a **Ollama locale** (es. `llama3`, o i tuoi `qwen3.5`/`deepseek-r1`). Rispetta la tua HARD RULE "zero paid API" e la sovranità locale.
- Install: `Settings → General → Magic → AI` → "Install Plugin". Endpoint: il tuo Ollama locale.
- ⚠️ Per te è **ridondante** con Claude Code/`claude` CLI — utility marginale, ma se lo configuri usa SOLO Ollama locale (mai endpoint paid).
- Esiste anche un **Browser plugin** (3.6) per pagine dentro iTerm — sperimentale, skip.

### 18. Liquid glass UI (3.6.3+) su Open Quickly e AI Chat — solo estetica.

---

## F. Python API + daemon scripts (priorità BASSA per ora, potenziale ALTO)

iTerm2 espone una **Python API** con runtime auto-installabile (`Settings → General → Magic → Python API`). Script in `~/Library/Application Support/iTerm2/Scripts/` (oggi vuota) possono **auto-lanciarsi all'avvio** (cartella `AutoLaunch/`). Casi d'uso per te:
- Auto-alert su job lunghi (esempio ufficiale `autoalert.py`).
- Auto-APS custom, badge dinamici con git branch, integrazione coi tuoi cron/agent.
- Daemon che apre layout di tab predefinito (Pro ssh + locale + log tail) all'avvio.

Vale la pena solo se vuoi automazione iTerm-side; per ora il ROI è sotto a triggers+snippets.

---

## PRIORITÀ DI ADOZIONE (per il tuo profilo d'uso)

| # | Feature | Effort | ROI | Quando |
|---|---|---|---|---|
| 1 | Fix profilo: TERM xterm-256color + scrollback + font non-ASCII | 2 min | 🔴🔴🔴 | SUBITO |
| 2 | Marks navigation (Cmd-Shift-↑↓) + Alert on mark (Cmd-Opt-A) | 0 (già attivo) | 🔴🔴🔴 | impara ora |
| 3 | Hotkey window | 2 min | 🔴🔴🔴 | subito |
| 4 | tmux -CC su ssh pro/mini | 5 min | 🔴🔴 | subito (risolve disconnect M5↔Pro) |
| 5 | Triggers (ERROR/quota highlight + named marks) | 10 min | 🔴🔴 | settimana |
| 6 | Semantic History → editor | 2 min | 🔴🔴 | subito |
| 7 | Snippets (comandi ssh/venv ricorrenti) | 5 min | 🔴 | quando capita |
| 8 | APS sfondo rosso su Pro | 5 min | 🔴 | settimana |
| 9 | Status bar + badge | 5 min | 🟡 | opzionale |
| 10 | AI plugin → Ollama | 10 min | 🟡 | ridondante con Claude |
| 11 | Python API daemon | 30 min+ | 🟡 | solo se vuoi automazione |

## Fonti
- [Shell Integration](https://iterm2.com/shell_integration.html)
- [Triggers](https://iterm2.com/documentation-triggers.html)
- [Coprocesses](https://iterm2.com/documentation-coprocesses.html)
- [Automatic Profile Switching](https://iterm2.com/documentation-automatic-profile-switching.html)
- [Features](https://iterm2.com/features.html)
- [Alert on Long-Running Jobs (Python API)](https://iterm2.com/python-api/examples/autoalert.html)
- [Changelog full](https://iterm2.com/appcasts/full_changes.txt)
- [3.6 AI plugin account](https://medium.com/@apier/iterm2-version-3-6-7f71330b796a)
