# 📰 Fonti Dati Intel Scraper

## 🔍 Dove Trova le Informazioni nello Step Iniziale

Lo scraper trova le informazioni da **2 fonti principali**:

---

## 1️⃣ **Google News RSS** (`rss_fetcher.py`)

### Come Funziona:
- **Fonte:** Google News RSS Feed
- **URL Base:** `https://news.google.com/rss/search`
- **Query:** Ricerca per topic specifici (vedi sotto)
- **Lingua:** Inglese + Bahasa Indonesia (`hl=en-ID&gl=ID&ceid=ID:en`)

### Topic Monitorati (20+ query):

#### Immigration
- `Indonesia visa KITAS regulation`
- `Bali visa immigration`
- `Indonesia golden visa`
- `digital nomad visa Indonesia`

#### Business
- `Indonesia PT PMA foreign investment`
- `Indonesia business regulation BKPM`
- `Bali business startup`
- `Indonesia KBLI OSS`

#### Tax
- `Indonesia tax regulation pajak`
- `Indonesia NPWP tax`
- `Indonesia corporate tax PPh`

#### Property
- `Bali property real estate`
- `Indonesia land ownership foreigner`
- `Bali villa investment`

#### Tech/AI
- `Indonesia AI artificial intelligence`
- `Indonesia startup technology funding`
- `Indonesia fintech digital economy`
- `Indonesia kecerdasan buatan`

#### Lifestyle
- `Bali expat news`
- `Bali digital nomad`

### Output RSS:
```json
{
  "title": "Article Title",
  "summary": "Article summary from RSS",
  "source": "Source Name",
  "sourceUrl": "https://...",
  "category": "immigration|business|tax|property|tech|lifestyle",
  "publishedAt": "2025-01-10T12:00:00Z"
}
```

---

## 2️⃣ **790+ Fonti Web** (`unified_scraper.py` - BaliZeroScraperV2)

### Come Funziona:
- **Fonte:** Scraping diretto da siti web configurati
- **Config:** `config/unified_sources.json` + `config/extended_sources.json`
- **Metodo:** Web scraping con `SmartExtractor`
- **Categorie:** immigration, tax_bkpm, property, business, tech, etc.

### Esempio Configurazione:
```json
{
  "sources": [
    {
      "name": "Jakarta Post",
      "url": "https://www.thejakartapost.com",
      "category": "business",
      "tier": "T1",
      "selectors": {
        "title": "h1.article-title",
        "content": ".article-body"
      }
    }
  ]
}
```

---

## 🔄 Flusso Completo

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 0: SEMANTIC DEDUPLICATION (Qdrant)                    │
│  ✅ Controlla se l'articolo è già stato processato          │
│  ✅ Usa embedding vettoriale per similarità semantica       │
│  ✅ Se duplicato → SKIP (risparmio $$$)                     │
└─────────────────────────────────────────────────────────────┘
                    ↓ (solo se NON duplicato)
┌─────────────────────────────────────────────────────────────┐
│  FONTE DATI:                                                 │
│                                                              │
│  MODE "quick" o "full":                                     │
│  └─> Google News RSS (rss_fetcher.py)                      │
│      └─> 20+ query per topic                                │
│      └─> Professional scoring (5 dimensioni)               │
│                                                              │
│  MODE "massive":                                            │
│  └─> 790+ fonti web (unified_scraper.py)                   │
│      └─> Scraping diretto da siti configurati               │
│      └─> SmartExtractor per estrazione contenuto            │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: LLAMA SCORER                                       │
│  ✅ Scoring locale veloce (Ollama)                          │
│  ✅ Filtra noise (score < 40)                              │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2-7: Pipeline completa...                            │
│  (Claude Validation → Enrichment → Images → SEO → etc.)    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Quando Viene Eseguito Step 0?

**Step 0 (Semantic Deduplication) viene eseguito PRIMA di tutto:**

1. ✅ **Articolo arriva** (da RSS o web scraping)
2. ✅ **Step 0:** Controlla Qdrant per duplicati semantici
3. ✅ **Se duplicato:** SKIP immediato (non passa a Step 1)
4. ✅ **Se unico:** Continua con Step 1 (LLAMA Scoring)

### Codice (`intel_pipeline.py`):

```python
async def process_article(self, article: PipelineArticle):
    # STEP 0: SEMANTIC DEDUPLICATION (PRIMA DI TUTTO)
    logger.info("🧠 Step 0: Semantic Deduplication Check...")
    try:
        is_dup, original_title, score = await self.deduplicator.is_duplicate(
            article.title,
            article.summary,
            article.url
        )
        if is_dup:
            logger.warning(f"🛑 DUPLICATE DETECTED (Score: {score:.2f})")
            article.is_duplicate = True
            self.stats.dedup_filtered += 1
            return article  # ← SKIP, non processa oltre
    except Exception as e:
        logger.error(f"Dedup check failed (continuing safely): {e}")
    
    # STEP 1: LLAMA SCORING (solo se non duplicato)
    # ...
```

---

## 🎯 Modalità di Esecuzione

### `--mode quick`
- **Fonte:** Solo Google News RSS
- **Step 0:** ✅ Deduplicazione semantica
- **Step 1:** ✅ LLAMA Scoring
- **Step 2+:** ❌ No enrichment (solo scoring + invio)

### `--mode full`
- **Fonte:** Google News RSS
- **Step 0:** ✅ Deduplicazione semantica
- **Step 1:** ✅ LLAMA Scoring
- **Step 2-7:** ✅ Pipeline completa (Claude enrichment, images, SEO, etc.)

### `--mode massive`
- **Fonte:** 790+ fonti web (scraping diretto)
- **Step 0:** ✅ Deduplicazione semantica
- **Step 1:** ✅ LLAMA Scoring
- **Step 2-7:** ✅ Pipeline completa

---

## 💡 Vantaggi Step 0 (Semantic Deduplication)

1. **Risparmio Costi:** Filtra duplicati PRIMA di chiamare Claude ($0.01-0.05 per articolo)
2. **Velocità:** Controllo rapido con Qdrant (millisecondi)
3. **Precisione:** Similarità semantica (88% threshold) invece di solo URL matching
4. **Memoria:** Salva articoli approvati per deduplicazione futura

---

## 📊 Statistiche

- **RSS Topics:** 20+ query Google News
- **Web Sources:** 790+ siti configurati
- **Categorie:** immigration, business, tax, property, tech, lifestyle
- **Deduplicazione:** Similarità semantica > 88% = duplicato
- **Window:** Controlla solo ultimi 5 giorni (configurabile)

---

**In sintesi:** Lo scraper trova le informazioni da Google News RSS (20+ topic) e/o 790+ fonti web. Lo Step 0 (Semantic Deduplication) viene eseguito **PRIMA** di tutto per filtrare duplicati e risparmiare costi.
