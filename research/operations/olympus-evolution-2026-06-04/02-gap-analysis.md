---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian — gap analysis
sources:
  - report 00 (baseline) + 01 (SOTA research) di questa pipeline
  - live prod query #2 nuzantara-rag (2026-06-04, via fly ssh + asyncpg) — evidenza numerica fresca
  - cicatrix W38 (backend_rag_v2 rolsuper), W64 (asyncpg InterfaceError), background-workers kill-switch
author: Claude Opus 4.8 (M5 session)
status: STEP 2 of 5 — gap analysis complete
---

# 02 — Gap Analysis: Olympus reale vs SOTA

> Terzo report. Incrocia i 7 principi SOTA (report 01) con lo stato prod reale (report 00 +
> query #2 fresca). **Diverse assunzioni di report 00/01 sono state CORRETTE da evidenza
> empirica nuova** — annotate sotto. Disciplina anti-allucinazione: ogni numero ri-verificato.

---

## 0. Correzioni empiriche (cosa avevo sbagliato/sovrastimato)

Query prod #2 ha ribaltato 3 assunzioni dei report precedenti:

1. **TXID wraparound NON è un rischio attuale.** `max(age(relfrozenxid)) = 3.547.415` vs
   `autovacuum_freeze_max_age = 200.000.000` → siamo all'**1.7%** della soglia. Report 01 lo
   marcava "gap critico". Correzione: è solo un gap di **osservabilità** (Olympus non lo mostra),
   non un pericolo imminente. Autovacuum nativo funziona.
2. **Le 68 refresh_matview failure NON sono croniche.** Sono TUTTE datate 2026-04-10/11
   (55+11+1+1), cioè boot iniziale. Probabile MV vuota/non-popolata al primo deploy. **Zero
   fallimenti recenti.** Report 00 implicava un problema in corso — falso. È storia.
3. **Il DB è genuinamente pulito ORA.** Una sola tabella con >1000 dead tuple: `user_stats`
   (9% dead). I 7.782 "vacuum skipped" erano transienti, non bloat cronico fuori-allowlist.

Lezione: senza ri-query empirica avrei scritto una spec che "risolve" problemi inesistenti.

---

## 1. Stato extension (fondamentale per i gap)

| Extension            | Disponibile | Installata                                     | Rilevanza                                                                  |
| -------------------- | ----------- | ---------------------------------------------- | -------------------------------------------------------------------------- |
| `pg_stat_statements` | ✅ sì       | ❌ **NO**                                      | **GAP #1** — query-intelligence cieca                                      |
| `pgstattuple`        | ✅ sì       | ❌ no                                          | misura bloat REALE indici/heap (oggi Olympus stima da pg_stat_user_tables) |
| `hypopg`             | ❌ no       | ❌ no                                          | what-if indici — non disponibile su Fly PG                                 |
| `pg_qualstats`       | ❌ no       | ❌ no                                          | suggerimento colonne — non disponibile                                     |
| installate ora       | —           | pg_trgm, pgcrypto, plpgsql, postgis, uuid-ossp | —                                                                          |

**Implicazione forte**: `hypopg`/`pg_qualstats` NON sono disponibili su questo PG → la pipeline
"qualify via hypothetical index" (Dexter/pganalyze) **non è implementabile as-is**. Serve
ripiego: o (a) what-if via `EXPLAIN` reale su clone, o (b) qualificazione euristica via
pg_stat_statements (quali query scansionano seq la tabella), o (c) chiedere a Fly se hypopg
è installabile. `pgstattuple` SÌ disponibile → upgrade di osservabilità a portata.

---

## 2. I gap, priorizzati (con evidenza numerica)

### GAP #1 — pg_stat_statements assente → query-intelligence cieca [ALTA]

- **Evidenza**: `has_pgss=false`. 704 azioni `query_intelligence skipped`. insights_by_type:
  **8.242 su 8.242 sono bloat_intelligence** — ZERO query insight.
- **SOTA**: pgss è la fondazione (DBtune, pganalyze, PostgresAI tutti partono da lì).
- **Blocco**: `CREATE EXTENSION pg_stat_statements` richiede (1) `shared_preload_libraries`
  (restart PG) e (2) privilegio. Interseca **cicatrix W38** (backend_rag_v2 rolsuper=t, demotion
  pending). Va fatto con admin DSN / flypgadmin, non a cuor leggero.
- **Valore**: sblocca regression detection query + baseline per ogni tuning futuro.

### GAP #2 — 8.242 insight inerti, nessun consumer [ALTA]

- **Evidenza**: insights_total=8.242, tutti `recommendation/bloat_intelligence`. Nessun codice
  legge `olympus_insights` per agire/digerire. `_check_v4_readiness` logga solo (soglia 500
  superata 16×) ma non attiva nulla. `olympus_skills` (Voyager) = scaffold vuoto.
- **SOTA principio #6**: insight DEVE avere consumer, altrimenti è spreco + crescita tabella.
- **Sub-problema**: probabile **duplicazione massiccia** — gli stessi unused_index ri-proposti
  ogni pulse (6.970 unused_index su ~704 pulse = ~10 per run, ripetuti). Nessuna dedup/supersede.
- **Valore**: trasformare 8.242 righe morte in (a) un digest settimanale azionabile per l'operatore,
  e/o (b) supersede automatico dei duplicati. Basso rischio, alto ROI.

### GAP #3 — Nessuna qualifica delle proposte (raw, non what-if) [MEDIA]

- **Evidenza**: 6.970 unused_index + 1.272 missing_index `proposed`, mai qualificati né attuati.
- **SOTA principio #2**: detect → **qualify** → propose → apply+rollback. Olympus salta qualify.
- **Vincolo**: hypopg non disponibile (vedi §1). Ripiego: qualificare unused_index con criteri
  più severi (idx_scan=0 **da N giorni** + non-unique + non-constraint), e missing_index solo
  se pgss conferma query lente sulla tabella. Senza qualify, restano rumore.

### GAP #4 — Nessun rollback versionato delle azioni di scrittura [MEDIA]

- **Evidenza**: feedback loop = solo confidence ±0.1. Se un'azione peggiora, Olympus non lo
  rileva né torna indietro. Tutte le confidence sono 1.0 (nessun degrado mai).
- **SOTA principio #5 (AgentOps)**: closed loop con versioned rollback.
- **Oggi mitigato da**: le azioni attuali sono quasi tutte idempotenti/safe (VACUUM, cleanup,
  refresh). Il rollback diventa CRITICO solo quando si aggiungono CREATE/DROP/ALTER. Quindi è
  **prerequisito** per qualsiasi azione L3, non urgente finché si resta L2.

### GAP #5 — Osservabilità incompleta (txid age, index bloat, lock duration) [MEDIA]

- **Evidenza**: heartbeat non cattura age(relfrozenxid) (anche se ora basso), né bloat indici
  (solo dead_tup heap), né durata lock (solo conteggio lock_waits). `pgstattuple` disponibile
  ma non usato.
- **SOTA principio #3/#5**: observability prima di optimization. boringsql: "VACUUM non sistema
  index bloat" → serve metrica index-bloat per decidere REINDEX.
- **Valore**: aggiungere 2-3 metriche heartbeat (txid_age, max_index_bloat via pgstattuple,
  longest_lock_seconds) → health_score più ricco + base per future azioni REINDEX sicure.

### GAP #6 — Crescita illimitata di olympus_heartbeats/actions/insights [BASSA-MEDIA]

- **Evidenza**: `ensure_next_partition` crea partizioni (2026_07 già presente ✓) MA **nessun
  drop di partizioni vecchie** né retention su olympus_actions/insights. 17.715 hb + 20.504
  actions + 8.242 insights e crescono. Parent `olympus_heartbeats` size=0 (dati nelle partizioni).
- **Rischio**: lento ma inesorabile. Olympus pulisce gli altri ma non sé stesso (eccetto creare
  partizioni). Ironico: il guardiano non applica la propria medicina (retention) a sé.
- **Valore**: aggiungere self-retention (drop partizioni hb >N mesi, prune actions/insights vecchi).

### GAP #7 — Insight duplicati, nessun supersede [BASSA]

- **Evidenza**: il campo `superseded_by` esiste su olympus_insights ma non è MAI popolato
  (8.242 righe, nessuna supersede). Stesse raccomandazioni ri-inserite ogni pulse.
- Sub-caso del GAP #2.

### GAP #8 — Robustezza loop / cicatrix correlate [TRASVERSALE]

- **Evidenza**: kill-switch `DISABLE_BACKGROUND_WORKERS` esiste per incident 2026-04-12 (pool
  corruption). Cicatrix W64: pattern asyncpg `InterfaceError` mancante in except sibling.
  Olympus usa `get_bg_pool_semaphore` (mitigazione S12).
- **Verifica necessaria**: i blocchi `except Exception` di Olympus catturano tutto (buono per
  resilienza) ma potrebbero mascherare InterfaceError. Da audit in fase spec.

---

## 3. Cosa NON è un gap (Olympus fa bene — non toccare)

- **Allowlist VACUUM 9%**: conservativa MA corretta. 7.782 skip sono il sistema che funziona.
  NON espandere a tappeto (anti-pattern confermato da SOTA).
- **No VACUUM FULL**: corretto. Mai introdurlo.
- **MV refresh**: 0 fallimenti recenti, 2.257 successi. Sano.
- **Partition creation**: funziona (2026_07 presente).
- **health_score**: matematicamente verificato, stabile a 98. Buon segnale aggregato.
- **Safety di repair_sequences / rebuild_invalid_indexes**: gating corretto (solo desync /
  solo indici invalidi).

---

## 4. Tabella riassuntiva priorità

| Gap | Titolo                              | Priorità    | Blocco/Dipendenza          | Rischio se non fatto                      |
| --- | ----------------------------------- | ----------- | -------------------------- | ----------------------------------------- |
| #1  | pg_stat_statements                  | ALTA        | restart PG + W38 privilege | query-intelligence resta cieca per sempre |
| #2  | consumer insight (digest+dedup)     | ALTA        | nessuno                    | 8.242 righe morte, crescono               |
| #3  | qualify proposte                    | MEDIA       | hypopg assente → ripiego   | proposte = rumore non azionabile          |
| #4  | rollback versionato                 | MEDIA       | prereq per L3              | blocca evoluzione verso azioni nuove      |
| #5  | osservabilità (txid/idx-bloat/lock) | MEDIA       | pgstattuple (disponibile)  | decisioni REINDEX cieche                  |
| #6  | self-retention                      | BASSA-MEDIA | nessuno                    | crescita illimitata tabelle olympus\_\*   |
| #7  | supersede insight                   | BASSA       | sub-#2                     | duplicazione                              |
| #8  | audit robustezza loop               | TRASVERSALE | —                          | pool corruption silente                   |

---

## 5. Tesi per la spec (input al panel 03)

Olympus è un **L2 sano ma "muto e cieco a metà"**: agisce bene nei suoi confini, ma
(a) è cieco sulle query (no pgss), (b) accumula insight che nessuno consuma, (c) non sa se
le sue azioni migliorano davvero (no rollback/misura). L'evoluzione giusta NON è "più azioni
automatiche" (saltare a L4) ma **chiudere il loop osservazione→insight→consumo** e
**aggiungere occhi** (pgss, pgstattuple, txid) PRIMA di aggiungere mani.

Ordine logico proposto (da validare col panel):

1. Vedere meglio (pgss + pgstattuple + txid/lock metrics) — observability first.
2. Consumare ciò che già vede (digest insight + dedup + self-retention) — basso rischio, alto ROI.
3. Qualificare le proposte (ripiego senza hypopg).
4. Solo DOPO: rollback versionato → prime azioni L3 gated (es. DROP unused index qualificato).

→ 03: sottoporre questa tesi + gap a Gemini + Codex + DeepSeek per red-team e priorità.
