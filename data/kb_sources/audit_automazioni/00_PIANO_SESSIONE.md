# Piano Sessione: Audit Completo Automazioni Nuzantara

**Data:** 2026-03-16
**Obiettivo:** Verificare, analizzare, eliminare/potenziare tutte le 109 automazioni
**Metodo:** 8 prompt specializzati, ognuno con scope chiaro e deliverable definito

---

## Mappa Prompt

| #   | Prompt                             | Scope                                         | Automazioni | Macchina | Priorità |
| --- | ---------------------------------- | --------------------------------------------- | ----------- | -------- | -------- |
| 1   | `01_PRO_CRONTAB.md`                | 5 entry crontab Pro                           | 5           | Pro      | ALTA     |
| 2   | `02_PRO_LAUNCHAGENTS_INFRA.md`     | LaunchAgents infrastrutturali Pro (KeepAlive) | 13          | Pro      | MEDIA    |
| 3   | `03_PRO_LAUNCHAGENTS_SCHEDULED.md` | LaunchAgents scheduled/non caricati Pro       | 13          | Pro      | ALTA     |
| 4   | `04_OPENCLAW_CRON.md`              | Tutti i 16 job OpenClaw                       | 16          | Pro      | CRITICA  |
| 5   | `05_BACKEND_AGENTS.md`             | Agenti autonomi + AutonomousScheduler         | 16          | Fly.io   | MEDIA    |
| 6   | `06_BACKEND_CHAINS_EVENTS.md`      | Workflow chains + event handlers + pipelines  | 20          | Fly.io   | MEDIA    |
| 7   | `07_AIR_CRONTAB.md`                | Tutti i cron job Air (dedup!)                 | ~30         | Air      | ALTA     |
| 8   | `08_AIR_LAUNCHAGENTS.md`           | LaunchAgents Air                              | 14          | Air      | MEDIA    |

**Totale: 8 prompt, ~127 verifiche (alcune overlap)**

---

## Ordine di Esecuzione Consigliato

1. **Prompt 1** (Pro crontab) — veloce, 5 entry, fix immediati
2. **Prompt 7** (Air crontab) — urgente, massiccia duplicazione
3. **Prompt 4** (OpenClaw cron) — 5 timeout + 4 broken, critico
4. **Prompt 3** (Pro LaunchAgents scheduled) — rotti + non caricati
5. **Prompt 2** (Pro LaunchAgents infra) — verifica salute servizi
6. **Prompt 8** (Air LaunchAgents) — verifica servizi Air
7. **Prompt 5** (Backend agents) — verifica agenti autonomi
8. **Prompt 6** (Backend chains/events) — verifica pipeline

I prompt 1+7 e 2+8 possono girare in parallelo su due AI diverse.
I prompt 5+6 possono girare in parallelo.

---

## Regole per ogni prompt

Ogni AI deve:

1. **VERIFICARE** — il job/servizio esiste? funziona? ultimo log?
2. **ANALIZZARE** — serve ancora? è duplicato? c'è overlap con altro?
3. **DECIDERE** — KEEP / POTENZIARE / ELIMINARE / FIXARE
4. **ESEGUIRE** — applicare la decisione (con conferma per eliminazioni)
5. **RI-VERIFICARE** — dopo le modifiche, confermare che tutto funziona

Output: tabella finale con decisione e stato post-modifica.
