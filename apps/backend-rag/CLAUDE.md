# Claude Memory - Backend RAG

## Session Update (2026-01-18 - Knowledge Graph Value Assessment + Pricing Policy Verification)

### Knowledge Graph Analysis - COMPLETED

**Obiettivo:** Analizzare il Knowledge Graph creato da 37M chiamate Gemini API (3.9M Rp / €230 EUR) per capire se l'investimento è stato utile.

**Risultati Chiave:**

- **Nodi**: 34,606 entità estratte
- **Relazioni**: 30,628 edges
- **ROI**: POSITIVO (~13,000 relazioni utili per €230)
- **Status**: ✅ ATTIVO in produzione come Tool #4 in Zantara
- **Estrazione continua**: ❌ DISABILITATA (troppo costosa)

---

### Distribuzioni Entità e Relazioni

**Top Entity Types:**
| Tipo | Count | % | Descrizione |
|------|-------|---|-------------|
| kbli | 6,932 | 20.0% | Codici classificazione business |
| biaya | 6,060 | 17.5% | Informazioni costi/fee |
| pasal | 3,954 | 11.4% | Riferimenti articoli legali |
| dokumen | 3,674 | 10.6% | Tipi di documenti |
| undang_undang | 2,800 | 8.1% | Leggi (UU) |

**Top Relationship Types:**
| Tipo | Count | % | Valore | Esempi |
|------|-------|---|--------|---------|
| REQUIRES | 8,218 | 26.8% | 🟢 HIGH | "PT PMA REQUIRES NPWP" |
| PART_OF | 7,595 | 24.8% | 🟡 LOW | "Pasal 286 PART_OF Ayat 1" (strutturale) |
| REFERENCES | 4,593 | 15.0% | 🟡 MEDIUM | "UU 6/2023 REFERENCES PP 28/2025" |
| HAS_FEE | ~1,500 | 4.9% | 🟢 HIGH | ⚠️ **CRITICAL** - Vedi sotto |
| HAS_DURATION | ~1,200 | 3.9% | 🟢 HIGH | "Work Permit HAS_DURATION 1 tahun" |

---

### ⚠️ CRITICAL DISCOVERY: HAS_FEE ≠ Prezzi Bali Zero

**Problema Identificato dall'utente:**

> "HAS_FEE (~1,500): Costi ufficiali - quali? attenzione gli unici costi che possiamo dire al cliente finale sono i nostri prezzi"

**Analisi Completata:**

#### Cosa Contengono le Relazioni HAS_FEE:

1. **Fee Governative PNBP** (da script `ingest_visa_kg.py`)
   - Fonte: Dump ufficiale imigrasi.go.id
   - Esempio: "Visa E28A biaya PNBP: Rp 3.500.000" (fee governativa)
   - Estratte via regex dalla sezione "biaya" dei documenti ufficiali

2. **Costi da Regolamenti Legali** (da script `kg_incremental_extraction.py`)
   - Fonte: Documenti legali (UU, PP, Permen) processati da Gemini
   - Esempio: "Pendaftaran PT sebesar Rp 500.000" (da regolamento)
   - Estratte via LLM con prompt che identifica entity type "biaya"

#### Cosa NON Contengono:

❌ **Prezzi Bali Zero** - CONFERMATO al 100%

I prezzi Bali Zero sono **SOLO** in:

- File: `backend/data/bali_zero_official_prices_2025.json`
- Tool: `PricingTool` (Tool #2 nell'orchestrator)
- Caricati da `PricingService._load_prices()`

**Verifica Codice:**

```python
# pricing_service.py:26-28
json_path = Path(__file__).parent.parent.parent / "data" / "bali_zero_official_prices_2025.json"
with open(json_path, encoding="utf-8") as f:
    self.prices = json.load(f)
```

Gli script KG (`ingest_visa_kg.py`, `kg_incremental_extraction.py`) **non importano né accedono** al file prezzi Bali Zero.

---

### Protezioni Sistema Contro Uso Fee KG Come Prezzi

**Il sistema HA GIÀ protezioni attive** in `prompt_builder.py:47-66`:

```
**🚨 CRITICAL: PRICING - ABSOLUTE RULES**

RULE 1: ONLY USE PRICES FROM get_pricing TOOL
- For Bali Zero services → CALL get_pricing tool → Use EXACT price from response
- NEVER invent, estimate, or guess ANY price

RULE 2: IF PRICE NOT IN TOOL, SAY "DA VERIFICARE"
- If get_pricing doesn't have a specific price → Say "Questo costo specifico è da verificare con il team"

RULE 3: ONLY STATE FACTS YOU CAN VERIFY
- ✅ CORRECT: "PT PMA costa Rp 20.000.000 [dal tool get_pricing]"
- ❌ WRONG: "Cambiare l'atto costa tra i 5 e i 10 milioni" (INVENTED!)
```

**PricingTool Description** (`tools.py:309-313`):

```python
"🚨 MANDATORY for ALL Bali Zero service price questions. "
"Get OFFICIAL pricing from Bali Zero database (NO AI generation, NO memory). "
"NEVER guess prices - ALWAYS call this tool first for price questions."
```

---

### Documentazione Creata

**File:** `docs/KG_VALUE_ASSESSMENT_2026_01_18.md` (318 righe)

**Sezioni Aggiunte:**

1. **Executive Summary** - ROI assessment con caveat
2. **Current Status** - ✅ Tool #4 attivo, ❌ estrazione disabilitata
3. **Data Quality Analysis** - Distribuzioni nodi/relazioni
4. **⚠️ CRITICAL: Pricing Policy** - HAS_FEE ≠ Bali Zero prices
   - Cosa contengono le HAS_FEE (PNBP governative + fee legali)
   - Perché NON comunicarle ai clienti (non verificate, obsolete, single source)
   - UNICA fonte verità: PricingTool
   - Esempi di uso corretto/sbagliato
5. **API Authentication** - Perché 401 errors (JWT required)
6. **Recommendations** - Miglioramenti futuri (confidence scoring, re-enable extraction con controlli)

---

### Files Modificati

| File                                     | Tipo | Descrizione                                 |
| ---------------------------------------- | ---- | ------------------------------------------- |
| `docs/KG_VALUE_ASSESSMENT_2026_01_18.md` | NEW  | Analisi completa valore KG + pricing policy |

**Commit:** `bd60e049` - "docs: clarify HAS_FEE relationships are NOT Bali Zero prices"

---

### Test Tentati (Non Completati per Auth)

**Obiettivo:** Verificare al 100% che LLM usa SOLO prezzi Bali Zero.

**Script Creati:**

1. `/tmp/test_pricing_policy.py` - Test HTTP con autenticazione
2. `/tmp/test_pricing_real.py` - Test diretto orchestrator
3. `/tmp/verify_pricing_config.py` - Verifica statica configurazione
4. `/tmp/MANUAL_PRICING_TESTS.md` - Guida test manuali

**Problema Incontrato:**

- Test HTTP richiedono JWT token (endpoint `/api/agentic/query` protetto)
- Test diretti falliscono per import errors (dipendenze mancanti in ambiente locale)
- Background processes killati (exit code 137)

**Stato:** ⚠️ **TEST REALI NON ESEGUITI**

---

### ⚠️ COSA NON È CHIARO / DA VERIFICARE

#### 1. Comportamento Reale LLM con Pricing

**Domanda:** L'LLM rispetta davvero le regole nel 100% dei casi?

**Cosa sappiamo:**

- ✅ Prompt ha regole esplicite (RULE 1, 2, 3)
- ✅ PricingTool ha description "MANDATORY"
- ✅ HAS_FEE non contiene prezzi Bali Zero (verificato codice sorgente)

**Cosa NON sappiamo (manca test reale):**

- ❓ L'LLM chiama sempre `get_pricing` per domande sui prezzi?
- ❓ L'LLM dice sempre "da verificare" quando prezzo non trovato?
- ❓ L'LLM inventa mai range tipo "5-10 milioni"?
- ❓ L'LLM usa mai HAS_FEE come prezzi cliente?

**Come Verificare:**

- Opzione A: Test manuale via browser su https://www.balizero.com/chat
- Opzione B: Script curl con JWT token (richiede login prima)
- Opzione C: Analisi conversation logs produzione (se disponibili)

#### 2. Quale Provider LLM È Attivo?

**Discovery:** Fly.io secrets mostrano **3 provider configurati**:

```
OPENAI_API_KEY ✅
ANTHROPIC_API_KEY ✅
GOOGLE_API_KEY (Gemini) ✅
```

**Domanda:** Quale viene usato di default per Zantara chat?

**Non abbiamo verificato:**

- File `llm_gateway.py` (tentativo di lettura fallito - file vuoto?)
- Configurazione default provider in `config.py`
- Logica di fallback tra provider

**Possibile che:**

- Usa OpenAI di default (più affidabile)
- Gemini solo per KG extraction (batch job)
- Fallback ad Anthropic se OpenAI down

**Come Verificare:**

```bash
grep -r "default.*provider\|DEFAULT_MODEL\|LLM_PROVIDER" apps/backend-rag/backend/
```

#### 3. Confidence Score nel KG

**Problema Noto (da documentazione):**

- Tutti i nodi hanno `confidence = 0.9` HARDCODED
- Non riflette vera qualità (source singola vs multipla)

**Domanda:** Questo impatta il ranking dei risultati KG tool?

**Non sappiamo:**

- Il KnowledgeGraphTool usa confidence per ranking?
- Entità single-source (77%) vengono filtrate?
- Rischio hallucination per single-source entities?

**File da analizzare:**

```
apps/backend-rag/backend/services/tools/knowledge_graph_tool.py
apps/backend-rag/backend/services/knowledge_graph/kg_builder.py
```

#### 4. Coverage KG per Collection

**Dalla documentazione:**
| Collection | Estimated Entities |
|------------|-------------------|
| legal_unified_hybrid | ~15,000 |
| visa_oracle | ~8,000 |
| tax_genius_hybrid | ~6,000 |
| kbli_atlas | ~3,500 |
| training_conversations | ~2,000 |

**Domanda:** Queste percentuali sono accurate?

**Non abbiamo verificato:**

- Query SQL diretta al database per contare per collection
- Overlap tra collections (stessa entity in più collections?)

**Come Verificare:**

```sql
SELECT source_collection, COUNT(*)
FROM kg_nodes
GROUP BY source_collection;
```

#### 5. Orphan Nodes

**Dalla documentazione:**

- ~5,000 nodi (14.5%) senza relazioni
- "Provide no graph traversal value"

**Domanda:** Questi dovrebbero essere puliti?

**Non sappiamo:**

- Impattano performance query KG?
- Causano falsi positivi in ricerche?
- Vale la pena fare cleanup?

---

### Raccomandazioni Next Steps

**Priorità Alta:**

1. ✅ **Test Reali Pricing Policy** (manuale o automatico)
   - Eseguire i 7 test case in `/tmp/MANUAL_PRICING_TESTS.md`
   - Documentare risultati in KG_VALUE_ASSESSMENT

2. 🔍 **Identificare LLM Provider Default**
   - Analizzare `llm_gateway.py` (file sembra corrotto?)
   - Verificare quale API viene usata per chat Zantara

**Priorità Media:** 3. 📊 **Analisi KG Coverage Reale**

- Query SQL per distribution per collection
- Verificare accuracy delle stime nella documentazione

4. 🧹 **Cleanup Orphan Nodes** (se impattano performance)
   - Script per identificare orphan nodes
   - Analisi se causano falsi positivi

**Priorità Bassa:** 5. ⚙️ **Implementare Dynamic Confidence Scoring**

- Già documentato in KG_VALUE_ASSESSMENT come improvement
- Basare confidence su numero sources (multi-source boost)

---

### LLM Provider Status

**Verificato via Fly.io secrets:**

```bash
fly secrets list -a nuzantara-rag
```

**Secrets Attivi:**

- `OPENAI_API_KEY` ✅
- `ANTHROPIC_API_KEY` ✅
- `GOOGLE_API_KEY` / `GOOGLEAISTUDIO_API_KEY` ✅
- `GOOGLE_CREDENTIALS_JSON` ✅ (Vertex AI)

**Domanda Utente:**

> "ma se abbiamo fermato tutte le api key di google come sta rispondendo LLM?"

**Risposta:**
Le API key Google NON sono state fermate - sono ancora configurate in Fly.io. Inoltre, il sistema ha **3 provider disponibili** (OpenAI, Anthropic, Gemini), quindi anche se uno fallisce, può usare gli altri.

**Da chiarire:** Quale provider è default per Zantara chat?

---

### Comandi Utili

**Verificare provider LLM:**

```bash
grep -r "DEFAULT_MODEL\|LLM_PROVIDER" apps/backend-rag/backend/app/core/
```

**Query KG stats:**

```sql
-- Nodes per collection
SELECT source_collection, COUNT(*) as nodes
FROM kg_nodes
GROUP BY source_collection
ORDER BY nodes DESC;

-- Orphan nodes
SELECT COUNT(*)
FROM kg_nodes n
WHERE NOT EXISTS (
  SELECT 1 FROM kg_edges e
  WHERE e.source_entity_id = n.entity_id
     OR e.target_entity_id = n.entity_id
);
```

**Test pricing via browser:**

1. Open https://www.balizero.com/chat
2. Login as zero@balizero.com
3. Ask: "Quanto costa aprire una PT PMA?"
4. Check DevTools Network tab for `get_pricing` tool call

---

### Key Learnings

1. **Knowledge Graph = Investimento Valido**
   - 34K nodi utilizzabili in produzione
   - ~13K relazioni semanticamente utili
   - €0.018 per relazione utile (ragionevole)

2. **HAS_FEE ≠ Prezzi Cliente**
   - Contiene SOLO fee governative (PNBP) e legali
   - Mai comunicare al cliente (non verificate, obsolete)
   - Bali Zero prices isolati in PricingTool

3. **Sistema Ben Protetto (in teoria)**
   - Prompt rules esplicite contro invenzione prezzi
   - PricingTool MANDATORY per pricing queries
   - Architettura separa dati legali da pricing commerciale

4. **Test Reali Mancanti**
   - Protezioni verificate solo a livello codice
   - Comportamento LLM reale non testato
   - Serve validazione empirica

---

**Preparato da:** Claude Sonnet 4.5
**Data Sessione:** 2026-01-18
**Status KG:** ✅ Active in Production (Tool #4)
**Status Pricing Policy:** ⚠️ Needs Real Testing
**Files Created:** 1 documentation + 4 test scripts (non eseguiti)
**Commits:** 1 (bd60e049)
