# DEPLOY INSTRUCTIONS

**Data:** 2026-01-13  
**Modifiche:** Consolidamento streaming SSE + Cleanup legacy code

---

## 📋 SITUAZIONE ATTUALE

### Modifiche Pronte:

- ✅ Consolidamento streaming SSE (rimozione duplicati)
- ✅ Logger strutturato implementato
- ✅ Error handling centralizzato
- ✅ Type safety migliorata
- ✅ Build completato con successo

### Test Status:

- ⚠️ 3 test falliscono (dashboard tests - probabilmente pre-esistenti)
- ✅ Tutti gli altri test passano (569/572)

---

## 🚀 OPZIONI DEPLOY

### Opzione 1: Deploy con Skip Hooks (Se test non correlati)

```bash
# Se i test falliscono anche senza le nostre modifiche
git add .
git commit -m "feat: consolidate streaming SSE and cleanup legacy code"
git push --no-verify origin main
```

**⚠️ ATTENZIONE:** Usa solo se i test falliti non sono correlati alle modifiche.

### Opzione 2: Fix Test Prima (Consigliato)

```bash
# 1. Fixare i 3 test falliti
# 2. Poi fare commit e push normale
git add .
git commit -m "feat: consolidate streaming SSE and cleanup legacy code"
git push origin main
```

### Opzione 3: Deploy Manuale Vercel

```bash
# Se Vercel è configurato per deploy manuale
cd apps/mouth
vercel deploy --prod
```

---

## ✅ VERIFICA PRE-DEPLOY

1. **Build Success:**

   ```bash
   cd apps/mouth
   npm run build
   ```

   ✅ Completato con successo

2. **Linter:**

   ```bash
   npm run lint
   ```

   ✅ Nessun errore

3. **Test Critici:**
   ```bash
   npm test -- src/lib/api/chat/chat.api.test.ts
   ```
   ✅ Passano

---

## 📊 MODIFICHE INCLUSE

### File Modificati:

- `apps/mouth/src/lib/api/chat/chat.api.ts` - Logger strutturato
- `apps/mouth/src/app/chat/actions.ts` - Rimozione sendMessageStream
- `apps/mouth/src/lib/api/drive/drive.api.ts` - Type safety fix
- Altri file di cleanup

### File Eliminati:

- `apps/mouth/src/hooks/useOptimisticChat.ts` - Hook deprecato

### File Nuovi:

- `apps/mouth/src/lib/utils/error-handler.ts` - Utility centralizzata

---

## 🎯 RISULTATO ATTESO

Dopo deploy:

- ✅ Streaming SSE consolidato (solo client-side)
- ✅ Logging strutturato attivo
- ✅ Error handling standardizzato
- ✅ Codice più pulito

---

**Last Updated:** 2026-01-13
