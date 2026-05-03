# CRM & Google Drive Integration Plan

**Created:** 2026-01-20  
**Status:** Planning Phase  
**Context:** Migliaia di cartelle clienti organizzate su Google Drive, CRM attualmente vuoto (0 clienti)

---

## 📊 SITUAZIONE ATTUALE

### CRM System (Zantara)

- **URL:** https://kita.balizero.com/clients
- **Stato:** ✅ **10,163 clienti nel database** (verificato 2026-01-20)
  - **Distribuzione per status:**
    - `lead`: 10,136 clienti (99.7%)
    - `active`: 13 clienti
    - `inactive`: 13 clienti
    - `prospect`: 1 cliente
  - **Distribuzione per team member (top 5):**
    - `ari`: 30 clienti
    - `adit`: 25 clienti
    - `surya`: 18 clienti
    - `krisna`: 17 clienti
    - `sahira`: 11 clienti
  - **Nota:** La pagina lista potrebbe mostrare "0 clients" per:
    - **Access Control**: Team members vedono solo clienti con `assigned_to` = loro email
    - **Admin (zero@balizero.com)**: Vede TUTTI i 10,163 clienti
    - Redirect automatico: La pagina potrebbe reindirizzare automaticamente
    - Caricamento dati: I dati potrebbero essere ancora in caricamento
- **Frontend:** Next.js 16 + React 19
- **Backend:** FastAPI (Python 3.11)
- **Database:** PostgreSQL (24 tabelle CRM)
- **Access Control Logic:**
  ```python
  # Admin vede tutti i clienti
  if is_admin:
      # Nessun filtro
  else:
      # Solo clienti assigned_to = current_user_email
      query += " AND c.assigned_to = $1"
  ```

### Google Drive Organization

- **Cartella Root CRM:** `1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl`
- **Stato:** Migliaia di cartelle clienti già organizzate
- **Struttura esistente:** Cartelle clienti sparse in varie sottocartelle
- **Tool disponibili:**
  - `integrations/google-apps-script/ReorganizeCRM.gs` - Script Apps Script per riorganizzazione
  - `tools/reorganize_gdrive.py` - Script Python per scan e riorganizzazione
  - `tools/client_folder_matcher.py` - Matching cartelle → clienti CRM

---

## 🏗️ ARCHITETTURA CRM ATTUALE

### Database Schema

**Tabelle principali:**

- `clients` - Anagrafica clienti (con campo `google_drive_folder_id`)
- `client_family_members` - Familiari e dipendenti
- `documents` - Documenti (con `google_drive_file_url`)
- `practices` - Pratiche legali (KITAS, PT PMA, etc.)
- `interactions` - Timeline comunicazioni

### API Endpoints Disponibili

#### Google Drive Folder Management

- `POST /clients/{client_id}/create-drive-folder` - Crea struttura standardizzata
- `GET /clients/{client_id}/drive-folder` - Verifica folder esistente
- `DELETE /clients/{client_id}/drive-folder` - Unlink folder (non elimina)

#### Client Management

- `GET /api/crm/clients` - Lista clienti (con filtri server-side)
- `POST /api/crm/clients` - Crea nuovo cliente
- `GET /api/crm/clients/{id}` - Dettaglio cliente
- `PATCH /api/crm/clients/{id}` - Aggiorna cliente

### Struttura Folder Standardizzata

Quando si crea una cartella Drive per un cliente, viene creata questa struttura:

```
[ID]_[Nome Cliente]/
├── 00_Profile/
├── 01_Immigration/
├── 02_Company/
├── 03_Tax/
├── 04_Family/
└── 99_Misc/
```

**Configurazione backend:**

```python
# apps/backend-rag/backend/app/routers/crm_drive_folders.py
STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "02_Company",
    "03_Tax",
    "04_Family",
    "99_Misc",
]
```

---

## 🔄 STRATEGIA DI INTEGRAZIONE

### Opzione A: Matching & Link Massivo (Raccomandata)

**Workflow:**

1. **Scan Google Drive** - Identifica tutte le cartelle clienti esistenti (migliaia)
2. **Matching con CRM** - Confronta nomi cartelle con i **10,163 clienti esistenti** nel CRM
3. **Link Folder** - Collega `google_drive_folder_id` ai clienti matchati
4. **Creazione Clienti** - Solo per cartelle non matchate (se necessario)
5. **Riorganizzazione** - Opzionale: riorganizza file nelle sottocartelle standard

**Nota:** Con 10,163 clienti già nel CRM, l'obiettivo principale è **collegare le cartelle Drive esistenti** ai clienti già presenti, non creare nuovi clienti.

**Tool disponibili:**

- `tools/reorganize_gdrive.py` - Scanner ricorsivo Google Drive
- `tools/client_folder_matcher.py` - Matching fuzzy name → CRM client

**Vantaggi:**

- ✅ Import rapido di migliaia di clienti
- ✅ Mantiene struttura Drive esistente
- ✅ Collega automaticamente cartelle → CRM

**Svantaggi:**

- ⚠️ Richiede matching intelligente nomi
- ⚠️ Potrebbero esserci duplicati da gestire

### Opzione B: Sync Bidirezionale

**Workflow:**

1. **Sync Drive → CRM** - Importa nuove cartelle come clienti
2. **Sync CRM → Drive** - Crea cartelle per nuovi clienti CRM
3. **Monitoraggio continuo** - Job schedulato per mantenere sync

**Vantaggi:**

- ✅ Mantiene sincronizzazione continua
- ✅ Supporta workflow bidirezionale

**Svantaggi:**

- ⚠️ Più complesso da implementare
- ⚠️ Richiede gestione conflitti

---

## 🛠️ TOOL DISPONIBILI

### 1. Google Apps Script (`ReorganizeCRM.gs`)

**Scopo:** Riorganizzazione cartelle clienti esistenti

**Funzionalità:**

- Scan ricorsivo cartella CRM
- Identificazione cartelle clienti (esclude team folders, utility, etc.)
- Categorizzazione automatica file:
  - `01_Passport` - File con keywords: passport, paspor, pp
  - `02_Company` - File con keywords: pt, pma, cv, npwp, nib, akta
  - `03_Other_Documents` - Default

**Configurazione:**

```javascript
const CONFIG = {
  CRM_FOLDER_ID: '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl',
  TEAM_FOLDERS: ['MAS ADIT', 'OM YOYOK', ...],
  UTILITY_FOLDERS: ['Bali Zero', 'Draft', 'Backup', ...],
  CATEGORY_FOLDERS: ['COMPANY', 'INDIVIDUAL', ...],
  VISA_TYPES: ['ALTUS', 'ITAS', 'KITAP', 'KITAS', ...],
  STATUS_FOLDERS: ['Done', 'On Proses', 'Pending', ...],
}
```

**Uso:**

1. Apri Google Drive → Extensions → Apps Script
2. Incolla script
3. Run `dryRun()` per preview
4. Run `execute()` per eseguire

### 2. Python Reorganization Engine (`reorganize_gdrive.py`)

**Scopo:** Scanner Python per identificare clienti su Google Drive

**Funzionalità:**

- Scan ricorsivo con Google Drive API
- Identificazione cartelle clienti
- Generazione report JSON con:
  - Nome cartella
  - Path completo
  - File count
  - Folder ID

**Output:**

```json
{
  "clients": [
    {
      "name": "Marco Rossi",
      "id": "1ABC...XYZ",
      "path": "CRM/KITAS/Marco Rossi",
      "files": [...]
    }
  ],
  "stats": {
    "clients_found": 1234,
    "errors": []
  }
}
```

### 3. Client Folder Matcher (`client_folder_matcher.py`)

**Scopo:** Matching fuzzy tra cartelle Drive e clienti CRM

**Algoritmo:**

- Confronta nome cartella con `clients.full_name`
- Usa similarity score (fuzzy matching)
- Confidence levels: high (>0.8), medium (0.6-0.8), low (<0.6)

**Output:**

```json
{
  "matches": [
    {
      "drive_folder": "Marco Rossi",
      "drive_path": "CRM/KITAS/Marco Rossi",
      "crm_id": 123,
      "crm_name": "Marco Rossi",
      "similarity": 0.95,
      "confidence": "high"
    }
  ]
}
```

---

## 📋 PIANO DI IMPLEMENTAZIONE

### Fase 1: Preparazione (1-2 giorni)

**Task:**

1. ✅ Verificare accesso Google Drive API
2. ✅ Testare scanner su subset cartelle (100-200 clienti)
3. ✅ Validare matching algorithm con dati reali
4. ✅ Documentare edge cases (nomi duplicati, cartelle vuote, etc.)

**Deliverable:**

- Report scan iniziale con statistiche
- Lista edge cases identificati
- Test matching su campione

### Fase 2: Matching & Link Massivo (3-5 giorni)

**Task:**

1. **Scan completo Google Drive**

   ```bash
   python tools/reorganize_gdrive.py --scan-only --output scan_results.json
   ```

   - Identifica tutte le cartelle clienti su Drive
   - Stima: migliaia di cartelle

2. **Matching con CRM esistente (10,163 clienti)**

   ```bash
   python tools/client_folder_matcher.py \
     --drive-scan scan_results.json \
     --crm-api https://nuzantara-rag.fly.dev \
     --output matches.json
   ```

   - Matching fuzzy: nome cartella → `clients.full_name`
   - Confidence levels: high (>0.8), medium (0.6-0.8), low (<0.6)

3. **Link Folder → CRM**
   - Per ogni match high confidence → UPDATE `clients.google_drive_folder_id`
   - Per match medium/low → Flag per review manuale
   - Batch processing: 100-200 clienti per batch

4. **Gestione cartelle non matchate**
   - Analisi cartelle senza match
   - Decisione: creare nuovi clienti o ignorare?
   - Review manuale per edge cases

**Deliverable:**

- Script matching & link batch
- Log completo operazioni
- Report: matched vs unmatched vs errors
- Dashboard review per match medium/low confidence

### Fase 3: Riorganizzazione Opzionale (2-3 giorni)

**Task:**

1. **Analisi struttura esistente**
   - Identifica cartelle già organizzate (con sottocartelle standard)
   - Identifica cartelle da riorganizzare

2. **Riorganizzazione selettiva**
   - Solo per cartelle che non hanno struttura standard
   - Usa Google Apps Script o Python script
   - Categorizzazione automatica file

**Deliverable:**

- Report cartelle riorganizzate
- Backup struttura originale

### Fase 4: Sync Continuo (Opzionale, futuro)

**Task:**

1. **Job schedulato** - Scan periodico nuove cartelle Drive
2. **Webhook Drive** - Notifiche real-time nuove cartelle
3. **Dashboard sync** - Monitoraggio stato sincronizzazione

---

## 🔍 DETTAGLI TECNICI

### Identificazione Cartelle Clienti

**Regole di esclusione:**

- ❌ Cartelle team (`MAS ADIT`, `OM YOYOK`, etc.)
- ❌ Cartelle utility (`Bali Zero`, `Draft`, `Backup`, etc.)
- ❌ Cartelle categoria (`COMPANY`, `INDIVIDUAL`, etc.)
- ❌ Cartelle tipo visa (`KITAS`, `KITAP`, etc.) - ma i loro subfolder sono clienti
- ❌ Cartelle status (`Done`, `Pending`, etc.) - ma i loro subfolder sono clienti

**Regole di inclusione:**

- ✅ Cartelle dentro `STATUS_FOLDERS` → probabile cliente
- ✅ Cartelle dentro `VISA_TYPES` → probabile cliente
- ✅ Cartelle con file (non solo subfolder)

### Estrazione Metadata da Nome Cartella

**Pattern comuni:**

- `[Nome] [Cognome]` → `full_name`
- `[Nome]_[Cognome]` → `full_name`
- `[ID]_[Nome]` → già ha ID, match diretto

**Esempi:**

- `Marco Rossi` → `full_name: "Marco Rossi"`
- `123_Marco_Rossi` → `id: 123, full_name: "Marco Rossi"`
- `Marco Rossi - KITAS` → `full_name: "Marco Rossi", tags: ["KITAS"]`

### Link Folder → CRM

**Campo database:**

```sql
ALTER TABLE clients ADD COLUMN google_drive_folder_id VARCHAR(255);
CREATE INDEX idx_clients_drive_folder ON clients(google_drive_folder_id);
```

**API Update:**

```python
# Dopo import, aggiorna cliente
UPDATE clients
SET google_drive_folder_id = $1, updated_at = NOW()
WHERE id = $2
```

---

## 📊 METRICHE DI SUCCESSO

### Matching & Link Massivo

- ✅ **Coverage:** >80% cartelle Drive collegate ai clienti CRM esistenti
- ✅ **Accuracy:** >90% matching corretto (fuzzy matching nome cartella → nome cliente)
- ✅ **Performance:** <2 ore per 10,000+ match (batch processing)
- ✅ **Error Rate:** <2% errori durante matching/link
- ✅ **Unmatched Folders:** <5% cartelle senza match (richiedono review manuale)

### Riorganizzazione

- ✅ **Structure Compliance:** >80% cartelle con struttura standard
- ✅ **File Categorization:** >70% file categorizzati correttamente
- ✅ **Zero Data Loss:** Nessun file perso durante riorganizzazione

---

## 🚨 RISCHI E MITIGAZIONI

### Rischio 1: Duplicati

**Scenario:** Stesso cliente con cartelle multiple su Drive

**Mitigazione:**

- Matching fuzzy prima di creare cliente
- Merge automatico se confidence >0.9
- Review manuale per confidence 0.7-0.9

### Rischio 2: Nomi Ambigui

**Scenario:** Cartella con nome generico che non è un cliente

**Mitigazione:**

- Whitelist/blacklist manuale
- Verifica presenza file (cartelle vuote = skip)
- Review manuale per edge cases

### Rischio 3: Performance Google Drive API

**Scenario:** Rate limiting durante scan massivo

**Mitigazione:**

- Batch processing con delay
- Exponential backoff su errori
- Resume capability (salva progress)

### Rischio 4: Data Loss durante Riorganizzazione

**Scenario:** File persi durante move/categorization

**Mitigazione:**

- Backup completo prima di riorganizzare
- Dry-run sempre prima di execute
- Log dettagliato ogni operazione

---

## 📚 DOCUMENTAZIONE CORRELATA

- **CRM Complete:** `docs/CRM_COMPLETE.md` (consolidated documentation)
- **Google Drive API:** `apps/backend-rag/backend/app/routers/crm_drive_folders.py`
- **Reorganization Script:** `integrations/google-apps-script/ReorganizeCRM.gs`
- **Python Scanner:** `tools/reorganize_gdrive.py`

---

## 🎯 PROSSIMI STEP

1. **Approvazione piano** - Review con team
2. **Setup ambiente** - Credenziali Google Drive API, test accesso
3. **Pilot test** - Scan e import su 50-100 clienti
4. **Validazione risultati** - Review matching e import
5. **Import completo** - Batch processing migliaia di clienti
6. **Riorganizzazione** - Opzionale, solo se necessario

---

**Last Updated:** 2026-01-20  
**Next Review:** After pilot test completion
