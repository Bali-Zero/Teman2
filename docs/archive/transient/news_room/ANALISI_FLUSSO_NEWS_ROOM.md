# Analisi Flusso News Room Dashboard

**Purpose:** Analizzare il flusso completo degli articoli dall'Intel Scraper alla dashboard News Room  
**Date:** 2026-01-24  
**Status:** 🔍 ANALISI IN CORSO

---

## 🎯 OBIETTIVO

Integrare gli articoli completi dell'Intel Scraper nella dashboard News Room:

- **URL:** https://kita.balizero.com/intelligence/news-room
- **Funzionalità:** Approvazione, Editing, Aggiunta Cover Image

---

## 📋 FASE 1: ANALISI FLUSSO ATTUALE

### 1.1 Flusso Intel Scraper → Backend

**Punto di partenza:** `apps/bali-intel-scraper/scripts/run_intel_feed.py`

**Flusso attuale:**

```
1. Intel Scraper crea articolo completo
   → Salvato in: data/pending_articles/{id}.json
   → Preview HTML: data/previews/{id}.html
   → Cover Image: data/images/cover_*.png

2. Invio a Telegram (opzionale)
   → telegram_approval.py
   → Notifica con preview link
   → Pulsanti Approve/Reject

3. Invio a Backend API
   → article_deep_enricher.py → send_to_api()
   → Endpoint: /api/intel/scraper/submit (da verificare)
   → Status: pending
```

**Da verificare:**

- [ ] Endpoint backend che riceve articoli
- [ ] Struttura dati inviata
- [ ] Come vengono salvati nel database
- [ ] Se esiste già endpoint per listare pending

### 1.2 Backend → Database

**Da verificare:**

- [ ] Tabella/collection dove vengono salvati gli articoli pending
- [ ] Schema dati
- [ ] Relazioni con altri dati (cover images, preview, etc.)

### 1.3 Backend → Frontend

**Da verificare:**

- [ ] Endpoint API per listare articoli pending
- [ ] Endpoint API per approvare articoli
- [ ] Endpoint API per editing articoli
- [ ] Endpoint API per upload cover image
- [ ] Endpoint API per pubblicare articoli

### 1.4 Frontend Dashboard

**URL Target:** `https://kita.balizero.com/intelligence/news-room`

**Da verificare:**

- [ ] Se esiste già la pagina/news-room
- [ ] Struttura routing Next.js
- [ ] Componenti esistenti
- [ ] API client configurato

---

## 📊 FASE 2: MAPPA COMPONENTI ESISTENTI

### 2.1 Backend Endpoints (da verificare)

```
GET  /api/intel/articles/pending      → Lista articoli pending
GET  /api/intel/articles/{id}         → Dettaglio articolo
POST /api/intel/articles/{id}/approve → Approva articolo
POST /api/intel/articles/{id}/reject  → Rifiuta articolo
PUT  /api/intel/articles/{id}         → Modifica articolo
POST /api/intel/articles/{id}/cover   → Upload cover image
POST /api/intel/articles/{id}/publish → Pubblica articolo
```

### 2.2 Frontend Components (da creare/verificare)

```
/app/intelligence/news-room/page.tsx          → Pagina principale
/app/intelligence/news-room/components/
  ├── ArticleList.tsx                        → Lista articoli
  ├── ArticleCard.tsx                        → Card articolo
  ├── ArticlePreview.tsx                     → Preview articolo
  ├── ApprovalActions.tsx                    → Pulsanti approvazione
  ├── ArticleEditor.tsx                      → Editor articolo
  └── CoverImageUploader.tsx                 → Upload cover image
```

### 2.3 Database Schema (da verificare)

```sql
-- Da verificare struttura esistente
articles_pending (
  id, article_id, title, category,
  enriched_content, cover_image_path,
  preview_html_path, status, created_at,
  approved_at, reviewed_by, ...
)
```

---

## 🔍 FASE 3: VERIFICA COMPONENTI ESISTENTI

### 3.1 Backend - Endpoint Intel Scraper

**File da verificare:**

- `apps/backend-rag/backend/app/routers/crm_enhanced.py`
- `apps/backend-rag/backend/app/routers/dashboard_summary.py`
- Altri router che potrebbero gestire intel/articles

**Comandi:**

```bash
grep -r "intel.*scraper\|scraper.*submit" apps/backend-rag/backend/app/routers/
grep -r "/api/intel\|/api/news" apps/backend-rag/backend/app/routers/
```

### 3.2 Frontend - Routing e Pages

**File da verificare:**

- `apps/mouth/src/app/(workspace)/intelligence/` (se esiste)
- `apps/mouth/src/app/intelligence/` (se esiste)
- Routing configuration

**Comandi:**

```bash
find apps/mouth/src/app -name "*intel*" -o -name "*news*"
ls -la apps/mouth/src/app/
```

### 3.3 Database - Schema Articles

**File da verificare:**

- Migration files
- Models/ORM definitions
- Database schema documentation

---

## 📝 FASE 4: PIANO DI IMPLEMENTAZIONE (DA DEFINIRE)

### Step 1: Backend API Endpoints

- [ ] Verificare endpoint esistenti
- [ ] Creare/modificare endpoint per listare pending
- [ ] Creare endpoint per approvazione
- [ ] Creare endpoint per editing
- [ ] Creare endpoint per upload cover image
- [ ] Creare endpoint per pubblicazione

### Step 2: Database Schema

- [ ] Verificare schema esistente
- [ ] Creare/modificare tabelle se necessario
- [ ] Migrazioni database

### Step 3: Frontend Dashboard

- [ ] Verificare struttura routing esistente
- [ ] Creare pagina news-room se non esiste
- [ ] Creare componenti lista articoli
- [ ] Creare componente preview articolo
- [ ] Creare componente editor
- [ ] Creare componente upload cover image
- [ ] Integrare API calls

### Step 4: Integrazione Flusso

- [ ] Collegare Intel Scraper → Backend API
- [ ] Collegare Backend → Frontend Dashboard
- [ ] Test end-to-end

### Step 5: Testing

- [ ] Test unitari backend
- [ ] Test integrazione API
- [ ] Test componenti frontend
- [ ] Test end-to-end completo

---

## ⚠️ NOTE IMPORTANTI

1. **Non implementare nulla ancora** - Solo analisi e pianificazione
2. **Verificare componenti esistenti** prima di creare nuovi
3. **Strutturare il piano** in modo dettagliato
4. **Considerare edge cases** (cover image mancante, editing parziale, etc.)
5. **Pensare all'UX** - Dashboard intuitiva e funzionale

---

## 📋 PROSSIMI PASSI

1. ✅ Analisi flusso attuale (questo documento)
2. ⏳ Verifica componenti backend esistenti
3. ⏳ Verifica componenti frontend esistenti
4. ⏳ Verifica database schema
5. ⏳ Creazione piano dettagliato implementazione
6. ⏳ Review piano con utente
7. ⏳ Implementazione step-by-step

---

**Status:** 🔍 ANALISI IN CORSO  
**Next:** Verificare componenti esistenti nel codebase
