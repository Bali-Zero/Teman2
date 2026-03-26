# CRON SCHEDULE — Attivita Giornaliere h24

**Timezone:** WITA (UTC+8) — Bali, Indonesia
**Engine:** OpenClaw cron tool (agentTurn o systemEvent)
**Formato:** `minuto ora giorno mese giorno_settimana`

---

## MAPPA VISUALE GIORNALIERA

```
WITA  00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
      |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
Zan   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ (always-on)
Flash ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ (on-demand)
Grav  *       *       *       *       *       *       *       *       *       *       *       *    (ogni 2h)
Grav  .....................................locks..................................................  (ogni 5min)
Sent  |               |               B       |       C       |               |       C       |    (briefing + competitor)
Vox   |               |               |       S               S               |       S       |    (social 3x)
Kodex |               |               |       |       |       T       |       |       |       |    (tech debt 12:00)

Legenda: * = health check deep, B = briefing, C = competitor watch, S = social pulse, T = tech debt
         . = lock cleanup (ogni 5 min), ~ = always on
```

---

## TABELLA CRON COMPLETA

### GRAVITY (Orchestrator) — Il piu attivo, mantiene il sistema

| #   | Nome                      | Cron WITA     | Cron UTC                | Durata  | Modello           | RAM   | Output                           |
| --- | ------------------------- | ------------- | ----------------------- | ------- | ----------------- | ----- | -------------------------------- |
| G1  | **Health Check Deep**     | `0 */2 * * *` | `0 */2 * * *` (Fly=UTC) | ~2 min  | Gemini 3 Pro      | ~1 GB | Log + Telegram alert se critico  |
| G2  | **Lock Cleanup**          | `*/5 * * * *` | `*/5 * * * *`           | ~5 sec  | Nessuno (SQL)     | ~0    | Locks scaduti rimossi            |
| G3  | **Disk Check**            | `0 6 * * *`   | `22 * * * *` (prev day) | ~30 sec | Nessuno (shell)   | ~0    | Alert se >85%                    |
| G4  | **DB Vacuum**             | `0 4 * * 0`   | `20 * * * 6`            | ~5 min  | Nessuno (SQL)     | ~0    | PostgreSQL VACUUM ANALYZE        |
| G5  | **Stale Branch Cleanup**  | `0 4 * * 1`   | `20 * * * 0`            | ~2 min  | Nessuno (git)     | ~0    | Branch >30 giorni eliminate      |
| G6  | **SSL/Domain Check**      | `0 6 * * 1`   | `22 * * * 0`            | ~1 min  | Nessuno (curl)    | ~0    | Alert se certificato scade <14gg |
| G7  | **Fly.io Machine Health** | `0 */6 * * *` | `0 */6 * * *`           | ~1 min  | Nessuno (fly CLI) | ~0    | Restart machine se unresponsive  |

**G1 Health Check Deep — Cosa controlla:**

```
1. Backend: GET https://nuzantara-rag.fly.dev/health (status, embeddings.model, services)
2. Frontend: GET https://zantara.balizero.com (HTTP 200)
3. Qdrant: GET /collections (7 collections present)
4. PostgreSQL: SELECT 1 (connection alive)
5. Redis: PING (connection alive)
6. Fly.io machines: fly status (2 machines running)
7. Disk: df -h (usage <85%)
8. Pro Mac: ping 192.168.0.17 (reachable)
```

---

### SENTINEL (Intelligence) — Briefing e monitoraggio

| #   | Nome                   | Cron WITA       | Cron UTC       | Durata  | Modello      | RAM   | Output                             |
| --- | ---------------------- | --------------- | -------------- | ------- | ------------ | ----- | ---------------------------------- |
| S1  | **Morning Briefing**   | `0 8 * * *`     | `0 0 * * *`    | ~10 min | Gemini 3 Pro | ~1 GB | Report in `memory/reports/daily/`  |
| S2  | **Competitor Watch**   | `0 14,20 * * *` | `0 6,12 * * *` | ~5 min  | Gemini 3 Pro | ~1 GB | Alert se prezzi/servizi cambiano   |
| S3  | **Regulation Scanner** | `0 9 * * 1,4`   | `0 1 * * 1,4`  | ~15 min | Gemini 3 Pro | ~1 GB | Check imigrasi.go.id + pajak.go.id |
| S4  | **KB Freshness Check** | `0 3 * * 0`     | `19 * * * 6`   | ~10 min | Gemini 3 Pro | ~1 GB | Verifica dati Qdrant ancora validi |

**S1 Morning Briefing — Cosa genera:**

```markdown
# Daily Briefing — {data}

## Headlines

- [x] Immigration news Indonesia
- [x] Digital nomad visa updates
- [x] Bali business news

## Competitor Activity

- Competitor X: nessun cambio
- Competitor Y: nuovo servizio rilevato

## Action Items

- [ ] Aggiornare pricing se necessario
- [ ] Nuovo articolo su topic trending

## System Status (da Gravity)

- Backend: healthy
- Frontend: healthy
- Qdrant: 58,880 vectors
```

---

### VOX (Marketing) — Content e social

| #   | Nome                      | Cron WITA    | Cron UTC                | Durata  | Modello        | RAM   | Output                         |
| --- | ------------------------- | ------------ | ----------------------- | ------- | -------------- | ----- | ------------------------------ |
| V1  | **Social Pulse AM**       | `0 9 * * *`  | `0 1 * * *`             | ~5 min  | Sonnet 4.5     | ~1 GB | Trending topics report         |
| V2  | **Social Pulse PM**       | `0 15 * * *` | `0 7 * * *`             | ~5 min  | Sonnet 4.5     | ~1 GB | Engagement check               |
| V3  | **Social Pulse Evening**  | `0 21 * * *` | `0 13 * * *`            | ~5 min  | Sonnet 4.5     | ~1 GB | Next-day content plan          |
| V4  | **Content Calendar Sync** | `0 0 * * *`  | `16 * * * *` (prev day) | ~3 min  | Nessuno (file) | ~0    | Upcoming posts review          |
| V5  | **Weekly Blog Draft**     | `0 10 * * 2` | `0 2 * * 2`             | ~20 min | Sonnet 4.5     | ~1 GB | Article draft via Composer API |

---

### KODEX (Builder) — Code maintenance

| #   | Nome                 | Cron WITA    | Cron UTC                | Durata  | Modello           | RAM     | Output                          |
| --- | -------------------- | ------------ | ----------------------- | ------- | ----------------- | ------- | ------------------------------- |
| K1  | **Tech Debt Scan**   | `0 12 * * *` | `0 4 * * *`             | ~10 min | Sonnet 4.5        | ~1.5 GB | TODO scan, stale issues report  |
| K2  | **Test Suite Run**   | `0 5 * * *`  | `21 * * * *` (prev day) | ~5 min  | Nessuno (pytest)  | ~0.5 GB | Test results, coverage report   |
| K3  | **Dependency Audit** | `0 3 * * 1`  | `19 * * * 0`            | ~5 min  | Nessuno (pip/npm) | ~0      | Security vulnerabilities report |
| K4  | **Linting Sweep**    | `0 5 * * 3`  | `21 * * * 2`            | ~3 min  | Nessuno (ruff)    | ~0      | Code quality report             |

---

### ZAN (Gateway) — Operazioni di sistema

| #   | Nome                   | Cron WITA      | Cron UTC                | Durata | Modello        | RAM   | Output                    |
| --- | ---------------------- | -------------- | ----------------------- | ------ | -------------- | ----- | ------------------------- |
| Z1  | **Heartbeat**          | Built-in 30min | —                       | ~1 sec | Nessuno        | ~0    | Keepalive OpenClaw        |
| Z2  | **Memory Compaction**  | `0 3 * * *`    | `19 * * * *` (prev day) | ~2 min | Sonnet 4.5     | ~1 GB | CORE_MEMORY.md aggiornato |
| Z3  | **Daily Log**          | `0 23 * * *`   | `0 15 * * *`            | ~5 min | Sonnet 4.5     | ~1 GB | `memory/YYYY-MM-DD.md`    |
| Z4  | **Pro Liveness Check** | `*/30 * * * *` | `*/30 * * * *`          | ~5 sec | Nessuno (ping) | ~0    | Restart Pro se down       |

---

## RIEPILOGO RISORSE PER FASCIA ORARIA

### Notte (00:00-06:00 WITA) — Basso carico

| Ora   | Task                        | Modello      | Note                   |
| ----- | --------------------------- | ------------ | ---------------------- |
| 00:00 | V4: Content calendar        | None         | Solo file I/O          |
| 02:00 | G1: Health check            | Gemini 3 Pro | Quick                  |
| 03:00 | Z2: Memory compaction       | Sonnet 4.5   | Solo se session attiva |
| 03:00 | S4: KB freshness (domenica) | Gemini 3 Pro | Settimanale            |
| 04:00 | G1: Health check            | Gemini 3 Pro | Quick                  |
| 04:00 | G4: DB vacuum (domenica)    | None         | SQL only               |
| 04:00 | G5: Stale branches (lunedi) | None         | Git only               |
| 05:00 | K2: Test suite              | None         | pytest                 |

**RAM picco notte:** ~3 GB (1 modello cloud alla volta)

### Mattina (06:00-12:00 WITA) — Carico medio-alto

| Ora   | Task                          | Modello      | Note                          |
| ----- | ----------------------------- | ------------ | ----------------------------- |
| 06:00 | G1: Health check + G3: Disk   | Gemini 3 Pro | Sistema check                 |
| 08:00 | S1: Morning briefing          | Gemini 3 Pro | Report 10 min                 |
| 09:00 | V1: Social pulse AM           | Sonnet 4.5   | Trend check                   |
| 09:00 | S3: Regulation scan (lun/gio) | Gemini 3 Pro | **Potenziale overlap con V1** |
| 10:00 | V5: Blog draft (martedi)      | Sonnet 4.5   | Settimanale                   |
| 10:00 | G1: Health check              | Gemini 3 Pro | Quick                         |

**RAM picco mattina:** ~4 GB (S1 + V1 possono overlappare)
**Nota:** S3 e V1 partono alla stessa ora il lunedi. Non e un problema perche usano provider diversi (Gemini vs Anthropic).

### Pomeriggio (12:00-18:00 WITA) — Carico alto (ore lavorative)

| Ora   | Task                 | Modello      | Note             |
| ----- | -------------------- | ------------ | ---------------- |
| 12:00 | K1: Tech debt scan   | Sonnet 4.5   | 10 min           |
| 12:00 | G1: Health check     | Gemini 3 Pro | Quick            |
| 14:00 | S2: Competitor watch | Gemini 3 Pro | 5 min            |
| 14:00 | G1: Health check     | Gemini 3 Pro | Quick            |
| 15:00 | V2: Social pulse PM  | Sonnet 4.5   | Engagement check |
| 16:00 | G1: Health check     | Gemini 3 Pro | Quick            |

**RAM picco pomeriggio:** ~5 GB (Kodex + Sentinel potenziale overlap)

### Sera (18:00-00:00 WITA) — Carico medio

| Ora   | Task                     | Modello      | Note          |
| ----- | ------------------------ | ------------ | ------------- |
| 18:00 | G1: Health check         | Gemini 3 Pro | Quick         |
| 20:00 | S2: Competitor watch     | Gemini 3 Pro | 5 min         |
| 20:00 | G1: Health check         | Gemini 3 Pro | Quick         |
| 21:00 | V3: Social pulse Evening | Sonnet 4.5   | Next-day plan |
| 22:00 | G1: Health check         | Gemini 3 Pro | Quick         |
| 23:00 | Z3: Daily log            | Sonnet 4.5   | Summary       |

**RAM picco sera:** ~3 GB

---

## COSTO STIMATO CRON (per provider)

| Provider         | Task Cron/giorno               | Token stimati/giorno | Costo                 |
| ---------------- | ------------------------------ | -------------------- | --------------------- |
| **Gemini 3 Pro** | G1x12 + S1 + S2x2 + S3x0.28    | ~500K in + ~200K out | $0 (Ultra illimitato) |
| **Sonnet 4.5**   | V1-V3 + K1 + V5x0.14 + Z2 + Z3 | ~300K in + ~100K out | $0 (MAX incluso)      |
| **None (local)** | G2-G7 + K2-K4 + V4 + Z1 + Z4   | 0                    | $0                    |

**Costo totale cron:** $0/giorno (tutti coperti dagli abbonamenti).

---

## IMPLEMENTAZIONE OPENCLAW CRON

```json
// Esempio di job cron in OpenClaw (aggiungere via tool cron)
{
  "name": "gravity_health_check",
  "schedule": "0 */2 * * *",
  "type": "agentTurn",
  "agentId": "antigravity-general",
  "prompt": "Esegui health check completo: backend health endpoint, frontend status, Qdrant collections count, PostgreSQL ping, Fly.io machines status, disk usage. Se qualcosa e critico, notifica Zero via Telegram.",
  "timezone": "Asia/Makassar"
}
```

**Nota:** OpenClaw supporta timezone via il campo `timezone`. Usare `Asia/Makassar` per WITA (UTC+8).
