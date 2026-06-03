---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian — evolution spec (SDD)
sources:
  - reports 00 (baseline) / 01 (SOTA) / 02 (gap) / 03 (panel) di questa pipeline
  - live prod queries x2 (2026-06-04) — evidenza numerica
  - cicatrix W38 (rolsuper demotion spec già esistente), W64 (asyncpg InterfaceError)
  - panel red-team: DeepSeek V4 Pro + Codex GPT-5.5 (convergenti su containment-first)
author: Claude Opus 4.8 (M5 session)
status: STEP 4 of 5 — SPEC DRAFT, awaiting Antonello approval (nothing executed)
decision_level: L2 (auth/RAG-adjacent infra + PG privilege + background workers)
---

# 04 — SPEC: Evoluzione Olympus DB Guardian

> Spec finale della pipeline olympus-evolution. **NIENTE è stato eseguito** — questo è un
> piano da approvare. Costruito sull'ordine corretto dal panel: **Safety Envelope PRIMA,
> osservabilità DOPO**. Ogni fase ha una metrica di successo falsificabile.
> Principio guida (panel-validato): trasformare Olympus da "trusted autonomous actor" a
> "bounded operator with auditable output" — poi, e solo poi, dargli più mani.

---

## 0. TL;DR

Olympus è un **SAE-L2 sano ma over-privileged, co-residente e con feedback debole**. Health=98
maschera l'assenza di misure di rischio (lock, query, crescita, delta-azioni). Il piano in 5 fasi:

- **P0 Safety Envelope** — contenimento (timeout, budget, kill-switch, circuit breaker, retention). _P0, ~1-2 settimane._
- **P1 Consume** — dedup/supersede insight + weekly digest Telegram. _Quick win, ~giorni._
- **P2 See** — pg*stat_statements + pgstattuple (budget-ato) + txid/lock metrics. \_Bloccato da restart+W38.*
- **P3 Qualify** — euristiche di qualifica + misura before/after. _Dipende da P2._
- **P4 Extract & L3** — worker separato + prime azioni gated. _Lungo termine._
- **INV — Investigazione confidence loop** — trasversale, in P0.

Ordine NON negoziabile: **P0 → P1 → P2 → P3 → P4**. Non saltare P0.

---

## 1. Problema (grounded)

Da reports 00/02 (verificato live):

- Olympus gira **in-process** nella FastAPI app, **single 2GB Fly machine**, pool asyncpg condiviso con l'app.
- Ruolo PG = `backend_rag_v2` = **superuser** (W38, demotion pending-approval).
- 13 regole, **tutte confidence 1.0 dopo 20.504 azioni** → feedback loop forse cerimoniale.
- 8.242 insight inerti (tutti bloat), **mai consumati, mai dedup-ati**.
- tabelle olympus\_\* **senza retention** → crescita illimitata.
- nessun `statement_timeout`/`lock_timeout`/budget sulle azioni pulse.
- health_score=98 non misura lock/query/crescita/delta.

Panel (03): il rischio #1 è **blast radius** (in-process + superuser + azioni autonome), non l'osservabilità.

---

## 2. Obiettivi & non-obiettivi

**Obiettivi**

- Ridurre il blast radius di Olympus a un livello provabile (timeout, budget, role-narrow, circuit breaker).
- Rendere consumabile l'output già prodotto (digest + dedup).
- Fermare la crescita illimitata (self-retention).
- Aggiungere osservabilità mancante in modo I/O-safe.
- Verificare se il feedback loop misura qualcosa di reale.

**Non-obiettivi (espliciti)**

- NO salto a L4/full-auto.
- NO azioni L3 (CREATE/DROP/ALTER autonomi) finché Olympus è in-process + superuser.
- NO VACUUM FULL, mai.
- NO espansione a tappeto dell'allowlist VACUUM a tutte le 265 tabelle.
- NO dipendenza da hypopg/pg_qualstats (non disponibili su questo PG).

---

## 3. FASE P0 — Safety Envelope [P0, ALTA]

> Obiettivo: Olympus non può più danneggiare l'app o il DB oltre confini provabili.

### P0.1 — Timeout per azione

- Ogni azione pulse che fa SQL di manutenzione apre la connection con
  `SET LOCAL statement_timeout = <N>s` e `SET LOCAL lock_timeout = <M>s`.
- Default proposti: `statement_timeout=300s` (VACUUM/REINDEX possono essere lunghi ma non infiniti),
  `lock_timeout=5s` (non aspettare lock più di 5s → fallisci pulito, riprova next pulse).
- Valori come regole olympus_rules (`action_statement_timeout_s`, `action_lock_timeout_s`).
- **Test**: tabella di prova con lock tenuto da altra sessione → l'azione fallisce con
  `lock_timeout` entro M s, outcome=failure, NON blocca il pulse.

### P0.2 — Budget per pulse

- `max_actions_per_pulse` (default 50) e `max_pulse_runtime_s` (default 600). Superato il budget,
  il pulse si ferma con un'azione `budget_exceeded` (proposed) e riprende next cycle.
- Previene il "runaway pulse" che esaurisce il pool (rischio DeepSeek).
- **Test**: seed con 200 tabelle bloated fittizie → pulse si ferma a 50 azioni.

### P0.3 — Circuit breaker su pool/InterfaceError

- Wrappare le acquire del pool: se N (default 3) errori `asyncpg.InterfaceError` /
  `ConnectionDoesNotExistError` consecutivi → Olympus entra stato OPEN, sospende heartbeat+pulse
  per cooldown (default 15min), alert Telegram. Half-open dopo cooldown.
- Chiude il gap W64 + l'incident 2026-04-12 (pool corruption → kill-switch manuale).
- **Cicatrix W64 fix concomitante**: assicurare che TUTTI gli except di Olympus includano
  `asyncpg.InterfaceError` accanto a `PostgresError` (sono sibling, non subclass).
- **Test**: mock pool che solleva InterfaceError 3× → breaker OPEN, loop sospeso, alert emesso.

### P0.4 — Kill-switch granulare

- Oggi: solo `DISABLE_BACKGROUND_WORKERS=1` (spegne tutto). Aggiungere:
  - regola DB `olympus_enabled` (bool) — spegne solo Olympus senza toccare altri worker.
  - regola `olympus_pulse_enabled` / `olympus_heartbeat_enabled` separate.
- Letto a inizio di ogni ciclo. Operatore può fermare il solo pulse lasciando l'heartbeat.
- **Test**: set `olympus_pulse_enabled=false` → heartbeat continua, pulse skippa con log.

### P0.5 — Self-retention (Olympus cura sé stesso)

- Nuova azione pulse `cleanup_olympus_self`:
  - DROP partizioni `olympus_heartbeats_YYYY_MM` più vecchie di `olympus_hb_retention_months` (default 6).
  - DELETE da `olympus_actions` più vecchie di `olympus_actions_retention_days` (default 90).
  - DELETE da `olympus_insights` superseded OR più vecchie di `olympus_insights_retention_days` (default 90).
- `olympus_heartbeats`/`olympus_actions` SONO già nell'allowlist VACUUM → coerente.
- **Test**: seed partizione vecchia + righe vecchie → cleanup le rimuove, conta i drop.

### P0.6 — Role narrowing (interseca W38)

- Olympus NON ha bisogno di superuser. Le sue azioni richiedono: OWNER sulle tabelle olympus\_\*
  (per partizioni), VACUUM/ANALYZE (owner o `MAINTAIN` priv PG16+), REFRESH MV (owner),
  REINDEX (owner), `pg_monitor` per le viste stat.
- Opzione A (preferita): allineare a W38 — quando `backend_rag_v2` diventa NOSUPERUSER, garantire
  che Olympus mantenga `pg_monitor` + `MAINTAIN` sulle tabelle target. NIENTE nuovo lavoro, solo
  validare che la demotion W38 non rompa Olympus (W38 spec lo cita già: "Olympus pulse DROP/CREATE
  partitions on owned olympus_heartbeats parent → OWNER preserves capability").
- Opzione B (se W38 resta bloccato): creare ruolo dedicato `olympus_maintenance` con privilegi
  minimi e far girare le azioni di scrittura Olympus con `SET ROLE olympus_maintenance`.
- **DECISIONE RICHIESTA**: A (dipende da approvazione W38) o B (indipendente ma più codice).

### INV — Investigazione confidence loop (Codex catch)

- Verificare PERCHÉ 0 regole degradate dopo 20.504 azioni. Ipotesi:
  (a) le azioni rule-governed (solo vacuum + audit_retention) non falliscono mai realmente;
  (b) `lower_confidence` chiamato solo su `outcome=failure` di azioni con `rule_applied` settato,
  e la maggior parte delle azioni non setta `rule_applied`.
- Query: `SELECT rule_applied, outcome, count(*) FROM olympus_actions GROUP BY 1,2`.
- Se il loop non misura nulla → o si arricchisce (legare più azioni a regole + success-criteria
  reali) o si dichiara esplicitamente "telemetria, non controllo" e si smette di chiamarlo feedback.
- **Output**: 1 paragrafo di verità nel report, eventuale micro-fix.

**Metrica di successo P0 (falsificabile)**: dopo P0, un VACUUM/REINDEX che supera statement*timeout
o un lock non disponibile NON blocca il pulse né tocca il pool oltre lock_timeout; un budget di 50
azioni è rispettato; un InterfaceError storm apre il breaker entro 3 errori; le tabelle olympus*\*
smettono di crescere illimitatamente. Tutto verificato con test su PG reale (Pro throwaway).

---

## 4. FASE P1 — Consume (output utile) [ALTA, quick win]

### P1.1 — Dedup/supersede insight

- Prima di inserire un insight, cercare un insight attivo (`superseded_by IS NULL`) con stesso
  `(source, title)` o stesso `applicable_to[0]`. Se esiste e l'evidenza è equivalente →
  aggiornare `accessed_count`/timestamp invece di inserire duplicato. Se l'evidenza cambia →
  inserire nuovo e settare `superseded_by` sul vecchio.
- Riduce 8.242 → poche centinaia di insight distinti.
- **Test**: 2 pulse consecutivi con stesso unused_index → 1 solo insight attivo, non 2.

### P1.2 — Weekly digest Telegram

- Nuovo cron/azione settimanale: leggi insight attivi (post-dedup) raggruppati per tipo/severità,
  produci digest markdown → invia Telegram all'operatore via AlertService esistente.
- Formato: top-N unused index (con size), top-N missing index (con seq_scan), anomalie query
  (quando P2 sblocca pgss), trend health_score 7gg.
- **Questo è il "consumer" mancante**: rende azionabili 8k osservazioni silenziose.
- **Test**: invocazione manuale → messaggio Telegram ben formato, ≤4000 char, no PII.

**Metrica di successo P1**: insight attivi < 500 (da 8.242); digest settimanale arriva su Telegram
con raccomandazioni leggibili; l'operatore può dire "sì droppa quell'indice" o "ignora".

---

## 5. FASE P2 — See (osservabilità) [MEDIA, bloccata]

### P2.1 — pg_stat_statements

- `shared_preload_libraries += pg_stat_statements` → **richiede restart PG** (finestra Sunday
  03:00-05:00 WITA, come W38 stage C). `CREATE EXTENSION pg_stat_statements`.
- Richiede privilegio → fare DOPO/INSIEME a W38 con admin DSN (`flypgadmin`), non con app role.
- Sblocca i 704 query_intelligence skipped → regression detection reale.
- **DECISIONE RICHIESTA**: schedulare restart PG. Costo: ~1 restart, finestra bassa-traffico.

### P2.2 — pgstattuple (I/O-safe)

- Usare `pgstattuple_approx()` (NON `pgstattuple()` full-scan) per stimare bloat indici/heap reale,
  SOLO su tabelle in allowlist, SOLO 1-2 per pulse (budget P0.2), mai in heartbeat (troppo frequente).
- Mitiga il rischio I/O-spike sollevato da DeepSeek.
- **Test**: pgstattuple_approx su tabella grande → ritorna stima, durata < statement_timeout.

### P2.3 — Metriche heartbeat aggiuntive

- `txid_age` = max(age(relfrozenxid)) — anche se ora 1.7%, mostrarlo (trend).
- `longest_lock_wait_s` = durata del lock-wait più lungo (non solo conteggio).
- (opz) `max_index_bloat_pct` da pgstattuple_approx (da P2.2).
- Aggiungere a HeartbeatSnapshot + colonne (migration) + health_score (pesi da ricalibrare).

**Metrica di successo P2**: query_intelligence produce ≥1 insight reale (non skipped); heartbeat
mostra txid_age + longest_lock; nessun degrado di latenza app misurabile post-pgss.

---

## 6. FASE P3 — Qualify (azioni qualificate) [MEDIA, dipende P2]

- **unused_index**: proporre DROP solo se `idx_scan=0` da ≥`unused_index_min_age_days` (default 30,
  basato su pg_stat_user_indexes reset tracking) AND non-unique AND non-constraint AND size>soglia.
- **missing_index**: proporre solo se pgss (P2.1) conferma query lente che scansionano seq la tabella.
- Ogni proposta qualificata porta una **stima** (size liberato per drop; query impattate per create).
- Resta `proposed` — l'attuazione è P4.
- **Test**: indice usato di recente NON proposto per drop; indice 0-scan da 60gg proposto.

**Metrica di successo P3**: ogni proposta nel digest ha una qualifica + stima; falsi positivi
(proporre drop di un indice usato) = 0 su un campione verificato a mano.

---

## 7. FASE P4 — Extract & L3 [LUNGO TERMINE, gated]

> Solo dopo P0-P3 stabili. Richiede approvazione separata.

### P4.1 — Estrazione in worker separato

- Spostare Olympus da in-process FastAPI a un processo/worker dedicato (process group separato o
  Fly machine dedicata) con: pool proprio, limiti risorse propri, ruolo PG ristretto, log propri,
  restart policy propria.
- Elimina il blast radius co-residenza (rischio #1 panel).

### P4.2 — Prime azioni L3 gated

- Solo DOPO estrazione + ruolo ristretto. Prima azione candidata: **DROP di unused_index
  qualificato** (P3) — MA con `CREATE INDEX` script di rollback pre-generato e salvato in
  olympus_actions.detail (l'unico "rollback" sensato per un DROP: ricreare l'indice). DeepSeek ha
  ragione che non è un vero rollback istantaneo, quindi: gate con approvazione operatore (digest →
  "approva drop" → esegui), NON full-auto.
- CREATE INDEX CONCURRENTLY con detection+cleanup `_ccnew` invalidi (riusa rebuild_invalid_indexes).

**Metrica di successo P4**: Olympus gira fuori dall'app; un crash di Olympus NON tocca la latenza
app; la prima azione L3 richiede approvazione esplicita e ha lo script di ricreazione salvato.

---

## 8. Rollout & sicurezza

- **Branch/worktree**: ogni fase in worktree dedicato (`scripts/agent_start.py --lane db`).
- **Test obbligatori**: ogni fase testata su PG reale throwaway (Pro) PRIMA del deploy, come fatto
  in report 00. Unit + e2e.
- **Deploy**: rolling, finestra bassa-traffico per P2.1 (restart PG). Post-deploy verify via
  `/internal/olympus/*` + query olympus_actions.
- **Rollback per fase**: P0-P1 puramente additive (nuove regole/azioni, disattivabili via kill-switch).
  P2.1 (pgss) reversibile (`DROP EXTENSION` + rimuovi da shared_preload). P4 dietro approvazione.
- **Kill-switch sempre disponibile**: `DISABLE_BACKGROUND_WORKERS=1` + nuovo `olympus_enabled=false`.
- **Cost**: $0 (no nuove API). pgss/pgstattuple sono extension PG già disponibili.

---

## 9. Decisioni richieste ad Antonello (gate)

1. **P0.6 role narrowing**: opzione A (legare a W38, aspettare la demotion) o B (ruolo dedicato
   `olympus_maintenance` ora)? → consigliata **A** se W38 è in approvazione comunque.
2. **P2.1 pgss**: autorizzi un restart PG in finestra bassa-traffico per `shared_preload_libraries`?
3. **Ordine confermato P0→P4**? In particolare: P0 Safety Envelope prima di tutto?
4. **Ampiezza prima iterazione**: solo P0+P1 (envelope + consume, ~2 settimane, basso rischio) come
   primo PR, poi rivalutare? → consigliato.

---

## 10. Checklist pre-implementazione (quando approvato)

- [ ] worktree `db/olympus-safety-envelope`
- [ ] migration: nuove regole olympus_rules (timeout, budget, retention, enabled flags)
- [ ] P0.1 timeout + P0.2 budget in pulse.py (con test PG reale)
- [ ] P0.3 circuit breaker in guardian.py + W64 InterfaceError fix in tutti gli except
- [ ] P0.4 kill-switch granulare (lettura regole a inizio ciclo)
- [ ] P0.5 cleanup_olympus_self azione + test
- [ ] INV: query confidence loop + 1 paragrafo verità
- [ ] P1.1 dedup/supersede in insights.py + test
- [ ] P1.2 weekly digest + Telegram (no PII) + test
- [ ] pytest backend/tests/services/olympus/ verde + nuovi test
- [ ] e2e su PG reale throwaway (Pro)
- [ ] deploy rolling + post-deploy verify
- [ ] (P2+) decisione restart PG + W38 coordination

---

## 11. Appendice — mapping gap→fase

| Gap (report 02)                 | Fase      | Note                                       |
| ------------------------------- | --------- | ------------------------------------------ |
| #1 pgss assente                 | P2.1      | bloccato da restart+W38 → NON è P0 (panel) |
| #2 insight inerti               | P1.1+P1.2 | dedup + digest                             |
| #3 no qualify                   | P3        | euristiche (no hypopg)                     |
| #4 no rollback                  | P4.2      | solo per L3, con approvazione              |
| #5 osservabilità                | P2.2+P2.3 | pgstattuple_approx + txid/lock             |
| #6 crescita illimitata          | P0.5      | self-retention (anticipato a P0!)          |
| #7 supersede                    | P1.1      | parte di dedup                             |
| #8 robustezza loop              | P0.3      | circuit breaker + W64 fix                  |
| (panel) confidence cerimoniale  | INV       | investigazione P0                          |
| (panel) blast radius in-process | P4.1      | estrazione lungo termine                   |
| (panel) timeout/budget assenti  | P0.1+P0.2 | il cuore dell'envelope                     |

---

> FINE PIPELINE olympus-evolution. 5 report: 00 baseline · 01 research · 02 gap · 03 panel · 04 spec.
> Stato: spec pronta, **nulla eseguito**, in attesa decisioni §9.
