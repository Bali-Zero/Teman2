# CRM Google Drive Folder - Architecture & Backend Design

**Created:** 2026-01-20  
**Status:** Design Phase  
**Purpose:** Architettura backend per gestione cartelle Google Drive nel CRM

---

## 🏗️ ARCHITETTURA GENERALE

### Principio Fondamentale

**Google Drive è SOLO storage backend - invisibile all'utente**

```
┌─────────────────────────────────────────────────────────┐
│  REGOLA D'ORO: MAI ACCESSO DIRETTO A DRIVE             │
│                                                         │
│  ❌ Frontend NON chiama mai drive.google.com           │
│  ❌ Frontend NON apre mai Drive in nuova tab           │
│  ❌ Frontend NON mostra mai link Drive all'utente      │
│                                                         │
│  ✅ Tutto passa per Backend Proxy                      │
│  ✅ Tutto rimane dentro Workspace                      │
│  ✅ In futuro: anche Portale Cliente                   │
└─────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Workspace)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Browser    │  │   Upload     │  │   Download   │  │
│  │  Documenti   │  │   Modal      │  │   Proxy      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
                        │ HTTP API
                        ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Folder     │  │   File       │  │   Proxy      │  │
│  │   Service    │  │   Service    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Google Drive API
                        ▼
┌─────────────────────────────────────────────────────────┐
│              GOOGLE DRIVE (Storage)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Folders    │  │   Files      │  │   Metadata   │  │
│  │   (Backend)  │  │   (Backend)  │  │   (Backend)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Utente NON vede mai Google Drive direttamente.**

---

## 📡 API ENDPOINTS NECESSARI

### Folder Management (Esistenti)

#### 1. `POST /api/clients/{client_id}/create-drive-folder`

**Status:** ✅ Esistente  
**Funzione:** Crea struttura folder standardizzata

**Request:**

```json
{}
```

**Response:**

```json
{
  "success": true,
  "root_folder_id": "1ABC...XYZ",
  "root_folder_url": "https://drive.google.com/...",
  "root_folder_name": "10218_Marco_Rossi",
  "folders": {
    "00_Profile": {"id": "...", "url": "..."},
    "01_Immigration": {"id": "...", "url": "..."},
    ...
  },
  "created_count": 6
}
```

#### 2. `GET /api/clients/{client_id}/drive-folder`

**Status:** ✅ Esistente  
**Funzione:** Verifica folder esistente

**Response:**

```json
{
  "client_id": 10218,
  "folder_id": "1ABC...XYZ",
  "folder_url": "https://drive.google.com/...",
  "exists": true
}
```

#### 3. `DELETE /api/clients/{client_id}/drive-folder`

**Status:** ✅ Esistente  
**Funzione:** Unlink folder (non elimina)

---

### Nuovi Endpoints Necessari

#### 4. `GET /api/clients/{client_id}/drive-folder/structure`

**Status:** ❌ Da creare  
**Funzione:** Ottiene struttura completa folder con file count

**Response:**

```json
{
  "root_folder_id": "1ABC...XYZ",
  "folders": [
    {
      "name": "00_Profile",
      "id": "1DEF...XYZ",
      "file_count": 12,
      "total_size_bytes": 5242880,
      "last_modified": "2026-01-20T10:30:00Z"
    },
    {
      "name": "01_Immigration",
      "id": "1GHI...XYZ",
      "file_count": 23,
      "total_size_bytes": 47185920,
      "last_modified": "2026-01-20T12:15:00Z"
    },
    ...
  ],
  "total_files": 47,
  "total_size_bytes": 131072000
}
```

#### 5. `GET /api/clients/{client_id}/drive-folder/{folder_name}/files`

**Status:** ❌ Da creare  
**Funzione:** Lista file in una sottocartella

**Query Params:**

- `limit`: int (default: 50, max: 200)
- `offset`: int (default: 0)
- `search`: string (opzionale, cerca nel nome file)

**Response:**

```json
{
  "folder_name": "01_Immigration",
  "folder_id": "1GHI...XYZ",
  "files": [
    {
      "id": "1JKL...XYZ",
      "name": "passport_marco.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 2359296,
      "created_time": "2026-01-15T08:20:00Z",
      "modified_time": "2026-01-15T08:20:00Z",
      "thumbnail_url": "/api/documents/thumbnail/1JKL...XYZ",
      "download_url": "/api/documents/proxy/1JKL...XYZ"
    },
    ...
  ],
  "total": 23,
  "limit": 50,
  "offset": 0
}
```

#### 6. `POST /api/clients/{client_id}/drive-folder/{folder_name}/upload`

**Status:** ❌ Da creare  
**Funzione:** Upload file direttamente in una cartella

**Request:**

```multipart/form-data
file: File
```

**Response:**

```json
{
  "success": true,
  "file_id": "1JKL...XYZ",
  "file_name": "passport_marco.pdf",
  "folder_id": "1GHI...XYZ",
  "folder_name": "01_Immigration",
  "size_bytes": 2359296,
  "download_url": "/api/documents/proxy/1JKL...XYZ"
}
```

#### 7. `GET /api/clients/{client_id}/drive-folder/stats`

**Status:** ❌ Da creare  
**Funzione:** Statistiche aggregate folder

**Response:**

```json
{
  "total_files": 47,
  "total_size_bytes": 131072000,
  "total_size_mb": 125.0,
  "last_synced": "2026-01-20T12:30:00Z",
  "by_category": {
    "00_Profile": { "files": 2, "size_mb": 5.2 },
    "01_Immigration": { "files": 23, "size_mb": 45.0 },
    "02_Company": { "files": 12, "size_mb": 26.3 },
    "03_Tax": { "files": 8, "size_mb": 17.1 },
    "04_Family": { "files": 2, "size_mb": 4.1 },
    "99_Misc": { "files": 0, "size_mb": 0.0 }
  }
}
```

---

## 🔧 SERVIZI BACKEND

### 1. GoogleDriveService (Esistente)

**File:** `backend/services/integrations/google_drive_service.py`

**Metodi esistenti:**

- `create_folder()` ✅
- `get_file()` ✅
- `is_connected()` ✅

**Metodi da aggiungere:**

```python
async def list_folder_files(
    self,
    folder_id: str,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None
) -> dict[str, Any]:
    """
    Lista file in una cartella Drive.

    Returns:
    {
        "files": [...],
        "total": 23,
        "limit": 50,
        "offset": 0
    }
    """

async def get_folder_structure(
    self,
    root_folder_id: str
) -> dict[str, Any]:
    """
    Ottiene struttura completa folder con statistiche.

    Returns:
    {
        "folders": [...],
        "total_files": 47,
        "total_size_bytes": 131072000
    }
    """

async def upload_file_to_folder(
    self,
    folder_id: str,
    file_content: bytes,
    file_name: str,
    mime_type: str
) -> dict[str, Any]:
    """
    Upload file direttamente in una cartella Drive.

    Returns:
    {
        "id": "1JKL...XYZ",
        "name": "passport_marco.pdf",
        "size_bytes": 2359296
    }
    """

async def get_folder_stats(
    self,
    root_folder_id: str
) -> dict[str, Any]:
    """
    Calcola statistiche aggregate per folder.

    Returns:
    {
        "total_files": 47,
        "total_size_bytes": 131072000,
        "by_category": {...}
    }
    """
```

---

### 2. DocumentProxyService (Da migliorare)

**File:** `backend/app/routers/documents_proxy.py` (esistente)

**Endpoints esistenti:**

- `GET /api/documents/proxy/{file_id}` ✅
- `GET /api/documents/thumbnail/{file_id}` ✅

**Miglioramenti necessari:**

- Supporto download multipli (zip)
- Cache thumbnail più aggressiva
- Supporto preview PDF direttamente nel browser

---

## 🗄️ DATABASE SCHEMA

### Tabella `clients` (Esistente)

```sql
ALTER TABLE clients ADD COLUMN google_drive_folder_id VARCHAR(255);
CREATE INDEX idx_clients_drive_folder ON clients(google_drive_folder_id);
```

### Nuova Tabella: `drive_folder_sync_log`

```sql
CREATE TABLE drive_folder_sync_log (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    folder_id VARCHAR(255) NOT NULL,
    sync_type VARCHAR(50), -- 'structure', 'files', 'stats'
    files_count INTEGER,
    total_size_bytes BIGINT,
    synced_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'success', -- 'success', 'error', 'partial'
    error_message TEXT
);

CREATE INDEX idx_sync_log_client ON drive_folder_sync_log(client_id);
CREATE INDEX idx_sync_log_folder ON drive_folder_sync_log(folder_id);
CREATE INDEX idx_sync_log_synced_at ON drive_folder_sync_log(synced_at DESC);
```

**Scopo:** Tracciare sincronizzazioni per cache e debugging

---

## 🔄 FLUSSO DATI

### Flusso 1: Visualizzazione Struttura Folder

```
Frontend: GET /api/clients/{id}/drive-folder/structure
    ↓
Backend: GoogleDriveService.get_folder_structure()
    ↓
Google Drive API: files.list() con query folder
    ↓
Backend: Aggrega risultati, calcola stats
    ↓
Response: JSON con struttura completa
    ↓
Frontend: Renderizza interfaccia (Stato B)
```

### Flusso 2: Lista File in Cartella

```
Frontend: GET /api/clients/{id}/drive-folder/01_Immigration/files?limit=50
    ↓
Backend: GoogleDriveService.list_folder_files()
    ↓
Google Drive API: files.list() con parent folder filter
    ↓
Backend: Trasforma risultati, aggiunge download URLs
    ↓
Response: JSON con lista file
    ↓
Frontend: Renderizza browser documenti
```

### Flusso 3: Download File (CRITICO - Nessun Link Drive)

```
Frontend: Click download su file
    ↓
Frontend: GET /api/documents/proxy/{file_id}
    ↓
Backend: DocumentProxyService.get_file()
    ↓
Backend: Verifica permessi utente (access control)
    ↓
Google Drive API: files.get() + files.get_media()
    ↓
Backend: Stream file content (proxy)
    ↓
Backend: Headers HTTP:
    - Content-Type: application/pdf
    - Content-Disposition: attachment; filename="passport.pdf"
    ↓
Frontend: File scaricato direttamente nel browser
    ↓
✅ Utente NON vede mai Drive, tutto nel workspace
```

**Importante:**

- Download URL è SEMPRE `/api/documents/proxy/{file_id}` (non drive.google.com)
- Backend fa da proxy trasparente
- File scaricato con nome originale
- Nessun branding Google Drive visibile

### Flusso 4: Upload File (CRITICO - Nessun Link Drive)

```
Frontend: POST /api/clients/{id}/drive-folder/01_Immigration/upload
    ↓
Frontend: Multipart form-data con file
    ↓
Backend: GoogleDriveService.upload_file_to_folder()
    ↓
Backend: Verifica permessi utente (access control)
    ↓
Google Drive API: files.create() con parent folder
    ↓
Backend: File caricato su Drive (invisibile all'utente)
    ↓
Backend: Salva metadata in database (opzionale)
    ↓
Response: JSON con file info (NON include link Drive)
    {
      "file_id": "1JKL...XYZ",
      "file_name": "passport.pdf",
      "download_url": "/api/documents/proxy/1JKL...XYZ"  ← Proxy URL
    }
    ↓
Frontend: Aggiorna lista file immediatamente
    ↓
✅ Utente vede file nel workspace, NON sa che è su Drive
```

**Importante:**

- Upload avviene via backend (invisibile)
- Response NON contiene link Drive diretto
- Solo proxy URL per download futuro
- File immediatamente disponibile nel workspace

---

## 🔐 SICUREZZA & PERMESSI

### Access Control

1. **Folder Access**: Solo utente con `assigned_to` = cliente può vedere folder
2. **Admin Override**: Admin (zero@balizero.com) vede tutti i folder
3. **Download Permission**: Verifica permessi Drive prima di proxy download
4. **Upload Permission**: Verifica permessi scrittura su folder prima di upload

### Google Drive Permissions

- **Service Account**: Usa service account per operazioni backend
- **OAuth User**: Per operazioni user-specific (se necessario)
- **Sharing**: Folder condivisi con service account + team members

---

## 📊 CACHING STRATEGY

### Cache Layer 1: Backend Memory Cache

```python
# Cache struttura folder per 5 minuti
@cached(ttl=300, prefix="drive_folder_structure")
async def get_folder_structure(client_id: int):
    ...

# Cache lista file per 2 minuti
@cached(ttl=120, prefix="drive_folder_files")
async def list_folder_files(folder_id: str, ...):
    ...

# Cache stats per 5 minuti
@cached(ttl=300, prefix="drive_folder_stats")
async def get_folder_stats(client_id: int):
    ...
```

### Cache Layer 2: Database Sync Log

- Ultima sincronizzazione salvata in `drive_folder_sync_log`
- Se sync recente (< 5 minuti) → usa dati cached
- Se sync vecchia → refresh da Drive API

### Cache Layer 3: Frontend State

- React state mantiene struttura folder
- Refresh manuale o automatico ogni 5 minuti
- Optimistic updates per upload immediati

---

## 🚀 PERFORMANCE OPTIMIZATIONS

1. **Batch Operations**: Lista file in batch (50 per volta)
2. **Lazy Loading**: Carica file solo quando cartella aperta
3. **Thumbnail Caching**: Cache thumbnail immagini (24h)
4. **Pagination**: Lista file paginata (non tutto in una volta)
5. **Virtual Scrolling**: Frontend virtualizza lista lunga
6. **Debounce Search**: Search debounced (500ms)

---

## 📋 CHECKLIST IMPLEMENTAZIONE BACKEND

### Fase 1: Nuovi Endpoints

- [ ] `GET /api/clients/{id}/drive-folder/structure`
- [ ] `GET /api/clients/{id}/drive-folder/{folder_name}/files`
- [ ] `POST /api/clients/{id}/drive-folder/{folder_name}/upload`
- [ ] `GET /api/clients/{id}/drive-folder/stats`

### Fase 2: GoogleDriveService Methods

- [ ] `list_folder_files()`
- [ ] `get_folder_structure()`
- [ ] `upload_file_to_folder()`
- [ ] `get_folder_stats()`

### Fase 3: Database

- [ ] Tabella `drive_folder_sync_log`
- [ ] Migrazione database
- [ ] Indici per performance

### Fase 4: Caching & Performance

- [ ] Cache layer backend
- [ ] Thumbnail caching
- [ ] Pagination support
- [ ] Batch operations

### Fase 5: Security

- [ ] Permission checks
- [ ] Access control
- [ ] Rate limiting
- [ ] Input validation

---

**Last Updated:** 2026-01-20  
**Next Step:** Implementazione backend → Testing → Frontend integration
