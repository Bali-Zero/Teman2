# CRM Drive Folder - Download Flow Documentation

**Created:** 2026-01-20  
**Purpose:** Documentazione dettagliata del flusso download/scaricamento documenti

---

## 🎯 PRINCIPIO FONDAMENTALE

**L'utente NON entra mai in Google Drive. Tutto avviene nel workspace.**

```
┌─────────────────────────────────────────────────────────┐
│  WORKSPACE CRM                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Utente vede:                                   │   │
│  │  - Lista file                                   │   │
│  │  - Preview immagini                              │   │
│  │  - Pulsante Download                            │   │
│  └─────────────────────────────────────────────────┘   │
│                    │                                     │
│                    │ Click Download                     │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Backend Proxy                                  │   │
│  │  GET /api/documents/proxy/{file_id}             │   │
│  └─────────────────────────────────────────────────┘   │
│                    │                                     │
│                    │ Google Drive API                    │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Google Drive (Storage Backend)                 │   │
│  │  File scaricato → Backend → Browser             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ✅ Utente NON vede mai Drive                          │
│  ✅ File scaricato direttamente nel browser            │
└─────────────────────────────────────────────────────────┘
```

---

## 📥 FLUSSO DOWNLOAD DETTAGLIATO

### Scenario 1: Download Singolo File

**Step-by-Step:**

```
1. Utente nel browser documenti workspace
   ↓
2. Vede lista file:
   📄 passport_marco.pdf    2.3 MB  [⬇️ Download]
   ↓
3. Click su [⬇️ Download]
   ↓
4. Frontend chiama:
   GET /api/documents/proxy/1JKL...XYZ
   Headers: { Authorization: Bearer ... }
   ↓
5. Backend verifica:
   - Utente autenticato? ✅
   - Utente ha accesso al cliente? ✅
   - File esiste su Drive? ✅
   ↓
6. Backend chiama Google Drive API:
   files.get(fileId='1JKL...XYZ')
   files.get_media(fileId='1JKL...XYZ')
   ↓
7. Backend riceve file stream da Drive
   ↓
8. Backend streama file al frontend:
   Headers:
   - Content-Type: application/pdf
   - Content-Disposition: attachment; filename="passport_marco.pdf"
   - Content-Length: 2359296
   ↓
9. Browser scarica file direttamente
   ↓
10. ✅ File salvato nella cartella Download utente
    ✅ Nome file: passport_marco.pdf
    ✅ Utente NON ha visto Drive
```

### Scenario 2: Download Multiplo File (ZIP)

**Step-by-Step:**

```
1. Utente seleziona multipli file:
   ☑️ passport_marco.pdf
   ☑️ kitas_application.pdf
   ☑️ visa_stamp.jpg
   ↓
2. Click su [⬇️ Download All]
   ↓
3. Frontend chiama:
   POST /api/documents/batch-download
   Body: { file_ids: ["1JKL...", "2MNO...", "3PQR..."] }
   ↓
4. Backend:
   - Scarica tutti i file da Drive
   - Crea ZIP in memoria
   - Streama ZIP al frontend
   ↓
5. Browser scarica ZIP
   ↓
6. ✅ File: documents_2026-01-20.zip
    ✅ Utente NON ha visto Drive
```

### Scenario 3: Preview Immagine

**Step-by-Step:**

```
1. Utente vede thumbnail immagine
   ↓
2. Click su immagine per preview
   ↓
3. Frontend chiama:
   GET /api/documents/thumbnail/1JKL...XYZ?size=large
   ↓
4. Backend:
   - Scarica thumbnail da Drive
   - Cache thumbnail (24h)
   - Ritorna immagine
   ↓
5. Frontend mostra preview full-size
   ↓
6. ✅ Immagine visualizzata nel workspace
    ✅ Utente NON ha visto Drive
```

---

## 🔄 FLUSSO UPLOAD DETTAGLIATO

### Scenario: Upload File in Cartella

**Step-by-Step:**

```
1. Utente in modal upload
   ↓
2. Seleziona file: passport_new.pdf
   Seleziona cartella: 01_Immigration
   ↓
3. Click [📤 Upload]
   ↓
4. Frontend chiama:
   POST /api/clients/10218/drive-folder/01_Immigration/upload
   Content-Type: multipart/form-data
   Body: { file: File }
   ↓
5. Backend:
   - Verifica permessi utente
   - Verifica cartella esiste
   - Upload file su Drive (invisibile)
   ↓
6. Google Drive API:
   files.create({
     name: "passport_new.pdf",
     parents: ["1GHI...XYZ"],  // 01_Immigration folder
     media_body: file_content
   })
   ↓
7. Backend riceve file_id da Drive
   ↓
8. Backend risponde:
   {
     "success": true,
     "file_id": "4STU...XYZ",
     "file_name": "passport_new.pdf",
     "download_url": "/api/documents/proxy/4STU...XYZ",  ← Proxy URL
     "size_bytes": 2457600
   }
   ↓
9. Frontend:
   - Chiude modal
   - Aggiorna lista file (ottimistic update)
   - Mostra toast: "File uploaded successfully"
   ↓
10. ✅ File visibile nel workspace immediatamente
     ✅ Utente NON sa che è su Drive
     ✅ Download URL è proxy (non Drive)
```

---

## 🌐 FUTURO: Portale Cliente

### Architettura Futura

```
┌─────────────────────────────────────────────────────────┐
│  PORTALE CLIENTE (Futuro)                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Cliente vede:                                 │   │
│  │  - I propri documenti                          │   │
│  │  - Preview documenti                          │   │
│  │  - Download documenti                          │   │
│  └─────────────────────────────────────────────────┘   │
│                    │                                     │
│                    │ Stesso Backend Proxy                │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Backend Proxy                                  │   │
│  │  GET /api/documents/proxy/{file_id}             │   │
│  │  (con autenticazione cliente)                   │   │
│  └─────────────────────────────────────────────────┘   │
│                    │                                     │
│                    │ Google Drive API                    │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Google Drive (Storage Backend)                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ✅ Cliente NON vede mai Drive                         │
│  ✅ Stesso flusso del workspace                        │
│  ✅ Stesso backend proxy                               │
└─────────────────────────────────────────────────────────┘
```

### Endpoint Portale (Futuro)

```typescript
// Stesso endpoint, autenticazione diversa
GET / api / portal / documents / { file_id } / download;
GET / api / portal / documents / { file_id } / preview;

// Backend verifica:
// - Cliente autenticato?
// - File appartiene al cliente?
// - Cliente ha permesso di vedere questo file?
```

---

## 🔐 SICUREZZA DOWNLOAD

### Access Control Layers

```
1. Frontend Check:
   - Utente autenticato?
   - Utente ha accesso al cliente?
   ↓
2. Backend Check:
   - JWT token valido?
   - Utente ha permesso su questo cliente?
   - File esiste?
   - File appartiene a questo cliente?
   ↓
3. Google Drive Check:
   - Service account ha accesso al file?
   - File non eliminato?
   ↓
4. Download:
   - Stream file al frontend
   - Log accesso per audit
```

### Audit Trail

```sql
CREATE TABLE document_access_log (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(255),
    client_id INTEGER,
    user_email VARCHAR(255),
    access_type VARCHAR(50), -- 'download', 'preview', 'upload'
    ip_address INET,
    user_agent TEXT,
    accessed_at TIMESTAMP DEFAULT NOW()
);
```

---

## 📊 METRICHE & MONITORING

### Metriche da Tracciare

1. **Download Success Rate**: % download completati con successo
2. **Download Time**: Tempo medio download (p50, p95, p99)
3. **Proxy Cache Hit Rate**: % richieste servite da cache
4. **Drive API Errors**: Errori Google Drive API
5. **File Size Distribution**: Distribuzione dimensioni file

### Alerting

- ⚠️ Download error rate > 5%
- ⚠️ Download time p95 > 10s
- ⚠️ Drive API quota exceeded
- ⚠️ Proxy cache hit rate < 50%

---

## 🚀 OPTIMIZAZIONI FUTURE

### 1. CDN per Download

```
Google Drive → Backend → CDN → Browser
```

- Cache file statici su CDN
- Riduce latenza download
- Riduce carico su backend

### 2. Streaming Progress

```
Frontend mostra progress bar durante download:
[████████░░] 80% - 1.8 MB / 2.3 MB
```

### 3. Resume Download

```
Se download interrotto:
- Salva stato download
- Permetti resume da punto interrotto
```

### 4. Preview PDF Inline

```
Preview PDF direttamente nel browser workspace
(senza download)
```

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend

- [ ] Endpoint `/api/documents/proxy/{file_id}` funzionante
- [ ] Endpoint `/api/documents/thumbnail/{file_id}` funzionante
- [ ] Access control verificato
- [ ] Audit logging implementato
- [ ] Error handling robusto
- [ ] Rate limiting su download

### Frontend

- [ ] Download link usa sempre proxy URL
- [ ] Nessun link esterno a Drive
- [ ] Progress bar durante download
- [ ] Error handling user-friendly
- [ ] Preview immagini inline
- [ ] Download multipli (ZIP)

### Testing

- [ ] Test download singolo file
- [ ] Test download multipli
- [ ] Test preview immagini
- [ ] Test access control
- [ ] Test error handling
- [ ] Test performance (file grandi)

---

**Last Updated:** 2026-01-20  
**Principle:** Mai accesso diretto a Drive - tutto via proxy backend
