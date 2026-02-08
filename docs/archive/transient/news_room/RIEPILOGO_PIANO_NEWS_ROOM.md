# Riepilogo Piano Integrazione News Room Dashboard

**Purpose:** Riepilogo completo dell'analisi e piano implementazione  
**Date:** 2026-01-24  
**Status:** ✅ ANALISI COMPLETA - PRONTO PER REVIEW

---

## 🎯 OBIETTIVO

Dashboard News Room (`https://zantara.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli completi dall'Intel Scraper
- ✅ Approvare/rifiutare articoli
- ✅ **Editare articoli** (titolo, contenuto, categoria)
- ✅ **Aggiungere/modificare cover image** se mancante
- ✅ Pubblicare articoli approvati

---

## ✅ COSA C'È GIÀ (Funziona)

### Frontend

- ✅ Pagina News Room esiste: `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
- ✅ Lista articoli pending funziona
- ✅ Filtri e ricerca funzionano
- ✅ Preview articolo (dialog) funziona
- ✅ Pulsante "Publish" funziona
- ✅ Bulk publish funziona
- ✅ Mostra warning se cover image mancante

### Backend

- ✅ Endpoint `POST /api/intel/scraper/submit` esiste
- ✅ Endpoint `GET /api/intel/staging/pending?type=news` esiste
- ✅ Endpoint `POST /api/intel/staging/publish/{type}/{id}` esiste
- ✅ Staging service funziona
- ✅ Salvataggio articoli in staging funziona

### Flusso Base

- ✅ Intel Scraper → Backend → Staging → Frontend funziona
- ✅ Articoli vengono mostrati nella dashboard

---

## ❌ COSA MANCA (Problemi Identificati)

### Problema 1: Preview HTML Non Disponibile

**Causa:** Preview HTML è solo locale, non viene inviato al backend

**Risultato:** Dashboard mostra solo markdown text, non preview HTML completo

### Problema 2: Editing Non Disponibile

**Causa:** Endpoint e componenti frontend non esistono

**Manca:**

- ❌ Endpoint `PUT /api/intel/staging/{type}/{id}` per editing
- ❌ Componente `ArticleEditor.tsx`
- ❌ Funzionalità editing nella dashboard

### Problema 3: Upload Cover Image Non Disponibile (MANUALE)

**Causa:** Endpoint e componenti frontend non esistono

**Manca:**

- ❌ Endpoint `POST /api/intel/staging/{type}/{id}/cover` per upload
- ❌ Componente `CoverImageUploader.tsx`
- ❌ Funzionalità upload nella dashboard

---

## 📋 PIANO IMPLEMENTAZIONE STEP-BY-STEP (AGGIORNATO)

**⚠️ IMPORTANTE:** Cover image NON viene inviata automaticamente dall'Intel Scraper.  
Viene aggiunta manualmente nella News Room quando l'articolo è già arricchito e impaginato.

### STEP 1: Includere Preview HTML nel Payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifica:** Aggiungere `preview_html` e `preview_url` al payload

**Cosa fare:**

1. Leggere preview HTML se disponibile
2. Includere nel payload come stringa
3. Includere preview_url (URL online)

### STEP 2: Backend Salva Preview HTML

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifica:** Salvare preview HTML file se presente

**Cosa fare:**

1. Se preview_html presente → salvare file
2. Aggiornare staging_data con path preview HTML

### STEP 3: Backend Endpoint Editing

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `PUT /api/intel/staging/{type}/{item_id}`

**Cosa fare:**

1. Creare `EditStagingItemRequest` model
2. Implementare endpoint editing
3. Validazione dati
4. Salvataggio modifiche

### STEP 4: Backend Endpoint Upload Cover Image (MANUALE)

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `POST /api/intel/staging/{type}/{item_id}/cover`

**Cosa fare:**

1. Creare `UploadCoverImageRequest` model
2. Implementare endpoint upload
3. Salvare file cover image
4. Aggiornare staging_data

### STEP 5: Frontend API Client Aggiornato

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Nuove funzioni:**

- `editItem(type, id, edits)`
- `uploadCoverImage(type, id, imageBase64, filename)`

### STEP 6: Frontend Componente Editor

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`

**Nuovo componente:** Editor per modificare titolo, contenuto, categoria

### STEP 7: Frontend Componente Upload Cover Image (MANUALE)

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Nuovo componente:** Uploader con drag & drop o file picker

### STEP 8: Integrazione nella Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:**

1. Aggiungere pulsante "Edit" su ogni card
2. Aggiungere pulsante "Upload Cover" se cover_image mancante
3. Integrare ArticleEditor (dialog/modal)
4. Integrare CoverImageUploader (dialog/modal)

---

## 🎯 PRIORITÀ IMPLEMENTAZIONE

### 🔴 Priorità ALTA (Blocca funzionalità)

1. **STEP 1:** Includere preview_html nel payload submission
2. **STEP 2:** Backend salva preview HTML
3. **STEP 4:** Backend endpoint upload cover image (MANUALE)
4. **STEP 7-8:** Upload cover image nella dashboard (MANUALE)

### 🟡 Priorità MEDIA (Migliora UX)

5. **STEP 3:** Backend endpoint editing articolo
6. **STEP 5-6:** Frontend componenti editor
7. **STEP 8:** Integrazione editing nella dashboard

### 🟢 Priorità BASSA (Nice to have)

8. Preview HTML completo nella dashboard
9. Link a preview online nella dashboard

---

## ⚠️ CRITICAL CONSIDERATIONS

### 1. Cover Image Upload Strategy (MANUALE)

**Workflow:**

1. Articolo arriva nella News Room SENZA cover image
2. Utente visualizza preview HTML completo (con componenti interattivi)
3. Utente decide cover image appropriata
4. Utente upload cover image manualmente tramite dashboard
5. Articolo completo viene pubblicato

**Formato:** Base64 upload → salvataggio file PNG nel backend

### 2. Preview HTML Strategy

**Opzioni:**

- **A)** Salvare HTML nel backend storage
- **B)** Usare URL preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)
- **C)** Generare HTML dal markdown nel frontend

**Raccomandazione:** Opzione B (URL online)

- Già disponibile e funzionante
- Non richiede storage aggiuntivo
- Accessibile da qualsiasi dispositivo

### 3. Editing Strategy

**Opzioni:**

- **A)** Editing completo (titolo, contenuto, categoria)
- **B)** Editing limitato (solo titolo e categoria)
- **C)** Solo aggiunta cover image

**Raccomandazione:** Opzione A (editing completo)

- Massima flessibilità
- Permette correzioni errori
- Migliora qualità articoli

---

## 📋 CHECKLIST PRE-IMPLEMENTAZIONE

Prima di iniziare l'implementazione:

- [x] ✅ Frontend page esiste (`news-room/page.tsx`)
- [x] ✅ Backend router esiste (`intel.py`)
- [x] ✅ Endpoint `/api/intel/scraper/submit` esiste
- [x] ✅ Endpoint `/api/intel/staging/pending` esiste
- [x] ✅ API client frontend esiste (`intelligence.api.ts`)
- [x] ✅ Flusso attuale documentato
- [x] ✅ Problemi identificati
- [x] ✅ Piano implementazione creato
- [ ] ⏳ **APPROVAZIONE UTENTE RICHIESTA**

---

## 🚀 ORDINE DI IMPLEMENTAZIONE RACCOMANDATO

1. **STEP 1-2:** Modificare Intel Scraper per inviare preview_html + Backend salva preview HTML
2. **STEP 3-4:** Backend endpoint editing e upload cover image (MANUALE)
3. **STEP 5:** Frontend API client aggiornato
4. **STEP 6-7:** Frontend componenti editor e uploader
5. **STEP 8:** Integrazione nella dashboard

**⚠️ IMPORTANTE:** Ogni step deve essere testato prima di procedere al successivo!

---

## 📚 DOCUMENTAZIONE CREATA

1. **docs/ANALISI_FLUSSO_NEWS_ROOM.md** - Analisi completa flusso attuale
2. **docs/PIANO_INTEGRAZIONE_NEWS_ROOM.md** - Piano generale integrazione
3. **docs/FLUSSO_COMPLETO_NEWS_ROOM.md** - Flusso dettagliato con problemi
4. **docs/PIANO_IMPLEMENTAZIONE_DETTAGLIATO.md** - Piano step-by-step con codice
5. **docs/RIEPILOGO_PIANO_NEWS_ROOM.md** - Questo documento (riepilogo)

---

## ✅ PROSSIMI PASSI

1. **Review piano** con utente
2. **Approvazione** modifiche proposte
3. **Implementazione** step-by-step
4. **Testing** per ogni step
5. **Deploy** incrementale

---

**Status:** ✅ ANALISI COMPLETA - PRONTO PER APPROVAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
