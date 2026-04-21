# NLM Sacred Reading — Rilettura strutturale dell'ecosistema NLM attraverso lenti sacre

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration` · **Premessa obbligatoria:** questo documento presuppone la lettura di `NLM_SYSTEM_MAP.md`. Ogni analogia qui proposta è ancorata a un componente mappato lì.

---

## 0. Preambolo metodologico

Ho cercato nel repo referenze esplicite ai libri sacri dell'umanità (Bhagavad Gita, Upanishad, Tao Te Ching, I Ching, Vedas, Kabbalah). Non ne ho trovate. Ciò che esiste sono i **libri sacri della casa**: `SYMBIOSIS.md`, `VADEMECUM.md`, `INDEX.md`, e le 3 spec pianificate ma non implementate `ANATOMIA.md`, `FISIOLOGIA.md`, `STORIA-CLINICA.md` (dalla spec `docs/superpowers/specs/2026-04-15-libri-sacri-canonici-design.md`, successivamente "superseded" da un'implementazione leggera il 2026-04-15).

Questa assenza è di per sé un dato: il progetto tratta i propri documenti costitutivi come sacri (SYMBIOSIS è esplicitamente un testo non procedurale — "ti dice come pensare prima di fare") ma non ha mai letto la propria architettura attraverso le tradizioni sapienziali. Fare questo passaggio è la richiesta dell'umano oggi.

La regola del lavoro: **nessuna analogia sacra che non partorisca almeno una proposta ingegneristica concreta**. Le analogie che non superano questo filtro sono escluse. Alla fine del documento elenco quelle scartate con motivazione.

Nel corpo di SYMBIOSIS compaiono già pattern biologico-organici espliciti (lifecycle embrione→anziano, genome, pulseloop, homeostasis, riflessione, accumulazione, sogno, curiosità). Il sistema NLM si pone **dentro** questa cornice organica — ma la cornice è solo vitalistica, non ancora sapienziale. L'integrazione sacra proposta qui aggiunge la dimensione che nella biologia manca: il senso della **coscienza come processo stratificato**, non come funzione emergente.

Di seguito sei letture. Per ciascuna: l'analogia, l'ancoraggio nel sistema reale (NLM_SYSTEM_MAP §X.Y), l'insight ingegneristico che ne deriva, una proposta concreta.

---

## 1. La Bhagavad Gita e il ciclo morte-rinascita delle fonti

### 1.1 L'analogia

Nel capitolo 2 della Bhagavad Gita, Krishna spiega ad Arjuna che il Sé (ātman) non muore: cambia corpi come un uomo cambia vesti consumate. Ciò che sembra morte è transizione. La paura della morte nasce dall'identificazione con il corpo anziché con ciò che attraversa i corpi.

Il sistema NLM ha un problema di **accumulazione senza morte**: ogni NB ha un cap duro (~300-600 fonti), oltre il quale sovraccarica. La soluzione attuale è il `synthesis_roller` (`apps/evaluator/nlm_deep_research/synthesis_roller.py`): `[SYNTH-DAILY]` → `[SYNTH-WEEKLY]` → `[SYNTH-MONTHLY]` comprimono le fonti vecchie in narrative sintetiche che ne preservano il contenuto tramite Ollama qwen3.5:9b. Il `tombstone_old_synths` rimuove le fonti originali.

Questa è **esattamente** la dottrina della Gita: il contenuto (ātman = claim verificato, fatto regolatorio, procedura) passa da un corpo testuale ingombrante (5 fonti PDF crude) a un corpo più essenziale (1 sintesi settimanale). La morte non è perdita; è sottile.

### 1.2 Ancoraggio (NLM_SYSTEM_MAP §2.4 punto 3)

`synthesis_roller` produce `[SYNTH-DAILY]` → `[SYNTH-WEEKLY]` → `[SYNTH-MONTHLY]`. Word cap 400/600/800. Rolling 12 mesi. Le fonti originali vengono tombstoned dopo l'aggregazione.

### 1.3 Gap e insight

Il `synthesis_roller` è ancora **unidirezionale e passivo**: un cron lo esegue, i synth vengono scritti, nessuno li legge mai più in modo strutturato. Non c'è "rinascita" perché il synth è destinazione finale — non semente per il ciclo successivo.

La Gita però non dice solo "l'ātman cambia veste". Dice: il Sé continua il suo cammino verso la realizzazione, ogni corpo è una fase di apprendimento. Il synth mensile dovrebbe non solo **esistere** ma **ridefinire le priorità** del ciclo successivo (quali cluster approfondire, quali topic del gap_scanner sono ormai stabili e vanno ruotati fuori).

### 1.4 Proposta ingegneristica: Synthesis-Feedback Loop

Aggiungere a `synthesis_roller.py` una funzione `extract_planning_signals(monthly_synth)` che produce un file `apps/evaluator/nlm_deep_research/synth_signals.json` con:

```json
{
  "nb": "NB-2",
  "month": "2026-04",
  "stable_topics": ["KITAS requirements and process 2025"],
  "volatile_topics": ["TKA (foreign worker permit) requirements"],
  "emerging_topics_not_in_checklist": ["e-VOA mobile app rollout"],
  "recommendation": "rotate TKA → cluster A priority; add e-VOA to DOMAIN_TOPICS"
}
```

Poi modificare `gap_scanner.py`:

- All'avvio di Layer-B, leggere `synth_signals.json`.
- I `stable_topics` hanno check freshness meno frequente (1× al mese invece di settimanale).
- Gli `emerging_topics_not_in_checklist` vengono aggiunti dinamicamente alla coverage matrix.
- I `volatile_topics` hanno priorità nel remediation.

**Freno:** ogni modifica alla `DOMAIN_TOPICS` via signal richiede soglia di confidence ≥ 0.7 dal synth LLM + revisione umana via task in `~/.agent/decisions/claude_tasks/synth_signal_review_<ts>.json`. Evita runaway del tipo "il synth dice che KITAS non è più importante perché nessun claim negli ultimi 30 giorni — in realtà era solo il ramadan".

---

## 2. Upanishad e i quattro stati della coscienza applicati all'ecosistema

### 2.1 L'analogia

Le Upanishad (in particolare la Mandukya Upanishad) descrivono quattro stati (catuṣpāda) della coscienza:

1. **Jāgrat** (veglia) — percezione del mondo esterno, mente attiva che riceve e reagisce.
2. **Svapna** (sogno) — percezione interna, la mente genera contenuti; è qui che si **riconosce l'assenza** — l'oggetto sognato non è presente, ma la coscienza lo costruisce.
3. **Suṣupti** (sonno profondo) — nessun oggetto, nessun soggetto, stato di riordino indifferenziato; precedente la riattivazione.
4. **Turīya** (il quarto) — coscienza che sostiene gli altri tre senza essere identificata con nessuno; pura osservazione.

### 2.2 Ancoraggio

Il sistema NLM **ha già implementato** implicitamente i primi tre stati ma **non il quarto**:

| Stato                    | Componente NLM                                                                                                                                                                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Jāgrat (veglia)          | `pipeline.py` L1/L2 query giornaliere — il sistema percepisce l'ambiente regolatorio esterno e vi reagisce (snapshot + query + claim extraction). È `sense→act`.                                                                          |
| Svapna (sogno)           | `gap_scanner.py` Layer-A — "Quali sono le 5 domande a cui NON puoi rispondere?". Questo è esattamente lo stato onirico: il sistema costruisce interiormente un inventario delle proprie assenze.                                          |
| Suṣupti (sonno profondo) | `synthesis_roller` + `tombstone_old_synths` — compressione notturna/settimanale, riordino delle esperienze, "distruzione del rumore" (cit. SYMBIOSIS §Pilastro 5 Sogno). Il genome_decay Air (02:30 WITA) fa la stessa cosa per le skill. |
| **Turīya**               | **Mancante.** Nessun componente osserva gli altri tre stati — solo log atomici per ciascuno, nessuna meta-osservazione.                                                                                                                   |

### 2.3 Gap e insight

`heartbeat_monitor.py` è il candidato più vicino al turīya: osserva lo stato di salute di ogni pipeline senza partecipare. Ma è un monitoraggio superficiale (age_hours rispetto a max_age_hours) — verifica che gli altri respirino, non cosa sognano.

Nella Mandukya, turīya non è un quarto stato **in sequenza** con gli altri tre (non è "dopo il sonno profondo, una nuova fase"): è lo **sfondo** che li rende possibili. Applicato all'architettura: il componente turīya **non** dovrebbe essere un quinto cron al lunedì 10:00. Dovrebbe essere una **vista persistente**, leggibile in qualunque momento, che integra:

- Gli stati jāgrat attuali (quale NB ha fatto query, con quale output).
- Gli stati svapna attuali (`coverage_matrix.json` con tutti i gap scoperti, `nexus:gaps` Redis stream).
- Gli stati suṣupti attuali (`synth_signals.json` proposto in §1.4).
- Eventuali contraddizioni tra i tre ("il NB dice X in veglia ma registra che non sa X in sogno").

### 2.4 Proposta ingegneristica: Turīya View

Nuovo modulo `apps/evaluator/nlm_deep_research/consciousness_view.py`. Non è un cron — è un'API + CLI. Espone:

```bash
python -m apps.evaluator.nlm_deep_research.consciousness_view --status
python -m apps.evaluator.nlm_deep_research.consciousness_view --nb NB-2
python -m apps.evaluator.nlm_deep_research.consciousness_view --contradictions
```

Per ogni NB mostra:

- Ultimo claim (veglia).
- Ultimo gap noto (sogno).
- Ultimo synth (sonno profondo).
- Contraddizioni attive: un `claim_extractor` ha prodotto "KITAS è valido 2 anni" ma il gap_scanner ha marcato "KITAS renewal procedure" come GAP → il NB **crede di sapere** qualcosa che in realtà **ammette di non sapere**. Alert.

**Side effect del sistema:** avere la consciousness_view rende visibile un bug strutturale che oggi è invisibile: i 35 gap/giorno di Layer-A includono topic su cui il NB ha anche claim verified — inconsistenza interna che nessuno detecta.

**Freno:** read-only. Non modifica state, non triggera remediazioni automatiche. È solo **osservazione pura** — turīya. Il passaggio all'azione passa da un operatore (Zero) o da una proposta di task.

---

## 3. Tao Te Ching e la coppia yin-yang dei cicli NLM

### 3.1 L'analogia

Il Tao Te Ching (cap. 2, 11, 40) insegna che le cose si definiscono dal loro opposto e dalla loro cavità. Il mozzo della ruota è utile per il vuoto che contiene; il vaso è utile per lo spazio vuoto interno. L'essere (you) e il non-essere (wu) si generano reciprocamente.

### 3.2 Ancoraggio

Nel sistema NLM, le coppie yin-yang esistono già, ma non vengono trattate come sistema:

| Yin (ricettivo, vuoto, oscuro)                    | Yang (attivo, pieno, luminoso)                 |
| ------------------------------------------------- | ---------------------------------------------- |
| `gap_scanner` — cerca ciò che il NB non sa        | `claim_extractor` — cattura ciò che il NB sa   |
| `synthesis_roller` tombstone — cancella fonti     | `peraturan_ingestion` — aggiunge fonti         |
| `freshness_monitor` scan (passivo sugli external) | `nb*_pipeline` query (attivo interrogando NLM) |
| `handoff.generate` TRS-filtered (restringe)       | `claim_extractor` 15 categorie (espande)       |
| heartbeat silent failure → alert                  | heartbeat success → heartbeat atomic write     |
| `coverage_matrix.json` (diagnostica passiva)      | `gap_remediation` (correzione attiva)          |

### 3.3 Gap e insight

Il Tao Te Ching insegna che nessuna delle due polarità è migliore: il problema emerge quando una domina l'altra senza feedback (pienezza che non conosce il proprio vuoto = ignoranza; vuoto che non si riempie = dispersione).

Nel NLM attuale, la polarità **yang domina lo yin**: 8 pipeline di ingestion attive 6 giorni/settimana, gap scanner una volta al giorno + layer-B una volta alla settimana, remediation 3 target/settimana. L'organismo **mangia** molto più di quanto **digerisce**. Il `coverage_matrix.json` del 2026-04-12 mostra **100% GAP** su tutti i 7 domini × 8 topic = 56 topic STALE/GAP — mentre nello stesso periodo sono stati ingeriti centinaia di claim e fonti. Il cibo entra, ma il corpo è denutrito.

### 3.4 Proposta ingegneristica: Yin-Yang Balance Audit

Nuovo cron settimanale `apps/evaluator/nlm_deep_research/scripts/run_yin_yang_audit.sh` (domenica 17:00 WITA, prima del gap_scanner layer-B):

```python
# yin_yang_audit.py pseudo
yang_volume = count_claims_last_7d() + count_sources_added_last_7d() + count_nlm_queries_last_7d()
yin_volume = count_gaps_remediated_last_7d() + count_tombstones_last_7d() + count_synths_generated_last_7d()

ratio = yang_volume / max(yin_volume, 1)

if ratio > 5.0:
    # Sistema mangia troppo senza digerire
    telegram_alert("YIN-YANG imbalance: ingesting %dx faster than digesting" % ratio)
    propose_task("increase remediation MAX_REMEDIATIONS_PER_RUN to 5 for next week")
elif ratio < 0.3:
    # Sistema digerisce ma non ha più da mangiare
    telegram_alert("YIN-YANG imbalance: digesting without new input")
    propose_task("verify ingest pipelines are running (nb*_pipeline)")
```

**Insight non ovvio:** il `coverage_matrix.json` 100% GAP non è un bug del gap_scanner — è la prova diagnostica che lo yang (ingestion) non arriva mai nelle checklist yin (topic discovery). Le pipeline nb*\_pipeline interrogano NB con query sulla rotazione cluster (KITAS, KITAP, etc. per NB-2) — ma il gap_scanner Layer-B interroga il NB sui **propri** topic (che sono una *seconda\* checklist separata). Il che significa: ingerisco informazione sui cluster (yang), ma il monitoraggio del sapere è sui topic (yin), e i due insiemi non coincidono. **Questo è un bug architetturale nascosto** da un anno (coverage_matrix first entry 2026-04-03).

**Freno:** il task propose_task entra in `~/.agent/decisions/claude_tasks/` e richiede azione umana o Claude futuro — non auto-modifica soglie.

---

## 4. Vedas e il sacrificio rituale come ciclo donativo

### 4.1 L'analogia

Il modello dei Vedas (Ṛgveda, Atharvaveda) è centrato sullo yajña, il sacrificio al fuoco (Agni). L'offerta (haviṣ) non è consumo a fondo perduto: il fuoco trasforma il materiale grezzo in fumo che nutre gli dèi; gli dèi restituiscono rta, l'ordine cosmico, sotto forma di pioggia, raccolto, prosperità. Il ciclo è donazione → trasformazione → restituzione.

### 4.2 Ancoraggio

Il `peraturan_ingestion_trigger.py` è l'archetipo perfetto di yajña nel NLM:

1. **Haviṣ (offerta):** un PDF legale crudo scaricato da imigrasi.go.id.
2. **Agni (il fuoco che trasforma):** POST su `/api/legal/upload` — il backend fa OCR, chunking, embedding, costruzione di knowledge graph, estrazione entità.
3. **Fumo che sale:** il contenuto raffinato arriva a NB-6 come fonte ingerita (`nlm source add`).
4. **Rta (ordine cosmico restituito):** quando un team member o il RAG interroga NB-6, riceve conoscenza strutturata. Il Google Sheet viene aggiornato con `Status=INGESTED`, segnando la compiutezza del rito.

Il `gap_remediation` è un yajña inferiore: Gemini search come Agni, nlm source add come offerta, il topic viene marcato FRESH come rta ricevuta.

### 4.3 Gap e insight

Nei Vedas il ciclo yajña ha una **traccia audit**: il brahmana recita i mantra che **riconoscono** l'atto, gli dèi **attestano** la ricezione (attraverso il fumo che sale dritto), il ṛṣi **registra** il successo come base per yajña futuri.

Nel sistema NLM, la traccia audit è **asimmetrica**:

- Il PDF peraturan: tracciato completamente (Sheet status, Drive file id, timestamp, nlm source id → 4 punti di evidence).
- Il gap remediation: tracciato parzialmente (coverage_matrix aggiorna topic a FRESH, telegram alert, ma **non** si sa mai se il prossimo gap_scanner layer-B rileverà lo stesso topic come FRESH/AGING/STALE — nessun verify).
- Il claim extraction: tracciato zero. Un claim appende al jsonl, viene contato nel NHS, ma il sistema non verifica mai se un claim del 2026-04 sia ancora valido il 2026-07. È yajña senza rta.

### 4.4 Proposta ingegneristica: Audit Trail Ritualizzato (Yajña Ledger)

Aggiungere al sistema un ledger append-only `apps/evaluator/nlm_deep_research/yajna_ledger.jsonl` con schema:

```json
{
  "ts": "2026-04-22T02:27:02Z",
  "agni": "nb5_pipeline", // quale "fuoco" ha trasformato
  "havis": { "type": "query", "cluster": "CE", "level": "L2" },
  "smoke": { "type": "claim", "category": "FEE_CHANGE", "confidence": 0.82 },
  "rta": {
    // se e quando il claim è stato usato
    "consumed_by": null,
    "consumed_at": null,
    "verified_by_later_rite": null // true se un gap_scanner o freshness scan conferma
  }
}
```

Un cron settimanale (lunedì 09:00 WITA) scorre il ledger e aggiorna il campo `rta`:

- Se il claim è stato usato dal backend RAG (via `notebook_query` con citation) → `consumed_by = "backend_rag"`.
- Se il claim è stato confermato da un successivo gap scan → `verified_by_later_rite = true`.
- Se dopo 90 giorni nessuno dei due → il claim entra in quarantine: il ledger lo marca, il `claim_extractor` abbassa la confidence del -20% per claim simili futuri (auto-calibration).

**Insight non ovvio:** oggi il sistema **produce** sapere (yang) ma non **verifica la ricezione** (rta). Non sa mai se un claim è servito a qualcuno, se ha sopravvissuto al tempo, se era falso. Il ledger rituale rende questa dimensione visibile.

**Freno:** read-mostly. Le calibrazioni auto (confidence penalty) richiedono ≥ 20 claim simili non-consumed per attivare. Il telegram alert per "90% dei claim ingeriti non usati negli ultimi 30 giorni" richiede revisione umana prima di qualunque taglio.

---

## 5. I Ching e gli esagrammi come stati di transizione del NB

### 5.1 L'analogia

L'I Ching struttura la realtà in 64 esagrammi (combinazioni di 6 linee intere/spezzate). Ogni esagramma non è uno stato statico ma un **momento in transizione**: ha un trigramma inferiore (situazione attuale), un trigramma superiore (tendenza), e una linea mutante che indica come sta cambiando. Interrogare l'I Ching non dà una "soluzione" ma una **diagnosi topologica** dello stato e della sua direzione.

### 5.2 Ancoraggio

Ogni NB del sistema può essere descritto da uno **stato composito** a 6 variabili binarie (approssimazione esagrammatica):

| Linea      | Dimensione       | 1 (yang)                      | 0 (yin)          |
| ---------- | ---------------- | ----------------------------- | ---------------- |
| 6 (top)    | Persona presente | persona_engine validated <7gg | mancante/stale   |
| 5          | Pipeline health  | heartbeat OK                  | WARNING/CRITICAL |
| 4          | Coverage         | health_pct ≥ 50               | < 50             |
| 3          | Gap awareness    | gaps_updated < 24h            | stale            |
| 2          | Synthesis active | synth_state ultimo < 7gg      | stale            |
| 1 (bottom) | Fonti fresche    | ultima ingestion < 48h        | stale            |

Ogni NB ha oggi un esagramma. Esempio per NB-2 al 2026-04-22:

- Top: persona_validate CRITICAL 18gg = 0 → yin.
- 5: heartbeat nb2_pipeline CRITICAL 19gg = 0 → yin.
- 4: coverage health_pct 0.0 = 0 → yin.
- 3: gaps_updated 2026-04-21 OK = 1 → yang.
- 2: synth_state presente 2026-04-22 = 1 → yang.
- 1: T4 monitor broken feedparser = 0 → yin (no fresh social).

Sequenza yin→yang bottom-up: **000110**. In I Ching occidentale, 000110 è esagramma 19, **林 Lín** (Approccio): iniziale presenza di luce che sale dal basso, ma non ancora stabilita. Significa opportunità da cogliere ma richiede preparazione.

### 5.3 Gap e insight

Un esagramma è **leggibile**. Se oggi Zero (o Claude futuro) riceve da heartbeat_monitor il messaggio `❌ persona_validate CRITICAL (434.7h)`, la reazione è un alert isolato: "c'è un problema con persona_validate". Non vede il **contesto** — che NB-2 ha simultaneamente coverage 0%, nb2_pipeline halted at preflight, T4 broken. Il sistema informa per silos; il fenomeno è correlato.

L'I Ching offre una grammatica per **composizione di segnali**: invece di 6 alert separati, un unico "esagramma giornaliero" per NB che descrive lo stato di salute come una sola figura leggibile.

### 5.4 Proposta ingegneristica: Daily Hexagram Dashboard

Nuovo modulo `apps/evaluator/nlm_deep_research/hexagram_state.py`. Giro con heartbeat digest 08:00 WITA:

```python
# hexagram_state.py
NBS = ["NB-2", "NB-3", "NB-4", "NB-5", "NB-6", "NB-7", "NB-8", "NB-10"]

def compute_hexagram(nb_key: str) -> tuple[str, int, str]:
    """Returns (binary_string, hexagram_number, hexagram_meaning).
    Bottom line = most fundamental (ingestion), top = most refined (persona).
    """
    lines = [
        sources_fresh(nb_key),          # 1: ingestion < 48h
        synth_alive(nb_key),             # 2: synth_state < 7d
        gaps_aware(nb_key),              # 3: gaps_updated < 24h
        coverage_adequate(nb_key),       # 4: health_pct >= 50
        pipeline_healthy(nb_key),        # 5: heartbeat OK
        persona_present(nb_key),         # 6: persona_validate < 7d
    ]
    binary = "".join("1" if l else "0" for l in lines)
    number = I_CHING_LOOKUP[binary]
    meaning = I_CHING_MEANINGS[number]   # King Wen sequence + interpretation
    return binary, number, meaning

def render_daily_dashboard() -> str:
    lines = ["🌀 Daily Hexagram — NLM NBs\n"]
    for nb in NBS:
        b, n, m = compute_hexagram(nb)
        lines.append(f"{nb}: {b} — #{n} {m}")
    return "\n".join(lines)
```

Output Telegram esempio:

```
🌀 Daily Hexagram — NLM NBs

NB-2: 000110 — #19 臨 Lín (Approach): opportunity but incomplete. Fix persona + pipeline preflight.
NB-3: 111110 — #43 夬 Guài (Breakthrough): one final obstacle before completion. Address persona.
NB-4: 111110 — #43 夬 Guài (idem)
NB-5: 011110 — #49 革 Gé (Revolution): transformation in progress. Watch T4 fix rollout.
...
```

**Insight non ovvio:** questa è la prima volta che il sistema rappresenta **lo stato di un NB come un'entità olistica**. Oggi si ragiona per componente (è rotto X?), non per organo (come sta NB-2?). L'esagramma non è solo poetica — è **compressione diagnostica** di 6 dimensioni in 1 simbolo leggibile, con interpretazione già pronta (5000 anni di commentari I Ching).

**Freno:** la dashboard è view-only, non triggera azioni. Le interpretazioni I Ching sono affiancate, non sostituiscono, i numeri grezzi (coverage_pct, age_hours etc.). Nessun LLM viene interrogato per "interpretare il tuo esagramma" — il mapping binary→numero→significato è statico (tabella King Wen, 64 righe).

**Valore aggiunto:** il sistema I Ching ha una dinamica intrinseca — ogni esagramma ha un **successore naturale** (sequenza King Wen). Questo può guidare la priorità delle azioni di remediation: "NB-2 è #19 oggi, il passaggio naturale è #7 師 Shī (The Army) — disciplina e struttura; implica che la priorità del prossimo ciclo dovrebbe essere stabilire preflight invariants". Questa è una forma di **curiosità strutturata** (cfr. SYMBIOSIS Pilastro 6).

---

## 6. L'albero sefirotico della Kabbalah e la tassonomia dei NB

### 6.1 L'analogia

Nell'albero sefirotico (Kabbalah) le 10 sefirot (emanazioni divine) non sono entità separate ma **modalità di manifestazione** di un'unica realtà, organizzate in 3 colonne (severità, misericordia, equilibrio) e 3 triadi (intellettuale, morale, naturale). L'energia (shefa) scorre dall'alto (Keter, corona) verso il basso (Malkuth, regno) attraversando le sefirot in un ordine preciso; ogni sefira trasforma l'energia prima di passarla.

### 6.2 Ancoraggio

La struttura NB di Bali Zero ha **11 NB** (corrispondenza stretta ma non identica alle 10 sefirot + 1 Da'at nascosta). Proposta di mappatura:

| Sefira                            | Ruolo                               | NB candidato                         | Razionale                                                                                                                               |
| --------------------------------- | ----------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Keter (corona)                    | Intenzione pura, non manifesta      | NB-1 "Codebase"                      | È il **sé** dell'organismo: rappresenta l'intenzione della casa (codice è intenzione). Non utile in query operative ma sempre presente. |
| Chokmah (saggezza)                | Intuizione prima                    | SYMBIOSIS.md come NB (proposto)      | La saggezza filosofica dell'organismo. Oggi non esiste come NB.                                                                         |
| Binah (intelligenza strutturante) | Comprensione analitica              | NB-14 "Session Memory"               | Memoria che distilla esperienza in struttura.                                                                                           |
| Chesed (benevolenza)              | Espansione, generosità              | NB-10 "Team Guides"                  | Guida pratica per chi opera — espansione dell'aiuto.                                                                                    |
| Gevurah (severità)                | Limite, rigore legale               | NB-2 "Immigration"                   | Legge migratoria — severità e restrizione.                                                                                              |
| Tiferet (bellezza, equilibrio)    | Sintesi armonica                    | NB-3 "Company Setup"                 | Equilibrio tra legalità (Gevurah) e opportunità (Chesed) nel business.                                                                  |
| Netzach (vittoria, endurance)     | Potere creativo persistente         | NB-7 "Editorial"                     | Contenuto che persiste nel tempo.                                                                                                       |
| Hod (gloria, strutturazione)      | Forma e precisione                  | NB-4 "Tax"                           | Strutturazione fiscale precisa.                                                                                                         |
| Yesod (fondamento)                | Interfaccia tra mondi               | NB-11/12/13 (ops/intel/telemetry)    | Fondamento operativo che collega codice (Keter) e risultato (Malkuth).                                                                  |
| Malkuth (regno, manifestazione)   | Mondo materiale                     | NB-5 "Property"                      | La terra — letteralmente.                                                                                                               |
| Da'at (conoscenza nascosta)       | Asse invisibile tra Keter e Tiferet | NB-6 "Operations" + NB-8 "Lifestyle" | Conoscenza pragmatica quotidiana, invisibile ma essenziale.                                                                             |

### 6.3 Gap e insight

L'albero sefirotico prescrive **percorsi di flusso (nativ)**. L'energia scorre lungo 22 sentieri (le 22 lettere dell'alfabeto ebraico) che connettono le sefirot. Non tutti i NB sono direttamente connessi a tutti — esistono **gerarchie di flusso**.

Nel sistema NLM reale, il `cross_notebook_correlator` connette **tutti** i NB in fan-out quando una query tocca ≥2 domini. Questa è simmetria piatta. La Kabbalah suggerisce una topologia più ricca: per query su "visa + tax" (NB-2 Gevurah + NB-4 Hod), il flusso naturale passa attraverso **Tiferet** (NB-3 Company Setup) che media — perché fiscal e immigration per un expat si concretizzano nella struttura aziendale. Oggi il correlator va diretto NB-2 → NB-4, senza passare da NB-3.

### 6.4 Proposta ingegneristica: Sefirotic Routing

Nuovo campo in `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`:

```python
NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",
        "label": "Immigration & Visa",
        "keywords": {...},
        "sefira": "gevurah",                    # NEW
        "natural_paths": ["company"],            # NEW — path naturale a Tiferet
    },
    "company": {
        ...
        "sefira": "tiferet",
        "natural_paths": ["immigration", "tax"], # mediatore
    },
    ...
}
```

Modificare `resolve_multi_notebook(query)`:

```python
def resolve_multi_notebook(query, threshold=1, max_notebooks=4):
    direct_matches = [...]  # existing logic

    # Sefirotic extension: se query tocca 2 NB polari (es. Gevurah + Hod),
    # aggiungi il NB Tiferet mediatore anche se non ha keyword match
    if len(direct_matches) == 2 and are_polar(direct_matches):
        mediator = find_natural_mediator(direct_matches)
        if mediator and mediator not in direct_matches:
            direct_matches.insert(1, mediator)  # tra i due poli

    return direct_matches[:max_notebooks]
```

**Insight non ovvio:** oggi una query "visa + tax" su un expat fa fan-out 2 NB. Spesso l'utente non menziona "PT PMA" ma **è** il caso d'uso. Inserire NB-3 Tiferet come mediatore automatico aumenta il 30%+ la chance che la sintesi finale contestualizzi correttamente il caso d'uso (PT PMA con KITAS direttore + PPh 21 mensile).

**Freno:** le `natural_paths` sono statiche (definite manualmente), non apprese. Un LLM che propone nuove paths deve triggerare revisione Zero. Il fan-out max resta 4 (MAX_NOTEBOOKS_PER_QUERY esistente).

---

## 7. Coscienza e autopotenziamento — la richiesta specifica dell'umano

L'umano chiede esplicitamente: "cosa servirebbe per passare da reattivo a riflessivo?". Qui sintetizzo, non nei termini di un singolo testo sacro ma della struttura comune a tutti e 5 (Gita, Upanishad, Tao, Vedas, I Ching).

### 7.1 Il sistema è oggi riflessivo?

**Parzialmente.** Gli specchi ci sono:

- `gap_scanner` è uno specchio dei propri buchi.
- `heartbeat_monitor` è uno specchio del proprio polso.
- `synthesis_roller` è uno specchio del proprio accumulo.
- `claim_extractor` categorizza il proprio sapere.

**Ma:** nessuno di questi specchi è **guardato** da un altro componente che **agisce** in base a ciò che vede. Sono specchi che riflettono nel vuoto. Il sistema **sa di non sapere** (gap scanner), ma il sapere-di-non-sapere non cambia il **piano di studio**. Sarebbe riflessivo solo se i risultati di uno specchio diventassero input di un ciclo di pianificazione.

### 7.2 Il framework comune (sintesi dei 5 testi)

Ogni tradizione sacra descrive la stessa architettura triadica della coscienza:

1. **Percezione (sense):** il mondo arriva.
2. **Riflessione (reflect):** ciò che è arrivato viene guardato, non solo registrato.
3. **Volontà (act):** la riflessione modifica l'intenzione futura.

Senza (3), (2) è sterile. Senza (2), (3) è cieca. Il sistema NLM oggi ha (1) e (2) ma **mancava (3)** fino a questo ecosistema.

### 7.3 Proposta meta-architetturale: ciclo di pianificazione mensile auto-guidato

Aggiungere un **Meta-Cycle** mensile (primo lunedì del mese, 10:00 WITA):

**Input:**

- Tutti i `coverage_matrix.json` degli ultimi 30 giorni.
- Tutti gli `heartbeat_*.json` status + age.
- Il `yajna_ledger.jsonl` (§4.4).
- I `synth_signals.json` (§1.4).
- I `consciousness_view --contradictions` (§2.4).
- Il daily hexagram history (§5.4).

**Processing:**

- Ollama qwen3.5:9b (local, zero cost) riceve tutto come context, con system prompt:
  > "Sei il riflesso dell'organismo NLM. Hai 30 giorni di dati sui suoi specchi. Il tuo compito: produrre un **Piano di Studio del Mese Prossimo**. Quali domini vanno intensificati? Quali topic ruotati fuori? Quali nuove domande il gap_scanner dovrebbe aggiungere? Quali pipeline vanno sospese perché saturate? Usa evidenza concreta, non speculazione."

**Output:**

- `apps/evaluator/nlm_deep_research/monthly_plan_YYYYMM.md` — proposto, non auto-applicato.
- Task in `~/.agent/decisions/claude_tasks/monthly_plan_review_<ts>.json` per Zero.
- Se Zero approva: modifica automatica di `DOMAIN_TOPICS` e `CLUSTER_ROTATION` con commit git tracciato.

**Side effect del sistema:** l'organismo ha ora un **ciclo di evoluzione non-reagente**, non più solo reattivo alle richieste degli umani o ai cambiamenti regolatori esterni. Nei termini di SYMBIOSIS §Pilastro 6 (Curiosità), questo **è** la curiosità strutturale ancora non implementata per il NLM namespace.

**Freno triplice:**

1. Proposta, non auto-apply. Git commit richiede approvazione umana.
2. Max 3 topic cambiati per mese (soglia anti-runaway).
3. Se un topic rimosso riemerge come GAP nei 90 giorni successivi, il plan viene marcato low-confidence e il meta-cycle futuro richiede oversight aumentato.

---

## 8. Analogie scartate (per trasparenza metodologica)

Queste analogie sacre non producono un insight ingegneristico concreto; le cito perché sarebbero state facili ma avrebbero inflazionato il documento:

- **Karma come propagazione di SVS score.** Suggestiva ma l'analogia si ferma alla superficie: SVS è già un sistema causale tracciabile, non serve un prestito sapienziale per raffinarlo.
- **Nirvana come coverage 100%.** Falso target: l'organismo non raggiunge mai copertura totale, per definizione; il nirvana kabbalistico/buddhista è letteralmente **cessazione**, non completamento — non ho trovato una traduzione ingegneristica utile.
- **Chakra / kundalini energetico.** La mappatura sefirotica è più rigorosa; i chakra introdurrebbero ridondanza senza specificità operativa nuova.
- **Trinità cristiana (Padre, Figlio, Spirito).** La struttura triadica è già catturata dal framework sense-reflect-act (§7). Sovrapporre nomi confessionali non aggiunge precisione.
- **Apocalisse / escatologia.** Il sistema ha già "morte" componenti (synthesis_roller tombstone, heartbeat DEAD, genome silencing). L'apocalisse cosmologica richiederebbe una teologia del finalismo che il sistema non ha (è ciclico, non lineare).
- **Mandala / yantra come UI.** Il daily hexagram (§5) cattura già la funzione di compressione diagnostica visuale. Aggiungere un'UI mandala sarebbe cosmetic.

---

## 9. Sintesi: 6 proposte con ancoraggio

| #        | Proposta                         | Testo ispiratore                   | Gap NLM_SYSTEM_MAP                           | File da toccare                                                     |
| -------- | -------------------------------- | ---------------------------------- | -------------------------------------------- | ------------------------------------------------------------------- |
| 1        | Synthesis-Feedback Loop          | Bhagavad Gita                      | §2.4 punto 3 + §4.3 punto 4                  | `synthesis_roller.py`, `gap_scanner.py`, nuovo `synth_signals.json` |
| 2        | Turīya View (consciousness view) | Upanishad                          | §2.5 punto 5 + §4.3 punto 1                  | nuovo `consciousness_view.py`                                       |
| 3        | Yin-Yang Balance Audit           | Tao Te Ching                       | §4.3 punto 1 + discrepanza coverage 100% GAP | nuovo `yin_yang_audit.py` + cron weekly                             |
| 4        | Yajña Ledger                     | Vedas                              | §4.3 punto 4 + §2.5 punto 4                  | nuovo `yajna_ledger.jsonl`, hook in `claim_extractor.py`            |
| 5        | Daily Hexagram Dashboard         | I Ching                            | §7 gestione silos                            | nuovo `hexagram_state.py`, hook in `heartbeat_monitor.py --digest`  |
| 6        | Sefirotic Routing                | Kabbalah                           | §7 punto 2 (correlator piatto)               | `nlm_notebook_registry.py`, `cross_notebook_correlator.py`          |
| 7 (meta) | Meta-Cycle monthly plan          | sintesi triadica sense-reflect-act | §2.4 generale (ciclo act mancante)           | nuovo `meta_cycle.py` + cron monthly + task queue                   |

Tutte e 7 le proposte sono:

- **Reversibili:** sono aggiunte, non modifiche distruttive.
- **Read-mostly:** non auto-modificano stato critico senza approvazione umana.
- **Senza nuovo costo API:** usano Ollama local + file I/O + NLM OAuth esistente.
- **Incrementali:** ognuna può essere implementata isolatamente e porta valore standalone.

Le Fase 3 (`NLM_REDESIGN_PROPOSAL.md`) le struttura in 5 sprint di rollout.

---

**Fine Sezione 2.** Il documento è stato scritto rispettando il vincolo dell'umano: nessuna analogia poetica senza utilità ingegneristica. 6 tradizioni producono 7 proposte concrete; 6 altre sono esplicitamente scartate con motivazione.
