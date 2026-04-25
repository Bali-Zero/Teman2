# DeepSeek Reasoner — NLM brainstorm

**Model**: deepseek-v4-flash
**Usage**: prompt=1277 completion=7237 reasoning=1450
**Finish**: stop

## Reasoning (chain-of-thought)

Stiamo progettando un brain storming sull'elevazione di NotebookLM (NLM) a livello SOTA 2026 nel sistema Nuzantara di Bali Zero. L'utente ha dato contesto fattuale (non marketing), chiedendo 3 livelli: fondamenta mancanti (must-have), pattern SOTA applicabili, estensioni oltre topic attuali, con red team per ogni proposta, vincoli hard. Il formato atteso è markdown strutturato ~2000-3000 parole.

Il mio ruolo: senior system architect con 15 anni esperienza RAG/knowledge systems. Devo rispondere con reasoning step-by-step prima della proposta finale, essere duro sui trade-off, cercare angolo contrarian/under-explored.

Analizzo richieste:

1. Fondamenta mancanti: 3-5 componenti infrastrutturali che un sistema NLM-centric SOTA non può non avere. Con (a) cosa, (b) perché indispensabile, (c) cheap-win vs grande-effort.

2. Pattern SOTA 2026 applicabili: 5-8 pattern concreti, non platitudes. Per ognuno: pattern + mappatura a Nuzantara (quali NB/services).

3. Estensioni oltre topic attuali: domini adiacenti/ortogonali, knowledge graph nuovi, NB meta.

Red team: per ciascuna proposta, identificare il modo più ovvio di fallire in produzione.

Vincoli: no paid Anthropic, paid API OK (DeepSeek), OAuth free preferred, self-hosted priority, hardware 48GB M4 Pro + 16GB M4 Air, no cloud GPU.

Devo differenziarmi da risposte generiche cercando angolo contrarian/under-explored. Cosa significa "under-explored" in questo contesto? Forse: concentrarsi sull'uso di NotebookLM non solo come contenitore di documenti ma come parte di un sistema multi-agente; sottolineare che NotebookLM ha limitazioni severe (context unico, source-limite 20, nessuna API pubblica); suggerire pattern che aggirano i limiti con orchestrazione esterna; l'angolo contrarian potrebbe essere che NLM è sopravvalutato e che il vero valore è nel suo utilizzo come "cervello esterno" per reasoning su domini ristretti, non come database.

Ma attenzione: l'utente sta usando NotebookLM come sorgente per RAG? Dice: "NotebookLM 51 notebook: NB-1 codebase aggregator, NB-2..NB-10 domain... NB-INTEL-{AIResearch/Reg/Tax/Immigration/Press} Mata Garuda feed". Quindi sta usando NLM per creare note e poi probabilmente le usa come sorgente nel sistema RAG (forse tramite query API non documentata? O via export?). Il contesto dice: "No paid Anthropic API, OAuth Claude Max only" - quindi usa Claude via OAuth (Claude Max subscription). NotebookLM free tier è gratuito, ma ha limiti: max 20 source per notebook, 500k caratteri per source? In realtà NotebookLM supporta fino a 50 source per notebook, 500 file total, 25M parole. Ma non ha API pubblica. Come sta integrando NLM nel sistema? Potrebbe usare l'export di NotebookLM (condivisione?) o scraping della UI? È ambiguo.

L'utente dice: "Materiale servito al RAG oggi: fermo-immagine del 22/04 travestito da live" - indica che il contenuto dei notebook non viene aggiornato in tempo reale. Quindi il problema principale è la freschezza e validazione del contenuto NLM.

Approccio strategico: data la mia esperienza, devo riconoscere che NotebookLM è uno strumento potente ma limitato: non ha API, non ha versioning, non ha controllo fine sul RAG interno. La vera SOTA 2026 per sistemi knowledge non è "usare NLM come knowledge base" ma "usare NLM come interfaccia di reasoning colloquiale per domini specializzati". Il pattern emergente è NotebookLM come "research assistant che produce sintesi e insight" piuttosto che come database. Quindi per elevarlo, bisogna focalizzarsi su: (a) freshness e validazione del contenuto, (b) orchestrazione di molti notebook per coprire domini con overlapping, (c) uso di NLM per generare ipotesi da validare con altri strumenti.

Angolo contrarian: la maggior parte degli articoli su "elevate NotebookLM" si concentrano su come usarlo meglio. Io dico: NotebookLM non è scalabile come singolo punto di verità. Il suo vero valore è come "generatore di briefing" e "strumento di sintesi" che alimenta un sistema più grande. Quindi le fondamenta mancanti non sono su NLM in sé, ma sul sistema di orchestrazione che gestisce i contenuti NLM.

Propongo struttura:

- Introduzione: contesto e posizionamento critico su NLM.
- Livello 1: Fondamenta: (1) Unified Orchestrator con freshness contract, (2) Continuous Evaluation Pipeline, (3) Source Lifecycle Management, (4) Multi-Model Reasoning Bus, (5) Honest Monitoring & Alerting.
- Livello 2: Pattern SOTA: (1) Multi-Notebook Synthesis via meta-notebook, (2) Time-Aware freshness scoring, (3) Hypothetical Document Embedding (HyDE) reverse engineering, (4) Deliberative RAG con NLM come expert panel, (5) Active Learning loop con NLM queries, (6) Cross-domain knowledge injection, (7) (bonus) Use NLM as fault-injection tool.
- Livello 3: Estensioni: (a) Domini adiacenti: NB-DIPLOMACY, NB-ECONOMICS, NB-TOURISM-MACRO, NB-INFRASTRUCTURE, NB-LEGAL-COMPARATIVE. (b) Knowledge graph nuovi: event graph, person/entity graph, temporal graph. (c) NB meta su meta: NB-META-INTROSPECTION (analisi performance dei NB), NB-META-SYNTHESIS (fusione inter-notebook).
- Red team per ogni proposta.

Devo essere concreto e verificabile. Per ogni proposta, dire modo concreto di fallire.

Lunghezza 2000-3000 parole. Rispetterò.

Ora scrivo il ragionamento e poi propongo.

---

## Final answer

# Elevazione NLM in Nuzantara: un approccio contrarian alla SOTA 2026

Prima di entrare nei livelli, un disclaimer epistemologico: **NotebookLM è un sistema chiuso, senza API pubblica, senza control flat, senza versioning esplicito**. Ogni proposta che tratta NLM come "database" o "knowledge base" è fragile. L'unico modo per renderlo SOTA è usarlo come **generatore di briefing sintetici e ipotesi**, non come fonte primaria di verità. Questo è il mio angolo contrarian: la comunità oversell NLM come "knowledge management system", mentre il suo vero vantaggio è come **interfaccia di reasoning contestuale ad alta interattività**, ma solo se orchestrato correttamente.

---

## 1. Fondamenta che mancano (must-have)

Prima di qualunque elevazione, devi riparare il 68% di pipeline morte e la falsa freschezza. Queste non sono opzionali.

### 1.1 Unified Orchestrator con Freshness Contract

**Cosa:** Un orchestrator centralizzato (non disperso in 8/9 cron zombie) che mantenga un contratto di freschezza per ogni notebook: ultimo aggiornamento, source version, delta rispetto a fonte upstream. Ogni cron che fallisce deve registrare un incidente, non uscire in 3ms.

**Perché indispensabile:** Il sistema oggi produce "fermo-immagine del 22/04 travestito da live". Senza orchestrazione, ogni elevazione sarà costruita su dati putridi. La metrica qui è **stale_time > 24h per qualsiasi NB contenente regolamentazione legale** = richiamo obbligatorio.

**Cheap-win vs grande-effort:**
- **Cheap-win (~2 giorni)**: Unico cron runner (tipo `watchdog.py` con `asyncio`) che:
  - Legge un `freshness_config.json` (per NB, frequenza, tolleranza)
  - Esegue ogni pipeline con timeout globale (non 60s ma 90s, perché hai 30-40s reali)
  - Logga success/fail + timestamps in un file JSON o su Redis
  - Notifica su Telegram/email se fail consecutivi >2
- **Grande-effort (settimane)**: Integrare con Qdrant vector versioning e fare rollback automatico se freschezza rotta.

**Red team:** Il singolo cron runner diventa single point of failure. Se `watchdog.py` crasha o perde lock (es. race condition con altri cron), non si accorge del silenzio mortale. **Soluzione:** implementare heartbeat esterno via GitHub Actions o cron Kubernetes-like, ma su una macchina separata (es. Air). Su 48GB M4 Pro, è accettabile un watchdog semplice ma con log persistente.

### 1.2 Continuous Evaluation Pipeline (CEP)

**Cosa:** Un loop che periodicamente (ogni 6h o dopo ogni aggiornamento NB) valuta la qualità del RAG costruito a partire da NLM: test di correttezza, completezza, non-contraddizione su un set di query golden (almeno 50 domande legali tipiche con risposta attesa).

**Perché indispensabile:** Senza evaluation, non sai se l'elevazione sta migliorando o degradando. Oggi il sistema produce risposte ma non c'è feedback quantitativo. Il bug `claim_extractor.py:216` blocca NB-2 da chissà quanto – se ci fosse CEP, sarebbe emerso in ore.

**Cheap-win vs grande-effort:**
- **Cheap-win**: Usa DeepSeek Reasoner ($0.01/query) per generare evaluation su 50 query. Risultati in tabella CSV + alert se hit rate <80% o contraddizione rilevata.
- **Grande-effort**: Pipeline RAGAS-3 con multi-LLM evaluator (Claude + Gemini + DeepSeek) su 500+ query, con version tracking dei punteggi.

**Red team:** Le query golden invecchiano. Se la normativa cambia, le risposte attese diventano obsolete e la CEP dà falsi positivi/negativi. **Soluzione:** Versionare le golden con data di validità e avere un meccanismo di revisione periodica (ogni mese) – cheap: `golden_version_YYYYMMDD.json` su GitHub.

### 1.3 Source Lifecycle Management

**Cosa:** Tracciamento completo del ciclo di vita di ogni source inserita in NLM: provenienza (URL, file, API), data di estrazione, validità (non revocata da fonte ufficiale), ultima data di verifica, checksum. Non solo per NB domain, ma anche per NB-INTEL e NB-1 codebase.

**Perché indispensabile:** Il governo indonesiano cambia regolamenti ogni ~3 mesi con effetto retroattivo. Una source obsoleta produce disinformazione legale con conseguenze reali (visti negati, tasse sbagliate). Senza lifecycle management, ogni NB è una potenziale fake news.

**Cheap-win vs grande-effort:**
- **Cheap-win**: Un file YAML `sources_catalog.yaml` con campi: `notebook: NB-2, source_url, extracted_at, last_verified, next_review, status (active/stale/revoked)`. Aggiornato manualmente a ogni ingesta. Con alert automatico su date scadute.
- **Grande-effort**: CRON per monitorare automaticamente i siti governativi (perubahan peraturan.go.id) e flaggare cambiamenti, con diff automatico.

**Red team:** La manutenzione manuale del YAML è fragile: il solo-dev può dimenticare di aggiornarlo. **Soluzione:** Almeno automatizzare il controllo di scadenza con script Python che legge il YAML e segnala notifiche 2 giorni prima della `next_review`. Non risolve la dimenticanza di update ma la rende visibile.

### 1.4 Multi-Model Reasoning Bus (già abbozzato con Consiglio, non integrato)

**Cosa:** Un bus di reasoning che può interrogare più LLM in parallelo, aggregare risposte e produrre una risposta finale pesata. Esiste Consiglio v1 ma è service Python non integrato nell'orchestrazione e non usa il freshness contract.

**Perché indispensabile:** Per coprire i bias di ciascun modello: Claude è buono su contesto lungo, Gemini è gratis ma a volte hallucina su Indonesia, DeepSeek è forte su reasoning ma lento. Senza bus, usi solo Claude e perdi robustezza.

**Cheap-win vs grande-effort:**
- **Cheap-win**: Modificare `Consiglio` per leggere `freshness_config` e, se un NB è stale, **bloccare la query** e restituire errore anziché dati falsi. Questo è il minimo etico.
- **Grande-effort**: Voting ponderato basato su accuracy storica (dalla CEP). Ogni LLM vota con peso = F1 su golden recente.

**Red team:** Il bus multi-LLM aumenta latenza (3x query). Per risposte real-time (es. chat clienti), può essere inaccettabile. **Soluzione:** Risposta preliminare da Claude in <5s, poi revisione asincrona da DeepSeek/Gemini e invio correzioni via email/notifica. Non ideale ma pragmatico.

### 1.5 Honest Monitoring (non "mente")

**Cosa:** Un dashboard (minimale, tipo `streamlit`) che mostra per ogni NB: freshness (ultimo update, target, delta), stato del cron, errori recenti, valutazione CEP ultima. Nessun mtime finto.

**Perché indispensabile:** Oggi "heartbeat mtime fresco ma ts interno stale 14/04". Questo è autoinganno. Senza monitoraggio onesto, non puoi fare decisioni su elevazione.

**Cheap-win vs grande-effort:**
- **Cheap-win**: Script Python che stampa su stdout `NB-2: stale 12 days` ogni 30 min su cron e manda alert su Telegram/Slack. Tempo: 1 ora.
- **Grande-effort**: Grafana + Prometheus con metriche esposte da FastAPI. Overkill per solo-dev ma dà bella visualizzazione.

**Red team:** Se il monitoraggio stesso non è monitorato (chi controlla il controllore?), può morire silenziosamente. **Soluzione:** Almeno una mail giornaliera automatica con sommario. Se non arriva, è allarme.

---

## 2. Pattern SOTA 2026 applicabili

Ora che le fondamenta sono (ipoteticamente) solide, ecco pattern reali che team top usano e che puoi adattare.

### 2.1 Multi-Notebook Synthesis via Meta-Notebook

**Pattern:** Invece di avere ogni NB isolato, creare un "meta-notebook" (NB-META) che contiene solo sintesi cross-notebook generate automaticamente da NLM stesso (usando la funzione "Sorgenti" di NLM che permette di aggiungere note generate da altri NB). DeepMind Labs ha sperimentato questo per sintesi di paper.

**Mappatura a Nuzantara:** Prendi NB-2 (immigration), NB-3 (company), NB-5 (tax), NB-6 (property): ogni settimana, Claude (via Consiglio) produce un brief "Legal Landscape Bali this week" che viene *importato come source* in NB-META. Poi NB-META serve come contesto rapido per risposte inter-dominio (es. "costituire una società per affittare ville a stranieri: aspetti immigrazione + società + fisco").

**NB/services toccare:** Crea `NB-META-WEEK` (o usa NB-0 ma con sorgenti nuove). Servizio: `meta_synthesizer.py` in RAG pipeline.

**Red team:** Se i brief sono scritti male (allucinazioni), NB-META propaga errori su tutti i domini. **Soluzione:** Ogni brief deve essere validato da DeepSeek Reasoner (costo trascurabile) con instruction "Trova contraddizioni o fatti inventati". Se score <0.7, non pubblicare.

### 2.2 Time-Aware Freshness Scoring

**Pattern:** I top team di legal tech (Relativity, Everlaw) hanno ranking di documenti basato su freschezza *relativa al contesto*. Una legge del 2023 non è "obsoleta" se non è stata abrogata, ma un'interpretazione della corte del 2020 sì. Usare il tempo come feature per vector search.

**Mappatura a Nuzantara:** Ogni chunk in Qdrant ha metadato `effective_date`, `valid_until_date` (se noto). Nella query, aggiungere boost per quelli più recenti entro validità. Usa `payload_filter` di Qdrant su timestamp.

**NB/services toccare:** `embedding_pipeline.py` (aggiungere metadata extraction), `qdrant_client.py` (modificare query filter).

**Red team:** Se `valid_until_date` è sconosciuto (la maggior parte), il ranking può dare peso sbagliato. **Soluzione:** default `valid_until` = NULL significa "non determinato" -> nessun boost/penalty. Richiede però che la CEP valuti la completezza di questi metadati.

### 2.3 Hypothetical Document Embedding (HyDE) Reverse Engineering

**Pattern:** HyDE è noto: genera un documento fittizio con la risposta attesa e lo usa per cercare chunk simili. Il contrarian è **reverse HyDE**: dato un chunk nel database, genera una domanda che lo avrebbe prodotto e mappa quella domanda all'originale. Utile per capire copertura del dataset.

**Mappatura a Nuzantara:** Per ogni chunk legale (es. "Pasal 36 KUHPidana"), genera 5 domande plausibili (con Claudia, costo basso). Aggiungi alle embedding come query-esample. Questo migliora recall su domande formulate in modo colloquiale dai clienti.

**NB/services toccare:** `claim_extractor.py` (devi correggere bug:216 prima), aggiungi modulo `question_generator.py`.

**Red team:** Generare domande per ogni chunk (104k vettori) costa 104k*5*~$0.01 (DeepSeek) = $5200, fuori budget. **Soluzione:** Solo sui chunk più query (Top 5000 per frequenza) e usa Ollama locale (gratis) con modello tipo Mistral: qualità inferiore ma bastano per embedding augmentative.

### 2.4 Deliberative RAG con NLM come Expert Panel

**Pattern:** Invece di RAG semplice (recupera chunk → riassumi), fare deliberazione multi-tour: Claude produce risposta A; Gemini produce B; poi NLM (con NB specifici) viene interrogato per valutare quale delle due è più coerente con le source, restituendo un ranking.

**Mappatura a Nuzantara:** Usa Consiglio v1 in modalità "adjudicator": dopo che Claude ha risposto, chiedi a NLM (tramite export di testo? O via UI browser? Sfida) di valutare. Più realistico: un agente Python che carica la risposta di Claude in un NB temporaneo e chiede "Contraddice questo NB?" via interfaccia simulata (poco pratico).

**Soluzione pragmatica:** Usa DeepSeek Reasoner per il ruolo di adjudicator, non NLM. DeepSeek è economico e capace di ragionamento strutturato. Così "Deliberative RAG" ma con attori Claude + DeepSeek + Gemini.

**NB/services toccare:** `consiglio_v1.py`, `deliberation_router.py`.

**Red team:** Aumenta latenza e costo. Per risposte semplici (es. "Document needed for KITAS?"), non serve deliberazione. **Soluzione:** Solo per query ad alto rischio (contraddizione potenziale, richieste legali complesse) classificate da un classifier veloce (regex + Ollama). Default usare Claude diretto.

### 2.5 Active Learning loop con NLM Queries

**Pattern:** Se il sistema nota (dalla CEP) che su certe query la risposta è poco confidente (bassa similarità media con chunk), può generare una nota di richiesta in NLM che poi un umano può revisionare e aggiungere source. Usato da startup mediche.

**Mappatura a Nuzantara:** Crea NB-ACTIVE-LEARN. Ogni volta che il sistema ha confidence <0.3 su una query legale importante, genera una "draft note" in quel NB con: "Ho bisogno di sapere: <domanda>. Fonti possibili: <url da web search>. Per favore, umano, aggiungi source o rispondi." L'umano (owner) risponde con testo e source, che vengono automaticamente indicizzati.

**NB/services toccare:** `confidence_tracker.py` (nuovo), `human_loop_bridge.py` (probabilmente via file system condiviso). NB-ACTIVE-LEARN in NLM (manuale).

**Red team:** L'owner è solo-dev, probabilmente non risponde in tempo. Le domande si accumulano e il NB diventa rumore. **Soluzione:** Priorità bassa automatica: solo query su temi ad alto impatto (es. "penale") e con frequenza >2/settimana. Le altre vanno in backlog con log.

### 2.6 Cross-Domain Knowledge Injection via Entity Linking (Oltre NLM)

**Pattern:** Non NLM ma knowledge graph: prendi entità da NB legali (leggi, articoli, termini) e le linka automaticamente a news (NB-INTEL) e codebase (NB-1). Crei KG che unisce informazioni.

**Mappatura a Nuzantara:** Oggi hai KG 108k nodi 243k edge. Ma è statico? Aggiungi edge che collegano "UU 6/2023" (legge) a "articolo di news su perubahan tax" (NB-INTEL) a "codice che implementa la verifica tax" (NB-1). Mantieni automaticamente via entiti extration su nuova source.

**NB/services toccare:** `KG_curiosity_loop.py` (estendere per agganciare NLM content), `entity_linker.py` (usando Ollama per NER locale).

**Red team:** Produce falsi positivi nel KG (edge errati). Su 243k edge, pochi falsi possono inquinare le query multi-hop. **Soluzione:** Solo edge con confidence score >0.8 (da DeepSeek Judge) e a lista di edge sospetti che l'owner può approvare/rifiutare via file.

### 2.7 (Bonus) Use NLM as Fault-Injection Tool

**Pattern:** Per testare la robustezza del sistema, inserisci intenzionalmente in NLM source errate o fuorvianti. Poi vedi se il sistema le rileva o risponde con allucinazioni. Metodo usato per auditing di sistemi legali da parte di organizzazioni indipendenti.

**Mappatura a Nuzantara:** Crea NB-SANDBOX-MALICIOUS. Inserisci leggi false (es. "Visa sosial budaya cost now $5000"). Lancia query al RAG standard e verifica se le riproduce. Se sì, la CEP deve fallire quel test. Serve per migliorare i filtri.

**NB/services toccare:** `sandbox_tester.py` (automatizzato settimanalmente), integra con CEP golden set.

**Red team:** Pericolo che source false escano dal sandbox e contaminino NB reali. **Soluzione:** NB-SANDBOX-MALICIOUS mai usato come source per risposte reali. Label esplicita nel metadato "malicious=true" e blocco a livello di orchestrator.

---

## 3. Estensioni oltre i topic attuali

Se Bali Zero fosse più ambiziosa, quali NB mancano? Oltre al dominio legale Indonesia, ecco domini adiacenti che potrebbero dare leva strategica.

### 3.1 NB-DIPLOMACY (domino adiacente: relazioni bilaterali Italia-Bali/Indonesia per espatriati)

**Perché:** I clienti Bali Zero sono spesso expat (Italiani? Ma si, Bali ha molta community italiana). Regole consolari, accordi bilaterali, visti diplomatici, agevolazioni per cittadini europei. Attualmente coperto solo marginalmente da NB-2 (immigration).

**Knowledge graph:** Collega "Italy-Indonesia Double Tax Avoidance" a NB-5 (tax). Questo è un edge nuovo che non esiste oggi.

**Red team:** NB-DIPLOMACY diventa obsoleto rapidamente (cambiano accordi). Senza frescohess contract, è più dannoso che utile. **Soluzione:** Source ufficiali (Ministero Estero italiano, Kemlu Indonesian) con web scrape settimanale automatizzato tramite `freshness_config`.

### 3.2 NB-ECONOMICS-MACRO (domino ortogonale: indicatori economici Bali/Indonesia)

**Perché:** Se Bali Zero è business intelligence, gli esperti possono avere bisogno di contesto macro per decisioni: inflazione, tassi di cambio, turismo inbound. Spesso ogni nuovo business planning richiede queste info.

**Knowledge graph:** Nodi per "GDP", "forex", "tourist arrival" collegati a nodi legali "pajak" (tax) per mostrare impatto.

**Red team:** Dati macro cambiano giornalmente. Un NB che non si aggiorna in tempo reale è inservibile. **Soluzione:** NB-ECONOMICS-MACRO solo per trend mensili/trimestrali, aggiornato via rss (BI.go.id, BPS). Non tentare real-time.

### 3.3 NB-INFRASTRUCTURE & LOGISTICS (adiacente: ottenere permessi per infrastrutture, costruzioni, business reali)

**Perché:** Molti clienti vogliono costruire ville/resort. Permesso di costruire (IMB/PBG), environmental permits, land acquisition. Attualmente non c'è questo NB. È alta complessità.

**Knowledge graph:** Edge tra "property" (NB-6) e "construction permits" (NB-7 eventuale) e "tax on property transaction" (NB-5).

**Red team:** È il dominio più litigioso (corruzione, interpretazioni locali). Le fonti ufficiali possono contraddire la prassi. Se il RAG risponde basandosi solo su regolamenti, dà risposte naive che portano a errori reali. **Soluzione:** Includere NB con prassi di fatto (es. articoli di avvocati locali, forum) ma con label "anecdotal" e riserva nella risposta: "Attenzione: la prassi locale può differire."

### 3.4 NB-META-ON-META (meta-notebook su monitoring dei notebook stessi)

**Pattern:** Oggi NB-0 meta esiste ma a 3 source (da audit: manca). Estendi a NB-META-INTROSPECTION che contiene:
- Log delle ultime freschezza
- Statistiche di utilizzo (quali NB più query dal RAG)
- Performance del sistema (latenza, errori)
- Alert recenti

**Perché:** Per avere una dashboard testuale accessibile anche da Claude via RAG. Non serve solo monitoraggio tecnico; serve per domande tipo "quale dominio è meno aggiornato?" o "quali NB hanno errore di validità?"

**NB/services toccare:** Lo scrive un cron settimanalmente (non real-time). Contiene testo markdown generato da Claude.

**Red team:** Se non viene aggiornato (cron fallisce), diventa disinformazione su se stesso. **Soluzione:** TTL esplicito. Se il file ha più di 7 giorni, il RAG non lo serve. Imposta `metadata.stale=True` in Qdrant.

### 3.5 NB-LIFESTYLE & COMMUNITY (ortogonale: risorse per expat a Bali - sanità, schools, networking)

**Perché:** Oltre al legale, gli expat chiedono spesso "dove fare check-up?" "quali scuole internazionali" "community events". Non c'è oggi. Se il sistema è business intelligence per expat, questi domini aggiungono retention.

**Knowledge graph:** Node "hospital" collegato a "BPJS Ketenagakerjaan" (social security) e "visa" (KITAS permette BPJS). Linkare conoscenze mediche con immigration.

**Red team:** Dominio vasto e in rapido cambiamento (orari, vaccini, dottori). Se la risposta è sbagliata (es. indirizzo clinico chiuso), danneggia fiducia. **Soluzione:** NB-LIFESTYLE solo con fonti ufficiali e aggiornabili via Google My Business API (non costo?). Ma meglio evitare: eccessivo scope creep. Suggerisco di saltare questa estensione per ora, è un ramp risk.

---

## Conclusione: 3 priorità di esecuzione

Dopo questa analisi, il mio piano per l'owner:

1. **Settimana 1-2:** Fondamenta obbligatorie: `freshness_config.yaml` + `watchdog.py` + monitoraggio TS reale. **Rimedi immediati:** fix `claim_extractor.py:216` (bug) e ripristina pipeline cron reali.
2. **Settimana 3-4:** Implementare Continuous Evaluation Pipeline con 50 golden query. DeepSeek Reasoner evaluation quotidiana. Tagliare code che non serve (8/9 pipeline zombie).
3. **Settimana 5-6:** NB-META-WEEK e Time-Aware Freshness Scoring. Poi valutare se aggiungere NB-DIPLOMACY e NB-ECONOMICS-MACRO con contratto di freschezza stretto.

Niente "just add more NBs" senza infrastruttura. Il sistema è fragile, non più di 2 nuovi NB finché fondamenta non sono solide e la CEP non dà >85% di accuracy.

**Inoltre, nota finale:** NotebookLM non ha API. Ogni integrazione è via scraping (pericoloso e fragile) o export manuale. **Considera seriamente di ridurre dipendenza da NLM** per contenuti critici e spostarti su file markdown locali su disco, versione controllata, con stessi metadati ma senza vendor lock-in. Gli NB NLM possono rimanere per interfaccia interattiva umana, non come fonte primaria per RAG. Questo è l'angolo under-explored più potente: liberarsi dalla dipendenza da una piattaforma senza API per un sistema che vuole essere SOTA 2026.

---

**Prossimi passi operativi:** se accetti questa analisi, posso fornire per ciascuna proposta uno pseudocodice/architettura dettagliata (costo in tempo di implementazione). Inoltre, posso aiutare a scrivere il `freshness_config.yaml` e la golden queries per CEP.
