# 🚀 Deploy Checklist - 2026-01-19

## 📊 Stato Attuale

### Modifiche in Attesa

**Staged (6 file):**

- ✅ Rimozione file duplicati dalla struttura ricorsiva
- ✅ Pulizia repository

**Non Staged (24 file):**

- ✅ **CRITICO**: Fix errore TypeScript in `apps/mouth/src/app/api/[...path]/route.ts`
- ✅ Fix import duplicati in `apps/mouth/src/lib/utils/storage.ts`
- ⚠️ Modifiche backend (constants.py, intent_classifier.py)
- 📄 Documentazione aggiornata
- 📊 Dati scraper aggiornati

## ✅ Modifiche Critiche per Deploy

### 1. Fix Errore TypeScript (route.ts)

**File**: `apps/mouth/src/app/api/[...path]/route.ts`
**Problema**: Errore di sintassi bloccante (`error TS1005: '}' expected`)
**Status**: ✅ **RISOLTO** - Codice corretto, import aggiunti
**Azione**: Committare prima del deploy

### 2. Fix Import Duplicati (storage.ts)

**File**: `apps/mouth/src/lib/utils/storage.ts`
**Problema**: Import duplicati di `logger` e `toError`
**Status**: ✅ **RISOLTO** - Import duplicati rimossi
**Azione**: Committare prima del deploy

## ⚠️ Errori TypeScript Rimanenti (Non Bloccanti)

Il file `next.config.ts` ha `ignoreBuildErrors: true`, quindi questi errori non bloccano il build:

- `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` - Errori di tipo
- `apps/mouth/src/app/(workspace)/dashboard/page.tsx` - Duplicati identifier

**Raccomandazione**: Risolvere in un secondo momento, non bloccano il deploy.

## 📋 Checklist Pre-Deploy

### Prima del Deploy

- [ ] Committare le modifiche critiche:

  ```bash
  git add apps/mouth/src/app/api/[...path]/route.ts
  git add apps/mouth/src/lib/utils/storage.ts
  git add apps/backend-rag/apps/  # Rimozioni struttura ricorsiva
  git commit -m "fix: resolve TypeScript errors and cleanup recursive structure"
  ```

- [ ] Verificare che il build funzioni:

  ```bash
  cd apps/mouth && npm run build
  ```

- [ ] (Opzionale) Verificare modifiche backend:
  ```bash
  cd apps/backend-rag && python -m pytest backend/tests/ -v --tb=short
  ```

### Deploy

- [ ] Push a `main`:

  ```bash
  git push origin main
  ```

- [ ] Verificare deploy automatico (Vercel/Fly.io)

## 🎯 Raccomandazione

**✅ SÌ, c'è da fare deploy** dopo aver committato le modifiche critiche:

1. **Priorità ALTA**: Fix errore TypeScript in `route.ts` (blocca build)
2. **Priorità MEDIA**: Fix import duplicati in `storage.ts`
3. **Priorità BASSA**: Pulizia struttura ricorsiva (già staged)

**Ordine di azione:**

1. Committare modifiche critiche
2. Verificare build
3. Push e deploy

## 📝 Note

- Le modifiche a documentazione e dati scraper non richiedono deploy immediato
- Gli errori TypeScript rimanenti sono non bloccanti grazie a `ignoreBuildErrors: true`
- La struttura ricorsiva è già stata rimossa fisicamente, le modifiche staged sono solo per Git
