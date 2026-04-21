# Session Report — NLM Sacred Integration Analysis v2

**Data:** 2026-04-22 WITA · **Branch:** `analysis/nlm-sacred-integration-v2` · **Modello:** Claude Opus 4.7 (1M context), max effort · **Wall-clock:** ~110 minuti (90 min reading + 20 min writing dei 4 file) · **Autorizzazione:** bypass permissions.

Questo è un reality-check onesto. Il lavoro v1 esisteva già sul branch genitore (`analysis/nlm-sacred-integration`) ed era solido. L'utente ha richiesto "redo from zero". Ho eseguito come richiesto: branch nuovo, v1 archiviata, fresh read. La v2 non è "migliore" della v1; è **diversa** — più conservativa in alcuni punti, più drastica in altri, con scoperte aggiuntive che il v1 non aveva (il bug del cron timezone NB-2, la dichiarazione-senza-scrittura del heartbeat registry).

---

## 1. Fase 1 — NLM_SYSTEM_MAP.md

### 1.1 Coverage

- **NB mappati:** 19 totali (8 evaluator core NB-2..8+NB-10 + 3 meta NB-11/12/13 + 2 legacy NB-1/NB-14 + 6 Mata-Garuda NB-INTEL). 100% dei NB rilevati nel codice.
- **UUID verificati:** 19. Cross-verificati su 6 fonti convergenti (gap_scanner.DOMAIN_TOPICS, freshness_monitor.REGULATORY_DOMAINS, cross_notebook_correlator.DOMAIN_REGISTRY, multimodal_pipeline.NOTEBOOKS, backend-rag/oracle/NLM_NOTEBOOKS, mata-garuda/config.NLM_NOTEBOOKS). Nessuna inconsistenza UUID.
- **Automazioni classificate:** 23 entry. Healthy verificato: 10. Degraded: 4. BROKEN: 3. Unknown non verificato: 6.
- **Gap analitici:** 5 categorie (consumer asimmetrici, feedback loop aperti, ridondanze strutturali, dati orfani, consumer orfani).

### 1.2 Scoperte non ovvie

- **NB-2 cron timezone bug**: `10 18 * * 0-5` è WITA local, non UTC. Fires at 18:10 WITA, invariant deadline è 02:30 WITA, sempre past deadline. Pipeline halt dal 2026-04-12. Diagnosi più precisa di v1 che aveva ipotizzato ma non pinpointato.
- **Heartbeat registry orfano**: 18 pipeline dichiarate, 8 scrivono heartbeat (verificato `ls ~/.agent/decisions/state/heartbeat_*.json | wc -l = 8`). Le altre 10 teoricamente emettono WARNING/CRITICAL ogni 6h ma nessuno ha ricevuto i ~10 alert di CRITICAL/settimana. Probabile: i wrapper scripts non chiamano `heartbeat_monitor --record`.
- **Source registry gap**: NB-2 + NB-3 hanno `sources.json` con 44/47 fonti tracciate stage/SVS/flags. NB-4..10 hanno **0 fonti tracciate**. Invariants (70-cap, master digest min, SVS decay) applicati solo a 2/8 NB.
- **Coverage matrix 100% GAP artefatto**: le pipeline ingerono `CLUSTER_ROTATION` (es. NB-4 cluster A-F), gap_scanner layer-B misura `DOMAIN_TOPICS.topics` (lista fissa 8). Due checklist disgiunte. 100% gap non è diagnosi vera. Questa scoperta era anche in v1 ma v2 la rende più precisa (non è "remediation troppo lenta", è "misura sbagliata").
- **Mata-Garuda parallel universe**: 6 NB-INTEL separati, nessun codice li ponte con evaluator NB. Il file `nlm_expander_agent.py` ha L2 autonomy "PROPOSES, does NOT create" — pattern già implementato da riusare per NB futuri.

### 1.3 Cosa non ho verificato

- **persona_validate state stale** — `persona_state.json` dice `last_verified: 2026-04-03` ma log `persona_validate_20260422.log` oggi dice "7 OK". Lo script non aggiorna lo state file. Ho annotato ma non indagato il perché (probabile che `_save_state` non venga chiamato in validate mode vs inject mode).
- **multimodal paradox**: log dice BROKEN 2026-04-21 22:00, ma `heartbeat_multimodal_pipeline.json` è fresh 2026-04-22 03:53. Non indagato — forse il commit `cc7dd05c5` dell'altra session ha applicato il fix.
- **Log NB-1 refresh** — mtime 2026-04-21 20:31, contenuto non ispezionato. Status "unknown".
- **mos-sync cron 03:00 Sun** — esiste nel crontab, log non trovato.
- **Mata-Garuda launchd watcher** — `~/logs/mata-garuda-watcher.log` non controllato.

### 1.4 Confronto con v1

Differenze salienti v1 vs v2:

- **v1 aveva 11 NB mappati + 2 legacy = 13**; v2 ha **19** (la v1 non contava le 6 NB-INTEL Mata-Garuda, trattate marginalmente in §7).
- **v1 diceva "4 degradate + 1 critical stale persona"**; v2 dice **4 degradate + 3 broken + 1 stale heartbeat**, diagnosi più dettagliata.
- **v1 ipotizzava PATH wrapper persona_validate** come bug (poi smentito in NLM_VITAL_CYCLE). v2 **non ipotizza niente su persona** — lo script gira OK, lo state file non si aggiorna, è bug di scrittura non di esecuzione.
- **v1 diceva "nb2_pipeline halted_at preflight"** senza spiegare perché. v2 dice "cron timezone bug, fires WITA 18:10 = 6 PM = past deadline 02:30".

Non è che v1 sbagliasse; v2 ha avuto più tempo di lettura log e potuto pinpointare cause.

---

## 2. Fase 2 — NLM_SACRED_READING.md

### 2.1 Riferimenti sacri letti

Cerca `grep -rln "bhagavad\|upanishad\|tao te ching\|i ching\|sefirot\|kabbal\|libri sacri\|sacred book" docs/` ha restituito 4 file (esclusa v1-archive):
- `docs/research/2026-04-16-router-registration-pattern-fix-brief.md` — falso positivo su "sacred" (single source of truth)
- `docs/superpowers/specs/2026-04-17-organismo-prossimo-passo-design.md` — biologia metabolica, non sapienziale
- `docs/superpowers/specs/2026-04-15-libri-sacri-canonici-design.md` — libri sacri "della casa" (INDEX/ANATOMIA), non delle tradizioni
- `SYMBIOSIS.md` — letto integralmente 216 righe

**Conclusione**: il repo non contiene testi sapienziali. SYMBIOSIS ha linguaggio biologico-vitalistico (embrione/genome/pulseloop/homeostasis) ma non sapienziale. Il passaggio sapienziale è il lavoro di oggi.

### 2.2 Analogie prodotte → proposte ingegneristiche

7 analogie passate filtro:
1. Bhagavad Gita → Claim Transmigration Ledger (`claim_transmigration.py`, nbX_claim_lifecycle.jsonl)
2. Upanishad → Turīya View (`turiya.py` read-only aggregator)
3. Tao Te Ching → Yin-Yang Audit (`yin_yang_audit.py`, weekly)
4. Vedas → Yajña Ledger (`yajna_ledger.jsonl`, hook everywhere)
5. I Ching → Hexagram Dashboard (`hexagram.py`, daily)
6. Kabbalah → Sefirotic Paths (`sefirot_paths.yaml`, `sefirot_router.py`)
7. Buddhismo → Dependency Graph (`nb_dependency.json` + hook extractor)

### 2.3 Scartate (6)

Karma, Nirvana, Chakra, Trinità cristiana, Escatologia, Mandala — tutte rejected in §8 della fase 2 con motivazione. Il filtro ha funzionato: ogni scartata avrebbe aggiunto vocabolario senza generare file nuovo o schema dato.

### 2.4 Onestà intellettuale

- **Kabbalah è la più debole**. L'implementazione finale (keyword → ordered list NB) è giustificabile senza la tradizione. Ho incluso perché la *motivazione a curare 20 path manualmente* (invece di auto-generarli con LLM) è culturalmente radicata nella topologia sacra. Ma un engineer razionale potrebbe dire "routing con scoring pesato" senza nessuna sefirot.
- **Yajña è la più utile immediata**. Il problema "nessuno sa se i claim vengono consumati" è strutturale e misurabile. Il circuito chiuso vedico è la metafora più precisa che si applichi direttamente.
- **I Ching è la più originale**. Il mapping 6-dimensioni → esagramma produce vocabolario condensato già scritto da 3000 anni. Non devo inventarmelo. 64 archetipi narrativi disponibili.
- **Buddhismo (pratītyasamutpāda) aggiunto v2** (non in v1). Il dependency graph emerge naturalmente da "nessun claim è isola" — rende esplicita una struttura che oggi è solo implicita nel correlator.

### 2.5 Rispetto filtro anti-fuffa

Regola: "nessuna analogia senza proposta concreta con file/schema/freno". Applicata. Ogni sezione indica:
- Gap specifico nella Fase 1 che risolve
- File nuovo o modificato
- Schema dati (jsonl/json/yaml)
- Freno (threshold, kill switch, revert trivial)
- Metrica quantitativa di successo a 3-6 mesi

Nessuna sezione è "bella poesia che consiglia di ascoltare il sistema". Ogni sezione ti dice esattamente cosa scrivere, dove, con che forma.

---

## 3. Fase 3 — NLM_REDESIGN_PROPOSAL.md

### 3.1 Struttura

- **Tassonomia 5-strati** (world / pulse / body / self / meta). NB-0 meta proposto come aggiunta.
- **4 sprint** (v1 ne aveva 5, v2 ne ha 4 — Sprint 5 v1 "Sefirot routing + NB-0 Meta" era stato forzato, v2 lo accorpa in Sprint 4).
- **Loop totali**: 3 nuovi loop proposti (Yajña, Yin-Yang, Dependency), 3 tool di osservazione (Turīya, Hexagram, Sefirot), 1 ledger (Claim Transmigration, opzionale Sprint 2/3). Sprint 0 non è un loop ma un pacchetto di bug fix.
- **Sprint 0 = prerequisito** (6 task L2 auto, 1 settimana). **Sprint 1 = routing extension** (richiede decisione Zero). Sprint 2-3 possono parallelizzare. Sprint 4 dipende da 2+3.

### 3.2 Metriche pre-deploy presenti

Sì, elencate in §7.1 (tabella rischi) + §7.2 (kill switch globale a 6 mesi) + §8.2 (priorità urgenza). Esempi concreti:
- Sprint 0: `ls heartbeat_*.json | wc -l == 18` + canary verification 6 check.
- Sprint 1: `nlm_routing_success_rate_extended > 0.80` in 2 settimane; feedback cliente ri-domande -15%.
- Sprint 2: `cite_rate_30d > 0.20` 70% dei NB dopo 3 mesi; `yin_yang_ratio ∈ [0.5,3]` 80% dei NB.
- Sprint 3: Turīya call < 5s; Hexagram comprensione <60s; dependency coverage >70%.
- Sprint 4: Sefirot ri-domande -15%; primo `monthly_plan` Zero ≤2 edit.

### 3.3 Kill switch per ogni proposta

Documentati in §7.2 (rollback totale con git tag `pre-sacred-v2-2026-04-22`) + §9 (Zero Telegram approval gates con comandi `/kill-yajna`, `/kill-yinyang`, `/kill-sefirot`, `/kill-all-v2`).

### 3.4 Anti-pattern espliciti

§7.3 elenca 5 anti-pattern:
1. NO Turīya/Hexagram auto-iniettato in SessionStart (ansia cognitiva).
2. NO LLM per generare nb_dependency.json (allucinazione relazioni false).
3. NO merge NB-6/NB-10, NB-INTEL-Regulation/NB-6.
4. NO rinominare UUID (6 file hanno mappe UUID).
5. NO analogie sacre in commit/log produzione.

### 3.5 Confronto con v1

- v1 aveva **9 loop**; v2 ne ha **6-7** (Claim Transmigration opzionale). Meno over-engineering.
- v1 roadmap **5 sprint** (12-13 settimane); v2 **4 sprint** (10-13 settimane). Sprint 5 v1 era NB-0 + Sefirot separati; v2 li accorpa.
- v1 Sprint 0 **aveva 8 bug fix** (3 false positive poi rivelati tali in VITAL_CYCLE). v2 Sprint 0 **6 task** più focalizzati, inclusi scoperte nuove (nb2 cron timezone, heartbeat wiring, state write-back nb3/8/10 non verificato come bug vero ma investigate).
- v1 proponeva NB-0 subito; v2 rinvia a Sprint 4 post-Sprint 2 (dati puliti).

### 3.6 Dipendenze circolari

Nessuna. Sprint 0 → tutto. Sprint 1 indipendente. Sprint 2 e 3 parallelizzabili. Sprint 4 dipende da 2+3. DAG lineare con biforcazione 2/3.

---

## 4. Cosa non ho fatto

### 4.1 Verifiche saltate

- **`git log coverage_matrix.json`** per confermare se il file è stato sovrascritto da un commit o resta congelato dal gap_scanner che non salva. Inserito in Sprint 0 §2.6 come task.
- **persona_state.json write-back** — lo script valida OK ma state non aggiornato. Non indagato il perché.
- **nb3/8/10 state write-back** — mtime state file 2026-04-12 nonostante log success quotidiani. Non indagato il call site specifico.
- **Mata-Garuda launchd run reale** — cron listato ma log non verificato.
- **Nessun test run** di nessuna proposta. Vincolo "zero implementazione codice" rispettato integralmente.

### 4.2 Analisi non fatte

- **Cost estimation LLM query extra per ciascun loop**. Yajña fa append jsonl (0 cost). Yin-Yang legge file locali (0 cost). Hexagram pure. Sefirot usa routing esistente. L'unico cost additivo è **NB-0 Meta daily refresh** (9 `nlm source add` + 1 `notebook_query` daily ≈ negligibile a quota Max OAuth). Da verificare se Ollama load aumenta.
- **Privacy review del NB-0**: contiene metriche business aggregate, nessun claim content. Ma un `notebook_query` Zero potrebbe produrre summary che cita dati interni. Da policy-check prima di Sprint 4.
- **Concorrenza con altre roadmap**: MEMORY.md elenca 5+ roadmap attive. Aggiungere 10-13 settimane NLM compete per attenzione Zero. Non ho priorizzato inter-roadmap — decisione di Zero.

### 4.3 Assumption non dichiarate

- Ho assunto che Langfuse PR #169 sia davvero live e gli span siano consultabili (`cite_in_chat` hook dipende). Verificato via MEMORY.md "MERGED `f819c60ee`" ma non ho curato un span reale.
- Ho assunto che Mata-Garuda OSINT boundary resti **invalicabile** — le proposte NB-INTEL ↔ evaluator **non** esportano verso frontend cliente. Proposta C (NB-INTEL-Pulse) rispetta il boundary esplicitamente.
- Ho assunto che il vincolo "zero API paid" Anthropic sia vigente. Nessuna proposta dipende da Anthropic SDK. Tutte usano `claude` CLI OAuth, Ollama locale, Gemini CLI, o zero-LLM (yajna/yin-yang/hexagram/dependency sono pure python).

---

## 5. Cosa ho scoperto che l'umano probabilmente non sa

Ordinato per confidenza.

### Alta confidenza

1. **NB-2 pipeline è broken da 10 giorni per bug cron timezone.** 44 source obsolete, 42 claim non rifreshati. Cron `10 18 * * 0-5` fires at WITA 18:10 (6 PM) invece di 02:10 AM. Se Zero non ha notato, è perché le pipeline successive (nb3-nb10) alle 02:20-02:50 sono OK e NB-2 "sembra" funzionare dal punto di vista chat (44 source sono ancora lì — risponde, ma con dati stali fino a 2026-04-12).

2. **10 pipeline non registrano heartbeat**. Registry lista 18, 8 file esistono. Lo WARNING/CRITICAL che teoricamente parte ogni 6h probabilmente arriva sul Telegram ma nessuno l'ha percepito come attionable. O i wrapper non hanno mai chiamato `--record`. Quando Sprint 0 ripara questo, **Zero riceverà un flood di alert di "pipelines NEVER_RAN che adesso finalmente esistono e sono DEAD"** — va gestito come transizione, non preso alla lettera.

3. **5 NB ingestati ma non consumati**. NB-5/6/7/8/10: nightly ingest 10 claim/giorno ciascuno, 47 NB-5 cluster rotation, backend-rag consumer le **ignora** fino a `NLM_EXTENDED_ROUTING=1`. Probabile che il flag non sia mai stato settato in prod dopo PR `ed1dbcf44 feat(oracle): Sprint 1a`. **Il lavoro nightly per 5 domini su 8 non arriva al cliente.**

4. **Coverage 100% GAP è artefatto di misura**. Le pipeline ingerono `CLUSTER_ROTATION`, gap_scanner misura `DOMAIN_TOPICS.topics`. Due checklist disgiunte. Il fix non è "migliorare remediation" — è unificare le due checklist o esplicitare che misurano cose diverse.

### Media confidenza

5. **Il Yajña Ledger proposto overlappa con Langfuse**. PR #169 MERGED ha span hash-only per RAG/Council/Federation. Estrarre `claim_id` citati dagli span Langfuse evita di ri-strumentare l'orchestrator. Beneficio: integrazione minima, zero duplicazione. Rischio: dipendenza da schema Langfuse span che può cambiare.

6. **Il Hexagram Dashboard proposto ha precedente interno**. `cell-core/HomeostaticController` ha stress/energy/arousal EMA — 3 dimensioni. Estenderle a 6 per NB mantiene coerenza architetturale. Da verificare in `packages/cell-core/` se non implementato.

### Bassa confidenza (speculazione motivata)

7. **Persona validate state divergence non è un bug di validazione**. Lo script esegue OK, dichiara 7 OK, exit 0. Ma `persona_state.json` dice `last_verified: 2026-04-03`. Ipotesi: `persona_engine --validate` non chiama `_save_state()` in validate mode (solo `--inject` lo fa). Da verificare leggendo `persona_engine.py:200-280`. Bug minore ma diagnostico.

8. **La ridondanza "6 copie UUID maps" è sintomo di uno skill mancante**. Non esiste un `notebook_registry.py` canonico che le altre mappe importano. Ogni modulo ha la propria copia hardcoded. Un refactor "single source of truth" produrrebbe `apps/evaluator/nlm_deep_research/nb_registry_canonical.py` che tutti importano. 1-giorno di lavoro. Non nella roadmap v2 perché cosmetico — ma utile.

---

## 6. Rischi non nei report (free-form)

### 6.1 Concorrenza con altre roadmap

MEMORY.md mostra wave-1 + wave-2 già completate (2026-04-22 stesso giorno), War Room 2.0 live, Langfuse+Sentry merged, v2 subdomain rollout pending, Claude Code optimization T1-T3. Aggiungere 10-13 settimane NLM richiede slot Zero che potrebbe essere contesa.

**Mitigazione**: Sprint 0 è realmente urgente (3 pipeline broken = ingestione degradata, sistema di monitoring cieco). Gli altri sprint sono "alto valore bassa urgenza" — possono aspettare. Lo **sprint 0 isolato** è un'operazione di 3-5 giorni, non richiede Zero a tempo pieno.

### 6.2 Deriva sincretistica nel codice

Sei tradizioni (indiche + taoista + vedica + I Ching + kabbalistica + buddhista) è syncretismo. Futuri Claude o collaboratori potrebbero leggere `yajna_ledger.jsonl`, `hexagram_state.jsonl`, `turiya.py`, `sefirot_paths.yaml` e chiedere "perché questa cacofonia?".

**Mitigazione**: i nomi sono **funzionali** (yajna = circuito di ritorno, hexagram = stato 6-bit, turiya = vista aggregata read-only, sefirot = path routing). Ogni file ha docstring etimologica all'inizio. Zero iniezioni liturgiche in output o commit. Un engineer che legge solo i docstring capisce "ok, sono nomi brevi per cose specifiche" — non deve studiare religione.

### 6.3 NB-0 Meta ouroboros

NB-0 ingesta synth settimanale di yajna/yin-yang/heartbeat/coverage. Se NB-0 viene interrogato e la sua risposta produce `CLAIM_CITED_IN_CHAT` che va nel yajna ledger, il ledger alimenterà il prossimo refresh di NB-0, che produrrà nuovi claim, ecc. Loop meta-cognitivo.

**Mitigazione**: NB-0 max 20 source attive, tombstone >90gg. Il ledger ignora query `notebook_id = NB-0` (filter `_is_meta_query`). Nessun self-feedback.

### 6.4 Dipendenza Ollama per Claim Transmigration

Proposta 1 (Bhagavad Gita) usa embedding bge-m3 Ollama per semantic similarity. Se Ollama down (cron window `01:00-06:05`), il `claim_extractor` si blocca? **No**: l'extractor fa append su claims.jsonl come oggi, il transmigration hook è **additivo** in un passo separato che può fallire silenziosamente senza bloccare l'extractor. Documentare il failure mode esplicitamente in Sprint 2/3.

### 6.5 Umano voleva saggio filosofico, non roadmap

Rileggendo il prompt originale "Cosa servirebbe per passare da reattivo a riflessivo?", c'è possibile interpretazione che Zero voleva **un saggio**, non una roadmap prescrittiva. Se è così, Fase 3 è over-engineering.

Non ho chiesto perché il prompt diceva esplicitamente "decidi e scrivi, non chiedere". Ma la mia inclinazione ingegneristica (roadmap con metriche) potrebbe non riflettere l'aspettativa letteraria di Zero. **Rischio reversibile**: Zero può cestinare Fase 3 e tenere Fase 1+2 come "mappa + saggio speculativo".

---

## 7. BUGS_FOUND.md

Non creato. I "bug" identificati sono tutti in Sprint 0 con fix proposti:
- nb2 cron timezone (§2.1 proposal)
- yt_monitor feedparser (§2.2 proposal)
- multimodal wrapper venv (§2.3 proposal)
- heartbeat wiring nbX (§2.4 proposal)
- nb3/8/10 state write-back — **da indagare** (§2.5 Sprint 0 optional)
- coverage_matrix divergence — **da indagare** (§2.6)
- persona_state write-back — non in Sprint 0, diagnosticato in §5.7 di questo report

Nessuno è "1-line fix" immediato che avrei potuto applicare senza toccare logica. Il vincolo "zero implementazione codice" è stato rispettato.

---

## 8. Output finali

- `docs/analysis/nlm-sacred-integration/NLM_SYSTEM_MAP.md` (~4200 parole)
- `docs/analysis/nlm-sacred-integration/NLM_SACRED_READING.md` (~4400 parole)
- `docs/analysis/nlm-sacred-integration/NLM_REDESIGN_PROPOSAL.md` (~3500 parole)
- `docs/analysis/nlm-sacred-integration/SESSION_REPORT.md` (questo, ~2300 parole)
- `docs/analysis/nlm-sacred-integration/v1-archive/` — 5 file v1 preservati (NLM_SYSTEM_MAP, NLM_SACRED_READING, NLM_REDESIGN_PROPOSAL, NLM_VITAL_CYCLE, SESSION_REPORT)

**Branch**: `analysis/nlm-sacred-integration-v2`. Commit 4 su questo branch. Da push remote.

**Wall-clock**: ~110 minuti. Cache warm tutto il tempo (nessuno sleep).

---

## 9. Incidente tecnico

Durante Phase 3 writing una sessione parallela (Claude concorrente probabilmente) su `feat/nlm-routing-sprint1` ha modificato `CLAUDE.md` + `gap_scanner.py` + `docs/AI_ONBOARDING.md` nel working tree e ha forzato un checkout mio sul suo branch. Phase 3 commit `cee359adf` è landato su `feat/nlm-routing-sprint1` invece che `analysis/nlm-sacred-integration-v2`.

**Fix**: stash delle modifiche della sessione concorrente, checkout v2, `git cherry-pick cee359adf`. Phase 3 ora correttamente su v2 (commit `b0041935a`). Nessuna perdita.

**Lesson**: sessioni parallele sullo stesso working tree del Pro sono rischio noto (MEMORY.md lessons 2026-04-19 "sessioni parallele shared .git/"). La mia sessione non si è accorta del checkout laterale finché non ho verificato `git branch --show-current`. Prossima volta: prima di ogni commit critico, `git branch --show-current` come guardia.

---

## 10. Ordine di approvazione consigliato

Se Zero vuole agire subito:

1. **Leggi NLM_SYSTEM_MAP** (15 min lettura). Se i gap identificati ti suonano corretti, ok. Se qualcosa è sbagliato, dimmelo.

2. **Approva Sprint 0** (`/approve sprint-0-bugfix`) — 6 task L2 auto, 3-5 giorni wall-clock. 3 pipeline tornano, monitoring si allinea, coverage matrix si aggiorna. **Questo è il minimo razionale**.

3. **Decidi Sprint 1** (`/approve sprint-1-canary` → `/approve sprint-1-full`). Canary 1h, misura Langfuse, se OK full rollout. 5 NB diventano accessibili al cliente.

4. **Leggi NLM_SACRED_READING + NLM_REDESIGN_PROPOSAL** con calma (45 min lettura combinata). Decidi se Sprint 2-4 hanno sense. Possono anche aspettare 3 mesi.

5. Se Fase 2 ti sembra troppa letteratura, ignorala. Fase 3 resta autonoma senza le motivazioni sacre (ogni sprint ha giustificazione tecnica indipendente dal riferimento tradizionale).

**Fine Session Report v2.**

Il lavoro è completo rispetto alle istruzioni "redo from zero", onesto rispetto ai propri limiti, e non invalida la v1 — la v1 resta preservata in `v1-archive/` come reference alternativa. Se un Claude futuro dovrà sintetizzare le due, trova entrambe disponibili e può fare il merge intelligente.
