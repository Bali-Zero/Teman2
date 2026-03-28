# Prompt 4/8: Audit OpenClaw Cron Jobs

**Macchina:** Pro (`nuzantara@Nuzantara`)
**Scope:** 16 job in `~/.openclaw/cron/jobs.json`
**Durata stimata:** 30-40 minuti (il più lungo — molti job da analizzare)
**Rischio:** MEDIO (modifiche a jobs.json, non a servizi)

---

## MISSIONE

Analizza tutti i 16 job OpenClaw. Per ognuno:

1. Verifica stato attuale (lastRunStatus, consecutiveErrors)
2. Analizza il payload — è ben scritto? Usa i tool giusti?
3. Verifica che gli script/tool referenziati esistano
4. Identifica overlap con altri sistemi (LaunchAgents Pro, cron Air)
5. Decidi: KEEP / FIX / DISABLE / ELIMINATE / POTENZIARE

## FILE DA LEGGERE

```bash
cat ~/.openclaw/cron/jobs.json
```

## STATO NOTO DEI JOB

### Funzionanti (7) — Verifica rapida

| Job                      | ID                          | Ultima Durata  | Note      |
| ------------------------ | --------------------------- | -------------- | --------- |
| compliance-autopilot     | c2b3a4d5-...                | 1230s (~20min) | OK        |
| practice-lifecycle-check | d3c4b5a6-...                | 365s (~6min)   | OK        |
| client-health-monitor    | f5e6d7c8-...                | 128s (~2min)   | OK        |
| articles-indexing-daily  | articles-indexing-daily-002 | 360s (~6min)   | Auto-stop |
| kbli-indexing-daily      | kbli-indexing-daily-001     | 3328s (~55min) | Auto-stop |
| weekly-report            | e4d5c6b7-...                | 912s (~15min)  | OK        |
| seo-guardian-weekly      | seo-guardian-weekly-001     | 1583s (~26min) | OK        |

**Per ognuno:** Leggi il payload, verifica che sia completo e corretto. Eventuali miglioramenti? Troppo frequente/raro?

### In Timeout (5) — Analisi dettagliata

| Job                  | ID                       | Durata Prima del Timeout | Timeout Gateway |
| -------------------- | ------------------------ | ------------------------ | --------------- |
| daily-ops-autopilot  | b1a2c3d4-...             | 3640s (60.7min)          | ~3660s          |
| nightly-code-quality | 6d39ad6b-...             | 3661s                    | ~3660s          |
| nightly-autofix-loop | autofix-loop-nightly-008 | 3661s                    | ~3660s          |
| seo-guardian-observe | seo-guardian-observe-001 | 3659s                    | ~3660s          |
| seo-guardian-measure | seo-guardian-measure-001 | 3631s                    | ~3660s          |

**Per ognuno:**

1. **Leggi il payload completo** — è troppo ambizioso per un singolo run?
2. **Verifica che i tool/script referenziati esistano:**
   - `mcporter call nuzantara-mcp.chain_daily_ops_autopilot` → funziona?
   - `mcporter call nuzantara-mcp-advanced.run_linting` → funziona?
   - `apps/evaluator/seo_guardian_agent.py` → esiste?
   - `apps/evaluator/seo_guardian_measure.py` → esiste?
3. **Identifica il collo di bottiglia:**
   - Il pre-warm Fly.io (35s) è una parte significativa?
   - Il test suite è troppo grande?
   - Il tool MCP è lento o fallisce silenziosamente?
4. **Proponi soluzione:**
   - Spezzare in 2-3 job più piccoli?
   - Ridurre scope (es. `scope=core` invece di `scope=full`)?
   - Eliminare step ridondanti?
   - Il job è duplicato da un LaunchAgent?

### Rotti/Disabilitati (4)

| Job                | ID           | Problema                                                                  |
| ------------------ | ------------ | ------------------------------------------------------------------------- |
| health-check       | a8985721-... | `payload.kind="agentTurn"` ma sessionTarget="main" richiede "systemEvent" |
| deploy-abort-timer | da9aea36-... | DISABLED, one-shot scaduto                                                |
| weekly-dep-audit   | h7g8f9e0-... | `enabled: true` ma nessun log di esecuzione                               |

**Per health-check:**

- FIX: cambiare `payload.kind` da "agentTurn" a "systemEvent"
- OPPURE: cambiare `sessionTarget` da "main" a "isolated"
- Verifica quale approach è corretto per questo tipo di job

**Per deploy-abort-timer:**

- ELIMINATE: è un one-shot scaduto, `deleteAfterRun: true` ma non cancellato
- Rimuovi dall'array jobs

**Per weekly-dep-audit:**

- DIAGNOSI: perché non ha mai eseguito? Il cron expr `30 3 * * 1` (lunedì 03:30) è corretto?
- Controlla `state.nextRunAtMs` — è nel futuro? O è passato senza eseguire?
- Se il job è valido → FIX. Se è ridondante con nightly-code-quality → ELIMINATE.

## OVERLAP DA VERIFICARE

| OpenClaw Job                 | Possibile Overlap                |
| ---------------------------- | -------------------------------- |
| daily-ops-autopilot          | LaunchAgent intel.nightly?       |
| nightly-code-quality         | Air cron auto_sentinel.sh?       |
| nightly-autofix-loop         | Air cron auto_test_force.sh?     |
| seo-guardian-observe/measure | Nessun overlap noto              |
| weekly-report                | Air cron daily-monitoring.sh?    |
| health-check                 | Pro crontab fly-health-check.sh? |

## AZIONI

Per modificare jobs.json, usa questo pattern:

```bash
# Backup PRIMA
cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.bak-$(date +%Y%m%d)

# Modifica con jq o editor
# Poi reload del gateway:
curl -X POST http://localhost:18789/reload 2>/dev/null || echo "Reload endpoint potrebbe non esistere"
```

## OUTPUT RICHIESTO

### Tabella Completa

| Job                  | Stato Attuale | Decisione | Azione Specifica | Overlap |
| -------------------- | ------------- | --------- | ---------------- | ------- |
| compliance-autopilot | OK 20min      | KEEP      | —                | —       |
| practice-lifecycle   | OK 6min       | KEEP      | —                | —       |
| ...                  |               |           |                  |         |

### Per i 5 job in timeout, rispondi a:

1. Quanto tempo serve realmente (stima dal payload)?
2. Quale step è il collo di bottiglia?
3. Si può spezzare? Come?
4. C'è overlap con automazioni su Pro/Air?

### Per i job rotti, fornisci:

1. Fix esatto (modifica JSON o eliminazione)
2. Verifica post-fix
