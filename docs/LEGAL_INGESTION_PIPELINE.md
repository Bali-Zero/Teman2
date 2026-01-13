# Legal Document Ingestion Pipeline

**Ultimo aggiornamento:** 2026-01-13

## Panoramica

La pipeline di ingestione legale è un sistema completo per processare documenti legali indonesiani (Peraturan Pemerintah, Undang-Undang, Instruksi Gubernur, ecc.) e integrarli nel sistema RAG di Nuzantara.

## Architettura della Pipeline

La pipeline è implementata in `LegalIngestionService` e processa i documenti attraverso 7 stadi sequenziali:

### STAGE 1: Parsing del Documento

**Obiettivo:** Estrarre testo grezzo dal PDF

**Implementazione:**
- Usa `auto_detect_and_parse()` per estrarre testo da PDF standard
- **OCR Avanzato:** Se nessun testo viene trovato (PDF scannerizzato), attiva automaticamente OCR con Google Gemini Vision
- Processa ogni pagina individualmente per massima qualità OCR
- Preserva formattazione, linee, paragrafi e struttura

**File:** `backend/core/parsers.py`
- `extract_text_from_pdf()` - Estrazione standard
- `extract_text_from_pdf_async()` - Versione async per contesti async
- `extract_text_from_pdf_ocr_async()` - OCR avanzato con Gemini Vision

**Gestione Errori:**
- Non-blocking: se OCR fallisce, l'ingestione continua con testo vuoto (logga warning)
- Fallback automatico da sync a async OCR quando necessario

### STAGE 1.5: Upload Google Drive (Permanente)

**Obiettivo:** Archiviare permanentemente il PDF su Google Drive

**Implementazione:**
- Upload automatico dopo parsing del PDF
- Crea ricorsivamente cartelle se non esistono (`BALI ZERO/PERATURAN`)
- Usa Domain-Wide Delegation con `zero@balizero.com`
- Salva `drive_file_id` e `drive_web_link` nei metadata

**File:** `backend/services/ingestion/legal_ingestion_service.py`
- `_ensure_drive_folder_exists()` - Trova/crea cartelle Drive
- Integrato dopo parsing, prima della pulizia

**Gestione Errori:**
- Non-blocking: se upload fallisce, l'ingestione continua (logga warning)
- Non blocca il resto della pipeline

### STAGE 2: Pulizia del Testo

**Obiettivo:** Rimuovere headers, footers, noise

**Implementazione:**
- Rimozione pattern comuni (numeri pagina, headers ripetuti)
- Normalizzazione spazi e caratteri speciali
- Preserva struttura legale (BAB, Pasal, Ayat)

**File:** `backend/core/legal/text_cleaner.py`

### STAGE 3: Estrazione Metadata

**Obiettivo:** Estrarre metadata strutturati dal documento

**Campi Estratti:**
- `type`: Tipo documento (PERATURAN PEMERINTAH, UNDANG-UNDANG, ecc.)
- `type_abbrev`: Abbreviazione (PP, UU, INGUB, ecc.)
- `number`: Numero del documento
- `year`: Anno
- `topic`: Argomento principale
- `status`: Stato (dicabut, berlaku, ecc.)
- `full_title`: Titolo completo

**File:** `backend/core/legal/metadata_extractor.py`

### STAGE 4: Parsing Struttura Gerarchica

**Obiettivo:** Identificare e strutturare BAB, Pasal, Ayat

**Implementazione:**
- Usa regex pattern per identificare sezioni gerarchiche
- Crea struttura ad albero (BAB → Pasal → Ayat)
- Mantiene riferimenti incrociati

**File:** `backend/core/legal/structure_parser.py`

### STAGE 5: Chunking Gerarchico

**Obiettivo:** Creare chunks semantici preservando contesto gerarchico

**Implementazione:**
- Chunking basato su Pasal con contesto BAB
- Iniezione di metadata gerarchici in ogni chunk
- Chunks ottimizzati per RAG (150-1500 caratteri)

**File:** `backend/core/legal/hierarchical_indexer.py`
- `index_legal_document()` - Chunking principale
- `_create_hierarchical_chunks()` - Creazione chunks con contesto

**Output:**
- Chunks semantici per Qdrant (ricerca vettoriale)
- Parent documents (BAB completi) per PostgreSQL (ricerca full-text)

### STAGE 6: Embedding e Storage

**Obiettivo:** Generare embeddings e salvare in Qdrant

**Implementazione:**
- Genera embeddings usando OpenAI `text-embedding-3-small` (1536 dims)
- Upsert in Qdrant collection `legal_unified` con named vectors (`dense`)
- Metadata completi per ogni chunk (document_id, bab, pasal, tier, ecc.)

**File:** `backend/core/legal/hierarchical_indexer.py`
- `_upsert_hierarchical_chunks()` - Upsert in Qdrant

**Gestione Errori:**
- Retry automatico con named vectors fallback
- Non-blocking per parent documents (se DB non disponibile)

### STAGE 7: Knowledge Graph Extraction (Permanente)

**Obiettivo:** Estrarre entità e relazioni per Knowledge Graph

**Implementazione:**
- Usa `KGIncrementalExtractor` con Gemini per estrazione avanzata
- Estrae entità (organizzazioni, leggi, concetti legali, ecc.)
- Estrae relazioni (richiede, modifica, implementa, ecc.)
- Salva in PostgreSQL (`kg_nodes`, `kg_edges`)

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`
- `extract_from_collection()` - Estrazione da collection Qdrant
- `_fetch_chunks_from_collection()` - Fetch chunks filtrati per document_id

**Gestione Errori:**
- Completamente non-blocking
- Se DB pool non disponibile, salta KG extraction (logga warning)
- Non blocca mai l'ingestione principale

## Flusso Completo

```
PDF File
  ↓
[STAGE 1] Parse (con OCR fallback se scannerizzato)
  ↓
[STAGE 1.5] Upload Google Drive (non-blocking)
  ↓
[STAGE 2] Clean Text
  ↓
[STAGE 3] Extract Metadata
  ↓
[STAGE 4] Parse Structure (BAB/Pasal/Ayat)
  ↓
[STAGE 5] Hierarchical Chunking
  ↓
[STAGE 6] Generate Embeddings & Store in Qdrant
  ↓
[STAGE 7] KG Extraction (non-blocking)
  ↓
Complete ✅
```

## Configurazione

### Variabili d'Ambiente Richieste

```bash
# Google Drive (per upload permanente)
GOOGLE_DRIVE_ROOT_FOLDER_ID=...
GOOGLE_CREDENTIALS_JSON=...

# Google AI Studio (per OCR avanzato)
GOOGLE_API_KEY=...

# Qdrant
QDRANT_URL=https://nuzantara-qdrant.fly.dev
QDRANT_API_KEY=...

# OpenAI (per embeddings)
OPENAI_API_KEY=...

# PostgreSQL (opzionale, per KG e parent documents)
DATABASE_URL=postgresql://...
```

### Configurazione Opzionale

```python
# In settings.py
kg_extraction_enabled: bool = True  # Abilita KG extraction
google_drive_upload_enabled: bool = True  # Abilita upload Drive
google_drive_legal_folder: str = "BALI ZERO/PERATURAN"  # Cartella Drive
```

## Gestione Errori e Robustezza

### Principi di Design

1. **Non-Blocking Operations:**
   - Google Drive upload: se fallisce, continua ingestione
   - KG extraction: se fallisce, continua ingestione
   - Parent documents save: se DB non disponibile, continua ingestione

2. **Graceful Degradation:**
   - OCR fallback automatico per PDF scannerizzati
   - Named vectors fallback per Qdrant compatibility
   - Quality columns fallback per PostgreSQL migrations

3. **Error Logging:**
   - Tutti gli errori sono loggati con contesto completo
   - Structured logging per monitoring
   - Warning invece di errori per operazioni non-blocking

## Costi OCR: Confronto Servizi

### Google Gemini Vision (Attuale Implementazione)

**Pricing (2025):**
- **Input Images:** $0.005 per immagine
- **Input Tokens:** $1.25 per milione di token
- **Output Tokens:** $5.00 per milione di token (fino a 128K tokens)
- **Output Tokens (128K+):** $10.00 per milione di token

**Esempio Costo per PDF Scannerizzato:**
- PDF con 10 pagine = 10 immagini
- Costo immagini: 10 × $0.005 = **$0.05**
- Costo tokens (stimato ~1000 tokens/pagina input, ~2000 tokens/pagina output):
  - Input: 10K tokens × $1.25/1M = **$0.0125**
  - Output: 20K tokens × $5/1M = **$0.10**
- **Totale per PDF: ~$0.16**

**Vantaggi:**
- ✅ Alta qualità OCR (preserva formattazione)
- ✅ Supporto multilingua (Indonesiano incluso)
- ✅ Integrazione nativa con Google AI Studio
- ✅ Gestione automatica di tabelle e strutture complesse

**Svantaggi:**
- ❌ Costo per documento scannerizzato
- ❌ Dipendenza da API esterna

### Tesseract OCR (Open Source)

**Pricing:**
- **Costo Software:** Gratuito (open source)
- **Costo Hosting:** $0 (può girare on-premise)

**Costi Indiretti:**
- Setup e configurazione: ~2-4 ore sviluppo
- Manutenzione: ~1-2 ore/mese
- Infrastruttura: CPU/GPU per processing (se on-premise)
- Integrazione: ~4-8 ore sviluppo

**Esempio Costo per PDF Scannerizzato:**
- Costo diretto: **$0**
- Costo setup iniziale: ~$200-400 (tempo sviluppo)
- Costo manutenzione: ~$50-100/mese

**Vantaggi:**
- ✅ Gratuito (no costi operativi)
- ✅ Controllo completo
- ✅ Privacy (dati non escono dal sistema)
- ✅ Nessun limite di rate

**Svantaggi:**
- ❌ Qualità inferiore a Gemini Vision
- ❌ Setup complesso
- ❌ Manutenzione richiesta
- ❌ Supporto limitato per lingue non-Latino
- ❌ Gestione tabelle complessa

### Altri Servizi OCR Commerciali

#### AWS Textract
- **Pricing:** $1.50 per 1000 pagine (primi 1M pagine/mese)
- **Costo per PDF 10 pagine:** ~$0.015
- **Vantaggi:** Alta qualità, integrazione AWS
- **Svantaggi:** Costo, vendor lock-in AWS

#### Azure Form Recognizer
- **Pricing:** $1.50 per 1000 pagine
- **Costo per PDF 10 pagine:** ~$0.015
- **Vantaggi:** Alta qualità, integrazione Azure
- **Svantaggi:** Costo, vendor lock-in Azure

#### OCR.space API
- **Pricing:** Gratuito (25K requests/mese) o $4.99/mese (100K requests)
- **Costo per PDF:** Gratuito (con limiti) o ~$0.00005
- **Vantaggi:** Molto economico, API semplice
- **Svantaggi:** Qualità variabile, rate limits

## Raccomandazione Costi

### Per Volume Basso (<100 PDF/mese)
**Raccomandazione: Google Gemini Vision**
- Costo totale: ~$16/mese
- Setup minimo, qualità alta
- Giustificato per volume basso

### Per Volume Medio (100-1000 PDF/mese)
**Raccomandazione: Google Gemini Vision**
- Costo totale: ~$160/mese
- Ancora conveniente rispetto a setup Tesseract
- Qualità superiore giustifica costo

### Per Volume Alto (>1000 PDF/mese)
**Raccomandazione: Tesseract Self-Hosted**
- Costo setup: ~$400 una tantum
- Costo operativo: ~$50-100/mese (manutenzione)
- ROI positivo dopo ~3-4 mesi
- Privacy e controllo completi

### Per Volume Critico (>10K PDF/mese)
**Raccomandazione: Hybrid Approach**
- Tesseract per batch processing (costo basso)
- Gemini Vision per documenti critici (qualità alta)
- Fallback automatico se Tesseract fallisce

## Metriche e Monitoring

### Metriche Chiave

1. **Ingestion Success Rate:**
   - Target: >95%
   - Monitora fallimenti per tipo (parsing, OCR, storage)

2. **OCR Usage:**
   - % documenti che richiedono OCR
   - Costo medio per documento OCR
   - Qualità OCR (caratteri estratti vs. attesi)

3. **Pipeline Duration:**
   - Tempo medio per documento
   - Breakdown per stage
   - Bottleneck identification

4. **Storage Metrics:**
   - Chunks creati per documento
   - Parent documents salvati
   - KG entities/relationships estratti

### Logging Strutturato

Tutti gli eventi sono loggati con:
- `document_id`: ID univoco documento
- `stage`: Stage corrente della pipeline
- `duration_ms`: Durata operazione
- `success`: Successo/fallimento
- `error`: Dettagli errore (se presente)

## Esempi d'Uso

### Ingestione Singolo Documento

```python
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

service = LegalIngestionService()
result = await service.ingest_legal_document(
    file_path="/path/to/document.pdf",
    category="immigrazione"
)

print(f"Success: {result['success']}")
print(f"Chunks: {result['chunks_created']}")
print(f"KG Entities: {result.get('kg_extraction', {}).get('entities', 0)}")
```

### Ingestione Batch

```python
import asyncio
from pathlib import Path

async def ingest_batch(pdf_dir: Path):
    service = LegalIngestionService()
    results = []
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        result = await service.ingest_legal_document(str(pdf_file))
        results.append(result)
    
    return results

# Usage
results = asyncio.run(ingest_batch(Path("/path/to/pdfs")))
```

## Troubleshooting

### Problema: OCR non funziona
**Soluzione:**
1. Verifica `GOOGLE_API_KEY` è configurato
2. Controlla logs per errori API
3. Verifica quota Google AI Studio

### Problema: Upload Drive fallisce
**Soluzione:**
1. Verifica `GOOGLE_DRIVE_ROOT_FOLDER_ID`
2. Controlla `GOOGLE_CREDENTIALS_JSON`
3. Verifica permessi Domain-Wide Delegation

### Problema: KG extraction non funziona
**Soluzione:**
1. Verifica `DATABASE_URL` è configurato
2. Controlla connessione PostgreSQL
3. Verifica tabelle `kg_nodes` e `kg_edges` esistono

### Problema: Named vectors error in Qdrant
**Soluzione:**
- Il sistema ha già fallback automatico
- Verifica collection `legal_unified` usa named vectors
- Controlla logs per dettagli retry

## Riferimenti

- **Codice Principale:** `apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py`
- **Parsers:** `apps/backend-rag/backend/core/parsers.py`
- **Hierarchical Indexer:** `apps/backend-rag/backend/core/legal/hierarchical_indexer.py`
- **KG Extraction:** `apps/backend-rag/scripts/kg_incremental_extraction.py`
- **Google Drive:** `apps/backend-rag/backend/services/integrations/team_drive_service.py`

## Changelog

### 2026-01-13
- ✅ Aggiunto OCR avanzato con Google Gemini Vision
- ✅ Aggiunto upload permanente Google Drive
- ✅ Aggiunta KG extraction permanente nella pipeline
- ✅ Migliorata robustezza (tutto non-blocking)
- ✅ Fix named vectors support in Qdrant
- ✅ Documentazione costi OCR completa

### 2025-12-XX
- Implementazione iniziale pipeline legale
- Supporto parsing gerarchico BAB/Pasal/Ayat
- Integrazione Qdrant e PostgreSQL
