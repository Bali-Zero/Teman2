# MODUS OPERANDI SUPREMO - Ingestione Knowledge Base Nuzantara

> Documento definitivo per l'ingestione di documenti legali nella Knowledge Base.
> Ultimo aggiornamento: 11 Dicembre 2025

---

## 1. ARCHITETTURA STORAGE

### 1.1 Dual-Storage System

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCUMENTO SORGENTE                        │
│              (PDF/TXT da imigrasi.go.id, etc.)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────────┐                   ┌───────────────────┐
│    POSTGRESQL     │                   │      QDRANT       │
│   (Full Text)     │                   │ (Vector Chunks)   │
├───────────────────┤                   ├───────────────────┤
│ parent_documents  │                   │ visa_oracle       │
│ - id              │                   │ - id (uuid)       │
│ - document_id     │                   │ - vector [1536]   │
│ - full_text       │                   │ - payload:        │
│ - metadata JSONB  │                   │   - text          │
│                   │                   │   - metadata      │
│ (Contesto BAB)    │                   │   - chunk_index   │
└───────────────────┘                   └───────────────────┘
        │                                           │
        └─────────────────────┬─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   RAG QUERY     │
                    │ Vector Search + │
                    │ Context Expand  │
                    └─────────────────┘
```

### 1.2 Collections Qdrant

| Collection | Uso | Esempi |
|------------|-----|--------|
| `visa_oracle` | Visa, KITAS, KITAP, Surat Edaran Imigrasi | IMI-417, IMI-941, E33G, E31A |
| `tax_genius` | Tasse, PPh, PPN, KUP | PMK, PP pajak |
| `legal_unified` | Leggi generali indonesiane | UU, PP generici |
| `kbli_unified` | Codici attività business | KBLI 2020 |
| `property_unified` | Immobiliare, agraria | Hak Pakai, HGB |
| `litigation_oracle` | Sentenze tribunali | Putusan MA, PN |
| `training_conversations` | Conversazioni Q&A training | NotebookLM output |

---

## 2. FLUSSO INGESTIONE STANDARD

### 2.1 Fase 0: Acquisizione Documento

```bash
# Directory sorgente
/Users/antonellosiano/Desktop/nuzantara/apps/kb/data/
├── immigration/     # ← PDF/TXT specifici visa/tax (PREFERITO)
├── raw_laws/              # ← PDF legali generici
├── raw_laws_local/        # ← Leggi locali (Bali, Jakarta)
└── court-decisions/           # ← Sentenze tribunali
```

**Naming Convention:**
```
SE_IMI-417_GR_01_01_2025_penyesuaian_pelayanan.txt
│  │       │        │     └── Argomento principale
│  │       │        └── Anno
│  │       └── Classificazione (GR.01.01)
│  └── Numero documento
└── Tipo (SE=Surat Edaran, UU=Undang-Undang, PP=Peraturan Pemerintah)
```

### 2.2 Fase 1: Preparazione Testo

**Per PDF:** Estrarre testo con struttura preservata
```python
# Se PDF già estratto da Claude (Read tool), copiare il testo
# Altrimenti usare PyMuPDF/PyPDF2
```

**Per TXT:** Creare file con header standard:
```
TITLE: [Titolo completo del documento]
SOURCE: [URL o fonte ufficiale]
DATE: [Data emanazione]
EFFECTIVE: [Data efficacia, se diversa]
TYPE: [Surat Edaran / Peraturan / UU / PP]
CATEGORY: [visa_procedure / tax / business / property]
==================================================

[CONTENUTO DEL DOCUMENTO]
```

### 2.3 Fase 2: Chunking

**Per documenti legali (Pasal-aware):**
- Chunk per sezione (## headers)
- Preservare contesto BAB/Pasal
- Overlap: 200 caratteri

**Configurazione ottimale:**
```python
chunk_size = 1500      # caratteri
overlap = 200          # caratteri
max_chunks = 500       # per documento
```

### 2.4 Fase 3: Metadata Extraction

**Metadata obbligatori:**
```python
{
    "source": "surat_edaran",           # Tipo fonte
    "file_name": "...",                 # Nome file
    "category": "visa_procedure",       # Categoria
    "document_type": "circular_letter", # Tipo documento
    "regulation_number": "IMI-417.GR.01.01",
    "regulation_year": "2025",
    "topic": "...",                      # Argomento principale
    "effective_date": "2025-05-29",     # Data efficacia
    "issuing_authority": "...",         # Autorità emittente
    "keywords": ["...", "..."],         # Parole chiave ricerca
}
```

### 2.5 Fase 4: Embedding Generation

**Provider:** OpenAI `text-embedding-3-small`
**Dimensioni:** 1536
**Batch size:** Fino a 2048 testi per chiamata API

```python
from core.embeddings import EmbeddingsGenerator

embedder = EmbeddingsGenerator(
    api_key=os.getenv("OPENAI_API_KEY"),
    provider="openai"
)
vector = embedder.generate_single_embedding(chunk_text[:8000])
```

### 2.6 Fase 5: Upsert to Qdrant

```python
point = {
    "id": str(uuid.uuid4()),
    "vector": vector,           # [1536 floats]
    "payload": {
        "text": chunk_text,
        "chunk_index": i,
        "total_chunks": len(chunks),
        **metadata
    }
}
```

**Via REST API (bypass SSL issues):**
```python
import requests

url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points"
headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
resp = requests.put(url, headers=headers, json={"points": points})
```

---

## 3. SCRIPT DI INGESTIONE

### 3.1 Script Disponibili

| Script | Uso | Collection Target |
|--------|-----|-------------------|
| `ingest_surat_edaran.py` | Surat Edaran Imigrasi | visa_oracle |
| `ingest_training_conversations_rest.py` | Q&A training | training_conversations |
| `ingest_laws.py` | Leggi generiche | legal_unified |
| `ingest_golden_data.py` | Dati golden visa | visa_oracle |
| `ingest_intelligent.py` | Auto-routing con Gemini | Multipli |

### 3.2 Esecuzione

```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/backend-rag

# Con variabili d'ambiente
PYTHONPATH=./backend python3 backend/scripts/ingest_surat_edaran.py

# Oppure con dotenv caricato automaticamente
python3 backend/scripts/ingest_surat_edaran.py
```

### 3.3 Verifica Post-Ingestione

```bash
# Conta punti totali
curl -s "https://nuzantara-qdrant.fly.dev/collections/visa_oracle" \
  -H "api-key: $QDRANT_API_KEY" | jq '.result.points_count'

# Cerca per metadata
curl -s -X POST "https://nuzantara-qdrant.fly.dev/collections/visa_oracle/points/scroll" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "filter": {"must": [{"key": "source", "match": {"value": "surat_edaran"}}]}}' \
  | jq '.result.points[].payload.regulation_number'
```

---

## 4. CHECKLIST INGESTIONE

### Pre-Ingestione
- [ ] PDF originale salvato in `immigration/`
- [ ] File .txt con header standard creato
- [ ] Metadata estratti correttamente
- [ ] Collection target identificata

### Durante Ingestione
- [ ] Script eseguito senza errori
- [ ] Embeddings generati (1536 dims)
- [ ] Punti upsertati in Qdrant

### Post-Ingestione
- [ ] Conteggio punti aumentato
- [ ] Ricerca per metadata funziona
- [ ] Query semantica trova il documento

---

## 5. TROUBLESHOOTING

### SSL Certificate Issues
```python
# Usare REST API diretto invece di qdrant-client
import requests
# invece di
# from qdrant_client import QdrantClient
```

### Embedding Dimension Mismatch
```
Errore: "Vector dimension mismatch"
Soluzione: Verificare che collection usi 1536 dims (OpenAI)
           Non mischiare embeddings di provider diversi
```

### Collection Not Found
```bash
# Creare collection se non esiste
curl -X PUT "https://nuzantara-qdrant.fly.dev/collections/NEW_COLLECTION" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

---

## 6. GERARCHIA NORMATIVA INDONESIA (Riferimento)

```
┌─────────────────────────────────────────────────┐
│              UUD 1945 (Costituzione)            │
├─────────────────────────────────────────────────┤
│         TAP MPR (Decreti Assemblea)             │
├─────────────────────────────────────────────────┤
│            UU (Undang-Undang / Leggi)           │  ← UU 6/2011 Keimigrasian
├─────────────────────────────────────────────────┤
│         PERPU (Regolamenti Urgenti)             │
├─────────────────────────────────────────────────┤
│          PP (Peraturan Pemerintah)              │  ← PP 31/2013, PP 40/2023
├─────────────────────────────────────────────────┤
│        PERPRES (Peraturan Presiden)             │  ← Perpres 95/2024
├─────────────────────────────────────────────────┤
│     PERMEN / PERMENKUMHAM (Peraturan Menteri)   │  ← Permenkumham 22/2023
├─────────────────────────────────────────────────┤
│         KEPMEN (Keputusan Menteri)              │
├─────────────────────────────────────────────────┤
│       SE (Surat Edaran / Circolari)             │  ← IMI-417/2025, IMI-941/2024
├─────────────────────────────────────────────────┤
│      Instruksi / Nota Dinas / SOP               │
└─────────────────────────────────────────────────┘
```

**Nota:** Le Surat Edaran sono circolari operative che spiegano COME applicare le leggi superiori. Possono cambiare frequentemente senza modificare la legge di base.

---

## 7. ESEMPIO COMPLETO: Ingestione Nuova Surat Edaran

### Step 1: Ottenere il PDF
```bash
# Scaricare da hukumonline.com, paralegal.id, o imigrasi.go.id
# Salvare in Desktop per facilità
```

### Step 2: Leggere con Claude
```
# Usare Read tool su PDF
Read /Users/antonellosiano/Desktop/NUOVO_DOCUMENTO.pdf
```

### Step 3: Copiare PDF in immigration
```bash
cp /Users/antonellosiano/Desktop/NUOVO_DOCUMENTO.pdf \
   /Users/antonellosiano/Desktop/nuzantara/apps/kb/data/immigration/
```

### Step 4: Creare file .txt con header
```bash
# Creare file con Write tool, includendo:
# - Header standard (TITLE, SOURCE, DATE, etc.)
# - Testo completo estratto dal PDF
# - Tabelle riepilogative alla fine
```

### Step 5: Aggiornare script ingestione
```python
# In ingest_surat_edaran.py, aggiungere:
SURAT_EDARAN_FILES = [
    # ...existing files...
    Path(".../SE_NUOVO_DOCUMENTO.txt"),
]
```

### Step 6: Eseguire ingestione
```bash
PYTHONPATH=./backend python3 backend/scripts/ingest_surat_edaran.py
```

### Step 7: Verificare
```bash
curl -s -X POST ".../points/scroll" -d '{"filter": {"key": "regulation_number", "match": {"value": "NUOVO"}}}'
```

---

## 8. MANUTENZIONE

### Aggiornamento Documenti Esistenti
Se un documento viene aggiornato (nuova versione Surat Edaran):
1. Eliminare vecchi punti per quel `regulation_number`
2. Re-ingestionare con nuova versione
3. Aggiornare `effective_date` nel metadata

### Backup
```bash
# Esportare collection
curl -X POST "https://nuzantara-qdrant.fly.dev/collections/visa_oracle/points/scroll" \
  -H "api-key: $QDRANT_API_KEY" \
  -d '{"limit": 10000, "with_payload": true, "with_vector": true}' \
  > backup_visa_oracle_$(date +%Y%m%d).json
```

### Pulizia Duplicati
```python
# Cercare per regulation_number e rimuovere vecchie versioni
# prima di re-ingestionare
```

---

**Fine Modus Operandi**

*Questo documento va aggiornato quando cambiano procedure, script, o strutture dati.*
