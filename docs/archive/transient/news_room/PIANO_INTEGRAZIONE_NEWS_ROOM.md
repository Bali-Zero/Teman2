# Piano Integrazione News Room Dashboard

**Purpose:** Piano dettagliato per integrare articoli Intel Scraper nella dashboard News Room  
**Date:** 2026-01-24  
**Status:** 📋 PIANIFICAZIONE

---

## 🎯 OBIETTIVO FINALE

Dashboard News Room (`https://kita.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli pending dall'Intel Scraper
- ✅ Approvare/rifiutare articoli
- ✅ Editare articoli (titolo, contenuto, categoria)
- ✅ Aggiungere/modificare cover image se mancante
- ✅ Pubblicare articoli approvati

---

## 📊 FASE 1: ANALISI COMPONENTI ESISTENTI

### 1.1 Frontend - News Room Page

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Status:** ✅ ESISTE GIÀ

**Da verificare:**

- [ ] Cosa mostra attualmente?
- [ ] Quali API chiama?
- [ ] Quali componenti usa?
- [ ] Cosa manca per mostrare articoli Intel Scraper?

### 1.2 Backend - Intel Router

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint esistenti trovati:**

- ✅ `POST /api/intel/scraper/submit` - Riceve articoli dall'Intel Scraper
- ✅ `GET /api/intel/staging/pending` - Lista articoli pending (da verificare)
- ✅ `POST /api/intel/staging/{id}/approve` - Approva articolo (da verificare)
- ✅ `POST /api/intel/staging/{id}/reject` - Rifiuta articolo (da verificare)

**Da verificare:**

- [ ] Struttura dati salvata nel database
- [ ] Se cover images sono salvate correttamente
- [ ] Se preview HTML è accessibile
- [ ] Endpoint per editing articoli
- [ ] Endpoint per upload cover image

### 1.3 Database Schema

**Da verificare:**

- [ ] Tabella/collection per staging articles
- [ ] Campi disponibili
- [ ] Relazioni con altri dati
- [ ] Indici per performance

### 1.4 API Client Frontend

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Da verificare:**

- [ ] Funzioni esistenti per chiamare backend
- [ ] Se supporta già staging/pending articles
- [ ] Se supporta approvazione/editing

---

## 🔍 FASE 2: VERIFICA DETTAGLIATA

### 2.1 Verifica Backend Endpoints

**Comandi:**

```bash
# Leggi router intel.py completo
cat apps/backend-rag/backend/app/routers/intel.py

# Verifica endpoint disponibili
grep -E "@router\.(get|post|put|delete)" apps/backend-rag/backend/app/routers/intel.py

# Verifica struttura dati
grep -A 20 "class.*Request\|class.*Response" apps/backend-rag/backend/app/routers/intel.py
```

### 2.2 Verifica Frontend Page

**Comandi:**

```bash
# Leggi pagina news-room completa
cat apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx

# Verifica componenti usati
grep -E "import.*from" apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx

# Verifica API calls
grep -E "fetch|api\." apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx
```

### 2.3 Verifica Database

**Comandi:**

```bash
# Cerca migration files
find apps/backend-rag -name "*migration*" -o -name "*schema*" | grep -i intel

# Cerca modelli database
grep -r "staging\|pending.*article" apps/backend-rag/backend --include="*.py" | head -20
```

---

## 📋 FASE 3: GAP ANALYSIS

### 3.1 Cosa C'è Già

**Backend:**

- ✅ Endpoint per ricevere articoli (`/api/intel/scraper/submit`)
- ✅ Endpoint per listare pending (da verificare)
- ✅ Endpoint per approvare (da verificare)

**Frontend:**

- ✅ Pagina News Room esiste
- ✅ Layout Intelligence Center esiste

### 3.2 Cosa Manca (Da Verificare)

**Backend:**

- [ ] Endpoint per editing articoli
- [ ] Endpoint per upload cover image
- [ ] Endpoint per pubblicare articoli
- [ ] Validazione cover image
- [ ] Storage cover images

**Frontend:**

- [ ] Componente lista articoli pending
- [ ] Componente preview articolo
- [ ] Componente editor articolo
- [ ] Componente upload cover image
- [ ] Integrazione con API backend
- [ ] Gestione stati (pending, approved, rejected)

**Database:**

- [ ] Verifica schema staging articles
- [ ] Campo per cover image path
- [ ] Campo per preview HTML path
- [ ] Indici per performance

---

## 🚀 FASE 4: PIANO IMPLEMENTAZIONE (DA DEFINIRE DOPO ANALISI)

### Step 1: Verifica e Documentazione Componenti Esistenti

- [ ] Leggere completamente `intel.py` router
- [ ] Leggere completamente `news-room/page.tsx`
- [ ] Leggere completamente `intelligence.api.ts`
- [ ] Documentare struttura dati attuale
- [ ] Documentare endpoint esistenti
- [ ] Creare diagramma flusso attuale

### Step 2: Backend - Completare Endpoints Mancanti

- [ ] Endpoint GET `/api/intel/staging/pending` (se manca)
- [ ] Endpoint GET `/api/intel/staging/{id}` (dettaglio articolo)
- [ ] Endpoint PUT `/api/intel/staging/{id}` (editing articolo)
- [ ] Endpoint POST `/api/intel/staging/{id}/cover` (upload cover image)
- [ ] Endpoint POST `/api/intel/staging/{id}/publish` (pubblicazione)
- [ ] Validazione dati
- [ ] Gestione errori

### Step 3: Database - Verifica e Migrazioni

- [ ] Verificare schema esistente
- [ ] Creare migrazioni se necessario
- [ ] Aggiungere campi mancanti (cover_image_path, preview_html_path)
- [ ] Creare indici per performance

### Step 4: Frontend - Componenti Dashboard

- [ ] Componente `ArticleList.tsx` (lista articoli pending)
- [ ] Componente `ArticleCard.tsx` (card articolo con preview)
- [ ] Componente `ArticlePreview.tsx` (preview completo)
- [ ] Componente `ArticleEditor.tsx` (editor articolo)
- [ ] Componente `CoverImageUploader.tsx` (upload cover image)
- [ ] Componente `ApprovalActions.tsx` (pulsanti approva/rifiuta)
- [ ] Integrazione API calls
- [ ] Gestione stati e loading

### Step 5: Integrazione End-to-End

- [ ] Test flusso Intel Scraper → Backend → Database
- [ ] Test flusso Database → Backend API → Frontend
- [ ] Test approvazione articolo
- [ ] Test editing articolo
- [ ] Test upload cover image
- [ ] Test pubblicazione articolo

### Step 6: Testing e Refinement

- [ ] Test unitari backend
- [ ] Test integrazione API
- [ ] Test componenti frontend
- [ ] Test end-to-end completo
- [ ] Fix bug e edge cases
- [ ] Ottimizzazione performance

---

## ⚠️ CRITICAL REQUIREMENTS

### Cover Image Handling

**Problema attuale:** Gli articoli hanno cover image path ma i file non sono sempre presenti localmente.

**Soluzioni possibili:**

1. **Upload da Intel Scraper:** Inviare cover image come base64 nel payload
2. **Storage Backend:** Salvare cover images nel backend (S3/Fly volumes)
3. **URL Reference:** Se cover image è già su CDN, salvare solo URL
4. **Fallback:** Se cover image manca, permettere upload manuale nella dashboard

**Raccomandazione:** Implementare soluzione ibrida:

- Intel Scraper invia cover image come base64 se disponibile
- Backend salva cover image in storage permanente
- Dashboard permette upload manuale se cover image manca

### Preview HTML

**Problema attuale:** Preview HTML è salvato localmente nell'Intel Scraper.

**Soluzioni possibili:**

1. **Includere nel payload:** Inviare preview HTML nel JSON payload
2. **Storage Backend:** Salvare preview HTML nel backend
3. **URL Reference:** Usare URL preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)

**Raccomandazione:** Usare URL reference (già disponibile) + salvare HTML nel backend come backup.

---

## 📋 CHECKLIST PRE-IMPLEMENTAZIONE

Prima di iniziare l'implementazione, verificare:

- [ ] ✅ Frontend page esiste (`news-room/page.tsx`)
- [ ] ✅ Backend router esiste (`intel.py`)
- [ ] ⏳ Endpoint `/api/intel/scraper/submit` funziona
- [ ] ⏳ Endpoint `/api/intel/staging/pending` esiste e funziona
- [ ] ⏳ Database schema verificato
- [ ] ⏳ API client frontend verificato
- [ ] ⏳ Flusso attuale documentato
- [ ] ⏳ Gap analysis completata
- [ ] ⏳ Piano implementazione approvato

---

## 🎯 PROSSIMI PASSI IMMEDIATI

1. **Leggere file esistenti completamente:**
   - `apps/backend-rag/backend/app/routers/intel.py` (tutto)
   - `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx` (tutto)
   - `apps/mouth/src/lib/api/intelligence.api.ts` (tutto)

2. **Verificare database schema:**
   - Trovare migration files
   - Verificare struttura tabelle staging

3. **Testare endpoint esistenti:**
   - Chiamare `/api/intel/staging/pending`
   - Verificare risposta e struttura dati

4. **Creare diagramma flusso completo:**
   - Intel Scraper → Backend → Database → Frontend

5. **Definire piano implementazione dettagliato:**
   - Step-by-step con file specifici
   - Dipendenze tra step
   - Testing per ogni step

---

**Status:** 📋 PIANIFICAZIONE IN CORSO  
**Next:** Leggere completamente i file esistenti per capire cosa c'è già
