# CRM Google Drive Folder - UI Design Complete

**Created:** 2026-01-20  
**Status:** Design Phase  
**Purpose:** Design completo delle interfacce per gestione cartelle Google Drive nel CRM

---

## 🎯 OBIETTIVI

1. **Visualizzare** la struttura folder standardizzata per ogni cliente
2. **Creare** nuove strutture folder quando necessario
3. **Collegare** cartelle Drive esistenti ai clienti CRM
4. **Navigare** facilmente tra le sottocartelle **dentro il workspace** (non Drive)
5. **Visualizzare** documenti direttamente nel workspace (preview, download)
6. **Upload** file direttamente nelle cartelle corrette (via workspace)
7. **Sincronizzare** stato tra CRM e Google Drive (background)

**PRINCIPIO FONDAMENTALE:**

```
┌─────────────────────────────────────────────────────────┐
│  ❌ MAI ACCESSO DIRETTO A GOOGLE DRIVE                │
│                                                         │
│  ✅ Documenti caricati DA Drive (backend)              │
│  ✅ Documenti scaricati DAL workspace (frontend)      │
│  ✅ In futuro: anche DAL portale cliente              │
│                                                         │
│  Google Drive = Storage Backend Invisibile             │
└─────────────────────────────────────────────────────────┘
```

**Flusso Documenti:**

1. **Upload**: Workspace → Backend API → Google Drive (invisibile)
2. **Visualizzazione**: Google Drive → Backend Proxy → Workspace (preview)
3. **Download**: Google Drive → Backend Proxy → Browser (file scaricato)
4. **Futuro Portale**: Google Drive → Backend Proxy → Portale Cliente

**L'utente NON vede mai:**

- ❌ Link esterni a drive.google.com
- ❌ Redirect a Google Drive
- ❌ Apertura Drive in nuova tab
- ❌ Autenticazione Google Drive nel browser

**L'utente vede SOLO:**

- ✅ Interfaccia workspace CRM
- ✅ Preview documenti nel workspace
- ✅ Download file dal workspace
- ✅ Upload file nel workspace

---

## 📐 STRUTTURA FOLDER STANDARDIZZATA

```
[ID]_[Nome Cliente]/
├── 00_Profile/          👤 Profilo cliente, foto, dati personali
├── 01_Immigration/     🛂 Visti, passaporti, KITAS, documenti immigrazione
├── 02_Company/         🏢 Documenti aziendali, PT PMA, NIB, NPWP
├── 03_Tax/             💰 Documenti fiscali, dichiarazioni, ricevute
├── 04_Family/          👨‍👩‍👧‍👦 Documenti familiari, dipendenti
└── 99_Misc/            📁 Altri documenti, vari
```

---

## 🎨 INTERFACCE - DESIGN COMPLETO

### INTERFACCIA 1: Visualizzazione Struttura Folder (Overview Tab)

**Posizione:** Pagina Cliente → Tab Overview → Sezione "Google Drive Folder"

**Stati possibili:**

#### Stato A: Nessuna Cartella Collegata

```
┌─────────────────────────────────────────────────────────┐
│  Google Drive Folder                                    │
│  Create a standardized folder structure for this client │
│                                                         │
│  Standard Structure:                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 👤 Profile    🛂 Immigration  🏢 Company        │   │
│  │ 💰 Tax        👨‍👩‍👧‍👦 Family     📁 Misc          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [➕ Create Folder Structure]  [🔗 Link Existing]     │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Mostra preview struttura standardizzata
- Due azioni principali: Create / Link
- Tooltip su ogni icona folder spiega il contenuto

#### Stato B: Cartella Collegata (Struttura Completa)

```
┌─────────────────────────────────────────────────────────┐
│  ✅ Google Drive Folder                                  │
│  📊 47 files • 125 MB • Last sync: 2h ago              │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 👤 Profile         12 files  [👁️ View]        │   │
│  │ 🛂 Immigration     23 files  [👁️ View]        │   │
│  │ 🏢 Company         12 files  [👁️ View]        │   │
│  │ 💰 Tax              8 files  [👁️ View]        │   │
│  │ 👨‍👩‍👧‍👦 Family         2 files  [👁️ View]        │   │
│  │ 📁 Misc            0 files   [👁️ View]        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [🔄 Refresh]  [📤 Upload Files]  [📋 View All]      │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Mostra tutte le 6 sottocartelle standard
- Contatore file per ogni cartella
- Icona [👁️ View] apre **browser documenti dentro workspace** (non Drive)
- Badge verde ✅ indica folder collegato
- Statistiche aggregate in header
- Azioni: Refresh (verifica stato), Upload (apre modal), View All (tutti i file)

#### Stato C: Cartella Collegata (Struttura Parziale)

```
┌─────────────────────────────────────────────────────────┐
│  ⚠️ Google Drive Folder                                 │
│  📊 35 files • 98 MB • Last sync: 2h ago               │
│                                                         │
│  ⚠️ Some subfolders missing. Click to reorganize.      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ✅ 👤 Profile         12 files  [👁️ View]     │   │
│  │ ✅ 🛂 Immigration     23 files  [👁️ View]     │   │
│  │ ❌ 🏢 Company         0 files   [➕ Create]   │   │
│  │ ✅ 💰 Tax             8 files   [👁️ View]     │   │
│  │ ❌ 👨‍👩‍👧‍👦 Family         0 files   [➕ Create]   │   │
│  │ ✅ 📁 Misc            0 files   [👁️ View]     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [🔄 Refresh]  [🔧 Reorganize Structure]               │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Mostra quali cartelle esistono (✅) e quali mancano (❌)
- Pulsante [➕ Create] per creare cartelle mancanti
- Icona [👁️ View] apre browser documenti dentro workspace (solo per cartelle esistenti)
- Azione [🔧 Reorganize] per standardizzare struttura esistente

---

### INTERFACCIA 2: Modal Link Cartella Esistente

**Trigger:** Click su "Link Existing Folder" (Stato A)

```
┌─────────────────────────────────────────────────────────┐
│  Link Existing Folder                            [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Enter the Google Drive folder ID or URL to link       │
│  to this client.                                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ https://drive.google.com/drive/folders/...     │   │
│  │                                                 │   │
│  │ or                                               │   │
│  │                                                 │   │
│  │ 1ABC...XYZ                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  💡 Tip: Copy the folder ID from the Drive URL         │
│                                                         │
│  [Cancel]                    [🔗 Link Folder]          │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Accetta sia URL completo che solo folder ID
- Validazione: verifica che il folder esista prima di linkare
- Loading state durante verifica
- Success: chiude modal e aggiorna interfaccia principale

---

### INTERFACCIA 3: Modal Creazione Folder (Conferma)

**Trigger:** Click su "Create Folder Structure" (Stato A)

```
┌─────────────────────────────────────────────────────────┐
│  Create Folder Structure                         [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  This will create a standardized folder structure       │
│  for:                                                   │
│                                                         │
│  👤 Marco Rossi                                        │
│                                                         │
│  Structure:                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📁 10218_Marco_Rossi/                          │   │
│  │   ├── 👤 00_Profile/                           │   │
│  │   ├── 🛂 01_Immigration/                        │   │
│  │   ├── 🏢 02_Company/                            │   │
│  │   ├── 💰 03_Tax/                                 │   │
│  │   ├── 👨‍👩‍👧‍👦 04_Family/                         │   │
│  │   └── 📁 99_Misc/                                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Location: Google Drive → Clients → Individuals        │
│                                                         │
│  [Cancel]              [✅ Create Structure]            │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Mostra preview struttura completa prima di creare
- Indica dove verrà creata (Individuals/Companies)
- Loading durante creazione
- Success: mostra struttura creata con link

---

### INTERFACCIA 4: Card Folder nella Lista Clienti

**Posizione:** Pagina `/clients` → Card Cliente

**Stato A: Nessuna Cartella**

```
┌─────────────────────────────────┐
│  👤 Marco Rossi                 │
│  🇮🇹 Italian                     │
│  📧 marco@example.com           │
│                                 │
│  [📁 No Drive Folder]           │
│                                 │
│  [View Details →]               │
└─────────────────────────────────┘
```

**Stato B: Cartella Collegata**

```
┌─────────────────────────────────┐
│  👤 Marco Rossi                 │
│  🇮🇹 Italian                     │
│  📧 marco@example.com           │
│                                 │
│  ✅ Drive Folder Linked          │
│  [📂 Open Folder ↗]             │
│                                 │
│  [View Details →]               │
└─────────────────────────────────┘
```

**Comportamento:**

- Badge visibile nella card cliente con statistiche
- Click su badge → naviga a pagina cliente → tab Documents
- Hover mostra tooltip con dettagli folder
- **NON** apre Drive esternamente

---

### INTERFACCIA 5: Integrazione Upload Documenti

**Posizione:** Pagina Cliente → Tab Documents → Modal Add Document

**Stato Attuale (da migliorare):**

```
┌─────────────────────────────────────────────────────────┐
│  Add Document                                    [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Document Type: [Passport ▼]                           │
│  Category:      [Immigration ▼]                        │
│  Expiry Date:  [2028-12-31]                           │
│                                                         │
│  Google Drive Link:                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │ https://drive.google.com/...                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Cancel]                          [✅ Add Document]    │
└─────────────────────────────────────────────────────────┘
```

**Stato Migliorato (con Folder Integration):**

```
┌─────────────────────────────────────────────────────────┐
│  Add Document                                    [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Document Type: [Passport ▼]                           │
│  Category:      [Immigration ▼]                        │
│  Expiry Date:  [2028-12-31]                           │
│                                                         │
│  📁 Upload to Folder:                                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🛂 01_Immigration ▼                            │   │
│  │                                                 │   │
│  │ 💡 Auto-selected based on category            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  OR                                                     │
│                                                         │
│  📎 Google Drive Link:                                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │ https://drive.google.com/...                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [Cancel]                          [✅ Add Document]    │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Dropdown mostra tutte le sottocartelle disponibili
- Auto-selezione basata su `document_category`:
  - `immigration` → `01_Immigration`
  - `pma` → `02_Company`
  - `tax` → `03_Tax`
  - `personal` → `04_Family`
  - `other` → `99_Misc`
- Se cliente non ha folder → mostra warning e suggerisce creazione

---

### INTERFACCIA 6: Browser Documenti dentro Workspace

**Posizione:** Quando si clicca "View" su una cartella → Nuova sezione nella pagina cliente

```
┌─────────────────────────────────────────────────────────┐
│  📁 01_Immigration                                       │
│  ← Back to Overview                                      │
│                                                         │
│  📊 23 files • 45 MB                                     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🔍 Search files...                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📄 passport_marco.pdf         2.3 MB  [⬇️]     │   │
│  │ 📄 kitas_application.pdf      1.8 MB  [⬇️]     │   │
│  │ 📄 visa_stamp.jpg             450 KB  [👁️]     │   │
│  │ 📄 medical_certificate.pdf    1.2 MB  [⬇️]     │   │
│  │ ... (19 more files)                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [⬇️ Download All]  [📤 Upload More]                   │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- **Tutto dentro workspace** - nessun link esterno
- Preview immagini direttamente nel browser
- Download file singoli o multipli
- Search/filter documenti
- Upload nuovi file direttamente nella cartella
- Breadcrumb per navigazione tra cartelle

---

### INTERFACCIA 7: Quick Actions Toolbar

**Posizione:** Pagina Cliente → Header (accanto a WhatsApp/Telegram buttons)

**Stato A: Nessuna Cartella**

```
[WhatsApp] [Telegram] [📁 Create Drive Folder]
```

**Stato B: Cartella Collegata**

```
[WhatsApp] [Telegram] [📂 View Documents] [📤 Upload]
```

**Comportamento:**

- Badge "Create Drive Folder" quando non esiste
- Badge "View Documents" quando esiste → scroll a sezione documenti o apre tab Documents
- Pulsante "Upload" apre modal upload diretto
- **NON** ci sono link esterni a Drive

---

### INTERFACCIA 8: Folder Status Indicator

**Posizione:** Pagina Cliente → Header (sotto nome cliente)

```
┌─────────────────────────────────────────────────────────┐
│  👤 Marco Rossi                                         │
│  Client #10218 • individual                             │
│                                                         │
│  📁 Drive Folder: ✅ Linked                             │
│  └─ Last synced: 2 hours ago                            │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Badge verde ✅ quando collegato
- Badge grigio ⚠️ quando non collegato
- Timestamp ultima sincronizzazione (se implementato)
- Click su badge → scroll a sezione Drive Folder

---

### INTERFACCIA 9: Modal Upload File Diretto

**Trigger:** Click su "Upload Files" o "📤 Upload" button

```
┌─────────────────────────────────────────────────────────┐
│  Upload to Drive Folder                          [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📁 Destination Folder:                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🛂 01_Immigration ▼                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  📎 Select Files:                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │  [📎 Choose Files] or drag & drop              │   │
│  │                                                 │   │
│  │  Selected: passport.pdf (2.3 MB)               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  💡 Files will be uploaded to Google Drive backend     │
│     and visible in workspace immediately                │
│                                                         │
│  [Cancel]                    [📤 Upload Files]          │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Drag & drop support
- Multi-file selection
- Preview file selezionati
- Progress bar durante upload
- Upload avviene via API backend → Google Drive (invisibile)
- Success: file immediatamente visibili nel workspace
- **NON** apre Drive esternamente

---

### INTERFACCIA 10: Folder Statistics Widget

**Posizione:** Pagina Cliente → Tab Overview → Accanto a Drive Folder Structure

```
┌─────────────────────────────────────────────────────────┐
│  📊 Folder Statistics                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Total Files:        47                                 │
│  Total Size:         125 MB                              │
│  Last Updated:       2 hours ago                        │
│                                                         │
│  By Category:                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🛂 Immigration    23 files  (49%)             │   │
│  │ 🏢 Company        12 files  (26%)             │   │
│  │ 💰 Tax             8 files  (17%)             │   │
│  │ 👤 Profile         2 files   (4%)              │   │
│  │ 👨‍👩‍👧‍👦 Family        2 files   (4%)              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [View All Files →]                                    │
└─────────────────────────────────────────────────────────┘
```

**Comportamento:**

- Statistiche aggregate per folder
- Breakdown per categoria
- Click "View All Files" → apre browser documenti dentro workspace (non Drive)
- Refresh automatico ogni 5 minuti
- **NON** apre Drive esternamente

---

## 🔄 FLUSSI UTENTE

### Flusso 1: Creazione Nuova Struttura Folder

```
1. Utente apre pagina cliente
   ↓
2. Vede "No Drive Folder" (Stato A)
   ↓
3. Click "Create Folder Structure"
   ↓
4. Modal conferma mostra preview struttura
   ↓
5. Click "Create Structure"
   ↓
6. Loading spinner durante creazione
   ↓
7. Success: Interfaccia aggiornata a Stato B
   ↓
8. Mostra tutte le 6 sottocartelle create
```

### Flusso 2: Link Cartella Esistente

```
1. Utente apre pagina cliente
   ↓
2. Vede "No Drive Folder" (Stato A)
   ↓
3. Click "Link Existing Folder"
   ↓
4. Modal apre con input field
   ↓
5. Utente incolla URL o folder ID
   ↓
6. Click "Link Folder"
   ↓
7. Sistema verifica che folder esista
   ↓
8. Success: Folder collegato, interfaccia aggiornata
   ↓
9. Mostra struttura (Stato B o C)
```

### Flusso 3: Upload Documento con Folder Integration

```
1. Utente in Tab Documents
   ↓
2. Click "Add Document"
   ↓
3. Seleziona tipo documento (es. Passport)
   ↓
4. Seleziona categoria (es. Immigration)
   ↓
5. Folder auto-selezionato: 01_Immigration
   ↓
6. Utente può cambiare folder se necessario
   ↓
7. Inserisce Google Drive link o upload file
   ↓
8. Click "Add Document"
   ↓
9. Documento salvato con riferimento folder
```

### Flusso 4: Navigazione e Visualizzazione Documenti

```
1. Utente vede struttura folder (Stato B)
   ↓
2. Click [👁️ View] su "01_Immigration"
   ↓
3. Si apre browser documenti dentro workspace
   ↓
4. Mostra lista file della cartella (23 files)
   ↓
5. Utente può:
   - Cercare file (search)
   - Preview immagini direttamente
   - Download file singoli o multipli
   - Upload nuovi file
   ↓
6. Click "← Back to Overview" → torna struttura folder
```

### Flusso 5: Download Documento

```
1. Utente in browser documenti
   ↓
2. Click icona [⬇️] su file
   ↓
3. Backend scarica da Google Drive (proxy)
   ↓
4. File scaricato direttamente nel browser
   ↓
5. Utente NON vede mai Drive, tutto nel workspace
```

---

## 🎨 DESIGN SYSTEM

### Colori Folder

| Folder         | Icona | Colore Badge | Colore Background  |
| -------------- | ----- | ------------ | ------------------ |
| 00_Profile     | 👤    | `blue-500`   | `bg-blue-500/20`   |
| 01_Immigration | 🛂    | `green-500`  | `bg-green-500/20`  |
| 02_Company     | 🏢    | `purple-500` | `bg-purple-500/20` |
| 03_Tax         | 💰    | `yellow-500` | `bg-yellow-500/20` |
| 04_Family      | 👨‍👩‍👧‍👦    | `pink-500`   | `bg-pink-500/20`   |
| 99_Misc        | 📁    | `gray-500`   | `bg-gray-500/20`   |

### Stati Visivi

- ✅ **Linked**: Badge verde, folder collegato e verificato
- ⚠️ **Partial**: Badge giallo, struttura incompleta
- ❌ **Missing**: Badge rosso, folder non trovato o non collegato
- 🔄 **Loading**: Spinner durante operazioni
- ✅ **Success**: Toast notification verde
- ❌ **Error**: Toast notification rosso

### Icone Lucide React

- `FolderOpen` - Folder principale
- `Folder` - Sottocartella
- `File` - File generico
- `Eye` - Visualizza documenti dentro workspace
- `Download` - Scarica file (via proxy backend)
- `Plus` - Crea nuovo
- `Link` - Link esistente
- `Upload` - Upload file
- `RefreshCw` - Refresh stato
- `CheckCircle2` - Successo
- `AlertCircle` - Warning
- `X` - Chiudi/Cancella

---

## 📱 RESPONSIVE DESIGN

### Mobile (< 768px)

- Folder structure: Stack verticale invece di grid
- Modal: Full screen invece di centered
- Quick actions: Icone senza testo
- Stats widget: Stack verticale

### Tablet (768px - 1024px)

- Folder structure: 2 colonne
- Modal: Centered con max-width
- Quick actions: Icone + testo corto

### Desktop (> 1024px)

- Folder structure: Grid completo
- Modal: Centered con max-width 500px
- Quick actions: Icone + testo completo
- Stats widget: Sidebar se spazio disponibile

---

## ⚡ PERFORMANCE CONSIDERATIONS

1. **Lazy Loading**: Carica struttura folder solo quando sezione visibile
2. **Caching**: Cache stato folder per 5 minuti
3. **Debounce**: Debounce su input link folder (500ms)
4. **Optimistic Updates**: Aggiorna UI immediatamente, sync dopo
5. **Error Retry**: Retry automatico su errori network (3 tentativi)
6. **Thumbnail Cache**: Cache thumbnail immagini per preview veloce
7. **Pagination**: Lista documenti paginata (50 per pagina)
8. **Virtual Scrolling**: Per liste lunghe di file
9. **Thumbnail Cache**: Cache thumbnail immagini per preview veloce
10. **Pagination**: Lista documenti paginata (50 per pagina)
11. **Virtual Scrolling**: Per liste lunghe di file

---

## 🔐 SICUREZZA

1. **Validazione Input**: Verifica formato folder ID/URL
2. **Permission Check**: Verifica permessi Drive prima di operazioni
3. **Error Handling**: Messaggi errori user-friendly
4. **Rate Limiting**: Limita creazione folder (max 10/min per utente)
5. **Proxy Download**: Tutti i download passano per backend (non link diretti Drive)
6. **Access Control**: Verifica permessi utente prima di mostrare/scaricare file
7. **Proxy Download**: Tutti i download passano per backend (non link diretti Drive)
8. **Access Control**: Verifica permessi utente prima di mostrare/scaricare file

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Fase 1: Core Components

- [ ] Componente `DriveFolderStructure` (Stati A, B, C)
- [ ] Modal `LinkFolderModal`
- [ ] Modal `CreateFolderConfirmModal`
- [ ] API client methods (create, get, link)

### Fase 2: Integration

- [ ] Integrazione in pagina cliente Overview tab
- [ ] Integrazione in lista clienti (card badge)
- [ ] Integrazione in header (quick actions)
- [ ] Integrazione in modal upload documenti
- [ ] Browser documenti dentro workspace (non Drive)
- [ ] Preview immagini direttamente nel workspace
- [ ] Download file via proxy backend (`/api/documents/proxy/{file_id}`)

### Fase 3: Advanced Features

- [ ] Folder statistics widget
- [ ] Upload diretto modal
- [ ] Browser documenti dentro workspace (non Drive)
- [ ] Preview immagini direttamente nel workspace
- [ ] Download file via proxy backend
- [ ] Auto-sync status

### Fase 4: Polish

- [ ] Loading states
- [ ] Error handling
- [ ] Toast notifications
- [ ] Responsive design
- [ ] Accessibility (ARIA labels)

---

---

## 📚 DOCUMENTAZIONE CORRELATA

- **Integration Plan:** `docs/CRM_GOOGLE_DRIVE_INTEGRATION_PLAN.md`
- **Backend Architecture:** `docs/CRM_DRIVE_FOLDER_ARCHITECTURE.md`
- **Download Flow:** `docs/CRM_DRIVE_FOLDER_DOWNLOAD_FLOW.md` ⭐

---

## ✅ VERIFICA PRINCIPIO FONDAMENTALE

Prima di implementare, verifica:

- [ ] ❌ Nessun link esterno a `drive.google.com`
- [ ] ❌ Nessun `window.open()` verso Drive
- [ ] ❌ Nessun redirect a Drive
- [ ] ✅ Tutti i download usano `/api/documents/proxy/{file_id}`
- [ ] ✅ Tutti i preview usano `/api/documents/thumbnail/{file_id}`
- [ ] ✅ Tutti gli upload passano per backend API
- [ ] ✅ Google Drive è completamente invisibile all'utente

---

**Last Updated:** 2026-01-20  
**Principle:** Mai accesso diretto a Drive - tutto via proxy backend  
**Next Step:** Review design → Approvazione → Implementazione
