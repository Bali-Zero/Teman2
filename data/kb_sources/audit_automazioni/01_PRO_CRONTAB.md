# Prompt 1/8: Audit Crontab Pro

**Macchina:** Pro (`nuzantara@Nuzantara`, `~/Desktop/nuzantara`)
**Scope:** 5 entry nel crontab utente
**Durata stimata:** 10-15 minuti
**Rischio:** BASSO (nessun servizio critico nel crontab)

---

## MISSIONE

Verifica, analizza e pulisci le 5 entry del crontab Pro. Per ognuna devi:

1. Verificare che lo script esista e sia eseguibile
2. Controllare i log recenti (se disponibili)
3. Decidere: KEEP / FIX / ELIMINATE
4. Applicare la decisione
5. Verificare il risultato

## CRONTAB ATTUALE

```
0 2 * * *    /tmp/unsplash_retry.sh
*/45 * * * * /Users/nuzantara/openclaw-gemini-refresh.sh
*/5 * * * *  /Users/nuzantara/scripts/fly-health-check.sh
0 3 * * *    /Users/nuzantara/scripts/fly-pg-backup.sh >> ~/backups/fly-postgres/backup.log 2>&1
*/10 * * * * /tmp/cron-stress-monitor.sh >> /tmp/cron-stress-test.log 2>&1
```

## ANALISI RICHIESTA PER OGNI ENTRY

### Entry 1: `/tmp/unsplash_retry.sh` (02:00 daily)

- **Stato noto:** Script MANCANTE in /tmp
- **Verifica:** `ls -la /tmp/unsplash_retry.sh` — esiste? Se no, era un test temporaneo?
- **Decisione probabile:** ELIMINARE (script in /tmp = temporaneo per definizione)

### Entry 2: `openclaw-gemini-refresh.sh` (ogni 45 min)

- **Verifica:** `cat ~/openclaw-gemini-refresh.sh` — cosa fa? È ancora necessario?
- **Log:** Controlla se genera output o errori
- **Domanda chiave:** OpenClaw usa ancora Gemini OAuth che richiede refresh? O è stato sostituito?

### Entry 3: `fly-health-check.sh` (ogni 5 min)

- **Verifica:** `cat ~/scripts/fly-health-check.sh` — cosa monitora esattamente?
- **Log:** Ultimi alert Telegram? Funziona ancora?
- **Domanda chiave:** È ridondante con il `health-check` OpenClaw cron (che è SKIPPED)?
- **Valuta:** 5 minuti è troppo frequente? Troppo poco?

### Entry 4: `fly-pg-backup.sh` (03:00 daily)

- **Verifica:** `cat ~/scripts/fly-pg-backup.sh` — backup funziona?
- **Log:** `tail -20 ~/backups/fly-postgres/backup.log` — ultimo backup riuscito?
- **Domanda chiave:** Quanto spazio occupano i backup? Rotation policy?
- **Nota:** C'è anche un LaunchAgent `com.nuzantara.db-backup` che fa un backup LOCALE (rotto). Overlap?

### Entry 5: `/tmp/cron-stress-monitor.sh` (ogni 10 min)

- **Stato noto:** Questo è il monitor dello stress test creato nella sessione precedente
- **Decisione:** ELIMINARE (era temporaneo per il test)

## AZIONI

Dopo l'analisi:

1. Rimuovi le entry da eliminare:

```bash
# Salva backup del crontab attuale
crontab -l > /tmp/crontab-backup-$(date +%Y%m%d).txt

# Genera nuovo crontab pulito
crontab -l | grep -v "ENTRY_DA_RIMUOVERE" | crontab -
```

2. Per entry da fixare, modifica lo script o il path

3. Verifica il nuovo crontab:

```bash
crontab -l
```

## OUTPUT RICHIESTO

Tabella finale:

| Entry                   | Decisione | Azione | Stato Post |
| ----------------------- | --------- | ------ | ---------- |
| unsplash_retry          | ?         | ?      | ?          |
| openclaw-gemini-refresh | ?         | ?      | ?          |
| fly-health-check        | ?         | ?      | ?          |
| fly-pg-backup           | ?         | ?      | ?          |
| cron-stress-monitor     | ?         | ?      | ?          |

- nuovo `crontab -l` dopo le modifiche.
