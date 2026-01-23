# Google Drive Documents System - Documentazione Tecnica

**Versione:** 2.0
**Data:** 2026-01-23
**Autore:** Sistema Zantara

---

## Indice

1. [Panoramica](#panoramica)
2. [Architettura](#architettura)
3. [Componenti Frontend](#componenti-frontend)
4. [Hooks Personalizzati](#hooks-personalizzati)
5. [Sistema di Logging](#sistema-di-logging)
6. [Interazioni Utente](#interazioni-utente)
7. [Testing](#testing)
8. [Performance](#performance)
9. [Troubleshooting](#troubleshooting)

---

## Panoramica

Il sistema Documents di Zantara fornisce un'interfaccia simile a Google Drive per la gestione dei documenti aziendali, integrato con Google Drive API tramite Service Account.

### Caratteristiche Principali

- **Provider:** Google Drive API via Service Account
- **Design:** Google Drive-like UX/UI
- **Layout:** 3-colonne (Sidebar, Content, Info Panel)
- **Interazioni:** Single-click select, double-click open
- **Prefetch:** Hover prefetch per navigazione istantanea
- **Keyboard:** Navigazione completa da tastiera

### Palette Colori

| Elemento            | Colore      | Hex       |
| ------------------- | ----------- | --------- |
| Primary Blue        | Google Blue | `#1a73e8` |
| Selected Background | Light Blue  | `#e8f0fe` |
| Hover Background    | Light Gray  | `#f5f5f5` |
| Border              | Gray        | `#dadce0` |
| Text Primary        | Dark Gray   | `#202124` |
| Text Secondary      | Medium Gray | `#5f6368` |

---

## Architettura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  /documents page.tsx (3-column layout)                              │
│  ├─ DriveSidebar.tsx      (224px - Navigation)                     │
│  ├─ Main Content Area     (flex-1)                                  │
│  │   ├─ DriveToolbar.tsx  (Search, View Toggle, Actions)           │
│  │   ├─ DriveBreadcrumb.tsx (Navigation Path)                      │
│  │   ├─ FileGrid.tsx | FileList.tsx (File Display)                 │
│  │   └─ FileGridSkeleton.tsx | FileListSkeleton.tsx (Loading)      │
│  └─ DriveInfoPanel.tsx    (320px - File Details)                   │
│                                                                      │
│  Hooks:                                                              │
│  ├─ useDrive.ts           (Query, Mutations, Prefetch)             │
│  └─ useKeyboardNavigation.ts (Keyboard Shortcuts)                   │
│                                                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ API Proxy (/api/[...path]/route.ts)
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       BACKEND (FastAPI)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  /api/drive/*                                                       │
│  ├─ GET  /status          (Connection status)                      │
│  ├─ GET  /files           (List files in folder)                   │
│  ├─ POST /folder          (Create folder)                          │
│  ├─ POST /doc             (Create Google Doc/Sheet/Slide)          │
│  ├─ PUT  /file/:id/rename (Rename file)                            │
│  ├─ POST /move            (Move files)                              │
│  ├─ DELETE /file/:id      (Delete file)                            │
│  ├─ GET  /download/:id    (Download file)                          │
│  └─ POST /upload          (Upload file)                             │
│                                                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ Google Drive API (Service Account)
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      GOOGLE DRIVE                                    │
│                 (Shared Drive / Folder)                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Componenti Frontend

### 1. DriveSidebar (`DriveSidebar.tsx`)

Sidebar di navigazione stile Google Drive.

**Props:**

```typescript
interface DriveSidebarProps {
  activeView: 'my-drive' | 'recent' | 'starred' | 'trash';
  onViewChange: (view: 'my-drive' | 'recent' | 'starred' | 'trash') => void;
  onNewClick: (e: React.MouseEvent) => void;
  onUploadClick: () => void;
  storageUsed?: number;
  storageTotal?: number;
  isCollapsed?: boolean;
}
```

**Elementi:**

- Pulsante "Nuovo" per creare cartelle/documenti
- Navigazione: Il mio Drive, Recenti, Speciali, Cestino
- Indicatore spazio di archiviazione con barra colorata

### 2. DriveInfoPanel (`DriveInfoPanel.tsx`)

Pannello laterale destro per dettagli file.

**Props:**

```typescript
interface DriveInfoPanelProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
  onPreview: (file: FileItem) => void;
  onDownload: (file: FileItem) => void;
  onDelete: (file: FileItem) => void;
}
```

**Informazioni visualizzate:**

- Nome file e icona
- Tipo file/cartella
- Dimensione (per file)
- Data modifica
- Link Google Drive
- Azioni rapide (Anteprima, Scarica, Elimina)

### 3. FileGrid (`FileGrid.tsx`)

Vista griglia per file e cartelle.

**Caratteristiche:**

- Cards con hover effect
- Prefetch on hover per cartelle
- Selezione visiva con bordo blu
- Context menu su right-click

### 4. FileList (`FileList.tsx`)

Vista lista tabellare.

**Colonne:**

- Checkbox (visibile on hover/selected)
- Nome con icona
- Data modifica
- Dimensione
- Azioni

### 5. Skeleton Loaders

**FileGridSkeleton.tsx:**

- Griglia 5 colonne
- Cards animate con shimmer
- Configurable via `count` prop

**FileListSkeleton.tsx:**

- Header sticky con colonne placeholder
- Righe con shimmer animation
- Responsive (nasconde colonne su mobile)

---

## Hooks Personalizzati

### useDriveFiles

Query per recuperare file di una cartella.

```typescript
function useDriveFiles(folderId: string | null, searchQuery: string = '');
```

**Features:**

- Cache 1 minuto
- Placeholder data durante fetch
- Supporto ricerca

### usePrefetchFolder

Prefetch contenuto cartella on hover.

```typescript
function usePrefetchFolder(): { prefetchFolder: (folderId: string) => void };
```

**Logging integrato:**

- `logPrefetchStarted` - Inizio prefetch
- `logPrefetchCompleted` - Completamento con durata e count
- `logPrefetchSkipped` - Skip se già in cache
- `logPrefetchError` - Errori

### useKeyboardNavigation

Navigazione completa da tastiera.

```typescript
interface UseKeyboardNavigationOptions {
  files: FileItem[];
  selectedFiles: Set<string>;
  onSelect: (files: Set<string>) => void;
  onOpen: (file: FileItem) => void;
  onDelete?: (files: FileItem[]) => void;
  enabled?: boolean;
}
```

**Shortcuts:**

| Tasto                | Azione                |
| -------------------- | --------------------- |
| `↑ / ↓`              | Naviga su/giù         |
| `← / →`              | Naviga (alias su/giù) |
| `Shift + ↑/↓`        | Selezione range       |
| `Enter`              | Apri file/cartella    |
| `Space`              | Toggle selezione      |
| `Cmd/Ctrl + A`       | Seleziona tutto       |
| `Escape`             | Deseleziona           |
| `Delete / Backspace` | Elimina selezionati   |
| `Home`               | Vai al primo          |
| `End`                | Vai all'ultimo        |

---

## Sistema di Logging

### DriveLogger (`src/lib/logging/drive-logger.ts`)

Logger strutturato per tutte le operazioni Drive.

**Categorie:**

| Categoria      | Descrizione          |
| -------------- | -------------------- |
| `USER_ACTION`  | Interazioni utente   |
| `API_CALL`     | Chiamate API         |
| `STATE_CHANGE` | Cambiamenti stato    |
| `PERFORMANCE`  | Metriche performance |
| `ERROR`        | Errori               |
| `KEYBOARD`     | Shortcuts tastiera   |
| `PREFETCH`     | Operazioni prefetch  |

**Metodi principali:**

```typescript
// User Actions
logFileSelected(fileId, fileName, isMultiSelect);
logFileOpened(fileId, fileName, isFolder);
logFileDeleted(fileIds, fileNames);
logViewModeChange(oldMode, newMode);
logInfoPanelToggle(isOpen);

// Navigation
logFolderNavigation(folderId, folderName, fromBreadcrumb);
logBreadcrumbClick(folderId, folderName, depth);
logSidebarNavigation(view);

// Keyboard
logKeyboardShortcut(key, action, modifiers);
logKeyboardNavigation(direction, newIndex);

// Prefetch
logPrefetchStarted(folderId);
logPrefetchCompleted(folderId, duration, fileCount);
logPrefetchSkipped(folderId, reason);
logPrefetchError(folderId, error);

// Performance
logPageLoad(duration);
logRenderTime(componentName, duration);
logNavigationPerformance(folderId, duration, fileCount);
```

**Output Development:**

```
🚀 [DEBUG] [PREFETCH] Prefetch started { folderId: "abc123" }
⚡ [DEBUG] [PREFETCH] Prefetch completed { folderId: "abc123", duration: 145, fileCount: 12 }
⌨️ [DEBUG] [KEYBOARD] Keyboard shortcut used { key: "Enter", action: "open" }
```

---

## Interazioni Utente

### Click Behavior (Google Drive Style)

| Azione              | Risultato          |
| ------------------- | ------------------ |
| Single Click        | Seleziona file     |
| Double Click        | Apre file/cartella |
| Cmd/Ctrl + Click    | Toggle selezione   |
| Shift + Click       | Selezione range    |
| Right Click         | Context menu       |
| Click su area vuota | Deseleziona tutto  |

### Context Menu

Disponibile su right-click con opzioni:

- Apri
- Anteprima
- Rinomina
- Sposta
- Scarica
- Elimina

---

## Testing

### Test Files

```
src/
├── app/(workspace)/documents/components/__tests__/
│   ├── FileGridSkeleton.test.tsx
│   ├── FileListSkeleton.test.tsx
│   ├── DriveSidebar.test.tsx
│   └── DriveInfoPanel.test.tsx
├── hooks/__tests__/
│   ├── useKeyboardNavigation.test.ts
│   └── usePrefetchFolder.test.ts
```

### Run Tests

```bash
cd apps/mouth
npm test
# or
npx vitest
```

### Test Coverage

| Componente            | Tests    |
| --------------------- | -------- |
| FileGridSkeleton      | 6 tests  |
| FileListSkeleton      | 8 tests  |
| DriveSidebar          | 12 tests |
| DriveInfoPanel        | 15 tests |
| useKeyboardNavigation | 18 tests |
| usePrefetchFolder     | 7 tests  |

---

## Performance

### Ottimizzazioni Implementate

1. **Prefetch on Hover**
   - Prefetch folder contents quando l'utente passa sopra una cartella
   - Cache 1 minuto per evitare chiamate duplicate
   - Navigazione percepita come istantanea

2. **Skeleton Loaders**
   - Rimpiazzano spinner per migliore perceived performance
   - Shimmer animation per feedback visivo
   - Layout shift minimo

3. **Placeholder Data**
   - Mantiene dati precedenti durante caricamento nuova cartella
   - Transizioni fluide tra cartelle

4. **Optimistic Updates**
   - Delete file rimuove immediatamente dalla UI
   - Rollback automatico in caso di errore

### Metriche Target

| Metrica           | Target  | Misurazione                          |
| ----------------- | ------- | ------------------------------------ |
| Initial Load      | < 1s    | driveLogger.logPageLoad              |
| Folder Navigation | < 200ms | driveLogger.logNavigationPerformance |
| Prefetch          | < 500ms | driveLogger.logPrefetchCompleted     |

---

## Troubleshooting

### Errore: "Non connesso a Google Drive"

**Causa:** Service Account non configurato o token scaduto.

**Soluzione:**

1. Verificare variabili ambiente GOOGLE*SERVICE_ACCOUNT*\*
2. Controllare che il Service Account abbia accesso alla cartella condivisa
3. Verificare logs backend per errori OAuth

### Prefetch non funziona

**Causa:** Cache già presente o errore silenzioso.

**Soluzione:**

1. Aprire DevTools Console
2. Cercare logs `[PREFETCH]`
3. Verificare se mostra "Prefetch skipped (cached)"

### Keyboard shortcuts non rispondono

**Causa:** Focus su input field o disabled.

**Soluzione:**

1. Verificare che il focus non sia in un campo input
2. Controllare che `enabled` sia true nel hook
3. Verificare che la lista files non sia vuota

### File non caricano

**Causa:** Errore API o permessi insufficienti.

**Soluzione:**

1. Controllare Console per errori API
2. Verificare logs `[API_CALL]` nel logger
3. Controllare permessi Service Account su Google Drive

---

## Changelog

### v2.0 (2026-01-23)

- UI trasformata in stile Google Drive
- Aggiunto layout 3-colonne con DriveSidebar e DriveInfoPanel
- Implementato prefetch on hover
- Aggiunto supporto keyboard navigation completo
- Implementato structured logging
- Aggiunto skeleton loaders
- Single-click select, double-click open behavior

### v1.0 (Initial)

- Implementazione base con integrazione Google Drive API
- File grid e list views
- Upload, download, delete files
- Create folders and documents
