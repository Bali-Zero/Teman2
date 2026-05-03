# Multi-Domain Fusion Architecture: NotebookLM + Zantara

> ⚠️ **STATUS: ARCHIVED / OUTDATED (2026-04-25)**
>
> Questo doc descrive un'architettura **parzialmente smantellata**. Il commit `0c60050e8` ("massive repo cleanup — untrack 739 files") ha rimosso `apps/federation/` come PoC A2A non più attivo (609 righe `a2a_service.py` cancellate). I riferimenti qui sotto a `apps/federation/*` (orchestrator.py, a2a_service.py porta 8087, nlm_auth_bridge.py) **non sono più codice eseguito**.
>
> **Cosa resta vivo**: `MultiAgentCoordinator` (backend/services/rag/multi_agent_coordinator.py), `AgenticRAGOrchestrator` (backend/services/rag/agentic/orchestrator.py), i 7 notebook NotebookLM, le MCP tools.
>
> Questo banner è stato aggiunto per evitare che NB-1 (codebase aggregator) continui a servire questo doc come "architettura attiva". Per lo stato reale aggiornato vedi `research/nlm-elevation/` (audit 2026-04-25).

## Problema

Quando un cliente chiede _"Voglio aprire un ristorante a Bali come straniero -- che visa mi serve, quanto costa la company, e le tasse?"_, la query tocca 3+ domini (Immigration, Company+KBLI, Tax). Ogni dominio ha un notebook NotebookLM dedicato con fonti curate. Il sistema deve:

1. Interrogare i notebook giusti in parallelo
2. Fondere le risposte senza contraddizioni
3. Rispondere in <15 secondi, conciso, via web/WhatsApp/Telegram

## Stato Attuale dell'Infrastruttura

### Cosa esiste gia

| Componente                  | File                                              | Stato                                                                     |
| --------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| **MultiAgentCoordinator**   | `backend/services/rag/multi_agent_coordinator.py` | Attivo (LangGraph, Legal+Financial+Timeline)                              |
| **Federation Orchestrator** | `apps/federation/orchestrator.py`                 | Attivo (dev-time, Qwen classifier)                                        |
| **NotebookLM A2A agent**    | `apps/federation/a2a_service.py` (port 8087)      | Attivo (CLI wrapper `nlm-query`)                                          |
| **NLM Auth Bridge**         | `apps/federation/nlm_auth_bridge.py`              | Attivo (auto re-login + Qdrant fallback)                                  |
| **NLM MCP tools**           | `cross_notebook_query`, `notebook_query`          | Disponibili                                                               |
| **AgenticRAGOrchestrator**  | `backend/services/rag/agentic/orchestrator.py`    | Attivo (client-facing, Gemini Flash)                                      |
| **7 Notebook tematici**     | NotebookLM                                        | Immigration, Company+KBLI, Tax, Property, Operations, Editorial, Codebase |

### Gap critico

Il `MultiAgentCoordinator` (Phase 6) gestisce query multi-dominio con LegalAgent + FinancialAgent + TimelineAgent, ma:

- Usa solo KG + PricingTool + LLM interno (Claude/GPT-4)
- **Non consulta NotebookLM** (i notebook contengono le fonti curate piu autorevoli)
- La sintesi finale e puro LLM senza citation grounding
- Esecuzione sequenziale (legal -> financial -> timeline -> synthesize), non parallela

Il Federation Orchestrator usa NotebookLM, ma:

- E un tool dev-time (CLI, non client-facing)
- Non ha la fusione multi-notebook strutturata
- Non e integrato nel flusso Zantara (web chat/WhatsApp/Telegram)

---

## Architettura Proposta: "Domain Fusion Pipeline"

### Pattern: Fan-Out / Fan-In con Arbiter

```
                     +-------------------+
                     |  Client Query     |
                     | "ristorante Bali" |
                     +--------+----------+
                              |
                     +--------v----------+
                     | 1. DECOMPOSER     |  <-- Gemini Flash (economico, <1s)
                     | Identifica domini |
                     | + sub-query per   |
                     |   ciascuno        |
                     +--------+----------+
                              |
              +---------------+---------------+
              |               |               |
     +--------v------+ +-----v--------+ +----v---------+
     | 2a. NLM Query | | 2b. NLM Query| | 2c. Pricing  |  <-- FAN-OUT parallelo
     | Immigration   | | Company+KBLI | | Tool + Tax   |
     | notebook      | | notebook     | | notebook     |
     +--------+------+ +-----+--------+ +----+---------+
              |               |               |
              +---------------+---------------+
                              |
                     +--------v----------+
                     | 3. ARBITER        |  <-- Gemini Flash (o Haiku per costo)
                     | - Rileva conflitti|
                     | - Marca certezze  |
                     | - Segnala gap     |
                     +--------+----------+
                              |
                     +--------v----------+
                     | 4. COMPOSER       |  <-- Gemini Flash con channel overlay
                     | - Fonde in 1 msg |
                     | - Applica formato |
                     |   canale (WA/web) |
                     | - Max ~300 parole |
                     +--------+----------+
                              |
                     +--------v----------+
                     |  Zantara Response  |
                     |  (web/WA/Telegram) |
                     +--------------------+
```

### Perche questo pattern

| Alternativa                                 | Pro                             | Contro                                 | Verdetto        |
| ------------------------------------------- | ------------------------------- | -------------------------------------- | --------------- |
| **Sequenziale** (un dominio alla volta)     | Semplice                        | 3x latenza (3 x 5s = 15s solo NLM)     | Troppo lento    |
| **Gerarchico** (un agente "manager" smista) | Intelligente routing            | Complessita infra, latenza raddoppia   | Over-engineered |
| **Fan-out/Fan-in**                          | Parallelo, <8s totali, semplice | Serve merger intelligente              | **Scelto**      |
| **Singolo prompt mega-context**             | Zero orchestrazione             | NLM ha 1 query = 1 notebook, non multi | Impossibile     |

---

## Componenti in Dettaglio

### 1. Decomposer (Domain Router)

**Cosa fa:** Prende la query originale, identifica i domini coinvolti, e genera una sub-query ottimizzata per ogni notebook.

**Implementazione:** Un singolo prompt Gemini Flash (~200 token output, <1s).

```python
DECOMPOSE_PROMPT = """Analyze this client question for a Bali business services company.
Identify which knowledge domains are needed and create a focused sub-query for each.

Available domains:
- IMMIGRATION: visas, KITAS, KITAP, work permits, stay permits
- COMPANY: PT PMA, PT PMDN, company setup, KBLI codes, OSS, NIB
- TAX: PPh, PPN, SPT, NPWP, tax reporting, withholding
- PROPERTY: land, buildings, zoning, HGB, Hak Pakai
- PRICING: Bali Zero service fees (always include if cost is asked)

Client question: "{query}"

Respond ONLY with JSON:
{{
  "domains": ["IMMIGRATION", "COMPANY", "TAX"],
  "sub_queries": {{
    "IMMIGRATION": "What visa does a foreigner need to own/manage a restaurant in Bali?",
    "COMPANY": "What KBLI code and company type (PT PMA) is needed for a restaurant in Bali?",
    "TAX": "What taxes apply to a foreign-owned restaurant business in Indonesia?"
  }},
  "needs_pricing": true,
  "complexity": "multi_domain"
}}"""
```

**Perche Gemini Flash:** Costa ~$0.0001 per classificazione. Il Decomposer non deve "ragionare" in profondita -- deve solo capire "di quali domini parla questa domanda?" e riscrivere sub-query chiare.

**Fallback:** Se Gemini Flash fallisce, keyword matching (gia implementato in `requires_multi_agent()`).

### 2. Fan-Out: Query Parallele a NotebookLM

**Cosa fa:** Lancia N query in parallelo, una per notebook tematico. Il pricing passa per `PricingTool` (non NLM).

**Implementazione:** `asyncio.gather()` con timeout per-query di 10s.

```python
async def fan_out_notebooks(
    sub_queries: dict[str, str],
    needs_pricing: bool,
) -> dict[str, DomainResult]:
    """Query multiple notebooks in parallel with timeout."""

    tasks = {}
    for domain, sub_query in sub_queries.items():
        notebook_id = DOMAIN_TO_NOTEBOOK[domain]
        tasks[domain] = query_notebook(notebook_id, sub_query)

    if needs_pricing:
        tasks["PRICING"] = get_pricing_context(sub_queries)

    results = {}
    gathered = await asyncio.gather(
        *[asyncio.wait_for(t, timeout=10.0) for t in tasks.values()],
        return_exceptions=True,
    )

    for domain, result in zip(tasks.keys(), gathered):
        if isinstance(result, Exception):
            logger.warning("Domain %s failed: %s", domain, result)
            results[domain] = DomainResult(
                domain=domain,
                status="failed",
                content="",
                error=str(result),
            )
        else:
            results[domain] = DomainResult(
                domain=domain,
                status="ok",
                content=result.text,
                citations=result.citations,
            )

    return results
```

**Notebook mapping:**

```python
DOMAIN_TO_NOTEBOOK = {
    "IMMIGRATION": "immigration-notebook-id",
    "COMPANY": "company-kbli-notebook-id",
    "TAX": "tax-notebook-id",
    "PROPERTY": "property-notebook-id",
}
```

**Come si interroga NLM:** Due opzioni, in ordine di preferenza:

1. **MCP `notebook_query`** -- diretto, gia funzionante via MCP bridge
2. **MCP `cross_notebook_query`** -- se la query attraversa 2+ notebook (NLM lo gestisce nativamente)

**Fallback se NLM e down:** Qdrant RAG via `recall_similar` (gia implementato in `a2a_service.py` linea 256-267). Perde le citazioni ma mantiene le risposte.

**Latenza attesa:** 3-8s per notebook (NLM e veloce sui notebook gia caricati). Essendo parallelo, il totale e `max(tempi)` non `sum(tempi)`.

### 3. Arbiter (Conflict Detector + Confidence Marker)

**Cosa fa:** Prende le N risposte dei notebook e:

1. Rileva contraddizioni fattuali (es. "capitale minimo 10B IDR" vs "2.5B IDR")
2. Marca il livello di certezza per ogni affermazione
3. Segnala gap (dominio richiesto ma risposta mancante/fallita)

**Implementazione:** Un prompt Gemini Flash con le risposte come input.

```python
ARBITER_PROMPT = """You are a fact-checker for Indonesian business regulations.
You received answers from multiple specialized knowledge bases.
Your job is to:

1. DETECT CONTRADICTIONS: If two sources give different numbers/dates/requirements,
   flag it as "[VERIFY]" and use the MORE CONSERVATIVE answer.
2. MARK CONFIDENCE:
   - [CONFIRMED] = consistent across sources or from official regulation
   - [LIKELY] = from one source, consistent with general knowledge
   - [VERIFY] = contradicted or uncertain, client should confirm with team
3. FLAG GAPS: If a domain query failed, note what information is missing.

Domain responses:
{domain_responses}

Output a merged factual summary with confidence markers.
Keep it factual, no fluff. Use bullet points."""
```

**Perche l'Arbiter e cruciale:**

- NotebookLM e ottimo per single-domain, ma non fa cross-validation
- Due notebook possono avere dati di anni diversi (es. capitale minimo cambiato nel 2024)
- L'Arbiter non inventa -- prende il piu conservativo e marca `[VERIFY]`

**Regola d'oro per conflitti:**

```
SE due fonti si contraddicono:
  -> Usa la risposta PIU RESTRITTIVA (protegge il cliente)
  -> Marca come [VERIFY]
  -> Aggiungi "Bali Zero puo confermare il dato aggiornato"
```

### 4. Composer (Channel-Aware Response Builder)

**Cosa fa:** Prende l'output dell'Arbiter e lo formatta per il canale di destinazione.

**Implementazione:** Riusa il `channel_overlays.py` gia esistente nel backend.

```python
COMPOSE_PROMPT = """You are Zantara, Bali Zero's AI assistant.
Create a single coherent response for the client from this verified information.

Verified facts:
{arbiter_output}

Channel: {channel}  (web_chat | whatsapp | telegram)
Language: {detected_language}

Rules:
- Web chat: markdown ok, max 400 words
- WhatsApp: no markdown, max 250 words, use emoji sparingly
- Telegram: markdown ok, max 300 words
- ALWAYS end with a call-to-action ("Contact us for exact pricing" or "Book a consultation")
- Group related info (don't repeat yourself)
- If [VERIFY] items exist, mention "Our team can confirm the latest figures"
- Use Bali Zero's tone: professional, warm, knowledgeable

Structure:
1. Direct answer to the main question (1-2 sentences)
2. Key details per domain (bullet points)
3. Next steps / call-to-action"""
```

**Perche un passo separato (non dentro l'Arbiter):**

- L'Arbiter produce fatti strutturati (per audit e debug)
- Il Composer produce testo per umani (per il canale specifico)
- Separandoli, possiamo cambiare il tono senza toccare la logica di fatto-checking
- Il Composer puo essere cachato per canale diverso (stessi fatti, formato diverso)

---

## Gestione Errori e Fallback

### Matrice di fallback per ogni fase

| Fase           | Errore                   | Fallback                                  | Latenza aggiunta    |
| -------------- | ------------------------ | ----------------------------------------- | ------------------- |
| **Decomposer** | Gemini Flash timeout     | Keyword matching (`requires_multi_agent`) | +0s (instant)       |
| **NLM Query**  | NotebookLM down          | Qdrant RAG `recall_similar` (gia impl.)   | +1-2s               |
| **NLM Query**  | Auth expired             | `nlm_auth_bridge.py` auto re-login        | +2-5s (prima volta) |
| **NLM Query**  | 1 notebook su 3 fallisce | Risposta parziale + "[info missing]"      | +0s                 |
| **Arbiter**    | Gemini Flash timeout     | Skip arbiter, passa raw a Composer        | +0s                 |
| **Composer**   | Gemini Flash timeout     | Concatena le risposte con header          | +0s                 |

### Principio: Graceful Degradation, Mai Silenzio

```python
if all_notebooks_failed:
    # Fallback totale: usa il flusso esistente (Gemini Flash + tools)
    return await self.core.process_query_core(query, ...)

if some_notebooks_failed:
    # Risposta parziale + disclosure
    arbiter_input += "\n[GAP] Tax information unavailable, suggest client contacts team"
```

---

## Budget Latenza (<15s target)

| Fase                    | Latenza stimata | Note                                 |
| ----------------------- | --------------- | ------------------------------------ |
| Decomposer              | 0.5 - 1.0s      | Gemini Flash, prompt corto           |
| Fan-out NLM (parallelo) | 3.0 - 8.0s      | `max(3 notebook queries)`, non somma |
| Arbiter                 | 0.5 - 1.5s      | Gemini Flash, ~500 token input       |
| Composer                | 0.5 - 1.0s      | Gemini Flash, ~300 token output      |
| **TOTALE**              | **4.5 - 11.5s** | Dentro il target di 15s              |

**Ottimizzazione futura:** Il Decomposer e il primo notebook query possono essere pipelinate (invia la prima sub-query appena il primo dominio e identificato, prima che la decomposizione sia completa).

---

## Integrazione nel Sistema Esistente

### Dove si inserisce

Il Domain Fusion Pipeline si inserisce come alternativa al `MultiAgentCoordinator` nel flusso di `OrchestratorCore.process_query_core()`:

```python
# In orchestrator_core.py, dopo entity extraction

if requires_multi_domain_fusion(query, extracted_entities):
    # NUOVO: Domain Fusion Pipeline (NLM-backed)
    result = await self.domain_fusion.process(
        query=query,
        user_context=user_context,
        channel=channel,
    )
    return result

elif requires_multi_agent(query, entity_list):
    # ESISTENTE: MultiAgentCoordinator (KG + Pricing + LLM)
    result = await self._multi_agent_coordinator.process(query, user_context)
    # ... wrap in CoreResult
```

### Quando si attiva il Domain Fusion vs MultiAgentCoordinator

```python
def requires_multi_domain_fusion(query: str, entities: dict) -> bool:
    """Detect if query needs NLM-backed multi-domain fusion.

    Triggers Domain Fusion when:
    - 2+ distinct business domains detected (immigration, company, tax, property)
    - Query is client-facing (not dev/ops)
    - NotebookLM is healthy

    Falls back to MultiAgentCoordinator when:
    - NLM is down (uses KG + PricingTool instead)
    - Only 1 domain (single notebook_query is sufficient)
    - Query is about operations/codebase (dev notebooks, not client)
    """
    CLIENT_DOMAINS = {"IMMIGRATION", "COMPANY", "TAX", "PROPERTY"}

    detected = detect_domains(query, entities)
    client_domains = detected & CLIENT_DOMAINS

    if len(client_domains) < 2:
        return False

    # Check NLM health (cached, <1ms after first check)
    if not is_nlm_healthy():
        logger.info("NLM unhealthy, falling back to MultiAgentCoordinator")
        return False

    return True
```

### File da creare/modificare

| File                                                | Azione        | Descrizione                                                 |
| --------------------------------------------------- | ------------- | ----------------------------------------------------------- |
| `backend/services/rag/domain_fusion.py`             | **NUOVO**     | Pipeline completa: Decomposer + FanOut + Arbiter + Composer |
| `backend/services/rag/agentic/orchestrator_core.py` | **MODIFICA**  | Aggiungere branch `requires_multi_domain_fusion()`          |
| `backend/services/rag/multi_agent_coordinator.py`   | **INVARIATO** | Resta come fallback quando NLM e down                       |

**Un singolo file nuovo (`domain_fusion.py`) contiene tutto il pipeline.** Nessun microservizio separato, nessun container aggiuntivo, nessuna nuova porta da gestire. E un modulo Python che usa `httpx` per NLM e Gemini Flash.

---

## Esempio End-to-End: "Ristorante a Bali come straniero"

### Input

```
Query: "Voglio aprire un ristorante a Bali come straniero -- che visa mi serve, quanto costa la company, e le tasse?"
Channel: web_chat
Language: it
```

### Step 1: Decomposer (0.8s)

```json
{
  "domains": ["IMMIGRATION", "COMPANY", "TAX"],
  "sub_queries": {
    "IMMIGRATION": "What visa and work permit does a foreigner need to own and manage a restaurant business in Bali, Indonesia?",
    "COMPANY": "What company type (PT PMA), KBLI code, and minimum capital is required to open a restaurant in Bali as a foreign investor?",
    "TAX": "What taxes (PPh, PPN, regional taxes) apply to a foreign-owned restaurant business in Indonesia?"
  },
  "needs_pricing": true,
  "complexity": "multi_domain"
}
```

### Step 2: Fan-Out (5.2s -- parallel, bottleneck = slowest notebook)

**IMMIGRATION notebook** (4.1s):

> A foreigner managing a restaurant in Bali needs:
>
> - **Investor KITAS (Index 313)** -- for the investor/director of the PT PMA
> - **RPTKA** (Foreign Worker Utilization Plan) -- must be approved before KITAS application
> - Alternatively, **KITAS Sponsor** if married to Indonesian citizen
> - Visa valid for 1 year, renewable annually, max 5 years before KITAP
>   [Source: Immigration Regulation PP 48/2023, Art. 52]

**COMPANY notebook** (5.2s):

> For a restaurant business:
>
> - **PT PMA** (foreign-owned limited liability company) required
> - **KBLI 56101** -- "Restoran/Rumah Makan"
> - Minimum investment: **Rp 10,000,000,000** (10B IDR, ~USD 625,000) per BKPM regulation
> - Capital per share: **Rp 2,500,000,000** (2.5B IDR) minimum for food & beverage sector
> - NIB via OSS required, medium-low risk classification
>   [Source: PP 5/2021 (Risk-Based Licensing), BKPM Investment List 2024]

**TAX notebook** (3.8s):

> Restaurant taxes in Indonesia:
>
> - **PPh Badan (Corporate Income Tax)**: 22% of net profit
> - **PPh 21**: Withholding tax on employee salaries
> - **PPN (VAT)**: 11% on services if annual revenue > Rp 4.8B
> - **Pajak Restoran (Restaurant Tax)**: 10% regional tax (replaces PPN for restaurants in many regions)
> - **PPh 23**: 2% on service payments to third parties
> - Monthly SPT reporting required, annual SPT by April 30
>   [Source: UU HPP 7/2021, Perda Badung 2019]

**PRICING** (0.3s -- PricingTool, local):

> PT PMA setup: Rp 20,000,000 (Bali Zero fee)
> Investor KITAS: Rp 15,000,000 (Bali Zero fee)
> Annual tax consulting: Rp 5,000,000/month

### Step 3: Arbiter (1.1s)

```markdown
## Verified Facts

**IMMIGRATION** [CONFIRMED]

- Investor KITAS (Index 313) required for foreign restaurant owner
- RPTKA approval prerequisite
- 1-year validity, renewable up to 5 years

**COMPANY** [CONFIRMED]

- PT PMA required, KBLI 56101 (Restoran)
- Investment minimum: Rp 10B (BKPM regulation) [CONFIRMED]
- Capital per share: Rp 2.5B minimum [CONFIRMED]
- NIB via OSS, medium-low risk

**TAX** [CONFIRMED]

- Corporate tax 22%, restaurant tax 10% (regional, often replaces PPN)
- PPh 21 on salaries, PPh 23 on services
- Monthly SPT filing required

**PRICING (Bali Zero)** [CONFIRMED - from PricingTool]

- PT PMA setup: Rp 20,000,000
- Investor KITAS: Rp 15,000,000
- Tax consulting: from Rp 5,000,000/month

**GAPS**: None
**CONTRADICTIONS**: None
```

### Step 4: Composer (0.9s) -- web_chat format, Italian

```markdown
**Aprire un ristorante a Bali come straniero: ecco cosa serve**

Per aprire un ristorante servono tre cose principali: la company giusta, il visto, e la gestione fiscale.

**Company (PT PMA)**

- Serve una PT PMA con codice KBLI 56101 (Restoran)
- Investimento minimo: Rp 10 miliardi (~USD 625.000)
- Registrazione via OSS, classificazione rischio medio-basso
- Costo Bali Zero: **Rp 20.000.000**

**Visto (Investor KITAS)**

- Come direttore/investitore ti serve un Investor KITAS (Index 313)
- Prerequisito: approvazione RPTKA
- Validita 1 anno, rinnovabile fino a 5 anni
- Costo Bali Zero: **Rp 15.000.000**

**Tasse**

- Imposta sul reddito societario: 22%
- Tassa ristorante regionale: 10% (al posto dell'IVA per la ristorazione)
- PPh 21 sugli stipendi, dichiarazione SPT mensile obbligatoria
- Consulenza fiscale Bali Zero: da **Rp 5.000.000/mese**

**Prossimi passi:** Contattaci per un preventivo personalizzato e una timeline dettagliata per il tuo progetto. Possiamo gestire tutto il processo dall'inizio alla fine.
```

**Tempo totale: 0.8 + 5.2 + 1.1 + 0.9 = ~8.0 secondi** (dentro il target di 15s).

---

## Gestione Conflitti: Esempio Concreto

Se il notebook Tax dicesse "PPN 11% su tutti i ristoranti" e il notebook Company dicesse "i ristoranti pagano pajak restoran 10%, non PPN":

### Arbiter output:

```
**TAX** [VERIFY]
- PPN 11% vs Restaurant Tax 10%: CONFLITTO RILEVATO
- Regola: Molte regioni sostituiscono PPN con pajak restoran per la ristorazione
  (Perda Badung, Perda Denpasar). La situazione dipende dalla localita esatta.
- AZIONE: Usare risposta conservativa (menzionare entrambi) + suggerire verifica
```

### Composer output:

```
**Tasse**
- Il regime fiscale dipende dalla localita esatta. In molte aree di Bali, i ristoranti
  pagano la **tassa ristorante regionale (10%)** invece dell'IVA standard (PPN 11%).
  Il nostro team fiscale puo confermare quale regime si applica alla tua location specifica.
```

---

## Costi Stimati

| Componente                | Costo per query | Note                                            |
| ------------------------- | --------------- | ----------------------------------------------- |
| Decomposer (Gemini Flash) | ~$0.0001        | ~200 token output                               |
| 3x NLM queries            | $0.00           | Google AI Ultra subscription, no per-query cost |
| PricingTool               | $0.00           | Local lookup                                    |
| Arbiter (Gemini Flash)    | ~$0.0003        | ~800 token input, ~300 output                   |
| Composer (Gemini Flash)   | ~$0.0002        | ~500 token input, ~400 output                   |
| **TOTALE per query**      | **~$0.0006**    | ~$0.60 per 1000 query multi-dominio             |

Confronto con il flusso attuale (MultiAgentCoordinator con Claude Sonnet):

- Claude Sonnet 4.5: ~$0.015 per query multi-dominio (3 agent calls + synthesis)
- **Risparmio: ~96%** passando a Gemini Flash + NLM

---

## Piano di Implementazione

### Fase 1: MVP (1-2 giorni)

1. Creare `backend/services/rag/domain_fusion.py` (~300 righe)
   - Decomposer con Gemini Flash
   - Fan-out con `notebook_query` MCP (o `cross_notebook_query`)
   - Arbiter con Gemini Flash
   - Composer con Gemini Flash + channel overlay
2. Aggiungere `requires_multi_domain_fusion()` in orchestrator_core.py
3. Test con 5 query multi-dominio rappresentative
4. Feature flag: `ENABLE_DOMAIN_FUSION=true` (default false)

### Fase 2: Hardening (3-5 giorni)

1. Fallback completo: NLM down -> Qdrant RAG -> MultiAgentCoordinator
2. Cache: stesso decompose result per query simili (semantic cache)
3. Metriche Prometheus: latenza per fase, hit rate NLM, conflitti rilevati
4. Test suite: 20+ query multi-dominio, coprendo tutti i casi edge

### Fase 3: Ottimizzazione (opzionale)

1. Pipeline streaming: Decomposer invia sub-query appena identifica un dominio
2. NLM batch: `cross_notebook_query` con i notebook IDs specifici
3. Response cache: stesse risposte NLM per query semanticamente identiche (24h TTL)
4. A/B test: Domain Fusion vs MultiAgentCoordinator su metriche di soddisfazione

---

## Decisioni Architetturali (ADR)

### ADR-1: Perche Gemini Flash per Decomposer/Arbiter/Composer (non Haiku o Sonnet)

- Flash e sufficiente per classificazione e merge (non servono capacita di ragionamento profondo)
- Costa 10x meno di Sonnet
- Gia usato come modello primario in Zantara (latenza nota, fallback gia implementato)
- Il "ragionamento profondo" lo fa NotebookLM (che usa Gemini Ultra internamente)

### ADR-2: Perche NotebookLM e non Qdrant RAG diretto

- NLM ha fonti curate e verificate manualmente per ogni dominio
- NLM produce citazioni esatte (pagina, paragrafo) -- Qdrant no
- NLM "ragiona" sulle fonti (non solo similarity matching)
- Qdrant e il fallback quando NLM e down (gia implementato)

### ADR-3: Perche un Arbiter separato (non fonde direttamente nel Composer)

- Separation of concerns: fact-checking != formatting
- L'Arbiter produce output strutturato auditabile (per debug e compliance)
- Il Composer puo cambiare per canale senza toccare la logica di validazione
- Se l'Arbiter trova un conflitto critico, puo escalare prima che il Composer risponda

### ADR-4: Perche non usare A2A protocol per questo

- A2A e per comunicazione inter-agente a lungo termine (dev-time workflows)
- Il Domain Fusion e un pipeline sincrono sub-15s (non serve stato persistente)
- Aggiungere A2A aggiungerebbe 8 servizi da avviare, porte da gestire, e complessita operativa
- Un modulo Python con `asyncio.gather()` fa lo stesso lavoro con zero infrastruttura extra

### ADR-5: Perche mantenere MultiAgentCoordinator come fallback

- MultiAgentCoordinator usa KG (34K nodi) e PricingTool -- dati diversi da NLM
- Quando NLM e down, il sistema non si ferma
- Per query "costo + timeline" senza multi-dominio, MultiAgentCoordinator e piu veloce (no NLM)
- Progressivamente, Domain Fusion assorbira i casi del MultiAgentCoordinator

---

## Monitoraggio

### Metriche chiave

```python
# In domain_fusion.py
domain_fusion_requests = Counter(
    'domain_fusion_requests_total',
    'Total domain fusion requests',
    ['status', 'num_domains']
)

domain_fusion_duration = Histogram(
    'domain_fusion_duration_seconds',
    'Domain fusion total duration',
    buckets=[2, 5, 8, 10, 15, 20]
)

domain_fusion_nlm_latency = Histogram(
    'domain_fusion_nlm_latency_seconds',
    'Per-notebook NLM query latency',
    ['domain'],
    buckets=[1, 2, 3, 5, 8, 10]
)

domain_fusion_conflicts = Counter(
    'domain_fusion_conflicts_total',
    'Contradictions detected by arbiter',
    ['domain_pair']
)

domain_fusion_fallbacks = Counter(
    'domain_fusion_fallbacks_total',
    'Fallback activations',
    ['reason']  # nlm_down, timeout, auth_expired
)
```

### Alerting

- **domain_fusion_duration_seconds p95 > 12s** -> Investigate NLM latency
- **domain_fusion_fallbacks_total rate > 5/hour** -> NLM health issue
- **domain_fusion_conflicts_total spike** -> Notebook content may be outdated, review sources
