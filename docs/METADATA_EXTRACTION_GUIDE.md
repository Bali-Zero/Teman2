# Metadata Extraction Guide

## Overview

Questo documento descrive il processo di estrazione metadata strutturati dal testo dei documenti Qdrant.

## Processo

### 1. Estrazione Metadata

Lo script `extract_and_update_metadata.py` analizza il testo dei documenti e estrae metadata strutturati usando pattern matching e parsing.

**Collezioni supportate:**
- `visa_oracle` - Estrae tipo visa, fee, duration, entry type
- `kbli_unified` - Estrae codice KBLI, descrizione, investment minimum, risk level
- `tax_genius` - Estrae tax type, tax rate, effective date
- `legal_unified` - Estrae law_id, pasal, status_vigensi, year
- `bali_zero_pricing` - Estrae service name, price USD/IDR

### 2. Pattern di Estrazione

#### Visa Oracle
- **Visa Type**: Pattern `[A-Z]\d+ VISA` (es. C7 VISA, D1 VISA)
- **Fee USD**: Pattern `$XXX` o `USD XXX`
- **Fee IDR**: Pattern `IDR XXX` o `Rp XXX`
- **Duration**: Pattern `X days/weeks/months`
- **Entry Type**: Pattern `single/multiple entry`

#### KBLI Unified
- **KBLI Code**: Pattern `\d{5}` (codice a 5 cifre)
- **Description**: Prima riga o header Markdown
- **Investment Minimum**: Pattern `investment.*IDR XXX`
- **Risk Level**: Pattern `risk level.*(low/medium/high)`

#### Tax Genius
- **Tax Type**: Headers Markdown o prima riga contenente "tax"
- **Tax Rate**: Pattern `X%` o `rate: X`
- **Effective Date**: Pattern `YYYY-MM-DD`

#### Legal Unified
- **Law ID**: Pattern `UU/PERMEN/PERDA No. X/YYYY`
- **Pasal**: Pattern `pasal X`
- **Status Vigensi**: Pattern `berlaku/dicabut/diubah`
- **Year**: Pattern `19XX` o `20XX`

### 3. Applicazione Aggiornamenti

Lo script `apply_metadata_updates.py` applica gli aggiornamenti estratti ai documenti Qdrant.

**Sicurezza:**
- Richiede conferma esplicita (`APPLICA` + `CONFERMA`)
- Supporta dry-run per preview
- Batch update per performance

## Utilizzo

### Estrazione Metadata (Test Mode)

```bash
python scripts/extract_and_update_metadata.py
```

Questo genera un report JSON con i metadata estratti **senza modificare** Qdrant.

### Applicazione Aggiornamenti

```bash
python scripts/apply_metadata_updates.py
```

Questo script:
1. Carica risultati estrazione
2. Mostra preview aggiornamenti
3. Richiede conferma doppia
4. Applica aggiornamenti in batch

## Statistiche Estrazione

Basato su test con 50 documenti per collezione:

| Collezione | Success Rate | Campi Estratti |
|------------|-------------|----------------|
| `kbli_unified` | 100% | kbli_code, kbli_description, investment_minimum |
| `legal_unified` | 90% | law_id, pasal, status_vigensi, year |
| `visa_oracle` | 70% | visa_type, fee_usd, fee_idr, duration |
| `tax_genius` | 64% | tax_type, tax_rate, effective_date |
| `bali_zero_pricing` | 41% | service_name, price_usd, price_idr |

## Miglioramenti Futuri

1. **ML-based extraction**: Usare LLM per estrazione più accurata
2. **Validation**: Validare metadata estratti contro schema
3. **Incremental updates**: Aggiornare solo documenti modificati
4. **Monitoring**: Tracciare qualità estrazione nel tempo

## Schema Metadata

Vedi `docs/QDRANT_METADATA_SCHEMA.md` per schema completo.

