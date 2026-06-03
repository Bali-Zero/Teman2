---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian — SOTA research
sources:
  - https://postgres.ai/blog/20250725-self-driving-postgres (WebFetch deep-read)
  - https://pganalyze.com/blog/automatic-indexing-system-postgres-pganalyze-indexing-engine
  - https://pganalyze.com/postgres-index-advisor (cluster-aware, constraint programming)
  - https://github.com/ankane/dexter + https://ankane.org/introducing-dexter (Dexter + HypoPG)
  - https://www.percona.com/blog/automatic-index-recommendations-in-postgresql-using-pg_qualstats-and-hypopg/
  - https://www.dbtune.com (AI param tuning, pg_stat_statements baseline)
  - https://devops.com/agentic-sre-the-next-frontier-of-reliability/ (bounded actions + policy)
  - https://www.emergentmind.com/topics/agentops-framework (closed feedback loop + versioned rollback)
  - https://arxiv.org/pdf/2602.11749 (AIR — agent safety via incident response DSL)
  - https://www.postgresql.org/docs/current/sql-reindex.html (REINDEX CONCURRENTLY tradeoffs)
  - https://boringsql.com/posts/vacuum-is-lie/ (VACUUM does NOT fix index bloat)
author: Claude Opus 4.8 (M5 session)
status: STEP 1 of 5 — deep research complete
---

# 01 — Deep Research: SOTA agenti DB autonomi

> Secondo report pipeline olympus-evolution. Input: tool reali (WebSearch ×4, WebFetch ×1).
> Exa MCP richiedeva OAuth interattivo (saltato); agy CLI verificato vivo ma verboso (riservato
> al panel 03). NotebookLM: nessun NB copre "autonomous DB agents" (dominio infra, non
> regulatory/visa/tax) → non interrogato, non è ground-truth per questo dominio.
> Scopo: mappare lo stato dell'arte e estrarre principi applicabili a Olympus.

---

## 1. Landscape: chi fa cosa (prior art)

### 1.1 Index automation (il cuore del gap Olympus)

| Tool                          | Approccio                                                                                                                                          | Lezione per Olympus                                                                                                                                                 |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dexter** (ankane)           | Legge log query → genera indici candidati → **valida con HypoPG** (indici ipotetici, EXPLAIN finto) → opzionale auto-create                        | Olympus oggi _propone_ missing_index senza validare il beneficio reale. Dexter aggiunge il "what-if" prima di proporre.                                             |
| **HypoPG**                    | Estensione: crea indici **ipotetici** (zero costo), EXPLAIN li considera                                                                           | Permette di stimare il guadagno di un indice SENZA crearlo. È il modo safe per qualificare i 1.272 missing_index.                                                   |
| **pg_qualstats**              | Campiona predicati WHERE/JOIN → suggerisce indici (solo B-Tree)                                                                                    | Complementare a pg_stat_statements per capire QUALI colonne indicizzare                                                                                             |
| **pganalyze Indexing Engine** | **Constraint programming**, cluster-aware, gira FUORI dal DB di prod (zero overhead, no estensioni in prod), usa il planner Postgres per "what-if" | SOTA assoluto. Insight chiave: l'analisi pesante NON deve girare in-process sul DB di prod. Cluster-aware = considera tutti gli indici insieme, non uno alla volta. |

**Takeaway #1**: la pipeline corretta è **detect → qualify (HypoPG/planner what-if) → propose con stima-guadagno → (opzionale) apply con rollback**. Olympus salta lo step "qualify": propone grezzo. I 6.970 unused_index + 1.272 missing_index sono raw signal, non qualificati.

### 1.2 Config / parameter tuning

- **DBtune**: agente che stabilisce baseline via `pg_stat_statements`, esplora config server (autovacuum, checkpoint, work_mem, shared_buffers) con AI engine, applica e ri-valuta contro un obiettivo. Loop iterativo monitor→propose→apply→evaluate.
- **PostgresAI self-driving**: `pg_index_pilot` per reindex automatico, tuning autovacuum + checkpoint params.
- Olympus ha `autovacuum_advisor` ma si ferma a `proposed` (mai ALTER). Coerente con prudenza, ma il valore resta inespresso.

**Takeaway #2**: pg_stat_statements è la **fondazione** di ogni sistema serio (baseline query + tuning). Olympus non ce l'ha in prod → tutto il ramo query-intelligence è cieco. Questo è il gap #1 da chiudere.

### 1.3 Oracle Autonomous DB / cloud RDBMS

- Oracle ADB: self-driving/self-securing/self-repairing, ma è un prodotto chiuso full-managed. Lezione concettuale, non implementativa: la tripletta **drive (tuning) / secure (access) / repair (heal)** è un buon assetto mentale.

---

## 2. Framework di autonomia: SAE J3016 levels (PostgresAI)

PostgresAI adotta la classificazione auto a guida autonoma SAE J3016 (0-5) per i DB:

| Livello | Significato DB                                                     | Dove sta Olympus OGGI                                                    |
| ------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| L0      | Nessuna automazione, tutto manuale                                 | —                                                                        |
| L1      | Assistenza (alert, suggerimenti)                                   | ✅ Olympus fa questo (proposed insights)                                 |
| **L2**  | **Automazione parziale bounded** (azioni safe in confini definiti) | ✅ **Olympus È QUI** (vacuum allowlist, cleanup, seq-repair, MV refresh) |
| L3      | Conditional — autonomo entro boundary, umano su eccezioni          | ⬅ target realistico prossimo                                             |
| L4      | High — autonomo, umano raramente                                   | aspirazionale                                                            |
| L5      | Full self-driving                                                  | no                                                                       |

**Takeaway #3**: Olympus è un **L2 solido** (osserva + agisce in confini stretti). L'evoluzione naturale è **L2→L3**: aumentare le azioni autonome MA solo dietro qualifica (what-if) + policy + rollback. NON saltare a L4.

PostgresAI insiste: "automation levels 3-4 initially" ma con **assisted RCA** (diagnosi assistita, non remediation cieca). E: **prioritize observability over optimization** — prima detect bloat, poi automate create.

---

## 3. Agentic SRE / AgentOps — i pattern di sicurezza

Dai risultati su agentic-SRE e AgentOps (2025-2026):

### 3.1 Bounded actions + policy + confidence threshold

> "an agent can recommend or execute low-risk actions ... tied to policy checks, confidence thresholds and human approval for anything that affects customer-facing production behavior."

Mappa diretta su Olympus:

- **low-risk auto** (già fa): VACUUM su allowlist, cleanup, refresh MV.
- **medium-risk gated**: CREATE INDEX, DROP unused index, ALTER autovacuum → richiede confidence + (per ora) human approval o canary.
- **high-risk mai-auto**: DROP TABLE, VACUUM FULL, ALTER SYSTEM.

### 3.2 Closed feedback loop + versioned rollback (AgentOps)

> "closed feedback loops ... automated triage, root cause discovery, and safe application of fixes, including ... versioned rollback."

Olympus ha **mezzo loop**: applica azioni, registra outcome, aggiusta confidence regole. MA:

- Manca il **rollback versionato**: se crea un indice e peggiora, non lo sa e non torna indietro.
- Manca il **consumer degli insight**: 8.242 insights raccolti, nessuno li legge/azione.

### 3.3 AIR — incident response come guardrail (arxiv 2602.11749)

DSL per gestire il ciclo incident: detect (semantic check) → contain → recover → **synthesize guardrail rules durante eradication**. Cioè: ogni incidente genera una nuova regola che previene il ripetersi.

**Takeaway #4**: il feedback loop di Olympus (confidence ±) è primitivo rispetto allo SOTA. Lo SOTA: ogni fallimento → nuova regola/guardrail, non solo -0.1 di confidence. Questo è il ponte verso olympus_skills (Voyager) oggi vuoto.

---

## 4. Rischi noti (dove un DB-agent fa danni) — da PG docs + boringsql

1. **REINDEX CONCURRENTLY**: fa **2 scan completi** della tabella + aspetta la terminazione di TUTTE le transazioni che potrebbero usare l'indice. Su tabelle grandi = ore, più lavoro totale, può fallire lasciando un indice `_ccnew` invalido. → Olympus lo fa solo su indici già invalidi (safe) ma se lo estende deve avere timeout + cleanup dei `_ccnew`.
2. **VACUUM FULL**: ACCESS EXCLUSIVE lock, blocca tutto. Olympus usa solo `VACUUM ANALYZE` (no FULL) — corretto. NON introdurre mai VACUUM FULL auto.
3. **VACUUM non sistema il bloat degli indici** (boringsql "VACUUM is a lie about your indexes"): heap sì, index no. Serve REINDEX. → Olympus monitora dead_tup (heap) ma non il bloat indici. Gap di osservabilità.
4. **TXID wraparound**: il rischio esistenziale. Autovacuum DEVE restare on. Olympus non monitora age(relfrozenxid) → cieco sul wraparound. **Gap critico di osservabilità.**
5. **Index creation in prod**: lock. CREATE INDEX CONCURRENTLY obbligatorio, ma può fallire e lasciare indice invalido → serve detection+cleanup loop (che Olympus già ha per rebuild_invalid_indexes — riusabile).

**Takeaway #5**: prima di aggiungere QUALSIASI azione di scrittura nuova (create/drop index, alter), aggiungere prima l'**osservabilità** del rischio relativo: index bloat ratio, txid age, lock-wait duration. "Observability over optimization".

---

## 5. Sintesi: 7 principi SOTA applicabili a Olympus

1. **pg_stat_statements è fondamentale** — senza, query-intelligence è cieca. (gap #1)
2. **detect → qualify (HypoPG/planner what-if) → propose → apply+rollback** — Olympus salta "qualify". (gap #2)
3. **Observability prima di optimization** — aggiungere txid-age, index-bloat, lock-duration PRIMA di nuove azioni. (gap #3)
4. **SAE L2→L3** — crescere bounded, non saltare a full-auto. Ogni nuova azione dietro policy+confidence+canary.
5. **Closed loop con rollback versionato** — non solo confidence±; serve "applico, misuro, se peggiora torno indietro".
6. **Insight DEVE avere consumer** — 8.242 insight inerti = spreco. O li si consuma (digest/azione) o si smette di raccoglierli. olympus_skills (Voyager) è lo slot giusto.
7. **Guardrail-synthesis dagli incidenti (AIR)** — ogni failure genera regola preventiva, non solo penalità.

## 6. Cosa NON fare (anti-pattern confermati dalla ricerca)

- Mai VACUUM FULL automatico.
- Mai CREATE/DROP index senza CONCURRENTLY + what-if + rollback.
- Mai analisi pesante in-process sul pool di prod (pganalyze gira FUORI). Olympus gira in-process → tenere le query insights LEGGERE o spostarle.
- Mai espandere l'allowlist VACUUM "a tutte le 265 tabelle" senza per-tabella qualify (alcune vogliono finestre, alcune sono partizionate).

---

## 7. Next

→ 02 gap-analysis: incrociare questi 7 principi con lo stato reale prod (report 00) e
produrre la lista priorizzata di gap con evidenza numerica.
