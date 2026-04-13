# Automations — Prompt per continuare la sessione

> Copia-incolla come primo messaggio dopo `/clear`

---

## Prompt

Riprendi il lavoro sulle automazioni. Leggi prima:

- `scripts/automation_catalog.json` — catalogo 266 automazioni con tools/APIs/LLMs per entry
- `docs/automations-inventory.xlsx` — Excel 11 sheet (rigenera con `python3 scripts/generate_automations_excel.py`)
- `docs/AUTOMATION_MODEL_MAP.md` — mappa visuale

### Contesto sessione precedente (2026-04-14)

- **179 → 266 automazioni** mappate in 2 sessioni
- **13 categorie**: openclaw_pro (24), openclaw_air (12), launchagents (44), cron_scripts (53), nlm_pipelines (20), backend_services (35), github_actions (8), claude_code_hooks (12), home_scripts (13), air_cron_extras (5), mata_garuda_pipeline (18), intel_scraper_pipeline (7), zombies (5)
- **3 nuove colonne** aggiunte: `tools_called`, `apis_called`, `secrets_used`
- **9 OpenClaw NLM jobs fixati** (payload.kind command→agentTurn): nlm-nb3/4/5/6/7/8/10, nlm-deep-research, cell-weekly-report. Gateway restartato.
- **Excel generator** aggiornato con 11 sheet e supporto per le nuove sezioni

### Cosa resta da fare

#### 1. Verificare che i 9 job fixati funzionino stanotte

```bash
# Controlla domani mattina:
python3 -c "
import json
d = json.load(open('$HOME/.openclaw/cron/jobs.json'))
for j in d.get('jobs', []):
    name = j.get('name', '')
    if 'nlm-nb' in name or 'nlm-deep' in name or 'cell-weekly' in name:
        state = j.get('state', {})
        print(f'{name}: status={state.get(\"lastRunStatus\")} err={state.get(\"lastError\",\"\")[:60]}')
"
```

Se ancora `skipped` → il gateway non ha ricaricato. Fai `launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway`.

#### 2. Automazioni senza enrichment (tools/APIs non ancora mappati)

Le seguenti sezioni hanno entry senza `tools_called`:

- `openclaw_air` (12 job) — non sono stati mappati dall'agente, solo Pro
- `launchagents` (44) — molti non hanno tools/APIs
- `cron_scripts` (53) — molti non hanno tools/APIs
- `nlm_pipelines` (20) — parziali

Per completare: lanciare un agente che legge i LaunchAgent plist + crontab + script header per ogni entry non enriched e aggiunge tools_called/apis_called.

#### 3. Zombie audit

La sezione `zombies` ha solo 5 entry. Cercare:

- LaunchAgent con `loaded=` (vuoto, non caricati) — potenziali zombie
- Cron job commentati ma script ancora esistenti
- Script in `~/scripts/` che nessun LaunchAgent/cron chiama
- OpenClaw job con `lastRunStatus=skipped` permanente

#### 4. Health dashboard

I dati ci sono tutti (266 automazioni con stato, LLM, tools). Manca una vista operativa:

- Quante automazioni sono healthy/failed/skipped/zombie?
- Quali usano LLM e quanto costano? (CLI = $0, API = $X)
- Quali hanno consumer mancanti (produce dati che nessuno legge)?
- Timeline giornaliera: cosa gira quando? (collision detection su orari)

Opzioni:

- **A**: script Python che genera un report Markdown da automation_catalog.json
- **B**: pagina HTML statica con filtri (generata da script)
- **C**: integrazione nel workspace kita.balizero.com

#### 5. Automations-as-code

Oggi le automazioni sono sparse in 4 posti diversi:

- `~/.openclaw/cron/jobs.json` (OpenClaw)
- `~/Library/LaunchAgents/*.plist` (launchd)
- `crontab -l` (cron)
- `.github/workflows/*.yml` (GitHub Actions)

Solo GitHub Actions è in git. Gli altri 3 sono config locale non versionata. Se Pro muore, si perde tutto.

Opzione: script che esporta tutti e 3 in un formato versionabile sotto `infra/automations/` nel repo. Backup + audit trail.

#### 6. Collegamento con l'organismo Mata Garuda

Il catalogo automazioni è il censimento degli organi. Il prompt organismo (`2026-04-14-mata-garuda-organism-prompt.md`) definisce come connetterli. Nella Fase 1 (Sinapsi):

- Il bridge bidirezionale Pro↔Fly sarà una NUOVA automazione da registrare
- I consumer dei nuovi stream saranno NUOVE automazioni
- Ogni nuova automazione DEVE essere registrata nel catalogo (VADEMECUM §1.9)

### Priorità suggerita

1. **Verifica 9 job fixati** (5 min, domani mattina)
2. **Zombie audit** (30 min, pulizia)
3. **Enrichment OpenClaw Air + LaunchAgents** (1h, completamento catalogo)
4. **Health report** (1h, visibilità operativa)
5. **Automations-as-code** (2h, resilienza)
6. **Collegamento organismo** (ongoing, Fase 1 Mata Garuda)

### Vincoli

- Ogni modifica al catalogo → rigenera Excel (`python3 scripts/generate_automations_excel.py`)
- Ogni nuova automazione → entry in `scripts/automation_catalog.json` (VADEMECUM §1.9)
- MAI toccare automazioni in produzione senza verificare che sono ancora in uso
- Il generatore Excel gira ogni notte alle 23:15 via `com.nuzantara.automations-reference`

---

_Scritto il 2026-04-14. Sessione deep scan 2: 179→266 automazioni, 9 job fixati, enrichment tools/APIs._
