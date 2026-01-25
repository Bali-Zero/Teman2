# Analisi Intel Scraper + Article Composer

## Confronto Codebase vs Documentazione

**Data Analisi:** 2026-01-24  
**Scopo:** Verificare corrispondenza tra implementazione e documentazione

---

## 📊 EXECUTIVE SUMMARY

| Componente                  | Codebase    | Documentazione | Stato           | Note                             |
| --------------------------- | ----------- | -------------- | --------------- | -------------------------------- |
| **Intel Scraper Pipeline**  | ✅ Completo | ⚠️ Parziale    | **DISCREPANZA** | Doc manca Step 0 (Deduplication) |
| **Article Composer**        | ✅ Completo | ✅ Completo    | **OK**          | Corrispondenza perfetta          |
| **Intel Router Backend**    | ✅ Completo | ❌ Mancante    | **MANCANZA**    | Nessuna doc API backend          |
| **Article Composer Router** | ✅ Completo | ✅ Completo    | **OK**          | Doc completa                     |

---

## 🔍 INTEL SCRAPER - Analisi Dettagliata

### 1. Pipeline Flow - Confronto

#### **Codebase** (`apps/bali-intel-scraper/scripts/intel_pipeline.py`)

```python
# Step 0: SEMANTIC DEDUPLICATION (Qdrant) ← MANCA NELLA DOC!
# Step 1: RSS FETCHER
# Step 2: LLAMA SCORER
# Step 3: CLAUDE VALIDATOR
# Step 4: CLAUDE MAX ENRICHMENT
# Step 5: IMAGE GENERATION (mandatory)
# Step 5.5: SEO/AEO OPTIMIZATION
# Step 6: SUBMIT FOR APPROVAL (Telegram + News Room)
# Step 7: AUTO-MEMORY (Qdrant)
```

#### **Documentazione** (`apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md`)

```
Step 1: RSS FETCHER
Step 2: LLAMA SCORER
Step 3: CLAUDE VALIDATOR
Step 4: CLAUDE MAX ENRICHMENT
Step 5: CLAUDE IMAGE REASONING
Step 5.5: SEO/AEO OPTIMIZATION
Step 6: TELEGRAM APPROVAL
Step 7: PUBLISH TO API
```

**DISCREPANZE IDENTIFICATE:**

1. ❌ **Step 0 (Semantic Deduplication) MANCA nella documentazione**
   - Codebase: Implementato in `semantic_deduplicator.py` e `semantic_deduplicator_httpx.py`
   - Funzione: Controlla similarità > 88% con articoli recenti
   - Importanza: **CRITICA** - salva $ evitando duplicati
   - Fix richiesto: Aggiungere Step 0 nella doc

2. ⚠️ **Step 6 descritto diversamente**
   - Codebase: "SUBMIT FOR APPROVAL (parallel)" → Telegram + News Room UI
   - Doc: Solo "TELEGRAM APPROVAL"
   - Fix: Documentare entrambi i canali (Telegram + News Room)

3. ⚠️ **Step 7 descritto diversamente**
   - Codebase: "AUTO-MEMORY (Qdrant)" - salva per future deduplicazioni
   - Doc: "PUBLISH TO API" - generico
   - Fix: Specificare che salva in Qdrant per deduplication

### 2. Componenti - Verifica Esistenza

| Componente             | File Codebase                  | Documentato | Note                          |
| ---------------------- | ------------------------------ | ----------- | ----------------------------- |
| `SemanticDeduplicator` | ✅ `semantic_deduplicator.py`  | ❌          | **MANCA** nella doc           |
| `OllamaScorer`         | ✅ `ollama_scorer.py`          | ✅          | OK                            |
| `ClaudeValidator`      | ✅ `claude_validator.py`       | ✅          | OK                            |
| `ArticleDeepEnricher`  | ✅ `article_deep_enricher.py`  | ✅          | OK                            |
| `GeminiImageGenerator` | ✅ `gemini_image_generator.py` | ✅          | OK                            |
| `SEOAEOOptimizer`      | ✅ `seo_aeo_optimizer.py`      | ✅          | OK                            |
| `TelegramApproval`     | ✅ `telegram_approval.py`      | ✅          | OK                            |
| `PreviewGenerator`     | ✅ `preview_generator.py`      | ⚠️          | Menzionato ma non dettagliato |
| `MetricsCollector`     | ✅ `metrics.py`                | ✅          | OK                            |
| `StructuredLogger`     | ✅ `logging_config.py`         | ✅          | OK                            |

### 3. Backend Integration - Router Intel

**Codebase:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoints implementati:**

```python
POST /api/intel/scraper/submit          # Riceve articoli da scraper
GET  /api/intel/staging/pending         # Lista pending
GET  /api/intel/staging/preview/{type}/{item_id}  # Preview
POST /api/intel/staging/approve/{type}/{item_id}  # Approve
POST /api/intel/staging/reject/{type}/{item_id}  # Reject
POST /api/intel/staging/publish/{type}/{item_id}  # Publish
POST /api/intel/staging/bulk-approve/{type}      # Bulk approve
POST /api/intel/staging/bulk-reject/{type}        # Bulk reject
POST /api/intel/search                  # Semantic search
POST /api/intel/store                    # Store in Qdrant
GET  /api/intel/metrics                 # System metrics
GET  /api/intel/critical                 # Critical items
GET  /api/intel/trends                   # Trending topics
GET  /api/intel/analytics                # Analytics
GET  /api/intel/stats/{collection}       # Collection stats
```

**Documentazione:** ❌ **MANCA COMPLETAMENTE**

**Fix richiesto:** Creare `docs/INTEL_ROUTER_API.md` con:

- Descrizione endpoint
- Request/Response models
- Esempi di utilizzo
- Integrazione con scraper pipeline

### 4. Cost Breakdown - Verifica

**Documentazione dice:**

```
- Qdrant check: $0
- LLAMA scoring: $0
- Claude validation: ~$0.01/article
- Claude Max enrichment: ~$0.05/article
- Gemini image: $0
- SEO/AEO optimization: $0
Total: ~$0.06/article
```

**Codebase verifica:**

- ✅ Qdrant: Gratis (infrastructure)
- ✅ LLAMA: Gratis (local Ollama)
- ✅ Claude validation: ~$0.01 (quick validation)
- ✅ Claude Max enrichment: ~$0.05 (full article)
- ✅ Gemini image: $0 (Google One AI Premium)
- ✅ SEO/AEO: $0 (local processing)

**Risultato:** ✅ **CORRETTO**

### 5. Telegram Approval System - Verifica

**Documentazione:** ✅ Completa (`PIPELINE_DOCUMENTATION.md` lines 159-256)

**Codebase:** ✅ Implementato (`telegram_approval.py`)

**Verifica corrispondenza:**

- ✅ HTML preview generation
- ✅ Telegram notifications
- ✅ Approve/Reject/Request Changes buttons
- ✅ Multi-recipient support
- ✅ Article tracking

**Risultato:** ✅ **CORRETTO**

---

## 📝 ARTICLE COMPOSER - Analisi Dettagliata

### 1. API Endpoints - Verifica

**Codebase:** `apps/backend-rag/backend/app/routers/article_composer.py`

**Endpoints implementati:**

```python
POST /api/articles/compose          # Enrich article
POST /api/articles/publish          # Publish to GitHub
GET  /api/articles/compose/status   # Check compose config
GET  /api/articles/publish/status   # Check publish config
```

**Documentazione:** ✅ Completa (`docs/ARTICLE_COMPOSER_API.md`)

**Verifica corrispondenza:**

| Endpoint              | Codebase | Doc | Request Model     | Response Model     | Status |
| --------------------- | -------- | --- | ----------------- | ------------------ | ------ |
| `POST /compose`       | ✅       | ✅  | ✅ ComposeRequest | ✅ ComposeResponse | ✅ OK  |
| `POST /publish`       | ✅       | ✅  | ✅ PublishRequest | ✅ PublishResponse | ✅ OK  |
| `GET /compose/status` | ✅       | ✅  | -                 | ✅ dict            | ✅ OK  |
| `GET /publish/status` | ✅       | ✅  | -                 | ✅ dict            | ✅ OK  |

**Risultato:** ✅ **PERFETTA CORRISPONDENZA**

### 2. Enrichment Prompt - Verifica

**Codebase:** `article_composer.py` lines 123-207

**Documentazione:** ✅ Descritto (`ARTICLE_COMPOSER_API.md` lines 128-145)

**Verifica:**

- ✅ System prompt: "Senior Editor at Bali Zero"
- ✅ Output format: JSON con headline, tldr, facts, bali_zero_take, next_steps
- ✅ Word count by priority: High=600, Medium=500, Low=400
- ✅ Model: `claude-sonnet-4-20250514`

**Risultato:** ✅ **CORRETTO**

### 3. Publishing Flow - Verifica

**Codebase:** `article_composer.py` lines 510-619

**Documentazione:** ✅ Descritto (`ARTICLE_COMPOSER_API.md` lines 148-238)

**Verifica:**

- ✅ MDX generation: `generate_mdx_content()`
- ✅ GitHub API: `github_publisher.upload_file()` o `create_commit_with_files()`
- ✅ Category mapping: immigration → immigration, tax → tax-legal, etc.
- ✅ File locations: MDX in `apps/mouth/src/content/articles/`, images in `apps/mouth/public/static/news/`
- ✅ Vercel auto-deploy: Triggered by GitHub commit

**Risultato:** ✅ **CORRETTO**

### 4. Error Handling - Verifica

**Codebase:** Try/except blocks con logging

**Documentazione:** ✅ Descritto (`ARTICLE_COMPOSER_API.md` lines 296-376)

**Verifica:**

- ✅ Claude API errors
- ✅ JSON parse errors
- ✅ GitHub API errors
- ✅ Missing configuration errors

**Risultato:** ✅ **CORRETTO**

### 5. Metrics - Verifica

**Codebase:** Prometheus metrics (`article_composer.py` lines 23-54)

**Documentazione:** ⚠️ Menzionato ma non implementato (`ARTICLE_COMPOSER_API.md` lines 482-504)

**Metrics implementate:**

```python
article_compose_requests_total{status, category}
article_compose_duration_seconds
article_enrichment_word_count{priority}
article_publish_requests_total{status, has_cover_image}
claude_api_cost_cents
```

**Documentazione dice:** "To be implemented"

**Fix richiesto:** Aggiornare doc per riflettere che metrics sono già implementate

---

## 🔗 INTEGRAZIONE TRA INTEL SCRAPER E ARTICLE COMPOSER

### Relazione Attuale

**Intel Scraper:**

- Processa articoli da RSS feeds
- Arricchisce con Claude Max
- Genera immagini con Gemini
- Invia a News Room + Telegram per approval
- Pubblica in Qdrant dopo approval

**Article Composer:**

- Processa articoli manuali (marketing team)
- Arricchisce con Claude Sonnet 4
- Pubblica direttamente su GitHub (Vercel)
- Non passa per approval workflow

### Potenziale Integrazione

**Osservazione:** Entrambi usano:

- Claude per enrichment (modelli diversi)
- Gemini per immagini (stesso sistema)
- SEO/AEO optimization (stesso sistema)

**Opportunità:**

1. Condividere `ArticleDeepEnricher` tra Intel Scraper e Article Composer
2. Unificare sistema di generazione immagini
3. Condividere SEO/AEO optimizer

**Attualmente:** ❌ Non condivisi (duplicazione codice)

---

## 📋 CHECKLIST CORREZIONI RICHIESTE

### Intel Scraper

- [x] **CRITICO:** Aggiungere Step 0 (Semantic Deduplication) in `PIPELINE_DOCUMENTATION.md` ✅ **COMPLETATO**
- [x] **IMPORTANTE:** Documentare entrambi i canali di approval (Telegram + News Room) nello Step 6 ✅ **COMPLETATO**
- [x] **IMPORTANTE:** Specificare che Step 7 salva in Qdrant per deduplication ✅ **COMPLETATO**
- [x] **IMPORTANTE:** Creare `docs/INTEL_ROUTER_API.md` con documentazione completa endpoint backend ✅ **COMPLETATO**
- [ ] **OPZIONALE:** Aggiungere dettagli su `PreviewGenerator` nella doc

### Article Composer

- [x] **IMPORTANTE:** Aggiornare sezione Metrics in `ARTICLE_COMPOSER_API.md` per riflettere implementazione esistente ✅ **COMPLETATO**
- [ ] **OPZIONALE:** Aggiungere esempi di integrazione con Intel Scraper

### Generale

- [ ] **OPZIONALE:** Creare documento unificato che spiega relazione tra Intel Scraper e Article Composer
- [ ] **OPZIONALE:** Documentare opportunità di code sharing tra i due sistemi

---

## 📊 STATISTICHE FINALI

| Categoria                  | Totale      | OK  | Discrepanze      | Mancanze                 |
| -------------------------- | ----------- | --- | ---------------- | ------------------------ |
| **Intel Scraper Pipeline** | 8 step      | 6   | 2                | 1 (Step 0)               |
| **Intel Router Backend**   | 13 endpoint | 13  | 0                | 13 (doc mancante)        |
| **Article Composer API**   | 4 endpoint  | 4   | 0                | 0                        |
| **Componenti Intel**       | 10          | 9   | 0                | 1 (SemanticDeduplicator) |
| **Metrics**                | 5           | 5   | 1 (doc outdated) | 0                        |

**Totale Discrepanze:** 3  
**Totale Mancanze:** 15 (principalmente doc backend router)

---

## 🎯 PRIORITÀ CORREZIONI

### 🔴 CRITICO (Fare subito)

1. Aggiungere Step 0 (Semantic Deduplication) nella doc Intel Scraper
2. Creare documentazione API per Intel Router Backend

### 🟡 IMPORTANTE (Fare presto)

3. Documentare entrambi i canali di approval (Telegram + News Room)
4. Specificare Step 7 (Auto-Memory) nella doc
5. Aggiornare sezione Metrics in Article Composer doc

### 🟢 OPZIONALE (Fare quando possibile)

6. Aggiungere dettagli PreviewGenerator
7. Documentare integrazione Intel Scraper ↔ Article Composer
8. Creare documento unificato

---

**Analisi completata:** 2026-01-24  
**Correzioni completate:** 2026-01-24

## ✅ CORREZIONI IMPLEMENTATE

### 1. Intel Scraper Pipeline Documentation ✅

**File:** `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md`

**Modifiche:**

- ✅ Aggiunto Step 0: Semantic Deduplication con descrizione completa
- ✅ Aggiornato Step 6: Documentati entrambi i canali (Telegram + News Room UI)
- ✅ Aggiornato Step 7: Specificato Auto-Memory (Qdrant) per deduplication
- ✅ Aggiunto Step 8: Publish to API (separato da Auto-Memory)
- ✅ Aggiunta sezione "Semantic Deduplicator" con esempi di utilizzo
- ✅ Aggiornato Cost Breakdown con Step 0
- ✅ Aggiornato File Structure con componenti deduplication
- ✅ Aggiunto changelog entry per 2026-01-24

### 2. Intel Router API Documentation ✅

**File:** `docs/INTEL_ROUTER_API.md` (NUOVO)

**Contenuto:**

- ✅ Documentazione completa di tutti i 15 endpoint
- ✅ Request/Response models per ogni endpoint
- ✅ Esempi di utilizzo
- ✅ Error handling
- ✅ Integrazione con Intel Scraper pipeline
- ✅ Prometheus metrics
- ✅ Best practices
- ✅ Development guide

### 3. Article Composer Metrics Documentation ✅

**File:** `docs/ARTICLE_COMPOSER_API.md`

**Modifiche:**

- ✅ Aggiornata sezione Monitoring: da "To be implemented" a "✅ IMPLEMENTED"
- ✅ Aggiunti esempi di query Prometheus
- ✅ Aggiunte istruzioni per accedere alle metrics
- ✅ Aggiornato changelog con v1.1

---

## 📊 STATO FINALE

| Categoria                  | Totale      | OK  | Discrepanze | Mancanze |
| -------------------------- | ----------- | --- | ----------- | -------- |
| **Intel Scraper Pipeline** | 8 step      | 8   | 0           | 0 ✅     |
| **Intel Router Backend**   | 13 endpoint | 13  | 0           | 0 ✅     |
| **Article Composer API**   | 4 endpoint  | 4   | 0           | 0 ✅     |
| **Componenti Intel**       | 10          | 10  | 0           | 0 ✅     |
| **Metrics**                | 5           | 5   | 0           | 0 ✅     |

**Totale Discrepanze:** 0 ✅  
**Totale Mancanze:** 0 ✅

**Tutte le correzioni critiche e importanti sono state completate!**
