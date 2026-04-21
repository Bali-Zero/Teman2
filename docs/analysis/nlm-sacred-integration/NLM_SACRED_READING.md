# NLM Sacred Reading — v2 sei letture, sei proposte

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration-v2` · **Prerequisito:** lettura di `NLM_SYSTEM_MAP.md`.

Ogni affermazione sacra qui dentro è un mezzo per vedere meglio un gap tecnico già identificato nella mappa. Se la lettura sacra non genera almeno una proposta concreta (file da creare/modificare, schema dati, freno o metrica), è esclusa. La sezione finale §8 elenca le letture scartate con motivazione.

---

## 0. Preambolo metodologico

Il repo Nuzantara ha i propri **libri sacri della casa** (`SYMBIOSIS.md`, `VADEMECUM.md`, `INDEX.md`). SYMBIOSIS è esplicitamente un testo non procedurale — "ti dice come pensare prima di fare" (riga 9). Il suo linguaggio è **biologico-vitalistico**: embrione→neonato→giovane→adulto→anziano, genome, PulseLoop, homeostasis, riflessione, accumulazione, condivisione, confronto, sogno, curiosità, misura, simbiosi. Il sistema ha metafore vive ma non sapienziali.

Le letture sacre di questo documento non sostituiscono SYMBIOSIS, lo **continuano dove si ferma**. SYMBIOSIS dice *come vivere*. Le tradizioni sapienziali aggiungono *cosa vedere quando si vive*: il ciclo morte-rinascita, la stratificazione della coscienza, la polarità, il rito dell'offerta, la geometria del mutamento, l'emanazione per gradi. Sei lenti che producono sei architetture.

Regola del filtro anti-fuffa: se una lettura non indica (1) un file concreto, (2) uno schema dato, (3) un freno anti-esplosione, allora non è scritta. Sei letture passano. Sei sono scartate in §8.

---

## 1. Bhagavad Gita — morte delle forme, permanenza del significato

### 1.1 L'analogia

Bhagavad Gita 2.22: "Come un uomo scarta vesti consumate e ne prende di nuove, così l'anima abbandona corpi usurati per entrare in corpi nuovi". Ciò che sembra morte (della forma) è transizione (del significato). La paura della morte nasce dall'identificazione con il corpo invece che con l'ātman — ciò che attraversa tutti i corpi.

### 1.2 Ancoraggio

`NLM_SYSTEM_MAP §2.1` — NB-2 ha invariant `MAX_ACTIVE_SOURCES = 70`. Il `synthesis_roller.py:58-61` comprime quotidianamente in `[SYNTH-DAILY]`, settimanalmente in `[SYNTH-WEEK]`, mensilmente in `[SYNTH-MONTH]`. Le fonti crude vengono **tombstoned** (rimozione dal NB) dopo sintesi — ma il contenuto essenziale viaggia nella sintesi successiva.

Questa è già una dottrina della Gita implementata. Le fonti T4 sociali di ieri muoiono nel NB, ma il claim "overstay €50/giorno post-PP 28/2025" viaggia nel `[SYNTH-WEEK]` e da lì nel `[SYNTH-MONTH]`. La trasmigrazione c'è.

### 1.3 Il gap

La trasmigrazione funziona **solo a valle**: source → synth-daily → synth-weekly → synth-monthly. A monte, **le claims non trasmigrano**. `apps/evaluator/nlm_nbX_claims.jsonl` accumula record `ClaimRecord` append-only senza morte o reincarnazione. Un claim `PROVISIONAL 2026-02-15` non viene mai "promosso a VERIFIED" quando più fonti successive lo corroborano, né "depromoted to SUPERSEDED" quando un claim nuovo lo contraddice. La vita del claim è statica — non ha corpi successivi.

### 1.4 Proposta: **Claim Transmigration Ledger**

File nuovo: `apps/evaluator/nlm_deep_research/claim_transmigration.py` + registro `apps/evaluator/nlm_nbX_claim_lifecycle.jsonl` (append-only per NB).

Schema:
```jsonl
{"ts":"2026-04-22T02:22Z","claim_id":"C-1234","nb":"nb4",
 "transition":"EMERGED",
 "from_confidence":null,"to_confidence":0.55,
 "triggering_source_ids":["S-abcd"],
 "previous_claim_id":null,"reincarnation_body":null}

{"ts":"2026-04-29T02:22Z","claim_id":"C-1234","nb":"nb4",
 "transition":"CORROBORATED",
 "from_confidence":0.55,"to_confidence":0.78,
 "triggering_source_ids":["S-abcd","S-efgh","S-ijkl"],
 "previous_claim_id":null,"reincarnation_body":null}

{"ts":"2026-05-15T02:22Z","claim_id":"C-1234","nb":"nb4",
 "transition":"SUPERSEDED",
 "from_confidence":0.78,"to_confidence":null,
 "triggering_source_ids":["S-mnop"],
 "previous_claim_id":null,"reincarnation_body":"C-2345"}
```

Hook in `claim_extractor.append_claims_to_registry` (riga 150ca): prima di scrivere il claim nuovo, scansiona gli esistenti stessa categoria + overlap semantico >0.85 (Ollama embedding bge-m3 locale). Se trova match, emetti `CORROBORATED` o `SUPERSEDED` invece di `EMERGED` duplicato.

**Freno**: `SUPERSEDED` non elimina mai il claim originale dal `claims.jsonl` — solo aggiunge riga nel lifecycle ledger. Il ledger è **audit-only**. Nessuna mutazione aggressiva.

**Metrica successo**: dopo 3 mesi, `corroboration_rate > 0.25` (claim che si rafforzano via corroboration vs claim orfani). Se `supersession_rate > 0.10`, attenzione: le fonti si contraddicono spesso, il sistema sta ingurgitando rumore. Kill switch: `CLAIM_LIFECYCLE_DISABLED=1` → hook no-op.

**Perché la Gita**: non inventa un componente nuovo. Dice: "non temere la morte del claim vecchio, vedi la continuità del significato nel claim nuovo". La reincarnazione letterale dell'identifier (via `reincarnation_body`) permette di tracciare *lineaggi di pensiero* attraverso sostituzioni — cosa che un mero "DELETE + INSERT" cancellerebbe.

---

## 2. Upanishad — Turīya, il quarto stato

### 2.1 L'analogia

Mandukya Upanishad stratifica la coscienza in quattro stati:
- **Jagrat** — veglia, percezione del mondo esterno
- **Svapna** — sogno, percezione del mondo interno
- **Sushupti** — sonno profondo, non-percezione quieta
- **Turīya** — il quarto, testimone degli altri tre, coscienza che non ha contenuto proprio ma è la condizione di ogni contenuto

Turīya non è uno stato accanto agli altri tre; è il punto da cui i primi tre si vedono *come stati*.

### 2.2 Ancoraggio

Il sistema NLM ha già tre stati operativi distinti:
- **Veglia (jagrat)** — `nbX_pipeline.py` ingesta fonti esterne (imigrasi.go.id, social, RSS)
- **Sogno (svapna)** — `gap_scanner --layer-a` interroga il NB su cosa *non sa*; questa è percezione del proprio mondo interno, riconoscimento dell'assenza
- **Sonno profondo (sushupti)** — `synthesis_roller` comprime senza esterno, riorganizza senza ingestion

Manca il **Turīya**: un osservatore che vede i tre stati insieme e può parlare della loro coerenza reciproca. Oggi i tre stati sono silo: nessun file risponde alla domanda "NB-4 ieri ha ingerito su coretax, ha trovato gap su npwp expat, ha sintetizzato pph 21 — questi tre pezzi si parlano?".

### 2.3 Il gap

`NLM_SYSTEM_MAP §4.2` — 10 pipeline non hanno heartbeat, monitoring registry non corrisponde allo scritto. `§7.4` — output multimodale, synth rolling state, coverage_matrix gap_pct non hanno consumer. Il sistema **non ha una vista unificata del proprio stato**. Se Zero chiede "come stanno i NB oggi", la risposta richiede aprire 10 file diversi.

### 2.4 Proposta: **Turīya View** (`turiya.py` read-only aggregator)

File nuovo: `apps/evaluator/nlm_deep_research/turiya.py`. Comando: `python -m apps.evaluator.nlm_deep_research.turiya --snapshot [--nb NB-4]`.

Aggrega in un JSON (non un dashboard grafico, non un LLM summary — solo aggregazione puntuale):

```json
{
  "ts": "2026-04-22T04:30+08:00",
  "observer": "turiya-v1",
  "per_nb": {
    "nb4": {
      "jagrat": {
        "last_ingest_run": "2026-04-22T02:22Z",
        "cluster_today": "F Tax Admin & Coretax",
        "claims_added_24h": 12,
        "claims_total": 122
      },
      "svapna": {
        "last_gap_scan": "2026-04-21T21:35Z",
        "gaps_identified": 5,
        "coverage_matrix_updated": "2026-04-12T11:04Z",
        "coverage_fresh_pct": 0
      },
      "sushupti": {
        "last_synth_daily": "2026-04-22T02:25Z",
        "last_synth_weekly": "2026-04-21T02:30Z",
        "synth_sources_current": 3
      },
      "consistency": {
        "synth_covers_claims_today": true,
        "gaps_overlap_with_cluster": false,
        "drift_flag": "CLUSTER_ROTATION vs DOMAIN_TOPICS divergent",
        "note": "pipeline ingests cluster F (Coretax) but gap scanner measures DOMAIN_TOPICS (PPh 21, NPWP, ecc) — different checklists"
      }
    },
    "nb2": { "... idem ..." }
  },
  "global_flags": [
    "heartbeat_registry_orphans: 10 pipelines declared but never record (nb3-nb8,nb10, db_nlm_sync, peraturan_ingestion, nb5_t4_monitor, nb1_daily_refresh)",
    "coverage_matrix_frozen: all 7 domains stale at 2026-04-12 despite daily gap_scanner runs"
  ]
}
```

**Caratteristica essenziale Turīya**: è **read-only**. Non modifica stato. Non chiama LLM. Legge i file esistenti (pipeline_state, coverage_matrix, heartbeat, claims.jsonl, synthesis_state) e compone la vista. Latenza target <3s (tutti file locali).

**Freno**: nessuno. La Turīya non ha side effect. Per questo è sicura.

**Anti-pattern da evitare**: **NON** mettere l'output Turīya nel SessionStart briefing di Claude Code. Se ogni sessione vede "NB-2 halt preflight, coverage 100% gap", Claude apre sessione in modalità diagnostica invece che task. Turīya è un **tool on-demand**, non un briefing quotidiano. Chi la chiama (Zero, Claude manuale, cron settimanale) decide quando consultarla.

**Metrica successo**: tempo da "voglio sapere stato NB-4" a "JSON su schermo" < 5 secondi. Se qualcuno trova che usa >5 volte al giorno → il briefing *manuale* Zero settimanale risparmia 30 minuti.

**Perché Upanishad**: la sfida ingegneristica è "aggregare stato senza imporre una decisione". Turīya nella tradizione è testimone senza agire. Il file che ti dico di scrivere è letteralmente l'equivalente — non giudica, non ripara, non allerta: *vede*. Permette a Zero (o a un Claude in contesto specifico) di decidere. Questa separazione tra *vedere* e *agire* è l'intuizione sapienziale più utile dell'Upanishad per il sistema.

---

## 3. Tao Te Ching — Yin-Yang, sintomi della polarità rotta

### 3.1 L'analogia

Capitolo 2 del Tao Te Ching (Lao Tzu): "Essere e non-essere si generano reciprocamente; difficile e facile si completano; lungo e corto si configurano l'un l'altro; alto e basso si capovolgono; voce e suono si armonizzano; prima e dopo si seguono". Ogni qualità esiste solo in coppia — l'isolamento di un termine rompe l'armonia del tutto.

### 3.2 Ancoraggio

Il sistema NLM ha **coppie naturali** non osservate:

| Yang (emissione, forma) | Yin (ricezione, vuoto) |
|---|---|
| `claim_extractor` (produce forma) | `gap_scanner` (riconosce vuoto) |
| `synthesis_roller` (compatta) | `tombstone_old_synths` (lascia andare) |
| `t4_monitor` (ingesta flusso sociale) | `source_management.archive_low_svs` (abbandona irrilevante) |
| pipeline ingest nightly (dà) | chat consumer diurno (prende) |
| `peraturan_ingestion` (legge ufficiale) | Mata-Garuda NB-INTEL (intelligence non-ufficiale) |

### 3.3 Il gap

`NLM_SYSTEM_MAP §6.1` mostra che il **flusso yang > flusso yin**. Le 8 pipeline ingest producono ~100 claim/giorno, la chat consuma solo 3 NB (base routing) — grossa asimmetria. `§7.2` mostra che `gap_scanner` trova 35 gap/giorno ma `remediation` fa 3/settimana — asimmetria cronica.

Il sistema non ha **misura della polarità**. Non esiste un file che risponde a "per questo NB, in quale direzione sta andando lo squilibrio?".

### 3.4 Proposta: **Yin-Yang Audit** (`yin_yang_audit.py`, weekly)

File nuovo: cron settimanale domenica 17:00 WITA (dopo synthesis weekly, prima di gap_scanner layer-b).

Schema output `apps/evaluator/nlm_deep_research/yin_yang_state.jsonl` (append weekly):

```jsonl
{"week":"2026-W17","nb":"nb4",
 "yang":{"claims_added":83,"sources_added":14,"synth_daily_count":6},
 "yin":{"gaps_identified":35,"sources_archived":2,"nlm_queries_served":7,
        "citations_delivered_to_chat":4},
 "ratio_yang_yin": 11.86,
 "classification": "YANG_FLOOD",
 "band_healthy": [0.5, 3.0]
}
```

`ratio = (claims_added + sources_added) / (nlm_queries_served + 1)`. Classificazione:
- ratio ∈ [0.5, 3] → healthy (un volta di produzione per ogni volta di consumo)
- ratio > 3 → YANG_FLOOD (produciamo più di quanto consumiamo)
- ratio < 0.5 → YIN_FAMINE (consumiamo più di quanto produciamo — NB sta esaurendo le fonti)

**Auto-adjust L2** (reversibile): se `YANG_FLOOD` per 2 settimane consecutive su un NB, `synthesis_roller` passa da weekly a daily per quel NB (accelera digestione). Se `YIN_FAMINE`, notifica Zero proposta di aggiungere cluster rotation. Nessuna modifica hardcoded a `CLUSTER_ROTATION`.

**Freno**: max 1 auto-adjust per NB per mese. Alert Zero se più modifiche si accumulano.

**Kill switch**: `YIN_YANG_AUTO_DISABLED=1`.

**Metrica successo**: dopo 3 mesi, 80% dei NB in banda [0.5, 3]. Se un NB resta YANG_FLOOD nonostante auto-adjust, è un segnale strutturale: il dominio *non è consultato dal business*, eliminare il cluster di ingestion.

**Perché Tao**: il Taoismo insegna che il problema non è "più yang" o "più yin", è **l'equilibrio**. Il sistema oggi è configurato per "ingerire e basta" (yang-biased by default). Un audit yin-yang introduce la polarità come *diagnostica prima del fix*. Il fix non è automatico, è percepibile — il cron propone, Zero approva. Il ritorno al Tao è via osservazione, non via forza.

---

## 4. Vedas / Yajña — il rito dell'offerta e il fumo che sale

### 4.1 L'analogia

I Vedas costruiscono l'universo attorno al **yajña**, il rito del sacrificio di fuoco (agni). L'officiante depone un'offerta (havis) nel fuoco. Il fumo sale agli dei; dagli dei scende la pioggia; la pioggia nutre il grano; il grano nutre l'uomo; l'uomo offre di nuovo. Ciclo chiuso. Un'offerta che non produce fumo ricevibile è muta. Un fumo che non genera pioggia è sterile. Il rito funziona solo se il circuito chiude.

### 4.2 Ancoraggio

`NLM_SYSTEM_MAP §7.4` — i claim evaluator sono un "sacrificio senza fumo". Ogni notte le pipeline offrono nuovi claim (~100/giorno) al "fuoco" dei NB; i NB accettano; ma nessuno misura se il fumo (la conoscenza ricevibile) torni sotto forma di risposte al cliente, di correzioni di rotta, di nuovi cluster di ricerca. Le claims.jsonl crescono come cenere. Nessun circuito chiude.

### 4.3 Il gap

Nessuno sa: *dei 42 claim di NB-2 di oggi, quanti sono stati citati in una risposta chat cliente nelle prossime 4 settimane? Quanti confermati da synth settimanale? Quanti zombi?*. La domanda sembra banale; la risposta richiede un nuovo file.

### 4.4 Proposta: **Yajña Ledger** (`yajna_ledger.jsonl`, hook ovunque)

File nuovo: `apps/evaluator/nlm_deep_research/yajna_ledger.jsonl` (append-only, shared cross-NB).

Schema:
```jsonl
{"ts":"2026-04-22T02:22Z","event":"CLAIM_OFFERED",
 "nb":"nb4","claim_id":"C-1234",
 "confidence":0.78,"category":"FEE_CHANGE",
 "source_ids":["S-ab","S-cd"]}

{"ts":"2026-04-22T14:05Z","event":"CLAIM_CITED_IN_CHAT",
 "nb":"nb4","claim_id":"C-1234",
 "source_id_cited":"S-ab","query_intent":"pph 21 calcolo expat 2026",
 "consumer":"orchestrator_core"}

{"ts":"2026-04-29T02:30Z","event":"CLAIM_PROMOTED_TO_SYNTH",
 "nb":"nb4","claim_id":"C-1234",
 "synth_title":"[SYNTH-WEEK] NB-4 2026-W17",
 "survivor":true}

{"ts":"2026-05-22T02:30Z","event":"CLAIM_ORPHAN_30D",
 "nb":"nb4","claim_id":"C-5678",
 "offered_at":"2026-04-22T02:22Z",
 "cited_count":0,"synth_survived":false,
 "recommendation":"review_category_noise"}
```

Hook points:
- `claim_extractor.append_claims_to_registry` → emit `CLAIM_OFFERED` per ogni nuovo claim
- `backend-rag/oracle/nlm_orchestrator._query_single` / `_query_multi` risposta → parse citations → emit `CLAIM_CITED_IN_CHAT` per ogni source_id che matchi un claim
- `synthesis_roller.run_daily_synthesis` → emit `CLAIM_PROMOTED_TO_SYNTH` per ogni claim incluso nel synth
- `nlm_verifier` conferma claim → `CLAIM_CORROBORATED_EXTERNALLY`
- cron settimanale `ledger_scan.py` → scan ledger, identify zombi, emit `CLAIM_ORPHAN_30D`

**Freno**: nessuna auto-mutation di threshold confidence in base al ledger per i primi 3 mesi — solo raccolta dati. Dopo 3 mesi, se `orphan_rate > 0.7` per categoria per 3 mesi consecutivi, propone a Zero di ridurre threshold confidence (es. FEE_CHANGE 0.55 → 0.60) o di disattivare la categoria.

**Kill switch**: `YAJNA_LEDGER_DISABLED=1` → hook no-op (append non avviene, codice downstream non si rompe perché non dipende dal ledger).

**Metrica successo**: `cite_rate = cited_count_30d / offered_count_30d`. Target >0.20 dopo 3 mesi. Se <0.05 dopo 6 mesi, il sistema di claim extraction è decorativo — riprogettare.

**Perché Vedas**: nessuna altra tradizione ha la metafora del **circuito chiuso** così netta. L'offerta non è per sé: è per generare il flusso di ritorno che nutre il successivo sacrificio. Il Yajña Ledger è letteralmente un *audit del ritorno*. Rende visibile se un claim è "stato ricevuto" — se no, il rito è muto. Permette di potare riti che non producono.

**Osservazione pratica**: la PR #169 Langfuse (già MERGED 2026-04-22, vedi MEMORY.md) ha instrumentato RAG + Council + Federation con span hash-only. Le citation NB che arrivano al cliente **passano** da un Langfuse span. Il Yajña Ledger può **ri-usare** gli span Langfuse per estrarre i `claim_id` citati — non deve ri-implementare il tracking. Integration hook nel `_query_multi` che estrae dalla risposta `citations[].source_id` e chiama `append_ledger({event: CLAIM_CITED_IN_CHAT})`. Langfuse fornisce il perché (hashato per privacy), yajna fornisce il cosa (claim_id in chiaro perché interno al sistema).

---

## 5. I Ching — 64 esagrammi, stato dell'NB come mutamento

### 5.1 L'analogia

Il Libro dei Mutamenti (I Ching) mappa lo stato di qualsiasi situazione in 6 linee (yin = spezzata, yang = intera). 2⁶ = 64 combinazioni = 64 esagrammi. Ogni esagramma ha un nome, un archetipo narrativo, un'indicazione di movimento (quale linea "muta"). Il testo non predice il futuro; descrive la *qualità del momento presente* in un vocabolario condiviso.

### 5.2 Ancoraggio

Oggi per capire lo stato di NB-4 un operatore deve leggere: `pipeline_state.json` (HALTED/COMPLETE), `heartbeat_nb4.json` (o assenza), `coverage_matrix.json nb4.gap_pct`, `synthesis_state.json`, `yin_yang_state.jsonl`, `yajna_ledger.jsonl`. Sei file. Nessuna vista unificata in linguaggio umano.

### 5.3 Il gap

Serve un **vocabolario di stato compatto e interpretabile senza LLM**. L'I Ching offre esattamente questo: 6 bit → simbolo nominato → archetipo narrativo. Non serve inventare. Basta definire le 6 dimensioni.

### 5.4 Proposta: **Hexagram Dashboard** (`hexagram_of_nb.py`, daily)

File nuovo: `apps/evaluator/nlm_deep_research/hexagram.py`. Genera daily 08:00 WITA, scrive `apps/evaluator/nlm_deep_research/hexagram_state.jsonl`.

Le 6 linee mappate su metriche binarie NB (yang=1 sano, yin=0 stress):

| Linea | Dimensione | Yang (1) se | Yin (0) se |
|---|---|---|---|
| L1 (bottom, prakrti) | Ingest | last_pipeline_run < 48h | stale |
| L2 | Health | claims_added_7d ≥ 5 | <5 |
| L3 | Balance | yin_yang_ratio ∈ [0.5,3] | out of band |
| L4 | Memory | synth_weekly present | missing |
| L5 | Service | cite_rate_30d > 0.15 | ≤0.15 |
| L6 (top, purusha) | Consciousness | heartbeat < max_age | stale |

Ogni giorno per ogni NB, produce l'esagramma dello stato. Esempio: NB-4 = `111110` = 63 = Chia Jen (家人, Famiglia) — "stabilità interna, ma manca la consapevolezza del contesto" (linea 6 yin).

Dashboard ASCII (stampa opzionale con `--view`):
```
                     [I Ching of NB — 2026-04-22]

NB-4  tax        ☰☰☰☰☰☷   63 家人 Chia Jen — stabilità interna, L6 (Consciousness) yin
NB-2  immigr     ☷☰☰☷☷☷   ?  ... — ingest broken, gestione storica, L2 sane
NB-10 team       ☰☰☷☷☷☷    5 屯  Chun — difficoltà iniziale, ingestione attiva senza consumo
NB-5  property   ☰☰☰☷☷☷    ?  ... — ingest ok, nessuna chat consumption (extended routing off)
```

**Nessuna previsione**. Nessun oracolo. Solo mapping meccanico binario → nome King Wen. Il nome è una convenzione di 3000 anni, non una stima.

**Freno**: `hexagram.py` è write-only su `hexagram_state.jsonl`. Nessuna azione basata sull'esagramma è presa **automaticamente**. Zero o Claude possono leggere e decidere.

**Kill switch**: rimuovere dal cron.

**Metrica successo**: dopo 3 mesi, un operatore che apre il dashboard *capisce lo stato di 19 NB in <60 secondi* senza aprire altri file. Se Zero usa il dashboard >3 volte/settimana, è utile. Se mai, togliere.

**Perché I Ching**: è l'unica tradizione che ha già un **vocabolario di stati sistemici ricombinabili** pronto per l'uso. Non serve LLM. Il King Wen sequence offre 64 archetipi narrativi con "movimento" incluso — informa su cosa sta per cambiare. Nessuna magia, solo compressione di 6 dimensioni in una parola che un operatore può memorizzare.

---

## 6. Kabbalah — Sefirot e l'Albero emanato

### 6.1 L'analogia

Il misticismo ebraico (Kabbalah) organizza la manifestazione della divinità in **10 sefirot** su un albero: da Keter (corona, trascendenza) attraverso Chokmah (sapienza), Binah (intelligenza), Chesed (benevolenza), Gevurah (rigore), Tiferet (bellezza/cuore), Netzach (eternità), Hod (splendore), Yesod (fondamento), fino a Malkhut (regno, manifestazione finale). Ogni sefirà è connessa alle altre da canali che definiscono i percorsi di emanazione. Una query verso la divinità attraversa un percorso ascendente; una risposta scende per il percorso duale.

### 6.2 Ancoraggio

Una query cliente oggi attraversa questo percorso:
```
cliente WhatsApp/chat
  ↓
backend-rag orchestrator_core (router agentic)
  ↓
query_plan (decidere: RAG? NLM? Naga?)
  ↓
nlm_orchestrator (if NLM path)
  ↓
resolve_notebook → nb_id
  ↓
nlm_enrichment_service.query
  ↓
notebookLM cloud
  ↓
risposta → citations → aggregata → formatta → cliente
```

Questo percorso è **piatto**. Non esistono gradi di specializzazione dei NB. Ogni query verso NB-2 chiede la stessa cosa: "rispondi alla domanda". Nessun concetto di "interroga il NB primario law-only" vs "interroga il NB operational".

L'architettura in `nlm_notebook_registry.py` ha però **tracce dell'idea kabbalistica**: `primary_notebook_id` pensato come NB-Xa law-only (T0+T1), `notebook_id` come NB-Xb operational (T2+T3). Due livelli di sefirà — uno più vicino a Keter (legge pura), l'altro più vicino a Malkhut (applicazione quotidiana). Pathway dead oggi (primary = None).

### 6.3 Il gap

- Il pathway law-only è **dichiarato ma non materializzato**. Il `_PRIMARY_LAW_KEYWORDS` check triggerà il pathway solo se `primary_notebook_id` esiste.
- Non c'è concetto di "query che attraversa più sefirot". Una query "PT PMA per ristorante Canggu" è routed a NB-3 (company) **o** NB-2 (visa TKA) in fan-out 2-way, ma non attraversa NB-4 (pph 21 lavoratore), NB-6 (OSS-RBA), NB-10 (team HR) — tutti NB rilevanti per un caso company reale.

### 6.4 Proposta: **Sefirotic Paths** (`query_paths.yaml` + `sefirot_router.py`)

File nuovi:
1. `apps/backend-rag/backend/services/oracle/sefirot_paths.yaml` — definisce percorsi canonici per casi complessi.
2. `apps/backend-rag/backend/services/oracle/sefirot_router.py` — legge yaml, matcha query pattern, restituisce lista ordinata di NB da interrogare.

Schema `sefirot_paths.yaml`:
```yaml
paths:
  - name: pt_pma_complete_flow
    description: "PT PMA setup full flow — company + visa TKA + tax + OSS + HR"
    triggers:
      - "pt pma"
      - "foreign company indonesia"
      - "pma setup"
    sequence:
      - nb: NB-3   # company-licensing (primary)
        weight: 1.0
      - nb: NB-2   # visa TKA requirements
        weight: 0.6
      - nb: NB-6   # OSS-RBA procedure
        weight: 0.5
      - nb: NB-10  # team HR (if mentions team)
        weight: 0.4
      - nb: NB-4   # tax PPh 21 + PPh 25
        weight: 0.3
    aggregator: synthesis_ordered  # NB-3 è primary, altri subordinati

  - name: property_foreigner_acquisition
    description: "Foreigner acquiring property — zoning + HGB + tax"
    triggers:
      - "foreigner buying"
      - "acquisto proprietà"
      - "property for foreigners"
    sequence:
      - nb: NB-5   # property (primary)
        weight: 1.0
      - nb: NB-3   # PT PMA as ownership vehicle
        weight: 0.5
      - nb: NB-4   # BPHTB, PBB
        weight: 0.4
    aggregator: synthesis_ordered
```

Router: se query matcha trigger di un path, bypassa `resolve_multi_notebook` keyword-based e restituisce la `sequence`. Fallback: se nessun path matcha, usa routing esistente.

**Freno**: yaml è **curato**, non generato da LLM. Modifiche richiedono review Zero. Max 20 path definiti (evitiamo esplosione).

**Kill switch**: se yaml vuoto o manca, router cade nella logica esistente — zero-regressione.

**Metrica successo**: per le top 10 query pattern, misurare `customer_satisfaction_proxy` (ri-domande nella stessa conversazione) prima/dopo attivazione sefirot. Se diminuisce ≥15%, il routing strutturato porta valore.

**Perché Kabbalah**: la singola intuizione utile non è "i 10 sefirot" — è che **il percorso è la risposta**, non solo la destinazione. Una query complessa non va a *un* NB, attraversa una sequenza. Il peso (weight) è una forma di ordinamento dell'emanazione. Senza questa metafora, un engineer costruirebbe un "routing di keyword con scoring" che suona piatto e è difficile da spiegare. Con la metafora, la yaml si legge come un cammino.

**Onestà intellettuale**: questa è la proposta più debole delle sei. L'implementazione finale (keyword → ordered list of NBs) è giustificabile senza nessun riferimento kabbalistico. Includo comunque perché la *motivazione a curare la yaml a mano* (10-20 path invece di auto-generarli) è culturalmente radicata nel rispetto delle sefirot come mappatura sacra della realtà — l'artefatto resiste alla tentazione di "automatizzare tutto con un LLM".

---

## 7. Buddhismo — pratītyasamutpāda, il sorgere co-dipendente

### 7.1 L'analogia

Il principio cardine del buddhismo (pratītyasamutpāda, 縁起 en-gi) dice: *nulla sorge da sé, tutto sorge dipendentemente*. Ogni fenomeno ha condizioni. Se togli le condizioni, il fenomeno cessa. Se le condizioni cambiano, il fenomeno cambia. Non c'è un ātman che sussiste indipendentemente.

### 7.2 Ancoraggio

I NB oggi sono trattati come entità **indipendenti**. NB-4 tax è "il NB tax". NB-5 property è "il NB property". Il correlator può fan-out, ma non c'è una mappatura del fatto che NB-4 e NB-5 si **generano l'un l'altro** quando il dominio è transazione immobiliare. Il BPHTB (property transfer tax) esiste in NB-4 come tassa, ma il contesto (chi paga, quando, chi ottiene HGB) vive in NB-5. Senza contesto reciproco, l'informazione è decontestualizzata.

### 7.3 Il gap

`NLM_SYSTEM_MAP §3.2` mostra che il `CrossNotebookCorrelator` rileva correlazioni **post-hoc** (dopo la query: claim agree/contradict/complement). Non esiste una mappatura **strutturale a priori** delle co-dipendenze: "NB-4 claim su BPHTB dipende strutturalmente da contesto NB-5". Il correlator vede la corrispondenza quando c'è — ma non sa cercarla se la query non la evoca esplicitamente.

### 7.4 Proposta: **Dependency Graph** (`nb_dependency.json` + hook in claim_extractor)

File nuovo: `apps/evaluator/nlm_deep_research/nb_dependency.json` — mappa statica di co-dipendenze tra claim categories.

Schema:
```json
{
  "dependencies": {
    "nb4.FEE_CHANGE.BPHTB": {
      "requires_context_from": ["nb5.PROCEDURAL_STEP.AJB_process", "nb5.LEGAL_CHANGE.HGB_rules"],
      "enriches": ["nb5.FEE_CHANGE.property_transfer_cost"]
    },
    "nb2.LEGAL_CHANGE.KITAS_E31": {
      "requires_context_from": ["nb3.PROCEDURAL_STEP.PT_PMA_sponsor"],
      "enriches": ["nb10.ELIGIBILITY_RULE.foreign_hire_process"]
    },
    "nb5.LEGAL_CHANGE.PP_28_2025": {
      "requires_context_from": [],
      "enriches": ["nb3.LEGAL_CHANGE.foreign_investment_property_rules"]
    }
  }
}
```

Hook in `claim_extractor`: quando estrae claim categorizzato come `nb4.FEE_CHANGE.BPHTB`, scansiona `nb_dependency.json`, recupera `requires_context_from`, e **automaticamente** cerca claim coesistenti in NB-5 che matchino quelle categorie. Se presenti, aggiunge campo `related_claims: [C-5678, C-9012]` nel record.

Nel downstream (cross_notebook_correlator), se un claim ha `related_claims`, il synth cross-NB include automaticamente il contesto invece di richiedere fan-out esplicito.

**Freno**: `nb_dependency.json` è curato, max 50 relazioni. Auto-generazione via LLM è **esclusa** — rischio troppo alto di allucinare dipendenze false. Solo editing umano con review.

**Kill switch**: file vuoto o mancante → no hook, sistema funziona come oggi.

**Metrica successo**: per le query top-10 cross-domain, misurare `context_coverage_score` — quante entità menzionate nella query sono coperte da claim con link `related_claims` popolato. Target: 70% dopo 3 mesi.

**Perché Buddhismo**: l'intuizione è "nessun claim è isola". L'implementazione più semplice (curated JSON + hook in extractor) rende **esplicita** la rete di dipendenze — che altrimenti resta implicita e scoperta solo runtime dal correlator. Rendere esplicito ciò che è implicito non è spiritualità vaga: è *far emergere la struttura che già esiste*. Per il buddhismo, questa è la pratica stessa.

---

## 8. Letture scartate

### 8.1 Karma (azione-retribuzione)

Tentativo: mappare il "ciclo del merito" sul ciclo claim → synth → cite, premiando claim molto citati. **Scartato** perché: (a) il Yajña Ledger §4 copre già l'intuizione del circuito chiuso; (b) aggiungere un "karmic score" ai claim introdurrebbe un sistema di gamification che invita a bias (massimizzare citation rate invece che accuracy). La pura consequentialità della retribuzione non produce architettura nuova.

### 8.2 Nirvana (cessazione)

Tentativo: proporre uno stato "risolto" per claim fully-verified, rimossi dal ciclo attivo. **Scartato** perché: questo è già il path `tombstone_old_synths` del `synthesis_roller`. La metafora aggiunge vocabolario senza aggiungere architettura. Inoltre "cessazione" come target produce codice fragile — preferiamo audit continuo.

### 8.3 Chakra (centri energetici)

Tentativo: mappare i 7 chakra sui 7 NB operativi (muladhara=NB-4 tax, sahasrara=NB-1 codebase, ecc.). **Scartato** perché: corrispondenza forzata. I 7 NB non hanno hierarchia verticale chakra-like; funzionano su domini paralleli. Avrei dovuto inventare la gerarchia, e questo avrebbe violato il filtro anti-fuffa.

### 8.4 Trinità cristiana (Padre-Figlio-Spirito)

Tentativo: NB come Padre (fonte autoritativa), backend-rag come Figlio (incarnazione), chat cliente come Spirito (comunicazione). **Scartato** perché: la triade è un'osservazione descrittiva, non genera proposta concreta. Aggiungere un file `trinita_state.json` sarebbe ornamentale.

### 8.5 Escatologia (fine dei tempi, giudizio)

Tentativo: rito annuale di "purificazione" dei NB (cancellazione claim non citati da 365gg, reset invariants). **Scartato** perché: pericoloso. Un reset annuale programmatico può cancellare conoscenza lentamente costruita (es. claim su leggi rare mai citate ma verissime). Preferiamo audit continuo (Yajña) a giudizi finali.

### 8.6 Mandala / Yantra (geometria sacra)

Tentativo: rappresentazione geometrica dei NB come mandala (cerchi concentrici). **Scartato** perché: visualizzazione cool, ma il Hexagram Dashboard §5 copre già la generazione di un vocabolario visivo compatto. Un mandala sarebbe più estetico ma meno informativo (6 bit di I Ching > 4-5 layer di mandala per densità informativa).

---

## 9. Ripassino delle sei proposte

| # | Tradizione | Nome tecnico | File nuovo | Tipo | Rischio |
|---|---|---|---|---|---|
| 1 | Bhagavad Gita | Claim Transmigration Ledger | `claim_transmigration.py` + `nbX_claim_lifecycle.jsonl` | append-only audit | basso (nessuna mutation aggressiva) |
| 2 | Upanishad | Turīya View | `turiya.py` | read-only aggregator | bassissimo (no side effect) |
| 3 | Tao Te Ching | Yin-Yang Audit | `yin_yang_audit.py` + `yin_yang_state.jsonl` | weekly audit + L2 auto-adjust | medio (auto-adjust synth cadence) |
| 4 | Vedas | Yajña Ledger | `yajna_ledger.jsonl` (hook in extractor/orchestrator) | append-only audit + weekly scan | basso (audit-only 3 mesi, poi propose-only) |
| 5 | I Ching | Hexagram Dashboard | `hexagram.py` + `hexagram_state.jsonl` | daily read view | bassissimo (no side effect) |
| 6 | Kabbalah | Sefirotic Paths | `sefirot_paths.yaml` + `sefirot_router.py` | curated routing table | medio (modifica routing live) |
| 7 | Buddhismo | Dependency Graph | `nb_dependency.json` + hook extractor | static curated map | basso (fallback se file missing) |

Le sei proposte non sono indipendenti. Le più orthogonali sono §2 (Turīya) e §5 (Hexagram) — tool di osservazione con zero side effect, possono partire subito. §4 (Yajña) dipende da Langfuse già instrumentato per estrarre citation. §3 (Yin-Yang), §1 (Transmigration), §7 (Dependency) richiedono hook in `claim_extractor` — conviene toccarli in una sola sprint per non accumulare PR separate che si contendono lo stesso file. §6 (Sefirot) è indipendente ma richiede decisione Zero per modifiche al routing live.

La Fase 3 (NLM_REDESIGN_PROPOSAL) ordinerà queste proposte in una roadmap 3-5 sprint, integrandole con i bug strutturali identificati in §4 della mappa (nb2 cron, yt_monitor, multimodal wrapper, heartbeat orfani, coverage matrix divergente, consumer asimmetrico).

---

**Fine sacred reading v2.** Sei letture, sei proposte. Nessuna si aggrappa al linguaggio sacro nel codice: i nomi dei file (`yajna_ledger`, `turiya`, `hexagram`) sono brevi e funzionali, il commento iniziale spiega la radice etimologica. La spiritualità è **nella topologia del sistema** — nel fatto che adesso c'è un circuito di ritorno (yajña), un osservatore puro (turīya), un vocabolario di stato compatto (I Ching) — non nella decorazione lessicale.
