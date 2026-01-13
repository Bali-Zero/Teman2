# Legal Ingestion Service - Testing & Coverage

**Ultimo aggiornamento:** 2026-01-13

## Panoramica Testing

Il file `test_legal_ingestion_service_coverage.py` fornisce test completi per la pipeline di ingestione legale con target di coverage >95%.

## Struttura Test

### Test Coverage Checklist

#### ✅ Inizializzazione
- Service initialization con collection name
- Verifica componenti inizializzati correttamente

#### ✅ STAGE 1: Parsing
- Parsing successo (PDF standard)
- Parsing fallimento (no text)
- OCR fallback per PDF scannerizzati
- OCR fallback failure

#### ✅ STAGE 1.5: Google Drive Upload
- Upload successo
- Upload fallimento non-blocking
- Creazione cartelle Drive

#### ✅ STAGE 2-5: Processing Pipeline
- Full pipeline success
- Metadata extraction failure
- Tier classification
- Tier override

#### ✅ STAGE 7: Knowledge Graph Extraction
- KG extraction successo
- KG extraction fallimento non-blocking
- KG extraction skipped (DB non disponibile)

#### ✅ Edge Cases
- File vuoto
- File inesistente
- Skip pricing flag
- Collection name override
- Trace ID e User ID propagation

#### ✅ Error Handling
- Cleaner error
- Indexer error
- General exception handling

#### ✅ Logging
- Structured logging verification

## Esecuzione Test

### Eseguire tutti i test
```bash
cd apps/backend-rag
pytest tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py -v
```

### Eseguire con coverage
```bash
pytest tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py \
  --cov=backend.services.ingestion.legal_ingestion_service \
  --cov-report=html \
  --cov-report=term-missing
```

### Eseguire test specifici
```bash
# Solo test parsing
pytest tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py::test_parsing_success -v

# Solo test OCR
pytest tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py -k "ocr" -v

# Solo test Drive
pytest tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py -k "drive" -v
```

## Mock e Fixtures

### Fixtures Principali

- `mock_settings`: Mock delle configurazioni
- `sample_pdf_path`: PDF di test standard
- `scanned_pdf_path`: PDF scannerizzato per test OCR
- `mock_legal_components`: Mock di tutti i componenti legali
- `mock_qdrant_client`: Mock Qdrant client
- `mock_embeddings`: Mock embeddings generator
- `mock_hierarchical_indexer`: Mock hierarchical indexer
- `mock_kg_extractor`: Mock KG extractor
- `mock_drive_service`: Mock Google Drive service

## Logging Razionale

### Structured Logging Implementation

Il logging è stato migliorato con structured logging razionale:

#### Formato Log

Ogni log entry include:
- `[STAGE X]` prefix per identificare lo stage
- `document_id`: ID univoco documento
- `stage`: Stage corrente (`parsing`, `cleaning`, `metadata_extraction`, `kg_extraction`, ecc.)
- `duration_seconds`: Durata operazione
- `success`: Successo/fallimento (quando applicabile)
- `error`: Dettagli errore (se presente)
- `error_type`: Tipo errore (se presente)

#### Esempi Log

```python
# Parsing con OCR
logger.info(
    "[STAGE 1] Parsing completed: 541 chars in 4.53s",
    extra={
        "document_id": "legal_123",
        "stage": "parsing",
        "duration_seconds": 4.53,
        "text_length": 541,
        "ocr_used": True,
    }
)

# Drive upload successo
logger.info(
    "[STAGE 1.5] Uploaded to Drive: file_id_123",
    extra={
        "document_id": "legal_123",
        "stage": "drive_upload",
        "drive_file_id": "file_id_123",
        "drive_web_link": "https://drive.google.com/...",
        "success": True,
    }
)

# KG extraction fallimento non-blocking
logger.warning(
    "[STAGE 7] KG extraction failed (non-blocking): Database error",
    extra={
        "document_id": "legal_123",
        "stage": "kg_extraction",
        "error": "Database error",
        "error_type": "DatabaseError",
        "non_blocking": True,
    }
)
```

### Vantaggi Structured Logging

1. **Ricercabilità**: Facile filtrare per `document_id`, `stage`, `error_type`
2. **Monitoring**: Metriche automatiche da log strutturati
3. **Debugging**: Contesto completo per ogni operazione
4. **Analytics**: Analisi performance per stage
5. **Alerting**: Alert automatici su errori critici

## Metriche Coverage

### Target Coverage

- **Overall**: >95%
- **Critical Paths**: 100%
- **Error Handling**: >90%
- **Edge Cases**: >85%

### Coverage Report

Dopo esecuzione test con coverage:

```bash
# Genera report HTML
pytest --cov=backend.services.ingestion.legal_ingestion_service \
  --cov-report=html

# Apri report
open htmlcov/index.html
```

## Best Practices

### Scrittura Test

1. **Isolamento**: Ogni test è indipendente
2. **Mocking**: Mock tutte le dipendenze esterne
3. **Assertions**: Verifica comportamento, non implementazione
4. **Edge Cases**: Testa casi limite e errori
5. **Non-Blocking**: Verifica che operazioni non-blocking non blocchino

### Logging

1. **Structured**: Usa sempre `extra={}` per metadata
2. **Stage Prefix**: Usa `[STAGE X]` per identificare stage
3. **Context**: Include sempre `document_id` e `stage`
4. **Errors**: Logga sempre `error_type` e `error` per errori
5. **Performance**: Include `duration_seconds` per operazioni lunghe

## Troubleshooting Test

### Problema: Test falliscono con AttributeError
**Soluzione**: Verifica che tutti i mock siano configurati correttamente

### Problema: Test async non funzionano
**Soluzione**: Usa `@pytest.mark.asyncio` e `AsyncMock` per async functions

### Problema: Coverage basso
**Soluzione**: Aggiungi test per branch non coperti (vedi report coverage)

## Riferimenti

- **Test File**: `apps/backend-rag/tests/unit/services/ingestion/test_legal_ingestion_service_coverage.py`
- **Service**: `apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py`
- **Pipeline Docs**: `docs/LEGAL_INGESTION_PIPELINE.md`
