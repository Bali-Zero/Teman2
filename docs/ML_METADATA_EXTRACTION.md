# ML-Based Metadata Extraction Guide

## Overview

Usa **Zantara AI (Gemini)** per estrarre metadata strutturati dal testo in modo più accurato rispetto ai pattern regex.

## Vantaggi ML vs Pattern

| Aspetto | Pattern Regex | ML (Gemini) |
|---------|---------------|-------------|
| **Accuratezza** | 70-100% (varia) | ~95-99% |
| **Velocità** | ⚡ Molto veloce | 🐢 Più lento |
| **Costo** | Gratis | ~$0.0001 per documento |
| **Flessibilità** | Rigido (pattern specifici) | Adattivo (capisce contesto) |
| **Manutenzione** | Richiede aggiornamento pattern | Auto-adattivo |

## Quando Usare ML

### ✅ Usa ML quando:
- Documenti con struttura variabile
- Pattern complessi difficili da regex
- Necessità alta accuratezza (>95%)
- Testi non standardizzati
- Collezioni nuove senza pattern definiti

### ⚡ Usa Pattern quando:
- Struttura molto standardizzata
- Performance critica (migliaia di documenti)
- Budget limitato
- Pattern già ben definiti

## Architettura Ibrida (Raccomandato)

**Approccio migliore**: Usa **Pattern come fallback** e **ML per casi complessi**

```python
# 1. Prova Pattern (veloce, gratis)
pattern_metadata = pattern_extractor.extract(collection, text)

# 2. Se Pattern fallisce o incomplete, usa ML
if len(pattern_metadata) < threshold:
    ml_metadata = ml_extractor.extract(collection, text)
    # Merge: ML ha priorità
    metadata = {**pattern_metadata, **ml_metadata}
```

## Setup

### 1. Configura API Key

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Oppure nel file `.env`:
```
GOOGLE_API_KEY=your-api-key-here
```

### 2. Usa Hybrid Extractor

```python
from scripts.ml_metadata_extractor import HybridMetadataExtractor

extractor = HybridMetadataExtractor()

# Pattern only (veloce)
metadata = extractor.extract(collection_name, text, use_ml=False)

# Hybrid (pattern + ML)
metadata = extractor.extract(collection_name, text, use_ml=True)
```

## Costi Stimati

Per **25,458 documenti**:
- **Pattern**: Gratis
- **ML (Gemini 2.5 Flash)**: ~$2.50
  - Input: ~500 tokens/doc × $0.075/1M = $0.0000375/doc
  - Output: ~100 tokens/doc × $0.30/1M = $0.00003/doc
  - Totale: ~$0.0000675/doc × 25,458 = **$1.72**

## Strategia Raccomandata

### Fase 1: Pattern-Based (Attuale)
- ✅ Già implementato
- ✅ Success rate: 70-100%
- ✅ Gratis e veloce

### Fase 2: Hybrid (Raccomandato)
- Usa Pattern per documenti standardizzati
- Usa ML solo per:
  - Documenti dove Pattern fallisce
  - Collezioni nuove
  - Validazione qualità

### Fase 3: ML-First (Opzionale)
- Se budget permette e accuratezza critica
- Usa ML per tutti i documenti
- Pattern come fallback se ML fallisce

## Implementazione

### Script Disponibili

1. **`ml_metadata_extractor.py`**
   - Estrazione ML-based
   - Hybrid extractor (pattern + ML)
   - Test e validazione

### Esempio Uso

```python
from scripts.ml_metadata_extractor import HybridMetadataExtractor

extractor = HybridMetadataExtractor()

# Estrai con ML per documenti complessi
complex_docs = [...]  # Documenti dove pattern fallisce
for doc in complex_docs:
    metadata = extractor.extract(
        collection_name="visa_oracle",
        text=doc["text"],
        use_ml=True  # Abilita ML
    )
```

## Prompt Engineering

Il prompt ML è ottimizzato per:
- **Structured output**: Richiede JSON valido
- **Schema-aware**: Usa schema metadata definito
- **Low temperature**: 0.1 per consistenza
- **Context-aware**: Include descrizione campi

### Prompt Template

```
Estrai metadata strutturati dal seguente testo secondo lo schema specificato.

COLLEZIONE: {collection_name}

SCHEMA METADATA:
- field1 (type): description
- field2 (type): description

TESTO DA ANALIZZARE:
{text}

ISTRUZIONI:
1. Estrai SOLO i campi presenti nel testo
2. Usa valori esatti quando possibile
3. Restituisci SOLO un JSON valido

JSON METADATA:
```

## Monitoring

Traccia:
- **Success rate** ML vs Pattern
- **Costo per documento**
- **Tempo di estrazione**
- **Qualità metadata estratti**

## Best Practices

1. **Start with Pattern**: Usa pattern per la maggior parte dei documenti
2. **ML for Edge Cases**: Usa ML solo quando necessario
3. **Batch Processing**: Processa in batch per efficienza
4. **Caching**: Cache risultati ML per documenti simili
5. **Validation**: Valida sempre metadata estratti contro schema

## Prossimi Passi

1. ✅ Pattern-based extraction implementato
2. 🔄 ML-based extraction implementato (richiede API key)
3. ⏳ Hybrid extractor da integrare in pipeline produzione
4. ⏳ Monitoring e analytics
5. ⏳ Auto-learning da feedback utente
