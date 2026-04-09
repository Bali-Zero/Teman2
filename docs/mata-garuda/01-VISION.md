# MATA GARUDA — Vision

> Data: 2026-04-08 | Sessione: deep research S02
> Fonti: Exa Deep Research Pro (121 pagine, 33 ricerche, $1.41), 4 NLM Deep Research (376 fonti totali),
> DeepSeek API (deepseek-chat), Gemini 2.5 Pro CLI, 20+ Web Search, 3 agenti Exa processing
> Notebook NLM creati: 4 (Palantir Ontology, Self-Improving Agents, Indonesia Gov Data, Open Source Intel)

---

## Il Problema Fondamentale

6 sistemi di intelligence frammentati. Un articolo su un cambiamento KITAS non arriva al Knowledge Graph, non aggiorna il dossier del Kanim, non triggera un briefing al cliente, non genera un post Instagram, non corregge Zantara AI.

## La Soluzione: Non un Sistema, un ORGANISMO

Mata Garuda non e' un tool. E' un **organismo di intelligence autonomo** con:
- Percezione (raccolta da centinaia di fonti)
- Cognizione (classificazione, NER, scoring, contradiction detection)
- Memoria (KG + NLM notebooks + Qdrant + MOS)
- Ragionamento (LangGraph agents + NLM synthesis + Claude CLI)
- Azione (distribuzione multi-canale, KB update, OSINT enrichment)
- Crescita (self-improving, auto-expanding, auto-healing)

## Pattern Rubati dai Migliori

### Da Palantir Gotham — L'Ontologia a 3 Layer
[Fonte: Exa Research Pro + NLM 51 fonti]

**Il concetto chiave**: Object Type = table/class, Property = column/field, Link = foreign key/association, Action = stored procedure/method.

Palantir ha 3 layer:

```
SEMANTIC LAYER — "Cosa sono le cose"
  Object Types con proprieta, link types, tipizzazione
  → NEL NOSTRO CASO: Neo4j schema (17 node types gia!)
  → UPGRADE: ontologia DINAMICA che evolve con le strutture di potere

KINETIC LAYER — "Come i dati grezzi diventano oggetti"
  ETL, data lineage, feed operativi, provenance
  → NEL NOSTRO CASO: Workers Layer 2 + NER + Entity Resolution
  → UPGRADE: ogni dato tracciato con hash provenance in PostgreSQL

DYNAMIC LAYER — "Logica di business sugli oggetti"
  Actions, lifecycle states, authorization per-attribute, workflows
  → NEL NOSTRO CASO: Analyst Agents + Quality Gate + Distribution Rules
  → UPGRADE: regole di alert codificate come proprieta del grafo
```

**Insight chiave** (DeepSeek): l'ontologia non e' statica — e' una **tassonomia vivente** che evolve. I nodi possono "generare" nuovi tipi di nodo quando pattern emergenti vengono riconosciuti.

### Da CIA's CATALYST — L'Analista nel Loop
[Fonte: DeepSeek reasoning]

**Il concetto chiave**: Machine propone, umano decide, sistema impara.

```
Ogni intelligence product (briefing, alert) ha bottoni:
  [Conferma] [Nega] [Amplifica]
  
Correzioni dell'analista → retraining automatico NER/classificazione
Tracking attenzione (click, dwell time) → feedback implicito
I giudizi dell'analista sono i MIGLIORI dati di training
```

### Da NSA's XKeyscore — Pattern-of-Life Tracker
[Fonte: DeepSeek reasoning]

**Il concetto chiave**: I pattern temporali rivelano l'intenzione prima dell'azione.

```
INDONESIAN POWER CYCLE DETECTORS:
  - Ciclo elettorale → spike procurement → attivita business famiglie
  - Festivita religiose → annunci policy → shift sentiment social
  - Ciclo budget → rilascio tender → coverage media
  - Mutasi periodiche → vuoti di potere → finestre di opportunita

In Indonesia, il TIMING non e' tutto — e' l'UNICA cosa.
```

### Da Bloomberg Terminal — The Context Machine
[Fonte: DeepSeek + Exa Research]

**Il concetto chiave**: Un keystroke connette tutto. 220K entita tracked, 10K topic, 660K persone, sentiment scoring.

```
GARUDA SHORTCUTS (via MCP tool garuda.query):
  /POL [nome] → dossier + tender recenti + business famiglie + cause
  /COMPANY [nome] → albero proprieta + violazioni + sentiment + competitor
  /CONFLICT [ent1] [ent2] → storia relazione + contraddizioni + timeline
  /DIFF [url] [data] → semantic diff regolamento vs versione precedente
```

### Da Recorded Future — Intelligence Graph + Risk Scoring
[Fonte: Web Search + Exa]

**Il concetto chiave**: Score pesato = novelty + prevalence + severity. Assenza di segnale E' un segnale.

```
SCORING AVANZATO per ogni articolo:
  quality_gate.yaml esistente (relevance, urgency, reliability, business_impact)
  + NOVELTY: e' la prima volta che questa info appare? (vs historical KB)
  + PREVALENCE: quante fonti riportano la stessa info? (cross-validation)
  + VELOCITY: quanto velocemente si sta diffondendo? (trend detection)
  + SILENCE: topic attesi ma ASSENTI nel periodo? (anomaly by absence)
```

### Da Babel Street — Entity Resolution Multilingue
[Fonte: Web Search]

**Il concetto chiave**: Da un nome → profilo multidimensionale, 200+ lingue.

```
BAHASA NUANCE ENGINE (DeepSeek insight):
  - Pattern di indirezione giavanese nelle dichiarazioni ufficiali
  - Marcatori dialettali regionali nei social media
  - Network di onorificenze (Bapak/Ibu) nella corrispondenza
  - In Indonesia, COME qualcosa viene detto conta piu di COSA
```

## Self-Improving: Come il Sistema Diventa Piu Intelligente

### The Reinforcement Flywheel
```
Scrape → Classify → Present → Collect Feedback → Retrain → Improve
```

### Meccanismi Concreti (DeepSeek + AutoAgent research)

1. **Source Reliability Scoring** (automatico):
   - 3 score per fonte: Accuracy, Timeliness, Exclusivity
   - Cross-validazione fatti tra fonti
   - Demote fonti che contraddicono fatti verificati
   - Promote fonti che breaking news poi verificate
   - **Bayesian/EMA updating** dei reliability scores
   - Pesi aggiornati dal meta-agent basato su performance downstream

2. **Meta-Agent Harness Optimization** (AutoAgent pattern):
   - Legge performance correnti (precision, recall, false positives)
   - Propone modifiche (prompt, tool, config, soglie)
   - Testa in sandbox
   - Misura risultato con benchmark automatici + LLM-as-judge
   - Se migliore → adotta, se peggiore → rollback
   - **Model empathy**: stesso modello ottimizza se stesso (6x performance gap)

3. **Contradiction Mining as Training Data**:
   - Sistema trova contraddizioni (Politico A dice X, documento mostra Y)
   - Flag per human review
   - Giudizio umano → labeled data per contradiction detection model

4. **NLM Auto-Specialization**:
   - Quando query ricorrenti su un topic superano soglia
   - Sistema crea automaticamente notebook specializzato
   - Pre-popola con fonti rilevanti, entita, alert

## Power Multiplication: 10x Additions

### Tier 1 — Immediato (gia accessibile)

| Risorsa | Cos'e | Valore |
|---------|-------|--------|
| **suryast/indonesia-civic-stack** | MCP server con 46 tool per 14 fonti gov indonesiane | GAME CHANGER — SDK pronto |
| **suryast/indonesia-gov-apis** | 50+ endpoint governativi documentati | Catalogo scrapers |
| **Pasal.id MCP** | 40K regs, 937K articoli | MCP gia pronto |
| **peraturan.go.id FAISS** | 541K segmenti legali indicizzati | Fork locale |
| **Putusan MA JSON API** | Decisioni Corte Suprema | API pubblica strutturata |
| **Tavily** | 1000 search/mese gratis | Complementare |
| **OpenBB** | Bloomberg Terminal open source | Property/economy intel |

### Tier 2 — Strategico (richiede lavoro)

| Risorsa | Cos'e | Valore |
|---------|-------|--------|
| **TikTok Indonesia** | Massivo, contenuto politico | Social listening expansion |
| **Facebook Groups** | Discussioni comunita locali | Ground truth |
| **Telegram Channels** | Network business/politici | Signal monitoring |
| **KPK** | Tracking casi corruzione | Legal intelligence |
| **e-Court** | Sistema giudiziario elettronico | Court monitoring |
| **AutoAgent** | Framework self-improving open source | Meta-agent |
| **Semantica** | Context graphs + decision intelligence | Accountability layer |
| **worldmonitor** | Dashboard intelligence real-time | Pattern UI |

### Tier 3 — Moonshot

| Risorsa | Cos'e | Valore |
|---------|-------|--------|
| Satellite imagery (Sentinel Hub) | Monitoraggio costruzioni, risorse | Property intelligence |
| Voice intelligence | Trascrizione rapat, hearing DPR | Political intelligence |
| Document forgery detection | Font, firma, sigillo | Security intelligence |
| Shadow economy mapping | Parcheggi, ristoranti, flussi | Proxy data |

## Indonesia-Specific: Il Nostro Vantaggio

### "Pubblico Ma Non Aggregato" (DeepSeek)

1. **LHKPN + BPJS + PBB**: cross-reference asset ufficiali vs proprieta familiari
2. **Banjar Networks** (Bali) + **RT/RW** (Java): strutture leadership locale = ground truth
3. **Pesantren Networks**: attivita economiche, proprieta, endorsement politici
4. **Koperasi**: entita economiche massicce con link politici, poco digitalizzate
5. **Alumni Associations**: UI, ITB, UGM, IPB, Unpad → alleanze business/politiche
6. **Perda** (regolamenti locali): 500+ distretti con regole proprie
7. **SK** (decreti ministeriali): regolamenti temporanei = opportunita

### Predicati Neo4j Indonesia-Specifici (Gemini)

Oltre ai predicati esistenti, aggiungere:
- `TIM_SUKSES_DARI` — parte del team elettorale di
- `KELUARGA_DARI` — famiglia di (con tipo: istri/suami/anak/saudara)
- `ALUMNI_DARI` — alumni di (universita o istituzioni: Akabri, Lemhanas)
- `PEMBANTU_DARI` — assistente/staff di
- `MANTAN_DARI` — ex- (jabatan, relazione)
- `SE_ANGKATAN` — stessa classe/anno di (accademia)
- `BANJAR_DI` — membro banjar di

### Cultural Intelligence Layers (DeepSeek)

- **"Basa-basi" Detector**: distinguere cortesia formale da commitment reale
- **"Musyawarah" Consensus Tracker**: come le decisioni si formano vs verbali ufficiali
- **Regional Power Dynamics**: prospettive Java-centriche vs isole esterne

## Il Cervello NLM che Cresce

### Notebook Domain Strategy

| ID | Notebook | Fonti importate | Status |
|----|----------|-----------------|--------|
| NB-MG-1 | MATA GARUDA — Intelligence Architecture Research | 51 | LIVE |
| NB-MG-2 | MATA GARUDA — Self-Improving Agent Research | 51 | LIVE |
| NB-MG-3 | MATA GARUDA — Indonesia Gov Data Sources | 173 (import parziale) | LIVE |
| NB-MG-4 | MATA GARUDA — Open Source Intel Tools | 89 | LIVE |
| NB-INTEL-1..6 | Domain notebooks (immigration, tax, property, regulation, competitor, economy) | Da creare | PLANNED |

### NLM come Harvester Autonomo

Quando il Daily Briefing Agent identifica un tema emergente senza copertura sufficiente:
1. Lancia NLM Deep Research (gratis, ~40 fonti per research)
2. Risultati ingestiti come articoli enriched nel bus
3. Fonti aggiunte al notebook domain permanente
4. Il sistema diventa **auto-espandente** senza costi

## Distribution Matrix (Gemini)

Ogni intelligence packet genera contenuto per TUTTI i canali contemporaneamente:

| Canale | Audience | Formato | Scopo Strategico |
|--------|----------|---------|-------------------|
| TG Privato Zero | Owner | Tutto, italiano | Comando e controllo |
| Email/Portal | C-Suite clienti | Deep-dive analysis | High-value, high-sensitivity |
| WhatsApp Blast | Base clienti | Snippet + link | Azione immediata |
| Blog/SEO | Inbound leads, pubblico | Long-form evergreen | Attrazione e autorita |
| LinkedIn | Professional network | Summaries, case study | Prestigio e posizionamento |
| Instagram/TikTok | Pubblico giovane | Infografiche, video | Brand awareness |
| X/Twitter | Giornalisti, gov officials | Thread real-time | Influenza in tempo reale |
| TG Channel | Niche groups | Alert specializzati | Community engagement |

**Un singolo cambiamento normativo** → email deep-dive + alert WhatsApp + infografica Instagram + thread X + articolo blog. Tutto automatico, tutto dallo stesso intelligence packet.

## Cosa Rende Mata Garuda DIVERSO da un News Aggregator

**La differenza e' l'ONTOLOGIA.** 

Un news aggregator mostra articoli.
Mata Garuda mostra una **MAPPA VIVENTE** dove:
- Ogni informazione e' collegata a entita, relazioni, pattern temporali
- Ogni entita ha una storia, un contesto, una rete di relazioni
- Ogni cambiamento normativo e' collegato a chi lo ha proposto, chi ne beneficia, chi ne soffre
- Il sistema PREVEDE cosa succedera basandosi su pattern ciclici indonesiani
- Il sistema SCOPRE connessioni nascoste che nessun analista umano vedrebbe

Non e' un feed. E' un **cervello** che costruisce una comprensione sempre piu profonda dell'Indonesia.

---

## Self-Improving: Architetture Concrete (Exa Research)

### PROTEUS — Agente Autonomo Self-Modifying (Reference Implementation)
[Fonte: Exa agent processing, medium.com/@ambitionmagician]

Open source, single-file Python (~2000 lines), gira su consumer hardware (AMD Ryzen 9 + 64GB RAM).

```
Architettura:
- Memory Layer: JSON persistente (beliefs, knowledge, reflections, seen URLs)
- LLM Layer: Ollama locale (dolphin3:8b) + llava:13b per vision
- Action Selection: 20+ tool (browser, search, arXiv, self-modify, shell, Docker)
- Autonomous Cycle: while True → decide → execute → if time_for_self_mod → modify
- Self-Modify: legge il proprio codice, propone patch, syntax-check, backup, applica
```

**Applicazione a Mata Garuda**: PROTEUS e' il template per il meta-agent che ottimizza
harvester, classifier, e scorer. Gira locale su Ollama, nessun costo API.

### Thompson Sampling per Source Discovery
[Fonte: Exa agent, ashitaorbis.com]

Pattern concreto per scoperta autonoma di nuove fonti:

```python
# Surprisal scoring: fonti rare pesano di piu
surprisal(x) = -log2(P(x))

# Esempio: database discovery (1.2% freq) = 6.4 bits
#          version-control (34.3% freq) = 1.5 bits
# → database discovery pesata 4:1 rispetto a version-control

# Thompson Sampling: ogni fonte ha Beta distribution
# successi/fallimenti → allocation automatica
# Fonti che producono buoni risultati → piu budget
# Fonti che non producono → meno budget, ma mai zero (esplorazione)
```

**Shadow Deployment**: esperimenti girano accanto al sistema esistente,
registrano raccomandazioni contraffattuali, non toccano decisioni reali.
Solo dopo threshold di datapoint → valutazione e potenziale adozione.

### Darwin Godel Machine — Self-Rewriting Code
[Fonte: Exa agent, ICML 2025]

"AI che riscrive autonomamente il proprio codice, 150% improvement su benchmark."
"Un sistema che migliora del 10% a settimana non migliora solo del 10% — migliora
nel migliorare." (Compound improvement effect)

### AlphaEvolve (Google DeepMind) — Evolutionary Feedback Loop
[Fonte: Exa agent]

```
LLM Ensemble: Gemini Flash (esplorazione ampia) + Gemini Pro (deep dive)
Automated Evaluators: 10,000x faster verification
Evolutionary Loop: codice scored, mutated, re-sampled per centinaia di iterazioni
```

## Intelligence Briefing: Pattern di Produzione (Exa Research)

### Feedly come Reference Implementation
[Fonte: Exa agent, feedly.com]

Production-grade intelligence briefing system:
- Auto-classifica threat: vulnerabilita, attori malevoli, TTP
- AI Feeds dedicati per tecnologia/settore/ambiente
- Distribuzione: Slack, Teams, Notion, SharePoint, HubSpot
- API e webhook per automazione
- Connettori: OpenCTI, Cortex XSOAR, Anomali, Splunk

**Applicazione**: il nostro Distribution Layer 5 deve funzionare esattamente cosi.
Ogni intelligence product → distribuito automaticamente a N canali via webhook/API.

### STIXAgent — Multi-Agent Report Generation
[Fonte: Exa agent, Georgia Institute of Technology, 2025]

Framework LangGraph che converte report non-strutturati in JSON strutturati:

```
1. Entity Extraction → 2. Field Population → 3. UUID Assignment
→ 4. Validation → 5. Error Handling + Enrichment → 6. Final Summary
```

**Applicazione**: stesso pattern per convertire articoli grezzi in intelligence products
strutturati (briefing, alert, dossier update) con validazione automatica.

### SPRE Controller — Priority Classification
[Fonte: Exa agent, ReadyTensor 2025]

4 fasi di prioritizzazione:
1. Strategic Planning — outline grossolano (depth <= 5)
2. Resource Assessment — stima costo per step, prune nodi a bassa utilita
3. Execution Policy — per step: reasoning diretto vs tool vs sub-planning
4. Synthesis — comprimi output parziali in working memory

Formula: utility attesa - (costo cumulativo token/tool × 0.2 regularizer)

### Urgency-Adaptive Classification (DispatchMAS)
[Fonte: BMC Emergency Medicine 2026]

Il sistema accelera quando la posta e' alta:
- Life-Critical Events: 1.8s per turno (piu veloce)
- Traumatic Incidents: 2.1s
- Individual Complaints: 2.4s (piu lento)

**Applicazione**: il nostro Quality Gate deve pesare la VELOCITA di risposta
in base all'urgency. Regulation change → alert in secondi. Market signal → briefing il giorno dopo.

## Palantir Ontology: Replicazione Tecnica (Exa Agent Report)

### Mapping Completo Palantir → Stack Nostro

| Palantir | Nostro Equivalente |
|----------|-------------------|
| OMS (Ontology Metadata Service) | PostgreSQL schema registry tables |
| Object Databases (OSv2) | Neo4j (graph) + PostgreSQL (tabular) |
| Object Set Service (OSS) | Neo4j Cypher + Qdrant vector search |
| Object Data Funnel | Python ETL workers (Layer 2) |
| Actions service | PostgreSQL action_log + FastAPI endpoints |
| Functions on Objects | Python callable da API |
| Dynamic Security | PostgreSQL RLS + Neo4j property filtering |
| Static Object Sets | Neo4j saved node collections (PKs) |
| Dynamic Object Sets | Saved Cypher query templates, re-executed on read |
| Interfaces (polymorphism) | Neo4j multiple labels per node |

### Microservizi Backend (6 componenti Palantir)

1. **OMS**: definisce tipi di oggetto, link, azioni → PostgreSQL schema
2. **Object Databases**: storage indicizzato per query veloci → Neo4j + indexes
3. **OSS**: reads dall'ontologia, search/filter/aggregate → Cypher + Qdrant
4. **Actions**: modifiche strutturate con permission/conditions → action_log
5. **Data Funnel**: orchestrazione write da datasource → ETL workers
6. **Functions on Objects**: logica eseguibile in contesti operativi → Python scripts

### Open Source Reference: `foundry-ontology-open`
Esiste gia: `github.com/cloudbadal007/foundry-ontology-open` — implementazione
open source dell'architettura a 3 layer di Foundry con bridge OWL/SHACL.

## Google Drive 30TB — Strategy

30TB su Google Drive antonellosiano@gmail.com come archivio intelligence:

```
Struttura proposta:
/MATA-GARUDA/
  /raw-archive/        — Snapshot articoli grezzi (provenance)
  /regulation-snapshots/— Versioni pagine .go.id nel tempo (per semantic diff)
  /nlm-research/       — Output NLM deep research (backup)
  /dossier-archive/    — Dossier OSINT storici (BLINDATO)
  /media-archive/      — Immagini, PDF, documenti OCR
  /training-data/      — Dataset per fine-tuning NER/classification
  /backups/            — PostgreSQL dumps, Neo4j exports
```

Benefici:
- Provenance: ogni articolo archiviato con metadata (quando scraperato, da dove, score)
- Temporal: regolamenti snapshottati settimanalmente per semantic diff
- Training: i giudizi umani (confirm/deny) diventano labeled training data
- Disaster recovery: l'intero KG puo essere ricostruito dai raw archive

## [OPEN] — Micro-punti da approfondire

- [ ] indonesia-civic-stack: valutare i 46 tool, testarli
- [ ] AutoAgent: fork e adattare per Mata Garuda meta-agent
- [ ] worldmonitor: studiare la UI per il nostro dashboard
- [ ] Satellite imagery: costi e fattibilita per Bali property
- [ ] TikTok Indonesia scraping: legalita e fattibilita
- [ ] HUMINT via WhatsApp bot: design del sistema di micro-contatti
- [ ] Cultural intelligence layers: come implementare basa-basi detector
- [ ] Distribution matrix: implementazione pratica multi-canale da single packet
- [ ] Predicati Neo4j Indonesia: aggiornare schema.py con nuovi predicati
- [ ] Scoring avanzato: novelty + prevalence + velocity + silence
