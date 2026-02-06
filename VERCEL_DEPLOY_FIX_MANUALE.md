# ✅ FIX DEPLOY VERCEL - Azione Manuale Richiesta

## 🎯 Problema

Il deploy su Vercel sta fallendo con l'errore:

```
ERR_PNPM_META_FETCH_FAIL  GET https://registry.npmjs.org/...: Value of "this" must be of type URLSearchParams
```

## 🔍 Root Cause

La **Root Directory** nel dashboard Vercel è configurata su `apps/mouth` invece di `.` (root del repository).

Questo causa conflitti con la cache di Vercel e con pnpm, che non riesce a risolvere correttamente le dipendenze del monorepo.

## 📋 Soluzione (MANUALE)

### 1. Apri Dashboard Vercel

Vai su: https://vercel.com/nuzantara-2026/mouth/settings

### 2. Modifica Root Directory

1. Nella sezione **General**, scorri fino a trovare **Root Directory**
2. **Attuale**: `apps/mouth`
3. **Nuovo**: `.` (solo un punto, senza path)
4. Clicca **Save**

### 3. Verifica Build Settings

Nella sezione **Build & Development Settings**, assicurati che siano configurati:

- **Build Command**: `pnpm build --filter=mouth`
- **Output Directory**: `apps/mouth/.next`
- **Install Command**: `pnpm install`
- **Framework Preset**: Next.js

### 4. Pulisci Cache (Consigliato)

Dopo aver salvato, trigga un nuovo deployment **con cache pulita**:

1. Vai alla lista dei deployment
2. Clicca sui 3 puntini dell'ultimo deployment fallito
3. Seleziona **Redeploy**
4. Spunta **Clear cache and redeploy**

### 5. Monitora il Deployment

Il nuovo deployment dovrebbe completare in circa 3-4 minuti con successo.

## 📊 Status Attuale

- ✅ `vercel.json` corretto (commitato e pushato)
- ❌ Root Directory nel dashboard: **da configurare manualmente**
- ⏳ In attesa di configurazione manuale

## 🔄 Cosa è Stato Fatto

1. ✅ Corretto `vercel.json` con:
   - Framework: nextjs
   - Build command: `pnpm build --filter=mouth`
   - Output directory: `apps/mouth/.next`
   - Install command: `pnpm install`

2. ✅ Pushato su GitHub (commit `60437f04f`)

3. ⏳ In attesa: Configurazione Root Directory nel dashboard Vercel

## 📚 Riferimenti

- Deployment fallito più recente: `mouth-mq8t05qse-nuzantara-2026.vercel.app`
- Ultimo deployment funzionante: 1 giorno fa (quando Root Directory era corretto)
- Pattern: Tutti i deployment dell'ultima giornata falliscono, quelli precedenti funzionavano

## 🎯 Prossimi Passi

1. **Tu (manuale)**: Configura Root Directory a `.` nel dashboard Vercel
2. **Vercel (automatico)**: Triggera nuovo deployment
3. **Verifica**: Deployment dovrebbe completare con successo in ~3 minuti

---

**IMPORTANTE**: Il file `vercel.json` è già corretto e committato. L'unica modifica rimasta è la configurazione del **Root Directory nel dashboard Vercel**, che richiede accesso al browser e login.
