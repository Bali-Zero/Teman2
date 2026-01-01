# Google Drive Team Setup - Bali Zero

## Overview

- **Total Space**: 30TB
- **Per Department**: 3TB max
- **Per Person**: 10GB personal folder
- **Root Folder**: https://drive.google.com/drive/folders/1hkOeV03YM5-sHbQhswYz809jsrnwC0At

---

## Step 1: Create Department Folders

Nel folder root, crea queste 4 cartelle:

1. **BOARD** - Per direzione e decisioni strategiche
2. **TAX DEPARTMENT** - Pratiche fiscali e contabili
3. **SET UP TEAM** - Pratiche di costituzione (KITAS, PT PMA, etc.)
4. **MARKETING** - Materiali marketing e comunicazione

### Come fare:
1. Apri il folder root
2. Click destro → "New folder"
3. Rinomina con i nomi sopra

---

## Step 2: Create Internal Structure

Per OGNI dipartimento, crea questa struttura:

```
📁 [DEPARTMENT NAME]
├── 📁 _Shared          ← Documenti comuni del dipartimento
│   ├── 📁 Templates    ← Template standard
│   ├── 📁 Procedures   ← SOP e procedure
│   └── 📁 Resources    ← Risorse condivise
│
└── 📁 Members          ← Cartelle personali
    ├── 📁 [Nome Persona 1]
    ├── 📁 [Nome Persona 2]
    └── ...
```

### Membri per Dipartimento:

**BOARD:**
- Zero (Owner)

**TAX DEPARTMENT:**
- Veronika (Head)
- [Altri membri tax se presenti]

**SET UP TEAM:**
- Ruslana (Head)
- Anton
- Dea
- Rina

**MARKETING:**
- [Membri marketing]

---

## Step 3: Configure Permissions

### Principio Base:
- **Owner (Zero)**: Accesso completo a tutto
- **Department Heads**: Accesso completo al proprio dipartimento
- **Members**: Accesso solo alla propria cartella + _Shared del dipartimento

### 3.1 Permessi BOARD

| Folder | Zero |
|--------|------|
| BOARD (tutto) | Owner |

### 3.2 Permessi TAX DEPARTMENT

| Folder | Zero | Veronika | Altri Tax |
|--------|------|----------|-----------|
| TAX DEPARTMENT | Owner | Editor | - |
| TAX/_Shared | Owner | Editor | Viewer |
| TAX/Members/Veronika | Owner | Editor | - |
| TAX/Members/[Altro] | Owner | Editor | Solo proprio |

**Come settare Veronika come Editor di tutto Tax:**
1. Click destro su "TAX DEPARTMENT"
2. "Share" → "Share"
3. Inserisci email Veronika
4. Seleziona "Editor"
5. Deseleziona "Notify people"
6. Click "Share"

### 3.3 Permessi SET UP TEAM

| Folder | Zero | Ruslana | Anton | Dea | Rina |
|--------|------|---------|-------|-----|------|
| SET UP TEAM | Owner | Editor | - | - | - |
| SET UP/_Shared | Owner | Editor | Viewer | Viewer | Viewer |
| SET UP/Members/Ruslana | Owner | Editor | - | - | - |
| SET UP/Members/Anton | Owner | Editor | Editor | - | - |
| SET UP/Members/Dea | Owner | Editor | - | Editor | - |
| SET UP/Members/Rina | Owner | Editor | - | - | Editor |

**Come settare (esempio per Anton):**
1. Click destro su "SET UP TEAM/Members/Anton"
2. "Share" → "Share"
3. Aggiungi Anton come "Editor"
4. Aggiungi Ruslana come "Editor" (può vedere tutto il suo team)

### 3.4 Permessi MARKETING

| Folder | Zero | Marketing Head | Altri Marketing |
|--------|------|----------------|-----------------|
| MARKETING | Owner | Editor | - |
| MARKETING/_Shared | Owner | Editor | Viewer |
| MARKETING/Members/[Nome] | Owner | Editor | Solo proprio |

---

## Step 4: Restrict Inheritance (IMPORTANTE!)

Di default, Google Drive eredita i permessi dal parent. Per bloccare questo:

### Per ogni cartella Members/[Persona]:

1. Click destro sulla cartella personale
2. "Share" → "Share"
3. Click sull'icona ingranaggio ⚙️
4. **DESELEZIONA** "Editors can change permissions and share"
5. Questo impedisce che altri membri vedano cartelle non loro

### Per _Shared folders:

1. Assicurati che i membri abbiano solo "Viewer" (non Editor)
2. Solo il Department Head può modificare

---

## Step 5: Storage Quotas

Google Drive non ha quote native per subfolder. Opzioni:

### Opzione A: Monitoraggio Manuale
- Usa Google Drive → Storage per vedere uso totale
- Controlla periodicamente con script

### Opzione B: Policy Aziendale
- Comunicare limite 10GB/persona
- Revisione mensile

### Opzione C: Google Workspace Admin (se hai Workspace)
- Puoi settare quote per utente in Admin Console

---

## Step 6: Quick Reference - Email Team

Invia questa guida ai membri:

```
ACCESSO GOOGLE DRIVE BALI ZERO

Il tuo folder personale:
[LINK DIRETTO AL FOLDER PERSONALE]

Regole:
1. Usa SOLO il tuo folder personale per file privati
2. Folder _Shared è READ-ONLY (chiedi al tuo head per modifiche)
3. Limite: 10GB per cartella personale
4. NON condividere link esterni senza approvazione

Per problemi: contatta [email supporto]
```

---

## Checklist Finale

- [ ] Creato folder BOARD
- [ ] Creato folder TAX DEPARTMENT
- [ ] Creato folder SET UP TEAM
- [ ] Creato folder MARKETING
- [ ] Creato _Shared in ogni dipartimento
- [ ] Creato Members in ogni dipartimento
- [ ] Creato folder personali per ogni membro
- [ ] Settato Veronika come Editor di TAX
- [ ] Settato Ruslana come Editor di SET UP TEAM
- [ ] Settato permessi individuali per Anton, Dea, Rina
- [ ] Verificato che membri non possano vedere cartelle altrui
- [ ] Inviato link ai membri

---

## Struttura Completa Finale

```
📁 Bali Zero Team (Root) - Owner: Zero
│
├── 📁 BOARD
│   ├── 📁 _Shared
│   │   ├── 📁 Templates
│   │   ├── 📁 Procedures
│   │   └── 📁 Resources
│   └── 📁 Members
│       └── 📁 Zero
│
├── 📁 TAX DEPARTMENT - Editor: Veronika
│   ├── 📁 _Shared (Viewer: all tax members)
│   │   ├── 📁 Templates
│   │   ├── 📁 Procedures
│   │   └── 📁 Resources
│   └── 📁 Members
│       ├── 📁 Veronika
│       └── 📁 [Altri membri tax...]
│
├── 📁 SET UP TEAM - Editor: Ruslana
│   ├── 📁 _Shared (Viewer: Anton, Dea, Rina)
│   │   ├── 📁 Templates
│   │   ├── 📁 Procedures
│   │   └── 📁 Resources
│   └── 📁 Members
│       ├── 📁 Ruslana
│       ├── 📁 Anton - Editor: Anton, Ruslana
│       ├── 📁 Dea - Editor: Dea, Ruslana
│       └── 📁 Rina - Editor: Rina, Ruslana
│
└── 📁 MARKETING
    ├── 📁 _Shared
    │   ├── 📁 Templates
    │   ├── 📁 Procedures
    │   └── 📁 Resources
    └── 📁 Members
        └── 📁 [Membri marketing...]
```

---

## Note Tecniche per Integrazione API

Per integrare con Zantara, useremo:
- **Google Drive API v3**
- **OAuth2** per autenticazione
- **Service Account** per accesso backend

L'integrazione permetterà ai membri di:
1. Vedere i propri file direttamente nell'app Zantara
2. Caricare documenti dalla chat
3. Collegare file a pratiche/clienti nel CRM
