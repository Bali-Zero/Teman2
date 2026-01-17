# 🔄 Nuzantara Dropbox → Google Drive Migration System

**Obiettivo**: Migrare 450GB di documenti clienti da Dropbox a Google Drive (30TB) con sync continuo e integrazione CRM.

---

## 📋 Workflow Completo

```
┌─────────────┐
│  DROPBOX    │ ← Upload manuale documenti
│   (450GB)   │
└──────┬──────┘
       │
       │ [1] Migrazione iniziale (batch)
       │ [2] Sync continuo (watch)
       ↓
┌──────────────┐
│ Python Script│
│ • Filtra file│
│ • Categorizza│
│ • Rinomina   │
└──────┬───────┘
       ↓
┌─────────────────┐
│ GOOGLE DRIVE    │
│  (30TB)         │
│                 │
│ Bali Zero       │
│ Clients/        │
│  ├─ ADITYA/     │
│  │  ├─ 01_Imm..│
│  │  ├─ 02_Comp.│
│  │  └─ 03_Tax/ │
│  ├─ DAVID/      │
│  └─ ...         │
└─────────┬───────┘
          │
          │ Auto-update
          ↓
    ┌─────────────┐
    │ CRM DATABASE│
    │ (PostgreSQL)│
    │             │
    │ documents   │
    │ table       │
    └─────────────┘
```

---

## 🚀 Setup Iniziale

### 1. Installa Dipendenze

```bash
cd /path/to/nuzantara
pip install dropbox google-api-python-client google-auth-httplib2 google-auth-oauthlib asyncpg --break-system-packages
```

### 2. Configurazione Dropbox API

**Passo 1**: Vai su https://www.dropbox.com/developers/apps

**Passo 2**: Crea nuova app
- Choose API: **Scoped access**
- Access type: **Full Dropbox**
- Name: `nuzantara-migration`

**Passo 3**: Genera Access Token
- Tab "Settings" → "Generated access token"
- Copia il token

**Passo 4**: Setta la variabile d'ambiente
```bash
export DROPBOX_API_TOKEN='sl.xxxxxxxxxxxxxxxxxxxxxxx'
```

### 3. Configurazione Google Drive API

**Passo 1**: Vai su https://console.cloud.google.com/

**Passo 2**: Crea progetto (se non esiste)
- Nome: `nuzantara-crm`

**Passo 3**: Abilita Google Drive API
- API & Services → Enable APIs
- Cerca "Google Drive API" → Enable

**Passo 4**: Crea Service Account
- IAM & Admin → Service Accounts → Create
- Download JSON credentials

**Passo 5**: Setta la variabile d'ambiente
```bash
export GOOGLE_DRIVE_CREDENTIALS_PATH='/path/to/credentials.json'
```

### 4. Database Configuration

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/nuzantara'
```

---

## 📂 Struttura File su Google Drive

```
Bali Zero Clients/
├── ADITYA/
│   ├── 01_Immigration/
│   │   ├── Passport_ADITYA_2028-12-31.pdf
│   │   ├── KITAS_Investor_2026-06-15.pdf
│   │   └── IMTA_2026-12-31.pdf
│   ├── 02_Company/
│   │   ├── PT_PMA_Deed_2024-01-15.pdf
│   │   ├── NIB_Certificate.pdf
│   │   └── NPWP_Company.pdf
│   ├── 03_Tax/
│   │   ├── Tax_Report_2025_December.pdf
│   │   └── SPT_2024.pdf
│   ├── 04_Family/
│   │   └── (vuoto se nessun familiare)
│   ├── 05_Contracts/
│   │   └── Service_Agreement_2024-01-01.pdf
│   └── 99_Uncategorized/
│       └── (file non categorizzabili)
├── DAVID/
│   ├── 01_Immigration/
│   └── ...
└── ...
```

---

## 🎯 Fase 1: Migrazione Iniziale

### Esegui Migrazione Batch

```bash
# Dry run (solo preview, no upload)
python dropbox_to_gdrive_migration.py --dry-run

# Migrazione reale
python dropbox_to_gdrive_migration.py

# Con batch size custom (default: 5 clienti per batch)
python dropbox_to_gdrive_migration.py --batch-size 10
```

### Cosa Fa lo Script

1. **Scansiona Dropbox**: Lista tutti i client folders
2. **Filtra File**: Esclude .DS_Store, .tmp, duplicati
3. **Categorizza**: Immigration, Company, Tax automaticamente
4. **Crea Struttura**: Cartelle organizzate in Google Drive
5. **Upload**: Migra file con progress bar
6. **Aggiorna CRM**: Inserisce record in `documents` table

### File Esclusi Automaticamente

- `.DS_Store`, `Thumbs.db`, `desktop.ini`
- `*.tmp`, `*.bak`, `~$*`
- Cartelle: `Screenshots`, `Mobile Uploads`, `Other computers`
- File vuoti (0 bytes)
- Duplicati esatti (stesso MD5 hash)

### Naming Convention Automatica

**Prima**:
```
passport marco.pdf
KITAS scan.jpg
tax 2024.xlsx
```

**Dopo**:
```
Passport_MARCO_ROSSI_2028-12-31.pdf
KITAS_Investor_2026-06-15.pdf
Tax_Report_2024_December.xlsx
```

---

## 🔄 Fase 2: Sync Continuo

### Avvia Watcher

```bash
# In background
nohup python continuous_sync_watcher.py &

# In foreground (per testing)
python continuous_sync_watcher.py
```

### Cosa Fa il Watcher

1. **Monitora Dropbox** ogni 60 secondi
2. **Rileva nuovi file** o modifiche
3. **Auto-categorizza** basandosi sul nome
4. **Upload immediato** a Google Drive
5. **Aggiorna CRM** in tempo reale

### Log File

```bash
# Visualizza log in real-time
tail -f continuous_sync.log

# Cerca errori
grep ERROR continuous_sync.log
```

---

## 🔗 Integrazione CRM

### Tabella Database: `documents`

Quando un file viene migrato, viene inserito automaticamente:

```sql
INSERT INTO documents (
    client_id,              -- Auto-matched da nome cartella
    document_type,          -- "Passport", "KITAS", "Tax Report"
    document_category,      -- "immigration", "company", "tax"
    document_name,          -- Nome file standardizzato
    google_drive_file_url,  -- Link diretto Google Drive
    file_id,                -- Google Drive file ID
    expiry_date,            -- Estratto dal nome file
    uploaded_at,            -- NOW()
    uploaded_by             -- 'migration_script'
) VALUES (...);
```

### Auto-Matching Cliente

Lo script cerca il cliente nel CRM usando:

1. **Nome esatto** della cartella Dropbox
2. **Fuzzy matching** se nome non esatto
3. **Creazione automatica** se cliente non esiste (opzionale)

```python
# Esempio fuzzy match
"ADITYA" → SELECT * FROM clients WHERE full_name ILIKE '%aditya%'
"Data OM DIAN" → "Om Dian" in database
```

---

## 📊 Monitoring & Stats

### Dashboard Stats

```python
# Genera report migrazione
python dropbox_to_gdrive_migration.py --report

# Output:
# ✓ Clients migrated: 45/50
# ✓ Files uploaded: 1,234
# ✓ Total size: 387 GB
# ✓ Duplicates skipped: 89
# ✗ Errors: 3 (see migration_YYYYMMDD.log)
```

### Query CRM per Documenti Migrati

```sql
-- Clienti con documenti migrati
SELECT 
    c.full_name,
    COUNT(d.id) as doc_count,
    MAX(d.uploaded_at) as last_upload
FROM clients c
LEFT JOIN documents d ON d.client_id = c.id
WHERE d.uploaded_by = 'migration_script'
GROUP BY c.id
ORDER BY doc_count DESC;

-- Documenti per categoria
SELECT 
    document_category,
    COUNT(*) as count
FROM documents
WHERE uploaded_by = 'migration_script'
GROUP BY document_category;
```

---

## 🛠️ Troubleshooting

### Problema: "Dropbox API token invalid"

```bash
# Rigenera token su https://www.dropbox.com/developers/apps
# Poi:
export DROPBOX_API_TOKEN='new_token'
```

### Problema: "Google Drive quota exceeded"

- Hai 30TB, non dovrebbe succedere
- Controlla: https://drive.google.com/settings/storage
- Se necessario, puoi comprare più spazio

### Problema: "Client not found in CRM"

**Opzione 1**: Crea manualmente il cliente nel CRM prima

**Opzione 2**: Abilita auto-create:
```python
# In dropbox_to_gdrive_migration.py
AUTO_CREATE_CLIENTS = True
```

### Problema: "Duplicate files uploaded"

Lo script controlla MD5 hash - se hai duplicati, controlla:
```bash
# Trova duplicati in Dropbox
python dropbox_to_gdrive_migration.py --find-duplicates
```

---

## 🔐 Security & Backup

### API Tokens Security

**NON** committare mai i token in Git!

```bash
# .env file (git-ignored)
DROPBOX_API_TOKEN=xxx
GOOGLE_DRIVE_CREDENTIALS_PATH=/secure/path/creds.json
DATABASE_URL=postgresql://...
```

### Backup Strategy

1. **Dropbox**: Mantieni i file originali per 30 giorni dopo migrazione
2. **Google Drive**: Abilita versioning (automatico)
3. **Database**: Daily backup via cron

```bash
# Backup database documenti
pg_dump -t documents nuzantara > documents_backup_$(date +%Y%m%d).sql
```

---

## 📈 Performance

### Tempo Stimato Migrazione

- **450 GB** @ 50 MB/s upload → ~2.5 ore
- Con categorizzazione e CRM update → ~4-5 ore
- Batch processing: pause ogni 5 clienti

### Ottimizzazioni

- Parallel uploads (max 5 concurrent)
- Skip files < 10KB (probabilmente thumbnails)
- Compress before upload (opzionale)

---

## ✅ Checklist Post-Migrazione

- [ ] Verifica tutti i clienti hanno cartelle in Google Drive
- [ ] Check documenti nel CRM database (query sopra)
- [ ] Test OCR su alcuni passaporti
- [ ] Abilita continuous watcher
- [ ] Setup cron job per watcher auto-restart
- [ ] Notifica team della nuova struttura
- [ ] Update CRM frontend per mostrare nuovi links

---

## 🚨 Support

**Issues**: Controlla `migration_YYYYMMDD.log`

**Questions**: zero@balizero.com

**Updates**: Questo README verrà aggiornato durante la migrazione
