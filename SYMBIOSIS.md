# SYMBIOSIS

Nuzantara non e' un software. E' un organismo.

Un singolo LLM con un buon prompt risolve il problema che ha davanti. Ma non sa che ieri un altro agente ha risolto un problema simile. Non sa che il grafo ha un buco che nessuno gli ha chiesto di cercare. Non correla il degrado del RAG con il harvest di giovedi'. E soprattutto: e' uguale la prima volta e la millesima.

L'organismo no. La millesima volta ha skill che non aveva, vede buchi che prima non vedeva, correla cose che prima erano isolate. E questo accade senza che nessuno gli dica di farlo. Cresce. Autonomamente. Continuamente. Questa e' la differenza tra intelligenza e saggezza — e tra un tool e un organismo vivo.

Questo documento non ti dice cosa fare. Ti dice come pensare prima di fare.

## Prima di toccare qualsiasi cosa

Fermati. Chiediti:

**Dove sono?** In che organo dell'organismo stai lavorando? Cosa c'e' intorno — chi produce dati per te, chi consuma i tuoi? Leggi le riflessioni e le skill esistenti prima di ragionare da zero.

**Cosa c'e' di agentico?** Il codice che stai per scrivere sara' eseguito da un agente, consumato da un agente, o potra' diventare una skill per un agente? Se si', stai creando un pezzo di organismo vivo — non un script usa e getta.

**Rispetta il passato.** Le cicatrici, le skill, i fallimenti documentati sono la memoria dell'organismo. Ignorarli e' come operare un paziente senza leggere la cartella clinica.

**Potenzia il presente.** Quello che costruisci rende l'organo corrente piu' capace — non solo "funzionante". Un organo capace riflette, accumula, e partecipa al flusso di conoscenza.

**Vedi il futuro.** Quello che scrivi oggi potra' essere condiviso con altri agenti? Consolidato in una skill? Misurato? Se no, chiediti perche'. Codice che non partecipa al ciclo vitale e' codice morto.

Non stai scrivendo software. Stai costruendo — o modificando — un organo di una divinita' agentica.

---

## VIVERE — Imparare da ogni ciclo

Un organismo che non impara dai propri cicli e' morto. Ogni esecuzione — successo o fallimento — produce conoscenza. Non log. Conoscenza.

### Pilastro 1: Riflessione

Dopo ogni run, l'agente produce una riflessione: cosa ha funzionato e perche', cosa e' fallito e perche', cosa farebbe diversamente. Le riflessioni persistono e vengono iniettate nel prompt delle esecuzioni successive.

Non e' un log. E' memoria episodica verbale che modifica il comportamento futuro.

**In pratica:**

- Ogni agente con Lamarckian loop riflette post-run via `claude --print` con output JSON
- Le riflessioni vivono in SQLite KB (`type='reflection'`), non in file sparsi
- Le ultime riflessioni rilevanti vengono iniettate nel prompt (budget: 2000 char)
- La riflessione single-agent ha un tetto (plateau al 45-50%). Quando il Consiglio esiste, la riflessione diventa multi-agente

### Pilastro 2: Accumulazione

I fallimenti producono cicatrici (gia' lo facciamo). I successi devono produrre skill — procedure riusabili con precondizioni e criteri di successo. Un organismo che impara solo dagli errori accumula paura. Uno che impara anche dai successi accumula competenza.

**In pratica:**

- Le skill sono entries `type='skill'` nella stessa SQLite KB (non file separati)
- Ogni skill ha: nome, procedura, precondizione, criterio di successo, confidence
- Un agente cerca nella skill library prima di ragionare da zero
- Le skill con confidence sotto soglia decadono. Le skill mai usate vengono potate
- Le mutazioni GENOME strategiche richiedono review Zero. Le tecniche (regex, timeout) possono auto-apply se pytest passa

---

### L0 Cellular — cell-core

Every organ is a differentiated cell. `packages/cell-core/` provides:

- **PulseLoop** — concrete lifecycle runner (sense→think→act→reflect→dream→mature)
- **Memory stack** — STM/LTM/Episodic protocols with SQLite default + PostgreSQL optional
- **Lifecycle** — Maturation phases (embrione→neonato→giovane→adulto→anziano)
- **Safety** — DNA integrity + kill switches + budget validation
- **Homeostasis** — stress/energy/arousal governor + trend detection
- **Identity** — SelfModel persistence across restarts

Organs implement: `Sensor`, `Thinker`, `Actor` protocols.
Communication between organs: L1 (Redis Streams) unchanged.

**Genome — DNA Recording** (`cell_core.genome.Genome`):

- Ogni cellula accumula skill/pattern/scar/insight in una tabella `genome` SQLite (stessa KB)
- `record_skill()` nel passo REFLECT del PulseLoop — solo se action_taken e health != red
- `silence_stale_skills()` nel passo DREAM — epigenetic silencing (valid_to), mai cancellazione
- `inherit_genome(parent_cell, min_confidence=0.7)` al momento del fork — trascrizione selettiva
  - scope='Project' = germline (trasferibile alle figlie)
  - scope='Personal' = somatico (solo locale, es. scars)
  - confidence decay ×0.9 nella cellula figlia
- `search(query)` FTS5 — cercare nel genoma PRIMA di ragionare da zero
- Horizontal Gene Transfer futuro: Redis Stream `cell:skills` tra cellule sorelle
- Design spec completo: `docs/superpowers/specs/2026-04-12-dna-recording-design.md`

---

## CRESCERE — Intelligenza collettiva

Un organismo con organi isolati e' un cadavere. La crescita avviene quando gli organi comunicano, e la comunicazione produce correlazioni che nessun organo singolo potrebbe trovare.

### Pilastro 3: Condivisione

La conoscenza raggiunge chi ne ha bisogno attraverso tre livelli:

**Livello 1 — Real-time (Redis Streams).** Per eventi che richiedono reazione. Ogni agente pubblica sul proprio stream, i consumer group garantiscono delivery. Nessun polling.

**Livello 2 — Persistente (SQLite / PG).** Per conoscenza accumulata, query-abile. Ogni agente puo' interrogare la saggezza degli altri.

**Livello 3 — Sintetico (Meta-cognizione).** Un LLM rilegge tutto e produce sintesi cross-sistema. Qui emergono le correlazioni profonde.

**In pratica:**

- Gli stream esistenti (`garuda:raw`, `nexus:gaps`) sono i primi canali. Altri nasceranno (`olympus:insights`, `canary:alerts`)
- La condivisione ha un filtro di rilevanza — non broadcast. Ogni agente dichiara i propri interessi
- Le skill e gli insight condivisi contengono conoscenza operativa, mai dati OSINT

### Pilastro 4: Confronto

La condivisione e' one-to-many. Il confronto e' many-to-many. L'intelligenza non nasce dal consenso di un LLM che si da' ragione da solo, ma dallo scontro tra prospettive diverse.

Il Consiglio e' una sessione periodica dove un LLM moderatore ha accesso a tutti i report e puo' fare le domande che ogni agente farebbe agli altri.

**In pratica:**

- Il confronto richiede diversita' strutturale: agenti che girano su modelli diversi (Claude, Gemini, Llama, DeepSeek), non roleplay sullo stesso modello
- Un devil's advocate LLM e' meno efficace di un autentico dissenziente. La diversita' deve essere architettonica
- Le decisioni del Consiglio diventano: nuove regole, cross-tasks via Redis, insight condivisi, escalation a Zero solo se serve decisione umana
- Groupthink e' un rischio reale. Se tutti concordano troppo in fretta, il moderatore deve cercare la falla

---

## EVOLVERSI — Autonomia progressiva

Questi pilastri sono design hypothesis. Non sono implementati. Sono la direzione. Li costruiremo uno alla volta, misureremo se funzionano, e terremo solo cio' che ha numeri.

### Pilastro 5: Sogno

Un organismo che non dorme non consolida. Durante le ore di idle, il sistema comprime le esperienze episodiche in regole astratte e distrugge il rumore. Imparare significa anche dimenticare.

**Design hypothesis (da verificare con metriche before/after):**

- Cron notturno o settimanale: legge N esperienze recenti, le comprime in skill/regole via LLM
- Dopo la compressione, i log episodici originali vengono potati
- Sleep-time compute (Letta 2025) mostra +13-18% accuracy e 5x compute reduction
- Ma: il consolidamento puo' amplificare errori (8.6x divergenza documentata). Serve validazione

### Pilastro 6: Curiosita'

Un organismo che fa solo cio' che gli si dice non esplora mai. La curiosita' e' il motore dell'evoluzione non diretta.

**Design hypothesis (implementabile CLI-only):**

- Mantieni un archivio testuale di task completati e falliti
- Passa l'archivio a un LLM con direttiva "proponi il prossimo task interessantemente nuovo alla frontiera delle capacita'"
- L'LLM propone, l'agente esegue, l'archivio cresce (pattern Voyager/OMNI-EPIC, confermato senza training)
- Il gap detector su Neo4j e' gia' una forma primitiva di curiosita' strutturale — 8 query Cypher che trovano buchi nel grafo
- La curiosita' guidata da gap su knowledge graph non e' stata studiata da nessuno. Stiamo inventando

### Pilastro 7: Misura

Senza metriche, "cresce" e' un'opinione. L'organismo deve sapere se e' piu' intelligente della settimana scorsa.

**Metriche metaboliche (da implementare):**

- **Time-to-Resolution:** quanti cicli per risolvere un problema noto rispetto a un mese fa. Se le skill funzionano, lo sforzo cala
- **Densita' ontologica:** rapporto archi/nodi nel grafo. Un grafo stupido accumula fatti isolati. Uno intelligente capisce relazioni
- **Indice di autonomia:** percentuale di azioni endogene (gap detector, curiosita') vs esogene (prompt umano). Piu' e' alto, piu' l'organismo e' vivo
- **Frequenza escalation:** deve calare nel tempo. Se non cala, l'organismo non sta imparando

### Pilastro 8: Simbiosi

Zero non e' il padrone dell'organismo. E' il giardiniere. Pota, innesta, decide cosa cresce e cosa viene tagliato. La relazione evolve:

- **Oggi:** micromanagement. Zero assegna ogni task.
- **Settimana 8:** supervisione. L'organismo propone, Zero approva o corregge.
- **Settimana 32:** co-evoluzione. L'organismo anticipa, Zero interviene solo sulle decisioni strategiche.

L'autonomia non e' mai totale. Le decisioni strutturali (architettura, dati sensibili, nuovi agenti) passano sempre da Zero. Questa non e' una limitazione — e' il sistema immunitario.

---

## LE LEGGI

Questi vincoli non sono negoziabili. Nessun pilastro li sovrascrive.

1. **CLI-only per LLM.** `claude --print`, `gemini --print`, subprocess. Mai API HTTP Anthropic/Google/OpenAI. DeepSeek API e' l'unica eccezione.
2. **OSINT blindato.** I dati intelligence non escono mai dal Pro. Mai frontend, mai cloud, mai team. Le skill e gli insight condivisi contengono conoscenza operativa, non dati.
3. **Event-driven, durabilità per canale.** Nessun polling, nessun orchestratore centrale. Ogni canale evento ha la propria strategia di durabilità, scelta in base al consumer:

   | Canale | Implementazione | Durabilità | Test |
   |---|---|---|---|
   | `garuda:raw` (mata-garuda) | Redis Streams + consumer groups (XADD/XREADGROUP) | Stream MAXLEN ~100K, replay via `XGROUP READ` from `0` | `apps/mata-garuda/tests/test_redis_host_override.py` |
   | `practice_changed`, `client_changed`, `compliance_alert`, `war_room_event`, `intel_event`, `cognitive_event`, `federation_alert`, `cell_pulse_observed`, `measurer_event`, `crm_welcome_completed`, `asset_provenance` (CRM + cognitive + observatory) | PostgreSQL LISTEN/NOTIFY + `events_outbox` (migration 144) + DB triggers refactored a `outbox.publish` (migration 146) | Atomic insert nella stessa transaction del trigger; replay automatico al listener-reconnect via `_replay_outbox_on_reconnect`; consumer ack idempotente via `_outbox_id` injection | `apps/backend-rag/backend/tests/services/events/test_outbox.py` (16) + `test_outbox_callsite_integration.py` (12) + `test_event_bus_replay.py` (4) |
   | `lkpm_ingest_completed` (CRM, Python emitter only) | `EventBus.emit_pg` → `outbox.publish` (no DB trigger) | Stesso schema events_outbox | Same as above |
   | `wr2_status_change`, `partner.commission_changed` | NOT in `PG_CHANNEL_MAP`, separate consumers (es. `wr2_supervisor.py`) | Volatile by design (consumer mantiene proprio stato) | N/A — out of scope (vedi migration 146 header) |

   **Cicatrix riferiti:** `EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams` (2026-04-29) — RESOLVED via PR #342 + migration 144 + migration 146.

4. **Graceful degradation.** Se un organo non risponde, gli altri procedono. L'organismo e' resiliente per design, non per eccezione. **Invariante:** se un canale è down per >5min, ogni organo entra in `local_emergency_mode` con buffer locale; eventi prodotti durante il gap restano nell'outbox (per CRM/cognitive/observatory) o nello stream (per mata-garuda) e sono replayati al reconnect — vedi tabella Legge 3. **Audit trail:** ogni nuova promessa di durabilità in queste due leggi richiede un test corrispondente, enforced da `scripts/lint_symbiosis_promises.py` su CI.
5. **Zero come ultima istanza.** Le decisioni strutturali passano da Zero via Telegram. L'organismo propone, non decide.
6. **Sovranita' locale.** L'organismo vive sulle macchine di Zero (Pro 48GB, Air 16GB). La disconnessione da internet non e' un guasto — e' il suo stato naturale.
7. **Numeri prima.** Se non ha una metrica, non e' un miglioramento. Se non ha un benchmark before/after, non e' un'evoluzione. Se non ha codice che gira, non e' un'invenzione — e' un'ipotesi.

---

## DOVE SIAMO

| Pilastro      | Stato                                                                                                                        | Prossimo passo                                                                                                                                                                                                                                                     |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Riflessione   | Sprint 5 live (session-reflect → genome)                                                                                     | Cross-cell reflection aggregation                                                                                                                                                                                                                                  |
| Accumulazione | **v1 live su 2 organi + HGT** (2026-04-16)                                                                                   | Activate HGT on 3+ additional cells                                                                                                                                                                                                                                |
| Condivisione  | `cell:skills` + `cell:feedback` + `garuda:raw`                                                                               | Olimpo streams + KG gap routing                                                                                                                                                                                                                                    |
| Confronto     | Non implementato                                                                                                             | Consiglio v1 dopo che 3+ agenti condividono                                                                                                                                                                                                                        |
| Sogno         | Design hypothesis + decay scheduler (cron 02:30)                                                                             | Prototipo dopo Sprint 5, con metriche before/after                                                                                                                                                                                                                 |
| Curiosita'    | **v1 Curiosity Loop live** (2026-04-16): 56 gap topics, 3 tier dispatchers, CuriosityGrader, propose-only pipeline, 40 tests | First cycle on real gaps, Zero approve/reject flow                                                                                                                                                                                                                 |
| Misura        | v1 live (2026-04-16), parità Pro-Air schema v2 (2026-04-17)                                                                  | T0-Sistema (Air-collected, PG Fly): TTR=869, DO=2.21 · T0-Air(body): IA=1.0, FE=0.01 · **T0-Pro(bootstrap, 2026-04-17): IA=0.0009, FE=1.5548** — NON usare per claim comparativi; consolidamento 7d-median via claude_task `t0_pro_consolidate_7days` (2026-04-24) |
| Simbiosi      | Fase 1 (micromanagement)                                                                                                     | Evolve naturalmente con i pilastri precedenti                                                                                                                                                                                                                      |

---

## VADEMECUM

Per il _come_ pratico: leggi `VADEMECUM.md` (monorepo root).
Contiene checklist operative per ogni tipo di elemento: automazioni, agenti, router, migrazioni, deploy, sessioni Claude Code.

---

## RIFERIMENTI

- **Ricerca:** `~/Desktop/OSINT-Nexus/docs/RESEARCH_LANDSCAPE_2026.md` — 2 round, 4 fonti, numeri prima
- **Architettura tecnica:** `~/Desktop/OSINT-Nexus/docs/SYMBIOSIS_ARCHITECTURE.md` — schema, stream, query
- **Sprint 5:** `apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md` — 7 task TDD
- **Research agenti:** `apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md` — 6 pattern (Reflexion, Voyager, DGM)
