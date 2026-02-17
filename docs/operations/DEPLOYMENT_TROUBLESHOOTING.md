# Deployment Troubleshooting Guide

**Last Updated:** 2026-01-16
**Status:** Production Ready

---

## 📋 Overview

Questa guida documenta problemi comuni di deployment e le loro soluzioni, basata su incidenti reali in produzione.

---

## 🚨 Caso Studio: Build Failures dopo Cleanup (16 Gen 2026)

### **Problema**

6 deployment consecutivi falliti su Vercel dopo commit di cleanup che eliminava file "legacy".

### **Root Cause**

File eliminati contenevano **implementazioni complete** ancora utilizzate dal codice:

- `enhanced-analytics.tsx` (270 righe)
- `dashboard-metrics.ts` (303 righe)
- `QueryProvider.tsx` (65 righe)
- `ZohoConnectBanner.tsx`

### **Errori Osservati**

#### 1. Missing Module Exports

```
Export enhancedAnalytics doesn't exist in target module
Module not found: Can't resolve '@/lib/enhanced-analytics'
```

**Causa:** Stub creati con solo 2-4 metodi vs 12+ metodi richiesti nell'originale.

#### 2. QueryClient Not Set

```
Error: No QueryClient set, use QueryClientProvider to set one
Export encountered an error on /chat/page
```

**Causa:** QueryProvider stub vuoto senza inizializzazione di `QueryClient`.

#### 3. Module Build Errors

```
at <unknown> (./apps/mouth/src/components/email/index.ts:1:1)
Module not found: Can't resolve './ZohoConnectBanner'
```

**Causa:** File eliminato ma ancora esportato in `index.ts`.

---

## ✅ Soluzioni Applicate

### 1. **Verifica Implementazione Originale**

```bash
# Prima di creare stub, controllare contenuto originale
git show HEAD^:path/to/file.ts | head -100

# Verificare tutte le exports
git show HEAD^:path/to/file.ts | grep "export"
```

### 2. **Ripristino File Completi**

```bash
# Ripristinare file originale invece di stub
git show HEAD^:path/to/file.ts > path/to/file.ts
git add path/to/file.ts
git commit -m "fix: restore original implementation"
```

### 3. **Test Build Locale**

```bash
# SEMPRE testare build prima di push
cd apps/mouth
npm run build

# Verificare tutte le pagine
# Output atteso: ✓ Generating static pages (62/62)
```

---

## 📝 Lezioni Apprese (CRITICHE)

### ⚠️ **REGOLA 1: Non Creare Stub Senza Verificare Originale**

**MAI fare:**

```typescript
// ❌ SBAGLIATO - stub minimo senza verificare originale
export const analytics = {
  track: () => {},
};
```

**SEMPRE fare:**

```bash
# ✅ CORRETTO - verificare implementazione originale prima
git show HEAD^:apps/mouth/src/lib/analytics.ts | wc -l
# Output: 270 righe → RIPRISTINARE, non creare stub!
```

### ⚠️ **REGOLA 2: Test Build Locale Prima di Push**

```bash
# Workflow corretto per ogni modifica
1. Fare modifiche
2. npm run build          # Test build locale
3. git add .
4. git commit
5. git push               # Solo se build OK
```

**Tempo perso senza test locale:**

- 6 deployment falliti × 3 minuti = 18 minuti
- Debug errori deployment = 30 minuti
- **Totale: 48 minuti vs 2 minuti di test locale**

### ⚠️ **REGOLA 3: Verificare TUTTI i File Eliminati**

```bash
# Prima di cleanup, lista file eliminati
git diff --name-only --diff-filter=D | grep "apps/mouth/src"

# Verificare se sono importati
for file in $(git diff --name-only --diff-filter=D); do
  basename=$(basename $file .tsx .ts)
  grep -r "from.*$basename" apps/mouth/src && echo "⚠️  $file ANCORA USATO"
done
```

### ⚠️ **REGOLA 4: Monorepo - Controllare OGNI Progetto Vercel**

**Setup Nuzantara:**

- Root workspace: `nuzantara` (solo config, non deployabile)
- App frontend: `mouth` (apps/mouth/) → **deployment principale**
- App backend: `backend-rag` (apps/backend-rag/)

**Verificare deployment:**

```bash
# Ogni app ha deployment separato
apps/mouth/.vercel/project.json          → Vercel project "mouth"
apps/backend-rag/.vercel/project.json    → Vercel project "backend-rag"
.vercel/project.json                     → Vercel project "nuzantara" (⚠️  non usato)
```

---

## 🔧 Workflow Deployment Corretto

### Pre-Push Checklist

```bash
# 1. Test build locale
cd apps/mouth && npm run build

# 2. Verificare output
✓ Generating static pages (62/62)    # ← Tutte le pagine OK

# 3. Controllare warnings
⚠️ Failed to copy traced files        # ← OK, solo warning standalone mode

# 4. Se build OK → Push
git push origin main
```

### Monitoraggio Deployment

```
1. Push su GitHub
   ↓
2. Vercel auto-deploy triggered
   ↓
3. Controllare ENTRAMBI i progetti:
   - mouth (principale) → DEVE essere Ready
   - nuzantara (root)   → Ignorare (deployment non necessario)
```

---

## 🐛 Debug Deployment Failures

### Errore: Module Not Found

**Sintomo:**

```
Module not found: Can't resolve '@/lib/xxx'
```

**Debug:**

```bash
# 1. Verificare file esiste
ls -la apps/mouth/src/lib/xxx.*

# 2. Verificare è committato
git ls-tree -r HEAD | grep xxx

# 3. Verificare exports
cat apps/mouth/src/lib/xxx.ts | grep export
```

### Errore: Missing Exports

**Sintomo:**

```
Export 'functionName' doesn't exist in target module
```

**Debug:**

```bash
# Confrontare exports stub vs originale
git show HEAD^:path/file.ts | grep "export function"    # Originale
cat path/file.ts | grep "export function"                # Attuale

# Se diversi → ripristinare originale
git show HEAD^:path/file.ts > path/file.ts
```

### Errore: QueryClient Not Set

**Sintomo:**

```
Error: No QueryClient set, use QueryClientProvider to set one
```

**Soluzione:**

```typescript
// QueryProvider DEVE inizializzare QueryClient
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function getQueryClient() {
  if (typeof window === "undefined") {
    return new QueryClient();
  }
  // Singleton per browser
  if (!browserQueryClient) {
    browserQueryClient = new QueryClient();
  }
  return browserQueryClient;
}
```

---

## 📊 Metriche Deployment

### Target

- ✅ Build success rate: >95%
- ✅ Deploy time: <3 minuti
- ✅ Zero-downtime deployments

### Incidente 16 Gen 2026

- ❌ 6 deployment falliti consecutivi
- ⏱️ 48 minuti downtime
- ✅ Risolto con ripristino file originali

### Miglioramenti Post-Incidente

1. ✅ Pre-commit hook: test build locale
2. ✅ Documentazione troubleshooting
3. ✅ Checklist cleanup file
4. ✅ Verifica monorepo deployment separati

---

## 🔗 Risorse

- [Next.js Build Errors](https://nextjs.org/docs/messages/prerender-error)
- [Vercel Deployment Logs](https://vercel.com/nuzantara-2026/mouth/deployments)
- [React Query Setup](https://tanstack.com/query/latest/docs/react/quick-start)

---

## 📞 Escalation

**Se deployment continua a fallire dopo 2 tentativi:**

1. Verificare Vercel status page
2. Rollback all'ultimo commit funzionante
3. Investigare in locale con `npm run build`
4. Non fare push finché build locale non è OK

**Ultimo deploy riuscito:** `dba82171` (16 Gen 2026 22:15)
