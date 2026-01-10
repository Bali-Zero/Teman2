# 📚 LE 11 COLLEZIONI QDRANT - Analisi Completa

**Data Analisi:** 2026-01-10  
**Metodo:** Analisi diretta API Qdrant + Campioni documenti  
**Totale Documenti:** 58,022

---

## 📊 OVERVIEW

| # | Collezione | Documenti | Tipo Contenuto | Status | Vector Size |
|---|------------|-----------|----------------|--------|-------------|
| 1 | `legal_unified_hybrid` | **47,959** | Text Document | ✅ Active | unknown |
| 2 | `training_conversations_hybrid` | 3,525 | Training Conversation | ✅ Active | unknown |
| 3 | `training_conversations` | 2,898 | Training Conversation | ✅ Active | 1536 |
| 4 | `kbli_unified` | 2,818 | Text Document | ✅ Active | unknown |
| 5 | `tax_genius_hybrid` | 332 | Text Document | ✅ Active | unknown |
| 6 | `tax_genius` | 332 | Text Document | ✅ Active | 1536 |
| 7 | `visa_oracle` | 82 | Text Document | ✅ Active | unknown |
| 8 | `bali_zero_pricing` | 70 | Pricing | ✅ Active | 1536 |
| 9 | `balizero_news_history` | 6 | News Article | ✅ Active | unknown |
| 10 | `collective_memories` | 0 | Unknown | 📭 Empty | 1536 |
| 11 | `bali_zero_pricing_hybrid` | 0 | Unknown | 🗑️ Obsolete | unknown |

**Totale:** 58,022 documenti

---

## 📋 DETTAGLIO COLLEZIONI

### 1. `legal_unified_hybrid` - **47,959 documenti**

**Tipo:** Text Document (Leggi e Regolamenti Indonesiani)  
**Status:** ✅ Active (PRIMARY)  
**Vector Config:** Single vector, unknown size

**Struttura Payload:**
- `metadata` (dict) - Metadati documento (book_title, book_author, source, etc.)
- `text` (str) - Testo completo del documento legale

**Contenuto:**
- Leggi indonesiane (UU, PP, Permen)
- Regolamenti governativi
- Testi normativi completi
- Include anche documenti da altre collezioni (consolidamento)

**Esempio Contenuto:**
```
(1) Penggabungan Daerah kabupaten/kota sebagaimana 
dimaksud dalam Pasal 44 ayat (1) huruf a yang dilakukan 
berdasarkan kesepakatan Daerah yang bersangkutan...
```

**Note:**
- ⚠️ Contiene molti più documenti del previsto (5,041 attesi)
- Probabile consolidamento di più collezioni legali
- Collezione PRIMARY per query legali

**Routing Keywords:** `legal`, `law`, `regulation`, `normativa`, `legge`

---

### 2. `training_conversations_hybrid` - **3,525 documenti**

**Tipo:** Training Conversation (Conversazioni Golden per Training)  
**Status:** ✅ Active  
**Vector Config:** Single vector, unknown size (hybrid format)

**Struttura Payload:**
- `category` (str) - Categoria conversazione (legal, business, visa, tax)
- `chunk_index` (int) - Indice chunk nella conversazione
- `data_version` (str) - Versione dati (es. "bali_zero_2025_corrected")
- `filename` (str) - Nome file sorgente
- `source` (str) - Path file sorgente
- `text` (str) - Testo chunk conversazione
- `title` (str) - Titolo conversazione completa
- `total_chunks` (int) - Numero totale chunk nella conversazione

**Contenuto:**
- Conversazioni golden per training AI
- Esempi di interazioni corrette
- Pattern di risposta ottimali
- Categorie: legal, business, visa, tax

**Esempio Contenuto:**
```
# Intellectual Property Basics — Full Conversation

> **Generated**: 2025-12-10
> **Topics Covered**: Trademark Registration, Copyright Protection...
```

**Note:**
- 🆕 Nuova collezione (non documentata)
- Formato hybrid (BM25 + Dense)
- Versione più recente di `training_conversations`

**Routing Keywords:** Nessuno (collezione interna per training)

---

### 3. `training_conversations` - **2,898 documenti**

**Tipo:** Training Conversation (Standard Format)  
**Status:** ✅ Active  
**Vector Config:** Single vector, 1536 dimensions, Cosine distance

**Struttura Payload:**
- `category` (str) - Categoria (business, visa, legal, tax)
- `chunk_index` (int) - Indice chunk
- `chunk_type` (str) - Tipo chunk (semantic, etc.)
- `file_name` (str) - Nome file
- `file_path` (str) - Path completo file
- `has_context` (bool) - Ha contesto aggiuntivo
- `language` (str) - Lingua (id, en)
- `parent_id` (str) - ID documento padre
- `source` (str) - Sorgente (training_conversation)
- `text` (str) - Testo chunk
- `topic` (str) - Argomento conversazione
- `total_chunks` (int) - Totale chunk

**Contenuto:**
- Conversazioni training formato standard
- Stesso contenuto di `training_conversations_hybrid` ma formato diverso
- Usa embeddings OpenAI (1536 dim)

**Esempio Contenuto:**
```
[CONTEXT: TRAINING - CATEGORY BUSINESS - TOPIC OSS NIB Registration - LANG ID]

Siapkan dokumen:
   - Akta pendirian
   - SK Kemenkumham
   - KTP Direktur...
```

**Note:**
- Versione standard (non hybrid)
- Probabilmente obsoleta rispetto a `training_conversations_hybrid`
- Mantenuta per compatibilità

**Routing Keywords:** Nessuno (collezione interna)

---

### 4. `kbli_unified` - **2,818 documenti**

**Tipo:** Text Document (Codici KBLI - Classificazione Business)  
**Status:** ✅ Active  
**Vector Config:** Single vector, unknown size

**Struttura Payload:**
- `metadata` (dict) - Metadati KBLI (kode, judul, risiko, etc.)
- `text` (str) - Testo completo codice KBLI

**Contenuto:**
- Codici KBLI (Klasifikasi Baku Lapangan Usaha Indonesia)
- Classificazione attività business
- Informazioni rischio, requisiti PMA
- Dati da PP 28/2025 e OSS RBA API

**Esempio Contenuto:**
```
[CONTEXT: KBLI 2025 - PP 28/2025 - Kode 1039 - Risiko N/A - Industri]

# KBLI 1039: Industri Pengolahan dan Pengawetan Lainnya 
Buah-buahan dan Sayuran
```

**Note:**
- ⚠️ Solo 2,818 documenti (vs 8,886 attesi)
- Possibile migrazione incompleta o cleanup
- Collezione PRIMARY per query KBLI

**Routing Keywords:** `kbli`, `business classification`, `klasifikasi`, `oss`, `nib`

---

### 5. `tax_genius_hybrid` - **332 documenti**

**Tipo:** Text Document (Regolamenti Fiscali - Hybrid Format)  
**Status:** ✅ Active  
**Vector Config:** Single vector, unknown size (hybrid format)

**Struttura Payload:**
- `metadata` (dict) - Metadati documento fiscale
- `text` (str) - Testo completo regolamento fiscale

**Contenuto:**
- Regolamenti fiscali indonesiani
- PPh 21, PPN/VAT
- Procedure fiscali
- Esempi e calcoli

**Esempio Contenuto:**
```
Nomor Faktur" → Request range baru (misal: 1-100)
Error 2: "ETAX-40001: Faktur Reject"
- Cause: NPWP buyer salah atau buyer bukan PKP
- Solution: Verifica NPWP buyer...
```

**Note:**
- Formato hybrid (BM25 + Dense)
- Identico contenuto a `tax_genius` standard
- Versione moderna con BM25

**Routing Keywords:** `tax`, `pajak`, `pph`, `ppn`, `vat`, `fiscal`

---

### 6. `tax_genius` - **332 documenti**

**Tipo:** Text Document (Regolamenti Fiscali - Standard Format)  
**Status:** ✅ Active  
**Vector Config:** Single vector, 1536 dimensions, Cosine distance

**Struttura Payload:**
- `metadata` (dict) - Metadati documento fiscale
- `text` (str) - Testo completo regolamento fiscale

**Contenuto:**
- Stesso contenuto di `tax_genius_hybrid`
- Formato standard (solo Dense vectors)
- Usa embeddings OpenAI (1536 dim)

**Esempio Contenuto:**
```
PPh 21 progresif → luwih gedhe gaji, luwih gedhe pajak
Gross salary: IDR 8,000,000
PPh 21 deduction: ~IDR 175,000...
```

**Note:**
- ⚠️ Duplicato di `tax_genius_hybrid`
- Probabilmente obsoleta (da rimuovere dopo migrazione completa)
- Mantenuta per compatibilità

**Routing Keywords:** `tax`, `pajak`, `pph`, `ppn`, `vat`

---

### 7. `visa_oracle` - **82 documenti**

**Tipo:** Text Document (Immigrazione e Visti)  
**Status:** ✅ Active  
**Vector Config:** Single vector, unknown size

**Struttura Payload:**
- `metadata` (dict) - Metadati visa (code, title, category, etc.)
- `text` (str) - Testo completo informazioni visa

**Contenuto:**
- Informazioni su visti indonesiani
- Codici visa (C22B, C4, C14, etc.)
- Requisiti e procedure
- KITAS, KITAP, permessi

**Esempio Contenuto:**
```
[CONTEXT: Immigration 2025 - Visa C22B - Visit Visa]

# C22B VISA PROGRAM MAGANG (INDUSTRI DAN PERUSAHAAN)

## Informazioni Base
- Codice Visa: C22B
- Categoria: Visit Visa
```

**Note:**
- ⚠️ Solo 82 documenti (vs 1,612 attesi)
- Possibile consolidamento in `legal_unified_hybrid`
- Collezione PRIMARY per query visa

**Routing Keywords:** `visa`, `kitas`, `kitap`, `immigration`, `imigrasi`, `passport`

---

### 8. `bali_zero_pricing` - **70 documenti**

**Tipo:** Pricing (Listino Prezzi Servizi)  
**Status:** ✅ Active  
**Vector Config:** Single vector, 1536 dimensions, Cosine distance

**Struttura Payload:**
- `category` (str) - Categoria servizio (urgent_services, kitas_permits, etc.)
- `currency` (str) - Valuta (IDR)
- `duration` (str) - Durata servizio
- `last_updated` (str) - Data ultimo aggiornamento
- `name` (str) - Nome servizio
- `notes` (str) - Note aggiuntive
- `price` (str) - Prezzo servizio
- `source_type` (str) - Tipo sorgente (bali_zero_pricing)
- `text` (str) - Testo completo servizio
- `validity` (str) - Validità prezzo

**Contenuto:**
- Listino prezzi servizi Bali Zero
- Servizi urgenti, KITAS, permessi
- Prezzi aggiornati
- Informazioni contatti

**Esempio Contenuto:**
```
# Urgent 2 Hari
**Category**: Urgent Services
**Price**: 2.500.000 IDR

**Contact**: info@balizero.com
**WhatsApp**: +62 813 3805 1876
```

**Note:**
- ✅ Collezione attiva e popolata
- Usata da `PricingTool` nel sistema Agentic RAG
- Prezzi aggiornati al 2025-12-31

**Routing Keywords:** `price`, `cost`, `harga`, `quanto costa`, `prezzo`

---

### 9. `balizero_news_history` - **6 documenti**

**Tipo:** News Article (Storia News Bali Zero)  
**Status:** ✅ Active  
**Vector Config:** Single vector, unknown size

**Struttura Payload:**
- `category` (str) - Categoria news (tax, legal, etc.)
- `ingested_at` (str) - Data ingestion
- `published_at` (str) - Data pubblicazione
- `source` (str) - Sorgente news (es. "Tempo.co English")
- `source_url` (str) - URL articolo originale
- `summary` (str) - Riassunto articolo
- `tier` (str) - Tier importanza (T2, etc.)
- `title` (str) - Titolo articolo

**Contenuto:**
- Articoli news processati dal pipeline Intel Scraper
- News rilevanti per Bali Zero
- Categorie: tax, legal, business

**Esempio Contenuto:**
```
Title: Indonesia Misses 2025 Tax Target by Rp271 Trillion
Summary: Indonesia's 2025 tax revenue missed target by Rp271T. 
Expect stricter enforcement...
Category: tax
Tier: T2
```

**Note:**
- 🆕 Nuova collezione (non documentata)
- Piccola collezione (solo 6 documenti)
- Parte del sistema Intel Scraper

**Routing Keywords:** Nessuno (collezione interna)

---

### 10. `collective_memories` - **0 documenti**

**Tipo:** Unknown (Memoria Collettiva Team)  
**Status:** 📭 Empty (vuota ma attiva)  
**Vector Config:** Single vector, 1536 dimensions, Cosine distance

**Struttura Payload:**
- Nessun campo (collezione vuota)

**Contenuto:**
- Dovrebbe contenere memorie collettive del team
- Fatti condivisi appresi da più utenti
- Attualmente vuota

**Note:**
- 📭 Collezione vuota ma configurata correttamente
- Dovrebbe essere popolata dal sistema Collective Memory
- Non eliminare - potrebbe essere necessaria

**Routing Keywords:** Nessuno (collezione interna)

---

### 11. `bali_zero_pricing_hybrid` - **0 documenti**

**Tipo:** Unknown (Pricing Hybrid - Obsoleta)  
**Status:** 🗑️ Obsolete (vuota, da rimuovere)  
**Vector Config:** Single vector, unknown size

**Struttura Payload:**
- Nessun campo (collezione vuota)

**Contenuto:**
- Dovrebbe essere versione hybrid di `bali_zero_pricing`
- Creata ma mai popolata
- Obsoleta

**Note:**
- 🗑️ **DA RIMUOVERE** - Collezione vuota e obsoleta
- `bali_zero_pricing` standard è sufficiente
- Script cleanup disponibile: `scripts/cleanup_obsolete_collections.py`

**Routing Keywords:** Nessuno (non usata)

---

## 📊 ANALISI PER CATEGORIA

### Collezioni PRIMARY (Usate dal Query Router)

1. **`legal_unified_hybrid`** - Query legali
2. **`kbli_unified`** - Query KBLI/business
3. **`visa_oracle`** - Query visa/immigrazione
4. **`tax_genius`** / **`tax_genius_hybrid`** - Query fiscali
5. **`bali_zero_pricing`** - Query prezzi

### Collezioni TRAINING (Per migliorare AI)

6. **`training_conversations_hybrid`** - Training formato hybrid
7. **`training_conversations`** - Training formato standard

### Collezioni SPECIALI

8. **`balizero_news_history`** - News processate
9. **`collective_memories`** - Memoria collettiva (vuota)

### Collezioni OBSOLETE

10. **`tax_genius`** - Duplicato di `tax_genius_hybrid` (da valutare rimozione)
11. **`bali_zero_pricing_hybrid`** - Vuota, obsoleta (da rimuovere)

---

## 🔄 PATTERN IDENTIFICATI

### Duplicati Standard vs Hybrid

| Standard | Hybrid | Status |
|----------|--------|--------|
| `tax_genius` (332) | `tax_genius_hybrid` (332) | Identici - Standard obsoleta |
| `training_conversations` (2,898) | `training_conversations_hybrid` (3,525) | Hybrid ha più documenti |
| `bali_zero_pricing` (70) | `bali_zero_pricing_hybrid` (0) | Hybrid vuota - obsoleta |

**Raccomandazione:**
- Mantenere solo versioni hybrid quando disponibili
- Rimuovere standard quando migrazione completata

---

## 📈 STATISTICHE PER TIPO

| Tipo Contenuto | Collezioni | Documenti Totali |
|----------------|------------|-----------------|
| Text Document | 5 | 53,523 |
| Training Conversation | 2 | 6,423 |
| Pricing | 1 | 70 |
| News Article | 1 | 6 |
| Unknown/Empty | 2 | 0 |

---

## ✅ CONCLUSIONI

### Collezioni Attive e Funzionanti
- ✅ 9 collezioni popolate e utilizzate
- ✅ 1 collezione vuota ma necessaria (`collective_memories`)
- ✅ 1 collezione obsoleta da rimuovere (`bali_zero_pricing_hybrid`)

### Collezioni PRIMARY
- ✅ `legal_unified_hybrid` - PRIMARY per query legali (47,959 docs)
- ✅ `kbli_unified` - PRIMARY per query KBLI (2,818 docs)
- ✅ `visa_oracle` - PRIMARY per query visa (82 docs)
- ✅ `tax_genius_hybrid` - PRIMARY per query fiscali (332 docs)
- ✅ `bali_zero_pricing` - PRIMARY per query prezzi (70 docs)

### Note Importanti
- ⚠️ `legal_unified_hybrid` contiene molti più documenti del previsto (consolidamento)
- ⚠️ `kbli_unified` e `visa_oracle` hanno meno documenti del previsto (verificare)
- ✅ Sistema funzionante con collezioni attuali

---

**Analisi completata:** 2026-01-10  
**Report JSON:** `docs/QDRANT_COLLECTIONS_ANALYSIS.json`
